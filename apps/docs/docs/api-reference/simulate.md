---
sidebar_position: 2
---

# POST /v1/simulate

Run a Monte Carlo simulation and receive a structured decision envelope.

**Quota:** Each successful call consumes 1 simulation from your monthly quota.

## Auto Mode (Simple)

Just describe your variable ranges and let the engine decide:

```bash
curl -X POST https://api.algenta.ai/v1/simulate \
  -H "Authorization: Bearer de_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "scenario": {
      "variables": {
        "revenue": { "low": 80000, "high": 200000 },
        "cost":    { "low": 30000, "high": 90000 }
      },
      "objective": "maximize_net_value"
    },
    "runs": 10000,
    "seed": 42
  }'
```

### Auto Mode Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | `"auto"` | ✓ | Use simple mode |
| `scenario.variables` | object | ✓ | Map of variable names to `{low, high}` ranges |
| `scenario.objective` | string | ✓ | `maximize_net_value`, `maximize_revenue`, `minimize_cost`, or `maximize_probability` |
| `scenario.name` | string | | Optional label for the scenario |
| `runs` | integer | | Number of simulations (default: 10,000, max: 100,000) |
| `seed` | integer | | Random seed for reproducibility |

## Expert Mode (Full Control)

Full control over distributions, correlations, and objective functions:

```json
{
  "mode": "expert",
  "simulation": {
    "variables": [
      {
        "name": "revenue",
        "distribution": "normal",
        "params": { "mean": 140000, "std": 30000 }
      },
      {
        "name": "cost",
        "distribution": "triangular",
        "params": { "low": 30000, "mode": 60000, "high": 90000 }
      }
    ],
    "correlations": [
      { "variables": ["revenue", "cost"], "coefficient": 0.3 }
    ],
    "objective_function": "revenue - cost",
    "scoring": {
      "expected_value": 0.6,
      "downside_risk": 0.4
    }
  },
  "runs": 50000,
  "seed": 42
}
```

### Supported Distributions

| Name | Required params | Description |
|------|----------------|-------------|
| `normal` | `mean`, `std` | Bell curve |
| `uniform` | `low`, `high` | Equal probability |
| `triangular` | `low`, `mode`, `high` | Peak at mode |
| `lognormal` | `mean`, `std` | Always positive |
| `fixed` | `value` | Constant |

## Response

Returns a [DecisionEnvelope](/api-reference#response-envelope).

### Response Headers

| Header | Value |
|--------|-------|
| `X-Decision-Hash` | `sha256=<64-char-hex>;v=1` |

### Verifying the hash

```python
import hashlib, json

result = client.simulate(...)
envelope = result.model_dump()

# Reconstruct canonical form
canonical = {
    "hash_version": "1",
    "run_id": str(envelope["run_id"]),
    "recommended_action": envelope["recommended_action"],
    "confidence": envelope["confidence"],
    "rationale": envelope["rationale"],
    "metrics": { ... },
    "percentiles": { ... },
    "scenarios_run": envelope["scenarios_run"],
    "engine_version": envelope["engine_version"],
}
expected = hashlib.sha256(
    json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()

assert expected == result.result_hash  # tamper-proof verification
```

## Errors

| Code | `error.code` | Description |
|------|-------------|-------------|
| `429` | `quota_exceeded` | Monthly quota exhausted |
| `429` | `rate_limit_exceeded` | Too many requests per minute |
| `400` | `validation_error` | Invalid request body |
| `401` | `invalid_api_key` | Authentication failed |
