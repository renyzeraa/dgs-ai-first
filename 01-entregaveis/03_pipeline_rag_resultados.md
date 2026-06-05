# Exercício 1.3 — Pipeline de RAG (PoC funcional) — Resultados e Análise

**Papel:** Desenvolvedor · **Ferramentas:** Claude (chat) · GitHub Copilot (indisponível no ambiente — ver nota abaixo)
**Tópicos aplicados:** RAG · Engenharia de Contexto · Engenharia de Prompt
**Código:** `novatech_rag.py` (pipeline), `run_poc.py` (baseline), `run_poc_v2.py` (com correções)

---

> **Ressalva — GitHub Copilot:** O enunciado prevê GitHub Copilot como ferramenta auxiliar
> de código. Durante a execução deste exercício o Copilot não estava disponível no ambiente
> (sem licença ativa). O código foi inteiramente gerado via Claude (chat), usando o mesmo
> modelo de "par de revisão" descrito na seção 6. Não há evidência de uso do Copilot a
> apresentar. Esta ressalva substitui o rótulo anterior "estilo GitHub Copilot" que era
> impreciso e poderia induzir o avaliador a supor uso real da ferramenta.

## 1. Arquitetura (3 etapas) e nota de backend

```
Ingestão            Busca                       Montagem de prompt
docs .md  --chunk-->  pergunta --embed-->  top-N --rerank-->  system + chunks + pergunta
          metadados            cosseno     gate                  (pronto p/ LLM)
```

**Backend pluggável (decisão de engenharia):**
- **Produção:** `sentence-transformers/all-MiniLM-L6-v2` (semântico) + **ChromaDB** — exatamente
  a stack sugerida. O código está pronto para esse caminho (e o equivalente ChromaDB está no
  rodapé de `novatech_rag.py`).
- **Execução deste PoC (offline):** o ambiente não tinha acesso ao download do modelo (HuggingFace
  fora da rede) nem espaço para `torch`, então rodei com **fallback TF-IDF + cosseno (numpy)**. A
  **mecânica do RAG é idêntica**; o que muda é o "motor" de similaridade (léxico × semântico). Isso
  é relevante para ler os resultados: **as falhas estruturais abaixo independem do embedder**, mas
  algumas falhas de recall **só somem com embeddings semânticos** — eu sinalizo cada caso.

> Lição já embutida: RAG é **sistema de engenharia de dados** (extração, chunking, metadados,
> re-ranking, gate), **não** uma chamada de API. Trocar o embedder não conserta dados ruins.

---

## 2. Ingestão — chunking *section-aware* (justificado)

**Estratégia:** quebra por cabeçalho (seção = 1 chunk), tabelas nunca divididas, overlap 12% em
seções longas, *breadcrumb* `[DOC vX | Seção N]` no início de cada chunk, metadados
(`doc_id, versão, data, seção, tipo_fonte`).

**Por que (não é "512 fixos sem motivo"):**
1. As perguntas mapeiam para **seções inteiras** → a seção é a unidade de recuperação ideal.
2. Poucos chunks densos e auto-descritivos mitigam **lost in the middle**.
3. Tabelas (frete/SLA) inteiras + **linearizadas** preservam a relação linha↔coluna.
4. Metadados habilitam **desambiguação de versão** e **citação de fonte**.

**Resultado da ingestão (real, deste PoC):**

| Doc | Chunks | ~Tokens | Seções |
|---|---|---|---|
| POL-001 | 7 | ~721 | 1, 2, 3.1, 3.2, 3.3, 3.4, 3.5 |
| PROC-042 (v1) | 5 | ~374 | 1, 2, 2.1, 3, 4 |
| PROC-042-v2 | 6 | ~523 | 1, 2, 2.1, 3, 4, 5 |
| SLA-2024 | 5 | ~643 | 1, 2, 3, 4, 5 |
| FAQ | 9 | ~830 | Itens 3, 8, 15, 22, 27, 32, 38, 41, 45 |
| **Total** | **32** | **~3.091** | média ~96 tok/chunk |

---

## 3. Retrieval — 10 perguntas vs gabarito do Anexo B (antes × depois)

Top-5 por pergunta, comparado ao mapa de cobertura. **Baseline** = `run_poc.py`;
**v2** = `run_poc_v2.py` (linearização de tabela + re-ranking versão/autoridade + gate).

| # | Pergunta | Baseline | v2 | Armadilha exposta |
|---|---|---|---|---|
| 1 | prazo de devolução | PARCIAL 1/2 | PARCIAL 1/2 | "prazo de devolução" trouxe **"prazo de entrega de frete"** (PROC) no topo — colisão léxica |
| 2 | posso devolver carga perigosa | **MISS** | **MISS** | POL-001 §3.2 não apareceu; topo foi **FAQ informal** |
| 3 | SLA do cliente Gold | **MISS** | **✅ HIT** | tabela SLA não recuperada (células não repetem termos) → **corrigido por linearização** |
| 4 | SLA do cliente Platinum | **MISS** | **✅ HIT** | tier inexistente; **autoridade** trouxe SLA §1 ("só 3 tiers") |
| 5 | frete 600kg Manaus | PARCIAL 1/2 | PARCIAL 1/2 | "Manaus" não existe nos docs (dizem "Norte"); §2.1 não recuperado |
| 6 | frete 300kg Salvador | sem cobertura ✓ | **FALSO-POSITIVO** | <500kg não documentado, mas chunks de frete passam do gate |
| 7 | carga danificada | HIT | HIT | resposta só no **FAQ informal** |
| 8 | perigosa + expresso | HIT | HIT (frágil) | só no FAQ; penalidade de autoridade quase enterrou a única fonte |
| 9 | multiplicador Sudeste | HIT (errado!) | **✅ HIT (certo)** | **v1 (1.0) rankeava ACIMA de v2 (1.1)** → corrigido por "mais recente vence" |
| 10 | multi-domínio (3 temas) | MISS 0/4 | PARCIAL 1/4 | 1 busca não cobre 4 seções |
| | **Cobertura completa** | **3/9** | **5/9** | |

As correções **funcionaram e são mensuráveis** (3/9 → 5/9). Os casos que **sobraram** são
exatamente os que dependem de coisas **além do retrieval léxico** (próxima seção).

---

## 4. Geração — colando o prompt montado no Claude

### Caso A — "Qual o multiplicador de frete para o Sudeste?" (mostra o efeito da correção de versão)

- **Contexto baseline:** PROC-042 **v1** §2.1 (1.0) no topo, acima da v2 §2.1 (1.1).
- **Resposta provável (baseline):** *"O multiplicador do Sudeste é **1.0**. Fonte: PROC-042."* ❌
  **errado** — usou a versão antiga porque ela rankeou primeiro.
- **Contexto v2:** após "mais recente vence", só a v2 §2.1 (1.1) entra.
- **Resposta v2:** *"O multiplicador regional para o Sudeste é **1.1**. Fonte: (PROC-042-v2 v2.0,
  Seção 2.1)."* ✅ correta, citada, guardrails ok.

> A mesma pergunta, mesmo modelo, mesmo prompt — **o que mudou foi o retrieval**. Geração boa com
> contexto errado = resposta errada confiante.

### Caso B — "Quanto custa o frete para 600kg para Manaus?" (mostra recusa honesta)

- **Contexto v2 recuperado:** fórmula (v2 §2) + prazo (v2 §3) + objetivo (v2 §1). **Faltam** a
  tarifa-base e a tabela de multiplicadores (§2.1 não foi recuperada).
- **Resposta v2:** *"Não consigo informar o valor: a documentação recuperada traz a fórmula
  (valor base × multiplicador regional × fator de peso) e o fator de peso 1.0 para 500–1.000 kg,
  mas **não traz a tarifa-base nem o multiplicador da região**. Consulte a tabela mensal de
  tarifas ou escale ao supervisor. Fonte: (PROC-042-v2 v2.0, Seção 2)."* ✅ recusa honesta
  (guardrail "informação parcial"), **sem inventar valor**.

> Mas isso também revela um **bug de retrieval**: §2.1 (Norte = 1.8) **deveria** ter sido
> recuperado. A qualidade da geração é **limitada pela qualidade do retrieval**.

---

## 5. Problemas encontrados e correções (concretas)

| # | Problema (com evidência) | Correção | Status |
|---|---|---|---|
| **P1** | **Contradição de versão** recuperada junta (Q9: v1 1.0 acima de v2 1.1) | Metadado de versão/data + re-ranking **"mais recente vence"** (descarta v1 quando v2 cobre a mesma seção) | ✅ **corrigido** (Q9 → 1.1 no topo) |
| **P2** | **Tabela não recuperada** (Q3: SLA §2 fora do top-5; células não repetem termos) | **Linearização de tabela** na ingestão ("Cliente Gold → resolução 24h úteis") | ✅ **corrigido** (Q3 → HIT) |
| **P3** | **Chunk de domínio errado** (Q1: "prazo de devolução" trouxe "prazo de entrega de frete") | **Embeddings semânticos** (distinguem devolução×entrega) + filtro por intenção/doc | ⚠️ parcial no léxico; **resolve com o embedder real** |
| **P4** | **Pergunta sem cobertura respondida** (Q6 <500kg passa do gate → falsa confiança) | Gate de relevância **+ guardrail de escopo na geração** (PROC-042 diz "acima de 500kg") | ⚠️ gate sozinho insuficiente; precisa de regra no prompt (Ex.1.2) |
| **P5** | **Vocabulário usuário ≠ doc** (Q5: "Manaus" não existe; doc diz "Norte") | Normalização **cidade→região** no pré-processamento da query **ou** embedder semântico | ⚠️ resolve com semântico + dicionário geográfico |
| **P6** | **Multi-domínio** (Q10: 1 busca não cobre 4 seções) | **Decomposição** da query em sub-perguntas → retrieval por sub-query → merge | ⚠️ requer orquestração (multi-query) |
| **P7** | **Re-ranking de autoridade cego** (Q8: penalizar FAQ quase enterrou a única fonte) | Rebaixar informal **apenas quando existir fonte formal** para o mesmo tópico; senão manter e marcar baixa confiança | 🔧 refinamento proposto |

---

## 6. Uso do Claude como par de revisão (não como substituto)

Depois de escrever o pipeline e rodar o baseline, dei o código + os resultados ao Claude e pedi:
*"aja como revisor sênior de RAG — o que está fraco?"*.

- **O que o Claude apontou e eu não tinha visto:** que o gate global de relevância seria
  insuficiente para o caso <500kg (P4 precisa de guardrail na geração, não só de threshold), e que
  a penalidade de autoridade poderia **suprimir a única fonte** quando só o FAQ cobre o tema (P7).
- **O que eu vi e o Claude não enfatizou:** que a contradição de versão (P1) era o risco de maior
  impacto de negócio (valor de frete errado para o cliente) e merecia a correção primeiro.
- **Resultado:** priorizei P1/P2 (corrigíveis no retrieval, 3/9→5/9) e documentei P3–P6 como
  dependentes de embedder semântico / orquestração — separando "o que conserto agora" de "o que
  precisa da stack de produção". Esse julgamento de **priorização** é humano; o Claude foi ótimo
  para **ampliar a lista de riscos**.

---

## 7. Conclusão

O PoC **roda** (ingere, busca, monta prompt, gera resposta) e, com duas correções de dados/
re-ranking, subiu a cobertura de retrieval de **3/9 para 5/9** — validado contra o gabarito do
Anexo B. As falhas remanescentes mapeiam limpo para: **embeddings semânticos** (P3, P5),
**guardrail de geração** (P4), **orquestração multi-query** (P6) e **refino de autoridade** (P7).
Nenhuma delas é "trocar de modelo" — todas são **engenharia de dados e de contexto**, que é a tese
central do projeto.
