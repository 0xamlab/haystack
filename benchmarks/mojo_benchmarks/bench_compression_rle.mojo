"""bench_compression_rle.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from compression.rle import rle_encode, rle_decode, rle_encode_string, rle_decode_string, compression_ratio
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

    var _acc_rle_encode: Float64 = 0.0
    var _t0_rle_encode = perf_counter_ns()
    for _ in range(N):
        var _r_rle_encode = rle_encode(_lub5)
        _acc_rle_encode += Float64(len(_r_rle_encode))
    var _t1_rle_encode = perf_counter_ns()
    var _ns_rle_encode = Float64(_t1_rle_encode - _t0_rle_encode) / Float64(N)
    print("MOJO_TIMING compression_rle::rle_encode", _ns_rle_encode, _acc_rle_encode)
    var _acc_rle_decode: Float64 = 0.0
    var _t0_rle_decode = perf_counter_ns()
    for _ in range(N):
        var _r_rle_decode = rle_decode(_lub5)
        _acc_rle_decode += Float64(len(_r_rle_decode))
    var _t1_rle_decode = perf_counter_ns()
    var _ns_rle_decode = Float64(_t1_rle_decode - _t0_rle_decode) / Float64(N)
    print("MOJO_TIMING compression_rle::rle_decode", _ns_rle_decode, _acc_rle_decode)
    var _acc_rle_encode_string: Float64 = 0.0
    var _t0_rle_encode_string = perf_counter_ns()
    for _ in range(N):
        _ = rle_encode_string("test")
    var _t1_rle_encode_string = perf_counter_ns()
    var _ns_rle_encode_string = Float64(_t1_rle_encode_string - _t0_rle_encode_string) / Float64(N)
    print("MOJO_TIMING compression_rle::rle_encode_string", _ns_rle_encode_string, _acc_rle_encode_string)
    var _result_rle_encode_string = rle_encode_string("test")
    var _summary_rle_encode_string = _summary_string(_result_rle_encode_string)
    print("MOJO_RESULT compression_rle::rle_encode_string", _summary_rle_encode_string)
    var _acc_rle_decode_string: Float64 = 0.0
    var _t0_rle_decode_string = perf_counter_ns()
    for _ in range(N):
        _ = rle_decode_string("test")
    var _t1_rle_decode_string = perf_counter_ns()
    var _ns_rle_decode_string = Float64(_t1_rle_decode_string - _t0_rle_decode_string) / Float64(N)
    print("MOJO_TIMING compression_rle::rle_decode_string", _ns_rle_decode_string, _acc_rle_decode_string)
    var _result_rle_decode_string = rle_decode_string("test")
    var _summary_rle_decode_string = _summary_string(_result_rle_decode_string)
    print("MOJO_RESULT compression_rle::rle_decode_string", _summary_rle_decode_string)
    var _acc_compression_ratio: Float64 = 0.0
    var _t0_compression_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_compression_ratio += compression_ratio(5, 5)
    var _t1_compression_ratio = perf_counter_ns()
    var _ns_compression_ratio = Float64(_t1_compression_ratio - _t0_compression_ratio) / Float64(N)
    print("MOJO_TIMING compression_rle::compression_ratio", _ns_compression_ratio, _acc_compression_ratio)
    var _result_compression_ratio = compression_ratio(5, 5)
    var _summary_compression_ratio = _summary_float64(_result_compression_ratio)
    print("MOJO_RESULT compression_rle::compression_ratio", _summary_compression_ratio)
