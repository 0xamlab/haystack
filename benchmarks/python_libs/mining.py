"""Python equivalent of mojo/engine/mining.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
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

def ore_grade(metal_mass, ore_mass):
    if math.fabs(ore_mass) < 1e-30:
        return 0.0
    return metal_mass / ore_mass * 100.0






def strip_ratio(waste_volume, ore_volume):
    if math.fabs(ore_volume) < 1e-30:
        return 0.0
    return waste_volume / ore_volume






def recovery_rate(metal_recovered, metal_in_feed):
    if math.fabs(metal_in_feed) < 1e-30:
        return 0.0
    return metal_recovered / metal_in_feed * 100.0






def mill_throughput(feed_rate, hours):
    return feed_rate * hours






def bond_work_index_energy(wi, p80, f80):
    if p80 <= 0.0 or f80 <= 0.0:
        return 0.0
    return 10.0 * wi * (1.0 / math.sqrt(p80) - 1.0 / math.sqrt(f80))






def cut_off_grade(mining_cost, processing_cost, metal_price, recovery):
    denom = metal_price * recovery
    if math.fabs(denom) < 1e-30:
        return 0.0
    return (mining_cost + processing_cost) / denom * 100.0






def dilution_factor(tonnes_waste_in_ore, tonnes_ore):
    total = tonnes_waste_in_ore + tonnes_ore
    if math.fabs(total) < 1e-30:
        return 0.0
    return tonnes_waste_in_ore / total * 100.0






def net_smelter_return(metal_price, grade, recovery, smelting_cost):
    return metal_price * grade / 100.0 * recovery / 100.0 - smelting_cost






def reserve_life(tonnes_reserve, annual_production):
    if math.fabs(annual_production) < 1e-30:
        return 0.0
    return tonnes_reserve / annual_production






def powder_factor(explosive_kg, rock_tonnes):
    if math.fabs(rock_tonnes) < 1e-30:
        return 0.0
    return explosive_kg / rock_tonnes






def ventilation_quantity(workers, airflow_per_worker):
    return workers * airflow_per_worker






def subsidence_factor(extraction_height, depth):
    if math.fabs(depth) < 1e-30:
        return 0.0
    return extraction_height / depth
