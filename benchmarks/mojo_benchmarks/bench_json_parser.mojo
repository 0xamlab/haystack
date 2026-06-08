"""bench_json_parser.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from json.parser import skip_whitespace, skip_json_value, find_key, json_get_string, json_get_float, json_get_int, json_get_bool, json_is_null, json_get_object, json_get_array, json_array_len, json_array_get
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

    var _acc_skip_whitespace: Float64 = 0.0
    var _t0_skip_whitespace = perf_counter_ns()
    for _ in range(N):
        _acc_skip_whitespace += Float64(skip_whitespace("test", 5))
    var _t1_skip_whitespace = perf_counter_ns()
    var _ns_skip_whitespace = Float64(_t1_skip_whitespace - _t0_skip_whitespace) / Float64(N)
    print("MOJO_TIMING json_parser::skip_whitespace", _ns_skip_whitespace, _acc_skip_whitespace)
    var _result_skip_whitespace = skip_whitespace("test", 5)
    var _summary_skip_whitespace = _summary_int(_result_skip_whitespace)
    print("MOJO_RESULT json_parser::skip_whitespace", _summary_skip_whitespace)
    var _acc_skip_json_value: Float64 = 0.0
    var _t0_skip_json_value = perf_counter_ns()
    for _ in range(N):
        _acc_skip_json_value += Float64(skip_json_value("test", 5))
    var _t1_skip_json_value = perf_counter_ns()
    var _ns_skip_json_value = Float64(_t1_skip_json_value - _t0_skip_json_value) / Float64(N)
    print("MOJO_TIMING json_parser::skip_json_value", _ns_skip_json_value, _acc_skip_json_value)
    var _result_skip_json_value = skip_json_value("test", 5)
    var _summary_skip_json_value = _summary_int(_result_skip_json_value)
    print("MOJO_RESULT json_parser::skip_json_value", _summary_skip_json_value)
    var _acc_find_key: Float64 = 0.0
    var _t0_find_key = perf_counter_ns()
    for _ in range(N):
        _acc_find_key += Float64(find_key("test", "test"))
    var _t1_find_key = perf_counter_ns()
    var _ns_find_key = Float64(_t1_find_key - _t0_find_key) / Float64(N)
    print("MOJO_TIMING json_parser::find_key", _ns_find_key, _acc_find_key)
    var _result_find_key = find_key("test", "test")
    var _summary_find_key = _summary_int(_result_find_key)
    print("MOJO_RESULT json_parser::find_key", _summary_find_key)
    var _acc_json_get_string: Float64 = 0.0
    var _t0_json_get_string = perf_counter_ns()
    for _ in range(N):
        _ = json_get_string("test", "test")
    var _t1_json_get_string = perf_counter_ns()
    var _ns_json_get_string = Float64(_t1_json_get_string - _t0_json_get_string) / Float64(N)
    print("MOJO_TIMING json_parser::json_get_string", _ns_json_get_string, _acc_json_get_string)
    var _result_json_get_string = json_get_string("test", "test")
    var _summary_json_get_string = _summary_string(_result_json_get_string)
    print("MOJO_RESULT json_parser::json_get_string", _summary_json_get_string)
    var _acc_json_get_float: Float64 = 0.0
    var _t0_json_get_float = perf_counter_ns()
    for _ in range(N):
        _acc_json_get_float += json_get_float("test", "test", 0.5)
    var _t1_json_get_float = perf_counter_ns()
    var _ns_json_get_float = Float64(_t1_json_get_float - _t0_json_get_float) / Float64(N)
    print("MOJO_TIMING json_parser::json_get_float", _ns_json_get_float, _acc_json_get_float)
    var _result_json_get_float = json_get_float("test", "test", 0.5)
    var _summary_json_get_float = _summary_float64(_result_json_get_float)
    print("MOJO_RESULT json_parser::json_get_float", _summary_json_get_float)
    var _acc_json_get_int: Float64 = 0.0
    var _t0_json_get_int = perf_counter_ns()
    for _ in range(N):
        _acc_json_get_int += Float64(json_get_int("test", "test", 5))
    var _t1_json_get_int = perf_counter_ns()
    var _ns_json_get_int = Float64(_t1_json_get_int - _t0_json_get_int) / Float64(N)
    print("MOJO_TIMING json_parser::json_get_int", _ns_json_get_int, _acc_json_get_int)
    var _result_json_get_int = json_get_int("test", "test", 5)
    var _summary_json_get_int = _summary_int(_result_json_get_int)
    print("MOJO_RESULT json_parser::json_get_int", _summary_json_get_int)
    var _acc_json_get_bool: Float64 = 0.0
    var _t0_json_get_bool = perf_counter_ns()
    for _ in range(N):
        _acc_json_get_bool += Float64(json_get_bool("test", "test", True))
    var _t1_json_get_bool = perf_counter_ns()
    var _ns_json_get_bool = Float64(_t1_json_get_bool - _t0_json_get_bool) / Float64(N)
    print("MOJO_TIMING json_parser::json_get_bool", _ns_json_get_bool, _acc_json_get_bool)
    var _result_json_get_bool = json_get_bool("test", "test", True)
    var _summary_json_get_bool = _summary_bool(_result_json_get_bool)
    print("MOJO_RESULT json_parser::json_get_bool", _summary_json_get_bool)
    var _acc_json_is_null: Float64 = 0.0
    var _t0_json_is_null = perf_counter_ns()
    for _ in range(N):
        _acc_json_is_null += Float64(json_is_null("test", "test"))
    var _t1_json_is_null = perf_counter_ns()
    var _ns_json_is_null = Float64(_t1_json_is_null - _t0_json_is_null) / Float64(N)
    print("MOJO_TIMING json_parser::json_is_null", _ns_json_is_null, _acc_json_is_null)
    var _result_json_is_null = json_is_null("test", "test")
    var _summary_json_is_null = _summary_bool(_result_json_is_null)
    print("MOJO_RESULT json_parser::json_is_null", _summary_json_is_null)
    var _acc_json_get_object: Float64 = 0.0
    var _t0_json_get_object = perf_counter_ns()
    for _ in range(N):
        _ = json_get_object("test", "test")
    var _t1_json_get_object = perf_counter_ns()
    var _ns_json_get_object = Float64(_t1_json_get_object - _t0_json_get_object) / Float64(N)
    print("MOJO_TIMING json_parser::json_get_object", _ns_json_get_object, _acc_json_get_object)
    var _result_json_get_object = json_get_object("test", "test")
    var _summary_json_get_object = _summary_string(_result_json_get_object)
    print("MOJO_RESULT json_parser::json_get_object", _summary_json_get_object)
    var _acc_json_get_array: Float64 = 0.0
    var _t0_json_get_array = perf_counter_ns()
    for _ in range(N):
        _ = json_get_array("test", "test")
    var _t1_json_get_array = perf_counter_ns()
    var _ns_json_get_array = Float64(_t1_json_get_array - _t0_json_get_array) / Float64(N)
    print("MOJO_TIMING json_parser::json_get_array", _ns_json_get_array, _acc_json_get_array)
    var _result_json_get_array = json_get_array("test", "test")
    var _summary_json_get_array = _summary_string(_result_json_get_array)
    print("MOJO_RESULT json_parser::json_get_array", _summary_json_get_array)
    var _acc_json_array_len: Float64 = 0.0
    var _t0_json_array_len = perf_counter_ns()
    for _ in range(N):
        _acc_json_array_len += Float64(json_array_len("test"))
    var _t1_json_array_len = perf_counter_ns()
    var _ns_json_array_len = Float64(_t1_json_array_len - _t0_json_array_len) / Float64(N)
    print("MOJO_TIMING json_parser::json_array_len", _ns_json_array_len, _acc_json_array_len)
    var _result_json_array_len = json_array_len("test")
    var _summary_json_array_len = _summary_int(_result_json_array_len)
    print("MOJO_RESULT json_parser::json_array_len", _summary_json_array_len)
    var _acc_json_array_get: Float64 = 0.0
    var _t0_json_array_get = perf_counter_ns()
    for _ in range(N):
        _ = json_array_get("test", 5)
    var _t1_json_array_get = perf_counter_ns()
    var _ns_json_array_get = Float64(_t1_json_array_get - _t0_json_array_get) / Float64(N)
    print("MOJO_TIMING json_parser::json_array_get", _ns_json_array_get, _acc_json_array_get)
    var _result_json_array_get = json_array_get("test", 5)
    var _summary_json_array_get = _summary_string(_result_json_array_get)
    print("MOJO_RESULT json_parser::json_array_get", _summary_json_array_get)
