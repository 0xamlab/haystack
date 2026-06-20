# Make (Integromat) Integration — Algenta

Use Make's **HTTP** module to call Algenta's hosted data, query, and simulation surfaces in any scenario.

- Cloud Managed: `https://api.algenta.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Algenta cloud.

The checked-in JSON templates intentionally use `https://your-algenta-base-url.example`; replace it with Cloud Managed `https://api.algenta.ai` or your self-hosted base URL before import.

## Files

- `contract_request.json` — request spec for `GET /v1/meta/contract`
- `openapi_contract_request.json` — compatibility request spec for `GET /openapi.json` when older self-hosted nodes still return `404` for `/v1/meta/contract`
- `query_batch_request.json` — request body for `POST /v1/query/batch`
- `sql_report_request.json` — request body for `POST /v1/query/sql-report`

## Quick Setup

### 1. Create a New Scenario

Add an **HTTP → Make a Request** module.

### 2. Configure the HTTP Module

| Field | Value |
|---|---|
| URL | `https://your-algenta-base-url.example/v1/meta/contract` |
| Method | GET |
| Headers | `Authorization: Bearer <YOUR_ALGENTA_API_KEY>` |
| Body Type | None for contract or discovery |
| Content Type | application/json |
| Request Content | Use a second HTTP module for `/v1/data`, `/v1/query`, `/v1/query/batch`, or `/v1/query/sql-report` |

Use `https://app.algenta.ai/dashboard/api-keys` only in Cloud Managed. In
`self_hosted` and `air_gapped`, replace `https://your-algenta-base-url.example`
with your self-hosted base URL and use the API key provisioned by your
self-hosted operator deployment. For Cloud Managed, replace it with
`https://api.algenta.ai`.

### 3. Sample Query Payload

```json
{
  "dataset_id": "orders_facts",
  "metric": {"role": "metric", "hint": "order_count"},
  "group_by": ["order_month"],
  "filter": {
    "time_filter": "last_year",
    "conditions": [{"dimension_hint": "status", "op": "eq", "value": "completed"}]
  },
  "limit": 12,
  "order": "desc"
}
```

### 4. Parse the Response

Add a **JSON → Parse JSON** module after the HTTP request.
Then use these fields downstream:

- `result` — the exact governed rows or values
- `request_id` — the upstream request trace
- `latency_ms` — the request latency

Use `/v1/meta/contract` first when the scenario needs the live discovery/query contract from the running service.
If an older self-hosted node still returns `404` there, call `/openapi.json`
and read `x-primary-data-query-contract` instead. Use the checked-in
`openapi_contract_request.json` when you want a copy-pasteable compatibility
request for that case.
Use `/v1/query/batch` when the scenario needs several exact metrics in one call.
Use `/v1/query/sql-report` when the scenario needs a wide read-only rowset.
Keep `/v1/simulate` for separate decision-analysis flows.
For persisted runtime follow-up or approval flows, add read-only HTTP modules
for:

- `GET /v1/agent/runs`
- `GET /v1/agent/runs/checkpoints`
- `GET /v1/agent/runs/mission-events`
- `GET /v1/agent/runs/telemetry`
- `GET /v1/audit-logs/artifacts`
- `GET /v1/execution/policy/snapshots`

That gives the scenario access to persisted run inventory, replay checkpoints,
mission traces, telemetry, immutable audit artifacts, and policy snapshots
before it fans out to downstream modules.
Use the checked-in request specs and request bodies in `contract_request.json`,
`openapi_contract_request.json`, `query_batch_request.json`, and
`sql_report_request.json` when you want copy-pasteable JSON for the HTTP
modules.

## Async Job Pattern (for large simulations)

For simulations with many variables or large run counts, use the async job pattern:

### Step 1: Submit Job

```json
POST https://your-algenta-base-url.example/v1/jobs
Authorization: Bearer <YOUR_ALGENTA_API_KEY>

{
  "request": { ...simulation payload... },
  "callback_url": "https://hook.make.com/YOUR_WEBHOOK_ID"
}
```

### Step 2: Configure Webhook Module

Add a **Webhooks → Custom Webhook** as your trigger.
Algenta will POST the result to your webhook when the job completes.

### Step 3: Parse Webhook Payload

```json
{
  "event": "job.completed",
  "job_id": "...",
  "result": { ...full DecisionEnvelope... }
}
```

Verify the `X-Webhook-Signature` header:
`sha256=HMAC-SHA256(payload, YOUR_WEBHOOK_SECRET)`

Replace `https://your-algenta-base-url.example` with Cloud Managed
`https://api.algenta.ai` or your self-hosted deployment before running the
async job flow. The bearer key follows the same rule.

## Example Scenario: Dataset Discovery → Batch Query → CRM Update

1. **Trigger:** Webhook or Database Watch (new deal)
2. **Module 1:** HTTP GET to `/v1/meta/contract`
3. **Module 2:** HTTP GET to `/v1/data?search=orders&compact=1`
4. **Module 3:** HTTP POST to `/v1/query/batch`
5. **Module 4:** Update CRM or send Slack with the returned governed metrics

## Self-hosted?

Change the URL to your instance: `http://YOUR_SERVER:8000/v1/data`
