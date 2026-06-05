# Cenário-Âncora 1 — Fase de Entendimento e Contexto

## Tópicos cobertos
- Fundamentos de IA Generativa
- Engenharia de Prompt
- Engenharia de Contexto
- RAG (Retrieval-Augmented Generation)

## Ferramentas disponíveis para os participantes
- **Claude** (chat) — todos os papéis
- **GitHub Copilot** — desenvolvedores e Tech Lead
- **Claude Cowork** — Delivery Manager, Product Specialist, QA
- **Claude Design** — Product Specialist

## Documentos de apoio
- **Anexo A — Documentação Simulada da NovaTech:** Contém o conteúdo completo dos 5 documentos-chave da NovaTech (POL-001, PROC-042, PROC-042-v2, SLA-2024, FAQ-Atendimento). É a fonte de verdade para todos os exercícios que pedem avaliação de respostas ou análise de documentação.
- **Anexo B — Chunks de Referência do Pipeline de RAG:** Contém os chunks que o pipeline de RAG extrairia dos documentos do Anexo A, com mapa de cobertura (pergunta → chunks esperados). Use nos exercícios que envolvem teste de prompts ou avaliação de retrieval.

---

## O Cenário

A NovaTech é uma empresa de médio porte do setor de logística com 1.200 funcionários. Sua operação depende de um conjunto extenso de documentação interna: manuais de procedimento operacional, políticas de compliance, tabelas de SLA por tipo de cliente, regras de cálculo de frete, e normas de segurança de carga.

Hoje, essa documentação está espalhada em três fontes: um SharePoint corporativo com ~800 documentos (PDFs e Word), uma wiki interna no Confluence com ~400 páginas, e uma pasta de rede com planilhas de referência atualizadas mensalmente.

O problema: a equipe de atendimento ao cliente (45 pessoas) gasta em média 12 minutos por chamado buscando informações nessas fontes para responder dúvidas de clientes sobre prazos, regras de frete, políticas de devolução e procedimentos de reclamação. Isso gera atrasos, respostas inconsistentes e frustração tanto dos atendentes quanto dos clientes.

A NovaTech contratou a DB1 para construir um assistente de IA que permita aos atendentes fazer perguntas em linguagem natural e receber respostas fundamentadas na documentação oficial da empresa, com indicação da fonte. O assistente será integrado ao ambiente Microsoft da NovaTech (Teams + SharePoint).

### Informações adicionais fornecidas pela NovaTech

- O volume médio é de 320 chamados/dia, dos quais ~60% envolvem consulta a documentação.
- A documentação é atualizada mensalmente por 3 áreas diferentes (Operações, Compliance, Comercial), sem processo unificado de revisão.
- Alguns documentos se contradizem entre versões — a equipe de atendimento hoje resolve isso "perguntando para quem sabe".
- A NovaTech já tem licenças Microsoft 365 E3 e está disposta a provisionar Azure AI Services.
- O projeto tem orçamento para 3 meses de discovery + desenvolvimento + go-live.
- A expectativa da diretoria é reduzir o tempo médio de busca de 12 para menos de 2 minutos por chamado.

---

## Exercício

---

### DESENVOLVEDOR

#### Exercício 1.1 — Análise de viabilidade técnica com fundamentos de LLM e engenharia de contexto

**Contexto:** O Tech Lead pediu que você avalie a viabilidade técnica do assistente considerando as características da documentação da NovaTech e o impacto do gerenciamento de contexto na arquitetura.

**Ferramentas a utilizar:** Claude (chat)

**Inputs fornecidos:**
- O cenário completo.
- Informações técnicas adicionais: *"Os PDFs do SharePoint incluem documentos com tabelas complexas (tabelas de frete com 15+ colunas), fluxogramas embutidos como imagens, e alguns documentos escaneados (OCR necessário). A wiki do Confluence tem links internos entre páginas e usa macros customizadas. As planilhas têm fórmulas interdependentes."*
- Conceito de context engineering aplicado a RAG: *"O contexto que o LLM recebe a cada pergunta é limitado pela janela de contexto do modelo. A qualidade da resposta depende de: quais chunks são selecionados (relevância), quantos chunks cabem no contexto (orçamento de atenção), onde ficam posicionados no prompt (informação no meio de contextos longos é 'esquecida' — o efeito 'lost in the middle'), e o que mais está no contexto competindo por atenção (system prompt, histórico de conversa, instruções)."*

**Tarefa:**
1. Usando o **Claude**, produza uma análise técnica que cubra:
   - Para cada tipo de fonte (PDFs com tabelas, PDFs escaneados, wiki com links, planilhas com fórmulas): qual o desafio para o pipeline de RAG, como isso afeta a qualidade das respostas, e uma estratégia de tratamento.
   - Estimativa do tamanho aproximado da base em tokens considerando ~800 documentos PDF (média de 10 páginas cada), ~400 páginas wiki (média de 1.500 palavras cada), e ~50 planilhas. Use a regra prática de ~0.75 palavras por token.
   - Análise de orçamento de contexto: dado que o GPT-4o tem 128K tokens de janela e o system prompt + instruções consomem ~2K tokens, quantos chunks de ~500 tokens cabem em cada query? Como isso afeta a estratégia de chunking e retrieval?
   - Recomendação de estratégia de chunking justificada pelo tipo de pergunta que o usuário fará e pelo conceito de *lost in the middle*.

2. Peça ao **Claude** que revise sua análise: forneça o documento e peça que identifique pontos fracos, estimativas otimistas demais ou riscos que você não considerou. Incorpore o feedback.

**Entregável:** A análise técnica final e o histórico de iteração com o Claude.

**Critérios de avaliação:**
- A análise demonstra entendimento de que diferentes tipos de conteúdo exigem diferentes estratégias de extração e chunking.
- A estimativa de tokens é razoável e mostra compreensão prática do conceito.
- A análise de orçamento de contexto demonstra compreensão de que context window é um recurso limitado que precisa ser gerenciado (não é "quanto maior melhor").
- A estratégia de chunking é justificada pelo tipo de pergunta e considera o efeito *lost in the middle*.
- A iteração com o Claude melhorou o documento de forma verificável.

---

#### Exercício 1.2 — Prototipação de prompt com engenharia de contexto

**Contexto:** Você precisa prototipar o system prompt do assistente e testar com cenários reais. Além do conteúdo do prompt, você precisa pensar em como o contexto é estruturado: o que é estático, o que é dinâmico, e como a ordem da informação afeta a resposta.

**Ferramentas a utilizar:** Claude (chat) — o próprio Claude serve como ambiente de teste do prompt

**Inputs fornecidos:**
- O cenário completo.
- Guardrails definidos pelo Product Specialist: *"O assistente deve (1) sempre citar a fonte do documento, (2) nunca inventar prazos ou valores que não estejam na documentação, (3) quando não encontrar resposta, dizer explicitamente que não encontrou e sugerir escalar para o supervisor, (4) responder em português formal mas acessível."*
- 3 chunks simulados de documentação (extraídos do **Anexo B** — o Anexo B contém o conjunto completo de chunks e o mapa de cobertura para validação):
  - Chunk A: *"Política de Devolução POL-001, seção 3.2: Mercadorias podem ser devolvidas em até 7 dias úteis após o recebimento, exceto cargas classificadas como perigosas (classes 1 a 6 da ANTT). O cliente deve abrir chamado no portal e anexar fotos da mercadoria."*
  - Chunk B: *"Tabela SLA-2024: Cliente Gold — resposta em até 2h, resolução em até 24h. Cliente Silver — resposta em até 4h, resolução em até 48h. Cliente Standard — resposta em até 8h, resolução em até 72h."*
  - Chunk C: *"PROC-042-v2, seção 2: Frete especial para cargas acima de 500kg: valor base × multiplicador regional. Região Sul: 1.3. Região Sudeste: 1.1. Região Norte: 1.8. Região Nordeste: 1.5. Região Centro-Oeste: 1.4."*
- Conceito de contexto estático vs dinâmico: *"Em um prompt de produção, algumas partes são estáticas (system prompt, guardrails — raramente mudam) e outras são dinâmicas (chunks recuperados, dados do cliente, histórico da conversa — mudam a cada query). A engenharia de contexto decide como essas partes se compõem: em que ordem, com que prioridade, e o que fazer quando o contexto total ultrapassa o orçamento."*

**Tarefa:**
1. Escreva um system prompt completo para o assistente, incorporando os guardrails e o contexto do projeto. Organize o prompt em seções claras: identidade, regras, formato de resposta, e instruções para uso dos chunks. Defina explicitamente a ordem de prioridade quando houver conflito entre fontes.

2. Documente a estrutura de contexto do prompt: identifique quais partes são estáticas (vão em toda query) e quais são dinâmicas (mudam por query). Estime o tamanho em tokens de cada parte.

3. Teste o prompt diretamente no **Claude**: abra uma conversa nova, cole o system prompt como instrução inicial junto com os chunks simulados, e faça estas 3 perguntas como se fosse o atendente:
   - "Qual o prazo de devolução para carga perigosa?"
   - "Meu cliente é Gold, qual o SLA de resolução?"
   - "Quanto custa o frete para 600kg para Manaus?"

4. Analise cada resposta: está correta? Citou a fonte? Respeitou os guardrails? Onde errou?

5. Itere o system prompt: reescreva partes que geraram respostas inadequadas e teste novamente.

**Entregável:** O system prompt v1 com mapeamento de contexto estático/dinâmico, as respostas obtidas, a análise crítica, o system prompt v2 (iterado), e as respostas da segunda rodada.

**Critérios de avaliação:**
- O system prompt é específico, com constraints claros (não é genérico como "você é um assistente útil").
- O mapeamento estático/dinâmico demonstra compreensão de engenharia de contexto (não é apenas "o prompt completo").
- A análise das falhas demonstra pensamento crítico (ex: para carga perigosa, a resposta correta é que NÃO pode devolver, conforme a exceção do POL-001).
- A iteração mostra melhoria concreta entre v1 e v2.
- O participante demonstra que usou o Claude como ambiente de teste real.

---

#### Exercício 1.3 — Construção de pipeline de RAG com ferramentas open-source

**Contexto:** O Tech Lead quer uma prova de conceito funcional do pipeline de RAG usando ferramentas gratuitas e open-source, antes de investir em licenças Azure. Você precisa construir um protótipo que ingira documentos, crie embeddings, armazene num vector store, e responda perguntas com base nos documentos.

**Ferramentas a utilizar:** Claude (chat) + GitHub Copilot

**Inputs fornecidos:**
- O cenário completo.
- Os documentos da NovaTech como arquivos individuais para ingestão (ver **Anexo A**, pasta `anexo-a-documentos-individuais/` — 5 arquivos .md, um por documento, prontos para processamento por scripts).
- Os chunks de referência (ver **Anexo B**) — use o mapa de cobertura como gabarito para validar se o pipeline recupera os chunks corretos.
- Stack sugerida (todas gratuitas/open-source):
  - **Python** como linguagem.
  - **ChromaDB** como vector store local (pip install chromadb).
  - **sentence-transformers** para embeddings open-source (pip install sentence-transformers — modelo sugerido: `all-MiniLM-L6-v2`).
  - **LangChain** ou código manual para orquestração (pip install langchain).
  - Para geração: usar o **Claude** (via chat manual, não via API) ou qualquer modelo local via **Ollama** (gratuito).
- Alternativa: se o participante preferir, pode usar outra stack free (FAISS em vez de ChromaDB, Ollama para embeddings locais, etc). O que importa é que funcione e seja gratuito.

**Tarefa:**
1. Usando o **GitHub Copilot**, implemente um pipeline de RAG mínimo com estas etapas:
   - **Ingestão:** Um script que lê os documentos do Anexo A (como texto), divide em chunks (defina a estratégia de chunking e justifique), gera embeddings, e armazena no ChromaDB.
   - **Busca:** Uma função que recebe uma pergunta, gera o embedding da pergunta, busca os N chunks mais similares no ChromaDB, e retorna os chunks com score de similaridade.
   - **Montagem de prompt:** Uma função que recebe os chunks recuperados e a pergunta, e monta o prompt completo (system prompt + chunks + pergunta) pronto para enviar ao LLM.

2. Teste o pipeline com ao menos 5 perguntas do mapa de cobertura do Anexo B. Para cada pergunta, documente: quais chunks foram recuperados, se são os chunks corretos (compare com o gabarito), e o score de similaridade.

3. Usando o **Claude** (chat), cole o prompt montado pelo pipeline e obtenha a resposta. Avalie: está correta? Citou fonte? Respeitou guardrails?

4. Identifique ao menos 2 problemas encontrados (ex: chunk errado recuperado, documento irrelevante no topo, chunking que cortou uma tabela no meio) e proponha correções.

**Entregável:** O código do pipeline (com evidência do Copilot), os resultados dos 5 testes com análise, e as propostas de correção.

**Critérios de avaliação:**
- O pipeline é funcional: ingere, busca e retorna chunks relevantes (não precisa ser perfeito, mas precisa rodar).
- A estratégia de chunking é justificada (não é apenas "512 tokens fixos" sem motivo).
- Os testes usam perguntas realistas do domínio e são comparados com o gabarito do Anexo B.
- Os problemas identificados são reais e as propostas de correção são concretas.
- O participante demonstra entendimento de que RAG é um sistema de engenharia de dados, não apenas chamada de API.

---