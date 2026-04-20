"""Python equivalent of mojo/engine/silviculture.mojo (auto-generated)."""
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

def basal_area(dbh_cm):
    if dbh_cm <= 0.0:
        return 0.0
    pi = 3.141592653589793
    r = dbh_cm / 2.0
    return pi * r * r



def stand_basal_area(mean_dbh_cm, stems_per_ha):
    if mean_dbh_cm <= 0.0 or stems_per_ha <= 0.0:
        return 0.0
    pi = 3.141592653589793
    r_m = mean_dbh_cm / 200.0  # cm → m, then /2 for radius
    return pi * r_m * r_m * stems_per_ha



def site_index(height_m, age_years, base_age):
    if age_years <= 0.0 or height_m <= 0.0:
        return 0.0
    return height_m * (base_age / age_years) ** (0.5)



def volume_scribner(small_end_diameter_in, log_length_ft):
    if small_end_diameter_in <= 0.0 or log_length_ft <= 0.0:
        return 0.0
    d = small_end_diameter_in
    return (0.79 * d * d - 2.0 * d - 4.0) * log_length_ft / 16.0



def timber_yield_per_ha(stems_per_ha, mean_vol_m3_per_tree):
    if stems_per_ha < 0.0 or mean_vol_m3_per_tree < 0.0:
        return 0.0
    return stems_per_ha * mean_vol_m3_per_tree



def relative_density_index(stems_per_ha, mean_dbh_cm):
    if stems_per_ha <= 0.0 or mean_dbh_cm <= 0.0:
        return 0.0
    return stems_per_ha / (25.4 / mean_dbh_cm) ** (1.6)



def reineke_sdi(stems_per_ha, mean_dbh_cm):
    if stems_per_ha <= 0.0 or mean_dbh_cm <= 0.0:
        return 0.0
    return stems_per_ha * (25.4 / mean_dbh_cm) ** (1.605)



def mean_annual_increment(total_volume_m3, age_years):
    if age_years <= 0.0:
        return 0.0
    return total_volume_m3 / age_years



def current_annual_increment(vol_now, vol_past, years):
    if years <= 0.0:
        return 0.0
    return (vol_now - vol_past) / years



def thinning_ratio(initial_stems, target_stems):
    if initial_stems <= 0.0:
        return 0.0
    removed = initial_stems - target_stems
    if removed < 0.0:
        return 0.0
    return removed / initial_stems
