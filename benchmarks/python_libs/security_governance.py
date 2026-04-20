"""Python equivalent of mojo/engine/security_governance.mojo (auto-generated)."""
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

def model_provenance_hash(weight_hash, config_hash, dataset_hash, step):
    p1 = 1000003.0
    p2 = 999983.0
    return weight_hash * p1 + config_hash * p2 + dataset_hash + step



def prompt_policy_score(toxicity_signal, jailbreak_signal, pii_signal):
    score = 0.4 * toxicity_signal + 0.4 * jailbreak_signal + 0.2 * pii_signal
    if score > 1.0:
        return 1.0
    return score



def output_safety_score(toxicity, hallucination_risk, factual_consistency):
    score = 0.5 * toxicity + 0.3 * hallucination_risk + 0.2 * (1.0 - factual_consistency)
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score



def tenant_quota_remaining(quota_tokens, used_tokens, quota_period_ms, elapsed_ms):
    remaining = quota_tokens - used_tokens
    if remaining < 0.0:
        return 0.0
    return remaining



def audit_log_hash(prev_hash, event_type, timestamp, tenant_id):
    prime = 1000003.0
    return prev_hash * prime + event_type * 997.0 + timestamp + tenant_id



def pii_sensitivity_score(n_email_matches, n_phone_matches, n_ssn_matches, n_credit_card_matches):
    score = (n_email_matches * 0.2 + n_phone_matches * 0.2 +
                 n_ssn_matches * 0.4 + n_credit_card_matches * 0.4)
    if score > 1.0:
        return 1.0
    return score



def differential_privacy_noise(sensitivity, epsilon, delta):
    if epsilon <= 0.0 or delta <= 0.0:
        return 1e9
    return sensitivity * math.sqrt(2.0 * math.log(1.25 / delta)) / epsilon



def permission_access_check(user_role_level, resource_required_level, time_based_restriction):
    if time_based_restriction > 0.5:
        return 0.0
    if user_role_level >= resource_required_level:
        return 1.0
    return 0.0



def data_retention_decay(data_age_days, retention_days):
    if retention_days <= 0.0:
        return 0.0
    ratio = data_age_days / retention_days
    if ratio >= 1.0:
        return 0.0
    return 1.0 - ratio



def governance_compliance_score(data_lineage_coverage, audit_completeness, policy_adherence, privacy_budget_remaining):
    return 0.25 * data_lineage_coverage + 0.25 * audit_completeness + 0.25 * policy_adherence + 0.25 * privacy_budget_remaining
