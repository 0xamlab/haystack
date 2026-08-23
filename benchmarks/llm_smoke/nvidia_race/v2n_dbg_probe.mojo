"""v2n_dbg_probe.mojo — minimal direct debug of the v2n/v3s narrow-N accum kernels:
does a single launch write anything, and is it the right value? Compares against the v2
accum on the same tiny problem (M=64, K=64, N=64 with synthetic weights) where the
expected result is computable on the host."""

from max.gpu.host import DeviceBuffer, DeviceContext
from std.gpu import block_idx, thread_idx
from std.sys import has_accelerator
from std.time import perf_counter_ns
from std.origin import MutAnyOrigin
from residentk.session import _ceil_div
from residentk.kernels_prefill_f32_v2 import (
    _G2_BM, _G2_BN, _G2_NTHREADS,
    _pf_gemm_accum_kernel_v2,
)
from residentk.kernels_prefill_f32_v2n import (
    _G2N_BN, _G2N_NTHREADS,
    _pf_gemm_accum_kernel_v2n,
)
from residentk.kernels_prefill_f32_v3 import (
    _G3S_BM, _G3S_BN, _G3S_NTHREADS,
    _pf_gemm_accum_kernel_v3s,
)

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]


def _dbg_fill_kernel(buf: _FP, v: Float32, n_i64: Int64):
    var i = Int(block_idx.x) * 256 + Int(thread_idx.x)
    if i < Int(n_i64):
        buf[i] = v


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return
    # shapes divisible by every tile: M=128, K=128, N=128
    var m = 128
    var k = 2048
    var n = 1024
    var ctx = DeviceContext()
    var x = ctx.enqueue_create_buffer[DType.float32](m * k)
    var w = ctx.enqueue_create_buffer[DType.float32](n * k)
    var y2 = ctx.enqueue_create_buffer[DType.float32](m * n)
    var y2n = ctx.enqueue_create_buffer[DType.float32](m * n)
    var y3s = ctx.enqueue_create_buffer[DType.float32](m * n)
    ctx.synchronize()

    # x[i] = 0.01 * ((i % 7) - 3); w[j] = 0.01 * ((j % 5) - 2); y base = 0.5
    var nx = m * k
    var nw = n * k
    var ny = m * n
    with x.map_to_host() as h:
        for i in range(nx):
            h[i] = Float32(0.01) * Float32((i % 7) - 3)
    with w.map_to_host() as h:
        for i in range(nw):
            h[i] = Float32(0.01) * Float32((i % 5) - 2)
    ctx.enqueue_function[_dbg_fill_kernel](y2.unsafe_ptr(), Float32(0.5), Int64(ny),
                                           grid_dim=_ceil_div(ny, 256), block_dim=256)
    ctx.enqueue_function[_dbg_fill_kernel](y2n.unsafe_ptr(), Float32(0.5), Int64(ny),
                                           grid_dim=_ceil_div(ny, 256), block_dim=256)
    ctx.enqueue_function[_dbg_fill_kernel](y3s.unsafe_ptr(), Float32(0.5), Int64(ny),
                                           grid_dim=_ceil_div(ny, 256), block_dim=256)
    ctx.synchronize()

    ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
        y2.unsafe_ptr(), x.unsafe_ptr(), w.unsafe_ptr(),
        Int64(m), Int64(k), Int64(n),
        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(n, _G2_BN),
        block_dim=_G2_NTHREADS)
    ctx.enqueue_function[_pf_gemm_accum_kernel_v2n](
        y2n.unsafe_ptr(), x.unsafe_ptr(), w.unsafe_ptr(),
        Int64(m), Int64(k), Int64(n),
        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(n, _G2N_BN),
        block_dim=_G2N_NTHREADS)
    ctx.enqueue_function[_pf_gemm_accum_kernel_v3s](
        y3s.unsafe_ptr(), x.unsafe_ptr(), w.unsafe_ptr(),
        Int64(m), Int64(k), Int64(n),
        grid_dim=_ceil_div(m, _G3S_BM) * _ceil_div(n, _G3S_BN),
        block_dim=_G3S_NTHREADS)
    ctx.synchronize()

    # host reference: y[r,c] = 0.5 + sum_t x[r,t]*w[c,t]
    var refv = List[Float64](capacity=ny)
    with x.map_to_host() as hx:
        with w.map_to_host() as hw:
            for idx in range(ny):
                var r = idx // n
                var c = idx % n
                var acc = 0.5
                for t in range(k):
                    acc += Float64(hx[r * k + t]) * Float64(hw[c * k + t])
                refv.append(acc)

    var d2 = 0.0
    var d2n = 0.0
    var d3s = 0.0
    with y2.map_to_host() as h:
        for i in range(ny):
            var d = Float64(h[i]) - refv[i]
            if d < 0.0:
                d = -d
            if d > d2:
                d2 = d
    with y2n.map_to_host() as h:
        for i in range(ny):
            var d = Float64(h[i]) - refv[i]
            if d < 0.0:
                d = -d
            if d > d2n:
                d2n = d
    with y3s.map_to_host() as h:
        for i in range(ny):
            var d = Float64(h[i]) - refv[i]
            if d < 0.0:
                d = -d
            if d > d3s:
                d3s = d
    print("M=128 K=128 N=128 accum vs host reference:")
    print("  v2  max_abs_diff =", d2)
    print("  v2n max_abs_diff =", d2n)
    print("  v3s max_abs_diff =", d3s)
    with y2.map_to_host() as h:
        print("  v2 y[0..3]:", h[0], h[1], h[2], h[3])
    with y2n.map_to_host() as h:
        print("  v2n y[0..3]:", h[0], h[1], h[2], h[3])
    with y3s.map_to_host() as h:
        print("  v3s y[0..3]:", h[0], h[1], h[2], h[3])
    print("  expected y[0] ~=", refv[0])
    print("v2n_dbg_probe: done")
