"""test_model_compare.mojo — known-value tests for model_compare."""
from std.math import isnan, isinf, abs as fabs
from model_compare import (
    paired_bootstrap_diff_ci,
    mcnemar_exact_p,
    diebold_mariano,
    sharpe_diff_bootstrap_ci,
)


fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)


fn close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return is_finite(a) and fabs(a - b) <= tol


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── mcnemar_exact_p ─────────────────────────────────────────────────────
    # Hand-computed: n=8, k_min=0 → p = 2 * 0.5^8 = 0.0078125 exactly.
    var p08 = mcnemar_exact_p(0, 8)
    if close(p08, 0.0078125, 1e-12):
        passed += 1
        print("  ✅ model_compare::mcnemar_exact_p (0,8) =", p08)
    else:
        failed += 1
        print("  ❌ model_compare::mcnemar_exact_p (0,8) → expected 0.0078125, got", p08)

    # Symmetric input: mcnemar(8, 0) must equal mcnemar(0, 8).
    var p80 = mcnemar_exact_p(8, 0)
    if close(p80, 0.0078125, 1e-12):
        passed += 1
        print("  ✅ model_compare::mcnemar_exact_p (8,0) symmetric =", p80)
    else:
        failed += 1
        print("  ❌ model_compare::mcnemar_exact_p (8,0) → expected 0.0078125, got", p80)

    # Perfectly balanced discordants: p capped at 1.0.
    var p44 = mcnemar_exact_p(4, 4)
    if close(p44, 1.0, 1e-12):
        passed += 1
        print("  ✅ model_compare::mcnemar_exact_p (4,4) =", p44)
    else:
        failed += 1
        print("  ❌ model_compare::mcnemar_exact_p (4,4) → expected 1.0, got", p44)

    # Hand-computed: n=10, k_min=2 → 2 * (C(10,0)+C(10,1)+C(10,2)) / 2^10
    #              = 2 * 56/1024 = 0.109375 (1e-9 tol: log-space exp round-trip).
    var p28 = mcnemar_exact_p(2, 8)
    if close(p28, 0.109375, 1e-9):
        passed += 1
        print("  ✅ model_compare::mcnemar_exact_p (2,8) =", p28)
    else:
        failed += 1
        print("  ❌ model_compare::mcnemar_exact_p (2,8) → expected 0.109375, got", p28)

    # Edge: no discordant pairs → 1.0.
    var p00 = mcnemar_exact_p(0, 0)
    if close(p00, 1.0, 1e-15):
        passed += 1
        print("  ✅ model_compare::mcnemar_exact_p (0,0) edge =", p00)
    else:
        failed += 1
        print("  ❌ model_compare::mcnemar_exact_p (0,0) → expected 1.0, got", p00)

    # Large counts must stay stable in log space (no factorial overflow).
    var p_big = mcnemar_exact_p(400, 600)
    if is_finite(p_big) and p_big > 0.0 and p_big < 1e-6:
        passed += 1
        print("  ✅ model_compare::mcnemar_exact_p (400,600) log-stable =", p_big)
    else:
        failed += 1
        print("  ❌ model_compare::mcnemar_exact_p (400,600) → expected tiny finite p, got", p_big)

    # ── paired_bootstrap_diff_ci ────────────────────────────────────────────
    var acc_a = List[Float64]()
    var acc_b = List[Float64]()
    acc_a.append(1.0); acc_a.append(0.0); acc_a.append(1.0)
    acc_a.append(1.0); acc_a.append(0.0)
    acc_b.append(1.0); acc_b.append(0.0); acc_b.append(1.0)
    acc_b.append(1.0); acc_b.append(0.0)

    # Identical arrays → every paired diff is 0 → CI exactly (0, 0), point 0, width 0.
    var ci_same = paired_bootstrap_diff_ci(acc_a, acc_b, 200, 0.05, 42)
    if ci_same.lo == 0.0 and ci_same.hi == 0.0 and ci_same.point == 0.0:
        passed += 1
        print("  ✅ model_compare::paired_bootstrap_diff_ci identical → (0,0,0)")
    else:
        failed += 1
        print("  ❌ model_compare::paired_bootstrap_diff_ci identical → got", ci_same.lo, ci_same.hi, ci_same.point)

    # Constant paired shift a = b + 1 → every replicate mean is exactly 1.0.
    var shift_a = List[Float64]()
    var shift_b = List[Float64]()
    shift_b.append(0.2); shift_b.append(0.5); shift_b.append(0.9); shift_b.append(0.1)
    for i in range(4):
        shift_a.append(shift_b[i] + 1.0)
    var ci_shift = paired_bootstrap_diff_ci(shift_a, shift_b, 200, 0.05, 7)
    if close(ci_shift.lo, 1.0, 1e-12) and close(ci_shift.hi, 1.0, 1e-12) and close(ci_shift.point, 1.0, 1e-12):
        passed += 1
        print("  ✅ model_compare::paired_bootstrap_diff_ci constant shift → (1,1,1)")
    else:
        failed += 1
        print("  ❌ model_compare::paired_bootstrap_diff_ci shift → got", ci_shift.lo, ci_shift.hi, ci_shift.point)

    # Determinism: same seed → identical bounds; sanity: lo <= point <= hi.
    var mixed_a = List[Float64]()
    var mixed_b = List[Float64]()
    mixed_a.append(1.0); mixed_a.append(1.0); mixed_a.append(0.0)
    mixed_a.append(1.0); mixed_a.append(1.0); mixed_a.append(0.0)
    mixed_b.append(0.0); mixed_b.append(1.0); mixed_b.append(0.0)
    mixed_b.append(0.0); mixed_b.append(1.0); mixed_b.append(1.0)
    var ci_r1 = paired_bootstrap_diff_ci(mixed_a, mixed_b, 500, 0.10, 99)
    var ci_r2 = paired_bootstrap_diff_ci(mixed_a, mixed_b, 500, 0.10, 99)
    if ci_r1.lo == ci_r2.lo and ci_r1.hi == ci_r2.hi and ci_r1.lo <= ci_r1.point and ci_r1.point <= ci_r1.hi:
        passed += 1
        print("  ✅ model_compare::paired_bootstrap_diff_ci deterministic seed, lo<=point<=hi")
    else:
        failed += 1
        print("  ❌ model_compare::paired_bootstrap_diff_ci determinism → r1(", ci_r1.lo, ci_r1.hi, ") r2(", ci_r2.lo, ci_r2.hi, ") point", ci_r1.point)

    # Edge: empty input → (0,0,0).
    var empty = List[Float64]()
    var ci_empty = paired_bootstrap_diff_ci(empty, empty, 100, 0.05, 1)
    if ci_empty.lo == 0.0 and ci_empty.hi == 0.0 and ci_empty.point == 0.0:
        passed += 1
        print("  ✅ model_compare::paired_bootstrap_diff_ci empty → (0,0,0)")
    else:
        failed += 1
        print("  ❌ model_compare::paired_bootstrap_diff_ci empty → got", ci_empty.lo, ci_empty.hi, ci_empty.point)

    # Edge: n=1 → the only replicate is the single pair, CI = point exactly.
    var one_a = List[Float64]()
    var one_b = List[Float64]()
    one_a.append(3.0)
    one_b.append(1.0)
    var ci_one = paired_bootstrap_diff_ci(one_a, one_b, 50, 0.05, 3)
    if ci_one.lo == 2.0 and ci_one.hi == 2.0 and ci_one.point == 2.0:
        passed += 1
        print("  ✅ model_compare::paired_bootstrap_diff_ci n=1 → (2,2,2)")
    else:
        failed += 1
        print("  ❌ model_compare::paired_bootstrap_diff_ci n=1 → got", ci_one.lo, ci_one.hi, ci_one.point)

    # ── diebold_mariano ─────────────────────────────────────────────────────
    # Identical errors → zero loss differential → dm_stat 0, p 1.
    var e_same_a = List[Float64]()
    var e_same_b = List[Float64]()
    e_same_a.append(0.5); e_same_a.append(-1.2); e_same_a.append(0.3); e_same_a.append(2.0)
    e_same_b.append(0.5); e_same_b.append(-1.2); e_same_b.append(0.3); e_same_b.append(2.0)
    var dm_same = diebold_mariano(e_same_a, e_same_b, 1)
    if dm_same.dm_stat == 0.0 and dm_same.p_two_sided == 1.0:
        passed += 1
        print("  ✅ model_compare::diebold_mariano identical errors → (0, 1)")
    else:
        failed += 1
        print("  ❌ model_compare::diebold_mariano identical → got", dm_same.dm_stat, dm_same.p_two_sided)

    # Hand-computed h=1: err_a=[2,0], err_b=[0,0] → d=[4,0], d̄=2, γ0=4,
    # dm = 2/sqrt(4/2) = sqrt(2) = 1.41421356..., p = 2(1-Φ(√2)) = 0.15729921.
    var e1a = List[Float64]()
    var e1b = List[Float64]()
    e1a.append(2.0); e1a.append(0.0)
    e1b.append(0.0); e1b.append(0.0)
    var dm1 = diebold_mariano(e1a, e1b, 1)
    if close(dm1.dm_stat, 1.4142135623730951, 1e-9) and close(dm1.p_two_sided, 0.15729920705028522, 1e-6):
        passed += 1
        print("  ✅ model_compare::diebold_mariano h=1 known value =", dm1.dm_stat, dm1.p_two_sided)
    else:
        failed += 1
        print("  ❌ model_compare::diebold_mariano h=1 → expected (1.41421356, 0.15729921), got", dm1.dm_stat, dm1.p_two_sided)

    # Hand-computed h=2 (one Newey-West lag, Bartlett weight 1/2):
    # err_a=[1,2,3], err_b=[0,0,0] → d=[1,4,9], d̄=14/3,
    # γ0=294/27, γ1=-4/27, lrv=290/27, dm = (14/3)/sqrt(290/81) = 2.46632492,
    # p = 0.01365074.
    var e2a = List[Float64]()
    var e2b = List[Float64]()
    e2a.append(1.0); e2a.append(2.0); e2a.append(3.0)
    e2b.append(0.0); e2b.append(0.0); e2b.append(0.0)
    var dm2 = diebold_mariano(e2a, e2b, 2)
    if close(dm2.dm_stat, 2.466324921961755, 1e-9) and close(dm2.p_two_sided, 0.013650744348504773, 1e-6):
        passed += 1
        print("  ✅ model_compare::diebold_mariano h=2 Newey-West known value =", dm2.dm_stat, dm2.p_two_sided)
    else:
        failed += 1
        print("  ❌ model_compare::diebold_mariano h=2 → expected (2.46632492, 0.01365074), got", dm2.dm_stat, dm2.p_two_sided)

    # Sign convention: a worse than b (larger errors) → positive dm_stat.
    if dm2.dm_stat > 0.0:
        passed += 1
        print("  ✅ model_compare::diebold_mariano sign convention (a worse → dm > 0)")
    else:
        failed += 1
        print("  ❌ model_compare::diebold_mariano sign → expected > 0, got", dm2.dm_stat)

    # Edge: empty input → (0, 1).
    var dm_empty = diebold_mariano(empty, empty, 1)
    if dm_empty.dm_stat == 0.0 and dm_empty.p_two_sided == 1.0:
        passed += 1
        print("  ✅ model_compare::diebold_mariano empty → (0, 1)")
    else:
        failed += 1
        print("  ❌ model_compare::diebold_mariano empty → got", dm_empty.dm_stat, dm_empty.p_two_sided)

    # ── sharpe_diff_bootstrap_ci ────────────────────────────────────────────
    # Identical return streams → diff 0 in every replicate → (0, 0, 0).
    var ret_a = List[Float64]()
    var ret_b = List[Float64]()
    ret_a.append(0.01); ret_a.append(-0.02); ret_a.append(0.03); ret_a.append(0.005)
    ret_b.append(0.01); ret_b.append(-0.02); ret_b.append(0.03); ret_b.append(0.005)
    var sci_same = sharpe_diff_bootstrap_ci(ret_a, ret_b, 200, 0.05, 11)
    if sci_same.lo == 0.0 and sci_same.hi == 0.0 and sci_same.point == 0.0:
        passed += 1
        print("  ✅ model_compare::sharpe_diff_bootstrap_ci identical → (0,0,0)")
    else:
        failed += 1
        print("  ❌ model_compare::sharpe_diff_bootstrap_ci identical → got", sci_same.lo, sci_same.hi, sci_same.point)

    # Hand-computed point: a=[1,3] → mean 2, pop std 1 → Sharpe 2;
    # b=[0,2] → mean 1, pop std 1 → Sharpe 1; point = 1.0 exactly.
    # Every bootstrap replicate is one of {both pairs → diff 1, degenerate → 0}.
    var s_a = List[Float64]()
    var s_b = List[Float64]()
    s_a.append(1.0); s_a.append(3.0)
    s_b.append(0.0); s_b.append(2.0)
    var sci = sharpe_diff_bootstrap_ci(s_a, s_b, 300, 0.05, 5)
    var bounds_ok = (sci.lo == 0.0 or sci.lo == 1.0) and (sci.hi == 0.0 or sci.hi == 1.0) and sci.lo <= sci.hi
    if close(sci.point, 1.0, 1e-12) and bounds_ok:
        passed += 1
        print("  ✅ model_compare::sharpe_diff_bootstrap_ci known point 1.0, bounds in {0,1}")
    else:
        failed += 1
        print("  ❌ model_compare::sharpe_diff_bootstrap_ci → expected point 1.0, got", sci.point, "bounds", sci.lo, sci.hi)

    # Edge: constant (zero-variance) returns → Sharpe defined as 0 → all zeros.
    var flat_a = List[Float64]()
    var flat_b = List[Float64]()
    for _ in range(5):
        flat_a.append(0.02)
        flat_b.append(0.01)
    var sci_flat = sharpe_diff_bootstrap_ci(flat_a, flat_b, 100, 0.05, 8)
    if sci_flat.lo == 0.0 and sci_flat.hi == 0.0 and sci_flat.point == 0.0:
        passed += 1
        print("  ✅ model_compare::sharpe_diff_bootstrap_ci zero-variance → (0,0,0)")
    else:
        failed += 1
        print("  ❌ model_compare::sharpe_diff_bootstrap_ci zero-variance → got", sci_flat.lo, sci_flat.hi, sci_flat.point)

    # Determinism: same seed twice → identical CI.
    var sci_d1 = sharpe_diff_bootstrap_ci(ret_a, s_b, 250, 0.10, 123)
    var sci_d2 = sharpe_diff_bootstrap_ci(ret_a, s_b, 250, 0.10, 123)
    if sci_d1.lo == sci_d2.lo and sci_d1.hi == sci_d2.hi and sci_d1.point == sci_d2.point:
        passed += 1
        print("  ✅ model_compare::sharpe_diff_bootstrap_ci deterministic seed")
    else:
        failed += 1
        print("  ❌ model_compare::sharpe_diff_bootstrap_ci determinism → r1(", sci_d1.lo, sci_d1.hi, ") r2(", sci_d2.lo, sci_d2.hi, ")")

    # Edge: empty input → (0,0,0).
    var sci_empty = sharpe_diff_bootstrap_ci(empty, empty, 100, 0.05, 2)
    if sci_empty.lo == 0.0 and sci_empty.hi == 0.0 and sci_empty.point == 0.0:
        passed += 1
        print("  ✅ model_compare::sharpe_diff_bootstrap_ci empty → (0,0,0)")
    else:
        failed += 1
        print("  ❌ model_compare::sharpe_diff_bootstrap_ci empty → got", sci_empty.lo, sci_empty.hi, sci_empty.point)

    print("  [model_compare] Passed:", passed, "Failed:", failed)
