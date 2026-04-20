"""Python equivalent of mojo/engine/pipeline.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import abs as fabs
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

def map_list(data, op):
    result = []
    for i in range(len(data)):
        v = data[i]
        if op == 0:
            result.append(v * v)
        elif op == 1:
            result.append(math.sqrt(v))
        elif op == 2:
            result.append(-v)
        elif op == 3:
            result.append(math.fabs(v))
        elif op == 4:
            result.append(v * 2.0)
        else:
            result.append(v)
    return result






def filter_list(data, op, threshold):
    result = []
    for i in range(len(data)):
        v = data[i]
        if op == 0 and v > threshold:
            result.append(v)
        elif op == 1 and v < threshold:
            result.append(v)
        elif op == 2 and math.fabs(v - threshold) < 1e-9:
            result.append(v)
        elif op == 3 and v >= threshold:
            result.append(v)
    return result






def reduce_sum(data):
    s = 0.0
    for i in range(len(data)):
        s += data[i]
    return s






def reduce_product(data):
    p = 1.0
    for i in range(len(data)):
        p *= data[i]
    return p






def reduce_min(data):
    if len(data) == 0:
        return 1e308
    m = data[0]
    for i in range(1, len(data)):
        if data[i] < m:
            m = data[i]
    return m






def reduce_max(data):
    if len(data) == 0:
        return -1e308
    m = data[0]
    for i in range(1, len(data)):
        if data[i] > m:
            m = data[i]
    return m






def chain_map_filter(data, map_op, filter_op, threshold):
    mapped = map_list(data, map_op)
    return filter_list(mapped, filter_op, threshold)






def batch(data, batch_size):
    result = []
    n = len(data)
    i = 0
    while i < n:
        b = []
        end = i + batch_size
        if end > n:
            end = n
        for j in range(i, end):
            b.append(data[j])
        result.append(b)
        i += batch_size
    return result






def flatten(batches):
    result = []
    for i in range(len(batches)):
        for j in range(len(batches[i])):
            result.append(batches[i][j])
    return result






def zip_lists(a, b):
    n = len(a)
    if len(b) < n:
        n = len(b)
    result = []
    for i in range(n):
        pair = []
        pair.append(a[i])
        pair.append(b[i])
        result.append(pair)
    return result






def window(data, size):
    result = []
    n = len(data)
    if size <= 0 or size > n:
        return result
    for i in range(n - size + 1):
        w = []
        for j in range(i, i + size):
            w.append(data[j])
        result.append(w)
    return result






def unique_values(data):
    result = []
    for i in range(len(data)):
        found = False
        for j in range(len(result)):
            if math.fabs(data[i] - result[j]) < 1e-12:
                found = True
                break
        if not found:
            result.append(data[i])
    return result
