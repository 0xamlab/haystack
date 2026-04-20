"""Python equivalent of mojo/engine/pneumatics.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass

PI = 3.141592653589793

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

def ideal_gas_volume(pressure1, volume1, pressure2):
    if math.fabs(pressure2) < 1e-30:
        return 0.0
    return pressure1 * volume1 / pressure2






def flow_rate_orifice(cd, area, pressure_drop, density):
    if math.fabs(density) < 1e-30:
        return 0.0
    inner = 2.0 * pressure_drop / density
    if inner < 0.0:
        return 0.0
    return cd * area * math.sqrt(inner)






def compressor_power(flow_rate, p1, p2, efficiency):
    if math.fabs(efficiency) < 1e-30 or math.fabs(p1) < 1e-30:
        return 0.0
    ratio = p2 / p1
    if ratio <= 0.0:
        return 0.0
    return flow_rate * p1 * math.log(ratio) / efficiency






def pressure_drop_pipe(f, length, diameter, density, velocity):
    if math.fabs(diameter) < 1e-30:
        return 0.0
    return f * length / diameter * density * velocity * velocity / 2.0






def air_consumption(bore_diameter, stroke, pressure, cycles_per_min):
    area = math.pi / 4.0 * bore_diameter * bore_diameter
    return area * stroke * 2.0 * pressure / 101.325 * cycles_per_min






def cylinder_force(bore_area, pressure):
    return bore_area * pressure






def bore_area(diameter):
    return math.pi / 4.0 * diameter * diameter






def piston_speed(stroke, cycles_per_min):
    return 2.0 * stroke * cycles_per_min / 60.0






def receiver_volume(flow_rate, run_time, p_max, p_min):
    dp = p_max - p_min
    if math.fabs(dp) < 1e-30:
        return 0.0
    return flow_rate * run_time / dp






def free_air_delivery(measured_flow, measured_pressure, atm_pressure):
    if math.fabs(atm_pressure) < 1e-30:
        return 0.0
    return measured_flow * measured_pressure / atm_pressure






def specific_power(power_kw, fad):
    if math.fabs(fad) < 1e-30:
        return 0.0
    return power_kw / fad






def dew_point_pressure(atm_dew_point, pressure_ratio):
    if pressure_ratio <= 0.0:
        return atm_dew_point
    return atm_dew_point + 10.0 * math.log(pressure_ratio)
