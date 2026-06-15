---
sidebar_position: 2
---

# ChatGPT Actions

Let ChatGPT call Codna automatically during conversations.

## Prerequisites

- An Codna API key
- A GPT with Actions enabled
- Read access for discovery and query routes

Use one base URL consistently for the OpenAPI import and every subsequent
request:

- Cloud Managed: `https://api.codna.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Codna cloud.

## Setup

1. In ChatGPT, go to **Explore** → **Create** → **Configure** → **Actions**
2. Click **Import from URL**: `https://your-algenta-base-url.example/openapi.json`
   and replace the placeholder with Cloud Managed `https://api.codna.ai` or
   `https://your-algenta-host.example/openapi.json` for `self_hosted` / `air_gapped`
3. Configure authentication as `Authorization: Bearer <api_key>`
4. Start read-only unless the GPT must connect or refresh datasets

The OpenAPI import path is also the compatibility path for older self-hosted
nodes. If `/v1/meta/contract` is not mounted yet there, read
`x-primary-data-query-contract` from `/openapi.json` instead.
That machine-readable contract includes
`primary_data_query_contract.governed_filter_contract`, so raw GPT actions can
inspect selector fields and allowed filter operators instead of inventing
private predicate syntax.

## OpenAPI Actions file

The complete spec is at [`examples/chatgpt-actions/openapi_actions.yaml`](https://github.com/decisionengine/decision-engine/tree/main/examples/chatgpt-actions/openapi_actions.yaml).

That action surface now includes the primary read-only Codna flow plus
persisted runtime and control-plane review:

- `GET /v1/meta/contract`
- `GET /v1/data`
- `GET /v1/data/{dataset_id}/summary`
- `POST /v1/query`
- `POST /v1/query/batch`
- `POST /v1/query/sql-report`
- `GET /v1/agent/runs`
- `GET /v1/agent/runs/checkpoints`
- `GET /v1/agent/runs/mission-events`
- `GET /v1/agent/runs/telemetry`
- `GET /v1/audit-logs/artifacts`
- `GET /v1/execution/policy/snapshots`
- `POST /v1/simulate`

## First prompt

> "Find the dataset that matches orders, summarize it, then return the overall completed-order total and a monthly breakdown for the last 12 months."

That keeps the GPT on the low-token read-only path:

1. `GET /v1/meta/contract`
2. `GET /v1/data?search=orders&compact=1`
3. `GET /v1/data/{dataset_id}/summary`
4. `POST /v1/query/batch`

## First write-capable action

After enabling write actions:

> "Connect this CSV as a dataset named `sales_pipeline`, then show me the schema."

## Tips

- Keep the GPT read-only by default and let it start with `search + compact` discovery.
- Use `GET /v1/meta/contract` when the GPT needs the live machine-readable Codna capability map.
- For older self-hosted nodes that still return `404` there, use `/openapi.json`
  and read `x-primary-data-query-contract` instead.
- Read `primary_data_query_contract.governed_filter_contract` when the GPT must
  build deterministic status/category/numeric/null filters without using SQL.
- Use `POST /v1/query/batch` when one prompt needs multiple governed metrics.
- Use `POST /v1/query/sql-report` only for wide read-only rowsets over already authorized datasets.
- Use the persisted runtime review endpoints when the GPT must inspect run
  lineage, checkpoint history, telemetry, or immutable audit artifacts after a
  hosted action completes.
- Use `GET /v1/execution/policy/snapshots` when the GPT must explain which
  active or historical execution-policy snapshot governed a reviewable action.
- Keep `POST /v1/simulate` as a separate decision-analysis lane, not the default dataset-query path.

## Revoke or disconnect

- Remove the imported action from the GPT
- Revoke the Codna API key if the GPT should no longer have access
- Use `disconnect_data` only when you want to remove a dataset, not just disconnect ChatGPT

## Troubleshooting

- `401 invalid_api_key`: wrong or revoked Bearer token
- `429 rate_limit_exceeded`: honor `Retry-After`
- GPT not calling the action: confirm the imported spec still uses Bearer auth and the GPT has Actions enabled
