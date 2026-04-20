"""bench_pattern.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pattern import glob_match, starts_with, ends_with, contains, count_occurrences, replace_all, template_substitute, split_string, join_strings, pad_left, pad_right, trim
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

    var _acc_glob_match: Float64 = 0.0
    var _t0_glob_match = perf_counter_ns()
    for _ in range(N):
        _acc_glob_match += Float64(glob_match("test", "test"))
    var _t1_glob_match = perf_counter_ns()
    var _ns_glob_match = Float64(_t1_glob_match - _t0_glob_match) / Float64(N)
    print("MOJO_TIMING pattern::glob_match", _ns_glob_match, _acc_glob_match)
    var _acc_starts_with: Float64 = 0.0
    var _t0_starts_with = perf_counter_ns()
    for _ in range(N):
        _acc_starts_with += Float64(starts_with("test", "test"))
    var _t1_starts_with = perf_counter_ns()
    var _ns_starts_with = Float64(_t1_starts_with - _t0_starts_with) / Float64(N)
    print("MOJO_TIMING pattern::starts_with", _ns_starts_with, _acc_starts_with)
    var _acc_ends_with: Float64 = 0.0
    var _t0_ends_with = perf_counter_ns()
    for _ in range(N):
        _acc_ends_with += Float64(ends_with("test", "test"))
    var _t1_ends_with = perf_counter_ns()
    var _ns_ends_with = Float64(_t1_ends_with - _t0_ends_with) / Float64(N)
    print("MOJO_TIMING pattern::ends_with", _ns_ends_with, _acc_ends_with)
    var _acc_contains: Float64 = 0.0
    var _t0_contains = perf_counter_ns()
    for _ in range(N):
        _acc_contains += Float64(contains("test", "test"))
    var _t1_contains = perf_counter_ns()
    var _ns_contains = Float64(_t1_contains - _t0_contains) / Float64(N)
    print("MOJO_TIMING pattern::contains", _ns_contains, _acc_contains)
    var _acc_count_occurrences: Float64 = 0.0
    var _t0_count_occurrences = perf_counter_ns()
    for _ in range(N):
        _acc_count_occurrences += Float64(count_occurrences("test", "test"))
    var _t1_count_occurrences = perf_counter_ns()
    var _ns_count_occurrences = Float64(_t1_count_occurrences - _t0_count_occurrences) / Float64(N)
    print("MOJO_TIMING pattern::count_occurrences", _ns_count_occurrences, _acc_count_occurrences)
    var _acc_replace_all: Float64 = 0.0
    var _t0_replace_all = perf_counter_ns()
    for _ in range(N):
        _ = replace_all("test", "test", "test")
    var _t1_replace_all = perf_counter_ns()
    var _ns_replace_all = Float64(_t1_replace_all - _t0_replace_all) / Float64(N)
    print("MOJO_TIMING pattern::replace_all", _ns_replace_all, _acc_replace_all)
    var _acc_template_substitute: Float64 = 0.0
    var _t0_template_substitute = perf_counter_ns()
    for _ in range(N):
        _ = template_substitute("test", ["a","b","c","d","e"], ["a","b","c","d","e"])
    var _t1_template_substitute = perf_counter_ns()
    var _ns_template_substitute = Float64(_t1_template_substitute - _t0_template_substitute) / Float64(N)
    print("MOJO_TIMING pattern::template_substitute", _ns_template_substitute, _acc_template_substitute)
    var _acc_split_string: Float64 = 0.0
    var _t0_split_string = perf_counter_ns()
    for _ in range(N):
        var _r_split_string = split_string("test", "test")
        _acc_split_string += Float64(len(_r_split_string))
    var _t1_split_string = perf_counter_ns()
    var _ns_split_string = Float64(_t1_split_string - _t0_split_string) / Float64(N)
    print("MOJO_TIMING pattern::split_string", _ns_split_string, _acc_split_string)
    var _acc_join_strings: Float64 = 0.0
    var _t0_join_strings = perf_counter_ns()
    for _ in range(N):
        _ = join_strings(["a","b","c","d","e"], "test")
    var _t1_join_strings = perf_counter_ns()
    var _ns_join_strings = Float64(_t1_join_strings - _t0_join_strings) / Float64(N)
    print("MOJO_TIMING pattern::join_strings", _ns_join_strings, _acc_join_strings)
    var _acc_pad_left: Float64 = 0.0
    var _t0_pad_left = perf_counter_ns()
    for _ in range(N):
        _ = pad_left("test", 5, 5)
    var _t1_pad_left = perf_counter_ns()
    var _ns_pad_left = Float64(_t1_pad_left - _t0_pad_left) / Float64(N)
    print("MOJO_TIMING pattern::pad_left", _ns_pad_left, _acc_pad_left)
    var _acc_pad_right: Float64 = 0.0
    var _t0_pad_right = perf_counter_ns()
    for _ in range(N):
        _ = pad_right("test", 5, 5)
    var _t1_pad_right = perf_counter_ns()
    var _ns_pad_right = Float64(_t1_pad_right - _t0_pad_right) / Float64(N)
    print("MOJO_TIMING pattern::pad_right", _ns_pad_right, _acc_pad_right)
    var _acc_trim: Float64 = 0.0
    var _t0_trim = perf_counter_ns()
    for _ in range(N):
        _ = trim("test")
    var _t1_trim = perf_counter_ns()
    var _ns_trim = Float64(_t1_trim - _t0_trim) / Float64(N)
    print("MOJO_TIMING pattern::trim", _ns_trim, _acc_trim)
