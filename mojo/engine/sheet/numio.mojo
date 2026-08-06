"""sheet.numio — correctly-rounded decimal <-> Float64 for the sheet plane.

Bit-level agreement with Excel's cached values requires a correctly-rounded
decimal decoder; a digits*10^k accumulator is off by ULPs exactly where it
matters (a cached 17-significant-digit <v> would false-mismatch). libc strtod
is correctly rounded per C99 and the process never calls setlocale, so the
radix stays '.'.

Everything here is package-private (underscore names): nothing lands in the
runtime contract, so the "0.0 for a non-number" convention stays internal —
callers inside the package always gate on `_parse_number` first.

NOTE: `hostio/wire_json.mojo` on a WIP branch uses the same technique; this
module exists because that file is not on main. When both land, consolidate.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_sheet_refs.mojo
benchmark: benchmarks/mojo_benchmarks/bench_sheet_plane.mojo
docs: docs/mojo/sheet-plane.md
version_introduced: 2026-08
deprecation_state: active
@endcapability
"""

from std.ffi import external_call


def _bs_str(buf: List[UInt8]) -> String:
    """Byte-faithful List[UInt8] -> String. `chr(b)` on a byte >= 128 emits
    that CODEPOINT (two UTF-8 bytes), silently double-encoding any non-ASCII
    text — measured live as mojibake'd sheet names failing to resolve. The
    += copies into the owned String's buffer (rule 1b), so nothing aliases
    the local span."""
    var out = String("")
    out += StringSlice(unsafe_from_utf8=Span(buf))
    return out^


def _nul_terminated(s: String) -> List[UInt8]:
    """A NUL-terminated copy of `s`'s bytes: String.as_bytes() does NOT
    terminate, and strtod reads until a non-numeric byte, so the copy is what
    guarantees no scan can walk off the end."""
    var src = s.as_bytes()
    var n = len(src)
    var out = List[UInt8]()
    for i in range(n):
        out.append(src[i])
    out.append(0)
    return out^


def _is_plain_decimal(bs: Span[UInt8, _]) -> Bool:
    """The grammar `[+-]? (digits [. digits?] | . digits) [(e|E)[+-]?digits]`,
    nothing else — refuses inf/nan/hex floats that strtod would accept."""
    var n = len(bs)
    var i = 0
    if i < n and (Int(bs[i]) == 43 or Int(bs[i]) == 45):
        i += 1
    var digits_before = 0
    while i < n and Int(bs[i]) >= 48 and Int(bs[i]) <= 57:
        digits_before += 1
        i += 1
    var digits_after = 0
    if i < n and Int(bs[i]) == 46:
        i += 1
        while i < n and Int(bs[i]) >= 48 and Int(bs[i]) <= 57:
            digits_after += 1
            i += 1
    if digits_before + digits_after == 0:
        return False
    if i < n and (Int(bs[i]) == 101 or Int(bs[i]) == 69):
        i += 1
        if i < n and (Int(bs[i]) == 43 or Int(bs[i]) == 45):
            i += 1
        var exp_digits = 0
        while i < n and Int(bs[i]) >= 48 and Int(bs[i]) <= 57:
            exp_digits += 1
            i += 1
        if exp_digits == 0:
            return False
    return i == n


def _parse_number(text: String, mut value: Float64) -> Bool:
    """Correctly-rounded decimal parse. False (value untouched) when `text`
    is not exactly one plain decimal number."""
    var bs = text.as_bytes()
    if len(bs) == 0 or len(bs) > 512:
        return False
    if not _is_plain_decimal(bs):
        return False
    var buf = _nul_terminated(text)
    var endp = List[UInt64]()
    endp.append(0)
    value = external_call["strtod", Float64](buf.unsafe_ptr(), endp.unsafe_ptr())
    return True


def _parse_number_trimmed(text: String, mut value: Float64) -> Bool:
    """Excel text->number coercion: leading/trailing ASCII whitespace is
    forgiven, the body must be one plain decimal number."""
    var bs = text.as_bytes()
    var n = len(bs)
    var a = 0
    while a < n:
        var b = Int(bs[a])
        if b == 32 or b == 9 or b == 10 or b == 13:
            a += 1
        else:
            break
    var e = n
    while e > a:
        var b = Int(bs[e - 1])
        if b == 32 or b == 9 or b == 10 or b == 13:
            e -= 1
        else:
            break
    if e <= a:
        return False
    # byte-preserving slice (chr() would re-encode bytes >= 0x80); non-ASCII
    # bodies fail strtod either way, but the text must reach it unmangled
    var bbuf = List[UInt8]()
    for i in range(a, e):
        bbuf.append(bs[i])
    var body = _bs_str(bbuf)
    return _parse_number(body, value)
