---
slug: /
sidebar_position: 1
---

# Algenta

**Monte Carlo simulation API for smarter, faster decisions.**

Algenta turns your uncertainty into structured recommendations in a single API call. Instead of spreadsheet guessing, you get probability distributions, confidence intervals, and actionable recommendations backed by simulated scenarios.

## What it does

```bash
curl -X POST https://api.algenta.ai/v1/simulate \
  -H "Authorization: Bearer de_live_..." \
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

Returns:

```json
{
  "recommended_action": "proceed",
  "confidence": 0.82,
  "rationale": "Expected value is positive in 82% of scenarios. Mean: $105,000.",
  "metrics": { "expected_value": 105000, "probability_of_loss": 0.18 },
  "result_hash": "40a76a11a4d1f7abec6e6105a817d72b..."
}
```

## Key features

| Feature | Description |
|---------|-------------|
| **Simple Mode** | Just define variable ranges — we handle everything else |
| **Expert Mode** | Full control: distributions, correlations, objective functions |
| **Decision Envelope** | Structured output with metrics, percentiles, and recommendations |
| **SHA-256 Integrity** | Every decision is cryptographically hashed for tamper detection |
| **Async Jobs** | Submit long-running simulations, poll for results |
| **Webhooks** | Get notified when async jobs complete |
| **SDKs** | Python, TypeScript, CLI — all officially supported |
| **Integrations** | ChatGPT, Claude/Codex MCP, Azure AI Foundry, n8n, local runtime, and more |

## Plans

| Plan | Simulations/month | Price |
|------|------------------|-------|
| Free | 500 | Free forever |
| Developer | 10,000 | $29/month |
| Pro | 100,000 | $99/month |
| Enterprise | Unlimited | Custom |

`DE` remains the canonical API key prefix in `v1` for compatibility. Public brand and base URL are `Algenta` and `https://api.algenta.ai`.

## Next steps

- [**Quickstart →**](/quickstart) — Make your first API call in under 2 minutes
- [**API Reference →**](/api-reference) — Full endpoint documentation
- [**Integrations →**](/integrations/overview) — Connect to your tools
