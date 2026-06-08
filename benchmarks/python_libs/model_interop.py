"""Python equivalent of mojo/engine/model_interop.mojo (auto-generated)."""
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

def safetensors_tensor_offset(prev_tensor_bytes, alignment):
    if alignment <= 0.0:
        return prev_tensor_bytes
    remainder = prev_tensor_bytes - float(int(prev_tensor_bytes / alignment)) * alignment
    if remainder == 0.0:
        return prev_tensor_bytes
    return prev_tensor_bytes + (alignment - remainder)



def gguf_kv_metadata_size(key_len, value_type, value_count):
    base = key_len + 4.0  # key + type tag
    if value_type == 2.0:
        return base + 8.0 * value_count  # string: 8B len + chars
    if value_type == 3.0:
        return base + value_count  # bool: 1B each
    return base + 4.0 * value_count  # int32/float32: 4B each



def onnx_node_flops(op_type, batch, m, n, k):
    if op_type == 1.0:
        return 2.0 * batch * m * n * k
    if op_type == 2.0:
        return 2.0 * batch * m * n * k * 9.0  # conv with 3×3 kernel approx
    if op_type == 3.0:
        return 5.0 * batch * m * n
    if op_type == 4.0:
        return 5.0 * batch * m * n
    return batch * m * n



def hf_config_head_dim(hidden_size, num_attention_heads):
    if num_attention_heads <= 0.0:
        return hidden_size
    return hidden_size / num_attention_heads



def hf_rope_theta_scale(base_theta, rope_scaling_factor):
    return base_theta * rope_scaling_factor



def dtype_convert_scale(src_max, dst_max):
    if src_max <= 0.0:
        return 1.0
    return dst_max / src_max



def checkpoint_version_compat(model_version, checkpoint_version):
    diff = model_version - checkpoint_version
    if diff < 0.0:
        diff = -diff
    if diff == 0.0:
        return 1.0
    return 1.0 / (1.0 + diff)



def weight_remap_cost(n_tensors_to_remap, avg_tensor_elements, remap_overhead_factor):
    return n_tensors_to_remap * avg_tensor_elements * remap_overhead_factor



def tokenizer_vocab_overlap(vocab_a_size, vocab_b_size, shared_tokens):
    union_size = vocab_a_size + vocab_b_size - shared_tokens
    if union_size <= 0.0:
        return 0.0
    return shared_tokens / union_size



def model_card_perplexity(log_likelihood_sum, n_tokens):
    if n_tokens <= 0.0:
        return 1e9
    return math.exp(-log_likelihood_sum / n_tokens)
