---
sidebar_position: 4
---

# Auto Mode vs Expert Mode

Decision Engine supports two modes. You can switch between them — they use the same engine and return the same response format.

## Auto Mode (Simple)

Designed for speed. Describe your variables with just a range — Decision Engine handles distributions, objective function, and scoring automatically.

**When to use:** Exploratory analysis, quick decisions, non-technical users, most business scenarios.

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

**What Auto does automatically:**
- Uses triangular distribution with midpoint as mode
- Classifies positive vs negative variables by name (cost/expense/loss → negative)
- Builds objective function: `revenue - cost`
- Uses default scoring weights (60% expected value, 40% downside risk)

**Objectives in Auto mode:**
| Value | Effect |
|-------|--------|
| `maximize_net_value` | `sum(positives) - sum(negatives)` |
| `maximize_revenue` | `sum(revenue variables)` |
| `minimize_cost` | `-sum(cost variables)` |
| `maximize_probability` | Maximize P(outcome > 0) |

## Expert Mode (Full Control)

Full control over every parameter: distributions, correlations, objective function, scoring weights.

**When to use:** Financial modeling, scientific analysis, complex multi-variable systems, custom scoring.

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

## Decision rules: when to use each

| Factor | Auto | Expert |
|--------|------|--------|
| Setup time | < 30 seconds | 2–10 minutes |
| Distribution control | ✗ (auto triangular) | ✓ Any distribution |
| Correlations | ✗ | ✓ |
| Custom objective function | ✗ | ✓ Any expression |
| Custom scoring weights | ✗ | ✓ |
| Non-technical users | ✓ | ✗ |
| Audit/compliance accuracy | ✗ | ✓ |

**Rule of thumb:** Start with Auto. Switch to Expert when you need a specific distribution (e.g. lognormal for revenue, normal for test scores) or when you need to model correlations between variables.
