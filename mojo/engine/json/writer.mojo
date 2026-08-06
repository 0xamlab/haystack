"""
json/writer.mojo — Pure Mojo JSON serializer/writer. Zero Python imports.

Complements json/parser.mojo (reader). Builds JSON strings from Mojo types
using a functional builder pattern: start with json_object_start(), chain
json_add_* calls, and finish with json_object_end().

Public API:
  json_object_start() -> String
  json_object_end(s: String) -> String
  json_add_string(s, key, value) -> String
  json_add_int(s, key, value) -> String
  json_add_float(s, key, value) -> String
  json_add_bool(s, key, value) -> String
  json_add_null(s, key) -> String
  json_add_array_float(s, key, values) -> String
  json_add_array_string(s, key, values) -> String
  json_add_raw(s, key, raw_json) -> String
  json_escape_string(s) -> String
  json_build_object(pairs: List[List[String]]) -> String
"""

from conv import float_to_string


# ── JSON escape ──────────────────────────────────────────────────────────────


def json_escape_string(s: String) -> String:
    """Escape special characters for JSON string values.

    Handles: \\ \" \\n \\r \\t \\b \\f and control chars < 0x20.
    """
    var result = String("")
    var bytes = s.as_bytes()
    var n = len(s)
    for i in range(n):
        var c = bytes[i]
        if c == UInt8(34):  # "
            result += '\\"'
        elif c == UInt8(92):  # backslash
            result += "\\\\"
        elif c == UInt8(10):  # \n
            result += "\\n"
        elif c == UInt8(13):  # \r
            result += "\\r"
        elif c == UInt8(9):  # \t
            result += "\\t"
        elif c == UInt8(8):  # \b
            result += "\\b"
        elif c == UInt8(12):  # \f
            result += "\\f"
        elif c < UInt8(32):
            # Control character — emit as \\u00XX
            var hi = Int(c) >> 4
            var lo = Int(c) & 0x0F
            result += "\\u00"
            result += _hex_digit(hi)
            result += _hex_digit(lo)
        else:
            result += chr(Int(c))
    return result


@always_inline
def _hex_digit(v: Int) -> String:
    """Convert 0-15 to hex digit character."""
    if v < 10:
        return chr(48 + v)  # '0' + v
    return chr(97 + v - 10)  # 'a' + (v - 10)


# ── Quoted key/value helpers ─────────────────────────────────────────────────


@always_inline
def _quoted(s: String) -> String:
    """Wrap string in double quotes with JSON escaping."""
    return '"' + json_escape_string(s) + '"'


@always_inline
def _key_prefix(key: String) -> String:
    """Return '"key":' prefix for a JSON field."""
    return '"' + json_escape_string(key) + '":'


# ── Object start/end ────────────────────────────────────────────────────────


def json_object_start() -> String:
    """Start a JSON object. Returns '{'."""
    return String("{")


def json_object_end(s: String) -> String:
    """Close a JSON object. Removes trailing comma if present, appends '}'.

    Args:
        s: The in-progress JSON string (should start with '{').

    Returns:
        Complete JSON object string.
    """
    var n = len(s)
    if n > 0:
        var bytes = s.as_bytes()
        # Check if last char is a comma
        if bytes[n - 1] == UInt8(44):  # ','
            # Strip trailing comma
            var result = String("")
            for i in range(n - 1):
                result += chr(Int(bytes[i]))
            return result + "}"
    return s + "}"


# ── Add typed fields ────────────────────────────────────────────────────────


def json_add_string(s: String, key: String, value: String) -> String:
    """Add a string field: "key":"value","""
    return s + _key_prefix(key) + _quoted(value) + ","


def json_add_int(s: String, key: String, value: Int) -> String:
    """Add an integer field: "key":123,"""
    return s + _key_prefix(key) + String(value) + ","


def json_add_float(s: String, key: String, value: Float64) -> String:
    """Add a float field: "key":1.23,"""
    return s + _key_prefix(key) + float_to_string(value) + ","


def json_add_bool(s: String, key: String, value: Bool) -> String:
    """Add a boolean field: "key":true or "key":false,"""
    var val_str: String
    if value:
        val_str = "true"
    else:
        val_str = "false"
    return s + _key_prefix(key) + val_str + ","


def json_add_null(s: String, key: String) -> String:
    """Add a null field: "key":null,"""
    return s + _key_prefix(key) + "null,"


# ── Add array fields ────────────────────────────────────────────────────────


def json_add_array_float(s: String, key: String, values: List[Float64]) -> String:
    """Add a float array field: "key":[1.0,2.0,3.0],"""
    var arr = String("[")
    for i in range(len(values)):
        if i > 0:
            arr += ","
        arr += float_to_string(values[i])
    arr += "]"
    return s + _key_prefix(key) + arr + ","


def json_add_array_string(s: String, key: String, values: List[String]) -> String:
    """Add a string array field: "key":["a","b","c"],"""
    var arr = String("[")
    for i in range(len(values)):
        if i > 0:
            arr += ","
        arr += _quoted(values[i])
    arr += "]"
    return s + _key_prefix(key) + arr + ","


# ── Add raw JSON ────────────────────────────────────────────────────────────


def json_add_raw(s: String, key: String, raw_json: String) -> String:
    """Add a pre-built JSON value (object or array) as a field.

    The raw_json must already be valid JSON. No escaping is performed.

    Args:
        s: In-progress JSON string.
        key: Field name.
        raw_json: Pre-built JSON string (object, array, or literal).
    """
    return s + _key_prefix(key) + raw_json + ","


# ── Build object from pairs ─────────────────────────────────────────────────


def json_build_object(pairs: List[List[String]]) -> String:
    """Build a JSON object from key-value pairs.

    Each pair is a List[String] of length 2: [key, value].
    Values must be pre-formatted JSON values (quoted strings, numbers, etc.).

    Example:
        var pairs = List[List[String]]()
        var p1 = List[String](); p1.append("name"); p1.append('"Codna"')
        pairs.append(p1)
        var obj = json_build_object(pairs)
        # -> '{"name":"Codna"}'
    """
    var result = String("{")
    for i in range(len(pairs)):
        if i > 0:
            result += ","
        var pair = pairs[i].copy()
        if len(pair) >= 2:
            result += '"' + json_escape_string(pair[0]) + '":'
            result += pair[1]
    result += "}"
    return result
