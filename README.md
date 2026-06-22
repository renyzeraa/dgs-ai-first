# Fase 3 — Governança e Validação · Papel Desenvolvedor · NovaTech Assistant

Entregáveis do **Cenário 3 (Governança)** do AI First (DGS/DB1), papel **Desenvolvedor**.
Tópicos: **Harness Engineering** (structured outputs + verificações determinísticas) e
**Revisão Crítica de Outputs de IA**.

> **Stack:** TypeScript strict, Zod, Vitest, pino. Tudo local — sem Azure/GitHub nesta fase.

## Os 2 exercícios

| # | Exercício | Entregável principal | Roda de verdade? |
|---|-----------|----------------------|------------------|
| 3.1 | **Harness de código** — structured output + 2 guardrails | schema Zod + `response-validator.ts` + code review | Sim — `tsc` strict + 11 testes |
| 3.2 | **Revisão de código de IA** — feedback handler | revisão dupla + handler reescrito segundo AGENTS.md | Sim — `tsc` strict + 4 testes |

Suíte completa: **26 testes verdes**, cobertura ~97% nos módulos implementados.

### 3.1 — Structured output e guardrails determinísticos
`src/services/response-validator.ts`: schema Zod `{ answer, source_document, confidence_score }`
com `.strict()`, mais 2 guardrails que **bloqueiam** (trocam por fallback seguro, não só
logam): (1) `source_document` obrigatório; (2) devolução de carga perigosa sem a negativa
exigida (POL-001 §3.2). O code review pegou 2 problemas reais — schema sem `.strict()` e um
falso positivo no regex que bloqueava a resposta CORRETA — ambos corrigidos.

### 3.2 — Revisão crítica do feedback handler
Revisão dupla (pessoa + Claude) do handler gerado por IA, pegando os 4 problemas exigidos
(`as any` sem Zod, `console.log`, `require` dinâmico, e-mail logado) e mais alguns. Reescrito
em `src/functions/feedback/handler.ts` com Zod, pino, imports estáticos, persistência atrás de
porta injetável, e um teste que **garante que o e-mail do atendente nunca vai para o log**.

## Estrutura

```
fase-3-desenvolvedor-novatech/
├── 01-entregaveis/
│   ├── 01_ex-3.1_structured-output-guardrails.md
│   └── 02_ex-3.2_revisao-codigo-feedback.md
├── 02-evidencias/
│   ├── ex-3.1_evidence.log
│   └── ex-3.2_evidence.log
├── 03-repo-novatech-assistant/        # starter repo MODIFICADO (cenários 2 + 3)
│   ├── src/services/response-validator.ts   ← 3.1
│   ├── src/shared/logger.ts                 ← 3.1/3.2
│   ├── src/functions/feedback/              ← 3.2 (handler + validator + wireup ref)
│   └── tests/unit/                          ← suítes dos 2 exercícios
├── COMO-REPRODUZIR.md
└── README.md
```

## Reproduzir (resumo)

```bash
cd 03-repo-novatech-assistant
npm install
npx tsc -p . --noEmit      # exit 0
npx vitest run             # 26 passed (26)
```
Detalhes em `COMO-REPRODUZIR.md`.
