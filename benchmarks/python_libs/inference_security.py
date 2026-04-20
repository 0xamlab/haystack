"""Python equivalent of mojo/engine/inference_security.mojo (auto-generated)."""
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

def prompt_injection_score(instruction_override_tokens, system_prompt_distance, role_switch_probability):
    return instruction_override_tokens * role_switch_probability / (system_prompt_distance + 1.0)



def token_level_safety_score(token_harm_logit, context_harm_factor, refusal_trained_weight):
    raw_harm = math.exp(token_harm_logit) * context_harm_factor
    return raw_harm * (1.0 - refusal_trained_weight)



def tool_call_validation_score(arg_type_match, arg_range_valid, permission_granted, rate_limit_ok):
    return arg_type_match * arg_range_valid * permission_granted * rate_limit_ok



def data_leakage_risk_score(token_memorization_score, training_data_similarity, privacy_sensitivity):
    return token_memorization_score * training_data_similarity * privacy_sensitivity



def jailbreak_pattern_score(roleplay_frame_depth, hypothetical_nesting, constraint_negation_count):
    return (roleplay_frame_depth * 0.4 + hypothetical_nesting * 0.3 +
            constraint_negation_count * 0.3)



def output_toxicity_estimate(toxicity_classifier_logit, generation_temperature, safety_steering_strength):
    base_toxicity = 1.0 / (1.0 + math.exp(-toxicity_classifier_logit))
    temperature_amplification = 1.0 + (generation_temperature - 1.0) * 0.2
    steered = base_toxicity * temperature_amplification * (1.0 - safety_steering_strength)
    if steered < 0.0:
        return 0.0
    if steered > 1.0:
        return 1.0
    return steered



def pii_token_risk(token_pii_classifier_prob, context_pii_density, user_consent_level):
    return token_pii_classifier_prob * context_pii_density * (1.0 - user_consent_level)



def sandboxed_exec_trust_score(tool_signature_valid, execution_timeout_ok, resource_limit_ok, output_schema_valid):
    return tool_signature_valid * execution_timeout_ok * resource_limit_ok * output_schema_valid



def rate_limit_violation_score(requests_in_window, rate_limit, window_fraction_elapsed):
    if rate_limit <= 0.0:
        return 1.0
    projected = requests_in_window / (window_fraction_elapsed + 1e-6)
    return (projected - rate_limit) / rate_limit



def adversarial_input_score(input_perplexity, baseline_perplexity, perturbation_budget):
    if baseline_perplexity <= 0.0:
        return 0.0
    ppl_ratio = input_perplexity / baseline_perplexity
    return (ppl_ratio - 1.0) * (1.0 + perturbation_budget)
