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
    return String("unknown_status")


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
