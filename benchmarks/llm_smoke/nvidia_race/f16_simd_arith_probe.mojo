"""f16_simd_arith_probe.mojo — the RUNTIME half of the mma-surface battery: the compile battery
(mma_surface_probe.sh) proved f16/i8 SIMD ARITHMETIC compiles for sm_80; this probe measures how
fast it actually RUNS on the A100, against the f32 SIMD twin. Question answered: even where the
toolchain accepts f16 SIMD math, does it execute at a useful rate (packed HFMA2), or does the
backend scalarize it the way the load-path battery already measured for loads?

Method: each kernel keeps 4 independent SIMD accumulator vectors alive in a FMA chain long enough
to be compute-bound (no loads in the timed loop), dispatched REPS times back-to-back with one
synchronize. FLOPs count every FMA as 2 ops. The A100's FP32 SIMT peak is 19.5 TFLOP/s; its
non-tensor FP16 rate is the SAME 19.5 TFLOP/s (datacenter A100 has no 2x packed-f16 SIMT
advantage — that belongs to the consumer parts), so a packed-HFMA2 lowering would show ~1.0x of
the f32 number and a scalarized lowering would show markedly less.

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/f16_simd_arith_probe.mojo -o probe
"""

from std.gpu import thread_idx
from std.origin import MutAnyOrigin
from std.sys import has_accelerator, is_defined
from std.time import perf_counter_ns
from max.gpu.host import DeviceContext

comptime REPS: Int = 20
comptime ITERS: Int = 4096
comptime NTHREADS: Int = 256
comptime NBLOCKS: Int = 432


def _f32_fma_kernel(dst: UnsafePointer[Float32, origin=MutAnyOrigin]):
    # INTEGRITY ARMOR, measured not assumed: the first three versions of this probe reported
    # 300-457% of the A100's physical FP32 peak. The embedded PTX proved why — Mojo's FP ops
    # lower with reassociation enabled, so ANY linear recurrence a' = a*b + c is RECURRENCE-
    # DOUBLED by LLVM (4096 iterations -> ~20 FMAs), constant OR runtime coefficient. This
    # version uses a COUPLED NONLINEAR recurrence (each accumulator multiplies its NEIGHBOUR,
    # a quadratic term) — no linear algebra can fold it. Verified by instruction count in the
    # embedded PTX before the timing is trusted. Seeds 0.30-0.33, c = 0.24 keep values in a
    # convergent basin (fixed point ~0.4): no overflow, no denormals, FMA pattern unchanged.
    var seed = Float32(Int(thread_idx.x) + 1) * Float32(1.0e-5)
    var a0 = SIMD[DType.float32, 4](Float32(0.30) + seed)
    var a1 = SIMD[DType.float32, 4](Float32(0.31) + seed)
    var a2 = SIMD[DType.float32, 4](Float32(0.32) + seed)
    var a3 = SIMD[DType.float32, 4](Float32(0.33) + seed)
    var c = SIMD[DType.float32, 4](Float32(0.24))
    for _ in range(ITERS):
        a0 = a0 * a1 + c
        a1 = a1 * a2 + c
        a2 = a2 * a3 + c
        a3 = a3 * a0 + c
    var sink = a0 + a1 + a2 + a3
    # Store ALL lanes' sum — a `sink[0]` store lets DCE kill lanes 1-3 (ncu caught it:
    # exactly 1/4 of the counted FMAs executed).
    dst[Int(thread_idx.x)] = sink[0] + sink[1] + sink[2] + sink[3]


def _f16_fma_kernel(dst: UnsafePointer[Float32, origin=MutAnyOrigin]):
    var seed = Float16(Float32(Int(thread_idx.x) + 1) * Float32(1.0e-5))
    var a0 = SIMD[DType.float16, 8](Float16(0.30) + seed)
    var a1 = SIMD[DType.float16, 8](Float16(0.31) + seed)
    var a2 = SIMD[DType.float16, 8](Float16(0.32) + seed)
    var a3 = SIMD[DType.float16, 8](Float16(0.33) + seed)
    var c = SIMD[DType.float16, 8](Float16(0.24))
    for _ in range(ITERS):
        a0 = a0 * a1 + c
        a1 = a1 * a2 + c
        a2 = a2 * a3 + c
        a3 = a3 * a0 + c
    var sink = (a0 + a1).cast[DType.float32]() + (a2 + a3).cast[DType.float32]()
    var acc = Float32(0.0)
    for i in range(8):
        acc += sink[i]
    dst[Int(thread_idx.x)] = acc


def main() raises:
    @parameter
    if not is_defined["ALGENTA_CUDA"]():
        print("f16_simd_arith_probe: built without -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("f16_simd_arith_probe: no accelerator on this host")
            return

        var ctx = DeviceContext()
        var buf = ctx.enqueue_create_buffer[DType.float32](NTHREADS)

        # Warmup both kernels (clock ramp + first-dispatch cost out of the timed window).
        ctx.enqueue_function[_f32_fma_kernel](buf.unsafe_ptr(),
                                              grid_dim=NBLOCKS, block_dim=NTHREADS)
        ctx.enqueue_function[_f16_fma_kernel](buf.unsafe_ptr(),
                                              grid_dim=NBLOCKS, block_dim=NTHREADS)
        ctx.synchronize()

        # Per kernel: ITERS x 4 accumulators x SIMD-width FMAs x threads x blocks; FMA = 2 ops.
        var flops = Float64(2) * Float64(ITERS) * Float64(4) * Float64(4) \
            * Float64(NTHREADS) * Float64(NBLOCKS)

        var t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_f32_fma_kernel](buf.unsafe_ptr(),
                                                  grid_dim=NBLOCKS, block_dim=NTHREADS)
        ctx.synchronize()
        var f32_s = Float64(perf_counter_ns() - t0) / 1.0e9 / Float64(REPS)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_f16_fma_kernel](buf.unsafe_ptr(),
                                                  grid_dim=NBLOCKS, block_dim=NTHREADS)
        ctx.synchronize()
        var f16_s = Float64(perf_counter_ns() - t0) / 1.0e9 / Float64(REPS)

        # f16 kernel runs 8-wide SIMD vs f32's 4-wide: double the element count for parity.
        var flops_f16 = flops * 2.0

        print("f16_simd_arith_probe: ITERS =", ITERS, "x 4 acc vectors x", NBLOCKS,
              "blocks x", NTHREADS, "threads x", REPS, "reps")
        print("  f32 SIMD[4]: ", f32_s * 1000.0, "ms/dispatch ->",
              flops / f32_s / 1.0e12, "TFLOP/s (", flops / f32_s / 1.0e12 / 19.5 * 100.0,
              "% of the 19.5 TFLOP/s FP32 SIMT peak)")
        print("  f16 SIMD[8]: ", f16_s * 1000.0, "ms/dispatch ->",
              flops_f16 / f16_s / 1.0e12, "TFLOP/s (", flops_f16 / f16_s / 1.0e12 / 19.5 * 100.0,
              "% of the 19.5 TFLOP/s non-tensor f16 rate)")
        print("  ratio f16/f32:", (flops_f16 / f16_s) / (flops / f32_s),
              "(~1.0 = packed HFMA2 lowering; << 1.0 = scalarized)")
