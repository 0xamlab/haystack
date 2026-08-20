"""f16_gemv_probe.mojo — head-to-head: the f32 decode GEMV family vs its f16 twins on NVIDIA.

The F16 CUDA session's decode came out 3x SLOWER than the f32 arm (87 vs 263 tok/s gen64) —
the opposite of the halved-bytes expectation. This probe isolates the mechanism: same shapes,
same grid/block, back-to-back dispatches, one synchronize, per-dispatch wall and achieved GB/s
for each variant (f16 traffic = half the f32 bytes). If the f16 kernels show a fraction of the
f32 kernels' bandwidth, the Metal-written f16 load path is mis-vectorizing on the NVIDIA
backend; the fix is then an NVIDIA-tuned load, not a session change.

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/f16_gemv_probe.mojo -o probe
"""

from max.gpu.host import DeviceContext
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from residentk.kernels import (
    _TG, _SUBS,
    _norm_gemv_kernel, _norm_gemv_kernel_f16,
    _gemv_accum_kernel, _gemv_accum_kernel_f16,
    _norm_gemv2_swiglu_kernel, _norm_gemv2_swiglu_kernel_f16,
)

comptime REPS: Int = 400
# Qwen3-0.6B shapes
comptime D_MODEL: Int = 1024
comptime N_QKV: Int = 3072
comptime D_FF: Int = 3072
comptime N_Q: Int = 2048
comptime HBM_GB_S: Float64 = 1555.0


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("f16_gemv_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("f16_gemv_probe: no accelerator")
            return

        var ctx = DeviceContext()
        print("f16_gemv_probe: device:", ctx.name())

        var x = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var ln = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var ln2 = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var wqkv_f32 = ctx.enqueue_create_buffer[DType.float32](N_QKV * D_MODEL)
        var wqkv_f16 = ctx.enqueue_create_buffer[DType.float16](N_QKV * D_MODEL)
        var wo_f32 = ctx.enqueue_create_buffer[DType.float32](N_Q * D_MODEL)
        var wo_f16 = ctx.enqueue_create_buffer[DType.float16](N_Q * D_MODEL)
        var wgu_f32 = ctx.enqueue_create_buffer[DType.float32](2 * D_FF * D_MODEL)
        var wgu_f16 = ctx.enqueue_create_buffer[DType.float16](2 * D_FF * D_MODEL)
        var qkv = ctx.enqueue_create_buffer[DType.float32](N_QKV)
        var hidden = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var attn_out = ctx.enqueue_create_buffer[DType.float32](N_Q)
        var act = ctx.enqueue_create_buffer[DType.float32](D_FF)

        # ═══ norm_gemv (qkv projection shape: k=1024, n=3072) ═══
        var t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_norm_gemv_kernel](
                qkv.unsafe_ptr(), x.unsafe_ptr(), ln.unsafe_ptr(),
                wqkv_f32.unsafe_ptr(), Int64(D_MODEL), Int64(N_QKV), Float32(1e-6),
                grid_dim=_ceil_div_local(N_QKV, _SUBS), block_dim=_TG)
        ctx.synchronize()
        var f32_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)
        var f32_bytes = Float64(N_QKV) * Float64(D_MODEL) * 4.0

        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_norm_gemv_kernel_f16](
                qkv.unsafe_ptr(), x.unsafe_ptr(), ln.unsafe_ptr(),
                wqkv_f16.unsafe_ptr(), Int64(D_MODEL), Int64(N_QKV), Float32(1e-6),
                grid_dim=_ceil_div_local(N_QKV, _SUBS), block_dim=_TG)
        ctx.synchronize()
        var f16_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)
        var f16_bytes = Float64(N_QKV) * Float64(D_MODEL) * 2.0

        print("norm_gemv(qkv) k=1024 n=3072:")
        print("  f32:", f32_us, "us ->", f32_bytes / (f32_us * 1e-6) / 1e9, "GB/s",
              "(", f32_bytes / (f32_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")
        print("  f16:", f16_us, "us ->", f16_bytes / (f16_us * 1e-6) / 1e9, "GB/s",
              "(", f16_bytes / (f16_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")

        # ═══ gemv_accum (o_proj shape: k=2048, n=1024) ═══
        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_gemv_accum_kernel](
                hidden.unsafe_ptr(), attn_out.unsafe_ptr(), wo_f32.unsafe_ptr(),
                Int64(N_Q), Int64(D_MODEL),
                grid_dim=_ceil_div_local(D_MODEL, _SUBS), block_dim=_TG)
        ctx.synchronize()
        f32_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)
        f32_bytes = Float64(N_Q) * Float64(D_MODEL) * 4.0

        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_gemv_accum_kernel_f16](
                hidden.unsafe_ptr(), attn_out.unsafe_ptr(), wo_f16.unsafe_ptr(),
                Int64(N_Q), Int64(D_MODEL),
                grid_dim=_ceil_div_local(D_MODEL, _SUBS), block_dim=_TG)
        ctx.synchronize()
        f16_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)
        f16_bytes = Float64(N_Q) * Float64(D_MODEL) * 2.0

        print("gemv_accum(o) k=2048 n=1024:")
        print("  f32:", f32_us, "us ->", f32_bytes / (f32_us * 1e-6) / 1e9, "GB/s",
              "(", f32_bytes / (f32_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")
        print("  f16:", f16_us, "us ->", f16_bytes / (f16_us * 1e-6) / 1e9, "GB/s",
              "(", f16_bytes / (f16_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")

        # ═══ norm_gemv2_swiglu (gate/up shape: k=1024, n_ff=3072) ═══
        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_norm_gemv2_swiglu_kernel](
                act.unsafe_ptr(), x.unsafe_ptr(), ln2.unsafe_ptr(),
                wgu_f32.unsafe_ptr(), Int64(D_MODEL), Int64(D_FF), Float32(1e-6),
                grid_dim=_ceil_div_local(D_FF, _SUBS), block_dim=_TG)
        ctx.synchronize()
        f32_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)
        f32_bytes = Float64(2) * Float64(D_FF) * Float64(D_MODEL) * 4.0

        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_norm_gemv2_swiglu_kernel_f16](
                act.unsafe_ptr(), x.unsafe_ptr(), ln2.unsafe_ptr(),
                wgu_f16.unsafe_ptr(), Int64(D_MODEL), Int64(D_FF), Float32(1e-6),
                grid_dim=_ceil_div_local(D_FF, _SUBS), block_dim=_TG)
        ctx.synchronize()
        f16_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)
        f16_bytes = Float64(2) * Float64(D_FF) * Float64(D_MODEL) * 2.0

        print("norm_gemv2_swiglu(gu) k=1024 n_ff=3072:")
        print("  f32:", f32_us, "us ->", f32_bytes / (f32_us * 1e-6) / 1e9, "GB/s",
              "(", f32_bytes / (f32_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")
        print("  f16:", f16_us, "us ->", f16_bytes / (f16_us * 1e-6) / 1e9, "GB/s",
              "(", f16_bytes / (f16_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")

        print("f16_gemv_probe: done")


def _ceil_div_local(a: Int, b: Int) -> Int:
    return (a + b - 1) // b
