---
sidebar_position: 3
---

# Decision Envelope

Every simulation returns a **Decision Envelope** — a structured object containing everything you need to act on the result.

## Full structure

```json
{
  "run_id": "a9a017f9-6479-45a8-9405-b3362f24a68c",
  "status": "completed",
  "engine_version": "0.1.0",

  "recommended_action": "proceed",
  "confidence": 0.82,
  "rationale": "Expected value is positive in 82% of scenarios. Mean: $105,000.",

  "metrics": {
    "expected_value": 105000.0,
    "median": 102000.0,
    "std_deviation": 38000.0,
    "variance": 1444000000.0,
    "probability_of_loss": 0.18,
    "var_95": -15000.0,
    "cvar_95": -25000.0
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
  "metadata": {
    "mode": "auto",
    "seed": 42,
    "billing_units": 1,
    "engine_version": "0.1.0"
  },
  "result_hash": "40a76a11a4d1f7abec6e6105a817d72b82f3ed46..."
}
```

## Recommended action

| Value | Meaning | Threshold |
|-------|---------|-----------|
| `proceed` | High probability of positive outcome | ≥ 65% chance of positive result |
| `caution` | Mixed — possible but uncertain | 40–65% |
| `reject` | High probability of negative outcome | < 40% |

## Metrics explained

| Field | Description |
|-------|-------------|
| `expected_value` | Mean outcome across all scenarios — the "average case" |
| `median` | The midpoint — half of scenarios are above, half below |
| `std_deviation` | How spread out the outcomes are — higher = more uncertainty |
| `probability_of_loss` | Fraction of scenarios where outcome < 0 |
| `var_95` | Value at Risk (95th confidence) — worst 5% of outcomes are below this |
| `cvar_95` | Expected loss in the worst 5% of scenarios |

## Percentiles

The percentile distribution gives you the full range of possible outcomes:

- `p5`: Only 5% of scenarios are worse than this — your realistic worst case
- `p50`: The median — your "most likely" single outcome  
- `p95`: Only 5% of scenarios are better than this — your realistic best case

A wide gap between p5 and p95 means **high uncertainty**. A narrow gap means the outcome is predictable.

## result_hash — cryptographic integrity

Every decision result is SHA-256 hashed at computation time. The hash covers:
- `run_id`, `recommended_action`, `confidence`, `rationale`
- All `metrics` fields
- All `percentiles`
- `scenarios_run`, `engine_version`

Use it to verify a stored result hasn't been tampered with:

```python
import hashlib, json

def verify(result: dict) -> bool:
    canonical = {
        "hash_version": "1",
        "run_id": str(result["run_id"]),
        "recommended_action": result["recommended_action"],
        "confidence": result["confidence"],
        "rationale": result["rationale"],
        "metrics": {k: result["metrics"][k] for k in 
                    ["expected_value","median","std_deviation","variance",
                     "probability_of_loss","var_95"]},
        "percentiles": result["percentiles"],
        "scenarios_run": result["scenarios_run"],
        "engine_version": result["engine_version"],
    }
    computed = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",",":")).encode()
    ).hexdigest()
    return computed == result["result_hash"]
```

Also returned as the `X-Decision-Hash: sha256=<hex>;v=1` response header.
