"""Python equivalent of mojo/engine/root_finding.mojo (auto-generated)."""
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
    from std.math import cos
except Exception:
    pass
try:
    from std.math import sin
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

def eval_func(x, func_id):
    if func_id == 0:
        return x * x - 2.0
    elif func_id == 1:
        return x * x * x - x - 2.0
    elif func_id == 2:
        return math.cos(x) - x
    elif func_id == 3:
        return math.exp(x) - 3.0 * x
    return 0.0



def eval_deriv(x, func_id):
    if func_id == 0:
        return 2.0 * x
    elif func_id == 1:
        return 3.0 * x * x - 1.0
    elif func_id == 2:
        return -math.sin(x) - 1.0
    elif func_id == 3:
        return math.exp(x) - 3.0
    return 0.0






def bisection(a, b, func_id, tol=1e-10, max_iter=100):
    lo = a
    hi = b
    fa = eval_func(lo, func_id)
    if fa * eval_func(hi, func_id) > 0.0:
        return (lo + hi) / 2.0  # fallback if bracket invalid

    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        fm = eval_func(mid, func_id)
        if math.fabs(fm) < tol or (hi - lo) / 2.0 < tol:
            return mid
        if fa * fm < 0.0:
            hi = mid
        else:
            lo = mid
            fa = fm
    return (lo + hi) / 2.0






def newton_raphson(x0, func_id, tol=1e-10, max_iter=100):
    x = x0
    for _ in range(max_iter):
        fx = eval_func(x, func_id)
        if math.fabs(fx) < tol:
            return x
        dfx = eval_deriv(x, func_id)
        if math.fabs(dfx) < 1e-15:
            break
        x = x - fx / dfx
    return x






def secant_method(x0, x1, func_id, tol=1e-10, max_iter=100):
    xp = x0
    xc = x1
    fp = eval_func(xp, func_id)
    fc = eval_func(xc, func_id)

    for _ in range(max_iter):
        if math.fabs(fc) < tol:
            return xc
        denom = fc - fp
        if math.fabs(denom) < 1e-15:
            break
        xn = xc - fc * (xc - xp) / denom
        xp = xc
        fp = fc
        xc = xn
        fc = eval_func(xc, func_id)
    return xc






def fixed_point(x0, func_id, tol=1e-10, max_iter=100):
    x = x0
    for _ in range(max_iter):
        fx = eval_func(x, func_id)
        if math.fabs(fx) < tol:
            return x
        dfx = eval_deriv(x, func_id)
        if math.fabs(dfx) < 1e-15:
            break
        xn = x - fx / dfx
        if math.fabs(xn - x) < tol:
            return xn
        x = xn
    return x






def regula_falsi(a, b, func_id, tol=1e-10, max_iter=100):
    lo = a
    hi = b
    flo = eval_func(lo, func_id)
    fhi = eval_func(hi, func_id)
    if flo * fhi > 0.0:
        return (lo + hi) / 2.0

    for _ in range(max_iter):
        c = (lo * fhi - hi * flo) / (fhi - flo)
        fc = eval_func(c, func_id)
        if math.fabs(fc) < tol:
            return c
        if flo * fc < 0.0:
            hi = c
            fhi = fc
        else:
            lo = c
            flo = fc
    return (lo * fhi - hi * flo) / (fhi - flo)






def bracket_root(func_id, start=0.0, step=0.5, max_steps=100):
    result = []
    a = start
    fa = eval_func(a, func_id)

    for i in range(1, max_steps + 1):
        b = start + float(i) * step
        fb = eval_func(b, func_id)
        if fa * fb < 0.0:
            result.append(a)
            result.append(b)
            return result

        c = start - float(i) * step
        fc = eval_func(c, func_id)
        if fa * fc < 0.0:
            result.append(c)
            result.append(a)
            return result
        a = b
        fa = fb


    result.append(start)
    result.append(start + step)
    return result






def convergence_order(errors):
    n = len(errors)
    if n < 3:
        return 0.0


    i = n - 3
    while i >= 0:
        e0 = errors[i]
        e1 = errors[i + 1]
        e2 = errors[i + 2]
        if e0 > 1e-15 and e1 > 1e-15 and e2 > 1e-15:
            r1 = e1 / e0
            r2 = e2 / e1
            if r1 > 1e-15 and r2 > 1e-15:
                return math.log(r2) / math.log(r1)
        i -= 1
    return 0.0
