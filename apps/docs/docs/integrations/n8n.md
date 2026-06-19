---
sidebar_position: 4
---

# n8n

Use Algenta in n8n to add governed dataset discovery, exact queries, batch exact queries, constrained SQL reports, and simulations to any workflow.

## Prerequisites

- An Algenta API key
- An n8n workflow with HTTP Request or AI-agent nodes
- Read-only access unless the workflow must mutate datasets

Use one base URL consistently across every n8n HTTP node:

- Cloud Managed: `https://api.codna.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Codna cloud.

## Setup

1. In your n8n workflow, add an **HTTP Request** node
2. Start with the live contract:
   - **Method**: `GET`
   - **URL**: `https://your-algenta-base-url.example/v1/meta/contract`
   - **Headers**: `Authorization` = `Bearer <YOUR_ALGENTA_API_KEY>`
   - **Older self-hosted fallback**: if that returns `404`, call `https://your-algenta-base-url.example/openapi.json` (or your self-host base URL) and read `x-primary-data-query-contract`
3. Continue with a read-only dataset discovery call:
   - **Method**: `GET`
   - **URL**: `https://your-algenta-base-url.example/v1/data?search=orders&compact=1&limit=5`
   - **Headers**: `Authorization` = `Bearer <YOUR_ALGENTA_API_KEY>`
4. Add another **HTTP Request** node for the exact query:
   - **Method**: `POST`
   - **URL**: `https://your-algenta-base-url.example/v1/query`
   - **Headers**: `Authorization` and `Content-Type: application/json`
4. Set **Body** to JSON:

```json
{
  "dataset_id": "orders_facts",
  "metric": { "role": "metric", "hint": "order_count" },
  "group_by": ["order_month"],
  "filter": {
    "time_filter": "last_year",
    "conditions": [{ "dimension_hint": "status", "op": "eq", "value": "completed" }]
  },
  "limit": 12,
  "order": "desc"
}
```

For multi-metric prompts, call `POST /v1/query/batch` instead of chaining many single-query nodes. For wide rowsets, use `POST /v1/query/sql-report`.

Replace `https://your-algenta-base-url.example` with Cloud Managed
`https://api.codna.ai` or your self-hosted base URL before enabling the
workflow.

Example artifacts:

- [`examples/n8n/workflow_contract.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/n8n/workflow_contract.json)
- [`examples/n8n/workflow_query_batch.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/n8n/workflow_query_batch.json)
- [`examples/n8n/workflow_sql_report.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/n8n/workflow_sql_report.json)
- [`examples/n8n/workflow_simulate.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/n8n/workflow_simulate.json)

The checked-in n8n workflows already use `/openapi.json` and extract
`x-primary-data-query-contract`, so they stay compatible with older self-hosted
nodes that still return `404` for `/v1/meta/contract`.
That contract also exposes `governed_filter_contract`, so the workflow can
inspect selector fields and allowed operators instead of hard-coding SQL-style
predicates.

## First workflow

Start with one governed query node, then pass:

- the selected `dataset_id`
- the query `result`
- `request_id`
- `latency_ms`

to Slack, Airtable, Notion, or approval steps.

For persisted runtime follow-up or approval workflows, add HTTP Request nodes
for:

- `GET /v1/agent/runs`
- `GET /v1/agent/runs/checkpoints`
- `GET /v1/agent/runs/mission-events`
- `GET /v1/agent/runs/telemetry`
- `GET /v1/audit-logs/artifacts`
- `GET /v1/execution/policy/snapshots`

Those surfaces let an n8n workflow inspect replay candidates, checkpoint
history, mission traces, runtime telemetry, immutable audit artifacts, and
execution-policy lineage before deciding whether to notify, branch, or call
another service.

## Typical use cases

- Inspect the live machine-readable contract with `GET /v1/meta/contract`
- On older self-hosted nodes that still return `404`, inspect `x-primary-data-query-contract` from `/openapi.json` instead
- Discover datasets with `GET /v1/data?search=...&compact=1`
- Get a low-token summary with `GET /v1/data/{dataset_id}/summary`
- Run one exact metric query with `POST /v1/query`
- Run multiple governed metrics in one request with `POST /v1/query/batch`
- Return wide read-only rowsets with `POST /v1/query/sql-report`
- Keep `POST /v1/simulate` for decision-analysis workflows rather than the default data path
- Inspect persisted agent-run inventory with `GET /v1/agent/runs`
- Inspect checkpoint, mission-event, or telemetry records with `GET /v1/agent/runs/checkpoints`, `GET /v1/agent/runs/mission-events`, and `GET /v1/agent/runs/telemetry`
- Review immutable audit artifacts with `GET /v1/audit-logs/artifacts`
- Review stored policy lineage with `GET /v1/execution/policy/snapshots`

## Write actions

Only add dataset mutations if the workflow needs them:

- `/v1/data/connect`
- `/v1/data/{dataset_id}/refresh`
- `/v1/data/{dataset_id}`

## Revoke or disconnect

- Remove the credential or environment variable from n8n
- Revoke the Algenta API key if the workflow should lose access entirely

## Troubleshooting

- `401 invalid_api_key`: wrong Bearer token or missing header
- `429 rate_limit_exceeded`: back off and honor `Retry-After`
- Empty downstream fields: inspect the HTTP node output and confirm you are mapping the Algenta response body, not the full transport envelope
