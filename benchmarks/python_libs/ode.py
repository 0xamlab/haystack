"""Python equivalent of mojo/engine/ode.mojo (auto-generated)."""
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

class ODEResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('t_values')
        self.t_values = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('y_values')
        self.y_values = _v1 if _v1 is not None else []
    def __repr__(self):
        return f'ODEResult({vars(self)})'

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

def _poly_eval(y, coeffs):
    n = len(coeffs)
    if n == 0:
        return 0.0

    if n == 1:
        return coeffs[0] * y


    result = 0.0
    y_pow = 1.0
    for i in range(n):
        result += coeffs[i] * y_pow
        y_pow *= y
    return result



def _poly_eval_system(y, coeffs):
    n = len(y)
    dy = []
    for i in range(n):
        if i < len(coeffs):
            dy.append(coeffs[i] * y[i])
        else:
            dy.append(0.0)
    return dy






def euler_step(y, dy, dt):
    n = len(y)
    y_new = []
    for i in range(n):
        if i < len(dy):
            y_new.append(y[i] + dt * dy[i])
        else:
            y_new.append(y[i])
    return y_new



def euler_solve(y0, dy_coeffs, t_span, dt):
    n_steps = int(t_span / dt)
    if n_steps < 1:
        n_steps = 1

    history = []

    y_curr = []
    for i in range(len(y0)):
        y_curr.append(y0[i])
    history.append(y_curr.copy())

    for step in range(n_steps):
        dy = _poly_eval_system(y_curr, dy_coeffs)
        y_curr = euler_step(y_curr, dy, dt)
        history.append(y_curr.copy())

    return history






def rk4_step(y, k_coeffs, t, dt):
    k1 = _poly_eval(y, k_coeffs)
    k2 = _poly_eval(y + 0.5 * dt * k1, k_coeffs)
    k3 = _poly_eval(y + 0.5 * dt * k2, k_coeffs)
    k4 = _poly_eval(y + dt * k3, k_coeffs)
    return y + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)



def rk4_solve(y0, k_coeffs, t_start, t_end, dt):
    n_steps = int((t_end - t_start) / dt)
    if n_steps < 1:
        n_steps = 1

    result = ODEResult()

    t = t_start
    y = y0
    result.t_values.append(t)
    result.y_values.append(y)

    for i in range(n_steps):
        y = rk4_step(y, k_coeffs, t, dt)
        t = t_start + float(i + 1) * dt
        result.t_values.append(t)
        result.y_values.append(y)

    return result






def exponential_decay(y0, rate, t):
    return y0 * math.exp(-rate * t)



def logistic_growth(y0, K, r, t):
    return K * y0 / (y0 + (K - y0) * math.exp(-r * t))






def rk4_step_system(y, coeffs, t, dt):
    n = len(y)


    k1 = _poly_eval_system(y, coeffs)


    y2 = []
    for i in range(n):
        y2.append(y[i] + 0.5 * dt * k1[i])
    k2 = _poly_eval_system(y2, coeffs)


    y3 = []
    for i in range(n):
        y3.append(y[i] + 0.5 * dt * k2[i])
    k3 = _poly_eval_system(y3, coeffs)


    y4 = []
    for i in range(n):
        y4.append(y[i] + dt * k3[i])
    k4 = _poly_eval_system(y4, coeffs)


    y_new = []
    for i in range(n):
        y_new.append(
            y[i] + (dt / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i])
        )
    return y_new



def rk4_solve_system(y0, coeffs, t_start, t_end, dt):
    n_steps = int((t_end - t_start) / dt)
    if n_steps < 1:
        n_steps = 1

    history = []
    y_curr = []
    for i in range(len(y0)):
        y_curr.append(y0[i])
    history.append(y_curr.copy())

    t = t_start
    for step in range(n_steps):
        y_curr = rk4_step_system(y_curr, coeffs, t, dt)
        t = t_start + float(step + 1) * dt
        history.append(y_curr.copy())

    return history
