"""
forecasting.bagging — moving-block-bootstrap aggregated forecasts (bagged ETS), keyed
draws, on this package's own fitted candidates. Zero Python imports.

What this module adds
---------------------
Bergmeir-Hyndman bagging on this substrate: decompose the series into a trend and a
remainder, MOVING-BLOCK-BOOTSTRAP the remainder (blocks preserve the local
autocorrelation an i.i.d. resample would destroy), recompose B simulated versions of the
series, refit ONE chosen candidate on each, and average the forecast paths. The average
over refits on perturbed histories flattens the parameter-estimation variance of a
single fit — the same reason M4 combinations beat selected single methods, applied to
one method across simulated histories instead of across methods.

The candidate pool, fits and forecast paths are `forecasting.select`'s (SES via
golden-section alpha, the fitted damped trend, classical Theta); this module perturbs
their INPUT, never their recursions. The ensemble includes the fit on the ORIGINAL
series — the bootstrap replicates are corrections around the real record, not a
replacement for it — and a replicate whose refit refuses is skipped and COUNTED
(`n_boot_refused`), never zero-filled.

Determinism
-----------
Every block start is a keyed draw through `determinism.counter_rng` (Philox4x64-10),
addressed by `(master_seed, series_id, replicate_id, stream, draw_index)` with the
stream id derived by name via `determinism.streams.stream_id("forecasting.bagging")`.
A draw is a pure function of its coordinates: the same arguments give a bit-identical
ensemble on any machine, whatever ran before — and two candidates bagged with the same
seed see the SAME simulated histories (common random numbers across candidates).
`BaggedForecast` carries `rng_version()` so a stored ensemble names its generator.
Seeds are non-negative `Int`s exactly as `forecasting.interval` takes them; a negative
is FC_ERR_SEED_RANGE, not a cast.

Decomposition, and the honest edges
-----------------------------------
The trend is a centered moving average whose window SHRINKS symmetrically at the edges
(radius `min(half, i, n-1-i)`), so it is defined at every point without inventing data
beyond the record; at the two endpoints the trend equals the observation and the
remainder is exactly zero. That understates remainder variance in the outermost points
and the docstring says so — it is the price of refusing to extrapolate the record to pad
a window. Seasonality is NOT handled here: hand this module a deseasonalised series
(the package's `point.deseasonalise_flat` exists for exactly that) or a non-seasonal
one; a remainder taken around a moving average shorter than the season would carry the
season into every block draw.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: optional
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_forecasting_bagging.mojo
benchmark: benchmarks/mojo_benchmarks/bench_forecasting.mojo
docs: none
version_introduced: 0.10.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from determinism.counter_rng import rng_uniform, rng_version
from determinism.streams import stream_id

from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_METHOD,
    FC_ERR_NON_FINITE,
    FC_ERR_PARAM_RANGE,
    FC_ERR_SEED_RANGE,
    FC_MAX_BACKTEST_WORK,
    FC_OK,
    fc_finite,
    fc_horizon_defect,
    fc_series_defect,
    fc_status_name,
    fc_work_fits,
)
from forecasting.fitted import damped_fitted
from forecasting.point import ets_ann_forecast, theta_forecast
from forecasting.select import (
    _golden_ses_alpha,
    _sel_method_ids,
    _ses_sse_mae,
    _theta_line,
)

# The replicate ceiling. Past a few hundred replicates the ensemble mean has converged
# to well under the forecast noise floor while the refit bill keeps growing linearly.
comptime BAG_MAX_BOOT: Int = 512

# The block-length floor: a block of one is an i.i.d. resample, which destroys exactly
# the autocorrelation the MOVING-block bootstrap exists to preserve.
comptime BAG_MIN_BLOCK: Int = 2

# The trend-window floor: a centered window needs at least one point each side.
comptime BAG_MIN_TREND_WINDOW: Int = 3

# The draw stream, derived by NAME so no integer collides with another consumer.
comptime BAG_STREAM_NAME = "forecasting.bagging"


@fieldwise_init
struct BaggedForecast(Copyable, Movable):
    """One candidate's bagged forecast: the ensemble mean and the ensemble census.

    `values` holds steps 1..horizon, EMPTY on refusal (`has_forecast` is the authority).
    The ensemble always includes the fit on the original series, so the divisor is
    `1 + n_boot_used`; `n_boot_used + n_boot_refused == n_boot_requested` and a refused
    replicate contributes NOTHING (skipped and counted, never zero-filled). `method_id`
    is the package vocabulary id of the bagged candidate; `candidate_index` is its
    position in `forecasting.select`'s tie-break order. `stream` and `rng_version` name
    the draw coordinates so a stored ensemble can be reproduced bit-for-bit.
    """

    var status: Int
    var method_id: Int
    var candidate_index: Int
    var horizon: Int
    var n_train: Int
    var values: List[Float64]
    var has_forecast: Bool
    var n_boot_requested: Int
    var n_boot_used: Int
    var n_boot_refused: Int
    var block_len: Int
    var trend_window: Int
    var master_seed: Int
    var series_id: Int
    var stream: Int
    var rng_version: String
    var status_name: String


def _no_bagged(
    status: Int, candidate: Int, horizon: Int, n_train: Int,
    n_boot: Int, block_len: Int, trend_window: Int, seed: Int, series_id: Int,
) -> BaggedForecast:
    """A refusal: no path, no ensemble, the request echoed so the record is auditable."""
    var ids = _sel_method_ids()
    var mid = ids[candidate] if candidate >= 0 and candidate < len(ids) else -1
    return BaggedForecast(
        status, mid, candidate, horizon, n_train, List[Float64](), False,
        n_boot, 0, 0, block_len, trend_window, seed, series_id,
        Int(stream_id(BAG_STREAM_NAME)), rng_version(), fc_status_name(status),
    )


def shrinking_ma_trend(y: List[Float64], trend_window: Int) -> List[Float64]:
    """Centered moving-average trend whose window shrinks symmetrically at the edges.

    At index `i` the radius is `min(trend_window // 2, i, n - 1 - i)`, so every point
    averages a window that exists entirely inside the record: no zero-padding (the
    frozen `time_series_decompose.moving_average_trend` zero-fills its edges, which
    would put spurious full-scale steps into a remainder), and no extrapolation. At the
    endpoints the radius is 0 and the trend EQUALS the observation — the remainder is
    exactly zero there, which understates edge variance and is stated rather than
    smoothed over. Even windows use `window // 2` each side, i.e. the odd window below.

    Empty for an empty series or `trend_window < BAG_MIN_TREND_WINDOW` — a trend over
    no window is not a trend.

    @capability shrinking_ma_trend
    complexity: O(n * trend_window)
    counts:
    - dim trend_window [kernel_validated]
    @endcapability
    """
    var out = List[Float64]()
    var n = len(y)
    if n == 0 or trend_window < BAG_MIN_TREND_WINDOW:
        return out^
    var half = trend_window // 2
    for i in range(n):
        var radius = half
        if i < radius:
            radius = i
        if n - 1 - i < radius:
            radius = n - 1 - i
        var s: Float64 = 0.0
        for j in range(i - radius, i + radius + 1):
            s += y[j]
        out.append(s / Float64(2 * radius + 1))
    return out^


def mbb_replicate(
    remainder: List[Float64], block_len: Int, master_seed: Int,
    series_id: Int, replicate_id: Int,
) -> List[Float64]:
    """One moving-block-bootstrap resample of `remainder`, same length, keyed draws.

    Blocks of `block_len` consecutive values are drawn with replacement — start index
    uniform on `[0, n - block_len]`, one keyed draw per block through
    `determinism.counter_rng.rng_uniform` at `(master_seed, series_id, replicate_id,
    stream, draw_index = block ordinal)` — concatenated and truncated to `n`. Contiguity
    inside a block is the method: it preserves autocorrelation up to `block_len` lags.
    `block_len == n` admits exactly one start, so the resample IS the remainder — the
    suite pins that identity.

    Empty for an empty remainder, `block_len` outside `[BAG_MIN_BLOCK, n]`, a negative
    seed / series / replicate id, or a non-finite remainder. Empty rather than partial:
    a resample missing an unknown number of members would recompose a series of the
    wrong length and the refit would score a phantom.

    @capability mbb_replicate
    complexity: O(n)
    counts:
    - dim block_len [kernel_validated]
    @endcapability
    """
    var out = List[Float64]()
    var n = len(remainder)
    if n == 0 or block_len < BAG_MIN_BLOCK or block_len > n:
        return out^
    if master_seed < 0 or series_id < 0 or replicate_id < 0:
        return out^
    for i in range(n):
        if not fc_finite(remainder[i]):
            return List[Float64]()
    var stream = stream_id(BAG_STREAM_NAME)
    var n_starts = n - block_len + 1
    var block = 0
    while len(out) < n:
        var u = rng_uniform(
            UInt64(master_seed), UInt64(series_id), UInt64(replicate_id),
            0, 0, stream, UInt64(block),
        )
        var start = Int(u * Float64(n_starts))
        if start >= n_starts:
            start = n_starts - 1
        for j in range(block_len):
            if len(out) < n:
                out.append(remainder[start + j])
        block += 1
    return out^


def _fit_one_candidate(
    y: List[Float64], horizon: Int, candidate: Int
) -> List[Float64]:
    """Candidate `candidate`'s forecast path on `y`, or EMPTY when the fit refuses.

    The same fits `forecasting.select._fit_candidates` runs, called one at a time so a
    bagging pass does not pay for the two candidates it is not bagging. Candidate order
    is `select`'s tie-break order: 0 = SES, 1 = Damped, 2 = Theta.
    """
    if candidate == 0:
        var a = _golden_ses_alpha(y)
        var chk = _ses_sse_mae(y, a)
        var fc = ets_ann_forecast(y, a, horizon)
        if len(chk) == 2 and fc.has_forecast and len(fc.values) == horizon:
            return fc.values.copy()
        return List[Float64]()
    if candidate == 1:
        var dmp = damped_fitted(y, horizon)
        if dmp.has_forecast and len(dmp.values) == horizon:
            return dmp.values.copy()
        return List[Float64]()
    var z = _theta_line(y)
    if len(z) != len(y) or len(z) < 2:
        return List[Float64]()
    var a_th = _golden_ses_alpha(z)
    var chk_th = _ses_sse_mae(z, a_th)
    var fc_th = theta_forecast(y, 2.0, a_th, horizon)
    if len(chk_th) == 2 and fc_th.has_forecast and len(fc_th.values) == horizon:
        return fc_th.values.copy()
    return List[Float64]()


def bagged_candidate_forecast(
    y: List[Float64], horizon: Int, candidate: Int, n_boot: Int,
    block_len: Int, trend_window: Int, master_seed: Int, series_id: Int,
) -> BaggedForecast:
    """The moving-block-bootstrap bagged forecast of ONE fitted candidate.

    Decompose (shrinking-window centered MA trend, additive remainder), draw `n_boot`
    keyed MBB resamples of the remainder, recompose, refit the candidate on each,
    average the paths TOGETHER WITH the fit on the original series. A replicate whose
    recomposition is non-finite or whose refit refuses is skipped and counted in
    `n_boot_refused`. If the fit on the ORIGINAL series refuses, the whole call refuses
    with that fact as FC_ERR_ALL_UNDEFINED — an ensemble whose center is missing is not
    a bagged version of anything.

    Hand this a DESEASONALISED or non-seasonal series; the module docstring says why.

    @capability bagged_candidate_forecast
    complexity: O(n_boot * n) -- n_boot + 1 bounded single-candidate refits
    counts:
    - dim horizon [kernel_validated]
    - dim n_boot [kernel_validated]
    - dim block_len [kernel_validated]
    - dim trend_window [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect == FC_OK:
        defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_bagged(
            defect, candidate, horizon, n, n_boot, block_len, trend_window,
            master_seed, series_id,
        )
    if candidate < 0 or candidate >= 3:
        return _no_bagged(
            FC_ERR_METHOD, candidate, horizon, n, n_boot, block_len, trend_window,
            master_seed, series_id,
        )
    if n_boot < 1 or n_boot > BAG_MAX_BOOT:
        return _no_bagged(
            FC_ERR_PARAM_RANGE, candidate, horizon, n, n_boot, block_len,
            trend_window, master_seed, series_id,
        )
    if block_len < BAG_MIN_BLOCK or block_len > n:
        return _no_bagged(
            FC_ERR_PARAM_RANGE, candidate, horizon, n, n_boot, block_len,
            trend_window, master_seed, series_id,
        )
    if trend_window < BAG_MIN_TREND_WINDOW:
        return _no_bagged(
            FC_ERR_PARAM_RANGE, candidate, horizon, n, n_boot, block_len,
            trend_window, master_seed, series_id,
        )
    if master_seed < 0 or series_id < 0:
        return _no_bagged(
            FC_ERR_SEED_RANGE, candidate, horizon, n, n_boot, block_len,
            trend_window, master_seed, series_id,
        )
    if not fc_work_fits(n_boot, n, FC_MAX_BACKTEST_WORK):
        return _no_bagged(
            FC_ERR_PARAM_RANGE, candidate, horizon, n, n_boot, block_len,
            trend_window, master_seed, series_id,
        )

    var base = _fit_one_candidate(y, horizon, candidate)
    if len(base) != horizon:
        return _no_bagged(
            FC_ERR_ALL_UNDEFINED, candidate, horizon, n, n_boot, block_len,
            trend_window, master_seed, series_id,
        )

    var trend = shrinking_ma_trend(y, trend_window)
    if len(trend) != n:
        return _no_bagged(
            FC_ERR_NON_FINITE, candidate, horizon, n, n_boot, block_len,
            trend_window, master_seed, series_id,
        )
    var remainder = List[Float64](capacity=n)
    for i in range(n):
        var r = y[i] - trend[i]
        if not fc_finite(r):
            return _no_bagged(
                FC_ERR_NON_FINITE, candidate, horizon, n, n_boot, block_len,
                trend_window, master_seed, series_id,
            )
        remainder.append(r)

    # The ensemble mean is accumulated as DEVIATIONS around the original-series fit:
    # `base + sum(path - base) / (1 + used)`. Algebraically the plain mean, but the
    # rounding lives on the deviation scale — and when every replicate reproduces the
    # base path exactly (zero remainder, full-length blocks) the deviation sum is
    # EXACTLY zero, so `bagged == single fit` is an identity the suite can assert
    # with `==` rather than a tolerance.
    var acc = List[Float64](capacity=horizon)
    for _ in range(horizon):
        acc.append(0.0)
    var used = 0
    var refused = 0
    for b in range(n_boot):
        var rstar = mbb_replicate(remainder, block_len, master_seed, series_id, b)
        if len(rstar) != n:
            refused += 1
            continue
        var ystar = List[Float64](capacity=n)
        var clean = True
        for i in range(n):
            var v = trend[i] + rstar[i]
            if not fc_finite(v):
                clean = False
                break
            ystar.append(v)
        if not clean:
            refused += 1
            continue
        var path = _fit_one_candidate(ystar, horizon, candidate)
        if len(path) != horizon:
            refused += 1
            continue
        for h in range(horizon):
            acc[h] += path[h] - base[h]
        used += 1

    var values = List[Float64](capacity=horizon)
    var divisor = Float64(1 + used)
    for h in range(horizon):
        var v = base[h] + acc[h] / divisor
        if not fc_finite(v):
            return _no_bagged(
                FC_ERR_NON_FINITE, candidate, horizon, n, n_boot, block_len,
                trend_window, master_seed, series_id,
            )
        values.append(v)
    var ids = _sel_method_ids()
    return BaggedForecast(
        FC_OK, ids[candidate], candidate, horizon, n, values^, True,
        n_boot, used, refused, block_len, trend_window, master_seed, series_id,
        Int(stream_id(BAG_STREAM_NAME)), rng_version(), fc_status_name(FC_OK),
    )
