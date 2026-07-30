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

# Depth bound: a deeply nested payload would otherwise recurse without limit.
comptime MAX_JSON_DEPTH: Int = 64


fn _slice(data: String, start: Int, end: Int) -> String:
    var bytes = data.as_bytes()
    var out = String("")
    for i in range(start, end):
        out += chr(Int(bytes[i]))
    return out


fn _unquote(token: String) -> String:
    """Decode a JSON string token's contents, handling the standard escapes."""
    var bytes = token.as_bytes()
    var out = String("")
    var i = 1  # skip the opening quote
    var limit = len(token) - 1
    while i < limit:
        if bytes[i] == 92 and i + 1 < limit:  # backslash
            var next = bytes[i + 1]
            if next == 110:
                out += "\n"
            elif next == 116:
                out += "\t"
            elif next == 114:
                out += "\r"
            elif next == 98:
                out += chr(8)
            elif next == 102:
                out += chr(12)
            else:
                # Covers \" \\ \/ and anything else: emit the escaped byte itself.
                out += chr(Int(next))
            i += 2
            continue
        out += chr(Int(bytes[i]))
        i += 1
    return out


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
    var token = _slice(data, pos, end)

    if first == _QUOTE:
        write_string(out, _unquote(token))
    elif first == _T:
        write_bool(out, True)
    elif first == _F:
        write_bool(out, False)
    elif first == _N:
        write_null(out)
    elif _looks_integer(token):
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
        keys.append(_unquote(_slice(data, scan, key_end)))
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
