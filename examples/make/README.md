# Make (Integromat) Integration — Algenta Decision Engine

Use Make's **HTTP** module to call the Algenta Decision Engine API in any scenario.

## Quick Setup

### 1. Create a New Scenario

Add an **HTTP → Make a Request** module.

### 2. Configure the HTTP Module

| Field | Value |
|---|---|
| URL | `https://api.algenta.ai/v1/simulate` |
| Method | POST |
| Headers | `Authorization: Bearer de_live_YOUR_KEY` |
| Body Type | Raw |
| Content Type | application/json |
| Request Content | See payload below |

> **Get your API key:** https://app.algenta.ai/dashboard/api-keys

### 3. Sample Payload

```json
{
  "mode": "auto",
  "runs": 50000,
  "scenario": {
    "name": "Product launch",
    "variables": {
      "revenue": {"low": 80000, "high": 200000},
      "cost":    {"low": 40000, "high": 90000}
    },
    "objective": "maximize_net_value"
  }
}
```

### 4. Parse the Response

Add a **JSON → Parse JSON** module after the HTTP request.
Then use these fields downstream:

- `recommended_action` — `"proceed"`, `"caution"`, `"reject"`, or `"hedge"`
- `confidence` — 0.0 to 1.0
- `rationale` — human-readable explanation
- `metrics.expected_value` — mean outcome
- `metrics.probability_of_loss` — fraction of negative scenarios
- `result_hash` — SHA-256 for chain-of-custody auditability

## Async Job Pattern (for large simulations)

For simulations with many variables or large run counts, use the async job pattern:

### Step 1: Submit Job

```json
POST https://api.algenta.ai/v1/jobs
Authorization: Bearer de_live_YOUR_KEY

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

## Example Scenario: New Deal → Simulate → CRM Update

1. **Trigger:** Webhook or Database Watch (new deal)
2. **Module 1:** HTTP POST to `/v1/simulate` with deal parameters
3. **Module 2:** Router — branch on `recommended_action`
4. **Module 3a (proceed):** Update CRM → Status = "Approved"
5. **Module 3b (caution/reject):** Slack → alert sales manager

## Self-hosted?

Change the URL to your instance: `http://YOUR_SERVER:8000/v1/simulate`
