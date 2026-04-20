"""Python equivalent of mojo/engine/ml.clustering.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.random import random_float64
except Exception:
    pass

class KMeansResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('centroids')
        self.centroids = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('labels')
        self.labels = _v1 if _v1 is not None else []
        _v2 = args[2] if 2 < len(args) else kwargs.get('inertia')
        self.inertia = _v2 if _v2 is not None else 0.0
        _v3 = args[3] if 3 < len(args) else kwargs.get('iterations')
        self.iterations = _v3 if _v3 is not None else 0
    def __repr__(self):
        return f'KMeansResult({vars(self)})'

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

def euclidean_distance(a, b):
    n = len(a)
    if len(b) < n:
        n = len(b)
    s = 0.0
    for i in range(n):
        d = a[i] - b[i]
        s += d * d
    return math.sqrt(s)






def assign_cluster(point, centroids):
    k = len(centroids)
    if k == 0:
        return 0
    best = 0
    best_dist = euclidean_distance(point, centroids[0])
    for c in range(1, k):
        d = euclidean_distance(point, centroids[c])
        if d < best_dist:
            best_dist = d
            best = c
    return best






def kmeans(data, k, max_iter=100, tol=1e-6):
    result = KMeansResult()
    n = len(data)
    if n == 0 or k <= 0:
        return result

    dim = len(data[0])


    for _ in range(n):
        result.labels.append(0)


    centroids = []
    used = []
    for _ in range(k):
        idx = int(random_float64() * float(n))
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0

        attempts = 0
        while attempts < 10:
            is_dup = False
            for u in range(len(used)):
                if used[u] == idx:
                    is_dup = True
                    break
            if not is_dup:
                break
            idx = (idx + 1) % n
            attempts += 1
        used.append(idx)
        centroid = []
        for d in range(dim):
            centroid.append(data[idx][d])
        centroids.append(centroid)


    iters = 0
    for it in range(max_iter):
        iters = it + 1


        for i in range(n):
            result.labels[i] = assign_cluster(data[i], centroids)


        new_centroids = []
        counts = []
        for _ in range(k):
            c = []
            for _ in range(dim):
                c.append(0.0)
            new_centroids.append(c)
            counts.append(0)

        for i in range(n):
            label = result.labels[i]
            counts[label] = counts[label] + 1
            for d in range(dim):
                new_centroids[label][d] = new_centroids[label][d] + data[i][d]

        for c in range(k):
            if counts[c] > 0:
                for d in range(dim):
                    new_centroids[c][d] = new_centroids[c][d] / float(counts[c])
            else:

                idx = int(random_float64() * float(n))
                if idx >= n:
                    idx = n - 1
                if idx < 0:
                    idx = 0
                for d in range(dim):
                    new_centroids[c][d] = data[idx][d]


        max_shift = 0.0
        for c in range(k):
            shift = euclidean_distance(centroids[c], new_centroids[c])
            if shift > max_shift:
                max_shift = shift


        centroids = new_centroids

        if max_shift < tol:
            break


    inertia = 0.0
    for i in range(n):
        d = euclidean_distance(data[i], centroids[result.labels[i]])
        inertia += d * d

    result.centroids = centroids
    result.inertia = inertia
    result.iterations = iters

    return result






def silhouette_score(data, labels):
    n = len(data)
    if n < 2:
        return 0.0


    max_label = 0
    for i in range(n):
        if labels[i] > max_label:
            max_label = labels[i]
    k = max_label + 1
    if k < 2:
        return 0.0

    total_silhouette = 0.0

    for i in range(n):
        label_i = labels[i]


        sum_same = 0.0
        count_same = 0
        sum_other = []
        count_other = []
        for _ in range(k):
            sum_other.append(0.0)
            count_other.append(0)

        for j in range(n):
            if i == j:
                continue
            d = euclidean_distance(data[i], data[j])
            if labels[j] == label_i:
                sum_same += d
                count_same += 1
            else:
                sum_other[labels[j]] = sum_other[labels[j]] + d
                count_other[labels[j]] = count_other[labels[j]] + 1

        a_i = 0.0
        if count_same > 0:
            a_i = sum_same / float(count_same)


        b_i = 1e300
        for c in range(k):
            if c == label_i:
                continue
            if count_other[c] > 0:
                mean_d = sum_other[c] / float(count_other[c])
                if mean_d < b_i:
                    b_i = mean_d

        if b_i > 1e299:
            b_i = 0.0

        denom = a_i
        if b_i > denom:
            denom = b_i
        s_i = 0.0
        if denom > 1e-15:
            s_i = (b_i - a_i) / denom

        total_silhouette += s_i

    return total_silhouette / float(n)
