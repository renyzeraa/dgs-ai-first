# Skill (Domain): azure-functions-endpoint

**Ativação:** Use esta skill ao criar ou revisar qualquer **HTTP endpoint** do NovaTech
Assistant (query, feedback, health). Cobre o padrão da borda HTTP: trigger Azure Functions
v4, validação Zod, logging pino e mapeamento de erro → status. **Não** cobre a lógica de
busca (ver `azure-ai-search-integration`) nem a montagem de prompt (ver a artifact
`create-rag-endpoint`).

**Nível:** Domain · **Dono:** Dev Sênior · **Status:** DRAFT (vira maduro após o critério 6
do doc de estratégia — uso por agente + iteração documentada).

---

## Contexto

O projeto tem 5 endpoints HTTP. Todos compartilham a mesma anatomia de borda: recebem JSON,
validam, delegam para services, e devolvem uma resposta tipada com tratamento de erro
consistente. Esta skill fixa esse esqueleto para que humanos e agentes produzam endpoints
uniformes — e para que o caso "input inválido" e o caso "falha de dependência" nunca sejam
improvisados.

Decisões herdadas (não negociáveis): TypeScript strict (ADR de stack), Zod em todo I/O,
pino para log, histórico de conversa limitado a 3 turnos e context budget da **ADR-0002**.

---

## Regras prescritivas

1. **Valide o input na borda, com Zod, antes de qualquer lógica.** A validação é uma função
   pura isolada do trigger (`validateXInput(raw: unknown)`), para ser testável sem HTTP.
2. **Use `.strict()` no schema do request** — rejeite campos desconhecidos (fail-closed). Um
   endpoint público de atendimento não aceita input ambíguo.
3. **Toda falha vira um custom error com `statusCode`.** Nunca devolva `throw new Error(...)`
   genérico para o cliente. Use `ValidationError` (400), `RetrievalError`/`CompletionError`
   (502/503), `NoCoverageError` (200 com coverage "none").
4. **Logue com pino, nunca `console.log`.** Log estruturado com nível por ambiente.
5. **Nunca use `any`.** Tipos vêm de `shared/types.ts`; o input validado é inferido do schema
   Zod (`z.infer`).
6. **O handler orquestra, não implementa.** Ele chama validate → service(s) → response
   builder. Lógica de negócio mora em `services/`, não no handler.
7. **Limites de budget são explícitos e citam a ADR.** Ex.: `MAX_HISTORY_TURNS = 3` com
   comentário apontando a ADR-0002. Constantes mágicas sem origem são proibidas.
8. **Caso "sem cobertura" é parte do contrato, não exceção esquecida.** Se a busca não cobre
   a pergunta, retorne a resposta canônica "não encontrei na documentação" — nunca invente
   (regra 3 do system prompt; armadilha 5 do Anexo B).

---

## Exemplos DO / DON'T (código real do projeto)

### DO — validação pura, Zod `.strict()`, limite citando a ADR

```typescript
// Extrato de src/functions/query/validator.ts (T-01). O arquivo completo compila em
// strict mode (tsc exit 0) e passa em 11 testes Vitest; este trecho é ilustrativo
// (historyTurnSchema é definido no arquivo original).
import { z } from "zod";
import { ValidationError } from "../../shared/errors.js";

export const MAX_HISTORY_TURNS = 3; // ADR-0002: histórico limitado a 3 turnos por query

export const queryInputSchema = z
  .object({
    question: z.string().trim().min(1, "question não pode ser vazia").max(2000),
    conversationId: z.string().uuid().optional(),
    history: z.array(historyTurnSchema).max(MAX_HISTORY_TURNS).optional(),
  })
  .strict(); // rejeita campos desconhecidos

export type QueryInput = z.infer<typeof queryInputSchema>;

export function validateQueryInput(raw: unknown): QueryInput {
  const result = queryInputSchema.safeParse(raw);
  if (!result.success) {
    const issues = result.error.issues.map((i) => `${i.path.join(".") || "(raiz)"}: ${i.message}`);
    throw new ValidationError("Input inválido para /api/query", issues);
  }
  return result.data;
}
```

### DON'T — validação manual, `any`, erro genérico

```typescript
// ❌ NÃO faça isto
export function handle(req: any) {              // any proibido
  if (!req.body.question) {                      // validação manual e frágil
    throw new Error("bad request");              // erro genérico, sem statusCode
  }
  console.log("got question", req.body.question);// console.log proibido (use pino)
  // ... lógica de busca direto no handler        // handler não deve implementar negócio
}
```

### DO — custom error com statusCode e issues legíveis

```typescript
// src/shared/errors.ts  (T-01)
export class ValidationError extends AppError {
  readonly statusCode = 400;
  readonly issues: readonly string[];
  constructor(message: string, issues: readonly string[] = []) {
    super(message);
    this.issues = issues;
  }
}
```

### DON'T — engolir o caso "sem cobertura"

```typescript
// ❌ NÃO faça isto: se não achou chunk, inventar resposta é alucinação
if (chunks.length === 0) {
  return { answer: model.guess(question) }; // viola regra 3 do system prompt
}
// ✅ correto: NoCoverageError -> resposta canônica com coverage "none"
```

---

## Anti-padrões comuns (neste contexto)

- **`console.log` "só para debugar"** que vaza para produção. → pino sempre.
- **`as any` para silenciar o compilador** ao tipar `req`. → tipar via `z.infer` e `shared/types.ts`.
- **Validação espalhada pelo handler** em vez de função pura. → quebra o teste sem HTTP.
- **Constante mágica de limite** (`> 3`, `> 2000`) sem citar a ADR de origem. → comentar a fonte.
- **Tratar "sem cobertura" como erro 500** em vez de resposta 200 com `coverage: "none"`.
- **Misturar multiplicador PROC-042 v1 e v2** por não priorizar a versão recente (ADR-0003) —
  responsabilidade da camada de busca/prompt, mas o endpoint não deve mascarar isso.

---

## Dependências

- **Foundation:** `typescript-conventions` (strict, sem any, ESM), `error-handling`
  (custom errors + pino + retry), `project-structure` (handler em `functions/`, lógica em
  `services/`).
- **Domain:** `azure-ai-search-integration` (a busca que o handler chama).
- **Testes:** `testing-patterns` + a artifact `create-integration-test` para o wire-up (T-08).

## Verificação rápida (checklist antes do PR)

- [ ] Input validado por função pura Zod `.strict()`, testável sem HTTP.
- [ ] Sem `any`, sem `console.log`, `tsc` strict limpo.
- [ ] Todo erro tem custom error com statusCode.
- [ ] Limites citam a ADR de origem.
- [ ] Caso "sem cobertura" tratado como contrato (coverage "none"), não como exceção.
