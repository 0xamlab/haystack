---
icon: wave-square
description: ES-RNN-class residual correction over a frozen exponential-smoothing backbone — backbone selection, a per-series-adaptive window feature, and two correctors that consume it.
---

# ES-RNN residual correction

`esrnn` is a from-scratch reduction of Slawek Smyl's ES-RNN approach (the M4-competition
winner): a classical, per-series exponential-smoothing point forecast as a deterministic
backbone, plus a correction stage that predicts what the backbone gets wrong. Three modules
split that idea into reusable pieces with zero Python imports — `esrnn.global_residual`
picks the backbone and builds the per-series-adaptive feature a corrector consumes,
`esrnn.bias_correction` is the simplest possible non-zero corrector (one scalar), and
`esrnn.per_frequency` is a linear corrector fit independently per frequency over the same
feature. None of the three re-fits or re-derives a frozen driver — `holt_fitted`,
`damped_fitted`, `theta_fitted` (`forecasting.fitted`) and `ridge_regression`/`predict`
(`regression`) are called unmodified throughout.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("esrnn.global_residual", "esrnn_window_scale", [[1.0, -2.0, 3.0]])["result"]
# 2.0 — mean absolute value of the window: the per-series scale a shared corrector needs
# to see comparable inputs from series a thousand-fold apart in magnitude

runtime.execute("esrnn.bias_correction", "esrnn_bias_mean", [[1.0, 2.0, 3.0, 6.0]])["result"]
# 3.0 — mean of a pooled residual list: the entire "training" step of a bias-only corrector
```

## The modules

| Module | What it does |
| --- | --- |
| `esrnn.global_residual` | backbone selection among the frozen Holt/Damped/Theta drivers, the per-series window-scaling and multi-horizon feature, and the residual/correction arithmetic every corrector in this family shares |
| `esrnn.bias_correction` | the simplest non-zero corrector: one scalar equal to the mean of a caller-pooled residual list, broadcast across an entire forecast |
| `esrnn.per_frequency` | a linear (ridge-regression) corrector fit independently per frequency over the identical per-series-adaptive window feature |

## Backbone selection: three frozen drivers, one winner

`esrnn_select_backbone(y, horizon)` fits `holt_fitted`, `damped_fitted` and `theta_fitted` on
the same series and keeps the lowest-`insample_mae` survivor as a `BackboneFit` (`status`,
`method_id`, `has_forecast`, `values`, `insample_mae`, `status_name`). All three real shapes
are reachable: a clean trend line picks Holt, a rise that decelerates toward a plateau picks
Damped, and a series with one sharp early outlier picks Theta (its global least-squares line
does not carry the spike's disturbance forward the way an adaptive level/trend method does).
Ties resolve by declaration order — each later candidate only replaces the incumbent on a
strict improvement (`<`, never `<=`) — and at the exact M4-minimum shape `n=2, h=1`, Holt and
Damped both reach `insample_mae == 0.0`, a genuine floating-point tie (Theta refuses outright
below `n=3`): Holt wins, by construction, not by luck. If nothing fits at all, `status` is
`FC_ERR_ALL_UNDEFINED` (`every_candidate_undefined`) with `method_id = -1` and empty `values` —
a selection among nothing is reported as exactly that, never a silent fallback to one method.

`esrnn_backbone_forecast(y, method_id, horizon)` is the companion call: fit exactly one named
method, no selection — the way a caller reapplies the method `esrnn_select_backbone` chose on
a training-held-back prefix to a second truncation of the same series. It is bit-for-bit the
same as calling `holt_fitted`/`damped_fitted`/`theta_fitted` directly; an unrecognized
`method_id` refuses with `FC_ERR_METHOD` before any fit runs.

## The per-series-adaptive window feature

A single model shared across every series still needs per-series-comparable input. Two
functions build that: `esrnn_window_scale(window)` is the mean absolute value of an
already-sliced window (`mean(|1.0, -2.0, 3.0|) == 2.0` exactly; `0.0` on an empty window) — a
local scale computed from the window's own recent history, so training-time and
inference-time windows normalize the same way. `esrnn_scaled_window(window, scale,
step_frac)` divides the window by that scale and appends one extra pseudo-timestep, the
fraction `step / horizon` of which future step is being predicted:

```python
runtime.execute("esrnn.global_residual", "esrnn_scaled_window", [[2.0, 4.0], 2.0, 0.5])["result"]
# [1.0, 2.0, 0.5] — [window / scale, ...] + [step_frac]
```

That trailing `step_frac` is the multi-horizon reduction: a corrector whose trained head
predicts one scalar per window (see [LSTM sequence training](ml-sequence-training.md)) can
still predict every step of a multi-step horizon, by pooling one window per `(series, horizon
step)` pair that differs only in this last entry. `esrnn_scaled_window` refuses (empty) when
`scale` is non-finite or not strictly positive — a window that never varied has nothing to
normalize by, and dividing by zero or a negative scale would invert or blow up every input
rather than surfacing the defect.

`esrnn_residual(actual, forecast)` and `esrnn_apply_correction(backbone, residual_hat)` are
the shared elementwise arithmetic — subtract, then add back — that both correctors below
reuse rather than reimplement. Both refuse (empty) on a length mismatch or any non-finite
input instead of silently iterating `min(len(a), len(b))`, which would drop the tail of
whichever list ran longer.

## Two correctors over the same feature: a scalar bias, or a per-frequency line

`esrnn.bias_correction` is the minimal case: `esrnn_bias_mean(residuals)` reduces a
caller-pooled residual list to one number (a caller decides the pool — every residual from
one frequency, for a single shared bias, or just one series' own residuals, for a
per-series-adaptive one), and `esrnn_apply_bias(backbone, bias)` broadcasts it: one add per
output element, with no capacity to react to horizon step or series history. If every
training-holdout residual really were the same number, the round trip is exact:

```python
actual   = [5.0, 6.0, 7.0]
forecast = [4.0, 5.0, 6.0]
resid = runtime.execute("esrnn.global_residual", "esrnn_residual", [actual, forecast])["result"]
# [1.0, 1.0, 1.0]
bias = runtime.execute("esrnn.bias_correction", "esrnn_bias_mean", [resid])["result"]
# 1.0
runtime.execute("esrnn.bias_correction", "esrnn_apply_bias", [forecast, bias])["result"]
# [5.0, 6.0, 7.0] == actual, exactly
```

A residual that actually varies is deliberately **not** fully fixed — proof the corrector is
genuinely one scalar, not a per-element fix in disguise. With `actual = [5.0, 6.0, 10.0]` and
`forecast = [4.0, 5.0, 5.0]`, the residual is `[1.0, 1.0, 5.0]`, its mean is `7/3 ≈ 2.333`, and
the corrected forecast leaves a different, nonzero leftover error at index 0 and index 2.

`esrnn.per_frequency` fits a linear corrector instead: `esrnn_fit_frequency_corrector(X, y,
alpha=1.0)` calls `regression.ridge_regression(X, y, alpha)` unmodified over an already-pooled
window matrix (one row per `(series, horizon step)` pair, matching `esrnn_scaled_window`'s own
shape) and adds the one check `ridge_regression` does not make on its own — `len(X) !=
len(y)` — refusing with an empty `RegressionResult` (`coefficients` and `residuals` both
empty, `r_squared = 0.0`) on that or an empty pool. Fit on data generated from a known,
zero-noise linear function (`y = 2*x0 + 3*x1 + 5` over 20 rows), it recovers coefficients
within `1e-6` of the true `[2.0, 3.0]`, an intercept within `1e-6` of `5.0`, and `r_squared >
0.999999` — the composition reaches the same signal a direct `ridge_regression` call would,
not merely a same-shaped result. `esrnn_apply_linear_correction(backbone, X, coefficients,
intercept)` composes `regression.predict` with `esrnn_apply_correction` in one call; correcting
an all-zero backbone with that fitted model reconstructs the original `y` to within `1e-6`,
pinning the correction's sign.

## Guarantees

- **Refusal, never a silent no-op.** `esrnn_apply_bias` returns empty on a non-finite bias or
  any non-finite backbone element; `esrnn_bias_mean` cannot return "empty" (a scalar has no
  such state), so it returns `0.0` — the neutral, correction-is-a-no-op value — on an empty
  input or any non-finite element, rather than propagating a NaN into every forecast the bias
  would otherwise touch. `esrnn_fit_frequency_corrector` and `esrnn_apply_linear_correction`
  refuse the same way on a bad shape or a non-finite value.
- **Composition, not reimplementation.** `esrnn_fit_frequency_corrector` and
  `esrnn_apply_linear_correction` are asserted bit-exact (`==`, not a tolerance) against direct
  calls to `regression.ridge_regression`/`predict`; `esrnn_backbone_forecast` is asserted
  bit-exact against a direct `holt_fitted`/`damped_fitted`/`theta_fitted` call.
- **No separately-supplied element count indexes a list.** `horizon` in
  `esrnn_backbone_forecast`/`esrnn_select_backbone` bounds only the output each frozen driver
  allocates, never an index into a caller-supplied list — every list-shaped input here is
  consumed by its own `len()`.
- **One status vocabulary.** Status codes reuse `forecasting.contract`'s shared 300-range
  (`FC_OK`, `FC_ERR_METHOD`, `FC_ERR_ALL_UNDEFINED`, ...) and `fc_status_name`; there is no
  second table.

## Verification

`mojo/tests/libs/test_esrnn_global_residual.mojo` cross-checks all three selection outcomes
(pure trend → Holt, decelerating rise → Damped, early-spike series → Theta) against the raw
`insample_mae` fields they rank, pins the exact `n=2, h=1` tie, and confirms
`esrnn_window_scale`/`esrnn_scaled_window`/`esrnn_residual`/`esrnn_apply_correction` against
hand-computed values including the round-trip identity
`apply_correction(backbone, residual(actual, backbone)) == actual`.
`mojo/tests/libs/test_esrnn_bias_correction.mojo` covers the known-value mean, the exact
round trip on a genuinely constant residual, the non-constant-residual leftover, and refusal
on non-finite input. `mojo/tests/libs/test_esrnn_per_frequency.mojo` pins
`esrnn_fit_frequency_corrector`/`esrnn_apply_linear_correction` bit-exact against direct
`ridge_regression`/`predict` calls, the zero-noise recovered signal, and refusal on an empty
pool, a length mismatch, and a non-finite coefficient.

**Next:** see the frozen backbone drivers this family selects among in
[Forecasting and backtesting](forecasting.md), or the shared-weight sequence trainer the
window feature was built to feed in [LSTM sequence training (BPTT)](ml-sequence-training.md).
