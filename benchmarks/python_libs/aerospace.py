"""Python equivalent of mojo/engine/aerospace.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import log as _ln
except Exception:
    pass

G0 = 9.80665  # standard gravity m/s²

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

def dynamic_pressure(density, velocity):
    return 0.5 * density * velocity * velocity






def lift_force(cl, q, wing_area):
    return cl * q * wing_area






def drag_force(cd, q, wing_area):
    return cd * q * wing_area






def lift_to_drag_ratio(cl, cd):
    if cd == 0.0:
        return 0.0
    return cl / cd






def thrust_required(weight, ld_ratio):
    if ld_ratio == 0.0:
        return 0.0
    return weight / ld_ratio






def specific_impulse(thrust, mass_flow_rate):
    denom = mass_flow_rate * G0
    if denom == 0.0:
        return 0.0
    return thrust / denom






def tsiolkovsky_delta_v(isp, mass_initial, mass_final):
    if mass_final <= 0.0 or mass_initial <= 0.0:
        return 0.0
    return isp * G0 * _ln(mass_initial / mass_final)






def mach_number(velocity, speed_of_sound_val):
    if speed_of_sound_val == 0.0:
        return 0.0
    return velocity / speed_of_sound_val






def speed_of_sound(gamma, gas_constant, temperature):
    return math.sqrt(gamma * gas_constant * temperature)






def orbital_velocity(mu, radius):
    if radius <= 0.0:
        return 0.0
    return math.sqrt(mu / radius)






def escape_velocity(mu, radius):
    if radius <= 0.0:
        return 0.0
    return math.sqrt(2.0 * mu / radius)






def hohmann_delta_v(mu, r1, r2):
    if r1 <= 0.0 or r2 <= 0.0:
        return 0.0
    v1 = math.sqrt(mu / r1)
    v2 = math.sqrt(mu / r2)
    sum_r = r1 + r2
    dv1 = v1 * (math.sqrt(2.0 * r2 / sum_r) - 1.0)
    dv2 = v2 * (1.0 - math.sqrt(2.0 * r1 / sum_r))

    if dv1 < 0.0:
        dv1 = -dv1
    if dv2 < 0.0:
        dv2 = -dv2
    return dv1 + dv2
