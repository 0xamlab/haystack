"""Tab 5 — examples library: every link and install command, in one place.

All package names and install commands are the real published ones:
PyPI (algenta-sdk, algenta-mcp, the eight Python integrations) and npm
(algenta-sdk, algenta-tools, n8n-nodes-algenta). Nothing here is aspirational.
"""

from __future__ import annotations

SDK_REPO = "https://github.com/thyn-ai/algenta-sdk"
INTEGRATIONS_REPO = "https://github.com/thyn-ai/algenta-integrations"
KERNELS_REPO = "https://github.com/thyn-ai/mojo-kernels"
WHEELS_RELEASE = f"{KERNELS_REPO}/releases/tag/arena-wheels-v0.1.0"
SPEED_ARENA = "https://huggingface.co/spaces/thyn-ai/algenta-speed-arena"
GOVERNED_SPACE = "https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls"
MCP_REGISTRY = "https://registry.modelcontextprotocol.io"
MCP_REGISTRY_ENTRY = "io.github.thyn-ai/algenta"
PYPI_MCP = "https://pypi.org/project/algenta-mcp/"
PYPI_SDK = "https://pypi.org/project/algenta-sdk/"
NPM_SDK = "https://www.npmjs.com/package/algenta-sdk"

#: The ten framework integrations (from thyn-ai/algenta-integrations' README).
INTEGRATIONS: list[tuple[str, str, str]] = [
    (
        "LangChain / LangGraph",
        "pip install langchain-algenta",
        "Governed tool list on langchain-mcp-adapters; typed receipts, catchable AlgentaExecutionBlocked.",
    ),
    (
        "LlamaIndex",
        "pip install llamaindex-algenta",
        "Governed FunctionTools with typed ExecutionReceipt outputs and named-gate denials.",
    ),
    (
        "pydantic-ai",
        "pip install pydantic-ai-algenta",
        "Governed WrapperToolset over pydantic-ai's MCPToolset; denials via the native ToolDenied primitive.",
    ),
    (
        "Microsoft Agent Framework",
        "pip install maf-algenta",
        "Governed FunctionTool list with two-layer safety-field scrubbing; typed denials on MiddlewareFailure.",
    ),
    (
        "Haystack",
        "pip install haystack-algenta",
        "Governed toolset on Haystack's MCPToolset plus an Agent after_tool governance hook.",
    ),
    (
        "LiteLLM (MCP Gateway)",
        "pip install litellm-algenta",
        "Config generator, linter and per-profile YAML on LiteLLM's real allowed_tools enforcement.",
    ),
    (
        "Ray Serve / KubeRay",
        "pip install ray-serve-algenta",
        "Byte-transparent multi-replica reverse proxy for the engine's /mcp surface; RayService manifest.",
    ),
    (
        "vLLM / OpenAI-compatible",
        "pip install vllm-algenta",
        "Thin helpers pointing the standard openai client at the engine's /v1/chat/completions.",
    ),
    (
        "Vercel AI SDK (ai)",
        "npm install algenta-tools",
        "Governed ToolSet factory with typed ExecutionReceipt results and ExecutionBlockedError denials.",
    ),
    (
        "n8n",
        "npm install n8n-nodes-algenta",
        "Community node exposing the governed tools as typed n8n operations, profile-enforced client-side.",
    ),
]

SDK_QUICKSTART_PY = """\
pip install algenta-sdk       # Python 3.10+
npm install algenta-sdk       # TypeScript / JavaScript, Node.js 18+
"""

SDK_QUICKSTART_CODE = """\
from algenta import GovernedAgent          # receipts on every tool call
agent = GovernedAgent(profile="observe")   # read-only by default
result = agent.call("query_data", {"source": "orders", "intent": "gross revenue"})
print(result.receipt)                      # signed allow/deny evidence
"""

MCP_CLAUDE_DESKTOP = """\
{
  "mcpServers": {
    "algenta": {
      "command": "algenta-mcp",
      "env": {
        "ALGENTA_API_KEY": "<YOUR_ALGENTA_API_KEY>",
        "ALGENTA_BASE_URL": "https://api.algenta.ai"
      }
    }
  }
}
"""

MCP_CODEX_TOML = """\
[mcp_servers.algenta]
command = "algenta-mcp"

[mcp_servers.algenta.env]
ALGENTA_API_KEY = "<YOUR_ALGENTA_API_KEY>"
ALGENTA_BASE_URL = "https://api.algenta.ai"
"""


def integrations_html() -> str:
    rows = "".join(
        f"<tr><td><b>{name}</b></td><td><code>{install}</code></td><td>{desc}</td></tr>"
        for name, install, desc in INTEGRATIONS
    )
    return f"""
<div class="kcard" style="overflow-x:auto">
<h3 style="margin-top:0">Ten framework integrations — one governed tool contract</h3>
<p>Every package maps the same engine surface (profiles <code>observe / govern / execute / full</code>,
typed receipts, named-gate denials) onto one framework's conventions. All ten are published
with their own test suites; the contract-parity test in each repo asserts the exposed tool
sets match <code>contracts/integration-tool-contract.json</code> exactly.</p>
<table class="lane-table">
<thead><tr><th>framework</th><th>install</th><th>what it gives you</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<p>Source + per-framework quickstarts:
<a href="{INTEGRATIONS_REPO}">github.com/thyn-ai/algenta-integrations</a></p>
</div>
"""


def examples_html() -> str:
    cards = [
        (
            "algenta-sdk — the Python & TypeScript client",
            "Governed data queries, simulations, decision memory with execution receipts, agent runs with approvals.",
            SDK_QUICKSTART_PY.strip(),
            f'<a href="{SDK_REPO}">github.com/thyn-ai/algenta-sdk</a> · <a href="{PYPI_SDK}">PyPI</a> · <a href="{NPM_SDK}">npm</a>',
        ),
        (
            "algenta-mcp — the MCP server",
            f"140 tools across 13 categories over stdio or HTTP; official Registry entry <code>{MCP_REGISTRY_ENTRY}</code>.",
            "pipx install algenta-mcp   # or: pip install algenta-mcp",
            f'<a href="{PYPI_MCP}">PyPI</a> · <a href="{MCP_REGISTRY}">MCP Registry</a>',
        ),
        (
            "mojo-kernels — the acceleration factory",
            "35 clean-room Mojo kernels as drop-in accelerators for popular Python libraries, "
            "bit-exact parity, pure-Python fallbacks. The repo's quickstart.py gets a first kernel running in minutes.",
            "pip install https://github.com/thyn-ai/mojo-kernels/releases/download/arena-wheels-v0.1.0/bm25_mojo-0.1.2-py3-none-manylinux_2_35_x86_64.whl",
            f'<a href="{KERNELS_REPO}">github.com/thyn-ai/mojo-kernels</a> · <a href="{WHEELS_RELEASE}">wheels releases</a>',
        ),
        (
            "⚡ Algenta Speed Arena",
            "The sister Space: 13 benchmark duels of native Mojo kernels vs incumbent libraries, "
            "measured live on HF cpu-basic — gate-first, seeded, median-of-5.",
            "",
            f'<a href="{SPEED_ARENA}">thyn-ai/algenta-speed-arena</a>',
        ),
        (
            "🛡️ Governed tool calls",
            "The sister Space: approve/deny a governed tool call and inspect the execution receipt — "
            "the same wire shapes tab 3 of this Space simulates.",
            "",
            f'<a href="{GOVERNED_SPACE}">thyn-ai/algenta-governed-tool-calls</a>',
        ),
        (
            "🏠 Self-host the engine — free",
            "The Algenta decision engine is free to self-host under the Algenta Community license: "
            "your data, your deployment, the same governed tool surface every demo here uses. "
            "The engine is proprietary and never vendored; SDKs, integrations and kernels are Apache-2.0.",
            'AlgentaClient(base_url="http://localhost:8000")  # point the SDK at your own deployment',
            f'<a href="{SDK_REPO}">get started</a>',
        ),
    ]
    body = "".join(
        f"""
<div class="kcard">
  <div class="kname">{title}</div>
  <p>{desc}</p>
  {f'<pre style="font-size:12px;background:#f8fafc;padding:8px;border-radius:8px;overflow-x:auto"><code>{code}</code></pre>' if code else ""}
  <div class="klinks">{links}</div>
</div>"""
        for title, desc, code, links in cards
    )
    return f'<div class="kgrid">{body}</div>'
