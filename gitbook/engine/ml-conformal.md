---
icon: gauge-high
description: Split-conformal prediction intervals with finite-sample coverage guarantees.
---

# Conformal prediction intervals

`conformal` turns any point-forecasting model into one with distribution-free
prediction intervals: calibrate on held-out residuals, then report `pred ± q`
with coverage ≥ 1 − alpha under exchangeability. It replaces the
split-conformal regression core of **mapie** / **nonconformist** with zero
Python imports — deterministic (heapsort quantile, no RNG) and sub-millisecond
for calibration sets up to ~10k scores.

## The modules

| Module | What it does |
| --- | --- |
| `conformal` | split-conformal prediction intervals with finite-sample coverage guarantees — calibrates on held-out residuals and reports `pred ± q` with coverage ≥ 1 − alpha under exchangeability — replacing the split-conformal regression core of **mapie** / **nonconformist** |

## Functions

| Function | What it does |
|---|---|
| `conformal_quantile(residuals_calibration, alpha)` | Split-conformal quantile `q`: the k-th smallest `\|residual\|` with `k = ceil((1-alpha)(n+1))`. Signed residuals accepted. |
| `conformal_quantile_normalized(residuals_calibration, scales, alpha)` | Same rank rule on `\|residual_i\| / scale_i` — the locally-weighted variant with a per-sample difficulty scale. |
| `conformal_interval(pred, q)` | Symmetric interval `[pred - q, pred + q]`, returned as a `ConformalInterval` (`lo`, `hi`). |
| `conformal_interval_normalized(pred, q, scale)` | Normalized interval `[pred - q*scale, pred + q*scale]` for this sample's scale. |
| `conformal_band(preds, q)` | `pred_i ± q` for a whole prediction list, returned as a `ConformalBand` (`lo`, `hi` lists); feeds `conformal_coverage`. |
| `conformal_coverage(y, lo, hi)` | Fraction of samples with `lo[i] <= y[i] <= hi[i]` (bounds inclusive) — the empirical coverage check. |

## Money-path conservative conventions

Malformed input can only widen intervals, never narrow them:

- When no finite calibration quantile achieves the requested coverage (empty
  calibration set, `alpha < 1/(n+1)`, NaN or infinite alpha), the quantile is
  the finite sentinel `1e308` — an effectively infinite half-width. The repo
  convention is finite `1e308` rather than IEEE `inf`, so downstream
  `pred ± q` arithmetic stays well-behaved.
- NaN or infinite residuals and nonpositive / non-finite scales score as
  `1e308` (maximally nonconforming) instead of being silently dropped.
- A negative or NaN half-width collapses to a degenerate point interval; it
  can never invert the bounds.
- `conformal_coverage` returns `0.0` for empty or length-mismatched inputs —
  malformed data never reports coverage.

## Verification

Known-value tests pin the rank rule and the coverage guarantee exactly
(tolerance 1e-12):

- n = 9 signed residuals at alpha = 0.1 → k = ceil(0.9 · 10) = 9 → q = 2.0;
  the same data at alpha = 0.2 selects the 8th sorted score, 1.5; fractional
  ceil is checked at n = 4, alpha = 0.5 (ceil(2.5) = 3 → 3.0).
- Calibration scores 1..99: alpha = 0.1 → q = 90 and alpha = 0.05 → q = 95;
  the constructed end-to-end band then covers exactly 0.90 of 100 test
  points.
- Boundary inclusivity is hand-checked (coverage 3/5 = 0.6 with `y == hi`
  counting as covered), and NaN-residual, infinite-residual, zero-scale, and
  denormal-scale cases all resolve to the finite `1e308` sentinel — the
  tests assert q is never IEEE `inf`.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
