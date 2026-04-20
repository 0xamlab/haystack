"""Python equivalent of mojo/engine/interpolate.mojo (auto-generated)."""
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

def _find_interval(x_data, x):
    n = len(x_data)
    if n <= 1:
        return 0
    if x <= x_data[0]:
        return 0
    if x >= x_data[n - 1]:
        return n - 2
    lo = 0
    hi = n - 2
    while lo < hi:
        mid = (lo + hi) // 2
        if x_data[mid + 1] <= x:
            lo = mid + 1
        else:
            hi = mid
    return lo






def linear_interp(x_data, y_data, x):
    n = len(x_data)
    if n == 0:
        return 0.0
    if n == 1:
        return y_data[0]

    if x <= x_data[0]:
        return y_data[0]
    if x >= x_data[n - 1]:
        return y_data[n - 1]
    i = _find_interval(x_data, x)
    dx = x_data[i + 1] - x_data[i]
    if math.fabs(dx) < 1e-15:
        return y_data[i]
    t = (x - x_data[i]) / dx
    return y_data[i] + t * (y_data[i + 1] - y_data[i])






def nearest_interp(x_data, y_data, x):
    n = len(x_data)
    if n == 0:
        return 0.0
    if n == 1:
        return y_data[0]
    if x <= x_data[0]:
        return y_data[0]
    if x >= x_data[n - 1]:
        return y_data[n - 1]
    i = _find_interval(x_data, x)
    d_left = math.fabs(x - x_data[i])
    d_right = math.fabs(x_data[i + 1] - x)
    if d_left <= d_right:
        return y_data[i]
    return y_data[i + 1]






def cubic_spline_natural(x_data, y_data, x):
    n = len(x_data)
    if n == 0:
        return 0.0
    if n == 1:
        return y_data[0]
    if n == 2:
        return linear_interp(x_data, y_data, x)


    x_eval = x
    if x_eval < x_data[0]:
        x_eval = x_data[0]
    if x_eval > x_data[n - 1]:
        x_eval = x_data[n - 1]


    h = []
    for i in range(n - 1):
        h.append(x_data[i + 1] - x_data[i])





    c = []
    for i in range(n):
        c.append(0.0)

    if n > 2:

        alpha = []
        for i in range(n):
            alpha.append(0.0)
        for i in range(1, n - 1):
            alpha[i] = 3.0 * ((y_data[i + 1] - y_data[i]) / h[i] - (y_data[i] - y_data[i - 1]) / h[i - 1])

        l = []
        mu = []
        z = []
        for i in range(n):
            l.append(0.0)
            mu.append(0.0)
            z.append(0.0)
        l[0] = 1.0

        for i in range(1, n - 1):
            l[i] = 2.0 * (x_data[i + 1] - x_data[i - 1]) - h[i - 1] * mu[i - 1]
            if math.fabs(l[i]) < 1e-15:
                l[i] = 1e-15
            mu[i] = h[i] / l[i]
            z[i] = (alpha[i] - h[i - 1] * z[i - 1]) / l[i]

        l[n - 1] = 1.0

        for j in range(n - 2, -1, -1):
            c[j] = z[j] - mu[j] * c[j + 1]


    b = []
    d = []
    for i in range(n - 1):
        b.append(0.0)
        d.append(0.0)

    for i in range(n - 1):
        if math.fabs(h[i]) < 1e-15:
            b[i] = 0.0
            d[i] = 0.0
        else:
            b[i] = (y_data[i + 1] - y_data[i]) / h[i] - h[i] * (c[i + 1] + 2.0 * c[i]) / 3.0
            d[i] = (c[i + 1] - c[i]) / (3.0 * h[i])


    idx = _find_interval(x_data, x_eval)
    dx = x_eval - x_data[idx]
    return y_data[idx] + b[idx] * dx + c[idx] * dx * dx + d[idx] * dx * dx * dx






def lagrange_interp(x_data, y_data, x):
    n = len(x_data)
    if n == 0:
        return 0.0
    if n == 1:
        return y_data[0]
    result = 0.0
    for i in range(n):
        basis = 1.0
        for j in range(n):
            if j != i:
                denom = x_data[i] - x_data[j]
                if math.fabs(denom) < 1e-15:
                    continue
                basis *= (x - x_data[j]) / denom
        result += y_data[i] * basis
    return result






def interp_array(x_data, y_data, x_new, method):
    result = []
    for i in range(len(x_new)):
        xi = x_new[i]
        if method == "nearest":
            result.append(nearest_interp(x_data, y_data, xi))
        elif method == "cubic":
            result.append(cubic_spline_natural(x_data, y_data, xi))
        elif method == "lagrange":
            result.append(lagrange_interp(x_data, y_data, xi))
        else:

            result.append(linear_interp(x_data, y_data, xi))
    return result






def extrapolate_linear(x_data, y_data, x):
    n = len(x_data)
    if n == 0:
        return 0.0
    if n == 1:
        return y_data[0]

    if x >= x_data[0] and x <= x_data[n - 1]:
        return linear_interp(x_data, y_data, x)

    if x < x_data[0]:
        dx = x_data[1] - x_data[0]
        if math.fabs(dx) < 1e-15:
            return y_data[0]
        slope = (y_data[1] - y_data[0]) / dx
        return y_data[0] + slope * (x - x_data[0])

    dx = x_data[n - 1] - x_data[n - 2]
    if math.fabs(dx) < 1e-15:
        return y_data[n - 1]
    slope = (y_data[n - 1] - y_data[n - 2]) / dx
    return y_data[n - 1] + slope * (x - x_data[n - 1])
