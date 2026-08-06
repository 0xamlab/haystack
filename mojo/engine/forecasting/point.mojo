"""
forecasting.point — ETS, Theta, checked AR and seasonal adjustment. Zero Python imports.

Nothing here implements a smoother, a regression or an AR fit. Every number comes out of a
frozen kernel:

  | quantity                        | frozen kernel called unchanged                     |
  | ------------------------------- | -------------------------------------------------- |
  | SES level path / level          | `series.exponential_forecast`                      |
  | Holt level path                 | `timeseries_stats.holt_linear`                     |
  | OLS intercept and slope         | `series._ols_fit`                                  |
  | centered moving-average trend   | `time_series_decompose.moving_average_trend`       |
  | detrending                      | `time_series_decompose.detrend`                    |
  | per-phase seasonal averages     | `time_series_decompose.seasonal_component`         |
  | naive / drift / window mean      | `series.naive_forecast`, `drift_forecast`, `sma_forecast` |
  | seasonal naive                  | `series.seasonal_naive`                            |
  | Yule-Walker AR fit and forecast | `arima.ar_fit_yule_walker`, `arima.ar_forecast`    |

What this module adds is the four things those kernels do not have: validation, an absence
marker, the extrapolation step, and a status.

How the Holt state is recovered WITHOUT re-running the smoother
--------------------------------------------------------------
`timeseries_stats.holt_linear` returns the LEVEL path and keeps its trend internal, so a
forecast cannot be read off its output directly. It does not need to be recomputed: the
frozen recursion is

    l_i = alpha * x_i + (1 - alpha) * (l_{i-1} + b_{i-1})
    b_i = beta  * (l_i - l_{i-1}) + (1 - beta) * b_{i-1},   b_0 = x_1 - x_0

and the second line depends only on the level path, `beta` and `b_0`. So `_holt_state`
replays the TREND line over the frozen kernel's own levels. There is no second smoother
here, and if `holt_linear` ever changes, the trend derived from its output changes with it,
which is the point.

Theta, stated precisely, because the folklore version is wrong about linear series
------------------------------------------------------------------------------------
The theta-line of a series is `Z_t(theta) = theta * y_t + (1 - theta) * L_t`, where `L` is
the OLS line fitted to `y`. That family has an exact decomposition identity,

    y = (1/theta) * Z(theta) + (1 - 1/theta) * Z(0),      Z(0) = L

which is where `theta_forecast`'s weights come from: they are not tuned, they are the
identity's own coefficients. `Z(0)` is a straight line and is extrapolated as one; `Z(theta)`
is extrapolated by frozen SES. `theta = 2` is the classical method and gives 0.5/0.5;
`theta = 1` degenerates to plain SES, which is correct and not a special case.

**Classical Theta does NOT reproduce a linear trend, and this is stated because a test that
asserted it would be asserting a bug.** On `y_t = a + b*t` the OLS line is `y` itself, so
`Z(theta) = y` for every theta, SES at `alpha = 1` returns `y_{n-1}`, and

    f_h = (1 - 1/theta) * (a + b*(n-1+h)) + (1/theta) * (a + b*(n-1))
        = y_{n-1} + (1 - 1/theta) * b * h

— the slope is DAMPED by `1 - 1/theta`, i.e. halved at `theta = 2`. That closed form is what
the suite asserts, since a hand-derived formula is stronger evidence than "close to the truth".

`theta_drift_forecast` is the variant for a caller who needs the trend reproduced: SES level
plus the FULL OLS slope. On a pure linear series it is exact, and it then agrees to the bit
with two independent frozen computations — `series.drift_forecast` (endpoint slope) and
`series.linear_extrapolation` (OLS line) — because on that input all three slopes coincide.
Agreement between three independent computations is evidence; one plausible number is not.

Seasonal indices are estimated only where the frozen trend EXISTS
-----------------------------------------------------------------
`moving_average_trend` zero-pads the first and last `period // 2` positions, so
`detrend(y, trend)` returns the RAW observation at those positions rather than a detrended
one. Feeding that straight into `seasonal_component` — which is what `decompose_additive`
does — averages padding into the seasonal estimate, and on a trending series the result is
badly wrong: on `y_t = 2t + s_{t mod 4}` over 12 points it produced indices
`[5/3, 1/3, 28/3, 6]` against a truth of `s + 1`, and the one-step forecast came out 17
against a true 25.

So `_seasonal_indices` slices the interior `[half, n - half)` — exactly where the frozen
trend is defined — hands THAT to the frozen `seasonal_component`, and rotates the phases
back: interior position `j` is series index `j + half`, so `raw[j]` belongs to true phase
`(j + half) mod period`. On the same series that recovers `s_p + 1` exactly (the `+1` is the
constant offset of the centered MA on an even period, which the Holt level absorbs when the
indices are added back), and `ets_aaa_forecast` then reproduces all four next values
EXACTLY. That is the known-value case in the suite.

The offset is REPORTED, not removed. `seasonal_component` does not center its averages;
`SeasonalAdjust.index_mean` says by how much, and recentring here would mean returning
numbers the frozen kernel did not produce.

Absence, per Rule 4
-------------------
`PointForecast.has_forecast` is the authority; on any refusal `values` is EMPTY, never a
padded list of zeros, and never the last observation "as a fallback". `has_level`,
`has_trend` and `has_scale` mark the three state quantities separately, because a method
that estimates no trend (SES) and a method whose trend came out zero are different facts.

Status codes 300-319 via `forecasting.contract`; no table here.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_forecasting_point.mojo
benchmark: benchmarks/mojo_benchmarks/bench_forecasting.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from arima import ar_fit_yule_walker, ar_forecast
from series import (
    _ols_fit,
    drift_forecast,
    naive_forecast,
    seasonal_naive,
    sma_forecast,
)
from time_series_decompose import detrend, moving_average_trend, seasonal_component
from timeseries_stats import holt_linear

from forecasting.contract import (
    FC_ERR_DIMENSION_TOO_LARGE,
    FC_ERR_EMPTY_SERIES,
    FC_ERR_INSUFFICIENT_HISTORY,
    FC_ERR_METHOD,
    FC_ERR_NON_FINITE,
    FC_ERR_PARAM_RANGE,
    FC_ERR_PERIOD,
    FC_METHOD_AR,
    FC_METHOD_DRIFT,
    FC_METHOD_ETS_AAA,
    FC_METHOD_ETS_AAN,
    FC_METHOD_ETS_ANN,
    FC_METHOD_MEAN,
    FC_METHOD_NAIVE,
    FC_METHOD_SEASONAL_NAIVE,
    FC_METHOD_THETA,
    FC_METHOD_THETA_DRIFT,
    FC_MAX_BACKTEST_WORK,
    FC_OK,
    MAX_FC_AR_ORDER,
    _fc_ses_level,
    fc_all_finite,
    fc_damping_defect,
    fc_finite,
    fc_horizon_defect,
    fc_period_defect,
    fc_series_defect,
    fc_smoothing_defect,
    fc_status_name,
    fc_tolerance,
    fc_work_fits,
)

# `1/theta` must stay meaningful and `1 - 1/theta` must stay strictly below 1: past this a
# theta-line is numerically the OLS line and the SES term contributes nothing, so a caller
# asking for it wants `series.linear_extrapolation` and should say so.
comptime FC_MAX_THETA: Float64 = 1.0e6


@fieldwise_init
struct PointForecast(Copyable, Movable):
    """A point forecast path plus the state it was produced from.

    `values` holds steps `1..horizon` in order, i.e. `values[h-1]` forecasts observation
    index `n_train - 1 + h`. On any status other than FC_OK it is EMPTY and `has_forecast`
    is False: a refusal carries no partial path, no padded zeros and no repeated last value.

    `level` / `trend` / `scale` are the terminal state of whichever method ran, each with its
    own presence flag, because "this method has no trend term" and "this method's trend came
    out 0.0" are different facts and 0.0 cannot express both. `scale` is an innovation
    VARIANCE where the method estimates one (AR via Yule-Walker) and is absent otherwise.

    `n_params` counts the fitted quantities that are actually carrying information: for AR it
    is the number of NONZERO coefficients, so a degenerate fit on a constant series (all
    coefficients zero, forecast equal to the sample mean) is distinguishable from a real
    AR(p). Reporting `p` there would claim structure the fit did not find.
    """

    var status: Int
    var method_id: Int
    var horizon: Int
    var n_train: Int
    var values: List[Float64]
    var has_forecast: Bool
    var level: Float64
    var has_level: Bool
    var trend: Float64
    var has_trend: Bool
    var scale: Float64
    var has_scale: Bool
    var n_params: Int
    var status_name: String


@fieldwise_init
struct SeasonalAdjust(Copyable, Movable):
    """A seasonally adjusted series, its indices, and a reversibility certificate.

    `indices[p]` is the additive index for phase `p`, so observation `t` carries index
    `indices[t % period]` and a future step `h` carries `indices[(n_obs - 1 + h) % period]`.
    `adjusted[t] = y[t] - indices[t % period]`.

    `index_mean` is the mean of the indices and is NOT removed — see the module docstring.

    WHAT THE CERTIFICATE COVERS, and nothing more: `reversible` is True only when, for EVERY
    observation, `|(adjusted[t] + indices[t % period]) - y[t]|` is within that observation's
    own rounding budget `fc_tolerance(|y[t]|, 0)`. Per observation, from that observation's
    own magnitude — a max or a sum over the series would let one large value's units pay for
    another's error. `max_recompose_residual` is that largest difference and is a measured
    number, not a bound: `(y - s) + s` is not exactly `y` in IEEE arithmetic.

    It does NOT claim the indices are the true seasonal pattern, that `period` is the right
    period, or that `n_cycles` cycles are enough to estimate one. `n_cycles` is reported so a
    caller can judge that themselves: it is the number of complete cycles inside the region
    where the frozen centered trend is defined, which is `(n_obs - 2 * (period // 2))`
    positions — always fewer than the series length.
    """

    var status: Int
    var period: Int
    var n_obs: Int
    var n_cycles: Int
    var adjusted: List[Float64]
    var indices: List[Float64]
    var has_result: Bool
    var index_mean: Float64
    var max_recompose_residual: Float64
    var reversible: Bool
    var status_name: String


def _no_forecast(status: Int, method_id: Int, horizon: Int, n_train: Int) -> PointForecast:
    """A refusal: no path, no state, every presence flag cleared."""
    return PointForecast(
        status, method_id, horizon, n_train, List[Float64](), False,
        0.0, False, 0.0, False, 0.0, False, 0, fc_status_name(status),
    )


def _no_adjust(status: Int, period: Int, n_obs: Int) -> SeasonalAdjust:
    """A refusal: no adjusted series, no indices, no certificate."""
    return SeasonalAdjust(
        status, period, n_obs, 0, List[Float64](), List[Float64](), False,
        0.0, 0.0, False, fc_status_name(status),
    )


def _damped_sum(phi: Float64, h: Int) -> Float64:
    """`phi + phi^2 + ... + phi^h`, the damped trend multiplier for step `h`.

    Accumulated rather than closed-form. The closed form `phi * (1 - phi^h) / (1 - phi)` has
    a removable singularity at `phi = 1` — exactly the undamped case, which is the common
    one — and a `if phi == 1` branch beside a division is two code paths for one quantity.
    `h` is bounded by `MAX_FC_HORIZON`, so the loop is bounded.
    """
    var total: Float64 = 0.0
    var power: Float64 = 1.0
    for _ in range(h):
        power *= phi
        total += power
    return total


def _holt_state(y: List[Float64], alpha: Float64, beta: Float64) -> List[Float64]:
    """`[level, trend]` at the end of the frozen Holt recursion, or empty on refusal.

    The level path is `timeseries_stats.holt_linear`'s output, unchanged. The trend is
    replayed from THAT path by the frozen kernel's own second recursion line, which depends
    only on the levels, `beta` and `b_0 = x_1 - x_0` — see the module docstring. No smoothing
    happens here.

    Empty for an empty series or a level path whose length does not match, and empty when any
    state came out non-finite, so a caller can never read a NaN level as a forecast.
    """
    var out = List[Float64]()
    var n = len(y)
    if n == 0:
        return out^
    var levels = holt_linear(y, alpha, beta)
    if len(levels) != n:
        return out^
    var trend: Float64 = 0.0
    if n > 1:
        trend = y[1] - y[0]
    for i in range(1, n):
        trend = beta * (levels[i] - levels[i - 1]) + (1.0 - beta) * trend
    var level = levels[n - 1]
    if not fc_finite(level) or not fc_finite(trend):
        return out^
    out.append(level)
    out.append(trend)
    return out^


def _seasonal_indices(y: List[Float64], period: Int) -> List[Float64]:
    """Additive seasonal indices by phase, estimated only where the frozen trend exists.

    Returns `period` values, or empty when the series cannot support one complete interior
    cycle. `period == 1` returns a single 0.0 — no seasonality is an additive index of zero,
    which keeps every caller free of a `period == 1` special case.

    Composition, in order, all four steps frozen:
      `moving_average_trend(y, period)` -> `detrend(y, trend)` -> slice `[half, n - half)`
      -> `seasonal_component(interior, period)`, then rotate phase by `half`.
    The slice is the whole point; see the module docstring for the measured failure without it.
    """
    var out = List[Float64]()
    var n = len(y)
    if period < 1 or n <= 0:
        return out^
    if period == 1:
        out.append(0.0)
        return out^
    var half = period // 2
    if n < period + 2 * half:
        return out^
    var trend = moving_average_trend(y, period)
    if len(trend) != n:
        return out^
    var detrended = detrend(y, trend)
    if len(detrended) != n:
        return out^
    var interior = List[Float64]()
    for i in range(half, n - half):
        interior.append(detrended[i])
    if len(interior) < period:
        return out^
    var raw = seasonal_component(interior, period)
    if len(raw) < period:
        return out^
    for p in range(period):
        var j = ((p - half) % period + period) % period
        if not fc_finite(raw[j]):
            return List[Float64]()
        out.append(raw[j])
    return out^


def ets_ann_forecast(
    y: List[Float64], alpha: Float64, horizon: Int
) -> PointForecast:
    """ETS(A,N,N) — simple exponential smoothing. Flat path at the terminal level.

    The whole computation is the frozen `series.exponential_forecast`, which produces both the
    level and the flat path; this driver validates, marks absence and reports a status.
    A flat forecast is the correct answer for a level-only model and is not a degenerate one.

    @capability ets_ann_forecast
    complexity: O(n + horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_ANN, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_ANN, horizon, n)
    defect = fc_smoothing_defect(alpha)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_ANN, horizon, n)
    var state = _fc_ses_level(y, alpha)
    if len(state) != 1:
        return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_ETS_ANN, horizon, n)
    var values = List[Float64]()
    for _ in range(horizon):
        values.append(state[0])
    return PointForecast(
        FC_OK, FC_METHOD_ETS_ANN, horizon, n, values^, True,
        state[0], True, 0.0, False, 0.0, False, 1, fc_status_name(FC_OK),
    )


def ets_aan_forecast(
    y: List[Float64], alpha: Float64, beta: Float64, phi: Float64, horizon: Int
) -> PointForecast:
    """ETS(A,A,N) with damped trend: `f_h = level + trend * (phi + ... + phi^h)`.

    `phi = 1` is undamped Holt. Needs at least two observations, because a trend estimated
    from one point does not exist — the frozen `holt_linear` initialises `b_0 = x_1 - x_0`
    and silently uses 0.0 when there is no `x_1`, which returns a flat path under a
    trend-model label.

    On `y_t = a + b*t` with `alpha = beta = 1` this is EXACT and equals
    `series.drift_forecast` to the bit; the suite asserts both.

    @capability ets_aan_forecast
    complexity: O(n + horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_AAN, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_AAN, horizon, n)
    defect = fc_smoothing_defect(alpha)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_AAN, horizon, n)
    defect = fc_smoothing_defect(beta)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_AAN, horizon, n)
    defect = fc_damping_defect(phi)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_AAN, horizon, n)
    if n < 2:
        return _no_forecast(FC_ERR_INSUFFICIENT_HISTORY, FC_METHOD_ETS_AAN, horizon, n)
    var state = _holt_state(y, alpha, beta)
    if len(state) != 2:
        return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_ETS_AAN, horizon, n)
    # `_damped_sum(phi, h)` recomputes `phi + ... + phi^h` from scratch, so calling it once per
    # `h` makes this O(horizon^2) while the declared complexity is O(n + horizon) and
    # `backtest._per_origin_cost` charges `n_obs + horizon`. FC_MAX_BACKTEST_WORK therefore never
    # saw a whole factor of `horizon`. MEASURED, identical shape, every declared ceiling satisfied
    # (n = 2,000,000, horizon = min_train = step = 16384, 121 origins):
    #   FC_METHOD_ETS_ANN   0.49 s
    #   FC_METHOD_ETS_AAN  23.89 s      -- 48x
    # At the permitted extreme the same arithmetic admits ~6.9e10 iterations, about 100 s of CPU
    # for one structurally valid request. Bounding memory is not bounding work, and from the
    # caller's side an undercharged loop IS the hang.
    #
    # The running sum is the same quantity `_damped_sum` returns for each `h`, accumulated once
    # instead of re-derived, so every emitted value is bit-identical and no `phi == 1` branch
    # appears. `_damped_sum` itself is left alone: it is correct standalone and still used where a
    # single `h` is wanted.
    var values = List[Float64]()
    var damped = Float64(0.0)
    var power = Float64(1.0)
    for h in range(1, horizon + 1):
        power *= phi
        damped += power
        var v = state[0] + state[1] * damped
        if not fc_finite(v):
            return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_ETS_AAN, horizon, n)
        values.append(v)
    return PointForecast(
        FC_OK, FC_METHOD_ETS_AAN, horizon, n, values^, True,
        state[0], True, state[1], True, 0.0, False, 2, fc_status_name(FC_OK),
    )


def ets_aaa_forecast(
    y: List[Float64], alpha: Float64, beta: Float64, phi: Float64,
    period: Int, horizon: Int
) -> PointForecast:
    """ETS(A,A,A) — additive trend and additive season, over frozen kernels only.

    Deseasonalise with `_seasonal_indices`, run the frozen Holt state on the adjusted
    series, extrapolate with the damped trend, then add the index of the future phase
    `(n - 1 + h) mod period` back.

    `period == 1` is accepted and reduces exactly to `ets_aan_forecast` (index 0.0).
    A period the series cannot support one interior cycle of is FC_ERR_PERIOD, not a
    forecast built from the frozen kernel's edge padding.

    On `y_t = 2t + s_{t mod 4}` over 12 observations with `alpha = beta = phi = 1` this
    reproduces the next four values EXACTLY; the suite asserts all four.

    @capability ets_aaa_forecast
    complexity: O(n + horizon)
    counts:
    - dim period [kernel_validated]
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_AAA, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_AAA, horizon, n)
    defect = fc_period_defect(n, period)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_AAA, horizon, n)
    defect = fc_smoothing_defect(alpha)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_AAA, horizon, n)
    defect = fc_smoothing_defect(beta)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_AAA, horizon, n)
    defect = fc_damping_defect(phi)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_ETS_AAA, horizon, n)
    if n < 2:
        return _no_forecast(FC_ERR_INSUFFICIENT_HISTORY, FC_METHOD_ETS_AAA, horizon, n)
    var indices = _seasonal_indices(y, period)
    if len(indices) != period:
        return _no_forecast(FC_ERR_PERIOD, FC_METHOD_ETS_AAA, horizon, n)
    var adjusted = List[Float64]()
    for t in range(n):
        adjusted.append(y[t] - indices[t % period])
    if not fc_all_finite(adjusted):
        return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_ETS_AAA, horizon, n)
    var state = _holt_state(adjusted, alpha, beta)
    if len(state) != 2:
        return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_ETS_AAA, horizon, n)
    # `_damped_sum(phi, h)` recomputes `phi + ... + phi^h` from scratch, so calling it once per
    # `h` makes this O(horizon^2) while the declared complexity is O(n + horizon) and
    # `backtest._per_origin_cost` charges `n_obs + horizon`. FC_MAX_BACKTEST_WORK therefore never
    # saw a whole factor of `horizon`. MEASURED, identical shape, every declared ceiling satisfied
    # (n = 2,000,000, horizon = min_train = step = 16384, 121 origins):
    #   FC_METHOD_ETS_ANN   0.49 s
    #   FC_METHOD_ETS_AAN  23.89 s      -- 48x
    # At the permitted extreme the same arithmetic admits ~6.9e10 iterations, about 100 s of CPU
    # for one structurally valid request. Bounding memory is not bounding work, and from the
    # caller's side an undercharged loop IS the hang.
    #
    # The running sum is the same quantity `_damped_sum` returns for each `h`, accumulated once
    # instead of re-derived, so every emitted value is bit-identical and no `phi == 1` branch
    # appears. `_damped_sum` itself is left alone: it is correct standalone and still used where a
    # single `h` is wanted.
    var values = List[Float64]()
    var damped = Float64(0.0)
    var power = Float64(1.0)
    for h in range(1, horizon + 1):
        power *= phi
        damped += power
        var v = state[0] + state[1] * damped + indices[(n - 1 + h) % period]
        if not fc_finite(v):
            return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_ETS_AAA, horizon, n)
        values.append(v)
    return PointForecast(
        FC_OK, FC_METHOD_ETS_AAA, horizon, n, values^, True,
        state[0], True, state[1], True, 0.0, False, 2 + period, fc_status_name(FC_OK),
    )


def theta_forecast(
    y: List[Float64], theta: Float64, alpha: Float64, horizon: Int
) -> PointForecast:
    """Classical Theta: the theta-line decomposition identity's own weights.

    `Z_t = theta * y_t + (1 - theta) * L_t` for the frozen OLS line `L`, then
    `f_h = (1 - 1/theta) * L(n-1+h) + (1/theta) * SES(Z)`. `theta = 2` is the classical
    equal-weight method; `theta = 1` is plain SES and is not a special case in the code.

    `theta < 1` is refused: it puts a NEGATIVE weight on the extrapolated trend line, so the
    forecast leans against the fitted trend. That is not a damping choice, it is a sign
    error waiting to be shipped, and `theta_drift_forecast` is the driver for a caller who
    wants MORE trend rather than less.

    THIS METHOD DAMPS A LINEAR TREND BY `1 - 1/theta` — it does not reproduce it. On
    `y_t = a + b*t` with `alpha = 1` the closed form is `y_{n-1} + (1 - 1/theta) * b * h`,
    which the suite asserts exactly. `trend` reports the FULL OLS slope `b`, not the damped
    one, because that is the fitted quantity; the damping lives in the path.

    @capability theta_forecast
    complexity: O(n + horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_THETA, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_THETA, horizon, n)
    defect = fc_smoothing_defect(alpha)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_THETA, horizon, n)
    if not fc_finite(theta):
        return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_THETA, horizon, n)
    if theta < 1.0 or theta > FC_MAX_THETA:
        return _no_forecast(FC_ERR_PARAM_RANGE, FC_METHOD_THETA, horizon, n)
    var fit = _ols_fit(y)
    if len(fit) != 2 or not fc_finite(fit[0]) or not fc_finite(fit[1]):
        return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_THETA, horizon, n)
    var intercept = fit[0]
    var slope = fit[1]
    var z = List[Float64]()
    for t in range(n):
        z.append(theta * y[t] + (1.0 - theta) * (intercept + slope * Float64(t)))
    if not fc_all_finite(z):
        return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_THETA, horizon, n)
    var state = _fc_ses_level(z, alpha)
    if len(state) != 1:
        return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_THETA, horizon, n)
    var w_line = 1.0 - 1.0 / theta
    var w_ses = 1.0 / theta
    var values = List[Float64]()
    for h in range(1, horizon + 1):
        var line = intercept + slope * Float64(n - 1 + h)
        var v = w_line * line + w_ses * state[0]
        if not fc_finite(v):
            return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_THETA, horizon, n)
        values.append(v)
    return PointForecast(
        FC_OK, FC_METHOD_THETA, horizon, n, values^, True,
        state[0], True, slope, True, 0.0, False, 3, fc_status_name(FC_OK),
    )


def theta_drift_forecast(
    y: List[Float64], alpha: Float64, horizon: Int
) -> PointForecast:
    """SES level plus the FULL frozen OLS slope: `f_h = SES(y) + b * h`.

    The variant for a caller who needs a linear trend REPRODUCED rather than damped. On
    `y_t = a + b*t` with `alpha = 1` it is exact, and it then equals
    `series.drift_forecast(y, horizon)` and `series.linear_extrapolation(y, horizon)` to the
    bit, because on that input the endpoint slope and the OLS slope coincide. The suite
    asserts the three-way agreement rather than a single plausible number.

    It is NOT `theta_forecast` at any theta: the line term there is anchored at the OLS
    line's value at `n-1`, this one at the SES level, and the two differ whenever the series
    is not exactly linear.

    @capability theta_drift_forecast
    complexity: O(n + horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_THETA_DRIFT, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_THETA_DRIFT, horizon, n)
    defect = fc_smoothing_defect(alpha)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_THETA_DRIFT, horizon, n)
    if n < 2:
        return _no_forecast(FC_ERR_INSUFFICIENT_HISTORY, FC_METHOD_THETA_DRIFT, horizon, n)
    var fit = _ols_fit(y)
    if len(fit) != 2 or not fc_finite(fit[1]):
        return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_THETA_DRIFT, horizon, n)
    var state = _fc_ses_level(y, alpha)
    if len(state) != 1:
        return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_THETA_DRIFT, horizon, n)
    var values = List[Float64]()
    for h in range(1, horizon + 1):
        var v = state[0] + fit[1] * Float64(h)
        if not fc_finite(v):
            return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_THETA_DRIFT, horizon, n)
        values.append(v)
    return PointForecast(
        FC_OK, FC_METHOD_THETA_DRIFT, horizon, n, values^, True,
        state[0], True, fit[1], True, 0.0, False, 2, fc_status_name(FC_OK),
    )


def ar_forecast_checked(
    y: List[Float64], ar_order: Int, horizon: Int
) -> PointForecast:
    """Yule-Walker AR(p) forecast with the frozen kernel's silent clamp made a status.

    `arima.ar_fit_yule_walker(series, p)` CLAMPS `p` to `n - 1` and then pads `phi` with
    zeros up to `p`, so asking for AR(10) on six observations returns an AR(5) wearing an
    AR(10) label — a different model presented as the requested one, with no way to tell.
    Here `ar_order > n - 1` is FC_ERR_INSUFFICIENT_HISTORY and nothing is fitted.

    The fit and the forecast are `arima.ar_fit_yule_walker` and `arima.ar_forecast`
    unchanged. `scale` is the frozen `sigma2`, the order-p innovation variance.

    `has_scale = False` with a valid forecast means the fit found NO innovation variance —
    `durbin_levinson` returns zero coefficients and `sigma2 = 0` when `gamma(0)` is
    effectively zero, i.e. a constant series. The forecast is then the sample mean, which is
    correct, and `n_params` counts the nonzero coefficients (zero) so it is distinguishable
    from a real AR(p). All-zero `phi` is also what a failed fit returns, and those two must
    not look alike.

    @capability ar_forecast_checked
    complexity: O(n * ar_order + ar_order^2 + horizon * ar_order)
    counts:
    - dim ar_order [kernel_validated]
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_AR, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_forecast(defect, FC_METHOD_AR, horizon, n)
    if ar_order < 1:
        return _no_forecast(FC_ERR_PARAM_RANGE, FC_METHOD_AR, horizon, n)
    if ar_order > MAX_FC_AR_ORDER:
        return _no_forecast(FC_ERR_DIMENSION_TOO_LARGE, FC_METHOD_AR, horizon, n)
    if ar_order > n - 1:
        return _no_forecast(FC_ERR_INSUFFICIENT_HISTORY, FC_METHOD_AR, horizon, n)
    if not fc_work_fits(ar_order, n + ar_order, FC_MAX_BACKTEST_WORK):
        return _no_forecast(FC_ERR_DIMENSION_TOO_LARGE, FC_METHOD_AR, horizon, n)
    var fit = ar_fit_yule_walker(y, ar_order)
    if len(fit.phi) != ar_order:
        return _no_forecast(FC_ERR_INSUFFICIENT_HISTORY, FC_METHOD_AR, horizon, n)
    if not fc_all_finite(fit.phi) or not fc_finite(fit.sigma2):
        return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_AR, horizon, n)
    var values = ar_forecast(y, fit.phi, horizon)
    if len(values) != horizon or not fc_all_finite(values):
        return _no_forecast(FC_ERR_NON_FINITE, FC_METHOD_AR, horizon, n)
    var nonzero = 0
    for i in range(ar_order):
        if fit.phi[i] != 0.0:
            nonzero += 1
    return PointForecast(
        FC_OK, FC_METHOD_AR, horizon, n, values^, True,
        y[n - 1], True, 0.0, False, fit.sigma2, fit.sigma2 > 0.0, nonzero,
        fc_status_name(FC_OK),
    )


def _baseline_defect(n: Int, method_id: Int, period: Int) -> Int:
    """Every precondition the four frozen baselines need, decided BEFORE any of them is called.

    Split out from `_baseline_values` on purpose: two of the frozen kernels index without
    checking, so the validation must be complete and in one place, and a validator that
    returns a code cannot accidentally fall through to a call the way an `if/elif` chain with
    a default branch can.
    """
    if method_id == FC_METHOD_NAIVE or method_id == FC_METHOD_MEAN:
        return FC_OK
    if method_id == FC_METHOD_DRIFT:
        return FC_OK if n >= 2 else FC_ERR_INSUFFICIENT_HISTORY
    if method_id == FC_METHOD_SEASONAL_NAIVE:
        if period < 1:
            return FC_ERR_PERIOD
        return FC_OK if period <= n else FC_ERR_INSUFFICIENT_HISTORY
    return FC_ERR_METHOD


def _baseline_values(
    y: List[Float64], method_id: Int, horizon: Int, period: Int
) -> List[Float64]:
    """Dispatch to the frozen baseline. Only ever called after `_baseline_defect` says FC_OK.

    An unknown id returns an EMPTY list, which the caller reads as a refusal — never a
    default method. `baseline_forecast` has already rejected the id, so the empty branch is
    unreachable from there; it exists so that this helper is safe on its own terms rather
    than only in the company of its current caller.
    """
    if method_id == FC_METHOD_NAIVE:
        return naive_forecast(y, horizon)
    if method_id == FC_METHOD_DRIFT:
        return drift_forecast(y, horizon)
    if method_id == FC_METHOD_MEAN:
        return sma_forecast(y, len(y), horizon)
    if method_id == FC_METHOD_SEASONAL_NAIVE:
        return seasonal_naive(y, period, horizon)
    return List[Float64]()


def baseline_forecast(
    y: List[Float64], method_id: Int, horizon: Int, period: Int
) -> PointForecast:
    """The four frozen baselines behind one guarded entry point, with a status.

    FC_METHOD_NAIVE -> `series.naive_forecast`, FC_METHOD_DRIFT -> `series.drift_forecast`,
    FC_METHOD_MEAN -> `series.sma_forecast` over the WHOLE window, FC_METHOD_SEASONAL_NAIVE
    -> `series.seasonal_naive`. `period` is read only by the last.

    These wrappers exist because two of the frozen four index without checking:

      * `naive_forecast` reads `data[len(data) - 1]`, so an empty series is an UNCATCHABLE
        process abort, not an error.
      * `seasonal_naive` reads `data[n - period + (h % period)]`, so `period > n` indexes
        NEGATIVE and `period <= 0` divides by zero. Both abort the worker.

    Neither is reachable from the generated A-Z suite, which calls them with a five-element
    list and `5`, so `n - period + h % period` lands in range and the hole is invisible
    there. The frozen kernels are unchanged; this is the guarded route.

    `drift_forecast` needs two observations (it divides by `n - 1`); with one it silently
    returns the single value repeated, which is `naive` under a `drift` label, so it is
    refused here instead.

    @capability baseline_forecast
    complexity: O(n + horizon)
    counts:
    - dim horizon [kernel_validated]
    - dim period [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_forecast(defect, method_id, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_forecast(defect, method_id, horizon, n)
    defect = _baseline_defect(n, method_id, period)
    if defect != FC_OK:
        return _no_forecast(defect, method_id, horizon, n)
    var values = _baseline_values(y, method_id, horizon, period)
    if len(values) != horizon or not fc_all_finite(values):
        return _no_forecast(FC_ERR_NON_FINITE, method_id, horizon, n)
    var level = values[0]
    return PointForecast(
        FC_OK, method_id, horizon, n, values^, True,
        level, True, 0.0, False, 0.0, False, 0, fc_status_name(FC_OK),
    )


def deseasonalise_flat(y: List[Float64], period: Int) -> SeasonalAdjust:
    """Seasonally adjust a series and CERTIFY that adding the indices back restores it.

    Indices come from `_seasonal_indices` (frozen composition, interior slice, phase
    rotation). See `SeasonalAdjust` for exactly what the certificate covers and what it does
    not — an incomplete certificate is worse than none, because a caller stops looking.

    A period the series cannot support one interior cycle of is FC_ERR_PERIOD with no
    adjusted series. Returning `y` unchanged with `has_result = True` would be the wrong
    answer wearing a success status.

    @capability deseasonalise_flat
    complexity: O(n * period)
    counts:
    - dim period [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_adjust(defect, period, n)
    defect = fc_period_defect(n, period)
    if defect != FC_OK:
        return _no_adjust(defect, period, n)
    var indices = _seasonal_indices(y, period)
    if len(indices) != period:
        return _no_adjust(FC_ERR_PERIOD, period, n)
    var adjusted = List[Float64]()
    for t in range(n):
        adjusted.append(y[t] - indices[t % period])
    if not fc_all_finite(adjusted):
        return _no_adjust(FC_ERR_NON_FINITE, period, n)

    var index_total: Float64 = 0.0
    for p in range(period):
        index_total += indices[p]
    var index_mean = index_total / Float64(period)

    # Reversibility, judged PER OBSERVATION against that observation's own magnitude.
    var worst: Float64 = 0.0
    var reversible = True
    for t in range(n):
        var restored = adjusted[t] + indices[t % period]
        var gap = fabs(restored - y[t])
        if gap > worst:
            worst = gap
        if gap > fc_tolerance(fabs(y[t]), 0.0):
            reversible = False

    var half = period // 2
    var interior_len = n - 2 * half
    var cycles = interior_len // period if period > 0 else 0
    return SeasonalAdjust(
        FC_OK, period, n, cycles, adjusted^, indices^, True,
        index_mean, worst, reversible, fc_status_name(FC_OK),
    )
