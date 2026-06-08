"""bench_pattern.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pattern import glob_match, starts_with, ends_with, contains, count_occurrences, replace_all, template_substitute, split_string, join_strings, pad_left, pad_right, trim
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

    var _acc_glob_match: Float64 = 0.0
    var _t0_glob_match = perf_counter_ns()
    for _ in range(N):
        _acc_glob_match += Float64(glob_match("test", "test"))
    var _t1_glob_match = perf_counter_ns()
    var _ns_glob_match = Float64(_t1_glob_match - _t0_glob_match) / Float64(N)
    print("MOJO_TIMING pattern::glob_match", _ns_glob_match, _acc_glob_match)
    var _result_glob_match = glob_match("test", "test")
    var _summary_glob_match = _summary_bool(_result_glob_match)
    print("MOJO_RESULT pattern::glob_match", _summary_glob_match)
    var _acc_starts_with: Float64 = 0.0
    var _t0_starts_with = perf_counter_ns()
    for _ in range(N):
        _acc_starts_with += Float64(starts_with("test", "test"))
    var _t1_starts_with = perf_counter_ns()
    var _ns_starts_with = Float64(_t1_starts_with - _t0_starts_with) / Float64(N)
    print("MOJO_TIMING pattern::starts_with", _ns_starts_with, _acc_starts_with)
    var _result_starts_with = starts_with("test", "test")
    var _summary_starts_with = _summary_bool(_result_starts_with)
    print("MOJO_RESULT pattern::starts_with", _summary_starts_with)
    var _acc_ends_with: Float64 = 0.0
    var _t0_ends_with = perf_counter_ns()
    for _ in range(N):
        _acc_ends_with += Float64(ends_with("test", "test"))
    var _t1_ends_with = perf_counter_ns()
    var _ns_ends_with = Float64(_t1_ends_with - _t0_ends_with) / Float64(N)
    print("MOJO_TIMING pattern::ends_with", _ns_ends_with, _acc_ends_with)
    var _result_ends_with = ends_with("test", "test")
    var _summary_ends_with = _summary_bool(_result_ends_with)
    print("MOJO_RESULT pattern::ends_with", _summary_ends_with)
    var _acc_contains: Float64 = 0.0
    var _t0_contains = perf_counter_ns()
    for _ in range(N):
        _acc_contains += Float64(contains("test", "test"))
    var _t1_contains = perf_counter_ns()
    var _ns_contains = Float64(_t1_contains - _t0_contains) / Float64(N)
    print("MOJO_TIMING pattern::contains", _ns_contains, _acc_contains)
    var _result_contains = contains("test", "test")
    var _summary_contains = _summary_bool(_result_contains)
    print("MOJO_RESULT pattern::contains", _summary_contains)
    var _acc_count_occurrences: Float64 = 0.0
    var _t0_count_occurrences = perf_counter_ns()
    for _ in range(N):
        _acc_count_occurrences += Float64(count_occurrences("test", "test"))
    var _t1_count_occurrences = perf_counter_ns()
    var _ns_count_occurrences = Float64(_t1_count_occurrences - _t0_count_occurrences) / Float64(N)
    print("MOJO_TIMING pattern::count_occurrences", _ns_count_occurrences, _acc_count_occurrences)
    var _result_count_occurrences = count_occurrences("test", "test")
    var _summary_count_occurrences = _summary_int(_result_count_occurrences)
    print("MOJO_RESULT pattern::count_occurrences", _summary_count_occurrences)
    var _acc_replace_all: Float64 = 0.0
    var _t0_replace_all = perf_counter_ns()
    for _ in range(N):
        _ = replace_all("test", "test", "test")
    var _t1_replace_all = perf_counter_ns()
    var _ns_replace_all = Float64(_t1_replace_all - _t0_replace_all) / Float64(N)
    print("MOJO_TIMING pattern::replace_all", _ns_replace_all, _acc_replace_all)
    var _result_replace_all = replace_all("test", "test", "test")
    var _summary_replace_all = _summary_string(_result_replace_all)
    print("MOJO_RESULT pattern::replace_all", _summary_replace_all)
    var _acc_template_substitute: Float64 = 0.0
    var _t0_template_substitute = perf_counter_ns()
    for _ in range(N):
        _ = template_substitute("test", ["a","b","c","d","e"], ["a","b","c","d","e"])
    var _t1_template_substitute = perf_counter_ns()
    var _ns_template_substitute = Float64(_t1_template_substitute - _t0_template_substitute) / Float64(N)
    print("MOJO_TIMING pattern::template_substitute", _ns_template_substitute, _acc_template_substitute)
    var _result_template_substitute = template_substitute("test", ["a","b","c","d","e"], ["a","b","c","d","e"])
    var _summary_template_substitute = _summary_string(_result_template_substitute)
    print("MOJO_RESULT pattern::template_substitute", _summary_template_substitute)
    var _acc_split_string: Float64 = 0.0
    var _t0_split_string = perf_counter_ns()
    for _ in range(N):
        var _r_split_string = split_string("test", "test")
        _acc_split_string += Float64(len(_r_split_string))
    var _t1_split_string = perf_counter_ns()
    var _ns_split_string = Float64(_t1_split_string - _t0_split_string) / Float64(N)
    print("MOJO_TIMING pattern::split_string", _ns_split_string, _acc_split_string)
    var _result_split_string = split_string("test", "test")
    var _summary_split_string = _summary_list_string(_result_split_string)
    print("MOJO_RESULT pattern::split_string", _summary_split_string)
    var _acc_join_strings: Float64 = 0.0
    var _t0_join_strings = perf_counter_ns()
    for _ in range(N):
        _ = join_strings(["a","b","c","d","e"], "test")
    var _t1_join_strings = perf_counter_ns()
    var _ns_join_strings = Float64(_t1_join_strings - _t0_join_strings) / Float64(N)
    print("MOJO_TIMING pattern::join_strings", _ns_join_strings, _acc_join_strings)
    var _result_join_strings = join_strings(["a","b","c","d","e"], "test")
    var _summary_join_strings = _summary_string(_result_join_strings)
    print("MOJO_RESULT pattern::join_strings", _summary_join_strings)
    var _acc_pad_left: Float64 = 0.0
    var _t0_pad_left = perf_counter_ns()
    for _ in range(N):
        _ = pad_left("test", 5, 5)
    var _t1_pad_left = perf_counter_ns()
    var _ns_pad_left = Float64(_t1_pad_left - _t0_pad_left) / Float64(N)
    print("MOJO_TIMING pattern::pad_left", _ns_pad_left, _acc_pad_left)
    var _result_pad_left = pad_left("test", 5, 5)
    var _summary_pad_left = _summary_string(_result_pad_left)
    print("MOJO_RESULT pattern::pad_left", _summary_pad_left)
    var _acc_pad_right: Float64 = 0.0
    var _t0_pad_right = perf_counter_ns()
    for _ in range(N):
        _ = pad_right("test", 5, 5)
    var _t1_pad_right = perf_counter_ns()
    var _ns_pad_right = Float64(_t1_pad_right - _t0_pad_right) / Float64(N)
    print("MOJO_TIMING pattern::pad_right", _ns_pad_right, _acc_pad_right)
    var _result_pad_right = pad_right("test", 5, 5)
    var _summary_pad_right = _summary_string(_result_pad_right)
    print("MOJO_RESULT pattern::pad_right", _summary_pad_right)
    var _acc_trim: Float64 = 0.0
    var _t0_trim = perf_counter_ns()
    for _ in range(N):
        _ = trim("test")
    var _t1_trim = perf_counter_ns()
    var _ns_trim = Float64(_t1_trim - _t0_trim) / Float64(N)
    print("MOJO_TIMING pattern::trim", _ns_trim, _acc_trim)
    var _result_trim = trim("test")
    var _summary_trim = _summary_string(_result_trim)
    print("MOJO_RESULT pattern::trim", _summary_trim)
