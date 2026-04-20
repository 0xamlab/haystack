"""bench_json_writer.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from json.writer import json_escape_string, json_object_start, json_object_end, json_add_string, json_add_int, json_add_float, json_add_bool, json_add_null, json_add_array_float, json_add_array_string, json_add_raw
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

    var _acc_json_escape_string: Float64 = 0.0
    var _t0_json_escape_string = perf_counter_ns()
    for _ in range(N):
        _ = json_escape_string("test")
    var _t1_json_escape_string = perf_counter_ns()
    var _ns_json_escape_string = Float64(_t1_json_escape_string - _t0_json_escape_string) / Float64(N)
    print("MOJO_TIMING json_writer::json_escape_string", _ns_json_escape_string, _acc_json_escape_string)
    var _acc_json_object_start: Float64 = 0.0
    var _t0_json_object_start = perf_counter_ns()
    for _ in range(N):
        _ = json_object_start()
    var _t1_json_object_start = perf_counter_ns()
    var _ns_json_object_start = Float64(_t1_json_object_start - _t0_json_object_start) / Float64(N)
    print("MOJO_TIMING json_writer::json_object_start", _ns_json_object_start, _acc_json_object_start)
    var _acc_json_object_end: Float64 = 0.0
    var _t0_json_object_end = perf_counter_ns()
    for _ in range(N):
        _ = json_object_end("test")
    var _t1_json_object_end = perf_counter_ns()
    var _ns_json_object_end = Float64(_t1_json_object_end - _t0_json_object_end) / Float64(N)
    print("MOJO_TIMING json_writer::json_object_end", _ns_json_object_end, _acc_json_object_end)
    var _acc_json_add_string: Float64 = 0.0
    var _t0_json_add_string = perf_counter_ns()
    for _ in range(N):
        _ = json_add_string("test", "test", "test")
    var _t1_json_add_string = perf_counter_ns()
    var _ns_json_add_string = Float64(_t1_json_add_string - _t0_json_add_string) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_string", _ns_json_add_string, _acc_json_add_string)
    var _acc_json_add_int: Float64 = 0.0
    var _t0_json_add_int = perf_counter_ns()
    for _ in range(N):
        _ = json_add_int("test", "test", 5)
    var _t1_json_add_int = perf_counter_ns()
    var _ns_json_add_int = Float64(_t1_json_add_int - _t0_json_add_int) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_int", _ns_json_add_int, _acc_json_add_int)
    var _acc_json_add_float: Float64 = 0.0
    var _t0_json_add_float = perf_counter_ns()
    for _ in range(N):
        _ = json_add_float("test", "test", 0.5)
    var _t1_json_add_float = perf_counter_ns()
    var _ns_json_add_float = Float64(_t1_json_add_float - _t0_json_add_float) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_float", _ns_json_add_float, _acc_json_add_float)
    var _acc_json_add_bool: Float64 = 0.0
    var _t0_json_add_bool = perf_counter_ns()
    for _ in range(N):
        _ = json_add_bool("test", "test", True)
    var _t1_json_add_bool = perf_counter_ns()
    var _ns_json_add_bool = Float64(_t1_json_add_bool - _t0_json_add_bool) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_bool", _ns_json_add_bool, _acc_json_add_bool)
    var _acc_json_add_null: Float64 = 0.0
    var _t0_json_add_null = perf_counter_ns()
    for _ in range(N):
        _ = json_add_null("test", "test")
    var _t1_json_add_null = perf_counter_ns()
    var _ns_json_add_null = Float64(_t1_json_add_null - _t0_json_add_null) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_null", _ns_json_add_null, _acc_json_add_null)
    var _acc_json_add_array_float: Float64 = 0.0
    var _t0_json_add_array_float = perf_counter_ns()
    for _ in range(N):
        _ = json_add_array_float("test", "test", _lf5)
    var _t1_json_add_array_float = perf_counter_ns()
    var _ns_json_add_array_float = Float64(_t1_json_add_array_float - _t0_json_add_array_float) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_array_float", _ns_json_add_array_float, _acc_json_add_array_float)
    var _acc_json_add_array_string: Float64 = 0.0
    var _t0_json_add_array_string = perf_counter_ns()
    for _ in range(N):
        _ = json_add_array_string("test", "test", ["a","b","c","d","e"])
    var _t1_json_add_array_string = perf_counter_ns()
    var _ns_json_add_array_string = Float64(_t1_json_add_array_string - _t0_json_add_array_string) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_array_string", _ns_json_add_array_string, _acc_json_add_array_string)
    var _acc_json_add_raw: Float64 = 0.0
    var _t0_json_add_raw = perf_counter_ns()
    for _ in range(N):
        _ = json_add_raw("test", "test", "test")
    var _t1_json_add_raw = perf_counter_ns()
    var _ns_json_add_raw = Float64(_t1_json_add_raw - _t0_json_add_raw) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_raw", _ns_json_add_raw, _acc_json_add_raw)
