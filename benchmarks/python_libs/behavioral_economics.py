"""Python equivalent of mojo/engine/behavioral_economics.mojo (auto-generated)."""
import math
import random as _rng

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

def prospect_theory_value(x, alpha, lambda_loss):
    if x >= 0.0:
        if x < 1e-30:
            return 0.0
        return math.exp(alpha * math.log(x))
    else:
        abs_x = math.fabs(x)
        if abs_x < 1e-30:
            return 0.0
        return -lambda_loss * math.exp(alpha * math.log(abs_x))






def probability_weighting(p, gamma):
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    if gamma <= 0.0:
        return p
    p_g = math.exp(gamma * math.log(p))
    q_g = math.exp(gamma * math.log(1.0 - p))
    denom = p_g + q_g
    if math.fabs(denom) < 1e-30:
        return p
    denom_pow = math.exp((1.0 / gamma) * math.log(denom))
    if math.fabs(denom_pow) < 1e-30:
        return p
    return p_g / denom_pow






def hyperbolic_discount(value, k, delay):
    return value / (1.0 + k * delay)






def quasi_hyperbolic_discount(value, beta, delta, period):
    if period <= 0.0:
        return value
    if delta <= 0.0:
        return 0.0
    return beta * math.exp(period * math.log(delta)) * value






def anchoring_adjusted_estimate(anchor, adjustment, adjustment_factor):
    return anchor + adjustment * adjustment_factor






def endowment_effect_wta_wtp_ratio(wta, wtp):
    if math.fabs(wtp) < 1e-30:
        return 0.0
    return wta / wtp






def loss_aversion_coefficient(loss_impact, gain_impact):
    if math.fabs(gain_impact) < 1e-30:
        return 0.0
    return math.fabs(loss_impact) / gain_impact






def mental_accounting_total(gains, losses):
    return gains + losses






def status_quo_bias(switching_cost, switching_benefit):
    return switching_cost - switching_benefit






def sunk_cost_ratio(sunk, total_budget):
    if math.fabs(total_budget) < 1e-30:
        return 0.0
    return sunk / total_budget






def fairness_ultimatum_threshold(offer, total):
    if math.fabs(total) < 1e-30:
        return 0.0
    return offer / total * 100.0






def nudge_effectiveness(treated_rate, control_rate):
    return treated_rate - control_rate
