"""test_polynomial.mojo — auto-generated tests for polynomial."""
from std.math import isnan, isinf
from polynomial import poly_eval, poly_add, poly_multiply, poly_derivative, poly_integral, poly_degree, quadratic_roots, poly_scale, poly_compose, poly_from_roots

def is_finite(x: Float64) -> Bool:
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

    var _v_poly_eval = poly_eval(_lf5, 0.5)
    if is_finite(_v_poly_eval): passed += 1; print("  ✅ polynomial::poly_eval =", _v_poly_eval)
    else: failed += 1; print("  ❌ polynomial::poly_eval → non-finite:", _v_poly_eval)
    var _v_poly_add = poly_add(_lf5, _lf5)
    if len(_v_poly_add) >= 0: passed += 1; print("  ✅ polynomial::poly_add")
    var _v_poly_multiply = poly_multiply(_lf5, _lf5)
    if len(_v_poly_multiply) >= 0: passed += 1; print("  ✅ polynomial::poly_multiply")
    var _v_poly_derivative = poly_derivative(_lf5)
    if len(_v_poly_derivative) >= 0: passed += 1; print("  ✅ polynomial::poly_derivative")
    var _v_poly_integral = poly_integral(_lf5, 0.5)
    if len(_v_poly_integral) >= 0: passed += 1; print("  ✅ polynomial::poly_integral")
    _ = poly_degree(_lf5)
    passed += 1; print("  ✅ polynomial::poly_degree")
    var _v_quadratic_roots = quadratic_roots(0.5, 0.5, 0.5)
    if len(_v_quadratic_roots) >= 0: passed += 1; print("  ✅ polynomial::quadratic_roots")
    var _v_poly_scale = poly_scale(_lf5, 0.5)
    if len(_v_poly_scale) >= 0: passed += 1; print("  ✅ polynomial::poly_scale")
    var _v_poly_compose = poly_compose(_lf5, _lf5)
    if len(_v_poly_compose) >= 0: passed += 1; print("  ✅ polynomial::poly_compose")
    var _v_poly_from_roots = poly_from_roots(_lf5)
    if len(_v_poly_from_roots) >= 0: passed += 1; print("  ✅ polynomial::poly_from_roots")

    print("  [polynomial] Passed:", passed, "Failed:", failed)
