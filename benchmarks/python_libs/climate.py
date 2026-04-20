"""Python equivalent of mojo/engine/climate.mojo (auto-generated)."""
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
    from std.math import exp
except Exception:
    pass
try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import pow
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

def celsius_to_fahrenheit(c):
    return c * 9.0 / 5.0 + 32.0






def fahrenheit_to_celsius(f):
    return (f - 32.0) * 5.0 / 9.0






def heat_index(temp_f, humidity):

    hi = 0.5 * (temp_f + 61.0 + (temp_f - 68.0) * 1.2 + humidity * 0.094)
    if hi < 80.0:
        return hi


    t = temp_f
    r = humidity
    hi = (
        -42.379
        + 2.04901523 * t
        + 10.14333127 * r
        - 0.22475541 * t * r
        - 0.00683783 * t * t
        - 0.05481717 * r * r
        + 0.00122874 * t * t * r
        + 0.00085282 * t * r * r
        - 0.00000199 * t * t * r * r
    )


    if r < 13.0 and t >= 80.0 and t <= 112.0:
        hi -= ((13.0 - r) / 4.0) * math.sqrt((17.0 - math.fabs(t - 95.0)) / 17.0)
    elif r > 85.0 and t >= 80.0 and t <= 87.0:
        hi += ((r - 85.0) / 10.0) * ((87.0 - t) / 5.0)

    return hi






def wind_chill(temp_f, wind_mph):
    if temp_f > 50.0 or wind_mph < 3.0:
        return temp_f
    v016 = (wind_mph) ** (0.16)
    return (
        35.74
        + 0.6215 * temp_f
        - 35.75 * v016
        + 0.4275 * temp_f * v016
    )






def saturation_vapor_pressure(temp_c):
    return 6.1078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))






def dew_point(temp_c, humidity):
    a = 17.27
    b = 237.3
    gamma = a * temp_c / (b + temp_c) + math.log(humidity / 100.0)
    return b * gamma / (a - gamma)






def wet_bulb_approx(temp_c, humidity):
    rh = humidity
    t = temp_c
    return (
        t * 0.151977 * math.sqrt(rh + 8.313659)
        + 0.00391838 * (rh) ** (1.5) * 0.023101
        + 0.023101 * rh
        - 4.686035
        + t * (0.151977 - 1.0 + 1.0)
        - t * 0.151977
    )






def relative_humidity(temp_c, dew_c):
    svp_t = saturation_vapor_pressure(temp_c)
    svp_d = saturation_vapor_pressure(dew_c)
    if svp_t < 1e-30:
        return 0.0
    return 100.0 * svp_d / svp_t






def apparent_temperature(temp_c, humidity, wind_ms):
    e = humidity / 100.0 * 6.105 * math.exp(17.27 * temp_c / (237.7 + temp_c))
    return temp_c + 0.33 * e - 0.70 * wind_ms - 4.00






def cloud_base_height(temp_c, dew_c):
    return (temp_c - dew_c) / 2.5 * 304.8






def pressure_altitude(station_pressure_hpa):
    return (1.0 - (station_pressure_hpa / 1013.25) ** (0.190284)) * 44307.694
