"""
vector_kernels/batch_ranker.mojo — Pre-filtered shortlist scorer + batch API.

Sits on top of table.mojo (SIMD cosine) and prefilter.mojo (candidate filter).
Provides:

  QueryForRank   — RankRequest extended with token IDs for pre-filter
  rank_shortlist — SIMD-score only the pre-filtered candidates
  rank_batch     — process a List[QueryForRank] with a shared scratch buffer

Typical latency with pre-filter (10-candidate shortlist from 1000-col schema):
  prefilter:     ~200 ns   (token posting walk)
  rank_shortlist:  ~300 ns  (10 SIMD dots)
  total:          ~500 ns   (vs ~1765 ns all-column scan on 10-col table)

Updated RankResult ABI (backwards-compatible additions):
  - planner_flags: UInt8  — bit 0 = confident, bit 1 = fallback_used
  - token_overlap: UInt8  — max shared token count for top-1 result

Mojo 0.26 ownership notes:
  - .copy() in __moveinit__ for all List fields
  - No ^ on struct fields
"""

from std.math import sqrt
from std.time import perf_counter_ns


# ── Shared constants (mirror table.mojo) ─────────────────────────────────────

comptime VEC_DIM:    Int     = 64
comptime SIMD_W:     Int     = 8
comptime RANK_TOP_K: Int     = 8
comptime AMBIG_GAP:  Float32 = Float32(0.08)
comptime MIN_ACCEPT: Float32 = Float32(0.72)  # planner confidence threshold
comptime W_NAME:     Float32 = Float32(0.55)

comptime SOURCE_UNKNOWN: UInt16 = 0
comptime SOURCE_POS:     UInt16 = 1
comptime SOURCE_BACKLOG: UInt16 = 2
comptime SOURCE_INVOICE: UInt16 = 3

comptime ROLE_OTHER:   UInt8 = 0
comptime ROLE_UNIT:    UInt8 = 1
comptime ROLE_DERIVED: UInt8 = 2


# ── Planner result flags ──────────────────────────────────────────────────────

comptime FLAG_CONFIDENT:     UInt8 = 1   # bit 0: best_score >= MIN_ACCEPT AND gap >= AMBIG_GAP
comptime FLAG_FALLBACK_USED: UInt8 = 2   # bit 1: prefilter had too few hits, ran all-column
comptime FLAG_AMBIGUOUS:     UInt8 = 4   # bit 2: gap < AMBIG_GAP (needs clarification)


# ── SIMD kernels (inline — same as table.mojo) ────────────────────────────────

@always_inline
def _dot64(a: List[Float32], b: List[Float32]) -> Float32:
    var pa = a.unsafe_ptr()
    var pb = b.unsafe_ptr()
    var a0 = (pa +  0).load[width=SIMD_W]() * (pb +  0).load[width=SIMD_W]()
    var a1 = (pa +  8).load[width=SIMD_W]() * (pb +  8).load[width=SIMD_W]()
    var a2 = (pa + 16).load[width=SIMD_W]() * (pb + 16).load[width=SIMD_W]()
    var a3 = (pa + 24).load[width=SIMD_W]() * (pb + 24).load[width=SIMD_W]()
    var a4 = (pa + 32).load[width=SIMD_W]() * (pb + 32).load[width=SIMD_W]()
    var a5 = (pa + 40).load[width=SIMD_W]() * (pb + 40).load[width=SIMD_W]()
    var a6 = (pa + 48).load[width=SIMD_W]() * (pb + 48).load[width=SIMD_W]()
    var a7 = (pa + 56).load[width=SIMD_W]() * (pb + 56).load[width=SIMD_W]()
    return ((a0 + a1) + (a2 + a3) + (a4 + a5) + (a6 + a7)).reduce_add()


@always_inline
def _cosine(qv: List[Float32], cv: List[Float32], q_ni: Float32, c_ni: Float32) -> Float32:
    if q_ni == 0.0 or c_ni == 0.0:
        return Float32(0.0)
    var raw = _dot64(qv, cv) * q_ni * c_ni
    if raw > 1.0: return Float32(1.0)
    if raw < 0.0: return Float32(0.0)
    return raw


@always_inline
def _type_boost(query_role: UInt8, cand_role: UInt8) -> Float32:
    if query_role == ROLE_OTHER: return Float32(0.0)
    if cand_role == query_role:  return Float32(0.15)
    if cand_role != ROLE_OTHER:  return Float32(-0.08)
    return Float32(0.0)


@always_inline
def _prior_boost(query_src: UInt16, cand_src: UInt16, cand_role: UInt8) -> Float32:
    if query_src == SOURCE_UNKNOWN: return Float32(0.0)
    if cand_src != SOURCE_UNKNOWN and cand_src != query_src: return Float32(0.0)
    if query_src == SOURCE_POS     and cand_role == ROLE_UNIT:    return Float32(0.10)
    if query_src == SOURCE_BACKLOG and cand_role == ROLE_DERIVED: return Float32(0.10)
    if query_src == SOURCE_INVOICE and cand_role == ROLE_DERIVED: return Float32(0.10)
    return Float32(0.0)


# ── Insertion-sort scratch slot (primitives only — no copy issues) ─────────────

struct _Slot(Copyable, Movable):
    var col_idx:    Int     # index into CandidateTable.entries
    var column_id:  UInt32
    var score:      Float32
    var name_sim:   Float32
    var type_boost: Float32
    var tok_hits:   UInt16

    def __init__(out self):
        self.col_idx    = 0
        self.column_id  = 0
        self.score      = Float32(0.0)
        self.name_sim   = Float32(0.0)
        self.type_boost = Float32(0.0)
        self.tok_hits   = 0

    def __copyinit__(out self, copy: Self):
        self.col_idx    = copy.col_idx
        self.column_id  = copy.column_id
        self.score      = copy.score
        self.name_sim   = copy.name_sim
        self.type_boost = copy.type_boost
        self.tok_hits   = copy.tok_hits

    def __moveinit__(out self, var take: Self):
        self.col_idx    = take.col_idx
        self.column_id  = take.column_id
        self.score      = take.score
        self.name_sim   = take.name_sim
        self.type_boost = take.type_boost
        self.tok_hits   = take.tok_hits


def _sort_slots(mut slots: List[_Slot]):
    var n = len(slots)
    for i in range(1, n):
        var ks  = slots[i].score
        var kid = slots[i].col_idx
        var kci = slots[i].column_id
        var kns = slots[i].name_sim
        var ktb = slots[i].type_boost
        var kth = slots[i].tok_hits
        var j   = i - 1
        while j >= 0 and slots[j].score < ks:
            var tmp = _Slot()
            tmp.col_idx    = slots[j].col_idx
            tmp.column_id  = slots[j].column_id
            tmp.score      = slots[j].score
            tmp.name_sim   = slots[j].name_sim
            tmp.type_boost = slots[j].type_boost
            tmp.tok_hits   = slots[j].tok_hits
            slots[j + 1]   = tmp^
            j -= 1
        var ins = _Slot()
        ins.col_idx    = kid
        ins.column_id  = kci
        ins.score      = ks
        ins.name_sim   = kns
        ins.type_boost = ktb
        ins.tok_hits   = kth
        slots[j + 1]   = ins^


# ── Inlined CandidateEntry / CandidateTable types ─────────────────────────────
#
# These mirror table.mojo. Once package-level imports are stable, remove these
# and import from table.mojo directly.

struct _Vec64(Copyable, Movable):
    var data: List[Float32]
    def __init__(out self):
        self.data = List[Float32](capacity=VEC_DIM)
        for _ in range(VEC_DIM): self.data.append(Float32(0.0))
    def __copyinit__(out self, copy: Self):
        self.data = copy.data.copy()
    def __moveinit__(out self, var take: Self):
        self.data = take.data.copy()


struct CandidateEntry(Copyable, Movable):
    var column_id: UInt32
    var source_id: UInt16
    var role_id:   UInt8
    var norm_inv:  Float32
    var vec:       _Vec64
    def __init__(out self):
        self.column_id = 0; self.source_id = SOURCE_UNKNOWN
        self.role_id   = ROLE_OTHER; self.norm_inv = Float32(0.0); self.vec = _Vec64()
    def __copyinit__(out self, copy: Self):
        self.column_id = copy.column_id; self.source_id = copy.source_id
        self.role_id   = copy.role_id;   self.norm_inv  = copy.norm_inv
        self.vec       = copy.vec.copy()
    def __moveinit__(out self, var take: Self):
        self.column_id = take.column_id; self.source_id = take.source_id
        self.role_id   = take.role_id;   self.norm_inv  = take.norm_inv
        self.vec       = take.vec.copy()


# ── TopKEntry / RankResult ────────────────────────────────────────────────────

@fieldwise_init
struct TopKEntry(Copyable, Movable):
    var column_id:  UInt32
    var score:      Float32
    var name_sim:   Float32
    var type_boost: Float32

    def __init__(out self):
        self.column_id  = 0;         self.score      = Float32(0.0)
        self.name_sim   = Float32(0.0); self.type_boost = Float32(0.0)

    def __copyinit__(out self, copy: Self):
        self.column_id = copy.column_id; self.score      = copy.score
        self.name_sim  = copy.name_sim;  self.type_boost = copy.type_boost

    def __moveinit__(out self, var take: Self):
        self.column_id = take.column_id; self.score      = take.score
        self.name_sim  = take.name_sim;  self.type_boost = take.type_boost


@fieldwise_init
struct RankResult(Copyable, Movable):
    """
    Top-k result with added planner flags (backwards-compatible with table.mojo).

    New fields vs table.mojo RankResult:
      planner_flags: UInt8  — FLAG_CONFIDENT, FLAG_FALLBACK_USED, FLAG_AMBIGUOUS
      token_overlap: UInt8  — max shared token count for top-1 result (explainability)
    """
    var count:          UInt8
    var ambiguous:      Bool
    var confidence_gap: Float32
    var entries:        List[TopKEntry]

    # Planner extensions
    var planner_flags:  UInt8   # bit flags: confident / fallback / ambiguous
    var token_overlap:  UInt8   # shared token hits for top result

    def __init__(out self):
        self.count          = 0
        self.ambiguous      = False
        self.confidence_gap = Float32(0.0)
        self.entries        = List[TopKEntry](capacity=RANK_TOP_K)
        for _ in range(RANK_TOP_K):
            self.entries.append(TopKEntry())
        self.planner_flags  = 0
        self.token_overlap  = 0

    def __copyinit__(out self, copy: Self):
        self.count          = copy.count
        self.ambiguous      = copy.ambiguous
        self.confidence_gap = copy.confidence_gap
        self.entries        = copy.entries.copy()
        self.planner_flags  = copy.planner_flags
        self.token_overlap  = copy.token_overlap

    def __moveinit__(out self, var take: Self):
        self.count          = take.count
        self.ambiguous      = take.ambiguous
        self.confidence_gap = take.confidence_gap
        self.entries        = take.entries.copy()   # ^ disallowed; use copy
        self.planner_flags  = take.planner_flags
        self.token_overlap  = take.token_overlap

    def is_confident(self) -> Bool:
        return (self.planner_flags & FLAG_CONFIDENT) != 0


# ── QueryForRank: RankRequest + token IDs for pre-filter ─────────────────────

struct QueryForRank(Copyable, Movable):
    """
    Extended query that carries both the vector (for SIMD scoring) and the
    token IDs (for pre-filter). Build once per request.

    Python side:
        token_strs = tokenize_name("unit_price")    # ["unit", "price"]
        token_ids  = [vocab[t] for t in token_strs if t in vocab]
        q = QueryForRank()
        q.source_id      = SOURCE_POS
        q.role_id        = ROLE_UNIT
        q.top_k          = 5
        q.query_norm_inv = build_vec64("unit_price", q.query_vec.data)
        q.set_token_ids(token_ids)
    """
    var source_id:      UInt16
    var role_id:        UInt8
    var top_k:          UInt8
    var query_norm_inv: Float32
    var query_vec:      _Vec64

    var token_count:    UInt8
    var token_ids:      List[UInt32]   # up to ~8 query tokens

    def __init__(out self):
        self.source_id      = SOURCE_UNKNOWN
        self.role_id        = ROLE_OTHER
        self.top_k          = 5
        self.query_norm_inv = Float32(0.0)
        self.query_vec      = _Vec64()
        self.token_count    = 0
        self.token_ids      = List[UInt32](capacity=8)
        for _ in range(8):
            self.token_ids.append(UInt32(0))

    def __copyinit__(out self, copy: Self):
        self.source_id      = copy.source_id
        self.role_id        = copy.role_id
        self.top_k          = copy.top_k
        self.query_norm_inv = copy.query_norm_inv
        self.query_vec      = copy.query_vec.copy()
        self.token_count    = copy.token_count
        self.token_ids      = copy.token_ids.copy()

    def __moveinit__(out self, var take: Self):
        self.source_id      = take.source_id
        self.role_id        = take.role_id
        self.top_k          = take.top_k
        self.query_norm_inv = take.query_norm_inv
        self.query_vec      = take.query_vec.copy()   # ^ disallowed; use copy
        self.token_count    = take.token_count
        self.token_ids      = take.token_ids.copy()

    def set_token_ids(mut self, ids: List[UInt32]):
        """Copy token IDs from a Python-provided list (max 8)."""
        var n = len(ids) if len(ids) <= 8 else 8
        self.token_count = UInt8(n)
        for i in range(n):
            self.token_ids[i] = ids[i]


# ── CandidateScratch import stub (mirrors prefilter.mojo) ────────────────────
#
# Production: import from prefilter.mojo
# Stub just the fields rank_shortlist needs:

struct _Scratch:
    """Read-only view used by rank_shortlist. Actual struct lives in prefilter.mojo."""
    var candidate_count: Int
    var candidate_ids:   List[UInt32]
    var token_hits:      List[UInt16]


# ── rank_shortlist: SIMD score over pre-filtered candidates ────────────────────

def rank_shortlist(
    entries:       List[CandidateEntry],  # from CandidateTable
    req:           QueryForRank,
    candidate_ids: List[UInt32],          # from CandidateScratch
    token_hits:    List[UInt16],          # from CandidateScratch
    n_candidates:  Int,
    fallback_used: Bool = False,
) -> RankResult:
    """
    Score a shortlist of n_candidates columns and return the top-k result.

    This is the hot path after pre-filtering. Only n_candidates SIMD dot
    products run (vs len(entries) in the all-column scan).

    Token-hit bonus: each shared token adds 0.05 to the score (cap at 3 hits
    = +0.15). This boosts candidates that matched on multiple relevant tokens
    and helps open up confidence_gap on ties.

    Complexity: O(n_candidates × VEC_DIM/SIMD_W)
    """
    var top_k  = Int(req.top_k) if Int(req.top_k) <= RANK_TOP_K else RANK_TOP_K
    var slots  = List[_Slot]()

    for k in range(n_candidates):
        var col_idx = Int(candidate_ids[k])
        var hits    = Int(token_hits[k])

        var c_id  = entries[col_idx].column_id
        var c_src = entries[col_idx].source_id
        var c_rol = entries[col_idx].role_id
        var c_ni  = entries[col_idx].norm_inv

        # SIMD cosine — no intermediate copy of vec.data
        var nsim = _cosine(
            req.query_vec.data,
            entries[col_idx].vec.data,
            req.query_norm_inv,
            c_ni,
        )

        var tb = _type_boost(req.role_id, c_rol)
        var pb = _prior_boost(req.source_id, c_src, c_rol)

        # Token-hit bonus: 0.05 per shared token, capped at 3 tokens
        var th = Float32(0.05) * Float32(hits if hits < 3 else 3)

        var fs = W_NAME * nsim + tb + pb + th
        if fs > 1.0: fs = Float32(1.0)
        elif fs < 0.0: fs = Float32(0.0)

        var slot = _Slot()
        slot.col_idx    = col_idx
        slot.column_id  = c_id
        slot.score      = fs
        slot.name_sim   = nsim
        slot.type_boost = tb + pb
        slot.tok_hits   = UInt16(hits)
        slots.append(slot^)

    if len(slots) == 0:
        return RankResult()

    _sort_slots(slots)

    var result  = RankResult()
    var out_n   = len(slots) if len(slots) < top_k else top_k
    result.count = UInt8(out_n)

    # Confidence gap + ambiguity
    var gap = Float32(0.0)
    if len(slots) >= 2:
        gap = slots[0].score - slots[1].score
    result.confidence_gap = gap
    result.ambiguous      = gap < AMBIG_GAP and len(slots) >= 2
    result.token_overlap  = UInt8(slots[0].tok_hits) if out_n > 0 else UInt8(0)

    # Planner flags
    var flags = UInt8(0)
    if slots[0].score >= MIN_ACCEPT and gap >= AMBIG_GAP:
        flags = flags | FLAG_CONFIDENT
    if result.ambiguous:
        flags = flags | FLAG_AMBIGUOUS
    if fallback_used:
        flags = flags | FLAG_FALLBACK_USED
    result.planner_flags = flags

    for i in range(out_n):
        result.entries[i].column_id  = slots[i].column_id
        result.entries[i].score      = slots[i].score
        result.entries[i].name_sim   = slots[i].name_sim
        result.entries[i].type_boost = slots[i].type_boost

    return result^


# ── rank_batch: process multiple queries sharing one scratch buffer ────────────

def rank_batch(
    entries:     List[CandidateEntry],  # CandidateTable.entries
    source_ids:  List[UInt16],          # flat parallel arrays for fast prefilter
    role_ids:    List[UInt8],
    requests:    List[QueryForRank],
    slices:      List[_PostingSlice],   # from TokenPostingIndex
    column_ids_idx: List[UInt32],       # posting flat buffer (renamed: avoids shadowing)
    mut marks:   List[UInt32],          # scratch epoch marks [n_columns]
    mut slots_s: List[Int32],           # scratch slots [n_columns]
    mut cand_ids: List[UInt32],         # scratch candidate_ids [shortlist_cap]
    mut tok_hits: List[UInt16],         # scratch token_hits [shortlist_cap]
    mut epoch:   UInt32,
    shortlist_cap: Int,
    mut results: List[RankResult],
):
    """
    Process a batch of QueryForRank requests sharing one scratch buffer.

    The scratch arrays are passed individually (not as CandidateScratch) so
    they can be stored outside the function without List copy overhead.
    In production, wrap these in a CandidateScratch struct.

    Benefits of batching:
      - query_vec stays warm in L1/L2 cache across the prefilter call
      - FFI crossing overhead amortized over N requests
      - PostingIndex arrays stay hot in L2 across multiple token lookups

    Complexity per request: O(Σ postings[query_tokens]) + O(shortlist × VEC_DIM/8)
    """
    var n_columns = len(entries)
    var n_requests = len(requests)
    var vocab_size = len(slices)

    for ri in range(n_requests):
        var req = requests[ri].copy()

        # ── Epoch reset (O(1)) ──────────────────────────────────────────
        if epoch == UInt32(0xFFFFFFFF):
            for i in range(n_columns):
                marks[i] = UInt32(0)
                slots_s[i] = Int32(-1)
            epoch = 1
        else:
            epoch += 1
        var candidate_count = 0
        var fallback_used = False

        # ── Token posting filter ────────────────────────────────────────
        var n_tokens = Int(req.token_count)
        for t in range(n_tokens):
            var tok_id = Int(req.token_ids[t])
            if tok_id >= vocab_size:
                continue
            var start = Int(slices[tok_id].start)
            var count = Int(slices[tok_id].count)

            for j in range(count):
                var col_idx = Int(column_ids_idx[start + j])
                if col_idx >= n_columns:
                    continue

                # Source gate
                if req.source_id != SOURCE_UNKNOWN:
                    var c_src = source_ids[col_idx]
                    if c_src != SOURCE_UNKNOWN and c_src != req.source_id:
                        continue

                # Role gate (same logic as prefilter.mojo _role_compatible)
                var c_rol = role_ids[col_idx]
                if req.role_id != ROLE_OTHER and c_rol != ROLE_OTHER and c_rol != req.role_id:
                    continue

                # Epoch dedup
                if marks[col_idx] != epoch:
                    if candidate_count >= shortlist_cap:
                        continue
                    marks[col_idx]            = epoch
                    slots_s[col_idx]          = Int32(candidate_count)
                    cand_ids[candidate_count] = UInt32(col_idx)
                    tok_hits[candidate_count] = UInt16(1)
                    candidate_count          += 1
                else:
                    var sl = Int(slots_s[col_idx])
                    if sl >= 0 and tok_hits[sl] < UInt16(255):
                        tok_hits[sl] += UInt16(1)

        # ── Fallback if shortlist too small ─────────────────────────────
        if candidate_count < 2:
            # Bump epoch, run all-column scan
            if epoch == UInt32(0xFFFFFFFF):
                for i in range(n_columns):
                    marks[i]   = UInt32(0)
                    slots_s[i] = Int32(-1)
                epoch = 1
            else:
                epoch += 1
            candidate_count = 0
            fallback_used   = True
            for col_idx in range(n_columns):
                if candidate_count >= shortlist_cap:
                    break
                marks[col_idx]            = epoch
                slots_s[col_idx]          = Int32(candidate_count)
                cand_ids[candidate_count] = UInt32(col_idx)
                tok_hits[candidate_count] = UInt16(0)
                candidate_count          += 1

        # ── SIMD score shortlist ─────────────────────────────────────────
        results.append(
            rank_shortlist(
                entries,
                req,
                cand_ids,
                tok_hits,
                candidate_count,
                fallback_used,
            )
        )


# ── Planner-facing helper ─────────────────────────────────────────────────────

struct PlannerResolution(Copyable, Movable):
    """
    Compact result for the decision planner.

    The planner only needs: resolved column_id, score, confidence.
    Full top-k is passed for clarification fallback.
    """
    var resolved_column_id: UInt32
    var score:              Float32
    var confidence_gap:     Float32
    var confident:          Bool
    var ambiguous:          Bool
    var fallback_used:      Bool

    def __init__(out self):
        self.resolved_column_id = 0
        self.score              = Float32(0.0)
        self.confidence_gap     = Float32(0.0)
        self.confident          = False
        self.ambiguous          = True
        self.fallback_used      = False

    def __copyinit__(out self, copy: Self):
        self.resolved_column_id = copy.resolved_column_id
        self.score              = copy.score
        self.confidence_gap     = copy.confidence_gap
        self.confident          = copy.confident
        self.ambiguous          = copy.ambiguous
        self.fallback_used      = copy.fallback_used

    def __moveinit__(out self, var take: Self):
        self.resolved_column_id = take.resolved_column_id
        self.score              = take.score
        self.confidence_gap     = take.confidence_gap
        self.confident          = take.confident
        self.ambiguous          = take.ambiguous
        self.fallback_used      = take.fallback_used


def to_planner_resolution(result: RankResult) -> PlannerResolution:
    """
    Extract the planner decision from a RankResult.

    Planner rule:
      confident = best_score >= MIN_ACCEPT(0.72) AND gap >= AMBIG_GAP(0.08)
      If not confident → mark ambiguous → trigger clarification or fallback
    """
    var p = PlannerResolution()
    if Int(result.count) > 0:
        p.resolved_column_id = result.entries[0].column_id
        p.score              = result.entries[0].score
    p.confidence_gap = result.confidence_gap
    p.confident      = (result.planner_flags & FLAG_CONFIDENT) != 0
    p.ambiguous      = result.ambiguous
    p.fallback_used  = (result.planner_flags & FLAG_FALLBACK_USED) != 0
    return p^


# ── _PostingSlice stub (to avoid prefilter.mojo import in standalone) ─────────

struct _PostingSlice(Copyable, Movable):
    var start: UInt32
    var count: UInt16
    def __init__(out self): self.start = 0; self.count = 0
    def __copyinit__(out self, copy: Self): self.start = copy.start; self.count = copy.count
    def __moveinit__(out self, var take: Self): self.start = take.start; self.count = take.count


def main():
    pass
