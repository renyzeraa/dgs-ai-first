#!/usr/bin/env python3
"""
Cliente MCP mínimo (stdio + JSON-RPC 2.0) para exercitar reference servers
e capturar respostas CRUAS. Usado como evidência de execução real do Ex 2.1.

Uso:
    python3 mcp_probe.py <nome-do-cenario>

Cada cenário sobe um server via stdio, faz o handshake MCP
(initialize -> notifications/initialized), lista tools e chama uma tool real.
"""
import json
import subprocess
import sys
import threading
import time

import os
# Caminho do repositório novatech-assistant.
# Ajuste se necessário: por padrão tenta achar o repo a partir da env var
# NOVATECH_REPO, senão usa o diretório atual.
REPO = os.environ.get("NOVATECH_REPO", os.getcwd())
# Se rodar de dentro de 02-evidencias/, o repo está em ../03-repo-novatech-assistant
_candidate = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                          "..", "03-repo-novatech-assistant"))
if os.path.isdir(os.path.join(_candidate, ".mcp")):
    REPO = _candidate


class MCPClient:
    def __init__(self, cmd, env=None):
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        self._id = 0
        # drena stderr em background (servers logam banner ali)
        self.stderr_lines = []
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _drain_stderr(self):
        for line in self.proc.stderr:
            self.stderr_lines.append(line.rstrip())

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _read(self, timeout=15):
        # le uma linha JSON-RPC de stdout, com timeout
        result = {}

        def reader():
            line = self.proc.stdout.readline()
            result["line"] = line

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        t.join(timeout)
        if "line" not in result or not result["line"]:
            return None
        return json.loads(result["line"])

    def request(self, method, params=None):
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method,
                    "params": params or {}})
        # alguns servers emitem notificações antes da resposta; pega a resposta com nosso id
        for _ in range(10):
            msg = self._read()
            if msg is None:
                return None
            if msg.get("id") == self._id:
                return msg
        return None

    def notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def initialize(self):
        resp = self.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "novatech-mcp-probe", "version": "0.1.0"},
        })
        self.notify("notifications/initialized")
        return resp

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def show(title, obj):
    print(f"\n--- {title} ---")
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def scenario_filesystem():
    print("=" * 70)
    print("SERVER: filesystem  (escopo least-privilege aplicado nos args)")
    print("=" * 70)
    cmd = [
        "npx", "-y", "@modelcontextprotocol/server-filesystem",
        f"{REPO}/src", f"{REPO}/specs", f"{REPO}/skills",
        f"{REPO}/docs/novatech", f"{REPO}/data/retrieval-corpus",
    ]
    c = MCPClient(cmd)
    init = c.initialize()
    show("initialize -> serverInfo", init.get("result", {}).get("serverInfo", init))

    tools = c.request("tools/list")
    names = [t["name"] for t in tools["result"]["tools"]]
    print("\nTools expostas:", names)

    # (a) listar docs/novatech
    ls = c.request("tools/call", {
        "name": "list_directory",
        "arguments": {"path": f"{REPO}/docs/novatech"},
    })
    show("tools/call list_directory docs/novatech", ls["result"]["content"][0]["text"])

    # (a) ler um documento de negocio
    rd = c.request("tools/call", {
        "name": "read_text_file",
        "arguments": {"path": f"{REPO}/docs/novatech/SLA-2024-tabela-sla-clientes.md"},
    })
    txt = rd["result"]["content"][0]["text"]
    show("tools/call read_text_file SLA-2024 (primeiras linhas)",
         "\n".join(txt.splitlines()[:12]))

    # teste de least-privilege: tentar ler fora do escopo (raiz do repo)
    outside = c.request("tools/call", {
        "name": "read_text_file",
        "arguments": {"path": f"{REPO}/AGENTS.md"},
    })
    show("tools/call read_text_file AGENTS.md (FORA do escopo -> deve falhar)",
         outside.get("result", outside.get("error")))

    c.close()


def scenario_filesystem_chunk():
    print("\n" + "=" * 70)
    print("SERVER: filesystem  ->  RECUPERAR CHUNK (gabarito Anexo B)")
    print("=" * 70)
    cmd = [
        "npx", "-y", "@modelcontextprotocol/server-filesystem",
        f"{REPO}/data/retrieval-corpus",
    ]
    c = MCPClient(cmd)
    c.initialize()
    # pergunta do dominio: "Qual o SLA do cliente Gold?" -> gabarito Anexo B: SLA-2024-B
    sr = c.request("tools/call", {
        "name": "search_files",
        "arguments": {"path": f"{REPO}/data/retrieval-corpus", "pattern": "Gold"},
    })
    show("tools/call search_files pattern=Gold", sr["result"]["content"][0]["text"])

    rd = c.request("tools/call", {
        "name": "read_text_file",
        "arguments": {"path": f"{REPO}/data/retrieval-corpus/chunks-novatech.md"},
    })
    full = rd["result"]["content"][0]["text"]
    # extrai o bloco do chunk SLA-2024-B (o gabarito p/ pergunta Gold)
    lines = full.splitlines()
    grabbed = []
    capture = False
    for ln in lines:
        if "SLA-2024-B" in ln:
            capture = True
        elif capture and ln.strip().startswith("**Chunk") and "SLA-2024-B" not in ln:
            break
        if capture:
            grabbed.append(ln)
    show("Chunk recuperado p/ 'Qual o SLA do cliente Gold?' (esperado: SLA-2024-B)",
         "\n".join(grabbed[:4]))
    c.close()


def scenario_git():
    print("\n" + "=" * 70)
    print("SERVER: git  (repositorio local, read-only de historico)")
    print("=" * 70)
    cmd = ["uvx", "mcp-server-git", "--repository", REPO]
    c = MCPClient(cmd)
    init = c.initialize()
    show("initialize -> serverInfo", init.get("result", {}).get("serverInfo", init))
    tools = c.request("tools/list")
    print("\nTools expostas:", [t["name"] for t in tools["result"]["tools"]])

    log = c.request("tools/call", {
        "name": "git_log",
        "arguments": {"repo_path": REPO, "max_count": 5},
    })
    show("tools/call git_log", log["result"]["content"][0]["text"])

    status = c.request("tools/call", {
        "name": "git_status",
        "arguments": {"repo_path": REPO},
    })
    show("tools/call git_status", status["result"]["content"][0]["text"])
    c.close()


def scenario_memory():
    print("\n" + "=" * 70)
    print("SERVER: memory  (grafo persistente de decisoes / linguagem ubiqua)")
    print("=" * 70)
    cmd = ["npx", "-y", "@modelcontextprotocol/server-memory"]
    c = MCPClient(cmd)
    c.initialize()
    tools = c.request("tools/list")
    print("\nTools expostas:", [t["name"] for t in tools["result"]["tools"]])

    create = c.request("tools/call", {
        "name": "create_entities",
        "arguments": {"entities": [
            {"name": "carga perigosa", "entityType": "linguagem-ubiqua",
             "observations": ["Sempre significa classes 1-6 da ANTT (Res. 5.947/2021)",
                              "NAO elegivel para devolucao pelo processo padrao (POL-001-B)"]},
            {"name": "ADR-0002", "entityType": "decisao",
             "observations": ["Context budget: ~4K system + ~8K chunks (5 chunks ~1.5K)"]},
        ]},
    })
    show("tools/call create_entities", create.get("result", create.get("error")))

    graph = c.request("tools/call", {"name": "read_graph", "arguments": {}})
    show("tools/call read_graph", graph["result"]["content"][0]["text"])
    c.close()


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("fs", "all"):
        scenario_filesystem()
    if which in ("chunk", "all"):
        scenario_filesystem_chunk()
    if which in ("git", "all"):
        scenario_git()
    if which in ("memory", "all"):
        scenario_memory()
