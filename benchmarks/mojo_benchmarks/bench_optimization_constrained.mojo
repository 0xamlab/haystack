"""bench_optimization_constrained.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from optimization_constrained import eval_objective_c, eval_constraint, is_feasible_c, penalty_value, gradient_estimate, penalty_method, barrier_method, augmented_lagrangian_step
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

    var _acc_eval_objective_c: Float64 = 0.0
    var _t0_eval_objective_c = perf_counter_ns()
    for _ in range(N):
        _acc_eval_objective_c += eval_objective_c(_lf5, 5)
    var _t1_eval_objective_c = perf_counter_ns()
    var _ns_eval_objective_c = Float64(_t1_eval_objective_c - _t0_eval_objective_c) / Float64(N)
    print("MOJO_TIMING optimization_constrained::eval_objective_c", _ns_eval_objective_c, _acc_eval_objective_c)
    var _result_eval_objective_c = eval_objective_c(_lf5, 5)
    var _summary_eval_objective_c = _summary_float64(_result_eval_objective_c)
    print("MOJO_RESULT optimization_constrained::eval_objective_c", _summary_eval_objective_c)
    var _acc_eval_constraint: Float64 = 0.0
    var _t0_eval_constraint = perf_counter_ns()
    for _ in range(N):
        _acc_eval_constraint += eval_constraint(_lf5, 5)
    var _t1_eval_constraint = perf_counter_ns()
    var _ns_eval_constraint = Float64(_t1_eval_constraint - _t0_eval_constraint) / Float64(N)
    print("MOJO_TIMING optimization_constrained::eval_constraint", _ns_eval_constraint, _acc_eval_constraint)
    var _result_eval_constraint = eval_constraint(_lf5, 5)
    var _summary_eval_constraint = _summary_float64(_result_eval_constraint)
    print("MOJO_RESULT optimization_constrained::eval_constraint", _summary_eval_constraint)
    var _acc_is_feasible_c: Float64 = 0.0
    var _t0_is_feasible_c = perf_counter_ns()
    for _ in range(N):
        _acc_is_feasible_c += Float64(is_feasible_c(_lf5, _li5, 0.5))
    var _t1_is_feasible_c = perf_counter_ns()
    var _ns_is_feasible_c = Float64(_t1_is_feasible_c - _t0_is_feasible_c) / Float64(N)
    print("MOJO_TIMING optimization_constrained::is_feasible_c", _ns_is_feasible_c, _acc_is_feasible_c)
    var _result_is_feasible_c = is_feasible_c(_lf5, _li5, 0.5)
    var _summary_is_feasible_c = _summary_bool(_result_is_feasible_c)
    print("MOJO_RESULT optimization_constrained::is_feasible_c", _summary_is_feasible_c)
    var _acc_penalty_value: Float64 = 0.0
    var _t0_penalty_value = perf_counter_ns()
    for _ in range(N):
        _acc_penalty_value += penalty_value(_lf5, _li5)
    var _t1_penalty_value = perf_counter_ns()
    var _ns_penalty_value = Float64(_t1_penalty_value - _t0_penalty_value) / Float64(N)
    print("MOJO_TIMING optimization_constrained::penalty_value", _ns_penalty_value, _acc_penalty_value)
    var _result_penalty_value = penalty_value(_lf5, _li5)
    var _summary_penalty_value = _summary_float64(_result_penalty_value)
    print("MOJO_RESULT optimization_constrained::penalty_value", _summary_penalty_value)
    var _acc_gradient_estimate: Float64 = 0.0
    var _t0_gradient_estimate = perf_counter_ns()
    for _ in range(N):
        var _r_gradient_estimate = gradient_estimate(_lf5, 5, _li5, 0.5, 0.5)
        _acc_gradient_estimate += Float64(len(_r_gradient_estimate))
    var _t1_gradient_estimate = perf_counter_ns()
    var _ns_gradient_estimate = Float64(_t1_gradient_estimate - _t0_gradient_estimate) / Float64(N)
    print("MOJO_TIMING optimization_constrained::gradient_estimate", _ns_gradient_estimate, _acc_gradient_estimate)
    var _result_gradient_estimate = gradient_estimate(_lf5, 5, _li5, 0.5, 0.5)
    var _summary_gradient_estimate = _summary_list_float64(_result_gradient_estimate)
    print("MOJO_RESULT optimization_constrained::gradient_estimate", _summary_gradient_estimate)
    var _acc_penalty_method: Float64 = 0.0
    var _t0_penalty_method = perf_counter_ns()
    for _ in range(N):
        var _r_penalty_method = penalty_method(_lf5, 5, _li5, 0.5, 5, 0.5)
        _acc_penalty_method += Float64(len(_r_penalty_method))
    var _t1_penalty_method = perf_counter_ns()
    var _ns_penalty_method = Float64(_t1_penalty_method - _t0_penalty_method) / Float64(N)
    print("MOJO_TIMING optimization_constrained::penalty_method", _ns_penalty_method, _acc_penalty_method)
    var _result_penalty_method = penalty_method(_lf5, 5, _li5, 0.5, 5, 0.5)
    var _summary_penalty_method = _summary_list_float64(_result_penalty_method)
    print("MOJO_RESULT optimization_constrained::penalty_method", _summary_penalty_method)
    var _acc_barrier_method: Float64 = 0.0
    var _t0_barrier_method = perf_counter_ns()
    for _ in range(N):
        var _r_barrier_method = barrier_method(_lf5, 5, _li5, 0.5, 5, 0.5)
        _acc_barrier_method += Float64(len(_r_barrier_method))
    var _t1_barrier_method = perf_counter_ns()
    var _ns_barrier_method = Float64(_t1_barrier_method - _t0_barrier_method) / Float64(N)
    print("MOJO_TIMING optimization_constrained::barrier_method", _ns_barrier_method, _acc_barrier_method)
    var _result_barrier_method = barrier_method(_lf5, 5, _li5, 0.5, 5, 0.5)
    var _summary_barrier_method = _summary_list_float64(_result_barrier_method)
    print("MOJO_RESULT optimization_constrained::barrier_method", _summary_barrier_method)
    var _acc_augmented_lagrangian_step: Float64 = 0.0
    var _t0_augmented_lagrangian_step = perf_counter_ns()
    for _ in range(N):
        var _r_augmented_lagrangian_step = augmented_lagrangian_step(_lf5, _lf5, 5, _li5, 0.5, 0.5)
        _acc_augmented_lagrangian_step += Float64(len(_r_augmented_lagrangian_step))
    var _t1_augmented_lagrangian_step = perf_counter_ns()
    var _ns_augmented_lagrangian_step = Float64(_t1_augmented_lagrangian_step - _t0_augmented_lagrangian_step) / Float64(N)
    print("MOJO_TIMING optimization_constrained::augmented_lagrangian_step", _ns_augmented_lagrangian_step, _acc_augmented_lagrangian_step)
    var _result_augmented_lagrangian_step = augmented_lagrangian_step(_lf5, _lf5, 5, _li5, 0.5, 0.5)
    var _summary_augmented_lagrangian_step = _summary_list_list_float64(_result_augmented_lagrangian_step)
    print("MOJO_RESULT optimization_constrained::augmented_lagrangian_step", _summary_augmented_lagrangian_step)
