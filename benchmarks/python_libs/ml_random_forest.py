"""Python equivalent of mojo/engine/ml.random_forest.mojo (auto-generated)."""
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

def _mean(vals):
    if len(vals) == 0:
        return 0.0
    s = 0.0
    for i in range(len(vals)):
        s += vals[i]
    return s / float(len(vals))



def _variance(vals):
    if len(vals) <= 1:
        return 0.0
    m = _mean(vals)
    s = 0.0
    for i in range(len(vals)):
        d = vals[i] - m
        s += d * d
    return s / float(len(vals))



def _sse(vals):
    if len(vals) == 0:
        return 0.0
    m = _mean(vals)
    s = 0.0
    for i in range(len(vals)):
        d = vals[i] - m
        s += d * d
    return s



def bootstrap_indices(n, sample_size):
    result = []
    for _ in range(sample_size):
        idx = int(random_float64() * float(n))
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0
        result.append(idx)
    return result



def feature_subsample(n_features, max_features):
    m = max_features
    if m > n_features:
        m = n_features

    arr = []
    for i in range(n_features):
        arr.append(i)

    for i in range(m):
        remaining = n_features - i
        j = i + int(random_float64() * float(remaining))
        if j >= n_features:
            j = n_features - 1

        tmp = arr[i]
        arr[i] = arr[j]
        arr[j] = tmp
    result = []
    for i in range(m):
        result.append(arr[i])
    return result






def tree_predict_simple(X_train, y_train, x_test, feature_subset):
    n = len(X_train)
    if n == 0:
        return 0.0
    best_feat = 0
    best_thresh = 0.0
    best_reduction = -1.0
    total_sse = _sse(y_train)

    for fi in range(len(feature_subset)):
        f = feature_subset[fi]

        fmin = X_train[0][f]
        fmax = X_train[0][f]
        for i in range(1, n):
            if X_train[i][f] < fmin:
                fmin = X_train[i][f]
            if X_train[i][f] > fmax:
                fmax = X_train[i][f]
        if fmax - fmin < 1e-12:
            continue

        for t in range(1, 6):
            thresh = fmin + float(t) / 6.0 * (fmax - fmin)
            left = []
            right = []
            for i in range(n):
                if X_train[i][f] <= thresh:
                    left.append(y_train[i])
                else:
                    right.append(y_train[i])
            if len(left) == 0 or len(right) == 0:
                continue
            reduction = total_sse - _sse(left) - _sse(right)
            if reduction > best_reduction:
                best_reduction = reduction
                best_feat = f
                best_thresh = thresh


    if best_reduction < 0.0:
        return _mean(y_train)
    left_vals = []
    right_vals = []
    for i in range(n):
        if X_train[i][best_feat] <= best_thresh:
            left_vals.append(y_train[i])
        else:
            right_vals.append(y_train[i])
    if x_test[best_feat] <= best_thresh:
        return _mean(left_vals)
    return _mean(right_vals)






def random_forest_predict(X_train, y_train, x_test, n_trees, max_features):
    n = len(X_train)
    if n == 0:
        return 0.0
    n_feat = len(X_train[0])
    total = 0.0
    for _t in range(n_trees):
        idxs = bootstrap_indices(n, n)
        X_b = []
        y_b = []
        for i in range(len(idxs)):
            X_b.append(X_train[idxs[i]].copy())
            y_b.append(y_train[idxs[i]])
        feats = feature_subsample(n_feat, max_features)
        total += tree_predict_simple(X_b, y_b, x_test, feats)
    return total / float(n_trees)



def random_forest_predict_batch(X_train, y_train, X_test, n_trees, max_features):
    result = []
    for i in range(len(X_test)):
        result.append(
            random_forest_predict(X_train, y_train, X_test[i], n_trees, max_features)
        )
    return result






def oob_score(X, y, n_trees, max_features):
    n = len(X)
    if n == 0:
        return 0.0
    n_feat = len(X[0])
    oob_sum = []
    oob_count = []
    for _i in range(n):
        oob_sum.append(0.0)
        oob_count.append(0)

    for _t in range(n_trees):
        idxs = bootstrap_indices(n, n)

        in_bag = []
        for _i in range(n):
            in_bag.append(False)
        for i in range(len(idxs)):
            in_bag[idxs[i]] = True

        X_b = []
        y_b = []
        for i in range(len(idxs)):
            X_b.append(X[idxs[i]].copy())
            y_b.append(y[idxs[i]])
        feats = feature_subsample(n_feat, max_features)

        for i in range(n):
            if not in_bag[i]:
                pred = tree_predict_simple(X_b, y_b, X[i], feats)
                oob_sum[i] = oob_sum[i] + pred
                oob_count[i] = oob_count[i] + 1


    y_mean = _mean(y)
    ss_res = 0.0
    ss_tot = 0.0
    valid = 0
    for i in range(n):
        if oob_count[i] > 0:
            pred = oob_sum[i] / float(oob_count[i])
            ss_res += (y[i] - pred) * (y[i] - pred)
            ss_tot += (y[i] - y_mean) * (y[i] - y_mean)
            valid += 1
    if ss_tot < 1e-15 or valid == 0:
        return 0.0
    return 1.0 - ss_res / ss_tot






def feature_importance_rf(X, y, n_trees, max_features):
    n = len(X)
    if n == 0:
        return []
    n_feat = len(X[0])

    preds = random_forest_predict_batch(X, y, X, n_trees, max_features)
    base_mse = 0.0
    for i in range(n):
        d = y[i] - preds[i]
        base_mse += d * d
    base_mse = base_mse / float(n)

    importance = []
    for f in range(n_feat):

        X_perm = []
        for i in range(n):
            row = []
            for j in range(n_feat):
                if j == f:
                    row.append(X[(i + 1) % n][j])
                else:
                    row.append(X[i][j])
            X_perm.append(row)
        preds_perm = random_forest_predict_batch(X, y, X_perm, n_trees, max_features)
        perm_mse = 0.0
        for i in range(n):
            d = y[i] - preds_perm[i]
            perm_mse += d * d
        perm_mse = perm_mse / float(n)
        importance.append(perm_mse - base_mse)
    return importance






def bagging_variance(predictions):
    if len(predictions) == 0:
        return []
    n_samples = len(predictions[0])
    n_trees = len(predictions)
    result = []
    for i in range(n_samples):
        vals = []
        for t in range(n_trees):
            if i < len(predictions[t]):
                vals.append(predictions[t][i])
        result.append(_variance(vals))
    return result
