"""Python equivalent of mojo/engine/model_router.mojo (auto-generated)."""
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

def capability_match_score(request_task_embedding, model_task_embedding, model_max_context, request_context_len):
    task_sim = request_task_embedding * model_task_embedding
    if task_sim < 0.0:
        task_sim = 0.0
    context_ok = 1.0 if request_context_len <= model_max_context else 0.0
    return task_sim * context_ok



def model_load_score(active_requests, max_capacity, queue_depth):
    if max_capacity <= 0.0:
        return 1.0
    return (active_requests + queue_depth) / max_capacity



def fallback_trigger_score(primary_error_rate, primary_latency_p99, sla_latency_ms, error_threshold):
    error_pressure = (primary_error_rate - error_threshold) / (error_threshold + 1e-9)
    latency_pressure = (primary_latency_p99 - sla_latency_ms) / (sla_latency_ms + 1e-9)
    return error_pressure + latency_pressure



def ensemble_weight(model_accuracy, model_latency_ms, latency_budget_ms, total_model_accuracy):
    if total_model_accuracy <= 0.0:
        return 0.0
    feasible = 1.0 if model_latency_ms <= latency_budget_ms else 0.0
    return (model_accuracy / total_model_accuracy) * feasible



def hybrid_pipeline_stage_score(retrieval_relevance, generation_confidence, use_retrieval_threshold):
    retrieval_benefit = retrieval_relevance - generation_confidence
    return retrieval_benefit - use_retrieval_threshold



def model_selection_utility(model_quality, model_cost, user_quality_weight):
    return user_quality_weight * model_quality - (1.0 - user_quality_weight) * model_cost



def routing_uncertainty(top_model_score, second_model_score):
    total = top_model_score + second_model_score
    if total <= 0.0:
        return 0.0
    return (top_model_score - second_model_score) / total



def latency_tier_assignment(request_latency_budget_ms, tier_interactive_ms, tier_batch_ms):
    if request_latency_budget_ms <= tier_interactive_ms:
        return 0.0
    if request_latency_budget_ms <= tier_batch_ms:
        return 1.0
    return 2.0



def model_freshness_score(model_training_step, current_step, decay_half_life_steps):
    if decay_half_life_steps <= 0.0:
        return 1.0
    staleness = current_step - model_training_step
    if staleness < 0.0:
        staleness = 0.0
    return math.exp(-staleness * 0.693 / decay_half_life_steps)



def shadow_routing_fraction(shadow_experiment_budget, total_traffic, statistical_power_needed):
    if total_traffic <= 0.0:
        return 0.0
    needed_fraction = statistical_power_needed / total_traffic
    if needed_fraction > shadow_experiment_budget:
        return shadow_experiment_budget
    return needed_fraction
