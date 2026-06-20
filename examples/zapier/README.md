# Zapier Integration — Algenta

Use the **Webhooks by Zapier** action to call Algenta's hosted data, query, and simulation surfaces in any Zap.

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

### 1. Create a New Zap

**Trigger:** Any trigger you want (e.g., New row in Google Sheets, Form submission, Schedule)

**Action:** Webhooks by Zapier → Custom Request

### 2. Configure the Webhook Action

| Field | Value |
|---|---|
| Method | GET |
| URL | `https://your-algenta-base-url.example/v1/meta/contract` |
| Data Pass-Through | No |
| Data | Use a second step for `/v1/data`, `/v1/query`, `/v1/query/batch`, or `/v1/query/sql-report` |
| Unflatten | No |
| Basic Auth | Leave empty |
| Headers | `Authorization: Bearer <YOUR_ALGENTA_API_KEY>` |

Use `https://app.algenta.ai/dashboard/api-keys` only in Cloud Managed. In
`self_hosted` and `air_gapped`, replace `https://your-algenta-base-url.example`
with your self-hosted base URL and use the API key provisioned by your
self-hosted operator deployment. For Cloud Managed, replace it with
`https://api.algenta.ai`.

### 3. Payload for `/v1/query`

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

### 4. Use the Response

The Zap receives the governed query response. Use these fields downstream:

- `result`
- `request_id`
- `latency_ms`

Use `/v1/meta/contract` first when the Zap needs the live discovery/query contract from the running service.
If an older self-hosted node still returns `404` there, call `/openapi.json`
and read `x-primary-data-query-contract` instead. Use the checked-in
`openapi_contract_request.json` when you want a copy-pasteable compatibility
request for that case.
Use `/v1/query/batch` when the Zap needs several exact metrics in one call.
Use `/v1/query/sql-report` when the Zap needs a wide read-only rowset.
Keep `/v1/simulate` for separate decision-analysis flows.
For persisted runtime follow-up or approval flows, add read-only Webhooks steps
for:

- `GET /v1/agent/runs`
- `GET /v1/agent/runs/checkpoints`
- `GET /v1/agent/runs/mission-events`
- `GET /v1/agent/runs/telemetry`
- `GET /v1/audit-logs/artifacts`
- `GET /v1/execution/policy/snapshots`

That gives the Zap access to persisted run inventory, replay checkpoints,
mission traces, telemetry, immutable audit artifacts, and policy snapshots
before it triggers Slack, email, or ticketing steps.
Use `contract_request.json`, `openapi_contract_request.json`,
`query_batch_request.json`, and `sql_report_request.json` as copy-paste request
specs and request bodies in the Zapier Custom Request step.

### Example Zap: Google Sheets → Dataset Query → Slack

1. **Trigger:** New row in Google Sheets (decision inputs)
2. **Action 1:** Webhooks → GET `/v1/meta/contract`
3. **Action 2:** Webhooks → GET `/v1/data?search=orders&compact=1`
4. **Action 3:** Webhooks → POST `/v1/query/batch`
5. **Action 4:** Slack → Send message with the returned governed metrics

### Testing

Use the Zapier "Test" button with this sample payload:

```json
{
  "dataset_id": "orders_facts",
  "metric": {"role": "metric", "hint": "order_count"},
  "filter": {
    "conditions": [{"dimension_hint": "status", "op": "eq", "value": "completed"}]
  }
}
```

Expected: `{"request_id": "req_...", "result": {...}, ...}`

### Self-hosted?

Change the URL to your instance: `http://YOUR_SERVER:8000/v1/data`
