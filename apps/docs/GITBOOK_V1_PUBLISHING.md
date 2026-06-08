# GitBook v1 Publishing Guide

This repository does not contain a native GitBook workspace config.

Use this guide plus [apps/docs/gitbook_v1_navigation.json](/Users/angel/Developer/decision-engine/apps/docs/gitbook_v1_navigation.json) as the source of truth when configuring the external GitBook workspace.

## Scope

GitBook v1 is the **self-hosted service product docs set**.

The primary reader journey is:

1. Overview
2. Quickstart
3. first successful `curl`
4. Operations
5. Operations (Advanced)

Do not publish GitBook v1 as a repo mirror.

## Sidebar

Use these top-level sidebar labels exactly:

- `🧭 Overview`
- `⚡ Quickstart`
- `⚙️ Operations`
- `🛠️ Operations (Advanced)`
- `🔐 API Authentication`
- `📦 SDKs`

Only top-level sidebar labels get icons.

Do not add icons to page titles.

## Page mapping

| GitBook section | Page title | Repo source |
| --- | --- | --- |
| `🧭 Overview` | `Overview` | `apps/docs/docs/index.md` |
| `⚡ Quickstart` | `Quickstart` | `apps/docs/docs/quickstart.md` |
| `⚙️ Operations` | `Operations` | `apps/docs/docs/operations/index.md` |
| `⚙️ Operations` | `Setup & Configuration` | `apps/docs/docs/self-hosting.md` |
| `⚙️ Operations` | `TLS & Reverse Proxy` | `apps/docs/docs/operations/tls-and-reverse-proxy.md` |
| `⚙️ Operations` | `Logs & Metrics` | `apps/docs/docs/operations/logs-and-metrics.md` |
| `⚙️ Operations` | `Upgrade & Rollback` | `apps/docs/docs/operations/upgrade-and-rollback.md` |
| `🛠️ Operations (Advanced)` | `Operations (Advanced)` | `apps/docs/docs/operations-advanced/index.md` |
| `🛠️ Operations (Advanced)` | `Backup & Recovery` | `apps/docs/docs/operations-advanced/backup-and-recovery.md` |
| `🛠️ Operations (Advanced)` | `Troubleshooting` | `apps/docs/docs/operations-advanced/troubleshooting.md` |
| `🛠️ Operations (Advanced)` | `Support Boundaries` | `apps/docs/docs/operations-advanced/support-boundaries.md` |
| `🔐 API Authentication` | `API Authentication` | `apps/docs/docs/api-reference/authentication.md` |
| `📦 SDKs` | `Python SDK` | `apps/docs/docs/sdks/python.md` |
| `📦 SDKs` | `TypeScript SDK` | `apps/docs/docs/sdks/typescript.md` |

## Exclude from the primary nav

Keep these pages out of the primary launch sidebar:

- `apps/docs/docs/integrations/local-runtime.md`
- `apps/docs/docs/mcp.md`
- `apps/docs/docs/integrations/overview.md`
- `apps/docs/docs/integrations/chatgpt-actions.md`
- `apps/docs/docs/integrations/claude-codex.md`
- `apps/docs/docs/integrations/n8n.md`
- `apps/docs/docs/integrations/zapier.md`
- `apps/docs/docs/integrations/make.md`
- `apps/docs/docs/integrations/langgraph.md`
- `apps/docs/docs/integrations/power-automate.md`
- `apps/docs/docs/integrations/azure-ai-studio.md`
- `apps/docs/docs/changelog.md`
- `apps/docs/docs/competitor-compatibility.md`
- `apps/docs/docs/connect-register-sources.md`
- `apps/docs/docs/api-reference/capability-plane.md`
- `apps/docs/docs/direct-api-client.md`
- `apps/docs/docs/supported-secondary-modes.md`

These pages may remain published separately, but they must not define the primary self-hosted launch path.

## Visual rules

Use only these status markers:

- `✅` supported / ready
- `⚠️` warning / best effort
- `❌` not supported / failure

Use only these callout types:

- Info
- Warning
- Critical

Examples:

- use **Warning** for operator-only guidance
- use **Critical** for one-time behaviors like bootstrap API key display

## Writing rules

- Keep page H1 titles noun-based.
- Keep Overview short.
- Keep Quickstart limited to:
  - install
  - health
  - bootstrap API key
  - first `/v1/simulate`
  - expected output
- Keep Backup & Recovery public, but only under **Operations (Advanced)**.
- Keep Troubleshooting command-first.
- Keep Support Boundaries as a table.

## Publish checklist

Before publishing the external GitBook workspace:

1. Run:
   ```bash
   make docs-gitbook-verify
   ```
2. Confirm the sidebar matches [apps/docs/gitbook_v1_navigation.json](/Users/angel/Developer/decision-engine/apps/docs/gitbook_v1_navigation.json).
3. Confirm Overview is the default landing page.
4. Confirm Quickstart is reachable in one click from Overview.
5. Confirm Backup & Recovery is not shown in Overview or Quickstart.
6. Confirm the excluded pages are not in the primary launch nav.

## Source of truth

Use these files when updating GitBook v1:

- [apps/docs/gitbook_v1_navigation.json](/Users/angel/Developer/decision-engine/apps/docs/gitbook_v1_navigation.json)
- [scripts/check_gitbook_v1_docs.py](/Users/angel/Developer/decision-engine/scripts/check_gitbook_v1_docs.py)
- [scripts/export_gitbook_v1_pack.py](/Users/angel/Developer/decision-engine/scripts/export_gitbook_v1_pack.py)
- [apps/docs/docs/index.md](/Users/angel/Developer/decision-engine/apps/docs/docs/index.md)
- [apps/docs/docs/quickstart.md](/Users/angel/Developer/decision-engine/apps/docs/docs/quickstart.md)
