"""bench_special_functions.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from special_functions import gamma_function, log_gamma, beta_function, digamma, incomplete_gamma_lower, regularized_gamma, erf, erfc, bessel_j0, factorial_float, double_factorial, binomial_coefficient
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

    var _acc_gamma_function: Float64 = 0.0
    var _t0_gamma_function = perf_counter_ns()
    for _ in range(N):
        _acc_gamma_function += gamma_function(0.5)
    var _t1_gamma_function = perf_counter_ns()
    var _ns_gamma_function = Float64(_t1_gamma_function - _t0_gamma_function) / Float64(N)
    print("MOJO_TIMING special_functions::gamma_function", _ns_gamma_function, _acc_gamma_function)
    var _acc_log_gamma: Float64 = 0.0
    var _t0_log_gamma = perf_counter_ns()
    for _ in range(N):
        _acc_log_gamma += log_gamma(0.5)
    var _t1_log_gamma = perf_counter_ns()
    var _ns_log_gamma = Float64(_t1_log_gamma - _t0_log_gamma) / Float64(N)
    print("MOJO_TIMING special_functions::log_gamma", _ns_log_gamma, _acc_log_gamma)
    var _acc_beta_function: Float64 = 0.0
    var _t0_beta_function = perf_counter_ns()
    for _ in range(N):
        _acc_beta_function += beta_function(0.5, 0.5)
    var _t1_beta_function = perf_counter_ns()
    var _ns_beta_function = Float64(_t1_beta_function - _t0_beta_function) / Float64(N)
    print("MOJO_TIMING special_functions::beta_function", _ns_beta_function, _acc_beta_function)
    var _acc_digamma: Float64 = 0.0
    var _t0_digamma = perf_counter_ns()
    for _ in range(N):
        _acc_digamma += digamma(0.5)
    var _t1_digamma = perf_counter_ns()
    var _ns_digamma = Float64(_t1_digamma - _t0_digamma) / Float64(N)
    print("MOJO_TIMING special_functions::digamma", _ns_digamma, _acc_digamma)
    var _acc_incomplete_gamma_lower: Float64 = 0.0
    var _t0_incomplete_gamma_lower = perf_counter_ns()
    for _ in range(N):
        _acc_incomplete_gamma_lower += incomplete_gamma_lower(0.5, 0.5)
    var _t1_incomplete_gamma_lower = perf_counter_ns()
    var _ns_incomplete_gamma_lower = Float64(_t1_incomplete_gamma_lower - _t0_incomplete_gamma_lower) / Float64(N)
    print("MOJO_TIMING special_functions::incomplete_gamma_lower", _ns_incomplete_gamma_lower, _acc_incomplete_gamma_lower)
    var _acc_regularized_gamma: Float64 = 0.0
    var _t0_regularized_gamma = perf_counter_ns()
    for _ in range(N):
        _acc_regularized_gamma += regularized_gamma(0.5, 0.5)
    var _t1_regularized_gamma = perf_counter_ns()
    var _ns_regularized_gamma = Float64(_t1_regularized_gamma - _t0_regularized_gamma) / Float64(N)
    print("MOJO_TIMING special_functions::regularized_gamma", _ns_regularized_gamma, _acc_regularized_gamma)
    var _acc_erf: Float64 = 0.0
    var _t0_erf = perf_counter_ns()
    for _ in range(N):
        _acc_erf += erf(0.5)
    var _t1_erf = perf_counter_ns()
    var _ns_erf = Float64(_t1_erf - _t0_erf) / Float64(N)
    print("MOJO_TIMING special_functions::erf", _ns_erf, _acc_erf)
    var _acc_erfc: Float64 = 0.0
    var _t0_erfc = perf_counter_ns()
    for _ in range(N):
        _acc_erfc += erfc(0.5)
    var _t1_erfc = perf_counter_ns()
    var _ns_erfc = Float64(_t1_erfc - _t0_erfc) / Float64(N)
    print("MOJO_TIMING special_functions::erfc", _ns_erfc, _acc_erfc)
    var _acc_bessel_j0: Float64 = 0.0
    var _t0_bessel_j0 = perf_counter_ns()
    for _ in range(N):
        _acc_bessel_j0 += bessel_j0(0.5)
    var _t1_bessel_j0 = perf_counter_ns()
    var _ns_bessel_j0 = Float64(_t1_bessel_j0 - _t0_bessel_j0) / Float64(N)
    print("MOJO_TIMING special_functions::bessel_j0", _ns_bessel_j0, _acc_bessel_j0)
    var _acc_factorial_float: Float64 = 0.0
    var _t0_factorial_float = perf_counter_ns()
    for _ in range(N):
        _acc_factorial_float += factorial_float(5)
    var _t1_factorial_float = perf_counter_ns()
    var _ns_factorial_float = Float64(_t1_factorial_float - _t0_factorial_float) / Float64(N)
    print("MOJO_TIMING special_functions::factorial_float", _ns_factorial_float, _acc_factorial_float)
    var _acc_double_factorial: Float64 = 0.0
    var _t0_double_factorial = perf_counter_ns()
    for _ in range(N):
        _acc_double_factorial += double_factorial(5)
    var _t1_double_factorial = perf_counter_ns()
    var _ns_double_factorial = Float64(_t1_double_factorial - _t0_double_factorial) / Float64(N)
    print("MOJO_TIMING special_functions::double_factorial", _ns_double_factorial, _acc_double_factorial)
    var _acc_binomial_coefficient: Float64 = 0.0
    var _t0_binomial_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_binomial_coefficient += binomial_coefficient(5, 5)
    var _t1_binomial_coefficient = perf_counter_ns()
    var _ns_binomial_coefficient = Float64(_t1_binomial_coefficient - _t0_binomial_coefficient) / Float64(N)
    print("MOJO_TIMING special_functions::binomial_coefficient", _ns_binomial_coefficient, _acc_binomial_coefficient)
