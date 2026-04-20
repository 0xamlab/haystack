"""Python equivalent of mojo/engine/stats_bootstrap.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.random import random_float64
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import log
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

def _sort_floats(arr):
    n = len(arr)
    for i in range(1, n):
        key = arr[i]
        j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key



def _mean(data):
    n = len(data)
    if n == 0:
        return 0.0
    s = 0.0
    for i in range(n):
        s += data[i]
    return s / float(n)



def _median(data):
    n = len(data)
    if n == 0:
        return 0.0
    sorted_d = []
    for i in range(n):
        sorted_d.append(data[i])
    _sort_floats(sorted_d)
    if n % 2 == 1:
        return sorted_d[n // 2]
    return (sorted_d[n // 2 - 1] + sorted_d[n // 2]) / 2.0



def _std(data):
    n = len(data)
    if n < 2:
        return 0.0
    m = _mean(data)
    ss = 0.0
    for i in range(n):
        d = data[i] - m
        ss += d * d
    return math.sqrt(ss / float(n - 1))






def _probit(p):

    pp = p
    if pp < 1e-10:
        pp = 1e-10
    if pp > 1.0 - 1e-10:
        pp = 1.0 - 1e-10
    if pp == 0.5:
        return 0.0
    sign = 1.0
    q = pp
    if pp > 0.5:
        q = 1.0 - pp
        sign = -1.0
    else:
        sign = 1.0
    t = math.sqrt(-2.0 * math.log(q))

    c0 = 2.515517
    c1 = 0.802853
    c2 = 0.010328
    d1 = 1.432788
    d2 = 0.189269
    d3 = 0.001308
    z = t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)
    return -sign * z



def _normcdf(x):


    if x > 8.0:
        return 1.0
    if x < -8.0:
        return 0.0
    t = 1.0 / (1.0 + 0.2316419 * math.fabs(x))
    d = 0.3989422804014327  # 1/math.sqrt(2*pi)
    p = d * _exp_neg_half_x2(x) * t * (
        0.319381530
        + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429)))
    )
    if x >= 0.0:
        return 1.0 - p
    return p



def _exp_neg_half_x2(x):
    from std.math import exp

    return math.exp(-0.5 * x * x)

def bootstrap_replicate(data):
    n = len(data)
    result = []
    for _ in range(n):
        idx = int(random_float64() * float(n))
        if idx >= n:
            idx = n - 1
        result.append(data[idx])
    return result






def bootstrap_mean_ci(data, n_bootstrap, confidence=0.95):
    means = []
    for _ in range(n_bootstrap):
        rep = bootstrap_replicate(data)
        means.append(_mean(rep))
    _sort_floats(means)
    alpha = (1.0 - confidence) / 2.0
    lo_idx = int(alpha * float(n_bootstrap))
    hi_idx = int((1.0 - alpha) * float(n_bootstrap))
    if lo_idx < 0:
        lo_idx = 0
    if hi_idx >= n_bootstrap:
        hi_idx = n_bootstrap - 1
    result = []
    result.append(means[lo_idx])
    result.append(means[hi_idx])
    return result






def bootstrap_std_ci(data, n_bootstrap, confidence=0.95):
    stds = []
    for _ in range(n_bootstrap):
        rep = bootstrap_replicate(data)
        stds.append(_std(rep))
    _sort_floats(stds)
    alpha = (1.0 - confidence) / 2.0
    lo_idx = int(alpha * float(n_bootstrap))
    hi_idx = int((1.0 - alpha) * float(n_bootstrap))
    if lo_idx < 0:
        lo_idx = 0
    if hi_idx >= n_bootstrap:
        hi_idx = n_bootstrap - 1
    result = []
    result.append(stds[lo_idx])
    result.append(stds[hi_idx])
    return result






def bootstrap_median_ci(data, n_bootstrap, confidence=0.95):
    medians = []
    for _ in range(n_bootstrap):
        rep = bootstrap_replicate(data)
        medians.append(_median(rep))
    _sort_floats(medians)
    alpha = (1.0 - confidence) / 2.0
    lo_idx = int(alpha * float(n_bootstrap))
    hi_idx = int((1.0 - alpha) * float(n_bootstrap))
    if lo_idx < 0:
        lo_idx = 0
    if hi_idx >= n_bootstrap:
        hi_idx = n_bootstrap - 1
    result = []
    result.append(medians[lo_idx])
    result.append(medians[hi_idx])
    return result






def bootstrap_bias(data, n_bootstrap, stat_type=0):
    orig_stat = 0.0
    if stat_type == 1:
        orig_stat = _median(data)
    else:
        orig_stat = _mean(data)
    boot_stats = []
    for _ in range(n_bootstrap):
        rep = bootstrap_replicate(data)
        if stat_type == 1:
            boot_stats.append(_median(rep))
        else:
            boot_stats.append(_mean(rep))
    boot_mean = _mean(boot_stats)
    return boot_mean - orig_stat






def bootstrap_se(data, n_bootstrap, stat_type=0):
    boot_stats = []
    for _ in range(n_bootstrap):
        rep = bootstrap_replicate(data)
        if stat_type == 1:
            boot_stats.append(_median(rep))
        else:
            boot_stats.append(_mean(rep))
    return _std(boot_stats)






def bootstrap_test(data1, data2, n_bootstrap):
    n1 = len(data1)
    n2 = len(data2)
    observed_diff = math.fabs(_mean(data1) - _mean(data2))


    pooled = []
    for i in range(n1):
        pooled.append(data1[i])
    for i in range(n2):
        pooled.append(data2[i])
    n_total = n1 + n2

    count = 0
    for _ in range(n_bootstrap):

        perm = []
        for i in range(n_total):
            perm.append(pooled[i])

        for i in range(n_total - 1, 0, -1):
            j = int(random_float64() * float(i + 1))
            if j > i:
                j = i
            tmp = perm[i]
            perm[i] = perm[j]
            perm[j] = tmp


        sum1 = 0.0
        for i in range(n1):
            sum1 += perm[i]
        sum2 = 0.0
        for i in range(n1, n_total):
            sum2 += perm[i]
        diff = math.fabs(sum1 / float(n1) - sum2 / float(n2))
        if diff >= observed_diff:
            count += 1
    return float(count) / float(n_bootstrap)






def jackknife_mean(data):
    n = len(data)
    total = _mean(data) * float(n)
    result = []
    for i in range(n):
        result.append((total - data[i]) / float(n - 1))
    return result






def jackknife_se(data):
    n = len(data)
    if n < 2:
        return 0.0
    jk_means = jackknife_mean(data)
    jk_bar = _mean(jk_means)
    ss = 0.0
    for i in range(n):
        d = jk_means[i] - jk_bar
        ss += d * d
    return math.sqrt(float(n - 1) / float(n) * ss)






def bca_correction(data, n_bootstrap, confidence=0.95):
    n = len(data)
    orig_mean = _mean(data)


    boot_means = []
    for _ in range(n_bootstrap):
        rep = bootstrap_replicate(data)
        boot_means.append(_mean(rep))
    _sort_floats(boot_means)


    count_below = 0
    for i in range(n_bootstrap):
        if boot_means[i] < orig_mean:
            count_below += 1
    p0 = float(count_below) / float(n_bootstrap)
    if p0 <= 0.0:
        p0 = 0.5 / float(n_bootstrap)
    if p0 >= 1.0:
        p0 = 1.0 - 0.5 / float(n_bootstrap)


    z0 = _probit(p0)


    jk_means = jackknife_mean(data)
    jk_bar = _mean(jk_means)
    num = 0.0
    den = 0.0
    for i in range(n):
        d = jk_bar - jk_means[i]
        num += d * d * d
        den += d * d
    a_hat = 0.0
    if den > 1e-15:
        a_hat = num / (6.0 * den * math.sqrt(den))


    alpha = (1.0 - confidence) / 2.0
    z_alpha = _probit(alpha)
    z_1alpha = _probit(1.0 - alpha)

    a1 = z0 + (z0 + z_alpha) / (1.0 - a_hat * (z0 + z_alpha))
    a2 = z0 + (z0 + z_1alpha) / (1.0 - a_hat * (z0 + z_1alpha))

    p1 = _normcdf(a1)
    p2 = _normcdf(a2)

    lo_idx = int(p1 * float(n_bootstrap))
    hi_idx = int(p2 * float(n_bootstrap))
    if lo_idx < 0:
        lo_idx = 0
    if hi_idx >= n_bootstrap:
        hi_idx = n_bootstrap - 1
    if lo_idx > hi_idx:
        lo_idx = 0
        hi_idx = n_bootstrap - 1

    result = []
    result.append(boot_means[lo_idx])
    result.append(boot_means[hi_idx])
    return result


