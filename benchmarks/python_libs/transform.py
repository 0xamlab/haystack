"""Python equivalent of mojo/engine/transform.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import sqrt
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

def _exp(x):




    from std.math import exp
    return math.exp(x)






def _sorted_copy(data):
    s = []
    for i in range(len(data)):
        s.append(data[i])
    n = len(s)
    for i in range(1, n):
        key = s[i]
        j = i - 1
        while j >= 0 and s[j] > key:
            s[j + 1] = s[j]
            j -= 1
        s[j + 1] = key
    return s



def _percentile(sorted_data, p):
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    idx = p * float(n - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= n:
        return sorted_data[n - 1]
    frac = idx - float(lo)
    return sorted_data[lo] * (1.0 - frac) + sorted_data[hi] * frac



def log_transform(data):
    result = []
    for i in range(len(data)):
        if data[i] <= 0.0:
            raise Error("log_transform: non-positive value at index " + str(i))
        result.append(math.log(data[i]))
    return result






def log1p_transform(data):
    result = []
    for i in range(len(data)):
        v = 1.0 + data[i]
        if v <= 0.0:
            raise Error("log1p_transform: 1+x non-positive at index " + str(i))
        result.append(math.log(v))
    return result






def box_cox(data, lmbda):
    result = []
    for i in range(len(data)):
        if data[i] <= 0.0:
            raise Error("box_cox: non-positive value at index " + str(i))
        if math.fabs(lmbda) < 1e-12:
            result.append(math.log(data[i]))
        else:

            powered = math.math.exp(lmbda * math.log(data[i]))
            result.append((powered - 1.0) / lmbda)
    return result



def standardize(data):
    n = len(data)
    if n == 0:
        raise Error("standardize: empty data")
    s = 0.0
    for i in range(n):
        s += data[i]
    mean = s / float(n)
    ss = 0.0
    for i in range(n):
        d = data[i] - mean
        ss += d * d
    std = math.sqrt(ss / float(n))
    if std < 1e-15:
        raise Error("standardize: zero standard deviation")
    result = []
    for i in range(n):
        result.append((data[i] - mean) / std)
    return result






def min_max_scale(data, new_min=0.0, new_max=1.0):
    n = len(data)
    if n == 0:
        raise Error("min_max_scale: empty data")
    lo = data[0]
    hi = data[0]
    for i in range(1, n):
        if data[i] < lo:
            lo = data[i]
        if data[i] > hi:
            hi = data[i]
    rng = hi - lo
    if rng < 1e-15:
        raise Error("min_max_scale: constant data")
    result = []
    for i in range(n):
        scaled = (data[i] - lo) / rng
        result.append(new_min + scaled * (new_max - new_min))
    return result






def robust_scale(data):
    n = len(data)
    if n == 0:
        raise Error("robust_scale: empty data")
    s = _sorted_copy(data)
    median = _percentile(s, 0.5)
    q1 = _percentile(s, 0.25)
    q3 = _percentile(s, 0.75)
    iqr = q3 - q1
    if iqr < 1e-15:
        raise Error("robust_scale: zero IQR")
    result = []
    for i in range(n):
        result.append((data[i] - median) / iqr)
    return result






def quantile_transform(data):
    n = len(data)
    if n == 0:
        raise Error("quantile_transform: empty data")
    if n == 1:
        result = []
        result.append(0.5)
        return result


    result = []
    for i in range(n):
        less = 0
        equal = 0
        for j in range(n):
            if data[j] < data[i]:
                less += 1
            elif data[j] == data[i]:
                equal += 1

        avg_rank = float(less) + float(equal - 1) / 2.0
        result.append(avg_rank / float(n - 1))
    return result






def power_transform(data, power):
    from std.math import exp
    result = []
    for i in range(len(data)):
        x = data[i]
        if x == 0.0:
            result.append(0.0)
        elif x > 0.0:
            result.append(math.exp(power * math.log(x)))
        else:

            result.append(-math.exp(power * math.log(-x)))
    return result






def clamp_values(data, lo, hi):
    result = []
    for i in range(len(data)):
        v = data[i]
        if v < lo:
            v = lo
        if v > hi:
            v = hi
        result.append(v)
    return result






def rank_transform(data):
    n = len(data)
    result = []
    for i in range(n):
        rank_sum = 0.0
        count = 0
        for j in range(n):
            if data[j] < data[i]:
                rank_sum += 1.0
            if data[j] == data[i]:
                count += 1

        avg = rank_sum + float(count + 1) / 2.0
        result.append(avg)
    return result






def abs_transform(data):
    result = []
    for i in range(len(data)):
        result.append(math.fabs(data[i]))
    return result






def reciprocal_transform(data):
    result = []
    for i in range(len(data)):
        if math.fabs(data[i]) < 1e-15:
            raise Error("reciprocal_transform: zero value at index " + str(i))
        result.append(1.0 / data[i])
    return result
