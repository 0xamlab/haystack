"""Python equivalent of mojo/engine/fft.mojo (auto-generated)."""
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
    from std.math import log
except Exception:
    pass

PI = 3.141592653589793

class Complex:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('re')
        self.re = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('im')
        self.im = _v1 if _v1 is not None else 0.0
    def __repr__(self):
        return f'Complex({vars(self)})'

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

def _sin(x):
    v = x
    while v > math.pi:
        v -= 2.0 * math.pi
    while v < -math.pi:
        v += 2.0 * math.pi
    x2 = v * v
    x3 = v * x2
    x5 = x3 * x2
    x7 = x5 * x2
    x9 = x7 * x2
    x11 = x9 * x2
    return v - x3 / 6.0 + x5 / 120.0 - x7 / 5040.0 + x9 / 362880.0 - x11 / 39916800.0



def _cos(x):
    v = x
    while v > math.pi:
        v -= 2.0 * math.pi
    while v < -math.pi:
        v += 2.0 * math.pi
    x2 = v * v
    x4 = x2 * x2
    x6 = x4 * x2
    x8 = x6 * x2
    x10 = x8 * x2
    return 1.0 - x2 / 2.0 + x4 / 24.0 - x6 / 720.0 + x8 / 40320.0 - x10 / 3628800.0



def _atan2(y, x):
    if math.fabs(x) < 1e-15 and math.fabs(y) < 1e-15:
        return 0.0
    if math.fabs(x) < 1e-15:
        return math.pi / 2.0 if y > 0.0 else -math.pi / 2.0
    a = y / x

    neg = a < 0.0
    if neg:
        a = -a
    high = a > 1.0
    if high:
        a = 1.0 / a

    a2 = a * a
    r = a * (1.0 - a2 * (1.0 / 3.0 - a2 * (1.0 / 5.0 - a2 * (1.0 / 7.0 - a2 / 9.0))))
    if high:
        r = math.pi / 2.0 - r
    if neg:
        r = -r
    if x < 0.0:
        if y >= 0.0:
            r += math.pi
        else:
            r -= math.pi
    return r






def _fft_recursive(x, invert):
    n = len(x)
    if n == 1:
        result = []
        result.append(Complex(x[0].re, x[0].im))
        return result


    even = []
    odd = []
    for i in range(0, n, 2):
        even.append(Complex(x[i].re, x[i].im))
    for i in range(1, n, 2):
        odd.append(Complex(x[i].re, x[i].im))

    E = _fft_recursive(even, invert)
    O = _fft_recursive(odd, invert)

    result = []
    for _ in range(n):
        result.append(Complex(0.0, 0.0))

    half = n // 2
    angle_sign = -1.0
    if invert:
        angle_sign = 1.0

    for k in range(half):
        angle = angle_sign * 2.0 * math.pi * float(k) / float(n)
        w = Complex(math.math.cos(angle), math.math.sin(angle))
        t = w * O[k]
        result[k] = math.e[k] + t
        result[k + half] = math.e[k] - t

    return result



def next_power_of_2(n):
    if n <= 1:
        return 1
    p = 1
    while p < n:
        p *= 2
    return p






def zero_pad(x, target_len):
    result = []
    for i in range(len(x)):
        result.append(x[i])
    for _ in range(len(x), target_len):
        result.append(0.0)
    return result






def fft(x):
    n = len(x)
    cx = []
    for i in range(n):
        cx.append(Complex(x[i], 0.0))
    return _fft_recursive(cx, False)



def power_spectrum(x):
    X = fft(x)
    n = float(len(x))
    result = []
    for i in range(len(X)):
        mag2 = X[i].re * X[i].re + X[i].im * X[i].im
        result.append(mag2 / n)
    return result
