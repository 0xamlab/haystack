"""
attnk.mask — attention masks as additive bias: causal, sliding-window, padding, packed. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_attnk_mask.mojo
benchmark: benchmarks/mojo_benchmarks/bench_tensorx_and_gemm.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

One convention: additive bias, never a masked logit
-----------------------------------------------------
Two frozen kernels cover causal masking and they are not two spellings of one thing — they are
different functions with different signatures:

    transformer_attention.causal_mask_value(q, k)        -> 0.0 or -1e9      an additive BIAS
    transformer_blocks.causal_mask_logit(logit, q, k)    -> logit or -1e9    the MASKED LOGIT

Both are correct for their own callers. This module produces **additive bias** throughout, because
that is what composes: a bias can be summed with a sliding-window bias and a padding bias and added
to a score matrix once, whereas a masked-logit function has to be threaded through the score
computation itself and cannot be combined with a second mask at all.

`mask_convention_agreement()` reports what each frozen kernel returns for the same position pair, so
the difference is visible rather than a trap. Both stay reachable and unchanged.

Why -1e9 and not -inf
-----------------------
The frozen kernels use `-1e9` and this module matches them, deliberately. A true `-inf` produces
`exp(-inf - max) = 0` correctly in most rows but yields `NaN` for a row where EVERY position is
masked — `max` is then also `-inf`, and `-inf - -inf` is `NaN`, which propagates through the whole
output. Fully-masked rows occur in real batches: a padding-only row in a ragged batch, or a
sliding-window row whose window falls entirely outside the sequence. `-1e9` degrades to a uniform
distribution over a masked row instead of poisoning the tensor, which is the behaviour a caller can
detect and recover from.

`MASK_NEG` is exported so a caller can test against the same constant the kernels use.

Masks compose by addition, and that is load-bearing
-----------------------------------------------------
A sliding-window causal model needs both masks. Adding two `-1e9` biases gives `-2e9`, which is still
finite, still enormously negative, and still softmaxes to zero — so composition is just a sum, with
no special case for "masked twice". `mask_combine_flat` exists to make that explicit rather than
leaving each caller to rediscover it.

Public API:
  mask_convention_agreement(q, k, logit)    — what each frozen kernel returns for the same pair
  mask_causal_flat(s_q, s_k, offset)        — lower-triangular bias, with a KV-cache offset
  mask_sliding_window_flat(s_q, s_k, window, offset)
  mask_padding_flat(valid_len, s_q, s_k)    — right-padding for a ragged batch
  mask_block_diagonal_flat(cu_seqlens, n_seq, total, causal)  — packed sequences
  mask_combine_flat(a, b, n)                — additive composition
  mask_row_fully_masked(bias, s_q, s_k)     — how many query rows have no visible key
"""

from attnk.contract import (
    ATTN_ERR_BAD_CU_SEQLENS,
    ATTN_ERR_DIM_TOO_LARGE,
    ATTN_ERR_EMPTY_DIM,
    ATTN_ERR_LENGTH_MISMATCH,
    ATTN_MAX_SEQ,
    ATTN_OK,
)
from sparse_attention import local_window_mask
from transformer_attention import causal_mask_value
from transformer_blocks import causal_mask_logit

comptime MASK_NEG: Float64 = -1.0e9
"""The masked bias, matching the frozen kernels. See the module docstring for why not `-inf`."""

comptime MASK_MAX_CELLS: Int = 1 << 26
"""Cap on `s_q * s_k` for a materialized bias matrix — 64M cells, 512 MB of Float64.

A materialized mask is the thing a tiled attention kernel exists to avoid, so this ceiling is
deliberately reachable: it marks the size past which a caller should be generating the bias inside
the tile loop instead of asking for the whole matrix."""


@fieldwise_init
struct MaskSpec(Copyable, Movable):
    """A dense additive-bias matrix, row-major `[query][key]`, plus how much it masked."""

    var bias: List[Float64]
    var s_q: Int
    var s_k: Int
    var n_masked: Int
    var status: Int


@fieldwise_init
struct MaskConvention(Copyable, Movable):
    """What each frozen causal kernel returns for one position pair."""

    var additive_bias: Float64
    var masked_logit: Float64
    var input_logit: Float64
    var same_shape: Bool


def mask_convention_agreement(
    query_pos: Float64, key_pos: Float64, logit: Float64
) -> MaskConvention:
    """Both frozen causal kernels on the same pair, so the difference is a number not a surprise.

    `same_shape` is False whenever the two return different things — which is *always* for an
    unmasked position, because one returns a zero bias and the other returns the logit unchanged.
    That is the point: they are different functions, and a caller who assumed otherwise would be
    adding a logit to a score.
    """
    var bias = causal_mask_value(query_pos, key_pos)
    var masked = causal_mask_logit(logit, query_pos, key_pos)
    return MaskConvention(bias, masked, logit, bias == masked)


def _alloc_bias(s_q: Int, s_k: Int) -> Int:
    """Validate a mask shape. Returns a status; callers allocate only after `ATTN_OK`."""
    if s_q <= 0 or s_k <= 0:
        return ATTN_ERR_EMPTY_DIM
    if s_q > ATTN_MAX_SEQ or s_k > ATTN_MAX_SEQ:
        return ATTN_ERR_DIM_TOO_LARGE
    # Division, not a multiply: s_q * s_k wraps at these ceilings.
    if s_k > MASK_MAX_CELLS // s_q:
        return ATTN_ERR_DIM_TOO_LARGE
    return ATTN_OK


def mask_causal_flat(s_q: Int, s_k: Int, offset: Int) -> MaskSpec:
    """Causal bias. `offset` is how many cached keys precede the first query — the decode case.

    Without the offset a decode step is wrong in the most confusing possible way: with one query and
    1000 cached keys, a naive causal mask compares query index 0 against key indices 0..999 and masks
    everything except the first, so the model attends to the *beginning* of its context instead of
    the end. The query's true position is `offset + q`.

    Uses the frozen `transformer_attention.causal_mask_value` per cell rather than restating the
    comparison, so "causal" means exactly one thing across the tree.

    @capability mask_causal_flat
    complexity: O(s_q * s_k)
    counts:
    - dim s_q <= ATTN_MAX_SEQ [kernel_validated]
    - dim s_k <= ATTN_MAX_SEQ [kernel_validated]
    @endcapability
    """
    var bias = List[Float64]()
    var st = _alloc_bias(s_q, s_k)
    if st != ATTN_OK:
        return MaskSpec(bias^, 0, 0, 0, st)
    if offset < 0:
        return MaskSpec(bias^, 0, 0, 0, ATTN_ERR_EMPTY_DIM)

    var n_masked = 0
    for q in range(s_q):
        var qp = Float64(offset + q)
        for k in range(s_k):
            var v = causal_mask_value(qp, Float64(k))
            if v != 0.0:
                n_masked += 1
            bias.append(v)
    return MaskSpec(bias^, s_q, s_k, n_masked, ATTN_OK)


def mask_sliding_window_flat(
    s_q: Int, s_k: Int, window: Int, offset: Int
) -> MaskSpec:
    """Causal bias restricted to the last `window` keys. `window <= 0` means unbounded.

    Uses the frozen `sparse_attention.local_window_mask` for the window test and
    `causal_mask_value` for the causal one, then sums them — which is exactly the composition rule
    this module is built on, applied to its own two constituents.

    @capability mask_sliding_window_flat
    complexity: O(s_q * s_k)
    counts:
    - dim s_q <= ATTN_MAX_SEQ [kernel_validated]
    - dim s_k <= ATTN_MAX_SEQ [kernel_validated]
    @endcapability
    """
    var bias = List[Float64]()
    var st = _alloc_bias(s_q, s_k)
    if st != ATTN_OK:
        return MaskSpec(bias^, 0, 0, 0, st)
    if offset < 0:
        return MaskSpec(bias^, 0, 0, 0, ATTN_ERR_EMPTY_DIM)

    var n_masked = 0
    for q in range(s_q):
        var qp = Float64(offset + q)
        for k in range(s_k):
            var kp = Float64(k)
            var v = causal_mask_value(qp, kp)
            if window > 0:
                # Left window only; the causal term already forbids the right side.
                var w = local_window_mask(qp, kp, Float64(window), 0.0)
                if w != 0.0:
                    v += w
            if v != 0.0:
                n_masked += 1
            bias.append(v)
    return MaskSpec(bias^, s_q, s_k, n_masked, ATTN_OK)


def mask_padding_flat(valid_len: Int, s_q: Int, s_k: Int) -> MaskSpec:
    """Mask keys at or beyond `valid_len` — right-padding in a ragged batch.

    Keys only. A padded *query* row produces garbage output that the caller discards anyway, whereas
    a padded *key* attended to by a real query corrupts a real output. Masking query rows as well
    would create fully-masked rows for no benefit.

    @capability mask_padding_flat
    complexity: O(s_q * s_k)
    counts:
    - dim s_q <= ATTN_MAX_SEQ [kernel_validated]
    - dim s_k <= ATTN_MAX_SEQ [kernel_validated]
    @endcapability
    """
    var bias = List[Float64]()
    var st = _alloc_bias(s_q, s_k)
    if st != ATTN_OK:
        return MaskSpec(bias^, 0, 0, 0, st)
    if valid_len < 0 or valid_len > s_k:
        return MaskSpec(bias^, 0, 0, 0, ATTN_ERR_LENGTH_MISMATCH)

    var n_masked = 0
    for _ in range(s_q):
        for k in range(s_k):
            if k >= valid_len:
                bias.append(MASK_NEG)
                n_masked += 1
            else:
                bias.append(0.0)
    return MaskSpec(bias^, s_q, s_k, n_masked, ATTN_OK)


def mask_block_diagonal_flat(
    cu_seqlens: List[Int], n_seq: Int, total: Int, causal: Bool
) -> MaskSpec:
    """Block-diagonal bias for packed sequences: a token may only see its own document.

    This is what makes sequence packing safe, and its absence is silent. Packing concatenates several
    documents into one row to avoid padding; without a block-diagonal mask, document two attends to
    document one, and the model trains on cross-document attention that will never exist at inference.
    Loss goes down, the run looks healthy, and the model is worse.

    @capability mask_block_diagonal_flat
    complexity: O(total^2)
    counts:
    - n_seq + 1 <= len(cu_seqlens) [enforced]
    - dim total <= ATTN_MAX_SEQ [kernel_validated]
    @endcapability
    """
    var bias = List[Float64]()
    var st = _alloc_bias(total, total)
    if st != ATTN_OK:
        return MaskSpec(bias^, 0, 0, 0, st)
    if n_seq <= 0 or len(cu_seqlens) < n_seq + 1:
        return MaskSpec(bias^, 0, 0, 0, ATTN_ERR_BAD_CU_SEQLENS)
    if cu_seqlens[0] != 0 or cu_seqlens[n_seq] != total:
        return MaskSpec(bias^, 0, 0, 0, ATTN_ERR_BAD_CU_SEQLENS)

    # Segment id per token, derived once. Recomputing it per cell would make this O(total^2 * n_seq).
    var seg = List[Int](capacity=total)
    for _ in range(total):
        seg.append(-1)
    for i in range(n_seq):
        var lo = cu_seqlens[i]
        var hi = cu_seqlens[i + 1]
        if hi < lo or hi > total or lo < 0:
            return MaskSpec(List[Float64](), 0, 0, 0, ATTN_ERR_BAD_CU_SEQLENS)
        for t in range(lo, hi):
            seg[t] = i

    var n_masked = 0
    for q in range(total):
        for k in range(total):
            var visible = seg[q] == seg[k] and seg[q] >= 0
            if visible and causal:
                # Positions restart per document, but within one document the flat indices are
                # ordered, so the flat comparison is the per-document comparison.
                visible = k <= q
            if visible:
                bias.append(0.0)
            else:
                bias.append(MASK_NEG)
                n_masked += 1
    return MaskSpec(bias^, total, total, n_masked, ATTN_OK)


def mask_combine_flat(a: List[Float64], b: List[Float64], n: Int) -> MaskSpec:
    """Sum two bias matrices. Two masked entries give `-2e9`, which is still finite and still zero
    after softmax — so composition needs no special case.

    @capability mask_combine_flat
    complexity: O(n)
    counts:
    - n <= len(a, b) [enforced]
    @endcapability
    """
    var out = List[Float64]()
    if n <= 0:
        return MaskSpec(out^, 0, 0, 0, ATTN_ERR_EMPTY_DIM)
    if len(a) < n or len(b) < n:
        return MaskSpec(out^, 0, 0, 0, ATTN_ERR_LENGTH_MISMATCH)
    var n_masked = 0
    for i in range(n):
        var v = a[i] + b[i]
        if v != 0.0:
            n_masked += 1
        out.append(v)
    return MaskSpec(out^, n, 1, n_masked, ATTN_OK)


def mask_row_fully_masked(bias: List[Float64], s_q: Int, s_k: Int) -> Int:
    """Count query rows with no visible key. `-1` on a shape disagreement.

    Worth exporting rather than leaving implicit: a fully-masked row is exactly the case that turns
    a `-inf` mask into NaN, and it is reachable through ordinary configuration — a padding-only row,
    or a sliding window that falls off the start of a sequence. A caller that gets a non-zero count
    here knows to expect uniform attention on those rows rather than meaningful output.

    @capability mask_row_fully_masked
    complexity: O(s_q * s_k)
    counts:
    - dim s_q <= ATTN_MAX_SEQ [kernel_validated]
    - dim s_k <= ATTN_MAX_SEQ [kernel_validated]
    @endcapability
    """
    if s_q <= 0 or s_k <= 0:
        return -1
    if s_k > MASK_MAX_CELLS // s_q or len(bias) < s_q * s_k:
        return -1
    var count = 0
    for q in range(s_q):
        var row = q * s_k
        var any_visible = False
        for k in range(s_k):
            if bias[row + k] == 0.0:
                any_visible = True
                break
        if not any_visible:
            count += 1
    return count
