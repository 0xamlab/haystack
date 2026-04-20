"""Python equivalent of mojo/engine/dimensionality.mojo (auto-generated)."""
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

class PCAResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('components')
        self.components = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('explained_variance')
        self.explained_variance = _v1 if _v1 is not None else []
        _v2 = args[2] if 2 < len(args) else kwargs.get('explained_variance_ratio')
        self.explained_variance_ratio = _v2 if _v2 is not None else []
        _v3 = args[3] if 3 < len(args) else kwargs.get('mean')
        self.mean = _v3 if _v3 is not None else []
    def __repr__(self):
        return f'PCAResult({vars(self)})'

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

def column_means(data):
    n = len(data)
    if n == 0:
        return []
    d = len(data[0])
    means = []
    for j in range(d):
        s = 0.0
        for i in range(n):
            s += data[i][j]
        means.append(s / float(n))
    return means






def center_data(data):
    n = len(data)
    if n == 0:
        return []
    means = column_means(data)
    d = len(means)
    result = []
    for i in range(n):
        row = []
        for j in range(d):
            row.append(data[i][j] - means[j])
        result.append(row)
    return result






def covariance_matrix(data):
    n = len(data)
    result = []
    if n < 2:
        return result
    d = len(data[0])

    for j in range(d):
        row = []
        for k in range(d):
            s = 0.0
            for i in range(n):
                s += data[i][j] * data[i][k]
            row.append(s / float(n - 1))
        result.append(row)
    return result






def power_iteration(matrix, n_iter=100):
    d = len(matrix)
    if d == 0:
        return []


    b = []
    init_val = 1.0 / math.sqrt(float(d))
    for _ in range(d):
        b.append(init_val)

    for _ in range(n_iter):

        ab = []
        for i in range(d):
            s = 0.0
            for j in range(d):
                s += matrix[i][j] * b[j]
            ab.append(s)


        norm = 0.0
        for i in range(d):
            norm += ab[i] * ab[i]
        norm = math.sqrt(norm)
        if norm < 1e-15:
            return b

        for i in range(d):
            b[i] = ab[i] / norm

    return b






def eigenvalue_from_vector(matrix, eigvec):
    d = len(eigvec)
    if d == 0:
        return 0.0


    av = []
    for i in range(d):
        s = 0.0
        for j in range(d):
            s += matrix[i][j] * eigvec[j]
        av.append(s)


    av_dot_v = 0.0
    v_dot_v = 0.0
    for i in range(d):
        av_dot_v += av[i] * eigvec[i]
        v_dot_v += eigvec[i] * eigvec[i]

    if v_dot_v < 1e-30:
        return 0.0
    return av_dot_v / v_dot_v






def deflate_matrix(matrix, eigval, eigvec):
    d = len(matrix)
    result = []
    for i in range(d):
        row = []
        for j in range(d):
            row.append(matrix[i][j] - eigval * eigvec[i] * eigvec[j])
        result.append(row)
    return result






def pca(data, n_components):
    result = PCAResult()
    n = len(data)
    if n < 2:
        return result
    d = len(data[0])
    k = n_components
    if k > d:
        k = d


    result.mean = column_means(data)
    centered = center_data(data)


    cov = covariance_matrix(centered)


    total_var = 0.0

    for i in range(d):
        total_var += cov[i][i]

    current_cov = cov
    for _ in range(k):
        evec = power_iteration(current_cov, 200)
        eval_ = eigenvalue_from_vector(current_cov, evec)
        if eval_ < 0.0:
            eval_ = 0.0
        result.components.append(evec)
        result.explained_variance.append(eval_)
        current_cov = deflate_matrix(current_cov, eval_, result.components[len(result.components) - 1])


    for i in range(k):
        if total_var > 1e-15:
            result.explained_variance_ratio.append(
                result.explained_variance[i] / total_var
            )
        else:
            result.explained_variance_ratio.append(0.0)

    return result





