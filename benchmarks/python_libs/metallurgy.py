"""Python equivalent of mojo/engine/metallurgy.mojo (auto-generated)."""
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

def hall_petch(sigma0, ky, d):
    if d <= 0.0:
        return sigma0
    return sigma0 + ky / math.sqrt(d)






def johnson_cook_flow_stress(a, b, strain, n):
    if strain <= 0.0:
        return a
    return a + b * math.exp(n * math.log(strain))






def hardness_to_tensile(hb):
    return 3.45 * hb






def carbon_equivalent(c, mn, si, ni, cr, mo, v):
    _ = si  # IIW formula doesn't include Si directly
    return c + mn / 6.0 + (cr + mo + v) / 5.0 + ni / 15.0






def jominy_distance_to_hardness(h0, decay_rate, distance):
    return h0 * math.exp(-decay_rate * distance)






def avrami_fraction(k, n, t):
    if t <= 0.0:
        return 0.0
    return 1.0 - math.exp(-k * math.exp(n * math.log(t)))






def quench_severity(h, diameter):
    return h * diameter






def tempering_parameter(temperature_k, time_hours, c):
    if time_hours <= 0.0:
        return 0.0
    log10_t = math.log(time_hours) / math.log(10.0)
    return temperature_k * (c + log10_t)






def density_of_alloy_rule_of_mixtures(f1, d1, f2, d2):
    return f1 * d1 + f2 * d2






def thermal_conductivity_wiedemann_franz(electrical_cond, temperature, lorenz):
    return lorenz * electrical_cond * temperature






def strain_hardening_exponent_from_points(stress1, strain1, stress2, strain2):
    if stress1 <= 0.0 or stress2 <= 0.0 or strain1 <= 0.0 or strain2 <= 0.0:
        return 0.0
    denom = math.log(strain2 / strain1)
    if math.fabs(denom) < 1e-30:
        return 0.0
    return math.log(stress2 / stress1) / denom






def fatigue_life_basquin(sigma_f, sigma_a, b):
    if math.fabs(sigma_f) < 1e-30 or math.fabs(b) < 1e-30:
        return 0.0
    ratio = sigma_a / sigma_f
    if ratio <= 0.0:
        return 0.0
    return math.exp((1.0 / b) * math.log(ratio))
