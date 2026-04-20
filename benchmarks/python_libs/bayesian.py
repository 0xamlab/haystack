"""Python equivalent of mojo/engine/bayesian.mojo (auto-generated)."""
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

def _probit(p):
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    if math.fabs(p - 0.5) < 1e-15:
        return 0.0
    pp = p
    sign = 1.0
    if p < 0.5:
        sign = -1.0
        pp = 1.0 - p
    _ = pp - 0.5

    r = 1.0 - pp  # small positive
    if r < 1e-300:
        r = 1e-300
    t = math.sqrt(-2.0 * math.log(r))
    c0 = 2.515517
    c1 = 0.802853
    c2 = 0.010328
    d1 = 1.432788
    d2 = 0.189269
    d3 = 0.001308
    z = t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)
    return sign * z



def _box_muller():
    u1 = random_float64()
    u2 = random_float64()
    if u1 < 1e-15:
        u1 = 1e-15
    return math.sqrt(-2.0 * math.log(u1)) * (2.0 * 3.141592653589793 * u2 - 3.141592653589793)





def _sample_gamma(shape):
    if shape < 1.0:

        g = _sample_gamma(shape + 1.0)
        u = random_float64()
        if u < 1e-15:
            u = 1e-15
        return g * math.exp(math.log(u) / shape)
    d = shape - 1.0 / 3.0
    c = 1.0 / math.sqrt(9.0 * d)
    while True:
        x = _box_muller()
        v = 1.0 + c * x
        if v <= 0.0:
            continue
        v = v * v * v
        u = random_float64()
        if u < 1e-15:
            u = 1e-15
        if u < 1.0 - 0.0331 * (x * x) * (x * x):
            return d * v
        if math.log(u) < 0.5 * x * x + d * (1.0 - v + math.log(v)):
            return d * v



def _sample_beta(alpha, beta):
    x = _sample_gamma(alpha)
    y = _sample_gamma(beta)
    if x + y < 1e-300:
        return 0.5
    return x / (x + y)






def beta_posterior(prior_alpha, prior_beta, successes, failures):
    result = []
    result.append(prior_alpha + float(successes))
    result.append(prior_beta + float(failures))
    return result



def beta_mean(alpha, beta):
    total = alpha + beta
    if total < 1e-15:
        return 0.5
    return alpha / total



def beta_variance(alpha, beta):
    ab = alpha + beta
    if ab < 1e-15:
        return 0.0
    return (alpha * beta) / (ab * ab * (ab + 1.0))



def beta_credible_interval(alpha, beta, mass=0.95):
    m = beta_mean(alpha, beta)
    v = beta_variance(alpha, beta)
    s = math.sqrt(v)
    z = _probit((1.0 + mass) / 2.0)
    lo = m - z * s
    hi = m + z * s

    if lo < 0.0:
        lo = 0.0
    if hi > 1.0:
        hi = 1.0
    result = []
    result.append(lo)
    result.append(hi)
    return result






def normal_posterior(prior_mean, prior_var, data_mean, data_var, n):
    prior_prec = 1.0 / prior_var if prior_var > 1e-15 else 1e15
    data_prec = float(n) / data_var if data_var > 1e-15 else 1e15
    post_prec = prior_prec + data_prec
    post_var = 1.0 / post_prec
    post_mean = (prior_prec * prior_mean + data_prec * data_mean) / post_prec
    result = []
    result.append(post_mean)
    result.append(post_var)
    return result






def poisson_posterior(prior_alpha, prior_beta, sum_x, n):
    result = []
    result.append(prior_alpha + float(sum_x))
    result.append(prior_beta + float(n))
    return result






def bayes_factor(likelihood_h1, likelihood_h0):
    if math.fabs(likelihood_h0) < 1e-300:
        return 0.0
    return likelihood_h1 / likelihood_h0






def posterior_predictive_beta(alpha, beta):
    return beta_mean(alpha, beta)






def hpd_interval_normal(mean, std, mass=0.95):
    z = _probit((1.0 + mass) / 2.0)
    result = []
    result.append(mean - z * std)
    result.append(mean + z * std)
    return result






def bayesian_ab_test(successes_a, trials_a, successes_b, trials_b, n_samples=10000):
    alpha_a = float(successes_a) + 1.0
    beta_a = float(trials_a - successes_a) + 1.0
    alpha_b = float(successes_b) + 1.0
    beta_b = float(trials_b - successes_b) + 1.0
    b_wins = 0
    for _ in range(n_samples):
        sa = _sample_beta(alpha_a, beta_a)
        sb = _sample_beta(alpha_b, beta_b)
        if sb > sa:
            b_wins += 1
    return float(b_wins) / float(n_samples)
