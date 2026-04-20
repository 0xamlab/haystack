"""Python equivalent of mojo/engine/data_feedback_loop.mojo (auto-generated)."""
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

def sample_informativeness(prediction_entropy, model_uncertainty, diversity_from_existing):
    return prediction_entropy * model_uncertainty * diversity_from_existing



def auto_label_confidence(teacher_model_logprob, label_agreement_rate, sample_difficulty):
    if sample_difficulty <= 0.0:
        return math.exp(teacher_model_logprob)
    return math.exp(teacher_model_logprob) * label_agreement_rate / sample_difficulty



def data_drift_detection_score(current_feature_mean, baseline_feature_mean, baseline_feature_std):
    if baseline_feature_std <= 0.0:
        return 0.0
    diff = current_feature_mean - baseline_feature_mean
    if diff < 0.0:
        diff = -diff
    return diff / baseline_feature_std



def retraining_trigger_score(performance_degradation, drift_score, data_volume_new, retrain_cost):
    benefit = performance_degradation * 10.0 + drift_score + math.log(data_volume_new + 1.0)
    return benefit - retrain_cost



def dataset_freshness_score(newest_sample_age_days, half_life_days):
    if half_life_days <= 0.0:
        return 1.0
    return math.exp(-newest_sample_age_days * 0.693 / half_life_days)



def annotation_effort_estimate(n_samples, avg_annotation_time_s, review_fraction):
    return n_samples * avg_annotation_time_s * (1.0 + review_fraction)



def deployment_readiness_score(validation_accuracy, accuracy_threshold, bias_score, bias_threshold, safety_score):
    acc_ok = 1.0 if validation_accuracy >= accuracy_threshold else 0.0
    bias_ok = 1.0 if bias_score <= bias_threshold else 0.0
    return acc_ok * bias_ok * safety_score



def online_evaluation_stat(treatment_metric, control_metric, pooled_std, n_samples):
    if pooled_std <= 0.0 or n_samples <= 0.0:
        return 0.0
    return (treatment_metric - control_metric) / (pooled_std / math.sqrt(n_samples))



def feedback_signal_quality(explicit_feedback_rate, implicit_signal_rate, label_noise_estimate):
    signal = explicit_feedback_rate * 0.7 + implicit_signal_rate * 0.3
    return signal * (1.0 - label_noise_estimate)



def continuous_learning_rate(base_lr, drift_magnitude, catastrophic_forgetting_risk):
    drift_boost = 1.0 + drift_magnitude
    forgetting_penalty = 1.0 - catastrophic_forgetting_risk * 0.9
    return base_lr * drift_boost * forgetting_penalty
