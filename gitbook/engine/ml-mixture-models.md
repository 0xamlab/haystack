---
icon: chart-scatter
description: Gaussian mixture models fit by log-space EM with BIC/AIC model selection.
---

# Gaussian mixture models

`mixture_models` fits Gaussian mixture models via expectation-maximization
— replacing `sklearn.mixture.GaussianMixture` (diagonal covariance) with
pure Mojo: seeded k-means++ initialization, log-space E-step
(log-sum-exp), variance-floored M-step, and BIC for choosing the number of
components. Zero Python imports.

## The modules

| Module | What it does |
| --- | --- |
| `mixture_models` | Gaussian mixture models fit by log-space EM — seeded k-means++ initialization, log-sum-exp E-step, variance-floored M-step, and BIC for choosing the number of components — replacing `sklearn.mixture.GaussianMixture` (diagonal covariance) |

## Functions

| Function | What it does |
|---|---|
| `GMMResult` | 1D fit result: `weights` / `means` / `vars` (components sorted by mean ascending), `loglik`, per-iteration `loglik_trace`, `iterations`, `converged`. |
| `GMMResultND` | N-D diagonal-covariance fit result; `means` / `vars` are flat row-major (k × cols), components sorted by first mean coordinate. |
| `gmm_fit(x, k, max_iter, tol, seed)` | Fit a k-component 1D Gaussian mixture via EM. Empty result if `len(x) == 0`, `k <= 0`, or `k > len(x)`. |
| `gmm_fit_nd(X, rows, cols, k, max_iter, tol, seed)` | Fit on flat row-major `X` (rows × cols) with diagonal covariance. Empty result on shape violations (`len(X) != rows * cols`, `k > rows`, ...). |
| `gmm_responsibilities(x, weights, means, vars)` | Posterior component probabilities per 1D point, flat (n × k); each row sums to 1. Empty list on inconsistent lengths. |
| `gmm_responsibilities_nd(X, rows, cols, weights, means, vars)` | Posterior component probabilities per N-D row, computed in log space. |
| `gmm_bic(loglik, n, k, dims)` | Bayesian Information Criterion, `p·ln(n) − 2·loglik` with `p = k(2·dims + 1) − 1`; lower is better. |

## Guarantees

- **EM monotonicity**: the E-step runs in log space via log-sum-exp, so
  `loglik_trace` is non-decreasing — the tests assert this on every fit
  (slack 1e-9). Convergence is `|Δloglik| < tol` before `max_iter`.
- **Determinism**: k-means++ initialization uses a seeded xorshift64 RNG;
  refitting with the same seed reproduces `loglik`, `iterations`, and
  means exactly (tested at seed 42).
- **No component collapse**: variances are floored at `VAR_FLOOR = 1e-9`
  and weights at `1e-12`; a single-point fit returns the exact mean with a
  floored variance, and all-equal data with k=2 stays finite (no NaN/inf).

## Choosing k with BIC

Fit each candidate k, then compare `gmm_bic(result.loglik, n, k, dims)` —
lowest wins. On the two-cluster test data (100 points near 0, 100 near
10), k=2 beats k=1 by BIC, and the fitted model recovers means within 0.5,
weights 0.5/0.5 within 0.1 (0.75/0.25 for a 150/50 split).

## Verification

Test reference values are hand-computed closed forms, checked to tight
tolerances:

- k=1 on `[1, 2, 3]` is the exact MLE: mean 2, population variance 2/3
  (to 1e-12), log-likelihood **−3.6486179374517715** (to 1e-9).
- Responsibilities under `w=[0.5,0.5], means=[0,10], vars=[1,1]`: the
  midpoint x=5 gives exactly 0.5/0.5; x=4 gives
  `1/(1+e^{−10}) = 0.9999546021312976` (to 1e-9).
- BIC: `gmm_bic(-100, 100, 2, 1) = 223.02585092994047` and
  `gmm_bic(-50, 200, 3, 2) = 174.1764431316725` (to 1e-6).

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
