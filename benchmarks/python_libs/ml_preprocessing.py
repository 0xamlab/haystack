"""Python equivalent of mojo/engine/ml.preprocessing.mojo (auto-generated)."""
import math
import random as _rng

try:
    from math_ext import mean
except Exception:
    pass
try:
    from math_ext import stdev
except Exception:
    pass
try:
    from math_ext import median
except Exception:
    pass
try:
    from math_ext import iqr
except Exception:
    pass

class SplitResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('train_data')
        self.train_data = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('test_data')
        self.test_data = _v1 if _v1 is not None else []
        _v2 = args[2] if 2 < len(args) else kwargs.get('train_labels')
        self.train_labels = _v2 if _v2 is not None else []
        _v3 = args[3] if 3 < len(args) else kwargs.get('test_labels')
        self.test_labels = _v3 if _v3 is not None else []
    def __repr__(self):
        return f'SplitResult({vars(self)})'

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

def normalize_minmax(data):
    n = len(data)
    result = []
    if n == 0:
        return result

    lo = data[0]
    hi = data[0]
    for i in range(1, n):
        if data[i] < lo:
            lo = data[i]
        if data[i] > hi:
            hi = data[i]

    rng = hi - lo
    for i in range(n):
        if rng == 0.0:
            result.append(0.0)
        else:
            result.append((data[i] - lo) / rng)
    return result






def normalize_zscore(data):
    n = len(data)
    result = []
    if n == 0:
        return result

    m = mean(data)
    s = stdev(data)

    for i in range(n):
        if s == 0.0:
            result.append(0.0)
        else:
            result.append((data[i] - m) / s)
    return result






def normalize_robust(data):
    n = len(data)
    result = []
    if n == 0:
        return result

    med = median(data)
    q_range = iqr(data)

    for i in range(n):
        if q_range == 0.0:
            result.append(0.0)
        else:
            result.append((data[i] - med) / q_range)
    return result






def one_hot_encode(categories, n_classes):
    result = []
    for i in range(len(categories)):
        row = []
        for j in range(n_classes):
            if j == categories[i]:
                row.append(1.0)
            else:
                row.append(0.0)
        result.append(row)
    return result






def polynomial_features(x, degree):
    result = []
    for i in range(len(x)):
        row = []
        val = 1.0
        for _ in range(degree):
            val = val * x[i]
            row.append(val)
        result.append(row)
    return result






def train_test_split(data, labels, test_ratio):
    n = len(data)
    n_test = int(float(n) * test_ratio)
    if n_test < 0:
        n_test = 0
    if n_test > n:
        n_test = n
    n_train = n - n_test

    result = SplitResult()

    for i in range(n_train):
        result.train_data.append(data[i])
        result.train_labels.append(labels[i])

    for i in range(n_train, n):
        result.test_data.append(data[i])
        result.test_labels.append(labels[i])

    return result
