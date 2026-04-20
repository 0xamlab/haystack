"""Python equivalent of mojo/engine/crypto.chacha20.mojo (auto-generated)."""
import math
import random as _rng

MASK32 = 0xFFFFFFFF
CONST0 = 0x61707865
CONST1 = 0x3320646E
CONST2 = 0x79622D32
CONST3 = 0x6B206574

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

def _words_to_bytes(words):
    result = []
    for i in range(len(words)):
        w = words[i] & MASK32
        result.append(w & 0xFF)
        result.append((w >> 8) & 0xFF)
        result.append((w >> 16) & 0xFF)
        result.append((w >> 24) & 0xFF)
    return result






def rotl32(value, shift):
    v = value & MASK32
    s = shift & 31
    return ((v << s) | (v >> (32 - s))) & MASK32






def quarter_round(state, a, b, c, d):
    state[a] = (state[a] + state[b]) & MASK32
    state[d] = rotl32(state[d] ^ state[a], 16)
    state[c] = (state[c] + state[d]) & MASK32
    state[b] = rotl32(state[b] ^ state[c], 12)
    state[a] = (state[a] + state[b]) & MASK32
    state[d] = rotl32(state[d] ^ state[a], 8)
    state[c] = (state[c] + state[d]) & MASK32
    state[b] = rotl32(state[b] ^ state[c], 7)






def chacha20_init_state(key, counter, nonce):
    state = []
    state.append(CONST0)
    state.append(CONST1)
    state.append(CONST2)
    state.append(CONST3)
    for i in range(8):
        state.append(key[i] & MASK32)
    state.append(counter & MASK32)
    for i in range(3):
        state.append(nonce[i] & MASK32)
    return state






def add_states(a, b):
    n = len(a)
    result = []
    for i in range(n):
        result.append((a[i] + b[i]) & MASK32)
    return result






def xor_states(a, b):
    n = len(a)
    result = []
    for i in range(n):
        result.append((a[i] ^ b[i]) & MASK32)
    return result






def chacha20_block(key, counter, nonce):
    initial = chacha20_init_state(key, counter, nonce)
    state = []
    for i in range(16):
        state.append(initial[i])

    for round_i in range(10):
        quarter_round(state, 0, 4, 8, 12)
        quarter_round(state, 1, 5, 9, 13)
        quarter_round(state, 2, 6, 10, 14)
        quarter_round(state, 3, 7, 11, 15)
        quarter_round(state, 0, 5, 10, 15)
        quarter_round(state, 1, 6, 11, 12)
        quarter_round(state, 2, 7, 8, 13)
        quarter_round(state, 3, 4, 9, 14)

    return add_states(state, initial)






def chacha20_encrypt(plaintext, key, nonce):
    n = len(plaintext)
    result = []
    counter = 0
    pos = 0

    while pos < n:
        block = chacha20_block(key, counter, nonce)
        keystream = _words_to_bytes(block)
        ks_len = len(keystream)
        for i in range(ks_len):
            if pos >= n:
                break
            result.append((plaintext[pos] ^ keystream[i]) & 0xFF)
            pos += 1
        counter += 1

    return result






def chacha20_decrypt(ciphertext, key, nonce):
    return chacha20_encrypt(ciphertext, key, nonce)
