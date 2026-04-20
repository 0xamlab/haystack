"""Python equivalent of mojo/engine/conv.mojo (auto-generated)."""
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

def _trimmed_bounds(bytes, n):
    start = 0
    while start < n and is_whitespace(bytes[start]):
        start += 1
    end = n
    while end > start and is_whitespace(bytes[end - 1]):
        end -= 1
    return (start, end)






def _pow10(exp):
    result = 1.0
    base = 10.0
    e = exp if exp >= 0 else -exp

    while e > 0:
        if e & 1 == 1:
            result *= base
        base *= base
        e >>= 1

    if exp < 0:
        return 1.0 / result
    return result



def _nibble_to_hex(n):
    if n < 10:
        return chr(48 + n)   # ord('0') = 48
    return chr(87 + n)       # ord('a') - 10 = 87



def is_digit(c):
    return c >= int(48) and c <= int(57)  # ord('0')=48, ord('9')=57



def is_whitespace(c):
    return c == int(32) or c == int(9) or c == int(10) or c == int(13)



def digit_value(c):
    return int(c) - 48






def span_to_str(s, start, end):
    bytes = s.encode('utf-8')
    e = min(end, len(s))
    result = str("")
    for i in range(start, e):
        result += chr(int(bytes[i]))
    return result



def span_to_str_end(s, start):
    return span_to_str(s, start, len(s))






def strip_whitespace(s):
    n = len(s)
    if n == 0:
        return s

    bytes = s.encode('utf-8')
    start = 0
    while start < n and is_whitespace(bytes[start]):
        start += 1

    end = n - 1
    while end >= start and is_whitespace(bytes[end]):
        end -= 1

    if start > end:
        return str("")


    result = str("")
    for i in range(start, end + 1):
        result += chr(int(bytes[i]))
    return result






def parse_float64(s):
    n = len(s)
    if n == 0:
        return 0.0

    bytes = s.encode('utf-8')
    bounds = _trimmed_bounds(bytes, n)
    pos = bounds[0]
    limit = bounds[1]

    if pos >= limit:
        return 0.0

    negative = False


    if bytes[pos] == int(45):
        negative = True
        pos += 1
    elif bytes[pos] == int(43):
        pos += 1

    if pos >= limit:
        return 0.0

    has_digits = False


    int_part = 0.0
    while pos < limit and is_digit(bytes[pos]):
        int_part = int_part * 10.0 + float(digit_value(bytes[pos]))
        pos += 1
        has_digits = True


    frac_part = 0.0
    if pos < limit and bytes[pos] == int(46):
        pos += 1
        frac_scale = 0.1
        while pos < limit and is_digit(bytes[pos]):
            frac_part += float(digit_value(bytes[pos])) * frac_scale
            frac_scale *= 0.1
            pos += 1
            has_digits = True

    if not has_digits:
        return 0.0

    result = int_part + frac_part


    if pos < limit and (bytes[pos] == int(101) or bytes[pos] == int(69)):
        pos += 1
        exp_negative = False
        if pos < limit and bytes[pos] == int(45):
            exp_negative = True
            pos += 1
        elif pos < limit and bytes[pos] == int(43):
            pos += 1

        exp_val = 0
        while pos < limit and is_digit(bytes[pos]):
            exp_val = exp_val * 10 + digit_value(bytes[pos])
            pos += 1

        if exp_negative:
            exp_val = -exp_val

        result *= _pow10(exp_val)


    if negative:
        result = -result

    return result






def parse_int(s):
    n = len(s)
    if n == 0:
        return 0

    bytes = s.encode('utf-8')
    bounds = _trimmed_bounds(bytes, n)
    pos = bounds[0]
    limit = bounds[1]

    if pos >= limit:
        return 0

    negative = False


    if bytes[pos] == int(45):
        negative = True
        pos += 1
    elif bytes[pos] == int(43):
        pos += 1

    if pos >= limit:
        return 0

    has_digits = False
    result = 0


    while pos < limit and is_digit(bytes[pos]):
        result = result * 10 + digit_value(bytes[pos])
        pos += 1
        has_digits = True

    if not has_digits:
        return 0



    if negative:
        result = -result

    return result






def float_to_string(v):
    return str(v)






def int_to_hex(v, width=8):
    s = str("")

    for i in range(width):
        shift = int((width - 1 - i) * 4)
        s += _nibble_to_hex(int((v >> shift) & 0xF))
    return s
