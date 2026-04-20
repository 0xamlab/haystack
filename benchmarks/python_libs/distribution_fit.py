"""Python equivalent of mojo/engine/distribution_fit.mojo (auto-generated)."""
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
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import exp
except Exception:
    pass

PI = 3.141592653589793
TWO_PI = 6.283185307179586
LOG_TWO_PI = 1.8378770664093453

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

def _gamma_approx(x):


    if x <= 0.0:
        return 1.0
    if x < 1.0:
        return _gamma_approx(x + 1.0) / x
    if x < 2.0:
        t = x - 1.0


        return 1.0 - 0.4552 * t + 0.4552 * t * t

    return (x - 1.0) * _gamma_approx(x - 1.0)






def _log_likelihood_uniform(data, lo, hi):
    n = len(data)
    rng = hi - lo
    if rng <= 0.0:
        return -1e18
    for i in range(n):
        if data[i] < lo or data[i] > hi:
            return -1e18
    return -float(n) * math.log(rng)






def _erfinv_approx(p):

    x = p
    if x <= -1.0:
        x = -0.9999
    if x >= 1.0:
        x = 0.9999
    a = 0.147
    ln_term = math.log(1.0 - x * x)
    b = 2.0 / (math.pi * a) + ln_term / 2.0
    sgn = 1.0
    if x < 0.0:
        sgn = -1.0
    val = math.sqrt(math.sqrt(b * b - ln_term / a) - b)
    return sgn * val



def _normal_quantile(p):
    return math.sqrt(2.0) * _erfinv_approx(2.0 * p - 1.0)






def fit_normal(data):
    n = len(data)
    mean = 0.0
    for i in range(n):
        mean += data[i]
    mean /= float(n)
    var_sum = 0.0
    for i in range(n):
        d = data[i] - mean
        var_sum += d * d
    std = math.sqrt(var_sum / float(n))
    result = []
    result.append(mean)
    result.append(std)
    return result






def fit_exponential(data):
    n = len(data)
    s = 0.0
    for i in range(n):
        s += data[i]
    mean = s / float(n)
    if mean <= 0.0:
        return 1.0
    return 1.0 / mean






def fit_uniform(data):
    lo = data[0]
    hi = data[0]
    for i in range(1, len(data)):
        if data[i] < lo:
            lo = data[i]
        if data[i] > hi:
            hi = data[i]
    result = []
    result.append(lo)
    result.append(hi)
    return result






def fit_weibull(data):
    n = len(data)
    mean = 0.0
    for i in range(n):
        mean += data[i]
    mean /= float(n)
    var_sum = 0.0
    for i in range(n):
        d = data[i] - mean
        var_sum += d * d
    std = math.sqrt(var_sum / float(n))

    cv = std / mean if mean > 0.0 else 1.0

    shape = 1.2 / cv if cv > 0.0 else 1.0
    if shape < 0.1:
        shape = 0.1



    inv_shape = 1.0 / shape
    gamma_approx = _gamma_approx(1.0 + inv_shape)
    scale = mean / gamma_approx if gamma_approx > 0.0 else mean
    result = []
    result.append(shape)
    result.append(scale)
    return result



def log_likelihood_normal(data, mean, std):
    n = len(data)
    s = std
    if s <= 0.0:
        s = 1e-10
    ll = -float(n) * 0.5 * LOG_TWO_PI - float(n) * math.log(s)
    inv_2s2 = 1.0 / (2.0 * s * s)
    for i in range(n):
        d = data[i] - mean
        ll -= d * d * inv_2s2
    return ll






def log_likelihood_exponential(data, rate):
    n = len(data)
    r = rate
    if r <= 0.0:
        r = 1e-10
    ll = float(n) * math.log(r)
    for i in range(n):
        ll -= r * data[i]
    return ll






def aic(log_likelihood, k):
    return 2.0 * float(k) - 2.0 * log_likelihood






def bic(log_likelihood, k, n):
    return float(k) * math.log(float(n)) - 2.0 * log_likelihood






def best_fit(data):

    norm_params = fit_normal(data)
    ll_norm = log_likelihood_normal(data, norm_params[0], norm_params[1])
    aic_norm = aic(ll_norm, 2)


    rate = fit_exponential(data)
    ll_exp = log_likelihood_exponential(data, rate)
    aic_exp = aic(ll_exp, 1)


    uni_params = fit_uniform(data)
    ll_uni = _log_likelihood_uniform(data, uni_params[0], uni_params[1])
    aic_uni = aic(ll_uni, 2)


    best_idx = 0
    best_aic = aic_norm
    if aic_exp < best_aic:
        best_aic = aic_exp
        best_idx = 1
    if aic_uni < best_aic:
        best_aic = aic_uni
        best_idx = 2
    return best_idx






def qq_residuals(data, mean, std):
    n = len(data)

    sorted_data = []
    for i in range(n):
        sorted_data.append(data[i])
    for i in range(1, n):
        key = sorted_data[i]
        j = i - 1
        while j >= 0 and sorted_data[j] > key:
            sorted_data[j + 1] = sorted_data[j]
            j -= 1
        sorted_data[j + 1] = key

    residuals = []
    for i in range(n):
        p = (float(i) + 0.5) / float(n)
        expected = mean + std * _normal_quantile(p)
        residuals.append(sorted_data[i] - expected)
    return residuals
