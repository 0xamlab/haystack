"""bench_interpolate.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from interpolate import linear_interp, nearest_interp, cubic_spline_natural, lagrange_interp, interp_array, extrapolate_linear
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_linear_interp = linear_interp(_lf5, _lf5, 0.5)
    var _summary_linear_interp = _summary_float64(_result_linear_interp)
    print("MOJO_RESULT interpolate::linear_interp", _summary_linear_interp)
    var _acc_nearest_interp: Float64 = 0.0
    var _t0_nearest_interp = perf_counter_ns()
    for _ in range(N):
        _acc_nearest_interp += nearest_interp(_lf5, _lf5, 0.5)
    var _t1_nearest_interp = perf_counter_ns()
    var _ns_nearest_interp = Float64(_t1_nearest_interp - _t0_nearest_interp) / Float64(N)
    print("MOJO_TIMING interpolate::nearest_interp", _ns_nearest_interp, _acc_nearest_interp)
    var _result_nearest_interp = nearest_interp(_lf5, _lf5, 0.5)
    var _summary_nearest_interp = _summary_float64(_result_nearest_interp)
    print("MOJO_RESULT interpolate::nearest_interp", _summary_nearest_interp)
    var _acc_cubic_spline_natural: Float64 = 0.0
    var _t0_cubic_spline_natural = perf_counter_ns()
    for _ in range(N):
        _acc_cubic_spline_natural += cubic_spline_natural(_lf5, _lf5, 0.5)
    var _t1_cubic_spline_natural = perf_counter_ns()
    var _ns_cubic_spline_natural = Float64(_t1_cubic_spline_natural - _t0_cubic_spline_natural) / Float64(N)
    print("MOJO_TIMING interpolate::cubic_spline_natural", _ns_cubic_spline_natural, _acc_cubic_spline_natural)
    var _result_cubic_spline_natural = cubic_spline_natural(_lf5, _lf5, 0.5)
    var _summary_cubic_spline_natural = _summary_float64(_result_cubic_spline_natural)
    print("MOJO_RESULT interpolate::cubic_spline_natural", _summary_cubic_spline_natural)
    var _acc_lagrange_interp: Float64 = 0.0
    var _t0_lagrange_interp = perf_counter_ns()
    for _ in range(N):
        _acc_lagrange_interp += lagrange_interp(_lf5, _lf5, 0.5)
    var _t1_lagrange_interp = perf_counter_ns()
    var _ns_lagrange_interp = Float64(_t1_lagrange_interp - _t0_lagrange_interp) / Float64(N)
    print("MOJO_TIMING interpolate::lagrange_interp", _ns_lagrange_interp, _acc_lagrange_interp)
    var _result_lagrange_interp = lagrange_interp(_lf5, _lf5, 0.5)
    var _summary_lagrange_interp = _summary_float64(_result_lagrange_interp)
    print("MOJO_RESULT interpolate::lagrange_interp", _summary_lagrange_interp)
    var _acc_interp_array: Float64 = 0.0
    var _t0_interp_array = perf_counter_ns()
    for _ in range(N):
        var _r_interp_array = interp_array(_lf5, _lf5, _lf5, "test")
        _acc_interp_array += Float64(len(_r_interp_array))
    var _t1_interp_array = perf_counter_ns()
    var _ns_interp_array = Float64(_t1_interp_array - _t0_interp_array) / Float64(N)
    print("MOJO_TIMING interpolate::interp_array", _ns_interp_array, _acc_interp_array)
    var _result_interp_array = interp_array(_lf5, _lf5, _lf5, "test")
    var _summary_interp_array = _summary_list_float64(_result_interp_array)
    print("MOJO_RESULT interpolate::interp_array", _summary_interp_array)
    var _acc_extrapolate_linear: Float64 = 0.0
    var _t0_extrapolate_linear = perf_counter_ns()
    for _ in range(N):
        _acc_extrapolate_linear += extrapolate_linear(_lf5, _lf5, 0.5)
    var _t1_extrapolate_linear = perf_counter_ns()
    var _ns_extrapolate_linear = Float64(_t1_extrapolate_linear - _t0_extrapolate_linear) / Float64(N)
    print("MOJO_TIMING interpolate::extrapolate_linear", _ns_extrapolate_linear, _acc_extrapolate_linear)
    var _result_extrapolate_linear = extrapolate_linear(_lf5, _lf5, 0.5)
    var _summary_extrapolate_linear = _summary_float64(_result_extrapolate_linear)
    print("MOJO_RESULT interpolate::extrapolate_linear", _summary_extrapolate_linear)
