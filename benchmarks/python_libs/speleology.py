"""Python equivalent of mojo/engine/speleology.mojo (auto-generated)."""
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
    from std.math import sqrt
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

def cave_passage_volume(length_m, width_m, height_m):
    pi = 3.141592653589793
    return pi / 4.0 * width_m * height_m * length_m



def stalactite_growth_rate(drip_rate_ml_per_min, calcite_per_ml_mg, density_g_cm3):
    mg_per_yr = drip_rate_ml_per_min * calcite_per_ml_mg * 525960.0  # min/yr
    cm3_per_yr = mg_per_yr / (density_g_cm3 * 1000.0)
    return cm3_per_yr * 10.0  # cm3 to mm, assuming 1 cm² area



def drip_water_calcite_saturation(ca_mmol_l, co3_mmol_l, ksp):
    if ksp <= 0.0:
        return 0.0
    ip = ca_mmol_l * 1e-3 * co3_mmol_l * 1e-3
    if ip <= 0.0:
        return 0.0
    return math.log(ip / ksp) / math.log(10.0)



def cave_climate_temperature(surface_maat, depth_m, lapse_rate):
    return surface_maat + depth_m * lapse_rate



def turbulent_flow_cave(velocity, hydraulic_diameter, kinematic_viscosity):
    if kinematic_viscosity <= 0.0:
        return 0.0
    return velocity * hydraulic_diameter / kinematic_viscosity



def karst_spring_discharge(storage_m3, recession_coefficient):
    return storage_m3 * recession_coefficient



def cave_radio_signal_depth(frequency_hz, conductivity):
    mu0 = 1.2566e-6  # permeability of free space
    omega = 2.0 * 3.141592653589793 * frequency_hz
    denom = omega * mu0 * conductivity
    if denom <= 0.0:
        return 0.0
    return math.sqrt(2.0 / denom)



def dissolution_rate_limestone(saturation_index, rate_constant):
    omega = (10.0) ** (saturation_index)
    undersaturation = 1.0 - omega
    if undersaturation <= 0.0:
        return 0.0
    return rate_constant * undersaturation



def age_uranium_series(activity_ratio_230_234):
    if activity_ratio_230_234 >= 1.0 or activity_ratio_230_234 <= 0.0:
        return 0.0
    lambda230 = 9.158e-6  # per year (half-life 75,380 yr)
    return -math.log(1.0 - activity_ratio_230_234) / lambda230



def radon_in_cave_air(radon_flux, ventilation_rate, decay_constant):
    removal = ventilation_rate + decay_constant
    if removal <= 0.0:
        return 0.0
    return radon_flux / removal
