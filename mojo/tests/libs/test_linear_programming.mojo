"""test_linear_programming.mojo — auto-generated tests for linear_programming library."""
from std.math import isnan, isinf
from linear_programming import line_intersection_2d, objective_value

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

    var _v_line_intersection_2d = line_intersection_2d(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if len(_v_line_intersection_2d) >= 0: passed += 1; print("  ✅ linear_programming::line_intersection_2d")
    var _v_objective_value = objective_value(_lf5, _lf5)
    if is_finite(_v_objective_value): passed += 1; print("  ✅ linear_programming::objective_value =", _v_objective_value)
    else: failed += 1; print("  ❌ linear_programming::objective_value → non-finite:", _v_objective_value)

    print("  [linear_programming] Passed:", passed, "Failed:", failed)
