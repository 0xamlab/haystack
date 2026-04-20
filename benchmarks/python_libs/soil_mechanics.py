"""Python equivalent of mojo/engine/soil_mechanics.mojo (auto-generated)."""
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

def bearing_capacity_terzaghi(cohesion, unit_weight, depth, width, phi_rad):
    from std.math import tan, cos, sin

    tan_phi = math.tan(phi_rad)
    pi = 3.141592653589793
    Nq = math.exp(pi * tan_phi) / (2.0 * math.cos(pi / 4.0 + phi_rad / 2.0) ** 2.0)
    Nc = (Nq - 1.0) / tan_phi if tan_phi > 1e-10 else 5.7
    Ng = (Nq - 1.0) * tan_phi
    return cohesion * Nc + unit_weight * depth * Nq + 0.5 * unit_weight * width * Ng



def settlement_elastic(pressure, width, modulus, poisson):
    if modulus <= 0.0:
        return 0.0
    iw = 0.82  # influence factor for square footing
    return pressure * width * (1.0 - poisson * poisson) * iw / modulus



def consolidation_degree(time_factor):
    if time_factor < 0.0:
        return 0.0
    if time_factor < 0.217:

        return math.sqrt(4.0 * time_factor / 3.14159)
    pi = 3.141592653589793
    return 1.0 - (8.0 / (pi * pi)) * math.exp(-pi * pi * time_factor / 4.0)



def void_ratio(specific_gravity, water_content, saturation):
    if saturation <= 0.0:
        return 0.0
    return specific_gravity * water_content / saturation



def relative_density(void_ratio_e, e_max, e_min):
    denom = e_max - e_min
    if denom <= 0.0:
        return 0.0
    dr = (e_max - void_ratio_e) / denom
    if dr < 0.0:
        return 0.0
    if dr > 1.0:
        return 1.0
    return dr



def liquid_limit_plasticity(liquid_limit, plastic_limit):
    pi = liquid_limit - plastic_limit
    if pi < 0.0:
        return 0.0
    return pi



def shear_strength_mohr_coulomb(cohesion, normal_stress, phi_rad):
    from std.math import tan
    return cohesion + normal_stress * math.tan(phi_rad)



def lateral_earth_pressure_ka(phi_rad):
    from std.math import tan
    pi = 3.141592653589793
    angle = pi / 4.0 - phi_rad / 2.0
    t = math.tan(angle)
    return t * t



def compression_index(liquid_limit):
    cc = 0.009 * (liquid_limit - 10.0)
    if cc < 0.0:
        return 0.0
    return cc



def hydraulic_conductivity_hazen(d10_mm):
    if d10_mm <= 0.0:
        return 0.0
    return d10_mm * d10_mm  # Hazen C ≈ 1
