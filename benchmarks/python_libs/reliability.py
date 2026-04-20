"""Python equivalent of mojo/engine/reliability.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import pow
except Exception:
    pass
try:
    from std.math import log as math_log
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

def _comb(n, k):
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    kk = k
    if kk > n - kk:
        kk = n - kk
    result = 1
    for i in range(kk):
        result = result * (n - i) // (i + 1)
    return result



def exponential_reliability(t, lambda_rate):
    return math.exp(-lambda_rate * t)






def exponential_failure_rate(lambda_rate):
    return lambda_rate






def weibull_reliability(t, beta, eta):
    if t <= 0.0:
        return 1.0
    if eta <= 0.0:
        return 0.0
    return math.exp(-(t / eta) ** (beta))






def weibull_failure_rate(t, beta, eta):
    if t <= 0.0 or eta <= 0.0:
        return 0.0
    return (beta / eta) * (t / eta) ** (beta - 1.0)






def mtbf(failure_rate):
    if failure_rate <= 0.0:
        return 1e30
    return 1.0 / failure_rate






def availability(mtbf_val, mttr):
    denom = mtbf_val + mttr
    if denom <= 0.0:
        return 0.0
    return mtbf_val / denom






def series_reliability(reliabilities):
    result = 1.0
    for i in range(len(reliabilities)):
        result *= reliabilities[i]
    return result






def parallel_reliability(reliabilities):
    fail_product = 1.0
    for i in range(len(reliabilities)):
        fail_product *= (1.0 - reliabilities[i])
    return 1.0 - fail_product






def k_of_n_reliability(k, n, r):
    result = 0.0
    q = 1.0 - r
    for i in range(k, n + 1):
        c = float(_comb(n, i))
        result += c * (r) ** (float(i)) * (q) ** (float(n - i))
    return result






def bathtub_rate(t, beta_infant, lambda_useful, beta_wearout, eta_wearout, t_wearout):

    infant = 0.0
    if t > 0.0 and t_wearout > 0.0:
        infant = (beta_infant / t_wearout) * (t / t_wearout) ** (beta_infant - 1.0)


    useful = lambda_useful


    wearout = 0.0
    if t > t_wearout and eta_wearout > 0.0:
        tw = t - t_wearout
        wearout = (beta_wearout / eta_wearout) * (tw / eta_wearout) ** (beta_wearout - 1.0)

    return infant + useful + wearout






def mission_reliability(duration, failure_rate):
    return math.exp(-failure_rate * duration)
