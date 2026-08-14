"""attention_forge.grouped_fa_steel_d64_driver -- correctness driver for the d_head=64 steel
prefill kernel (`grouped_fa_steel_d64.mojo`), feat/llama-prefill (2026-08-13). Checks:

  1. Correctness against `attnk.sdpa.sdpa_forward_flat` (the trusted materialized Float64
     reference every attention driver in this repo checks against) at a sweep of shapes: tiny
     aligned, ragged K, nonzero causal offset (KV-cache continuation), TinyLlama-1.1B's real dims
     (h_q=32, h_kv=4, d=64), and 512/1024-token single-shot prefills. The CPU oracle computes
     every query head FULLY INDEPENDENTLY, so a per-head match rules out cross-head leakage.
  2. Multi-chunk continuation consistency: a 64-token prefill at pos_base=0 followed by a
     40-token continuation at pos_base=64 must produce the SAME last-row output as a single
     104-token prefill (the producer/attention pos_base contract, exercised end-to-end).
  3. A 200-dispatch determinism soak on the TinyLlama-dims shape.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge -I ../mojo/engine \
      ../attention_forge/grouped_fa_steel_d64_driver.mojo
"""
from max.gpu.host import DeviceContext
from attnk.contract import ATTN_OK
from attnk.mask import mask_causal_flat
from attnk.sdpa import sdpa_forward_flat
from grouped_fa_steel_d64 import _attn_grouped_fa_d64_kernel


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _n_blocks_for(n_tok_k: Int, key_block_size: Int) -> Int:
    return (n_tok_k + key_block_size - 1) // key_block_size


def _pack_k_native(k64: List[Float64], n_tok_k: Int, h_kv: Int, d: Int, key_block_size: Int, n_blocks: Int) -> List[Float64]:
    """Host-side re-layout of a NATURAL `[position][kv_head][d_head]` K buffer into the kernel's
    native packed layout `[kv_head][key_block][d_chunk][key_in_block]` -- the SAME flat-index
    formula `native_kv_producer.mojo` writes (`((hk*n_blocks+block)*d+dd)*key_block_size+kk`),
    restated independently here per this repo's driver convention."""
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
    """Same as `_pack_k_native` but for V's native layout `[kv_head][key_block][key_in_block]
    [d_chunk]`: `((hk*n_blocks+block)*key_block_size+kk)*d+dd`."""
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
    """Deterministic generator, narrowed to Float16 and widened back immediately, so F16 storage
    precision is a controlled input to both the GPU kernel and the CPU oracle."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float16(raw)))
    return o^


def test_correctness(
    ctx: DeviceContext, name: String,
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int,
) raises -> Bool:
    if d != 64:
        print("  [", name, "] SKIPPED: this kernel is specialized to d_head=64")
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

    var n_q_blocks = (n_tok_q + 31) // 32
    var grid = n_q_blocks * h_q
    ctx.enqueue_function[_attn_grouped_fa_d64_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
        Float32(scale), Int64(offset), Int64(n_blocks),
        grid_dim=grid, block_dim=128,
    )
    ctx.synchronize()

    var worst_out = 0.0
    var worst_lse = 0.0
    with out_buf.map_to_host() as ho:
        for i in range(n_tok_q * h_q * d):
            var got = Float64(ho[i])
            if got == -999.0:
                print("  [", name, "] CANARY SURVIVED at ", i, " -- store path missed a row")
                return False
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


def _run_kernel_read_out(
    ctx: DeviceContext, q64: List[Float64], k64: List[Float64], v64: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int,
) raises -> List[Float32]:
    """Dispatch the d64 kernel over already-natural-layout Q/K/V host data (packing K/V here)
    and return the F32 output as a host list."""
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
    var scale = Float32(1.0 / Float64(d) ** 0.5)
    var n_q_blocks = (n_tok_q + 31) // 32
    var grid = n_q_blocks * h_q
    ctx.enqueue_function[_attn_grouped_fa_d64_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
        scale, Int64(offset), Int64(n_blocks),
        grid_dim=grid, block_dim=128,
    )
    ctx.synchronize()
    var out = List[Float32](capacity=n_tok_q * h_q * d)
    with out_buf.map_to_host() as ho:
        for i in range(n_tok_q * h_q * d):
            out.append(ho[i])
    return out^


def test_continuation(ctx: DeviceContext, name: String) raises -> Bool:
    """64-token prefill + 40-token continuation at pos_base=64 == single 104-token prefill on the
    last 40 rows (TinyLlama dims). The continuation call carries the FULL 104-key packed cache
    (both chunks' K/V), exactly the engine's per-chunk contract."""
    var d = 64
    var h_q = 32
    var h_kv = 4
    var n1 = 64
    var n2 = 40
    var n_tot = n1 + n2

    var q_all = _pseudo_f16(n_tot * h_q * d, 5)
    var k_all = _pseudo_f16(n_tot * h_kv * d, 7)
    var v_all = _pseudo_f16(n_tot * h_kv * d, 13)

    # Single-shot reference: all 104 tokens at once.
    var ref_out = _run_kernel_read_out(ctx, q_all, k_all, v_all, n_tot, n_tot, h_q, h_kv, d, 0)

    # Chunked: the continuation chunk's Q rows are q_all's LAST n2 rows; the K/V cache passed in
    # is the FULL 104-key cache; pos_base=64 makes the causal mask absolute.
    var q2 = List[Float64](capacity=n2 * h_q * d)
    for i in range(n2):
        for e in range(h_q * d):
            q2.append(q_all[(n1 + i) * h_q * d + e])
    var got = _run_kernel_read_out(ctx, q2, k_all, v_all, n2, n_tot, h_q, h_kv, d, n1)

    var worst = 0.0
    for i in range(n2):
        for e in range(h_q * d):
            var diff = _abs64(Float64(got[i * h_q * d + e]) - Float64(ref_out[(n1 + i) * h_q * d + e]))
            if diff > worst:
                worst = diff
    var ok = worst <= 1.0e-4
    print("  [", name, "] continuation vs single-shot worst abs delta=", worst, "  ", "OK" if ok else "MISMATCH")
    return ok


def test_determinism(ctx: DeviceContext, name: String, reps: Int) raises -> Bool:
    var d = 64
    var h_q = 32
    var h_kv = 4
    var n = 128
    var q64 = _pseudo_f16(n * h_q * d, 3)
    var k64 = _pseudo_f16(n * h_kv * d, 11)
    var v64 = _pseudo_f16(n * h_kv * d, 29)
    var first = _run_kernel_read_out(ctx, q64, k64, v64, n, n, h_q, h_kv, d, 0)
    var mismatches = 0
    for r in range(reps):
        var again = _run_kernel_read_out(ctx, q64, k64, v64, n, n, h_q, h_kv, d, 0)
        for i in range(n * h_q * d):
            if again[i] != first[i]:
                mismatches += 1
    var ok = mismatches == 0
    print("  [", name, "] ", reps, "-dispatch soak mismatches=", mismatches, "  ", "OK" if ok else "MISMATCH")
    return ok


def main() raises:
    var ctx = DeviceContext()
    var all_ok = True

    print("grouped_fa_steel_d64 correctness sweep (oracle = attnk.sdpa.sdpa_forward_flat):")
    all_ok = test_correctness(ctx, "tiny aligned", 8, 64, 2, 1, 64, 0) and all_ok
    all_ok = test_correctness(ctx, "ragged K", 33, 70, 4, 2, 64, 0) and all_ok
    all_ok = test_correctness(ctx, "offset continuation", 16, 96, 4, 2, 64, 17) and all_ok
    all_ok = test_correctness(ctx, "tinyllama dims 128q", 128, 128, 32, 4, 64, 0) and all_ok
    all_ok = test_correctness(ctx, "tinyllama dims 512q", 512, 512, 32, 4, 64, 0) and all_ok
    all_ok = test_correctness(ctx, "tinyllama dims 1024q", 1024, 1024, 32, 4, 64, 0) and all_ok
    all_ok = test_correctness(ctx, "tinyllama ragged 500/1000", 500, 1000, 32, 4, 64, 0) and all_ok
    all_ok = test_correctness(ctx, "tinyllama chunked offset 512@512", 512, 1024, 32, 4, 64, 512) and all_ok

    print("continuation contract:")
    all_ok = test_continuation(ctx, "64+40 @pos_base=64") and all_ok

    print("determinism:")
    all_ok = test_determinism(ctx, "soak", 200) and all_ok

    if all_ok:
        print("GROUPED_FA_STEEL_D64: ALL CHECKS PASSED")
    else:
        print("GROUPED_FA_STEEL_D64: FAILURES PRESENT")
