# Exercício 1.1 — Análise de Viabilidade Técnica

**Projeto:** Assistente de IA de Atendimento — NovaTech
**Papel:** Desenvolvedor · **Ferramenta:** Claude (chat)
**Tópicos aplicados:** Fundamentos de IA Generativa · Engenharia de Contexto · RAG/MCP

> Este documento traz a **versão final (v2)**. A iteração com o Claude (v1 → crítica → v2)
> está registrada no final, na seção "Histórico de iteração".

---

## 1. Veredito

O assistente é **viável** com a stack proposta (Azure AI Search + Azure OpenAI sobre M365),
mas o sucesso **não depende do modelo** — depende do **pipeline de dados (RAG)** e da
**engenharia de contexto**. A maior parte dos riscos abaixo é de *dados* e *extração*, não de
*geração*. A meta da diretoria (de 12 → 2 min/chamado) é plausível para os ~60% de chamados que
consultam documentação, **desde que** o retrieval seja confiável e os documentos contraditórios
sejam tratados na ingestão.

---

## 2. Desafios por tipo de fonte

Cada formato tem um modo de falha próprio que **se propaga até a resposta** — um chunk ruim na
ingestão vira uma resposta errada com aparência confiante.

| Fonte | Desafio técnico | Como afeta a resposta | Estratégia de tratamento |
|---|---|---|---|
| **PDF com tabelas (15+ colunas)** — frete | Extração de texto "achata" a tabela e embaralha a relação linha↔coluna | O modelo lê "Norte 1.8 Sudeste 1.1" como texto solto e pode trocar valores entre regiões | Extração *layout-aware* (Azure Document Intelligence); converter cada tabela para Markdown/CSV preservando cabeçalho; manter a tabela **inteira** em 1 chunk; **linearizar** linhas ("Região Norte → multiplicador 1.8") |
| **PDF escaneado (~15%)** | Sem camada de texto → exige OCR; erros de OCR em números (1.8↔18, O↔0) | Corrompe exatamente os dados críticos (valores, prazos) | OCR com *confidence score*; revisão humana de campos numéricos com baixa confiança; marcar o chunk com `origem=ocr` |
| **Wiki Confluence (links + macros)** | Links internos carregam contexto que some quando a página é isolada; macros renderizam ruído | Chunk perde o contexto que estava "na outra página"; macro vira lixo no embedding | Expandir/resolver macros na ingestão; guardar alvos de link como metadado; remover markup de macro |
| **Planilhas (fórmulas interdependentes)** | Valor de uma célula depende de outras; exportar mostra fórmula, não resultado | Embedda `=B2*1.3` em vez de "1.95"; ou valores sem rótulo | Exportar **valores calculados** com cabeçalho; serializar cada linha como registro auto-descritivo; *snapshot* mensal versionado |

**Princípio:** tipos de conteúdo diferentes exigem **estratégias de extração e chunking
diferentes**. Um pipeline único "PDF→texto→chunk fixo de 512 tokens" quebra em 3 dos 4 casos.

---

## 3. Estimativa de tamanho da base (em tokens)

Regra prática do treinamento: **~0,75 palavra por token** → `tokens ≈ palavras ÷ 0,75`.

| Fonte | Volume | Palavras (estimativa) | Tokens (~÷0,75) |
|---|---|---|---|
| PDFs SharePoint | 800 docs × 10 pág. × ~500 palavras/pág. | ~4,0M | **~5,3M** |
| Wiki Confluence | 400 pág. × ~1.500 palavras | ~0,6M | **~0,8M** |
| Planilhas | 50 × ~3.000 palavras-equiv. (tabelas) | ~0,15M | **~0,2M** |
| **TOTAL** | | ~4,75M | **~6,3M tokens** |

**Sensibilidade (honestidade da estimativa):** o número é dominado pela suposição de
palavras/página. A 400 palavras/pág. → ~5,3M total; a 750 → ~9M+. Faixa realista:
**~6–10M tokens**, podendo chegar a ~12M se as páginas forem densas/longas. **Implicação:** a
base inteira **nunca cabe** na janela do modelo (128K) — por isso o problema é de **retrieval
seletivo**, não de "jogar tudo no contexto".

---

## 4. Orçamento de contexto (o ponto central de engenharia de contexto)

GPT-4o tem janela de **128K tokens**. O cálculo ingênuo:

```
(128.000 − 2.000 system/instruções) ÷ 500 tokens/chunk ≈ 252 chunks "cabem"
```

**Esse número é um teto, não uma meta.** Encher o contexto **piora** a resposta por dois efeitos:

- **Orçamento de atenção limitado:** o modelo tem capacidade finita de "prestar atenção". Quanto
  mais chunks irrelevantes competindo, menor a precisão (mais distratores → mais alucinação).
- **Lost in the middle:** informação no **meio** de um contexto longo é processada pior que no
  **início** e no **fim**. Com 200 chunks, o chunk certo "afoga".

**Orçamento recomendado por query (alvo, não teto):**

| Parte do contexto | Estático/Dinâmico | Tokens |
|---|---|---|
| System prompt + guardrails | estático | ~1.500 |
| Metadados do cliente (tier, etc.) | dinâmico | ~150 |
| **Chunks recuperados (5–10 × ~500)** | dinâmico | **~2.500–5.000** |
| Histórico da conversa (Teams, com *cap*) | dinâmico, crescente | ~1.500–3.000 |
| Pergunta | dinâmico | ~100 |
| Reserva para a resposta | — | ~1.500 |
| **Total típico** | | **~7.000–11.000 (de 128K)** |

**Conclusão:** usamos **<10%** da janela. O gargalo **não é o tamanho da janela** — é a
**qualidade do retrieval** (trazer os 5–10 chunks **certos**) e o **posicionamento** (chunk mais
relevante no topo). "Context window grande" ≠ "melhor"; é um **recurso a ser gerenciado**.

---

## 5. Estratégia de chunking recomendada (justificada)

**Recomendação: chunking *section-aware* (por seção/cabeçalho), ~300–500 tokens, overlap de
10–15%, tabelas nunca divididas, com metadados de versão/data/seção.**

Justificativa **pelo tipo de pergunta** e pelo **lost in the middle**:

1. **As perguntas mapeiam para seções inteiras.** "Qual o prazo de devolução?" → POL-001 §3.1;
   "multiplicador do Sudeste?" → PROC-042-v2 §2.1. A **seção é a unidade semântica natural** —
   um chunk = uma seção maximiza a chance de **um único chunk** de alta relevância responder.
2. **Menos chunks, mais densos.** Chunks alinhados à seção evitam fragmentar a resposta em 5
   pedaços (que disputam atenção e ativam o *lost in the middle*).
3. **Tabelas inteiras + linearizadas.** A tabela de frete/SLA é inútil cortada no meio; mantê-la
   íntegra e adicionar uma versão linha-a-linha ("Cliente Gold → resolução 24h úteis") melhora
   muito o recall (comprovado no Ex. 1.3: SLA Gold passou de *MISS* para *HIT*).
4. **Metadados por chunk** (`doc_id`, `versão`, `data`, `seção`, `tipo_fonte`) habilitam
   desambiguação de versão (PROC-042 v1 vs v2) e **citação de fonte** — requisito do produto.

Chunking **fixo sem overlap** (a anti-prática) cortaria a tabela de multiplicadores e perderia
contexto nas fronteiras de seção.

---

## 6. Onde entra MCP (RAG vs MCP — complementares)

Nem tudo deve ir para o RAG. Conceitualmente:

- **RAG** responde *"o que a documentação diz"* — conhecimento textual, semi-estático. É o que
  resolve prazos, políticas, regras de frete.
- **MCP** (Model Context Protocol) é o **protocolo padronizado** para o assistente **chamar
  ferramentas / dados vivos**: status de rastreamento em tempo real, **tier do cliente vindo do
  CRM**, abertura de chamado, ou disparo da **re-ingestão** quando um documento novo é publicado.

**Decisão de arquitetura:** dados **dinâmicos** (tier, tracking, valor declarado) **não devem
ser embeddados** (ficariam desatualizados) — devem ser buscados via **tool/MCP** no momento da
query e injetados como metadado dinâmico do contexto. No ambiente Microsoft, MCP é o que conecta
o assistente do Teams ao SharePoint/CRM/sistema de chamados de forma governada.

---

## 7. Mapa de riscos (probabilidade × impacto × mitigação)

| # | Risco | Prob. | Impacto | Mitigação acionável |
|---|---|---|---|---|
| R1 | **Documentos contraditórios** (PROC-042 v1 × v2) misturados na mesma resposta | **Alta** | Qualidade (resposta errada com confiança) | Versionamento explícito no pipeline (data de vigência como metadado); re-ranking "mais recente vence"; **comprovado no Ex.1.3**: descartar v1 quando v2 cobre a mesma seção |
| R2 | **FAQ informal como fonte de informação crítica** | **Alta** | Qualidade/Compliance | Marcar `tipo_fonte=informal`; rebaixar FAQ no re-ranking; **bloquear** FAQ como fonte única para temas críticos (carga perigosa, valores) |
| R3 | **Alucinação** — inventar tier ("Platinum"), prazo ou valor inexistente | **Média** | Qualidade/Confiança do usuário | Guardrail no prompt ("nunca invente") + **enforcement determinístico** fora do prompt (filtro que rejeita resposta sem citação válida); gate de relevância |
| R4 | **Tabelas extraídas erradas** (frete/SLA) | **Média** | Qualidade (valor trocado) | Extração layout-aware + linearização + revisão de campos numéricos |
| R5 | **Context rot / lost in the middle** em conversas longas no Teams | **Média** | Qualidade (a 5ª pergunta ignora os chunks) | *Cap* de histórico (últimas N trocas); re-recuperar chunks a cada pergunta; resumo de sessão em vez de histórico bruto |
| R6 | **Expectativa da diretoria** ("sabe tudo, como o ChatGPT") | **Alta** | Prazo/Político | Alinhar critérios mensuráveis (% respostas com fonte verificável, taxa de "não sei" correta); demo honesta com os 40% sem cobertura |
| R7 | **Pergunta sem cobertura na base** (frete <500kg) respondida assim mesmo | **Média** | Qualidade | Gate de relevância + regra de escopo no prompt; comportamento "não encontrei" auditável |

---

## 8. Três perguntas para o Tech Lead (antes de confirmar 3 meses)

1. **Quem é dono da curadoria de dados?** O RAG depende da qualidade-fonte. Vamos ter acesso e um
   responsável da NovaTech para **resolver as contradições na origem** (marcar versão vigente),
   ou o pipeline terá que inferir vigência? (Define o esforço de ingestão.)
2. **Qual o pipeline de atualização?** O requisito é "24h após publicação". A re-ingestão será
   *event-driven* (webhook do SharePoint/MCP) ou batch agendado? Quem garante que documento
   obsoleto sai do índice? (Risco operacional R1/R5.)
3. **Como medimos "certo"?** Vamos ter um **conjunto-gabarito** (pergunta → chunk/resposta
   esperada, como o Anexo B) para testar retrieval e geração de forma não-determinística? Sem
   isso, não há critério objetivo de aceite nem regressão.

---

## 9. Histórico de iteração com o Claude (v1 → crítica → v2)

**Prompt 1 (v1):** *"Você é desenvolvedor avaliando a viabilidade técnica deste assistente RAG
para a NovaTech [cenário]. Liste os riscos técnicos."*
→ **Output v1:** lista genérica — "a IA pode errar", "qualidade dos dados é importante",
"monitorar alucinação". Sem números, sem mitigação acionável.

**Prompt 2 (crítica dirigida):** *"Revise criticamente sua própria lista. Aponte: (a) riscos
genéricos demais; (b) onde faltou número/estimativa; (c) mitigações que são só 'monitorar';
(d) riscos de **contexto** (context rot, lost in the middle, orçamento de atenção) que você não
citou."*
→ **Output:** o Claude apontou que faltava a **estimativa de tokens**, o **orçamento de contexto**
(o número "252 chunks cabem" como teto, não meta), o risco de **FAQ como fonte crítica** e a
distinção **RAG vs MCP** para dados dinâmicos.

**Prompt 3 (refino):** pedi para reescrever cada risco com prob./impacto/mitigação **concreta** e
amarrar à evidência do PoC do Ex.1.3.
→ **Output v2:** este documento. Ganhos verificáveis sobre o v1: estimativa quantitativa,
orçamento de contexto explícito, mitigações acionáveis (versionamento, re-ranking, gate),
e riscos de contexto nomeados.

**Lição:** o Claude como **revisor** (não só gerador) elevou o material de "lista óbvia" para
"análise com trade-offs". O valor veio da **crítica dirigida**, não do primeiro prompt.
