"""bench_special_functions.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from special_functions import gamma_function, log_gamma, beta_function, digamma, incomplete_gamma_lower, regularized_gamma, erf, erfc, bessel_j0, factorial_float, double_factorial, binomial_coefficient
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_gamma_function: Float64 = 0.0
    var _t0_gamma_function = perf_counter_ns()
    for _ in range(N):
        _acc_gamma_function += gamma_function(0.5)
    var _t1_gamma_function = perf_counter_ns()
    var _ns_gamma_function = Float64(_t1_gamma_function - _t0_gamma_function) / Float64(N)
    print("MOJO_TIMING special_functions::gamma_function", _ns_gamma_function, _acc_gamma_function)
    var _result_gamma_function = gamma_function(0.5)
    var _summary_gamma_function = _summary_float64(_result_gamma_function)
    print("MOJO_RESULT special_functions::gamma_function", _summary_gamma_function)
    var _acc_log_gamma: Float64 = 0.0
    var _t0_log_gamma = perf_counter_ns()
    for _ in range(N):
        _acc_log_gamma += log_gamma(0.5)
    var _t1_log_gamma = perf_counter_ns()
    var _ns_log_gamma = Float64(_t1_log_gamma - _t0_log_gamma) / Float64(N)
    print("MOJO_TIMING special_functions::log_gamma", _ns_log_gamma, _acc_log_gamma)
    var _result_log_gamma = log_gamma(0.5)
    var _summary_log_gamma = _summary_float64(_result_log_gamma)
    print("MOJO_RESULT special_functions::log_gamma", _summary_log_gamma)
    var _acc_beta_function: Float64 = 0.0
    var _t0_beta_function = perf_counter_ns()
    for _ in range(N):
        _acc_beta_function += beta_function(0.5, 0.5)
    var _t1_beta_function = perf_counter_ns()
    var _ns_beta_function = Float64(_t1_beta_function - _t0_beta_function) / Float64(N)
    print("MOJO_TIMING special_functions::beta_function", _ns_beta_function, _acc_beta_function)
    var _result_beta_function = beta_function(0.5, 0.5)
    var _summary_beta_function = _summary_float64(_result_beta_function)
    print("MOJO_RESULT special_functions::beta_function", _summary_beta_function)
    var _acc_digamma: Float64 = 0.0
    var _t0_digamma = perf_counter_ns()
    for _ in range(N):
        _acc_digamma += digamma(0.5)
    var _t1_digamma = perf_counter_ns()
    var _ns_digamma = Float64(_t1_digamma - _t0_digamma) / Float64(N)
    print("MOJO_TIMING special_functions::digamma", _ns_digamma, _acc_digamma)
    var _result_digamma = digamma(0.5)
    var _summary_digamma = _summary_float64(_result_digamma)
    print("MOJO_RESULT special_functions::digamma", _summary_digamma)
    var _acc_incomplete_gamma_lower: Float64 = 0.0
    var _t0_incomplete_gamma_lower = perf_counter_ns()
    for _ in range(N):
        _acc_incomplete_gamma_lower += incomplete_gamma_lower(0.5, 0.5)
    var _t1_incomplete_gamma_lower = perf_counter_ns()
    var _ns_incomplete_gamma_lower = Float64(_t1_incomplete_gamma_lower - _t0_incomplete_gamma_lower) / Float64(N)
    print("MOJO_TIMING special_functions::incomplete_gamma_lower", _ns_incomplete_gamma_lower, _acc_incomplete_gamma_lower)
    var _result_incomplete_gamma_lower = incomplete_gamma_lower(0.5, 0.5)
    var _summary_incomplete_gamma_lower = _summary_float64(_result_incomplete_gamma_lower)
    print("MOJO_RESULT special_functions::incomplete_gamma_lower", _summary_incomplete_gamma_lower)
    var _acc_regularized_gamma: Float64 = 0.0
    var _t0_regularized_gamma = perf_counter_ns()
    for _ in range(N):
        _acc_regularized_gamma += regularized_gamma(0.5, 0.5)
    var _t1_regularized_gamma = perf_counter_ns()
    var _ns_regularized_gamma = Float64(_t1_regularized_gamma - _t0_regularized_gamma) / Float64(N)
    print("MOJO_TIMING special_functions::regularized_gamma", _ns_regularized_gamma, _acc_regularized_gamma)
    var _result_regularized_gamma = regularized_gamma(0.5, 0.5)
    var _summary_regularized_gamma = _summary_float64(_result_regularized_gamma)
    print("MOJO_RESULT special_functions::regularized_gamma", _summary_regularized_gamma)
    var _acc_erf: Float64 = 0.0
    var _t0_erf = perf_counter_ns()
    for _ in range(N):
        _acc_erf += erf(0.5)
    var _t1_erf = perf_counter_ns()
    var _ns_erf = Float64(_t1_erf - _t0_erf) / Float64(N)
    print("MOJO_TIMING special_functions::erf", _ns_erf, _acc_erf)
    var _result_erf = erf(0.5)
    var _summary_erf = _summary_float64(_result_erf)
    print("MOJO_RESULT special_functions::erf", _summary_erf)
    var _acc_erfc: Float64 = 0.0
    var _t0_erfc = perf_counter_ns()
    for _ in range(N):
        _acc_erfc += erfc(0.5)
    var _t1_erfc = perf_counter_ns()
    var _ns_erfc = Float64(_t1_erfc - _t0_erfc) / Float64(N)
    print("MOJO_TIMING special_functions::erfc", _ns_erfc, _acc_erfc)
    var _result_erfc = erfc(0.5)
    var _summary_erfc = _summary_float64(_result_erfc)
    print("MOJO_RESULT special_functions::erfc", _summary_erfc)
    var _acc_bessel_j0: Float64 = 0.0
    var _t0_bessel_j0 = perf_counter_ns()
    for _ in range(N):
        _acc_bessel_j0 += bessel_j0(0.5)
    var _t1_bessel_j0 = perf_counter_ns()
    var _ns_bessel_j0 = Float64(_t1_bessel_j0 - _t0_bessel_j0) / Float64(N)
    print("MOJO_TIMING special_functions::bessel_j0", _ns_bessel_j0, _acc_bessel_j0)
    var _result_bessel_j0 = bessel_j0(0.5)
    var _summary_bessel_j0 = _summary_float64(_result_bessel_j0)
    print("MOJO_RESULT special_functions::bessel_j0", _summary_bessel_j0)
    var _acc_factorial_float: Float64 = 0.0
    var _t0_factorial_float = perf_counter_ns()
    for _ in range(N):
        _acc_factorial_float += factorial_float(5)
    var _t1_factorial_float = perf_counter_ns()
    var _ns_factorial_float = Float64(_t1_factorial_float - _t0_factorial_float) / Float64(N)
    print("MOJO_TIMING special_functions::factorial_float", _ns_factorial_float, _acc_factorial_float)
    var _result_factorial_float = factorial_float(5)
    var _summary_factorial_float = _summary_float64(_result_factorial_float)
    print("MOJO_RESULT special_functions::factorial_float", _summary_factorial_float)
    var _acc_double_factorial: Float64 = 0.0
    var _t0_double_factorial = perf_counter_ns()
    for _ in range(N):
        _acc_double_factorial += double_factorial(5)
    var _t1_double_factorial = perf_counter_ns()
    var _ns_double_factorial = Float64(_t1_double_factorial - _t0_double_factorial) / Float64(N)
    print("MOJO_TIMING special_functions::double_factorial", _ns_double_factorial, _acc_double_factorial)
    var _result_double_factorial = double_factorial(5)
    var _summary_double_factorial = _summary_float64(_result_double_factorial)
    print("MOJO_RESULT special_functions::double_factorial", _summary_double_factorial)
    var _acc_binomial_coefficient: Float64 = 0.0
    var _t0_binomial_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_binomial_coefficient += binomial_coefficient(5, 5)
    var _t1_binomial_coefficient = perf_counter_ns()
    var _ns_binomial_coefficient = Float64(_t1_binomial_coefficient - _t0_binomial_coefficient) / Float64(N)
    print("MOJO_TIMING special_functions::binomial_coefficient", _ns_binomial_coefficient, _acc_binomial_coefficient)
    var _result_binomial_coefficient = binomial_coefficient(5, 5)
    var _summary_binomial_coefficient = _summary_float64(_result_binomial_coefficient)
    print("MOJO_RESULT special_functions::binomial_coefficient", _summary_binomial_coefficient)
