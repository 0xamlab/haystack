"""f16_vec8_probe.mojo — tests whether the f16 GEMV collapse on NVIDIA (5-7% of HBM peak with
the Metal-tuned half4 loads) is a VECTOR-WIDTH problem: identical kernel bodies with
width-8 f16 loads (16 bytes, byte-matched to the f32 arm's float4). If width 8 restores
bandwidth, the NVIDIA f16 arm gets width-8 twins (kernels_cuda_f16.mojo), and the shared
Metal-tuned half4 kernels stay untouched.

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/f16_vec8_probe.mojo -o probe
"""

from max.gpu.host import DeviceContext
from std.gpu import block_idx, thread_idx
from max.gpu import barrier
from max.gpu.memory import AddressSpace
from std.math import sqrt
from std.memory import stack_allocation
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from residentk.kernels import _TG, _SUBS, _LANES, _STAGE, _norm_gemv_kernel

comptime REPS: Int = 400
comptime D_MODEL: Int = 1024
comptime N_QKV: Int = 3072
comptime HBM_GB_S: Float64 = 1555.0
comptime _VEC8: Int = 8
comptime _VEC_STRIDE8: Int = _LANES * _VEC8

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _HP = UnsafePointer[Float16, origin=MutAnyOrigin]


def _norm_gemv_kernel_f16_vec8(
    y: _FP, x: _FP, gamma: _FP, w: _HP, k_i64: Int64, n_i64: Int64, eps: Float32
):
    """Width-8 experiment: byte-for-byte `_norm_gemv_kernel_f16`'s body with `_VEC_H` 4 -> 8
    (16-byte weight loads, byte-matched to the f32 kernel's float4)."""
    var k = Int(k_i64)
    var n = Int(n_i64)
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    var s = tid
    while s < k:
        xs[s] = x[s] * inv * gamma[s]
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var base = j * k
        var k_vec = (k // _VEC_STRIDE8) * _VEC_STRIDE8
        var t = lane * _VEC8
        while t < k_vec:
            var xv = xs.load[width=_VEC8](t)
            var wv = w.load[width=_VEC8](base + t).cast[DType.float32]()
            var pv = xv * wv
            for lane_e in range(_VEC8):
                acc += pv[lane_e]
            t += _VEC_STRIDE8
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * Float32(w[base + tt])
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = red[sub * _LANES]


alias _I32P = UnsafePointer[Int32, origin=MutAnyOrigin]


def _norm_gemv_kernel_f16_asint(
    y: _FP, x: _FP, gamma: _FP, w_i32: _I32P, k_i64: Int64, n_i64: Int64, eps: Float32
):
    """Int32-load workaround: read the f16 weight stream as 4-element Int32 vectors (16 bytes,
    the f32 arm's proven load path), bitcast each to 8 Float16, widen, multiply."""
    var k = Int(k_i64)
    var n = Int(n_i64)
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    var s = tid
    while s < k:
        xs[s] = x[s] * inv * gamma[s]
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        # k is in ELEMENTS (f16); the i32 view has k/2 elements; stride by lane*4 i32s = 8 f16
        var k_i32 = k // 2
        var base_i32 = j * k_i32
        var t = lane * 4
        while t < k_i32:
            var xv = xs.load[width=_VEC8](t * 2)
            var wv = w_i32.load[width=4](base_i32 + t).unsafe_bitcast[SIMD[Float16, 8]]().cast[DType.float32]()
            var pv = xv * wv
            for lane_e in range(_VEC8):
                acc += pv[lane_e]
            t += _VEC_STRIDE8 // 2
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = red[sub * _LANES]


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("f16_vec8_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("f16_vec8_probe: no accelerator")
            return

        var ctx = DeviceContext()
        print("f16_vec8_probe: device:", ctx.name())

        var x = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var ln = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var wqkv_f32 = ctx.enqueue_create_buffer[DType.float32](N_QKV * D_MODEL)
        var wqkv_f16 = ctx.enqueue_create_buffer[DType.float16](N_QKV * D_MODEL)
        var qkv = ctx.enqueue_create_buffer[DType.float32](N_QKV)

        # f32 reference
        var t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_norm_gemv_kernel](
                qkv.unsafe_ptr(), x.unsafe_ptr(), ln.unsafe_ptr(),
                wqkv_f32.unsafe_ptr(), Int64(D_MODEL), Int64(N_QKV), Float32(1e-6),
                grid_dim=(N_QKV + _SUBS - 1) // _SUBS, block_dim=_TG)
        ctx.synchronize()
        var f32_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)

        # f16 width-8 experiment
        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_norm_gemv_kernel_f16_vec8](
                qkv.unsafe_ptr(), x.unsafe_ptr(), ln.unsafe_ptr(),
                wqkv_f16.unsafe_ptr(), Int64(D_MODEL), Int64(N_QKV), Float32(1e-6),
                grid_dim=(N_QKV + _SUBS - 1) // _SUBS, block_dim=_TG)
        ctx.synchronize()
        var f16v8_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)

        var f32_bytes = Float64(N_QKV) * Float64(D_MODEL) * 4.0
        var f16_bytes = Float64(N_QKV) * Float64(D_MODEL) * 2.0
        print("norm_gemv(qkv) k=1024 n=3072:")
        print("  f32 (float4):     ", f32_us, "us ->",
              f32_bytes / (f32_us * 1e-6) / 1e9, "GB/s (",
              f32_bytes / (f32_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")
        print("  f16 vec8 (half8): ", f16v8_us, "us ->",
              f16_bytes / (f16v8_us * 1e-6) / 1e9, "GB/s (",
              f16_bytes / (f16v8_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")
        print("  speedup vs f32:", f32_us / f16v8_us, "x")

        # f16 via Int32 loads (the workaround)
        var wqkv_i32_view = ctx.enqueue_create_buffer[DType.int32](N_QKV * D_MODEL // 2)
        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_norm_gemv_kernel_f16_asint](
                qkv.unsafe_ptr(), x.unsafe_ptr(), ln.unsafe_ptr(),
                wqkv_i32_view.unsafe_ptr(), Int64(D_MODEL), Int64(N_QKV), Float32(1e-6),
                grid_dim=(N_QKV + _SUBS - 1) // _SUBS, block_dim=_TG)
        ctx.synchronize()
        var f16ai_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)
        print("  f16 via Int32 ld: ", f16ai_us, "us ->",
              f16_bytes / (f16ai_us * 1e-6) / 1e9, "GB/s (",
              f16_bytes / (f16ai_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")
        print("  asint speedup vs f32:", f32_us / f16ai_us, "x")
        print("f16_vec8_probe: done")
