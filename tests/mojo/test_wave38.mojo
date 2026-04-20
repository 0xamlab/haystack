"""Tests for Wave 38 — String Distance Metrics, Data Transformations, Combinatorial Optimization."""

from string_distance import (
    damerau_levenshtein,
    soundex,
    edit_similarity,
    common_prefix_length,
    common_suffix_length,
    dice_coefficient,
    overlap_coefficient,
    bigrams,
    string_reverse,
    is_palindrome,
)
from transform import (
    log_transform,
    log1p_transform,
    box_cox,
    standardize,
    min_max_scale,
    robust_scale,
    quantile_transform,
    power_transform,
    clamp_values,
    rank_transform,
    abs_transform,
    reciprocal_transform,
)
from combinatorial import (
    knapsack_01,
    knapsack_01_value,
    tsp_greedy,
    tsp_tour_length,
    bin_packing_first_fit,
    bin_packing_first_fit_decreasing,
    assignment_greedy,
    max_subarray_sum,
    longest_increasing_subsequence,
    coin_change,
)
from std.math import abs as fabs, log


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── String Distance tests ────────────────────────────────────────────────────


fn test_string_distance() raises:
    print("── String Distance tests ──")
    var passed = 0

    # 1. damerau_levenshtein transposition
    _assert(damerau_levenshtein("cat", "cta") == 1, "dl cat/cta == 1")
    passed += 1

    # 2. damerau_levenshtein kitten/sitting
    _assert(damerau_levenshtein("kitten", "sitting") == 3, "dl kitten/sitting == 3")
    passed += 1

    # 3. damerau_levenshtein identical
    _assert(damerau_levenshtein("hello", "hello") == 0, "dl identical == 0")
    passed += 1

    # 4. damerau_levenshtein empty
    _assert(damerau_levenshtein("", "abc") == 3, "dl empty/abc == 3")
    passed += 1

    # 5. soundex Robert
    _assert(soundex("Robert") == "R163", "soundex Robert == R163")
    passed += 1

    # 6. soundex Rupert
    _assert(soundex("Rupert") == "R163", "soundex Rupert == R163")
    passed += 1

    # 7. soundex Ashcraft
    var sx = soundex("Ashcraft")
    _assert(sx == "A261", "soundex Ashcraft == A261, got " + sx)
    passed += 1

    # 8. edit_similarity identical
    _assert_close(edit_similarity("abc", "abc"), 1.0, 1e-9, "edit_sim abc/abc == 1.0")
    passed += 1

    # 9. edit_similarity different
    var es = edit_similarity("abc", "xyz")
    _assert(es >= 0.0 and es <= 1.0, "edit_sim range [0,1]")
    passed += 1

    # 10. edit_similarity empty
    _assert_close(edit_similarity("", ""), 1.0, 1e-9, "edit_sim empty == 1.0")
    passed += 1

    # 11. common_prefix_length
    _assert(common_prefix_length("hello", "help") == 3, "prefix hello/help == 3")
    passed += 1

    # 12. common_prefix_length no match
    _assert(common_prefix_length("abc", "xyz") == 0, "prefix abc/xyz == 0")
    passed += 1

    # 13. common_suffix_length
    _assert(common_suffix_length("testing", "running") == 3, "suffix testing/running == 3")
    passed += 1

    # 14. common_suffix_length
    _assert(common_suffix_length("abc", "xbc") == 2, "suffix abc/xbc == 2")
    passed += 1

    # 15. bigrams
    var bg = bigrams("abc")
    _assert(len(bg) == 2, "bigrams abc len == 2")
    passed += 1

    # 16. bigrams content
    _assert(bg[0] == "ab" and bg[1] == "bc", "bigrams abc == [ab, bc]")
    passed += 1

    # 17. dice_coefficient
    var dc = dice_coefficient("night", "nacht")
    _assert(dc > 0.0 and dc < 1.0, "dice night/nacht in (0,1)")
    passed += 1

    # 18. dice_coefficient identical
    _assert_close(dice_coefficient("abc", "abc"), 1.0, 1e-9, "dice identical == 1.0")
    passed += 1

    # 19. overlap_coefficient identical
    _assert_close(overlap_coefficient("abc", "abc"), 1.0, 1e-9, "overlap identical == 1.0")
    passed += 1

    # 20. overlap_coefficient range
    var oc = overlap_coefficient("night", "nacht")
    _assert(oc >= 0.0 and oc <= 1.0, "overlap range [0,1]")
    passed += 1

    # 21. string_reverse
    _assert(string_reverse("hello") == "olleh", "reverse hello == olleh")
    passed += 1

    # 22. string_reverse empty
    _assert(string_reverse("") == "", "reverse empty")
    passed += 1

    # 23. is_palindrome true
    _assert(is_palindrome("racecar") == True, "racecar is palindrome")
    passed += 1

    # 24. is_palindrome false
    _assert(is_palindrome("hello") == False, "hello not palindrome")
    passed += 1

    # 25. is_palindrome case insensitive with spaces
    _assert(is_palindrome("Race Car") == True, "Race Car is palindrome")
    passed += 1

    print("  ✓ " + String(passed) + " string distance tests passed")


# ── Transform tests ──────────────────────────────────────────────────────────


fn test_transform() raises:
    print("── Transform tests ──")
    var passed = 0

    # e ≈ 2.718281828
    var e_val = 2.718281828459045
    var e2_val = e_val * e_val

    # 26. log_transform [1, e, e^2] ≈ [0, 1, 2]
    var lt_in = List[Float64]()
    lt_in.append(1.0)
    lt_in.append(e_val)
    lt_in.append(e2_val)
    var lt = log_transform(lt_in)
    _assert_close(lt[0], 0.0, 1e-9, "log(1) == 0")
    passed += 1

    # 27.
    _assert_close(lt[1], 1.0, 1e-6, "log(e) == 1")
    passed += 1

    # 28.
    _assert_close(lt[2], 2.0, 1e-6, "log(e^2) == 2")
    passed += 1

    # 29. log1p_transform [0] ≈ [0]
    var l1_in = List[Float64]()
    l1_in.append(0.0)
    var l1 = log1p_transform(l1_in)
    _assert_close(l1[0], 0.0, 1e-9, "log1p(0) == 0")
    passed += 1

    # 30. box_cox with lambda=0 ≈ log
    var bc_in = List[Float64]()
    bc_in.append(1.0)
    bc_in.append(2.0)
    bc_in.append(3.0)
    var bc0 = box_cox(bc_in, 0.0)
    _assert_close(bc0[0], log(1.0), 1e-9, "box_cox(1,0) == log(1)")
    passed += 1

    # 31.
    _assert_close(bc0[1], log(2.0), 1e-6, "box_cox(2,0) == log(2)")
    passed += 1

    # 32. standardize: mean ≈ 0
    var std_in = List[Float64]()
    std_in.append(10.0)
    std_in.append(20.0)
    std_in.append(30.0)
    std_in.append(40.0)
    std_in.append(50.0)
    var zs = standardize(std_in)
    var mean_z = 0.0
    for i in range(len(zs)):
        mean_z += zs[i]
    mean_z /= Float64(len(zs))
    _assert_close(mean_z, 0.0, 1e-9, "standardize mean ≈ 0")
    passed += 1

    # 33. standardize: std ≈ 1
    var ss = 0.0
    for i in range(len(zs)):
        ss += zs[i] * zs[i]
    var std_z = (ss / Float64(len(zs)))
    _assert_close(std_z, 1.0, 1e-9, "standardize var ≈ 1")
    passed += 1

    # 34. min_max_scale: min=0, max=1
    var mm_in = List[Float64]()
    mm_in.append(1.0)
    mm_in.append(2.0)
    mm_in.append(3.0)
    var mm = min_max_scale(mm_in)
    _assert_close(mm[0], 0.0, 1e-9, "min_max min == 0")
    passed += 1

    # 35.
    _assert_close(mm[2], 1.0, 1e-9, "min_max max == 1")
    passed += 1

    # 36.
    _assert_close(mm[1], 0.5, 1e-9, "min_max mid == 0.5")
    passed += 1

    # 37. robust_scale: median ≈ 0
    var rs_in = List[Float64]()
    rs_in.append(1.0)
    rs_in.append(2.0)
    rs_in.append(3.0)
    rs_in.append(4.0)
    rs_in.append(5.0)
    var rs = robust_scale(rs_in)
    _assert_close(rs[2], 0.0, 1e-9, "robust_scale median == 0")
    passed += 1

    # 38. quantile_transform: values in [0,1]
    var qt_in = List[Float64]()
    qt_in.append(1.0)
    qt_in.append(2.0)
    qt_in.append(3.0)
    var qt = quantile_transform(qt_in)
    _assert(qt[0] >= 0.0 and qt[0] <= 1.0, "quantile in [0,1]")
    passed += 1

    # 39. quantile_transform ordered
    _assert_close(qt[0], 0.0, 1e-9, "quantile min == 0")
    passed += 1

    # 40.
    _assert_close(qt[2], 1.0, 1e-9, "quantile max == 1")
    passed += 1

    # 41. clamp_values
    var cl_in = List[Float64]()
    cl_in.append(1.0)
    cl_in.append(5.0)
    cl_in.append(10.0)
    var cl = clamp_values(cl_in, 2.0, 8.0)
    _assert_close(cl[0], 2.0, 1e-9, "clamp 1 -> 2")
    passed += 1

    # 42.
    _assert_close(cl[1], 5.0, 1e-9, "clamp 5 -> 5")
    passed += 1

    # 43.
    _assert_close(cl[2], 8.0, 1e-9, "clamp 10 -> 8")
    passed += 1

    # 44. rank_transform
    var rk_in = List[Float64]()
    rk_in.append(30.0)
    rk_in.append(10.0)
    rk_in.append(20.0)
    var rk = rank_transform(rk_in)
    _assert_close(rk[0], 3.0, 1e-9, "rank 30 -> 3")
    passed += 1

    # 45.
    _assert_close(rk[1], 1.0, 1e-9, "rank 10 -> 1")
    passed += 1

    # 46.
    _assert_close(rk[2], 2.0, 1e-9, "rank 20 -> 2")
    passed += 1

    # 47. abs_transform
    var ab_in = List[Float64]()
    ab_in.append(-1.0)
    ab_in.append(2.0)
    ab_in.append(-3.0)
    var ab = abs_transform(ab_in)
    _assert_close(ab[0], 1.0, 1e-9, "abs(-1) == 1")
    passed += 1

    # 48.
    _assert_close(ab[1], 2.0, 1e-9, "abs(2) == 2")
    passed += 1

    # 49.
    _assert_close(ab[2], 3.0, 1e-9, "abs(-3) == 3")
    passed += 1

    # 50. reciprocal_transform
    var rc_in = List[Float64]()
    rc_in.append(2.0)
    rc_in.append(4.0)
    var rc = reciprocal_transform(rc_in)
    _assert_close(rc[0], 0.5, 1e-9, "1/2 == 0.5")
    passed += 1

    # 51.
    _assert_close(rc[1], 0.25, 1e-9, "1/4 == 0.25")
    passed += 1

    # 52. power_transform
    var pw_in = List[Float64]()
    pw_in.append(4.0)
    pw_in.append(9.0)
    var pw = power_transform(pw_in, 0.5)
    _assert_close(pw[0], 2.0, 1e-6, "4^0.5 == 2")
    passed += 1

    # 53.
    _assert_close(pw[1], 3.0, 1e-6, "9^0.5 == 3")
    passed += 1

    print("  ✓ " + String(passed) + " transform tests passed")


# ── Combinatorial tests ──────────────────────────────────────────────────────


fn test_combinatorial() raises:
    print("── Combinatorial tests ──")
    var passed = 0

    # 54. knapsack_01_value
    var kw = List[Int]()
    kw.append(2)
    kw.append(3)
    kw.append(4)
    var kv = List[Int]()
    kv.append(3)
    kv.append(4)
    kv.append(5)
    _assert(knapsack_01_value(kw, kv, 5) == 7, "knapsack value == 7")
    passed += 1

    # 55. knapsack_01 returns valid indices
    var sel = knapsack_01(kw, kv, 5)
    var total_w = 0
    var total_v = 0
    for i in range(len(sel)):
        total_w += kw[sel[i]]
        total_v += kv[sel[i]]
    _assert(total_w <= 5, "knapsack weight <= capacity")
    passed += 1

    # 56.
    _assert(total_v == 7, "knapsack selected value == 7")
    passed += 1

    # 57. tsp_greedy visits all cities
    var dist = List[List[Float64]]()
    for i in range(4):
        var row = List[Float64]()
        for j in range(4):
            if i == j:
                row.append(0.0)
            else:
                row.append(Float64(i + j + 1) * 1.5)
        dist.append(row^)
    var tour = tsp_greedy(dist)
    # Tour should have n+1 elements (return to start)
    _assert(len(tour) == 5, "tsp tour len == n+1")
    passed += 1

    # 58. Tour starts and ends at 0
    _assert(tour[0] == 0 and tour[4] == 0, "tsp starts/ends at 0")
    passed += 1

    # 59. All cities visited
    var visited = List[Bool]()
    for _ in range(4):
        visited.append(False)
    for i in range(len(tour) - 1):
        visited[tour[i]] = True
    var all_visited = True
    for i in range(4):
        if not visited[i]:
            all_visited = False
    _assert(all_visited, "tsp all cities visited")
    passed += 1

    # 60. tsp_tour_length positive
    var tlen = tsp_tour_length(dist, tour)
    _assert(tlen > 0.0, "tsp tour length > 0")
    passed += 1

    # 61. bin_packing_first_fit
    var bp_items = List[Float64]()
    bp_items.append(0.7)
    bp_items.append(0.3)
    bp_items.append(0.5)
    bp_items.append(0.4)
    var ff = bin_packing_first_fit(bp_items, 1.0)
    _assert(ff >= 2 and ff <= 4, "bin_packing ff reasonable")
    passed += 1

    # 62. bin_packing_first_fit_decreasing <= first_fit
    var ffd = bin_packing_first_fit_decreasing(bp_items, 1.0)
    _assert(ffd <= ff, "ffd <= ff")
    passed += 1

    # 63. ffd reasonable
    _assert(ffd >= 2, "ffd >= 2")
    passed += 1

    # 64. assignment_greedy
    var cost = List[List[Float64]]()
    var r0 = List[Float64]()
    r0.append(9.0)
    r0.append(2.0)
    r0.append(7.0)
    cost.append(r0^)
    var r1 = List[Float64]()
    r1.append(6.0)
    r1.append(4.0)
    r1.append(3.0)
    cost.append(r1^)
    var r2 = List[Float64]()
    r2.append(5.0)
    r2.append(8.0)
    r2.append(1.0)
    cost.append(r2^)
    var asgn = assignment_greedy(cost)
    _assert(len(asgn) == 3, "assignment len == 3")
    passed += 1

    # 65. Assignment row 0 -> col 1 (cheapest=2)
    _assert(asgn[0] == 1, "assignment row 0 -> col 1")
    passed += 1

    # 66. max_subarray_sum (Kadane's)
    var ms_in = List[Float64]()
    ms_in.append(-2.0)
    ms_in.append(1.0)
    ms_in.append(-3.0)
    ms_in.append(4.0)
    ms_in.append(-1.0)
    ms_in.append(2.0)
    ms_in.append(1.0)
    ms_in.append(-5.0)
    ms_in.append(4.0)
    _assert_close(max_subarray_sum(ms_in), 6.0, 1e-9, "max_subarray == 6")
    passed += 1

    # 67. max_subarray_sum all positive
    var ap = List[Float64]()
    ap.append(1.0)
    ap.append(2.0)
    ap.append(3.0)
    _assert_close(max_subarray_sum(ap), 6.0, 1e-9, "max_subarray all positive")
    passed += 1

    # 68. max_subarray_sum all negative
    var an = List[Float64]()
    an.append(-5.0)
    an.append(-2.0)
    an.append(-8.0)
    _assert_close(max_subarray_sum(an), -2.0, 1e-9, "max_subarray all negative")
    passed += 1

    # 69. longest_increasing_subsequence
    var lis_in = List[Float64]()
    lis_in.append(10.0)
    lis_in.append(9.0)
    lis_in.append(2.0)
    lis_in.append(5.0)
    lis_in.append(3.0)
    lis_in.append(7.0)
    lis_in.append(101.0)
    _assert(longest_increasing_subsequence(lis_in) == 4, "LIS == 4")
    passed += 1

    # 70. LIS monotonic
    var mono = List[Float64]()
    mono.append(1.0)
    mono.append(2.0)
    mono.append(3.0)
    mono.append(4.0)
    _assert(longest_increasing_subsequence(mono) == 4, "LIS monotonic == 4")
    passed += 1

    # 71. LIS decreasing
    var dec = List[Float64]()
    dec.append(4.0)
    dec.append(3.0)
    dec.append(2.0)
    dec.append(1.0)
    _assert(longest_increasing_subsequence(dec) == 1, "LIS decreasing == 1")
    passed += 1

    # 72. coin_change
    var coins = List[Int]()
    coins.append(1)
    coins.append(5)
    coins.append(10)
    coins.append(25)
    _assert(coin_change(coins, 30) == 2, "coin_change 30 == 2 (25+5)")
    passed += 1

    # 73. coin_change exact
    _assert(coin_change(coins, 25) == 1, "coin_change 25 == 1")
    passed += 1

    # 74. coin_change impossible
    var coins2 = List[Int]()
    coins2.append(3)
    coins2.append(5)
    _assert(coin_change(coins2, 1) == -1, "coin_change impossible == -1")
    passed += 1

    # 75. coin_change zero
    _assert(coin_change(coins, 0) == 0, "coin_change 0 == 0")
    passed += 1

    print("  ✓ " + String(passed) + " combinatorial tests passed")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 38 Tests ===")
    test_string_distance()
    test_transform()
    test_combinatorial()
    print("=== All Wave 38 tests passed! ===")
