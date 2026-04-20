"""bench_time_series_decompose.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from time_series_decompose import moving_average_trend, detrend, seasonal_component, residual, decompose_additive, seasonal_strength, trend_strength, detect_period, stl_like
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

    var _acc_moving_average_trend: Float64 = 0.0
    var _t0_moving_average_trend = perf_counter_ns()
    for _ in range(N):
        var _r_moving_average_trend = moving_average_trend(_lf5, 5)
        _acc_moving_average_trend += Float64(len(_r_moving_average_trend))
    var _t1_moving_average_trend = perf_counter_ns()
    var _ns_moving_average_trend = Float64(_t1_moving_average_trend - _t0_moving_average_trend) / Float64(N)
    print("MOJO_TIMING time_series_decompose::moving_average_trend", _ns_moving_average_trend, _acc_moving_average_trend)
    var _acc_detrend: Float64 = 0.0
    var _t0_detrend = perf_counter_ns()
    for _ in range(N):
        var _r_detrend = detrend(_lf5, _lf5)
        _acc_detrend += Float64(len(_r_detrend))
    var _t1_detrend = perf_counter_ns()
    var _ns_detrend = Float64(_t1_detrend - _t0_detrend) / Float64(N)
    print("MOJO_TIMING time_series_decompose::detrend", _ns_detrend, _acc_detrend)
    var _acc_seasonal_component: Float64 = 0.0
    var _t0_seasonal_component = perf_counter_ns()
    for _ in range(N):
        var _r_seasonal_component = seasonal_component(_lf5, 5)
        _acc_seasonal_component += Float64(len(_r_seasonal_component))
    var _t1_seasonal_component = perf_counter_ns()
    var _ns_seasonal_component = Float64(_t1_seasonal_component - _t0_seasonal_component) / Float64(N)
    print("MOJO_TIMING time_series_decompose::seasonal_component", _ns_seasonal_component, _acc_seasonal_component)
    var _acc_residual: Float64 = 0.0
    var _t0_residual = perf_counter_ns()
    for _ in range(N):
        var _r_residual = residual(_lf5, _lf5, _lf5)
        _acc_residual += Float64(len(_r_residual))
    var _t1_residual = perf_counter_ns()
    var _ns_residual = Float64(_t1_residual - _t0_residual) / Float64(N)
    print("MOJO_TIMING time_series_decompose::residual", _ns_residual, _acc_residual)
    var _acc_decompose_additive: Float64 = 0.0
    var _t0_decompose_additive = perf_counter_ns()
    for _ in range(N):
        var _r_decompose_additive = decompose_additive(_lf5, 5)
        _acc_decompose_additive += Float64(len(_r_decompose_additive))
    var _t1_decompose_additive = perf_counter_ns()
    var _ns_decompose_additive = Float64(_t1_decompose_additive - _t0_decompose_additive) / Float64(N)
    print("MOJO_TIMING time_series_decompose::decompose_additive", _ns_decompose_additive, _acc_decompose_additive)
    var _acc_seasonal_strength: Float64 = 0.0
    var _t0_seasonal_strength = perf_counter_ns()
    for _ in range(N):
        _acc_seasonal_strength += seasonal_strength(_lf5, _lf5)
    var _t1_seasonal_strength = perf_counter_ns()
    var _ns_seasonal_strength = Float64(_t1_seasonal_strength - _t0_seasonal_strength) / Float64(N)
    print("MOJO_TIMING time_series_decompose::seasonal_strength", _ns_seasonal_strength, _acc_seasonal_strength)
    var _acc_trend_strength: Float64 = 0.0
    var _t0_trend_strength = perf_counter_ns()
    for _ in range(N):
        _acc_trend_strength += trend_strength(_lf5, _lf5)
    var _t1_trend_strength = perf_counter_ns()
    var _ns_trend_strength = Float64(_t1_trend_strength - _t0_trend_strength) / Float64(N)
    print("MOJO_TIMING time_series_decompose::trend_strength", _ns_trend_strength, _acc_trend_strength)
    var _acc_detect_period: Float64 = 0.0
    var _t0_detect_period = perf_counter_ns()
    for _ in range(N):
        _acc_detect_period += Float64(detect_period(_lf5, 5))
    var _t1_detect_period = perf_counter_ns()
    var _ns_detect_period = Float64(_t1_detect_period - _t0_detect_period) / Float64(N)
    print("MOJO_TIMING time_series_decompose::detect_period", _ns_detect_period, _acc_detect_period)
    var _acc_stl_like: Float64 = 0.0
    var _t0_stl_like = perf_counter_ns()
    for _ in range(N):
        var _r_stl_like = stl_like(_lf5, 5, 5)
        _acc_stl_like += Float64(len(_r_stl_like))
    var _t1_stl_like = perf_counter_ns()
    var _ns_stl_like = Float64(_t1_stl_like - _t0_stl_like) / Float64(N)
    print("MOJO_TIMING time_series_decompose::stl_like", _ns_stl_like, _acc_stl_like)
