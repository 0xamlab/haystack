"""Python equivalent of mojo/engine/optimization_meta.mojo (auto-generated)."""
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
try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import cos
except Exception:
    pass
try:
    from std.random import random_float64
except Exception:
    pass

PI = 3.141592653589793
E_CONST = 2.718281828459045

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

def eval_objective(x, func_id):
    n = len(x)
    if func_id == 0:

        s = 0.0
        for i in range(n):
            s += x[i] * x[i]
        return s
    elif func_id == 1:

        s = 10.0 * float(n)
        for i in range(n):
            s += x[i] * x[i] - 10.0 * math.cos(2.0 * math.pi * x[i])
        return s
    else:

        sum_sq = 0.0
        sum_cos = 0.0
        for i in range(n):
            sum_sq += x[i] * x[i]
            sum_cos += math.cos(2.0 * math.pi * x[i])
        nd = float(n)
        t1 = -20.0 * math.exp(-0.2 * math.sqrt(sum_sq / nd))
        t2 = -math.exp(sum_cos / nd)
        return t1 + t2 + 20.0 + E_CONST






def acceptance_probability(current_cost, new_cost, temperature):
    if new_cost < current_cost:
        return 1.0
    if temperature <= 0.0:
        return 0.0
    delta = new_cost - current_cost
    return math.exp(-delta / temperature)






def neighbor(x, step_size):
    result = []
    for i in range(len(x)):
        noise = (random_float64() * 2.0 - 1.0) * step_size
        result.append(x[i] + noise)
    return result






def simulated_annealing(x0, func_id, temp, cooling, max_iter):
    dim = len(x0)
    current = []
    for i in range(dim):
        current.append(x0[i])
    current_cost = eval_objective(current, func_id)

    best = []
    for i in range(dim):
        best.append(x0[i])
    best_cost = current_cost

    t = temp
    for _ in range(max_iter):
        step = t * 0.1
        if step < 0.001:
            step = 0.001
        candidate = neighbor(current, step)
        candidate_cost = eval_objective(candidate, func_id)
        ap = acceptance_probability(current_cost, candidate_cost, t)
        if random_float64() < ap:
            current = candidate
            current_cost = candidate_cost
        if current_cost < best_cost:
            best_cost = current_cost
            best = []
            for i in range(len(current)):
                best.append(current[i])
        t *= cooling
    return best






def particle_swarm(n_particles, dim, func_id, max_iter, bounds_lo, bounds_hi):
    w = 0.7
    c1 = 1.5
    c2 = 1.5
    span = bounds_hi - bounds_lo


    positions = []
    velocities = []
    pbest = []
    pbest_cost = []

    for _ in range(n_particles):
        pos = []
        vel = []
        for _ in range(dim):
            pos.append(bounds_lo + random_float64() * span)
            vel.append((random_float64() * 2.0 - 1.0) * span * 0.1)
        pb = []
        for j in range(dim):
            pb.append(pos[j])
        pbest_cost.append(eval_objective(pos, func_id))
        positions.append(pos)
        velocities.append(vel)
        pbest.append(pb)


    gbest = []
    for j in range(dim):
        gbest.append(pbest[0][j])
    gbest_cost = pbest_cost[0]
    for i in range(1, n_particles):
        if pbest_cost[i] < gbest_cost:
            gbest_cost = pbest_cost[i]
            gbest = []
            for j in range(dim):
                gbest.append(pbest[i][j])


    for _ in range(max_iter):
        for i in range(n_particles):
            for j in range(dim):
                r1 = random_float64()
                r2 = random_float64()
                velocities[i][j] = (
                    w * velocities[i][j]
                    + c1 * r1 * (pbest[i][j] - positions[i][j])
                    + c2 * r2 * (gbest[j] - positions[i][j])
                )
                positions[i][j] += velocities[i][j]

                if positions[i][j] < bounds_lo:
                    positions[i][j] = bounds_lo
                if positions[i][j] > bounds_hi:
                    positions[i][j] = bounds_hi
            cost = eval_objective(positions[i], func_id)
            if cost < pbest_cost[i]:
                pbest_cost[i] = cost
                for j in range(dim):
                    pbest[i][j] = positions[i][j]
                if cost < gbest_cost:
                    gbest_cost = cost
                    for j in range(dim):
                        gbest[j] = positions[i][j]
    return gbest






def random_search(dim, func_id, n_samples, bounds_lo, bounds_hi):
    span = bounds_hi - bounds_lo
    best = []
    for _ in range(dim):
        best.append(bounds_lo + random_float64() * span)
    best_cost = eval_objective(best, func_id)

    for _ in range(n_samples - 1):
        candidate = []
        for _ in range(dim):
            candidate.append(bounds_lo + random_float64() * span)
        cost = eval_objective(candidate, func_id)
        if cost < best_cost:
            best_cost = cost
            best = candidate
    return best






def hill_climbing(x0, func_id, step_size, max_iter):
    current = []
    for i in range(len(x0)):
        current.append(x0[i])
    current_cost = eval_objective(current, func_id)

    for _ in range(max_iter):
        candidate = neighbor(current, step_size)
        candidate_cost = eval_objective(candidate, func_id)
        if candidate_cost < current_cost:
            current = candidate
            current_cost = candidate_cost
    return current
