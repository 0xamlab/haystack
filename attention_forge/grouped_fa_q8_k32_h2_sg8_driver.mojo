"""attention_forge.grouped_fa_q8_k32_h2_sg8_driver -- correctness driver for CANDIDATE A
(`grouped_fa_q8_k32_h2_sg8.mojo`; see that file's own docstring for the exact shape shipped and
why), matching this repo's established forge-native pattern
(`attention_forge.parity_replica_driver`, `mma_forge/probes/correctness_probe_partial.mojo`).

NATIVE PACKED KV LAYOUT (Phase 2B wiring): the kernel under test no longer reads K/V from a
natural `[position][kv_head][d_head]` device buffer -- it now reads
`attention_forge.abi.KV_LAYOUT_NATIVE_PACKED_V2`-shaped buffers (see that kernel's own module
docstring). This driver's own `_pack_k_native`/`_pack_v_native` (below) re-lay-out this same
file's already-established `_pseudo_f16` natural-layout test vectors into that packed layout
BEFORE upload, using the SAME flat-index formula `native_kv_producer.mojo` writes
(`((hk*n_blocks+block)*128+d)*32+kk` for K, `((hk*n_blocks+block)*32+kk)*128+d` for V,
`block=gk//32`, `kk=gk%32`) -- restated independently here, not imported, per this repo's own
established driver convention of not depending on another phase's internals. Every existing
correctness/pairing-isolation/determinism check below now packs its K/V before upload and is
otherwise UNCHANGED, including its comparison against `sdpa_forward_flat`'s own natural-layout
oracle -- that oracle never sees the packed representation, so any packing-formula bug (in this
driver) OR any layout-consumption bug (in the kernel) still shows up as a mismatch against ground
truth, not a self-consistent false pass. A NEW check (#2 below) additionally hand-builds a packed
buffer using a SEPARATE, inline restatement of the same formula (not routed through the shared
`_pack_k_native`/`_pack_v_native` helpers), so the packing formula itself is exercised by two
independent implementations, not just the one every other test shares.

Four checks:

  1. **Correctness against `attnk.sdpa.sdpa_forward_flat`** (the same trusted materialized
     reference `parity_replica_driver.mojo` itself checks against) at a sweep of shapes: tiny
     aligned, ragged K, nonzero causal offset (KV-cache continuation), real Qwen3-0.6B-Base dims,
     and a full 256-token single-shot prefill. Because the CPU oracle computes every query head's
     output FULLY INDEPENDENTLY (its own GQA head mapping has zero cross-head coupling), a
     per-head match against it already rules out any cross-head contamination bug in this
     candidate's shared-K/V-tile pairing -- a bug that leaked head-0 data into head-1's output (or
     vice versa) would show up here as a mismatch against a reference that never mixes them.
  2. **H_TILE=2 (paired) vs. solo-pair grid-independence**, the check this candidate's own task
     spec calls out by name, built the way `attn_block_update_probe.mojo`'s own
     `_run_case_h_tile_equivalence` is built EXCEPT adapted to this candidate's actual
     architecture: this kernel has no "H_TILE=1" mode at all (K/V-tile sharing between two sibling
     heads is baked into every dispatch, not a toggle), so the operationally meaningful analogue
     of "paired vs. per-head" is "one pair processed as part of a multi-pair grid" vs. "that SAME
     pair processed alone, with every OTHER pair removed from the grid AND from the K/V buffer
     entirely" -- proving no cross-block state leakage and no grid-size-dependent indexing bug.
     Guards explicitly against the exact pitfall that function's own docstring warns about: the
     solo call is given ONLY its own owning KV head's data, sliced out row-by-row -- never the
     full multi-head K/V buffer with a mismatched head-count argument (which would silently
     compute `group = h_q // h_kv` wrong and read garbage through unsafe pointers with no error
     signal). Because both the paired and solo runs execute the IDENTICAL kernel code on
     IDENTICAL per-pair data with IDENTICAL K_TILE tiling, this check uses a near-exact tolerance
     (not the CPU oracle's looser one) -- any deviation at all is a real bug, not floating-point
     tiling-order noise.
  3. **`test_native_packing_hand_built`**: a small, deliberately traceable-by-hand shape
     (`h_q=4, h_kv=2, d=128, n_tok_k=70, offset=5`, spanning THREE native blocks including one
     fully-ragged tail) whose packed K/V buffer is built via an inline restatement of the
     flat-index formula (independent of `_pack_k_native`/`_pack_v_native`), verified against
     `sdpa_forward_flat`'s natural-layout oracle -- see this file's own module docstring.
  4. A 1,000-dispatch determinism soak on the real-Qwen3-dims shape.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge -I ../mojo/engine \
      ../attention_forge/grouped_fa_q8_k32_h2_sg8_driver.mojo
"""
from max.gpu.host import DeviceContext
from attnk.contract import ATTN_OK
from attnk.mask import mask_causal_flat
from attnk.sdpa import sdpa_forward_flat
from grouped_fa_q8_k32_h2_sg8 import _attn_grouped_fa_kernel


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _n_blocks_for(n_tok_k: Int, key_block_size: Int) -> Int:
    return (n_tok_k + key_block_size - 1) // key_block_size


def _pack_k_native(k64: List[Float64], n_tok_k: Int, h_kv: Int, d: Int, key_block_size: Int, n_blocks: Int) -> List[Float64]:
    """Host-side re-layout of a NATURAL `[position][kv_head][d_head]` K buffer (`k64`, this file's
    own `_pseudo_f16` convention) into the kernel-under-test's native packed layout
    (`[kv_head][key_block][d_chunk][key_in_block]`), matching `native_kv_producer.mojo`'s own
    flat-index formula exactly (`((hk*n_blocks+block)*d+dd)*key_block_size+kk`, `block =
    gk//key_block_size`, `kk = gk%key_block_size`) -- restated here independently, not imported.
    Positions at or beyond `n_tok_k` within the last block are left at 0.0; the kernel under test
    never reads them as anything numerically load-bearing (see that kernel's own module docstring's
    "K: DEVICE-DIRECT MMA LOAD" section), but zero is still a deliberately unsurprising default."""
    var total = h_kv * n_blocks * d * key_block_size
    var out = List[Float64](capacity=total)
    for _ in range(total):
        out.append(0.0)
    for gk in range(n_tok_k):
        var block = gk // key_block_size
        var kk = gk % key_block_size
        for hk in range(h_kv):
            for dd in range(d):
                out[((hk * n_blocks + block) * d + dd) * key_block_size + kk] = k64[(gk * h_kv + hk) * d + dd]
    return out^


def _pack_v_native(v64: List[Float64], n_tok_k: Int, h_kv: Int, d: Int, key_block_size: Int, n_blocks: Int) -> List[Float64]:
    """Same as `_pack_k_native` but for V's native layout (`[kv_head][key_block][key_in_block]
    [d_chunk]`): `((hk*n_blocks+block)*key_block_size+kk)*d+dd`. Positions at or beyond `n_tok_k`
    within the last block are left at 0.0 -- for V this IS load-bearing (the kernel's own
    `kk < nb` boundary zero-fill already covers this at the shared-memory-staging step, but this
    driver's own upload buffer starts zeroed regardless, so a bug in that guard would still read a
    deterministic, finite 0.0 here rather than truly arbitrary device memory)."""
    var total = h_kv * n_blocks * key_block_size * d
    var out = List[Float64](capacity=total)
    for _ in range(total):
        out.append(0.0)
    for gk in range(n_tok_k):
        var block = gk // key_block_size
        var kk = gk % key_block_size
        for hk in range(h_kv):
            for dd in range(d):
                out[((hk * n_blocks + block) * key_block_size + kk) * d + dd] = v64[(gk * h_kv + hk) * d + dd]
    return out^


def _pseudo_f16(n: Int, seed: Int) -> List[Float64]:
    """Same deterministic generator convention as `parity_replica_driver.mojo`'s `_pseudo_f16`
    (itself matching `attn_block_update_probe.mojo`'s `_pseudo`): narrowed to Float16 and widened
    back immediately, so F16 storage precision is a controlled input to both the GPU kernel and
    the CPU oracle, not an unattributed source of mismatch."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float16(raw)))
    return o^


def test_correctness(
    ctx: DeviceContext, name: String,
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int,
) raises -> Bool:
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

    var key_block_size = 32
    var n_blocks = _n_blocks_for(n_tok_k, key_block_size)
    var k_native = _pack_k_native(k64, n_tok_k, h_kv, d, key_block_size, n_blocks)
    var v_native = _pack_v_native(v64, n_tok_k, h_kv, d, key_block_size, n_blocks)

    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d * key_block_size)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * key_block_size * d)
    with q_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * d * key_block_size):
            h[i] = Float16(k_native[i])
    with v_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * key_block_size * d):
            h[i] = Float16(v_native[i])
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    with out_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float32(-999.0)  # canary: must be fully overwritten for every valid row

    var n_q_blocks = (n_tok_q + 15) // 16
    var grid = n_q_blocks * (h_q // 2)
    ctx.enqueue_function[_attn_grouped_fa_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
        Float32(scale), Int64(offset), Int64(n_blocks),
        grid_dim=grid, block_dim=256,
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
    print("  [", name, "] worst-ratio out=", worst_out, " lse=", worst_lse, "  ", "OK" if ok else "MISMATCH")
    return ok


def test_h_tile_pairing_isolation(
    ctx: DeviceContext, name: String, n_tok_q: Int, n_tok_k: Int, h_kv: Int, offset: Int,
) raises -> Bool:
    """H_TILE=2 (paired, multi-pair grid) vs. solo-pair (that ONE pair alone, every other pair
    removed from BOTH the grid and the K/V buffer) -- see module docstring's item 2. `h_kv` here
    is the number of KV heads / sibling pairs in the PAIRED run; `h_q_paired = h_kv * 2`."""
    var d = 128
    var h_q_paired = h_kv * 2
    var q64 = _pseudo_f16(n_tok_q * h_q_paired * d, 3)
    var k64 = _pseudo_f16(n_tok_k * h_kv * d, 11)
    var v64 = _pseudo_f16(n_tok_k * h_kv * d, 29)
    var scale = 1.0 / Float64(d) ** 0.5
    var n_q_blocks = (n_tok_q + 15) // 16
    var key_block_size = 32
    var n_blocks = _n_blocks_for(n_tok_k, key_block_size)

    # --- paired run: every sibling pair sharing this dispatch's grid ---
    var k_native_paired = _pack_k_native(k64, n_tok_k, h_kv, d, key_block_size, n_blocks)
    var v_native_paired = _pack_v_native(v64, n_tok_k, h_kv, d, key_block_size, n_blocks)
    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q_paired * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d * key_block_size)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * key_block_size * d)
    with q_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q_paired * d):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * d * key_block_size):
            h[i] = Float16(k_native_paired[i])
    with v_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * key_block_size * d):
            h[i] = Float16(v_native_paired[i])
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q_paired * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q_paired * n_tok_q)
    var grid_paired = n_q_blocks * h_kv
    ctx.enqueue_function[_attn_grouped_fa_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q_paired), Int64(h_kv),
        Float32(scale), Int64(offset), Int64(n_blocks),
        grid_dim=grid_paired, block_dim=256,
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
        # full multi-head buffer with a mismatched head-count argument (the exact pitfall
        # `attn_block_update_probe.mojo`'s own `_run_case_h_tile_equivalence` docstring warns
        # about: that silently computes `group = h_q // h_kv` wrong and reads garbage through
        # unsafe pointers with no error signal).
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
        var k_native_solo = _pack_k_native(k_solo, n_tok_k, 1, d, key_block_size, n_blocks)
        var v_native_solo = _pack_v_native(v_solo, n_tok_k, 1, d, key_block_size, n_blocks)

        var qs_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * 2 * d)
        var ks_buf = ctx.enqueue_create_buffer[DType.float16](1 * n_blocks * d * key_block_size)
        var vs_buf = ctx.enqueue_create_buffer[DType.float16](1 * n_blocks * key_block_size * d)
        with qs_buf.map_to_host() as h:
            for i in range(n_tok_q * 2 * d):
                h[i] = Float16(q_solo[i])
        with ks_buf.map_to_host() as h:
            for j in range(n_blocks * d * key_block_size):
                h[j] = Float16(k_native_solo[j])
        with vs_buf.map_to_host() as h:
            for j in range(n_blocks * key_block_size * d):
                h[j] = Float16(v_native_solo[j])
        var outs_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * 2 * d)
        var lses_buf = ctx.enqueue_create_buffer[DType.float32](2 * n_tok_q)
        var grid_solo = n_q_blocks * 1
        ctx.enqueue_function[_attn_grouped_fa_kernel](
            outs_buf.unsafe_ptr(), lses_buf.unsafe_ptr(),
            qs_buf.unsafe_ptr(), ks_buf.unsafe_ptr(), vs_buf.unsafe_ptr(),
            Int64(n_tok_q), Int64(n_tok_k), Int64(2), Int64(1),
            Float32(scale), Int64(offset), Int64(n_blocks),
            grid_dim=grid_solo, block_dim=256,
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
    print("  [", name, "] paired vs. solo-pair worst abs delta: out=", worst_out, " lse=", worst_lse, "  ", "OK" if ok else "MISMATCH")
    return ok


def test_determinism_soak(
    ctx: DeviceContext, n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int, n_runs: Int,
) raises -> Bool:
    var q64 = _pseudo_f16(n_tok_q * h_q * d, 3)
    var k64 = _pseudo_f16(n_tok_k * h_kv * d, 11)
    var v64 = _pseudo_f16(n_tok_k * h_kv * d, 29)
    var key_block_size = 32
    var n_blocks = _n_blocks_for(n_tok_k, key_block_size)
    var k_native = _pack_k_native(k64, n_tok_k, h_kv, d, key_block_size, n_blocks)
    var v_native = _pack_v_native(v64, n_tok_k, h_kv, d, key_block_size, n_blocks)
    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d * key_block_size)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * key_block_size * d)
    with q_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * d * key_block_size):
            h[i] = Float16(k_native[i])
    with v_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * key_block_size * d):
            h[i] = Float16(v_native[i])
    var scale = 1.0 / Float64(d) ** 0.5
    var n_q_blocks = (n_tok_q + 15) // 16
    var grid = n_q_blocks * (h_q // 2)

    var first = List[Float32](capacity=n_tok_q * h_q * d)
    var worst_flip = 0
    for run in range(n_runs):
        var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
        var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
        ctx.enqueue_function[_attn_grouped_fa_kernel](
            out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
            Float32(scale), Int64(offset), Int64(n_blocks),
            grid_dim=grid, block_dim=256,
        )
        ctx.synchronize()
        with out_buf.map_to_host() as ho:
            if run == 0:
                for i in range(n_tok_q * h_q * d):
                    first.append(ho[i])
            else:
                for i in range(n_tok_q * h_q * d):
                    if ho[i] != first[i]:
                        worst_flip += 1

    var ok = worst_flip == 0
    print("  determinism soak: n_runs=", n_runs, " mismatching-element-dispatches=", worst_flip, "  ", "OK" if ok else "NONDETERMINISTIC")
    return ok


def test_native_packing_hand_built(ctx: DeviceContext) raises -> Bool:
    """New correctness case (per this task's own instruction) that builds a small packed K/V
    buffer directly BY HAND -- via an inline restatement of the flat-index formula, deliberately
    NOT routed through `_pack_k_native`/`_pack_v_native` (every other test in this file shares
    those two helpers; this one exists so the packing formula itself is exercised by a SECOND,
    independent implementation, not just the one everything else relies on). Shape: `h_q=4,
    h_kv=2, d=128, n_tok_k=70, offset=5` -- 70 keys spans block 0 ([0,32)), block 1 ([32,64)), and a
    RAGGED tail of block 2 ([64,70) valid, [70,96) unwritten) -- three blocks, one of them
    partial, at a nonzero causal offset, checked against the same `sdpa_forward_flat` natural-
    layout oracle every other test in this file uses."""
    var h_q = 4
    var h_kv = 2
    var d = 128
    var n_tok_q = 12
    var n_tok_k = 70
    var offset = 5
    var key_block_size = 32
    var n_blocks = (n_tok_k + key_block_size - 1) // key_block_size  # = 3, restated inline

    var q64 = _pseudo_f16(n_tok_q * h_q * d, 41)
    var k64 = _pseudo_f16(n_tok_k * h_kv * d, 43)
    var v64 = _pseudo_f16(n_tok_k * h_kv * d, 47)

    var cm = mask_causal_flat(n_tok_q, n_tok_k, offset)
    if cm.status != ATTN_OK:
        print("  [ native packing, hand-built ] mask build FAILED")
        return False
    var scale = 1.0 / Float64(d) ** 0.5
    var oracle = sdpa_forward_flat(q64, k64, v64, cm.bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale, True)
    if oracle.status != ATTN_OK:
        print("  [ native packing, hand-built ] oracle FAILED, status=", oracle.status)
        return False

    # Hand-built K/V native buffers -- inline flat-index formula, restated here independently of
    # `_pack_k_native`/`_pack_v_native` (see this function's own docstring).
    var k_total = h_kv * n_blocks * d * key_block_size
    var v_total = h_kv * n_blocks * key_block_size * d
    var k_native = List[Float64](capacity=k_total)
    for _ in range(k_total):
        k_native.append(0.0)
    var v_native = List[Float64](capacity=v_total)
    for _ in range(v_total):
        v_native.append(0.0)
    for gk in range(n_tok_k):
        var block = gk // key_block_size
        var kk = gk % key_block_size
        for hk in range(h_kv):
            for dd in range(d):
                var natural_val_k = k64[(gk * h_kv + hk) * d + dd]
                var natural_val_v = v64[(gk * h_kv + hk) * d + dd]
                var k_flat = ((hk * n_blocks + block) * d + dd) * key_block_size + kk
                var v_flat = ((hk * n_blocks + block) * key_block_size + kk) * d + dd
                k_native[k_flat] = natural_val_k
                v_native[v_flat] = natural_val_v

    # A few hand-computed (position, kv_head, d) -> flat-index spot checks, printed for the human
    # record, including the 31/32 and 63/64 block-boundary pairs and a position (69) in the ragged
    # tail of the final, partially-filled block.
    var spot_checks = List[Tuple[Int, Int, Int]]()
    spot_checks.append((31, 0, 0))
    spot_checks.append((32, 0, 0))
    spot_checks.append((63, 1, 100))
    spot_checks.append((64, 1, 100))
    spot_checks.append((69, 1, 127))
    var spot_ok = True
    for t in spot_checks:
        var pos = t[0]
        var hkv = t[1]
        var dd = t[2]
        var block = pos // key_block_size
        var kk = pos % key_block_size
        var k_flat = ((hkv * n_blocks + block) * d + dd) * key_block_size + kk
        var want = k64[(pos * h_kv + hkv) * d + dd]
        var got = k_native[k_flat]
        var ok = got == want
        spot_ok = spot_ok and ok
        print("    [hand-index] pos=", pos, " hk=", hkv, " d=", dd, " block=", block, " kk=", kk, " k_flat=", k_flat, "  ", "OK" if ok else "MISMATCH")
    print("  [native packing hand-index spot checks]  ", "OK" if spot_ok else "MISMATCH")

    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](k_total)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](v_total)
    with q_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(k_total):
            h[i] = Float16(k_native[i])
    with v_buf.map_to_host() as h:
        for i in range(v_total):
            h[i] = Float16(v_native[i])
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    with out_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float32(-999.0)

    var n_q_blocks = (n_tok_q + 15) // 16
    var grid = n_q_blocks * (h_q // 2)
    ctx.enqueue_function[_attn_grouped_fa_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
        Float32(scale), Int64(offset), Int64(n_blocks),
        grid_dim=grid, block_dim=256,
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

    var ok = spot_ok and worst_out <= 1.0 and worst_lse <= 1.0
    print("  [ native packing, hand-built, 3 blocks incl. ragged tail ] worst-ratio out=", worst_out, " lse=", worst_lse, "  ", "OK" if ok else "MISMATCH")
    return ok


def main() raises:
    var ctx = DeviceContext()
    var all_ok = True

    print("=== Candidate A (grouped_fa_q8_k32_h2_sg8): correctness vs attnk.sdpa (trusted materialized reference) ===")
    all_ok = test_correctness(ctx, "tiny aligned", 8, 64, 2, 1, 128, 0) and all_ok
    all_ok = test_correctness(ctx, "tiny ragged K", 8, 37, 2, 1, 128, 0) and all_ok
    all_ok = test_correctness(ctx, "two q-blocks, offset", 16, 96, 2, 1, 128, 13) and all_ok
    all_ok = test_correctness(ctx, "real Qwen3-0.6B-Base dims, m=17 offset=37", 17, 130, 16, 8, 128, 37) and all_ok
    all_ok = test_correctness(ctx, "real dims, 256-token single-shot prefill", 256, 256, 16, 8, 128, 0) and all_ok

    print("")
    print("=== H_TILE=2 (paired) vs. solo-pair grid-independence ===")
    all_ok = test_h_tile_pairing_isolation(ctx, "h_tile aligned", 16, 64, 8, 0) and all_ok
    all_ok = test_h_tile_pairing_isolation(ctx, "h_tile mid-block cutoff, ragged, offset", 10, 37, 4, 5) and all_ok
    all_ok = test_h_tile_pairing_isolation(ctx, "h_tile real dims", 17, 130, 8, 37) and all_ok

    print("")
    print("=== native packed KV layout: hand-built packing (independent of _pack_k_native/_pack_v_native) ===")
    all_ok = test_native_packing_hand_built(ctx) and all_ok

    print("")
    print("=== 1,000-dispatch determinism soak (real dims, single-shot prefill) ===")
    all_ok = test_determinism_soak(ctx, 256, 256, 16, 8, 128, 0, 1000) and all_ok

    print("")
    if all_ok:
        print("CANDIDATE A (grouped_fa_q8_k32_h2_sg8): PASS (correct vs CPU oracle on native packed KV, hand-built packing verified, paired==solo-pair, deterministic over 1,000 dispatches)")
    else:
        print("CANDIDATE A (grouped_fa_q8_k32_h2_sg8): FAIL")
