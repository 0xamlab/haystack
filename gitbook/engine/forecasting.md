---
icon: arrow-trend-up
description: Forecast a series, measure the method out of sample, put an honest band around it, and make a hierarchy add up — with a refusal wherever the answer does not exist.
---

# Forecasting and backtesting

Six kernel families for a series over time: point forecasts, rolling-origin backtesting,
prediction bands built from the errors the method actually made, hierarchical reconciliation,
and intermittent (mostly-zero) demand. All run as compiled kernels inside the runtime that
ships with the SDK — there is nothing to start and nothing to install separately.

The order matters, and it is the shape of the whole surface: **you backtest first, and the
band comes out of the backtest.** A band derived from the residuals of a model scored on its
own training data is not a prediction interval, and nothing in a fitted model can tell you so.

{% hint style="danger" %}
**For Holt, damped-trend and ETS(A,A,A), call `forecasting.fitted`, not the hand-parameterized
methods in `forecasting.point` below.** `forecasting.point.ets_aan_forecast` and
`ets_aaa_forecast` take `alpha`/`beta`/`phi` as arguments you must already know, and their
initial level/trend come from the frozen `timeseries_stats.holt_linear`, which copies
`l0 = y[0]`, `b0 = y[1] - y[0]` from the first two observations unfitted. At the smoothing
weights the M4 corpus actually selects, that one noisy first difference is extrapolated across
the entire forecast horizon. Measured on the same 95,000 M4 series, same metric: the frozen-init
kernel at its SSE-optimal parameters scores Monthly sMAPE **44.13** — worse than a naive
compensating parameter fit (18.05) — while `forecasting.fitted.holt_fitted`, which fits the
initial state jointly with the smoothing parameters, scores **13.97**, matching statsforecast
2.1.1's own state-space fit to 1e-10 on all 100,000 M4 series. See
[Fit the model instead of guessing its parameters](#fit-the-model-instead-of-guessing-its-parameters)
below before reaching for `ets_aan_forecast` or `ets_aaa_forecast` on real data. The other
`forecasting.point` methods — Theta, the AR forecast, the four baselines, seasonal adjustment —
are unaffected; this defect is specific to the Holt-family frozen initial state.
{% endhint %}

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

ETS_ANN = 4          # method ids come from forecasting.contract

# 60 observations, forecast 4 steps ahead from every second origin,
# never training on fewer than 24 points, expanding window
y = [10.0 + 0.5 * i for i in range(60)]

bt = runtime.execute("forecasting.backtest", "backtest_flat", [
    y, ETS_ANN, 4, 24, 2, True,   # series, method, horizon, min_train, step, expanding
    0, 0,                         # period, ar_order — unused by this method
    0.5, 0.1, 1.0, 2.0,           # alpha, beta, phi, theta
])["result"]

bt["n_origins_requested"]   # 17 — what the configuration admits
bt["n_origins_run"]         # 17 — how many produced a full 4-step forecast
bt["n_origins_refused"]     # 0
bt["n_cells"]               # 68 — origins x horizon
bt["mae"]                   # 1.74999999... pooled over every cell
bt["rmse"]                  # 1.83711730...
bt["worst_origin"]          # 12 — the origin with the largest MAE
bt["worst_origin_mae"]      # 1.75
```

`forecast`, `actual` and `error` come back as full row-major matrices, one row per origin, so
any statistic you want later can be computed without re-running anything.

## The modules

| Module | What it does |
| --- | --- |
| `forecasting.contract` | the package's one vocabulary: status names, method ids, size ceilings, the single empirical quantile, and one validator per class of input |
| `forecasting.point` | ETS(A,N,N) / ETS(A,A,N) with damped trend / ETS(A,A,A), Theta and a trend-reproducing Theta variant, a validated AR forecast, four baselines, and seasonal adjustment with a reversibility check |
| `forecasting.fitted` | `holt_fitted`, `damped_fitted` and `ets_aaa_fitted` — the same three model families as above, but with the smoothing parameters AND the initial level/trend/seasonal state fitted jointly by the reference Nelder-Mead optimizer, closing the frozen initial-state defect described above |
| `forecasting.backtest` | rolling-origin evaluation — per-origin and pooled errors, the worst origin, and MAE / RMSE / MAPE / sMAPE / MASE each with its own presence flag and undefined count |
| `forecasting.interval` | prediction bands from backtest residuals, per lead time, empirical or seeded-bootstrap, plus a measurement of the coverage they actually achieved |
| `forecasting.hierarchy` | bottom-up and top-down reconciliation of forecasts that must add up, and an audit of a hierarchy somebody else produced |
| `forecasting.intermittent` | mostly-zero demand: Croston with its bias-corrected variants, and an ADI / CV² classification of the series |

## Fit the model instead of guessing its parameters

`forecasting.fitted.holt_fitted(y, horizon)` and `damped_fitted(y, horizon)` fit `alpha`,
`beta` (and, for the damped driver, `phi`) by the same Nelder-Mead search statsforecast 2.1.1
uses, and fit the initial level and trend jointly with them rather than copying them from the
first two observations. `ets_aaa_fitted(y, period, horizon)` does the same for ETS(A,A,A),
additionally fitting the seasonal indices.

The corrupted-first-difference series below makes the defect concrete: `y[0] = 107`, then
`y_t = 100 + 3t`. The true trend is `+3`; the frozen kernel's unfitted `b0 = y[1] - y[0] = -4`
is the OPPOSITE sign, and at the small-beta regime a real fit selects, that one bad difference
never gets corrected:

{% tabs %}
{% tab title="Python" %}
```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

y = [107.0] + [100.0 + 3.0 * t for t in range(1, 12)]

fitted = runtime.execute("forecasting.fitted", "holt_fitted", [y, 6])["result"]
fitted["trend"]          # 2.7322175161337428 — recovers the true +3 trend
fitted["values"][5]      # 148.50739437590457 — 1.7% off the truth of 151

# the frozen, unfitted-init driver at the same small-beta regime a real fit selects
frozen = runtime.execute("forecasting.point", "ets_aan_forecast",
                         [y, 0.5, 0.0001, 1.0, 6])["result"]
frozen["trend"]          # -3.993701415029936 — extrapolates the corrupted first difference
frozen["values"][5]      # 102.04953508158104 — 32% off the truth of 151
```
{% endtab %}

{% tab title="TypeScript" %}
```ts
import { MojoRuntime } from "algenta-sdk";

const runtime = new MojoRuntime();

const y = [107.0, ...Array.from({ length: 11 }, (_, i) => 100.0 + 3.0 * (i + 1))];

const { result: fitted } = await runtime.execute("forecasting.fitted", "holt_fitted", [y, 6]) as {
  result: { trend: number; values: number[] };
};
fitted.trend;        // 2.7322175161337428 — recovers the true +3 trend
fitted.values[5];    // 148.50739437590457 — 1.7% off the truth of 151

const { result: frozen } = await runtime.execute("forecasting.point", "ets_aan_forecast", [
  y, 0.5, 0.0001, 1.0, 6,
]) as { result: { trend: number; values: number[] } };
frozen.trend;        // -3.993701415029936 — extrapolates the corrupted first difference
frozen.values[5];    // 102.04953508158104 — 32% off the truth of 151
```
{% endtab %}
{% endtabs %}

`init_status` / `init_solved` on the returned struct report the initial-state provenance
separately from `status`: for the non-seasonal drivers, a singular 2x2 system still forecasts
but is flagged; for `ets_aaa_fitted` there is no closed-form audit of a jointly-fitted seasonal
state, so it reports `init_status = FC_OK` with `init_solved = False` by construction.
`fitted_init_solve(y, alpha, beta, phi)` exposes the closed-form solve on its own, for a caller
who already has fitted smoothing parameters from elsewhere and only wants the matching initial
state.

`ets_aaa_fitted` with `period == 1` reduces to `holt_fitted` (`gamma` reported `0.0`) rather
than being refused, matching `forecasting.point.ets_aaa_forecast`'s own convention.

## Requested, run and refused are three different numbers

A forecaster may decline an origin whose training window cannot support it — a seasonal model
inside its first complete cycle, an AR model whose order exceeds the window, Croston in a
window with no positive demand. Reporting only the mean over the survivors would answer a
question nobody asked, so all three counts come back.

Two failures that look alike are deliberately different statuses:

* `no_complete_backtest_origin` — your `horizon`, `min_train` and `step` leave no origin at
  all. `backtest_origin_count` computes that number on its own, so you can size a run before
  making it.
* `every_candidate_undefined` — the configuration was fine and the forecaster declined every
  window.

"Your windows are too short" and "your method refused every window" need different fixes.

## The two error measures that are undefined more often than they look

```python
r = runtime.execute("forecasting.backtest", "forecast_errors_flat", [
    [0.0, 4.0, 8.0, 16.0],        # actual — note the exact zero
    [1.0, 5.0, 7.0, 15.0],        # forecast
    [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],   # the training series MASE scales by
    1,                            # seasonal period for that scale
])["result"]

r["mae"]                  # 1.0
r["mape"]                 # 14.5833... over the points where it exists
r["n_defined_mape"]       # 3
r["n_undefined_mape"]     # 1 — the actual of exactly 0.0
r["has_mase"]             # True
r["scale_denominator"]    # 1.0
```

`mape = 14.58` over 100 points and `mape = 14.58` over 3 points with 1 undefined are
completely different claims, and without the count they are the same number. MAPE is excluded
at an actual of **exactly** zero and nowhere else: a tiny nonzero actual gives an enormous but
genuinely defined ratio, and screening it out with a small constant would be a hidden
tolerance at a scale you never chose.

MASE has two separate ways to not exist, and they are separate flags:

```python
r = runtime.execute("forecasting.backtest", "forecast_errors_flat", [
    [0.0, 4.0, 8.0, 16.0], [1.0, 5.0, 7.0, 15.0],
    [1.0, 2.0, 1.0, 2.0, 1.0, 2.0],    # an exactly periodic training series
    2,
])["result"]

r["has_scale"]            # True — the denominator was computable
r["scale_denominator"]    # 0.0 — and it is zero
r["has_mase"]             # False — so there is no MASE
```

"No denominator" and "a denominator of zero" are different facts about your data, and one
flag cannot carry both.

## A band needs enough residuals, and a bootstrap does not change that

A two-sided band at level `L` is read off the `(1-L)/2` and `(1+L)/2` quantiles of the
residuals at that lead time. The smallest nonzero tail probability `k` order statistics can
express is `1/k`, so the band needs `k >= 2 / (1 - L)` residuals — and one residual per lead
time comes from one backtest origin:

```python
for level in (0.90, 0.95, 0.99):
    runtime.execute("forecasting.contract", "fc_min_samples_for_level", [level])["result"]
# 20, 40, 200
```

The 17-origin backtest above therefore cannot support a 95% band, and says so instead of
returning the min and max of seventeen numbers wearing a confidence label:

```python
band = runtime.execute("forecasting.interval", "interval_empirical_flat", [
    bt["error"], bt["n_origins_run"], 4,        # the backtest's own error matrix
    [40.0, 40.5, 41.0, 41.5], 0.95,             # the point forecast, and the level
])["result"]

band["status"]                     # 316
band["min_residuals_required"]     # 40
band["lower"]                      # [] — no padded lists, no per-step flags
runtime.execute("forecasting.contract", "fc_status_name",
                [band["status"]])["result"]     # "no_estimable_residual_set"
```

With 40 origins the same call answers, and each step's band is built from **its own column**
of the error matrix — never pooled across lead times, because one-step and four-step
uncertainty grow at different rates and pooling them is too wide near and too narrow far, at
the same time.

{% hint style="warning" %}
**The bootstrap is gated on the residual count, not on the number of draws.** Asking for
10,000 resamples from 6 residuals produces a beautifully smooth distribution supported on
those same six values. `interval_bootstrap_flat` refuses a 5-residual column even with 4,000
draws (`no_estimable_residual_set`), exactly as the empirical path does.

**Too few draws is also a refusal, not a narrow band.** Both quantiles are read off the
resample, so the draw count has to clear the same requirement. Measured on 40 residuals at
level 0.95, where 40 residuals are required: `n_draws` of 1, 2 and 39 all come back
`parameter_out_of_range` with no band, and 40 answers. A single draw would otherwise have
produced a **zero-width 95% prediction interval** under a success status, and everything
downstream branches on band width.
{% endhint %}

## The band is reproducible, and says which generator made it

```python
# 40 origins, one lead time: the residual at origin j is j - 20
error = [float(j - 20) for j in range(40)]

band = runtime.execute("forecasting.interval", "interval_bootstrap_flat", [
    error, 40, 1, [100.0], 0.95,
    512, 7, 0,               # n_draws, seed, stream
])["result"]

band["lower"][0]                  # 81.0  — the same number on every run with this seed
band["upper"][0]                  # 119.0
band["has_interval"][0]           # True
band["draws_per_step"]            # 512
band["rng_version"]               # "philox4x64-10/v1"
band["seed"], band["stream"]      # 7, 0 — carried back, so a stored band is reconstructable
```

Draws are a pure function of `(seed, stream, draw index)`, and each lead time owns a disjoint
block of that space — so the band does not depend on how many steps were computed first, or in
what order, or on what else in your process drew a number. Two runs with the same
`(seed, stream, n_draws)` are equal bit for bit.

{% hint style="info" %}
A different seed usually moves the band, but it is not guaranteed to: on a coarse residual
set two seeds can land on the same order statistic. Measured on the 40 integer residuals
above with 512 draws, seeds 7 and 8 both give `[81.0, 119.0]`. Reproducibility is the
property this surface promises; "a different seed gives a different band" is not one.
{% endhint %}

Coverage is a measurable property, so `interval_coverage_flat` measures it rather than
asserting it. A band labelled 95% that covers 62% of held-out actuals is a fact worth having,
and the misses are split by side — a band biased low and a band merely narrow are different
diagnoses.

## A hierarchy that cannot be reconciled is refused, not averaged

Forecast three regions and the country independently and they will not add up. Two
reconciliations are offered, and each keeps a **different** set of numbers fixed:

Reconciliation ids live in their own range, disjoint from the point-forecast ones: `0` and `1`
are point-forecast methods, and a point-forecast id arriving at `reconcile_flat` is
`unknown_method` rather than a silent bottom-up run.

```python
BOTTOM_UP, TOP_DOWN = 200, 201   # method ids come from forecasting.contract

parent_of = [-1, 0, 0]        # node 0 is the root; nodes 1 and 2 are its children
base = [3.0, 4.0, 6.0]        # one cell per node, row-major n_nodes x horizon

r = runtime.execute("forecasting.hierarchy", "reconcile_flat",
                    [base, parent_of, 1, BOTTOM_UP, 0.0])["result"]

r["reconciled"][0]          # 10.0 — the root replaced by its subtree total
r["adjustment_l1"]          # 7.0 — the total distance travelled to reach coherence
r["coherent"]               # True — MEASURED after the fact, not asserted
r["n_incoherent_cells"]     # 0
```

`adjustment_l1` is the price of coherence. A large value is not an error and is not hidden: it
says the base forecasts disagreed badly, which is information about them.

Top-down splits each parent in proportion to the children's own base forecasts — and when
those are all zero under a nonzero parent, there is no split the data justifies:

```python
r = runtime.execute("forecasting.hierarchy", "reconcile_flat",
                    [[10.0, 0.0, 0.0], parent_of, 1, TOP_DOWN, 0.0])["result"]

r["status"]          # 315 — "cannot_reconcile_children_to_parent"
r["has_result"]      # False
r["reconciled"]      # []
r["max_residual"]    # 10.0 — the parent value that could not be distributed
r["worst_node"]      # 0
r["worst_step"]      # 0
```

It specifically does **not** split the parent equally among the children. An equal split
asserts a share the data never suggested, and it would arrive under a success status — which
is worse than the refusal, because a caller stops looking. A method id that is neither of the
two is `unknown_method` with no result, rather than a silent fall back to bottom-up: the two
methods keep different numbers fixed, so a substituted method is a substituted answer.

`hierarchy_coherence_flat` audits a hierarchy you were handed. On the `[3, 4, 6]` base above
it reports `coherent = False` with `max_residual = 7.0` at `worst_node = 0`; on the
reconciled result, `coherent = True` and `max_residual = 0.0`. What that certificate covers is
stated and bounded: for every internal node and step, that the parent equals the sum of **its
own** children within rounding. It does not claim the forecasts are accurate, that the
hierarchy is the right one, or that any value is plausible.

## The horizon is bounded by the data, not only by a ceiling

```python
y = [1.0, 2.0, 3.0, 4.0, 5.0]

r = runtime.execute("forecasting.point", "ets_aan_forecast",
                    [y, 0.5, 0.3, 0.9, 500])["result"]
r["status"]      # 305 — "horizon_unsupported_by_data"
r["values"]      # []

r = runtime.execute("forecasting.point", "ets_aan_forecast",
                    [y, 0.5, 0.3, 0.9, 3])["result"]
r["values"]      # [5.9, 6.71, 7.439]
r["has_trend"]   # True
```

Five observations contain no evidence for step 6, and there is certainly no way to backtest
it. A dimension inside the allocation ceiling can still be tied to nothing in the request, so
the horizon is checked against your series length as well as against the ceiling.

{% hint style="info" %}
**Damped-trend cost grows with the horizon, in proportion to it.** Each step of
`ets_aan_forecast` extends a running damped sum by one multiply-add, so the cost is one pass
over the history plus one step per horizon point. Measured on a 40,000-point series, cost per
horizon step at horizons 4,096 / 8,192 / 16,384 / 32,768 was 111.6 / 48.2 / 29.8 / 13.1 ns —
falling, because the fixed pass over the history dominates — and the damped path stayed a
flat ~3x the undamped one throughout rather than growing against it.

Backtesting multiplies that by the origin count, and every factor of the cost is charged
against a work budget: the seasonal path also carries `period` and the AR path carries
`ar_order`. Exceeding the budget is `work_budget_exceeded` — a refusal you get immediately,
not a request that runs for minutes.
{% endhint %}

## Mostly-zero demand is classified before it is forecast

```python
demand = [0.0, 0.0, 5.0, 0.0, 0.0, 0.0, 3.0, 0.0, 0.0, 8.0, 0.0, 0.0]

p = runtime.execute("forecasting.intermittent", "demand_classify", [demand])["result"]
p["class_name"]      # "intermittent"
p["adi"]             # 3.3333... average interval between nonzero demands
p["cv2"]             # 0.2226... squared coefficient of variation of the sizes
p["zero_fraction"]   # 0.75
p["n_nonzero"]       # 3

f = runtime.execute("forecasting.intermittent", "croston_forecast",
                    [demand, 0.1, 0.1, 0, 3])["result"]   # alphas, variant, horizon
f["forecast"][0]        # 1.6569579288...
f["demand_level"]       # 5.12
f["interval_level"]     # 3.09
f["bias_factor"]        # 1.0 — classical Croston; the variants correct it
```

A history with no positive demand at all has no demand level and no interval to estimate, so
it comes back `no_positive_demand_observed` with an empty forecast rather than a forecast of
zero. Zero is a perfectly ordinary forecast value, which is exactly why it must not double as
"there was nothing to estimate".

## Every refusal names itself

Statuses are one vocabulary for the whole package, and `fc_status_name` turns any of them into
a name — `horizon_unsupported_by_data`, `insufficient_history`, `parameter_out_of_range`,
`seasonal_period_invalid`, `interval_level_out_of_range`, `seed_or_stream_out_of_range`,
`no_estimable_residual_set`, `hierarchy_shape_invalid`,
`cannot_reconcile_children_to_parent`, `negative_value_where_nonnegative_required`,
`no_positive_demand_observed`, `unknown_method`, `work_budget_exceeded` — so a rejection tells
you which of your arguments to look at instead of saying "invalid input".

Absence is always a flag beside a finite number, never a sentinel inside one: `has_forecast`,
`has_level`, `has_trend`, `has_interval[h]`, `has_mase`, `has_scale`, `has_result`,
`has_pooled`. Where a flag is `False` the number beside it is padding and not a claim, and
`fc_method_name` names the method that produced any stored report so a number keeps its
meaning after it leaves your process.

## See also

* [Statistical inference](statistical-inference.md) — p-values with the verdict on their assumptions, and sample sizes that are verified
* [Conformal prediction intervals](ml-conformal.md) — distribution-free intervals with a finite-sample coverage guarantee
* [AR/MA estimation (ARIMA building blocks)](ml-arima.md) — the frozen AR fit these forecasts call
* [Time-series model selection](ml-model-selection.md) — choosing between candidates
* [Declared capabilities](capabilities.md) — what each kernel says about determinism, seeds and cost
* [Runtime library catalog](runtime-library-catalog.md) — every module and function
