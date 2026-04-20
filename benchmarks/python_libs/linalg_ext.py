"""Python equivalent of mojo/engine/linalg_ext.mojo (auto-generated)."""
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
    from linalg import Matrix
except Exception:
    pass
try:
    from linalg import mat_zeros
except Exception:
    pass
try:
    from linalg import mat_identity
except Exception:
    pass
try:
    from linalg import mat_from_list
except Exception:
    pass
try:
    from linalg import mat_mul
except Exception:
    pass
try:
    from linalg import mat_transpose
except Exception:
    pass
try:
    from linalg import mat_inv
except Exception:
    pass
try:
    from linalg import mat_det
except Exception:
    pass
try:
    from linalg import vec_dot
except Exception:
    pass
try:
    from linalg import vec_norm
except Exception:
    pass

class QRResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('Q')
        self.Q = _v0 if _v0 is not None else None
        _v1 = args[1] if 1 < len(args) else kwargs.get('R')
        self.R = _v1 if _v1 is not None else None
    def __repr__(self):
        return f'QRResult({vars(self)})'

class PowerIterResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('eigenvalue')
        self.eigenvalue = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('eigenvector')
        self.eigenvector = _v1 if _v1 is not None else []
    def __repr__(self):
        return f'PowerIterResult({vars(self)})'

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

def mat_norm_frobenius(a):
    s = 0.0
    for i in range(a.rows * a.cols):
        s += a.data[i] * a.data[i]
    return math.sqrt(s)






def mat_norm_inf(a):
    max_sum = 0.0
    for i in range(a.rows):
        row_sum = 0.0
        for j in range(a.cols):
            row_sum += math.fabs(a.get(i, j))
        if row_sum > max_sum:
            max_sum = row_sum
    return max_sum






def mat_trace(a):
    n = a.rows
    if a.cols < n:
        n = a.cols
    s = 0.0
    for i in range(n):
        s += a.get(i, i)
    return s






def mat_is_symmetric(a, tol=1e-10):
    if a.rows != a.cols:
        return False
    n = a.rows
    for i in range(n):
        for j in range(i + 1, n):
            if math.fabs(a.get(i, j) - a.get(j, i)) > tol:
                return False
    return True






def mat_is_positive_definite(a):
    if a.rows != a.cols:
        return False
    if not mat_is_symmetric(a):
        return False

    n = a.rows

    l = mat_zeros(n, n)

    for i in range(n):
        for j in range(i + 1):
            s = 0.0
            for k in range(j):
                s += l.get(i, k) * l.get(j, k)

            if i == j:
                diag = a.get(i, i) - s
                if diag <= 0.0:
                    return False  # Not positive definite
                l.set(i, j, math.sqrt(diag))
            else:
                lval = l.get(j, j)
                if math.fabs(lval) < 1e-15:
                    return False
                l.set(i, j, (a.get(i, j) - s) / lval)

    return True






def mat_power_iteration(a, max_iter=100):
    n = a.rows


    v = []
    inv_sqrt_n = 1.0 / math.sqrt(float(n))
    for i in range(n):
        v.append(inv_sqrt_n)

    eigenvalue = 0.0

    for _iter in range(max_iter):

        w = []
        for i in range(n):
            s = 0.0
            for j in range(n):
                s += a.get(i, j) * v[j]
            w.append(s)


        vw = 0.0
        vv = 0.0
        for i in range(n):
            vw += v[i] * w[i]
            vv += v[i] * v[i]
        if vv > 1e-15:
            eigenvalue = vw / vv


        norm_w = 0.0
        for i in range(n):
            norm_w += w[i] * w[i]
        norm_w = math.sqrt(norm_w)

        if norm_w < 1e-15:
            break

        for i in range(n):
            v[i] = w[i] / norm_w

    return PowerIterResult(eigenvalue, v)






def mat_condition_number(a):
    if a.rows != a.cols:
        return 1e18

    norm_a = mat_norm_inf(a)
    a_inv = mat_inv(a)


    inv_is_zero = True
    for i in range(a_inv.rows * a_inv.cols):
        if math.fabs(a_inv.data[i]) > 1e-15:
            inv_is_zero = False
            break

    if inv_is_zero:
        return 1e18  # Singular matrix

    norm_a_inv = mat_norm_inf(a_inv)
    return norm_a * norm_a_inv
