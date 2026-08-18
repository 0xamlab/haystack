"""
string_utils.mojo — String processing utilities. Zero Python imports.

Replaces Python's str methods and textwrap with pure Mojo implementations.

Public API:
  str_split()        — split string by delimiter
  str_join()         — join list of strings with delimiter
  str_replace()      — replace all occurrences of old with new
  str_startswith()   — check if string starts with prefix
  str_endswith()     — check if string ends with suffix
  str_contains()     — check if string contains substring
  str_repeat()       — repeat string n times
  str_pad_left()     — left-pad to width
  str_pad_right()    — right-pad to width
  str_upper()        — convert to uppercase
  str_lower()        — convert to lowercase
  str_trim()         — strip leading/trailing whitespace
  str_count()        — count non-overlapping occurrences of substr
  str_reverse()      — reverse a string
  str_truncate()     — truncate with suffix
  str_center()       — center string in field of given width
"""


# ── Byte helpers ─────────────────────────────────────────────────────────────


@always_inline
def _is_whitespace(c: UInt8) -> Bool:
    return c == 32 or c == 9 or c == 10 or c == 13 or c == 12


# ── str_split ────────────────────────────────────────────────────────────────


def str_split(s: String, delimiter: String) -> List[String]:
    """Split string by delimiter. Returns list of parts.
    If delimiter is empty, returns the whole string as a single element.
    """
    var result = List[String]()
    var s_len = s.byte_length()
    var d_len = delimiter.byte_length()

    if d_len == 0 or s_len == 0:
        result.append(s)
        return result^

    var s_bytes = s.as_bytes()
    var d_bytes = delimiter.as_bytes()
    var start = 0

    var i = 0
    while i <= s_len - d_len:
        # Check for delimiter match at position i
        var found = True
        for j in range(d_len):
            if s_bytes[i + j] != d_bytes[j]:
                found = False
                break
        if found:
            # Extract substring from start to i
            var part = String("")
            for k in range(start, i):
                part += chr(Int(s_bytes[k]))
            result.append(part^)
            start = i + d_len
            i = start
        else:
            i += 1

    # Remaining part
    var tail = String("")
    for k in range(start, s_len):
        tail += chr(Int(s_bytes[k]))
    result.append(tail^)

    return result^


# ── str_join ─────────────────────────────────────────────────────────────────


def str_join(parts: List[String], delimiter: String) -> String:
    """Join list of strings with delimiter."""
    var n = len(parts)
    if n == 0:
        return String("")
    var result = parts[0]
    for i in range(1, n):
        result += delimiter
        result += parts[i]
    return result


# ── str_replace ──────────────────────────────────────────────────────────────


def str_replace(s: String, old: String, new: String) -> String:
    """Replace all non-overlapping occurrences of old with new."""
    var s_len = s.byte_length()
    var old_len = old.byte_length()

    if old_len == 0 or s_len == 0:
        return s

    var s_bytes = s.as_bytes()
    var old_bytes = old.as_bytes()
    var result = String("")
    var i = 0

    while i <= s_len - old_len:
        var found = True
        for j in range(old_len):
            if s_bytes[i + j] != old_bytes[j]:
                found = False
                break
        if found:
            result += new
            i += old_len
        else:
            result += chr(Int(s_bytes[i]))
            i += 1

    # Copy remaining characters
    while i < s_len:
        result += chr(Int(s_bytes[i]))
        i += 1

    return result


# ── str_startswith ───────────────────────────────────────────────────────────


def str_startswith(s: String, prefix: String) -> Bool:
    """Return True if s starts with prefix."""
    var s_len = s.byte_length()
    var p_len = prefix.byte_length()
    if p_len > s_len:
        return False
    var s_bytes = s.as_bytes()
    var p_bytes = prefix.as_bytes()
    for i in range(p_len):
        if s_bytes[i] != p_bytes[i]:
            return False
    return True


# ── str_endswith ─────────────────────────────────────────────────────────────


def str_endswith(s: String, suffix: String) -> Bool:
    """Return True if s ends with suffix."""
    var s_len = s.byte_length()
    var suf_len = suffix.byte_length()
    if suf_len > s_len:
        return False
    var s_bytes = s.as_bytes()
    var suf_bytes = suffix.as_bytes()
    var offset = s_len - suf_len
    for i in range(suf_len):
        if s_bytes[offset + i] != suf_bytes[i]:
            return False
    return True


# ── str_contains ─────────────────────────────────────────────────────────────


def str_contains(s: String, substr: String) -> Bool:
    """Return True if s contains substr."""
    var s_len = s.byte_length()
    var sub_len = substr.byte_length()
    if sub_len == 0:
        return True
    if sub_len > s_len:
        return False
    var s_bytes = s.as_bytes()
    var sub_bytes = substr.as_bytes()
    for i in range(s_len - sub_len + 1):
        var found = True
        for j in range(sub_len):
            if s_bytes[i + j] != sub_bytes[j]:
                found = False
                break
        if found:
            return True
    return False


# ── str_repeat ───────────────────────────────────────────────────────────────


def str_repeat(s: String, n: Int) -> String:
    """Repeat string n times."""
    var result = String("")
    for _ in range(n):
        result += s
    return result


# ── str_pad_left ─────────────────────────────────────────────────────────────


def str_pad_left(s: String, width: Int, ch: String) -> String:
    """Left-pad s to given width with ch (uses first character of ch).
    If s is already >= width, returns s unchanged.
    """
    var s_len = s.byte_length()
    if s_len >= width:
        return s
    var pad_len = width - s_len
    var fill_char = ch
    if ch.byte_length() == 0:
        fill_char = String(" ")
    var result = String("")
    for _ in range(pad_len):
        result += fill_char
    result += s
    return result


# ── str_pad_right ────────────────────────────────────────────────────────────


def str_pad_right(s: String, width: Int, ch: String) -> String:
    """Right-pad s to given width with ch (uses first character of ch).
    If s is already >= width, returns s unchanged.
    """
    var s_len = s.byte_length()
    if s_len >= width:
        return s
    var pad_len = width - s_len
    var fill_char = ch
    if ch.byte_length() == 0:
        fill_char = String(" ")
    var result = s
    for _ in range(pad_len):
        result += fill_char
    return result


# ── str_upper ────────────────────────────────────────────────────────────────


def str_upper(s: String) -> String:
    """Convert all lowercase ASCII letters to uppercase."""
    var bs = s.as_bytes()
    var n = s.byte_length()
    var result = String("")
    for i in range(n):
        var c = Int(bs[i])
        if c >= 97 and c <= 122:  # 'a'..'z'
            result += chr(c - 32)
        else:
            result += chr(c)
    return result


# ── str_lower ────────────────────────────────────────────────────────────────


def str_lower(s: String) -> String:
    """Convert all uppercase ASCII letters to lowercase."""
    var bs = s.as_bytes()
    var n = s.byte_length()
    var result = String("")
    for i in range(n):
        var c = Int(bs[i])
        if c >= 65 and c <= 90:  # 'A'..'Z'
            result += chr(c + 32)
        else:
            result += chr(c)
    return result


# ── str_trim ─────────────────────────────────────────────────────────────────


def str_trim(s: String) -> String:
    """Strip leading and trailing ASCII whitespace (space, tab, newline, etc.)."""
    var n = s.byte_length()
    if n == 0:
        return String("")
    var bs = s.as_bytes()
    var start = 0
    while start < n and _is_whitespace(bs[start]):
        start += 1
    var end = n - 1
    while end >= start and _is_whitespace(bs[end]):
        end -= 1
    if start > end:
        return String("")
    var result = String("")
    for i in range(start, end + 1):
        result += chr(Int(bs[i]))
    return result


# ── str_count ────────────────────────────────────────────────────────────────


def str_count(s: String, substr: String) -> Int:
    """Count non-overlapping occurrences of substr in s."""
    var s_len = s.byte_length()
    var sub_len = substr.byte_length()
    if sub_len == 0 or sub_len > s_len:
        return 0
    var s_bytes = s.as_bytes()
    var sub_bytes = substr.as_bytes()
    var count = 0
    var i = 0
    while i <= s_len - sub_len:
        var found = True
        for j in range(sub_len):
            if s_bytes[i + j] != sub_bytes[j]:
                found = False
                break
        if found:
            count += 1
            i += sub_len  # non-overlapping
        else:
            i += 1
    return count


# ── str_reverse ──────────────────────────────────────────────────────────────


def str_reverse(s: String) -> String:
    """Reverse a string (byte-level, ASCII-safe)."""
    var n = s.byte_length()
    if n == 0:
        return String("")
    var bs = s.as_bytes()
    var result = String("")
    for i in range(n):
        result += chr(Int(bs[n - 1 - i]))
    return result


# ── str_truncate ─────────────────────────────────────────────────────────────


def str_truncate(s: String, max_len: Int, suffix: String) -> String:
    """Truncate s to max_len characters, appending suffix if truncated.
    The total returned length including suffix will be <= max_len.
    """
    var s_len = s.byte_length()
    if s_len <= max_len:
        return s
    var suf_len = suffix.byte_length()
    var keep = max_len - suf_len
    if keep < 0:
        keep = 0
    var bs = s.as_bytes()
    var result = String("")
    for i in range(keep):
        result += chr(Int(bs[i]))
    result += suffix
    return result


# ── str_center ───────────────────────────────────────────────────────────────


def str_center(s: String, width: Int, fill: String) -> String:
    """Center s within a field of given width, padding with fill character."""
    var s_len = s.byte_length()
    if s_len >= width:
        return s
    var total_pad = width - s_len
    var left_pad = total_pad // 2
    var right_pad = total_pad - left_pad
    var fill_char = fill
    if fill.byte_length() == 0:
        fill_char = String(" ")
    var result = String("")
    for _ in range(left_pad):
        result += fill_char
    result += s
    for _ in range(right_pad):
        result += fill_char
    return result
