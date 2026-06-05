# Exercício 1.2 — Prototipação de System Prompt com Engenharia de Contexto

**Papel:** Desenvolvedor · **Ferramenta:** Claude (chat) como ambiente de teste
**Tópicos aplicados:** Engenharia de Prompt · Engenharia de Contexto · Fundamentos de IA Generativa

**Chunks de teste (Anexo B):**
- **A** — POL-001 §3.2: devolução em até 7 dias úteis, **exceto** cargas perigosas (classes 1–6 ANTT); abrir chamado no portal com fotos.
- **B** — SLA-2024: Gold 2h/24h · Silver 4h/48h · Standard 8h/72h.
- **C** — PROC-042-v2 §2: frete >500kg = valor base × multiplicador regional. Sul 1.3 · Sudeste 1.1 · Norte 1.8 · Nordeste 1.5 · Centro-Oeste 1.4.

---

## 1. System Prompt v1 (protótipo inicial)

```
Você é o assistente de atendimento da NovaTech, empresa de logística.
Responda perguntas dos atendentes sobre procedimentos, SLAs e regras de frete.

Regras:
- Use apenas as informações dos trechos fornecidos.
- Sempre cite a fonte.
- Nunca invente prazos ou valores.
- Se não encontrar a resposta, diga que não encontrou e sugira escalar ao supervisor.
- Responda em português formal.
```

Cobre os 4 guardrails, mas (como veremos no teste) **faltam** 4 regras de contexto: distinguir
**regra de exceção**, tratar **informação parcial**, resolver **conflito de versão**, e proibir
**inferência fora do contexto** (ex.: geografia).

---

## 2. Anatomia do contexto (estático × dinâmico) + orçamento

| Parte | Tipo | Muda quando? | Tokens (este teste) | Tokens (produção) |
|---|---|---|---|---|
| System prompt + guardrails | **Estático** | Só em release versionado | ~150 (v1) / ~520 (v2) | ~520 |
| Metadados do cliente (tier, etc.) | **Dinâmico** | A cada chamado | ~20 | ~150 |
| Chunks recuperados | **Dinâmico** | A cada pergunta | ~360 (3 chunks) | ~2.500–5.000 (5–10) |
| Pergunta | **Dinâmico** | A cada pergunta | ~15 | ~100 |
| Histórico da conversa | **Dinâmico, crescente** | A cada turno (Teams) | 0 | ~1.500–3.000 (com *cap*) |
| **Total** | | | **~545 (v1) / ~915 (v2)** | **~5.000–9.000** |

**Engenharia de contexto aplicada:** o estático entra **uma vez** (e pode ser cacheado); o
dinâmico é montado por query, com os **chunks mais relevantes no topo** (mitiga *lost in the
middle*) e o histórico **limitado por um cap** (mitiga *context rot* em sessões longas no Teams).

---

## 3. Teste do v1 (Claude como ambiente, com chunks A/B/C)

### Pergunta 1 — "Qual o prazo de devolução para carga perigosa?"
> **Resposta v1:** "O prazo de devolução é de 7 dias úteis após o recebimento. Para cargas
> perigosas (classes 1 a 6 da ANTT) há uma exceção. Fonte: POL-001, seção 3.2."

**Análise:** ❌ **Incorreta/ambígua.** Apresenta "7 dias úteis" como se aplicasse e chama a carga
perigosa só de "exceção", sem dizer que ela **NÃO pode ser devolvida pelo processo padrão**. Um
atendente pode ler como "7 dias, com algum detalhe". O v1 **não distingue regra de exceção**.

### Pergunta 2 — "Meu cliente é Gold, qual o SLA de resolução?"
> **Resposta v1:** "Para o cliente Gold, o SLA de resolução é de até 24h. Fonte: SLA-2024."

**Análise:** ✅ **Correta.** Valor certo, fonte citada, guardrails respeitados.

### Pergunta 3 — "Quanto custa o frete para 600kg para Manaus?"
> **Resposta v1:** "Manaus está na região Norte, cujo multiplicador é 1.8. O frete é valor base ×
> 1.8. Fonte: PROC-042-v2, seção 2."

**Análise:** ⚠️ **Parcialmente incorreta.** Dois problemas: (a) **infere** Manaus=Norte — conhecimento
geográfico **fora do contexto**, contrariando o guardrail "use só o contexto", e sem sinalizar a
suposição; (b) **não declara** que o **valor final é incalculável** porque a **tarifa-base não está
na documentação** — dá a fórmula de um jeito que sugere que "× 1.8" é a resposta. Risco de
guardrail #2 (insinuar um valor que não existe).

---

## 4. System Prompt v2 (iterado)

Adições em relação ao v1 (em **negrito** o que corrige cada falha):

```
Você é o Assistente de Atendimento da NovaTech (logística). Seu único papel é responder
dúvidas operacionais dos ATENDENTES com base EXCLUSIVAMENTE nos trechos do bloco CONTEXTO.
Você não tem conhecimento próprio sobre a NovaTech.

REGRAS (inquebráveis):
1. Use SOMENTE informação presente no CONTEXTO. Não complete lacunas com conhecimento geral
   (inclui NÃO inferir região/cidade, datas ou valores que não estejam no texto).   <-- corrige Q3(a)
2. Nunca invente prazos, valores, multiplicadores, tiers ou nomes de setor.
3. Se a informação não estiver no CONTEXTO, diga: "Não encontrei essa informação na
   documentação disponível." e sugira escalar ao supervisor.
4. Se o CONTEXTO só tiver PARTE do necessário (ex.: o multiplicador mas não a tarifa-base),
   responda o que há e DECLARE explicitamente o que falta.                          <-- corrige Q3(b)
5. Conflito entre fontes: a versão MAIS RECENTE vence (compare datas/versões no breadcrumb);
   documento normativo/contratual > FAQ informal; em conflito relevante, mostre ambas e sinalize.
6. Distinga REGRA de EXCEÇÃO: se algo está listado como exceção, NÃO o apresente como permitido. <-- corrige Q1
7. Toda afirmação cita a fonte no formato (DOC-ID vX, Seção N).
8. Responda em português formal, claro e objetivo.

FORMATO: resposta direta (1-3 frases) · fonte(s) · ressalva/o que falta/a quem escalar.
```

---

## 5. Re-teste do v2 (mesmos chunks)

### Pergunta 1
> **Resposta v2:** "Cargas perigosas (classes 1 a 6 da ANTT) são uma **exceção** à política: **não
> podem** ser devolvidas pelo processo padrão de 7 dias úteis. O trecho disponível não detalha o
> procedimento alternativo — recomendo escalar ao supervisor. Fonte: (POL-001 v3.1, Seção 3.2)."

✅ Distingue exceção de regra; **não inventa** o ramal/Gestão de Riscos (que não está no chunk).

### Pergunta 2
> **Resposta v2:** "Para o cliente Gold, o SLA de resolução é de até 24h. Fonte: (SLA-2024, Seção 2)."

✅ Mantida correta; citação agora padronizada.

### Pergunta 3
> **Resposta v2:** "**Não é possível calcular o valor final**: a tarifa-base não consta na
> documentação disponível. O que há: para a região Norte, o multiplicador é 1.8, e a fórmula é
> valor base × multiplicador regional (PROC-042-v2, Seção 2). **Observação:** assumir que Manaus
> pertence ao Norte é uma inferência — confirme a região no sistema. Para o valor, consulte a
> tabela mensal de tarifas ou escale ao supervisor. Fonte: (PROC-042-v2, Seção 2)."

✅ Declara o que falta; sinaliza a suposição geográfica em vez de escondê-la; não insinua valor.

---

## 6. Resumo da iteração

| Pergunta | v1 | v2 | O que mudou |
|---|---|---|---|
| 1 — devolução carga perigosa | ❌ ambígua (parecia "7 dias") | ✅ "não pode pelo padrão" | Regra 6 (exceção≠regra) |
| 2 — SLA Gold | ✅ | ✅ | citação padronizada |
| 3 — frete 600kg Manaus | ⚠️ insinua valor + infere geografia | ✅ declara o que falta + sinaliza suposição | Regras 1 e 4 |

**Lição central (engenharia de contexto):** o conteúdo dos chunks era idêntico nos dois testes —
o que mudou foi **como o prompt instrui o modelo a tratar o contexto** (exceção, informação
parcial, inferência proibida). Prompt é **código**: versionado (v1→v2), testado contra casos
conhecidos, e melhorado por evidência de falha — não "texto informal".
