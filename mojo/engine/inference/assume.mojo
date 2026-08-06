"""
inference.assume — a p-value with the verdict on its assumptions. Zero Python imports.

Why this module exists
----------------------
A p-value from a test whose assumptions were not met is not a p-value. Every frozen test in
the tree returns the number and nothing else: `stat_tests.TestResult` is
`(statistic, p_value, reject_h0)` and `hypothesis`'s tests return a bare `List[Float64]`. So a
caller cannot tell a chi-squared statistic computed on cells with expected count 0.4 from one
computed on cells with expected count 400, and nothing anywhere reports the difference.

Where the assumption is CHECKABLE, this module checks it and returns the verdict beside the
number. Three are checkable and all three are checked here:

* **variance homogeneity** — Levene's test on absolute deviations from group MEDIANS (the
  Brown-Forsythe variant, which is the one that stays valid on skewed data). Nothing in the
  tree tests it; there is no Levene, no Bartlett and no one-way ANOVA F.
* **minimum expected cell counts** — the condition under which a chi-squared statistic is
  chi-squared distributed at all. `stat_tests.chi_squared_test` never looks, and it silently
  SKIPS any cell with a non-positive expected count (`if expected[i] > 0.0:`) while still
  using `k - 1` degrees of freedom, so the statistic and the reference distribution disagree
  without anything saying so.
* **normality of residuals** — from the two frozen tests that measure it, with their verdicts
  reported separately AND their agreement stated, because two normality tests that disagree is
  information a single `reject_h0` cannot carry.

Three frozen kernels this module wraps report a non-answer as a verdict. All three are
reproduced in the suite:

    shapiro_wilk_approx([1.0, 2.0, 3.0])
        -> statistic 1.0000000000000002, p_value nan, reject_h0 False

  Its p-value is `1 - Phi((log(1 - w) - mu) / sigma)`. On perfectly collinear order statistics
  `w` comes out fractionally ABOVE 1, so `1 - w` is -2.2e-16 and `log` of it is NaN. The
  kernel's own clamps cannot catch that — `nan < 0.0` and `nan > 1.0` are both False — and
  `reject_h0` is `nan < 0.05`, i.e. False. So it reports "do not reject normality", decided by
  a NaN. That is rule 4d's nan trap, live in a frozen kernel, and it is why
  `NormalityVerdict` has no path from a non-probability to a verdict:
  `INF_ERR_PVALUE_RANGE`, and `CheckedTest.normality_checked` is False rather than True.

    z_test_proportions(0, 0, 0, 0)
        -> [0.0, 0.9999999989503827]

  Three divisions of 0 by 0 produce NaN, the `if se > 1e-15` guard sees the NaN and takes the
  else branch leaving `z = 0.0`, and the result is a confident "not significant" from a request
  containing no data at all.

    confidence_interval_proportion(0, 0, 0.95)
        -> [nan, nan]

  The same empty request through the Wilson interval, where `is_significant(nan)` is False and
  a plotted interval would simply not appear.

Rule 4, in the form it takes here
---------------------------------
* **Failing to reject is not proof.** `satisfied` in every verdict below means "the check did
  not find a violation at this alpha", never "the assumption holds". A small sample fails to
  reject almost everything. Every struct's docstring says which way its flag points, and
  `alpha` and the sample size travel with it so a caller can see how much power the check had.
* **A verdict that does not exist is absent.** When Levene's within-group sum of squares is
  exactly zero the F statistic is `0/0` and there is no p-value: `INF_ERR_DEGENERATE`, not
  `F = 0` and `p = 1` (which reads as "perfectly homogeneous" and is the answer a naive
  implementation gives to the least informative possible input).
* **The frozen p-value is reported beside the corrected one.** `t_test_checked_flat` returns
  both, plus `frozen_p_value_usable`. The frozen t-test p-value is derived from
  `stat_tests._regularized_incomplete_beta`, which omits a continued-fraction level (see
  `inference.core` for the reproduction), so it can be a clamped `0.0` under
  `reject_h0 = True` where the true p is `0.0213`. Reporting only the corrected number would
  fix the arithmetic and hide the disagreement; reporting both makes it auditable.
* **The two-sample t-test's assumption is stated precisely.** `t_test_2sample` is WELCH's
  test, which does NOT assume equal variances. The homogeneity verdict is therefore reported
  as information — it says whether the pooled Student test would also have been valid — and
  not as a precondition of the number returned. Saying otherwise would be a caveat that is
  itself wrong.

What is reused rather than rebuilt
----------------------------------
* `stat_tests.t_test_2sample` — the Welch statistic, taken from the frozen kernel and never
  recomputed. This module computes the Welch-Satterthwaite degrees of freedom, which the
  frozen `TestResult` does not carry and which the corrected tail needs, and then CROSS-CHECKS
  its own `(m1 - m2) / se` against the frozen statistic and reports the agreement.
* `stat_tests.chi_squared_test` — the chi-squared statistic and its tail. `_chi2_cdf` was
  verified accurate against closed forms (see `inference.core`), so it is used as-is.
* `stat_tests.shapiro_wilk_approx`, `anderson_darling_normal` — both normality tests.
* `stat_tests._variance` — the sample variance behind the Welch df and the variance ratio.
* `stats_bootstrap._median` — the per-group centre Levene needs.
* `ab_testing.z_test_proportions`, `confidence_interval_proportion` — the two-proportion test
  and the Wilson interval, both of which divide by a count without checking it.
* `inference.core.inference_f_sf` / `inference_t_sf_two_sided` / `inference_norm_sf_two_sided` —
  the tails.

Bounds, per rule 1c and "bounding memory is not bounding work"
-------------------------------------------------------------
`MAX_ASSUME_OBS` is 2^12 and is SMALL on purpose, and the reason is work rather than memory:
the frozen `stats_bootstrap._median` and the frozen normality tests all insertion-sort, so
every one of them is O(m^2) in the length handed to it. One group of 2^12 is 1.7e7
comparisons; 2^20 would be 1.1e12, which is a hang — and from the caller's side a hang is the
same outcome as rule 1's uncatchable abort. Every group length is bounded individually AND
their sum is required to equal `len(values)` exactly, so a declared length the payload does
not back is a rejection rather than a smaller loop.

Status codes 320-339 belong to the `inference` package; this module allocates none of its own
(rule 4e).

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_inference_assume.mojo
benchmark: benchmarks/mojo_benchmarks/bench_inference.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, sqrt

from ab_testing import confidence_interval_proportion, z_test_proportions
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
    inference_f_sf,
    inference_finite,
    inference_norm_sf_two_sided,
    inference_scaled_tol,
    inference_t_sf_two_sided,
)
from stat_tests import (
    _variance,
    anderson_darling_normal,
    chi_squared_test,
    shapiro_wilk_approx,
    t_test_2sample,
)
from stats_bootstrap import _median

# The conventional minimum expected cell count for a chi-squared test. Exposed as the value a
# caller should PASS rather than defaulted into a signature: the arity of a public function is
# load-bearing here (the dispatch generator emits an exact-count check), and an unstated
# convention is exactly what this module exists to stop.
comptime CHI2_MIN_EXPECTED_CONVENTION: Float64 = 5.0

# A probability is non-negative, so -1.0 is outside the range and says "never computed".
comptime ASSUME_P_ABSENT: Float64 = -1.0

comptime METHOD_LEVENE_MEDIAN: String = "levene_brown_forsythe_median_centred"
comptime METHOD_CHI2_CELLS: String = "chi_squared_minimum_expected_cell"
comptime METHOD_NORMALITY_PAIR: String = "shapiro_wilk_and_anderson_darling"
comptime METHOD_WELCH: String = "welch_two_sample_t"
comptime METHOD_TWO_PROPORTION_Z: String = "two_proportion_pooled_z"


@fieldwise_init
struct AssumptionVerdict(Copyable, Movable):
    """Levene's verdict on whether several groups share a variance.

    `satisfied` is True when the test did NOT find heterogeneity at `alpha`. It is not a claim
    that the variances are equal — failing to reject is not proof, and `n_obs` and `n_groups`
    are carried so a caller can see how much power the check had.

    `statistic`, `p_value`, `df1` and `df2` are meaningful only when `status == INF_OK`.

    `variance_ratio` is `max(s_j^2) / min(s_j^2)`, a descriptive companion to the test, and
    `variance_ratio_known` is False when the smallest group variance is exactly zero — a ratio
    with a zero denominator does not exist and is not "infinitely heterogeneous".
    """

    var status: Int
    var method: String
    var n_obs: Int
    var n_groups: Int
    var alpha: Float64
    var statistic: Float64
    var p_value: Float64
    var df1: Float64
    var df2: Float64
    var satisfied: Bool
    var variance_ratio: Float64
    var variance_ratio_known: Bool


def _verdict_failure(code: Int, n: Int, k: Int, alpha: Float64) -> AssumptionVerdict:
    return AssumptionVerdict(
        code, METHOD_LEVENE_MEDIAN, n, k, alpha, 0.0, ASSUME_P_ABSENT,
        -1.0, -1.0, False, -1.0, False,
    )


def variance_homogeneity_flat(
    values: List[Float64], group_lengths: List[Int], alpha: Float64
) -> AssumptionVerdict:
    """Levene's test with median centring (Brown-Forsythe), over concatenated groups.

    `values` is every group's observations end to end and `group_lengths[j]` is how many belong
    to group `j`; the lengths must sum to EXACTLY `len(values)`. The statistic is the one-way F
    on `z_ij = |x_ij - median_j|`:

        F = ((N - k) / (k - 1)) * sum_j n_j (zbar_j - zbar)^2 / sum_j sum_i (z_ij - zbar_j)^2

    with the tail from `inference.core.inference_f_sf`. Median centring rather than mean
    centring is deliberate: it is what makes the test robust to non-normal, skewed groups,
    which is the situation a homogeneity check is usually run in.

    The relation `sum(group_lengths) == len(values)` cannot be written in the declared
    `counts:` grammar — the left side must be a product of parameter NAMES and there is no
    form for a sum over a list's contents — so it is checked in the kernel and written here in
    the grammar's style so it is greppable when the grammar grows (rule 1d). No `counts:`
    entry claims it, because an incomplete `[enforced]` is worse than no declaration.

    Refuses: fewer than two groups (`INF_ERR_GROUPS` — there is nothing to compare), any group
    with fewer than two observations (a group of one has no within-group deviation to
    contribute), a length sum that does not match the payload, a length above `MAX_ASSUME_OBS`,
    a non-finite value, an `alpha` outside `(0, 1)`, and a within-group sum of squares of
    exactly zero (`INF_ERR_DEGENERATE`: `F` is `0/0` and there is no p-value).

    @capability variance_homogeneity_flat
    complexity: O(sum_j n_j^2) — the frozen per-group median insertion-sorts
    counts: none
    @endcapability
    """
    var k = len(group_lengths)
    if k < 2:
        return _verdict_failure(INF_ERR_GROUPS, len(values), k, alpha)
    if not inference_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return _verdict_failure(INF_ERR_ALPHA_RANGE, len(values), k, alpha)
    var total = 0
    for j in range(k):
        var m = group_lengths[j]
        if m < 2:
            return _verdict_failure(INF_ERR_GROUPS, len(values), k, alpha)
        if m > MAX_ASSUME_OBS:
            return _verdict_failure(INF_ERR_DIMENSION_TOO_LARGE, len(values), k, alpha)
        total += m
        if total > MAX_ASSUME_OBS:
            return _verdict_failure(INF_ERR_DIMENSION_TOO_LARGE, len(values), k, alpha)
    # sum(group_lengths) == len(values) — the relation the grammar cannot say.
    if total != len(values):
        return _verdict_failure(INF_ERR_SHAPE, len(values), k, alpha)
    for i in range(total):
        if not inference_finite(values[i]):
            return _verdict_failure(INF_ERR_NON_FINITE, total, k, alpha)

    var deviations = List[Float64](capacity=total)
    var group_mean_dev = List[Float64](capacity=k)
    var variances = List[Float64](capacity=k)
    var offset = 0
    var grand_sum: Float64 = 0.0
    for j in range(k):
        var m = group_lengths[j]
        var group = List[Float64](capacity=m)
        for i in range(m):
            group.append(values[offset + i])
        var centre = _median(group)
        variances.append(_variance(group))
        var dev_sum: Float64 = 0.0
        for i in range(m):
            var d = fabs(group[i] - centre)
            deviations.append(d)
            dev_sum += d
        group_mean_dev.append(dev_sum / Float64(m))
        grand_sum += dev_sum
        offset += m
    var grand_mean = grand_sum / Float64(total)

    var between: Float64 = 0.0
    var within: Float64 = 0.0
    offset = 0
    for j in range(k):
        var m = group_lengths[j]
        var gap = group_mean_dev[j] - grand_mean
        between += Float64(m) * gap * gap
        for i in range(m):
            var d = deviations[offset + i] - group_mean_dev[j]
            within += d * d
        offset += m

    if within <= 0.0:
        # Every observation in every group is exactly its group's median distance away, so
        # F is 0/0. There is no statistic, and reporting F = 0 with p = 1 would present the
        # least informative possible input as perfect homogeneity.
        return _verdict_failure(INF_ERR_DEGENERATE, total, k, alpha)

    var df1 = Float64(k - 1)
    var df2 = Float64(total - k)
    var f = (df2 / df1) * (between / within)
    if not inference_finite(f) or f < 0.0:
        return _verdict_failure(INF_ERR_DEGENERATE, total, k, alpha)
    var p = inference_f_sf(f, df1, df2)
    if not inference_finite(p):
        return _verdict_failure(INF_ERR_DEGENERATE, total, k, alpha)

    var min_v = variances[0]
    var max_v = variances[0]
    for j in range(1, k):
        if variances[j] < min_v:
            min_v = variances[j]
        if variances[j] > max_v:
            max_v = variances[j]
    var ratio_known = min_v > 0.0
    var ratio = (max_v / min_v) if ratio_known else -1.0
    return AssumptionVerdict(
        INF_OK, METHOD_LEVENE_MEDIAN, total, k, alpha, f, p, df1, df2,
        p >= alpha, ratio, ratio_known,
    )


@fieldwise_init
struct CellCountVerdict(Copyable, Movable):
    """The chi-squared statistic together with the condition that makes it chi-squared.

    `satisfied` is True only when every expected cell reaches `min_expected_required` AND the
    two totals agree. Both are necessary: the reference distribution is asymptotic in the
    expected counts, and a goodness-of-fit statistic compares two distributions of the SAME
    total, so mismatched totals make the statistic measure the totals rather than the shape.

    `n_below_min` and `min_expected_cell` say how badly the count condition is missed, so a
    caller can distinguish "one cell at 4.8" from "half the cells at 0.3".

    `totals_match` is decided with a tolerance built from the totals' own magnitude (rule 4b),
    not from an absolute epsilon that a large table would fail on regardless.
    """

    var status: Int
    var method: String
    var n_cells: Int
    var statistic: Float64
    var p_value: Float64
    var df: Float64
    var n_below_min: Int
    var min_expected_cell: Float64
    var min_expected_required: Float64
    var total_observed: Float64
    var total_expected: Float64
    var totals_match: Bool
    var satisfied: Bool


def _cells_failure(code: Int, n: Int, required: Float64) -> CellCountVerdict:
    return CellCountVerdict(
        code, METHOD_CHI2_CELLS, n, 0.0, ASSUME_P_ABSENT, -1.0, -1,
        -1.0, required, 0.0, 0.0, False, False,
    )


def expected_counts_flat(
    observed: List[Float64], expected: List[Float64], min_expected: Float64
) -> CellCountVerdict:
    """The frozen chi-squared test plus the verdict on its minimum-expected-cell assumption.

    The statistic and tail come from `stat_tests.chi_squared_test` unchanged. What is added is
    everything a caller needs to know whether that number is a chi-squared value at all:

    * `stat_tests.chi_squared_test` truncates to `min(len(observed), len(expected))`. A length
      mismatch is `INF_ERR_SHAPE` here rather than a silently shorter table.
    * It skips any cell whose expected count is not strictly positive while still using
      `k - 1` degrees of freedom, so the statistic and the reference distribution stop
      describing the same table. A non-positive expected count is `INF_ERR_DEGENERATE` here:
      the term `(O - E)^2 / E` does not exist and neither does the test.
    * A negative observed or expected count is not a count: `INF_ERR_RESPONSE_RANGE`.

    Pass `CHI2_MIN_EXPECTED_CONVENTION` (5.0) for `min_expected` unless you have a reason not
    to; it is a convention, which is why it is a parameter and not a hidden constant.

    @capability expected_counts_flat
    complexity: O(n)
    counts: none
    @endcapability
    """
    var n = len(observed)
    if n == 0:
        return _cells_failure(INF_ERR_EMPTY, 0, min_expected)
    if len(expected) != n:
        return _cells_failure(INF_ERR_SHAPE, n, min_expected)
    if n > MAX_ASSUME_OBS:
        return _cells_failure(INF_ERR_DIMENSION_TOO_LARGE, n, min_expected)
    if not inference_finite(min_expected) or min_expected < 0.0:
        return _cells_failure(INF_ERR_ALPHA_RANGE, n, min_expected)
    var total_o: Float64 = 0.0
    var total_e: Float64 = 0.0
    var min_cell = expected[0]
    var below = 0
    for i in range(n):
        if not inference_finite(observed[i]) or not inference_finite(expected[i]):
            return _cells_failure(INF_ERR_NON_FINITE, n, min_expected)
        if observed[i] < 0.0 or expected[i] < 0.0:
            return _cells_failure(INF_ERR_RESPONSE_RANGE, n, min_expected)
        if expected[i] <= 0.0:
            return _cells_failure(INF_ERR_DEGENERATE, n, min_expected)
        if expected[i] < min_cell:
            min_cell = expected[i]
        if expected[i] < min_expected:
            below += 1
        total_o += observed[i]
        total_e += expected[i]

    var result = chi_squared_test(observed, expected)
    if not inference_finite(result.statistic):
        return _cells_failure(INF_ERR_DEGENERATE, n, min_expected)
    if not inference_finite(result.p_value) or result.p_value < 0.0 or result.p_value > 1.0:
        return _cells_failure(INF_ERR_PVALUE_RANGE, n, min_expected)
    # Judged quantity: the difference of the two totals. Scale: the totals' own magnitude.
    var gap = fabs(total_o - total_e)
    var scale = total_o if total_o > total_e else total_e
    var totals_match = gap <= inference_scaled_tol(scale, 0.0)
    var df = Float64(n - 1)
    if df < 1.0:
        df = 1.0
    return CellCountVerdict(
        INF_OK, METHOD_CHI2_CELLS, n, result.statistic, result.p_value, df,
        below, min_cell, min_expected, total_o, total_e, totals_match,
        below == 0 and totals_match,
    )


@fieldwise_init
struct NormalityVerdict(Copyable, Movable):
    """Two frozen normality tests on the same sample, with their agreement stated.

    `satisfied` is True when NEITHER test rejects normality at `alpha`. As everywhere in this
    module that is "no violation found", not "the sample is normal": on 5 observations neither
    test rejects almost anything, which is why `n_obs` travels with the verdict.

    `tests_agree` is False when the two tests reach different conclusions. That is information
    a single flag cannot carry and it is the reason both are run: Shapiro-Wilk is sensitive to
    asymmetry and short tails, Anderson-Darling to the tails themselves, and a disagreement
    tells a caller which kind of departure they have.
    """

    var status: Int
    var method: String
    var n_obs: Int
    var alpha: Float64
    var shapiro_statistic: Float64
    var shapiro_p: Float64
    var shapiro_normal: Bool
    var anderson_statistic: Float64
    var anderson_p: Float64
    var anderson_normal: Bool
    var tests_agree: Bool
    var satisfied: Bool


def _normality_failure(code: Int, n: Int, alpha: Float64) -> NormalityVerdict:
    return NormalityVerdict(
        code, METHOD_NORMALITY_PAIR, n, alpha, 0.0, ASSUME_P_ABSENT, False,
        0.0, ASSUME_P_ABSENT, False, False, False,
    )


def residual_normality_flat(
    residuals: List[Float64], n: Int, alpha: Float64
) -> NormalityVerdict:
    """Shapiro-Wilk and Anderson-Darling on the first `n` residuals, both verdicts reported.

    Both statistics come from the frozen kernels (`stat_tests.shapiro_wilk_approx` and
    `anderson_darling_normal`) unchanged.

    The refusal that matters: both frozen tests return `TestResult(0.0, 1.0, False)` for a
    sample too small to test — `n < 3` for Anderson-Darling, `n < 3` for Shapiro-Wilk — and
    `p = 1.0, reject_h0 = False` reads exactly like "this sample is normal". `n < 3` is
    `INF_ERR_TOO_FEW` here, because a normality verdict on two points does not exist.

    @capability residual_normality_flat
    complexity: O(n^2) — both frozen tests sort with an insertion sort
    counts:
    - n <= len(residuals) [kernel_validated]
    @endcapability
    """
    if n <= 0:
        return _normality_failure(INF_ERR_EMPTY, n, alpha)
    if n > len(residuals):
        return _normality_failure(INF_ERR_SHAPE, n, alpha)
    if n > MAX_ASSUME_OBS:
        return _normality_failure(INF_ERR_DIMENSION_TOO_LARGE, n, alpha)
    if n < 3:
        return _normality_failure(INF_ERR_TOO_FEW, n, alpha)
    if not inference_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return _normality_failure(INF_ERR_ALPHA_RANGE, n, alpha)
    var sample = List[Float64](capacity=n)
    for i in range(n):
        if not inference_finite(residuals[i]):
            return _normality_failure(INF_ERR_NON_FINITE, n, alpha)
        sample.append(residuals[i])

    var sw = shapiro_wilk_approx(sample)
    var ad = anderson_darling_normal(sample)
    if not inference_finite(sw.p_value) or not inference_finite(ad.p_value):
        return _normality_failure(INF_ERR_PVALUE_RANGE, n, alpha)
    if sw.p_value < 0.0 or sw.p_value > 1.0 or ad.p_value < 0.0 or ad.p_value > 1.0:
        return _normality_failure(INF_ERR_PVALUE_RANGE, n, alpha)
    var sw_ok = sw.p_value >= alpha
    var ad_ok = ad.p_value >= alpha
    return NormalityVerdict(
        INF_OK, METHOD_NORMALITY_PAIR, n, alpha,
        sw.statistic, sw.p_value, sw_ok,
        ad.statistic, ad.p_value, ad_ok,
        sw_ok == ad_ok, sw_ok and ad_ok,
    )


@fieldwise_init
struct CheckedTest(Copyable, Movable):
    """A Welch two-sample t-test with a corrected p-value and every checkable assumption.

    `p_value` is the CORRECTED two-sided tail, from `inference.core.inference_t_sf_two_sided`.
    `frozen_p_value` is what `stat_tests.t_test_2sample` returned for the same data, and
    `frozen_p_value_usable` is False when the two disagree beyond rounding — which is the
    normal case, because the frozen tail is computed from a defective incomplete beta and is
    clamped into `[0, 1]` afterwards. Both are reported so the disagreement is auditable
    rather than quietly fixed.

    `statistic` is the frozen kernel's own Welch statistic, not recomputed.
    `statistic_reproduced` is True when this module's independent `(m1 - m2) / se` agrees with
    it — a differential check inside the driver, since the Welch degrees of freedom had to be
    derived here (the frozen `TestResult` does not carry them) and a df derived from the wrong
    variances would give a plausible p-value for the wrong test.

    `equal_variance_p` is INFORMATION, not a precondition: Welch's test does not assume equal
    variances. It says whether the pooled Student test would also have been valid.

    `assumptions_satisfied` is the conjunction of the two normality verdicts only, for exactly
    that reason, and `normality_checked` is False when a group was too small to test.
    """

    var status: Int
    var method: String
    var n1: Int
    var n2: Int
    var alpha: Float64
    var mean1: Float64
    var mean2: Float64
    var variance1: Float64
    var variance2: Float64
    var statistic: Float64
    var statistic_reproduced: Bool
    var df: Float64
    var p_value: Float64
    var frozen_p_value: Float64
    var frozen_p_value_usable: Bool
    var reject: Bool
    var equal_variance_p: Float64
    var equal_variance_satisfied: Bool
    var normality_checked: Bool
    var normality_satisfied_1: Bool
    var normality_satisfied_2: Bool
    var assumptions_satisfied: Bool


def _checked_failure(code: Int, n1: Int, n2: Int, alpha: Float64) -> CheckedTest:
    return CheckedTest(
        code, METHOD_WELCH, n1, n2, alpha, 0.0, 0.0, -1.0, -1.0, 0.0, False,
        -1.0, ASSUME_P_ABSENT, ASSUME_P_ABSENT, False, False,
        ASSUME_P_ABSENT, False, False, False, False, False,
    )


def t_test_checked_flat(
    values: List[Float64], n1: Int, n2: Int, alpha: Float64
) -> CheckedTest:
    """Welch's two-sample t-test with a corrected tail and every checkable assumption verdict.

    `values` is the two groups concatenated: the first `n1` entries then the next `n2`, with
    `len(values)` exactly `n1 + n2`. A longer payload is `INF_ERR_SHAPE`, not a silently
    ignored tail.

    The statistic is `stat_tests.t_test_2sample`'s. The degrees of freedom are the
    Welch-Satterthwaite value, derived here from the frozen `stat_tests._variance` because the
    frozen `TestResult` carries only three fields and the corrected tail needs the df. That
    derivation is then CHECKED against the frozen statistic (`statistic_reproduced`), which is
    what makes it safe to have derived: a df computed from variances that do not reproduce the
    frozen t would be a plausible p-value for a different test.

    The p-value is `inference_t_sf_two_sided`, which is the two-tail mass DIRECTLY rather than
    `2 * (1 - cdf)`; see `inference.core` for why that matters and for the reproduction of the
    frozen defect this replaces.

    Refuses a group smaller than 2 (`INF_ERR_TOO_FEW`: no variance), a zero standard error
    (`INF_ERR_DEGENERATE`: with both variances zero there is no t statistic, and the frozen
    kernel returns `1e10` with `p = 0.0` for that case), and a non-finite value.

    @capability t_test_checked_flat
    complexity: O((n1 + n2)^2) — the assumption checks sort
    counts:
    - n1 + n2 == len(values) [kernel_validated]
    @endcapability
    """
    if n1 < 2 or n2 < 2:
        return _checked_failure(INF_ERR_TOO_FEW, n1, n2, alpha)
    if n1 > MAX_ASSUME_OBS or n2 > MAX_ASSUME_OBS:
        return _checked_failure(INF_ERR_DIMENSION_TOO_LARGE, n1, n2, alpha)
    var total = n1 + n2
    if len(values) != total:
        return _checked_failure(INF_ERR_SHAPE, n1, n2, alpha)
    if not inference_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return _checked_failure(INF_ERR_ALPHA_RANGE, n1, n2, alpha)
    var g1 = List[Float64](capacity=n1)
    var g2 = List[Float64](capacity=n2)
    for i in range(total):
        if not inference_finite(values[i]):
            return _checked_failure(INF_ERR_NON_FINITE, n1, n2, alpha)
        if i < n1:
            g1.append(values[i])
        else:
            g2.append(values[i])

    var frozen = t_test_2sample(g1, g2)
    var v1 = _variance(g1)
    var v2 = _variance(g2)
    var m1: Float64 = 0.0
    for i in range(n1):
        m1 += g1[i]
    m1 /= Float64(n1)
    var m2: Float64 = 0.0
    for i in range(n2):
        m2 += g2[i]
    m2 /= Float64(n2)

    var se = sqrt(v1 / Float64(n1) + v2 / Float64(n2))
    if not inference_finite(se) or se <= 0.0:
        return _checked_failure(INF_ERR_DEGENERATE, n1, n2, alpha)
    var own_t = (m1 - m2) / se
    # Judged quantity: the frozen statistic. Scale: its own magnitude.
    var reproduced = fabs(own_t - frozen.statistic) <= inference_scaled_tol(
        frozen.statistic, 0.0
    )

    var a1 = v1 / Float64(n1)
    var a2 = v2 / Float64(n2)
    var num = (a1 + a2) * (a1 + a2)
    var den = a1 * a1 / Float64(n1 - 1) + a2 * a2 / Float64(n2 - 1)
    var df = Float64(total - 2)
    if den > 0.0:
        df = num / den
    if not inference_finite(df) or df <= 0.0:
        return _checked_failure(INF_ERR_DEGENERATE, n1, n2, alpha)

    var p = inference_t_sf_two_sided(frozen.statistic, df)
    if not inference_finite(p):
        return _checked_failure(INF_ERR_PVALUE_RANGE, n1, n2, alpha)
    # Judged quantity: the corrected p-value. Scale: its own magnitude, plus 1e-6 absolute --
    # the same tolerance `inference.core.t_cdf_agreement` uses, and for the same reason: the
    # two continued-fraction implementations agree to 5.8e-11 away from the branch-switch
    # threshold, but a narrow region right at that threshold can reach a gap of 3.4e-7 (see
    # `t_cdf_agreement`'s docstring), now that `stat_tests._regularized_incomplete_beta` is
    # fixed.
    var frozen_usable = (
        inference_finite(frozen.p_value)
        and fabs(frozen.p_value - p) <= inference_scaled_tol(p, 1e-6)
    )

    var lengths = List[Int](capacity=2)
    lengths.append(n1)
    lengths.append(n2)
    var homogeneity = variance_homogeneity_flat(values, lengths, alpha)
    var homo_p = homogeneity.p_value if homogeneity.status == INF_OK else ASSUME_P_ABSENT
    var homo_ok = homogeneity.status == INF_OK and homogeneity.satisfied

    var norm1 = residual_normality_flat(g1, n1, alpha)
    var norm2 = residual_normality_flat(g2, n2, alpha)
    var checked = norm1.status == INF_OK and norm2.status == INF_OK
    var ok1 = checked and norm1.satisfied
    var ok2 = checked and norm2.satisfied

    return CheckedTest(
        INF_OK, METHOD_WELCH, n1, n2, alpha, m1, m2, v1, v2,
        frozen.statistic, reproduced, df, p, frozen.p_value, frozen_usable,
        p < alpha, homo_p, homo_ok, checked, ok1, ok2, checked and ok1 and ok2,
    )


@fieldwise_init
struct CheckedProportionTest(Copyable, Movable):
    """A two-proportion z-test with the normal-approximation condition it depends on.

    `normal_approximation_ok` is True when every one of the four cells `n p̂` and `n (1-p̂)`
    reaches 5, which is the condition under which a binomial count is close enough to normal
    for this test's reference distribution to apply. `min_expected_cell` is the smallest of
    them, so a caller can see how far off it is.

    `p_value` is `inference_norm_sf_two_sided(z)` and `frozen_p_value` is
    `ab_testing.z_test_proportions`' own. These two normally agree to about 1e-7 — the frozen
    kernel's normal CDF is an Abramowitz-Stegun erf and `math_ext.norm_cdf` is a different one —
    so `frozen_p_value_usable` being True is the expected outcome here, unlike the t-test case.

    `ci_a` / `ci_b` are Wilson score intervals from `ab_testing.confidence_interval_proportion`,
    which divides by `n` without checking it; the counts are validated before that call.
    """

    var status: Int
    var method: String
    var n_a: Int
    var n_b: Int
    var alpha: Float64
    var p_hat_a: Float64
    var p_hat_b: Float64
    var z: Float64
    var p_value: Float64
    var frozen_p_value: Float64
    var frozen_p_value_usable: Bool
    var min_expected_cell: Float64
    var normal_approximation_ok: Bool
    var reject: Bool
    var ci_a_lo: Float64
    var ci_a_hi: Float64
    var ci_b_lo: Float64
    var ci_b_hi: Float64


def _proportion_failure(code: Int, n_a: Int, n_b: Int, alpha: Float64) -> CheckedProportionTest:
    return CheckedProportionTest(
        code, METHOD_TWO_PROPORTION_Z, n_a, n_b, alpha, -1.0, -1.0, 0.0,
        ASSUME_P_ABSENT, ASSUME_P_ABSENT, False, -1.0, False, False,
        0.0, 0.0, 0.0, 0.0,
    )


def proportion_test_checked_flat(
    successes_a: Int, n_a: Int, successes_b: Int, n_b: Int, alpha: Float64
) -> CheckedProportionTest:
    """The frozen two-proportion z-test, validated, with its normal-approximation verdict.

    `ab_testing.z_test_proportions` divides by `n_a`, `n_b` and `n_a + n_b` with no check at
    all, so `z_test_proportions(0, 0, 0, 0)` produces NaN for both the statistic and the
    p-value, and `is_significant(nan)` is False — a silent "not significant" for a request that
    contains no data. `ab_testing.confidence_interval_proportion` divides by `n` the same way.

    Everything is validated here first: `n >= 1` for both groups, `0 <= successes <= n`, and
    `alpha` strictly inside `(0, 1)`. Then the frozen kernels are called unchanged and their
    outputs re-checked for finiteness, because a validated input is not by itself a promise
    about a frozen kernel's output.

    `min_expected_cell` and `normal_approximation_ok` are the assumption verdict: this is a
    normal-approximation test, and on `n = 10` with `p̂ = 0.1` it is not one.
    """
    if n_a < 1 or n_b < 1:
        return _proportion_failure(INF_ERR_EMPTY, n_a, n_b, alpha)
    if n_a > MAX_ASSUME_OBS or n_b > MAX_ASSUME_OBS:
        return _proportion_failure(INF_ERR_DIMENSION_TOO_LARGE, n_a, n_b, alpha)
    if successes_a < 0 or successes_a > n_a or successes_b < 0 or successes_b > n_b:
        return _proportion_failure(INF_ERR_RESPONSE_RANGE, n_a, n_b, alpha)
    if not inference_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return _proportion_failure(INF_ERR_ALPHA_RANGE, n_a, n_b, alpha)

    var pa = Float64(successes_a) / Float64(n_a)
    var pb = Float64(successes_b) / Float64(n_b)
    var cells = List[Float64](capacity=4)
    cells.append(Float64(successes_a))
    cells.append(Float64(n_a - successes_a))
    cells.append(Float64(successes_b))
    cells.append(Float64(n_b - successes_b))
    var min_cell = cells[0]
    for i in range(1, 4):
        if cells[i] < min_cell:
            min_cell = cells[i]

    var frozen = z_test_proportions(successes_a, n_a, successes_b, n_b)
    if len(frozen) != 2:
        return _proportion_failure(INF_ERR_SHAPE, n_a, n_b, alpha)
    var z = frozen[0]
    if not inference_finite(z):
        return _proportion_failure(INF_ERR_DEGENERATE, n_a, n_b, alpha)
    var p = inference_norm_sf_two_sided(z)
    if not inference_finite(p):
        return _proportion_failure(INF_ERR_PVALUE_RANGE, n_a, n_b, alpha)
    # Judged quantity: the corrected p-value. Scale: its own magnitude, plus 1e-6 absolute for
    # the two normal CDFs' differing approximation error (measured ~1.4e-7 at z = 1.96).
    var usable = (
        inference_finite(frozen[1])
        and fabs(frozen[1] - p) <= inference_scaled_tol(p, 1e-6)
    )

    var confidence = 1.0 - alpha
    var ci_a = confidence_interval_proportion(successes_a, n_a, confidence)
    var ci_b = confidence_interval_proportion(successes_b, n_b, confidence)
    if len(ci_a) != 2 or len(ci_b) != 2:
        return _proportion_failure(INF_ERR_SHAPE, n_a, n_b, alpha)
    for i in range(2):
        if not inference_finite(ci_a[i]) or not inference_finite(ci_b[i]):
            return _proportion_failure(INF_ERR_DEGENERATE, n_a, n_b, alpha)

    return CheckedProportionTest(
        INF_OK, METHOD_TWO_PROPORTION_Z, n_a, n_b, alpha, pa, pb, z, p,
        frozen[1], usable, min_cell, min_cell >= 5.0, p < alpha,
        ci_a[0], ci_a[1], ci_b[0], ci_b[1],
    )
