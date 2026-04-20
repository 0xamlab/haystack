"""Python equivalent of mojo/engine/workflow_engine.mojo (auto-generated)."""
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

def dag_node_ready_score(n_dependencies, n_completed_dependencies, blocked_by_resource):
    if blocked_by_resource > 0.5:
        return 0.0
    if n_dependencies <= 0.0:
        return 1.0
    if n_completed_dependencies >= n_dependencies:
        return 1.0
    return 0.0



def retry_backoff_delay(attempt_number, base_delay_ms, max_delay_ms, jitter_factor):
    delay = base_delay_ms * math.exp(attempt_number * 0.693)  # 2^attempt
    if delay > max_delay_ms:
        delay = max_delay_ms
    return delay * (1.0 + jitter_factor * 0.5)



def conditional_branch_score(condition_probability, branch_value, branch_cost):
    return condition_probability * branch_value - branch_cost



def pipeline_stage_throughput(stage_compute_ms, stage_io_ms, parallelism):
    bottleneck = stage_compute_ms if stage_compute_ms > stage_io_ms else stage_io_ms
    if bottleneck <= 0.0:
        return parallelism
    return parallelism / bottleneck



def workflow_completion_fraction(completed_nodes, total_nodes, failed_nodes):
    if total_nodes <= 0.0:
        return 1.0
    return (completed_nodes - failed_nodes) / total_nodes



def step_timeout_remaining_ms(step_start_ms, current_ms, timeout_budget_ms):
    elapsed = current_ms - step_start_ms
    return timeout_budget_ms - elapsed



def dependency_resolution_order(n_downstream_nodes, critical_path_length, node_compute_cost):
    if node_compute_cost <= 0.0:
        return n_downstream_nodes * critical_path_length
    return n_downstream_nodes * critical_path_length / node_compute_cost



def parallel_step_efficiency(sequential_time_ms, parallel_time_ms, n_workers):
    if parallel_time_ms <= 0.0 or n_workers <= 0.0:
        return 1.0
    return sequential_time_ms / (parallel_time_ms * n_workers)



def workflow_cost_accumulator(previous_cost, step_compute_cost, step_io_cost, step_api_cost):
    return previous_cost + step_compute_cost + step_io_cost + step_api_cost



def chain_output_compatibility(output_schema_version, next_step_schema_version, output_type_code, expected_type_code):
    type_match = 1.0 if output_type_code == expected_type_code else 0.0
    version_diff = output_schema_version - next_step_schema_version
    if version_diff < 0.0:
        version_diff = -version_diff
    version_compat = math.exp(-version_diff)
    return type_match * version_compat
