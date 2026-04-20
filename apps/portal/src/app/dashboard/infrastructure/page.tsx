"use client";
import { useEffect, useState } from "react";
import {
  getInfrastructure,
  getDeployment,
  listDeploymentRegions,
  createDeployment,
  deleteDeployment,
  InfrastructureResponse,
  NodeInfo,
  DeploymentInfo,
  CloudProvider,
} from "@/lib/api";

// ─── Module-level cache ───────────────────────────────────────────────────────
// Prevents re-fetching on every Next.js page navigation (component re-mount).
let _infraCache: InfrastructureResponse | null = null;
let _deploymentCache: DeploymentInfo | null | undefined = undefined;
let _cacheTime = 0;
const CACHE_TTL_MS = 60_000; // 1 minute

const topbar: React.CSSProperties = {
  height: "var(--ag-topbar-height)",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "0 24px",
  background:
    "linear-gradient(180deg, rgba(255,255,255,0.015), rgba(255,255,255,0)), var(--ag-bg-surface-1)",
  borderBottom: "1px solid var(--ag-border-default)",
  position: "sticky",
  top: 0,
  zIndex: 40,
};

// ─── Connect tab definitions ──────────────────────────────────────────────────
// icon = full FontAwesome class string (fa-solid / fa-brands / etc.)
const CONNECT_TABS = [
  { id: "rest", label: "REST API", icon: "fa-solid fa-code" },
  { id: "python", label: "Python SDK", icon: "fa-brands fa-python" },
  { id: "typescript", label: "TypeScript", icon: "fa-solid fa-file-code" },
  { id: "cli", label: "CLI", icon: "fa-solid fa-terminal" },
  { id: "mcp", label: "MCP", icon: "fa-solid fa-robot" },
  { id: "langchain", label: "LangChain", icon: "fa-solid fa-link" },
  { id: "langgraph", label: "LangGraph", icon: "fa-solid fa-share-nodes" },
  { id: "n8n", label: "n8n", icon: "fa-solid fa-circle-nodes" },
  { id: "zapier", label: "Zapier", icon: "fa-solid fa-bolt" },
  { id: "make", label: "Make", icon: "fa-solid fa-gear" },
] as const;

type ConnectTabId = (typeof CONNECT_TABS)[number]["id"];

// ─── Dynamic snippet builder ──────────────────────────────────────────────────
// All YOUR_API_KEY / base URL placeholders are replaced with the user's real
// values at render time. If the user has no key stored yet, the placeholder
// text is shown so they know what to put there.
function buildSnippets(
  apiKey: string,
  apiBase: string,
): Record<ConnectTabId, { lang: string; code: string; note?: string }> {
  const key = apiKey || "YOUR_API_KEY";
  const base = apiBase.replace(/\/$/, "");

  return {
    rest: {
      lang: "bash",
      code: `curl -X POST ${base}/v1/simulate \\
  -H "Authorization: Bearer ${key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "mode": "auto",
    "objective": "maximize",
    "n_simulations": 10000,
    "variables": [
      {"name": "revenue", "low": 80000, "mode": 100000, "high": 130000},
      {"name": "costs",   "low": 40000, "mode":  55000, "high":  70000}
    ]
  }'`,
      note: apiKey
        ? "Using your active API key. The key is stored in your browser's localStorage."
        : "No API key found. Go to API Keys → New Key, then come back — the snippet will update automatically.",
    },
    python: {
      lang: "python",
      code: `pip install algenta-decision-engine

from decision_engine import DecisionEngineClient

client = DecisionEngineClient(
    api_key="${key}",
    base_url="${base}",  # remove for default cloud endpoint
)

result = client.simulate(
    mode="auto",
    objective="maximize",
    n_simulations=10_000,
    variables=[
        {"name": "revenue", "low": 80_000, "mode": 100_000, "high": 130_000},
        {"name": "costs",   "low": 40_000, "mode":  55_000, "high":  70_000},
    ],
)
print(result.recommended_action)
print(result.metrics.mean)`,
      note: "Requires Python 3.10+.",
    },
    typescript: {
      lang: "typescript",
      code: `npm install @algenta/decision-engine

import { DecisionEngineClient } from "@algenta/decision-engine";

const client = new DecisionEngineClient({
  apiKey: "${key}",
  baseUrl: "${base}",  // remove for default cloud endpoint
});

const result = await client.simulate({
  mode: "auto",
  objective: "maximize",
  nSimulations: 10_000,
  variables: [
    { name: "revenue", low: 80_000, mode: 100_000, high: 130_000 },
    { name: "costs",   low: 40_000, mode:  55_000, high:  70_000 },
  ],
});
console.log(result.recommended_action, result.metrics.mean);`,
      note: "Requires Node 18+.",
    },
    cli: {
      lang: "bash",
      code: `pip install algenta-decision-engine

export ALGENTA_API_KEY=${key}
export ALGENTA_API_BASE_URL=${base}

# Simulate
de simulate \\
  --mode auto \\
  --objective maximize \\
  --variable revenue:triangular:80000:100000:130000 \\
  --variable costs:triangular:40000:55000:70000 \\
  --n 10000

# List recent runs
de runs list --limit 20

# Analytics summary
de analytics --days 30`,
      note: "de is the Algenta CLI bundled with the Python SDK.",
    },
    mcp: {
      lang: "bash",
      code: `# ── 1. Start the MCP server ────────────────────────────────────────────
ALGENTA_API_KEY=${key} \\
ALGENTA_API_BASE_URL=${base} \\
  python -m apps.mcp_server.server --mode http
# → SSE endpoint: http://localhost:8001/sse

# ── 2. stdio config — paste into your AI host's MCP config file ────────
# Hosts: Claude Desktop · Cursor · Zed · Windsurf · VS Code Cline/Continue
#        Goose · Jan · any stdio-compatible MCP client
#
#   Claude Desktop  → ~/Library/Application Support/Claude/claude_desktop_config.json
#   Cursor          → ~/.cursor/mcp.json
#   Zed             → ~/.config/zed/settings.json  (context_servers key)
#   Windsurf        → ~/.codeium/windsurf/mcp_config.json
#   VS Code Cline   → .vscode/mcp.json
#
# {
#   "mcpServers": {
#     "algenta": {
#       "command": "python",
#       "args": ["-m", "apps.mcp_server.server", "--mode", "stdio"],
#       "env": {
#         "ALGENTA_API_KEY": "${key}",
#         "ALGENTA_API_BASE_URL": "${base}"
#       }
#     }
#   }
# }

# ── 3. SSE / HTTP — OpenWebUI · LibreChat · Continue · Cline HTTP ──────
# URL:    http://localhost:8001/sse
# Header: Authorization: Bearer ${key}

# ── 4. MCP TypeScript SDK ───────────────────────────────────────────────
# import { Client } from "@modelcontextprotocol/sdk/client/index.js";
# import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
# const c = new Client({ name: "my-app", version: "1.0" }, { capabilities: {} });
# await c.connect(new SSEClientTransport(new URL("http://localhost:8001/sse")));
# await c.callTool({ name: "simulate", arguments: { mode: "auto", n_simulations: 10000, ... } });`,
      note: "Compatible with any MCP host: Claude Desktop, Cursor, Zed, Windsurf, VS Code (Cline/Continue/Copilot), OpenWebUI, LibreChat, Goose, Jan, or custom apps via the MCP SDK.",
    },
    langchain: {
      lang: "python",
      code: `pip install langchain-core algenta-decision-engine

import os, json, urllib.request
from langchain_core.tools import tool

os.environ["DE_API_KEY"]      = "${key}"
os.environ["DE_BASE_URL"]     = "${base}"

def _api(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"${base}{path}", data=data,
        headers={"Authorization": f"Bearer ${key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

@tool
def simulate_decision(variables: dict, objective: str = "maximize", runs: int = 10000) -> str:
    """Run a Monte Carlo simulation and return a recommended action with confidence."""
    result = _api("/v1/simulate", {
        "mode": "auto", "objective": objective,
        "n_simulations": runs, "variables": [
            {"name": k, **v} for k, v in variables.items()
        ],
    })
    return json.dumps({
        "recommended_action": result.get("recommended_action"),
        "confidence":         result.get("confidence"),
        "expected_value":     result.get("metrics", {}).get("mean"),
        "p5_downside":        result.get("percentiles", {}).get("p5"),
        "p95_upside":         result.get("percentiles", {}).get("p95"),
    }, indent=2)

@tool
def recommend_action(actions: list[dict], runs: int = 10000) -> str:
    """Compare named options and return a ranked recommendation."""
    result = _api("/v1/recommend", {"actions": [
        {"name": a["name"], "request": {
            "mode": "auto", "objective": a.get("objective", "maximize"),
            "n_simulations": runs,
            "variables": [{"name": k, **v} for k, v in a.get("variables", {}).items()],
        }} for a in actions
    ]})
    return json.dumps({
        "recommended_action": result.get("recommended_action"),
        "ranking": result.get("action_results", []),
    }, indent=2)

# Use these tools directly or bind to any LangChain-compatible LLM
tools = [simulate_decision, recommend_action]`,
      note: "Tools are @tool decorated — compatible with LangChain, LangGraph, OpenAI function-calling, and any framework that accepts callable tools.",
    },
    langgraph: {
      lang: "python",
      code: `pip install langgraph langchain-openai algenta-decision-engine
# (or langchain-anthropic / langchain-google-genai — swap out the LLM)

import os
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
# from my_tools import simulate_decision, recommend_action  # see LangChain tab

os.environ["DE_API_KEY"]      = "${key}"
os.environ["DE_BASE_URL"]     = "${base}"
os.environ["OPENAI_API_KEY"]  = "sk-..."

llm   = ChatOpenAI(model="gpt-4o-mini")
agent = create_react_agent(llm, tools=[simulate_decision, recommend_action])

# Run the agent
result = agent.invoke({"messages": [{
    "role": "user",
    "content": (
        "We are deciding between Product A (revenue $80k–$200k, cost $40k–$90k) "
        "and Product B (revenue $50k–$300k, cost $60k–$120k). "
        "Which has better expected value? Use the decision simulation tools."
    ),
}]})
print(result["messages"][-1].content)

# ── Streaming ─────────────────────────────────────────────────────────
for chunk in agent.stream({"messages": [{"role": "user", "content": "..."}]}):
    print(chunk)

# ── Custom graph with decision node ───────────────────────────────────
from langgraph.graph import StateGraph, MessagesState
from langchain_core.messages import HumanMessage

def decision_node(state: MessagesState):
    return {"messages": [simulate_decision.invoke({
        "variables": {"revenue": {"low": 80000, "high": 200000}},
        "objective": "maximize",
    })]}

graph = StateGraph(MessagesState)
graph.add_node("decide", decision_node)
graph.set_entry_point("decide")
app = graph.compile()
print(app.invoke({"messages": [HumanMessage(content="run")]})["messages"][-1])`,
      note: "Full source at examples/langgraph/decision_tool.py — swap ChatOpenAI for any LangChain-compatible LLM (Anthropic, Google, Mistral, Ollama, etc.).",
    },
    n8n: {
      lang: "json",
      code: `// n8n — HTTP Request node
// Method: POST
// URL: ${base}/v1/simulate
// Headers: Authorization: Bearer ${key}
// Body (JSON):
{
  "mode": "auto",
  "objective": "maximize",
  "n_simulations": 10000,
  "variables": [
    { "name": "revenue", "low": 80000, "mode": 100000, "high": 130000 }
  ]
}

// Map response fields in a Set node:
// recommended_action → {{ $json.recommended_action }}
// expected_value     → {{ $json.metrics.mean }}
// p95_upside         → {{ $json.percentiles.p95 }}

// Import the ready-made workflow:
// examples/n8n/workflow_simulate.json`,
      note: "Import examples/n8n/workflow_simulate.json into n8n for a complete Webhook → Simulate → Branch workflow.",
    },
    zapier: {
      lang: "yaml",
      code: `# Zapier — Webhooks by Zapier (POST)
URL:    ${base}/v1/simulate
Method: POST
Headers:
  Authorization: Bearer ${key}
  Content-Type:  application/json
Body (JSON):
  mode:         auto
  objective:    maximize
  n_simulations: 10000
  variables:
    - name: revenue
      low:  80000
      mode: 100000
      high: 130000

# Map to next Zap step:
# recommended_action → CRM field / Slack message
# metrics.mean       → expected value
# metrics.p95        → worst-case 95th percentile`,
      note: "See examples/zapier/README.md for a full walkthrough (Google Sheets row → Simulate → Slack alert).",
    },
    make: {
      lang: "json",
      code: `// Make (Integromat) — HTTP module
// URL:    ${base}/v1/simulate
// Method: POST
// Headers: Authorization: Bearer ${key}
// Body (raw JSON):
{
  "mode": "auto",
  "objective": "maximize",
  "n_simulations": 10000,
  "variables": [
    {"name": "revenue", "low": 80000, "mode": 100000, "high": 130000}
  ]
}

// Parse with JSON module → map fields:
// recommended_action, metrics.mean, metrics.p95, metrics.std_dev

// Async pattern (large simulations):
// 1. POST ${base}/v1/jobs  → get job_id
// 2. Poll GET ${base}/v1/jobs/{{job_id}} until status = "completed"`,
      note: "See examples/make/README.md for the full scenario template.",
    },
  };
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function ProgressBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div>
      <p
        style={{
          fontSize: 11,
          fontWeight: 500,
          color: "var(--ag-text-primary)",
          marginBottom: 4,
        }}
      >
        {pct}%
      </p>
      <div
        style={{
          width: 72,
          height: 4,
          background: "var(--ag-border-strong)",
          borderRadius: 2,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.min(pct, 100)}%`,
            height: "100%",
            background: color,
            borderRadius: 2,
            transition: "width 300ms",
          }}
        />
      </div>
    </div>
  );
}

function NodeStatusBadge({ status }: { status: string }) {
  if (status === "live")
    return (
      <>
        <span className="ag-status-dot ag-status-dot--success" />
        <span
          style={{ color: "var(--ag-success)", fontSize: 12, fontWeight: 500 }}
        >
          Healthy
        </span>
      </>
    );
  if (status === "warning")
    return (
      <>
        <span className="ag-status-dot ag-status-dot--warning" />
        <span
          style={{ color: "var(--ag-warning)", fontSize: 12, fontWeight: 500 }}
        >
          Warning
        </span>
      </>
    );
  if (status === "error")
    return (
      <>
        <span className="ag-status-dot ag-status-dot--danger" />
        <span
          style={{ color: "var(--ag-danger)", fontSize: 12, fontWeight: 500 }}
        >
          Error
        </span>
      </>
    );
  return (
    <>
      <span className="ag-status-dot ag-status-dot--muted" />
      <span
        style={{ color: "var(--ag-text-muted)", fontSize: 12, fontWeight: 500 }}
      >
        Offline
      </span>
    </>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="ag-button ag-button--sm"
      style={{ position: "absolute", top: 10, right: 10, opacity: 0.8 }}
      onClick={() => {
        navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        });
      }}
    >
      <i
        className={`fa-solid ${copied ? "fa-check" : "fa-copy"}`}
        style={{ marginRight: 4 }}
      />
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function InfrastructurePage() {
  const [infra, setInfra] = useState<InfrastructureResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  // Deployment state
  const [deployment, setDeployment] = useState<
    DeploymentInfo | null | undefined
  >(undefined);
  const [providersLoading, setProvidersLoading] = useState(false);
  const [providers, setProviders] = useState<CloudProvider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedRegion, setSelectedRegion] = useState("");
  const [wizardOpen, setWizardOpen] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [deployError, setDeployError] = useState<string | null>(null);

  // Connect section — read API key + base URL from browser storage so snippets are real
  const [connectTab, setConnectTab] = useState<ConnectTabId>("rest");
  const [apiKey, setApiKey] = useState("");
  const [apiBase, setApiBase] = useState(
    process.env.NEXT_PUBLIC_API_URL ?? "https://api.algenta.ai",
  );
  useEffect(() => {
    setApiKey(localStorage.getItem("de_api_key") ?? "");
    const stored = process.env.NEXT_PUBLIC_API_URL;
    if (stored) setApiBase(stored);
  }, []);

  function load(force = false) {
    const now = Date.now();
    // Use cache if fresh and not forcing refresh
    if (
      !force &&
      _cacheTime > 0 &&
      now - _cacheTime < CACHE_TTL_MS &&
      _infraCache !== null
    ) {
      setInfra(_infraCache);
      setDeployment(_deploymentCache);
      setLoading(false);
      setLastRefresh(new Date(_cacheTime));
      return;
    }
    setRefreshing(true);
    Promise.all([getInfrastructure(), getDeployment().catch(() => null)])
      .then(([infraData, dep]) => {
        _infraCache = infraData;
        _deploymentCache = dep;
        _cacheTime = Date.now();
        setInfra(infraData);
        setDeployment(dep);
        setLastRefresh(new Date());
      })
      .catch(() => {})
      .finally(() => {
        setLoading(false);
        setRefreshing(false);
      });
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Lazy-load providers — only when user opens the deployment wizard
  function loadProviders() {
    if (providers.length > 0) return;
    setProvidersLoading(true);
    listDeploymentRegions()
      .then((regData) => {
        if (regData.providers && regData.providers.length > 0) {
          setProviders(regData.providers);
        }
      })
      .catch(() => {})
      .finally(() => setProvidersLoading(false));
  }

  const selectedProviderData = providers.find((p) => p.id === selectedProvider);
  const availableRegions = selectedProviderData?.regions ?? [];

  async function handleDeploy() {
    setDeploying(true);
    setDeployError(null);
    try {
      const dep = await createDeployment({
        provider: selectedProvider,
        region: selectedRegion,
        billing_markup_pct: 20,
      });
      _deploymentCache = dep;
      _cacheTime = Date.now();
      setDeployment(dep);
      setWizardOpen(false);
    } catch (err: unknown) {
      setDeployError(err instanceof Error ? err.message : "Deployment failed");
    }
    setDeploying(false);
  }

  async function handleDeprovision(deploymentId: string) {
    if (
      !confirm(
        "Are you sure you want to deprovision? Your org will revert to the shared pool.",
      )
    )
      return;
    try {
      await deleteDeployment(deploymentId);
      _deploymentCache = null;
      _cacheTime = Date.now();
      setDeployment(null);
    } catch (err: unknown) {
      setDeployError(err instanceof Error ? err.message : "Deprovision failed");
    }
  }

  const nodes: NodeInfo[] = infra?.nodes ?? [];
  const liveCount = nodes.filter((n) => n.status === "live").length;
  const avgLatency = infra ? Math.round(infra.avg_latency_ms) : null;
  const p95Latency = infra ? Math.round(infra.p95_latency_ms) : null;
  const throughput = infra?.throughput_rpm;
  const uptime = infra?.uptime_30d_pct;
  const engineVer = infra?.engine_version ?? "—";
  const engineMode = infra?.engine_mode ?? "—";
  const tpDisplay =
    throughput != null
      ? throughput >= 1000
        ? `${(throughput / 1000).toFixed(1)}k`
        : String(Math.round(throughput))
      : "—";

  const nodeRows = nodes.map((n, i) => ({
    id: n.node_id ?? `node-${i + 1}`,
    icon: i === 0 ? "fa-desktop" : "fa-server",
    status: n.status,
    cpu: n.cpu_pct ?? null,
    mem:
      n.memory_gb != null
        ? Math.min(Math.round(n.memory_gb * 6.25), 100)
        : null,
    throughput:
      n.jobs_per_sec != null
        ? `${Math.round(n.jobs_per_sec * 60)} runs/min`
        : "—",
    region: n.region ?? "—",
    engine_ver: n.engine_version ?? engineVer,
  }));

  function cpuColor(p: number) {
    return p >= 85
      ? "var(--ag-danger)"
      : p >= 65
        ? "var(--ag-warning)"
        : "var(--ag-brand-primary)";
  }

  const activeSnippet = buildSnippets(apiKey, apiBase)[connectTab];

  return (
    <div style={{ minHeight: "100vh", background: "var(--ag-bg-canvas)" }}>
      <header style={topbar}>
        <div>
          <h1 className="ag-page-title">Infrastructure</h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {lastRefresh && (
            <span className="ag-caption">
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span
              className={`ag-status-dot ${infra ? "ag-status-dot--live" : "ag-status-dot--muted"}`}
            />
            <span className="ag-caption">
              {infra
                ? "Engine healthy"
                : loading
                  ? "Connecting…"
                  : "Unavailable"}
            </span>
          </div>
          {engineVer !== "—" && (
            <>
              <span
                style={{
                  width: 1,
                  height: 16,
                  background: "var(--ag-border-default)",
                }}
              />
              <span className="ag-caption">
                v{" "}
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    color: "var(--ag-text-primary)",
                    fontSize: 11,
                  }}
                >
                  {engineVer}
                </span>
              </span>
            </>
          )}
          <button
            className="ag-button ag-button--sm"
            onClick={() => load(true)}
            disabled={refreshing}
          >
            <i
              className={`fa-solid fa-rotate-right ${refreshing ? "fa-spin" : ""}`}
              style={{ marginRight: refreshing ? 5 : 0 }}
            />
            {refreshing ? "Refreshing…" : ""}
          </button>
        </div>
      </header>

      <div className="ag-content">
        {/* ── Engine Status + Deployment — two-column compact strip ──────────── */}
        <div
          style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}
        >
          {/* Engine Status */}
          <div className="ag-card">
            <div className="ag-card-header">
              <div>
                <p className="ag-section-title">Engine Status</p>
                <p className="ag-section-subtitle">Runtime configuration</p>
              </div>
            </div>
            <div className="ag-card-body">
              {infra ? (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    gap: 10,
                  }}
                >
                  {[
                    {
                      label: "Mode",
                      value: infra.deployment_mode ?? "Algenta Cloud",
                      icon: "fa-cloud",
                    },
                    {
                      label: "Engine",
                      value: engineMode,
                      icon: "fa-microchip",
                    },
                    { label: "Version", value: engineVer, icon: "fa-tag" },
                    {
                      label: "API Version",
                      value: infra.api_version ?? "—",
                      icon: "fa-code",
                    },
                    {
                      label: "Nodes",
                      value: `${liveCount} / ${nodes.length} live`,
                      icon: "fa-server",
                    },
                    {
                      label: "Uptime 30d",
                      value: uptime != null ? `${uptime.toFixed(2)}%` : "—",
                      icon: "fa-clock",
                    },
                  ].map(({ label, value, icon }) => (
                    <div
                      key={label}
                      style={{
                        background: "var(--ag-bg-surface-2)",
                        border: "1px solid var(--ag-border-default)",
                        borderRadius: "var(--ag-radius-md)",
                        padding: "10px 12px",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          marginBottom: 5,
                        }}
                      >
                        <i
                          className={`fa-solid ${icon}`}
                          style={{
                            fontSize: 10,
                            color: "var(--ag-text-muted)",
                          }}
                        />
                        <span
                          style={{
                            fontSize: 10,
                            color: "var(--ag-text-muted)",
                            fontWeight: 500,
                            textTransform: "uppercase",
                            letterSpacing: "0.04em",
                          }}
                        >
                          {label}
                        </span>
                      </div>
                      <div
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 13,
                          fontWeight: 700,
                          color: "var(--ag-text-primary)",
                        }}
                      >
                        {value}
                      </div>
                    </div>
                  ))}
                </div>
              ) : loading ? (
                <div
                  style={{
                    padding: "24px 0",
                    textAlign: "center",
                    color: "var(--ag-text-muted)",
                  }}
                >
                  <i
                    className="fa-solid fa-spinner fa-spin"
                    style={{ marginRight: 8 }}
                  />
                  Loading…
                </div>
              ) : (
                <div
                  style={{
                    padding: 12,
                    background: "var(--ag-warning-soft)",
                    border: "1px solid rgba(245,158,11,0.25)",
                    borderRadius: "var(--ag-radius-md)",
                  }}
                >
                  <p className="ag-caption">
                    <i
                      className="fa-solid fa-triangle-exclamation"
                      style={{ color: "var(--ag-warning)", marginRight: 6 }}
                    />
                    Unable to reach the engine. Ensure the API server is
                    running.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Deployment Location */}
          <div className="ag-card">
            <div className="ag-card-header">
              <div>
                <p className="ag-section-title">Deployment Location</p>
                <p className="ag-section-subtitle">
                  Where your data and compute run
                </p>
              </div>
            </div>
            <div className="ag-card-body">
              {deployError && (
                <div
                  style={{
                    background: "var(--ag-danger-soft)",
                    border: "1px solid rgba(239,68,68,0.22)",
                    borderRadius: "var(--ag-radius-md)",
                    padding: "8px 12px",
                    marginBottom: 12,
                    fontSize: 12,
                    color: "var(--ag-danger)",
                  }}
                >
                  <i
                    className="fa-solid fa-circle-exclamation"
                    style={{ marginRight: 6 }}
                  />
                  {deployError}
                </div>
              )}

              {deployment && deployment.status !== "deprovisioned" ? (
                /* Active deployment */
                <div>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(2, 1fr)",
                      gap: 10,
                      marginBottom: 14,
                    }}
                  >
                    {[
                      {
                        label: "Provider",
                        value:
                          deployment.provider === "algenta_shared"
                            ? "Algenta Managed"
                            : deployment.provider.toUpperCase(),
                      },
                      { label: "Region", value: deployment.region },
                      { label: "Status", value: deployment.status },
                      {
                        label: "Cost",
                        value:
                          deployment.provider === "algenta_shared"
                            ? "Included"
                            : `$${deployment.billable_cost_usd_month.toFixed(0)}/mo`,
                      },
                    ].map(({ label, value }) => (
                      <div
                        key={label}
                        style={{
                          background: "var(--ag-bg-surface-2)",
                          border: "1px solid var(--ag-border-default)",
                          borderRadius: "var(--ag-radius-md)",
                          padding: "10px 12px",
                        }}
                      >
                        <p
                          style={{
                            fontSize: 10,
                            color: "var(--ag-text-muted)",
                            fontWeight: 500,
                            textTransform: "uppercase",
                            letterSpacing: "0.04em",
                            margin: "0 0 4px",
                          }}
                        >
                          {label}
                        </p>
                        <p
                          style={{
                            fontSize: 13,
                            fontWeight: 700,
                            color: "var(--ag-text-primary)",
                            margin: 0,
                            fontFamily: "var(--font-mono)",
                          }}
                        >
                          {value}
                        </p>
                      </div>
                    ))}
                  </div>
                  {deployment.endpoint_url && (
                    <p className="ag-caption" style={{ marginBottom: 10 }}>
                      <i
                        className="fa-solid fa-link"
                        style={{ marginRight: 6, color: "var(--ag-success)" }}
                      />
                      <code
                        style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}
                      >
                        {deployment.endpoint_url}
                      </code>
                    </p>
                  )}
                  {(deployment.status === "provisioning" ||
                    deployment.status === "requested") && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        color: "var(--ag-info)",
                        fontSize: 12,
                      }}
                    >
                      <i className="fa-solid fa-spinner fa-spin" />
                      Provisioning — typically 3–5 minutes…
                    </div>
                  )}
                  {deployment.status === "active" &&
                    deployment.provider !== "algenta_shared" && (
                      <button
                        className="ag-button ag-button--sm"
                        onClick={() =>
                          handleDeprovision(deployment.deployment_id)
                        }
                      >
                        <i
                          className="fa-solid fa-xmark"
                          style={{ marginRight: 5 }}
                        />
                        Deprovision
                      </button>
                    )}
                </div>
              ) : !wizardOpen ? (
                /* Compact prompt — no large empty state */
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                    padding: "14px 16px",
                    background: "var(--ag-bg-surface-2)",
                    border: "1px solid var(--ag-border-default)",
                    borderRadius: "var(--ag-radius-md)",
                  }}
                >
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 10 }}
                  >
                    <i
                      className="fa-solid fa-cloud"
                      style={{ fontSize: 18, color: "var(--ag-brand-primary)" }}
                    />
                    <div>
                      <p
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: "var(--ag-text-primary)",
                          margin: 0,
                        }}
                      >
                        Algenta Shared Pool
                      </p>
                      <p className="ag-caption" style={{ margin: "2px 0 0" }}>
                        Managed multi-tenant · US East · Encrypted at rest
                      </p>
                    </div>
                  </div>
                  <button
                    className="ag-button ag-button--primary ag-button--sm"
                    onClick={() => {
                      setWizardOpen(true);
                      loadProviders();
                    }}
                  >
                    <i
                      className="fa-solid fa-cloud-arrow-up"
                      style={{ marginRight: 5 }}
                    />
                    Change
                  </button>
                </div>
              ) : (
                /* Multi-step deployment wizard */
                <div
                  style={{ display: "flex", flexDirection: "column", gap: 14 }}
                >
                  {/* Step 1 — Provider */}
                  <div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        marginBottom: 10,
                      }}
                    >
                      <div
                        style={{
                          width: 20,
                          height: 20,
                          borderRadius: "50%",
                          background: selectedProvider
                            ? "var(--ag-brand-primary)"
                            : "var(--ag-border-strong)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 10,
                          fontWeight: 700,
                          color: "#fff",
                          flexShrink: 0,
                        }}
                      >
                        {selectedProvider ? (
                          <i className="fa-solid fa-check" />
                        ) : (
                          "1"
                        )}
                      </div>
                      <p className="ag-section-kicker" style={{ margin: 0 }}>
                        Cloud Provider
                      </p>
                      {selectedProvider && (
                        <button
                          className="ag-button ag-button--sm"
                          style={{ marginLeft: "auto" }}
                          onClick={() => {
                            setSelectedProvider("");
                            setSelectedRegion("");
                          }}
                        >
                          Change
                        </button>
                      )}
                    </div>
                    {!selectedProvider && (
                      <>
                        {providersLoading && (
                          <p className="ag-caption">
                            <i
                              className="fa-solid fa-spinner fa-spin"
                              style={{ marginRight: 6 }}
                            />
                            Loading providers…
                          </p>
                        )}
                        {!providersLoading && providers.length === 0 && (
                          <p
                            className="ag-caption"
                            style={{ color: "var(--ag-warning)" }}
                          >
                            <i
                              className="fa-solid fa-triangle-exclamation"
                              style={{ marginRight: 6 }}
                            />
                            Could not load providers.{" "}
                            <button
                              className="ag-button ag-button--sm"
                              style={{ marginLeft: 6 }}
                              onClick={() => {
                                setProviders([]);
                                loadProviders();
                              }}
                            >
                              Retry
                            </button>
                          </p>
                        )}
                        {!providersLoading && providers.length > 0 && (
                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns: "repeat(4, 1fr)",
                              gap: 8,
                            }}
                          >
                            {providers.map((p) => (
                              <button
                                key={p.id}
                                onClick={() => {
                                  setSelectedProvider(p.id);
                                  setSelectedRegion("");
                                }}
                                style={{
                                  padding: "10px 8px",
                                  borderRadius: "var(--ag-radius-md)",
                                  border: "1px solid var(--ag-border-default)",
                                  background: "var(--ag-bg-surface-2)",
                                  cursor: "pointer",
                                  textAlign: "center",
                                }}
                              >
                                <div style={{ fontSize: 20, marginBottom: 3 }}>
                                  {p.icon}
                                </div>
                                <p
                                  style={{
                                    fontSize: 11,
                                    fontWeight: 600,
                                    color: "var(--ag-text-primary)",
                                    margin: 0,
                                  }}
                                >
                                  {p.name}
                                </p>
                              </button>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                    {selectedProvider && (
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          padding: "7px 10px",
                          background: "var(--ag-brand-soft)",
                          border: "1px solid var(--ag-brand-border)",
                          borderRadius: "var(--ag-radius-md)",
                        }}
                      >
                        <span style={{ fontSize: 14 }}>
                          {
                            providers.find((p) => p.id === selectedProvider)
                              ?.icon
                          }
                        </span>
                        <span
                          style={{
                            fontSize: 12,
                            fontWeight: 600,
                            color: "var(--ag-text-primary)",
                          }}
                        >
                          {
                            providers.find((p) => p.id === selectedProvider)
                              ?.name
                          }
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Step 2 — Region */}
                  {selectedProvider &&
                    selectedProvider !== "algenta_shared" && (
                      <div>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            marginBottom: 10,
                          }}
                        >
                          <div
                            style={{
                              width: 20,
                              height: 20,
                              borderRadius: "50%",
                              background: selectedRegion
                                ? "var(--ag-brand-primary)"
                                : "var(--ag-border-strong)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: 10,
                              fontWeight: 700,
                              color: "#fff",
                              flexShrink: 0,
                            }}
                          >
                            {selectedRegion ? (
                              <i className="fa-solid fa-check" />
                            ) : (
                              "2"
                            )}
                          </div>
                          <p
                            className="ag-section-kicker"
                            style={{ margin: 0 }}
                          >
                            Region
                          </p>
                          {selectedRegion && (
                            <button
                              className="ag-button ag-button--sm"
                              style={{ marginLeft: "auto" }}
                              onClick={() => setSelectedRegion("")}
                            >
                              Change
                            </button>
                          )}
                        </div>
                        {!selectedRegion && (
                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns: "repeat(3, 1fr)",
                              gap: 6,
                              maxHeight: 200,
                              overflowY: "auto",
                            }}
                          >
                            {availableRegions.map((r) => (
                              <button
                                key={r.id}
                                onClick={() => setSelectedRegion(r.id)}
                                style={{
                                  padding: "6px 8px",
                                  borderRadius: "var(--ag-radius-sm)",
                                  border: "1px solid var(--ag-border-default)",
                                  background: "var(--ag-bg-surface-2)",
                                  cursor: "pointer",
                                  textAlign: "left",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 5,
                                }}
                              >
                                <span style={{ fontSize: 12 }}>{r.flag}</span>
                                <span
                                  style={{
                                    fontSize: 10,
                                    fontWeight: 600,
                                    color: "var(--ag-text-primary)",
                                  }}
                                >
                                  {r.label}
                                </span>
                              </button>
                            ))}
                          </div>
                        )}
                        {selectedRegion && (
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 8,
                              padding: "7px 10px",
                              background: "var(--ag-bg-surface-2)",
                              border: "1px solid var(--ag-border-default)",
                              borderRadius: "var(--ag-radius-md)",
                            }}
                          >
                            <span style={{ fontSize: 14 }}>
                              {
                                availableRegions.find(
                                  (r) => r.id === selectedRegion,
                                )?.flag
                              }
                            </span>
                            <span
                              style={{
                                fontSize: 12,
                                fontWeight: 600,
                                color: "var(--ag-text-primary)",
                              }}
                            >
                              {
                                availableRegions.find(
                                  (r) => r.id === selectedRegion,
                                )?.label
                              }
                            </span>
                          </div>
                        )}
                      </div>
                    )}

                  {/* Step 3 — Review + Deploy */}
                  {selectedProvider &&
                    (selectedProvider === "algenta_shared" ||
                      selectedRegion) && (
                      <div
                        style={{
                          paddingTop: 12,
                          borderTop: "1px solid var(--ag-border-subtle)",
                          display: "flex",
                          flexDirection: "column",
                          gap: 10,
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                          }}
                        >
                          <div
                            style={{
                              width: 20,
                              height: 20,
                              borderRadius: "50%",
                              background: "var(--ag-border-strong)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: 10,
                              fontWeight: 700,
                              color: "#fff",
                              flexShrink: 0,
                            }}
                          >
                            {selectedProvider === "algenta_shared" ? "2" : "3"}
                          </div>
                          <p
                            className="ag-section-kicker"
                            style={{ margin: 0 }}
                          >
                            Review & Deploy
                          </p>
                        </div>
                        <div
                          style={{
                            background:
                              selectedProvider === "algenta_shared"
                                ? "var(--ag-brand-soft)"
                                : "var(--ag-success-soft)",
                            border: `1px solid ${selectedProvider === "algenta_shared" ? "var(--ag-brand-border)" : "rgba(0,211,149,0.22)"}`,
                            borderRadius: "var(--ag-radius-md)",
                            padding: "10px 12px",
                            fontSize: 11,
                            color: "var(--ag-text-secondary)",
                            lineHeight: 1.6,
                          }}
                        >
                          {selectedProvider === "algenta_shared" ? (
                            <>
                              <i
                                className="fa-solid fa-shield-check"
                                style={{
                                  color: "var(--ag-brand-primary)",
                                  marginRight: 6,
                                }}
                              />
                              <strong
                                style={{ color: "var(--ag-text-primary)" }}
                              >
                                Hosted by Algenta
                              </strong>{" "}
                              — Algenta-managed infrastructure, US East
                              (us-east-1). Encrypted at rest and in transit.
                              Shared multi-tenant pool.{" "}
                              <a
                                href="https://algenta.ai/privacy"
                                style={{ color: "var(--ag-brand-primary)" }}
                              >
                                Privacy Policy →
                              </a>
                            </>
                          ) : (
                            <>
                              <i
                                className="fa-solid fa-location-dot"
                                style={{
                                  color: "var(--ag-success)",
                                  marginRight: 6,
                                }}
                              />
                              <strong
                                style={{ color: "var(--ag-text-primary)" }}
                              >
                                Data stays in{" "}
                                {availableRegions.find(
                                  (r) => r.id === selectedRegion,
                                )?.label ?? selectedRegion}
                              </strong>{" "}
                              — Isolated compute, DB, and storage. No data
                              leaves this region. Billed at cloud cost + 20%.
                            </>
                          )}
                        </div>
                        <div style={{ display: "flex", gap: 8 }}>
                          <button
                            className="ag-button ag-button--primary ag-button--sm"
                            onClick={handleDeploy}
                            disabled={deploying}
                          >
                            {deploying ? (
                              <>
                                <i
                                  className="fa-solid fa-spinner fa-spin"
                                  style={{ marginRight: 5 }}
                                />
                                Provisioning…
                              </>
                            ) : selectedProvider === "algenta_shared" ? (
                              <>
                                <i
                                  className="fa-solid fa-check"
                                  style={{ marginRight: 5 }}
                                />
                                Use Algenta Managed
                              </>
                            ) : (
                              <>
                                <i
                                  className="fa-solid fa-cloud-arrow-up"
                                  style={{ marginRight: 5 }}
                                />
                                Deploy to {selectedProvider.toUpperCase()}
                              </>
                            )}
                          </button>
                          <button
                            className="ag-button ag-button--sm"
                            onClick={() => {
                              setWizardOpen(false);
                              setSelectedProvider("");
                              setSelectedRegion("");
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Connect ───────────────────────────────────────────────────────── */}
        <div className="ag-card">
          <div className="ag-card-header">
            <div>
              <p className="ag-section-title">Connect</p>
              <p className="ag-section-subtitle">
                Integrate the Decision Engine into your app, workflow, or AI
                agent
              </p>
            </div>
          </div>

          {/* Tab bar */}
          <div
            style={{
              display: "flex",
              gap: 2,
              padding: "0 18px",
              borderBottom: "1px solid var(--ag-border-default)",
              overflowX: "auto",
            }}
          >
            {CONNECT_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setConnectTab(tab.id)}
                style={{
                  padding: "9px 14px",
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "pointer",
                  background: "transparent",
                  border: "none",
                  borderBottom:
                    connectTab === tab.id
                      ? "2px solid var(--ag-brand-primary)"
                      : "2px solid transparent",
                  color:
                    connectTab === tab.id
                      ? "var(--ag-text-primary)"
                      : "var(--ag-text-muted)",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  whiteSpace: "nowrap",
                  transition: "color 150ms",
                  marginBottom: -1,
                }}
              >
                <i className={tab.icon} style={{ fontSize: 11 }} />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Code panel */}
          <div className="ag-card-body">
            {activeSnippet.note && (
              <p
                style={{
                  fontSize: 12,
                  color: "var(--ag-text-secondary)",
                  marginBottom: 10,
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 6,
                }}
              >
                <i
                  className="fa-solid fa-circle-info"
                  style={{ color: "var(--ag-info)", marginTop: 1 }}
                />
                {activeSnippet.note}
              </p>
            )}
            <div style={{ position: "relative" }}>
              <pre
                style={{
                  margin: 0,
                  padding: "14px 16px",
                  paddingRight: 100,
                  background: "var(--ag-bg-canvas)",
                  border: "1px solid var(--ag-border-default)",
                  borderRadius: "var(--ag-radius-md)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  lineHeight: 1.65,
                  color: "var(--ag-text-primary)",
                  overflowX: "auto",
                  whiteSpace: "pre",
                }}
              >
                {activeSnippet.code}
              </pre>
              <CopyButton text={activeSnippet.code} />
            </div>

            {/* Quick-links row */}
            <div
              style={{
                display: "flex",
                gap: 8,
                marginTop: 12,
                flexWrap: "wrap",
              }}
            >
              {connectTab === "rest" && (
                <>
                  <a
                    href="https://docs.algenta.io/api-reference"
                    target="_blank"
                    rel="noreferrer"
                    className="ag-button ag-button--sm"
                    style={{ textDecoration: "none" }}
                  >
                    <i
                      className="fa-solid fa-book"
                      style={{ marginRight: 5 }}
                    />
                    API Reference
                  </a>
                  <a
                    href="/dashboard/api-keys"
                    className="ag-button ag-button--sm"
                    style={{ textDecoration: "none" }}
                  >
                    <i className="fa-solid fa-key" style={{ marginRight: 5 }} />
                    Get API Key
                  </a>
                </>
              )}
              {connectTab === "python" && (
                <>
                  <a
                    href="https://pypi.org/project/algenta-decision-engine/"
                    target="_blank"
                    rel="noreferrer"
                    className="ag-button ag-button--sm"
                    style={{ textDecoration: "none" }}
                  >
                    <i
                      className="fa-brands fa-python"
                      style={{ marginRight: 5 }}
                    />
                    PyPI
                  </a>
                  <a
                    href="https://docs.algenta.io/sdks/python"
                    target="_blank"
                    rel="noreferrer"
                    className="ag-button ag-button--sm"
                    style={{ textDecoration: "none" }}
                  >
                    <i
                      className="fa-solid fa-book"
                      style={{ marginRight: 5 }}
                    />
                    SDK Docs
                  </a>
                </>
              )}
              {connectTab === "typescript" && (
                <>
                  <a
                    href="https://www.npmjs.com/package/@algenta/decision-engine"
                    target="_blank"
                    rel="noreferrer"
                    className="ag-button ag-button--sm"
                    style={{ textDecoration: "none" }}
                  >
                    <i
                      className="fa-brands fa-npm"
                      style={{ marginRight: 5 }}
                    />
                    npm
                  </a>
                  <a
                    href="https://docs.algenta.io/sdks/typescript"
                    target="_blank"
                    rel="noreferrer"
                    className="ag-button ag-button--sm"
                    style={{ textDecoration: "none" }}
                  >
                    <i
                      className="fa-solid fa-book"
                      style={{ marginRight: 5 }}
                    />
                    SDK Docs
                  </a>
                </>
              )}
              {connectTab === "cli" && (
                <a
                  href="https://docs.algenta.io/sdks/cli"
                  target="_blank"
                  rel="noreferrer"
                  className="ag-button ag-button--sm"
                  style={{ textDecoration: "none" }}
                >
                  <i className="fa-solid fa-book" style={{ marginRight: 5 }} />
                  CLI Docs
                </a>
              )}
              {connectTab === "mcp" && (
                <>
                  <a
                    href="https://docs.algenta.io/integrations/mcp"
                    target="_blank"
                    rel="noreferrer"
                    className="ag-button ag-button--sm"
                    style={{ textDecoration: "none" }}
                  >
                    <i
                      className="fa-solid fa-book"
                      style={{ marginRight: 5 }}
                    />
                    MCP Docs
                  </a>
                  <a
                    href="examples/claude-desktop/README.md"
                    className="ag-button ag-button--sm"
                    style={{ textDecoration: "none" }}
                  >
                    <i
                      className="fa-solid fa-robot"
                      style={{ marginRight: 5 }}
                    />
                    Claude Setup
                  </a>
                </>
              )}
              {(connectTab === "langchain" || connectTab === "langgraph") && (
                <>
                  <a
                    href="https://docs.algenta.io/integrations/langgraph"
                    target="_blank"
                    rel="noreferrer"
                    className="ag-button ag-button--sm"
                    style={{ textDecoration: "none" }}
                  >
                    <i
                      className="fa-solid fa-book"
                      style={{ marginRight: 5 }}
                    />
                    LangGraph Docs
                  </a>
                  <a
                    href="https://github.com/algenta/decision-engine/blob/main/examples/langgraph/decision_tool.py"
                    target="_blank"
                    rel="noreferrer"
                    className="ag-button ag-button--sm"
                    style={{ textDecoration: "none" }}
                  >
                    <i
                      className="fa-brands fa-github"
                      style={{ marginRight: 5 }}
                    />
                    View Full Example
                  </a>
                </>
              )}
              {connectTab === "n8n" && (
                <a
                  href="https://docs.algenta.io/integrations/n8n"
                  target="_blank"
                  rel="noreferrer"
                  className="ag-button ag-button--sm"
                  style={{ textDecoration: "none" }}
                >
                  <i className="fa-solid fa-book" style={{ marginRight: 5 }} />
                  n8n Guide
                </a>
              )}
              {connectTab === "zapier" && (
                <a
                  href="https://docs.algenta.io/integrations/zapier"
                  target="_blank"
                  rel="noreferrer"
                  className="ag-button ag-button--sm"
                  style={{ textDecoration: "none" }}
                >
                  <i className="fa-solid fa-book" style={{ marginRight: 5 }} />
                  Zapier Guide
                </a>
              )}
              {connectTab === "make" && (
                <a
                  href="https://docs.algenta.io/integrations/make"
                  target="_blank"
                  rel="noreferrer"
                  className="ag-button ag-button--sm"
                  style={{ textDecoration: "none" }}
                >
                  <i className="fa-solid fa-book" style={{ marginRight: 5 }} />
                  Make Guide
                </a>
              )}
              <a
                href="/dashboard/playground"
                className="ag-button ag-button--sm"
                style={{ textDecoration: "none" }}
              >
                <i className="fa-solid fa-play" style={{ marginRight: 5 }} />
                Try in Playground
              </a>
            </div>
          </div>
        </div>

        {/* ── Engine Health metrics ─────────────────────────────────────────── */}
        {infra && (
          <div>
            <div className="ag-section-header">
              <p className="ag-section-title">Engine Health</p>
              <p className="ag-section-subtitle">
                Real-time performance metrics
              </p>
            </div>
            <div className="ag-grid-4">
              {[
                {
                  icon: "fa-bolt",
                  iconColor: "var(--ag-warning)",
                  label: "Avg Latency",
                  value: avgLatency != null ? `${avgLatency}ms` : "—",
                  sub: p95Latency != null ? `p95: ${p95Latency}ms` : "—",
                  subColor: "var(--ag-text-muted)",
                },
                {
                  icon: "fa-gauge-high",
                  iconColor: "var(--ag-info)",
                  label: "Throughput",
                  value: tpDisplay,
                  sub: "runs/min",
                  subColor: "var(--ag-text-muted)",
                },
                {
                  icon: "fa-triangle-exclamation",
                  iconColor: "var(--ag-warning)",
                  label: "Error Rate",
                  value: "0.02%",
                  sub: "Within SLA",
                  subColor: "var(--ag-success)",
                },
                {
                  icon: "fa-clock",
                  iconColor: "var(--ag-brand-primary)",
                  label: "Uptime",
                  value: uptime != null ? `${uptime.toFixed(2)}%` : "—",
                  sub: "Last 30 days",
                  subColor: "var(--ag-text-muted)",
                },
              ].map(({ icon, iconColor, label, value, sub, subColor }) => (
                <div key={label} className="ag-card ag-card-body ag-kpi-card">
                  <div className="ag-kpi-header">
                    <span
                      className="ag-kpi-icon"
                      style={{ background: `${iconColor}18`, color: iconColor }}
                    >
                      <i className={`fa-solid ${icon}`} />
                    </span>
                    <span className="ag-kpi-label">{label}</span>
                  </div>
                  <div className="ag-kpi-value">{value}</div>
                  <div className="ag-kpi-sub" style={{ color: subColor }}>
                    {sub}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Compute Nodes ─────────────────────────────────────────────────── */}
        <div className="ag-card">
          <div className="ag-card-header">
            <div>
              <p className="ag-section-title">Compute Nodes</p>
              <p className="ag-section-subtitle">
                {nodes.length > 0
                  ? `${liveCount} of ${nodes.length} nodes live`
                  : "No nodes registered"}
              </p>
            </div>
            <button
              className="ag-button ag-button--sm"
              onClick={() => load(true)}
              disabled={refreshing}
            >
              <i
                className={`fa-solid fa-rotate-right ${refreshing ? "fa-spin" : ""}`}
              />
            </button>
          </div>
          {loading ? (
            <div
              style={{
                padding: "32px 0",
                textAlign: "center",
                color: "var(--ag-text-muted)",
              }}
            >
              <i
                className="fa-solid fa-spinner fa-spin"
                style={{ marginRight: 8 }}
              />
              Loading…
            </div>
          ) : nodes.length === 0 ? (
            <div style={{ padding: "24px" }}>
              <div
                style={{
                  padding: 14,
                  background: "var(--ag-bg-surface-2)",
                  border: "1px solid var(--ag-border-default)",
                  borderRadius: "var(--ag-radius-md)",
                }}
              >
                <p className="ag-body-strong" style={{ marginBottom: 4 }}>
                  No compute nodes registered
                </p>
                <p className="ag-caption" style={{ marginBottom: 10 }}>
                  In Algenta Cloud, compute is managed automatically. For
                  self-hosted, nodes register when workers start.
                </p>
                <a
                  href="https://docs.algenta.io/self-hosting"
                  target="_blank"
                  rel="noreferrer"
                  className="ag-button ag-button--sm"
                  style={{ textDecoration: "none" }}
                >
                  <i className="fa-solid fa-book" style={{ marginRight: 5 }} />
                  Self-hosting docs
                </a>
              </div>
            </div>
          ) : (
            <table className="ag-table">
              <thead>
                <tr>
                  {[
                    "Node ID",
                    "Status",
                    "CPU",
                    "Memory",
                    "Throughput",
                    "Region",
                    "Version",
                  ].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {nodeRows.map((node) => (
                  <tr key={node.id}>
                    <td>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                        }}
                      >
                        <i
                          className={`fa-solid ${node.icon}`}
                          style={{
                            color: "var(--ag-text-muted)",
                            fontSize: 12,
                          }}
                        />
                        <span className="ag-mono">{node.id}</span>
                      </div>
                    </td>
                    <td>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                        }}
                      >
                        <NodeStatusBadge status={node.status} />
                      </div>
                    </td>
                    <td>
                      {node.cpu != null ? (
                        <ProgressBar
                          pct={node.cpu}
                          color={cpuColor(node.cpu)}
                        />
                      ) : (
                        <span className="ag-caption">—</span>
                      )}
                    </td>
                    <td>
                      {node.mem != null ? (
                        <ProgressBar
                          pct={node.mem}
                          color={cpuColor(node.mem)}
                        />
                      ) : (
                        <span className="ag-caption">—</span>
                      )}
                    </td>
                    <td>
                      <span className="ag-caption">{node.throughput}</span>
                    </td>
                    <td>
                      <span className="ag-mono" style={{ fontSize: 11 }}>
                        {node.region}
                      </span>
                    </td>
                    <td>
                      <span className="ag-mono" style={{ fontSize: 11 }}>
                        {node.engine_ver}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {nodes.length > 0 && (
            <div
              style={{
                padding: "10px 16px",
                borderTop: "1px solid var(--ag-border-default)",
              }}
            >
              <span className="ag-caption">
                <span
                  style={{ color: "var(--ag-text-primary)", fontWeight: 500 }}
                >
                  {nodes.length} nodes
                </span>
                {" · "}
                <span
                  style={{ color: "var(--ag-text-primary)", fontWeight: 500 }}
                >
                  {liveCount} live
                </span>
                {" · Mode: "}
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    color: "var(--ag-text-primary)",
                    fontSize: 11,
                  }}
                >
                  {engineMode}
                </span>
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
