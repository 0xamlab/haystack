---
icon: clock-rotate-left
description: What's new in Algenta — notable releases, improvements, and fixes to the engine, SDKs, MCP server, and self-hosted deployment, newest first.
---

# Changelog

What's new in Algenta — the engine and the four ways to reach it (HTTP API, SDKs, MCP, self-hosted deployment), newest first. Each entry is dated and tagged; follow the links for the full detail.

{% hint style="info" %}
We call out behavior changes with a **Changed** tag — pin your SDK version and read these before upgrading.
{% endhint %}

{% update date="2026-06-21" tags="documentation,improvements,changed" %}
## Reworked documentation and a single licensing model

A full documentation refresh on a shared, audited docs system — plus a simpler licensing model.

**New**

- A live, interactive [API explorer](api/explorer.md) — set your key and base URL, then call every endpoint from the browser.
- A friendlier, help-center-style [Troubleshooting](troubleshooting.md) page: a quick-fix table plus expandable cards by symptom.
- A [Connectors](connectors/overview.md) section — overview, full reference, and per-source guides (Snowflake, BigQuery, ClickHouse, REST).
- Agentic and long-running guides: [run an agent](guides/agent-runs.md), [async jobs](guides/async-jobs.md), and [repository intelligence](guides/repository-intelligence.md).
- Deploy-and-integrate guides: [BYOK](guides/byok.md), [device binding](guides/device-binding.md), [air-gapped](guides/air-gapped.md), and [CI/CD](guides/ci-cd.md).
- [Testing with Algenta](sdk/testing.md) and deeper SDK coverage, plus operate guides for [monitoring](operate/monitoring.md) and [encryption at rest](operate/byok-kms.md).
- [Using these docs with AI](help/ai-access.md) — the `llms.txt` context files, per-page Markdown, and the docs MCP server.

**Improved**

- A cleaner landing page and consistent navigation across every page.

**Changed**

- Licensing now uses a **single v2 format** — install the v2 license file Algenta provides. The legacy v1 format was retired. See [Licensing](licensing.md).
{% endupdate %}

{% update date="2026-06-19" tags="new-releases" %}
## Self-hosted install, privacy proof, and end-to-end checks

Everything needed to run Algenta on your own infrastructure — and to prove it stays private.

**New**

- One-command [self-hosted install](self-hosting.md) (Docker Compose: api + worker + Postgres + Redis + object storage).
- A **privacy report** (`GET /v1/admin/privacy-report`) that proves a deployment is cloud-free, with a 24-hour egress summary.
- Smoke and persistence proof scripts that exercise the full stack end to end (`self_host_smoke.sh`, `self_host_persistence_proof.sh`).
- The strict **air-gapped** profile (`ALGENTA_DEPLOYMENT_MODE=air_gapped`) and a telemetry-disable switch.
{% endupdate %}

{% update date="2026-06-15" tags="new-releases" %}
## The engine, four surfaces, and offline licensing

The Algenta engine and every surface that reaches it.

**New**

- The **HTTP API** under `/v1` — Monte Carlo simulation, decisions, governed data, and async jobs.
- **Python SDK** (`algenta-sdk`, `AlgentaClient`) plus source-built TypeScript and in-process [`algenta` runtime](sdk/python.md) surfaces that are rolling toward public registry release.
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
