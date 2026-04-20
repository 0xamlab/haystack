"""Python equivalent of mojo/engine/rlhf_dpo.mojo (auto-generated)."""
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

def dpo_loss(log_ratio_chosen, log_ratio_rejected, beta):
    logit = beta * (log_ratio_chosen - log_ratio_rejected)
    return -math.log(1.0 / (1.0 + math.exp(-logit)))  # -log sigmoid



def ipo_loss(log_ratio_chosen, log_ratio_rejected, tau):
    diff = log_ratio_chosen - log_ratio_rejected - 1.0 / (2.0 * tau)
    return diff * diff



def orpo_ratio(chosen_log_prob, rejected_log_prob, chosen_seq_len, rejected_seq_len, lambda_orpo):
    log_odds_chosen = chosen_log_prob - math.log(1.0 - math.exp(chosen_log_prob) + 1e-10)
    log_odds_rejected = rejected_log_prob - math.log(1.0 - math.exp(rejected_log_prob) + 1e-10)
    log_ratio = log_odds_chosen - log_odds_rejected
    return -lambda_orpo * math.log(1.0 / (1.0 + math.exp(-log_ratio)))



def ppo_clip_objective(ratio, advantage, clip_eps):
    clipped_ratio = ratio
    if clipped_ratio > 1.0 + clip_eps:
        clipped_ratio = 1.0 + clip_eps
    if clipped_ratio < 1.0 - clip_eps:
        clipped_ratio = 1.0 - clip_eps
    obj1 = ratio * advantage
    obj2 = clipped_ratio * advantage
    if obj1 < obj2:
        return obj1
    return obj2



def reward_model_score(chosen_logit, rejected_logit):
    diff = chosen_logit - rejected_logit
    return -math.log(1.0 / (1.0 + math.exp(-diff)))



def kl_penalty_term(log_prob_policy, log_prob_reference, beta):
    return beta * (log_prob_policy - log_prob_reference)



def advantage_gae(reward, value_current, value_next, gamma, lam, prev_gae):
    delta = reward + gamma * value_next - value_current
    return delta + gamma * lam * prev_gae



def grpo_group_advantage(reward, group_mean, group_std):
    if group_std <= 0.0:
        return reward - group_mean
    return (reward - group_mean) / group_std



def sft_loss_token(log_prob):
    return -log_prob



def preference_margin_loss(chosen_reward, rejected_reward, margin):
    gap = chosen_reward - rejected_reward
    loss = margin - gap
    if loss < 0.0:
        return 0.0
    return loss
