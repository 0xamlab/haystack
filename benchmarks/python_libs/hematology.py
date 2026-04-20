"""Python equivalent of mojo/engine/hematology.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import pow
except Exception:
    pass
try:
    from std.math import log
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

def hematocrit(rbc_volume, total_blood_volume):
    if total_blood_volume <= 0.0:
        return 0.0
    return rbc_volume / total_blood_volume



def mean_corpuscular_volume(hematocrit_fraction, rbc_count_millions):
    if rbc_count_millions <= 0.0:
        return 0.0
    return hematocrit_fraction * 10.0 / rbc_count_millions * 1000.0



def mean_corpuscular_hemoglobin(hemoglobin_g_dl, rbc_count_millions):
    if rbc_count_millions <= 0.0:
        return 0.0
    return hemoglobin_g_dl / rbc_count_millions * 10.0



def mchc(hemoglobin_g_dl, hematocrit_fraction):
    if hematocrit_fraction <= 0.0:
        return 0.0
    return hemoglobin_g_dl / hematocrit_fraction



def red_cell_distribution_width(std_mcv, mean_mcv):
    if mean_mcv <= 0.0:
        return 0.0
    return (std_mcv / mean_mcv) * 100.0



def oxygen_carrying_capacity(hemoglobin_g_dl):
    return 1.34 * hemoglobin_g_dl



def coagulation_inr(patient_pt, mean_normal_pt, isi):
    if mean_normal_pt <= 0.0:
        return 0.0
    return (patient_pt / mean_normal_pt) ** (isi)



def platelet_count_index(mean_platelet_volume, platelet_count_k):
    return mean_platelet_volume * platelet_count_k / 100.0



def blood_viscosity_relative(hematocrit_fraction):
    if hematocrit_fraction < 0.0 or hematocrit_fraction >= 1.0:
        return 1.0
    return (1.0 - hematocrit_fraction) ** (-2.5)



def erythrocyte_sedimentation(fibrinogen_g_l, age, sex_factor):
    esr = fibrinogen_g_l * 0.4 + age * 0.065 + sex_factor
    if esr < 0.0:
        return 0.0
    return esr
