"""Python equivalent of mojo/engine/signal.filter.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import log as math_log
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

def _sort_window(arr):
    n = len(arr)
    for i in range(1, n):
        key = arr[i]
        j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key



def lowpass_ema(data, alpha):
    n = len(data)
    result = []
    if n == 0:
        return result
    result.append(data[0])
    for i in range(1, n):
        prev = result[i - 1]
        result.append(alpha * data[i] + (1.0 - alpha) * prev)
    return result






def highpass_ema(data, alpha):
    lp = lowpass_ema(data, alpha)
    n = len(data)
    result = []
    for i in range(n):
        result.append(data[i] - lp[i])
    return result






def bandpass(data, alpha_low, alpha_high):
    lp_low = lowpass_ema(data, alpha_low)
    lp_high = lowpass_ema(data, alpha_high)
    n = len(data)
    result = []
    for i in range(n):
        result.append(lp_low[i] - lp_high[i])
    return result






def median_filter(data, window):
    n = len(data)
    result = []
    if n == 0:
        return result
    w = window
    if w % 2 == 0:
        w += 1  # ensure odd
    hw = w // 2
    for i in range(n):
        lo = i - hw
        hi = i + hw
        if lo < 0:
            lo = 0
        if hi >= n:
            hi = n - 1
        win = []
        for j in range(lo, hi + 1):
            win.append(data[j])
        _sort_window(win)
        mid = len(win) // 2
        result.append(win[mid])
    return result






def savitzky_golay_3(data):
    n = len(data)
    result = []
    if n < 5:
        for i in range(n):
            result.append(data[i])
        return result

    result.append(data[0])
    result.append(data[1])
    for i in range(2, n - 2):
        v = (-3.0 * data[i - 2] + 12.0 * data[i - 1] + 17.0 * data[i]
                 + 12.0 * data[i + 1] - 3.0 * data[i + 2]) / 35.0
        result.append(v)

    result.append(data[n - 2])
    result.append(data[n - 1])
    return result






def moving_average_filter(data, window):
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
        result.append(s / float(cnt))
    return result






def iir_filter_1st(data, a, b):
    n = len(data)
    result = []
    if n == 0:
        return result
    result.append(b * data[0])
    for i in range(1, n):
        prev = result[i - 1]
        result.append(b * data[i] + a * prev)
    return result






def diff_filter(data):
    n = len(data)
    result = []
    for i in range(1, n):
        result.append(data[i] - data[i - 1])
    return result






def integrate_filter(data, dt=1.0):
    n = len(data)
    result = []
    if n == 0:
        return result
    result.append(0.0)
    for i in range(1, n):
        prev = result[i - 1]
        result.append(prev + 0.5 * (data[i - 1] + data[i]) * dt)
    return result






def snr(signal, noise):
    sig_power = 0.0
    for i in range(len(signal)):
        sig_power += signal[i] * signal[i]
    noise_power = 0.0
    for i in range(len(noise)):
        noise_power += noise[i] * noise[i]
    if noise_power == 0.0:
        return 1e30  # effectively infinite
    ratio = sig_power / noise_power
    if ratio <= 0.0:
        return -1e30

    ln10 = 2.302585092994046
    return 10.0 * math_log(ratio) / ln10






def rms(data):
    n = len(data)
    if n == 0:
        return 0.0
    s = 0.0
    for i in range(n):
        s += data[i] * data[i]
    return math.sqrt(s / float(n))
