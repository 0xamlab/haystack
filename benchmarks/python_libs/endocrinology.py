"""Python equivalent of mojo/engine/endocrinology.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import cos
except Exception:
    pass
try:
    from std.math import exp
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

def hormone_clearance_rate(dose, auc):
    if auc <= 0.0:
        return 0.0
    return dose / auc



def receptor_binding_bmax(bound, free_conc, kd):
    if free_conc <= 0.0:
        return 0.0
    return bound + bound * kd / free_conc



def feedback_gain(open_loop_gain, feedback_fraction):
    denom = 1.0 + open_loop_gain * feedback_fraction
    if denom <= 0.0:
        return 0.0
    return open_loop_gain / denom



def hormone_pulsatility(n_pulses, observation_hours):
    if observation_hours <= 0.0:
        return 0.0
    return n_pulses / observation_hours



def cortisol_circadian(time_hours, peak_value, trough_value):
    mean = (peak_value + trough_value) / 2.0
    amplitude = (peak_value - trough_value) / 2.0
    pi = 3.141592653589793
    return mean + amplitude * math.cos(2.0 * pi * (time_hours - 8.0) / 24.0)



def insulin_sensitivity_index(fasting_glucose_mmol, fasting_insulin_pmol):
    insulin_uIU = fasting_insulin_pmol / 6.0  # pmol/L → μU/mL
    return fasting_glucose_mmol * insulin_uIU / 22.5



def thyroid_free_fraction(total_t4, tbg_conc, binding_constant):
    denom = 1.0 + binding_constant * tbg_conc
    if denom <= 0.0:
        return 1.0
    return 1.0 / denom



def growth_rate_igf(igf1_nmol, baseline_rate, sensitivity):
    return baseline_rate + sensitivity * igf1_nmol



def testosterone_free(total_t, shbg, albumin):
    ka_shbg = 5.97e8 / 1e9  # L/nmol
    ka_alb = 3.6e4 / 1e9   # L/nmol (albumin 66,500 g/mol)
    alb_nmol = albumin / 66.5e-3 * 1000.0  # g/dL → nmol/L (approx)
    denom = 1.0 + ka_shbg * shbg + ka_alb * alb_nmol
    if denom <= 0.0:
        return total_t
    return total_t / denom



def negative_feedback_strength(response_at_half_max, hill_n):
    r = response_at_half_max
    return hill_n * (r) ** (hill_n - 1.0) / (1.0 + math.pow(r) ** (hill_n), 2.0)
