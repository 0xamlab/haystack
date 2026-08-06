"""test_survival_analysis_base.mojo — known values for the censoring contract and the guards.

Hand-written. What this suite pins, none of it a "it returned something" check:

1. THE WRAPPING MULTIPLY. `3 * 6148914691236517206 == 2` is asserted as an arithmetic FACT
   first, so the hazard is shown to exist, and then `sa_work_fits` is asked about the same
   pair and must refuse. A budget check written on a formed product would pass 1.8e19 units of
   work as "2".
2. THE RISK TABLE, BY HAND. On `times = 2, 3, 4, 4, 5, 6, 8, 9`,
   `event = 1, 0, 1, 1, 0, 1, 0, 1` the table is `(2, 8, 1), (4, 6, 2), (6, 3, 1), (9, 1, 1)`
   because `n_j = #{t_i >= t_j}` counts the observations censored exactly at `t_j`, and the
   survival column is `7/8, 7/12, 7/18, 0`.
3. AN EVENT AT TIME 0 SURVIVES THE ROW FILTER. The frozen `kaplan_meier` emits a synthetic
   origin row `(0, 1.0, n, 0)`, so a filter of "skip index 0" would delete a genuine event at
   `t = 0`. The filter is `events > 0`, and `times = [0, 1]` with both events is asserted to
   produce TWO rows with the first at `t = 0`.
4. GREENWOOD'S ABSENT MARKER IS -1.0 AND IS UNAMBIGUOUS, because every defined term is
   strictly positive: `d_j >= 1` and `n_j > d_j` on a defined row.
5. TIES ARE CANONICALISED. Inside one tie group events are emitted before censorings, so two
   callers who list the same sample in different row orders get byte-identical output. The
   suite feeds the same sample twice in different orders and compares.
6. EVERY STATUS CODE IS DISTINCT, LIES IN 900-949, AND NAMES DISTINCTLY -- including the two
   added by the repair, 931 `likelihood_unbounded_no_mle_exists` and 932
   `em_log_likelihood_decreased`.
7. `SA_DBL_EPSILON` IS THE REAL DBL_EPSILON, `2^-52`, asserted by construction from
   `1.0 + eps != 1.0` and `1.0 + eps/2 == 1.0`.
"""
from std.math import abs as fabs

from survival_analysis.base import (
    SA_DBL_EPSILON,
    SA_ERR_BAD_CONFIDENCE,
    SA_ERR_BAD_EVENT_CODE,
    SA_ERR_CENSOR_LENGTH,
    SA_ERR_EMPTY,
    SA_ERR_EM_NOT_MONOTONE,
    SA_ERR_LIKELIHOOD_UNBOUNDED,
    SA_ERR_NEGATIVE_TIME,
    SA_ERR_NON_FINITE_TIME,
    SA_ERR_TOO_MANY_OBS,
    SA_MAX_OBS,
    SA_MAX_WORK,
    SA_OK,
    sa_greenwood_terms,
    sa_is_finite,
    sa_risk_table,
    sa_sort_observations,
    sa_status_name,
    sa_validate_confidence,
    sa_validate_observations,
    sa_work_fits,
    sa_z_for_confidence,
)


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
    var slop = ulps * SA_DBL_EPSILON * fabs(want)
    if slop < ulps * SA_DBL_EPSILON:
        slop = ulps * SA_DBL_EPSILON
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
    print("[survival_analysis.base] hand-written known values")

    # ── 1. the wrapping multiply, and the guard that survives it ─────────────
    var wrap = 6148914691236517206
    if 3 * wrap == 2:
        passed += 1
        print("  ✅ 3 * 6148914691236517206 == 2 in this compiler: the hazard is real")
    else:
        failed += 1
        print("  ❌ the wrapping-multiply premise does not hold here")

    var pair = _i(3, wrap)
    var triple = _i(1024, 1024, 1024)
    var with_zero = _i(0, wrap, wrap)
    if (
        not sa_work_fits(pair, SA_MAX_WORK)
        and sa_work_fits(triple, SA_MAX_WORK)
        and not sa_work_fits(_i(1024, 1024, 1025), SA_MAX_WORK)
        and sa_work_fits(with_zero, SA_MAX_WORK)
        and not sa_work_fits(_i(-1, 2), SA_MAX_WORK)
        and not sa_work_fits(triple, -1)
    ):
        passed += 1
        print("  ✅ sa_work_fits refuses (3, 6148914691236517206), accepts 2^30 exactly,"
              " refuses 2^30 + 2^20, accepts any list containing a zero factor, and refuses"
              " a negative factor or a negative budget")
    else:
        failed += 1
        print("  ❌ the work-budget guard is wrong somewhere")

    # ── 2. the risk table by hand ────────────────────────────────────────────
    var t8 = _f(2.0, 3.0, 4.0, 4.0, 5.0, 6.0, 8.0, 9.0)
    var e8 = _i(1, 0, 1, 1, 0, 1, 0, 1)
    var table = sa_risk_table(t8, e8)
    if table.status != SA_OK or table.n_event_times != 4:
        failed += 1
        print("  ❌ sa_risk_table refused:", sa_status_name(table.status))
    else:
        var ok = (
            table.time[0] == 2.0
            and table.time[1] == 4.0
            and table.time[2] == 6.0
            and table.time[3] == 9.0
            and table.at_risk[0] == 8
            and table.at_risk[1] == 6
            and table.at_risk[2] == 3
            and table.at_risk[3] == 1
            and table.events[0] == 1
            and table.events[1] == 2
            and table.events[2] == 1
            and table.events[3] == 1
            and _close(table.survival[0], 0.875, 4.0)
            and _close(table.survival[1], 0.5833333333333334, 4.0)
            and _close(table.survival[2], 0.38888888888888895, 4.0)
            and table.survival[3] == 0.0
            and table.n_obs == 8
            and table.n_events == 5
            and table.n_censored == 3
            and table.monotone
        )
        if ok:
            passed += 1
            print("  ✅ risk table (2,8,1), (4,6,2), (6,3,1), (9,1,1) with S = 7/8, 7/12,"
                  " 7/18, 0 -- a censoring at exactly an event time still counts in n_j")
        else:
            failed += 1
            print("  ❌ risk table wrong")

    # ── 3. an event at time 0 is not the synthetic origin ────────────────────
    var zero = sa_risk_table(_f(0.0, 1.0), _i(1, 1))
    if zero.status == SA_OK and zero.n_event_times == 2 and zero.time[0] == 0.0:
        passed += 1
        print("  ✅ an event at t = 0 produces a row: the filter is events > 0, not"
              " 'skip index 0', so the frozen origin row is the only thing dropped")
    else:
        failed += 1
        print("  ❌ the t = 0 event was deleted with the origin row:", zero.n_event_times)

    # ── 4. Greenwood's absent marker ─────────────────────────────────────────
    var terms = sa_greenwood_terms(_i(8, 6, 3, 1), _i(1, 2, 1, 1))
    if len(terms) == 4:
        var g_ok = (
            _close(terms[0], 1.0 / 56.0, 4.0)
            and _close(terms[1], 2.0 / 24.0, 4.0)
            and _close(terms[2], 1.0 / 6.0, 4.0)
            and terms[3] == -1.0
        )
        if g_ok:
            passed += 1
            print("  ✅ Greenwood terms 1/56, 2/24, 1/6 and ABSENT (-1.0) where n_j == d_j;"
                  " -1.0 is unambiguous because every defined term is strictly positive")
        else:
            failed += 1
            print("  ❌ Greenwood terms wrong:", terms[0], terms[1], terms[2], terms[3])
    else:
        failed += 1
        print("  ❌ Greenwood terms length", len(terms))

    var mismatched = sa_greenwood_terms(_i(8, 6), _i(1, 2, 1))
    if len(mismatched) == 0:
        passed += 1
        print("  ✅ mismatched at_risk/events columns return an EMPTY list rather than"
              " indexing the shorter one -- the abort this package exists to prevent")
    else:
        failed += 1
        print("  ❌ a length mismatch was indexed anyway")

    # ── 5. ties are canonicalised ────────────────────────────────────────────
    var s1 = sa_sort_observations(_f(4.0, 4.0, 2.0), _i(0, 1, 1))
    var s2 = sa_sort_observations(_f(4.0, 2.0, 4.0), _i(1, 1, 0))
    if s1.status == SA_OK and s2.status == SA_OK:
        var same = True
        for r in range(3):
            if s1.time[r] != s2.time[r] or s1.is_event[r] != s2.is_event[r]:
                same = False
        # inside the tie at t = 4 the event comes first
        var canon = s1.time[0] == 2.0 and s1.is_event[1] and not s1.is_event[2]
        if same and canon:
            passed += 1
            print("  ✅ the same sample listed in two row orders gives identical output, and"
                  " inside a tie group the event precedes the censoring")
        else:
            failed += 1
            print("  ❌ tie canonicalisation is order-dependent")
    else:
        failed += 1
        print("  ❌ sa_sort_observations refused a valid sample")

    # ── 6. status codes ──────────────────────────────────────────────────────
    var codes = _i(900, 901, 902, 903, 904, 905, 906, 907, 908, 909, 910, 911, 912, 913,
                   914, 915, 916, 917, 918, 919, 920, 921, 922, 923, 924, 925, 926, 927,
                   928, 929, 930, 931, 932)
    var range_ok = True
    var names_ok = True
    for i in range(len(codes)):
        if codes[i] < 900 or codes[i] > 949:
            range_ok = False
        if len(sa_status_name(codes[i])) == 0 or sa_status_name(codes[i]) == "unknown_status":
            names_ok = False
        for j in range(i + 1, len(codes)):
            if sa_status_name(codes[i]) == sa_status_name(codes[j]):
                names_ok = False
    if (
        range_ok
        and names_ok
        and sa_status_name(SA_OK) == "ok"
        and sa_status_name(933) == "unknown_status"
        and sa_status_name(SA_ERR_LIKELIHOOD_UNBOUNDED) == "likelihood_unbounded_no_mle_exists"
        and sa_status_name(SA_ERR_EM_NOT_MONOTONE) == "em_log_likelihood_decreased"
    ):
        passed += 1
        print("  ✅ all 33 codes lie in 900-949, name distinctly, and the two added by the"
              " repair name the defect they report")
    else:
        failed += 1
        print("  ❌ status-code allocation broken:", range_ok, names_ok)

    # ── 7. the epsilon is the real one ───────────────────────────────────────
    if (
        1.0 + SA_DBL_EPSILON != 1.0
        and 1.0 + 0.5 * SA_DBL_EPSILON == 1.0
        and SA_DBL_EPSILON == 2.220446049250313e-16
    ):
        passed += 1
        print("  ✅ SA_DBL_EPSILON is 2^-52: 1 + eps != 1 and 1 + eps/2 == 1")
    else:
        failed += 1
        print("  ❌ SA_DBL_EPSILON is not the machine epsilon")

    # ── the validation door, one refusal per defect ───────────────────────────
    var empty_f = List[Float64]()
    var empty_i = List[Int]()
    var door = (
        sa_validate_observations(empty_f, empty_i) == SA_ERR_EMPTY
        and sa_validate_observations(_f(1.0, 2.0), _i(1)) == SA_ERR_CENSOR_LENGTH
        and sa_validate_observations(_f(1.0), _i(1, 0)) == SA_ERR_CENSOR_LENGTH
        and sa_validate_observations(_f(1.0, _nan()), _i(1, 1)) == SA_ERR_NON_FINITE_TIME
        and sa_validate_observations(_f(1.0, _inf()), _i(1, 1)) == SA_ERR_NON_FINITE_TIME
        and sa_validate_observations(_f(1.0, -2.0), _i(1, 1)) == SA_ERR_NEGATIVE_TIME
        and sa_validate_observations(_f(1.0, 2.0), _i(1, 2)) == SA_ERR_BAD_EVENT_CODE
        and sa_validate_observations(_f(1.0, 2.0), _i(1, -1)) == SA_ERR_BAD_EVENT_CODE
        and sa_validate_observations(_f(0.0, 2.0), _i(1, 1)) == SA_OK
    )
    if door:
        passed += 1
        print("  ✅ empty / short / long indicator / NaN / inf / negative time / event code 2"
              " / event code -1 each refused with their own code, and t = 0 accepted")
    else:
        failed += 1
        print("  ❌ the validation door let something through")

    # a status column recorded as 1/2 is the realistic mistake the Int code catches
    if sa_validate_observations(_f(1.0, 2.0, 3.0), _i(1, 2, 0)) == SA_ERR_BAD_EVENT_CODE:
        passed += 1
        print("  ✅ a 1/2-coded status column is refused rather than silently read as"
              " 'event' -- which is why `event` is List[Int] and not List[Bool]")
    else:
        failed += 1
        print("  ❌ a 1/2-coded status column was accepted")

    # confidence levels and the z it produces
    if (
        sa_validate_confidence(0.95) == SA_OK
        and sa_validate_confidence(0.5) == SA_OK
        and sa_validate_confidence(0.499) == SA_ERR_BAD_CONFIDENCE
        and sa_validate_confidence(1.0) == SA_ERR_BAD_CONFIDENCE
        and sa_validate_confidence(_nan()) == SA_ERR_BAD_CONFIDENCE
        and _close(sa_z_for_confidence(0.95), 1.959963984540054, 1e8)
        and sa_z_for_confidence(1.0) == 0.0
        and sa_z_for_confidence(0.999999) < 5.0
    ):
        passed += 1
        print("  ✅ conf_level in [0.5, 0.999999] only, z(0.95) = 1.959963984540054, and a"
              " refused level yields z = 0 rather than norm_ppf's 1e300 sentinel")
    else:
        failed += 1
        print("  ❌ confidence validation or z wrong:", sa_z_for_confidence(0.95))

    if sa_is_finite(1.0) and not sa_is_finite(_nan()) and not sa_is_finite(_inf()):
        passed += 1
        print("  ✅ sa_is_finite agrees with the frozen numeric.reduce definition")
    else:
        failed += 1
        print("  ❌ sa_is_finite is wrong")

    if SA_MAX_OBS == 1048576 and SA_MAX_WORK == 1073741824:
        passed += 1
        print("  ✅ the ceilings are 2^20 observations and 2^30 work units")
    else:
        failed += 1
        print("  ❌ a ceiling drifted:", SA_MAX_OBS, SA_MAX_WORK)

    var lf5 = _f(0.5, 0.5, 0.5, 0.5, 0.5)
    var li5 = _i(5, 5, 5, 5, 5)
    if (
        sa_validate_observations(lf5, li5) == SA_ERR_BAD_EVENT_CODE
        and sa_risk_table(lf5, li5).status == SA_ERR_BAD_EVENT_CODE
        and len(sa_greenwood_terms(li5, li5)) == 5
        and not sa_work_fits(li5, 5)
    ):
        passed += 1
        print("  ✅ the fixed 5-element/5-integer harness pattern is handled, not indexed")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern was mishandled")

    print("  [survival_analysis.base] Passed:", passed, "Failed:", failed)
