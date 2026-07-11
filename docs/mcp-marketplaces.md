---
icon: plug
description: Internal distribution checklist for publishing Algenta MCP to public registries and marketplaces.
---

# Distributing the Algenta MCP server to public marketplaces

Goal: `algenta-mcp` discoverable + one-click installable everywhere — Cursor, Claude, Codex, and every public
MCP directory. This is the distribution manifest: what's in the repo to enable it, and the status/step per
marketplace.

## In-repo enablers (done)
- **`server.json`** (repo root) — the [Official MCP Registry](https://registry.modelcontextprotocol.io) manifest: name `io.github.thyn-ai/algenta`, the `algenta-mcp` PyPI package (stdio), a rich description, and the `ALGENTA_API_KEY` / `ALGENTA_BASE_URL` env schema so directories render the install form.
- **`smithery.yaml`** (repo root) — [Smithery](https://smithery.ai) config: config schema + `commandFunction` for one-click install.
- **`packages/mcp/README.md`** — the `<!-- mcp-name: io.github.thyn-ai/algenta -->` ownership marker (proves the PyPI package ↔ registry name) + copy-paste configs for Cursor / Claude / Codex / Zed / n8n / LangChain / etc.
- **`.github/workflows/publish-mcp.yml`** — publishes `server.json` to the Official Registry via GitHub OIDC.

## Leverage: the Official MCP Registry feeds most of the others
Publishing to `registry.modelcontextprotocol.io` (via `publish-mcp.yml`) is the single highest-leverage step —
Glama, PulseMCP, mcp.so, the Cursor directory and others **mirror/crawl the official registry**. So the flow is:

1. Publish `algenta-mcp` to **PyPI** (via `release-sdks.yml`, token auth).
2. Dispatch **`publish-mcp.yml`** → registers `io.github.thyn-ai/algenta` in the Official Registry.
3. The mirrors pick it up automatically; the few that need a manual nudge are listed below.

## Per-marketplace status

| Marketplace | How it gets Algenta | Action |
|---|---|---|
| **Official MCP Registry** | `server.json` + `publish-mcp.yml` (OIDC) | dispatch `publish-mcp.yml` after PyPI is live |
| **Smithery** (smithery.ai) | `smithery.yaml` in the repo | connect the repo at smithery.ai/new (owner, one-time) |
| **Glama** (glama.ai/mcp/servers) | crawls GitHub + the official registry | auto after registry publish; optional claim at glama.ai |
| **PulseMCP** (pulsemcp.com) | mirrors the official registry + GitHub | auto after registry publish |
| **mcp.so** | community directory (official registry + submissions) | auto after registry publish; optional submit |
| **Cursor directory** | pulls the official registry | auto after registry publish |
| **Awesome MCP Servers** (punkpeye/awesome-mcp-servers) | curated GitHub list | open a PR adding Algenta under "Developer Tools" |
| **mcp-get / mcpservers.org** | registries | optional submit |

## Next steps
1. Publish `algenta-mcp` (+ `algenta-sdk` it depends on) to PyPI.
2. Dispatch `publish-mcp.yml` (Actions → publish-mcp → Run) once the PyPI version resolves.
3. One-time marketplace connects: Smithery (connect repo), and an Awesome-MCP-Servers PR. The rest auto-index
   from the Official Registry within their crawl window.

Keep `server.json` `version` in lockstep with the published `algenta-mcp` version before dispatching.
