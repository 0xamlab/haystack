"""
attnk.flash — tiled attention with online softmax. Never materializes the score matrix. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_attnk_flash.mojo
benchmark: benchmarks/mojo_benchmarks/bench_attnk.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

The recurrence is frozen; this module is the loop around it
-------------------------------------------------------------
`flash_attention.mojo` already contains the whole online-softmax recurrence, one scalar step at a
time — that is what those five functions are, read in order:

    flash_block_max(m_old, score)                        -> m_new
    flash_block_sum_exp(l_old, m_old, m_new, score)      -> l_old*exp(m_old-m_new) + exp(score-m_new)
    flash_block_output(o_old, m_old, m_new, w, value)    -> o_old*exp(m_old-m_new) + w*value
    flash_final_normalize(o, l)                          -> o / l

They were never called by anything. What was missing is the loop that walks K and V in blocks while
carrying `(m, l, o)` forward, and that loop is all this module adds. Rule 3: the value here is the
composition, not the arithmetic.

Why this is the point of the whole package
--------------------------------------------
Materialized attention allocates `s_q x s_k` scores. At 32k context that is a billion cells per head
— 8 GB in Float64 — before any arithmetic happens, which is why long context is a memory problem
rather than a compute one. The online form keeps three running scalars per query row plus the output
accumulator, so peak extra memory is `O(d)` per query and independent of `s_k`. The answer is the
same; only the allocation differs. `flash_agrees_with_sdpa` is what turns that from a claim into a
measurement.

The update order is load-bearing
----------------------------------
`flash_block_sum_exp` and `flash_block_output` both take `m_old` AND `m_new`. So the running max must
be updated *after* both, not before — advancing `m` first makes the rescale factor `exp(m_new-m_new)`
= 1 and silently drops the correction for every value already accumulated. The result still looks
like attention: it is a valid probability distribution over a wrong set of weights.

Fully-masked rows and the initial max
---------------------------------------
`m` starts at a large negative finite sentinel rather than `-inf`, for the same reason `attnk.mask`
uses `-1e9` rather than `-inf`: with `-inf`, a row whose scores are all `-inf` computes
`exp(-inf - -inf)` = `NaN` and poisons the output. With a finite sentinel a fully-masked row
degrades to a uniform average, which a caller can detect via `mask_row_fully_masked` and act on.

Public API:
  flash_forward_flat(q, k, v, bias, ..., block_k)  -> FlashOut
  flash_block_plan(s_k, d, cache_bytes)            -> FlashPlan
  flash_agrees_with_sdpa(q, k, v, bias, ...)       -> FlashAgreement
"""

from std.math import exp as mexp, log as mlog
from attnk.contract import (
    ATTN_ERR_LENGTH_MISMATCH,
    ATTN_ERR_NON_FINITE_SCALAR,
    ATTN_OK,
    attn_dims_check,
    attn_scalars_ok,
)
from attnk.sdpa import sdpa_forward_flat
from flash_attention import (
    flash_block_max,
    flash_block_output,
    flash_block_sum_exp,
    flash_final_normalize,
)
from tensorx.dtype import DT_F64, dtx_tol_for
from transformer_attention import scaled_dot_product_attention

comptime FLASH_NEG_SENTINEL: Float64 = -1.0e308
"""Initial running max. Finite on purpose — see the module docstring."""

comptime FLASH_DEFAULT_BLOCK_K: Int = 64
"""Keys per tile when the caller does not choose.

64 keys of Float64 at head dim 128 is 64 KB of K plus 64 KB of V — an L1/L2-resident working set that
is reused across every query in the tile. `flash_block_plan` derives it from a real cache size."""


@fieldwise_init
struct FlashOut(Copyable, Movable):
    """Attention output and per-row log-sum-exp, same shape as the materialized reference."""

    var out: List[Float64]
    var lse: List[Float64]
    var n_tok: Int
    var n_heads: Int
    var head_dim: Int
    var blocks_walked: Int
    var status: Int


@fieldwise_init
struct FlashPlan(Copyable, Movable):
    """Chosen key-block size and what it implies about memory."""

    var block_k: Int
    var n_blocks: Int
    var working_bytes: Int
    var materialized_bytes: Float64
    var status: Int


@fieldwise_init
struct FlashAgreement(Copyable, Movable):
    """How far the tiled kernel is from the materialized one, and how far it is allowed to be."""

    var max_out_delta: Float64
    var max_lse_delta: Float64
    var tolerance_at_max: Float64
    var within_tolerance: Bool
    var n_compared: Int
    var status: Int


def flash_block_plan(s_k: Int, d: Int, cache_bytes: Int) -> FlashPlan:
    """Pick a key-block size, and report what the materialized form would have cost.

    `materialized_bytes` is returned as Float64 because at long context it exceeds `Int` — which is
    itself the argument for this kernel existing.

    @capability flash_block_plan
    complexity: O(1)
    @endcapability
    """
    if s_k <= 0 or d <= 0 or cache_bytes <= 0:
        return FlashPlan(0, 0, 0, 0.0, ATTN_ERR_LENGTH_MISMATCH)
    # K and V tiles plus one output accumulator row, all Float64.
    var per_key = 2 * 8 * d
    var block = cache_bytes // per_key if per_key > 0 else FLASH_DEFAULT_BLOCK_K
    if block < 1:
        block = 1
    if block > s_k:
        block = s_k
    if block > 4096:
        block = 4096
    var n_blocks = (s_k + block - 1) // block
    var materialized = 8.0 * Float64(s_k) * Float64(s_k)
    return FlashPlan(block, n_blocks, block * per_key, materialized, ATTN_OK)


def flash_forward_flat(
    q: List[Float64], k: List[Float64], v: List[Float64], bias: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int,
    scale: Float64, use_bias: Bool, block_k: Int
) -> FlashOut:
    """Attention over K/V in blocks of `block_k`, carrying `(m, l, o)` per query row.

    Peak extra memory is `O(d)` per query row and independent of `n_tok_k`, which is the entire
    difference from `sdpa_forward_flat`. Every step of the recurrence is a frozen kernel call.

    @capability flash_forward_flat
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
        return FlashOut(out^, lse^, 0, 0, 0, 0, shape)
    if not attn_scalars_ok(scale):
        return FlashOut(out^, lse^, 0, 0, 0, 0, ATTN_ERR_NON_FINITE_SCALAR)
    if len(q) < n_tok_q * h_q * d or len(k) < n_tok_k * h_kv * d or len(v) < n_tok_k * h_kv * d:
        return FlashOut(out^, lse^, 0, 0, 0, 0, ATTN_ERR_LENGTH_MISMATCH)
    if use_bias and len(bias) < n_tok_q * n_tok_k:
        return FlashOut(out^, lse^, 0, 0, 0, 0, ATTN_ERR_LENGTH_MISMATCH)

    var bk = block_k if block_k > 0 else FLASH_DEFAULT_BLOCK_K
    if bk > n_tok_k:
        bk = n_tok_k

    var group = h_q // h_kv
    var qp = q.unsafe_ptr()
    var kp = k.unsafe_ptr()
    var vp = v.unsafe_ptr()

    for _ in range(n_tok_q * h_q * d):
        out.append(0.0)
    for _ in range(h_q * n_tok_q):
        lse.append(0.0)
    var op = out.unsafe_ptr()

    # The whole per-row state: one accumulator row plus two scalars. Never s_k-sized.
    var acc = List[Float64](capacity=d)
    for _ in range(d):
        acc.append(0.0)
    var ap = acc.unsafe_ptr()

    var blocks_walked = 0

    for h in range(h_q):
        var hk = h // group
        for i in range(n_tok_q):
            var qbase = (i * h_q + h) * d
            var m = FLASH_NEG_SENTINEL
            var l = 0.0
            for e in range(d):
                ap[e] = 0.0

            var j0 = 0
            while j0 < n_tok_k:
                var j_hi = j0 + bk
                if j_hi > n_tok_k:
                    j_hi = n_tok_k
                blocks_walked += 1

                for j in range(j0, j_hi):
                    var kbase = (j * h_kv + hk) * d
                    var dot = 0.0
                    for e in range(d):
                        dot += qp[qbase + e] * kp[kbase + e]
                    var s = dot * scale if scale > 0.0 else scaled_dot_product_attention(dot, Float64(d))
                    if use_bias:
                        s += bias[i * n_tok_k + j]

                    # Frozen recurrence, in the only order that is correct: m_new first as a value,
                    # then BOTH consumers of (m_old, m_new), then advance m.
                    var m_new = flash_block_max(m, s)
                    var w = mexp(s - m_new)
                    var vbase = (j * h_kv + hk) * d
                    for e in range(d):
                        ap[e] = flash_block_output(ap[e], m, m_new, w, vp[vbase + e])
                    l = flash_block_sum_exp(l, m, m_new, s)
                    m = m_new

                j0 += bk

            var obase = (i * h_q + h) * d
            for e in range(d):
                op[obase + e] = flash_final_normalize(ap[e], l)
            lse[h * n_tok_q + i] = m + mlog(l) if l > 0.0 else FLASH_NEG_SENTINEL

    return FlashOut(out^, lse^, n_tok_q, h_q, d, blocks_walked, ATTN_OK)


def flash_agrees_with_sdpa(
    q: List[Float64], k: List[Float64], v: List[Float64], bias: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int,
    scale: Float64, use_bias: Bool, block_k: Int
) -> FlashAgreement:
    """Compare the tiled kernel against the materialized reference, output and lse.

    The claim this module makes is "same answer, no score matrix". This is the half a test can check.

    Not exact equality: the online form accumulates in a different order and rescales as it goes, so
    it differs from a single-pass softmax in the last bits. The bound is built from each row's own
    magnitude via `dtx_tol_for`, scaled by the reduction length — not from a max over the output,
    which is rule 4b spelling 2.

    Both `out` and `lse` are compared, and the lse is the sharper of the two: it depends on every
    score in the row, whereas the output is a weighted average in which two compensating errors can
    cancel.

    @capability flash_agrees_with_sdpa
    complexity: O(h_q * n_tok_q * n_tok_k * d)
    counts:
    - n_tok_q * h_q * d <= len(q) [enforced]
    - n_tok_k * h_kv * d <= len(k, v) [enforced]
    @endcapability
    """
    var reference = sdpa_forward_flat(
        q, k, v, bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale, use_bias
    )
    if reference.status != ATTN_OK:
        return FlashAgreement(0.0, 0.0, 0.0, False, 0, reference.status)
    var tiled = flash_forward_flat(
        q, k, v, bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale, use_bias, block_k
    )
    if tiled.status != ATTN_OK:
        return FlashAgreement(0.0, 0.0, 0.0, False, 0, tiled.status)
    if len(tiled.out) != len(reference.out) or len(tiled.lse) != len(reference.lse):
        return FlashAgreement(0.0, 0.0, 0.0, False, 0, ATTN_ERR_LENGTH_MISMATCH)

    var worst_out = 0.0
    var worst_tol = 0.0
    var within = True
    for idx in range(len(reference.out)):
        var want = reference.out[idx]
        var got = tiled.out[idx]
        var diff = got - want
        if diff < 0.0:
            diff = -diff
        var tol = dtx_tol_for(want, DT_F64, 1.0e-300)
        var allowed = tol.relative_term * Float64(n_tok_k) * 8.0 + 1.0e-12
        if diff > allowed:
            within = False
        if diff > worst_out:
            worst_out = diff
            worst_tol = allowed

    var worst_lse = 0.0
    for idx in range(len(reference.lse)):
        var want = reference.lse[idx]
        if want <= FLASH_NEG_SENTINEL * 0.5:
            continue
        var diff = tiled.lse[idx] - want
        if diff < 0.0:
            diff = -diff
        var tol = dtx_tol_for(want, DT_F64, 1.0e-300)
        if diff > tol.relative_term * Float64(n_tok_k) * 8.0 + 1.0e-12:
            within = False
        if diff > worst_lse:
            worst_lse = diff

    return FlashAgreement(worst_out, worst_lse, worst_tol, within, len(reference.out), ATTN_OK)
