"""Python equivalent of mojo/engine/virology.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import exp
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

def basic_reproduction_number(beta, infectious_period, population):
    return beta * population * infectious_period



def viral_doubling_time(growth_rate):
    if growth_rate <= 0.0:
        return 0.0
    return math.log(2.0) / growth_rate



def plaque_forming_units(plaque_count, dilution, volume_ml):
    if dilution <= 0.0 or volume_ml <= 0.0:
        return 0.0
    return plaque_count / (dilution * volume_ml)



def burst_size(progeny_particles, initial_infected_cells):
    if initial_infected_cells <= 0.0:
        return 0.0
    return progeny_particles / initial_infected_cells



def eclipse_period(time_of_burst, adsorption_time):
    ep = time_of_burst - adsorption_time
    if ep < 0.0:
        return 0.0
    return ep



def neutralisation_titre(log2_dilution_at_50_inhibition):
    return (2.0) ** (log2_dilution_at_50_inhibition)



def antiviral_ic50(conc_high, conc_low, inhibition_high, inhibition_low):
    if inhibition_high == inhibition_low:
        return (conc_high + conc_low) / 2.0
    slope = (inhibition_high - inhibition_low) / (conc_high - conc_low)
    if slope == 0.0:
        return (conc_high + conc_low) / 2.0
    return conc_low + (50.0 - inhibition_low) / slope



def virus_decay_rate(initial_titre, final_titre, time):
    if final_titre <= 0.0 or initial_titre <= 0.0 or time <= 0.0:
        return 0.0
    return math.log(initial_titre / final_titre) / time



def infection_threshold(dose, id50, probit_slope):
    if id50 <= 0.0:
        return 0.0
    p = 0.5 + probit_slope * (dose - id50) / id50
    if p < 0.0:
        return 0.0
    if p > 1.0:
        return 1.0
    return p



def herd_immunity_threshold_viro(r0):
    if r0 <= 1.0:
        return 0.0
    return 1.0 - 1.0 / r0
