"""Python equivalent of mojo/engine/vector_kernels.batch_ranker.mojo (auto-generated)."""
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
RANK_TOP_K = 8
AMBIG_GAP = float(0.08)
MIN_ACCEPT = float(0.72)  # planner confidence threshold
W_NAME = float(0.55)
SOURCE_UNKNOWN = 0
SOURCE_POS = 1
SOURCE_BACKLOG = 2
SOURCE_INVOICE = 3
ROLE_OTHER = 0
ROLE_UNIT = 1
ROLE_DERIVED = 2
FLAG_CONFIDENT = 1   # bit 0: best_score >= MIN_ACCEPT AND gap >= AMBIG_GAP
FLAG_FALLBACK_USED = 2   # bit 1: prefilter had too few hits, ran all-column
FLAG_AMBIGUOUS = 4   # bit 2: gap < AMBIG_GAP (needs clarification)

class _Slot:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('col_idx')
        self.col_idx = _v0 if _v0 is not None else None
        _v1 = args[1] if 1 < len(args) else kwargs.get('column_id')
        self.column_id = _v1 if _v1 is not None else 0
        _v2 = args[2] if 2 < len(args) else kwargs.get('score')
        self.score = _v2 if _v2 is not None else 0.0
        _v3 = args[3] if 3 < len(args) else kwargs.get('name_sim')
        self.name_sim = _v3 if _v3 is not None else 0.0
        _v4 = args[4] if 4 < len(args) else kwargs.get('type_boost')
        self.type_boost = _v4 if _v4 is not None else 0.0
        _v5 = args[5] if 5 < len(args) else kwargs.get('tok_hits')
        self.tok_hits = _v5 if _v5 is not None else 0
    def __repr__(self):
        return f'_Slot({vars(self)})'

class _Vec64:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('data')
        self.data = _v0 if _v0 is not None else []
    def __repr__(self):
        return f'_Vec64({vars(self)})'

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
        _v4 = args[4] if 4 < len(args) else kwargs.get('planner_flags')
        self.planner_flags = _v4 if _v4 is not None else None
        _v5 = args[5] if 5 < len(args) else kwargs.get('token_overlap')
        self.token_overlap = _v5 if _v5 is not None else None
    def __repr__(self):
        return f'RankResult({vars(self)})'
    def is_confident(self):
        return (self.planner_flags & FLAG_CONFIDENT) != 0
    
    

class QueryForRank:
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
        _v5 = args[5] if 5 < len(args) else kwargs.get('token_count')
        self.token_count = _v5 if _v5 is not None else 0
        _v6 = args[6] if 6 < len(args) else kwargs.get('token_ids')
        self.token_ids = _v6 if _v6 is not None else []
    def __repr__(self):
        return f'QueryForRank({vars(self)})'
    def set_token_ids(self, ids):
        n = len(ids) if len(ids) <= 8 else 8
        self.token_count = int(n)
        for i in range(n):
            self.token_ids[i] = ids[i]
    
    

class _Scratch:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('candidate_count')
        self.candidate_count = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('candidate_ids')
        self.candidate_ids = _v1 if _v1 is not None else []
        _v2 = args[2] if 2 < len(args) else kwargs.get('token_hits')
        self.token_hits = _v2 if _v2 is not None else []
    def __repr__(self):
        return f'_Scratch({vars(self)})'

class PlannerResolution:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('resolved_column_id')
        self.resolved_column_id = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('score')
        self.score = _v1 if _v1 is not None else 0.0
        _v2 = args[2] if 2 < len(args) else kwargs.get('confidence_gap')
        self.confidence_gap = _v2 if _v2 is not None else 0.0
        _v3 = args[3] if 3 < len(args) else kwargs.get('confident')
        self.confident = _v3 if _v3 is not None else False
        _v4 = args[4] if 4 < len(args) else kwargs.get('ambiguous')
        self.ambiguous = _v4 if _v4 is not None else False
        _v5 = args[5] if 5 < len(args) else kwargs.get('fallback_used')
        self.fallback_used = _v5 if _v5 is not None else False
    def __repr__(self):
        return f'PlannerResolution({vars(self)})'

class _PostingSlice:
    def __init__(self, *args, **kwargs):
        _v0 = args[0] if 0 < len(args) else kwargs.get('start')
        self.start = _v0 if _v0 is not None else 0
        _v1 = args[1] if 1 < len(args) else kwargs.get('count')
        self.count = _v1 if _v1 is not None else 0
    def __repr__(self):
        return f'_PostingSlice({vars(self)})'

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



def _type_boost(query_role, cand_role):
    if query_role == ROLE_OTHER:
        return float(0.0)
    if cand_role == query_role:
        return float(0.15)
    if cand_role != ROLE_OTHER:
        return float(-0.08)
    return float(0.0)



def _prior_boost(query_src, cand_src, cand_role):
    if query_src == SOURCE_UNKNOWN:
        return float(0.0)
    if cand_src != SOURCE_UNKNOWN and cand_src != query_src:
        return float(0.0)
    if query_src == SOURCE_POS     and cand_role == ROLE_UNIT:
        return float(0.10)
    if query_src == SOURCE_BACKLOG and cand_role == ROLE_DERIVED:
        return float(0.10)
    if query_src == SOURCE_INVOICE and cand_role == ROLE_DERIVED:
        return float(0.10)
    return float(0.0)





def _sort_slots(slots):
    n = len(slots)
    for i in range(1, n):
        ks = slots[i].score
        kid = slots[i].col_idx
        kci = slots[i].column_id
        kns = slots[i].name_sim
        ktb = slots[i].type_boost
        kth = slots[i].tok_hits
        j = i - 1
        while j >= 0 and slots[j].score < ks:
            tmp = _Slot()
            tmp.col_idx    = slots[j].col_idx
            tmp.column_id  = slots[j].column_id
            tmp.score      = slots[j].score
            tmp.name_sim   = slots[j].name_sim
            tmp.type_boost = slots[j].type_boost
            tmp.tok_hits   = slots[j].tok_hits
            slots[j + 1]   = tmp
            j -= 1
        ins = _Slot()
        ins.col_idx    = kid
        ins.column_id  = kci
        ins.score      = ks
        ins.name_sim   = kns
        ins.type_boost = ktb
        ins.tok_hits   = kth
        slots[j + 1]   = ins








def main():
    pass
