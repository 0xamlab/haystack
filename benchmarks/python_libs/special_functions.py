"""Python equivalent of mojo/engine/special_functions.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import sin
except Exception:
    pass

_PI = 3.14159265358979323846
_EULER_MASCHERONI = 0.5772156649015329

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

def _lanczos_coeffs():
    c = []
    c.append(0.99999999999980993)
    c.append(676.5203681218851)
    c.append(-1259.1392167224028)
    c.append(771.32342877765313)
    c.append(-176.61502916214059)
    c.append(12.507343278686905)
    c.append(-0.13857109526572012)
    c.append(9.9843695780195716e-6)
    c.append(1.5056327351493116e-7)
    return c






def _cos_approx(x):

    two_pi = 2.0 * _PI
    z = x
    while z > two_pi:
        z -= two_pi
    while z < 0.0:
        z += two_pi

    x2 = z * z
    return 1.0 - x2 / 2.0 + x2 * x2 / 24.0 - x2 * x2 * x2 / 720.0 + x2 * x2 * x2 * x2 / 40320.0



def _sin_approx(x):
    two_pi = 2.0 * _PI
    z = x
    while z > two_pi:
        z -= two_pi
    while z < 0.0:
        z += two_pi
    x2 = z * z
    return z * (1.0 - x2 / 6.0 + x2 * x2 / 120.0 - x2 * x2 * x2 / 5040.0)






def gamma_function(x):
    if x < 0.5:

        s = math.sin(_PI * x)
        if math.fabs(s) < 1e-15:
            return 1e308  # pole
        return _PI / (s * gamma_function(1.0 - x))

    z = x - 1.0
    g = 7.0
    coeffs = _lanczos_coeffs()
    ag = coeffs[0]
    for i in range(1, 9):
        ag += coeffs[i] / (z + float(i))
    t = z + g + 0.5
    return math.sqrt(2.0 * _PI) * (t ** (z + 0.5)) * math.exp(-t) * ag



def log_gamma(x):
    if x < 0.5:
        s = math.sin(_PI * x)
        if math.fabs(s) < 1e-15:
            return 700.0  # large value for pole
        return math.log(_PI / math.fabs(s)) - log_gamma(1.0 - x)

    z = x - 1.0
    g = 7.0
    coeffs = _lanczos_coeffs()
    ag = coeffs[0]
    for i in range(1, 9):
        ag += coeffs[i] / (z + float(i))
    t = z + g + 0.5
    return 0.5 * math.log(2.0 * _PI) + (z + 0.5) * math.log(t) - t + math.log(ag)






def beta_function(a, b):
    return math.exp(log_gamma(a) + log_gamma(b) - log_gamma(a + b))






def digamma(x):
    result = 0.0
    z = x


    while z < 6.0:
        result -= 1.0 / z
        z += 1.0


    z2 = 1.0 / (z * z)
    result += math.log(z) - 0.5 / z
    result -= z2 * (1.0 / 12.0 - z2 * (1.0 / 120.0 - z2 * (1.0 / 252.0
        - z2 * (1.0 / 240.0 - z2 * (1.0 / 132.0)))))
    return result






def incomplete_gamma_lower(a, x):
    if x < 0.0:
        return 0.0
    if x == 0.0:
        return 0.0

    term = 1.0 / a
    total = term
    for n in range(1, 200):
        term *= x / (a + float(n))
        total += term
        if math.fabs(term) < 1e-15 * math.fabs(total):
            break

    return total * math.exp(-x + a * math.log(x))



def regularized_gamma(a, x):
    if x <= 0.0:
        return 0.0
    return incomplete_gamma_lower(a, x) / gamma_function(a)






def erf(x):
    sign = 1.0
    ax = x
    if x < 0.0:
        sign = -1.0
        ax = -x


    p = 0.3275911
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429

    t = 1.0 / (1.0 + p * ax)
    t2 = t * t
    t3 = t2 * t
    t4 = t3 * t
    t5 = t4 * t

    y = 1.0 - (a1 * t + a2 * t2 + a3 * t3 + a4 * t4 + a5 * t5) * math.exp(
        -ax * ax
    )
    return sign * y



def erfc(x):
    return 1.0 - erf(x)






def bessel_j0(x):
    ax = math.fabs(x)

    if ax < 8.0:

        x2 = x * x
        term = 1.0
        total = 1.0
        for m in range(1, 30):
            term *= -x2 / (4.0 * float(m) * float(m))
            total += term
            if math.fabs(term) < 1e-15:
                break
        return total
    else:

        z = 8.0 / ax
        z2 = z * z
        p0 = 1.0 - 0.1098628627e-2 * z2 + 0.2734510407e-4 * z2 * z2
        q0 = -0.1562499995e-1 * z + 0.1430488765e-3 * z * z2
        theta = ax - 0.7853981634
        return math.sqrt(0.636619772 / ax) * (p0 * _cos_approx(theta)
            - q0 * _sin_approx(theta))



def factorial_float(n):
    if n < 0:
        return 0.0
    if n <= 1:
        return 1.0
    if n <= 20:
        result = 1.0
        for i in range(2, n + 1):
            result *= float(i)
        return result

    return gamma_function(float(n) + 1.0)



def double_factorial(n):
    if n <= 0:
        return 1.0
    result = 1.0
    k = n
    while k > 0:
        result *= float(k)
        k -= 2
    return result






def binomial_coefficient(n, k):
    if k < 0 or k > n:
        return 0.0
    if k == 0 or k == n:
        return 1.0
    fn_val = float(n) + 1.0
    fk = float(k) + 1.0
    fnk = float(n - k) + 1.0
    log_binom = log_gamma(fn_val) - log_gamma(fk) - log_gamma(fnk)
    return math.exp(log_binom)
