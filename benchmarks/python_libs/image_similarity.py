"""Python equivalent of mojo/engine/image_similarity.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log as _log
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

def _pixel_count(width, height):
    if width <= 0 or height <= 0:
        return 0
    return width * height



def _pixel_value(flat, index):
    if index < 0 or index >= len(flat):
        return 0.0
    return flat[index]



def _abs(v):
    return -v if v < 0.0 else v



def _clamp01(v):
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v



def mean_squared_error_flat(flat_a, flat_b, width, height):
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    total = 0.0
    for index in range(pixels):
        diff = _pixel_value(flat_a, index) - _pixel_value(flat_b, index)
        total += diff * diff
    return total / float(pixels)



def mean_abs_error_flat(flat_a, flat_b, width, height):
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    total = 0.0
    for index in range(pixels):
        total += _abs(_pixel_value(flat_a, index) - _pixel_value(flat_b, index))
    return total / float(pixels)



def psnr_flat(flat_a, flat_b, width, height, max_value):
    if max_value <= 0.0:
        return 0.0
    mse = mean_squared_error_flat(flat_a, flat_b, width, height)
    if mse <= 1e-12:
        return 99.0
    return 10.0 * (math.log((max_value * max_value) / mse) / math.log(10.0))

def normalized_cross_correlation_flat(flat_a, flat_b, width, height):
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    mean_a = 0.0
    mean_b = 0.0
    for index in range(pixels):
        mean_a += _pixel_value(flat_a, index)
        mean_b += _pixel_value(flat_b, index)
    mean_a /= float(pixels)
    mean_b /= float(pixels)

    numerator = 0.0
    denom_a = 0.0
    denom_b = 0.0
    for index in range(pixels):
        da = _pixel_value(flat_a, index) - mean_a
        db = _pixel_value(flat_b, index) - mean_b
        numerator += da * db
        denom_a += da * da
        denom_b += db * db
    denom = math.sqrt(denom_a * denom_b)
    if denom <= 1e-12:
        return 1.0 if mean_abs_error_flat(flat_a, flat_b, width, height) <= 1e-12 else 0.0
    return numerator / denom

def ssim_global_flat(flat_a, flat_b, width, height):
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    mean_a = 0.0
    mean_b = 0.0
    for index in range(pixels):
        mean_a += _pixel_value(flat_a, index)
        mean_b += _pixel_value(flat_b, index)
    mean_a /= float(pixels)
    mean_b /= float(pixels)

    var_a = 0.0
    var_b = 0.0
    covariance = 0.0
    for index in range(pixels):
        da = _pixel_value(flat_a, index) - mean_a
        db = _pixel_value(flat_b, index) - mean_b
        var_a += da * da
        var_b += db * db
        covariance += da * db
    var_a /= float(pixels)
    var_b /= float(pixels)
    covariance /= float(pixels)

    c1 = 6.5025
    c2 = 58.5225
    return (
        (2.0 * mean_a * mean_b + c1)
        * (2.0 * covariance + c2)
    ) / (
        (mean_a * mean_a + mean_b * mean_b + c1)
        * (var_a + var_b + c2)
    )

def diff_fraction_flat(flat_a, flat_b, width, height, diff_threshold):
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    count = 0
    for index in range(pixels):
        if _abs(_pixel_value(flat_a, index) - _pixel_value(flat_b, index)) > diff_threshold:
            count += 1
    return float(count) / float(pixels)

def crop_region_similarity_flat(flat_a, flat_b, width, height, x0, y0, x1, y1):
    if width <= 0 or height <= 0:
        return 0.0
    left = x0
    top = y0
    right = x1
    bottom = y1
    if left < 0:
        left = 0
    if top < 0:
        top = 0
    if right >= width:
        right = width - 1
    if bottom >= height:
        bottom = height - 1
    if right < left or bottom < top:
        return 0.0
    total = 0.0
    count = 0
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            total += _abs(_pixel_value(flat_a, y * width + x) - _pixel_value(flat_b, y * width + x))
            count += 1
    if count <= 0:
        return 0.0
    return _clamp01(1.0 - (total / float(count)) / 255.0)

def duplicate_score_flat(flat_a, flat_b, width, height):
    ssim = _clamp01(ssim_global_flat(flat_a, flat_b, width, height))
    ncc = _clamp01((normalized_cross_correlation_flat(flat_a, flat_b, width, height) + 1.0) / 2.0)
    stable = 1.0 - diff_fraction_flat(flat_a, flat_b, width, height, 12.0)
    return _clamp01(0.55 * ssim + 0.25 * ncc + 0.20 * stable)
