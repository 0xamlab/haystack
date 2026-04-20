"""Python equivalent of mojo/engine/scheduler_ops.mojo (auto-generated)."""
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

def priority_fair_score(priority, wait_time, base_priority_weight):
    return base_priority_weight * priority + wait_time



def weighted_fair_queue_credit(current_credit, weight, tick):
    return current_credit + weight * tick



def backpressure_load_factor(queue_depth, max_queue_depth):
    if max_queue_depth <= 0.0:
        return 1.0
    load = queue_depth / max_queue_depth
    if load > 1.0:
        return 1.0
    return load



def token_bucket_tokens(current_tokens, refill_rate, elapsed_ms, max_tokens):
    new_tokens = current_tokens + refill_rate * elapsed_ms
    if new_tokens > max_tokens:
        return max_tokens
    return new_tokens



def rate_limiter_wait_time(tokens_needed, current_tokens, refill_rate):
    deficit = tokens_needed - current_tokens
    if deficit <= 0.0:
        return 0.0
    if refill_rate <= 0.0:
        return 1e9
    return deficit / refill_rate



def work_stealing_threshold(local_queue_depth, remote_queue_depth, steal_ratio):
    if local_queue_depth <= 0.0 and remote_queue_depth > 0.0:
        return 1.0
    if local_queue_depth <= 0.0:
        return 0.0
    if remote_queue_depth / local_queue_depth > steal_ratio:
        return 1.0
    return 0.0



def request_timeout_score(elapsed_ms, timeout_ms, priority):
    if timeout_ms <= 0.0:
        return priority
    urgency = elapsed_ms / timeout_ms
    if urgency > 1.0:
        urgency = 1.0
    return priority * (1.0 + urgency * urgency)



def pipeline_stage_utilization(busy_time_ms, total_time_ms):
    if total_time_ms <= 0.0:
        return 0.0
    util = busy_time_ms / total_time_ms
    if util > 1.0:
        return 1.0
    return util



def latency_sla_headroom(sla_budget_ms, elapsed_ms, remaining_stages, avg_stage_latency_ms):
    remaining_budget = sla_budget_ms - elapsed_ms
    remaining_work = remaining_stages * avg_stage_latency_ms
    return remaining_budget - remaining_work



def exponential_backoff_delay(attempt, base_delay_ms, max_delay_ms, jitter):
    delay = base_delay_ms * math.exp(attempt * 0.6931471805599453)  # × 2^attempt
    if delay > max_delay_ms:
        delay = max_delay_ms
    return delay * (1.0 + jitter)
