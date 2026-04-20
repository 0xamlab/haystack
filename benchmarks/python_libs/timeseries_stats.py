"""Python equivalent of mojo/engine/timeseries_stats.mojo (auto-generated)."""
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

def autocorrelation(data, lag):
    n = len(data)
    if n == 0 or lag < 0 or lag >= n:
        return 0.0


    mean = 0.0
    for i in range(n):
        mean += data[i]
    mean /= float(n)


    denom = 0.0
    for i in range(n):
        d = data[i] - mean
        denom += d * d

    if math.fabs(denom) < 1e-15:
        return 0.0


    num = 0.0
    for i in range(n - lag):
        num += (data[i] - mean) * (data[i + lag] - mean)

    return num / denom






def autocorrelation_function(data, max_lag):
    result = []
    for k in range(max_lag + 1):
        result.append(autocorrelation(data, k))
    return result






def partial_autocorrelation(data, max_lag):
    acf = autocorrelation_function(data, max_lag)
    result = []
    result.append(1.0)  # PACF at lag 0 is always 1.0

    if max_lag == 0:
        return result




    phi_prev = []
    for _ in range(max_lag + 1):
        phi_prev.append(0.0)

    phi_curr = []
    for _ in range(max_lag + 1):
        phi_curr.append(0.0)


    phi_curr[1] = acf[1]
    result.append(phi_curr[1])

    if max_lag == 1:
        return result

    for k in range(2, max_lag + 1):

        for j in range(max_lag + 1):
            phi_prev[j] = phi_curr[j]


        num = acf[k]
        for j in range(1, k):
            num -= phi_prev[j] * acf[k - j]


        den = 1.0
        for j in range(1, k):
            den -= phi_prev[j] * acf[j]

        if math.fabs(den) < 1e-15:
            phi_curr[k] = 0.0
        else:
            phi_curr[k] = num / den


        for j in range(1, k):
            phi_curr[j] = phi_prev[j] - phi_curr[k] * phi_prev[k - j]

        result.append(phi_curr[k])

    return result






def rolling_mean(data, window):
    n = len(data)
    result = []
    if window <= 0 or window > n:
        return result


    s = 0.0
    for i in range(window):
        s += data[i]
    result.append(s / float(window))


    for i in range(window, n):
        s += data[i] - data[i - window]
        result.append(s / float(window))

    return result






def rolling_std(data, window):
    n = len(data)
    result = []
    if window <= 0 or window > n:
        return result

    for i in range(n - window + 1):
        mean = 0.0
        for j in range(window):
            mean += data[i + j]
        mean /= float(window)

        var_sum = 0.0
        for j in range(window):
            d = data[i + j] - mean
            var_sum += d * d
        result.append(math.sqrt(var_sum / float(window)))

    return result






def exponential_smoothing(data, alpha):
    n = len(data)
    result = []
    if n == 0:
        return result

    result.append(data[0])
    for i in range(1, n):
        s = alpha * data[i] + (1.0 - alpha) * result[i - 1]
        result.append(s)

    return result






def difference(data, order=1):
    current = []
    for i in range(len(data)):
        current.append(data[i])

    for _ in range(order):
        next_list = []
        for i in range(len(current) - 1):
            next_list.append(current[i + 1] - current[i])
        current = next_list

    return current






def adf_test_statistic(data):
    n = len(data)
    if n < 3:
        return 0.0



    m = n - 1  # number of observations


    sum_x = 0.0
    sum_y = 0.0
    sum_xx = 0.0
    sum_xy = 0.0

    for i in range(m):
        x = data[i]
        y_dep = data[i + 1] - data[i]
        sum_x += x
        sum_y += y_dep
        sum_xx += x * x
        sum_xy += x * y_dep

    fm = float(m)
    denom = fm * sum_xx - sum_x * sum_x
    if math.fabs(denom) < 1e-15:
        return 0.0


    gamma_hat = (fm * sum_xy - sum_x * sum_y) / denom


    intercept = (sum_y - gamma_hat * sum_x) / fm
    rss = 0.0
    for i in range(m):
        x = data[i]
        y_dep = data[i + 1] - data[i]
        resid = y_dep - intercept - gamma_hat * x
        rss += resid * resid

    s2 = rss / float(m - 2) if m > 2 else rss
    se_gamma = math.sqrt(s2 * fm / denom)
    if math.fabs(se_gamma) < 1e-15:
        return 0.0

    return gamma_hat / se_gamma






def holt_linear(data, alpha, beta):
    n = len(data)
    result = []
    if n == 0:
        return result


    level = data[0]
    trend = 0.0
    if n > 1:
        trend = data[1] - data[0]

    result.append(level)

    for i in range(1, n):
        prev_level = level
        level = alpha * data[i] + (1.0 - alpha) * (prev_level + trend)
        trend = beta * (level - prev_level) + (1.0 - beta) * trend
        result.append(level)

    return result
