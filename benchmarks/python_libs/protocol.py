"""Python equivalent of mojo/engine/protocol.mojo (auto-generated)."""
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

def encode_varint(value):
    result = []
    v = value
    if v == 0:
        result.append(0)
        return result
    while v > 0:
        byte = v & 0x7F  # low 7 bits
        v >>= 7
        if v > 0:
            byte |= 0x80  # set continuation bit
        result.append(byte)
    return result



def decode_varint(data, offset):
    result = []
    value = 0
    shift = 0
    pos = offset
    while pos < len(data):
        byte = data[pos]
        value |= (byte & 0x7F) << shift
        pos += 1
        if (byte & 0x80) == 0:
            break
        shift += 7
    result.append(value)
    result.append(pos - offset)
    return result






def zigzag_encode(value):
    return (value << 1) ^ (value >> 63)



def zigzag_decode(value):
    unsigned_shift = value >> 1
    if (value & 1) == 0:
        return unsigned_shift
    else:
        return unsigned_shift ^ -1






def encode_field(field_number, wire_type, value):
    tag = (field_number << 3) | wire_type
    result = encode_varint(tag)
    val_bytes = encode_varint(value)
    for i in range(len(val_bytes)):
        result.append(val_bytes[i])
    return result



def decode_field(data, offset):
    result = []

    tag_result = decode_varint(data, offset)
    tag = tag_result[0]
    tag_bytes = tag_result[1]
    field_number = tag >> 3
    wire_type = tag & 0x07


    val_result = decode_varint(data, offset + tag_bytes)
    value = val_result[0]
    val_bytes = val_result[1]

    result.append(field_number)
    result.append(wire_type)
    result.append(value)
    result.append(tag_bytes + val_bytes)
    return result






def encode_string_field(field_number, text):
    tag = (field_number << 3) | 2  # wire_type 2 = length-delimited
    result = encode_varint(tag)
    text_bytes = text.encode('utf-8')
    length = len(text)
    len_enc = encode_varint(length)
    for i in range(len(len_enc)):
        result.append(len_enc[i])
    for i in range(length):
        result.append(int(text_bytes[i]))
    return result



def decode_string_field(data, offset):
    result = []

    tag_result = decode_varint(data, offset)
    tag = tag_result[0]
    tag_bytes = tag_result[1]
    field_number = tag >> 3


    len_result = decode_varint(data, offset + tag_bytes)
    str_len = len_result[0]
    len_bytes = len_result[1]

    str_start = offset + tag_bytes + len_bytes
    total = tag_bytes + len_bytes + str_len

    result.append(field_number)
    result.append(str_start)
    result.append(str_len)
    result.append(total)
    return result






def encode_message(fields):
    result = []
    for i in range(len(fields)):
        if len(fields[i]) >= 2:
            encoded = encode_field(fields[i][0], 0, fields[i][1])
            for j in range(len(encoded)):
                result.append(encoded[j])
    return result



def decode_message(data):
    result = []
    pos = 0
    while pos < len(data):
        field_result = decode_field(data, pos)
        entry = []
        entry.append(field_result[0])  # field_number
        entry.append(field_result[1])  # wire_type
        entry.append(field_result[2])  # value
        result.append(entry)
        pos += field_result[3]  # advance by bytes consumed
    return result
