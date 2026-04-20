"""Python equivalent of mojo/engine/control.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import abs as fabs
except Exception:
    pass

class PIDState:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('kp')
        self.kp = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('ki')
        self.ki = _v1 if _v1 is not None else 0.0
        _v2 = args[2] if 2 < len(args) else kwargs.get('kd')
        self.kd = _v2 if _v2 is not None else 0.0
        _v3 = args[3] if 3 < len(args) else kwargs.get('output_min')
        self.output_min = _v3 if _v3 is not None else 0.0
        _v4 = args[4] if 4 < len(args) else kwargs.get('output_max')
        self.output_max = _v4 if _v4 is not None else 0.0
        self.integral = 0.0
        self.prev_error = 0.0
    def __repr__(self):
        return f'PIDState({vars(self)})'

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

def create_pid(kp, ki, kd, output_min=-1e18, output_max=1e18):
    return PIDState(kp, ki, kd, output_min, output_max)






def pid_simulate(kp, ki, kd, setpoint, initial, plant_gain, dt, steps):
    state = create_pid(kp, ki, kd)
    trajectory = []
    y = initial
    trajectory.append(y)

    for i in range(steps):
        u = pid_update(state, setpoint, y, dt)
        y = y + plant_gain * u * dt
        trajectory.append(y)
    return trajectory






def bang_bang(setpoint, measured, hysteresis=0.0):
    if measured < setpoint - hysteresis:
        return 1.0
    if measured > setpoint + hysteresis:
        return 0.0
    return 0.5






def step_response(gain, time_constant, dt, steps):
    result = []
    for i in range(steps):
        t = float(i) * dt
        result.append(gain * (1.0 - math.exp(-t / time_constant)))
    return result






def ramp_response(gain, time_constant, dt, steps):
    result = []
    for i in range(steps):
        t = float(i) * dt
        result.append(gain * (t - time_constant * (1.0 - math.exp(-t / time_constant))))
    return result






def settling_time(response, setpoint, tolerance=0.02):
    band = math.fabs(setpoint) * tolerance
    if band < 1e-15:
        band = tolerance  # Fallback for setpoint ≈ 0

    n = len(response)

    last_violation = -1
    for i in range(n):
        if math.fabs(response[i] - setpoint) > band:
            last_violation = i

    if last_violation == -1:
        return 0.0  # Always within band
    if last_violation == n - 1:
        return -1.0  # Never settled
    return float(last_violation + 1)






def overshoot(response, setpoint):
    if math.fabs(setpoint) < 1e-15:
        return 0.0

    peak = response[0]
    for i in range(1, len(response)):
        if setpoint > 0.0:
            if response[i] > peak:
                peak = response[i]
        else:
            if response[i] < peak:
                peak = response[i]

    os_val = (peak - setpoint) / math.fabs(setpoint)
    if os_val < 0.0:
        return 0.0
    return os_val






def steady_state_error(response, setpoint):
    if len(response) == 0:
        return math.fabs(setpoint)
    return math.fabs(response[len(response) - 1] - setpoint)
