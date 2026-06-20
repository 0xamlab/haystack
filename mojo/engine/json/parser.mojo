"""
json/parser.mojo — Schema-aware JSON field extraction. Zero Python imports.

Extracts known fields directly from raw JSON byte streams without building
intermediate DOM nodes. Designed for the Codna request schema but usable
for any JSON object field extraction.

Strategy:
  1. find_key() scans a JSON object byte-by-byte for a "key": pattern at
     the current nesting level, correctly skipping nested structures.
  2. skip_json_value() handles balanced bracket counting for objects/arrays,
     string escaping, and numeric/boolean/null literals.
  3. All json_get_* functions call find_key() then parse the value in place.

Public API:
  json_get_string(raw, key) -> String
  json_get_float(raw, key, default) -> Float64
  json_get_int(raw, key, default) -> Int
  json_get_bool(raw, key, default) -> Bool
  json_get_object(raw, key) -> String
  json_get_array(raw, key) -> String
  json_is_null(raw, key) -> Bool
  json_array_len(arr) -> Int
  json_array_get(arr, index) -> String

Internal helpers:
  skip_whitespace(data, pos) -> Int
  skip_json_value(data, pos) -> Int
  find_key(data, key) -> Int
"""

from conv import parse_float64, parse_int, is_whitespace


# ── ASCII byte constants ──────────────────────────────────────────────────────

comptime _QUOTE = UInt8(34)       # "
comptime _BACKSLASH = UInt8(92)   # backslash
comptime _LBRACE = UInt8(123)     # {
comptime _RBRACE = UInt8(125)     # }
comptime _LBRACKET = UInt8(91)    # [
comptime _RBRACKET = UInt8(93)    # ]
comptime _COLON = UInt8(58)       # :
comptime _COMMA = UInt8(44)       # ,
comptime _MINUS = UInt8(45)       # -
comptime _DOT = UInt8(46)         # .
comptime _CHAR_T = UInt8(116)     # t
comptime _CHAR_F = UInt8(102)     # f
comptime _CHAR_N = UInt8(110)     # n
comptime _CHAR_E = UInt8(101)     # e (scientific notation)
comptime _CHAR_E_UP = UInt8(69)   # E
comptime _CHAR_PLUS = UInt8(43)   # +
comptime _DIGIT_0 = UInt8(48)     # 0
comptime _DIGIT_9 = UInt8(57)     # 9
comptime _AT = UInt8(64)          # @  (binary-buffer arg marker, e.g. "@u8:<base64>")
comptime _CHAR_U = UInt8(117)     # u
comptime _CHAR_8 = UInt8(56)      # 8
comptime _SLASH = UInt8(47)       # /
comptime _EQUALS = UInt8(61)      # =


# ── Whitespace skipping ──────────────────────────────────────────────────────


@always_inline
fn skip_whitespace(data: String, pos: Int) -> Int:
    """Advance pos past whitespace chars."""
    var bytes = data.as_bytes()
    var n = len(data)
    var p = pos
    while p < n and is_whitespace(bytes[p]):
        p += 1
    return p


# ── Skip a complete JSON value ───────────────────────────────────────────────


fn skip_json_value(data: String, pos: Int) -> Int:
    """Advance pos past a complete JSON value (string, number, object, array, bool, null).

    Handles:
    - Strings: scans to closing unescaped quote
    - Objects/Arrays: balanced bracket counting, respects strings inside
    - Numbers: scans digits, dots, signs, exponents
    - Literals: true, false, null
    """
    var bytes = data.as_bytes()
    var n = len(data)
    var p = skip_whitespace(data, pos)

    if p >= n:
        return p

    var ch = bytes[p]

    # ── String ──
    if ch == _QUOTE:
        p += 1  # skip opening "
        while p < n:
            if bytes[p] == _BACKSLASH:
                p += 2  # skip escaped char
                continue
            if bytes[p] == _QUOTE:
                p += 1  # skip closing "
                return p
            p += 1
        return p  # unterminated string — return end

    # ── Object ──
    if ch == _LBRACE:
        p += 1
        var depth = 1
        while p < n and depth > 0:
            var c = bytes[p]
            if c == _QUOTE:
                # Skip entire string (may contain braces)
                p += 1
                while p < n:
                    if bytes[p] == _BACKSLASH:
                        p += 2
                        continue
                    if bytes[p] == _QUOTE:
                        p += 1
                        break
                    p += 1
                continue
            if c == _LBRACE:
                depth += 1
            elif c == _RBRACE:
                depth -= 1
            p += 1
        return p

    # ── Array ──
    if ch == _LBRACKET:
        p += 1
        var depth = 1
        while p < n and depth > 0:
            var c = bytes[p]
            if c == _QUOTE:
                # Skip entire string (may contain brackets)
                p += 1
                while p < n:
                    if bytes[p] == _BACKSLASH:
                        p += 2
                        continue
                    if bytes[p] == _QUOTE:
                        p += 1
                        break
                    p += 1
                continue
            if c == _LBRACKET:
                depth += 1
            elif c == _RBRACKET:
                depth -= 1
            p += 1
        return p

    # ── true ──
    if ch == _CHAR_T:
        return p + 4  # "true"

    # ── false ──
    if ch == _CHAR_F:
        return p + 5  # "false"

    # ── null ──
    if ch == _CHAR_N:
        return p + 4  # "null"

    # ── Number (digits, minus, dot, e/E, +) ──
    if ch == _MINUS or (ch >= _DIGIT_0 and ch <= _DIGIT_9):
        p += 1
        while p < n:
            var c = bytes[p]
            if (
                (c >= _DIGIT_0 and c <= _DIGIT_9)
                or c == _DOT
                or c == _CHAR_E
                or c == _CHAR_E_UP
                or c == _MINUS
                or c == _CHAR_PLUS
            ):
                p += 1
            else:
                break
        return p

    # Unknown — advance one to avoid infinite loop
    return p + 1


# ── Find a key's value position in a JSON object ────────────────────────────


fn find_key(data: String, key: String) -> Int:
    """Find the position of the value for 'key' in a JSON object.
    Returns -1 if not found.

    Correctly handles:
    - Nested objects (skips them when scanning for top-level keys)
    - Nested arrays
    - Escaped quotes in strings
    - Keys appearing inside nested string values
    """
    var bytes = data.as_bytes()
    var n = len(data)
    var key_bytes = key.as_bytes()
    var key_len = len(key)

    # Find opening brace
    var p = skip_whitespace(data, 0)
    if p >= n or bytes[p] != _LBRACE:
        return -1
    p += 1

    while p < n:
        p = skip_whitespace(data, p)
        if p >= n:
            return -1

        # End of object
        if bytes[p] == _RBRACE:
            return -1

        # Skip comma between entries
        if bytes[p] == _COMMA:
            p += 1
            p = skip_whitespace(data, p)

        # Expect a quoted string key
        if p >= n or bytes[p] != _QUOTE:
            return -1

        # ── Read key string and compare ──
        p += 1  # skip opening "
        var key_start = p
        while p < n:
            if bytes[p] == _BACKSLASH:
                p += 2
                continue
            if bytes[p] == _QUOTE:
                break
            p += 1
        var key_end = p
        p += 1  # skip closing "

        # Compare key bytes
        var found = (key_end - key_start) == key_len
        if found:
            for i in range(key_len):
                if bytes[key_start + i] != key_bytes[i]:
                    found = False
                    break

        # Skip whitespace + colon + whitespace
        p = skip_whitespace(data, p)
        if p >= n or bytes[p] != _COLON:
            return -1
        p += 1
        p = skip_whitespace(data, p)

        if found:
            return p  # position of the value

        # Skip this value — not our key
        p = skip_json_value(data, p)

    return -1


# ── String extraction ─────────────────────────────────────────────────────────


fn json_get_string(raw: String, key: String) -> String:
    """Extract a string value for the given key. Returns "" if not found."""
    var pos = find_key(raw, key)
    if pos < 0:
        return String("")

    var bytes = raw.as_bytes()
    var n = len(raw)

    if pos >= n or bytes[pos] != _QUOTE:
        return String("")

    pos += 1  # skip opening "
    var result = String("")
    while pos < n:
        if bytes[pos] == _BACKSLASH and pos + 1 < n:
            # Handle escape sequences
            var next_ch = bytes[pos + 1]
            if next_ch == _QUOTE:
                result += '"'
            elif next_ch == _BACKSLASH:
                result += "\\"
            elif next_ch == UInt8(110):  # \n
                result += "\n"
            elif next_ch == UInt8(116):  # \t
                result += "\t"
            elif next_ch == UInt8(114):  # \r
                result += "\r"
            elif next_ch == UInt8(47):  # \/
                result += "/"
            else:
                result += chr(Int(next_ch))
            pos += 2
            continue
        if bytes[pos] == _QUOTE:
            break
        result += chr(Int(bytes[pos]))
        pos += 1

    return result


# ── Internal: extract raw number string at position ──────────────────────────


@always_inline
fn _extract_number_str(raw: String, pos: Int) -> String:
    """Extract the raw number string starting at pos (up to delimiter)."""
    var bytes = raw.as_bytes()
    var n = len(raw)
    var p = pos
    while p < n:
        var c = bytes[p]
        if c == _COMMA or c == _RBRACE or c == _RBRACKET or is_whitespace(c):
            break
        p += 1
    # Build the substring
    var result = String("")
    for i in range(pos, p):
        result += chr(Int(bytes[i]))
    return result


# ── Float extraction ──────────────────────────────────────────────────────────


fn json_get_float(raw: String, key: String, default: Float64) -> Float64:
    """Extract a float/int value for the given key. Returns default if not found."""
    var pos = find_key(raw, key)
    if pos < 0:
        return default

    var bytes = raw.as_bytes()
    var n = len(raw)
    if pos >= n:
        return default

    # Check for null
    if bytes[pos] == _CHAR_N:
        return default

    var num_str = _extract_number_str(raw, pos)
    if len(num_str) == 0:
        return default
    return parse_float64(num_str)


# ── Int extraction ────────────────────────────────────────────────────────────


fn json_get_int(raw: String, key: String, default: Int) -> Int:
    """Extract an integer value for the given key. Returns default if not found."""
    var pos = find_key(raw, key)
    if pos < 0:
        return default

    var bytes = raw.as_bytes()
    var n = len(raw)
    if pos >= n:
        return default

    # Check for null
    if bytes[pos] == _CHAR_N:
        return default

    var num_str = _extract_number_str(raw, pos)
    if len(num_str) == 0:
        return default
    return parse_int(num_str)


# ── Boolean extraction ────────────────────────────────────────────────────────


fn json_get_bool(raw: String, key: String, default: Bool) -> Bool:
    """Extract a boolean value for the given key. Returns default if not found."""
    var pos = find_key(raw, key)
    if pos < 0:
        return default

    var bytes = raw.as_bytes()
    var n = len(raw)
    if pos >= n:
        return default

    if bytes[pos] == _CHAR_T:
        return True
    if bytes[pos] == _CHAR_F:
        return False
    return default


# ── Null check ────────────────────────────────────────────────────────────────


fn json_is_null(raw: String, key: String) -> Bool:
    """Check if a key's value is null or the key is absent."""
    var pos = find_key(raw, key)
    if pos < 0:
        return True  # key absent → treat as null

    var bytes = raw.as_bytes()
    var n = len(raw)
    if pos >= n:
        return True

    return bytes[pos] == _CHAR_N  # starts with 'n' → null


# ── Object extraction ────────────────────────────────────────────────────────


fn json_get_object(raw: String, key: String) -> String:
    """Extract a nested JSON object as raw string. Returns "" if not found."""
    var pos = find_key(raw, key)
    if pos < 0:
        return String("")

    var bytes = raw.as_bytes()
    var n = len(raw)
    if pos >= n or bytes[pos] != _LBRACE:
        return String("")

    var end = skip_json_value(raw, pos)

    # Build substring [pos, end)
    var result = String("")
    for i in range(pos, end):
        result += chr(Int(bytes[i]))
    return result


# ── Array extraction ──────────────────────────────────────────────────────────


fn json_get_array(raw: String, key: String) -> String:
    """Extract a JSON array as raw string. Returns "" if not found."""
    var pos = find_key(raw, key)
    if pos < 0:
        return String("")

    var bytes = raw.as_bytes()
    var n = len(raw)
    if pos >= n or bytes[pos] != _LBRACKET:
        return String("")

    var end = skip_json_value(raw, pos)

    # Build substring [pos, end)
    var result = String("")
    for i in range(pos, end):
        result += chr(Int(bytes[i]))
    return result


# ── Array length ──────────────────────────────────────────────────────────────


fn json_array_len(arr: String) -> Int:
    """Count elements in a JSON array string like "[1,2,3]"."""
    var bytes = arr.as_bytes()
    var n = len(arr)

    var p = skip_whitespace(arr, 0)
    if p >= n or bytes[p] != _LBRACKET:
        return 0
    p += 1
    p = skip_whitespace(arr, p)

    # Empty array
    if p < n and bytes[p] == _RBRACKET:
        return 0

    var count = 0
    while p < n:
        p = skip_whitespace(arr, p)
        if p >= n or bytes[p] == _RBRACKET:
            break

        count += 1
        p = skip_json_value(arr, p)
        p = skip_whitespace(arr, p)

        if p < n and bytes[p] == _COMMA:
            p += 1

    return count


# ── Array element access ──────────────────────────────────────────────────────


fn json_array_get(arr: String, index: Int) -> String:
    """Get element at index from a JSON array. Returns raw element string."""
    var bytes = arr.as_bytes()
    var n = len(arr)

    var p = skip_whitespace(arr, 0)
    if p >= n or bytes[p] != _LBRACKET:
        return String("")
    p += 1

    var current = 0
    while p < n:
        p = skip_whitespace(arr, p)
        if p >= n or bytes[p] == _RBRACKET:
            break

        if current == index:
            # Found our element — extract its raw text
            var start = p
            var end = skip_json_value(arr, p)
            var result = String("")
            for i in range(start, end):
                result += chr(Int(bytes[i]))
            return result

        # Skip this element
        p = skip_json_value(arr, p)
        p = skip_whitespace(arr, p)

        if p < n and bytes[p] == _COMMA:
            p += 1

        current += 1

    return String("")


# ── Single-pass array tokenizer (O(n), replaces per-index json_array_get) ───────


fn json_array_tokens(arr: String) raises -> List[String]:
    """Split a JSON array string into its raw element strings in ONE pass — O(n) total.

    The old pattern `for i in range(json_array_len(arr)): json_array_get(arr, i)` re-scans
    the array from position 0 on every index, so parsing an n-element array is O(n^2)
    (e.g. ~6 s for a 39k-element pixel buffer). This walks the array once instead.
    """
    var bytes = arr.as_bytes()
    var n = len(arr)
    var result = List[String]()

    var p = skip_whitespace(arr, 0)
    if p >= n or bytes[p] != _LBRACKET:
        return result^
    p += 1

    while p < n:
        p = skip_whitespace(arr, p)
        if p >= n or bytes[p] == _RBRACKET:
            break
        var start = p
        var end = skip_json_value(arr, p)
        var elem = String("")
        for i in range(start, end):
            elem += chr(Int(bytes[i]))
        result.append(elem)
        p = skip_whitespace(arr, end)
        if p < n and bytes[p] == _COMMA:
            p += 1

    return result^


# ── Binary buffer decode (base64) for bulk numeric args ─────────────────────────


@always_inline
fn _b64_sextet(c: UInt8) -> Int:
    """Base64 alphabet → 6-bit value; -1 for padding/whitespace/invalid (skipped)."""
    if c >= UInt8(65) and c <= UInt8(90):      # A-Z
        return Int(c) - 65
    if c >= UInt8(97) and c <= UInt8(122):     # a-z
        return Int(c) - 97 + 26
    if c >= _DIGIT_0 and c <= _DIGIT_9:        # 0-9
        return Int(c) - 48 + 52
    if c == _CHAR_PLUS:                        # +
        return 62
    if c == _SLASH:                            # /
        return 63
    return -1                                  # '=', whitespace, anything else → skip


fn json_decode_base64_bytes(s: String) -> List[UInt8]:
    """Standard base64 → raw bytes, single pass O(n). Non-alphabet chars are skipped."""
    var bytes = s.as_bytes()
    var n = len(s)
    var out = List[UInt8]()
    var acc: Int = 0
    var nbits: Int = 0
    for i in range(n):
        var v = _b64_sextet(bytes[i])
        if v < 0:
            continue
        acc = (acc << 6) | v
        nbits += 6
        if nbits >= 8:
            nbits -= 8
            out.append(UInt8((acc >> nbits) & 0xFF))
    return out^


fn json_parse_float64_list(token: String) raises -> List[Float64]:
    """Parse a `List[Float64]` arg with a binary fast path.

    A JSON-string token of the form `"@u8:<base64>"` is decoded as raw uint8 bytes (pixel
    values 0-255) in one O(n) pass — no per-element text parsing. Any other token falls back
    to a single-pass JSON-array parse. This is the hot path for image kernels, where the arg
    is a flat pixel buffer; shipping it as a u8 buffer is ~13x smaller than JSON text and
    avoids the float tokenizer entirely.
    """
    var bytes = token.as_bytes()
    var n = len(token)
    var p = skip_whitespace(token, 0)
    if p < n and bytes[p] == _QUOTE:
        # JSON string token → look for the "@u8:" binary-buffer marker.
        var start = p + 1
        var q = start
        while q < n and bytes[q] != _QUOTE:
            q += 1
        if (
            q - start >= 4
            and bytes[start] == _AT
            and bytes[start + 1] == _CHAR_U
            and bytes[start + 2] == _CHAR_8
            and bytes[start + 3] == _COLON
        ):
            var b64 = String("")
            for i in range(start + 4, q):
                b64 += chr(Int(bytes[i]))
            var raw = json_decode_base64_bytes(b64)
            var out = List[Float64]()
            for i in range(len(raw)):
                out.append(Float64(Int(raw[i])))
            return out^

    # Array path — single pass (O(n)), not the old per-index re-scan.
    var wrapped = "{\"v\":" + token + "}"
    var array_json = json_get_array(wrapped, "v")
    var tokens = json_array_tokens(array_json)
    var result = List[Float64]()
    for i in range(len(tokens)):
        result.append(parse_float64(tokens[i]))
    return result^
