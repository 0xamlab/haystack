"""attn_block_update_probe.mojo — does a GENUINE block-combined online-softmax update (one
rescale per block of `block_k` keys, not one per key) compute the same answer as the trusted
per-key reference? Phase 0 of the tiled-MMA-attention plan: pure host Float64, no GPU, no
toolchain risk — the cheapest place to catch a masking/rescaling bug before any kernel is written.

Hand-written, throwaway measurement (not registered in `generate_mojo_tests.py`), exactly like
`sdpa_simd_reduce_probe.mojo` before it: a probe for a design decision, not a golden-vector suite.
Run with the pinned toolchain, no GPU flag needed:

    cd mojo_env && pixi run mojo run -I ../mojo/engine ../benchmarks/llm_smoke/attn_block_update_probe.mojo

Why this needs its own reference, when `attnk.flash` already exists and is proven
----------------------------------------------------------------------------------
`attnk.flash.flash_forward_flat` already walks K/V in blocks of `block_k` — but reading its inner
loop shows the blocking is a LOOP-TILING boundary only: inside each block it still calls
`flash_block_max`/`flash_block_sum_exp`/`flash_block_output` once PER KEY, rescaling the (m, l, o)
accumulator that many times. That is why its own golden vectors can prove "bit-identical across
block sizes 1, 7, 64" almost for free: the actual arithmetic performed is IDENTICAL regardless of
`block_k`, only the re-chunking of the same scalar loop changes.

The planned GPU kernel (`_pf_attn_tiled_kernel_simd` redesign, Phase 1) wants something stronger:
compute all `block_k` scores for a block, take ONE block max, rescale the accumulator ONCE, then
sum the block's weighted contributions in a single pass — one rescale per block of 8 instead of
eight. That is a real algorithmic difference (fewer rescales, different floating-point summation
order), not just a loop restructuring, and it is NOT what the existing golden vectors exercise.
This probe implements it and checks it against two independent trusted computations: the
materialized reference (`attnk.sdpa.sdpa_forward_flat`) and the already-proven tiled reference
(`attnk.flash.flash_forward_flat`), output AND log-sum-exp (the sharper check — see both modules'
own docstrings on why lse catches what a weighted-average output can hide).

`flash_block_max` is reused for the one honest per-block operation it actually performs correctly
either way: `max(m_old, x)` for any `x`, including a block's own pre-computed max. The rest of the
block update (single rescale, single pass of weighted-sum) is new arithmetic, spelled out directly
rather than forced through the single-key frozen functions, because chaining THOSE per key within
a block would silently re-derive `flash_forward_flat`'s own form (multiple rescales), not the
thing being tested.

Edge cases exercised, matching the plan's own stated risk (causality is the added complexity vs.
the GEMM work): a causal cutoff falling strictly inside a block rather than on a block boundary; a
key count not a multiple of the block size (ragged last block); a single block where some query
rows see almost nothing and others see everything (within-block masking variance); and a shape
using the real Qwen3-0.6B-Base `d_head=128`/`h_q=16`/`h_kv=8` with a non-8-aligned query-tile size
and a nonzero KV-cache offset, matching a real decode-continuation prefill call.
"""

from std.math import exp as mexp, log as mlog
from attnk.contract import ATTN_OK
from attnk.flash import FlashOut, flash_forward_flat
from attnk.mask import mask_causal_flat
from attnk.sdpa import sdpa_forward_flat
from flash_attention import flash_block_max, flash_final_normalize
from tensorx.dtype import DT_F64, dtx_tol_for
from transformer_attention import scaled_dot_product_attention

comptime _NEG_SENTINEL: Float64 = -1.0e308


def block_combined_forward_flat(
    q: List[Float64], k: List[Float64], v: List[Float64], bias: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int,
    scale: Float64, use_bias: Bool, block_k: Int
) -> FlashOut:
    """The candidate: one (m, l, o) rescale per block of `block_k` keys, not one per key.

    Same public shape as `flash_forward_flat` so the two can be diffed field-for-field."""
    var out = List[Float64]()
    var lse = List[Float64]()
    if n_tok_q <= 0 or n_tok_k <= 0 or h_q <= 0 or h_kv <= 0 or d <= 0 or block_k <= 0:
        return FlashOut(out^, lse^, 0, 0, 0, 0, ATTN_OK)

    var group = h_q // h_kv
    var qp = q.unsafe_ptr()
    var kp = k.unsafe_ptr()
    var vp = v.unsafe_ptr()

    for _ in range(n_tok_q * h_q * d):
        out.append(0.0)
    for _ in range(h_q * n_tok_q):
        lse.append(0.0)
    var op = out.unsafe_ptr()

    var block_scores = List[Float64](capacity=block_k)
    for _ in range(block_k):
        block_scores.append(0.0)
    var acc = List[Float64](capacity=d)
    for _ in range(d):
        acc.append(0.0)
    var ap = acc.unsafe_ptr()

    var blocks_walked = 0

    for h in range(h_q):
        var hk = h // group
        for i in range(n_tok_q):
            var qbase = (i * h_q + h) * d
            var m = _NEG_SENTINEL
            var l = 0.0
            for e in range(d):
                ap[e] = 0.0

            var j0 = 0
            while j0 < n_tok_k:
                var j_hi = j0 + block_k
                if j_hi > n_tok_k:
                    j_hi = n_tok_k
                blocks_walked += 1
                var nb = j_hi - j0

                # Pass 1: every score in this block, and this block's own local max.
                var block_max_raw = _NEG_SENTINEL
                for jj in range(nb):
                    var j = j0 + jj
                    var kbase = (j * h_kv + hk) * d
                    var dot = 0.0
                    for e in range(d):
                        dot += qp[qbase + e] * kp[kbase + e]
                    var s = dot * scale if scale > 0.0 else scaled_dot_product_attention(dot, Float64(d))
                    if use_bias:
                        s += bias[i * n_tok_k + j]
                    block_scores[jj] = s
                    if s > block_max_raw:
                        block_max_raw = s

                # ONE rescale decision for the whole block -- the thing being tested.
                var m_new = flash_block_max(m, block_max_raw)
                var corr = mexp(m - m_new)
                for e in range(d):
                    ap[e] = ap[e] * corr
                var block_sum = 0.0
                for jj in range(nb):
                    var j = j0 + jj
                    var w = mexp(block_scores[jj] - m_new)
                    block_sum += w
                    var vbase = (j * h_kv + hk) * d
                    for e in range(d):
                        ap[e] += w * vp[vbase + e]
                l = l * corr + block_sum
                m = m_new

                j0 += block_k

            var obase = (i * h_q + h) * d
            for e in range(d):
                op[obase + e] = flash_final_normalize(ap[e], l)
            lse[h * n_tok_q + i] = m + mlog(l) if l > 0.0 else _NEG_SENTINEL

    return FlashOut(out^, lse^, n_tok_q, h_q, d, blocks_walked, ATTN_OK)


def _pseudo(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2)
    return o^


def _worst_deltas(
    a: List[Float64], b: List[Float64], n_tok_k: Int
) -> Float64:
    """Same tolerance bound `flash_agrees_with_sdpa` uses: per-element, scaled by reduction length."""
    var worst = 0.0
    for idx in range(len(a)):
        var want = a[idx]
        var got = b[idx]
        var diff = got - want
        if diff < 0.0:
            diff = -diff
        var tol = dtx_tol_for(want, DT_F64, 1.0e-300)
        var allowed = tol.relative_term * Float64(n_tok_k) * 8.0 + 1.0e-12
        var ratio = diff / allowed if allowed > 0.0 else diff
        if ratio > worst:
            worst = ratio
    return worst


def _run_case(
    name: String,
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int,
    scale: Float64, offset: Int, block_k: Int
) raises -> Bool:
    var q = _pseudo(n_tok_q * h_q * d, 3)
    var k = _pseudo(n_tok_k * h_kv * d, 11)
    var v = _pseudo(n_tok_k * h_kv * d, 29)
    var cm = mask_causal_flat(n_tok_q, n_tok_k, offset)
    if cm.status != ATTN_OK:
        print("  [", name, "] mask build FAILED, status=", cm.status)
        return False

    var sdpa_ref = sdpa_forward_flat(q, k, v, cm.bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale, True)
    var tiled = flash_forward_flat(q, k, v, cm.bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale, True, block_k)
    var combined = block_combined_forward_flat(q, k, v, cm.bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale, True, block_k)

    if sdpa_ref.status != ATTN_OK or tiled.status != ATTN_OK or combined.status != ATTN_OK:
        print("  [", name, "] a reference FAILED: sdpa=", sdpa_ref.status, "flash=", tiled.status, "combined=", combined.status)
        return False

    var d_out_vs_sdpa = _worst_deltas(sdpa_ref.out, combined.out, n_tok_k)
    var d_lse_vs_sdpa = _worst_deltas(sdpa_ref.lse, combined.lse, n_tok_k)
    var d_out_vs_flash = _worst_deltas(tiled.out, combined.out, n_tok_k)
    var d_lse_vs_flash = _worst_deltas(tiled.lse, combined.lse, n_tok_k)

    var ok = d_out_vs_sdpa <= 1.0 and d_lse_vs_sdpa <= 1.0 and d_out_vs_flash <= 1.0 and d_lse_vs_flash <= 1.0
    print(
        "  [", name, "] n_masked=", cm.n_masked, "/", n_tok_q * n_tok_k,
        " blocks_walked(combined vs flash)=", combined.blocks_walked, "/", tiled.blocks_walked,
        "  worst-ratio out/lse vs sdpa=", d_out_vs_sdpa, "/", d_lse_vs_sdpa,
        "  vs flash=", d_out_vs_flash, "/", d_lse_vs_flash,
        "  ", "OK" if ok else "MISMATCH",
    )
    return ok


def main() raises:
    print("=== Phase 0: block-combined (one rescale per block of 8) vs per-key online softmax ===")
    print("")

    var all_ok = True

    print("--- control: aligned, no causal edge tension ---")
    all_ok = _run_case("aligned 8x64 d=8", 8, 64, 2, 1, 8, -1.0, 0, 8) and all_ok

    print("--- causal cutoff strictly inside a block (not on a block boundary) ---")
    all_ok = _run_case("mid-block cutoff", 10, 20, 2, 1, 8, -1.0, 5, 8) and all_ok

    print("--- n_tok_k not a multiple of block_k (ragged last block) ---")
    all_ok = _run_case("ragged tail 37 keys", 12, 37, 2, 1, 8, -1.0, 0, 8) and all_ok

    print("--- single block, extreme within-block masking variance (row 0 sees 1 key, row 7 sees 8) ---")
    all_ok = _run_case("within-block variance", 8, 8, 2, 1, 8, -1.0, 0, 8) and all_ok

    print("--- real Qwen3-0.6B-Base dims: d=128, h_q=16, h_kv=8 (GQA g=2), non-8-aligned tile, offset ---")
    all_ok = _run_case("real dims m=17 offset=37", 17, 53, 16, 8, 128, -1.0, 37, 8) and all_ok

    print("")
    if all_ok:
        print("ALL CASES OK: block-combined update (one rescale per block of 8) agrees with both the")
        print("materialized reference and the already-proven per-key tiled reference. Phase 0 cleared --")
        print("Phase 1 (GPU scalar block-of-8 kernel) can proceed on this exact recurrence.")
    else:
        print("MISMATCH: the block-combined recurrence does not agree. Do not proceed to Phase 1.")
