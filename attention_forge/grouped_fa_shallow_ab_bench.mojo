"""attention_forge.grouped_fa_shallow_ab_bench -- beat-llama.cpp campaign (2026-08-11 night):
STEEL (production `_attn_grouped_fa_kernel`, BQ=32, 1 head/TG, block_dim=128) vs LEAN-Q8
(`grouped_fa_lean_q8_k32_h2_sg8._attn_grouped_fa_lean_q8_kernel`, Q_TILE=8, h2-paired, 256
threads) at the SHALLOW/MID depths where the DVFS-controlled three-way still loses prefill
(1K: 0.87x/0.95x of controls). The morning roofline measured steel at only 6.5 TF/s @1K vs
11.8 @8K -- prologue-amortization-bound at shallow depths -- while the old lean experiments
found q8-style kernels WIN shallow (1.23x @1K) and lose deep (0.97x @8K). This bench settles
the crossover for a possible DEPTH-SWITCHED attention dispatch (lean shallow, steel deep).
Timing: same resident buffers, 3 warmup dispatches each, then 4 alternating rounds (steel, lean
per round) to cancel drift; per-depth per-kernel median of rounds. Correctness is established by
the kernels' own oracle suites (steel: PR #621 gates; lean-q8: its own driver's gates); this
bench is timing-only.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge \
      ../attention_forge/grouped_fa_shallow_ab_bench.mojo
"""
from max.gpu.host import DeviceContext
from std.time import perf_counter_ns
from grouped_fa_q8_k32_h2_sg8 import _attn_grouped_fa_kernel
from grouped_fa_lean_q8_k32_h2_sg8 import _attn_grouped_fa_lean_q8_kernel

comptime _H_Q: Int = 16
comptime _H_KV: Int = 8
comptime _D: Int = 128
comptime _KBS: Int = 32


def _fill_f16(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float16(raw)))
    return o^


def bench_pair(ctx: DeviceContext, n_tok: Int, reps: Int) raises:
    var h_q = _H_Q
    var h_kv = _H_KV
    var d = _D
    var kbs = _KBS
    var n_blocks = (n_tok + kbs - 1) // kbs
    var scale = Float32(1.0 / Float64(d) ** 0.5)

    var q_n = n_tok * h_q * d
    var k_n = h_kv * n_blocks * d * kbs
    var v_n = h_kv * n_blocks * kbs * d
    var q64 = _fill_f16(q_n, 3)
    var k64 = _fill_f16(k_n, 11)
    var v64 = _fill_f16(v_n, 29)

    var q_buf = ctx.enqueue_create_buffer[DType.float16](q_n)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](k_n)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](v_n)
    var out_buf = ctx.enqueue_create_buffer[DType.float32](q_n)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok)
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

    var steel_grid = (n_tok + 31) // 32 * h_q
    var lean_grid = (n_tok + 7) // 8 * (h_q // 2)

    # Warmup both.
    for _ in range(3):
        ctx.enqueue_function[_attn_grouped_fa_kernel](
            out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_tok), Int64(n_tok), Int64(h_q), Int64(h_kv),
            scale, Int64(0), Int64(n_blocks),
            grid_dim=steel_grid, block_dim=128)
        ctx.enqueue_function[_attn_grouped_fa_lean_q8_kernel](
            out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_tok), Int64(n_tok), Int64(h_q), Int64(h_kv),
            scale, Int64(0), Int64(n_blocks),
            grid_dim=lean_grid, block_dim=256)
    ctx.synchronize()

    var steel_ms = List[Float64]()
    var lean_ms = List[Float64]()
    for _ in range(4):
        var t0 = perf_counter_ns()
        for _ in range(reps):
            ctx.enqueue_function[_attn_grouped_fa_kernel](
                out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
                q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
                Int64(n_tok), Int64(n_tok), Int64(h_q), Int64(h_kv),
                scale, Int64(0), Int64(n_blocks),
                grid_dim=steel_grid, block_dim=128)
        ctx.synchronize()
        var t1 = perf_counter_ns()
        steel_ms.append(Float64(t1 - t0) / 1.0e6 / Float64(reps))
        var t2 = perf_counter_ns()
        for _ in range(reps):
            ctx.enqueue_function[_attn_grouped_fa_lean_q8_kernel](
                out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
                q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
                Int64(n_tok), Int64(n_tok), Int64(h_q), Int64(h_kv),
                scale, Int64(0), Int64(n_blocks),
                grid_dim=lean_grid, block_dim=256)
        ctx.synchronize()
        var t3 = perf_counter_ns()
        lean_ms.append(Float64(t3 - t2) / 1.0e6 / Float64(reps))

    # Medians.
    var s_med = steel_ms[0]
    var l_med = lean_ms[0]
    for i in range(1, 4):
        if steel_ms[i] < s_med:
            s_med = steel_ms[i]
        if lean_ms[i] < l_med:
            l_med = lean_ms[i]
    var pairs = Float64(n_tok) * Float64(n_tok + 1) / 2.0
    var gf = 2.0 * Float64(h_q) * pairs * (2.0 * Float64(d)) / 1.0e9
    print("  [shallow-ab] N=", n_tok,
          " steel=", s_med, "ms (", gf / (s_med / 1.0e3) / 1.0e3, "TF/s)",
          " leanq8=", l_med, "ms (", gf / (l_med / 1.0e3) / 1.0e3, "TF/s)",
          " lean/steel=", s_med / l_med if l_med > 1.0e-9 else -1.0, "x")


def main() raises:
    var ctx = DeviceContext()
    print("=== steel (production, BQ=32) vs lean-q8 (Q_TILE=8, h2) -- shallow crossover hunt ===")
    bench_pair(ctx, 512, 30)
    bench_pair(ctx, 1024, 20)
    bench_pair(ctx, 2048, 10)
    bench_pair(ctx, 4096, 6)
    bench_pair(ctx, 8192, 3)
    print("done")
