"""Python equivalent of mojo/engine/crypto.aes_sbox.mojo (auto-generated)."""
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

def _build_sbox():
    s = []
    s.append(0x63); s.append(0x7C); s.append(0x77); s.append(0x7B)
    s.append(0xF2); s.append(0x6B); s.append(0x6F); s.append(0xC5)
    s.append(0x30); s.append(0x01); s.append(0x67); s.append(0x2B)
    s.append(0xFE); s.append(0xD7); s.append(0xAB); s.append(0x76)
    s.append(0xCA); s.append(0x82); s.append(0xC9); s.append(0x7D)
    s.append(0xFA); s.append(0x59); s.append(0x47); s.append(0xF0)
    s.append(0xAD); s.append(0xD4); s.append(0xA2); s.append(0xAF)
    s.append(0x9C); s.append(0xA4); s.append(0x72); s.append(0xC0)
    s.append(0xB7); s.append(0xFD); s.append(0x93); s.append(0x26)
    s.append(0x36); s.append(0x3F); s.append(0xF7); s.append(0xCC)
    s.append(0x34); s.append(0xA5); s.append(0xE5); s.append(0xF1)
    s.append(0x71); s.append(0xD8); s.append(0x31); s.append(0x15)
    s.append(0x04); s.append(0xC7); s.append(0x23); s.append(0xC3)
    s.append(0x18); s.append(0x96); s.append(0x05); s.append(0x9A)
    s.append(0x07); s.append(0x12); s.append(0x80); s.append(0xE2)
    s.append(0xEB); s.append(0x27); s.append(0xB2); s.append(0x75)
    s.append(0x09); s.append(0x83); s.append(0x2C); s.append(0x1A)
    s.append(0x1B); s.append(0x6E); s.append(0x5A); s.append(0xA0)
    s.append(0x52); s.append(0x3B); s.append(0xD6); s.append(0xB3)
    s.append(0x29); s.append(0xE3); s.append(0x2F); s.append(0x84)
    s.append(0x53); s.append(0xD1); s.append(0x00); s.append(0xED)
    s.append(0x20); s.append(0xFC); s.append(0xB1); s.append(0x5B)
    s.append(0x6A); s.append(0xCB); s.append(0xBE); s.append(0x39)
    s.append(0x4A); s.append(0x4C); s.append(0x58); s.append(0xCF)
    s.append(0xD0); s.append(0xEF); s.append(0xAA); s.append(0xFB)
    s.append(0x43); s.append(0x4D); s.append(0x33); s.append(0x85)
    s.append(0x45); s.append(0xF9); s.append(0x02); s.append(0x7F)
    s.append(0x50); s.append(0x3C); s.append(0x9F); s.append(0xA8)
    s.append(0x51); s.append(0xA3); s.append(0x40); s.append(0x8F)
    s.append(0x92); s.append(0x9D); s.append(0x38); s.append(0xF5)
    s.append(0xBC); s.append(0xB6); s.append(0xDA); s.append(0x21)
    s.append(0x10); s.append(0xFF); s.append(0xF3); s.append(0xD2)
    s.append(0xCD); s.append(0x0C); s.append(0x13); s.append(0xEC)
    s.append(0x5F); s.append(0x97); s.append(0x44); s.append(0x17)
    s.append(0xC4); s.append(0xA7); s.append(0x7E); s.append(0x3D)
    s.append(0x64); s.append(0x5D); s.append(0x19); s.append(0x73)
    s.append(0x60); s.append(0x81); s.append(0x4F); s.append(0xDC)
    s.append(0x22); s.append(0x2A); s.append(0x90); s.append(0x88)
    s.append(0x46); s.append(0xEE); s.append(0xB8); s.append(0x14)
    s.append(0xDE); s.append(0x5E); s.append(0x0B); s.append(0xDB)
    s.append(0xE0); s.append(0x32); s.append(0x3A); s.append(0x0A)
    s.append(0x49); s.append(0x06); s.append(0x24); s.append(0x5C)
    s.append(0xC2); s.append(0xD3); s.append(0xAC); s.append(0x62)
    s.append(0x91); s.append(0x95); s.append(0xE4); s.append(0x79)
    s.append(0xE7); s.append(0xC8); s.append(0x37); s.append(0x6D)
    s.append(0x8D); s.append(0xD5); s.append(0x4E); s.append(0xA9)
    s.append(0x6C); s.append(0x56); s.append(0xF4); s.append(0xEA)
    s.append(0x65); s.append(0x7A); s.append(0xAE); s.append(0x08)
    s.append(0xBA); s.append(0x78); s.append(0x25); s.append(0x2E)
    s.append(0x1C); s.append(0xA6); s.append(0xB4); s.append(0xC6)
    s.append(0xE8); s.append(0xDD); s.append(0x74); s.append(0x1F)
    s.append(0x4B); s.append(0xBD); s.append(0x8B); s.append(0x8A)
    s.append(0x70); s.append(0x3E); s.append(0xB5); s.append(0x66)
    s.append(0x48); s.append(0x03); s.append(0xF6); s.append(0x0E)
    s.append(0x61); s.append(0x35); s.append(0x57); s.append(0xB9)
    s.append(0x86); s.append(0xC1); s.append(0x1D); s.append(0x9E)
    s.append(0xE1); s.append(0xF8); s.append(0x98); s.append(0x11)
    s.append(0x69); s.append(0xD9); s.append(0x8E); s.append(0x94)
    s.append(0x9B); s.append(0x1E); s.append(0x87); s.append(0xE9)
    s.append(0xCE); s.append(0x55); s.append(0x28); s.append(0xDF)
    s.append(0x8C); s.append(0xA1); s.append(0x89); s.append(0x0D)
    s.append(0xBF); s.append(0xE6); s.append(0x42); s.append(0x68)
    s.append(0x41); s.append(0x99); s.append(0x2D); s.append(0x0F)
    s.append(0xB0); s.append(0x54); s.append(0xBB); s.append(0x16)
    return s



def _build_inv_sbox():
    fwd = _build_sbox()
    inv = []
    for _ in range(256):
        inv.append(0)
    for i in range(256):
        inv[fwd[i]] = i
    return inv






def aes_sbox(byte):
    table = _build_sbox()
    idx = byte & 0xFF
    return table[idx]



def aes_inv_sbox(byte):
    table = _build_inv_sbox()
    idx = byte & 0xFF
    return table[idx]



def sub_bytes(state):
    table = _build_sbox()
    out = []
    for i in range(len(state)):
        out.append(table[state[i] & 0xFF])
    return out



def inv_sub_bytes(state):
    table = _build_inv_sbox()
    out = []
    for i in range(len(state)):
        out.append(table[state[i] & 0xFF])
    return out



def shift_rows(state):
    out = []
    for _ in range(16):
        out.append(0)

    out[0] = state[0]; out[1] = state[1]; out[2] = state[2]; out[3] = state[3]

    out[4] = state[5]; out[5] = state[6]; out[6] = state[7]; out[7] = state[4]

    out[8] = state[10]; out[9] = state[11]; out[10] = state[8]; out[11] = state[9]

    out[12] = state[15]; out[13] = state[12]; out[14] = state[13]; out[15] = state[14]
    return out



def inv_shift_rows(state):
    out = []
    for _ in range(16):
        out.append(0)

    out[0] = state[0]; out[1] = state[1]; out[2] = state[2]; out[3] = state[3]

    out[4] = state[7]; out[5] = state[4]; out[6] = state[5]; out[7] = state[6]

    out[8] = state[10]; out[9] = state[11]; out[10] = state[8]; out[11] = state[9]

    out[12] = state[13]; out[13] = state[14]; out[14] = state[15]; out[15] = state[12]
    return out



def xor_bytes(a, b):
    n = len(a)
    if len(b) < n:
        n = len(b)
    out = []
    for i in range(n):
        out.append((a[i] ^ b[i]) & 0xFF)
    return out



def add_round_key(state, key):
    return xor_bytes(state, key)
