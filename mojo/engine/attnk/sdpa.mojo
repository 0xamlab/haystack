"""
attnk.sdpa — scaled dot-product attention, materialized. The reference, not the fast path. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_attnk_sdpa.mojo
benchmark: benchmarks/mojo_benchmarks/bench_attnk.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

This module is deliberately the slow one
------------------------------------------
It materializes the full `s_q x s_k` score matrix, softmaxes it, and multiplies by V. That is exactly
what `flash.mojo` exists to avoid, and exactly why this exists: the tiled kernel's correctness claim
is "same answer as the materialized one", and that claim needs something to be measured against.

So this is optimized for being obviously right rather than fast. It does the arithmetic in the order
the definition states, uses the frozen scalar kernels for every step, and has no blocking, no
tiling and no reordering that could hide a discrepancy.

Layout
------
Q is `[token][head][dim]` row-major with `h_q` heads. K and V are `[token][head][dim]` with `h_kv`
heads. With grouped-query attention `h_kv < h_q` and each KV head serves `h_q / h_kv` consecutive
query heads — `attn_dims_check` enforces the divisibility, because a non-divisible pair silently gives
some group a different size and every indexing scheme picks a different wrong head for the remainder.

The scale is applied to the score, not folded into Q
------------------------------------------------------
`score = (q . k) / sqrt(d)` via the frozen `transformer_attention.scaled_dot_product_attention`.
Pre-scaling Q would be one fewer multiply per score, and it changes the numbers: scaling once per
element of Q rounds differently from scaling once per dot product. For a reference whose whole job is
to be the thing others are compared against, matching the definition matters more than the multiply.

Public API:
  sdpa_scores_flat(q, k, n_tok_q, n_tok_k, h_q, h_kv, d, scale) -> SdpaScores
  sdpa_softmax_rows_flat(scores, rows, cols)                     -> SdpaScores
  sdpa_forward_flat(q, k, v, bias, ...)                          -> SdpaOut
"""

from std.math import exp as mexp, log as mlog
from attnk.contract import (
    ATTN_ERR_EMPTY_DIM,
    ATTN_ERR_LENGTH_MISMATCH,
    ATTN_ERR_NON_FINITE_SCALAR,
    ATTN_OK,
    attn_dims_check,
    attn_scalars_ok,
)
from transformer_attention import attention_softmax_stable, scaled_dot_product_attention


@fieldwise_init
struct SdpaScores(Copyable, Movable):
    """A materialized score or probability matrix, row-major `[head][query][key]`."""

    var values: List[Float64]
    var n_heads: Int
    var rows: Int
    var cols: Int
    var status: Int


@fieldwise_init
struct SdpaOut(Copyable, Movable):
    """Attention output, `[token][head][dim]`, plus the log-sum-exp per (head, query) row.

    `lse` is carried because the tiled kernel produces it naturally and the two must agree — it is a
    far more sensitive equality check than the output alone, since it depends on every score in the
    row rather than on a weighted average that can hide compensating errors.
    """

    var out: List[Float64]
    var lse: List[Float64]
    var n_tok: Int
    var n_heads: Int
    var head_dim: Int
    var status: Int


fn sdpa_scores_flat(
    q: List[Float64], k: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, scale: Float64
) -> SdpaScores:
    """Q @ K^T scaled, materialized as `[head][query][key]`.

    `scale <= 0` means "use 1/sqrt(d)", the standard. An explicit positive scale overrides it, which
    some architectures need.

    @capability sdpa_scores_flat
    complexity: O(h_q * n_tok_q * n_tok_k * d)
    counts:
    - n_tok_q * h_q * d <= len(q) [enforced]
    - n_tok_k * h_kv * d <= len(k) [enforced]
    @endcapability
    """
    var out = List[Float64]()
    var shape = attn_dims_check(1, h_q, h_kv, n_tok_q, n_tok_k, d)
    if shape != ATTN_OK:
        return SdpaScores(out^, 0, 0, 0, shape)
    if not attn_scalars_ok(scale):
        return SdpaScores(out^, 0, 0, 0, ATTN_ERR_NON_FINITE_SCALAR)
    if len(q) < n_tok_q * h_q * d or len(k) < n_tok_k * h_kv * d:
        return SdpaScores(out^, 0, 0, 0, ATTN_ERR_LENGTH_MISMATCH)

    var group = h_q // h_kv
    var qp = q.unsafe_ptr()
    var kp = k.unsafe_ptr()

    for h in range(h_q):
        var hk = h // group
        for i in range(n_tok_q):
            var qbase = (i * h_q + h) * d
            for j in range(n_tok_k):
                var kbase = (j * h_kv + hk) * d
                var dot = 0.0
                for e in range(d):
                    dot += qp[qbase + e] * kp[kbase + e]
                # Frozen kernel: applies 1/sqrt(d_k) to the dot product.
                var s = scaled_dot_product_attention(dot, Float64(d))
                if scale > 0.0:
                    # An explicit scale replaces the default rather than compounding it.
                    s = dot * scale
                out.append(s)

    return SdpaScores(out^, h_q, n_tok_q, n_tok_k, ATTN_OK)


fn sdpa_softmax_rows_flat(scores: List[Float64], rows: Int, cols: Int) -> SdpaScores:
    """Row-wise stable softmax over a flat `[rows][cols]` matrix.

    Max-subtracted, via the frozen `transformer_attention.attention_softmax_stable`. Without the
    subtraction, `exp(score)` overflows to inf for scores past ~709 and the row becomes NaN — and
    scores reach that range with large head dimensions and unnormalised inputs.

    @capability sdpa_softmax_rows_flat
    complexity: O(rows * cols)
    counts:
    - rows * cols <= len(scores) [enforced]
    @endcapability
    """
    var out = List[Float64]()
    if rows <= 0 or cols <= 0:
        return SdpaScores(out^, 0, 0, 0, ATTN_ERR_EMPTY_DIM)
    if len(scores) < rows * cols:
        return SdpaScores(out^, 0, 0, 0, ATTN_ERR_LENGTH_MISMATCH)

    for r in range(rows):
        var base = r * cols
        var m = scores[base]
        for c in range(1, cols):
            if scores[base + c] > m:
                m = scores[base + c]
        var total = 0.0
        for c in range(cols):
            total += mexp(scores[base + c] - m)
        for c in range(cols):
            out.append(attention_softmax_stable(scores[base + c], m, total))

    return SdpaScores(out^, 1, rows, cols, ATTN_OK)


fn sdpa_forward_flat(
    q: List[Float64], k: List[Float64], v: List[Float64], bias: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int,
    scale: Float64, use_bias: Bool
) -> SdpaOut:
    """Full attention: softmax(QK^T/sqrt(d) + bias) @ V, materialized.

    `bias` is the additive mask from `attnk.mask`, shaped `[query][key]` and shared across heads —
    which is what a causal or packing mask is. A per-head bias would be a different shape and is not
    accepted here rather than being guessed at from the length.

    @capability sdpa_forward_flat
    complexity: O(h_q * n_tok_q * n_tok_k * d)
    counts:
    - n_tok_q * h_q * d <= len(q) [enforced]
    - n_tok_k * h_kv * d <= len(k, v) [enforced]
    @endcapability
    """
    var out = List[Float64]()
    var lse = List[Float64]()
    var shape = attn_dims_check(1, h_q, h_kv, n_tok_q, n_tok_k, d)
    if shape != ATTN_OK:
        return SdpaOut(out^, lse^, 0, 0, 0, shape)
    if not attn_scalars_ok(scale):
        return SdpaOut(out^, lse^, 0, 0, 0, ATTN_ERR_NON_FINITE_SCALAR)
    if len(q) < n_tok_q * h_q * d or len(k) < n_tok_k * h_kv * d or len(v) < n_tok_k * h_kv * d:
        return SdpaOut(out^, lse^, 0, 0, 0, ATTN_ERR_LENGTH_MISMATCH)
    if use_bias and len(bias) < n_tok_q * n_tok_k:
        return SdpaOut(out^, lse^, 0, 0, 0, ATTN_ERR_LENGTH_MISMATCH)

    var group = h_q // h_kv
    var qp = q.unsafe_ptr()
    var kp = k.unsafe_ptr()
    var vp = v.unsafe_ptr()

    for _ in range(n_tok_q * h_q * d):
        out.append(0.0)
    for _ in range(h_q * n_tok_q):
        lse.append(0.0)
    var op = out.unsafe_ptr()

    var row = List[Float64](capacity=n_tok_k)
    for _ in range(n_tok_k):
        row.append(0.0)

    for h in range(h_q):
        var hk = h // group
        for i in range(n_tok_q):
            var qbase = (i * h_q + h) * d

            # One score row, materialized. This is the allocation flash.mojo refuses to make.
            var m = -1.0e308
            for j in range(n_tok_k):
                var kbase = (j * h_kv + hk) * d
                var dot = 0.0
                for e in range(d):
                    dot += qp[qbase + e] * kp[kbase + e]
                var s = dot * scale if scale > 0.0 else scaled_dot_product_attention(dot, Float64(d))
                if use_bias:
                    s += bias[i * n_tok_k + j]
                row[j] = s
                if s > m:
                    m = s

            var total = 0.0
            for j in range(n_tok_k):
                total += mexp(row[j] - m)

            # log-sum-exp in the max-shifted form, which is the only form that stays finite.
            lse[h * n_tok_q + i] = m + _ln(total)

            var obase = (i * h_q + h) * d
            for j in range(n_tok_k):
                var w = attention_softmax_stable(row[j], m, total)
                if w == 0.0:
                    continue
                var vbase = (j * h_kv + hk) * d
                for e in range(d):
                    op[obase + e] += w * vp[vbase + e]

    return SdpaOut(out^, lse^, n_tok_q, h_q, d, ATTN_OK)


fn _ln(x: Float64) -> Float64:
    """Natural log, guarding the zero case.

    A fully-masked row can produce a zero normalizer under some bias conventions. `log(0)` is `-inf`,
    which then propagates through any comparison against the lse; returning a large negative finite
    value keeps the diagnostic usable, matching the reasoning behind `MASK_NEG` in `attnk.mask`.
    """
    if x <= 0.0:
        return -1.0e308
    return mlog(x)
