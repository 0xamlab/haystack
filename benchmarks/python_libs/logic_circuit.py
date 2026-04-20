"""Python equivalent of mojo/engine/logic_circuit.mojo (auto-generated)."""
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

def gate_and(a, b):
    if a == 1 and b == 1:
        return 1
    return 0



def gate_or(a, b):
    if a == 1 or b == 1:
        return 1
    return 0



def gate_not(a):
    if a == 0:
        return 1
    return 0



def gate_xor(a, b):
    if a != b:
        return 1
    return 0



def gate_nand(a, b):
    return gate_not(gate_and(a, b))



def gate_nor(a, b):
    return gate_not(gate_or(a, b))






def half_adder(a, b):
    result = []
    result.append(gate_xor(a, b))
    result.append(gate_and(a, b))
    return result



def full_adder(a, b, cin):
    ha1 = half_adder(a, b)
    ha2 = half_adder(ha1[0], cin)
    carry_out = gate_or(ha1[1], ha2[1])
    result = []
    result.append(ha2[0])
    result.append(carry_out)
    return result



def ripple_carry_adder(a, b):
    n = len(a)
    result = []
    carry = 0
    for i in range(n):
        fa = full_adder(a[i], b[i], carry)
        result.append(fa[0])
        carry = fa[1]
    result.append(carry)
    return result






def multiplexer_2to1(a, b, sel):
    not_sel = gate_not(sel)
    out_a = gate_and(a, not_sel)
    out_b = gate_and(b, sel)
    return gate_or(out_a, out_b)



def decoder_2to4(a, b):
    not_a = gate_not(a)
    not_b = gate_not(b)
    result = []
    result.append(gate_and(not_a, not_b))  # o0: a=0, b=0
    result.append(gate_and(a, not_b))      # o1: a=1, b=0
    result.append(gate_and(not_a, b))      # o2: a=0, b=1
    result.append(gate_and(a, b))          # o3: a=1, b=1
    return result






def bits_to_int(bits):
    value = 0
    power = 1
    for i in range(len(bits)):
        if bits[i] == 1:
            value += power
        power *= 2
    return value



def int_to_bits(value, n_bits):
    result = []
    v = value
    for i in range(n_bits):
        result.append(v & 1)
        v >>= 1
    return result
