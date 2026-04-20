"""bench_optimize.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from optimize import eval_poly, eval_poly_deriv, minimize_scalar_golden, minimize_brent, root_bisection, root_newton, gradient_descent_1d, linear_regression, LinRegResult, OptResult
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

    var _acc_eval_poly: Float64 = 0.0
    var _t0_eval_poly = perf_counter_ns()
    for _ in range(N):
        _acc_eval_poly += eval_poly(_lf5, 0.5)
    var _t1_eval_poly = perf_counter_ns()
    var _ns_eval_poly = Float64(_t1_eval_poly - _t0_eval_poly) / Float64(N)
    print("MOJO_TIMING optimize::eval_poly", _ns_eval_poly, _acc_eval_poly)
    var _acc_eval_poly_deriv: Float64 = 0.0
    var _t0_eval_poly_deriv = perf_counter_ns()
    for _ in range(N):
        _acc_eval_poly_deriv += eval_poly_deriv(_lf5, 0.5)
    var _t1_eval_poly_deriv = perf_counter_ns()
    var _ns_eval_poly_deriv = Float64(_t1_eval_poly_deriv - _t0_eval_poly_deriv) / Float64(N)
    print("MOJO_TIMING optimize::eval_poly_deriv", _ns_eval_poly_deriv, _acc_eval_poly_deriv)
    var _keeper_minimize_scalar_golden = List[OptResult]()
    _keeper_minimize_scalar_golden.append(minimize_scalar_golden(_lf5, 0.5, 0.5, 0.5, 5))
    var _acc_minimize_scalar_golden: Float64 = 0.0
    var _t0_minimize_scalar_golden = perf_counter_ns()
    for _ in range(N):
        _keeper_minimize_scalar_golden[0] = minimize_scalar_golden(_lf5, 0.5, 0.5, 0.5, 5)
        _acc_minimize_scalar_golden += Float64(len(_keeper_minimize_scalar_golden))
    var _t1_minimize_scalar_golden = perf_counter_ns()
    var _ns_minimize_scalar_golden = Float64(_t1_minimize_scalar_golden - _t0_minimize_scalar_golden) / Float64(N)
    print("MOJO_TIMING optimize::minimize_scalar_golden", _ns_minimize_scalar_golden, _acc_minimize_scalar_golden)
    var _keeper_minimize_brent = List[OptResult]()
    _keeper_minimize_brent.append(minimize_brent(_lf5, 0.5, 0.5, 0.5, 5))
    var _acc_minimize_brent: Float64 = 0.0
    var _t0_minimize_brent = perf_counter_ns()
    for _ in range(N):
        _keeper_minimize_brent[0] = minimize_brent(_lf5, 0.5, 0.5, 0.5, 5)
        _acc_minimize_brent += Float64(len(_keeper_minimize_brent))
    var _t1_minimize_brent = perf_counter_ns()
    var _ns_minimize_brent = Float64(_t1_minimize_brent - _t0_minimize_brent) / Float64(N)
    print("MOJO_TIMING optimize::minimize_brent", _ns_minimize_brent, _acc_minimize_brent)
    var _keeper_root_bisection = List[OptResult]()
    _keeper_root_bisection.append(root_bisection(_lf5, 0.5, 0.5, 0.5, 5))
    var _acc_root_bisection: Float64 = 0.0
    var _t0_root_bisection = perf_counter_ns()
    for _ in range(N):
        _keeper_root_bisection[0] = root_bisection(_lf5, 0.5, 0.5, 0.5, 5)
        _acc_root_bisection += Float64(len(_keeper_root_bisection))
    var _t1_root_bisection = perf_counter_ns()
    var _ns_root_bisection = Float64(_t1_root_bisection - _t0_root_bisection) / Float64(N)
    print("MOJO_TIMING optimize::root_bisection", _ns_root_bisection, _acc_root_bisection)
    var _keeper_root_newton = List[OptResult]()
    _keeper_root_newton.append(root_newton(0.5, _lf5, 0.5, 5))
    var _acc_root_newton: Float64 = 0.0
    var _t0_root_newton = perf_counter_ns()
    for _ in range(N):
        _keeper_root_newton[0] = root_newton(0.5, _lf5, 0.5, 5)
        _acc_root_newton += Float64(len(_keeper_root_newton))
    var _t1_root_newton = perf_counter_ns()
    var _ns_root_newton = Float64(_t1_root_newton - _t0_root_newton) / Float64(N)
    print("MOJO_TIMING optimize::root_newton", _ns_root_newton, _acc_root_newton)
    var _keeper_gradient_descent_1d = List[OptResult]()
    _keeper_gradient_descent_1d.append(gradient_descent_1d(_lf5, 0.5, 0.5, 0.5, 5))
    var _acc_gradient_descent_1d: Float64 = 0.0
    var _t0_gradient_descent_1d = perf_counter_ns()
    for _ in range(N):
        _keeper_gradient_descent_1d[0] = gradient_descent_1d(_lf5, 0.5, 0.5, 0.5, 5)
        _acc_gradient_descent_1d += Float64(len(_keeper_gradient_descent_1d))
    var _t1_gradient_descent_1d = perf_counter_ns()
    var _ns_gradient_descent_1d = Float64(_t1_gradient_descent_1d - _t0_gradient_descent_1d) / Float64(N)
    print("MOJO_TIMING optimize::gradient_descent_1d", _ns_gradient_descent_1d, _acc_gradient_descent_1d)
    var _keeper_linear_regression = List[LinRegResult]()
    _keeper_linear_regression.append(linear_regression(_lf5, _lf5))
    var _acc_linear_regression: Float64 = 0.0
    var _t0_linear_regression = perf_counter_ns()
    for _ in range(N):
        _keeper_linear_regression[0] = linear_regression(_lf5, _lf5)
        _acc_linear_regression += Float64(len(_keeper_linear_regression))
    var _t1_linear_regression = perf_counter_ns()
    var _ns_linear_regression = Float64(_t1_linear_regression - _t0_linear_regression) / Float64(N)
    print("MOJO_TIMING optimize::linear_regression", _ns_linear_regression, _acc_linear_regression)
