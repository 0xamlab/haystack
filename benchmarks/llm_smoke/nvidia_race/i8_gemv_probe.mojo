"""i8_gemv_probe.mojo — does the int8-weight GEMV family (the Metal race arm's kernels, char4 =
4-byte loads + per-row f32 scale dequant) run fast on NVIDIA? The f16 family collapses to
5-7% of HBM peak here (f16_gemv_probe.mojo's finding), but the i8 path loads Int8 vectors the
same 4-byte width the f32 kernels prove fast, and Int8->Float32 is a hardware value cast (no
bit reinterpretation, which this toolchain has no primitive for).

If these land >= ~50% of HBM peak, the CUDA race arm gets the int8 session (quarter the f32
weight traffic), raced against llama.cpp's Q8_0 control.

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/i8_gemv_probe.mojo -o probe
"""

from max.gpu.host import DeviceContext
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from residentk.kernels import (
    _TG, _SUBS,
    _norm_gemv_kernel, _norm_gemv_kernel_i8,
    _gemv_accum_kernel, _gemv_accum_kernel_i8,
    _norm_gemv2_swiglu_kernel, _norm_gemv2_swiglu_kernel_i8,
)

comptime REPS: Int = 400
comptime D_MODEL: Int = 1024
comptime N_QKV: Int = 3072
comptime D_FF: Int = 3072
comptime N_Q: Int = 2048
comptime HBM_GB_S: Float64 = 1555.0


def _ceil_div_local(a: Int, b: Int) -> Int:
    return (a + b - 1) // b


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("i8_gemv_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("i8_gemv_probe: no accelerator")
            return

        var ctx = DeviceContext()
        print("i8_gemv_probe: device:", ctx.name())

        var x = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var ln = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var ln2 = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var wqkv_f32 = ctx.enqueue_create_buffer[DType.float32](N_QKV * D_MODEL)
        var wqkv_i8 = ctx.enqueue_create_buffer[DType.int8](N_QKV * D_MODEL)
        var wqkv_scale = ctx.enqueue_create_buffer[DType.float32](N_QKV)
        var wo_f32 = ctx.enqueue_create_buffer[DType.float32](N_Q * D_MODEL)
        var wo_i8 = ctx.enqueue_create_buffer[DType.int8](N_Q * D_MODEL)
        var wo_scale = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var wgu_f32 = ctx.enqueue_create_buffer[DType.float32](2 * D_FF * D_MODEL)
        var wgu_i8 = ctx.enqueue_create_buffer[DType.int8](2 * D_FF * D_MODEL)
        var wgu_scale = ctx.enqueue_create_buffer[DType.float32](2 * D_FF)
        var qkv = ctx.enqueue_create_buffer[DType.float32](N_QKV)
        var hidden = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var attn_out = ctx.enqueue_create_buffer[DType.float32](N_Q)
        var act = ctx.enqueue_create_buffer[DType.float32](D_FF)

        # ═══ norm_gemv (qkv shape: k=1024, n=3072) ═══
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
            ctx.enqueue_function[_norm_gemv_kernel_i8](
                qkv.unsafe_ptr(), x.unsafe_ptr(), ln.unsafe_ptr(),
                wqkv_i8.unsafe_ptr(), wqkv_scale.unsafe_ptr(),
                Int64(D_MODEL), Int64(N_QKV), Float32(1e-6),
                grid_dim=_ceil_div_local(N_QKV, _SUBS), block_dim=_TG)
        ctx.synchronize()
        var i8_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)
        var i8_bytes = Float64(N_QKV) * Float64(D_MODEL) * 1.0

        print("norm_gemv(qkv) k=1024 n=3072:")
        print("  f32:", f32_us, "us ->", f32_bytes / (f32_us * 1e-6) / 1e9, "GB/s (",
              f32_bytes / (f32_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")
        print("  i8: ", i8_us, "us ->", i8_bytes / (i8_us * 1e-6) / 1e9, "GB/s (",
              i8_bytes / (i8_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")

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
            ctx.enqueue_function[_gemv_accum_kernel_i8](
                hidden.unsafe_ptr(), attn_out.unsafe_ptr(), wo_i8.unsafe_ptr(),
                wo_scale.unsafe_ptr(), Int64(N_Q), Int64(D_MODEL),
                grid_dim=_ceil_div_local(D_MODEL, _SUBS), block_dim=_TG)
        ctx.synchronize()
        i8_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)
        i8_bytes = Float64(N_Q) * Float64(D_MODEL) * 1.0

        print("gemv_accum(o) k=2048 n=1024:")
        print("  f32:", f32_us, "us ->", f32_bytes / (f32_us * 1e-6) / 1e9, "GB/s (",
              f32_bytes / (f32_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")
        print("  i8: ", i8_us, "us ->", i8_bytes / (i8_us * 1e-6) / 1e9, "GB/s (",
              i8_bytes / (i8_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")

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
            ctx.enqueue_function[_norm_gemv2_swiglu_kernel_i8](
                act.unsafe_ptr(), x.unsafe_ptr(), ln2.unsafe_ptr(),
                wgu_i8.unsafe_ptr(), wgu_scale.unsafe_ptr(),
                Int64(D_MODEL), Int64(D_FF), Float32(1e-6),
                grid_dim=_ceil_div_local(D_FF, _SUBS), block_dim=_TG)
        ctx.synchronize()
        i8_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)
        i8_bytes = Float64(2) * Float64(D_FF) * Float64(D_MODEL) * 1.0

        print("norm_gemv2_swiglu(gu) k=1024 n_ff=3072:")
        print("  f32:", f32_us, "us ->", f32_bytes / (f32_us * 1e-6) / 1e9, "GB/s (",
              f32_bytes / (f32_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")
        print("  i8: ", i8_us, "us ->", i8_bytes / (i8_us * 1e-6) / 1e9, "GB/s (",
              i8_bytes / (i8_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")

        print("i8_gemv_probe: done")
