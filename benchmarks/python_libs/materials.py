"""Python equivalent of mojo/engine/materials.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import pow
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

def youngs_modulus(stress, strain):
    if math.fabs(strain) < 1e-30:
        return 0.0
    return stress / strain






def shear_modulus(E, poisson):
    denom = 2.0 * (1.0 + poisson)
    if math.fabs(denom) < 1e-30:
        return 0.0
    return math.e / denom






def bulk_modulus(E, poisson):
    denom = 3.0 * (1.0 - 2.0 * poisson)
    if math.fabs(denom) < 1e-30:
        return 0.0
    return math.e / denom






def stress_from_force(force, area):
    if math.fabs(area) < 1e-30:
        return 0.0
    return force / area






def strain_from_deformation(delta_l, original_l):
    if math.fabs(original_l) < 1e-30:
        return 0.0
    return delta_l / original_l






def thermal_expansion(original_l, alpha, delta_t):
    return original_l * alpha * delta_t






def safety_factor(ultimate_stress, working_stress):
    if math.fabs(working_stress) < 1e-30:
        return 0.0
    return ultimate_stress / working_stress






def stress_concentration(nominal_stress, kt):
    return kt * nominal_stress






def fatigue_life(sigma_a, sigma_f, b):
    if math.fabs(sigma_f) < 1e-30 or math.fabs(b) < 1e-30:
        return 0.0
    return (sigma_a / sigma_f) ** (1.0 / b)






def beam_deflection_cantilever(force, length, E, I):
    denom = 3.0 * math.e * I
    if math.fabs(denom) < 1e-30:
        return 0.0
    return force * length * length * length / denom






def moment_of_inertia_rect(width, height):
    return width * height * height * height / 12.0






def poisson_ratio_from_moduli(E, G):
    if math.fabs(G) < 1e-30:
        return 0.0
    return math.e / (2.0 * G) - 1.0
