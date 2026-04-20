"""Python equivalent of mojo/engine/distillation.mojo (auto-generated)."""
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
    from std.math import exp
except Exception:
    pass
try:
    from std.math import abs
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

def relative_volatility(y1, x1):
    if x1 <= 0.0 or x1 >= 1.0 or y1 <= 0.0 or y1 >= 1.0:
        return 0.0
    return (y1 / (1.0 - y1)) / (x1 / (1.0 - x1))



def min_reflux_underwood(alpha, xd, xf, q):
    if abs(alpha - 1.0) < 1e-15:
        return 0.0
    return (alpha * xd - xf) / (alpha - 1.0)



def actual_reflux(rmin, factor):
    return rmin * factor



def fenske_min_stages(xd, xb, alpha):
    if alpha <= 1.0 or xd <= 0.0 or xd >= 1.0 or xb <= 0.0 or xb >= 1.0:
        return 0.0
    numerator = math.log((xd / (1.0 - xd)) * ((1.0 - xb) / xb))
    denominator = math.log(alpha)
    if abs(denominator) < 1e-15:
        return 0.0
    return numerator / denominator



def gilliland_stages(nmin, rmin, r):
    if r + 1.0 == 0.0:
        return nmin
    x_val = (r - rmin) / (r + 1.0)
    if x_val < 0.0:
        x_val = 0.0
    if x_val > 1.0:
        x_val = 1.0
    y_val = 0.75 * math.exp(0.566 * math.log(1.0 - x_val)) if (1.0 - x_val) > 0.0 else 0.0
    return nmin + (nmin + 1.0) * y_val



def mccabe_thiele_operating_line_enriching(r, xd, x):
    if r + 1.0 == 0.0:
        return 0.0
    return (r / (r + 1.0)) * x + xd / (r + 1.0)



def mccabe_thiele_operating_line_stripping(r, xd, xb, x, f_ratio):
    if r + 1.0 == 0.0:
        return 0.0
    return ((r + f_ratio) / (r + 1.0)) * x - (xb * (f_ratio - 1.0)) / (r + 1.0)



def boiling_point_elevation(kb, molality):
    return kb * molality



def raoults_law_partial_pressure(x, psat):
    return x * psat



def daltons_law_total_pressure(p1, p2):
    return p1 + p2



def stage_efficiency(y_actual, y_equilibrium, y_in):
    denom = y_equilibrium - y_in
    if abs(denom) < 1e-15:
        return 0.0
    return (y_actual - y_in) / denom * 100.0



def heat_duty_condenser(v_rate, latent_heat):
    return v_rate * latent_heat
