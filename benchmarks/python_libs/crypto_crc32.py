"""Python equivalent of mojo/engine/crypto.crc32.mojo (auto-generated)."""
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

def _make_crc_table():
    table = []
    for i in range(256):
        crc = int(i)
        for _ in range(8):
            if (crc & 1) != 0:
                crc = (crc >> 1) ^ int(0xEDB88320)
            else:
                crc = crc >> 1
        table.append(crc)
    return table






def _nibble_to_hex(n):
    if n < 10:
        return chr(ord("0") + n)
    return chr(ord("a") + n - 10)



def _gf2_matrix_times(mat, vec):
    result = int(0)
    v = vec
    idx = 0
    while v != 0:
        if (v & 1) != 0:
            result ^= mat[idx]
        v >>= 1
        idx += 1
    return result



def _gf2_matrix_square(square, mat):
    for n in range(32):
        square[n] = _gf2_matrix_times(mat, mat[n])

def crc32(data):
    table = _make_crc_table()
    crc = int(0xFFFFFFFF)
    bytes = data.encode('utf-8')

    for i in range(len(bytes)):
        byte_val = int(int(bytes[i]))
        index = int((crc ^ byte_val) & int(0xFF))
        crc = (crc >> 8) ^ table[index]

    return crc ^ int(0xFFFFFFFF)






def crc32_hex(data):
    c = crc32(data)
    result = str("")


    for i in range(7, -1, -1):
        nibble = int((c >> int(i * 4)) & int(0xF))
        result += _nibble_to_hex(nibble)

    return result






def crc32_combine(crc1, crc2, len2):
    if len2 == 0:
        return crc1






    odd = []
    for _ in range(32):
        odd.append(int(0))
    odd[0] = int(0xEDB88320)  # Polynomial
    row = 1
    for i in range(1, 32):
        odd[i] = row
        row <<= 1


    even = []
    for _ in range(32):
        even.append(int(0))
    _gf2_matrix_square(even, odd)
    _gf2_matrix_square(odd, even)

    result = crc1
    remaining = len2

    while remaining > 0:

        _gf2_matrix_square(even, odd)
        if (remaining & 1) != 0:
            result = _gf2_matrix_times(even, result)
        remaining >>= 1
        if remaining == 0:
            break


        _gf2_matrix_square(odd, even)
        if (remaining & 1) != 0:
            result = _gf2_matrix_times(odd, result)
        remaining >>= 1

    return result ^ crc2


