# Como reproduzir — Fase 3 Desenvolvedor

## Pré-requisitos
- Node.js 20+ (testado em 22) e npm

## Passos

```bash
cd 03-repo-novatech-assistant
npm install                 # zod (dependency), vitest, typescript, @types/node
npx tsc -p . --noEmit       # deve sair exit 0 (strict mode)
npx vitest run              # deve mostrar 26 passed (26)
npx vitest run --coverage   # response-validator 100%, feedback validator 100%, handler 92%
```

## O que cada teste prova

- `tests/unit/response-validator.test.ts` (11) — schema `.strict()` rejeita extras; os 2
  guardrails BLOQUEIAM (retornam fallback, não só logam); a resposta correta de carga
  perigosa (com a negativa) passa; variações sem acento/caixa são pegas.
- `tests/unit/feedback-handler.test.ts` (4) — valida com Zod (400 em input ruim, sem chamar
  o repo); persiste e retorna 201; 503 em falha; e o e-mail do atendente NUNCA aparece no log.
- `tests/unit/query-validator.test.ts` (11) — herdado do cenário 2.

## Sobre o wire-up Azure (3.2)

`src/functions/feedback/azure-wireup.ts.txt` é o registro `app.http(...)` + adapter Cosmos.
Está como `.txt` para não exigir `@azure/functions`/`@azure/cosmos` nesta fase. Para ativar:
instale as duas deps e renomeie para `azure-wireup.ts`.

## Colar na branch / subir

O repositório real é `03-repo-novatech-assistant`. As pastas `01-entregaveis` e
`02-evidencias` são organização da entrega.

```bash
cd 03-repo-novatech-assistant
git add src/services/response-validator.ts src/shared/logger.ts \
        src/functions/feedback/ tests/unit/response-validator.test.ts \
        tests/unit/feedback-handler.test.ts package.json tsconfig.json
git commit -m "feat(harness): structured output + guardrails; refactor(feedback): handler segue AGENTS.md"
```
