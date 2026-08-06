"""bench_root_finding.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from root_finding import eval_func, eval_deriv, bisection, newton_raphson, secant_method, fixed_point, regula_falsi, bracket_root, convergence_order
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

    var _acc_eval_func: Float64 = 0.0
    var _t0_eval_func = perf_counter_ns()
    for _ in range(N):
        _acc_eval_func += eval_func(0.5, 5)
    var _t1_eval_func = perf_counter_ns()
    var _ns_eval_func = Float64(_t1_eval_func - _t0_eval_func) / Float64(N)
    print("MOJO_TIMING root_finding::eval_func", _ns_eval_func, _acc_eval_func)
    var _result_eval_func = eval_func(0.5, 5)
    var _summary_eval_func = _summary_float64(_result_eval_func)
    print("MOJO_RESULT root_finding::eval_func", _summary_eval_func)
    var _acc_eval_deriv: Float64 = 0.0
    var _t0_eval_deriv = perf_counter_ns()
    for _ in range(N):
        _acc_eval_deriv += eval_deriv(0.5, 5)
    var _t1_eval_deriv = perf_counter_ns()
    var _ns_eval_deriv = Float64(_t1_eval_deriv - _t0_eval_deriv) / Float64(N)
    print("MOJO_TIMING root_finding::eval_deriv", _ns_eval_deriv, _acc_eval_deriv)
    var _result_eval_deriv = eval_deriv(0.5, 5)
    var _summary_eval_deriv = _summary_float64(_result_eval_deriv)
    print("MOJO_RESULT root_finding::eval_deriv", _summary_eval_deriv)
    var _acc_bisection: Float64 = 0.0
    var _t0_bisection = perf_counter_ns()
    for _ in range(N):
        _acc_bisection += bisection(0.5, 0.5, 5, 0.5, 5)
    var _t1_bisection = perf_counter_ns()
    var _ns_bisection = Float64(_t1_bisection - _t0_bisection) / Float64(N)
    print("MOJO_TIMING root_finding::bisection", _ns_bisection, _acc_bisection)
    var _result_bisection = bisection(0.5, 0.5, 5, 0.5, 5)
    var _summary_bisection = _summary_float64(_result_bisection)
    print("MOJO_RESULT root_finding::bisection", _summary_bisection)
    var _acc_newton_raphson: Float64 = 0.0
    var _t0_newton_raphson = perf_counter_ns()
    for _ in range(N):
        _acc_newton_raphson += newton_raphson(0.5, 5, 0.5, 5)
    var _t1_newton_raphson = perf_counter_ns()
    var _ns_newton_raphson = Float64(_t1_newton_raphson - _t0_newton_raphson) / Float64(N)
    print("MOJO_TIMING root_finding::newton_raphson", _ns_newton_raphson, _acc_newton_raphson)
    var _result_newton_raphson = newton_raphson(0.5, 5, 0.5, 5)
    var _summary_newton_raphson = _summary_float64(_result_newton_raphson)
    print("MOJO_RESULT root_finding::newton_raphson", _summary_newton_raphson)
    var _acc_secant_method: Float64 = 0.0
    var _t0_secant_method = perf_counter_ns()
    for _ in range(N):
        _acc_secant_method += secant_method(0.5, 0.5, 5, 0.5, 5)
    var _t1_secant_method = perf_counter_ns()
    var _ns_secant_method = Float64(_t1_secant_method - _t0_secant_method) / Float64(N)
    print("MOJO_TIMING root_finding::secant_method", _ns_secant_method, _acc_secant_method)
    var _result_secant_method = secant_method(0.5, 0.5, 5, 0.5, 5)
    var _summary_secant_method = _summary_float64(_result_secant_method)
    print("MOJO_RESULT root_finding::secant_method", _summary_secant_method)
    var _acc_fixed_point: Float64 = 0.0
    var _t0_fixed_point = perf_counter_ns()
    for _ in range(N):
        _acc_fixed_point += fixed_point(0.5, 5, 0.5, 5)
    var _t1_fixed_point = perf_counter_ns()
    var _ns_fixed_point = Float64(_t1_fixed_point - _t0_fixed_point) / Float64(N)
    print("MOJO_TIMING root_finding::fixed_point", _ns_fixed_point, _acc_fixed_point)
    var _result_fixed_point = fixed_point(0.5, 5, 0.5, 5)
    var _summary_fixed_point = _summary_float64(_result_fixed_point)
    print("MOJO_RESULT root_finding::fixed_point", _summary_fixed_point)
    var _acc_regula_falsi: Float64 = 0.0
    var _t0_regula_falsi = perf_counter_ns()
    for _ in range(N):
        _acc_regula_falsi += regula_falsi(-1.0, 1.0, 0, 0.5, 5)
    var _t1_regula_falsi = perf_counter_ns()
    var _ns_regula_falsi = Float64(_t1_regula_falsi - _t0_regula_falsi) / Float64(N)
    print("MOJO_TIMING root_finding::regula_falsi", _ns_regula_falsi, _acc_regula_falsi)
    var _result_regula_falsi = regula_falsi(-1.0, 1.0, 0, 0.5, 5)
    var _summary_regula_falsi = _summary_float64(_result_regula_falsi)
    print("MOJO_RESULT root_finding::regula_falsi", _summary_regula_falsi)
    var _acc_bracket_root: Float64 = 0.0
    var _t0_bracket_root = perf_counter_ns()
    for _ in range(N):
        var _r_bracket_root = bracket_root(5, 0.5, 0.5, 5)
        _acc_bracket_root += Float64(len(_r_bracket_root))
    var _t1_bracket_root = perf_counter_ns()
    var _ns_bracket_root = Float64(_t1_bracket_root - _t0_bracket_root) / Float64(N)
    print("MOJO_TIMING root_finding::bracket_root", _ns_bracket_root, _acc_bracket_root)
    var _result_bracket_root = bracket_root(5, 0.5, 0.5, 5)
    var _summary_bracket_root = _summary_list_float64(_result_bracket_root)
    print("MOJO_RESULT root_finding::bracket_root", _summary_bracket_root)
    var _acc_convergence_order: Float64 = 0.0
    var _t0_convergence_order = perf_counter_ns()
    for _ in range(N):
        _acc_convergence_order += convergence_order(_lf5)
    var _t1_convergence_order = perf_counter_ns()
    var _ns_convergence_order = Float64(_t1_convergence_order - _t0_convergence_order) / Float64(N)
    print("MOJO_TIMING root_finding::convergence_order", _ns_convergence_order, _acc_convergence_order)
    var _result_convergence_order = convergence_order(_lf5)
    var _summary_convergence_order = _summary_float64(_result_convergence_order)
    print("MOJO_RESULT root_finding::convergence_order", _summary_convergence_order)
