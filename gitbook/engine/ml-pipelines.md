---
icon: diagram-project
description: Composable fit/transform preprocessing pipelines (standardize, min-max, chained) with exact inverses.
---

# Fit/transform pipelines

`pipelines` replaces `sklearn.pipeline.Pipeline` composed with
`sklearn.preprocessing` — `StandardScaler`, `MinMaxScaler`,
`FunctionTransformer(log1p)`, clip, and `SimpleImputer(strategy="median")`
— as a pipeline **spec** executor with zero Python imports. Transforms are
encoded by integer id, fitted per-column statistics are flattened into one
`Float64` buffer, and transform/inverse replay the spec deterministically
on row-major matrices, fitting each step on the output of the previous
steps (sklearn `Pipeline.fit` semantics).

## The modules

| Module | What it does |
| --- | --- |
| `pipelines` | fit/transform/inverse preprocessing pipelines -- standardize, min-max, log1p, clip, and median-impute steps encoded by integer id and replayed deterministically from one flattened, fitted spec, with exact inverses where the step supports one -- replacing `sklearn.pipeline.Pipeline` composed with `sklearn.preprocessing` |

## Functions

| Function | What it does |
|---|---|
| `pipeline_fit(x, rows, cols, steps, params)` | Fit a step spec sequentially on flat row-major X; `params` supplies `(lo, hi)` per clip step in step order. Returns a `PipelineState` with `ok=False` on any invalid spec/shape (including clip `lo > hi`). |
| `pipeline_transform(state, x, rows)` | Apply the fitted steps in order to new data; empty list on shape mismatch or unfitted state. An empty spec is the identity. |
| `pipeline_inverse(state, y, rows)` | Apply step inverses in reverse order; `InverseResult.ok=False` if any step is clip or impute_median. |
| `pipeline_is_invertible(state)` | True iff every step has an exact inverse (standardize, minmax, log1p only). |
| `step_param_count(t, cols)` | Learned-param buffer length for one step id (`2*cols`, `2*cols`, `0`, `2`, `cols`); `-1` for unknown ids. |

Step ids: `0` standardize (population std, ddof=0), `1` minmax, `2` log1p,
`3` clip(lo, hi), `4` impute_median.

## NaN semantics and degenerate columns

Missing values are IEEE NaN. Fitting ignores NaN when learning statistics
(tests: column `[1, NaN, 3]` learns mean 2, std 1); standardize, minmax,
and clip pass NaN through unchanged; impute_median fills it with the
per-column median of non-NaN values — odd counts take the middle value,
even counts average (`[1, 5, NaN, NaN]` → 3.0), and an all-NaN column
imputes 0.0. Degenerate columns stay defined: `std == 0` or
`range == 0` maps to 0.0, and the inverse then recovers the mean / min
exactly.

## Verification

The tests pin hand-computed values end to end. Standardize on
`[[1,2],[3,4],[5,6]]` learns means `[3, 4]` and population std
`sqrt(8/3) = 1.6329931618554518` per column (z-scores
`±1.224744871391589`, checked to 1e-12). A standardize → minmax chain
fits the second step on the z-scores and produces exactly
`[0, 0, 0.5, 0.5, 1, 1]`; the unseen row `[7, 8]` maps to `[1.5, 1.5]`,
and `pipeline_inverse` round-trips both back to the originals within 1e-9
(this repo's `std.math` exp/log carry ~1e-10 relative error). log1p is
pinned at `log 2 = 0.6931471805599453` and returns NaN for `1 + x <= 0`.
A full five-step chain (impute → log1p → standardize → minmax → clip)
lands every output inside the clip bounds `[0.05, 0.95]` with the learned
buffer laid out at the documented offsets.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
