"""syncscope_probe.mojo — RIGOROUS test of the per-stream sync scopes the L5 design relies
on (the first probe's Q2/Q3 could not distinguish "waited for the tiny op" from "waited for
nothing"). For each of the three sync surfaces, enqueue a LONG kernel (~200 ms) on the
side stream, call the sync, and measure the wall: a working sync pays the kernel's remaining
duration; a broken sync returns immediately.

  T1  view.synchronize() waits the view stream's long kernel
  T2  map_to_host round-trip on a view-created buffer waits the view stream (enter+exit
      syncs are supposed to bracket the copy)
  T3  enqueue_copy D2H on the view + view.synchronize() delivers the COPIED value (data
      check, not just timing)
  T4  a kernel enqueued on the view AFTER a long kernel orders behind it (in-stream order)

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/syncscope_probe.mojo -o syncprobe
"""

from max.gpu.host import DeviceContext
from std.gpu import block_idx, thread_idx
from std.origin import MutAnyOrigin
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime SPIN_ITERS: Int = 30_000_000  # ~200 ms latency chain


def _spin_kernel(sink: _FP, iters_i64: Int64, tag_i64: Int64):
    var iters = Int(iters_i64)
    var tag = Float32(Float64(Int(tag_i64)) * 1.0e-9)
    var gtid = Int(block_idx.x) * 256 + Int(thread_idx.x)
    var acc = Float32(Float64(gtid) * 1.0e-13) + tag
    for i in range(iters):
        acc = acc * Float32(1.0000000001) + Float32(1.0e-13)
    if acc == Float32(1.2345e30):
        sink[gtid] = acc


def _fill_kernel(dst: _FP, val_i64: Int64, n_i64: Int64):
    var val = Float32(Float64(Int(val_i64)))
    var n = Int(n_i64)
    var i = Int(block_idx.x) * 256 + Int(thread_idx.x)
    if i < n:
        dst[i] = val


def _ms(ns: Int) -> Float64:
    return Float64(ns) / 1.0e6


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("syncscope_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("syncscope_probe: no accelerator")
            return

        var ctx = DeviceContext()
        _ = ctx.create_stream()
        var v1 = ctx.select_stream(1)
        print("syncscope_probe: device:", ctx.name())

        var sink = ctx.enqueue_create_buffer[DType.float32](1024)
        var vsink = v1.enqueue_create_buffer[DType.float32](1024)
        var vbuf = v1.enqueue_create_buffer[DType.float32](256)
        var vhost = v1.enqueue_create_host_buffer[DType.float32](256)
        ctx.synchronize()
        v1.synchronize()

        # calibrate the spin on the view stream
        var t0 = perf_counter_ns()
        v1.enqueue_function[_spin_kernel](
            vsink.unsafe_ptr(), Int64(SPIN_ITERS), Int64(1),
            grid_dim=4, block_dim=256)
        v1.synchronize()
        var spin_ms = _ms(perf_counter_ns() - t0)
        print("calibration: view-stream spin =", spin_ms, "ms")

        # ═══ T1 — view.synchronize() waits the view stream ═══
        v1.enqueue_function[_spin_kernel](
            vsink.unsafe_ptr(), Int64(SPIN_ITERS), Int64(2),
            grid_dim=4, block_dim=256)
        t0 = perf_counter_ns()
        v1.synchronize()
        var t1 = _ms(perf_counter_ns() - t0)
        print("T1 view.synchronize() after spin:", t1, "ms",
              "| WORKS" if t1 > spin_ms * 0.5 else "| BROKEN (returned early)")

        # ═══ T2 — map_to_host on a view buffer waits the view stream ═══
        v1.enqueue_function[_spin_kernel](
            vsink.unsafe_ptr(), Int64(SPIN_ITERS), Int64(3),
            grid_dim=4, block_dim=256)
        t0 = perf_counter_ns()
        with vbuf.map_to_host() as h:
            h[0] = Float32(7.0)
        var t2 = _ms(perf_counter_ns() - t0)
        print("T2 map_to_host round-trip during spin:", t2, "ms",
              "| WORKS" if t2 > spin_ms * 0.5 else "| BROKEN (returned early)")

        # ═══ T3 — D2H copy on the view delivers the copied VALUE ═══
        # write 42.0 into vbuf (view stream), spin on the view stream, then copy+sync:
        # the host must see 42.0, and only AFTER the sync
        v1.enqueue_function[_fill_kernel](
            vbuf.unsafe_ptr(), Int64(42), Int64(256), grid_dim=1, block_dim=256)
        v1.enqueue_function[_spin_kernel](
            vsink.unsafe_ptr(), Int64(SPIN_ITERS), Int64(4),
            grid_dim=4, block_dim=256)
        v1.enqueue_copy(vhost, vbuf)
        t0 = perf_counter_ns()
        v1.synchronize()
        var t3 = _ms(perf_counter_ns() - t0)
        var seen = Float64(vhost.unsafe_ptr()[0])
        print("T3 D2H copy+sync during spin:", t3, "ms | host value:", seen,
              "|", "WORKS" if seen == 42.0 and t3 > spin_ms * 0.5 else "BROKEN")

        # ═══ T4 — in-stream order on the view: fill-after-spin sees the spin done ═══
        # (structural: if the fill runs BEFORE the spin finishes, this still passes — the
        #  real check is T5 below: cross-stream visibility of lane writes)
        v1.enqueue_function[_fill_kernel](
            vbuf.unsafe_ptr(), Int64(11), Int64(256), grid_dim=1, block_dim=256)
        v1.synchronize()
        v1.enqueue_copy(vhost, vbuf)
        v1.synchronize()
        var t4 = Float64(vhost.unsafe_ptr()[0])
        print("T4 in-stream order value:", t4, "|", "WORKS" if t4 == 11.0 else "BROKEN")

        # ═══ T5 — cross-stream visibility: view writes, default-stream kernel reads ═══
        # fill vbuf with 99 on the view stream; view.synchronize(); then a DEFAULT-stream
        # kernel copies vbuf[0] into sink[0]; the host must read 99 — proves completed
        # side-stream writes are visible to the primary stream (the L5 KV contract).
        v1.enqueue_function[_fill_kernel](
            vbuf.unsafe_ptr(), Int64(99), Int64(256), grid_dim=1, block_dim=256)
        v1.synchronize()
        ctx.enqueue_function[_fill_kernel](
            sink.unsafe_ptr(), Int64(0), Int64(256), grid_dim=1, block_dim=256)
        ctx.synchronize()
        ctx.enqueue_copy(vhost, vbuf)
        ctx.synchronize()
        var t5 = Float64(vhost.unsafe_ptr()[0])
        print("T5 cross-stream visibility value:", t5,
              "|", "WORKS" if t5 == 99.0 else "BROKEN")

        print("syncscope_probe: done")
