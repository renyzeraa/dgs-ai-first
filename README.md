# Fase 1 — Papel Desenvolvedor · Cenário NovaTech

Este repositório contém a resolução dos 3 exercícios do papel **Desenvolvedor** da Fase 1
da trilha **AI First** (DGS / DB1).

O cenário é a **NovaTech**, uma transportadora que quer um assistente de IA capaz de
responder perguntas dos atendentes usando a própria documentação interna da empresa.

---

## O que tem aqui

```
├── 01-entregaveis/          # respostas dos 3 exercícios
│   ├── 01_analise_viabilidade_tecnica.md
│   ├── 02_system_prompt_e_testes.md
│   └── 03_pipeline_rag_resultados.md
│
├── 02-rag-poc/              # código que roda de verdade
│   ├── novatech_rag.py      # o pipeline de RAG (ingestão, busca, montagem de prompt)
│   ├── run_poc.py           # execução baseline
│   ├── run_poc_v2.py        # execução com correções
│   ├── docs/                # os 5 documentos da NovaTech (corpus)
│   └── outputs/             # resultados gerados
│
└── 03-referencia-cenario/   # enunciados e gabarito original
    ├── exercicio-fase-1-entendimento.md
    ├── anexo-a-documentacao-simulada-novatech.md
    └── anexo-b-chunks-referencia-rag.md
```

---

## Os 3 exercícios

**Ex 1.1 — Análise de viabilidade**
Avalia se vale a pena construir o assistente. Estima quantos tokens os documentos ocupam,
qual o tamanho de janela de contexto necessário, quais os riscos e o que precisaria ser
confirmado antes de começar.

**Ex 1.2 — System prompt**
Escreve e testa o prompt que instrui o assistente de como responder. Cobre casos de
borda: o que fazer quando a informação não está nos docs, quando há duas versões
contraditórias, quando a pergunta mistura assuntos.

**Ex 1.3 — Pipeline de RAG**
Constrói e mede um pipeline que busca os trechos certos nos documentos antes de montar
a resposta. Os resultados são medidos contra um gabarito (Anexo B) que diz qual trecho
deveria ter sido encontrado para cada pergunta.

---

## Como rodar

```bash
cd 02-rag-poc

# instala as dependências
pip install -r requirements.txt

# baseline: como estava antes das correções
python run_poc.py

# versão corrigida
python run_poc_v2.py
```

Se o `sentence-transformers` não estiver disponível, o pipeline cai automaticamente para
um backend TF-IDF (mais simples, funciona offline). A saída informa qual backend foi usado.

---

## Resultados

O gabarito tem 9 perguntas com resposta esperada (a 10ª não tem cobertura nos documentos
— é uma armadilha para testar se o assistente inventa ou admite que não sabe).

| Versão | Perguntas com tudo certo |
|---|---|
| Baseline (`run_poc.py`) | 3/9 |
| Com correções (`run_poc_v2.py`) | 3/9 |

O número ficou igual, mas a composição mudou:

- **Q3 (SLA Gold): MISS → HIT** — a tabela de SLA não era recuperada porque as células
  não repetiam os termos da pergunta. A correção foi linearizar a tabela na ingestão
  (transformar cada linha em texto corrido).

- **Q8 (carga perigosa + expresso): HIT → MISS** — a penalidade aplicada a fontes
  informais (FAQ) foi longe demais: derrubou o único documento que cobria o assunto.
  O problema está documentado como P7 e tem correção proposta.

- **Q4 (SLA Platinum): era falso positivo** — o baseline contava como acerto porque
  o chunk aparecia na lista de candidatos, mas com score abaixo do limiar mínimo de
  relevância. Corrigido.

Os problemas que ficaram abertos (vocabulário diferente do usuário vs. documento,
perguntas sobre múltiplos assuntos de uma vez) estão mapeados no entregável 1.3 com
as correções necessárias — nenhuma delas é "trocar de modelo".
