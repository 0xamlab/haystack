---
icon: scale-balanced
description: SMOTE, random over/under-sampling and balanced class weights for skewed datasets.
---

# Imbalanced-data resampling

`imbalance` rebalances classification datasets where one class dominates —
zero Python imports — replacing imbalanced-learn (`SMOTE`,
`RandomOverSampler`, `RandomUnderSampler`) and
`sklearn.utils.class_weight.compute_class_weight("balanced")`. It covers
synthetic minority oversampling by interpolation between nearest minority
neighbors, seeded random over/under-sampling to the majority/minority
count, and inverse-frequency class weights.

## Functions

| Function | What it does |
|---|---|
| `smote_1d(x, labels, minority_label, k_neighbors, n_synthetic, seed)` | SMOTE for a single feature: synthetic minority values, each on the interval between a minority value and one of its k nearest minority neighbors. |
| `smote_nd(X, n_features, labels, minority_label, k_neighbors, n_synthetic, seed)` | SMOTE for d features (row-major flat `X`): each synthetic row is `x_b + gap * (x_nb − x_b)` with `gap ~ U[0, 1)`, so it lies on the segment between two minority rows. |
| `random_oversample_indices(labels, seed)` | Indices resampled so every class reaches the max class count: originals in order, then each class's deficit filled by sampling with replacement. |
| `random_undersample_indices(labels, seed)` | Keeps min-class-count samples per class, chosen without replacement (partial Fisher–Yates), returned in ascending order. |
| `class_weights(labels)` | Balanced inverse-frequency weights per class: `weight_c = n / (n_classes * count_c)` — sklearn's `"balanced"` mode. |

## Usage guidance

- **Deterministic for a given seed.** All samplers draw from a seeded
  xorshift64 RNG: same seed → identical output, different seed →
  different output (both test-verified). Already-balanced labels return
  the identity `[0, n)`; empty labels return empty.
- **Infeasible configs return empty, never trap.** Fewer than 2 minority
  rows, `k_neighbors < 1`, `n_synthetic < 1`, `n_features < 1`, or a
  mis-sized `X` all yield an empty result; `k_neighbors` larger than
  `n_minority − 1` is clamped.
- **Cost.** Nearest neighbors are computed lazily once per distinct base
  row and cached, so worst case is
  O(min(n_synthetic, n_min) · n_min · n_features). SMOTE is offline
  training-data prep (never in the live decision loop); for typical
  minority classes (n_min ≤ ~1k) it is sub-millisecond.

## Verification

Geometry is test-pinned: with minority values {0, 10, 20} and majority
values {100, 101}, all 16 synthetic values stay inside the minority hull
[0, 20] — majority rows never leak into the interpolation. In 2-D with
minority rows A=(0,0), B=(4,0), C=(4,3) (squared distances AB=16, AC=25,
BC=9), every k=1 synthetic row lies on segment AB or BC — never AC —
matching the exact 1-NN structure, and k=2 rows are always convex
combinations of some minority pair. `class_weights([0,0,0,1])` returns
[2/3, 2] exact to 1e-12 with sample-weight mass preserved
(`sum count_c · w_c == n = 4`), matching sklearn's `"balanced"` formula;
oversampling `[0,0,0,1]` gives exactly `[0,1,2,3,3,3]`, and a 3-class
input balances every class to the max count of 3.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
