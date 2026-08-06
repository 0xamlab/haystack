"""
test_conv.mojo — Tests for the pure-Mojo number/string conversion library.

Validates parse_float64, parse_int, int_to_hex, and byte-level helpers
against all documented edge cases.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_conv.mojo
"""
from conv import (
    parse_float64,
    parse_int,
    float_to_string,
    int_to_hex,
    is_digit,
    is_whitespace,
    digit_value,
    strip_whitespace,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def approx_eq(a: Float64, b: Float64, eps: Float64 = 1e-10) -> Bool:
    """Check if two Float64 values are approximately equal."""
    var diff = a - b
    if diff < 0:
        diff = -diff
    return diff < eps


def _assert_float(got: Float64, expected: Float64, label: String) raises:
    """Assert two floats are approximately equal."""
    if not approx_eq(got, expected):
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)
    print("✅ " + label)


def _assert_int(got: Int, expected: Int, label: String) raises:
    """Assert two ints are equal."""
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)
    print("✅ " + label)


def _assert_str(got: String, expected: String, label: String) raises:
    """Assert two strings are equal."""
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + expected)
        print("   got:      " + got)
        raise Error("assertion failed: " + label)
    print("✅ " + label)


def _assert_true(cond: Bool, label: String) raises:
    """Assert condition is true."""
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)
    print("✅ " + label)


# ── parse_float64 tests ──────────────────────────────────────────────────────


def test_parse_float64_basic_integers() raises:
    _assert_float(parse_float64("42"), 42.0, "parse_float64('42') == 42.0")
    _assert_float(parse_float64("0"), 0.0, "parse_float64('0') == 0.0")
    _assert_float(parse_float64("-100"), -100.0, "parse_float64('-100') == -100.0")


def test_parse_float64_decimals() raises:
    _assert_float(parse_float64("3.14"), 3.14, "parse_float64('3.14') == 3.14")
    _assert_float(parse_float64("-0.5"), -0.5, "parse_float64('-0.5') == -0.5")
    _assert_float(parse_float64(".5"), 0.5, "parse_float64('.5') == 0.5")
    _assert_float(parse_float64("-.5"), -0.5, "parse_float64('-.5') == -0.5")


def test_parse_float64_scientific() raises:
    _assert_float(parse_float64("1.5e3"), 1500.0, "parse_float64('1.5e3') == 1500.0")
    _assert_float(
        parse_float64("2.5E-4"), 0.00025, "parse_float64('2.5E-4') == 0.00025"
    )
    _assert_float(parse_float64("-1e2"), -100.0, "parse_float64('-1e2') == -100.0")
    _assert_float(parse_float64("5e0"), 5.0, "parse_float64('5e0') == 5.0")
    _assert_float(parse_float64("1e+3"), 1000.0, "parse_float64('1e+3') == 1000.0")


def test_parse_float64_whitespace() raises:
    _assert_float(
        parse_float64("  42.0  "), 42.0, "parse_float64('  42.0  ') == 42.0"
    )
    _assert_float(
        parse_float64("\t3.14\n"), 3.14, "parse_float64('\\t3.14\\n') == 3.14"
    )


def test_parse_float64_large_numbers() raises:
    _assert_float(
        parse_float64("100000"), 100000.0, "parse_float64('100000') == 100000.0"
    )
    _assert_float(
        parse_float64("20000.50"), 20000.50, "parse_float64('20000.50') == 20000.50"
    )


def test_parse_float64_edge_cases() raises:
    _assert_float(parse_float64(""), 0.0, "parse_float64('') == 0.0")
    _assert_float(parse_float64("abc"), 0.0, "parse_float64('abc') == 0.0")
    _assert_float(parse_float64("-0"), 0.0, "parse_float64('-0') == 0.0 (negative zero)")
    _assert_float(parse_float64("+42"), 42.0, "parse_float64('+42') == 42.0")


# ── parse_int tests ──────────────────────────────────────────────────────────


def test_parse_int_basic() raises:
    _assert_int(parse_int("42"), 42, "parse_int('42') == 42")
    _assert_int(parse_int("-100"), -100, "parse_int('-100') == -100")
    _assert_int(parse_int("0"), 0, "parse_int('0') == 0")


def test_parse_int_whitespace() raises:
    _assert_int(parse_int("  42  "), 42, "parse_int('  42  ') == 42")


def test_parse_int_large() raises:
    _assert_int(parse_int("10000"), 10000, "parse_int('10000') == 10000")


def test_parse_int_truncation() raises:
    _assert_int(parse_int("42.7"), 42, "parse_int('42.7') == 42 (truncation)")
    _assert_int(parse_int("-3.9"), -3, "parse_int('-3.9') == -3 (truncation)")


def test_parse_int_edge_cases() raises:
    _assert_int(parse_int(""), 0, "parse_int('') == 0")
    _assert_int(parse_int("abc"), 0, "parse_int('abc') == 0")


# ── int_to_hex tests ─────────────────────────────────────────────────────────


def test_int_to_hex() raises:
    _assert_str(
        int_to_hex(UInt32(0), 8), "00000000", "int_to_hex(0, 8) == '00000000'"
    )
    _assert_str(
        int_to_hex(UInt32(255), 8), "000000ff", "int_to_hex(255, 8) == '000000ff'"
    )
    _assert_str(
        int_to_hex(UInt32(0xDEADBEEF), 8),
        "deadbeef",
        "int_to_hex(0xdeadbeef, 8) == 'deadbeef'",
    )
    _assert_str(
        int_to_hex(UInt32(0x6A09E667), 8),
        "6a09e667",
        "int_to_hex(0x6a09e667, 8) == '6a09e667'",
    )


# ── Byte helper tests ────────────────────────────────────────────────────────


def test_is_digit() raises:
    _assert_true(is_digit(UInt8(ord("0"))), "is_digit('0') == True")
    _assert_true(is_digit(UInt8(ord("9"))), "is_digit('9') == True")
    _assert_true(is_digit(UInt8(ord("5"))), "is_digit('5') == True")
    _assert_true(not is_digit(UInt8(ord("a"))), "is_digit('a') == False")
    _assert_true(not is_digit(UInt8(ord(" "))), "is_digit(' ') == False")


def test_is_whitespace() raises:
    _assert_true(is_whitespace(UInt8(ord(" "))), "is_whitespace(' ') == True")
    _assert_true(is_whitespace(UInt8(ord("\n"))), "is_whitespace('\\n') == True")
    _assert_true(is_whitespace(UInt8(ord("\t"))), "is_whitespace('\\t') == True")
    _assert_true(is_whitespace(UInt8(ord("\r"))), "is_whitespace('\\r') == True")
    _assert_true(not is_whitespace(UInt8(ord("x"))), "is_whitespace('x') == False")
    _assert_true(not is_whitespace(UInt8(ord("0"))), "is_whitespace('0') == False")


def test_digit_value() raises:
    _assert_int(digit_value(UInt8(ord("0"))), 0, "digit_value('0') == 0")
    _assert_int(digit_value(UInt8(ord("5"))), 5, "digit_value('5') == 5")
    _assert_int(digit_value(UInt8(ord("9"))), 9, "digit_value('9') == 9")


# ── strip_whitespace tests ───────────────────────────────────────────────────


def test_strip_whitespace() raises:
    _assert_str(strip_whitespace("  hello  "), "hello", "strip('  hello  ')")
    _assert_str(strip_whitespace("\t\nhello\r\n"), "hello", "strip('\\t\\nhello\\r\\n')")
    _assert_str(strip_whitespace("hello"), "hello", "strip('hello') no-op")
    _assert_str(strip_whitespace("   "), "", "strip('   ') == ''")
    _assert_str(strip_whitespace(""), "", "strip('') == ''")


# ── Runner ────────────────────────────────────────────────────────────────────


def main() raises:
    print("━━━ conv.mojo test suite ━━━")

    # parse_float64
    test_parse_float64_basic_integers()
    test_parse_float64_decimals()
    test_parse_float64_scientific()
    test_parse_float64_whitespace()
    test_parse_float64_large_numbers()
    test_parse_float64_edge_cases()

    # parse_int
    test_parse_int_basic()
    test_parse_int_whitespace()
    test_parse_int_large()
    test_parse_int_truncation()
    test_parse_int_edge_cases()

    # int_to_hex
    test_int_to_hex()

    # byte helpers
    test_is_digit()
    test_is_whitespace()
    test_digit_value()

    # strip_whitespace
    test_strip_whitespace()

    print("━━━ ✅ All conv tests passed ━━━")
