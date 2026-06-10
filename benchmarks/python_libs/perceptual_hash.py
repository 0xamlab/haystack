"""Python equivalent of mojo/engine/perceptual_hash.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import cos
except Exception:
    pass
try:
    from image_resize import reshape_to_grid
except Exception:
    pass
try:
    from image_resize import resize_for_hash
except Exception:
    pass
try:
    from image_resize import resize_for_dhash
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

def _popcount_u64(x):
    n = x
    count = 0
    for _ in range(64):
        count += int(n & int(1))
        n = n >> int(1)
    return count






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






def _dct8x8(image):
    n = 32
    k = 8
    pi = 3.141592653589793
    cos_t = []
    for freq in range(k):
        row = []
        for i in range(n):
            angle = (2.0 * float(i) + 1.0) * float(freq) * pi / (
                2.0 * float(n)
            )
            row.append(math.cos(angle))
        cos_t.append(row)

    g = []
    for v in range(k):
        row = []
        for x in range(n):
            s = 0.0
            for y in range(n):
                s += image[y][x] * cos_t[v][y]
            row.append(s)
        g.append(row)

    out = []
    for u in range(k):
        for v in range(k):
            s = 0.0
            for x in range(n):
                s += g[v][x] * cos_t[u][x]
            out.append(s)
    return out






def ahash(image):
    g = resize_for_hash(image, 8)
    if len(g) < 8 or len(g[0]) < 8:
        return int(0)
    s = 0.0
    for r in range(8):
        for c in range(8):
            s += g[r][c]
    mean = s / 64.0
    h = 0
    for r in range(8):
        for c in range(8):
            h = h << int(1)
            if g[r][c] >= mean:
                h = h | int(1)
    return h






def dhash(image):
    g = resize_for_dhash(image, 8, 8)
    if len(g) < 8 or len(g[0]) < 9:
        return int(0)
    h = 0
    for r in range(8):
        for c in range(8):
            h = h << int(1)
            if g[r][c] < g[r][c + 1]:
                h = h | int(1)
    return h






def phash(image):
    g = resize_for_hash(image, 32)
    if len(g) < 32 or len(g[0]) < 32:
        return int(0)
    coeffs = _dct8x8(g)
    ac = []
    for i in range(1, 64):
        ac.append(coeffs[i])
    med = _median(ac)
    h = 0
    for i in range(64):
        h = h << int(1)
        if coeffs[i] > med:
            h = h | int(1)
    return h






def hamming_distance(a, b):
    return _popcount_u64(a ^ b)



def is_duplicate(a, b, max_distance):
    return hamming_distance(a, b) <= max_distance






def ahash_flat(flat, width, height):
    return ahash(reshape_to_grid(flat, width, height))



def dhash_flat(flat, width, height):
    return dhash(reshape_to_grid(flat, width, height))



def phash_flat(flat, width, height):
    return phash(reshape_to_grid(flat, width, height))
