"""Python equivalent of mojo/engine/finance.mojo (auto-generated)."""
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

def _npv_derivative(rate, cashflows):
    total = 0.0
    n = len(cashflows)
    for t in range(1, n):
        discount = (1.0 + rate) ** (float(t + 1))
        total += -float(t) * cashflows[t] / discount
    return total



def npv(rate, cashflows):
    total = 0.0
    n = len(cashflows)
    for t in range(n):
        discount = (1.0 + rate) ** (float(t))
        total += cashflows[t] / discount
    return total






def irr(cashflows, guess=0.1, tol=1e-6, max_iter=100):
    r = guess
    for _ in range(max_iter):
        f = npv(r, cashflows)
        df = _npv_derivative(r, cashflows)
        if math.fabs(df) < 1e-15:
            break
        r_new = r - f / df
        if math.fabs(r_new - r) < tol:
            return r_new
        r = r_new
    return r






def payback_period(cashflows):
    n = len(cashflows)
    if n == 0:
        return -1.0
    cumulative = 0.0
    for t in range(n):
        cumulative += cashflows[t]
        if cumulative >= 0.0 and t > 0:

            prev = cumulative - cashflows[t]
            frac = -prev / cashflows[t] if cashflows[t] != 0.0 else 0.0
            return float(t - 1) + frac
    return -1.0






def roi(gain, cost):
    if math.fabs(cost) < 1e-15:
        return 0.0
    return (gain - cost) / cost






def compound_interest(principal, rate, periods):
    return principal * (1.0 + rate) ** (float(periods))






def present_value(future_value, rate, periods):
    return future_value / (1.0 + rate) ** (float(periods))






def future_value(present_val, rate, periods):
    return present_val * (1.0 + rate) ** (float(periods))






def annuity_payment(principal, rate, periods):
    if math.fabs(rate) < 1e-15:
        if periods == 0:
            return 0.0
        return principal / float(periods)
    factor = (1.0 + rate) ** (float(periods))
    return principal * rate * factor / (factor - 1.0)






def sharpe_ratio(returns, risk_free_rate):
    n = len(returns)
    if n < 2:
        return 0.0

    sum_r = 0.0
    for i in range(n):
        sum_r += returns[i]
    mean = sum_r / float(n)

    sum_sq = 0.0
    for i in range(n):
        diff = returns[i] - mean
        sum_sq += diff * diff
    std_dev = math.sqrt(sum_sq / float(n))
    if std_dev < 1e-15:
        return 0.0
    return (mean - risk_free_rate) / std_dev






def max_drawdown(values):
    n = len(values)
    if n < 2:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for i in range(1, n):
        if values[i] > peak:
            peak = values[i]
        dd = (peak - values[i]) / peak if peak > 0.0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd






def cagr(start_value, end_value, years):
    if math.fabs(start_value) < 1e-15 or math.fabs(years) < 1e-15:
        return 0.0
    return (end_value / start_value) ** (1.0 / years) - 1.0






def wacc(equity, debt, cost_equity, cost_debt, tax_rate):
    total = equity + debt
    if math.fabs(total) < 1e-15:
        return 0.0
    e_weight = equity / total
    d_weight = debt / total
    return e_weight * cost_equity + d_weight * cost_debt * (1.0 - tax_rate)
