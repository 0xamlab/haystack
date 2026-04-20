"""Python equivalent of mojo/engine/horticulture.mojo (auto-generated)."""
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

def photosynthesis_rate(light_intensity, pmax, light_saturation):
    denom = light_saturation + light_intensity
    if denom <= 0.0:
        return 0.0
    return pmax * light_intensity / denom



def crop_growth_rate(net_assimilation_rate, leaf_area_index):
    return net_assimilation_rate * leaf_area_index



def net_assimilation_rate(biomass_2, biomass_1, lai_2, lai_1, days):
    if days <= 0.0 or lai_1 <= 0.0 or lai_2 <= lai_1:
        return 0.0
    mean_lai = (lai_2 - lai_1) / math.log(lai_2 / lai_1)
    if mean_lai <= 0.0:
        return 0.0
    return (biomass_2 - biomass_1) / (mean_lai * days)



def specific_leaf_area(leaf_area_cm2, leaf_dry_mass_g):
    if leaf_dry_mass_g <= 0.0:
        return 0.0
    return leaf_area_cm2 / leaf_dry_mass_g



def transplant_shock_index(root_damage_fraction, stomatal_conductance_ratio):
    return root_damage_fraction * (1.0 - stomatal_conductance_ratio)



def fertigation_dose(target_conc_mg_l, flow_rate_l_h, stock_conc_g_l):
    if stock_conc_g_l <= 0.0:
        return 0.0

    return target_conc_mg_l * flow_rate_l_h / stock_conc_g_l



def vpd_plant(leaf_temp, air_temp, relative_humidity):
    a = 17.27
    b = 237.7
    es_leaf = 0.6108 * math.exp(a * leaf_temp / (b + leaf_temp))
    es_air = 0.6108 * math.exp(a * air_temp / (b + air_temp))
    return es_leaf - es_air * relative_humidity / 100.0



def chilling_requirement(daily_temps, threshold_temp, days):
    if daily_temps >= threshold_temp:
        return 0.0

    return days * 24.0



def pruning_efficiency(pre_prune_lai, target_lai):
    if pre_prune_lai <= 0.0:
        return 0.0
    k = 0.5  # extinction coefficient
    i_before = 1.0 - math.exp(-k * pre_prune_lai)
    i_after = 1.0 - math.exp(-k * target_lai)
    return i_before - i_after



def rooting_hormone_index(auxin_concentration, optimal_conc):
    sigma = optimal_conc / 2.0
    if sigma <= 0.0:
        return 0.0
    ratio = (auxin_concentration - optimal_conc) / sigma
    return math.exp(-ratio * ratio)
