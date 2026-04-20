"""Python equivalent of mojo/engine/oceanography.mojo (auto-generated)."""
import math
import random as _rng

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

def seawater_density(temperature, salinity):

    return (1000.0
            - 0.0682 * temperature
            + 0.00817 * temperature * temperature * 0.01
            + 0.7814 * salinity * 0.01)



def buoyancy_frequency(rho_upper, rho_lower, layer_thickness):
    if layer_thickness <= 0.0 or rho_upper <= 0.0:
        return 0.0
    g = 9.81
    drho_dz = (rho_lower - rho_upper) / layer_thickness
    n2 = -g / rho_upper * drho_dz  # N² = -g/ρ * dρ/dz
    if n2 <= 0.0:
        return 0.0
    return math.sqrt(n2)



def tidal_force(mass_moon, distance_m, radius_earth):
    if distance_m <= 0.0:
        return 0.0
    G = 6.674e-11
    return 2.0 * G * mass_moon * radius_earth / (distance_m * distance_m * distance_m)



def geostrophic_velocity(pressure_gradient, density, coriolis):
    if density <= 0.0 or coriolis == 0.0:
        return 0.0
    return -pressure_gradient / (density * coriolis)



def ekman_depth(wind_stress, coriolis):
    if coriolis <= 0.0 or wind_stress <= 0.0:
        return 0.0
    pi = 3.141592653589793
    rho = 1025.0  # typical seawater density
    Av = 0.01  # eddy viscosity m²/s (typical)
    return pi * math.sqrt(2.0 * Av / abs(coriolis))



def mixed_layer_heat_flux(density, heat_capacity, depth, delta_temp, delta_time):
    if delta_time <= 0.0:
        return 0.0
    return density * heat_capacity * depth * delta_temp / delta_time



def salinity_from_chlorinity(chlorinity):
    return 1.80655 * chlorinity



def wave_celerity_shallow(depth):
    if depth <= 0.0:
        return 0.0
    g = 9.81
    return math.sqrt(g * depth)



def wave_celerity_deep(period):
    if period <= 0.0:
        return 0.0
    g = 9.81
    pi = 3.141592653589793
    return g * period / (2.0 * pi)



def freshwater_flux(evaporation, precipitation, area):
    return (evaporation - precipitation) * area
