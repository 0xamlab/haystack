"""Python equivalent of mojo/engine/veterinary.mojo (auto-generated)."""
import math
import random as _rng

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

def _sqrt_approx(x):
    if x <= 0.0:
        return 0.0
    guess = x * 0.5
    for _ in range(20):
        guess = (guess + x / guess) * 0.5
    return guess






def dose_mg(weight_kg, dose_per_kg):
    return weight_kg * dose_per_kg






def fluid_rate_ml_hr(total_ml, hours):
    return total_ml / hours






def fluid_deficit(weight_kg, dehydration_pct):
    return weight_kg * dehydration_pct / 100.0 * 1000.0






def maintenance_fluid_dog(weight_kg):
    return 60.0 * weight_kg






def caloric_requirement_dog(weight_kg):



    w3 = weight_kg * weight_kg * weight_kg
    s1 = _sqrt_approx(w3)
    s2 = _sqrt_approx(s1)
    return 70.0 * s2



def body_condition_score_ideal(species_code):
    return 5.0






def anesthesia_mac(species_code, agent_code):
    if species_code == 0:
        if agent_code == 0:
            return 1.3
        return 2.4  # Sevoflurane

    if agent_code == 0:
        return 1.6
    return 3.1  # Sevoflurane






def gestation_period_days(species_code):
    if species_code == 0:
        return 63.0
    elif species_code == 1:
        return 65.0
    elif species_code == 2:
        return 340.0
    elif species_code == 3:
        return 283.0
    return 0.0






def heart_rate_normal_range_low(species_code):
    if species_code == 0:
        return 60.0
    elif species_code == 1:
        return 120.0
    elif species_code == 2:
        return 28.0
    return 0.0






def heart_rate_normal_range_high(species_code):
    if species_code == 0:
        return 140.0
    elif species_code == 1:
        return 220.0
    elif species_code == 2:
        return 44.0
    return 0.0






def packed_cell_volume_normal(species_code):
    if species_code == 0:
        return 46.0
    elif species_code == 1:
        return 37.5
    return 0.0






def blood_volume_estimate(weight_kg, species_code):
    if species_code == 0:
        return weight_kg * 90.0
    elif species_code == 1:
        return weight_kg * 60.0
    return 0.0
