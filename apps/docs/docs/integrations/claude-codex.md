---
sidebar_position: 3
---

# Claude and Codex

Connect Algenta to Claude, Codex, and other MCP clients with the canonical `v1` MCP contract.

## Canonical connection

Endpoint:

```text
https://api.algenta.ai/mcp/sse
```

Auth:

```text
Authorization: Bearer de_live_...
```

## When to use which mode

- Use the hosted remote MCP endpoint when your client supports a remote MCP URL.
- Use the local stdio bridge when your client only knows how to launch a local MCP process.

## Remote MCP setup

1. Add a new remote MCP server in your client.
2. Set the URL to `https://api.algenta.ai/mcp/sse`.
3. Add `Authorization: Bearer de_live_...`.
4. Start in read-only mode if your client supports tool scoping.

First prompt:

```text
List my datasets and explain which one looks best for a revenue-risk analysis.
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
        "ALGENTA_API_KEY": "de_live_YOUR_KEY_HERE",
        "ALGENTA_BASE_URL": "https://api.algenta.ai"
      }
    }
  }
}
```

Reference guide: [`examples/claude-desktop/README.md`](https://github.com/decisionengine/decision-engine/tree/main/examples/claude-desktop/README.md)

## First write-capable action

After enabling write tools:

```text
Connect this CSV as a dataset named "Q2 pipeline", then show me the schema.
```

## Revoke or disconnect

- Remove the MCP connection from the client
- Revoke the Algenta API key if the machine or workspace should lose access entirely
- Use `disconnect_data` only when you want to remove a registered dataset

## Troubleshooting

- `401 invalid_api_key`: wrong or revoked Bearer token
- `400 unsupported_mcp_auth_configuration`: unsupported auth mode
- `503 mcp_upstream_unavailable`: upstream outage or timeout
- Tools missing after a local config change: restart the MCP host fully
