"""bench_compression_lz77.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from compression.lz77 import bytes_to_ints, ints_to_string, find_longest_match, lz77_encode, compression_ratio
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

    var _acc_bytes_to_ints: Float64 = 0.0
    var _t0_bytes_to_ints = perf_counter_ns()
    for _ in range(N):
        var _r_bytes_to_ints = bytes_to_ints("test")
        _acc_bytes_to_ints += Float64(len(_r_bytes_to_ints))
    var _t1_bytes_to_ints = perf_counter_ns()
    var _ns_bytes_to_ints = Float64(_t1_bytes_to_ints - _t0_bytes_to_ints) / Float64(N)
    print("MOJO_TIMING compression_lz77::bytes_to_ints", _ns_bytes_to_ints, _acc_bytes_to_ints)
    var _result_bytes_to_ints = bytes_to_ints("test")
    var _summary_bytes_to_ints = _summary_list_int(_result_bytes_to_ints)
    print("MOJO_RESULT compression_lz77::bytes_to_ints", _summary_bytes_to_ints)
    var _acc_ints_to_string: Float64 = 0.0
    var _t0_ints_to_string = perf_counter_ns()
    for _ in range(N):
        _ = ints_to_string(_li5)
    var _t1_ints_to_string = perf_counter_ns()
    var _ns_ints_to_string = Float64(_t1_ints_to_string - _t0_ints_to_string) / Float64(N)
    print("MOJO_TIMING compression_lz77::ints_to_string", _ns_ints_to_string, _acc_ints_to_string)
    var _result_ints_to_string = ints_to_string(_li5)
    var _summary_ints_to_string = _summary_string(_result_ints_to_string)
    print("MOJO_RESULT compression_lz77::ints_to_string", _summary_ints_to_string)
    var _acc_find_longest_match: Float64 = 0.0
    var _t0_find_longest_match = perf_counter_ns()
    for _ in range(N):
        var _r_find_longest_match = find_longest_match(_li5, 5, 5, 5)
        _acc_find_longest_match += Float64(len(_r_find_longest_match))
    var _t1_find_longest_match = perf_counter_ns()
    var _ns_find_longest_match = Float64(_t1_find_longest_match - _t0_find_longest_match) / Float64(N)
    print("MOJO_TIMING compression_lz77::find_longest_match", _ns_find_longest_match, _acc_find_longest_match)
    var _result_find_longest_match = find_longest_match(_li5, 5, 5, 5)
    var _summary_find_longest_match = _summary_list_int(_result_find_longest_match)
    print("MOJO_RESULT compression_lz77::find_longest_match", _summary_find_longest_match)
    var _acc_lz77_encode: Float64 = 0.0
    var _t0_lz77_encode = perf_counter_ns()
    for _ in range(N):
        var _r_lz77_encode = lz77_encode(_li5, 5, 5)
        _acc_lz77_encode += Float64(len(_r_lz77_encode))
    var _t1_lz77_encode = perf_counter_ns()
    var _ns_lz77_encode = Float64(_t1_lz77_encode - _t0_lz77_encode) / Float64(N)
    print("MOJO_TIMING compression_lz77::lz77_encode", _ns_lz77_encode, _acc_lz77_encode)
    var _acc_compression_ratio: Float64 = 0.0
    var _t0_compression_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_compression_ratio += compression_ratio(5, 5)
    var _t1_compression_ratio = perf_counter_ns()
    var _ns_compression_ratio = Float64(_t1_compression_ratio - _t0_compression_ratio) / Float64(N)
    print("MOJO_TIMING compression_lz77::compression_ratio", _ns_compression_ratio, _acc_compression_ratio)
    var _result_compression_ratio = compression_ratio(5, 5)
    var _summary_compression_ratio = _summary_float64(_result_compression_ratio)
    print("MOJO_RESULT compression_lz77::compression_ratio", _summary_compression_ratio)
