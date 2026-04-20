"""Python equivalent of mojo/engine/inventory.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
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
try:
    from std.math import exp
except Exception:
    pass

PI = 3.141592653589793
SQRT_2 = 1.4142135623730951

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

def _normal_cdf_approx(z):
    if z < -8.0:
        return 0.0
    if z > 8.0:
        return 1.0
    x = z
    neg = False
    if x < 0.0:
        neg = True
        x = -x

    b0 = 0.2316419
    b1 = 0.319381530
    b2 = -0.356563782
    b3 = 1.781477937
    b4 = -1.821255978
    b5 = 1.330274429
    t = 1.0 / (1.0 + b0 * x)
    pdf = math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
    poly = t * (b1 + t * (b2 + t * (b3 + t * (b4 + t * b5))))
    cdf = 1.0 - pdf * poly
    if neg:
        cdf = 1.0 - cdf
    return cdf






def _normal_quantile_approx(p):

    pp = p
    if pp <= 0.0:
        pp = 1e-10
    if pp >= 1.0:
        pp = 1.0 - 1e-10

    y = pp - 0.5
    if math.fabs(y) < 0.42:
        r = y * y
        x = y * ((((-25.44106049637 * r + 41.39119773534) * r - 18.61500062529) * r + 2.506628277459) /
            ((((3.13082909833 * r - 21.06224101826) * r + 23.08336743743) * r - 8.47351093090) * r + 1.0))
        return x
    else:
        r = 0.0
        if y > 0.0:
            r = 1.0 - pp
        else:
            r = pp
        s = math.log(-math.log(r))
        x = 0.3374754822726147 + s * (0.9761690190917186 + s * (0.1607979714918209 +
            s * (0.0276438810333863 + s * (0.0038405729373609 + s * (0.0003951896511919 +
            s * (0.0000321767881768 + s * (0.0000002888167364 + s * 0.0000003960315187)))))))
        if y < 0.0:
            x = -x
        return x






def eoq(demand, order_cost, holding_cost):
    if holding_cost <= 0.0:
        return 0.0
    return math.sqrt(2.0 * demand * order_cost / holding_cost)






def reorder_point(demand_rate, lead_time, safety_stock):
    return demand_rate * lead_time + safety_stock






def safety_stock(z_score, demand_std, lead_time):
    return z_score * demand_std * math.sqrt(lead_time)






def total_inventory_cost(demand, order_qty, order_cost, holding_cost):
    if order_qty <= 0.0:
        return 0.0
    return (demand / order_qty) * order_cost + (order_qty / 2.0) * holding_cost






def newsvendor_qty(mean_demand, std_demand, cost_under, cost_over):
    total = cost_under + cost_over
    if total <= 0.0:
        return mean_demand
    cr = cost_under / total  # Critical ratio
    z = _normal_quantile_approx(cr)
    return mean_demand + z * std_demand






def service_level(z_score):
    return _normal_cdf_approx(z_score)






def abc_classify(values):
    n = len(values)
    if n == 0:
        return []


    idx = []
    for i in range(n):
        idx.append(i)

    for i in range(1, n):
        key = idx[i]
        key_val = values[key]
        j = i - 1
        while j >= 0 and values[idx[j]] < key_val:
            idx[j + 1] = idx[j]
            j -= 1
        idx[j + 1] = key


    total = 0.0
    for i in range(n):
        total += values[i]


    result = []
    for _ in range(n):
        result.append(2)  # Default C
    cumulative = 0.0
    for i in range(n):
        orig_idx = idx[i]
        cumulative += values[orig_idx]
        pct = cumulative / total if total > 0.0 else 1.0
        if pct <= 0.20:
            result[orig_idx] = 0  # A
        elif pct <= 0.50:
            result[orig_idx] = 1  # B
        else:
            result[orig_idx] = 2  # C
    return result






def days_of_supply(inventory, daily_demand):
    if daily_demand <= 0.0:
        return 0.0
    return inventory / daily_demand






def inventory_turnover(cogs, avg_inventory):
    if avg_inventory <= 0.0:
        return 0.0
    return cogs / avg_inventory






def fill_rate(orders_filled, total_orders):
    if total_orders <= 0:
        return 0.0
    return float(orders_filled) / float(total_orders)






def periodic_review_order(target, on_hand, on_order):
    qty = target - on_hand - on_order
    if qty < 0.0:
        return 0.0
    return qty
