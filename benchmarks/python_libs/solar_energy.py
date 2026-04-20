"""Python equivalent of mojo/engine/solar_energy.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sin
except Exception:
    pass
try:
    from std.math import cos
except Exception:
    pass
try:
    from std.math import sqrt
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
    from std.math import abs as fabs
except Exception:
    pass

PI = 3.141592653589793
DEG2RAD = 3.141592653589793 / 180.0

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

def solar_irradiance_on_surface(ghi, cos_incidence):
    return ghi * cos_incidence






def panel_power_output(area, efficiency, irradiance):
    return area * efficiency * irradiance






def temperature_derate(pmax_stc, temp_coeff, cell_temp, stc_temp):
    return pmax_stc * (1.0 + temp_coeff * (cell_temp - stc_temp))






def cell_temperature_noct(ambient, noct, irradiance):
    return ambient + (noct - 20.0) / 800.0 * irradiance






def solar_declination(day_of_year):
    return 23.45 * math.sin(2.0 * math.pi * (284.0 + day_of_year) / 365.0)






def hour_angle(solar_time_hours):
    return 15.0 * (solar_time_hours - 12.0)






def solar_altitude(latitude, declination, hour_ang):
    lat_r = latitude * DEG2RAD
    dec_r = declination * DEG2RAD
    ha_r = hour_ang * DEG2RAD
    sin_alt = math.sin(lat_r) * math.sin(dec_r) + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha_r)

    if sin_alt > 1.0:
        sin_alt = 1.0
    if sin_alt < -1.0:
        sin_alt = -1.0














    abs_x = math.fabs(sin_alt)
    result = 0.0
    if abs_x <= 1.0:

        x2 = abs_x * abs_x
        result = abs_x * (1.0 + x2 * (1.0 / 6.0 + x2 * (3.0 / 40.0 + x2 * (15.0 / 336.0 + x2 * 105.0 / 3456.0))))

        if abs_x > 0.7:
            complement = math.sqrt(1.0 - x2)
            c2 = complement * complement
            asin_c = complement * (1.0 + c2 * (1.0 / 6.0 + c2 * (3.0 / 40.0 + c2 * (15.0 / 336.0 + c2 * 105.0 / 3456.0))))
            result = math.pi / 2.0 - asin_c
    if sin_alt < 0.0:
        result = -result
    return result / DEG2RAD






def capacity_factor_solar(annual_kwh, rated_kw, hours_year):
    denom = rated_kw * hours_year
    if math.fabs(denom) < 1e-30:
        return 0.0
    return annual_kwh / denom






def lcoe(total_cost, total_energy):
    if math.fabs(total_energy) < 1e-30:
        return 0.0
    return total_cost / total_energy






def payback_period(system_cost, annual_savings):
    if math.fabs(annual_savings) < 1e-30:
        return 0.0
    return system_cost / annual_savings






def inverter_efficiency(ac_output, dc_input):
    if math.fabs(dc_input) < 1e-30:
        return 0.0
    return ac_output / dc_input






def string_voltage(modules_in_series, vmp):
    return modules_in_series * vmp
