"""test_inference_assume.mojo — known-value tests for the assumption-checking drivers.

Hand-written. Every statistic below is hand-computed and every closed form is stated.

*Levene's test, computed on paper.* Two groups of four: `[0,0,0,0]` and `[-10,0,0,10]`.
Medians 0 and 0, so the absolute deviations are `[0,0,0,0]` and `[10,0,0,10]`, group means of
deviation 0 and 5, grand mean 2.5. Then

    between = 4 (0 - 2.5)^2 + 4 (5 - 2.5)^2 = 25 + 25 = 50
    within  = 0 + [(10-5)^2 + (0-5)^2 + (0-5)^2 + (10-5)^2] = 100
    F       = ((8 - 2) / (2 - 1)) * 50 / 100 = 3.0        exactly, on 1 and 6 df

and `P(F_{1,6} >= 3)` has the elementary closed form `(2 - sqrt(3)) / 2 = 0.1339745962155614`.
So this one input pins the statistic exactly AND its tail against a closed form. The variance
ratio is reported as absent because the first group's variance is exactly 0 — an infinite ratio
is not a number, and 0 in the denominator is not "infinitely heterogeneous".

*The chi-squared cell condition.* Observed `[10,20,30,40]` against expected `[25,25,25,25]`
gives `chi2 = (225 + 25 + 25 + 225) / 25 = 20.0` exactly on 3 df. The frozen tail returns
1.697428291143055e-4; the closed form for 3 degrees of freedom,
`erfc(sqrt(x/2)) + sqrt(2x/pi) e^{-x/2}` evaluated in double precision, is
1.6974243555282643e-4, so the frozen `_chi2_cdf` is accurate to 4e-9 absolute here — which is
why `inference.core` does NOT replace it, unlike the incomplete beta.

*The t-test, and the frozen defect it used to expose.* `[1,2,3]` against `[4,5,6]`: equal
variances of 1.0 and equal group sizes, so the Welch degrees of freedom are exactly
`2(n-1) = 4` and the statistic is `-3 / sqrt(2/3) = -3.6742346141747673`. The corrected
two-sided p is 0.021311641133773648. `stat_tests._regularized_incomplete_beta` used to be
defective, which made `stat_tests.t_test_2sample` return **p_value = 0.0 with
reject_h0 = True** for this data (its tail came out above 1 and its own clamp turned a
negative p-value into zero); it is fixed as of this session (see `inference.core`'s module
docstring), and `t_test_2sample` now returns `p_value = 0.021311641136474657` — within
2.7e-12 of the corrected value above. Both numbers are asserted, and `frozen_p_value_usable`
is now True: agreement between two independent implementations, not a known defect, is the
module's ongoing cross-check.

*The proportion test.* 30/100 against 45/100: pooled `p = 0.375`, so
`se = sqrt(0.375 * 0.625 * 0.02) = 0.06846531968814577` and `z = -0.15 / se = -2.1908902300206647`.
The corrected two-sided p is 0.028459637652763714 and the frozen kernel's is
0.028459636522371046 — these two agree (to 1.1e-9), because the frozen proportion test's
normal CDF was always sound; `frozen_p_value_usable` is True here, as it now also is for the
t-test above, since both frozen tails are correct. And `z_test_proportions(0, 0, 0, 0)` divides
by zero and produces NaN, which `is_significant(nan)` reads as "not significant" — that request
is refused here.
"""
from std.math import abs as fabs, sqrt

from ab_testing import confidence_interval_proportion, z_test_proportions
from inference.assume import (
    ASSUME_P_ABSENT,
    CHI2_MIN_EXPECTED_CONVENTION,
    METHOD_CHI2_CELLS,
    METHOD_LEVENE_MEDIAN,
    METHOD_NORMALITY_PAIR,
    METHOD_TWO_PROPORTION_Z,
    METHOD_WELCH,
    AssumptionVerdict,
    CellCountVerdict,
    NormalityVerdict,
    expected_counts_flat,
    proportion_test_checked_flat,
    residual_normality_flat,
    t_test_checked_flat,
    variance_homogeneity_flat,
)
from inference.core import (
    INF_ERR_ALPHA_RANGE,
    INF_ERR_DEGENERATE,
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_EMPTY,
    INF_ERR_GROUPS,
    INF_ERR_NON_FINITE,
    INF_ERR_PVALUE_RANGE,
    INF_ERR_RESPONSE_RANGE,
    INF_ERR_SHAPE,
    INF_ERR_TOO_FEW,
    INF_OK,
    MAX_ASSUME_OBS,
    inference_absent,
    inference_f_sf,
    inference_t_sf_two_sided,
)
from stat_tests import anderson_darling_normal, shapiro_wilk_approx, t_test_2sample


def _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _no_verdict(v: AssumptionVerdict) -> Bool:
    """A refusal has no statistic, no p-value and no verdict."""
    return (
        v.status != INF_OK
        and v.p_value == ASSUME_P_ABSENT
        and not v.satisfied
        and v.df1 == -1.0
        and v.df2 == -1.0
    )


def main():
    var passed: Int = 0
    var failed: Int = 0

    # ── 1. Levene, hand-computed to F = 3.0 exactly ───────────────────────────
    var groups = _floats(0.0, 0.0, 0.0, 0.0, -10.0, 0.0, 0.0, 10.0)
    var lengths = _ints(4, 4)
    var lev = variance_homogeneity_flat(groups, lengths, 0.05)
    var f_closed = (2.0 - sqrt(3.0)) / 2.0
    if (
        lev.status == INF_OK
        and lev.method == METHOD_LEVENE_MEDIAN
        # the statistic is exact arithmetic on integers, so this is bitwise
        and lev.statistic == 3.0
        and lev.df1 == 1.0
        and lev.df2 == 6.0
        # and its tail has the closed form (2 - sqrt 3)/2
        and fabs(lev.p_value - f_closed) <= 1.0e-8
        and fabs(lev.p_value - 0.1339745962155614) <= 1.0e-8
        and lev.p_value == inference_f_sf(3.0, 1.0, 6.0)
        # p = 0.134 > 0.05, so the check does not find heterogeneity at this alpha — which on
        # eight observations is a statement about power, not about the variances
        and lev.satisfied
        and lev.n_obs == 8
        and lev.n_groups == 2
        # the first group's variance is exactly 0, so the ratio does not exist
        and not lev.variance_ratio_known
        and lev.variance_ratio == -1.0
    ):
        passed += 1
        print("  ✅ Levene is F = 3.0 exactly on 1 and 6 df, p = (2-sqrt3)/2")
    else:
        failed += 1
        print("  ❌ Levene:", lev.status, lev.statistic, lev.p_value, f_closed)

    # ── 2. Levene finds real heterogeneity, and reports the ratio ─────────────
    # Two groups with the same mean and wildly different spread: [4,5,6,5] (var 0.667) and
    # [-50,50,-50,50] (var 3333). The ratio is 5000 and the test rejects.
    var spread = _floats(4.0, 5.0, 6.0, 5.0, -50.0, 50.0, -50.0, 50.0)
    var het = variance_homogeneity_flat(spread, lengths, 0.05)
    if (
        het.status == INF_OK
        and not het.satisfied
        and het.p_value < 0.05
        and het.variance_ratio_known
        and het.variance_ratio > 1000.0
        and het.statistic > 3.0
    ):
        passed += 1
        print("  ✅ a 5000x variance ratio is detected: satisfied is False and p < 0.05")
    else:
        failed += 1
        print("  ❌ heterogeneity:", het.status, het.p_value, het.variance_ratio)

    # ── 3. the degeneracy Levene must refuse ─────────────────────────────────
    # Two groups whose absolute deviations are IDENTICAL within each group: the within-group sum
    # of squares is exactly 0, F is 0/0, and there is no p-value. Returning F = 0 with p = 1
    # would report the least informative possible input as perfect homogeneity.
    var no_spread = _floats(1.0, 3.0, 11.0, 13.0)
    var deg = variance_homogeneity_flat(no_spread, _ints(2, 2), 0.05)
    if (
        _no_verdict(deg)
        and deg.status == INF_ERR_DEGENERATE
        and deg.statistic == 0.0
    ):
        passed += 1
        print("  ✅ zero within-group variation is INF_ERR_DEGENERATE, not F=0 with p=1")
    else:
        failed += 1
        print("  ❌ degeneracy:", deg.status, deg.statistic, deg.p_value)

    # ── 4. Levene's refusals ────────────────────────────────────────────────
    if (
        # one group is nothing to compare
        _no_verdict(variance_homogeneity_flat(groups, _ints(8), 0.05))
        and variance_homogeneity_flat(groups, _ints(8), 0.05).status == INF_ERR_GROUPS
        # a group of one has no within-group deviation to contribute
        and variance_homogeneity_flat(groups, _ints(1, 7), 0.05).status == INF_ERR_GROUPS
        # sum(group_lengths) must equal len(values) exactly — the relation the declared
        # counts grammar cannot express, checked in the kernel
        and variance_homogeneity_flat(groups, _ints(4, 3), 0.05).status == INF_ERR_SHAPE
        and variance_homogeneity_flat(groups, _ints(4, 5), 0.05).status == INF_ERR_SHAPE
        and variance_homogeneity_flat(groups, lengths, 0.0).status == INF_ERR_ALPHA_RANGE
        and variance_homogeneity_flat(groups, lengths, 1.0).status == INF_ERR_ALPHA_RANGE
        and variance_homogeneity_flat(
            _floats(1.0, 2.0, inference_absent(), 4.0), _ints(2, 2), 0.05
        ).status == INF_ERR_NON_FINITE
        and variance_homogeneity_flat(groups, _ints(MAX_ASSUME_OBS + 1, 4), 0.05).status
        == INF_ERR_DIMENSION_TOO_LARGE
    ):
        passed += 1
        print("  ✅ eight malformed group specifications are refused with distinct statuses")
    else:
        failed += 1
        print("  ❌ a Levene refusal leaked")

    # ── 5. the chi-squared cell condition ───────────────────────────────────
    var observed = _floats(10.0, 20.0, 30.0, 40.0)
    var expected = _floats(25.0, 25.0, 25.0, 25.0)
    var cells = expected_counts_flat(observed, expected, CHI2_MIN_EXPECTED_CONVENTION)
    if (
        cells.status == INF_OK
        and cells.method == METHOD_CHI2_CELLS
        # 500/25 = 20.0, exact integer arithmetic
        and cells.statistic == 20.0
        and cells.df == 3.0
        # the closed form for 3 df in double precision is 1.6974243555282643e-4; the frozen
        # tail is accurate to 4e-9 absolute here, which is why it is reused rather than replaced
        and fabs(cells.p_value - 1.6974243555282643e-4) <= 1.0e-8
        and cells.p_value == 1.697428291143055e-4
        and cells.n_cells == 4
        and cells.n_below_min == 0
        and cells.min_expected_cell == 25.0
        and cells.min_expected_required == 5.0
        and cells.total_observed == 100.0
        and cells.total_expected == 100.0
        and cells.totals_match
        and cells.satisfied
    ):
        passed += 1
        print("  ✅ chi2 is 20.0 exactly on 3 df, p 1.6974e-4, and every cell clears 5")
    else:
        failed += 1
        print("  ❌ chi2 cells:", cells.status, cells.statistic, cells.p_value)

    # ── 6. the cell condition FAILING, which is the informative case ────────
    # Four cells with expected counts of 0.5: the statistic is computable, the reference
    # distribution does not apply, and `satisfied` says so while the number is still returned.
    var small_e = _floats(0.5, 0.5, 0.5, 0.5)
    var small_o = _floats(2.0, 0.0, 0.0, 0.0)
    var thin = expected_counts_flat(small_o, small_e, CHI2_MIN_EXPECTED_CONVENTION)
    if (
        thin.status == INF_OK
        and thin.statistic > 0.0
        and thin.n_below_min == 4
        and thin.min_expected_cell == 0.5
        and not thin.satisfied
        # the totals disagree (2 against 2), so this half is fine and the failure is the cells
        and thin.totals_match
    ):
        passed += 1
        print("  ✅ four cells at 0.5 return the statistic AND satisfied = False")
    else:
        failed += 1
        print("  ❌ thin cells:", thin.status, thin.n_below_min, thin.satisfied)

    # ── 7. mismatched totals are flagged, not refused ───────────────────────
    var wrong_total = expected_counts_flat(observed, _floats(20.0, 20.0, 20.0, 20.0), 5.0)
    if (
        wrong_total.status == INF_OK
        and wrong_total.total_observed == 100.0
        and wrong_total.total_expected == 80.0
        and not wrong_total.totals_match
        and not wrong_total.satisfied
        and wrong_total.n_below_min == 0
        # the statistic is still reported: it exists, it is just not a goodness-of-fit test
        and wrong_total.statistic > 0.0
    ):
        passed += 1
        print("  ✅ totals of 100 against 80 are flagged, with the statistic still reported")
    else:
        failed += 1
        print("  ❌ totals:", wrong_total.totals_match, wrong_total.satisfied)

    # ── 8. the chi-squared refusals ─────────────────────────────────────────
    if (
        # the frozen kernel would silently truncate to the shorter table
        expected_counts_flat(observed, _floats(25.0, 25.0), 5.0).status == INF_ERR_SHAPE
        # the frozen kernel SKIPS a non-positive expected cell while keeping k-1 df, so the
        # statistic and the reference distribution stop describing the same table
        and expected_counts_flat(observed, _floats(25.0, 25.0, 0.0, 25.0), 5.0).status
        == INF_ERR_DEGENERATE
        and expected_counts_flat(observed, _floats(25.0, 25.0, -1.0, 25.0), 5.0).status
        == INF_ERR_RESPONSE_RANGE
        and expected_counts_flat(_floats(-1.0, 20.0, 30.0, 40.0), expected, 5.0).status
        == INF_ERR_RESPONSE_RANGE
        and expected_counts_flat(List[Float64](), List[Float64](), 5.0).status
        == INF_ERR_EMPTY
        and expected_counts_flat(observed, expected, -1.0).status == INF_ERR_ALPHA_RANGE
        and expected_counts_flat(
            _floats(inference_absent(), 20.0, 30.0, 40.0), expected, 5.0
        ).status == INF_ERR_NON_FINITE
    ):
        passed += 1
        print("  ✅ a short table, a zero expected cell and a negative count are all refused")
    else:
        failed += 1
        print("  ❌ a chi2 refusal leaked")

    # ── 9. residual normality, both frozen tests reported ───────────────────
    var res = _floats(1.0, 2.0, 3.0, 4.0, 5.0)
    var norm = residual_normality_flat(res, 5, 0.05)
    var sw = shapiro_wilk_approx(res)
    var ad = anderson_darling_normal(res)
    if (
        norm.status == INF_OK
        and norm.method == METHOD_NORMALITY_PAIR
        # the statistics ARE the frozen kernels' own, bitwise
        and norm.shapiro_statistic == sw.statistic
        and norm.shapiro_p == sw.p_value
        and norm.anderson_statistic == ad.statistic
        and norm.anderson_p == ad.p_value
        and norm.shapiro_normal
        and norm.anderson_normal
        and norm.tests_agree
        and norm.satisfied
        and norm.n_obs == 5
    ):
        passed += 1
        print("  ✅ both normality statistics are the frozen kernels' own values, bitwise")
    else:
        failed += 1
        print("  ❌ normality:", norm.status, norm.shapiro_statistic, sw.statistic)

    # ── 10. the normality refusal that matters ─────────────────────────────
    # Both frozen tests return TestResult(0.0, 1.0, False) for a sample too small to test, and
    # `p = 1.0, reject_h0 = False` reads exactly like "this sample is normal".
    var two_points = _floats(1.0, 2.0)
    var frozen_two = anderson_darling_normal(two_points)
    if (
        # the frozen kernel says "normal" for two observations
        frozen_two.p_value == 1.0
        and not frozen_two.reject_h0
        # and this driver refuses
        and residual_normality_flat(two_points, 2, 0.05).status == INF_ERR_TOO_FEW
        and not residual_normality_flat(two_points, 2, 0.05).satisfied
        and residual_normality_flat(two_points, 2, 0.05).shapiro_p == ASSUME_P_ABSENT
        and residual_normality_flat(two_points, 2, 0.05).anderson_p == ASSUME_P_ABSENT
        and residual_normality_flat(res, 25, 0.05).status == INF_ERR_SHAPE
        and residual_normality_flat(res, 0, 0.05).status == INF_ERR_EMPTY
        and residual_normality_flat(res, 5, 0.0).status == INF_ERR_ALPHA_RANGE
        and residual_normality_flat(
            _floats(1.0, 2.0, inference_absent()), 3, 0.05
        ).status == INF_ERR_NON_FINITE
    ):
        passed += 1
        print("  ✅ the frozen tests call two points normal; this driver refuses instead")
    else:
        failed += 1
        print("  ❌ normality refusal:", residual_normality_flat(two_points, 2, 0.05).status)

    # ── 11. the checked t-test, and the frozen defect it used to expose ─────
    var pair = _floats(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    var checked = t_test_checked_flat(pair, 3, 3, 0.05)
    var frozen_t = t_test_2sample(_floats(1.0, 2.0, 3.0), _floats(4.0, 5.0, 6.0))
    if (
        checked.status == INF_OK
        and checked.method == METHOD_WELCH
        # the statistic is the frozen kernel's, bitwise, and this module reproduces it
        and checked.statistic == frozen_t.statistic
        and checked.statistic == -3.6742346141747673
        and checked.statistic_reproduced
        # equal variances and equal group sizes give Welch df = 2(n-1) = 4 exactly
        and checked.df == 4.0
        and checked.variance1 == 1.0
        and checked.variance2 == 1.0
        and checked.mean1 == 2.0
        and checked.mean2 == 5.0
        # the corrected two-sided p, which is also inference_t_sf_two_sided of the same inputs
        and fabs(checked.p_value - 0.021311641133773648) <= 1.0e-15
        and checked.p_value == inference_t_sf_two_sided(frozen_t.statistic, 4.0)
        and checked.reject
    ):
        passed += 1
        print("  ✅ Welch t = -3.67423 on exactly 4 df, corrected p = 0.02131164")
    else:
        failed += 1
        print("  ❌ checked t-test:", checked.status, checked.statistic, checked.df)

    if (
        # the frozen kernel is fixed: it now agrees with the corrected p-value to within the
        # two implementations' own continued-fraction truncation, not the old defect's
        # `p = 0.0, reject_h0 = True` regardless of the true tail
        fabs(frozen_t.p_value - 0.021311641136474657) <= 1.0e-9
        and frozen_t.reject_h0
        and fabs(checked.frozen_p_value - 0.021311641136474657) <= 1.0e-9
        and checked.frozen_p_value_usable
        # both tests reject, and now for the same reason
        and checked.reject
        and checked.p_value > 0.02
    ):
        passed += 1
        print("  ✅ the frozen and corrected p-values now agree, both correctly reject")
    else:
        failed += 1
        print("  ❌ frozen/corrected agreement wrong:", frozen_t.p_value, checked.frozen_p_value_usable)

    # ── 12. A THIRD frozen defect, and why normality_checked exists ─────────
    # `shapiro_wilk_approx` computes `p = 1 - Phi((log(1 - w) - mu)/sigma)`. On three EQUALLY
    # SPACED points the correlation is perfect, `w` comes out as 1.0000000000000002, so
    # `1 - w` is -2.2e-16 and `log` of it is NaN. The kernel's own clamps cannot catch that
    # (`nan < 0.0` and `nan > 1.0` are both False), so it returns `p_value = nan` with
    # `reject_h0 = False` — "do not reject normality", decided by a NaN. That is rule 4d's nan
    # trap, live in a frozen kernel.
    #
    # So `t_test_checked_flat` on two three-point groups reports `normality_checked = False`
    # rather than inheriting the NaN, and `residual_normality_flat` refuses those groups with
    # `INF_ERR_PVALUE_RANGE`. Both are asserted, because "the check could not run" and "the
    # check passed" must not be the same answer.
    var three_linear = _floats(1.0, 2.0, 3.0)
    var sw3 = shapiro_wilk_approx(three_linear)
    if (
        # the frozen statistic is fractionally ABOVE 1, which is what makes the log NaN
        sw3.statistic > 1.0
        and not (sw3.p_value == sw3.p_value)
        and not sw3.reject_h0
        and residual_normality_flat(three_linear, 3, 0.05).status == INF_ERR_PVALUE_RANGE
        # and the checked t-test says the normality check did not run, rather than passing
        and not checked.normality_checked
        and not checked.normality_satisfied_1
        and not checked.assumptions_satisfied
        # while the homogeneity check DID run: both variances are 1.0, so Levene's F is 0
        and checked.equal_variance_p == 1.0
        and checked.equal_variance_satisfied
        and checked.n1 == 3
        and checked.n2 == 3
        and checked.alpha == 0.05
    ):
        passed += 1
        print("  ✅ frozen Shapiro-Wilk returns p=NaN on 3 linear points; that is not 'passed'")
    else:
        failed += 1
        print("  ❌ nan trap:", sw3.statistic, sw3.p_value, checked.normality_checked)

    # ── 12b. and on groups large enough, every verdict DOES travel ──────────
    var wider = _floats(2.1, 3.4, 1.9, 4.2, 2.8, 5.1, 6.4, 4.9, 7.2, 5.8)
    var full = t_test_checked_flat(wider, 5, 5, 0.05)
    if (
        full.status == INF_OK
        and full.statistic_reproduced
        and fabs(full.statistic - (-5.0083542247063315)) <= 1.0e-12
        # the two groups are the same five values shifted by exactly 3, so the variances agree
        # to rounding and the Welch df is 8 to rounding
        and fabs(full.df - 8.0) <= 1.0e-12
        and fabs(full.mean2 - full.mean1 - 3.0) <= 1.0e-12
        and fabs(full.p_value - 0.001041900557283009) <= 1.0e-15
        and full.reject
        # the frozen kernel is fixed: it agrees with the corrected p-value here too
        and fabs(full.frozen_p_value - 0.001041900557415154) <= 1.0e-9
        and full.frozen_p_value_usable
        # every checkable assumption ran and was satisfied
        and full.equal_variance_satisfied
        and full.normality_checked
        and full.normality_satisfied_1
        and full.normality_satisfied_2
        and full.assumptions_satisfied
    ):
        passed += 1
        print("  ✅ on 5+5 groups the number arrives with all three verdicts attached")
    else:
        failed += 1
        print("  ❌ full verdicts:", full.status, full.normality_checked, full.p_value)

    # ── 13. the t-test's refusals ─────────────────────────────────────────
    if (
        t_test_checked_flat(pair, 1, 5, 0.05).status == INF_ERR_TOO_FEW
        and t_test_checked_flat(pair, 3, 4, 0.05).status == INF_ERR_SHAPE
        and t_test_checked_flat(pair, 3, 3, 0.0).status == INF_ERR_ALPHA_RANGE
        and t_test_checked_flat(
            _floats(1.0, 2.0, inference_absent(), 4.0), 2, 2, 0.05
        ).status == INF_ERR_NON_FINITE
        # both variances zero: no standard error, so no t statistic. The frozen kernel returns
        # 1e10 with p = 0.0 for exactly this input.
        and t_test_checked_flat(_floats(1.0, 1.0, 5.0, 5.0), 2, 2, 0.05).status
        == INF_ERR_DEGENERATE
        and t_test_2sample(_floats(1.0, 1.0), _floats(5.0, 5.0)).statistic == 1.0e10
        and t_test_checked_flat(pair, 3, 3, 0.05).p_value > 0.0
    ):
        passed += 1
        print("  ✅ a zero standard error is refused where the frozen kernel returns 1e10")
    else:
        failed += 1
        print("  ❌ a t-test refusal leaked")

    # ── 14. the proportion test ──────────────────────────────────────────
    var prop = proportion_test_checked_flat(30, 100, 45, 100, 0.05)
    var se_closed = sqrt(0.375 * 0.625 * 0.02)
    if (
        prop.status == INF_OK
        and prop.method == METHOD_TWO_PROPORTION_Z
        and prop.p_hat_a == 0.30
        and prop.p_hat_b == 0.45
        # z = -0.15 / sqrt(0.375 * 0.625 * (1/100 + 1/100))
        and fabs(prop.z - (-0.15 / se_closed)) <= 1.0e-12
        and fabs(prop.z - (-2.1908902300206647)) <= 1.0e-12
        and fabs(prop.p_value - 0.028459637652763714) <= 1.0e-15
        # unlike the t-test, the frozen proportion tail is sound, so the two DO agree — that
        # contrast is what makes the t-test's False informative rather than generic distrust
        and prop.frozen_p_value_usable
        and fabs(prop.frozen_p_value - prop.p_value) <= 1.0e-8
        and prop.reject
        # every cell of the 2x2 clears 5, so the normal approximation applies
        and prop.min_expected_cell == 30.0
        and prop.normal_approximation_ok
        # the Wilson intervals come from the frozen kernel and bracket the estimates
        and prop.ci_a_lo < 0.30
        and 0.30 < prop.ci_a_hi
        and prop.ci_b_lo < 0.45
        and 0.45 < prop.ci_b_hi
    ):
        passed += 1
        print("  ✅ z = -2.19089 with p 0.0284596, and the frozen tail AGREES here")
    else:
        failed += 1
        print("  ❌ proportion test:", prop.status, prop.z, prop.p_value)

    # ── 15. the normal-approximation verdict, and the NaN the frozen kernel gives ─
    var thin_prop = proportion_test_checked_flat(1, 10, 2, 10, 0.05)
    var frozen_empty = z_test_proportions(0, 0, 0, 0)
    var frozen_ci = confidence_interval_proportion(0, 0, 0.95)
    if (
        thin_prop.status == INF_OK
        and thin_prop.min_expected_cell == 1.0
        and not thin_prop.normal_approximation_ok
        # the number is still returned; only the verdict says not to trust it
        and thin_prop.p_value >= 0.0
        # On an EMPTY request the frozen z-test divides 0 by 0 three times, its
        # `if se > 1e-15` guard sees a NaN and takes the else branch, and it returns
        # z = 0.0 with p = 0.9999999989503827 — a confident "not significant" from no data.
        and frozen_empty[0] == 0.0
        and frozen_empty[1] > 0.99
        # the frozen Wilson interval on the same request returns NaN for both endpoints
        and not (frozen_ci[0] == frozen_ci[0])
        and not (frozen_ci[1] == frozen_ci[1])
        # and this driver refuses that request outright rather than reporting either
        and proportion_test_checked_flat(0, 0, 0, 0, 0.05).status == INF_ERR_EMPTY
        and proportion_test_checked_flat(11, 10, 2, 10, 0.05).status
        == INF_ERR_RESPONSE_RANGE
        and proportion_test_checked_flat(-1, 10, 2, 10, 0.05).status
        == INF_ERR_RESPONSE_RANGE
        and proportion_test_checked_flat(1, 10, 2, 10, 0.0).status == INF_ERR_ALPHA_RANGE
        and proportion_test_checked_flat(1, MAX_ASSUME_OBS + 1, 2, 10, 0.05).status
        == INF_ERR_DIMENSION_TOO_LARGE
    ):
        passed += 1
        print("  ✅ a 1-in-10 cell is flagged, and the frozen kernel's NaN request is refused")
    else:
        failed += 1
        print("  ❌ proportion refusals:", thin_prop.normal_approximation_ok)

    # ── 16. the A-Z harness shapes, which must not abort ──────────────────
    # _lf5 = [0.5, 0.6, 0.7, 0.4, 0.3] and _li5 = [1, 2, 3, 4, 5], with 5 for every Int.
    var lf5 = _floats(0.5, 0.6, 0.7, 0.4, 0.3)
    var li5 = _ints(1, 2, 3, 4, 5)
    if (
        # group_lengths = [1,2,3,4,5]: the first group has one observation
        variance_homogeneity_flat(lf5, li5, 0.5).status == INF_ERR_GROUPS
        # equal-length tables of positive expected counts: this one runs
        and expected_counts_flat(lf5, lf5, 0.5).status == INF_OK
        and expected_counts_flat(lf5, lf5, 0.5).statistic == 0.0
        and residual_normality_flat(lf5, 5, 0.5).status == INF_OK
        # n1 + n2 = 10 against a five-element payload
        and t_test_checked_flat(lf5, 5, 5, 0.5).status == INF_ERR_SHAPE
        # successes = n = 5 for both groups, so the pooled proportion is 1 and the standard
        # error is 0; the frozen kernel returns z = 0 there, which is finite and admitted
        and proportion_test_checked_flat(5, 5, 5, 5, 0.5).status == INF_OK
    ):
        passed += 1
        print("  ✅ all five harness calls either answer or refuse, none indexes past the end")
    else:
        failed += 1
        print("  ❌ a harness call misbehaved:", variance_homogeneity_flat(lf5, li5, 0.5).status)

    print("  [inference.assume] Passed:", passed, "Failed:", failed)
