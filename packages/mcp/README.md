# Algenta MCP Server

<!-- mcp-name: io.github.thyn-ai/algenta -->

**Model Context Protocol server for [Algenta](https://algenta.ai) — self-hosted building blocks for AI applications.**

Any MCP-capable agent operates the engine — metered and audited like every other caller. This
server gives MCP-compatible agents access to governed data discovery, exact queries, decisions,
simulations, runtime utilities, and account operations through the same public API contract used
by the Algenta SDKs. The Algenta engine itself is proprietary; everything in this package is
Apache-2.0.

Full reference: [docs.algenta.ai/sdk/mcp](https://docs.algenta.ai/sdk/mcp)

## Install

```bash
pipx install algenta-mcp
```

`pip install algenta-mcp` is also supported. The package includes its MCP transport dependencies;
users do not install or manage a separate protocol package.

## Configure

```bash
export ALGENTA_API_KEY="<YOUR_ALGENTA_API_KEY>"
export ALGENTA_BASE_URL="https://api.algenta.ai"
```

Use your deployment URL for self-hosted Algenta. Private deployment profiles fail closed rather
than silently sending traffic to Algenta Cloud.

## Cursor and Claude Desktop

`algenta-mcp` uses stdio by default. Add this server to Cursor's `~/.cursor/mcp.json` or Claude
Desktop's MCP configuration:

```json
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
```

Restart the client after changing its MCP configuration.

## Codex

Add the stdio server to `~/.codex/config.toml`:

```toml
[mcp_servers.algenta]
command = "algenta-mcp"

[mcp_servers.algenta.env]
ALGENTA_API_KEY = "<YOUR_ALGENTA_API_KEY>"
ALGENTA_BASE_URL = "https://api.algenta.ai"
```

Keep credentials in user-level configuration or environment variables, not in a repository.

## Streamable HTTP

Start the remote transport:

```bash
algenta-mcp --mode http --port 8001
```

The standalone server binds to `127.0.0.1` by default. Set `ALGENTA_MCP_HOST=0.0.0.0` only when
an authenticated container ingress or gateway must expose it to another host.

Connect modern clients to:

```text
http://localhost:8001/mcp
```

The endpoint uses stateless Streamable HTTP. It dual-serves both protocol eras from the same
endpoint: a legacy `initialize` handshake negotiates `2025-11-25`, and a modern per-request caller
(the `MCP-Protocol-Version` header plus the `2026-07-28` `_meta` envelope, no handshake) gets
`2026-07-28`, including the built-in `server/discover` method. Algenta pins the official Python MCP
SDK `2.0.0`. Deprecated `/mcp/sse` and `/mcp/messages` routes remain for older clients but are not
the default.

LangChain example:

```python
import os

from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient(
    {
        "algenta": {
            "transport": "http",
            "url": "http://localhost:8001/mcp",
            "headers": {
                "Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"
            },
        }
    }
)

tools = await client.get_tools()
```

## Verify

The human-readable discovery route is available alongside the protocol endpoint:

```bash
curl -s http://localhost:8001/mcp/tools | jq '.tools | length'
```

In an MCP client, call `get_contract` first, then use `list_data` and `get_data_summary` before
querying a dataset. Tool names, descriptions, and input schemas are returned by MCP `tools/list`.

## Security

- Tool calls use `Authorization: Bearer <ALGENTA_API_KEY>` or the configured process credential.
- Streamable HTTP validates `Host` and `Origin` to prevent DNS-rebinding access.
- Standalone HTTP binds to loopback unless `ALGENTA_MCP_HOST` is explicitly changed.
- Error payloads redact API-key material.
- `ALGENTA_BASE_URL` is required when cloud access is disabled.
- Put an authenticating gateway in front of a publicly reachable standalone MCP port.

## Compatibility

Canonical environment variables are `ALGENTA_API_KEY` and `ALGENTA_BASE_URL`. Legacy
`DE_API_KEY`, `DE_BASE_URL`, and `ALGENTA_API_URL` remain accepted for existing deployments.

## License

Apache-2.0
