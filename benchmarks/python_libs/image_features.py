"""Python equivalent of mojo/engine/image_features.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from image_ops import convolve_2d
except Exception:
    pass
try:
    from image_ops import sobel_x_kernel
except Exception:
    pass
try:
    from image_ops import sobel_y_kernel
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

def sobel_magnitude(image):
    gx = convolve_2d(image, sobel_x_kernel())
    gy = convolve_2d(image, sobel_y_kernel())
    result = []
    for r in range(len(gx)):
        row = []
        for c in range(len(gx[r])):
            row.append(math.sqrt(gx[r][c] * gx[r][c] + gy[r][c] * gy[r][c]))
        result.append(row)
    return result



def edge_density(image, mag_threshold):
    mag = sobel_magnitude(image)
    n = 0
    strong = 0
    for r in range(len(mag)):
        for c in range(len(mag[r])):
            n += 1
            if mag[r][c] > mag_threshold:
                strong += 1
    if n == 0:
        return 0.0
    return float(strong) / float(n)






def color_histogram(flat_rgb, width, height, bins_per_channel):
    bins = bins_per_channel
    if bins <= 0:
        bins = 1
    total_bins = bins * bins * bins
    hist = []
    for _ in range(total_bins):
        hist.append(0.0)
    npx = width * height
    bin_w = 256.0 / float(bins)
    count = 0
    for i in range(npx):
        base = i * 3
        if base + 2 >= len(flat_rgb):
            break
        rb = int(flat_rgb[base] / bin_w)
        gb = int(flat_rgb[base + 1] / bin_w)
        bb = int(flat_rgb[base + 2] / bin_w)
        if rb >= bins:
            rb = bins - 1
        if rb < 0:
            rb = 0
        if gb >= bins:
            gb = bins - 1
        if gb < 0:
            gb = 0
        if bb >= bins:
            bb = bins - 1
        if bb < 0:
            bb = 0
        hist[(rb * bins + gb) * bins + bb] += 1.0
        count += 1
    if count > 0:
        for k in range(total_bins):
            hist[k] = hist[k] / float(count)
    return hist



def histogram_intersection(a, b):
    n = len(a)
    if len(b) < n:
        n = len(b)
    s = 0.0
    for i in range(n):
        s += a[i] if a[i] < b[i] else b[i]
    return s



def histogram_chi_square(a, b):
    n = len(a)
    if len(b) < n:
        n = len(b)
    s = 0.0
    for i in range(n):
        denom = a[i] + b[i]
        if denom > 0.0:
            d = a[i] - b[i]
            s += (d * d) / denom
    return 0.5 * s



def histogram_correlation(a, b):
    n = len(a)
    if len(b) < n:
        n = len(b)
    if n == 0:
        return 0.0
    ma = 0.0
    mb = 0.0
    for i in range(n):
        ma += a[i]
        mb += b[i]
    ma = ma / float(n)
    mb = mb / float(n)
    cov = 0.0
    va = 0.0
    vb = 0.0
    for i in range(n):
        da = a[i] - ma
        db = b[i] - mb
        cov += da * db
        va += da * da
        vb += db * db
    denom = math.sqrt(va * vb)
    if denom <= 0.0:
        return 0.0
    return cov / denom






def dominant_colors(flat_rgb, width, height, levels):
    bins = levels
    if bins <= 0:
        bins = 1
    hist = color_histogram(flat_rgb, width, height, bins)
    bin_w = 256.0 / float(bins)
    out = []
    for _pick in range(3):
        best = 0
        best_w = -1.0
        for k in range(len(hist)):
            if hist[k] > best_w:
                best_w = hist[k]
                best = k
        bb = best % bins
        gb = (best // bins) % bins
        rb = (best // (bins * bins)) % bins
        out.append((float(rb) + 0.5) * bin_w)
        out.append((float(gb) + 0.5) * bin_w)
        out.append((float(bb) + 0.5) * bin_w)
        out.append(best_w if best_w > 0.0 else 0.0)
        if len(hist) > 0:
            hist[best] = -1.0
    return out






def saliency_grid(image, grid_rows, grid_cols):
    result = []
    if grid_rows <= 0 or grid_cols <= 0:
        return result
    mag = sobel_magnitude(image)
    hh = len(mag)
    if hh == 0:
        return result
    ww = len(mag[0])
    for gr in range(grid_rows):
        y0 = (gr * hh) // grid_rows
        y1 = ((gr + 1) * hh) // grid_rows
        if y1 <= y0:
            y1 = y0 + 1
        if y1 > hh:
            y1 = hh
        row = []
        for gc in range(grid_cols):
            x0 = (gc * ww) // grid_cols
            x1 = ((gc + 1) * ww) // grid_cols
            if x1 <= x0:
                x1 = x0 + 1
            if x1 > ww:
                x1 = ww
            s = 0.0
            cnt = 0
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    s += mag[yy][xx]
                    cnt += 1
            if cnt == 0:
                row.append(0.0)
            else:
                row.append(s / float(cnt))
        result.append(row)
    return result



def most_salient_cell(saliency):
    rows = len(saliency)
    if rows == 0:
        return -1
    cols = len(saliency[0])
    if cols == 0:
        return -1
    best = -1
    best_v = -1.0
    for r in range(rows):
        for c in range(len(saliency[r])):
            if saliency[r][c] > best_v:
                best_v = saliency[r][c]
                best = r * cols + c
    return best






def edge_density_flat(flat, width, height, mag_threshold):
    return edge_density(reshape_to_grid(flat, width, height), mag_threshold)



def most_salient_cell_flat(flat, width, height, grid_rows, grid_cols):
    grid = reshape_to_grid(flat, width, height)
    return most_salient_cell(saliency_grid(grid, grid_rows, grid_cols))
