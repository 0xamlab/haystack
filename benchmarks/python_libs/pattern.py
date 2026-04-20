"""Python equivalent of mojo/engine/pattern.mojo (auto-generated)."""
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

def _is_ws(c):
    return c == 32 or c == 9 or c == 10 or c == 13






def glob_match(pattern, text):
    pbs = pattern.encode('utf-8')
    tbs = text.encode('utf-8')
    plen = len(pattern)
    tlen = len(text)
    STAR = int(ord("*"))
    QMARK = int(ord("?"))

    cols = tlen + 1
    dp = []
    for _ in range((plen + 1) * cols):
        dp.append(False)
    dp[0] = True  # empty pattern matches empty text

    for i in range(1, plen + 1):
        if pbs[i - 1] == STAR:
            dp[i * cols] = dp[(i - 1) * cols]
        for j in range(1, tlen + 1):
            pc = pbs[i - 1]
            if pc == STAR:
                dp[i * cols + j] = dp[(i - 1) * cols + j] or dp[i * cols + j - 1]
            elif pc == QMARK or pc == tbs[j - 1]:
                dp[i * cols + j] = dp[(i - 1) * cols + (j - 1)]
            else:
                dp[i * cols + j] = False
    return dp[plen * cols + tlen]






def starts_with(text, prefix):
    plen = len(prefix)
    if plen > len(text):
        return False
    tbs = text.encode('utf-8')
    pbs = prefix.encode('utf-8')
    for i in range(plen):
        if tbs[i] != pbs[i]:
            return False
    return True






def ends_with(text, suffix):
    slen = len(suffix)
    tlen = len(text)
    if slen > tlen:
        return False
    tbs = text.encode('utf-8')
    sbs = suffix.encode('utf-8')
    offset = tlen - slen
    for i in range(slen):
        if tbs[offset + i] != sbs[i]:
            return False
    return True






def contains(text, sub):
    tlen = len(text)
    slen = len(sub)
    if slen == 0:
        return True
    if slen > tlen:
        return False
    tbs = text.encode('utf-8')
    sbs = sub.encode('utf-8')
    for i in range(tlen - slen + 1):
        found = True
        for j in range(slen):
            if tbs[i + j] != sbs[j]:
                found = False
                break
        if found:
            return True
    return False






def count_occurrences(text, sub):
    tlen = len(text)
    slen = len(sub)
    if slen == 0:
        return 0
    tbs = text.encode('utf-8')
    sbs = sub.encode('utf-8')
    count = 0
    i = 0
    while i <= tlen - slen:
        found = True
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






def replace_all(text, old, new):
    tlen = len(text)
    olen = len(old)
    if olen == 0:
        return text
    tbs = text.encode('utf-8')
    obs = old.encode('utf-8')
    result = str("")
    i = 0
    while i < tlen:
        if i <= tlen - olen:
            found = True
            for j in range(olen):
                if tbs[i + j] != obs[j]:
                    found = False
                    break
            if found:
                result += new
                i += olen
                continue
        result += chr(int(tbs[i]))
        i += 1
    return result






def template_substitute(template, keys, values):
    result = template
    nk = len(keys)
    for i in range(nk):
        placeholder = "{{" + keys[i] + "}}"
        result = replace_all(result, placeholder, values[i])
    return result






def split_string(text, delimiter):
    parts = []
    tlen = len(text)
    dlen = len(delimiter)
    if dlen == 0 or tlen == 0:
        parts.append(text)
        return parts
    tbs = text.encode('utf-8')
    dbs = delimiter.encode('utf-8')
    start = 0
    i = 0
    while i <= tlen - dlen:
        found = True
        for j in range(dlen):
            if tbs[i + j] != dbs[j]:
                found = False
                break
        if found:
            part = str("")
            for k in range(start, i):
                part += chr(int(tbs[k]))
            parts.append(part)
            start = i + dlen
            i = start
        else:
            i += 1
    tail = str("")
    for k in range(start, tlen):
        tail += chr(int(tbs[k]))
    parts.append(tail)
    return parts






def join_strings(parts, delimiter):
    n = len(parts)
    if n == 0:
        return str("")
    result = parts[0]
    for i in range(1, n):
        result += delimiter
        result += parts[i]
    return result






def pad_left(text, width, fill_char=32):
    tlen = len(text)
    if tlen >= width:
        return text
    pad_count = width - tlen
    fc = chr(fill_char)
    result = str("")
    for _ in range(pad_count):
        result += fc
    result += text
    return result






def pad_right(text, width, fill_char=32):
    tlen = len(text)
    if tlen >= width:
        return text
    pad_count = width - tlen
    fc = chr(fill_char)
    result = text
    for _ in range(pad_count):
        result += fc
    return result






def trim(text):
    tlen = len(text)
    if tlen == 0:
        return text
    bs = text.encode('utf-8')
    start = 0
    while start < tlen and _is_ws(bs[start]):
        start += 1
    end = tlen - 1
    while end >= start and _is_ws(bs[end]):
        end -= 1
    if start > end:
        return str("")
    result = str("")
    for i in range(start, end + 1):
        result += chr(int(bs[i]))
    return result
