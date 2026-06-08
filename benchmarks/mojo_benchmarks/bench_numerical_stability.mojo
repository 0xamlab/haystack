"""bench_numerical_stability.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from numerical_stability import logsumexp, softmax, log_softmax, kahan_sum, welford_mean_var, log_add_exp, sigmoid_stable, log_sigmoid, softplus, normalize_probabilities, relative_error, safe_divide
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

    var _acc_logsumexp: Float64 = 0.0
    var _t0_logsumexp = perf_counter_ns()
    for _ in range(N):
        _acc_logsumexp += logsumexp(_lf5)
    var _t1_logsumexp = perf_counter_ns()
    var _ns_logsumexp = Float64(_t1_logsumexp - _t0_logsumexp) / Float64(N)
    print("MOJO_TIMING numerical_stability::logsumexp", _ns_logsumexp, _acc_logsumexp)
    var _result_logsumexp = logsumexp(_lf5)
    var _summary_logsumexp = _summary_float64(_result_logsumexp)
    print("MOJO_RESULT numerical_stability::logsumexp", _summary_logsumexp)
    var _acc_softmax: Float64 = 0.0
    var _t0_softmax = perf_counter_ns()
    for _ in range(N):
        var _r_softmax = softmax(_lf5)
        _acc_softmax += Float64(len(_r_softmax))
    var _t1_softmax = perf_counter_ns()
    var _ns_softmax = Float64(_t1_softmax - _t0_softmax) / Float64(N)
    print("MOJO_TIMING numerical_stability::softmax", _ns_softmax, _acc_softmax)
    var _result_softmax = softmax(_lf5)
    var _summary_softmax = _summary_list_float64(_result_softmax)
    print("MOJO_RESULT numerical_stability::softmax", _summary_softmax)
    var _acc_log_softmax: Float64 = 0.0
    var _t0_log_softmax = perf_counter_ns()
    for _ in range(N):
        var _r_log_softmax = log_softmax(_lf5)
        _acc_log_softmax += Float64(len(_r_log_softmax))
    var _t1_log_softmax = perf_counter_ns()
    var _ns_log_softmax = Float64(_t1_log_softmax - _t0_log_softmax) / Float64(N)
    print("MOJO_TIMING numerical_stability::log_softmax", _ns_log_softmax, _acc_log_softmax)
    var _result_log_softmax = log_softmax(_lf5)
    var _summary_log_softmax = _summary_list_float64(_result_log_softmax)
    print("MOJO_RESULT numerical_stability::log_softmax", _summary_log_softmax)
    var _acc_kahan_sum: Float64 = 0.0
    var _t0_kahan_sum = perf_counter_ns()
    for _ in range(N):
        _acc_kahan_sum += kahan_sum(_lf5)
    var _t1_kahan_sum = perf_counter_ns()
    var _ns_kahan_sum = Float64(_t1_kahan_sum - _t0_kahan_sum) / Float64(N)
    print("MOJO_TIMING numerical_stability::kahan_sum", _ns_kahan_sum, _acc_kahan_sum)
    var _result_kahan_sum = kahan_sum(_lf5)
    var _summary_kahan_sum = _summary_float64(_result_kahan_sum)
    print("MOJO_RESULT numerical_stability::kahan_sum", _summary_kahan_sum)
    var _acc_welford_mean_var: Float64 = 0.0
    var _t0_welford_mean_var = perf_counter_ns()
    for _ in range(N):
        var _r_welford_mean_var = welford_mean_var(_lf5)
        _acc_welford_mean_var += Float64(len(_r_welford_mean_var))
    var _t1_welford_mean_var = perf_counter_ns()
    var _ns_welford_mean_var = Float64(_t1_welford_mean_var - _t0_welford_mean_var) / Float64(N)
    print("MOJO_TIMING numerical_stability::welford_mean_var", _ns_welford_mean_var, _acc_welford_mean_var)
    var _result_welford_mean_var = welford_mean_var(_lf5)
    var _summary_welford_mean_var = _summary_list_float64(_result_welford_mean_var)
    print("MOJO_RESULT numerical_stability::welford_mean_var", _summary_welford_mean_var)
    var _acc_log_add_exp: Float64 = 0.0
    var _t0_log_add_exp = perf_counter_ns()
    for _ in range(N):
        _acc_log_add_exp += log_add_exp(0.5, 0.5)
    var _t1_log_add_exp = perf_counter_ns()
    var _ns_log_add_exp = Float64(_t1_log_add_exp - _t0_log_add_exp) / Float64(N)
    print("MOJO_TIMING numerical_stability::log_add_exp", _ns_log_add_exp, _acc_log_add_exp)
    var _result_log_add_exp = log_add_exp(0.5, 0.5)
    var _summary_log_add_exp = _summary_float64(_result_log_add_exp)
    print("MOJO_RESULT numerical_stability::log_add_exp", _summary_log_add_exp)
    var _acc_sigmoid_stable: Float64 = 0.0
    var _t0_sigmoid_stable = perf_counter_ns()
    for _ in range(N):
        _acc_sigmoid_stable += sigmoid_stable(0.5)
    var _t1_sigmoid_stable = perf_counter_ns()
    var _ns_sigmoid_stable = Float64(_t1_sigmoid_stable - _t0_sigmoid_stable) / Float64(N)
    print("MOJO_TIMING numerical_stability::sigmoid_stable", _ns_sigmoid_stable, _acc_sigmoid_stable)
    var _result_sigmoid_stable = sigmoid_stable(0.5)
    var _summary_sigmoid_stable = _summary_float64(_result_sigmoid_stable)
    print("MOJO_RESULT numerical_stability::sigmoid_stable", _summary_sigmoid_stable)
    var _acc_log_sigmoid: Float64 = 0.0
    var _t0_log_sigmoid = perf_counter_ns()
    for _ in range(N):
        _acc_log_sigmoid += log_sigmoid(0.5)
    var _t1_log_sigmoid = perf_counter_ns()
    var _ns_log_sigmoid = Float64(_t1_log_sigmoid - _t0_log_sigmoid) / Float64(N)
    print("MOJO_TIMING numerical_stability::log_sigmoid", _ns_log_sigmoid, _acc_log_sigmoid)
    var _result_log_sigmoid = log_sigmoid(0.5)
    var _summary_log_sigmoid = _summary_float64(_result_log_sigmoid)
    print("MOJO_RESULT numerical_stability::log_sigmoid", _summary_log_sigmoid)
    var _acc_softplus: Float64 = 0.0
    var _t0_softplus = perf_counter_ns()
    for _ in range(N):
        _acc_softplus += softplus(0.5)
    var _t1_softplus = perf_counter_ns()
    var _ns_softplus = Float64(_t1_softplus - _t0_softplus) / Float64(N)
    print("MOJO_TIMING numerical_stability::softplus", _ns_softplus, _acc_softplus)
    var _result_softplus = softplus(0.5)
    var _summary_softplus = _summary_float64(_result_softplus)
    print("MOJO_RESULT numerical_stability::softplus", _summary_softplus)
    var _acc_normalize_probabilities: Float64 = 0.0
    var _t0_normalize_probabilities = perf_counter_ns()
    for _ in range(N):
        var _r_normalize_probabilities = normalize_probabilities(_lf5)
        _acc_normalize_probabilities += Float64(len(_r_normalize_probabilities))
    var _t1_normalize_probabilities = perf_counter_ns()
    var _ns_normalize_probabilities = Float64(_t1_normalize_probabilities - _t0_normalize_probabilities) / Float64(N)
    print("MOJO_TIMING numerical_stability::normalize_probabilities", _ns_normalize_probabilities, _acc_normalize_probabilities)
    var _result_normalize_probabilities = normalize_probabilities(_lf5)
    var _summary_normalize_probabilities = _summary_list_float64(_result_normalize_probabilities)
    print("MOJO_RESULT numerical_stability::normalize_probabilities", _summary_normalize_probabilities)
    var _acc_relative_error: Float64 = 0.0
    var _t0_relative_error = perf_counter_ns()
    for _ in range(N):
        _acc_relative_error += relative_error(0.5, 0.5)
    var _t1_relative_error = perf_counter_ns()
    var _ns_relative_error = Float64(_t1_relative_error - _t0_relative_error) / Float64(N)
    print("MOJO_TIMING numerical_stability::relative_error", _ns_relative_error, _acc_relative_error)
    var _result_relative_error = relative_error(0.5, 0.5)
    var _summary_relative_error = _summary_float64(_result_relative_error)
    print("MOJO_RESULT numerical_stability::relative_error", _summary_relative_error)
    var _acc_safe_divide: Float64 = 0.0
    var _t0_safe_divide = perf_counter_ns()
    for _ in range(N):
        _acc_safe_divide += safe_divide(0.5, 0.5, 0.5)
    var _t1_safe_divide = perf_counter_ns()
    var _ns_safe_divide = Float64(_t1_safe_divide - _t0_safe_divide) / Float64(N)
    print("MOJO_TIMING numerical_stability::safe_divide", _ns_safe_divide, _acc_safe_divide)
    var _result_safe_divide = safe_divide(0.5, 0.5, 0.5)
    var _summary_safe_divide = _summary_float64(_result_safe_divide)
    print("MOJO_RESULT numerical_stability::safe_divide", _summary_safe_divide)
