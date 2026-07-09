---
icon: toolbox
description: The Algenta MCP server exposes the engine as Model Context Protocol tools for Cursor, Claude, and other hosts. Browse the tool catalog by domain.
---

# Algenta MCP tools

The Algenta MCP server (`algenta-mcp`) turns your engine into a set of Model Context Protocol tools. Point an MCP host at your deployment and your assistant can discover datasets, run governed queries, manage connectors, simulate decisions, and more — every tool a thin, authenticated wrapper over one `/v1` endpoint. This section is the reference for the tools themselves, grouped by domain. For installing and connecting the server, see the [MCP server](../sdk/mcp.md) page.

{% hint style="info" %}
Each MCP tool maps one-to-one to an Algenta API endpoint. Anything you can do through a tool you can reproduce with a direct `curl` against the same `/v1` path — useful for verifying behavior outside an MCP host.
{% endhint %}

## How the tools appear in your host

Once the server is configured, the tools show up in your host's tool panel after a restart, named exactly as in the reference tables below (for example `list_data`, `query_data`, `create_connector`). You drive them in natural language; the assistant picks the tool and fills the arguments.

| Host | Transport | Config |
| --- | --- | --- |
| Cursor, Claude Desktop, Zed, Windsurf, VS Code | stdio | Add `algenta-mcp` to the host's MCP config. |
| ChatGPT, OpenWebUI, LibreChat, n8n, custom apps | HTTP / SSE | Point the client at `$ALGENTA_BASE_URL/mcp/sse`. |

The tool schemas are always live. Enumerate the exact set your deployment exposes with:

```bash title="list the live tool set"
curl -s $ALGENTA_BASE_URL/mcp/tools | jq -r '.tools[].name'
```

{% hint style="info" %}
The visible tool set depends on your key's entitlements and product edition. If a tool below is not in the live list for your deployment, your key is not entitled to it. Start any session with `get_contract` to read the machine-readable capability contract.
{% endhint %}

## Tool groups

Each page is a reference: a table of every tool in the group, the method and endpoint each maps to, and worked examples you can run from an MCP host or reproduce with `curl`.

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Onboard and ingest data</strong></td><td>Register and train datasets, run the high-level connection flow, register sources, and ingest tables to a simulation.</td><td><a href="data.md">data.md</a></td></tr>
<tr><td><strong>Manage saved connectors</strong></td><td>Create, inspect, test, browse, update, and delete reusable data connectors — plus preview inline definitions.</td><td><a href="connectors.md">connectors.md</a></td></tr>
<tr><td><strong>Run governed queries</strong></td><td>Governed exact queries, multi-metric batches, and constrained read-only SQL reports over your datasets.</td><td><a href="query.md">query.md</a></td></tr>
</tbody></table>

{% hint style="info" %}
The server exposes many more tools than these three groups — LLM utilities, decisions and simulations, agent runs, triggers, repository intelligence, and control-plane operations among them. The [MCP server](../sdk/mcp.md) page catalogs the core set, and `get_contract` returns the full contract for your deployment.
{% endhint %}

## Discover, then act

The data and query tools are designed to be chained low-token first, then exact — cheap discovery before you pay for a full schema or a query.

{% stepper %}
{% step %}
### Read the contract

`get_contract` returns the machine-readable contract: tool names, endpoint families, and the governed-filter rules for this deployment.
{% endstep %}

{% step %}
### Find datasets cheaply

`list_data(search=..., compact=true)` for low-token dataset discovery, then `get_data_summary(dataset_id)` before loading the full schema.
{% endstep %}

{% step %}
### Load the schema only when needed

`get_data_schema(dataset_id)` returns columns, roles, formulas, and query hints — reach for it once you have chosen a dataset.
{% endstep %}

{% step %}
### Run governed queries

`query_data` for a single governed exact query, `query_batch` for several in one call, and `query_sql_report` for wide read-only rowsets.
{% endstep %}
{% endstepper %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Set up the MCP server</strong></td><td>Install, configure, and connect Algenta to Cursor, Claude Desktop, and HTTP hosts.</td><td><a href="../sdk/mcp.md">../sdk/mcp.md</a></td></tr>
<tr><td><strong>Discover tools and the contract</strong></td><td>Bootstrap any client from the live contract and tool list.</td><td><a href="../sdk/tool-discovery.md">../sdk/tool-discovery.md</a></td></tr>
<tr><td><strong>Browse the HTTP API</strong></td><td>The one contract every tool wraps.</td><td><a href="../api/overview.md">../api/overview.md</a></td></tr>
</tbody></table>
