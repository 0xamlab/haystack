"""Python equivalent of mojo/engine/units.mojo (auto-generated)."""
import math
import random as _rng

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

def _length_factor(unit):
    if unit == "m":
        return 1.0
    if unit == "km":
        return 1000.0
    if unit == "mi":
        return 1609.344
    if unit == "ft":
        return 0.3048
    if unit == "in":
        return 0.0254
    if unit == "cm":
        return 0.01
    if unit == "mm":
        return 0.001
    if unit == "yd":
        return 0.9144
    if unit == "nm":
        return 1852.0
    return 1.0



def _mass_factor(unit):
    if unit == "kg":
        return 1.0
    if unit == "g":
        return 0.001
    if unit == "mg":
        return 0.000001
    if unit == "lb":
        return 0.45359237
    if unit == "oz":
        return 0.028349523125
    if unit == "ton":
        return 1000.0
    if unit == "st":
        return 6.35029318
    return 1.0



def _to_celsius(value, unit):
    if unit == "C":
        return value
    if unit == "F":
        return (value - 32.0) * 5.0 / 9.0
    if unit == "K":
        return value - 273.15
    return value



def _from_celsius(value_c, unit):
    if unit == "C":
        return value_c
    if unit == "F":
        return value_c * 9.0 / 5.0 + 32.0
    if unit == "K":
        return value_c + 273.15
    return value_c



def _time_factor(unit):
    if unit == "s":
        return 1.0
    if unit == "ms":
        return 0.001
    if unit == "us":
        return 0.000001
    if unit == "min":
        return 60.0
    if unit == "hr":
        return 3600.0
    if unit == "day":
        return 86400.0
    if unit == "week":
        return 604800.0
    if unit == "year":
        return 31557600.0  # Julian year (365.25 days)
    return 1.0



def _area_factor(unit):
    if unit == "m2":
        return 1.0
    if unit == "km2":
        return 1000000.0
    if unit == "ft2":
        return 0.09290304
    if unit == "acre":
        return 4046.8564224
    if unit == "hectare":
        return 10000.0
    return 1.0



def _volume_factor(unit):
    if unit == "L":
        return 1.0
    if unit == "mL":
        return 0.001
    if unit == "gal":
        return 3.785411784
    if unit == "qt":
        return 0.946352946
    if unit == "pt":
        return 0.473176473
    if unit == "cup":
        return 0.2365882365
    if unit == "m3":
        return 1000.0
    return 1.0



def _speed_factor(unit):
    if unit == "m/s":
        return 1.0
    if unit == "km/h":
        return 1000.0 / 3600.0  # 0.27778
    if unit == "mph":
        return 1609.344 / 3600.0  # 0.44704
    if unit == "knot":
        return 1852.0 / 3600.0  # 0.51444
    if unit == "ft/s":
        return 0.3048
    return 1.0



def _data_factor(unit):
    if unit == "B":
        return 1.0
    if unit == "KB":
        return 1024.0
    if unit == "MB":
        return 1048576.0
    if unit == "GB":
        return 1073741824.0
    if unit == "TB":
        return 1099511627776.0
    if unit == "PB":
        return 1125899906842624.0
    return 1.0



def convert_length(value, from_unit, to_unit):
    return value * (_length_factor(from_unit) / _length_factor(to_unit))






def convert_mass(value, from_unit, to_unit):
    return value * (_mass_factor(from_unit) / _mass_factor(to_unit))






def convert_temperature(value, from_unit, to_unit):
    celsius = _to_celsius(value, from_unit)
    return _from_celsius(celsius, to_unit)






def convert_time(value, from_unit, to_unit):
    return value * (_time_factor(from_unit) / _time_factor(to_unit))






def convert_area(value, from_unit, to_unit):
    return value * (_area_factor(from_unit) / _area_factor(to_unit))






def convert_volume(value, from_unit, to_unit):
    return value * (_volume_factor(from_unit) / _volume_factor(to_unit))






def convert_speed(value, from_unit, to_unit):
    return value * (_speed_factor(from_unit) / _speed_factor(to_unit))






def convert_data(value, from_unit, to_unit):
    return value * (_data_factor(from_unit) / _data_factor(to_unit))
