"""bench_compression_huffman.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from compression.huffman import frequency_count, build_huffman_tree, huffman_encode, compression_ratio_huffman, avg_code_length
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_frequency_count: Float64 = 0.0
    var _t0_frequency_count = perf_counter_ns()
    for _ in range(N):
        var _r_frequency_count = frequency_count(_li5)
        _acc_frequency_count += Float64(len(_r_frequency_count))
    var _t1_frequency_count = perf_counter_ns()
    var _ns_frequency_count = Float64(_t1_frequency_count - _t0_frequency_count) / Float64(N)
    print("MOJO_TIMING compression_huffman::frequency_count", _ns_frequency_count, _acc_frequency_count)
    var _result_frequency_count = frequency_count(_li5)
    var _summary_frequency_count = _summary_list_list_int(_result_frequency_count)
    print("MOJO_RESULT compression_huffman::frequency_count", _summary_frequency_count)
    var _acc_build_huffman_tree: Float64 = 0.0
    var _t0_build_huffman_tree = perf_counter_ns()
    for _ in range(N):
        var _r_build_huffman_tree = build_huffman_tree([[0,1,1],[1,0,1],[1,1,0]])
        _acc_build_huffman_tree += Float64(len(_r_build_huffman_tree))
    var _t1_build_huffman_tree = perf_counter_ns()
    var _ns_build_huffman_tree = Float64(_t1_build_huffman_tree - _t0_build_huffman_tree) / Float64(N)
    print("MOJO_TIMING compression_huffman::build_huffman_tree", _ns_build_huffman_tree, _acc_build_huffman_tree)
    var _acc_huffman_encode: Float64 = 0.0
    var _t0_huffman_encode = perf_counter_ns()
    for _ in range(N):
        var _r_huffman_encode = huffman_encode(_li5)
        _acc_huffman_encode += Float64(len(_r_huffman_encode))
    var _t1_huffman_encode = perf_counter_ns()
    var _ns_huffman_encode = Float64(_t1_huffman_encode - _t0_huffman_encode) / Float64(N)
    print("MOJO_TIMING compression_huffman::huffman_encode", _ns_huffman_encode, _acc_huffman_encode)
    var _result_huffman_encode = huffman_encode(_li5)
    var _summary_huffman_encode = _summary_list_int(_result_huffman_encode)
    print("MOJO_RESULT compression_huffman::huffman_encode", _summary_huffman_encode)
    var _acc_compression_ratio_huffman: Float64 = 0.0
    var _t0_compression_ratio_huffman = perf_counter_ns()
    for _ in range(N):
        _acc_compression_ratio_huffman += compression_ratio_huffman(5, 5)
    var _t1_compression_ratio_huffman = perf_counter_ns()
    var _ns_compression_ratio_huffman = Float64(_t1_compression_ratio_huffman - _t0_compression_ratio_huffman) / Float64(N)
    print("MOJO_TIMING compression_huffman::compression_ratio_huffman", _ns_compression_ratio_huffman, _acc_compression_ratio_huffman)
    var _result_compression_ratio_huffman = compression_ratio_huffman(5, 5)
    var _summary_compression_ratio_huffman = _summary_float64(_result_compression_ratio_huffman)
    print("MOJO_RESULT compression_huffman::compression_ratio_huffman", _summary_compression_ratio_huffman)
    var _acc_avg_code_length: Float64 = 0.0
    var _t0_avg_code_length = perf_counter_ns()
    for _ in range(N):
        _acc_avg_code_length += avg_code_length([[0,1,1],[1,0,1],[1,1,0]], [[0,1,1],[1,0,1],[1,1,0]])
    var _t1_avg_code_length = perf_counter_ns()
    var _ns_avg_code_length = Float64(_t1_avg_code_length - _t0_avg_code_length) / Float64(N)
    print("MOJO_TIMING compression_huffman::avg_code_length", _ns_avg_code_length, _acc_avg_code_length)
    var _result_avg_code_length = avg_code_length([[0,1,1],[1,0,1],[1,1,0]], [[0,1,1],[1,0,1],[1,1,0]])
    var _summary_avg_code_length = _summary_float64(_result_avg_code_length)
    print("MOJO_RESULT compression_huffman::avg_code_length", _summary_avg_code_length)
