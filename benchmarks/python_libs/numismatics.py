"""Python equivalent of mojo/engine/numismatics.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import abs as fabs
except Exception:
    pass
try:
    from std.math import pow
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

def melt_value(metal_weight_oz, metal_price_per_oz):
    return metal_weight_oz * metal_price_per_oz






def premium_over_melt(market_price, melt_val):
    if math.fabs(melt_val) < 1e-30:
        return 0.0
    return (market_price - melt_val) / melt_val * 100.0






def grade_numeric_to_scale(sheldon_grade):
    if sheldon_grade < 0.0:
        return 0.0
    if sheldon_grade > 70.0:
        return 70.0
    return sheldon_grade






def population_scarcity(certified_count, total_mintage):
    if math.fabs(total_mintage) < 1e-30:
        return 0.0
    return certified_count / total_mintage * 100.0






def annual_return(purchase_price, current_price, years):
    if math.fabs(purchase_price) < 1e-30 or math.fabs(years) < 1e-30:
        return 0.0
    ratio = current_price / purchase_price
    if ratio <= 0.0:
        return 0.0
    return ((ratio) ** (1.0 / years) - 1.0) * 100.0






def insurance_value(market_price, coverage_factor):
    return market_price * coverage_factor






def mintage_per_capita(mintage, population):
    if math.fabs(population) < 1e-30:
        return 0.0
    return mintage / population






def survival_rate_estimate(surviving, original_mintage):
    if math.fabs(original_mintage) < 1e-30:
        return 0.0
    return surviving / original_mintage * 100.0






def price_trend(prices_avg_old, prices_avg_new):
    if math.fabs(prices_avg_old) < 1e-30:
        return 0.0
    return (prices_avg_new - prices_avg_old) / prices_avg_old * 100.0






def auction_fee(hammer_price, buyer_premium_pct):
    return hammer_price * buyer_premium_pct / 100.0






def total_cost_acquisition(hammer, premium, tax_rate):
    return hammer * (1.0 + premium / 100.0) * (1.0 + tax_rate / 100.0)






def bullion_content_troy_oz(weight_grams, purity):
    return weight_grams * purity / 31.1035
