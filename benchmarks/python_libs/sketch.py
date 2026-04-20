"""Python equivalent of mojo/engine/sketch.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import log
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.math import pow
except Exception:
    pass

class CountMinSketch:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('table')
        self.table = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('width')
        self.width = _v1 if _v1 is not None else 0
        _v2 = args[2] if 2 < len(args) else kwargs.get('depth')
        self.depth = _v2 if _v2 is not None else 0
        _v3 = args[3] if 3 < len(args) else kwargs.get('hash_seeds')
        self.hash_seeds = _v3 if _v3 is not None else []
    def __repr__(self):
        return f'CountMinSketch({vars(self)})'

class HyperLogLog:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('registers')
        self.registers = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('m')
        self.m = _v1 if _v1 is not None else 0
        _v2 = args[2] if 2 < len(args) else kwargs.get('p')
        self.p = _v2 if _v2 is not None else 0
    def __repr__(self):
        return f'HyperLogLog({vars(self)})'

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

def create_cms(width, depth):
    table = []
    seeds = []
    for d in range(depth):
        row = []
        for _ in range(width):
            row.append(0)
        table.append(row)
        seeds.append(d * 1000003 + 7)
    return CountMinSketch(table, width, depth, seeds)



def cms_hash(item, seed, width):
    val = item * seed + 17

    if val < 0:
        val = -val
    val = val % 1000003
    return val % width



def create_hll(precision=10):
    m = 1 << precision  # 2^precision
    regs = []
    for _ in range(m):
        regs.append(0)
    return HyperLogLog(regs, m, precision)



def hll_hash(item):
    h = item & 0xFFFFFFFF
    h = (((h >> 16) ^ h) * 0x45D9F3B) & 0xFFFFFFFF
    h = (((h >> 16) ^ h) * 0x45D9F3B) & 0xFFFFFFFF
    h = ((h >> 16) ^ h) & 0x7FFFFFFF
    return h



def leading_zeros(value, max_bits=32):
    if value == 0:
        return max_bits
    count = 0
    mask = 1 << (max_bits - 1)
    v = value

    full_mask = (1 << max_bits) - 1
    v = v & full_mask
    while mask > 0:
        if (v & mask) != 0:
            return count
        count += 1
        mask >>= 1
    return count


