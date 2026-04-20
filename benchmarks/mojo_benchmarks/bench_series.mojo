"""bench_series.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from series import sma_forecast, linear_extrapolation, weighted_moving_avg, exponential_forecast, naive_forecast, seasonal_naive, drift_forecast, forecast_accuracy, trend_strength, detect_seasonality
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_sma_forecast: Float64 = 0.0
    var _t0_sma_forecast = perf_counter_ns()
    for _ in range(N):
        var _r_sma_forecast = sma_forecast(_lf5, 5, 5)
        _acc_sma_forecast += Float64(len(_r_sma_forecast))
    var _t1_sma_forecast = perf_counter_ns()
    var _ns_sma_forecast = Float64(_t1_sma_forecast - _t0_sma_forecast) / Float64(N)
    print("MOJO_TIMING series::sma_forecast", _ns_sma_forecast, _acc_sma_forecast)
    var _acc_linear_extrapolation: Float64 = 0.0
    var _t0_linear_extrapolation = perf_counter_ns()
    for _ in range(N):
        var _r_linear_extrapolation = linear_extrapolation(_lf5, 5)
        _acc_linear_extrapolation += Float64(len(_r_linear_extrapolation))
    var _t1_linear_extrapolation = perf_counter_ns()
    var _ns_linear_extrapolation = Float64(_t1_linear_extrapolation - _t0_linear_extrapolation) / Float64(N)
    print("MOJO_TIMING series::linear_extrapolation", _ns_linear_extrapolation, _acc_linear_extrapolation)
    var _acc_weighted_moving_avg: Float64 = 0.0
    var _t0_weighted_moving_avg = perf_counter_ns()
    for _ in range(N):
        _acc_weighted_moving_avg += weighted_moving_avg(_lf5, _lf5)
    var _t1_weighted_moving_avg = perf_counter_ns()
    var _ns_weighted_moving_avg = Float64(_t1_weighted_moving_avg - _t0_weighted_moving_avg) / Float64(N)
    print("MOJO_TIMING series::weighted_moving_avg", _ns_weighted_moving_avg, _acc_weighted_moving_avg)
    var _acc_exponential_forecast: Float64 = 0.0
    var _t0_exponential_forecast = perf_counter_ns()
    for _ in range(N):
        var _r_exponential_forecast = exponential_forecast(_lf5, 0.5, 5)
        _acc_exponential_forecast += Float64(len(_r_exponential_forecast))
    var _t1_exponential_forecast = perf_counter_ns()
    var _ns_exponential_forecast = Float64(_t1_exponential_forecast - _t0_exponential_forecast) / Float64(N)
    print("MOJO_TIMING series::exponential_forecast", _ns_exponential_forecast, _acc_exponential_forecast)
    var _acc_naive_forecast: Float64 = 0.0
    var _t0_naive_forecast = perf_counter_ns()
    for _ in range(N):
        var _r_naive_forecast = naive_forecast(_lf5, 5)
        _acc_naive_forecast += Float64(len(_r_naive_forecast))
    var _t1_naive_forecast = perf_counter_ns()
    var _ns_naive_forecast = Float64(_t1_naive_forecast - _t0_naive_forecast) / Float64(N)
    print("MOJO_TIMING series::naive_forecast", _ns_naive_forecast, _acc_naive_forecast)
    var _acc_seasonal_naive: Float64 = 0.0
    var _t0_seasonal_naive = perf_counter_ns()
    for _ in range(N):
        var _r_seasonal_naive = seasonal_naive(_lf5, 5, 5)
        _acc_seasonal_naive += Float64(len(_r_seasonal_naive))
    var _t1_seasonal_naive = perf_counter_ns()
    var _ns_seasonal_naive = Float64(_t1_seasonal_naive - _t0_seasonal_naive) / Float64(N)
    print("MOJO_TIMING series::seasonal_naive", _ns_seasonal_naive, _acc_seasonal_naive)
    var _acc_drift_forecast: Float64 = 0.0
    var _t0_drift_forecast = perf_counter_ns()
    for _ in range(N):
        var _r_drift_forecast = drift_forecast(_lf5, 5)
        _acc_drift_forecast += Float64(len(_r_drift_forecast))
    var _t1_drift_forecast = perf_counter_ns()
    var _ns_drift_forecast = Float64(_t1_drift_forecast - _t0_drift_forecast) / Float64(N)
    print("MOJO_TIMING series::drift_forecast", _ns_drift_forecast, _acc_drift_forecast)
    var _acc_forecast_accuracy: Float64 = 0.0
    var _t0_forecast_accuracy = perf_counter_ns()
    for _ in range(N):
        var _r_forecast_accuracy = forecast_accuracy(_lf5, _lf5)
        _acc_forecast_accuracy += Float64(len(_r_forecast_accuracy))
    var _t1_forecast_accuracy = perf_counter_ns()
    var _ns_forecast_accuracy = Float64(_t1_forecast_accuracy - _t0_forecast_accuracy) / Float64(N)
    print("MOJO_TIMING series::forecast_accuracy", _ns_forecast_accuracy, _acc_forecast_accuracy)
    var _acc_trend_strength: Float64 = 0.0
    var _t0_trend_strength = perf_counter_ns()
    for _ in range(N):
        _acc_trend_strength += trend_strength(_lf5)
    var _t1_trend_strength = perf_counter_ns()
    var _ns_trend_strength = Float64(_t1_trend_strength - _t0_trend_strength) / Float64(N)
    print("MOJO_TIMING series::trend_strength", _ns_trend_strength, _acc_trend_strength)
    var _acc_detect_seasonality: Float64 = 0.0
    var _t0_detect_seasonality = perf_counter_ns()
    for _ in range(N):
        _acc_detect_seasonality += Float64(detect_seasonality(_lf5, 5))
    var _t1_detect_seasonality = perf_counter_ns()
    var _ns_detect_seasonality = Float64(_t1_detect_seasonality - _t0_detect_seasonality) / Float64(N)
    print("MOJO_TIMING series::detect_seasonality", _ns_detect_seasonality, _acc_detect_seasonality)
