"""Python equivalent of mojo/engine/composites.mojo (auto-generated)."""
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

def rule_of_mixtures_modulus(vf, ef, em):
    return vf * ef + (1.0 - vf) * em



def inverse_rule_of_mixtures(vf, ef, em):
    if ef <= 0.0 or em <= 0.0:
        return 0.0
    inv = vf / ef + (1.0 - vf) / em
    if inv <= 0.0:
        return 0.0
    return 1.0 / inv



def composite_density(vf, rho_f, rho_m):
    return vf * rho_f + (1.0 - vf) * rho_m






def fiber_volume_fraction(fiber_mass, fiber_density, matrix_mass, matrix_density):
    if fiber_density <= 0.0 or matrix_density <= 0.0:
        return 0.0
    vf_vol = fiber_mass / fiber_density
    vm_vol = matrix_mass / matrix_density
    total = vf_vol + vm_vol
    if total <= 0.0:
        return 0.0
    return vf_vol / total






def laminate_thickness(n_plies, ply_thickness):
    return n_plies * ply_thickness






def specific_stiffness(modulus, density):
    if density <= 0.0:
        return 0.0
    return modulus / density



def specific_strength(strength, density):
    if density <= 0.0:
        return 0.0
    return strength / density






def halpin_tsai(vf, ef, em, xi):
    if em <= 0.0:
        return 0.0
    ratio = ef / em
    denom_eta = ratio + xi
    if denom_eta <= 0.0:
        return 0.0
    eta = (ratio - 1.0) / denom_eta
    denom = 1.0 - eta * vf
    if denom <= 0.0:
        return 0.0
    return em * (1.0 + xi * eta * vf) / denom






def critical_fiber_length(fiber_strength, fiber_diameter, interfacial_shear):
    if interfacial_shear <= 0.0:
        return 0.0
    return fiber_strength * fiber_diameter / (2.0 * interfacial_shear)






def shear_lag_stress_transfer(applied_stress, aspect_ratio, vf):
    return applied_stress * (1.0 + aspect_ratio * vf / 2.0)






def impact_energy_charpy(absorbed_energy, cross_section_area):
    if cross_section_area <= 0.0:
        return 0.0
    return absorbed_energy / cross_section_area






def void_content(theoretical_density, measured_density):
    if theoretical_density <= 0.0:
        return 0.0
    return (theoretical_density - measured_density) / theoretical_density * 100.0
