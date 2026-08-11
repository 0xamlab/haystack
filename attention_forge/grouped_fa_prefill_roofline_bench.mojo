"""attention_forge.grouped_fa_prefill_roofline_bench -- beat-llama.cpp campaign (KV-resident
scoping): standalone steady-state TIMING of the CURRENT grouped-FA prefill attention kernel
(`grouped_fa_q8_k32_h2_sg8._attn_grouped_fa_kernel`, Q_TILE=16) at the deep-prefill shapes that
decide the 8K verdict. Purpose: settle, by measurement, whether the kernel is BANDWIDTH-bound
(KV-traffic arithmetic intensity -- the KV-resident restructure is the right lever) or
COMPUTE/LATENCY-bound (bigger MMA tiles / fewer barriers / softmax vectorization is the right
lever) BEFORE sinking effort into a from-scratch kernel.

No correctness oracle here (that lives in `grouped_fa_q8_k32_h2_sg8_driver.mojo`); buffers are
filled with a simple deterministic F16 pattern (no NaN, so exp/softmax stay finite) purely so the
kernel runs its real control flow at the real shape. Upload once, keep resident, warmup, then time
`reps` dispatches with perf_counter_ns + ctx.synchronize.

Reports per dispatch:
  - wall ms
  - achieved GFLOP/s  (FLOPs = 2 * h_q * N(N+1)/2 * 2d  for QK^T + PV, causal, offset=0)
  - min-traffic GB/s  (each of Q/K/V/out moved exactly once -- the LOWER bound on bytes; if the
    kernel were perfectly cache-reusing, measured GB/s lands near this; the gap between this and
    the hardware DRAM bandwidth is how much room KV re-reads have to hurt)
  - implied KV re-read multiplier = (n_q/Q_TILE) q-block threadgroups each sweeping the causal KV.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge \
      ../attention_forge/grouped_fa_prefill_roofline_bench.mojo
"""
from max.gpu.host import DeviceContext
from std.time import perf_counter_ns
from grouped_fa_q8_k32_h2_sg8 import _attn_grouped_fa_kernel

comptime _H_Q: Int = 16
comptime _H_KV: Int = 8
comptime _D: Int = 128
comptime _QT: Int = 32
comptime _KBS: Int = 32


def _fill_f16(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float16(raw)))
    return o^


def bench_prefill(ctx: DeviceContext, n_tok: Int, reps: Int) raises:
    var h_q = _H_Q
    var h_kv = _H_KV
    var d = _D
    var qt = _QT
    var kbs = _KBS
    var n_blocks = (n_tok + kbs - 1) // kbs
    var n_q_blocks = (n_tok + qt - 1) // qt
    # Steel re-layout (PR #621): 1 head/threadgroup, BQ=32 q rows, block_dim=128.
    var grid = n_q_blocks * h_q
    var scale = Float32(1.0 / Float64(d) ** 0.5)

    var q_n = n_tok * h_q * d
    var k_n = h_kv * n_blocks * d * kbs
    var v_n = h_kv * n_blocks * kbs * d
    var out_n = n_tok * h_q * d
    var lse_n = h_q * n_tok

    var q64 = _fill_f16(q_n, 3)
    var k64 = _fill_f16(k_n, 11)
    var v64 = _fill_f16(v_n, 29)

    var q_buf = ctx.enqueue_create_buffer[DType.float16](q_n)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](k_n)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](v_n)
    var out_buf = ctx.enqueue_create_buffer[DType.float32](out_n)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](lse_n)
    with q_buf.map_to_host() as h:
        for i in range(q_n):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(k_n):
            h[i] = Float16(k64[i])
    with v_buf.map_to_host() as h:
        for i in range(v_n):
            h[i] = Float16(v64[i])
    ctx.synchronize()

    # Warmup (untimed).
    for _ in range(2):
        ctx.enqueue_function[_attn_grouped_fa_kernel](
            out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_tok), Int64(n_tok), Int64(h_q), Int64(h_kv),
            scale, Int64(0), Int64(n_blocks),
            grid_dim=grid, block_dim=128,
        )
    ctx.synchronize()

    var t0 = perf_counter_ns()
    for _ in range(reps):
        ctx.enqueue_function[_attn_grouped_fa_kernel](
            out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_tok), Int64(n_tok), Int64(h_q), Int64(h_kv),
            scale, Int64(0), Int64(n_blocks),
            grid_dim=grid, block_dim=128,
        )
    ctx.synchronize()
    var t1 = perf_counter_ns()
    var ms = Float64(t1 - t0) / 1.0e6 / Float64(reps)

    # FLOPs: causal (offset=0) -- query row i attends to i+1 keys; sum_i (i+1) = N(N+1)/2 pairs,
    # each pair costs 2*d FLOP for QK^T and again for PV.
    var pairs = Float64(n_tok) * Float64(n_tok + 1) / 2.0
    var flops = 2.0 * Float64(h_q) * pairs * (2.0 * Float64(d))
    var gflops = flops / (ms * 1.0e-3) / 1.0e9

    # Min-traffic bytes (each buffer moved once -- the arithmetic-intensity ceiling if KV were
    # perfectly reused): Q read + K read + V read + out write + lse write.
    var min_bytes = Float64(q_n) * 2.0 + Float64(k_n) * 2.0 + Float64(v_n) * 2.0 \
        + Float64(out_n) * 4.0 + Float64(lse_n) * 4.0
    var min_gbs = min_bytes / (ms * 1.0e-3) / 1.0e9

    # The current kernel's KV re-read factor: every one of the n_q_blocks*q-block threadgroups
    # sweeps the causal KV (avg ~half the cache), so K/V bytes are touched ~n_q_blocks times.
    var re_read = Float64(n_q_blocks)

    print("  [prefill-roofline] N=", n_tok, " grid=", grid, " reps=", reps,
          " wall=", ms, "ms/dispatch  GFLOP/s=", gflops,
          " min-traffic-GB/s=", min_gbs, " kv-reread-x=", re_read)


def main() raises:
    var ctx = DeviceContext()
    print("grouped-FA prefill roofline (steel BQ=32, 1 head/TG, h_q=16, h_kv=8, d=128, offset=0)")
    bench_prefill(ctx, 1024, 20)
    bench_prefill(ctx, 2048, 10)
    bench_prefill(ctx, 4096, 6)
    bench_prefill(ctx, 8192, 3)
