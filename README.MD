# Fase 2 — Estruturação · Papel Desenvolvedor · NovaTech Assistant

Entregáveis do **Cenário 2 (Estruturação)** do programa AI First (DGS/DB1), papel
**Desenvolvedor**. O projeto NovaTech é um assistente de IA (RAG) para atendimento ao
cliente de uma transportadora. O Cenário 1 fez o entendimento e o protótipo; o Cenário 2
configura os padrões, artefatos e conexões que governam o desenvolvimento **antes** de
escrever código de produção.

> **Stack:** TypeScript (Azure Functions v4, strict), Zod, Vitest, pino. Nesta fase **não
> há remoto, Azure nem GitHub** — tudo roda local. Servers MCP são *reference servers*
> gratuitos.

## Os 3 exercícios

| # | Exercício | Entregável principal | Roda de verdade? |
|---|-----------|----------------------|------------------|
| 2.1 | **MCP servers** — configurar e usar de verdade | `.mcp/mcp.json` + evidência de execução + análise de riscos | Sim — 4 servers executados (log JSON-RPC) |
| 2.2 | **SDD** — plan → tasks → primeira task | `tasks.md` (8 tasks) + código da T-01 + revisão crítica | Sim — `tsc` strict + 11 testes Vitest verdes |
| 2.3 | **Skills** — estratégia + skill completa | Árvore Foundation→Domain→Artifact + `azure-functions-endpoint` | n/a (artefato de doc) |

### 2.1 — MCP servers
Quatro servers locais com **least privilege concreto**: `filesystem-rw` (código/specs/skills),
`filesystem-ro` (docs+corpus de negócio), `git` (histórico), `memory` (linguagem ubíqua). O
escopo se prova na evidência (ler fora do escopo → `Access denied`) e a análise de risco é
**demonstrada**, não teórica (o reference server não tem read-only nativo — provado com um
`write_file` que passou; mitigação por permissão de SO).

### 2.2 — Spec Driven Development
`plan.md` do query endpoint decomposto em 8 tasks atômicas. A **T-01** (contrato de I/O +
validação Zod) foi implementada e **testada de verdade**: 11 testes Vitest, 100% de
cobertura no validator e nos errors, `tsc` strict sem erro. A revisão crítica aponta 3
pontos reais (ex.: conflito `strict()` vs "strip" no critério de aceite).

### 2.3 — Estratégia de skills
Árvore nas 3 camadas com papéis (quem cria/consome/frequência), a `SKILL.md` completa da
`azure-functions-endpoint` (exemplos DO/DON'T tirados do código real da T-01) e 8 critérios
de "skill madura" — sendo o gargalo o critério de uso real por um agente.

## Estrutura

```
dgs-ai-first/
├── 01-entregaveis/                 # os 3 documentos de entrega (numerados)
│   ├── 01_ex-2.1_mcp-servers.md
│   ├── 02_ex-2.2_query-endpoint-sdd.md
│   └── 03_ex-2.3_estrategia-skills.md
├── 02-evidencias/                  # capturas de execução real
│   ├── ex-2.1_mcp-evidence.log     # respostas JSON-RPC cruas dos 4 servers
│   ├── ex-2.1_mcp_probe.py         # cliente MCP usado (reproduzível)
│   └── ex-2.2_t01-evidence.log     # tsc + vitest da T-01
├── 03-repo-novatech-assistant/     # starter repo (Anexo D) MODIFICADO
│   ├── .mcp/mcp.json               # ← 2.1
│   ├── specs/query-endpoint/       # plan.md + tasks.md ← 2.2
│   ├── src/functions/query/validator.ts, src/shared/errors.ts  # ← 2.2 (T-01)
│   ├── tests/unit/query-validator.test.ts                      # ← 2.2
│   ├── skills/domain/azure-functions-endpoint.md               # ← 2.3
│   └── docs/{mcp,sdd,skills}/      # cópias dos entregáveis no contexto do repo
├── COMO-REPRODUZIR.md              # passo a passo para rodar tudo do zero
└── README.md
```

## Reproduzir

Ver `COMO-REPRODUZIR.md` para subir os MCP servers, rodar a evidência e executar os testes
da T-01. Resumo: `cd 03-repo-novatech-assistant && npm install && npx vitest run`.