"""
semantic_micro/semantic_expand.mojo — Token expansion via precomputed nearest-neighbor table.

For each query token, looks up its NN_K nearest neighbors in the precomputed
table and emits those whose cosine similarity clears EXPAND_MIN_SCORE.

This replaces manual alias maintenance for synonym pairs: the training pipeline
pre-clusters the embedding space and stores the top-K neighbors per token so
expansion is O(token_count × K) at runtime — no ANN index, no matrix multiply.

Dedup uses an epoch scratch pattern (same idiom as prefilter.mojo):
  epoch_mark[token_id] == current_epoch → already seen → skip
Caller increments epoch between calls. Max expansion is capped at max_out.
"""

from mojo.engine.vector_kernels.semantic_micro.semantic_types import (
    SemanticModel, NN_K, EXPAND_MIN_SCORE,
)


@always_inline
fn expand_tokens_topk(
    model:       SemanticModel,
    token_ids:   UnsafePointer[UInt32],
    token_count: UInt16,
    min_score:   Float32,
    epoch:       UInt32,
    epoch_marks: UnsafePointer[UInt32],   # [vocab_size] scratch; epoch-marked dedup
    out_ids:     UnsafePointer[UInt32],   # [max_out] output token ids
    out_scores:  UnsafePointer[Float32],  # [max_out] output similarity scores
    max_out:     UInt8,
) -> UInt8:
    """
    Collect nearest-neighbor expansions for each query token.

    For each token t in token_ids, emits its NN_K neighbors from the
    precomputed table where score >= min_score AND not yet seen this epoch.

    Args:
        model:       loaded SemanticModel with nn_token_ids / nn_scores
        token_ids:   query token IDs (length = token_count)
        token_count: number of valid entries in token_ids
        min_score:   cosine similarity floor (default: EXPAND_MIN_SCORE = 0.82)
        epoch:       monotonically increasing call counter for dedup scratch
        epoch_marks: per-token epoch mark array (length = model.embeddings.vocab_size)
        out_ids:     output array for expanded token IDs
        out_scores:  output array for expansion scores
        max_out:     capacity of out_ids / out_scores

    Returns:
        Number of entries written to out_ids (≤ max_out).
    """
    var vocab_size = Int(model.embeddings.vocab_size)
    var out_count  = UInt8(0)

    for t in range(Int(token_count)):
        var tok = Int(token_ids[t])
        if tok >= vocab_size:
            continue

        var nn_base = tok * NN_K

        for k in range(NN_K):
            var score = model.nn_scores[nn_base + k]
            if score < min_score:
                break   # neighbors are sorted descending; first miss → no more hits

            var neighbor = model.nn_token_ids[nn_base + k]
            var nidx     = Int(neighbor)
            if nidx >= vocab_size:
                continue

            # Skip if already emitted this epoch
            if epoch_marks[nidx] == epoch:
                continue

            epoch_marks[nidx] = epoch

            out_ids[Int(out_count)]    = neighbor
            out_scores[Int(out_count)] = score
            out_count += 1

            if out_count >= max_out:
                return out_count

    return out_count


@always_inline
fn expand_tokens_simple(
    model:       SemanticModel,
    token_ids:   UnsafePointer[UInt32],
    token_count: UInt16,
    out_ids:     UnsafePointer[UInt32],
    out_scores:  UnsafePointer[Float32],
    max_out:     UInt8,
) -> UInt8:
    """
    Simpler expansion without epoch-mark dedup — for callers that manage
    a fresh scratch buffer per call or do not care about duplicates.
    """
    var vocab_size = Int(model.embeddings.vocab_size)
    var out_count  = UInt8(0)
    var seen: List[Bool] = List[Bool]()
    for _ in range(vocab_size):
        seen.append(False)

    for t in range(Int(token_count)):
        var tok = Int(token_ids[t])
        if tok >= vocab_size:
            continue
        var nn_base = tok * NN_K
        for k in range(NN_K):
            var score    = model.nn_scores[nn_base + k]
            if score < EXPAND_MIN_SCORE:
                break
            var neighbor = model.nn_token_ids[nn_base + k]
            var nidx     = Int(neighbor)
            if nidx >= vocab_size or seen[nidx]:
                continue
            seen[nidx] = True
            out_ids[Int(out_count)]    = neighbor
            out_scores[Int(out_count)] = score
            out_count += 1
            if out_count >= max_out:
                return out_count

    return out_count
