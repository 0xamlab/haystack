---
sidebar_position: 1
---

# Monte Carlo Simulation

Monte Carlo simulation is the core technology behind Decision Engine. Understanding how it works helps you design better scenarios and interpret results confidently.

## The core idea

Instead of trying to calculate a single "correct" answer, Monte Carlo runs your scenario thousands of times with randomly sampled inputs. Each run uses slightly different values within your defined ranges, producing a distribution of possible outcomes.

The result isn't "the answer" — it's **the full probability distribution of all possible answers**, from which you can extract:
- What's the most likely outcome?
- What's the worst 5% of cases?
- How much variability is there?
- What's the probability of loss?

## A simple example

**Scenario**: Should we launch this product?
- Revenue: somewhere between $80,000 and $200,000
- Cost: somewhere between $30,000 and $90,000

**What Decision Engine does:**
1. Samples a revenue value (e.g. $142,000) from the range
2. Samples a cost value (e.g. $67,000) from the range
3. Computes profit = revenue - cost = $75,000
4. Records this outcome
5. Repeats 10,000 times
6. Analyzes the distribution of 10,000 profit values

**Result**: 
```
Expected profit: $75,000 (mean of all 10,000 runs)
Probability of loss: 12% (fraction of runs where profit < 0)
95th percentile: $135,000
5th percentile: $12,000
```

## Why 10,000 runs?

More runs = more accurate statistics. The default of 10,000 gives you:
- Standard errors < 1% for probability estimates
- Stable percentile values
- Sub-100ms execution time on the Python engine

For enterprise accuracy requirements, use `"runs": 100000`.

## Determinism with seeds

Set `"seed": 42` to get reproducible results. Same seed + same inputs = identical output every time. This is essential for:
- Debugging
- Audit trails
- Regression testing
- SHA-256 hash verification

## The objective function

The objective function determines **what you're optimizing**. In Auto mode, Decision Engine auto-builds it from your variables:
- Variables named `revenue`, `sales`, `income` are treated as positive
- Variables named `cost`, `expense`, `loss`, `risk` are treated as negative
- Result: `net_value = sum(positives) - sum(negatives)`

In Expert mode, you write it explicitly: `"objective_function": "revenue * units - fixed_cost - variable_cost * units"`
