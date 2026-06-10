"""test_dimensions.mojo — auto-generated tests for dimensions."""
from std.math import isnan, isinf
from dimensions import infer_from_samples, propagate, propagate_is_valid, validate_formula, can_sum, can_avg, aggregation_valid, role_for_dimension, dimension_name, dimension_from_role

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

    _ = infer_from_samples(_lf5)
    passed += 1; print("  ✅ dimensions::infer_from_samples")
    _ = propagate("test", 5, 5)
    passed += 1; print("  ✅ dimensions::propagate")
    _ = propagate_is_valid("test", 5, 5)
    passed += 1; print("  ✅ dimensions::propagate_is_valid")
    _ = validate_formula("test", 5, 5, 5)
    passed += 1; print("  ✅ dimensions::validate_formula")
    _ = can_sum(5)
    passed += 1; print("  ✅ dimensions::can_sum")
    _ = can_avg(5)
    passed += 1; print("  ✅ dimensions::can_avg")
    _ = aggregation_valid("test", 5)
    passed += 1; print("  ✅ dimensions::aggregation_valid")
    _ = role_for_dimension(5)
    passed += 1; print("  ✅ dimensions::role_for_dimension")
    _ = dimension_name(5)
    passed += 1; print("  ✅ dimensions::dimension_name")
    _ = dimension_from_role("test")
    passed += 1; print("  ✅ dimensions::dimension_from_role")

    print("  [dimensions] Passed:", passed, "Failed:", failed)
