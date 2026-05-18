"""
pattern.mojo — Pattern matching & template utilities. Zero Python imports.

Replaces fnmatch glob matching and jinja2 basic template substitution
with pure Mojo implementations. Also provides common string operations
(split, join, trim, pad, replace, contains, count).

Public API:
  glob_match           — simple glob matching (* and ?)
  starts_with          — check prefix
  ends_with            — check suffix
  contains             — check substring presence
  count_occurrences    — count non-overlapping occurrences
  replace_all          — replace all occurrences
  template_substitute  — replace {{key}} with value
  split_string         — split by delimiter
  join_strings         — join with delimiter
  pad_left             — left-pad to width
  pad_right            — right-pad to width
  trim                 — remove leading/trailing whitespace
"""


# ── Byte helpers ─────────────────────────────────────────────────────────────


@always_inline
fn _is_ws(c: UInt8) -> Bool:
    return c == 32 or c == 9 or c == 10 or c == 13


# ── glob_match ───────────────────────────────────────────────────────────────


fn glob_match(pattern: String, text: String) -> Bool:
    """Simple glob matching: * matches any sequence, ? matches single char."""
    var pbs = pattern.as_bytes()
    var tbs = text.as_bytes()
    var plen = len(pattern)
    var tlen = len(text)
    var STAR = UInt8(ord("*"))
    var QMARK = UInt8(ord("?"))
    # dp[i][j] = pattern[:i] matches text[:j]
    var cols = tlen + 1
    var dp = List[Bool]()
    for _ in range((plen + 1) * cols):
        dp.append(False)
    dp[0] = True  # empty pattern matches empty text

    for i in range(1, plen + 1):
        if pbs[i - 1] == STAR:
            dp[i * cols] = dp[(i - 1) * cols]
        for j in range(1, tlen + 1):
            var pc = pbs[i - 1]
            if pc == STAR:
                dp[i * cols + j] = dp[(i - 1) * cols + j] or dp[i * cols + j - 1]
            elif pc == QMARK or pc == tbs[j - 1]:
                dp[i * cols + j] = dp[(i - 1) * cols + (j - 1)]
            else:
                dp[i * cols + j] = False
    return dp[plen * cols + tlen]


# ── starts_with ──────────────────────────────────────────────────────────────


fn starts_with(text: String, prefix: String) -> Bool:
    """Check if text starts with prefix."""
    var plen = len(prefix)
    if plen > len(text):
        return False
    var tbs = text.as_bytes()
    var pbs = prefix.as_bytes()
    for i in range(plen):
        if tbs[i] != pbs[i]:
            return False
    return True


# ── ends_with ────────────────────────────────────────────────────────────────


fn ends_with(text: String, suffix: String) -> Bool:
    """Check if text ends with suffix."""
    var slen = len(suffix)
    var tlen = len(text)
    if slen > tlen:
        return False
    var tbs = text.as_bytes()
    var sbs = suffix.as_bytes()
    var offset = tlen - slen
    for i in range(slen):
        if tbs[offset + i] != sbs[i]:
            return False
    return True


# ── contains ─────────────────────────────────────────────────────────────────


fn contains(text: String, sub: String) -> Bool:
    """Check if text contains substring."""
    var tlen = len(text)
    var slen = len(sub)
    if slen == 0:
        return True
    if slen > tlen:
        return False
    var tbs = text.as_bytes()
    var sbs = sub.as_bytes()
    for i in range(tlen - slen + 1):
        var found = True
        for j in range(slen):
            if tbs[i + j] != sbs[j]:
                found = False
                break
        if found:
            return True
    return False


# ── count_occurrences ────────────────────────────────────────────────────────


fn count_occurrences(text: String, sub: String) -> Int:
    """Count non-overlapping occurrences of sub in text."""
    var tlen = len(text)
    var slen = len(sub)
    if slen == 0:
        return 0
    var tbs = text.as_bytes()
    var sbs = sub.as_bytes()
    var count = 0
    var i = 0
    while i <= tlen - slen:
        var found = True
        for j in range(slen):
            if tbs[i + j] != sbs[j]:
                found = False
                break
        if found:
            count += 1
            i += slen
        else:
            i += 1
    return count


# ── replace_all ──────────────────────────────────────────────────────────────


fn replace_all(text: String, old: String, new: String) -> String:
    """Replace all non-overlapping occurrences of old with new."""
    var tlen = len(text)
    var olen = len(old)
    if olen == 0:
        return text
    var tbs = text.as_bytes()
    var obs = old.as_bytes()
    var result = String("")
    var i = 0
    while i < tlen:
        if i <= tlen - olen:
            var found = True
            for j in range(olen):
                if tbs[i + j] != obs[j]:
                    found = False
                    break
            if found:
                result += new
                i += olen
                continue
        result += chr(Int(tbs[i]))
        i += 1
    return result


# ── template_substitute ──────────────────────────────────────────────────────


fn template_substitute(
    template: String, keys: List[String], values: List[String]
) -> String:
    """Replace {{key}} placeholders with corresponding values."""
    var result = template
    var nk = len(keys)
    for i in range(nk):
        var placeholder = "{{" + keys[i] + "}}"
        result = replace_all(result, placeholder, values[i])
    return result


# ── split_string ─────────────────────────────────────────────────────────────


fn split_string(text: String, delimiter: String) -> List[String]:
    """Split text by delimiter. Returns list of parts."""
    var parts = List[String]()
    var tlen = len(text)
    var dlen = len(delimiter)
    if dlen == 0 or tlen == 0:
        parts.append(text)
        return parts^
    var tbs = text.as_bytes()
    var dbs = delimiter.as_bytes()
    var start = 0
    var i = 0
    while i <= tlen - dlen:
        var found = True
        for j in range(dlen):
            if tbs[i + j] != dbs[j]:
                found = False
                break
        if found:
            var part = String("")
            for k in range(start, i):
                part += chr(Int(tbs[k]))
            parts.append(part^)
            start = i + dlen
            i = start
        else:
            i += 1
    var tail = String("")
    for k in range(start, tlen):
        tail += chr(Int(tbs[k]))
    parts.append(tail^)
    return parts^


# ── join_strings ─────────────────────────────────────────────────────────────


fn join_strings(parts: List[String], delimiter: String) -> String:
    """Join strings with delimiter."""
    var n = len(parts)
    if n == 0:
        return String("")
    var result = parts[0]
    for i in range(1, n):
        result += delimiter
        result += parts[i]
    return result


# ── pad_left ─────────────────────────────────────────────────────────────────


fn pad_left(text: String, width: Int, fill_char: Int = 32) -> String:
    """Left-pad text to width with fill character (default space=32)."""
    var tlen = len(text)
    if tlen >= width:
        return text
    var pad_count = width - tlen
    var fc = chr(fill_char)
    var result = String("")
    for _ in range(pad_count):
        result += fc
    result += text
    return result


# ── pad_right ────────────────────────────────────────────────────────────────


fn pad_right(text: String, width: Int, fill_char: Int = 32) -> String:
    """Right-pad text to width with fill character (default space=32)."""
    var tlen = len(text)
    if tlen >= width:
        return text
    var pad_count = width - tlen
    var fc = chr(fill_char)
    var result = text
    for _ in range(pad_count):
        result += fc
    return result


# ── trim ─────────────────────────────────────────────────────────────────────


fn trim(text: String) -> String:
    """Remove leading and trailing whitespace (space, tab, newline, cr)."""
    var tlen = len(text)
    if tlen == 0:
        return text
    var bs = text.as_bytes()
    var start = 0
    while start < tlen and _is_ws(bs[start]):
        start += 1
    var end = tlen - 1
    while end >= start and _is_ws(bs[end]):
        end -= 1
    if start > end:
        return String("")
    var result = String("")
    for i in range(start, end + 1):
        result += chr(Int(bs[i]))
    return result
