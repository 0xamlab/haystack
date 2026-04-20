"""Python equivalent of mojo/engine/allocation.mojo (auto-generated)."""
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

def equal_weight(n_assets):
    w = []
    if n_assets <= 0:
        return w
    wt = 1.0 / float(n_assets)
    for _ in range(n_assets):
        w.append(wt)
    return w






def inverse_variance(variances):
    n = len(variances)
    w = []
    if n == 0:
        return w
    total = 0.0
    for i in range(n):
        v = variances[i]
        if v <= 0.0:
            v = 1e-10
        total += 1.0 / v
    for i in range(n):
        v = variances[i]
        if v <= 0.0:
            v = 1e-10
        w.append((1.0 / v) / total)
    return w






def risk_parity_simple(variances):
    n = len(variances)
    w = []
    if n == 0:
        return w
    total = 0.0
    for i in range(n):
        v = variances[i]
        if v <= 0.0:
            v = 1e-10
        total += 1.0 / math.sqrt(v)
    for i in range(n):
        v = variances[i]
        if v <= 0.0:
            v = 1e-10
        w.append((1.0 / math.sqrt(v)) / total)
    return w






def max_sharpe_2asset(r1, r2, s1, s2, rho, rf):
    er1 = r1 - rf
    er2 = r2 - rf
    cov12 = rho * s1 * s2
    num = er1 * s2 * s2 - er2 * cov12
    den = er1 * s2 * s2 + er2 * s1 * s1 - (er1 + er2) * cov12
    w1 = 0.5
    if math.fabs(den) > 1e-15:
        w1 = num / den

    if w1 < 0.0:
        w1 = 0.0
    if w1 > 1.0:
        w1 = 1.0
    w = []
    w.append(w1)
    w.append(1.0 - w1)
    return w






def min_variance_2asset(s1, s2, rho):
    cov12 = rho * s1 * s2
    num = s2 * s2 - cov12
    den = s1 * s1 + s2 * s2 - 2.0 * cov12
    w1 = 0.5
    if math.fabs(den) > 1e-15:
        w1 = num / den
    if w1 < 0.0:
        w1 = 0.0
    if w1 > 1.0:
        w1 = 1.0
    w = []
    w.append(w1)
    w.append(1.0 - w1)
    return w






def portfolio_return(weights, returns):
    n = len(weights)
    m = len(returns)
    sz = n if n < m else m
    total = 0.0
    for i in range(sz):
        total += weights[i] * returns[i]
    return total






def portfolio_variance_2asset(w1, s1, s2, rho):
    w2 = 1.0 - w1
    return (
        w1 * w1 * s1 * s1
        + w2 * w2 * s2 * s2
        + 2.0 * w1 * w2 * rho * s1 * s2
    )






def kelly_criterion(win_prob, win_ratio):
    if win_ratio <= 0.0:
        return 0.0
    return win_prob - (1.0 - win_prob) / win_ratio






def efficient_frontier_2asset(r1, r2, s1, s2, rho, n_points):
    frontier = []
    if n_points <= 0:
        return frontier
    step = 1.0
    if n_points > 1:
        step = 1.0 / float(n_points - 1)
    for i in range(n_points):
        w1 = float(i) * step
        if w1 > 1.0:
            w1 = 1.0
        w2 = 1.0 - w1
        ret = w1 * r1 + w2 * r2
        var_ = portfolio_variance_2asset(w1, s1, s2, rho)
        risk = math.sqrt(var_)
        point = []
        point.append(ret)
        point.append(risk)
        frontier.append(point)
    return frontier






def rebalance_threshold(current_weights, target_weights, threshold):
    n = len(current_weights)
    m = len(target_weights)
    sz = n if n < m else m
    for i in range(sz):
        if math.fabs(current_weights[i] - target_weights[i]) > threshold:
            return True
    return False
