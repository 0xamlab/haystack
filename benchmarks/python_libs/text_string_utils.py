"""Python equivalent of mojo/engine/text.string_utils.mojo (auto-generated)."""
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

def _is_whitespace(c):
    return c == 32 or c == 9 or c == 10 or c == 13 or c == 12






def str_split(s, delimiter):
    result = []
    s_len = len(s)
    d_len = len(delimiter)

    if d_len == 0 or s_len == 0:
        result.append(s)
        return result

    s_bytes = s.encode('utf-8')
    d_bytes = delimiter.encode('utf-8')
    start = 0

    i = 0
    while i <= s_len - d_len:

        found = True
        for j in range(d_len):
            if s_bytes[i + j] != d_bytes[j]:
                found = False
                break
        if found:

            part = str("")
            for k in range(start, i):
                part += chr(int(s_bytes[k]))
            result.append(part)
            start = i + d_len
            i = start
        else:
            i += 1


    tail = str("")
    for k in range(start, s_len):
        tail += chr(int(s_bytes[k]))
    result.append(tail)

    return result






def str_join(parts, delimiter):
    n = len(parts)
    if n == 0:
        return str("")
    result = parts[0]
    for i in range(1, n):
        result += delimiter
        result += parts[i]
    return result






def str_replace(s, old, new):
    s_len = len(s)
    old_len = len(old)

    if old_len == 0 or s_len == 0:
        return s

    s_bytes = s.encode('utf-8')
    old_bytes = old.encode('utf-8')
    result = str("")
    i = 0

    while i <= s_len - old_len:
        found = True
        for j in range(old_len):
            if s_bytes[i + j] != old_bytes[j]:
                found = False
                break
        if found:
            result += new
            i += old_len
        else:
            result += chr(int(s_bytes[i]))
            i += 1


    while i < s_len:
        result += chr(int(s_bytes[i]))
        i += 1

    return result






def str_startswith(s, prefix):
    s_len = len(s)
    p_len = len(prefix)
    if p_len > s_len:
        return False
    s_bytes = s.encode('utf-8')
    p_bytes = prefix.encode('utf-8')
    for i in range(p_len):
        if s_bytes[i] != p_bytes[i]:
            return False
    return True






def str_endswith(s, suffix):
    s_len = len(s)
    suf_len = len(suffix)
    if suf_len > s_len:
        return False
    s_bytes = s.encode('utf-8')
    suf_bytes = suffix.encode('utf-8')
    offset = s_len - suf_len
    for i in range(suf_len):
        if s_bytes[offset + i] != suf_bytes[i]:
            return False
    return True






def str_contains(s, substr):
    s_len = len(s)
    sub_len = len(substr)
    if sub_len == 0:
        return True
    if sub_len > s_len:
        return False
    s_bytes = s.encode('utf-8')
    sub_bytes = substr.encode('utf-8')
    for i in range(s_len - sub_len + 1):
        found = True
        for j in range(sub_len):
            if s_bytes[i + j] != sub_bytes[j]:
                found = False
                break
        if found:
            return True
    return False






def str_repeat(s, n):
    result = str("")
    for _ in range(n):
        result += s
    return result






def str_pad_left(s, width, ch):
    s_len = len(s)
    if s_len >= width:
        return s
    pad_len = width - s_len
    fill_char = ch
    if len(ch) == 0:
        fill_char = str(" ")
    result = str("")
    for _ in range(pad_len):
        result += fill_char
    result += s
    return result






def str_pad_right(s, width, ch):
    s_len = len(s)
    if s_len >= width:
        return s
    pad_len = width - s_len
    fill_char = ch
    if len(ch) == 0:
        fill_char = str(" ")
    result = s
    for _ in range(pad_len):
        result += fill_char
    return result






def str_upper(s):
    bs = s.encode('utf-8')
    n = len(s)
    result = str("")
    for i in range(n):
        c = int(bs[i])
        if c >= 97 and c <= 122:
            result += chr(c - 32)
        else:
            result += chr(c)
    return result






def str_lower(s):
    bs = s.encode('utf-8')
    n = len(s)
    result = str("")
    for i in range(n):
        c = int(bs[i])
        if c >= 65 and c <= 90:
            result += chr(c + 32)
        else:
            result += chr(c)
    return result






def str_trim(s):
    n = len(s)
    if n == 0:
        return str("")
    bs = s.encode('utf-8')
    start = 0
    while start < n and _is_whitespace(bs[start]):
        start += 1
    end = n - 1
    while end >= start and _is_whitespace(bs[end]):
        end -= 1
    if start > end:
        return str("")
    result = str("")
    for i in range(start, end + 1):
        result += chr(int(bs[i]))
    return result






def str_count(s, substr):
    s_len = len(s)
    sub_len = len(substr)
    if sub_len == 0 or sub_len > s_len:
        return 0
    s_bytes = s.encode('utf-8')
    sub_bytes = substr.encode('utf-8')
    count = 0
    i = 0
    while i <= s_len - sub_len:
        found = True
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






def str_reverse(s):
    n = len(s)
    if n == 0:
        return str("")
    bs = s.encode('utf-8')
    result = str("")
    for i in range(n):
        result += chr(int(bs[n - 1 - i]))
    return result






def str_truncate(s, max_len, suffix):
    s_len = len(s)
    if s_len <= max_len:
        return s
    suf_len = len(suffix)
    keep = max_len - suf_len
    if keep < 0:
        keep = 0
    bs = s.encode('utf-8')
    result = str("")
    for i in range(keep):
        result += chr(int(bs[i]))
    result += suffix
    return result






def str_center(s, width, fill):
    s_len = len(s)
    if s_len >= width:
        return s
    total_pad = width - s_len
    left_pad = total_pad // 2
    right_pad = total_pad - left_pad
    fill_char = fill
    if len(fill) == 0:
        fill_char = str(" ")
    result = str("")
    for _ in range(left_pad):
        result += fill_char
    result += s
    for _ in range(right_pad):
        result += fill_char
    return result
