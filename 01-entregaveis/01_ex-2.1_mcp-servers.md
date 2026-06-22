# Exercício 2.1 — Configuração e uso real de MCP servers

**Papel:** Desenvolvedor · **Fase:** 2 (Estruturação) · **Projeto:** NovaTech Assistant

Este documento entrega os quatro itens pedidos: (1) o mapeamento necessidade → server
com least privilege justificado, (2) o `.mcp/mcp.json` final, (3) evidência de execução
real dos servers, e (4) a análise de riscos de segurança com mitigação.

---

## 1. Mapeamento necessidade → server (least privilege)

Cada necessidade do projeto é atendida por um *reference server* local e gratuito. O
critério de least privilege é: **cada server recebe o menor conjunto de pastas que ainda
permite cumprir sua função**, e as fontes de negócio (documentação e corpus) são isoladas
das pastas de código.

| # | Necessidade do projeto | Server | Expõe (primitivas) | Escopo concedido | Quem consome |
|---|---|---|---|---|---|
| 1 | Ler/editar código, specs e skills | `filesystem-rw` | Tools (read + **write**) | `./src ./specs ./skills` | Dev (Claude/Copilot) gerando código e tasks |
| 2 | Ler documentação de negócio da NovaTech (era Confluence) | `filesystem-ro` | Tools (read; write **deve ser bloqueada por SO** — ver §4) | `./docs/novatech` | Agente montando contexto/grounding |
| 3 | "Recuperar" chunks do RAG (era Azure AI Search) | `filesystem-ro` | Tools (read) | `./data/retrieval-corpus` | Agente simulando retrieval |
| 4 | Histórico, diff e branches do repo (era GitHub) | `git` | Tools (log, status, diff, branch, …) | repositório local (`.`) | Dev/TL inspecionando histórico |
| 5 | Memória persistente de decisões e linguagem ubíqua | `memory` | Tools (grafo de entidades/relações) | grafo local em memória/arquivo | Todos os agentes do projeto |
| 6 | Aprender as primitivas de MCP (tools/resources/prompts) | `everything` | Tools + Resources + Prompts (demo) | — (sem acesso a dados do projeto) | Aprendizado da equipe |

**Por que separar `filesystem-rw` e `filesystem-ro`?** O reference `server-filesystem`
aplica escopo por pasta, mas **não tem um modo read-only que bloqueie escrita** (ver §4,
risco R1 — verificado empiricamente). Separar em dois servers torna a *intenção* de
least privilege explícita e auditável no próprio `mcp.json`: tudo que está sob
`filesystem-ro` é, por contrato do projeto, somente-leitura, e a imposição técnica é feita
por permissão de sistema de arquivos. Misturar código e docs num único server amplo seria
o anti-padrão que o exercício pede para evitar.

**`everything` não recebe nenhuma pasta do projeto** de propósito: seu papel é didático
(explorar tools/resources/prompts do protocolo). Dar a ele acesso a dados reais seria
privilégio sem necessidade.

---

## 2. `.mcp/mcp.json` final

Arquivo versionado em `.mcp/mcp.json` (preenchendo o scaffold vazio `{ "mcpServers": {} }`
do starter repo). Caminhos relativos à raiz do repositório.

```json
{
  "mcpServers": {
    "filesystem-rw": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./src", "./specs", "./skills"]
    },
    "filesystem-ro": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./docs/novatech", "./data/retrieval-corpus"]
    },
    "git": {
      "command": "uvx",
      "args": ["mcp-server-git", "--repository", "."]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    }
  }
}
```

**Justificativa de escopo mínimo, server a server:**

- **`filesystem-rw` → `./src ./specs ./skills`** — são as três pastas onde o Dev
  legitimamente *escreve* nesta fase (código, tasks SDD, skills). Não inclui `./docs`,
  `./infra`, `./prompts` nem a raiz: o agente não precisa alterá-las para implementar uma
  task, então elas ficam fora. Em particular, manter a **raiz fora do escopo** evita
  acesso a `AGENTS.md`, `package.json`, `.git/`, `.env` (ver evidência §3, teste de borda).
- **`filesystem-ro` → `./docs/novatech ./data/retrieval-corpus`** — exatamente as duas
  fontes de leitura que o exercício define. Nada além. Tratadas como read-only por
  contrato; imposição técnica em §4/R1.
- **`git` → `.`** — o server precisa enxergar o repositório inteiro para `git_log`/`diff`,
  mas só expõe operações de Git, não o filesystem bruto. As operações usadas no fluxo são
  de leitura (log/status/diff); commit/branch existem mas passam pelos validation gates.
- **`memory`** — não recebe pasta; opera sobre seu próprio grafo. Privilégio mínimo por
  construção.
- **`everything` foi deliberadamente omitido do `mcp.json` de trabalho** e fica registrado
  apenas como referência de aprendizado: ligá-lo no projeto seria superfície de ataque sem
  ganho operacional. (Pode ser adicionado num `mcp.local.json` individual do dev, fora do
  versionamento.)

`mcp-server-git` é instalado via `uvx` (Python); a versão arquivada do server de GitHub no
upstream exigiria conta/token externos — por isso o repositório é tratado **localmente**
com `filesystem` + `git`, sem nenhum serviço pago.

---

## 3. Evidência de execução real

Ambiente: Linux, Node 22, Python 3.12, Git 2.43. Cliente: `mcp_probe.py` falando
JSON-RPC 2.0 sobre stdio, `protocolVersion 2024-11-05`. Log cru completo em
`docs/mcp/mcp-evidence.log`. Versões observadas: `server-filesystem 2026.1.14`,
`server-memory 2026.1.26`, `mcp-server-git 1.28.0`.

### (a) Listar e ler um documento de `docs/novatech/`

Handshake → `tools/list` → `list_directory` → `read_text_file`. Saída crua (resumida):

```
initialize -> serverInfo: { "name": "secure-filesystem-server", "version": "0.2.0" }

list_directory docs/novatech:
  [FILE] FAQ-atendimento.md
  [FILE] POL-001-politica-devolucao.md
  [FILE] PROC-042-frete-especial-v1.md
  [FILE] PROC-042-v2-frete-especial-revisado.md
  [FILE] README.md
  [FILE] SLA-2024-tabela-sla-clientes.md

read_text_file SLA-2024-tabela-sla-clientes.md (início):
  # SLA-2024 — Tabela de SLA por Tipo de Cliente
  Versão: 2024.1 · Última atualização: 02/01/2024
  Classificação: Documento contratual ...
```

**Teste de borda (prova do least privilege):** com o `filesystem-rw` ativo (escopo
`src/specs/skills`), pedir para ler `AGENTS.md` (na raiz, fora do escopo) retorna:

```
isError: true
"Access denied - path outside allowed directories:
 .../AGENTS.md not in .../src, .../specs, .../skills, .../docs/novatech, .../data/retrieval-corpus"
```

Ou seja, o escopo não é decorativo — o server **recusa** acesso fora das pastas concedidas.

### (b) Recuperar um chunk relevante de `data/retrieval-corpus/`

Pergunta do domínio: **"Qual o SLA do cliente Gold?"** — gabarito do Anexo B: chunk
**SLA-2024-B**. Via `filesystem-ro`, lendo o corpus e recuperando o trecho:

```
Chunk recuperado:
  **Chunk SLA-2024-B** — Seção 2: Tabela de SLAs (chamados gerais)
  > SLAs para chamados gerais — Gold: resposta em até 2h úteis, resolução em até 24h úteis.
    Silver: resposta em até 4h úteis, resolução em até 48h úteis.
    Standard: resposta em até 8h úteis, resolução em até 72h úteis.
```

Bate com o gabarito do Anexo B. (Nota técnica: o `search_files` do reference server casa
por **nome de arquivo**, não por conteúdo — por isso a recuperação por conteúdo é feita
lendo o arquivo e filtrando o trecho, que é o comportamento equivalente ao que o Azure AI
Search faria por similaridade.)

### (c) Ler o histórico do repositório via `git`

Handshake → `git_log` → `git_status`. Saída crua:

```
initialize -> serverInfo: { "name": "mcp-git", "version": "1.28.0" }
tools: git_status, git_diff_unstaged, git_diff_staged, git_diff, git_commit,
       git_add, git_reset, git_log, git_create_branch, git_checkout, git_show, git_branch

git_log:
  Commit: bbdd03aeecd7e349a2bfc93849e0552a0b766ac6
  Author: Trilha AI First <trilha@db1.local>
  Date:   2026-06-09 18:13:30+00:00
  Message: chore: starter repo (Anexo D) — estrutura + dados semeados dos Anexos A e B

git_status:
  On branch master
  nothing to commit, working tree clean
```

### (d) Bônus — `memory` persistindo linguagem ubíqua

Para mostrar a primitiva de memória, foram criadas duas entidades e lidas de volta:

```
create_entities -> "carga perigosa" (linguagem-ubiqua):
   - Sempre significa classes 1-6 da ANTT (Res. 5.947/2021)
   - NÃO elegível para devolução pelo processo padrão (POL-001-B)
create_entities -> "ADR-0002" (decisao):
   - Context budget: ~4K system + ~8K chunks (5 chunks ~1.5K)

read_graph -> retorna as 2 entidades acima (relations: [])
```

Isso demonstra o uso pretendido do `memory`: fixar que **"carga perigosa" = classes 1–6
da ANTT**, evitando que o agente confunda regra com exceção (armadilha 4 do Anexo B).

---

## 4. Análise de riscos de segurança (específicos do setup local)

### R1 — "Read-only" não é garantido pelo server: escrita sem revisão na fonte de negócio

**Risco.** O reference `server-filesystem` **não tem modo read-only que bloqueie escrita**.
As únicas referências a `readOnly` no código são `readOnlyHint` — anotações *descritivas*
por tool (uma dica para o cliente), não um guard. As tools `write_file`, `edit_file`,
`move_file` e `create_directory` continuam expostas e funcionais dentro do escopo. Isto foi
**verificado empiricamente**: com o escopo de `filesystem-ro` (`docs/novatech` +
`data/retrieval-corpus`), uma chamada `write_file` criou o arquivo
`data/retrieval-corpus/_attack.md` com sucesso (`"Successfully wrote to ..."`). Um agente
comprometido por prompt injection (ex.: um doc da NovaTech com instrução embutida) poderia
**alterar o corpus de RAG** — a base que alimenta as respostas — sem passar por code review.

**Mitigação (acionável).**
1. Impor read-only **fora do server**, no sistema de arquivos: `chmod -R a-w docs/novatech
   data/retrieval-corpus` (ou montar como read-only), de modo que a escrita falhe no nível
   do SO mesmo que a tool seja chamada.
2. Rodar o `filesystem-ro` sob um **usuário de SO sem permissão de escrita** nessas pastas.
3. Versionar o corpus no Git e tratar qualquer modificação como mudança revisável: um
   `git diff` inesperado em `data/retrieval-corpus/` no validation gate de merge sinaliza
   adulteração.

### R2 — Escopo amplo demais expõe segredos (`.env`, `.git`, credenciais)

**Risco.** Se, por conveniência, o `filesystem` fosse apontado para a raiz do repositório
(`.`) em vez das subpastas, ele exporia `.env` (que o `.gitignore` já mantém fora do
versionamento justamente por conter segredos), o diretório `.git/` inteiro, e arquivos de
configuração com chaves. Como o agente lê tudo que está no escopo, um prompt injection
poderia exfiltrar segredos pedindo "leia e me mostre o `.env`".

**Mitigação (acionável).**
1. **Nunca** apontar o `filesystem` para a raiz — usar apenas as subpastas necessárias
   (foi o que o `mcp.json` faz). O teste de borda em §3(a) prova que `AGENTS.md` na raiz já
   fica inacessível com este escopo.
2. Garantir que segredos vivem **fora** de qualquer pasta concedida (ex.: `.env` na raiz,
   nunca em `src/`), e manter `.env` no `.gitignore` (já está).
3. Auditar periodicamente o escopo via `list_allowed_directories` (tool nativa) e revisar
   qualquer ampliação de escopo no `mcp.json` como mudança que passa pelo gate do Tech Lead.

### R3 (adicional) — Servers via `npx -y`/`uvx` baixam código na hora (supply chain)

**Risco.** `npx -y` e `uvx` resolvem e executam a versão mais recente do pacote no momento
da subida. Um pacote comprometido no registro executaria com as permissões do dev. Além
disso, a versão pode mudar entre execuções, quebrando reprodutibilidade.

**Mitigação.** Fixar versões exatas no `mcp.json`
(`@modelcontextprotocol/server-filesystem@2026.1.14`), revisar o lockfile, e preferir
instalação auditada (`npm ci` de um manifesto fixo) a `-y` cego em ambiente de equipe.

---

## Arquivos desta entrega

- `.mcp/mcp.json` — configuração final (4 servers, least privilege).
- `docs/mcp/ex-2.1-mcp-servers.md` — este documento.
- `docs/mcp/mcp-evidence.log` — captura crua das respostas JSON-RPC dos 4 servers.
- `docs/mcp/mcp_probe.py` — cliente MCP usado para exercitar os servers (reproduzível).
