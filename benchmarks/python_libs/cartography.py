"""Python equivalent of mojo/engine/cartography.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import log
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
    from std.math import acos
except Exception:
    pass
try:
    from std.math import floor
except Exception:
    pass

PI = 3.141592653589793

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

def scale_factor(map_distance, ground_distance):
    if math.fabs(ground_distance) < 1e-30:
        return 0.0
    return map_distance / ground_distance






def representative_fraction(map_cm, ground_cm):
    if math.fabs(map_cm) < 1e-30:
        return 0.0
    return ground_cm / map_cm






def ground_distance_from_map(map_distance, scale_denominator):
    return map_distance * scale_denominator






def map_distance_from_ground(ground_distance, scale_denominator):
    if math.fabs(scale_denominator) < 1e-30:
        return 0.0
    return ground_distance / scale_denominator






def latitude_to_utm_zone(longitude):
    return int(math.floor((longitude + 180.0) / 6.0)) + 1






def mercator_y(latitude_rad):
    arg = math.pi / 4.0 + latitude_rad / 2.0

    c = math.cos(arg)
    if math.fabs(c) < 1e-30:
        return 0.0
    t = math.sin(arg) / c
    if t <= 0.0:
        return 0.0
    return math.log(t)






def equirectangular_x(longitude_rad, central_meridian, cos_lat):
    return (longitude_rad - central_meridian) * cos_lat






def equirectangular_y(latitude_rad):
    return latitude_rad






def great_circle_distance(lat1, lon1, lat2, lon2, radius):
    cos_angle = math.sin(lat1) * math.sin(lat2) + math.cos(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)

    if cos_angle > 1.0:
        cos_angle = 1.0
    if cos_angle < -1.0:
        cos_angle = -1.0
    return radius * math.acos(cos_angle)






def map_area_at_scale(real_area, scale_denominator):
    s2 = scale_denominator * scale_denominator
    if math.fabs(s2) < 1e-30:
        return 0.0
    return real_area / s2






def contour_interval_suggestion(elevation_range, n_contours):
    if math.fabs(n_contours) < 1e-30:
        return 0.0
    return elevation_range / n_contours






def declination_correction(bearing, declination):
    return bearing + declination
