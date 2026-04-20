"""Python equivalent of mojo/engine/neuropharmacology.mojo (auto-generated)."""
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

def receptor_occupancy_brain(free_plasma_conc, kp_uu, kd):
    c_brain = free_plasma_conc * kp_uu
    denom = kd + c_brain
    if denom <= 0.0:
        return 0.0
    return c_brain / denom



def blood_brain_barrier_efflux(a_to_b_papp, b_to_a_papp):
    if a_to_b_papp <= 0.0:
        return 0.0
    return b_to_a_papp / a_to_b_papp



def receptor_binding_ki(ic50, radioligand_conc, radioligand_kd):
    return ic50 / (1.0 + radioligand_conc / radioligand_kd)



def synapse_neurotransmitter_level(release_rate, reuptake_rate, degradation_rate):
    clearance = reuptake_rate + degradation_rate
    if clearance <= 0.0:
        return 0.0
    return release_rate / clearance



def bbb_penetration_ratio(brain_conc, plasma_conc):
    if plasma_conc <= 0.0:
        return 0.0
    return brain_conc / plasma_conc



def cns_drug_exposure(kp, free_fraction_brain, free_fraction_plasma):
    if free_fraction_plasma <= 0.0:
        return 0.0
    return kp * free_fraction_brain / free_fraction_plasma



def d2_receptor_occupancy(plasma_conc, ec50):
    denom = ec50 + plasma_conc
    if denom <= 0.0:
        return 0.0
    return 100.0 * plasma_conc / denom



def minimal_effective_dose_cns(ec20_nM, fu_plasma, kp_uu, clearance_l_per_h):
    c_plasma_free = ec20_nM / kp_uu
    if fu_plasma <= 0.0:
        return 0.0
    c_plasma_total = c_plasma_free / fu_plasma
    return c_plasma_total * clearance_l_per_h



def cns_side_effect_threshold(therapeutic_occupancy, selectivity_ratio):
    if selectivity_ratio <= 0.0:
        return 0.0
    return therapeutic_occupancy / selectivity_ratio



def neuronal_firing_modulation(baseline_hz, drug_effect, receptor_occupancy):
    return baseline_hz * (1.0 + drug_effect * receptor_occupancy)
