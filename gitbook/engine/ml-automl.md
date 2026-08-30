---
icon: robot
description: Hyperband successive-halving schedules and Latin-hypercube search plans for hyperparameter optimization.
---

# Hyperparameter search schedules

`automl` generates the budget-allocation math behind modern hyperparameter
search — successive halving (Jamieson & Talwalkar 2016), Hyperband
(Li et al. 2018), and Latin-hypercube random search — replacing
`sklearn.model_selection.HalvingRandomSearchCV`'s halving arithmetic and
`scipy.stats.qmc.LatinHypercube`-style sampling with zero Python imports.
It is callback-free by design: every function returns a **schedule** (plain
data) that the caller executes however it likes — local train loops, remote
workers, anything.

## The modules

| Module | What it does |
| --- | --- |
| `automl` | budget-allocation schedules for hyperparameter search — successive halving (Jamieson & Talwalkar 2016), Hyperband (Li et al. 2018), and Latin-hypercube random search — replacing `sklearn.model_selection.HalvingRandomSearchCV`'s halving arithmetic and `scipy.stats.qmc.LatinHypercube`-style sampling |

## Functions

| Function | What it does |
|---|---|
| `successive_halving_schedule(n_configs, min_budget, eta)` | SHA rounds of `(n_survivors, budget)`: round *i* keeps `floor(n_configs / eta^i)` configs at budget `min_budget * eta^i`, until one survivor remains. Invalid input (`n_configs < 1`, `min_budget < 1`, `eta < 2`) → empty list. |
| `hyperband_brackets(max_budget, eta)` | Full Hyperband bracket list, ordered most-exploratory-first (`s = s_max .. 0`); each `Bracket` carries its `(s, n_configs, min_budget)` plus an embedded SHA schedule of `s + 1` rounds. |
| `promote_top_k(scores, k)` | Indices of the `k` highest scores, ordered best-first; ties broken deterministically toward the lower index; `k` clamps to `len(scores)`. |
| `random_search_configs(n, dims, seed)` | Latin-hypercube config matrix, `n` rows × `dims` columns, every value in `[0, 1)`; per dimension the `n` samples occupy the `n` strata exactly once. |

## Determinism and integer-exact schedules

Budgets and config counts use exact integer math — never float `log`/`pow`
— so schedules are bit-reproducible across platforms. The LHS sampler runs
on a seeded xorshift64 generator: identical output for the same
`(n, dims, seed)` (tests pin seed 42 reproducible, seed 43 different), and
per dimension `floor(v * n)` hits each of the `n` strata exactly once.

## Verification

The known-value tests pin the canonical schedules exactly, not approximately:

- SHA `n_configs=27, eta=3` → `(27,1), (9,3), (3,9), (1,27)`;
  `min_budget=2` scales budgets to `2, 6, 18, 54`; non-power-of-eta
  `n=10` floors to `(10,1), (3,3), (1,9)`.
- Hyperband `max_budget=81, eta=3` → exactly 5 brackets with
  `(n_s, r_s)` = `(81,1), (34,3), (15,9), (8,27), (5,81)` — the canonical
  Hyperband example table. Every bracket's final round runs at budget 81
  with ≥ 1 survivor, and the `s=0` bracket degenerates to plain random
  search: a single `(5, 81)` round.
- `promote_top_k([0.5, 0.9, 0.5, 0.7], 3)` → `[1, 3, 0]`: the 0.5 tie
  resolves to the lower index, so promotion decisions never depend on
  evaluation order.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
