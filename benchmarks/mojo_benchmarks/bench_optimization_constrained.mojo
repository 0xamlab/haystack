"""bench_optimization_constrained.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from optimization_constrained import eval_objective_c, eval_constraint, is_feasible_c, penalty_value, gradient_estimate, penalty_method, barrier_method, augmented_lagrangian_step
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

    var _acc_eval_objective_c: Float64 = 0.0
    var _t0_eval_objective_c = perf_counter_ns()
    for _ in range(N):
        _acc_eval_objective_c += eval_objective_c(_lf5, 5)
    var _t1_eval_objective_c = perf_counter_ns()
    var _ns_eval_objective_c = Float64(_t1_eval_objective_c - _t0_eval_objective_c) / Float64(N)
    print("MOJO_TIMING optimization_constrained::eval_objective_c", _ns_eval_objective_c, _acc_eval_objective_c)
    var _acc_eval_constraint: Float64 = 0.0
    var _t0_eval_constraint = perf_counter_ns()
    for _ in range(N):
        _acc_eval_constraint += eval_constraint(_lf5, 5)
    var _t1_eval_constraint = perf_counter_ns()
    var _ns_eval_constraint = Float64(_t1_eval_constraint - _t0_eval_constraint) / Float64(N)
    print("MOJO_TIMING optimization_constrained::eval_constraint", _ns_eval_constraint, _acc_eval_constraint)
    var _acc_is_feasible_c: Float64 = 0.0
    var _t0_is_feasible_c = perf_counter_ns()
    for _ in range(N):
        _acc_is_feasible_c += Float64(is_feasible_c(_lf5, _li5, 0.5))
    var _t1_is_feasible_c = perf_counter_ns()
    var _ns_is_feasible_c = Float64(_t1_is_feasible_c - _t0_is_feasible_c) / Float64(N)
    print("MOJO_TIMING optimization_constrained::is_feasible_c", _ns_is_feasible_c, _acc_is_feasible_c)
    var _acc_penalty_value: Float64 = 0.0
    var _t0_penalty_value = perf_counter_ns()
    for _ in range(N):
        _acc_penalty_value += penalty_value(_lf5, _li5)
    var _t1_penalty_value = perf_counter_ns()
    var _ns_penalty_value = Float64(_t1_penalty_value - _t0_penalty_value) / Float64(N)
    print("MOJO_TIMING optimization_constrained::penalty_value", _ns_penalty_value, _acc_penalty_value)
    var _acc_gradient_estimate: Float64 = 0.0
    var _t0_gradient_estimate = perf_counter_ns()
    for _ in range(N):
        var _r_gradient_estimate = gradient_estimate(_lf5, 5, _li5, 0.5, 0.5)
        _acc_gradient_estimate += Float64(len(_r_gradient_estimate))
    var _t1_gradient_estimate = perf_counter_ns()
    var _ns_gradient_estimate = Float64(_t1_gradient_estimate - _t0_gradient_estimate) / Float64(N)
    print("MOJO_TIMING optimization_constrained::gradient_estimate", _ns_gradient_estimate, _acc_gradient_estimate)
    var _acc_penalty_method: Float64 = 0.0
    var _t0_penalty_method = perf_counter_ns()
    for _ in range(N):
        var _r_penalty_method = penalty_method(_lf5, 5, _li5, 0.5, 5, 0.5)
        _acc_penalty_method += Float64(len(_r_penalty_method))
    var _t1_penalty_method = perf_counter_ns()
    var _ns_penalty_method = Float64(_t1_penalty_method - _t0_penalty_method) / Float64(N)
    print("MOJO_TIMING optimization_constrained::penalty_method", _ns_penalty_method, _acc_penalty_method)
    var _acc_barrier_method: Float64 = 0.0
    var _t0_barrier_method = perf_counter_ns()
    for _ in range(N):
        var _r_barrier_method = barrier_method(_lf5, 5, _li5, 0.5, 5, 0.5)
        _acc_barrier_method += Float64(len(_r_barrier_method))
    var _t1_barrier_method = perf_counter_ns()
    var _ns_barrier_method = Float64(_t1_barrier_method - _t0_barrier_method) / Float64(N)
    print("MOJO_TIMING optimization_constrained::barrier_method", _ns_barrier_method, _acc_barrier_method)
    var _acc_augmented_lagrangian_step: Float64 = 0.0
    var _t0_augmented_lagrangian_step = perf_counter_ns()
    for _ in range(N):
        var _r_augmented_lagrangian_step = augmented_lagrangian_step(_lf5, _lf5, 5, _li5, 0.5, 0.5)
        _acc_augmented_lagrangian_step += Float64(len(_r_augmented_lagrangian_step))
    var _t1_augmented_lagrangian_step = perf_counter_ns()
    var _ns_augmented_lagrangian_step = Float64(_t1_augmented_lagrangian_step - _t0_augmented_lagrangian_step) / Float64(N)
    print("MOJO_TIMING optimization_constrained::augmented_lagrangian_step", _ns_augmented_lagrangian_step, _acc_augmented_lagrangian_step)
