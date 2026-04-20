"""Python equivalent of mojo/engine/photovoltaics.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import cos
except Exception:
    pass
try:
    from std.math import exp
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

def cell_efficiency(p_max, irradiance, area):
    if irradiance <= 0.0 or area <= 0.0:
        return 0.0
    return p_max / (irradiance * area)



def fill_factor(p_max, voc, isc):
    if voc <= 0.0 or isc <= 0.0:
        return 0.0
    return p_max / (voc * isc)



def power_output(efficiency, irradiance, area):
    return efficiency * irradiance * area



def temperature_coefficient(p_stc, gamma, cell_temp):
    return p_stc * (1.0 + gamma * (cell_temp - 25.0))



def energy_yield(peak_power_kw, peak_sun_hours, pr):
    return peak_power_kw * peak_sun_hours * pr * 365.0



def irradiance_on_tilted_plane(g_horizontal, tilt_rad, sun_zenith_rad):
    if g_horizontal <= 0.0:
        return 0.0
    cos_incidence = math.cos(tilt_rad) * math.cos(sun_zenith_rad)
    if cos_incidence < 0.0:
        return 0.0
    return g_horizontal * cos_incidence / (math.cos(sun_zenith_rad) + 1e-10)



def lcoe_solar(capex, opex_annual, energy_annual, lifetime_years, discount_rate):
    if energy_annual <= 0.0 or lifetime_years <= 0.0:
        return 0.0

    r = discount_rate
    n = lifetime_years
    crf = 0.0
    if r <= 0.0:
        crf = 1.0 / n
    else:
        rn = (1.0 + r) ** n
        crf = r * rn / (rn - 1.0)
    total_cost = capex * crf + opex_annual
    return total_cost / energy_annual



def capacity_factor(actual_energy, installed_kw, hours):
    theoretical = installed_kw * hours
    if theoretical <= 0.0:
        return 0.0
    return actual_energy / theoretical



def peak_sun_hours(daily_irradiation):
    return daily_irradiation / 1000.0



def system_pr(actual_yield, reference_yield):
    if reference_yield <= 0.0:
        return 0.0
    return actual_yield / reference_yield
