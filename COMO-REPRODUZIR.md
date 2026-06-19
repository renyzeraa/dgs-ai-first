# Como reproduzir — Fase 2 Desenvolvedor

Passo a passo para chegar ao mesmo resultado deste projeto, do zero. Tudo local e gratuito.

## Pré-requisitos

- Node.js 20+ (testado em 22) e npm
- Python 3.11+ (testado em 3.12) com `uv`/`uvx` — para o MCP server de git
- git

Instalar `uv` (se ainda não tiver): `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

## Parte A — Exercício 2.2 (rodar os testes da T-01)

É a parte mais rápida de confirmar e não depende de MCP.

```bash
cd 03-repo-novatech-assistant
npm install                 # instala zod, vitest, typescript
npx tsc -p . --noEmit       # deve sair com exit 0 (strict mode, sem erros)
npx vitest run              # deve mostrar 11 passed (11)
```

Para ver a cobertura (validator e errors a 100%):

```bash
npm install -D @vitest/coverage-v8@2
npx vitest run --coverage
```

Resultado esperado: `src/functions/query/validator.ts` e `src/shared/errors.ts` com 100%.

---

## Parte B — Exercício 2.1 (subir os MCP servers e gerar a evidência)

### B.1 Instalar os reference servers

```bash
npm install -g @modelcontextprotocol/server-filesystem @modelcontextprotocol/server-memory
# o server de git roda via uvx (baixa na primeira execução):
uvx mcp-server-git --help
```

### B.2 Conferir o `.mcp/mcp.json`

O arquivo já está em `03-repo-novatech-assistant/.mcp/mcp.json` com os 4 servers e o
least privilege aplicado (filesystem-rw / filesystem-ro / git / memory). Caminhos são
relativos à raiz do repo.

### B.3 Gerar a evidência de execução (cliente MCP incluído)

O cliente `02-evidencias/ex-2.1_mcp_probe.py` faz o handshake JSON-RPC com cada server e
captura as respostas cruas. Ele tem o caminho do repo embutido na constante `REPO` no topo
— **ajuste essa constante** para o caminho absoluto do seu `03-repo-novatech-assistant`
antes de rodar. Depois:

```bash
# do diretório onde está o probe:
python3 ex-2.1_mcp_probe.py all     # roda filesystem + chunk + git + memory
# ou um por vez:
python3 ex-2.1_mcp_probe.py fs       # lista e lê um doc de docs/novatech (+ teste de escopo)
python3 ex-2.1_mcp_probe.py chunk    # recupera o chunk SLA-2024-B (gabarito Anexo B)
python3 ex-2.1_mcp_probe.py git      # git_log + git_status do repo
python3 ex-2.1_mcp_probe.py memory   # cria entidades de linguagem ubíqua e lê o grafo
```

A saída de referência (a que foi capturada aqui) está em `02-evidencias/ex-2.1_mcp-evidence.log`.

### B.4 (opcional) Reproduzir o teste de risco R1 (read-only não nativo)

Para confirmar que o reference filesystem **permite escrita** dentro do escopo (motivo da
mitigação por permissão de SO): chame `write_file` apontando para `data/retrieval-corpus/`.
O arquivo será criado — prova de que o read-only precisa vir do sistema de arquivos, não do
server. (Lembre de apagar o arquivo de teste depois.)

### B.5 Evidência visual no IDE (recomendado para a entrega)

Para o print que o avaliador espera: abra o `03-repo-novatech-assistant` no VS Code com
GitHub Copilot, deixe os servers do `.mcp/mcp.json` ativos, e peça ao agente para (a) ler um
doc de `docs/novatech/`, (b) recuperar um chunk e (c) ler o `git log`. O comportamento é o
mesmo do log capturado (mesmo `mcp.json`).

---

## Parte C — Exercício 2.3 (skills)

São artefatos de documentação, não há o que executar. Os arquivos:

- `03-repo-novatech-assistant/skills/domain/azure-functions-endpoint.md` — a skill completa.
- `01-entregaveis/03_ex-2.3_estrategia-skills.md` — árvore, papéis e critérios de maturidade.

Para "amadurecer" a skill (critério 6): com o repo aberto no Copilot/Claude e a skill no
contexto, peça a geração de um novo endpoint e verifique se o output segue as regras;
documente o que foi ignorado e torne a regra mais prescritiva.

---

## Montar o repositório para o GitHub

Quando for subir (fora desta fase, que é local), a pasta `03-repo-novatech-assistant` é o
repositório de verdade. As pastas `01-entregaveis` e `02-evidencias` são organização da
entrega da trilha — você pode mantê-las num branch de entrega ou numa pasta `docs/entrega/`.

```bash
cd 03-repo-novatech-assistant
git init
git add .
git commit -m "feat: cenário 2 — MCP config, query endpoint T-01, skill azure-functions-endpoint"
```
