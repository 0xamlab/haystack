"""bench_signal_processing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from signal_processing import hamming_window, hann_window, blackman_window, apply_window, peak_detect, zero_crossings, spectral_energy, spectral_centroid, spectral_flatness, signal_power
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

    var _acc_hamming_window: Float64 = 0.0
    var _t0_hamming_window = perf_counter_ns()
    for _ in range(N):
        var _r_hamming_window = hamming_window(5)
        _acc_hamming_window += Float64(len(_r_hamming_window))
    var _t1_hamming_window = perf_counter_ns()
    var _ns_hamming_window = Float64(_t1_hamming_window - _t0_hamming_window) / Float64(N)
    print("MOJO_TIMING signal_processing::hamming_window", _ns_hamming_window, _acc_hamming_window)
    var _acc_hann_window: Float64 = 0.0
    var _t0_hann_window = perf_counter_ns()
    for _ in range(N):
        var _r_hann_window = hann_window(5)
        _acc_hann_window += Float64(len(_r_hann_window))
    var _t1_hann_window = perf_counter_ns()
    var _ns_hann_window = Float64(_t1_hann_window - _t0_hann_window) / Float64(N)
    print("MOJO_TIMING signal_processing::hann_window", _ns_hann_window, _acc_hann_window)
    var _acc_blackman_window: Float64 = 0.0
    var _t0_blackman_window = perf_counter_ns()
    for _ in range(N):
        var _r_blackman_window = blackman_window(5)
        _acc_blackman_window += Float64(len(_r_blackman_window))
    var _t1_blackman_window = perf_counter_ns()
    var _ns_blackman_window = Float64(_t1_blackman_window - _t0_blackman_window) / Float64(N)
    print("MOJO_TIMING signal_processing::blackman_window", _ns_blackman_window, _acc_blackman_window)
    var _acc_apply_window: Float64 = 0.0
    var _t0_apply_window = perf_counter_ns()
    for _ in range(N):
        var _r_apply_window = apply_window(_lf5, _lf5)
        _acc_apply_window += Float64(len(_r_apply_window))
    var _t1_apply_window = perf_counter_ns()
    var _ns_apply_window = Float64(_t1_apply_window - _t0_apply_window) / Float64(N)
    print("MOJO_TIMING signal_processing::apply_window", _ns_apply_window, _acc_apply_window)
    var _acc_peak_detect: Float64 = 0.0
    var _t0_peak_detect = perf_counter_ns()
    for _ in range(N):
        var _r_peak_detect = peak_detect(_lf5, 0.5)
        _acc_peak_detect += Float64(len(_r_peak_detect))
    var _t1_peak_detect = perf_counter_ns()
    var _ns_peak_detect = Float64(_t1_peak_detect - _t0_peak_detect) / Float64(N)
    print("MOJO_TIMING signal_processing::peak_detect", _ns_peak_detect, _acc_peak_detect)
    var _acc_zero_crossings: Float64 = 0.0
    var _t0_zero_crossings = perf_counter_ns()
    for _ in range(N):
        var _r_zero_crossings = zero_crossings(_lf5)
        _acc_zero_crossings += Float64(len(_r_zero_crossings))
    var _t1_zero_crossings = perf_counter_ns()
    var _ns_zero_crossings = Float64(_t1_zero_crossings - _t0_zero_crossings) / Float64(N)
    print("MOJO_TIMING signal_processing::zero_crossings", _ns_zero_crossings, _acc_zero_crossings)
    var _acc_spectral_energy: Float64 = 0.0
    var _t0_spectral_energy = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_energy += spectral_energy(_lf5)
    var _t1_spectral_energy = perf_counter_ns()
    var _ns_spectral_energy = Float64(_t1_spectral_energy - _t0_spectral_energy) / Float64(N)
    print("MOJO_TIMING signal_processing::spectral_energy", _ns_spectral_energy, _acc_spectral_energy)
    var _acc_spectral_centroid: Float64 = 0.0
    var _t0_spectral_centroid = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_centroid += spectral_centroid(_lf5, 0.5)
    var _t1_spectral_centroid = perf_counter_ns()
    var _ns_spectral_centroid = Float64(_t1_spectral_centroid - _t0_spectral_centroid) / Float64(N)
    print("MOJO_TIMING signal_processing::spectral_centroid", _ns_spectral_centroid, _acc_spectral_centroid)
    var _acc_spectral_flatness: Float64 = 0.0
    var _t0_spectral_flatness = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_flatness += spectral_flatness(_lf5)
    var _t1_spectral_flatness = perf_counter_ns()
    var _ns_spectral_flatness = Float64(_t1_spectral_flatness - _t0_spectral_flatness) / Float64(N)
    print("MOJO_TIMING signal_processing::spectral_flatness", _ns_spectral_flatness, _acc_spectral_flatness)
    var _acc_signal_power: Float64 = 0.0
    var _t0_signal_power = perf_counter_ns()
    for _ in range(N):
        _acc_signal_power += signal_power(_lf5)
    var _t1_signal_power = perf_counter_ns()
    var _ns_signal_power = Float64(_t1_signal_power - _t0_signal_power) / Float64(N)
    print("MOJO_TIMING signal_processing::signal_power", _ns_signal_power, _acc_signal_power)
