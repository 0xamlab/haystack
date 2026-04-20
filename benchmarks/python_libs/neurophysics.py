"""Python equivalent of mojo/engine/neurophysics.mojo (auto-generated)."""
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
    from std.math import log
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

def nernst_potential(z, conc_outside, conc_inside, temperature):
    if conc_inside <= 0.0 or conc_outside <= 0.0 or z == 0.0:
        return 0.0
    R = 8.314
    F = 96485.0
    return (R * temperature / (z * F)) * math.log(conc_outside / conc_inside) * 1000.0



def goldman_equation(pk, pna, pcl, k_out, na_out, cl_in, k_in, na_in, cl_out):
    num = pk * k_out + pna * na_out + pcl * cl_in
    den = pk * k_in  + pna * na_in  + pcl * cl_out
    if num <= 0.0 or den <= 0.0:
        return 0.0
    R = 8.314; T = 310.15; F = 96485.0
    return (R * T / F) * math.log(num / den) * 1000.0



def membrane_time_constant(r_membrane, c_membrane):
    if r_membrane < 0.0 or c_membrane < 0.0:
        return 0.0
    return r_membrane * c_membrane / 1000.0  # to ms (if Rm in Ω·cm², Cm in μF/cm²)



def cable_length_constant(r_membrane, r_internal):
    if r_internal <= 0.0 or r_membrane < 0.0:
        return 0.0
    return math.sqrt(r_membrane / r_internal)



def action_potential_threshold(v_threshold, v_rest, r_input):
    if r_input <= 0.0:
        return 0.0
    return (v_threshold - v_rest) / r_input



def firing_rate_simple(refractory_ms, integration_time_ms):
    total = refractory_ms + integration_time_ms
    if total <= 0.0:
        return 0.0
    return 1000.0 / total



def synaptic_current(conductance, v_membrane, e_synapse):
    return conductance * (v_membrane - e_synapse)



def integrate_and_fire_voltage(v_rest, i_input, r_input, tau, time):
    if tau <= 0.0:
        return v_rest
    return v_rest + i_input * r_input * (1.0 - math.exp(-time / tau))



def eeg_spectral_power(frequency, beta):
    if frequency <= 0.0:
        return 0.0
    return 1.0 / (frequency) ** (beta)



def conduction_velocity(axon_diameter_um):
    if axon_diameter_um <= 0.0:
        return 0.0
    return 5.5 * math.sqrt(axon_diameter_um)
