"""
attnk.contract — the one status vocabulary and work budget for attention kernels. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_attnk_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_tensorx_and_gemm.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Status range
------------
`attnk` owns **360-379**, after `tensorx` 300-319 and `gemm` 320-339 (rule 4e). Finiteness comes from
`tensorx.contract.tx_finite` rather than a fourth private copy.

Attention's work budget is not a product of its dimensions
------------------------------------------------------------
Every other kernel here bounds `m * n * k`. Attention cannot use that shape, because its cost is
quadratic in sequence length and the quadratic term is per head and per sequence:

    score cells = n_seq x h_q x s^2   for a fixed length s
                = h_q x d x SUM_i(s_i^2)   for variable lengths

The sum-of-squares matters. With variable-length sequences packed into one batch, `n_seq * max_len^2`
over-counts a packed batch of short sequences and *under*-counts a batch containing one long one —
and the under-count is the direction that hurts, because a single 32k sequence hidden among short
ones is precisely the request that runs for hours. So `attn_work_cells_varlen` charges each sequence
its own square.

Rule 1c applies on top: bounding the cell count is not bounding memory. A materialized score matrix
is `s^2` cells per head; the whole reason a tiled kernel exists is to never allocate it.

Public API:
  attn_status_name(code)                                  — the status vocabulary
  attn_dims_check(n_seq, h_q, h_kv, s_q, s_k, d)          — head/shape agreement, GQA divisibility
  attn_work_fits(n_seq, h_q, s, d, ceiling)               — fixed-length budget, no wrapping product
  attn_work_cells_varlen(cu_seqlens, n_seq, h_q, d)       — per-sequence sum of squares
  attn_backend_name(code)                                 — which kernel produced a result
  attn_ws_bytes_direct(s_q, s_kv, d)                      — one worker's materialized-score bytes
  attn_ws_bytes_tiled(br, bc, d)                          — one worker's tiled-kernel scratch bytes
  attn_score_bytes_fit(s_q, s_kv, n_workers, ceiling)     — refuse the quadratic allocation, don't attempt it
"""

from tensorx.contract import tx_finite

# ── status codes: attnk owns 360-379 ──────────────────────────────────────────

comptime ATTN_OK: Int = 360
comptime ATTN_ERR_EMPTY_DIM: Int = 361
comptime ATTN_ERR_HEAD_MISMATCH: Int = 362
comptime ATTN_ERR_GQA_NOT_DIVISIBLE: Int = 363
comptime ATTN_ERR_LENGTH_MISMATCH: Int = 364
comptime ATTN_ERR_WORK_TOO_LARGE: Int = 365
comptime ATTN_ERR_DIM_TOO_LARGE: Int = 366
comptime ATTN_ERR_NON_FINITE_SCALAR: Int = 367
comptime ATTN_ERR_BAD_CU_SEQLENS: Int = 368
comptime ATTN_ERR_UNKNOWN_MASK: Int = 369
comptime ATTN_ERR_UNKNOWN_SCALING: Int = 370
comptime ATTN_ERR_NON_FINITE_SCALE: Int = 371
comptime ATTN_ERR_CAUSAL_SHAPE: Int = 372
comptime ATTN_ERR_TILE: Int = 373
comptime ATTN_ERR_SCORE_BYTES: Int = 374
comptime ATTN_ERR_OVERFLOW: Int = 375
comptime ATTN_ERR_Q_LENGTH: Int = 376

# ── backend tags: which kernel produced an AttnResult ─────────────────────────

comptime ATTN_BACKEND_DIRECT: Int = 0
"""Materialized s_q x s_kv score matrix, softmax with max-subtraction. Stable, and the memory-cost
arm: it exists so the tiled kernel's O(br*bc) claim is a measurement against a real alternative."""

comptime ATTN_BACKEND_TILED: Int = 1
"""Blockwise online softmax. O(br*bc) live intermediates per worker, never O(s^2). The product
kernel."""

comptime ATTN_BACKEND_UNSTABLE: Int = 2
"""`ATTN_BACKEND_DIRECT`'s code path with the max-subtraction skipped. Never the recommended entry;
exists to make the stability argument a measured overflow rather than an assertion."""

comptime ATTN_MAX_SCORE_BYTES: Int = 1 << 30
"""Ceiling on the TOTAL bytes every worker's materialized score matrix would occupy at once
(`n_workers * s_q * s_kv * 8`). 1 GiB is far past any legitimate direct-kernel call — the tiled
kernel exists precisely so a real deployment never needs this much — and low enough that a
fat-fingered sequence length is refused rather than attempted. Mirrors `ATTN_MAX_WORK_CELLS`'s
role: rule 1c's "bounding cell count is not bounding memory" applies most directly here, since this
is the one kernel in the package that actually materializes the quadratic term."""

comptime ATTN_MAX_SEQ: Int = 1 << 20
"""Longest single sequence, per head.

2^20 tokens is far past any served context and still leaves the squared term inside the work ceiling
below. It exists so a caller who passes a byte count where a token count belongs gets an error rather
than a machine that stops responding."""

comptime ATTN_MAX_HEAD_DIM: Int = 1024
"""Largest per-head dimension. 128 is typical, 256 appears; 1024 is comfortable headroom and small
enough that a transposed or mis-multiplied dimension is caught rather than allocated."""

comptime ATTN_MAX_WORK_CELLS: Int = 1 << 38
"""Bound on total score cells across every head and sequence.

2^38 is minutes of scalar work — high enough that no legitimate call reaches it, low enough that a
fat-fingered sequence length returns an error instead of a hang. From a client's side a hang is
indistinguishable from rule 1's uncatchable abort, which is why work is bounded at all."""


fn attn_status_name(code: Int) -> String:
    """Name a status code. Unknown codes say so rather than borrowing a neighbour's meaning."""
    if code == ATTN_OK:
        return String("ok")
    if code == ATTN_ERR_EMPTY_DIM:
        return String("empty_dimension")
    if code == ATTN_ERR_HEAD_MISMATCH:
        return String("head_count_mismatch")
    if code == ATTN_ERR_GQA_NOT_DIVISIBLE:
        return String("gqa_heads_not_divisible")
    if code == ATTN_ERR_LENGTH_MISMATCH:
        return String("length_mismatch")
    if code == ATTN_ERR_WORK_TOO_LARGE:
        return String("work_budget_exceeded")
    if code == ATTN_ERR_DIM_TOO_LARGE:
        return String("dimension_too_large")
    if code == ATTN_ERR_NON_FINITE_SCALAR:
        return String("non_finite_scalar")
    if code == ATTN_ERR_BAD_CU_SEQLENS:
        return String("bad_cu_seqlens")
    if code == ATTN_ERR_UNKNOWN_MASK:
        return String("unknown_mask_kind")
    if code == ATTN_ERR_UNKNOWN_SCALING:
        return String("unknown_rope_scaling")
    if code == ATTN_ERR_NON_FINITE_SCALE:
        return String("non_finite_scale")
    if code == ATTN_ERR_CAUSAL_SHAPE:
        return String("causal_requires_equal_seq_lengths")
    if code == ATTN_ERR_TILE:
        return String("invalid_tile_shape")
    if code == ATTN_ERR_SCORE_BYTES:
        return String("score_matrix_bytes_exceeded")
    if code == ATTN_ERR_OVERFLOW:
        return String("softmax_overflow")
    if code == ATTN_ERR_Q_LENGTH:
        return String("output_length_mismatch")
    return String("unknown_status")


fn attn_backend_name(code: Int) -> String:
    """Name a backend tag. Unknown codes say so rather than borrowing a neighbour's meaning."""
    if code == ATTN_BACKEND_DIRECT:
        return String("direct")
    if code == ATTN_BACKEND_TILED:
        return String("tiled")
    if code == ATTN_BACKEND_UNSTABLE:
        return String("unstable")
    return String("unknown_backend")


fn attn_work_fits(n_seq: Int, h_q: Int, s: Int, d: Int, ceiling: Int) -> Bool:
    """True when `n_seq * h_q * s * s * d` fits in `ceiling`, computed WITHOUT forming the product.

    Five factors, grown one at a time by division. A wrapping 64-bit multiply is how a product guard
    was walked past in `sparse_numerics` and aborted the worker; with `s` appearing twice the
    opportunity here is larger, not smaller.

    @capability attn_work_fits
    complexity: O(1)
    counts:
    - dim s <= ATTN_MAX_SEQ [kernel_validated]
    - dim d <= ATTN_MAX_HEAD_DIM [kernel_validated]
    @endcapability
    """
    if n_seq <= 0 or h_q <= 0 or s <= 0 or d <= 0 or ceiling <= 0:
        return False
    if s > ATTN_MAX_SEQ or d > ATTN_MAX_HEAD_DIM:
        return False
    var remaining = ceiling
    if n_seq > remaining:
        return False
    remaining = remaining // n_seq
    if h_q > remaining:
        return False
    remaining = remaining // h_q
    if s > remaining:
        return False
    remaining = remaining // s
    if s > remaining:
        return False
    remaining = remaining // s
    return d <= remaining


fn attn_dims_check(
    n_seq: Int, h_q: Int, h_kv: Int, s_q: Int, s_k: Int, d: Int
) -> Int:
    """Validate attention shapes, including the GQA head-grouping rule.

    `h_q % h_kv == 0` is the check worth having. Grouped-query attention shares one KV head across a
    fixed group of query heads; a non-divisible pair means some group is a different size, and every
    indexing scheme silently picks a different wrong head for the remainder. It produces a full
    output tensor and a model that is subtly wrong.

    @capability attn_dims_check
    complexity: O(1)
    counts:
    - dim s_q <= ATTN_MAX_SEQ [kernel_validated]
    - dim s_k <= ATTN_MAX_SEQ [kernel_validated]
    - dim d <= ATTN_MAX_HEAD_DIM [kernel_validated]
    @endcapability
    """
    if n_seq <= 0 or h_q <= 0 or h_kv <= 0 or s_q <= 0 or s_k <= 0 or d <= 0:
        return ATTN_ERR_EMPTY_DIM
    if s_q > ATTN_MAX_SEQ or s_k > ATTN_MAX_SEQ:
        return ATTN_ERR_DIM_TOO_LARGE
    if d > ATTN_MAX_HEAD_DIM:
        return ATTN_ERR_DIM_TOO_LARGE
    if h_kv > h_q:
        return ATTN_ERR_HEAD_MISMATCH
    if h_q % h_kv != 0:
        return ATTN_ERR_GQA_NOT_DIVISIBLE
    var s_max = s_q if s_q > s_k else s_k
    if not attn_work_fits(n_seq, h_q, s_max, d, ATTN_MAX_WORK_CELLS):
        return ATTN_ERR_WORK_TOO_LARGE
    return ATTN_OK


fn attn_work_cells_varlen(
    cu_seqlens: List[Int], n_seq: Int, h_q: Int, d: Int
) -> Float64:
    """Score cells for a packed batch: `h_q * d * SUM_i(s_i^2)`. Negative on a malformed `cu_seqlens`.

    The sum of squares, not `n_seq * max_len^2`. A packed batch of one 32k sequence and thirty short
    ones has a max length of 32k, so the max-based estimate would charge thirty-one 32k sequences —
    and the same estimate applied the other way round *under*-charges the batch that actually costs,
    which is the direction that produces a run that never returns.

    Returns `Float64` because the true count exceeds `Int` well before it exceeds the budget, and a
    wrapped count would compare as small.

    @capability attn_work_cells_varlen
    complexity: O(n_seq)
    counts:
    - n_seq + 1 <= len(cu_seqlens) [enforced]
    @endcapability
    """
    if n_seq <= 0 or h_q <= 0 or d <= 0:
        return -1.0
    if len(cu_seqlens) < n_seq + 1:
        return -1.0
    if cu_seqlens[0] != 0:
        return -1.0
    var total = 0.0
    for i in range(n_seq):
        var lo = cu_seqlens[i]
        var hi = cu_seqlens[i + 1]
        if hi < lo:
            return -1.0
        var s = Float64(hi - lo)
        if s > Float64(ATTN_MAX_SEQ):
            return -1.0
        total += s * s
    return total * Float64(h_q) * Float64(d)


fn attn_scalars_ok(scale: Float64) -> Bool:
    """True when the softmax scale is finite.

    Checked before any score is formed. A NaN scale makes every score NaN, every subsequent
    comparison False, and an audit that counts zero violations (rule 4d).
    """
    return tx_finite(scale)


fn attn_scale_ok(scale: Float64) -> Bool:
    """Alias of `attn_scalars_ok`, named for the single-scalar call sites that check one softmax
    scale rather than a batch of them. Same body, on purpose: two names for one check would let
    them drift."""
    return attn_scalars_ok(scale)


fn attn_ws_bytes_direct(s_q: Int, s_kv: Int, d: Int) -> Float64:
    """Bytes ONE worker's materialized score matrix occupies: `s_q * s_kv` Float64 cells.

    `d` is accepted for signature symmetry with `attn_ws_bytes_tiled` and is not part of the
    formula: the direct kernel's live intermediate is the score matrix alone, per the module
    docstring's "a materialized score matrix is s^2 cells per head".

    @capability attn_ws_bytes_direct
    complexity: O(1)
    counts:
    - dim s_q <= ATTN_MAX_SEQ [enforced]
    - dim s_kv <= ATTN_MAX_SEQ [enforced]
    @endcapability
    """
    if s_q <= 0 or s_kv <= 0:
        return 0.0
    return Float64(s_q) * Float64(s_kv) * 8.0


fn attn_ws_bytes_tiled(br: Int, bc: Int, d: Int) -> Float64:
    """Bytes ONE worker's tiled-kernel scratch occupies for a `(br, bc)` tile at head dimension `d`.

    Three pieces, all Float64: the `br x bc` score tile, the `br x d` running accumulator, and the
    `bc x d` K and V blocks streamed against it (one each). At the shipped defaults
    `BR_DEFAULT=32, BC_DEFAULT=128, d=64` this is `8 * (32*128 + 32*64 + 2*128*64)` = 180224 bytes =
    176 KiB, matching the measured figure in `attnk.tiled`'s module docstring exactly -- this formula
    is read off that worked example, not assumed independently of it.

    @capability attn_ws_bytes_tiled
    complexity: O(1)
    counts:
    - dim br <= ATTN_MAX_SEQ [enforced]
    - dim bc <= ATTN_MAX_SEQ [enforced]
    @endcapability
    """
    if br <= 0 or bc <= 0 or d <= 0:
        return 0.0
    var score_tile = Float64(br) * Float64(bc)
    var accumulator = Float64(br) * Float64(d)
    var kv_blocks = 2.0 * Float64(bc) * Float64(d)
    return 8.0 * (score_tile + accumulator + kv_blocks)


fn attn_score_bytes_fit(s_q: Int, s_kv: Int, n_workers: Int, ceiling: Int) -> Bool:
    """True when `n_workers * s_q * s_kv * 8` fits in `ceiling`, computed WITHOUT forming the product.

    This is the TOTAL the direct kernel would hold live across every worker at once -- each worker
    materializes its own full `s_q x s_kv` score matrix -- which is why `n_workers` is a factor here
    and not in `attn_ws_bytes_direct`, which reports only one worker's share for comparison against
    the tiled kernel. Grown by division, one factor at a time, for the same reason
    `attn_work_fits` is: a wrapping 64-bit multiply is how a product guard was walked past in
    `sparse_numerics` and aborted the worker.

    @capability attn_score_bytes_fit
    complexity: O(1)
    counts:
    - dim s_q <= ATTN_MAX_SEQ [enforced]
    - dim s_kv <= ATTN_MAX_SEQ [enforced]
    @endcapability
    """
    if s_q <= 0 or s_kv <= 0 or n_workers <= 0 or ceiling <= 0:
        return False
    var remaining = ceiling
    if n_workers > remaining:
        return False
    remaining = remaining // n_workers
    if s_q > remaining:
        return False
    remaining = remaining // s_q
    if s_kv > remaining:
        return False
    remaining = remaining // s_kv
    return 8 <= remaining
