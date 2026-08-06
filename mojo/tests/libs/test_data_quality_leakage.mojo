"""test_data_quality_leakage.mojo — known-value tests for provable vs suspicious leakage.

Hand-written. Every number is derived below or taken from a named reference.

Target used throughout: `y = [1, 2, 3, 4, 5]`.

1. PROVEN COPY. feature = y. Identical masks, identical values.
2. PROVEN AFFINE. feature = [8, 11, 14, 17, 20] = 3y + 5. The two-point map is derived from
   the smallest and largest target: slope = (20 - 8)/(5 - 1) = 3, intercept = 8 - 3*1 = 5,
   and every row's residual is exactly 0.
3. SUSPICIOUS ONLY. feature = y^2 = [1, 4, 9, 16, 25]. Pearson r, by hand:
       mean(x) = 55/5 = 11,  mean(y) = 3
       Sxy = (-10)(-2) + (-7)(-1) + (-2)(0) + (5)(1) + (14)(2) = 20 + 7 + 0 + 5 + 28 = 60
       Sxx = 100 + 49 + 4 + 25 + 196 = 374
       Syy = 4 + 1 + 0 + 1 + 4 = 10
       r   = 60 / sqrt(374 * 10) = 60 / sqrt(3740) = 60 / 61.155539405682624
           = 0.9811049102515929
   The affine candidate from the endpoints is slope = (25 - 1)/(5 - 1) = 6,
   intercept = 1 - 6 = -5, so at y = 3 it predicts 13 against an actual 9 — a residual of
   exactly 4.0. A correlation of 0.98 with a residual of 4 is the case that must come back
   SUSPICIOUS and not proven.
4. NO SIGNAL. feature = [5, -2, 7, -1, 0.5]:
       mean(x) = 1.9,  Sxy = -8.0,  Sxx = 61.199999999999996,  Syy = 10
       |r| = 8 / sqrt(611.99999999999996) = 0.3233808333817773
5. TIMING. feature_time = [10, 20, 45, 40, 50], target_time = [15, 25, 30, 40, 60]. Only row
   2 has feature_time > target_time, with a lead of 45 - 30 = 15. Row 3 is EQUAL and is
   counted as simultaneous, not as proof.

The Pearson digits are the closed-form value above; the residual, slope, intercept, lead and
counts are all integers or exact halves readable straight off the vectors.

The four wrong answers this suite now pins, and where each expected value comes from
--------------------------------------------------------------------------------------
6. NOT A FUNCTION OF THE TARGET AT ALL. target = [1, 1+ulp, 1, 1, 1] where ulp is
   2.220446049250313e-16, feature = y = [1, 2, 3, 4, 5]. No floating point is needed to
   settle this: rows 0, 2, 3 and 4 all carry target exactly 1.0 while the feature there is
   1, 3, 4 and 5. An affine map is a FUNCTION, so equal inputs must give equal outputs, and
   no function of any kind can produce that column. The endpoint fit is
   slope = (2 - 1)/2.220446049250313e-16 = 4503599627370496 (which is 2^52),
   intercept = 1 - 2^52 = -4503599627370495, and at target 1.0 it predicts exactly 1.0, so
   row 4's residual is |5 - 1| = 4.0. That residual is IDENTICAL to case 3's, and the two
   must therefore reach the SAME verdict — case 3 asserts residual 4.0 with NOT proven, so
   this must too. It did not: it returned PROVEN, decided only by the target's spread.
7. AN ILL-CONDITIONED FIT ON ORDINARY DATA. An epoch-nanosecond timestamp target,
   1.7e18 + [0, 1024, 2048, 3072], against feature = [1, 50, 2, 90]. ulp(1.7e18) is 256, so
   every target value and every difference is exact and the target is an exact arithmetic
   progression with step 1024. An affine image of an arithmetic progression is an arithmetic
   progression; the feature's differences are [49, -48, 88], so it is not one. Endpoint fit:
   slope = 89/3072 = 0.028971354166666668, intercept = 1 - slope*1.7e18 =
   -4.9251302083333336e16. Predictions, recomputed independently in CPython with the same
   two-step rounding (`p = slope*t; p + intercept`): [0.0, 32.0, 56.0, 88.0], so the
   residuals are [1.0, 18.0, 54.0, 2.0] and the maximum is 54.0 at row 2.
   |r| = 0.6607454795729699. A 42% prediction error on a feature correlating 0.66 was
   returned as PROOF, because the tolerance was scaled by the two cancelling intermediates
   (each ~4.93e16, giving a slack of ~350) instead of by the value being judged.
8. A CONSTANT FEATURE. feature = [7, 7, 7, 7, 7] and separately all-zeros, target = y.
   `f(t) = c` fits slope 0, intercept c with residual exactly 0 on every row, so the
   arithmetic "proves" it — and computing a constant column requires zero knowledge of the
   target. The struct was self-refuting: PROVEN leakage beside `has_pearson = False`.
9. AN OVERFLOWING LEAD. feature_time = [1e308, 5, 5], target_time = [-1e308, 10, 30]. Row
   0's lead is 1e308 - (-1e308), which overflows binary64 (CPython: `inf`). The largest lead
   is therefore not a representable number, so it must be ABSENT. The reported value was
   `has_max_future_lead = True` with `max_future_lead = 0.0` — the one reading the docs say
   is impossible, because 0.0 under a True flag means simultaneity. The mixed case
   feature_time = [1e308, 20, 5] adds a second future row with a lead of exactly 10.0, and
   reporting 10.0 as the maximum understates row 0's lead without bound.
"""
from data_quality.contract import (
    DQ_ERR_LENGTH_MISMATCH,
    DQ_ERR_MASK_LENGTH,
    DQ_OK,
    dq_is_finite,
    dq_mask_all_valid,
)
from data_quality.leakage import (
    DQ_LEAK_ERR_THRESHOLD,
    DQ_LEAK_INSUFFICIENT,
    DQ_LEAK_NONE,
    DQ_LEAK_PROVEN_AFFINE,
    DQ_LEAK_PROVEN_FUTURE,
    DQ_LEAK_PROVEN_TARGET_COPY,
    DQ_LEAK_SUSPICIOUS,
    LeakageReport,
    LeakageTimingReport,
    leakage_scan_flat,
    leakage_status_name,
    leakage_timing_flat,
)


def _nan() -> Float64:
    var zero: Float64 = 0.0
    return zero / zero


def _f5(a: Float64, b: Float64, c: Float64, d: Float64, e: Float64) -> List[Float64]:
    var o = List[Float64]()
    o.append(a)
    o.append(b)
    o.append(c)
    o.append(d)
    o.append(e)
    return o^


def _b5(a: Bool, b: Bool, c: Bool, d: Bool, e: Bool) -> List[Bool]:
    var o = List[Bool]()
    o.append(a)
    o.append(b)
    o.append(c)
    o.append(d)
    o.append(e)
    return o^


def _slots_finite(r: LeakageReport) -> Bool:
    return (
        dq_is_finite(r.affine_slope)
        and dq_is_finite(r.affine_intercept)
        and dq_is_finite(r.affine_max_residual)
        and dq_is_finite(r.abs_pearson)
        and dq_is_finite(r.missingness_agreement)
    )


def check():
    var passed = 0
    var failed = 0
    var m5 = dq_mask_all_valid(5)
    var y = _f5(1.0, 2.0, 3.0, 4.0, 5.0)

    # ── 1. the feature IS the target ──────────────────────────────────────────
    var copy = leakage_scan_flat(y, m5, y, m5, 5, 0.95, 0.95)
    if copy.status == DQ_OK and copy.proven_target_copy and copy.verdict == DQ_LEAK_PROVEN_TARGET_COPY:
        passed += 1
        print("  ✅ a feature identical to the target is PROVEN, not merely correlated")
    else:
        failed += 1
        print("  ❌ target copy not proven:", leakage_status_name(copy.verdict))

    if copy.has_pearson and copy.abs_pearson == 1.0 and copy.n_compared == 5:
        passed += 1
        print("  ✅ its correlation is 1.0, and that is reported beside the proof, not as it")
    else:
        failed += 1
        print("  ❌ correlation missing on the copy case")

    # ── 2. an exact affine image ──────────────────────────────────────────────
    var affine = leakage_scan_flat(_f5(8.0, 11.0, 14.0, 17.0, 20.0), m5, y, m5, 5, 0.95, 0.95)
    if affine.proven_affine and affine.verdict == DQ_LEAK_PROVEN_AFFINE:
        passed += 1
        print("  ✅ feature = 3*target + 5 is proven as a deterministic function")
    else:
        failed += 1
        print("  ❌ the affine relation was not proven:", leakage_status_name(affine.verdict))

    if affine.has_affine and affine.affine_slope == 3.0 and affine.affine_intercept == 5.0:
        passed += 1
        print("  ✅ the recovered map is exactly slope 3.0, intercept 5.0")
    else:
        failed += 1
        print("  ❌ recovered map wrong:", affine.affine_slope, affine.affine_intercept)

    if affine.has_affine_residual and affine.affine_max_residual == 0.0 and not affine.proven_target_copy:
        passed += 1
        print("  ✅ max residual 0.0, and it is an affine image rather than a copy")
    else:
        failed += 1
        print("  ❌ residual/copy classification wrong:", affine.affine_max_residual)

    # ── 3. high correlation is SUSPICIOUS, never proof ────────────────────────
    var quad = leakage_scan_flat(_f5(1.0, 4.0, 9.0, 16.0, 25.0), m5, y, m5, 5, 0.90, 0.95)
    if quad.has_pearson and quad.abs_pearson == 0.9811049102515929:
        passed += 1
        print("  ✅ |r| = 60/sqrt(3740) = 0.9811049102515929, matching the closed form")
    else:
        failed += 1
        print("  ❌ Pearson wrong:", quad.abs_pearson)

    if quad.suspicious_correlation and not quad.proven_affine and quad.verdict == DQ_LEAK_SUSPICIOUS:
        passed += 1
        print("  ✅ 0.98 correlation is SUSPICIOUS and explicitly not proven")
    else:
        failed += 1
        print("  ❌ a correlation was promoted to a proof:", leakage_status_name(quad.verdict))

    if quad.has_affine and quad.affine_slope == 6.0 and quad.affine_intercept == -5.0 and quad.affine_max_residual == 4.0:
        passed += 1
        print("  ✅ the best affine candidate (6x - 5) has max residual exactly 4.0")
    else:
        failed += 1
        print(
            "  ❌ affine candidate wrong:",
            quad.affine_slope, quad.affine_intercept, quad.affine_max_residual,
        )

    if quad.affine_worst_row == 2:
        passed += 1
        print("  ✅ the worst row is named: row 2, where 6*3-5 = 13 against an actual 9")
    else:
        failed += 1
        print("  ❌ the worst row was not addressed:", quad.affine_worst_row)

    # A threshold above the observed correlation must clear the flag: the flag is the
    # caller's declared line, not a property of the data.
    var quad_strict = leakage_scan_flat(_f5(1.0, 4.0, 9.0, 16.0, 25.0), m5, y, m5, 5, 0.99, 0.95)
    if not quad_strict.suspicious_correlation and quad_strict.verdict == DQ_LEAK_NONE:
        passed += 1
        print("  ✅ raising the threshold to 0.99 clears the flag — the line is the caller's")
    else:
        failed += 1
        print("  ❌ the correlation threshold is not respected")

    # ── 4. no signal ──────────────────────────────────────────────────────────
    var noise = leakage_scan_flat(_f5(5.0, -2.0, 7.0, -1.0, 0.5), m5, y, m5, 5, 0.90, 0.95)
    if noise.has_pearson and noise.abs_pearson == 0.3233808333817773 and noise.verdict == DQ_LEAK_NONE:
        passed += 1
        print("  ✅ |r| = 0.3233808333817773 and the verdict is no signal")
    else:
        failed += 1
        print("  ❌ the no-signal case is wrong:", noise.abs_pearson, leakage_status_name(noise.verdict))

    # ── absence, not zero: a correlation that cannot exist is ABSENT ──────────
    var short_y = _f5(1.0, 2.0, 0.0, 0.0, 0.0)
    var two_only = _b5(True, True, False, False, False)
    var two_rows = leakage_scan_flat(_f5(3.0, 9.0, 0.0, 0.0, 0.0), two_only, short_y, two_only, 5, 0.5, 0.95)
    if two_rows.n_compared == 2 and not two_rows.has_pearson and two_rows.abs_pearson == 0.0:
        passed += 1
        print("  ✅ two compared rows: no correlation exists, and it is ABSENT not 0.0")
    else:
        failed += 1
        print("  ❌ a two-row correlation was reported:", two_rows.has_pearson)

    # `stat_tests.pearson_r` returns r = 0.0 for a constant column too, which is
    # indistinguishable from a real zero. The precondition is decided before the call.
    var const_feature = _f5(7.0, 7.0, 7.0, 7.0, 7.0)
    var const_scan = leakage_scan_flat(const_feature, m5, y, m5, 5, 0.5, 0.95)
    if const_scan.feature_constant_on_compared and not const_scan.has_pearson:
        passed += 1
        print("  ✅ a constant feature has no correlation, reported absent rather than 0.0")
    else:
        failed += 1
        print("  ❌ a constant feature produced a correlation")

    # ── 8. a CONSTANT feature is not leakage, however exactly it fits ─────────
    # `f(t) = 7` satisfies slope 0, intercept 7 with residual 0 on every row. The
    # arithmetic proves it and the finding is worthless: a constant column can be computed
    # without ever seeing the target. This input used to return the module's HIGHEST
    # severity verdict (433, proven affine image) while `has_pearson` said the correlation
    # could not even be computed — one struct making two contradictory claims.
    if (
        const_scan.verdict == DQ_LEAK_NONE
        and not const_scan.proven_affine
        and not const_scan.has_affine
        and const_scan.affine_slope == 0.0
        and const_scan.affine_intercept == 0.0
    ):
        passed += 1
        print("  ✅ a constant feature is NO SIGNAL, not a proof — f(t)=7 needs no target")
    else:
        failed += 1
        print(
            "  ❌ a constant feature was reported as leakage:",
            leakage_status_name(const_scan.verdict),
            const_scan.proven_affine, const_scan.affine_slope, const_scan.affine_intercept,
        )

    # An all-DEFAULT / all-zero column is the common shape of this in a real table, and it
    # must not hard-block a pipeline on the highest-severity verdict either.
    var zeros_scan = leakage_scan_flat(_f5(0.0, 0.0, 0.0, 0.0, 0.0), m5, y, m5, 5, 0.5, 0.95)
    if (
        zeros_scan.verdict == DQ_LEAK_NONE
        and not zeros_scan.proven_affine
        and zeros_scan.feature_constant_on_compared
    ):
        passed += 1
        print("  ✅ an all-zeros column is the same answer: no signal, not proven leakage")
    else:
        failed += 1
        print("  ❌ an all-zeros column was reported as leakage:", zeros_scan.verdict)

    # ── 6. a feature that is not a FUNCTION of the target cannot be its image ─
    # target = [1, 1+ulp, 1, 1, 1]: four rows carry target exactly 1.0 while the feature
    # there is 1, 3, 4, 5. Equal inputs, four different outputs — not a function, so not an
    # affine one. The endpoint fit is slope 2^52, intercept 1 - 2^52, predicting 1.0 at
    # target 1.0, so row 4's residual is |5 - 1| = 4.0.
    var one_ulp_up: Float64 = 1.0000000000000002
    var flat_target = _f5(1.0, one_ulp_up, 1.0, 1.0, 1.0)
    var ill = leakage_scan_flat(y, m5, flat_target, m5, 5, 0.95, 0.95)
    if (
        ill.status == DQ_OK
        and not ill.proven_affine
        and ill.verdict == DQ_LEAK_NONE
        and ill.affine_max_residual == 4.0
    ):
        passed += 1
        print("  ✅ a column that is not a function of the target is NOT its affine image")
    else:
        failed += 1
        print(
            "  ❌ a non-function was proven affine:",
            leakage_status_name(ill.verdict), ill.proven_affine, ill.affine_max_residual,
        )

    # THE INVARIANT the two cases share, and the contradiction that used to sit between
    # them: identical worst residual, so identical verdict on `proven_affine`. Case 3
    # (feature = y^2) also reports 4.0 and is NOT proven. The old code decided the two
    # differently, using only the target's spread.
    if (
        ill.affine_max_residual == quad.affine_max_residual
        and ill.proven_affine == quad.proven_affine
        and not ill.proven_affine
    ):
        passed += 1
        print("  ✅ the same worst residual (4.0) gets the same verdict on both inputs")
    else:
        failed += 1
        print(
            "  ❌ residual 4.0 decided two ways:",
            ill.affine_max_residual, ill.proven_affine,
            quad.affine_max_residual, quad.proven_affine,
        )

    # ── 7. an ill-conditioned fit on ordinary data: epoch nanoseconds ────────
    # Target 1.7e18 + [0, 1024, 2048, 3072] is an exact arithmetic progression (ulp(1.7e18)
    # is 256). An affine image of one is one; the feature's steps are [49, -48, 88].
    # Residuals recomputed in CPython: [1.0, 18.0, 54.0, 2.0], max 54.0 at row 2.
    var epoch_base: Float64 = 1.7e18
    var epoch_t = List[Float64]()
    epoch_t.append(epoch_base)
    epoch_t.append(epoch_base + 1024.0)
    epoch_t.append(epoch_base + 2048.0)
    epoch_t.append(epoch_base + 3072.0)
    var epoch_f = List[Float64]()
    epoch_f.append(1.0)
    epoch_f.append(50.0)
    epoch_f.append(2.0)
    epoch_f.append(90.0)
    var m4 = dq_mask_all_valid(4)
    var epoch = leakage_scan_flat(epoch_f, m4, epoch_t, m4, 4, 0.95, 0.95)
    if (
        epoch.status == DQ_OK
        and not epoch.proven_affine
        and epoch.verdict == DQ_LEAK_NONE
        and epoch.affine_max_residual == 54.0
        and epoch.affine_worst_row == 2
    ):
        passed += 1
        print("  ✅ a 54.0 residual on a 0.66-correlated feature is not a proof of anything")
    else:
        failed += 1
        print(
            "  ❌ an ill-conditioned two-point fit was proven exact:",
            epoch.proven_affine, epoch.affine_max_residual, epoch.affine_worst_row,
        )

    if epoch.has_pearson and epoch.abs_pearson == 0.6607454795729699:
        passed += 1
        print("  ✅ |r| = 0.6607454795729699 on that feature, and 0.66 proves nothing")
    else:
        failed += 1
        print("  ❌ the epoch-target correlation is wrong:", epoch.abs_pearson)

    # The tolerance is built from the magnitude of the ROW BEING JUDGED, so a target with a
    # huge magnitude and a narrow range cannot buy slack. 16*eps*|f_i| at |f_i| = 90 is
    # 3.197e-13; the smallest residual above is 1.0, twelve orders of magnitude larger.
    var tol_at_90 = 16.0 * 2.220446049250313e-16 * 90.0
    if epoch.affine_max_residual > tol_at_90 and tol_at_90 < 1.0e-12:
        passed += 1
        print("  ✅ the per-row tolerance stays at 3.2e-13, not the 350 the intermediates gave")
    else:
        failed += 1
        print("  ❌ the tolerance is not scaled by the judged row:", tol_at_90)

    var const_target = leakage_scan_flat(y, m5, const_feature, m5, 5, 0.5, 0.95)
    if const_target.target_constant_on_compared and const_target.verdict == DQ_LEAK_INSUFFICIENT:
        passed += 1
        print("  ✅ a constant target has no learning problem: INSUFFICIENT, not NONE")
    else:
        failed += 1
        print("  ❌ a constant target was scored:", leakage_status_name(const_target.verdict))

    # ── missingness as a label ────────────────────────────────────────────────
    # A binary target [0,0,1,1,1] with the feature present exactly on the two zero rows:
    # "absent -> class 1" is right on all five rows, so agreement is 1.0. The compared set
    # is only the two present rows, so the value-based checks cannot see this at all —
    # which is why INSUFFICIENT must not outrank SUSPICIOUS.
    var binary_y = _f5(0.0, 0.0, 1.0, 1.0, 1.0)
    var present_on_zeros = _b5(True, True, False, False, False)
    var miss = leakage_scan_flat(_f5(3.0, 4.0, 0.0, 0.0, 0.0), present_on_zeros, binary_y, m5, 5, 0.99, 0.95)
    if miss.has_missingness_agreement and miss.missingness_agreement == 1.0 and miss.suspicious_missingness:
        passed += 1
        print("  ✅ missingness predicts the class perfectly: agreement 1.0, flagged")
    else:
        failed += 1
        print("  ❌ missingness check wrong:", miss.missingness_agreement)

    if miss.verdict == DQ_LEAK_SUSPICIOUS:
        passed += 1
        print("  ✅ SUSPICIOUS outranks INSUFFICIENT, so the finding is not hidden")
    else:
        failed += 1
        print("  ❌ the missingness finding was suppressed:", leakage_status_name(miss.verdict))

    # Not a binary target -> the question does not apply, and the answer is ABSENT.
    if not noise.has_missingness_agreement and noise.missingness_agreement == 0.0:
        passed += 1
        print("  ✅ a five-valued target is not binary, so missingness agreement is absent")
    else:
        failed += 1
        print("  ❌ a non-binary target produced a missingness number")

    # Every row present -> the rule degenerates to "predict the majority", which measures
    # the target's balance rather than the feature. Absent.
    var all_present = leakage_scan_flat(_f5(3.0, 4.0, 5.0, 6.0, 7.0), m5, binary_y, m5, 5, 0.99, 0.95)
    if not all_present.has_missingness_agreement:
        passed += 1
        print("  ✅ with nothing absent there is no missingness signal to measure")
    else:
        failed += 1
        print("  ❌ a degenerate missingness rule was reported as a measurement")

    # ── what this module cannot see, said out loud ────────────────────────────
    if (
        not copy.temporal_checked
        and not affine.temporal_checked
        and not quad.temporal_checked
        and not noise.temporal_checked
    ):
        passed += 1
        print("  ✅ temporal_checked is False in every data-only report, including the clean one")
    else:
        failed += 1
        print("  ❌ a data-only report claimed a temporal check")

    if _slots_finite(copy) and _slots_finite(quad) and _slots_finite(two_rows) and _slots_finite(const_scan):
        passed += 1
        print("  ✅ no leakage report holds a raw non-finite in any value slot")
    else:
        failed += 1
        print("  ❌ a non-finite reached a value slot")

    # A NaN is excluded from the compared set, never propagated into a coefficient.
    var with_nan = leakage_scan_flat(_f5(8.0, 11.0, _nan(), 17.0, 20.0), m5, y, m5, 5, 0.95, 0.95)
    if with_nan.n_compared == 4 and with_nan.proven_affine and with_nan.abs_pearson == 1.0:
        passed += 1
        print("  ✅ a NaN row is excluded (4 compared) and the remaining rows still prove 3y+5")
    else:
        failed += 1
        print("  ❌ a NaN changed the verdict:", with_nan.n_compared, with_nan.abs_pearson)

    # ── the one proof of future information ──────────────────────────────────
    var timing = leakage_timing_flat(
        _f5(10.0, 20.0, 45.0, 40.0, 50.0), _f5(15.0, 25.0, 30.0, 40.0, 60.0), m5, 5
    )
    if (
        timing.status == DQ_OK
        and timing.proven_future_information
        and timing.verdict == DQ_LEAK_PROVEN_FUTURE
        and timing.n_future_rows == 1
        and timing.first_future_row == 2
    ):
        passed += 1
        print("  ✅ row 2's feature was observed after the target event — proven, and addressed")
    else:
        failed += 1
        print("  ❌ the timing proof failed:", timing.n_future_rows, timing.first_future_row)

    if timing.has_max_future_lead and timing.max_future_lead == 15.0 and timing.n_compared == 5:
        passed += 1
        print("  ✅ the lead is 45 - 30 = 15.0, so skew and lookahead are distinguishable")
    else:
        failed += 1
        print("  ❌ the lead is wrong:", timing.max_future_lead)

    if timing.n_simultaneous_rows == 1:
        passed += 1
        print("  ✅ the equal-timestamp row is counted as simultaneous, NOT as proof")
    else:
        failed += 1
        print("  ❌ a tie was treated as leakage:", timing.n_simultaneous_rows)

    var clean_timing = leakage_timing_flat(_f5(1.0, 2.0, 3.0, 4.0, 5.0), _f5(9.0, 9.0, 9.0, 9.0, 9.0), m5, 5)
    if (
        clean_timing.verdict == DQ_LEAK_NONE
        and not clean_timing.proven_future_information
        and not clean_timing.has_max_future_lead
        and clean_timing.max_future_lead == 0.0
        and clean_timing.n_unrepresentable_lead_rows == 0
    ):
        passed += 1
        print("  ✅ no future row means the lead is ABSENT, not 0.0 (0.0 would mean a tie)")
    else:
        failed += 1
        print("  ❌ a clean timing report reported a lead")

    # ── 9. a lead that OVERFLOWS is absent, never 0.0 and never the runner-up ─
    # feature_time[0] - target_time[0] = 1e308 - (-1e308) = +inf. The proof stands (row 0 is
    # still a future row) but the SIZE of the largest lead does not exist, so the flag must
    # be False with the slot at 0.0. This returned has=True with 0.0 — the one reading the
    # docstring promises is impossible, because 0.0 under a True flag means simultaneity.
    var huge: Float64 = 1.0e308
    var m3t = dq_mask_all_valid(3)
    var overflow_f = List[Float64]()
    overflow_f.append(huge)
    overflow_f.append(5.0)
    overflow_f.append(5.0)
    var overflow_t = List[Float64]()
    overflow_t.append(-huge)
    overflow_t.append(10.0)
    overflow_t.append(30.0)
    var over = leakage_timing_flat(overflow_f, overflow_t, m3t, 3)
    if (
        over.status == DQ_OK
        and over.verdict == DQ_LEAK_PROVEN_FUTURE
        and over.n_future_rows == 1
        and over.n_unrepresentable_lead_rows == 1
        and not over.has_max_future_lead
        and over.max_future_lead == 0.0
    ):
        passed += 1
        print("  ✅ an overflowing lead is ABSENT — the proof stands, the magnitude does not")
    else:
        failed += 1
        print(
            "  ❌ an unrepresentable lead was reported as a measurement:",
            over.has_max_future_lead, over.max_future_lead,
            over.n_unrepresentable_lead_rows,
        )

    # The mixed case is the understatement: one row leads by 2e308 and another by exactly
    # 10.0. Reporting 10.0 would call an astronomical lookahead a ten-unit clock skew, which
    # is precisely the distinction this field exists to make.
    var mixed_f = List[Float64]()
    mixed_f.append(huge)
    mixed_f.append(20.0)
    mixed_f.append(5.0)
    var mixed_lead = leakage_timing_flat(mixed_f, overflow_t, m3t, 3)
    if (
        mixed_lead.n_future_rows == 2
        and mixed_lead.n_unrepresentable_lead_rows == 1
        and not mixed_lead.has_max_future_lead
        and mixed_lead.max_future_lead == 0.0
    ):
        passed += 1
        print("  ✅ one overflowing row makes the MAXIMUM absent, not the largest of the rest")
    else:
        failed += 1
        print(
            "  ❌ the maximum lead understated an overflow:",
            mixed_lead.has_max_future_lead, mixed_lead.max_future_lead,
        )

    # And the all-finite version of the same shape still reports the lead: 20 - 10 = 10.0.
    var finite_f = List[Float64]()
    finite_f.append(1.0)
    finite_f.append(20.0)
    finite_f.append(5.0)
    var finite_t = List[Float64]()
    finite_t.append(0.0)
    finite_t.append(10.0)
    finite_t.append(30.0)
    var finite_lead = leakage_timing_flat(finite_f, finite_t, m3t, 3)
    if (
        finite_lead.n_future_rows == 2
        and finite_lead.n_unrepresentable_lead_rows == 0
        and finite_lead.has_max_future_lead
        and finite_lead.max_future_lead == 10.0
    ):
        passed += 1
        print("  ✅ with every lead representable the maximum is reported: 20 - 10 = 10.0")
    else:
        failed += 1
        print("  ❌ a representable maximum went missing:", finite_lead.max_future_lead)

    var nothing_observed = _b5(False, False, False, False, False)
    if leakage_timing_flat(y, y, nothing_observed, 5).verdict == DQ_LEAK_INSUFFICIENT:
        passed += 1
        print("  ✅ no observed row means nothing can be decided, not 'no leakage'")
    else:
        failed += 1
        print("  ❌ an empty timing comparison reported no leakage")

    # ── refusals ──────────────────────────────────────────────────────────────
    if (
        leakage_scan_flat(y, m5, y, m5, 5, 1.5, 0.5).status == DQ_LEAK_ERR_THRESHOLD
        and leakage_scan_flat(y, m5, y, m5, 5, -0.1, 0.5).status == DQ_LEAK_ERR_THRESHOLD
        and leakage_scan_flat(y, m5, y, m5, 5, 0.5, _nan()).status == DQ_LEAK_ERR_THRESHOLD
    ):
        passed += 1
        print("  ✅ a threshold outside [0,1], or a NaN one, is refused")
    else:
        failed += 1
        print("  ❌ an unusable threshold was accepted")

    if leakage_scan_flat(y, m5, y, m5, 4, 0.5, 0.5).status == DQ_ERR_MASK_LENGTH:
        passed += 1
        print("  ✅ a mask that does not describe exactly n_rows is refused")
    else:
        failed += 1
        print("  ❌ a mismatched mask was accepted")

    var short_values = List[Float64]()
    short_values.append(1.0)
    if (
        leakage_scan_flat(short_values, m5, y, m5, 5, 0.5, 0.5).status == DQ_ERR_LENGTH_MISMATCH
        and leakage_timing_flat(short_values, y, m5, 5).status == DQ_ERR_LENGTH_MISMATCH
    ):
        passed += 1
        print("  ✅ n_rows greater than a value list is refused before any read")
    else:
        failed += 1
        print("  ❌ a caller's oversized count was trusted")

    # The A-Z shape: 5-element lists and 5 for every Int.
    var lf5 = _f5(0.5, 0.6, 0.7, 0.4, 0.3)
    var lb5 = _b5(True, False, True, True, False)
    if (
        leakage_scan_flat(lf5, lb5, lf5, lb5, 5, 0.5, 0.5).status == DQ_OK
        and leakage_timing_flat(lf5, lf5, lb5, 5).status == DQ_OK
    ):
        passed += 1
        print("  ✅ the A-Z argument shape completes with a status and nothing aborts")
    else:
        failed += 1
        print("  ❌ the A-Z shape behaved unexpectedly")

    print("  [data_quality.leakage] Passed:", passed, "Failed:", failed)


def main():
    check()
