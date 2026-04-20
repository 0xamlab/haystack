"""Python equivalent of mojo/engine/time_series_decompose.mojo (auto-generated)."""
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

def _mean(data):
    n = len(data)
    if n == 0:
        return 0.0
    s = 0.0
    for i in range(n):
        s += data[i]
    return s / float(n)



def _variance(data):
    n = len(data)
    if n == 0:
        return 0.0
    m = _mean(data)
    s = 0.0
    for i in range(n):
        d = data[i] - m
        s += d * d
    return s / float(n)






def moving_average_trend(data, window):
    n = len(data)
    result = []
    for i in range(n):
        result.append(0.0)
    if n == 0 or window <= 0:
        return result
    half = window // 2
    for i in range(n):
        if i < half or i >= n - half:
            result[i] = 0.0
        else:
            s = 0.0
            for j in range(i - half, i - half + window):
                s += data[j]
            result[i] = s / float(window)
    return result






def detrend(data, trend):
    n = len(data)
    result = []
    for i in range(n):
        if i < len(trend):
            result.append(data[i] - trend[i])
        else:
            result.append(data[i])
    return result






def seasonal_component(detrended, period):
    n = len(detrended)
    if n == 0 or period <= 0:
        return []
    season_avg = []
    for p in range(period):
        s = 0.0
        count = 0
        idx = p
        while idx < n:
            s += detrended[idx]
            count += 1
            idx += period
        if count > 0:
            season_avg.append(s / float(count))
        else:
            season_avg.append(0.0)
    result = []
    for i in range(n):
        result.append(season_avg[i % period])
    return result






def residual(data, trend, seasonal):
    n = len(data)
    result = []
    for i in range(n):
        t = 0.0
        s = 0.0
        if i < len(trend):
            t = trend[i]
        if i < len(seasonal):
            s = seasonal[i]
        result.append(data[i] - t - s)
    return result






def decompose_additive(data, period):
    trend_comp = moving_average_trend(data, period)
    detrended = detrend(data, trend_comp)
    seasonal_comp = seasonal_component(detrended, period)
    resid = residual(data, trend_comp, seasonal_comp)
    result = []
    result.append(trend_comp)
    result.append(seasonal_comp)
    result.append(resid)
    return result






def seasonal_strength(resid, seasonal_plus_residual):
    var_r = _variance(resid)
    var_sr = _variance(seasonal_plus_residual)
    if var_sr < 1e-15:
        return 0.0
    val = 1.0 - var_r / var_sr
    if val < 0.0:
        return 0.0
    if val > 1.0:
        return 1.0
    return val






def trend_strength(resid, trend_plus_residual):
    var_r = _variance(resid)
    var_tr = _variance(trend_plus_residual)
    if var_tr < 1e-15:
        return 0.0
    val = 1.0 - var_r / var_tr
    if val < 0.0:
        return 0.0
    if val > 1.0:
        return 1.0
    return val






def detect_period(data, max_period):
    n = len(data)
    if n < 4 or max_period < 2:
        return 1
    m = _mean(data)
    denom = 0.0
    for i in range(n):
        d = data[i] - m
        denom += d * d
    if denom < 1e-15:
        return 1
    best_lag = 1
    best_acf = -2.0
    limit = max_period
    if limit >= n:
        limit = n - 1
    for lag in range(2, limit + 1):
        numer = 0.0
        for t in range(n - lag):
            numer += (data[t] - m) * (data[t + lag] - m)
        acf = numer / denom
        if acf > best_acf:
            best_acf = acf
            best_lag = lag
    return best_lag






def stl_like(data, period, n_iter=2):
    n = len(data)
    trend_comp = []
    for i in range(n):
        trend_comp.append(0.0)
    seasonal_comp = []
    for i in range(n):
        seasonal_comp.append(0.0)

    for _iter in range(n_iter):
        deseasoned = []
        for i in range(n):
            deseasoned.append(data[i] - seasonal_comp[i])
        trend_comp = moving_average_trend(deseasoned, period)
        detrended = detrend(data, trend_comp)
        seasonal_comp = seasonal_component(detrended, period)

    resid = residual(data, trend_comp, seasonal_comp)
    result = []
    result.append(trend_comp)
    result.append(seasonal_comp)
    result.append(resid)
    return result
