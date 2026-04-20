"""Python equivalent of mojo/engine/recommender.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
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

def cosine_sim_users(ratings, u1, u2):
    n_items = len(ratings[u1])
    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for j in range(n_items):
        r1 = ratings[u1][j]
        r2 = ratings[u2][j]
        if r1 != 0.0 and r2 != 0.0:
            dot += r1 * r2
            norm1 += r1 * r1
            norm2 += r2 * r2
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (math.sqrt(norm1) * math.sqrt(norm2))






def predict_rating(ratings, user, item, k):
    n_users = len(ratings)

    sims = []
    rats = []
    for u in range(n_users):
        if u == user:
            continue
        if ratings[u][item] == 0.0:
            continue
        s = cosine_sim_users(ratings, user, u)
        if s > 0.0:
            sims.append(s)
            rats.append(ratings[u][item])

    n = len(sims)
    for i in range(1, n):
        ks = sims[i]
        kr = rats[i]
        j = i - 1
        while j >= 0 and sims[j] < ks:
            sims[j + 1] = sims[j]
            rats[j + 1] = rats[j]
            j -= 1
        sims[j + 1] = ks
        rats[j + 1] = kr
    top = k if k < n else n
    wsum = 0.0
    wdenom = 0.0
    for i in range(top):
        wsum += sims[i] * rats[i]
        wdenom += sims[i]
    if wdenom == 0.0:
        return 0.0
    return wsum / wdenom






def popularity_ranking(ratings):
    n_users = len(ratings)
    if n_users == 0:
        return []
    n_items = len(ratings[0])
    counts = []
    indices = []
    for j in range(n_items):
        c = 0
        for u in range(n_users):
            if ratings[u][j] != 0.0:
                c += 1
        counts.append(c)
        indices.append(j)

    for i in range(1, n_items):
        kc = counts[i]
        ki = indices[i]
        j = i - 1
        while j >= 0 and counts[j] < kc:
            counts[j + 1] = counts[j]
            indices[j + 1] = indices[j]
            j -= 1
        counts[j + 1] = kc
        indices[j + 1] = ki
    return indices






def mean_rating_per_item(ratings):
    n_users = len(ratings)
    if n_users == 0:
        return []
    n_items = len(ratings[0])
    result = []
    for j in range(n_items):
        s = 0.0
        c = 0
        for u in range(n_users):
            if ratings[u][j] != 0.0:
                s += ratings[u][j]
                c += 1
        if c == 0:
            result.append(0.0)
        else:
            result.append(s / float(c))
    return result






def mean_rating_per_user(ratings):
    n_users = len(ratings)
    result = []
    for u in range(n_users):
        s = 0.0
        c = 0
        n_items = len(ratings[u])
        for j in range(n_items):
            if ratings[u][j] != 0.0:
                s += ratings[u][j]
                c += 1
        if c == 0:
            result.append(0.0)
        else:
            result.append(s / float(c))
    return result






def top_n_items(item_scores, n):
    m = len(item_scores)
    scores = []
    indices = []
    for i in range(m):
        scores.append(item_scores[i])
        indices.append(i)

    for i in range(1, m):
        ks = scores[i]
        ki = indices[i]
        j = i - 1
        while j >= 0 and scores[j] < ks:
            scores[j + 1] = scores[j]
            indices[j + 1] = indices[j]
            j -= 1
        scores[j + 1] = ks
        indices[j + 1] = ki
    top = n if n < m else m
    result = []
    for i in range(top):
        result.append(indices[i])
    return result






def item_overlap(ratings, u1, u2):
    n_items = len(ratings[u1])
    count = 0
    for j in range(n_items):
        if ratings[u1][j] != 0.0 and ratings[u2][j] != 0.0:
            count += 1
    return count






def cold_start_recommend(ratings, n):
    ranked = popularity_ranking(ratings)
    top = n if n < len(ranked) else len(ranked)
    result = []
    for i in range(top):
        result.append(ranked[i])
    return result






def rmse_ratings(predicted, actual):
    n = len(actual)
    sse = 0.0
    count = 0
    for i in range(n):
        if actual[i] != 0.0:
            diff = predicted[i] - actual[i]
            sse += diff * diff
            count += 1
    if count == 0:
        return 0.0
    return math.sqrt(sse / float(count))
