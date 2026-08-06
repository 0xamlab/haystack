"""
forecasting.pool — training-holdout selection and combination over the WIDE method pool.
Zero Python imports.

Why this module exists, in one measured sentence
------------------------------------------------
Per-series selection over the three-method pool (`forecasting.select`) has a measured
ceiling: on the full M4 corpus the test-window oracle over {SES, Damped, Theta} is
0.775 total OWA while every honest selection criterion lands at ~0.874, and the oracle
over the eight-candidate pool below is 0.671 — the pool, not the criterion, is where
the remaining headroom lives. This module widens the pool and moves the criterion from
in-sample one-step errors to a LAST-`horizon` TRAINING HOLDOUT, which is the only
criterion that can see a regime change between a series' body and its final stretch.

THE NO-LEAKAGE CONTRACT (the module's one inviolable rule)
----------------------------------------------------------
Every decision here is computed from the TRAINING series alone:

  * `u = n - horizon`. Every candidate is fitted on the first `u` observations and
    scored on observations `u .. n-1` — the held-back TAIL OF THE TRAINING SERIES,
    never a test window (the signature has no test-window argument to leak).
  * The SHIPPED path is the candidate refitted on the FULL training series; the
    truncated fit exists only to produce the selection statistic. Fit on `y[:u]`,
    score on `y[u:]`, refit on `y` — the rolling-origin discipline of
    `forecasting.backtest` at the single origin that resembles tomorrow most.
  * The seasonal factors used to compare candidates on a common scale are the
    caller's own training-window ratios (below) — no quantity dated after `n - 1`
    enters any weight, rank or parameter.

The two input series and the seasonal-factor convention
-------------------------------------------------------
`y_raw` is the series on its original scale; `y_des` is the SAME series after the
caller's own multiplicative deseasonalisation (the M4/Naive2 protocol: classical
decomposition when the seasonality test fires, identity otherwise). Pass `y_des ==
y_raw` for a series with no seasonal component. The module derives the factors it
needs as ratios `si_t = y_raw[t] / y_des[t]`:

  * holdout positions `u .. n-1`: the ratio AT the position — exact, training-window.
  * future positions `n .. n+horizon-1`: the last-cycle convention, ratio at
    `n - period + (k mod period)` — exactly the official M4 `SIout` tiling.

A position with `y_des == 0` and `y_raw != 0` has no finite factor and the whole
report is refused with FC_ERR_PARAM_RANGE (an inconsistent deseasonalisation is a
caller defect, not a forecast); `0/0` reads as factor 1.0, the correct answer for "no
seasonality at a zero observation".

The eight candidates (pool-local indices, ONE definition)
---------------------------------------------------------
  0 ses      `point.ets_ann_forecast` on `y_des`, alpha by the select module's golden
             section — the exact SES the M4 record was built on.       (x si)
  1 holt     `fitted.holt_fitted` on `y_des`.                          (x si)
  2 damped   `fitted.damped_fitted` on `y_des`.                        (x si)
  3 theta    `point.theta_forecast(theta = 2)` on `y_des`, theta-line alpha by the
             same golden section (the select module's fit, unchanged). (x si)
  4 comb     the official M4 Comb: per-step mean of ses, holt and damped ON THE RAW
             SCALE; in the pool only when all three components fitted.
  5 ets_aaa  `fitted.ets_aaa_fitted` on `y_raw` — its own seasonal state, no external
             factors; FC_ERR_PERIOD (not in the pool) when `period == 1`.
  6 snaive   `point.baseline_forecast(FC_METHOD_SEASONAL_NAIVE)` on `y_raw`;
             FC_ERR_PERIOD when `period == 1` — it would be a bit-identical duplicate
             of naive2 there, and a duplicate double-counts in every weighted mode.
  7 naive2   the M4 benchmark itself: last deseasonalised value, reseasonalised.

These indices are a POOL-LOCAL vocabulary (`pool_candidate_name`), not new
FC_METHOD ids: comb is a combination, naive2 is Naive-on-`y_des`, and holt/damped
share FC_METHOD_ETS_AAN — the append-only method-id table cannot name this pool
without minting fictions, which is exactly what `forecasting.select` refused to do.

A candidate is IN THE POOL for a series only when BOTH its truncated fit and its
full-training refit produced complete finite paths; otherwise it carries the first
failing status, `holdout_mae = -1.0` (impossible for a real MAE, so an ignored status
stays loud) and zero-filled matrix rows that `candidate_status` is the authority over.
If NO candidate survives, the report is FC_ERR_ALL_UNDEFINED with empty matrices —
a selection among nothing is not a naive fallback.

Selection versus combination (measure both — M4's standing lesson)
------------------------------------------------------------------
`pool_blend_flat` turns one report into a forecast under four modes:

  POOL_MODE_SELECT   hard argmin of holdout MAE (ties: lowest index — deterministic,
                     and the earlier candidate is deliberately the simpler one).
  POOL_MODE_INV_MAE  weights `w_i = (1/mae_i) / sum` over the `top_k` best fitted
                     candidates (`top_k = 0` = all fitted) — the package's standing
                     evidence-weighting, applied to HOLDOUT evidence; an exact fit
                     (mae <= SEL_EXACT_MAE) takes the whole weight, split equally
                     among exact fits, for the overflow reason documented in select.
  POOL_MODE_MEAN     equal weights over the `top_k` best — the trimmed pool.
  POOL_MODE_MEDIAN   per-step MEDIAN over the `top_k` best (even count: mean of the
                     two middle values). `weights` then reports MEMBERSHIP (1/k each);
                     the median is not a weighted mean and `mode` says so.

A blend over ONE member (`top_k = 1`, or a single survivor) IS that candidate and is
reported as such: `chosen_candidate` set, `is_combination = False` — a mean of one
thing is not a combination and labelling it one would misreport the arithmetic.

`pool_blend_flat` is deliberately separable from `pool_holdout_report`: the report is
the expensive pass (every candidate fitted twice) and the blend is arithmetic, so a
caller comparing modes runs one report and many blends — and a later meta-learner can
feed the SAME blend kernel weights trained on richer training-only features. The
one-call driver `pool_holdout_forecast` composes the two and validates the cheap
arguments (mode, top_k) BEFORE paying for a single fit.

Work: a report is a fixed number (16) of already-budgeted fits — each candidate driver
charges its own FIT/seasonal work budget; no multiplicative dimension is introduced.

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
golden_vectors: mojo/tests/libs/test_forecasting_pool.mojo
benchmark: benchmarks/mojo_benchmarks/bench_forecasting.mojo
docs: none
version_introduced: 0.10.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_HORIZON,
    FC_ERR_INSUFFICIENT_HISTORY,
    FC_ERR_LENGTH_MISMATCH,
    FC_ERR_METHOD,
    FC_ERR_NON_FINITE,
    FC_ERR_PARAM_RANGE,
    FC_ERR_PERIOD,
    FC_METHOD_SEASONAL_NAIVE,
    FC_OK,
    MAX_FC_HORIZON,
    fc_cells_fit,
    fc_finite,
    fc_horizon_defect,
    fc_series_defect,
    fc_status_name,
)
from forecasting.fitted import damped_fitted, ets_aaa_fitted, holt_fitted
from forecasting.point import baseline_forecast, ets_ann_forecast, theta_forecast
from forecasting.select import SEL_EXACT_MAE, _golden_ses_alpha, _theta_line

# The pool-local candidate vocabulary. Order IS the tie-break order and is part of the
# contract: on equal holdout error the EARLIER (simpler) candidate wins.
comptime POOL_CAND_SES: Int = 0
comptime POOL_CAND_HOLT: Int = 1
comptime POOL_CAND_DAMPED: Int = 2
comptime POOL_CAND_THETA: Int = 3
comptime POOL_CAND_COMB: Int = 4
comptime POOL_CAND_ETS_AAA: Int = 5
comptime POOL_CAND_SNAIVE: Int = 6
comptime POOL_CAND_NAIVE2: Int = 7
comptime POOL_N_CANDIDATES: Int = 8

# Blend modes. SELECT is a hard argmin; the other three are combinations.
comptime POOL_MODE_SELECT: Int = 0
comptime POOL_MODE_INV_MAE: Int = 1
comptime POOL_MODE_MEAN: Int = 2
comptime POOL_MODE_MEDIAN: Int = 3

# `pool_blend_flat` is generic over the candidate count so a meta-learner stage can
# reuse it; 64 bounds the allocation without constraining any real pool.
comptime POOL_MAX_CANDIDATES: Int = 64

# The minimum observations the TRUNCATED fit needs: below three, every selection
# statistic is a coin read as a measurement (forecasting.select's own floor).
comptime POOL_MIN_FIT: Int = 3


def pool_candidate_name(index: Int) -> String:
    """The pool-local vocabulary, one place. Unknown indices are loud, never blank.

    @capability pool_candidate_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if index == POOL_CAND_SES:
        return "ses"
    if index == POOL_CAND_HOLT:
        return "holt"
    if index == POOL_CAND_DAMPED:
        return "damped"
    if index == POOL_CAND_THETA:
        return "theta"
    if index == POOL_CAND_COMB:
        return "comb"
    if index == POOL_CAND_ETS_AAA:
        return "ets_aaa"
    if index == POOL_CAND_SNAIVE:
        return "snaive"
    if index == POOL_CAND_NAIVE2:
        return "naive2"
    return "unknown_candidate"


def pool_mode_name(mode: Int) -> String:
    """The blend-mode vocabulary, one place. Unknown modes are loud, never blank.

    @capability pool_mode_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if mode == POOL_MODE_SELECT:
        return "select"
    if mode == POOL_MODE_INV_MAE:
        return "inverse_mae"
    if mode == POOL_MODE_MEAN:
        return "mean"
    if mode == POOL_MODE_MEDIAN:
        return "median"
    return "unknown_mode"


@fieldwise_init
struct PoolReport(Copyable, Movable):
    """The expensive pass: every candidate fitted twice, every decision input exposed.

    `candidate_status`, `holdout_mae` are parallel to the pool vocabulary (length
    POOL_N_CANDIDATES). `holdout_values` and `full_values` are row-major
    `POOL_N_CANDIDATES x horizon` matrices ON THE RAW SCALE — `holdout_values` from the
    truncated fit (scored against the held-back training tail), `full_values` from the
    full-training refit (the only rows a shipped forecast may use). A candidate outside
    the pool carries its first failing status, `holdout_mae = -1.0`, and ZERO-FILLED
    rows: a flat matrix must stay rectangular, so `candidate_status` — not the zeros —
    is the authority for absence, and the impossible -1.0 keeps an ignored status loud.

    `si_holdout` / `si_future` are the training-window seasonal factors the module
    derived (module docstring); they are reported so the no-leakage audit can recompute
    every holdout error from this one struct. On refusal every matrix is EMPTY
    (`has_report` is the authority) but `candidate_status` still carries per-candidate
    reasons when the refusal is FC_ERR_ALL_UNDEFINED — "which fits failed" is the
    answer the caller needs then.
    """

    var status: Int
    var horizon: Int
    var n_train: Int
    var n_fit: Int
    var period: Int
    var has_report: Bool
    var candidate_status: List[Int]
    var holdout_mae: List[Float64]
    var holdout_values: List[Float64]
    var full_values: List[Float64]
    var si_holdout: List[Float64]
    var si_future: List[Float64]
    var status_name: String


@fieldwise_init
struct PoolForecast(Copyable, Movable):
    """A pool decision: the blended path, and every number that produced it.

    `values` holds steps 1..horizon on the RAW scale, EMPTY on refusal (`has_forecast`
    is the authority). `weights`, `holdout_mae` and `candidate_status` are parallel to
    the candidate indices of the report that fed the blend. `chosen_candidate` is the
    winning index when the result IS one candidate (POOL_MODE_SELECT, or any mode whose
    member set has exactly one element) and -1 with `is_combination = True` otherwise.
    For POOL_MODE_MEDIAN the weights report MEMBERSHIP (1/k for each member): a median
    is not a weighted mean, and `mode` is the field that says which arithmetic ran.
    """

    var status: Int
    var horizon: Int
    var mode: Int
    var top_k: Int
    var n_candidates: Int
    var values: List[Float64]
    var has_forecast: Bool
    var chosen_candidate: Int
    var is_combination: Bool
    var candidate_status: List[Int]
    var holdout_mae: List[Float64]
    var weights: List[Float64]
    var status_name: String


def _no_report(
    status: Int, horizon: Int, n_train: Int, n_fit: Int, period: Int,
    candidate_status: List[Int],
) -> PoolReport:
    """A refusal: empty matrices, loud MAEs, per-candidate reasons when known."""
    var maes = List[Float64]()
    for _ in range(len(candidate_status)):
        maes.append(-1.0)
    return PoolReport(
        status, horizon, n_train, n_fit, period, False,
        candidate_status.copy(), maes^, List[Float64](), List[Float64](),
        List[Float64](), List[Float64](), fc_status_name(status),
    )


def _uniform_status(status: Int) -> List[Int]:
    """The whole pool refused for one shared reason."""
    var out = List[Int]()
    for _ in range(POOL_N_CANDIDATES):
        out.append(status)
    return out^


def _no_pool(
    status: Int, horizon: Int, mode: Int, top_k: Int, n_candidates: Int
) -> PoolForecast:
    """A refusal: no path, no winner; parallel slots only when the count is trusted."""
    var stats = List[Int]()
    var maes = List[Float64]()
    var weights = List[Float64]()
    if n_candidates >= 1 and n_candidates <= POOL_MAX_CANDIDATES:
        for _ in range(n_candidates):
            stats.append(status)
            maes.append(-1.0)
            weights.append(0.0)
    return PoolForecast(
        status, horizon, mode, top_k, n_candidates, List[Float64](), False,
        -1, False, stats^, maes^, weights^, fc_status_name(status),
    )


def _si_at(y_raw: List[Float64], y_des: List[Float64], index: Int) -> List[Float64]:
    """`[factor]` at one position, or EMPTY when the deseasonalisation is inconsistent.

    `0/0` is factor 1.0 — the correct reading of "no seasonal component at a zero
    observation". A zero `y_des` under a nonzero `y_raw` has no finite factor, and a
    non-finite ratio is refused the same way: both are caller defects to surface, not
    values to invent.
    """
    var out = List[Float64]()
    var d = y_des[index]
    var r = y_raw[index]
    if d == 0.0:
        if r == 0.0:
            out.append(1.0)
            return out^
        return out^
    var f = r / d
    if not fc_finite(f):
        return out^
    out.append(f)
    return out^


def _prefix(y: List[Float64], end: Int) -> List[Float64]:
    """The first `end` observations — the truncated training window."""
    var out = List[Float64]()
    for t in range(end):
        out.append(y[t])
    return out^


@fieldwise_init
struct _PoolPaths(Copyable, Movable):
    """One fitting pass over the eight candidates: statuses + a flat 8 x horizon matrix."""

    var status: List[Int]
    var paths: List[Float64]


def _candidate_paths(
    y_raw: List[Float64], y_des: List[Float64], period: Int, horizon: Int,
    si: List[Float64],
) -> _PoolPaths:
    """Fit all eight candidates on ONE window and return raw-scale paths.

    Every path comes out of this package's existing drivers — this module fits nothing
    of its own. Deseasonalised-scale candidates are mapped to the raw scale with `si`
    (length `horizon`); ets_aaa and snaive already live on the raw scale. A refused
    candidate keeps its own status and a zero-filled row; `status` is the authority.
    """
    var status = List[Int]()
    var paths = List[Float64]()
    for _ in range(POOL_N_CANDIDATES):
        status.append(FC_ERR_ALL_UNDEFINED)
    for _ in range(POOL_N_CANDIDATES * horizon):
        paths.append(0.0)

    # ses / holt / damped / theta: deseasonalised scale, then x si.
    var a_ses = _golden_ses_alpha(y_des)
    var f_ses = ets_ann_forecast(y_des, a_ses, horizon)
    status[POOL_CAND_SES] = f_ses.status

    var f_holt = holt_fitted(y_des, horizon)
    status[POOL_CAND_HOLT] = f_holt.status

    var f_damped = damped_fitted(y_des, horizon)
    status[POOL_CAND_DAMPED] = f_damped.status

    var z = _theta_line(y_des)
    var theta_ok = len(z) == len(y_des) and len(z) >= 2
    if theta_ok:
        var a_th = _golden_ses_alpha(z)
        var f_theta = theta_forecast(y_des, 2.0, a_th, horizon)
        status[POOL_CAND_THETA] = f_theta.status
        if f_theta.status == FC_OK and f_theta.has_forecast:
            for k in range(horizon):
                paths[POOL_CAND_THETA * horizon + k] = f_theta.values[k] * si[k]
    else:
        status[POOL_CAND_THETA] = FC_ERR_NON_FINITE

    if f_ses.status == FC_OK and f_ses.has_forecast:
        for k in range(horizon):
            paths[POOL_CAND_SES * horizon + k] = f_ses.values[k] * si[k]
    if f_holt.status == FC_OK and f_holt.has_forecast:
        for k in range(horizon):
            paths[POOL_CAND_HOLT * horizon + k] = f_holt.values[k] * si[k]
    if f_damped.status == FC_OK and f_damped.has_forecast:
        for k in range(horizon):
            paths[POOL_CAND_DAMPED * horizon + k] = f_damped.values[k] * si[k]

    # comb: the official M4 combination, and only of a COMPLETE component set — a mean
    # over survivors would be a different method wearing comb's name.
    if status[POOL_CAND_SES] == FC_OK and status[POOL_CAND_HOLT] == FC_OK and status[POOL_CAND_DAMPED] == FC_OK:
        status[POOL_CAND_COMB] = FC_OK
        for k in range(horizon):
            paths[POOL_CAND_COMB * horizon + k] = (
                paths[POOL_CAND_SES * horizon + k]
                + paths[POOL_CAND_HOLT * horizon + k]
                + paths[POOL_CAND_DAMPED * horizon + k]
            ) / 3.0
    elif status[POOL_CAND_SES] != FC_OK:
        status[POOL_CAND_COMB] = status[POOL_CAND_SES]
    elif status[POOL_CAND_HOLT] != FC_OK:
        status[POOL_CAND_COMB] = status[POOL_CAND_HOLT]
    else:
        status[POOL_CAND_COMB] = status[POOL_CAND_DAMPED]

    # ets_aaa / snaive: raw scale, seasonal frequencies only.
    if period > 1:
        var f_aaa = ets_aaa_fitted(y_raw, period, horizon)
        status[POOL_CAND_ETS_AAA] = f_aaa.status
        if f_aaa.status == FC_OK and f_aaa.has_forecast:
            for k in range(horizon):
                paths[POOL_CAND_ETS_AAA * horizon + k] = f_aaa.values[k]
        var f_sn = baseline_forecast(y_raw, FC_METHOD_SEASONAL_NAIVE, horizon, period)
        status[POOL_CAND_SNAIVE] = f_sn.status
        if f_sn.status == FC_OK and f_sn.has_forecast:
            for k in range(horizon):
                paths[POOL_CAND_SNAIVE * horizon + k] = f_sn.values[k]
    else:
        status[POOL_CAND_ETS_AAA] = FC_ERR_PERIOD
        status[POOL_CAND_SNAIVE] = FC_ERR_PERIOD

    # naive2: the benchmark itself — last deseasonalised value, reseasonalised.
    var last = y_des[len(y_des) - 1]
    status[POOL_CAND_NAIVE2] = FC_OK
    for k in range(horizon):
        paths[POOL_CAND_NAIVE2 * horizon + k] = last * si[k]

    # One finiteness sweep: a path that overflowed its si mapping is a refusal, not a
    # row of infinities handed to a MAE.
    for i in range(POOL_N_CANDIDATES):
        if status[i] != FC_OK:
            continue
        var bad = False
        for k in range(horizon):
            if not fc_finite(paths[i * horizon + k]):
                bad = True
                break
        if bad:
            status[i] = FC_ERR_NON_FINITE
            for k in range(horizon):
                paths[i * horizon + k] = 0.0

    return _PoolPaths(status^, paths^)


def pool_holdout_report(
    y_raw: List[Float64], y_des: List[Float64], period: Int, horizon: Int
) -> PoolReport:
    """Fit the pool twice — on `y[:n-horizon]` and on `y` — and expose every decision input.

    The truncated fits are scored on the held-back training tail `y_raw[n-horizon ..]`
    (raw scale, so candidates on different working scales compete on one ruler); the
    full-training rows are the only ones a shipped forecast may use. See the module
    docstring for the no-leakage contract and the seasonal-factor convention.

    @capability pool_holdout_report
    complexity: O(n * period) -- 16 already-budgeted candidate fits, plus O(horizon)
    counts:
    - dim horizon [kernel_validated]
    - dim period [kernel_validated]
    @endcapability
    """
    var n = len(y_raw)
    if len(y_des) != n:
        return _no_report(
            FC_ERR_LENGTH_MISMATCH, horizon, n, 0, period,
            _uniform_status(FC_ERR_LENGTH_MISMATCH),
        )
    var defect = fc_series_defect(y_raw)
    if defect == FC_OK:
        defect = fc_series_defect(y_des)
    if defect == FC_OK:
        defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_report(defect, horizon, n, 0, period, _uniform_status(defect))
    if period < 1 or period > n:
        return _no_report(
            FC_ERR_PERIOD, horizon, n, 0, period, _uniform_status(FC_ERR_PERIOD)
        )
    var u = n - horizon
    if u < horizon or u < POOL_MIN_FIT:
        return _no_report(
            FC_ERR_INSUFFICIENT_HISTORY, horizon, n, u, period,
            _uniform_status(FC_ERR_INSUFFICIENT_HISTORY),
        )

    # Seasonal factors: training-window ratios only (module docstring).
    var si_holdout = List[Float64]()
    for k in range(horizon):
        var f = _si_at(y_raw, y_des, u + k)
        if len(f) != 1:
            return _no_report(
                FC_ERR_PARAM_RANGE, horizon, n, u, period,
                _uniform_status(FC_ERR_PARAM_RANGE),
            )
        si_holdout.append(f[0])
    var si_future = List[Float64]()
    for k in range(horizon):
        var f = _si_at(y_raw, y_des, n - period + (k % period))
        if len(f) != 1:
            return _no_report(
                FC_ERR_PARAM_RANGE, horizon, n, u, period,
                _uniform_status(FC_ERR_PARAM_RANGE),
            )
        si_future.append(f[0])

    var raw_fit = _prefix(y_raw, u)
    var des_fit = _prefix(y_des, u)
    var hold = _candidate_paths(raw_fit, des_fit, period, horizon, si_holdout)
    var full = _candidate_paths(y_raw, y_des, period, horizon, si_future)

    # A candidate is in the pool only when BOTH fits succeeded; first failing status wins.
    var candidate_status = List[Int]()
    var holdout_mae = List[Float64]()
    var any_ok = False
    for i in range(POOL_N_CANDIDATES):
        var st = hold.status[i]
        if st == FC_OK:
            st = full.status[i]
        if st != FC_OK:
            candidate_status.append(st)
            holdout_mae.append(-1.0)
            continue
        var abs_sum: Float64 = 0.0
        for k in range(horizon):
            abs_sum += fabs(y_raw[u + k] - hold.paths[i * horizon + k])
        var mae = abs_sum / Float64(horizon)
        if not fc_finite(mae):
            candidate_status.append(FC_ERR_NON_FINITE)
            holdout_mae.append(-1.0)
            continue
        candidate_status.append(FC_OK)
        holdout_mae.append(mae)
        any_ok = True

    if not any_ok:
        return _no_report(
            FC_ERR_ALL_UNDEFINED, horizon, n, u, period, candidate_status
        )

    # Zero the rows of every candidate that fell out of the pool AFTER the join, so a
    # holdout row whose full refit failed cannot be mistaken for a live candidate.
    for i in range(POOL_N_CANDIDATES):
        if candidate_status[i] == FC_OK:
            continue
        for k in range(horizon):
            hold.paths[i * horizon + k] = 0.0
            full.paths[i * horizon + k] = 0.0

    return PoolReport(
        FC_OK, horizon, n, u, period, True,
        candidate_status^, holdout_mae^, hold.paths.copy(), full.paths.copy(),
        si_holdout^, si_future^, fc_status_name(FC_OK),
    )


def _rank_fitted(holdout_mae: List[Float64], candidate_status: List[Int]) -> List[Int]:
    """Fitted candidate indices, ascending holdout MAE, ties to the LOWER index.

    Stable insertion sort over at most POOL_MAX_CANDIDATES entries: the strict `>`
    comparison never reorders equal MAEs, and the input order is ascending index, so
    the tie rule is structural rather than asserted.
    """
    var idx = List[Int]()
    for i in range(len(holdout_mae)):
        if candidate_status[i] == FC_OK:
            idx.append(i)
    for i in range(1, len(idx)):
        var key = idx[i]
        var j = i - 1
        while j >= 0 and holdout_mae[idx[j]] > holdout_mae[key]:
            idx[j + 1] = idx[j]
            j -= 1
        idx[j + 1] = key
    return idx^


def _median_of(values: List[Float64]) -> Float64:
    """The median by insertion sort of a copy; even counts average the two middles."""
    var v = values.copy()
    for i in range(1, len(v)):
        var key = v[i]
        var j = i - 1
        while j >= 0 and v[j] > key:
            v[j + 1] = v[j]
            j -= 1
        v[j + 1] = key
    var n = len(v)
    if n % 2 == 1:
        return v[n // 2]
    return 0.5 * (v[n // 2 - 1] + v[n // 2])


def _blend_defect(
    full_values: List[Float64], holdout_mae: List[Float64],
    candidate_status: List[Int], n_candidates: Int, horizon: Int,
    mode: Int, top_k: Int,
) -> Int:
    """Every precondition of `pool_blend_flat`, decided in one place BEFORE any arithmetic.

    The shape test is `fc_cells_fit` (a division): `n_candidates * horizon ==
    len(full_values)` as a plain multiply is a wrapping comparison, not a bound. A
    candidate whose status claims FC_OK but whose MAE is negative or non-finite is a
    CONTRADICTORY caller input and the whole call is refused — quietly dropping it
    would repair the caller's books instead of surfacing them.
    """
    if n_candidates < 1 or n_candidates > POOL_MAX_CANDIDATES:
        return FC_ERR_PARAM_RANGE
    if horizon <= 0:
        return FC_ERR_HORIZON
    if horizon > MAX_FC_HORIZON:
        return FC_ERR_HORIZON
    if len(holdout_mae) != n_candidates or len(candidate_status) != n_candidates:
        return FC_ERR_LENGTH_MISMATCH
    if not fc_cells_fit(n_candidates, horizon, len(full_values)):
        return FC_ERR_LENGTH_MISMATCH
    if mode < POOL_MODE_SELECT or mode > POOL_MODE_MEDIAN:
        return FC_ERR_METHOD
    if top_k < 0 or top_k > n_candidates:
        return FC_ERR_PARAM_RANGE
    for i in range(n_candidates):
        if candidate_status[i] != FC_OK:
            continue
        if not fc_finite(holdout_mae[i]) or holdout_mae[i] < 0.0:
            return FC_ERR_PARAM_RANGE
        for k in range(horizon):
            if not fc_finite(full_values[i * horizon + k]):
                return FC_ERR_NON_FINITE
    return FC_OK


def pool_blend_flat(
    full_values: List[Float64], holdout_mae: List[Float64],
    candidate_status: List[Int], n_candidates: Int, horizon: Int,
    mode: Int, top_k: Int,
) -> PoolForecast:
    """One report, one mode, one forecast — pure arithmetic over already-fitted paths.

    `full_values` is row-major `n_candidates x horizon` (a `PoolReport.full_values`, or
    any caller-built matrix over its own candidate vocabulary); `holdout_mae` and
    `candidate_status` are parallel to the rows. `top_k = 0` means "all fitted
    candidates"; POOL_MODE_SELECT reads only the ranking's head and ignores `top_k`
    beyond validation. See the module docstring for the four modes and the tie rule.

    @capability pool_blend_flat
    complexity: O(n_candidates * horizon)
    counts:
    - n_candidates * horizon == len(full_values) [kernel_validated]
    - dim top_k [kernel_validated]
    @endcapability
    """
    var defect = _blend_defect(
        full_values, holdout_mae, candidate_status, n_candidates, horizon,
        mode, top_k,
    )
    if defect != FC_OK:
        return _no_pool(defect, horizon, mode, top_k, n_candidates)

    var ranked = _rank_fitted(holdout_mae, candidate_status)
    if len(ranked) == 0:
        return _no_pool(FC_ERR_ALL_UNDEFINED, horizon, mode, top_k, n_candidates)
    var k_eff = len(ranked)
    if mode != POOL_MODE_SELECT and top_k > 0 and top_k < k_eff:
        k_eff = top_k
    if mode == POOL_MODE_SELECT:
        k_eff = 1

    # Membership weights per mode, over the k_eff best-ranked candidates.
    var weights = List[Float64]()
    for _ in range(n_candidates):
        weights.append(0.0)
    if mode == POOL_MODE_SELECT:
        weights[ranked[0]] = 1.0
    elif mode == POOL_MODE_INV_MAE:
        var n_exact = 0
        for j in range(k_eff):
            if holdout_mae[ranked[j]] <= SEL_EXACT_MAE:
                n_exact += 1
        if n_exact == 1:
            # One exact fit takes EVERYTHING: the output is that candidate's path,
            # and reporting a one-hot "combination" would mislabel the arithmetic —
            # this is the same truth as the single-member rule below.
            var w = ranked[0]
            for j in range(k_eff):
                if holdout_mae[ranked[j]] <= SEL_EXACT_MAE:
                    w = ranked[j]
            weights[w] = 1.0
            var one = List[Float64]()
            for k in range(horizon):
                one.append(full_values[w * horizon + k])
            return PoolForecast(
                FC_OK, horizon, mode, top_k, n_candidates, one^, True, w, False,
                candidate_status.copy(), holdout_mae.copy(), weights^,
                fc_status_name(FC_OK),
            )
        if n_exact > 0:
            for j in range(k_eff):
                if holdout_mae[ranked[j]] <= SEL_EXACT_MAE:
                    weights[ranked[j]] = 1.0 / Float64(n_exact)
        else:
            var total: Float64 = 0.0
            for j in range(k_eff):
                total += 1.0 / holdout_mae[ranked[j]]
            if not fc_finite(total) or total <= 0.0:
                return _no_pool(
                    FC_ERR_NON_FINITE, horizon, mode, top_k, n_candidates
                )
            for j in range(k_eff):
                weights[ranked[j]] = (1.0 / holdout_mae[ranked[j]]) / total
    else:
        for j in range(k_eff):
            weights[ranked[j]] = 1.0 / Float64(k_eff)

    # Compose the path. A single member IS that candidate, whatever the mode's name.
    var values = List[Float64]()
    if k_eff == 1 or mode == POOL_MODE_SELECT:
        var w = ranked[0]
        for k in range(horizon):
            values.append(full_values[w * horizon + k])
        return PoolForecast(
            FC_OK, horizon, mode, top_k, n_candidates, values^, True, w, False,
            candidate_status.copy(), holdout_mae.copy(), weights^,
            fc_status_name(FC_OK),
        )
    if mode == POOL_MODE_MEDIAN:
        for k in range(horizon):
            var column = List[Float64]()
            for j in range(k_eff):
                column.append(full_values[ranked[j] * horizon + k])
            values.append(_median_of(column))
    else:
        for k in range(horizon):
            var v: Float64 = 0.0
            for j in range(k_eff):
                var i = ranked[j]
                v += weights[i] * full_values[i * horizon + k]
            if not fc_finite(v):
                return _no_pool(
                    FC_ERR_NON_FINITE, horizon, mode, top_k, n_candidates
                )
            values.append(v)
    return PoolForecast(
        FC_OK, horizon, mode, top_k, n_candidates, values^, True, -1, True,
        candidate_status.copy(), holdout_mae.copy(), weights^,
        fc_status_name(FC_OK),
    )


def pool_holdout_forecast(
    y_raw: List[Float64], y_des: List[Float64], period: Int, horizon: Int,
    mode: Int, top_k: Int,
) -> PoolForecast:
    """The one-call driver: holdout report, then blend — training data in, forecast out.

    Validates the CHEAP arguments (mode, top_k) before paying for a single fit, so a
    mistyped mode cannot burn sixteen model fits to be told so. Everything else — the
    no-leakage contract, the candidate pool, the modes — is `pool_holdout_report` and
    `pool_blend_flat`, unchanged; this function adds no third behaviour.

    @capability pool_holdout_forecast
    complexity: O(n * period) -- 16 already-budgeted candidate fits, plus O(horizon)
    counts:
    - dim horizon [kernel_validated]
    - dim period [kernel_validated]
    - dim top_k [kernel_validated]
    @endcapability
    """
    if mode < POOL_MODE_SELECT or mode > POOL_MODE_MEDIAN:
        return _no_pool(FC_ERR_METHOD, horizon, mode, top_k, POOL_N_CANDIDATES)
    if top_k < 0 or top_k > POOL_N_CANDIDATES:
        return _no_pool(FC_ERR_PARAM_RANGE, horizon, mode, top_k, POOL_N_CANDIDATES)
    var report = pool_holdout_report(y_raw, y_des, period, horizon)
    if not report.has_report:
        var out = _no_pool(
            report.status, horizon, mode, top_k, POOL_N_CANDIDATES
        )
        # The per-candidate reasons survive the composition (they are the diagnosis).
        out.candidate_status = report.candidate_status.copy()
        out.holdout_mae = report.holdout_mae.copy()
        return out^
    return pool_blend_flat(
        report.full_values, report.holdout_mae, report.candidate_status,
        POOL_N_CANDIDATES, report.horizon, mode, top_k,
    )
