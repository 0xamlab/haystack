"""Python equivalent of mojo/engine/population_genetics.mojo (auto-generated)."""
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

def hardy_weinberg_freq(p):
    if p < 0.0 or p > 1.0:
        return 0.0
    return 2.0 * p * (1.0 - p)



def allele_frequency_drift(p, effective_pop_size):
    if effective_pop_size <= 0.0 or p < 0.0 or p > 1.0:
        return 0.0
    q = 1.0 - p
    return math.sqrt(p * q / (2.0 * effective_pop_size))



def selection_coefficient(p, s, h):
    if p < 0.0 or p > 1.0:
        return 0.0
    q = 1.0 - p
    return s * p * q * (p + h * q)



def effective_population_size(n_female, n_male):
    denom = n_female + n_male
    if denom <= 0.0:
        return 0.0
    return 4.0 * n_female * n_male / denom



def nucleotide_diversity(n_sequences, pairwise_differences):
    if n_sequences < 2.0:
        return 0.0
    n_pairs = n_sequences * (n_sequences - 1.0) / 2.0
    return pairwise_differences / n_pairs



def tajimas_d_simplified(n, seg_sites, avg_pairwise_diff):
    if n <= 1.0 or seg_sites <= 0.0:
        return 0.0

    a1 = 0.0
    i = 1.0
    while i < n:
        a1 += 1.0 / i
        i += 1.0
    theta_w = seg_sites / a1

    norm = math.sqrt(seg_sites * 0.05 + 0.001)
    return (avg_pairwise_diff - theta_w) / norm



def fst_wright(ht, hs):
    if ht <= 0.0:
        return 0.0
    fst = (ht - hs) / ht
    if fst < 0.0:
        return 0.0
    return fst



def inbreeding_coefficient(p, observed_het):
    h_exp = 2.0 * p * (1.0 - p)
    if h_exp <= 0.0:
        return 0.0
    return 1.0 - observed_het / h_exp



def mutation_load(mutation_rate, dominance_h):
    if dominance_h < 0.0:
        return mutation_rate
    if dominance_h == 0.0:
        return mutation_rate
    return mutation_rate / (2.0 * dominance_h)



def linkage_disequilibrium(p_ab, p_a, p_b):
    return p_ab - p_a * p_b
