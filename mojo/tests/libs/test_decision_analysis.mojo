"""test_decision_analysis.mojo — auto-generated tests for decision_analysis library."""
from std.math import isnan, isinf
from decision_analysis import expected_value, expected_utility

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

    var _v_expected_value = expected_value(_lf5, _lf5)
    if is_finite(_v_expected_value): passed += 1; print("  ✅ decision_analysis::expected_value =", _v_expected_value)
    else: failed += 1; print("  ❌ decision_analysis::expected_value → non-finite:", _v_expected_value)
    var _v_expected_utility = expected_utility(_lf5, _lf5, 0.5)
    if is_finite(_v_expected_utility): passed += 1; print("  ✅ decision_analysis::expected_utility =", _v_expected_utility)
    else: failed += 1; print("  ❌ decision_analysis::expected_utility → non-finite:", _v_expected_utility)

    print("  [decision_analysis] Passed:", passed, "Failed:", failed)
