"""test_regression_tree.mojo — auto-generated tests for regression_tree library."""
from std.math import isnan, isinf
from regression_tree import mse_reduction

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

    var _v_mse_reduction = mse_reduction(_lf5, _li5, _li5)
    if is_finite(_v_mse_reduction): passed += 1; print("  ✅ regression_tree::mse_reduction =", _v_mse_reduction)
    else: failed += 1; print("  ❌ regression_tree::mse_reduction → non-finite:", _v_mse_reduction)

    print("  [regression_tree] Passed:", passed, "Failed:", failed)
