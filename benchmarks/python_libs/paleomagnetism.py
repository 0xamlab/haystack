"""Python equivalent of mojo/engine/paleomagnetism.mojo (auto-generated)."""
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
    from std.math import cos
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

def virtual_geomagnetic_pole_lat(inclination_deg):
    pi = 3.141592653589793
    i_rad = inclination_deg * pi / 180.0
    tan_lambda = 0.5 * (sin_approx(i_rad) / cos_approx(i_rad))
    lambda_rad = atan_approx(tan_lambda)
    return lambda_rad * 180.0 / pi



def sin_approx(x):
    x2 = x * x
    return x * (1.0 - x2 / 6.0 + x2 * x2 / 120.0)



def cos_approx(x):
    x2 = x * x
    return 1.0 - x2 / 2.0 + x2 * x2 / 24.0



def atan_approx(x):
    if x < 0.0:
        return -atan_approx(-x)
    if x > 1.0:
        pi_2 = 1.5707963267948966
        return pi_2 - atan_approx(1.0 / x)
    x2 = x * x
    return x * (1.0 - x2 / 3.0 + x2 * x2 / 5.0 - x2 * x2 * x2 / 7.0)



def paleolatitude(inclination_deg):
    pi = 3.141592653589793
    i_rad = inclination_deg * pi / 180.0
    tan_i = sin_approx(i_rad) / (cos_approx(i_rad) + 1e-15)
    return atan_approx(tan_i / 2.0) * 180.0 / pi



def geomagnetic_intensity(nrm, susceptibility):
    if susceptibility <= 0.0:
        return 0.0
    return nrm / susceptibility



def declination_correction(observed_dec, site_azimuth):
    return observed_dec - site_azimuth



def magnetic_reversal_rate(n_reversals, timespan_myr):
    if timespan_myr <= 0.0:
        return 0.0
    return n_reversals / timespan_myr



def koenigsberger_ratio(nrm, field_strength, susceptibility):
    induced = susceptibility * field_strength
    if induced <= 0.0:
        return 0.0
    return nrm / induced



def stability_index(nrm_before, nrm_after_heating):
    if nrm_before <= 0.0:
        return 0.0
    diff = nrm_after_heating - nrm_before
    if diff < 0.0:
        diff = -diff
    return diff / nrm_before



def rock_magnetic_susceptibility(measured_susceptibility, mass_g):
    if mass_g <= 0.0:
        return 0.0
    return measured_susceptibility / (mass_g * 1e-3) * 1e8



def anhysteretic_remanence(arm, bias_field_mt):
    if bias_field_mt <= 0.0:
        return 0.0
    return arm / bias_field_mt



def coercivity_spectrum_median(h_upper, h_lower):
    return (h_upper + h_lower) / 2.0
