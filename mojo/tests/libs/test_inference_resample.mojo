"""test_inference_resample.mojo — known-value tests for the reproducible resampling drivers.

Hand-written. Resampling produces a random quantity, so the assertions here are of four kinds
and none of them is "it returned something":

1. *Bit-identity under the same seed, and difference under another stream.* Two calls with the
   same `(seed, stream, n_resamples)` must return bitwise equal endpoints, standard error and
   bias — asserted with `==`, not a tolerance, because counter-based randomness makes a draw a
   pure function of its coordinates and anything less than equality means the coordinates are
   not what they claim. A different `stream` on the same seed must give a different interval,
   which is what makes an independent replication possible without changing the published seed.

2. *An EXACT closed form where the resampling has no freedom.* With `n1 = n2 = 1` every
   permutation of two observations produces the same absolute mean difference, so every one of
   them is "at least as extreme" and the p-value is exactly `(1 + B) / (1 + B) = 1.0`. That is
   asserted as `== 1.0`, and it also pins the `>=` in the extremeness comparison: with a strict
   `>` the count would be short by the identity permutation.

3. *A closed form the resampling must CONVERGE to.* The bootstrap standard error of the mean
   converges to `sigma_hat / sqrt(n)` with `sigma_hat^2 = sum (x - xbar)^2 / n`, i.e. to
   `s sqrt((n-1)/n) / sqrt(n)` in terms of the sample standard deviation. On the 20-point
   sample below that is 0.15988667861957728, and 4000 resamples give 0.15845694880994177 —
   0.89% low, against a Monte-Carlo standard error for an SD estimate of about
   `1/sqrt(2B) = 1.1%`. The assertion is 5% because that is roughly four Monte-Carlo standard
   errors; asserting tighter would be asserting the noise.

4. *An independent frozen computation of the same quantity.* The closed-form t interval for the
   same sample is `xbar +- t_{0.975,19} s / sqrt(20)` = [2.641659766796389, 3.328340233203612],
   built from `inference.core.inference_t_quantile` and the frozen
   `stats_bootstrap._mean` / `_std`. The percentile bootstrap interval [2.685, 3.300] must sit
   INSIDE it — a percentile interval uses the biased plug-in scale and no t inflation, so it is
   the narrower of the two by construction, and containment is the sharp statement of
   "brackets the closed-form t interval" rather than the vague one.

The permutation test also has a fully enumerable case: `values = [1,2,3,4]` split 2 and 2 has
six equally likely splits, with absolute mean differences 2, 1, 0, 0, 1, 2, so
`P(|d| >= 2) = 2/6 = 1/3` exactly. 3000 permutations at a fixed seed give 0.33422192602465844,
which is 0.0009 from 1/3 against a standard error of `sqrt((1/3)(2/3)/3000) = 0.0086`.
"""
from std.math import abs as fabs, sqrt

from inference.core import (
    INF_ERR_ALPHA_RANGE,
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_EMPTY,
    INF_ERR_NON_FINITE,
    INF_ERR_RESAMPLE_COUNT,
    INF_ERR_SHAPE,
    INF_ERR_TOO_FEW,
    INF_ERR_TUNING,
    INF_OK,
    MAX_RESAMPLES,
    inference_absent,
    inference_finite,
    inference_t_quantile,
)
from inference.resample import (
    STAT_MEAN,
    STAT_MEDIAN,
    STAT_STD,
    BootstrapCI,
    bootstrap_ci_flat,
    permutation_test_flat,
    resample_statistic_name,
)
from stats_bootstrap import _mean, _median, _std


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _sample20() -> List[Float64]:
    """A fixed 20-point sample. Never regenerated, so every number quoted above stays valid."""
    return _floats(
        2.1, 3.4, 1.9, 4.2, 2.8, 3.1, 2.5, 3.9, 2.2, 3.6,
        2.9, 4.1, 1.7, 3.3, 2.6, 3.8, 2.4, 3.0, 2.7, 3.5,
    )


fn _refused(c: BootstrapCI) -> Bool:
    """A refusal carries no interval, and says so in a field rather than by a value of 0.0."""
    return (
        c.status != INF_OK
        and not c.interval_known
        and c.lo == 0.0
        and c.hi == 0.0
        and c.lo_rank == -1
        and c.hi_rank == -1
    )


fn main():
    var passed: Int = 0
    var failed: Int = 0

    var x = _sample20()
    var mean_x = _mean(x)
    var sd_x = _std(x)

    # ── 1. bit-identity under the same seed ────────────────────────────────────
    var a = bootstrap_ci_flat(x, 20, STAT_MEAN, 4000, 0.95, 20260731, 5)
    var b = bootstrap_ci_flat(x, 20, STAT_MEAN, 4000, 0.95, 20260731, 5)
    var other_stream = bootstrap_ci_flat(x, 20, STAT_MEAN, 4000, 0.95, 20260731, 6)
    var other_seed = bootstrap_ci_flat(x, 20, STAT_MEAN, 4000, 0.95, 20260732, 5)
    if (
        a.status == INF_OK
        and a.interval_known
        and a.lo == b.lo
        and a.hi == b.hi
        and a.resample_se == b.resample_se
        and a.bias == b.bias
        and a.lo_mc_halfwidth == b.lo_mc_halfwidth
        and a.seed == 20260731
        and a.stream == 5
        and a.n_resamples == 4000
        # A different stream and a different seed each address different draws.
        and other_stream.lo != a.lo
        and other_seed.lo != a.lo
    ):
        passed += 1
        print("  ✅ same seed and stream reproduce BITWISE; another stream or seed does not")
    else:
        failed += 1
        print("  ❌ reproducibility broken:", a.lo, b.lo, other_stream.lo)

    # ── 2. the interval, and the point estimate straight from the frozen kernel ─
    if (
        a.point_estimate == mean_x
        and a.lo == 2.6849999999999996
        and a.hi == 3.3
        and a.lo < a.point_estimate
        and a.point_estimate < a.hi
        and a.lo_rank == 100
        and a.hi_rank == 3900
        and a.confidence == 0.95
        and a.statistic == STAT_MEAN
        and a.n_obs == 20
    ):
        passed += 1
        print("  ✅ the interval is [2.685, 3.300] at ranks 100 and 3900 of 4000")
    else:
        failed += 1
        print("  ❌ interval wrong:", a.lo, a.hi, a.lo_rank, a.hi_rank)

    # ── 3. containment in the closed-form t interval ───────────────────────────
    # xbar +- t_{0.975,19} s / sqrt(20), with t_{0.975,19} = 2.0930240544283807.
    var tq = inference_t_quantile(0.975, 19.0)
    var half = tq * sd_x / sqrt(20.0)
    var t_lo = mean_x - half
    var t_hi = mean_x + half
    if (
        fabs(tq - 2.0930240544283807) <= 1.0e-9
        and fabs(t_lo - 2.641659766796389) <= 1.0e-12
        and fabs(t_hi - 3.328340233203612) <= 1.0e-12
        # The percentile interval is the narrower of the two by construction (plug-in scale, no
        # t inflation), so containment is the sharp form of "brackets the t interval".
        and t_lo <= a.lo
        and a.hi <= t_hi
        and t_lo < t_hi
    ):
        passed += 1
        print("  ✅ the bootstrap interval sits inside the closed-form t interval")
    else:
        failed += 1
        print("  ❌ containment failed:", t_lo, a.lo, a.hi, t_hi)

    # ── 4. the standard error converges to its closed form ────────────────────
    # se_boot -> s sqrt((n-1)/n) / sqrt(n) = 0.15988667861957728 on this sample.
    var se_closed = sd_x * sqrt(19.0 / 20.0) / sqrt(20.0)
    var relative_gap = fabs(a.resample_se / se_closed - 1.0)
    if (
        fabs(se_closed - 0.15988667861957728) <= 1.0e-15
        and fabs(a.resample_se - 0.15845694880994177) <= 1.0e-15
        and relative_gap <= 0.05
        and relative_gap >= 0.0
        # The bias of the bootstrap mean is zero in expectation, so the measured bias must be
        # small relative to the standard error rather than exactly zero.
        and fabs(a.bias) <= 0.2 * a.resample_se
    ):
        passed += 1
        print("  ✅ the resample SE is 0.89% from its closed form, and the bias is ~0")
    else:
        failed += 1
        print("  ❌ SE convergence:", a.resample_se, se_closed, relative_gap)

    # ── 5. the Monte-Carlo uncertainty OF THE INTERVAL ────────────────────────
    # The endpoint rank is Binomial(B, 0.025), so its SD is sqrt(4000 * 0.025 * 0.975) =
    # 9.874208829065754 ranks. The reported half-widths are the value-scale spread across that
    # many ranks, measured on the resample distribution.
    var rank_sd_closed = sqrt(4000.0 * 0.025 * 0.975)
    if (
        fabs(a.endpoint_rank_sd - rank_sd_closed) <= 1.0e-12
        and fabs(a.endpoint_rank_sd - 9.874208829065754) <= 1.0e-12
        and a.lo_mc_halfwidth > 0.0
        and a.hi_mc_halfwidth > 0.0
        # The endpoint uncertainty must be far smaller than the interval it qualifies,
        # otherwise B is too small to quote the interval at all.
        and a.lo_mc_halfwidth < 0.1 * (a.hi - a.lo)
        and a.hi_mc_halfwidth < 0.1 * (a.hi - a.lo)
    ):
        passed += 1
        print("  ✅ the endpoint rank SD is sqrt(B a (1-a)) and the value-scale spread is small")
    else:
        failed += 1
        print("  ❌ MC uncertainty:", a.endpoint_rank_sd, a.lo_mc_halfwidth)

    # ── 6. the other two statistics come from the frozen kernels ──────────────
    var med = bootstrap_ci_flat(x, 20, STAT_MEDIAN, 500, 0.95, 20260731, 5)
    var std_ci = bootstrap_ci_flat(x, 20, STAT_STD, 1000, 0.95, 20260731, 5)
    if (
        med.status == INF_OK
        and med.point_estimate == _median(x)
        and med.lo <= med.point_estimate
        and med.point_estimate <= med.hi
        and std_ci.status == INF_OK
        and std_ci.point_estimate == _std(x)
        and std_ci.point_estimate == sd_x
        and std_ci.lo <= sd_x
        and sd_x <= std_ci.hi
        and resample_statistic_name(STAT_MEAN) == "mean"
        and resample_statistic_name(STAT_MEDIAN) == "median"
        and resample_statistic_name(STAT_STD) == "standard_deviation"
        and resample_statistic_name(7) == "unknown"
    ):
        passed += 1
        print("  ✅ median and sd point estimates ARE the frozen kernels' own values")
    else:
        failed += 1
        print("  ❌ statistic selection wrong:", med.point_estimate, _median(x))

    # ── 7. the permutation test's exact case ──────────────────────────────────
    # n1 = n2 = 1: every permutation gives the same |mean difference|, so every one of them is
    # at least as extreme and p is exactly 1.0. With a strict `>` the identity permutation
    # would be missed and p would come out below 1.
    var two = _floats(0.0, 1.0)
    var exact = permutation_test_flat(two, 1, 1, 50, 5, 3)
    if (
        exact.status == INF_OK
        and exact.p_value == 1.0
        and exact.count_at_least_as_extreme == 50
        and exact.observed_diff == -1.0
        and fabs(exact.p_value_floor - 1.0 / 51.0) <= 1.0e-15
        and exact.mean1 == 0.0
        and exact.mean2 == 1.0
    ):
        passed += 1
        print("  ✅ two observations give p exactly 1.0 — the >= comparison is right")
    else:
        failed += 1
        print("  ❌ exact permutation case:", exact.p_value, exact.count_at_least_as_extreme)

    # ── 8. the permutation test against an enumerable probability ─────────────
    # [1,2,3,4] split 2/2: the six splits give |d| of 2, 1, 0, 0, 1, 2, so P(|d| >= 2) = 1/3.
    var quad = _floats(1.0, 2.0, 3.0, 4.0)
    var pt = permutation_test_flat(quad, 2, 2, 3000, 99, 3)
    var pt_again = permutation_test_flat(quad, 2, 2, 3000, 99, 3)
    if (
        pt.status == INF_OK
        and pt.observed_diff == -2.0
        and fabs(pt.p_value - 1.0 / 3.0) <= 0.05
        and fabs(pt.p_value - 0.33422192602465844) <= 1.0e-15
        and pt.p_value == pt_again.p_value
        and pt.count_at_least_as_extreme == 1002
        and pt.n_permutations == 3000
        and pt.seed == 99
        and pt.stream == 3
        # never zero, and the floor says how small a p-value this B could ever produce
        and pt.p_value > 0.0
        and fabs(pt.p_value_floor - 1.0 / 3001.0) <= 1.0e-15
    ):
        passed += 1
        print("  ✅ 3000 permutations estimate the enumerable 1/3 to 0.0009, reproducibly")
    else:
        failed += 1
        print("  ❌ permutation estimate:", pt.p_value, pt.count_at_least_as_extreme)

    # ── 9. a p-value of zero does not exist, even when nothing is as extreme ──
    # Two groups this far apart: no permutation of the pooled values reaches the observed
    # difference, so the raw count is the identity permutation's contribution only. The frozen
    # `stats_bootstrap.bootstrap_test` would return count/B here, which can be 0.0.
    var separated = _floats(0.0, 0.1, 0.2, 100.0, 100.1, 100.2)
    var strong = permutation_test_flat(separated, 3, 3, 200, 11, 3)
    if (
        strong.status == INF_OK
        and strong.p_value > 0.0
        and strong.p_value <= 0.06
        and fabs(strong.p_value_floor - 1.0 / 201.0) <= 1.0e-15
        and strong.p_value >= strong.p_value_floor
    ):
        passed += 1
        print("  ✅ a maximally separated pair still has p > 0, floored at 1/(1+B)")
    else:
        failed += 1
        print("  ❌ zero p-value leaked:", strong.p_value, strong.count_at_least_as_extreme)

    # ── 10. refusals ─────────────────────────────────────────────────────────
    if (
        # an unrecognised statistic is refused, never silently treated as the mean
        _refused(bootstrap_ci_flat(x, 20, 9, 100, 0.95, 1, 1))
        and bootstrap_ci_flat(x, 20, 9, 100, 0.95, 1, 1).status == INF_ERR_TUNING
        and _refused(bootstrap_ci_flat(x, 0, STAT_MEAN, 100, 0.95, 1, 1))
        and bootstrap_ci_flat(x, 0, STAT_MEAN, 100, 0.95, 1, 1).status == INF_ERR_EMPTY
        # a declared n larger than the payload would read past the end (rule 1)
        and bootstrap_ci_flat(x, 25, STAT_MEAN, 100, 0.95, 1, 1).status == INF_ERR_SHAPE
        and bootstrap_ci_flat(_floats(1.0), 1, STAT_STD, 100, 0.95, 1, 1).status
        == INF_ERR_TOO_FEW
        and bootstrap_ci_flat(x, 20, STAT_MEAN, 0, 0.95, 1, 1).status
        == INF_ERR_RESAMPLE_COUNT
        and bootstrap_ci_flat(x, 20, STAT_MEAN, MAX_RESAMPLES + 1, 0.95, 1, 1).status
        == INF_ERR_RESAMPLE_COUNT
        and bootstrap_ci_flat(x, 20, STAT_MEAN, 100, 1.0, 1, 1).status
        == INF_ERR_ALPHA_RANGE
        and bootstrap_ci_flat(x, 20, STAT_MEAN, 100, 0.0, 1, 1).status
        == INF_ERR_ALPHA_RANGE
        and bootstrap_ci_flat(_floats(1.0, inference_absent()), 2, STAT_MEAN, 10, 0.95, 1, 1).status
        == INF_ERR_NON_FINITE
    ):
        passed += 1
        print("  ✅ nine bad requests are refused with distinct statuses and no interval")
    else:
        failed += 1
        print("  ❌ a bootstrap refusal leaked")

    if (
        permutation_test_flat(quad, 2, 3, 100, 1, 1).status == INF_ERR_SHAPE
        and permutation_test_flat(quad, 0, 4, 100, 1, 1).status == INF_ERR_EMPTY
        and permutation_test_flat(quad, 2, 2, 0, 1, 1).status == INF_ERR_RESAMPLE_COUNT
        and permutation_test_flat(quad, 2, 2, MAX_RESAMPLES + 1, 1, 1).status
        == INF_ERR_RESAMPLE_COUNT
        and permutation_test_flat(
            _floats(1.0, inference_absent()), 1, 1, 10, 1, 1
        ).status == INF_ERR_NON_FINITE
        and permutation_test_flat(quad, 2, 3, 100, 1, 1).p_value == -1.0
    ):
        passed += 1
        print("  ✅ a mismatched group split is refused, and a refusal's p_value is -1.0")
    else:
        failed += 1
        print("  ❌ a permutation refusal leaked")

    # ── 11. the A-Z harness shapes, which must refuse rather than abort ───────
    # The generated suite calls with _lf5 and 5 for every Int, so the statistic selector is 5
    # (unrecognised) and the permutation split declares 10 observations backed by 5.
    var lf5 = _floats(0.5, 0.6, 0.7, 0.4, 0.3)
    if (
        bootstrap_ci_flat(lf5, 5, 5, 5, 0.5, 42, 42).status == INF_ERR_TUNING
        and _refused(bootstrap_ci_flat(lf5, 5, 5, 5, 0.5, 42, 42))
        and permutation_test_flat(lf5, 5, 5, 5, 42, 42).status == INF_ERR_SHAPE
    ):
        passed += 1
        print("  ✅ both harness calls are refused, not indexed past the end")
    else:
        failed += 1
        print("  ❌ a harness call was not refused")

    # ── 12. a work budget that counts every factor ───────────────────────────
    # The median statistic sorts, so its cost is B * n^2 and the budget charges the product.
    # 2^20 resamples of a 2^12 sample is 1.7e13 operations and must be refused for WORK even
    # though every individual dimension is inside its own ceiling.
    var big = List[Float64](capacity=4096)
    for i in range(4096):
        big.append(Float64(i % 17))
    if (
        bootstrap_ci_flat(big, 4096, STAT_MEDIAN, MAX_RESAMPLES, 0.95, 1, 1).status
        == INF_ERR_DIMENSION_TOO_LARGE
        and bootstrap_ci_flat(big, 4096, STAT_MEAN, 8, 0.95, 1, 1).status == INF_OK
    ):
        passed += 1
        print("  ✅ the B*n^2 work product is charged, while a small request still runs")
    else:
        failed += 1
        print("  ❌ work budget not charged")

    print("  [inference.resample] Passed:", passed, "Failed:", failed)
