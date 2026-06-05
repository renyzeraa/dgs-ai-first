"""
run_poc.py — executa o pipeline e avalia o retrieval contra o gabarito do Anexo B.
Uso: python3 run_poc.py
"""
import json
from novatech_rag import ingest, make_embedder, VectorStore, assemble_prompt

# Gabarito do Anexo B expresso como (doc_id, secao) que DEVEM ser recuperados.
# secao "*" = qualquer secao do doc; None = nenhum chunk deve ser relevante (pergunta sem cobertura).
GOLD = [
    {"q": "Qual o prazo de devolução?",
     "expect": [("POL-001", "3.1"), ("POL-001", "3.2")], "trap": None},
    {"q": "Posso devolver carga perigosa?",
     "expect": [("POL-001", "3.2")], "trap": "regra vs excecao (NAO pode)"},
    {"q": "Qual o SLA do cliente Gold?",
     "expect": [("SLA-2024", "2")], "trap": None},
    {"q": "Qual o SLA do cliente Platinum?",
     "expect": [("SLA-2024", "1")], "trap": "tier inexistente (alucinacao)"},
    {"q": "Quanto custa o frete para 600kg para Manaus?",
     "expect": [("PROC-042-v2", "2.1"), ("PROC-042-v2", "2")],
     "trap": "v1 vs v2 (contradicao) + tarifa-base ausente"},
    {"q": "Quanto custa o frete para 300kg para Salvador?",
     "expect": None, "trap": "sem cobertura (<500kg nao documentado)"},
    {"q": "O que acontece com carga danificada em trânsito?",
     "expect": [("FAQ", "Item 38")], "trap": "fonte so no FAQ informal"},
    {"q": "Posso enviar carga perigosa com frete expresso?",
     "expect": [("FAQ", "Item 32")], "trap": "fonte so no FAQ informal"},
    {"q": "Qual o multiplicador de frete para o Sudeste?",
     "expect": [("PROC-042-v2", "2.1")], "trap": "v1 (1.0) vs v2 (1.1) contradicao"},
    {"q": "Qual o prazo de devolução, posso devolver carga perigosa e quanto custa frete pesado?",
     "expect": [("POL-001", "3.1"), ("POL-001", "3.2"),
                ("PROC-042-v2", "2"), ("PROC-042-v2", "2.1")], "trap": "multi-dominio"},
]

N = 5  # chunks recuperados por pergunta (orcamento de contexto enxuto)


def sec_match(chunk, doc_id, sec):
    if chunk.doc_id != doc_id:
        return False
    return sec == "*" or chunk.section == sec or chunk.section.startswith(sec)


def main():
    print("=" * 78)
    print("INGESTAO")
    chunks = ingest("docs/*.md")
    by_doc = {}
    for c in chunks:
        by_doc.setdefault(c.doc_id, []).append(c)
    for d, cs in by_doc.items():
        toks = sum(c.approx_tokens for c in cs)
        print(f"  {d:<12} {len(cs):>2} chunks | ~{toks:>4} tokens | "
              f"secoes: {', '.join(c.section for c in cs)}")
    total_tok = sum(c.approx_tokens for c in chunks)
    print(f"  TOTAL: {len(chunks)} chunks, ~{total_tok} tokens, "
          f"media ~{total_tok//len(chunks)} tok/chunk")

    print("=" * 78)
    embedder = make_embedder(prefer_real=True)
    print(f"BACKEND DE EMBEDDING: {embedder.name}")
    store = VectorStore(embedder)
    store.add(chunks)

    print("=" * 78)
    print(f"RETRIEVAL — {len(GOLD)} perguntas (top-{N}) vs gabarito Anexo B\n")
    results = []
    hits = 0
    for i, case in enumerate(GOLD, 1):
        retrieved = store.query(case["q"], n=N)
        got = [(r.chunk.doc_id, r.chunk.section, round(r.score, 3)) for r in retrieved]

        if case["expect"] is None:
            # sucesso = nenhum chunk com score alto deveria virar "resposta confiante"
            top_score = retrieved[0].score
            status = "OK (esperado: SEM cobertura)"
            covered = "n/a"
        else:
            found = []
            for (d, s) in case["expect"]:
                ok = any(sec_match(r.chunk, d, s) for r in retrieved)
                found.append(((d, s), ok))
            n_ok = sum(1 for _, ok in found if ok)
            covered = f"{n_ok}/{len(case['expect'])}"
            full = n_ok == len(case["expect"])
            hits += 1 if full else 0
            status = "HIT" if full else ("PARCIAL" if n_ok else "MISS")

        print(f"[{i:>2}] {case['q']}")
        print(f"     status={status}  cobertura={covered}  armadilha={case['trap']}")
        for r in retrieved:
            flag = ""
            if r.chunk.doc_id == "PROC-042":
                flag = "  <-- VERSAO ANTIGA (v1): risco de contradicao"
            if r.chunk.source_type == "informal":
                flag = "  <-- FONTE INFORMAL (FAQ nao validado)"
            print(f"        {r.score:.3f}  {r.chunk.doc_id} v{r.chunk.version} "
                  f"Sec {r.chunk.section} ({r.chunk.section_title}){flag}")
        print()
        results.append({"q": case["q"], "status": status, "covered": covered,
                        "trap": case["trap"], "retrieved": got})

    print("=" * 78)
    scored = [c for c in GOLD if c["expect"] is not None]
    print(f"RESUMO retrieval: {hits}/{len(scored)} perguntas com cobertura COMPLETA do gabarito")

    # exemplo de prompt montado para a pergunta 5 (a mais delicada)
    case5 = GOLD[4]
    prompt5 = assemble_prompt(case5["q"], store.query(case5["q"], n=N))
    with open("prompt_montado_exemplo_q5.txt", "w", encoding="utf-8") as f:
        f.write(prompt5)
    with open("resultados_retrieval.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("Artefatos: prompt_montado_exemplo_q5.txt, resultados_retrieval.json")


if __name__ == "__main__":
    main()
