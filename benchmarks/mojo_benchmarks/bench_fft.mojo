"""bench_fft.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fft import next_power_of_2, zero_pad, fft, power_spectrum
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

    var _acc_next_power_of_2: Float64 = 0.0
    var _t0_next_power_of_2 = perf_counter_ns()
    for _ in range(N):
        _acc_next_power_of_2 += Float64(next_power_of_2(5))
    var _t1_next_power_of_2 = perf_counter_ns()
    var _ns_next_power_of_2 = Float64(_t1_next_power_of_2 - _t0_next_power_of_2) / Float64(N)
    print("MOJO_TIMING fft::next_power_of_2", _ns_next_power_of_2, _acc_next_power_of_2)
    var _acc_zero_pad: Float64 = 0.0
    var _t0_zero_pad = perf_counter_ns()
    for _ in range(N):
        var _r_zero_pad = zero_pad(_lf5, 5)
        _acc_zero_pad += Float64(len(_r_zero_pad))
    var _t1_zero_pad = perf_counter_ns()
    var _ns_zero_pad = Float64(_t1_zero_pad - _t0_zero_pad) / Float64(N)
    print("MOJO_TIMING fft::zero_pad", _ns_zero_pad, _acc_zero_pad)
    var _acc_fft: Float64 = 0.0
    var _t0_fft = perf_counter_ns()
    for _ in range(N):
        var _r_fft = fft(_lf5)
        _acc_fft += Float64(len(_r_fft))
    var _t1_fft = perf_counter_ns()
    var _ns_fft = Float64(_t1_fft - _t0_fft) / Float64(N)
    print("MOJO_TIMING fft::fft", _ns_fft, _acc_fft)
    var _acc_power_spectrum: Float64 = 0.0
    var _t0_power_spectrum = perf_counter_ns()
    for _ in range(N):
        var _r_power_spectrum = power_spectrum(_lf5)
        _acc_power_spectrum += Float64(len(_r_power_spectrum))
    var _t1_power_spectrum = perf_counter_ns()
    var _ns_power_spectrum = Float64(_t1_power_spectrum - _t0_power_spectrum) / Float64(N)
    print("MOJO_TIMING fft::power_spectrum", _ns_power_spectrum, _acc_power_spectrum)
