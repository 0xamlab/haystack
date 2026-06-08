"""Python equivalent of mojo/engine/vector_kernels.bench_prefilter.mojo (auto-generated)."""
import math
import random as _rng

try:
    from std.math import sqrt
except Exception:
    pass
try:
    from std.time import perf_counter_ns
except Exception:
    pass

VEC_DIM = 64
SIMD_W = 8
VOCAB_SIZE = 128
SLIST_CAP = 64
BATCH_SIZE = 10

class _Vec64:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('data')
        self.data = _v0 if _v0 is not None else []
    def __repr__(self):
        return f'_Vec64({vars(self)})'

class _Entry:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('norm_inv')
        self.norm_inv = _v0 if _v0 is not None else 0.0
        _v1 = args[1] if 1 < len(args) else kwargs.get('vec')
        self.vec = _v1 if _v1 is not None else _Vec64()
    def __repr__(self):
        return f'_Entry({vars(self)})'

class _PostingSlice:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('start')
        self.start = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('count')
        self.count = _v1 if _v1 is not None else 0
    def __repr__(self):
        return f'_PostingSlice({vars(self)})'

class _PostingIndex:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('slices')
        self.slices = _v0 if _v0 is not None else []
        _v1 = args[1] if 1 < len(args) else kwargs.get('column_ids')
        self.column_ids = _v1 if _v1 is not None else []
    def __repr__(self):
        return f'_PostingIndex({vars(self)})'

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

def _dot64(a, b):
    pa = a.unsafe_ptr()
    pb = b.unsafe_ptr()
    a0 = (pa +  0).load[width=SIMD_W]() * (pb +  0).load[width=SIMD_W]()
    a1 = (pa +  8).load[width=SIMD_W]() * (pb +  8).load[width=SIMD_W]()
    a2 = (pa + 16).load[width=SIMD_W]() * (pb + 16).load[width=SIMD_W]()
    a3 = (pa + 24).load[width=SIMD_W]() * (pb + 24).load[width=SIMD_W]()
    a4 = (pa + 32).load[width=SIMD_W]() * (pb + 32).load[width=SIMD_W]()
    a5 = (pa + 40).load[width=SIMD_W]() * (pb + 40).load[width=SIMD_W]()
    a6 = (pa + 48).load[width=SIMD_W]() * (pb + 48).load[width=SIMD_W]()
    a7 = (pa + 56).load[width=SIMD_W]() * (pb + 56).load[width=SIMD_W]()
    return ((a0 + a1) + (a2 + a3) + (a4 + a5) + (a6 + a7)).reduce_add()



def _cosine(qv, cv, q_ni, c_ni):
    if q_ni == float(0.0) or c_ni == float(0.0):
        return float(0.0)
    r = _dot64(qv, cv) * q_ni * c_ni
    if r > float(1.0):
        return float(1.0)
    if r < float(0.0):
        return float(0.0)
    return r





def _col_tok(col, k):
    if k == 0:
        return col % VOCAB_SIZE
    if k == 1:
        return (col * 7  +  3) % VOCAB_SIZE
    if k == 2:
        return (col * 13 +  5) % VOCAB_SIZE
    return     (col * 3  + 11) % VOCAB_SIZE





def _make_entries(n):
    entries = []
    for col in range(n):
        e = _Entry()
        norm_sq = float(0.0)
        for d in range(VEC_DIM):
            v = float((col + d + 1) % 64) / float(32.0)
            e.vec.data[d] = v
            norm_sq = norm_sq + v * v
        if norm_sq > float(0.0):
            e.norm_inv = float(1.0) / math.sqrt(norm_sq)
        entries.append(e)
    return entries



def _make_posting_index(n):
    idx = _PostingIndex()


    counts = []
    for _ in range(VOCAB_SIZE):
        counts.append(0)

    for col in range(n):
        for k in range(4):
            tok = _col_tok(col, k)
            counts[tok] += 1


    starts = []
    starts.append(0)
    for i in range(1, VOCAB_SIZE):
        starts.append(starts[i - 1] + counts[i - 1])
    total = starts[VOCAB_SIZE - 1] + counts[VOCAB_SIZE - 1]


    for i in range(VOCAB_SIZE):
        sl = _PostingSlice()
        sl.start = int(starts[i])
        sl.count = int(counts[i])
        idx.slices.append(sl)


    for _ in range(total):
        idx.column_ids.append(int(0))


    fill_pos = []
    for i in range(VOCAB_SIZE):
        fill_pos.append(starts[i])

    for col in range(n):
        for k in range(4):
            tok = _col_tok(col, k)
            pos = fill_pos[tok]
            idx.column_ids[pos] = int(col)
            fill_pos[tok] += 1

    return idx



def _make_query():
    q = _Entry()
    for d in range(VEC_DIM):
        q.vec.data[d] = float(1.0)
    norm_sq = float(VEC_DIM)    # 64 × 1² = 64
    q.norm_inv = float(1.0) / math.sqrt(norm_sq)
    return q



def _query_token_ids():
    ids = []
    ids.append(int(0))
    ids.append(int(1))
    ids.append(int(2))
    ids.append(int(3))
    return ids





def _full_scan(entries, query, n):
    best = float(0.0)
    for i in range(n):
        s = _cosine(query.vec.data, entries[i].vec.data, query.norm_inv, entries[i].norm_inv)
        if s > best:
            best = s
    return best



def _run_tier(n, iters):
    entries = _make_entries(n)
    idx = _make_posting_index(n)
    query = _make_query()
    tok_ids = _query_token_ids()


    marks = []
    cands = []
    for _ in range(n):         marks.append(int(0))
    for _ in range(SLIST_CAP): cands.append(int(0))
    epoch = int(1)



    n_cands_check = 0
    epoch_chk = int(0xFFFF)
    for t in range(len(tok_ids)):
        tok = int(tok_ids[t])
        start = int(idx.slices[tok].start)
        count = int(idx.slices[tok].count)
        for j in range(count):
            col = int(idx.column_ids[start + j])
            if marks[col] != epoch_chk:
                if n_cands_check >= SLIST_CAP:
                    continue
                marks[col] = epoch_chk
                n_cands_check += 1

    for i in range(n):
        marks[i] = int(0)

    acc = float(0.0)   # prevents dead-code elimination


    t0 = perf_counter_ns()
    for _ in range(iters):
        acc = acc + _full_scan(entries, query, n)
    t1 = perf_counter_ns()
    ns_a = float(t1 - t0) / float(iters)


    t2 = perf_counter_ns()
    for _ in range(iters):
        acc = acc + _prefilter_score(
            entries, query, tok_ids,
            idx.slices, idx.column_ids,
            marks, cands, epoch,
        )
    t3 = perf_counter_ns()
    ns_b = float(t3 - t2) / float(iters)


    t4 = perf_counter_ns()
    for _ in range(iters):
        for _ in range(BATCH_SIZE):
            acc = acc + _full_scan(entries, query, n)
    t5 = perf_counter_ns()
    ns_c = float(t5 - t4) / float(iters * BATCH_SIZE)


    t6 = perf_counter_ns()
    for _ in range(iters):
        for _ in range(BATCH_SIZE):
            acc = acc + _prefilter_score(
                entries, query, tok_ids,
                idx.slices, idx.column_ids,
                marks, cands, epoch,
            )
    t7 = perf_counter_ns()
    ns_d = float(t7 - t6) / float(iters * BATCH_SIZE)


    spd_b = ns_a / ns_b   if ns_b > 0.0 else float(0.0)
    spd_d = ns_c / ns_d   if ns_d > 0.0 else float(0.0)

    print("[N=", n, " shortlist~", n_cands_check, "]")
    print("  A full_scan   single :", ns_a,  "ns/query")
    print("  B prefilter   single :", ns_b,  "ns/query  speedup vs A:", spd_b)
    print("  C full_scan   batch10:", ns_c,  "ns/query")
    print("  D prefilter   batch10:", ns_d,  "ns/query  speedup vs C:", spd_d)
    print()


    print("  checksum:", acc)





def main():
    print("=== bench_prefilter_vs_fullscan ===")
    print("VEC_DIM=64  VOCAB=128  TOKS_PER_COL=4  QUERY_TOKS=4  SHORTLIST_CAP=64")
    print()


    _run_tier(32, 100)


    print("── 32 columns (2000 iters) ──────────────────────────────────────────")
    _run_tier(32,   2000)

    print("── 128 columns (2000 iters) ─────────────────────────────────────────")
    _run_tier(128,  2000)

    print("── 512 columns (1000 iters) ─────────────────────────────────────────")
    _run_tier(512,  1000)

    print("── 2048 columns (500 iters) ─────────────────────────────────────────")
    _run_tier(2048,  500)
