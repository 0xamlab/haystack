"""Python equivalent of mojo/engine/video_quality.mojo (auto-generated)."""
import math
import random as _rng

try:
    from image_quality import quality_score
except Exception:
    pass
try:
    from image_resize import reshape_to_grid
except Exception:
    pass
try:
    from video_ops import frame_count_from_flat
except Exception:
    pass
try:
    from video_ops import frame_mean_intensities
except Exception:
    pass
try:
    from video_ops import sample_frame_indices
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

def _clamp01(x):
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x



def _frame_stride(width, height, channels):
    if width <= 0 or height <= 0 or channels <= 0:
        return 0
    return width * height * channels



def _extract_frame_gray_flat(flat_frames, width, height, channels, frame_index):
    out = []
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    if frame_index < 0 or frame_index >= frames or stride <= 0:
        return out
    base = frame_index * stride
    pixels = width * height
    for pixel_index in range(pixels):
        pixel_base = base + pixel_index * channels
        total = 0.0
        for c in range(channels):
            total += flat_frames[pixel_base + c]
        out.append(total / float(channels))
    return out



def frame_quality_series(flat_frames, width, height, channels, sample_frames):
    picks = sample_frame_indices(flat_frames, width, height, channels, sample_frames)
    out = []
    for pick in picks:
        out.append(
            quality_score(
                reshape_to_grid(
                    _extract_frame_gray_flat(flat_frames, width, height, channels, pick),
                    width,
                    height,
                )
            )
        )
    return out



def average_frame_quality(flat_frames, width, height, channels, sample_frames):
    qualities = frame_quality_series(flat_frames, width, height, channels, sample_frames)
    if len(qualities) == 0:
        return 0.0
    total = 0.0
    for quality in qualities:
        total += quality
    return total / float(len(qualities))



def brightness_flicker_score(flat_frames, width, height, channels):
    means = frame_mean_intensities(flat_frames, width, height, channels)
    if len(means) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(means)):
        diff = means[i] - means[i - 1]
        if diff < 0.0:
            diff = -diff
        total += diff
    return total / float(len(means) - 1)



def temporal_stability_score(flat_frames, width, height, channels):
    flicker = brightness_flicker_score(flat_frames, width, height, channels)
    return _clamp01(1.0 / (1.0 + flicker / 48.0))



def video_quality_score(flat_frames, width, height, channels, sample_frames):
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return 0.0
    frame_quality = average_frame_quality(flat_frames, width, height, channels, sample_frames)
    stability = temporal_stability_score(flat_frames, width, height, channels)
    coverage = 1.0 if frames > 1 else 0.7
    return _clamp01(0.7 * frame_quality + 0.2 * stability + 0.1 * coverage)



def is_usable_video(flat_frames, width, height, channels, sample_frames, min_quality):
    return (
        video_quality_score(flat_frames, width, height, channels, sample_frames)
        >= min_quality
    )
