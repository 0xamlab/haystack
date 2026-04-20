"""Python equivalent of mojo/engine/astronomy.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import cos
except Exception:
    pass
try:
    from std.math import sin
except Exception:
    pass
try:
    from std.math import tan
except Exception:
    pass
try:
    from std.math import acos
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import log10
except Exception:
    pass
try:
    from std.math import pow
except Exception:
    pass
try:
    from std.math import floor
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass

PI = 3.14159265358979323846
DEG2RAD = math.pi / 180.0
RAD2DEG = 180.0 / math.pi

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

def _atan2(y, x):
    r = math.sqrt(x * x + y * y)
    if r < 1e-15:
        return 0.0
    angle = math.acos(x / r)
    if y < 0.0:
        angle = -angle
    return angle

def julian_date(year, month, day):
    y = year
    m = month
    if m <= 2:
        y -= 1
        m += 12
    A = int(math.floor(float(y) / 100.0))
    B = 2 - A + int(math.floor(float(A) / 4.0))
    jd = math.floor(365.25 * float(y + 4716)) + math.floor(30.6001 * float(m + 1)) + float(day) + float(B) - 1524.5
    return jd






def modified_julian_date(jd):
    return jd - 2400000.5






def sidereal_time(jd, longitude):
    T = (jd - 2451545.0) / 36525.0

    gmst = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * T * T - T * T * T / 38710000.0

    lst = gmst + longitude

    lst = lst - math.floor(lst / 360.0) * 360.0
    if lst < 0.0:
        lst += 360.0

    return lst / 15.0






def solar_declination(day_of_year):
    angle = 360.0 / 365.0 * float(day_of_year + 10) * DEG2RAD
    return -23.45 * math.cos(angle)






def sunrise_hour_angle(latitude, declination):
    lat_rad = latitude * DEG2RAD
    dec_rad = declination * DEG2RAD
    cos_ha = -math.tan(lat_rad) * math.tan(dec_rad)
    if cos_ha > 1.0:
        return 0.0  # No sunrise (polar night)
    if cos_ha < -1.0:
        return 180.0  # No sunset (midnight sun)
    return math.acos(cos_ha) * RAD2DEG






def day_length(latitude, day_of_year):
    dec = solar_declination(day_of_year)
    ha = sunrise_hour_angle(latitude, dec)

    return 2.0 * ha / 15.0






def parallax_correction(distance_au, radius_earth):
    if distance_au <= 0.0:
        return 0.0


    d_meters = distance_au * 1.496e11
    p_rad = radius_earth / d_meters
    return p_rad * 206265.0  # radians to arcseconds






def kepler_equation(M, e, tol=1e-10):
    E = M  # Initial guess
    max_iter = 100
    for _ in range(max_iter):
        dE = (math.e - e * math.sin(math.e) - M) / (1.0 - e * math.cos(math.e))
        E -= dE
        if math.fabs(dE) < tol:
            break
    return math.e






def orbital_period(semi_major_au):
    return (semi_major_au) ** (1.5)






def apparent_magnitude(abs_mag, distance_pc):
    if distance_pc <= 0.0:
        return 0.0
    return abs_mag + 5.0 * math.log10(distance_pc) - 5.0






def distance_from_magnitude(abs_mag, app_mag):
    return (10.0) ** ((app_mag - abs_mag + 5.0) / 5.0)






def ecliptic_to_equatorial(ecliptic_lon, ecliptic_lat, obliquity):
    lon_r = ecliptic_lon * DEG2RAD
    lat_r = ecliptic_lat * DEG2RAD
    eps_r = obliquity * DEG2RAD


    sin_dec = math.sin(lat_r) * math.cos(eps_r) + math.cos(lat_r) * math.sin(eps_r) * math.sin(lon_r)

    if sin_dec > 1.0:
        sin_dec = 1.0
    if sin_dec < -1.0:
        sin_dec = -1.0
    dec = math.acos(math.sqrt(1.0 - sin_dec * sin_dec)) * RAD2DEG
    if sin_dec < 0.0:
        dec = -dec


    y_val = math.sin(lon_r) * math.cos(eps_r) - math.tan(lat_r) * math.sin(eps_r)
    x_val = math.cos(lon_r)

    ra_rad = _atan2(y_val, x_val)
    ra = ra_rad * RAD2DEG

    ra = ra - math.floor(ra / 360.0) * 360.0
    if ra < 0.0:
        ra += 360.0

    result = []
    result.append(ra)
    result.append(dec)
    return result


