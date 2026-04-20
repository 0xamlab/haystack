"""Python equivalent of mojo/engine/lidar.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import abs
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
    from std.math import atan
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

def range_from_tof(time_of_flight, c=3.0e8):
    return c * time_of_flight / 2.0



def point_density(n_points, area):
    if area <= 0.0:
        return 0.0
    return n_points / area



def scan_swath_width(altitude, scan_angle_deg):
    half_angle_rad = (scan_angle_deg / 2.0) * math.pi / 180.0
    tan_val = math.sin(half_angle_rad) / math.cos(half_angle_rad)
    return 2.0 * altitude * tan_val



def footprint_diameter(altitude, divergence_mrad):
    return altitude * divergence_mrad / 1000.0



def pulse_repetition_frequency_to_point_rate(prf, scan_lines_per_sec=1.0, points_per_line=1.0):
    return prf



def ground_sampling_distance(altitude, focal_length, pixel_size):
    if focal_length <= 0.0:
        return 0.0
    return altitude * pixel_size / focal_length



def vegetation_index_from_returns(first_returns, last_returns):
    if first_returns <= 0.0:
        return 0.0
    return (first_returns - last_returns) / first_returns * 100.0



def canopy_height(dsm, dtm):
    return dsm - dtm



def slope_from_elevation(dz, dx):
    if abs(dx) < 1e-15:
        return 90.0
    return math.atan(dz / dx) * 180.0 / math.pi



def intensity_normalization(intensity, range_val, ref_range):
    if ref_range <= 0.0:
        return 0.0
    ratio = range_val / ref_range
    return intensity * ratio * ratio



def overlap_percentage(swath_width, strip_spacing):
    if swath_width <= 0.0:
        return 0.0
    return (swath_width - strip_spacing) / swath_width * 100.0



def point_cloud_file_size_mb(n_points, bytes_per_point):
    return n_points * bytes_per_point / 1.0e6
