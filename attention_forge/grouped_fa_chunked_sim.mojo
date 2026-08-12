"""attention_forge.grouped_fa_chunked_sim -- beat-llama.cpp campaign (2026-08-12): SIMULATION
harness for the chunked production prefill. Production prefills chunk into sequential
PREFILL_MAX_TILE-row prefill_batch calls (activations are tile-sized); production's tile was RAISED
512 -> 1024 this same night (see REALRACE_RESULTS.md "PREFILL TILE 512 -> 1024"), so `sim_prefill`
is TILE-PARAMETRIC and `main` A/Bs 512 vs 1024 at 4K/8K. Chunk i attends n_q=tile rows against keys
[0, tile(i+1)) with pos_base=tile*i. This bench measures the steel attention kernel at EACH chunk's
exact (n_q, n_kv, offset) shape and sums -- the attention half of a roofline SIMULATION of
whole-prefill wall time (the probe's per-role budgets in REALRACE_RESULTS.md supply the
non-attention constants). Purpose: predict whole-prefill attention cost at any depth WITHOUT the
full engine, and locate where the deep-prefill attention budget concentrates (MLX leads 8K prefill
solo 6820 vs ~5600). NOTE: this captures ONLY the attention-kernel cost; the tile win measured in
production came from the HOST/DISPATCH gap (chunks halved), which this GPU-only sim does not model.
Timing-only (steel correctness is PR #621's gates); buffers sized for the deepest n_kv,
warmup per chunk, best-of-3 rounds.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge \
      ../attention_forge/grouped_fa_chunked_sim.mojo
"""
from max.gpu.host import DeviceContext
from std.time import perf_counter_ns
from grouped_fa_q8_k32_h2_sg8 import _attn_grouped_fa_kernel

comptime _H_Q: Int = 16
comptime _H_KV: Int = 8
comptime _D: Int = 128
comptime _KBS: Int = 32
comptime _TILE: Int = 1024


def _fill_f16(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float16(raw)))
    return o^


def sim_prefill(ctx: DeviceContext, total_tokens: Int, tile: Int) raises:
    """Sum steel attention over all `tile`-row chunks of a `total_tokens` production prefill, each
    measured at its real (n_q, n_kv, offset) shape."""
    var h_q = _H_Q
    var n_chunks = (total_tokens + tile - 1) // tile
    var n_blocks_max = (total_tokens + _KBS - 1) // _KBS
    var scale = Float32(1.0 / Float64(_D) ** 0.5)

    var q_buf = ctx.enqueue_create_buffer[DType.float16](tile * h_q * _D)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](_H_KV * n_blocks_max * _D * _KBS)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](_H_KV * n_blocks_max * _KBS * _D)
    var out_buf = ctx.enqueue_create_buffer[DType.float32](tile * h_q * _D)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * tile)
    var q64 = _fill_f16(tile * h_q * _D, 3)
    var k64 = _fill_f16(_H_KV * n_blocks_max * _D * _KBS, 11)
    var v64 = _fill_f16(_H_KV * n_blocks_max * _KBS * _D, 29)
    with q_buf.map_to_host() as h:
        for i in range(tile * h_q * _D):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(_H_KV * n_blocks_max * _D * _KBS):
            h[i] = Float16(k64[i])
    with v_buf.map_to_host() as h:
        for i in range(_H_KV * n_blocks_max * _KBS * _D):
            h[i] = Float16(v64[i])
    ctx.synchronize()

    var attn_total_ms = 0.0
    for c in range(n_chunks):
        var offset = c * tile
        var n_q = tile if total_tokens - offset >= tile else total_tokens - offset
        var n_kv = offset + n_q
        var n_blocks = (n_kv + _KBS - 1) // _KBS
        var grid = (n_q + 31) // 32 * h_q
        var reps = 20 if n_kv <= 2048 else (10 if n_kv <= 4096 else 5)

        for _ in range(3):
            ctx.enqueue_function[_attn_grouped_fa_kernel](
                out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
                q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
                Int64(n_q), Int64(n_kv), Int64(h_q), Int64(_H_KV),
                scale, Int64(offset), Int64(n_blocks),
                grid_dim=grid, block_dim=128)
        ctx.synchronize()

        var best = -1.0
        for _ in range(3):
            var t0 = perf_counter_ns()
            for _ in range(reps):
                ctx.enqueue_function[_attn_grouped_fa_kernel](
                    out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
                    q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
                    Int64(n_q), Int64(n_kv), Int64(h_q), Int64(_H_KV),
                    scale, Int64(offset), Int64(n_blocks),
                    grid_dim=grid, block_dim=128)
            ctx.synchronize()
            var t1 = perf_counter_ns()
            var ms = Float64(t1 - t0) / 1.0e6 / Float64(reps)
            if best < 0.0 or ms < best:
                best = ms
        attn_total_ms += best
        print("  [chunk-sim] chunk ", c, " n_kv=", n_kv, " attn=", best, "ms")
    print("  [chunk-sim] tile=", tile, " total_tokens=", total_tokens, " chunks=", n_chunks,
          " attention-total=", attn_total_ms, "ms (per layer)")


def main() raises:
    var ctx = DeviceContext()
    print("=== chunked-prefill attention simulation (steel): 8K tile sweep 512..8192 (production now 2048) ===")
    sim_prefill(ctx, 8192, 512)
    sim_prefill(ctx, 8192, 1024)
    sim_prefill(ctx, 8192, 2048)
    sim_prefill(ctx, 8192, 4096)
    sim_prefill(ctx, 8192, 8192)
    print("done")
