"""
vector_kernels/types.mojo — Shared value types for the SIMD column ranker.

Two distinct layers:

  LAYER 1 — internal working types (use List[Float32], mutable)
    Vec64F32       — owned 64-element bigram vector + cached norm_inv
    QueryFeatures  — query column with vector + role/source context
    CandidateScore — one ranked result (from JSON pipeline)

  LAYER 2 — ABI-stable types for the typed/resident pipeline
    SourceId / RoleId  — integer constants (no enums for FFI stability)
    TopKEntry          — single result: 16 bytes, C-compatible layout
    RankResult         — top-k results, fixed 8 slots: ~136 bytes total
    RankRequest        — typed query: source_id, role_id, pre-built vec
    CandidateEntry     — one packed resident table row

Python FFI note (ctypes layout for the Layer 2 types):

    class TopKEntry(ctypes.Structure):
        _fields_ = [("column_id", c_uint32),
                    ("score",     c_float),
                    ("name_sim",  c_float),
                    ("type_boost", c_float)]   # 16 bytes

    class RankResult(ctypes.Structure):
        _fields_ = [("count",          c_uint8),
                    ("ambiguous",      c_uint8),
                    ("_pad",           c_uint8 * 2),
                    ("confidence_gap", c_float),
                    ("entries",        TopKEntry * 8)]   # 8 + 128 = 136 bytes

Mojo 0.26 notes:
  - __copyinit__ param named 'copy', __moveinit__ param named 'take' (var)
  - In __moveinit__ assign fields by copy (no field^ from var param)
  - List[T] not ImplicitlyCopyable — use explicit copy or move
"""

# ── Compile-time dimension constants ─────────────────────────────────────────

comptime VEC_DIM:    Int = 64
comptime RANK_TOP_K: Int = 8   # max entries in RankResult


# ── Layer 2: SourceId / RoleId integer constants ──────────────────────────────
#
# Using comptime Int rather than an enum so Python ctypes/cffi can directly
# map uint16/uint8 fields without needing to know the Mojo enum ABI.

comptime SOURCE_UNKNOWN: UInt16 = 0
comptime SOURCE_POS:     UInt16 = 1
comptime SOURCE_BACKLOG: UInt16 = 2
comptime SOURCE_INVOICE: UInt16 = 3

comptime ROLE_OTHER:   UInt8 = 0
comptime ROLE_UNIT:    UInt8 = 1   # unit_measure: unit price, unit cost
comptime ROLE_DERIVED: UInt8 = 2   # derived_measure: ext price, total


# ── Layer 1: Vec64F32 (mutable working type) ──────────────────────────────────

struct Vec64F32(Copyable, Movable):
    """
    64-element Float32 bigram vector with pre-computed L2-norm inverse.

    Build with build_vec64_f32() from dot.mojo. Store norm_inv alongside so
    cosine calls are always O(1) after construction.
    """
    var data:     List[Float32]
    var norm_inv: Float32

    fn __init__(out self):
        self.data = List[Float32](capacity=VEC_DIM)
        for _ in range(VEC_DIM):
            self.data.append(Float32(0.0))
        self.norm_inv = Float32(0.0)

    fn __copyinit__(out self, copy: Self):
        self.data     = copy.data.copy()   # explicit — List not ImplicitlyCopyable
        self.norm_inv = copy.norm_inv

    fn __moveinit__(out self, var take: Self):
        self.data     = take.data.copy()   # ^ on fields disallowed; runtime destroys take
        self.norm_inv = take.norm_inv


# ── Layer 1: QueryFeatures ────────────────────────────────────────────────────

struct QueryFeatures(Copyable, Movable):
    """
    Encoded query column for one JSON-pipeline matching pass.
    See ranker.mojo for usage.
    """
    var name:      String
    var vec:       Vec64F32
    var role_hint: String
    var source:    String

    fn __init__(out self):
        self.name      = ""
        self.vec       = Vec64F32()
        self.role_hint = ""
        self.source    = ""

    fn __copyinit__(out self, copy: Self):
        self.name      = copy.name
        self.vec       = copy.vec.copy()   # explicit — Vec64F32 contains List
        self.role_hint = copy.role_hint
        self.source    = copy.source

    fn __moveinit__(out self, var take: Self):
        self.name      = take.name
        self.vec       = take.vec.copy()   # ^ disallowed; use copy
        self.role_hint = take.role_hint
        self.source    = take.source


# ── Layer 1: CandidateScore (JSON pipeline result) ────────────────────────────

struct CandidateScore(Copyable, Movable):
    """
    Scored result for one candidate column (JSON pipeline).
    score = 0.55*name_sim + 0.25*token_sim + type_boost + prior_boost
    """
    var source:      String
    var column:      String
    var score:       Float32
    var name_sim:    Float32
    var token_sim:   Float32
    var type_boost:  Float32
    var prior_boost: Float32

    fn __init__(out self):
        self.source      = ""
        self.column      = ""
        self.score       = Float32(0.0)
        self.name_sim    = Float32(0.0)
        self.token_sim   = Float32(0.0)
        self.type_boost  = Float32(0.0)
        self.prior_boost = Float32(0.0)

    fn __copyinit__(out self, copy: Self):
        self.source      = copy.source
        self.column      = copy.column
        self.score       = copy.score
        self.name_sim    = copy.name_sim
        self.token_sim   = copy.token_sim
        self.type_boost  = copy.type_boost
        self.prior_boost = copy.prior_boost

    fn __moveinit__(out self, var take: Self):
        self.source      = take.source
        self.column      = take.column
        self.score       = take.score
        self.name_sim    = take.name_sim
        self.token_sim   = take.token_sim
        self.type_boost  = take.type_boost
        self.prior_boost = take.prior_boost


# ── Layer 2: TopKEntry — one ranked result (16 bytes, C-compatible) ───────────

@fieldwise_init
struct TopKEntry(Copyable, Movable):
    """
    Single ranked result from the typed pipeline.

    C layout (ctypes):
        ("column_id",  c_uint32)   # 4  — opaque column identifier
        ("score",      c_float)    # 4  — final weighted score [0, 1]
        ("name_sim",   c_float)    # 4  — cosine similarity component
        ("type_boost", c_float)    # 4  — role + prior boost applied
        # total: 16 bytes
    """
    var column_id:  UInt32
    var score:      Float32
    var name_sim:   Float32
    var type_boost: Float32

    fn __init__(out self):
        self.column_id  = 0
        self.score      = Float32(0.0)
        self.name_sim   = Float32(0.0)
        self.type_boost = Float32(0.0)

    fn __copyinit__(out self, copy: Self):
        self.column_id  = copy.column_id
        self.score      = copy.score
        self.name_sim   = copy.name_sim
        self.type_boost = copy.type_boost

    fn __moveinit__(out self, var take: Self):
        self.column_id  = take.column_id
        self.score      = take.score
        self.name_sim   = take.name_sim
        self.type_boost = take.type_boost


# ── Layer 2: RankResult — top-k results + ambiguity (136 bytes) ───────────────

struct RankResult(Copyable, Movable):
    """
    Top-k ranking result from the typed pipeline.

    Holds up to RANK_TOP_K (8) entries. `count` is the number of valid
    entries populated; slots above `count` are zeroed.

    C layout (ctypes):
        ("count",          c_uint8)       # 1  — valid entry count
        ("ambiguous",      c_uint8)       # 1  — 1 if confidence_gap < 0.08
        ("_pad",           c_uint8 * 2)   # 2  — alignment
        ("confidence_gap", c_float)       # 4  — score[0] - score[1]
        ("entries",        TopKEntry * 8) # 128 — 8 × 16-byte TopKEntry
        # total: 136 bytes
    """
    var count:          UInt8
    var ambiguous:      Bool
    var confidence_gap: Float32
    var entries:        List[TopKEntry]   # always exactly RANK_TOP_K slots

    fn __init__(out self):
        self.count          = 0
        self.ambiguous      = False
        self.confidence_gap = Float32(0.0)
        self.entries        = List[TopKEntry](capacity=RANK_TOP_K)
        for _ in range(RANK_TOP_K):
            self.entries.append(TopKEntry())

    fn __copyinit__(out self, copy: Self):
        self.count          = copy.count
        self.ambiguous      = copy.ambiguous
        self.confidence_gap = copy.confidence_gap
        self.entries        = copy.entries.copy()   # explicit

    fn __moveinit__(out self, var take: Self):
        self.count          = take.count
        self.ambiguous      = take.ambiguous
        self.confidence_gap = take.confidence_gap
        self.entries        = take.entries.copy()   # ^ disallowed; use copy


# ── Layer 2: RankRequest — typed query (no JSON) ──────────────────────────────

struct RankRequest(Copyable, Movable):
    """
    Typed query for the resident-table ranking pipeline.

    Python constructs this by:
      1. normalising the query column name
      2. calling build_vec64_f32() to fill query_vec + query_norm_inv
      3. mapping source/role strings to integer IDs
      4. passing to CandidateTable.rank()

    This eliminates JSON serialisation entirely from the hot path.
    """
    var source_id:      UInt16
    var role_id:        UInt8
    var top_k:          UInt8      # how many results to return (≤ RANK_TOP_K)
    var query_norm_inv: Float32
    var query_vec:      Vec64F32

    fn __init__(out self):
        self.source_id      = SOURCE_UNKNOWN
        self.role_id        = ROLE_OTHER
        self.top_k          = 5
        self.query_norm_inv = Float32(0.0)
        self.query_vec      = Vec64F32()

    fn __copyinit__(out self, copy: Self):
        self.source_id      = copy.source_id
        self.role_id        = copy.role_id
        self.top_k          = copy.top_k
        self.query_norm_inv = copy.query_norm_inv
        self.query_vec      = copy.query_vec.copy()  # explicit

    fn __moveinit__(out self, var take: Self):
        self.source_id      = take.source_id
        self.role_id        = take.role_id
        self.top_k          = take.top_k
        self.query_norm_inv = take.query_norm_inv
        self.query_vec      = take.query_vec.copy()  # ^ disallowed; use copy


# ── Layer 2: CandidateEntry — one packed resident table row ──────────────────

struct CandidateEntry(Copyable, Movable):
    """
    One candidate column stored in a CandidateTable.

    The bigram vector and norm_inv are pre-computed at table-build time,
    so the ranking hot path does only SIMD dot products + integer comparisons.

    Memory layout per entry (approx):
        column_id   4 bytes (UInt32)
        source_id   2 bytes (UInt16)
        role_id     1 byte  (UInt8)
        _pad        1 byte
        norm_inv    4 bytes (Float32)
        vec.data   64 × 4 = 256 bytes (List[Float32] heap)
        ≈ 268 bytes per entry (plus List overhead)
    """
    var column_id: UInt32
    var source_id: UInt16
    var role_id:   UInt8
    var norm_inv:  Float32
    var vec:       Vec64F32

    fn __init__(out self):
        self.column_id = 0
        self.source_id = SOURCE_UNKNOWN
        self.role_id   = ROLE_OTHER
        self.norm_inv  = Float32(0.0)
        self.vec       = Vec64F32()

    fn __copyinit__(out self, copy: Self):
        self.column_id = copy.column_id
        self.source_id = copy.source_id
        self.role_id   = copy.role_id
        self.norm_inv  = copy.norm_inv
        self.vec       = copy.vec.copy()   # explicit

    fn __moveinit__(out self, var take: Self):
        self.column_id = take.column_id
        self.source_id = take.source_id
        self.role_id   = take.role_id
        self.norm_inv  = take.norm_inv
        self.vec       = take.vec.copy()   # ^ disallowed; use copy
