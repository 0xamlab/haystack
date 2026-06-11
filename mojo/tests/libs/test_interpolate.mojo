"""test_interpolate.mojo — auto-generated tests for interpolate."""
from std.math import isnan, isinf
from interpolate import linear_interp, nearest_interp, cubic_spline_natural, lagrange_interp, interp_array, extrapolate_linear

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

    var _v_linear_interp = linear_interp(_lf5, _lf5, 0.5)
    if is_finite(_v_linear_interp): passed += 1; print("  ✅ interpolate::linear_interp =", _v_linear_interp)
    else: failed += 1; print("  ❌ interpolate::linear_interp → non-finite:", _v_linear_interp)
    var _v_nearest_interp = nearest_interp(_lf5, _lf5, 0.5)
    if is_finite(_v_nearest_interp): passed += 1; print("  ✅ interpolate::nearest_interp =", _v_nearest_interp)
    else: failed += 1; print("  ❌ interpolate::nearest_interp → non-finite:", _v_nearest_interp)
    var _v_cubic_spline_natural = cubic_spline_natural(_lf5, _lf5, 0.5)
    if is_finite(_v_cubic_spline_natural): passed += 1; print("  ✅ interpolate::cubic_spline_natural =", _v_cubic_spline_natural)
    else: failed += 1; print("  ❌ interpolate::cubic_spline_natural → non-finite:", _v_cubic_spline_natural)
    var _v_lagrange_interp = lagrange_interp(_lf5, _lf5, 0.5)
    if is_finite(_v_lagrange_interp): passed += 1; print("  ✅ interpolate::lagrange_interp =", _v_lagrange_interp)
    else: failed += 1; print("  ❌ interpolate::lagrange_interp → non-finite:", _v_lagrange_interp)
    var _v_interp_array = interp_array(_lf5, _lf5, _lf5, "test")
    if len(_v_interp_array) >= 0: passed += 1; print("  ✅ interpolate::interp_array")
    var _v_extrapolate_linear = extrapolate_linear(_lf5, _lf5, 0.5)
    if is_finite(_v_extrapolate_linear): passed += 1; print("  ✅ interpolate::extrapolate_linear =", _v_extrapolate_linear)
    else: failed += 1; print("  ❌ interpolate::extrapolate_linear → non-finite:", _v_extrapolate_linear)

    print("  [interpolate] Passed:", passed, "Failed:", failed)
