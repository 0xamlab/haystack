---
icon: magnifying-glass-chart
description: KernelSHAP and permutation importance for explaining any model's predictions.
---

# Model explainability

`explainability` computes model-agnostic attributions over precomputed
prediction grids: permutation importance, partial dependence / ICE, and the
KernelSHAP coalition-weighting machinery. It replaces `sklearn.inspection`
(`permutation_importance`, `partial_dependence`) and the coalition design of
`shap.KernelExplainer`, with zero Python imports. Callback-free by design:
the caller evaluates its own model and passes flat metric / prediction
arrays; this kernel only aggregates and generates seeded coalition designs.

## Functions

| Function | What it does |
|---|---|
| `permutation_importance_from_preds(base_metric, permuted_metrics, n_features, n_repeats)` | Per-feature importance from precomputed metric evaluations: `means[f]` = mean over repeats of (permuted − base) metric, `stds[f]` = population std of the permuted metric. |
| `partial_dependence_grid(preds_at_gridpoints, n_grid, n_samples)` | Aggregates ICE evaluations into a PD curve: `mean[g]` = average prediction at grid point g, `std[g]` = ICE spread over samples. |
| `kernel_shap_weight(n_features, coalition_size)` | KernelSHAP kernel weight `pi(z) = (M-1) / (C(M,\|z\|) · \|z\| · (M-\|z\|))`; 0.0 for the degenerate empty/full coalitions. |
| `shapley_sampling_weights(n_features, n_samples, seed)` | Seeded 0/1 coalition matrix (flat row-major) with the matching `pi(z)` weight per row; never emits an all-zero or all-one coalition. |

## Usage and determinism

- `permuted_metrics` is flat **feature-major** (`f * n_repeats + r`);
  `preds_at_gridpoints` is flat **grid-major** (`g * n_samples + s`). Bad
  dimensions or length mismatches return empty structs, never partial
  results.
- Importance signs follow loss-style metrics (lower is better → positive
  means the feature matters); negate for higher-is-better scores. `stds` is
  the population std (ddof = 0), matching sklearn's `importances_std`.
- Large `std[g]` on the PD curve flags interactions the PD average hides.
- `shapley_sampling_weights` uses a seeded xorshift64 generator and is
  deterministic for a given seed. To recover SHAP values, mask inputs per
  coalition row, form `y[s] = f(masked_s) - f(background)`, scale row s and
  `y[s]` by `sqrt(weights[s])`, and solve with `ensembles.stack_fit_ridge`.

## Verification

Known-value tests pin the arithmetic against hand-computed references:

- Kernel weights: `pi(4,1) = 0.25`, `pi(4,2) = 0.125`, `pi(4,3) = 0.25`,
  `pi(2,1) = 0.5`, `pi(3,1) = pi(3,2) = 1/3`, `pi(10,2) = 0.0125`, all to
  1e-15, plus the symmetry `pi(k) == pi(M-k)` across M = 7.
- Permutation importance: base 0.1 with feature-0 repeats {0.2, 0.3, 0.4}
  gives mean +0.2 and population std `sqrt(0.02/3)` exactly (1e-12); a
  metric that improves under permutation yields the negative importance
  −0.2.
- Partial dependence: ICE column {1, 2, 3} → mean 2.0, std `sqrt(2/3)`
  (1e-12); constant predictions give a flat curve with zero spread.
- Coalition sampling: 200 draws at M = 4, seed 7 are bit-identical on
  re-run, differ under seed 8, contain only 0/1 entries with no empty or
  full rows, and every row's weight matches `kernel_shap_weight(4, |z|)`;
  at M = 2 every row is a singleton with weight exactly 0.5.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
