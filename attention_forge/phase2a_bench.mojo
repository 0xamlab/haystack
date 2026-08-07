"""attention_forge.phase2a_bench -- Attention Compiler Plan v1.0, Phase 2A Round 1: wall-clock
operator latency for the parity replica (L1) and the confirmed-correct tournament candidates,
measured ONE AT A TIME (never concurrently -- see reference_mojo_gpu_timing_gap.md /
REALRACE_RESULTS.md's own Phase 1 entry on why concurrent/parallel GPU benchmarking would
contaminate the numbers) so results are directly comparable to each other and to L0's own
fa_operator_harness.m measurement at the same tiny single-tile shape, plus a second, larger shape
(256-token single-shot prefill) matching the plan's own Definition-of-Victory latency metric.

Buffers are allocated ONCE per candidate, outside the timed region (matching parity_replica_driver.
mojo's own bench_operator_latency methodology) -- only enqueue_function + synchronize is timed.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge -I ../mojo/engine ../attention_forge/phase2a_bench.mojo
"""
from max.gpu.host import DeviceContext
from std.time import perf_counter_ns
from parity_replica import _attn_parity_replica_kernel
from grouped_fa_q8_k32_h2_sg8 import _attn_grouped_fa_kernel
from splitk_fa import _attn_splitk_partial_kernel, _attn_splitk_merge_kernel
from candidate_b_score_slab import (
    _score_slab_qk_kernel,
    _b1_softmax_kernel,
    _b1_pv_kernel,
    _b2_stats_kernel,
    _b2_pv_kernel,
    _b3_fused_kernel,
)


def _pseudo_f16(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float16(raw)))
    return o^


def _median_ms(times_ns: List[Int]) -> Float64:
    var n = len(times_ns)
    var sorted_ = List[Int](capacity=n)
    for i in range(n):
        sorted_.append(times_ns[i])
    for i in range(1, n):
        var key = sorted_[i]
        var j = i - 1
        while j >= 0 and sorted_[j] > key:
            sorted_[j + 1] = sorted_[j]
            j -= 1
        sorted_[j + 1] = key
    return Float64(sorted_[n // 2]) / 1.0e6


def bench_parity_replica(ctx: DeviceContext, n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int, n_runs: Int) raises -> Float64:
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
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    ctx.synchronize()

    var scale = 1.0 / Float64(d) ** 0.5
    var n_q_blocks = (n_tok_q + 7) // 8
    var grid = n_q_blocks * h_q

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
    return _median_ms(times_ns)


def bench_candidate_a(ctx: DeviceContext, n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int, n_runs: Int) raises -> Float64:
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
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    ctx.synchronize()

    var scale = 1.0 / Float64(d) ** 0.5
    var n_q_blocks = (n_tok_q + 7) // 8
    var grid = n_q_blocks * (h_q // 2)

    var times_ns = List[Int](capacity=n_runs)
    for _ in range(n_runs):
        var t0 = perf_counter_ns()
        ctx.enqueue_function[_attn_grouped_fa_kernel](
            out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
            Float32(scale), Int64(offset),
            grid_dim=grid, block_dim=256,
        )
        ctx.synchronize()
        var t1 = perf_counter_ns()
        times_ns.append(t1 - t0)
    return _median_ms(times_ns)


def bench_candidate_c(ctx: DeviceContext, n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int, n_splits: Int, n_runs: Int) raises -> Float64:
    """Candidate C (associative grouped-head split-K, H_TILE=2, K_TILE=32): two dispatches per
    call -- the partial kernel (one threadgroup per (q_block, sibling-pair, split)) then the merge
    kernel (one threadgroup per (row, head)) -- timed together as ONE operator call, matching how
    every other candidate here is timed as the full cost of one attention operator invocation."""
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
    var n_pairs = h_q // 2
    var grid_partial = n_q_blocks * n_pairs * n_splits
    var grid_merge = n_tok_q * h_q

    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    var m_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits)
    var l_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits)
    var o_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * n_splits * d)
    ctx.synchronize()

    var times_ns = List[Int](capacity=n_runs)
    for _ in range(n_runs):
        var t0 = perf_counter_ns()
        ctx.enqueue_function[_attn_splitk_partial_kernel](
            m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
            Float32(scale), Int64(offset), Int64(n_splits),
            grid_dim=grid_partial, block_dim=256,
        )
        ctx.enqueue_function[_attn_splitk_merge_kernel](
            out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
            m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            Int64(n_tok_q), Int64(h_q), Int64(n_splits),
            grid_dim=grid_merge, block_dim=128,
        )
        ctx.synchronize()
        var t1 = perf_counter_ns()
        times_ns.append(t1 - t0)
    return _median_ms(times_ns)


def bench_candidate_b(ctx: DeviceContext, variant: String, n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int, n_runs: Int) raises -> Float64:
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
    var scores_buf = ctx.enqueue_create_buffer[DType.float16](h_q * n_tok_q * n_tok_k)
    var stats_m_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    var stats_linv_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    ctx.synchronize()

    var times_ns = List[Int](capacity=n_runs)
    for _ in range(n_runs):
        var t0 = perf_counter_ns()
        if variant == "b1":
            ctx.enqueue_function[_score_slab_qk_kernel](
                scores_buf.unsafe_ptr(), q_buf.unsafe_ptr(), k_buf.unsafe_ptr(),
                Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
                Float32(scale), Int64(offset), grid_dim=grid, block_dim=128,
            )
            ctx.enqueue_function[_b1_softmax_kernel](
                scores_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
                Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(offset), grid_dim=grid, block_dim=128,
            )
            ctx.enqueue_function[_b1_pv_kernel](
                out_buf.unsafe_ptr(), scores_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
                Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv), Int64(offset), grid_dim=grid, block_dim=128,
            )
        elif variant == "b2":
            ctx.enqueue_function[_score_slab_qk_kernel](
                scores_buf.unsafe_ptr(), q_buf.unsafe_ptr(), k_buf.unsafe_ptr(),
                Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
                Float32(scale), Int64(offset), grid_dim=grid, block_dim=128,
            )
            ctx.enqueue_function[_b2_stats_kernel](
                scores_buf.unsafe_ptr(), lse_buf.unsafe_ptr(), stats_m_buf.unsafe_ptr(), stats_linv_buf.unsafe_ptr(),
                Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(offset), grid_dim=grid, block_dim=128,
            )
            ctx.enqueue_function[_b2_pv_kernel](
                out_buf.unsafe_ptr(), scores_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
                stats_m_buf.unsafe_ptr(), stats_linv_buf.unsafe_ptr(),
                Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv), Int64(offset), grid_dim=grid, block_dim=128,
            )
        else:
            ctx.enqueue_function[_b3_fused_kernel](
                out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
                q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
                Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
                Float32(scale), Int64(offset), grid_dim=grid, block_dim=128,
            )
        ctx.synchronize()
        var t1 = perf_counter_ns()
        times_ns.append(t1 - t0)
    return _median_ms(times_ns)


def main() raises:
    var ctx = DeviceContext()
    var n_runs = 200

    print("=== Phase 2A Round 1: operator wall-latency, one candidate at a time (no concurrent GPU use) ===")
    print("")
    print("--- shape A: single-tile, matches L0's fa_operator_harness.m (Q_ROWS=8,N_KV=64,H_Q=16,H_KV=8,DK=DV=128) ---")
    print("  L1 parity replica:  ", bench_parity_replica(ctx, 8, 64, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate A (q8/k32/h2/sg8):  ", bench_candidate_a(ctx, 8, 64, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate B1:  ", bench_candidate_b(ctx, "b1", 8, 64, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate B2:  ", bench_candidate_b(ctx, "b2", 8, 64, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate B3:  ", bench_candidate_b(ctx, "b3", 8, 64, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate C (splitk h2/k32, n_splits=2):  ", bench_candidate_c(ctx, 8, 64, 16, 8, 128, 0, 2, n_runs), "ms")

    print("")
    print("--- shape B: 256-token single-shot prefill (n_tok_q=256, n_tok_k=256, offset=0) ---")
    print("  L1 parity replica:  ", bench_parity_replica(ctx, 256, 256, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate A (q8/k32/h2/sg8):  ", bench_candidate_a(ctx, 256, 256, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate B1:  ", bench_candidate_b(ctx, "b1", 256, 256, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate B2:  ", bench_candidate_b(ctx, "b2", 256, 256, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate B3:  ", bench_candidate_b(ctx, "b3", 256, 256, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate C (splitk h2/k32, n_splits=2):  ", bench_candidate_c(ctx, 256, 256, 16, 8, 128, 0, 2, n_runs), "ms")

    print("")
    print("--- shape C: 128-row (Round 1 hard-gate row count) ---")
    print("  L1 parity replica:  ", bench_parity_replica(ctx, 128, 128, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate A (q8/k32/h2/sg8):  ", bench_candidate_a(ctx, 128, 128, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate B1:  ", bench_candidate_b(ctx, "b1", 128, 128, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate B2:  ", bench_candidate_b(ctx, "b2", 128, 128, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate B3:  ", bench_candidate_b(ctx, "b3", 128, 128, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate C (splitk h2/k32, n_splits=2):  ", bench_candidate_c(ctx, 128, 128, 16, 8, 128, 0, 2, n_runs), "ms")

    print("")
    print("--- shape D: 512-row (Round 1 hard-gate row count) ---")
    print("  L1 parity replica:  ", bench_parity_replica(ctx, 512, 512, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate A (q8/k32/h2/sg8):  ", bench_candidate_a(ctx, 512, 512, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate B1:  ", bench_candidate_b(ctx, "b1", 512, 512, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate B2:  ", bench_candidate_b(ctx, "b2", 512, 512, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate B3:  ", bench_candidate_b(ctx, "b3", 512, 512, 16, 8, 128, 0, n_runs), "ms")
    print("  Candidate C (splitk h2/k32, n_splits=2):  ", bench_candidate_c(ctx, 512, 512, 16, 8, 128, 0, 2, n_runs), "ms")
    print("  Candidate C (splitk h2/k32, n_splits=4):  ", bench_candidate_c(ctx, 512, 512, 16, 8, 128, 0, 4, n_runs), "ms")
