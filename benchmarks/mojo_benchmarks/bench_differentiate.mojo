"""bench_differentiate.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from differentiate import derivative_forward, derivative_central, derivative_backward, second_derivative, gradient, poly_derivative_coeffs
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

    var _acc_derivative_forward: Float64 = 0.0
    var _t0_derivative_forward = perf_counter_ns()
    for _ in range(N):
        var _r_derivative_forward = derivative_forward(_lf5, 0.5)
        _acc_derivative_forward += Float64(len(_r_derivative_forward))
    var _t1_derivative_forward = perf_counter_ns()
    var _ns_derivative_forward = Float64(_t1_derivative_forward - _t0_derivative_forward) / Float64(N)
    print("MOJO_TIMING differentiate::derivative_forward", _ns_derivative_forward, _acc_derivative_forward)
    var _acc_derivative_central: Float64 = 0.0
    var _t0_derivative_central = perf_counter_ns()
    for _ in range(N):
        var _r_derivative_central = derivative_central(_lf5, 0.5)
        _acc_derivative_central += Float64(len(_r_derivative_central))
    var _t1_derivative_central = perf_counter_ns()
    var _ns_derivative_central = Float64(_t1_derivative_central - _t0_derivative_central) / Float64(N)
    print("MOJO_TIMING differentiate::derivative_central", _ns_derivative_central, _acc_derivative_central)
    var _acc_derivative_backward: Float64 = 0.0
    var _t0_derivative_backward = perf_counter_ns()
    for _ in range(N):
        var _r_derivative_backward = derivative_backward(_lf5, 0.5)
        _acc_derivative_backward += Float64(len(_r_derivative_backward))
    var _t1_derivative_backward = perf_counter_ns()
    var _ns_derivative_backward = Float64(_t1_derivative_backward - _t0_derivative_backward) / Float64(N)
    print("MOJO_TIMING differentiate::derivative_backward", _ns_derivative_backward, _acc_derivative_backward)
    var _acc_second_derivative: Float64 = 0.0
    var _t0_second_derivative = perf_counter_ns()
    for _ in range(N):
        var _r_second_derivative = second_derivative(_lf5, 0.5)
        _acc_second_derivative += Float64(len(_r_second_derivative))
    var _t1_second_derivative = perf_counter_ns()
    var _ns_second_derivative = Float64(_t1_second_derivative - _t0_second_derivative) / Float64(N)
    print("MOJO_TIMING differentiate::second_derivative", _ns_second_derivative, _acc_second_derivative)
    var _acc_gradient: Float64 = 0.0
    var _t0_gradient = perf_counter_ns()
    for _ in range(N):
        var _r_gradient = gradient(_lf5, _lf5)
        _acc_gradient += Float64(len(_r_gradient))
    var _t1_gradient = perf_counter_ns()
    var _ns_gradient = Float64(_t1_gradient - _t0_gradient) / Float64(N)
    print("MOJO_TIMING differentiate::gradient", _ns_gradient, _acc_gradient)
    var _acc_poly_derivative_coeffs: Float64 = 0.0
    var _t0_poly_derivative_coeffs = perf_counter_ns()
    for _ in range(N):
        var _r_poly_derivative_coeffs = poly_derivative_coeffs(_lf5)
        _acc_poly_derivative_coeffs += Float64(len(_r_poly_derivative_coeffs))
    var _t1_poly_derivative_coeffs = perf_counter_ns()
    var _ns_poly_derivative_coeffs = Float64(_t1_poly_derivative_coeffs - _t0_poly_derivative_coeffs) / Float64(N)
    print("MOJO_TIMING differentiate::poly_derivative_coeffs", _ns_poly_derivative_coeffs, _acc_poly_derivative_coeffs)
