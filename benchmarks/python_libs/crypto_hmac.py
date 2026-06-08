"""Python equivalent of mojo/engine/crypto.hmac.mojo (auto-generated)."""
import math
import random as _rng

try:
    from sha256 import _compress
except Exception:
    pass

_BLOCK_SIZE = 64   # SHA-256 block size in bytes
_HASH_SIZE = 32    # SHA-256 output size in bytes
_IPAD_BYTE = 0x36
_OPAD_BYTE = 0x5C

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

def _sha256_of_bytes(data):

    h = []
    h.append(0x6a09e667); h.append(0xbb67ae85)
    h.append(0x3c6ef372); h.append(0xa54ff53a)
    h.append(0x510e527f); h.append(0x9b05688c)
    h.append(0x1f83d9ab); h.append(0x5be0cd19)

    msg_len = len(data)


    pos = 0
    while pos + 64 <= msg_len:
        _compress(data, pos, h)
        pos += 64


    buf = []

    while pos < msg_len:
        buf.append(data[pos])
        pos += 1


    buf.append(0x80)

    while len(buf) % 64 != 56:
        buf.append(0)

    bit_len = int(msg_len) * 8
    buf.append(int(int((bit_len >> 56) & 0xFF)))
    buf.append(int(int((bit_len >> 48) & 0xFF)))
    buf.append(int(int((bit_len >> 40) & 0xFF)))
    buf.append(int(int((bit_len >> 32) & 0xFF)))
    buf.append(int(int((bit_len >> 24) & 0xFF)))
    buf.append(int(int((bit_len >> 16) & 0xFF)))
    buf.append(int(int((bit_len >> 8) & 0xFF)))
    buf.append(int(int(bit_len & 0xFF)))


    off = 0
    while off < len(buf):
        _compress(buf, off, h)
        off += 64


    result = []
    for i in range(8):
        w = h[i]
        result.append(int(int((w >> 24) & 0xFF)))
        result.append(int(int((w >> 16) & 0xFF)))
        result.append(int(int((w >> 8) & 0xFF)))
        result.append(int(int(w & 0xFF)))
    return result



def _bytes_to_hex(data):
    result = str("")
    for i in range(len(data)):
        b = int(data[i])

        hi = (b >> 4) & 0x0F
        if hi < 10:
            result += chr(48 + hi)
        else:
            result += chr(87 + hi)

        lo = b & 0x0F
        if lo < 10:
            result += chr(48 + lo)
        else:
            result += chr(87 + lo)
    return result





def hmac_sha256(key, message):

    key_bytes = []
    raw_key = key.encode('utf-8')
    key_len = len(key)

    if key_len > _BLOCK_SIZE:

        hashed = []
        for i in range(key_len):
            hashed.append(raw_key[i])
        hk = _sha256_of_bytes(hashed)
        for i in range(len(hk)):
            key_bytes.append(hk[i])
    else:
        for i in range(key_len):
            key_bytes.append(raw_key[i])


    while len(key_bytes) < _BLOCK_SIZE:
        key_bytes.append(0)



    msg_bytes = message.encode('utf-8')
    msg_len = len(message)
    inner_data = []

    for i in range(_BLOCK_SIZE):
        inner_data.append(key_bytes[i] ^ int(_IPAD_BYTE))
    for i in range(msg_len):
        inner_data.append(msg_bytes[i])

    inner_hash = _sha256_of_bytes(inner_data)  # 32 raw bytes



    outer_data = []

    for i in range(_BLOCK_SIZE):
        outer_data.append(key_bytes[i] ^ int(_OPAD_BYTE))
    for i in range(len(inner_hash)):
        outer_data.append(inner_hash[i])

    outer_hash = _sha256_of_bytes(outer_data)  # 32 raw bytes


    return _bytes_to_hex(outer_hash)



def hmac_sha256_verify(key, message, expected_hex):
    computed = hmac_sha256(key, message)
    if len(computed) != len(expected_hex):
        return False


    cb = computed.encode('utf-8')
    eb = expected_hex.encode('utf-8')
    diff = 0
    for i in range(len(computed)):
        diff |= int(cb[i]) ^ int(eb[i])
    return diff == 0
