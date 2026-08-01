"""
forecasting.backtest — rolling-origin evaluation and honest error measures. Zero Python.

Why this is the most valuable module in the package
--------------------------------------------------
A forecast scored against the data it was fitted to is not evidence, and until now nothing in
the tree distinguished the two cases. `series.forecast_accuracy(actual, predicted)` takes both
arrays from the caller: it will happily score `holt_linear(y, a, b)` against `y` and return an
excellent MAE for a model that has seen every point it is being tested on. No status said so,
because the function cannot know.

A rolling-origin backtest closes that by construction. At each origin the training window ends
at index `t`, the forecaster sees ONLY `y[.. t)`, and it is scored against `y[t .. t+horizon)` —
points that did not exist when the model was fitted. Repeating that over many origins gives a
distribution of out-of-sample errors instead of one number.

Two window policies, and they answer different questions
--------------------------------------------------------
`expanding = True` trains on `y[0 .. t)`: every origin uses all history, so the training set
grows and later origins are fitted on more data. That measures the method as it would actually
be operated.

`expanding = False` trains on `y[t - min_train .. t)`: a SLIDING window of constant length, so
every origin is fitted on the same amount of data. That is the one to use when comparing
methods, because with an expanding window a difference between origins confounds "the method
got better" with "the training set got bigger".

PER-ORIGIN ERRORS ARE RETURNED, NOT ONLY THEIR MEAN
---------------------------------------------------
`origin_mae` and `origin_rmse` come back alongside the pooled figures, plus `worst_origin` and
`worst_origin_mae`. A mean over origins hides exactly the thing a caller needs: a method that
is excellent on the first eighteen origins and catastrophic on the last two has a good average
and is unusable, and the last two are the ones that resemble tomorrow. The full `forecast`,
`actual` and `error` matrices come back too (row-major, one row per origin), so any other
statistic can be computed without re-running anything.

Requested, run and refused are three different numbers
------------------------------------------------------
`n_origins_requested` is what the configuration `(n_obs, horizon, min_train, step)` admits —
pure arithmetic, and `backtest_origin_count` computes it on its own so a caller can size a run
before making it. `n_origins_run` is how many produced a complete `horizon`-step forecast.
`n_origins_refused` is the difference, and it is not hypothetical: a forecaster declines an
origin whose window cannot support it — `ets_aaa_forecast` inside its first complete seasonal
cycle, `croston_forecast` in a window with no positive demand, `ar_forecast_checked` with
`ar_order > len(train) - 1`.

Reporting only the mean over the survivors would answer a question nobody asked. Worse, if
EVERY origin is refused there is no error at all, and that is FC_ERR_ALL_UNDEFINED with empty
matrices — deliberately a different status from FC_ERR_NO_ORIGINS, which means the
configuration itself admitted no origin. "Your windows are too short" and "your method
refused every window" need different fixes.

The error measures, and the two that are undefined more often than they look
---------------------------------------------------------------------------
`forecast_errors_flat` reports MAE and RMSE (always defined for at least one point), MAPE,
sMAPE and MASE, each with its own presence flag AND its own count of undefined points.

  * MAPE divides by the actual. At an actual of EXACTLY ZERO the ratio does not exist, so that
    point is excluded and COUNTED. The count is the whole point: `mape = 4.2` over 100 points
    and `mape = 4.2` over 6 points with 94 undefined are completely different claims, and
    without `n_undefined_mape` they are the same number.

    The threshold is exact zero, not `|a| < 1e-15`. A tiny nonzero actual gives an enormous
    but genuinely DEFINED ratio, and screening it out with a small constant is a hidden
    absolute tolerance at a scale the caller never chose — rule 4b's third spelling. MAPE on
    near-zero actuals really is enormous; that is why MASE exists, not something to smooth over.

    The frozen `series.forecast_accuracy` does it the other way: it skips `|a| <= 1e-15` and
    then divides by the FULL length, so its MAPE shrinks as more points become inapplicable.
    The relation is exact and the suite asserts it —
    `mape * n_defined_mape == frozen_mape * n_points` whenever no actual lies in (0, 1e-15].

  * sMAPE is undefined when `|a| + |f|` is zero (a zero forecast for a zero actual), counted
    separately because it is a different set of points from MAPE's.

  * MASE divides the MAE by the in-sample seasonal-naive MAE of the TRAINING series,
    `mean |y_t - y_{t-period}|`. That denominator does not exist without a training series
    longer than `period`, and it is ZERO for a training series that is exactly periodic — a
    perfectly ordinary input for which MASE is a division by zero and therefore has no value.
    `has_scale` and `has_mase` are separate flags so "no denominator" and "a denominator of
    zero" are distinguishable.

MAE and RMSE are accumulated in ascending index order and divided by `Float64(n)`, exactly as
the frozen kernel does, so they are BIT-IDENTICAL to `series.forecast_accuracy`'s first and
third outputs. The suite asserts equality rather than closeness, because a tolerance there
would hide a real mis-accumulation.

Work is charged, not just memory
--------------------------------
`n_origins * horizon` cells are bounded by `MAX_FC_CELLS` and the per-origin refit cost is
charged separately against `FC_MAX_BACKTEST_WORK`. Every factor that multiplies into the cost
is charged: the seasonal path is O(n * period) per origin and the AR path is
O(n * ar_order + ar_order^2 + horizon * ar_order), so `period` and `ar_order` enter the budget
rather than being bounded only by their own ceilings. A budget that counts one factor of a
product is not a budget — a sibling package hung because `n_machines` was charged against
allocation and never against work, and from the caller's side a hang and the uncatchable abort
are the same outcome. Every charge is formed by DIVISION (`fc_work_fits`), never by a
multiplication that could wrap.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_forecasting_backtest.mojo
benchmark: benchmarks/mojo_benchmarks/bench_forecasting.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, sqrt

from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_DIMENSION_TOO_LARGE,
    FC_ERR_EMPTY_SERIES,
    FC_ERR_INSUFFICIENT_HISTORY,
    FC_ERR_LENGTH_MISMATCH,
    FC_ERR_METHOD,
    FC_ERR_NON_FINITE,
    FC_ERR_NO_ORIGINS,
    FC_ERR_PARAM_RANGE,
    FC_ERR_WORK_BUDGET,
    FC_MAX_BACKTEST_WORK,
    FC_METHOD_AR,
    FC_METHOD_CROSTON,
    FC_METHOD_ETS_AAA,
    FC_METHOD_ETS_AAN,
    FC_METHOD_ETS_ANN,
    FC_METHOD_MAX,
    FC_METHOD_THETA,
    FC_METHOD_THETA_DRIFT,
    FC_OK,
    MAX_FC_CELLS,
    MAX_FC_SERIES,
    fc_all_finite,
    fc_cells_fit,
    fc_finite,
    fc_horizon_defect,
    fc_series_defect,
    fc_status_name,
    fc_work_fits,
)
from forecasting.intermittent import FC_CROSTON_CLASSIC, croston_forecast
from forecasting.point import (
    PointForecast,
    ar_forecast_checked,
    baseline_forecast,
    ets_aaa_forecast,
    ets_aan_forecast,
    ets_ann_forecast,
    theta_drift_forecast,
    theta_forecast,
)


@fieldwise_init
struct BacktestReport(Copyable, Movable):
    """A rolling-origin backtest: the whole error matrix, per-origin summaries, and the census.

    LAYOUT. `origin_index[j]` is the EXCLUSIVE end of origin `j`'s training window, so that
    origin was fitted on `y[.. origin_index[j])` (expanding) or
    `y[origin_index[j] - min_train .. origin_index[j])` (sliding) and scored against
    `y[origin_index[j] .. origin_index[j] + horizon)`. `forecast`, `actual` and `error` are
    row-major `n_origins_run x horizon`, so cell `(j, h)` is at `j * horizon + h` and
    `error = actual - forecast`.

    THE THREE COUNTS. `n_origins_requested` is what the configuration admits,
    `n_origins_run` how many produced a complete forecast, `n_origins_refused` the difference.
    They are separate fields because a mean over the survivors is a different statistic from
    the one requested — see the module docstring.

    PER-ORIGIN BEFORE POOLED. `origin_mae[j]` and `origin_rmse[j]` are that origin's own
    errors over its `horizon` steps. `mae` and `rmse` are POOLED over every cell, which is the
    definition that weights every out-of-sample point equally. Every origin that ran
    contributed exactly `horizon` cells, so the pooled MAE and the mean of `origin_mae` are the
    same quantity up to floating-point association — but they are accumulated differently, and
    only the pooled figure stays correct if a future variant ever admits a short origin.
    `worst_origin` is the index INTO `origin_index` of the largest `origin_mae`, lowest index on
    a tie so the report does not depend on scan order.

    `has_pooled` is the authority for `mae` and `rmse`. On any refusal every list is empty,
    every count is 0 and `has_pooled` is False — no partial matrix, no zero-filled rows.
    """

    var status: Int
    var method_id: Int
    var horizon: Int
    var n_obs: Int
    var min_train: Int
    var step: Int
    var expanding: Bool
    var n_origins_requested: Int
    var n_origins_run: Int
    var n_origins_refused: Int
    var n_cells: Int
    var origin_index: List[Int]
    var forecast: List[Float64]
    var actual: List[Float64]
    var error: List[Float64]
    var origin_mae: List[Float64]
    var origin_rmse: List[Float64]
    var mae: Float64
    var rmse: Float64
    var has_pooled: Bool
    var worst_origin: Int
    var worst_origin_mae: Float64
    var status_name: String


@fieldwise_init
struct ErrorReport(Copyable, Movable):
    """Five error measures, each with its own presence flag AND its own undefined count.

    A measure that is inapplicable at some points is reported over the points where it IS
    defined, with the number of points it skipped. `mape = 4.2` over 100 defined points and
    `mape = 4.2` over 6 defined points with 94 undefined are different claims; only the count
    distinguishes them, which is why substituting 0.0 or silently skipping is not an option.

    `mae` and `rmse` are bit-identical to `series.forecast_accuracy`'s first and third outputs.
    `mape` is NOT identical to its second, by design: see the module docstring for the exact
    relation, which the suite asserts.

    `scale_denominator` is the in-sample seasonal-naive MAE of the training series and is
    reported even when it is 0.0, because "the denominator is zero" (a periodic training
    series) and "there is no denominator" (a training series shorter than `period + 1`) are
    different facts. `has_scale` marks the second; `has_mase` requires the first to be
    strictly positive as well.
    """

    var status: Int
    var n_points: Int
    var period: Int
    var mae: Float64
    var has_mae: Bool
    var rmse: Float64
    var has_rmse: Bool
    var mape: Float64
    var has_mape: Bool
    var n_defined_mape: Int
    var n_undefined_mape: Int
    var smape: Float64
    var has_smape: Bool
    var n_defined_smape: Int
    var n_undefined_smape: Int
    var mase: Float64
    var has_mase: Bool
    var scale_denominator: Float64
    var has_scale: Bool
    var status_name: String


fn _no_backtest(
    status: Int, method_id: Int, horizon: Int, n_obs: Int, min_train: Int,
    step: Int, expanding: Bool, requested: Int, refused: Int
) -> BacktestReport:
    """A refusal: empty matrices, no pooled error, but the census kept where it is known."""
    return BacktestReport(
        status, method_id, horizon, n_obs, min_train, step, expanding,
        requested, 0, refused, 0,
        List[Int](), List[Float64](), List[Float64](), List[Float64](),
        List[Float64](), List[Float64](),
        0.0, 0.0, False, -1, 0.0, fc_status_name(status),
    )


fn _no_errors(status: Int, n_points: Int, period: Int) -> ErrorReport:
    """A refusal: every measure absent, every count zero."""
    return ErrorReport(
        status, n_points, period, 0.0, False, 0.0, False, 0.0, False, 0, 0,
        0.0, False, 0, 0, 0.0, False, 0.0, False, fc_status_name(status),
    )


fn backtest_origin_count(
    n_obs: Int, horizon: Int, min_train: Int, step: Int
) -> Int:
    """How many rolling origins a configuration admits. Pure arithmetic, no series needed.

    Origins are `t = min_train, min_train + step, ...` while `t + horizon <= n_obs`, so the
    count is `(n_obs - horizon - min_train) / step + 1` when that is non-negative.

    Returns 0 for a valid configuration with no room for a single origin, and -1 when the
    configuration itself is INVALID (a non-positive `n_obs`, `horizon`, `min_train` or `step`,
    or a dimension past `MAX_FC_SERIES`). Those are two different answers and -1 is impossible
    for a real count, so a caller that ignores the distinction gets a loud wrong number rather
    than a quiet "no origins".

    Exposed separately from `backtest_flat` so a caller can size a run before making one — and
    so the arithmetic has its own known-value test independent of any forecasting.

    @capability backtest_origin_count
    complexity: O(1)
    counts: none
    @endcapability
    """
    if n_obs <= 0 or horizon <= 0 or min_train <= 0 or step <= 0:
        return -1
    if n_obs > MAX_FC_SERIES or min_train > MAX_FC_SERIES or step > MAX_FC_SERIES:
        return -1
    if horizon > MAX_FC_SERIES:
        return -1
    var room = n_obs - horizon - min_train
    if room < 0:
        return 0
    return room // step + 1


fn _forecast_by_method(
    train: List[Float64], method_id: Int, horizon: Int, period: Int,
    ar_order: Int, alpha: Float64, beta: Float64, phi: Float64, theta: Float64
) -> PointForecast:
    """THE package's one method_id -> forecast dispatch. Private, and that is deliberate.

    It returns `point.PointForecast`, a struct owned by ANOTHER module, and
    `apps/runtime/mojo_inventory.py` resolves struct marshalling one file at a time — so a
    PUBLIC function returning it from here would be silently dropped from the runtime contract
    and from dispatch, with no error anywhere. Keeping it private makes that a non-issue: a
    caller who wants one forecast calls the named driver in `forecasting.point` or
    `forecasting.intermittent` directly, and this exists so `backtest_flat` has exactly one
    place where a method id becomes a forecast.

    Croston returns an `IntermittentForecast`, which is repacked here rather than in
    `intermittent` for the same struct-ownership reason. `level` carries its rate; `trend` and
    `scale` are absent because a rate has neither.

    An unknown id returns a refusal with FC_ERR_METHOD and NO values. It does not fall back to
    naive: a mistyped id that returns a plausible forecast under a success status is the
    `func_id` defect this tree has already paid for once.
    """
    if method_id == FC_METHOD_ETS_ANN:
        return ets_ann_forecast(train, alpha, horizon)
    if method_id == FC_METHOD_ETS_AAN:
        return ets_aan_forecast(train, alpha, beta, phi, horizon)
    if method_id == FC_METHOD_ETS_AAA:
        return ets_aaa_forecast(train, alpha, beta, phi, period, horizon)
    if method_id == FC_METHOD_THETA:
        return theta_forecast(train, theta, alpha, horizon)
    if method_id == FC_METHOD_THETA_DRIFT:
        return theta_drift_forecast(train, alpha, horizon)
    if method_id == FC_METHOD_AR:
        return ar_forecast_checked(train, ar_order, horizon)
    if method_id == FC_METHOD_CROSTON:
        var rate = croston_forecast(
            train, alpha, beta, FC_CROSTON_CLASSIC, horizon
        )
        if rate.status != FC_OK or not rate.has_forecast:
            return PointForecast(
                rate.status, FC_METHOD_CROSTON, horizon, len(train),
                List[Float64](), False, 0.0, False, 0.0, False, 0.0, False, 0,
                rate.status_name,
            )
        return PointForecast(
            FC_OK, FC_METHOD_CROSTON, horizon, len(train), rate.forecast.copy(),
            True, rate.forecast[0], True, 0.0, False, 0.0, False, 2,
            fc_status_name(FC_OK),
        )
    # The four frozen baselines share one guarded entry; `baseline_forecast` returns
    # FC_ERR_METHOD itself for anything outside them, so there is no default branch here.
    return baseline_forecast(train, method_id, horizon, period)


fn _reported(value: Float64, present: Bool) -> Float64:
    """The value when it is present, and 0.0 when it is not -- never a raw non-finite.

    Every metric here is computed FIRST and flag-checked SECOND (`mae = abs_sum / n` then
    `has_mae = fc_finite(mae)`), so an overflowing sum leaves a nan or +/-inf sitting in the value
    slot with its `has_*` flag correctly False. The flag is the answer to "is there a value"; the
    slot should not simultaneously carry something that cannot be represented.

    It matters beyond tidiness: `String(nan)` serializes to the bare token `nan`, which is not valid
    JSON, so ONE absent metric made the whole `ErrorReport` frame unparseable and took the worker
    process with it. The serializer now refuses a non-finite instead of emitting it, which turns
    that into a typed error -- but the report would still be refused wholesale for a field the
    caller was already told to ignore. Zeroing the absent slot keeps the other four metrics
    readable.

    0.0 is safe here precisely BECAUSE the flag is authoritative: a reader that consults `has_mae`
    cannot mistake it for a measurement, and one that ignores the flag was already wrong.
    """
    return value if present else 0.0


fn _per_origin_cost(
    n_obs: Int, horizon: Int, method_id: Int, period: Int, ar_order: Int
) -> Int:
    """Elementary operations one origin costs, or -1 when a FACTOR alone blows the budget.

    Charging `n_origins * (n_obs + horizon)` would be a budget that counts one factor of a
    product. The seasonal path calls `moving_average_trend`, which is O(n * period); the AR
    path is O(n * ar_order + ar_order^2 + horizon * ar_order). Both extra factors are charged
    here, and each intermediate product is checked with `fc_work_fits` (a DIVISION) before it
    is formed, so no charge can wrap into a small number and quietly stop being a budget.
    """
    if method_id == FC_METHOD_ETS_AAA:
        if not fc_work_fits(n_obs, period, FC_MAX_BACKTEST_WORK):
            return -1
        return n_obs * period + horizon
    if method_id == FC_METHOD_AR:
        if not fc_work_fits(n_obs, ar_order, FC_MAX_BACKTEST_WORK):
            return -1
        if not fc_work_fits(ar_order, ar_order, FC_MAX_BACKTEST_WORK):
            return -1
        if not fc_work_fits(horizon, ar_order, FC_MAX_BACKTEST_WORK):
            return -1
        return n_obs * ar_order + ar_order * ar_order + horizon * ar_order
    return n_obs + horizon


fn backtest_flat(
    y: List[Float64], method_id: Int, horizon: Int, min_train: Int,
    step: Int, expanding: Bool, period: Int, ar_order: Int,
    alpha: Float64, beta: Float64, phi: Float64, theta: Float64
) -> BacktestReport:
    """Rolling-origin backtest of one method over expanding or sliding training windows.

    Each origin's forecaster sees ONLY `y[.. t)` and is scored against `y[t .. t+horizon)`, so
    every error in the report is out of sample. See `BacktestReport` for the layout and the
    module docstring for the two window policies and the three origin counts.

    `alpha`, `beta`, `phi`, `theta`, `period` and `ar_order` are read only by the methods that
    need them (`fc_method_name` names the ids). For FC_METHOD_CROSTON, `alpha` smooths the
    demand sizes and `beta` the intervals.

    `min_train < horizon` is refused up front with FC_ERR_INSUFFICIENT_HISTORY: it is the
    per-origin form of the rule `fc_horizon_defect` applies to the whole series — a window
    cannot support a forecast longer than itself — and without the up-front check it would
    surface as every origin being refused, which is a much worse error message for the same
    defect.

    @capability backtest_flat
    complexity: O(n_origins * (n_obs + horizon)) for the non-seasonal, non-AR methods
    counts:
    - dim horizon [kernel_validated]
    - dim min_train [kernel_validated]
    - dim step [kernel_validated]
    - dim period [kernel_validated]
    - dim ar_order [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_backtest(
            defect, method_id, horizon, n, min_train, step, expanding, 0, 0
        )
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_backtest(
            defect, method_id, horizon, n, min_train, step, expanding, 0, 0
        )
    if method_id < 0 or method_id > FC_METHOD_MAX:
        return _no_backtest(
            FC_ERR_METHOD, method_id, horizon, n, min_train, step, expanding, 0, 0
        )
    if min_train <= 0 or step <= 0:
        return _no_backtest(
            FC_ERR_PARAM_RANGE, method_id, horizon, n, min_train, step, expanding, 0, 0
        )
    if min_train > n or step > n:
        return _no_backtest(
            FC_ERR_INSUFFICIENT_HISTORY, method_id, horizon, n, min_train, step,
            expanding, 0, 0,
        )
    if min_train < horizon:
        return _no_backtest(
            FC_ERR_INSUFFICIENT_HISTORY, method_id, horizon, n, min_train, step,
            expanding, 0, 0,
        )

    var requested = backtest_origin_count(n, horizon, min_train, step)
    if requested < 0:
        return _no_backtest(
            FC_ERR_PARAM_RANGE, method_id, horizon, n, min_train, step, expanding, 0, 0
        )
    if requested == 0:
        return _no_backtest(
            FC_ERR_NO_ORIGINS, method_id, horizon, n, min_train, step, expanding, 0, 0
        )
    if not fc_work_fits(requested, horizon, MAX_FC_CELLS):
        return _no_backtest(
            FC_ERR_DIMENSION_TOO_LARGE, method_id, horizon, n, min_train, step,
            expanding, requested, 0,
        )
    var cost = _per_origin_cost(n, horizon, method_id, period, ar_order)
    if cost < 0 or not fc_work_fits(requested, cost, FC_MAX_BACKTEST_WORK):
        return _no_backtest(
            FC_ERR_WORK_BUDGET, method_id, horizon, n, min_train, step,
            expanding, requested, 0,
        )

    var origin_index = List[Int]()
    var forecasts = List[Float64]()
    var actuals = List[Float64]()
    var errors = List[Float64]()
    var origin_mae = List[Float64]()
    var origin_rmse = List[Float64]()
    var refused = 0
    var pooled_abs: Float64 = 0.0
    var pooled_sq: Float64 = 0.0

    var t = min_train
    while t + horizon <= n:
        var train = List[Float64]()
        var start = 0 if expanding else t - min_train
        for i in range(start, t):
            train.append(y[i])
        var fit = _forecast_by_method(
            train, method_id, horizon, period, ar_order, alpha, beta, phi, theta
        )
        if fit.status != FC_OK or not fit.has_forecast or len(fit.values) != horizon:
            refused += 1
            t += step
            continue
        var abs_sum: Float64 = 0.0
        var sq_sum: Float64 = 0.0
        for h in range(horizon):
            var predicted = fit.values[h]
            var observed = y[t + h]
            var err = observed - predicted
            forecasts.append(predicted)
            actuals.append(observed)
            errors.append(err)
            var magnitude = fabs(err)
            abs_sum += magnitude
            sq_sum += err * err
            pooled_abs += magnitude
            pooled_sq += err * err
        origin_index.append(t)
        origin_mae.append(abs_sum / Float64(horizon))
        origin_rmse.append(sqrt(sq_sum / Float64(horizon)))
        t += step

    var run = len(origin_index)
    if run == 0:
        return _no_backtest(
            FC_ERR_ALL_UNDEFINED, method_id, horizon, n, min_train, step,
            expanding, requested, refused,
        )
    var cells = run * horizon
    var pooled_mae = pooled_abs / Float64(cells)
    var pooled_rmse = sqrt(pooled_sq / Float64(cells))
    if not fc_finite(pooled_mae) or not fc_finite(pooled_rmse):
        return _no_backtest(
            FC_ERR_NON_FINITE, method_id, horizon, n, min_train, step,
            expanding, requested, refused,
        )

    # Lowest index wins a tie, so the report does not depend on scan order.
    var worst = 0
    for j in range(1, run):
        if origin_mae[j] > origin_mae[worst]:
            worst = j
    var worst_value = origin_mae[worst]

    return BacktestReport(
        FC_OK, method_id, horizon, n, min_train, step, expanding,
        requested, run, refused, cells,
        origin_index^, forecasts^, actuals^, errors^, origin_mae^, origin_rmse^,
        pooled_mae, pooled_rmse, True, worst, worst_value, fc_status_name(FC_OK),
    )


fn backtest_residuals_at_step(
    error: List[Float64], n_origins: Int, horizon: Int, step_index: Int
) -> List[Float64]:
    """Column `step_index` of a row-major `n_origins x horizon` error matrix.

    The residual sample a prediction interval for horizon step `step_index + 1` must be built
    from: one value per origin, all at the SAME lead time. Pooling lead times would mix
    one-step and h-step uncertainty, which grow at different rates, and produce a band that is
    too wide at the near end and too narrow at the far end.

    Returns EMPTY for any shape defect — a wrong `n_origins`, a `step_index` outside
    `[0, horizon)`, or a length that is not exactly `n_origins * horizon`. Empty rather than a
    partial column: a residual sample missing an unknown number of its members would produce a
    quantile that is wrong by an unknown amount.

    The shape test goes through `contract.fc_cells_fit`, which divides. `n_origins * horizon ==
    len(error)` is a wrapping multiply, so it is not a bound: `3 * 6148914691236517206 == 2` is
    how a sibling walked past exactly this guard and aborted the worker.

    @capability backtest_residuals_at_step
    complexity: O(n_origins)
    counts:
    - n_origins * horizon == len(error) [kernel_validated]
    - dim step_index [kernel_validated]
    @endcapability
    """
    var out = List[Float64]()
    if not fc_cells_fit(n_origins, horizon, len(error)):
        return out^
    if step_index < 0 or step_index >= horizon:
        return out^
    for j in range(n_origins):
        out.append(error[j * horizon + step_index])
    return out^


fn forecast_errors_flat(
    actual: List[Float64], forecast: List[Float64],
    train: List[Float64], period: Int
) -> ErrorReport:
    """MAE, RMSE, MAPE, sMAPE and MASE, each with a presence flag and an undefined count.

    `train` and `period` are used ONLY for the MASE denominator (the in-sample seasonal-naive
    MAE, `mean |y_t - y_{t-period}|`); pass an empty `train` to get everything except MASE. A
    `period` of 1 gives the non-seasonal MASE.

    See the module docstring for why MAPE's undefined set is `actual == 0.0` exactly rather
    than `|actual| < 1e-15`, and for the exact relation to the frozen
    `series.forecast_accuracy` that the suite asserts.

    Refuses only when there is nothing to measure: unequal lengths (FC_ERR_LENGTH_MISMATCH),
    an empty pair (FC_ERR_EMPTY_SERIES), or a non-finite input (FC_ERR_NON_FINITE). Every
    other shortfall is an ABSENT measure with a count, never a failed report — withholding a
    perfectly good MAE because MAPE was inapplicable would answer a question nobody asked.

    @capability forecast_errors_flat
    complexity: O(n + len(train))
    counts:
    - dim period [kernel_validated]
    @endcapability
    """
    var n = len(actual)
    if n != len(forecast):
        return _no_errors(FC_ERR_LENGTH_MISMATCH, n, period)
    if n == 0:
        return _no_errors(FC_ERR_EMPTY_SERIES, 0, period)
    if n > MAX_FC_SERIES or len(train) > MAX_FC_SERIES:
        return _no_errors(FC_ERR_DIMENSION_TOO_LARGE, n, period)
    if not fc_all_finite(actual) or not fc_all_finite(forecast):
        return _no_errors(FC_ERR_NON_FINITE, n, period)
    if not fc_all_finite(train):
        return _no_errors(FC_ERR_NON_FINITE, n, period)

    # Ascending order and a divide by Float64(n), matching `series.forecast_accuracy` exactly,
    # so MAE and RMSE are bit-identical to it rather than merely close.
    var abs_sum: Float64 = 0.0
    var sq_sum: Float64 = 0.0
    var pct_sum: Float64 = 0.0
    var sym_sum: Float64 = 0.0
    var defined_pct = 0
    var defined_sym = 0
    for i in range(n):
        var err = actual[i] - forecast[i]
        var magnitude = fabs(err)
        abs_sum += magnitude
        sq_sum += err * err
        if actual[i] != 0.0:
            pct_sum += magnitude / fabs(actual[i])
            defined_pct += 1
        var denom = fabs(actual[i]) + fabs(forecast[i])
        if denom != 0.0:
            sym_sum += 2.0 * magnitude / denom
            defined_sym += 1

    var mae = abs_sum / Float64(n)
    var rmse = sqrt(sq_sum / Float64(n))
    var has_mae = fc_finite(mae)
    var has_rmse = fc_finite(rmse)

    var mape: Float64 = 0.0
    var has_mape = False
    if defined_pct > 0:
        mape = pct_sum / Float64(defined_pct) * 100.0
        has_mape = fc_finite(mape)

    var smape: Float64 = 0.0
    var has_smape = False
    if defined_sym > 0:
        smape = sym_sum / Float64(defined_sym) * 100.0
        has_smape = fc_finite(smape)

    # MASE denominator: the in-sample seasonal-naive MAE of the TRAINING series.
    var scale: Float64 = 0.0
    var has_scale = False
    if period >= 1 and len(train) > period:
        var diff_sum: Float64 = 0.0
        var count = 0
        for i in range(period, len(train)):
            diff_sum += fabs(train[i] - train[i - period])
            count += 1
        if count > 0:
            scale = diff_sum / Float64(count)
            has_scale = fc_finite(scale)

    var mase: Float64 = 0.0
    var has_mase = False
    if has_scale and scale > 0.0 and has_mae:
        mase = mae / scale
        has_mase = fc_finite(mase)

    return ErrorReport(
        FC_OK, n, period,
        _reported(mae, has_mae), has_mae,
        _reported(rmse, has_rmse), has_rmse,
        _reported(mape, has_mape), has_mape, defined_pct, n - defined_pct,
        _reported(smape, has_smape), has_smape, defined_sym, n - defined_sym,
        _reported(mase, has_mase), has_mase,
        _reported(scale, has_scale), has_scale,
        fc_status_name(FC_OK),
    )
