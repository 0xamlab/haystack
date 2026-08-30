---
icon: chart-line
description: Durbin-Levinson AR estimation, innovations MA fitting and ARIMA forecasting building blocks.
---

# AR/MA estimation (ARIMA building blocks)

`arima` fits AR(p) and MA(q) models in pure Mojo with zero Python
imports — replacing `statsmodels.tsa` (AutoReg / ARIMA Yule-Walker
fitting, innovations MA estimation, conditional-sum-of-squares
likelihood). It complements `timeseries_stats`, which provides ACF/PACF
diagnostics only; this module actually estimates coefficients. Model
convention matches statsmodels (positive θ on lagged innovations), with
the sample mean μ handled internally.

## The modules

| Module | What it does |
| --- | --- |
| `arima` | fits AR(p) and MA(q) coefficients in pure Mojo — Yule-Walker/Durbin-Levinson AR estimation, innovations-algorithm MA estimation, CSS log-likelihood scoring, and order-d differencing/undifferencing |
| `timeseries_stats` | ACF/PACF and ADF diagnostics plus rolling mean/std, exponential smoothing and Holt linear trend — describes a series, does not fit AR/MA coefficients |

## Functions

| Function | What it does |
|---|---|
| `ar_fit_yule_walker(series, p)` | Fit AR(p) by Yule-Walker: Durbin-Levinson on the sample ACF (series de-meaned internally). Returns `ARFit` (phi, sigma2). |
| `durbin_levinson(autocov, p)` | Durbin-Levinson recursion solving the order-p Yule-Walker equations on given autocovariances γ(0..p). |
| `ar_forecast(series, phi, steps)` | h-step-ahead recursive AR forecasts; decays toward the sample mean for stationary φ. |
| `ma_fit_innovations(series, q, max_iter)` | Fit MA(q) via the innovations algorithm on the sample ACF. Returns `MAFit` (theta, sigma2). |
| `innovations_algorithm(autocov, q, max_iter)` | Innovations recursion (Brockwell & Davis) on given autocovariances; θ estimates converge to the MA(q) coefficients as iterations grow. |
| `arma_loglik_css(series, phi, theta)` | Conditional-sum-of-squares Gaussian log-likelihood at the profile MLE variance. Higher is better; compare fits with equal p. |
| `difference(series, order)` | Order-d differencing — the ARIMA "I" step. |
| `undifference(diffed, initial)` | Exact inverse of `difference` given the first d values of the original series. |

## Usage guidance

- **Deterministic**: the same series always produces bit-identical fits
  (asserted directly in the tests).
- Keep `max_iter` modest for the innovations algorithm — it is O(M³);
  20–50 is typical and estimates stabilize quickly. `ma_fit_innovations`
  is sub-millisecond for M ≤ ~60 at any n ≤ 10k; do not pass
  `max_iter ~ n`.
- Degenerate inputs never trap: empty series or p/q ≤ 0 yield empty
  coefficient lists; an all-equal series (γ(0) ≈ 0) yields zero
  coefficients with sigma2 = 0.
- Round-trip identity: `undifference(difference(x, d), x[0:d]) == x` —
  exact (verified bit-for-bit on integer-valued floats for d = 1..3).

## Verification

Tests pin hand-derived references, not library snapshots:

- Hand-solved Yule-Walker at p = 2 on γ = [1, 0.5, 0.2]: φ =
  (0.5333333333333333, −0.06666666666666667) = (8/15, −1/15) and
  sigma2 = 0.7466666666666666 = 11.2/15, matched to 1e-12.
- Hand-run innovations recursion on the exact MA(1) ACF (θ = 0.5):
  θ₁ = 42/85 = 0.49411764705882355 and sigma2 = 341/340 at M = 3 to
  1e-12; at M = 30 the estimate converges to θ = 0.5, sigma2 = 1
  within 1e-3.
- Seeded synthetic recovery (n = 2000): AR(1) with φ = 0.7 is recovered
  within 0.05 (overfit p = 2 gives |φ₂| < 0.08, the near-zero lag-2
  PACF); MA(1) with θ = 0.5 is recovered within 0.08; both innovation
  variances land within 0.15 of the true 1.0.
- CSS log-likelihood matches hand-computed values −3.825292490936347
  (AR(1)) and −3.806951651082006 (ARMA(1,1)) to 1e-9, and the true
  φ = 0.7 beats φ = 0 on the synthetic AR(1) data.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
