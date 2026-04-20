"""bench_polynomial.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from polynomial import poly_eval, poly_add, poly_multiply, poly_derivative, poly_integral, poly_degree, quadratic_roots, poly_scale, poly_compose, poly_from_roots
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

    var _acc_poly_eval: Float64 = 0.0
    var _t0_poly_eval = perf_counter_ns()
    for _ in range(N):
        _acc_poly_eval += poly_eval(_lf5, 0.5)
    var _t1_poly_eval = perf_counter_ns()
    var _ns_poly_eval = Float64(_t1_poly_eval - _t0_poly_eval) / Float64(N)
    print("MOJO_TIMING polynomial::poly_eval", _ns_poly_eval, _acc_poly_eval)
    var _acc_poly_add: Float64 = 0.0
    var _t0_poly_add = perf_counter_ns()
    for _ in range(N):
        var _r_poly_add = poly_add(_lf5, _lf5)
        _acc_poly_add += Float64(len(_r_poly_add))
    var _t1_poly_add = perf_counter_ns()
    var _ns_poly_add = Float64(_t1_poly_add - _t0_poly_add) / Float64(N)
    print("MOJO_TIMING polynomial::poly_add", _ns_poly_add, _acc_poly_add)
    var _acc_poly_multiply: Float64 = 0.0
    var _t0_poly_multiply = perf_counter_ns()
    for _ in range(N):
        var _r_poly_multiply = poly_multiply(_lf5, _lf5)
        _acc_poly_multiply += Float64(len(_r_poly_multiply))
    var _t1_poly_multiply = perf_counter_ns()
    var _ns_poly_multiply = Float64(_t1_poly_multiply - _t0_poly_multiply) / Float64(N)
    print("MOJO_TIMING polynomial::poly_multiply", _ns_poly_multiply, _acc_poly_multiply)
    var _acc_poly_derivative: Float64 = 0.0
    var _t0_poly_derivative = perf_counter_ns()
    for _ in range(N):
        var _r_poly_derivative = poly_derivative(_lf5)
        _acc_poly_derivative += Float64(len(_r_poly_derivative))
    var _t1_poly_derivative = perf_counter_ns()
    var _ns_poly_derivative = Float64(_t1_poly_derivative - _t0_poly_derivative) / Float64(N)
    print("MOJO_TIMING polynomial::poly_derivative", _ns_poly_derivative, _acc_poly_derivative)
    var _acc_poly_integral: Float64 = 0.0
    var _t0_poly_integral = perf_counter_ns()
    for _ in range(N):
        var _r_poly_integral = poly_integral(_lf5, 0.5)
        _acc_poly_integral += Float64(len(_r_poly_integral))
    var _t1_poly_integral = perf_counter_ns()
    var _ns_poly_integral = Float64(_t1_poly_integral - _t0_poly_integral) / Float64(N)
    print("MOJO_TIMING polynomial::poly_integral", _ns_poly_integral, _acc_poly_integral)
    var _acc_poly_degree: Float64 = 0.0
    var _t0_poly_degree = perf_counter_ns()
    for _ in range(N):
        _acc_poly_degree += Float64(poly_degree(_lf5))
    var _t1_poly_degree = perf_counter_ns()
    var _ns_poly_degree = Float64(_t1_poly_degree - _t0_poly_degree) / Float64(N)
    print("MOJO_TIMING polynomial::poly_degree", _ns_poly_degree, _acc_poly_degree)
    var _acc_quadratic_roots: Float64 = 0.0
    var _t0_quadratic_roots = perf_counter_ns()
    for _ in range(N):
        var _r_quadratic_roots = quadratic_roots(0.5, 0.5, 0.5)
        _acc_quadratic_roots += Float64(len(_r_quadratic_roots))
    var _t1_quadratic_roots = perf_counter_ns()
    var _ns_quadratic_roots = Float64(_t1_quadratic_roots - _t0_quadratic_roots) / Float64(N)
    print("MOJO_TIMING polynomial::quadratic_roots", _ns_quadratic_roots, _acc_quadratic_roots)
    var _acc_poly_scale: Float64 = 0.0
    var _t0_poly_scale = perf_counter_ns()
    for _ in range(N):
        var _r_poly_scale = poly_scale(_lf5, 0.5)
        _acc_poly_scale += Float64(len(_r_poly_scale))
    var _t1_poly_scale = perf_counter_ns()
    var _ns_poly_scale = Float64(_t1_poly_scale - _t0_poly_scale) / Float64(N)
    print("MOJO_TIMING polynomial::poly_scale", _ns_poly_scale, _acc_poly_scale)
    var _acc_poly_compose: Float64 = 0.0
    var _t0_poly_compose = perf_counter_ns()
    for _ in range(N):
        var _r_poly_compose = poly_compose(_lf5, _lf5)
        _acc_poly_compose += Float64(len(_r_poly_compose))
    var _t1_poly_compose = perf_counter_ns()
    var _ns_poly_compose = Float64(_t1_poly_compose - _t0_poly_compose) / Float64(N)
    print("MOJO_TIMING polynomial::poly_compose", _ns_poly_compose, _acc_poly_compose)
    var _acc_poly_from_roots: Float64 = 0.0
    var _t0_poly_from_roots = perf_counter_ns()
    for _ in range(N):
        var _r_poly_from_roots = poly_from_roots(_lf5)
        _acc_poly_from_roots += Float64(len(_r_poly_from_roots))
    var _t1_poly_from_roots = perf_counter_ns()
    var _ns_poly_from_roots = Float64(_t1_poly_from_roots - _t0_poly_from_roots) / Float64(N)
    print("MOJO_TIMING polynomial::poly_from_roots", _ns_poly_from_roots, _acc_poly_from_roots)
