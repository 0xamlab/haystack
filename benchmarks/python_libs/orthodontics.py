"""Python equivalent of mojo/engine/orthodontics.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import pow
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

def tooth_movement_rate(applied_force_g, optimal_force_g):
    if optimal_force_g <= 0.0:
        return 0.0
    ratio = applied_force_g / optimal_force_g
    if ratio > 1.0:
        return 1.0
    return ratio



def moment_to_force_ratio(moment_g_mm, force_g):
    if force_g <= 0.0:
        return 0.0
    return moment_g_mm / force_g



def anchorage_loss_estimate(reactive_force_g, anchor_teeth):
    if anchor_teeth <= 0.0:
        return 0.0
    return reactive_force_g / anchor_teeth



def arch_wire_force(deflection_mm, wire_diameter_mm, elastic_modulus_gpa, span_mm):
    if span_mm <= 0.0:
        return 0.0
    pi = 3.141592653589793
    d_m = wire_diameter_mm * 1e-3
    I = pi * (d_m) ** (4.0) / 64.0  # m⁴
    E = elastic_modulus_gpa * 1e9  # Pa
    L_m = span_mm * 1e-3
    delta_m = deflection_mm * 1e-3
    return 48.0 * math.e * I * delta_m / (L_m) ** (3.0)



def levelling_torque(third_order_angle_deg, wire_dimension_mm, elastic_modulus_gpa, bracket_width_mm):
    pi = 3.141592653589793
    theta_rad = third_order_angle_deg * pi / 180.0
    d_m = wire_dimension_mm * 1e-3
    J = pi * (d_m) ** (4.0) / 32.0
    E = elastic_modulus_gpa * 1e9
    L_m = bracket_width_mm * 1e-3
    if L_m <= 0.0:
        return 0.0
    return math.e * J * theta_rad / L_m * 1000.0  # convert to N·mm



def bolton_ratio(mandibular_sum_mm, maxillary_sum_mm):
    if maxillary_sum_mm <= 0.0:
        return 0.0
    return mandibular_sum_mm / maxillary_sum_mm * 100.0



def pont_index(upper_four_premolars_sum_mm, region):
    factor = 80.0
    if region > 0.5:
        factor = 64.0
    return upper_four_premolars_sum_mm * 100.0 / factor



def arch_perimeter_estimate(irregularity_index_mm, available_space_mm):
    return available_space_mm + irregularity_index_mm



def growth_prediction_cephalometric(sna_deg, snb_deg, ans_pns_mm):
    return sna_deg - snb_deg - ans_pns_mm / 10.0



def retainer_force_decay(initial_force_g, time_weeks, decay_constant):
    return initial_force_g * math.exp(-decay_constant * time_weeks)
