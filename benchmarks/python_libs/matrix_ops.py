"""Python equivalent of mojo/engine/matrix_ops.mojo (auto-generated)."""
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

def _mat_rows(A):
    return len(A)



def _mat_cols(A):
    if len(A) == 0:
        return 0
    return len(A[0])



def _mat_mul(A, B):
    m = _mat_rows(A)
    p = _mat_cols(A)
    n = _mat_cols(B)
    C = []
    for i in range(m):
        row = []
        for j in range(n):
            s = 0.0
            for k in range(p):
                s += A[i][k] * B[k][j]
            row.append(s)
        C.append(row)
    return C



def _mat_identity(n):
    I = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            else:
                row.append(0.0)
        I.append(row)
    return I



def _mat_add(A, B):
    m = _mat_rows(A)
    n = _mat_cols(A)
    C = []
    for i in range(m):
        row = []
        for j in range(n):
            row.append(A[i][j] + B[i][j])
        C.append(row)
    return C



def _mat_sub(A, B):
    m = _mat_rows(A)
    n = _mat_cols(A)
    C = []
    for i in range(m):
        row = []
        for j in range(n):
            row.append(A[i][j] - B[i][j])
        C.append(row)
    return C



def _mat_scale(A, s):
    m = _mat_rows(A)
    n = _mat_cols(A)
    C = []
    for i in range(m):
        row = []
        for j in range(n):
            row.append(A[i][j] * s)
        C.append(row)
    return C






def kronecker_product(A, B):
    m = _mat_rows(A)
    n = _mat_cols(A)
    p = _mat_rows(B)
    q = _mat_cols(B)
    C = []
    for i in range(m * p):
        row = []
        for j in range(n * q):
            ai = i // p
            bi = i % p
            aj = j // q
            bj = j % q
            row.append(A[ai][aj] * B[bi][bj])
        C.append(row)
    return C






def hadamard_product(A, B):
    m = _mat_rows(A)
    n = _mat_cols(A)
    C = []
    for i in range(m):
        row = []
        for j in range(n):
            row.append(A[i][j] * B[i][j])
        C.append(row)
    return C






def matrix_power(A, n):
    size = _mat_rows(A)
    if n == 0:
        return _mat_identity(size)
    if n == 1:
        return A.copy()

    result = _mat_identity(size)
    base = A.copy()
    exp = n
    while exp > 0:
        if exp % 2 == 1:
            result = _mat_mul(result, base)
        base = _mat_mul(base, base)
        exp = exp // 2
    return result






def outer_product(a, b):
    n = len(a)
    m = len(b)
    C = []
    for i in range(n):
        row = []
        for j in range(m):
            row.append(a[i] * b[j])
        C.append(row)
    return C






def matrix_exp_approx(A, terms=10):
    size = _mat_rows(A)
    result = _mat_identity(size)
    term = _mat_identity(size)  # A^k / k!
    for k in range(1, terms):
        term = _mat_mul(term, A)
        term = _mat_scale(term, 1.0 / float(k))
        result = _mat_add(result, term)
    return result






def vec(A):
    m = _mat_rows(A)
    n = _mat_cols(A)
    v = []
    for j in range(n):
        for i in range(m):
            v.append(A[i][j])
    return v






def unvec(v, rows, cols):
    A = []
    for i in range(rows):
        row = []
        for j in range(cols):
            row.append(v[j * rows + i])
        A.append(row)
    return A






def matrix_norm_1(A):
    m = _mat_rows(A)
    n = _mat_cols(A)
    max_sum = 0.0
    for j in range(n):
        col_sum = 0.0
        for i in range(m):
            col_sum += math.fabs(A[i][j])
        if col_sum > max_sum:
            max_sum = col_sum
    return max_sum






def matrix_norm_inf(A):
    m = _mat_rows(A)
    n = _mat_cols(A)
    max_sum = 0.0
    for i in range(m):
        row_sum = 0.0
        for j in range(n):
            row_sum += math.fabs(A[i][j])
        if row_sum > max_sum:
            max_sum = row_sum
    return max_sum






def commutator(A, B):
    AB = _mat_mul(A, B)
    BA = _mat_mul(B, A)
    return _mat_sub(AB, BA)






def is_orthogonal(A, tol=1e-8):
    n = _mat_rows(A)
    m = _mat_cols(A)

    for i in range(m):
        for j in range(m):
            s = 0.0
            for k in range(n):
                s += A[k][i] * A[k][j]
            expected = 0.0
            if i == j:
                expected = 1.0
            if math.fabs(s - expected) > tol:
                return False
    return True






def gram_schmidt(vectors):
    n = len(vectors)
    if n == 0:
        return []

    dim = len(vectors[0])
    result = []

    for i in range(n):

        v = []
        for d in range(dim):
            v.append(vectors[i][d])


        for j in range(len(result)):
            dot = 0.0
            for d in range(dim):
                dot += v[d] * result[j][d]
            for d in range(dim):
                v[d] -= dot * result[j][d]


        norm = 0.0
        for d in range(dim):
            norm += v[d] * v[d]
        norm = math.sqrt(norm)

        if norm > 1e-12:
            for d in range(dim):
                v[d] /= norm
            result.append(v)

    return result
