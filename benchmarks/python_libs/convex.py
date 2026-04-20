"""Python equivalent of mojo/engine/convex.mojo (auto-generated)."""
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

def eval_function(x, func_id):
    n = len(x)
    if func_id == 0:
        s = 0.0
        for i in range(n):
            s += x[i] * x[i]
        return s
    elif func_id == 1:
        s = 0.0
        for i in range(n - 1):
            xi = x[i]
            xi1 = x[i + 1]
            a = xi1 - xi * xi
            b = 1.0 - xi
            s += 100.0 * a * a + b * b
        return s
    return 0.0






def compute_gradient(x, func_id):
    n = len(x)
    g = []
    for _ in range(n):
        g.append(0.0)

    if func_id == 0:
        for i in range(n):
            g[i] = 2.0 * x[i]
    elif func_id == 1:
        for i in range(n):
            if i < n - 1:
                xi = x[i]
                xi1 = x[i + 1]
                g[i] += -400.0 * xi * (xi1 - xi * xi) - 2.0 * (1.0 - xi)
            if i > 0:
                xim1 = x[i - 1]
                g[i] += 200.0 * (x[i] - xim1 * xim1)
    return g






def l2_norm(x):
    s = 0.0
    for i in range(len(x)):
        s += x[i] * x[i]
    return math.sqrt(s)






def vector_sub(a, b):
    n = len(a)
    result = []
    for i in range(n):
        result.append(a[i] - b[i])
    return result






def proximal_l1(x, lambda_val):
    n = len(x)
    result = []
    for i in range(n):
        ax = math.fabs(x[i])
        shrunk = ax - lambda_val
        if shrunk < 0.0:
            shrunk = 0.0
        sign = 1.0
        if x[i] < 0.0:
            sign = -1.0
        elif x[i] == 0.0:
            sign = 0.0
        result.append(sign * shrunk)
    return result






def line_search_backtrack(x, grad, func_id, alpha=1.0, beta=0.5, sigma=0.1):
    fx = eval_function(x, func_id)
    grad_sq = 0.0
    for i in range(len(grad)):
        grad_sq += grad[i] * grad[i]

    t = alpha
    n = len(x)
    for _ in range(50):
        x_new = []
        for i in range(n):
            x_new.append(x[i] - t * grad[i])
        fx_new = eval_function(x_new, func_id)
        if fx_new <= fx - sigma * t * grad_sq:
            return t
        t *= beta
    return t






def gradient_descent(x0, learning_rate, max_iter, tol, func_id):
    n = len(x0)
    x = []
    for i in range(n):
        x.append(x0[i])

    for _ in range(max_iter):
        g = compute_gradient(x, func_id)
        gnorm = l2_norm(g)
        if gnorm < tol:
            break
        for i in range(n):
            x[i] = x[i] - learning_rate * g[i]
    return x






def projected_gradient_descent(x0, lr, max_iter, lower, upper, func_id):
    n = len(x0)
    x = []
    for i in range(n):
        x.append(x0[i])

    for _ in range(max_iter):
        g = compute_gradient(x, func_id)
        for i in range(n):
            x[i] = x[i] - lr * g[i]

            if x[i] < lower:
                x[i] = lower
            elif x[i] > upper:
                x[i] = upper
    return x






def adam_optimizer(x0, lr, max_iter, func_id):
    beta1 = 0.9
    beta2 = 0.999
    eps = 1e-8
    n = len(x0)

    x = []
    m = []
    v = []
    for i in range(n):
        x.append(x0[i])
        m.append(0.0)
        v.append(0.0)

    b1t = 1.0
    b2t = 1.0

    for _ in range(max_iter):
        g = compute_gradient(x, func_id)
        b1t *= beta1
        b2t *= beta2

        for i in range(n):
            m[i] = beta1 * m[i] + (1.0 - beta1) * g[i]
            v[i] = beta2 * v[i] + (1.0 - beta2) * g[i] * g[i]
            m_hat = m[i] / (1.0 - b1t)
            v_hat = v[i] / (1.0 - b2t)
            x[i] = x[i] - lr * m_hat / (math.sqrt(v_hat) + eps)
    return x
