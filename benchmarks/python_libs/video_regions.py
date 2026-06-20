"""Python equivalent of mojo/engine/video_regions.mojo (auto-generated)."""
import math
import random as _rng

try:
    from image_regions import connected_component_boxes_flat
except Exception:
    pass
try:
    from video_ops import frame_count_from_flat
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

def _frame_stride(width, height, channels):
    if width <= 0 or height <= 0 or channels <= 0:
        return 0
    return width * height * channels



def _pixel_mean(flat_frames, base, channels):
    if channels <= 0:
        return 0.0
    total = 0.0
    for c in range(channels):
        total += flat_frames[base + c]
    return total / float(channels)



def _abs(value):
    return -value if value < 0.0 else value



def _foreground_count(mask_flat, fg_threshold):
    count = 0
    for value in mask_flat:
        if value >= fg_threshold:
            count += 1
    return count



def _mask_bbox(mask_flat, width, height, fg_threshold):
    out = []
    if width <= 0 or height <= 0:
        return out
    min_x = width
    min_y = height
    max_x = -1
    max_y = -1
    area = 0
    for index in range(len(mask_flat)):
        if mask_flat[index] < fg_threshold:
            continue
        area += 1
        x = index % width
        y = index // width
        if x < min_x:
            min_x = x
        if y < min_y:
            min_y = y
        if x > max_x:
            max_x = x
        if y > max_y:
            max_y = y
    if area <= 0:
        return out
    out.append(min_x)
    out.append(min_y)
    out.append(max_x)
    out.append(max_y)
    out.append(area)
    return out



def _diff_mask_between_frames(flat_frames, width, height, channels, frame_a_index, frame_b_index, diff_threshold):
    out = []
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    if (
        stride <= 0
        or frame_a_index < 0
        or frame_b_index < 0
        or frame_a_index >= frames
        or frame_b_index >= frames
    ):
        return out

    pixels = width * height
    base_a = frame_a_index * stride
    base_b = frame_b_index * stride
    for pixel_index in range(pixels):
        mean_a = _pixel_mean(flat_frames, base_a + pixel_index * channels, channels)
        mean_b = _pixel_mean(flat_frames, base_b + pixel_index * channels, channels)
        out.append(255.0 if _abs(mean_a - mean_b) >= diff_threshold else 0.0)
    return out



def frame_diff_mask_flat(flat_frames, width, height, channels, frame_a_index, frame_b_index, diff_threshold):
    return _diff_mask_between_frames(
        flat_frames,
        width,
        height,
        channels,
        frame_a_index,
        frame_b_index,
        diff_threshold,
    )



def motion_boxes_between_frames(flat_frames, width, height, channels, frame_a_index, frame_b_index, diff_threshold, max_regions):
    if max_regions <= 0:
        empty = []
        return empty
    return connected_component_boxes_flat(
        _diff_mask_between_frames(
            flat_frames,
            width,
            height,
            channels,
            frame_a_index,
            frame_b_index,
            diff_threshold,
        ),
        width,
        height,
        128.0,
        max_regions,
    )



def largest_motion_box_between_frames(flat_frames, width, height, channels, frame_a_index, frame_b_index, diff_threshold):
    boxes = motion_boxes_between_frames(
        flat_frames,
        width,
        height,
        channels,
        frame_a_index,
        frame_b_index,
        diff_threshold,
        1,
    )
    out = []
    for value in boxes:
        out.append(value)
    return out



def temporal_motion_area_series(flat_frames, width, height, channels, diff_threshold):
    out = []
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    pixels = width * height
    if frames < 2 or pixels <= 0:
        return out
    for frame_index in range(1, frames):
        mask = _diff_mask_between_frames(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
            diff_threshold,
        )
        out.append(float(_foreground_count(mask, 128.0)) / float(pixels))
    return out



def peak_motion_box_flat(flat_frames, width, height, channels, diff_threshold):
    out = []
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames < 2:
        return out

    best_count = -1
    for frame_index in range(1, frames):
        mask = _diff_mask_between_frames(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
            diff_threshold,
        )
        count = _foreground_count(mask, 128.0)
        if count > best_count:
            best_count = count
            boxes = connected_component_boxes_flat(mask, width, height, 128.0, 1)
            out = []
            for value in boxes:
                out.append(value)
    return out



def temporal_union_motion_box_flat(flat_frames, width, height, channels, diff_threshold):
    out = []
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    pixels = width * height
    if frames < 2 or pixels <= 0:
        return out

    union_mask = []
    for _ in range(pixels):
        union_mask.append(0.0)
    for frame_index in range(1, frames):
        mask = _diff_mask_between_frames(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
            diff_threshold,
        )
        for index in range(pixels):
            if mask[index] >= 128.0:
                union_mask[index] = 255.0
    return _mask_bbox(union_mask, width, height, 128.0)



def motion_coverage_ratio_flat(flat_frames, width, height, channels, diff_threshold):
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    pixels = width * height
    if frames < 2 or pixels <= 0:
        return 0.0

    union_mask = []
    for _ in range(pixels):
        union_mask.append(0.0)
    for frame_index in range(1, frames):
        mask = _diff_mask_between_frames(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
            diff_threshold,
        )
        for index in range(pixels):
            if mask[index] >= 128.0:
                union_mask[index] = 255.0
    return float(_foreground_count(union_mask, 128.0)) / float(pixels)

