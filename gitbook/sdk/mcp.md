---
icon: plug
description: Connect Algenta to MCP-compatible tools like Cursor and Claude Desktop. Configure the MCP server, authenticate, and verify the tools appear.
---

# MCP server

`algenta-mcp` is a Model Context Protocol bridge for Algenta. Install it once, point it at your engine with two environment variables, and your AI assistant gains a governed set of Algenta tools: dataset discovery and exact queries, deterministic utility-model routes, the simplified product helpers, persisted decision memory, and agent runs. This page is the reference for installing, configuring, and connecting the server from Cursor, Claude Desktop, Zed, and Streamable HTTP clients such as OpenWebUI and LibreChat, plus the full catalog of tools it exposes.

## Install

```bash
pipx install algenta-mcp        # or: pip install algenta-mcp
```

The package installs a single console script, `algenta-mcp`. It depends on the published `algenta-sdk` for the API client and egress guard, plus the `mcp` protocol library; there is no monorepo dependency.

{% hint style="info" %}
`algenta-mcp` is a thin client. It calls your Algenta engine over HTTP using your API key. It does not run the engine itself, so the engine (self-hosted or hosted) must be reachable at the configured base URL.
{% endhint %}

## Configure

Introspection (`initialize`/`tools/list`) needs no credentials. Executing tools requires a free community login — device registration at algenta.ai (free): run `algenta login`, or create a key at https://app.algenta.ai/dashboard/api-keys, then set `ALGENTA_API_KEY`.

Point the server at your deployment with two environment variables:

```bash title=".env"
export ALGENTA_BASE_URL="http://localhost:8000"   # your engine; https://api.algenta.ai for Cloud Managed
export ALGENTA_API_KEY="de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

`ALGENTA_BASE_URL` and `ALGENTA_API_KEY` are the canonical variables. Legacy `DE_BASE_URL`, `ALGENTA_API_URL`, and `DE_API_KEY` remain accepted for compatibility.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ALGENTA_API_KEY` | Yes | — | Bearer credential sent to the engine. Legacy `DE_API_KEY` accepted. |
| `ALGENTA_BASE_URL` | Self-hosted: yes | `https://api.algenta.ai` (Cloud Managed only) | Engine base URL. Legacy `DE_BASE_URL` / `ALGENTA_API_URL` accepted. |
| `ALGENTA_MCP_PORT` | No | `8001` | Streamable HTTP listen port. |
| `ALGENTA_MCP_HOST` | No | `127.0.0.1` | Standalone HTTP bind address. Set `0.0.0.0` only behind authenticated ingress. |
| `ALGENTA_MCP_TIMEOUT` | No | `60` | Per-request read timeout in seconds. |
| `ALGENTA_MCP_CONNECT_TIMEOUT` | No | `120` | Connect timeout for slow onboarding calls. |

Choose the base URL by deployment mode:

- **Cloud Managed**: `https://api.algenta.ai`. Manage keys at `https://app.algenta.ai/dashboard/api-keys`.
- **`self_hosted` and `air_gapped`**: set `ALGENTA_BASE_URL` to your own base URL and use the key provisioned by your operator deployment.

{% hint style="warning" %}
Private profiles fail closed. When cloud is disabled, the server refuses to target an Algenta-owned URL and raises a privacy configuration error rather than silently falling back to Algenta cloud. There is no implicit default base URL in that mode.
{% endhint %}

## Transports

`algenta-mcp` runs the **stdio** transport by default, which is what local editors expect. For remote agents and web UIs, run the **Streamable HTTP** transport.

{% tabs %}
{% tab title="stdio (default)" %}
```bash
# Cursor, Claude Desktop, Zed
algenta-mcp
```
{% endtab %}

{% tab title="Streamable HTTP" %}
```bash
# OpenWebUI, LibreChat, n8n, remote agents
algenta-mcp --mode http --port 8001
```
{% endtab %}
{% endtabs %}

`--transport` is an accepted alias for `--mode`. The port resolves from `--port`, then `ALGENTA_MCP_PORT`, then `8001`.
Standalone HTTP binds to loopback by default. Set `ALGENTA_MCP_HOST=0.0.0.0` only when a container or authenticated gateway must expose it to another host.

### Equivalent invocations and explicit interpreter
The following calls are interchangeable for the HTTP transport on port 9000:

```bash
algenta-mcp --transport http --port 9000
ALGENTA_MCP_PORT=9000 algenta-mcp --mode http
```

You can also invoke the module directly, which is convenient for editor configs that prefer an explicit interpreter:

```bash
python -m algenta_mcp.server --mode http --port 8001
```

## Connect an editor (stdio)

{% stepper %}
{% step %}
### Add the server to your MCP config

For Cursor and Claude Desktop, the simplest form uses the installed `algenta-mcp` command with the two environment variables.

```json title="mcp.json"
{
  "mcpServers": {
    "algenta": {
      "command": "algenta-mcp",
      "env": {
        "ALGENTA_BASE_URL": "http://localhost:8000",
        "ALGENTA_API_KEY": "de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

Config file locations:

| Client | Path |
|--------|------|
| Cursor | `~/.cursor/mcp.json` |
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |

### Alternative: explicit Python interpreter
If you prefer an explicit interpreter over the console script, use `python -m algenta_mcp.server`:

```json title="mcp.json"
{
  "mcpServers": {
    "algenta": {
      "command": "python",
      "args": ["-m", "algenta_mcp.server"],
      "env": {
        "ALGENTA_API_KEY": "de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "ALGENTA_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Zed configuration
Zed uses `context_servers` rather than `mcpServers`. Add to `~/.config/zed/settings.json`:

```json title="settings.json"
{
  "context_servers": {
    "algenta": {
      "command": {
        "path": "algenta-mcp",
        "args": [],
        "env": {
          "ALGENTA_API_KEY": "de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
          "ALGENTA_BASE_URL": "http://localhost:8000"
        }
      }
    }
  }
}
```
{% endstep %}

{% step %}
### Restart the client

Restart the editor so it picks up the new configuration. The `algenta` tools then appear in the tools panel.
{% endstep %}

{% step %}
### Drive it with a first prompt

A good first prompt chains low-token discovery into an exact query:

{% hint style="success" %}
Inspect `get_contract()`, find the orders dataset with `list_data(search='orders', compact=true)`, inspect its summary, then query completed orders by month for the last 12 months.
{% endhint %}
{% endstep %}
{% endstepper %}

## Connect a web UI or remote agent (Streamable HTTP)

Start the HTTP transport:

```bash
algenta-mcp --mode http --port 8001
```

If you already run the Algenta API server, the MCP surface is mounted there too:

| Route | Purpose |
|-------|---------|
| `GET /mcp/tools` | List tools as JSON. Always available, no auth required. |
| `POST /mcp` | Send an MCP JSON-RPC request or notification. |
| `GET /mcp` | Optional server-to-client event stream; this stateless deployment may return `405`. |
| `DELETE /mcp` | Session termination; this stateless deployment may return `404` or `405`. |
| `GET /mcp/sse` and `POST /mcp/messages` | Deprecated HTTP+SSE compatibility routes for older clients. |

```bash
curl -s http://localhost:8000/mcp/tools | jq '.tools | length'
```

{% hint style="info" %}
The published `algenta-mcp` package and official Algenta API image already bundle the MCP transport dependencies. A `503` with `error.code = "mcp_transport_unavailable"` means the deployment is an incomplete or outdated custom image; upgrade or reinstall the official distribution instead of managing a side dependency.
{% endhint %}

Algenta uses the MCP `2025-11-25` protocol and the single-endpoint Streamable HTTP transport. The server is stateless, returns JSON responses, validates `Host` and `Origin`, and does not require sticky sessions across API workers.

### Connect a client

{% tabs %}
{% tab title="n8n" %}
1. Add an **MCP Client** node.
2. Set **Transport** to `Streamable HTTP`.
3. Set **URL** to `$ALGENTA_BASE_URL/mcp`.
4. Set **Header** to `Authorization: Bearer $ALGENTA_API_KEY`.
{% endtab %}

{% tab title="LangChain / LangGraph" %}
```python title="connect_langchain.py"
import os

from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "algenta": {
        "url": "http://localhost:8001/mcp",
        "transport": "http",
        "headers": {"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    }
})

tools = await client.get_tools()
```
{% endtab %}
{% endtabs %}

## Tool catalog

The server exposes one MCP tool per capability. Tool names, descriptions, and input schemas are returned by `GET /mcp/tools` and by the MCP `list_tools` call. The core groups below cover the primary data, utility-model, product, and decision-memory lanes.

### Discovery and data

| Tool | Description |
|------|-------------|
| `get_contract` | Machine-readable Algenta contract for tool/API/SDK discovery. |
| `connect_data` | High-level dataset onboarding. Connect once and get a reusable `dataset_id`. |
| `list_data` | Canonical dataset discovery. Supports `search`, `status`, `source_name`, and `compact`. |
| `get_data_summary` | Low-token summary for a dataset before loading the full schema. |
| `get_data_schema` | Full schema, roles, formulas, and query hints for a dataset. |
| `query_data` | Governed exact query over a chosen dataset. |
| `query_batch` | Governed multi-metric exact query in one API call. |
| `query_sql_report` | Constrained read-only SQL rowset over authorized datasets. |

### Utility models

| Tool | Description |
|------|-------------|
| `list_models` | Truthful model catalog with routed provider targets, failover policy, timeout budgets, and auth-header readiness. |
| `resolve_artifact_bridge` | Resolve one Hugging Face artifact path through the cache-safe compatibility bridge. |
| `tokenize` | Deterministic tokenizer utility route. |
| `count_tokens` | Deterministic token-count utility route. |
| `chat_completions` | Tokenizer-backed utility chat contract. |
| `responses` | Unified deterministic utility response surface. |
| `embeddings` | Deterministic lexical embedding route. |
| `embedding_similarity` | Score caller-supplied vectors with a supported similarity model. |
| `rerank` | Rank caller-supplied document embeddings deterministically. |

### Runtime libraries

| Tool | Description |
|------|-------------|
| `list_runtime_libraries` | List the live compiled runtime modules and their public functions. |
| `execute_runtime_library` | Execute one named runtime function through the deployment's warm worker. |

These tools call the authenticated `/v1/libraries` API surface. MCP users do
not launch or configure a separate local runtime.

### Simplified product helpers

| Tool | Description |
|------|-------------|
| `product_decision` | Run the product decision helper and return the chosen action plus risk summary. |
| `product_agent_run` | Run the product task-execution helper and return a compact task result. |
| `product_optimize` | Run the product optimization helper and return the best variable values. |
| `product_retrieve` | Run the product retrieval helper over caller-supplied documents or a collection id. |
| `product_forecast` | Run the product forecast helper over a historical metric series. |

### Decision memory

| Tool | Description |
|------|-------------|
| `plan_decision` | Return the structured DecisionPlan without the full decision envelope. |
| `log_decision` | Persist one decision-memory record for later outcome review. |
| `list_decisions` | List persisted decision-memory records with optional outcome-only filtering. |
| `get_decision` | Fetch one persisted decision-memory record by id. |

{% hint style="info" %}
The server exposes more tools than the groups above — including agent-run lifecycle, simulations, async jobs, triggers, connectors, repository intelligence, deployments, billing, team, and execution-policy tools. Enumerate the live set for your deployment with `curl -s $ALGENTA_BASE_URL/mcp/tools | jq -r '.tools[].name'`.
{% endhint %}

## Recommended data flow

The tools are designed to be chained low-token first, then exact.

{% stepper %}
{% step %}
### Discover capabilities
`get_contract()` returns the machine-readable contract for the deployment.
{% endstep %}

{% step %}
### Find datasets cheaply
`list_data(search=..., compact=true)` for low-token dataset discovery.
{% endstep %}

{% step %}
### Summarize before loading the schema
`get_data_summary(dataset_id)` before paying for the full schema.
{% endstep %}

{% step %}
### Load the full schema only when needed
`get_data_schema(dataset_id)` only when you need the full schema payload.
{% endstep %}

{% step %}
### Run governed exact queries
`query_data(dataset_id=...)` for a single governed exact query, then `query_batch(...)` for multi-metric governed exact queries.
{% endstep %}

{% step %}
### Reach for SQL last
`query_sql_report(...)` only for wide read-only rowsets.
{% endstep %}
{% endstepper %}

{% hint style="info" %}
The governed filter behind `query_data` and `query_batch` is a record-predicate contract over normalized rows, not SQL. The same tool contract therefore applies to SQL backends, Redis snapshots, files, and API-fed data. The operator families and validation rules are exposed through `get_contract()` under `primary_data_query_contract.governed_filter_contract`.
{% endhint %}

## What the tools call

Each MCP tool maps to a single authenticated Algenta API endpoint. Because the mapping is one-to-one, you can call the same endpoints directly to verify behavior outside an MCP client. The table lists representative tools and their endpoints.

| Tool | Method | Endpoint |
|------|--------|----------|
| `get_contract` | `GET` | `/v1/meta/contract` |
| `connect_data` | `POST` | `/v1/data/connect` |
| `list_data` | `GET` | `/v1/data` |
| `get_data_summary` | `GET` | `/v1/data/{dataset_id}/summary` |
| `get_data_schema` | `GET` | `/v1/data/{dataset_id}` |
| `query_data` | `POST` | `/v1/query` |
| `query_batch` | `POST` | `/v1/query/batch` |
| `query_sql_report` | `POST` | `/v1/query/sql-report` |
| `list_models` | `GET` | `/v1/models` |
| `tokenize` | `POST` | `/v1/tokenize` |
| `count_tokens` | `POST` | `/v1/count_tokens` |
| `embeddings` | `POST` | `/v1/embeddings` |
| `product_decision` | `POST` | `/v1/decision` |
| `product_forecast` | `POST` | `/v1/forecast` |
| `plan_decision` | `POST` | `/v1/decisions/plan` |
| `log_decision` | `POST` | `/v1/decisions` |
| `list_decisions` | `GET` | `/v1/decisions` |
| `get_decision` | `GET` | `/v1/decisions/{decision_id}` |

### Verify the mapping with curl

Because each tool is a one-to-one wrapper, you can reproduce any tool call against the raw endpoint.

{% tabs %}
{% tab title="list_data" %}
Discover datasets the same way `list_data(search="orders", compact=true)` does:

```bash
curl -s "$ALGENTA_BASE_URL/v1/data?search=orders&compact=true" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" | jq '.datasets[].dataset_id'
```
{% endtab %}

{% tab title="count_tokens" %}
Count tokens the same way `count_tokens` does:

```bash
curl -s "$ALGENTA_BASE_URL/v1/count_tokens" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "the quick brown fox", "model": "text.tokenizer"}'
```
{% endtab %}

{% tab title="product_decision" %}
Run the product decision helper the same way `product_decision` does:

```bash
curl -s "$ALGENTA_BASE_URL/v1/decision" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "objective": "Maximize Q3 margin",
        "risk_tolerance": "medium",
        "inputs": [
          {"name": "revenue", "value": 500000, "low": 400000, "high": 650000},
          {"name": "cost", "value": 300000}
        ]
      }'
```
{% endtab %}
{% endtabs %}

## Direct Python, no MCP client

Because the server is a thin client over the API, you can drive Algenta from plain Python when you do not need an MCP host:

```python title="direct_forecast.py"
import os
import httpx

api_key = os.environ["ALGENTA_API_KEY"]
base_url = os.environ["ALGENTA_BASE_URL"]

resp = httpx.post(
    f"{base_url}/v1/forecast",
    headers={"Authorization": f"Bearer {api_key}"},
    json={"metric": "mrr", "history": [100, 110, 121, 133], "horizon": 3},
)
print(resp.json())
```

## Security notes

- **stdio** runs locally. Your API key stays in the editor process environment.
- **Streamable HTTP** authenticates downstream to the Algenta API with your key. Put your own gateway (API gateway or Nginx) in front of the MCP HTTP port in production.
- `GET /mcp/tools` is a public list endpoint and exposes no sensitive data. Every actual tool call requires `ALGENTA_API_KEY` (or legacy `DE_API_KEY`).
- Error messages and logs scrub key material, so a misbehaving upstream that reflects a credential cannot leak it through an MCP error.

{% hint style="danger" %}
Never expose the MCP HTTP port directly to the public internet without an authenticating gateway in front of it. The transport relays your key downstream to the Algenta API on every tool call.
{% endhint %}

## OAuth discovery (RFC 9728)

When the API server embedding MCP has Microsoft Entra ID and/or a generic OIDC provider configured (see [Identity and access](../trust/identity-and-access.md) and [Generic OIDC](../integrations/identity/generic-oidc.md)), an unauthenticated `tools/call` — on the streamable `/mcp` mount or the deprecated `/mcp/sse` + `/mcp/messages` pair — answers `401` with a `WWW-Authenticate` header carrying an RFC 9728 discovery hint:

```http title="401 response"
WWW-Authenticate: Bearer realm="algenta", error="invalid_token", resource_metadata="https://your-gateway.example.com/.well-known/oauth-protected-resource/mcp"
```

A compliant OAuth-aware MCP client follows `resource_metadata` to fetch the protected-resource metadata document, which names every authorization server this gateway will actually accept a token from:

```bash
curl -s https://your-gateway.example.com/.well-known/oauth-protected-resource/mcp | jq
```

```json
{
  "resource": "https://your-gateway.example.com/mcp",
  "authorization_servers": ["https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0"],
  "bearer_methods_supported": ["header"],
  "resource_name": "Algenta MCP Server",
  "resource_documentation": "https://docs.algenta.ai/sdk/mcp"
}
```

The same document is also published at the bare `/.well-known/oauth-protected-resource` location for client compatibility.

{% hint style="info" %}
Both routes **404** when neither Entra nor generic OIDC is configured — this gateway never advertises an authorization server that doesn't exist, and a bearer-key-only deployment's `WWW-Authenticate` challenge is unchanged (no `resource_metadata` param). This is the same discipline `GET /.well-known/jwks.json` already follows for the license control plane.
{% endhint %}

## Troubleshooting

| Symptom | Resolution |
|---------|------------|
| `ALGENTA_API_KEY is not set` | Executing tools requires a free community login — device registration at algenta.ai (free): run `algenta login`, or create a key at `https://app.algenta.ai/dashboard/api-keys`, then export `ALGENTA_API_KEY` (or pass `Authorization: Bearer <key>` over HTTP) before launching. |
| `mcp package not installed` | Reinstall or upgrade `algenta-mcp`; its declared dependencies include the MCP protocol library. Do not install a side dependency separately. |
| `API error 401` | Rotate the key at `https://app.algenta.ai/dashboard/api-keys` (Cloud Managed) or in your operator deployment (self-hosted). |
| `API error 429` | Inspect the structured code for an endpoint abuse control, upstream provider limit, or operator policy; Algenta editions have no request meter. |
| `503 mcp_transport_unavailable` on `/mcp` | Upgrade to the current official Algenta API image or reinstall `algenta-mcp`; both bundle the transport. |
| Tool not showing in Claude Desktop | Check JSON config syntax, restart the client, inspect `~/Library/Logs/Claude/`. |
| MCP private profile error targeting an Algenta URL | In `self_hosted` / `air_gapped`, set `ALGENTA_BASE_URL` to your own engine; private profiles refuse Algenta-owned URLs. |

{% content-ref url="../authentication.md" %}
[../authentication.md](../authentication.md)
{% endcontent-ref %}

{% content-ref url="../api/reference.md" %}
[../api/reference.md](../api/reference.md)
{% endcontent-ref %}

{% content-ref url="python.md" %}
[python.md](python.md)
{% endcontent-ref %}

{% content-ref url="../self-hosting.md" %}
[../self-hosting.md](../self-hosting.md)
{% endcontent-ref %}
