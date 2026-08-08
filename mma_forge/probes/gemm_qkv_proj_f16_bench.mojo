"""gemm_qkv_proj_f16_bench.mojo -- Attention Compiler Plan v1.0, GEMM tournament Phase 0's own
concrete "next step" (REALRACE_RESULTS.md, 2026-08-07 "GEMM tournament Phase 0" entry): the
isolation experiment for the operand-width hypothesis that entry's roofline analysis raised but did
not yet test. Times/verifies the NEW `_qkv_proj_gemm_mma8x8_f16` kernel (`mma_forge/mm8.mojo`,
appended there, `_qkv_proj_gemm_mma8x8` itself untouched) -- byte-for-byte identical to Algenta's
production `_qkv_proj_gemm_mma8x8` except the shared-memory tiles the hardware MMA op consumes are
`DType.float16` instead of `DType.float32` (Int8 storage + per-output-row dequant on load are
UNCHANGED; the bandwidth advantage stays upstream of the tile).

Does NOT modify `gemm_qkv_proj_bench.mojo`, `mm8_driver.mojo`, or any existing probe -- new,
standalone file only, reusing that file's exact methodology (same pseudo-random generators, same
oracle math, same timing discipline) so the two files' numbers are directly comparable.

Three things measured, in order, mirroring `gemm_qkv_proj_bench.mojo`'s own two-step structure plus
the one extra step that file's own "honest gaps" section flagged as missing (a correctness check at
the REAL benchmarked shape, not just the small one):

  1. Correctness at the SAME small, deliberately non-32-tile-aligned shape (M=33, K=64, N=37)
     `gemm_qkv_proj_bench.mojo` uses, against the SAME CPU Float64 oracle (byte-identical math:
     `acc += Float64(xn) * Float64(Float32(w_i8) * wscale)` -- the oracle intentionally does NOT
     itself narrow to Float16; it represents the full-precision-Float32 "ideal" result, so the F16
     kernel's deviation from it isolates exactly the error the extra F16-narrowing step introduces).

     Tolerance derivation (not copied from the F32 kernel's 0.02 threshold, or from the ledger
     entry's suggested 1e-2..1e-1 range, without justification): Float16 has 10 explicit mantissa
     bits, so round-to-nearest unit roundoff u = 2^-11 ~= 4.883e-4. Both the activation (`xn`) and
     the already-Float32-dequantized weight are independently rounded to Float16 before the
     multiply, so each product term's relative error is bounded by ~2u (one factor of u from each
     operand's narrowing, to first order). This session's own pseudo-random generators bound
     |xn| <= 1.0 (`_pseudo_activation`'s range is exactly [-1.0, 1.0]) and |dequantized weight| <=
     ~0.05 (`_pseudo_weight_raw`'s range is [-0.05, 0.05), and dequantization recovers the
     pre-quantization value to within int8 rounding), so |term| <= ~0.05 for every (row,k) pair in
     this synthetic dataset. A worst-case (fully-correlated-sign) bound on the summed error over k
     terms is then `2u * k * 0.05`:
       - small shape (k=64):   2 * 4.883e-4 * 64   * 0.05 ~= 3.1e-3  -> tolerance set to 1e-2 (~3x margin)
       - real shape  (k=1024): 2 * 4.883e-4 * 1024 * 0.05 ~= 5.0e-2  -> tolerance set to 1e-1 (~2x margin)
     Both land inside the 1e-2..1e-1 range the ledger entry's "concrete next step" section named as
     plausible for this class of change -- but derived here from this file's own data ranges and
     Float16's actual unit roundoff, not copied from that range blindly. The REAL measured worst
     delta is reported below regardless of whether it falls inside or outside these bounds; the
     tolerance is a pass/fail line for this file's own correctness gate, not a ceiling imposed on
     the reported number.

  2. Correctness at the REAL qkv_proj production shape (M=256, K=1024, N=4096) -- the same shape
     that gets timed in step 3, against the same Float64 oracle, at the "real shape" tolerance
     derived above. `gemm_qkv_proj_bench.mojo`'s own "honest gaps" section flagged that its
     correctness check ran at a different (small) shape than the one it timed; this file closes
     that specific gap for the new kernel by checking both.

  3. Timing: identical methodology to `gemm_qkv_proj_bench.mojo`'s `bench_qkv_proj_shape` -- all
     buffers (activations, quantized weights, per-row scales, output) allocated/uploaded ONCE
     outside the timed region; 1 untimed warmup dispatch (excluded from the sample, per this
     session's own documented cold-first-run artifact); 200 warm `enqueue_function` +
     `ctx.synchronize()` runs; median/p10/p90 wall time; GFLOP/s via the identical `2*M*K*N/time`
     convention, at the real qkv_proj shape (M=256, K=1024, N=4096, Qwen3-0.6B-Base, m_rows=256).
     Run 3 independent process launches of this file, matching `gemm_qkv_proj_bench.mojo`'s own
     3-launch discipline for its Int8/F32 kernel.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . probes/gemm_qkv_proj_f16_bench.mojo
"""
from max.gpu.host import DeviceContext
from std.time import perf_counter_ns
from mm8 import _qkv_proj_gemm_mma8x8_f16


def _pseudo_activation(i: Int, seed: Int) -> Float32:
    """Verbatim copy of `gemm_qkv_proj_bench.mojo`'s own `_pseudo_activation` (itself copied from
    `correctness_probe_partial.mojo`'s `xn_vals` formula) -- kept byte-identical so this file's
    activation distribution matches the one already established elsewhere in this repo."""
    return Float32((i * 7 + seed * 13 + 3) % 13) / 6.0 - 1.0


def _pseudo_weight_raw(i: Int, seed: Int) -> Float64:
    """Verbatim copy of `gemm_qkv_proj_bench.mojo`'s own `_pseudo_weight_raw`. Deterministic
    pseudo-random 'true' (pre-quantization) weight value, flat index `i` over the row-major [N,K]
    weight matrix. Range ~[-0.05, 0.05)."""
    return Float64(((i * 11 + seed * 7 + 5) % 17) - 8) / 160.0


def _quantize_row(mut out: List[Int8], k: Int, row_offset: Int, seed: Int) -> Float32:
    """Verbatim copy of `gemm_qkv_proj_bench.mojo`'s own `_quantize_row` -- exactly `mm8.mojo`'s
    own documented per-row-symmetric int8 scheme (`scale = maxabs/127`, round-to-nearest, clamp to
    [-127, 127]), applied to synthetic data instead of a real checkpoint."""
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


def _check_correctness_f16(ctx: DeviceContext, m: Int, k: Int, n: Int, tol: Float32, label: String) raises -> Bool:
    """Dispatches `_qkv_proj_gemm_mma8x8_f16` at shape (m,k,n) and compares against the SAME
    Float64 CPU oracle `gemm_qkv_proj_bench.mojo`'s own `_check_correctness` uses (byte-identical
    accumulate math: the oracle does NOT itself narrow to Float16 -- it is the full-precision-
    Float32 'ideal' result the F16 kernel's own extra narrowing step is expected to deviate from).
    `tol` is this call's pass/fail bound (see module docstring for its derivation); `label`
    distinguishes the small-shape call from the real-shape call in printed output."""
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
    ctx.enqueue_function[_qkv_proj_gemm_mma8x8_f16](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n),
        grid_dim=grid, block_dim=256,
    )
    ctx.synchronize()

    var worst = Float32(0.0)
    var n_mismatch = 0
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
                if d > tol:
                    n_mismatch += 1
                    if n_mismatch <= 5:
                        print("    MISMATCH (", mi, ",", j, "): got", got, "want", want, "delta", d)
    print("  [", label, "] correctness shape M=", m, " K=", k, " N=", n, " worst delta:", worst, " tol:", tol)
    if n_mismatch > 0:
        print("  [", label, "] total mismatches over tol:", n_mismatch, "/", m * n)
    return worst <= tol


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


def bench_qkv_proj_shape_f16(ctx: DeviceContext, m: Int, k: Int, n: Int, n_runs: Int) raises:
    """Times `_qkv_proj_gemm_mma8x8_f16` at shape (m,k,n). Identical methodology to
    `gemm_qkv_proj_bench.mojo`'s own `bench_qkv_proj_shape`: buffers allocated/uploaded ONCE outside
    the timed region; 1 untimed warmup dispatch, then `n_runs` warm runs of enqueue+synchronize."""
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
    ctx.enqueue_function[_qkv_proj_gemm_mma8x8_f16](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n),
        grid_dim=grid, block_dim=256,
    )
    ctx.synchronize()

    var times_ns = List[Int](capacity=n_runs)
    for _ in range(n_runs):
        var t0 = perf_counter_ns()
        ctx.enqueue_function[_qkv_proj_gemm_mma8x8_f16](
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
    print("=== gemm_qkv_proj_f16_bench: Algenta's F16-MMA-operand variant, _qkv_proj_gemm_mma8x8_f16 ===")
    print("=== (mma_forge/mm8.mojo) -- GEMM tournament Phase 0 isolation experiment.              ===")
    print("=== Storage stays INT8 per-output-row-quantized (unchanged); ONLY the MMA operand      ===")
    print("=== width changes, Float32 -> Float16, vs. the already-proven _qkv_proj_gemm_mma8x8.   ===")
    print("")
    print("--- Step 1: correctness, small non-32-aligned shape (M=33,K=64,N=37), tol=1e-2 ---")
    var ok_small = _check_correctness_f16(ctx, 33, 64, 37, Float32(1.0e-2), "small")
    if not ok_small:
        print("  CORRECTNESS (small shape): FAIL -- aborting, not trusting the timing run below")
        return
    print("  CORRECTNESS (small shape): PASS")

    print("")
    print("--- Step 2: correctness, REAL qkv_proj production shape (M=256,K=1024,N=4096), tol=1e-1 ---")
    var ok_real = _check_correctness_f16(ctx, 256, 1024, 4096, Float32(1.0e-1), "real")
    if not ok_real:
        print("  CORRECTNESS (real shape): FAIL -- aborting, not trusting the timing run below")
        return
    print("  CORRECTNESS (real shape): PASS")

    print("")
    print("--- Step 3: timing, qkv_proj production shape (Qwen3-0.6B-Base, m_rows=256) ---")
    bench_qkv_proj_shape_f16(ctx, 256, 1024, 4096, 200)
