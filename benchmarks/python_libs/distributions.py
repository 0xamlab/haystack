"""Python equivalent of mojo/engine/distributions.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.random import random_float64
except Exception:
    pass
try:
    from std.random import randn_float64
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import exp
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
    from std.math import pow
except Exception:
    pass
try:
    from std.math import cos
except Exception:
    pass
try:
    from std.math import pi
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

def _xorshift64(state):
    s = state; s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s


def _xr_f64(state):
    return float(state >> 11) * (1.0 / 9007199254740992.0)


def sample_normal(mu, sigma):
    return mu + sigma * randn_float64()


def sample_uniform(lo, hi):
    return lo + (hi - lo) * random_float64()


def sample_triangular(lo, mode, hi):
    u = random_float64(); r = hi - lo
    if r == 0.0:
        return lo
    fc = (mode - lo) / r
    if u < fc:
        return lo + math.sqrt(u * r * (mode - lo))
    return hi - math.sqrt((1.0 - u) * r * (hi - mode))


def sample_lognormal(mu, sigma):
    return math.exp(mu + sigma * randn_float64())


def sample_exponential(rate):
    return -math.log(max(random_float64(), 1e-15)) / rate


def sample_weibull(shape, scale):
    return scale * (-math.log(max(random_float64()) ** (1e-15)), 1.0 / shape)


def sample_gamma_mt(shape, scale):
    shape_adj = shape; boost = 1.0
    if shape < 1.0:
        shape_adj = shape + 1.0
        boost = (max(random_float64()) ** (1e-15), 1.0 / shape)
    d = shape_adj - 1.0 / 3.0
    c = 1.0 / math.sqrt(9.0 * d)
    while True:
        x = randn_float64(); v = 1.0 + c * x
        if v <= 0.0:
            continue
        v = v * v * v
        u = random_float64()
        if u < 1.0 - 0.0331 * (x * x) * (x * x):
            return boost * scale * d * v
        if math.log(u) < 0.5 * x * x + d * (1.0 - v + math.log(v)):
            return boost * scale * d * v


def sample_beta(alpha, beta):
    x = sample_gamma_mt(alpha, 1.0); y = sample_gamma_mt(beta, 1.0)
    t = x + y; return x / t if t != 0.0 else 0.5


def sample_pert(lo, likely, hi, g):
    r = hi - lo
    if r == 0.0:
        return lo
    mu = (lo + g * likely + hi) / (g + 2.0)
    alpha = (mu - lo) / r * (g + 2.0) / (1.0 + g)
    beta = ((hi - mu) / r) * (g + 2.0) / (1.0 + g)
    return lo + r * sample_beta(max(alpha, 0.01), max(beta, 0.01))


def sample_bernoulli(p):
    return 1.0 if random_float64() < p else 0.0


def sample_poisson(lam):
    if lam <= 0.0:
        return 0.0
    if lam > 30.0:
        return max(0.0, round(sample_normal(lam, math.sqrt(lam))))
    l = math.exp(-lam); k = 0.0; p = 1.0
    while p > l: k += 1.0; p *= random_float64()
    return k - 1.0


def sample_student_t(df, mu, sigma):
    n = randn_float64()
    chi2 = sample_gamma_mt(df / 2.0, 2.0)
    if chi2 <= 0.0:
        return mu
    return mu + sigma * n / math.sqrt(chi2 / df)


def sample_cauchy(location, scale):
    u = max(1e-10, min(1.0 - 1e-10, random_float64()))
    return location + scale * (2.0 * u - 1.0) / (2.0 * (u if u < 0.5 else 1.0 - u)) * 3.141592653589793


def sample_laplace(mu, b):
    u = random_float64() - 0.5
    return mu - b * (1.0 if u >= 0.0 else -1.0) * math.log(1.0 - 2.0 * math.fabs(u))


def sample_pareto(alpha, x_m):
    u = max(random_float64(), 1e-15)
    return x_m * (u) ** (-1.0 / alpha)


def sample_gumbel(mu, beta):
    u = max(1e-15, min(1.0 - 1e-15, random_float64()))
    return mu - beta * math.log(-math.log(u))


def sample_rayleigh(sigma):
    return sigma * math.sqrt(-2.0 * math.log(max(random_float64(), 1e-15)))


def sample_arcsine(lo, hi):
    u = random_float64(); s = math.sqrt(u)
    return lo + (hi - lo) * s * s


def sample_logistic(mu, s):
    u = max(1e-15, min(1.0 - 1e-15, random_float64()))
    return mu + s * math.log(u / (1.0 - u))


def sample_halfnormal(sigma):
    return math.fabs(randn_float64() * sigma)


def acos_approx(x):
    cx = max(-1.0, min(1.0, x))
    return 3.141592653589793 / 2.0 - (cx + cx*cx*cx/6.0 + 3.0*cx*cx*cx*cx*cx/40.0)


def sample_vonmises(mu, kappa):
    if kappa <= 0.0:
        return sample_uniform(0.0, 6.283185307179586)
    tau = 1.0 + math.sqrt(1.0 + 4.0 * kappa * kappa)
    rho = (tau - math.sqrt(2.0 * tau)) / (2.0 * kappa)
    r = (1.0 + rho * rho) / (2.0 * rho)
    while True:
        u1 = random_float64()
        z = math.cos(3.141592653589793 * u1) if u1 < 0.5 else -math.cos(3.141592653589793 * (u1 - 0.5))
        z_val = (1.0 + r * z) / (r + z)
        c = kappa * (r - z_val)
        u2 = random_float64()
        if c * (2.0 - c) > u2:
            return mu + (1.0 if random_float64() > 0.5 else -1.0) * acos_approx(z_val)
        if math.log(c / u2) + 1.0 >= c:
            return mu + (1.0 if random_float64() > 0.5 else -1.0) * acos_approx(z_val)


def sample_neg_binomial(r, p):
    lam = sample_gamma_mt(r, (1.0 - p) / p)
    return sample_poisson(lam)


def sample_hypergeometric(N, K, n):
    k = 0.0
    N_i = N; K_i = K; n_i = n
    while n_i > 0.0 and K_i > 0.0 and N_i > 0.0:
        prob = K_i / N_i
        if random_float64() < prob:
            k += 1.0; K_i -= 1.0
        N_i -= 1.0; n_i -= 1.0
    return k






def sample_one(dt, p0, p1, p2, p3, dv, dp):
    if dt == 0:
        return sample_normal(p0, p1)
    elif dt == 1:
        return sample_uniform(p0, p1)
    elif dt == 2:
        return sample_triangular(p0, p1, p2)
    elif dt == 3:
        return sample_lognormal(p0, p1)
    elif dt == 4:
        return p0
    elif dt == 5:
        return sample_beta(p0, p1)
    elif dt == 7:
        return sample_exponential(p0)
    elif dt == 8:
        return sample_weibull(p0, p1)
    elif dt == 9:
        return sample_gamma_mt(p0, p1)
    elif dt == 10:
        return sample_pert(p0, p1, p2, p3)
    elif dt == 11:
        return sample_bernoulli(p0)
    elif dt == 12:
        return sample_poisson(p0)
    elif dt == 13:
        u = random_float64()
        for k in range(len(dp)):
            if u <= dp[k]:
                return dv[k]
        return dv[len(dv)-1] if len(dv) > 0 else 0.0
    elif dt == 14:
        return sample_student_t(p0, p1, p2)
    elif dt == 15:
        return sample_cauchy(p0, p1)
    elif dt == 16:
        return sample_laplace(p0, p1)
    elif dt == 17:
        return sample_pareto(p0, p1)
    elif dt == 18:
        return sample_gumbel(p0, p1)
    elif dt == 19:
        return sample_rayleigh(p0)
    elif dt == 20:
        return sample_arcsine(p0, p1)
    elif dt == 21:
        return sample_logistic(p0, p1)
    elif dt == 22:
        return sample_halfnormal(p0)
    elif dt == 23:
        return sample_vonmises(p0, p1)
    elif dt == 24:
        return sample_neg_binomial(p0, p1)
    elif dt == 25:
        return sample_hypergeometric(p0, p1, p2)
    elif dt == 26:
        u = random_float64()
        for k in range(len(dp)):
            if u <= dp[k]:
                return float(k)
        return float(len(dp) - 1) if len(dp) > 0 else 0.0
    return p0
