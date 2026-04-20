"""Python equivalent of mojo/engine/ergonomics.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import atan2
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass

LN2 = 0.6931471805599453
LN10 = 2.302585092994046
PI = 3.14159265358979323846

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

def _log2(x):
    return math.log(x) / LN2



def _log10(x):
    return math.log(x) / LN10



def _pow10(x):
    return math.exp(x * LN10)






def niosh_rwl(lc, hm, vm, dm, am, fm, cm):
    return lc * hm * vm * dm * am * fm * cm






def lifting_index(load_weight, rwl):
    return load_weight / rwl






def metabolic_rate_walking(body_mass, speed, grade):
    return body_mass * (2.0 + 3.0 * speed + grade * speed * 0.5)






def heat_stress_index(metabolic_heat, evaporative_capacity):
    return metabolic_heat / evaporative_capacity * 100.0






def decibel_addition(db1, db2):
    p1 = _pow10(db1 / 10.0)
    p2 = _pow10(db2 / 10.0)
    return 10.0 * math.math.log10(p1 + p2)






def noise_dose(exposure_time, allowed_time):
    return exposure_time / allowed_time






def cumulative_noise_dose_2(t1, ta1, t2, ta2):
    return t1 / ta1 + t2 / ta2






def visual_angle_minutes(object_size, distance):
    half_angle = math.atan2(object_size / 2.0, distance)
    return 2.0 * half_angle * (180.0 / math.pi) * 60.0






def fitts_law_movement_time(a, b, distance, width):
    return a + b * math.math.log2(2.0 * distance / width)






def hicks_law_reaction_time(a, b, n_choices):
    return a + b * math.math.log2(n_choices + 1.0)






def comfort_temperature_pmv_simplified(met, clo, air_temp):
    neutral = 22.0 + (clo - 0.5) * 3.0 - (met - 1.0) * 2.0
    return air_temp - neutral






def body_mass_index(weight_kg, height_m):
    return weight_kg / (height_m * height_m)
