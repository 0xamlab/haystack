"""Python equivalent of mojo/engine/nutrition.mojo (auto-generated)."""
import math
import random as _rng

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

def bmi(weight_kg, height_m):
    return weight_kg / (height_m * height_m)






def bmi_category(bmi_val):
    if bmi_val < 18.5:
        return 0
    elif bmi_val < 25.0:
        return 1
    elif bmi_val < 30.0:
        return 2
    else:
        return 3






def bmr_mifflin(weight_kg, height_cm, age, is_male):
    base = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * float(age)
    if is_male:
        return base + 5.0
    return base - 161.0






def tdee(bmr_val, activity_level):
    return bmr_val * activity_level






def caloric_deficit(tdee_val, target_loss_kg_per_week):
    return target_loss_kg_per_week * 7700.0 / 7.0






def macro_split(calories, protein_pct, fat_pct):
    carb_pct = 1.0 - protein_pct - fat_pct
    protein_g = (calories * protein_pct) / 4.0
    fat_g = (calories * fat_pct) / 9.0
    carb_g = (calories * carb_pct) / 4.0
    result = []
    result.append(protein_g)
    result.append(fat_g)
    result.append(carb_g)
    return result






def ideal_body_weight(height_cm, is_male):
    inches = height_cm / 2.54
    if is_male:
        return 50.0 + 2.3 * (inches - 60.0)
    return 45.5 + 2.3 * (inches - 60.0)






def body_fat_estimate(bmi_val, age, is_male):
    sex_factor = 1.0 if is_male else 0.0
    return 1.20 * bmi_val + 0.23 * float(age) - 10.8 * sex_factor - 5.4






def water_intake(weight_kg):
    return weight_kg * 0.033






def heart_rate_max(age):
    return 220 - age






def target_heart_rate(hr_max, intensity_low, intensity_high):
    result = []
    result.append(float(hr_max) * intensity_low)
    result.append(float(hr_max) * intensity_high)
    return result






def vo2max_estimate(hr_rest, hr_max):
    return 15.3 * (float(hr_max) / float(hr_rest))
