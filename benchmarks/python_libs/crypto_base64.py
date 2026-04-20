"""Python equivalent of mojo/engine/crypto.base64.mojo (auto-generated)."""
import math
import random as _rng

_B64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

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

def _b64_char_at(idx):
    return chr(int(_B64_ALPHABET.encode('utf-8')[idx]))



def _b64_decode_byte(b):
    o = int(b)
    if o >= 65 and o <= 90:
        return o - 65
    if o >= 97 and o <= 122:
        return o - 71
    if o >= 48 and o <= 57:
        return o + 4
    if o == 43:
        return 62
    if o == 47:
        return 63
    if o == 45:
        return 62
    if o == 95:
        return 63
    return -1





def b64_encode(data):
    n = len(data)
    if n == 0:
        return ""

    result = str("")
    bspan = data.encode('utf-8')
    i = 0


    while i + 3 <= n:
        b0 = int(bspan[i])
        b1 = int(bspan[i + 1])
        b2 = int(bspan[i + 2])

        result += _b64_char_at((b0 >> 2) & 0x3F)
        result += _b64_char_at(((b0 & 0x03) << 4) | ((b1 >> 4) & 0x0F))
        result += _b64_char_at(((b1 & 0x0F) << 2) | ((b2 >> 6) & 0x03))
        result += _b64_char_at(b2 & 0x3F)
        i += 3


    remaining = n - i
    if remaining == 1:
        b0 = int(bspan[i])
        result += _b64_char_at((b0 >> 2) & 0x3F)
        result += _b64_char_at((b0 & 0x03) << 4)
        result += "=="
    elif remaining == 2:
        b0 = int(bspan[i])
        b1 = int(bspan[i + 1])
        result += _b64_char_at((b0 >> 2) & 0x3F)
        result += _b64_char_at(((b0 & 0x03) << 4) | ((b1 >> 4) & 0x0F))
        result += _b64_char_at((b1 & 0x0F) << 2)
        result += "="

    return result



def b64_decode(encoded):
    n = len(encoded)
    if n == 0:
        return ""

    enc_bytes = encoded.encode('utf-8')


    end = n
    while end > 0 and enc_bytes[end - 1] == int(61):  # '='
        end -= 1

    result = str("")
    buf = 0
    bits = 0

    for i in range(end):
        val = _b64_decode_byte(enc_bytes[i])
        if val < 0:
            continue  # skip whitespace / invalid chars
        buf = (buf << 6) | val
        bits += 6
        if bits >= 8:
            bits -= 8
            result += chr((buf >> bits) & 0xFF)

    return result





def b64_url_encode(data):
    standard = b64_encode(data)
    result = str("")
    sb = standard.encode('utf-8')
    for i in range(len(standard)):
        b = sb[i]
        if b == int(43):
            result += "-"
        elif b == int(47):
            result += "_"
        elif b == int(61):
            pass  # strip padding
        else:
            result += chr(int(b))
    return result



def b64_url_decode(encoded):

    standard = str("")
    eb = encoded.encode('utf-8')
    for i in range(len(encoded)):
        b = eb[i]
        if b == int(45):
            standard += "+"
        elif b == int(95):
            standard += "/"
        else:
            standard += chr(int(b))


    pad = len(standard) % 4
    if pad == 2:
        standard += "=="
    elif pad == 3:
        standard += "="

    return b64_decode(standard)
