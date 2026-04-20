"""bench_random_utils.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from random_utils import random_choice, random_shuffle, random_sample, random_bootstrap, random_uniform_int, random_permutation, stratified_sample
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

    var _acc_random_choice: Float64 = 0.0
    var _t0_random_choice = perf_counter_ns()
    for _ in range(N):
        _acc_random_choice += Float64(random_choice(_lf5))
    var _t1_random_choice = perf_counter_ns()
    var _ns_random_choice = Float64(_t1_random_choice - _t0_random_choice) / Float64(N)
    print("MOJO_TIMING random_utils::random_choice", _ns_random_choice, _acc_random_choice)
    var _acc_random_shuffle: Float64 = 0.0
    var _t0_random_shuffle = perf_counter_ns()
    for _ in range(N):
        _ = random_shuffle(_lf5)
    var _t1_random_shuffle = perf_counter_ns()
    var _ns_random_shuffle = Float64(_t1_random_shuffle - _t0_random_shuffle) / Float64(N)
    print("MOJO_TIMING random_utils::random_shuffle", _ns_random_shuffle, _acc_random_shuffle)
    var _acc_random_sample: Float64 = 0.0
    var _t0_random_sample = perf_counter_ns()
    for _ in range(N):
        var _r_random_sample = random_sample(_lf5, 5)
        _acc_random_sample += Float64(len(_r_random_sample))
    var _t1_random_sample = perf_counter_ns()
    var _ns_random_sample = Float64(_t1_random_sample - _t0_random_sample) / Float64(N)
    print("MOJO_TIMING random_utils::random_sample", _ns_random_sample, _acc_random_sample)
    var _acc_random_bootstrap: Float64 = 0.0
    var _t0_random_bootstrap = perf_counter_ns()
    for _ in range(N):
        var _r_random_bootstrap = random_bootstrap(_lf5, 5)
        _acc_random_bootstrap += Float64(len(_r_random_bootstrap))
    var _t1_random_bootstrap = perf_counter_ns()
    var _ns_random_bootstrap = Float64(_t1_random_bootstrap - _t0_random_bootstrap) / Float64(N)
    print("MOJO_TIMING random_utils::random_bootstrap", _ns_random_bootstrap, _acc_random_bootstrap)
    var _acc_random_uniform_int: Float64 = 0.0
    var _t0_random_uniform_int = perf_counter_ns()
    for _ in range(N):
        _acc_random_uniform_int += Float64(random_uniform_int(5, 5))
    var _t1_random_uniform_int = perf_counter_ns()
    var _ns_random_uniform_int = Float64(_t1_random_uniform_int - _t0_random_uniform_int) / Float64(N)
    print("MOJO_TIMING random_utils::random_uniform_int", _ns_random_uniform_int, _acc_random_uniform_int)
    var _acc_random_permutation: Float64 = 0.0
    var _t0_random_permutation = perf_counter_ns()
    for _ in range(N):
        var _r_random_permutation = random_permutation(5)
        _acc_random_permutation += Float64(len(_r_random_permutation))
    var _t1_random_permutation = perf_counter_ns()
    var _ns_random_permutation = Float64(_t1_random_permutation - _t0_random_permutation) / Float64(N)
    print("MOJO_TIMING random_utils::random_permutation", _ns_random_permutation, _acc_random_permutation)
    var _acc_stratified_sample: Float64 = 0.0
    var _t0_stratified_sample = perf_counter_ns()
    for _ in range(N):
        var _r_stratified_sample = stratified_sample(_lf5, 5)
        _acc_stratified_sample += Float64(len(_r_stratified_sample))
    var _t1_stratified_sample = perf_counter_ns()
    var _ns_stratified_sample = Float64(_t1_stratified_sample - _t0_stratified_sample) / Float64(N)
    print("MOJO_TIMING random_utils::stratified_sample", _ns_stratified_sample, _acc_stratified_sample)
