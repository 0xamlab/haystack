"""test_causal_inference_estimators.mojo — known-value tests for the adjusted estimators.

Hand-written. The centrepiece is ONE dataset on which the true ATE is exactly 5 and every
adjusted estimator must recover exactly 5 while the unadjusted contrast must not. It is
constructed so that the recovery is EXACT in floating point, not approximate, which is what turns
"the estimator looks right" into "the estimator is right":

    a binary confounder x in {0, 1}
    true propensity e(x) = 0.25 when x = 0, 0.75 when x = 1
    outcome        Y = 2 + 3 x + 5 T          (no noise: the model is exactly linear)

    x = 0:  4 units, exactly 1 treated  (so the realised share IS 0.25)
    x = 1:  4 units, exactly 3 treated  (so the realised share IS 0.75)

    Y:  x=0 treated -> 7,  x=0 control -> 2,  x=1 treated -> 10,  x=1 control -> 5

Worked by hand, and every one of these is asserted:

    naive difference   (7 + 30)/4 - (6 + 5)/4 = 9.25 - 2.75 = 6.5     <- CONFOUNDED, not 5
    frozen causal.ate  the same 6.5, asserted equal to `naive_ate`
    IPW Horvitz-Thomp. (28 + 40 - 8 - 20)/8 = 40/8 = 5                <- exact
    IPW Hajek          68/8 - 28/8 = 8.5 - 3.5 = 5                    <- exact
    stratified         stratum 0: 7 - 2 = 5;  stratum 1: 10 - 5 = 5   <- exact, both strata
    outcome regression mu1 = 3x + 7, mu0 = 3x + 2, mean(mu1 - mu0) = 5 <- exact
    AIPW               corrections vanish on a perfect outcome model   <- exact

DOUBLE ROBUSTNESS, BOTH DIRECTIONS, AS EXACT IDENTITIES
-------------------------------------------------------
The point of AIPW is that it survives ONE of its two models being wrong. Both directions are
algebraic on this dataset and both are asserted:

  * wrong propensity, right outcome model — set every `e_i` to 0.5, which is flatly wrong here,
    and AIPW still returns exactly 5, because a perfect outcome model makes both correction terms
    identically zero whatever the weights are;
  * right propensity, useless outcome model — set `mu0 = mu1 = c` for an arbitrary constant `c`
    (17.0 below), and AIPW still returns exactly 5. Worked out: the correction is
    `(1/8)[(68 - 8c) - (28 - 8c)] = 40/8 = 5`, independent of `c`. The suite asserts it for two
    different constants to show the independence is real and not a coincidence at one value.

The bootstrap is asserted for BIT-IDENTITY across two calls with the same seed, and for movement
across two different seeds. A resampled interval that changes between runs cannot be used in a
decision that has to be explained, which is why the resample draws from `determinism.counter_rng`
through `uniform_int_keyed` rather than from process-global state.
"""
from std.math import abs as fabs, sqrt
from time import perf_counter_ns

from causal import ate as frozen_ate, stratified_ate as frozen_stratified

from causal_inference.base import (
    CI_ABSENT,
    CI_ERR_DEGENERATE_PROPENSITY,
    CI_ERR_INDEX,
    CI_ERR_INSUFFICIENT_DATA,
    CI_ERR_INVALID_PARAMETER,
    CI_ERR_LENGTH_MISMATCH,
    CI_ERR_NOT_CONVERGED,
    CI_ERR_SHAPE,
    CI_ERR_TREATMENT_NOT_BINARY,
    CI_ERR_WORK_BUDGET,
    CI_OK,
    MAX_CI_BOOTSTRAP_WORK,
    MAX_CI_FIT_WORK,
    MAX_CI_ITERATIONS,
    ci_product_fits,
    ci_tolerance,
)
from causal_inference.estimators import (
    aipw_ate,
    aipw_bootstrap_ci,
    naive_ate,
    outcome_regression_ate,
    strata_ate,
)
from causal_inference.propensity import ipw_ate


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


fn _close(a: Float64, b: Float64) -> Bool:
    """Judged against the magnitude of THE TWO TERMS BEING COMPARED, and nothing else."""
    return fabs(a - b) <= ci_tolerance(fabs(a) + fabs(b), 0.0)


# A bootstrap-shaped sample of `n` units, alternating arms, every score strictly interior so no
# replicate is dropped. Used by the scaling assertion, where `n` is held fixed and the replicate
# count is what varies.
#
# THE REPLICATE ATEs MUST GENUINELY DIFFER, and that is a property of this data rather than an
# incidental one. The suite's main dataset pairs `e = 0.5` with a perfect outcome model, so every
# replicate's AIPW estimate is the SAME number — and an insertion sort of an already-sorted array
# is O(B), not O(B^2). Measured with exactly that data, the quadratic sort ran the scaling test at
# 3.94x and the assertion below passed against the defect it exists to catch. The periods here
# (5 / 13 / 3 / 4) are pairwise coprime with each other and with the arm alternation, so a
# resample lands on a different mixture almost every time and the sort sees unsorted input.
fn _boot_y(n: Int) -> List[Float64]:
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(1.0 + Float64(i % 13))
    return out^


fn _boot_t(n: Int) -> List[Int]:
    var out = List[Int](capacity=n)
    for i in range(n):
        out.append(1 if (i % 2) == 0 else 0)
    return out^


fn _boot_e(n: Int) -> List[Float64]:
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(0.35 + 0.3 * Float64(i % 5) / 5.0)
    return out^


fn _boot_m0(n: Int) -> List[Float64]:
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(0.5 + Float64(i % 3))
    return out^


fn _boot_m1(n: Int) -> List[Float64]:
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(1.5 + Float64(i % 4))
    return out^


fn _lf5() -> List[Float64]:
    return _floats(0.5, 0.6, 0.7, 0.4, 0.3)


fn _li5() -> List[Int]:
    return _ints(1, 2, 3, 4, 5)


# ── the known-effect dataset: true ATE is exactly 5 ──────────────────────────
# Unit order: four x=0 units (1 treated), then four x=1 units (3 treated).


fn _x() -> List[Float64]:
    return _floats(0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0)


fn _t() -> List[Int]:
    return _ints(1, 0, 0, 0, 1, 1, 1, 0)


fn _y() -> List[Float64]:
    """Y = 2 + 3x + 5T, exactly."""
    return _floats(7.0, 2.0, 2.0, 2.0, 10.0, 10.0, 10.0, 5.0)


fn _e_true() -> List[Float64]:
    return _floats(0.25, 0.25, 0.25, 0.25, 0.75, 0.75, 0.75, 0.75)


fn _e_wrong() -> List[Float64]:
    return _floats(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)


fn _strata() -> List[Int]:
    return _ints(0, 0, 0, 0, 1, 1, 1, 1)


fn _mu1_perfect() -> List[Float64]:
    """mu1 = 3x + 7: matches Y exactly for every TREATED unit."""
    return _floats(7.0, 7.0, 7.0, 7.0, 10.0, 10.0, 10.0, 10.0)


fn _mu0_perfect() -> List[Float64]:
    """mu0 = 3x + 2: matches Y exactly for every CONTROL unit."""
    return _floats(2.0, 2.0, 2.0, 2.0, 5.0, 5.0, 5.0, 5.0)


fn _const(c: Float64) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(8):
        out.append(c)
    return out^


fn main() raises:
    var passed = 0
    var failed = 0

    # ── the unadjusted contrast is 6.5, and the frozen kernel agrees ──────────
    var naive = naive_ate(_y(), _t())
    var yt = _floats(7.0, 10.0, 10.0, 10.0)
    var yc = _floats(2.0, 2.0, 2.0, 5.0)
    var frozen = frozen_ate(yt, yc)
    if (
        naive.status == CI_OK
        and naive.has_diff
        and naive.diff == 6.5
        and naive.diff == frozen
        and naive.mean_treated == 9.25
        and naive.mean_control == 2.75
        and naive.n_treated == 4
        and naive.n_control == 4
        and naive.has_se
    ):
        passed += 1
        print("  ✅ unadjusted contrast is 6.5 (NOT the true 5) and equals frozen causal.ate")
    else:
        failed += 1
        print("  ❌ naive contrast wrong:", naive.diff, frozen)

    # ── IPW with the TRUE propensities recovers 5 exactly, both forms ─────────
    var ipw = ipw_ate(_y(), _t(), _e_true(), 0.0, 1000.0)
    if (
        ipw.status == CI_OK
        and ipw.has_estimate
        and _close(ipw.ate_ht, 5.0)
        and _close(ipw.ate_hajek, 5.0)
        and _close(ipw.sum_weight_treated, 8.0)
        and _close(ipw.sum_weight_control, 8.0)
        and ipw.n_used == 8
    ):
        passed += 1
        print("  ✅ IPW with the true e: HT and Hajek are both EXACTLY 5.0")
    else:
        failed += 1
        print("  ❌ IPW recovery wrong:", ipw.ate_ht, ipw.ate_hajek)

    # ── stratification recovers 5 exactly, and each stratum is 5 ─────────────
    var strat = strata_ate(_y(), _t(), _strata(), 2)
    if (
        strat.status == CI_OK
        and strat.has_ate
        and strat.ate == 5.0
        and strat.n_usable == 2
        and strat.n_covered == 8
        and strat.covered_fraction == 1.0
        and strat.is_full_sample
        and strat.stratum_has_ate[0]
        and strat.stratum_has_ate[1]
        and strat.stratum_ate[0] == 5.0
        and strat.stratum_ate[1] == 5.0
        and strat.stratum_n[0] == 4
        and strat.stratum_n_treated[0] == 1
        and strat.stratum_n_treated[1] == 3
    ):
        passed += 1
        print("  ✅ stratified: both strata are exactly 5.0, and so is the weighted total")
    else:
        failed += 1
        print("  ❌ stratification wrong:", strat.ate, strat.n_usable)

    # Full coverage means the two conventions agree, and the frozen kernel is the oracle.
    var frozen_strat = frozen_stratified(_y(), _t(), _strata(), 2)
    if (
        strat.ate == frozen_strat
        and strat.ate_uncovered_as_zero == frozen_strat
    ):
        passed += 1
        print("  ✅ at full coverage this matches frozen causal.stratified_ate exactly")
    else:
        failed += 1
        print("  ❌ divergence from the frozen kernel at full coverage:", frozen_strat)

    # ── an unusable stratum is REPORTED, not absorbed into a smaller number ──
    # Add a third stratum holding two treated units and no control. The frozen kernel silently
    # drops it and divides by the whole sample, pulling the answer toward zero; here the weights
    # are renormalised over the covered mass and `covered_fraction` says how much that is.
    var y10 = _floats(7.0, 2.0, 2.0, 2.0, 10.0, 10.0, 10.0, 5.0, 99.0, 98.0)
    var t10 = _ints(1, 0, 0, 0, 1, 1, 1, 0, 1, 1)
    var s10 = _ints(0, 0, 0, 0, 1, 1, 1, 1, 2, 2)
    var partial = strata_ate(y10, t10, s10, 3)
    var frozen_partial = frozen_stratified(y10, t10, s10, 3)
    if (
        partial.status == CI_OK
        and partial.has_ate
        and partial.ate == 5.0
        and not partial.is_full_sample
        and partial.n_usable == 2
        and partial.n_covered == 8
        and partial.covered_fraction == 0.8
        and not partial.stratum_has_ate[2]
        and partial.stratum_ate[2] == 0.0
        and _close(partial.ate_uncovered_as_zero, 4.0)
        and _close(partial.ate_uncovered_as_zero, frozen_partial)
    ):
        passed += 1
        print("  ✅ an armless stratum: ate stays 5.0, the frozen convention gives 4.0, and")
        print("     covered_fraction reports the 0.8 that explains the difference")
    else:
        failed += 1
        print(
            "  ❌ partial coverage wrong:",
            partial.ate,
            partial.ate_uncovered_as_zero,
            frozen_partial,
        )

    # ── outcome regression recovers 5 exactly, with the coefficients by hand ──
    var om = outcome_regression_ate(_x(), 8, 1, _t(), _y(), 0.0, 0.0, 20000, 1.0e-14)
    if (
        om.status == CI_OK
        and om.has_ate
        and _close(om.ate, 5.0)
        and om.converged_treated
        and om.converged_control
        and len(om.mu0) == 8
        and len(om.mu1) == 8
        and _close(om.coef_treated[0], 3.0)
        and _close(om.coef_control[0], 3.0)
        and _close(om.bias_treated, 7.0)
        and _close(om.bias_control, 2.0)
        and om.n_treated == 4
        and om.n_control == 4
    ):
        passed += 1
        print("  ✅ outcome regression: slopes 3 and 3, intercepts 7 and 2, ATE 5.0")
    else:
        failed += 1
        print("  ❌ outcome regression wrong:", om.ate, om.coef_treated[0], om.bias_treated)

    # Its predictions must reproduce the observed outcome for every unit's OWN arm, since the
    # generating model is exactly linear. That is a per-unit check, not an average.
    var preds_ok = om.has_ate
    if preds_ok:
        for i in range(8):
            var own = om.mu1[i] if _t()[i] == 1 else om.mu0[i]
            if not _close(own, _y()[i]):
                preds_ok = False
    if preds_ok:
        passed += 1
        print("  ✅ every unit's own-arm prediction reproduces its observed outcome")
    else:
        failed += 1
        print("  ❌ the fitted predictions do not reproduce the noiseless outcomes")

    # ── AIPW: the decomposition identity is exact on every call ───────────────
    var dr = aipw_ate(
        _y(), _t(), _e_true(), _mu0_perfect(), _mu1_perfect(), 0.0, 1000.0, 1.96
    )
    if (
        dr.status == CI_OK
        and dr.has_ate
        and _close(dr.ate, 5.0)
        and dr.ate_regression == 5.0
        and dr.ate_correction == 0.0
        and dr.decomposition_residual == 0.0
        and dr.n_used == 8
    ):
        passed += 1
        print("  ✅ AIPW with both models right: 5.0, corrections exactly 0, residual exactly 0")
    else:
        failed += 1
        print("  ❌ AIPW baseline wrong:", dr.ate, dr.ate_correction, dr.decomposition_residual)

    # ── double robustness, direction 1: the PROPENSITY is wrong ───────────────
    var dr_bad_e = aipw_ate(
        _y(), _t(), _e_wrong(), _mu0_perfect(), _mu1_perfect(), 0.0, 1000.0, 1.96
    )
    if (
        dr_bad_e.status == CI_OK
        and _close(dr_bad_e.ate, 5.0)
        and dr_bad_e.ate_correction == 0.0
        and dr_bad_e.decomposition_residual == 0.0
    ):
        passed += 1
        print("  ✅ DR direction 1: e all 0.5 (wrong) + perfect outcome model -> exactly 5.0")
    else:
        failed += 1
        print("  ❌ DR direction 1 failed:", dr_bad_e.ate)

    # ── double robustness, direction 2: the OUTCOME MODEL is useless ──────────
    # mu0 = mu1 = c. The regression part is 0 and the correction is (68 - 8c - 28 + 8c)/8 = 5,
    # independent of c. Asserted at two different constants so the independence is demonstrated.
    var dr_c17 = aipw_ate(_y(), _t(), _e_true(), _const(17.0), _const(17.0), 0.0, 1.0e9, 1.96)
    var dr_c0 = aipw_ate(_y(), _t(), _e_true(), _const(0.0), _const(0.0), 0.0, 1.0e9, 1.96)
    if (
        dr_c17.status == CI_OK
        and _close(dr_c17.ate, 5.0)
        and dr_c17.ate_regression == 0.0
        and _close(dr_c17.ate_correction, 5.0)
        and dr_c0.status == CI_OK
        and _close(dr_c0.ate, 5.0)
        and _close(dr_c0.decomposition_residual, 0.0)
    ):
        passed += 1
        print("  ✅ DR direction 2: constant outcome model (c=17 and c=0) + true e -> 5.0")
    else:
        failed += 1
        print("  ❌ DR direction 2 failed:", dr_c17.ate, dr_c0.ate)

    # With c = 0 the estimator IS Horvitz-Thompson IPW, so it must equal `ipw_ate`'s HT exactly.
    if dr_c0.ate == ipw.ate_ht:
        passed += 1
        print("  ✅ mu = 0 makes AIPW literally the HT estimator — bit-identical to ipw_ate")
    else:
        failed += 1
        print("  ❌ AIPW with mu=0 differs from HT IPW:", dr_c0.ate, ipw.ate_ht)

    # ── the AIPW chain end to end: fitted models, not hand-built ones ─────────
    var chained = aipw_ate(_y(), _t(), _e_true(), om.mu0, om.mu1, 0.0, 1000.0, 1.96)
    if chained.status == CI_OK and chained.has_ate and _close(chained.ate, 5.0):
        passed += 1
        print("  ✅ AIPW over outcome_regression_ate's own mu0/mu1 recovers 5.0")
    else:
        failed += 1
        print("  ❌ the chained pipeline failed:", chained.ate)

    # ── the interval, and its absence ────────────────────────────────────────
    # The noiseless dataset makes every influence value equal, so the variance is 0 and the
    # interval has zero width. That is a real answer and the SE is present, not absent.
    if (
        dr.has_se
        and dr.se == 0.0
        and dr.has_ci
        and _close(dr.ci_lo, 5.0)
        and dr.ci_lo == dr.ci_hi
    ):
        passed += 1
        print("  ✅ a noiseless dataset gives se = 0 and a zero-width interval, not an absence")
    else:
        failed += 1
        print("  ❌ interval wrong:", dr.se, dr.ci_lo, dr.ci_hi)

    # z <= 0 suppresses the interval rather than producing a degenerate one.
    var no_ci = aipw_ate(
        _y(), _t(), _e_true(), _mu0_perfect(), _mu1_perfect(), 0.0, 1000.0, 0.0
    )
    if no_ci.status == CI_OK and no_ci.has_se and not no_ci.has_ci:
        passed += 1
        print("  ✅ z = 0 suppresses the interval; the SE is still reported")
    else:
        failed += 1
        print("  ❌ z=0 handling wrong")

    # ── the bootstrap is bit-identical for a fixed seed ──────────────────────
    var noisy_y = _floats(7.0, 2.5, 1.5, 2.0, 11.0, 9.0, 10.5, 5.5)
    var b_a = aipw_bootstrap_ci(
        noisy_y, _t(), _e_true(), _mu0_perfect(), _mu1_perfect(), 200, 12345, 0.05
    )
    var b_b = aipw_bootstrap_ci(
        noisy_y, _t(), _e_true(), _mu0_perfect(), _mu1_perfect(), 200, 12345, 0.05
    )
    var b_c = aipw_bootstrap_ci(
        noisy_y, _t(), _e_true(), _mu0_perfect(), _mu1_perfect(), 200, 999, 0.05
    )
    if (
        b_a.status == CI_OK
        and b_a.has_ci
        and b_a.ci_lo == b_b.ci_lo
        and b_a.ci_hi == b_b.ci_hi
        and b_a.se_boot == b_b.se_boot
        and b_a.point == b_b.point
        and b_a.n_replicates_used == b_b.n_replicates_used
        and b_a.seed_used == 12345
    ):
        passed += 1
        print("  ✅ same seed -> BIT-IDENTICAL interval, se and replicate count")
    else:
        failed += 1
        print("  ❌ the bootstrap is not reproducible:", b_a.ci_lo, b_b.ci_lo)

    if b_c.status == CI_OK and b_c.has_ci and (b_c.ci_lo != b_a.ci_lo or b_c.ci_hi != b_a.ci_hi):
        passed += 1
        print("  ✅ a different seed moves the interval — the draws are real, not constant")
    else:
        failed += 1
        print("  ❌ a different seed produced the identical interval")

    # The point estimate is the full-sample AIPW, not a bootstrap average.
    var point_check = aipw_ate(
        noisy_y, _t(), _e_true(), _mu0_perfect(), _mu1_perfect(), 0.0, 1.0e300, 0.0
    )
    if (
        b_a.point == point_check.ate
        and b_a.ci_lo <= b_a.ci_hi
        and b_a.n_replicates == 200
        and b_a.n_replicates_used + b_a.n_replicates_dropped == 200
    ):
        passed += 1
        print("  ✅ point == the full-sample AIPW; used + dropped == n_replicates")
    else:
        failed += 1
        print("  ❌ bootstrap bookkeeping wrong:", b_a.point, point_check.ate)

    # A degenerate propensity is refused ONCE, before any replicate runs.
    var boot_degen = aipw_bootstrap_ci(
        _y(), _t(), _floats(0.0, 0.25, 0.25, 0.25, 0.75, 0.75, 0.75, 0.75),
        _mu0_perfect(), _mu1_perfect(), 50, 1, 0.05,
    )
    if boot_degen.status == CI_ERR_DEGENERATE_PROPENSITY and not boot_degen.has_ci:
        passed += 1
        print("  ✅ a degenerate propensity is refused once, not silently per replicate")
    else:
        failed += 1
        print("  ❌ bootstrap degeneracy handling wrong:", boot_degen.status)

    # ── the bootstrap is charged against ITS OWN measured cost ────────────────
    # This used to borrow `MAX_CI_FIT_WORK` (2^30), a ceiling whose comment justifies itself with
    # "max_iter x n_units x (n_features+1)^2 for the Newton fit ... 2^30 is order-of-seconds" —
    # written for a ~1 ns multiply-accumulate. A bootstrap replicate is not a Newton step: it
    # allocates six n-length lists and runs a keyed RNG call per drawn unit. MEASURED across four
    # shapes (n = 200..2048, replicates = 4096..80,000): 98-141 ns per charged (replicate x unit),
    # so 2^30 bought 118-151 SECONDS. 2^24 was chosen by measuring AT it — 1.84 s at
    # 1024 units x 16,384 replicates, 1.96-2.26 s at the same charge in two other shapes.
    #
    # The boundary is asserted on the arithmetic (no 2-second call in a unit suite) and the
    # refusal on a real call: 64 units x 2^20 replicates is a charge of 2^26, four times the new
    # ceiling and a sixteenth of the old one, so it was admitted before and is refused now.
    var boot_y = List[Float64]()
    var boot_t = List[Int]()
    var boot_e = List[Float64]()
    var boot_m0 = List[Float64]()
    var boot_m1 = List[Float64]()
    for i in range(64):
        boot_t.append(1 if (i % 2) == 0 else 0)
        boot_e.append(0.5)
        boot_y.append(1.0 + Float64(i % 7) + (3.0 if (i % 2) == 0 else 0.0))
        boot_m0.append(1.0 + Float64(i % 7))
        boot_m1.append(4.0 + Float64(i % 7))
    var over_budget = aipw_bootstrap_ci(
        boot_y, boot_t, boot_e, boot_m0, boot_m1, MAX_CI_ITERATIONS, 3, 0.05
    )
    var in_budget = aipw_bootstrap_ci(boot_y, boot_t, boot_e, boot_m0, boot_m1, 500, 3, 0.05)
    if (
        MAX_CI_BOOTSTRAP_WORK == 1 << 24
        # the ceiling it used to borrow was 64x looser, which is the whole defect
        and MAX_CI_BOOTSTRAP_WORK < MAX_CI_FIT_WORK
        # exact boundary, without forming the product being bounded
        and ci_product_fits(1 << 20, 16, MAX_CI_BOOTSTRAP_WORK)
        and not ci_product_fits(1 << 20, 17, MAX_CI_BOOTSTRAP_WORK)
        # a charge the old ceiling admitted (2^26 <= 2^30) is now refused
        and ci_product_fits(MAX_CI_ITERATIONS, 64, MAX_CI_FIT_WORK)
        and not ci_product_fits(MAX_CI_ITERATIONS, 64, MAX_CI_BOOTSTRAP_WORK)
        and over_budget.status == CI_ERR_WORK_BUDGET
        and not over_budget.has_ci
        # and an ordinary bootstrap is untouched
        and in_budget.status == CI_OK
        and in_budget.has_ci
        and in_budget.n_replicates_used == 500
    ):
        passed += 1
        print("  ✅ the bootstrap has its own measured work ceiling, not the Newton fit's")
    else:
        failed += 1
        print(
            "  ❌ bootstrap work budget wrong:",
            MAX_CI_BOOTSTRAP_WORK,
            over_budget.status,
            in_budget.status,
        )

    # ── the charge has to bound the COST, and only a run can say whether it does ──
    # The ceiling above bounds `n_replicates x n`. The two percentile calls at the end of
    # `aipw_bootstrap_ci` cost `O(f(n_replicates))` with no `n` in it at all, so the charge says
    # nothing about them, and `math_ext.quantile` makes `f` QUADRATIC (its `_sort_copy` is an
    # insertion sort). MEASURED with that quantile, at charges the ceiling admits exactly:
    #
    #     n = 1024, B =   16384    1.12 s
    #     n =  256, B =   65536    1.84 s
    #     n =   64, B =  262144   20.79 s
    #     n =   16, B = 1048576  353.92 s     <- and the block above ASSERTS this one admitted
    #
    # Same four charges through `stats.quantile`: 0.70 / 0.74 / 0.99 / 1.56 s.
    #
    # Asserted as a SCALING RATIO rather than a wall-clock bound, because a ratio is a property
    # of the algorithm and a stopwatch reading is a property of the machine. Quadrupling `B` at a
    # fixed `n` costs ~4x under an introsort and ~16x under an insertion sort; measured here,
    # 4.02x against 14.16x, which no plausible machine or load reorders. The absolute ceiling
    # beside it is deliberately loose (55x the observed 0.18 s) and exists only to catch a
    # regression so gross that the ratio survives it.
    var t_a0 = perf_counter_ns()
    var boot_small = aipw_bootstrap_ci(
        _boot_y(16), _boot_t(16), _boot_e(16), _boot_m0(16), _boot_m1(16), 32768, 7, 0.05
    )
    var t_a1 = perf_counter_ns()
    var boot_big = aipw_bootstrap_ci(
        _boot_y(16), _boot_t(16), _boot_e(16), _boot_m0(16), _boot_m1(16), 131072, 7, 0.05
    )
    var t_a2 = perf_counter_ns()
    var secs_small = Float64(Int(t_a1 - t_a0)) / 1.0e9
    var secs_big = Float64(Int(t_a2 - t_a1)) / 1.0e9
    var quadruple_ratio = secs_big / secs_small if secs_small > 0.0 else 1.0e9
    if (
        boot_small.status == CI_OK
        and boot_big.status == CI_OK
        and boot_small.has_ci
        and boot_big.has_ci
        # 4x the replicates must cost about 4x, not about 16x
        and quadruple_ratio < 8.0
        and secs_big < 10.0
    ):
        passed += 1
        print(
            "  ✅ 4x the replicates costs",
            quadruple_ratio,
            "x, not 16x — the percentile sort is O(B log B)",
        )
    else:
        failed += 1
        print(
            "  ❌ the bootstrap percentile is superlinear in n_replicates:",
            secs_small,
            "s ->",
            secs_big,
            "s, ratio",
            quadruple_ratio,
        )

    # ── refusals ─────────────────────────────────────────────────────────────
    if (
        naive_ate(_floats(1.0), _ints(1)).status == 349
        and naive_ate(_y(), _ints(1, 0)).status == CI_ERR_LENGTH_MISMATCH
        and naive_ate(List[Float64](), List[Int]()).status == CI_ERR_INSUFFICIENT_DATA
        and strata_ate(_y(), _t(), _strata(), 0).status == CI_ERR_SHAPE
        and strata_ate(_y(), _t(), _strata(), 9).status == CI_ERR_SHAPE
        and strata_ate(_y(), _t(), _ints(0, 0, 0, 0, 1, 1, 1, 7), 2).status == CI_ERR_INDEX
        and aipw_ate(_y(), _t(), _e_true(), _mu0_perfect(), _floats(1.0), 0.0, 1.0, 1.0).status
        == CI_ERR_LENGTH_MISMATCH
        and aipw_bootstrap_ci(
            _y(), _t(), _e_true(), _mu0_perfect(), _mu1_perfect(), 1, 1, 0.05
        ).status
        == CI_ERR_INVALID_PARAMETER
        and aipw_bootstrap_ci(
            _y(), _t(), _e_true(), _mu0_perfect(), _mu1_perfect(), 10, -1, 0.05
        ).status
        == CI_ERR_INVALID_PARAMETER
        # An explicit replicate ceiling as well as the `n_replicates * n` product budget, which
        # admits half a billion replicates on a small sample — each allocating six lists.
        and aipw_bootstrap_ci(
            _y(), _t(), _e_true(), _mu0_perfect(), _mu1_perfect(),
            MAX_CI_ITERATIONS + 1, 1, 0.05,
        ).status
        == CI_ERR_INVALID_PARAMETER
        and outcome_regression_ate(
            _x(), 8, 1, _t(), _y(), 0.0, 0.0, MAX_CI_ITERATIONS + 1, 1.0e-12
        ).status
        == CI_ERR_INVALID_PARAMETER
    ):
        passed += 1
        print("  ✅ one-armed, mismatched, out-of-range stratum, bad replicate count and seed")
    else:
        failed += 1
        print("  ❌ refusals incomplete")

    # An arm with fewer units than parameters cannot identify its regression.
    var thin = outcome_regression_ate(
        _floats(1.0, 2.0, 3.0, 4.0, 5.0, 6.0), 3, 2, _ints(1, 1, 0), _floats(1.0, 2.0, 3.0),
        0.0, 0.0, 100, 1.0e-12,
    )
    if thin.status == CI_ERR_INSUFFICIENT_DATA and not thin.has_ate:
        passed += 1
        print("  ✅ an arm with fewer rows than features+1 is refused, not fitted arbitrarily")
    else:
        failed += 1
        print("  ❌ thin-arm refusal wrong:", thin.status)

    # An iteration cap of 1 does not converge, and then there is no ATE.
    var capped = outcome_regression_ate(_x(), 8, 1, _t(), _y(), 0.0, 0.0, 1, 1.0e-14)
    if (
        capped.status == CI_ERR_NOT_CONVERGED
        and not capped.has_ate
        and len(capped.mu0) == 0
        and len(capped.mu1) == 0
        and capped.n_iter_treated == 1
    ):
        passed += 1
        print("  ✅ max_iter=1: NOT_CONVERGED with mu0/mu1 absent and n_iter reported")
    else:
        failed += 1
        print("  ❌ non-convergence handling wrong:", capped.status, len(capped.mu0))

    # ── the A-Z harness pattern ──────────────────────────────────────────────
    if (
        naive_ate(_lf5(), _li5()).status == CI_ERR_TREATMENT_NOT_BINARY
        and outcome_regression_ate(_lf5(), 5, 5, _li5(), _lf5(), 0.5, 0.5, 5, 0.5).status
        == CI_ERR_SHAPE
        and aipw_ate(_lf5(), _li5(), _lf5(), _lf5(), _lf5(), 0.5, 0.5, 0.5).status
        == CI_ERR_INVALID_PARAMETER
        and strata_ate(_lf5(), _li5(), _li5(), 5).status == CI_ERR_TREATMENT_NOT_BINARY
        and aipw_bootstrap_ci(_lf5(), _li5(), _lf5(), _lf5(), _lf5(), 5, 5, 0.5).status
        == CI_ERR_TREATMENT_NOT_BINARY
    ):
        passed += 1
        print("  ✅ the fixed 5-element / 5-integer harness pattern is refused, not indexed")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern was mishandled")

    print("  [causal_inference.estimators] Passed:", passed, "Failed:", failed)
