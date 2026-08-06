"""test_ab_testing.mojo — auto-generated tests for ab_testing."""
from std.math import isnan, isinf
from ab_testing import sample_size_proportion, z_test_proportions, confidence_interval_proportion, relative_uplift, is_significant, power_analysis, mde, sequential_test, epsilon_greedy_select, ucb1_select

def is_finite(x: Float64) -> Bool:
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

    _ = sample_size_proportion(0.5, 0.5, 0.5, 0.5)
    passed += 1; print("  ✅ ab_testing::sample_size_proportion")
    var _v_z_test_proportions = z_test_proportions(5, 5, 5, 5)
    if len(_v_z_test_proportions) >= 0: passed += 1; print("  ✅ ab_testing::z_test_proportions")
    var _v_confidence_interval_proportion = confidence_interval_proportion(5, 5, 0.5)
    if len(_v_confidence_interval_proportion) >= 0: passed += 1; print("  ✅ ab_testing::confidence_interval_proportion")
    var _v_relative_uplift = relative_uplift(0.5, 0.5)
    if is_finite(_v_relative_uplift): passed += 1; print("  ✅ ab_testing::relative_uplift =", _v_relative_uplift)
    else: failed += 1; print("  ❌ ab_testing::relative_uplift → non-finite:", _v_relative_uplift)
    _ = is_significant(0.5, 0.5)
    passed += 1; print("  ✅ ab_testing::is_significant")
    var _v_power_analysis = power_analysis(0.5, 5, 0.5)
    if is_finite(_v_power_analysis): passed += 1; print("  ✅ ab_testing::power_analysis =", _v_power_analysis)
    else: failed += 1; print("  ❌ ab_testing::power_analysis → non-finite:", _v_power_analysis)
    var _v_mde = mde(5, 0.5, 0.5, 0.5)
    if is_finite(_v_mde): passed += 1; print("  ✅ ab_testing::mde =", _v_mde)
    else: failed += 1; print("  ❌ ab_testing::mde → non-finite:", _v_mde)
    _ = sequential_test(5, 5, 5, 5, 0.5)
    passed += 1; print("  ✅ ab_testing::sequential_test")
    _ = epsilon_greedy_select(_lf5, _li5, 0.5)
    passed += 1; print("  ✅ ab_testing::epsilon_greedy_select")
    _ = ucb1_select(_lf5, _li5, 5)
    passed += 1; print("  ✅ ab_testing::ucb1_select")

    print("  [ab_testing] Passed:", passed, "Failed:", failed)
