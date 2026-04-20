"""Python equivalent of mojo/engine/paged_kv_cache.mojo (auto-generated)."""
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

def page_table_lookup(virtual_block_id, page_table_entry):
    return page_table_entry



def cache_compaction_gain(fragmented_blocks, block_size_tokens, dtype_bytes, n_layers, n_heads, head_dim):
    bytes_per_block = block_size_tokens * n_layers * n_heads * head_dim * dtype_bytes * 2.0
    return fragmented_blocks * bytes_per_block * 0.5  # avg 50% wasted per block



def prefix_sharing_savings(shared_prefix_tokens, n_sequences, n_layers, n_heads, head_dim, dtype_bytes):
    prefix_bytes = 2.0 * shared_prefix_tokens * n_layers * n_heads * head_dim * dtype_bytes
    if n_sequences <= 1.0:
        return 0.0
    return (n_sequences - 1.0) * prefix_bytes



def speculative_branch_memory(n_branches, speculation_depth, n_layers, n_heads, head_dim, dtype_bytes):
    return n_branches * speculation_depth * n_layers * n_heads * head_dim * dtype_bytes * 2.0



def cache_eviction_lru_score(last_access_step, current_step):
    return current_step - last_access_step



def cache_eviction_beladys_score(next_access_step, current_step):
    if next_access_step < current_step:
        return 1e9  # Never accessed again → evict
    return next_access_step - current_step



def block_copy_cost(block_size_tokens, n_layers, n_heads, head_dim, dtype_bytes, bandwidth_gbs):
    block_bytes = 2.0 * block_size_tokens * n_layers * n_heads * head_dim * dtype_bytes
    if bandwidth_gbs <= 0.0:
        return 0.0
    return block_bytes / (bandwidth_gbs * 1e9) * 1000.0



def cache_hit_latency_saving(prompt_tokens, prefill_throughput_tps):
    if prefill_throughput_tps <= 0.0:
        return 0.0
    return prompt_tokens / prefill_throughput_tps



def dynamic_ntk_rope_scale(seq_len, base_context, alpha):
    if base_context <= 0.0:
        return 1.0
    ratio = seq_len / base_context
    if ratio <= 1.0:
        return 1.0
    return math.exp(alpha * math.log(ratio))



def context_extension_factor(original_max_len, target_max_len):
    if original_max_len <= 0.0:
        return 1.0
    return target_max_len / original_max_len
