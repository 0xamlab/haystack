"""
validate.mojo — Data validation utilities. Zero Python imports.
Replaces: Python's validators and custom validation logic.

Public API:
  is_valid_email, is_valid_ip4, is_valid_number, is_valid_json,
  is_in_range, is_positive, is_finite, clamp,
  sanitize_string, validate_array_bounds, check_monotonic
"""
from std.math import abs as fabs


# ── Helper: byte-level substring ──────────────────────────────────────────────

def _substr(s: String, start: Int, end: Int) -> String:
    """Extract substring s[start:end]."""
    var bs = s.as_bytes()
    var e = end
    if e > len(s):
        e = len(s)
    var result = String("")
    for i in range(start, e):
        result += chr(Int(bs[i]))
    return result^


# ── Email validation ──────────────────────────────────────────────────────────


def is_valid_email(s: String) -> Bool:
    """Basic email format check: has exactly one @, local part and domain are non-empty,
    domain has at least one dot, no spaces."""
    var n = len(s)
    if n < 3:
        return False

    var bs = s.as_bytes()
    var SPACE = UInt8(ord(" "))
    var AT = UInt8(ord("@"))
    var DOT = UInt8(ord("."))

    # Check for spaces
    for i in range(n):
        if bs[i] == SPACE:
            return False

    # Find @ symbol
    var at_pos = -1
    var at_count = 0
    for i in range(n):
        if bs[i] == AT:
            at_pos = i
            at_count += 1

    if at_count != 1:
        return False

    # Local part must be non-empty
    if at_pos == 0:
        return False

    # Domain part must be non-empty and have at least one dot
    var domain_start = at_pos + 1
    if domain_start >= n:
        return False

    var has_dot = False
    var last_was_dot = False
    for i in range(domain_start, n):
        if bs[i] == DOT:
            if i == domain_start:
                return False  # Domain starts with dot
            if last_was_dot:
                return False  # Consecutive dots
            has_dot = True
            last_was_dot = True
        else:
            last_was_dot = False

    if not has_dot:
        return False

    # Domain must not end with dot
    if bs[n - 1] == DOT:
        return False

    # TLD must have at least 2 characters
    var last_dot = -1
    for i in range(domain_start, n):
        if bs[i] == DOT:
            last_dot = i
    if last_dot >= 0 and (n - last_dot - 1) < 2:
        return False

    return True


# ── IPv4 validation ───────────────────────────────────────────────────────────


def is_valid_ip4(s: String) -> Bool:
    """IPv4 address validation: four decimal octets 0-255 separated by dots."""
    var n = len(s)
    if n < 7 or n > 15:
        return False

    var bs = s.as_bytes()
    var DOT = UInt8(ord("."))
    var ZERO = UInt8(ord("0"))
    var NINE = UInt8(ord("9"))

    var octet_count = 0
    var current_val = 0
    var digit_count = 0

    for i in range(n):
        var c = bs[i]
        if c == DOT:
            if digit_count == 0:
                return False  # Empty octet
            if current_val > 255:
                return False
            octet_count += 1
            current_val = 0
            digit_count = 0
        elif c >= ZERO and c <= NINE:
            current_val = current_val * 10 + Int(c - ZERO)
            digit_count += 1
            if digit_count > 3:
                return False
        else:
            return False  # Invalid character

    # Last octet
    if digit_count == 0:
        return False
    if current_val > 255:
        return False
    octet_count += 1

    return octet_count == 4


# ── Number validation ─────────────────────────────────────────────────────────


def is_valid_number(s: String) -> Bool:
    """Check if string can be parsed as a number (integer or float).
    Accepts optional leading sign, digits, optional decimal point, optional exponent."""
    var n = len(s)
    if n == 0:
        return False

    var bs = s.as_bytes()
    var PLUS = UInt8(ord("+"))
    var MINUS = UInt8(ord("-"))
    var DOT = UInt8(ord("."))
    var ZERO = UInt8(ord("0"))
    var NINE = UInt8(ord("9"))
    var E_LOWER = UInt8(ord("e"))
    var E_UPPER = UInt8(ord("E"))

    var i = 0
    # Optional sign
    if bs[i] == PLUS or bs[i] == MINUS:
        i += 1

    if i >= n:
        return False

    var has_digits = False
    var has_dot = False

    # Main digits and decimal
    while i < n:
        var c = bs[i]
        if c >= ZERO and c <= NINE:
            has_digits = True
            i += 1
        elif c == DOT and not has_dot:
            has_dot = True
            i += 1
        elif c == E_LOWER or c == E_UPPER:
            break  # Handle exponent
        else:
            return False

    if not has_digits:
        return False

    # Optional exponent
    if i < n and (bs[i] == E_LOWER or bs[i] == E_UPPER):
        i += 1
        if i >= n:
            return False
        if bs[i] == PLUS or bs[i] == MINUS:
            i += 1
        if i >= n:
            return False
        var exp_digits = False
        while i < n:
            if bs[i] >= ZERO and bs[i] <= NINE:
                exp_digits = True
                i += 1
            else:
                return False
        if not exp_digits:
            return False

    return i == n


# ── JSON validation ───────────────────────────────────────────────────────────


def is_valid_json(s: String) -> Bool:
    """Basic JSON structure validation.
    Checks balanced braces/brackets and basic structural correctness."""
    var n = len(s)
    if n == 0:
        return False

    var bs = s.as_bytes()
    var SPACE = UInt8(32)
    var NEWLINE = UInt8(10)
    var TAB = UInt8(9)
    var CR = UInt8(13)
    var LBRACE = UInt8(ord("{"))
    var RBRACE = UInt8(ord("}"))
    var LBRACK = UInt8(ord("["))
    var RBRACK = UInt8(ord("]"))
    var QUOTE = UInt8(ord('"'))
    var BACKSLASH = UInt8(ord("\\"))

    # Skip leading whitespace
    var start = 0
    while start < n and (bs[start] == SPACE or bs[start] == NEWLINE or bs[start] == TAB or bs[start] == CR):
        start += 1

    if start >= n:
        return False

    var first = bs[start]

    # Valid JSON must start with { or [ or " or digit or true/false/null
    if first == LBRACE or first == LBRACK:
        # Check balanced braces/brackets
        var brace_count = 0
        var bracket_count = 0
        var in_string = False
        var escaped = False

        for i in range(start, n):
            var c = bs[i]
            if escaped:
                escaped = False
                continue
            if c == BACKSLASH:
                if in_string:
                    escaped = True
                continue
            if c == QUOTE:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == LBRACE:
                brace_count += 1
            elif c == RBRACE:
                brace_count -= 1
                if brace_count < 0:
                    return False
            elif c == LBRACK:
                bracket_count += 1
            elif c == RBRACK:
                bracket_count -= 1
                if bracket_count < 0:
                    return False

        return brace_count == 0 and bracket_count == 0

    elif first == QUOTE:
        # String value
        if n < start + 2:
            return False
        return bs[n - 1] == QUOTE

    elif (first >= UInt8(ord("0")) and first <= UInt8(ord("9"))) or first == UInt8(ord("-")):
        # Number — use is_valid_number on trimmed string
        var end = n
        while end > start and (bs[end - 1] == SPACE or bs[end - 1] == NEWLINE or bs[end - 1] == TAB or bs[end - 1] == CR):
            end -= 1
        var trimmed = _substr(s, start, end)
        return is_valid_number(trimmed)

    elif n - start >= 4:
        # Check for true, null, false
        var t = UInt8(ord("t"))
        var nu = UInt8(ord("n"))
        var f = UInt8(ord("f"))
        if first == t and n - start >= 4:
            if bs[start + 1] == UInt8(ord("r")) and bs[start + 2] == UInt8(ord("u")) and bs[start + 3] == UInt8(ord("e")):
                return True
        if first == nu and n - start >= 4:
            if bs[start + 1] == UInt8(ord("u")) and bs[start + 2] == UInt8(ord("l")) and bs[start + 3] == UInt8(ord("l")):
                return True
        if first == f and n - start >= 5:
            if bs[start + 1] == UInt8(ord("a")) and bs[start + 2] == UInt8(ord("l")) and bs[start + 3] == UInt8(ord("s")) and bs[start + 4] == UInt8(ord("e")):
                return True

    return False


# ── Range check ───────────────────────────────────────────────────────────────


def is_in_range(value: Float64, low: Float64, high: Float64) -> Bool:
    """Check if value is in [low, high] inclusive."""
    return value >= low and value <= high


# ── Positive check ────────────────────────────────────────────────────────────


def is_positive(value: Float64) -> Bool:
    """Check if value is strictly positive."""
    return value > 0.0


# ── Finite check ──────────────────────────────────────────────────────────────


def is_finite(value: Float64) -> Bool:
    """Check if value is finite (not NaN or Inf).
    NaN != NaN, and Inf - Inf = NaN."""
    # NaN check: NaN != NaN
    if value != value:
        return False
    # Inf check: if value is infinite, value - value = NaN
    var diff = value - value
    if diff != diff:
        return False
    return True


# ── Clamp ─────────────────────────────────────────────────────────────────────


def clamp(value: Float64, low: Float64, high: Float64) -> Float64:
    """Clamp value to [low, high]."""
    if value < low:
        return low
    if value > high:
        return high
    return value


# ── Sanitize string ──────────────────────────────────────────────────────────


def sanitize_string(s: String) -> String:
    """Remove control characters (ASCII 0-31 except tab, newline, carriage return)."""
    var bs = s.as_bytes()
    var result = String("")
    for i in range(len(s)):
        var o = Int(bs[i])
        # Keep printable characters and common whitespace
        if o >= 32 or o == 9 or o == 10 or o == 13:
            result += chr(o)
    return result^


# ── Array bounds validation ───────────────────────────────────────────────────


def validate_array_bounds(data: List[Float64], min_val: Float64, max_val: Float64) -> Bool:
    """Check that all elements in data are within [min_val, max_val]."""
    for i in range(len(data)):
        if data[i] < min_val or data[i] > max_val:
            return False
    return True


# ── Monotonicity check ───────────────────────────────────────────────────────


def check_monotonic(data: List[Float64]) -> Int:
    """Check monotonicity of a sequence.
    Returns: 1 if strictly increasing, -1 if strictly decreasing, 0 if neither.
    A sequence of length 0 or 1 is considered both (returns 1)."""
    var n = len(data)
    if n <= 1:
        return 1

    var increasing = True
    var decreasing = True

    for i in range(1, n):
        if data[i] <= data[i - 1]:
            increasing = False
        if data[i] >= data[i - 1]:
            decreasing = False

    if increasing:
        return 1
    if decreasing:
        return -1
    return 0
