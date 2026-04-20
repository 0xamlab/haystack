"""Python equivalent of mojo/engine/signal_processing.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import cos
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass

PI = 3.141592653589793
TWO_PI = 6.283185307179586

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

def hamming_window(n):
    w = []
    if n <= 0:
        return w
    if n == 1:
        w.append(1.0)
        return w
    denom = float(n - 1)
    for k in range(n):
        val = 0.54 - 0.46 * math.cos(TWO_PI * float(k) / denom)
        w.append(val)
    return w



def hann_window(n):
    w = []
    if n <= 0:
        return w
    if n == 1:
        w.append(1.0)
        return w
    denom = float(n - 1)
    for k in range(n):
        val = 0.5 * (1.0 - math.cos(TWO_PI * float(k) / denom))
        w.append(val)
    return w



def blackman_window(n):
    w = []
    if n <= 0:
        return w
    if n == 1:
        w.append(1.0)
        return w
    denom = float(n - 1)
    for k in range(n):
        fk = float(k)
        val = 0.42 - 0.5 * math.cos(TWO_PI * fk / denom) + 0.08 * math.cos(
            2.0 * TWO_PI * fk / denom
        )
        w.append(val)
    return w






def apply_window(data, window):
    n = len(data)
    m = len(window)
    sz = n if n < m else m
    out = []
    for i in range(sz):
        out.append(data[i] * window[i])
    return out






def peak_detect(data, threshold):
    peaks = []
    n = len(data)
    if n < 3:
        return peaks
    for i in range(1, n - 1):
        if data[i] > data[i - 1] and data[i] > data[i + 1] and data[i] > threshold:
            peaks.append(i)
    return peaks






def zero_crossings(data):
    crossings = []
    n = len(data)
    if n < 2:
        return crossings
    for i in range(n - 1):
        s1 = 1.0 if data[i] >= 0.0 else -1.0
        s2 = 1.0 if data[i + 1] >= 0.0 else -1.0
        if s1 != s2:
            crossings.append(i)
    return crossings






def spectral_energy(magnitudes):
    energy = 0.0
    for i in range(len(magnitudes)):
        energy += magnitudes[i] * magnitudes[i]
    return energy



def spectral_centroid(magnitudes, sample_rate):
    n = len(magnitudes)
    if n == 0:
        return 0.0
    weighted_sum = 0.0
    total = 0.0
    freq_step = sample_rate / (2.0 * float(n))
    for k in range(n):
        freq = float(k) * freq_step
        mag = magnitudes[k]
        if mag < 0.0:
            mag = -mag
        weighted_sum += freq * mag
        total += mag
    if total == 0.0:
        return 0.0
    return weighted_sum / total



def spectral_flatness(magnitudes):
    n = len(magnitudes)
    if n == 0:
        return 0.0
    log_sum = 0.0
    arith_sum = 0.0
    count = 0
    for i in range(n):
        mag = magnitudes[i]
        if mag < 0.0:
            mag = -mag
        if mag < 1e-20:
            mag = 1e-20
        log_sum += math.log(mag)
        arith_sum += mag
        count += 1
    if count == 0 or arith_sum == 0.0:
        return 0.0
    geo_mean = math.exp(log_sum / float(count))
    arith_mean = arith_sum / float(count)
    result = geo_mean / arith_mean
    if result > 1.0:
        result = 1.0
    if result < 0.0:
        result = 0.0
    return result






def signal_power(data):
    n = len(data)
    if n == 0:
        return 0.0
    total = 0.0
    for i in range(n):
        total += data[i] * data[i]
    return total / float(n)
