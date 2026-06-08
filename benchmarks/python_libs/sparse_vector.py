"""Python equivalent of mojo/engine/sparse_vector.mojo (auto-generated)."""
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

def _same_indices(a, b):
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True



def _is_identity_indices(indices, size):
    if len(indices) != size:
        return False
    for i in range(size):
        if indices[i] != i:
            return False
    return True



def _all_above_tol(values, tol):
    for i in range(len(values)):
        if math.fabs(values[i]) <= tol:
            return False
    return True






def sv_dot(idx_a, val_a, idx_b, val_b):
    result = 0.0
    i = 0
    j = 0
    na = len(idx_a)
    nb = len(idx_b)
    while i < na and j < nb:
        if idx_a[i] == idx_b[j]:
            result += val_a[i] * val_b[j]
            i += 1
            j += 1
        elif idx_a[i] < idx_b[j]:
            i += 1
        else:
            j += 1
    return result






def sv_add(idx_a, val_a, idx_b, val_b):
    na = len(idx_a)
    nb = len(idx_b)
    if _same_indices(idx_a, idx_b):
        same_idx = []
        same_val = []
        for i in range(na):
            s = val_a[i] + val_b[i]
            if math.fabs(s) > 1e-15:
                same_idx.append(float(idx_a[i]))
                same_val.append(s)
        same_result = []
        same_result.append(same_idx)
        same_result.append(same_val)
        return same_result

    merged_idx = []
    merged_val = []
    i = 0
    j = 0
    while i < na and j < nb:
        if idx_a[i] == idx_b[j]:
            s = val_a[i] + val_b[j]
            if math.fabs(s) > 1e-15:
                merged_idx.append(float(idx_a[i]))
                merged_val.append(s)
            i += 1
            j += 1
        elif idx_a[i] < idx_b[j]:
            merged_idx.append(float(idx_a[i]))
            merged_val.append(val_a[i])
            i += 1
        else:
            merged_idx.append(float(idx_b[j]))
            merged_val.append(val_b[j])
            j += 1
    while i < na:
        merged_idx.append(float(idx_a[i]))
        merged_val.append(val_a[i])
        i += 1
    while j < nb:
        merged_idx.append(float(idx_b[j]))
        merged_val.append(val_b[j])
        j += 1
    result = []
    result.append(merged_idx)
    result.append(merged_val)
    return result






def sv_scale(values, scalar):
    out = values.copy()
    n = len(out)
    for i in range(n):
        out[i] = out[i] * scalar
    return out






def sv_norm(values):
    s = 0.0
    for i in range(len(values)):
        s += values[i] * values[i]
    return math.sqrt(s)






def sv_cosine(idx_a, val_a, idx_b, val_b):
    dot = sv_dot(idx_a, val_a, idx_b, val_b)
    na = sv_norm(val_a)
    nb = sv_norm(val_b)
    if na < 1e-30 or nb < 1e-30:
        return 0.0
    return dot / (na * nb)






def sv_to_dense(indices, values, size):
    if size <= 0:
        return []
    if len(values) == size and _is_identity_indices(indices, size):
        return values.copy()

    out = []
    for i in range(size):
        out.append(0.0)
    for i in range(len(indices)):
        if indices[i] >= 0 and indices[i] < size:
            out[indices[i]] = values[i]
    return out






def dense_to_sparse(dense, tol=1e-15):
    n = len(dense)
    if _all_above_tol(dense, tol):
        dense_idx = []
        for i in range(n):
            dense_idx.append(float(i))
        dense_result = []
        dense_result.append(dense_idx)
        dense_result.append(dense.copy())
        return dense_result
    idx = []
    vals = []
    for i in range(n):
        if math.fabs(dense[i]) > tol:
            idx.append(float(i))
            vals.append(dense[i])
    result = []
    result.append(idx)
    result.append(vals)
    return result






def sv_nnz(values):
    count = 0
    for i in range(len(values)):
        if math.fabs(values[i]) > 1e-30:
            count += 1
    return count






def sv_sparsity(nnz, size):
    if size <= 0:
        return 1.0
    return 1.0 - float(nnz) / float(size)






def sv_max(values):
    if len(values) == 0:
        return 0.0
    m = values[0]
    for i in range(1, len(values)):
        if values[i] > m:
            m = values[i]
    return m
