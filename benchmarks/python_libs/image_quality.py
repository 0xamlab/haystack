"""Python equivalent of mojo/engine/image_quality.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log as _log
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass
try:
    from image_ops import convolve_2d
except Exception:
    pass
try:
    from image_ops import histogram
except Exception:
    pass
try:
    from image_ops import mean_pixel
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

def _abs(x):
    return -x if x < 0.0 else x



def _clamp01(x):
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x



def _laplacian_kernel():
    k = []
    r0 = []
    r0.append(0.0); r0.append(1.0); r0.append(0.0)
    r1 = []
    r1.append(1.0); r1.append(-4.0); r1.append(1.0)
    r2 = []
    r2.append(0.0); r2.append(1.0); r2.append(0.0)
    k.append(r0); k.append(r1); k.append(r2)
    return k



def _median(values):
    n = len(values)
    if n == 0:
        return 0.0
    a = []
    for i in range(n):
        a.append(values[i])
    for i in range(1, n):
        key = a[i]
        j = i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
    if n % 2 == 1:
        return a[n // 2]
    return (a[n // 2 - 1] + a[n // 2]) / 2.0






def blur_score(image):
    lap = convolve_2d(image, _laplacian_kernel())
    n = 0
    s = 0.0
    for r in range(len(lap)):
        for c in range(len(lap[r])):
            s += lap[r][c]
            n += 1
    if n == 0:
        return 0.0
    mean = s / float(n)
    acc = 0.0
    for r in range(len(lap)):
        for c in range(len(lap[r])):
            d = lap[r][c] - mean
            acc += d * d
    return acc / float(n)



def is_blurry(image, threshold):
    return blur_score(image) < threshold






def brightness_mean(image):
    return mean_pixel(image)



def contrast_std(image):
    n = 0
    s = 0.0
    for r in range(len(image)):
        for c in range(len(image[r])):
            s += image[r][c]
            n += 1
    if n == 0:
        return 0.0
    mean = s / float(n)
    acc = 0.0
    for r in range(len(image)):
        for c in range(len(image[r])):
            d = image[r][c] - mean
            acc += d * d
    return math.sqrt(acc / float(n))






def shannon_entropy(image):
    bins = histogram(image, 256)
    total = 0
    for i in range(len(bins)):
        total += bins[i]
    if total == 0:
        return 0.0
    ln2 = math.math.log(2.0)
    ent = 0.0
    for i in range(len(bins)):
        if bins[i] > 0:
            p = float(bins[i]) / float(total)
            ent -= p * (math.math.log(p) / ln2)
    return ent



def is_near_blank(image, std_threshold):
    return contrast_std(image) < std_threshold



def uniformity(image):
    bins = histogram(image, 16)
    total = 0
    mx = 0
    for i in range(len(bins)):
        total += bins[i]
        if bins[i] > mx:
            mx = bins[i]
    if total == 0:
        return 0.0
    return float(mx) / float(total)






def noise_estimate(image):
    lap = convolve_2d(image, _laplacian_kernel())
    vals = []
    for r in range(len(lap)):
        for c in range(len(lap[r])):
            vals.append(lap[r][c])
    if len(vals) == 0:
        return 0.0
    med = _median(vals)
    devs = []
    for i in range(len(vals)):
        devs.append(_abs(vals[i] - med))
    return 1.4826 * _median(devs)






def is_over_or_under_exposed(image, low, high):
    m = mean_pixel(image)
    return m < low or m > high



def quality_score(image):
    b = mean_pixel(image)
    exposure = 1.0 - _abs(b - 128.0) / 128.0
    ent = shannon_entropy(image) / 8.0
    blur = blur_score(image)
    sharp = blur / (blur + 100.0)
    return _clamp01(0.4 * sharp + 0.3 * exposure + 0.3 * ent)






def blur_score_flat(flat, width, height):
    return blur_score(reshape_to_grid(flat, width, height))



def brightness_flat(flat, width, height):
    return brightness_mean(reshape_to_grid(flat, width, height))



def entropy_flat(flat, width, height):
    return shannon_entropy(reshape_to_grid(flat, width, height))



def contrast_flat(flat, width, height):
    return contrast_std(reshape_to_grid(flat, width, height))



def quality_score_flat(flat, width, height):
    return quality_score(reshape_to_grid(flat, width, height))
