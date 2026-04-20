"""Python equivalent of mojo/engine/observability.mojo (auto-generated)."""
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

def p99_latency_estimate(mean_latency, std_latency):
    return mean_latency + 2.326 * std_latency



def memory_pressure_score(used_bytes, total_bytes, fragmentation):
    if total_bytes <= 0.0:
        return 1.0
    util = used_bytes / total_bytes
    if util > 1.0:
        util = 1.0
    score = util + fragmentation * 0.2
    if score > 1.0:
        return 1.0
    return score



def token_throughput_ema(current_ema, new_tokens, elapsed_ms, alpha):
    if elapsed_ms <= 0.0:
        return current_ema
    new_rate = new_tokens / elapsed_ms * 1000.0
    return alpha * new_rate + (1.0 - alpha) * current_ema



def cache_miss_rate(total_accesses, cache_misses):
    if total_accesses <= 0.0:
        return 0.0
    return cache_misses / total_accesses



def batch_queue_wait_percentile(mean_wait, std_wait, percentile):
    if percentile <= 0.0:
        return 0.0
    if percentile >= 1.0:
        return mean_wait + 4.0 * std_wait
    z = -math.log(1.0 - percentile + 1e-10) * 1.2816
    return mean_wait + z * std_wait



def gpu_utilization_rolling(current_util, new_sample, alpha):
    return alpha * new_sample + (1.0 - alpha) * current_util



def request_success_rate(successes, total_requests):
    if total_requests <= 0.0:
        return 1.0
    return successes / total_requests



def model_drift_alert_score(psi_score, accuracy_drop, calibration_ece):
    return 0.4 * psi_score + 0.4 * accuracy_drop + 0.2 * calibration_ece



def cost_per_token_rolling(current_cpt, new_cost, new_tokens, alpha):
    if new_tokens <= 0.0:
        return current_cpt
    new_rate = new_cost / new_tokens
    return alpha * new_rate + (1.0 - alpha) * current_cpt



def health_check_score(memory_pressure, gpu_util, error_rate, queue_depth_ratio):
    issues = 0.3 * memory_pressure + 0.4 * error_rate + 0.3 * queue_depth_ratio
    health = 1.0 - issues
    if health < 0.0:
        return 0.0
    return health
