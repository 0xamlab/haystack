"""bench_probability.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from probability import bayes, joint_probability, total_probability, factorial, combinations, permutations, binomial_pmf, poisson_pmf, entropy, kl_divergence, mutual_information
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

    var _acc_bayes: Float64 = 0.0
    var _t0_bayes = perf_counter_ns()
    for _ in range(N):
        _acc_bayes += bayes(0.5, 0.5, 0.5)
    var _t1_bayes = perf_counter_ns()
    var _ns_bayes = Float64(_t1_bayes - _t0_bayes) / Float64(N)
    print("MOJO_TIMING probability::bayes", _ns_bayes, _acc_bayes)
    var _result_bayes = bayes(0.5, 0.5, 0.5)
    var _summary_bayes = _summary_float64(_result_bayes)
    print("MOJO_RESULT probability::bayes", _summary_bayes)
    var _acc_joint_probability: Float64 = 0.0
    var _t0_joint_probability = perf_counter_ns()
    for _ in range(N):
        _acc_joint_probability += joint_probability(0.5, 0.5)
    var _t1_joint_probability = perf_counter_ns()
    var _ns_joint_probability = Float64(_t1_joint_probability - _t0_joint_probability) / Float64(N)
    print("MOJO_TIMING probability::joint_probability", _ns_joint_probability, _acc_joint_probability)
    var _result_joint_probability = joint_probability(0.5, 0.5)
    var _summary_joint_probability = _summary_float64(_result_joint_probability)
    print("MOJO_RESULT probability::joint_probability", _summary_joint_probability)
    var _acc_total_probability: Float64 = 0.0
    var _t0_total_probability = perf_counter_ns()
    for _ in range(N):
        _acc_total_probability += total_probability(_lf5, _lf5)
    var _t1_total_probability = perf_counter_ns()
    var _ns_total_probability = Float64(_t1_total_probability - _t0_total_probability) / Float64(N)
    print("MOJO_TIMING probability::total_probability", _ns_total_probability, _acc_total_probability)
    var _result_total_probability = total_probability(_lf5, _lf5)
    var _summary_total_probability = _summary_float64(_result_total_probability)
    print("MOJO_RESULT probability::total_probability", _summary_total_probability)
    var _acc_factorial: Float64 = 0.0
    var _t0_factorial = perf_counter_ns()
    for _ in range(N):
        _acc_factorial += factorial(5)
    var _t1_factorial = perf_counter_ns()
    var _ns_factorial = Float64(_t1_factorial - _t0_factorial) / Float64(N)
    print("MOJO_TIMING probability::factorial", _ns_factorial, _acc_factorial)
    var _result_factorial = factorial(5)
    var _summary_factorial = _summary_float64(_result_factorial)
    print("MOJO_RESULT probability::factorial", _summary_factorial)
    var _acc_combinations: Float64 = 0.0
    var _t0_combinations = perf_counter_ns()
    for _ in range(N):
        _acc_combinations += combinations(5, 5)
    var _t1_combinations = perf_counter_ns()
    var _ns_combinations = Float64(_t1_combinations - _t0_combinations) / Float64(N)
    print("MOJO_TIMING probability::combinations", _ns_combinations, _acc_combinations)
    var _result_combinations = combinations(5, 5)
    var _summary_combinations = _summary_float64(_result_combinations)
    print("MOJO_RESULT probability::combinations", _summary_combinations)
    var _acc_permutations: Float64 = 0.0
    var _t0_permutations = perf_counter_ns()
    for _ in range(N):
        _acc_permutations += permutations(5, 5)
    var _t1_permutations = perf_counter_ns()
    var _ns_permutations = Float64(_t1_permutations - _t0_permutations) / Float64(N)
    print("MOJO_TIMING probability::permutations", _ns_permutations, _acc_permutations)
    var _result_permutations = permutations(5, 5)
    var _summary_permutations = _summary_float64(_result_permutations)
    print("MOJO_RESULT probability::permutations", _summary_permutations)
    var _acc_binomial_pmf: Float64 = 0.0
    var _t0_binomial_pmf = perf_counter_ns()
    for _ in range(N):
        _acc_binomial_pmf += binomial_pmf(5, 5, 0.5)
    var _t1_binomial_pmf = perf_counter_ns()
    var _ns_binomial_pmf = Float64(_t1_binomial_pmf - _t0_binomial_pmf) / Float64(N)
    print("MOJO_TIMING probability::binomial_pmf", _ns_binomial_pmf, _acc_binomial_pmf)
    var _result_binomial_pmf = binomial_pmf(5, 5, 0.5)
    var _summary_binomial_pmf = _summary_float64(_result_binomial_pmf)
    print("MOJO_RESULT probability::binomial_pmf", _summary_binomial_pmf)
    var _acc_poisson_pmf: Float64 = 0.0
    var _t0_poisson_pmf = perf_counter_ns()
    for _ in range(N):
        _acc_poisson_pmf += poisson_pmf(5, 0.5)
    var _t1_poisson_pmf = perf_counter_ns()
    var _ns_poisson_pmf = Float64(_t1_poisson_pmf - _t0_poisson_pmf) / Float64(N)
    print("MOJO_TIMING probability::poisson_pmf", _ns_poisson_pmf, _acc_poisson_pmf)
    var _result_poisson_pmf = poisson_pmf(5, 0.5)
    var _summary_poisson_pmf = _summary_float64(_result_poisson_pmf)
    print("MOJO_RESULT probability::poisson_pmf", _summary_poisson_pmf)
    var _acc_entropy: Float64 = 0.0
    var _t0_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_entropy += entropy(_lf5)
    var _t1_entropy = perf_counter_ns()
    var _ns_entropy = Float64(_t1_entropy - _t0_entropy) / Float64(N)
    print("MOJO_TIMING probability::entropy", _ns_entropy, _acc_entropy)
    var _result_entropy = entropy(_lf5)
    var _summary_entropy = _summary_float64(_result_entropy)
    print("MOJO_RESULT probability::entropy", _summary_entropy)
    var _acc_kl_divergence: Float64 = 0.0
    var _t0_kl_divergence = perf_counter_ns()
    for _ in range(N):
        _acc_kl_divergence += kl_divergence(_lf5, _lf5)
    var _t1_kl_divergence = perf_counter_ns()
    var _ns_kl_divergence = Float64(_t1_kl_divergence - _t0_kl_divergence) / Float64(N)
    print("MOJO_TIMING probability::kl_divergence", _ns_kl_divergence, _acc_kl_divergence)
    var _result_kl_divergence = kl_divergence(_lf5, _lf5)
    var _summary_kl_divergence = _summary_float64(_result_kl_divergence)
    print("MOJO_RESULT probability::kl_divergence", _summary_kl_divergence)
    var _acc_mutual_information: Float64 = 0.0
    var _t0_mutual_information = perf_counter_ns()
    for _ in range(N):
        _acc_mutual_information += mutual_information([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_mutual_information = perf_counter_ns()
    var _ns_mutual_information = Float64(_t1_mutual_information - _t0_mutual_information) / Float64(N)
    print("MOJO_TIMING probability::mutual_information", _ns_mutual_information, _acc_mutual_information)
    var _result_mutual_information = mutual_information([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_mutual_information = _summary_float64(_result_mutual_information)
    print("MOJO_RESULT probability::mutual_information", _summary_mutual_information)
