"""Python equivalent of mojo/engine/matrix_decomp.mojo (auto-generated)."""
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

def det_2x2(A):
    return A[0][0] * A[1][1] - A[0][1] * A[1][0]






def det_3x3(A):
    a = A[0][0]
    b = A[0][1]
    c = A[0][2]
    return (
        a * (A[1][1] * A[2][2] - A[1][2] * A[2][1])
        - b * (A[1][0] * A[2][2] - A[1][2] * A[2][0])
        + c * (A[1][0] * A[2][1] - A[1][1] * A[2][0])
    )






def trace(A):
    s = 0.0
    n = len(A)
    for i in range(n):
        s += A[i][i]
    return s






def is_symmetric(A, tol=1e-10):
    n = len(A)
    for i in range(n):
        if len(A[i]) != n:
            return False
        for j in range(i + 1, n):
            if math.fabs(A[i][j] - A[j][i]) > tol:
                return False
    return True






def cholesky(A):
    n = len(A)

    L = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(0.0)
        L.append(row)
    for i in range(n):
        for j in range(i + 1):
            s = 0.0
            for k in range(j):
                s += L[i][k] * L[j][k]
            if i == j:
                val = A[i][i] - s
                if val <= 0.0:
                    return []  # not PD
                L[i][j] = math.sqrt(val)
            else:
                if L[j][j] == 0.0:
                    return []
                L[i][j] = (A[i][j] - s) / L[j][j]
    return L






def is_positive_definite(A):
    L = cholesky(A)
    return len(L) > 0






def lu_decompose(A):
    n = len(A)

    U = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(A[i][j])
        U.append(row)

    L = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            else:
                row.append(0.0)
        L.append(row)
    for k in range(n):

        max_val = math.fabs(U[k][k])
        max_row = k
        for i in range(k + 1, n):
            if math.fabs(U[i][k]) > max_val:
                max_val = math.fabs(U[i][k])
                max_row = i
        if max_row != k:

            tmp_u = U[k].copy()
            U[k] = U[max_row].copy()
            U[max_row] = tmp_u

            for j in range(k):
                tmp = L[k][j]
                L[k][j] = L[max_row][j]
                L[max_row][j] = tmp

        for i in range(k + 1, n):
            if U[k][k] == 0.0:
                continue
            factor = U[i][k] / U[k][k]
            L[i][k] = factor
            for j in range(k, n):
                U[i][j] = U[i][j] - factor * U[k][j]
    result = List[list]()
    result.append(L)
    result.append(U)
    return result






def eigen_2x2(A):
    a = A[0][0]
    b = A[0][1]
    c = A[1][0]
    d = A[1][1]

    tr = a + d
    det = a * d - b * c
    disc = tr * tr - 4.0 * det
    if disc < 0.0:
        disc = 0.0
    sq = math.sqrt(disc)
    l1 = (tr + sq) / 2.0
    l2 = (tr - sq) / 2.0

    eigenvalues = []
    eigenvalues.append(l1)
    eigenvalues.append(l2)

    v1 = []
    v2 = []

    if math.fabs(b) > 1e-15:
        v1.append(b)
        v1.append(l1 - a)
    elif math.fabs(c) > 1e-15:
        v1.append(l1 - d)
        v1.append(c)
    else:
        v1.append(1.0)
        v1.append(0.0)

    if math.fabs(b) > 1e-15:
        v2.append(b)
        v2.append(l2 - a)
    elif math.fabs(c) > 1e-15:
        v2.append(l2 - d)
        v2.append(c)
    else:
        v2.append(0.0)
        v2.append(1.0)

    mag1 = math.sqrt(v1[0] * v1[0] + v1[1] * v1[1])
    if mag1 > 1e-15:
        v1[0] = v1[0] / mag1
        v1[1] = v1[1] / mag1
    mag2 = math.sqrt(v2[0] * v2[0] + v2[1] * v2[1])
    if mag2 > 1e-15:
        v2[0] = v2[0] / mag2
        v2[1] = v2[1] / mag2
    result = []
    result.append(eigenvalues)
    result.append(v1)
    result.append(v2)
    return result






def forward_substitution(L, b):
    n = len(b)
    x = []
    for i in range(n):
        x.append(0.0)
    for i in range(n):
        s = 0.0
        for j in range(i):
            s += L[i][j] * x[j]
        if L[i][i] == 0.0:
            x[i] = 0.0
        else:
            x[i] = (b[i] - s) / L[i][i]
    return x






def back_substitution(U, b):
    n = len(b)
    x = []
    for i in range(n):
        x.append(0.0)
    for i in range(n - 1, -1, -1):
        s = 0.0
        for j in range(i + 1, n):
            s += U[i][j] * x[j]
        if U[i][i] == 0.0:
            x[i] = 0.0
        else:
            x[i] = (b[i] - s) / U[i][i]
    return x






def solve_lu(A, b):
    n = len(b)

    M = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(A[i][j])
        row.append(b[i])
        M.append(row)

    for k in range(n):

        max_val = math.fabs(M[k][k])
        max_row = k
        for i in range(k + 1, n):
            if math.fabs(M[i][k]) > max_val:
                max_val = math.fabs(M[i][k])
                max_row = i
        if max_row != k:
            tmp = M[k].copy()
            M[k] = M[max_row].copy()
            M[max_row] = tmp

        for i in range(k + 1, n):
            if M[k][k] == 0.0:
                continue
            factor = M[i][k] / M[k][k]
            for j in range(k, n + 1):
                M[i][j] = M[i][j] - factor * M[k][j]

    x = []
    for i in range(n):
        x.append(0.0)
    for i in range(n - 1, -1, -1):
        s = 0.0
        for j in range(i + 1, n):
            s += M[i][j] * x[j]
        if M[i][i] == 0.0:
            x[i] = 0.0
        else:
            x[i] = (M[i][n] - s) / M[i][i]
    return x
