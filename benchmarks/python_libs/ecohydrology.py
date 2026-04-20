"""Python equivalent of mojo/engine/ecohydrology.mojo (auto-generated)."""
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

def interception_loss(rainfall, canopy_storage_mm, evaporation_rate):
    direct = rainfall if rainfall < canopy_storage_mm else canopy_storage_mm
    evap_additional = (rainfall - direct) * evaporation_rate
    if evap_additional < 0.0:
        evap_additional = 0.0
    return direct + evap_additional



def transpiration_priestley_taylor(net_radiation_w_m2, soil_heat_w_m2, temperature_c, alpha):
    delta = 4098.0 * 0.6108 * math.exp(17.27 * temperature_c / (temperature_c + 237.3)) / ((temperature_c + 237.3) ** 2)
    gamma = 0.067  # kPa/°C at standard conditions
    lambda_v = 2.45  # MJ/kg latent heat of vaporisation
    rn_g = (net_radiation_w_m2 - soil_heat_w_m2) * 86400.0 / 1e6  # W/m² to MJ/m²/day
    return alpha * delta / (delta + gamma) * rn_g / lambda_v



def root_water_uptake(soil_moisture, field_capacity, wilting_point, max_uptake):
    range = field_capacity - wilting_point
    if range <= 0.0:
        return 0.0
    frac = (soil_moisture - wilting_point) / range
    if frac < 0.0:
        return 0.0
    if frac > 1.0:
        frac = 1.0
    return max_uptake * frac



def streamflow_baseflow_index(baseflow_mm, total_streamflow_mm):
    if total_streamflow_mm <= 0.0:
        return 0.0
    return baseflow_mm / total_streamflow_mm



def wetland_retention_time(volume_m3, inflow_m3_per_day):
    if inflow_m3_per_day <= 0.0:
        return 0.0
    return volume_m3 / inflow_m3_per_day



def riparian_buffer_efficiency(width_m, slope, saturated_conductivity):
    if saturated_conductivity <= 0.0:
        return 0.0
    hrt = width_m * slope / saturated_conductivity
    k_removal = 0.1  # typical first-order N removal rate (day⁻¹)
    eff = 1.0 - math.exp(-k_removal * hrt)
    if eff < 0.0:
        return 0.0
    return eff



def ecohydrological_stress(soil_moisture, field_capacity, wilting_point):
    range = field_capacity - wilting_point
    if range <= 0.0:
        return 0.0
    beta = (soil_moisture - wilting_point) / range
    if beta < 0.0:
        return 0.0
    if beta > 1.0:
        return 1.0
    return beta



def flood_pulse_benefit(flood_duration_days, nutrient_input, productivity_rate):
    return flood_duration_days * nutrient_input * productivity_rate / 365.0



def water_table_depth_et(water_table_m, extinction_depth_m, pet):
    if extinction_depth_m <= 0.0:
        return 0.0
    factor = 1.0 - water_table_m / extinction_depth_m
    if factor < 0.0:
        return 0.0
    return pet * factor



def catchment_runoff_ratio(annual_runoff_mm, annual_precipitation_mm):
    if annual_precipitation_mm <= 0.0:
        return 0.0
    return annual_runoff_mm / annual_precipitation_mm
