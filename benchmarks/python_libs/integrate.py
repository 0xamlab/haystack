"""Python equivalent of mojo/engine/integrate.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import abs as fabs
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

def trapezoid(y, dx):
    n = len(y)
    if n < 2:
        return 0.0
    s = 0.5 * (y[0] + y[n - 1])
    for i in range(1, n - 1):
        s += y[i]
    return s * dx






def simpson(y, dx):
    n = len(y)
    if n < 3:
        return trapezoid(y, dx)

    s = 0.0

    m = n
    if n % 2 == 0:

        m = n - 1


    s = y[0] + y[m - 1]
    for i in range(1, m - 1):
        if i % 2 == 1:
            s += 4.0 * y[i]
        else:
            s += 2.0 * y[i]
    s *= dx / 3.0


    if n % 2 == 0:
        s += 0.5 * dx * (y[n - 2] + y[n - 1])

    return s






def romberg(y, dx, max_iter=10):
    n = len(y)
    if n < 2:
        return 0.0


    max_levels = 1
    pts = 2
    while pts < n and max_levels < max_iter:
        pts *= 2
        max_levels += 1
    if max_levels > max_iter:
        max_levels = max_iter


    table_size = max_levels * max_levels
    r = []
    for _i in range(table_size):
        r.append(0.0)


    r[0] = 0.5 * float(n - 1) * dx * (y[0] + y[n - 1])

    for k in range(1, max_levels):

        num_intervals = 1
        for _p in range(k):
            num_intervals *= 2
        step_idx = (n - 1) // num_intervals
        if step_idx < 1:
            step_idx = 1


        s = 0.5 * (y[0] + y[n - 1])
        idx = step_idx
        while idx < n - 1:
            s += y[idx]
            idx += step_idx
        r[k * max_levels + 0] = s * float(step_idx) * dx


        four_j = 1.0
        for j in range(1, k + 1):
            four_j *= 4.0
            r[k * max_levels + j] = (four_j * r[k * max_levels + j - 1] - r[(k - 1) * max_levels + j - 1]) / (four_j - 1.0)


    best_level = max_levels - 1
    return r[best_level * max_levels + best_level]






def cumulative_trapezoid(y, dx):
    n = len(y)
    result = []
    if n < 2:
        return result

    cum = 0.0
    for i in range(1, n):
        cum += 0.5 * dx * (y[i - 1] + y[i])
        result.append(cum)

    return result






def integrate_poly(coeffs, a, b):
    n = len(coeffs)
    result = 0.0
    for i in range(n):
        power = i + 1

        bp = 1.0
        ap = 1.0
        for _j in range(power):
            bp *= b
            ap *= a
        result += coeffs[i] * (bp - ap) / float(power)
    return result






def quad_gauss_legendre(y_values, a, b):

    nodes = []
    nodes.append(-0.906179845938664)
    nodes.append(-0.538469310105683)
    nodes.append(0.0)
    nodes.append(0.538469310105683)
    nodes.append(0.906179845938664)

    weights = []
    weights.append(0.236926885056189)
    weights.append(0.478628670499366)
    weights.append(0.568888888888889)
    weights.append(0.478628670499366)
    weights.append(0.236926885056189)

    half_width = (b - a) / 2.0
    mid = (a + b) / 2.0
    n = len(y_values)

    if n == 5:

        result = 0.0
        for i in range(5):
            result += weights[i] * y_values[i]
        return result * half_width


    if n < 2:
        return 0.0

    result = 0.0
    for i in range(5):

        x = mid + half_width * nodes[i]

        t = (x - a) / (b - a) * float(n - 1)
        idx = int(t)
        if idx < 0:
            idx = 0
        if idx >= n - 1:
            idx = n - 2
        frac = t - float(idx)
        yval = y_values[idx] * (1.0 - frac) + y_values[idx + 1] * frac
        result += weights[i] * yval

    return result * half_width
