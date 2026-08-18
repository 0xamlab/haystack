"""
serialization_io.mojo — Weights/model state to/from STRING. Zero Python imports.

Replaces pickle / json / numpy.save weight dumps for persisting named
Float64 arrays. The kernel stays pure — string in, string out — and the
caller persists the string (file, KV store, receipt log). Fills the
real-serialization gap: conv.float_to_string / conv.parse_float64 are
rounded/lossy; this format is bit-exact in both directions.

Line format (one line per named array, '\\n'-terminated):

    v1|<name>|<len>|<v0>,<v1>,...,<v(len-1)>

Value tokens (full float precision via manual formatting):
  '0' / '-0'            — signed zeros (sign preserved)
  'inf' / '-inf' / 'nan'
  plain decimal integer — when the value is an integer with |v| < 2^62
  '<m>p<e>'             — otherwise: value = +-m * 2^e, with m an odd
                          positive decimal integer < 2^53 and e a base-2
                          exponent (C99 hex-float 'p' notation)

Only exact power-of-two scalings and integer digit arithmetic are used, so
weights_from_string(weights_to_string(...)) reproduces every Float64
bit-for-bit (negatives, subnormals, signed zeros, max/min magnitudes).
Every structurally valid token maps onto an exactly representable finite
Float64 (p-form domain: m < 2^53, e >= -1074, and e + bitlen(m) <= 1024,
i.e. m * 2^e <= (2^53 - 1) * 2^971 = max finite; this covers all finite
doubles, including odd-significand values above 2^971 such as
2^1023 = 1p1023); any corruption -> WeightsBundle.ok == False, never a
silently wrong value. Names must not contain '|' or newlines ('|', '\\n', '\\r'
bytes are replaced with '_'); ASCII names round-trip verbatim.

Performance: single pass over the payload; per-value cost is
O(|exponent|/32 + digits) ~= 70 simple ops, so 10k typical weights
serialize or parse well under 1 ms (worst-case subnormal-heavy payloads
roughly double that, still sub-ms).

Public API:
  WeightsBundle       — parse result: ok flag + names + arrays
  weights_to_string   — named Float64 arrays -> versioned string
  weights_from_string — string -> WeightsBundle (ok=False on any corruption)
  string_checksum     — FNV-1a 64-bit xor-folded to 32 bits, as Float64 (receipts)
"""


# ── WeightsBundle ────────────────────────────────────────────────────────────


struct WeightsBundle(Copyable, Movable):
    """Parse result: ok=False means corrupt/invalid payload (lists empty)."""

    var ok: Bool
    var names: List[String]
    var arrays: List[List[Float64]]

    def __init__(out self):
        self.ok = False
        self.names = List[String]()
        self.arrays = List[List[Float64]]()


# ── integer digit formatting (manual, no String(Float64)) ───────────────────


def _uint_to_string(v: Int) -> String:
    """Decimal digits of a non-negative Int, built manually."""
    if v <= 0:
        return String("0")
    var digits = List[Int]()
    var x = v
    while x > 0:
        digits.append(x % 10)
        x //= 10
    var s = String("")
    var i = len(digits) - 1
    while i >= 0:
        s += chr(48 + digits[i])
        i -= 1
    return s


def _int_to_string(v: Int) -> String:
    """Decimal digits of a signed Int."""
    if v < 0:
        return "-" + _uint_to_string(-v)
    return _uint_to_string(v)


def _bit_length(v: Int) -> Int:
    """Number of bits needed to represent v > 0."""
    var b = 0
    var x = v
    while x > 0:
        x >>= 1
        b += 1
    return b


# ── special-value helpers ────────────────────────────────────────────────────


@always_inline
def _pos_inf() -> Float64:
    var big: Float64 = 1.0e308
    return big * 10.0


@always_inline
def _quiet_nan() -> Float64:
    var z: Float64 = 0.0
    return z / z


@always_inline
def _is_neg_zero(v: Float64) -> Bool:
    if v != 0.0:
        return False
    var one: Float64 = 1.0
    return one / v < 0.0


# ── exact binary decomposition / reconstruction ──────────────────────────────


def _decompose(x0: Float64) -> Tuple[Int, Int]:
    """Exact (m, e) with x0 = m * 2^e and m odd, for finite x0 > 0.

    Scales x0 into [2^52, 2^53) using only power-of-two multiplies and
    divides (each exact: same significand bits, shifted exponent), reads
    off the integer significand, then strips trailing zero bits.
    """
    var two21: Float64 = 2097152.0
    var two32: Float64 = 4294967296.0
    var two52: Float64 = 4503599627370496.0
    var two53: Float64 = 9007199254740992.0
    var two84 = two52 * two32
    var x = x0
    var e = 0
    while x < two21:
        x *= two32
        e -= 32
    while x < two52:
        x *= 2.0
        e -= 1
    while x >= two84:
        x /= two32
        e += 32
    while x >= two53:
        x /= 2.0
        e += 1
    var m = Int(x)
    while (m & 1) == 0:
        m >>= 1
        e += 1
    return (m, e)


def _scale_by_pow2(v0: Float64, e: Int) -> Float64:
    """v0 * 2^e via exact power-of-two steps.

    Exact whenever the true result (and thus every intermediate, which
    shares its significand bits) is representable — guaranteed for every
    token the strict parser accepts.
    """
    var two32: Float64 = 4294967296.0
    var v = v0
    var t = e
    while t >= 32:
        v *= two32
        t -= 32
    while t > 0:
        v *= 2.0
        t -= 1
    while t <= -32:
        v /= two32
        t += 32
    while t < 0:
        v /= 2.0
        t += 1
    return v


# ── value token: format ──────────────────────────────────────────────────────


def _float_to_token(v: Float64) -> String:
    """One Float64 -> exact token (see module docstring for grammar)."""
    if v != v:
        return String("nan")
    var inf_val = _pos_inf()
    if v == inf_val:
        return String("inf")
    if v == -inf_val:
        return String("-inf")
    if v == 0.0:
        if _is_neg_zero(v):
            return String("-0")
        return String("0")
    var neg = v < 0.0
    var x = v
    if neg:
        x = -x
    var me = _decompose(x)
    var m = me[0]
    var e = me[1]
    var sign = String("")
    if neg:
        sign = String("-")
    if e >= 0 and e <= 62 - _bit_length(m):
        # Exact integer that fits comfortably in Int64: plain digits.
        return sign + _uint_to_string(m << e)
    return sign + _uint_to_string(m) + "p" + _int_to_string(e)


# ── value token: parse ───────────────────────────────────────────────────────


def _parse_token(bytes: Span[Byte, _], start: Int, end: Int) -> Tuple[Bool, Float64]:
    """Strict parse of one token in bytes[start:end). Returns (ok, value)."""
    if start >= end:
        return (False, 0.0)
    var i = start
    var neg = False
    if bytes[i] == UInt8(45):  # '-'
        neg = True
        i += 1
        if i >= end:
            return (False, 0.0)
    if bytes[i] == UInt8(105):  # 'i'
        if end - i == 3 and bytes[i + 1] == UInt8(110) and bytes[i + 2] == UInt8(102):
            var inf_val = _pos_inf()
            if neg:
                return (True, -inf_val)
            return (True, inf_val)
        return (False, 0.0)
    if bytes[i] == UInt8(110):  # 'n'
        if (
            not neg
            and end - i == 3
            and bytes[i + 1] == UInt8(97)
            and bytes[i + 2] == UInt8(110)
        ):
            return (True, _quiet_nan())
        return (False, 0.0)

    # Significand digits.
    var m = 0
    var have = False
    while i < end and bytes[i] >= UInt8(48) and bytes[i] <= UInt8(57):
        if m > 461168601842738790:  # keep m*10+9 < ~2^62: no Int64 overflow
            return (False, 0.0)
        m = m * 10 + Int(bytes[i] - UInt8(48))
        have = True
        i += 1
    if not have:
        return (False, 0.0)

    if i == end:
        # Plain integer form: must be exactly representable as Float64.
        var v = Float64(m)
        if Int(v) != m:
            return (False, 0.0)
        if neg:
            v = -v
        return (True, v)

    # 'p' exponent form.
    if bytes[i] != UInt8(112):  # 'p'
        return (False, 0.0)
    i += 1
    if m >= 9007199254740992:  # p-form significand must be < 2^53
        return (False, 0.0)
    var eneg = False
    if i < end and bytes[i] == UInt8(45):  # '-'
        eneg = True
        i += 1
    var eabs = 0
    var ehave = False
    while i < end and bytes[i] >= UInt8(48) and bytes[i] <= UInt8(57):
        eabs = eabs * 10 + Int(bytes[i] - UInt8(48))
        if eabs > 100000:
            return (False, 0.0)
        ehave = True
        i += 1
    if not ehave or i != end:
        return (False, 0.0)
    var e = eabs
    if eneg:
        e = -eabs
    # Exact-representability domain: e >= -1074 (multiple of the min
    # subnormal) and m * 2^e <= (2^53-1) * 2^971 = max finite, which for
    # m < 2^53 is exactly e + bitlen(m) <= 1024 (m odd after _decompose
    # can carry e up to 1023, e.g. 2^1023 -> '1p1023').
    if e < -1074 or e > 1024 - _bit_length(m):
        return (False, 0.0)
    var v = _scale_by_pow2(Float64(m), e)
    if neg:
        v = -v
    return (True, v)


# ── name sanitization ────────────────────────────────────────────────────────


def _sanitize_name(name: String) -> String:
    """Replace '|', '\\n', '\\r' bytes with '_'; unchanged names pass through."""
    var bytes = name.as_bytes()
    var n = name.byte_length()
    var has_bad = False
    for i in range(n):
        var c = bytes[i]
        if c == UInt8(124) or c == UInt8(10) or c == UInt8(13):
            has_bad = True
            break
    if not has_bad:
        return name
    var out = String("")
    for i in range(n):
        var c = bytes[i]
        if c == UInt8(124) or c == UInt8(10) or c == UInt8(13):
            out += "_"
        else:
            out += chr(Int(c))
    return out


# ── weights_to_string ────────────────────────────────────────────────────────


def weights_to_string(names: List[String], arrays: List[List[Float64]]) -> String:
    """Serialize named Float64 arrays to the versioned 'v1|name|len|csv' format.

    One '\\n'-terminated line per array; value tokens are bit-exact (see
    module docstring). Deterministic: identical inputs yield identical
    strings, so string_checksum receipts are stable.

    Args:
        names: Array names, parallel to arrays ('|' and newlines -> '_').
        arrays: One List[Float64] per name.

    Returns:
        Serialized payload, or empty string when len(names) != len(arrays)
        (caller must treat empty-with-nonempty-input as an error). Empty
        inputs serialize to the empty string.
    """
    var out = String("")
    if len(names) != len(arrays):
        return out
    for k in range(len(names)):
        out += "v1|"
        out += _sanitize_name(names[k])
        out += "|"
        out += _uint_to_string(len(arrays[k]))
        out += "|"
        for i in range(len(arrays[k])):
            if i > 0:
                out += ","
            out += _float_to_token(arrays[k][i])
        out += "\n"
    return out


# ── weights_from_string ──────────────────────────────────────────────────────


def _parse_line(
    bytes: Span[Byte, _], start: Int, end: Int, mut bundle: WeightsBundle
) -> Bool:
    """Parse one 'v1|name|len|csv' line in bytes[start:end) into bundle."""
    var i = start
    if end - i < 3:
        return False
    if (
        bytes[i] != UInt8(118)  # 'v'
        or bytes[i + 1] != UInt8(49)  # '1'
        or bytes[i + 2] != UInt8(124)  # '|'
    ):
        return False
    i += 3

    # Name field (until '|').
    var name = String("")
    while i < end and bytes[i] != UInt8(124):
        name += chr(Int(bytes[i]))
        i += 1
    if i >= end:
        return False
    i += 1

    # Declared length field (until '|').
    var declared = 0
    var have_digit = False
    while i < end and bytes[i] != UInt8(124):
        var c = bytes[i]
        if c < UInt8(48) or c > UInt8(57):
            return False
        declared = declared * 10 + Int(c - UInt8(48))
        if declared > 100000000:
            return False
        have_digit = True
        i += 1
    if not have_digit or i >= end:
        return False
    i += 1

    # CSV values.
    var vals = List[Float64]()
    if i < end:
        var tok_start = i
        var j = i
        while j <= end:
            if j == end or bytes[j] == UInt8(44):  # ','
                var pv = _parse_token(bytes, tok_start, j)
                if not pv[0]:
                    return False
                vals.append(pv[1])
                tok_start = j + 1
            j += 1
    if len(vals) != declared:
        return False
    bundle.names.append(name^)
    bundle.arrays.append(vals^)
    return True


def weights_from_string(s: String) -> WeightsBundle:
    """Parse a payload produced by weights_to_string.

    Strict: version tag must be 'v1', field count must match, declared
    length must equal the number of value tokens, and every token must be
    well-formed and in the exactly-representable domain. Any violation
    returns ok=False with empty lists — corrupt payloads never yield
    partial or silently-rounded weights. Blank lines and '\\r\\n' endings
    are tolerated; the empty string parses to an ok, empty bundle.

    Args:
        s: Serialized payload.

    Returns:
        WeightsBundle(ok, names, arrays); parsed values equal the original
        Float64s bit-for-bit.
    """
    var bundle = WeightsBundle()
    var bytes = s.as_bytes()
    var n = s.byte_length()
    var pos = 0
    while pos < n:
        var eol = pos
        while eol < n and bytes[eol] != UInt8(10):  # '\n'
            eol += 1
        var line_end = eol
        if line_end > pos and bytes[line_end - 1] == UInt8(13):  # '\r'
            line_end -= 1
        if line_end > pos:
            if not _parse_line(bytes, pos, line_end, bundle):
                return WeightsBundle()  # ok=False, lists empty
        pos = eol + 1
    bundle.ok = True
    return bundle^


# ── string_checksum ──────────────────────────────────────────────────────────


def string_checksum(s: String) -> Float64:
    """FNV-1a 64-bit hash of the string's bytes, xor-folded to 32 bits.

    For receipts/audit logs: deterministic, order-sensitive, and exactly
    representable (integer-valued Float64 in [0, 2^32), so no precision is
    lost storing or comparing it as Float64).

    Args:
        s: Any string (typically a weights_to_string payload).

    Returns:
        Folded FNV-1a checksum as an integer-valued Float64.
    """
    var h: UInt64 = UInt64(0xCBF29CE484222325)  # FNV offset basis
    var bytes = s.as_bytes()
    for i in range(s.byte_length()):
        h = h ^ UInt64(Int(bytes[i]))
        h = h * UInt64(0x100000001B3)  # FNV prime (wrapping)
    var folded = (h >> 32) ^ (h & UInt64(0xFFFFFFFF))
    return Float64(Int(folded))
