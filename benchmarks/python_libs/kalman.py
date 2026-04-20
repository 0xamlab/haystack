"""Python equivalent of mojo/engine/kalman.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import abs as fabs
except Exception:
    pass

class KalmanState:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('x')
        self.x = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('P')
        self.P = _v1 if _v1 is not None else []
    def __repr__(self):
        return f'KalmanState({vars(self)})'

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

def _scalar_inv(a):
    result = []
    row = []
    if math.fabs(a[0][0]) < 1e-15:
        row.append(0.0)
    else:
        row.append(1.0 / a[0][0])
    result.append(row)
    return result



def _mat_inv(a):
    n = len(a)
    if n == 1:
        return _scalar_inv(a)
    return mat_inv_2x2(a)






def mat_identity(n):
    result = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            else:
                row.append(0.0)
        result.append(row)
    return result



def mat_mul(a, b):
    rows_a = len(a)
    cols_a = len(a[0]) if rows_a > 0 else 0
    cols_b = len(b[0]) if len(b) > 0 else 0
    result = []
    for i in range(rows_a):
        row = []
        for j in range(cols_b):
            s = 0.0
            for k in range(cols_a):
                s += a[i][k] * b[k][j]
            row.append(s)
        result.append(row)
    return result



def mat_transpose(a):
    rows = len(a)
    cols = len(a[0]) if rows > 0 else 0
    result = []
    for j in range(cols):
        row = []
        for i in range(rows):
            row.append(a[i][j])
        result.append(row)
    return result



def mat_add(a, b):
    rows = len(a)
    cols = len(a[0]) if rows > 0 else 0
    result = []
    for i in range(rows):
        row = []
        for j in range(cols):
            row.append(a[i][j] + b[i][j])
        result.append(row)
    return result



def mat_sub(a, b):
    rows = len(a)
    cols = len(a[0]) if rows > 0 else 0
    result = []
    for i in range(rows):
        row = []
        for j in range(cols):
            row.append(a[i][j] - b[i][j])
        result.append(row)
    return result



def mat_scale(a, s):
    rows = len(a)
    cols = len(a[0]) if rows > 0 else 0
    result = []
    for i in range(rows):
        row = []
        for j in range(cols):
            row.append(a[i][j] * s)
        result.append(row)
    return result



def mat_inv_2x2(a):
    det = a[0][0] * a[1][1] - a[0][1] * a[1][0]
    if math.fabs(det) < 1e-15:

        result = []
        for _ in range(2):
            row = []
            row.append(0.0)
            row.append(0.0)
            result.append(row)
        return result
    inv_det = 1.0 / det
    result = []
    row0 = []
    row0.append(a[1][1] * inv_det)
    row0.append(-a[0][1] * inv_det)
    result.append(row0)
    row1 = []
    row1.append(-a[1][0] * inv_det)
    row1.append(a[0][0] * inv_det)
    result.append(row1)
    return result



def matvec(a, v):
    rows = len(a)
    cols = len(a[0]) if rows > 0 else 0
    result = []
    for i in range(rows):
        s = 0.0
        for j in range(cols):
            s += a[i][j] * v[j]
        result.append(s)
    return result






def kalman_smooth_1d(measurements, process_var, measurement_var):
    n = len(measurements)
    if n == 0:
        return []

    result = []


    x = measurements[0]
    p = measurement_var

    result.append(x)

    for i in range(1, n):

        x_pred = x
        p_pred = p + process_var


        k = p_pred / (p_pred + measurement_var)
        x = x_pred + k * (measurements[i] - x_pred)
        p = (1.0 - k) * p_pred

        result.append(x)

    return result
