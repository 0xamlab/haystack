"""Python equivalent of mojo/engine/dimensions.mojo (auto-generated)."""
import math
import random as _rng

DIM_UNKNOWN = 0
DIM_COUNT = 1   # non-negative integers   [unit]
DIM_CURRENCY = 2   # monetary total          [$]
DIM_RATE = 3   # per-unit value          [$/unit]
DIM_RATIO = 4   # proportion 0–1 or 0–100 [%]
DIM_IDENTIFIER = 5   # surrogate key, no math
DIM_INVALID = -1  # dimensionally inconsistent

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

def infer_from_samples(samples):
    n = len(samples)
    if n == 0:
        return DIM_UNKNOWN

    mn = samples[0]
    mx = samples[0]
    for i in range(1, n):
        if samples[i] < mn:
            mn = samples[i]
        if samples[i] > mx:
            mx = samples[i]


    if mn < 0.0:
        return DIM_UNKNOWN


    non_int = 0
    for i in range(n):
        v = samples[i]
        rv = float(int(v + 0.5))
        diff = v - rv
        if diff < 0.0:
            diff = -diff
        if diff > 1e-4:
            non_int += 1
    dec_frac = float(non_int) / float(n)


    if dec_frac < 0.05:
        return DIM_COUNT


    if mx <= 1.001 and dec_frac > 0.10:
        return DIM_RATIO


    return DIM_UNKNOWN






def propagate(op, dim_a, dim_b):
    if dim_a == DIM_IDENTIFIER or dim_b == DIM_IDENTIFIER:
        return DIM_INVALID


    if op == "multiply" or op == "mul" or op == "*" or op == "x":

        a = dim_a
        b = dim_b
        if a > b:
            tmp = a
            a = b
            b = tmp

        if a == DIM_COUNT and b == DIM_RATE:
            return DIM_CURRENCY
        if a == DIM_COUNT and b == DIM_CURRENCY:
            return DIM_CURRENCY
        if a == DIM_COUNT and b == DIM_RATIO:
            return DIM_COUNT
        if a == DIM_CURRENCY and b == DIM_RATIO:
            return DIM_CURRENCY
        if a == DIM_RATIO and b == DIM_RATE:
            return DIM_RATE
        if a == DIM_RATE and b == DIM_RATE:
            return DIM_INVALID
        if a == DIM_CURRENCY and b == DIM_CURRENCY:
            return DIM_INVALID
        if a == DIM_RATIO and b == DIM_RATIO:
            return DIM_RATIO
        return DIM_UNKNOWN


    if op == "add" or op == "+" or op == "subtract" or op == "-":
        if dim_a == dim_b:
            return dim_a   # same dimension always valid


        if dim_a != DIM_UNKNOWN and dim_b != DIM_UNKNOWN:
            return DIM_INVALID

        return DIM_UNKNOWN


    if op == "divide" or op == "/":
        if dim_a == DIM_CURRENCY and dim_b == DIM_COUNT:
            return DIM_RATE
        if dim_a == DIM_CURRENCY and dim_b == DIM_CURRENCY:
            return DIM_RATIO
        if dim_a == DIM_COUNT    and dim_b == DIM_COUNT:
            return DIM_RATIO
        if dim_a == DIM_RATE     and dim_b == DIM_RATE:
            return DIM_RATIO
        if dim_a == DIM_RATE     and dim_b == DIM_COUNT:
            return DIM_RATE
        return DIM_UNKNOWN

    return DIM_UNKNOWN






def propagate_is_valid(op, dim_a, dim_b):
    return propagate(op, dim_a, dim_b) != DIM_INVALID






def validate_formula(op, dim_a, dim_b, dim_c):
    if dim_a == DIM_UNKNOWN or dim_b == DIM_UNKNOWN or dim_c == DIM_UNKNOWN:
        return True

    expected = propagate(op, dim_a, dim_b)

    if expected == DIM_INVALID:
        return False
    if expected == DIM_UNKNOWN:
        return True

    return expected == dim_c






def can_sum(dim):
    return dim == DIM_COUNT or dim == DIM_CURRENCY



def can_avg(dim):
    return (dim == DIM_COUNT or dim == DIM_CURRENCY
            or dim == DIM_RATE or dim == DIM_RATIO)



def aggregation_valid(agg, dim):
    if dim == DIM_IDENTIFIER:
        return False
    if agg == "sum":
        return can_sum(dim)
    if agg == "avg":
        return can_avg(dim)
    if agg == "count" or agg == "min" or agg == "max":
        return dim != DIM_IDENTIFIER
    return False






def role_for_dimension(dim):
    if dim == DIM_COUNT:
        return str("base_measure")
    if dim == DIM_CURRENCY:
        return str("derived_measure")
    if dim == DIM_RATE:
        return str("unit_measure")
    if dim == DIM_RATIO:
        return str("ratio")
    if dim == DIM_IDENTIFIER:
        return str("identifier")

    return str("metric")



def dimension_name(dim):
    if dim == DIM_COUNT:
        return str("Count [unit]")
    if dim == DIM_CURRENCY:
        return str("Currency [$]")
    if dim == DIM_RATE:
        return str("Rate [$/unit]")
    if dim == DIM_RATIO:
        return str("Ratio [%]")
    if dim == DIM_IDENTIFIER:
        return str("Identifier")
    if dim == DIM_INVALID:
        return str("INVALID")
    return str("Unknown")



def dimension_from_role(role):
    if role == "base_measure":
        return DIM_COUNT
    if role == "derived_measure":
        return DIM_CURRENCY
    if role == "unit_measure":
        return DIM_RATE
    if role == "ratio":
        return DIM_RATIO
    if role == "identifier":
        return DIM_IDENTIFIER
    return DIM_UNKNOWN
