"""
PoC de pipeline RAG — Assistente de Atendimento NovaTech
Exercício 1.3 — Papel: Desenvolvedor (DGS / DB1)

Etapas implementadas (conforme enunciado):
  1. Ingestao  -> le os .md, faz chunking *section-aware* com overlap, anexa metadados
  2. Busca     -> embedding da pergunta + top-N por similaridade de cosseno
  3. Montagem  -> system prompt + chunks recuperados + pergunta

Backend pluggavel:
  - REAL    : sentence-transformers (all-MiniLM-L6-v2) + ChromaDB   <- o que roda em prod / com internet
  - FALLBACK: TF-IDF (scikit-learn) + cosseno em numpy             <- roda offline, sem download de modelo
O pipeline detecta automaticamente o que esta disponivel e informa qual backend usou.
A MECANICA do RAG (chunk -> embed -> store -> retrieve -> assemble) e identica nos dois.
"""

from __future__ import annotations
import os, re, glob, json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional

# ----------------------------------------------------------------------------- #
# 1. INGESTAO: carga + parsing de metadados + chunking section-aware
# ----------------------------------------------------------------------------- #

# Mapeia o nome de arquivo -> doc_id canonico e versao (resolve a ambiguidade PROC-042 v1 vs v2)
DOC_REGISTRY = {
    "POL-001-politica-devolucao.md":            {"doc_id": "POL-001",      "version": "3.1"},
    "PROC-042-frete-especial-v1.md":             {"doc_id": "PROC-042",     "version": "1.0"},
    "PROC-042-v2-frete-especial-revisado.md":    {"doc_id": "PROC-042-v2",  "version": "2.0"},
    "SLA-2024-tabela-sla-clientes.md":           {"doc_id": "SLA-2024",     "version": "2024.1"},
    "FAQ-atendimento.md":                        {"doc_id": "FAQ",          "version": "nao-controlada"},
}


@dataclass
class Chunk:
    chunk_id: str
    text: str                      # texto que vai para o embedding (com "breadcrumb" de contexto)
    doc_id: str
    version: str
    section: str                   # ex: "3.2" ou "Item 8"
    section_title: str
    source_type: str               # "normativo" | "procedimento" | "contratual" | "informal"
    doc_date: str
    has_table: bool
    approx_tokens: int
    meta: Dict = field(default_factory=dict)


def _approx_tokens(text: str) -> int:
    # regra pratica do treinamento: ~0.75 palavra por token  ->  tokens ~= palavras / 0.75
    return round(len(text.split()) / 0.75)


def _parse_header(md: str) -> Dict[str, str]:
    """Extrai os campos **Chave:** valor do cabecalho do documento."""
    header = {}
    for line in md.splitlines()[:15]:
        m = re.match(r"\*\*(.+?):\*\*\s*(.+)", line.strip())
        if m:
            header[m.group(1).strip().lower()] = m.group(2).strip()
    return header


def _classify_source(doc_id: str, header: Dict[str, str]) -> str:
    cls = (header.get("classificacao") or header.get("classificação") or
           header.get("status") or "").lower()
    if doc_id == "FAQ" or "informal" in cls or "nao controlada" in cls or "não controlada" in cls:
        return "informal"
    if "contratual" in cls:
        return "contratual"
    if "normativo" in cls:
        return "normativo"
    if doc_id.startswith("PROC"):
        return "procedimento"
    return "normativo"


# secoes que sao "ruido" para o RAG (objetivo, escopo, avisos) — indexamos so o que responde perguntas
_NOISE_TITLES = ("objetivo", "escopo", "aviso interno", "perguntas selecionadas")


def _linearize_table(body_lines: List[str]) -> str:
    """Converte uma tabela markdown em frases auto-descritivas, uma por linha.
    Ex.: '| Gold | 2h | 24h |' -> 'Gold: Tempo de resposta = 2h; Resolução = 24h.'
    CORRECAO: tabelas embedam mal (celulas nao repetem os termos da pergunta);
    linearizar aumenta recall de perguntas tabulares (SLA por tier, multiplicador por regiao)."""
    rows = [l for l in body_lines if l.strip().startswith("|")]
    if len(rows) < 2:
        return ""
    def cells(r): return [c.strip() for c in r.strip().strip("|").split("|")]
    header = cells(rows[0])
    out = []
    for r in rows[2:]:  # pula header e separador (---)
        vals = cells(r)
        if not vals or all(not v for v in vals):
            continue
        key = vals[0]
        pairs = [f"{header[i]} = {vals[i]}" for i in range(1, min(len(header), len(vals))) if vals[i]]
        out.append(f"{header[0]} {key}: " + "; ".join(pairs) + ".")
    return "\n".join(out)


def chunk_markdown(path: str, max_tokens: int = 450, overlap_ratio: float = 0.12,
                   linearize_tables: bool = False) -> List[Chunk]:
    """
    Chunking SECTION-AWARE:
      - quebra nos cabecalhos markdown (##, ###); cada secao-folha vira 1 chunk
      - tabelas NUNCA sao divididas (chunk inteiro preservado)
      - secoes muito longas (sem tabela) sao subdivididas por paragrafo com overlap
      - cada chunk recebe um "breadcrumb" [DOC | Secao] no inicio -> contexto p/ embedding e citacao
    Justificativa: as perguntas dos atendentes mapeiam para SECOES inteiras
    ("qual o prazo de devolucao" -> POL-001 secao 3.1), entao a secao e a unidade
    semantica natural; alem disso, mitiga 'lost in the middle' (poucos chunks, densos e
    auto-descritivos) e protege as tabelas de frete/SLA de serem cortadas no meio.
    """
    fname = os.path.basename(path)
    reg = DOC_REGISTRY[fname]
    with open(path, encoding="utf-8") as f:
        md = f.read()

    header = _parse_header(md)
    doc_title = md.splitlines()[0].lstrip("# ").strip()
    doc_date = (header.get("última atualização") or header.get("ultima atualizacao") or
                header.get("data de emissão") or header.get("data de emissao") or "s/data")
    source_type = _classify_source(reg["doc_id"], header)

    # particiona o corpo por cabecalhos, guardando a hierarquia de titulos
    lines = md.splitlines()
    sections = []  # (level, num, title, body_lines)
    cur = None
    for ln in lines:
        h = re.match(r"^(#{2,4})\s+(.*)", ln)
        if h:
            if cur:
                sections.append(cur)
            title_raw = h.group(2).strip()
            num_m = re.match(r"^(\d+(?:\.\d+)*)\.?\s*(.*)", title_raw)
            item_m = re.match(r"^Item\s+(\d+)\s*[—-]?\s*(.*)", title_raw)
            if num_m:
                num, title = num_m.group(1), num_m.group(2) or title_raw
            elif item_m:
                num, title = f"Item {item_m.group(1)}", item_m.group(2) or title_raw
            else:
                num, title = "", title_raw
            cur = {"level": len(h.group(1)), "num": num, "title": title, "body": []}
        elif cur is not None:
            cur["body"].append(ln)
    if cur:
        sections.append(cur)

    chunks: List[Chunk] = []
    seq = 0
    for sec in sections:
        title_l = (sec["title"] or "").lower()
        if any(n in title_l for n in _NOISE_TITLES) and not sec["num"]:
            continue
        body = "\n".join(sec["body"]).strip()
        if not body:
            continue
        has_table = any(l.strip().startswith("|") for l in sec["body"])
        if has_table and linearize_tables:
            lin = _linearize_table(sec["body"])
            if lin:
                body = body + "\n" + lin
        breadcrumb = f"[{reg['doc_id']} v{reg['version']} — {doc_title} | Seção {sec['num']} {sec['title']}]".strip()

        # decide se subdivide
        units = [body]
        if not has_table and _approx_tokens(body) > max_tokens:
            paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
            units, buf = [], ""
            for p in paras:
                if _approx_tokens(buf + " " + p) > max_tokens and buf:
                    units.append(buf.strip())
                    # overlap: carrega o final do bloco anterior
                    tail = " ".join(buf.split()[-int(len(buf.split()) * overlap_ratio):])
                    buf = tail + " " + p
                else:
                    buf = (buf + "\n\n" + p) if buf else p
            if buf.strip():
                units.append(buf.strip())

        for u in units:
            seq += 1
            text = f"{breadcrumb}\n{u}"
            chunks.append(Chunk(
                chunk_id=f"{reg['doc_id']}::sec{sec['num'] or seq}::{seq}",
                text=text,
                doc_id=reg["doc_id"], version=reg["version"],
                section=sec["num"] or f"§{seq}", section_title=sec["title"],
                source_type=source_type, doc_date=doc_date,
                has_table=has_table, approx_tokens=_approx_tokens(text),
                meta={"doc_title": doc_title, "responsavel": header.get("responsável",
                       header.get("responsavel", ""))},
            ))
    return chunks


def ingest(docs_glob: str, linearize_tables: bool = False) -> List[Chunk]:
    chunks = []
    for path in sorted(glob.glob(docs_glob)):
        if os.path.basename(path) in DOC_REGISTRY:
            chunks.extend(chunk_markdown(path, linearize_tables=linearize_tables))
    return chunks


# ----------------------------------------------------------------------------- #
# 2. EMBEDDINGS + VECTOR STORE (backend pluggavel)
# ----------------------------------------------------------------------------- #

class BaseEmbedder:
    name = "base"
    def fit(self, texts: List[str]): ...
    def encode(self, texts: List[str]): ...


class SentenceTransformerEmbedder(BaseEmbedder):
    """Caminho REAL (semantico). Requer internet/HuggingFace na 1a execucao."""
    name = "sentence-transformers/all-MiniLM-L6-v2 (semantico)"
    def __init__(self):
        from sentence_transformers import SentenceTransformer  # import tardio
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
    def fit(self, texts): pass
    def encode(self, texts):
        return self.model.encode(texts, normalize_embeddings=True)


class TfidfEmbedder(BaseEmbedder):
    """Fallback OFFLINE (lexico). Roda sem download de modelo."""
    name = "tf-idf scikit-learn (lexico, fallback offline)"
    _PT_STOP = ("de a o que e do da em um para com nao uma os no se na por mais as dos como "
                "mas ao ele das seu sua ou quando muito nos ja esta eu tambem so pelo pela ate "
                "isso ela entre era depois sem mesmo aos ter seus quem nas me esse eles voce essa "
                "num nem suas meu as minha numa pelos elas qual seja").split()
    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1,
                                   stop_words=list(self._PT_STOP), lowercase=True)
        self._fitted = None
    def fit(self, texts):
        self.matrix = self.vec.fit_transform(texts)
    def encode(self, texts):
        import numpy as np
        m = self.vec.transform(texts).toarray()
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return m / norms


def make_embedder(prefer_real: bool = True) -> BaseEmbedder:
    if prefer_real:
        try:
            return SentenceTransformerEmbedder()
        except Exception as e:
            print(f"[backend] sentence-transformers indisponivel ({type(e).__name__}); "
                  f"usando fallback TF-IDF offline.")
    return TfidfEmbedder()


@dataclass
class Retrieved:
    chunk: Chunk
    score: float


class VectorStore:
    """numpy cosine store (com fallback) — espelha o papel do ChromaDB.
    O codigo ChromaDB equivalente esta em comentario no final do arquivo."""
    def __init__(self, embedder: BaseEmbedder):
        self.embedder = embedder
        self.chunks: List[Chunk] = []
        self.matrix = None
    def add(self, chunks: List[Chunk]):
        import numpy as np
        self.chunks = chunks
        self.embedder.fit([c.text for c in chunks])
        self.matrix = np.asarray(self.embedder.encode([c.text for c in chunks]))
    def query(self, question: str, n: int = 5) -> List[Retrieved]:
        import numpy as np
        q = np.asarray(self.embedder.encode([question]))[0]
        sims = self.matrix @ q  # vetores ja normalizados -> dot = cosseno
        order = np.argsort(-sims)[:n]
        return [Retrieved(self.chunks[i], float(sims[i])) for i in order]


# ----------------------------------------------------------------------------- #
# 3. MONTAGEM DE PROMPT
# ----------------------------------------------------------------------------- #

SYSTEM_PROMPT = """\
Você é o Assistente de Atendimento da NovaTech (logística). Seu único papel é responder
dúvidas operacionais dos ATENDENTES com base EXCLUSIVAMENTE nos trechos de documentação
fornecidos no bloco CONTEXTO. Você não tem conhecimento próprio sobre a NovaTech.

REGRAS (inquebráveis):
1. Use SOMENTE informação presente no CONTEXTO. Não complete lacunas com conhecimento geral.
2. Nunca invente prazos, valores, multiplicadores, tiers ou nomes de setor.
3. Se a informação não estiver no CONTEXTO, diga: "Não encontrei essa informação na
   documentação disponível." e sugira escalar ao supervisor. Não tente adivinhar.
4. Se o CONTEXTO só tiver PARTE do necessário (ex.: o multiplicador mas não a tarifa-base),
   responda o que há e declare explicitamente o que falta.
5. Prioridade entre fontes conflitantes: versão mais recente vence (compare as datas/versões
   no breadcrumb). Documento normativo/contratual > FAQ informal. Em conflito relevante,
   mostre ambas as versões com a data e sinalize.
6. Distinga REGRA de EXCEÇÃO: se algo é listado como exceção, não o apresente como permitido.
7. Toda afirmação deve citar a fonte no formato (DOC-ID vX, Seção N).
8. Responda em português formal, claro e objetivo.

FORMATO:
- Resposta direta (1-3 frases).
- Fonte(s) citada(s).
- Se aplicável: ressalva / o que falta / a quem escalar.
"""


def assemble_prompt(question: str, retrieved: List[Retrieved],
                    client_meta: Optional[str] = None) -> str:
    ctx_blocks = []
    for r in retrieved:
        ctx_blocks.append(f"--- Fonte: {r.chunk.doc_id} v{r.chunk.version} "
                          f"(Seção {r.chunk.section}; tipo={r.chunk.source_type}; "
                          f"data={r.chunk.doc_date}; score={r.score:.3f}) ---\n{r.chunk.text}")
    context = "\n\n".join(ctx_blocks)
    meta_line = f"\n[METADADOS DO CLIENTE]: {client_meta}\n" if client_meta else ""
    return (f"{SYSTEM_PROMPT}\n{meta_line}\n[CONTEXTO — trechos recuperados]\n{context}\n\n"
            f"[PERGUNTA DO ATENDENTE]\n{question}\n\n[RESPOSTA]")


# ---- Equivalente ChromaDB (caminho de producao) -----------------------------
# import chromadb
# client = chromadb.PersistentClient(path="./chroma_db")
# col = client.get_or_create_collection("novatech", metadata={"hnsw:space": "cosine"})
# emb = SentenceTransformerEmbedder()
# col.add(ids=[c.chunk_id for c in chunks],
#         embeddings=emb.encode([c.text for c in chunks]).tolist(),
#         documents=[c.text for c in chunks],
#         metadatas=[{"doc_id": c.doc_id, "version": c.version, "section": c.section,
#                     "source_type": c.source_type, "date": c.doc_date} for c in chunks])
# res = col.query(query_embeddings=[emb.encode([question])[0].tolist()], n_results=5)
# ------------------------------------------------------------------------------
