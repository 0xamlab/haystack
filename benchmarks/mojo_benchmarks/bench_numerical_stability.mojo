"""bench_numerical_stability.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from numerical_stability import logsumexp, softmax, log_softmax, kahan_sum, welford_mean_var, log_add_exp, sigmoid_stable, log_sigmoid, softplus, normalize_probabilities, relative_error, safe_divide
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

    var _acc_logsumexp: Float64 = 0.0
    var _t0_logsumexp = perf_counter_ns()
    for _ in range(N):
        _acc_logsumexp += logsumexp(_lf5)
    var _t1_logsumexp = perf_counter_ns()
    var _ns_logsumexp = Float64(_t1_logsumexp - _t0_logsumexp) / Float64(N)
    print("MOJO_TIMING numerical_stability::logsumexp", _ns_logsumexp, _acc_logsumexp)
    var _acc_softmax: Float64 = 0.0
    var _t0_softmax = perf_counter_ns()
    for _ in range(N):
        var _r_softmax = softmax(_lf5)
        _acc_softmax += Float64(len(_r_softmax))
    var _t1_softmax = perf_counter_ns()
    var _ns_softmax = Float64(_t1_softmax - _t0_softmax) / Float64(N)
    print("MOJO_TIMING numerical_stability::softmax", _ns_softmax, _acc_softmax)
    var _acc_log_softmax: Float64 = 0.0
    var _t0_log_softmax = perf_counter_ns()
    for _ in range(N):
        var _r_log_softmax = log_softmax(_lf5)
        _acc_log_softmax += Float64(len(_r_log_softmax))
    var _t1_log_softmax = perf_counter_ns()
    var _ns_log_softmax = Float64(_t1_log_softmax - _t0_log_softmax) / Float64(N)
    print("MOJO_TIMING numerical_stability::log_softmax", _ns_log_softmax, _acc_log_softmax)
    var _acc_kahan_sum: Float64 = 0.0
    var _t0_kahan_sum = perf_counter_ns()
    for _ in range(N):
        _acc_kahan_sum += kahan_sum(_lf5)
    var _t1_kahan_sum = perf_counter_ns()
    var _ns_kahan_sum = Float64(_t1_kahan_sum - _t0_kahan_sum) / Float64(N)
    print("MOJO_TIMING numerical_stability::kahan_sum", _ns_kahan_sum, _acc_kahan_sum)
    var _acc_welford_mean_var: Float64 = 0.0
    var _t0_welford_mean_var = perf_counter_ns()
    for _ in range(N):
        var _r_welford_mean_var = welford_mean_var(_lf5)
        _acc_welford_mean_var += Float64(len(_r_welford_mean_var))
    var _t1_welford_mean_var = perf_counter_ns()
    var _ns_welford_mean_var = Float64(_t1_welford_mean_var - _t0_welford_mean_var) / Float64(N)
    print("MOJO_TIMING numerical_stability::welford_mean_var", _ns_welford_mean_var, _acc_welford_mean_var)
    var _acc_log_add_exp: Float64 = 0.0
    var _t0_log_add_exp = perf_counter_ns()
    for _ in range(N):
        _acc_log_add_exp += log_add_exp(0.5, 0.5)
    var _t1_log_add_exp = perf_counter_ns()
    var _ns_log_add_exp = Float64(_t1_log_add_exp - _t0_log_add_exp) / Float64(N)
    print("MOJO_TIMING numerical_stability::log_add_exp", _ns_log_add_exp, _acc_log_add_exp)
    var _acc_sigmoid_stable: Float64 = 0.0
    var _t0_sigmoid_stable = perf_counter_ns()
    for _ in range(N):
        _acc_sigmoid_stable += sigmoid_stable(0.5)
    var _t1_sigmoid_stable = perf_counter_ns()
    var _ns_sigmoid_stable = Float64(_t1_sigmoid_stable - _t0_sigmoid_stable) / Float64(N)
    print("MOJO_TIMING numerical_stability::sigmoid_stable", _ns_sigmoid_stable, _acc_sigmoid_stable)
    var _acc_log_sigmoid: Float64 = 0.0
    var _t0_log_sigmoid = perf_counter_ns()
    for _ in range(N):
        _acc_log_sigmoid += log_sigmoid(0.5)
    var _t1_log_sigmoid = perf_counter_ns()
    var _ns_log_sigmoid = Float64(_t1_log_sigmoid - _t0_log_sigmoid) / Float64(N)
    print("MOJO_TIMING numerical_stability::log_sigmoid", _ns_log_sigmoid, _acc_log_sigmoid)
    var _acc_softplus: Float64 = 0.0
    var _t0_softplus = perf_counter_ns()
    for _ in range(N):
        _acc_softplus += softplus(0.5)
    var _t1_softplus = perf_counter_ns()
    var _ns_softplus = Float64(_t1_softplus - _t0_softplus) / Float64(N)
    print("MOJO_TIMING numerical_stability::softplus", _ns_softplus, _acc_softplus)
    var _acc_normalize_probabilities: Float64 = 0.0
    var _t0_normalize_probabilities = perf_counter_ns()
    for _ in range(N):
        var _r_normalize_probabilities = normalize_probabilities(_lf5)
        _acc_normalize_probabilities += Float64(len(_r_normalize_probabilities))
    var _t1_normalize_probabilities = perf_counter_ns()
    var _ns_normalize_probabilities = Float64(_t1_normalize_probabilities - _t0_normalize_probabilities) / Float64(N)
    print("MOJO_TIMING numerical_stability::normalize_probabilities", _ns_normalize_probabilities, _acc_normalize_probabilities)
    var _acc_relative_error: Float64 = 0.0
    var _t0_relative_error = perf_counter_ns()
    for _ in range(N):
        _acc_relative_error += relative_error(0.5, 0.5)
    var _t1_relative_error = perf_counter_ns()
    var _ns_relative_error = Float64(_t1_relative_error - _t0_relative_error) / Float64(N)
    print("MOJO_TIMING numerical_stability::relative_error", _ns_relative_error, _acc_relative_error)
    var _acc_safe_divide: Float64 = 0.0
    var _t0_safe_divide = perf_counter_ns()
    for _ in range(N):
        _acc_safe_divide += safe_divide(0.5, 0.5, 0.5)
    var _t1_safe_divide = perf_counter_ns()
    var _ns_safe_divide = Float64(_t1_safe_divide - _t0_safe_divide) / Float64(N)
    print("MOJO_TIMING numerical_stability::safe_divide", _ns_safe_divide, _acc_safe_divide)
