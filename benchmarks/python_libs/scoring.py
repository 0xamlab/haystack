"""Python equivalent of mojo/engine/scoring.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import log
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

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))






def logit(p):
    pp = p
    if pp < 1e-15:
        pp = 1e-15
    if pp > 1.0 - 1e-15:
        pp = 1.0 - 1e-15
    return math.log(pp / (1.0 - pp))






def log_odds_to_score(log_odds, base_score=600.0, pdo=20.0):
    ln2 = math.log(2.0)
    return base_score - pdo * log_odds / ln2






def score_to_log_odds(score, base_score=600.0, pdo=20.0):
    ln2 = math.log(2.0)
    return (base_score - score) * ln2 / pdo






def woe(events, non_events, total_events, total_non_events):
    dist_e = float(events) / float(total_events)
    dist_ne = float(non_events) / float(total_non_events)

    if dist_e < 1e-15:
        dist_e = 1e-15
    if dist_ne < 1e-15:
        dist_ne = 1e-15
    return math.log(dist_ne / dist_e)






def iv(woe_values, dist_events, dist_non_events):
    total = 0.0
    n = len(woe_values)
    for i in range(n):
        total += (dist_non_events[i] - dist_events[i]) * woe_values[i]
    return total






def gini_coefficient(actual, predicted):
    n = len(actual)
    if n == 0:
        return 0.0


    indices = []
    for i in range(n):
        indices.append(i)


    for i in range(1, n):
        key = indices[i]
        j = i - 1
        while j >= 0 and predicted[indices[j]] < predicted[key]:
            indices[j + 1] = indices[j]
            j -= 1
        indices[j + 1] = key


    total_pos = 0.0
    total_neg = 0.0
    for i in range(n):
        if actual[i] > 0.5:
            total_pos += 1.0
        else:
            total_neg += 1.0

    if total_pos < 1.0 or total_neg < 1.0:
        return 0.0

    tp = 0.0
    fp = 0.0
    auc = 0.0
    prev_fpr = 0.0
    prev_tpr = 0.0

    for i in range(n):
        idx = indices[i]
        if actual[idx] > 0.5:
            tp += 1.0
        else:
            fp += 1.0
        tpr = tp / total_pos
        fpr = fp / total_neg

        auc += (fpr - prev_fpr) * (tpr + prev_tpr) / 2.0
        prev_fpr = fpr
        prev_tpr = tpr

    return 2.0 * auc - 1.0






def ks_statistic(actual, predicted):
    n = len(actual)
    if n == 0:
        return 0.0


    indices = []
    for i in range(n):
        indices.append(i)
    for i in range(1, n):
        key = indices[i]
        j = i - 1
        while j >= 0 and predicted[indices[j]] > predicted[key]:
            indices[j + 1] = indices[j]
            j -= 1
        indices[j + 1] = key

    total_pos = 0.0
    total_neg = 0.0
    for i in range(n):
        if actual[i] > 0.5:
            total_pos += 1.0
        else:
            total_neg += 1.0

    if total_pos < 1.0 or total_neg < 1.0:
        return 0.0

    cum_pos = 0.0
    cum_neg = 0.0
    max_ks = 0.0

    for i in range(n):
        idx = indices[i]
        if actual[idx] > 0.5:
            cum_pos += 1.0
        else:
            cum_neg += 1.0
        diff = math.fabs(cum_pos / total_pos - cum_neg / total_neg)
        if diff > max_ks:
            max_ks = diff

    return max_ks






def score_band(score, boundaries, labels):
    for i in range(len(boundaries)):
        if score <= boundaries[i]:
            return labels[i]
    return labels[len(labels) - 1]






def linear_score(features, weights, intercept):
    total = intercept
    n = len(features)
    for i in range(n):
        total += features[i] * weights[i]
    return total






def normalize_score(score, min_score, max_score):
    denom = max_score - min_score
    if math.fabs(denom) < 1e-15:
        return 0.0
    result = (score - min_score) / denom
    if result < 0.0:
        return 0.0
    if result > 1.0:
        return 1.0
    return result
