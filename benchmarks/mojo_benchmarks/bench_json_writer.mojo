"""bench_json_writer.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from json.writer import json_escape_string, json_object_start, json_object_end, json_add_string, json_add_int, json_add_float, json_add_bool, json_add_null, json_add_array_float, json_add_array_string, json_add_raw
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

    var _acc_json_escape_string: Float64 = 0.0
    var _t0_json_escape_string = perf_counter_ns()
    for _ in range(N):
        _ = json_escape_string("test")
    var _t1_json_escape_string = perf_counter_ns()
    var _ns_json_escape_string = Float64(_t1_json_escape_string - _t0_json_escape_string) / Float64(N)
    print("MOJO_TIMING json_writer::json_escape_string", _ns_json_escape_string, _acc_json_escape_string)
    var _result_json_escape_string = json_escape_string("test")
    var _summary_json_escape_string = _summary_string(_result_json_escape_string)
    print("MOJO_RESULT json_writer::json_escape_string", _summary_json_escape_string)
    var _acc_json_object_start: Float64 = 0.0
    var _t0_json_object_start = perf_counter_ns()
    for _ in range(N):
        _ = json_object_start()
    var _t1_json_object_start = perf_counter_ns()
    var _ns_json_object_start = Float64(_t1_json_object_start - _t0_json_object_start) / Float64(N)
    print("MOJO_TIMING json_writer::json_object_start", _ns_json_object_start, _acc_json_object_start)
    var _result_json_object_start = json_object_start()
    var _summary_json_object_start = _summary_string(_result_json_object_start)
    print("MOJO_RESULT json_writer::json_object_start", _summary_json_object_start)
    var _acc_json_object_end: Float64 = 0.0
    var _t0_json_object_end = perf_counter_ns()
    for _ in range(N):
        _ = json_object_end("test")
    var _t1_json_object_end = perf_counter_ns()
    var _ns_json_object_end = Float64(_t1_json_object_end - _t0_json_object_end) / Float64(N)
    print("MOJO_TIMING json_writer::json_object_end", _ns_json_object_end, _acc_json_object_end)
    var _result_json_object_end = json_object_end("test")
    var _summary_json_object_end = _summary_string(_result_json_object_end)
    print("MOJO_RESULT json_writer::json_object_end", _summary_json_object_end)
    var _acc_json_add_string: Float64 = 0.0
    var _t0_json_add_string = perf_counter_ns()
    for _ in range(N):
        _ = json_add_string("test", "test", "test")
    var _t1_json_add_string = perf_counter_ns()
    var _ns_json_add_string = Float64(_t1_json_add_string - _t0_json_add_string) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_string", _ns_json_add_string, _acc_json_add_string)
    var _result_json_add_string = json_add_string("test", "test", "test")
    var _summary_json_add_string = _summary_string(_result_json_add_string)
    print("MOJO_RESULT json_writer::json_add_string", _summary_json_add_string)
    var _acc_json_add_int: Float64 = 0.0
    var _t0_json_add_int = perf_counter_ns()
    for _ in range(N):
        _ = json_add_int("test", "test", 5)
    var _t1_json_add_int = perf_counter_ns()
    var _ns_json_add_int = Float64(_t1_json_add_int - _t0_json_add_int) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_int", _ns_json_add_int, _acc_json_add_int)
    var _result_json_add_int = json_add_int("test", "test", 5)
    var _summary_json_add_int = _summary_string(_result_json_add_int)
    print("MOJO_RESULT json_writer::json_add_int", _summary_json_add_int)
    var _acc_json_add_float: Float64 = 0.0
    var _t0_json_add_float = perf_counter_ns()
    for _ in range(N):
        _ = json_add_float("test", "test", 0.5)
    var _t1_json_add_float = perf_counter_ns()
    var _ns_json_add_float = Float64(_t1_json_add_float - _t0_json_add_float) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_float", _ns_json_add_float, _acc_json_add_float)
    var _result_json_add_float = json_add_float("test", "test", 0.5)
    var _summary_json_add_float = _summary_string(_result_json_add_float)
    print("MOJO_RESULT json_writer::json_add_float", _summary_json_add_float)
    var _acc_json_add_bool: Float64 = 0.0
    var _t0_json_add_bool = perf_counter_ns()
    for _ in range(N):
        _ = json_add_bool("test", "test", True)
    var _t1_json_add_bool = perf_counter_ns()
    var _ns_json_add_bool = Float64(_t1_json_add_bool - _t0_json_add_bool) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_bool", _ns_json_add_bool, _acc_json_add_bool)
    var _result_json_add_bool = json_add_bool("test", "test", True)
    var _summary_json_add_bool = _summary_string(_result_json_add_bool)
    print("MOJO_RESULT json_writer::json_add_bool", _summary_json_add_bool)
    var _acc_json_add_null: Float64 = 0.0
    var _t0_json_add_null = perf_counter_ns()
    for _ in range(N):
        _ = json_add_null("test", "test")
    var _t1_json_add_null = perf_counter_ns()
    var _ns_json_add_null = Float64(_t1_json_add_null - _t0_json_add_null) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_null", _ns_json_add_null, _acc_json_add_null)
    var _result_json_add_null = json_add_null("test", "test")
    var _summary_json_add_null = _summary_string(_result_json_add_null)
    print("MOJO_RESULT json_writer::json_add_null", _summary_json_add_null)
    var _acc_json_add_array_float: Float64 = 0.0
    var _t0_json_add_array_float = perf_counter_ns()
    for _ in range(N):
        _ = json_add_array_float("test", "test", _lf5)
    var _t1_json_add_array_float = perf_counter_ns()
    var _ns_json_add_array_float = Float64(_t1_json_add_array_float - _t0_json_add_array_float) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_array_float", _ns_json_add_array_float, _acc_json_add_array_float)
    var _result_json_add_array_float = json_add_array_float("test", "test", _lf5)
    var _summary_json_add_array_float = _summary_string(_result_json_add_array_float)
    print("MOJO_RESULT json_writer::json_add_array_float", _summary_json_add_array_float)
    var _acc_json_add_array_string: Float64 = 0.0
    var _t0_json_add_array_string = perf_counter_ns()
    for _ in range(N):
        _ = json_add_array_string("test", "test", ["a","b","c","d","e"])
    var _t1_json_add_array_string = perf_counter_ns()
    var _ns_json_add_array_string = Float64(_t1_json_add_array_string - _t0_json_add_array_string) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_array_string", _ns_json_add_array_string, _acc_json_add_array_string)
    var _result_json_add_array_string = json_add_array_string("test", "test", ["a","b","c","d","e"])
    var _summary_json_add_array_string = _summary_string(_result_json_add_array_string)
    print("MOJO_RESULT json_writer::json_add_array_string", _summary_json_add_array_string)
    var _acc_json_add_raw: Float64 = 0.0
    var _t0_json_add_raw = perf_counter_ns()
    for _ in range(N):
        _ = json_add_raw("test", "test", "test")
    var _t1_json_add_raw = perf_counter_ns()
    var _ns_json_add_raw = Float64(_t1_json_add_raw - _t0_json_add_raw) / Float64(N)
    print("MOJO_TIMING json_writer::json_add_raw", _ns_json_add_raw, _acc_json_add_raw)
    var _result_json_add_raw = json_add_raw("test", "test", "test")
    var _summary_json_add_raw = _summary_string(_result_json_add_raw)
    print("MOJO_RESULT json_writer::json_add_raw", _summary_json_add_raw)
