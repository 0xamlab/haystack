"""Python equivalent of mojo/engine/encoding.mojo (auto-generated)."""
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

def build_vocabulary(labels):
    vocab = []
    for i in range(len(labels)):
        found = False
        for j in range(len(vocab)):
            if vocab[j] == labels[i]:
                found = True
                break
        if not found:
            vocab.append(labels[i])
    return vocab






def label_encode(labels):
    vocab = build_vocabulary(labels)
    result = []
    for i in range(len(labels)):
        for j in range(len(vocab)):
            if vocab[j] == labels[i]:
                result.append(j)
                break
    return result






def label_decode(encoded, vocabulary):
    result = []
    for i in range(len(encoded)):
        idx = encoded[i]
        if idx >= 0 and idx < len(vocabulary):
            result.append(vocabulary[idx])
        else:
            result.append(str("?"))
    return result






def one_hot_encode(labels, n_classes):
    result = []
    for i in range(len(labels)):
        row = []
        for j in range(n_classes):
            if j == labels[i]:
                row.append(1.0)
            else:
                row.append(0.0)
        result.append(row)
    return result






def ordinal_encode(data, order):
    result = []
    for i in range(len(data)):
        found = False
        for j in range(len(order)):
            if order[j] == data[i]:
                result.append(j)
                found = True
                break
        if not found:
            result.append(-1)
    return result






def binary_encode(value, n_bits):
    result = []
    for _ in range(n_bits):
        result.append(0)

    v = value
    for i in range(n_bits):
        bit_pos = n_bits - 1 - i
        if v & (1 << bit_pos) != 0:
            result[i] = 1
    return result






def frequency_encode(labels):
    n = len(labels)
    result = []
    if n == 0:
        return result

    vocab = build_vocabulary(labels)
    counts = []
    for _ in range(len(vocab)):
        counts.append(0)

    for i in range(n):
        for j in range(len(vocab)):
            if vocab[j] == labels[i]:
                counts[j] = counts[j] + 1
                break

    total = float(n)
    for i in range(n):
        for j in range(len(vocab)):
            if vocab[j] == labels[i]:
                result.append(float(counts[j]) / total)
                break

    return result
