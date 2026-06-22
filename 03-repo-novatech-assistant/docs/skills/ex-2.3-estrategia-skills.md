# Exercício 2.3 — Estratégia de skills do projeto

**Papel:** Desenvolvedor · **Fase:** 2 (Estruturação) · **Projeto:** NovaTech Assistant

Entrega os três itens pedidos: (1) a árvore de skills com nome, descrição (frase-ativação),
quem cria, quem consome e frequência de uso; (2) a `SKILL.md` completa da
`azure-functions-endpoint` (Domain level) — em `skills/domain/azure-functions-endpoint.md`;
e (3) os critérios para "skill madura".

> **Nota de honestidade:** os exemplos DO/DON'T da skill `azure-functions-endpoint` foram
> derivados do **código real da T-01** (Ex 2.2), que compila em strict mode e passa nos 11
> testes Vitest. Não são trechos hipotéticos — saíram de `src/functions/query/validator.ts`
> e `src/shared/errors.ts`.

---

## 1. Árvore de skills

A hierarquia segue **Foundation → Domain → Artifact**: Foundation são regras transversais a
qualquer código do projeto; Domain são padrões de um tipo de componente; Artifact são
receitas completas que compõem várias skills para produzir um entregável de ponta a ponta.

### Foundation (regras transversais — todo agente consome sempre)

| Skill | Frase-ativação (descrição) | Quem cria | Quem consome | Frequência |
|-------|----------------------------|-----------|--------------|------------|
| `typescript-conventions` | "Ao escrever qualquer TypeScript: strict mode, sem `any`, exports explícitos, ESM." | Tech Lead | Todos os agentes/devs | Altíssima (toda task de código) |
| `error-handling` | "Ao tratar erros: custom errors com statusCode, logging com pino, retry com backoff em chamadas externas." | Dev Sênior | Todos os agentes/devs | Alta |
| `project-structure` | "Ao criar arquivos/módulos: onde cada coisa mora (functions/services/shared), nomenclatura de pastas, exports." | Tech Lead | Todos os agentes/devs | Alta |

### Domain (padrão por tipo de componente)

| Skill | Frase-ativação (descrição) | Quem cria | Quem consome | Frequência |
|-------|----------------------------|-----------|--------------|------------|
| `azure-functions-endpoint` | "Ao criar um HTTP endpoint: trigger Azure Functions v4, validação Zod na borda, logging pino, mapeamento erro→status." | Dev Sênior | Devs criando endpoints; agentes | Alta (5 endpoints no projeto) |
| `azure-ai-search-integration` | "Ao integrar com o índice de busca: cliente, top-k, mock nos testes, tratamento de índice vazio." | Dev Sênior | Devs do pipeline e do query | Média |
| `react-components` | "Ao criar componente React do painel: estrutura, tipagem de props, estado, acessibilidade." | Dev (frontend) | Devs do painel web | Média |
| `testing-patterns` | "Ao escrever testes: Vitest, `describe>it('should...when...')`, arrange/act/assert, mocks sem rede real." | QA | Todos os agentes/devs | Alta |

### Artifact (receita completa — compõe Foundation + Domain)

| Skill | Frase-ativação (descrição) | Quem cria | Quem consome | Frequência |
|-------|----------------------------|-----------|--------------|------------|
| `create-rag-endpoint` | "Para criar um endpoint RAG do zero: do contrato Zod ao retorno com source_document, ponta a ponta." | Tech Lead | Devs; agentes gerando endpoint completo | Baixa-Média (1x por endpoint novo) |
| `create-integration-test` | "Para criar um teste de integração de endpoint: msw, fluxo feliz + erros, sem serviço real." | QA | Devs; agentes | Média |
| `create-react-card` | "Para criar um Adaptive Card / card de resposta do painel ou Teams, coerente com o contrato de resposta." | Dev (frontend) | Devs do painel/bot | Baixa |

**Como as camadas se compõem (exemplo concreto):** a artifact `create-rag-endpoint` referencia
a domain `azure-functions-endpoint` (borda HTTP + Zod) + `azure-ai-search-integration`
(busca) + `testing-patterns` (testes), e todas herdam `typescript-conventions` e
`error-handling` da foundation. Uma artifact nunca repete regra de foundation: ela aponta
para a skill, não recopia.

### Quem cria vs quem consome — princípio

- **Foundation** é escrita por quem detém a autoridade técnica transversal (Tech Lead / Dev
  Sênior) e revisada cedo, porque um erro aqui se propaga para tudo.
- **Domain** é escrita por quem mais usa aquele tipo de componente.
- **Artifact** é escrita pelo Tech Lead (composição = decisão de arquitetura) e é a que mais
  muda quando o padrão evolui.
- **Agentes (Copilot/Claude) são sempre consumidores, nunca autores** de skill sem revisão
  humana — uma skill é contrato, e contrato não se gera sem gate (alinha com o validation
  gate 2 do Ex 2.1).

---

## 2. SKILL.md completa — `azure-functions-endpoint`

Ver `skills/domain/azure-functions-endpoint.md` (entregue preenchida). Resumo do que ela
contém: contexto/frase-ativação, regras prescritivas numeradas, exemplos DO/DON'T com código
real, anti-padrões comuns e dependências (aponta para foundation e para a domain de busca).

---

## 3. Critérios para "skill madura"

Uma skill só é considerada **madura** (pronta para uso pelo time e por agentes sem
supervisão extra) quando satisfaz todos os critérios abaixo. Antes disso, fica marcada como
`DRAFT` no topo do arquivo.

1. **Frase-ativação inequívoca.** Um agente lendo só a primeira linha sabe quando aplicar a
   skill e quando não — sem sobreposição confusa com outra skill.
2. **Regras prescritivas, não descritivas.** Diz o que fazer ("valide o input com Zod na
   borda"), não o que existe ("o projeto usa Zod"). Cada regra é verificável.
3. **Pelo menos um par DO/DON'T com código que compila.** O exemplo "certo" precisa ser
   código real do projeto que passa no `tsc` e nos testes — não pseudocódigo. O "errado"
   precisa ser um erro que de fato já aconteceu ou aconteceria.
4. **Anti-padrões nomeados.** Lista os erros mais prováveis daquele contexto (ex.: usar
   `console.log`, vazar `any`, esquecer o caso "sem cobertura").
5. **Dependências declaradas.** Aponta explicitamente para as skills de que depende, sem
   recopiar o conteúdo delas.
6. **Testada contra um agente real.** A skill foi usada por Copilot/Claude para gerar um
   artefato e o output seguiu as regras — com pelo menos uma rodada de iteração documentada
   (o que o agente ignorou virou regra mais prescritiva). Este é o critério que separa uma
   skill "escrita" de uma skill "que funciona".
7. **Revisada e aprovada pelo dono da camada.** Foundation/Artifact pelo Tech Lead; Domain
   pelo autor + 1 revisor. Aprovação registrada (commit/PR markdown).
8. **Consistente com o AGENTS.md.** Não contradiz nenhuma regra da constitution; quando a
   constitution muda, a skill é revisitada.

> Critério 6 é o gargalo real: muitas skills parecem prontas no papel e só revelam buracos
> quando um agente tenta segui-las. Maturidade exige a evidência de uso, não só a redação.

---

## Arquivos desta entrega

- `docs/skills/ex-2.3-estrategia-skills.md` — este documento (árvore + papéis + maturidade).
- `skills/domain/azure-functions-endpoint.md` — a SKILL.md completa (preenchida).
