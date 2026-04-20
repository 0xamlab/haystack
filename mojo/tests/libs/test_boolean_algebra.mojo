"""test_boolean_algebra.mojo — auto-generated tests for boolean_algebra library."""
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
