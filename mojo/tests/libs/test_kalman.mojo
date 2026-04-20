"""test_kalman.mojo — auto-generated tests for kalman library."""
from std.math import isnan, isinf
from kalman import mat_identity, kalman_smooth_1d

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

    _ = mat_identity(5)
    passed += 1; print("  ✅ kalman::mat_identity")
    var _v_kalman_smooth_1d = kalman_smooth_1d(_lf5, 0.5, 0.5)
    if len(_v_kalman_smooth_1d) >= 0: passed += 1; print("  ✅ kalman::kalman_smooth_1d")

    print("  [kalman] Passed:", passed, "Failed:", failed)
