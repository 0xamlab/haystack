"""Python equivalent of mojo/engine/causal.mojo (auto-generated)."""
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
    from std.math import exp
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

def _mean(data):
    n = len(data)
    if n == 0:
        return 0.0
    s = 0.0
    for i in range(n):
        s += data[i]
    return s / float(n)



def _variance(data):
    n = len(data)
    if n < 2:
        return 0.0
    m = _mean(data)
    s = 0.0
    for i in range(n):
        d = data[i] - m
        s += d * d
    return s / float(n - 1)



def _std(data):
    return math.sqrt(_variance(data))



def _covariance(x, y):
    n = len(x)
    if n < 2 or len(y) < 2:
        return 0.0
    mn = n
    if len(y) < mn:
        mn = len(y)
    mx = _mean(x)
    my = _mean(y)
    s = 0.0
    for i in range(mn):
        s += (x[i] - mx) * (y[i] - my)
    return s / float(mn - 1)






def ate(outcomes_treated, outcomes_control):
    return _mean(outcomes_treated) - _mean(outcomes_control)






def att(outcomes_treated, counterfactual):
    return _mean(outcomes_treated) - _mean(counterfactual)






def propensity_score(features, treatment):
    result = []
    n = len(features)
    if n == 0:
        return result
    m = _mean(features)
    s = _std(features)
    if s < 1e-15:
        s = 1.0  # avoid division by zero
    for i in range(n):
        z = (features[i] - m) / s
        p = 1.0 / (1.0 + math.exp(-z))

        if p < 0.01:
            p = 0.01
        elif p > 0.99:
            p = 0.99
        result.append(p)
    return result






def ipw_estimate(outcomes, treatment, propensity):
    n = len(outcomes)
    if n == 0:
        return 0.0
    s = 0.0
    for i in range(n):
        p = propensity[i]
        if p < 0.01:
            p = 0.01
        if p > 0.99:
            p = 0.99
        if treatment[i] == 1:
            s += outcomes[i] / p
        else:
            s -= outcomes[i] / (1.0 - p)
    return s / float(n)






def diff_in_diff(pre_treatment, post_treatment, pre_control, post_control):
    d_treat = _mean(post_treatment) - _mean(pre_treatment)
    d_ctrl = _mean(post_control) - _mean(pre_control)
    return d_treat - d_ctrl






def regression_discontinuity(x, y, cutoff):
    sum_above = 0.0
    n_above = 0
    sum_below = 0.0
    n_below = 0
    n = len(x)
    for i in range(n):
        if x[i] >= cutoff:
            sum_above += y[i]
            n_above += 1
        else:
            sum_below += y[i]
            n_below += 1
    if n_above == 0 or n_below == 0:
        return 0.0
    return (sum_above / float(n_above)) - (sum_below / float(n_below))






def iv_estimate(z, x, y):
    cov_zy = _covariance(z, y)
    cov_zx = _covariance(z, x)
    if math.fabs(cov_zx) < 1e-15:
        return 0.0
    return cov_zy / cov_zx






def stratified_ate(outcomes, treatment, strata, n_strata):
    n = len(outcomes)
    if n == 0:
        return 0.0

    total_ate = 0.0
    for s in range(n_strata):
        sum_t = 0.0
        cnt_t = 0
        sum_c = 0.0
        cnt_c = 0
        for i in range(n):
            if strata[i] == s:
                if treatment[i] == 1:
                    sum_t += outcomes[i]
                    cnt_t += 1
                else:
                    sum_c += outcomes[i]
                    cnt_c += 1
        if cnt_t > 0 and cnt_c > 0:
            stratum_ate = (sum_t / float(cnt_t)) - (sum_c / float(cnt_c))
            stratum_size = cnt_t + cnt_c
            total_ate += stratum_ate * float(stratum_size) / float(n)
    return total_ate






def cohens_d(group1, group2):
    n1 = len(group1)
    n2 = len(group2)
    if n1 < 2 or n2 < 2:
        return 0.0
    m1 = _mean(group1)
    m2 = _mean(group2)
    v1 = _variance(group1)
    v2 = _variance(group2)
    pooled = math.sqrt(
        (float(n1 - 1) * v1 + float(n2 - 1) * v2)
        / float(n1 + n2 - 2)
    )
    if pooled < 1e-15:
        return 0.0
    return (m1 - m2) / pooled






def needed_sample_size_ate(effect_size, std, alpha=0.05, power=0.8):

    z_alpha = 0.0
    if alpha <= 0.01:
        z_alpha = 2.576
    elif alpha <= 0.05:
        z_alpha = 1.96
    else:
        z_alpha = 1.645

    z_beta = 0.0
    if power >= 0.95:
        z_beta = 1.645
    elif power >= 0.9:
        z_beta = 1.282
    elif power >= 0.8:
        z_beta = 0.842
    else:
        z_beta = 0.524

    if math.fabs(effect_size) < 1e-15:
        return 1000000  # very large if no effect

    z_sum = z_alpha + z_beta
    n_float = 2.0 * z_sum * z_sum * std * std / (effect_size * effect_size)
    n = int(n_float) + 1  # ceiling
    if n < 2:
        n = 2
    return n
