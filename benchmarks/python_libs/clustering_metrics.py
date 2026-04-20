"""Python equivalent of mojo/engine/clustering_metrics.mojo (auto-generated)."""
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

def _euclidean_dist(a, b):
    s = 0.0
    n = len(a)
    for i in range(n):
        d = a[i] - b[i]
        s += d * d
    return math.sqrt(s)






def _comb2(n):
    if n < 2:
        return 0
    return n * (n - 1) // 2



def cluster_sizes(labels, k):
    counts = []
    for i in range(k):
        counts.append(0)
    for i in range(len(labels)):
        c = labels[i]
        if c >= 0 and c < k:
            counts[c] += 1
    return counts






def cluster_centroids(data, labels, k):
    n = len(data)
    if n == 0:
        return []
    dim = len(data[0])

    sums = []
    counts = []
    for c in range(k):
        row = []
        for d in range(dim):
            row.append(0.0)
        sums.append(row)
        counts.append(0)

    for i in range(n):
        c = labels[i]
        if c >= 0 and c < k:
            counts[c] += 1
            for d in range(dim):
                sums[c][d] += data[i][d]

    for c in range(k):
        if counts[c] > 0:
            cnt = float(counts[c])
            for d in range(dim):
                sums[c][d] /= cnt
    return sums






def inertia(data, labels, centroids):
    total = 0.0
    n = len(data)
    for i in range(n):
        c = labels[i]
        dim = len(data[i])
        for d in range(dim):
            diff = data[i][d] - centroids[c][d]
            total += diff * diff
    return total






def davies_bouldin(data, labels, k):
    cents = cluster_centroids(data, labels, k)
    n = len(data)

    scatter = []
    sizes = cluster_sizes(labels, k)
    for c in range(k):
        scatter.append(0.0)
    for i in range(n):
        c = labels[i]
        scatter[c] += _euclidean_dist(data[i], cents[c])
    for c in range(k):
        if sizes[c] > 0:
            scatter[c] /= float(sizes[c])

    db = 0.0
    for i in range(k):
        max_r = 0.0
        for j in range(k):
            if i != j:
                d_ij = _euclidean_dist(cents[i], cents[j])
                if d_ij > 1e-15:
                    r = (scatter[i] + scatter[j]) / d_ij
                    if r > max_r:
                        max_r = r
        db += max_r
    if k > 0:
        db /= float(k)
    return db






def calinski_harabasz(data, labels, k):
    n = len(data)
    if n <= k or k <= 1:
        return 0.0
    dim = len(data[0])
    cents = cluster_centroids(data, labels, k)
    sizes = cluster_sizes(labels, k)

    global_mean = []
    for d in range(dim):
        global_mean.append(0.0)
    for i in range(n):
        for d in range(dim):
            global_mean[d] += data[i][d]
    for d in range(dim):
        global_mean[d] /= float(n)

    bg = 0.0
    for c in range(k):
        dist_sq = 0.0
        for d in range(dim):
            diff = cents[c][d] - global_mean[d]
            dist_sq += diff * diff
        bg += float(sizes[c]) * dist_sq

    wg = 0.0
    for i in range(n):
        c = labels[i]
        for d in range(dim):
            diff = data[i][d] - cents[c][d]
            wg += diff * diff
    if wg < 1e-15:
        return 0.0
    return (bg / float(k - 1)) / (wg / float(n - k))






def contingency_matrix(labels_true, labels_pred, n_true, n_pred):
    mat = []
    for i in range(n_true):
        row = []
        for j in range(n_pred):
            row.append(0)
        mat.append(row)
    n = len(labels_true)
    for i in range(n):
        t = labels_true[i]
        p = labels_pred[i]
        if t >= 0 and t < n_true and p >= 0 and p < n_pred:
            mat[t][p] += 1
    return mat






def purity(labels_true, labels_pred, n_true, n_pred):
    n = len(labels_true)
    if n == 0:
        return 0.0
    mat = contingency_matrix(labels_true, labels_pred, n_true, n_pred)
    correct = 0
    for j in range(n_pred):
        max_count = 0
        for i in range(n_true):
            if mat[i][j] > max_count:
                max_count = mat[i][j]
        correct += max_count
    return float(correct) / float(n)






def adjusted_rand_index(labels_true, labels_pred):
    n = len(labels_true)
    if n == 0:
        return 0.0

    max_true = 0
    max_pred = 0
    for i in range(n):
        if labels_true[i] > max_true:
            max_true = labels_true[i]
        if labels_pred[i] > max_pred:
            max_pred = labels_pred[i]
    n_true = max_true + 1
    n_pred = max_pred + 1
    mat = contingency_matrix(labels_true, labels_pred, n_true, n_pred)

    row_sums = []
    for i in range(n_true):
        s = 0
        for j in range(n_pred):
            s += mat[i][j]
        row_sums.append(s)
    col_sums = []
    for j in range(n_pred):
        s = 0
        for i in range(n_true):
            s += mat[i][j]
        col_sums.append(s)

    sum_comb = 0.0
    for i in range(n_true):
        for j in range(n_pred):
            sum_comb += float(_comb2(mat[i][j]))
    sum_row = 0.0
    for i in range(n_true):
        sum_row += float(_comb2(row_sums[i]))
    sum_col = 0.0
    for j in range(n_pred):
        sum_col += float(_comb2(col_sums[j]))
    comb_n = float(_comb2(n))
    if comb_n < 1e-15:
        return 1.0
    expected = sum_row * sum_col / comb_n
    max_index = (sum_row + sum_col) / 2.0
    denom = max_index - expected
    if math.fabs(denom) < 1e-15:
        return 1.0
    return (sum_comb - expected) / denom
