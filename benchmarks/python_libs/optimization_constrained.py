"""Python equivalent of mojo/engine/optimization_constrained.mojo (auto-generated)."""
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

def _penalized_objective(x, func_id, constraints, mu):
    return eval_objective_c(x, func_id) + mu * penalty_value(x, constraints)






def _barrier_objective(x, func_id, constraints, mu):
    obj = eval_objective_c(x, func_id)
    for i in range(len(constraints)):
        g = eval_constraint(x, constraints[i])
        if g >= 0.0:
            return 1e18  # infeasible
        obj -= mu * math.log(-g)
    return obj



def _barrier_gradient(x, func_id, constraints, mu, h=1e-5):
    n = len(x)
    grad = []
    for i in range(n):
        xp = []
        xm = []
        for j in range(n):
            xp.append(x[j])
            xm.append(x[j])
        xp[i] = x[i] + h
        xm[i] = x[i] - h
        fp = _barrier_objective(xp, func_id, constraints, mu)
        fm = _barrier_objective(xm, func_id, constraints, mu)
        grad.append((fp - fm) / (2.0 * h))
    return grad



def eval_objective_c(x, func_id):
    if func_id == 0:
        s = 0.0
        for i in range(len(x)):
            s += x[i] * x[i]
        return s
    elif func_id == 1:
        if len(x) >= 2:
            return -(x[0] * x[1])
        return 0.0
    elif func_id == 2:
        s = 0.0
        for i in range(len(x)):
            s += x[i]
        return s
    return 0.0






def eval_constraint(x, constraint_id):
    if len(x) < 2:
        return 0.0
    if constraint_id == 0:
        return x[0] + x[1] - 1.0
    elif constraint_id == 1:
        return x[0] * x[0] + x[1] * x[1] - 1.0
    elif constraint_id == 2:
        return -x[0]
    elif constraint_id == 3:
        return -x[1]
    return 0.0






def is_feasible_c(x, constraints, tol=1e-6):
    for i in range(len(constraints)):
        g = eval_constraint(x, constraints[i])
        if g > tol:
            return False
    return True



def penalty_value(x, constraints):
    total = 0.0
    for i in range(len(constraints)):
        g = eval_constraint(x, constraints[i])
        if g > 0.0:
            total += g * g
    return total






def gradient_estimate(x, func_id, constraints, mu, h=1e-5):
    n = len(x)
    grad = []
    for i in range(n):
        xp = []
        xm = []
        for j in range(n):
            xp.append(x[j])
            xm.append(x[j])
        xp[i] = x[i] + h
        xm[i] = x[i] - h
        fp = _penalized_objective(xp, func_id, constraints, mu)
        fm = _penalized_objective(xm, func_id, constraints, mu)
        grad.append((fp - fm) / (2.0 * h))
    return grad






def penalty_method(x0, func_id, constraints, mu, max_iter, lr):
    n = len(x0)
    x = []
    for i in range(n):
        x.append(x0[i])
    cur_mu = mu
    for _iter in range(max_iter):
        grad = gradient_estimate(x, func_id, constraints, cur_mu)
        for i in range(n):
            x[i] = x[i] - lr * grad[i]

        if (_iter + 1) % 10 == 0:
            cur_mu = cur_mu * 2.0
    return x






def barrier_method(x0, func_id, constraints, mu, max_iter, lr):
    n = len(x0)
    x = []
    for i in range(n):
        x.append(x0[i])
    cur_mu = mu
    for _iter in range(max_iter):
        grad = _barrier_gradient(x, func_id, constraints, cur_mu)

        step = lr
        x_new = []
        for i in range(n):
            x_new.append(x[i] - step * grad[i])

        feasible = True
        for i in range(len(constraints)):
            if eval_constraint(x_new, constraints[i]) >= 0.0:
                feasible = False
                break
        if feasible:
            x = x_new
        else:

            for _bt in range(20):
                step = step * 0.5
                x_new = []
                for i in range(n):
                    x_new.append(x[i] - step * grad[i])
                ok = True
                for i in range(len(constraints)):
                    if eval_constraint(x_new, constraints[i]) >= 0.0:
                        ok = False
                        break
                if ok:
                    x = x_new
                    break

        if (_iter + 1) % 10 == 0:
            cur_mu = cur_mu * 0.5
    return x






def augmented_lagrangian_step(x, lambdas, func_id, constraints, mu, lr):
    n = len(x)
    nc = len(constraints)

    grad = gradient_estimate(x, func_id, constraints, mu)

    h = 1e-5
    for i in range(n):
        extra = 0.0
        for ci in range(nc):
            xp = []
            xm = []
            for j in range(n):
                xp.append(x[j])
                xm.append(x[j])
            xp[i] = x[i] + h
            xm[i] = x[i] - h
            gp = eval_constraint(xp, constraints[ci])
            gm = eval_constraint(xm, constraints[ci])
            dg = (gp - gm) / (2.0 * h)
            extra += lambdas[ci] * dg
        grad[i] = grad[i] + extra


    new_x = []
    for i in range(n):
        new_x.append(x[i] - lr * grad[i])


    new_lambdas = []
    for i in range(nc):
        g = eval_constraint(new_x, constraints[i])
        lam = lambdas[i] + mu * g
        if lam < 0.0:
            lam = 0.0
        new_lambdas.append(lam)

    result = []
    result.append(new_x)
    result.append(new_lambdas)
    return result
