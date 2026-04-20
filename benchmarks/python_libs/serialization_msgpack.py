"""Python equivalent of mojo/engine/serialization.msgpack.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.memory import bitcast
except Exception:
    pass

class MsgPackIntResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('value')
        self.value = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('consumed')
        self.consumed = _v1 if _v1 is not None else 0
    def __repr__(self):
        return f'MsgPackIntResult({vars(self)})'

class MsgPackFloatResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('value')
        self.value = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('consumed')
        self.consumed = _v1 if _v1 is not None else 0
    def __repr__(self):
        return f'MsgPackFloatResult({vars(self)})'

class MsgPackStringResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('value')
        self.value = _v0 if _v0 is not None else ""
        _v1 = args[1] if 1 < len(args) else kwargs.get('consumed')
        self.consumed = _v1 if _v1 is not None else 0
    def __repr__(self):
        return f'MsgPackStringResult({vars(self)})'

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

def msgpack_encode_int(v):
    buf = []


    if v >= 0 and v <= 127:
        buf.append(int(v))
        return buf


    if v >= -32 and v < 0:
        buf.append(int(v + 256))
        return buf


    if v >= 0 and v <= 255:
        buf.append(int(0xcc))
        buf.append(int(v))
        return buf


    if v >= 0 and v <= 65535:
        buf.append(int(0xcd))
        buf.append(int((v >> 8) & 0xff))
        buf.append(int(v & 0xff))
        return buf


    if v >= 0 and v <= 4294967295:
        buf.append(int(0xce))
        buf.append(int((v >> 24) & 0xff))
        buf.append(int((v >> 16) & 0xff))
        buf.append(int((v >> 8) & 0xff))
        buf.append(int(v & 0xff))
        return buf


    if v >= 0:
        buf.append(int(0xcf))
        buf.append(int((v >> 56) & 0xff))
        buf.append(int((v >> 48) & 0xff))
        buf.append(int((v >> 40) & 0xff))
        buf.append(int((v >> 32) & 0xff))
        buf.append(int((v >> 24) & 0xff))
        buf.append(int((v >> 16) & 0xff))
        buf.append(int((v >> 8) & 0xff))
        buf.append(int(v & 0xff))
        return buf


    if v >= -128:
        buf.append(int(0xd0))
        buf.append(int(v + 256))
        return buf


    if v >= -32768:
        buf.append(int(0xd1))
        u = v + 65536
        buf.append(int((u >> 8) & 0xff))
        buf.append(int(u & 0xff))
        return buf


    if v >= -2147483648:
        buf.append(int(0xd2))
        u = v + 4294967296
        buf.append(int((u >> 24) & 0xff))
        buf.append(int((u >> 16) & 0xff))
        buf.append(int((u >> 8) & 0xff))
        buf.append(int(u & 0xff))
        return buf


    buf.append(int(0xd3))
    u = v
    buf.append(int((u >> 56) & 0xff))
    buf.append(int((u >> 48) & 0xff))
    buf.append(int((u >> 40) & 0xff))
    buf.append(int((u >> 32) & 0xff))
    buf.append(int((u >> 24) & 0xff))
    buf.append(int((u >> 16) & 0xff))
    buf.append(int((u >> 8) & 0xff))
    buf.append(int(u & 0xff))
    return buf






def msgpack_encode_float(v):
    buf = []
    buf.append(int(0xcb))

    bits = bitcast[DType.uint64](v)
    u = int(bits)
    buf.append(int((u >> 56) & 0xff))
    buf.append(int((u >> 48) & 0xff))
    buf.append(int((u >> 40) & 0xff))
    buf.append(int((u >> 32) & 0xff))
    buf.append(int((u >> 24) & 0xff))
    buf.append(int((u >> 16) & 0xff))
    buf.append(int((u >> 8) & 0xff))
    buf.append(int(u & 0xff))
    return buf






def msgpack_encode_string(v):
    buf = []
    bs = v.encode('utf-8')
    n = len(v)

    if n <= 31:
        buf.append(int(0xa0 | n))
    elif n <= 255:
        buf.append(int(0xd9))
        buf.append(int(n))
    elif n <= 65535:
        buf.append(int(0xda))
        buf.append(int((n >> 8) & 0xff))
        buf.append(int(n & 0xff))
    else:
        buf.append(int(0xdb))
        buf.append(int((n >> 24) & 0xff))
        buf.append(int((n >> 16) & 0xff))
        buf.append(int((n >> 8) & 0xff))
        buf.append(int(n & 0xff))

    for i in range(n):
        buf.append(bs[i])

    return buf






def msgpack_encode_bool(v):
    buf = []
    if v:
        buf.append(int(0xc3))
    else:
        buf.append(int(0xc2))
    return buf






def msgpack_encode_nil():
    buf = []
    buf.append(int(0xc0))
    return buf






def msgpack_encode_array_header(n):
    buf = []
    if n <= 15:
        buf.append(int(0x90 | n))
    elif n <= 65535:
        buf.append(int(0xdc))
        buf.append(int((n >> 8) & 0xff))
        buf.append(int(n & 0xff))
    else:
        buf.append(int(0xdd))
        buf.append(int((n >> 24) & 0xff))
        buf.append(int((n >> 16) & 0xff))
        buf.append(int((n >> 8) & 0xff))
        buf.append(int(n & 0xff))
    return buf






def msgpack_encode_map_header(n):
    buf = []
    if n <= 15:
        buf.append(int(0x80 | n))
    elif n <= 65535:
        buf.append(int(0xde))
        buf.append(int((n >> 8) & 0xff))
        buf.append(int(n & 0xff))
    else:
        buf.append(int(0xdf))
        buf.append(int((n >> 24) & 0xff))
        buf.append(int((n >> 16) & 0xff))
        buf.append(int((n >> 8) & 0xff))
        buf.append(int(n & 0xff))
    return buf






def msgpack_decode_int(data, pos):
    if pos >= len(data):
        return MsgPackIntResult(0, 0)

    tag = int(data[pos])


    if tag <= 0x7f:
        return MsgPackIntResult(tag, 1)


    if tag >= 0xe0:
        return MsgPackIntResult(tag - 256, 1)


    if tag == 0xcc:
        if pos + 1 >= len(data):
            return MsgPackIntResult(0, 0)
        return MsgPackIntResult(int(data[pos + 1]), 2)


    if tag == 0xcd:
        if pos + 2 >= len(data):
            return MsgPackIntResult(0, 0)
        v = (int(data[pos + 1]) << 8) | int(data[pos + 2])
        return MsgPackIntResult(v, 3)


    if tag == 0xce:
        if pos + 4 >= len(data):
            return MsgPackIntResult(0, 0)
        v = (int(data[pos + 1]) << 24) | (int(data[pos + 2]) << 16) | (int(data[pos + 3]) << 8) | int(data[pos + 4])
        return MsgPackIntResult(v, 5)


    if tag == 0xcf:
        if pos + 8 >= len(data):
            return MsgPackIntResult(0, 0)
        v = 0
        for i in range(8):
            v = (v << 8) | int(data[pos + 1 + i])
        return MsgPackIntResult(v, 9)


    if tag == 0xd0:
        if pos + 1 >= len(data):
            return MsgPackIntResult(0, 0)
        v = int(data[pos + 1])
        if v >= 128:
            v = v - 256
        return MsgPackIntResult(v, 2)


    if tag == 0xd1:
        if pos + 2 >= len(data):
            return MsgPackIntResult(0, 0)
        v = (int(data[pos + 1]) << 8) | int(data[pos + 2])
        if v >= 32768:
            v = v - 65536
        return MsgPackIntResult(v, 3)


    if tag == 0xd2:
        if pos + 4 >= len(data):
            return MsgPackIntResult(0, 0)
        v = (int(data[pos + 1]) << 24) | (int(data[pos + 2]) << 16) | (int(data[pos + 3]) << 8) | int(data[pos + 4])
        if v >= 2147483648:
            v = v - 4294967296
        return MsgPackIntResult(v, 5)


    if tag == 0xd3:
        if pos + 8 >= len(data):
            return MsgPackIntResult(0, 0)
        v = 0
        for i in range(8):
            v = (v << 8) | int(data[pos + 1 + i])
        if v >= (1 << 63):
            v = v - (1 << 64)
        return MsgPackIntResult(v, 9)

    return MsgPackIntResult(0, 0)






def msgpack_decode_float(data, pos):
    if pos >= len(data):
        return MsgPackFloatResult(0.0, 0)

    tag = int(data[pos])


    if tag == 0xcb:
        if pos + 8 >= len(data):
            return MsgPackFloatResult(0.0, 0)
        bits = 0
        for i in range(8):
            bits = (bits << 8) | int(data[pos + 1 + i])
        v = bitcast[DType.float64](bits)
        return MsgPackFloatResult(float(v), 9)


    if tag == 0xca:
        if pos + 4 >= len(data):
            return MsgPackFloatResult(0.0, 0)
        bits = 0
        for i in range(4):
            bits = (bits << 8) | int(data[pos + 1 + i])
        v = bitcast[DType.float32](bits)
        return MsgPackFloatResult(float(v), 5)

    return MsgPackFloatResult(0.0, 0)






def msgpack_decode_string(data, pos):
    if pos >= len(data):
        return MsgPackStringResult(str(""), 0)

    tag = int(data[pos])
    str_len = 0
    header_size = 0


    if tag >= 0xa0 and tag <= 0xbf:
        str_len = tag & 0x1f
        header_size = 1
    elif tag == 0xd9:
        if pos + 1 >= len(data):
            return MsgPackStringResult(str(""), 0)
        str_len = int(data[pos + 1])
        header_size = 2
    elif tag == 0xda:
        if pos + 2 >= len(data):
            return MsgPackStringResult(str(""), 0)
        str_len = (int(data[pos + 1]) << 8) | int(data[pos + 2])
        header_size = 3
    elif tag == 0xdb:
        if pos + 4 >= len(data):
            return MsgPackStringResult(str(""), 0)
        str_len = (int(data[pos + 1]) << 24) | (int(data[pos + 2]) << 16) | (int(data[pos + 3]) << 8) | int(data[pos + 4])
        header_size = 5
    else:
        return MsgPackStringResult(str(""), 0)

    result = str("")
    start = pos + header_size
    for i in range(str_len):
        if start + i < len(data):
            result += chr(int(data[start + i]))

    return MsgPackStringResult(result, header_size + str_len)
