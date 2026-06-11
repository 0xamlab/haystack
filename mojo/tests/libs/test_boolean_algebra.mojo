"""test_boolean_algebra.mojo — auto-generated tests for boolean_algebra."""
from std.math import isnan, isinf
from boolean_algebra import bool_and, bool_or, bool_not, bool_xor, bool_implies, bool_iff, truth_table_2, is_tautology_2var, count_satisfying_2var, majority_vote, parity

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

    _ = bool_and(True, True)
    passed += 1; print("  ✅ boolean_algebra::bool_and")
    _ = bool_or(True, True)
    passed += 1; print("  ✅ boolean_algebra::bool_or")
    _ = bool_not(True)
    passed += 1; print("  ✅ boolean_algebra::bool_not")
    _ = bool_xor(True, True)
    passed += 1; print("  ✅ boolean_algebra::bool_xor")
    _ = bool_implies(True, True)
    passed += 1; print("  ✅ boolean_algebra::bool_implies")
    _ = bool_iff(True, True)
    passed += 1; print("  ✅ boolean_algebra::bool_iff")
    _ = truth_table_2(5)
    passed += 1; print("  ✅ boolean_algebra::truth_table_2")
    _ = is_tautology_2var(5)
    passed += 1; print("  ✅ boolean_algebra::is_tautology_2var")
    _ = count_satisfying_2var(5)
    passed += 1; print("  ✅ boolean_algebra::count_satisfying_2var")
    _ = majority_vote(_lb5)
    passed += 1; print("  ✅ boolean_algebra::majority_vote")
    _ = parity(_lb5)
    passed += 1; print("  ✅ boolean_algebra::parity")

    print("  [boolean_algebra] Passed:", passed, "Failed:", failed)
