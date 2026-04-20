"""bench_sampling.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sampling import halton_sequence, halton_2d, stratified_sample_1d, latin_hypercube_sample, sobol_like_2d, discrepancy_l2_star
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

    var _acc_halton_sequence: Float64 = 0.0
    var _t0_halton_sequence = perf_counter_ns()
    for _ in range(N):
        var _r_halton_sequence = halton_sequence(5, 5)
        _acc_halton_sequence += Float64(len(_r_halton_sequence))
    var _t1_halton_sequence = perf_counter_ns()
    var _ns_halton_sequence = Float64(_t1_halton_sequence - _t0_halton_sequence) / Float64(N)
    print("MOJO_TIMING sampling::halton_sequence", _ns_halton_sequence, _acc_halton_sequence)
    var _acc_halton_2d: Float64 = 0.0
    var _t0_halton_2d = perf_counter_ns()
    for _ in range(N):
        var _r_halton_2d = halton_2d(5)
        _acc_halton_2d += Float64(len(_r_halton_2d))
    var _t1_halton_2d = perf_counter_ns()
    var _ns_halton_2d = Float64(_t1_halton_2d - _t0_halton_2d) / Float64(N)
    print("MOJO_TIMING sampling::halton_2d", _ns_halton_2d, _acc_halton_2d)
    var _acc_stratified_sample_1d: Float64 = 0.0
    var _t0_stratified_sample_1d = perf_counter_ns()
    for _ in range(N):
        var _r_stratified_sample_1d = stratified_sample_1d(5)
        _acc_stratified_sample_1d += Float64(len(_r_stratified_sample_1d))
    var _t1_stratified_sample_1d = perf_counter_ns()
    var _ns_stratified_sample_1d = Float64(_t1_stratified_sample_1d - _t0_stratified_sample_1d) / Float64(N)
    print("MOJO_TIMING sampling::stratified_sample_1d", _ns_stratified_sample_1d, _acc_stratified_sample_1d)
    var _acc_latin_hypercube_sample: Float64 = 0.0
    var _t0_latin_hypercube_sample = perf_counter_ns()
    for _ in range(N):
        var _r_latin_hypercube_sample = latin_hypercube_sample(5, 5)
        _acc_latin_hypercube_sample += Float64(len(_r_latin_hypercube_sample))
    var _t1_latin_hypercube_sample = perf_counter_ns()
    var _ns_latin_hypercube_sample = Float64(_t1_latin_hypercube_sample - _t0_latin_hypercube_sample) / Float64(N)
    print("MOJO_TIMING sampling::latin_hypercube_sample", _ns_latin_hypercube_sample, _acc_latin_hypercube_sample)
    var _acc_sobol_like_2d: Float64 = 0.0
    var _t0_sobol_like_2d = perf_counter_ns()
    for _ in range(N):
        var _r_sobol_like_2d = sobol_like_2d(5)
        _acc_sobol_like_2d += Float64(len(_r_sobol_like_2d))
    var _t1_sobol_like_2d = perf_counter_ns()
    var _ns_sobol_like_2d = Float64(_t1_sobol_like_2d - _t0_sobol_like_2d) / Float64(N)
    print("MOJO_TIMING sampling::sobol_like_2d", _ns_sobol_like_2d, _acc_sobol_like_2d)
    var _acc_discrepancy_l2_star: Float64 = 0.0
    var _t0_discrepancy_l2_star = perf_counter_ns()
    for _ in range(N):
        _acc_discrepancy_l2_star += discrepancy_l2_star([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_discrepancy_l2_star = perf_counter_ns()
    var _ns_discrepancy_l2_star = Float64(_t1_discrepancy_l2_star - _t0_discrepancy_l2_star) / Float64(N)
    print("MOJO_TIMING sampling::discrepancy_l2_star", _ns_discrepancy_l2_star, _acc_discrepancy_l2_star)
