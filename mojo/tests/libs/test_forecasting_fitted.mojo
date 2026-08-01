"""test_forecasting_fitted.mojo — known-value tests for the fitted Holt-family drivers.

Hand-written. Every expected number below was either derived on paper (the 2x2 solves —
each derivation is in the comment beside its assertion) or computed with the state-space
replica that was validated to 1e-10 against statsforecast 2.1.1 on all 100,000 M4 series
before this module existed; the replica command is cited where used.

The assertion that bites, and why
---------------------------------
The frozen `timeseries_stats.holt_linear` initialises `b0 = y[1] - y[0]` unfitted. The
corrupted-first-difference series below (`y[0] = 107`, `y[t] = 100 + 3t` after it) makes
that ONE noisy difference equal -4 while the true trend is +3. At the small-beta regime
the M4 fit actually selects (beta ~ 1e-4), the frozen-init driver carries -4 across the
whole horizon and forecasts a DECLINE (102.05 at h = 6, truth 151); the fitted drivers
recover the true trend (+2.73) and land within 1.7% (148.51). Both facts are asserted,
plus the differential (the frozen miss is more than 10x the fitted miss), plus the same
recovery through the closed-form solver at FIXED parameters (b0 = +2.61 where the frozen
init hard-codes -4). Anti-vacuity was demonstrated by replacing the fitted initial state
with the frozen one and watching these assertions fail; the transcript of that run is in
the PR that introduced this file.

Exactness is asserted where the arithmetic is exactly representable: the two hand-derived
solves and the seasonal reproduction are all dyadic rationals, so `==` is used there, not
a tolerance. For the seasonal ramp the exactness now runs THROUGH the joint fit: the
decomposition + OLS starting state is the perfect fit (pa = [1, -1, 2, -2], l0 = -2,
b0 = 2, all dyadic), every in-sample error is exactly zero, so the recursion transports
the states untouched and the optimizer cannot leave the minimum it started on.

The seasonal biting assertion (4b) mirrors the corrupted-difference one: a seasonal
amplitude that GROWS makes any static seasonal index wrong on the next cycle by the
amplitude drift, while the joint fit tracks it through the fitted seasonal state
(expected values from the replica validated against statsforecast 2.1.1 on this exact
series to 1e-11: joint worst error 0.262, static composition worst 1.51, fitted gamma
0.9499). Anti-vacuity for the new assertions was demonstrated the same way as the
original: pointing assertion 4b at the static-index composition fails it, and reporting
gamma = 0 from the seasonal driver fails the audit-trail check.
"""
from std.math import abs as fabs

from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_EMPTY_SERIES,
    FC_ERR_HORIZON,
    FC_ERR_INSUFFICIENT_HISTORY,
    FC_ERR_NON_FINITE,
    FC_ERR_PARAM_RANGE,
    FC_ERR_PERIOD,
    FC_ERR_WORK_BUDGET,
    FC_METHOD_ETS_AAA,
    FC_METHOD_ETS_AAN,
    FC_OK,
)
from forecasting.fitted import (
    FIT_MAX_WORK,
    FIT_NM_MAX_EVALS,
    FIT_THETA_HI,
    DotmFit,
    FittedForecast,
    InitSolve,
    ThetaFit,
    _dotm_forecast_path,
    _dotm_pass,
    damped_fitted,
    dotm_fitted,
    ets_aaa_fitted,
    fitted_init_solve,
    holt_fitted,
    theta_fitted,
    theta_fitted_at,
)
from forecasting.point import ets_aaa_forecast, ets_aan_forecast, theta_forecast
from forecasting.select import _golden_ses_alpha, _theta_line


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _corrupted() -> List[Float64]:
    """y[0] = 107 (one corrupted first difference: y[1]-y[0] = -4), then y_t = 100+3t."""
    var y = List[Float64]()
    y.append(107.0)
    for t in range(1, 12):
        y.append(100.0 + 3.0 * Float64(t))
    return y^


fn _line() -> List[Float64]:
    """y_t = 2 + 3t, twelve points, every value a small integer."""
    var y = List[Float64]()
    for t in range(12):
        y.append(2.0 + 3.0 * Float64(t))
    return y^


fn main():
    var passed = 0
    var failed = 0
    print("\n[forecasting.fitted] hand-written known-value suite")

    # ══ 1. the 2x2 solve, derived on paper, asserted EXACT ═══════════════════════════
    #
    # y = [1, 2], alpha = beta = 0.5, phi = 1. One pass of the three recursions:
    #   t=0: (fq, fr) = (1, 1), res = 1;  updates: q -> (0.5, -0.5), r -> (0.5, 0.5),
    #        p -> (0.5, 0.5)
    #   t=1: (fq, fr) = (0, 1), fp = 1, res = 1
    # Sums: Sqq = 1, Sqr = 1, Srr = 2, Sqy = 1, Sry = 2, det = 2 - 1 = 1.
    # l0 = (1*2 - 2*1)/1 = 0;  b0 = (1*2 - 1*1)/1 = 1. Check: state (0,1) forecasts
    # y_0 = 0+1 = 1 (e=0) then l=1,b=1 forecasts y_1 = 2 (e=0), so SSE = 0. All values
    # dyadic, so the comparison is `==`.
    var s1 = fitted_init_solve(_floats(1.0, 2.0), 0.5, 0.5, 1.0)
    if (
        s1.status == FC_OK and s1.solved and s1.has_state
        and s1.l0 == 0.0 and s1.b0 == 1.0 and s1.sse == 0.0
    ):
        passed += 1
        print("  ✅ 2x2 solve on [1,2]: (l0, b0) = (0, 1) exactly, SSE exactly 0")
    else:
        failed += 1
        print("  ❌ hand-derived solve wrong:", s1.l0, s1.b0, s1.sse)

    # y = [1, 1], alpha = beta = phi = 0.5 — a CONSTANT series is not singular: the
    # normal matrix depends only on (alpha, beta, phi, n), never on y. By the same
    # arithmetic (all powers of two): Sqq = 1.0625, Sqr = 0.59375, Srr = 0.390625,
    # Sqy = 1.0625, Sry = 0.59375, det = 0.0625; l0 = 1, b0 = 0, SSE = 0.
    var s2 = fitted_init_solve(_floats(1.0, 1.0), 0.5, 0.5, 0.5)
    if s2.status == FC_OK and s2.solved and s2.l0 == 1.0 and s2.b0 == 0.0 and s2.sse == 0.0:
        passed += 1
        print("  ✅ constant series solves to (c, 0) exactly — not singular")
    else:
        failed += 1
        print("  ❌ constant-series solve wrong:", s2.l0, s2.b0)

    # ONE observation is singular in exact arithmetic: the single design row is
    # (1, phi), so det = 1*phi^2 - phi^2 = 0 exactly. The fallback is REPORTED:
    # solved = False, l0 = y[0], b0 = 0, status names the defect.
    var s3 = fitted_init_solve(_floats(7.0), 0.5, 0.5, 1.0)
    if (
        s3.status == FC_ERR_INSUFFICIENT_HISTORY and not s3.solved and s3.has_state
        and s3.l0 == 7.0 and s3.b0 == 0.0 and s3.det == 0.0
    ):
        passed += 1
        print("  ✅ one observation: det exactly 0, fallback (y0, 0) REPORTED not silent")
    else:
        failed += 1
        print("  ❌ singular system not reported:", s3.status, s3.solved)

    # ══ 2. THE BITING ASSERTION: one corrupted first difference ════════════════════
    var yc = _corrupted()
    var truth6: Float64 = 151.0  # 100 + 3*17

    # The frozen-init driver at the small-beta regime the M4 fit selects: its
    # b0 = y[1] - y[0] = -4 never updates (beta = 1e-4), so it extrapolates the
    # corruption. Replica values: trend -3.9937, f_6 = 102.05.
    var fro = ets_aan_forecast(yc, 0.5, 0.0001, 1.0, 6)
    var fro_ok = (
        fro.has_forecast and fro.trend < 0.0 and fro.values[5] < 110.0
    )

    # The fitted driver recovers the true trend from the same record. Replica values
    # (validated to 1e-10 against statsforecast on all 100,000 M4 series):
    # trend +2.7322, f_6 = 148.51 -> 1.7% off truth against the frozen driver's 32%.
    var hf = holt_fitted(yc, 6)
    var hf_ok = (
        hf.status == FC_OK and hf.has_forecast
        and hf.trend > 2.0 and hf.trend < 3.5
        and fabs(hf.values[5] - truth6) < 0.05 * truth6
    )
    var differential = (
        fro_ok and hf_ok
        and fabs(fro.values[5] - truth6) > 10.0 * fabs(hf.values[5] - truth6)
    )
    if differential:
        passed += 1
        print("  ✅ corrupted first difference: fitted recovers +3, frozen extrapolates -4,")
        print("     and the frozen miss is more than 10x the fitted miss at h = 6")
    else:
        failed += 1
        print("  ❌ the defect this module closes is not closed:",
              hf.trend, hf.values[5], fro.values[5])

    # The damped driver must not extrapolate the corruption either (replica: trend
    # +2.4533, f_6 = 145.26, 3.9% off truth).
    var dfc = damped_fitted(yc, 6)
    if (
        dfc.status == FC_OK and dfc.trend > 2.0
        and fabs(dfc.values[5] - truth6) < 0.06 * truth6
    ):
        passed += 1
        print("  ✅ damped_fitted also recovers the trend (within 6% at h = 6)")
    else:
        failed += 1
        print("  ❌ damped_fitted extrapolated the corruption:", dfc.trend, dfc.values[5])

    # The SAME recovery through the closed-form solver at FIXED parameters — this is
    # the assertion that isolates the initial state from the parameter fit. At
    # (alpha, beta, phi) = (0.5, 1e-4, 1) the exact solve gives b0 = +2.6115 (replica);
    # the frozen init hard-codes b0 = -4 on this series. Anti-vacuity: with the solve
    # replaced by the frozen init this assertion fails.
    var sc = fitted_init_solve(yc, 0.5, 0.0001, 1.0)
    if sc.status == FC_OK and sc.solved and sc.b0 > 2.0 and sc.b0 < 3.5:
        passed += 1
        print("  ✅ exact solve at fixed (0.5, 1e-4, 1): b0 = +2.61 where frozen init is -4")
    else:
        failed += 1
        print("  ❌ solve did not recover the trend:", sc.b0)

    # ══ 3. a perfect line is recovered ═══════════════════════════════════════════════
    var yl = _line()
    # The solve at any admissible parameters: state (a-b, b) = (-1, 3) reproduces the
    # line exactly (every forecast lands on the next point, e_t = 0 for all t), so the
    # normal system is consistent and its solution is exact — dyadic in, dyadic out.
    var sl = fitted_init_solve(yl, 0.5, 0.5, 1.0)
    if sl.solved and sl.l0 == -1.0 and sl.b0 == 3.0 and sl.sse == 0.0:
        passed += 1
        print("  ✅ solve on y = 2+3t recovers (l0, b0) = (-1, 3) exactly, SSE exactly 0")
    else:
        failed += 1
        print("  ❌ line solve wrong:", sl.l0, sl.b0, sl.sse)

    var hl = holt_fitted(yl, 6)
    var line_exact = hl.status == FC_OK
    for k in range(6):
        var want = 2.0 + 3.0 * Float64(12 + k)
        if fabs(hl.values[k] - want) > 1.0e-9:
            line_exact = False
    if line_exact:
        passed += 1
        print("  ✅ holt_fitted continues a perfect line (38, 41, ..., 53)")
    else:
        failed += 1
        print("  ❌ holt_fitted bent a straight line")

    # Damped on a line: less damping always fits better, so the fit must sit at the
    # phi ceiling (0.98 — a box CLAMP, so equality is exact), and the damped path lies
    # strictly below the true continuation while still rising.
    var dl = damped_fitted(yl, 6)
    if (
        dl.status == FC_OK and dl.phi == 0.98
        and dl.values[0] > 36.0 and dl.values[5] > dl.values[0]
        and dl.values[5] < 53.0
    ):
        passed += 1
        print("  ✅ damped_fitted on a line: phi at the 0.98 ceiling, path damped below it")
    else:
        failed += 1
        print("  ❌ damped line behaviour wrong:", dl.phi, dl.values[5])

    # ══ 4. seasonal reproduction, EXACT ════════════════════════════════════════════
    # y_t = 2t + s_{t mod 4}, s = [1, -1, 2, -2] over 12 points. The joint seasonal fit
    # starts at the decomposition + OLS state, which on this series IS the perfect fit
    # (every value dyadic: pa = [1, -1, 2, -2], l0 = -2, b0 = 2), every in-sample error
    # is exactly 0, so the states pass through the recursion unchanged and the next four
    # true values 25, 25, 30, 28 come back EXACTLY — dyadic arithmetic end to end. The
    # in-sample SSE of the reported fit is asserted at the same time: only a
    # numerically perfect fit forecasts this series exactly.
    var ys = List[Float64]()
    var s_idx = _floats(1.0, -1.0, 2.0, -2.0)
    for t in range(12):
        ys.append(2.0 * Float64(t) + s_idx[t % 4])
    var af = ets_aaa_fitted(ys, 4, 4)
    if (
        af.status == FC_OK
        and af.values[0] == 25.0 and af.values[1] == 25.0
        and af.values[2] == 30.0 and af.values[3] == 28.0
        and af.sse < 1.0e-12
    ):
        passed += 1
        print("  ✅ ets_aaa_fitted reproduces 25, 25, 30, 28 EXACTLY on the seasonal ramp")
    else:
        failed += 1
        print("  ❌ seasonal reproduction wrong")

    # ══ 4b. THE SEASONAL BITING ASSERTION: evolving seasonal amplitude ═══════════════
    # y = 10 + amp_c * base[t mod 4], base = [1, -1, 0.5, -0.5], amplitude growing
    # 1.00, 1.25, .., 3.75 over 12 cycles; the next (13th) cycle's true amplitude is
    # 4.0. STATIC decomposition indices can only carry the average amplitude (~2.4), so
    # the frozen-index driver misses the last cycle by ~1.5 at every phase no matter
    # its smoothing weights; the joint fit tracks the growth through the fitted
    # seasonal state (replica gamma 0.9499, = statsforecast 2.1.1 on this series to
    # 1e-11) and lands within 0.27 everywhere. Asserted on the WORST step, where the
    # static index cannot hide behind a lucky phase: joint < 0.5, frozen > 1.0, at
    # least a 3x differential, and the fitted gamma is reported LARGE — the capability
    # the static composition lacks is visible in the audit trail, not just in the miss.
    var ye = List[Float64]()
    var base = _floats(1.0, -1.0, 0.5, -0.5)
    for c in range(12):
        for j in range(4):
            ye.append(10.0 + (1.0 + 0.25 * Float64(c)) * base[j])
    var truth = _floats(14.0, 6.0, 12.0, 8.0)  # 10 + 4.0 * base
    var ae = ets_aaa_fitted(ye, 4, 4)
    var fe = ets_aaa_forecast(ye, 0.2, 0.05, 1.0, 4, 4)
    var evolving_ok = ae.status == FC_OK and fe.has_forecast and ae.gamma > 0.5
    var worst_joint: Float64 = 0.0
    var worst_frozen: Float64 = 0.0
    for k in range(4):
        worst_joint = max(worst_joint, fabs(ae.values[k] - truth[k]))
        worst_frozen = max(worst_frozen, fabs(fe.values[k] - truth[k]))
    if worst_frozen < 3.0 * worst_joint:
        evolving_ok = False
    if evolving_ok and worst_joint < 0.5 and worst_frozen > 1.0:
        passed += 1
        print("  ✅ evolving seasonality: joint fit within 0.5 (gamma fitted large),")
        print("     static-index composition misses by > 1.0 — 3x differential per step")
    else:
        failed += 1
        print("  ❌ the seasonal joint fit does not track evolving amplitude:",
              worst_joint, worst_frozen, ae.gamma)

    # ══ 5. bit-reproducibility: same input, same fit, twice ═══════════════════════════
    var r1 = holt_fitted(yc, 6)
    var r2 = holt_fitted(yc, 6)
    var same = (
        r1.alpha == r2.alpha and r1.beta == r2.beta
        and r1.l0 == r2.l0 and r1.b0 == r2.b0 and r1.sse == r2.sse
    )
    for k in range(6):
        if r1.values[k] != r2.values[k]:
            same = False
    var a1 = ets_aaa_fitted(ye, 4, 4)
    var a2 = ets_aaa_fitted(ye, 4, 4)
    if a1.alpha != a2.alpha or a1.gamma != a2.gamma or a1.sse != a2.sse:
        same = False
    for k in range(4):
        if a1.values[k] != a2.values[k]:
            same = False
    if same:
        passed += 1
        print("  ✅ bit-reproducible: two identical calls agree to the bit (AAN and AAA)")
    else:
        failed += 1
        print("  ❌ the fit is not deterministic")

    # ══ 6. refusals, per rule 4: absent, never a padded stand-in ══════════════════════
    var e_empty = holt_fitted(List[Float64](), 3)
    var e_h = holt_fitted(yl, 20)
    var e_one = holt_fitted(_floats(4.0), 1)
    var y8 = List[Float64]()
    for t in range(8):
        y8.append(yl[t])
    var e_per = ets_aaa_fitted(y8, 5, 3)  # 8 < 5 + 2*(5//2) = 9: one interior cycle
    if (
        e_empty.status == FC_ERR_EMPTY_SERIES and not e_empty.has_forecast
        and len(e_empty.values) == 0
        and e_h.status == FC_ERR_HORIZON and not e_h.has_forecast
        and e_one.status == FC_ERR_INSUFFICIENT_HISTORY
        and e_per.status == FC_ERR_PERIOD and len(e_per.values) == 0
    ):
        passed += 1
        print("  ✅ empty, horizon > n, n = 1 and an unsupportable period are refusals")
    else:
        failed += 1
        print("  ❌ a refusal leaked a result:", e_empty.status, e_h.status,
              e_one.status, e_per.status)

    # Solver validation: a smoothing weight of 0, a NaN, an out-of-range phi.
    var nan = 0.0 / 0.0
    if (
        fitted_init_solve(yl, 0.0, 0.5, 1.0).status == FC_ERR_PARAM_RANGE
        and fitted_init_solve(yl, 0.5, 0.5, 1.5).status == FC_ERR_PARAM_RANGE
        and fitted_init_solve(yl, nan, 0.5, 1.0).status == FC_ERR_NON_FINITE
        and not fitted_init_solve(yl, 0.0, 0.5, 1.0).has_state
    ):
        passed += 1
        print("  ✅ solver refuses alpha = 0, phi > 1 and NaN, with no state reported")
    else:
        failed += 1
        print("  ❌ solver validation leaked a state")

    # A series whose magnitudes overflow the recursion: EVERY Nelder-Mead vertex is
    # non-finite, so there is no fit at all — FC_ERR_ALL_UNDEFINED, empty path, no
    # parameter estimates presented as if they meant something.
    var yo = List[Float64]()
    for t in range(8):
        yo.append(1.0e308 if t % 2 == 0 else -1.0e308)
    var eo = holt_fitted(yo, 3)
    if eo.status == FC_ERR_ALL_UNDEFINED and not eo.has_forecast and len(eo.values) == 0:
        passed += 1
        print("  ✅ overflow-scale series: every candidate undefined, reported as exactly that")
    else:
        failed += 1
        print("  ❌ an unfittable series returned something:", eo.status)

    # The work budget: FIT_MAX_WORK / FIT_NM_MAX_EVALS observations is the ceiling
    # (536,870 at the shipped constants); one past it is a refusal BEFORE any pass runs.
    var cap = FIT_MAX_WORK // FIT_NM_MAX_EVALS
    var ybig = List[Float64](capacity=cap + 1)
    for _ in range(cap + 1):
        ybig.append(1.0)
    var ew = holt_fitted(ybig, 1)
    if ew.status == FC_ERR_WORK_BUDGET and not ew.has_forecast:
        passed += 1
        print("  ✅ the NM work budget refuses n past FIT_MAX_WORK / FIT_NM_MAX_EVALS")
    else:
        failed += 1
        print("  ❌ the work budget did not bite:", ew.status)

    # ══ 7. the audit trail: init provenance is reported on success ════════════════════
    # The seasonal driver's reserved combination: init_status FC_OK with
    # init_solved = False (jointly fitted state, no 2x2 audit), n_params = m + 4
    # (alpha, beta, gamma, l0, b0, m - 1 free seasonal states), gamma reported for the
    # seasonal fit and exactly 0.0 for the non-seasonal drivers — the reference
    # recursion's own value for a seasonless model, so the field can never be read as
    # a fitted seasonal weight where none was fitted.
    if (
        hf.init_status == FC_OK and hf.init_solved
        and hf.method_id == FC_METHOD_ETS_AAN
        and af.method_id == FC_METHOD_ETS_AAA
        and hf.n_params == 4 and dfc.n_params == 5
        and af.n_params == 8
        and af.init_status == FC_OK and not af.init_solved
        and hf.gamma == 0.0 and dfc.gamma == 0.0
    ):
        passed += 1
        print("  ✅ init provenance, method ids, parameter counts and gamma are reported")
    else:
        failed += 1
        print("  ❌ audit fields wrong:", hf.init_status, hf.n_params, dfc.n_params,
              af.n_params, af.init_solved, hf.gamma)

    # ══ 8. optimized theta: the fitted theta and its anchors ══════════════════════════
    #
    # 8a. THE ANCHOR: theta forced to 2.0 IS the shipped classical-Theta pipeline,
    # bit-for-bit. `forecasting.select` carries the reference alpha fit for the theta-2
    # line (the same golden section the M4 Theta row's parameters came out of);
    # `theta_fitted_at(y, 2.0, h)` must reproduce that alpha to the LAST BIT and the
    # forecast must equal `theta_forecast` at that alpha to the last bit. This is also
    # the drift guard for the op-identical helper copies in `fitted` — any divergence
    # from `select`'s recursion order shows up here as a bit mismatch, so `==`, never a
    # tolerance. The series is trend + deterministic zig-zag, nothing degenerate.
    var yzz = List[Float64]()
    for t in range(40):
        yzz.append(
            10.0 + 0.3 * Float64(t)
            + (3.0 if t % 2 == 0 else -2.0)
            + 0.1 * Float64((t * 7) % 5)
        )
    var zline = _theta_line(yzz)
    var a_sel = _golden_ses_alpha(zline)
    var fc_ref = theta_forecast(yzz, 2.0, a_sel, 8)
    var at2 = theta_fitted_at(yzz, 2.0, 8)
    var anchor_ok = (
        at2.status == FC_OK and at2.has_forecast and fc_ref.has_forecast
        and at2.alpha == a_sel and at2.theta == 2.0 and len(at2.values) == 8
    )
    if anchor_ok:
        for k in range(8):
            if at2.values[k] != fc_ref.values[k]:
                anchor_ok = False
    if anchor_ok:
        passed += 1
        print("  ✅ theta_fitted_at(2.0) == select's alpha fit + theta_forecast, bit-exact")
    else:
        failed += 1
        print("  ❌ the theta = 2 anchor drifted:", at2.alpha, a_sel)

    # 8b. A perfect line, hand-derived: on y = 3 + 2t the OLS line is y itself, so the
    # theta line Z = theta*y + (1-theta)*L equals y for EVERY theta — the inner alpha
    # fit and the SES level s are therefore IDENTICAL across theta, and the profile
    # objective is (1/theta)^2 * C with C > 0 constant: monotone decreasing, so the
    # fitted theta must sit at the top of the box (midpoint of a 28-iteration bracket,
    # within 1e-3 of FIT_THETA_HI). The forecast error obeys the closed form
    # f_h - truth = (1/theta) * (s - truth_h) with the SAME s for every theta, hence
    # the exact identity theta* x err_fitted(h) = 2 x err_theta2(h), asserted at 1e-9
    # relative (the subtraction f - truth cancels ~digit-for-digit at these magnitudes,
    # nothing worse). The fitted theta's error is |2/theta*| ~ 0.2 of classical
    # theta's — the driver's reason to exist, asserted, not narrated.
    var ylin = List[Float64]()
    for t in range(30):
        ylin.append(3.0 + 2.0 * Float64(t))
    var flin = theta_fitted(ylin, 6)
    var flin2 = theta_fitted_at(ylin, 2.0, 6)
    var lin_ok = (
        flin.status == FC_OK and flin.theta > FIT_THETA_HI - 1.0e-3
        and flin2.status == FC_OK
    )
    if lin_ok:
        for k in range(6):
            var truth = 3.0 + 2.0 * Float64(29 + k + 1)
            var err_f = flin.values[k] - truth
            var err_2 = flin2.values[k] - truth
            if fabs(flin.theta * err_f - 2.0 * err_2) > 1.0e-9 * fabs(2.0 * err_2):
                lin_ok = False
            if not (fabs(err_f) < fabs(err_2)):
                lin_ok = False
    if lin_ok:
        passed += 1
        print("  ✅ on y = 3+2t: theta -> box top, err identity theta*errF == 2*err2 holds")
    else:
        failed += 1
        print("  ❌ linear-series theta fit wrong:", flin.theta, flin.values[5])

    # 8c. The optimizer optimises ITS OWN objective: on the zig-zag series the fitted
    # theta is interior (measured 5.6276..., pinned only as "strictly inside the box")
    # and its method-scale SSE is <= the SSE at theta = 1, 2 and 10 probed through the
    # same public building block (measured 292.81 vs 369.91 / 321.98 / 294.60). A
    # flipped bracket update, a dropped (1/theta)^2 rescale or an ignored theta
    # argument each break at least one of these (verified by mutation before this
    # file shipped). Consistency: theta_fitted's path IS theta_fitted_at(theta*)'s,
    # bit-for-bit, so the optimum and its forecast cannot drift apart.
    var fzz = theta_fitted(yzz, 8)
    var zz1 = theta_fitted_at(yzz, 1.0, 8)
    var zz10 = theta_fitted_at(yzz, 10.0, 8)
    var fzz_at = theta_fitted_at(yzz, fzz.theta, 8)
    var opt_ok = (
        fzz.status == FC_OK and fzz.theta > 1.01 and fzz.theta < 9.99
        and fzz.sse <= zz1.sse and fzz.sse <= at2.sse and fzz.sse <= zz10.sse
        and fzz.alpha == fzz_at.alpha and fzz.insample_mae == fzz_at.insample_mae
    )
    if opt_ok:
        for k in range(8):
            if fzz.values[k] != fzz_at.values[k]:
                opt_ok = False
    if opt_ok:
        passed += 1
        print("  ✅ fitted theta interior, beats theta = 1/2/10 on its objective,")
        print("     and equals theta_fitted_at(theta*) bit-for-bit")
    else:
        failed += 1
        print("  ❌ theta optimum inconsistent:", fzz.theta, fzz.sse, at2.sse)

    # 8d. The selection statistic is the METHOD's, not the line's: at theta = 2 the
    # reported insample_mae must be EXACTLY half the SES-on-Z mae — the same
    # (1/theta)-rescale `forecasting.select` applies to its theta candidate, so a
    # selector can rank this driver against the existing pool without conversion.
    var z_pass_sae: Float64 = 0.0
    var s_run = zline[0]
    for t in range(1, len(zline)):
        var e = zline[t] - s_run
        z_pass_sae += fabs(e)
        s_run = a_sel * zline[t] + (1.0 - a_sel) * s_run
    var z_mae = z_pass_sae / Float64(len(zline) - 1)
    if at2.insample_mae == 0.5 * z_mae:
        passed += 1
        print("  ✅ insample_mae at theta = 2 is exactly half the theta-line SES mae")
    else:
        failed += 1
        print("  ❌ method-scale mae wrong:", at2.insample_mae, 0.5 * z_mae)

    # 8e. Refusals, per rule 4: absent, never a padded stand-in.
    var t_empty = theta_fitted(List[Float64](), 4)
    var t_short = theta_fitted(_floats(1.0, 2.0), 1)
    var t_range = theta_fitted_at(yzz, 0.5, 4)   # theta < 1 leans against the trend
    var t_hor = theta_fitted(yzz, 0)
    if (
        t_empty.status == FC_ERR_EMPTY_SERIES and not t_empty.has_forecast
        and len(t_empty.values) == 0
        and t_short.status == FC_ERR_INSUFFICIENT_HISTORY and not t_short.has_forecast
        and t_range.status == FC_ERR_PARAM_RANGE and not t_range.has_forecast
        and t_hor.status == FC_ERR_HORIZON and not t_hor.has_forecast
    ):
        passed += 1
        print("  ✅ theta refusals: empty, n < 3, theta < 1, horizon 0 — all absent")
    else:
        failed += 1
        print("  ❌ a theta refusal leaked a forecast:", t_empty.status,
              t_short.status, t_range.status, t_hor.status)

    # ══ 9. DOTM: the dynamic theta recursion, pinned to the reference ═════════════════
    #
    # 9a. THE REFERENCE-PINNED PASS, derived by hand and confirmed against the compiled
    # statsforecast 2.1.1 `theta::calc` (which this port was validated against on 200
    # randomized trials to 1e-12 and 600 M4 series end-to-end at rel < 1e-4, 597/600
    # rel < 1e-8, before this section was written). y = [3, 5, 4, 7], l0 = 2,
    # alpha = 0.5, theta = 2 — every state is hand-checkable:
    #   i=0: lev = 2.5, meany = A = 3, B = 0, no error charged (mu_0 = y_0)
    #   i=1: mu = 2.5 + .5*(3*.5) = 3.25, e = 1.75; lev 3.75; B = (6*(5-3)/2)/3 = 2,
    #        meany 4, A = 4 - 2*3/2 = 1
    #   i=2: mu = 3.75 + .5*(1*.25 + 2*(1-.125)/.5) = 5.625, e = -1.625; lev 3.875;
    #        B = (1*2 + 0)/4 = 0.5, meany 4, A = 3
    #   i=3: mu = 3.875 + .5*(3*.125 + .5*(1-.0625)/.5) = 4.53125, e = 2.46875;
    #        lev 5.4375; B = (2*.5 + 6*(7-4)/4)/5 = 1.1 <- FROM THE PRE-UPDATE MEAN 4,
    #        the sampler-style post-update mean gives 0.875 and a different estimator;
    #        meany 4.75, A = 4.75 - 1.1*5/2 = 2
    # objective = 2.46875^2 / mean|y| = 6.0947265625 / 4.75; sse(t>=1) = 3.0625 +
    # 2.640625 + 6.0947265625 = 11.7978515625. Dyadic except the two divisions, which
    # are single correctly-rounded IEEE ops, so `==` throughout.
    var ydot = _floats(3.0, 5.0, 4.0, 7.0)
    var dp = _dotm_pass(ydot, 2.0, 0.5, 2.0)
    if (
        len(dp) == 7
        and dp[0] == 6.0947265625 / 4.75
        and dp[1] == 5.4375 and dp[2] == 4.75 and dp[3] == 2.0 and dp[4] == 1.1
        and dp[5] == 11.7978515625
    ):
        passed += 1
        print("  ✅ DOTM pass on [3,5,4,7]: every state and both errors hand-exact")
    else:
        failed += 1
        if len(dp) == 7:
            print("  ❌ DOTM pass wrong:", dp[0], dp[1], dp[2], dp[3], dp[4], dp[5])
        else:
            print("  ❌ DOTM pass refused a finite series")

    # 9b. The forecast recursion continues the SAME updates with mu standing in for y:
    # step 1 = 5.4375 + .5*(2*.0625 + 1.1*(1-.03125)/.5) = 6.565625, and the states it
    # implies give step 2 = 6.937509765625 — both confirmed equal to the compiled
    # reference `theta::forecast` output on this exact input. 1e-12 relative covers
    # the one non-dyadic product; the reference values themselves are printed digits
    # of the compiled library's doubles.
    var dpath = _dotm_forecast_path(4, 2, 0.5, 2.0, dp[1], dp[2], dp[3], dp[4])
    if (
        len(dpath) == 2
        and fabs(dpath[0] - 6.565625) <= 1.0e-12 * 6.565625
        and fabs(dpath[1] - 6.937509765625) <= 1.0e-12 * 6.937509765625
    ):
        passed += 1
        print("  ✅ DOTM forecast recursion reproduces the reference path (2 steps)")
    else:
        failed += 1
        print("  ❌ DOTM forecast wrong:", dpath[0] if len(dpath) > 0 else -1.0,
              dpath[1] if len(dpath) > 1 else -1.0)

    # 9c. The fitted driver on a perfect line: the dynamic OLS states on y = 3 + 2t
    # equal the true line from the second observation on, so a large theta rides it
    # and the h = 6 forecast must land within 0.1 of the truth 73 (measured 72.9595)
    # — STRICTLY closer than the static theta_fitted's box-capped 71.798, which is
    # the dynamics' reason to exist. Plus bit-reproducibility and rule-4 refusals
    # (n = 3 is a refusal HERE — the reference objective sees no error at n <= 3 and
    # would converge instantly on an arbitrary start; theta_fitted accepts n = 3
    # because ITS objective scores errors from t = 1).
    var ylin9 = List[Float64]()
    for t in range(30):
        ylin9.append(3.0 + 2.0 * Float64(t))
    var d9 = dotm_fitted(ylin9, 6)
    var d9b = dotm_fitted(ylin9, 6)
    var s9 = theta_fitted(ylin9, 6)
    var d9_ok = (
        d9.status == FC_OK and d9.has_forecast
        and fabs(d9.values[5] - 73.0) < 0.1
        and fabs(d9.values[5] - 73.0) < fabs(s9.values[5] - 73.0)
        and d9.values[5] == d9b.values[5] and d9.theta == d9b.theta
    )
    var d_empty = dotm_fitted(List[Float64](), 4)
    var d_short = dotm_fitted(_floats(1.0, 2.0, 3.0), 1)
    var d_hor = dotm_fitted(ydot, 0)
    if (
        d9_ok
        and d_empty.status == FC_ERR_EMPTY_SERIES and not d_empty.has_forecast
        and d_short.status == FC_ERR_INSUFFICIENT_HISTORY and not d_short.has_forecast
        and d_hor.status == FC_ERR_HORIZON and not d_hor.has_forecast
    ):
        passed += 1
        print("  ✅ dotm_fitted: line within 0.1 of truth, beats static, reproducible,")
        print("     and empty / n = 3 / horizon 0 are refusals")
    else:
        failed += 1
        print("  ❌ dotm_fitted wrong:", d9.status, d9.values[5] if d9.has_forecast else -1.0,
              d_short.status)

    print("  [forecasting.fitted] Passed:", passed, "Failed:", failed)
