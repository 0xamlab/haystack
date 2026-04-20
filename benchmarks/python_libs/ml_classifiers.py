"""Python equivalent of mojo/engine/ml.classifiers.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.random import random_float64
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

def euclidean_distance(a, b):
    n = len(a)
    if len(b) < n:
        n = len(b)
    s = 0.0
    for i in range(n):
        d = a[i] - b[i]
        s += d * d
    return math.sqrt(s)



def manhattan_distance(a, b):
    n = len(a)
    if len(b) < n:
        n = len(b)
    s = 0.0
    for i in range(n):
        s += math.fabs(a[i] - b[i])
    return s



def cosine_similarity(a, b):
    n = len(a)
    if len(b) < n:
        n = len(b)

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for i in range(n):
        dot += a[i] * b[i]
        norm_a += a[i] * a[i]
        norm_b += b[i] * b[i]

    denom = math.sqrt(norm_a) * math.sqrt(norm_b)
    if denom == 0.0:
        return 0.0
    return dot / denom






def logistic_sigmoid(x):
    if x >= 500.0:
        return 1.0
    if x <= -500.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))



def softmax(values):
    n = len(values)
    result = []
    if n == 0:
        return result


    max_val = values[0]
    for i in range(1, n):
        if values[i] > max_val:
            max_val = values[i]


    sum_exp = 0.0
    for i in range(n):
        e = math.exp(values[i] - max_val)
        result.append(e)
        sum_exp += e


    if sum_exp > 0.0:
        for i in range(n):
            result[i] = result[i] / sum_exp

    return result






def knn_predict(train_x, train_y, test_point, k):
    n = len(train_x)
    if n == 0:
        return 0.0


    distances = []
    indices = []
    for i in range(n):
        distances.append(euclidean_distance(train_x[i], test_point))
        indices.append(i)


    k_actual = k
    if k_actual > n:
        k_actual = n

    for i in range(k_actual):
        min_idx = i
        for j in range(i + 1, n):
            if distances[j] < distances[min_idx]:
                min_idx = j

        tmp_d = distances[i]
        distances[i] = distances[min_idx]
        distances[min_idx] = tmp_d

        tmp_i = indices[i]
        indices[i] = indices[min_idx]
        indices[min_idx] = tmp_i



    labels = []
    for i in range(k_actual):
        labels.append(train_y[indices[i]])


    best_label = labels[0]
    best_count = 0

    for i in range(k_actual):
        count = 0
        for j in range(k_actual):

            if math.fabs(labels[i] - labels[j]) < 1e-9:
                count += 1
        if count > best_count:
            best_count = count
            best_label = labels[i]

    return best_label






def kmeans_cluster(data, k, max_iter=100):
    n = len(data)
    if n == 0 or k <= 0:
        return []

    dim = len(data[0])


    assignments = []
    for _ in range(n):
        assignments.append(0)


    centroids = []
    for _ in range(k):
        idx = int(random_float64() * float(n))
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0
        centroid = []
        for d in range(dim):
            centroid.append(data[idx][d])
        centroids.append(centroid)


    for _ in range(max_iter):
        changed = False


        for i in range(n):
            best_cluster = 0
            best_dist = 1e300
            for c in range(k):
                dist = euclidean_distance(data[i], centroids[c])
                if dist < best_dist:
                    best_dist = dist
                    best_cluster = c
            if assignments[i] != best_cluster:
                assignments[i] = best_cluster
                changed = True


        if not changed:
            break



        for c in range(k):
            for d in range(dim):
                centroids[c][d] = 0.0

        counts = []
        for _ in range(k):
            counts.append(0)

        for i in range(n):
            c = assignments[i]
            counts[c] = counts[c] + 1
            for d in range(dim):
                centroids[c][d] = centroids[c][d] + data[i][d]

        for c in range(k):
            if counts[c] > 0:
                for d in range(dim):
                    centroids[c][d] = centroids[c][d] / float(counts[c])
            else:

                idx = int(random_float64() * float(n))
                if idx >= n:
                    idx = n - 1
                if idx < 0:
                    idx = 0
                for d in range(dim):
                    centroids[c][d] = data[idx][d]

    return assignments
