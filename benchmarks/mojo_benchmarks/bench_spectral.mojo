"""bench_spectral.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from spectral import power_spectral_density, cross_spectral_density, coherence, spectral_centroid, spectral_bandwidth, spectral_rolloff, spectral_flatness, spectral_entropy, band_energy, peak_frequency
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

    var _acc_power_spectral_density: Float64 = 0.0
    var _t0_power_spectral_density = perf_counter_ns()
    for _ in range(N):
        var _r_power_spectral_density = power_spectral_density(_lf5, 0.5)
        _acc_power_spectral_density += Float64(len(_r_power_spectral_density))
    var _t1_power_spectral_density = perf_counter_ns()
    var _ns_power_spectral_density = Float64(_t1_power_spectral_density - _t0_power_spectral_density) / Float64(N)
    print("MOJO_TIMING spectral::power_spectral_density", _ns_power_spectral_density, _acc_power_spectral_density)
    var _acc_cross_spectral_density: Float64 = 0.0
    var _t0_cross_spectral_density = perf_counter_ns()
    for _ in range(N):
        var _r_cross_spectral_density = cross_spectral_density(_lf5, _lf5, 0.5)
        _acc_cross_spectral_density += Float64(len(_r_cross_spectral_density))
    var _t1_cross_spectral_density = perf_counter_ns()
    var _ns_cross_spectral_density = Float64(_t1_cross_spectral_density - _t0_cross_spectral_density) / Float64(N)
    print("MOJO_TIMING spectral::cross_spectral_density", _ns_cross_spectral_density, _acc_cross_spectral_density)
    var _acc_coherence: Float64 = 0.0
    var _t0_coherence = perf_counter_ns()
    for _ in range(N):
        var _r_coherence = coherence(_lf5, _lf5, 0.5)
        _acc_coherence += Float64(len(_r_coherence))
    var _t1_coherence = perf_counter_ns()
    var _ns_coherence = Float64(_t1_coherence - _t0_coherence) / Float64(N)
    print("MOJO_TIMING spectral::coherence", _ns_coherence, _acc_coherence)
    var _acc_spectral_centroid: Float64 = 0.0
    var _t0_spectral_centroid = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_centroid += spectral_centroid(_lf5, _lf5)
    var _t1_spectral_centroid = perf_counter_ns()
    var _ns_spectral_centroid = Float64(_t1_spectral_centroid - _t0_spectral_centroid) / Float64(N)
    print("MOJO_TIMING spectral::spectral_centroid", _ns_spectral_centroid, _acc_spectral_centroid)
    var _acc_spectral_bandwidth: Float64 = 0.0
    var _t0_spectral_bandwidth = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_bandwidth += spectral_bandwidth(_lf5, _lf5, 0.5)
    var _t1_spectral_bandwidth = perf_counter_ns()
    var _ns_spectral_bandwidth = Float64(_t1_spectral_bandwidth - _t0_spectral_bandwidth) / Float64(N)
    print("MOJO_TIMING spectral::spectral_bandwidth", _ns_spectral_bandwidth, _acc_spectral_bandwidth)
    var _acc_spectral_rolloff: Float64 = 0.0
    var _t0_spectral_rolloff = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_rolloff += spectral_rolloff(_lf5, _lf5, 0.5)
    var _t1_spectral_rolloff = perf_counter_ns()
    var _ns_spectral_rolloff = Float64(_t1_spectral_rolloff - _t0_spectral_rolloff) / Float64(N)
    print("MOJO_TIMING spectral::spectral_rolloff", _ns_spectral_rolloff, _acc_spectral_rolloff)
    var _acc_spectral_flatness: Float64 = 0.0
    var _t0_spectral_flatness = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_flatness += spectral_flatness(_lf5)
    var _t1_spectral_flatness = perf_counter_ns()
    var _ns_spectral_flatness = Float64(_t1_spectral_flatness - _t0_spectral_flatness) / Float64(N)
    print("MOJO_TIMING spectral::spectral_flatness", _ns_spectral_flatness, _acc_spectral_flatness)
    var _acc_spectral_entropy: Float64 = 0.0
    var _t0_spectral_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_entropy += spectral_entropy(_lf5)
    var _t1_spectral_entropy = perf_counter_ns()
    var _ns_spectral_entropy = Float64(_t1_spectral_entropy - _t0_spectral_entropy) / Float64(N)
    print("MOJO_TIMING spectral::spectral_entropy", _ns_spectral_entropy, _acc_spectral_entropy)
    var _acc_band_energy: Float64 = 0.0
    var _t0_band_energy = perf_counter_ns()
    for _ in range(N):
        _acc_band_energy += band_energy(_lf5, _lf5, 0.5, 0.5)
    var _t1_band_energy = perf_counter_ns()
    var _ns_band_energy = Float64(_t1_band_energy - _t0_band_energy) / Float64(N)
    print("MOJO_TIMING spectral::band_energy", _ns_band_energy, _acc_band_energy)
    var _acc_peak_frequency: Float64 = 0.0
    var _t0_peak_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_peak_frequency += peak_frequency(_lf5, _lf5)
    var _t1_peak_frequency = perf_counter_ns()
    var _ns_peak_frequency = Float64(_t1_peak_frequency - _t0_peak_frequency) / Float64(N)
    print("MOJO_TIMING spectral::peak_frequency", _ns_peak_frequency, _acc_peak_frequency)
