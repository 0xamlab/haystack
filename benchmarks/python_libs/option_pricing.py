"""Python equivalent of mojo/engine/option_pricing.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import erf
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

def _norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)






def _d1(S, K, T, r, sigma):
    return (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))



def _d2(S, K, T, r, sigma):
    return _d1(S, K, T, r, sigma) - sigma * math.sqrt(T)






def _pow_simple(base, n):
    result = 1.0
    for _ in range(n):
        result *= base
    return result






def norm_cdf(x):
    return 0.5 * (1.0 + erf(x / SQRT2))






def black_scholes_call(S, K, T, r, sigma):
    d1 = _d1(S, K, T, r, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)






def black_scholes_put(S, K, T, r, sigma):
    d1 = _d1(S, K, T, r, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)






def delta_call(S, K, T, r, sigma):
    return norm_cdf(_d1(S, K, T, r, sigma))






def gamma(S, K, T, r, sigma):
    d1 = _d1(S, K, T, r, sigma)
    return _norm_pdf(d1) / (S * sigma * math.sqrt(T))






def vega(S, K, T, r, sigma):
    d1 = _d1(S, K, T, r, sigma)
    return S * _norm_pdf(d1) * math.sqrt(T)






def theta_call(S, K, T, r, sigma):
    d1 = _d1(S, K, T, r, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    term1 = -(S * _norm_pdf(d1) * sigma) / (2.0 * math.sqrt(T))
    term2 = -r * K * math.exp(-r * T) * norm_cdf(d2)
    return term1 + term2






def put_call_parity(call_price, K, T, r, S):
    return call_price - S + K * math.exp(-r * T)






def binomial_tree_call(S, K, T, r, sigma, n_steps):
    dt = T / float(n_steps)
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    p = (math.exp(r * dt) - d) / (u - d)
    disc = math.exp(-r * dt)


    prices = []
    for i in range(n_steps + 1):
        ST = S * _pow_simple(u, n_steps - i) * _pow_simple(d, i)
        payoff = ST - K
        if payoff < 0.0:
            payoff = 0.0
        prices.append(payoff)


    for step in range(n_steps - 1, -1, -1):
        new_prices = []
        for i in range(step + 1):
            new_prices.append(disc * (p * prices[i] + (1.0 - p) * prices[i + 1]))
        prices = new_prices

    return prices[0]



def implied_volatility(market_price, S, K, T, r, is_call):
    lo = 0.001
    hi = 5.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        price = 0.0
        if is_call:
            price = black_scholes_call(S, K, T, r, mid)
        else:
            price = black_scholes_put(S, K, T, r, mid)
        if price < market_price:
            lo = mid
        else:
            hi = mid
        if math.fabs(hi - lo) < 1e-10:
            break
    return (lo + hi) / 2.0
