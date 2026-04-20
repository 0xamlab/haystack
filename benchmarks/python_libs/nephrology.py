"""Python equivalent of mojo/engine/nephrology.mojo (auto-generated)."""
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

def gfr_ckd_epi(creatinine_mg_dl, age, is_female):
    kappa = 0.9
    alpha = -0.411
    if is_female > 0.5:
        kappa = 0.7
        alpha = -0.329
    ratio = creatinine_mg_dl / kappa
    min_ratio = ratio if ratio < 1.0 else 1.0
    max_ratio = ratio if ratio > 1.0 else 1.0
    egfr = 141.0 * (min_ratio) ** (alpha) * (max_ratio) ** (-1.209) * (0.993) ** (age)
    if is_female > 0.5:
        egfr = egfr * 1.018
    return egfr



def creatinine_clearance_cockroft(age, weight_kg, creatinine_mg_dl, is_female):
    if creatinine_mg_dl <= 0.0:
        return 0.0
    crcl = (140.0 - age) * weight_kg / (72.0 * creatinine_mg_dl)
    if is_female > 0.5:
        crcl = crcl * 0.85
    return crcl



def fractional_excretion_sodium(urine_na, plasma_na, urine_cr, plasma_cr):
    denom = plasma_na * urine_cr
    if denom <= 0.0:
        return 0.0
    return urine_na * plasma_cr / denom * 100.0



def urine_anion_gap(urine_na, urine_k, urine_cl):
    return urine_na + urine_k - urine_cl



def transtubular_potassium_gradient(urine_k, plasma_k, urine_osm, plasma_osm):
    if plasma_k <= 0.0 or plasma_osm <= 0.0:
        return 0.0
    correction = urine_osm / plasma_osm
    if correction <= 0.0:
        return 0.0
    return (urine_k / plasma_k) / correction



def renal_plasma_flow(urine_pah_conc, plasma_pah_conc, urine_volume_ml_per_min):
    if plasma_pah_conc <= 0.0:
        return 0.0
    return urine_pah_conc * urine_volume_ml_per_min / plasma_pah_conc



def filtration_fraction(gfr, rpf):
    if rpf <= 0.0:
        return 0.0
    return gfr / rpf



def osmolar_clearance(urine_osm, urine_flow, plasma_osm):
    if plasma_osm <= 0.0:
        return 0.0
    return urine_osm * urine_flow / plasma_osm



def free_water_clearance(urine_flow, cosm):
    return urine_flow - cosm



def protein_creatinine_ratio(urine_protein_mg_dl, urine_creatinine_mg_dl):
    if urine_creatinine_mg_dl <= 0.0:
        return 0.0
    return urine_protein_mg_dl / urine_creatinine_mg_dl
