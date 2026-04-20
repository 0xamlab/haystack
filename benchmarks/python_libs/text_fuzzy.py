"""Python equivalent of mojo/engine/text.fuzzy.mojo (auto-generated)."""
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

def levenshtein_distance(a, b):
    m = len(a)
    n = len(b)
    if m == 0:
        return n
    if n == 0:
        return m

    a_bytes = a.encode('utf-8')
    b_bytes = b.encode('utf-8')


    prev = []
    curr = []
    for j in range(n + 1):
        prev.append(j)
        curr.append(0)

    for i in range(1, m + 1):
        curr[0] = i
        for j in range(1, n + 1):
            cost = 0
            if a_bytes[i - 1] != b_bytes[j - 1]:
                cost = 1
            del_cost = prev[j] + 1
            ins_cost = curr[j - 1] + 1
            sub_cost = prev[j - 1] + cost
            best = del_cost
            if ins_cost < best:
                best = ins_cost
            if sub_cost < best:
                best = sub_cost
            curr[j] = best

        for j in range(n + 1):
            tmp = prev[j]
            prev[j] = curr[j]
            curr[j] = tmp

    return prev[n]






def normalized_levenshtein(a, b):
    la = len(a)
    lb = len(b)
    if la == 0 and lb == 0:
        return 1.0
    max_len = la
    if lb > max_len:
        max_len = lb
    dist = levenshtein_distance(a, b)
    return 1.0 - float(dist) / float(max_len)






def jaro_similarity(a, b):
    la = len(a)
    lb = len(b)
    if la == 0 and lb == 0:
        return 1.0
    if la == 0 or lb == 0:
        return 0.0

    a_bytes = a.encode('utf-8')
    b_bytes = b.encode('utf-8')

    max_len = la
    if lb > max_len:
        max_len = lb
    match_window = max_len // 2 - 1
    if match_window < 0:
        match_window = 0


    a_matched = []
    b_matched = []
    for _ in range(la):
        a_matched.append(False)
    for _ in range(lb):
        b_matched.append(False)

    matches = 0
    transpositions = 0


    for i in range(la):
        low = i - match_window
        if low < 0:
            low = 0
        high = i + match_window + 1
        if high > lb:
            high = lb
        for j in range(low, high):
            if not b_matched[j] and a_bytes[i] == b_bytes[j]:
                a_matched[i] = True
                b_matched[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0


    k = 0
    for i in range(la):
        if a_matched[i]:
            while not b_matched[k]:
                k += 1
            if a_bytes[i] != b_bytes[k]:
                transpositions += 1
            k += 1

    t = float(transpositions) / 2.0
    m = float(matches)
    return (m / float(la) + m / float(lb) + (m - t) / m) / 3.0






def jaro_winkler_similarity(a, b, prefix_weight=0.1):
    jaro = jaro_similarity(a, b)


    la = len(a)
    lb = len(b)
    max_prefix = 4
    if la < max_prefix:
        max_prefix = la
    if lb < max_prefix:
        max_prefix = lb

    a_bytes = a.encode('utf-8')
    b_bytes = b.encode('utf-8')
    prefix_len = 0
    for i in range(max_prefix):
        if a_bytes[i] == b_bytes[i]:
            prefix_len += 1
        else:
            break

    return jaro + float(prefix_len) * prefix_weight * (1.0 - jaro)






def hamming_distance(a, b):
    la = len(a)
    lb = len(b)
    if la != lb:
        raise Error("hamming_distance: strings must be equal length")

    a_bytes = a.encode('utf-8')
    b_bytes = b.encode('utf-8')
    dist = 0
    for i in range(la):
        if a_bytes[i] != b_bytes[i]:
            dist += 1
    return dist






def longest_common_subsequence(a, b):
    m = len(a)
    n = len(b)
    if m == 0 or n == 0:
        return 0

    a_bytes = a.encode('utf-8')
    b_bytes = b.encode('utf-8')


    prev = []
    curr = []
    for _ in range(n + 1):
        prev.append(0)
        curr.append(0)

    for i in range(1, m + 1):
        curr[0] = 0
        for j in range(1, n + 1):
            if a_bytes[i - 1] == b_bytes[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                top = prev[j]
                left = curr[j - 1]
                if top > left:
                    curr[j] = top
                else:
                    curr[j] = left
        for j in range(n + 1):
            prev[j] = curr[j]

    return prev[n]






def fuzzy_ratio(a, b):
    la = len(a)
    lb = len(b)
    if la == 0 and lb == 0:
        return 1.0
    if la == 0 or lb == 0:
        return 0.0
    lcs = longest_common_subsequence(a, b)
    return 2.0 * float(lcs) / float(la + lb)
