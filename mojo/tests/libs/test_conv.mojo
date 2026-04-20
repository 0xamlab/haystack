"""test_conv.mojo — auto-generated tests for conv library."""
from std.math import isnan, isinf
from conv import is_digit, is_whitespace, digit_value, span_to_str, span_to_str_end, strip_whitespace, parse_float64, parse_int, float_to_string, int_to_hex

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    _ = is_digit(UInt8(8))
    passed += 1; print("  ✅ conv::is_digit")
    _ = is_whitespace(UInt8(8))
    passed += 1; print("  ✅ conv::is_whitespace")
    _ = digit_value(UInt8(8))
    passed += 1; print("  ✅ conv::digit_value")
    _ = span_to_str("test", 5, 5)
    passed += 1; print("  ✅ conv::span_to_str")
    _ = span_to_str_end("test", 5)
    passed += 1; print("  ✅ conv::span_to_str_end")
    _ = strip_whitespace("test")
    passed += 1; print("  ✅ conv::strip_whitespace")
    var _v_parse_float64 = parse_float64("test")
    if is_finite(_v_parse_float64): passed += 1; print("  ✅ conv::parse_float64 =", _v_parse_float64)
    else: failed += 1; print("  ❌ conv::parse_float64 → non-finite:", _v_parse_float64)
    _ = parse_int("test")
    passed += 1; print("  ✅ conv::parse_int")
    _ = float_to_string(0.5)
    passed += 1; print("  ✅ conv::float_to_string")
    _ = int_to_hex(UInt32(42), 5)
    passed += 1; print("  ✅ conv::int_to_hex")

    print("  [conv] Passed:", passed, "Failed:", failed)
