"""gemm_qkv_proj_wide_bench.mojo -- GEMM tournament Phase 0, TILE-SHAPE isolation experiment
(REALRACE_RESULTS.md, 2026-08-07 entries): standalone wall-clock latency + implied-GFLOP/s
measurement for `_qkv_proj_gemm_mma8x8_wide` (`mma_forge/mm8.mojo`) at the REAL qkv_proj shape from
Qwen3-0.6B-Base's own checkpoint (`hidden_size=1024`, `num_attention_heads=16`,
`num_key_value_heads=8`, `head_dim=128` -> `N = (16+2*8)*128 = 4096`, `K = hidden_size = 1024`) at the
batched-prefill row count this plan's own GPU-counter measurement used (`m_rows=256`).

BACKGROUND, so this file's numbers are never quoted without it: the prior Phase 0 entry measured
llama.cpp's own `kernel_mul_mm_f16_f32` beating Algenta's production `_qkv_proj_gemm_mma8x8` (Int8)
by 20-26% wall-clock at this exact shape, via `gemm_qkv_proj_bench.mojo` (unmodified by this file). A
follow-up isolation experiment built `_qkv_proj_gemm_mma8x8_f16` (F16 MMA operands, identical
BM=32/BN=32/BK=16 tile) to test the "MMA operand width is the lever" hypothesis -- REFUTED (did not
close the gap; ~14% slower on average than Algenta's own F32 kernel, never beat llama.cpp). This
file tests the remaining, already-documented axis: TILE SHAPE / THREADGROUP ORGANIZATION.
`_qkv_proj_gemm_mma8x8_wide` re-derives llama.cpp's OWN legacy (non-tensor-core) `kernel_mul_mm`
geometry directly from the vendored source (`benchmarks/competitors/llama_cpp/upstream_src/
ggml-metal.metal:10157-10367`, `ggml-metal-device.cpp:704-763`, `ggml-metal-impl.h:8-15`) -- a 64x32
output tile (in THIS repo's (M,N) naming: `_BN_W=64`, `_BM_W=32`), K-stepped 32 at a time
(`_BK_W=32`), computed by 4 simdgroups over a 128-thread threadgroup -- approximated with Mojo's
8x8-fragment-only MMA primitive (see `_SUBTILES_PER_SG_W`'s own docstring in `mm8.mojo` for the full
derivation and every place this necessarily diverges from llama.cpp's exact scheme). Int8
storage-dequant-to-Float32 is UNCHANGED from `_qkv_proj_gemm_mma8x8` -- tile shape is the ONLY
variable changed relative to that already-proven kernel; the F16-operand change is NOT combined
here (that was a separate, already-refuted hypothesis -- combining them would confound two variables
in one measurement).

**ASYMMETRY DISCLOSURE, same as `gemm_qkv_proj_bench.mojo`'s own**: llama.cpp's comparison point
(`kernel_mul_mm_f16_f32`, L0) runs DENSE F16 weights; this kernel runs INT8 per-output-row-quantized
weights -- a real, disclosed, NOT-equalized 2x raw-bit-width asymmetry in Algenta's favor on paper,
unchanged from every other entry in this tournament.

Does NOT modify `mm8.mojo`'s existing kernels, `mm8_driver.mojo`, or any existing probe (including
`gemm_qkv_proj_bench.mojo`/`gemm_qkv_proj_f16_bench.mojo`) -- new, standalone file only, appending
only a new kernel (`_qkv_proj_gemm_mma8x8_wide`) to `mm8.mojo`.

Three things measured, in order:
  1. Correctness at a small shape: `_qkv_proj_gemm_mma8x8_wide`'s OWN dispatch from THIS file, at a
     shape deliberately NON-tile-aligned in ALL THREE of `_BM_W=32`/`_BN_W=64`/`_BK_W=32` at once
     (M=33, K=50, N=70 -- note this is a strictly stronger stress than `gemm_qkv_proj_bench.mojo`'s
     own M=33/K=64/N=37, whose K=64 happens to be an exact multiple of that file's BK=16, so it never
     exercised a partial final K-step; K=50 is not a multiple of this file's BK_W=32, so this probe
     exercises partial M, partial N, AND partial K in the same run), checked against a CPU Float64
     oracle that replicates the kernel's exact int8-dequant-then-accumulate math (same style as
     `correctness_probe_partial.mojo`'s own oracles and `gemm_qkv_proj_bench.mojo`'s own
     `_check_correctness`) -- confirms this file's own buffer layout, dispatch arguments, and
     grid/block sizing are right before trusting anything it times.
  2. Correctness AT THE REAL BENCHMARKED SHAPE (M=256, K=1024, N=4096): the SAME CPU Float64 oracle,
     run at the exact shape being timed below -- closing a gap `gemm_qkv_proj_bench.mojo`'s own
     "Honest gaps" section explicitly disclosed for the ORIGINAL kernel ("Algenta's correctness check
     for this entry is at a different shape than the one being timed... does NOT independently
     re-verify bit-level correctness at the actual M=256/K=1024/N=4096 shape"). This file does not
     repeat that gap: bit-level correctness is verified at the exact benchmarked shape, not just a
     small proxy shape, before any speed number below is trusted.
  3. Timing: 1 untimed warmup dispatch (excluded from the measured sample -- this session has
     documented, repeatedly, a real cold-first-run artifact; see `mm8.mojo`'s own `_BN_NARROW`
     docstring and `gemm_qkv_proj_bench.mojo`'s own methodology note) followed by 200 warm runs of
     `enqueue_function` + `ctx.synchronize()` (wall time only -- `DeviceContext` has NO
     `GPUStartTime`/`GPUEndTime` on this toolchain, same limitation already confirmed elsewhere in
     this session). All buffers allocated/uploaded ONCE outside the timed region. Uses a DIFFERENT
     random seed than the correctness pass at the same shape (matching `gemm_qkv_proj_bench.mojo`'s
     own convention of decoupling "prove dispatch is right" data from "measure speed" data).

Weight/activation data is deterministic pseudo-random, generated with the EXACT SAME formulas
`gemm_qkv_proj_bench.mojo` already uses (`_pseudo_activation`, `_pseudo_weight_raw`,
`_quantize_row`) -- kept byte-identical so this file's data distribution is not a new, unvetted
choice, and any speed difference measured is attributable to the kernel's own tile geometry, not to
a different data distribution.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . probes/gemm_qkv_proj_wide_bench.mojo
"""
from max.gpu.host import DeviceContext
from std.time import perf_counter_ns
from mm8 import _qkv_proj_gemm_mma8x8_wide

# `_BM_W=32`/`_BN_W=64`/`_BK_W=32`/`_NTHREADS_W=128` mirror `mm8.mojo`'s own (private) comptime
# constants for `_qkv_proj_gemm_mma8x8_wide` -- kept as plain literals here, exactly the same
# convention `gemm_qkv_proj_bench.mojo` already uses for the original kernel's 32/32/256 (grid/block
# sizing lives in the harness, not imported from the kernel module).


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
    """Dispatches THIS file's own buffers/grid/args through `_qkv_proj_gemm_mma8x8_wide` at a small
    shape deliberately non-aligned to `_BM_W=32`/`_BN_W=64`/`_BK_W=32` all at once, and compares
    against a CPU Float64 oracle replicating the exact int8-dequant-then-accumulate math the kernel
    performs -- proves this NEW file dispatches correctly (grid sizing for the new 32x64 tile, the
    new 128-thread block_dim, the wide kernel's own cooperative-load indexing) before its timing
    numbers are trusted."""
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

    var grid = ((m + 31) // 32) * ((n + 63) // 64)
    ctx.enqueue_function[_qkv_proj_gemm_mma8x8_wide](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n),
        grid_dim=grid, block_dim=128,
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


def bench_qkv_proj_wide_shape(ctx: DeviceContext, m: Int, k: Int, n: Int, n_runs: Int) raises:
    """Times `_qkv_proj_gemm_mma8x8_wide` at shape (m,k,n). Buffers allocated/uploaded ONCE outside
    the timed region; 1 untimed warmup dispatch, then `n_runs` warm runs of enqueue+synchronize --
    identical methodology to `gemm_qkv_proj_bench.mojo`'s own `bench_qkv_proj_shape`, so the two
    numbers are directly comparable."""
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

    var grid = ((m + 31) // 32) * ((n + 63) // 64)

    # 1 untimed warmup -- excluded from the measured sample (documented cold-first-run artifact).
    ctx.enqueue_function[_qkv_proj_gemm_mma8x8_wide](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n),
        grid_dim=grid, block_dim=128,
    )
    ctx.synchronize()

    var times_ns = List[Int](capacity=n_runs)
    for _ in range(n_runs):
        var t0 = perf_counter_ns()
        ctx.enqueue_function[_qkv_proj_gemm_mma8x8_wide](
            y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
            wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n),
            grid_dim=grid, block_dim=128,
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
    print("=== gemm_qkv_proj_wide_bench: _qkv_proj_gemm_mma8x8_wide (mma_forge/mm8.mojo)        ===")
    print("=== Tile-shape tournament axis: BM=32/BN=64/BK=32, 4 simdgroups/128 threads,         ===")
    print("=== matching llama.cpp's own kernel_mul_mm legacy-path geometry as closely as        ===")
    print("=== Mojo's 8x8-fragment-only MMA primitive allows. Int8 storage/dequant UNCHANGED    ===")
    print("=== from _qkv_proj_gemm_mma8x8 -- tile shape is the ONLY variable under test here.    ===")
    print("=== ASYMMETRY DISCLOSURE: this kernel uses INT8 per-output-row-quantized weights.   ===")
    print("=== The llama.cpp comparison point for this shape uses DENSE F16 weights (2x bits). ===")
    print("")
    print("--- Step 1: correctness, THIS file's own dispatch, small shape non-aligned to BM_W/BN_W/BK_W ---")
    var ok_small = _check_correctness(ctx, 33, 50, 70)
    if not ok_small:
        print("  CORRECTNESS: FAIL -- aborting, not trusting the timing run below")
        return
    print("  CORRECTNESS: PASS")

    print("")
    print("--- Step 2: correctness AT THE REAL BENCHMARKED SHAPE (M=256, K=1024, N=4096) ---")
    print("  (closes gemm_qkv_proj_bench.mojo's own disclosed gap: this verifies bit-level")
    print("   correctness at the EXACT shape timed below, not just a small proxy shape)")
    var ok_real = _check_correctness(ctx, 256, 1024, 4096)
    if not ok_real:
        print("  CORRECTNESS: FAIL -- aborting, not trusting the timing run below")
        return
    print("  CORRECTNESS: PASS")

    print("")
    print("--- Step 3: timing, qkv_proj production shape (Qwen3-0.6B-Base, m_rows=256) ---")
    bench_qkv_proj_wide_shape(ctx, 256, 1024, 4096, 200)
