"""
semantic_micro/semantic_api.mojo — Top-level entry points for the semantic layer.

Two public functions:

  infer_semantic_hints()
      Query vector → run all three heads → return SemanticHints
      Hints are gated by confidence thresholds; low-confidence heads emit HINT_NONE.
      Total latency: ~1–3 µs (embed 32-dim + 3× tiny MLP)

  semantic_expand_query()
      Token IDs → neighbor lookup → return expanded token IDs + scores
      O(T × NN_K) where T = token_count, NN_K = 8
      Latency: ~200–500 ns for typical queries (3–8 tokens)

Both functions operate on caller-provided scratch buffers to avoid
heap allocation on the hot path.  Buffer sizes are:
    query_vec_buf:  EMB_DIM  (32) Float32
    hidden_buf:     HIDDEN_DIM (24) Float32
    logits_buf:     max(INTENT_CLASSES=4, AGG_CLASSES=6, FAMILY_CLASSES=6) = 6 Float32
"""

from mojo.engine.vector_kernels.semantic_micro.semantic_types import (
    SemanticModel, SemanticQuery, SemanticHints,
    EMB_DIM, HIDDEN_DIM,
    INTENT_CLASSES, AGG_CLASSES, FAMILY_CLASSES,
    INTENT_CONF_THRESHOLD, AGG_CONF_THRESHOLD, FAMILY_CONF_THRESHOLD,
    EXPAND_MIN_SCORE, HINT_NONE,
)
from mojo.engine.vector_kernels.semantic_micro.semantic_embed import embed_query_avg
from mojo.engine.vector_kernels.semantic_micro.semantic_mlp import run_head
from mojo.engine.vector_kernels.semantic_micro.semantic_expand import expand_tokens_topk


fn infer_semantic_hints(
    model:          SemanticModel,
    query:          SemanticQuery,
    query_vec_buf:  UnsafePointer[Float32],   # caller scratch [EMB_DIM]
    hidden_buf:     UnsafePointer[Float32],   # caller scratch [HIDDEN_DIM]
    logits_buf:     UnsafePointer[Float32],   # caller scratch [6]
) -> SemanticHints:
    """
    Run the full semantic inference pipeline for one query.

    Steps:
      1. Embed query tokens → query_vec_buf (average pooling)
      2. Intent head   → hints.intent_class / intent_conf
      3. Aggregation head → hints.agg_class / agg_conf
      4. Family head   → hints.family_class / family_conf
      Each head silences its output if confidence < threshold.

    Args:
        model:         loaded SemanticModel
        query:         token IDs + metadata
        query_vec_buf: EMB_DIM scratch; overwritten
        hidden_buf:    HIDDEN_DIM scratch; overwritten
        logits_buf:    ≥ 6 float scratch; overwritten

    Returns:
        SemanticHints — check has_intent() / has_agg() / has_family() before use.
    """
    var hints = SemanticHints()

    # Step 1: embed query tokens → query vector
    embed_query_avg(
        model.embeddings,
        query.token_ids,
        query.token_count,
        query_vec_buf,
    )

    # Step 2: intent head
    var cls_buf  = UnsafePointer[UInt8].alloc(1)
    var conf_buf = UnsafePointer[Float32].alloc(1)

    run_head(
        model.intent_fc1, model.intent_fc2,
        query_vec_buf, hidden_buf, logits_buf,
        INTENT_CONF_THRESHOLD, cls_buf, conf_buf,
    )
    hints.intent_class = cls_buf[0]
    hints.intent_conf  = conf_buf[0]

    # Step 3: aggregation head
    run_head(
        model.agg_fc1, model.agg_fc2,
        query_vec_buf, hidden_buf, logits_buf,
        AGG_CONF_THRESHOLD, cls_buf, conf_buf,
    )
    hints.agg_class = cls_buf[0]
    hints.agg_conf  = conf_buf[0]

    # Step 4: semantic-family head
    run_head(
        model.family_fc1, model.family_fc2,
        query_vec_buf, hidden_buf, logits_buf,
        FAMILY_CONF_THRESHOLD, cls_buf, conf_buf,
    )
    hints.family_class = cls_buf[0]
    hints.family_conf  = conf_buf[0]

    cls_buf.free()
    conf_buf.free()

    return hints


fn semantic_expand_query(
    model:       SemanticModel,
    query:       SemanticQuery,
    min_score:   Float32,
    epoch:       UInt32,
    epoch_marks: UnsafePointer[UInt32],   # [vocab_size] dedup scratch
    out_ids:     UnsafePointer[UInt32],   # output expanded token IDs
    out_scores:  UnsafePointer[Float32],  # output expansion scores
    max_out:     UInt8,
) -> UInt8:
    """
    Expand query tokens via semantic nearest-neighbor table.

    Returns the expanded token IDs that score above min_score, deduplicated
    via epoch_marks.  Designed to be called once per query; caller increments
    epoch between calls to reset the dedup state.

    Args:
        model:       loaded SemanticModel
        query:       token IDs to expand
        min_score:   cosine similarity floor (default: EXPAND_MIN_SCORE = 0.82)
        epoch:       dedup epoch counter (monotonically increasing per call)
        epoch_marks: per-token epoch scratch [vocab_size]
        out_ids:     output buffer for expanded token IDs [max_out]
        out_scores:  output buffer for expansion scores [max_out]
        max_out:     capacity of output buffers

    Returns:
        Number of expanded tokens written to out_ids.
    """
    return expand_tokens_topk(
        model,
        query.token_ids,
        query.token_count,
        min_score,
        epoch,
        epoch_marks,
        out_ids,
        out_scores,
        max_out,
    )
