"""Python equivalent of mojo/engine/random_utils.mojo (auto-generated)."""
import math
import random as _rng

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

def random_choice(weights):
    n = len(weights)
    if n == 0:
        return -1
    if n == 1:
        return 0


    total = 0.0
    for i in range(n):
        total += weights[i]

    if total <= 0.0:
        return 0

    u = random_float64() * total
    cumulative = 0.0
    for i in range(n):
        cumulative += weights[i]
        if u <= cumulative:
            return i
    return n - 1






def random_shuffle(data):
    n = len(data)
    if n <= 1:
        return
    for i in range(n - 1, 0, -1):
        j = int(random_float64() * float(i + 1))
        if j > i:
            j = i
        if j != i:
            tmp = data[i]
            data[i] = data[j]
            data[j] = tmp






def random_sample(data, n):
    sz = len(data)
    k = n
    if k > sz:
        k = sz


    pool = []
    for i in range(sz):
        pool.append(data[i])


    for i in range(k):
        j = i + int(random_float64() * float(sz - i))
        if j >= sz:
            j = sz - 1
        if j != i:
            tmp = pool[i]
            pool[i] = pool[j]
            pool[j] = tmp


    result = []
    for i in range(k):
        result.append(pool[i])
    return result






def random_bootstrap(data, n):
    sz = len(data)
    result = []
    if sz == 0:
        return result
    for i in range(n):
        idx = int(random_float64() * float(sz))
        if idx >= sz:
            idx = sz - 1
        result.append(data[idx])
    return result






def random_uniform_int(low, high):
    if low >= high:
        return low
    range_size = high - low
    idx = int(random_float64() * float(range_size))
    if idx >= range_size:
        idx = range_size - 1
    return low + idx






def random_permutation(n):
    perm = []
    for i in range(n):
        perm.append(i)

    for i in range(n - 1, 0, -1):
        j = int(random_float64() * float(i + 1))
        if j > i:
            j = i
        if j != i:
            tmp = perm[i]
            perm[i] = perm[j]
            perm[j] = tmp
    return perm






def stratified_sample(data, n_strata):
    n = len(data)
    result = []
    if n == 0 or n_strata <= 0:
        return result

    strata_count = n_strata
    if strata_count > n:
        strata_count = n

    stratum_size = n // strata_count
    remainder = n - stratum_size * strata_count

    offset = 0
    for s in range(strata_count):

        this_size = stratum_size
        if s < remainder:
            this_size += 1
        if this_size <= 0:
            continue
        idx = offset + int(random_float64() * float(this_size))
        if idx >= offset + this_size:
            idx = offset + this_size - 1
        result.append(data[idx])
        offset += this_size

    return result
