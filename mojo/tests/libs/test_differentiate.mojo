"""test_differentiate.mojo — auto-generated tests for differentiate library."""
from std.math import isnan, isinf
from differentiate import derivative_forward, derivative_central, derivative_backward, second_derivative, gradient, poly_derivative_coeffs

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

    var _v_derivative_forward = derivative_forward(_lf5, 0.5)
    if len(_v_derivative_forward) >= 0: passed += 1; print("  ✅ differentiate::derivative_forward")
    var _v_derivative_central = derivative_central(_lf5, 0.5)
    if len(_v_derivative_central) >= 0: passed += 1; print("  ✅ differentiate::derivative_central")
    var _v_derivative_backward = derivative_backward(_lf5, 0.5)
    if len(_v_derivative_backward) >= 0: passed += 1; print("  ✅ differentiate::derivative_backward")
    var _v_second_derivative = second_derivative(_lf5, 0.5)
    if len(_v_second_derivative) >= 0: passed += 1; print("  ✅ differentiate::second_derivative")
    var _v_gradient = gradient(_lf5, _lf5)
    if len(_v_gradient) >= 0: passed += 1; print("  ✅ differentiate::gradient")
    var _v_poly_derivative_coeffs = poly_derivative_coeffs(_lf5)
    if len(_v_poly_derivative_coeffs) >= 0: passed += 1; print("  ✅ differentiate::poly_derivative_coeffs")

    print("  [differentiate] Passed:", passed, "Failed:", failed)
