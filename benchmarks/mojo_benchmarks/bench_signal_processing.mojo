"""bench_signal_processing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from signal_processing import hamming_window, hann_window, blackman_window, apply_window, peak_detect, zero_crossings, spectral_energy, spectral_centroid, spectral_flatness, signal_power
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

    var _acc_hamming_window: Float64 = 0.0
    var _t0_hamming_window = perf_counter_ns()
    for _ in range(N):
        var _r_hamming_window = hamming_window(5)
        _acc_hamming_window += Float64(len(_r_hamming_window))
    var _t1_hamming_window = perf_counter_ns()
    var _ns_hamming_window = Float64(_t1_hamming_window - _t0_hamming_window) / Float64(N)
    print("MOJO_TIMING signal_processing::hamming_window", _ns_hamming_window, _acc_hamming_window)
    var _result_hamming_window = hamming_window(5)
    var _summary_hamming_window = _summary_list_float64(_result_hamming_window)
    print("MOJO_RESULT signal_processing::hamming_window", _summary_hamming_window)
    var _acc_hann_window: Float64 = 0.0
    var _t0_hann_window = perf_counter_ns()
    for _ in range(N):
        var _r_hann_window = hann_window(5)
        _acc_hann_window += Float64(len(_r_hann_window))
    var _t1_hann_window = perf_counter_ns()
    var _ns_hann_window = Float64(_t1_hann_window - _t0_hann_window) / Float64(N)
    print("MOJO_TIMING signal_processing::hann_window", _ns_hann_window, _acc_hann_window)
    var _result_hann_window = hann_window(5)
    var _summary_hann_window = _summary_list_float64(_result_hann_window)
    print("MOJO_RESULT signal_processing::hann_window", _summary_hann_window)
    var _acc_blackman_window: Float64 = 0.0
    var _t0_blackman_window = perf_counter_ns()
    for _ in range(N):
        var _r_blackman_window = blackman_window(5)
        _acc_blackman_window += Float64(len(_r_blackman_window))
    var _t1_blackman_window = perf_counter_ns()
    var _ns_blackman_window = Float64(_t1_blackman_window - _t0_blackman_window) / Float64(N)
    print("MOJO_TIMING signal_processing::blackman_window", _ns_blackman_window, _acc_blackman_window)
    var _result_blackman_window = blackman_window(5)
    var _summary_blackman_window = _summary_list_float64(_result_blackman_window)
    print("MOJO_RESULT signal_processing::blackman_window", _summary_blackman_window)
    var _acc_apply_window: Float64 = 0.0
    var _t0_apply_window = perf_counter_ns()
    for _ in range(N):
        var _r_apply_window = apply_window(_lf5, _lf5)
        _acc_apply_window += Float64(len(_r_apply_window))
    var _t1_apply_window = perf_counter_ns()
    var _ns_apply_window = Float64(_t1_apply_window - _t0_apply_window) / Float64(N)
    print("MOJO_TIMING signal_processing::apply_window", _ns_apply_window, _acc_apply_window)
    var _result_apply_window = apply_window(_lf5, _lf5)
    var _summary_apply_window = _summary_list_float64(_result_apply_window)
    print("MOJO_RESULT signal_processing::apply_window", _summary_apply_window)
    var _acc_peak_detect: Float64 = 0.0
    var _t0_peak_detect = perf_counter_ns()
    for _ in range(N):
        var _r_peak_detect = peak_detect(_lf5, 0.5)
        _acc_peak_detect += Float64(len(_r_peak_detect))
    var _t1_peak_detect = perf_counter_ns()
    var _ns_peak_detect = Float64(_t1_peak_detect - _t0_peak_detect) / Float64(N)
    print("MOJO_TIMING signal_processing::peak_detect", _ns_peak_detect, _acc_peak_detect)
    var _result_peak_detect = peak_detect(_lf5, 0.5)
    var _summary_peak_detect = _summary_list_int(_result_peak_detect)
    print("MOJO_RESULT signal_processing::peak_detect", _summary_peak_detect)
    var _acc_zero_crossings: Float64 = 0.0
    var _t0_zero_crossings = perf_counter_ns()
    for _ in range(N):
        var _r_zero_crossings = zero_crossings(_lf5)
        _acc_zero_crossings += Float64(len(_r_zero_crossings))
    var _t1_zero_crossings = perf_counter_ns()
    var _ns_zero_crossings = Float64(_t1_zero_crossings - _t0_zero_crossings) / Float64(N)
    print("MOJO_TIMING signal_processing::zero_crossings", _ns_zero_crossings, _acc_zero_crossings)
    var _result_zero_crossings = zero_crossings(_lf5)
    var _summary_zero_crossings = _summary_list_int(_result_zero_crossings)
    print("MOJO_RESULT signal_processing::zero_crossings", _summary_zero_crossings)
    var _acc_spectral_energy: Float64 = 0.0
    var _t0_spectral_energy = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_energy += spectral_energy(_lf5)
    var _t1_spectral_energy = perf_counter_ns()
    var _ns_spectral_energy = Float64(_t1_spectral_energy - _t0_spectral_energy) / Float64(N)
    print("MOJO_TIMING signal_processing::spectral_energy", _ns_spectral_energy, _acc_spectral_energy)
    var _result_spectral_energy = spectral_energy(_lf5)
    var _summary_spectral_energy = _summary_float64(_result_spectral_energy)
    print("MOJO_RESULT signal_processing::spectral_energy", _summary_spectral_energy)
    var _acc_spectral_centroid: Float64 = 0.0
    var _t0_spectral_centroid = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_centroid += spectral_centroid(_lf5, 0.5)
    var _t1_spectral_centroid = perf_counter_ns()
    var _ns_spectral_centroid = Float64(_t1_spectral_centroid - _t0_spectral_centroid) / Float64(N)
    print("MOJO_TIMING signal_processing::spectral_centroid", _ns_spectral_centroid, _acc_spectral_centroid)
    var _result_spectral_centroid = spectral_centroid(_lf5, 0.5)
    var _summary_spectral_centroid = _summary_float64(_result_spectral_centroid)
    print("MOJO_RESULT signal_processing::spectral_centroid", _summary_spectral_centroid)
    var _acc_spectral_flatness: Float64 = 0.0
    var _t0_spectral_flatness = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_flatness += spectral_flatness(_lf5)
    var _t1_spectral_flatness = perf_counter_ns()
    var _ns_spectral_flatness = Float64(_t1_spectral_flatness - _t0_spectral_flatness) / Float64(N)
    print("MOJO_TIMING signal_processing::spectral_flatness", _ns_spectral_flatness, _acc_spectral_flatness)
    var _result_spectral_flatness = spectral_flatness(_lf5)
    var _summary_spectral_flatness = _summary_float64(_result_spectral_flatness)
    print("MOJO_RESULT signal_processing::spectral_flatness", _summary_spectral_flatness)
    var _acc_signal_power: Float64 = 0.0
    var _t0_signal_power = perf_counter_ns()
    for _ in range(N):
        _acc_signal_power += signal_power(_lf5)
    var _t1_signal_power = perf_counter_ns()
    var _ns_signal_power = Float64(_t1_signal_power - _t0_signal_power) / Float64(N)
    print("MOJO_TIMING signal_processing::signal_power", _ns_signal_power, _acc_signal_power)
    var _result_signal_power = signal_power(_lf5)
    var _summary_signal_power = _summary_float64(_result_signal_power)
    print("MOJO_RESULT signal_processing::signal_power", _summary_signal_power)
