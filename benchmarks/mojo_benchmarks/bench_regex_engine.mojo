"""bench_regex_engine.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from regex_engine import match_literal, match_dot_star, match_char_class, regex_match, regex_search, regex_find_first, count_matches, split_by_literal, is_valid_pattern
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

    var _acc_match_literal: Float64 = 0.0
    var _t0_match_literal = perf_counter_ns()
    for _ in range(N):
        _acc_match_literal += Float64(match_literal("test", "test"))
    var _t1_match_literal = perf_counter_ns()
    var _ns_match_literal = Float64(_t1_match_literal - _t0_match_literal) / Float64(N)
    print("MOJO_TIMING regex_engine::match_literal", _ns_match_literal, _acc_match_literal)
    var _result_match_literal = match_literal("test", "test")
    var _summary_match_literal = _summary_bool(_result_match_literal)
    print("MOJO_RESULT regex_engine::match_literal", _summary_match_literal)
    var _acc_match_dot_star: Float64 = 0.0
    var _t0_match_dot_star = perf_counter_ns()
    for _ in range(N):
        _acc_match_dot_star += Float64(match_dot_star("test", 5, 5))
    var _t1_match_dot_star = perf_counter_ns()
    var _ns_match_dot_star = Float64(_t1_match_dot_star - _t0_match_dot_star) / Float64(N)
    print("MOJO_TIMING regex_engine::match_dot_star", _ns_match_dot_star, _acc_match_dot_star)
    var _result_match_dot_star = match_dot_star("test", 5, 5)
    var _summary_match_dot_star = _summary_bool(_result_match_dot_star)
    print("MOJO_RESULT regex_engine::match_dot_star", _summary_match_dot_star)
    var _acc_match_char_class: Float64 = 0.0
    var _t0_match_char_class = perf_counter_ns()
    for _ in range(N):
        _acc_match_char_class += Float64(match_char_class("test", 5))
    var _t1_match_char_class = perf_counter_ns()
    var _ns_match_char_class = Float64(_t1_match_char_class - _t0_match_char_class) / Float64(N)
    print("MOJO_TIMING regex_engine::match_char_class", _ns_match_char_class, _acc_match_char_class)
    var _result_match_char_class = match_char_class("test", 5)
    var _summary_match_char_class = _summary_bool(_result_match_char_class)
    print("MOJO_RESULT regex_engine::match_char_class", _summary_match_char_class)
    var _acc_regex_match: Float64 = 0.0
    var _t0_regex_match = perf_counter_ns()
    for _ in range(N):
        _acc_regex_match += Float64(regex_match("test", "test"))
    var _t1_regex_match = perf_counter_ns()
    var _ns_regex_match = Float64(_t1_regex_match - _t0_regex_match) / Float64(N)
    print("MOJO_TIMING regex_engine::regex_match", _ns_regex_match, _acc_regex_match)
    var _result_regex_match = regex_match("test", "test")
    var _summary_regex_match = _summary_bool(_result_regex_match)
    print("MOJO_RESULT regex_engine::regex_match", _summary_regex_match)
    var _acc_regex_search: Float64 = 0.0
    var _t0_regex_search = perf_counter_ns()
    for _ in range(N):
        _acc_regex_search += Float64(regex_search("test", "test"))
    var _t1_regex_search = perf_counter_ns()
    var _ns_regex_search = Float64(_t1_regex_search - _t0_regex_search) / Float64(N)
    print("MOJO_TIMING regex_engine::regex_search", _ns_regex_search, _acc_regex_search)
    var _result_regex_search = regex_search("test", "test")
    var _summary_regex_search = _summary_bool(_result_regex_search)
    print("MOJO_RESULT regex_engine::regex_search", _summary_regex_search)
    var _acc_regex_find_first: Float64 = 0.0
    var _t0_regex_find_first = perf_counter_ns()
    for _ in range(N):
        var _r_regex_find_first = regex_find_first("test", "test")
        _acc_regex_find_first += Float64(len(_r_regex_find_first))
    var _t1_regex_find_first = perf_counter_ns()
    var _ns_regex_find_first = Float64(_t1_regex_find_first - _t0_regex_find_first) / Float64(N)
    print("MOJO_TIMING regex_engine::regex_find_first", _ns_regex_find_first, _acc_regex_find_first)
    var _result_regex_find_first = regex_find_first("test", "test")
    var _summary_regex_find_first = _summary_list_int(_result_regex_find_first)
    print("MOJO_RESULT regex_engine::regex_find_first", _summary_regex_find_first)
    var _acc_count_matches: Float64 = 0.0
    var _t0_count_matches = perf_counter_ns()
    for _ in range(N):
        _acc_count_matches += Float64(count_matches("test", "test"))
    var _t1_count_matches = perf_counter_ns()
    var _ns_count_matches = Float64(_t1_count_matches - _t0_count_matches) / Float64(N)
    print("MOJO_TIMING regex_engine::count_matches", _ns_count_matches, _acc_count_matches)
    var _result_count_matches = count_matches("test", "test")
    var _summary_count_matches = _summary_int(_result_count_matches)
    print("MOJO_RESULT regex_engine::count_matches", _summary_count_matches)
    var _acc_split_by_literal: Float64 = 0.0
    var _t0_split_by_literal = perf_counter_ns()
    for _ in range(N):
        var _r_split_by_literal = split_by_literal("test", "test")
        _acc_split_by_literal += Float64(len(_r_split_by_literal))
    var _t1_split_by_literal = perf_counter_ns()
    var _ns_split_by_literal = Float64(_t1_split_by_literal - _t0_split_by_literal) / Float64(N)
    print("MOJO_TIMING regex_engine::split_by_literal", _ns_split_by_literal, _acc_split_by_literal)
    var _result_split_by_literal = split_by_literal("test", "test")
    var _summary_split_by_literal = _summary_list_string(_result_split_by_literal)
    print("MOJO_RESULT regex_engine::split_by_literal", _summary_split_by_literal)
    var _acc_is_valid_pattern: Float64 = 0.0
    var _t0_is_valid_pattern = perf_counter_ns()
    for _ in range(N):
        _acc_is_valid_pattern += Float64(is_valid_pattern("test"))
    var _t1_is_valid_pattern = perf_counter_ns()
    var _ns_is_valid_pattern = Float64(_t1_is_valid_pattern - _t0_is_valid_pattern) / Float64(N)
    print("MOJO_TIMING regex_engine::is_valid_pattern", _ns_is_valid_pattern, _acc_is_valid_pattern)
    var _result_is_valid_pattern = is_valid_pattern("test")
    var _summary_is_valid_pattern = _summary_bool(_result_is_valid_pattern)
    print("MOJO_RESULT regex_engine::is_valid_pattern", _summary_is_valid_pattern)
