"""Python equivalent of mojo/engine/immunology.mojo (auto-generated)."""
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

def antibody_titer(dilution_factor, od_ratio):
    if dilution_factor <= 0.0 or od_ratio <= 0.0:
        return 0.0
    return 1.0 / (dilution_factor * od_ratio)



def seroconversion_rate(n_seroconverted, n_total):
    if n_total <= 0.0:
        return 0.0
    return n_seroconverted / n_total



def antigen_antibody_binding(ka, antigen_conc, antibody_conc):
    denom = 1.0 + ka * antibody_conc
    if denom <= 0.0:
        return 0.0
    return ka * antibody_conc / denom



def complement_activation(antibody_conc, threshold, rate_constant):
    if antibody_conc <= threshold:
        return 0.0
    return rate_constant * (antibody_conc - threshold)



def t_cell_proliferation(n0, max_cells, growth_rate, time):
    if max_cells <= 0.0 or n0 <= 0.0:
        return n0
    ratio = (max_cells - n0) / n0
    denom = 1.0 + ratio * math.exp(-growth_rate * time)
    if denom <= 0.0:
        return max_cells
    return max_cells / denom



def innate_response_decay(c0, decay_rate, time):
    if c0 < 0.0 or decay_rate < 0.0:
        return c0
    return c0 * math.exp(-decay_rate * time)



def vaccine_efficacy(attack_rate_vaccinated, attack_rate_unvaccinated):
    if attack_rate_unvaccinated <= 0.0:
        return 0.0
    rr = attack_rate_vaccinated / attack_rate_unvaccinated
    return 1.0 - rr



def herd_immunity_threshold(r0):
    if r0 <= 1.0:
        return 0.0
    return 1.0 - 1.0 / r0



def antibody_avidity_index(od_urea, od_pbs):
    if od_pbs <= 0.0:
        return 0.0
    return (od_urea / od_pbs) * 100.0



def opsonisation_index(phagocytosis_immune, phagocytosis_control):
    if phagocytosis_control <= 0.0:
        return 0.0
    return (phagocytosis_immune / phagocytosis_control) - 1.0
