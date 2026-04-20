"""Python equivalent of mojo/engine/cryptanalysis.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log as _log
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

def _log2(x):
    return math.math.log(x) / math.math.log(2.0)



def _gcd(a_in, b_in):
    a = a_in
    b = b_in
    if a < 0:
        a = -a
    if b < 0:
        b = -b
    while b != 0:
        t = b
        b = a % b
        a = t
    return a



def _entropy_term(p):
    if p > 0.0:
        return -p * math.math.log2(p)
    return 0.0






def frequency_score_2(c0, c1, ef0, ef1):
    total = float(c0 + c1)
    e0 = ef0 * total
    e1 = ef1 * total
    score = 0.0
    if e0 > 0.0:
        d0 = float(c0) - e0
        score += (d0 * d0) / e0
    if e1 > 0.0:
        d1 = float(c1) - e1
        score += (d1 * d1) / e1
    return score






def index_of_coincidence_2(c0, c1, total):
    if total <= 1:
        return 0.0
    numerator = c0 * (c0 - 1) + c1 * (c1 - 1)
    return float(numerator) / float(total * (total - 1))






def expected_ic_random(alphabet_size):
    if alphabet_size <= 0:
        return 0.0
    return 1.0 / float(alphabet_size)






def expected_ic_english():
    return 0.0667






def friedman_key_length(ic, alphabet_size):
    kp = 0.0667
    kr = 1.0 / float(alphabet_size)
    denom = ic - kr
    if denom <= 0.0:
        return 1.0
    return (kp - kr) / denom






def kasiski_distance_gcd(d1, d2):
    return _gcd(d1, d2)






def caesar_decrypt_score(shift, expected_e_freq, actual_freq_at_e):
    diff = actual_freq_at_e - expected_e_freq
    if diff < 0.0:
        diff = -diff
    return diff






def hamming_distance_bytes(a, b):
    xor_val = a ^ b
    count = 0
    v = xor_val
    while v != 0:
        count += v & 1
        v = v >> 1
    return count






def entropy_bits_2(p0, p1):
    return _entropy_term(p0) + _entropy_term(p1)






def entropy_bits_4(p0, p1, p2, p3):
    return _entropy_term(p0) + _entropy_term(p1) + _entropy_term(p2) + _entropy_term(p3)






def brute_force_time_estimate(key_bits, ops_per_second):
    if ops_per_second <= 0.0:
        return 0.0
    keyspace = 1.0
    for _ in range(key_bits):
        keyspace *= 2.0
    return keyspace / ops_per_second






def avalanche_effect(changed_bits, total_bits):
    if total_bits <= 0:
        return 0.0
    return float(changed_bits) / float(total_bits)
