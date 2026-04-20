"""bench_text_regex.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from text.regex import regex_match, regex_search, regex_find_all, regex_replace, regex_split, is_match_literal, is_match_simple
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

    var _acc_regex_match: Float64 = 0.0
    var _t0_regex_match = perf_counter_ns()
    for _ in range(N):
        _acc_regex_match += Float64(regex_match("test", "test"))
    var _t1_regex_match = perf_counter_ns()
    var _ns_regex_match = Float64(_t1_regex_match - _t0_regex_match) / Float64(N)
    print("MOJO_TIMING text_regex::regex_match", _ns_regex_match, _acc_regex_match)
    var _acc_regex_search: Float64 = 0.0
    var _t0_regex_search = perf_counter_ns()
    for _ in range(N):
        _acc_regex_search += Float64(regex_search("test", "test"))
    var _t1_regex_search = perf_counter_ns()
    var _ns_regex_search = Float64(_t1_regex_search - _t0_regex_search) / Float64(N)
    print("MOJO_TIMING text_regex::regex_search", _ns_regex_search, _acc_regex_search)
    var _acc_regex_find_all: Float64 = 0.0
    var _t0_regex_find_all = perf_counter_ns()
    for _ in range(N):
        var _r_regex_find_all = regex_find_all("test", "test")
        _acc_regex_find_all += Float64(len(_r_regex_find_all))
    var _t1_regex_find_all = perf_counter_ns()
    var _ns_regex_find_all = Float64(_t1_regex_find_all - _t0_regex_find_all) / Float64(N)
    print("MOJO_TIMING text_regex::regex_find_all", _ns_regex_find_all, _acc_regex_find_all)
    var _acc_regex_replace: Float64 = 0.0
    var _t0_regex_replace = perf_counter_ns()
    for _ in range(N):
        _ = regex_replace("test", "test", "test")
    var _t1_regex_replace = perf_counter_ns()
    var _ns_regex_replace = Float64(_t1_regex_replace - _t0_regex_replace) / Float64(N)
    print("MOJO_TIMING text_regex::regex_replace", _ns_regex_replace, _acc_regex_replace)
    var _acc_regex_split: Float64 = 0.0
    var _t0_regex_split = perf_counter_ns()
    for _ in range(N):
        var _r_regex_split = regex_split("test", "test")
        _acc_regex_split += Float64(len(_r_regex_split))
    var _t1_regex_split = perf_counter_ns()
    var _ns_regex_split = Float64(_t1_regex_split - _t0_regex_split) / Float64(N)
    print("MOJO_TIMING text_regex::regex_split", _ns_regex_split, _acc_regex_split)
    var _acc_is_match_literal: Float64 = 0.0
    var _t0_is_match_literal = perf_counter_ns()
    for _ in range(N):
        _acc_is_match_literal += Float64(is_match_literal("test", "test"))
    var _t1_is_match_literal = perf_counter_ns()
    var _ns_is_match_literal = Float64(_t1_is_match_literal - _t0_is_match_literal) / Float64(N)
    print("MOJO_TIMING text_regex::is_match_literal", _ns_is_match_literal, _acc_is_match_literal)
    var _acc_is_match_simple: Float64 = 0.0
    var _t0_is_match_simple = perf_counter_ns()
    for _ in range(N):
        _acc_is_match_simple += Float64(is_match_simple("test", "test"))
    var _t1_is_match_simple = perf_counter_ns()
    var _ns_is_match_simple = Float64(_t1_is_match_simple - _t0_is_match_simple) / Float64(N)
    print("MOJO_TIMING text_regex::is_match_simple", _ns_is_match_simple, _acc_is_match_simple)
