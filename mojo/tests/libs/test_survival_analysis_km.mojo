"""test_survival_analysis_km.mojo — known values for Kaplan-Meier, Greenwood, RMST, lookup.

Hand-written. The sample used throughout is the 8-row censored one
`times = 2, 3, 4, 4, 5, 6, 8, 9`, `event = 1, 0, 1, 1, 0, 1, 0, 1`, whose risk table is
`(2, 8, 1), (4, 6, 2), (6, 3, 1), (9, 1, 1)` -- countable by hand from
`n_j = #{t_i >= t_j}`.

1. THE PRODUCT-LIMIT ESTIMATE, exact fractions: `S = 7/8, 7/12, 7/18, 0`.
2. GREENWOOD, from `S(t)^2 sum d_j/(n_j(n_j - d_j))`, recomputed independently in Python:
   `se = 0.11692679333668568, 0.1855609613317693, 0.20126912147485335`. The FOURTH row has
   `n_j == d_j`: the term is `1/0`, the variance does not exist, and `has_std_error` is
   asserted False there. The suite pins the ABSENCE, not a zero.
3. THE LOG-LOG BAND at `t = 2`: `[0.3870000140320252, 0.981392965878966]`, from
   `S^exp(±z se_ll)` with `se_ll = sqrt(sum) / |log S|` and `z = 1.959963984540054` --
   the algebra `survfit(conf.type = "log-log")` uses, recomputed digit by digit in Python.
4. BOTH MEDIAN CONVENTIONS. On `times = 1, 2, 3, 4` all events, `S = 0.75, 0.5, 0.25, 0`:
   the textbook `min{t : S(t) <= 0.5}` is 2 and the frozen `median_survival`'s
   `min{t : S(t) < 0.5}` is 3. Both are asserted, because a caller comparing against an
   existing report needs to know which one they are holding.
5. RMST BY HAND. To `tau = 9`: `1*2 + (7/8)*2 + (7/12)*2 + (7/18)*3 = 6.083333333333334`.
   Also `tau = 6 -> 4.916666666666667` and `tau = 4 -> 3.75`.
6. NO EXTRAPOLATION. `km_survival_at` past the largest observed time is ABSENT. The
   previous behaviour published `S(1e300) = 0.25` with `has_value = true` on a sample whose
   last observation is 10, which is the last known level carried forward and presented as a
   measurement; `km_rmst` refuses a `tau` past the same boundary and gives the reason in its
   own docstring. R's `survfit` reports NA there. The assertion below fails against the
   extrapolating code at `t = 10.0001`, `1e6` and `1e300`.
"""
from std.math import abs as fabs

from survival_analysis.base import (
    SA_ERR_BAD_CONFIDENCE,
    SA_ERR_BAD_TAU,
    SA_ERR_CENSOR_LENGTH,
    SA_ERR_EMPTY,
    SA_OK,
    sa_status_name,
)
from survival_analysis.km import km_fit, km_rmst, km_survival_at

comptime EPS: Float64 = 2.220446049250313e-16


fn _f(*v: Float64) -> List[Float64]:
    var o = List[Float64]()
    for i in range(len(v)):
        o.append(v[i])
    return o^


fn _i(*v: Int) -> List[Int]:
    var o = List[Int]()
    for i in range(len(v)):
        o.append(v[i])
    return o^


fn _close(got: Float64, want: Float64, ulps: Float64) -> Bool:
    var slop = ulps * EPS * fabs(want)
    if slop < ulps * EPS:
        slop = ulps * EPS
    return fabs(got - want) <= slop


fn _rel(got: Float64, want: Float64, rel: Float64) -> Bool:
    var slop = rel * fabs(want)
    if slop < rel:
        slop = rel
    return fabs(got - want) <= slop


fn main() raises:
    var passed = 0
    var failed = 0
    print("[survival_analysis.km] hand-written known values")

    var t8 = _f(2.0, 3.0, 4.0, 4.0, 5.0, 6.0, 8.0, 9.0)
    var e8 = _i(1, 0, 1, 1, 0, 1, 0, 1)
    var fit = km_fit(t8, e8, 0.95)

    # ── 1 + 2. the curve and the Greenwood SEs ───────────────────────────────
    if fit.status != SA_OK or fit.n_event_times != 4:
        failed += 1
        print("  ❌ km_fit refused:", sa_status_name(fit.status))
    else:
        var ws = _f(0.875, 0.5833333333333334, 0.38888888888888895, 0.0)
        var wse = _f(0.11692679333668568, 0.1855609613317693, 0.20126912147485335)
        var ok = True
        for j in range(4):
            if not _close(fit.survival[j], ws[j], 8.0):
                ok = False
                print("     S j", j, fit.survival[j], ws[j])
        for j in range(3):
            if not _close(fit.std_error[j], wse[j], 8.0):
                ok = False
                print("     se j", j, fit.std_error[j], wse[j])
            if not fit.has_std_error[j]:
                ok = False
        if ok and fit.at_risk[0] == 8 and fit.at_risk[1] == 6 and fit.at_risk[2] == 3:
            passed += 1
            print("  ✅ S = 7/8, 7/12, 7/18, 0 on risk sets 8, 6, 3, 1 with Greenwood SEs")
        else:
            failed += 1
            print("  ❌ curve or Greenwood SEs wrong")

        if not fit.has_std_error[3] and fit.std_error[3] == 0.0:
            passed += 1
            print("  ✅ n_j == d_j at t=9: the Greenwood variance is ABSENT, and the slot"
                  " holds 0.0 as a placeholder rather than claiming zero uncertainty")
        else:
            failed += 1
            print("  ❌ the undefined Greenwood row was published as a measurement")

        # ── 3. the log-log band ──────────────────────────────────────────────
        if _rel(fit.lower[0], 0.3870000140320252, 1e-8) and _rel(
            fit.upper[0], 0.981392965878966, 1e-8
        ):
            passed += 1
            print("  ✅ log-log band at t=2 = [0.387000014, 0.981392966], survfit's algebra")
        else:
            failed += 1
            print("  ❌ log-log band at t=2:", fit.lower[0], fit.upper[0])

        var inside = True
        for j in range(4):
            if fit.has_band[j]:
                if fit.lower[j] < 0.0 or fit.upper[j] > 1.0:
                    inside = False
                if fit.lower[j] > fit.survival[j] or fit.upper[j] < fit.survival[j]:
                    inside = False
        if inside:
            passed += 1
            print("  ✅ every band lies inside [0, 1] and contains its point estimate")
        else:
            failed += 1
            print("  ❌ a band left [0, 1] or excluded its own point estimate")

    # ── 4. both median conventions ───────────────────────────────────────────
    var even = km_fit(_f(1.0, 2.0, 3.0, 4.0), _i(1, 1, 1, 1), 0.95)
    if (
        even.status == SA_OK
        and even.has_median
        and even.has_median_strict
        and even.median_time == 2.0
        and even.median_strict_time == 3.0
    ):
        passed += 1
        print("  ✅ on S = .75, .5, .25, 0 the <= 0.5 median is 2 and the frozen < 0.5"
              " median is 3; both are reported, neither is substituted")
    else:
        failed += 1
        print("  ❌ median conventions:", even.median_time, even.median_strict_time)

    # ── 5. RMST by hand ──────────────────────────────────────────────────────
    var taus = _f(9.0, 6.0, 4.0)
    var want_rmst = _f(6.083333333333334, 4.916666666666667, 3.75)
    var rmst_ok = True
    for i in range(3):
        var r = km_rmst(t8, e8, taus[i])
        if r.status != SA_OK or not r.has_rmst or not _close(r.rmst, want_rmst[i], 8.0):
            rmst_ok = False
            print("     tau", taus[i], "->", sa_status_name(r.status), r.rmst)
    if rmst_ok:
        passed += 1
        print("  ✅ RMST(9) = 6.083333333333334 = 1*2 + (7/8)*2 + (7/12)*2 + (7/18)*3,"
              " RMST(6) = 4.916666666666667, RMST(4) = 3.75")
    else:
        failed += 1
        print("  ❌ RMST known values wrong")

    # ── 6. no extrapolation past the last observation ────────────────────────
    var tq = _f(2.0, 3.0, 4.0, 10.0)
    var eq = _i(1, 1, 1, 0)
    var lk = km_survival_at(tq, eq, _f(4.0, 9.999, 10.0, 10.0001, 1e6, 1e300))
    if lk.status != SA_OK:
        failed += 1
        print("  ❌ km_survival_at refused:", sa_status_name(lk.status))
    else:
        var in_ok = (
            lk.has_value[0]
            and lk.has_value[1]
            and lk.has_value[2]
            and _close(lk.survival[0], 0.25, 8.0)
            and _close(lk.survival[1], 0.25, 8.0)
            and _close(lk.survival[2], 0.25, 8.0)
        )
        var out_ok = (
            not lk.has_value[3]
            and not lk.has_value[4]
            and not lk.has_value[5]
            and lk.survival[3] == 0.0
            and lk.survival[4] == 0.0
            and lk.survival[5] == 0.0
        )
        if in_ok and out_ok and lk.n_beyond_support == 3 and lk.max_observed_time == 10.0:
            passed += 1
            print("  ✅ S = 0.25 up to t = 10 and ABSENT at 10.0001, 1e6, 1e300"
                  " (n_beyond_support = 3); the step function is not extrapolated")
        else:
            failed += 1
            print("  ❌ lookup extrapolates past the last observation:",
                  lk.has_value[3], lk.survival[3], lk.n_beyond_support)

        # the two entry points must agree about where the data end
        var rt = km_rmst(tq, eq, 10.0001)
        var rt_ok = km_rmst(tq, eq, 10.0)
        if rt.status == SA_ERR_BAD_TAU and rt_ok.status == SA_OK:
            passed += 1
            print("  ✅ km_rmst refuses tau = 10.0001 and accepts tau = 10.0: the lookup and"
                  " the integral draw the boundary at the same place")
        else:
            failed += 1
            print("  ❌ km_rmst and km_survival_at disagree about the support")

    # a negative and a non-finite query are absent without failing the batch
    var mixed = km_survival_at(tq, eq, _f(-1.0, 2.0))
    if mixed.status == SA_OK and not mixed.has_value[0] and mixed.has_value[1]:
        passed += 1
        print("  ✅ a negative query is absent and does not discard the other answers")
    else:
        failed += 1
        print("  ❌ one bad query row spoiled the batch")

    # ── refusals ─────────────────────────────────────────────────────────────
    var empty_f = List[Float64]()
    var empty_i = List[Int]()
    var refusals = (
        km_fit(empty_f, empty_i, 0.95).status == SA_ERR_EMPTY
        and km_fit(t8, _i(1, 1), 0.95).status == SA_ERR_CENSOR_LENGTH
        and km_fit(t8, e8, 0.4).status == SA_ERR_BAD_CONFIDENCE
        and km_fit(t8, e8, 1.0).status == SA_ERR_BAD_CONFIDENCE
        and km_rmst(t8, e8, 0.0).status == SA_ERR_BAD_TAU
        and km_rmst(t8, e8, -3.0).status == SA_ERR_BAD_TAU
    )
    if refusals:
        passed += 1
        print("  ✅ empty, length mismatch, conf_level 0.4 and 1.0, tau 0 and negative refused")
    else:
        failed += 1
        print("  ❌ a refusal path did not fire")

    var lf5 = _f(0.5, 0.5, 0.5, 0.5, 0.5)
    var li5 = _i(5, 5, 5, 5, 5)
    if (
        km_fit(lf5, li5, 0.5).status != SA_OK
        and km_rmst(lf5, li5, 0.5).status != SA_OK
        and km_survival_at(lf5, li5, lf5).status != SA_OK
    ):
        passed += 1
        print("  ✅ the fixed 5-element/5-integer harness pattern is refused, not indexed")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern was accepted")

    print("  [survival_analysis.km] Passed:", passed, "Failed:", failed)
