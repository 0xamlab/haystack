"""Python equivalent of mojo/engine/linear_programming.mojo (auto-generated)."""
import math
import random as _rng

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

def _inf():
    return 1e308






def line_intersection_2d(a1, b1, c1, a2, b2, c2):
    det = a1 * b2 - a2 * b1
    if math.fabs(det) < 1e-12:
        return []
    x = (c1 * b2 - c2 * b1) / det
    y = (a1 * c2 - a2 * c1) / det
    result = []
    result.append(x)
    result.append(y)
    return result






def is_feasible(x, A, b):
    n = len(x)
    for j in range(n):
        if x[j] < -1e-9:
            return False
    m = len(A)
    for i in range(m):
        s = 0.0
        cols = len(A[i])
        for j in range(cols):
            if j < n:
                s += A[i][j] * x[j]
        if s > b[i] + 1e-9:
            return False
    return True






def objective_value(c, x):
    s = 0.0
    n = len(c)
    for i in range(n):
        if i < len(x):
            s += c[i] * x[i]
    return s






def enumerate_vertices_2d(A, b):
    m = len(A)
    vertices = []


    all_a1 = []
    all_b1 = []
    all_c1 = []
    for i in range(m):
        all_a1.append(A[i][0])
        all_b1.append(A[i][1])
        all_c1.append(b[i])

    all_a1.append(1.0)
    all_b1.append(0.0)
    all_c1.append(0.0)

    all_a1.append(0.0)
    all_b1.append(1.0)
    all_c1.append(0.0)

    total = len(all_a1)
    for i in range(total):
        for j in range(i + 1, total):
            pt = line_intersection_2d(
                all_a1[i], all_b1[i], all_c1[i],
                all_a1[j], all_b1[j], all_c1[j],
            )
            if len(pt) == 2:
                xv = []
                xv.append(pt[0])
                xv.append(pt[1])
                if is_feasible(xv, A, b):

                    dup = False
                    for k in range(len(vertices)):
                        if math.fabs(vertices[k][0] - pt[0]) < 1e-9 and math.fabs(vertices[k][1] - pt[1]) < 1e-9:
                            dup = True
                            break
                    if not dup:
                        vertices.append(xv)
    return vertices






def lp_solve_2var(c, A, b):
    verts = enumerate_vertices_2d(A, b)
    if len(verts) == 0:
        return []

    best_val = -_inf()
    best_idx = 0
    for i in range(len(verts)):
        val = objective_value(c, verts[i])
        if val > best_val:
            best_val = val
            best_idx = i

    result = []
    result.append(verts[best_idx][0])
    result.append(verts[best_idx][1])
    result.append(best_val)
    return result






def dual_value(A, b, c):
    sol = lp_solve_2var(c, A, b)
    if len(sol) == 0:
        return 0.0
    return sol[2]






def sensitivity_rhs(c, A, b, constraint_idx, delta):
    orig = lp_solve_2var(c, A, b)
    orig_val = 0.0
    if len(orig) >= 3:
        orig_val = orig[2]

    b_new = []
    for i in range(len(b)):
        if i == constraint_idx:
            b_new.append(b[i] + delta)
        else:
            b_new.append(b[i])

    new_sol = lp_solve_2var(c, A, b_new)
    new_val = 0.0
    if len(new_sol) >= 3:
        new_val = new_sol[2]

    return new_val - orig_val






def transportation_cost(supply, demand, costs):
    m = len(supply)
    n = len(demand)
    if m == 0 or n == 0:
        return 0.0


    s = []
    for i in range(m):
        s.append(supply[i])
    d = []
    for j in range(n):
        d.append(demand[j])

    total_cost = 0.0
    i = 0
    j = 0
    while i < m and j < n:
        ship = s[i]
        if d[j] < ship:
            ship = d[j]
        total_cost += ship * costs[i][j]
        s[i] = s[i] - ship
        d[j] = d[j] - ship
        if s[i] < 1e-12:
            i += 1
        if j < n and d[j] < 1e-12:
            j += 1
    return total_cost
