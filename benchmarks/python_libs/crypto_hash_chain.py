"""Python equivalent of mojo/engine/crypto.hash_chain.mojo (auto-generated)."""
import math
import random as _rng

FNV_OFFSET = 2166136261
FNV_PRIME = 16777619
MASK_32 = 0xFFFFFFFF

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

def _next_level(level):
    result = []
    padded = []
    for i in range(len(level)):
        padded.append(level[i])

    if len(padded) % 2 == 1:
        padded.append(padded[len(padded) - 1])
    i = 0
    while i < len(padded):
        result.append(combine_hashes(padded[i], padded[i + 1]))
        i += 2
    return result



def simple_hash(data):
    h = FNV_OFFSET
    for i in range(len(data)):
        h = h ^ (data[i] & 0xFF)
        h = (h * FNV_PRIME) & MASK_32
    return h



def int_to_bytes(value):
    result = []
    v = value & MASK_32
    result.append((v >> 24) & 0xFF)
    result.append((v >> 16) & 0xFF)
    result.append((v >> 8) & 0xFF)
    result.append(v & 0xFF)
    return result



def hash_single(value):
    return simple_hash(int_to_bytes(value))



def combine_hashes(a, b):
    data = []
    a_bytes = int_to_bytes(a)
    b_bytes = int_to_bytes(b)
    for i in range(len(a_bytes)):
        data.append(a_bytes[i])
    for i in range(len(b_bytes)):
        data.append(b_bytes[i])
    return simple_hash(data)






def hash_chain_build(items):
    chain = []
    if len(items) == 0:
        return chain
    chain.append(simple_hash(items[0]))
    for i in range(1, len(items)):
        prev_bytes = int_to_bytes(chain[i - 1])
        combined = []
        for j in range(len(prev_bytes)):
            combined.append(prev_bytes[j])
        for j in range(len(items[i])):
            combined.append(items[i][j])
        chain.append(simple_hash(combined))
    return chain



def hash_chain_verify(items, chain):
    if len(items) != len(chain):
        return False
    if len(items) == 0:
        return True
    expected = simple_hash(items[0])
    if expected != chain[0]:
        return False
    for i in range(1, len(items)):
        prev_bytes = int_to_bytes(chain[i - 1])
        combined = []
        for j in range(len(prev_bytes)):
            combined.append(prev_bytes[j])
        for j in range(len(items[i])):
            combined.append(items[i][j])
        expected = simple_hash(combined)
        if expected != chain[i]:
            return False
    return True






def merkle_root(leaves):
    if len(leaves) == 0:
        return 0
    if len(leaves) == 1:
        return leaves[0]
    current = []
    for i in range(len(leaves)):
        current.append(leaves[i])
    while len(current) > 1:
        current = _next_level(current)
    return current[0]



def merkle_proof(leaves, index):
    proof = []
    if len(leaves) <= 1:
        return proof
    current = []
    for i in range(len(leaves)):
        current.append(leaves[i])
    idx = index
    while len(current) > 1:

        if len(current) % 2 == 1:
            current.append(current[len(current) - 1])

        if idx % 2 == 0:
            proof.append(current[idx + 1])
        else:
            proof.append(current[idx - 1])

        next_level = []
        i = 0
        while i < len(current):
            next_level.append(combine_hashes(current[i], current[i + 1]))
            i += 2
        current = next_level
        idx = idx // 2
    return proof



def merkle_verify(leaf_hash, proof, index, root):
    current = leaf_hash
    idx = index
    for i in range(len(proof)):
        if idx % 2 == 0:
            current = combine_hashes(current, proof[i])
        else:
            current = combine_hashes(proof[i], current)
        idx = idx // 2
    return current == root
