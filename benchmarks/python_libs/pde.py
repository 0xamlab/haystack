"""Python equivalent of mojo/engine/pde.mojo (auto-generated)."""
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

def heat_equation_1d(u0, alpha, dx, dt, n_steps):
    n = len(u0)
    if n < 3:
        return u0.copy()
    r = alpha * dt / (dx * dx)
    u = u0.copy()
    u_new = []
    for _i in range(n):
        u_new.append(0.0)

    for _step in range(n_steps):
        u_new[0] = 0.0
        u_new[n - 1] = 0.0
        for i in range(1, n - 1):
            u_new[i] = u[i] + r * (u[i + 1] - 2.0 * u[i] + u[i - 1])

        for i in range(n):
            u[i] = u_new[i]
    return u






def wave_equation_1d(u0, v0, c, dx, dt, n_steps):
    n = len(u0)
    if n < 3:
        return u0.copy()
    r2 = (c * dt / dx) * (c * dt / dx)


    u_prev = u0.copy()
    u_curr = []
    for _i in range(n):
        u_curr.append(0.0)


    u_curr[0] = 0.0
    u_curr[n - 1] = 0.0
    for i in range(1, n - 1):
        u_curr[i] = (
            u_prev[i]
            + v0[i] * dt
            + 0.5 * r2 * (u_prev[i + 1] - 2.0 * u_prev[i] + u_prev[i - 1])
        )

    if n_steps <= 1:
        return u_curr

    u_next = []
    for _i in range(n):
        u_next.append(0.0)

    for _step in range(1, n_steps):
        u_next[0] = 0.0
        u_next[n - 1] = 0.0
        for i in range(1, n - 1):
            u_next[i] = (
                2.0 * u_curr[i]
                - u_prev[i]
                + r2 * (u_curr[i + 1] - 2.0 * u_curr[i] + u_curr[i - 1])
            )
        for i in range(n):
            u_prev[i] = u_curr[i]
            u_curr[i] = u_next[i]

    return u_curr






def laplace_2d(u, n_iter):
    nrows = len(u)
    if nrows < 3:
        return u.copy()

    ncols = len(u[0])
    if ncols < 3:
        return u.copy()


    curr = []
    for i in range(nrows):
        row = []
        for j in range(ncols):
            row.append(u[i][j])
        curr.append(row)

    next_ = []
    for i in range(nrows):
        row = []
        for j in range(ncols):
            row.append(u[i][j])
        next_.append(row)

    for _it in range(n_iter):
        for i in range(1, nrows - 1):
            for j in range(1, ncols - 1):
                next_[i][j] = 0.25 * (
                    curr[i + 1][j] + curr[i - 1][j]
                    + curr[i][j + 1] + curr[i][j - 1]
                )
        for i in range(1, nrows - 1):
            for j in range(1, ncols - 1):
                curr[i][j] = next_[i][j]

    return curr






def diffusion_cfl(alpha, dx):
    if alpha <= 0.0:
        return 1e30
    return dx * dx / (2.0 * alpha)






def wave_cfl(c, dx):
    if c <= 0.0:
        return 1e30
    return dx / c






def is_stable_heat(alpha, dx, dt):
    dt_max = diffusion_cfl(alpha, dx)
    return dt <= dt_max






def finite_difference_second(u, dx):
    n = len(u)
    result = []
    for _i in range(n):
        result.append(0.0)
    dx2 = dx * dx
    for i in range(1, n - 1):
        result[i] = (u[i + 1] - 2.0 * u[i] + u[i - 1]) / dx2
    return result






def gaussian_initial(n, center, width):
    result = []
    if n <= 1:
        result.append(math.exp(-(0.0 - center) * (0.0 - center) / (width * width)))
        return result
    dx = 1.0 / float(n - 1)
    for i in range(n):
        x = float(i) * dx
        d = x - center
        result.append(math.exp(-d * d / (width * width)))
    return result






def max_norm(u):
    m = 0.0
    for i in range(len(u)):
        a = math.fabs(u[i])
        if a > m:
            m = a
    return m






def energy(u, dx):
    s = 0.0
    for i in range(len(u)):
        s += u[i] * u[i] * dx
    return s
