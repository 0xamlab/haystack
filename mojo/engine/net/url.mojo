"""
url.mojo — URL parsing and construction. Zero Python imports.

Replaces Python's urllib.parse with pure Mojo implementations.

Public API:
  struct URL        — parsed URL components
  fn url_parse()    — parse a URL string into components
  fn url_to_string()— reconstruct URL from components
  fn url_encode()   — percent-encode a string
  fn url_decode()   — decode percent-encoded string
  fn query_parse()  — parse query string into key/value pairs
  fn query_get()    — get value from query string by key
  fn query_build()  — build query string from key/value pairs
"""


# ── Byte helpers ─────────────────────────────────────────────────────────────


@always_inline
fn _is_alpha(c: UInt8) -> Bool:
    return (c >= 65 and c <= 90) or (c >= 97 and c <= 122)


@always_inline
fn _is_digit(c: UInt8) -> Bool:
    return c >= 48 and c <= 57


@always_inline
fn _is_alnum(c: UInt8) -> Bool:
    return _is_alpha(c) or _is_digit(c)


@always_inline
fn _is_unreserved(c: UInt8) -> Bool:
    """RFC 3986 unreserved characters: A-Z a-z 0-9 - . _ ~"""
    return _is_alnum(c) or c == 45 or c == 46 or c == 95 or c == 126


fn _hex_digit(val: Int) -> String:
    """Convert 0-15 to hex character."""
    if val < 10:
        return chr(48 + val)
    return chr(65 + val - 10)


fn _hex_val(c: UInt8) -> Int:
    """Convert hex char to value. Returns -1 if invalid."""
    var ci = Int(c)
    if ci >= 48 and ci <= 57:
        return ci - 48
    if ci >= 65 and ci <= 70:
        return ci - 65 + 10
    if ci >= 97 and ci <= 102:
        return ci - 97 + 10
    return -1


fn _int_to_string(val: Int) -> String:
    """Convert non-negative integer to string."""
    if val == 0:
        return String("0")
    var result = String("")
    var v = val
    while v > 0:
        result = chr(48 + v % 10) + result
        v = v // 10
    return result


fn _string_to_int(s: String) -> Int:
    """Parse non-negative integer from string. Returns 0 on failure."""
    var bs = s.as_bytes()
    var n = len(s)
    var result = 0
    for i in range(n):
        var c = Int(bs[i])
        if c >= 48 and c <= 57:
            result = result * 10 + (c - 48)
        else:
            break
    return result


fn _substr(s: String, start: Int, end: Int) -> String:
    """Extract substring from start (inclusive) to end (exclusive)."""
    var bs = s.as_bytes()
    var n = len(s)
    var e = end
    if e > n:
        e = n
    var st = start
    if st < 0:
        st = 0
    var result = String("")
    for i in range(st, e):
        result += chr(Int(bs[i]))
    return result


fn _find(s: String, needle: String, start: Int) -> Int:
    """Find first occurrence of needle in s starting from start. Returns -1 if not found."""
    var s_len = len(s)
    var n_len = len(needle)
    if n_len == 0:
        return start
    if start + n_len > s_len:
        return -1
    var s_bytes = s.as_bytes()
    var n_bytes = needle.as_bytes()
    for i in range(start, s_len - n_len + 1):
        var found = True
        for j in range(n_len):
            if s_bytes[i + j] != n_bytes[j]:
                found = False
                break
        if found:
            return i
    return -1


fn _find_char(s: String, ch: UInt8, start: Int) -> Int:
    """Find first occurrence of a single byte in s. Returns -1 if not found."""
    var bs = s.as_bytes()
    var n = len(s)
    for i in range(start, n):
        if bs[i] == ch:
            return i
    return -1


# ── URL struct ───────────────────────────────────────────────────────────────


@fieldwise_init
struct URL(Copyable, Movable):
    """Parsed URL components."""
    var scheme: String      # "https"
    var host: String        # "api.algenta.ai"
    var port: Int           # 443 (0 = default/unspecified)
    var path: String        # "/v1/simulate"
    var query: String       # "mode=auto&runs=10000"
    var fragment: String    # ""

    fn __init__(out self):
        self.scheme = String("")
        self.host = String("")
        self.port = 0
        self.path = String("")
        self.query = String("")
        self.fragment = String("")


# ── url_parse ────────────────────────────────────────────────────────────────


fn url_parse(raw: String) -> URL:
    """Parse a URL string into components.

    Handles: scheme://host[:port][/path][?query][#fragment]
    """
    var u = URL()
    var s = raw
    var total = len(s)

    # ── Extract scheme ──
    var pos = 0
    var colon_slash = _find(s, "://", 0)
    if colon_slash >= 0:
        u.scheme = _substr(s, 0, colon_slash)
        pos = colon_slash + 3

    # ── Extract fragment (from the end) ──
    var hash_pos = _find_char(s, UInt8(35), pos)  # '#'
    var working_end = total
    if hash_pos >= 0:
        u.fragment = _substr(s, hash_pos + 1, total)
        working_end = hash_pos

    # ── Extract query (from the end of working string) ──
    var q_pos = _find_char(s, UInt8(63), pos)  # '?'
    if q_pos >= 0 and q_pos < working_end:
        u.query = _substr(s, q_pos + 1, working_end)
        working_end = q_pos

    # ── Extract path ──
    var slash_pos = _find_char(s, UInt8(47), pos)  # '/'
    if slash_pos >= 0 and slash_pos < working_end:
        u.path = _substr(s, slash_pos, working_end)
        working_end = slash_pos
    else:
        u.path = String("")

    # ── Extract host and port ──
    var authority = _substr(s, pos, working_end)
    var auth_len = len(authority)

    if auth_len > 0:
        # Check for port (last colon)
        var auth_bs = authority.as_bytes()
        var colon_pos = -1
        for i in range(auth_len):
            if auth_bs[i] == UInt8(58):  # ':'
                colon_pos = i
        if colon_pos >= 0:
            u.host = _substr(authority, 0, colon_pos)
            var port_str = _substr(authority, colon_pos + 1, auth_len)
            u.port = _string_to_int(port_str)
        else:
            u.host = authority

    return u^


# ── url_to_string ────────────────────────────────────────────────────────────


fn url_to_string(u: URL) -> String:
    """Reconstruct URL from components."""
    var result = String("")

    if len(u.scheme) > 0:
        result += u.scheme
        result += "://"

    result += u.host

    if u.port > 0:
        result += ":"
        result += _int_to_string(u.port)

    result += u.path

    if len(u.query) > 0:
        result += "?"
        result += u.query

    if len(u.fragment) > 0:
        result += "#"
        result += u.fragment

    return result


# ── url_encode ───────────────────────────────────────────────────────────────


fn url_encode(s: String) -> String:
    """Percent-encode a string for URL use.
    Encodes non-unreserved chars as %XX (uppercase hex).
    """
    var bs = s.as_bytes()
    var n = len(s)
    var result = String("")
    for i in range(n):
        var c = bs[i]
        if _is_unreserved(c):
            result += chr(Int(c))
        else:
            result += "%"
            result += _hex_digit(Int(c) >> 4)
            result += _hex_digit(Int(c) & 0x0F)
    return result


# ── url_decode ───────────────────────────────────────────────────────────────


fn url_decode(s: String) -> String:
    """Decode percent-encoded string. %XX → byte, + → space."""
    var bs = s.as_bytes()
    var n = len(s)
    var result = String("")
    var i = 0
    while i < n:
        if bs[i] == UInt8(37) and i + 2 < n:  # '%'
            var hi = _hex_val(bs[i + 1])
            var lo = _hex_val(bs[i + 2])
            if hi >= 0 and lo >= 0:
                result += chr(hi * 16 + lo)
                i += 3
                continue
        if bs[i] == UInt8(43):  # '+'
            result += " "
        else:
            result += chr(Int(bs[i]))
        i += 1
    return result


# ── query_parse ──────────────────────────────────────────────────────────────


fn query_parse(query: String) -> List[List[String]]:
    """Parse query string "key1=val1&key2=val2" into list of [key, value] pairs."""
    var result = List[List[String]]()
    var q_len = len(query)
    if q_len == 0:
        return result^

    var start = 0

    while start < q_len:
        # Find next '&'
        var amp_pos = _find_char(query, UInt8(38), start)  # '&'
        var end = amp_pos
        if end < 0:
            end = q_len

        var pair_str = _substr(query, start, end)
        var eq_pos = _find_char(pair_str, UInt8(61), 0)  # '='

        var pair = List[String]()
        if eq_pos >= 0:
            pair.append(_substr(pair_str, 0, eq_pos))
            pair.append(_substr(pair_str, eq_pos + 1, len(pair_str)))
        else:
            pair.append(pair_str)
            pair.append(String(""))
        result.append(pair^)

        if amp_pos < 0:
            break
        start = amp_pos + 1

    return result^


# ── query_get ────────────────────────────────────────────────────────────────


fn query_get(query: String, key: String) -> String:
    """Get a value from a query string by key. Returns "" if not found."""
    var pairs = query_parse(query)
    var n = len(pairs)
    for i in range(n):
        if len(pairs[i]) >= 2 and pairs[i][0] == key:
            return pairs[i][1]
    return String("")


# ── query_build ──────────────────────────────────────────────────────────────


fn query_build(params: List[List[String]]) -> String:
    """Build query string from list of [key, value] pairs."""
    var n = len(params)
    var result = String("")
    for i in range(n):
        if i > 0:
            result += "&"
        if len(params[i]) >= 1:
            result += params[i][0]
        if len(params[i]) >= 2:
            result += "="
            result += params[i][1]
    return result
