"""
Pure Mojo number/string conversion utilities. Zero Python imports.

Replaces the Python-dependent fast_f64(), fast_int(), and py_str() helpers
in python_bridge.mojo with native byte-by-byte parsing.  Used by the
Mojo-native JSON parser for converting raw token bytes into Float64/Int.

Public API:
  parse_float64(s: String) -> Float64    — decimal/scientific string → Float64
  parse_int(s: String) -> Int            — integer string → Int (truncates floats)
  float_to_string(v: Float64) -> String  — Float64 → String
  int_to_hex(v: UInt32, width: Int) -> String — UInt32 → zero-padded hex
  strip_whitespace(s: String) -> String  — trim leading/trailing ASCII whitespace

Byte-level helpers (always_inline):
  is_digit(c: UInt8) -> Bool
  is_whitespace(c: UInt8) -> Bool
  digit_value(c: UInt8) -> Int
"""


# ── Byte-level helpers ──────────────────────────────────────────────────────────


@always_inline
fn is_digit(c: UInt8) -> Bool:
    """Check if byte is ASCII digit '0'-'9'."""
    return c >= UInt8(48) and c <= UInt8(57)  # ord('0')=48, ord('9')=57


@always_inline
fn is_whitespace(c: UInt8) -> Bool:
    """Check if byte is ASCII whitespace (space, tab, newline, carriage return)."""
    return c == UInt8(32) or c == UInt8(9) or c == UInt8(10) or c == UInt8(13)


@always_inline
fn digit_value(c: UInt8) -> Int:
    """Convert ASCII digit byte to its integer value. Assumes is_digit(c)."""
    return Int(c) - 48


# ── Safe substring extraction ─────────────────────────────────────────────────


fn span_to_str(s: String, start: Int, end: Int) -> String:
    """Extract substring [start, end) from s, building char-by-char.

    Unlike String(bytes[start:end]), this always produces the actual
    character content rather than a repr of the byte array.
    """
    var bytes = s.as_bytes()
    var e = min(end, len(s))
    var result = String("")
    for i in range(start, e):
        result += chr(Int(bytes[i]))
    return result


fn span_to_str_end(s: String, start: Int) -> String:
    """Extract substring [start, len(s)) from s, building char-by-char."""
    return span_to_str(s, start, len(s))


# ── Whitespace stripping ────────────────────────────────────────────────────────


fn strip_whitespace(s: String) -> String:
    """Remove leading and trailing ASCII whitespace from string."""
    var n = len(s)
    if n == 0:
        return s

    var bytes = s.as_bytes()
    var start = 0
    while start < n and is_whitespace(bytes[start]):
        start += 1

    var end = n - 1
    while end >= start and is_whitespace(bytes[end]):
        end -= 1

    if start > end:
        return String("")

    # Build result character-by-character to avoid byte-slice null-terminator issues
    var result = String("")
    for i in range(start, end + 1):
        result += chr(Int(bytes[i]))
    return result


# ── Internal: find whitespace-trimmed bounds ─────────────────────────────────


fn _trimmed_bounds(bytes: Span[Byte, _], n: Int) -> Tuple[Int, Int]:
    """Return (start, end_exclusive) indices skipping leading/trailing whitespace."""
    var start = 0
    while start < n and is_whitespace(bytes[start]):
        start += 1
    var end = n
    while end > start and is_whitespace(bytes[end - 1]):
        end -= 1
    return (start, end)


# ── Float64 parsing from raw bytes ──────────────────────────────────────────────


fn _pow10(exp: Int) -> Float64:
    """Compute 10.0 ** exp for integer exponents (positive or negative)."""
    var result: Float64 = 1.0
    var base: Float64 = 10.0
    var e = exp if exp >= 0 else -exp

    while e > 0:
        if e & 1 == 1:
            result *= base
        base *= base
        e >>= 1

    if exp < 0:
        return 1.0 / result
    return result


fn parse_float64(s: String) -> Float64:
    """Parse a decimal number string to Float64.

    Handles:
    - Integer: "42" → 42.0
    - Decimal: "3.14" → 3.14
    - Negative: "-100.5" → -100.5
    - Scientific: "1.5e3" → 1500.0, "2.5E-4" → 0.00025
    - Leading/trailing whitespace: "  42.0  " → 42.0
    - Edge cases: "0", "-0", ".5" → 0.5, "-.5" → -0.5
    Returns 0.0 for unparseable strings.
    """
    var n = len(s)
    if n == 0:
        return 0.0

    var bytes = s.as_bytes()
    var bounds = _trimmed_bounds(bytes, n)
    var pos = bounds[0]
    var limit = bounds[1]

    if pos >= limit:
        return 0.0

    var negative = False

    # ── 1. Sign ──
    if bytes[pos] == UInt8(45):  # '-'
        negative = True
        pos += 1
    elif bytes[pos] == UInt8(43):  # '+'
        pos += 1

    if pos >= limit:
        return 0.0

    var has_digits = False

    # ── 2. Integer part ──
    var int_part: Float64 = 0.0
    while pos < limit and is_digit(bytes[pos]):
        int_part = int_part * 10.0 + Float64(digit_value(bytes[pos]))
        pos += 1
        has_digits = True

    # ── 3. Fractional part ──
    var frac_part: Float64 = 0.0
    if pos < limit and bytes[pos] == UInt8(46):  # '.'
        pos += 1
        var frac_scale: Float64 = 0.1
        while pos < limit and is_digit(bytes[pos]):
            frac_part += Float64(digit_value(bytes[pos])) * frac_scale
            frac_scale *= 0.1
            pos += 1
            has_digits = True

    if not has_digits:
        return 0.0

    var result = int_part + frac_part

    # ── 4. Exponent (scientific notation) ──
    if pos < limit and (bytes[pos] == UInt8(101) or bytes[pos] == UInt8(69)):  # 'e' or 'E'
        pos += 1
        var exp_negative = False
        if pos < limit and bytes[pos] == UInt8(45):  # '-'
            exp_negative = True
            pos += 1
        elif pos < limit and bytes[pos] == UInt8(43):  # '+'
            pos += 1

        var exp_val = 0
        while pos < limit and is_digit(bytes[pos]):
            exp_val = exp_val * 10 + digit_value(bytes[pos])
            pos += 1

        if exp_negative:
            exp_val = -exp_val

        result *= _pow10(exp_val)

    # ── 5. Apply sign ──
    if negative:
        result = -result

    return result


# ── Integer parsing from raw bytes ──────────────────────────────────────────────


fn parse_int(s: String) -> Int:
    """Parse an integer string to Int.

    Handles:
    - Positive: "42" → 42
    - Negative: "-100" → -100
    - Leading/trailing whitespace: "  42  " → 42
    - Float input: "42.7" → 42 (truncate at decimal point)
    Returns 0 for unparseable strings.
    """
    var n = len(s)
    if n == 0:
        return 0

    var bytes = s.as_bytes()
    var bounds = _trimmed_bounds(bytes, n)
    var pos = bounds[0]
    var limit = bounds[1]

    if pos >= limit:
        return 0

    var negative = False

    # ── 1. Sign ──
    if bytes[pos] == UInt8(45):  # '-'
        negative = True
        pos += 1
    elif bytes[pos] == UInt8(43):  # '+'
        pos += 1

    if pos >= limit:
        return 0

    var has_digits = False
    var result = 0

    # ── 2. Digits (stop at '.' for float truncation) ──
    while pos < limit and is_digit(bytes[pos]):
        result = result * 10 + digit_value(bytes[pos])
        pos += 1
        has_digits = True

    if not has_digits:
        return 0

    # If there's a decimal point, we just ignore the fractional part (truncation)

    if negative:
        result = -result

    return result


# ── Float64 to String ──────────────────────────────────────────────────────────


fn float_to_string(v: Float64) -> String:
    """Convert Float64 to string representation.

    Uses Mojo's built-in String conversion for consistent formatting.
    """
    return String(v)


# ── Int to hex string ──────────────────────────────────────────────────────────


@always_inline
fn _nibble_to_hex(n: Int) -> String:
    """Convert a 4-bit nibble (0-15) to a single lowercase hex character."""
    if n < 10:
        return chr(48 + n)   # ord('0') = 48
    return chr(87 + n)       # ord('a') - 10 = 87


fn int_to_hex(v: UInt32, width: Int = 8) -> String:
    """Convert UInt32 to zero-padded lowercase hex string.

    Example: int_to_hex(255, 8) → "000000ff"
    Used by sha256.mojo for hex digest.
    """
    var s = String("")
    # Build hex from most-significant nibble down
    for i in range(width):
        var shift = UInt32((width - 1 - i) * 4)
        s += _nibble_to_hex(Int((v >> shift) & 0xF))
    return s
