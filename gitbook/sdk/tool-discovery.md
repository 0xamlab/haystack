---
icon: compass
description: How an AI agent or MCP client discovers Algenta's tools — list the gated tool catalog, read the machine-readable contract, and check the runtime manifest before planning.
---

# Tool discovery

Algenta exposes a broad, gated tool catalog over MCP and HTTP. A good agent never hardcodes the count — it discovers the set it is allowed to use at runtime, reads a machine-readable contract to plan, and checks the signed runtime manifest before reaching for execution paths. This page explains the three discovery surfaces — the live tool list, `get_contract`, and `get_runtime_manifest` — how the visible set is gated by your edition and license, and how to drive discovery from an MCP client or straight over HTTP.

{% hint style="info" %}
Discovery is how Algenta stays safe to hand to an autonomous agent: the agent asks what it can do, gets back exactly the tools its key and edition permit, and reads the contract that tells it how to use them — instead of guessing at endpoints.
{% endhint %}

## The tool catalog

An MCP client sees the live surface as a flat tool list; the groups below are how to reason about the catalog. The exact list is source-of-truth at runtime because editions and licenses can intentionally hide tools from a given key.

| Category | What it covers |
| --- | --- |
| Data onboarding | `onboard_dataset`, `list_datasets`, `get_dataset_status`, `retrain_dataset` |
| Data access | `connect_data`, `list_data`, `get_data_summary`, `get_data_schema`, `refresh_data`, `disconnect_data` |
| Schema discovery | `list_connectors`, `create_connector`, `test_connector`, `browse_connector`, `register_source`, `get_source_schema` |
| Repository intelligence | `triage_repository`, `create_repository_snapshot`, `query_repository_graph`, `run_repository_fix`, `apply_repository` |
| Query & ingest | `query_data`, `query_batch`, `query_sql_report`, `ingest_data` |
| LLM utilities | `list_models`, `tokenize`, `count_tokens`, `chat_completions`, `responses`, `embeddings`, `rerank` |
| Runtime metadata | `get_runtime_manifest`, `get_runtime_modules`, `get_runtime_benchmarks`, `get_runtime_release_validation` |
| Decisions | `simulate`, `recommend`, `score`, `plan_decision`, `submit_job`, `poll_job`, the product helpers |
| Agent runtime | `create_agent_run`, `get_agent_run`, `get_agent_run_events`, `resume_agent_run`, `cancel_agent_run` |
| Capability plane | `list_capability_providers`, `route_capability`, `execute_capability`, `list_skills`, `create_skill` |
| Control plane | deployments, team, devices, audit logs, execution policy, billing |
| Observability | `get_contract`, `get_runtime_manifest`, `get_me`, `get_limits`, `get_usage` |
| Decision Memory | `log_decision`, `list_decisions`, `record_outcome` |
| Triggers | `register_trigger`, `list_triggers`, `fire_trigger`, `pause_trigger`, `delete_trigger` |

The same tools are reachable three ways: **stdio** (Cursor, Claude Desktop, Zed, Windsurf, VS Code), **Streamable HTTP** (ChatGPT, OpenWebUI, LibreChat, n8n, custom agents), and the **`/mcp`** route embedded in the API server. See [MCP server](mcp.md) for transport setup.

## List the tools you can use

An MCP client calls the standard `tools/list` method on connect — your assistant does this automatically once the [MCP server](mcp.md) is configured. The list you get back is **not** the whole registry: it is scoped to exactly what your key permits.

```text
visible tools = installed tools  ∩  product edition allowlist  ∩  license feature grants
```

So the catalog an agent discovers depends on the edition it is pointed at (`X-Algenta-Product` / `ALGENTA_PRODUCT`), the verified key's entitlements, and the license's feature grants. An unknown or unentitled product resolves to the **empty** set — never the full registry — so discovery fails closed. See [Licensing & editions](../licensing.md) for how features map to tools.

{% hint style="success" %}
Because the list is gated, you can safely connect the same MCP server to different keys: each agent discovers only the tools that key is allowed to call. There is nothing to configure per client beyond the key.
{% endhint %}

## Read the contract

`get_contract` returns the machine-readable **Algenta public contract** — the canonical discovery, summary, query, batch, SQL-report, governed-filter, CLI, and MCP entrypoints. An agent calls it once, up front, to learn how to use the tools it just discovered before planning any work.

{% tabs %}
{% tab title="MCP" %}
The tool takes no arguments. Most agents call it as their first step:

```text
get_contract()  →  the canonical Algenta contract (JSON)
```
{% endtab %}

{% tab title="HTTP" %}
The same payload is served over HTTP for non-MCP clients:

```bash
curl -sS "$ALGENTA_API_URL/v1/meta/contract" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Python" %}
```python
import os

import httpx

api_url = os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai")
resp = httpx.get(
    f"{api_url}/v1/meta/contract",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
)
resp.raise_for_status()
print(resp.json())
```
{% endtab %}
{% endtabs %}

**Expected result.** A JSON contract describing the discovery, query, and execution entrypoints, the governed-filter rules, and the CLI/MCP surfaces — everything an agent needs to plan tool use without trial and error.

## Check the runtime manifest

Before using a runtime-backed execution path, an agent can read `get_runtime_manifest` — the **signed** runtime manifest. It carries the runtime-core inventory, the maturity state of each surface, the proof matrix, and the typed failure contract, so an agent knows what is production-ready and how failures are reported.

```bash
curl -sS "$ALGENTA_API_URL/v1/runtime/manifest" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

## The recommended discovery flow

{% stepper %}
{% step %}
### List the tools

Connect the [MCP server](mcp.md); the client calls `tools/list` and receives the gated catalog for your key.
{% endstep %}

{% step %}
### Read the contract to plan

Call `get_contract` (or `GET /v1/meta/contract`) to learn the entrypoints, governed-filter rules, and query grammar.
{% endstep %}

{% step %}
### Check the manifest before runtime execution

Call `get_runtime_manifest` when you intend to use a runtime-backed path, to confirm maturity and the failure contract.
{% endstep %}

{% step %}
### Plan and call

With the catalog, the contract, and the manifest, the agent plans and calls the specific tools it needs — discovery is complete and nothing was hardcoded.
{% endstep %}
{% endstepper %}

## Related

{% content-ref url="mcp.md" %}
[mcp.md](mcp.md)
{% endcontent-ref %}

{% content-ref url="../help/ai-access.md" %}
[ai-access.md](../help/ai-access.md)
{% endcontent-ref %}

{% content-ref url="../licensing.md" %}
[licensing.md](../licensing.md)
{% endcontent-ref %}

{% content-ref url="../api/overview.md" %}
[overview.md](../api/overview.md)
{% endcontent-ref %}
