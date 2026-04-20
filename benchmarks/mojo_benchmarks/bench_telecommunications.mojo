"""bench_telecommunications.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from telecommunications import shannon_capacity, erlang_b, bit_error_rate_bpsk, spectral_efficiency, link_margin, thermal_noise_power, signal_to_noise_ratio, snr_db, data_rate_nyquist, propagation_delay, throughput, availability_percentage
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

    var _acc_shannon_capacity: Float64 = 0.0
    var _t0_shannon_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_shannon_capacity += shannon_capacity(0.5, 0.5)
    var _t1_shannon_capacity = perf_counter_ns()
    var _ns_shannon_capacity = Float64(_t1_shannon_capacity - _t0_shannon_capacity) / Float64(N)
    print("MOJO_TIMING telecommunications::shannon_capacity", _ns_shannon_capacity, _acc_shannon_capacity)
    var _acc_erlang_b: Float64 = 0.0
    var _t0_erlang_b = perf_counter_ns()
    for _ in range(N):
        _acc_erlang_b += erlang_b(5, 0.5)
    var _t1_erlang_b = perf_counter_ns()
    var _ns_erlang_b = Float64(_t1_erlang_b - _t0_erlang_b) / Float64(N)
    print("MOJO_TIMING telecommunications::erlang_b", _ns_erlang_b, _acc_erlang_b)
    var _acc_bit_error_rate_bpsk: Float64 = 0.0
    var _t0_bit_error_rate_bpsk = perf_counter_ns()
    for _ in range(N):
        _acc_bit_error_rate_bpsk += bit_error_rate_bpsk(0.5)
    var _t1_bit_error_rate_bpsk = perf_counter_ns()
    var _ns_bit_error_rate_bpsk = Float64(_t1_bit_error_rate_bpsk - _t0_bit_error_rate_bpsk) / Float64(N)
    print("MOJO_TIMING telecommunications::bit_error_rate_bpsk", _ns_bit_error_rate_bpsk, _acc_bit_error_rate_bpsk)
    var _acc_spectral_efficiency: Float64 = 0.0
    var _t0_spectral_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_efficiency += spectral_efficiency(0.5, 0.5)
    var _t1_spectral_efficiency = perf_counter_ns()
    var _ns_spectral_efficiency = Float64(_t1_spectral_efficiency - _t0_spectral_efficiency) / Float64(N)
    print("MOJO_TIMING telecommunications::spectral_efficiency", _ns_spectral_efficiency, _acc_spectral_efficiency)
    var _acc_link_margin: Float64 = 0.0
    var _t0_link_margin = perf_counter_ns()
    for _ in range(N):
        _acc_link_margin += link_margin(0.5, 0.5)
    var _t1_link_margin = perf_counter_ns()
    var _ns_link_margin = Float64(_t1_link_margin - _t0_link_margin) / Float64(N)
    print("MOJO_TIMING telecommunications::link_margin", _ns_link_margin, _acc_link_margin)
    var _acc_thermal_noise_power: Float64 = 0.0
    var _t0_thermal_noise_power = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_noise_power += thermal_noise_power(0.5, 0.5)
    var _t1_thermal_noise_power = perf_counter_ns()
    var _ns_thermal_noise_power = Float64(_t1_thermal_noise_power - _t0_thermal_noise_power) / Float64(N)
    print("MOJO_TIMING telecommunications::thermal_noise_power", _ns_thermal_noise_power, _acc_thermal_noise_power)
    var _acc_signal_to_noise_ratio: Float64 = 0.0
    var _t0_signal_to_noise_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_signal_to_noise_ratio += signal_to_noise_ratio(0.5, 0.5)
    var _t1_signal_to_noise_ratio = perf_counter_ns()
    var _ns_signal_to_noise_ratio = Float64(_t1_signal_to_noise_ratio - _t0_signal_to_noise_ratio) / Float64(N)
    print("MOJO_TIMING telecommunications::signal_to_noise_ratio", _ns_signal_to_noise_ratio, _acc_signal_to_noise_ratio)
    var _acc_snr_db: Float64 = 0.0
    var _t0_snr_db = perf_counter_ns()
    for _ in range(N):
        _acc_snr_db += snr_db(0.5)
    var _t1_snr_db = perf_counter_ns()
    var _ns_snr_db = Float64(_t1_snr_db - _t0_snr_db) / Float64(N)
    print("MOJO_TIMING telecommunications::snr_db", _ns_snr_db, _acc_snr_db)
    var _acc_data_rate_nyquist: Float64 = 0.0
    var _t0_data_rate_nyquist = perf_counter_ns()
    for _ in range(N):
        _acc_data_rate_nyquist += data_rate_nyquist(0.5, 0.5)
    var _t1_data_rate_nyquist = perf_counter_ns()
    var _ns_data_rate_nyquist = Float64(_t1_data_rate_nyquist - _t0_data_rate_nyquist) / Float64(N)
    print("MOJO_TIMING telecommunications::data_rate_nyquist", _ns_data_rate_nyquist, _acc_data_rate_nyquist)
    var _acc_propagation_delay: Float64 = 0.0
    var _t0_propagation_delay = perf_counter_ns()
    for _ in range(N):
        _acc_propagation_delay += propagation_delay(0.5, 0.5)
    var _t1_propagation_delay = perf_counter_ns()
    var _ns_propagation_delay = Float64(_t1_propagation_delay - _t0_propagation_delay) / Float64(N)
    print("MOJO_TIMING telecommunications::propagation_delay", _ns_propagation_delay, _acc_propagation_delay)
    var _acc_throughput: Float64 = 0.0
    var _t0_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_throughput += throughput(0.5, 0.5)
    var _t1_throughput = perf_counter_ns()
    var _ns_throughput = Float64(_t1_throughput - _t0_throughput) / Float64(N)
    print("MOJO_TIMING telecommunications::throughput", _ns_throughput, _acc_throughput)
    var _acc_availability_percentage: Float64 = 0.0
    var _t0_availability_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_availability_percentage += availability_percentage(0.5, 0.5)
    var _t1_availability_percentage = perf_counter_ns()
    var _ns_availability_percentage = Float64(_t1_availability_percentage - _t0_availability_percentage) / Float64(N)
    print("MOJO_TIMING telecommunications::availability_percentage", _ns_availability_percentage, _acc_availability_percentage)
