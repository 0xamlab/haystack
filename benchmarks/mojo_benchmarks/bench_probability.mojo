"""bench_probability.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from probability import bayes, joint_probability, total_probability, factorial, combinations, permutations, binomial_pmf, poisson_pmf, entropy, kl_divergence, mutual_information
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

    var _acc_bayes: Float64 = 0.0
    var _t0_bayes = perf_counter_ns()
    for _ in range(N):
        _acc_bayes += bayes(0.5, 0.5, 0.5)
    var _t1_bayes = perf_counter_ns()
    var _ns_bayes = Float64(_t1_bayes - _t0_bayes) / Float64(N)
    print("MOJO_TIMING probability::bayes", _ns_bayes, _acc_bayes)
    var _acc_joint_probability: Float64 = 0.0
    var _t0_joint_probability = perf_counter_ns()
    for _ in range(N):
        _acc_joint_probability += joint_probability(0.5, 0.5)
    var _t1_joint_probability = perf_counter_ns()
    var _ns_joint_probability = Float64(_t1_joint_probability - _t0_joint_probability) / Float64(N)
    print("MOJO_TIMING probability::joint_probability", _ns_joint_probability, _acc_joint_probability)
    var _acc_total_probability: Float64 = 0.0
    var _t0_total_probability = perf_counter_ns()
    for _ in range(N):
        _acc_total_probability += total_probability(_lf5, _lf5)
    var _t1_total_probability = perf_counter_ns()
    var _ns_total_probability = Float64(_t1_total_probability - _t0_total_probability) / Float64(N)
    print("MOJO_TIMING probability::total_probability", _ns_total_probability, _acc_total_probability)
    var _acc_factorial: Float64 = 0.0
    var _t0_factorial = perf_counter_ns()
    for _ in range(N):
        _acc_factorial += factorial(5)
    var _t1_factorial = perf_counter_ns()
    var _ns_factorial = Float64(_t1_factorial - _t0_factorial) / Float64(N)
    print("MOJO_TIMING probability::factorial", _ns_factorial, _acc_factorial)
    var _acc_combinations: Float64 = 0.0
    var _t0_combinations = perf_counter_ns()
    for _ in range(N):
        _acc_combinations += combinations(5, 5)
    var _t1_combinations = perf_counter_ns()
    var _ns_combinations = Float64(_t1_combinations - _t0_combinations) / Float64(N)
    print("MOJO_TIMING probability::combinations", _ns_combinations, _acc_combinations)
    var _acc_permutations: Float64 = 0.0
    var _t0_permutations = perf_counter_ns()
    for _ in range(N):
        _acc_permutations += permutations(5, 5)
    var _t1_permutations = perf_counter_ns()
    var _ns_permutations = Float64(_t1_permutations - _t0_permutations) / Float64(N)
    print("MOJO_TIMING probability::permutations", _ns_permutations, _acc_permutations)
    var _acc_binomial_pmf: Float64 = 0.0
    var _t0_binomial_pmf = perf_counter_ns()
    for _ in range(N):
        _acc_binomial_pmf += binomial_pmf(5, 5, 0.5)
    var _t1_binomial_pmf = perf_counter_ns()
    var _ns_binomial_pmf = Float64(_t1_binomial_pmf - _t0_binomial_pmf) / Float64(N)
    print("MOJO_TIMING probability::binomial_pmf", _ns_binomial_pmf, _acc_binomial_pmf)
    var _acc_poisson_pmf: Float64 = 0.0
    var _t0_poisson_pmf = perf_counter_ns()
    for _ in range(N):
        _acc_poisson_pmf += poisson_pmf(5, 0.5)
    var _t1_poisson_pmf = perf_counter_ns()
    var _ns_poisson_pmf = Float64(_t1_poisson_pmf - _t0_poisson_pmf) / Float64(N)
    print("MOJO_TIMING probability::poisson_pmf", _ns_poisson_pmf, _acc_poisson_pmf)
    var _acc_entropy: Float64 = 0.0
    var _t0_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_entropy += entropy(_lf5)
    var _t1_entropy = perf_counter_ns()
    var _ns_entropy = Float64(_t1_entropy - _t0_entropy) / Float64(N)
    print("MOJO_TIMING probability::entropy", _ns_entropy, _acc_entropy)
    var _acc_kl_divergence: Float64 = 0.0
    var _t0_kl_divergence = perf_counter_ns()
    for _ in range(N):
        _acc_kl_divergence += kl_divergence(_lf5, _lf5)
    var _t1_kl_divergence = perf_counter_ns()
    var _ns_kl_divergence = Float64(_t1_kl_divergence - _t0_kl_divergence) / Float64(N)
    print("MOJO_TIMING probability::kl_divergence", _ns_kl_divergence, _acc_kl_divergence)
    var _acc_mutual_information: Float64 = 0.0
    var _t0_mutual_information = perf_counter_ns()
    for _ in range(N):
        _acc_mutual_information += mutual_information([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_mutual_information = perf_counter_ns()
    var _ns_mutual_information = Float64(_t1_mutual_information - _t0_mutual_information) / Float64(N)
    print("MOJO_TIMING probability::mutual_information", _ns_mutual_information, _acc_mutual_information)
