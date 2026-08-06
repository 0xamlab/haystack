"""
semantic_micro/semantic_loader.mojo — Buffer-based factory for SemanticModel.

Python loads the flat-binary artifacts, allocates aligned buffers, fills them,
and calls from_buffers() via FFI.  The Mojo side does zero I/O; all it does is
bind pointer fields inside SemanticModel.

Binary format contract (produced by training/semantic/export_artifacts.py):
  embeddings:         float32 [vocab_size × EMB_DIM]           row-major
  intent_fc1_weight:  float32 [HIDDEN_DIM × EMB_DIM]           row-major
  intent_fc1_bias:    float32 [HIDDEN_DIM]
  intent_fc2_weight:  float32 [INTENT_CLASSES × HIDDEN_DIM]    row-major
  intent_fc2_bias:    float32 [INTENT_CLASSES]
  agg_fc{1,2}_{weight,bias}  — same pattern, AGG_CLASSES outputs
  family_fc{1,2}_{weight,bias} — same pattern, FAMILY_CLASSES outputs
  nn_ids:             uint32  [vocab_size × NN_K]
  nn_scores:          float32 [vocab_size × NN_K]

All buffers must stay alive for the lifetime of the returned SemanticModel.
"""

from mojo.engine.vector_kernels.semantic_micro.semantic_types import (
    SemanticModel, EmbeddingTable, LinearLayer,
    EMB_DIM, HIDDEN_DIM,
    INTENT_CLASSES, AGG_CLASSES, FAMILY_CLASSES,
)


def _make_linear(
    weight_ptr: UnsafePointer[Float32],
    bias_ptr:   UnsafePointer[Float32],
    in_d:       Int,
    out_d:      Int,
) -> LinearLayer:
    var l = LinearLayer()
    l.weight  = weight_ptr
    l.bias    = bias_ptr
    l.in_dim  = UInt16(in_d)
    l.out_dim = UInt16(out_d)
    return l


def from_buffers(
    # Embeddings
    emb_ptr:    UnsafePointer[Float32],
    vocab_size: UInt32,

    # Intent head
    intent_fc1_w: UnsafePointer[Float32],
    intent_fc1_b: UnsafePointer[Float32],
    intent_fc2_w: UnsafePointer[Float32],
    intent_fc2_b: UnsafePointer[Float32],

    # Aggregation head
    agg_fc1_w: UnsafePointer[Float32],
    agg_fc1_b: UnsafePointer[Float32],
    agg_fc2_w: UnsafePointer[Float32],
    agg_fc2_b: UnsafePointer[Float32],

    # Family head
    family_fc1_w: UnsafePointer[Float32],
    family_fc1_b: UnsafePointer[Float32],
    family_fc2_w: UnsafePointer[Float32],
    family_fc2_b: UnsafePointer[Float32],

    # Nearest-neighbor table
    nn_ids_ptr:    UnsafePointer[UInt32],
    nn_scores_ptr: UnsafePointer[Float32],
) -> SemanticModel:
    """
    Bind all pre-loaded buffers into a SemanticModel.

    Called once at startup after Python reads the artifact files.
    Returns a fully-configured model ready for infer_semantic_hints()
    and semantic_expand_query().
    """
    var m = SemanticModel()

    # Embeddings
    m.embeddings.values     = emb_ptr
    m.embeddings.vocab_size = vocab_size

    # Intent head (EMB_DIM → HIDDEN_DIM → INTENT_CLASSES)
    m.intent_fc1 = _make_linear(intent_fc1_w, intent_fc1_b, EMB_DIM, HIDDEN_DIM)
    m.intent_fc2 = _make_linear(intent_fc2_w, intent_fc2_b, HIDDEN_DIM, INTENT_CLASSES)

    # Aggregation head (EMB_DIM → HIDDEN_DIM → AGG_CLASSES)
    m.agg_fc1 = _make_linear(agg_fc1_w, agg_fc1_b, EMB_DIM, HIDDEN_DIM)
    m.agg_fc2 = _make_linear(agg_fc2_w, agg_fc2_b, HIDDEN_DIM, AGG_CLASSES)

    # Family head (EMB_DIM → HIDDEN_DIM → FAMILY_CLASSES)
    m.family_fc1 = _make_linear(family_fc1_w, family_fc1_b, EMB_DIM, HIDDEN_DIM)
    m.family_fc2 = _make_linear(family_fc2_w, family_fc2_b, HIDDEN_DIM, FAMILY_CLASSES)

    # Nearest-neighbor expansion table
    m.nn_token_ids = nn_ids_ptr
    m.nn_scores    = nn_scores_ptr

    return m
