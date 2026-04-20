"""Python equivalent of mojo/engine/training_stability.mojo (auto-generated)."""
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
try:
    from std.math import cos
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

def loss_scale_adjust(current_scale, overflow_occurred, scale_up_factor, scale_down_factor, growth_interval, steps_since_overflow):
    if overflow_occurred > 0.5:
        return current_scale / scale_down_factor
    if steps_since_overflow >= growth_interval:
        return current_scale * scale_up_factor
    return current_scale



def is_finite_check(value):
    if value != value:
        return 0.0
    abs_val = value if value >= 0.0 else -value
    if abs_val > 1e308:
        return 0.0
    return 1.0



def gradient_accumulation_step(accumulated_grad, new_grad, accumulation_steps):
    if accumulation_steps <= 0.0:
        return accumulated_grad + new_grad
    return accumulated_grad + new_grad / accumulation_steps



def warmup_lr_schedule(step, warmup_steps, target_lr):
    if warmup_steps <= 0.0:
        return target_lr
    ratio = step / warmup_steps
    if ratio > 1.0:
        return target_lr
    return target_lr * ratio



def cosine_warmup_schedule(step, warmup_steps, total_steps, lr_max, lr_min):
    pi = 3.141592653589793
    if step <= warmup_steps:
        if warmup_steps <= 0.0:
            return lr_max
        return lr_max * step / warmup_steps
    decay_steps = total_steps - warmup_steps
    if decay_steps <= 0.0:
        return lr_min
    t = step - warmup_steps
    return lr_min + 0.5 * (lr_max - lr_min) * (1.0 + math.cos(pi * t / decay_steps))



def ema_weight_update(ema_param, model_param, decay):
    return decay * ema_param + (1.0 - decay) * model_param



def overflow_skip_step(has_overflow, optimizer_step_count):
    if has_overflow > 0.5:
        return optimizer_step_count  # Skip this step
    return optimizer_step_count + 1.0



def grad_norm_finite(grad_norm, max_allowed):
    if grad_norm != grad_norm:
        return 0.0
    if grad_norm > 1e8:
        return 0.0
    if grad_norm > max_allowed:
        return 0.0
    return 1.0



def loss_spike_detector(current_loss, running_mean, spike_threshold):
    if running_mean <= 0.0:
        return 0.0
    if current_loss / running_mean > spike_threshold:
        return 1.0
    return 0.0



def training_step_budget(compute_budget_flops, flops_per_step):
    if flops_per_step <= 0.0:
        return 0.0
    return compute_budget_flops / flops_per_step
