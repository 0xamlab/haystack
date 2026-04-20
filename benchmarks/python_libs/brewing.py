"""Python equivalent of mojo/engine/brewing.mojo (auto-generated)."""
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

def original_gravity_to_plato(og):
    return (og - 1.0) * 1000.0 / 4.0






def plato_to_gravity(plato):
    return 1.0 + plato * 4.0 / 1000.0






def abv_from_og_fg(og, fg):
    return (og - fg) * 131.25






def apparent_attenuation(og, fg):
    denom = og - 1.0
    if denom == 0.0:
        return 0.0
    return (og - fg) / denom * 100.0






def real_attenuation(apparent_att):
    return apparent_att * 0.8192






def ibu_tinseth(utilization, alpha_acid_pct, weight_oz, volume_gal):
    if volume_gal == 0.0:
        return 0.0
    return (utilization * alpha_acid_pct * weight_oz * 7490.0) / volume_gal






def utilization_tinseth(gravity, time_min):
    bigness = 1.65 * math.exp((gravity - 1.0) * math.log(0.000125))
    boil_factor = (1.0 - math.exp(-0.04 * time_min)) / 4.15
    return bigness * boil_factor






def mash_water_volume(grain_weight_kg, ratio):
    return grain_weight_kg * ratio






def strike_water_temp(target_temp, grain_temp, ratio):
    if ratio == 0.0:
        return target_temp
    return (0.2 / ratio) * (target_temp - grain_temp) + target_temp






def color_srm_from_mcu(mcu):
    if mcu <= 0.0:
        return 0.0
    return 1.4922 * math.exp(0.6859 * math.log(mcu))






def calories_per_12oz(og, fg):
    re = 0.8114 * og + 0.1886 * fg - 1.0
    abw = (og - fg) * 2.75
    cal = 3621.0 * fg * (re * 3.55 + abw * 7.0) / 12.0
    return cal






def priming_sugar_g(volume_co2, temp_c, volume_beer_l):
    residual = 3.0378 - 0.050062 * temp_c + 0.00026555 * temp_c * temp_c
    needed = volume_co2 - residual
    if needed < 0.0:
        needed = 0.0
    return volume_beer_l * needed * 4.0
