"""Python equivalent of mojo/engine/execution_planner.mojo (auto-generated)."""
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

def fusion_opportunity_score(op_a_flops, op_b_flops, memory_traffic_saved):
    total_flops = op_a_flops + op_b_flops
    if total_flops <= 0.0:
        return 0.0
    return memory_traffic_saved / total_flops



def device_placement_score(op_arithmetic_intensity, device_ridge_point, device_peak_flops):
    if device_ridge_point <= 0.0:
        return 0.0
    utilization = op_arithmetic_intensity / device_ridge_point
    if utilization > 1.0:
        utilization = 1.0
    return utilization * device_peak_flops



def kv_policy_eviction_priority(last_access_step, current_step, attention_score, seq_remaining):
    staleness = current_step - last_access_step + 1.0
    return attention_score * seq_remaining / staleness



def batching_strategy_score(request_latency_budget_ms, current_batch_size, throughput_gain_per_request, latency_cost_per_request):
    if latency_cost_per_request >= request_latency_budget_ms:
        return -1.0
    return throughput_gain_per_request - latency_cost_per_request / request_latency_budget_ms



def scheduling_priority_score(queue_wait_ms, sla_budget_ms, request_value, estimated_compute_ms):
    if sla_budget_ms <= 0.0 or estimated_compute_ms <= 0.0:
        return 0.0
    urgency = (queue_wait_ms + 1.0) / sla_budget_ms
    return urgency * request_value / estimated_compute_ms



def prefetch_benefit_estimate(weight_bytes, bandwidth_bytes_per_ms, compute_ms_until_needed):
    if bandwidth_bytes_per_ms <= 0.0 or compute_ms_until_needed <= 0.0:
        return 0.0
    load_time_ms = weight_bytes / bandwidth_bytes_per_ms
    benefit = (compute_ms_until_needed - load_time_ms) / compute_ms_until_needed
    if benefit < 0.0:
        return 0.0
    if benefit > 1.0:
        return 1.0
    return benefit



def graph_rewrite_gain(original_flops, rewritten_flops, original_memory, rewritten_memory, flop_weight):
    flop_gain = 0.0
    mem_gain = 0.0
    if original_flops > 0.0:
        flop_gain = 1.0 - rewritten_flops / original_flops
    if original_memory > 0.0:
        mem_gain = 1.0 - rewritten_memory / original_memory
    return flop_weight * flop_gain + (1.0 - flop_weight) * mem_gain



def memory_placement_affinity(access_frequency, tensor_bytes, tier_bandwidth, tier_capacity):
    if tensor_bytes <= 0.0 or tier_capacity <= 0.0:
        return 0.0
    return access_frequency * tier_bandwidth / (tensor_bytes * tier_capacity)



def pipeline_depth_optimal(stage_latency_ms, bubble_fraction, n_microbatches):
    if stage_latency_ms <= 0.0:
        return 0.0
    useful = 1.0 - bubble_fraction
    if useful < 0.0:
        useful = 0.0
    return useful * n_microbatches / stage_latency_ms



def adaptive_batch_size(current_batch, gpu_utilization, target_utilization, max_batch, adjust_rate):
    error = target_utilization - gpu_utilization
    new_batch = current_batch + adjust_rate * error * current_batch
    if new_batch < 1.0:
        return 1.0
    if new_batch > max_batch:
        return max_batch
    return new_batch
