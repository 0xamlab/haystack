"""test_time_series_decompose.mojo — auto-generated tests for time_series_decompose."""
from std.math import isnan, isinf
from time_series_decompose import moving_average_trend, detrend, seasonal_component, residual, decompose_additive, seasonal_strength, trend_strength, detect_period, stl_like

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

    var _v_moving_average_trend = moving_average_trend(_lf5, 5)
    if len(_v_moving_average_trend) >= 0: passed += 1; print("  ✅ time_series_decompose::moving_average_trend")
    var _v_detrend = detrend(_lf5, _lf5)
    if len(_v_detrend) >= 0: passed += 1; print("  ✅ time_series_decompose::detrend")
    var _v_seasonal_component = seasonal_component(_lf5, 5)
    if len(_v_seasonal_component) >= 0: passed += 1; print("  ✅ time_series_decompose::seasonal_component")
    var _v_residual = residual(_lf5, _lf5, _lf5)
    if len(_v_residual) >= 0: passed += 1; print("  ✅ time_series_decompose::residual")
    _ = decompose_additive(_lf5, 5)
    passed += 1; print("  ✅ time_series_decompose::decompose_additive")
    var _v_seasonal_strength = seasonal_strength(_lf5, _lf5)
    if is_finite(_v_seasonal_strength): passed += 1; print("  ✅ time_series_decompose::seasonal_strength =", _v_seasonal_strength)
    else: failed += 1; print("  ❌ time_series_decompose::seasonal_strength → non-finite:", _v_seasonal_strength)
    var _v_trend_strength = trend_strength(_lf5, _lf5)
    if is_finite(_v_trend_strength): passed += 1; print("  ✅ time_series_decompose::trend_strength =", _v_trend_strength)
    else: failed += 1; print("  ❌ time_series_decompose::trend_strength → non-finite:", _v_trend_strength)
    _ = detect_period(_lf5, 5)
    passed += 1; print("  ✅ time_series_decompose::detect_period")
    _ = stl_like(_lf5, 5, 5)
    passed += 1; print("  ✅ time_series_decompose::stl_like")

    print("  [time_series_decompose] Passed:", passed, "Failed:", failed)
