---
icon: tree
description: Gradient-boosted regression trees with exact SSE-gain splits, subsampling and shrinkage.
---

# Gradient-boosted regression trees

`gbdt` fits gradient-boosted regression trees with squared loss — replacing
`xgboost.XGBRegressor` / `lightgbm.LGBMRegressor` /
`sklearn.ensemble.GradientBoostingRegressor` for tabular regression.
Depth-limited greedy variance-reduction splits, residual fitting, shrinkage
(learning rate), and seeded row subsampling, all on a flat row-major
feature matrix with an O(m log m) prefix-sum split search. Zero Python
imports.

## Functions

| Function | What it does |
|---|---|
| `GBDTModel` | The whole forest as flat parallel node lists (`split_feature` / `split_value` / `left_child` / `right_child` / `leaf_value`) with absolute indices; `tree_root[t]` is tree t's root. Leaf values are stored with the learning rate already applied. |
| `gbdt_fit(X, y, n_cols, n_trees, max_depth, learning_rate, min_leaf, subsample, seed)` | Fit boosted trees on flat row-major `X` (len(y) rows × n_cols), squared loss. Defaults: `min_leaf=1`, `subsample=1.0`, `seed=0`. |
| `gbdt_predict(model, x)` | Predict one feature row: `base_score` + one (lr-scaled) leaf per tree. O(n_trees × max_depth). |
| `gbdt_predict_batch(model, X, n_cols)` | Predict every row of a flat row-major matrix. |
| `gbdt_n_nodes(model)` | Total node count across the forest. |

## Fitting behavior

Boosting starts from `base_score = mean(y)`; each round fits a
depth-limited CART to the current residuals and adds
`learning_rate × leaf_mean` to the running prediction. Splits maximize the
SSE reduction `S_L²/n_L + S_R²/n_R − S²/m`, honoring `min_leaf` on both
sides; ties keep the lowest feature index and lowest threshold, so results
are deterministic. `subsample` in (0, 1) trains each tree on a seeded
Fisher-Yates row sample without replacement (clamped to ≥ 1 row);
residual updates always use all rows. Fitting is fully deterministic for a
fixed seed — the tests fit twice with `subsample=0.6, seed=42` and require
identical node counts and bit-identical predictions. Degenerate configs
(empty `y`, `n_cols <= 0`, short `X`, `n_trees <= 0`) return a
base-score-only model.

## Verification

Reference values in the tests are hand-computed from the
variance-reduction gain formula rather than snapshotted from a library:

- Step data (4 rows near 0, 4 near 1, targets 0/10): a depth-1 tree
  recovers the gap-midpoint threshold **0.65** and exact 0 / 10
  predictions; `learning_rate=0.5` scales them to exactly 2.5 / 7.5.
- `y = x` on [1..4]: split gains 3.0 / **4.0** / 3.0 → threshold 2.5,
  predictions 1.5, 1.5, 3.5, 3.5 (checked to 1e-12).
- `min_leaf` constraints: `min_leaf=1` picks split 1.5, `min_leaf=2`
  forces 2.5, `min_leaf=3` on n=4 collapses to a root leaf at the mean.
- 200 seeded synthetic rows of `y = x0 + 2·x1` (120 trees, depth 3,
  lr 0.1) reach train R² > 0.9; the subsampled fit still explains > 50%
  of variance.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
