"""multistream_probe.mojo — L5 groundwork probe: verifies the MAX 26.5 multi-stream surface
on the A100 with hardware evidence, answering the four questions the multi-stream admission
design depends on (no guessing):

  Q1 do two kernels on two streams OVERLAP in time? (wall of concurrent pair vs sequential)
  Q2 is a select_stream VIEW's synchronize() scoped to ITS stream, or device-wide?
     (a long kernel runs on the default stream while the view syncs a tiny copy — a
      device-wide sync would pay the long kernel's full duration)
  Q3 are a view-created buffer's copies/mappings ordered on the VIEW's stream?
     (tiny D2H via the view while the default stream is busy: per-stream ordering completes
      fast; default-stream ordering would queue behind the long kernel)
  Q4 do 4 streams overlap the same way (the 4-stream admission arm)?

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/multistream_probe.mojo -o msprobe
"""

from max.gpu.host import DeviceBuffer, DeviceContext, HostBuffer
from std.gpu import block_idx, thread_idx
from std.origin import MutAnyOrigin
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime SPIN_ITERS: Int = 60_000_000  # ~one slow kernel's worth per block-grid (tuned below)


def _spin_kernel(sink: _FP, iters_i64: Int64, tag_i64: Int64):
    """A fixed-work busy kernel: every thread runs `iters` dependent FMAs (latency chain, so
    grid size barely matters — wall is set by iters). Two of these on ONE stream serialize;
    on TWO streams they overlap if the runtime really gives us concurrent streams."""
    var iters = Int(iters_i64)
    var tag = Float32(Float64(Int(tag_i64)) * 1.0e-9)
    var gtid = Int(block_idx.x) * 256 + Int(thread_idx.x)
    var acc = Float32(Float64(gtid) * 1.0e-13) + tag
    for i in range(iters):
        acc = acc * Float32(1.0000000001) + Float32(1.0e-13)
    if acc == Float32(1.2345e30):
        sink[gtid] = acc


def _tiny_kernel(sink: _FP):
    var gtid = Int(block_idx.x) * 256 + Int(thread_idx.x)
    sink[gtid] = Float32(gtid)


def _ms(ns: Int) -> Float64:
    return Float64(ns) / 1.0e6


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("multistream_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("multistream_probe: no accelerator")
            return

        var ctx = DeviceContext()
        print("multistream_probe: device:", ctx.name(),
              "| num_streams:", ctx.num_streams())
        # the stream pool grows on create_stream(); select_stream(id) needs id < pool size
        _ = ctx.create_stream()
        _ = ctx.create_stream()
        _ = ctx.create_stream()
        print("multistream_probe: after 3x create_stream, num_streams:", ctx.num_streams())

        var sink0 = ctx.enqueue_create_buffer[DType.float32](1024)
        var sink1 = ctx.enqueue_create_buffer[DType.float32](1024)
        ctx.synchronize()

        # ═══ Q1 — two-stream overlap ═══
        # calibrate: one spin alone on the default stream
        var t0 = perf_counter_ns()
        ctx.enqueue_function[_spin_kernel](
            sink0.unsafe_ptr(), Int64(SPIN_ITERS), Int64(0),
            grid_dim=4, block_dim=256)
        ctx.synchronize()
        var one_ms = _ms(perf_counter_ns() - t0)
        print("Q1: single spin (default stream):", one_ms, "ms")

        # sequential: two spins on the default stream
        t0 = perf_counter_ns()
        ctx.enqueue_function[_spin_kernel](
            sink0.unsafe_ptr(), Int64(SPIN_ITERS), Int64(0),
            grid_dim=4, block_dim=256)
        ctx.enqueue_function[_spin_kernel](
            sink0.unsafe_ptr(), Int64(SPIN_ITERS), Int64(1),
            grid_dim=4, block_dim=256)
        ctx.synchronize()
        var seq_ms = _ms(perf_counter_ns() - t0)
        print("Q1: two spins SEQUENTIAL (default stream):", seq_ms, "ms")

        # concurrent: spin A default stream, spin B on stream 1 (select_stream VIEW —
        # the exact API shape the L5 admission arm will use)
        var v1 = ctx.select_stream(1)
        t0 = perf_counter_ns()
        ctx.enqueue_function[_spin_kernel](
            sink0.unsafe_ptr(), Int64(SPIN_ITERS), Int64(0),
            grid_dim=4, block_dim=256)
        v1.enqueue_function[_spin_kernel](
            sink1.unsafe_ptr(), Int64(SPIN_ITERS), Int64(1),
            grid_dim=4, block_dim=256)
        ctx.synchronize()
        v1.synchronize()
        var con2_ms = _ms(perf_counter_ns() - t0)
        print("Q1: two spins CONCURRENT (2 streams):", con2_ms, "ms",
              "| overlap ratio (seq/concurrent):", seq_ms / con2_ms)

        # ═══ Q4 — four-stream overlap ═══
        var v2 = ctx.select_stream(2)
        var v3 = ctx.select_stream(3)
        var sink2 = ctx.enqueue_create_buffer[DType.float32](1024)
        var sink3 = ctx.enqueue_create_buffer[DType.float32](1024)
        t0 = perf_counter_ns()
        ctx.enqueue_function[_spin_kernel](
            sink0.unsafe_ptr(), Int64(SPIN_ITERS), Int64(0),
            grid_dim=4, block_dim=256)
        v1.enqueue_function[_spin_kernel](
            sink1.unsafe_ptr(), Int64(SPIN_ITERS), Int64(1),
            grid_dim=4, block_dim=256)
        v2.enqueue_function[_spin_kernel](
            sink2.unsafe_ptr(), Int64(SPIN_ITERS), Int64(2),
            grid_dim=4, block_dim=256)
        v3.enqueue_function[_spin_kernel](
            sink3.unsafe_ptr(), Int64(SPIN_ITERS), Int64(3),
            grid_dim=4, block_dim=256)
        ctx.synchronize()
        v1.synchronize()
        v2.synchronize()
        v3.synchronize()
        var con4_ms = _ms(perf_counter_ns() - t0)
        print("Q4: four spins CONCURRENT (4 streams):", con4_ms, "ms",
              "| ratio vs single:", one_ms / con4_ms)

        # ═══ Q2 — is a view's synchronize() per-stream or device-wide? ═══
        # WARM the tiny kernel's JIT on v1 first (a first-use enqueue_function[kernel]
        # compiles host-side; Q2-cold below measures that compile, not a sync scope).
        v1.enqueue_function[_tiny_kernel](
            sink1.unsafe_ptr(), grid_dim=4, block_dim=256)
        v1.synchronize()
        # long kernel on the DEFAULT stream; then a tiny op + sync on the view
        ctx.enqueue_function[_spin_kernel](
            sink0.unsafe_ptr(), Int64(SPIN_ITERS), Int64(0),
            grid_dim=4, block_dim=256)
        t0 = perf_counter_ns()
        v1.enqueue_function[_tiny_kernel](
            sink1.unsafe_ptr(), grid_dim=4, block_dim=256)
        v1.synchronize()
        var viewsync_ms = _ms(perf_counter_ns() - t0)
        ctx.synchronize()
        print("Q2: view(stream1) warm-tiny+sync while default stream busy:", viewsync_ms,
              "ms (device-wide sync would be >=", one_ms, "ms)")

        # ═══ Q5 — is the BASE ctx.synchronize() per-stream or device-wide? ═══
        # (seed_and_run_batched_graph calls it while admission may be in flight on a
        #  side stream — its scope decides whether the decode loop bubbles)
        v1.enqueue_function[_spin_kernel](
            sink1.unsafe_ptr(), Int64(SPIN_ITERS), Int64(9),
            grid_dim=4, block_dim=256)
        t0 = perf_counter_ns()
        ctx.synchronize()
        var basesync_ms = _ms(perf_counter_ns() - t0)
        v1.synchronize()
        print("Q5: base ctx.synchronize() while stream1 busy:", basesync_ms,
              "ms (device-wide sync waits the full", one_ms, "ms spin)",
              "| ctx.stream().synchronize() variant:")
        v1.enqueue_function[_spin_kernel](
            sink1.unsafe_ptr(), Int64(SPIN_ITERS), Int64(9),
            grid_dim=4, block_dim=256)
        t0 = perf_counter_ns()
        ctx.stream().synchronize()
        var streamsync_ms = _ms(perf_counter_ns() - t0)
        v1.synchronize()
        print("Q5: ctx.stream().synchronize() while stream1 busy:", streamsync_ms, "ms")

        # ═══ Q3 — view-created buffer's copies/mappings on the view's stream ═══
        var vbuf = v1.enqueue_create_buffer[DType.float32](256)
        var vhost = v1.enqueue_create_host_buffer[DType.float32](256)
        # long kernel on the DEFAULT stream again
        ctx.enqueue_function[_spin_kernel](
            sink0.unsafe_ptr(), Int64(SPIN_ITERS), Int64(0),
            grid_dim=4, block_dim=256)
        # tiny D2H through the view: fast ONLY if it orders on stream 1
        t0 = perf_counter_ns()
        v1.enqueue_copy(vhost, vbuf)
        v1.synchronize()
        var copy_ms = _ms(perf_counter_ns() - t0)
        ctx.synchronize()
        print("Q3: view D2H copy+sync while default stream busy:", copy_ms,
              "ms (default-stream ordering would be >=", one_ms, "ms)")

        # the map_to_host form the admission prefill uses for token uploads
        ctx.enqueue_function[_spin_kernel](
            sink0.unsafe_ptr(), Int64(SPIN_ITERS), Int64(0),
            grid_dim=4, block_dim=256)
        t0 = perf_counter_ns()
        with vbuf.map_to_host() as h:
            h[0] = Float32(1.0)
        var map_ms = _ms(perf_counter_ns() - t0)
        ctx.synchronize()
        print("Q3: view map_to_host round-trip while default stream busy:", map_ms,
              "ms (device-wide scope would be >=", one_ms, "ms)")

        print("multistream_probe: done")
