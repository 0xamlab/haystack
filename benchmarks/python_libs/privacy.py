"""Python equivalent of mojo/engine/privacy.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import log
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

def _laplace_sample(scale):
    u = random_float64()

    if u < 1e-15:
        u = 1e-15
    if u > 1.0 - 1e-15:
        u = 1.0 - 1e-15
    if u < 0.5:
        return scale * math.log(2.0 * u)
    else:
        return -scale * math.log(2.0 * (1.0 - u))






def _gaussian_sample(sigma):
    u1 = random_float64()
    u2 = random_float64()
    if u1 < 1e-15:
        u1 = 1e-15
    z = math.sqrt(-2.0 * math.log(u1)) * _cos_approx(2.0 * 3.141592653589793 * u2)
    return sigma * z



def _cos_approx(x):
    pi = 3.141592653589793
    two_pi = 2.0 * pi

    r = x
    while r < 0.0:
        r += two_pi
    while r >= two_pi:
        r -= two_pi


    if r > pi:
        r = r - two_pi
    r2 = r * r
    r4 = r2 * r2
    r6 = r4 * r2
    r8 = r4 * r4
    r10 = r6 * r4
    return 1.0 - r2 / 2.0 + r4 / 24.0 - r6 / 720.0 + r8 / 40320.0 - r10 / 3628800.0






def laplace_mechanism(value, sensitivity, epsilon):
    scale = sensitivity / epsilon
    return value + _laplace_sample(scale)






def gaussian_mechanism(value, sensitivity, epsilon, delta):
    sigma = sensitivity * math.sqrt(2.0 * math.log(1.25 / delta)) / epsilon
    return value + _gaussian_sample(sigma)






def exponential_mechanism_scores(scores, sensitivity, epsilon):
    result = []
    for i in range(len(scores)):
        w = math.exp(epsilon * scores[i] / (2.0 * sensitivity))
        result.append(w)
    return result






def randomized_response(true_value, p):
    r = random_float64()
    if r < p:
        return true_value
    else:
        return not true_value






def composition_epsilon(epsilons):
    total = 0.0
    for i in range(len(epsilons)):
        total += epsilons[i]
    return total






def advanced_composition(epsilon, delta, k):
    kf = float(k)
    term1 = epsilon * math.sqrt(2.0 * kf * math.log(1.0 / delta))
    term2 = kf * epsilon * (math.exp(epsilon) - 1.0)
    return term1 + term2






def sensitivity_l1(data):
    m = 0.0
    for i in range(len(data)):
        a = math.fabs(data[i])
        if a > m:
            m = a
    return m






def sensitivity_l2(data):
    m = 0.0
    for i in range(len(data)):
        a = math.fabs(data[i])
        if a > m:
            m = a

    return m






def dp_mean(data, lower, upper, epsilon):
    n = len(data)
    if n == 0:
        return 0.0
    s = 0.0
    for i in range(n):
        v = data[i]
        if v < lower:
            v = lower
        if v > upper:
            v = upper
        s += v
    mean = s / float(n)
    sensitivity = (upper - lower) / float(n)
    return mean + _laplace_sample(sensitivity / epsilon)






def dp_count(count, epsilon):
    scale = 1.0 / epsilon
    return float(count) + _laplace_sample(scale)
