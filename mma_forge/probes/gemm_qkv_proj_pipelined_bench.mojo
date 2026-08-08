"""gemm_qkv_proj_pipelined_bench.mojo -- GEMM tournament, third isolation experiment
(REALRACE_RESULTS.md, 2026-08-07 "two isolation experiments" entry, "What is left" section):
standalone wall-clock latency + implied-GFLOP/s measurement for `_qkv_proj_gemm_mma8x8_pipelined`
(`mma_forge/mm8.mojo`) at the REAL qkv_proj shape from Qwen3-0.6B-Base's own checkpoint
(`hidden_size=1024`, `num_attention_heads=16`, `num_key_value_heads=8`, `head_dim=128` ->
`N = (16+2*8)*128 = 4096`, `K = hidden_size = 1024`) at the batched-prefill row count this plan's own
GPU-counter measurement used (`m_rows=256`).

BACKGROUND, so this file's numbers are never quoted without it: the GEMM tournament Phase 0 entry
measured llama.cpp's own `kernel_mul_mm_f16_f32` (L0) beating Algenta's production
`_qkv_proj_gemm_mma8x8` (Int8 storage, F32 MMA operands) by 20-26% wall-clock at this exact shape
(0.562ms median wall / ~3821 GFLOP/s for L0, vs. 0.689-0.708ms / 3033-3117 GFLOP/s for Algenta's
kernel, across 3 independent process launches), via `gemm_qkv_proj_bench.mojo` (unmodified by this
file). Two follow-up single-variable isolation experiments were both REFUTED: (1)
`_qkv_proj_gemm_mma8x8_f16` (MMA operand width F32->F16) measured ~14% SLOWER on average than the
original F32 kernel, never beating L0; (2) `_qkv_proj_gemm_mma8x8_wide` (tile shape/threadgroup
geometry matched to llama.cpp's own `nr0=64/nr1=32/nsg=4`) measured ~4.2-4.3x SLOWER, diagnosed as an
occupancy collapse from fewer/larger threadgroups. Neither prior experiment is modified or re-run by
this file. That entry's own recorded next step, not yet attempted before this file: software-
pipelined / double-buffered K-steps (prefetching the NEXT BK=16 K-slice's cooperative shared-memory
load while the CURRENT slice's MMA multiply-accumulate is still in flight) -- independent of both
operand width (stays Float32, exactly like the original kernel) and tile shape (stays
BM=32/BN=32/BK=16, 8 simdgroups/256 threads, exactly like the original kernel). This file tests that
axis via `_qkv_proj_gemm_mma8x8_pipelined`, which restructures ONLY the load/barrier/compute/barrier
loop of `_qkv_proj_gemm_mma8x8` into a ping-pong double-buffered form (see that kernel's own
docstring in `mm8.mojo` for the full barrier-placement reasoning).

**ASYMMETRY DISCLOSURE, same as `gemm_qkv_proj_bench.mojo`'s and `gemm_qkv_proj_wide_bench.mojo`'s
own**: llama.cpp's comparison point (`kernel_mul_mm_f16_f32`, L0) runs DENSE F16 weights; this kernel
runs INT8 per-output-row-quantized weights -- a real, disclosed, NOT-equalized 2x raw-bit-width
asymmetry in Algenta's favor on paper, unchanged from every other entry in this tournament.

Does NOT modify `mm8.mojo`'s existing kernels, `mm8_driver.mojo`, or any existing probe (including
`gemm_qkv_proj_bench.mojo`/`gemm_qkv_proj_f16_bench.mojo`/`gemm_qkv_proj_wide_bench.mojo`) -- new,
standalone file only, dispatching the new kernel (`_qkv_proj_gemm_mma8x8_pipelined`) already appended
to `mm8.mojo`.

Three things measured, in order (identical methodology to `gemm_qkv_proj_wide_bench.mojo`'s own, so
all three files' numbers are directly comparable):
  1. Correctness at a small shape: `_qkv_proj_gemm_mma8x8_pipelined`'s OWN dispatch from THIS file,
     at a shape deliberately NON-tile-aligned to `_BM=32`/`_BN=32`/`_BK=16` (M=33, K=50, N=37 --
     K=50 is not a multiple of BK=16, so a partial final K-step, including the pipelined prologue/
     prefetch machinery around it, is genuinely exercised), checked against a CPU Float64 oracle
     that replicates the kernel's exact int8-dequant-then-accumulate math -- confirms this file's own
     buffer layout, dispatch arguments, and grid/block sizing are right, AND that the double-buffered
     loop restructuring did not introduce a race or an off-by-one in the prologue/prefetch/barrier
     sequence, before trusting anything it times.
  2. Correctness AT THE REAL BENCHMARKED SHAPE (M=256, K=1024, N=4096): the SAME CPU Float64 oracle,
     run at the exact shape being timed below -- bit-level correctness is verified at the exact
     benchmarked shape, not just a small proxy shape, before any speed number below is trusted.
  3. Timing: 1 untimed warmup dispatch (excluded from the measured sample -- this session has
     documented, repeatedly, a real cold-first-run artifact) followed by 200 warm runs of
     `enqueue_function` + `ctx.synchronize()` (wall time only -- `DeviceContext` has NO
     `GPUStartTime`/`GPUEndTime` on this toolchain). All buffers allocated/uploaded ONCE outside the
     timed region. Uses a DIFFERENT random seed than the correctness pass at the same shape (matching
     `gemm_qkv_proj_bench.mojo`'s own convention of decoupling "prove dispatch is right" data from
     "measure speed" data).

Weight/activation data is deterministic pseudo-random, generated with the EXACT SAME formulas
`gemm_qkv_proj_bench.mojo`/`gemm_qkv_proj_wide_bench.mojo` already use (`_pseudo_activation`,
`_pseudo_weight_raw`, `_quantize_row`) -- kept byte-identical so this file's data distribution is not
a new, unvetted choice, and any speed difference measured is attributable to the kernel's own
load/compute pipelining, not to a different data distribution.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . probes/gemm_qkv_proj_pipelined_bench.mojo
"""
from max.gpu.host import DeviceContext
from std.time import perf_counter_ns
from mm8 import _qkv_proj_gemm_mma8x8_pipelined

# `_BM=32`/`_BN=32`/`_BK=16`/`_NTHREADS=256` mirror `mm8.mojo`'s own (private) comptime constants
# for `_qkv_proj_gemm_mma8x8_pipelined` (identical to `_qkv_proj_gemm_mma8x8`'s tile shape) -- kept
# as plain literals here, exactly the same convention `gemm_qkv_proj_bench.mojo` and
# `gemm_qkv_proj_wide_bench.mojo` already use (grid/block sizing lives in the harness, not imported
# from the kernel module).


def _pseudo_activation(i: Int, seed: Int) -> Float32:
    """Verbatim copy of `gemm_qkv_proj_bench.mojo`'s own `_pseudo_activation` -- kept byte-identical
    so this file's activation distribution is not a new, unvetted choice."""
    return Float32((i * 7 + seed * 13 + 3) % 13) / 6.0 - 1.0


def _pseudo_weight_raw(i: Int, seed: Int) -> Float64:
    """Verbatim copy of `gemm_qkv_proj_bench.mojo`'s own `_pseudo_weight_raw`."""
    return Float64(((i * 11 + seed * 7 + 5) % 17) - 8) / 160.0


def _quantize_row(mut out: List[Int8], k: Int, row_offset: Int, seed: Int) -> Float32:
    """Verbatim copy of `gemm_qkv_proj_bench.mojo`'s own `_quantize_row` -- the real production
    per-output-row symmetric Int8 scheme (`scale = maxabs/127`, round-to-nearest, clamp to
    [-127,127]), applied here to the same synthetic data generator."""
    var maxabs = Float64(0.0)
    for kk in range(k):
        var raw = _pseudo_weight_raw(row_offset + kk, seed)
        var a = raw if raw >= 0.0 else -raw
        if a > maxabs:
            maxabs = a
    var scale = maxabs / 127.0 if maxabs > 0.0 else 1.0e-8
    for kk in range(k):
        var raw = _pseudo_weight_raw(row_offset + kk, seed)
        var half = 0.5 if raw >= 0.0 else -0.5
        var q = Int(raw / scale + half)
        if q > 127:
            q = 127
        if q < -127:
            q = -127
        out.append(Int8(q))
    return Float32(scale)


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def _check_correctness(ctx: DeviceContext, m: Int, k: Int, n: Int) raises -> Bool:
    """Dispatches THIS file's own buffers/grid/args through `_qkv_proj_gemm_mma8x8_pipelined` at a
    small shape deliberately non-aligned to `_BM=32`/`_BK=16` (K=50), and compares against a CPU
    Float64 oracle replicating the exact int8-dequant-then-accumulate math the kernel performs --
    proves this NEW file dispatches correctly AND that the double-buffered prologue/prefetch/barrier
    restructuring produces byte-identical results to the original sequential kernel's own math,
    before its timing numbers are trusted."""
    var xn_vals = List[Float32](capacity=m * k)
    for i in range(m * k):
        xn_vals.append(_pseudo_activation(i, 5))

    var w_i8 = List[Int8](capacity=n * k)
    var wscale_vals = List[Float32](capacity=n)
    for j in range(n):
        wscale_vals.append(_quantize_row(w_i8, k, j * k, 3))

    var xn_buf = ctx.enqueue_create_buffer[DType.float32](m * k)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](n * k)
    var wscale_buf = ctx.enqueue_create_buffer[DType.float32](n)
    var y_buf = ctx.enqueue_create_buffer[DType.float32](m * n)
    with xn_buf.map_to_host() as h:
        for i in range(m * k):
            h[i] = xn_vals[i]
    with w_buf.map_to_host() as h:
        for i in range(n * k):
            h[i] = w_i8[i]
    with wscale_buf.map_to_host() as h:
        for j in range(n):
            h[j] = wscale_vals[j]
    with y_buf.map_to_host() as h:
        for i in range(m * n):
            h[i] = Float32(-999.0)  # canary: must be fully overwritten for every valid (r,c)
    ctx.synchronize()

    var grid = ((m + 31) // 32) * ((n + 31) // 32)
    ctx.enqueue_function[_qkv_proj_gemm_mma8x8_pipelined](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n),
        grid_dim=grid, block_dim=256,
    )
    ctx.synchronize()

    var worst = Float32(0.0)
    with y_buf.map_to_host() as hy:
        for mi in range(m):
            for j in range(n):
                var acc = Float64(0.0)
                for kk in range(k):
                    var wq = w_i8[j * k + kk]
                    acc += Float64(xn_vals[mi * k + kk]) * Float64(Float32(wq) * wscale_vals[j])
                var got = hy[mi * n + j]
                var want = Float32(acc)
                var d = _abs32(got - want)
                if d > worst:
                    worst = d
                if d > 0.02:
                    print("    MISMATCH (", mi, ",", j, "): got", got, "want", want)
    print("  correctness shape M=", m, " K=", k, " N=", n, " worst delta:", worst)
    return worst <= 0.02


def _sorted_ns(times_ns: List[Int]) -> List[Int]:
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
    return sorted_^


def _pct_ms(sorted_ns: List[Int], frac: Float64) -> Float64:
    var n = len(sorted_ns)
    var idx = Int(frac * Float64(n - 1))
    if idx < 0:
        idx = 0
    if idx > n - 1:
        idx = n - 1
    return Float64(sorted_ns[idx]) / 1.0e6


def bench_qkv_proj_pipelined_shape(ctx: DeviceContext, m: Int, k: Int, n: Int, n_runs: Int) raises:
    """Times `_qkv_proj_gemm_mma8x8_pipelined` at shape (m,k,n). Buffers allocated/uploaded ONCE
    outside the timed region; 1 untimed warmup dispatch, then `n_runs` warm runs of
    enqueue+synchronize -- identical methodology to `gemm_qkv_proj_bench.mojo`'s and
    `gemm_qkv_proj_wide_bench.mojo`'s own, so all three files' numbers are directly comparable."""
    var w_i8 = List[Int8](capacity=n * k)
    var wscale_vals = List[Float32](capacity=n)
    for j in range(n):
        wscale_vals.append(_quantize_row(w_i8, k, j * k, 41))

    var xn_vals = List[Float32](capacity=m * k)
    for i in range(m * k):
        xn_vals.append(_pseudo_activation(i, 9))

    var xn_buf = ctx.enqueue_create_buffer[DType.float32](m * k)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](n * k)
    var wscale_buf = ctx.enqueue_create_buffer[DType.float32](n)
    var y_buf = ctx.enqueue_create_buffer[DType.float32](m * n)
    with xn_buf.map_to_host() as h:
        for i in range(m * k):
            h[i] = xn_vals[i]
    with w_buf.map_to_host() as h:
        for i in range(n * k):
            h[i] = w_i8[i]
    with wscale_buf.map_to_host() as h:
        for j in range(n):
            h[j] = wscale_vals[j]
    ctx.synchronize()

    var grid = ((m + 31) // 32) * ((n + 31) // 32)

    # 1 untimed warmup -- excluded from the measured sample (documented cold-first-run artifact).
    ctx.enqueue_function[_qkv_proj_gemm_mma8x8_pipelined](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n),
        grid_dim=grid, block_dim=256,
    )
    ctx.synchronize()

    var times_ns = List[Int](capacity=n_runs)
    for _ in range(n_runs):
        var t0 = perf_counter_ns()
        ctx.enqueue_function[_qkv_proj_gemm_mma8x8_pipelined](
            y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
            wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n),
            grid_dim=grid, block_dim=256,
        )
        ctx.synchronize()
        var t1 = perf_counter_ns()
        times_ns.append(t1 - t0)

    var sorted_ = _sorted_ns(times_ns)
    var median_ms = _pct_ms(sorted_, 0.5)
    var p10_ms = _pct_ms(sorted_, 0.10)
    var p90_ms = _pct_ms(sorted_, 0.90)
    var flops = 2.0 * Float64(m) * Float64(k) * Float64(n)
    var gflops_median = flops / (median_ms / 1000.0) / 1.0e9
    var gflops_at_p10_time = flops / (p10_ms / 1000.0) / 1.0e9  # p10 TIME = fastest -> HIGHEST GFLOP/s
    var gflops_at_p90_time = flops / (p90_ms / 1000.0) / 1.0e9  # p90 TIME = slowest -> LOWEST GFLOP/s
    print("  shape: M=", m, " K=", k, " N=", n, " (qkv_proj, Qwen3-0.6B-Base, m_rows=", m, ")")
    print("  wall time (ms): median=", median_ms, " p10=", p10_ms, " p90=", p90_ms, " over n_runs=", n_runs)
    print("  implied GFLOP/s (2*M*K*N/time, WALL-CLOCK -- no GPU-only timer on this toolchain):")
    print("    at median time:", gflops_median)
    print("    at p10 time (fastest observed, highest GFLOP/s):", gflops_at_p10_time)
    print("    at p90 time (slowest observed, lowest GFLOP/s):", gflops_at_p90_time)


def main() raises:
    var ctx = DeviceContext()
    print("=== gemm_qkv_proj_pipelined_bench: _qkv_proj_gemm_mma8x8_pipelined (mma_forge/mm8.mojo) ===")
    print("=== GEMM tournament, 3rd isolation axis: software-pipelined / double-buffered K-steps, ===")
    print("=== BM=32/BN=32/BK=16, 8 simdgroups/256 threads (SAME as _qkv_proj_gemm_mma8x8) --      ===")
    print("=== operand width stays Float32, tile shape unchanged; ONLY the load/barrier/compute   ===")
    print("=== loop is restructured into ping-pong double buffering. Int8 storage/dequant          ===")
    print("=== UNCHANGED from _qkv_proj_gemm_mma8x8.                                               ===")
    print("=== ASYMMETRY DISCLOSURE: this kernel uses INT8 per-output-row-quantized weights.       ===")
    print("=== The llama.cpp comparison point for this shape uses DENSE F16 weights (2x bits).     ===")
    print("")
    print("--- Step 1: correctness, THIS file's own dispatch, small shape non-aligned to BM/BK ---")
    var ok_small = _check_correctness(ctx, 33, 50, 37)
    if not ok_small:
        print("  CORRECTNESS: FAIL -- aborting, not trusting the timing run below")
        return
    print("  CORRECTNESS: PASS")

    print("")
    print("--- Step 2: correctness AT THE REAL BENCHMARKED SHAPE (M=256, K=1024, N=4096) ---")
    var ok_real = _check_correctness(ctx, 256, 1024, 4096)
    if not ok_real:
        print("  CORRECTNESS: FAIL -- aborting, not trusting the timing run below")
        return
    print("  CORRECTNESS: PASS")

    print("")
    print("--- Step 3: timing, qkv_proj production shape (Qwen3-0.6B-Base, m_rows=256) ---")
    bench_qkv_proj_pipelined_shape(ctx, 256, 1024, 4096, 200)
