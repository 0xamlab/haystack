"""bench_text_regex.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from text.regex import regex_match, regex_search, regex_find_all, regex_replace, regex_split, is_match_literal, is_match_simple
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

    var _acc_regex_match: Float64 = 0.0
    var _t0_regex_match = perf_counter_ns()
    for _ in range(N):
        _acc_regex_match += Float64(regex_match("test", "test"))
    var _t1_regex_match = perf_counter_ns()
    var _ns_regex_match = Float64(_t1_regex_match - _t0_regex_match) / Float64(N)
    print("MOJO_TIMING text_regex::regex_match", _ns_regex_match, _acc_regex_match)
    var _result_regex_match = regex_match("test", "test")
    var _summary_regex_match = _summary_bool(_result_regex_match)
    print("MOJO_RESULT text_regex::regex_match", _summary_regex_match)
    var _acc_regex_search: Float64 = 0.0
    var _t0_regex_search = perf_counter_ns()
    for _ in range(N):
        _acc_regex_search += Float64(regex_search("test", "test"))
    var _t1_regex_search = perf_counter_ns()
    var _ns_regex_search = Float64(_t1_regex_search - _t0_regex_search) / Float64(N)
    print("MOJO_TIMING text_regex::regex_search", _ns_regex_search, _acc_regex_search)
    var _result_regex_search = regex_search("test", "test")
    var _summary_regex_search = _summary_int(_result_regex_search)
    print("MOJO_RESULT text_regex::regex_search", _summary_regex_search)
    var _acc_regex_find_all: Float64 = 0.0
    var _t0_regex_find_all = perf_counter_ns()
    for _ in range(N):
        var _r_regex_find_all = regex_find_all("test", "test")
        _acc_regex_find_all += Float64(len(_r_regex_find_all))
    var _t1_regex_find_all = perf_counter_ns()
    var _ns_regex_find_all = Float64(_t1_regex_find_all - _t0_regex_find_all) / Float64(N)
    print("MOJO_TIMING text_regex::regex_find_all", _ns_regex_find_all, _acc_regex_find_all)
    var _result_regex_find_all = regex_find_all("test", "test")
    var _summary_regex_find_all = _summary_list_string(_result_regex_find_all)
    print("MOJO_RESULT text_regex::regex_find_all", _summary_regex_find_all)
    var _acc_regex_replace: Float64 = 0.0
    var _t0_regex_replace = perf_counter_ns()
    for _ in range(N):
        _ = regex_replace("test", "test", "test")
    var _t1_regex_replace = perf_counter_ns()
    var _ns_regex_replace = Float64(_t1_regex_replace - _t0_regex_replace) / Float64(N)
    print("MOJO_TIMING text_regex::regex_replace", _ns_regex_replace, _acc_regex_replace)
    var _result_regex_replace = regex_replace("test", "test", "test")
    var _summary_regex_replace = _summary_string(_result_regex_replace)
    print("MOJO_RESULT text_regex::regex_replace", _summary_regex_replace)
    var _acc_regex_split: Float64 = 0.0
    var _t0_regex_split = perf_counter_ns()
    for _ in range(N):
        var _r_regex_split = regex_split("test", "test")
        _acc_regex_split += Float64(len(_r_regex_split))
    var _t1_regex_split = perf_counter_ns()
    var _ns_regex_split = Float64(_t1_regex_split - _t0_regex_split) / Float64(N)
    print("MOJO_TIMING text_regex::regex_split", _ns_regex_split, _acc_regex_split)
    var _result_regex_split = regex_split("test", "test")
    var _summary_regex_split = _summary_list_string(_result_regex_split)
    print("MOJO_RESULT text_regex::regex_split", _summary_regex_split)
    var _acc_is_match_literal: Float64 = 0.0
    var _t0_is_match_literal = perf_counter_ns()
    for _ in range(N):
        _acc_is_match_literal += Float64(is_match_literal("test", "test"))
    var _t1_is_match_literal = perf_counter_ns()
    var _ns_is_match_literal = Float64(_t1_is_match_literal - _t0_is_match_literal) / Float64(N)
    print("MOJO_TIMING text_regex::is_match_literal", _ns_is_match_literal, _acc_is_match_literal)
    var _result_is_match_literal = is_match_literal("test", "test")
    var _summary_is_match_literal = _summary_bool(_result_is_match_literal)
    print("MOJO_RESULT text_regex::is_match_literal", _summary_is_match_literal)
    var _acc_is_match_simple: Float64 = 0.0
    var _t0_is_match_simple = perf_counter_ns()
    for _ in range(N):
        _acc_is_match_simple += Float64(is_match_simple("test", "test"))
    var _t1_is_match_simple = perf_counter_ns()
    var _ns_is_match_simple = Float64(_t1_is_match_simple - _t0_is_match_simple) / Float64(N)
    print("MOJO_TIMING text_regex::is_match_simple", _ns_is_match_simple, _acc_is_match_simple)
    var _result_is_match_simple = is_match_simple("test", "test")
    var _summary_is_match_simple = _summary_bool(_result_is_match_simple)
    print("MOJO_RESULT text_regex::is_match_simple", _summary_is_match_simple)
