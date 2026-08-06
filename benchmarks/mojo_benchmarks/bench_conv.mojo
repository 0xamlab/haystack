"""bench_conv.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from conv import is_digit, is_whitespace, digit_value, span_to_str, span_to_str_end, strip_whitespace, parse_float64, parse_int, float_to_string, int_to_hex
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

    var _acc_is_digit: Float64 = 0.0
    var _t0_is_digit = perf_counter_ns()
    for _ in range(N):
        _acc_is_digit += Float64(is_digit(1))
    var _t1_is_digit = perf_counter_ns()
    var _ns_is_digit = Float64(_t1_is_digit - _t0_is_digit) / Float64(N)
    print("MOJO_TIMING conv::is_digit", _ns_is_digit, _acc_is_digit)
    var _result_is_digit = is_digit(1)
    var _summary_is_digit = _summary_bool(_result_is_digit)
    print("MOJO_RESULT conv::is_digit", _summary_is_digit)
    var _acc_is_whitespace: Float64 = 0.0
    var _t0_is_whitespace = perf_counter_ns()
    for _ in range(N):
        _acc_is_whitespace += Float64(is_whitespace(1))
    var _t1_is_whitespace = perf_counter_ns()
    var _ns_is_whitespace = Float64(_t1_is_whitespace - _t0_is_whitespace) / Float64(N)
    print("MOJO_TIMING conv::is_whitespace", _ns_is_whitespace, _acc_is_whitespace)
    var _result_is_whitespace = is_whitespace(1)
    var _summary_is_whitespace = _summary_bool(_result_is_whitespace)
    print("MOJO_RESULT conv::is_whitespace", _summary_is_whitespace)
    var _acc_digit_value: Float64 = 0.0
    var _t0_digit_value = perf_counter_ns()
    for _ in range(N):
        _acc_digit_value += Float64(digit_value(1))
    var _t1_digit_value = perf_counter_ns()
    var _ns_digit_value = Float64(_t1_digit_value - _t0_digit_value) / Float64(N)
    print("MOJO_TIMING conv::digit_value", _ns_digit_value, _acc_digit_value)
    var _result_digit_value = digit_value(1)
    var _summary_digit_value = _summary_int(_result_digit_value)
    print("MOJO_RESULT conv::digit_value", _summary_digit_value)
    var _acc_span_to_str: Float64 = 0.0
    var _t0_span_to_str = perf_counter_ns()
    for _ in range(N):
        _ = span_to_str("test", 5, 5)
    var _t1_span_to_str = perf_counter_ns()
    var _ns_span_to_str = Float64(_t1_span_to_str - _t0_span_to_str) / Float64(N)
    print("MOJO_TIMING conv::span_to_str", _ns_span_to_str, _acc_span_to_str)
    var _result_span_to_str = span_to_str("test", 5, 5)
    var _summary_span_to_str = _summary_string(_result_span_to_str)
    print("MOJO_RESULT conv::span_to_str", _summary_span_to_str)
    var _acc_span_to_str_end: Float64 = 0.0
    var _t0_span_to_str_end = perf_counter_ns()
    for _ in range(N):
        _ = span_to_str_end("test", 5)
    var _t1_span_to_str_end = perf_counter_ns()
    var _ns_span_to_str_end = Float64(_t1_span_to_str_end - _t0_span_to_str_end) / Float64(N)
    print("MOJO_TIMING conv::span_to_str_end", _ns_span_to_str_end, _acc_span_to_str_end)
    var _result_span_to_str_end = span_to_str_end("test", 5)
    var _summary_span_to_str_end = _summary_string(_result_span_to_str_end)
    print("MOJO_RESULT conv::span_to_str_end", _summary_span_to_str_end)
    var _acc_strip_whitespace: Float64 = 0.0
    var _t0_strip_whitespace = perf_counter_ns()
    for _ in range(N):
        _ = strip_whitespace("test")
    var _t1_strip_whitespace = perf_counter_ns()
    var _ns_strip_whitespace = Float64(_t1_strip_whitespace - _t0_strip_whitespace) / Float64(N)
    print("MOJO_TIMING conv::strip_whitespace", _ns_strip_whitespace, _acc_strip_whitespace)
    var _result_strip_whitespace = strip_whitespace("test")
    var _summary_strip_whitespace = _summary_string(_result_strip_whitespace)
    print("MOJO_RESULT conv::strip_whitespace", _summary_strip_whitespace)
    var _acc_parse_float64: Float64 = 0.0
    var _t0_parse_float64 = perf_counter_ns()
    for _ in range(N):
        _acc_parse_float64 += parse_float64("test")
    var _t1_parse_float64 = perf_counter_ns()
    var _ns_parse_float64 = Float64(_t1_parse_float64 - _t0_parse_float64) / Float64(N)
    print("MOJO_TIMING conv::parse_float64", _ns_parse_float64, _acc_parse_float64)
    var _result_parse_float64 = parse_float64("test")
    var _summary_parse_float64 = _summary_float64(_result_parse_float64)
    print("MOJO_RESULT conv::parse_float64", _summary_parse_float64)
    var _acc_parse_int: Float64 = 0.0
    var _t0_parse_int = perf_counter_ns()
    for _ in range(N):
        _acc_parse_int += Float64(parse_int("test"))
    var _t1_parse_int = perf_counter_ns()
    var _ns_parse_int = Float64(_t1_parse_int - _t0_parse_int) / Float64(N)
    print("MOJO_TIMING conv::parse_int", _ns_parse_int, _acc_parse_int)
    var _result_parse_int = parse_int("test")
    var _summary_parse_int = _summary_int(_result_parse_int)
    print("MOJO_RESULT conv::parse_int", _summary_parse_int)
    var _acc_float_to_string: Float64 = 0.0
    var _t0_float_to_string = perf_counter_ns()
    for _ in range(N):
        _ = float_to_string(0.5)
    var _t1_float_to_string = perf_counter_ns()
    var _ns_float_to_string = Float64(_t1_float_to_string - _t0_float_to_string) / Float64(N)
    print("MOJO_TIMING conv::float_to_string", _ns_float_to_string, _acc_float_to_string)
    var _result_float_to_string = float_to_string(0.5)
    var _summary_float_to_string = _summary_string(_result_float_to_string)
    print("MOJO_RESULT conv::float_to_string", _summary_float_to_string)
    var _acc_int_to_hex: Float64 = 0.0
    var _t0_int_to_hex = perf_counter_ns()
    for _ in range(N):
        _ = int_to_hex(1, 5)
    var _t1_int_to_hex = perf_counter_ns()
    var _ns_int_to_hex = Float64(_t1_int_to_hex - _t0_int_to_hex) / Float64(N)
    print("MOJO_TIMING conv::int_to_hex", _ns_int_to_hex, _acc_int_to_hex)
    var _result_int_to_hex = int_to_hex(1, 5)
    var _summary_int_to_hex = _summary_string(_result_int_to_hex)
    print("MOJO_RESULT conv::int_to_hex", _summary_int_to_hex)
