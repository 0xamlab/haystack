"""Python equivalent of mojo/engine/epidemiology.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import exp
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

def sir_step(S, I, R, beta, gamma, dt):
    N = S + I + R
    dS = -beta * S * I / N * dt
    dI = (beta * S * I / N - gamma * I) * dt
    dR = gamma * I * dt
    result = []
    result.append(S + dS)
    result.append(I + dI)
    result.append(R + dR)
    return result






def sir_simulate(S0, I0, R0, beta, gamma, dt, n_steps):
    result = []
    init = []
    init.append(S0); init.append(I0); init.append(R0)
    result.append(init)
    S = S0
    I = I0
    R = R0
    for _ in range(n_steps):
        step = sir_step(S, I, R, beta, gamma, dt)
        S = step[0]
        I = step[1]
        R = step[2]
        row = []
        row.append(S); row.append(I); row.append(R)
        result.append(row)
    return result






def seir_step(S, E, I, R, beta, sigma, gamma, dt):
    N = S + math.e + I + R
    dS = -beta * S * I / N * dt
    dE = (beta * S * I / N - sigma * math.e) * dt
    dI = (sigma * math.e - gamma * I) * dt
    dR = gamma * I * dt
    result = []
    result.append(S + dS)
    result.append(math.e + dE)
    result.append(I + dI)
    result.append(R + dR)
    return result






def basic_reproduction_number(beta, gamma):
    if gamma == 0.0:
        return 0.0
    return beta / gamma






def herd_immunity_threshold(R0):
    if R0 <= 0.0:
        return 0.0
    return 1.0 - 1.0 / R0






def effective_reproduction(R0, vaccinated_fraction):
    return R0 * (1.0 - vaccinated_fraction)






def doubling_time(growth_rate):
    if growth_rate == 0.0:
        return 0.0
    return math.log(2.0) / growth_rate






def attack_rate(R0):
    if R0 <= 1.0:
        return 0.0
    z = 0.99  # initial guess
    for _ in range(200):
        z = 1.0 - math.exp(-R0 * z)
    return z






def case_fatality_rate(deaths, cases):
    if cases == 0:
        return 0.0
    return float(deaths) / float(cases)






def incidence_rate(new_cases, population, time_period):
    denom = float(population) * time_period
    if denom == 0.0:
        return 0.0
    return float(new_cases) / denom
