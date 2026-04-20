"""bench_conv.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from conv import is_digit, is_whitespace, digit_value, span_to_str, span_to_str_end, strip_whitespace, parse_float64, parse_int, float_to_string, int_to_hex
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

    var _acc_is_digit: Float64 = 0.0
    var _t0_is_digit = perf_counter_ns()
    for _ in range(N):
        _acc_is_digit += Float64(is_digit(1))
    var _t1_is_digit = perf_counter_ns()
    var _ns_is_digit = Float64(_t1_is_digit - _t0_is_digit) / Float64(N)
    print("MOJO_TIMING conv::is_digit", _ns_is_digit, _acc_is_digit)
    var _acc_is_whitespace: Float64 = 0.0
    var _t0_is_whitespace = perf_counter_ns()
    for _ in range(N):
        _acc_is_whitespace += Float64(is_whitespace(1))
    var _t1_is_whitespace = perf_counter_ns()
    var _ns_is_whitespace = Float64(_t1_is_whitespace - _t0_is_whitespace) / Float64(N)
    print("MOJO_TIMING conv::is_whitespace", _ns_is_whitespace, _acc_is_whitespace)
    var _acc_digit_value: Float64 = 0.0
    var _t0_digit_value = perf_counter_ns()
    for _ in range(N):
        _acc_digit_value += Float64(digit_value(1))
    var _t1_digit_value = perf_counter_ns()
    var _ns_digit_value = Float64(_t1_digit_value - _t0_digit_value) / Float64(N)
    print("MOJO_TIMING conv::digit_value", _ns_digit_value, _acc_digit_value)
    var _acc_span_to_str: Float64 = 0.0
    var _t0_span_to_str = perf_counter_ns()
    for _ in range(N):
        _ = span_to_str("test", 5, 5)
    var _t1_span_to_str = perf_counter_ns()
    var _ns_span_to_str = Float64(_t1_span_to_str - _t0_span_to_str) / Float64(N)
    print("MOJO_TIMING conv::span_to_str", _ns_span_to_str, _acc_span_to_str)
    var _acc_span_to_str_end: Float64 = 0.0
    var _t0_span_to_str_end = perf_counter_ns()
    for _ in range(N):
        _ = span_to_str_end("test", 5)
    var _t1_span_to_str_end = perf_counter_ns()
    var _ns_span_to_str_end = Float64(_t1_span_to_str_end - _t0_span_to_str_end) / Float64(N)
    print("MOJO_TIMING conv::span_to_str_end", _ns_span_to_str_end, _acc_span_to_str_end)
    var _acc_strip_whitespace: Float64 = 0.0
    var _t0_strip_whitespace = perf_counter_ns()
    for _ in range(N):
        _ = strip_whitespace("test")
    var _t1_strip_whitespace = perf_counter_ns()
    var _ns_strip_whitespace = Float64(_t1_strip_whitespace - _t0_strip_whitespace) / Float64(N)
    print("MOJO_TIMING conv::strip_whitespace", _ns_strip_whitespace, _acc_strip_whitespace)
    var _acc_parse_float64: Float64 = 0.0
    var _t0_parse_float64 = perf_counter_ns()
    for _ in range(N):
        _acc_parse_float64 += parse_float64("test")
    var _t1_parse_float64 = perf_counter_ns()
    var _ns_parse_float64 = Float64(_t1_parse_float64 - _t0_parse_float64) / Float64(N)
    print("MOJO_TIMING conv::parse_float64", _ns_parse_float64, _acc_parse_float64)
    var _acc_parse_int: Float64 = 0.0
    var _t0_parse_int = perf_counter_ns()
    for _ in range(N):
        _acc_parse_int += Float64(parse_int("test"))
    var _t1_parse_int = perf_counter_ns()
    var _ns_parse_int = Float64(_t1_parse_int - _t0_parse_int) / Float64(N)
    print("MOJO_TIMING conv::parse_int", _ns_parse_int, _acc_parse_int)
    var _acc_float_to_string: Float64 = 0.0
    var _t0_float_to_string = perf_counter_ns()
    for _ in range(N):
        _ = float_to_string(0.5)
    var _t1_float_to_string = perf_counter_ns()
    var _ns_float_to_string = Float64(_t1_float_to_string - _t0_float_to_string) / Float64(N)
    print("MOJO_TIMING conv::float_to_string", _ns_float_to_string, _acc_float_to_string)
    var _acc_int_to_hex: Float64 = 0.0
    var _t0_int_to_hex = perf_counter_ns()
    for _ in range(N):
        _ = int_to_hex(1, 5)
    var _t1_int_to_hex = perf_counter_ns()
    var _ns_int_to_hex = Float64(_t1_int_to_hex - _t0_int_to_hex) / Float64(N)
    print("MOJO_TIMING conv::int_to_hex", _ns_int_to_hex, _acc_int_to_hex)
