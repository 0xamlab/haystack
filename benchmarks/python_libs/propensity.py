"""Python equivalent of mojo/engine/propensity.mojo (auto-generated)."""
import math
import random as _rng

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
try:
    from std.math import sqrt
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

def _sigmoid(x):
    if x > 500.0:
        return 1.0
    if x < -500.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))






def propensity_scores(features, treatment):
    n = len(features)
    if n == 0:
        return []
    d = len(features[0])


    means = []
    stds = []
    for j in range(d):
        s = 0.0
        for i in range(n):
            s += features[i][j]
        m = s / float(n)
        means.append(m)
        ss = 0.0
        for i in range(n):
            diff = features[i][j] - m
            ss += diff * diff
        sd = math.sqrt(ss / float(n))
        if sd < 1e-12:
            sd = 1.0
        stds.append(sd)


    treat_mean = 0.0
    for i in range(n):
        treat_mean += float(treatment[i])
    treat_mean /= float(n)

    weights = []
    for j in range(d):
        cov = 0.0
        for i in range(n):
            cov += (features[i][j] - means[j]) * (float(treatment[i]) - treat_mean)
        cov /= float(n)
        weights.append(cov / (stds[j] * stds[j]))


    scores = []
    for i in range(n):
        z = 0.0
        for j in range(d):
            z += weights[j] * (features[i][j] - means[j]) / stds[j]
        s = _sigmoid(z)

        if s < 1e-6:
            s = 1e-6
        if s > 1.0 - 1e-6:
            s = 1.0 - 1e-6
        scores.append(s)
    return scores






def nearest_neighbor_match(scores_treated, scores_control):
    matches = []
    for i in range(len(scores_treated)):
        best_idx = 0
        best_dist = math.fabs(scores_treated[i] - scores_control[0])
        for j in range(1, len(scores_control)):
            d = math.fabs(scores_treated[i] - scores_control[j])
            if d < best_dist:
                best_dist = d
                best_idx = j
        matches.append(best_idx)
    return matches






def caliper_match(scores_treated, scores_control, caliper):
    matches = []
    for i in range(len(scores_treated)):
        best_idx = -1
        best_dist = caliper + 1.0
        for j in range(len(scores_control)):
            d = math.fabs(scores_treated[i] - scores_control[j])
            if d <= caliper and d < best_dist:
                best_dist = d
                best_idx = j
        matches.append(best_idx)
    return matches






def matched_ate(outcomes, treatment, matches):

    treated_outcomes = []
    control_outcomes_list = []
    control_indices = []

    for i in range(len(treatment)):
        if treatment[i] == 1:
            treated_outcomes.append(outcomes[i])
        else:
            control_outcomes_list.append(outcomes[i])
            control_indices.append(i)

    if len(treated_outcomes) == 0:
        return 0.0

    total = 0.0
    count = 0
    for i in range(len(treated_outcomes)):
        if i < len(matches) and matches[i] >= 0 and matches[i] < len(control_outcomes_list):
            total += treated_outcomes[i] - control_outcomes_list[matches[i]]
            count += 1
    if count == 0:
        return 0.0
    return total / float(count)






def balance_check(features_treated, features_control):
    nt = len(features_treated)
    nc = len(features_control)
    if nt == 0 or nc == 0:
        return 0.0

    mean_t = 0.0
    for i in range(nt):
        mean_t += features_treated[i]
    mean_t /= float(nt)

    mean_c = 0.0
    for i in range(nc):
        mean_c += features_control[i]
    mean_c /= float(nc)

    var_t = 0.0
    for i in range(nt):
        diff = features_treated[i] - mean_t
        var_t += diff * diff
    if nt > 1:
        var_t /= float(nt - 1)

    var_c = 0.0
    for i in range(nc):
        diff = features_control[i] - mean_c
        var_c += diff * diff
    if nc > 1:
        var_c /= float(nc - 1)

    pooled_sd = math.sqrt((var_t + var_c) / 2.0)
    if pooled_sd < 1e-12:
        return 0.0
    return math.fabs(mean_t - mean_c) / pooled_sd






def propensity_overlap(scores, treatment):
    min_t = 1e18
    max_t = -1e18
    min_c = 1e18
    max_c = -1e18
    has_t = False
    has_c = False

    for i in range(len(scores)):
        if treatment[i] == 1:
            has_t = True
            if scores[i] < min_t:
                min_t = scores[i]
            if scores[i] > max_t:
                max_t = scores[i]
        else:
            has_c = True
            if scores[i] < min_c:
                min_c = scores[i]
            if scores[i] > max_c:
                max_c = scores[i]

    if not has_t or not has_c:
        return 0.0

    upper = max_t
    if max_c < upper:
        upper = max_c
    lower = min_t
    if min_c > lower:
        lower = min_c
    return upper - lower






def trimmed_sample(scores, treatment, lo, hi):
    indices = []
    for i in range(len(scores)):
        if scores[i] >= lo and scores[i] <= hi:
            indices.append(i)
    return indices






def stratified_estimate(outcomes, treatment, scores, n_strata):
    n = len(scores)
    if n == 0 or n_strata <= 0:
        return 0.0


    smin = scores[0]
    smax = scores[0]
    for i in range(1, n):
        if scores[i] < smin:
            smin = scores[i]
        if scores[i] > smax:
            smax = scores[i]

    width = (smax - smin) / float(n_strata)
    if width < 1e-12:

        sum_t = 0.0
        cnt_t = 0
        sum_c = 0.0
        cnt_c = 0
        for i in range(n):
            if treatment[i] == 1:
                sum_t += outcomes[i]
                cnt_t += 1
            else:
                sum_c += outcomes[i]
                cnt_c += 1
        if cnt_t == 0 or cnt_c == 0:
            return 0.0
        return sum_t / float(cnt_t) - sum_c / float(cnt_c)

    total_ate = 0.0
    strata_count = 0

    for s in range(n_strata):
        lo = smin + float(s) * width
        hi = lo + width
        if s == n_strata - 1:
            hi = smax + 1e-12  # Include the max value

        sum_t = 0.0
        cnt_t = 0
        sum_c = 0.0
        cnt_c = 0

        for i in range(n):
            if scores[i] >= lo and scores[i] < hi:
                if treatment[i] == 1:
                    sum_t += outcomes[i]
                    cnt_t += 1
                else:
                    sum_c += outcomes[i]
                    cnt_c += 1

        if cnt_t > 0 and cnt_c > 0:
            total_ate += sum_t / float(cnt_t) - sum_c / float(cnt_c)
            strata_count += 1

    if strata_count == 0:
        return 0.0
    return total_ate / float(strata_count)






def match_quality(matches):
    n = len(matches)
    if n == 0:
        return 0.0
    good = 0
    for i in range(n):
        if matches[i] >= 0:
            good += 1
    return float(good) / float(n)
