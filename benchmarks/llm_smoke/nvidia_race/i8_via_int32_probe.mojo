"""i8_via_int32_probe.mojo — the last remaining load path for quantized weights on this
toolchain: i8_gemv_probe.mojo showed char4 (Int8 vector) loads collapse to 1-1.6% of HBM peak
on the Mojo 1.0.0 CUDA backend, while float4 loads run at 63-91%. This probe tests whether
loading the SAME bytes through the proven 4-byte path (Int32 vectors) and unpacking in
software restores bandwidth:

  V1: Int32 loads, sum raw words (no unpack) — the pure load-path question at the GEMV shape
  V2: Int32 loads + SIMD byte-unpack + sign-extend + scale dequant + FMA (the full recipe)

If V1 is fast and V2's unpack overhead is bounded, the NVIDIA int8 session gets Int32-load
twins (kernels_cuda_i8.mojo) and the race arm runs at quarter the f32 weight traffic.

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/i8_via_int32_probe.mojo -o probe
"""

from max.gpu.host import DeviceContext
from std.gpu import block_idx, thread_idx
from max.gpu import barrier
from max.gpu.memory import AddressSpace
from std.math import sqrt
from std.memory import stack_allocation
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from residentk.kernels import _TG, _SUBS, _STAGE, _LANES, _norm_gemv_kernel

comptime REPS: Int = 400
comptime D_MODEL: Int = 1024
comptime N_QKV: Int = 3072
comptime HBM_GB_S: Float64 = 1555.0
# 4 bytes per Int32 = 4 int8 elements per load; per-warp step = 32 lanes * 4 words = 128 words
comptime VEC_W: Int = 4
comptime ELEM_PER_W: Int = 4
comptime WORD_STRIDE: Int = _LANES * VEC_W

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _I8P = UnsafePointer[Int8, origin=MutAnyOrigin]
alias _I32P = UnsafePointer[Int32, origin=MutAnyOrigin]


def _norm_gemv_i8_rawwords(
    y: _FP, x: _FP, gamma: _FP, w_i32: _I32P, k_i64: Int64, n_i64: Int64, eps: Float32
):
    """V1: the norm_gemv structure with the weight stream read as Int32 vectors and the words
    summed raw (no unpack) — isolates the load path at the GEMV shape."""
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
        # weight row j: k int8 = k/4 words
        var k_w = k // ELEM_PER_W
        var base_w = j * k_w
        var t = lane * VEC_W
        while t < k_w:
            var wv = w_i32.load[width=VEC_W](base_w + t)
            var wsum = Float32(0)
            for e in range(VEC_W):
                wsum += Float32(wv[e])
            acc += xs[t * ELEM_PER_W] * wsum
            t += WORD_STRIDE
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


def _norm_gemv_i8_unpack(
    y: _FP, x: _FP, gamma: _FP, w_i32: _I32P, wscale: _FP, k_i64: Int64, n_i64: Int64,
    eps: Float32
):
    """V2: the full recipe — Int32 vector loads, per-byte unpack + sign extension, Float32
    dequant with the row scale, per-element FMA against the staged normalized row."""
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
        var scale_j = wscale[j]
        var k_w = k // ELEM_PER_W
        var base_w = j * k_w
        var t = lane * VEC_W
        while t < k_w:
            var wv = w_i32.load[width=VEC_W](base_w + t)
            for e in range(VEC_W):
                var word = wv[e]
                var b0 = word & 0xFF
                if b0 > 127:
                    b0 -= 256
                var xv = xs[t * ELEM_PER_W + e]
                acc += xv * (Float32(b0) * scale_j)
            t += WORD_STRIDE
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


def _ceil_div_local(a: Int, b: Int) -> Int:
    return (a + b - 1) // b


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("i8_via_int32_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("i8_via_int32_probe: no accelerator")
            return

        var ctx = DeviceContext()
        print("i8_via_int32_probe: device:", ctx.name())

        var x = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var ln = ctx.enqueue_create_buffer[DType.float32](D_MODEL)
        var wqkv_f32 = ctx.enqueue_create_buffer[DType.float32](N_QKV * D_MODEL)
        var wqkv_i32 = ctx.enqueue_create_buffer[DType.int32](N_QKV * D_MODEL // 4)
        var wqkv_scale = ctx.enqueue_create_buffer[DType.float32](N_QKV)
        var qkv = ctx.enqueue_create_buffer[DType.float32](N_QKV)

        var grid = _ceil_div_local(N_QKV, _SUBS)

        var t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_norm_gemv_kernel](
                qkv.unsafe_ptr(), x.unsafe_ptr(), ln.unsafe_ptr(),
                wqkv_f32.unsafe_ptr(), Int64(D_MODEL), Int64(N_QKV), Float32(1e-6),
                grid_dim=grid, block_dim=_TG)
        ctx.synchronize()
        var f32_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)
        var f32_bytes = Float64(N_QKV) * Float64(D_MODEL) * 4.0

        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_norm_gemv_i8_rawwords](
                qkv.unsafe_ptr(), x.unsafe_ptr(), ln.unsafe_ptr(),
                wqkv_i32.unsafe_ptr(), Int64(D_MODEL), Int64(N_QKV), Float32(1e-6),
                grid_dim=grid, block_dim=_TG)
        ctx.synchronize()
        var v1_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)
        var i8_bytes = Float64(N_QKV) * Float64(D_MODEL) * 1.0

        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_norm_gemv_i8_unpack](
                qkv.unsafe_ptr(), x.unsafe_ptr(), ln.unsafe_ptr(),
                wqkv_i32.unsafe_ptr(), wqkv_scale.unsafe_ptr(),
                Int64(D_MODEL), Int64(N_QKV), Float32(1e-6),
                grid_dim=grid, block_dim=_TG)
        ctx.synchronize()
        var v2_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)

        print("norm_gemv(qkv) k=1024 n=3072:")
        print("  f32 float4:        ", f32_us, "us ->",
              f32_bytes / (f32_us * 1e-6) / 1e9, "GB/s (",
              f32_bytes / (f32_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")
        print("  i8 via Int32 raw:  ", v1_us, "us ->",
              i8_bytes / (v1_us * 1e-6) / 1e9, "GB/s (",
              i8_bytes / (v1_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")
        print("  i8 via Int32 unpck:", v2_us, "us ->",
              i8_bytes / (v2_us * 1e-6) / 1e9, "GB/s (",
              i8_bytes / (v2_us * 1e-6) / 1e9 / HBM_GB_S * 100.0, "% peak )")
        print("i8_via_int32_probe: done")
