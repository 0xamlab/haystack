"""Python equivalent of mojo/engine/video_accessibility.mojo (auto-generated)."""
import math
import random as _rng

try:
    from color_check import wcag_aa_required_contrast
except Exception:
    pass
try:
    from color_science import contrast_ratio
except Exception:
    pass
try:
    from color_science import rgb_to_luminance
except Exception:
    pass
try:
    from video_ops import frame_count_from_flat
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

def _clamp_rgb255(v):
    if v < 0.0:
        return 0.0
    if v > 255.0:
        return 255.0
    return v



def _frame_stride(width, height, channels):
    if width <= 0 or height <= 0 or channels <= 0:
        return 0
    return width * height * channels



def _pixel_luminance(flat_frames, base, channels):
    r = _clamp_rgb255(flat_frames[base]) / 255.0
    g = r
    b = r
    if channels >= 2:
        g = _clamp_rgb255(flat_frames[base + 1]) / 255.0
        b = g
    if channels >= 3:
        b = _clamp_rgb255(flat_frames[base + 2]) / 255.0
    return rgb_to_luminance(r, g, b)



def _best_contrast_from_minima(min_black, min_white):
    return min_black if min_black >= min_white else min_white



def _best_text_color_from_minima(min_black, min_white):
    return "#000000" if min_black >= min_white else "#FFFFFF"



def _region_text_contrast_minima(flat_frames, width, height, channels, frame_index, row_start, row_end):
    out = []
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    if frame_index < 0 or frame_index >= frames or stride <= 0:
        out.append(0.0)
        out.append(0.0)
        return out

    effective_row_start = row_start
    if effective_row_start < 0:
        effective_row_start = 0
    effective_row_end = row_end
    if effective_row_end > height:
        effective_row_end = height
    if effective_row_start >= effective_row_end or width <= 0:
        out.append(0.0)
        out.append(0.0)
        return out

    frame_base = frame_index * stride
    min_black = float(1e9)
    min_white = float(1e9)
    valid_pixels = 0
    for y in range(effective_row_start, effective_row_end):
        row_base = frame_base + y * width * channels
        for x in range(width):
            luminance = _pixel_luminance(flat_frames, row_base + x * channels, channels)
            black_contrast = contrast_ratio(0.0, luminance)
            white_contrast = contrast_ratio(1.0, luminance)
            if black_contrast < min_black:
                min_black = black_contrast
            if white_contrast < min_white:
                min_white = white_contrast
            valid_pixels += 1
    if valid_pixels == 0:
        out.append(0.0)
        out.append(0.0)
        return out

    out.append(min_black)
    out.append(min_white)
    return out



def _frame_preferred_contrast(flat_frames, width, height, channels, frame_index):
    minima = _region_text_contrast_minima(
        flat_frames,
        width,
        height,
        channels,
        frame_index,
        0,
        height,
    )
    return _best_contrast_from_minima(minima[0], minima[1])



def _frame_preferred_text_color(flat_frames, width, height, channels, frame_index):
    minima = _region_text_contrast_minima(
        flat_frames,
        width,
        height,
        channels,
        frame_index,
        0,
        height,
    )
    return _best_text_color_from_minima(minima[0], minima[1])



def _sampled_frame_indices(flat_frames, width, height, channels, sample_frames_n):
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return []
    target = sample_frames_n
    if target <= 0 or target > frames:
        target = frames
    return sample_frame_indices(flat_frames, width, height, channels, target)



def _band_row_start(height, band_rows):
    if height <= 0 or band_rows <= 0:
        return -1
    rows = band_rows
    if rows > height:
        rows = height
    return height - rows



def frame_min_preferred_text_contrast_for_video(flat_frames, width, height, channels, frame_index):
    return _frame_preferred_contrast(flat_frames, width, height, channels, frame_index)



def frame_preferred_text_color_for_video(flat_frames, width, height, channels, frame_index):
    return _frame_preferred_text_color(flat_frames, width, height, channels, frame_index)



def sampled_video_min_text_contrast(flat_frames, width, height, channels, sample_frames_n):
    picks = _sampled_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if len(picks) == 0:
        return 0.0
    best_min = float(1e9)
    for pick_index in range(len(picks)):
        frame_contrast = _frame_preferred_contrast(
            flat_frames,
            width,
            height,
            channels,
            picks[pick_index],
        )
        if frame_contrast < best_min:
            best_min = frame_contrast
    return best_min



def sampled_video_wcag_safe_ratio(flat_frames, width, height, channels, sample_frames_n, font_size_pt, is_bold):
    picks = _sampled_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if len(picks) == 0:
        return 0.0
    threshold = wcag_aa_required_contrast(font_size_pt, is_bold)
    safe = 0
    for pick_index in range(len(picks)):
        if (
            _frame_preferred_contrast(
                flat_frames,
                width,
                height,
                channels,
                picks[pick_index],
            )
            >= threshold
        ):
            safe += 1
    return float(safe) / float(len(picks))



def needs_text_backplate_for_video(flat_frames, width, height, channels, sample_frames_n, font_size_pt, is_bold):
    return sampled_video_wcag_safe_ratio(
        flat_frames,
        width,
        height,
        channels,
        sample_frames_n,
        font_size_pt,
        is_bold,
    ) < 1.0



def subtitle_band_min_preferred_text_contrast_for_video(flat_frames, width, height, channels, sample_frames_n, band_rows):
    row_start = _band_row_start(height, band_rows)
    if row_start < 0:
        return 0.0
    picks = _sampled_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if len(picks) == 0:
        return 0.0
    min_black = float(1e9)
    min_white = float(1e9)
    for pick_index in range(len(picks)):
        minima = _region_text_contrast_minima(
            flat_frames,
            width,
            height,
            channels,
            picks[pick_index],
            row_start,
            height,
        )
        if minima[0] < min_black:
            min_black = minima[0]
        if minima[1] < min_white:
            min_white = minima[1]
    return _best_contrast_from_minima(min_black, min_white)



def subtitle_band_preferred_text_color_for_video(flat_frames, width, height, channels, sample_frames_n, band_rows):
    row_start = _band_row_start(height, band_rows)
    if row_start < 0:
        return "#000000"
    picks = _sampled_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if len(picks) == 0:
        return "#000000"
    min_black = float(1e9)
    min_white = float(1e9)
    for pick_index in range(len(picks)):
        minima = _region_text_contrast_minima(
            flat_frames,
            width,
            height,
            channels,
            picks[pick_index],
            row_start,
            height,
        )
        if minima[0] < min_black:
            min_black = minima[0]
        if minima[1] < min_white:
            min_white = minima[1]
    return _best_text_color_from_minima(min_black, min_white)



def sampled_subtitle_band_wcag_safe_ratio(flat_frames, width, height, channels, sample_frames_n, band_rows, font_size_pt, is_bold):
    row_start = _band_row_start(height, band_rows)
    if row_start < 0:
        return 0.0
    picks = _sampled_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if len(picks) == 0:
        return 0.0
    threshold = wcag_aa_required_contrast(font_size_pt, is_bold)
    safe = 0
    for pick_index in range(len(picks)):
        minima = _region_text_contrast_minima(
            flat_frames,
            width,
            height,
            channels,
            picks[pick_index],
            row_start,
            height,
        )
        if _best_contrast_from_minima(minima[0], minima[1]) >= threshold:
            safe += 1
    return float(safe) / float(len(picks))



def subtitle_band_needs_backplate_for_video(flat_frames, width, height, channels, sample_frames_n, band_rows, font_size_pt, is_bold):
    return sampled_subtitle_band_wcag_safe_ratio(
        flat_frames,
        width,
        height,
        channels,
        sample_frames_n,
        band_rows,
        font_size_pt,
        is_bold,
    ) < 1.0
