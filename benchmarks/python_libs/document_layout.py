"""Python equivalent of mojo/engine/document_layout.mojo (auto-generated)."""
import math
import random as _rng

try:
    from document_vision import horizontal_projection
except Exception:
    pass
try:
    from document_vision import vertical_projection
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



def _is_foreground(mask_flat, index, fg_threshold):
    return _pixel_value(mask_flat, index) >= fg_threshold



def _normalized_min_count(min_count):
    return 1 if min_count < 1 else min_count



def _clamp01(value):
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value



def _abs(value):
    return -value if value < 0.0 else value



def _count_projection_bands(projection, min_count):
    if len(projection) == 0:
        return 0
    threshold = float(_normalized_min_count(min_count))
    bands = 0
    active = False
    for value in projection:
        if value >= threshold:
            if not active:
                bands += 1
                active = True
        else:
            active = False
    return bands



def text_line_boxes_flat(mask_flat, width, height, fg_threshold, min_row_ink):
    out = []
    if _pixel_count(width, height) <= 0:
        return out

    threshold = _normalized_min_count(min_row_ink)
    in_band = False
    band_y0 = 0
    band_y1 = 0
    band_min_x = width
    band_max_x = -1
    band_area = 0

    for y in range(height):
        row_area = 0
        row_min_x = width
        row_max_x = -1
        for x in range(width):
            if _is_foreground(mask_flat, y * width + x, fg_threshold):
                row_area += 1
                if x < row_min_x:
                    row_min_x = x
                if x > row_max_x:
                    row_max_x = x
        if row_area >= threshold:
            if not in_band:
                in_band = True
                band_y0 = y
                band_min_x = row_min_x
                band_max_x = row_max_x
                band_area = row_area
            else:
                if row_min_x < band_min_x:
                    band_min_x = row_min_x
                if row_max_x > band_max_x:
                    band_max_x = row_max_x
                band_area += row_area
            band_y1 = y
        elif in_band:
            out.append(band_min_x)
            out.append(band_y0)
            out.append(band_max_x)
            out.append(band_y1)
            out.append(band_area)
            in_band = False
    if in_band:
        out.append(band_min_x)
        out.append(band_y0)
        out.append(band_max_x)
        out.append(band_y1)
        out.append(band_area)
    return out



def line_count_flat(mask_flat, width, height, fg_threshold, min_row_ink):
    return len(text_line_boxes_flat(mask_flat, width, height, fg_threshold, min_row_ink)) // 5



def column_boxes_flat(mask_flat, width, height, fg_threshold, min_col_ink):
    out = []
    if _pixel_count(width, height) <= 0:
        return out

    threshold = _normalized_min_count(min_col_ink)
    in_band = False
    band_x0 = 0
    band_x1 = 0
    band_min_y = height
    band_max_y = -1
    band_area = 0

    for x in range(width):
        col_area = 0
        col_min_y = height
        col_max_y = -1
        for y in range(height):
            if _is_foreground(mask_flat, y * width + x, fg_threshold):
                col_area += 1
                if y < col_min_y:
                    col_min_y = y
                if y > col_max_y:
                    col_max_y = y
        if col_area >= threshold:
            if not in_band:
                in_band = True
                band_x0 = x
                band_min_y = col_min_y
                band_max_y = col_max_y
                band_area = col_area
            else:
                if col_min_y < band_min_y:
                    band_min_y = col_min_y
                if col_max_y > band_max_y:
                    band_max_y = col_max_y
                band_area += col_area
            band_x1 = x
        elif in_band:
            out.append(band_x0)
            out.append(band_min_y)
            out.append(band_x1)
            out.append(band_max_y)
            out.append(band_area)
            in_band = False
    if in_band:
        out.append(band_x0)
        out.append(band_min_y)
        out.append(band_x1)
        out.append(band_max_y)
        out.append(band_area)
    return out



def column_count_flat(mask_flat, width, height, fg_threshold, min_col_ink):
    return len(column_boxes_flat(mask_flat, width, height, fg_threshold, min_col_ink)) // 5



def text_density_grid_flat(mask_flat, width, height, fg_threshold, grid_rows, grid_cols):
    out = []
    if _pixel_count(width, height) <= 0 or grid_rows <= 0 or grid_cols <= 0:
        return out

    for row in range(grid_rows):
        y0 = (row * height) // grid_rows
        y1 = ((row + 1) * height) // grid_rows - 1
        if y1 < y0:
            y1 = y0
        for col in range(grid_cols):
            x0 = (col * width) // grid_cols
            x1 = ((col + 1) * width) // grid_cols - 1
            if x1 < x0:
                x1 = x0
            count = 0
            cell_area = (y1 - y0 + 1) * (x1 - x0 + 1)
            if cell_area <= 0:
                out.append(0.0)
                continue
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    if _is_foreground(mask_flat, y * width + x, fg_threshold):
                        count += 1
            out.append(float(count) / float(cell_area))
    return out



def multi_column_score_flat(mask_flat, width, height, fg_threshold):
    if width < 3 or height <= 0:
        return 0.0

    projection = vertical_projection(mask_flat, width, height, fg_threshold)
    prefix = []
    running = 0.0
    for value in projection:
        running += value
        prefix.append(running)
    if running <= 0.0:
        return 0.0

    best = 0.0
    for split in range(1, width - 1):
        left_mass = prefix[split - 1]
        right_mass = running - prefix[split]
        if left_mass <= 0.0 or right_mass <= 0.0:
            continue
        left_density = left_mass / float(split * height)
        right_density = right_mass / float((width - split - 1) * height)
        max_side = left_density if left_density > right_density else right_density
        if max_side <= 0.0:
            continue
        valley_density = projection[split] / float(height)
        balance = 1.0 - (_abs(left_density - right_density) / max_side)
        valley_separation = 1.0 - (valley_density / max_side)
        side_strength = left_density if left_density < right_density else right_density
        strength = side_strength / 0.35
        score = (
            _clamp01(balance)
            * _clamp01(valley_separation)
            * _clamp01(strength)
        )
        if score > best:
            best = score
    return _clamp01(best)



def table_like_score_flat(mask_flat, width, height, fg_threshold):
    if _pixel_count(width, height) <= 0:
        return 0.0

    min_row_ink = width // 5
    if min_row_ink < 1:
        min_row_ink = 1
    min_col_ink = height // 5
    if min_col_ink < 1:
        min_col_ink = 1

    row_bands = _count_projection_bands(
        horizontal_projection(mask_flat, width, height, fg_threshold),
        min_row_ink,
    )
    col_bands = _count_projection_bands(
        vertical_projection(mask_flat, width, height, fg_threshold),
        min_col_ink,
    )

    densities = text_density_grid_flat(mask_flat, width, height, fg_threshold, 4, 4)
    active_cells = 0
    for density in densities:
        if density >= 0.12:
            active_cells += 1
    active_ratio = 0.0
    if len(densities) > 0:
        active_ratio = float(active_cells) / float(len(densities))

    row_strength = _clamp01(float(row_bands - 1) / 2.0)
    col_strength = _clamp01(float(col_bands - 1) / 2.0)
    structure = 0.5 * row_strength + 0.5 * col_strength
    if row_bands < 2 or col_bands < 2:
        structure *= 0.35
    return _clamp01(0.8 * structure + 0.2 * active_ratio)

