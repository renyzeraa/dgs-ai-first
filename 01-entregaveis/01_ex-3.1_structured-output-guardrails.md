# Exercício 3.1 — Structured output e verificações determinísticas (harness de código)

**Papel:** Desenvolvedor · **Fase:** 3 (Governança) · **Módulo:** `src/services/response-validator.ts`

Entrega: (1) o schema Zod do structured output, (2) o `response-validator.ts` com os 2
guardrails, e (3) o code review com problemas reais identificados e corrigidos.

---

## 1. Schema Zod do structured output

O modelo passa a responder em JSON `{ answer, source_document, confidence_score }`. O schema
usa `.strict()` para rejeitar campos extras (o modelo não pode contrabandear chaves).

```typescript
export const assistantResponseSchema = z
  .object({
    answer: z.string().trim().min(1, "answer não pode ser vazia"),
    source_document: z.string().trim().min(1, "source_document é obrigatório").nullable(),
    confidence_score: z.number().min(0).max(1),
  })
  .strict();
```

`source_document` é `nullable` no schema (o modelo *pode* emitir `null`), mas o **guardrail 1**
rejeita `null`/vazio na resposta final — a distinção é proposital: o schema descreve o que o
modelo pode emitir; o guardrail decide o que é aceitável para o atendente.

## 2. `response-validator.ts` — os 2 guardrails (bloqueiam, não só logam)

A função `validateAssistantResponse(raw)` aplica três camadas e, em qualquer falha, **loga o
motivo e retorna uma resposta de fallback segura** (`ok: false` + `SAFE_FALLBACK_ANSWER` com
`confidence_score: 0`):

1. **Schema** — se o JSON não bate, rejeita antes de checar conteúdo.
2. **Guardrail 1 — `source_document` obrigatório** — `null` ou vazio → bloqueado.
3. **Guardrail 2 — carga perigosa + devolução** — se a resposta trata de devolução de carga
   perigosa e **não** contém a negativa exigida (POL-001 §3.2), é bloqueada.

A diferença entre `ok: false` (bloqueado) e só logar é o ponto central: o retorno troca a
resposta pelo fallback, então a resposta inválida **não segue** para o atendente.

### Prompt (probabilístico) vs código (determinístico)

O prompt *pede* JSON e *pede* citar a fonte — mas é probabilístico: o modelo pode esquecer. O
`response-validator` é determinístico: a mesma entrada sempre produz o mesmo veredito, sem
depender do modelo. O prompt reduz a probabilidade do erro; o código garante que, quando o
erro acontece, ele não passa. São camadas complementares, não substitutas.

## 3. Code review — problemas reais encontrados e corrigidos

> Estrutura de dupla revisão: a coluna "Revisor (pessoa)" e a coluna "Claude" foram
> produzidas de forma independente e depois reconciliadas.

### Problema #1 — Schema sem `.strict()` aceitaria campos extras (encontrado por ambos)

**Revisor (pessoa):** "A primeira versão do schema usava só `z.object({...})`. Isso aceita
silenciosamente qualquer chave extra que o modelo inventar (ex.: um `override: true`), o que
derrota o propósito do structured output."

**Claude:** "Concordo. `z.object` sem `.strict()` faz *strip* por padrão no parse, mas não
sinaliza a presença de campos não previstos. Para um harness de governança, o correto é
`.strict()` — falhar quando há chave desconhecida, não limpá-la em silêncio."

**Correção:** `.strict()` aplicado; teste `should reject unknown extra fields` cobre o caso.

### Problema #2 — Regex do guardrail 2 bloqueava a resposta CORRETA (falso positivo)

**Revisor (pessoa):** "O guardrail tinha um padrão `affirmsAllowed` que casava 'podem ser
devolvidas'. Mas a resposta correta — 'cargas perigosas **não podem ser devolvidas**' —
contém exatamente essa sequência. Resultado: a resposta certa era bloqueada como se fosse
violação. Peguei isso porque o teste `should ALLOW the correct dangerous-goods answer`
falhou."

**Claude:** "Esse é o erro mais perigoso dos dois, porque um guardrail que bloqueia a resposta
certa gera falsos negativos de produto — o atendente recebe o fallback genérico mesmo quando o
assistente acertou. A causa é ordem de avaliação: afirmação e negação foram testadas em
paralelo, sem prioridade. A negativa precisa ter precedência: se há negação ligada à
devolução, a resposta está correta, independentemente de conter as palavras 'podem devolver'."

**Correção:** a função passou a dar **prioridade à negativa** (`if (hasNegation) return false;`)
antes de qualquer regra de afirmação. Sem negativa, qualquer menção a devolução de carga
perigosa é bloqueada. Testes cobrem: inversão bloqueada, variação sem acento/caixa bloqueada,
resposta correta com negativa liberada, e devolução comum (sem carga perigosa) liberada.

### Observação adicional (risco residual, não corrigido)

O guardrail 2 é baseado em regex — robusto para as variações testadas, mas regex nunca cobre
toda a linguagem natural. Uma formulação muito atípica pode escapar. Mitigação aceita como
risco residual nesta fase: o guardrail 1 (fonte obrigatória) + a verificação de fonte do Tech
Lead (Ex 3.1 TL) + HITL para baixa confiança reduzem o impacto. Documentado para o backlog.

---

## Evidência de execução

```
tsc -p . --noEmit  -> exit 0 (strict)
vitest             -> 11 testes do response-validator passam (22 no total com a T-01)
logs do harness    -> motivos estruturados (schema_invalido, guardrail_source_document_ausente,
                      guardrail_carga_perigosa_devolucao) — sem dados sensíveis
```

Captura completa em `docs/harness/ex-3.1-evidence.log`.

## Arquivos

- `src/services/response-validator.ts` — schema + guardrails.
- `src/shared/logger.ts` — logger estruturado (pino com fallback).
- `tests/unit/response-validator.test.ts` — 11 testes.
- `docs/harness/ex-3.1-evidence.log` — captura tsc + vitest.
