"""Python equivalent of mojo/engine/structured_output.mojo (auto-generated)."""
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

def json_next_token_valid(fsm_state, token_type):


    if fsm_state == 1.0 and token_type == 0.0:
        return 0.0  # Need key first
    if fsm_state == 5.0:
        return 0.0
    return 1.0



def schema_field_confidence(field_log_prob, schema_match_score):
    return math.exp(field_log_prob) * schema_match_score



def sql_clause_transition(current_clause, next_clause):
    if next_clause > current_clause:
        return 1.0
    if next_clause == current_clause:
        return 0.5  # Same clause continuation
    return 0.0  # Backward transition invalid



def xml_nesting_depth_valid(current_depth, max_depth):
    if current_depth <= max_depth and current_depth >= 0.0:
        return 1.0
    return 0.0



def output_repair_edit_distance(original_len, n_edits):
    if original_len <= 0.0:
        return 0.0
    return n_edits / original_len



def regex_constraint_match(token_char_code, pattern_accept_min, pattern_accept_max):
    if token_char_code >= pattern_accept_min and token_char_code <= pattern_accept_max:
        return 1.0
    return 0.0



def type_coercion_score(raw_value, target_type):
    if target_type == 0.0:
        return 1.0 if raw_value == float(int(raw_value)) else 0.5
    if target_type == 1.0:
        return 1.0
    if target_type == 2.0:
        return 1.0 if (raw_value == 0.0 or raw_value == 1.0) else 0.0
    return 0.8  # string: usually coercible



def field_extraction_recall(required_fields_extracted, total_required_fields):
    if total_required_fields <= 0.0:
        return 1.0
    return required_fields_extracted / total_required_fields



def output_diversity_score(n_unique_outputs, total_outputs):
    if total_outputs <= 0.0:
        return 0.0
    return n_unique_outputs / total_outputs



def format_compliance_rate(compliant_outputs, total_outputs):
    if total_outputs <= 0.0:
        return 1.0
    return compliant_outputs / total_outputs
