"""Python equivalent of mojo/engine/polynomial.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import abs as fabs
except Exception:
    pass
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

def poly_eval(coeffs, x):
    n = len(coeffs)
    if n == 0:
        return 0.0

    result = coeffs[n - 1]
    i = n - 2
    while i >= 0:
        result = result * x + coeffs[i]
        i -= 1
    return result






def poly_add(a, b):
    na = len(a)
    nb = len(b)
    n = na if na > nb else nb
    result = []
    for i in range(n):
        va = 0.0
        vb = 0.0
        if i < na:
            va = a[i]
        if i < nb:
            vb = b[i]
        result.append(va + vb)
    return result






def poly_multiply(a, b):
    na = len(a)
    nb = len(b)
    if na == 0 or nb == 0:
        return []
    nc = na + nb - 1
    result = []
    for _ in range(nc):
        result.append(0.0)
    for i in range(na):
        for j in range(nb):
            result[i + j] += a[i] * b[j]
    return result






def poly_derivative(coeffs):
    n = len(coeffs)
    if n <= 1:
        zero = []
        zero.append(0.0)
        return zero
    result = []
    for i in range(1, n):
        result.append(float(i) * coeffs[i])
    return result






def poly_integral(coeffs, C=0.0):
    n = len(coeffs)
    result = []
    result.append(C)
    for i in range(n):
        result.append(coeffs[i] / float(i + 1))
    return result






def poly_degree(coeffs):
    n = len(coeffs)
    if n == 0:
        return -1
    deg = n - 1
    while deg > 0 and math.fabs(coeffs[deg]) < 1e-15:
        deg -= 1
    return deg






def quadratic_roots(a, b, c):
    result = []
    if math.fabs(a) < 1e-15:

        if math.fabs(b) > 1e-15:
            result.append(-c / b)
        return result
    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return result  # complex roots
    sq = math.sqrt(disc)
    r1 = (-b - sq) / (2.0 * a)
    r2 = (-b + sq) / (2.0 * a)
    result.append(r1)
    result.append(r2)
    return result






def poly_scale(coeffs, s):
    n = len(coeffs)
    result = []
    for i in range(n):
        result.append(coeffs[i] * s)
    return result






def poly_compose(f, g):
    nf = len(f)
    if nf == 0:
        return []

    result = []
    result.append(f[nf - 1])
    i = nf - 2
    while i >= 0:

        result = poly_multiply(result, g)

        if len(result) == 0:
            result.append(f[i])
        else:
            result[0] += f[i]
        i -= 1
    return result






def poly_from_roots(roots):
    n = len(roots)
    if n == 0:
        one = []
        one.append(1.0)
        return one

    result = []
    result.append(-roots[0])
    result.append(1.0)
    for i in range(1, n):
        factor = []
        factor.append(-roots[i])
        factor.append(1.0)
        result = poly_multiply(result, factor)
    return result
