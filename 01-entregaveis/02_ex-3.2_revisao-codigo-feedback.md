# Exercício 3.2 — Revisão crítica de código gerado por IA

**Papel:** Desenvolvedor · **Fase:** 3 (Governança) · **Módulo:** `src/functions/feedback/handler.ts`

Entrega: (1) revisão do código gerado pelo Copilot, (2) segunda revisão e comparação,
(3) o módulo reescrito seguindo o AGENTS.md.

---

## 1 e 2. Revisão dupla e comparação

Cada problema foi levantado de forma independente pelo revisor (pessoa) e pelo Claude; a
tabela reconcilia as duas listas. Classificação: **[AGENTS]** violação do AGENTS.md ·
**[SEC]** segurança · **[BUG]** bug potencial.

| # | Problema | Classe | Revisor (pessoa) | Claude | Convergência |
|---|----------|--------|:----------------:|:------:|--------------|
| 1 | `await request.json() as any` — sem validação, sem tipo | [AGENTS] + [BUG] | ✓ | ✓ | Ambos |
| 2 | `console.log('Feedback recebido', ...)` em vez de pino | [AGENTS] | ✓ | ✓ | Ambos |
| 3 | `attendantEmail` (dado pessoal) é logado dentro do objeto | [SEC] | ✓ | ✓ | Ambos |
| 4 | `require('@azure/cosmos')` dinâmico no meio da função | [AGENTS] | ✓ | ✓ | Ambos |
| 5 | Sem tratamento de erro: se o Cosmos falhar, exceção vaza como 500 não tratado | [BUG] | ✓ | ✓ | Ambos |
| 6 | `CosmosClient` instanciado a cada request (custo/conexão) | [BUG] | parcial | ✓ | Claude detalhou |
| 7 | Retorna `body: 'OK'` (texto) em vez de JSON, e status 200 em vez de 201 (criação) | [BUG] | — | ✓ | Só Claude |
| 8 | Acoplamento ao Cosmos impede teste sem serviço real | [BUG] | ✓ | parcial | Pessoa enfatizou |

## 3. Módulo reescrito (segue o AGENTS.md)

Decisões da reescrita, mapeadas aos problemas:

- **#1 →** validação com Zod em `feedback/validator.ts` (`validateFeedbackInput`), sem `as any`.
- **#2 →** `logger` estruturado (pino), nunca `console.log`.
- **#3 →** o e-mail do atendente **nunca** é escrito em log: o log de sucesso emite só
  `queryId`, `rating` e `id`; o de rejeição emite só os `issues`. (Teste dedicado garante que
  a string do e-mail não aparece em nenhuma saída de log.)
- **#4 →** imports estáticos no topo; nenhum `require` dinâmico.
- **#5 / #8 →** persistência atrás de uma porta `FeedbackRepository` injetada; o núcleo
  `handleFeedback(rawBody, repo)` é uma função pura testável sem Azure/Cosmos, com try/catch
  que retorna 503 em falha de persistência.
- **#6 / #7 →** o wire-up Azure (em `azure-wireup.ts.txt`, mantido como referência por depender
  de pacotes não instalados nesta fase) cria o cliente Cosmos **uma vez** fora do handler e
  retorna `jsonBody` com status 201.

### Evidência de execução

```
tsc -p . --noEmit  -> exit 0 (strict)
vitest             -> 4 testes do feedback handler passam (26 no total)
log de sucesso     -> {"level":"info","queryId":"...","rating":5,"id":"abc-123"}  (sem e-mail)
```

O teste `should NEVER write the attendant email to logs` captura `process.stderr.write` e
falha se a string do e-mail aparecer — é a verificação determinística do problema #3.
Captura completa em `docs/harness/ex-3.2-evidence.log`.

## Arquivos

- `src/functions/feedback/handler.ts` — handler reescrito (núcleo puro + porta injetada).
- `src/functions/feedback/validator.ts` — validação Zod do feedback.
- `src/functions/feedback/azure-wireup.ts.txt` — wire-up Azure de referência (renomear p/ .ts
  quando `@azure/functions` e `@azure/cosmos` estiverem instalados).
- `tests/unit/feedback-handler.test.ts` — 4 testes, incluindo o de não-vazamento de PII.
- `docs/harness/ex-3.2-evidence.log` — captura tsc + vitest.
