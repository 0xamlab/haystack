"""Python equivalent of mojo/engine/scipy_optimize_ops.mojo (auto-generated)."""
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

def bfgs_hessian_update_term(s, y, sy_dot):
    if sy_dot <= 0.0:
        return 0.0
    return 1.0 / sy_dot



def conjugate_gradient_beta_fr(grad_norm_sq_new, grad_norm_sq_old):
    if grad_norm_sq_old <= 0.0:
        return 0.0
    return grad_norm_sq_new / grad_norm_sq_old



def conjugate_gradient_beta_pr(grad_new, grad_old, grad_norm_sq_old):
    if grad_norm_sq_old <= 0.0:
        return 0.0
    return grad_new * (grad_new - grad_old) / grad_norm_sq_old



def armijo_condition(f_new, f_old, alpha, grad_dot_dir, c1):
    if f_new <= f_old + c1 * alpha * grad_dot_dir:
        return 1.0
    return 0.0



def wolfe_curvature_condition(grad_new_dot_dir, grad_old_dot_dir, c2):
    lhs = grad_new_dot_dir
    if lhs < 0.0:
        lhs = -lhs
    rhs = c2 * grad_old_dot_dir
    if rhs < 0.0:
        rhs = -rhs
    if lhs <= rhs:
        return 1.0
    return 0.0



def golden_section_midpoint(a, b, use_left):
    phi = 0.6180339887498949
    if use_left > 0.5:
        return b - phi * (b - a)
    return a + phi * (b - a)



def newton_step(f_val, f_prime):
    if f_prime == 0.0:
        return 0.0
    return -f_val / f_prime



def secant_step(x0, x1, f0, f1):
    df = f1 - f0
    if df == 0.0:
        return x1
    return x1 - f1 * (x1 - x0) / df



def bisection_midpoint(a, b):
    return (a + b) / 2.0



def trust_region_step_norm(grad_norm, hessian_min_eig, delta):
    if hessian_min_eig <= 0.0:
        return delta
    cauchy = grad_norm / hessian_min_eig
    if cauchy > delta:
        return delta
    return cauchy
