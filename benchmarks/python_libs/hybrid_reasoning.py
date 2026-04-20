"""Python equivalent of mojo/engine/hybrid_reasoning.mojo (auto-generated)."""
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

def ml_simulation_blend(ml_prediction, simulation_output, ml_confidence):
    return ml_confidence * ml_prediction + (1.0 - ml_confidence) * simulation_output



def optimization_objective_gate(ml_feasibility_score, feasibility_threshold, objective_value):
    if ml_feasibility_score < feasibility_threshold:
        return objective_value * ml_feasibility_score
    return objective_value



def rule_violation_penalty(constraint_value, constraint_limit, penalty_coefficient):
    violation = constraint_value - constraint_limit
    if violation <= 0.0:
        return 0.0
    return penalty_coefficient * violation * violation



def simulation_rollout_value(immediate_reward, rollout_return, discount, ml_value_estimate, blend_weight):
    sim_value = immediate_reward + discount * rollout_return
    return blend_weight * sim_value + (1.0 - blend_weight) * ml_value_estimate



def ml_confidence_simulation_cost(ml_confidence, simulation_cost, expected_gain_from_simulation):
    return (1.0 - ml_confidence) * expected_gain_from_simulation - simulation_cost



def counterfactual_reasoning_score(factual_outcome, counterfactual_outcome, intervention_cost):
    return (counterfactual_outcome - factual_outcome) / (intervention_cost + 1.0)



def symbolic_constraint_score(predicate_value, lower_bound, upper_bound):
    if predicate_value >= lower_bound and predicate_value <= upper_bound:
        return 1.0
    dist_low = lower_bound - predicate_value
    dist_high = predicate_value - upper_bound
    dist = dist_low if dist_low > dist_high else dist_high
    return math.exp(-dist)



def reasoning_chain_coherence(step_confidence, n_steps, dependency_strength):
    if step_confidence <= 0.0:
        return 0.0
    base = step_confidence if step_confidence <= 1.0 else 1.0
    chain_prob = math.exp(n_steps * math.log(base + 1e-9))
    return chain_prob * dependency_strength



def hybrid_uncertainty_estimate(epistemic_uncertainty, aleatoric_uncertainty, model_disagreement):
    combined = math.sqrt(epistemic_uncertainty * epistemic_uncertainty +
                        aleatoric_uncertainty * aleatoric_uncertainty)
    return combined + model_disagreement



def meta_reasoning_switch(problem_complexity, time_budget_ms, ml_latency_ms, sim_latency_ms):
    if time_budget_ms < ml_latency_ms:
        return 0.0  # Only fast approximation fits
    if problem_complexity < 0.3:
        return 0.0  # Simple problem: ML only
    if time_budget_ms >= ml_latency_ms + sim_latency_ms and problem_complexity > 0.7:
        return 2.0  # Full simulation
    return 1.0  # Hybrid
