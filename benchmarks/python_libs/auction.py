"""Python equivalent of mojo/engine/auction.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import abs as fabs
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

def first_price_sealed(bids, n):
    if n <= 0:
        r = []
        r.append(-1.0)
        r.append(0.0)
        return r
    best_idx = 0
    best_val = bids[0]
    for i in range(1, n):
        if bids[i] > best_val:
            best_val = bids[i]
            best_idx = i
    result = []
    result.append(float(best_idx))
    result.append(best_val)
    return result






def second_price_sealed(bids, n):
    if n <= 0:
        r = []
        r.append(-1.0)
        r.append(0.0)
        return r
    best_idx = 0
    best_val = bids[0]
    second_val = 0.0
    for i in range(1, n):
        if bids[i] > best_val:
            second_val = best_val
            best_val = bids[i]
            best_idx = i
        elif bids[i] > second_val:
            second_val = bids[i]
    result = []
    result.append(float(best_idx))
    result.append(second_val)
    return result






def english_auction_revenue(bids, n):
    if n <= 0:
        return 0.0
    if n == 1:
        return bids[0]
    best = bids[0]
    second = 0.0
    for i in range(1, n):
        if bids[i] > best:
            second = best
            best = bids[i]
        elif bids[i] > second:
            second = bids[i]
    return second






def dutch_auction_revenue(bids, n):
    if n <= 0:
        return 0.0
    best = bids[0]
    for i in range(1, n):
        if bids[i] > best:
            best = bids[i]
    return best






def all_pay_revenue(bids, n):
    total = 0.0
    for i in range(n):
        total += bids[i]
    return total






def revenue_equivalence_check(bids, n):
    fp = dutch_auction_revenue(bids, n)  # first-price = highest bid
    sp = english_auction_revenue(bids, n)  # second-price = second highest
    if math.fabs(fp) < 1e-12 and math.fabs(sp) < 1e-12:
        return True
    avg = (fp + sp) / 2.0
    if math.fabs(avg) < 1e-12:
        return True
    return math.fabs(fp - sp) / avg < 0.2






def vcg_payment(values, n, winner_idx):
    max_other = 0.0
    for i in range(n):
        if i != winner_idx and values[i] > max_other:
            max_other = values[i]
    return max_other






def reserve_price_filter(bids, n, reserve):
    count = 0.0
    total = 0.0
    for i in range(n):
        if bids[i] >= reserve:
            count += 1.0
            total += bids[i]
    result = []
    result.append(count)
    result.append(total)
    return result






def bid_shading_optimal(value, n_bidders):
    if n_bidders <= 1:
        return 0.0
    return value * float(n_bidders - 1) / float(n_bidders)






def expected_revenue_uniform(n_bidders, max_val):
    if n_bidders <= 0:
        return 0.0
    return float(n_bidders - 1) / float(n_bidders + 1) * max_val






def winners_curse_adjustment(estimate, n_bidders):
    if n_bidders <= 1:
        return estimate
    return estimate * float(n_bidders - 1) / float(n_bidders)
