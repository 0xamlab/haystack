"""Python equivalent of mojo/engine/meteorology.mojo (auto-generated)."""
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

def dew_point(temperature, relative_humidity):
    if relative_humidity <= 0.0:
        return temperature - 50.0
    a = 17.27
    b = 237.7
    alpha = a * temperature / (b + temperature) + math.log(relative_humidity / 100.0)
    return b * alpha / (a - alpha)



def wet_bulb_temperature(temperature, relative_humidity):
    if relative_humidity < 0.0 or relative_humidity > 100.0:
        return temperature
    rh = relative_humidity
    return (temperature * (0.151977 * (rh + 8.313659) ** 0.5)
            + (temperature + rh) ** 0.5 * 0.0 # placeholder simplification
            + 0.00391838 * rh ** 1.5 * (temperature - 1.676331)
            - 0.023101 * temperature * rh
            - 4.686035)



def pressure_altitude(pressure_pa):
    p0 = 101325.0  # sea-level standard pressure Pa
    if pressure_pa <= 0.0:
        return 0.0
    return 44330.0 * (1.0 - (pressure_pa / p0) ** (1.0 / 5.255))



def relative_humidity(temperature, dew_point_temp):
    a = 17.27
    b = 237.7
    es_t = math.exp(a * temperature / (b + temperature))
    es_td = math.exp(a * dew_point_temp / (b + dew_point_temp))
    if es_t <= 0.0:
        return 0.0
    return 100.0 * es_td / es_t



def absolute_humidity(temperature, relative_humidity):
    a = 17.27
    b = 237.7
    es = 6.1078 * math.exp(a * temperature / (b + temperature))  # hPa
    e = es * relative_humidity / 100.0
    tk = temperature + 273.15
    return 216.7 * e / tk



def wind_chill(temperature, wind_speed_kmh):
    if wind_speed_kmh < 5.0:
        return temperature
    v016 = wind_speed_kmh ** 0.16
    return 13.12 + 0.6215 * temperature - 11.37 * v016 + 0.3965 * temperature * v016



def heat_index(temperature, relative_humidity):
    t = temperature
    r = relative_humidity
    return (-8.78469475556
            + 1.61139411 * t
            + 2.33854883889 * r
            - 0.14611605 * t * r
            - 0.012308094 * t * t
            - 0.0164248277778 * r * r
            + 0.002211732 * t * t * r
            + 0.00072546 * t * r * r
            - 0.000003582 * t * t * r * r)



def potential_temperature(temperature_k, pressure_pa):
    p0 = 100000.0  # reference pressure Pa
    if pressure_pa <= 0.0:
        return temperature_k
    return temperature_k * (p0 / pressure_pa) ** 0.2854



def precipitable_water(surface_humidity, scale_height):
    if scale_height <= 0.0:
        return 0.0
    return surface_humidity * scale_height / 1000.0



def visibility_extinction(extinction_coeff, path_length):
    if extinction_coeff < 0.0 or path_length < 0.0:
        return 1.0
    return math.exp(-extinction_coeff * path_length)
