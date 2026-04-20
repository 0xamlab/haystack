"""Python equivalent of mojo/engine/math_ext.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import pow
except Exception:
    pass
try:
    from std.math import sin
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

def _ins_sort(a, lo, hi):
    for i in range(lo + 1, hi + 1):
        k = a[i]
        j = i - 1
        while j >= lo and a[j] > k:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = k



def _sort_copy(data):
    sorted = []
    for i in range(len(data)):
        sorted.append(data[i])
    n = len(sorted)
    if n <= 1:
        return sorted
    _ins_sort(sorted, 0, n - 1)
    return sorted




_PI = 3.141592653589793
_SQRT_2PI = 2.5066282746310002
_SQRT_2 = 1.4142135623730951
_LN_SQRT_2PI = 0.9189385332046727






def mean(data):
    n = len(data)
    if n == 0:
        return 0.0
    s = 0.0
    for i in range(n):
        s += data[i]
    return s / float(n)



def median(data):
    n = len(data)
    if n == 0:
        return 0.0
    sorted = _sort_copy(data)
    if n % 2 == 1:
        return sorted[n // 2]
    return (sorted[n // 2 - 1] + sorted[n // 2]) / 2.0



def mode_approx(data, bins=100):
    n = len(data)
    if n == 0:
        return 0.0
    if n == 1:
        return data[0]

    lo = data[0]
    hi = data[0]
    for i in range(1, n):
        if data[i] < lo:
            lo = data[i]
        if data[i] > hi:
            hi = data[i]

    if lo == hi:
        return lo

    width = (hi - lo) / float(bins)
    counts = []
    for i in range(bins):
        counts.append(0)

    for i in range(n):
        b = int((data[i] - lo) / width)
        if b >= bins:
            b = bins - 1
        if b < 0:
            b = 0
        counts[b] = counts[b] + 1

    max_count = 0
    max_bin = 0
    for i in range(bins):
        if counts[i] > max_count:
            max_count = counts[i]
            max_bin = i

    return lo + (float(max_bin) + 0.5) * width



def stdev(data):
    return math.sqrt(variance(data))



def variance(data):
    n = len(data)
    if n <= 1:
        return 0.0
    m = mean(data)
    s = 0.0
    for i in range(n):
        d = data[i] - m
        s += d * d
    return s / float(n - 1)



def skewness(data):
    n = len(data)
    if n < 3:
        return 0.0
    m = mean(data)
    sd = stdev(data)
    if sd == 0.0:
        return 0.0
    s = 0.0
    for i in range(n):
        z = (data[i] - m) / sd
        s += z * z * z
    nf = float(n)
    return (nf / ((nf - 1.0) * (nf - 2.0))) * s



def kurtosis(data):
    n = len(data)
    if n < 4:
        return 0.0
    m = mean(data)
    sd = stdev(data)
    if sd == 0.0:
        return 0.0
    s = 0.0
    for i in range(n):
        z = (data[i] - m) / sd
        s += z * z * z * z
    nf = float(n)
    num = nf * (nf + 1.0) * s
    den = (nf - 1.0) * (nf - 2.0) * (nf - 3.0)
    correction = 3.0 * (nf - 1.0) * (nf - 1.0) / ((nf - 2.0) * (nf - 3.0))
    return num / den - correction



def covariance(x, y):
    n = len(x)
    if len(y) < n:
        n = len(y)
    if n <= 1:
        return 0.0
    mx = mean(x)
    my = mean(y)
    s = 0.0
    for i in range(n):
        s += (x[i] - mx) * (y[i] - my)
    return s / float(n - 1)



def correlation(x, y):
    n = len(x)
    if len(y) < n:
        n = len(y)
    if n <= 1:
        return 0.0
    mx = mean(x)
    my = mean(y)
    sxy = 0.0
    sxx = 0.0
    syy = 0.0
    for i in range(n):
        dx = x[i] - mx
        dy = y[i] - my
        sxy += dx * dy
        sxx += dx * dx
        syy += dy * dy
    denom = math.sqrt(sxx * syy)
    if denom == 0.0:
        return 0.0
    return sxy / denom






def percentile(data, p):
    return quantile(data, p / 100.0)



def quantile(data, q):
    n = len(data)
    if n == 0:
        return 0.0
    if n == 1:
        return data[0]

    sorted = _sort_copy(data)

    qq = q
    if qq < 0.0:
        qq = 0.0
    if qq > 1.0:
        qq = 1.0

    idx = qq * float(n - 1)
    lo_idx = int(idx)
    if lo_idx >= n - 1:
        return sorted[n - 1]
    if lo_idx < 0:
        return sorted[0]

    frac = idx - float(lo_idx)
    return sorted[lo_idx] * (1.0 - frac) + sorted[lo_idx + 1] * frac



def iqr(data):
    return quantile(data, 0.75) - quantile(data, 0.25)






def z_score(value, mu, sigma):
    if sigma == 0.0:
        return 0.0
    return (value - mu) / sigma



def t_statistic(sample_mean, pop_mean, sample_std, n):
    if n <= 0 or sample_std == 0.0:
        return 0.0
    return (sample_mean - pop_mean) / (sample_std / math.sqrt(float(n)))



def chi_squared(observed, expected):
    n = len(observed)
    if len(expected) < n:
        n = len(expected)
    s = 0.0
    for i in range(n):
        if expected[i] != 0.0:
            d = observed[i] - expected[i]
            s += d * d / expected[i]
    return s






def erf(x):
    t = 1.0 / (1.0 + 0.3275911 * math.fabs(x))
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * math.exp(-x * x)
    if x >= 0.0:
        return y
    return -y



def norm_cdf(x):
    return 0.5 * (1.0 + erf(x / _SQRT_2))



def norm_pdf(x):
    return math.exp(-0.5 * x * x) / _SQRT_2PI



def norm_ppf(p):
    if p <= 0.0:
        return -1e300
    if p >= 1.0:
        return 1e300
    if p == 0.5:
        return 0.0


    a1 = -3.969683028665376e+01
    a2 = 2.209460984245205e+02
    a3 = -2.759285104469687e+02
    a4 = 1.383577518672690e+02
    a5 = -3.066479806614716e+01
    a6 = 2.506628277459239e+00

    b1 = -5.447609879822406e+01
    b2 = 1.615858368580409e+02
    b3 = -1.556989798598866e+02
    b4 = 6.680131188771972e+01
    b5 = -1.328068155288572e+01

    c1 = -7.784894002430293e-03
    c2 = -3.223964580411365e-01
    c3 = -2.400758277161838e+00
    c4 = -2.549732539343734e+00
    c5 = 4.374664141464968e+00
    c6 = 2.938163982698783e+00

    d1 = 7.784695709041462e-03
    d2 = 3.224671290700398e-01
    d3 = 2.445134137142996e+00
    d4 = 3.754408661907416e+00

    p_low = 0.02425
    p_high = 1.0 - 0.02425

    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) / ((((d1 * q + d2) * q + d3) * q + d4) * q + 1.0)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a1 * r + a2) * r + a3) * r + a4) * r + a5) * r + a6) * q / (((((b1 * r + b2) * r + b3) * r + b4) * r + b5) * r + 1.0)
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) / ((((d1 * q + d2) * q + d3) * q + d4) * q + 1.0)



def log_gamma(x):
    if x <= 0.0:
        return 1e300

    xx = x
    if xx < 0.5:
        return math.log(_PI / math.sin(_PI * xx)) - log_gamma(1.0 - xx)

    xx = xx - 1.0
    b = xx + 7.5
    c = 0.99999999999980993
    c += 676.5203681218851 / (xx + 1.0)
    c += -1259.1392167224028 / (xx + 2.0)
    c += 771.32342877765313 / (xx + 3.0)
    c += -176.61502916214059 / (xx + 4.0)
    c += 12.507343278686905 / (xx + 5.0)
    c += -0.13857109526572012 / (xx + 6.0)
    c += 9.9843695780195716e-6 / (xx + 7.0)
    c += 1.5056327351493116e-7 / (xx + 8.0)

    return _LN_SQRT_2PI + (xx + 0.5) * math.log(b) - b + math.log(c)



def gamma_fn(x):
    if x < 0.5:
        return _PI / (math.sin(_PI * x) * gamma_fn(1.0 - x))
    xx = x - 1.0
    b = xx + 7.5
    c = 0.99999999999980993
    c += 676.5203681218851 / (xx + 1.0)
    c += -1259.1392167224028 / (xx + 2.0)
    c += 771.32342877765313 / (xx + 3.0)
    c += -176.61502916214059 / (xx + 4.0)
    c += 12.507343278686905 / (xx + 5.0)
    c += -0.13857109526572012 / (xx + 6.0)
    c += 9.9843695780195716e-6 / (xx + 7.0)
    c += 1.5056327351493116e-7 / (xx + 8.0)
    return math.sqrt(2.0 * _PI) * (b) ** (xx + 0.5) * math.exp(-b) * c



def beta_fn(a, b):
    return math.exp(log_gamma(a) + log_gamma(b) - log_gamma(a + b))
