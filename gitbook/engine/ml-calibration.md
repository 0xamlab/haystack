---
icon: sliders
description: Isotonic (PAV) and z-score affine calibration with reliability diagnostics for turning raw model scores into trustworthy probabilities.
---

# Probability & prediction calibration

`calibration` maps raw model scores to trustworthy probabilities or
magnitudes. A model can rank well and still be badly calibrated — betting
sizes, thresholds, and expected-value math all need calibrated outputs.

## Functions

| Function | What it does |
|---|---|
| `isotonic_fit(x, y)` / `isotonic_transform(...)` | Isotonic regression via Pool Adjacent Violators (weighted tie handling, sklearn-equivalent). Monotonic, non-parametric — the standard for calibrating regression outputs and probabilities without assuming a shape. |
| `platt_fit(scores, labels, max_iter)` / `platt_transform(a, b, scores)` | Platt scaling: logistic calibration with Platt's target smoothing — best when the miscalibration is sigmoidal and data is scarce. |
| `calibration_curve(probs, labels, n_bins)` | Reliability diagram data: per-bin predicted vs observed frequency and counts. Pair with the ECE/Brier metrics in `ml_metrics_extended`. |

## Choosing isotonic vs Platt

Isotonic fits any monotone distortion but needs more data (it can overfit
below ~1k samples). Platt is two parameters — robust when small. When in
doubt, compare both on a held-out reliability curve.

## Verification

Verified against sklearn's isotonic regression, including weighted-tie
pooling cases that break naive PAV implementations.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
