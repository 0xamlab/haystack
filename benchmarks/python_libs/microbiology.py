"""Python equivalent of mojo/engine/microbiology.mojo (auto-generated)."""
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
    from std.math import sqrt
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

def exponential_growth(n0, growth_rate, time):
    if n0 < 0.0 or growth_rate < 0.0 or time < 0.0:
        return n0
    return n0 * math.exp(growth_rate * time)



def doubling_time(growth_rate):
    if growth_rate <= 0.0:
        return 0.0
    return math.log(2.0) / growth_rate



def monod_growth_rate(mu_max, substrate, ks):
    denom = ks + substrate
    if denom <= 0.0:
        return 0.0
    return mu_max * substrate / denom



def bacterial_generation_time(n_initial, n_final, elapsed_h):
    if n_initial <= 0.0 or n_final <= n_initial or elapsed_h <= 0.0:
        return 0.0
    generations = math.log(n_final / n_initial) / math.log(2.0)
    if generations <= 0.0:
        return 0.0
    return elapsed_h / generations



def colony_forming_units(colony_count, dilution_factor, volume_ml):
    if dilution_factor <= 0.0 or volume_ml <= 0.0:
        return 0.0
    return colony_count / (dilution_factor * volume_ml)



def minimum_inhibitory_conc(inhibition_zone_mm, disk_conc_ug):
    if inhibition_zone_mm <= 6.0:
        return disk_conc_ug  # no inhibition at disc edge
    return disk_conc_ug / (inhibition_zone_mm - 6.0)



def biofilm_formation_index(od_sample, od_control):
    if od_control <= 0.0:
        return 0.0
    return od_sample / od_control



def inactivation_first_order(n0, inactivation_rate, time):
    if n0 < 0.0 or inactivation_rate < 0.0 or time < 0.0:
        return n0
    return n0 * math.exp(-inactivation_rate * time)



def d_value(inactivation_rate):
    if inactivation_rate <= 0.0:
        return 0.0
    return math.log(10.0) / inactivation_rate



def z_value(d1, d2, t1, t2):
    if d1 <= 0.0 or d2 <= 0.0 or d1 == d2:
        return 0.0
    return (t2 - t1) / math.log(d1 / d2) * math.log(10.0)
