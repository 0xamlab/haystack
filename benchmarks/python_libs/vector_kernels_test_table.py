"""Python equivalent of mojo/engine/vector_kernels.test_table.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.time import perf_counter_ns
except Exception:
    pass
try:
    from std.math import sqrt
except Exception:
    pass

VEC_DIM = 64
SIMD_W = 8
RANK_TOP_K = 8
AMBIG_GAP = float(0.08)
W_NAME = float(0.55)
SOURCE_UNKNOWN = 0
SOURCE_POS = 1
SOURCE_BACKLOG = 2
SOURCE_INVOICE = 3
ROLE_OTHER = 0
ROLE_UNIT = 1
ROLE_DERIVED = 2

class _Vec64:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('data')
        self.data = _v0 if _v0 is not None else []
    def __repr__(self):
        return f'_Vec64({vars(self)})'

class _Slot:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('column_id')
        self.column_id = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('score')
        self.score = _v1 if _v1 is not None else 0.0
        _v2 = args[2] if 2 < len(args) else kwargs.get('name_sim')
        self.name_sim = _v2 if _v2 is not None else 0.0
        _v3 = args[3] if 3 < len(args) else kwargs.get('type_boost')
        self.type_boost = _v3 if _v3 is not None else 0.0
    def __repr__(self):
        return f'_Slot({vars(self)})'

class TopKEntry:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('column_id')
        self.column_id = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('score')
        self.score = _v1 if _v1 is not None else 0.0
        _v2 = args[2] if 2 < len(args) else kwargs.get('name_sim')
        self.name_sim = _v2 if _v2 is not None else 0.0
        _v3 = args[3] if 3 < len(args) else kwargs.get('type_boost')
        self.type_boost = _v3 if _v3 is not None else 0.0
    def __repr__(self):
        return f'TopKEntry({vars(self)})'

class RankResult:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('count')
        self.count = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('ambiguous')
        self.ambiguous = _v1 if _v1 is not None else False
        _v2 = args[2] if 2 < len(args) else kwargs.get('confidence_gap')
        self.confidence_gap = _v2 if _v2 is not None else 0.0
        _v3 = args[3] if 3 < len(args) else kwargs.get('entries')
        self.entries = _v3 if _v3 is not None else []
    def __repr__(self):
        return f'RankResult({vars(self)})'

class RankRequest:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('source_id')
        self.source_id = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('role_id')
        self.role_id = _v1 if _v1 is not None else 0
        _v2 = args[2] if 2 < len(args) else kwargs.get('top_k')
        self.top_k = _v2 if _v2 is not None else 0
        _v3 = args[3] if 3 < len(args) else kwargs.get('query_norm_inv')
        self.query_norm_inv = _v3 if _v3 is not None else 0.0
        _v4 = args[4] if 4 < len(args) else kwargs.get('query_vec')
        self.query_vec = _v4 if _v4 is not None else _Vec64()
    def __repr__(self):
        return f'RankRequest({vars(self)})'

class CandidateEntry:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('column_id')
        self.column_id = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('source_id')
        self.source_id = _v1 if _v1 is not None else 0
        _v2 = args[2] if 2 < len(args) else kwargs.get('role_id')
        self.role_id = _v2 if _v2 is not None else 0
        _v3 = args[3] if 3 < len(args) else kwargs.get('norm_inv')
        self.norm_inv = _v3 if _v3 is not None else 0.0
        _v4 = args[4] if 4 < len(args) else kwargs.get('vec')
        self.vec = _v4 if _v4 is not None else _Vec64()
    def __repr__(self):
        return f'CandidateEntry({vars(self)})'

class CandidateTable:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('entries')
        self.entries = _v0 if _v0 is not None else []
    def __repr__(self):
        return f'CandidateTable({vars(self)})'
    def add_column(self, column_id, source_id, role_id, name):
        entry = CandidateEntry()
        entry.column_id = column_id
        entry.source_id = source_id
        entry.role_id   = role_id
        entry.norm_inv  = _build_vec_inplace(name, entry.vec.data)
        self.entries.append(entry)
    
    def size(self):
        return len(self.entries)
    
    def rank(self, req):
        n_cands = len(self.entries)
        top_k = int(req.top_k) if int(req.top_k) <= RANK_TOP_K else RANK_TOP_K
        slots = []
    
        for i in range(n_cands):
            c_id = self.entries[i].column_id
            c_src = self.entries[i].source_id
            c_rol = self.entries[i].role_id
            c_ni = self.entries[i].norm_inv
    
    
            nsim = _cosine(
                req.query_vec.data,
                self.entries[i].vec.data,
                req.query_norm_inv,
                c_ni,
            )
            tb = _type_boost_ids(req.role_id, c_rol)
            pb = _prior_boost_ids(req.source_id, c_src, c_rol)
    
            fs = W_NAME * nsim + tb + pb
            if fs > 1.0:
                fs = float(1.0)
            elif fs < 0.0:
                fs = float(0.0)
    
            slot = _Slot()
            slot.column_id  = c_id
            slot.score      = fs
            slot.name_sim   = nsim
            slot.type_boost = tb + pb
            slots.append(slot)
    
        if len(slots) == 0:
            return RankResult()
    
        _insert_sort_slots(slots)
    
        result = RankResult()
        out_n = len(slots) if len(slots) < top_k else top_k
        result.count = int(out_n)
    
        gap = float(0.0)
        if len(slots) >= 2:
            gap = slots[0].score - slots[1].score
        result.confidence_gap = gap
        result.ambiguous = gap < AMBIG_GAP and len(slots) >= 2
    
        for i in range(out_n):
            result.entries[i].column_id  = slots[i].column_id
            result.entries[i].score      = slots[i].score
            result.entries[i].name_sim   = slots[i].name_sim
            result.entries[i].type_boost = slots[i].type_boost
    
        return result
    
    

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

def _norm_byte(c):
    if c == 95 or c == 45 or c == 46:
        return 32
    if c >= 65 and c <= 90:
        return c + 32
    return c



def _build_vec_inplace(s, buf):
    for i in range(VEC_DIM):
        buf[i] = float(0.0)
    sb = s.encode('utf-8')
    n = len(sb)
    if n == 0:
        return float(0.0)
    prev = _norm_byte(sb[0])
    for i in range(1, n):
        cur = _norm_byte(sb[i])
        h = (int(prev) * 31 + int(cur)) & (VEC_DIM - 1)
        buf[h] += float(1.0)
        prev = cur
    p = buf.unsafe_ptr()
    s0 = (p +  0).load(width=SIMD_W)
    s1 = (p +  8).load(width=SIMD_W)
    s2 = (p + 16).load(width=SIMD_W)
    s3 = (p + 24).load(width=SIMD_W)
    s4 = (p + 32).load(width=SIMD_W)
    s5 = (p + 40).load(width=SIMD_W)
    s6 = (p + 48).load(width=SIMD_W)
    s7 = (p + 56).load(width=SIMD_W)
    mag = (
        (s0*s0 + s1*s1) + (s2*s2 + s3*s3) +
        (s4*s4 + s5*s5) + (s6*s6 + s7*s7)
    ).reduce_add()
    if mag <= 0.0:
        return float(0.0)
    return float(1.0) / math.sqrt(mag)



def _dot64(a, b):
    pa = a.unsafe_ptr()
    pb = b.unsafe_ptr()
    a0 = (pa +  0).load(width=SIMD_W) * (pb +  0).load(width=SIMD_W)
    a1 = (pa +  8).load(width=SIMD_W) * (pb +  8).load(width=SIMD_W)
    a2 = (pa + 16).load(width=SIMD_W) * (pb + 16).load(width=SIMD_W)
    a3 = (pa + 24).load(width=SIMD_W) * (pb + 24).load(width=SIMD_W)
    a4 = (pa + 32).load(width=SIMD_W) * (pb + 32).load(width=SIMD_W)
    a5 = (pa + 40).load(width=SIMD_W) * (pb + 40).load(width=SIMD_W)
    a6 = (pa + 48).load(width=SIMD_W) * (pb + 48).load(width=SIMD_W)
    a7 = (pa + 56).load(width=SIMD_W) * (pb + 56).load(width=SIMD_W)
    return ((a0 + a1) + (a2 + a3) + (a4 + a5) + (a6 + a7)).reduce_add()



def _cosine(qv, cv, q_ni, c_ni):
    if q_ni == 0.0 or c_ni == 0.0:
        return float(0.0)
    raw = _dot64(qv, cv) * q_ni * c_ni
    if raw > 1.0:
        return float(1.0)
    if raw < 0.0:
        return float(0.0)
    return raw



def _type_boost_ids(query_role, cand_role):
    if query_role == ROLE_OTHER:
        return float(0.0)
    if cand_role == query_role:
        return float(0.15)
    if cand_role != ROLE_OTHER:
        return float(-0.08)
    return float(0.0)



def _prior_boost_ids(query_src, cand_src, cand_role):
    if query_src == SOURCE_UNKNOWN:
        return float(0.0)
    if cand_src != SOURCE_UNKNOWN and cand_src != query_src:
        return float(0.0)
    if query_src == SOURCE_POS and cand_role == ROLE_UNIT:
        return float(0.10)
    if query_src == SOURCE_BACKLOG and cand_role == ROLE_DERIVED:
        return float(0.10)
    if query_src == SOURCE_INVOICE and cand_role == ROLE_DERIVED:
        return float(0.10)
    return float(0.0)





def _insert_sort_slots(slots):
    n = len(slots)
    for i in range(1, n):
        ks = slots[i].score
        kid = slots[i].column_id
        kns = slots[i].name_sim
        ktb = slots[i].type_boost
        j = i - 1
        while j >= 0 and slots[j].score < ks:
            tmp = _Slot()
            tmp.column_id  = slots[j].column_id
            tmp.score      = slots[j].score
            tmp.name_sim   = slots[j].name_sim
            tmp.type_boost = slots[j].type_boost
            slots[j + 1] = tmp
            j -= 1
        ins = _Slot()
        ins.column_id  = kid
        ins.score      = ks
        ins.name_sim   = kns
        ins.type_boost = ktb
        slots[j + 1] = ins





def check(label, ok):
    if ok:
        print("[PASS]", label)
    else:
        print("[FAIL]", label)





def main():

    table = CandidateTable()
    table.add_column(1,  SOURCE_POS,     ROLE_UNIT,    "unit_price")
    table.add_column(2,  SOURCE_POS,     ROLE_DERIVED, "extended_price")
    table.add_column(3,  SOURCE_POS,     ROLE_OTHER,   "quantity")
    table.add_column(4,  SOURCE_INVOICE, ROLE_DERIVED, "total_amount")
    table.add_column(5,  SOURCE_BACKLOG, ROLE_DERIVED, "line_total")
    table.add_column(6,  SOURCE_BACKLOG, ROLE_OTHER,   "customer_name")
    table.add_column(7,  SOURCE_UNKNOWN, ROLE_OTHER,   "description")
    table.add_column(8,  SOURCE_POS,     ROLE_UNIT,    "unit_cost")
    table.add_column(9,  SOURCE_POS,     ROLE_OTHER,   "part_number")
    table.add_column(10, SOURCE_INVOICE, ROLE_OTHER,   "invoice_date")

    check("table size = 10", table.size() == 10)


    req = build_query("unit_price", SOURCE_POS, ROLE_UNIT, 5)
    res = table.rank(req)

    check("count = 5",         int(res.count) == 5)
    check("top result = 1",    res.entries[0].column_id == 1)
    check("top score > 0.5",   res.entries[0].score > 0.5)
    check("not ambiguous",     not res.ambiguous)

    print("  top-3 for 'unit_price' (POS, UNIT):")
    for i in range(3):
        print("   #" + str(i+1)
              + " id="    + str(res.entries[i].column_id)
              + "  score=" + str(res.entries[i].score)
              + "  sim="   + str(res.entries[i].name_sim)
              + "  boost=" + str(res.entries[i].type_boost))
    print("  confidence_gap =", res.confidence_gap)


    req2 = build_query("extended_price", SOURCE_POS, ROLE_DERIVED, 5)
    res2 = table.rank(req2)
    check("extended_price top = 2", res2.entries[0].column_id == 2)


    req3 = build_query("unit", SOURCE_POS, ROLE_UNIT, 8)
    res3 = table.rank(req3)
    check("short query returns results", int(res3.count) > 0)


    print("")
    N = 10000


    t0 = perf_counter_ns()
    for _ in range(N):
        r = table.rank(req)
        _ = r.count
    t1 = perf_counter_ns()
    rank_ns = float(t1 - t0) / float(N)
    print("[BENCH] table.rank()         10 cands,", N, "iters:", rank_ns, "ns/call")


    t2 = perf_counter_ns()
    for _ in range(N):
        rq = build_query("unit_price", SOURCE_POS, ROLE_UNIT, 5)
        rr = table.rank(rq)
        _ = rr.count
    t3 = perf_counter_ns()
    full_ns = float(t3 - t2) / float(N)
    print("[BENCH] build_query + rank() 10 cands,", N, "iters:", full_ns, "ns/call")

    print("")
    print("  [ref] JSON pipeline (run_column_rank_v2): ~9302 ns/call")
    print("  [ref] pure SIMD kernel (no JSON):         ~2849 ns/call")
