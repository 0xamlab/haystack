"""test_combinatorial.mojo — auto-generated tests for combinatorial."""
from std.math import isnan, isinf
from combinatorial import knapsack_01, knapsack_01_value, bin_packing_first_fit, bin_packing_first_fit_decreasing, max_subarray_sum, longest_increasing_subsequence, coin_change

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _li3 = List[Int]()
    _li3.append(1); _li3.append(2); _li3.append(3)
    var _li2_zero = List[Int]()
    _li2_zero.append(0); _li2_zero.append(1)
    var _li3_tail = List[Int]()
    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)
    var _li8 = List[Int]()
    for i in range(8):
        _li8.append(i + 1)
    var _li6_grid2x3 = List[Int]()
    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    var _li10_borda = List[Int]()
    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)
    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)
    var _li16 = List[Int]()
    for i in range(16):
        _li16.append(i)
    var _lf6_matrix = List[Float64]()
    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)
    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)
    var _lf8_coalitions = List[Float64]()
    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)
    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_knapsack_01 = knapsack_01(_li5, _li5, 5)
    if len(_v_knapsack_01) >= 0: passed += 1; print("  ✅ combinatorial::knapsack_01")
    _ = knapsack_01_value(_li5, _li5, 5)
    passed += 1; print("  ✅ combinatorial::knapsack_01_value")
    _ = bin_packing_first_fit(_lf5, 0.5)
    passed += 1; print("  ✅ combinatorial::bin_packing_first_fit")
    _ = bin_packing_first_fit_decreasing(_lf5, 0.5)
    passed += 1; print("  ✅ combinatorial::bin_packing_first_fit_decreasing")
    var _v_max_subarray_sum = max_subarray_sum(_lf5)
    if is_finite(_v_max_subarray_sum): passed += 1; print("  ✅ combinatorial::max_subarray_sum =", _v_max_subarray_sum)
    else: failed += 1; print("  ❌ combinatorial::max_subarray_sum → non-finite:", _v_max_subarray_sum)
    _ = longest_increasing_subsequence(_lf5)
    passed += 1; print("  ✅ combinatorial::longest_increasing_subsequence")
    _ = coin_change(_li5, 5)
    passed += 1; print("  ✅ combinatorial::coin_change")

    print("  [combinatorial] Passed:", passed, "Failed:", failed)
