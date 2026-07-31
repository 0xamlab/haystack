---
icon: wave-square
description: Normalization kernel results — RMSNorm and LayerNorm forward and backward cost, the price of the numerically safe variance, and gradient checks against finite differences.
---

# Normalization

Results for the normalization kernels: RMSNorm and LayerNorm, forward and backward. A norm is the cheapest layer in a transformer and the one best placed to quietly damage a model, so most of this page is about correctness with the timings alongside.

## Hardware

| Property | Value |
| --- | --- |
| Chip | Apple silicon, 16 physical cores |
| Precision measured | 64-bit floating point |

Results are reported for this configuration only. Other chip generations and memory configurations are published separately as they are measured, never averaged into a single figure.

## Cost per element

| Row width | Rows | Cost per element |
| --- | --- | --- |
| 512 | 64 | 8.09 ns |
| 2,048 | 64 | 3.11 ns |
| 8,192 | 64 | 1.21 ns |

**Per-element cost falls rather than staying flat, and the reason is not that wider rows are cheaper.** All three shapes are large enough to run across cores, so each pays one fixed cost to distribute work and amortises it over more elements as the row grows. The gated property is only that cost does not *rise* — a normalization whose per-element cost grew with width would be doing something more than linear work.

Below the threshold where distribution pays for itself, the kernel runs on a single core deliberately:

| Shape | Cost per element |
| --- | --- |
| 8 rows, single core | 56.2 ns |
| 4,096 rows, distributed | 0.82 ns |

## The price of a numerically safe variance

LayerNorm needs the variance of each row. There is a one-pass formula that computes it in a single walk of the data, and a two-pass formula that computes the mean first and then the deviations from it. Algenta uses the two-pass form.

The one-pass form loses accuracy when a row's values sit far from zero — which is what a transformer's residual stream looks like after a few blocks. Measured on a row offset by 100 million, the one-pass identity is wrong by **3.65** where the row's actual variance is about **0.35**: an error ten times the size of the quantity being computed. Pushed further it returns a negative variance, at which point the square root produces a non-number and the entire model output becomes invalid — from a kernel that appeared to work.

The cost of avoiding this:

| Kernel | Time |
| --- | --- |
| RMSNorm (one reduction) | 324 µs |
| LayerNorm (two passes) | 333 µs |

**3%.** The second pass re-reads a row that is already in the nearest cache level, so it is close to free. On centred data the two formulas agree to 4.9e-15, and that agreement is reported by the kernel itself on the caller's own data rather than assumed.

## Backward pass

| Direction | Time | Ratio |
| --- | --- | --- |
| Forward | 324 µs | — |
| Backward | 635 µs | 1.96x |

A backward pass that costs nothing is a backward pass that is wrong. This one runs two reduction passes and a reduction across rows for the scale parameter.

**Gradients are checked against finite differences**, not against a reading of the algebra:

| Kernel | Difference | Tolerance |
| --- | --- | --- |
| RMSNorm | 7.3e-9 | 4.0e-8 |
| LayerNorm | 3.1e-9 | 1.1e-8 |

The tolerance is deliberately looser than the forward kernel's. A finite difference carries two error sources that pull in opposite directions as the step size changes, so it cannot resolve a gradient better than roughly the square of that step. Judging it by a forward-parity tolerance would fail on correct code.

**The check is also shown to be capable of failing.** Each gradient has a term that a careless derivation drops. Recomputing without it moves the result by **2.19** (RMSNorm) and **3.75** (LayerNorm) — far outside tolerance. A gradient check that cannot fail proves nothing, so the failing case is asserted alongside the passing one.

## Reproducibility across cores

The gradient with respect to the scale parameter sums across rows. Computing it with one worker per row would need a shared accumulator: a race, and non-deterministic even when locked, because the sum order would depend on which thread arrived first.

Algenta splits that reduction by column instead — each worker owns whole columns and sums them in row order. The result is **bit-identical** to a single-threaded reference across 4,096 rows, regardless of how many cores run it.

## What is not claimed

* Any comparison against a third-party normalization implementation.
* That these figures represent the product's normalization throughput at lower precision. Every number here is 64-bit, and a norm is limited by memory bandwidth, so a narrower numeric format reads a fraction of the bytes and is most of the remaining headroom.

## Related

* [Benchmarks](overview.md) — methodology and what is not published.
* [Attention](attention.md) — the attention kernels these norms surround.
* [Feed-forward](feed-forward.md) — the other half of a transformer block.
