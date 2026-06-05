# Fase 1 — Papel Desenvolvedor · Cenário NovaTech

Resolução completa dos **3 exercícios do papel Desenvolvedor** da Fase 1 da trilha
**AI First** (DGS / DB1), ancorados no cenário **NovaTech** — uma transportadora que
quer um assistente de IA de atendimento alimentado pela própria documentação interna.

O pacote aplica os quatro tópicos da fase: **Fundamentos de IA Generativa**,
**Engenharia de Prompt**, **Engenharia de Contexto** e **RAG / MCP**. O destaque é que
o pipeline de RAG do Exercício 1.3 **roda de verdade** — não é pseudocódigo.

---

## Estrutura das pastas

```
fase-1-desenvolvedor-novatech/
│
├── README.md                          # este arquivo (visão geral + como rodar)
│
├── 01-entregaveis/                    # as RESPOSTAS dos 3 exercícios
│   ├── 01_analise_viabilidade_tecnica.md   # Ex 1.1
│   ├── 02_system_prompt_e_testes.md        # Ex 1.2
│   └── 03_pipeline_rag_resultados.md       # Ex 1.3 (resultados + análise)
│
├── 02-rag-poc/                        # o CÓDIGO da PoC de RAG (Ex 1.3)
│   ├── novatech_rag.py                # módulo do pipeline (ingestão→busca→montagem)
│   ├── run_poc.py                     # runner baseline (avalia vs gabarito)
│   ├── run_poc_v2.py                  # runner com as correções aplicadas
│   ├── requirements.txt               # dependências (backend real + fallback)
│   ├── docs/                          # corpus indexado (os 5 documentos da NovaTech)
│   └── outputs/                       # artefatos gerados pela execução
│       ├── resultados_retrieval.json
│       └── prompt_montado_exemplo_q5.txt
│
└── 03-referencia-cenario/             # material original (para reproduzir / auditar)
    ├── exercicio-fase-1-entendimento.md     # enunciado dos exercícios
    ├── anexo-a-documentacao-simulada-novatech.md
    └── anexo-b-chunks-referencia-rag.md     # gabarito: pergunta → chunks esperados
```

A numeração `01-`, `02-`, `03-` é só para a leitura cair na ordem certa: **leia os
entregáveis, rode o código, confira contra a referência**.

---

## O que cada exercício entrega

| Ex | Arquivo | Tópicos | Em uma frase |
|----|---------|---------|--------------|
| **1.1** | `01_analise_viabilidade_tecnica.md` | Fundamentos + Eng. de Contexto | Veredito de viabilidade: o gargalo não é o LLM, é o tratamento dos dados. Estimativa de tokens, orçamento de contexto, riscos e perguntas ao Tech Lead. |
| **1.2** | `02_system_prompt_e_testes.md` | Eng. de Prompt + Eng. de Contexto | System prompt versionado (v1→v2), com anatomia estático/dinâmico, testado contra casos conhecidos. Prompt tratado como **código**. |
| **1.3** | `03_pipeline_rag_resultados.md` + pasta `02-rag-poc/` | RAG / MCP | Pipeline de RAG funcional medido contra o gabarito do Anexo B: **3/9 → 5/9** após correções. |

---

## Como rodar a PoC de RAG (Exercício 1.3)

### Pré-requisitos
- Python 3.10+
- As dependências de `02-rag-poc/requirements.txt`

### Passo a passo
```bash
cd 02-rag-poc

# (opcional, recomendado) ambiente isolado
python3 -m venv .venv && source .venv/bin/activate

# instala o backend real + o fallback
pip install -r requirements.txt

# 1) baseline: indexa o corpus e avalia o retrieval contra o gabarito
python3 run_poc.py

# 2) versão com correções (linearização de tabela + re-ranking de versão/autoridade)
python3 run_poc_v2.py
```

Cada runner imprime, para as 10 perguntas de teste, **quais chunks foram recuperados**
e se batem com o esperado pelo Anexo B (HIT / MISS / parcial), além de gravar o
detalhamento em `outputs/resultados_retrieval.json`.

### Dois backends — escolha automática
O pipeline detecta o que está instalado e informa qual backend usou:

- **REAL** — `sentence-transformers` (embeddings semânticos `all-MiniLM-L6-v2`) +
  `ChromaDB`. É o que rodaria em produção.
- **FALLBACK** — `TF-IDF` (scikit-learn) + cosseno em `numpy`. Roda **offline**, sem
  baixar modelo. Foi o backend usado na execução registrada nos entregáveis, por
  restrição de rede/espaço típica de uma PoC.

> A **mecânica** do RAG (chunk → embed → store → retrieve → assemble) é idêntica nos
> dois. O que muda é a **qualidade** do retrieval em casos de vocabulário diferente
> (ex.: "Manaus" vs "região Norte"), onde o embedder semântico ganha do TF-IDF. Isso
> está documentado como problema P5 no entregável 1.3.

---

## Como o pipeline funciona (resumo)

Três etapas, todas em `novatech_rag.py`:

1. **Ingestão** — lê os `.md`, faz **chunking *section-aware*** (cada seção é um chunk,
   tabelas nunca são quebradas, ~12% de overlap) e anexa metadados a cada chunk:
   `doc_id`, `versão`, `data`, `seção`, `tipo de fonte` e um *breadcrumb* de contexto
   tipo `[DOC vX | Seção N]`. O `DOC_REGISTRY` resolve a ambiguidade do PROC-042 v1 vs v2.

2. **Busca** — gera o embedding da pergunta e retorna os top-N chunks por similaridade
   de cosseno. A v2 adiciona **re-ranking**: "versão mais recente vence" (descarta o
   PROC-042 v1 quando existe o v2) e rebaixa fontes informais (FAQ) quando há fonte
   formal cobrindo o mesmo assunto.

3. **Montagem** — concatena o **system prompt** (com 8 regras inquebráveis — não
   inferir geografia, distinguir regra de exceção, respeitar versão mais recente,
   admitir quando não há cobertura, etc.), os chunks recuperados e a pergunta.

Detalhes, tabelas de resultado e a análise dos 7 problemas encontrados estão em
`01-entregaveis/03_pipeline_rag_resultados.md`.

---

## Resultados em uma olhada

| | Cobertura completa (10 perguntas) | Principais correções |
|---|---|---|
| **Baseline** (`run_poc.py`) | **3/9** | — |
| **Com correções** (`run_poc_v2.py`) | **5/9** | Linearizar tabela → SLA Gold MISS→HIT · Re-rank de autoridade → Platinum MISS→HIT · "versão mais recente vence" → multiplicador correto no topo |

Os problemas restantes (vocabulário usuário≠documento, perguntas multi-domínio,
guardrail de geração) estão mapeados com a correção proposta no entregável 1.3 — e
nenhuma delas é "trocar de modelo": são engenharia de dados e de contexto.

---

## Onde cada tópico da trilha aparece

- **Fundamentos de IA Generativa** — estimativa de tokens (~0,75 palavra/token),
  limites de janela de contexto, alucinação vs. recusa honesta → Ex 1.1 e 1.3.
- **Engenharia de Prompt** — system prompt versionado e testado contra casos de
  falha conhecidos → Ex 1.2.
- **Engenharia de Contexto** — orçamento de contexto ("128K é teto, não meta";
  usar 5–10 chunks), chunking *section-aware*, metadados → Ex 1.1, 1.2 e 1.3.
- **RAG / MCP** — pipeline funcional ingestão→busca→montagem; quando RAG resolve e
  quando um conector MCP seria melhor → Ex 1.3 (e seção MCP no Ex 1.1).

---

## Notas de honestidade técnica

- A execução registrada usou o **backend fallback (TF-IDF)** por restrição de
  ambiente. O código de produção (`sentence-transformers` + ChromaDB) está pronto e
  é selecionado automaticamente quando as dependências existem.
- O corpus em `02-rag-poc/docs/` é **simulado** (Anexo A): contém contradições
  propositais (PROC-042 v1 vs v2), uma exceção escondida (carga perigosa na POL-001
  §3.2) e uma armadilha de alucinação (cliente "Platinum" não existe). São esses
  casos que o gabarito do Anexo B cobra.
- O Claude foi usado como **par de revisão** — não só gerador. A crítica dirigida aos
  primeiros rascunhos (prompt e análise) é o que elevou o material; isso está
  registrado nos históricos de iteração dos entregáveis 1.1 e 1.2.
