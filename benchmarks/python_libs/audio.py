"""Python equivalent of mojo/engine/audio.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sin
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import pow
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass

PI = 3.141592653589793
LN10 = 2.302585092994046
LN2 = 0.6931471805599453
LOG10_E = 0.4342944819032518   # 1/ln(10)
LOG2_E = 1.4426950408889634     # 1/ln(2)

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

def _log10(x):
    return math.log(x) * LOG10_E



def _log2(x):
    return math.log(x) * LOG2_E






def amplitude_to_db(amplitude, reference=1.0):
    if amplitude <= 0.0 or reference <= 0.0:
        return -200.0  # floor value for silence
    return 20.0 * math.math.log10(amplitude / reference)






def db_to_amplitude(db, reference=1.0):
    return reference * (10.0) ** (db / 20.0)






def frequency_to_midi(freq):
    if freq <= 0.0:
        return 0.0
    return 69.0 + 12.0 * math.math.log2(freq / 440.0)






def midi_to_frequency(midi):
    return 440.0 * (2.0) ** ((midi - 69.0) / 12.0)






def generate_sine(freq, sample_rate, n_samples):
    result = []
    if n_samples <= 0 or sample_rate <= 0.0:
        return result
    omega = 2.0 * math.pi * freq / sample_rate
    for i in range(n_samples):
        result.append(math.sin(omega * float(i)))
    return result






def rms_amplitude(samples):
    n = len(samples)
    if n == 0:
        return 0.0
    sum_sq = 0.0
    for i in range(n):
        sum_sq += samples[i] * samples[i]
    return math.sqrt(sum_sq / float(n))






def zero_crossing_rate(samples):
    n = len(samples)
    if n < 2:
        return 0.0
    crossings = 0
    for i in range(1, n):
        prev_pos = samples[i - 1] >= 0.0
        curr_pos = samples[i] >= 0.0
        if prev_pos != curr_pos:
            crossings += 1
    return float(crossings) / float(n - 1)






def envelope(samples, window):
    n = len(samples)
    result = []
    if n == 0 or window <= 0:
        return result
    hw = window // 2
    for i in range(n):
        lo = i - hw
        hi = i + hw
        if lo < 0:
            lo = 0
        if hi >= n:
            hi = n - 1
        max_val = 0.0
        for j in range(lo, hi + 1):
            av = math.fabs(samples[j])
            if av > max_val:
                max_val = av
        result.append(max_val)
    return result






def normalize_audio(samples):
    n = len(samples)
    result = []
    if n == 0:
        return result
    peak = 0.0
    for i in range(n):
        av = math.fabs(samples[i])
        if av > peak:
            peak = av
    if peak == 0.0:
        for i in range(n):
            result.append(0.0)
        return result
    for i in range(n):
        result.append(samples[i] / peak)
    return result






def mix_signals(a, b, weight_a=0.5):
    na = len(a)
    nb = len(b)
    n = na
    if nb < n:
        n = nb
    result = []
    wb = 1.0 - weight_a
    for i in range(n):
        result.append(weight_a * a[i] + wb * b[i])
    return result
