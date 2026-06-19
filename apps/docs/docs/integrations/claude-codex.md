---
sidebar_position: 3
---

# Claude and Codex

Connect Algenta to Claude, Codex, and other MCP clients with the canonical `v1` MCP contract.

## Canonical connection

- Cloud Managed endpoint:

```text
https://api.codna.ai/mcp/sse
```

- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

```text
https://your-algenta-host.example/mcp/sse
```

Private profiles do not silently fall back to Codna cloud.

Auth:

```text
Authorization: Bearer <YOUR_ALGENTA_API_KEY>
```

## When to use which mode

- Use the hosted remote MCP endpoint when your client supports a remote MCP URL.
- Use the local stdio bridge when your client only knows how to launch a local MCP process.

## Remote MCP setup

1. Add a new remote MCP server in your client.
2. Set the URL to the endpoint for your deployment mode.
3. Add `Authorization: Bearer <YOUR_ALGENTA_API_KEY>`.
4. Start in read-only mode if your client supports tool scoping.

First prompt:

```text
Inspect get_contract(), then find the orders dataset with list_data(search="orders", compact=true), inspect its summary, then query completed orders by month for the last 12 months.
```

## Local stdio bridge

Use this when your MCP host expects a local process:

```json
{
  "mcpServers": {
    "algenta": {
      "command": "python",
      "args": ["-m", "apps.mcp_server.server"],
      "env": {
        "ALGENTA_API_KEY": "<SET ALGENTA_API_KEY OR DE_API_KEY BEFORE LAUNCH>",
        "ALGENTA_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

Use `https://api.codna.ai` only in Cloud Managed. `self_hosted` and
`air_gapped` must point `ALGENTA_BASE_URL`, `DE_BASE_URL`, or
`ALGENTA_API_URL` at the self-hosted base URL.
Canonical env vars are `ALGENTA_API_KEY` and `ALGENTA_BASE_URL`; legacy `DE_API_KEY`, `DE_BASE_URL`, and `ALGENTA_API_URL` remain accepted for compatibility.

Reference guide: [`examples/claude-desktop/README.md`](https://github.com/decisionengine/decision-engine/tree/main/examples/claude-desktop/README.md)

## First write-capable action

After enabling write tools:

```text
Connect this CSV as a dataset named "Q2 pipeline", then show me the schema.
```

## Recommended data flow

Use the same low-token governed path as the rest of Algenta:

1. `get_contract()`
2. `list_data(search=..., compact=true)`
3. `get_data_summary(dataset_id)`
4. `get_data_schema(dataset_id)` only when you need the full schema payload
5. `query_data(...)` for one exact metric query
6. `query_batch(...)` for multi-metric governed exact queries
7. `query_sql_report(...)` only for wide read-only rowsets over authorized datasets

## Revoke or disconnect

- Remove the MCP connection from the client
- Revoke the Algenta API key if the machine or workspace should lose access entirely
- Use `disconnect_data` only when you want to remove a registered dataset

## Troubleshooting

- `401 invalid_api_key`: wrong or revoked Bearer token
- `400 unsupported_mcp_auth_configuration`: unsupported auth mode
- `503 mcp_upstream_unavailable`: upstream outage or timeout
- Tools missing after a local config change: restart the MCP host fully
