"""Python equivalent of mojo/engine/regex_engine.mojo (auto-generated)."""
import math
import random as _rng

def random_float64(lo=0.0, hi=1.0): return _rng.uniform(lo, hi)
def random_si64(): return _rng.randint(-2**31, 2**31)
def random_ui64(): return _rng.randint(0, 2**32)

def json_get_string(raw, key, default=''):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return str(v) if v is not None else default
    except Exception: return default
def json_get_float(raw, key, default=0.0):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return float(v) if v is not None else default
    except Exception: return default
def json_get_int(raw, key, default=0):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return int(v) if v is not None else default
    except Exception: return default
def json_get_bool(raw, key, default=False):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return bool(v) if v is not None else default
    except Exception: return default
def json_get_object(raw, key, default='{}'):
    try:
        import json as _j; v = _j.loads(raw).get(key, {})
        return _j.dumps(v) if isinstance(v, dict) else default
    except Exception: return default
def json_get_array(raw, key, default='[]'):
    try:
        import json as _j; v = _j.loads(raw).get(key, [])
        return _j.dumps(v) if isinstance(v, list) else default
    except Exception: return default
def json_array_len(arr):
    try:
        import json as _j; return len(_j.loads(arr))
    except Exception: return 0
def json_array_get(arr, index):
    try:
        import json as _j; v = _j.loads(arr)
        return _j.dumps(v[index]) if index < len(v) else ''
    except Exception: return ''
def to_lower(s): return s.lower()
def contains_keyword(text, keyword): return keyword.lower() in text.lower()
def detect_polarity(field_name):
    n = field_name.lower()
    if any(k in n for k in ('cost','expense','loss','debit','charge','penalty','tax')): return -1
    if any(k in n for k in ('revenue','profit','income','gain','credit','sales')): return 1
    return 0
def detect_unit_hint(field_name):
    n = field_name.lower()
    if any(k in n for k in ('cost','price','revenue','profit','amount','value','dollar')): return 'currency'
    if any(k in n for k in ('pct','percent','ratio','rate','margin')): return 'percentage'
    if any(k in n for k in ('qty','quantity','count','units','volume')): return 'count'
    return ''
def infer_distribution_from_values(values): return ('normal', '{}')
def map_fields(raw): return []
def build_objective_function(mappings): return ''
def build_variables_json(mappings): return '[]'
class FieldMapping: pass
def dice_coefficient(a, b):
    if not a or not b: return 0.0
    def _bg(s): return set(s[i:i+2] for i in range(len(s)-1))
    ag, bg = _bg(a), _bg(b)
    if not ag or not bg: return 0.0
    return 2.0 * len(ag & bg) / (len(ag) + len(bg))
def edit_similarity(a, b):
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    m, n = len(a), len(b); dp = list(range(n+1))
    for i in range(1, m+1):
        prev, dp[0] = dp[0], i
        for j in range(1, n+1):
            t = dp[j]; dp[j] = prev if a[i-1]==b[j-1] else 1+min(prev,dp[j],dp[j-1]); prev=t
    return 1.0 - dp[n] / max(m, n)
def jaccard_index(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb: return 1.0
    if not sa or not sb: return 0.0
    return len(sa & sb) / len(sa | sb)
def to_set(lst): return list(set(lst))
def parse_float64(s, default=0.0):
    try: return float(s)
    except Exception: return default
def parse_int(s, default=0):
    try: return int(float(s))
    except Exception: return default
DIM_UNKNOWN = 0; DIM_COUNT = 1; DIM_CURRENCY = 2; DIM_RATE = 3
DIM_RATIO = 4; DIM_IDENTIFIER = 5; DIM_INVALID = -1
def infer_from_samples(values): return DIM_UNKNOWN
def propagate(a, b, op): return DIM_UNKNOWN
def role_for_dimension(dim): return 'metric'
class Python:
    @staticmethod
    def import_module(name):
        import importlib; return importlib.import_module(name)

def _byte_at(s, i):
    return int(s.encode('utf-8')[i])






def _parse_class(pattern, start):
    pb = pattern.encode('utf-8')
    n = len(pattern)
    content = str("")
    i = start
    while i < n:
        if int(pb[i]) == 93:
            return (content, i + 1)
        content += chr(int(pb[i]))
        i += 1
    return (content, i)



def _match_one(pattern, pp, text, tp):
    if tp >= len(text):
        return (False, pp)
    pb = pattern.encode('utf-8')
    tb = text.encode('utf-8')
    pch = int(pb[pp])
    tch = int(tb[tp])

    if pch == 46:
        return (True, pp + 1)
    elif pch == 91:
        result = _parse_class(pattern, pp + 1)
        cls = result[0]
        end_pos = result[1]
        if match_char_class(cls, tch):
            return (True, end_pos)
        return (False, end_pos)
    elif pch == 92:
        if pp + 1 < len(pattern):
            next_ch = int(pb[pp + 1])
            if next_ch == int(pb[pp + 1]):
                if tch == next_ch:
                    return (True, pp + 2)
                return (False, pp + 2)
        return (False, pp + 1)
    else:
        if tch == pch:
            return (True, pp + 1)
        return (False, pp + 1)



def _skip_one(pattern, pp):
    if pp >= len(pattern):
        return pp
    pb = pattern.encode('utf-8')
    pch = int(pb[pp])
    if pch == 91:
        result = _parse_class(pattern, pp + 1)
        return result[1]
    elif pch == 92:
        return pp + 2
    else:
        return pp + 1



def _match_here(pattern, pp, text, tp, plen, tlen):
    if pp >= plen:
        return True

    pb = pattern.encode('utf-8')


    if pp == plen - 1 and int(pb[pp]) == 36:
        return tp == tlen


    next_pp = _skip_one(pattern, pp)
    has_quantifier = False
    quant = 0
    if next_pp < plen:
        qch = int(pb[next_pp])
        if qch == 42 or qch == 43 or qch == 63:
            has_quantifier = True
            quant = qch

    if has_quantifier:
        after_quant = next_pp + 1
        if quant == 42:

            count = 0

            t = tp
            while t < tlen:
                result = _match_one(pattern, pp, text, t)
                if not result[0]:
                    break
                count += 1
                t += 1

            i = count
            while i >= 0:
                if _match_here(pattern, after_quant, text, tp + i, plen, tlen):
                    return True
                i -= 1
            return False
        elif quant == 43:
            count = 0
            t = tp
            while t < tlen:
                result = _match_one(pattern, pp, text, t)
                if not result[0]:
                    break
                count += 1
                t += 1
            i = count
            while i >= 1:
                if _match_here(pattern, after_quant, text, tp + i, plen, tlen):
                    return True
                i -= 1
            return False
        elif quant == 63:

            result = _match_one(pattern, pp, text, tp)
            if result[0] and _match_here(pattern, after_quant, text, tp + 1, plen, tlen):
                return True
            return _match_here(pattern, after_quant, text, tp, plen, tlen)


    result = _match_one(pattern, pp, text, tp)
    if result[0]:
        return _match_here(pattern, result[1], text, tp + 1, plen, tlen)
    return False






def match_literal(pattern, text):
    if len(pattern) != len(text):
        return False
    pb = pattern.encode('utf-8')
    tb = text.encode('utf-8')
    for i in range(len(pattern)):
        if pb[i] != tb[i]:
            return False
    return True






def match_dot_star(text, start, end):
    return start >= 0 and end >= start and end <= len(text)






def match_char_class(char_class, ch):
    cb = char_class.encode('utf-8')
    n = len(char_class)
    i = 0
    while i < n:
        if i + 2 < n and int(cb[i + 1]) == 45:
            lo = int(cb[i])
            hi = int(cb[i + 2])
            if ch >= lo and ch <= hi:
                return True
            i += 3
        else:
            if ch == int(cb[i]):
                return True
            i += 1
    return False






def regex_match(pattern, text):
    plen = len(pattern)
    tlen = len(text)
    if plen == 0:
        return tlen == 0

    pb = pattern.encode('utf-8')
    pp = 0

    if int(pb[0]) == 94:
        pp = 1


    pat = pattern
    if int(pb[plen - 1]) != 36:
        pat = pattern + "$"

    full_plen = len(pat)
    if _match_here(pat, pp, text, 0, full_plen, tlen):
        return True
    return False






def regex_search(pattern, text):
    plen = len(pattern)
    tlen = len(text)
    if plen == 0:
        return True

    pb = pattern.encode('utf-8')
    pp = 0
    if int(pb[0]) == 94:
        return _match_here(pattern, 1, text, 0, plen, tlen)

    for i in range(tlen + 1):
        if _match_here(pattern, pp, text, i, plen, tlen):
            return True
    return False






def regex_find_first(pattern, text):
    plen = len(pattern)
    tlen = len(text)
    if plen == 0:
        r = []
        r.append(0)
        r.append(0)
        return r

    for start in range(tlen):
        for end in range(start, tlen + 1):

            sub = str("")
            tb = text.encode('utf-8')
            for k in range(start, end):
                sub += chr(int(tb[k]))
            if regex_match(pattern, sub):
                r = []
                r.append(start)
                r.append(end)
                return r
    return []






def count_matches(pattern, text):
    plen = len(pattern)
    tlen = len(text)
    if plen == 0 or plen > tlen:
        return 0
    count = 0
    i = 0
    pb = pattern.encode('utf-8')
    tb = text.encode('utf-8')
    while i <= tlen - plen:
        found = True
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






def split_by_literal(text, delimiter):
    result = []
    dlen = len(delimiter)
    tlen = len(text)
    if dlen == 0 or tlen == 0:
        result.append(text)
        return result

    tb = text.encode('utf-8')
    db = delimiter.encode('utf-8')
    start = 0
    i = 0
    while i <= tlen - dlen:
        found = True
        for j in range(dlen):
            if tb[i + j] != db[j]:
                found = False
                break
        if found:
            part = str("")
            for k in range(start, i):
                part += chr(int(tb[k]))
            result.append(part)
            i += dlen
            start = i
        else:
            i += 1

    last = str("")
    for k in range(start, tlen):
        last += chr(int(tb[k]))
    result.append(last)
    return result






def is_valid_pattern(pattern):
    pb = pattern.encode('utf-8')
    n = len(pattern)
    bracket_depth = 0
    prev_is_quantifiable = False

    i = 0
    while i < n:
        ch = int(pb[i])
        if ch == 91:
            bracket_depth += 1
            prev_is_quantifiable = False
        elif ch == 93:
            if bracket_depth <= 0:
                return False
            bracket_depth -= 1
            prev_is_quantifiable = True
        elif ch == 42 or ch == 43 or ch == 63:
            if not prev_is_quantifiable:
                return False
            prev_is_quantifiable = False  # can't double-quantify
        elif ch == 92:
            i += 1  # skip escaped char
            if i >= n:
                return False
            prev_is_quantifiable = True
        elif ch == 94 or ch == 36:
            prev_is_quantifiable = False
        elif ch == 46:
            prev_is_quantifiable = True
        else:
            prev_is_quantifiable = True
        i += 1

    return bracket_depth == 0
