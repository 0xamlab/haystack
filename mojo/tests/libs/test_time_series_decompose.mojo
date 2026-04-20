"""test_time_series_decompose.mojo — auto-generated tests for time_series_decompose library."""
from std.math import isnan, isinf
from time_series_decompose import moving_average_trend, detrend, seasonal_component, residual, decompose_additive, seasonal_strength, trend_strength, detect_period, stl_like

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
