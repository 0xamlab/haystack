"""Python equivalent of mojo/engine/feature_selection.mojo (auto-generated)."""
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
    from std.math import log
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

def _compute_mse_with_features(X, y, features):
    n = len(X)
    if n == 0 or len(features) == 0:
        return 1e30
    y_mean = 0.0
    for i in range(n):
        y_mean += y[i]
    y_mean /= float(n)

    pred = []
    for i in range(n):
        pred.append(y_mean)

    nf = len(features)
    for fi in range(nf):
        j = features[fi]
        x_mean = 0.0
        for i in range(n):
            x_mean += X[i][j]
        x_mean /= float(n)
        cov = 0.0
        var_x = 0.0
        for i in range(n):
            dx = X[i][j] - x_mean
            cov += dx * (y[i] - y_mean)
            var_x += dx * dx
        if var_x > 1e-30:
            beta = cov / var_x
            for i in range(n):
                pred[i] = pred[i] + beta * (X[i][j] - x_mean) / float(nf)

    mse = 0.0
    for i in range(n):
        e = y[i] - pred[i]
        mse += e * e
    return mse / float(n)



def column_mean(data):
    n = len(data)
    if n == 0:
        return []
    ncols = len(data[0])
    means = []
    for j in range(ncols):
        s = 0.0
        for i in range(n):
            s += data[i][j]
        means.append(s / float(n))
    return means






def column_variance(data):
    n = len(data)
    if n == 0:
        return []
    ncols = len(data[0])
    means = column_mean(data)
    variances = []
    for j in range(ncols):
        ss = 0.0
        for i in range(n):
            d = data[i][j] - means[j]
            ss += d * d
        variances.append(ss / float(n))
    return variances






def variance_threshold(data, threshold=0.0):
    variances = column_variance(data)
    selected = []
    for j in range(len(variances)):
        if variances[j] > threshold:
            selected.append(j)
    return selected






def correlation_filter(data, max_corr=0.95):
    n = len(data)
    if n == 0:
        return []
    ncols = len(data[0])
    means = column_mean(data)
    removed = []
    for j in range(ncols):
        removed.append(False)

    for i_col in range(ncols):
        if removed[i_col]:
            continue
        for j_col in range(i_col + 1, ncols):
            if removed[j_col]:
                continue
            cov = 0.0
            var_a = 0.0
            var_b = 0.0
            for r in range(n):
                da = data[r][i_col] - means[i_col]
                db = data[r][j_col] - means[j_col]
                cov += da * db
                var_a += da * da
                var_b += db * db
            denom = math.sqrt(var_a * var_b)
            if denom > 1e-15:
                corr = cov / denom
                if math.fabs(corr) > max_corr:
                    removed[j_col] = True

    selected = []
    for j in range(ncols):
        if not removed[j]:
            selected.append(j)
    return selected






def f_test_scores(X, y):
    n = len(X)
    if n < 3:
        return []
    ncols = len(X[0])
    y_mean = 0.0
    for i in range(n):
        y_mean += y[i]
    y_mean /= float(n)

    scores = []
    for j in range(ncols):
        x_mean = 0.0
        for i in range(n):
            x_mean += X[i][j]
        x_mean /= float(n)

        cov = 0.0
        var_x = 0.0
        var_y = 0.0
        for i in range(n):
            dx = X[i][j] - x_mean
            dy = y[i] - y_mean
            cov += dx * dy
            var_x += dx * dx
            var_y += dy * dy
        denom = var_x * var_y
        if denom < 1e-30:
            scores.append(0.0)
            continue
        r2 = (cov * cov) / denom
        f_val = r2 * float(n - 2) / (1.0 - r2 + 1e-30)
        scores.append(f_val)
    return scores






def select_k_best(scores, k):
    n = len(scores)
    actual_k = k
    if actual_k > n:
        actual_k = n
    used = []
    for i in range(n):
        used.append(False)
    result = []
    for round_i in range(actual_k):
        best_idx = -1
        best_val = -1e300
        for j in range(n):
            if not used[j] and scores[j] > best_val:
                best_val = scores[j]
                best_idx = j
        if best_idx >= 0:
            result.append(best_idx)
            used[best_idx] = True
    return result






def forward_selection_greedy(X, y, k):
    n = len(X)
    if n == 0:
        return []
    ncols = len(X[0])
    actual_k = k
    if actual_k > ncols:
        actual_k = ncols

    selected = []
    used = []
    for j in range(ncols):
        used.append(False)

    for round_i in range(actual_k):
        best_feat = -1
        best_mse = 1e30
        for j in range(ncols):
            if used[j]:
                continue
            candidate = []
            for si in range(len(selected)):
                candidate.append(selected[si])
            candidate.append(j)
            mse_val = _compute_mse_with_features(X, y, candidate)
            if mse_val < best_mse:
                best_mse = mse_val
                best_feat = j
        if best_feat >= 0:
            selected.append(best_feat)
            used[best_feat] = True
    return selected






def information_gain(feature, target, n_bins=10):
    n = len(feature)
    if n == 0:
        return 0.0

    f_min = feature[0]
    f_max = feature[0]
    t_min = target[0]
    t_max = target[0]
    for i in range(1, n):
        if feature[i] < f_min:
            f_min = feature[i]
        if feature[i] > f_max:
            f_max = feature[i]
        if target[i] < t_min:
            t_min = target[i]
        if target[i] > t_max:
            t_max = target[i]

    f_range = f_max - f_min
    t_range = t_max - t_min
    if f_range < 1e-15:
        f_range = 1.0
    if t_range < 1e-15:
        t_range = 1.0

    nb = n_bins
    f_counts = []
    t_counts = []
    joint_counts = []
    for i in range(nb):
        f_counts.append(0)
        t_counts.append(0)
    for i in range(nb * nb):
        joint_counts.append(0)

    for i in range(n):
        fb = int((feature[i] - f_min) / f_range * float(nb - 1) + 0.5)
        if fb < 0:
            fb = 0
        if fb >= nb:
            fb = nb - 1
        tb = int((target[i] - t_min) / t_range * float(nb - 1) + 0.5)
        if tb < 0:
            tb = 0
        if tb >= nb:
            tb = nb - 1
        f_counts[fb] += 1
        t_counts[tb] += 1
        joint_counts[fb * nb + tb] += 1

    fn_val = float(n)
    h_f = 0.0
    h_t = 0.0
    h_ft = 0.0
    for i in range(nb):
        if f_counts[i] > 0:
            p = float(f_counts[i]) / fn_val
            h_f -= p * math.log(p)
        if t_counts[i] > 0:
            p = float(t_counts[i]) / fn_val
            h_t -= p * math.log(p)
    for i in range(nb * nb):
        if joint_counts[i] > 0:
            p = float(joint_counts[i]) / fn_val
            h_ft -= p * math.log(p)

    mi = h_f + h_t - h_ft
    if mi < 0.0:
        mi = 0.0
    return mi






def feature_importance_permutation(X, y, n_permutations=5):
    n = len(X)
    if n == 0:
        return []
    ncols = len(X[0])

    y_mean = 0.0
    for i in range(n):
        y_mean += y[i]
    y_mean /= float(n)
    base_mse = 0.0
    for i in range(n):
        e = y[i] - y_mean
        base_mse += e * e
    base_mse /= float(n)

    importances = []
    for j in range(ncols):
        total_mse_increase = 0.0
        for p in range(n_permutations):
            shift = (p + 1) % n
            if shift == 0:
                shift = 1
            perm_mse = 0.0
            for i in range(n):
                si = (i + shift) % n
                e = y[i] - y_mean
                perm_mse += e * e + (X[i][j] - X[si][j]) * (X[i][j] - X[si][j]) * 0.01
            perm_mse /= float(n)
            total_mse_increase += perm_mse - base_mse
        importances.append(total_mse_increase / float(n_permutations))
    return importances
