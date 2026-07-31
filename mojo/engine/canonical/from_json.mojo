"""
canonical.from_json — transcode arbitrary JSON text into canonical bytes. Zero Python.

Hashing JSON *text* does not identify a value: `{"a":1,"b":2}` and `{"b":2,"a":1}`
are the same value and hash differently, as do the same bytes with different
whitespace. Any two producers that serialise independently — a Python SDK and a
TypeScript SDK, say — will eventually disagree, and the disagreement shows up as a
cache miss or a false "the plan changed", not as an error.

Transcoding removes the text from the equation: parse the JSON, re-emit it through
`canonical.encode`, hash that. Key order, whitespace and number formatting all stop
mattering because none of them survive the round trip.

Numbers
-------
JSON does not distinguish integers from floats, so a rule is needed and any rule is
a decision: a token with no `.`, `e` or `E` encodes as an int, everything else as a
float. That keeps `1` and `1.0` distinguishable — they are different JSON tokens and
a caller who wrote one did not write the other — while making `1.0` and `1.00`
identical, which they are.

Strings
-------
A string is decoded to its BYTES before encoding, so the escape form does not leak
into the hash: `"\\u00f1"` and a literal `"ñ"` are the same value and must hash the
same. That decoding has to be exact in both directions, and getting it wrong the
other way is worse than not doing it — this file shipped with a `\\uXXXX` decoder
that emitted the literal `u` and let the four hex digits through as text, so `ñ` and
the ASCII text `u00f1` produced IDENTICAL canonical bytes. Two different plans then
shared one `plan_hash`, which is precisely the property a canonical hash exists to
provide, and a caller trusts it. So: `\\uXXXX` decodes to the UTF-8 bytes of that
code point, a `\\uD83D\\uDE00` surrogate pair decodes to the one code point it
denotes, and every other byte is copied through untouched — never rebuilt with
`chr(Int(byte))`, which turns any byte >= 0x80 into two.

Malformed input is refused rather than canonicalised, for the same reason
`_is_number_token` refuses `a`: an invented canonical form for garbage collides with
the real spelling of something else. `"\\q"` has no meaning in JSON, and mapping it
to `q` or to `\\q` makes it collide with a document that says one of those literally.
"""
from json.parser import skip_json_value, skip_whitespace

from canonical.encode import (
    write_array_header,
    write_bool,
    write_float,
    write_int,
    write_null,
    write_object_header,
    write_string,
    byte_order_less,
)

comptime _QUOTE: UInt8 = 34
comptime _MINUS: UInt8 = 45
comptime _DOT: UInt8 = 46
comptime _ZERO: UInt8 = 48
comptime _NINE: UInt8 = 57
comptime _COLON: UInt8 = 58
comptime _UPPER_E: UInt8 = 69
comptime _LOWER_E: UInt8 = 101
comptime _BRACKET_OPEN: UInt8 = 91
comptime _BRACKET_CLOSE: UInt8 = 93
comptime _BRACE_OPEN: UInt8 = 123
comptime _BRACE_CLOSE: UInt8 = 125
comptime _COMMA: UInt8 = 44
comptime _T: UInt8 = 116
comptime _F: UInt8 = 102
comptime _N: UInt8 = 110
# The escape alphabet, named as one vocabulary so the decoder table reads as a table.
# `_LOWER_T/F/N` are the same bytes as `_T/_F/_N` above by coincidence — `true` and `\t`
# both start with `t` — and the two names mark two different roles, so neither replaces
# the other.
comptime _BACKSLASH: UInt8 = 92
comptime _SLASH: UInt8 = 47
comptime _LOWER_U: UInt8 = 117
comptime _LOWER_B: UInt8 = 98
comptime _LOWER_N: UInt8 = 110
comptime _LOWER_R: UInt8 = 114
comptime _LOWER_T: UInt8 = 116
comptime _LOWER_F: UInt8 = 102

# Depth bound: a deeply nested payload would otherwise recurse without limit.
comptime MAX_JSON_DEPTH: Int = 64


fn _string_from_utf8(data: List[UInt8]) -> String:
    """A String OWNING a copy of raw UTF-8 bytes, byte for byte.

    Why `+=` into an owned String rather than `String(StringSlice(unsafe_from_utf8=...))`:
    the direct form aliases `data`, a LOCAL of the caller that dies on return, leaving
    the String pointing at freed memory. Under `mojo run` it survives; in the optimized
    worker binary that exact pattern crashed a `filter` op and made `project` read a
    garbage op name (rule 1b). `+=` copies into the String's own buffer, so no aliasing
    survives.

    Why not `chr`: `chr(Int(byte))` of any byte >= 0x80 emits a two-byte UTF-8 sequence,
    so "café" (5 bytes) round-trips as "cafÃ©" (7). Every byte here must be preserved
    exactly, because the hash is over these bytes.

    This mirrors `query.plan._string_from_utf8` deliberately rather than importing it:
    `query.plan` imports `canonical.from_json`, so the import would be circular. The two
    must agree on what a decoded name is, so any change to one belongs in both.
    """
    var out = String("")
    out += StringSlice(unsafe_from_utf8=Span(data))
    return out


fn _slice(data: String, start: Int, end: Int) -> String:
    """Bytes `[start, end)` as an owned String, byte-exact and CLAMPED at both ends.

    Clamping is load-bearing, not defensive dressing: `skip_json_value` returns `p + 4`
    for a token starting with `t` without checking it spells `true`, so `transcode("[t]")`
    asks for bytes 1..5 of a 3-byte document. An unclamped read there is an uncatchable
    abort that takes the worker and every resident dataset with it (rule 1) — verified:
    it crashed the process. The truncated token that survives clamping is then rejected
    by the caller.
    """
    var bytes = data.as_bytes()
    var begin = start if start > 0 else 0
    var finish = end if end < len(bytes) else len(bytes)
    if finish <= begin:
        return String("")
    var raw = List[UInt8]()
    for i in range(begin, finish):
        raw.append(bytes[i])
    return _string_from_utf8(raw)


fn _hex_nibble(c: UInt8) -> Int:
    """One hex digit's value, or -1. Used only by the `\\uXXXX` decoder."""
    if c >= UInt8(48) and c <= UInt8(57):
        return Int(c) - 48
    if c >= UInt8(97) and c <= UInt8(102):
        return Int(c) - 97 + 10
    if c >= UInt8(65) and c <= UInt8(70):
        return Int(c) - 65 + 10
    return -1


fn _append_code_point(mut out: List[UInt8], code_point: Int):
    """UTF-8 encode one code point. The `\\uXXXX` escape's whole point."""
    var cp = code_point
    if cp < 0:
        return
    if cp < 0x80:
        out.append(UInt8(cp))
    elif cp < 0x800:
        out.append(UInt8(0xC0 | (cp >> 6)))
        out.append(UInt8(0x80 | (cp & 0x3F)))
    elif cp < 0x10000:
        out.append(UInt8(0xE0 | (cp >> 12)))
        out.append(UInt8(0x80 | ((cp >> 6) & 0x3F)))
        out.append(UInt8(0x80 | (cp & 0x3F)))
    else:
        out.append(UInt8(0xF0 | (cp >> 18)))
        out.append(UInt8(0x80 | ((cp >> 12) & 0x3F)))
        out.append(UInt8(0x80 | ((cp >> 6) & 0x3F)))
        out.append(UInt8(0x80 | (cp & 0x3F)))


fn _decode_string_token(data: String, start: Int, end: Int) raises -> String:
    """The bytes a JSON string token at `[start, end)` denotes — quotes stripped.

    Bounds are clamped before any read (rule 1), then the quotes are REQUIRED: a token
    that does not open and close with one is a truncated string, and accepting it would
    let `["ab` and `["ab"]` produce the same canonical bytes.

    `\\uXXXX` decodes to the UTF-8 bytes of that code point, and a high surrogate is
    paired with the low surrogate that follows it so `\\uD83D\\uDE00` is one code point
    (4 bytes) rather than two half-characters. An unpaired surrogate is encoded as-is,
    matching `query.plan.json_unescape`, so the two paths never disagree about a name.

    Anything that is not a JSON escape raises. See the module docstring: an invented
    canonical form for invalid input collides with the valid spelling of something else,
    which is the same defect as the `\\u` bug this decoder replaced.
    """
    var bytes = data.as_bytes()
    var begin = start if start > 0 else 0
    var finish = end if end < len(bytes) else len(bytes)
    if finish - begin < 2 or bytes[begin] != _QUOTE or bytes[finish - 1] != _QUOTE:
        raise Error("canonical.from_json: unterminated string token")

    var out = List[UInt8]()
    var i = begin + 1
    var limit = finish - 1
    while i < limit:
        var c = bytes[i]
        if c != _BACKSLASH:
            out.append(c)
            i += 1
            continue
        if i + 1 >= limit:
            raise Error("canonical.from_json: string ends in a backslash")
        var next = bytes[i + 1]

        if next == _LOWER_U:
            if i + 5 >= limit:
                raise Error("canonical.from_json: truncated \\u escape")
            var h0 = _hex_nibble(bytes[i + 2])
            var h1 = _hex_nibble(bytes[i + 3])
            var h2 = _hex_nibble(bytes[i + 4])
            var h3 = _hex_nibble(bytes[i + 5])
            if h0 < 0 or h1 < 0 or h2 < 0 or h3 < 0:
                raise Error("canonical.from_json: \\u escape needs four hex digits")
            var cp = (h0 << 12) | (h1 << 8) | (h2 << 4) | h3
            i += 6
            if cp >= 0xD800 and cp <= 0xDBFF and i + 5 < limit:
                if bytes[i] == _BACKSLASH and bytes[i + 1] == _LOWER_U:
                    var l0 = _hex_nibble(bytes[i + 2])
                    var l1 = _hex_nibble(bytes[i + 3])
                    var l2 = _hex_nibble(bytes[i + 4])
                    var l3 = _hex_nibble(bytes[i + 5])
                    if l0 >= 0 and l1 >= 0 and l2 >= 0 and l3 >= 0:
                        var low = (l0 << 12) | (l1 << 8) | (l2 << 4) | l3
                        if low >= 0xDC00 and low <= 0xDFFF:
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (low - 0xDC00)
                            i += 6
            _append_code_point(out, cp)
            continue

        if next == _QUOTE:
            out.append(_QUOTE)
        elif next == _BACKSLASH:
            out.append(_BACKSLASH)
        elif next == _SLASH:
            out.append(_SLASH)
        elif next == _LOWER_N:
            out.append(UInt8(10))
        elif next == _LOWER_T:
            out.append(UInt8(9))
        elif next == _LOWER_R:
            out.append(UInt8(13))
        elif next == _LOWER_B:
            out.append(UInt8(8))
        elif next == _LOWER_F:
            out.append(UInt8(12))
        else:
            raise Error(
                "canonical.from_json: invalid string escape (byte " + String(Int(next)) + ")"
            )
        i += 2
    return _string_from_utf8(out)


fn _looks_integer(token: String) -> Bool:
    """True when a number token has no fractional or exponent part."""
    var bytes = token.as_bytes()
    for i in range(len(token)):
        if bytes[i] == _DOT or bytes[i] == _UPPER_E or bytes[i] == _LOWER_E:
            return False
    return True


fn _is_number_token(token: String) -> Bool:
    """True only for a syntactically plausible JSON number.

    Needed because the alternative is failing open: without it a stray token like
    `a` parses as 0, so two different malformed documents encode identically and
    hash the same. A canonical encoder that silently agrees on garbage is worse than
    one that refuses it.
    """
    if len(token) == 0:
        return False
    var bytes = token.as_bytes()
    var i = 0
    if bytes[0] == _MINUS:
        i = 1
    if i >= len(token):
        return False
    var digits = 0
    while i < len(token):
        var c = bytes[i]
        if c >= _ZERO and c <= _NINE:
            digits += 1
        elif c == _DOT or c == _UPPER_E or c == _LOWER_E or c == _MINUS or c == 43:
            pass  # '+' is 43; exponent signs are permitted
        else:
            return False
        i += 1
    return digits > 0


fn _parse_int_token(token: String) raises -> Int:
    if not _is_number_token(token):
        raise Error("canonical.from_json: not a JSON number: " + token)
    var bytes = token.as_bytes()
    var negative = False
    var value = 0
    var i = 0
    if bytes[0] == _MINUS:
        negative = True
        i = 1
    while i < len(token):
        if bytes[i] < _ZERO or bytes[i] > _NINE:
            break
        value = value * 10 + Int(bytes[i] - _ZERO)
        i += 1
    return -value if negative else value


fn _parse_float_token(token: String) raises -> Float64:
    if not _is_number_token(token):
        raise Error("canonical.from_json: not a JSON number: " + token)
    return Float64(token)


fn transcode(json_text: String) raises -> List[UInt8]:
    """Canonical bytes for a JSON document, independent of its text form."""
    var out = List[UInt8]()
    var start = skip_whitespace(json_text, 0)
    _ = _write_value(json_text, start, out, 0)
    return out^


fn _write_value(
    data: String,
    start: Int,
    mut out: List[UInt8],
    depth: Int,
) raises -> Int:
    """Encode the value at `start`; returns the index just past it."""
    if depth > MAX_JSON_DEPTH:
        raise Error("canonical.from_json: nesting deeper than " + String(MAX_JSON_DEPTH))

    var pos = skip_whitespace(data, start)
    if pos >= len(data):
        raise Error("canonical.from_json: unexpected end of input")
    var bytes = data.as_bytes()
    var first = bytes[pos]

    if first == _BRACE_OPEN:
        return _write_object(data, pos, out, depth)
    if first == _BRACKET_OPEN:
        return _write_array(data, pos, out, depth)

    var end = skip_json_value(data, pos)

    if first == _QUOTE:
        write_string(out, _decode_string_token(data, pos, end))
        return end

    var token = _slice(data, pos, end)

    if first == _T or first == _F or first == _N:
        # The literal must be spelled out in full. `skip_json_value` returns `pos + 4`
        # for anything starting with `t` without looking, so without this check `[t]`,
        # `[tr]` and `[true]` all encode as `true` and share one hash — and the token
        # only exists at all because `_slice` clamps the overshoot instead of crashing.
        if token == "true":
            write_bool(out, True)
        elif token == "false":
            write_bool(out, False)
        elif token == "null":
            write_null(out)
        else:
            raise Error("canonical.from_json: not a JSON literal: " + token)
        return end

    if _looks_integer(token):
        write_int(out, _parse_int_token(token))
    else:
        write_float(out, _parse_float_token(token))
    return end


fn _write_array(
    data: String,
    start: Int,
    mut out: List[UInt8],
    depth: Int,
) raises -> Int:
    # Two passes: count first, because the canonical header is length-prefixed and
    # nothing may be emitted before the count is known.
    var bytes = data.as_bytes()
    var pos = skip_whitespace(data, start + 1)
    var count = 0
    var scan = pos
    while scan < len(data) and bytes[scan] != _BRACKET_CLOSE:
        scan = skip_json_value(data, skip_whitespace(data, scan))
        count += 1
        scan = skip_whitespace(data, scan)
        if scan < len(data) and bytes[scan] == _COMMA:
            scan = skip_whitespace(data, scan + 1)
    write_array_header(out, count)

    var cursor = pos
    for _ in range(count):
        cursor = _write_value(data, cursor, out, depth + 1)
        cursor = skip_whitespace(data, cursor)
        if cursor < len(data) and bytes[cursor] == _COMMA:
            cursor = skip_whitespace(data, cursor + 1)
    return skip_json_value(data, start)


fn _write_object(
    data: String,
    start: Int,
    mut out: List[UInt8],
    depth: Int,
) raises -> Int:
    """Collect key/value spans, sort by key, then emit — order is canonical."""
    var bytes = data.as_bytes()
    var keys = List[String]()
    var value_starts = List[Int]()

    var scan = skip_whitespace(data, start + 1)
    while scan < len(data) and bytes[scan] != _BRACE_CLOSE:
        var key_end = skip_json_value(data, scan)
        # A non-string key raises here rather than being read as bare text: `{a:1}` is
        # not JSON, and giving it a canonical form would make it collide with `{"a":1}`.
        keys.append(_decode_string_token(data, scan, key_end))
        var after = skip_whitespace(data, key_end)
        if after < len(data) and bytes[after] == _COLON:
            after = skip_whitespace(data, after + 1)
        value_starts.append(after)
        scan = skip_whitespace(data, skip_json_value(data, after))
        if scan < len(data) and bytes[scan] == _COMMA:
            scan = skip_whitespace(data, scan + 1)

    write_object_header(out, len(keys))

    # Selection sort over indices: key counts are small, and this keeps each key
    # paired with its value span without needing a tuple type.
    var order = List[Int]()
    for i in range(len(keys)):
        order.append(i)
    for i in range(len(order)):
        var best = i
        for j in range(i + 1, len(order)):
            if byte_order_less(keys[order[j]], keys[order[best]]):
                best = j
        if best != i:
            var swap = order[i]
            order[i] = order[best]
            order[best] = swap

    for i in range(len(order)):
        var index = order[i]
        write_string(out, keys[index])
        _ = _write_value(data, value_starts[index], out, depth + 1)

    return skip_json_value(data, start)
