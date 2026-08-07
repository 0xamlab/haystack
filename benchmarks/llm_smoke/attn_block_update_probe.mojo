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

from std.math import exp as mexp, log as mlog, sqrt
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


def _to_f16_grid(x: List[Float64]) -> List[Float64]:
    """Simulates F16 storage narrowing (Attention Compiler Plan v1.0, Phase 0B's own "F16-in/
    F32-state" extension) without a real Float16 dependency in this host-only file: rounds each
    value to the nearest multiple of its own F16 ULP. This is not bit-exact IEEE754 F16 rounding,
    but it reproduces the property that matters for this check -- real, bounded precision loss
    proportional to magnitude -- which is what the block-combined recurrence's running STATE
    (kept Float64 here, standing in for Float32 in the real kernel) must tolerate."""
    var out = List[Float64](capacity=len(x))
    for i in range(len(x)):
        var v = x[i]
        var av = v if v >= 0.0 else -v
        if av < 1.0e-12:
            out.append(0.0)
            continue
        # F16 has 10 mantissa bits -> ULP is roughly value / 1024, rounded to the nearest step.
        var scale = 1024.0
        var exp_adjust = 1.0
        while av * exp_adjust >= 2.0:
            exp_adjust *= 0.5
        while av * exp_adjust < 1.0:
            exp_adjust *= 2.0
        var step = 1.0 / (scale * exp_adjust)
        var rounded = Float64(Int(v / step + (0.5 if v >= 0.0 else -0.5))) * step
        out.append(rounded)
    return out^


def _run_case_f16_precision(
    name: String, n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int, block_k: Int
) raises -> Bool:
    """Phase 0B extension: F16-narrowed Q/K/V (running state stays Float64, standing in for the
    real kernel's Float32 accumulator) vs. the full-Float64 combined recurrence. This is the host-
    side proof that the precision contract Phase 1/4 plan to use (F16 storage, F32 state) doesn't
    need a wider tolerance than plain F16 rounding alone already implies -- if this failed, the
    recurrence itself (not just storage narrowing) would be amplifying error, which would be a
    reason to reconsider the algorithm, not just the dtype."""
    var q64 = _pseudo(n_tok_q * h_q * d, 3)
    var k64 = _pseudo(n_tok_k * h_kv * d, 11)
    var v64 = _pseudo(n_tok_k * h_kv * d, 29)
    var q16 = _to_f16_grid(q64)
    var k16 = _to_f16_grid(k64)
    var v16 = _to_f16_grid(v64)

    var cm = mask_causal_flat(n_tok_q, n_tok_k, offset)
    if cm.status != ATTN_OK:
        print("  [", name, "] mask build FAILED")
        return False

    var ref64 = block_combined_forward_flat(q64, k64, v64, cm.bias, n_tok_q, n_tok_k, h_q, h_kv, d, -1.0, True, block_k)
    var ref16 = block_combined_forward_flat(q16, k16, v16, cm.bias, n_tok_q, n_tok_k, h_q, h_kv, d, -1.0, True, block_k)
    if ref64.status != ATTN_OK or ref16.status != ATTN_OK:
        print("  [", name, "] a reference FAILED")
        return False

    var worst = 0.0
    for i in range(len(ref64.out)):
        var diff = ref16.out[i] - ref64.out[i]
        if diff < 0.0:
            diff = -diff
        if diff > worst:
            worst = diff
    # F16 has ~3 decimal digits of precision; a bound of 1e-2 absolute is generous for pseudo-data
    # in the O(1) range this probe uses, and would clearly fail if the recurrence amplified error
    # rather than merely inheriting F16's own rounding.
    var ok = worst <= 1.0e-2
    print("  [", name, "] F16-in/F64-state worst abs delta vs full-F64=", worst, "  ", "OK" if ok else "MISMATCH")
    return ok


def _run_case_h_tile_equivalence(
    name: String, n_tok_q: Int, n_tok_k: Int, h_kv: Int, d: Int, offset: Int, block_k: Int
) raises -> Bool:
    """Phase 0B extension: H_TILE is a compute-ORGANIZATION choice (process a GQA-sibling pair of
    query heads together, sharing one K/V load) -- it must never change the per-head answer. This
    verifies head h and its sibling h+1 (both mapping to the same KV head under group size 2)
    give IDENTICAL results whether computed via one h_q=2*h_kv call (H_TILE=2, "paired") or two
    independent h_q=1*h_kv... calls run separately and compared head-by-head (H_TILE=1, "per-
    head"). `block_combined_forward_flat` has no cross-head coupling in its own math, so this is
    really a check that slicing its output by head after a PAIRED call agrees with running it
    TWICE with only one sibling present each time -- exactly the invariant Phase 2's real kernel
    reshape (h_q * ceil(m/8) -> h_kv * ceil(m/8), H_TILE query heads per shared K/V load) depends
    on being true before any GPU code is written."""
    var group = 2
    var h_q_paired = h_kv * group
    var q_paired = _pseudo(n_tok_q * h_q_paired * d, 3)
    var k = _pseudo(n_tok_k * h_kv * d, 11)
    var v = _pseudo(n_tok_k * h_kv * d, 29)
    var cm = mask_causal_flat(n_tok_q, n_tok_k, offset)
    if cm.status != ATTN_OK:
        print("  [", name, "] mask build FAILED")
        return False

    var paired = block_combined_forward_flat(q_paired, k, v, cm.bias, n_tok_q, n_tok_k, h_q_paired, h_kv, d, -1.0, True, block_k)
    if paired.status != ATTN_OK:
        print("  [", name, "] paired (H_TILE=2) reference FAILED")
        return False

    var worst = 0.0
    for h in range(h_q_paired):
        # Extract head h's own Q slice, AND its one owning KV head's K/V slice, and run it alone
        # (H_TILE=1: one head per KV load, per-head dispatch) -- q_paired is
        # [n_tok_q, h_q_paired, d] row-major; k/v are [n_tok_k, h_kv, d] row-major. Passing the
        # FULL k/v with h_kv=h_kv here (instead of slicing to the one owning head) would make
        # `group = h_q // h_kv = 1 // h_kv = 0` inside block_combined_forward_flat and divide by
        # zero computing `hk`, silently reading garbage through its unsafe K/V pointers rather
        # than trapping -- caught by this very check reporting a large, real mismatch.
        var hk_owner = h // group
        var q_solo = List[Float64](capacity=n_tok_q * d)
        for i in range(n_tok_q):
            for e in range(d):
                q_solo.append(q_paired[(i * h_q_paired + h) * d + e])
        var k_solo = List[Float64](capacity=n_tok_k * d)
        var v_solo = List[Float64](capacity=n_tok_k * d)
        for j in range(n_tok_k):
            for e in range(d):
                k_solo.append(k[(j * h_kv + hk_owner) * d + e])
                v_solo.append(v[(j * h_kv + hk_owner) * d + e])
        var solo = block_combined_forward_flat(q_solo, k_solo, v_solo, cm.bias, n_tok_q, n_tok_k, 1, 1, d, -1.0, True, block_k)
        if solo.status != ATTN_OK:
            print("  [", name, "] solo (H_TILE=1) reference FAILED for head", h)
            return False
        for i in range(n_tok_q):
            for e in range(d):
                var diff = solo.out[i * d + e] - paired.out[(i * h_q_paired + h) * d + e]
                if diff < 0.0:
                    diff = -diff
                if diff > worst:
                    worst = diff

    var ok = worst <= 1.0e-9
    print("  [", name, "] H_TILE=2 (paired) vs H_TILE=1 (per-head) worst abs delta=", worst, "  ", "OK" if ok else "MISMATCH")
    return ok


def _run_case_split_merge(
    name: String, n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int, block_k: Int, n_splits: Int
) raises -> Bool:
    """Phase 0B extension: the associative online-softmax merge identity Candidate C (associative
    split-K FlashAttention) depends on -- `m = max(m_s); l = sum(l_s * exp(m_s - m)); o = sum(o_s
    * exp(m_s - m)); O = o / l` -- verified here by splitting the KEY range into `n_splits` chunks,
    running `block_combined_forward_flat` independently on EACH chunk (each chunk's own "full"
    result, before final normalization, IS a valid partial state: `flash_final_normalize` divides
    by `l`, so the pre-division accumulator and lse-implied `l` together are exactly `(o_s, l_s,
    m_s)`), merging them via the identity above, and comparing against the single-pass combined
    result over the WHOLE key range. This is the same merge math this repo's decode-side split-K
    already ships in production, now verified for the block-combined recurrence specifically."""
    var q = _pseudo(n_tok_q * h_q * d, 3)
    var k = _pseudo(n_tok_k * h_kv * d, 11)
    var v = _pseudo(n_tok_k * h_kv * d, 29)
    var cm = mask_causal_flat(n_tok_q, n_tok_k, offset)
    if cm.status != ATTN_OK:
        print("  [", name, "] mask build FAILED")
        return False

    var whole = block_combined_forward_flat(q, k, v, cm.bias, n_tok_q, n_tok_k, h_q, h_kv, d, -1.0, True, block_k)
    if whole.status != ATTN_OK:
        print("  [", name, "] whole-range reference FAILED")
        return False

    # Merge each split's own (m_s, l_s, o_s) via the associative identity, per (head, row).
    var group = h_q // h_kv
    var merged_out = List[Float64](capacity=len(whole.out))
    for _ in range(len(whole.out)):
        merged_out.append(0.0)
    var worst = 0.0

    for h in range(h_q):
        var hk = h // group
        for qi in range(n_tok_q):
            var n_keys_visible = offset + qi + 1
            if n_keys_visible > n_tok_k:
                n_keys_visible = n_tok_k
            var m_merged = _NEG_SENTINEL
            var l_merged = 0.0
            var o_merged = List[Float64](capacity=d)
            for _ in range(d):
                o_merged.append(0.0)

            var split_size = (n_keys_visible + n_splits - 1) // n_splits
            if split_size < 1:
                split_size = 1
            var j0 = 0
            while j0 < n_keys_visible:
                var j1 = j0 + split_size
                if j1 > n_keys_visible:
                    j1 = n_keys_visible
                var chunk_k = j1 - j0
                # Slice this split's own K/V range for head hk, rows [j0, j1).
                var k_chunk = List[Float64](capacity=chunk_k * d)
                var v_chunk = List[Float64](capacity=chunk_k * d)
                for j in range(j0, j1):
                    for e in range(d):
                        k_chunk.append(k[(j * h_kv + hk) * d + e])
                        v_chunk.append(v[(j * h_kv + hk) * d + e])
                var q_row = List[Float64](capacity=d)
                for e in range(d):
                    q_row.append(q[(qi * h_q + h) * d + e])
                # No causal mask needed here: this split's own [j0,j1) range is already known to be
                # entirely within this row's visible-key window (n_keys_visible), so every key in
                # the chunk is valid -- an empty (all-False) bias, not mask_causal_flat again.
                var empty_bias = List[Float64]()
                var part = block_combined_forward_flat(
                    q_row, k_chunk, v_chunk, empty_bias, 1, chunk_k, 1, 1, d, -1.0, False, block_k
                )
                if part.status != ATTN_OK:
                    print("  [", name, "] split-chunk reference FAILED")
                    return False
                # Recover this chunk's own (m_s, l_s) from its block_combined_forward_flat result:
                # lse = m_s + log(l_s), and m_s is independently exactly the chunk's own max raw
                # score (recomputed directly, since a single-head, single-chunk, no-mask call's
                # running max IS the max over its own scores) -- avoids solving the lse identity
                # for two unknowns from one equation.
                var m_s2 = _NEG_SENTINEL
                for j in range(chunk_k):
                    var dot = 0.0
                    for e in range(d):
                        dot += q_row[e] * k_chunk[j * d + e]
                    var s = dot * (1.0 / sqrt(Float64(d)))
                    if s > m_s2:
                        m_s2 = s
                var l_s = mexp(part.lse[0] - m_s2)
                var nm = m_merged if m_merged > m_s2 else m_s2
                var corr_old = mexp(m_merged - nm)
                var corr_new = mexp(m_s2 - nm)
                l_merged = l_merged * corr_old + l_s * corr_new
                for e in range(d):
                    var o_s_e = part.out[e] * l_s  # undo flash_final_normalize's own division
                    o_merged[e] = o_merged[e] * corr_old + o_s_e * corr_new
                m_merged = nm
                j0 = j1

            for e in range(d):
                var val = o_merged[e] / l_merged if l_merged > 0.0 else 0.0
                merged_out[(qi * h_q + h) * d + e] = val
                var diff = val - whole.out[(qi * h_q + h) * d + e]
                if diff < 0.0:
                    diff = -diff
                if diff > worst:
                    worst = diff

    var ok = worst <= 1.0e-9
    print(
        "  [", name, "] split-merge (n_splits=", n_splits, ") vs single-pass whole-range worst abs delta=",
        worst, "  ", "OK" if ok else "MISMATCH",
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
    print("=== Phase 0B extensions: KEY_TILE sweep, H_TILE equivalence, F16 precision, split-merge ===")
    print("")

    print("--- KEY_TILE sweep at real dims, fixed shape ---")
    for key_tile in [8, 16, 32, 64, 128]:
        all_ok = _run_case("key_tile=" + String(key_tile), 17, 130, 16, 8, 128, -1.0, 37, key_tile) and all_ok

    print("")
    print("--- H_TILE=2 (paired GQA-sibling heads) vs H_TILE=1 (per-head) equivalence ---")
    all_ok = _run_case_h_tile_equivalence("h_tile aligned", 16, 64, 8, 128, 0, 8) and all_ok
    all_ok = _run_case_h_tile_equivalence("h_tile mid-block cutoff", 10, 37, 4, 64, 5, 8) and all_ok

    print("")
    print("--- F16-narrowed Q/K/V vs full-Float64 (state stays wide, matching the F32-state plan) ---")
    all_ok = _run_case_f16_precision("f16 real dims", 17, 53, 16, 8, 128, 37, 8) and all_ok
    all_ok = _run_case_f16_precision("f16 ragged", 12, 37, 2, 1, 8, 0, 8) and all_ok

    print("")
    print("--- associative split-state merge vs single-pass whole-range ---")
    all_ok = _run_case_split_merge("split2 real dims", 17, 53, 16, 8, 128, 37, 8, 2) and all_ok
    all_ok = _run_case_split_merge("split4 real dims", 17, 130, 16, 8, 128, 37, 8, 4) and all_ok
    all_ok = _run_case_split_merge("split3 ragged", 12, 37, 2, 1, 8, 0, 8, 3) and all_ok

    print("")
    if all_ok:
        print("ALL CASES OK: block-combined update (one rescale per block of 8) agrees with both the")
        print("materialized reference and the already-proven per-key tiled reference. Phase 0 cleared --")
        print("Phase 1 (GPU scalar block-of-8 kernel) can proceed on this exact recurrence.")
    else:
        print("MISMATCH: the block-combined recurrence does not agree. Do not proceed to Phase 1.")
