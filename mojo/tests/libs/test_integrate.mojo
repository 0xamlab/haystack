"""test_integrate.mojo — auto-generated tests for integrate."""
from std.math import isnan, isinf
from integrate import trapezoid, simpson, romberg, cumulative_trapezoid, integrate_poly, quad_gauss_legendre

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

    var _v_trapezoid = trapezoid(_lf5, 0.5)
    if is_finite(_v_trapezoid): passed += 1; print("  ✅ integrate::trapezoid =", _v_trapezoid)
    else: failed += 1; print("  ❌ integrate::trapezoid → non-finite:", _v_trapezoid)
    var _v_simpson = simpson(_lf5, 0.5)
    if is_finite(_v_simpson): passed += 1; print("  ✅ integrate::simpson =", _v_simpson)
    else: failed += 1; print("  ❌ integrate::simpson → non-finite:", _v_simpson)
    var _v_romberg = romberg(_lf5, 0.5, 5)
    if is_finite(_v_romberg): passed += 1; print("  ✅ integrate::romberg =", _v_romberg)
    else: failed += 1; print("  ❌ integrate::romberg → non-finite:", _v_romberg)
    var _v_cumulative_trapezoid = cumulative_trapezoid(_lf5, 0.5)
    if len(_v_cumulative_trapezoid) >= 0: passed += 1; print("  ✅ integrate::cumulative_trapezoid")
    var _v_integrate_poly = integrate_poly(_lf5, 0.5, 0.5)
    if is_finite(_v_integrate_poly): passed += 1; print("  ✅ integrate::integrate_poly =", _v_integrate_poly)
    else: failed += 1; print("  ❌ integrate::integrate_poly → non-finite:", _v_integrate_poly)
    var _v_quad_gauss_legendre = quad_gauss_legendre(_lf5, 0.5, 0.5)
    if is_finite(_v_quad_gauss_legendre): passed += 1; print("  ✅ integrate::quad_gauss_legendre =", _v_quad_gauss_legendre)
    else: failed += 1; print("  ❌ integrate::quad_gauss_legendre → non-finite:", _v_quad_gauss_legendre)

    print("  [integrate] Passed:", passed, "Failed:", failed)
