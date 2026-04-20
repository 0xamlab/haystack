"""Python equivalent of mojo/engine/stateful_runtime.mojo (auto-generated)."""
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

def session_memory_relevance(memory_embedding, query_embedding, recency_weight, access_count):
    sim = memory_embedding * query_embedding
    if sim < 0.0:
        sim = 0.0
    return sim * recency_weight * math.log(1.0 + access_count)



def memory_decay_score(memory_strength, elapsed_steps, decay_rate):
    return memory_strength * math.exp(-decay_rate * elapsed_steps)



def state_transition_validity(from_state, to_state, n_states, transition_mask_bit):
    if from_state < 0.0 or to_state < 0.0:
        return 0.0
    if from_state >= n_states or to_state >= n_states:
        return 0.0
    return transition_mask_bit



def replay_buffer_priority(td_error, priority_alpha, max_priority):
    abs_error = td_error if td_error >= 0.0 else -td_error
    priority = math.exp(priority_alpha * math.log(abs_error + 1e-6))
    if priority > max_priority:
        return max_priority
    return priority



def memory_consolidation_score(access_frequency, memory_importance, short_term_capacity_pressure):
    return memory_importance * access_frequency * (1.0 + short_term_capacity_pressure) - 1.0



def working_memory_capacity_used(active_tokens, context_window, reserved_output_tokens):
    usable = context_window - reserved_output_tokens
    if usable <= 0.0:
        return 1.0
    used = active_tokens / usable
    if used > 1.0:
        return 1.0
    return used



def long_term_retrieval_score(semantic_similarity, temporal_relevance, importance_weight):
    return semantic_similarity * 0.5 + temporal_relevance * 0.3 + importance_weight * 0.2



def state_compression_ratio(raw_state_bytes, compressed_state_bytes):
    if compressed_state_bytes <= 0.0:
        return 1.0
    return raw_state_bytes / compressed_state_bytes



def replayability_score(deterministic_ops_fraction, external_state_captured, rng_seed_fixed):
    return deterministic_ops_fraction * external_state_captured * (0.5 + 0.5 * rng_seed_fixed)



def session_continuity_score(overlap_tokens, session_chunk_tokens, context_coverage):
    if session_chunk_tokens <= 0.0:
        return 1.0
    overlap_ratio = overlap_tokens / session_chunk_tokens
    if overlap_ratio > 1.0:
        overlap_ratio = 1.0
    return 0.5 * overlap_ratio + 0.5 * context_coverage
