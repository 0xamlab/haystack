---
sidebar_position: 7
---

# Make (formerly Integromat)

Use the Algenta HTTP module pattern in Make scenarios.

## Setup

1. In Make, create a new scenario
2. Add **HTTP → Make a request** module
3. Configure:
   - **URL**: `https://api.algenta.ai/v1/simulate`
   - **Method**: POST
   - **Headers**: `Authorization: Bearer de_live_...` and `Content-Type: application/json`
   - **Body type**: Raw → JSON
   - **Request content**:

```json
{
  "mode": "auto",
  "scenario": {
    "variables": {
      "revenue": { "low": 80000, "high": 200000 },
      "cost":    { "low": 30000, "high": 90000 }
    },
    "objective": "maximize_net_value"
  }
}
```

4. Parse the response and use `recommended_action`, `confidence`, `rationale` in downstream modules

See [`examples/make/README.md`](https://github.com/decisionengine/decision-engine/tree/main/examples/make/README.md) for a complete walkthrough.
