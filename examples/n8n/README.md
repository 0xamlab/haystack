# Algenta — n8n

Use Algenta from n8n with HTTP Request nodes or MCP-aware AI flows.

- Cloud Managed: `https://api.algenta.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Algenta cloud.

The checked-in workflow JSON templates intentionally use `https://your-algenta-base-url.example`; replace it with Cloud Managed `https://api.algenta.ai` or your self-hosted base URL before import.

## Files

- `workflow_contract.json` — inspect the live machine-readable contract by extracting `x-primary-data-query-contract` from `/openapi.json`
- `workflow_simulate.json` — example HTTP workflow for `/v1/simulate`
- `workflow_query_batch.json` — discover a dataset, fetch a low-token summary, then call `/v1/query/batch`
- `workflow_sql_report.json` — discover a dataset, fetch a low-token summary, then call `/v1/query/sql-report`

## Setup

1. Add an **HTTP Request** node.
2. Start with `GET https://your-algenta-base-url.example/v1/meta/contract`.
   If an older self-hosted node still returns `404` there, call
   `https://your-algenta-base-url.example/openapi.json` (or your self-host base URL) and read
   `x-primary-data-query-contract` instead.
   The checked-in `workflow_contract.json`, `workflow_query_batch.json`, and
   `workflow_sql_report.json` already do this by reading `/openapi.json`
   directly, so they stay compatible with both current hosted nodes and older
   self-hosted nodes.
3. Continue with `GET https://your-algenta-base-url.example/v1/data?search=orders&compact=1&limit=5`.
4. Add `Authorization: Bearer <YOUR_ALGENTA_API_KEY>`.
5. Follow with `POST https://your-algenta-base-url.example/v1/query` or `POST https://your-algenta-base-url.example/v1/query/batch`.

Replace `https://your-algenta-base-url.example` with Cloud Managed
`https://api.algenta.ai` or your self-hosted deployment before enabling the
workflow. The placeholder key above follows the same rule: Cloud Managed uses a
Cloud Managed key, while `self_hosted` and `air_gapped` use the API key
provisioned by that deployment.

## First workflow

Use `workflow_query_batch.json` for the primary governed metrics flow, `workflow_sql_report.json` for wide read-only rowsets, and `workflow_simulate.json` only when you need simulations. The primary data/query path is:

- `GET /v1/meta/contract`
- `/openapi.json` plus `x-primary-data-query-contract` as the raw-HTTP fallback on older self-hosted nodes
- `GET /v1/data`
- `GET /v1/data/{dataset_id}/summary`
- `POST /v1/query` or `POST /v1/query/batch`
- `POST /v1/query/sql-report` for wide read-only rowsets

Then map the returned `result`, `request_id`, and `latency_ms` into downstream nodes.

For persisted runtime follow-up or approval flows, add read-only HTTP nodes for:

- `GET /v1/agent/runs`
- `GET /v1/agent/runs/checkpoints`
- `GET /v1/agent/runs/mission-events`
- `GET /v1/agent/runs/telemetry`
- `GET /v1/audit-logs/artifacts`
- `GET /v1/execution/policy/snapshots`

That gives the workflow access to persisted run inventory, checkpoint and
mission-trace inspection, runtime telemetry, immutable audit artifacts, and
policy snapshots before it fans out into Slack, approvals, or downstream APIs.

## Revoke or disconnect

- Remove the node credentials or environment variable
- Revoke the Algenta API key if the workflow should lose access entirely
