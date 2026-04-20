"""Python equivalent of mojo/engine/nn_layers.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import exp
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
try:
    from std.math import tanh
except Exception:
    pass
try:
    from std.math import abs as fabs
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

def dense_forward(input, weights, bias):
    n_out = len(weights)
    result = []
    for i in range(n_out):
        s = bias[i]
        for j in range(len(weights[i])):
            s += weights[i][j] * input[j]
        result.append(s)
    return result






def relu(x):
    result = []
    for i in range(len(x)):
        if x[i] > 0.0:
            result.append(x[i])
        else:
            result.append(0.0)
    return result






def sigmoid_activation(x):
    result = []
    for i in range(len(x)):
        result.append(1.0 / (1.0 + math.exp(-x[i])))
    return result






def tanh_activation(x):
    result = []
    for i in range(len(x)):
        result.append(math.tanh(x[i]))
    return result






def softmax_layer(x):
    n = len(x)
    max_val = x[0]
    for i in range(1, n):
        if x[i] > max_val:
            max_val = x[i]
    exps = []
    total = 0.0
    for i in range(n):
        e = math.exp(x[i] - max_val)
        exps.append(e)
        total += e
    result = []
    for i in range(n):
        result.append(exps[i] / total)
    return result






def mse_loss(predicted, actual):
    n = len(predicted)
    total = 0.0
    for i in range(n):
        d = predicted[i] - actual[i]
        total += d * d
    return total / float(n)






def cross_entropy_loss(predicted, actual):
    n = len(predicted)
    total = 0.0
    eps = 1e-15
    for i in range(n):
        p = predicted[i]
        if p < eps:
            p = eps
        if p > 1.0 - eps:
            p = 1.0 - eps
        total += actual[i] * math.log(p) + (1.0 - actual[i]) * math.log(1.0 - p)
    return -total / float(n)






def dropout(x, rate):
    result = []
    scale = 1.0 / (1.0 - rate)
    for i in range(len(x)):
        if random_float64() < rate:
            result.append(0.0)
        else:
            result.append(x[i] * scale)
    return result






def batch_norm(x, gamma=1.0, beta=0.0):
    n = len(x)
    mean = 0.0
    for i in range(n):
        mean += x[i]
    mean /= float(n)
    variance = 0.0
    for i in range(n):
        d = x[i] - mean
        variance += d * d
    variance /= float(n)
    std = math.sqrt(variance + 1e-8)
    result = []
    for i in range(n):
        result.append((x[i] - mean) / std * gamma + beta)
    return result






def leaky_relu(x, alpha=0.01):
    result = []
    for i in range(len(x)):
        if x[i] > 0.0:
            result.append(x[i])
        else:
            result.append(alpha * x[i])
    return result






def init_weights_xavier(n_in, n_out):
    limit = math.sqrt(6.0 / float(n_in + n_out))
    weights = []
    for _ in range(n_out):
        row = []
        for _ in range(n_in):
            r = random_float64()  # [0, 1)
            row.append(r * 2.0 * limit - limit)
        weights.append(row)
    return weights
