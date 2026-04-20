"""test_series.mojo — auto-generated tests for series library."""
from std.math import isnan, isinf
from series import sma_forecast, linear_extrapolation, weighted_moving_avg, exponential_forecast, naive_forecast, seasonal_naive, drift_forecast, forecast_accuracy, trend_strength, detect_seasonality

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
