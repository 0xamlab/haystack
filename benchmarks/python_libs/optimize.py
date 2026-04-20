"""Python equivalent of mojo/engine/optimize.mojo (auto-generated)."""
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
    from std.math import pow
except Exception:
    pass

_PHI = 1.6180339887498949          # golden ratio
_RESPHI = 0.3819660112501051       # 2 - phi  (= 1/phi^2)

class OptResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('x')
        self.x = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('fun')
        self.fun = _v1 if _v1 is not None else 0.0
        _v2 = args[2] if 2 < len(args) else kwargs.get('iterations')
        self.iterations = _v2 if _v2 is not None else 0
        _v3 = args[3] if 3 < len(args) else kwargs.get('converged')
        self.converged = _v3 if _v3 is not None else False
    def __repr__(self):
        return f'OptResult({vars(self)})'

class LinRegResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('slope')
        self.slope = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('intercept')
        self.intercept = _v1 if _v1 is not None else 0.0
        _v2 = args[2] if 2 < len(args) else kwargs.get('r_squared')
        self.r_squared = _v2 if _v2 is not None else 0.0
    def __repr__(self):
        return f'LinRegResult({vars(self)})'

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

def _eval_poly_deriv2(coeffs, x):
    n = len(coeffs)
    if n <= 2:
        return 0.0
    result = float(n - 1) * float(n - 2) * coeffs[n - 1]
    i = n - 2
    while i >= 2:
        result = result * x + float(i) * float(i - 1) * coeffs[i]
        i -= 1
    return result






def eval_poly(coeffs, x):
    n = len(coeffs)
    if n == 0:
        return 0.0
    result = coeffs[n - 1]
    i = n - 2
    while i >= 0:
        result = result * x + coeffs[i]
        i -= 1
    return result



def eval_poly_deriv(coeffs, x):
    n = len(coeffs)
    if n <= 1:
        return 0.0


    result = float(n - 1) * coeffs[n - 1]
    i = n - 2
    while i >= 1:
        result = result * x + float(i) * coeffs[i]
        i -= 1
    return result



def minimize_scalar_golden(f_coeffs, a, b, tol=1e-8, max_iter=1000):
    lo = a
    hi = b

    x1 = lo + _RESPHI * (hi - lo)
    x2 = hi - _RESPHI * (hi - lo)
    f1 = eval_poly(f_coeffs, x1)
    f2 = eval_poly(f_coeffs, x2)

    iters = 0
    while iters < max_iter and (hi - lo) > tol:
        if f1 < f2:

            hi = x2
            x2 = x1
            f2 = f1
            x1 = lo + _RESPHI * (hi - lo)
            f1 = eval_poly(f_coeffs, x1)
        else:

            lo = x1
            x1 = x2
            f1 = f2
            x2 = hi - _RESPHI * (hi - lo)
            f2 = eval_poly(f_coeffs, x2)
        iters += 1

    x_opt = (lo + hi) / 2.0
    f_opt = eval_poly(f_coeffs, x_opt)
    converged = (hi - lo) <= tol
    return OptResult(x_opt, f_opt, iters, converged)






def minimize_brent(f_coeffs, a, b, tol=1e-8, max_iter=200):
    lo = a
    hi = b
    x_best = lo + _RESPHI * (hi - lo)
    w = x_best
    v = x_best
    f_best = eval_poly(f_coeffs, x_best)
    fw = f_best
    fv = f_best

    d = 0.0
    e = 0.0  # distance moved in the step before last

    iters = 0
    while iters < max_iter:
        mid = 0.5 * (lo + hi)
        tol1 = tol * math.fabs(x_best) + 1e-10
        tol2 = 2.0 * tol1


        if math.fabs(x_best - mid) <= (tol2 - 0.5 * (hi - lo)):
            return OptResult(x_best, f_best, iters, True)


        do_golden = True
        if math.fabs(e) > tol1:

            r = (x_best - w) * (f_best - fv)
            q = (x_best - v) * (f_best - fw)
            p = (x_best - v) * q - (x_best - w) * r
            q = 2.0 * (q - r)
            if q > 0.0:
                p = -p
            else:
                q = -q
            r2 = e
            e = d

            if math.fabs(p) < math.fabs(0.5 * q * r2) and p > q * (lo - x_best) and p < q * (hi - x_best):

                d = p / q
                u = x_best + d
                if (u - lo) < tol2 or (hi - u) < tol2:
                    if x_best < mid:
                        d = tol1
                    else:
                        d = -tol1
                do_golden = False

        if do_golden:
            if x_best < mid:
                e = hi - x_best
            else:
                e = lo - x_best
            d = _RESPHI * e

        u = 0.0
        if math.fabs(d) >= tol1:
            u = x_best + d
        else:
            if d > 0.0:
                u = x_best + tol1
            else:
                u = x_best - tol1

        fu = eval_poly(f_coeffs, u)

        if fu <= f_best:
            if u < x_best:
                hi = x_best
            else:
                lo = x_best
            v = w
            fv = fw
            w = x_best
            fw = f_best
            x_best = u
            f_best = fu
        else:
            if u < x_best:
                lo = u
            else:
                hi = u
            if fu <= fw or w == x_best:
                v = w
                fv = fw
                w = u
                fw = fu
            elif fu <= fv or v == x_best or v == w:
                v = u
                fv = fu

        iters += 1

    return OptResult(x_best, f_best, iters, False)






def root_bisection(f_coeffs, a, b, tol=1e-10, max_iter=100):
    lo = a
    hi = b
    f_lo = eval_poly(f_coeffs, lo)
    f_hi = eval_poly(f_coeffs, hi)


    if f_lo > 0.0:
        tmp = lo
        lo = hi
        hi = tmp
        ftmp = f_lo
        f_lo = f_hi
        f_hi = ftmp

    iters = 0
    while iters < max_iter:
        mid = (lo + hi) / 2.0
        f_mid = eval_poly(f_coeffs, mid)

        if math.fabs(f_mid) < tol or (hi - lo) / 2.0 < tol:
            return OptResult(mid, f_mid, iters, True)

        if f_mid < 0.0:
            lo = mid
            f_lo = f_mid
        else:
            hi = mid
            f_hi = f_mid

        iters += 1

    x_final = (lo + hi) / 2.0
    return OptResult(x_final, eval_poly(f_coeffs, x_final), iters, False)






def root_newton(x0, f_coeffs, tol=1e-10, max_iter=50):
    x = x0

    iters = 0
    while iters < max_iter:
        fx = eval_poly(f_coeffs, x)
        fpx = eval_poly_deriv(f_coeffs, x)

        if math.fabs(fpx) < 1e-15:

            return OptResult(x, fx, iters, False)

        x_new = x - fx / fpx

        if math.fabs(x_new - x) < tol:
            return OptResult(x_new, eval_poly(f_coeffs, x_new), iters + 1, True)

        x = x_new
        iters += 1

    return OptResult(x, eval_poly(f_coeffs, x), iters, False)






def gradient_descent_1d(f_coeffs, x0, lr=0.01, tol=1e-8, max_iter=1000):
    x = x0

    iters = 0
    while iters < max_iter:
        grad = eval_poly_deriv(f_coeffs, x)

        if math.fabs(grad) < tol:
            return OptResult(x, eval_poly(f_coeffs, x), iters, True)

        x_new = x - lr * grad

        if math.fabs(x_new - x) < tol:
            return OptResult(x_new, eval_poly(f_coeffs, x_new), iters + 1, True)

        x = x_new
        iters += 1

    return OptResult(x, eval_poly(f_coeffs, x), iters, False)






def linear_regression(x, y):
    n = len(x)
    if n < 2 or len(y) < 2:
        return LinRegResult(0.0, 0.0, 0.0)
    if len(y) < n:
        n = len(y)


    sum_x = 0.0
    sum_y = 0.0
    for i in range(n):
        sum_x += x[i]
        sum_y += y[i]
    mean_x = sum_x / float(n)
    mean_y = sum_y / float(n)


    ss_xy = 0.0
    ss_xx = 0.0
    ss_yy = 0.0
    for i in range(n):
        dx = x[i] - mean_x
        dy = y[i] - mean_y
        ss_xy += dx * dy
        ss_xx += dx * dx
        ss_yy += dy * dy

    if ss_xx == 0.0:
        return LinRegResult(0.0, mean_y, 0.0)

    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x

    r_squared = 0.0
    if ss_yy > 0.0:
        r_squared = (ss_xy * ss_xy) / (ss_xx * ss_yy)

    return LinRegResult(slope, intercept, r_squared)
