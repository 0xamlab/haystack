"""bench_convex.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from convex import eval_function, compute_gradient, l2_norm, vector_sub, proximal_l1, line_search_backtrack, gradient_descent, projected_gradient_descent, adam_optimizer
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

    var _acc_eval_function: Float64 = 0.0
    var _t0_eval_function = perf_counter_ns()
    for _ in range(N):
        _acc_eval_function += eval_function(_lf5, 5)
    var _t1_eval_function = perf_counter_ns()
    var _ns_eval_function = Float64(_t1_eval_function - _t0_eval_function) / Float64(N)
    print("MOJO_TIMING convex::eval_function", _ns_eval_function, _acc_eval_function)
    var _result_eval_function = eval_function(_lf5, 5)
    var _summary_eval_function = _summary_float64(_result_eval_function)
    print("MOJO_RESULT convex::eval_function", _summary_eval_function)
    var _acc_compute_gradient: Float64 = 0.0
    var _t0_compute_gradient = perf_counter_ns()
    for _ in range(N):
        var _r_compute_gradient = compute_gradient(_lf5, 5)
        _acc_compute_gradient += Float64(len(_r_compute_gradient))
    var _t1_compute_gradient = perf_counter_ns()
    var _ns_compute_gradient = Float64(_t1_compute_gradient - _t0_compute_gradient) / Float64(N)
    print("MOJO_TIMING convex::compute_gradient", _ns_compute_gradient, _acc_compute_gradient)
    var _result_compute_gradient = compute_gradient(_lf5, 5)
    var _summary_compute_gradient = _summary_list_float64(_result_compute_gradient)
    print("MOJO_RESULT convex::compute_gradient", _summary_compute_gradient)
    var _acc_l2_norm: Float64 = 0.0
    var _t0_l2_norm = perf_counter_ns()
    for _ in range(N):
        _acc_l2_norm += l2_norm(_lf5)
    var _t1_l2_norm = perf_counter_ns()
    var _ns_l2_norm = Float64(_t1_l2_norm - _t0_l2_norm) / Float64(N)
    print("MOJO_TIMING convex::l2_norm", _ns_l2_norm, _acc_l2_norm)
    var _result_l2_norm = l2_norm(_lf5)
    var _summary_l2_norm = _summary_float64(_result_l2_norm)
    print("MOJO_RESULT convex::l2_norm", _summary_l2_norm)
    var _acc_vector_sub: Float64 = 0.0
    var _t0_vector_sub = perf_counter_ns()
    for _ in range(N):
        var _r_vector_sub = vector_sub(_lf5, _lf5)
        _acc_vector_sub += Float64(len(_r_vector_sub))
    var _t1_vector_sub = perf_counter_ns()
    var _ns_vector_sub = Float64(_t1_vector_sub - _t0_vector_sub) / Float64(N)
    print("MOJO_TIMING convex::vector_sub", _ns_vector_sub, _acc_vector_sub)
    var _result_vector_sub = vector_sub(_lf5, _lf5)
    var _summary_vector_sub = _summary_list_float64(_result_vector_sub)
    print("MOJO_RESULT convex::vector_sub", _summary_vector_sub)
    var _acc_proximal_l1: Float64 = 0.0
    var _t0_proximal_l1 = perf_counter_ns()
    for _ in range(N):
        var _r_proximal_l1 = proximal_l1(_lf5, 0.5)
        _acc_proximal_l1 += Float64(len(_r_proximal_l1))
    var _t1_proximal_l1 = perf_counter_ns()
    var _ns_proximal_l1 = Float64(_t1_proximal_l1 - _t0_proximal_l1) / Float64(N)
    print("MOJO_TIMING convex::proximal_l1", _ns_proximal_l1, _acc_proximal_l1)
    var _result_proximal_l1 = proximal_l1(_lf5, 0.5)
    var _summary_proximal_l1 = _summary_list_float64(_result_proximal_l1)
    print("MOJO_RESULT convex::proximal_l1", _summary_proximal_l1)
    var _acc_line_search_backtrack: Float64 = 0.0
    var _t0_line_search_backtrack = perf_counter_ns()
    for _ in range(N):
        _acc_line_search_backtrack += line_search_backtrack(_lf5, _lf5, 5, 0.5, 0.5, 0.5)
    var _t1_line_search_backtrack = perf_counter_ns()
    var _ns_line_search_backtrack = Float64(_t1_line_search_backtrack - _t0_line_search_backtrack) / Float64(N)
    print("MOJO_TIMING convex::line_search_backtrack", _ns_line_search_backtrack, _acc_line_search_backtrack)
    var _result_line_search_backtrack = line_search_backtrack(_lf5, _lf5, 5, 0.5, 0.5, 0.5)
    var _summary_line_search_backtrack = _summary_float64(_result_line_search_backtrack)
    print("MOJO_RESULT convex::line_search_backtrack", _summary_line_search_backtrack)
    var _acc_gradient_descent: Float64 = 0.0
    var _t0_gradient_descent = perf_counter_ns()
    for _ in range(N):
        var _r_gradient_descent = gradient_descent(_lf5, 0.5, 5, 0.5, 5)
        _acc_gradient_descent += Float64(len(_r_gradient_descent))
    var _t1_gradient_descent = perf_counter_ns()
    var _ns_gradient_descent = Float64(_t1_gradient_descent - _t0_gradient_descent) / Float64(N)
    print("MOJO_TIMING convex::gradient_descent", _ns_gradient_descent, _acc_gradient_descent)
    var _result_gradient_descent = gradient_descent(_lf5, 0.5, 5, 0.5, 5)
    var _summary_gradient_descent = _summary_list_float64(_result_gradient_descent)
    print("MOJO_RESULT convex::gradient_descent", _summary_gradient_descent)
    var _acc_projected_gradient_descent: Float64 = 0.0
    var _t0_projected_gradient_descent = perf_counter_ns()
    for _ in range(N):
        var _r_projected_gradient_descent = projected_gradient_descent(_lf5, 0.5, 5, 0.5, 0.5, 5)
        _acc_projected_gradient_descent += Float64(len(_r_projected_gradient_descent))
    var _t1_projected_gradient_descent = perf_counter_ns()
    var _ns_projected_gradient_descent = Float64(_t1_projected_gradient_descent - _t0_projected_gradient_descent) / Float64(N)
    print("MOJO_TIMING convex::projected_gradient_descent", _ns_projected_gradient_descent, _acc_projected_gradient_descent)
    var _result_projected_gradient_descent = projected_gradient_descent(_lf5, 0.5, 5, 0.5, 0.5, 5)
    var _summary_projected_gradient_descent = _summary_list_float64(_result_projected_gradient_descent)
    print("MOJO_RESULT convex::projected_gradient_descent", _summary_projected_gradient_descent)
    var _acc_adam_optimizer: Float64 = 0.0
    var _t0_adam_optimizer = perf_counter_ns()
    for _ in range(N):
        var _r_adam_optimizer = adam_optimizer(_lf5, 0.5, 5, 5)
        _acc_adam_optimizer += Float64(len(_r_adam_optimizer))
    var _t1_adam_optimizer = perf_counter_ns()
    var _ns_adam_optimizer = Float64(_t1_adam_optimizer - _t0_adam_optimizer) / Float64(N)
    print("MOJO_TIMING convex::adam_optimizer", _ns_adam_optimizer, _acc_adam_optimizer)
    var _result_adam_optimizer = adam_optimizer(_lf5, 0.5, 5, 5)
    var _summary_adam_optimizer = _summary_list_float64(_result_adam_optimizer)
    print("MOJO_RESULT convex::adam_optimizer", _summary_adam_optimizer)
