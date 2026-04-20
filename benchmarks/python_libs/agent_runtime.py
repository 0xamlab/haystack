"""Python equivalent of mojo/engine/agent_runtime.mojo (auto-generated)."""
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

def tool_call_cost_estimate(tool_latency_ms, input_tokens, output_tokens, cost_per_1k_tokens):
    token_cost = (input_tokens + output_tokens) * cost_per_1k_tokens / 1000.0
    latency_cost = tool_latency_ms / 1000.0  # seconds as proxy
    return token_cost + latency_cost * 0.001  # weight latency



def retry_should_attempt(attempt, max_attempts, last_error_type):
    if attempt >= max_attempts:
        return 0.0
    if last_error_type >= 2.0:
        return 0.0
    return 1.0



def plan_step_dependency_ready(completed_steps_mask, required_steps_mask):

    covered = float(Int64(completed_steps_mask) & Int64(required_steps_mask))
    if covered == required_steps_mask:
        return 1.0
    return 0.0



def action_value_estimate(immediate_reward, future_value, discount, steps_remaining):
    return immediate_reward + math.exp(steps_remaining * math.log(discount if discount > 0.0 else 1e-300)) * future_value



def tool_selection_score(tool_relevance, tool_cost, tool_reliability):
    denom = tool_cost + 1e-6
    return tool_relevance * tool_reliability / denom



def memory_retrieval_relevance(query_embed_dot, query_norm, memory_norm, recency_weight):
    denom = query_norm * memory_norm
    if denom <= 0.0:
        return 0.0
    return (query_embed_dot / denom) * recency_weight



def context_window_budget(max_tokens, used_tokens, reserved_output_tokens):
    remaining = max_tokens - used_tokens - reserved_output_tokens
    if remaining < 0.0:
        return 0.0
    return remaining



def agent_step_reward(goal_progress, step_cost, constraint_violation, penalty):
    return goal_progress - step_cost - constraint_violation * penalty



def structured_output_match(output_schema_hash, actual_output_hash):
    if output_schema_hash == actual_output_hash:
        return 1.0
    return 0.0



def agent_cost_budget_remaining(total_budget, spent_tokens, spent_tool_calls, cost_per_token, cost_per_tool_call):
    spent = spent_tokens * cost_per_token + spent_tool_calls * cost_per_tool_call
    remaining = total_budget - spent
    if remaining < 0.0:
        return 0.0
    return remaining
