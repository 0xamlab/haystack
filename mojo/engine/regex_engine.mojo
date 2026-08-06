"""
regex_engine.mojo — Simple regex engine. Zero Python imports.

Replaces Python's re module core matching with a pure Mojo implementation
supporting: literal chars, . (any), * (0+), + (1+), ? (0 or 1),
^ (start), $ (end), [abc] (char class), [a-z] (range).

Public API:
  regex_match       — Full match: does pattern match entire text?
  regex_search      — Partial match: does pattern appear anywhere?
  regex_find_first  — Find first match, return [start, end] or empty
  match_literal     — Exact literal string match
  match_dot_star    — Match .* (always true within bounds)
  match_char_class  — Check if byte matches [abc] or [a-z] class
  count_matches     — Count non-overlapping literal matches
  split_by_literal  — Split text by literal delimiter
  is_valid_pattern  — Basic pattern validation
"""


# ── Byte helpers ──────────────────────────────────────────────────────────────

def _byte_at(s: String, i: Int) -> Int:
    """Get byte value at index i."""
    return Int(s.as_bytes()[i])


# ── match_literal ─────────────────────────────────────────────────────────────


def match_literal(pattern: String, text: String) -> Bool:
    """Exact literal string match. Returns True if pattern == text."""
    if len(pattern) != len(text):
        return False
    var pb = pattern.as_bytes()
    var tb = text.as_bytes()
    for i in range(len(pattern)):
        if pb[i] != tb[i]:
            return False
    return True


# ── match_dot_star ────────────────────────────────────────────────────────────


def match_dot_star(text: String, start: Int, end: Int) -> Bool:
    """Match .* — always true if start and end are within bounds."""
    return start >= 0 and end >= start and end <= len(text)


# ── match_char_class ──────────────────────────────────────────────────────────


def match_char_class(char_class: String, ch: Int) -> Bool:
    """Check if byte ch matches character class string.

    char_class is the content inside brackets, e.g. "abc" or "a-z" or "0-9A-F".
    Supports literal characters and ranges like a-z.
    """
    var cb = char_class.as_bytes()
    var n = len(char_class)
    var i = 0
    while i < n:
        if i + 2 < n and Int(cb[i + 1]) == 45:  # '-' = 45
            var lo = Int(cb[i])
            var hi = Int(cb[i + 2])
            if ch >= lo and ch <= hi:
                return True
            i += 3
        else:
            if ch == Int(cb[i]):
                return True
            i += 1
    return False


# ── Internal: _match_here ─────────────────────────────────────────────────────


def _parse_class(pattern: String, start: Int) -> Tuple[String, Int]:
    """Parse character class starting after '['. Returns (class_content, end_pos)."""
    var pb = pattern.as_bytes()
    var n = len(pattern)
    var content = String("")
    var i = start
    while i < n:
        if Int(pb[i]) == 93:  # ']'
            return (content, i + 1)
        content += chr(Int(pb[i]))
        i += 1
    return (content, i)


def _match_one(pattern: String, pp: Int, text: String, tp: Int) -> Tuple[Bool, Int]:
    """Match one pattern element at pp against text at tp.
    Returns (matched, new_pattern_pos)."""
    if tp >= len(text):
        return (False, pp)
    var pb = pattern.as_bytes()
    var tb = text.as_bytes()
    var pch = Int(pb[pp])
    var tch = Int(tb[tp])

    if pch == 46:  # '.'
        return (True, pp + 1)
    elif pch == 91:  # '['
        var result = _parse_class(pattern, pp + 1)
        var cls = result[0]
        var end_pos = result[1]
        if match_char_class(cls, tch):
            return (True, end_pos)
        return (False, end_pos)
    elif pch == 92:  # '\' escape
        if pp + 1 < len(pattern):
            var next_ch = Int(pb[pp + 1])
            if next_ch == Int(pb[pp + 1]):  # any escaped char
                if tch == next_ch:
                    return (True, pp + 2)
                return (False, pp + 2)
        return (False, pp + 1)
    else:
        if tch == pch:
            return (True, pp + 1)
        return (False, pp + 1)


def _skip_one(pattern: String, pp: Int) -> Int:
    """Skip one pattern element (char, class, or escape)."""
    if pp >= len(pattern):
        return pp
    var pb = pattern.as_bytes()
    var pch = Int(pb[pp])
    if pch == 91:  # '['
        var result = _parse_class(pattern, pp + 1)
        return result[1]
    elif pch == 92:  # '\'
        return pp + 2
    else:
        return pp + 1


def _match_here(pattern: String, pp: Int, text: String, tp: Int, plen: Int, tlen: Int) -> Bool:
    """Recursive matching of pattern[pp:] against text[tp:]."""
    if pp >= plen:
        return True

    var pb = pattern.as_bytes()

    # Check for $ at end of pattern
    if pp == plen - 1 and Int(pb[pp]) == 36:  # '$'
        return tp == tlen

    # Check for quantifier after current element
    var next_pp = _skip_one(pattern, pp)
    var has_quantifier = False
    var quant = 0
    if next_pp < plen:
        var qch = Int(pb[next_pp])
        if qch == 42 or qch == 43 or qch == 63:  # *, +, ?
            has_quantifier = True
            quant = qch

    if has_quantifier:
        var after_quant = next_pp + 1
        if quant == 42:  # '*' — 0 or more
            # Try matching 0 copies first (greedy from right)
            var count = 0
            # Count max matches
            var t = tp
            while t < tlen:
                var result = _match_one(pattern, pp, text, t)
                if not result[0]:
                    break
                count += 1
                t += 1
            # Try from max down to 0
            var i = count
            while i >= 0:
                if _match_here(pattern, after_quant, text, tp + i, plen, tlen):
                    return True
                i -= 1
            return False
        elif quant == 43:  # '+' — 1 or more
            var count = 0
            var t = tp
            while t < tlen:
                var result = _match_one(pattern, pp, text, t)
                if not result[0]:
                    break
                count += 1
                t += 1
            var i = count
            while i >= 1:
                if _match_here(pattern, after_quant, text, tp + i, plen, tlen):
                    return True
                i -= 1
            return False
        elif quant == 63:  # '?' — 0 or 1
            # Try 1 then 0
            var result = _match_one(pattern, pp, text, tp)
            if result[0] and _match_here(pattern, after_quant, text, tp + 1, plen, tlen):
                return True
            return _match_here(pattern, after_quant, text, tp, plen, tlen)

    # No quantifier — match exactly one
    var result = _match_one(pattern, pp, text, tp)
    if result[0]:
        return _match_here(pattern, result[1], text, tp + 1, plen, tlen)
    return False


# ── regex_match ───────────────────────────────────────────────────────────────


def regex_match(pattern: String, text: String) -> Bool:
    """Full match: does pattern match entire text?

    Supports: literal, ., *, +, ?, ^, $, [abc], [a-z].
    """
    var plen = len(pattern)
    var tlen = len(text)
    if plen == 0:
        return tlen == 0

    var pb = pattern.as_bytes()
    var pp = 0

    if Int(pb[0]) == 94:  # '^'
        pp = 1

    # Append '$' to enforce full-text match if not already present
    var pat = pattern
    if Int(pb[plen - 1]) != 36:  # not '$'
        pat = pattern + "$"

    var full_plen = len(pat)
    if _match_here(pat, pp, text, 0, full_plen, tlen):
        return True
    return False


# ── regex_search ──────────────────────────────────────────────────────────────


def regex_search(pattern: String, text: String) -> Bool:
    """Partial match: does pattern appear anywhere in text?"""
    var plen = len(pattern)
    var tlen = len(text)
    if plen == 0:
        return True

    var pb = pattern.as_bytes()
    var pp = 0
    if Int(pb[0]) == 94:  # '^' — anchor to start
        return _match_here(pattern, 1, text, 0, plen, tlen)

    for i in range(tlen + 1):
        if _match_here(pattern, pp, text, i, plen, tlen):
            return True
    return False


# ── regex_find_first ──────────────────────────────────────────────────────────


def regex_find_first(pattern: String, text: String) -> List[Int]:
    """Find first match of pattern in text, return [start, end] or empty list."""
    var plen = len(pattern)
    var tlen = len(text)
    if plen == 0:
        var r = List[Int]()
        r.append(0)
        r.append(0)
        return r^

    for start in range(tlen):
        for end in range(start, tlen + 1):
            # Check if pattern matches text[start:end]
            var sub = String("")
            var tb = text.as_bytes()
            for k in range(start, end):
                sub += chr(Int(tb[k]))
            if regex_match(pattern, sub):
                var r = List[Int]()
                r.append(start)
                r.append(end)
                return r^
    return List[Int]()


# ── count_matches ─────────────────────────────────────────────────────────────


def count_matches(pattern: String, text: String) -> Int:
    """Count non-overlapping matches of literal pattern in text."""
    var plen = len(pattern)
    var tlen = len(text)
    if plen == 0 or plen > tlen:
        return 0
    var count = 0
    var i = 0
    var pb = pattern.as_bytes()
    var tb = text.as_bytes()
    while i <= tlen - plen:
        var found = True
        for j in range(plen):
            if tb[i + j] != pb[j]:
                found = False
                break
        if found:
            count += 1
            i += plen  # non-overlapping
        else:
            i += 1
    return count


# ── split_by_literal ──────────────────────────────────────────────────────────


def split_by_literal(text: String, delimiter: String) -> List[String]:
    """Split text by literal delimiter pattern."""
    var result = List[String]()
    var dlen = len(delimiter)
    var tlen = len(text)
    if dlen == 0 or tlen == 0:
        result.append(text)
        return result^

    var tb = text.as_bytes()
    var db = delimiter.as_bytes()
    var start = 0
    var i = 0
    while i <= tlen - dlen:
        var found = True
        for j in range(dlen):
            if tb[i + j] != db[j]:
                found = False
                break
        if found:
            var part = String("")
            for k in range(start, i):
                part += chr(Int(tb[k]))
            result.append(part)
            i += dlen
            start = i
        else:
            i += 1
    # Add remaining part
    var last = String("")
    for k in range(start, tlen):
        last += chr(Int(tb[k]))
    result.append(last)
    return result^


# ── is_valid_pattern ──────────────────────────────────────────────────────────


def is_valid_pattern(pattern: String) -> Bool:
    """Basic pattern validation: balanced brackets, valid quantifier placement."""
    var pb = pattern.as_bytes()
    var n = len(pattern)
    var bracket_depth = 0
    var prev_is_quantifiable = False

    var i = 0
    while i < n:
        var ch = Int(pb[i])
        if ch == 91:  # '['
            bracket_depth += 1
            prev_is_quantifiable = False
        elif ch == 93:  # ']'
            if bracket_depth <= 0:
                return False
            bracket_depth -= 1
            prev_is_quantifiable = True
        elif ch == 42 or ch == 43 or ch == 63:  # *, +, ?
            if not prev_is_quantifiable:
                return False
            prev_is_quantifiable = False  # can't double-quantify
        elif ch == 92:  # '\'
            i += 1  # skip escaped char
            if i >= n:
                return False
            prev_is_quantifiable = True
        elif ch == 94 or ch == 36:  # ^ or $
            prev_is_quantifiable = False
        elif ch == 46:  # '.'
            prev_is_quantifiable = True
        else:
            prev_is_quantifiable = True
        i += 1

    return bracket_depth == 0
