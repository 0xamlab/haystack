---
icon: plug
description: Install the Algenta MCP server from the Official MCP Registry — io.github.thyn-ai/algenta — into Cursor, Claude Desktop, Claude Code, or Codex, passing your ALGENTA_API_KEY.
---

# Install Algenta from the MCP Registry

The Algenta MCP server exposes the whole engine — governed data, decisions, simulations, agent runs, and repository intelligence — as Model Context Protocol tools your AI client can call. It is published to the **Official MCP Registry** as `io.github.thyn-ai/algenta`, so registry-aware clients and directories can discover and install it by name. Under the hood it runs the `algenta-mcp` package and authenticates to your deployment with `ALGENTA_API_KEY`.

This page connects it to the most common clients. For the tool catalog and transports, see [MCP server](mcp.md); for the tools grouped by capability, see [MCP tools overview](../mcp-tools/overview.md).

## Before you start

- An Algenta API key exported as `ALGENTA_API_KEY`. Get one from [Authentication & API keys](../authentication.md).
- Your base URL: `https://api.algenta.ai` (hosted) or `http://localhost:8000` (self-hosted). Set it as `ALGENTA_BASE_URL`.
- The server package on your PATH:

```bash title="install-algenta-mcp.sh"
pipx install algenta-mcp    # or: pip install algenta-mcp
```

{% hint style="info" %}
`algenta-mcp` runs the **stdio** transport by default — the right choice for the desktop clients below. The canonical environment variables are `ALGENTA_API_KEY` and `ALGENTA_BASE_URL` (legacy `DE_API_KEY` / `DE_BASE_URL` are still accepted).
{% endhint %}

The Official MCP Registry advertises both the PyPI stdio package and the hosted
Streamable HTTP endpoint at `https://api.algenta.ai/mcp`. Registry-aware clients
that support remote servers can discover that endpoint directly and prompt for
an `Authorization: Bearer $ALGENTA_API_KEY` header.

## Connect your client

{% tabs %}
{% tab title="Cursor" %}
Add the server to `~/.cursor/mcp.json`:

```json title="~/.cursor/mcp.json"
{
  "mcpServers": {
    "algenta": {
      "command": "algenta-mcp",
      "env": {
        "ALGENTA_API_KEY": "$ALGENTA_API_KEY",
        "ALGENTA_BASE_URL": "https://api.algenta.ai"
      }
    }
  }
}
```

Reload Cursor, then reference the server in chat: *"@algenta simulate this business case…"*.
{% endtab %}

{% tab title="Claude Desktop" %}
Add the server to `claude_desktop_config.json` (on macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json title="claude_desktop_config.json"
{
  "mcpServers": {
    "algenta": {
      "command": "algenta-mcp",
      "env": {
        "ALGENTA_API_KEY": "$ALGENTA_API_KEY",
        "ALGENTA_BASE_URL": "https://api.algenta.ai"
      }
    }
  }
}
```

Restart Claude Desktop. `algenta` appears in the tools panel.
{% endtab %}

{% tab title="Claude Code" %}
Add the server with the Claude Code CLI (`-e` passes environment variables; everything after `--` is the launch command):

```bash title="claude-code-add.sh"
claude mcp add algenta \
  -e ALGENTA_API_KEY=$ALGENTA_API_KEY \
  -e ALGENTA_BASE_URL=https://api.algenta.ai \
  -- algenta-mcp
```

Verify it registered:

```bash title="claude-code-list.sh"
claude mcp list
```
{% endtab %}

{% tab title="Codex" %}
Add the local stdio server to `~/.codex/config.toml`:

```toml title="~/.codex/config.toml"
[mcp_servers.algenta]
command = "algenta-mcp"
env = { ALGENTA_API_KEY = "$ALGENTA_API_KEY", ALGENTA_BASE_URL = "https://api.algenta.ai" }
```

Restart Codex so it picks up the new server.

For Algenta Cloud, Codex can connect directly to the Streamable HTTP endpoint instead. Export `ALGENTA_API_KEY`, then use:

```toml title="~/.codex/config.toml"
[mcp_servers.algenta]
url = "https://api.algenta.ai/mcp"
bearer_token_env_var = "ALGENTA_API_KEY"
```

For repo-specific Codex workflows, keep durable project instructions in `AGENTS.md` and keep MCP credentials in `~/.codex/config.toml` or a trusted project `.codex/config.toml`. Codex reads the `AGENTS.md` instruction chain when it starts a run, and the same MCP config is shared by the CLI and IDE extension.
{% endtab %}
{% endtabs %}

{% hint style="warning" %}
On a **self-hosted** or **air-gapped** deployment, point `ALGENTA_BASE_URL` at your own engine (for example `http://localhost:8000`). Private profiles fail closed and never fall back to the Algenta cloud.
{% endhint %}

## Install via Smithery

[Smithery](https://smithery.ai) builds and runs the server from the repository's `smithery.yaml`. Install it into a client with the Smithery CLI:

```bash title="smithery-install.sh"
npx -y @smithery/cli install algenta --client cursor
```

Swap `--client` for `claude`, `claude-code`, or another supported target. Smithery reads `smithery.yaml` for the run command and prompts for `ALGENTA_API_KEY` and `ALGENTA_BASE_URL`.

## Verify the connection

{% hint style="success" %}
**Expected result** — your client lists the Algenta tools (for example `get_contract`, `simulate`, `list_data`, `triage_repository`). Ask it to *"call get_contract and summarize the available Algenta tools"* — a successful reply confirms the key and base URL are wired correctly.
{% endhint %}

## Discoverable everywhere

Because Algenta is in the Official MCP Registry, third-party directories index it automatically — no extra publishing step:

- **Glama** — mcp server catalog and quality scoring.
- **PulseMCP** — server discovery and changelogs.
- **mcp.so** — searchable MCP server index.

Searching any of them for "Algenta" surfaces the same `io.github.thyn-ai/algenta` server.

## Troubleshooting

<details>
<summary>The client shows no Algenta tools</summary>

Confirm `algenta-mcp` is on your PATH (`pipx install algenta-mcp`) and that the config file is valid JSON/TOML, then fully restart the client. Desktop clients only load MCP config at startup.
</details>

<details>
<summary>Tool calls fail with 401</summary>

`ALGENTA_API_KEY` is missing or invalid. Set it in the client's `env` block (or shell) and confirm it matches an active key — see [Authentication & API keys](../authentication.md).
</details>

<details>
<summary>It cannot reach the engine</summary>

Check `ALGENTA_BASE_URL`. Use `https://api.algenta.ai` for hosted, or your own origin for self-hosted. The engine must be reachable from the machine running the client.
</details>

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Browse the MCP tools</strong></td><td>Every tool, grouped by capability.</td><td><a href="../mcp-tools/overview.md">mcp-tools/overview.md</a></td></tr>
<tr><td><strong>Read the MCP server guide</strong></td><td>Transports, HTTP mode, and options.</td><td><a href="mcp.md">mcp.md</a></td></tr>
<tr><td><strong>Get an API key</strong></td><td>Mint the key your client will use.</td><td><a href="../authentication.md">authentication.md</a></td></tr>
</tbody></table>
