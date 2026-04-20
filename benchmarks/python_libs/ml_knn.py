"""Python equivalent of mojo/engine/ml.knn.mojo (auto-generated)."""
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

def _majority_vote(labels):
    n = len(labels)
    if n == 0:
        return 0
    best_label = labels[0]
    best_count = 0
    for i in range(n):
        count = 0
        for j in range(n):
            if labels[j] == labels[i]:
                count += 1
        if count > best_count:
            best_count = count
            best_label = labels[i]
    return best_label






def euclidean_distance_knn(a, b):
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






def knn_distances(X_train, x_test):
    result = []
    for i in range(len(X_train)):
        result.append(euclidean_distance_knn(X_train[i], x_test))
    return result






def k_nearest_indices(distances, k):
    n = len(distances)
    actual_k = k
    if actual_k > n:
        actual_k = n
    used = []
    for i in range(n):
        used.append(False)
    indices = []
    for _i in range(actual_k):
        best_idx = -1
        best_dist = 1e300
        for j in range(n):
            if not used[j] and distances[j] < best_dist:
                best_dist = distances[j]
                best_idx = j
        if best_idx >= 0:
            indices.append(best_idx)
            used[best_idx] = True
    return indices






def knn_predict(X_train, y_train, x_test, k):
    dists = knn_distances(X_train, x_test)
    indices = k_nearest_indices(dists, k)
    neighbor_labels = []
    for i in range(len(indices)):
        neighbor_labels.append(y_train[indices[i]])
    return _majority_vote(neighbor_labels)






def knn_predict_batch(X_train, y_train, X_test, k):
    result = []
    for i in range(len(X_test)):
        result.append(knn_predict(X_train, y_train, X_test[i], k))
    return result






def weighted_knn_predict(X_train, y_train, x_test, k):
    dists = knn_distances(X_train, x_test)
    indices = k_nearest_indices(dists, k)


    classes = []
    for i in range(len(indices)):
        label = y_train[indices[i]]
        found = False
        for j in range(len(classes)):
            if classes[j] == label:
                found = True
                break
        if not found:
            classes.append(label)

    best_class = 0
    best_weight = -1.0
    for c in range(len(classes)):
        w = 0.0
        for i in range(len(indices)):
            if y_train[indices[i]] == classes[c]:
                d = dists[indices[i]]
                if d < 1e-15:
                    w += 1e12
                else:
                    w += 1.0 / d
        if w > best_weight:
            best_weight = w
            best_class = classes[c]
    return best_class






def knn_regression(X_train, y_train, x_test, k):
    dists = knn_distances(X_train, x_test)
    indices = k_nearest_indices(dists, k)
    if len(indices) == 0:
        return 0.0
    s = 0.0
    for i in range(len(indices)):
        s += y_train[indices[i]]
    return s / float(len(indices))






def leave_one_out_cv(X, y, k):
    n = len(X)
    if n <= 1:
        return 0.0
    correct = 0
    for i in range(n):
        X_train = []
        y_train = []
        for j in range(n):
            if j != i:
                X_train.append(X[j].copy())
                y_train.append(y[j])
        pred = knn_predict(X_train, y_train, X[i], k)
        if pred == y[i]:
            correct += 1
    return float(correct) / float(n)






def optimal_k(X, y, max_k):
    n = len(X)
    limit = max_k
    if limit >= n:
        limit = n - 1
    if limit < 1:
        limit = 1
    best_k = 1
    best_acc = -1.0
    for k in range(1, limit + 1):
        acc = leave_one_out_cv(X, y, k)
        if acc > best_acc:
            best_acc = acc
            best_k = k
    return best_k
