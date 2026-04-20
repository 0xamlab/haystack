"""Python equivalent of mojo/engine/copula.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass
try:
    from std.random import random_float64
except Exception:
    pass

PI = 3.141592653589793
SQRT2 = 1.4142135623730951

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

def _box_muller_pair():
    u1 = random_float64()
    u2 = random_float64()

    if u1 < 1e-15:
        u1 = 1e-15
    r = math.sqrt(-2.0 * math.log(u1))
    theta = 2.0 * math.pi * u2

    z0 = r * _cos_approx(theta)
    z1 = r * _sin_approx(theta)
    result = []
    result.append(z0)
    result.append(z1)
    return result



def _sin_approx(x):

    v = x
    while v > math.pi:
        v -= 2.0 * math.pi
    while v < -math.pi:
        v += 2.0 * math.pi

    x2 = v * v
    x3 = v * x2
    x5 = x3 * x2
    x7 = x5 * x2
    x9 = x7 * x2
    x11 = x9 * x2
    return v - x3 / 6.0 + x5 / 120.0 - x7 / 5040.0 + x9 / 362880.0 - x11 / 39916800.0



def _cos_approx(x):
    v = x
    while v > math.pi:
        v -= 2.0 * math.pi
    while v < -math.pi:
        v += 2.0 * math.pi
    x2 = v * v
    x4 = x2 * x2
    x6 = x4 * x2
    x8 = x6 * x2
    x10 = x8 * x2
    return 1.0 - x2 / 2.0 + x4 / 24.0 - x6 / 720.0 + x8 / 40320.0 - x10 / 3628800.0






def _rank(values):
    n = len(values)
    indices = []
    for i in range(n):
        indices.append(i)


    for i in range(1, n):
        key_idx = indices[i]
        key_val = values[key_idx]
        j = i - 1
        while j >= 0 and values[indices[j]] > key_val:
            indices[j + 1] = indices[j]
            j -= 1
        indices[j + 1] = key_idx


    ranks = []
    for _ in range(n):
        ranks.append(0.0)

    i = 0
    while i < n:
        j = i
        while j < n - 1 and math.fabs(values[indices[j + 1]] - values[indices[i]]) < 1e-12:
            j += 1
        avg_rank = float(i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indices[k]] = avg_rank
        i = j + 1

    return ranks



def norm_cdf_approx(x):
    if x < -8.0:
        return 0.0
    if x > 8.0:
        return 1.0


    ax = x
    if ax < 0.0:
        ax = -ax


    p = 0.2316419
    b1 = 0.319381530
    b2 = -0.356563782
    b3 = 1.781477937
    b4 = -1.821255978
    b5 = 1.330274429

    t = 1.0 / (1.0 + p * ax)
    t2 = t * t
    t3 = t2 * t
    t4 = t3 * t
    t5 = t4 * t

    pdf = math.exp(-0.5 * ax * ax) / math.sqrt(2.0 * math.pi)
    cdf = 1.0 - pdf * (b1 * t + b2 * t2 + b3 * t3 + b4 * t4 + b5 * t5)

    if x < 0.0:
        return 1.0 - cdf
    return cdf






def norm_ppf_approx(p):
    if p <= 0.0:
        return -1e10
    if p >= 1.0:
        return 1e10


    a1 = -3.969683028665376e+01
    a2 = 2.209460984245205e+02
    a3 = -2.759285104469687e+02
    a4 = 1.383577518672690e+02
    a5 = -3.066479806614716e+01
    a6 = 2.506628277459239e+00

    b1 = -5.447609879822406e+01
    b2 = 1.615858368580409e+02
    b3 = -1.556989798598866e+02
    b4 = 6.680131188771972e+01
    b5 = -1.328068155288572e+01

    c1 = -7.784894002430293e-03
    c2 = -3.223964580411365e-01
    c3 = -2.400758277161838e+00
    c4 = -2.549732539343734e+00
    c5 = 4.374664141464968e+00
    c6 = 2.938163982698783e+00

    d1 = 7.784695709041462e-03
    d2 = 3.224671290700398e-01
    d3 = 2.445134137142996e+00
    d4 = 3.754408661907416e+00

    p_low = 0.02425
    p_high = 1.0 - p_low

    result = 0.0

    if p < p_low:

        q = math.sqrt(-2.0 * math.log(p))
        result = (((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) / ((((d1 * q + d2) * q + d3) * q + d4) * q + 1.0)
    elif p <= p_high:

        q = p - 0.5
        r = q * q
        result = (((((a1 * r + a2) * r + a3) * r + a4) * r + a5) * r + a6) * q / (((((b1 * r + b2) * r + b3) * r + b4) * r + b5) * r + 1.0)
    else:

        q = math.sqrt(-2.0 * math.log(1.0 - p))
        result = -(((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) / ((((d1 * q + d2) * q + d3) * q + d4) * q + 1.0)

    return result






def gaussian_copula_sample(n, rho):
    result = []


    rho2 = rho * rho
    chol_21 = rho
    chol_22 = math.sqrt(1.0 - rho2) if rho2 < 1.0 else 0.0

    for _ in range(n):
        pair = _box_muller_pair()
        z1 = pair[0]
        z2_raw = pair[1]


        x1 = z1
        x2 = chol_21 * z1 + chol_22 * z2_raw


        u1 = norm_cdf_approx(x1)
        u2 = norm_cdf_approx(x2)


        if u1 < 0.0:
            u1 = 0.0
        if u1 > 1.0:
            u1 = 1.0
        if u2 < 0.0:
            u2 = 0.0
        if u2 > 1.0:
            u2 = 1.0

        sample = []
        sample.append(u1)
        sample.append(u2)
        result.append(sample)

    return result






def rank_correlation(x, y):
    n = len(x)
    if n < 2:
        return 0.0

    rx = _rank(x)
    ry = _rank(y)


    sum_rx = 0.0
    sum_ry = 0.0
    for i in range(n):
        sum_rx += rx[i]
        sum_ry += ry[i]
    mean_rx = sum_rx / float(n)
    mean_ry = sum_ry / float(n)

    num = 0.0
    den_x = 0.0
    den_y = 0.0
    for i in range(n):
        dx = rx[i] - mean_rx
        dy = ry[i] - mean_ry
        num += dx * dy
        den_x += dx * dx
        den_y += dy * dy

    denom = math.sqrt(den_x * den_y)
    if denom < 1e-15:
        return 0.0
    return num / denom






def kendall_tau(x, y):
    n = len(x)
    if n < 2:
        return 0.0

    concordant = 0
    discordant = 0
    ties_x = 0
    ties_y = 0

    for i in range(n):
        for j in range(i + 1, n):
            dx = x[j] - x[i]
            dy = y[j] - y[i]
            sign_x = 0
            sign_y = 0
            if dx > 1e-12:
                sign_x = 1
            elif dx < -1e-12:
                sign_x = -1
            if dy > 1e-12:
                sign_y = 1
            elif dy < -1e-12:
                sign_y = -1

            product = sign_x * sign_y
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
            else:
                if sign_x == 0:
                    ties_x += 1
                if sign_y == 0:
                    ties_y += 1

    n0 = n * (n - 1) // 2
    denom = math.sqrt(float(n0 - ties_x) * float(n0 - ties_y))
    if denom < 1e-15:
        return 0.0
    return float(concordant - discordant) / denom
