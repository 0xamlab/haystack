"""Python equivalent of mojo/engine/sampling.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.random import random_float64
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

def halton_sequence(n, base):
    result = []
    for i in range(1, n + 1):
        f = 1.0
        r = 0.0
        idx = i
        while idx > 0:
            f /= float(base)
            r += f * float(idx % base)
            idx //= base
        result.append(r)
    return result






def halton_2d(n):
    seq_x = halton_sequence(n, 2)
    seq_y = halton_sequence(n, 3)
    result = []
    for i in range(n):
        pt = []
        pt.append(seq_x[i])
        pt.append(seq_y[i])
        result.append(pt)
    return result






def stratified_sample_1d(n_strata):
    result = []
    width = 1.0 / float(n_strata)
    for i in range(n_strata):
        lo = float(i) * width
        u = random_float64()
        result.append(lo + u * width)
    return result






def latin_hypercube_sample(n, d):

    result = []
    for _ in range(n):
        pt = []
        for _ in range(d):
            pt.append(0.0)
        result.append(pt)

    width = 1.0 / float(n)

    for dim in range(d):

        perm = []
        for i in range(n):
            perm.append(i)


        for i in range(n - 1, 0, -1):
            u = random_float64()
            j = int(u * float(i + 1))
            if j > i:
                j = i

            tmp = perm[i]
            perm[i] = perm[j]
            perm[j] = tmp


        for i in range(n):
            stratum = perm[i]
            lo = float(stratum) * width
            u = random_float64()
            result[i][dim] = lo + u * width

    return result






def sobol_like_2d(n):


    phi2 = 1.32471795724474602596
    alpha1 = 1.0 / phi2
    alpha2 = 1.0 / (phi2 * phi2)

    result = []
    for i in range(n):
        x = 0.5 + float(i + 1) * alpha1
        y = 0.5 + float(i + 1) * alpha2

        x = x - float(int(x))
        y = y - float(int(y))
        pt = []
        pt.append(x)
        pt.append(y)
        result.append(pt)
    return result






def discrepancy_l2_star(points):
    n = len(points)
    if n == 0:
        return 0.0


    term1 = 1.0 / 9.0



    sum2 = 0.0
    for i in range(n):
        xi = points[i][0]
        yi = points[i][1]
        sum2 += (1.0 - xi * xi) * (1.0 - yi * yi)
    term2 = -sum2 / (2.0 * float(n))


    sum3 = 0.0
    for i in range(n):
        xi = points[i][0]
        yi = points[i][1]
        for j in range(n):
            xj = points[j][0]
            yj = points[j][1]
            mx = xi if xi > xj else xj
            my = yi if yi > yj else yj
            sum3 += (1.0 - mx) * (1.0 - my)
    term3 = sum3 / (float(n) * float(n))

    d2 = term1 + term2 + term3
    if d2 < 0.0:
        d2 = 0.0
    return math.sqrt(d2)
