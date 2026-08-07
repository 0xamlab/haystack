"""attention_forge.parity_replica_driver -- forces codegen of `_attn_parity_replica_kernel`
(Phase 1's faithful llama.cpp replica, see `parity_replica.mojo`'s own docstring for the exact
scope) and checks it two ways, matching this repo's own established forge-native pattern
(`mma_forge/probes/correctness_probe_partial.mojo`):

  1. Correctness against `attnk.sdpa.sdpa_forward_flat` -- the same TRUSTED materialized reference
     `attn_block_update_probe.mojo` itself checks against -- at a sweep of shapes (small, real
     Qwen3-0.6B-Base dims, ragged K, nonzero causal offset). Q/K/V are narrowed to Float16 FIRST,
     then that SAME narrowed value (widened back to Float64) is what the CPU oracle consumes --
     isolating any mismatch to the kernel's own math rather than conflating it with ordinary F16
     storage precision loss.
  2. A 1,000-dispatch determinism soak on the real-Qwen3-dims shape (Attention Compiler Plan
     v1.0's own non-negotiable stop rule: never assume a new kernel is deterministic without
     checking, after this session's own real, pre-existing Mojo 1.0.0b2 reduction-bug finding in
     the UNRELATED per-key production kernels).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge -I ../mojo/engine ../attention_forge/parity_replica_driver.mojo
"""
from max.gpu.host import DeviceContext
from attnk.contract import ATTN_OK
from attnk.mask import mask_causal_flat
from attnk.sdpa import sdpa_forward_flat
from parity_replica import _attn_parity_replica_kernel
from mm8 import _qkv_proj_gemm_mma8x8


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f16(n: Int, seed: Int) -> List[Float64]:
    """Same deterministic generator convention as `attn_block_update_probe.mojo`'s `_pseudo`, but
    immediately narrowed to Float16 and widened back -- the value both the CPU oracle and the GPU
    kernel will actually consume, so F16 storage precision is a controlled input, not a source of
    unattributed mismatch."""
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
        print("  [", name, "] SKIPPED: this replica is specialized to d_qk=d_v=128 (Qwen3-0.6B-Base)")
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
    var grid = n_q_blocks * h_q
    ctx.enqueue_function[_attn_parity_replica_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
        Float32(scale), Int64(offset),
        grid_dim=grid, block_dim=128,
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
    var grid = n_q_blocks * h_q

    var first = List[Float32](capacity=n_tok_q * h_q * d)
    var worst_flip = 0
    for run in range(n_runs):
        var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
        var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
        ctx.enqueue_function[_attn_parity_replica_kernel](
            out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
            Float32(scale), Int64(offset),
            grid_dim=grid, block_dim=128,
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


def bench_operator_latency(
    ctx: DeviceContext, n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int, n_runs: Int,
) raises:
    """Wall-clock latency at the EXACT shape L0's own operator harness
    (`benchmarks/competitors/llama_cpp/operator_harness/fa_operator_harness.m`) measures --
    Q_ROWS=8, N_KV=64, H_Q=16, H_KV=8, DK=DV=128, one Q-tile, one K-tile, causal -- so the two
    numbers are directly comparable. Fresh output/LSE buffers per dispatch, matching L0's own
    fresh-command-buffer-per-iteration methodology; `ctx.synchronize()` plays the role of
    `waitUntilCompleted`. This measures WALL time, not GPU-only time (Mojo's `DeviceContext` does
    not expose a `GPUStartTime`/`GPUEndTime`-equivalent at this toolchain version) -- comparable
    to L0's own reported wall-median, not its GPU-only median; both are printed in the gap
    write-up so the comparison states which one it is using."""
    from std.time import perf_counter_ns

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
    var grid = n_q_blocks * h_q

    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    ctx.synchronize()

    var times_ns = List[Int](capacity=n_runs)
    for _ in range(n_runs):
        var t0 = perf_counter_ns()
        ctx.enqueue_function[_attn_parity_replica_kernel](
            out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
            Float32(scale), Int64(offset),
            grid_dim=grid, block_dim=128,
        )
        ctx.synchronize()
        var t1 = perf_counter_ns()
        times_ns.append(t1 - t0)

    for i in range(1, len(times_ns)):
        var key = times_ns[i]
        var j = i - 1
        while j >= 0 and times_ns[j] > key:
            times_ns[j + 1] = times_ns[j]
            j -= 1
        times_ns[j + 1] = key

    var median_ms = Float64(times_ns[n_runs // 2]) / 1.0e6
    var p10_ms = Float64(times_ns[n_runs // 10]) / 1.0e6
    var p90_ms = Float64(times_ns[n_runs * 9 // 10]) / 1.0e6
    print("  L1 (parity replica) timing (n=", n_runs, " dispatches, same shape as L0): wall median=", median_ms,
          "ms (p10=", p10_ms, "p90=", p90_ms, ")")


def bench_dispatch_overhead(ctx: DeviceContext, n_runs: Int, grid: Int) raises:
    """Isolates Mojo's OWN `enqueue_function` + `synchronize` dispatch overhead from the parity
    replica kernel's actual compute cost, using the ALREADY-PROVEN, unrelated `_qkv_proj_gemm_
    mma8x8` (`mma_forge/mm8.mojo`) at a trivially small (M=8,K=8,N=8) shape and the SAME
    threadgroup count as the operator-latency comparison above. If this trivial dispatch's wall
    time is itself a large fraction of `bench_operator_latency`'s measured 0.57ms, the L0-vs-L1
    wall-time gap is substantially a dispatch-overhead artifact of comparing Mojo's `enqueue_
    function` against hand-written Objective-C `setBuffer`/`setBytes`/`dispatchThreadgroups` --
    not evidence about the kernel's own GPU-side efficiency -- and must be reported as such rather
    than attributed to the attention kernel's schedule."""
    from std.time import perf_counter_ns

    var m = 8
    var k = 8
    var n = 8
    var xn_buf = ctx.enqueue_create_buffer[DType.float32](m * k)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](n * k)
    var wscale_buf = ctx.enqueue_create_buffer[DType.float32](n)
    var y_buf = ctx.enqueue_create_buffer[DType.float32](m * n)
    with xn_buf.map_to_host() as h:
        for i in range(m * k):
            h[i] = Float32(0.01)
    with w_buf.map_to_host() as h:
        for i in range(n * k):
            h[i] = Int8(1)
    with wscale_buf.map_to_host() as h:
        for i in range(n):
            h[i] = Float32(0.01)
    ctx.synchronize()

    var times_ns = List[Int](capacity=n_runs)
    for _ in range(n_runs):
        var t0 = perf_counter_ns()
        ctx.enqueue_function[_qkv_proj_gemm_mma8x8](
            y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
            wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n),
            grid_dim=grid, block_dim=256,
        )
        ctx.synchronize()
        var t1 = perf_counter_ns()
        times_ns.append(t1 - t0)

    for i in range(1, len(times_ns)):
        var key = times_ns[i]
        var j = i - 1
        while j >= 0 and times_ns[j] > key:
            times_ns[j + 1] = times_ns[j]
            j -= 1
        times_ns[j + 1] = key

    var median_ms = Float64(times_ns[n_runs // 2]) / 1.0e6
    print("  Mojo dispatch-overhead control (trivial 8x8x8 GEMM, grid=", grid, ", n=", n_runs, "): wall median=", median_ms, "ms")


def main() raises:
    var ctx = DeviceContext()
    var all_ok = True

    print("=== Phase 1 parity replica: correctness vs attnk.sdpa (trusted materialized reference) ===")
    all_ok = test_correctness(ctx, "tiny aligned", 8, 64, 2, 1, 128, 0) and all_ok
    all_ok = test_correctness(ctx, "tiny ragged K", 8, 37, 2, 1, 128, 0) and all_ok
    all_ok = test_correctness(ctx, "two q-blocks, offset", 16, 96, 2, 1, 128, 13) and all_ok
    all_ok = test_correctness(ctx, "real Qwen3-0.6B-Base dims, m=17 offset=37", 17, 130, 16, 8, 128, 37) and all_ok
    all_ok = test_correctness(ctx, "real dims, 256-token single-shot prefill", 256, 256, 16, 8, 128, 0) and all_ok

    print("")
    print("=== 1,000-dispatch determinism soak (real dims, single-shot prefill) ===")
    all_ok = test_determinism_soak(ctx, 256, 256, 16, 8, 128, 0, 1000) and all_ok

    print("")
    print("=== operator-latency comparison vs L0 (same shape as fa_operator_harness.m) ===")
    bench_operator_latency(ctx, 8, 64, 16, 8, 128, 0, 200)
    bench_dispatch_overhead(ctx, 200, 16)

    print("")
    if all_ok:
        print("PHASE 1 PARITY REPLICA: PASS (correct vs CPU oracle, deterministic over 1,000 dispatches)")
    else:
        print("PHASE 1 PARITY REPLICA: FAIL")
