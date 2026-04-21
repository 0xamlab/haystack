---
sidebar_position: 2
---

# Quickstart

Make your first API call in under 2 minutes.

## Step 1: Get an API key

[Sign up at algenta.ai →](https://algenta.ai/signup)

Your API key looks like: `de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Make your first call

### curl

```bash
curl -X POST https://api.algenta.ai/v1/simulate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer de_live_YOUR_KEY_HERE" \
  -d '{
    "mode": "auto",
    "scenario": {
      "variables": {
        "revenue": { "low": 80000, "high": 200000 },
        "cost":    { "low": 30000, "high": 90000 }
      },
      "objective": "maximize_net_value"
    }
  }'
```

### Python

```python
pip install decision-engine-sdk
```

```python
from decision_engine import DecisionEngineClient

client = DecisionEngineClient(api_key="de_live_YOUR_KEY_HERE")

result = client.simulate(
    mode="auto",
    scenario={
        "variables": {
            "revenue": {"low": 80000, "high": 200000},
            "cost":    {"low": 30000, "high": 90000},
        },
        "objective": "maximize_net_value",
    }
)

print(f"Recommendation: {result.recommended_action}")
print(f"Confidence: {result.confidence:.0%}")
print(f"Expected value: ${result.metrics.expected_value:,.0f}")
```

### TypeScript

```bash
npm install @decision-engine/sdk
```

```typescript
import { DecisionEngineClient } from '@decision-engine/sdk';

const client = new DecisionEngineClient({ apiKey: 'de_live_YOUR_KEY_HERE' });

const result = await client.simulate({
  mode: 'auto',
  scenario: {
    variables: {
      revenue: { low: 80000, high: 200000 },
      cost:    { low: 30000, high: 90000 },
    },
    objective: 'maximize_net_value',
  },
});

console.log(`Recommendation: ${result.recommended_action}`);
console.log(`Confidence: ${(result.confidence * 100).toFixed(0)}%`);
```

## Step 3: Understand the response

```json
{
  "run_id": "a9a017f9-6479-45a8-9405-b3362f24a68c",
  "status": "completed",
  "recommended_action": "proceed",
  "confidence": 0.82,
  "rationale": "Expected value is positive in 82% of scenarios. Mean: $105,000.",
  "metrics": {
    "expected_value": 105000.0,
    "median": 102000.0,
    "std_deviation": 38000.0,
    "probability_of_loss": 0.18,
    "var_95": -15000.0
  },
  "percentiles": {
    "p5": 42000.0,
    "p25": 72000.0,
    "p50": 102000.0,
    "p75": 135000.0,
    "p95": 175000.0
  },
  "scenarios_run": 10000,
  "execution_ms": 42,
  "result_hash": "40a76a11a4d1f7abec6e6105a817d72b82f3ed46..."
}
```

| Field | Description |
|-------|-------------|
| `recommended_action` | `proceed`, `caution`, or `reject` |
| `confidence` | Probability of a positive outcome (0.0–1.0) |
| `rationale` | Human-readable explanation |
| `metrics.expected_value` | Mean simulation outcome |
| `metrics.probability_of_loss` | Fraction of scenarios with negative outcome |
| `percentiles` | p5 through p95 of outcome distribution |
| `result_hash` | SHA-256 fingerprint for tamper detection |

## Next steps

- **More complex scenarios**: Use [Expert Mode](/api-reference/simulate#expert-mode-full-control) for full control over distributions and correlations
- **Compare options**: Use `POST /v1/recommend` to automatically pick the best of multiple scenarios
- **Automate decisions**: Connect to [ChatGPT Actions](/integrations/chatgpt-actions), [Claude and Codex](/integrations/claude-codex), [n8n](/integrations/n8n), or [Azure AI Foundry and Studio](/integrations/azure-ai-studio)
- **Run locally**: Use the [Local Runtime](/integrations/local-runtime) when you want hosted licensing with local execution and offline task history
- **Verify integrity**: The `result_hash` lets you verify a decision result hasn't been tampered with

## Rate limits

| Plan | Requests/minute | Simulations/month |
|------|----------------|------------------|
| Free | 60 | 500 |
| Developer | 300 | 10,000 |
| Pro | 1,000 | 100,000 |
| Enterprise | 10,000 | Unlimited |

Returns `HTTP 429` with `Retry-After` header when rate limit is exceeded.

Legacy clients can continue using `X-API-Key` during the `v1` compatibility window, but new integrations should use `Authorization: Bearer`.
