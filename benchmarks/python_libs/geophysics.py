"""Python equivalent of mojo/engine/geophysics.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import sin
except Exception:
    pass
try:
    from std.math import cos
except Exception:
    pass
try:
    from std.math import log
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

def gravity_anomaly_bouguer(observed_g, latitude_rad, elevation_m, rock_density):

    g_th = 978032.7 * (1.0 + 0.005302 * math.sin(latitude_rad) ** 2.0
               - 0.0000058 * math.sin(2.0 * latitude_rad) ** 2.0) / 1000.0
    fac = 0.3086 * elevation_m   # mGal
    bouguer = 0.04191 * rock_density * elevation_m  # mGal
    return observed_g - g_th + fac - bouguer



def gravitational_acceleration(latitude_rad, elevation_m):
    ge = 9.7803267714
    re = 6.371e6  # mean Earth radius m
    s = math.sin(latitude_rad)
    g_lat = ge * (1.0 + 0.00193185 * s * s)
    return g_lat * (1.0 - 2.0 * elevation_m / re)



def magnetic_inclination(bz, bh):
    if bh == 0.0:
        return 1e9  # vertical field
    return bz / bh



def seismic_p_wave_velocity(bulk_modulus, shear_modulus, density):
    if density <= 0.0:
        return 0.0
    M = (bulk_modulus + 4.0 * shear_modulus / 3.0) * 1e9  # GPa → Pa
    return math.sqrt(M / density)



def seismic_s_wave_velocity(shear_modulus, density):
    if density <= 0.0:
        return 0.0
    return math.sqrt(shear_modulus * 1e9 / density)



def depth_from_reflection(two_way_time, velocity):
    return velocity * two_way_time / 2.0



def vp_vs_ratio(vp, vs):
    if vs <= 0.0:
        return 0.5
    r = vp / vs
    num = r * r - 2.0
    den = 2.0 * (r * r - 1.0)
    if den <= 0.0:
        return 0.5
    return num / den



def earth_radius_at_latitude(latitude_rad):
    a = 6378137.0      # equatorial radius m
    b = 6356752.314    # polar radius m
    cos_lat = math.cos(latitude_rad)
    sin_lat = math.sin(latitude_rad)
    num = (a * a * cos_lat) ** 2.0 + (b * b * sin_lat) ** 2.0
    den = (a * cos_lat) ** 2.0 + (b * sin_lat) ** 2.0
    if den <= 0.0:
        return a
    return math.sqrt(num / den)



def free_air_correction(elevation_m):
    return 0.3086 * elevation_m



def isostasy_airy(topography_m, crust_density, mantle_density):
    drho = mantle_density - crust_density
    if drho <= 0.0:
        return 0.0
    return topography_m * crust_density / drho
