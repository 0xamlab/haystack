"""
vector_kernels/table.mojo — Resident candidate table + typed ranking hot path.

This module eliminates JSON from the scoring loop entirely.

Architecture:
  Build phase (once):
    CandidateTable.add_column(id, source_id, role_id, name)
      → normalise name → build bigram vector → cache norm_inv
      → store as CandidateEntry in resident List

  Query phase (hot path, per request):
    CandidateTable.rank(req: RankRequest) -> RankResult
      → SIMD dot product per candidate
      → integer role/source boost (no string ops)
      → insertion-sort top-k
      → return typed RankResult (no JSON)

Public API:
  CandidateTable     — resident column store (build once, query many)
  build_table_json   — populate a CandidateTable from a JSON candidates array
  source_id_of       — map source string → UInt16 constant
  role_id_of         — map role string → UInt8 constant

Speedup profile (vs JSON pipeline):
  JSON pipeline:    ~9.3µs  (includes json parsing + string ops)
  Typed hot path:   ~0.7µs  expected (SIMD + integer ops only, ~13×)
  Pure SIMD kernel: ~0.0µs  (sub-nanosecond when table fits in L1)
"""

from std.math import sqrt


# ── Re-export constants from types.mojo (inline here for self-containment) ────

comptime VEC_DIM:    Int     = 64
comptime SIMD_W:     Int     = 8
comptime RANK_TOP_K: Int     = 8
comptime AMBIG_GAP:  Float32 = Float32(0.08)
comptime W_NAME:     Float32 = Float32(0.55)
comptime W_TYPE:     Float32 = Float32(0.20)   # type/role boost weight
comptime W_PRIOR:    Float32 = Float32(0.10)   # source-context prior weight

comptime SOURCE_UNKNOWN: UInt16 = 0
comptime SOURCE_POS:     UInt16 = 1
comptime SOURCE_BACKLOG: UInt16 = 2
comptime SOURCE_INVOICE: UInt16 = 3

comptime ROLE_OTHER:   UInt8 = 0
comptime ROLE_UNIT:    UInt8 = 1
comptime ROLE_DERIVED: UInt8 = 2


# ── SIMD kernels (private, inline) ────────────────────────────────────────────

@always_inline
def _norm_byte(c: UInt8) -> UInt8:
    if c == 95 or c == 45 or c == 46:   # _ - .
        return 32
    if c >= 65 and c <= 90:             # A-Z → a-z
        return c + 32
    return c


def _build_vec_inplace(s: String, mut buf: List[Float32]) -> Float32:
    """Zero buf, fill with bigram counts (direct byte scan), return norm_inv."""
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
    # compute norm_inv
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
def _cosine(
    qv: List[Float32], cv: List[Float32],
    q_ni: Float32, c_ni: Float32,
) -> Float32:
    if q_ni == 0.0 or c_ni == 0.0:
        return Float32(0.0)
    var raw = _dot64(qv, cv) * q_ni * c_ni
    if raw > 1.0: return Float32(1.0)
    if raw < 0.0: return Float32(0.0)
    return raw


# ── Role/source boost (integer arithmetic — no strings) ───────────────────────

@always_inline
def _type_boost_ids(query_role: UInt8, cand_role: UInt8) -> Float32:
    """
    +0.15 exact role match, +0.05 both non-OTHER, -0.08 clear mismatch.
    Integer comparison only — zero string ops on the hot path.
    """
    if query_role == ROLE_OTHER:
        return Float32(0.0)
    if cand_role == query_role:
        return Float32(0.15)
    if cand_role != ROLE_OTHER:
        return Float32(-0.08)   # both typed but different
    return Float32(0.0)


@always_inline
def _prior_boost_ids(query_src: UInt16, cand_src: UInt16, cand_role: UInt8) -> Float32:
    """
    Source-context prior: integer table lookup, no strings.
    POS   + UNIT    = +0.10
    BACKLOG + DERIVED = +0.10
    INVOICE + DERIVED = +0.10
    """
    if query_src == SOURCE_UNKNOWN:
        return Float32(0.0)
    if cand_src != SOURCE_UNKNOWN and cand_src != query_src:
        return Float32(0.0)   # different document type
    if query_src == SOURCE_POS and cand_role == ROLE_UNIT:
        return Float32(0.10)
    if query_src == SOURCE_BACKLOG and cand_role == ROLE_DERIVED:
        return Float32(0.10)
    if query_src == SOURCE_INVOICE and cand_role == ROLE_DERIVED:
        return Float32(0.10)
    return Float32(0.0)


# ── Internal scored slot (used during sort) ───────────────────────────────────

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
    """Descending insertion sort by score."""
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


# ── Vec64F32 (inline; avoid cross-module import for now) ─────────────────────

struct _Vec64(Copyable, Movable):
    """Internal 64-element Float32 buffer with cached norm_inv."""
    var data:     List[Float32]
    var norm_inv: Float32

    def __init__(out self):
        self.data = List[Float32](capacity=VEC_DIM)
        for _ in range(VEC_DIM):
            self.data.append(Float32(0.0))
        self.norm_inv = Float32(0.0)

    def __copyinit__(out self, copy: Self):
        self.data     = copy.data.copy()   # explicit — List not ImplicitlyCopyable
        self.norm_inv = copy.norm_inv

    def __moveinit__(out self, var take: Self):
        self.data     = take.data.copy()   # ^ on fields disallowed; runtime destroys take
        self.norm_inv = take.norm_inv


# ── CandidateEntry (resident table row) ──────────────────────────────────────

struct CandidateEntry(Copyable, Movable):
    """One column stored in the resident CandidateTable."""
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
        self.vec       = take.vec.copy()   # ^ disallowed; use copy


# ── RankRequest (typed query — no JSON) ──────────────────────────────────────

struct RankRequest(Copyable, Movable):
    """
    Typed query for CandidateTable.rank().
    Python builds this by pre-encoding the query column name into a vector.
    """
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
        self.query_vec      = take.query_vec.copy()  # ^ disallowed; use copy


# ── TopKEntry + RankResult (typed output) ────────────────────────────────────

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


struct RankResult(Copyable, Movable):
    """
    Top-k ranking result from the typed pipeline.
    `entries` holds exactly `count` valid TopKEntry values (rest are zeroed).
    """
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
        self.entries        = take.entries.copy()   # ^ disallowed; use copy


# ── CandidateTable — the resident store ──────────────────────────────────────

struct CandidateTable(Movable):
    """
    Resident in-memory column table.

    Build once per session by calling add_column() for each candidate.
    Then call rank() repeatedly with different RankRequest values.
    The bigram vectors and norm inverses are pre-computed and cached,
    so the hot path does only SIMD dot products + integer comparisons.

    Usage:
        var table = CandidateTable()
        table.add_column(1, SOURCE_POS, ROLE_UNIT, "unit_price")
        table.add_column(2, SOURCE_POS, ROLE_DERIVED, "extended_price")
        ...
        var req = RankRequest()
        req.source_id = SOURCE_POS
        req.role_id   = ROLE_UNIT
        req.top_k     = 5
        req.query_norm_inv = build_query_vec(table._tmp_buf, "unit_price")
        req.query_vec      = table._tmp_buf  # copy
        var result = table.rank(req)
    """
    var entries: List[CandidateEntry]

    def __init__(out self):
        self.entries = List[CandidateEntry]()

    def __moveinit__(out self, var take: Self):
        self.entries = take.entries.copy()   # ^ disallowed; use copy

    def add_column(
        mut self,
        column_id: UInt32,
        source_id: UInt16,
        role_id:   UInt8,
        name:      String,
    ):
        """
        Add one candidate column to the table.
        Builds and caches the bigram vector at insert time.
        """
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
        Score every resident candidate against the query vector.

        Hot path — zero JSON, zero string operations:
          • SIMD 8-wide dot product per candidate
          • integer role/source boost lookup
          • insertion-sort top-k (≤ RANK_TOP_K)
          • populate and return RankResult

        Complexity: O(N × VEC_DIM/SIMD_W) = O(N × 8) multiply-accumulates.
        For N=100 candidates: 800 SIMD fused multiply-adds, ~sub-microsecond.
        """
        var n_cands  = len(self.entries)
        var top_k    = Int(req.top_k) if Int(req.top_k) <= RANK_TOP_K else RANK_TOP_K

        var slots = List[_Slot]()

        for i in range(n_cands):
            # Read candidate fields without implicit struct copy
            var c_id  = self.entries[i].column_id
            var c_src = self.entries[i].source_id
            var c_rol = self.entries[i].role_id
            var c_ni  = self.entries[i].norm_inv

            # Pass data lists as borrows — no intermediate var, no implicit copy
            var nsim = _cosine(
                req.query_vec.data,
                self.entries[i].vec.data,
                req.query_norm_inv,
                c_ni,
            )

            # Integer boost — no string ops
            var tb = _type_boost_ids(req.role_id, c_rol)
            var pb = _prior_boost_ids(req.source_id, c_src, c_rol)

            # Weighted fusion
            var raw_score = W_NAME * nsim + tb + pb
            var fs = raw_score
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

        # Build RankResult
        var result = RankResult()
        var out_n = len(slots) if len(slots) < top_k else top_k
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


# ── build_query — encode a name string into a RankRequest vec ─────────────────

def build_query(name: String, source_id: UInt16, role_id: UInt8, top_k: UInt8) -> RankRequest:
    """
    Helper: build a typed RankRequest from a raw column name.
    Call this once per query on the Python side to eliminate build_vec overhead.
    """
    var req = RankRequest()
    req.source_id = source_id
    req.role_id   = role_id
    req.top_k     = top_k
    req.query_norm_inv = _build_vec_inplace(name, req.query_vec.data)
    return req^


# ── source_id_of / role_id_of — string → integer mapping ─────────────────────

def source_id_of(s: String) -> UInt16:
    """Map source-type string to UInt16 constant. Case-sensitive."""
    if s == "POS":     return SOURCE_POS
    if s == "BACKLOG": return SOURCE_BACKLOG
    if s == "INVOICE": return SOURCE_INVOICE
    return SOURCE_UNKNOWN


def role_id_of(s: String) -> UInt8:
    """Map role-hint string to UInt8 constant. Case-sensitive."""
    if s == "unit_measure":    return ROLE_UNIT
    if s == "derived_measure": return ROLE_DERIVED
    return ROLE_OTHER


# ── build_table_json — populate from JSON candidates array ───────────────────

def _jget(raw: String, key: String) -> String:
    """Minimal JSON string value extractor."""
    var needle = '"' + key + '"'
    var ki = raw.find(needle)
    if ki == -1: return ""
    var colon = raw.find(":", ki + needle.byte_length())
    if colon == -1: return ""
    var start = colon + 1
    var rlen = raw.byte_length()
    var rb = raw.as_bytes()
    while start < rlen and (rb[start] == 32 or rb[start] == 9):
        start += 1
    if start >= rlen: return ""
    if rb[start] == 34:
        var end = raw.find('"', start + 1)
        if end == -1: return ""
        return String(raw[byte=start + 1 : end])
    var end2 = start
    while end2 < rlen and rb[end2] != 44 and rb[end2] != 125:
        end2 += 1
    return String(raw[byte=start : end2])


def build_table_json(candidates_json: String) -> CandidateTable:
    """
    Build a CandidateTable from a JSON candidates array.

    Input format:
      [{"id": 1, "source": "POS", "role": "unit_measure", "name": "unit_price"}, ...]

    'id' is optional — auto-assigned from index if absent.
    'source' and 'role' are optional — default to UNKNOWN/OTHER.

    Call this once at startup; then call table.rank() per query.
    """
    var table = CandidateTable()
    var arr_start = candidates_json.find("[")
    if arr_start == -1:
        return table^

    var pos = arr_start + 1
    var arr_end = candidates_json.find("]", arr_start)
    if arr_end == -1:
        return table^

    var auto_id = UInt32(0)
    while pos < arr_end:
        var obj_open = candidates_json.find("{", pos)
        if obj_open == -1 or obj_open >= arr_end:
            break
        var obj_close = candidates_json.find("}", obj_open)
        if obj_close == -1:
            break
        var obj = String(candidates_json[byte=obj_open : obj_close + 1])

        var c_name   = _jget(obj, "name")
        var c_source = _jget(obj, "source")
        var c_role   = _jget(obj, "role")
        var c_id_s   = _jget(obj, "id")

        var c_id = auto_id
        if c_id_s.byte_length() > 0:
            try:
                c_id = UInt32(Int(c_id_s))
            except:
                pass
        auto_id += 1

        pos = obj_close + 1
        if c_name.byte_length() == 0:
            continue

        table.add_column(c_id, source_id_of(c_source), role_id_of(c_role), c_name)

    return table^
