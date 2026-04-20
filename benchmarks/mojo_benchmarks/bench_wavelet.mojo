"""bench_wavelet.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from wavelet import haar_forward, haar_inverse, haar_multilevel, haar_multilevel_inverse, threshold_hard, threshold_soft, denoise_haar, energy_ratio, detail_coefficients, approx_coefficients
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

    var _acc_haar_forward: Float64 = 0.0
    var _t0_haar_forward = perf_counter_ns()
    for _ in range(N):
        var _r_haar_forward = haar_forward(_lf5)
        _acc_haar_forward += Float64(len(_r_haar_forward))
    var _t1_haar_forward = perf_counter_ns()
    var _ns_haar_forward = Float64(_t1_haar_forward - _t0_haar_forward) / Float64(N)
    print("MOJO_TIMING wavelet::haar_forward", _ns_haar_forward, _acc_haar_forward)
    var _acc_haar_inverse: Float64 = 0.0
    var _t0_haar_inverse = perf_counter_ns()
    for _ in range(N):
        var _r_haar_inverse = haar_inverse(_lf5)
        _acc_haar_inverse += Float64(len(_r_haar_inverse))
    var _t1_haar_inverse = perf_counter_ns()
    var _ns_haar_inverse = Float64(_t1_haar_inverse - _t0_haar_inverse) / Float64(N)
    print("MOJO_TIMING wavelet::haar_inverse", _ns_haar_inverse, _acc_haar_inverse)
    var _acc_haar_multilevel: Float64 = 0.0
    var _t0_haar_multilevel = perf_counter_ns()
    for _ in range(N):
        var _r_haar_multilevel = haar_multilevel(_lf5, 5)
        _acc_haar_multilevel += Float64(len(_r_haar_multilevel))
    var _t1_haar_multilevel = perf_counter_ns()
    var _ns_haar_multilevel = Float64(_t1_haar_multilevel - _t0_haar_multilevel) / Float64(N)
    print("MOJO_TIMING wavelet::haar_multilevel", _ns_haar_multilevel, _acc_haar_multilevel)
    var _acc_haar_multilevel_inverse: Float64 = 0.0
    var _t0_haar_multilevel_inverse = perf_counter_ns()
    for _ in range(N):
        var _r_haar_multilevel_inverse = haar_multilevel_inverse(_lf5, 5)
        _acc_haar_multilevel_inverse += Float64(len(_r_haar_multilevel_inverse))
    var _t1_haar_multilevel_inverse = perf_counter_ns()
    var _ns_haar_multilevel_inverse = Float64(_t1_haar_multilevel_inverse - _t0_haar_multilevel_inverse) / Float64(N)
    print("MOJO_TIMING wavelet::haar_multilevel_inverse", _ns_haar_multilevel_inverse, _acc_haar_multilevel_inverse)
    var _acc_threshold_hard: Float64 = 0.0
    var _t0_threshold_hard = perf_counter_ns()
    for _ in range(N):
        var _r_threshold_hard = threshold_hard(_lf5, 0.5)
        _acc_threshold_hard += Float64(len(_r_threshold_hard))
    var _t1_threshold_hard = perf_counter_ns()
    var _ns_threshold_hard = Float64(_t1_threshold_hard - _t0_threshold_hard) / Float64(N)
    print("MOJO_TIMING wavelet::threshold_hard", _ns_threshold_hard, _acc_threshold_hard)
    var _acc_threshold_soft: Float64 = 0.0
    var _t0_threshold_soft = perf_counter_ns()
    for _ in range(N):
        var _r_threshold_soft = threshold_soft(_lf5, 0.5)
        _acc_threshold_soft += Float64(len(_r_threshold_soft))
    var _t1_threshold_soft = perf_counter_ns()
    var _ns_threshold_soft = Float64(_t1_threshold_soft - _t0_threshold_soft) / Float64(N)
    print("MOJO_TIMING wavelet::threshold_soft", _ns_threshold_soft, _acc_threshold_soft)
    var _acc_denoise_haar: Float64 = 0.0
    var _t0_denoise_haar = perf_counter_ns()
    for _ in range(N):
        var _r_denoise_haar = denoise_haar(_lf5, 0.5, 5)
        _acc_denoise_haar += Float64(len(_r_denoise_haar))
    var _t1_denoise_haar = perf_counter_ns()
    var _ns_denoise_haar = Float64(_t1_denoise_haar - _t0_denoise_haar) / Float64(N)
    print("MOJO_TIMING wavelet::denoise_haar", _ns_denoise_haar, _acc_denoise_haar)
    var _acc_energy_ratio: Float64 = 0.0
    var _t0_energy_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_energy_ratio += energy_ratio(_lf5)
    var _t1_energy_ratio = perf_counter_ns()
    var _ns_energy_ratio = Float64(_t1_energy_ratio - _t0_energy_ratio) / Float64(N)
    print("MOJO_TIMING wavelet::energy_ratio", _ns_energy_ratio, _acc_energy_ratio)
    var _acc_detail_coefficients: Float64 = 0.0
    var _t0_detail_coefficients = perf_counter_ns()
    for _ in range(N):
        var _r_detail_coefficients = detail_coefficients(_lf5)
        _acc_detail_coefficients += Float64(len(_r_detail_coefficients))
    var _t1_detail_coefficients = perf_counter_ns()
    var _ns_detail_coefficients = Float64(_t1_detail_coefficients - _t0_detail_coefficients) / Float64(N)
    print("MOJO_TIMING wavelet::detail_coefficients", _ns_detail_coefficients, _acc_detail_coefficients)
    var _acc_approx_coefficients: Float64 = 0.0
    var _t0_approx_coefficients = perf_counter_ns()
    for _ in range(N):
        var _r_approx_coefficients = approx_coefficients(_lf5)
        _acc_approx_coefficients += Float64(len(_r_approx_coefficients))
    var _t1_approx_coefficients = perf_counter_ns()
    var _ns_approx_coefficients = Float64(_t1_approx_coefficients - _t0_approx_coefficients) / Float64(N)
    print("MOJO_TIMING wavelet::approx_coefficients", _ns_approx_coefficients, _acc_approx_coefficients)
