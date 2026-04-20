"""Python equivalent of mojo/engine/risk.mojo (auto-generated)."""
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

def _sort_copy(data):
    out = data.copy()
    n = len(out)
    for i in range(1, n):
        k = out[i]
        j = i - 1
        while j >= 0 and out[j] > k:
            out[j + 1] = out[j]
            j -= 1
        out[j + 1] = k
    return out






def _mean(data):
    n = len(data)
    if n == 0:
        return 0.0
    s = 0.0
    for i in range(n):
        s += data[i]
    return s / float(n)



def _std(data):
    n = len(data)
    if n < 2:
        return 0.0
    m = _mean(data)
    ss = 0.0
    for i in range(n):
        d = data[i] - m
        ss += d * d
    return math.sqrt(ss / float(n))



def _cov(a, b):
    n = len(a)
    if n < 2:
        return 0.0
    ma = _mean(a)
    mb = _mean(b)
    s = 0.0
    for i in range(n):
        s += (a[i] - ma) * (b[i] - mb)
    return s / float(n)



def _var(data):
    n = len(data)
    if n < 2:
        return 0.0
    m = _mean(data)
    ss = 0.0
    for i in range(n):
        d = data[i] - m
        ss += d * d
    return ss / float(n)






def value_at_risk(returns, confidence):
    n = len(returns)
    if n == 0:
        return 0.0
    sorted = _sort_copy(returns)
    idx_f = (1.0 - confidence) * float(n - 1)
    lo = int(idx_f)
    hi = lo + 1
    if hi >= n:
        return -sorted[n - 1]
    frac = idx_f - float(lo)
    val = sorted[lo] * (1.0 - frac) + sorted[hi] * frac
    return -val






def conditional_var(returns, confidence):
    n = len(returns)
    if n == 0:
        return 0.0
    var_val = value_at_risk(returns, confidence)
    threshold = -var_val  # The return level
    total = 0.0
    count = 0
    for i in range(n):
        if returns[i] <= threshold:
            total += returns[i]
            count += 1
    if count == 0:
        return var_val
    return -(total / float(count))






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






def drawdown_series(values):
    n = len(values)
    result = []
    if n == 0:
        return result
    peak = values[0]
    for i in range(n):
        if values[i] > peak:
            peak = values[i]
        dd = (peak - values[i]) / peak if peak > 0.0 else 0.0
        result.append(dd)
    return result






def sortino_ratio(returns, target=0.0):
    m = _mean(returns)
    dd = downside_deviation(returns, target)
    if dd < 1e-15:
        return 0.0
    return (m - target) / dd






def sharpe_ratio(returns, risk_free=0.0):
    m = _mean(returns)
    s = _std(returns)
    if s < 1e-15:
        return 0.0
    return (m - risk_free) / s






def beta(asset_returns, market_returns):
    v = _var(market_returns)
    if v < 1e-15:
        return 0.0
    return _cov(asset_returns, market_returns) / v






def alpha(asset_returns, market_returns, risk_free=0.0):
    b = beta(asset_returns, market_returns)
    ma = _mean(asset_returns)
    mm = _mean(market_returns)
    return ma - risk_free - b * (mm - risk_free)






def information_ratio(returns, benchmark):
    n = len(returns)
    if n == 0:
        return 0.0
    excess = []
    for i in range(n):
        excess.append(returns[i] - benchmark[i])
    m = _mean(excess)
    s = _std(excess)
    if s < 1e-15:
        return 0.0
    return m / s






def calmar_ratio(returns, values):
    mdd = max_drawdown(values)
    if mdd < 1e-15:
        return 0.0
    ann_ret = _mean(returns) * 252.0
    return ann_ret / mdd






def downside_deviation(returns, target=0.0):
    n = len(returns)
    if n == 0:
        return 0.0
    ss = 0.0
    for i in range(n):
        d = returns[i] - target
        if d < 0.0:
            ss += d * d
    return math.sqrt(ss / float(n))
