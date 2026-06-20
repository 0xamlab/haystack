"""Python equivalent of mojo/engine/document_vision.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import atan2
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass
try:
    from image_quality import quality_score
except Exception:
    pass
try:
    from image_resize import box_sum
except Exception:
    pass
try:
    from image_resize import integral_image
except Exception:
    pass
try:
    from image_resize import reshape_to_grid
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



def _clamp255(v):
    if v < 0.0:
        return 0.0
    if v > 255.0:
        return 255.0
    return v



def _clamp01(v):
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v



def _abs(v):
    return -v if v < 0.0 else v



def _foreground_mask_value(value, threshold):
    return 255.0 if value <= threshold else 0.0



def _projection_coefficient_of_variation(values):
    if len(values) == 0:
        return 0.0
    mean = 0.0
    for value in values:
        mean += value
    mean /= float(len(values))
    if mean <= 0.0:
        return 0.0
    variance = 0.0
    for value in values:
        diff = value - mean
        variance += diff * diff
    variance /= float(len(values))
    return math.sqrt(variance) / mean



def otsu_threshold_flat(flat, width, height):
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0

    hist = []
    for _ in range(256):
        hist.append(0)
    for index in range(pixels):
        bucket = int(_clamp255(_pixel_value(flat, index)))
        hist[bucket] += 1

    total_sum = 0.0
    for bucket in range(256):
        total_sum += float(bucket * hist[bucket])

    weight_background = 0
    sum_background = 0.0
    best_threshold = 0
    best_score = -1.0
    for threshold in range(256):
        weight_background += hist[threshold]
        if weight_background == 0:
            continue
        weight_foreground = pixels - weight_background
        if weight_foreground == 0:
            break
        sum_background += float(threshold * hist[threshold])
        mean_background = sum_background / float(weight_background)
        mean_foreground = (total_sum - sum_background) / float(weight_foreground)
        diff = mean_background - mean_foreground
        score = (
            float(weight_background)
            * float(weight_foreground)
            * diff
            * diff
        )
        if score > best_score:
            best_score = score
            best_threshold = threshold
    return float(best_threshold)



def binarize_otsu_flat(flat, width, height):
    out = []
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out
    threshold = otsu_threshold_flat(flat, width, height)
    for index in range(pixels):
        out.append(_foreground_mask_value(_pixel_value(flat, index), threshold))
    return out



def adaptive_mean_binarize_flat(flat, width, height, window_radius, bias):
    out = []
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out
    radius = window_radius
    if radius < 0:
        radius = 0
    grid = reshape_to_grid(flat, width, height)
    sat = integral_image(grid)
    for y in range(height):
        y0 = y - radius
        if y0 < 0:
            y0 = 0
        y1 = y + radius
        if y1 >= height:
            y1 = height - 1
        for x in range(width):
            x0 = x - radius
            if x0 < 0:
                x0 = 0
            x1 = x + radius
            if x1 >= width:
                x1 = width - 1
            count = (y1 - y0 + 1) * (x1 - x0 + 1)
            mean = box_sum(sat, y0, x0, y1, x1) / float(count)
            out.append(_foreground_mask_value(grid[y][x], mean - bias))
    return out



def horizontal_projection(mask_flat, width, height, fg_threshold):
    out = []
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out
    for y in range(height):
        total = 0.0
        for x in range(width):
            if _pixel_value(mask_flat, y * width + x) >= fg_threshold:
                total += 1.0
        out.append(total)
    return out



def vertical_projection(mask_flat, width, height, fg_threshold):
    out = []
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out
    for x in range(width):
        total = 0.0
        for y in range(height):
            if _pixel_value(mask_flat, y * width + x) >= fg_threshold:
                total += 1.0
        out.append(total)
    return out



def mask_content_bbox_flat(mask_flat, width, height, fg_threshold):
    out = []
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out
    min_x = width
    min_y = height
    max_x = -1
    max_y = -1
    area = 0
    for y in range(height):
        for x in range(width):
            if _pixel_value(mask_flat, y * width + x) >= fg_threshold:
                area += 1
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    if area == 0:
        return out
    out.append(min_x)
    out.append(min_y)
    out.append(max_x)
    out.append(max_y)
    out.append(area)
    return out



def skew_angle_estimate_flat(mask_flat, width, height, fg_threshold):
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    sum_y = 0.0
    sum_center = 0.0
    sum_yy = 0.0
    sum_y_center = 0.0
    row_count = 0
    for y in range(height):
        left = width
        right = -1
        count = 0
        for x in range(width):
            if _pixel_value(mask_flat, y * width + x) >= fg_threshold:
                count += 1
                if x < left:
                    left = x
                if x > right:
                    right = x
        if count == 0:
            continue
        center = (float(left) + float(right)) / 2.0
        yf = float(y)
        sum_y += yf
        sum_center += center
        sum_yy += yf * yf
        sum_y_center += yf * center
        row_count += 1
    if row_count < 2:
        return 0.0
    n = float(row_count)
    denom = n * sum_yy - sum_y * sum_y
    if denom == 0.0:
        return 0.0
    slope = (n * sum_y_center - sum_y * sum_center) / denom
    return math.atan2(slope, 1.0) * 180.0 / 3.141592653589793



def horizontal_text_score_flat(mask_flat, width, height, fg_threshold):
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    hp = horizontal_projection(mask_flat, width, height, fg_threshold)
    vp = vertical_projection(mask_flat, width, height, fg_threshold)
    total_ink = 0.0
    for value in hp:
        total_ink += value
    if total_ink <= 0.0:
        return 0.0
    row_cv = _projection_coefficient_of_variation(hp)
    col_cv = _projection_coefficient_of_variation(vp)
    if row_cv <= 0.0 and col_cv <= 0.0:
        return 0.5
    return _clamp01(row_cv / (row_cv + col_cv))

def document_scan_quality_flat(flat, width, height):
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    grid = reshape_to_grid(flat, width, height)
    base_quality = quality_score(grid)
    mask = binarize_otsu_flat(flat, width, height)
    bbox = mask_content_bbox_flat(mask, width, height, 128.0)
    if len(bbox) < 5:
        return 0.0
    area_ratio = float(bbox[4]) / float(pixels)
    coverage_score = _clamp01(area_ratio / 0.18)
    if area_ratio > 0.45:
        coverage_score = _clamp01((0.95 - area_ratio) / 0.50)
    skew_score = 1.0 - _clamp01(_abs(skew_angle_estimate_flat(mask, width, height, 128.0)) / 15.0)
    text_score = horizontal_text_score_flat(mask, width, height, 128.0)
    return _clamp01(
        0.45 * base_quality
        + 0.20 * coverage_score
        + 0.20 * skew_score
        + 0.15 * text_score
    )
