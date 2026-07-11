---
icon: table-list
description: One-page cheat sheet — every common Algenta task mapped to its HTTP endpoint, de CLI command, and Python SDK call, plus the handful of env vars you need most.
---

# Quick reference

The fastest lookup in the docs: find your task, copy the call. Each row shows the same operation across the three surfaces. Full detail lives on the linked pages and in the [API explorer](../api/explorer.md).

## Reach the engine

| Surface | Use it for | Start here |
| --- | --- | --- |
| **HTTP API** (`/v1`) | Any language, zero install | [API overview](../api/overview.md) |
| **Python SDK** | Live typed client over the API | [Python SDK](../sdk/python.md) |
| **TypeScript SDK** | Live typed client from npm (`algenta-sdk`) | [TypeScript SDK](../sdk/typescript.md) |
| **MCP server** | AI agents (Cursor, Claude Desktop) | [MCP server](../sdk/mcp.md) |
| **`de` CLI** | The terminal | [CLI reference](../cli.md) |

## Common tasks

| Task | HTTP | `de` CLI | Python SDK |
| --- | --- | --- | --- |
| Check the engine is up | `GET /v1/health` | `de health` | — |
| Authenticate a request | `Authorization: Bearer $ALGENTA_API_KEY` | `de config set-key $ALGENTA_API_KEY` | `AlgentaClient(api_key=…)` |
| Run a simulation | `POST /v1/simulate` | `de simulate run.json` | `client.simulate(...)` |
| Get a recommendation | `POST /v1/recommend` | `de recommend run.json` | `client.recommend(...)` |
| Query governed data | `POST /v1/query` | `de data query-batch …` | `client.query(...)` |
| List / summarize data | `GET /v1/data` · `GET /v1/data/{id}/summary` | `de data list` · `de data summary $DATASET_ID` | `client.list_data()` |
| Connect a data source | `POST /v1/connectors` | `de connectors create …` | `client.create_connector(...)` |
| Log a decision + outcome | `POST /v1/decisions` · `PATCH /v1/decisions/{id}/outcome` | `de decisions log …` · `de decisions outcome …` | `client.log_decision(...)` |
| Run an agent | `POST /v1/agent/run` | `de agent-runs create …` | `client.create_agent_run(...)` |
| Submit an async job | `POST /v1/jobs` · `GET /v1/jobs/{id}/result` | `de job submit …` · `de job result $JOB_ID` | `client.submit_job(...)` |
| Check usage & limits | `GET /v1/usage` · `GET /v1/limits` | `de account usage` · `de account limits` | `client.usage()` |

## Env vars you reach for most

| Variable | What it does |
| --- | --- |
| `ALGENTA_API_KEY` | Your bearer credential (`DE_API_KEY` is a legacy alias). |
| `ALGENTA_BASE_URL` | The engine URL for self-hosted clients (absolute, e.g. `http://localhost:8000`). |
| `ALGENTA_DEPLOYMENT_MODE` | `saas` \| `self_hosted` \| `air_gapped` \| … — the privacy/egress profile. |
| `ALGENTA_PRODUCT` | The edition surface to expose (for example, `algenta`). |

## When something breaks

Two checks isolate most problems: `curl http://localhost:8000/v1/health` and `python3 scripts/license_status.py`. Then jump to [Troubleshooting](../troubleshooting.md). New to a term? See the [Glossary](glossary.md).
