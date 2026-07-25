---
icon: layer-group
description: Stacking and weighted voting ensembles over arbitrary base-model predictions.
---

# Model ensembling

`ensembles` combines predictions from multiple models — zero Python
imports — replacing sklearn.ensemble's `VotingClassifier`,
`VotingRegressor`, and the `StackingRegressor` ridge meta-learner. It
operates on flat prediction matrices so any model type can feed it, and
complements `voting`, which is social choice theory and unrelated to
model ensembling.

## Functions

| Function | What it does |
|---|---|
| `voting_classify(pred_labels, n_models, n_samples, n_classes, weights)` | Majority / weighted-majority vote over per-model class labels; exact ties break toward the lowest class index. |
| `blend_regression(preds, n_models, n_samples, weights)` | Weight-normalized average of regression predictions per sample (`[1, 3]` behaves as `[0.25, 0.75]`). |
| `stack_fit_ridge(oof_preds, n_samples, n_models, y, l2)` | Closed-form ridge meta-weights from out-of-fold predictions: solves the normal equations `(XᵀX + l2·I) w = Xᵀy` exactly (no intercept). |
| `stack_predict(preds, n_samples, n_models, weights)` | Applies meta-weights raw — not normalized, since ridge weights already encode scale: `out[s] = Σ_m weights[m] · preds[s, m]`. |

Layout: `voting_classify` / `blend_regression` take model-major input
(entry [m, s] at `m * n_samples + s`); `stack_fit_ridge` /
`stack_predict` take sample-major input (entry [s, m] at
`s * n_models + m`).

## Usage guidance

- **Fully deterministic.** No RNG anywhere: identical inputs give
  identical outputs. Voting ties break to the lowest class index (test:
  two models predicting {1, 0} with uniform weights → 0), and labels
  outside `[0, n_classes)` contribute nothing to the vote.
- **Weight fallbacks.** A weights list of the wrong length (e.g. empty)
  means uniform 1.0; `blend_regression` also falls back to the uniform
  mean when `|sum(weights)| < 1e-12` (e.g. `[1, −1]`).
- **Singularity is signaled, not hidden.** The internal
  Gaussian-elimination solver (partial pivoting) returns the empty list
  when a pivot magnitude falls below 1e-12: duplicated models with
  `l2 = 0` yield empty; passing `l2 > 0` regularizes, and the duplicates
  then split the weight symmetrically, summing to ~1. Inconsistent
  dimensions also return empty across all four functions.

## Verification

Known-value tests pin every function to hand-computed results at 1e-12
tolerance: a 3-model × 4-sample majority vote returns `[0, 1, 2, 2]`, and
weights `[0.2, 0.2, 0.6]` flip sample 0 to give `[1, 1, 2, 2]`; blending
predictions `[1, 2]` / `[3, 6]` with weights `[0.25, 0.75]` gives
`[2.5, 5.0]`, identically for unnormalized `[1, 3]`. For the ridge
meta-learner, X = [1, 2], y = [2, 4] gives w = 10/6 at `l2 = 1` and
exactly 2 at `l2 = 0` (exact least squares); when model 1 equals y and
model 2 is a constant, `stack_fit_ridge` recovers weights ≈ [1, 0] and
the fit + predict roundtrip reproduces y within 0.05.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
