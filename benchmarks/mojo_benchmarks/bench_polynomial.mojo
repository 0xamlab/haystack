"""bench_polynomial.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from polynomial import poly_eval, poly_add, poly_multiply, poly_derivative, poly_integral, poly_degree, quadratic_roots, poly_scale, poly_compose, poly_from_roots
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

    var _acc_poly_eval: Float64 = 0.0
    var _t0_poly_eval = perf_counter_ns()
    for _ in range(N):
        _acc_poly_eval += poly_eval(_lf5, 0.5)
    var _t1_poly_eval = perf_counter_ns()
    var _ns_poly_eval = Float64(_t1_poly_eval - _t0_poly_eval) / Float64(N)
    print("MOJO_TIMING polynomial::poly_eval", _ns_poly_eval, _acc_poly_eval)
    var _result_poly_eval = poly_eval(_lf5, 0.5)
    var _summary_poly_eval = _summary_float64(_result_poly_eval)
    print("MOJO_RESULT polynomial::poly_eval", _summary_poly_eval)
    var _acc_poly_add: Float64 = 0.0
    var _t0_poly_add = perf_counter_ns()
    for _ in range(N):
        var _r_poly_add = poly_add(_lf5, _lf5)
        _acc_poly_add += Float64(len(_r_poly_add))
    var _t1_poly_add = perf_counter_ns()
    var _ns_poly_add = Float64(_t1_poly_add - _t0_poly_add) / Float64(N)
    print("MOJO_TIMING polynomial::poly_add", _ns_poly_add, _acc_poly_add)
    var _result_poly_add = poly_add(_lf5, _lf5)
    var _summary_poly_add = _summary_list_float64(_result_poly_add)
    print("MOJO_RESULT polynomial::poly_add", _summary_poly_add)
    var _acc_poly_multiply: Float64 = 0.0
    var _t0_poly_multiply = perf_counter_ns()
    for _ in range(N):
        var _r_poly_multiply = poly_multiply(_lf5, _lf5)
        _acc_poly_multiply += Float64(len(_r_poly_multiply))
    var _t1_poly_multiply = perf_counter_ns()
    var _ns_poly_multiply = Float64(_t1_poly_multiply - _t0_poly_multiply) / Float64(N)
    print("MOJO_TIMING polynomial::poly_multiply", _ns_poly_multiply, _acc_poly_multiply)
    var _result_poly_multiply = poly_multiply(_lf5, _lf5)
    var _summary_poly_multiply = _summary_list_float64(_result_poly_multiply)
    print("MOJO_RESULT polynomial::poly_multiply", _summary_poly_multiply)
    var _acc_poly_derivative: Float64 = 0.0
    var _t0_poly_derivative = perf_counter_ns()
    for _ in range(N):
        var _r_poly_derivative = poly_derivative(_lf5)
        _acc_poly_derivative += Float64(len(_r_poly_derivative))
    var _t1_poly_derivative = perf_counter_ns()
    var _ns_poly_derivative = Float64(_t1_poly_derivative - _t0_poly_derivative) / Float64(N)
    print("MOJO_TIMING polynomial::poly_derivative", _ns_poly_derivative, _acc_poly_derivative)
    var _result_poly_derivative = poly_derivative(_lf5)
    var _summary_poly_derivative = _summary_list_float64(_result_poly_derivative)
    print("MOJO_RESULT polynomial::poly_derivative", _summary_poly_derivative)
    var _acc_poly_integral: Float64 = 0.0
    var _t0_poly_integral = perf_counter_ns()
    for _ in range(N):
        var _r_poly_integral = poly_integral(_lf5, 0.5)
        _acc_poly_integral += Float64(len(_r_poly_integral))
    var _t1_poly_integral = perf_counter_ns()
    var _ns_poly_integral = Float64(_t1_poly_integral - _t0_poly_integral) / Float64(N)
    print("MOJO_TIMING polynomial::poly_integral", _ns_poly_integral, _acc_poly_integral)
    var _result_poly_integral = poly_integral(_lf5, 0.5)
    var _summary_poly_integral = _summary_list_float64(_result_poly_integral)
    print("MOJO_RESULT polynomial::poly_integral", _summary_poly_integral)
    var _acc_poly_degree: Float64 = 0.0
    var _t0_poly_degree = perf_counter_ns()
    for _ in range(N):
        _acc_poly_degree += Float64(poly_degree(_lf5))
    var _t1_poly_degree = perf_counter_ns()
    var _ns_poly_degree = Float64(_t1_poly_degree - _t0_poly_degree) / Float64(N)
    print("MOJO_TIMING polynomial::poly_degree", _ns_poly_degree, _acc_poly_degree)
    var _result_poly_degree = poly_degree(_lf5)
    var _summary_poly_degree = _summary_int(_result_poly_degree)
    print("MOJO_RESULT polynomial::poly_degree", _summary_poly_degree)
    var _acc_quadratic_roots: Float64 = 0.0
    var _t0_quadratic_roots = perf_counter_ns()
    for _ in range(N):
        var _r_quadratic_roots = quadratic_roots(0.5, 0.5, 0.5)
        _acc_quadratic_roots += Float64(len(_r_quadratic_roots))
    var _t1_quadratic_roots = perf_counter_ns()
    var _ns_quadratic_roots = Float64(_t1_quadratic_roots - _t0_quadratic_roots) / Float64(N)
    print("MOJO_TIMING polynomial::quadratic_roots", _ns_quadratic_roots, _acc_quadratic_roots)
    var _result_quadratic_roots = quadratic_roots(0.5, 0.5, 0.5)
    var _summary_quadratic_roots = _summary_list_float64(_result_quadratic_roots)
    print("MOJO_RESULT polynomial::quadratic_roots", _summary_quadratic_roots)
    var _acc_poly_scale: Float64 = 0.0
    var _t0_poly_scale = perf_counter_ns()
    for _ in range(N):
        var _r_poly_scale = poly_scale(_lf5, 0.5)
        _acc_poly_scale += Float64(len(_r_poly_scale))
    var _t1_poly_scale = perf_counter_ns()
    var _ns_poly_scale = Float64(_t1_poly_scale - _t0_poly_scale) / Float64(N)
    print("MOJO_TIMING polynomial::poly_scale", _ns_poly_scale, _acc_poly_scale)
    var _result_poly_scale = poly_scale(_lf5, 0.5)
    var _summary_poly_scale = _summary_list_float64(_result_poly_scale)
    print("MOJO_RESULT polynomial::poly_scale", _summary_poly_scale)
    var _acc_poly_compose: Float64 = 0.0
    var _t0_poly_compose = perf_counter_ns()
    for _ in range(N):
        var _r_poly_compose = poly_compose(_lf5, _lf5)
        _acc_poly_compose += Float64(len(_r_poly_compose))
    var _t1_poly_compose = perf_counter_ns()
    var _ns_poly_compose = Float64(_t1_poly_compose - _t0_poly_compose) / Float64(N)
    print("MOJO_TIMING polynomial::poly_compose", _ns_poly_compose, _acc_poly_compose)
    var _result_poly_compose = poly_compose(_lf5, _lf5)
    var _summary_poly_compose = _summary_list_float64(_result_poly_compose)
    print("MOJO_RESULT polynomial::poly_compose", _summary_poly_compose)
    var _acc_poly_from_roots: Float64 = 0.0
    var _t0_poly_from_roots = perf_counter_ns()
    for _ in range(N):
        var _r_poly_from_roots = poly_from_roots(_lf5)
        _acc_poly_from_roots += Float64(len(_r_poly_from_roots))
    var _t1_poly_from_roots = perf_counter_ns()
    var _ns_poly_from_roots = Float64(_t1_poly_from_roots - _t0_poly_from_roots) / Float64(N)
    print("MOJO_TIMING polynomial::poly_from_roots", _ns_poly_from_roots, _acc_poly_from_roots)
    var _result_poly_from_roots = poly_from_roots(_lf5)
    var _summary_poly_from_roots = _summary_list_float64(_result_poly_from_roots)
    print("MOJO_RESULT polynomial::poly_from_roots", _summary_poly_from_roots)
