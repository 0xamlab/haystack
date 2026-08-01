"""
forecasting.select — per-series selection and combination over {SES, Damped, Theta}.
Zero Python imports.

What this module adds
---------------------
The package can now produce three strong point forecasts for the same series — SES
(`point.ets_ann_forecast` over the frozen `series.exponential_forecast`), the fitted
damped trend (`fitted.damped_fitted`) and classical Theta (`point.theta_forecast` over
the frozen `series._ols_fit` + SES) — and no way to CHOOSE between them per series, or
to weight them. A fixed equal-weight combination (M4's "Comb") ignores everything the
in-sample fit already learned; a fixed single method ignores that no method dominates
every series. Both facts are measured in the M4 record this package's fitted drivers
were built against.

The selection statistic is the mean absolute one-step in-sample error over t = 1..n-1,
the same quantity for every candidate:

  * SES: `e_t = y_t - s_{t-1}` under the engine recursion `s_t = a*y_t + (1-a)*s_{t-1}`,
    `s_0 = y_0` — exactly the recursion the frozen `series.exponential_forecast` runs,
    with alpha fitted here by 28-iteration golden section on one-step SSE in
    [0.01, 0.99], the like-for-like bounds of the reference SES fit.
  * Damped: the one-step errors of `fitted.damped_fitted`'s state-space recursion at its
    fitted parameters and initial state (`FittedForecast.insample_mae`, which excludes
    t = 0 for exactly this comparability).
  * Theta: `y = 0.5*Z(2) + 0.5*L` is an identity for the theta-2 line `Z = 2y - L`, so
    the one-step error is `0.5 * (z_t - s^Z_{t-1})` — half the SES error on the theta
    line, with the theta-line alpha fitted by the same golden section. `L` is the frozen
    OLS line over the WHOLE series, so the theta in-sample error sees the full-sample
    trend — stated because it is a real (mild, method-inherent) in-sample advantage, not
    an implementation accident: the forecast uses the same full-sample line.

t = 0 is excluded from every candidate's error because the state-space models emit a
t = 0 error and SES structurally cannot; comparing a 12-error mean against an 11-error
mean would bias the selection toward whichever convention a method happened to use.

Selection versus combination
----------------------------
`select_best_fitted` picks the single candidate with the smallest in-sample MAE (ties:
first of SES, Damped, Theta — deterministic, and the tie order is part of the contract).
`combine_inverse_mae_fitted` weights every candidate that fitted by `1/mae`, normalised;
an exact in-sample fit (mae 0 within 1e-300) takes the whole weight, split equally if
several candidates achieve it. Inverse-error weighting is the standard evidence-weighted
pool; the suite pins both the one-hot and the equal-split degenerate cases.

A candidate that REFUSES (a series too short for a trend model, a non-finite theta
line) is dropped with its status carried in `component_status`, and the survivors are
reweighted. If NO candidate fits, the status is FC_ERR_ALL_UNDEFINED and there is no
forecast — a selection among nothing is not a naive fallback (rule 4).

`maes` reports -1.0 for a refused candidate: impossible for a real mean absolute error,
so an ignored status still reads as a loud defect rather than as "this method fitted
perfectly" (0.0 would claim exactly that).

Status codes 300-319 via `forecasting.contract`; no table here. Method ids in the
result are the package's ONE vocabulary (`FC_METHOD_ETS_ANN`, `FC_METHOD_ETS_AAN`,
`FC_METHOD_THETA`); no new ids are minted — a combination is reported as its components
and weights, `chosen_method_id = -1` with `is_combination = True`, because a weighted
pool of three methods IS NOT a fourth method and numbering it as one would put a
fiction in the append-only id table.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_forecasting_select.mojo
benchmark: benchmarks/mojo_benchmarks/bench_forecasting.mojo
docs: none
version_introduced: 0.10.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from series import _ols_fit

from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_INSUFFICIENT_HISTORY,
    FC_ERR_NON_FINITE,
    FC_METHOD_ETS_AAN,
    FC_METHOD_ETS_ANN,
    FC_METHOD_THETA,
    FC_OK,
    fc_finite,
    fc_horizon_defect,
    fc_series_defect,
    fc_status_name,
)
from forecasting.fitted import damped_fitted
from forecasting.point import ets_ann_forecast, theta_forecast

# The reference SES bounds (SimpleExponentialSmoothingOptimized's (0.01, 0.99)), and the
# golden-section iteration count the prior harness used: 28 halvings of a 0.98-wide
# bracket end below 2e-6, far inside the flat region of any one-step SSE curve here.
comptime SEL_ALPHA_LO: Float64 = 0.01
comptime SEL_ALPHA_HI: Float64 = 0.99
comptime SEL_GOLDEN_ITERS: Int = 28
comptime SEL_GOLDEN_RATIO: Float64 = 0.6180339887498949  # (sqrt(5) - 1) / 2

# Below this an in-sample MAE is an exact fit: 1/mae would overflow toward inf and the
# normalised weights would be poisoned, so exact fits take the whole weight instead.
comptime SEL_EXACT_MAE: Float64 = 1.0e-300

# The three candidate method ids, in tie-break order. ONE definition, used by both
# drivers, so the reported `method_ids` and the tie order cannot drift apart.
fn _sel_method_ids() -> List[Int]:
    var out = List[Int]()
    out.append(FC_METHOD_ETS_ANN)
    out.append(FC_METHOD_ETS_AAN)
    out.append(FC_METHOD_THETA)
    return out^


@fieldwise_init
struct SelectedForecast(Copyable, Movable):
    """A per-series selection or combination over {SES, Damped, Theta}.

    `values` holds steps 1..horizon, EMPTY on refusal (`has_forecast` is the authority).
    `method_ids` is always the three candidates in tie-break order; `component_status`,
    `maes` and `weights` are parallel to it. A refused candidate carries its own status,
    `mae = -1.0` (impossible for a real MAE — never 0.0, which would claim an exact fit)
    and weight 0.0. `chosen_method_id` is the winning id for `select_best_fitted` and
    -1 (with `is_combination = True`) for a combination, which is reported as its
    components rather than being minted a method id of its own.
    """

    var status: Int
    var horizon: Int
    var n_train: Int
    var values: List[Float64]
    var has_forecast: Bool
    var chosen_method_id: Int
    var is_combination: Bool
    var method_ids: List[Int]
    var component_status: List[Int]
    var maes: List[Float64]
    var weights: List[Float64]
    var status_name: String


fn _no_selection(status: Int, horizon: Int, n_train: Int) -> SelectedForecast:
    """A refusal: no path, no winner, every candidate marked absent."""
    var maes = List[Float64]()
    var weights = List[Float64]()
    var stats = List[Int]()
    for _ in range(3):
        maes.append(-1.0)
        weights.append(0.0)
        stats.append(status)
    return SelectedForecast(
        status, horizon, n_train, List[Float64](), False, -1, False,
        _sel_method_ids(), stats^, maes^, weights^, fc_status_name(status),
    )


fn _ses_sse_mae(y: List[Float64], alpha: Float64) -> List[Float64]:
    """`[sse, mae]` of one-step errors under the engine SES recursion, `s_0 = y[0]`.

    The recursion is `series.exponential_forecast`'s own (`s = a*y + (1-a)*s`), replayed
    for its ERRORS, which the frozen kernel does not expose. Errors run t = 1..n-1; the
    caller guarantees n >= 2. Empty on a non-finite accumulation.
    """
    var out = List[Float64]()
    var s = y[0]
    var sse: Float64 = 0.0
    var sae: Float64 = 0.0
    for t in range(1, len(y)):
        var e = y[t] - s
        sse += e * e
        sae += fabs(e)
        s = alpha * y[t] + (1.0 - alpha) * s
    if not fc_finite(sse) or not fc_finite(sae):
        return out^
    out.append(sse)
    out.append(sae / Float64(len(y) - 1))
    return out^


fn _golden_ses_alpha(y: List[Float64]) -> Float64:
    """Golden-section argmin of the SES one-step SSE over [SEL_ALPHA_LO, SEL_ALPHA_HI].

    28 iterations, deterministic, no derivative. A non-finite SSE at a probe (magnitudes
    overflowing the recursion) is treated as +inf so the bracket walks away from it; if
    both probes are non-finite the bracket midpoint is still returned and the CALLER's
    subsequent pass reports the non-finite fit — this helper never invents a status.
    """
    var lo = SEL_ALPHA_LO
    var hi = SEL_ALPHA_HI
    for _ in range(SEL_GOLDEN_ITERS):
        var x1 = hi - SEL_GOLDEN_RATIO * (hi - lo)
        var x2 = lo + SEL_GOLDEN_RATIO * (hi - lo)
        var p1 = _ses_sse_mae(y, x1)
        var p2 = _ses_sse_mae(y, x2)
        var f1 = p1[0] if len(p1) == 2 else 1.0 / 0.0
        var f2 = p2[0] if len(p2) == 2 else 1.0 / 0.0
        if f1 < f2:
            hi = x2
        else:
            lo = x1
    return 0.5 * (lo + hi)


fn _theta_line(y: List[Float64]) -> List[Float64]:
    """The theta-2 line `Z_t = 2*y_t - (a + b*t)` over the frozen OLS fit, or empty."""
    var out = List[Float64]()
    var fit = _ols_fit(y)
    if len(fit) != 2 or not fc_finite(fit[0]) or not fc_finite(fit[1]):
        return out^
    for t in range(len(y)):
        var z = 2.0 * y[t] - (fit[0] + fit[1] * Float64(t))
        if not fc_finite(z):
            return List[Float64]()
        out.append(z)
    return out^


@fieldwise_init
struct _Candidates(Copyable, Movable):
    """The three fitted candidates: statuses, in-sample MAEs, forecast paths."""

    var status: List[Int]
    var maes: List[Float64]
    var paths: List[List[Float64]]


fn _fit_candidates(y: List[Float64], horizon: Int) -> _Candidates:
    """Fit SES, Damped and Theta; a refusal is carried per-candidate, never invented.

    Every forecast path comes out of this package's existing drivers
    (`point.ets_ann_forecast`, `fitted.damped_fitted`, `point.theta_forecast`) — this
    module fits selection weights, not new recursions. The theta in-sample errors are
    half the SES errors on the theta line, by the decomposition identity in the module
    docstring, so no theta-specific error pass exists to drift from the forecast.
    """
    var status = List[Int]()
    var maes = List[Float64]()
    var paths = List[List[Float64]]()

    # SES.
    var a_ses = _golden_ses_alpha(y)
    var ses_pass = _ses_sse_mae(y, a_ses)
    var ses_fc = ets_ann_forecast(y, a_ses, horizon)
    if len(ses_pass) == 2 and ses_fc.has_forecast:
        status.append(FC_OK)
        maes.append(ses_pass[1])
        paths.append(ses_fc.values.copy())
    else:
        status.append(ses_fc.status if not ses_fc.has_forecast else FC_ERR_NON_FINITE)
        maes.append(-1.0)
        paths.append(List[Float64]())

    # Damped, fitted.
    var dmp = damped_fitted(y, horizon)
    if dmp.has_forecast:
        status.append(FC_OK)
        maes.append(dmp.insample_mae)
        paths.append(dmp.values.copy())
    else:
        status.append(dmp.status)
        maes.append(-1.0)
        paths.append(List[Float64]())

    # Theta.
    var z = _theta_line(y)
    if len(z) == len(y) and len(z) >= 2:
        var a_th = _golden_ses_alpha(z)
        var z_pass = _ses_sse_mae(z, a_th)
        var th_fc = theta_forecast(y, 2.0, a_th, horizon)
        if len(z_pass) == 2 and th_fc.has_forecast:
            status.append(FC_OK)
            maes.append(0.5 * z_pass[1])
            paths.append(th_fc.values.copy())
        else:
            status.append(th_fc.status if not th_fc.has_forecast else FC_ERR_NON_FINITE)
            maes.append(-1.0)
            paths.append(List[Float64]())
    else:
        status.append(FC_ERR_NON_FINITE)
        maes.append(-1.0)
        paths.append(List[Float64]())

    return _Candidates(status^, maes^, paths^)


fn _selection_weights(maes: List[Float64], status: List[Int]) -> List[Float64]:
    """Inverse-MAE weights over the fitted candidates, normalised to sum 1.

    An exact fit (mae <= SEL_EXACT_MAE) takes the whole weight — split equally when
    several candidates achieve it — because `1/mae` past that point overflows and a
    poisoned normalisation would hand every candidate a NaN weight. Refused candidates
    weigh 0. Returns empty when no candidate fitted, which the caller refuses loudly.
    """
    var out = List[Float64]()
    var n_exact = 0
    var any_ok = False
    for i in range(len(maes)):
        if status[i] == FC_OK:
            any_ok = True
            if maes[i] <= SEL_EXACT_MAE:
                n_exact += 1
    if not any_ok:
        return out^
    if n_exact > 0:
        for i in range(len(maes)):
            if status[i] == FC_OK and maes[i] <= SEL_EXACT_MAE:
                out.append(1.0 / Float64(n_exact))
            else:
                out.append(0.0)
        return out^
    var total: Float64 = 0.0
    for i in range(len(maes)):
        if status[i] == FC_OK:
            total += 1.0 / maes[i]
    if not fc_finite(total) or total <= 0.0:
        return List[Float64]()
    for i in range(len(maes)):
        if status[i] == FC_OK:
            out.append((1.0 / maes[i]) / total)
        else:
            out.append(0.0)
    return out^


fn select_best_fitted(y: List[Float64], horizon: Int) -> SelectedForecast:
    """The single candidate with the smallest in-sample one-step MAE, per series.

    Ties break to the FIRST of (SES, Damped, Theta) — deterministic, and biased
    deliberately toward the simpler model: a tie in the selection statistic is not
    evidence for the more flexible candidate. Requires n >= 3 so every candidate's MAE
    averages at least two errors; a two-observation "selection" would be a coin read as
    a measurement.

    @capability select_best_fitted
    complexity: O(n) -- three bounded fits, each O(n) passes, plus O(horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_selection(defect, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_selection(defect, horizon, n)
    if n < 3:
        return _no_selection(FC_ERR_INSUFFICIENT_HISTORY, horizon, n)
    var cand = _fit_candidates(y, horizon)
    var best = -1
    for i in range(3):
        if cand.status[i] != FC_OK:
            continue
        if best < 0 or cand.maes[i] < cand.maes[best]:
            best = i
    if best < 0:
        return _no_selection(FC_ERR_ALL_UNDEFINED, horizon, n)
    var weights = List[Float64]()
    for i in range(3):
        weights.append(1.0 if i == best else 0.0)
    var ids = _sel_method_ids()
    var chosen = ids[best]
    return SelectedForecast(
        FC_OK, horizon, n, cand.paths[best].copy(), True, chosen, False,
        ids^, cand.status.copy(), cand.maes.copy(), weights^, fc_status_name(FC_OK),
    )


fn combine_inverse_mae_fitted(y: List[Float64], horizon: Int) -> SelectedForecast:
    """The inverse-MAE weighted combination of every candidate that fitted.

    `f_h = sum_i w_i * f_i,h` with `w_i = (1/mae_i) / sum_j (1/mae_j)` over the fitted
    candidates — evidence-weighted rather than equal-weighted, which is the difference
    between this and the fixed Comb benchmark. Degenerate cases are pinned in the suite:
    an exact fit takes the whole weight; a refused candidate is reweighted away; no
    fitted candidate at all is FC_ERR_ALL_UNDEFINED with no forecast.

    @capability combine_inverse_mae_fitted
    complexity: O(n) -- three bounded fits, each O(n) passes, plus O(horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect != FC_OK:
        return _no_selection(defect, horizon, n)
    defect = fc_horizon_defect(n, horizon)
    if defect != FC_OK:
        return _no_selection(defect, horizon, n)
    if n < 3:
        return _no_selection(FC_ERR_INSUFFICIENT_HISTORY, horizon, n)
    var cand = _fit_candidates(y, horizon)
    var weights = _selection_weights(cand.maes, cand.status)
    if len(weights) != 3:
        return _no_selection(FC_ERR_ALL_UNDEFINED, horizon, n)
    var values = List[Float64]()
    for h in range(horizon):
        var v: Float64 = 0.0
        for i in range(3):
            if weights[i] > 0.0:
                v += weights[i] * cand.paths[i][h]
        if not fc_finite(v):
            return _no_selection(FC_ERR_NON_FINITE, horizon, n)
        values.append(v)
    return SelectedForecast(
        FC_OK, horizon, n, values^, True, -1, True,
        _sel_method_ids(), cand.status.copy(), cand.maes.copy(), weights^, fc_status_name(FC_OK),
    )
