"""Python equivalent of mojo/engine/crypto.pbkdf2.mojo (auto-generated)."""
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

def _rotr(x, n):
    return (x >> int(n)) | (x << int(32 - n))



def _k_constants():
    k = []
    k.append(0x428a2f98); k.append(0x71374491); k.append(0xb5c0fbcf); k.append(0xe9b5dba5)
    k.append(0x3956c25b); k.append(0x59f111f1); k.append(0x923f82a4); k.append(0xab1c5ed5)
    k.append(0xd807aa98); k.append(0x12835b01); k.append(0x243185be); k.append(0x550c7dc3)
    k.append(0x72be5d74); k.append(0x80deb1fe); k.append(0x9bdc06a7); k.append(0xc19bf174)
    k.append(0xe49b69c1); k.append(0xefbe4786); k.append(0x0fc19dc6); k.append(0x240ca1cc)
    k.append(0x2de92c6f); k.append(0x4a7484aa); k.append(0x5cb0a9dc); k.append(0x76f988da)
    k.append(0x983e5152); k.append(0xa831c66d); k.append(0xb00327c8); k.append(0xbf597fc7)
    k.append(0xc6e00bf3); k.append(0xd5a79147); k.append(0x06ca6351); k.append(0x14292967)
    k.append(0x27b70a85); k.append(0x2e1b2138); k.append(0x4d2c6dfc); k.append(0x53380d13)
    k.append(0x650a7354); k.append(0x766a0abb); k.append(0x81c2c92e); k.append(0x92722c85)
    k.append(0xa2bfe8a1); k.append(0xa81a664b); k.append(0xc24b8b70); k.append(0xc76c51a3)
    k.append(0xd192e819); k.append(0xd6990624); k.append(0xf40e3585); k.append(0x106aa070)
    k.append(0x19a4c116); k.append(0x1e376c08); k.append(0x2748774c); k.append(0x34b0bcb5)
    k.append(0x391c0cb3); k.append(0x4ed8aa4a); k.append(0x5b9cca4f); k.append(0x682e6ff3)
    k.append(0x748f82ee); k.append(0x78a5636f); k.append(0x84c87814); k.append(0x8cc70208)
    k.append(0x90befffa); k.append(0xa4506ceb); k.append(0xbef9a3f7); k.append(0xc67178f2)
    return k



def _compress_block(data, offset, h):
    k = _k_constants()
    w = []
    for i in range(16):
        base = offset + i * 4
        word = (int(data[base]) << int(24)) | (int(data[base + 1]) << int(16)) | (int(data[base + 2]) << int(8)) | int(data[base + 3])
        w.append(word)
    for i in range(16, 64):
        s0 = _rotr(w[i-15], 7) ^ _rotr(w[i-15], 18) ^ (w[i-15] >> int(3))
        s1 = _rotr(w[i-2], 17) ^ _rotr(w[i-2], 19) ^ (w[i-2] >> int(10))
        w.append(w[i-16] + s0 + w[i-7] + s1)

    a = h[0]; b = h[1]; c = h[2]; d = h[3]
    e = h[4]; f = h[5]; g = h[6]; hh = h[7]

    for i in range(64):
        S1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25)
        ch = (e & f) ^ (~e & g)
        t1 = hh + S1 + ch + k[i] + w[i]
        S0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22)
        maj = (a & b) ^ (a & c) ^ (b & c)
        t2 = S0 + maj
        hh = g; g = f; f = e; e = d + t1
        d = c; c = b; b = a; a = t1 + t2

    h[0] += a; h[1] += b; h[2] += c; h[3] += d
    h[4] += e; h[5] += f; h[6] += g; h[7] += hh






def sha256_bytes(data):
    h = []
    h.append(0x6a09e667); h.append(0xbb67ae85)
    h.append(0x3c6ef372); h.append(0xa54ff53a)
    h.append(0x510e527f); h.append(0x9b05688c)
    h.append(0x1f83d9ab); h.append(0x5be0cd19)

    msg_len = len(data)
    pos = 0
    while pos + 64 <= msg_len:
        _compress_block(data, pos, h)
        pos += 64


    buf = []
    while pos < msg_len:
        buf.append(data[pos])
        pos += 1
    buf.append(0x80)
    while len(buf) % 64 != 56:
        buf.append(0)
    bit_len = int(msg_len) * 8
    buf.append(int((bit_len >> 56) & 0xFF))
    buf.append(int((bit_len >> 48) & 0xFF))
    buf.append(int((bit_len >> 40) & 0xFF))
    buf.append(int((bit_len >> 32) & 0xFF))
    buf.append(int((bit_len >> 24) & 0xFF))
    buf.append(int((bit_len >> 16) & 0xFF))
    buf.append(int((bit_len >> 8) & 0xFF))
    buf.append(int(bit_len & 0xFF))

    off = 0
    while off < len(buf):
        _compress_block(buf, off, h)
        off += 64

    result = []
    for i in range(8):
        w = h[i]
        result.append(int((w >> 24) & 0xFF))
        result.append(int((w >> 16) & 0xFF))
        result.append(int((w >> 8) & 0xFF))
        result.append(int(w & 0xFF))
    return result






def bytes_from_string(s):
    bspan = s.encode('utf-8')
    n = len(s)
    result = []
    for i in range(n):
        result.append(int(bspan[i]))
    return result



def bytes_to_hex(data):
    result = str("")
    for i in range(len(data)):
        b = data[i]
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



def xor_byte_lists(a, b):
    n = len(a)
    result = []
    for i in range(n):
        result.append(a[i] ^ b[i])
    return result



def int_to_bytes_be(value, length):
    result = []
    for i in range(length):
        result.append(0)
    v = value
    for i in range(length):
        result[length - 1 - i] = v & 0xFF
        v >>= 8
    return result






def hmac_sha256_bytes(key, message):
    block_size = 64


    k = []
    if len(key) > block_size:
        hashed = sha256_bytes(key)
        for i in range(len(hashed)):
            k.append(hashed[i])
    else:
        for i in range(len(key)):
            k.append(key[i])


    while len(k) < block_size:
        k.append(0)


    inner = []
    for i in range(block_size):
        inner.append(k[i] ^ 0x36)
    for i in range(len(message)):
        inner.append(message[i])
    inner_hash = sha256_bytes(inner)


    outer = []
    for i in range(block_size):
        outer.append(k[i] ^ 0x5C)
    for i in range(len(inner_hash)):
        outer.append(inner_hash[i])

    return sha256_bytes(outer)






def pbkdf2_hmac_sha256(password, salt, iterations, dk_len):
    hash_len = 32  # SHA-256 output

    blocks = (dk_len + hash_len - 1) // hash_len

    dk = []

    for block_idx in range(1, blocks + 1):

        salt_block = []
        for i in range(len(salt)):
            salt_block.append(salt[i])
        be = int_to_bytes_be(block_idx, 4)
        for i in range(4):
            salt_block.append(be[i])

        u = hmac_sha256_bytes(password, salt_block)

        t = []
        for i in range(hash_len):
            t.append(u[i])


        for iter_idx in range(1, iterations):
            u = hmac_sha256_bytes(password, u)
            for i in range(hash_len):
                t[i] = t[i] ^ u[i]


        for i in range(hash_len):
            if len(dk) < dk_len:
                dk.append(t[i])

    return dk
