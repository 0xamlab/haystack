"""Python equivalent of mojo/engine/stats.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass

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

def compute_mean(v, n):
    t = 0.0
    for i in range(n): t += v[i]
    return t / float(n)


def compute_variance(v, n, mean):
    if n <= 1:
        return 0.0
    s = 0.0
    for i in range(n):
        d = v[i] - mean; s += d * d
    return s / float(n - 1)


def pctile(v, n, p):
    return v[max(0, min((n-1)*p//100, n-1))]


def count_below_zero(v, n):
    c = 0
    for i in range(n):
        if v[i] < 0.0:
            c += 1
    return c





def ins_sort(a, lo, hi):
    for i in range(lo+1, hi+1):
        k = a[i]; j = i-1
        while j >= lo and a[j] > k: a[j+1] = a[j]; j -= 1
        a[j+1] = k


def ilog2(n):
    r = 0; x = n
    while x > 1: x >>= 1; r += 1
    return r


def part3(a, lo, hi):
    mid = lo + (hi - lo) // 2
    if a[lo] > a[mid]:
        t = a[lo];  a[lo]  = a[mid]; a[mid] = t
    if a[lo] > a[hi]:
        t = a[lo];  a[lo]  = a[hi];  a[hi]  = t
    if a[mid] > a[hi]:
        t = a[mid]; a[mid] = a[hi];  a[hi]  = t
    piv = a[mid]
    t2 = a[mid]; a[mid] = a[hi-1]; a[hi-1] = t2
    i = lo; j = hi-1
    while True:
        i += 1
        while a[i] < piv: i += 1
        j -= 1
        while a[j] > piv: j -= 1
        if i >= j:
            break
        t3 = a[i]; a[i] = a[j]; a[j] = t3
    t4 = a[i]; a[i] = a[hi-1]; a[hi-1] = t4
    return i


def fast_sort(a, n):
    if n <= 1:
        return
    if n <= 16:
        ins_sort(a, 0, n-1); return
    stk = []
    stk.append(0); stk.append(n-1); stk.append(2*ilog2(n))
    while len(stk) > 0:
        d = stk[len(stk)-1]
        hi = stk[len(stk)-2]
        lo = stk[len(stk)-3]
        stk.resize(len(stk)-3, 0)
        if hi <= lo:
            continue
        if hi - lo <= 16:
            ins_sort(a, lo, hi); continue
        if d == 0:
            ins_sort(a, lo, hi); continue
        p = part3(a, lo, hi)
        stk.append(lo);   stk.append(p-1); stk.append(d-1)
        stk.append(p+1);  stk.append(hi);  stk.append(d-1)
