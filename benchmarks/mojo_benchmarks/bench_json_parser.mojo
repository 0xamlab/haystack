"""bench_json_parser.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from json.parser import skip_whitespace, skip_json_value, find_key, json_get_string, json_get_float, json_get_int, json_get_bool, json_is_null, json_get_object, json_get_array, json_array_len, json_array_get
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

    var _acc_skip_whitespace: Float64 = 0.0
    var _t0_skip_whitespace = perf_counter_ns()
    for _ in range(N):
        _acc_skip_whitespace += Float64(skip_whitespace("test", 5))
    var _t1_skip_whitespace = perf_counter_ns()
    var _ns_skip_whitespace = Float64(_t1_skip_whitespace - _t0_skip_whitespace) / Float64(N)
    print("MOJO_TIMING json_parser::skip_whitespace", _ns_skip_whitespace, _acc_skip_whitespace)
    var _acc_skip_json_value: Float64 = 0.0
    var _t0_skip_json_value = perf_counter_ns()
    for _ in range(N):
        _acc_skip_json_value += Float64(skip_json_value("test", 5))
    var _t1_skip_json_value = perf_counter_ns()
    var _ns_skip_json_value = Float64(_t1_skip_json_value - _t0_skip_json_value) / Float64(N)
    print("MOJO_TIMING json_parser::skip_json_value", _ns_skip_json_value, _acc_skip_json_value)
    var _acc_find_key: Float64 = 0.0
    var _t0_find_key = perf_counter_ns()
    for _ in range(N):
        _acc_find_key += Float64(find_key("test", "test"))
    var _t1_find_key = perf_counter_ns()
    var _ns_find_key = Float64(_t1_find_key - _t0_find_key) / Float64(N)
    print("MOJO_TIMING json_parser::find_key", _ns_find_key, _acc_find_key)
    var _acc_json_get_string: Float64 = 0.0
    var _t0_json_get_string = perf_counter_ns()
    for _ in range(N):
        _ = json_get_string("test", "test")
    var _t1_json_get_string = perf_counter_ns()
    var _ns_json_get_string = Float64(_t1_json_get_string - _t0_json_get_string) / Float64(N)
    print("MOJO_TIMING json_parser::json_get_string", _ns_json_get_string, _acc_json_get_string)
    var _acc_json_get_float: Float64 = 0.0
    var _t0_json_get_float = perf_counter_ns()
    for _ in range(N):
        _acc_json_get_float += json_get_float("test", "test", 0.5)
    var _t1_json_get_float = perf_counter_ns()
    var _ns_json_get_float = Float64(_t1_json_get_float - _t0_json_get_float) / Float64(N)
    print("MOJO_TIMING json_parser::json_get_float", _ns_json_get_float, _acc_json_get_float)
    var _acc_json_get_int: Float64 = 0.0
    var _t0_json_get_int = perf_counter_ns()
    for _ in range(N):
        _acc_json_get_int += Float64(json_get_int("test", "test", 5))
    var _t1_json_get_int = perf_counter_ns()
    var _ns_json_get_int = Float64(_t1_json_get_int - _t0_json_get_int) / Float64(N)
    print("MOJO_TIMING json_parser::json_get_int", _ns_json_get_int, _acc_json_get_int)
    var _acc_json_get_bool: Float64 = 0.0
    var _t0_json_get_bool = perf_counter_ns()
    for _ in range(N):
        _acc_json_get_bool += Float64(json_get_bool("test", "test", True))
    var _t1_json_get_bool = perf_counter_ns()
    var _ns_json_get_bool = Float64(_t1_json_get_bool - _t0_json_get_bool) / Float64(N)
    print("MOJO_TIMING json_parser::json_get_bool", _ns_json_get_bool, _acc_json_get_bool)
    var _acc_json_is_null: Float64 = 0.0
    var _t0_json_is_null = perf_counter_ns()
    for _ in range(N):
        _acc_json_is_null += Float64(json_is_null("test", "test"))
    var _t1_json_is_null = perf_counter_ns()
    var _ns_json_is_null = Float64(_t1_json_is_null - _t0_json_is_null) / Float64(N)
    print("MOJO_TIMING json_parser::json_is_null", _ns_json_is_null, _acc_json_is_null)
    var _acc_json_get_object: Float64 = 0.0
    var _t0_json_get_object = perf_counter_ns()
    for _ in range(N):
        _ = json_get_object("test", "test")
    var _t1_json_get_object = perf_counter_ns()
    var _ns_json_get_object = Float64(_t1_json_get_object - _t0_json_get_object) / Float64(N)
    print("MOJO_TIMING json_parser::json_get_object", _ns_json_get_object, _acc_json_get_object)
    var _acc_json_get_array: Float64 = 0.0
    var _t0_json_get_array = perf_counter_ns()
    for _ in range(N):
        _ = json_get_array("test", "test")
    var _t1_json_get_array = perf_counter_ns()
    var _ns_json_get_array = Float64(_t1_json_get_array - _t0_json_get_array) / Float64(N)
    print("MOJO_TIMING json_parser::json_get_array", _ns_json_get_array, _acc_json_get_array)
    var _acc_json_array_len: Float64 = 0.0
    var _t0_json_array_len = perf_counter_ns()
    for _ in range(N):
        _acc_json_array_len += Float64(json_array_len("test"))
    var _t1_json_array_len = perf_counter_ns()
    var _ns_json_array_len = Float64(_t1_json_array_len - _t0_json_array_len) / Float64(N)
    print("MOJO_TIMING json_parser::json_array_len", _ns_json_array_len, _acc_json_array_len)
    var _acc_json_array_get: Float64 = 0.0
    var _t0_json_array_get = perf_counter_ns()
    for _ in range(N):
        _ = json_array_get("test", 5)
    var _t1_json_array_get = perf_counter_ns()
    var _ns_json_array_get = Float64(_t1_json_array_get - _t0_json_array_get) / Float64(N)
    print("MOJO_TIMING json_parser::json_array_get", _ns_json_array_get, _acc_json_array_get)
