"""test_regression.mojo — auto-generated tests for regression library."""
from std.math import isnan, isinf
from regression import r_squared, mse, rmse, ols_simple, polynomial_features

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

    var _v_r_squared = r_squared(_lf5, _lf5)
    if is_finite(_v_r_squared): passed += 1; print("  ✅ regression::r_squared =", _v_r_squared)
    else: failed += 1; print("  ❌ regression::r_squared → non-finite:", _v_r_squared)
    var _v_mse = mse(_lf5, _lf5)
    if is_finite(_v_mse): passed += 1; print("  ✅ regression::mse =", _v_mse)
    else: failed += 1; print("  ❌ regression::mse → non-finite:", _v_mse)
    var _v_rmse = rmse(_lf5, _lf5)
    if is_finite(_v_rmse): passed += 1; print("  ✅ regression::rmse =", _v_rmse)
    else: failed += 1; print("  ❌ regression::rmse → non-finite:", _v_rmse)
    _ = ols_simple(_lf5, _lf5)
    passed += 1; print("  ✅ regression::ols_simple")
    _ = polynomial_features(_lf5, 5)
    passed += 1; print("  ✅ regression::polynomial_features")

    print("  [regression] Passed:", passed, "Failed:", failed)
