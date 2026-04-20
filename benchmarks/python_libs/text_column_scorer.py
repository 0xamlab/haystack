"""Python equivalent of mojo/engine/text.column_scorer.mojo (auto-generated)."""
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

def _to_tokens(s):
    result = []
    current = str("")

    s_bytes = s.encode('utf-8')
    n = len(s_bytes)

    for i in range(n):
        b = s_bytes[i]
        if b == 95 or b == 32 or b == 45:
            if len(current) > 0:
                result.append(current)
                current = str("")
        else:
            current = current + chr(int(b))

    if len(current) > 0:
        result.append(current)

    return result



def _count_shared_tokens(a_tokens, b_tokens):
    count = 0
    for i in range(len(a_tokens)):
        for j in range(len(b_tokens)):
            if a_tokens[i] == b_tokens[j]:
                count += 1
                break
    return count



def _ngrams(s, n):
    result = []
    s_len = len(s)
    if s_len < n:
        return result
    s_bytes = s.encode('utf-8')
    for i in range(s_len - n + 1):
        gram = str("")
        for j in range(n):
            gram = gram + chr(int(s_bytes[i + j]))
        result.append(gram)
    return result



def _count_shared_ngrams(a_grams, b_grams):
    count = 0
    b_used = []
    for _ in range(len(b_grams)):
        b_used.append(False)

    for i in range(len(a_grams)):
        for j in range(len(b_grams)):
            if not b_used[j] and a_grams[i] == b_grams[j]:
                count += 1
                b_used[j] = True
                break
    return count






def score_token_overlap(hint, col):
    a_toks = _to_tokens(hint)
    b_toks = _to_tokens(col)

    a_n = len(a_toks)
    b_n = len(b_toks)

    if a_n == 0 and b_n == 0:
        return 1.0
    if a_n == 0 or b_n == 0:
        return 0.0

    shared = _count_shared_tokens(a_toks, b_toks)
    union = a_n + b_n - shared
    if union == 0:
        return 0.0
    return float(shared) / float(union)






def score_ngram_overlap(hint, col, n=2):
    a_grams = _ngrams(hint, n)
    b_grams = _ngrams(col, n)

    a_n = len(a_grams)
    b_n = len(b_grams)

    if a_n == 0 and b_n == 0:
        return 1.0
    if a_n == 0 or b_n == 0:
        return 0.0

    shared = _count_shared_ngrams(a_grams, b_grams)
    return 2.0 * float(shared) / float(a_n + b_n)






def score_prefix_match(hint, col):
    la = len(hint)
    lb = len(col)
    if la == 0:
        return 1.0
    if lb == 0:
        return 0.0

    a_bytes = hint.encode('utf-8')
    b_bytes = col.encode('utf-8')

    common = 0
    max_compare = la
    if lb < max_compare:
        max_compare = lb

    for i in range(max_compare):
        if a_bytes[i] == b_bytes[i]:
            common += 1
        else:
            break

    return float(common) / float(la)






def score_column_hint(hint, col, token_weight=0.50, ngram_weight=0.30, prefix_weight=0.20):
    if len(hint) == 0 and len(col) == 0:
        return 1.0
    if len(hint) == 0 or len(col) == 0:
        return 0.0

    tok = score_token_overlap(hint, col)
    ngram = score_ngram_overlap(hint, col, 2)
    pref = score_prefix_match(hint, col)

    score = token_weight * tok + ngram_weight * ngram + prefix_weight * pref

    if score > 1.0:
        return 1.0
    if score < 0.0:
        return 0.0
    return score
