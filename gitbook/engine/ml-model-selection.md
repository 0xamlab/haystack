---
icon: clock-rotate-left
description: Walk-forward, purged, k-fold and temporal splits for leakage-free time-series model selection.
---

# Time-series model selection (walk-forward & purged CV)

`model_selection` provides cross-validation splitters that respect time — the
foundation for validating any model trained on sequential data (markets,
sensors, demand). Random k-fold leaks the future into training; these
splitters never do.

All functions run natively in the Mojo engine (zero Python imports,
deterministic, seeded where applicable).

## Functions

| Function | What it does |
|---|---|
| `walk_forward_splits(n, n_splits, min_train, expanding)` | Ordered walk-forward folds: train on `[0, k)`, test on the next contiguous window. `expanding=True` grows the training window each fold; `False` rolls it at `min_train`. Test windows are contiguous, non-overlapping, and cover the tail. |
| `purged_walk_forward_splits(n, n_splits, min_train, purge_gap, embargo)` | Finance-grade walk-forward: drops `purge_gap` samples between train end and test start (removes label leakage from overlapping forward-return windows) and embargoes `embargo` samples after each test window from later training folds. |
| `kfold_splits(n, k, seed, shuffle)` | Classic k-fold for non-temporal data. |
| `stratified_kfold_splits(labels, k, seed)` | K-fold preserving class proportions per fold. |
| `train_test_split_temporal(n, test_fraction)` | Single ordered split. |

## When to use purged CV

If your label at time *t* is computed from data in *(t, t+h]* (a forward
return, a settlement outcome), a plain walk-forward split lets training
samples within *h* of the test boundary see part of the test window's
future. Set `purge_gap >= h` to remove them. This is the standard
Lopez de Prado correction for overlapping-label leakage.

## Verification

Every splitter is covered by known-value geometry tests plus a
50k-split invariant fuzzer.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
