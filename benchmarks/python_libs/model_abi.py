"""Python equivalent of mojo/engine/model_abi.mojo (auto-generated)."""
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

def tensor_layout_stride(dim_size, element_size_bytes, outer_stride):
    return outer_stride * dim_size * element_size_bytes



def dtype_byte_width(dtype_code):
    if dtype_code == 0.0:
        return 4.0  # fp32
    if dtype_code == 1.0:
        return 2.0  # fp16
    if dtype_code == 2.0:
        return 2.0  # bf16
    if dtype_code == 3.0:
        return 1.0  # int8
    if dtype_code == 4.0:
        return 0.5  # int4 (packed)
    if dtype_code == 5.0:
        return 8.0  # fp64
    return 4.0  # default fp32



def attention_head_dim(model_dim, n_heads):
    if n_heads <= 0.0:
        return model_dim
    return model_dim / n_heads



def rope_theta_scale(base_theta, original_context, target_context):
    if original_context <= 0.0:
        return base_theta
    scale_ratio = target_context / original_context
    return base_theta * scale_ratio * scale_ratio



def weight_shard_offset(shard_index, shard_size_bytes, header_bytes):
    return header_bytes + shard_index * shard_size_bytes



def activation_layout_index(n, c, h, w, c_size, h_size, w_size, is_nhwc):
    if is_nhwc > 0.5:
        return n * h_size * w_size * c_size + h * w_size * c_size + w * c_size + c
    return n * c_size * h_size * w_size + c * h_size * w_size + h * w_size + w



def model_config_head_count(model_dim, head_dim):
    if head_dim <= 0.0:
        return 1.0
    return model_dim / head_dim



def kv_head_group_size(n_query_heads, n_kv_heads):
    if n_kv_heads <= 0.0:
        return n_query_heads
    return n_query_heads / n_kv_heads



def ffn_dim_from_model_dim(model_dim, ffn_multiplier, round_to):
    raw = model_dim * ffn_multiplier
    if round_to <= 0.0:
        return raw
    return float(int(raw / round_to) + 1) * round_to



def abi_version_compatible(model_abi_version, runtime_abi_version, breaking_version_threshold):
    diff = runtime_abi_version - model_abi_version
    if diff < 0.0:
        diff = -diff
    if diff >= breaking_version_threshold:
        return 0.0
    return 1.0
