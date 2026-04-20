"""Python equivalent of mojo/engine/linalg.mojo (auto-generated)."""
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

class Matrix:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('rows')
        self.rows = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('cols')
        self.cols = _v1 if _v1 is not None else 0
        self.data = []
        self.data = [0.0] * (self.rows * self.cols)
    def __repr__(self):
        return f'Matrix({vars(self)})'
    def get(self, i, j):
        return self.data[i * self.cols + j]
    
    def set(self, i, j, val):
        self.data[i * self.cols + j] = val
    
    

class LUResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('L')
        self.L = _v0 if _v0 is not None else Matrix()
        _v1 = args[1] if 1 < len(args) else kwargs.get('U')
        self.U = _v1 if _v1 is not None else Matrix()
        _v2 = args[2] if 2 < len(args) else kwargs.get('pivots')
        self.pivots = _v2 if _v2 is not None else []
    def __repr__(self):
        return f'LUResult({vars(self)})'

class EigResult2x2:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('lambda1')
        self.lambda1 = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('lambda2')
        self.lambda2 = _v1 if _v1 is not None else 0.0
    def __repr__(self):
        return f'EigResult2x2({vars(self)})'

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

def _minor_3x3(a, skip_row, skip_col):
    m = []
    for i in range(4):
        if i == skip_row:
            continue
        for j in range(4):
            if j == skip_col:
                continue
            m.append(a.get(i, j))

    return (m[0] * (m[4] * m[8] - m[5] * m[7])
          - m[1] * (m[3] * m[8] - m[5] * m[6])
          + m[2] * (m[3] * m[7] - m[4] * m[6]))



def _det_lu(a):
    n = a.rows

    u = Matrix(n, n)
    for i in range(n * n):
        u.data[i] = a.data[i]

    sign = 1.0

    for col in range(n):

        max_val = 0.0
        max_row = col
        for row in range(col, n):
            v = math.fabs(u.get(row, col))
            if v > max_val:
                max_val = v
                max_row = row

        if max_val < 1e-15:
            return 0.0  # Singular


        if max_row != col:
            for j in range(n):
                tmp = u.get(col, j)
                u.set(col, j, u.get(max_row, j))
                u.set(max_row, j, tmp)
            sign = -sign


        for row in range(col + 1, n):
            factor = u.get(row, col) / u.get(col, col)
            for j in range(col, n):
                u.set(row, j, u.get(row, j) - factor * u.get(col, j))


    det = sign
    for i in range(n):
        det *= u.get(i, i)

    return det






def mat_zeros(rows, cols):
    return Matrix(rows, cols)



def mat_identity(n):
    m = Matrix(n, n)
    for i in range(n):
        m.set(i, i, 1.0)
    return m



def mat_from_list(data, rows, cols):
    m = Matrix(rows, cols)
    n = len(data)
    total = rows * cols
    for i in range(total):
        if i < n:
            m.data[i] = data[i]
    return m






def mat_add(a, b):
    r = a.rows
    c = a.cols
    m = Matrix(r, c)
    for i in range(r * c):
        m.data[i] = a.data[i] + b.data[i]
    return m



def mat_sub(a, b):
    r = a.rows
    c = a.cols
    m = Matrix(r, c)
    for i in range(r * c):
        m.data[i] = a.data[i] - b.data[i]
    return m



def mat_scale(a, s):
    m = Matrix(a.rows, a.cols)
    for i in range(a.rows * a.cols):
        m.data[i] = a.data[i] * s
    return m



def mat_transpose(a):
    m = Matrix(a.cols, a.rows)
    for i in range(a.rows):
        for j in range(a.cols):
            m.set(j, i, a.get(i, j))
    return m






def mat_mul(a, b):
    m = a.rows
    k = a.cols
    n = b.cols
    c = Matrix(m, n)

    for i in range(m):
        for j in range(n):
            s = 0.0
            for p in range(k):
                s += a.get(i, p) * b.get(p, j)
            c.set(i, j, s)

    return c






def mat_det(a):
    n = a.rows
    if n != a.cols:
        return 0.0

    if n == 1:
        return a.get(0, 0)

    if n == 2:
        return a.get(0, 0) * a.get(1, 1) - a.get(0, 1) * a.get(1, 0)

    if n == 3:
        return (a.get(0, 0) * (a.get(1, 1) * a.get(2, 2) - a.get(1, 2) * a.get(2, 1))
              - a.get(0, 1) * (a.get(1, 0) * a.get(2, 2) - a.get(1, 2) * a.get(2, 0))
              + a.get(0, 2) * (a.get(1, 0) * a.get(2, 1) - a.get(1, 1) * a.get(2, 0)))

    if n == 4:

        det = 0.0
        for j in range(4):
            minor = _minor_3x3(a, 0, j)
            if j % 2 == 0:
                det += a.get(0, j) * minor
            else:
                det -= a.get(0, j) * minor
        return det


    return _det_lu(a)



def mat_inv(a):
    n = a.rows
    if n != a.cols:
        return Matrix(n, n)


    aug = Matrix(n, 2 * n)
    for i in range(n):
        for j in range(n):
            aug.set(i, j, a.get(i, j))
        aug.set(i, n + i, 1.0)


    for col in range(n):

        max_val = 0.0
        max_row = col
        for row in range(col, n):
            v = math.fabs(aug.get(row, col))
            if v > max_val:
                max_val = v
                max_row = row

        if max_val < 1e-15:
            return Matrix(n, n)  # Singular


        if max_row != col:
            for j in range(2 * n):
                tmp = aug.get(col, j)
                aug.set(col, j, aug.get(max_row, j))
                aug.set(max_row, j, tmp)


        pivot = aug.get(col, col)
        for j in range(2 * n):
            aug.set(col, j, aug.get(col, j) / pivot)


        for row in range(n):
            if row == col:
                continue
            factor = aug.get(row, col)
            for j in range(2 * n):
                aug.set(row, j, aug.get(row, j) - factor * aug.get(col, j))


    inv = Matrix(n, n)
    for i in range(n):
        for j in range(n):
            inv.set(i, j, aug.get(i, n + j))

    return inv






def vec_dot(a, b):
    n = len(a)
    if len(b) < n:
        n = len(b)
    s = 0.0
    for i in range(n):
        s += a[i] * b[i]
    return s



def vec_norm(a):
    return math.sqrt(vec_dot(a, a))



def vec_cross(a, b):
    result = []
    if len(a) < 3 or len(b) < 3:
        result.append(0.0)
        result.append(0.0)
        result.append(0.0)
        return result

    result.append(a[1] * b[2] - a[2] * b[1])
    result.append(a[2] * b[0] - a[0] * b[2])
    result.append(a[0] * b[1] - a[1] * b[0])
    return result





