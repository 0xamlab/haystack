"""
semantic_micro/semantic_embed.mojo — Query embedding via average pooling.

Takes a sequence of token IDs, looks up each in the EmbeddingTable, and
produces a single fixed-size query vector by averaging.

SIMD path: EMB_DIM=32, SIMD_W=8 → 4 accumulators updated per token.
@parameter for unrolls the chunk loop at compile time → zero branch overhead.

Out-of-vocab tokens (id >= vocab_size) are silently skipped so callers do
not need to sanitize inputs.
"""

from mojo.engine.vector_kernels.semantic_micro.semantic_types import (
    EmbeddingTable, EMB_DIM, EMB_CHUNKS, SIMD_W,
)


@always_inline
fn embed_query_avg(
    emb:         EmbeddingTable,
    token_ids:   UnsafePointer[UInt32],
    token_count: UInt16,
    out_vec:     UnsafePointer[Float32],
):
    """
    Average-pool token embeddings into one EMB_DIM query vector.

    Args:
        emb:         loaded EmbeddingTable
        token_ids:   array of resolved token IDs (length = token_count)
        token_count: number of valid entries in token_ids
        out_vec:     caller-owned scratch of EMB_DIM floats; overwritten
    """
    # Zero accumulators via SIMD stores
    @parameter
    for c in range(EMB_CHUNKS):
        (out_vec + c * SIMD_W).store(SIMD[DType.float32, SIMD_W](Float32(0.0)))

    var valid: Int = 0

    for t in range(Int(token_count)):
        var tok = Int(token_ids[t])
        if tok >= Int(emb.vocab_size):
            continue
        valid += 1
        var ep = emb.values + tok * EMB_DIM
        @parameter
        for c in range(EMB_CHUNKS):
            var acc = (out_vec + c * SIMD_W).load[width=SIMD_W]()
            acc += (ep + c * SIMD_W).load[width=SIMD_W]()
            (out_vec + c * SIMD_W).store(acc)

    if valid == 0:
        return

    var inv_n = SIMD[DType.float32, SIMD_W](Float32(1.0) / Float32(valid))
    @parameter
    for c in range(EMB_CHUNKS):
        var acc = (out_vec + c * SIMD_W).load[width=SIMD_W]()
        (out_vec + c * SIMD_W).store(acc * inv_n)


@always_inline
fn embed_single_token(
    emb:     EmbeddingTable,
    tok_id:  UInt32,
    out_vec: UnsafePointer[Float32],
) -> Bool:
    """
    Copy one token embedding into out_vec.
    Returns True if token is in-vocab, False otherwise (out_vec unchanged).
    """
    if tok_id >= emb.vocab_size:
        return False
    var ep = emb.values + Int(tok_id) * EMB_DIM
    @parameter
    for c in range(EMB_CHUNKS):
        (out_vec + c * SIMD_W).store((ep + c * SIMD_W).load[width=SIMD_W]())
    return True


@always_inline
fn cosine_emb_dim(
    a: UnsafePointer[Float32],
    b: UnsafePointer[Float32],
) -> Float32:
    """
    Cosine similarity between two EMB_DIM vectors.
    Assumes non-zero norms (caller must verify; returns 0.0 if zero norm).
    """
    var dot  = SIMD[DType.float32, SIMD_W](Float32(0.0))
    var sq_a = SIMD[DType.float32, SIMD_W](Float32(0.0))
    var sq_b = SIMD[DType.float32, SIMD_W](Float32(0.0))

    @parameter
    for c in range(EMB_CHUNKS):
        var va = (a + c * SIMD_W).load[width=SIMD_W]()
        var vb = (b + c * SIMD_W).load[width=SIMD_W]()
        dot  += va * vb
        sq_a += va * va
        sq_b += vb * vb

    var d  = dot.reduce_add()
    var na = sq_a.reduce_add()
    var nb = sq_b.reduce_add()

    if na <= Float32(0.0) or nb <= Float32(0.0):
        return Float32(0.0)

    from std.math import sqrt
    var sim = d / (sqrt(na) * sqrt(nb))
    if sim > Float32(1.0): return Float32(1.0)
    if sim < Float32(0.0): return Float32(0.0)
    return sim
