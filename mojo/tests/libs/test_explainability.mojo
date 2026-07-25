"""test_explainability.mojo — known-value tests for explainability."""
from explainability import (
    PermutationImportance,
    PartialDependence,
    ShapleySamples,
    permutation_importance_from_preds,
    partial_dependence_grid,
    kernel_shap_weight,
    shapley_sampling_weights,
)

from std.math import abs as fabs, sqrt


fn _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


fn check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ explainability::" + name)
    else:
        failed += 1
        print("  ❌ explainability::" + name)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── kernel_shap_weight: hand-computed for M=4, |z|=1..3 ──────────────────
    # pi(z) = (M-1) / (C(M,|z|) * |z| * (M-|z|))
    #   k=1: 3 / (4*1*3)  = 0.25
    #   k=2: 3 / (6*2*2)  = 0.125
    #   k=3: 3 / (4*3*1)  = 0.25
    check(
        _close(kernel_shap_weight(4, 1), 0.25, 1e-15),
        "kernel weight M=4 k=1 == 3/12",
        passed,
        failed,
    )
    check(
        _close(kernel_shap_weight(4, 2), 0.125, 1e-15),
        "kernel weight M=4 k=2 == 3/24",
        passed,
        failed,
    )
    check(
        _close(kernel_shap_weight(4, 3), 0.25, 1e-15),
        "kernel weight M=4 k=3 == 3/12",
        passed,
        failed,
    )

    # ── kernel_shap_weight: more hand values + symmetry ──────────────────────
    # M=2 k=1: 1/(2*1*1) = 0.5.  M=3 k=1: 2/(3*1*2) = 1/3 = k=2.
    # M=10 k=2: 9/(45*2*8) = 9/720 = 0.0125.
    check(
        _close(kernel_shap_weight(2, 1), 0.5, 1e-15)
        and _close(kernel_shap_weight(3, 1), 1.0 / 3.0, 1e-15)
        and _close(kernel_shap_weight(3, 2), 1.0 / 3.0, 1e-15)
        and _close(kernel_shap_weight(10, 2), 0.0125, 1e-15),
        "kernel weight M=2,3,10 hand values",
        passed,
        failed,
    )
    var sym_ok = True
    for k in range(1, 7):
        if not _close(
            kernel_shap_weight(7, k), kernel_shap_weight(7, 7 - k), 1e-15
        ):
            sym_ok = False
    check(sym_ok, "kernel weight symmetric pi(k) == pi(M-k) for M=7", passed, failed)
    check(
        kernel_shap_weight(4, 0) == 0.0
        and kernel_shap_weight(4, 4) == 0.0
        and kernel_shap_weight(4, -1) == 0.0
        and kernel_shap_weight(4, 5) == 0.0
        and kernel_shap_weight(1, 1) == 0.0
        and kernel_shap_weight(0, 0) == 0.0,
        "kernel weight degenerate coalitions -> 0.0",
        passed,
        failed,
    )

    # ── permutation_importance_from_preds: known values ──────────────────────
    # base MSE 0.1; feature-major, 3 repeats:
    #   f0 permuted: 0.2, 0.3, 0.4 -> mean 0.3, importance +0.2,
    #      pop std = sqrt(((0.1)^2 + 0 + (0.1)^2)/3) = sqrt(0.02/3)
    #   f1 permuted: 0.1, 0.1, 0.1 -> importance 0.0, std 0.0
    var pm = List[Float64]()
    pm.append(0.2); pm.append(0.3); pm.append(0.4)
    pm.append(0.1); pm.append(0.1); pm.append(0.1)
    var pi_res = permutation_importance_from_preds(0.1, pm, 2, 3)
    check(
        len(pi_res.means) == 2 and len(pi_res.stds) == 2,
        "permutation importance output lengths",
        passed,
        failed,
    )
    check(
        _close(pi_res.means[0], 0.2, 1e-12)
        and _close(pi_res.means[1], 0.0, 1e-12),
        "permutation importance means exact (+0.2, 0.0)",
        passed,
        failed,
    )
    check(
        _close(pi_res.stds[0], sqrt(0.02 / 3.0), 1e-12)
        and _close(pi_res.stds[1], 0.0, 1e-12),
        "permutation importance pop stds exact",
        passed,
        failed,
    )

    # Negative importance (metric improves when permuted) + n_repeats=2 std.
    # base 0.5, single feature, repeats {0.4, 0.6}: mean 0.5 -> importance 0,
    # pop std = 0.1. Then base 0.5 vs single repeat {0.3}: importance -0.2, std 0.
    var pm2 = List[Float64]()
    pm2.append(0.4); pm2.append(0.6)
    var pi2 = permutation_importance_from_preds(0.5, pm2, 1, 2)
    var pm3 = List[Float64]()
    pm3.append(0.3)
    var pi3 = permutation_importance_from_preds(0.5, pm3, 1, 1)
    check(
        len(pi2.means) == 1
        and _close(pi2.means[0], 0.0, 1e-12)
        and _close(pi2.stds[0], 0.1, 1e-12)
        and len(pi3.means) == 1
        and _close(pi3.means[0], -0.2, 1e-12)
        and _close(pi3.stds[0], 0.0, 1e-12),
        "permutation importance negative shift + single repeat",
        passed,
        failed,
    )

    # Edge cases: bad dims / empty input -> empty struct.
    var empty_f = List[Float64]()
    var pi_bad = permutation_importance_from_preds(0.1, pm, 2, 2)  # len 6 != 4
    var pi_e1 = permutation_importance_from_preds(0.1, empty_f, 0, 3)
    var pi_e2 = permutation_importance_from_preds(0.1, empty_f, 2, 0)
    check(
        len(pi_bad.means) == 0
        and len(pi_e1.means) == 0
        and len(pi_e2.means) == 0,
        "permutation importance bad dims -> empty",
        passed,
        failed,
    )

    # ── partial_dependence_grid: known values ────────────────────────────────
    # 2 grid points, 3 samples, grid-major:
    #   g0 ICE: 1, 2, 3 -> mean 2, pop std sqrt(2/3)
    #   g1 ICE: 4, 4, 4 -> mean 4, std 0
    var ice = List[Float64]()
    ice.append(1.0); ice.append(2.0); ice.append(3.0)
    ice.append(4.0); ice.append(4.0); ice.append(4.0)
    var pd = partial_dependence_grid(ice, 2, 3)
    check(
        len(pd.mean) == 2
        and _close(pd.mean[0], 2.0, 1e-12)
        and _close(pd.mean[1], 4.0, 1e-12),
        "partial dependence means exact (2, 4)",
        passed,
        failed,
    )
    check(
        _close(pd.std[0], sqrt(2.0 / 3.0), 1e-12)
        and _close(pd.std[1], 0.0, 1e-12),
        "partial dependence ICE spread exact",
        passed,
        failed,
    )

    # n_samples=1: PD curve equals the single ICE curve, std all-zero.
    var ice1 = List[Float64]()
    ice1.append(7.5); ice1.append(-2.0)
    var pd1 = partial_dependence_grid(ice1, 2, 1)
    check(
        len(pd1.mean) == 2
        and _close(pd1.mean[0], 7.5, 1e-12)
        and _close(pd1.mean[1], -2.0, 1e-12)
        and pd1.std[0] == 0.0
        and pd1.std[1] == 0.0,
        "partial dependence n_samples=1 passthrough",
        passed,
        failed,
    )

    # All-equal predictions: flat PD curve.
    var flat = List[Float64]()
    for _ in range(6):
        flat.append(3.0)
    var pdf = partial_dependence_grid(flat, 3, 2)
    check(
        len(pdf.mean) == 3
        and _close(pdf.mean[0], 3.0, 1e-12)
        and _close(pdf.mean[2], 3.0, 1e-12)
        and pdf.std[1] == 0.0,
        "partial dependence all-equal -> flat curve",
        passed,
        failed,
    )

    # Edge cases: bad dims -> empty.
    var pd_bad = partial_dependence_grid(ice, 2, 2)  # len 6 != 4
    var pd_e = partial_dependence_grid(empty_f, 0, 3)
    check(
        len(pd_bad.mean) == 0 and len(pd_e.mean) == 0,
        "partial dependence bad dims -> empty",
        passed,
        failed,
    )

    # ── shapley_sampling_weights: validity of the coalition matrix ───────────
    var ss = shapley_sampling_weights(4, 200, 7)
    check(
        ss.n_samples == 200
        and ss.n_features == 4
        and len(ss.coalitions) == 800
        and len(ss.weights) == 200,
        "shapley samples dims (200 x 4)",
        passed,
        failed,
    )
    var entries_ok = True
    var rows_ok = True
    var weights_ok = True
    var saw_k2 = False
    var saw_k13 = False
    for s in range(200):
        var k = 0
        for f in range(4):
            var v = ss.coalitions[s * 4 + f]
            if v != 0 and v != 1:
                entries_ok = False
            k += v
        if k == 0 or k == 4:
            rows_ok = False
        if not _close(ss.weights[s], kernel_shap_weight(4, k), 1e-15):
            weights_ok = False
        if k == 2:
            saw_k2 = True
        if k == 1 or k == 3:
            saw_k13 = True
    check(entries_ok, "shapley coalitions entries all 0/1", passed, failed)
    check(rows_ok, "shapley no empty and no full coalitions", passed, failed)
    check(
        weights_ok,
        "shapley weights match pi(M=4, |z|) per row",
        passed,
        failed,
    )
    check(
        saw_k2 and saw_k13,
        "shapley multiple coalition sizes sampled",
        passed,
        failed,
    )

    # ── shapley_sampling_weights: determinism + seed sensitivity ─────────────
    var ss_b = shapley_sampling_weights(4, 200, 7)
    var same = len(ss_b.coalitions) == len(ss.coalitions)
    if same:
        for i in range(len(ss.coalitions)):
            if ss.coalitions[i] != ss_b.coalitions[i]:
                same = False
    check(same, "shapley deterministic for seed=7", passed, failed)
    var ss_c = shapley_sampling_weights(4, 200, 8)
    var differs = False
    for i in range(len(ss.coalitions)):
        if ss.coalitions[i] != ss_c.coalitions[i]:
            differs = True
    check(differs, "shapley seed=8 differs from seed=7", passed, failed)

    # ── shapley_sampling_weights: M=2 exact — rows are (0,1)/(1,0), pi=0.5 ──
    var s2 = shapley_sampling_weights(2, 50, 11)
    var m2_ok = s2.n_samples == 50
    var saw01 = False
    var saw10 = False
    for s in range(50):
        var a = s2.coalitions[s * 2]
        var b = s2.coalitions[s * 2 + 1]
        if a + b != 1:
            m2_ok = False
        if a == 0 and b == 1:
            saw01 = True
        if a == 1 and b == 0:
            saw10 = True
        if not _close(s2.weights[s], 0.5, 1e-15):
            m2_ok = False
    check(
        m2_ok and saw01 and saw10,
        "shapley M=2: both singleton coalitions, weight 0.5",
        passed,
        failed,
    )

    # ── shapley_sampling_weights: infeasible -> empty struct ─────────────────
    var s_bad1 = shapley_sampling_weights(1, 10, 0)
    var s_bad2 = shapley_sampling_weights(0, 10, 0)
    var s_bad3 = shapley_sampling_weights(4, 0, 0)
    check(
        s_bad1.n_samples == 0
        and len(s_bad1.coalitions) == 0
        and s_bad2.n_samples == 0
        and s_bad3.n_samples == 0
        and len(s_bad3.weights) == 0,
        "shapley M<2 or n_samples<=0 -> empty",
        passed,
        failed,
    )

    print("  [explainability] Passed:", passed, "Failed:", failed)
