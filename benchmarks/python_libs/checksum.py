"""Python equivalent of mojo/engine/checksum.mojo (auto-generated)."""
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

def _verhoeff_d(i, j):

    if i == 0:
        if j == 0:
            return 0
        if j == 1:
            return 1
        if j == 2:
            return 2
        if j == 3:
            return 3
        if j == 4:
            return 4
        if j == 5:
            return 5
        if j == 6:
            return 6
        if j == 7:
            return 7
        if j == 8:
            return 8
        return 9
    if i == 1:
        if j == 0:
            return 1
        if j == 1:
            return 2
        if j == 2:
            return 3
        if j == 3:
            return 4
        if j == 4:
            return 0
        if j == 5:
            return 6
        if j == 6:
            return 7
        if j == 7:
            return 8
        if j == 8:
            return 9
        return 5
    if i == 2:
        if j == 0:
            return 2
        if j == 1:
            return 3
        if j == 2:
            return 4
        if j == 3:
            return 0
        if j == 4:
            return 1
        if j == 5:
            return 7
        if j == 6:
            return 8
        if j == 7:
            return 9
        if j == 8:
            return 5
        return 6
    if i == 3:
        if j == 0:
            return 3
        if j == 1:
            return 4
        if j == 2:
            return 0
        if j == 3:
            return 1
        if j == 4:
            return 2
        if j == 5:
            return 8
        if j == 6:
            return 9
        if j == 7:
            return 5
        if j == 8:
            return 6
        return 7
    if i == 4:
        if j == 0:
            return 4
        if j == 1:
            return 0
        if j == 2:
            return 1
        if j == 3:
            return 2
        if j == 4:
            return 3
        if j == 5:
            return 9
        if j == 6:
            return 5
        if j == 7:
            return 6
        if j == 8:
            return 7
        return 8
    if i == 5:
        if j == 0:
            return 5
        if j == 1:
            return 9
        if j == 2:
            return 8
        if j == 3:
            return 7
        if j == 4:
            return 6
        if j == 5:
            return 0
        if j == 6:
            return 4
        if j == 7:
            return 3
        if j == 8:
            return 2
        return 1
    if i == 6:
        if j == 0:
            return 6
        if j == 1:
            return 5
        if j == 2:
            return 9
        if j == 3:
            return 8
        if j == 4:
            return 7
        if j == 5:
            return 1
        if j == 6:
            return 0
        if j == 7:
            return 4
        if j == 8:
            return 3
        return 2
    if i == 7:
        if j == 0:
            return 7
        if j == 1:
            return 6
        if j == 2:
            return 5
        if j == 3:
            return 9
        if j == 4:
            return 8
        if j == 5:
            return 2
        if j == 6:
            return 1
        if j == 7:
            return 0
        if j == 8:
            return 4
        return 3
    if i == 8:
        if j == 0:
            return 8
        if j == 1:
            return 7
        if j == 2:
            return 6
        if j == 3:
            return 5
        if j == 4:
            return 9
        if j == 5:
            return 3
        if j == 6:
            return 2
        if j == 7:
            return 1
        if j == 8:
            return 0
        return 4

    if j == 0:
        return 9
    if j == 1:
        return 8
    if j == 2:
        return 7
    if j == 3:
        return 6
    if j == 4:
        return 5
    if j == 5:
        return 4
    if j == 6:
        return 3
    if j == 7:
        return 2
    if j == 8:
        return 1
    return 0



def _verhoeff_p(i, j):

    if i == 0:
        if j == 0:
            return 0
        if j == 1:
            return 1
        if j == 2:
            return 2
        if j == 3:
            return 3
        if j == 4:
            return 4
        if j == 5:
            return 5
        if j == 6:
            return 6
        if j == 7:
            return 7
        if j == 8:
            return 8
        return 9
    if i == 1:
        if j == 0:
            return 1
        if j == 1:
            return 5
        if j == 2:
            return 7
        if j == 3:
            return 6
        if j == 4:
            return 2
        if j == 5:
            return 8
        if j == 6:
            return 3
        if j == 7:
            return 0
        if j == 8:
            return 9
        return 4
    if i == 2:
        if j == 0:
            return 5
        if j == 1:
            return 8
        if j == 2:
            return 0
        if j == 3:
            return 3
        if j == 4:
            return 7
        if j == 5:
            return 9
        if j == 6:
            return 6
        if j == 7:
            return 1
        if j == 8:
            return 4
        return 2
    if i == 3:
        if j == 0:
            return 8
        if j == 1:
            return 9
        if j == 2:
            return 1
        if j == 3:
            return 6
        if j == 4:
            return 0
        if j == 5:
            return 4
        if j == 6:
            return 3
        if j == 7:
            return 5
        if j == 8:
            return 2
        return 7
    if i == 4:
        if j == 0:
            return 9
        if j == 1:
            return 4
        if j == 2:
            return 5
        if j == 3:
            return 3
        if j == 4:
            return 1
        if j == 5:
            return 2
        if j == 6:
            return 6
        if j == 7:
            return 8
        if j == 8:
            return 7
        return 0
    if i == 5:
        if j == 0:
            return 4
        if j == 1:
            return 2
        if j == 2:
            return 8
        if j == 3:
            return 6
        if j == 4:
            return 5
        if j == 5:
            return 7
        if j == 6:
            return 3
        if j == 7:
            return 9
        if j == 8:
            return 0
        return 1
    if i == 6:
        if j == 0:
            return 2
        if j == 1:
            return 7
        if j == 2:
            return 9
        if j == 3:
            return 3
        if j == 4:
            return 8
        if j == 5:
            return 0
        if j == 6:
            return 6
        if j == 7:
            return 4
        if j == 8:
            return 1
        return 5

    if j == 0:
        return 7
    if j == 1:
        return 0
    if j == 2:
        return 4
    if j == 3:
        return 6
    if j == 4:
        return 9
    if j == 5:
        return 1
    if j == 6:
        return 3
    if j == 7:
        return 2
    if j == 8:
        return 5
    return 8



def adler32(data):
    a = 1
    b = 0
    mod = 65521
    for i in range(len(data)):
        a = (a + (data[i] & 0xFF)) % mod
        b = (b + a) % mod
    return (b << 16) | a






def fletcher16(data):
    sum1 = 0
    sum2 = 0
    for i in range(len(data)):
        sum1 = (sum1 + (data[i] & 0xFF)) % 255
        sum2 = (sum2 + sum1) % 255
    return (sum2 << 8) | sum1






def luhn_check(digits):
    n = len(digits)
    if n == 0:
        return False
    total = 0
    alt = False
    i = n - 1
    while i >= 0:
        d = digits[i]
        if alt:
            d = d * 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
        i -= 1
    return total % 10 == 0






def luhn_checksum(digits):
    n = len(digits)
    total = 0
    alt = True  # Start alternating from rightmost (which will be the check digit)
    i = n - 1
    while i >= 0:
        d = digits[i]
        if alt:
            d = d * 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
        i -= 1
    return (10 - (total % 10)) % 10






def isbn10_check(digits):
    if len(digits) != 10:
        return False
    total = 0
    for i in range(10):
        total += digits[i] * (10 - i)
    return total % 11 == 0






def isbn13_check(digits):
    if len(digits) != 13:
        return False
    total = 0
    for i in range(13):
        if i % 2 == 0:
            total += digits[i]
        else:
            total += digits[i] * 3
    return total % 10 == 0






def xor_checksum(data):
    result = 0
    for i in range(len(data)):
        result = result ^ (data[i] & 0xFF)
    return result






def modular_sum(data, modulus=256):
    total = 0
    for i in range(len(data)):
        total += data[i]
    return total % modulus






def parity_bit(data):
    count = 0
    for i in range(len(data)):
        if data[i] != 0:
            count += 1
    return count % 2






def internet_checksum(data):
    total = 0
    n = len(data)
    i = 0
    while i < n - 1:
        word = ((data[i] & 0xFF) << 8) | (data[i + 1] & 0xFF)
        total += word
        i += 2
    if n % 2 == 1:
        total += (data[n - 1] & 0xFF) << 8


    while total > 0xFFFF:
        total = (total & 0xFFFF) + (total >> 16)

    return (~total) & 0xFFFF






def verhoeff_check(digits):
    n = len(digits)
    if n == 0:
        return False
    c = 0
    for i in range(n):
        idx = n - 1 - i
        p_idx = (i + 1) % 8
        p_val = _verhoeff_p(p_idx, digits[idx])
        c = _verhoeff_d(c, p_val)
    return c == 0
