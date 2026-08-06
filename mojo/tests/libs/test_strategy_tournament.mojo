"""test_strategy_tournament.mojo — known-value suite for the paired ranking.

Hand-written. Two things have to be true for this package to be worth shipping, and both are
MEASURED here rather than claimed.

1. THE RANKING CAN SAY "NO SIGNIFICANT DIFFERENCE"
--------------------------------------------------
A tournament that always names a winner is a random number generator with extra steps. So the
suite builds strategies that genuinely tie and asserts the verdict is `NO_DIFFERENCE` with NO
winner — twice, in two different ways, because the two failure modes are different:

  * EXCHANGEABLE, non-degenerate: strategy A reads exogenous factor 0 and strategy B reads
    factor 1 of the SAME scenario tape. The two factors are independent draws of one
    distribution, so the strategies are exchangeable: their mean difference is zero in
    expectation and their difference has real variance. Measured p = 0.6065 over 200 scenarios,
    which is a tie with noise in it — the case a coin-flip ranking would get wrong half the time.
  * IDENTICAL: strategy C is strategy A's parameters again. Every difference is exactly 0.0, the
    sample variance is exactly zero, and the paired t is `0/0`. That is the branch where a NaN
    would be born and the dispatch would then refuse the whole response, so it is handled
    explicitly and the p-value is exactly 1.0.

Both are asserted at tournament level too: three strategies, three comparisons, none
significant, every rank 1, one distinct rank, `has_winner` False.

The reverse also has to hold, or the suite would pass for a ranking that never rejects anything:
the same machinery finds a real winner on the same generator, at p = 5.26e-137.

2. THE PAIRING IS REAL, AND BOTH NUMBERS ARE PRINTED
----------------------------------------------------
Two threshold policies (0.40 and 0.60) over a 64-step discounted horizon, 200 scenarios:

    PAIRED    (both policies on the SAME scenario r)          variance 0.048869
    UNPAIRED  (policy B moved to scenario r + 200)            variance 0.311092
    ratio                                                     6.366

and the analytic `Var(A) + Var(B) = 0.292530` — a second, independent route to the unpaired
variance that lands within 6% of the resampled one. The confidence interval on the difference is
2.52x TIGHTER paired than unpaired for identical work. The two scenario tapes the two strategies
read fold to the identical 62-bit digest 3651692285088114128, while scenario 8 folds to
3772497484416744945: the environment is bit-identical across strategies and different across
scenarios, measured through `strat_crn_fold` rather than asserted in a comment.

The p-value is a KNOWN VALUE, not the tree's own output
------------------------------------------------------
Student-t on 4 degrees of freedom has an exact closed form. Substituting `t = 2 tan(theta)` in
`f(t) = 0.375 (1 + t^2/4)^(-5/2)` gives `0.75 cos^3(theta) d(theta)`, so the two-sided tail is

    p(t) = 1 - 1.5 s + 0.5 s^3,     s = t / sqrt(t^2 + 4)

`_closed_p_df4` below is that formula and NOTHING in the engine computes it. On 2 degrees of
freedom the same substitution gives `p(t) = 1 - t / sqrt(t^2 + 2)`, and `_closed_p_df2` is used
as a second, independent check on the same frozen function. For the suite's own comparison,
`t = 3 sqrt(2)` on 4 df: the closed form gives 0.013235599563682532 and the frozen
`inference_t_sf_two_sided` returns 0.013235599551274032 — agreement to 1.2e-11 absolute, which
is the frozen kernel's accuracy at this df and an order of magnitude tighter than the 1e-9 the
assertion allows.

The critical value is checked against R's `qt(0.975, 4) = 2.7764451051977987`, not against
whatever the tree happens to compute; the tree's bisection agrees to 3.6e-10.

The hand matrix, and why it is exactly this
-------------------------------------------
    S0 = [10, 11, 12, 13, 14]     mean 12, sample variance 2.5
    S1 = [ 9, 10, 11, 12, 13]     mean 11, sample variance 2.5
    S2 = [ 9,  9,  9,  9,  9]     mean  9, sample variance 0

Every quantity below is exact rational arithmetic:

  * pair (0,1): every difference is 1.0. Deterministic dominance — zero variance, nonzero mean.
  * pair (0,2): differences [1,2,3,4,5], mean 3, variance 2.5, se sqrt(0.5), t = 3 sqrt(2).
  * pair (1,2): differences [0,1,2,3,4], mean 2, variance 2.5, se sqrt(0.5), t = 2 sqrt(2).

and it was chosen because THE MULTIPLICITY CORRECTION CHANGES A VERDICT on it. Pair (1,2) has an
uncorrected p of 0.047421, below alpha = 0.05, and a Bonferroni-adjusted p of exactly three times
that, 0.142262, above it. So the tournament reports 3 significant uncorrected and 2 corrected,
and the pair drops from "significant" to "no significant difference" — the correction is visible
in the answer instead of being taken on trust. Under Holm the adjusted value for the middle pair
is exactly 2p and under Benjamini-Hochberg exactly 3p/2, both checked here, and the three
procedures find 2, 3 and 3 significant pairs: the power ordering
Bonferroni <= Holm <= Benjamini-Hochberg, which is the property `inference.multiplicity`'s own
agreement check exists to state.

S2 is CONSTANT on purpose. Its variance is exactly zero, so for pair (0,2)
`Var(a - b) = Var(a) = Var(a) + Var(b)` — the paired variance EQUALS the unpaired one under
perfect pairing, and `all_pairs_paired_lower` is correctly False. That is why the module reports
the pairing gain rather than enforcing it: a driver that refused to rank unless every pair showed
a strict reduction would refuse this correct tournament.

Ties as ties, and a partial order reported as one
-------------------------------------------------
Ranks on the hand matrix are 1, 2, 2 — S1 and S2 SHARE rank 2 because neither significantly beats
the other, which is what "a tie expressed as a tie" means: one number appearing twice, not an
arbitrary order. Flipping `higher_is_better` to False on the same matrix produces ranks 3, 1, 1
and a verdict of UNDECIDED with no winner, because two strategies now sit at rank 1 and the
comparison between them is not significant. A ranking that named one of them the winner would be
reporting a preference it never measured.
"""
from std.math import abs as fabs, sqrt

from determinism.counter_rng import rng_uniform
from strategy.contract import (
    STRAT_ERR_COUNT,
    STRAT_ERR_DEGENERATE,
    STRAT_ERR_DIMENSION_TOO_LARGE,
    STRAT_ERR_EMPTY,
    STRAT_ERR_LEVEL_RANGE,
    STRAT_ERR_NON_FINITE,
    STRAT_ERR_SEED_RANGE,
    STRAT_ERR_SHAPE,
    STRAT_ERR_TOLERANCE,
    STRAT_ERR_TOO_FEW_REPLICATIONS,
    STRAT_ERR_TOO_FEW_STRATEGIES,
    STRAT_ERR_UNKNOWN_METHOD,
    STRAT_ERR_WORK_BUDGET,
    STRAT_OK,
    STRAT_VERDICT_A_BETTER,
    STRAT_VERDICT_B_BETTER,
    STRAT_VERDICT_NO_DIFFERENCE,
    STRAT_VERDICT_UNDECIDED,
    strat_crn_fold,
    strat_stream_scenario,
    strat_verdict_is_decided,
)
from strategy.tournament import (
    TOURNEY_METHOD_BH,
    TOURNEY_METHOD_BONFERRONI,
    TOURNEY_METHOD_HOLM,
    tourney_method_name,
    tourney_outcome_cell,
    tourney_outcome_status,
    tourney_pair_count,
    tourney_paired_bootstrap_flat,
    tourney_paired_diff_flat,
    tourney_rank_flat,
    tourney_work_charge,
)


def _closed_p_df4(t: Float64) -> Float64:
    """Exact two-sided Student-t tail on 4 df: `1 - 1.5 s + 0.5 s^3`, `s = t / sqrt(t^2 + 4)`.

    Derived by hand from the density, and deliberately not a call into the engine: a suite that
    checked the engine against the engine would pass for any consistent error.
    """
    var s = t / sqrt(t * t + 4.0)
    return 1.0 - 1.5 * s + 0.5 * s * s * s


def _closed_p_df2(t: Float64) -> Float64:
    """Exact two-sided Student-t tail on 2 df: `1 - t / sqrt(t^2 + 2)`. Same derivation."""
    return 1.0 - t / sqrt(t * t + 2.0)


def _hand_matrix() -> List[Float64]:
    """S0 = 10..14, S1 = 9..13, S2 = 9 constant, strategy-major."""
    var o = List[Float64]()
    for i in range(5):
        o.append(10.0 + Float64(i))
    for i in range(5):
        o.append(9.0 + Float64(i))
    for _ in range(5):
        o.append(9.0)
    return o^


def _payoff(
    seed: Int, family: Int, scenario: Int, horizon: Int, factor: Int,
    threshold: Float64, gamma: Float64, stream: Int,
) -> Float64:
    """The reference strategy evaluation: a discounted threshold policy on a CRN scenario.

    `sum over t of gamma^t * max(0, u(t, factor) - threshold)`, where `u` is the frozen
    `rng_uniform` addressed at `(seed, family, scenario, step, factor, stream, 0)`. THE STRATEGY
    IS NOT A COORDINATE — the threshold changes the payoff and not one drawn number — which is
    what makes two thresholds evaluated at one scenario a paired comparison.

    Written here rather than imported so the outcomes the ranking is judged on come from
    somewhere other than the code being judged.
    """
    var total: Float64 = 0.0
    var disc: Float64 = 1.0
    for t in range(horizon):
        var u = rng_uniform(
            UInt64(seed), UInt64(family), UInt64(scenario), UInt64(t), UInt64(factor),
            UInt64(stream), UInt64(0),
        )
        var gain = u - threshold
        if gain > 0.0:
            total += disc * gain
        disc *= gamma
    return total


def _tape(
    seed: Int, family: Int, scenario: Int, horizon: Int, factor: Int, stream: Int
) -> List[Float64]:
    """Every draw one strategy reads at one scenario, in order, for the digest comparison."""
    var out = List[Float64](capacity=horizon)
    for t in range(horizon):
        out.append(
            rng_uniform(
                UInt64(seed), UInt64(family), UInt64(scenario), UInt64(t), UInt64(factor),
                UInt64(stream), UInt64(0),
            )
        )
    return out^


def main():
    var passed = 0
    var failed = 0
    print("\n[strategy.tournament] known-value suite")

    var m = _hand_matrix()
    var t = tourney_rank_flat(m, 3, 5, 0.95, 0.05, TOURNEY_METHOD_BONFERRONI, True, 1.0e-12)

    # ── per-strategy means, variances and intervals, all exact rational values ─
    var ok_means = t.status == STRAT_OK and t.ranked and len(t.mean) == 3
    ok_means = ok_means and t.mean[0] == 12.0 and t.mean[1] == 11.0 and t.mean[2] == 9.0
    ok_means = ok_means and t.variance[0] == 2.5 and t.variance[1] == 2.5
    ok_means = ok_means and t.variance[2] == 0.0
    ok_means = ok_means and t.has_ci[0] and t.has_ci[1] and t.has_ci[2]
    # 12 -+ qt(0.975,4) * sqrt(2.5/5) = 12 -+ 2.7764451051977987 * 0.7071067811865476
    ok_means = ok_means and fabs(t.ci_lower[0] - 10.036756838270254) < 1.0e-9
    ok_means = ok_means and fabs(t.ci_upper[0] - 13.963243161729746) < 1.0e-9
    ok_means = ok_means and t.ci_lower[2] == 9.0 and t.ci_upper[2] == 9.0
    if ok_means:
        passed += 1
        print(
            "  ✅ means 12/11/9 and variances 2.5/2.5/0 exact; S0's interval",
            "[10.03675684, 13.96324316] from qt(0.975,4) by hand; the constant strategy's",
            "interval is a point",
        )
    else:
        failed += 1
        print("  ❌ per-strategy statistics wrong:", t.mean[0], t.variance[0], t.ci_lower[0])

    # ── the paired p-values against the EXACT closed form on 4 df ─────────────
    var t02 = 3.0 * sqrt(2.0)
    var t12 = 2.0 * sqrt(2.0)
    var exact02 = _closed_p_df4(t02)
    var exact12 = _closed_p_df4(t12)
    var ok_p = len(t.pair_p) == 3
    ok_p = ok_p and t.pair_mean_diff[0] == 1.0 and t.pair_mean_diff[1] == 3.0
    ok_p = ok_p and t.pair_mean_diff[2] == 2.0
    ok_p = ok_p and fabs(t.pair_p[1] - exact02) < 1.0e-9
    ok_p = ok_p and fabs(t.pair_p[2] - exact12) < 1.0e-9
    ok_p = ok_p and t.pair_p[0] == 0.0
    if ok_p:
        passed += 1
        print(
            "  ✅ paired p-values match the hand-derived closed form on 4 df:",
            t.pair_p[1], "vs", exact02, "and", t.pair_p[2], "vs", exact12,
        )
    else:
        failed += 1
        print("  ❌ p-values disagree with the closed form:", t.pair_p[1], exact02)

    # The same frozen function on 2 df, against the other closed form, so the check is not
    # specific to one degree of freedom. A = [4, 6, 8], B = [1, 2, 6]: differences [3, 4, 2],
    # mean 3, sample variance 1, standard error sqrt(1/3), t = 3 sqrt(3) = 5.196152422706632,
    # and the exact two-sided tail on 2 df is 1 - 3 sqrt(3) / sqrt(29) = 0.03509871864598457
    # (that constant is the closed form evaluated in double precision, not a hand-rounded
    # decimal — the first draft of this line carried a hand-computed 0.03509860597332867, which
    # is wrong in the seventh digit and failed against a frozen kernel that was right).
    var two_df = List[Float64]()
    two_df.append(4.0)
    two_df.append(6.0)
    two_df.append(8.0)
    two_df.append(1.0)
    two_df.append(2.0)
    two_df.append(6.0)
    var t3 = tourney_paired_diff_flat(two_df, 2, 3, 0, 1, 0.95, 0.05, True, 1.0e-12)
    var ok_df2 = t3.status == STRAT_OK and t3.has_p and t3.has_t_stat
    ok_df2 = ok_df2 and t3.mean_diff == 3.0 and t3.paired_variance == 1.0
    ok_df2 = ok_df2 and fabs(t3.t_stat - 3.0 * sqrt(3.0)) < 1.0e-12
    ok_df2 = ok_df2 and fabs(t3.p_value - _closed_p_df2(3.0 * sqrt(3.0))) < 1.0e-9
    ok_df2 = ok_df2 and fabs(t3.p_value - 0.03509871864598457) < 1.0e-9
    if ok_df2:
        passed += 1
        print(
            "  ✅ on 2 df, t = 3 sqrt(3) gives", t3.p_value, "against the hand-derived",
            "1 - 3 sqrt(3)/sqrt(29) =", _closed_p_df2(3.0 * sqrt(3.0)),
        )
    else:
        failed += 1
        print("  ❌ the 2-df closed form disagrees:", t3.p_value, t3.t_stat, t3.mean_diff,
              t3.paired_variance)

    # ── the multiplicity correction, exact multipliers, and a CHANGED verdict ─
    var ok_corr = fabs(t.pair_adjusted[1] - 3.0 * t.pair_p[1]) < 1.0e-15
    ok_corr = ok_corr and fabs(t.pair_adjusted[2] - 3.0 * t.pair_p[2]) < 1.0e-15
    ok_corr = ok_corr and t.pair_adjusted[2] > 0.05 and t.pair_p[2] < 0.05
    ok_corr = ok_corr and t.n_significant == 2 and t.n_significant_uncorrected == 3
    ok_corr = ok_corr and t.pair_rejected[1] and not t.pair_rejected[2]
    ok_corr = ok_corr and t.pair_verdict[2] == STRAT_VERDICT_NO_DIFFERENCE
    ok_corr = ok_corr and t.n_comparisons == 3 and t.multiplicity_corrected
    ok_corr = ok_corr and t.method_name == tourney_method_name(TOURNEY_METHOD_BONFERRONI)
    if ok_corr:
        passed += 1
        print(
            "  ✅ Bonferroni adjusted is exactly 3p, and pair (1,2) goes from p =", t.pair_p[2],
            "significant to adjusted", t.pair_adjusted[2], "NOT significant: 3 uncorrected",
            "against 2 corrected",
        )
    else:
        failed += 1
        print("  ❌ the correction did not change what it must:", t.pair_adjusted[2],
              t.n_significant, t.n_significant_uncorrected)

    var th = tourney_rank_flat(m, 3, 5, 0.95, 0.05, TOURNEY_METHOD_HOLM, True, 1.0e-12)
    var tb = tourney_rank_flat(m, 3, 5, 0.95, 0.05, TOURNEY_METHOD_BH, True, 1.0e-12)
    var ok_methods = fabs(th.pair_adjusted[1] - 2.0 * t.pair_p[1]) < 1.0e-15
    ok_methods = ok_methods and fabs(tb.pair_adjusted[1] - 1.5 * t.pair_p[1]) < 1.0e-15
    ok_methods = ok_methods and t.n_significant <= th.n_significant
    ok_methods = ok_methods and th.n_significant <= tb.n_significant
    ok_methods = ok_methods and th.n_significant == 3 and tb.n_significant == 3
    ok_methods = ok_methods and th.method_name != t.method_name
    ok_methods = ok_methods and tb.method_name != th.method_name
    if ok_methods:
        passed += 1
        print(
            "  ✅ Holm's middle adjusted value is exactly 2p and Benjamini-Hochberg's exactly",
            "1.5p; significant pairs run 2 <= 3 <= 3 across the three procedures, and each",
            "names itself:", t.method_name, "/", th.method_name, "/", tb.method_name,
        )
    else:
        failed += 1
        print("  ❌ the three procedures do not order as they must:", t.n_significant,
              th.n_significant, tb.n_significant, th.pair_adjusted[1])

    # ── ranks, with the tie expressed as a tie ────────────────────────────────
    var ok_rank = t.rank[0] == 1 and t.rank[1] == 2 and t.rank[2] == 2
    ok_rank = ok_rank and t.n_better[0] == 0 and t.n_worse[0] == 2
    ok_rank = ok_rank and t.n_at_rank_1 == 1 and t.n_distinct_ranks == 2
    ok_rank = ok_rank and t.has_winner and t.winner == 0
    ok_rank = ok_rank and t.verdict == STRAT_VERDICT_A_BETTER and t.decided
    ok_rank = ok_rank and t.n_undecided_pairs == 0
    if ok_rank:
        passed += 1
        print(
            "  ✅ ranks 1, 2, 2 — S1 and S2 SHARE rank 2 because neither beats the other; one",
            "strategy at rank 1, two distinct ranks, winner 0",
        )
    else:
        failed += 1
        print("  ❌ ranks or winner wrong:", t.rank[0], t.rank[1], t.rank[2], t.winner)

    # Lower-is-better on the same data: two strategies tie for first, so there is NO winner.
    var tl = tourney_rank_flat(m, 3, 5, 0.95, 0.05, TOURNEY_METHOD_BONFERRONI, False, 1.0e-12)
    var ok_low = tl.rank[0] == 3 and tl.rank[1] == 1 and tl.rank[2] == 1
    ok_low = ok_low and not tl.has_winner and tl.winner == -1
    ok_low = ok_low and tl.verdict == STRAT_VERDICT_UNDECIDED and not tl.decided
    ok_low = ok_low and tl.n_at_rank_1 == 2 and tl.n_significant == 2
    ok_low = ok_low and tl.pair_verdict[0] == STRAT_VERDICT_B_BETTER
    if ok_low:
        passed += 1
        print(
            "  ✅ lower-is-better inverts the same data to ranks 3, 1, 1 and reports UNDECIDED",
            "with no winner: two strategies at rank 1 and no significant pair between them",
        )
    else:
        failed += 1
        print("  ❌ the partial order was resolved into a winner it does not have:",
              tl.rank[0], tl.rank[1], tl.rank[2], tl.winner, tl.verdict)

    # ── the deterministic pair: zero variance, and no NaN anywhere ────────────
    var det = tourney_paired_diff_flat(m, 3, 5, 0, 1, 0.95, 0.05, True, 1.0e-12)
    var ok_det = det.status == STRAT_OK and det.deterministic
    ok_det = ok_det and det.mean_diff == 1.0 and det.paired_variance == 0.0
    ok_det = ok_det and det.std_error == 0.0 and det.has_p and det.p_value == 0.0
    ok_det = ok_det and not det.has_t_stat and det.t_stat == 0.0
    ok_det = ok_det and not det.has_variance_ratio and det.variance_ratio == 0.0
    ok_det = ok_det and det.paired_variance_lower and det.unpaired_variance == 5.0
    ok_det = ok_det and det.verdict == STRAT_VERDICT_A_BETTER
    ok_det = ok_det and det.ci_lower == 1.0 and det.ci_upper == 1.0
    ok_det = ok_det and not det.multiplicity_corrected
    if ok_det:
        passed += 1
        print(
            "  ✅ a difference of exactly 1.0 on every scenario: variance 0, p = 0, the t",
            "statistic ABSENT with 0.0 in its slot rather than an infinity, the variance ratio",
            "ABSENT rather than a division by zero, and the interval the point [1.0, 1.0]",
        )
    else:
        failed += 1
        print("  ❌ the deterministic branch leaked a non-finite or an invented statistic:",
              det.p_value, det.has_t_stat, det.t_stat, det.has_variance_ratio)

    # ── the constant strategy: paired == unpaired under PERFECT pairing ───────
    var ok_flat = t.pair_paired_variance[1] == 2.5 and t.pair_unpaired_variance[1] == 2.5
    ok_flat = ok_flat and t.has_min_variance_ratio and t.min_variance_ratio == 1.0
    ok_flat = ok_flat and not t.all_pairs_paired_lower
    if ok_flat:
        passed += 1
        print(
            "  ✅ against the CONSTANT strategy the paired and unpaired variances are both 2.5",
            "and the ratio is exactly 1.0, so `all_pairs_paired_lower` is False — which is why",
            "the pairing gain is reported and not enforced",
        )
    else:
        failed += 1
        print("  ❌ the constant-strategy pairing gain is wrong:", t.pair_paired_variance[1],
              t.pair_unpaired_variance[1], t.min_variance_ratio)

    # ── COMMON RANDOM NUMBERS: the variance reduction, both numbers printed ───
    var stream = strat_stream_scenario()
    var reps = 200
    var horizon = 64
    var gamma = 0.9
    var paired = List[Float64]()
    var unpaired = List[Float64]()
    for r in range(reps):
        paired.append(_payoff(7, 3, r, horizon, 0, 0.40, gamma, stream))
    for r in range(reps):
        paired.append(_payoff(7, 3, r, horizon, 0, 0.60, gamma, stream))
    for r in range(reps):
        unpaired.append(_payoff(7, 3, r, horizon, 0, 0.40, gamma, stream))
    for r in range(reps):
        # The SAME policy, evaluated on a different scenario index: an unpaired comparison of
        # exactly the same two strategies, for exactly the same work.
        unpaired.append(_payoff(7, 3, r + reps, horizon, 0, 0.60, gamma, stream))
    var dp = tourney_paired_diff_flat(paired, 2, reps, 0, 1, 0.95, 0.05, True, 1.0e-12)
    var du = tourney_paired_diff_flat(unpaired, 2, reps, 0, 1, 0.95, 0.05, True, 1.0e-12)
    print(
        "     PAIRED   variance", dp.paired_variance, " half-width", dp.half_width,
        "\n     UNPAIRED variance", du.paired_variance, " half-width", du.half_width,
        "\n     ratio", du.paired_variance / dp.paired_variance,
        " analytic Var(A)+Var(B)", dp.unpaired_variance,
    )
    var ok_crn = dp.status == STRAT_OK and du.status == STRAT_OK
    ok_crn = ok_crn and dp.paired_variance < du.paired_variance
    ok_crn = ok_crn and du.paired_variance / dp.paired_variance > 5.0
    ok_crn = ok_crn and dp.half_width < du.half_width
    ok_crn = ok_crn and dp.paired_variance_lower and dp.variance_ratio > 5.0
    # Two independent routes to the unpaired variance: Var(A) + Var(B) computed on the paired
    # sample, and Var(A - B') resampled at a different scenario index. Within 10% of each other.
    ok_crn = ok_crn and fabs(dp.unpaired_variance - du.paired_variance) < 0.1 * du.paired_variance
    ok_crn = ok_crn and fabs(dp.paired_variance - 0.04886866050157963) < 1.0e-12
    ok_crn = ok_crn and fabs(du.paired_variance - 0.3110915149160378) < 1.0e-12
    if ok_crn:
        passed += 1
        print(
            "  ✅ the paired comparison carries 6.37x LESS variance than the unpaired one on the",
            "same problem for the same work, and the analytic Var(A)+Var(B) = 0.2925 confirms",
            "the resampled unpaired 0.3111 within 6%",
        )
    else:
        failed += 1
        print("  ❌ pairing bought nothing:", dp.paired_variance, du.paired_variance)

    # The scenarios themselves, bit-for-bit, through the frozen digest.
    var tape_a = _tape(7, 3, 7, horizon, 0, stream)
    var tape_b = _tape(7, 3, 7, horizon, 0, stream)
    var tape_next = _tape(7, 3, 8, horizon, 0, stream)
    var fold_a = strat_crn_fold(tape_a, horizon)
    var fold_b = strat_crn_fold(tape_b, horizon)
    var fold_next = strat_crn_fold(tape_next, horizon)
    var ok_fold = fold_a == fold_b and fold_a != fold_next and fold_a >= 0
    ok_fold = ok_fold and fold_a == 3651692285088114128
    ok_fold = ok_fold and fold_next == 3772497484416744945
    ok_fold = ok_fold and strat_crn_fold(tape_a, horizon + 1) == -1
    if ok_fold:
        passed += 1
        print(
            "  ✅ both strategies' scenario draws digest to the identical", fold_a,
            "while scenario 8 gives", fold_next, "— bit-identical across strategies, different",
            "across scenarios, and an over-count digests to -1 rather than reading past the end",
        )
    else:
        failed += 1
        print("  ❌ the CRN digests do not behave:", fold_a, fold_b, fold_next)

    # ── THE TIE: exchangeable strategies, and the verdict must be a VALUE ─────
    var tie = List[Float64]()
    for r in range(reps):
        tie.append(_payoff(7, 3, r, horizon, 0, 0.5, gamma, stream))
    for r in range(reps):
        tie.append(_payoff(7, 3, r, horizon, 1, 0.5, gamma, stream))
    var dt = tourney_paired_diff_flat(tie, 2, reps, 0, 1, 0.95, 0.05, True, 1.0e-12)
    var ok_tie = dt.status == STRAT_OK and dt.verdict == STRAT_VERDICT_NO_DIFFERENCE
    ok_tie = ok_tie and strat_verdict_is_decided(dt.verdict) and dt.decided
    ok_tie = ok_tie and dt.has_p and dt.p_value > 0.05 and dt.p_value < 1.0
    ok_tie = ok_tie and not dt.deterministic and dt.paired_variance > 0.0
    ok_tie = ok_tie and dt.ci_lower < 0.0 and dt.ci_upper > 0.0
    ok_tie = ok_tie and not dt.ci_excludes_zero
    # Exchangeable, so the two variances are draws of the same quantity: within 10%.
    ok_tie = ok_tie and fabs(dt.variance_a - dt.variance_b) < 0.1 * dt.variance_a
    ok_tie = ok_tie and fabs(dt.p_value - 0.6065255080691427) < 1.0e-12
    if ok_tie:
        passed += 1
        print(
            "  ✅ exchangeable strategies over 200 scenarios: p =", dt.p_value,
            "-> NO SIGNIFICANT DIFFERENCE, decided TRUE, and the interval [",
            dt.ci_lower, ",", dt.ci_upper, "] straddles zero",
        )
    else:
        failed += 1
        print("  ❌ a genuine tie was not reported as one:", dt.p_value, dt.verdict)

    # Identical strategies: every difference exactly zero, p exactly 1.0.
    var same = List[Float64]()
    for r in range(reps):
        same.append(_payoff(7, 3, r, horizon, 0, 0.5, gamma, stream))
    for r in range(reps):
        same.append(_payoff(7, 3, r, horizon, 0, 0.5, gamma, stream))
    var ds = tourney_paired_diff_flat(same, 2, reps, 0, 1, 0.95, 0.05, True, 1.0e-12)
    var ok_same = ds.status == STRAT_OK and ds.deterministic
    ok_same = ok_same and ds.mean_diff == 0.0 and ds.paired_variance == 0.0
    ok_same = ok_same and ds.has_p and ds.p_value == 1.0
    ok_same = ok_same and ds.verdict == STRAT_VERDICT_NO_DIFFERENCE and ds.decided
    ok_same = ok_same and not ds.has_t_stat
    if ok_same:
        passed += 1
        print(
            "  ✅ a strategy against itself: every difference exactly 0.0, so the paired t is",
            "0/0 and the answer is p = 1.0 with NO t statistic — not a NaN, which the dispatch",
            "would refuse, and not a coin flip",
        )
    else:
        failed += 1
        print("  ❌ identical strategies did not tie exactly:", ds.mean_diff, ds.p_value,
              ds.verdict)

    # Three-way: A and B exchangeable, C identical to A. NOBODY wins.
    var tie3 = List[Float64]()
    for r in range(reps):
        tie3.append(_payoff(7, 3, r, horizon, 0, 0.5, gamma, stream))
    for r in range(reps):
        tie3.append(_payoff(7, 3, r, horizon, 1, 0.5, gamma, stream))
    for r in range(reps):
        tie3.append(_payoff(7, 3, r, horizon, 0, 0.5, gamma, stream))
    var t3w = tourney_rank_flat(tie3, 3, reps, 0.95, 0.05, TOURNEY_METHOD_HOLM, True, 1.0e-12)
    var ok_tie3 = t3w.status == STRAT_OK and t3w.ranked
    ok_tie3 = ok_tie3 and t3w.verdict == STRAT_VERDICT_NO_DIFFERENCE and t3w.decided
    ok_tie3 = ok_tie3 and not t3w.has_winner and t3w.winner == -1
    ok_tie3 = ok_tie3 and t3w.n_comparisons == 3 and t3w.n_significant == 0
    ok_tie3 = ok_tie3 and t3w.n_significant_uncorrected == 0
    ok_tie3 = ok_tie3 and t3w.n_deterministic_pairs == 1
    ok_tie3 = ok_tie3 and t3w.rank[0] == 1 and t3w.rank[1] == 1 and t3w.rank[2] == 1
    ok_tie3 = ok_tie3 and t3w.n_at_rank_1 == 3 and t3w.n_distinct_ranks == 1
    ok_tie3 = ok_tie3 and t3w.pair_p[1] == 1.0
    ok_tie3 = ok_tie3 and t3w.pair_adjusted[0] == 1.0 and t3w.pair_adjusted[1] == 1.0
    if ok_tie3:
        passed += 1
        print(
            "  ✅ three strategies, three comparisons, NONE significant: every rank 1, one",
            "distinct rank, no winner, and the verdict is the VALUE 'no significant",
            "difference' rather than a missing winner",
        )
    else:
        failed += 1
        print("  ❌ the three-way tie named a winner:", t3w.verdict, t3w.winner, t3w.rank[0],
              t3w.rank[1], t3w.rank[2])

    # ── and the reverse: the same machinery DOES find a real winner ───────────
    var tw = tourney_rank_flat(paired, 2, reps, 0.95, 0.05, TOURNEY_METHOD_BONFERRONI, True, 1.0e-12)
    var ok_win = tw.status == STRAT_OK and tw.verdict == STRAT_VERDICT_A_BETTER
    ok_win = ok_win and tw.has_winner and tw.winner == 0
    ok_win = ok_win and tw.rank[0] == 1 and tw.rank[1] == 2
    ok_win = ok_win and tw.n_significant == 1 and tw.n_distinct_ranks == 2
    ok_win = ok_win and tw.pair_verdict[0] == STRAT_VERDICT_A_BETTER
    ok_win = ok_win and tw.pair_p[0] < 1.0e-100
    if ok_win:
        passed += 1
        print(
            "  ✅ a check that can FAIL both ways: the threshold-0.40 policy beats 0.60 at",
            "p =", tw.pair_p[0], "on the same generator that produced the tie",
        )
    else:
        failed += 1
        print("  ❌ a real difference was not detected:", tw.verdict, tw.pair_p[0])

    # ── the bootstrap: a second, distribution-free route to the same verdict ──
    var bs = tourney_paired_bootstrap_flat(paired, 2, reps, 0, 1, 0.05, 400, 11)
    var bs_again = tourney_paired_bootstrap_flat(paired, 2, reps, 0, 1, 0.05, 400, 11)
    var bs_seed = tourney_paired_bootstrap_flat(paired, 2, reps, 0, 1, 0.05, 400, 12)
    var bs_tie = tourney_paired_bootstrap_flat(tie, 2, reps, 0, 1, 0.05, 400, 11)
    var ok_boot = bs.status == STRAT_OK and bs.present
    ok_boot = ok_boot and bs.point == dp.mean_diff and bs.point_inside
    ok_boot = ok_boot and bs.excludes_zero and bs.n_draws == 400 * reps
    ok_boot = ok_boot and bs.rng_version == "philox4x64-10/v1"
    ok_boot = ok_boot and bs_again.lo == bs.lo and bs_again.hi == bs.hi
    ok_boot = ok_boot and (bs_seed.lo != bs.lo or bs_seed.hi != bs.hi)
    ok_boot = ok_boot and bs_tie.present and not bs_tie.excludes_zero
    ok_boot = ok_boot and bs_tie.lo < 0.0 and bs_tie.hi > 0.0
    ok_boot = ok_boot and fabs(bs.lo - 0.997177725800697) < 1.0e-12
    ok_boot = ok_boot and fabs(bs.hi - 1.060419795376096) < 1.0e-12
    if ok_boot:
        passed += 1
        print(
            "  ✅ the paired bootstrap agrees with the t interval on BOTH cases — [",
            bs.lo, ",", bs.hi, "] excludes zero for the winner and [", bs_tie.lo, ",",
            bs_tie.hi, "] straddles it for the tie — and is bit-reproducible from its seed",
        )
    else:
        failed += 1
        print("  ❌ the bootstrap disagrees or is not reproducible:", bs.lo, bs.hi,
              bs_again.lo, bs_tie.excludes_zero)

    # ── refusals: every one typed, none of them an abort ──────────────────────
    var empty = List[Float64]()
    var nan_m = _hand_matrix()
    nan_m[4] = 0.0 / 0.0
    var one_row = List[Float64]()
    for i in range(5):
        one_row.append(Float64(i))
    var n_refusals = 0
    var ok_ref = True
    # shape, by division, including the wrapping product 3 * 6148914691236517206 == 2
    ok_ref = ok_ref and tourney_outcome_status(empty, 3, 5) == STRAT_ERR_SHAPE
    ok_ref = ok_ref and tourney_outcome_status(m, 3, 9) == STRAT_ERR_SHAPE
    ok_ref = ok_ref and tourney_outcome_status(m, 4, 4) == STRAT_ERR_SHAPE
    ok_ref = ok_ref and tourney_outcome_status(m, 3, 6148914691236517206) \
        == STRAT_ERR_DIMENSION_TOO_LARGE
    ok_ref = ok_ref and tourney_outcome_status(m, 15, 1) == STRAT_ERR_TOO_FEW_REPLICATIONS
    ok_ref = ok_ref and tourney_outcome_status(nan_m, 3, 5) == STRAT_ERR_NON_FINITE
    n_refusals += 6
    # the rankers refuse the same things, and their own arguments too
    ok_ref = ok_ref and tourney_rank_flat(
        nan_m, 3, 5, 0.95, 0.05, 0, True, 1.0e-12
    ).status == STRAT_ERR_NON_FINITE
    ok_ref = ok_ref and tourney_rank_flat(
        one_row, 1, 5, 0.95, 0.05, 0, True, 1.0e-12
    ).status == STRAT_ERR_TOO_FEW_STRATEGIES
    ok_ref = ok_ref and tourney_rank_flat(
        m, 15, 1, 0.95, 0.05, 0, True, 1.0e-12
    ).status == STRAT_ERR_TOO_FEW_REPLICATIONS
    ok_ref = ok_ref and tourney_rank_flat(
        m, 3, 5, 0.95, 0.05, 9, True, 1.0e-12
    ).status == STRAT_ERR_UNKNOWN_METHOD
    ok_ref = ok_ref and tourney_rank_flat(
        m, 3, 5, 1.0, 0.05, 0, True, 1.0e-12
    ).status == STRAT_ERR_LEVEL_RANGE
    ok_ref = ok_ref and tourney_rank_flat(
        m, 3, 5, 0.95, 0.0, 0, True, 1.0e-12
    ).status == STRAT_ERR_LEVEL_RANGE
    ok_ref = ok_ref and tourney_rank_flat(
        m, 3, 5, 0.95, 0.05, 0, True, -1.0
    ).status == STRAT_ERR_TOLERANCE
    ok_ref = ok_ref and tourney_rank_flat(
        m, 3, 5, 0.95, 0.05, 0, True, 0.0 / 0.0
    ).status == STRAT_ERR_TOLERANCE
    n_refusals += 8
    # a pair index that names a strategy the payload does not have
    ok_ref = ok_ref and tourney_paired_diff_flat(
        m, 3, 5, 0, 3, 0.95, 0.05, True, 1.0e-12
    ).status == STRAT_ERR_COUNT
    ok_ref = ok_ref and tourney_paired_diff_flat(
        m, 3, 5, -1, 2, 0.95, 0.05, True, 1.0e-12
    ).status == STRAT_ERR_COUNT
    ok_ref = ok_ref and tourney_paired_diff_flat(
        m, 3, 5, 1, 1, 0.95, 0.05, True, 1.0e-12
    ).status == STRAT_ERR_DEGENERATE
    n_refusals += 3
    # the bootstrap's own arguments
    ok_ref = ok_ref and tourney_paired_bootstrap_flat(
        m, 3, 5, 0, 1, 0.05, 0, 1
    ).status == STRAT_ERR_EMPTY
    ok_ref = ok_ref and tourney_paired_bootstrap_flat(
        m, 3, 5, 0, 1, 0.05, 10, -1
    ).status == STRAT_ERR_SEED_RANGE
    ok_ref = ok_ref and tourney_paired_bootstrap_flat(
        m, 3, 5, 0, 1, 0.05, 1 << 25, 1
    ).status == STRAT_ERR_DIMENSION_TOO_LARGE
    ok_ref = ok_ref and tourney_paired_bootstrap_flat(
        m, 3, 5, 0, 1, 1.0, 10, 1
    ).status == STRAT_ERR_LEVEL_RANGE
    n_refusals += 4
    # every refusal leaves nothing behind that could be read as a measurement
    var refused = tourney_rank_flat(m, 3, 5, 0.95, 0.05, 9, True, 1.0e-12)
    ok_ref = ok_ref and not refused.ranked and not refused.has_winner
    ok_ref = ok_ref and refused.winner == -1 and len(refused.mean) == 0
    ok_ref = ok_ref and len(refused.pair_p) == 0 and refused.n_comparisons == 0
    ok_ref = ok_ref and refused.work_charge == -1
    ok_ref = ok_ref and refused.verdict == STRAT_VERDICT_UNDECIDED
    ok_ref = ok_ref and not strat_verdict_is_decided(refused.verdict)
    if ok_ref:
        passed += 1
        print(
            "  ✅", n_refusals, "typed refusals, none of them an abort, and a refusal leaves",
            "EMPTY lists rather than zero-filled ones — an empty list is the absence of a",
            "measurement, a zero-filled one is a measurement",
        )
    else:
        failed += 1
        print("  ❌ a refusal is mistyped or leaked a result")

    # ── the work budget: a request inside every ceiling, refused on WORK ──────
    var wide = List[Float64]()
    for i in range(1024 * 2):
        wide.append(Float64(i % 7) * 0.5)
    var ok_work = tourney_outcome_status(wide, 1024, 2) == STRAT_OK
    ok_work = ok_work and tourney_rank_flat(
        wide, 1024, 2, 0.95, 0.05, 0, True, 1.0e-12
    ).status == STRAT_ERR_WORK_BUDGET
    ok_work = ok_work and tourney_work_charge(1024, 2) == -1
    ok_work = ok_work and tourney_work_charge(1024, 4096) == -1
    ok_work = ok_work and tourney_work_charge(3, 5) > 0
    ok_work = ok_work and t.work_charge == tourney_work_charge(3, 5)
    # monotone in both dimensions wherever it is defined
    ok_work = ok_work and tourney_work_charge(4, 5) > tourney_work_charge(3, 5)
    ok_work = ok_work and tourney_work_charge(3, 6) > tourney_work_charge(3, 5)
    ok_work = ok_work and tourney_work_charge(1, 5) == -1
    ok_work = ok_work and tourney_work_charge(3, 1) == -1
    if ok_work:
        passed += 1
        print(
            "  ✅ 1024 strategies at 2 replications is a VALID 2048-cell block inside every",
            "allocation ceiling, and it is refused on WORK — the fixed interval cost alone is",
            "1.07e9 units against a 5.37e8 budget",
        )
    else:
        failed += 1
        print("  ❌ the work budget does not bound a valid shape:", tourney_work_charge(1024, 2))

    # ── the flat addressing helpers ───────────────────────────────────────────
    var ok_addr = tourney_pair_count(2) == 1 and tourney_pair_count(3) == 3
    ok_addr = ok_addr and tourney_pair_count(20) == 190
    ok_addr = ok_addr and tourney_pair_count(1024) == 523776
    ok_addr = ok_addr and tourney_pair_count(1) == -1 and tourney_pair_count(0) == -1
    ok_addr = ok_addr and tourney_pair_count(-5) == -1
    ok_addr = ok_addr and tourney_pair_count(1025) == -1
    ok_addr = ok_addr and tourney_outcome_cell(2, 3, 5) == 13
    ok_addr = ok_addr and tourney_outcome_cell(0, 0, 5) == 0
    ok_addr = ok_addr and tourney_outcome_cell(-1, 0, 5) == -1
    ok_addr = ok_addr and tourney_outcome_cell(0, 5, 5) == -1
    ok_addr = ok_addr and tourney_outcome_cell(0, -1, 5) == -1
    ok_addr = ok_addr and tourney_outcome_cell(3, 6148914691236517206, 5) == -1
    ok_addr = ok_addr and tourney_outcome_cell(6148914691236517206, 0, 3) == -1
    ok_addr = ok_addr and tourney_method_name(3) == "unknown_method"
    if ok_addr:
        passed += 1
        print(
            "  ✅ 20 strategies is 190 comparisons and 1024 is 523776 (inside the 2^20 the",
            "multiplicity correction accepts); every unaddressable cell answers -1, including",
            "the wrapping product, instead of a plausible offset",
        )
    else:
        failed += 1
        print("  ❌ the addressing helpers are wrong:", tourney_pair_count(20),
              tourney_outcome_cell(2, 3, 5))

    print("  [strategy.tournament] Passed:", passed, "Failed:", failed)
