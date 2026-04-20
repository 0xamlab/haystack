"""bench_reservoir.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from reservoir import reservoir_sample, weighted_reservoir_sample, reservoir_sample_indices, bootstrap_sample, systematic_sample, sample_with_replacement, sample_without_replacement
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

    var _acc_reservoir_sample: Float64 = 0.0
    var _t0_reservoir_sample = perf_counter_ns()
    for _ in range(N):
        var _r_reservoir_sample = reservoir_sample(_lf5, 5)
        _acc_reservoir_sample += Float64(len(_r_reservoir_sample))
    var _t1_reservoir_sample = perf_counter_ns()
    var _ns_reservoir_sample = Float64(_t1_reservoir_sample - _t0_reservoir_sample) / Float64(N)
    print("MOJO_TIMING reservoir::reservoir_sample", _ns_reservoir_sample, _acc_reservoir_sample)
    var _acc_weighted_reservoir_sample: Float64 = 0.0
    var _t0_weighted_reservoir_sample = perf_counter_ns()
    for _ in range(N):
        var _r_weighted_reservoir_sample = weighted_reservoir_sample(_lf5, _lf5, 5)
        _acc_weighted_reservoir_sample += Float64(len(_r_weighted_reservoir_sample))
    var _t1_weighted_reservoir_sample = perf_counter_ns()
    var _ns_weighted_reservoir_sample = Float64(_t1_weighted_reservoir_sample - _t0_weighted_reservoir_sample) / Float64(N)
    print("MOJO_TIMING reservoir::weighted_reservoir_sample", _ns_weighted_reservoir_sample, _acc_weighted_reservoir_sample)
    var _acc_reservoir_sample_indices: Float64 = 0.0
    var _t0_reservoir_sample_indices = perf_counter_ns()
    for _ in range(N):
        var _r_reservoir_sample_indices = reservoir_sample_indices(5, 5)
        _acc_reservoir_sample_indices += Float64(len(_r_reservoir_sample_indices))
    var _t1_reservoir_sample_indices = perf_counter_ns()
    var _ns_reservoir_sample_indices = Float64(_t1_reservoir_sample_indices - _t0_reservoir_sample_indices) / Float64(N)
    print("MOJO_TIMING reservoir::reservoir_sample_indices", _ns_reservoir_sample_indices, _acc_reservoir_sample_indices)
    var _acc_bootstrap_sample: Float64 = 0.0
    var _t0_bootstrap_sample = perf_counter_ns()
    for _ in range(N):
        var _r_bootstrap_sample = bootstrap_sample(_lf5)
        _acc_bootstrap_sample += Float64(len(_r_bootstrap_sample))
    var _t1_bootstrap_sample = perf_counter_ns()
    var _ns_bootstrap_sample = Float64(_t1_bootstrap_sample - _t0_bootstrap_sample) / Float64(N)
    print("MOJO_TIMING reservoir::bootstrap_sample", _ns_bootstrap_sample, _acc_bootstrap_sample)
    var _acc_systematic_sample: Float64 = 0.0
    var _t0_systematic_sample = perf_counter_ns()
    for _ in range(N):
        var _r_systematic_sample = systematic_sample(_lf5, 5)
        _acc_systematic_sample += Float64(len(_r_systematic_sample))
    var _t1_systematic_sample = perf_counter_ns()
    var _ns_systematic_sample = Float64(_t1_systematic_sample - _t0_systematic_sample) / Float64(N)
    print("MOJO_TIMING reservoir::systematic_sample", _ns_systematic_sample, _acc_systematic_sample)
    var _acc_sample_with_replacement: Float64 = 0.0
    var _t0_sample_with_replacement = perf_counter_ns()
    for _ in range(N):
        var _r_sample_with_replacement = sample_with_replacement(_lf5, 5)
        _acc_sample_with_replacement += Float64(len(_r_sample_with_replacement))
    var _t1_sample_with_replacement = perf_counter_ns()
    var _ns_sample_with_replacement = Float64(_t1_sample_with_replacement - _t0_sample_with_replacement) / Float64(N)
    print("MOJO_TIMING reservoir::sample_with_replacement", _ns_sample_with_replacement, _acc_sample_with_replacement)
    var _acc_sample_without_replacement: Float64 = 0.0
    var _t0_sample_without_replacement = perf_counter_ns()
    for _ in range(N):
        var _r_sample_without_replacement = sample_without_replacement(_lf5, 5)
        _acc_sample_without_replacement += Float64(len(_r_sample_without_replacement))
    var _t1_sample_without_replacement = perf_counter_ns()
    var _ns_sample_without_replacement = Float64(_t1_sample_without_replacement - _t0_sample_without_replacement) / Float64(N)
    print("MOJO_TIMING reservoir::sample_without_replacement", _ns_sample_without_replacement, _acc_sample_without_replacement)
