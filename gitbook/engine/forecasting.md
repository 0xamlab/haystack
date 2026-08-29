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
| `forecasting.select` | per-series selection or inverse-MAE combination over {SES, Damped, Theta} by mean one-step in-sample error, ties breaking to the simpler model |
| `forecasting.origin_select` | the same three candidates scored by K paired rolling origins instead of one in-sample number, plus a paired-t tournament gate that combines a genuine tie instead of forcing a single winner |
| `forecasting.bagging` | moving-block-bootstrap bagging of one chosen candidate — perturb the series, refit, and average the paths to flatten parameter-estimation variance |
| `forecasting.pool` | the same idea widened to an eight-candidate pool (adds Holt, the M4 Comb, ETS(A,A,A), seasonal-naive and Naive2) and rescored on a last-`horizon` TRAINING holdout instead of in-sample error |
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

## Select and origin_select score the same three candidates two different ways

Four more modules sit on top of `point` and `fitted` rather than beside them: they call the
existing drivers and choose or blend the paths those drivers already produced, adding no new
forecasting arithmetic of their own.

`forecasting.select` picks (or combines) among the same three fitted candidates — SES, the
fitted damped trend, and classical Theta — by the mean absolute **one-step in-sample** error,
t = 1..n-1. On a constant 10-point series all three fit exactly (MAE `0.0` for every
candidate): `select_best_fitted` breaks the tie to the first, SES, and forecasts exactly
`5.0`; `combine_inverse_mae_fitted` splits the weight into exact thirds and also forecasts
exactly `5.0`.

```python
y_const = [5.0] * 10

sb = runtime.execute("forecasting.select", "select_best_fitted", [y_const, 3])["result"]
sb["chosen_method_id"]   # 4 -- FC_METHOD_ETS_ANN (SES), the tie-break winner
sb["maes"]                # [0.0, 0.0, 0.0] -- every candidate fits the constant exactly
sb["values"][0]           # 5.0

cb = runtime.execute("forecasting.select", "combine_inverse_mae_fitted", [y_const, 3])["result"]
cb["weights"]             # [0.333..., 0.333..., 0.333...] -- the exact-fit guard splits evenly
cb["values"][0]           # 5.0
```

On a trending series the ranking flips predictably: Damped's in-sample MAE is smallest,
Theta's is **exactly half** of SES's — an identity, not a coincidence, because on an exact
line the theta-2 line equals the series itself, so the theta-line golden-section fit sees
bit-identical input to the SES fit and its one-step error is structurally half of SES's — and
`select_best_fitted` returns Damped one-hot.

`forecasting.origin_select` replaces that single in-sample number with a K-SAMPLE PAIRED
estimate: K rolling origins inside the training series, every candidate refitted on the SAME
windows and scored on the SAME held-out horizon slice — common random numbers applied to
method selection instead of to a simulation. The schedule is pinned in the suite:

```python
runtime.execute("forecasting.origin_select", "origin_schedule", [13, 6, 8])["result"]
# [6, 7] -- the M4-Yearly minimum shape

runtime.execute("forecasting.origin_select", "origin_schedule", [16, 8, 8])["result"]
# [8] -- the M4-Quarterly minimum: only one origin fits

runtime.execute("forecasting.origin_select", "origin_schedule", [60, 6, 8])["result"]
# [33, 36, 39, 42, 45, 48, 51, 54] -- 8 origins, spaced 3 apart, from the recent end
```

`crn_origin_select` selects the smallest mean paired MAE, same tie-break order as `select`.
`tournament_gated_select` adds a statistical gate on top: the apparent best is handed to
`strategy.tournament`'s paired-t core against every other survivor at significance `alpha`;
anything not significantly beaten stays in a tied set that gets combined by inverse
mean-MAE weight, and a refused or undecided comparison counts as a tie, never a win. On a
24-point constant series the two drivers disagree on purpose: `crn_origin_select` breaks the
exact tie to SES one-hot, while `tournament_gated_select` reads the floating-point-residue
differences between three exact fits as a genuine three-way tie and combines all three — still
forecasting exactly `5.0` — because a mean per-origin difference below a floor scaled by the
two means being compared (`1e-12 * (1 + mean_a + mean_b)`) is read as numerical residue before
any test is even consulted. With fewer than two origins (a short Yearly series) no test exists
at all, so every surviving candidate ties by construction: the least evidence yields the most
cautious answer.

The gate is sensitive to `alpha` at the exact reported p-value, not just qualitatively: on a
wiggly, mildly-trending 60-point series, setting `alpha` just below the smallest per-candidate
p ties everything into the full three-way combination; setting it just above the largest flips
to a lone selection. And the whole apparatus is provably leakage-free: fed a pure upward trend
(whose rolling origins all favour Damped) alongside a hand-built continuation — a flat line at
the last observed level, which actually rewards SES, and is never passed to the kernel —
`crn_origin_select` still returns Damped: a function of the training series alone, it
structurally cannot see what the continuation rewards.

## Bagging refits one candidate on perturbed histories, not a different model

`forecasting.bagging` implements moving-block-bootstrap (MBB) bagging on this candidate pool:
decompose the series into a shrinking-window centered moving-average trend plus a remainder,
draw `n_boot` MBB resamples of the remainder (blocks of `block_len` consecutive points drawn
with replacement, so the resample keeps the local autocorrelation an i.i.d. draw would
destroy), recompose `n_boot` simulated series, refit ONE named candidate (0 = SES, 1 = Damped,
2 = Theta — `forecasting.select`'s own fits and tie-break order) on each, and average the
resulting forecast paths together with the fit on the ORIGINAL series. A replicate whose
recomposition is non-finite or whose refit refuses is skipped and counted in `n_boot_refused`,
never zero-filled; if the fit on the original series itself refuses, the whole call refuses
(`every_candidate_undefined`) — an ensemble with no center is not a bagged version of anything.
Draws are keyed by `(master_seed, series_id, replicate_id, stream, block index)` through
`determinism.counter_rng` (Philox4x64-10), so two calls with identical arguments are
bit-identical, and `BaggedForecast.rng_version` names the generator for a stored ensemble.

Two identities the suite pins with `==`, not a tolerance:

```python
y = [2.0 + 3.0 * t for t in range(20)]   # a perfect line

trend = runtime.execute("forecasting.bagging", "shrinking_ma_trend", [y, 7])["result"]
trend["values"] == y                     # True -- a centered average of a line is the line

bag = runtime.execute("forecasting.bagging", "bagged_candidate_forecast",
                      [y, 4, 1, 10, 5, 7, 7, 11])["result"]   # candidate 1 = Damped
# the remainder is identically zero at every point, so every recomposed replicate IS the
# original series and the ensemble equals the single fit, bit for bit -- even with block_len
# (5) well under n (20)
```

`block_len == n` is the other pinned identity: a single admissible block start means the
resample IS the remainder, so the bagged forecast equals the single fit for any `n_boot`. Away
from these degenerate cases — a genuinely wiggly remainder — the ensemble measurably differs
from the single fit and moves with `block_len`, `trend_window` and the seed, while staying
bit-reproducible for a fixed set of arguments. The decomposition states its own honest edge
case: the moving-average window shrinks symmetrically at the edges (radius
`min(trend_window // 2, i, n-1-i)`) rather than being zero-padded, so the two endpoints have an
exactly-zero remainder and understate edge variance rather than extrapolating the record to
hide it. This module expects a deseasonalised or non-seasonal series; a remainder taken around
a moving average shorter than the season would carry the season into every block draw.

## A wider pool, scored on a training holdout instead of in-sample error

`forecasting.pool` exists because of one measured ceiling: on the full M4 corpus, the
test-window oracle over the three-candidate pool above scores 0.775 total OWA while every
honest in-sample selection criterion over that same pool lands around 0.874 — and the oracle
over an eight-candidate pool drops to 0.671. The pool, not the selection criterion, is where
the remaining headroom lives, so `pool` widens the candidate set to eight (adding Holt, the
official M4 "Comb" of SES + Holt + Damped, ETS(A,A,A), seasonal-naive and Naive2) and moves the
criterion from in-sample one-step error to a **last-`horizon` TRAINING holdout**: every
candidate is fitted on the first `n - horizon` observations, scored against the held-back tail
of the TRAINING series (never a test window — the function signature has no such argument),
then refitted on the full series for the shipped forecast.

That criterion change can flip the answer, and the flip is the point. On a 36-point series
built from a 30-point upward trend followed by a 6-point plateau, the in-sample criterion
(dominated by the 30-point trend body) picks Damped; the training-holdout pool sees the
plateau and picks Naive2 instead — and on a constructed continuation of the plateau (never an
input to either call), the holdout pick's error comes in more than 5x smaller (measured about
31x in the suite):

```python
y = ([10.0 + 2.0 * t for t in range(30)]
     + [68.2, 67.9, 68.1, 67.8, 68.0, 68.1])          # trend body, then a plateau

report = runtime.execute("forecasting.pool", "pool_holdout_report", [y, y, 1, 6])["result"]
report["n_train"], report["n_fit"]     # 36, 30 -- u = n - horizon, the truncated fit size

pool_fc = runtime.execute("forecasting.pool", "pool_holdout_forecast",
                          [y, y, 1, 6, 0, 0])["result"]     # mode 0 = POOL_MODE_SELECT
pool_fc["chosen_candidate"]            # 7 -- naive2

insample = runtime.execute("forecasting.select", "select_best_fitted", [y, 6])["result"]
insample["chosen_method_id"]           # 5 -- FC_METHOD_ETS_AAN (Damped)
```

The fit-refit split shows up in the report's own numbers: naive2's holdout row is exactly
`68.0` at every step (the last value of the truncated 30-point window, `y[29]`), while its
full row is exactly `68.1` (the last value of the whole 36-point series, `y[35]`) — two
different numbers only a genuine fit-on-prefix, refit-on-full implementation produces. On this
non-seasonal call (`period = 1`), the two seasonal-only candidates — ETS(A,A,A) and
seasonal-naive — are excluded as `seasonal_period_invalid`, with `holdout_mae = -1.0`, never a
silent zero-weight inclusion.

The no-leakage discipline is checked the same way `origin_select`'s is: on a pure 13-point
trend (the M4-Yearly minimum shape, `u = 7` training points against `horizon = 6`), a test
window that collapsed to zero would reward SES (holdout MAE > 10) or Naive2 (> 10) — but
`pool` has no test-window argument through which such a future could arrive, and the training
data supports exactly one answer: Holt, whose holdout MAE on the trend tail is exactly `0.0`,
taking the ENTIRE inverse-MAE weight when `pool_holdout_forecast` is asked to blend rather than
select (`weights[HOLT] == 1.0`, reported as that one candidate rather than a one-member
"combination").

`pool_blend_flat` is the arithmetic split out on its own — four modes (hard select,
inverse-MAE, equal-weight mean, per-step median) over an already-computed report, so a caller
comparing modes pays for one report and many blends. Ties still break to the lower (simpler)
index; an exact holdout fit still takes the whole weight, split evenly among however many
candidates hit it exactly (on a seasonal series with an exactly reproducible pattern, five of
the eight candidates land at MAE `0.0` and split the inverse-MAE weight into exact fifths,
while the three whose fit is merely Nelder-Mead-close, not bit-exact, weigh `0.0`); and a pool
of one survivor is reported as that candidate, whatever mode was asked for, because a mean of
one thing is not a combination. `pool_candidate_name` and `pool_mode_name` turn the pool-local
indices and blend modes into names (`"naive2"`, `"inverse_mae"`, ...) — loud
(`"unknown_candidate"` / `"unknown_mode"`) on an out-of-range index rather than blank.

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
