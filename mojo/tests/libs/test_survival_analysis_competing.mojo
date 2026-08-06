"""test_survival_analysis_competing.mojo — known values for Aalen-Johansen cumulative incidence.

Hand-written. The sample is `times = 1..6`, `cause = 1, 2, 1, 0, 2, 1`, `n_causes = 2`: a
cause-1 failure at 1, a cause-2 failure at 2, cause-1 at 3, a censoring at 4, cause-2 at 5,
cause-1 at 6. Every quantity below was computed in EXACT RATIONAL arithmetic outside this
tree, so the expected values are fractions and not printouts:

    t   n_j  S(t)   CIF_1   CIF_2   H_1     H_2
    1    6   5/6    1/6     0       1/6     0
    2    5   2/3    1/6     1/6     1/6     1/5
    3    4   1/2    1/3     1/6     5/12    1/5
    5    2   1/4    1/3     5/12    5/12    7/10
    6    1   0      7/12    5/12    17/12   7/10

`CIF_k(t) = sum_{t_j <= t} S(t_{j-1}) d_kj / n_j` -- worked at `t = 3`:
`1 * (1/6) + (2/3) * (1/4) = 1/6 + 1/6 = 1/3`.

1. THE PARTITION IDENTITY `S + CIF_1 + CIF_2 == 1` is exact algebra on this sample, so the
   residual is asserted to be EXACTLY 0.0, not merely small.
2. THE MISTAKE THE MODULE EXISTS TO PREVENT is measured, not described. Treating cause 2 as
   censoring and reporting `1 - S_KM` gives 1.0 at `t = 6`, against the correct
   `CIF_1(6) = 7/12 = 0.5833333`. The suite asserts that gap: 1.0 vs 7/12 is a 71% overstatement
   of the cause-1 risk, and it is the number a caller gets from the frozen `kaplan_meier`
   alone, which cannot be told about a cause code because it takes `List[Bool]`.
3. THE CAUSE-SPECIFIC CUMULATIVE HAZARD AND ITS AALEN SE: `H_1 = 17/12` with
   `se = sqrt(sum d_1j/n_j^2) = 1.044163673845139`, and `H_2 = 7/10` with
   `se = 0.5385164807134504`.
4. NO EXTRAPOLATION past the largest observed time, the same rule `km_survival_at` follows.
   The previous behaviour published `CIF(1e300) = 0.5` with `has_value = true` on a sample
   ending at 10; the assertion below fails against that code.
5. THE CEILING CANNOT DRIFT: `CIF_MAX_CAUSES` is 64 and `n_causes = 65` is refused, so the
   number in the `counts:` declaration is the number the kernel compares against.
"""
from std.math import abs as fabs

from survival_analysis.competing import CIF_MAX_CAUSES, cif_at_time, cif_fit, cif_validate_causes
from survival_analysis.base import (
    SA_ERR_BAD_CAUSE_CODE,
    SA_ERR_BAD_CAUSE_SELECTION,
    SA_ERR_CENSOR_LENGTH,
    SA_ERR_EMPTY,
    SA_ERR_NO_EVENTS,
    SA_ERR_TOO_MANY_CAUSES,
    SA_OK,
    sa_risk_table,
    sa_status_name,
)
from survival_analysis.km import km_fit

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
    var slop = ulps * EPS * fabs(want)
    if slop < ulps * EPS:
        slop = ulps * EPS
    return fabs(got - want) <= slop


def main() raises:
    var passed = 0
    var failed = 0
    print("[survival_analysis.competing] hand-written known values")

    var t6 = _f(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    var c6 = _i(1, 2, 1, 0, 2, 1)
    var fit = cif_fit(t6, c6, 2)

    if fit.status != SA_OK or fit.n_event_times != 5 or fit.n_causes != 2:
        failed += 1
        print("  ❌ cif_fit refused:", sa_status_name(fit.status), fit.n_event_times)
    else:
        var k = fit.n_event_times
        var w_s = _f(0.8333333333333334, 0.6666666666666667, 0.5, 0.25, 0.0)
        var w1 = _f(0.16666666666666666, 0.16666666666666666, 0.3333333333333333,
                    0.3333333333333333, 0.5833333333333334)
        var w2 = _f(0.0, 0.16666666666666666, 0.16666666666666666, 0.4166666666666667,
                    0.4166666666666667)
        var ok = True
        for j in range(k):
            if not _close(fit.overall_survival[j], w_s[j], 8.0):
                ok = False
                print("     S j", j, fit.overall_survival[j], w_s[j])
            if not _close(fit.incidence[j], w1[j], 8.0):
                ok = False
                print("     CIF1 j", j, fit.incidence[j], w1[j])
            if not _close(fit.incidence[k + j], w2[j], 8.0):
                ok = False
                print("     CIF2 j", j, fit.incidence[k + j], w2[j])
        if ok and fit.at_risk[0] == 6 and fit.at_risk[3] == 2 and fit.at_risk[4] == 1:
            passed += 1
            print("  ✅ CIF_1 = 1/6, 1/6, 1/3, 1/3, 7/12 and CIF_2 = 0, 1/6, 1/6, 5/12, 5/12"
                  " on S = 5/6, 2/3, 1/2, 1/4, 0 (Aalen-Johansen, exact rationals)")
        else:
            failed += 1
            print("  ❌ cumulative incidence known values wrong")

        # ── 1. the partition identity, exactly ───────────────────────────────
        if fit.partition_holds and fit.partition_max_error == 0.0 and fit.monotone:
            passed += 1
            print("  ✅ S + CIF_1 + CIF_2 == 1 at every event time with residual exactly 0.0")
        else:
            failed += 1
            print("  ❌ partition residual", fit.partition_max_error)

        # ── 3. the cause-specific cumulative hazards ─────────────────────────
        var h_ok = (
            _close(fit.cause_cum_hazard[k - 1], 1.4166666666666667, 8.0)
            and _close(fit.cause_cum_hazard[2 * k - 1], 0.7, 8.0)
            and _close(fit.cause_cum_hazard_se[k - 1], 1.044163673845139, 8.0)
            and _close(fit.cause_cum_hazard_se[2 * k - 1], 0.5385164807134504, 8.0)
            and fit.cause_event_count[0] == 3
            and fit.cause_event_count[1] == 2
        )
        if h_ok:
            passed += 1
            print("  ✅ H_1 = 17/12 with se 1.044163673845139, H_2 = 7/10 with se"
                  " 0.5385164807134504, and the per-cause totals are 3 and 2")
        else:
            failed += 1
            print("  ❌ cause-specific cumulative hazard or its SE wrong")

        # ── 2. the mistake, measured ─────────────────────────────────────────
        var as_censored = _i(0, 0, 0, 0, 0, 0)
        for i in range(6):
            as_censored[i] = 1 if c6[i] == 1 else 0
        var naive = km_fit(t6, as_censored, 0.95)
        if naive.status == SA_OK:
            var one_minus_s = 1.0 - naive.survival[naive.n_event_times - 1]
            var cif1_end = fit.incidence[k - 1]
            if _close(one_minus_s, 1.0, 8.0) and _close(cif1_end, 0.5833333333333334, 8.0):
                passed += 1
                print("  ✅ 1 - S_KM(cause 2 censored) = 1.0 against the correct"
                      " CIF_1(6) = 7/12 = 0.5833333: a 71% overstatement of the cause-1"
                      " risk, which is what the frozen kaplan_meier alone can produce")
            else:
                failed += 1
                print("  ❌ the naive-vs-correct comparison did not reproduce:",
                      one_minus_s, cif1_end)
        else:
            failed += 1
            print("  ❌ the naive KM comparison could not be built")

    # ── the step-function lookup, and its support boundary ───────────────────
    var look = cif_at_time(t6, c6, 2, 1, _f(0.5, 1.0, 2.5, 3.0, 6.0))
    if look.status == SA_OK:
        var lk_ok = (
            _close(look.incidence[0], 0.0, 8.0)
            and look.has_value[0]
            and _close(look.incidence[1], 0.16666666666666666, 8.0)
            and _close(look.incidence[2], 0.16666666666666666, 8.0)
            and _close(look.incidence[3], 0.3333333333333333, 8.0)
            and _close(look.incidence[4], 0.5833333333333334, 8.0)
        )
        if lk_ok:
            passed += 1
            print("  ✅ lookup is right-continuous: 0 before the first event (a real answer:"
                  " nobody has failed yet), 1/6 at 1 and 2.5, 1/3 at 3, 7/12 at 6")
        else:
            failed += 1
            print("  ❌ lookup values wrong")
    else:
        failed += 1
        print("  ❌ cif_at_time refused:", sa_status_name(look.status))

    # ── 4. no extrapolation ──────────────────────────────────────────────────
    var tq = _f(2.0, 3.0, 4.0, 10.0)
    var cq = _i(1, 2, 1, 0)
    var beyond = cif_at_time(tq, cq, 2, 1, _f(4.0, 10.0, 10.0001, 1e6, 1e300))
    if beyond.status == SA_OK:
        var ok4 = (
            beyond.has_value[0]
            and beyond.has_value[1]
            and not beyond.has_value[2]
            and not beyond.has_value[3]
            and not beyond.has_value[4]
            and beyond.incidence[2] == 0.0
            and beyond.incidence[3] == 0.0
            and beyond.incidence[4] == 0.0
            and beyond.n_beyond_support == 3
            and beyond.max_observed_time == 10.0
        )
        if ok4:
            passed += 1
            print("  ✅ CIF is ABSENT past the last observation (10.0001, 1e6, 1e300) and"
                  " present at 10.0; n_beyond_support = 3")
        else:
            failed += 1
            print("  ❌ cif_at_time extrapolates:", beyond.has_value[2], beyond.incidence[4])
    else:
        failed += 1
        print("  ❌ the beyond-support lookup refused:", sa_status_name(beyond.status))

    # ── 5. the ceiling, and the cause-code refusals ──────────────────────────
    if CIF_MAX_CAUSES == 64:
        passed += 1
        print("  ✅ CIF_MAX_CAUSES is 64, the literal the `counts:` declarations name")
    else:
        failed += 1
        print("  ❌ CIF_MAX_CAUSES drifted to", CIF_MAX_CAUSES)

    var empty_f = List[Float64]()
    var empty_i = List[Int]()
    var refusals = (
        cif_fit(t6, c6, CIF_MAX_CAUSES + 1).status == SA_ERR_TOO_MANY_CAUSES
        and cif_fit(t6, c6, 999).status == SA_ERR_TOO_MANY_CAUSES
        and cif_fit(t6, c6, 0).status == SA_ERR_BAD_CAUSE_CODE
        and cif_fit(t6, c6, -7).status == SA_ERR_BAD_CAUSE_CODE
        and cif_fit(t6, c6, 1).status == SA_ERR_BAD_CAUSE_CODE
        and cif_fit(t6, _i(1, 2), 2).status == SA_ERR_CENSOR_LENGTH
        and cif_fit(empty_f, empty_i, 2).status == SA_ERR_EMPTY
        and cif_fit(t6, _i(0, 0, 0, 0, 0, 0), 2).status == SA_ERR_NO_EVENTS
        and cif_at_time(t6, c6, 2, 3, t6).status == SA_ERR_BAD_CAUSE_SELECTION
        and cif_at_time(t6, c6, 2, 0, t6).status == SA_ERR_BAD_CAUSE_SELECTION
        and cif_at_time(t6, c6, 2, -3, t6).status == SA_ERR_BAD_CAUSE_SELECTION
        and cif_validate_causes(t6, c6, 2) == SA_OK
    )
    if refusals:
        passed += 1
        print("  ✅ n_causes 65/999/0/-7, a cause code above n_causes, a short cause list,"
              " an empty sample, an all-censored sample and selected 3/0/-3 all refused")
    else:
        failed += 1
        print("  ❌ a refusal path did not fire")

    # a cause code of 3 with n_causes = 2 must NOT silently vanish
    if cif_fit(t6, _i(1, 2, 3, 0, 2, 1), 2).status == SA_ERR_BAD_CAUSE_CODE:
        passed += 1
        print("  ✅ a status column recorded as 1/2/3 passed with n_causes = 2 is refused,"
              " not quietly dropped into the censored bucket")
    else:
        failed += 1
        print("  ❌ an out-of-range cause code was accepted")

    # the risk table the incidence is built from is the frozen KM's
    var table = sa_risk_table(t6, _i(1, 1, 1, 0, 1, 1))
    if table.status == SA_OK and table.n_event_times == 5 and table.at_risk[0] == 6:
        passed += 1
        print("  ✅ the all-cause risk table under the incidence is the frozen"
              " kaplan_meier's own (5 event times, first risk set 6)")
    else:
        failed += 1
        print("  ❌ risk table alignment")

    var lf5 = _f(0.5, 0.5, 0.5, 0.5, 0.5)
    var li5 = _i(5, 5, 5, 5, 5)
    if cif_fit(lf5, li5, 5).status == SA_OK and cif_at_time(lf5, li5, 5, 5, lf5).status == SA_OK:
        passed += 1
        print("  ✅ the fixed 5-element/5-integer harness pattern is a VALID"
              " competing-risks sample (5 cause-5 failures at one time) and is answered,"
              " not indexed out of bounds")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern was mishandled")

    print("  [survival_analysis.competing] Passed:", passed, "Failed:", failed)
