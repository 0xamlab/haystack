---
sidebar_position: 6
---

# Zapier

Connect Algenta to 5,000+ apps via Zapier's no-code automation platform.

Use one base URL consistently across every Zapier webhook step:

- Cloud Managed: `https://api.codna.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Codna cloud.

## Setup

1. In Zapier, create a **New Zap**
2. Set your trigger (e.g., "New row in Google Sheets")
3. Add a **Webhooks by Zapier** action for the live contract:
   - **Method**: GET
   - **URL**: `https://your-algenta-base-url.example/v1/meta/contract`
   - **Headers**: `Authorization: Bearer <YOUR_ALGENTA_API_KEY>`
   - **Older self-hosted fallback**: if that returns `404`, call `https://your-algenta-base-url.example/openapi.json` (or your self-host base URL) and read `x-primary-data-query-contract`
4. Add a **Webhooks by Zapier** action for governed discovery:
   - **Method**: GET
   - **URL**: `https://your-algenta-base-url.example/v1/data?search=orders&compact=1&limit=5`
   - **Headers**: `Authorization: Bearer <YOUR_ALGENTA_API_KEY>`
5. Add another **Webhooks by Zapier** action for the exact query:
   - **Method**: POST
   - **URL**: `https://your-algenta-base-url.example/v1/query`
   - **Headers**: `Authorization: Bearer <YOUR_ALGENTA_API_KEY>`
   - **Data**: JSON body with `dataset_id`, `metric`, and optional `group_by` or `filter`

4. Use the response fields in downstream actions

Replace `https://your-algenta-base-url.example` with Cloud Managed
`https://api.codna.ai` or your self-hosted base URL before enabling the Zap.

If an older self-hosted node still returns `404` for `/v1/meta/contract`, use
`/openapi.json` and read `x-primary-data-query-contract` instead.
That machine-readable contract also includes `governed_filter_contract` so raw
Zapier webhooks can inspect the exact filter model before building requests.

## Example Zap

**Trigger**: New form submission (Typeform)  
**Action 1**: List Algenta datasets with `search=orders&compact=1`  
**Action 2**: Query the selected dataset with `POST /v1/query/batch`  
**Action 3**: Send Slack message with the returned metrics

Use `POST /v1/query/sql-report` when the Zap needs a read-only wide rowset. Keep `POST /v1/simulate` for separate decision-analysis flows.

For persisted runtime follow-up or approval flows, add read-only webhook steps
for:

- `GET /v1/agent/runs`
- `GET /v1/agent/runs/checkpoints`
- `GET /v1/agent/runs/mission-events`
- `GET /v1/agent/runs/telemetry`
- `GET /v1/audit-logs/artifacts`
- `GET /v1/execution/policy/snapshots`

Those surfaces let a Zap inspect replay candidates, mission traces, telemetry,
immutable audit artifacts, and policy lineage before it sends notifications or
branches into downstream actions.

See [`examples/zapier/README.md`](https://github.com/decisionengine/decision-engine/tree/main/examples/zapier/README.md) for detailed setup steps.
Use the checked-in request bodies when you want copy-paste JSON:

- [`examples/zapier/contract_request.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/zapier/contract_request.json)
- [`examples/zapier/openapi_contract_request.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/zapier/openapi_contract_request.json)
- [`examples/zapier/query_batch_request.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/zapier/query_batch_request.json)
- [`examples/zapier/sql_report_request.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/zapier/sql_report_request.json)

Use `openapi_contract_request.json` when the Zap must recover the live contract
from `/openapi.json` on an older self-hosted node that still returns `404` for
`/v1/meta/contract`.
