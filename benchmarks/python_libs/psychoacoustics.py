"""Python equivalent of mojo/engine/psychoacoustics.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import pow
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

def _log10(x):
    return math.log(x) / math.log(10.0)



def loudness_phon_to_sone(phon):
    if phon < 0.0:
        return 0.0
    if phon >= 40.0:
        return (2.0) ** ((phon - 40.0) / 10.0)
    return (phon / 40.0) ** (2.642)



def loudness_sone_to_phon(sone):
    if sone <= 0.0:
        return 0.0
    if sone >= 1.0:
        return 40.0 + 10.0 * math.log(sone) / math.log(2.0)
    return 40.0 * (sone) ** (0.378)



def critical_bandwidth(center_freq_hz):
    return 24.7 * (4.37 * center_freq_hz / 1000.0 + 1.0)



def bark_scale(frequency_hz):
    return 26.81 * frequency_hz / (1960.0 + frequency_hz) - 0.53



def masking_threshold(masker_spl, masker_freq_hz, target_freq_hz):
    bark_m = bark_scale(masker_freq_hz)
    bark_t = bark_scale(target_freq_hz)
    delta_bark = bark_t - bark_m

    spread = 0.0
    if delta_bark >= 0.0:
        spread = -delta_bark * 25.0  # upper slope ~25 dB/Bark
    else:
        spread = delta_bark * 15.0   # lower slope ~15 dB/Bark
    return masker_spl + spread - 10.0



def speech_intelligibility_index(speech_spl, noise_spl, band_importance):
    snr = speech_spl - noise_spl
    sii = band_importance * (snr + 15.0) / 30.0
    if sii < 0.0:
        return 0.0
    if sii > band_importance:
        return band_importance
    return sii



def equal_loudness_correction(frequency_hz, spl_db):

    f = frequency_hz
    if f <= 0.0:
        return spl_db - 70.0
    log_f = math.math.log10(f)

    a_weight = (-145.528 + 98.262 * log_f
                   - 19.509 * log_f * log_f
                   + 0.975 * log_f * log_f * log_f)
    return spl_db + a_weight



def frequency_just_noticeable(center_freq_hz, jnd_fraction):
    return center_freq_hz * jnd_fraction



def temporal_masking_decay(time_after_offset_ms, initial_masking_db):
    if time_after_offset_ms < 0.0:
        return initial_masking_db
    return initial_masking_db * math.exp(-time_after_offset_ms / 20.0)



def binaural_masking_level_diff(monaural_threshold, binaural_advantage_db):
    return monaural_threshold - binaural_advantage_db
