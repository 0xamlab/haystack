# Algenta — ChatGPT Actions

Use the hosted Algenta OpenAPI contract inside ChatGPT Actions.

- Cloud Managed: `https://api.algenta.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Algenta cloud.

The checked-in `openapi_actions.yaml` template intentionally uses `https://your-algenta-base-url.example`; replace it with Cloud Managed `https://api.algenta.ai` or your self-hosted base URL before import.

## Files

- `openapi_actions.yaml` — importable OpenAPI action definition

## Setup

1. Create or edit an Action-enabled GPT.
2. Import `https://your-algenta-base-url.example/openapi.json`. Replace the
   placeholder with Cloud Managed `https://api.algenta.ai` or your self-hosted
   `/openapi.json` URL for `self_hosted` / `air_gapped`. You can also use
   `openapi_actions.yaml`.
3. Configure auth as `Authorization: Bearer <YOUR_ALGENTA_API_KEY>`.
4. Start with read-only actions unless you explicitly need dataset mutations.

Importing `/openapi.json` is also the compatibility path for older self-hosted
nodes. If `/v1/meta/contract` is not mounted yet there, use
`x-primary-data-query-contract` from the OpenAPI document instead.

## First prompt

```text
Inspect the live contract, then find the dataset that matches OTP, summarize it, and return the overall OTP rate plus a monthly breakdown for the last 12 months.
```

The action spec now exposes the full read-only discovery, query, and persisted
runtime review flow:

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

`POST /v1/simulate` remains available as a separate decision-analysis lane.

Use the persisted runtime and control-plane review endpoints when the GPT needs
to inspect run lineage, checkpoint history, immutable audit artifacts, or
execution-policy snapshot history without mutating the system.

## Revoke or disconnect

- Remove the imported action from the GPT
- Revoke the Algenta API key if the GPT should no longer have access
