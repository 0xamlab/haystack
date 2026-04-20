"""Python equivalent of mojo/engine/optimizer_full.mojo (auto-generated)."""
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

def lbfgs_two_loop_scale(s_dot_y, y_dot_y):
    if y_dot_y <= 0.0:
        return 1.0
    return s_dot_y / y_dot_y



def adadelta_update(param, gradient, eg2, edx2, rho, eps):
    new_eg2 = rho * eg2 + (1.0 - rho) * gradient * gradient
    delta = -math.sqrt(edx2 + eps) / math.sqrt(new_eg2 + eps) * gradient
    return param + delta



def nadam_update(param, m_hat, v_hat, gradient, beta1, lr, eps):
    nesterov_m = beta1 * m_hat + (1.0 - beta1) * gradient
    return param - lr * nesterov_m / (math.sqrt(v_hat) + eps)



def sophia_hessian_clip(h_diag, rho):
    if h_diag < rho:
        return rho
    return h_diag



def sophia_update(param, gradient, h_diag, lr, rho, weight_decay):
    h_clip = sophia_hessian_clip(h_diag, rho)
    return param - lr * gradient / h_clip - lr * weight_decay * param



def prodigy_d_estimate(s, g_sq_sum, d_prev, beta3):
    if g_sq_sum <= 0.0:
        return d_prev
    d_candidate = s / math.sqrt(g_sq_sum + 1.0)
    if d_candidate > d_prev:
        return d_candidate
    return d_prev



def adan_update(param, m, v, n, gradient, prev_gradient, beta1, beta2, beta3, lr, eps):
    g_diff = gradient - prev_gradient
    new_m = beta1 * m + (1.0 - beta1) * gradient
    new_v = beta2 * v + (1.0 - beta2) * g_diff
    combined_g = gradient + (1.0 - beta2) * g_diff
    new_n = beta3 * n + (1.0 - beta3) * combined_g * combined_g
    return param - lr * (new_m + (1.0 - beta2) * new_v) / (math.sqrt(new_n) + eps)



def schedule_free_update(x, z, gradient, lr, beta, weight_decay):
    z_new = z - lr * gradient - lr * weight_decay * z
    return (1.0 - beta) * z_new + beta * x



def muon_orthogonal_update(param, gradient, momentum, projection, lr, mu):
    new_m = mu * momentum + projection
    nesterov_g = mu * new_m + projection
    return param - lr * nesterov_g



def gradient_centralization(gradient, gradient_mean):
    return gradient - gradient_mean
