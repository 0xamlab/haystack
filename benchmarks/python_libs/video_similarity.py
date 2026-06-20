"""Python equivalent of mojo/engine/video_similarity.mojo (auto-generated)."""
import math
import random as _rng

try:
    from image_similarity import duplicate_score_flat
except Exception:
    pass
try:
    from perceptual_hash import dhash_flat
except Exception:
    pass
try:
    from perceptual_hash import hamming_distance
except Exception:
    pass
try:
    from video_features import scene_change_scores
except Exception:
    pass
try:
    from video_ops import frame_count_from_flat
except Exception:
    pass
try:
    from video_ops import frame_mean_intensity
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

def _abs(v):
    return -v if v < 0.0 else v



def _clamp01(v):
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v



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



def _extract_frame_gray_flat(flat_frames, width, height, channels, frame_index):
    out = []
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    if frame_index < 0 or frame_index >= frames or stride <= 0:
        return out
    pixels = width * height
    frame_base = frame_index * stride
    for pixel_index in range(pixels):
        out.append(_pixel_mean(flat_frames, frame_base + pixel_index * channels, channels))
    return out



def _paired_frame_count(flat_a, flat_b, width, height, channels):
    frames_a = frame_count_from_flat(flat_a, width, height, channels)
    frames_b = frame_count_from_flat(flat_b, width, height, channels)
    return frames_a if frames_a <= frames_b else frames_b



def _frame_count_gap_ratio(frames_a, frames_b):
    if frames_a <= 0 and frames_b <= 0:
        return 0.0
    max_frames = frames_a if frames_a >= frames_b else frames_b
    gap = frames_a - frames_b
    if gap < 0:
        gap = -gap
    return float(gap) / float(max_frames)



def frame_duplicate_scores(flat_a, flat_b, width, height, channels):
    out = []
    frames = _paired_frame_count(flat_a, flat_b, width, height, channels)
    if frames <= 0:
        return out
    for frame_index in range(frames):
        frame_a = _extract_frame_gray_flat(flat_a, width, height, channels, frame_index)
        frame_b = _extract_frame_gray_flat(flat_b, width, height, channels, frame_index)
        out.append(duplicate_score_flat(frame_a, frame_b, width, height))
    return out



def average_frame_duplicate_score(flat_a, flat_b, width, height, channels):
    frames_a = frame_count_from_flat(flat_a, width, height, channels)
    frames_b = frame_count_from_flat(flat_b, width, height, channels)
    if frames_a <= 0 and frames_b <= 0:
        return 1.0
    if frames_a <= 0 or frames_b <= 0:
        return 0.0
    scores = frame_duplicate_scores(flat_a, flat_b, width, height, channels)
    if len(scores) == 0:
        return 0.0
    total = 0.0
    for score in scores:
        total += score
    return total / float(len(scores))



def frame_hash_hamming_series(flat_a, flat_b, width, height, channels):
    out = []
    frames = _paired_frame_count(flat_a, flat_b, width, height, channels)
    if frames <= 0:
        return out
    for frame_index in range(frames):
        frame_a = _extract_frame_gray_flat(flat_a, width, height, channels, frame_index)
        frame_b = _extract_frame_gray_flat(flat_b, width, height, channels, frame_index)
        out.append(hamming_distance(dhash_flat(frame_a, width, height), dhash_flat(frame_b, width, height)))
    return out



def average_frame_hash_hamming(flat_a, flat_b, width, height, channels):
    frames_a = frame_count_from_flat(flat_a, width, height, channels)
    frames_b = frame_count_from_flat(flat_b, width, height, channels)
    if frames_a <= 0 and frames_b <= 0:
        return 0.0
    if frames_a <= 0 or frames_b <= 0:
        return 64.0
    distances = frame_hash_hamming_series(flat_a, flat_b, width, height, channels)
    if len(distances) == 0:
        return 64.0
    total = 0.0
    for value in distances:
        total += float(value)
    return total / float(len(distances))



def temporal_signature_distance(flat_a, flat_b, width, height, channels):
    frames_a = frame_count_from_flat(flat_a, width, height, channels)
    frames_b = frame_count_from_flat(flat_b, width, height, channels)
    if frames_a <= 0 and frames_b <= 0:
        return 0.0
    if frames_a <= 0 or frames_b <= 0:
        return 1.0

    paired_frames = frames_a if frames_a <= frames_b else frames_b
    intensity_gap = 0.0
    for frame_index in range(paired_frames):
        intensity_gap += _abs(
            frame_mean_intensity(flat_a, width, height, channels, frame_index)
            - frame_mean_intensity(flat_b, width, height, channels, frame_index)
        ) / 255.0
    intensity_gap /= float(paired_frames)

    motion_a = scene_change_scores(flat_a, width, height, channels)
    motion_b = scene_change_scores(flat_b, width, height, channels)
    paired_transitions = len(motion_a)
    if len(motion_b) < paired_transitions:
        paired_transitions = len(motion_b)

    motion_gap = 0.0
    if paired_transitions > 0:
        for index in range(paired_transitions):
            motion_gap += _abs(motion_a[index] - motion_b[index])
        motion_gap /= float(paired_transitions)

    count_gap = _frame_count_gap_ratio(frames_a, frames_b)
    return _clamp01(0.55 * intensity_gap + 0.30 * motion_gap + 0.15 * count_gap)



def clip_duplicate_score_flat(flat_a, flat_b, width, height, channels):
    frames_a = frame_count_from_flat(flat_a, width, height, channels)
    frames_b = frame_count_from_flat(flat_b, width, height, channels)
    if frames_a <= 0 and frames_b <= 0:
        return 1.0
    if frames_a <= 0 or frames_b <= 0:
        return 0.0

    frame_score = average_frame_duplicate_score(flat_a, flat_b, width, height, channels)
    hash_similarity = _clamp01(
        1.0 - average_frame_hash_hamming(flat_a, flat_b, width, height, channels) / 64.0
    )
    temporal_similarity = 1.0 - temporal_signature_distance(flat_a, flat_b, width, height, channels)
    return _clamp01(0.55 * frame_score + 0.25 * hash_similarity + 0.20 * temporal_similarity)



def is_duplicate_clip_flat(flat_a, flat_b, width, height, channels, min_score):
    return clip_duplicate_score_flat(flat_a, flat_b, width, height, channels) >= min_score
