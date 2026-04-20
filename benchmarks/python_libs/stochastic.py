"""Python equivalent of mojo/engine/stochastic.mojo (auto-generated)."""
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
    from std.math import log
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

def _normal_random():


    u1 = 0.0
    u2 = 0.0
    s = 0.0

    while True:
        u1 = 2.0 * random_float64() - 1.0
        u2 = 2.0 * random_float64() - 1.0
        s = u1 * u1 + u2 * u2
        if s > 0.0 and s < 1.0:
            break
    factor = math.sqrt(-2.0 * math.log(s) / s)
    return u1 * factor






def random_walk_1d(n_steps):
    result = []
    result.append(0.0)
    pos = 0.0
    for _ in range(n_steps):
        if random_float64() < 0.5:
            pos += 1.0
        else:
            pos -= 1.0
        result.append(pos)
    return result






def random_walk_2d(n_steps):
    result = []
    x = 0.0
    y = 0.0
    start = []
    start.append(x)
    start.append(y)
    result.append(start)

    for _ in range(n_steps):
        r = random_float64()
        if r < 0.25:
            x += 1.0
        elif r < 0.5:
            x -= 1.0
        elif r < 0.75:
            y += 1.0
        else:
            y -= 1.0
        pt = []
        pt.append(x)
        pt.append(y)
        result.append(pt)

    return result






def brownian_motion(n_steps, dt=0.01):
    result = []
    result.append(0.0)
    pos = 0.0
    scale = math.sqrt(dt)
    for _ in range(n_steps):
        pos += _normal_random() * scale
        result.append(pos)
    return result






def geometric_brownian_motion(s0, mu, sigma, dt, n_steps):
    result = []
    result.append(s0)
    s = s0
    drift = (mu - 0.5 * sigma * sigma) * dt
    vol = sigma * math.sqrt(dt)
    for _ in range(n_steps):
        z = _normal_random()
        s = s * math.exp(drift + vol * z)
        result.append(s)
    return result






def poisson_process(rate, duration):
    result = []
    if rate <= 0.0 or duration <= 0.0:
        return result

    t = 0.0
    while True:

        u = random_float64()
        if u < 1e-15:
            u = 1e-15  # avoid math.log(0)
        inter = -math.log(u) / rate
        t += inter
        if t >= duration:
            break
        result.append(t)

    return result






def ornstein_uhlenbeck(x0, theta, mu, sigma, dt, n_steps):
    result = []
    result.append(x0)
    x = x0
    sqrt_dt = math.sqrt(dt)
    for _ in range(n_steps):
        dw = _normal_random() * sqrt_dt
        x = x + theta * (mu - x) * dt + sigma * dw
        result.append(x)
    return result






def birth_death_process(birth_rate, death_rate, initial, n_steps):
    result = []
    pop = initial
    if pop < 0:
        pop = 0
    result.append(pop)
    total = birth_rate + death_rate
    if total <= 0.0:
        for _ in range(n_steps):
            result.append(pop)
        return result

    p_birth = birth_rate / total
    for _ in range(n_steps):
        r = random_float64()
        if r < p_birth:
            pop += 1
        else:
            if pop > 0:
                pop -= 1
        result.append(pop)

    return result






def monte_carlo_pi(n_samples):
    if n_samples <= 0:
        return 0.0
    inside = 0
    for _ in range(n_samples):
        x = random_float64()
        y = random_float64()
        if x * x + y * y <= 1.0:
            inside += 1
    return 4.0 * float(inside) / float(n_samples)






def expected_hitting_time(p, target):
    if target <= 0:
        return 0.0
    t = float(target)
    if math.fabs(p - 0.5) < 1e-12:

        return t * t
    elif p > 0.5:
        return t / (2.0 * p - 1.0)
    else:

        return -1.0






def first_passage_time(n_simulations, target):
    if n_simulations <= 0:
        return 0.0
    abs_target = math.fabs(target)
    if abs_target < 1e-12:
        return 0.0

    total_steps = 0.0
    max_steps = 100000
    for _ in range(n_simulations):
        pos = 0.0
        steps = 0
        while steps < max_steps:
            if random_float64() < 0.5:
                pos += 1.0
            else:
                pos -= 1.0
            steps += 1
            if math.fabs(pos) >= abs_target:
                break
        total_steps += float(steps)

    return total_steps / float(n_simulations)
