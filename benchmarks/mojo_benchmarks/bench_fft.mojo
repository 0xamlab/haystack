"""bench_fft.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fft import next_power_of_2, zero_pad, fft, power_spectrum
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

    var _acc_next_power_of_2: Float64 = 0.0
    var _t0_next_power_of_2 = perf_counter_ns()
    for _ in range(N):
        _acc_next_power_of_2 += Float64(next_power_of_2(5))
    var _t1_next_power_of_2 = perf_counter_ns()
    var _ns_next_power_of_2 = Float64(_t1_next_power_of_2 - _t0_next_power_of_2) / Float64(N)
    print("MOJO_TIMING fft::next_power_of_2", _ns_next_power_of_2, _acc_next_power_of_2)
    var _result_next_power_of_2 = next_power_of_2(5)
    var _summary_next_power_of_2 = _summary_int(_result_next_power_of_2)
    print("MOJO_RESULT fft::next_power_of_2", _summary_next_power_of_2)
    var _acc_zero_pad: Float64 = 0.0
    var _t0_zero_pad = perf_counter_ns()
    for _ in range(N):
        var _r_zero_pad = zero_pad(_lf5, 5)
        _acc_zero_pad += Float64(len(_r_zero_pad))
    var _t1_zero_pad = perf_counter_ns()
    var _ns_zero_pad = Float64(_t1_zero_pad - _t0_zero_pad) / Float64(N)
    print("MOJO_TIMING fft::zero_pad", _ns_zero_pad, _acc_zero_pad)
    var _result_zero_pad = zero_pad(_lf5, 5)
    var _summary_zero_pad = _summary_list_float64(_result_zero_pad)
    print("MOJO_RESULT fft::zero_pad", _summary_zero_pad)
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
    var _result_power_spectrum = power_spectrum(_lf5)
    var _summary_power_spectrum = _summary_list_float64(_result_power_spectrum)
    print("MOJO_RESULT fft::power_spectrum", _summary_power_spectrum)
