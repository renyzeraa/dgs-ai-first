# Tasks — Query Endpoint

> Derivado de `specs/query-endpoint/plan.md` (Tech Lead) seguindo Spec Driven Development.
> Cada task é atômica: entregável único, critérios de aceite verificáveis, dependências
> explícitas. Estimativa em P (<=2h) / M (meio dia) / G (>=1 dia).
>
> **Convenção de status:** `TODO` - `WIP` - `DONE` - `BLOCKED`.
> **Gate de implementação (validation gate 2):** o Tech Lead aprova este `tasks.md` antes
> de qualquer task sair de `TODO`. A task implementada neste exercício é a **T-01**.

---

## Visão geral da decomposição

O `plan.md` descreve um fluxo de 5 passos (receber -> embeddar -> buscar -> montar prompt
-> completar). Decompondo por **fronteira testável** (cada peça com mock próprio, sem
serviço Azure real nos testes unitários — convenção do projeto), chega-se a 8 tasks:

| ID | Título | Estima | Depende de |
|----|--------|--------|-----------|
| T-01 | Setup do endpoint: contrato de I/O + validação Zod | P | — |
| T-02 | Tipos de domínio compartilhados (`shared/types.ts`) | P | — |
| T-03 | Custom errors + logger pino | P | — |
| T-04 | Service de busca (top-5 chunks) com mock do Azure AI Search | M | T-02 |
| T-05 | Prompt builder com enforcement de context budget (ADR-0002) | M | T-02, T-04 |
| T-06 | Service de completion (GPT-4o) com retry/backoff | M | T-02, T-03 |
| T-07 | Response builder: resposta + `source_document` + caso "sem cobertura" | M | T-02, T-05 |
| T-08 | Wire-up do HTTP trigger Azure Functions v4 + testes de integração | G | T-01..T-07 |

> Observação de sequência: T-02 e T-03 são pré-requisitos transversais. T-01 foi mantida
> **independente de propósito** (não depende de T-02) para ser a primeira a implementar:
> ela define o contrato de entrada/saída e a validação, que é a fundação verificável do
> endpoint e não exige nenhum serviço externo.

---

## T-01 — Setup do endpoint: contrato de I/O + validação Zod  ·  `DONE`  ·  P

**Descrição.** Definir o contrato de request/response do `POST /api/query` e implementar a
validação determinística de input com Zod, isolada do HTTP trigger (função pura testável).
Sem chamadas Azure, sem montagem de prompt — só a borda de entrada do endpoint.

**Escopo (o que entra).**
- Schema Zod do request: `{ question: string (1..2000 chars, trim), conversationId?: uuid, history?: turno[] (máx 3 — ADR-0002) }`.
- Schema Zod da response (contrato público): `{ answer, sources[], coverage, conversationId? }`.
- Função `validateQueryInput(raw: unknown)` que retorna `QueryInput` válido ou lança `ValidationError`.

**Fora de escopo.** Embedding, busca, prompt, completion, wire-up do `app.http(...)`.

**Critérios de aceite (verificáveis por teste).**
1. `validateQueryInput` aceita request mínimo válido (`{ question: "Qual o SLA Gold?" }`) e retorna objeto tipado.
2. Rejeita `question` vazia, só espaços, ausente, ou > 2000 chars — com `ValidationError` e mensagem útil.
3. Rejeita `history` com mais de 3 turnos (limite da ADR-0002).
4. `conversationId`, se presente, precisa ser UUID válido; se ausente, passa.
5. Strip de campos desconhecidos (não propaga input não declarado).
6. Cobertura de teste da função >= 90% das linhas; testes seguem `describe('validateQueryInput') > it('should ... when ...')` com arrange/act/assert.

**Dependências.** Nenhuma (usa só Zod, já no `package.json`).

**Definition of Done.** `npm test` verde para a suíte de T-01; `tsc` sem erro em strict
mode; nenhum `console.log`; nenhum `any`.

---

## T-02 — Tipos de domínio compartilhados  ·  `TODO`  ·  P

**Descrição.** `shared/types.ts` com os tipos do domínio NovaTech: `Chunk` (id, docId,
version, section, text, vigência), `RetrievalResult`, `QueryInput`, `QueryResponse`,
`Source` (formato `DOC-ID vX, Seção N`, exigido pelo system prompt v2).

**Critérios de aceite.** Tipos exportados explicitamente; `Source` modela o formato de
citação do system prompt; `Chunk` carrega metadado de vigência (ADR-0003). Sem `any`.

**Depende de.** —

---

## T-03 — Custom errors + logger pino  ·  `TODO`  ·  P

**Descrição.** `shared/errors.ts` (`ValidationError`, `RetrievalError`, `CompletionError`,
`NoCoverageError`, com `statusCode`) e `shared/logger.ts` (instância pino, nível por env).
Convenção: nunca `console.log`.

**Critérios de aceite.** Cada erro tem `name`, `statusCode` e é `instanceof Error`; logger
exporta `info/warn/error`; teste confirma o statusCode de cada erro.

**Depende de.** —

---

## T-04 — Service de busca (top-5) com mock do Azure AI Search  ·  `TODO`  ·  M

**Descrição.** `services/search.ts`: dada a pergunta, retorna top-5 `Chunk`. Nos testes o
cliente do Azure AI Search é mockado (sem rede). Usa o corpus do Anexo B como fixture.

**Critérios de aceite.** "Qual o SLA do cliente Gold?" retorna `SLA-2024-B` no topo
(gabarito Anexo B); pergunta sem cobertura (frete < 500kg) retorna lista vazia/baixa
relevância sinalizada; teto de 5 resultados respeitado.

**Depende de.** T-02.

---

## T-05 — Prompt builder com context budget (ADR-0002)  ·  `TODO`  ·  M

**Descrição.** `services/prompt-builder.ts`: monta system prompt + chunks + histórico +
pergunta respeitando o orçamento (~4K system, ~8K chunks, histórico <= 3 turnos). Descarta
chunks excedentes preservando relevância e marca contradições de vigência (ADR-0003).

**Critérios de aceite.** Tokens dos chunks nunca excedem ~8K; system prompt carregado de
`/prompts/system-prompt.md`; com PROC-042 v1 e v2, a v2 é priorizada (ADR-0003); teste
cobre excedente de budget.

**Depende de.** T-02, T-04.

---

## T-06 — Service de completion (GPT-4o) com retry/backoff  ·  `TODO`  ·  M

**Descrição.** `services/completion.ts`: chama Azure OpenAI (GPT-4o) com retry e exponential
backoff. Cliente mockado nos testes.

**Critérios de aceite.** Retry em erro transitório (429/5xx) com backoff e teto de
tentativas; falha definitiva lança `CompletionError`; teste valida tentativas e backoff
(timers fake).

**Depende de.** T-02, T-03.

---

## T-07 — Response builder + caso "sem cobertura"  ·  `TODO`  ·  M

**Descrição.** `functions/query/response-builder.ts`: monta `QueryResponse` com `answer`,
`sources[]` (formato `DOC-ID vX, Seção N`) e `coverage`. Sem cobertura -> resposta padrão
"não encontrei na documentação" (regra 3 do system prompt; armadilha 5 do Anexo B).

**Critérios de aceite.** Resposta com conteúdo tem >= 1 source; pergunta sem cobertura
produz `coverage: "none"` e mensagem canônica, sem fonte fabricada; teste cobre os dois
caminhos.

**Depende de.** T-02, T-05.

---

## T-08 — Wire-up HTTP trigger v4 + testes de integração  ·  `TODO`  ·  G

**Descrição.** `functions/query/handler.ts`: registra `app.http('query', ...)` (Azure
Functions v4), orquestra validate -> search -> prompt -> completion -> response, com logging
pino e mapeamento de erro -> status HTTP. Testes de integração (msw) no fluxo feliz e de erro.

**Critérios de aceite.** POST válido -> 200 com `QueryResponse`; input inválido -> 400;
falha de completion -> 502/503; sem cobertura -> 200 com `coverage: "none"`. Requer
`@azure/functions` e `pino` adicionados ao `package.json`.

**Depende de.** T-01..T-07.
