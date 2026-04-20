"""Python equivalent of mojo/engine/fuzzy_logic.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import exp
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

def triangular_mf(x, a, b, c):
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if a == b:

        if x < b:
            return 0.0
        return (c - x) / (c - b)
    if b == c:

        if x > b:
            return 0.0
        return (x - a) / (b - a)
    if x < b:
        return (x - a) / (b - a)
    return (c - x) / (c - b)






def trapezoidal_mf(x, a, b, c, d):
    if x <= a or x >= d:
        return 0.0
    if x >= b and x <= c:
        return 1.0
    if x < b:
        if a == b:
            return 1.0
        return (x - a) / (b - a)

    if c == d:
        return 1.0
    return (d - x) / (d - c)






def gaussian_mf(x, mean, sigma):
    if sigma == 0.0:
        if x == mean:
            return 1.0
        return 0.0
    diff = x - mean
    return math.exp(-(diff * diff) / (2.0 * sigma * sigma))






def fuzzy_and(a, b):
    if a < b:
        return a
    return b






def fuzzy_or(a, b):
    if a > b:
        return a
    return b






def fuzzy_not(a):
    return 1.0 - a






def defuzzify_centroid(x_values, memberships):
    n = len(x_values)
    if n == 0:
        return 0.0
    num = 0.0
    den = 0.0
    for i in range(n):
        num += x_values[i] * memberships[i]
        den += memberships[i]
    if den == 0.0:
        return 0.0
    return num / den






def defuzzify_bisector(x_values, memberships):
    n = len(x_values)
    if n == 0:
        return 0.0
    total = 0.0
    for i in range(n):
        total += memberships[i]
    if total == 0.0:
        return 0.0
    half = total / 2.0
    cumsum = 0.0
    for i in range(n):
        cumsum += memberships[i]
        if cumsum >= half:
            return x_values[i]
    return x_values[n - 1]






def defuzzify_mom(x_values, memberships):
    n = len(x_values)
    if n == 0:
        return 0.0
    max_mu = memberships[0]
    for i in range(1, n):
        if memberships[i] > max_mu:
            max_mu = memberships[i]
    total = 0.0
    count = 0
    for i in range(n):
        if math.fabs(memberships[i] - max_mu) < 1e-12:
            total += x_values[i]
            count += 1
    if count == 0:
        return 0.0
    return total / float(count)






def fuzzy_rule_eval(inputs, rule_type):
    n = len(inputs)
    if n == 0:
        return 0.0
    result = inputs[0]
    for i in range(1, n):
        if rule_type == 0:
            if inputs[i] < result:
                result = inputs[i]
        else:
            if inputs[i] > result:
                result = inputs[i]
    return result






def alpha_cut(x_values, memberships, alpha):
    result = []
    n = len(x_values)
    for i in range(n):
        if memberships[i] >= alpha:
            result.append(x_values[i])
    return result
