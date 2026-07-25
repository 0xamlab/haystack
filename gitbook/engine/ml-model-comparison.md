---
icon: scale-balanced
description: Paired bootstrap CIs, exact McNemar and Diebold-Mariano tests that decide whether a candidate model is genuinely better than the champion.
---

# Statistical model comparison

`model_compare` decides whether model B is genuinely better than model A —
with uncertainty, not a single point estimate. Comparing two accuracy
scalars answers nothing; these tests answer "is the difference real?"

## Functions

| Function | What it does |
|---|---|
| `paired_bootstrap_diff_ci(metric_a, metric_b, n_boot, alpha, seed)` | Confidence interval on `mean(a - b)` by resampling **pairs** (per-prediction correctness, per-trade PnL). If the CI excludes 0, the difference is real at level `alpha`. |
| `mcnemar_exact_p(b01, b10)` | Exact two-sided McNemar test on disagreement counts (A-wrong/B-right vs A-right/B-wrong). Log-space binomial; exact for any n. |
| `diebold_mariano(err_a, err_b, h)` | Forecast-accuracy comparison on squared-error loss differentials with Newey–West variance (lag `h-1`) — the standard test for comparing two forecasting models over time. |
| `sharpe_diff_bootstrap_ci(returns_a, returns_b, n_boot, alpha, seed)` | Paired bootstrap CI on the Sharpe-ratio difference between two return streams — compares models by **trading outcome**, not accuracy. |

## Recommended promotion gate

For a candidate model to replace a champion:

1. `paired_bootstrap_diff_ci` on per-sample correctness → CI lower bound > 0
2. `mcnemar_exact_p` < 0.05 on the disagreement table
3. `sharpe_diff_bootstrap_ci` on realized signal PnL → CI lower bound > 0

Any single point estimate can flatter a candidate; requiring the interval
to clear zero is what "only promote if better" means statistically.

## Serial dependence caveat

`paired_bootstrap_diff_ci`, `mcnemar_exact_p` and `sharpe_diff_bootstrap_ci`
assume exchangeable pairs. Overlapping forecast targets (stride-1 windows
predicting h-step returns) violate that badly — measured ~3× type-I
inflation at h = 5 in the design-partner system. For such data either
subsample every h-th observation before calling them, or use
`diebold_mariano(err_a, err_b, h)`, whose Newey–West variance (lags
`1..h-1`) is designed exactly for overlapping h-step forecast errors and
needs no subsampling.

## Design-partner origin

Powers autonomous champion/challenger promotion in a live trading system:
candidates fine-tuned on drift are promoted only when the paired tests
agree. Verified against independent references (McNemar to 2e-9 relative
error; Diebold–Mariano re-derived from the Newey–West definition).

**Next:** validate on honest splits with [time-series model selection](ml-model-selection.md), or browse the [engine catalog](catalog.md).
