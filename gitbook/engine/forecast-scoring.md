---
icon: bullseye-arrow
description: Score probabilistic forecasts honestly — Brier skill, calibration error, and the Murphy decomposition that separates being wrong from being overconfident.
---

# Forecast scoring & the Murphy decomposition

`forecast_metrics` scores probabilistic forecasts against what actually happened. It exists because a
single accuracy number hides the two ways a forecast fails, and they call for opposite fixes.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

probs    = [0.9, 0.7, 0.3, 0.1, 0.2, 0.8]
outcomes = [1.0, 1.0, 0.0, 0.0, 1.0, 1.0]

base = runtime.execute("forecast_metrics", "base_rate", [outcomes])["result"]
runtime.execute("forecast_metrics", "brier_score", [probs, outcomes])["result"]
runtime.execute("forecast_metrics", "brier_skill_score", [probs, outcomes, base])["result"]
```

## Functions

| Function | What it does |
|---|---|
| `brier_score(probs, outcomes)` | Mean squared error of probabilistic forecasts against 0/1 outcomes. |
| `brier_skill_score(probs, outcomes, baseline)` | Skill against a constant-probability baseline. **This is the number to report**, not raw Brier. |
| `base_rate(outcomes)` | Observed event frequency — the climatological baseline to score against. |
| `expected_calibration_error(probs, outcomes, n_bins)` | Bin-weighted mean \|forecast − observed\|. |
| `reliability_bins(probs, outcomes, n_bins)` | Per-bin forecast mean, observed frequency and count — the reliability diagram. |
| `murphy_decomposition(probs, outcomes, n_bins)` | `BS = reliability − resolution + uncertainty`. Separates miscalibration from lack of discrimination. |
| `log_loss(probs, outcomes, eps)` | Mean negative log likelihood, clipped so a confident miss is heavy but finite. |
| `spearman_rho(a, b)` | Rank correlation with proper average-rank tie handling. |

## Why raw Brier misleads on rare events

For an event with a 3% base rate, a forecast that always predicts 3% already scores about
`p(1−p) = 0.029`. A model scoring 0.027 looks excellent and has roughly **7% skill**. Brier skill score
divides that out by scoring against the constant-rate baseline explicitly, which is why it is the primary
number here and raw Brier is reported beside it rather than instead of it.

## Reliability against resolution, and why the split matters

The Murphy decomposition splits the Brier score into three parts:

* **reliability** — how far your stated probabilities are from observed frequencies. Low is good.
* **resolution** — how far your forecasts move away from the base rate. High is good.
* **uncertainty** — `p(1−p)` of the outcome itself. Not yours to change.

The split matters because the two failure modes need opposite responses. A model can improve its Brier by
becoming better calibrated while *losing* discrimination — it hedges toward the base rate, looks better
on one number, and has become less useful. Only the decomposition shows that trade.

It also localises drift. A model deployed into new conditions that holds its resolution while its
reliability rises tenfold has not stopped discriminating; it has become overconfident, and the fix is
recalibration rather than remodelling.

## Binning is shared

`expected_calibration_error` and `reliability_bins` call one binning function, so a published diagram and
a published ECE can never disagree about which bin a forecast fell in.

## Relationship to the other metrics modules

[`ml_metrics_extended`](runtime-library-catalog.md) provides *per-term* contributions
(`brier_score_term`, `calibration_ece_term`) for building your own aggregations; `ml.metrics` covers
point-prediction accuracy. `forecast_metrics` is the aggregate-scoring and decomposition layer above
them — use it when the question is "should I trust these probabilities", not "how accurate is this
classifier".

## Verification

The Murphy identity is asserted exactly: `reliability − resolution + uncertainty` must reconstruct the
Brier score. A constant base-rate forecast is checked to score exactly `p(1−p)` and exactly zero skill,
which is what makes the rare-event argument above testable rather than rhetorical. Spearman is verified
against tied inputs, where integer-rank shortcuts silently bias the coefficient.

**Next:** turn scores into probabilities with [probability calibration](ml-calibration.md), or compare
two models properly with [statistical model comparison](ml-model-comparison.md).
