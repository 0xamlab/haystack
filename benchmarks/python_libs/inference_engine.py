"""Python equivalent of mojo/engine/inference_engine.mojo (auto-generated)."""
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

def batch_padding_mask(token_pos, sequence_length):
    if token_pos < sequence_length:
        return 1.0
    return 0.0



def dynamic_batching_priority(wait_time, sequence_length, sla_deadline):
    if sequence_length <= 0.0 or sla_deadline <= 0.0:
        return wait_time
    urgency = 1.0 / sla_deadline
    return (wait_time / sequence_length) * urgency



def kv_cache_hit_ratio(cache_hits, total_requests):
    if total_requests <= 0.0:
        return 0.0
    return cache_hits / total_requests



def latency_percentile_estimate(mean_latency, std_latency, percentile):
    if percentile <= 0.0:
        return mean_latency
    if percentile >= 1.0:
        return mean_latency + 5.0 * std_latency
    z = -math.log(1.0 - percentile) * 1.2816  # approximation
    return mean_latency + z * std_latency



def throughput_tokens_per_sec(batch_size, tokens_per_request, latency_ms):
    if latency_ms <= 0.0:
        return 0.0
    return batch_size * tokens_per_request / (latency_ms / 1000.0)



def speculative_decode_accept_rate(draft_accepted, draft_tokens):
    if draft_tokens <= 0.0:
        return 0.0
    return draft_accepted / draft_tokens



def continuous_batching_capacity(gpu_memory_bytes, kv_cache_per_token_bytes, model_weights_bytes):
    if kv_cache_per_token_bytes <= 0.0:
        return 0.0
    available = gpu_memory_bytes - model_weights_bytes
    if available <= 0.0:
        return 0.0
    return available / kv_cache_per_token_bytes



def quantized_inference_speedup(fp32_flops, int8_throughput_ratio, memory_bandwidth_ratio):
    if int8_throughput_ratio < memory_bandwidth_ratio:
        return int8_throughput_ratio
    return memory_bandwidth_ratio



def prefill_time_estimate(n_tokens, n_layers, d_model, flops_per_second):
    if flops_per_second <= 0.0:
        return 0.0
    flops = 2.0 * n_tokens * n_layers * d_model * d_model * 4.0
    return flops / flops_per_second * 1000.0



def decode_time_per_token(n_layers, d_model, flops_per_second):
    if flops_per_second <= 0.0:
        return 0.0
    flops = 2.0 * n_layers * d_model * d_model * 4.0
    return flops / flops_per_second * 1000.0
