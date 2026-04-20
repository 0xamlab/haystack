"""Python equivalent of mojo/engine/fermentation.mojo (auto-generated)."""
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

def ethanol_yield(glucose_g):
    return 0.511 * glucose_g



def alcohol_by_volume(original_gravity, final_gravity):
    return (original_gravity - final_gravity) * 131.25



def carbon_dioxide_produced(glucose_g):
    return 0.489 * glucose_g



def yeast_growth_rate(mu_max, substrate_conc, ks, ethanol_conc):
    pm = 100.0  # maximum tolerated ethanol g/L
    monod = substrate_conc / (ks + substrate_conc) if (ks + substrate_conc) > 0.0 else 0.0
    inhibition = 1.0 - ethanol_conc / pm
    if inhibition < 0.0:
        inhibition = 0.0
    return mu_max * monod * inhibition



def substrate_consumption(growth_rate, biomass_conc, yield_factor):
    if yield_factor <= 0.0:
        return 0.0
    return (growth_rate / yield_factor) * biomass_conc



def volumetric_productivity(product_conc, fermentation_time):
    if fermentation_time <= 0.0:
        return 0.0
    return product_conc / fermentation_time



def fermentation_efficiency(actual_yield, theoretical_yield):
    if theoretical_yield <= 0.0:
        return 0.0
    return actual_yield / theoretical_yield * 100.0



def dissolved_oxygen_kla(kla, o2_saturation, o2_actual):
    deficit = o2_saturation - o2_actual
    if deficit < 0.0:
        return 0.0
    return kla * deficit



def ph_buffer_capacity(acid_base_concentration, pka, ph):
    from std.math import pow as fpow
    h_plus = fpow(10.0, -ph)
    ka = fpow(10.0, -pka)
    denom = (ka + h_plus) * (ka + h_plus)
    if denom <= 0.0:
        return 0.0
    return 2.303 * ka * acid_base_concentration / denom



def heat_generation_rate(oxygen_uptake_rate, heat_of_combustion):
    return oxygen_uptake_rate * heat_of_combustion
