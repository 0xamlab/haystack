"""
semantic_micro/semantic_types.mojo — Compile-time constants and POD structs
for the ultra-thin semantic model.

All structs use flat contiguous memory so artifacts can be memory-mapped
directly from the Python training export without any deserialization step.

Dimensions are compile-time constants, enabling the Mojo compiler to unroll
all inner loops in the embed / MLP / expansion kernels.

Binary artifact layout (produced by training/semantic/export_artifacts.py):
  embeddings.bin          float32 [vocab_size × EMB_DIM]
  intent_fc1_weight.bin   float32 [HIDDEN_DIM × EMB_DIM]
  intent_fc1_bias.bin     float32 [HIDDEN_DIM]
  intent_fc2_weight.bin   float32 [INTENT_CLASSES × HIDDEN_DIM]
  intent_fc2_bias.bin     float32 [INTENT_CLASSES]
  agg_fc{1,2}_{weight,bias}.bin  — same pattern, AGG_CLASSES outputs
  family_fc{1,2}_{weight,bias}.bin — same pattern, FAMILY_CLASSES outputs
  nn_ids.bin              uint32  [vocab_size × NN_K]
  nn_scores.bin           float32 [vocab_size × NN_K]
  meta.json               shape metadata + class label names
  vocab.json              token → id mapping
"""

# ── Compile-time dimensions ───────────────────────────────────────────────────

alias EMB_DIM:        Int = 32    # token embedding dimension
alias HIDDEN_DIM:     Int = 24    # MLP hidden layer width
alias NN_K:           Int = 8     # top-K nearest neighbors per token
alias SIMD_W:         Int = 8     # SIMD lane width (Float32 × 8 = 256-bit AVX)
alias EMB_CHUNKS:     Int = 4     # EMB_DIM / SIMD_W
alias HIDDEN_CHUNKS:  Int = 3     # HIDDEN_DIM / SIMD_W

# Classification head output sizes
alias INTENT_CLASSES:  Int = 4   # column_like | meta_query | weak_semantic | unsupported
alias AGG_CLASSES:     Int = 6   # none | count | sum | avg | min | max
alias FAMILY_CLASSES:  Int = 4   # measure | dimension | date | entity

# ── Confidence thresholds — below these the hint is silenced ─────────────────
# These are conservative by design: the deterministic resolver stays in charge.

alias INTENT_CONF_THRESHOLD:  Float32 = 0.70
alias AGG_CONF_THRESHOLD:     Float32 = 0.72
alias FAMILY_CONF_THRESHOLD:  Float32 = 0.68
alias EXPAND_MIN_SCORE:       Float32 = 0.82   # cosine floor for expansion

# ── Intent class IDs ──────────────────────────────────────────────────────────

alias INTENT_COLUMN_LIKE:   UInt8 = 0   # maps to a real column
alias INTENT_META_QUERY:    UInt8 = 1   # row-count / aggregation intent
alias INTENT_WEAK_SEMANTIC: UInt8 = 2   # ambiguous; needs resolver tie-break
alias INTENT_UNSUPPORTED:   UInt8 = 3   # unknown domain

# ── Aggregation class IDs ─────────────────────────────────────────────────────

alias AGG_NONE:  UInt8 = 0
alias AGG_COUNT: UInt8 = 1
alias AGG_SUM:   UInt8 = 2
alias AGG_AVG:   UInt8 = 3
alias AGG_MIN:   UInt8 = 4
alias AGG_MAX:   UInt8 = 5

# ── Semantic family class IDs ─────────────────────────────────────────────────

alias FAMILY_MEASURE:   UInt8 = 0   # numeric measure (revenue, qty, price)
alias FAMILY_DIMENSION: UInt8 = 1   # categorical grouping key
alias FAMILY_DATE:      UInt8 = 2   # temporal field
alias FAMILY_ENTITY:    UInt8 = 3   # row entity (customer, server, order)

# Sentinel: confidence below threshold → do not use this hint
alias HINT_NONE: UInt8 = 255


# ── EmbeddingTable ────────────────────────────────────────────────────────────

struct EmbeddingTable(Copyable, Movable):
    """
    Token embedding lookup.  Points into an externally-owned buffer.
    Memory layout: row-major [vocab_size × EMB_DIM] Float32.
    Token t starts at offset t * EMB_DIM.
    """
    var values:     UnsafePointer[Float32]
    var vocab_size: UInt32

    fn __init__(out self):
        self.values     = UnsafePointer[Float32]()
        self.vocab_size = 0

    fn __copyinit__(out self, copy: Self):
        self.values     = copy.values
        self.vocab_size = copy.vocab_size

    fn __moveinit__(out self, var take: Self):
        self.values     = take.values
        self.vocab_size = take.vocab_size


# ── LinearLayer ───────────────────────────────────────────────────────────────

struct LinearLayer(Copyable, Movable):
    """
    Single fully-connected layer.
    weight: row-major [out_dim × in_dim] Float32.
    bias:   [out_dim] Float32.
    """
    var weight:  UnsafePointer[Float32]
    var bias:    UnsafePointer[Float32]
    var in_dim:  UInt16
    var out_dim: UInt16

    fn __init__(out self):
        self.weight  = UnsafePointer[Float32]()
        self.bias    = UnsafePointer[Float32]()
        self.in_dim  = 0
        self.out_dim = 0

    fn __copyinit__(out self, copy: Self):
        self.weight  = copy.weight
        self.bias    = copy.bias
        self.in_dim  = copy.in_dim
        self.out_dim = copy.out_dim

    fn __moveinit__(out self, var take: Self):
        self.weight  = take.weight
        self.bias    = take.bias
        self.in_dim  = take.in_dim
        self.out_dim = take.out_dim


# ── SemanticModel ─────────────────────────────────────────────────────────────

struct SemanticModel(Movable):
    """
    Fully-loaded thin semantic model.  All pointer fields are views into
    externally-owned buffers (loaded by semantic_loader.mojo).

    Three 2-layer MLP heads share the same embedding table:
      intent head  → INTENT_CLASSES  outputs  (route: column / meta / weak / unsupported)
      agg head     → AGG_CLASSES     outputs  (aggregation: none/count/sum/avg/min/max)
      family head  → FAMILY_CLASSES  outputs  (measure / dimension / date / entity)

    Nearest-neighbor table enables token expansion without ANN search:
      nn_token_ids[tok * NN_K + k]  = k-th neighbor token id
      nn_scores   [tok * NN_K + k]  = cosine similarity (pre-normalized)
    """
    var embeddings:   EmbeddingTable

    var intent_fc1:   LinearLayer          # EMB_DIM  → HIDDEN_DIM
    var intent_fc2:   LinearLayer          # HIDDEN_DIM → INTENT_CLASSES

    var agg_fc1:      LinearLayer          # EMB_DIM  → HIDDEN_DIM
    var agg_fc2:      LinearLayer          # HIDDEN_DIM → AGG_CLASSES

    var family_fc1:   LinearLayer          # EMB_DIM  → HIDDEN_DIM
    var family_fc2:   LinearLayer          # HIDDEN_DIM → FAMILY_CLASSES

    var nn_token_ids: UnsafePointer[UInt32]   # [vocab_size × NN_K]
    var nn_scores:    UnsafePointer[Float32]  # [vocab_size × NN_K]

    fn __init__(out self):
        self.embeddings   = EmbeddingTable()
        self.intent_fc1   = LinearLayer()
        self.intent_fc2   = LinearLayer()
        self.agg_fc1      = LinearLayer()
        self.agg_fc2      = LinearLayer()
        self.family_fc1   = LinearLayer()
        self.family_fc2   = LinearLayer()
        self.nn_token_ids = UnsafePointer[UInt32]()
        self.nn_scores    = UnsafePointer[Float32]()

    fn __moveinit__(out self, var take: Self):
        self.embeddings   = take.embeddings
        self.intent_fc1   = take.intent_fc1
        self.intent_fc2   = take.intent_fc2
        self.agg_fc1      = take.agg_fc1
        self.agg_fc2      = take.agg_fc2
        self.family_fc1   = take.family_fc1
        self.family_fc2   = take.family_fc2
        self.nn_token_ids = take.nn_token_ids
        self.nn_scores    = take.nn_scores


# ── SemanticQuery ─────────────────────────────────────────────────────────────

struct SemanticQuery(Copyable, Movable):
    """
    Input to the semantic layer.  Token IDs must already be resolved against
    the model's vocab (unknown tokens mapped to UInt32.MAX → skipped in embed).
    """
    var token_ids:   UnsafePointer[UInt32]
    var token_count: UInt16
    var source_id:   UInt16   # resolver SOURCE_* constant (hint, not binding)
    var role_id:     UInt8    # resolver ROLE_* constant

    fn __init__(out self):
        self.token_ids   = UnsafePointer[UInt32]()
        self.token_count = 0
        self.source_id   = 0
        self.role_id     = 0

    fn __copyinit__(out self, copy: Self):
        self.token_ids   = copy.token_ids
        self.token_count = copy.token_count
        self.source_id   = copy.source_id
        self.role_id     = copy.role_id

    fn __moveinit__(out self, var take: Self):
        self.token_ids   = take.token_ids
        self.token_count = take.token_count
        self.source_id   = take.source_id
        self.role_id     = take.role_id


# ── SemanticHints ─────────────────────────────────────────────────────────────

struct SemanticHints(Copyable, Movable):
    """
    Output from infer_semantic_hints().

    Fields set to HINT_NONE (255) when confidence is below the relevant
    threshold — the resolver/planner MUST check has_*() before using a hint.

    The semantic layer is a feature generator, not a decision maker:
      ✓ Use hints to augment token expansion or apply soft priors.
      ✗ Never let hints override resolver outcome or gap checks.
    """
    var intent_class: UInt8
    var intent_conf:  Float32
    var agg_class:    UInt8
    var agg_conf:     Float32
    var family_class: UInt8
    var family_conf:  Float32

    fn __init__(out self):
        self.intent_class = HINT_NONE
        self.intent_conf  = Float32(0.0)
        self.agg_class    = HINT_NONE
        self.agg_conf     = Float32(0.0)
        self.family_class = HINT_NONE
        self.family_conf  = Float32(0.0)

    fn __copyinit__(out self, copy: Self):
        self.intent_class = copy.intent_class
        self.intent_conf  = copy.intent_conf
        self.agg_class    = copy.agg_class
        self.agg_conf     = copy.agg_conf
        self.family_class = copy.family_class
        self.family_conf  = copy.family_conf

    fn __moveinit__(out self, var take: Self):
        self.intent_class = take.intent_class
        self.intent_conf  = take.intent_conf
        self.agg_class    = take.agg_class
        self.agg_conf     = take.agg_conf
        self.family_class = take.family_class
        self.family_conf  = take.family_conf

    @always_inline
    fn has_intent(self) -> Bool:
        return self.intent_class != HINT_NONE

    @always_inline
    fn has_agg(self) -> Bool:
        return self.agg_class != HINT_NONE

    @always_inline
    fn has_family(self) -> Bool:
        return self.family_class != HINT_NONE
