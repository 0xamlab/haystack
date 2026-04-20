"""Python equivalent of mojo/engine/ceramics.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import exp
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import abs as fabs
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

def weibull_failure_probability(stress, sigma0, m):
    if math.fabs(sigma0) < 1e-30:
        return 0.0
    ratio = stress / sigma0
    if ratio < 0.0:
        return 0.0
    exponent = math.exp(m * math.log(ratio))
    return 1.0 - math.exp(-exponent)






def weibull_characteristic_strength(mean_strength, m):
    return mean_strength * 1.1






def thermal_shock_resistance(strength, modulus, alpha, poisson):
    denom = modulus * alpha
    if math.fabs(denom) < 1e-30:
        return 0.0
    return strength * (1.0 - poisson) / denom






def youngs_modulus_porosity(e0, porosity, b):
    return e0 * math.exp(-b * porosity)






def sintering_shrinkage(initial_length, final_length):
    if math.fabs(initial_length) < 1e-30:
        return 0.0
    return (initial_length - final_length) / initial_length * 100.0






def density_from_archimedes(dry_mass, wet_mass, suspended_mass, fluid_density):
    denom = wet_mass - suspended_mass
    if math.fabs(denom) < 1e-30:
        return 0.0
    return dry_mass * fluid_density / denom






def relative_density(actual, theoretical):
    if math.fabs(theoretical) < 1e-30:
        return 0.0
    return actual / theoretical * 100.0






def porosity_from_density(actual_density, theoretical_density):
    if math.fabs(theoretical_density) < 1e-30:
        return 0.0
    return (1.0 - actual_density / theoretical_density) * 100.0






def fracture_toughness_indentation(hardness, crack_length, load, c_factor, modulus):
    if math.fabs(hardness) < 1e-30 or crack_length <= 0.0:
        return 0.0
    eh_ratio = math.exp(0.5 * math.log(modulus / hardness))
    c15 = math.exp(1.5 * math.log(crack_length))
    if math.fabs(c15) < 1e-30:
        return 0.0
    return c_factor * eh_ratio * load / c15






def dielectric_constant_mixture(v1, k1, v2, k2):
    return v1 * k1 + v2 * k2






def coefficient_of_thermal_expansion(delta_l, l0, delta_t):
    denom = l0 * delta_t
    if math.fabs(denom) < 1e-30:
        return 0.0
    return delta_l / denom






def glass_transition_estimate(melting_point):
    return (2.0 / 3.0) * melting_point
