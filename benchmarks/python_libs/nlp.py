"""Python equivalent of mojo/engine/nlp.mojo (auto-generated)."""
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

def _is_ws(c):
    return c == 32 or c == 9 or c == 10 or c == 13  # space, tab, nl, cr



def _is_punct(c):
    return (c == 46 or c == 44 or c == 33 or c == 63 or c == 59   # . , ! ? ;
            or c == 58 or c == 40 or c == 41 or c == 91 or c == 93   # : ( ) [ ]
            or c == 123 or c == 125 or c == 34 or c == 39 or c == 45  # { } " ' -
            or c == 47 or c == 92 or c == 64 or c == 35 or c == 36   # / \ @ # $
            or c == 37 or c == 38 or c == 42 or c == 43 or c == 61   # % & * + =
            or c == 60 or c == 62 or c == 124 or c == 126 or c == 96  # < > | ~ `
            or c == 94)  # ^



def _to_lower_byte(c):
    if c >= 65 and c <= 90:
        return c + 32
    return c



def _contains_str(haystack, needle):
    for i in range(len(haystack)):
        if haystack[i] == needle:
            return True
    return False






def tokenize(text):
    tokens = []
    bs = text.encode('utf-8')
    n = len(text)
    start = -1
    for i in range(n):
        c = bs[i]
        if _is_ws(c) or _is_punct(c):
            if start >= 0:
                tok = str("")
                for j in range(start, i):
                    tok += chr(int(_to_lower_byte(bs[j])))
                tokens.append(tok)
                start = -1
        else:
            if start < 0:
                start = i
    if start >= 0:
        tok = str("")
        for j in range(start, n):
            tok += chr(int(_to_lower_byte(bs[j])))
        tokens.append(tok)
    return tokens






def ngrams(tokens, n):
    result = []
    sz = len(tokens)
    if n <= 0 or sz < n:
        return result
    for i in range(sz - n + 1):
        gram = tokens[i]
        for j in range(1, n):
            gram += "_" + tokens[i + j]
        result.append(gram)
    return result






def term_frequency(tokens):
    terms = []
    counts = []
    for i in range(len(tokens)):
        t = tokens[i]
        found = False
        for j in range(len(terms)):
            if terms[j] == t:
                counts[j] += 1
                found = True
                break
        if not found:
            terms.append(t)
            counts.append(1)

    for i in range(1, len(terms)):
        kc = counts[i]
        kt = terms[i]
        j = i - 1
        while j >= 0 and counts[j] < kc:
            counts[j + 1] = counts[j]
            terms[j + 1] = terms[j]
            j -= 1
        counts[j + 1] = kc
        terms[j + 1] = kt
    result = []
    for i in range(len(terms)):
        pair = []
        pair.append(terms[i])
        pair.append(str(counts[i]))
        result.append(pair)
    return result






def tf(term, tokens):
    n = len(tokens)
    if n == 0:
        return 0.0
    count = 0
    for i in range(n):
        if tokens[i] == term:
            count += 1
    return float(count) / float(n)






def cosine_similarity_vec(a, b):
    n = len(a)
    if n == 0 or len(b) != n:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        dot += a[i] * b[i]
        na += a[i] * a[i]
        nb += b[i] * b[i]
    denom = math.sqrt(na) * math.sqrt(nb)
    if denom < 1e-15:
        return 0.0
    return dot / denom






def jaccard_similarity(a, b):

    union_set = []
    intersection_count = 0

    for i in range(len(a)):
        if not _contains_str(union_set, a[i]):
            union_set.append(a[i])

    a_unique = []
    for i in range(len(a)):
        if not _contains_str(a_unique, a[i]):
            a_unique.append(a[i])
    for i in range(len(b)):
        if not _contains_str(union_set, b[i]):
            union_set.append(b[i])

    for i in range(len(a_unique)):
        for j in range(len(b)):
            if a_unique[i] == b[j]:
                intersection_count += 1
                break
    union_size = len(union_set)
    if union_size == 0:
        return 0.0
    return float(intersection_count) / float(union_size)






def word_count(text):
    count = 0
    in_word = False
    bs = text.encode('utf-8')
    n = len(text)
    for i in range(n):
        if _is_ws(bs[i]):
            if in_word:
                count += 1
                in_word = False
        else:
            in_word = True
    if in_word:
        count += 1
    return count






def char_count(text):
    count = 0
    bs = text.encode('utf-8')
    n = len(text)
    for i in range(n):
        if not _is_ws(bs[i]):
            count += 1
    return count






def unique_tokens(tokens):
    result = []
    for i in range(len(tokens)):
        if not _contains_str(result, tokens[i]):
            result.append(tokens[i])
    return result
