"""Tests for Wave 43 — Counting Bloom Filter, A/B Testing, Extended Matrix Ops."""

from bloom_counting import (
    CountingBloom,
    cb_create,
    cb_add,
    cb_remove,
    cb_contains,
    cb_count_estimate,
    cb_hash,
    cb_false_positive_rate,
    cb_optimal_hashes,
    cb_reset,
)
from ab_testing import (
    sample_size_proportion,
    z_test_proportions,
    confidence_interval_proportion,
    relative_uplift,
    is_significant,
    power_analysis,
    mde,
    sequential_test,
    epsilon_greedy_select,
    ucb1_select,
)
from matrix_ops import (
    kronecker_product,
    hadamard_product,
    matrix_power,
    outer_product,
    matrix_exp_approx,
    vec,
    unvec,
    matrix_norm_1,
    matrix_norm_inf,
    commutator,
    is_orthogonal,
    gram_schmidt,
)
from std.math import abs as fabs, sqrt


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


fn _assert_eq(a: Int, b: Int, msg: String) raises:
    if a != b:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Helper builders ───────────────────────────────────────────────────────────

fn _flist1(a: Float64) -> List[Float64]:
    var v = List[Float64]()
    v.append(a)
    return v^

fn _flist2(a: Float64, b: Float64) -> List[Float64]:
    var v = List[Float64]()
    v.append(a)
    v.append(b)
    return v^

fn _flist3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var v = List[Float64]()
    v.append(a)
    v.append(b)
    v.append(c)
    return v^

fn _ilist2(a: Int, b: Int) -> List[Int]:
    var v = List[Int]()
    v.append(a)
    v.append(b)
    return v^

fn _ilist3(a: Int, b: Int, c: Int) -> List[Int]:
    var v = List[Int]()
    v.append(a)
    v.append(b)
    v.append(c)
    return v^

fn _mat2x2(a: Float64, b: Float64, c: Float64, d: Float64) -> List[List[Float64]]:
    var m = List[List[Float64]]()
    m.append(_flist2(a, b))
    m.append(_flist2(c, d))
    return m^

fn _identity2() -> List[List[Float64]]:
    return _mat2x2(1.0, 0.0, 0.0, 1.0)

fn _zeros2() -> List[List[Float64]]:
    return _mat2x2(0.0, 0.0, 0.0, 0.0)


# ── Counting Bloom Filter Tests ──────────────────────────────────────────────

fn test_cb_create() raises:
    var bloom = cb_create(100, 3)
    _assert_eq(bloom.size, 100, "cb_create size")                          # 1
    _assert_eq(bloom.n_hashes, 3, "cb_create n_hashes")                    # 2
    _assert_eq(len(bloom.counters), 100, "cb_create counters len")         # 3
    # All counters should be 0
    var all_zero = True
    for i in range(100):
        if bloom.counters[i] != 0:
            all_zero = False
    _assert(all_zero, "cb_create all counters zero")                       # 4

fn test_cb_add_contains() raises:
    var bloom = cb_create(1000, 5)
    cb_add(bloom, 42)
    _assert(cb_contains(bloom, 42), "cb_contains after add")               # 5
    cb_add(bloom, 99)
    _assert(cb_contains(bloom, 99), "cb_contains 99 after add")            # 6
    cb_add(bloom, 12345)
    _assert(cb_contains(bloom, 12345), "cb_contains 12345")                # 7

fn test_cb_not_contains() raises:
    var bloom = cb_create(10000, 5)
    cb_add(bloom, 1)
    cb_add(bloom, 2)
    cb_add(bloom, 3)
    # Items never added — with large filter, FP should be very rare
    var fps = 0
    for i in range(1000, 1100):
        if cb_contains(bloom, i):
            fps += 1
    _assert(fps < 20, "cb_contains FP rate low")                           # 8

fn test_cb_remove() raises:
    var bloom = cb_create(1000, 3)
    cb_add(bloom, 50)
    _assert(cb_contains(bloom, 50), "contains before remove")              # 9
    cb_remove(bloom, 50)
    _assert(not cb_contains(bloom, 50), "not contains after remove")       # 10

fn test_cb_remove_no_underflow() raises:
    var bloom = cb_create(100, 3)
    # Remove item that was never added — counters should stay at 0
    cb_remove(bloom, 999)
    var all_zero = True
    for i in range(100):
        if bloom.counters[i] != 0:
            all_zero = False
    _assert(all_zero, "cb_remove no underflow")                            # 11

fn test_cb_count_estimate() raises:
    var bloom = cb_create(10000, 4)
    cb_add(bloom, 7)
    cb_add(bloom, 7)
    cb_add(bloom, 7)
    var est = cb_count_estimate(bloom, 7)
    _assert_eq(est, 3, "cb_count_estimate after 3 adds")                   # 12
    cb_add(bloom, 7)
    cb_add(bloom, 7)
    est = cb_count_estimate(bloom, 7)
    _assert_eq(est, 5, "cb_count_estimate after 5 adds")                   # 13

fn test_cb_count_estimate_removed() raises:
    var bloom = cb_create(10000, 4)
    cb_add(bloom, 10)
    cb_add(bloom, 10)
    cb_add(bloom, 10)
    cb_remove(bloom, 10)
    var est = cb_count_estimate(bloom, 10)
    _assert_eq(est, 2, "cb_count_estimate after remove")                   # 14

fn test_cb_false_positive_rate() raises:
    var fpr = cb_false_positive_rate(1000, 3, 10)
    _assert(fpr > 0.0, "cb_fpr > 0")                                      # 15
    _assert(fpr < 1.0, "cb_fpr < 1")                                      # 16
    # With 0 items, compute theoretically
    var fpr0 = cb_false_positive_rate(1000, 3, 0)
    _assert_close(fpr0, 0.0, 1e-10, "cb_fpr with 0 items")                # 17
    # More items => higher FPR
    var fpr_high = cb_false_positive_rate(100, 3, 100)
    _assert(fpr_high > fpr, "more items => higher fpr")                    # 18

fn test_cb_optimal_hashes() raises:
    var k = cb_optimal_hashes(1000, 100)
    _assert(k > 0, "optimal_hashes > 0")                                   # 19
    _assert(k < 100, "optimal_hashes reasonable")                          # 20
    # For m/n=10, optimal k ≈ 10*ln(2) ≈ 6.93 → 6
    _assert(k >= 5 and k <= 8, "optimal_hashes ~7 for m/n=10")            # 21

fn test_cb_hash() raises:
    var h1 = cb_hash(42, 1, 100)
    var h2 = cb_hash(42, 2, 100)
    _assert(h1 >= 0 and h1 < 100, "cb_hash in range")                     # 22
    _assert(h2 >= 0 and h2 < 100, "cb_hash in range 2")                   # 23
    # Different seeds should (usually) give different results
    # (not guaranteed but very likely for size=100)

fn test_cb_reset() raises:
    var bloom = cb_create(100, 3)
    cb_add(bloom, 1)
    cb_add(bloom, 2)
    cb_add(bloom, 3)
    cb_reset(bloom)
    var all_zero = True
    for i in range(100):
        if bloom.counters[i] != 0:
            all_zero = False
    _assert(all_zero, "cb_reset all counters zero")                        # 24
    _assert(not cb_contains(bloom, 1), "not contains after reset")         # 25


# ── A/B Testing Tests ────────────────────────────────────────────────────────

fn test_sample_size() raises:
    var n = sample_size_proportion(0.1, 0.12)
    _assert(n > 0, "sample_size positive")                                 # 26
    _assert(n > 100, "sample_size > 100 for small effect")                 # 27
    # Larger effect needs fewer samples
    var n2 = sample_size_proportion(0.1, 0.2)
    _assert(n2 < n, "larger effect => smaller sample")                     # 28

fn test_z_test_proportions_significant() raises:
    # Clear winner: A=500/1000, B=600/1000
    var result = z_test_proportions(500, 1000, 600, 1000)
    var z_stat = result[0]
    var p_val = result[1]
    _assert(fabs(z_stat) > 1.96, "z_test significant z")                   # 29
    _assert(p_val < 0.05, "z_test significant p")                          # 30

fn test_z_test_proportions_not_significant() raises:
    # Close: A=100/1000, B=102/1000
    var result = z_test_proportions(100, 1000, 102, 1000)
    var p_val = result[1]
    _assert(p_val > 0.05, "z_test not significant")                        # 31

fn test_confidence_interval() raises:
    var ci = confidence_interval_proportion(50, 100)
    var p_hat = 0.5
    _assert(ci[0] < p_hat, "CI lower < proportion")                       # 32
    _assert(ci[1] > p_hat, "CI upper > proportion")                       # 33
    _assert(ci[0] > 0.0, "CI lower > 0")                                  # 34
    _assert(ci[1] < 1.0, "CI upper < 1")                                  # 35

fn test_relative_uplift() raises:
    var u = relative_uplift(0.1, 0.12)
    _assert_close(u, 0.2, 0.01, "relative_uplift 0.1->0.12")             # 36
    var u2 = relative_uplift(0.5, 0.6)
    _assert_close(u2, 0.2, 0.01, "relative_uplift 0.5->0.6")             # 37

fn test_is_significant() raises:
    _assert(is_significant(0.01), "is_significant 0.01")                   # 38
    _assert(is_significant(0.001), "is_significant 0.001")                 # 39
    _assert(not is_significant(0.1), "not is_significant 0.1")             # 40
    _assert(not is_significant(0.06), "not is_significant 0.06")           # 41

fn test_power_analysis() raises:
    var pwr = power_analysis(0.5, 100)
    _assert(pwr > 0.0, "power > 0")                                       # 42
    _assert(pwr < 1.0, "power < 1")                                       # 43
    # Larger effect or larger n => more power
    var pwr2 = power_analysis(0.5, 500)
    _assert(pwr2 > pwr, "more n => more power")                           # 44

fn test_mde() raises:
    var effect = mde(1000, 0.1)
    _assert(effect > 0.0, "mde > 0")                                      # 45
    _assert(effect < 0.5, "mde reasonable")                                # 46

fn test_sequential_test() raises:
    # Very clear winner
    var r = sequential_test(100, 1000, 900, 1000)
    _assert(r == 1 or r == 2, "sequential decides")                        # 47
    # Very similar
    var r2 = sequential_test(500, 1000, 501, 1000)
    _assert(r2 == 0, "sequential continues for close rates")               # 48

fn test_epsilon_greedy() raises:
    var rewards = _flist3(10.0, 5.0, 1.0)
    var counts = _ilist3(10, 10, 10)
    # With epsilon=0.0, always exploit (best arm = 0)
    var arm = epsilon_greedy_select(rewards, counts, 0.0)
    _assert_eq(arm, 0, "epsilon_greedy exploits best arm")                 # 49
    # With counts=0 for one arm, should prefer it
    var counts2 = _ilist3(10, 0, 10)
    arm = epsilon_greedy_select(rewards, counts2, 0.0)
    _assert_eq(arm, 1, "epsilon_greedy prefers unexplored")                # 50

fn test_ucb1() raises:
    var rewards = _flist3(5.0, 3.0, 1.0)
    var counts = _ilist3(10, 10, 0)
    # Should explore arm 2 (count=0)
    var arm = ucb1_select(rewards, counts, 20)
    _assert_eq(arm, 2, "ucb1 explores unvisited arm")                      # 51
    # All visited — should pick best or explore
    var counts2 = _ilist3(10, 10, 10)
    arm = ucb1_select(rewards, counts2, 30)
    _assert(arm >= 0 and arm < 3, "ucb1 valid arm index")                  # 52


# ── Matrix Ops Tests ──────────────────────────────────────────────────────────

fn test_kronecker_identity() raises:
    var I2 = _identity2()
    var K = kronecker_product(I2, I2)
    # 2×2 ⊗ 2×2 = 4×4 identity
    _assert_eq(len(K), 4, "kronecker 4 rows")                             # 53
    _assert_eq(len(K[0]), 4, "kronecker 4 cols")                          # 54
    _assert_close(K[0][0], 1.0, 1e-10, "kron I⊗I [0,0]=1")              # 55
    _assert_close(K[1][1], 1.0, 1e-10, "kron I⊗I [1,1]=1")              # 56
    _assert_close(K[2][2], 1.0, 1e-10, "kron I⊗I [2,2]=1")              # 57
    _assert_close(K[3][3], 1.0, 1e-10, "kron I⊗I [3,3]=1")              # 58
    _assert_close(K[0][1], 0.0, 1e-10, "kron I⊗I [0,1]=0")              # 59

fn test_hadamard_with_ones() raises:
    var A = _mat2x2(3.0, 5.0, 7.0, 11.0)
    var ones = _mat2x2(1.0, 1.0, 1.0, 1.0)
    var H = hadamard_product(A, ones)
    _assert_close(H[0][0], 3.0, 1e-10, "hadamard ones [0,0]")            # 60
    _assert_close(H[0][1], 5.0, 1e-10, "hadamard ones [0,1]")            # 61
    _assert_close(H[1][0], 7.0, 1e-10, "hadamard ones [1,0]")            # 62
    _assert_close(H[1][1], 11.0, 1e-10, "hadamard ones [1,1]")           # 63

fn test_matrix_power_identity() raises:
    var I2 = _identity2()
    var I_pow = matrix_power(I2, 5)
    _assert_close(I_pow[0][0], 1.0, 1e-10, "I^5 [0,0]=1")               # 64
    _assert_close(I_pow[0][1], 0.0, 1e-10, "I^5 [0,1]=0")               # 65
    _assert_close(I_pow[1][0], 0.0, 1e-10, "I^5 [1,0]=0")               # 66
    _assert_close(I_pow[1][1], 1.0, 1e-10, "I^5 [1,1]=1")               # 67

fn test_matrix_power_squared() raises:
    var A = _mat2x2(1.0, 2.0, 3.0, 4.0)
    var A2 = matrix_power(A, 2)
    # A^2 = [[1*1+2*3, 1*2+2*4], [3*1+4*3, 3*2+4*4]] = [[7,10],[15,22]]
    _assert_close(A2[0][0], 7.0, 1e-10, "A^2 [0,0]=7")                  # 68
    _assert_close(A2[0][1], 10.0, 1e-10, "A^2 [0,1]=10")                # 69
    _assert_close(A2[1][0], 15.0, 1e-10, "A^2 [1,0]=15")                # 70
    _assert_close(A2[1][1], 22.0, 1e-10, "A^2 [1,1]=22")                # 71

fn test_outer_product() raises:
    var a = _flist2(1.0, 2.0)
    var b = _flist2(3.0, 4.0)
    var O = outer_product(a, b)
    _assert_close(O[0][0], 3.0, 1e-10, "outer [0,0]=3")                  # 72
    _assert_close(O[0][1], 4.0, 1e-10, "outer [0,1]=4")                  # 73
    _assert_close(O[1][0], 6.0, 1e-10, "outer [1,0]=6")                  # 74
    _assert_close(O[1][1], 8.0, 1e-10, "outer [1,1]=8")                  # 75

fn test_vec_unvec_roundtrip() raises:
    var A = _mat2x2(1.0, 2.0, 3.0, 4.0)
    var v = vec(A)
    # Column-major: [1,3,2,4]
    _assert_close(v[0], 1.0, 1e-10, "vec col-major [0]=1")               # 76
    _assert_close(v[1], 3.0, 1e-10, "vec col-major [1]=3")               # 77
    var B = unvec(v, 2, 2)
    _assert_close(B[0][0], 1.0, 1e-10, "unvec roundtrip [0,0]")          # 78
    _assert_close(B[0][1], 2.0, 1e-10, "unvec roundtrip [0,1]")          # 79
    _assert_close(B[1][0], 3.0, 1e-10, "unvec roundtrip [1,0]")          # 80
    _assert_close(B[1][1], 4.0, 1e-10, "unvec roundtrip [1,1]")          # 81

fn test_matrix_norm_1_identity() raises:
    var I2 = _identity2()
    var n1 = matrix_norm_1(I2)
    _assert_close(n1, 1.0, 1e-10, "norm_1 identity = 1")                 # 82

fn test_matrix_norm_inf() raises:
    var A = _mat2x2(1.0, -2.0, 3.0, 4.0)
    var ni = matrix_norm_inf(A)
    # Row sums: |1|+|-2|=3, |3|+|4|=7 => max=7
    _assert_close(ni, 7.0, 1e-10, "norm_inf = 7")                        # 83

fn test_matrix_norm_1_general() raises:
    var A = _mat2x2(1.0, -2.0, 3.0, 4.0)
    var n1 = matrix_norm_1(A)
    # Column sums: |1|+|3|=4, |-2|+|4|=6 => max=6
    _assert_close(n1, 6.0, 1e-10, "norm_1 = 6")                          # 84

fn test_commutator_self() raises:
    var A = _mat2x2(1.0, 2.0, 3.0, 4.0)
    var C = commutator(A, A)
    # [A,A] = 0
    _assert_close(C[0][0], 0.0, 1e-10, "[A,A] [0,0]=0")                 # 85
    _assert_close(C[0][1], 0.0, 1e-10, "[A,A] [0,1]=0")                 # 86
    _assert_close(C[1][0], 0.0, 1e-10, "[A,A] [1,0]=0")                 # 87
    _assert_close(C[1][1], 0.0, 1e-10, "[A,A] [1,1]=0")                 # 88

fn test_is_orthogonal_identity() raises:
    var I2 = _identity2()
    _assert(is_orthogonal(I2), "identity is orthogonal")                   # 89

fn test_is_orthogonal_non_orthogonal() raises:
    var A = _mat2x2(1.0, 2.0, 3.0, 4.0)
    _assert(not is_orthogonal(A), "non-orthogonal matrix")                 # 90

fn test_gram_schmidt() raises:
    var vecs = List[List[Float64]]()
    vecs.append(_flist3(1.0, 1.0, 0.0))
    vecs.append(_flist3(1.0, 0.0, 1.0))
    vecs.append(_flist3(0.0, 1.0, 1.0))
    var ortho = gram_schmidt(vecs)
    _assert_eq(len(ortho), 3, "gram_schmidt 3 vectors")                   # 91
    # Check orthogonality: dot products should be ~0
    var dot01: Float64 = 0.0
    var dot02: Float64 = 0.0
    var dot12: Float64 = 0.0
    for d in range(3):
        dot01 += ortho[0][d] * ortho[1][d]
        dot02 += ortho[0][d] * ortho[2][d]
        dot12 += ortho[1][d] * ortho[2][d]
    _assert_close(dot01, 0.0, 1e-10, "gram_schmidt ortho 0·1")           # 92
    _assert_close(dot02, 0.0, 1e-10, "gram_schmidt ortho 0·2")           # 93
    _assert_close(dot12, 0.0, 1e-10, "gram_schmidt ortho 1·2")           # 94
    # Check unit length
    var norm0: Float64 = 0.0
    var norm1: Float64 = 0.0
    for d in range(3):
        norm0 += ortho[0][d] * ortho[0][d]
        norm1 += ortho[1][d] * ortho[1][d]
    _assert_close(norm0, 1.0, 1e-10, "gram_schmidt unit vec 0")          # 95
    _assert_close(norm1, 1.0, 1e-10, "gram_schmidt unit vec 1")          # 96

fn test_matrix_exp_identity() raises:
    # e^0 = I
    var Z = _zeros2()
    var E = matrix_exp_approx(Z)
    _assert_close(E[0][0], 1.0, 1e-8, "exp(0) [0,0]=1")                 # 97
    _assert_close(E[0][1], 0.0, 1e-8, "exp(0) [0,1]=0")                 # 98
    _assert_close(E[1][0], 0.0, 1e-8, "exp(0) [1,0]=0")                 # 99
    _assert_close(E[1][1], 1.0, 1e-8, "exp(0) [1,1]=1")                 # 100

fn test_matrix_power_zero() raises:
    var A = _mat2x2(5.0, 6.0, 7.0, 8.0)
    var A0 = matrix_power(A, 0)
    _assert_close(A0[0][0], 1.0, 1e-10, "A^0 = I [0,0]")               # 101
    _assert_close(A0[0][1], 0.0, 1e-10, "A^0 = I [0,1]")               # 102


# ── Main ──────────────────────────────────────────────────────────────────────

fn main() raises:
    # Counting Bloom tests
    test_cb_create()
    test_cb_add_contains()
    test_cb_not_contains()
    test_cb_remove()
    test_cb_remove_no_underflow()
    test_cb_count_estimate()
    test_cb_count_estimate_removed()
    test_cb_false_positive_rate()
    test_cb_optimal_hashes()
    test_cb_hash()
    test_cb_reset()

    # A/B Testing tests
    test_sample_size()
    test_z_test_proportions_significant()
    test_z_test_proportions_not_significant()
    test_confidence_interval()
    test_relative_uplift()
    test_is_significant()
    test_power_analysis()
    test_mde()
    test_sequential_test()
    test_epsilon_greedy()
    test_ucb1()

    # Matrix ops tests
    test_kronecker_identity()
    test_hadamard_with_ones()
    test_matrix_power_identity()
    test_matrix_power_squared()
    test_outer_product()
    test_vec_unvec_roundtrip()
    test_matrix_norm_1_identity()
    test_matrix_norm_inf()
    test_matrix_norm_1_general()
    test_commutator_self()
    test_is_orthogonal_identity()
    test_is_orthogonal_non_orthogonal()
    test_gram_schmidt()
    test_matrix_exp_identity()
    test_matrix_power_zero()

    print("✅ Wave 43: all 102 assertions passed.")
