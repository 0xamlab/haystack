"""
engines/string_similarity.mojo — NL hint → column name fuzzy + acronym similarity.

Implements a RapidFuzz-style matching pipeline:
  1. Symbol-expand column name  (% → percent, $ → dollar, # → number)
  2. camelCase split            (TDGCode → tdg code)
  3. Tokenize hint words and expanded column into [a-z0-9]+ tokens
  4. Per hint word: best match  = prefix_ratio OR bigram_dice over col tokens
  5. Geometric mean of per-hint scores → fuzzy_score
  6. Acronym check: any ALL-CAPS 2-6 char col token == initials of hint phrase?
       → acronym_score ∈ [0, 1]
  7. final_score = max(fuzzy_score, acronym_score)

All logic is pure Mojo — zero Python imports.
Uses: string_distance.dice_coefficient, field_mapper.to_lower, std.math.log/exp

Input:
  {
    "engine_type": "string_similarity",
    "hint_words": ["business", "unit"],
    "columns": ["LEACH_BU", "SALES_REP_NAME", "INVEN_BUSINESS_UNIT"],
    "threshold": 0.0
  }

Output:
  {
    "matches": [
      {"column":"INVEN_BUSINESS_UNIT","score":1.0,"fuzzy":1.0,"acronym":0.0,"method":"fuzzy"},
      {"column":"LEACH_BU","score":1.0,"fuzzy":0.354,"acronym":1.0,"method":"acronym"},
      {"column":"SALES_REP_NAME","score":0.0,"fuzzy":0.0,"acronym":0.0,"method":"fuzzy"}
    ]
  }
"""
from std.math import log, exp, abs as fabs

from string_distance import dice_coefficient
from field_mapper import to_lower
from json.parser import (
    json_get_float,
    json_get_array,
    json_array_len,
    json_array_get,
)


# ── Byte-level helpers ────────────────────────────────────────────────────────

fn _to_lower_byte(c: UInt8) -> UInt8:
    """Lowercase a single ASCII byte."""
    if c >= UInt8(65) and c <= UInt8(90):
        return c + UInt8(32)
    return c

fn _is_alnum_lower(c: UInt8) -> Bool:
    """True for [a-z0-9]."""
    return (c >= UInt8(97) and c <= UInt8(122)) or (c >= UInt8(48) and c <= UInt8(57))

fn _is_alnum_any(c: UInt8) -> Bool:
    """True for [A-Za-z0-9]."""
    return ((c >= UInt8(65) and c <= UInt8(90)) or
            (c >= UInt8(97) and c <= UInt8(122)) or
            (c >= UInt8(48) and c <= UInt8(57)))

fn _is_upper_alpha(c: UInt8) -> Bool:
    return c >= UInt8(65) and c <= UInt8(90)

fn _is_lower_alpha(c: UInt8) -> Bool:
    return c >= UInt8(97) and c <= UInt8(122)

fn _is_stop_word(w: String) -> Bool:
    return (w == "of" or w == "the" or w == "a" or w == "an" or
            w == "and" or w == "or" or w == "by" or w == "in" or
            w == "at" or w == "for" or w == "per")


# ── JSON string unquote (mirrors request_parser._unquote) ────────────────────

fn _unquote(s: String) -> String:
    """Strip surrounding JSON double-quotes; handle backslash escapes."""
    var n = len(s)
    if n < 2:
        return s
    var bytes = s.as_bytes()
    if bytes[0] != UInt8(34) or bytes[n - 1] != UInt8(34):
        return s
    var result = String("")
    var i = 1
    while i < n - 1:
        if bytes[i] == UInt8(92) and i + 1 < n - 1:
            var nxt = bytes[i + 1]
            if nxt == UInt8(34):    result += '"'
            elif nxt == UInt8(92):  result += "\\"
            elif nxt == UInt8(110): result += "\n"
            elif nxt == UInt8(116): result += "\t"
            elif nxt == UInt8(114): result += "\r"
            elif nxt == UInt8(47):  result += "/"
            else:                   result += chr(Int(nxt))
            i += 2
            continue
        result += chr(Int(bytes[i]))
        i += 1
    return result


# ── Column name preprocessing ─────────────────────────────────────────────────

fn _expand_column(col: String) -> String:
    """
    Expand column name for tokenization:
      - Symbol substitution: % → percent, $ → dollar, # → number
      - camelCase splitting: lowercase char → uppercase char inserts a space
      - Convert to lowercase
    """
    var n = len(col)
    var bytes = col.as_bytes()
    var result = String("")
    for i in range(n):
        var c = bytes[i]
        if c == UInt8(37):        # %
            result += " percent "
        elif c == UInt8(36):      # $
            result += " dollar "
        elif c == UInt8(35):      # #
            result += " number "
        elif _is_upper_alpha(c) and i > 0 and _is_lower_alpha(bytes[i - 1]):
            # camelCase boundary: insert space before uppercase
            result += " "
            result += chr(Int(c + UInt8(32)))  # lowercase
        else:
            result += chr(Int(_to_lower_byte(c)))
    return result


fn _tokenize(s: String) -> List[String]:
    """Extract [a-z0-9]+ tokens from an already-lowercased/expanded string."""
    var result = List[String]()
    var bytes = s.as_bytes()
    var n = len(s)
    var i = 0
    while i < n:
        if _is_alnum_lower(bytes[i]):
            var start = i
            while i < n and _is_alnum_lower(bytes[i]):
                i += 1
            var tok = String("")
            for k in range(start, i):
                tok += chr(Int(bytes[k]))
            if len(tok) > 0:
                result.append(tok)
        else:
            i += 1
    return result^


fn _col_raw_parts(col: String) -> List[String]:
    """
    Extract [A-Za-z0-9]+ tokens from original column name, preserving case.
    Used for acronym detection (need to check all-uppercase tokens).
    """
    var result = List[String]()
    var bytes = col.as_bytes()
    var n = len(col)
    var i = 0
    while i < n:
        if _is_alnum_any(bytes[i]):
            var start = i
            while i < n and _is_alnum_any(bytes[i]):
                i += 1
            var tok = String("")
            for k in range(start, i):
                tok += chr(Int(bytes[k]))
            if len(tok) > 0:
                result.append(tok)
        else:
            i += 1
    return result^


# ── Similarity kernels ────────────────────────────────────────────────────────

fn _fuzzy_token_sim(a: String, b: String) -> Float64:
    """
    Compare two lowercase tokens:
      1. Exact match       → 1.0
      2. Prefix containment → len(short)/len(long)
      3. Bigram Dice       → dice_coefficient(a, b)
    Returns the best score.
    """
    if len(a) == 0 or len(b) == 0:
        return 0.0
    if a == b:
        return 1.0
    var la = len(a)
    var lb = len(b)
    # Identify shorter and longer
    var short_s = a
    var long_s  = b
    var sl = la
    var ll = lb
    if la > lb:
        short_s = b; long_s = a
        sl = lb; ll = la
    # Prefix check: does long_s start with short_s?
    var sb = short_s.as_bytes()
    var lb2 = long_s.as_bytes()
    var is_prefix = True
    for k in range(sl):
        if sb[k] != lb2[k]:
            is_prefix = False
            break
    if is_prefix:
        return Float64(sl) / Float64(ll)
    # Bigram Dice similarity
    return dice_coefficient(a, b)


fn _fuzzy_name_sim(hint_toks: List[String], col_toks: List[String]) -> Float64:
    """
    Geometric mean of per-hint-word best fuzzy token similarity.

    For each hint word, find its best match across all column tokens.
    Combine per-word scores via geometric mean so ALL hint words must be
    represented — a partial match on one word cannot compensate for zero
    match on another.
    """
    var n_hint = len(hint_toks)
    var n_col  = len(col_toks)
    if n_hint == 0 or n_col == 0:
        return 0.0
    var log_sum: Float64 = 0.0
    for hi in range(n_hint):
        var best: Float64 = 1e-6   # floor to avoid log(0)
        for ci in range(n_col):
            var sim = _fuzzy_token_sim(hint_toks[hi], col_toks[ci])
            if sim > best:
                best = sim
        log_sum += log(best)
    return exp(log_sum / Float64(n_hint))


fn _acronym_score(hint_toks: List[String], col_parts: List[String]) -> Float64:
    """
    Score based on whether any ALL-CAPS 2-6-char column token spells out
    the initials of the hint phrase.

    e.g. hint_words=["business","unit"] → initials="BU"
         col_parts=["LEACH","BU"] → "BU"=="BU" → 1.0

    Stop words ("of","the","a","an","and","or","by","in","at","for","per")
    are excluded from initial extraction.
    """
    # Build initials string from content (non-stop) hint words
    var initials = String("")
    for i in range(len(hint_toks)):
        var hw = hint_toks[i]
        if _is_stop_word(hw) or len(hw) == 0:
            continue
        var wb = hw.as_bytes()
        var first = wb[0]
        # Uppercase the first character
        if _is_lower_alpha(first):
            initials += chr(Int(first - UInt8(32)))
        else:
            initials += chr(Int(first))

    if len(initials) == 0:
        return 0.0

    var init_bytes = initials.as_bytes()
    var init_len   = len(initials)
    var best: Float64 = 0.0

    for pi in range(len(col_parts)):
        var part = col_parts[pi]
        var plen = len(part)
        if plen < 2 or plen > 6:
            continue
        # Must be entirely uppercase alphabetic
        var pb = part.as_bytes()
        var all_upper = True
        for k in range(plen):
            if not _is_upper_alpha(pb[k]):
                all_upper = False
                break
        if not all_upper:
            continue
        # Exact match → perfect score
        if part == initials:
            return 1.0
        # Partial match: count positional matches over longer of the two
        var min_len = plen if plen < init_len else init_len
        var max_len = plen if plen > init_len else init_len
        var matches = 0
        for k in range(min_len):
            if pb[k] == init_bytes[k]:
                matches += 1
        var partial = Float64(matches) / Float64(max_len)
        if partial > best:
            best = partial

    return best


# ── Main entry point ──────────────────────────────────────────────────────────

fn run_string_similarity(raw: String) raises -> String:
    """
    Score each column name against the hint_words and return all matches
    (optionally filtered by threshold) in the order they were supplied.

    Callers sort by score descending if needed.
    """
    # Parse hint_words array
    var hint_arr = json_get_array(raw, "hint_words")
    var n_hints  = json_array_len(hint_arr)
    var threshold: Float64 = json_get_float(raw, "threshold", 0.0)

    # Build lowercase hint token list
    var hint_toks = List[String]()
    for i in range(n_hints):
        var raw_hw = _unquote(json_array_get(hint_arr, i))
        var hw = to_lower(raw_hw)
        # Trim leading/trailing spaces
        var hb = hw.as_bytes()
        var hn = len(hw)
        var hs = 0
        var he = hn
        while hs < hn and hb[hs] == UInt8(32):
            hs += 1
        while he > hs and hb[he - 1] == UInt8(32):
            he -= 1
        if he > hs:
            var htok = String("")
            for k in range(hs, he):
                htok += chr(Int(hb[k]))
            if len(htok) > 0:
                hint_toks.append(htok)

    # Parse columns array
    var cols_arr = json_get_array(raw, "columns")
    var n_cols   = json_array_len(cols_arr)

    if len(hint_toks) == 0 or n_cols == 0:
        return '{"matches":[]}'

    var output = String('{"matches":[')
    var match_count = 0

    for ci in range(n_cols):
        var col = _unquote(json_array_get(cols_arr, ci))
        if len(col) == 0:
            continue

        # Expand + tokenize for fuzzy matching
        var col_exp  = _expand_column(col)
        var col_toks = _tokenize(col_exp)

        # Raw parts (original case) for acronym detection
        var col_parts = _col_raw_parts(col)

        var fuzzy = _fuzzy_name_sim(hint_toks, col_toks)
        var acro  = _acronym_score(hint_toks, col_parts)

        var score = fuzzy
        if acro > score:
            score = acro

        if score < threshold:
            continue

        var method = String("fuzzy")
        if acro >= fuzzy and acro > 0.0:
            method = "acronym"

        if match_count > 0:
            output += ","
        output += '{"column":"' + col + '",'
        output += '"score":'   + String(score) + ','
        output += '"fuzzy":'   + String(fuzzy) + ','
        output += '"acronym":' + String(acro)  + ','
        output += '"method":"' + method + '"}'
        match_count += 1

    output += ']}'
    return output
