"""Python equivalent of mojo/engine/supply_chain.mojo (auto-generated)."""
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

def lead_time_demand(demand_rate, lead_time):
    return demand_rate * lead_time






def bullwhip_effect(demand_variance, order_variance):
    if demand_variance < 1e-30:
        return 0.0
    return order_variance / demand_variance






def forecast_error_mae(actual, forecast):
    n = len(actual)
    if n == 0:
        return 0.0
    total = 0.0
    for i in range(n):
        total += math.fabs(actual[i] - forecast[i])
    return total / float(n)






def forecast_error_mape(actual, forecast):
    n = len(actual)
    if n == 0:
        return 0.0
    total = 0.0
    count = 0
    for i in range(n):
        if math.fabs(actual[i]) > 1e-30:
            total += math.fabs((actual[i] - forecast[i]) / actual[i])
            count += 1
    if count == 0:
        return 0.0
    return total / float(count) * 100.0






def forecast_bias(actual, forecast):
    n = len(actual)
    if n == 0:
        return 0.0
    total = 0.0
    for i in range(n):
        total += forecast[i] - actual[i]
    return total / float(n)






def tracking_signal(actual, forecast):
    n = len(actual)
    if n == 0:
        return 0.0
    cum_error = 0.0
    mad = 0.0
    for i in range(n):
        err = forecast[i] - actual[i]
        cum_error += err
        mad += math.fabs(err)
    mad /= float(n)
    if mad < 1e-30:
        return 0.0
    return cum_error / mad






def economic_production_qty(demand, setup_cost, holding_cost, production_rate):
    if production_rate <= demand:
        return 0.0
    if holding_cost < 1e-30:
        return 0.0
    ratio = 1.0 - demand / production_rate
    if ratio < 1e-30:
        return 0.0
    return math.sqrt(2.0 * demand * setup_cost / (holding_cost * ratio))






def total_cost_of_ownership(purchase, ordering, holding, shortage):
    return purchase + ordering + holding + shortage






def service_level_type1(stockout_probability):
    return 1.0 - stockout_probability






def fill_rate_type2(expected_shortage, demand):
    if demand < 1e-30:
        return 0.0
    return 1.0 - expected_shortage / demand






def moving_average_forecast(data, periods):
    n = len(data)
    if n == 0 or periods <= 0:
        return 0.0
    actual_periods = periods
    if actual_periods > n:
        actual_periods = n
    total = 0.0
    for i in range(n - actual_periods, n):
        total += data[i]
    return total / float(actual_periods)






def exponential_smoothing_forecast(data, alpha):
    n = len(data)
    if n == 0:
        return 0.0
    if n == 1:
        return data[0]
    forecast = data[0]
    for i in range(1, n):
        forecast = alpha * data[i] + (1.0 - alpha) * forecast
    return forecast
