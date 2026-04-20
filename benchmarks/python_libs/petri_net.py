"""Python equivalent of mojo/engine/petri_net.mojo (auto-generated)."""
import math
import random as _rng

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

def is_transition_enabled_2p(m0, m1, in0, in1):
    return m0 >= in0 and m1 >= in1






def fire_transition_2p(m0, m1, in0, in1, out0, out1):
    new0 = m0 - in0 + out0
    new1 = m1 - in1 + out1
    return new0 + new1






def token_count_3p(m0, m1, m2):
    return m0 + m1 + m2






def is_deadlocked_1t_2p(m0, m1, in0, in1):
    return not is_transition_enabled_2p(m0, m1, in0, in1)






def is_deadlocked_2t_2p(m0, m1, t0_in0, t0_in1, t1_in0, t1_in1):
    t0_ok = m0 >= t0_in0 and m1 >= t0_in1
    t1_ok = m0 >= t1_in0 and m1 >= t1_in1
    return not t0_ok and not t1_ok






def reachable_from_firing(marking_sum, input_sum, output_sum):
    return marking_sum - input_sum + output_sum






def place_bounded(max_tokens, bound):
    return max_tokens <= bound






def is_live_transition(enabled_count, total_markings):
    if total_markings == 0:
        return 0.0
    return float(enabled_count) / float(total_markings)






def coverability_check(marking_val, target_val):
    return marking_val >= target_val






def incidence_value(output_weight, input_weight):
    return output_weight - input_weight






def siphon_empty_3p(t0, t1, t2, s0, s1, s2):
    if s0 and t0 > 0:
        return False
    if s1 and t1 > 0:
        return False
    if s2 and t2 > 0:
        return False
    return True






def is_transition_enabled_list(marking, input_arcs, n_places):
    for i in range(n_places):
        if marking[i] < input_arcs[i]:
            return False
    return True



def fire_transition_list(marking, input_arcs, output_arcs, n_places):
    total = 0
    for i in range(n_places):
        new_val = marking[i] - input_arcs[i] + output_arcs[i]
        total += new_val
    return total
