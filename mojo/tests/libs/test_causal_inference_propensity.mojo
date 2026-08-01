"""test_causal_inference_propensity.mojo — known-value tests for propensity scores, IPW and matching.

Hand-written. The assertions target the three defects this module exists to remove, and each one
is pinned by a value computed by hand or by an independent identity rather than by observation:

1. THE CLAMP IS GONE. `causal.propensity_score` clamps to [0.01, 0.99] and `causal.ipw_estimate`
   clamps again inside the weighting loop, so a unit the model says could not have been treated
   silently acquires a weight of 100. Here a propensity of exactly 0.0 for a treated unit is
   `CI_ERR_DEGENERATE_PROPENSITY` with NO estimate, and the same data with `trim_eps` set is an
   estimate with `n_trimmed = 1`. Both are asserted.

2. HAJEK EQUALS THE NAIVE DIFFERENCE UNDER A CONSTANT PROPENSITY — for ANY constant, and with
   UNBALANCED arms. That is an exact algebraic identity (the weights cancel arm by arm) and it is
   the sharpest available check on the weighting arithmetic. Horvitz-Thompson does NOT equal it
   there, and that asymmetry is asserted too: with `e = 0.3`, three treated and two control,
   Hajek is 7.0 (= 12 - 5, the arm means) while HT is 21.14. A single reported estimate could
   not show that.

3. THE FIT IS A REAL FIT. `causal.propensity_score` never reads its `treatment` argument at all.
   Here the fitted scores satisfy the logistic MLE's own score equation for the unpenalised
   intercept, `sum_i e_i == sum_i T_i`, which is an identity the fit must satisfy and which no
   monotone rescaling of a covariate would. Measured residual: 4.4e-16 on the case below. And
   separable data with `l2 = 0` comes back `CI_ERR_NOT_CONVERGED` with the scores ABSENT, because
   perfect separability IS the no-overlap case.

The matching assertions include one hand-traced case where greedy is STRICTLY WORSE than optimal:
treated scores 0.47 and 0.50, controls 0.49 and 0.10. Greedy takes 0.47<->0.49 (0.02) and is left
with 0.50<->0.10 (0.40) for a total of 0.42; the optimum is 0.47<->0.10 (0.37) plus 0.50<->0.49
(0.01) for 0.38. Both numbers are asserted, so the frozen Hungarian is doing real work and not
reproducing the greedy answer.
"""
from std.math import abs as fabs

from causal_inference.base import (
    CI_ABSENT,
    CI_ERR_DEGENERATE_PROPENSITY,
    CI_ERR_INSUFFICIENT_DATA,
    CI_ERR_INVALID_PARAMETER,
    CI_ERR_LENGTH_MISMATCH,
    CI_ERR_NON_FINITE,
    CI_ERR_NOT_CONVERGED,
    CI_ERR_NO_MATCHES,
    CI_ERR_SHAPE,
    CI_ERR_TREATMENT_NOT_BINARY,
    CI_ERR_WORK_BUDGET,
    CI_LOGISTIC_BACKTRACK_STEPS,
    CI_OK,
    MAX_CI_FIT_WORK,
    MAX_CI_ITERATIONS,
    ci_product3_fits,
    ci_tolerance,
)
from causal_inference.propensity import (
    ipw_ate,
    match_nearest,
    match_optimal,
    overlap_report,
    propensity_fit,
)


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _same_ints(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _close(a: Float64, b: Float64) -> Bool:
    """Judged against the magnitude of THE TWO TERMS BEING COMPARED and nothing else."""
    return fabs(a - b) <= ci_tolerance(fabs(a) + fabs(b), 0.0)


fn _lf5() -> List[Float64]:
    return _floats(0.5, 0.6, 0.7, 0.4, 0.3)


fn _li5() -> List[Int]:
    return _ints(1, 2, 3, 4, 5)


fn main() raises:
    var passed = 0
    var failed = 0

    # ── the constant-propensity identity, with BALANCED arms ─────────────────
    # Y = (10, 12 | 4, 6), e = 0.5 everywhere. Arm means 11 and 5, so the naive difference is 6.
    # HT = (1/4)(10/.5 + 12/.5 - 4/.5 - 6/.5) = (20+24-8-12)/4 = 6. Hajek = 11 - 5 = 6.
    var y_bal = _floats(10.0, 12.0, 4.0, 6.0)
    var t_bal = _ints(1, 1, 0, 0)
    var e_half = _floats(0.5, 0.5, 0.5, 0.5)
    var bal = ipw_ate(y_bal, t_bal, e_half, 0.0, 100.0)
    if (
        bal.status == CI_OK
        and bal.has_estimate
        and bal.ate_ht == 6.0
        and bal.ate_hajek == 6.0
        and bal.n_used == 4
        and bal.n_trimmed == 0
        and bal.n_extreme == 0
        and bal.max_weight == 2.0
        and bal.ess_treated == 2.0
        and bal.ess_control == 2.0
        and bal.sum_weight_treated == 4.0
        and bal.sum_weight_control == 4.0
    ):
        passed += 1
        print("  ✅ e=0.5 balanced: HT == Hajek == the naive difference, exactly 6.0; ESS == 2")
    else:
        failed += 1
        print("  ❌ balanced constant-propensity case wrong:", bal.ate_ht, bal.ate_hajek)

    # ── the same identity where the two estimators SEPARATE ──────────────────
    # e = 0.3 for all five units, three treated (10, 12, 14) and two control (4, 6). Arm means
    # are 12 and 5, so Hajek must be exactly 7. HT is (1/5)(36/.3 - 10/.7) = 21.142857..., which
    # is not 7 — reporting one number could not show that the weights are doing something odd.
    var y_un = _floats(10.0, 12.0, 14.0, 4.0, 6.0)
    var t_un = _ints(1, 1, 1, 0, 0)
    var e_three = _floats(0.3, 0.3, 0.3, 0.3, 0.3)
    var un = ipw_ate(y_un, t_un, e_three, 0.0, 100.0)
    var ht_expected = (36.0 / 0.3 - 10.0 / 0.7) / 5.0
    if (
        un.status == CI_OK
        and _close(un.ate_hajek, 7.0)
        and _close(un.ate_ht, ht_expected)
        and not _close(un.ate_ht, 7.0)
        and un.ess_treated == 3.0
        and un.ess_control == 2.0
    ):
        passed += 1
        print("  ✅ e=0.3 unbalanced: Hajek is exactly the arm difference 7.0, HT is not")
    else:
        failed += 1
        print("  ❌ unbalanced case wrong:", un.ate_hajek, un.ate_ht, ht_expected)

    # ── extreme weights are REPORTED, and the ESS collapses ──────────────────
    # One treated unit at e = 0.0025 carries a weight of 400. Kish ESS for the treated arm is
    # (400 + 2)^2 / (400^2 + 4) = 161604 / 160004 = 1.00999..., i.e. two treated units worth
    # barely one. That is the number a caller needs and the frozen kernel cannot produce.
    var y_x = _floats(10.0, 12.0, 4.0, 6.0)
    var t_x = _ints(1, 1, 0, 0)
    var e_x = _floats(0.0025, 0.5, 0.5, 0.5)
    var xtreme = ipw_ate(y_x, t_x, e_x, 0.0, 100.0)
    var ess_expected = (400.0 + 2.0) * (400.0 + 2.0) / (400.0 * 400.0 + 4.0)
    if (
        xtreme.status == CI_OK
        and xtreme.has_estimate
        and xtreme.max_weight == 400.0
        and xtreme.n_extreme == 1
        and _close(xtreme.ess_treated, ess_expected)
        and xtreme.ess_control == 2.0
        and xtreme.n_trimmed == 0
    ):
        passed += 1
        print("  ✅ weight 400 reported, ESS collapses to 1.01 of 2 treated units")
    else:
        failed += 1
        print("  ❌ extreme-weight reporting wrong:", xtreme.max_weight, xtreme.ess_treated)

    # ── a propensity of exactly 0 for a treated unit is a REFUSAL, not a clamp ─
    var e_zero = _floats(0.0, 0.5, 0.5, 0.5)
    var refused = ipw_ate(y_x, t_x, e_zero, 0.0, 100.0)
    var e_one = _floats(0.5, 0.5, 1.0, 0.5)
    var refused_c = ipw_ate(y_x, t_x, e_one, 0.0, 100.0)
    if (
        refused.status == CI_ERR_DEGENERATE_PROPENSITY
        and not refused.has_estimate
        and refused.ate_ht == 0.0
        and refused.ate_hajek == 0.0
        and refused.max_weight == CI_ABSENT
        and refused.ess_treated == CI_ABSENT
        and refused_c.status == CI_ERR_DEGENERATE_PROPENSITY
    ):
        passed += 1
        print("  ✅ e=0 (treated) and e=1 (control) refused with NO numbers, never clamped")
    else:
        failed += 1
        print("  ❌ a degenerate propensity produced an estimate:", refused.status)

    # ── trimming is the CALLER's decision, and its size is always reported ────
    var trimmed = ipw_ate(y_x, t_x, e_zero, 0.01, 100.0)
    if (
        trimmed.status == CI_OK
        and trimmed.has_estimate
        and trimmed.n_trimmed == 1
        and trimmed.n_used == 3
        and trimmed.n_used_treated == 1
        and trimmed.n_used_control == 2
    ):
        passed += 1
        print("  ✅ trim_eps=0.01 drops the impossible unit and reports n_trimmed=1")
    else:
        failed += 1
        print("  ❌ trimming wrong:", trimmed.status, trimmed.n_trimmed)

    # Trimming an arm out of existence has no ATE.
    var all_trimmed = ipw_ate(y_x, t_x, _floats(0.001, 0.002, 0.5, 0.5), 0.01, 100.0)
    if all_trimmed.status == 348 and not all_trimmed.has_estimate:
        passed += 1
        print("  ✅ trimming away every treated unit is CI_ERR_NO_TREATED, not an estimate")
    else:
        failed += 1
        print("  ❌ empty arm after trimming:", all_trimmed.status)

    # ── overlap is measured, and its absence is reported ─────────────────────
    # Treated scores (0.8, 0.9), control (0.1, 0.2): the ranges do not intersect at all.
    var no_sup = overlap_report(_floats(0.8, 0.9, 0.1, 0.2), _ints(1, 1, 0, 0), 0.05)
    if (
        no_sup.status == CI_OK
        and no_sup.has_report
        and not no_sup.has_support
        and no_sup.support_lo == 0.8
        and no_sup.support_hi == 0.2
        and no_sup.n_treated_outside == 2
        and no_sup.n_control_outside == 2
        and no_sup.overlap_fraction == 0.0
        and _close(no_sup.mean_treated, 0.85)
        and _close(no_sup.mean_control, 0.15)
        and no_sup.has_standardized_diff
    ):
        passed += 1
        print("  ✅ disjoint score ranges: has_support=False, overlap_fraction exactly 0.0")
    else:
        failed += 1
        print("  ❌ no-support case wrong:", no_sup.has_support, no_sup.overlap_fraction)

    # Full overlap: identical score sets in both arms.
    var full_sup = overlap_report(_floats(0.4, 0.6, 0.4, 0.6), _ints(1, 1, 0, 0), 0.05)
    if (
        full_sup.has_support
        and full_sup.support_lo == 0.4
        and full_sup.support_hi == 0.6
        and full_sup.overlap_fraction == 1.0
        and full_sup.n_treated_outside == 0
        and full_sup.standardized_diff == 0.0
        and full_sup.has_standardized_diff
        and full_sup.n_degenerate == 0
    ):
        passed += 1
        print("  ✅ identical arms: full support and a standardized difference of exactly 0")
    else:
        failed += 1
        print("  ❌ full-overlap case wrong:", full_sup.overlap_fraction)

    # Zero variance in both arms has no standardized difference — absent, not division by zero.
    var flat_sup = overlap_report(_floats(0.5, 0.5, 0.5, 0.5), _ints(1, 1, 0, 0), 0.05)
    if flat_sup.status == CI_OK and not flat_sup.has_standardized_diff:
        passed += 1
        print("  ✅ zero spread in both arms: the standardized difference is ABSENT")
    else:
        failed += 1
        print("  ❌ standardized difference computed with a zero denominator")

    # Degenerate scores are counted and never rewritten.
    var degen = overlap_report(_floats(0.0, 0.5, 1.0, 0.5), _ints(1, 1, 0, 0), 0.05)
    if degen.status == CI_OK and degen.n_degenerate == 2 and degen.n_below_eps == 1:
        passed += 1
        print("  ✅ scores at exactly 0 and 1 are COUNTED, not clamped away")
    else:
        failed += 1
        print("  ❌ degenerate-score counting wrong:", degen.n_degenerate)

    # ── a variance that does not exist is not a denominator ──────────────────
    # ONE treated unit against four spread controls. The frozen `math_ext.variance` returns 0.0
    # for n <= 1, so `pooled = sqrt(0.5 * (0 + vc)) = sqrt(vc / 2)` is strictly positive and the
    # old `pooled > 0.0` guard passed on the strength of an invented number — reporting a
    # standardized difference a factor of sqrt(2) too large (measured: 0.1195 where the one arm
    # that HAS spread gives 0.0845, which crosses the conventional 0.1 balance threshold).
    # The means are still reported: a mean of one observation exists.
    var one_t = overlap_report(
        _floats(0.5, 0.30, 0.35, 0.40, 0.45), _ints(1, 0, 0, 0, 0), 0.01
    )
    var one_c = overlap_report(
        _floats(0.30, 0.35, 0.40, 0.45, 0.5), _ints(1, 1, 1, 1, 0), 0.01
    )
    var one_one = overlap_report(_floats(0.4, 0.6), _ints(1, 0), 0.01)
    if (
        one_t.status == CI_OK
        and one_t.has_report
        and not one_t.has_standardized_diff
        and one_t.standardized_diff == 0.0
        and one_t.n_treated == 1
        and one_t.n_control == 4
        and _close(one_t.mean_treated, 0.5)
        and not one_c.has_standardized_diff
        and one_c.standardized_diff == 0.0
        and one_c.n_control == 1
        and not one_one.has_standardized_diff
    ):
        passed += 1
        print("  ✅ a singleton arm has no variance, so the standardized difference is ABSENT")
    else:
        failed += 1
        print(
            "  ❌ a fabricated n<=1 variance became a denominator:",
            one_t.has_standardized_diff,
            one_t.standardized_diff,
            one_c.has_standardized_diff,
        )

    # The gate is on the variance EXISTING, not on it being non-zero. Treated (0.4, 0.6) against
    # control (0.3, 0.5): both variances are 0.02, pooled = sqrt(0.02), difference of means 0.1,
    # so the statistic is exactly 0.1 / sqrt(0.02) = 1/sqrt(2). And a GENUINE zero variance in
    # one arm — two treated units both scoring 0.5, control (0.3, 0.5) with variance 0.02 — is
    # the textbook pooled SD sqrt(0.01) = 0.1 over a difference of means of 0.1, i.e. exactly 1.
    var both_var = overlap_report(_floats(0.4, 0.6, 0.3, 0.5), _ints(1, 1, 0, 0), 0.01)
    var genuine_zero = overlap_report(_floats(0.5, 0.5, 0.3, 0.5), _ints(1, 1, 0, 0), 0.01)
    if (
        both_var.has_standardized_diff
        and _close(both_var.standardized_diff, 0.7071067811865476)
        and genuine_zero.has_standardized_diff
        and _close(genuine_zero.standardized_diff, 1.0)
    ):
        passed += 1
        print("  ✅ two real variances give the pooled statistic, a genuine zero included")
    else:
        failed += 1
        print(
            "  ❌ pooled standardized difference wrong:",
            both_var.standardized_diff,
            genuine_zero.standardized_diff,
        )

    # ── greedy matching: pairs, gaps and the unmatched count, by hand ─────────
    # Treated (unit 0: 0.6, unit 1: 0.4), control (unit 2: 0.55, unit 3: 0.2), caliper 0.1.
    # Unit 0 takes unit 2 (gap 0.05). Unit 1's only remaining option is unit 3 at gap 0.2 > 0.1,
    # so it goes unmatched. ATT over the single pair is 10 - 4 = 6.
    var y_m = _floats(10.0, 12.0, 4.0, 6.0)
    var t_m = _ints(1, 1, 0, 0)
    var s_m = _floats(0.6, 0.4, 0.55, 0.2)
    var greedy = match_nearest(y_m, t_m, s_m, 0.1, False)
    if (
        greedy.status == CI_OK
        and greedy.has_estimate
        and greedy.n_matched == 1
        and greedy.n_unmatched == 1
        and not greedy.is_full_sample
        and greedy.matched_fraction == 0.5
        and greedy.att == 6.0
        and _close(greedy.total_gap, 0.05)
        and _same_ints(greedy.matched_treated, _ints(0))
        and _same_ints(greedy.matched_control, _ints(2))
        and greedy.n_controls_used == 1
    ):
        passed += 1
        print("  ✅ caliper 0.1: one pair (0,2), one unmatched, matched_fraction 0.5, ATT 6.0")
    else:
        failed += 1
        print("  ❌ greedy matching wrong:", greedy.n_matched, greedy.att, greedy.total_gap)

    # A caliper nothing fits is CI_ERR_NO_MATCHES with no estimate at all.
    var none_fit = match_nearest(y_m, t_m, s_m, 0.001, False)
    if (
        none_fit.status == CI_ERR_NO_MATCHES
        and not none_fit.has_estimate
        and none_fit.n_matched == 0
        and len(none_fit.matched_treated) == 0
        and none_fit.total_gap == CI_ABSENT
        and none_fit.matched_fraction == CI_ABSENT
    ):
        passed += 1
        print("  ✅ a caliper nothing fits: refused with empty pairs and absent diagnostics")
    else:
        failed += 1
        print("  ❌ empty match wrong:", none_fit.status, none_fit.n_matched)

    # With replacement the second treated unit may reuse the same control.
    var with_rep = match_nearest(y_m, t_m, s_m, 0.2, True)
    if (
        with_rep.status == CI_OK
        and with_rep.n_matched == 2
        and with_rep.is_full_sample
        and with_rep.n_controls_used == 1
        and _same_ints(with_rep.matched_control, _ints(2, 2))
        and with_rep.with_replacement
    ):
        passed += 1
        print("  ✅ with replacement: both treated take control 2; n_controls_used reports 1")
    else:
        failed += 1
        print("  ❌ with-replacement case wrong:", with_rep.n_matched, with_rep.n_controls_used)

    # ── optimal matching STRICTLY beats greedy, both totals by hand ───────────
    # Treated 0.47 (unit 0) and 0.50 (unit 1); controls 0.49 (unit 2) and 0.10 (unit 3).
    var s_gap = _floats(0.47, 0.50, 0.49, 0.10)
    var y_gap = _floats(10.0, 20.0, 1.0, 2.0)
    var g2 = match_nearest(y_gap, t_m, s_gap, 1.0, False)
    var o2 = match_optimal(y_gap, t_m, s_gap, 1.0)
    if (
        g2.status == CI_OK
        and o2.status == CI_OK
        and _close(g2.total_gap, 0.42)
        and _close(o2.total_gap, 0.38)
        and o2.total_gap < g2.total_gap
        and o2.n_matched == 2
        and o2.is_full_sample
    ):
        passed += 1
        print("  ✅ optimal total gap 0.38 < greedy 0.42 — the Hungarian is doing real work")
    else:
        failed += 1
        print("  ❌ optimal-vs-greedy wrong:", g2.total_gap, o2.total_gap)

    # The optimal matcher can never be worse, so this inequality is a standing invariant. It is
    # asserted here on the earlier full-matching case too, where the two happen to agree.
    var g3 = match_nearest(y_m, t_m, s_m, 1.0, False)
    var o3 = match_optimal(y_m, t_m, s_m, 1.0)
    if (
        g3.status == CI_OK
        and o3.status == CI_OK
        and o3.total_gap <= g3.total_gap + ci_tolerance(g3.total_gap, 0.0)
        and o3.n_matched == g3.n_matched
    ):
        passed += 1
        print("  ✅ optimal <= greedy holds on the case where both match everybody")
    else:
        failed += 1
        print("  ❌ the optimal-<=-greedy invariant failed:", o3.total_gap, g3.total_gap)

    # Fewer controls than treated is a refusal, NOT a silent transpose.
    var thin = match_optimal(
        _floats(1.0, 2.0, 3.0), _ints(1, 1, 0), _floats(0.5, 0.5, 0.5), 1.0
    )
    if thin.status == CI_ERR_INSUFFICIENT_DATA and not thin.has_estimate:
        passed += 1
        print("  ✅ fewer controls than treated: refused rather than transposed")
    else:
        failed += 1
        print("  ❌ rectangular refusal wrong:", thin.status)

    # A caliper that makes a complete matching impossible is all-or-nothing here.
    var no_perfect = match_optimal(y_gap, t_m, s_gap, 0.02)
    if no_perfect.status == CI_ERR_NO_MATCHES and not no_perfect.has_estimate:
        passed += 1
        print("  ✅ no complete matching inside the caliper: refused, not partially answered")
    else:
        failed += 1
        print("  ❌ optimal caliper refusal wrong:", no_perfect.status)

    # ── the fit is a REAL fit: the intercept score equation holds ─────────────
    # sum_i e_i == sum_i T_i is an identity of the logistic MLE with an unpenalised intercept.
    # No monotone rescaling of a covariate satisfies it, which is what `causal.propensity_score`
    # returns.
    var x_ns = _floats(0.0, 1.0, 2.0, 3.0, 1.5, 1.6)
    var t_ns = _ints(0, 1, 0, 1, 1, 0)
    var fit = propensity_fit(x_ns, 6, 1, t_ns, 0.0, 500, 1.0e-13)
    var score_sum = 0.0
    if fit.has_scores:
        for i in range(6):
            score_sum += fit.scores[i]
    if (
        fit.status == CI_OK
        and fit.has_scores
        and fit.converged
        and len(fit.scores) == 6
        and fabs(score_sum - 3.0) <= 1.0e-9
        and fit.n_treated == 3
        and fit.n_control == 3
        and fit.n_degenerate == 0
        and len(fit.weights) == 1
        and len(fit.std_errors) == 2
    ):
        passed += 1
        print("  ✅ fitted scores satisfy sum(e) == sum(T) — the MLE's own score equation")
    else:
        failed += 1
        print("  ❌ the fit is not an MLE:", fit.status, score_sum)

    # The arm extremes come back from the same fit, and bracket the scores.
    var brackets_ok = fit.has_scores
    if brackets_ok:
        for i in range(6):
            var p = fit.scores[i]
            if t_ns[i] == 1:
                if p < fit.min_score_treated or p > fit.max_score_treated:
                    brackets_ok = False
            else:
                if p < fit.min_score_control or p > fit.max_score_control:
                    brackets_ok = False
    if brackets_ok:
        passed += 1
        print("  ✅ the reported per-arm score extremes really bracket that arm's scores")
    else:
        failed += 1
        print("  ❌ the reported arm extremes are wrong")

    # ── separable data with l2 = 0 is NO OVERLAP, reported as non-convergence ─
    var x_sep = _floats(0.0, 1.0, 2.0, 3.0)
    var t_sep = _ints(0, 0, 1, 1)
    var sep = propensity_fit(x_sep, 4, 1, t_sep, 0.0, 60, 1.0e-10)
    if (
        sep.status == CI_ERR_NOT_CONVERGED
        and not sep.has_scores
        and not sep.converged
        and sep.n_iter == 60
        and len(sep.scores) == 0
    ):
        passed += 1
        print("  ✅ separable + l2=0: NOT_CONVERGED with the scores ABSENT, n_iter reported")
    else:
        failed += 1
        print("  ❌ separable case wrong:", sep.status, sep.converged, sep.n_iter)

    # The same data with regularisation converges, which is the caller's remedy.
    var sep_reg = propensity_fit(x_sep, 4, 1, t_sep, 1.0, 200, 1.0e-12)
    if sep_reg.status == CI_OK and sep_reg.has_scores and sep_reg.converged:
        passed += 1
        print("  ✅ the same data with l2=1 converges — the refusal was informative, not fatal")
    else:
        failed += 1
        print("  ❌ regularised fit failed:", sep_reg.status)

    # ── the frozen fit's line search is CHARGED, not assumed free ────────────
    # `linear_models.logistic_fit` runs a backtracking line search inside every Newton step
    # (`for _ in range(20)` at linear_models.mojo:336), each trial a full O(n x (p+1)) penalized
    # log-likelihood pass. Charging only `max_iter x n x (p+1)^2` left that loop unpriced:
    # MEASURED at p = 1, the worst case, 9.4-11.1 ns per old-charged unit against 0.19-0.24 ns
    # when the search exits immediately, so the ceiling bought ~10.1-11.9 s where it promises
    # order-of-seconds. `n = 1000, p = 1, max_iter = 100,000` is the witness: the old charge is
    # 4.0e8 and fits under 2^30, the honest charge is 4.4e9 and does not.
    var line_x = List[Float64]()
    var line_t = List[Int]()
    for i in range(1000):
        line_t.append(1 if (i % 2) == 0 else 0)
        line_x.append(Float64((i * 3) % 11) / 11.0)
    var undercharged = propensity_fit(line_x, 1000, 1, line_t, 1.0, 100000, 1.0e-9)
    var ordinary = propensity_fit(line_x, 1000, 1, line_t, 1.0, 200, 1.0e-9)
    var pp1 = 2
    if (
        CI_LOGISTIC_BACKTRACK_STEPS == 20
        # the charge that omitted the line search admitted this request …
        and ci_product3_fits(100000, 1000, pp1 * pp1, MAX_CI_FIT_WORK)
        # … and the charge that includes it does not.
        and not ci_product3_fits(
            100000, 1000, pp1 * pp1 + CI_LOGISTIC_BACKTRACK_STEPS * pp1, MAX_CI_FIT_WORK
        )
        and undercharged.status == CI_ERR_WORK_BUDGET
        # and an ordinary request is untouched: 200 x 1000 x 44 is 1.8% of the ceiling.
        and ordinary.status == CI_OK
        and ordinary.has_scores
    ):
        passed += 1
        print("  ✅ propensity_fit charges the frozen fit's 20-step line search, not just Newton")
    else:
        failed += 1
        print(
            "  ❌ line-search work is uncharged:",
            undercharged.status,
            ordinary.status,
            CI_LOGISTIC_BACKTRACK_STEPS,
        )

    # ── refusals ─────────────────────────────────────────────────────────────
    if (
        propensity_fit(_floats(1.0), 1, 0, _ints(1), 0.0, 10, 1.0e-9).status == CI_ERR_SHAPE
        and propensity_fit(_floats(1.0, 2.0), 2, 1, _ints(1), 0.0, 10, 1.0e-9).status
        == CI_ERR_LENGTH_MISMATCH
        and propensity_fit(_floats(1.0, 2.0), 2, 1, _ints(1, 0), -1.0, 10, 1.0e-9).status
        == CI_ERR_INVALID_PARAMETER
        and propensity_fit(_floats(1.0, 2.0), 2, 1, _ints(1, 0), 0.0, 0, 1.0e-9).status
        == CI_ERR_INVALID_PARAMETER
        # An iteration ceiling as well as a product budget: `max_iter * n * p^2 <= 2^30` admits a
        # billion iterations on a two-unit, one-feature problem, and each one allocates.
        and propensity_fit(
            _floats(1.0, 2.0), 2, 1, _ints(1, 0), 0.0, MAX_CI_ITERATIONS + 1, 1.0e-9
        ).status
        == CI_ERR_INVALID_PARAMETER
        and propensity_fit(_floats(1.0, 2.0), 2, 1, _ints(1, 2), 0.0, 10, 1.0e-9).status
        == CI_ERR_TREATMENT_NOT_BINARY
    ):
        passed += 1
        print("  ✅ propensity_fit refuses bad shape, length, penalty, iteration cap and arms")
    else:
        failed += 1
        print("  ❌ propensity_fit validation incomplete")

    if (
        ipw_ate(List[Float64](), List[Int](), List[Float64](), 0.0, 1.0).status
        == CI_ERR_INSUFFICIENT_DATA
        and ipw_ate(y_bal, _ints(1, 0), e_half, 0.0, 1.0).status == CI_ERR_LENGTH_MISMATCH
        and ipw_ate(y_bal, t_bal, e_half, 0.5, 1.0).status == CI_ERR_INVALID_PARAMETER
        and ipw_ate(y_bal, t_bal, e_half, 0.0, 0.0).status == CI_ERR_INVALID_PARAMETER
        and overlap_report(_lf5(), _li5(), 0.5).status == CI_ERR_INVALID_PARAMETER
        and match_nearest(y_bal, t_bal, e_half, -1.0, False).status == CI_ERR_INVALID_PARAMETER
    ):
        passed += 1
        print("  ✅ length, trim, threshold, eps and caliper ranges all refused")
    else:
        failed += 1
        print("  ❌ parameter validation incomplete")

    # ── the A-Z harness pattern ──────────────────────────────────────────────
    if (
        propensity_fit(_lf5(), 5, 5, _li5(), 0.5, 5, 0.5).status == CI_ERR_SHAPE
        and overlap_report(_lf5(), _li5(), 0.5).status == CI_ERR_INVALID_PARAMETER
        and ipw_ate(_lf5(), _li5(), _lf5(), 0.5, 0.5).status == CI_ERR_INVALID_PARAMETER
        and match_nearest(_lf5(), _li5(), _lf5(), 0.5, True).status
        == CI_ERR_TREATMENT_NOT_BINARY
        and match_optimal(_lf5(), _li5(), _lf5(), 0.5).status == CI_ERR_TREATMENT_NOT_BINARY
    ):
        passed += 1
        print("  ✅ the fixed 5-element / 5-integer harness pattern is refused, not indexed")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern was mishandled")

    print("  [causal_inference.propensity] Passed:", passed, "Failed:", failed)
