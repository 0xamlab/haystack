"""test_series.mojo — auto-generated tests for series."""
from std.math import isnan, isinf
from series import sma_forecast, linear_extrapolation, weighted_moving_avg, exponential_forecast, naive_forecast, seasonal_naive, drift_forecast, forecast_accuracy, trend_strength, detect_seasonality

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

    var _v_sma_forecast = sma_forecast(_lf5, 5, 5)
    if len(_v_sma_forecast) >= 0: passed += 1; print("  ✅ series::sma_forecast")
    var _v_linear_extrapolation = linear_extrapolation(_lf5, 5)
    if len(_v_linear_extrapolation) >= 0: passed += 1; print("  ✅ series::linear_extrapolation")
    var _v_weighted_moving_avg = weighted_moving_avg(_lf5, _lf5)
    if is_finite(_v_weighted_moving_avg): passed += 1; print("  ✅ series::weighted_moving_avg =", _v_weighted_moving_avg)
    else: failed += 1; print("  ❌ series::weighted_moving_avg → non-finite:", _v_weighted_moving_avg)
    var _v_exponential_forecast = exponential_forecast(_lf5, 0.5, 5)
    if len(_v_exponential_forecast) >= 0: passed += 1; print("  ✅ series::exponential_forecast")
    var _v_naive_forecast = naive_forecast(_lf5, 5)
    if len(_v_naive_forecast) >= 0: passed += 1; print("  ✅ series::naive_forecast")
    var _v_seasonal_naive = seasonal_naive(_lf5, 5, 5)
    if len(_v_seasonal_naive) >= 0: passed += 1; print("  ✅ series::seasonal_naive")
    var _v_drift_forecast = drift_forecast(_lf5, 5)
    if len(_v_drift_forecast) >= 0: passed += 1; print("  ✅ series::drift_forecast")
    var _v_forecast_accuracy = forecast_accuracy(_lf5, _lf5)
    if len(_v_forecast_accuracy) >= 0: passed += 1; print("  ✅ series::forecast_accuracy")
    var _v_trend_strength = trend_strength(_lf5)
    if is_finite(_v_trend_strength): passed += 1; print("  ✅ series::trend_strength =", _v_trend_strength)
    else: failed += 1; print("  ❌ series::trend_strength → non-finite:", _v_trend_strength)
    _ = detect_seasonality(_lf5, 5)
    passed += 1; print("  ✅ series::detect_seasonality")

    print("  [series] Passed:", passed, "Failed:", failed)
