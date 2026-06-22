# Exercício 2.2 — Implementação de spec com Spec Driven Development

**Papel:** Desenvolvedor · **Fase:** 2 (Estruturação) · **Módulo:** query-endpoint

Entrega os três itens pedidos: (1) `tasks.md` com tasks atômicas, (2) o código da primeira
task implementado (setup do endpoint com validação Zod), e (3) a revisão crítica do código.

> **Nota de honestidade (continuidade da auto-auditoria do Cenário 1):** o código abaixo
> foi **compilado em strict mode (`tsc` exit 0) e testado (`vitest`, 11/11 verdes)** neste
> ambiente — não é pseudocódigo. As capturas estão em `docs/sdd/ex-2.2-t01-evidence.log`.
> O código foi escrito com assistência do Claude (não do GitHub Copilot), como no Cenário 1.

---

## 1. Decomposição em tasks atômicas

O `plan.md` (Tech Lead) tem um fluxo de 5 passos. A decomposição completa está em
`specs/query-endpoint/tasks.md` — 8 tasks (T-01 a T-08), cada uma com ID, descrição,
escopo, critérios de aceite verificáveis, dependências e estimativa P/M/G.

Critério de corte usado: **cada task é uma fronteira testável isolada** (com mock próprio,
sem serviço Azure real nos testes unitários — convenção do projeto). Por isso "buscar
chunks", "montar prompt" e "chamar GPT-4o" viram tasks separadas: cada uma tem um ponto de
mock distinto e um conjunto de critérios próprio.

A **T-01** foi escolhida como primeira por ser a única sem dependência de serviço externo:
define o contrato de I/O e a validação da borda do endpoint, que é a fundação sobre a qual
as outras 7 se apoiam.

---

## 2. Código da primeira task (T-01) — implementado e testado

Arquivos produzidos:

- `src/functions/query/validator.ts` — schema Zod do request + `validateQueryInput()`.
- `src/shared/errors.ts` — `AppError` (base) + `ValidationError` (statusCode 400, issues).
- `tests/unit/query-validator.test.ts` — 11 testes Vitest cobrindo os 6 critérios de aceite.

**Decisões de implementação amarradas ao contexto:**

- `MAX_HISTORY_TURNS = 3` deriva diretamente da **ADR-0002** (histórico limitado a 3 turnos
  por query). O limite não é arbitrário — está citado no código e no teste.
- `.strict()` no schema rejeita campos desconhecidos, impedindo que input não declarado
  (ex.: `isAdmin: true`) entre no pipeline. (Ver ressalva na revisão, ponto B.)
- `validateQueryInput` é uma **função pura**, sem acoplamento ao HTTP trigger nem a serviços
  Azure, exatamente para ser testável sem rede — o que permitiu rodar os testes de verdade.
- `ValidationError` carrega `issues: string[]` legíveis, para o handler (T-08) devolver um
  400 útil ao cliente.

**Evidência de execução (resumo):**

```
tsc -p . --noEmit   -> exit 0 (strict mode, sem erros)
vitest run          -> 11 passed (11)
cobertura           -> validator.ts 100% | errors.ts 100%
```

---

## 3. Revisão crítica — pontos a ajustar antes de um code review real

Pontos reais identificados durante a implementação (não cosméticos):

### A. Conflito entre o critério de aceite 5 ("strip") e a implementação (`.strict()` rejeita)

O critério 5 do `tasks.md` diz **"strip de campos desconhecidos"**, mas a implementação usa
`.strict()`, que **rejeita** o request inteiro quando há chave desconhecida (lança
`ValidationError`), em vez de silenciosamente removê-la (`.strip()`). São políticas de
segurança diferentes: *fail-closed* (rejeitar) vs *tolerante* (limpar e seguir). O teste foi
escrito coerente com `.strict()`, mas **isso significa que o teste valida a implementação,
não o critério original** — o tipo de divergência que passa despercebido e depois vira bug
de contrato. Antes do merge é preciso uma decisão consciente do Tech Lead: para um endpoint
público de atendimento, *fail-closed* é defensável (não aceitar input ambíguo), mas então o
**critério de aceite no `tasks.md` deve ser corrigido** para dizer "rejeita campos
desconhecidos", não "strip". Não dá para deixar os dois textos se contradizendo.

### B. Estimativa de tokens ausente — o limite de 2000 chars é um proxy frágil para o budget

A T-01 limita `question` a 2000 caracteres, mas a ADR-0002 raciocina em **tokens**, não em
caracteres. 2000 chars de português podem dar ~500–700 tokens, mas o número real depende do
tokenizer do GPT-4o. O limite de caracteres serve como guarda-corpo contra abuso, porém
**não é a mesma coisa que respeitar o context budget** — e o `tasks.md` lista o controle de
budget só na T-05 (prompt builder). Risco: alguém ler "validação de input feita" e assumir
que o budget está protegido na borda, o que não é verdade. Antes do code review, deixar
explícito no código/doc que o controle de tokens é responsabilidade da T-05, e considerar se
o `history` (que também consome budget) precisa de um limite de tamanho por turno mais
rígido — hoje cada `answer` no histórico não tem teto de comprimento.

### C. (menor) `ValidationError` ainda é local da T-01 e será reconciliada na T-03

A T-03 vai definir a família completa de erros. Hoje `errors.ts` só tem `ValidationError`.
Quando T-03 entrar, é preciso garantir que não haja duplicação nem mudança de assinatura
que quebre o `validator.ts` — registrar isso como dependência explícita evita retrabalho.

---

## Arquivos desta entrega

- `specs/query-endpoint/plan.md` — plan do Tech Lead (versionado).
- `specs/query-endpoint/tasks.md` — decomposição SDD em 8 tasks atômicas.
- `src/functions/query/validator.ts` — implementação da T-01.
- `src/shared/errors.ts` — `ValidationError`.
- `tests/unit/query-validator.test.ts` — suíte Vitest (11 testes).
- `docs/sdd/ex-2.2-t01-evidence.log` — captura de `tsc` + `vitest`.
- `docs/sdd/ex-2.2-query-endpoint.md` — este documento.
