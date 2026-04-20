"""Python equivalent of mojo/engine/ml.naive_bayes.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
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

PI = 3.141592653589793
MIN_STD = 1e-9

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

def compute_priors(y, n_classes):
    counts = []
    for _ in range(n_classes):
        counts.append(0.0)
    n = len(y)
    for i in range(n):
        c = y[i]
        if c >= 0 and c < n_classes:
            counts[c] = counts[c] + 1.0
    if n > 0:
        for c in range(n_classes):
            counts[c] = counts[c] / float(n)
    return counts






def gaussian_log_likelihood(x, mean, std):
    s = std
    if s < MIN_STD:
        s = MIN_STD
    diff = x - mean
    return -0.5 * math.log(2.0 * math.pi) - math.log(s) - (diff * diff) / (2.0 * s * s)






def gaussian_nb_fit(X, y, n_classes):
    n_samples = len(X)
    n_features = 0
    if n_samples > 0:
        n_features = len(X[0])


    counts = []
    for _ in range(n_classes):
        counts.append(0)
    for i in range(n_samples):
        c = y[i]
        if c >= 0 and c < n_classes:
            counts[c] = counts[c] + 1


    sums = []
    sq_sums = []
    for _ in range(n_classes):
        row = []
        sq_row = []
        for _ in range(n_features):
            row.append(0.0)
            sq_row.append(0.0)
        sums.append(row)
        sq_sums.append(sq_row)

    for i in range(n_samples):
        c = y[i]
        if c >= 0 and c < n_classes:
            for f in range(n_features):
                v = X[i][f]
                sums[c][f] = sums[c][f] + v
                sq_sums[c][f] = sq_sums[c][f] + v * v


    params = []
    for c in range(n_classes):
        row = []
        cnt = float(counts[c])
        for f in range(n_features):
            if cnt > 0.0:
                mean = sums[c][f] / cnt
                variance = sq_sums[c][f] / cnt - mean * mean
                if variance < 0.0:
                    variance = 0.0
                std = math.sqrt(variance)
                if std < MIN_STD:
                    std = MIN_STD
                row.append(mean)
                row.append(std)
            else:
                row.append(0.0)
                row.append(MIN_STD)
        params.append(row)

    return params






def gaussian_nb_predict(params, priors, x):
    n_classes = len(params)
    best_class = 0
    best_score = -1e308

    for c in range(n_classes):
        score = 0.0
        if priors[c] > 0.0:
            score = math.log(priors[c])
        else:
            score = -1e308

        n_features = len(x)
        for f in range(n_features):
            mean = params[c][f * 2]
            std = params[c][f * 2 + 1]
            score += gaussian_log_likelihood(x[f], mean, std)

        if score > best_score:
            best_score = score
            best_class = c

    return best_class






def gaussian_nb_predict_batch(params, priors, X):
    results = []
    for i in range(len(X)):
        results.append(gaussian_nb_predict(params, priors, X[i]))
    return results






def accuracy(predicted, actual):
    n = len(predicted)
    if len(actual) < n:
        n = len(actual)
    if n == 0:
        return 0.0
    correct = 0
    for i in range(n):
        if predicted[i] == actual[i]:
            correct += 1
    return float(correct) / float(n)






def confusion_matrix(predicted, actual, n_classes):
    mat = []
    for _ in range(n_classes):
        row = []
        for _ in range(n_classes):
            row.append(0)
        mat.append(row)

    n = len(predicted)
    if len(actual) < n:
        n = len(actual)

    for i in range(n):
        a = actual[i]
        p = predicted[i]
        if a >= 0 and a < n_classes and p >= 0 and p < n_classes:
            mat[a][p] = mat[a][p] + 1

    return mat






def precision_recall(predicted, actual, target_class):
    tp = 0
    fp = 0
    fn_count = 0

    n = len(predicted)
    if len(actual) < n:
        n = len(actual)

    for i in range(n):
        if predicted[i] == target_class and actual[i] == target_class:
            tp += 1
        elif predicted[i] == target_class and actual[i] != target_class:
            fp += 1
        elif predicted[i] != target_class and actual[i] == target_class:
            fn_count += 1

    precision = 0.0
    if tp + fp > 0:
        precision = float(tp) / float(tp + fp)

    recall = 0.0
    if tp + fn_count > 0:
        recall = float(tp) / float(tp + fn_count)

    f1 = 0.0
    if precision + recall > 0.0:
        f1 = 2.0 * precision * recall / (precision + recall)

    result = []
    result.append(precision)
    result.append(recall)
    result.append(f1)
    return result
