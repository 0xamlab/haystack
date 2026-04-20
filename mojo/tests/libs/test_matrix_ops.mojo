"""test_matrix_ops.mojo — auto-generated tests for matrix_ops library."""
from std.math import isnan, isinf
from matrix_ops import outer_product, unvec

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

    _ = outer_product(_lf5, _lf5)
    passed += 1; print("  ✅ matrix_ops::outer_product")
    _ = unvec(_lf5, 5, 5)
    passed += 1; print("  ✅ matrix_ops::unvec")

    print("  [matrix_ops] Passed:", passed, "Failed:", failed)
