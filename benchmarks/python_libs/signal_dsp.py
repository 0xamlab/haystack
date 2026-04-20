"""Python equivalent of mojo/engine/signal.dsp.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import sqrt
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

def moving_average(data, window):
    n = len(data)
    result = []
    if n == 0 or window <= 0:
        return result
    w = window
    if w > n:
        w = n

    hw = w // 2

    for i in range(n):
        lo = i - hw
        hi = i + hw
        if lo < 0:
            lo = 0
        if hi >= n:
            hi = n - 1
        s = 0.0
        cnt = 0
        for j in range(lo, hi + 1):
            s += data[j]
            cnt += 1
        if cnt > 0:
            result.append(s / float(cnt))
        else:
            result.append(0.0)
    return result






def exponential_moving_average(data, alpha):
    n = len(data)
    result = []
    if n == 0:
        return result
    a = alpha
    if a < 0.0:
        a = 0.0
    if a > 1.0:
        a = 1.0
    result.append(data[0])
    for i in range(1, n):
        ema = a * data[i] + (1.0 - a) * result[i - 1]
        result.append(ema)
    return result






def diff(data):
    n = len(data)
    result = []
    if n <= 1:
        return result
    for i in range(n - 1):
        result.append(data[i + 1] - data[i])
    return result






def cumsum(data):
    n = len(data)
    result = []
    if n == 0:
        return result
    s = 0.0
    for i in range(n):
        s += data[i]
        result.append(s)
    return result






def convolve(signal_data, kernel):
    n = len(signal_data)
    m = len(kernel)
    result = []
    if n == 0 or m == 0:
        return result
    out_len = n + m - 1
    for i in range(out_len):
        s = 0.0

        j_lo = 0
        if i >= n:
            j_lo = i - n + 1
        j_hi = m - 1
        if i < j_hi:
            j_hi = i
        for j in range(j_lo, j_hi + 1):
            s += signal_data[i - j] * kernel[j]
        result.append(s)
    return result






def autocorrelation(data, max_lag):
    n = len(data)
    result = []
    if n == 0:
        return result


    mean = 0.0
    for i in range(n):
        mean += data[i]
    mean /= float(n)


    var0 = 0.0
    for i in range(n):
        d = data[i] - mean
        var0 += d * d

    if var0 < 1e-15:

        for lag in range(max_lag + 1):
            result.append(1.0)
        return result

    lags = max_lag
    if lags >= n:
        lags = n - 1

    for lag in range(lags + 1):
        s = 0.0
        for i in range(n - lag):
            s += (data[i] - mean) * (data[i + lag] - mean)
        result.append(s / var0)

    return result






def detrend_linear(data):
    n = len(data)
    result = []
    if n == 0:
        return result
    if n == 1:
        result.append(0.0)
        return result


    sx = 0.0
    sy = 0.0
    sxx = 0.0
    sxy = 0.0
    nf = float(n)

    for i in range(n):
        xi = float(i)
        sx += xi
        sy += data[i]
        sxx += xi * xi
        sxy += xi * data[i]

    denom = nf * sxx - sx * sx
    b = 0.0
    a = 0.0
    if math.fabs(denom) > 1e-15:
        b = (nf * sxy - sx * sy) / denom
        a = (sy - b * sx) / nf
    else:
        a = sy / nf

    for i in range(n):
        result.append(data[i] - (a + b * float(i)))
    return result






def normalize_signal(data):
    n = len(data)
    result = []
    if n == 0:
        return result

    mn = data[0]
    mx = data[0]
    for i in range(1, n):
        if data[i] < mn:
            mn = data[i]
        if data[i] > mx:
            mx = data[i]

    rng = mx - mn
    if rng < 1e-15:
        for i in range(n):
            result.append(0.0)
        return result

    for i in range(n):

        result.append(2.0 * (data[i] - mn) / rng - 1.0)
    return result






def zero_crossings(data):
    n = len(data)
    if n <= 1:
        return 0
    count = 0
    for i in range(1, n):

        if (data[i - 1] > 0.0 and data[i] < 0.0) or (data[i - 1] < 0.0 and data[i] > 0.0):
            count += 1
        elif data[i - 1] != 0.0 and data[i] == 0.0:

            count += 1
    return count






def peak_detect(data, threshold):
    n = len(data)
    peaks = []
    if n <= 2:
        return peaks
    for i in range(1, n - 1):
        if data[i] > data[i - 1] and data[i] > data[i + 1] and data[i] >= threshold:
            peaks.append(i)
    return peaks
