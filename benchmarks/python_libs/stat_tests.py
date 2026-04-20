"""Python equivalent of mojo/engine/stat_tests.mojo (auto-generated)."""
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

_PI = 3.141592653589793
_SQRT_2 = 1.4142135623730951
_SQRT_2PI = 2.5066282746310002
_LN_SQRT_2PI = 0.9189385332046727

class TestResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('statistic')
        self.statistic = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('p_value')
        self.p_value = _v1 if _v1 is not None else 0.0
        _v2 = args[2] if 2 < len(args) else kwargs.get('reject_h0')
        self.reject_h0 = _v2 if _v2 is not None else False
    def __repr__(self):
        return f'TestResult({vars(self)})'

class CorrResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('r')
        self.r = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('p_value')
        self.p_value = _v1 if _v1 is not None else 0.0
    def __repr__(self):
        return f'CorrResult({vars(self)})'

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

def _erf(x):
    t = 1.0 / (1.0 + 0.3275911 * math.fabs(x))
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * math.exp(-x * x)
    if x >= 0.0:
        return y
    return -y



def _norm_cdf(x):
    return 0.5 * (1.0 + _erf(x / _SQRT_2))



def _norm_pdf(x):
    return math.exp(-0.5 * x * x) / _SQRT_2PI



def _log_gamma(x):
    if x <= 0.0:
        return 1e300
    xx = x
    if xx < 0.5:
        return math.log(_PI / math.sin(_PI * xx)) - _log_gamma(1.0 - xx)
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



def _regularized_incomplete_beta(x, a, b):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0


    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - _regularized_incomplete_beta(1.0 - x, b, a)


    lbeta = _log_gamma(a) + _log_gamma(b) - _log_gamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1.0 - x) * b - lbeta) / a


    f = 1.0
    c = 1.0
    d = 0.0

    for i in range(1, 201):
        m = i // 2
        numerator = 0.0

        if i % 2 == 0:

            mf = float(m)
            numerator = (mf * (b - mf) * x) / ((a + 2.0 * mf - 1.0) * (a + 2.0 * mf))
        else:

            mf = float(m)
            numerator = -((a + mf) * (a + b + mf) * x) / ((a + 2.0 * mf) * (a + 2.0 * mf + 1.0))

        d = 1.0 + numerator * d
        if math.fabs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d

        c = 1.0 + numerator / c
        if math.fabs(c) < 1e-30:
            c = 1e-30

        f *= c * d

        if math.fabs(c * d - 1.0) < 1e-10:
            break

    return front * (f - 1.0)



def _t_cdf(t, df):
    x = df / (df + t * t)
    ibeta = _regularized_incomplete_beta(x, df / 2.0, 0.5)
    if t >= 0.0:
        return 1.0 - 0.5 * ibeta
    else:
        return 0.5 * ibeta



def _regularized_gamma_lower(s, x):
    if x <= 0.0:
        return 0.0
    if x > s + 200.0:
        return 1.0  # asymptotic


    log_prefix = s * math.log(x) - x - _log_gamma(s)
    prefix = math.exp(log_prefix)

    sum_val = 1.0 / s
    term = 1.0 / s
    for k in range(1, 300):
        term *= x / (s + float(k))
        sum_val += term
        if math.fabs(term) < 1e-12 * math.fabs(sum_val):
            break

    return prefix * sum_val



def _chi2_cdf(x, df):
    if x <= 0.0:
        return 0.0
    return _regularized_gamma_lower(df / 2.0, x / 2.0)



def _ks_asymptotic_pvalue(d, n):
    lam = (math.sqrt(n) + 0.12 + 0.11 / math.sqrt(n)) * d
    if lam == 0.0:
        return 1.0

    p = 0.0
    for k in range(1, 101):
        kf = float(k)
        term = math.exp(-2.0 * kf * kf * lam * lam)
        if k % 2 == 0:
            p -= term
        else:
            p += term
    p = 2.0 * p

    if p < 0.0:
        p = 0.0
    if p > 1.0:
        p = 1.0
    return p



def _insertion_sort(a):
    n = len(a)
    for i in range(1, n):
        k = a[i]
        j = i - 1
        while j >= 0 and a[j] > k:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = k



def _sort_copy(data):
    sorted = []
    for i in range(len(data)):
        sorted.append(data[i])
    _insertion_sort(sorted)
    return sorted



def _mean(data):
    n = len(data)
    if n == 0:
        return 0.0
    s = 0.0
    for i in range(n):
        s += data[i]
    return s / float(n)



def _stdev(data):
    n = len(data)
    if n <= 1:
        return 0.0
    m = _mean(data)
    s = 0.0
    for i in range(n):
        d = data[i] - m
        s += d * d
    return math.sqrt(s / float(n - 1))



def _variance(data):
    n = len(data)
    if n <= 1:
        return 0.0
    m = _mean(data)
    s = 0.0
    for i in range(n):
        d = data[i] - m
        s += d * d
    return s / float(n - 1)






def _norm_ppf_approx(p):
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






def _rank(data, n):

    indices = []
    for i in range(n):
        indices.append(i)


    for i in range(1, n):
        key_idx = indices[i]
        key_val = data[key_idx]
        j = i - 1
        while j >= 0 and data[indices[j]] > key_val:
            indices[j + 1] = indices[j]
            j -= 1
        indices[j + 1] = key_idx


    ranks = []
    for i in range(n):
        ranks.append(0.0)

    i = 0
    while i < n:
        j = i

        while j < n - 1 and data[indices[j + 1]] == data[indices[i]]:
            j += 1

        avg_rank = float(i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indices[k]] = avg_rank
        i = j + 1

    return ranks

def ks_test_2sample(sample1, sample2):
    n1 = len(sample1)
    n2 = len(sample2)
    if n1 == 0 or n2 == 0:
        return TestResult(0.0, 1.0, False)

    s1 = _sort_copy(sample1)
    s2 = _sort_copy(sample2)


    d_max = 0.0
    i1 = 0
    i2 = 0

    while i1 < n1 and i2 < n2:
        if s1[i1] < s2[i2]:
            i1 += 1
        elif s2[i2] < s1[i1]:
            i2 += 1
        else:

            i1 += 1
            i2 += 1
        ecdf1 = float(i1) / float(n1)
        ecdf2 = float(i2) / float(n2)
        diff = math.fabs(ecdf1 - ecdf2)
        if diff > d_max:
            d_max = diff


    n_eff = float(n1 * n2) / float(n1 + n2)
    p_val = _ks_asymptotic_pvalue(d_max, n_eff)

    return TestResult(d_max, p_val, p_val < 0.05)



def ks_test_normal(sample):
    n = len(sample)
    if n == 0:
        return TestResult(0.0, 1.0, False)

    sorted = _sort_copy(sample)
    mu = _mean(sample)
    sd = _stdev(sample)
    if sd == 0.0:
        sd = 1.0

    d_max = 0.0
    for i in range(n):
        z = (sorted[i] - mu) / sd
        cdf_val = _norm_cdf(z)
        ecdf_upper = float(i + 1) / float(n)
        ecdf_lower = float(i) / float(n)

        d1 = math.fabs(ecdf_upper - cdf_val)
        d2 = math.fabs(cdf_val - ecdf_lower)

        if d1 > d_max:
            d_max = d1
        if d2 > d_max:
            d_max = d2

    p_val = _ks_asymptotic_pvalue(d_max, float(n))
    return TestResult(d_max, p_val, p_val < 0.05)






def t_test_1sample(sample, mu0):
    n = len(sample)
    if n < 2:
        return TestResult(0.0, 1.0, False)

    m = _mean(sample)
    s = _stdev(sample)
    if s == 0.0:
        if m == mu0:
            return TestResult(0.0, 1.0, False)
        else:
            return TestResult(1e10, 0.0, True)

    t = (m - mu0) / (s / math.sqrt(float(n)))
    df = float(n - 1)


    p_val = 2.0 * (1.0 - _t_cdf(math.fabs(t), df))
    if p_val > 1.0:
        p_val = 1.0
    if p_val < 0.0:
        p_val = 0.0

    return TestResult(t, p_val, p_val < 0.05)



def t_test_2sample(sample1, sample2):
    n1 = len(sample1)
    n2 = len(sample2)
    if n1 < 2 or n2 < 2:
        return TestResult(0.0, 1.0, False)

    m1 = _mean(sample1)
    m2 = _mean(sample2)
    v1 = _variance(sample1)
    v2 = _variance(sample2)

    se = math.sqrt(v1 / float(n1) + v2 / float(n2))
    if se == 0.0:
        if m1 == m2:
            return TestResult(0.0, 1.0, False)
        else:
            return TestResult(1e10, 0.0, True)

    t = (m1 - m2) / se


    num = (v1 / float(n1) + v2 / float(n2)) * (v1 / float(n1) + v2 / float(n2))
    den = (v1 * v1) / (float(n1 * n1) * float(n1 - 1)) + (v2 * v2) / (float(n2 * n2) * float(n2 - 1))
    df = 0.0
    if den > 0.0:
        df = num / den
    else:
        df = float(n1 + n2 - 2)

    p_val = 2.0 * (1.0 - _t_cdf(math.fabs(t), df))
    if p_val > 1.0:
        p_val = 1.0
    if p_val < 0.0:
        p_val = 0.0

    return TestResult(t, p_val, p_val < 0.05)






def chi_squared_test(observed, expected):
    n = len(observed)
    if len(expected) < n:
        n = len(expected)
    if n == 0:
        return TestResult(0.0, 1.0, False)

    chi2 = 0.0
    for i in range(n):
        if expected[i] > 0.0:
            d = observed[i] - expected[i]
            chi2 += d * d / expected[i]

    df = float(n - 1)
    if df < 1.0:
        df = 1.0


    p_val = 1.0 - _chi2_cdf(chi2, df)
    if p_val < 0.0:
        p_val = 0.0
    if p_val > 1.0:
        p_val = 1.0

    return TestResult(chi2, p_val, p_val < 0.05)






def anderson_darling_normal(sample):
    n = len(sample)
    if n < 3:
        return TestResult(0.0, 1.0, False)

    sorted = _sort_copy(sample)
    mu = _mean(sample)
    sd = _stdev(sample)
    if sd == 0.0:
        return TestResult(0.0, 1.0, False)

    nf = float(n)
    s = 0.0

    for i in range(n):
        z = (sorted[i] - mu) / sd
        cdf_i = _norm_cdf(z)

        if cdf_i < 1e-15:
            cdf_i = 1e-15
        if cdf_i > 1.0 - 1e-15:
            cdf_i = 1.0 - 1e-15

        z_rev = (sorted[n - 1 - i] - mu) / sd
        cdf_rev = _norm_cdf(z_rev)
        if cdf_rev < 1e-15:
            cdf_rev = 1e-15
        if cdf_rev > 1.0 - 1e-15:
            cdf_rev = 1.0 - 1e-15

        weight = float(2 * (i + 1) - 1)
        s += weight * (math.log(cdf_i) + math.log(1.0 - cdf_rev))

    a2 = -nf - s / nf


    a2_star = a2 * (1.0 + 0.75 / nf + 2.25 / (nf * nf))



    p_val = 0.0
    if a2_star < 0.2:
        p_val = 1.0 - math.exp(-13.436 + 101.14 * a2_star - 223.73 * a2_star * a2_star)
    elif a2_star < 0.34:
        p_val = 1.0 - math.exp(-8.318 + 42.796 * a2_star - 59.938 * a2_star * a2_star)
    elif a2_star < 0.6:
        p_val = math.exp(0.9177 - 4.279 * a2_star - 1.38 * a2_star * a2_star)
    elif a2_star < 13.0:
        p_val = math.exp(1.2937 - 5.709 * a2_star + 0.0186 * a2_star * a2_star)
    else:
        p_val = 0.0

    if p_val < 0.0:
        p_val = 0.0
    if p_val > 1.0:
        p_val = 1.0

    return TestResult(a2_star, p_val, p_val < 0.05)






def shapiro_wilk_approx(sample):
    n = len(sample)
    if n < 3:
        return TestResult(1.0, 1.0, False)

    sorted = _sort_copy(sample)
    mu = _mean(sample)


    ss = 0.0
    for i in range(n):
        d = sorted[i] - mu
        ss += d * d

    if ss == 0.0:
        return TestResult(1.0, 1.0, False)


    nf = float(n)
    a = []
    for i in range(n):
        p = (float(i + 1) - 0.375) / (nf + 0.25)

        a.append(_norm_ppf_approx(p))


    a_ss = 0.0
    for i in range(n):
        a_ss += a[i] * a[i]
    a_norm = math.sqrt(a_ss)
    if a_norm == 0.0:
        a_norm = 1.0
    for i in range(n):
        a[i] = a[i] / a_norm


    num = 0.0
    for i in range(n):
        num += a[i] * sorted[i]
    w = (num * num) / ss



    log_n = math.log(nf)
    mu_w = 0.0
    sigma_w = 0.0

    if n <= 11:

        mu_w = -1.2725 + 1.0521 * log_n
        sigma_w = 1.0308 - 0.26758 * log_n
    else:

        mu_w = -1.2725 + 1.0521 * log_n - 0.001 * log_n * log_n
        sigma_w = 1.0308 - 0.26758 * log_n + 0.003 * log_n * log_n

    if sigma_w <= 0.0:
        sigma_w = 0.01

    z = (math.log(1.0 - w) - mu_w) / sigma_w
    p_val = 1.0 - _norm_cdf(z)

    if p_val < 0.0:
        p_val = 0.0
    if p_val > 1.0:
        p_val = 1.0

    return TestResult(w, p_val, p_val < 0.05)



def pearson_r(x, y):
    n = len(x)
    if len(y) < n:
        n = len(y)
    if n < 3:
        return CorrResult(0.0, 1.0)

    mx = _mean(x)
    my = _mean(y)
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
        return CorrResult(0.0, 1.0)

    r = sxy / denom


    if r > 1.0:
        r = 1.0
    if r < -1.0:
        r = -1.0


    r2 = r * r
    if r2 >= 1.0:
        return CorrResult(r, 0.0)

    t = r * math.sqrt(float(n - 2)) / math.sqrt(1.0 - r2)
    df = float(n - 2)
    p_val = 2.0 * (1.0 - _t_cdf(math.fabs(t), df))
    if p_val > 1.0:
        p_val = 1.0
    if p_val < 0.0:
        p_val = 0.0

    return CorrResult(r, p_val)



def spearman_r(x, y):
    n = len(x)
    if len(y) < n:
        n = len(y)
    if n < 3:
        return CorrResult(0.0, 1.0)


    rx = _rank(x, n)
    ry = _rank(y, n)


    result = pearson_r(rx, ry)
    return CorrResult(result.r, result.p_value)


