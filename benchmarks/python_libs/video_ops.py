"""Python equivalent of mojo/engine/video_ops.mojo (auto-generated)."""
import math
import random as _rng

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



def _frame_count_internal(flat_frames, width, height, channels):
    stride = _frame_stride(width, height, channels)
    if stride <= 0:
        return 0
    return len(flat_frames) // stride



def _pixel_mean(flat_frames, base, channels):
    if channels <= 0:
        return 0.0
    total = 0.0
    for c in range(channels):
        total += flat_frames[base + c]
    return total / float(channels)



def frame_count_from_flat(flat_frames, width, height, channels):
    return _frame_count_internal(flat_frames, width, height, channels)



def frame_mean_intensity(flat_frames, width, height, channels, frame_index):
    frames = _frame_count_internal(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    if frame_index < 0 or frame_index >= frames or stride <= 0:
        return 0.0
    pixels = width * height
    if pixels <= 0:
        return 0.0
    frame_base = frame_index * stride
    total = 0.0
    for pixel_index in range(pixels):
        total += _pixel_mean(flat_frames, frame_base + pixel_index * channels, channels)
    return total / float(pixels)



def frame_mean_intensities(flat_frames, width, height, channels):
    out = []
    frames = _frame_count_internal(flat_frames, width, height, channels)
    for frame_index in range(frames):
        out.append(frame_mean_intensity(flat_frames, width, height, channels, frame_index))
    return out



def frame_mean_abs_diff(flat_frames, width, height, channels, frame_a_index, frame_b_index):
    frames = _frame_count_internal(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    if (
        frame_a_index < 0
        or frame_b_index < 0
        or frame_a_index >= frames
        or frame_b_index >= frames
        or stride <= 0
    ):
        return 0.0
    pixels = width * height
    if pixels <= 0:
        return 0.0
    base_a = frame_a_index * stride
    base_b = frame_b_index * stride
    total = 0.0
    for pixel_index in range(pixels):
        mean_a = _pixel_mean(flat_frames, base_a + pixel_index * channels, channels)
        mean_b = _pixel_mean(flat_frames, base_b + pixel_index * channels, channels)
        diff = mean_a - mean_b
        if diff < 0.0:
            diff = -diff
        total += diff
    return total / float(pixels)



def temporal_mean_abs_diff(flat_frames, width, height, channels):
    frames = _frame_count_internal(flat_frames, width, height, channels)
    if frames < 2:
        return 0.0
    total = 0.0
    for frame_index in range(1, frames):
        total += frame_mean_abs_diff(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
        )
    return total / float(frames - 1)



def temporal_max_abs_diff(flat_frames, width, height, channels):
    frames = _frame_count_internal(flat_frames, width, height, channels)
    if frames < 2:
        return 0.0
    best = 0.0
    for frame_index in range(1, frames):
        diff = frame_mean_abs_diff(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
        )
        if diff > best:
            best = diff
    return best



def freeze_frame_ratio(flat_frames, width, height, channels, diff_threshold):
    frames = _frame_count_internal(flat_frames, width, height, channels)
    if frames < 2:
        return 1.0
    frozen = 0
    for frame_index in range(1, frames):
        if (
            frame_mean_abs_diff(
                flat_frames,
                width,
                height,
                channels,
                frame_index - 1,
                frame_index,
            )
            <= diff_threshold
        ):
            frozen += 1
    return float(frozen) / float(frames - 1)



def sample_frame_indices(flat_frames, width, height, channels, target_frames):
    out = []
    frames = _frame_count_internal(flat_frames, width, height, channels)
    if frames <= 0 or target_frames <= 0:
        return out
    if target_frames >= frames or target_frames == 1:
        if target_frames == 1:
            out.append(0)
            return out
        for frame_index in range(frames):
            out.append(frame_index)
        return out

    last = -1
    for pick in range(target_frames):
        idx = (pick * (frames - 1)) // (target_frames - 1)
        if idx <= last:
            idx = last + 1
        if idx >= frames:
            idx = frames - 1
        out.append(idx)
        last = idx
    return out
