---
icon: layer-group
description: SIMD-batched Black-Scholes price and greeks across a whole option chain in one call, matching the scalar pricing functions to 1e-9.
---

# Batched chain greeks

`option_greeks_batch` prices an entire option chain — hundreds to thousands
of strikes and expiries — in a single call, vectorizing the Black-Scholes
math across hardware SIMD lanes. It replaces per-contract scalar pricing
loops where call overhead and scalar transcendentals dominate.

## Functions

| Function | What it does |
|---|---|
| `chain_greeks(spots, strikes, times, rates, sigmas, is_calls)` | Batched BS price, delta, gamma, vega and theta for mixed call/put chains (`is_calls` 1.0/0.0). Returns `ChainGreeksResult` with five parallel `List[Float64]` outputs. |

## Semantics and guarantees

- Results match the scalar `option_pricing` functions to 1e-9 on the valid
  domain (verified across a 144-cell hostile grid of moneyness, expiry and
  volatility, calls and puts).
- Put greeks derive from parity — `delta_put = delta_call - 1`,
  `theta_put = theta_call + r·K·e^(-rT)`; gamma and vega are shared.
  Theta is per year, the same convention as `theta_call`.
- Degenerate lanes (`T <= 0` or `sigma <= 0`) return discounted intrinsic
  value with zero greeks instead of NaN.
- The SIMD main loop and scalar tail produce identical results at every
  batch size (verified for n = 1..11 against single-element calls).

## Throughput

Measured on a 2-lane NEON float64 machine (wider AVX lanes scale further),
with dead-code elimination defeated by checksum accumulation:

```text
1,000-contract chain: batch 28.2 us | scalar loop 88.1 us | 3.1x
= 28 ns per contract for price + all four greeks
```

**Next:** feed the greeks into [statistical model comparison](ml-model-comparison.md) experiments, or browse the [engine catalog](catalog.md).
