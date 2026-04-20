"""Python equivalent of mojo/engine/quantum.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import cos
except Exception:
    pass
try:
    from std.math import sin
except Exception:
    pass
try:
    from std.math import atan2
except Exception:
    pass

_SQRT2_INV = 0.7071067811865476  # 1/√2

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

def qubit_zero():
    q = []
    q.append(1.0)
    q.append(0.0)
    q.append(0.0)
    q.append(0.0)
    return q



def qubit_one():
    q = []
    q.append(0.0)
    q.append(0.0)
    q.append(1.0)
    q.append(0.0)
    return q






def hadamard(q):
    a_re = q[0]
    a_im = q[1]
    b_re = q[2]
    b_im = q[3]
    out = []
    out.append(_SQRT2_INV * (a_re + b_re))
    out.append(_SQRT2_INV * (a_im + b_im))
    out.append(_SQRT2_INV * (a_re - b_re))
    out.append(_SQRT2_INV * (a_im - b_im))
    return out



def pauli_x(q):
    out = []
    out.append(q[2])
    out.append(q[3])
    out.append(q[0])
    out.append(q[1])
    return out



def pauli_z(q):
    out = []
    out.append(q[0])
    out.append(q[1])
    out.append(-q[2])
    out.append(-q[3])
    return out



def phase_gate(q, theta):
    b_re = q[2]
    b_im = q[3]
    c = math.cos(theta)
    s = math.sin(theta)
    out = []
    out.append(q[0])
    out.append(q[1])

    out.append(b_re * c - b_im * s)
    out.append(b_re * s + b_im * c)
    return out






def measure_probability(q):
    p0 = q[0] * q[0] + q[1] * q[1]
    p1 = q[2] * q[2] + q[3] * q[3]
    out = []
    out.append(p0)
    out.append(p1)
    return out



def qubit_norm(q):
    return q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]






def bell_state():
    out = []
    out.append(_SQRT2_INV)  # |00⟩ re
    out.append(0.0)         # |00⟩ im
    out.append(0.0)         # |01⟩ re
    out.append(0.0)         # |01⟩ im
    out.append(0.0)         # |10⟩ re
    out.append(0.0)         # |10⟩ im
    out.append(_SQRT2_INV)  # |11⟩ re
    out.append(0.0)         # |11⟩ im
    return out






def expectation_z(q):
    p0 = q[0] * q[0] + q[1] * q[1]
    p1 = q[2] * q[2] + q[3] * q[3]
    return p0 - p1






def bloch_coords(q):
    a_re = q[0]
    a_im = q[1]
    b_re = q[2]
    b_im = q[3]

    re_part = a_re * b_re + a_im * b_im
    im_part = a_re * b_im - a_im * b_re
    p0 = a_re * a_re + a_im * a_im
    p1 = b_re * b_re + b_im * b_im
    out = []
    out.append(2.0 * re_part)   # x
    out.append(2.0 * im_part)   # y
    out.append(p0 - p1)         # z
    return out
