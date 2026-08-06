"""
test_table.mojo — Compile verification + correctness check + benchmark
for CandidateTable resident-table hot path.

Run:
    cd mojo_env && pixi run mojo run ../mojo/engine/vector_kernels/test_table.mojo

Mojo 0.26 ownership notes applied here:
  - List[T] is NOT ImplicitlyCopyable — use field.copy() in __copyinit__
  - Partial field-moves from 'var take' are not allowed in __moveinit__ when
    other fields remain alive after the ^. Solutions:
      (a) Single-field struct: self.field = take.field^ (OK — nothing after)
      (b) Multi-field struct: use .copy() in __moveinit__ for all List fields
  - _Vec64 drops the redundant norm_inv field (callers store it separately)
    → becomes a single-field wrapper → __moveinit__ uses take.data^
  - CandidateTable has a single entries field → __moveinit__ uses take.entries^
"""

from std.time import perf_counter_ns
from std.math import sqrt


# ── Constants ─────────────────────────────────────────────────────────────────

comptime VEC_DIM:    Int     = 64
comptime SIMD_W:     Int     = 8
comptime RANK_TOP_K: Int     = 8
comptime AMBIG_GAP:  Float32 = Float32(0.08)
comptime W_NAME:     Float32 = Float32(0.55)

comptime SOURCE_UNKNOWN: UInt16 = 0
comptime SOURCE_POS:     UInt16 = 1
comptime SOURCE_BACKLOG: UInt16 = 2
comptime SOURCE_INVOICE: UInt16 = 3

comptime ROLE_OTHER:   UInt8 = 0
comptime ROLE_UNIT:    UInt8 = 1
comptime ROLE_DERIVED: UInt8 = 2


# ── _Vec64: single-field wrapper so __moveinit__ can use take.data^ ───────────
#
# norm_inv is NOT stored here — callers (CandidateEntry, RankRequest) hold it
# directly. This keeps _Vec64 to ONE field, making ownership transfers valid.

struct _Vec64(Copyable, Movable):
    var data: List[Float32]

    def __init__(out self):
        self.data = List[Float32](capacity=VEC_DIM)
        for _ in range(VEC_DIM):
            self.data.append(Float32(0.0))

    def __copyinit__(out self, copy: Self):
        self.data = copy.data.copy()   # explicit — List not ImplicitlyCopyable

    def __moveinit__(out self, var take: Self):
        self.data = take.data.copy()   # ^ on fields not allowed; runtime destroys take


# ── SIMD kernels ──────────────────────────────────────────────────────────────

@always_inline
def _norm_byte(c: UInt8) -> UInt8:
    if c == 95 or c == 45 or c == 46:   # _ - .
        return 32
    if c >= 65 and c <= 90:             # A-Z → a-z
        return c + 32
    return c


def _build_vec_inplace(s: String, mut buf: List[Float32]) -> Float32:
    """Zero buf, fill bigram counts (direct byte scan), return norm_inv."""
    for i in range(VEC_DIM):
        buf[i] = Float32(0.0)
    var sb = s.as_bytes()
    var n  = len(sb)
    if n == 0:
        return Float32(0.0)
    var prev = _norm_byte(sb[0])
    for i in range(1, n):
        var cur = _norm_byte(sb[i])
        var h = (Int(prev) * 31 + Int(cur)) & (VEC_DIM - 1)
        buf[h] += Float32(1.0)
        prev = cur
    var p = buf.unsafe_ptr()
    var s0 = (p +  0).load[width=SIMD_W]()
    var s1 = (p +  8).load[width=SIMD_W]()
    var s2 = (p + 16).load[width=SIMD_W]()
    var s3 = (p + 24).load[width=SIMD_W]()
    var s4 = (p + 32).load[width=SIMD_W]()
    var s5 = (p + 40).load[width=SIMD_W]()
    var s6 = (p + 48).load[width=SIMD_W]()
    var s7 = (p + 56).load[width=SIMD_W]()
    var mag = (
        (s0*s0 + s1*s1) + (s2*s2 + s3*s3) +
        (s4*s4 + s5*s5) + (s6*s6 + s7*s7)
    ).reduce_add()
    if mag <= 0.0:
        return Float32(0.0)
    return Float32(1.0) / sqrt(mag)


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
def _type_boost_ids(query_role: UInt8, cand_role: UInt8) -> Float32:
    if query_role == ROLE_OTHER:
        return Float32(0.0)
    if cand_role == query_role:
        return Float32(0.15)
    if cand_role != ROLE_OTHER:
        return Float32(-0.08)
    return Float32(0.0)


@always_inline
def _prior_boost_ids(query_src: UInt16, cand_src: UInt16, cand_role: UInt8) -> Float32:
    if query_src == SOURCE_UNKNOWN:
        return Float32(0.0)
    if cand_src != SOURCE_UNKNOWN and cand_src != query_src:
        return Float32(0.0)
    if query_src == SOURCE_POS and cand_role == ROLE_UNIT:
        return Float32(0.10)
    if query_src == SOURCE_BACKLOG and cand_role == ROLE_DERIVED:
        return Float32(0.10)
    if query_src == SOURCE_INVOICE and cand_role == ROLE_DERIVED:
        return Float32(0.10)
    return Float32(0.0)


# ── Insertion-sort scratch slot (all primitive fields — no copy issues) ────────

struct _Slot(Copyable, Movable):
    var column_id:  UInt32
    var score:      Float32
    var name_sim:   Float32
    var type_boost: Float32

    def __init__(out self):
        self.column_id  = 0
        self.score      = Float32(0.0)
        self.name_sim   = Float32(0.0)
        self.type_boost = Float32(0.0)

    def __copyinit__(out self, copy: Self):
        self.column_id  = copy.column_id
        self.score      = copy.score
        self.name_sim   = copy.name_sim
        self.type_boost = copy.type_boost

    def __moveinit__(out self, var take: Self):
        self.column_id  = take.column_id
        self.score      = take.score
        self.name_sim   = take.name_sim
        self.type_boost = take.type_boost


def _insert_sort_slots(mut slots: List[_Slot]):
    var n = len(slots)
    for i in range(1, n):
        var ks  = slots[i].score
        var kid = slots[i].column_id
        var kns = slots[i].name_sim
        var ktb = slots[i].type_boost
        var j = i - 1
        while j >= 0 and slots[j].score < ks:
            var tmp = _Slot()
            tmp.column_id  = slots[j].column_id
            tmp.score      = slots[j].score
            tmp.name_sim   = slots[j].name_sim
            tmp.type_boost = slots[j].type_boost
            slots[j + 1] = tmp^
            j -= 1
        var ins = _Slot()
        ins.column_id  = kid
        ins.score      = ks
        ins.name_sim   = kns
        ins.type_boost = ktb
        slots[j + 1] = ins^


# ── TopKEntry: all primitives — no copy issues ────────────────────────────────

struct TopKEntry(Copyable, Movable):
    var column_id:  UInt32
    var score:      Float32
    var name_sim:   Float32
    var type_boost: Float32

    def __init__(out self):
        self.column_id  = 0
        self.score      = Float32(0.0)
        self.name_sim   = Float32(0.0)
        self.type_boost = Float32(0.0)

    def __copyinit__(out self, copy: Self):
        self.column_id  = copy.column_id
        self.score      = copy.score
        self.name_sim   = copy.name_sim
        self.type_boost = copy.type_boost

    def __moveinit__(out self, var take: Self):
        self.column_id  = take.column_id
        self.score      = take.score
        self.name_sim   = take.name_sim
        self.type_boost = take.type_boost


# ── RankResult: entries is a List → use .copy() in __moveinit__ ──────────────

struct RankResult(Copyable, Movable):
    var count:          UInt8
    var ambiguous:      Bool
    var confidence_gap: Float32
    var entries:        List[TopKEntry]

    def __init__(out self):
        self.count          = 0
        self.ambiguous      = False
        self.confidence_gap = Float32(0.0)
        self.entries        = List[TopKEntry](capacity=RANK_TOP_K)
        for _ in range(RANK_TOP_K):
            self.entries.append(TopKEntry())

    def __copyinit__(out self, copy: Self):
        self.count          = copy.count
        self.ambiguous      = copy.ambiguous
        self.confidence_gap = copy.confidence_gap
        self.entries        = copy.entries.copy()   # explicit

    def __moveinit__(out self, var take: Self):
        self.count          = take.count
        self.ambiguous      = take.ambiguous
        self.confidence_gap = take.confidence_gap
        self.entries        = take.entries.copy()   # can't ^ with other fields alive


# ── RankRequest: query_vec is _Vec64 → use .copy() in __moveinit__ ───────────

struct RankRequest(Copyable, Movable):
    var source_id:      UInt16
    var role_id:        UInt8
    var top_k:          UInt8
    var query_norm_inv: Float32
    var query_vec:      _Vec64

    def __init__(out self):
        self.source_id      = SOURCE_UNKNOWN
        self.role_id        = ROLE_OTHER
        self.top_k          = 5
        self.query_norm_inv = Float32(0.0)
        self.query_vec      = _Vec64()

    def __copyinit__(out self, copy: Self):
        self.source_id      = copy.source_id
        self.role_id        = copy.role_id
        self.top_k          = copy.top_k
        self.query_norm_inv = copy.query_norm_inv
        self.query_vec      = copy.query_vec.copy()  # explicit

    def __moveinit__(out self, var take: Self):
        self.source_id      = take.source_id
        self.role_id        = take.role_id
        self.top_k          = take.top_k
        self.query_norm_inv = take.query_norm_inv
        self.query_vec      = take.query_vec.copy()  # can't ^ with other fields alive


# ── CandidateEntry: vec is _Vec64 → use .copy() in __moveinit__ ──────────────

struct CandidateEntry(Copyable, Movable):
    var column_id: UInt32
    var source_id: UInt16
    var role_id:   UInt8
    var norm_inv:  Float32
    var vec:       _Vec64

    def __init__(out self):
        self.column_id = 0
        self.source_id = SOURCE_UNKNOWN
        self.role_id   = ROLE_OTHER
        self.norm_inv  = Float32(0.0)
        self.vec       = _Vec64()

    def __copyinit__(out self, copy: Self):
        self.column_id = copy.column_id
        self.source_id = copy.source_id
        self.role_id   = copy.role_id
        self.norm_inv  = copy.norm_inv
        self.vec       = copy.vec.copy()   # explicit

    def __moveinit__(out self, var take: Self):
        self.column_id = take.column_id
        self.source_id = take.source_id
        self.role_id   = take.role_id
        self.norm_inv  = take.norm_inv
        self.vec       = take.vec.copy()   # can't ^ with other fields alive


# ── CandidateTable: single-field struct → __moveinit__ can use ^ ─────────────

struct CandidateTable(Movable):
    var entries: List[CandidateEntry]

    def __init__(out self):
        self.entries = List[CandidateEntry]()

    def __moveinit__(out self, var take: Self):
        self.entries = take.entries.copy()   # ^ on fields not allowed; use copy

    def add_column(
        mut self,
        column_id: UInt32,
        source_id: UInt16,
        role_id:   UInt8,
        name:      String,
    ):
        var entry = CandidateEntry()
        entry.column_id = column_id
        entry.source_id = source_id
        entry.role_id   = role_id
        entry.norm_inv  = _build_vec_inplace(name, entry.vec.data)
        self.entries.append(entry^)

    def size(self) -> Int:
        return len(self.entries)

    def rank(self, req: RankRequest) -> RankResult:
        """
        Hot path: zero JSON, zero strings.
        Lists are passed as borrows to _cosine — no intermediate var, no copy.
        """
        var n_cands = len(self.entries)
        var top_k   = Int(req.top_k) if Int(req.top_k) <= RANK_TOP_K else RANK_TOP_K
        var slots   = List[_Slot]()

        for i in range(n_cands):
            var c_id  = self.entries[i].column_id
            var c_src = self.entries[i].source_id
            var c_rol = self.entries[i].role_id
            var c_ni  = self.entries[i].norm_inv

            # Pass data lists as borrows — no intermediate var, no copy
            var nsim = _cosine(
                req.query_vec.data,
                self.entries[i].vec.data,
                req.query_norm_inv,
                c_ni,
            )
            var tb = _type_boost_ids(req.role_id, c_rol)
            var pb = _prior_boost_ids(req.source_id, c_src, c_rol)

            var fs = W_NAME * nsim + tb + pb
            if fs > 1.0: fs = Float32(1.0)
            elif fs < 0.0: fs = Float32(0.0)

            var slot = _Slot()
            slot.column_id  = c_id
            slot.score      = fs
            slot.name_sim   = nsim
            slot.type_boost = tb + pb
            slots.append(slot^)

        if len(slots) == 0:
            return RankResult()

        _insert_sort_slots(slots)

        var result = RankResult()
        var out_n  = len(slots) if len(slots) < top_k else top_k
        result.count = UInt8(out_n)

        var gap = Float32(0.0)
        if len(slots) >= 2:
            gap = slots[0].score - slots[1].score
        result.confidence_gap = gap
        result.ambiguous = gap < AMBIG_GAP and len(slots) >= 2

        for i in range(out_n):
            result.entries[i].column_id  = slots[i].column_id
            result.entries[i].score      = slots[i].score
            result.entries[i].name_sim   = slots[i].name_sim
            result.entries[i].type_boost = slots[i].type_boost

        return result^


def build_query(name: String, source_id: UInt16, role_id: UInt8, top_k: UInt8) -> RankRequest:
    var req = RankRequest()
    req.source_id      = source_id
    req.role_id        = role_id
    req.top_k          = top_k
    req.query_norm_inv = _build_vec_inplace(name, req.query_vec.data)
    return req^


# ── Helpers ───────────────────────────────────────────────────────────────────

def check(label: String, ok: Bool):
    if ok:
        print("[PASS]", label)
    else:
        print("[FAIL]", label)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    # Build resident table: 10 representative columns
    var table = CandidateTable()
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

    # Query 1: "unit_price" POS UNIT → id=1 should win
    var req = build_query("unit_price", SOURCE_POS, ROLE_UNIT, 5)
    var res = table.rank(req)

    check("count = 5",         Int(res.count) == 5)
    check("top result = 1",    res.entries[0].column_id == 1)
    check("top score > 0.5",   res.entries[0].score > 0.5)
    check("not ambiguous",     not res.ambiguous)

    print("  top-3 for 'unit_price' (POS, UNIT):")
    for i in range(3):
        print("   #" + String(i+1)
              + " id="    + String(res.entries[i].column_id)
              + "  score=" + String(res.entries[i].score)
              + "  sim="   + String(res.entries[i].name_sim)
              + "  boost=" + String(res.entries[i].type_boost))
    print("  confidence_gap =", res.confidence_gap)

    # Query 2: "extended_price" POS DERIVED → id=2
    var req2 = build_query("extended_price", SOURCE_POS, ROLE_DERIVED, 5)
    var res2 = table.rank(req2)
    check("extended_price top = 2", res2.entries[0].column_id == 2)

    # Query 3: short query — should still return results
    var req3 = build_query("unit", SOURCE_POS, ROLE_UNIT, 8)
    var res3 = table.rank(req3)
    check("short query returns results", Int(res3.count) > 0)

    # ── Benchmark ──────────────────────────────────────────────────────────────
    print("")
    var N: Int = 10000

    # Hot path only (pre-built query)
    var t0 = perf_counter_ns()
    for _ in range(N):
        var r = table.rank(req)
        _ = r.count
    var t1 = perf_counter_ns()
    var rank_ns = Float64(t1 - t0) / Float64(N)
    print("[BENCH] table.rank()         10 cands,", N, "iters:", rank_ns, "ns/call")

    # Full typed path (encode query + rank)
    var t2 = perf_counter_ns()
    for _ in range(N):
        var rq = build_query("unit_price", SOURCE_POS, ROLE_UNIT, 5)
        var rr = table.rank(rq)
        _ = rr.count
    var t3 = perf_counter_ns()
    var full_ns = Float64(t3 - t2) / Float64(N)
    print("[BENCH] build_query + rank() 10 cands,", N, "iters:", full_ns, "ns/call")

    print("")
    print("  [ref] JSON pipeline (run_column_rank_v2): ~9302 ns/call")
    print("  [ref] pure SIMD kernel (no JSON):         ~2849 ns/call")
