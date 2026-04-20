"""Python equivalent of mojo/engine/geodesy.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sin
except Exception:
    pass
try:
    from std.math import cos
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import asin
except Exception:
    pass
try:
    from std.math import atan2
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import tan
except Exception:
    pass

PI = 3.141592653589793
EARTH_RADIUS_KM = 6371.0
WGS84_A = 6378137.0          # semi-major axis (m)
WGS84_B = 6356752.314245      # semi-minor axis (m)
WGS84_F = 1.0 / 298.257223563 # flattening

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

def _deg2rad(d):
    return d * math.pi / 180.0



def _rad2deg(r):
    return r * 180.0 / math.pi






def haversine_distance(lat1, lon1, lat2, lon2):
    p1 = _deg2rad(lat1)
    p2 = _deg2rad(lat2)
    dp = _deg2rad(lat2 - lat1)
    dl = _deg2rad(lon2 - lon1)
    a = math.sin(dp / 2.0) * math.sin(dp / 2.0) + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) * math.sin(dl / 2.0)
    sq = math.sqrt(a)
    if sq > 1.0:
        sq = 1.0
    return 2.0 * EARTH_RADIUS_KM * math.asin(sq)






def vincenty_distance(lat1, lon1, lat2, lon2):
    u1 = math.atan2((1.0 - WGS84_F) * math.sin(_deg2rad(lat1)), math.cos(_deg2rad(lat1)))
    u2 = math.atan2((1.0 - WGS84_F) * math.sin(_deg2rad(lat2)), math.cos(_deg2rad(lat2)))
    L = _deg2rad(lon2 - lon1)
    lam = L
    sin_u1 = math.sin(u1)
    cos_u1 = math.cos(u1)
    sin_u2 = math.sin(u2)
    cos_u2 = math.cos(u2)

    for _ in range(100):
        sin_lam = math.sin(lam)
        cos_lam = math.cos(lam)
        sin_sig = math.sqrt(
            (cos_u2 * sin_lam) * (cos_u2 * sin_lam)
            + (cos_u1 * sin_u2 - sin_u1 * cos_u2 * cos_lam)
            * (cos_u1 * sin_u2 - sin_u1 * cos_u2 * cos_lam)
        )
        if sin_sig < 1e-12:
            return 0.0  # coincident points
        cos_sig = sin_u1 * sin_u2 + cos_u1 * cos_u2 * cos_lam
        sig = math.atan2(sin_sig, cos_sig)
        sin_alpha = cos_u1 * cos_u2 * sin_lam / sin_sig
        cos2_alpha = 1.0 - sin_alpha * sin_alpha
        cos_2sigm = 0.0
        if cos2_alpha > 1e-12:
            cos_2sigm = cos_sig - 2.0 * sin_u1 * sin_u2 / cos2_alpha
        C = WGS84_F / 16.0 * cos2_alpha * (4.0 + WGS84_F * (4.0 - 3.0 * cos2_alpha))
        lam_prev = lam
        lam = L + (1.0 - C) * WGS84_F * sin_alpha * (
            sig + C * sin_sig * (cos_2sigm + C * cos_sig * (-1.0 + 2.0 * cos_2sigm * cos_2sigm))
        )
        if math.fabs(lam - lam_prev) < 1e-12:

            u_sq = cos2_alpha * (WGS84_A * WGS84_A - WGS84_B * WGS84_B) / (WGS84_B * WGS84_B)
            A_v = 1.0 + u_sq / 16384.0 * (4096.0 + u_sq * (-768.0 + u_sq * (320.0 - 175.0 * u_sq)))
            B_v = u_sq / 1024.0 * (256.0 + u_sq * (-128.0 + u_sq * (74.0 - 47.0 * u_sq)))
            dsig = B_v * sin_sig * (
                cos_2sigm + B_v / 4.0 * (
                    cos_sig * (-1.0 + 2.0 * cos_2sigm * cos_2sigm)
                    - B_v / 6.0 * cos_2sigm * (-3.0 + 4.0 * sin_sig * sin_sig) * (-3.0 + 4.0 * cos_2sigm * cos_2sigm)
                )
            )
            return WGS84_B * A_v * (sig - dsig) / 1000.0  # m → km


    return haversine_distance(lat1, lon1, lat2, lon2)






def initial_bearing(lat1, lon1, lat2, lon2):
    p1 = _deg2rad(lat1)
    p2 = _deg2rad(lat2)
    dl = _deg2rad(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    brng = _rad2deg(math.atan2(x, y))
    while brng < 0.0:
        brng += 360.0
    while brng >= 360.0:
        brng -= 360.0
    return brng






def destination_point(lat, lon, bearing_deg, distance_km):
    p1 = _deg2rad(lat)
    l1 = _deg2rad(lon)
    brng = _deg2rad(bearing_deg)
    d = distance_km / EARTH_RADIUS_KM
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(brng))
    l2 = l1 + math.atan2(math.sin(brng) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    result = []
    result.append(_rad2deg(p2))
    result.append(_rad2deg(l2))
    return result






def midpoint(lat1, lon1, lat2, lon2):
    p1 = _deg2rad(lat1)
    p2 = _deg2rad(lat2)
    l1 = _deg2rad(lon1)
    dl = _deg2rad(lon2 - lon1)
    bx = math.cos(p2) * math.cos(dl)
    by = math.cos(p2) * math.sin(dl)
    p3 = math.atan2(math.sin(p1) + math.sin(p2), math.sqrt((math.cos(p1) + bx) * (math.cos(p1) + bx) + by * by))
    l3 = l1 + math.atan2(by, math.cos(p1) + bx)
    result = []
    result.append(_rad2deg(p3))
    result.append(_rad2deg(l3))
    return result






def cross_track_distance(lat, lon, start_lat, start_lon, end_lat, end_lon):
    d13 = haversine_distance(start_lat, start_lon, lat, lon) / EARTH_RADIUS_KM  # angular
    b13 = _deg2rad(initial_bearing(start_lat, start_lon, lat, lon))
    b12 = _deg2rad(initial_bearing(start_lat, start_lon, end_lat, end_lon))
    dxt = math.asin(math.sin(d13) * math.sin(b13 - b12))
    return math.fabs(dxt) * EARTH_RADIUS_KM






def along_track_distance(lat, lon, start_lat, start_lon, end_lat, end_lon):
    d13 = haversine_distance(start_lat, start_lon, lat, lon) / EARTH_RADIUS_KM
    dxt = cross_track_distance(lat, lon, start_lat, start_lon, end_lat, end_lon) / EARTH_RADIUS_KM
    cos_dxt = math.cos(dxt)
    if math.fabs(cos_dxt) < 1e-15:
        return 0.0
    dat = math.asin(math.sqrt(math.fabs(math.sin(d13) * math.sin(d13) - math.sin(dxt) * math.sin(dxt))) / cos_dxt)
    return dat * EARTH_RADIUS_KM






def geodetic_to_ecef(lat, lon, alt):
    p = _deg2rad(lat)
    l = _deg2rad(lon)
    e2 = 1.0 - (WGS84_B * WGS84_B) / (WGS84_A * WGS84_A)
    sin_p = math.sin(p)
    cos_p = math.cos(p)
    N = WGS84_A / math.sqrt(1.0 - e2 * sin_p * sin_p)
    result = []
    result.append((N + alt) * cos_p * math.cos(l))
    result.append((N + alt) * cos_p * math.sin(l))
    result.append((N * (1.0 - e2) + alt) * sin_p)
    return result






def ecef_to_geodetic(x, y, z):
    e2 = 1.0 - (WGS84_B * WGS84_B) / (WGS84_A * WGS84_A)
    lon = math.atan2(y, x)
    p = math.sqrt(x * x + y * y)
    lat = math.atan2(z, p * (1.0 - e2))
    for _ in range(10):
        sin_lat = math.sin(lat)
        N = WGS84_A / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
        lat = math.atan2(z + e2 * N * sin_lat, p)
    sin_lat = math.sin(lat)
    N = WGS84_A / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    cos_lat = math.cos(lat)
    alt = 0.0
    if math.fabs(cos_lat) > 1e-10:
        alt = p / cos_lat - N
    else:
        alt = math.fabs(z) - WGS84_B
    result = []
    result.append(_rad2deg(lat))
    result.append(_rad2deg(lon))
    result.append(alt)
    return result






def rhumb_distance(lat1, lon1, lat2, lon2):
    p1 = _deg2rad(lat1)
    p2 = _deg2rad(lat2)
    dp = p2 - p1
    dl = _deg2rad(lon2 - lon1)

    dpsi = math.log(math.tan(math.pi / 4.0 + p2 / 2.0) / math.tan(math.pi / 4.0 + p1 / 2.0))
    q = 0.0
    if math.fabs(dpsi) > 1e-12:
        q = dp / dpsi
    else:
        q = math.cos(p1)

    while dl > math.pi:
        dl -= 2.0 * math.pi
    while dl < -math.pi:
        dl += 2.0 * math.pi
    dist = math.sqrt(dp * dp + q * q * dl * dl) * EARTH_RADIUS_KM
    return dist
