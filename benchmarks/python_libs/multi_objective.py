"""Python equivalent of mojo/engine/multi_objective.mojo (auto-generated)."""
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

def is_dominated(a, b, maximize):
    n = len(a)
    m = len(b)
    k = len(maximize)
    count = n
    if m < count:
        count = m
    if k < count:
        count = k

    at_least_as_good = True
    strictly_better = False

    for i in range(count):
        if maximize[i]:

            if b[i] < a[i]:
                at_least_as_good = False
                break
            if b[i] > a[i]:
                strictly_better = True
        else:

            if b[i] > a[i]:
                at_least_as_good = False
                break
            if b[i] < a[i]:
                strictly_better = True

    return at_least_as_good and strictly_better






def pareto_front(objectives, maximize):
    n = len(objectives)
    if n == 0:
        return []


    dominated = []
    for i in range(n):
        dominated.append(False)


    for i in range(n):
        if dominated[i]:
            continue
        for j in range(n):
            if i == j or dominated[j]:
                continue

            if is_dominated(objectives[i], objectives[j], maximize):
                dominated[i] = True
                break


    front = []
    for i in range(n):
        if not dominated[i]:
            front.append(i)

    return front






def weighted_score(values, weights):
    n = len(values)
    m = len(weights)
    count = n if n < m else m
    total = 0.0
    for i in range(count):
        total += values[i] * weights[i]
    return total






def normalize_objectives(objectives):
    n = len(objectives)
    if n == 0:
        return []

    n_obj = len(objectives[0])
    if n_obj == 0:
        return []


    col_min = []
    col_max = []
    for j in range(n_obj):
        col_min.append(objectives[0][j])
        col_max.append(objectives[0][j])

    for i in range(1, n):
        for j in range(n_obj):
            if j < len(objectives[i]):
                v = objectives[i][j]
                if v < col_min[j]:
                    col_min[j] = v
                if v > col_max[j]:
                    col_max[j] = v


    result = []
    for i in range(n):
        row = []
        for j in range(n_obj):
            if j < len(objectives[i]):
                range_j = col_max[j] - col_min[j]
                if math.fabs(range_j) < 1e-15:
                    row.append(0.0)
                else:
                    row.append((objectives[i][j] - col_min[j]) / range_j)
            else:
                row.append(0.0)
        result.append(row)

    return result






def ideal_point(objectives, maximize):
    n = len(objectives)
    if n == 0:
        return []

    n_obj = len(objectives[0])
    ideal = []
    for j in range(n_obj):
        ideal.append(objectives[0][j])

    for i in range(1, n):
        for j in range(n_obj):
            if j < len(objectives[i]) and j < len(maximize):
                v = objectives[i][j]
                if maximize[j]:
                    if v > ideal[j]:
                        ideal[j] = v
                else:
                    if v < ideal[j]:
                        ideal[j] = v

    return ideal






def nadir_point(objectives, maximize):
    n = len(objectives)
    if n == 0:
        return []

    n_obj = len(objectives[0])
    nadir = []
    for j in range(n_obj):
        nadir.append(objectives[0][j])

    for i in range(1, n):
        for j in range(n_obj):
            if j < len(objectives[i]) and j < len(maximize):
                v = objectives[i][j]
                if maximize[j]:

                    if v < nadir[j]:
                        nadir[j] = v
                else:

                    if v > nadir[j]:
                        nadir[j] = v

    return nadir






def topsis_rank(alternatives, weights, maximize):
    n = len(alternatives)
    if n == 0:
        return []

    n_crit = len(alternatives[0])
    if n_crit == 0:
        empty = []
        for i in range(n):
            empty.append(0.0)
        return empty


    col_norms = []
    for j in range(n_crit):
        ss = 0.0
        for i in range(n):
            if j < len(alternatives[i]):
                v = alternatives[i][j]
                ss += v * v
        col_norms.append(math.sqrt(ss))


    norm_w = []
    for i in range(n):
        row = []
        for j in range(n_crit):
            v = 0.0
            if j < len(alternatives[i]):
                v = alternatives[i][j]
            norm_val = 0.0
            if col_norms[j] > 1e-15:
                norm_val = v / col_norms[j]

            w = 1.0
            if j < len(weights):
                w = weights[j]
            row.append(norm_val * w)
        norm_w.append(row)


    ideal_vals = []
    neg_ideal_vals = []
    for j in range(n_crit):
        ideal_vals.append(norm_w[0][j])
        neg_ideal_vals.append(norm_w[0][j])

    for i in range(1, n):
        for j in range(n_crit):
            v = norm_w[i][j]
            is_max = True
            if j < len(maximize):
                is_max = maximize[j]
            if is_max:
                if v > ideal_vals[j]:
                    ideal_vals[j] = v
                if v < neg_ideal_vals[j]:
                    neg_ideal_vals[j] = v
            else:
                if v < ideal_vals[j]:
                    ideal_vals[j] = v
                if v > neg_ideal_vals[j]:
                    neg_ideal_vals[j] = v


    scores = []
    for i in range(n):
        d_plus = 0.0
        d_minus = 0.0
        for j in range(n_crit):
            diff_p = norm_w[i][j] - ideal_vals[j]
            d_plus += diff_p * diff_p
            diff_n = norm_w[i][j] - neg_ideal_vals[j]
            d_minus += diff_n * diff_n
        d_plus = math.sqrt(d_plus)
        d_minus = math.sqrt(d_minus)


        denom = d_plus + d_minus
        if denom < 1e-15:
            scores.append(0.0)
        else:
            scores.append(d_minus / denom)

    return scores
