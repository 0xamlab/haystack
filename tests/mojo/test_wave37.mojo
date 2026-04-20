"""Tests for Wave 37 — Polynomial Operations, Voting Methods, Bootstrap Statistics."""

from polynomial import (
    poly_eval,
    poly_add,
    poly_multiply,
    poly_derivative,
    poly_integral,
    poly_degree,
    quadratic_roots,
    poly_scale,
    poly_compose,
    poly_from_roots,
)
from election import (
    plurality,
    borda_count,
    borda_winner,
    condorcet_winner,
    pairwise_matrix,
    instant_runoff,
    approval_voting,
    copeland_scores,
)
from stats_bootstrap import (
    bootstrap_replicate,
    bootstrap_mean_ci,
    bootstrap_std_ci,
    bootstrap_median_ci,
    bootstrap_bias,
    bootstrap_se,
    bootstrap_test,
    jackknife_mean,
    jackknife_se,
    bca_correction,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Polynomial tests ─────────────────────────────────────────────────────────


fn test_polynomial() raises:
    print("── Polynomial tests ──")
    var passed = 0

    # 1. poly_eval([1,2,3], 2.0) = 1 + 2*2 + 3*4 = 17
    var c1 = List[Float64]()
    c1.append(1.0)
    c1.append(2.0)
    c1.append(3.0)
    _assert_close(poly_eval(c1, 2.0), 17.0, 1e-9, "poly_eval [1,2,3] at 2 = 17")
    passed += 1

    # 2. poly_eval([5], 100.0) = 5 (constant)
    var c2 = List[Float64]()
    c2.append(5.0)
    _assert_close(poly_eval(c2, 100.0), 5.0, 1e-9, "poly_eval [5] at 100 = 5")
    passed += 1

    # 3. poly_eval empty = 0
    var c_empty = List[Float64]()
    _assert_close(poly_eval(c_empty, 42.0), 0.0, 1e-9, "poly_eval empty = 0")
    passed += 1

    # 4. poly_add([1,2], [3,4]) = [4,6]
    var a1 = List[Float64]()
    a1.append(1.0)
    a1.append(2.0)
    var b1 = List[Float64]()
    b1.append(3.0)
    b1.append(4.0)
    var sum1 = poly_add(a1, b1)
    _assert_close(sum1[0], 4.0, 1e-9, "poly_add [1,2]+[3,4] idx0 = 4")
    passed += 1

    # 5.
    _assert_close(sum1[1], 6.0, 1e-9, "poly_add [1,2]+[3,4] idx1 = 6")
    passed += 1

    # 6. poly_add different lengths
    var a2 = List[Float64]()
    a2.append(1.0)
    var b2 = List[Float64]()
    b2.append(2.0)
    b2.append(3.0)
    var sum2 = poly_add(a2, b2)
    _assert(len(sum2) == 2, "poly_add diff lengths has 2 terms")
    passed += 1

    # 7. poly_multiply([1,1], [1,1]) = [1,2,1]  (x+1)² = x²+2x+1
    var m1 = List[Float64]()
    m1.append(1.0)
    m1.append(1.0)
    var m2 = List[Float64]()
    m2.append(1.0)
    m2.append(1.0)
    var prod = poly_multiply(m1, m2)
    _assert(len(prod) == 3, "poly_multiply [1,1]*[1,1] has 3 terms")
    passed += 1

    # 8.
    _assert_close(prod[0], 1.0, 1e-9, "poly_multiply [1,1]² idx0 = 1")
    passed += 1

    # 9.
    _assert_close(prod[1], 2.0, 1e-9, "poly_multiply [1,1]² idx1 = 2")
    passed += 1

    # 10.
    _assert_close(prod[2], 1.0, 1e-9, "poly_multiply [1,1]² idx2 = 1")
    passed += 1

    # 11. poly_derivative([3, 2, 1]) = [2, 2]  (d/dx of 3+2x+x² = 2+2x)
    var d1 = List[Float64]()
    d1.append(3.0)
    d1.append(2.0)
    d1.append(1.0)
    var deriv = poly_derivative(d1)
    _assert_close(deriv[0], 2.0, 1e-9, "poly_derivative [3,2,1] idx0 = 2")
    passed += 1

    # 12.
    _assert_close(deriv[1], 2.0, 1e-9, "poly_derivative [3,2,1] idx1 = 2")
    passed += 1

    # 13. poly_integral([2, 2]) = [0, 2, 1]  (∫2+2x dx = 2x+x²)
    var int_c = List[Float64]()
    int_c.append(2.0)
    int_c.append(2.0)
    var integ = poly_integral(int_c)
    _assert_close(integ[0], 0.0, 1e-9, "poly_integral [2,2] C=0 idx0 = 0")
    passed += 1

    # 14.
    _assert_close(integ[1], 2.0, 1e-9, "poly_integral [2,2] idx1 = 2")
    passed += 1

    # 15.
    _assert_close(integ[2], 1.0, 1e-9, "poly_integral [2,2] idx2 = 1")
    passed += 1

    # 16. poly_degree([1,0,3]) = 2
    var deg_c = List[Float64]()
    deg_c.append(1.0)
    deg_c.append(0.0)
    deg_c.append(3.0)
    _assert(poly_degree(deg_c) == 2, "poly_degree [1,0,3] = 2")
    passed += 1

    # 17. poly_degree([5]) = 0
    var deg_c2 = List[Float64]()
    deg_c2.append(5.0)
    _assert(poly_degree(deg_c2) == 0, "poly_degree [5] = 0")
    passed += 1

    # 18. quadratic_roots(1, -3, 2) = roots of x²-3x+2 = (x-1)(x-2)
    var roots = quadratic_roots(1.0, -3.0, 2.0)
    _assert(len(roots) == 2, "quadratic_roots x²-3x+2 has 2 roots")
    passed += 1

    # 19. roots are 1 and 2
    var r_min = roots[0]
    var r_max = roots[1]
    if r_min > r_max:
        var tmp = r_min
        r_min = r_max
        r_max = tmp
    _assert_close(r_min, 1.0, 1e-9, "quadratic_roots smaller root = 1")
    passed += 1

    # 20.
    _assert_close(r_max, 2.0, 1e-9, "quadratic_roots larger root = 2")
    passed += 1

    # 21. quadratic_roots with no real roots
    var no_roots = quadratic_roots(1.0, 0.0, 1.0)  # x²+1=0
    _assert(len(no_roots) == 0, "quadratic_roots x²+1 has no real roots")
    passed += 1

    # 22. poly_scale([1,2,3], 2.0) = [2,4,6]
    var sc = poly_scale(c1, 2.0)
    _assert_close(sc[0], 2.0, 1e-9, "poly_scale [1,2,3]*2 idx0 = 2")
    passed += 1

    # 23.
    _assert_close(sc[1], 4.0, 1e-9, "poly_scale [1,2,3]*2 idx1 = 4")
    passed += 1

    # 24.
    _assert_close(sc[2], 6.0, 1e-9, "poly_scale [1,2,3]*2 idx2 = 6")
    passed += 1

    # 25. poly_from_roots([1,2]) evaluates to 0 at x=1 and x=2
    var fr_roots = List[Float64]()
    fr_roots.append(1.0)
    fr_roots.append(2.0)
    var fr_poly = poly_from_roots(fr_roots)
    _assert_close(poly_eval(fr_poly, 1.0), 0.0, 1e-9, "poly_from_roots([1,2]) at x=1 = 0")
    passed += 1

    # 26.
    _assert_close(poly_eval(fr_poly, 2.0), 0.0, 1e-9, "poly_from_roots([1,2]) at x=2 = 0")
    passed += 1

    # 27. poly_compose: f(x)=x+1=[1,1], g(x)=2x=[0,2] → f(g(x))=2x+1=[1,2]
    var f_comp = List[Float64]()
    f_comp.append(1.0)
    f_comp.append(1.0)
    var g_comp = List[Float64]()
    g_comp.append(0.0)
    g_comp.append(2.0)
    var comp = poly_compose(f_comp, g_comp)
    _assert_close(comp[0], 1.0, 1e-9, "poly_compose f(g(x)) idx0 = 1")
    passed += 1

    # 28.
    _assert_close(comp[1], 2.0, 1e-9, "poly_compose f(g(x)) idx1 = 2")
    passed += 1

    print("  ✓ Polynomial:", passed, "passed")


# ── Election tests ───────────────────────────────────────────────────────────


fn test_election() raises:
    print("── Election tests ──")
    var passed = 0

    # Setup: 5 ballots, 3 candidates (0, 1, 2)
    # Candidate 0 wins plurality (3 first-place votes)
    var ballots = List[List[Int]]()
    var b0 = List[Int]()
    b0.append(0)
    b0.append(1)
    b0.append(2)
    ballots.append(b0^)
    var b1 = List[Int]()
    b1.append(0)
    b1.append(2)
    b1.append(1)
    ballots.append(b1^)
    var b2 = List[Int]()
    b2.append(0)
    b2.append(1)
    b2.append(2)
    ballots.append(b2^)
    var b3 = List[Int]()
    b3.append(1)
    b3.append(2)
    b3.append(0)
    ballots.append(b3^)
    var b4 = List[Int]()
    b4.append(2)
    b4.append(1)
    b4.append(0)
    ballots.append(b4^)

    # 29. plurality — candidate 0 has 3 first-place votes
    _assert(plurality(ballots, 3) == 0, "plurality winner = 0")
    passed += 1

    # 30. borda_count — candidate 0: 3*2+0+0=6, candidate 1: 1*2+2*1+0=4, candidate 2: 1*2+1*1+1*0=3
    # Actually: borda scores for 3 candidates: first=2, second=1, third=0
    # c0: ballot0=2, ballot1=2, ballot2=2, ballot3=0, ballot4=0 => 6
    # c1: ballot0=1, ballot1=0, ballot2=1, ballot3=2, ballot4=1 => 5
    # c2: ballot0=0, ballot1=1, ballot2=0, ballot3=1, ballot4=2 => 4
    var borda = borda_count(ballots, 3)
    _assert_close(borda[0], 6.0, 1e-9, "borda_count c0 = 6")
    passed += 1

    # 31.
    _assert_close(borda[1], 5.0, 1e-9, "borda_count c1 = 5")
    passed += 1

    # 32.
    _assert_close(borda[2], 4.0, 1e-9, "borda_count c2 = 4")
    passed += 1

    # 33. borda_winner = 0
    _assert(borda_winner(ballots, 3) == 0, "borda_winner = 0")
    passed += 1

    # 34. condorcet_winner — c0 beats c1 (3 out of 5), c0 beats c2 (3 out of 5)
    _assert(condorcet_winner(ballots, 3) == 0, "condorcet_winner = 0")
    passed += 1

    # 35. condorcet_winner returns -1 with Condorcet cycle
    # A>B, B>C, C>A
    var cycle_ballots = List[List[Int]]()
    var cb0 = List[Int]()
    cb0.append(0)
    cb0.append(1)
    cb0.append(2)
    cycle_ballots.append(cb0^)
    var cb1 = List[Int]()
    cb1.append(1)
    cb1.append(2)
    cb1.append(0)
    cycle_ballots.append(cb1^)
    var cb2 = List[Int]()
    cb2.append(2)
    cb2.append(0)
    cb2.append(1)
    cycle_ballots.append(cb2^)
    _assert(condorcet_winner(cycle_ballots, 3) == -1, "condorcet_winner cycle = -1")
    passed += 1

    # 36. pairwise_matrix — [i][j] + [j][i] = n_ballots for all i != j
    var pw = pairwise_matrix(ballots, 3)
    var pw0 = pw[0].copy()
    var pw1 = pw[1].copy()
    var pw2 = pw[2].copy()
    _assert(pw0[1] + pw1[0] == 5, "pairwise [0][1] + [1][0] = 5")
    passed += 1

    # 37.
    _assert(pw0[2] + pw2[0] == 5, "pairwise [0][2] + [2][0] = 5")
    passed += 1

    # 38.
    _assert(pw1[2] + pw2[1] == 5, "pairwise [1][2] + [2][1] = 5")
    passed += 1

    # 39. instant_runoff — candidate 0 has majority (3/5), wins immediately
    _assert(instant_runoff(ballots, 3) == 0, "IRV winner = 0")
    passed += 1

    # 40. approval_voting — each ballot approves first 2
    var approvals = List[List[Int]]()
    var ap0 = List[Int]()
    ap0.append(0)
    ap0.append(1)
    approvals.append(ap0^)
    var ap1 = List[Int]()
    ap1.append(0)
    ap1.append(2)
    approvals.append(ap1^)
    var ap2 = List[Int]()
    ap2.append(1)
    ap2.append(2)
    approvals.append(ap2^)
    var ap3 = List[Int]()
    ap3.append(0)
    ap3.append(1)
    approvals.append(ap3^)
    # c0: 3 approvals, c1: 3 approvals, c2: 2 approvals
    # c0 wins (first with max)
    var av_winner = approval_voting(approvals, 3)
    _assert(av_winner == 0 or av_winner == 1, "approval_voting winner is 0 or 1 (tied)")
    passed += 1

    # 41. copeland_scores — with original ballots
    var cop = copeland_scores(ballots, 3)
    # c0 beats c1 (3>2) → +1, c0 beats c2 (3>2) → +1 → c0=2
    # c1 beats c2 (3>2) → +1 → c1=1
    # c2 = 0
    _assert_close(cop[0], 2.0, 1e-9, "copeland c0 = 2")
    passed += 1

    # 42.
    _assert_close(cop[1], 1.0, 1e-9, "copeland c1 = 1")
    passed += 1

    # 43.
    _assert_close(cop[2], 0.0, 1e-9, "copeland c2 = 0")
    passed += 1

    # 44. copeland with cycle — all scores equal
    var cop_cycle = copeland_scores(cycle_ballots, 3)
    _assert_close(cop_cycle[0], 1.0, 1e-9, "copeland cycle c0 = 1")
    passed += 1

    # 45.
    _assert_close(cop_cycle[1], 1.0, 1e-9, "copeland cycle c1 = 1")
    passed += 1

    # 46.
    _assert_close(cop_cycle[2], 1.0, 1e-9, "copeland cycle c2 = 1")
    passed += 1

    print("  ✓ Election:", passed, "passed")


# ── Bootstrap tests ──────────────────────────────────────────────────────────


fn test_bootstrap() raises:
    print("── Bootstrap tests ──")
    var passed = 0

    # Symmetric data
    var data = List[Float64]()
    data.append(1.0)
    data.append(2.0)
    data.append(3.0)
    data.append(4.0)
    data.append(5.0)
    data.append(6.0)
    data.append(7.0)
    data.append(8.0)
    data.append(9.0)
    data.append(10.0)

    # 47. bootstrap_replicate — same length as data
    var rep = bootstrap_replicate(data)
    _assert(len(rep) == len(data), "bootstrap_replicate same length")
    passed += 1

    # 48. bootstrap_replicate values within data range
    var all_in_range = True
    for i in range(len(rep)):
        if rep[i] < 1.0 or rep[i] > 10.0:
            all_in_range = False
    _assert(all_in_range, "bootstrap_replicate values in [1,10]")
    passed += 1

    # 49. bootstrap_mean_ci — lower < mean < upper
    var ci = bootstrap_mean_ci(data, 500)
    var data_mean: Float64 = 5.5
    _assert(ci[0] < data_mean, "bootstrap_mean_ci lower < mean")
    passed += 1

    # 50.
    _assert(ci[1] > data_mean, "bootstrap_mean_ci upper > mean")
    passed += 1

    # 51. bootstrap_mean_ci — lower < upper
    _assert(ci[0] < ci[1], "bootstrap_mean_ci lower < upper")
    passed += 1

    # 52. bootstrap_std_ci — lower < upper
    var std_ci = bootstrap_std_ci(data, 500)
    _assert(std_ci[0] < std_ci[1], "bootstrap_std_ci lower < upper")
    passed += 1

    # 53. bootstrap_std_ci — both positive
    _assert(std_ci[0] > 0.0, "bootstrap_std_ci lower > 0")
    passed += 1

    # 54. bootstrap_median_ci — lower < upper
    var med_ci = bootstrap_median_ci(data, 500)
    _assert(med_ci[0] < med_ci[1], "bootstrap_median_ci lower < upper")
    passed += 1

    # 55. bootstrap_se — positive
    var se = bootstrap_se(data, 500)
    _assert(se > 0.0, "bootstrap_se positive")
    passed += 1

    # 56. bootstrap_bias — close to 0 for mean of symmetric data
    var bias = bootstrap_bias(data, 500, 0)
    _assert(fabs(bias) < 1.0, "bootstrap_bias mean of symmetric data close to 0")
    passed += 1

    # 57. bootstrap_test on identical groups → p > 0.05
    var data2 = List[Float64]()
    data2.append(1.0)
    data2.append(2.0)
    data2.append(3.0)
    data2.append(4.0)
    data2.append(5.0)
    data2.append(6.0)
    data2.append(7.0)
    data2.append(8.0)
    data2.append(9.0)
    data2.append(10.0)
    var p_val = bootstrap_test(data, data2, 500)
    _assert(p_val > 0.05, "bootstrap_test identical groups p > 0.05")
    passed += 1

    # 58. bootstrap_test on very different groups → p < 0.5
    var data_high = List[Float64]()
    data_high.append(100.0)
    data_high.append(101.0)
    data_high.append(102.0)
    data_high.append(103.0)
    data_high.append(104.0)
    var data_low = List[Float64]()
    data_low.append(1.0)
    data_low.append(2.0)
    data_low.append(3.0)
    data_low.append(4.0)
    data_low.append(5.0)
    var p_diff = bootstrap_test(data_high, data_low, 500)
    _assert(p_diff < 0.05, "bootstrap_test different groups p < 0.05")
    passed += 1

    # 59. jackknife_mean — n values (leave-one-out)
    var jk = jackknife_mean(data)
    _assert(len(jk) == 10, "jackknife_mean returns n values")
    passed += 1

    # 60. jackknife_mean — removing 1 shifts mean
    # Mean without 1.0 = (55-1)/9 = 6.0
    _assert_close(jk[0], 6.0, 1e-9, "jackknife_mean[0] = 6.0 (remove 1)")
    passed += 1

    # 61. jackknife_mean — removing 10 shifts mean
    # Mean without 10.0 = (55-10)/9 = 5.0
    _assert_close(jk[9], 5.0, 1e-9, "jackknife_mean[9] = 5.0 (remove 10)")
    passed += 1

    # 62. jackknife_se — positive
    var jk_se = jackknife_se(data)
    _assert(jk_se > 0.0, "jackknife_se positive")
    passed += 1

    # 63. bca_correction — lower < upper
    var bca = bca_correction(data, 500)
    _assert(bca[0] < bca[1], "bca_correction lower < upper")
    passed += 1

    # 64. bca_correction — CI contains true mean (likely)
    _assert(bca[0] < data_mean, "bca_correction lower < true mean")
    passed += 1

    # 65. bca_correction — upper bound reasonable
    _assert(bca[1] > data_mean, "bca_correction upper > true mean")
    passed += 1

    print("  ✓ Bootstrap:", passed, "passed")


# ── main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 37 Tests ===")
    test_polynomial()
    test_election()
    test_bootstrap()
    print("=== All Wave 37 tests passed ===")
