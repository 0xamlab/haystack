---
icon: clock-rotate-left
description: What's new in Algenta — notable releases, improvements, and fixes to the engine, SDKs, MCP server, and self-hosted deployment, newest first.
---

# Changelog

What's new in Algenta — the engine and the four ways to reach it (HTTP API, SDKs, MCP, self-hosted deployment), newest first. Each entry is dated and tagged; follow the links for the full detail.

{% hint style="info" %}
Algenta is in active preview. Anything that changes existing behavior is called out with a **Changed** tag — pin your SDK version and read these before upgrading.
{% endhint %}

{% update date="2026-06-21" tags="documentation,improvements,changed" %}
## Reworked documentation and a single licensing model

A full documentation refresh on a shared, audited docs system — plus a simpler licensing model.

**New**

- A live, interactive [API explorer](api/explorer.md) — set your key and base URL, then call every endpoint from the browser.
- A friendlier, help-center-style [Troubleshooting](troubleshooting.md) page: a quick-fix table plus expandable cards by symptom.

**Improved**

- A cleaner landing page and consistent navigation across every page.

**Changed**

- Licensing is now a **single v2 format**. The legacy v1 license format and its flags (`--license-version`, `--allow-v1`) were removed — always mint v2. See [Licensing](licensing.md).
{% endupdate %}

{% update date="2026-06-19" tags="new-releases" %}
## Self-hosted install, privacy proof, and end-to-end checks

Everything needed to run Algenta on your own infrastructure — and to prove it stays private.

**New**

- One-command [self-hosted install](self-hosting.md) (Docker Compose: api + worker + Postgres + Redis + object storage).
- The operator **privacy report** (`GET /v1/admin/privacy-report`) — buyer-facing proof a deployment is cloud-free, with a 24-hour egress summary.
- Smoke and persistence proof scripts that exercise the full stack end to end (`self_host_smoke.sh`, `self_host_persistence_proof.sh`).
- The strict **air-gapped** profile (`ALGENTA_DEPLOYMENT_MODE=air_gapped`) and a telemetry-disable switch.
{% endupdate %}

{% update date="2026-06-15" tags="new-releases" %}
## Preview: the engine, four surfaces, and offline licensing

The Algenta engine and every surface that reaches it.

**New**

- The **HTTP API** under `/v1` — Monte Carlo simulation, decisions, governed data, and async jobs.
- **Python and TypeScript SDKs** (`algenta-sdk`, `AlgentaClient`) plus the in-process [`algenta-core` runtime](sdk/python.md).
- The [MCP server](sdk/mcp.md) (`algenta-mcp`) — governed datasets, exact queries, simulations, and agent runs exposed as tools for Cursor, Claude Desktop, and more.
- Durable, fully **offline RS256 licensing** with product entitlements and capacity caps, plus BYOK provider keys.
{% endupdate %}

## Keep going

{% content-ref url="install.md" %}
[install.md](install.md)
{% endcontent-ref %}

{% content-ref url="api/explorer.md" %}
[api/explorer.md](api/explorer.md)
{% endcontent-ref %}
