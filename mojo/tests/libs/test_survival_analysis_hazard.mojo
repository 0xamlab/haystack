"""test_survival_analysis_hazard.mojo — known values for Nelson-Aalen and the smoothed hazard.

Hand-written. Every number below was derived OUTSIDE this tree, either by hand from the
definition or in exact rational arithmetic, and none of it is a self-consistency check.

1. THE KERNEL-SMOOTHED HAZARD, AGAINST EXACT RATIONALS. Klein & Moeschberger *Survival
   Analysis* eq. 6.2.1 is `h(t) = (1/b) sum_j K((t - t_j)/b) dH_j` with the Epanechnikov
   kernel `K(u) = 3/4 (1 - u^2)` on `|u| <= 1`. On `times = 1..5`, all events, `b = 2` the
   Nelson-Aalen increments are `1/5, 1/4, 1/3, 1/2, 1` and every kernel weight is a rational,
   so the five answers are exact fractions:

       93/640, 39/160, 43/128, 9/16, 33/64  =  0.1453125, 0.24375, 0.3359375, 0.5625, 0.515625

   Worked by hand at `t = 1`: the window reaches `t_j = 1, 2, 3`; `K(0) = 3/4`,
   `K(-1/2) = 9/16`, `K(-1) = 0`; so `h = (3/4 * 1/5 + 9/16 * 1/4) / 2 = (3/20 + 9/64)/2
   = 93/640`. THE ANSWER RISES 3.55x ACROSS THE CURVE, and that ratio is asserted, because
   the defect this suite exists to prevent returned a FLAT `1/b = 0.5` at all five times --
   the same number for every dataset. The flatness assertion fails against that code by
   construction: `0.5 / 0.5 = 1.0`, not 3.55.

2. THE `b = 1` CASE A READER CAN CHECK WITHOUT A CALCULATOR. With integer times one apart
   and `b = 1`, every neighbour sits at `|u| = 1` where `K = 0`, so only the point's own
   increment survives and `h(t_j) = 3/4 * dH_j` exactly: 0.15, 0.1875, 0.25, 0.375, 0.75.

3. THE WORK CHARGE IS THE WORK DONE. `kernel_pairs` is asserted to be 19 on that sample,
   counted by hand: the windows hold 3, 4, 5, 4 and 3 event times.

4. THE INCREMENTS ARE THE FROZEN KERNEL'S. `increment_sum` is compared against
   `survival.nelson_aalen`'s own total and the residual is asserted to be exactly 0.0 --
   the same `Float64(d)/Float64(n)` divisions, in the same order.

5. NELSON-AALEN AND THE AALEN VARIANCE, exact rationals again: on the 8-row censored
   showcase sample `H = 1/8, 11/24, 19/24, 43/24` and
   `sigma = sqrt(sum d_j/n_j^2) = 0.125, 0.2667968432263687, 0.42695628191498325,
   1.087332362558324`. The log-transformed band at `t = 2` is
   `[0.017607936761652187, 0.8873839230289169]`, recomputed independently in Python.
"""
from std.math import abs as fabs

from survival_analysis.base import (
    SA_ERR_BAD_SHAPE_PARAM,
    SA_ERR_CENSOR_LENGTH,
    SA_ERR_EMPTY,
    SA_ERR_NON_FINITE_TIME,
    SA_OK,
    sa_status_name,
)
from survival_analysis.hazard import SA_EPANECHNIKOV_PEAK, na_fit, na_smoothed_hazard

comptime EPS: Float64 = 2.220446049250313e-16


def _f(*v: Float64) -> List[Float64]:
    var o = List[Float64]()
    for i in range(len(v)):
        o.append(v[i])
    return o^


def _i(*v: Int) -> List[Int]:
    var o = List[Int]()
    for i in range(len(v)):
        o.append(v[i])
    return o^


def _close(got: Float64, want: Float64, ulps: Float64) -> Bool:
    """Per-ITEM: scaled by THAT item's own magnitude times DBL_EPSILON. Nothing else."""
    var slop = ulps * EPS * fabs(want)
    if slop < ulps * EPS:
        slop = ulps * EPS
    return fabs(got - want) <= slop


def _rel(got: Float64, want: Float64, rel: Float64) -> Bool:
    """A looser per-item comparison for values built through `log`/`exp`/`erf`."""
    var slop = rel * fabs(want)
    if slop < rel:
        slop = rel
    return fabs(got - want) <= slop


def _nan() -> Float64:
    var z: Float64 = 0.0
    return z / z


def _inf() -> Float64:
    var z: Float64 = 0.0
    return 1.0 / z


def main() raises:
    var passed = 0
    var failed = 0
    print("[survival_analysis.hazard] hand-written known values")

    # ── 1. the smoothed hazard against exact rationals ───────────────────────
    var t5 = _f(1.0, 2.0, 3.0, 4.0, 5.0)
    var e5 = _i(1, 1, 1, 1, 1)
    var sm = na_smoothed_hazard(t5, e5, 2.0)
    var want = _f(0.1453125, 0.24375, 0.3359375, 0.5625, 0.515625)
    if sm.status != SA_OK or sm.n_event_times != 5:
        failed += 1
        print("  ❌ smoothed hazard refused:", sa_status_name(sm.status))
    else:
        var ok = True
        for j in range(5):
            if not _close(sm.rate[j], want[j], 8.0):
                ok = False
                print("     j", j, "got", sm.rate[j], "want", want[j])
            if not sm.has_rate[j]:
                ok = False
                print("     j", j, "reported absent")
        if ok:
            passed += 1
            print("  ✅ h(1..5), b=2 = 93/640, 39/160, 43/128, 9/16, 33/64 (K&M eq. 6.2.1)")
        else:
            failed += 1
            print("  ❌ smoothed hazard does not match the exact rationals")

    # THE ASSERTION THAT FAILS AGAINST THE DEFECT: a data-independent 1/b is flat.
    if sm.status == SA_OK and sm.n_event_times == 5:
        var ratio = sm.rate[4] / sm.rate[0]
        var flat = _close(sm.rate[0], 0.5, 8.0) and _close(sm.rate[4], 0.5, 8.0)
        if ratio > 3.0 and ratio < 4.0 and not flat:
            passed += 1
            print("  ✅ the curve RISES 3.55x; it is not the flat 1/b = 0.5 the frozen"
                  " hazard_rate returns for every uncensored sample")
        else:
            failed += 1
            print("  ❌ smoothed hazard is flat or data-independent: ratio", ratio)

    # A COMPLETELY DIFFERENT SAMPLE MUST GIVE A DIFFERENT ANSWER.
    var sm_alt = na_smoothed_hazard(_f(1.0, 1.5, 1.7, 1.9, 100.0), e5, 2.0)
    if sm_alt.status == SA_OK and sm_alt.n_event_times == 5:
        var differs = False
        for j in range(5):
            if not _close(sm_alt.rate[j], 0.5, 8.0):
                differs = True
        if differs:
            passed += 1
            print("  ✅ [1, 1.5, 1.7, 1.9, 100] gives a different curve, not 0.5 everywhere")
        else:
            failed += 1
            print("  ❌ the estimate is independent of the data")

    # ── 2. b = 1: only the point's own increment is inside the window ─────────
    var sm1 = na_smoothed_hazard(t5, e5, 1.0)
    var want1 = _f(0.15, 0.1875, 0.25, 0.375, 0.75)
    if sm1.status == SA_OK:
        var ok1 = True
        for j in range(5):
            if not _close(sm1.rate[j], want1[j], 8.0):
                ok1 = False
            if not _close(sm1.rate[j], SA_EPANECHNIKOV_PEAK * sm1.increment[j], 8.0):
                ok1 = False
        if ok1:
            passed += 1
            print("  ✅ b=1 on unit-spaced times gives exactly 3/4 * dH_j at every point")
        else:
            failed += 1
            print("  ❌ b=1 case wrong")
    else:
        failed += 1
        print("  ❌ b=1 refused:", sa_status_name(sm1.status))

    # ── 3. the charge equals the work, and the boundary flags ────────────────
    if sm.status == SA_OK:
        if sm.kernel_pairs == 19:
            passed += 1
            print("  ✅ kernel_pairs = 19, the hand-counted window sizes 3+4+5+4+3")
        else:
            failed += 1
            print("  ❌ kernel_pairs", sm.kernel_pairs, "expected 19")
        if (
            sm.boundary[0]
            and sm.boundary[1]
            and not sm.boundary[2]
            and sm.boundary[3]
            and sm.boundary[4]
        ):
            passed += 1
            print("  ✅ only t=3 is interior at b=2; the other four are boundary-flagged")
        else:
            failed += 1
            print("  ❌ boundary flags wrong")

    # ── 4. the increments are the frozen kernel's, exactly ───────────────────
    if sm.status == SA_OK:
        var inc_ok = (
            _close(sm.increment[0], 0.2, 4.0)
            and _close(sm.increment[1], 0.25, 4.0)
            and _close(sm.increment[2], 1.0 / 3.0, 4.0)
            and _close(sm.increment[3], 0.5, 4.0)
            and _close(sm.increment[4], 1.0, 4.0)
        )
        if inc_ok and sm.frozen_agrees and sm.frozen_residual == 0.0:
            passed += 1
            print("  ✅ increments 1/5,1/4,1/3,1/2,1 and the frozen nelson_aalen total agree"
                  " with residual exactly 0.0")
        else:
            failed += 1
            print("  ❌ increment column or frozen cross-check:", sm.frozen_residual,
                  sm.frozen_agrees)

    # ── 5. Nelson-Aalen and the Aalen variance on the censored showcase ──────
    var t8 = _f(2.0, 3.0, 4.0, 4.0, 5.0, 6.0, 8.0, 9.0)
    var e8 = _i(1, 0, 1, 1, 0, 1, 0, 1)
    var na = na_fit(t8, e8, 0.95)
    if na.status != SA_OK or na.n_event_times != 4:
        failed += 1
        print("  ❌ na_fit refused:", sa_status_name(na.status))
    else:
        var wh = _f(0.125, 0.4583333333333333, 0.7916666666666666, 1.7916666666666667)
        var ws = _f(0.125, 0.2667968432263687, 0.42695628191498325, 1.087332362558324)
        var ok5 = True
        for j in range(4):
            if not _close(na.hazard[j], wh[j], 8.0):
                ok5 = False
                print("     H j", j, na.hazard[j], wh[j])
            if not _close(na.std_error[j], ws[j], 8.0):
                ok5 = False
                print("     se j", j, na.std_error[j], ws[j])
            if not na.has_std_error[j]:
                ok5 = False
        if ok5 and na.n_events == 5 and na.n_censored == 3 and na.frozen_rows_aligned:
            passed += 1
            print("  ✅ H = 1/8, 11/24, 19/24, 43/24 with the Aalen sqrt(sum d/n^2) SEs")
        else:
            failed += 1
            print("  ❌ na_fit known values wrong")
        # the log band at t=2, recomputed in Python from the same definition
        if _rel(na.lower[0], 0.017607936761652187, 1e-8) and _rel(
            na.upper[0], 0.8873839230289169, 1e-8
        ):
            passed += 1
            print("  ✅ log band at t=2 = [0.0176079367616, 0.8873839230289]")
        else:
            failed += 1
            print("  ❌ log band at t=2:", na.lower[0], na.upper[0])

    # ── refusals ─────────────────────────────────────────────────────────────
    var bad_bw = 0
    var bws = _f(0.0, -1.0, _nan(), _inf())
    for i in range(len(bws)):
        if na_smoothed_hazard(t5, e5, bws[i]).status == SA_ERR_BAD_SHAPE_PARAM:
            bad_bw += 1
    if bad_bw == 4:
        passed += 1
        print("  ✅ bandwidth 0, negative, NaN and infinite are all refused (a zero-width"
              " window otherwise returns a complete curve of zeros)")
    else:
        failed += 1
        print("  ❌ bandwidth refusals:", bad_bw, "of 4")

    var empty_f = List[Float64]()
    var empty_i = List[Int]()
    var refusals_ok = (
        na_smoothed_hazard(empty_f, empty_i, 1.0).status == SA_ERR_EMPTY
        and na_smoothed_hazard(t5, _i(1, 1), 1.0).status == SA_ERR_CENSOR_LENGTH
        and na_smoothed_hazard(_f(1.0, _nan()), _i(1, 1), 1.0).status == SA_ERR_NON_FINITE_TIME
        and na_fit(t5, e5, 1.0).status != SA_OK
    )
    if refusals_ok:
        passed += 1
        print("  ✅ empty, length mismatch, non-finite time and conf_level = 1.0 refused")
    else:
        failed += 1
        print("  ❌ a refusal path did not fire")

    # ── the A-Z harness argument pattern ─────────────────────────────────────
    var lf5 = _f(0.5, 0.5, 0.5, 0.5, 0.5)
    var li5 = _i(5, 5, 5, 5, 5)
    if (
        na_smoothed_hazard(lf5, li5, 0.5).status != SA_OK
        and na_fit(lf5, li5, 0.5).status != SA_OK
    ):
        passed += 1
        print("  ✅ the fixed 5-element/5-integer harness pattern is refused, not indexed")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern was accepted")

    print("  [survival_analysis.hazard] Passed:", passed, "Failed:", failed)
