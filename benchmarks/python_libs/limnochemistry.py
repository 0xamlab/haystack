"""Python equivalent of mojo/engine/limnochemistry.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import exp
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

def carbonate_alkalinity(hco3_meq_l, co3_meq_l, oh_meq_l, h_meq_l):
    return hco3_meq_l + 2.0 * co3_meq_l + oh_meq_l - h_meq_l



def ionic_strength(concentrations, charges_sq):
    return 0.5 * charges_sq



def activity_coefficient_davies(ionic_strength, charge):
    a = 0.5085
    si = math.sqrt(ionic_strength)
    log_gamma = -a * charge * charge * (si / (1.0 + si) - 0.3 * ionic_strength)
    return pow_10(log_gamma)



def pow_10(x):
    return math.exp(x * math.log(10.0))



def saturation_index_calcite(ca_mmol_l, alk_meq_l, ph, temp_c):
    if ca_mmol_l <= 0.0 or alk_meq_l <= 0.0:
        return -1.0
    ph_sat = 11.73 - 0.053 * temp_c - math.log(ca_mmol_l) / math.log(10.0) - math.log(alk_meq_l) / math.log(10.0)
    return ph - ph_sat



def silicon_weathering_flux(si_conc_umol_l, discharge_m3_s, catchment_km2):
    if catchment_km2 <= 0.0:
        return 0.0
    flux_mol_s = si_conc_umol_l * 1e-6 * discharge_m3_s * 1000.0
    return flux_mol_s * 31557600.0 / catchment_km2



def redox_pe_eh(eh_mv, temperature_c):
    T_K = temperature_c + 273.15
    factor = 11604.5 / T_K  # F / (R × 2.303)
    return eh_mv / 1000.0 * factor



def phosphorus_fractionation(total_p_ug_l, dissolved_p_ug_l):
    pp = total_p_ug_l - dissolved_p_ug_l
    if pp < 0.0:
        return 0.0
    return pp



def nitrogen_speciation(nh4_mg_l, no3_mg_l, no2_mg_l):
    return nh4_mg_l + no3_mg_l + no2_mg_l



def doc_light_attenuation(doc_mg_l, specific_absorption):
    return specific_absorption * doc_mg_l



def epilimnion_mixing_depth(surface_temp_c, bottom_temp_c, total_depth_m):
    delta_t = surface_temp_c - bottom_temp_c
    if delta_t <= 0.0:
        return total_depth_m  # fully mixed
    threshold = 1.0  # °C/m typical thermocline criterion
    return total_depth_m * threshold / delta_t
