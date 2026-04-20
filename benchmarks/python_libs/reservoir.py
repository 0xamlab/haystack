"""Python equivalent of mojo/engine/reservoir.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import floor
except Exception:
    pass
try:
    from std.random import random_float64
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

def reservoir_sample(stream, k):
    n = len(stream)
    if k >= n:
        copy = []
        for i in range(n):
            copy.append(stream[i])
        return copy
    reservoir = []
    for i in range(k):
        reservoir.append(stream[i])
    for i in range(k, n):
        j = int(random_float64() * float(i + 1))
        if j < 0:
            j = 0
        if j >= i + 1:
            j = i
        if j < k:
            reservoir[j] = stream[i]
    return reservoir






def weighted_reservoir_sample(stream, weights, k):
    n = len(stream)
    if k >= n:
        copy = []
        for i in range(n):
            copy.append(stream[i])
        return copy


    reservoir = []
    keys = []
    for i in range(k):
        u = random_float64()
        if u < 1e-15:
            u = 1e-15
        w = weights[i]
        if w < 1e-15:
            w = 1e-15
        key = math.log(u) / w  # math.log(u^(1/w)) = math.log(u)/w — monotone transform
        reservoir.append(stream[i])
        keys.append(key)


    min_key = keys[0]
    min_idx = 0
    for i in range(1, k):
        if keys[i] < min_key:
            min_key = keys[i]
            min_idx = i


    for i in range(k, n):
        u = random_float64()
        if u < 1e-15:
            u = 1e-15
        w = weights[i]
        if w < 1e-15:
            w = 1e-15
        key = math.log(u) / w
        if key > min_key:
            reservoir[min_idx] = stream[i]
            keys[min_idx] = key

            min_key = keys[0]
            min_idx = 0
            for j in range(1, k):
                if keys[j] < min_key:
                    min_key = keys[j]
                    min_idx = j

    return reservoir






def reservoir_sample_indices(n, k):
    actual_k = k
    if actual_k > n:
        actual_k = n

    indices = []
    for i in range(n):
        indices.append(i)

    for i in range(actual_k):
        remaining = n - i
        j_offset = int(random_float64() * float(remaining))
        if j_offset >= remaining:
            j_offset = remaining - 1
        if j_offset < 0:
            j_offset = 0
        j = i + j_offset

        tmp = indices[i]
        indices[i] = indices[j]
        indices[j] = tmp

    result = []
    for i in range(actual_k):
        result.append(indices[i])
    return result






def bootstrap_sample(data):
    n = len(data)
    result = []
    for _ in range(n):
        idx = int(random_float64() * float(n))
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0
        result.append(data[idx])
    return result






def systematic_sample(data, k):
    n = len(data)
    if k >= n:
        copy = []
        for i in range(n):
            copy.append(data[i])
        return copy
    step = float(n) / float(k)
    start = random_float64() * step
    result = []
    for i in range(k):
        idx = int(start + float(i) * step)
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0
        result.append(data[idx])
    return result






def sample_with_replacement(data, k):
    n = len(data)
    result = []
    for _ in range(k):
        idx = int(random_float64() * float(n))
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0
        result.append(data[idx])
    return result






def sample_without_replacement(data, k):
    n = len(data)
    actual_k = k
    if actual_k > n:
        actual_k = n

    arr = []
    for i in range(n):
        arr.append(data[i])

    for i in range(actual_k):
        remaining = n - i
        j_offset = int(random_float64() * float(remaining))
        if j_offset >= remaining:
            j_offset = remaining - 1
        if j_offset < 0:
            j_offset = 0
        j = i + j_offset
        tmp = arr[i]
        arr[i] = arr[j]
        arr[j] = tmp
    result = []
    for i in range(actual_k):
        result.append(arr[i])
    return result
