"""Python equivalent of mojo/engine/image_ops.mojo (auto-generated)."""
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

def _clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v






def convolve_2d(image, kernel):
    ih = len(image)
    iw = len(image[0])
    kh = len(kernel)
    kw = len(kernel[0])
    oh = ih - kh + 1
    ow = iw - kw + 1
    result = []
    for r in range(oh):
        row = []
        for c in range(ow):
            s = 0.0
            for kr in range(kh):
                for kc in range(kw):
                    s += image[r + kr][c + kc] * kernel[kr][kc]
            row.append(s)
        result.append(row)
    return result






def sobel_x_kernel():
    k = []
    r0 = []
    r0.append(-1.0); r0.append(0.0); r0.append(1.0)
    r1 = []
    r1.append(-2.0); r1.append(0.0); r1.append(2.0)
    r2 = []
    r2.append(-1.0); r2.append(0.0); r2.append(1.0)
    k.append(r0); k.append(r1); k.append(r2)
    return k



def sobel_y_kernel():
    k = []
    r0 = []
    r0.append(-1.0); r0.append(-2.0); r0.append(-1.0)
    r1 = []
    r1.append(0.0); r1.append(0.0); r1.append(0.0)
    r2 = []
    r2.append(1.0); r2.append(2.0); r2.append(1.0)
    k.append(r0); k.append(r1); k.append(r2)
    return k



def gaussian_kernel_3x3():
    k = []
    r0 = []
    r0.append(1.0 / 16.0); r0.append(2.0 / 16.0); r0.append(1.0 / 16.0)
    r1 = []
    r1.append(2.0 / 16.0); r1.append(4.0 / 16.0); r1.append(2.0 / 16.0)
    r2 = []
    r2.append(1.0 / 16.0); r2.append(2.0 / 16.0); r2.append(1.0 / 16.0)
    k.append(r0); k.append(r1); k.append(r2)
    return k



def sharpen_kernel():
    k = []
    r0 = []
    r0.append(0.0); r0.append(-1.0); r0.append(0.0)
    r1 = []
    r1.append(-1.0); r1.append(5.0); r1.append(-1.0)
    r2 = []
    r2.append(0.0); r2.append(-1.0); r2.append(0.0)
    k.append(r0); k.append(r1); k.append(r2)
    return k






def histogram(image, n_bins):
    bins = []
    for _ in range(n_bins):
        bins.append(0)
    bin_width = 256.0 / float(n_bins)
    rows = len(image)
    for r in range(rows):
        cols = len(image[r])
        for c in range(cols):
            idx = int(image[r][c] / bin_width)
            if idx >= n_bins:
                idx = n_bins - 1
            if idx < 0:
                idx = 0
            bins[idx] += 1
    return bins






def threshold(image, thresh):
    result = []
    rows = len(image)
    for r in range(rows):
        row = []
        cols = len(image[r])
        for c in range(cols):
            if image[r][c] > thresh:
                row.append(255.0)
            else:
                row.append(0.0)
        result.append(row)
    return result






def invert(image):
    result = []
    rows = len(image)
    for r in range(rows):
        row = []
        cols = len(image[r])
        for c in range(cols):
            row.append(255.0 - image[r][c])
        result.append(row)
    return result






def brightness(image, delta):
    result = []
    rows = len(image)
    for r in range(rows):
        row = []
        cols = len(image[r])
        for c in range(cols):
            row.append(_clamp(image[r][c] + delta, 0.0, 255.0))
        result.append(row)
    return result






def contrast(image, factor):
    result = []
    rows = len(image)
    for r in range(rows):
        row = []
        cols = len(image[r])
        for c in range(cols):
            v = (image[r][c] - 128.0) * factor + 128.0
            row.append(_clamp(v, 0.0, 255.0))
        result.append(row)
    return result






def mean_pixel(image):
    total = 0.0
    count = 0
    rows = len(image)
    for r in range(rows):
        cols = len(image[r])
        for c in range(cols):
            total += image[r][c]
            count += 1
    if count == 0:
        return 0.0
    return total / float(count)
