"""Python equivalent of mojo/engine/latency_optimizer.mojo (auto-generated)."""
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

def early_exit_confidence(intermediate_logit_entropy, exit_threshold, layer_depth_fraction):
    entropy_margin = exit_threshold - intermediate_logit_entropy
    return entropy_margin * layer_depth_fraction



def adaptive_depth_score(token_difficulty, available_compute_budget, full_model_compute):
    if full_model_compute <= 0.0:
        return 1.0
    budget_fraction = available_compute_budget / full_model_compute
    depth = token_difficulty * budget_fraction
    if depth > 1.0:
        return 1.0
    return depth



def prefill_decode_split_latency(prefill_tokens, decode_tokens, prefill_throughput_tps, decode_throughput_tps):
    prefill_time = 0.0
    decode_time = 0.0
    if prefill_throughput_tps > 0.0:
        prefill_time = prefill_tokens / prefill_throughput_tps
    if decode_throughput_tps > 0.0:
        decode_time = decode_tokens / decode_throughput_tps
    return prefill_time + decode_time



def async_speculation_gain(accepted_tokens, total_speculated, speculation_overhead):
    return accepted_tokens - speculation_overhead * total_speculated



def token_streaming_headroom(buffer_tokens, generation_rate_tps, consumption_rate_tps):
    net_rate = generation_rate_tps - consumption_rate_tps
    if net_rate <= 0.0:
        if consumption_rate_tps <= 0.0:
            return 1e9
        return buffer_tokens / consumption_rate_tps
    return buffer_tokens / consumption_rate_tps + net_rate



def layer_skip_quality_cost(layer_importance_score, n_skipped_layers, model_depth):
    if model_depth <= 0.0:
        return 0.0
    skip_fraction = n_skipped_layers / model_depth
    return layer_importance_score * skip_fraction * skip_fraction



def partial_forward_savings(full_forward_flops, partial_forward_flops, quality_degradation, quality_threshold):
    if quality_degradation > quality_threshold:
        return 0.0
    return full_forward_flops - partial_forward_flops



def kv_prefetch_overlap(decode_step_latency_ms, kv_load_latency_ms):
    if decode_step_latency_ms <= 0.0:
        return 0.0
    overlap = decode_step_latency_ms - kv_load_latency_ms
    if overlap <= 0.0:
        return 0.0
    fraction = overlap / decode_step_latency_ms
    if fraction > 1.0:
        return 1.0
    return fraction



def attention_skip_score(layer_attention_entropy, skip_entropy_threshold, positional_importance):
    return (skip_entropy_threshold - layer_attention_entropy) * positional_importance



def output_caching_hit_benefit(cache_hit_rate, full_generation_latency_ms, cache_lookup_latency_ms):
    return cache_hit_rate * (full_generation_latency_ms - cache_lookup_latency_ms)
