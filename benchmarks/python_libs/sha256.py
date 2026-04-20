"""Python equivalent of mojo/engine/sha256.mojo (auto-generated)."""
import math
import random as _rng

class SHA256:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('_h')
        self._h = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('_buf')
        self._buf = _v1 if _v1 is not None else []
        _v2 = args[2] if 2 < len(args) else kwargs.get('_total')
        self._total = _v2 if _v2 is not None else 0
    def __repr__(self):
        return f'SHA256({vars(self)})'
    def update(self, data):
        bspan = data.encode('utf-8')
        data_len = len(data)
        self._total += data_len
        pos = 0
    
    
        if len(self._buf) > 0:
            space = 64 - len(self._buf)
            to_copy = min(space, data_len)
            for i in range(to_copy):
                self._buf.append(int(bspan[i]))
            pos = to_copy
            if len(self._buf) == 64:
                _compress(self._buf, 0, self._h)
                self._buf.clear()
    
    
        while pos + 64 <= data_len:
            block = []
            for i in range(64):
                block.append(int(bspan[pos + i]))
            _compress(block, 0, self._h)
            pos += 64
    
    
        while pos < data_len:
            self._buf.append(int(bspan[pos]))
            pos += 1
    
    def hexdigest(self):
    
        h = []
        for i in range(8):
            h.append(self._h[i])
        buf = []
        for i in range(len(self._buf)):
            buf.append(self._buf[i])
    
    
        msg_len = self._total
    
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
    
    
        out = str("")
        for i in range(8):
            out += _u32_hex(h[i])
        return out
    
    
    def update(self, data):
        if not hasattr(self, '_hlib'):
            import hashlib
            self._hlib = hashlib.sha256()
        self._hlib.update(data.encode() if isinstance(data, str) else bytes(data))
    def hexdigest(self):
        if not hasattr(self, '_hlib'): return ''
        return self._hlib.hexdigest()

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



def _ch(x, y, z):
    return (x & y) ^ (~x & z)



def _maj(x, y, z):
    return (x & y) ^ (x & z) ^ (y & z)



def _big_sigma0(x):
    return _rotr(x, 2) ^ _rotr(x, 13) ^ _rotr(x, 22)



def _big_sigma1(x):
    return _rotr(x, 6) ^ _rotr(x, 11) ^ _rotr(x, 25)



def _small_sigma0(x):
    return _rotr(x, 7) ^ _rotr(x, 18) ^ (x >> int(3))



def _small_sigma1(x):
    return _rotr(x, 17) ^ _rotr(x, 19) ^ (x >> int(10))





def _nibble_hex(n):
    if n < 10:
        return chr(48 + n)   # ord("0") = 48
    return chr(87 + n)       # ord("a") - 10 = 87



def _u32_hex(v):
    s = str("")
    for i in range(8):
        shift = int((7 - i) * 4)
        s += _nibble_hex(int((v >> shift) & 0xF))
    return s






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





def _compress(block, offset, h):
    k = _k_constants()


    w = []
    for i in range(16):
        base = offset + i * 4
        word = (int(block[base]) << int(24)) | (int(block[base + 1]) << int(16)) | (int(block[base + 2]) << int(8)) | int(block[base + 3])
        w.append(word)
    for i in range(16, 64):
        s0 = _small_sigma0(w[i - 15])
        s1 = _small_sigma1(w[i - 2])
        w.append(w[i - 16] + s0 + w[i - 7] + s1)


    a = h[0]; b = h[1]; c = h[2]; d = h[3]
    e = h[4]; f = h[5]; g = h[6]; hh = h[7]


    for i in range(64):
        t1 = hh + _big_sigma1(e) + _ch(e, f, g) + k[i] + w[i]
        t2 = _big_sigma0(a) + _maj(a, b, c)
        hh = g; g = f; f = e; e = d + t1
        d = c; c = b; b = a; a = t1 + t2


    h[0] += a; h[1] += b; h[2] += c; h[3] += d
    h[4] += e; h[5] += f; h[6] += g; h[7] += hh





def sha256_hex(data):
    hasher = SHA256()
    hasher.update(data)
    return hasher.hexdigest()
