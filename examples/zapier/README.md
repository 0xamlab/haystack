# Zapier Integration — Algenta Decision Engine

Use the **Webhooks by Zapier** action to call the Algenta Decision Engine API in any Zap.

## Quick Setup

### 1. Create a New Zap

**Trigger:** Any trigger you want (e.g., New row in Google Sheets, Form submission, Schedule)

**Action:** Webhooks by Zapier → Custom Request

### 2. Configure the Webhook Action

| Field | Value |
|---|---|
| Method | POST |
| URL | `https://api.algenta.ai/v1/simulate` |
| Data Pass-Through | No |
| Data | See payload below |
| Unflatten | No |
| Basic Auth | Leave empty |
| Headers | `Authorization: Bearer de_live_YOUR_KEY` |

> **Get your API key:** https://app.algenta.ai/dashboard/api-keys

### 3. Payload for `/v1/simulate` (auto mode)

```json
{
  "mode": "auto",
  "runs": 50000,
  "scenario": {
    "name": "My decision",
    "variables": {
      "revenue": {"low": 80000, "high": 200000},
      "cost":    {"low": 40000, "high": 90000}
    },
    "objective": "maximize_net_value"
  }
}
```

### 4. Use the Response

The Zap receives the full `DecisionEnvelope`. Use these fields downstream:

- `recommended_action` — `"proceed"`, `"caution"`, `"reject"`, or `"hedge"`
- `confidence` — 0.0 to 1.0
- `rationale` — human-readable explanation
- `metrics.expected_value` — mean outcome across all scenarios
- `metrics.probability_of_loss` — fraction of scenarios with negative outcome
- `result_hash` — SHA-256 chain-of-custody hash for auditability

### Example Zap: Google Sheets → Simulate → Slack

1. **Trigger:** New row in Google Sheets (decision inputs)
2. **Action 1:** Webhooks → POST to `/v1/simulate` with row data as variables
3. **Action 2:** Slack → Send message with `recommended_action` and `rationale`

### Testing

Use the Zapier "Test" button with this sample payload:

```json
{
  "mode": "auto",
  "runs": 10000,
  "scenario": {
    "variables": {"x": {"low": 100, "high": 500}},
    "objective": "maximize_net_value"
  }
}
```

Expected: `{"recommended_action": "proceed", "confidence": 0.84, ...}`

### Self-hosted?

Change the URL to your instance: `http://YOUR_SERVER:8000/v1/simulate`
