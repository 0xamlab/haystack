"""Python equivalent of mojo/engine/anomaly.mojo (auto-generated)."""
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
try:
    from std.math import log
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

def _sort_copy(data):
    out = data.copy()
    n = len(out)
    for i in range(1, n):
        k = out[i]
        j = i - 1
        while j >= 0 and out[j] > k:
            out[j + 1] = out[j]
            j -= 1
        out[j + 1] = k
    return out






def _avg_path_length(n):
    if n <= 1.0:
        return 0.0
    if n <= 2.0:
        return 1.0

    h = math.log(n - 1.0) + 0.5772156649  # Euler-Mascheroni
    return 2.0 * h - 2.0 * (n - 1.0) / n



def percentile(data, p):
    n = len(data)
    if n == 0:
        return 0.0
    if n == 1:
        return data[0]
    sorted = _sort_copy(data)
    idx = (p / 100.0) * float(n - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= n:
        return sorted[n - 1]
    frac = idx - float(lo)
    return sorted[lo] * (1.0 - frac) + sorted[hi] * frac






def median(data):
    n = len(data)
    if n == 0:
        return 0.0
    sorted = _sort_copy(data)
    if n % 2 == 1:
        return sorted[n // 2]
    return (sorted[n // 2 - 1] + sorted[n // 2]) / 2.0






def mad(data):
    n = len(data)
    if n == 0:
        return 0.0
    med = median(data)
    deviations = []
    for i in range(n):
        deviations.append(math.fabs(data[i] - med))
    return median(deviations)






def zscore_detect(data, threshold=3.0):
    n = len(data)
    flags = []
    if n < 2:
        for _ in range(n):
            flags.append(False)
        return flags


    mean = 0.0
    for i in range(n):
        mean += data[i]
    mean /= float(n)


    var_sum = 0.0
    for i in range(n):
        d = data[i] - mean
        var_sum += d * d
    std = math.sqrt(var_sum / float(n))

    if std < 1e-15:
        for _ in range(n):
            flags.append(False)
        return flags

    for i in range(n):
        z = math.fabs((data[i] - mean) / std)
        flags.append(z > threshold)
    return flags






def iqr_detect(data, factor=1.5):
    n = len(data)
    flags = []
    if n < 4:
        for _ in range(n):
            flags.append(False)
        return flags

    q1 = percentile(data, 25.0)
    q3 = percentile(data, 75.0)
    iqr_val = q3 - q1
    lower = q1 - factor * iqr_val
    upper = q3 + factor * iqr_val

    for i in range(n):
        flags.append(data[i] < lower or data[i] > upper)
    return flags






def modified_zscore_detect(data, threshold=3.5):
    n = len(data)
    flags = []
    if n < 2:
        for _ in range(n):
            flags.append(False)
        return flags

    med = median(data)
    mad_val = mad(data)

    if mad_val < 1e-15:
        for _ in range(n):
            flags.append(False)
        return flags

    for i in range(n):
        mz = math.fabs(0.6745 * (data[i] - med) / mad_val)
        flags.append(mz > threshold)
    return flags






def isolation_score(data, point, n_trees=100, sample_size=32):
    n = len(data)
    if n == 0:
        return 0.5
    actual_sample = sample_size
    if actual_sample > n:
        actual_sample = n
    max_depth = 10
    if actual_sample > 2:

        d = 0
        v = actual_sample
        while v > 1:
            v = v // 2
            d += 1
        max_depth = d + 1

    total_path = 0.0

    for t in range(n_trees):

        sample = []
        for s in range(actual_sample):
            idx = int(random_float64() * float(n)) % n
            sample.append(data[idx])


        lo = sample[0]
        hi = sample[0]
        for s in range(1, len(sample)):
            if sample[s] < lo:
                lo = sample[s]
            if sample[s] > hi:
                hi = sample[s]


        depth = 0
        cur_lo = lo
        cur_hi = hi
        cur_size = actual_sample
        while depth < max_depth and cur_size > 1:
            if cur_hi - cur_lo < 1e-15:
                break
            split = cur_lo + random_float64() * (cur_hi - cur_lo)

            n_left = 0
            for s in range(len(sample)):
                if sample[s] < split:
                    n_left += 1
            n_right = cur_size - n_left
            if point < split:
                cur_hi = split
                cur_size = n_left
            else:
                cur_lo = split
                cur_size = n_right
            depth += 1


        path = float(depth) + _avg_path_length(float(cur_size))
        total_path += path

    avg_path = total_path / float(n_trees)
    c_n = _avg_path_length(float(actual_sample))
    if c_n < 1e-15:
        return 0.5


    exponent = -avg_path / c_n

    ln2 = 0.6931471805599453
    score = exp_approx(exponent * ln2)
    return score



def exp_approx(x):

    clamped = x
    if clamped > 20.0:
        clamped = 20.0
    if clamped < -20.0:
        clamped = -20.0
    result = 1.0
    term = 1.0
    for i in range(1, 30):
        term *= clamped / float(i)
        result += term
    return result






def grubbs_test_statistic(data):
    n = len(data)
    if n < 3:
        return 0.0

    mean = 0.0
    for i in range(n):
        mean += data[i]
    mean /= float(n)

    var_sum = 0.0
    for i in range(n):
        d = data[i] - mean
        var_sum += d * d
    std = math.sqrt(var_sum / float(n))

    if std < 1e-15:
        return 0.0

    max_dev = 0.0
    for i in range(n):
        dev = math.fabs(data[i] - mean)
        if dev > max_dev:
            max_dev = dev
    return max_dev / std






def count_anomalies(flags):
    count = 0
    for i in range(len(flags)):
        if flags[i]:
            count += 1
    return count
