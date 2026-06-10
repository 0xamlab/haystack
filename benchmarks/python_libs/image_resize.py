"""Python equivalent of mojo/engine/image_resize.mojo (auto-generated)."""
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

def _empty_grid():
    return []






def reshape_to_grid(flat, width, height):
    result = []
    if width <= 0 or height <= 0:
        return result
    n = len(flat)
    for r in range(height):
        row = []
        for c in range(width):
            idx = r * width + c
            if idx < n:
                row.append(flat[idx])
            else:
                row.append(0.0)
        result.append(row)
    return result



def flatten_grid(image):
    result = []
    rows = len(image)
    for r in range(rows):
        cols = len(image[r])
        for c in range(cols):
            result.append(image[r][c])
    return result






def box_downscale(image, out_w, out_h):
    ih = len(image)
    if ih == 0 or out_w <= 0 or out_h <= 0:
        return _empty_grid()
    iw = len(image[0])
    if iw == 0:
        return _empty_grid()
    result = []
    for oy in range(out_h):
        y0 = (oy * ih) // out_h
        y1 = ((oy + 1) * ih) // out_h
        if y1 <= y0:
            y1 = y0 + 1
        if y1 > ih:
            y1 = ih
        row = []
        for ox in range(out_w):
            x0 = (ox * iw) // out_w
            x1 = ((ox + 1) * iw) // out_w
            if x1 <= x0:
                x1 = x0 + 1
            if x1 > iw:
                x1 = iw
            s = 0.0
            cnt = 0
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    s += image[yy][xx]
                    cnt += 1
            if cnt == 0:
                row.append(0.0)
            else:
                row.append(s / float(cnt))
        result.append(row)
    return result






def bilinear_downscale(image, out_w, out_h):
    ih = len(image)
    if ih == 0 or out_w <= 0 or out_h <= 0:
        return _empty_grid()
    iw = len(image[0])
    if iw == 0:
        return _empty_grid()
    result = []
    for oy in range(out_h):
        sy = (float(oy) + 0.5) * float(ih) / float(out_h) - 0.5
        if sy < 0.0:
            sy = 0.0
        y0 = int(sy)
        y1 = y0 + 1
        if y1 > ih - 1:
            y1 = ih - 1
        fy = sy - float(y0)
        row = []
        for ox in range(out_w):
            sx = (float(ox) + 0.5) * float(iw) / float(out_w) - 0.5
            if sx < 0.0:
                sx = 0.0
            x0 = int(sx)
            x1 = x0 + 1
            if x1 > iw - 1:
                x1 = iw - 1
            fx = sx - float(x0)
            top = image[y0][x0] * (1.0 - fx) + image[y0][x1] * fx
            bot = image[y1][x0] * (1.0 - fx) + image[y1][x1] * fx
            row.append(top * (1.0 - fy) + bot * fy)
        result.append(row)
    return result






def resize_for_hash(image, size):
    return box_downscale(image, size, size)



def resize_for_dhash(image, hash_w, hash_h):
    return box_downscale(image, hash_w + 1, hash_h)






def integral_image(image):
    ih = len(image)
    if ih == 0:
        return _empty_grid()
    iw = len(image[0])
    result = []
    zero_row = []
    for _ in range(iw + 1):
        zero_row.append(0.0)
    result.append(zero_row)
    for y in range(ih):
        row = []
        row.append(0.0)
        for x in range(iw):
            v = image[y][x] + result[y][x + 1] + row[x] - result[y][x]
            row.append(v)
        result.append(row)
    return result



def box_sum(integral, r0, c0, r1, c1):
    h = len(integral)
    if h == 0:
        return 0.0
    w = len(integral[0])
    a0 = r0
    b0 = c0
    a1 = r1
    b1 = c1
    if a0 < 0:
        a0 = 0
    if b0 < 0:
        b0 = 0
    if a1 > h - 2:
        a1 = h - 2
    if b1 > w - 2:
        b1 = w - 2
    if a1 < a0 or b1 < b0:
        return 0.0
    return (
        integral[a1 + 1][b1 + 1]
        - integral[a0][b1 + 1]
        - integral[a1 + 1][b0]
        + integral[a0][b0]
    )






def downscale_flat(flat, in_w, in_h, out_w, out_h):
    grid = reshape_to_grid(flat, in_w, in_h)
    small = box_downscale(grid, out_w, out_h)
    return flatten_grid(small)
