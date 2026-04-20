---
sidebar_position: 2
---

# Probability Distributions

In Expert Mode, you choose the distribution that best represents each variable's uncertainty. Choosing the right distribution produces more realistic simulations.

## Quick reference

| Distribution | When to use | Required params |
|---|---|---|
| `triangular` | You know min, max, and most-likely value | `low`, `mode`, `high` |
| `normal` | Symmetric uncertainty around a mean (many natural processes) | `mean`, `std` |
| `uniform` | Complete uncertainty between two bounds | `low`, `high` |
| `lognormal` | Always positive, right-skewed (revenue, costs) | `mean`, `std` |
| `fixed` | A known constant (no uncertainty) | `value` |

## Triangular — the most common choice

Use when you can estimate a minimum, maximum, and most likely value. Perfect for cost and time estimates.

```json
{
  "name": "project_cost",
  "distribution": "triangular",
  "params": { "low": 40000, "mode": 65000, "high": 120000 }
}
```

The `mode` is the peak of the distribution — the value you'd bet on if forced to give a single answer.

## Normal (Gaussian)

Use for measurements with natural variability around a central value. Financial returns, manufacturing tolerances, test scores.

```json
{
  "name": "daily_sales",
  "distribution": "normal",
  "params": { "mean": 5000, "std": 800 }
}
```

⚠️ Normal distributions can produce negative values. If your variable can't be negative (e.g. revenue), use `lognormal` instead.

## Uniform

Every value between `low` and `high` is equally likely. Use when you genuinely have no information about which values are more likely.

```json
{
  "name": "market_share",
  "distribution": "uniform",
  "params": { "low": 0.05, "high": 0.25 }
}
```

## Log-normal

Always positive, skewed right. Perfect for financial modeling (stock prices, revenue) and natural phenomena (incomes, city populations).

```json
{
  "name": "revenue",
  "distribution": "lognormal",
  "params": { "mean": 11.5, "std": 0.4 }
}
```

The `mean` and `std` here are the **natural log** of the variable, not the variable itself. If you want a median of ~$100,000: `mean = ln(100000) ≈ 11.51`.

## Fixed

No randomness — the value is always exactly this. Useful for known constants in your objective function.

```json
{
  "name": "tax_rate",
  "distribution": "fixed",
  "params": { "value": 0.21 }
}
```

## Correlations

In reality, variables often move together. Rising revenue often correlates with rising costs. Model this with correlations:

```json
{
  "correlations": [
    { "variables": ["revenue", "cost"], "coefficient": 0.7 }
  ]
}
```

`coefficient`: -1 (perfectly inverse) to +1 (perfectly correlated). 0 = independent.

Failing to model positive correlations underestimates risk — your downside scenarios become more extreme than independent sampling suggests.
