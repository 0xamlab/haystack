"""bench_root_finding.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from root_finding import eval_func, eval_deriv, bisection, newton_raphson, secant_method, fixed_point, regula_falsi, bracket_root, convergence_order
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

    var _acc_eval_func: Float64 = 0.0
    var _t0_eval_func = perf_counter_ns()
    for _ in range(N):
        _acc_eval_func += eval_func(0.5, 5)
    var _t1_eval_func = perf_counter_ns()
    var _ns_eval_func = Float64(_t1_eval_func - _t0_eval_func) / Float64(N)
    print("MOJO_TIMING root_finding::eval_func", _ns_eval_func, _acc_eval_func)
    var _acc_eval_deriv: Float64 = 0.0
    var _t0_eval_deriv = perf_counter_ns()
    for _ in range(N):
        _acc_eval_deriv += eval_deriv(0.5, 5)
    var _t1_eval_deriv = perf_counter_ns()
    var _ns_eval_deriv = Float64(_t1_eval_deriv - _t0_eval_deriv) / Float64(N)
    print("MOJO_TIMING root_finding::eval_deriv", _ns_eval_deriv, _acc_eval_deriv)
    var _acc_bisection: Float64 = 0.0
    var _t0_bisection = perf_counter_ns()
    for _ in range(N):
        _acc_bisection += bisection(0.5, 0.5, 5, 0.5, 5)
    var _t1_bisection = perf_counter_ns()
    var _ns_bisection = Float64(_t1_bisection - _t0_bisection) / Float64(N)
    print("MOJO_TIMING root_finding::bisection", _ns_bisection, _acc_bisection)
    var _acc_newton_raphson: Float64 = 0.0
    var _t0_newton_raphson = perf_counter_ns()
    for _ in range(N):
        _acc_newton_raphson += newton_raphson(0.5, 5, 0.5, 5)
    var _t1_newton_raphson = perf_counter_ns()
    var _ns_newton_raphson = Float64(_t1_newton_raphson - _t0_newton_raphson) / Float64(N)
    print("MOJO_TIMING root_finding::newton_raphson", _ns_newton_raphson, _acc_newton_raphson)
    var _acc_secant_method: Float64 = 0.0
    var _t0_secant_method = perf_counter_ns()
    for _ in range(N):
        _acc_secant_method += secant_method(0.5, 0.5, 5, 0.5, 5)
    var _t1_secant_method = perf_counter_ns()
    var _ns_secant_method = Float64(_t1_secant_method - _t0_secant_method) / Float64(N)
    print("MOJO_TIMING root_finding::secant_method", _ns_secant_method, _acc_secant_method)
    var _acc_fixed_point: Float64 = 0.0
    var _t0_fixed_point = perf_counter_ns()
    for _ in range(N):
        _acc_fixed_point += fixed_point(0.5, 5, 0.5, 5)
    var _t1_fixed_point = perf_counter_ns()
    var _ns_fixed_point = Float64(_t1_fixed_point - _t0_fixed_point) / Float64(N)
    print("MOJO_TIMING root_finding::fixed_point", _ns_fixed_point, _acc_fixed_point)
    var _acc_regula_falsi: Float64 = 0.0
    var _t0_regula_falsi = perf_counter_ns()
    for _ in range(N):
        _acc_regula_falsi += regula_falsi(-1.0, 1.0, 0, 0.5, 5)
    var _t1_regula_falsi = perf_counter_ns()
    var _ns_regula_falsi = Float64(_t1_regula_falsi - _t0_regula_falsi) / Float64(N)
    print("MOJO_TIMING root_finding::regula_falsi", _ns_regula_falsi, _acc_regula_falsi)
    var _acc_bracket_root: Float64 = 0.0
    var _t0_bracket_root = perf_counter_ns()
    for _ in range(N):
        var _r_bracket_root = bracket_root(5, 0.5, 0.5, 5)
        _acc_bracket_root += Float64(len(_r_bracket_root))
    var _t1_bracket_root = perf_counter_ns()
    var _ns_bracket_root = Float64(_t1_bracket_root - _t0_bracket_root) / Float64(N)
    print("MOJO_TIMING root_finding::bracket_root", _ns_bracket_root, _acc_bracket_root)
    var _acc_convergence_order: Float64 = 0.0
    var _t0_convergence_order = perf_counter_ns()
    for _ in range(N):
        _acc_convergence_order += convergence_order(_lf5)
    var _t1_convergence_order = perf_counter_ns()
    var _ns_convergence_order = Float64(_t1_convergence_order - _t0_convergence_order) / Float64(N)
    print("MOJO_TIMING root_finding::convergence_order", _ns_convergence_order, _acc_convergence_order)
