"""Python equivalent of mojo/engine/series.mojo (auto-generated)."""
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

def _ols_fit(data):
    n = len(data)
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    sxy = 0.0
    for i in range(n):
        x = float(i)
        sx += x
        sy += data[i]
        sxx += x * x
        sxy += x * data[i]
    nf = float(n)
    denom = nf * sxx - sx * sx
    if math.fabs(denom) < 1e-15:
        result = []
        result.append(sy / nf)
        result.append(0.0)
        return result
    b = (nf * sxy - sx * sy) / denom
    a = (sy - b * sx) / nf
    result = []
    result.append(a)
    result.append(b)
    return result






def _autocorrelation(data, lag):
    n = len(data)
    if lag >= n:
        return 0.0
    mean = 0.0
    for i in range(n):
        mean += data[i]
    mean /= float(n)
    num = 0.0
    den = 0.0
    for i in range(n):
        den += (data[i] - mean) * (data[i] - mean)
    if den < 1e-15:
        return 0.0
    for i in range(n - lag):
        num += (data[i] - mean) * (data[i + lag] - mean)
    return num / den






def sma_forecast(data, window, horizon):
    n = len(data)
    w = window
    if w > n:
        w = n
    total = 0.0
    for i in range(n - w, n):
        total += data[i]
    sma = total / float(w)
    result = []
    for _ in range(horizon):
        result.append(sma)
    return result






def linear_extrapolation(data, horizon):
    n = len(data)
    fit = _ols_fit(data)
    a = fit[0]
    b = fit[1]
    result = []
    for h in range(horizon):
        result.append(a + b * float(n + h))
    return result






def weighted_moving_avg(data, weights):
    n = len(data)
    w = len(weights)
    total = 0.0
    wsum = 0.0
    for i in range(w):
        idx = n - w + i
        if idx >= 0:
            total += data[idx] * weights[i]
            wsum += weights[i]
    if wsum < 1e-15:
        return 0.0
    return total / wsum






def exponential_forecast(data, alpha, horizon):
    n = len(data)
    if n == 0:
        result = []
        for _ in range(horizon):
            result.append(0.0)
        return result
    s = data[0]
    for i in range(1, n):
        s = alpha * data[i] + (1.0 - alpha) * s
    result = []
    for _ in range(horizon):
        result.append(s)
    return result






def naive_forecast(data, horizon):
    result = []
    last = data[len(data) - 1]
    for _ in range(horizon):
        result.append(last)
    return result






def seasonal_naive(data, period, horizon):
    n = len(data)
    result = []
    for h in range(horizon):
        idx = n - period + (h % period)
        result.append(data[idx])
    return result






def drift_forecast(data, horizon):
    n = len(data)
    result = []
    if n < 2:
        for _ in range(horizon):
            result.append(data[0] if n > 0 else 0.0)
        return result
    y_T = data[n - 1]
    y_1 = data[0]
    slope = (y_T - y_1) / float(n - 1)
    for h in range(1, horizon + 1):
        result.append(y_T + float(h) * slope)
    return result






def forecast_accuracy(actual, predicted):
    n = len(actual)
    mae = 0.0
    mape = 0.0
    mse = 0.0
    for i in range(n):
        err = math.fabs(actual[i] - predicted[i])
        mae += err
        if math.fabs(actual[i]) > 1e-15:
            mape += err / math.fabs(actual[i])
        d = actual[i] - predicted[i]
        mse += d * d
    nf = float(n)
    result = []
    result.append(mae / nf)
    result.append(mape / nf * 100.0)
    result.append(math.sqrt(mse / nf))
    return result






def trend_strength(data):
    n = len(data)
    if n < 2:
        return 0.0
    fit = _ols_fit(data)
    a = fit[0]
    b = fit[1]

    mean_d = 0.0
    for i in range(n):
        mean_d += data[i]
    mean_d /= float(n)
    var_data = 0.0
    var_resid = 0.0
    for i in range(n):
        dd = data[i] - mean_d
        var_data += dd * dd
        r = data[i] - (a + b * float(i))
        var_resid += r * r
    if var_data < 1e-15:
        return 0.0
    strength = 1.0 - var_resid / var_data
    if strength < 0.0:
        strength = 0.0
    return strength






def detect_seasonality(data, max_period):
    best_period = 2
    best_acf = -2.0
    limit = max_period
    if limit >= len(data):
        limit = len(data) - 1
    for p in range(2, limit + 1):
        acf = _autocorrelation(data, p)
        if acf > best_acf:
            best_acf = acf
            best_period = p
    return best_period
