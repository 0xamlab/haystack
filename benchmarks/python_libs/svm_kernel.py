"""Python equivalent of mojo/engine/svm_kernel.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import tanh
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

def kernel_linear(a, b):
    n = len(a)
    if len(b) < n:
        n = len(b)
    s = 0.0
    for i in range(n):
        s += a[i] * b[i]
    return s






def kernel_rbf(a, b, gamma=1.0):
    n = len(a)
    if len(b) < n:
        n = len(b)
    sq = 0.0
    for i in range(n):
        d = a[i] - b[i]
        sq += d * d
    return math.exp(-gamma * sq)






def kernel_polynomial(a, b, degree=3, coef0=0.0):
    dot = kernel_linear(a, b)
    base = dot + coef0
    result = 1.0
    for _ in range(degree):
        result *= base
    return result






def kernel_sigmoid(a, b, gamma=1.0, coef0=0.0):
    dot = kernel_linear(a, b)
    return math.tanh(gamma * dot + coef0)






def kernel_matrix(data, kernel_type, gamma=1.0, degree=3, coef0=0.0):
    n = len(data)
    K = []
    for i in range(n):
        row = []
        for j in range(n):
            if kernel_type == 0:
                row.append(kernel_linear(data[i], data[j]))
            elif kernel_type == 1:
                row.append(kernel_rbf(data[i], data[j], gamma))
            elif kernel_type == 2:
                row.append(kernel_polynomial(data[i], data[j], degree, coef0))
            else:
                row.append(kernel_sigmoid(data[i], data[j], gamma, coef0))
        K.append(row)
    return K






def kernel_center(K):
    n = len(K)
    if n == 0:
        return []
    inv_n = 1.0 / float(n)


    row_mean = []
    for i in range(n):
        s = 0.0
        for j in range(n):
            s += K[i][j]
        row_mean.append(s * inv_n)


    col_mean = []
    for j in range(n):
        s = 0.0
        for i in range(n):
            s += K[i][j]
        col_mean.append(s * inv_n)


    grand = 0.0
    for i in range(n):
        grand += row_mean[i]
    grand *= inv_n


    Kc = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(K[i][j] - row_mean[i] - col_mean[j] + grand)
        Kc.append(row)
    return Kc






def frobenius_norm(K):
    s = 0.0
    for i in range(len(K)):
        for j in range(len(K[i])):
            s += K[i][j] * K[i][j]
    return math.sqrt(s)






def kernel_alignment(K1, K2):
    n = len(K1)
    inner = 0.0
    for i in range(n):
        for j in range(len(K1[i])):
            inner += K1[i][j] * K2[i][j]
    n1 = frobenius_norm(K1)
    n2 = frobenius_norm(K2)
    if n1 < 1e-15 or n2 < 1e-15:
        return 0.0
    return inner / (n1 * n2)






def is_positive_semidefinite(K):
    n = len(K)
    if n == 0:
        return True

    for i in range(n):
        if K[i][i] < -1e-10:
            return False
        for j in range(i + 1, n):
            if math.fabs(K[i][j] - K[j][i]) > 1e-10:
                return False

    for i in range(n):
        off_sum = 0.0
        for j in range(n):
            if j != i:
                off_sum += math.fabs(K[i][j])
        if K[i][i] + 1e-10 < off_sum:
            return False
    return True
