"""Python equivalent of mojo/engine/spectral.mojo (auto-generated)."""
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
try:
    from std.math import exp
except Exception:
    pass

PI = 3.141592653589793

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

def _sin(x):
    v = x
    while v > math.pi:
        v -= 2.0 * math.pi
    while v < -math.pi:
        v += 2.0 * math.pi
    x2 = v * v
    x3 = v * x2
    x5 = x3 * x2
    x7 = x5 * x2
    x9 = x7 * x2
    x11 = x9 * x2
    return v - x3 / 6.0 + x5 / 120.0 - x7 / 5040.0 + x9 / 362880.0 - x11 / 39916800.0



def _cos(x):
    return math.math.sin(x + math.pi / 2.0)






def _dft_real(signal):
    n = len(signal)
    half = n // 2 + 1
    result = []
    for k in range(half):
        re = 0.0
        im = 0.0
        for j in range(n):
            angle = 2.0 * math.pi * float(k) * float(j) / float(n)
            re += signal[j] * math.math.cos(angle)
            im -= signal[j] * math.math.sin(angle)
        result.append(re * re + im * im)
    return result



def _dft_complex(signal):
    n = len(signal)
    half = n // 2 + 1
    result = []
    for k in range(half):
        re = 0.0
        im = 0.0
        for j in range(n):
            angle = 2.0 * math.pi * float(k) * float(j) / float(n)
            re += signal[j] * math.math.cos(angle)
            im -= signal[j] * math.math.sin(angle)
        result.append(re)
        result.append(im)
    return result






def power_spectral_density(signal, fs):
    n = len(signal)
    if n == 0:
        return []
    pows = _dft_real(signal)
    result = []
    nf = float(n) * fs
    for i in range(len(pows)):
        result.append(pows[i] / nf)
    return result






def cross_spectral_density(x, y, fs):
    n = len(x)
    if n == 0 or len(y) != n:
        return []
    dx = _dft_complex(x)
    dy = _dft_complex(y)
    half = n // 2 + 1
    nf = float(n) * fs
    result = []
    for k in range(half):
        xr = dx[k * 2]
        xi = dx[k * 2 + 1]
        yr = dy[k * 2]
        yi = dy[k * 2 + 1]

        csd_re = (xr * yr + xi * yi) / nf
        csd_im = (xr * yi - xi * yr) / nf
        result.append(math.sqrt(csd_re * csd_re + csd_im * csd_im))
    return result






def coherence(x, y, fs):
    csd = cross_spectral_density(x, y, fs)
    pxx = power_spectral_density(x, fs)
    pyy = power_spectral_density(y, fs)
    result = []
    for i in range(len(csd)):
        denom = pxx[i] * pyy[i]
        if denom < 1e-30:
            result.append(0.0)
        else:
            val = (csd[i] * csd[i]) / denom
            if val > 1.0:
                val = 1.0
            result.append(val)
    return result






def spectral_centroid(magnitudes, frequencies):
    num = 0.0
    den = 0.0
    for i in range(len(magnitudes)):
        num += frequencies[i] * magnitudes[i]
        den += magnitudes[i]
    if den < 1e-30:
        return 0.0
    return num / den






def spectral_bandwidth(magnitudes, frequencies, centroid):
    num = 0.0
    den = 0.0
    for i in range(len(magnitudes)):
        diff = frequencies[i] - centroid
        num += magnitudes[i] * diff * diff
        den += magnitudes[i]
    if den < 1e-30:
        return 0.0
    return math.sqrt(num / den)






def spectral_rolloff(magnitudes, frequencies, threshold):
    total = 0.0
    for i in range(len(magnitudes)):
        total += magnitudes[i]
    target = total * threshold
    cumsum = 0.0
    for i in range(len(magnitudes)):
        cumsum += magnitudes[i]
        if cumsum >= target:
            return frequencies[i]
    if len(frequencies) > 0:
        return frequencies[len(frequencies) - 1]
    return 0.0






def spectral_flatness(magnitudes):
    n = len(magnitudes)
    if n == 0:
        return 0.0
    log_sum = 0.0
    arith_sum = 0.0
    count = 0
    for i in range(n):
        if magnitudes[i] > 1e-30:
            log_sum += math.log(magnitudes[i])
            arith_sum += magnitudes[i]
            count += 1
        else:
            return 0.0  # zero value → flatness is 0
    if count == 0 or arith_sum < 1e-30:
        return 0.0
    geo_mean = math.exp(log_sum / float(count))
    arith_mean = arith_sum / float(count)
    return geo_mean / arith_mean






def spectral_entropy(magnitudes):
    n = len(magnitudes)
    if n == 0:
        return 0.0
    total = 0.0
    for i in range(n):
        total += magnitudes[i]
    if total < 1e-30:
        return 0.0
    entropy = 0.0
    for i in range(n):
        p = magnitudes[i] / total
        if p > 1e-30:
            entropy -= p * math.log(p)
    return entropy






def band_energy(magnitudes, frequencies, low, high):
    energy = 0.0
    for i in range(len(magnitudes)):
        if frequencies[i] >= low and frequencies[i] <= high:
            energy += magnitudes[i] * magnitudes[i]
    return energy






def peak_frequency(magnitudes, frequencies):
    if len(magnitudes) == 0:
        return 0.0
    max_val = magnitudes[0]
    max_idx = 0
    for i in range(1, len(magnitudes)):
        if magnitudes[i] > max_val:
            max_val = magnitudes[i]
            max_idx = i
    return frequencies[max_idx]
