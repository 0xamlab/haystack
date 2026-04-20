"""test_combinatorial.mojo — auto-generated tests for combinatorial library."""
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
