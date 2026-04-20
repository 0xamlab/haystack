"""bench_interpolate.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from interpolate import linear_interp, nearest_interp, cubic_spline_natural, lagrange_interp, interp_array, extrapolate_linear
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

    var _acc_linear_interp: Float64 = 0.0
    var _t0_linear_interp = perf_counter_ns()
    for _ in range(N):
        _acc_linear_interp += linear_interp(_lf5, _lf5, 0.5)
    var _t1_linear_interp = perf_counter_ns()
    var _ns_linear_interp = Float64(_t1_linear_interp - _t0_linear_interp) / Float64(N)
    print("MOJO_TIMING interpolate::linear_interp", _ns_linear_interp, _acc_linear_interp)
    var _acc_nearest_interp: Float64 = 0.0
    var _t0_nearest_interp = perf_counter_ns()
    for _ in range(N):
        _acc_nearest_interp += nearest_interp(_lf5, _lf5, 0.5)
    var _t1_nearest_interp = perf_counter_ns()
    var _ns_nearest_interp = Float64(_t1_nearest_interp - _t0_nearest_interp) / Float64(N)
    print("MOJO_TIMING interpolate::nearest_interp", _ns_nearest_interp, _acc_nearest_interp)
    var _acc_cubic_spline_natural: Float64 = 0.0
    var _t0_cubic_spline_natural = perf_counter_ns()
    for _ in range(N):
        _acc_cubic_spline_natural += cubic_spline_natural(_lf5, _lf5, 0.5)
    var _t1_cubic_spline_natural = perf_counter_ns()
    var _ns_cubic_spline_natural = Float64(_t1_cubic_spline_natural - _t0_cubic_spline_natural) / Float64(N)
    print("MOJO_TIMING interpolate::cubic_spline_natural", _ns_cubic_spline_natural, _acc_cubic_spline_natural)
    var _acc_lagrange_interp: Float64 = 0.0
    var _t0_lagrange_interp = perf_counter_ns()
    for _ in range(N):
        _acc_lagrange_interp += lagrange_interp(_lf5, _lf5, 0.5)
    var _t1_lagrange_interp = perf_counter_ns()
    var _ns_lagrange_interp = Float64(_t1_lagrange_interp - _t0_lagrange_interp) / Float64(N)
    print("MOJO_TIMING interpolate::lagrange_interp", _ns_lagrange_interp, _acc_lagrange_interp)
    var _acc_interp_array: Float64 = 0.0
    var _t0_interp_array = perf_counter_ns()
    for _ in range(N):
        var _r_interp_array = interp_array(_lf5, _lf5, _lf5, "test")
        _acc_interp_array += Float64(len(_r_interp_array))
    var _t1_interp_array = perf_counter_ns()
    var _ns_interp_array = Float64(_t1_interp_array - _t0_interp_array) / Float64(N)
    print("MOJO_TIMING interpolate::interp_array", _ns_interp_array, _acc_interp_array)
    var _acc_extrapolate_linear: Float64 = 0.0
    var _t0_extrapolate_linear = perf_counter_ns()
    for _ in range(N):
        _acc_extrapolate_linear += extrapolate_linear(_lf5, _lf5, 0.5)
    var _t1_extrapolate_linear = perf_counter_ns()
    var _ns_extrapolate_linear = Float64(_t1_extrapolate_linear - _t0_extrapolate_linear) / Float64(N)
    print("MOJO_TIMING interpolate::extrapolate_linear", _ns_extrapolate_linear, _acc_extrapolate_linear)
