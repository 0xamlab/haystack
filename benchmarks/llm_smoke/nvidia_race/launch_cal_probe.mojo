"""launch_cal_probe.mojo — calibrates enqueue/launch cost vs GPU kernel cost for the L6
battery (the battery's first cut measured 37 ms/launch with the GPU at 0% util — this
isolates host enqueue cost from device kernel time with a trivial kernel and the shipped
p3 batched assign kernel)."""

from max.gpu.host import DeviceContext
from std.gpu import global_idx
from std.origin import MutAnyOrigin
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from residentk.kernels_packed3_batched import _P3B_TG, _batched_p3_gemv_assign_kernel

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]


def _trivial(dst: _FP, n_i64: Int64):
    var n = Int(n_i64)
    var i = Int(global_idx.x)
    if i < n:
        dst[i] = Float32(i)


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        return
    else:
        if not has_accelerator():
            return
        var ctx = DeviceContext()
        print("launch_cal_probe: device:", ctx.name())

        var k = 1024
        var n = 2560
        var B = 8
        var k_pack = ((k + 11) // 12) * 12
        var words = k_pack // 3
        var nblocks = (k_pack + 31) // 32

        var wp = ctx.enqueue_create_buffer[DType.float32](n * words)
        var ws = ctx.enqueue_create_buffer[DType.float32](n * nblocks)
        var wz = ctx.enqueue_create_buffer[DType.float32](n * nblocks)
        var x = ctx.enqueue_create_buffer[DType.float32](B * k)
        var y = ctx.enqueue_create_buffer[DType.float32](B * n)
        var z = ctx.enqueue_create_buffer[DType.float32](n)
        ctx.synchronize()

        # 1. trivial kernel: 200 back-to-back enqueues, one sync — enqueue path cost
        _ = ctx.enqueue_function[_trivial](z.unsafe_ptr(), Int64(n), grid_dim=10, block_dim=256)
        ctx.synchronize()
        var t0 = perf_counter_ns()
        for _ in range(200):
            ctx.enqueue_function[_trivial](z.unsafe_ptr(), Int64(n), grid_dim=10, block_dim=256)
        var t_enq = Float64(perf_counter_ns() - t0) / 200.0 / 1000.0
        ctx.synchronize()
        var t_tot = Float64(perf_counter_ns() - t0) / 200.0 / 1000.0
        print("trivial: enqueue-only", t_enq, "us | enqueue+drain", t_tot, "us per launch")

        # 2. p3 assign kernel: 50 back-to-back enqueues
        _ = ctx.enqueue_function[_batched_p3_gemv_assign_kernel](
            y.unsafe_ptr(), x.unsafe_ptr(), wp.unsafe_ptr(), ws.unsafe_ptr(),
            wz.unsafe_ptr(), Int64(k), Int64(n), Int64(B),
            grid_dim=n, block_dim=_P3B_TG)
        ctx.synchronize()
        t0 = perf_counter_ns()
        for _ in range(50):
            ctx.enqueue_function[_batched_p3_gemv_assign_kernel](
                y.unsafe_ptr(), x.unsafe_ptr(), wp.unsafe_ptr(), ws.unsafe_ptr(),
                wz.unsafe_ptr(), Int64(k), Int64(n), Int64(B),
                grid_dim=n, block_dim=_P3B_TG)
        var p_enq = Float64(perf_counter_ns() - t0) / 50.0 / 1000.0
        ctx.synchronize()
        var p_tot = Float64(perf_counter_ns() - t0) / 50.0 / 1000.0
        print("p3 assign: enqueue-only", p_enq, "us | enqueue+drain", p_tot, "us per launch")
        print("launch_cal_probe: done")
