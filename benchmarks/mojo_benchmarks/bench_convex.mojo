"""bench_convex.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from convex import eval_function, compute_gradient, l2_norm, vector_sub, proximal_l1, line_search_backtrack, gradient_descent, projected_gradient_descent, adam_optimizer
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

    var _acc_eval_function: Float64 = 0.0
    var _t0_eval_function = perf_counter_ns()
    for _ in range(N):
        _acc_eval_function += eval_function(_lf5, 5)
    var _t1_eval_function = perf_counter_ns()
    var _ns_eval_function = Float64(_t1_eval_function - _t0_eval_function) / Float64(N)
    print("MOJO_TIMING convex::eval_function", _ns_eval_function, _acc_eval_function)
    var _acc_compute_gradient: Float64 = 0.0
    var _t0_compute_gradient = perf_counter_ns()
    for _ in range(N):
        var _r_compute_gradient = compute_gradient(_lf5, 5)
        _acc_compute_gradient += Float64(len(_r_compute_gradient))
    var _t1_compute_gradient = perf_counter_ns()
    var _ns_compute_gradient = Float64(_t1_compute_gradient - _t0_compute_gradient) / Float64(N)
    print("MOJO_TIMING convex::compute_gradient", _ns_compute_gradient, _acc_compute_gradient)
    var _acc_l2_norm: Float64 = 0.0
    var _t0_l2_norm = perf_counter_ns()
    for _ in range(N):
        _acc_l2_norm += l2_norm(_lf5)
    var _t1_l2_norm = perf_counter_ns()
    var _ns_l2_norm = Float64(_t1_l2_norm - _t0_l2_norm) / Float64(N)
    print("MOJO_TIMING convex::l2_norm", _ns_l2_norm, _acc_l2_norm)
    var _acc_vector_sub: Float64 = 0.0
    var _t0_vector_sub = perf_counter_ns()
    for _ in range(N):
        var _r_vector_sub = vector_sub(_lf5, _lf5)
        _acc_vector_sub += Float64(len(_r_vector_sub))
    var _t1_vector_sub = perf_counter_ns()
    var _ns_vector_sub = Float64(_t1_vector_sub - _t0_vector_sub) / Float64(N)
    print("MOJO_TIMING convex::vector_sub", _ns_vector_sub, _acc_vector_sub)
    var _acc_proximal_l1: Float64 = 0.0
    var _t0_proximal_l1 = perf_counter_ns()
    for _ in range(N):
        var _r_proximal_l1 = proximal_l1(_lf5, 0.5)
        _acc_proximal_l1 += Float64(len(_r_proximal_l1))
    var _t1_proximal_l1 = perf_counter_ns()
    var _ns_proximal_l1 = Float64(_t1_proximal_l1 - _t0_proximal_l1) / Float64(N)
    print("MOJO_TIMING convex::proximal_l1", _ns_proximal_l1, _acc_proximal_l1)
    var _acc_line_search_backtrack: Float64 = 0.0
    var _t0_line_search_backtrack = perf_counter_ns()
    for _ in range(N):
        _acc_line_search_backtrack += line_search_backtrack(_lf5, _lf5, 5, 0.5, 0.5, 0.5)
    var _t1_line_search_backtrack = perf_counter_ns()
    var _ns_line_search_backtrack = Float64(_t1_line_search_backtrack - _t0_line_search_backtrack) / Float64(N)
    print("MOJO_TIMING convex::line_search_backtrack", _ns_line_search_backtrack, _acc_line_search_backtrack)
    var _acc_gradient_descent: Float64 = 0.0
    var _t0_gradient_descent = perf_counter_ns()
    for _ in range(N):
        var _r_gradient_descent = gradient_descent(_lf5, 0.5, 5, 0.5, 5)
        _acc_gradient_descent += Float64(len(_r_gradient_descent))
    var _t1_gradient_descent = perf_counter_ns()
    var _ns_gradient_descent = Float64(_t1_gradient_descent - _t0_gradient_descent) / Float64(N)
    print("MOJO_TIMING convex::gradient_descent", _ns_gradient_descent, _acc_gradient_descent)
    var _acc_projected_gradient_descent: Float64 = 0.0
    var _t0_projected_gradient_descent = perf_counter_ns()
    for _ in range(N):
        var _r_projected_gradient_descent = projected_gradient_descent(_lf5, 0.5, 5, 0.5, 0.5, 5)
        _acc_projected_gradient_descent += Float64(len(_r_projected_gradient_descent))
    var _t1_projected_gradient_descent = perf_counter_ns()
    var _ns_projected_gradient_descent = Float64(_t1_projected_gradient_descent - _t0_projected_gradient_descent) / Float64(N)
    print("MOJO_TIMING convex::projected_gradient_descent", _ns_projected_gradient_descent, _acc_projected_gradient_descent)
    var _acc_adam_optimizer: Float64 = 0.0
    var _t0_adam_optimizer = perf_counter_ns()
    for _ in range(N):
        var _r_adam_optimizer = adam_optimizer(_lf5, 0.5, 5, 5)
        _acc_adam_optimizer += Float64(len(_r_adam_optimizer))
    var _t1_adam_optimizer = perf_counter_ns()
    var _ns_adam_optimizer = Float64(_t1_adam_optimizer - _t0_adam_optimizer) / Float64(N)
    print("MOJO_TIMING convex::adam_optimizer", _ns_adam_optimizer, _acc_adam_optimizer)
