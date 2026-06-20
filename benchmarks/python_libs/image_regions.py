"""Python equivalent of mojo/engine/image_regions.mojo (auto-generated)."""
import math
import random as _rng

try:
    from document_vision import binarize_otsu_flat
except Exception:
    pass
try:
    from image_features import most_salient_cell
except Exception:
    pass
try:
    from image_features import saliency_grid
except Exception:
    pass
try:
    from image_morphology import connected_components_4_flat
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



def foreground_mask_otsu_flat(flat, width, height):
    return binarize_otsu_flat(flat, width, height)



def connected_component_boxes_flat(mask_flat, width, height, fg_threshold, max_regions):
    out = []
    pixels = _pixel_count(width, height)
    if pixels <= 0 or max_regions <= 0:
        return out

    labels = connected_components_4_flat(mask_flat, width, height, fg_threshold)
    max_label = 0
    for label in labels:
        if label > max_label:
            max_label = label
    if max_label <= 0:
        return out

    min_x = []
    min_y = []
    max_x = []
    max_y = []
    area = []
    for _ in range(max_label + 1):
        min_x.append(width)
        min_y.append(height)
        max_x.append(-1)
        max_y.append(-1)
        area.append(0)
    for index in range(len(labels)):
        label = labels[index]
        if label <= 0:
            continue
        x = index % width
        y = index // width
        area[label] += 1
        if x < min_x[label]:
            min_x[label] = x
        if y < min_y[label]:
            min_y[label] = y
        if x > max_x[label]:
            max_x[label] = x
        if y > max_y[label]:
            max_y[label] = y
    order = []
    for label in range(1, max_label + 1):
        if area[label] > 0:
            order.append(label)
    for i in range(1, len(order)):
        key = order[i]
        j = i - 1
        while j >= 0 and area[order[j]] < area[key]:
            order[j + 1] = order[j]
            j -= 1
        order[j + 1] = key
    limit = max_regions
    if limit > len(order):
        limit = len(order)
    for i in range(limit):
        label = order[i]
        out.append(min_x[label])
        out.append(min_y[label])
        out.append(max_x[label])
        out.append(max_y[label])
        out.append(area[label])
    return out

def largest_foreground_box_flat(flat, width, height):
    mask = foreground_mask_otsu_flat(flat, width, height)
    boxes = connected_component_boxes_flat(mask, width, height, 128.0, 1)
    out = []
    for i in range(len(boxes)):
        out.append(boxes[i])
    return out

def saliency_box_flat(flat, width, height, grid_rows, grid_cols):
    out = []
    if width <= 0 or height <= 0 or grid_rows <= 0 or grid_cols <= 0:
        return out
    sal = saliency_grid(reshape_to_grid(flat, width, height), grid_rows, grid_cols)
    index = most_salient_cell(sal)
    if index < 0:
        return out
    row = index // grid_cols
    col = index % grid_cols
    x0 = (col * width) // grid_cols
    y0 = (row * height) // grid_rows
    x1 = ((col + 1) * width) // grid_cols - 1
    y1 = ((row + 1) * height) // grid_rows - 1
    if x1 < x0:
        x1 = x0
    if y1 < y0:
        y1 = y0
    out.append(x0)
    out.append(y0)
    out.append(x1)
    out.append(y1)
    out.append((x1 - x0 + 1) * (y1 - y0 + 1))
    return out

def extract_box_flat(flat, width, height, x0, y0, x1, y1):
    out = []
    if width <= 0 or height <= 0:
        return out
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
        return out
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            out.append(_pixel_value(flat, y * width + x))
    return out

def box_iou(box_a, box_b):
    if len(box_a) < 4 or len(box_b) < 4:
        return 0.0
    ax0 = box_a[0]
    ay0 = box_a[1]
    ax1 = box_a[2]
    ay1 = box_a[3]
    if ax1 < ax0:
        tmp = ax0
        ax0 = ax1
        ax1 = tmp
    if ay1 < ay0:
        tmp = ay0
        ay0 = ay1
        ay1 = tmp
    bx0 = box_b[0]
    by0 = box_b[1]
    bx1 = box_b[2]
    by1 = box_b[3]
    if bx1 < bx0:
        tmp = bx0
        bx0 = bx1
        bx1 = tmp
    if by1 < by0:
        tmp = by0
        by0 = by1
        by1 = tmp
    ix0 = ax0 if ax0 > bx0 else bx0
    iy0 = ay0 if ay0 > by0 else by0
    ix1 = ax1 if ax1 < bx1 else bx1
    iy1 = ay1 if ay1 < by1 else by1
    if ix1 < ix0 or iy1 < iy0:
        return 0.0
    intersection = float((ix1 - ix0 + 1) * (iy1 - iy0 + 1))
    area_a = float((ax1 - ax0 + 1) * (ay1 - ay0 + 1))
    area_b = float((bx1 - bx0 + 1) * (by1 - by0 + 1))
    union_area = area_a + area_b - intersection
    if union_area <= 0.0:
        return 0.0
    return intersection / union_area
