"""Python equivalent of mojo/engine/bryology.mojo (auto-generated)."""
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

def sphagnum_water_holding(dry_mass_g, saturated_mass_g):
    if dry_mass_g <= 0.0:
        return 0.0
    return (saturated_mass_g - dry_mass_g) / dry_mass_g



def moss_growth_rate(initial_mass_g, final_mass_g, days):
    if initial_mass_g <= 0.0 or final_mass_g <= 0.0 or days <= 0.0:
        return 0.0
    return math.log(final_mass_g / initial_mass_g) / days



def carbon_accumulation_peatland(npp_g_c_m2_yr, decomposition_g_c_m2_yr):
    return npp_g_c_m2_yr - decomposition_g_c_m2_yr



def bryophyte_desiccation_recovery(time_h, k_recovery, max_recovery):
    return max_recovery * (1.0 - math.exp(-k_recovery * time_h))



def nitrogen_deposition_effect(n_deposition_kg_ha_yr, optimal_n_kg_ha_yr):
    if optimal_n_kg_ha_yr <= 0.0:
        return 0.0
    diff = n_deposition_kg_ha_yr - optimal_n_kg_ha_yr
    if diff < 0.0:
        diff = -diff
    response = 1.0 - diff / optimal_n_kg_ha_yr
    if response < 0.0:
        return 0.0
    return response



def moss_photosynthesis_rate(par_umol_m2_s, pmax, half_sat_par, water_potential_mpa):
    denom = half_sat_par + par_umol_m2_s
    if denom <= 0.0:
        return 0.0
    light_response = pmax * par_umol_m2_s / denom
    psi_50 = -2.0  # MPa at 50% inhibition
    water_factor = math.exp(water_potential_mpa / (-psi_50))
    if water_factor > 1.0:
        water_factor = 1.0
    return light_response * water_factor



def peat_accumulation_rate(productivity_mm_yr, humification_factor):
    return productivity_mm_yr * (1.0 - humification_factor)



def sphagnum_acidity(cation_exchange_capacity, base_saturation):
    return 3.0 + 2.0 * base_saturation / 100.0



def patch_colonisation_probability(spore_rain, substrate_suitability, moisture_factor):
    p = spore_rain * substrate_suitability * moisture_factor
    if p > 1.0:
        return 1.0
    return p



def biomass_to_litter_ratio(standing_biomass_g_m2, annual_litter_g_m2_yr):
    if annual_litter_g_m2_yr <= 0.0:
        return 0.0
    return standing_biomass_g_m2 / annual_litter_g_m2_yr
