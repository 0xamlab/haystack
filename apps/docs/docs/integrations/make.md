---
sidebar_position: 7
---

# Make (formerly Integromat)

Use the Algenta HTTP module pattern in Make scenarios for governed dataset discovery, exact queries, batch exact queries, constrained SQL reports, and simulations.

Use one base URL consistently across every Make HTTP module:

- Cloud Managed: `https://api.codna.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Codna cloud.

## Setup

1. In Make, create a new scenario
2. Add **HTTP → Make a request** module
3. Configure the live contract call first:
   - **URL**: `https://your-algenta-base-url.example/v1/meta/contract`
   - **Method**: GET
   - **Headers**: `Authorization: Bearer <YOUR_ALGENTA_API_KEY>` and `Content-Type: application/json`
   - **Older self-hosted fallback**: if that returns `404`, call `https://your-algenta-base-url.example/openapi.json` (or your self-host base URL) and read `x-primary-data-query-contract`
4. Configure a read-only discovery call next:
   - **URL**: `https://your-algenta-base-url.example/v1/data?search=orders&compact=1&limit=5`
   - **Method**: GET
   - **Headers**: `Authorization: Bearer <YOUR_ALGENTA_API_KEY>` and `Content-Type: application/json`
5. Add another **HTTP → Make a request** module for the exact query:
   - **URL**: `https://your-algenta-base-url.example/v1/query`
   - **Method**: POST
   - **Headers**: `Authorization: Bearer <YOUR_ALGENTA_API_KEY>` and `Content-Type: application/json`
   - **Body type**: Raw → JSON
   - **Request content**:

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

5. Parse the response and use `result`, `request_id`, and `latency_ms` in downstream modules

Replace `https://your-algenta-base-url.example` with Cloud Managed
`https://api.codna.ai` or your self-hosted base URL before enabling the
scenario.

If an older self-hosted node still returns `404` for `/v1/meta/contract`, use
`/openapi.json` and read `x-primary-data-query-contract` instead.
That machine-readable contract also includes `governed_filter_contract` for
selector fields, operator families, and validation rules on deterministic exact
filters.

For multi-metric prompts, use `POST /v1/query/batch`. For wide read-only rowsets, use `POST /v1/query/sql-report`. Keep `POST /v1/simulate` for separate decision-analysis flows.

For persisted runtime follow-up or approval flows, add read-only HTTP modules
for:

- `GET /v1/agent/runs`
- `GET /v1/agent/runs/checkpoints`
- `GET /v1/agent/runs/mission-events`
- `GET /v1/agent/runs/telemetry`
- `GET /v1/audit-logs/artifacts`
- `GET /v1/execution/policy/snapshots`

Those surfaces let a Make scenario inspect replay candidates, mission traces,
runtime telemetry, immutable audit artifacts, and execution-policy lineage
before it branches into email, Slack, CRM, or approval modules.

See [`examples/make/README.md`](https://github.com/decisionengine/decision-engine/tree/main/examples/make/README.md) for a complete walkthrough.
Use the checked-in request bodies when you want copy-paste JSON:

- [`examples/make/contract_request.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/make/contract_request.json)
- [`examples/make/openapi_contract_request.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/make/openapi_contract_request.json)
- [`examples/make/query_batch_request.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/make/query_batch_request.json)
- [`examples/make/sql_report_request.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/make/sql_report_request.json)

Use `openapi_contract_request.json` when the scenario must recover the live
contract from `/openapi.json` on an older self-hosted node that still returns
`404` for `/v1/meta/contract`.
