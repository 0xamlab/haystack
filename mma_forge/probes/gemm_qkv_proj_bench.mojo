"""gemm_qkv_proj_bench.mojo -- Attention Compiler Plan v1.0, GEMM optimization effort: standalone
wall-clock latency + implied-GFLOP/s measurement for Algenta's OWN production GEMM kernel
(`_qkv_proj_gemm_mma8x8`, `mma_forge/mm8.mojo`) at the REAL qkv_proj shape from Qwen3-0.6B-Base's
own checkpoint (`hidden_size=1024`, `num_attention_heads=16`, `num_key_value_heads=8`,
`head_dim=128` -> `N = (16+2*8)*128 = 4096`, `K = hidden_size = 1024`) at the batched-prefill row
count this plan's own GPU-counter measurement used (`m_rows=256`).

Written to directly compare against this plan's ALREADY-CONFIRMED llama.cpp side of the same
qkv_proj GEMM (dense F16 weights, Metal `kernel_mul_mm_f16_f32`, native `simdgroup_half8x8`
hardware MMA -- see `fa_operator_harness.m`-style teardown notes elsewhere in this effort). STATE
THIS EXPLICITLY, every time this file's numbers are quoted: Algenta's own kernel measured here uses
INT8 per-output-row-quantized weights (symmetric, no zero-point: `scale = maxabs/127` per row,
`dequant = Float32(w_i8) * wscale[row]`, exactly `mm8.mojo`'s own documented scheme) against
llama.cpp's DENSE F16 weights -- a real, already-disclosed 2x raw-bit-width asymmetry, not a bug,
not silently equalized here.

Does NOT modify `mm8.mojo`, `mm8_driver.mojo`, or any existing probe -- new, standalone file only.

Two things measured, in order:
  1. Correctness: `_qkv_proj_gemm_mma8x8`'s OWN dispatch from THIS file, at a small deliberately
     non-32-tile-aligned shape (M=33, K=64, N=37), checked against a CPU Float64 oracle that
     replicates the kernel's exact int8-dequant-then-accumulate math (same style as
     `correctness_probe_partial.mojo`'s own oracles) -- confirms this file's own buffer layout,
     dispatch arguments, and grid/block sizing are right before trusting anything it times. This
     is deliberately independent of (not a rerun of) the existing partial-tile probe: the point is
     to verify THIS file's own dispatch, not to re-verify the kernel (already proven elsewhere).
  2. Timing: 1 untimed warmup dispatch (this session has documented, repeatedly, a real cold-first-
     run artifact -- see `mm8.mojo`'s own `_BN_NARROW` docstring and REALRACE_RESULTS.md's Phase 1
     entry on `reference_mojo_gpu_timing_gap.md` -- so it is excluded from the measured sample, not
     included as run #1) followed by 200 warm runs of `enqueue_function` + `ctx.synchronize()`
     (wall time only -- `DeviceContext` has NO `GPUStartTime`/`GPUEndTime` on this toolchain, a
     limitation already confirmed elsewhere in this session; this file does not claim otherwise).
     All buffers (activations, quantized weights, per-row scales, output) are allocated and
     uploaded ONCE, outside the timed region, matching `phase2a_bench.mojo`'s own methodology.

Weight/activation data is deterministic pseudo-random, NOT drawn from the real checkpoint (a pure
kernel-speed probe does not need real weights to be representative of the kernel's own runtime,
which depends only on shape/dtype, not data values -- flagged here as an explicit, deliberate
choice per this task's own instructions). The activation formula
(`((i*7 + seed*13 + 3) % 13) / 6.0 - 1.0`) is copied verbatim from `correctness_probe_partial.
mojo`'s own `xn_vals` generator for consistency with this repo's existing convention. The weight
scheme mirrors the REAL production quantization this repo already ships (see this module's own
docstring above): raw pseudo-random Float64 values in a small, trained-weight-like range are
generated per (row,k) coordinate, then quantized PER OUTPUT ROW exactly the way `mm8.mojo`'s own
module docstring describes production weights being prepared (`scale = maxabs/127`, round-to-
nearest, clamp to [-127,127]) -- not simplified further, so the quantization arithmetic itself
(not just the GEMM shape) is representative of what the kernel sees in production.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . probes/gemm_qkv_proj_bench.mojo
"""
from max.gpu.host import DeviceContext
from std.time import perf_counter_ns
from mm8 import _qkv_proj_gemm_mma8x8


def _pseudo_activation(i: Int, seed: Int) -> Float32:
    """Verbatim copy of `correctness_probe_partial.mojo`'s own `xn_vals` formula -- kept
    byte-identical so this file's activation distribution is the same one already established
    elsewhere in this repo as a representative post-RMSNorm-ish range, not a new, unvetted choice."""
    return Float32((i * 7 + seed * 13 + 3) % 13) / 6.0 - 1.0


def _pseudo_weight_raw(i: Int, seed: Int) -> Float64:
    """Deterministic pseudo-random 'true' (pre-quantization) weight value, flat index `i` over the
    row-major [N,K] weight matrix. Range ~[-0.05, 0.05) -- a small, trained-weight-like magnitude,
    chosen so per-row `maxabs` (and therefore `wscale`) is representative of real quantized
    checkpoints (values that use only a small fraction of the int8 range would be unrealistic)."""
    return Float64(((i * 11 + seed * 7 + 5) % 17) - 8) / 160.0


def _quantize_row(mut out: List[Int8], k: Int, row_offset: Int, seed: Int) -> Float32:
    """Quantizes ONE output row's `k` raw weight values per the real production scheme
    (`scale = maxabs/127`, round-to-nearest via `+/-0.5` before truncation, clamp to [-127,127]) --
    exactly `mm8.mojo`'s own documented per-row-symmetric int8 scheme, applied here to synthetic
    data instead of a real checkpoint. Appends the quantized row directly into the caller's `out`
    list (avoids returning an owned `List[Int8]` by value, which this toolchain's copy-checker
    rejects without an explicit transfer)."""
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
    """Dispatches THIS file's own buffers/grid/args through `_qkv_proj_gemm_mma8x8` at a small
    non-32-tile-aligned shape and compares against a CPU Float64 oracle that replicates the exact
    int8-dequant-then-accumulate math the kernel performs (same style as
    `correctness_probe_partial.mojo`'s own `test_assign` oracle) -- proves this NEW file dispatches
    correctly before its timing numbers are trusted."""
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
    ctx.enqueue_function[_qkv_proj_gemm_mma8x8](
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


def bench_qkv_proj_shape(ctx: DeviceContext, m: Int, k: Int, n: Int, n_runs: Int) raises:
    """Times `_qkv_proj_gemm_mma8x8` at shape (m,k,n). Buffers allocated/uploaded ONCE outside the
    timed region; 1 untimed warmup dispatch, then `n_runs` warm runs of enqueue+synchronize."""
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
    ctx.enqueue_function[_qkv_proj_gemm_mma8x8](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n),
        grid_dim=grid, block_dim=256,
    )
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
    print("=== gemm_qkv_proj_bench: Algenta's own _qkv_proj_gemm_mma8x8 (mma_forge/mm8.mojo) ===")
    print("=== ASYMMETRY DISCLOSURE: this kernel uses INT8 per-output-row-quantized weights.   ===")
    print("=== The llama.cpp comparison point for this shape uses DENSE F16 weights (2x bits). ===")
    print("")
    print("--- Step 1: correctness, THIS file's own dispatch, small non-32-aligned shape ---")
    var ok = _check_correctness(ctx, 33, 64, 37)
    if not ok:
        print("  CORRECTNESS: FAIL -- aborting, not trusting the timing run below")
        return
    print("  CORRECTNESS: PASS")

    print("")
    print("--- Step 2: timing, qkv_proj production shape (Qwen3-0.6B-Base, m_rows=256) ---")
    bench_qkv_proj_shape(ctx, 256, 1024, 4096, 200)
