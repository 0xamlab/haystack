"""attention_forge.grouped_fa_q8_k32_h2_sg8_driver -- correctness driver for CANDIDATE A
(`grouped_fa_q8_k32_h2_sg8.mojo`; see that file's own docstring for the exact shape shipped and
why), matching this repo's established forge-native pattern
(`attention_forge.parity_replica_driver`, `mma_forge/probes/correctness_probe_partial.mojo`).

Three checks:

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
  3. A 1,000-dispatch determinism soak on the real-Qwen3-dims shape.

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

    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * h_kv * d)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * h_kv * d)
    with q_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(n_tok_k * h_kv * d):
            h[i] = Float16(k64[i])
    with v_buf.map_to_host() as h:
        for i in range(n_tok_k * h_kv * d):
            h[i] = Float16(v64[i])
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    with out_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float32(-999.0)  # canary: must be fully overwritten for every valid row

    var n_q_blocks = (n_tok_q + 7) // 8
    var grid = n_q_blocks * (h_q // 2)
    ctx.enqueue_function[_attn_grouped_fa_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
        Float32(scale), Int64(offset),
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
    var n_q_blocks = (n_tok_q + 7) // 8

    # --- paired run: every sibling pair sharing this dispatch's grid ---
    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q_paired * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * h_kv * d)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * h_kv * d)
    with q_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q_paired * d):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(n_tok_k * h_kv * d):
            h[i] = Float16(k64[i])
    with v_buf.map_to_host() as h:
        for i in range(n_tok_k * h_kv * d):
            h[i] = Float16(v64[i])
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q_paired * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q_paired * n_tok_q)
    var grid_paired = n_q_blocks * h_kv
    ctx.enqueue_function[_attn_grouped_fa_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q_paired), Int64(h_kv),
        Float32(scale), Int64(offset),
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

        var qs_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * 2 * d)
        var ks_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * d)
        var vs_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * d)
        with qs_buf.map_to_host() as h:
            for i in range(n_tok_q * 2 * d):
                h[i] = Float16(q_solo[i])
        with ks_buf.map_to_host() as h:
            for j in range(n_tok_k * d):
                h[j] = Float16(k_solo[j])
        with vs_buf.map_to_host() as h:
            for j in range(n_tok_k * d):
                h[j] = Float16(v_solo[j])
        var outs_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * 2 * d)
        var lses_buf = ctx.enqueue_create_buffer[DType.float32](2 * n_tok_q)
        var grid_solo = n_q_blocks * 1
        ctx.enqueue_function[_attn_grouped_fa_kernel](
            outs_buf.unsafe_ptr(), lses_buf.unsafe_ptr(),
            qs_buf.unsafe_ptr(), ks_buf.unsafe_ptr(), vs_buf.unsafe_ptr(),
            Int64(n_tok_q), Int64(n_tok_k), Int64(2), Int64(1),
            Float32(scale), Int64(offset),
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
    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * h_kv * d)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * h_kv * d)
    with q_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(n_tok_k * h_kv * d):
            h[i] = Float16(k64[i])
    with v_buf.map_to_host() as h:
        for i in range(n_tok_k * h_kv * d):
            h[i] = Float16(v64[i])
    var scale = 1.0 / Float64(d) ** 0.5
    var n_q_blocks = (n_tok_q + 7) // 8
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
            Float32(scale), Int64(offset),
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
    print("=== 1,000-dispatch determinism soak (real dims, single-shot prefill) ===")
    all_ok = test_determinism_soak(ctx, 256, 256, 16, 8, 128, 0, 1000) and all_ok

    print("")
    if all_ok:
        print("CANDIDATE A (grouped_fa_q8_k32_h2_sg8): PASS (correct vs CPU oracle, paired==solo-pair, deterministic over 1,000 dispatches)")
    else:
        print("CANDIDATE A (grouped_fa_q8_k32_h2_sg8): FAIL")
