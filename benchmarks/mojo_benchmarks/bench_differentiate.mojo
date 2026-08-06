"""bench_differentiate.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from differentiate import derivative_forward, derivative_central, derivative_backward, second_derivative, gradient, poly_derivative_coeffs
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_derivative_forward: Float64 = 0.0
    var _t0_derivative_forward = perf_counter_ns()
    for _ in range(N):
        var _r_derivative_forward = derivative_forward(_lf5, 0.5)
        _acc_derivative_forward += Float64(len(_r_derivative_forward))
    var _t1_derivative_forward = perf_counter_ns()
    var _ns_derivative_forward = Float64(_t1_derivative_forward - _t0_derivative_forward) / Float64(N)
    print("MOJO_TIMING differentiate::derivative_forward", _ns_derivative_forward, _acc_derivative_forward)
    var _result_derivative_forward = derivative_forward(_lf5, 0.5)
    var _summary_derivative_forward = _summary_list_float64(_result_derivative_forward)
    print("MOJO_RESULT differentiate::derivative_forward", _summary_derivative_forward)
    var _acc_derivative_central: Float64 = 0.0
    var _t0_derivative_central = perf_counter_ns()
    for _ in range(N):
        var _r_derivative_central = derivative_central(_lf5, 0.5)
        _acc_derivative_central += Float64(len(_r_derivative_central))
    var _t1_derivative_central = perf_counter_ns()
    var _ns_derivative_central = Float64(_t1_derivative_central - _t0_derivative_central) / Float64(N)
    print("MOJO_TIMING differentiate::derivative_central", _ns_derivative_central, _acc_derivative_central)
    var _result_derivative_central = derivative_central(_lf5, 0.5)
    var _summary_derivative_central = _summary_list_float64(_result_derivative_central)
    print("MOJO_RESULT differentiate::derivative_central", _summary_derivative_central)
    var _acc_derivative_backward: Float64 = 0.0
    var _t0_derivative_backward = perf_counter_ns()
    for _ in range(N):
        var _r_derivative_backward = derivative_backward(_lf5, 0.5)
        _acc_derivative_backward += Float64(len(_r_derivative_backward))
    var _t1_derivative_backward = perf_counter_ns()
    var _ns_derivative_backward = Float64(_t1_derivative_backward - _t0_derivative_backward) / Float64(N)
    print("MOJO_TIMING differentiate::derivative_backward", _ns_derivative_backward, _acc_derivative_backward)
    var _result_derivative_backward = derivative_backward(_lf5, 0.5)
    var _summary_derivative_backward = _summary_list_float64(_result_derivative_backward)
    print("MOJO_RESULT differentiate::derivative_backward", _summary_derivative_backward)
    var _acc_second_derivative: Float64 = 0.0
    var _t0_second_derivative = perf_counter_ns()
    for _ in range(N):
        var _r_second_derivative = second_derivative(_lf5, 0.5)
        _acc_second_derivative += Float64(len(_r_second_derivative))
    var _t1_second_derivative = perf_counter_ns()
    var _ns_second_derivative = Float64(_t1_second_derivative - _t0_second_derivative) / Float64(N)
    print("MOJO_TIMING differentiate::second_derivative", _ns_second_derivative, _acc_second_derivative)
    var _result_second_derivative = second_derivative(_lf5, 0.5)
    var _summary_second_derivative = _summary_list_float64(_result_second_derivative)
    print("MOJO_RESULT differentiate::second_derivative", _summary_second_derivative)
    var _acc_gradient: Float64 = 0.0
    var _t0_gradient = perf_counter_ns()
    for _ in range(N):
        var _r_gradient = gradient(_lf5, _lf5)
        _acc_gradient += Float64(len(_r_gradient))
    var _t1_gradient = perf_counter_ns()
    var _ns_gradient = Float64(_t1_gradient - _t0_gradient) / Float64(N)
    print("MOJO_TIMING differentiate::gradient", _ns_gradient, _acc_gradient)
    var _result_gradient = gradient(_lf5, _lf5)
    var _summary_gradient = _summary_list_float64(_result_gradient)
    print("MOJO_RESULT differentiate::gradient", _summary_gradient)
    var _acc_poly_derivative_coeffs: Float64 = 0.0
    var _t0_poly_derivative_coeffs = perf_counter_ns()
    for _ in range(N):
        var _r_poly_derivative_coeffs = poly_derivative_coeffs(_lf5)
        _acc_poly_derivative_coeffs += Float64(len(_r_poly_derivative_coeffs))
    var _t1_poly_derivative_coeffs = perf_counter_ns()
    var _ns_poly_derivative_coeffs = Float64(_t1_poly_derivative_coeffs - _t0_poly_derivative_coeffs) / Float64(N)
    print("MOJO_TIMING differentiate::poly_derivative_coeffs", _ns_poly_derivative_coeffs, _acc_poly_derivative_coeffs)
    var _result_poly_derivative_coeffs = poly_derivative_coeffs(_lf5)
    var _summary_poly_derivative_coeffs = _summary_list_float64(_result_poly_derivative_coeffs)
    print("MOJO_RESULT differentiate::poly_derivative_coeffs", _summary_poly_derivative_coeffs)
