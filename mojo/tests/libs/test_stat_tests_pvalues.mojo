"""test_stat_tests_pvalues.mojo — known-value tests for stat_tests p-values.

Hand-written, not generated. `test_stat_tests.mojo` (auto-generated) only proves every
public function in this module runs without crashing; it asserts no numeric value at all.
Nothing anywhere checked that a `stat_tests` p-value is actually CORRECT until this file,
which is also why `_regularized_incomplete_beta`'s first-term bug (see below) shipped
undetected for as long as it did.

Every expected value below is `scipy`'s reference for the identical input, computed once
and hardcoded as a literal — not re-derived by a second Mojo implementation, so agreement
here is evidence against an independent computation, not a comparison of this module with
itself.

Why the tolerances are 1e-6, not 1e-12
---------------------------------------
`_regularized_incomplete_beta`'s continued fraction and scipy's own incomplete-beta
machinery are two independent implementations of the same function, and away from the
continued fraction's branch-switch threshold they agree to ~1e-10 or better. AT that
threshold (`x` very close to `(a+1)/(a+b+2)` — `(0.5, 4.0, 4.0)` below is exactly on it,
since `a == b` puts the threshold at exactly `x = 0.5`) convergence is slower by
construction, and the gap can widen to the 1e-9 range for small `(a, b)` and further for
large ones (see `inference.core.t_cdf_agreement`'s docstring for the measured worst case,
`3.4e-7`, at large degrees of freedom). `1e-6` is comfortably above every case exercised
here while staying five-plus orders of magnitude tighter than the pre-fix defect, which was
not a precision question at all: `_regularized_incomplete_beta(0.6, 3.0, 0.5)` used to
return `-0.02297233739032732`, a NEGATIVE probability, and `_t_cdf(2.0, 6.0)` used to
return `1.0114861686851442`, greater than 1.
"""
from std.math import abs as fabs

from stat_tests import (
    _regularized_incomplete_beta,
    _t_cdf,
    pearson_r,
    spearman_r,
    t_test_1sample,
    t_test_2sample,
)


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


def main():
    var passed: Int = 0
    var failed: Int = 0

    # ── 1. the incomplete beta itself, across a: b) grid including the branch ──
    # threshold and a near-underflow tail value.
    var xs = List[Float64]()
    var aas = List[Float64]()
    var bbs = List[Float64]()
    var refs = List[Float64]()
    xs.append(0.6); aas.append(3.0); bbs.append(0.5); refs.append(0.09242631153167516)
    xs.append(0.5); aas.append(4.0); bbs.append(4.0); refs.append(0.5)
    xs.append(0.9); aas.append(4.0); bbs.append(0.5); refs.append(0.3733749174022597)
    xs.append(0.1); aas.append(2.0); bbs.append(2.0); refs.append(0.028000000000000008)
    xs.append(0.3); aas.append(0.5); bbs.append(0.5); refs.append(0.36901011956554536)
    xs.append(0.99); aas.append(10.0); bbs.append(10.0); refs.append(0.9999999999999991)
    xs.append(0.01); aas.append(10.0); bbs.append(10.0); refs.append(8.509104732905513e-16)
    xs.append(0.5); aas.append(0.001); bbs.append(0.001); refs.append(0.49999999999999994)

    var beta_ok = True
    for i in range(len(xs)):
        var got = _regularized_incomplete_beta(xs[i], aas[i], bbs[i])
        var expected = refs[i]
        var tol = 1.0e-6 if expected > 1.0e-6 else expected * 0.01 + 1.0e-18
        if not _close(got, expected, tol):
            beta_ok = False
            print("  ❌ I_x(a,b) at index", i, ":", got, "vs", expected)
    if beta_ok and _regularized_incomplete_beta(0.6, 3.0, 0.5) > 0.0:
        passed += 1
        print("  ✅ _regularized_incomplete_beta matches scipy.special.betainc over 8 (x,a,b) points")
    else:
        failed += 1
        print("  ❌ _regularized_incomplete_beta grid failed")

    # ── 2. the t CDF is a probability, and matches the closed-form-cross-checked truth ──
    var t_2_6 = _t_cdf(2.0, 6.0)
    var t_1_5 = _t_cdf(1.0, 5.0)
    if (
        t_2_6 > 0.0 and t_2_6 < 1.0
        and _close(t_2_6, 0.9537868442341706, 1.0e-6)
        and t_1_5 > 0.0 and t_1_5 < 1.0
        and _close(t_1_5, 0.8183912661754367, 1.0e-6)
    ):
        passed += 1
        print("  ✅ _t_cdf(2,6) and _t_cdf(1,5) are both probabilities matching the true CDF")
    else:
        failed += 1
        print("  ❌ _t_cdf wrong:", t_2_6, t_1_5)

    # ── 3. t_test_1sample against scipy.stats.ttest_1samp ───────────────────────
    var s1 = List[Float64]()
    for v in [5.1, 4.9, 5.3, 5.0, 4.8, 5.2, 5.05, 4.95, 5.1, 4.9]:
        s1.append(v)
    var t1 = t_test_1sample(s1, 5.0)
    if (
        _close(t1.statistic, 0.627059712862443, 1.0e-9)
        and _close(t1.p_value, 0.5461963009225377, 1.0e-6)
        and not t1.reject_h0
    ):
        passed += 1
        print("  ✅ t_test_1sample matches scipy.stats.ttest_1samp: t=0.62706 p=0.54620")
    else:
        failed += 1
        print("  ❌ t_test_1sample wrong:", t1.statistic, t1.p_value)

    # ── 4. t_test_2sample -- the exact case this module's history is written around ──
    var g1 = List[Float64](); g1.append(1.0); g1.append(2.0); g1.append(3.0)
    var g2 = List[Float64](); g2.append(4.0); g2.append(5.0); g2.append(6.0)
    var t2 = t_test_2sample(g1, g2)
    if (
        t2.statistic == -3.6742346141747673
        and t2.p_value > 0.02 and t2.p_value < 0.03
        and _close(t2.p_value, 0.021311641128756727, 1.0e-6)
        and t2.reject_h0
    ):
        passed += 1
        print("  ✅ t_test_2sample([1,2,3],[4,5,6]): t=-3.67423 p=0.02131 (was p=0.0 pre-fix)")
    else:
        failed += 1
        print("  ❌ t_test_2sample wrong:", t2.statistic, t2.p_value, t2.reject_h0)

    # ── 5. pearson_r against scipy.stats.pearsonr ───────────────────────────────
    var x = List[Float64]()
    var y = List[Float64]()
    for v in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]:
        x.append(v)
    for v in [2.1, 3.9, 6.2, 7.8, 10.5, 11.5, 14.2, 15.8, 18.1, 19.9]:
        y.append(v)
    var pr = pearson_r(x, y)
    var pr_p_rel = fabs(pr.p_value - 5.325524542227731e-12) / 5.325524542227731e-12
    if (
        _close(pr.r, 0.9989492896628988, 1.0e-9)
        and pr_p_rel < 1.0e-4
    ):
        passed += 1
        print("  ✅ pearson_r matches scipy.stats.pearsonr: r=0.99895 p=5.3255e-12")
    else:
        failed += 1
        print("  ❌ pearson_r wrong:", pr.r, pr.p_value)

    # ── 6. spearman_r against scipy.stats.spearmanr, a non-underflowed case ────
    var x2 = List[Float64]()
    var y2 = List[Float64]()
    for v in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]:
        x2.append(v)
    for v in [3.0, 1.0, 4.0, 2.0, 6.0, 5.0, 9.0, 7.0, 8.0, 10.0]:
        y2.append(v)
    var sr = spearman_r(x2, y2)
    if (
        sr.r == 0.8909090909090909
        and _close(sr.p_value, 0.0005421442248338665, 1.0e-6)
    ):
        passed += 1
        print("  ✅ spearman_r matches scipy.stats.spearmanr: rho=0.89091 p=5.4214e-4")
    else:
        failed += 1
        print("  ❌ spearman_r wrong:", sr.r, sr.p_value)

    print("  [stat_tests_pvalues] Passed:", passed, "Failed:", failed)
