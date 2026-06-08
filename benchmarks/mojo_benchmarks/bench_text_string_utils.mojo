"""bench_text_string_utils.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from text.string_utils import str_split, str_join, str_replace, str_startswith, str_endswith, str_contains, str_repeat, str_pad_left, str_pad_right, str_upper, str_lower, str_trim, str_count, str_reverse, str_truncate, str_center
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

    var _acc_str_split: Float64 = 0.0
    var _t0_str_split = perf_counter_ns()
    for _ in range(N):
        var _r_str_split = str_split("test", "test")
        _acc_str_split += Float64(len(_r_str_split))
    var _t1_str_split = perf_counter_ns()
    var _ns_str_split = Float64(_t1_str_split - _t0_str_split) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_split", _ns_str_split, _acc_str_split)
    var _result_str_split = str_split("test", "test")
    var _summary_str_split = _summary_list_string(_result_str_split)
    print("MOJO_RESULT text_string_utils::str_split", _summary_str_split)
    var _acc_str_join: Float64 = 0.0
    var _t0_str_join = perf_counter_ns()
    for _ in range(N):
        _ = str_join(["a","b","c","d","e"], "test")
    var _t1_str_join = perf_counter_ns()
    var _ns_str_join = Float64(_t1_str_join - _t0_str_join) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_join", _ns_str_join, _acc_str_join)
    var _result_str_join = str_join(["a","b","c","d","e"], "test")
    var _summary_str_join = _summary_string(_result_str_join)
    print("MOJO_RESULT text_string_utils::str_join", _summary_str_join)
    var _acc_str_replace: Float64 = 0.0
    var _t0_str_replace = perf_counter_ns()
    for _ in range(N):
        _ = str_replace("test", "test", "test")
    var _t1_str_replace = perf_counter_ns()
    var _ns_str_replace = Float64(_t1_str_replace - _t0_str_replace) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_replace", _ns_str_replace, _acc_str_replace)
    var _result_str_replace = str_replace("test", "test", "test")
    var _summary_str_replace = _summary_string(_result_str_replace)
    print("MOJO_RESULT text_string_utils::str_replace", _summary_str_replace)
    var _acc_str_startswith: Float64 = 0.0
    var _t0_str_startswith = perf_counter_ns()
    for _ in range(N):
        _acc_str_startswith += Float64(str_startswith("test", "test"))
    var _t1_str_startswith = perf_counter_ns()
    var _ns_str_startswith = Float64(_t1_str_startswith - _t0_str_startswith) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_startswith", _ns_str_startswith, _acc_str_startswith)
    var _result_str_startswith = str_startswith("test", "test")
    var _summary_str_startswith = _summary_bool(_result_str_startswith)
    print("MOJO_RESULT text_string_utils::str_startswith", _summary_str_startswith)
    var _acc_str_endswith: Float64 = 0.0
    var _t0_str_endswith = perf_counter_ns()
    for _ in range(N):
        _acc_str_endswith += Float64(str_endswith("test", "test"))
    var _t1_str_endswith = perf_counter_ns()
    var _ns_str_endswith = Float64(_t1_str_endswith - _t0_str_endswith) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_endswith", _ns_str_endswith, _acc_str_endswith)
    var _result_str_endswith = str_endswith("test", "test")
    var _summary_str_endswith = _summary_bool(_result_str_endswith)
    print("MOJO_RESULT text_string_utils::str_endswith", _summary_str_endswith)
    var _acc_str_contains: Float64 = 0.0
    var _t0_str_contains = perf_counter_ns()
    for _ in range(N):
        _acc_str_contains += Float64(str_contains("test", "test"))
    var _t1_str_contains = perf_counter_ns()
    var _ns_str_contains = Float64(_t1_str_contains - _t0_str_contains) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_contains", _ns_str_contains, _acc_str_contains)
    var _result_str_contains = str_contains("test", "test")
    var _summary_str_contains = _summary_bool(_result_str_contains)
    print("MOJO_RESULT text_string_utils::str_contains", _summary_str_contains)
    var _acc_str_repeat: Float64 = 0.0
    var _t0_str_repeat = perf_counter_ns()
    for _ in range(N):
        _ = str_repeat("test", 5)
    var _t1_str_repeat = perf_counter_ns()
    var _ns_str_repeat = Float64(_t1_str_repeat - _t0_str_repeat) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_repeat", _ns_str_repeat, _acc_str_repeat)
    var _result_str_repeat = str_repeat("test", 5)
    var _summary_str_repeat = _summary_string(_result_str_repeat)
    print("MOJO_RESULT text_string_utils::str_repeat", _summary_str_repeat)
    var _acc_str_pad_left: Float64 = 0.0
    var _t0_str_pad_left = perf_counter_ns()
    for _ in range(N):
        _ = str_pad_left("test", 5, "test")
    var _t1_str_pad_left = perf_counter_ns()
    var _ns_str_pad_left = Float64(_t1_str_pad_left - _t0_str_pad_left) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_pad_left", _ns_str_pad_left, _acc_str_pad_left)
    var _result_str_pad_left = str_pad_left("test", 5, "test")
    var _summary_str_pad_left = _summary_string(_result_str_pad_left)
    print("MOJO_RESULT text_string_utils::str_pad_left", _summary_str_pad_left)
    var _acc_str_pad_right: Float64 = 0.0
    var _t0_str_pad_right = perf_counter_ns()
    for _ in range(N):
        _ = str_pad_right("test", 5, "test")
    var _t1_str_pad_right = perf_counter_ns()
    var _ns_str_pad_right = Float64(_t1_str_pad_right - _t0_str_pad_right) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_pad_right", _ns_str_pad_right, _acc_str_pad_right)
    var _result_str_pad_right = str_pad_right("test", 5, "test")
    var _summary_str_pad_right = _summary_string(_result_str_pad_right)
    print("MOJO_RESULT text_string_utils::str_pad_right", _summary_str_pad_right)
    var _acc_str_upper: Float64 = 0.0
    var _t0_str_upper = perf_counter_ns()
    for _ in range(N):
        _ = str_upper("test")
    var _t1_str_upper = perf_counter_ns()
    var _ns_str_upper = Float64(_t1_str_upper - _t0_str_upper) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_upper", _ns_str_upper, _acc_str_upper)
    var _result_str_upper = str_upper("test")
    var _summary_str_upper = _summary_string(_result_str_upper)
    print("MOJO_RESULT text_string_utils::str_upper", _summary_str_upper)
    var _acc_str_lower: Float64 = 0.0
    var _t0_str_lower = perf_counter_ns()
    for _ in range(N):
        _ = str_lower("test")
    var _t1_str_lower = perf_counter_ns()
    var _ns_str_lower = Float64(_t1_str_lower - _t0_str_lower) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_lower", _ns_str_lower, _acc_str_lower)
    var _result_str_lower = str_lower("test")
    var _summary_str_lower = _summary_string(_result_str_lower)
    print("MOJO_RESULT text_string_utils::str_lower", _summary_str_lower)
    var _acc_str_trim: Float64 = 0.0
    var _t0_str_trim = perf_counter_ns()
    for _ in range(N):
        _ = str_trim("test")
    var _t1_str_trim = perf_counter_ns()
    var _ns_str_trim = Float64(_t1_str_trim - _t0_str_trim) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_trim", _ns_str_trim, _acc_str_trim)
    var _result_str_trim = str_trim("test")
    var _summary_str_trim = _summary_string(_result_str_trim)
    print("MOJO_RESULT text_string_utils::str_trim", _summary_str_trim)
    var _acc_str_count: Float64 = 0.0
    var _t0_str_count = perf_counter_ns()
    for _ in range(N):
        _acc_str_count += Float64(str_count("test", "test"))
    var _t1_str_count = perf_counter_ns()
    var _ns_str_count = Float64(_t1_str_count - _t0_str_count) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_count", _ns_str_count, _acc_str_count)
    var _result_str_count = str_count("test", "test")
    var _summary_str_count = _summary_int(_result_str_count)
    print("MOJO_RESULT text_string_utils::str_count", _summary_str_count)
    var _acc_str_reverse: Float64 = 0.0
    var _t0_str_reverse = perf_counter_ns()
    for _ in range(N):
        _ = str_reverse("test")
    var _t1_str_reverse = perf_counter_ns()
    var _ns_str_reverse = Float64(_t1_str_reverse - _t0_str_reverse) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_reverse", _ns_str_reverse, _acc_str_reverse)
    var _result_str_reverse = str_reverse("test")
    var _summary_str_reverse = _summary_string(_result_str_reverse)
    print("MOJO_RESULT text_string_utils::str_reverse", _summary_str_reverse)
    var _acc_str_truncate: Float64 = 0.0
    var _t0_str_truncate = perf_counter_ns()
    for _ in range(N):
        _ = str_truncate("test", 5, "test")
    var _t1_str_truncate = perf_counter_ns()
    var _ns_str_truncate = Float64(_t1_str_truncate - _t0_str_truncate) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_truncate", _ns_str_truncate, _acc_str_truncate)
    var _result_str_truncate = str_truncate("test", 5, "test")
    var _summary_str_truncate = _summary_string(_result_str_truncate)
    print("MOJO_RESULT text_string_utils::str_truncate", _summary_str_truncate)
    var _acc_str_center: Float64 = 0.0
    var _t0_str_center = perf_counter_ns()
    for _ in range(N):
        _ = str_center("test", 5, "test")
    var _t1_str_center = perf_counter_ns()
    var _ns_str_center = Float64(_t1_str_center - _t0_str_center) / Float64(N)
    print("MOJO_TIMING text_string_utils::str_center", _ns_str_center, _acc_str_center)
    var _result_str_center = str_center("test", 5, "test")
    var _summary_str_center = _summary_string(_result_str_center)
    print("MOJO_RESULT text_string_utils::str_center", _summary_str_center)
