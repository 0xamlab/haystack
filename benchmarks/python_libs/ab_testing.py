"""Python equivalent of mojo/engine/ab_testing.mojo (auto-generated)."""
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

def _norm_cdf(x):
    t = 1.0 / (1.0 + 0.2316419 * math.fabs(x))
    d = 0.3989422804014327  # 1/math.sqrt(2*pi)
    p = d * math.exp(-x * x / 2.0) * (
        t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    )
    if x >= 0.0:
        return 1.0 - p
    return p



def _norm_ppf(p):
    if p <= 0.0:
        return -6.0
    if p >= 1.0:
        return 6.0
    if p == 0.5:
        return 0.0

    t = 0.0
    if p < 0.5:
        t = math.sqrt(-2.0 * math.log(p))
    else:
        t = math.sqrt(-2.0 * math.log(1.0 - p))


    c0 = 2.515517
    c1 = 0.802853
    c2 = 0.010328
    d1 = 1.432788
    d2 = 0.189269
    d3 = 0.001308

    result = t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)

    if p < 0.5:
        return -result
    return result






def sample_size_proportion(p1, p2, alpha=0.05, power=0.8):
    z_alpha = _norm_ppf(1.0 - alpha / 2.0)
    z_beta = _norm_ppf(power)
    p_bar = (p1 + p2) / 2.0
    diff = p2 - p1
    if math.fabs(diff) < 1e-15:
        return 1000000  # Infinite sample needed for zero effect
    numer = (z_alpha * math.sqrt(2.0 * p_bar * (1.0 - p_bar)) + z_beta * math.sqrt(p1 * (1.0 - p1) + p2 * (1.0 - p2)))
    n = (numer * numer) / (diff * diff)
    ni = int(n) + 1
    if ni < 1:
        ni = 1
    return ni






def z_test_proportions(successes_a, n_a, successes_b, n_b):
    p_a = float(successes_a) / float(n_a)
    p_b = float(successes_b) / float(n_b)
    p_pool = float(successes_a + successes_b) / float(n_a + n_b)
    se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / float(n_a) + 1.0 / float(n_b)))
    z = 0.0
    if se > 1e-15:
        z = (p_a - p_b) / se
    p_value = 2.0 * (1.0 - _norm_cdf(math.fabs(z)))
    result = []
    result.append(z)
    result.append(p_value)
    return result






def confidence_interval_proportion(successes, n, confidence=0.95):
    p_hat = float(successes) / float(n)
    z = _norm_ppf(1.0 - (1.0 - confidence) / 2.0)
    z2 = z * z
    nf = float(n)
    denom = 1.0 + z2 / nf
    center = (p_hat + z2 / (2.0 * nf)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1.0 - p_hat) / nf + z2 / (4.0 * nf * nf))
    result = []
    result.append(center - margin)
    result.append(center + margin)
    return result






def relative_uplift(control_rate, treatment_rate):
    if math.fabs(control_rate) < 1e-15:
        return 0.0
    return (treatment_rate - control_rate) / control_rate






def is_significant(p_value, alpha=0.05):
    return p_value < alpha






def power_analysis(effect_size, n, alpha=0.05):
    z_alpha = _norm_ppf(1.0 - alpha / 2.0)
    noncentrality = effect_size * math.sqrt(float(n) / 2.0)
    power_val = _norm_cdf(noncentrality - z_alpha) + _norm_cdf(-noncentrality - z_alpha)
    if power_val < 0.0:
        power_val = 0.0
    if power_val > 1.0:
        power_val = 1.0
    return power_val






def mde(n, baseline_rate, alpha=0.05, power=0.8):
    z_alpha = _norm_ppf(1.0 - alpha / 2.0)
    z_beta = _norm_ppf(power)
    se = math.sqrt(2.0 * baseline_rate * (1.0 - baseline_rate) / float(n))
    return (z_alpha + z_beta) * se






def sequential_test(successes_a, n_a, successes_b, n_b, alpha=0.05):
    result = z_test_proportions(successes_a, n_a, successes_b, n_b)
    z_stat = result[0]
    z_boundary = _norm_ppf(1.0 - alpha / 2.0)


    total = float(n_a + n_b)
    info_frac = total / (total + 100.0)  # Approximate info fraction
    adj_boundary = z_boundary / math.sqrt(info_frac)
    if adj_boundary < z_boundary:
        adj_boundary = z_boundary

    if z_stat > adj_boundary:
        return 1  # A wins (higher proportion)
    if z_stat < -adj_boundary:
        return 2  # B wins
    return 0  # Continue






def epsilon_greedy_select(rewards, counts, epsilon):
    n_arms = len(rewards)
    if n_arms == 0:
        return 0


    r = random_float64()
    if r < epsilon:

        arm_f = random_float64() * float(n_arms)
        arm = int(arm_f)
        if arm >= n_arms:
            arm = n_arms - 1
        return arm


    best_arm = 0
    best_mean = -1e18
    for i in range(n_arms):
        mean_r = 0.0
        if counts[i] > 0:
            mean_r = rewards[i] / float(counts[i])
        else:
            mean_r = 1e18  # Prefer unexplored arms
        if mean_r > best_mean:
            best_mean = mean_r
            best_arm = i
    return best_arm






def ucb1_select(rewards, counts, total):
    n_arms = len(rewards)
    if n_arms == 0:
        return 0


    for i in range(n_arms):
        if counts[i] == 0:
            return i

    best_arm = 0
    best_ucb = -1e18
    ln_total = math.log(float(total))

    for i in range(n_arms):
        mean_r = rewards[i] / float(counts[i])
        explore = math.sqrt(2.0 * ln_total / float(counts[i]))
        ucb = mean_r + explore
        if ucb > best_ucb:
            best_ucb = ucb
            best_arm = i
    return best_arm
