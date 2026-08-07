"""attention_forge.splitk_fa_driver -- forces codegen of Candidate C's two kernels
(`_attn_splitk_partial_kernel`, `_attn_splitk_merge_kernel`, see `splitk_fa.mojo`'s own docstring)
and checks them FIVE ways, matching this repo's own established forge-native pattern
(`parity_replica_driver.mojo`, `grouped_fa_q8_k32_h2_sg8_driver.mojo`):

**PHASE 2B ADAPTATION.** `_attn_splitk_partial_kernel` now consumes K/V in the native packed
layout (`attention_forge/native_kv_producer.mojo`'s own layout, see `splitk_fa.mojo`'s "PHASE 2B
ADAPTATION" docstring section for the exact flat-index formulas) instead of a natural
`[position][kv_head][d_head]` buffer, so every test below that used to upload `k64`/`v64` straight
into a natural-layout device buffer now packs them FIRST via `_pack_native_kv` -- a hand-written
(NOT calling into `native_kv_producer.mojo`, per this task's own instruction not to touch that
file) restatement of the exact same flat-index formulas, so this driver's own buffer construction
is an INDEPENDENT re-derivation of the packing convention, not a shared dependency that could hide
a matching bug on both sides. Every existing correctness/isolation/determinism case below is
otherwise UNCHANGED (same shapes, same pseudo-random seeds, same tolerances, same oracles) --
Phase 2B changed how K/V are CONSUMED, not the attention math itself, so every case still checks
the exact same numerical result, just fed through the new layout. `test_hand_packed_buffer` (new,
item 0 below) is the dedicated case this task asked for: it builds a small packed K/V buffer via
literal, explicitly-restated flat indices (not even routed through the shared `_pack_native_kv`
helper) and includes a few hand-verified index assertions in the style of `native_kv_producer_
driver.mojo`'s own `test_packing_hand_indices`, before running the full partial+merge pipeline
against `attnk.sdpa.sdpa_forward_flat` -- genuine end-to-end confidence that isn't just "this
driver's helper agrees with itself."

  0. `test_hand_packed_buffer` -- see above.
  1. `test_partial_isolation` -- Candidate C's own correctness requirement (a): each partial-kernel
     dispatch produces a correct UNNORMALIZED partial state `(m_s, l_s, o_s)` for its own key
     sub-range in ISOLATION -- compared against a DIRECT (no online-softmax, no tiling) Float64
     host computation of exactly that sub-range's own contribution, including the same per-row
     causal check the GPU kernel applies (`gk < n_tok_k and gk <= pos_base + row0 + row`). Genuinely
     empty splits (`n_splits` exceeding the visible-key count) are checked against the exact
     `(m=_NEG_SENTINEL, l=0, o=0)` contract, not skipped. This host reference is per INDIVIDUAL head
     `h` (never per pair), so it is unaffected by the H_TILE=2 correction below -- only the GPU
     dispatch's own grid shape (now `(q_block, pair_idx, split)`, `pair_idx` over `h_q // 2`) needed
     updating.
  2. `test_correctness` -- requirement (b): the FULL two-kernel pipeline (partial dispatch for
     every split, then the merge dispatch) against `attnk.sdpa.sdpa_forward_flat` -- the same
     TRUSTED materialized single-pass whole-range reference `parity_replica_driver.mojo` itself
     checks against, and the SAME associative-merge identity `attn_block_update_probe.mojo`'s own
     `_run_case_split_merge` already proved on the CPU, now reproduced on two real GPU dispatches.
     Q/K/V are narrowed to Float16 FIRST, then that SAME narrowed value (widened back to Float64)
     is what both the CPU oracle and the isolation reference in (1) consume, isolating any mismatch
     to the kernels' own math rather than F16 storage precision.
  3. `test_pair_grid_isolation` -- the H_TILE=2 correction's own isolation requirement: a sibling
     pair processed as part of a multi-pair grid must give IDENTICAL per-head partial states (after
     merge) to that SAME pair processed alone. There is no surviving H_TILE=1 code path in
     `splitk_fa.mojo` to compare against (the corrected kernel always processes pairs) -- so, exactly
     like `grouped_fa_q8_k32_h2_sg8_driver.mojo`'s own `test_h_tile_pairing_isolation`, this instead
     dispatches the IDENTICAL corrected kernel twice: once across a multi-pair grid, once across a
     grid with only ONE pair and a K/V buffer sliced to ONLY that pair's own owning KV head (never
     the full multi-head buffer with a mismatched head-count argument -- the exact pitfall
     `attn_block_update_probe.mojo`'s own `_run_case_h_tile_equivalence` docstring warns about, and
     which this driver's own earlier `test_correctness`/`test_partial_isolation` avoid the same way
     by never slicing at all). Both runs execute the SAME kernel on the SAME per-pair data, so this
     uses a near-exact tolerance, not the CPU oracle's looser one -- proving no cross-pair state
     leakage and no grid-size-dependent indexing bug in the corrected `pair_idx`/`hh`/`sg_local`
     decode.
  4. A 1,000-dispatch determinism soak (partial + merge, both re-dispatched every iteration) at the
     real-Qwen3-dims shape (this plan's own non-negotiable stop rule: never assume a new kernel is
     deterministic without checking).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge -I ../mojo/engine ../attention_forge/splitk_fa_driver.mojo
"""
from max.gpu.host import DeviceContext
from std.math import exp as mexp
from attnk.contract import ATTN_OK
from attnk.mask import mask_causal_flat
from attnk.sdpa import sdpa_forward_flat
from splitk_fa import _attn_splitk_partial_kernel, _attn_splitk_merge_kernel


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f16(n: Int, seed: Int) -> List[Float64]:
    """Same deterministic generator convention as `parity_replica_driver.mojo`'s own
    `_pseudo_f16` (itself derived from `attn_block_update_probe.mojo`'s `_pseudo`), immediately
    narrowed to Float16 and widened back -- the value both the CPU oracle and the GPU kernels will
    actually consume, so F16 storage precision is a controlled input, not a source of unattributed
    mismatch. Duplicated locally rather than imported (this repo's own established precedent --
    `parity_replica_driver.mojo`'s docstring makes the same choice relative to `attn_block_update_
    probe.mojo`) to keep this driver self-contained and to avoid force-compiling `parity_replica.mojo`
    /`mm8.mojo` as a side effect of importing their driver."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float16(raw)))
    return o^


def _n_blocks_for(n_tok_k: Int) -> Int:
    """`ceil(n_tok_k / 32)` -- `32` is this candidate's own `_KT`, byte-identical to
    `native_kv_producer.mojo`'s own `key_block_size` (see `splitk_fa.mojo`'s "PHASE 2B ADAPTATION"
    docstring section: this is not a coincidence, it is the whole reason a native block is directly
    consumable without reconciling two different tile sizes). Every block this kernel's own
    `block_hi = (key_end-1)//32` bound can ever reach is `< _n_blocks_for(n_tok_k)`, since
    `key_end <= n_keys_block <= n_tok_k` always -- so a packed buffer sized with this many blocks
    per `kv_head` is always large enough, never read out of bounds."""
    return (n_tok_k + 31) // 32


def _pack_native_kv(natural64: List[Float64], n_tok_k: Int, h_kv: Int, d: Int, n_blocks: Int, is_k: Bool) -> List[Float64]:
    """Hand-packs a NATURAL `[position][kv_head][d_head]` pseudo-random buffer (`natural64`, the
    SAME array both `test_correctness`'s CPU oracle and `test_partial_isolation`'s own direct host
    computation already consume) into the Phase 2B native layout `splitk_fa.mojo`'s
    `_attn_splitk_partial_kernel` now reads -- restated here independently of
    `native_kv_producer.mojo` (never imported, per this task's own instruction not to touch that
    file), so this driver's own construction of its test inputs is a SECOND, independent
    re-derivation of the packing convention this task's ground-truth report specifies, not a
    shared dependency with the kernel or the producer that could hide a matching bug on both sides:

      K: `((hk*n_blocks+block)*d + dd)*32 + kk`  -- `[kv_head][key_block][d_chunk][key_in_block]`
      V: `((hk*n_blocks+block)*32+kk)*d + dd`     -- `[kv_head][key_block][key_in_block][d_chunk]`

    `block = j // 32`, `kk = j % 32` for real key position `j` in `[0, n_tok_k)`. Positions beyond
    `n_tok_k` within a block's own 32-wide span (a block only partially filled by real tokens) are
    left at `0.0` -- never read by the kernel (masked out by `gk < n_tok_k` before use), so their
    exact value is immaterial; `0.0` merely keeps this helper simple, it is not a correctness
    requirement the kernel depends on."""
    var kbs = 32
    var size = h_kv * n_blocks * d * kbs
    var out = List[Float64](capacity=size)
    for _ in range(size):
        out.append(0.0)
    for j in range(n_tok_k):
        var block = j // kbs
        var kk = j % kbs
        for hk in range(h_kv):
            for dd in range(d):
                var src = (j * h_kv + hk) * d + dd
                if is_k:
                    var dst = ((hk * n_blocks + block) * d + dd) * kbs + kk
                    out[dst] = natural64[src]
                else:
                    var dst = ((hk * n_blocks + block) * kbs + kk) * d + dd
                    out[dst] = natural64[src]
    return out^


def test_partial_isolation(
    ctx: DeviceContext, name: String,
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int, n_splits: Int,
) raises -> Bool:
    """Requirement (a): compares every `(row, head, split)` partial written by ONE dispatch of
    `_attn_splitk_partial_kernel` against a direct Float64 host computation of exactly that split's
    own key sub-range -- no online-softmax recurrence, no tiling, just "sum over the keys this split
    owns, masked exactly as the GPU kernel masks them". Uses the SAME block-level `key_start`/
    `key_end` partition formula the kernel itself uses (re-derived here, not imported, so this is an
    independent check of the kernel's own arithmetic, not a tautology)."""
    if d != 128:
        print("  [", name, "] SKIPPED: this candidate is specialized to d_qk=d_v=128 (Qwen3-0.6B-Base)")
        return True
    if h_q % 2 != 0:
        print("  [", name, "] SKIPPED: H_TILE=2 requires an even h_q (one sibling pair per KV head)")
        return True

    var q64 = _pseudo_f16(n_tok_q * h_q * d, 3)
    var k64 = _pseudo_f16(n_tok_k * h_kv * d, 11)
    var v64 = _pseudo_f16(n_tok_k * h_kv * d, 29)

    var n_blocks = _n_blocks_for(n_tok_k)
    var k_native64 = _pack_native_kv(k64, n_tok_k, h_kv, d, n_blocks, True)
    var v_native64 = _pack_native_kv(v64, n_tok_k, h_kv, d, n_blocks, False)

    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d * 32)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * 32 * d)
    with q_buf.map_to_host() as hbuf:
        for i in range(n_tok_q * h_q * d):
            hbuf[i] = Float16(q64[i])
    with k_buf.map_to_host() as hbuf:
        for i in range(h_kv * n_blocks * d * 32):
            hbuf[i] = Float16(k_native64[i])
    with v_buf.map_to_host() as hbuf:
        for i in range(h_kv * n_blocks * 32 * d):
            hbuf[i] = Float16(v_native64[i])

    var n_q_blocks = (n_tok_q + 7) // 8
    var m_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits)
    var l_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits)
    var o_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits * d)

    var scale = 1.0 / Float64(d) ** 0.5
    var n_pairs = h_q // 2
    var grid_partial = n_q_blocks * n_pairs * n_splits
    ctx.enqueue_function[_attn_splitk_partial_kernel](
        m_scratch.unsafe_ptr(), l_scratch.unsafe_ptr(), o_scratch.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
        Float32(scale), Int64(offset), Int64(n_splits), Int64(n_blocks),
        grid_dim=grid_partial, block_dim=256,
    )
    ctx.synchronize()

    var m_host = List[Float64](capacity=n_tok_q * h_q * n_splits)
    var l_host = List[Float64](capacity=n_tok_q * h_q * n_splits)
    var o_host = List[Float64](capacity=n_tok_q * h_q * n_splits * d)
    with m_scratch.map_to_host() as hh:
        for i in range(n_tok_q * h_q * n_splits):
            m_host.append(Float64(hh[i]))
    with l_scratch.map_to_host() as hh:
        for i in range(n_tok_q * h_q * n_splits):
            l_host.append(Float64(hh[i]))
    with o_scratch.map_to_host() as hh:
        for i in range(n_tok_q * h_q * n_splits * d):
            o_host.append(Float64(hh[i]))

    var group = h_q // h_kv
    var worst = 0.0
    var contract_violations = 0

    for qb in range(n_q_blocks):
        var row0 = qb * 8
        var q_hi = offset + row0 + 7
        var kv_upper = (n_tok_k - 1) if (n_tok_k - 1 < q_hi) else q_hi
        var n_keys_block = kv_upper + 1
        if n_keys_block < 0:
            n_keys_block = 0

        for h in range(h_q):
            var hk = h // group

            for s in range(n_splits):
                var key_start = (n_keys_block * s) // n_splits
                var key_end = (n_keys_block * (s + 1)) // n_splits

                for r in range(8):
                    var gi = row0 + r
                    if gi >= n_tok_q:
                        continue
                    var qpos = offset + gi

                    var m_s = -3.0e38
                    for j in range(key_start, key_end):
                        if j < n_tok_k and j <= qpos:
                            var dot = 0.0
                            for e in range(d):
                                dot += q64[(gi * h_q + h) * d + e] * k64[(j * h_kv + hk) * d + e]
                            var sc = dot * scale
                            if sc > m_s:
                                m_s = sc

                    var l_s = 0.0
                    var o_s = List[Float64](capacity=d)
                    for _ in range(d):
                        o_s.append(0.0)
                    for j in range(key_start, key_end):
                        if j < n_tok_k and j <= qpos:
                            var dot = 0.0
                            for e in range(d):
                                dot += q64[(gi * h_q + h) * d + e] * k64[(j * h_kv + hk) * d + e]
                            var sc = dot * scale
                            var w = mexp(sc - m_s)
                            l_s += w
                            for e in range(d):
                                o_s[e] = o_s[e] + w * v64[(j * h_kv + hk) * d + e]

                    var pidx = (gi * h_q + h) * n_splits + s
                    var got_m = m_host[pidx]
                    var got_l = l_host[pidx]

                    if l_s == 0.0:
                        # Genuinely empty split: `l` must be EXACTLY 0.0 (its untouched initial
                        # value, representable exactly in both Float32 and Float64) and `m` must
                        # still be sentinel-negative -- but NOT compared for exact equality against
                        # the Float64 literal `-3.0e38`: the kernel's `_NEG_SENTINEL` is a Float32
                        # constant, and Float32's own nearest-representable rounding of the decimal
                        # `-3.0e38` is `-3.0000000054977558e+38` once widened to Float64, which is
                        # NOT bit-equal to the independently-rounded Float64 literal `-3.0e38` --
                        # confirmed by direct probe, not assumed. A loose bound (well past any real
                        # attention score) is the correct check here, not bit-exact equality.
                        if got_l != 0.0 or got_m > -1.0e30:
                            contract_violations += 1
                    else:
                        var diff_l = _abs64(got_l - l_s)
                        var allowed_l = 5.0e-2 * (1.0 + _abs64(l_s))
                        var ratio_l = diff_l / allowed_l
                        if ratio_l > worst:
                            worst = ratio_l
                        for e in range(d):
                            var got_o = o_host[pidx * d + e]
                            var want_o = o_s[e]
                            var diff_o = _abs64(got_o - want_o)
                            var allowed_o = 5.0e-2 * (1.0 + _abs64(want_o))
                            var ratio_o = diff_o / allowed_o
                            if ratio_o > worst:
                                worst = ratio_o

    var ok = worst <= 1.0 and contract_violations == 0
    print(
        "  [", name, "] partial-isolation (n_splits=", n_splits, ") worst-ratio=", worst,
        " empty-split-contract-violations=", contract_violations, "  ", "OK" if ok else "MISMATCH",
    )
    return ok


def test_correctness(
    ctx: DeviceContext, name: String,
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int, n_splits: Int,
) raises -> Bool:
    """Requirement (b): the full partial-dispatch + merge-dispatch pipeline vs. `attnk.sdpa.
    sdpa_forward_flat` (single-pass whole-range materialized reference)."""
    if d != 128:
        print("  [", name, "] SKIPPED: this candidate is specialized to d_qk=d_v=128 (Qwen3-0.6B-Base)")
        return True
    if h_q % 2 != 0:
        print("  [", name, "] SKIPPED: H_TILE=2 requires an even h_q (one sibling pair per KV head)")
        return True

    var q64 = _pseudo_f16(n_tok_q * h_q * d, 3)
    var k64 = _pseudo_f16(n_tok_k * h_kv * d, 11)
    var v64 = _pseudo_f16(n_tok_k * h_kv * d, 29)

    var cm = mask_causal_flat(n_tok_q, n_tok_k, offset)
    if cm.status != ATTN_OK:
        print("  [", name, "] mask build FAILED")
        return False

    var scale = 1.0 / Float64(d) ** 0.5
    var oracle = sdpa_forward_flat(q64, k64, v64, cm.bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale, True)
    if oracle.status != ATTN_OK:
        print("  [", name, "] oracle FAILED, status=", oracle.status)
        return False

    var n_blocks = _n_blocks_for(n_tok_k)
    var k_native64 = _pack_native_kv(k64, n_tok_k, h_kv, d, n_blocks, True)
    var v_native64 = _pack_native_kv(v64, n_tok_k, h_kv, d, n_blocks, False)

    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d * 32)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * 32 * d)
    with q_buf.map_to_host() as hbuf:
        for i in range(n_tok_q * h_q * d):
            hbuf[i] = Float16(q64[i])
    with k_buf.map_to_host() as hbuf:
        for i in range(h_kv * n_blocks * d * 32):
            hbuf[i] = Float16(k_native64[i])
    with v_buf.map_to_host() as hbuf:
        for i in range(h_kv * n_blocks * 32 * d):
            hbuf[i] = Float16(v_native64[i])

    var n_q_blocks = (n_tok_q + 7) // 8
    var m_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits)
    var l_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits)
    var o_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits * d)
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    with out_buf.map_to_host() as hbuf:
        for i in range(n_tok_q * h_q * d):
            hbuf[i] = Float32(-999.0)  # canary: must be fully overwritten for every valid row

    var n_pairs = h_q // 2
    var grid_partial = n_q_blocks * n_pairs * n_splits
    ctx.enqueue_function[_attn_splitk_partial_kernel](
        m_scratch.unsafe_ptr(), l_scratch.unsafe_ptr(), o_scratch.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
        Float32(scale), Int64(offset), Int64(n_splits), Int64(n_blocks),
        grid_dim=grid_partial, block_dim=256,
    )
    ctx.synchronize()

    var grid_merge = n_tok_q * h_q
    ctx.enqueue_function[_attn_splitk_merge_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        m_scratch.unsafe_ptr(), l_scratch.unsafe_ptr(), o_scratch.unsafe_ptr(),
        Int64(n_tok_q), Int64(h_q), Int64(n_splits),
        grid_dim=grid_merge, block_dim=128,
    )
    ctx.synchronize()

    var worst_out = 0.0
    var worst_lse = 0.0
    with out_buf.map_to_host() as ho:
        for i in range(n_tok_q * h_q * d):
            var got = Float64(ho[i])
            var want = oracle.out[i]
            var diff = _abs64(got - want)
            var allowed = 5.0e-2 * (1.0 + _abs64(want))
            var ratio = diff / allowed
            if ratio > worst_out:
                worst_out = ratio
    with lse_buf.map_to_host() as hl:
        for i in range(h_q * n_tok_q):
            var got = Float64(hl[i])
            var want = oracle.lse[i]
            var diff = _abs64(got - want)
            var allowed = 5.0e-2 * (1.0 + _abs64(want))
            var ratio = diff / allowed
            if ratio > worst_lse:
                worst_lse = ratio

    var ok = worst_out <= 1.0 and worst_lse <= 1.0
    print(
        "  [", name, "] full pipeline (n_splits=", n_splits, ") worst-ratio out=", worst_out,
        " lse=", worst_lse, "  ", "OK" if ok else "MISMATCH",
    )
    return ok


def test_pair_grid_isolation(
    ctx: DeviceContext, name: String, n_tok_q: Int, n_tok_k: Int, h_kv: Int, offset: Int, n_splits: Int,
) raises -> Bool:
    """H_TILE=2 (paired) vs. solo-pair grid-independence -- see module docstring item 3, and
    `grouped_fa_q8_k32_h2_sg8_driver.mojo`'s own `test_h_tile_pairing_isolation`, which this mirrors
    as closely as this candidate's two-kernel (partial + merge) pipeline allows. `splitk_fa.mojo`'s
    corrected kernel never had, and does not now have, an H_TILE=1 mode to compare against -- every
    dispatch processes a sibling pair -- so "isolation" here means: run the FULL partial+merge
    pipeline once across a multi-pair grid (`h_kv` sibling pairs sharing one grid), and once more per
    pair ALONE (a grid with exactly one pair, `h_q=2, h_kv=1`, fed ONLY that pair's own owning KV
    head's K/V slice -- never the full multi-head buffer with a mismatched head-count argument, the
    exact pitfall `attn_block_update_probe.mojo`'s own `_run_case_h_tile_equivalence` docstring
    warns about). Both runs execute the IDENTICAL kernel code on IDENTICAL per-pair data with
    IDENTICAL K_TILE tiling and IDENTICAL split partitioning (`key_start`/`key_end` depend only on
    `row0`/`n_tok_k`/`offset`/`n_splits`, not on grid size or pair count) -- so this uses a
    near-exact tolerance, not the CPU oracle's looser one; any deviation at all is a real
    cross-pair-leakage or grid-indexing bug, not floating-point tiling-order noise."""
    var d = 128
    var h_q_paired = h_kv * 2
    var q64 = _pseudo_f16(n_tok_q * h_q_paired * d, 3)
    var k64 = _pseudo_f16(n_tok_k * h_kv * d, 11)
    var v64 = _pseudo_f16(n_tok_k * h_kv * d, 29)
    var scale = 1.0 / Float64(d) ** 0.5
    var n_q_blocks = (n_tok_q + 7) // 8
    var n_blocks = _n_blocks_for(n_tok_k)

    # --- paired run: every sibling pair sharing this dispatch's grid ---
    var k_native64 = _pack_native_kv(k64, n_tok_k, h_kv, d, n_blocks, True)
    var v_native64 = _pack_native_kv(v64, n_tok_k, h_kv, d, n_blocks, False)
    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q_paired * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d * 32)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * 32 * d)
    with q_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q_paired * d):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * d * 32):
            h[i] = Float16(k_native64[i])
    with v_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * 32 * d):
            h[i] = Float16(v_native64[i])

    var m_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q_paired * n_splits)
    var l_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q_paired * n_splits)
    var o_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q_paired * n_splits * d)
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q_paired * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q_paired * n_tok_q)

    var grid_partial_paired = n_q_blocks * h_kv * n_splits
    ctx.enqueue_function[_attn_splitk_partial_kernel](
        m_scratch.unsafe_ptr(), l_scratch.unsafe_ptr(), o_scratch.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q_paired), Int64(h_kv),
        Float32(scale), Int64(offset), Int64(n_splits), Int64(n_blocks),
        grid_dim=grid_partial_paired, block_dim=256,
    )
    ctx.synchronize()

    var grid_merge_paired = n_tok_q * h_q_paired
    ctx.enqueue_function[_attn_splitk_merge_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        m_scratch.unsafe_ptr(), l_scratch.unsafe_ptr(), o_scratch.unsafe_ptr(),
        Int64(n_tok_q), Int64(h_q_paired), Int64(n_splits),
        grid_dim=grid_merge_paired, block_dim=128,
    )
    ctx.synchronize()

    var out_paired = List[Float32](capacity=n_tok_q * h_q_paired * d)
    with out_buf.map_to_host() as ho:
        for i in range(n_tok_q * h_q_paired * d):
            out_paired.append(ho[i])
    var lse_paired = List[Float32](capacity=h_q_paired * n_tok_q)
    with lse_buf.map_to_host() as hl:
        for i in range(h_q_paired * n_tok_q):
            lse_paired.append(hl[i])

    var worst_out = 0.0
    var worst_lse = 0.0
    for pair_idx in range(h_kv):
        var h0 = pair_idx * 2
        var h1 = h0 + 1

        # Slice out ONLY this pair's own two Q heads and ONLY its own owning KV head -- never the
        # full multi-head buffer with a mismatched head-count argument.
        var q_solo = List[Float64](capacity=n_tok_q * 2 * d)
        for i in range(n_tok_q):
            for hh in range(2):
                var h = h0 if hh == 0 else h1
                for e in range(d):
                    q_solo.append(q64[(i * h_q_paired + h) * d + e])
        var k_solo = List[Float64](capacity=n_tok_k * d)
        var v_solo = List[Float64](capacity=n_tok_k * d)
        for j in range(n_tok_k):
            for e in range(d):
                k_solo.append(k64[(j * h_kv + pair_idx) * d + e])
                v_solo.append(v64[(j * h_kv + pair_idx) * d + e])

        var k_solo_native64 = _pack_native_kv(k_solo, n_tok_k, 1, d, n_blocks, True)
        var v_solo_native64 = _pack_native_kv(v_solo, n_tok_k, 1, d, n_blocks, False)

        var qs_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * 2 * d)
        var ks_buf = ctx.enqueue_create_buffer[DType.float16](n_blocks * d * 32)
        var vs_buf = ctx.enqueue_create_buffer[DType.float16](n_blocks * 32 * d)
        with qs_buf.map_to_host() as h:
            for i in range(n_tok_q * 2 * d):
                h[i] = Float16(q_solo[i])
        with ks_buf.map_to_host() as h:
            for j in range(n_blocks * d * 32):
                h[j] = Float16(k_solo_native64[j])
        with vs_buf.map_to_host() as h:
            for j in range(n_blocks * 32 * d):
                h[j] = Float16(v_solo_native64[j])

        var ms_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * 2 * n_splits)
        var ls_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * 2 * n_splits)
        var os_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * 2 * n_splits * d)
        var outs_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * 2 * d)
        var lses_buf = ctx.enqueue_create_buffer[DType.float32](2 * n_tok_q)

        var grid_partial_solo = n_q_blocks * 1 * n_splits
        ctx.enqueue_function[_attn_splitk_partial_kernel](
            ms_scratch.unsafe_ptr(), ls_scratch.unsafe_ptr(), os_scratch.unsafe_ptr(),
            qs_buf.unsafe_ptr(), ks_buf.unsafe_ptr(), vs_buf.unsafe_ptr(),
            Int64(n_tok_q), Int64(n_tok_k), Int64(2), Int64(1),
            Float32(scale), Int64(offset), Int64(n_splits), Int64(n_blocks),
            grid_dim=grid_partial_solo, block_dim=256,
        )
        ctx.synchronize()

        var grid_merge_solo = n_tok_q * 2
        ctx.enqueue_function[_attn_splitk_merge_kernel](
            outs_buf.unsafe_ptr(), lses_buf.unsafe_ptr(),
            ms_scratch.unsafe_ptr(), ls_scratch.unsafe_ptr(), os_scratch.unsafe_ptr(),
            Int64(n_tok_q), Int64(2), Int64(n_splits),
            grid_dim=grid_merge_solo, block_dim=128,
        )
        ctx.synchronize()

        with outs_buf.map_to_host() as ho:
            for i in range(n_tok_q):
                for hh in range(2):
                    var h = h0 if hh == 0 else h1
                    for e in range(d):
                        var got = ho[(i * 2 + hh) * d + e]
                        var want = out_paired[(i * h_q_paired + h) * d + e]
                        var diff = Float64(_abs64(Float64(got) - Float64(want)))
                        if diff > worst_out:
                            worst_out = diff
        with lses_buf.map_to_host() as hl:
            for i in range(n_tok_q):
                for hh in range(2):
                    var h = h0 if hh == 0 else h1
                    var got = hl[hh * n_tok_q + i]
                    var want = lse_paired[h * n_tok_q + i]
                    var diff = Float64(_abs64(Float64(got) - Float64(want)))
                    if diff > worst_lse:
                        worst_lse = diff

    var ok = worst_out <= 1.0e-4 and worst_lse <= 1.0e-4
    print(
        "  [", name, "] paired-grid vs. solo-pair-grid worst abs delta: out=", worst_out,
        " lse=", worst_lse, "  ", "OK" if ok else "MISMATCH",
    )
    return ok


def test_determinism_soak(
    ctx: DeviceContext, n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int,
    n_splits: Int, n_runs: Int,
) raises -> Bool:
    var q64 = _pseudo_f16(n_tok_q * h_q * d, 3)
    var k64 = _pseudo_f16(n_tok_k * h_kv * d, 11)
    var v64 = _pseudo_f16(n_tok_k * h_kv * d, 29)

    var n_blocks = _n_blocks_for(n_tok_k)
    var k_native64 = _pack_native_kv(k64, n_tok_k, h_kv, d, n_blocks, True)
    var v_native64 = _pack_native_kv(v64, n_tok_k, h_kv, d, n_blocks, False)

    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d * 32)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * 32 * d)
    with q_buf.map_to_host() as hbuf:
        for i in range(n_tok_q * h_q * d):
            hbuf[i] = Float16(q64[i])
    with k_buf.map_to_host() as hbuf:
        for i in range(h_kv * n_blocks * d * 32):
            hbuf[i] = Float16(k_native64[i])
    with v_buf.map_to_host() as hbuf:
        for i in range(h_kv * n_blocks * 32 * d):
            hbuf[i] = Float16(v_native64[i])

    var scale = 1.0 / Float64(d) ** 0.5
    var n_q_blocks = (n_tok_q + 7) // 8
    var n_pairs = h_q // 2
    var grid_partial = n_q_blocks * n_pairs * n_splits
    var grid_merge = n_tok_q * h_q

    var first_out = List[Float32](capacity=n_tok_q * h_q * d)
    var first_lse = List[Float32](capacity=h_q * n_tok_q)
    var worst_flip = 0

    for run in range(n_runs):
        var m_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits)
        var l_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits)
        var o_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits * d)
        var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
        var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)

        ctx.enqueue_function[_attn_splitk_partial_kernel](
            m_scratch.unsafe_ptr(), l_scratch.unsafe_ptr(), o_scratch.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
            Float32(scale), Int64(offset), Int64(n_splits), Int64(n_blocks),
            grid_dim=grid_partial, block_dim=256,
        )
        ctx.enqueue_function[_attn_splitk_merge_kernel](
            out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
            m_scratch.unsafe_ptr(), l_scratch.unsafe_ptr(), o_scratch.unsafe_ptr(),
            Int64(n_tok_q), Int64(h_q), Int64(n_splits),
            grid_dim=grid_merge, block_dim=128,
        )
        ctx.synchronize()

        with out_buf.map_to_host() as ho:
            if run == 0:
                for i in range(n_tok_q * h_q * d):
                    first_out.append(ho[i])
            else:
                for i in range(n_tok_q * h_q * d):
                    if ho[i] != first_out[i]:
                        worst_flip += 1
        with lse_buf.map_to_host() as hl:
            if run == 0:
                for i in range(h_q * n_tok_q):
                    first_lse.append(hl[i])
            else:
                for i in range(h_q * n_tok_q):
                    if hl[i] != first_lse[i]:
                        worst_flip += 1

    var ok = worst_flip == 0
    print(
        "  determinism soak: n_runs=", n_runs, " mismatching-element-dispatches=", worst_flip,
        "  ", "OK" if ok else "NONDETERMINISTIC",
    )
    return ok


def test_hand_packed_buffer(ctx: DeviceContext) raises -> Bool:
    """The dedicated case this task asked for: builds a small packed K/V buffer via LITERAL,
    explicitly-restated flat indices -- not even routed through this file's own shared
    `_pack_native_kv` helper (used by every OTHER test in this driver) -- then runs the full
    partial+merge pipeline against `attnk.sdpa.sdpa_forward_flat`, exactly like `test_correctness`
    does, but starting from a buffer THIS function itself hand-assembled. `n_tok_k=40` spans native
    block 0 (`[0,32)`) and block 1 (`[32,40)`); `offset=30` with `n_tok_q=3` gives row 2 (absolute
    position 32) a causal horizon landing exactly on the 31/32 block boundary; `n_splits=2` gives
    split 1 a `key_start=19` that is NOT a multiple of 32, so split 1's own native-block walk
    touches BOTH native blocks even though its own key range starts mid-block-0 -- exactly the case
    this task's own `gk >= key_start` guard (see `splitk_fa.mojo`) exists for. A handful of
    (position, d) -> literal flat-index spot checks (mirroring `native_kv_producer_driver.mojo`'s
    own `test_packing_hand_indices` style) are verified BEFORE this buffer is ever uploaded to the
    GPU."""
    var h_q = 2
    var h_kv = 1
    var d = 128
    var n_tok_q = 3
    var n_tok_k = 40
    var offset = 30
    var n_splits = 2
    var n_blocks = 2  # ceil(40/32) restated literally here, not via `_n_blocks_for`, on purpose

    var q64 = _pseudo_f16(n_tok_q * h_q * d, 3)
    var k64 = _pseudo_f16(n_tok_k * h_kv * d, 11)
    var v64 = _pseudo_f16(n_tok_k * h_kv * d, 29)

    # Hand-packing: a literal loop restating the flat-index formulas directly (K:
    # `((hk*n_blocks+block)*d+dd)*32+kk`, V: `((hk*n_blocks+block)*32+kk)*d+dd`, `hk=0` always since
    # `h_kv=1` here) -- deliberately NOT calling `_pack_native_kv`.
    var k_native = List[Float64](capacity=h_kv * n_blocks * d * 32)
    for _ in range(h_kv * n_blocks * d * 32):
        k_native.append(0.0)
    var v_native = List[Float64](capacity=h_kv * n_blocks * 32 * d)
    for _ in range(h_kv * n_blocks * 32 * d):
        v_native.append(0.0)
    for j in range(n_tok_k):
        var block = j // 32
        var kk = j % 32
        for dd in range(d):
            var src = j * d + dd  # h_kv=1, so the natural-layout source collapses to j*d+dd
            k_native[(block * d + dd) * 32 + kk] = k64[src]
            v_native[(block * 32 + kk) * d + dd] = v64[src]

    var idx_ok = True
    # position 31 (last slot of block 0), d=0: block=0, kk=31 -> k_flat=(0*128+0)*32+31=31
    if k_native[31] != k64[31 * d + 0]:
        idx_ok = False
    # position 32 (first slot of block 1), d=0: block=1, kk=0 -> k_flat=(1*128+0)*32+0=4096
    if k_native[4096] != k64[32 * d + 0]:
        idx_ok = False
    # position 39 (last real key), d=127: block=1, kk=7 -> k_flat=(1*128+127)*32+7=8167
    if k_native[8167] != k64[39 * d + 127]:
        idx_ok = False
    # V, position 32, d=0: block=1, kk=0 -> v_flat=(1*32+0)*128+0=4096
    if v_native[4096] != v64[32 * d + 0]:
        idx_ok = False
    print("  [hand-packed sanity] literal (position,d)->flat-index spot checks  ", "OK" if idx_ok else "MISMATCH")

    var cm = mask_causal_flat(n_tok_q, n_tok_k, offset)
    if cm.status != ATTN_OK:
        print("  [hand-packed buffer] mask build FAILED")
        return False
    var scale = 1.0 / Float64(d) ** 0.5
    var oracle = sdpa_forward_flat(q64, k64, v64, cm.bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale, True)
    if oracle.status != ATTN_OK:
        print("  [hand-packed buffer] oracle FAILED, status=", oracle.status)
        return False

    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d * 32)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * 32 * d)
    with q_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * d * 32):
            h[i] = Float16(k_native[i])
    with v_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * 32 * d):
            h[i] = Float16(v_native[i])

    var n_q_blocks = (n_tok_q + 7) // 8
    var m_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits)
    var l_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits)
    var o_scratch = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits * d)
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)

    var n_pairs = h_q // 2
    var grid_partial = n_q_blocks * n_pairs * n_splits
    ctx.enqueue_function[_attn_splitk_partial_kernel](
        m_scratch.unsafe_ptr(), l_scratch.unsafe_ptr(), o_scratch.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
        Float32(scale), Int64(offset), Int64(n_splits), Int64(n_blocks),
        grid_dim=grid_partial, block_dim=256,
    )
    ctx.synchronize()

    var grid_merge = n_tok_q * h_q
    ctx.enqueue_function[_attn_splitk_merge_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        m_scratch.unsafe_ptr(), l_scratch.unsafe_ptr(), o_scratch.unsafe_ptr(),
        Int64(n_tok_q), Int64(h_q), Int64(n_splits),
        grid_dim=grid_merge, block_dim=128,
    )
    ctx.synchronize()

    var worst_out = 0.0
    var worst_lse = 0.0
    with out_buf.map_to_host() as ho:
        for i in range(n_tok_q * h_q * d):
            var got = Float64(ho[i])
            var want = oracle.out[i]
            var diff = _abs64(got - want)
            var allowed = 5.0e-2 * (1.0 + _abs64(want))
            var ratio = diff / allowed
            if ratio > worst_out:
                worst_out = ratio
    with lse_buf.map_to_host() as hl:
        for i in range(h_q * n_tok_q):
            var got = Float64(hl[i])
            var want = oracle.lse[i]
            var diff = _abs64(got - want)
            var allowed = 5.0e-2 * (1.0 + _abs64(want))
            var ratio = diff / allowed
            if ratio > worst_lse:
                worst_lse = ratio

    var ok = idx_ok and worst_out <= 1.0 and worst_lse <= 1.0
    print(
        "  [hand-packed buffer, n_tok_k=40 spanning block 0/1, split key_start=19 mid-block] worst-ratio out=", worst_out,
        " lse=", worst_lse, "  ", "OK" if ok else "MISMATCH",
    )
    return ok


def main() raises:
    var ctx = DeviceContext()
    var all_ok = True

    print("=== Candidate C: hand-packed native K/V buffer, built without _pack_native_kv (item 0) ===")
    all_ok = test_hand_packed_buffer(ctx) and all_ok

    print("")
    print("=== Candidate C (associative split-K FlashAttention): partial-isolation (requirement a) ===")
    all_ok = test_partial_isolation(ctx, "tiny aligned s2", 8, 64, 2, 1, 128, 0, 2) and all_ok
    all_ok = test_partial_isolation(ctx, "tiny ragged K s2", 8, 37, 2, 1, 128, 0, 2) and all_ok
    all_ok = test_partial_isolation(ctx, "two q-blocks offset s2", 16, 96, 2, 1, 128, 13, 2) and all_ok
    all_ok = test_partial_isolation(ctx, "real Qwen3 dims s2", 17, 130, 16, 8, 128, 37, 2) and all_ok
    all_ok = test_partial_isolation(ctx, "real Qwen3 dims s4", 17, 130, 16, 8, 128, 37, 4) and all_ok
    all_ok = test_partial_isolation(ctx, "256-token prefill s2", 256, 256, 16, 8, 128, 0, 2) and all_ok
    all_ok = test_partial_isolation(ctx, "many-empty-splits s4", 8, 1, 2, 1, 128, 0, 4) and all_ok

    print("")
    print("=== Candidate C: full pipeline vs attnk.sdpa (requirement b) ===")
    all_ok = test_correctness(ctx, "tiny aligned s2", 8, 64, 2, 1, 128, 0, 2) and all_ok
    all_ok = test_correctness(ctx, "tiny ragged K s2", 8, 37, 2, 1, 128, 0, 2) and all_ok
    all_ok = test_correctness(ctx, "two q-blocks offset s2", 16, 96, 2, 1, 128, 13, 2) and all_ok
    all_ok = test_correctness(ctx, "real Qwen3-0.6B-Base dims, m=17 offset=37, s2", 17, 130, 16, 8, 128, 37, 2) and all_ok
    all_ok = test_correctness(ctx, "real dims s4", 17, 130, 16, 8, 128, 37, 4) and all_ok
    all_ok = test_correctness(ctx, "real dims s3 (non-power-of-2)", 17, 130, 16, 8, 128, 37, 3) and all_ok
    all_ok = test_correctness(ctx, "real dims, 256-token single-shot prefill, s2", 256, 256, 16, 8, 128, 0, 2) and all_ok
    all_ok = test_correctness(ctx, "many-empty-splits s4", 8, 1, 2, 1, 128, 0, 4) and all_ok

    print("")
    print("=== H_TILE=2 (paired) vs. solo-pair grid-independence ===")
    all_ok = test_pair_grid_isolation(ctx, "pair-grid aligned s2", 16, 64, 8, 0, 2) and all_ok
    all_ok = test_pair_grid_isolation(ctx, "pair-grid mid-block cutoff, ragged, offset, s3", 10, 37, 4, 5, 3) and all_ok
    all_ok = test_pair_grid_isolation(ctx, "pair-grid real dims s4", 17, 130, 8, 37, 4) and all_ok

    print("")
    print("=== 1,000-dispatch determinism soak (real dims, offset=37, n_splits=2) ===")
    all_ok = test_determinism_soak(ctx, 17, 130, 16, 8, 128, 37, 2, 1000) and all_ok

    print("")
    if all_ok:
        print("CANDIDATE C (SPLIT-K FLASHATTENTION, H_TILE=2, PHASE 2B NATIVE-KV-LAYOUT ADAPTED): PASS (hand-packed buffer correct, partial-isolation correct, full pipeline correct vs CPU oracle, paired-grid==solo-pair-grid, deterministic over 1,000 dispatches)")
    else:
        print("CANDIDATE C (SPLIT-K FLASHATTENTION, H_TILE=2, PHASE 2B NATIVE-KV-LAYOUT ADAPTED): FAIL")
