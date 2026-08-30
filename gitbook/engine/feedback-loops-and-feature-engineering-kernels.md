---
icon: arrows-rotate
description: Scalar scoring functions for the data flywheel (drift, retraining triggers, RLHF reward, calibration) and the scaling/encoding/selection utilities that build model inputs from raw columns.
---

# Feedback loops and feature engineering

Four small modules split across two different jobs. `data_feedback_loop` and
`evaluation_feedback` are the closing-the-loop half: every function in both takes a handful of
already-computed statistics (a mean, a rate, an error, a count) and returns one scalar — a drift
score, a retraining-trigger value, a reward signal, a required sample size — the kind of number a
training pipeline checks against a threshold to decide whether to relabel, retrain, or promote a
shadow model to production. `feature_engineering` and `feature_selection` are the other half: the
former turns one raw value into one model-ready value (scaled, transformed, binned, encoded)
given caller-supplied statistics; the latter looks at a whole feature matrix and returns which
*columns* of it are worth keeping. None of the four import Python, and — like the rest of this
kernel tree — none of them talk to each other or to a training loop directly; the runtime just
exposes the arithmetic and the caller wires it into whatever loop it is running.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Should we retrain? benefit = 10*degradation + drift + log(new_volume+1); score = benefit - cost
runtime.execute("data_feedback_loop", "retraining_trigger_score",
                [0.1, 0.5, 9.0, 1.0])["result"]
# 2.802585092994046 — positive means retrain now

# How many eval samples to resolve a 0.02 standard error against a metric with std 0.4?
runtime.execute("evaluation_feedback", "evaluation_sample_efficiency", [0.02, 0.4])["result"]
# 400.0 — (0.4 / 0.02)^2, the same n an online A/B test at that pooled std would need
```

## The modules

| Module | What it does |
| --- | --- |
| `data_feedback_loop` | Ten scoring functions for the data-centric side of the loop: active-learning sample value, auto-label (pseudo-labeling) confidence, data drift as a z-score, a combined retraining-trigger score, exponential-decay dataset freshness, annotation-effort estimation, an all-gates-must-pass deployment-readiness score, an online A/B z-statistic, feedback-signal quality, and a drift/forgetting-aware continual-learning rate. |
| `evaluation_feedback` | Ten scoring functions for the model-evaluation side: EMA rolling accuracy, a per-point KS-statistic contribution, a per-bin PSI term, normalized prediction-mean shift, RLHF reward from human ratings, inter-annotator label-noise estimation, a streaming AUC update, calibration (ECE) drift, production-vs-shadow-model divergence, and minimum sample size for a target standard error. |
| `feature_engineering` | Ten scalar transforms for one value at a time, each taking its statistics (min/max, mean/std, median/IQR, a smoothing constant) as arguments rather than computing them: min-max, z-score, and robust scaling; log1p, Box-Cox, and Yeo-Johnson power transforms; a polynomial feature cross; a percentile-rank lookup; Bayesian-smoothed target encoding; and equal-width bin assignment. |
| `feature_selection` | Nine functions over a full `List[List[Float64]]` feature matrix: per-column mean/variance, a variance-threshold filter, a pairwise-correlation filter, correlation-based F-test scores, top-k selection by score, greedy forward selection by MSE reduction, binned mutual information (information gain), and a cyclic-shift approximation of permutation importance. The module docstring calls this out directly: it "replaces `sklearn.feature_selection`" for the pure-Mojo runtime. |

## Same scaling math as `ml.preprocessing`, called a different way

`feature_engineering`'s `minmax_scale`, `standard_scale`, and `robust_scale` compute exactly the
same formulas as `ml.preprocessing`'s `normalize_minmax`, `normalize_zscore`, and
`normalize_robust`, documented in [Classical ML algorithms](ml-classical-algorithms.md) — but the
two modules split the work at a different point. `ml.preprocessing`'s functions take a whole
`List[Float64]` column, compute the min/max, mean/sample-stdev, or median/IQR themselves, and
return every scaled value at once. `feature_engineering`'s functions take one `x` and the
statistic(s) already computed by the caller, and return one scaled value. This is provable, not
just plausible: feeding the exact statistics `ml.preprocessing` computes internally for its
textbook eight-point dataset (`[2, 4, 4, 4, 5, 5, 7, 9]`, mean `5.0`, sample stdev
`2.138089935299395`, median `4.5`, IQR `1.5`) into `feature_engineering`'s scalar functions
reproduces the same-position output to the last representable digit:

```python
runtime.execute("feature_engineering", "minmax_scale", [9.0, 2.0, 9.0])["result"]
# 1.0 — matches ml.preprocessing.normalize_minmax([2,4,4,4,5,5,7,9])'s last element exactly

runtime.execute("feature_engineering", "standard_scale", [9.0, 5.0, 2.138089935299395])["result"]
# 1.8708286933869707 — matches normalize_zscore's last element exactly

runtime.execute("feature_engineering", "robust_scale", [9.0, 4.5, 1.5])["result"]
# 3.0 — matches normalize_robust's last element exactly
```

In other words, `feature_engineering` is the "transform" half of a fit/transform split that
`ml.preprocessing` does not separate — the shape a production feature store or a DL data loader
actually needs, where the statistics are computed once (at training time, or from a running
buffer) and then applied to one incoming sample at inference or streaming-ingestion time, rather
than recomputed from a full column on every call. `feature_selection` has no equivalent
classical-namespace counterpart; there is no `ml.feature_selection` in the contract, and it should
not be confused with `model_selection` (leakage-free walk-forward/purged/k-fold *splitters* for
time-series cross-validation — see [Time-series model selection](ml-model-selection.md) — which
picks training/test row splits, not feature columns) or the already-documented `feature_hashing`
(which maps arbitrary tokens into fixed-width hash buckets — an encoding scheme, not a selection or
scaling one, see [Feature hashing](ml-feature-hashing.md)).

## Two ten-function families reading the same loop from different ends

`data_feedback_loop` is the data engineer's view of the flywheel — what to label next
(`sample_informativeness`, `auto_label_confidence`), when the input distribution has moved
(`data_drift_detection_score`), whether to act on it (`retraining_trigger_score`, which blends
performance degradation, drift, new-data volume, and compute cost into one signed number — positive
retrains, negative waits), and whether the result is safe to ship
(`deployment_readiness_score`). `evaluation_feedback` is the model evaluator's view — drift
detection restated as the two textbook statistics an ML monitoring dashboard actually plots
(`model_drift_ks_stat` for a per-point Kolmogorov-Smirnov contribution, `population_stability_index`
for a per-bin PSI term — both accumulate by summing/maxing across bins or sample points, which is
the caller's job, not the kernel's), plus the human-feedback side (`feedback_reward_signal` for
RLHF, `label_noise_rate_estimate` for annotator disagreement) and the shadow-deployment check
(`shadow_model_divergence`) that validates a candidate model against production traffic before
promotion.

## Worked examples: the loop

Every number below was traced by hand against the real formulas in `mojo/engine/data_feedback_loop.mojo`
and `mojo/engine/evaluation_feedback.mojo` — see [Verification](#verification).

**Drift as a z-score, two ways.** `data_drift_detection_score` and `evaluation_feedback`'s
`prediction_shift_score` are the identical `|a - b| / std` shape applied to different quantities —
one to an input feature's mean, one to a model's prediction mean:

```python
runtime.execute("data_feedback_loop", "data_drift_detection_score", [5.4, 5.0, 0.2])["result"]
# 2.0 — current feature mean is 2 standard deviations from baseline (right at the ">2 = significant" line)

runtime.execute("evaluation_feedback", "prediction_shift_score", [0.55, 0.5, 0.1])["result"]
# 0.5 — model's mean output has drifted half a standard deviation from its reference
```

**An A/B test and the sample size it needed.** `online_evaluation_stat`'s z-statistic and
`evaluation_sample_efficiency`'s minimum-sample-size formula share the same `std / sqrt(n)` /
`(std/SE)^2` relationship — plug the same pooled std and sample count into both and they agree:

```python
runtime.execute("data_feedback_loop", "online_evaluation_stat", [0.62, 0.60, 0.4, 400.0])["result"]
# 1.0 — z = (0.62 - 0.60) / (0.4 / sqrt(400)) = 0.02 / 0.02

runtime.execute("evaluation_feedback", "evaluation_sample_efficiency", [0.02, 0.4])["result"]
# 400.0 — the n that A/B test actually used, recovered from (metric_std / target_std_error)^2
```

**Deployment readiness is a hard gate, not a weighted average.** `deployment_readiness_score`
multiplies two pass/fail indicators by the safety score — either gate failing zeroes the result
regardless of how good the other numbers are:

```python
runtime.execute("data_feedback_loop", "deployment_readiness_score",
                [0.92, 0.90, 0.03, 0.05, 0.95])["result"]
# 0.95 — accuracy 0.92 >= 0.90 (pass), bias 0.03 <= 0.05 (pass): 1 * 1 * 0.95

runtime.execute("data_feedback_loop", "deployment_readiness_score",
                [0.85, 0.90, 0.03, 0.05, 0.95])["result"]
# 0.0 — accuracy 0.85 < 0.90 fails the gate; the 0.95 safety score never gets multiplied in
```

**Label noise from annotator agreement, corrected for chance.** `label_noise_rate_estimate`
subtracts the agreement rate expected from `n_annotators` guessing at random before treating the
rest of the disagreement as real noise:

```python
runtime.execute("evaluation_feedback", "label_noise_rate_estimate", [0.9, 5.0])["result"]
# 0.125 — expected chance agreement is 1/5 = 0.2; noise = 1 - (0.9-0.2)/(1-0.2) = 1 - 0.875
```

## Worked examples: feature engineering

Every number below was traced by hand against `mojo/engine/feature_engineering.mojo` — see
[Verification](#verification).

```python
runtime.execute("feature_engineering", "log_transform", [9.0])["result"]
# 2.302585092994046 — log(1 + 9) = log(10)

runtime.execute("feature_engineering", "box_cox_transform", [4.0, 0.5])["result"]
# 2.0 — (4^0.5 - 1) / 0.5 = (2 - 1) / 0.5

runtime.execute("feature_engineering", "box_cox_transform", [4.0, 0.0])["result"]
# 1.3862943611198906 — lambda == 0 falls back to log(x) = log(4)

runtime.execute("feature_engineering", "yeo_johnson_transform", [3.0, 0.5])["result"]
# 2.0 — x >= 0 branch: ((3+1)^0.5 - 1) / 0.5 = (2 - 1) / 0.5

runtime.execute("feature_engineering", "yeo_johnson_transform", [-3.0, 0.5])["result"]
# -4.666666666666665 — x < 0 branch: -((3+1)^1.5 - 1) / 1.5 = -(8 - 1) / 1.5

runtime.execute("feature_engineering", "feature_cross", [3.0, 4.0, 2.0])["result"]
# 12.0 — degree == 2.0 takes the fast path and returns the raw product x*y

runtime.execute("feature_engineering", "feature_cross", [3.0, 4.0, 4.0])["result"]
# 144.0 — degree != 2.0 falls through to (x*y)^(degree/2) = 12^2

runtime.execute("feature_engineering", "target_encode_smooth", [0.8, 0.3, 10.0, 5.0])["result"]
# 0.6333333333333333 — (10*0.8 + 5*0.3) / (10 + 5), pulled toward the 0.3 global mean by smoothing=5

runtime.execute("feature_engineering", "binning_equal_width", [7.0, 0.0, 10.0, 5.0])["result"]
# 3.0 — (7-0)/10 * 5 = 3.5, truncated (not rounded) to bin index 3
```

`feature_cross`'s two branches are worth noting: `degree == 2.0` is a real special case (a fast
path for the single most common polynomial degree, ordinary multiplication), not a rounding
artifact of the general `exp(degree/2 * log(product))` path below it — which is why a non-negative
product raised to degree 2 through either branch gives the identical `12.0`, but a negative product
at a non-integer degree returns `0.0` from the general path instead of a complex number.

## Worked examples: feature selection

`feature_selection`'s functions chain into a real, if tiny, selection pipeline. Take a 5-row,
2-column matrix where column 0 carries signal and column 1 is a dead constant feature:

```python
X = [[1.0, 5.0], [2.0, 5.0], [3.0, 5.0], [4.0, 5.0], [5.0, 5.0]]
y = [2.0, 4.0, 5.0, 4.0, 5.0]

runtime.execute("feature_selection", "column_mean", [X])["result"]
# [3.0, 5.0]

runtime.execute("feature_selection", "column_variance", [X])["result"]
# [2.0, 0.0] — population variance; column 1 is exactly constant

runtime.execute("feature_selection", "variance_threshold", [X, 0.0])["result"]
# [0] — only column 0 clears "variance > 0.0"; column 1's 0.0 does not satisfy strict ">"

runtime.execute("feature_selection", "f_test_scores", [X, y])["result"]
# [4.499999999999999, 0.0] — column 0's r^2 = 0.6 gives F = 0.6*3/0.4 = 4.5;
#                            column 1 has zero variance, so denom < 1e-30 and it scores 0.0

runtime.execute("feature_selection", "select_k_best", [[4.5, 0.0], 1])["result"]
# [0] — the higher-scoring column wins

runtime.execute("feature_selection", "forward_selection_greedy", [X, y, 1])["result"]
# [0] — adding column 0 alone drops MSE to 0.48; column 1 alone leaves MSE at 1.2 (no signal)

runtime.execute("feature_selection", "information_gain", [[1.0, 2.0, 3.0, 4.0, 5.0], y, 2])["result"]
# 0.2231435513142097 nats — 2-bin mutual information between column 0 and y
```

For the pairwise-correlation filter, extend to three columns where column 1 is an exact duplicate
of column 0 (correlation 1.0) and column 2 is a third, weakly-anticorrelated feature (correlation
-0.5 with column 0):

```python
X3 = [[1.0, 1.0, 5.0], [2.0, 2.0, 3.0], [3.0, 3.0, 1.0], [4.0, 4.0, 4.0], [5.0, 5.0, 2.0]]

runtime.execute("feature_selection", "correlation_filter", [X3, 0.95])["result"]
# [0, 2] — column 1 is dropped: |corr(col0, col1)| = 1.0 > 0.95;
#          |corr(col0, col2)| = 0.5 does not exceed the threshold, both 0 and 2 survive
```

`correlation_filter` only ever drops the *later* column of a correlated pair (`removed[j_col]`,
never `removed[i_col]`), and a column that reaches the loop already marked removed is skipped
entirely rather than re-evaluated against the columns after it — so which of two correlated
columns survives depends on their order in the matrix, not on which one carries more signal.

`feature_importance_permutation` uses a "deterministic cyclic permutation for reproducibility," per
its own docstring, not sklearn's shuffle-and-refit: at `n_permutations=1` it shifts every row by one
position (`si = (i + 1) % n`) and re-scores using the *literal difference* between a feature's
original and shifted values (scaled by `0.01`) as a proxy penalty, rather than actually refitting a
model on the permuted column:

```python
runtime.execute("feature_selection", "feature_importance_permutation", [X, y, 1])["result"]
# [0.039999999999999813, 0.0] — column 0's biggest cyclic-shift jump contributes (4.0^2)*0.01/5;
#                               column 1 never changes value under any shift (it's constant), so it scores exactly 0.0

runtime.execute("feature_selection", "feature_importance_permutation", [X, y, 5])["result"]
# [0.04799999999999991, 0.0] — a different n_permutations changes column 0's score, because each
#                              round uses a *different* fixed shift ((p+1) % n), not a fresh random resample of the same one
```

## Edge cases and refusal behavior

Every function across all four modules is a `def` that operates on plain scalars or lists — there
is no `raise`s path in any of the four source files. Guarding happens by returning a defined
sentinel instead of dividing by zero, indexing past a list's end, or taking `log` of a non-positive
number:

- **Division-by-zero guards return `0.0`, not `nan`/`inf`.** `data_drift_detection_score` (baseline
  std `<= 0`), `online_evaluation_stat` (pooled std or `n <= 0`), `minmax_scale`/`standard_scale`/
  `robust_scale` (range/std/IQR `<= 0`), and `binning_equal_width` (range or bin count `<= 0`) all
  short-circuit to `0.0` before the division that would otherwise produce it.
- **`dataset_freshness_score`'s guard goes the other way.** A `half_life_days <= 0` returns `1.0`
  (maximally fresh) rather than `0.0` — the function treats "no decay configured" as "nothing has
  gone stale yet," not as an error state.
- **`evaluation_sample_efficiency`'s guard returns a deliberately huge sentinel.** A
  `target_std_error <= 0` returns `1e6` rather than `0.0` or infinity — an impossible-to-satisfy
  target reads as "you would need at least a million samples," not as an undefined result.
- **Log-domain guards skip the term instead of crashing.** `population_stability_index` returns
  `0.0` if either proportion is `<= 0` (avoiding `log` of a non-positive number for that bin, on the
  assumption the caller sums per-bin contributions rather than dividing further);
  `log_transform`/`box_cox_transform` return the sentinel `-1e300` for `x <= -1` / `x <= 0`
  respectively, rather than raising on the domain violation.
- **`auto_label_confidence`'s zero-difficulty case drops a factor, not the whole result.** A
  `sample_difficulty <= 0.0` skips the division (which would otherwise be division by zero) and
  returns `exp(teacher_model_logprob)` alone, rather than `0.0` or the undivided product.
- **List-shape guards return empty rather than reading past the shorter list.** `f_test_scores`,
  `forward_selection_greedy`, and `feature_importance_permutation` all check `len(y) < len(X)`
  (indexing `y[i]` for every row of `X` would otherwise be an uncatchable abort on a mismatched
  runtime, not a Python-style `IndexError`) and return an empty list rather than proceeding.
  `information_gain` applies the same check to `len(target) < len(feature)`.
- **Negative or zero counts return empty rather than an invalid allocation.** `select_k_best`
  returns `[]` for `k <= 0` (a negative value would otherwise become a negative `List` capacity —
  an abort, per the source comment); `information_gain` returns `0.0` for `n_bins <= 0` for the
  same reason.
- **Untrusted iteration counts are clamped, not rejected.** `information_gain` clamps `n_bins` to
  `MAX_BINS = 1000` (the joint-histogram allocation is `n_bins^2`, so an unbounded value is a
  memory weapon) and `feature_importance_permutation` clamps `n_permutations` to
  `MAX_PERMUTATIONS = 100000` (each permutation round is `O(n)` work) — both continue with the
  clamped value rather than refusing the call outright.

## Verification

All four modules' test files — `test_data_feedback_loop.mojo`, `test_evaluation_feedback.mojo`,
`test_feature_engineering.mojo`, and `test_feature_selection.mojo` — are auto-generated coverage
smoke tests: every function in `data_feedback_loop`, `evaluation_feedback`, and
`feature_engineering` is called exactly once with the same shared, arbitrary fixture (mostly
`0.5` for every `Float64` argument), and the test only asserts the result is finite. It pins no
specific numeric output for any of the thirty functions across those three modules.
`test_feature_selection.mojo` goes further in one direction and less far in another: it does not
pin numeric output either, but it also only exercises two of `feature_selection`'s nine
functions (`select_k_best` and `information_gain`) — `column_mean`, `column_variance`,
`variance_threshold`, `correlation_filter`, `f_test_scores`, `forward_selection_greedy`, and
`feature_importance_permutation` are not called by the generated suite at all.

None of the worked numbers above came from a test assertion, because none exist to lift — every
one was computed independently in plain Python from the formulas in `mojo/engine/data_feedback_loop.mojo`,
`mojo/engine/evaluation_feedback.mojo`, `mojo/engine/feature_engineering.mojo`, and
`mojo/engine/feature_selection.mojo`, matching the same "hand-trace against the source, since the
test file won't do it for you" approach used for `ml.classifiers` and `ml.random_forest` in
[Classical ML algorithms](ml-classical-algorithms.md).

**Next:** see the batch statistics these scalar functions consume upstream in
[Classical ML algorithms](ml-classical-algorithms.md), or the categorical-hashing counterpart to
feature engineering in [Feature hashing](ml-feature-hashing.md).
