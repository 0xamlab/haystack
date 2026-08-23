"""graphsync_probe.mojo — LEVER L7 groundwork: characterize the ORDERING SEMANTICS of
DeviceGraph.replay() against streams and events on this toolchain (MAX 26.5 / Mojo 1.0.0),
with data checks, not timing guesses. The round-2 bisect proved a captured graph replayed
co-resident with side-stream work mis-reads state (the seed copy raced replay #1 per the
L5 commit; the mechanism was never isolated). L7 needs these facts before choosing fences:

  Q1 does replay() order after a PRECEDING base-stream enqueue_copy with NO host sync in
     between? (the seed-feed race the L5 commit names). Tested quiet AND under side-stream
     pressure (a heavy spin grid on a side stream enqueued just before the copy, contending
     for the copy engine / SMs the way admission lanes do).
  Q2 can a DeviceGraph be CAPTURED against a select_stream view (dedicated replay stream)?
  Q3 if captured on a side stream, does an enqueue_wait_for(event) on that stream order the
     next replay after an event recorded on the base stream (the seed-copy fence shape)?
  Q4 does the BASE ctx.synchronize() wait in-flight replays (timing of a spin-graph)?
  Q5 graph->lane direction: replay-stream writes, lane stream waits an event, reads — does
     the value arrive?
  Q6 lane->graph direction WITHOUT events: side-stream fill + view.synchronize(), then a
     replay reads the buffer — is host-sync visibility enough for graph reads?
  Q7 DeviceContext.enqueue_wait_for(other_view) (the Self overload): does the base context
     wait another view's enqueued work? (measures whether it blocks on the other stream)

Every question prints a data-backed PASS/FAIL. Build:

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/graphsync_probe.mojo -o graphsync
"""

from max.gpu.host import DeviceContext, DeviceEvent, DeviceGraph, DeviceGraphBuilder
from std.collections import Optional
from std.gpu import block_idx, thread_idx, global_idx
from std.origin import MutAnyOrigin
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]

comptime N: Int = 4096
comptime SPIN_ITERS: Int = 30_000_000   # ~150-200 ms latency chain per launch
comptime SPIN_ITERS_SHORT: Int = 4_000_000
comptime ROUNDS: Int = 200


def _spin_kernel(sink: _FP, iters_i64: Int64, tag_i64: Int64):
    var iters = Int(iters_i64)
    var tag = Float32(Float64(Int(tag_i64)) * 1.0e-9)
    var gtid = Int(global_idx.x)
    var acc = Float32(Float64(gtid) * 1.0e-13) + tag
    for i in range(iters):
        acc = acc * Float32(1.0000000001) + Float32(1.0e-13)
    if acc == Float32(1.2345e30):
        sink[gtid] = acc


def _fill_i64(dst: _I64P, val_i64: Int64, n_i64: Int64):
    var n = Int(n_i64)
    var i = Int(global_idx.x)
    if i < n:
        dst[i] = val_i64


def _seed_a(dst: _FP, state: _I64P, n_i64: Int64):
    """A[i] = STATE[0] + i — the graph's only read of host-seeded state (the serve driver's
    embed-reads-STATE analog)."""
    var n = Int(n_i64)
    var seed = Float32(Float64(state[0]))
    var i = Int(global_idx.x)
    if i < n:
        dst[i] = seed + Float32(i)


def _sum_f32(dst: _FP, src: _FP, n_i64: Int64):
    """C[0] = sum(A) — naive single-block sum (N=4096, one 256-thread block grid-stride)."""
    var n = Int(n_i64)
    var acc = Float32(0.0)
    var i = Int(thread_idx.x)
    while i < n:
        acc += src[i]
        i += 256
    # no barrier: single-warp-free sequential per-thread stride then thread-0 serial sum is
    # WRONG for parallel threads — keep it trivially correct: thread 0 sums everything
    if Int(thread_idx.x) == 0:
        var s = Float32(0.0)
        for j in range(n):
            s += src[j]
        dst[0] = s


def _read_first_f32(dst: _FP, src: _I64P):
    """dst[0] = Float32(src[0]) — an int64 read converted to f32 (no bitcast aliasing)."""
    if Int(global_idx.x) == 0:
        dst[0] = Float32(Float64(src[0]))


def _read_first_i64(dst: _I64P, src: _I64P):
    if Int(global_idx.x) == 0:
        dst[0] = src[0]


def _ms(ns: Int) -> Float64:
    return Float64(ns) / 1.0e6


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("graphsync_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("graphsync_probe: no accelerator")
            return

        var ctx = DeviceContext()
        # KEEP the DeviceStream handles — record_event / enqueue_wait_for(event) live on
        # DeviceStream, not on the DeviceContext views (compile-measured, L7 round 3)
        var s_lane = ctx.create_stream()   # stream 1 — the "lane"
        var s_graph = ctx.create_stream()  # stream 2 — the dedicated "graph" stream candidate
        var s_press = ctx.create_stream()  # stream 3 — pressure
        var v_lane = ctx.select_stream(1)
        var v_graph = ctx.select_stream(2)
        var v_press = ctx.select_stream(3)
        print("graphsync_probe: device:", ctx.name(),
              "| num_streams:", ctx.num_streams())

        var A = ctx.enqueue_create_buffer[DType.float32](N)
        var C = ctx.enqueue_create_buffer[DType.float32](1)
        var state = ctx.enqueue_create_buffer[DType.int64](1)
        var shared = ctx.enqueue_create_buffer[DType.int64](16)
        var hstate = ctx.enqueue_create_host_buffer[DType.int64](1)
        var hC = ctx.enqueue_create_host_buffer[DType.float32](1)
        var hshared = ctx.enqueue_create_host_buffer[DType.int64](16)
        var sink_lane = v_lane.enqueue_create_buffer[DType.float32](1024)
        var sink_press = v_press.enqueue_create_buffer[DType.float32](1024)
        ctx.synchronize()

        var base = Float64(N) * Float64(N - 1) / 2.0

        # warm every kernel's JIT on the streams that will use them (first-use compiles)
        v_press.enqueue_function[_spin_kernel](
            sink_press.unsafe_ptr(), Int64(1000), Int64(0), grid_dim=4, block_dim=256)
        v_lane.enqueue_function[_fill_i64](
            shared.unsafe_ptr(), Int64(0), Int64(16), grid_dim=1, block_dim=256)
        v_lane.enqueue_function[_spin_kernel](
            sink_lane.unsafe_ptr(), Int64(1000), Int64(0), grid_dim=4, block_dim=256)
        v_lane.synchronize()
        v_press.synchronize()

        # ═══ capture the two graphs ═══
        # G_base: captured against the BASE context (the serve driver's current shape)
        var a_addr = Int(A.unsafe_ptr())
        var c_addr = Int(C.unsafe_ptr())
        var st_addr = Int(state.unsafe_ptr())
        var shared_addr = Int(shared.unsafe_ptr())

        def build_sum(mut builder: DeviceGraphBuilder) raises {imm}:
            var a_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=a_addr)
            var c_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=c_addr)
            var st_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=st_addr)
            var rec = builder.recording_context()
            rec.enqueue_function[_seed_a](
                a_p, st_p, Int64(N), grid_dim=N // 256, block_dim=256)
            rec.enqueue_function[_sum_f32](
                c_p, a_p, Int64(N), grid_dim=1, block_dim=256)

        var g_base = DeviceGraph.create(ctx, build_sum)

        # Q2 — can capture run against a select_stream view?
        var q2_ok = True
        var g_side = Optional[DeviceGraph]()
        try:
            g_side = DeviceGraph.create(v_graph, build_sum)
        except e:
            q2_ok = False
            print("Q2: DeviceGraph.create(select_stream view) RAISED:", String(e))
        print("Q2: capture on a select_stream view:",
              "WORKS" if q2_ok else "NOT SUPPORTED")

        # a read-shared graph for Q5/Q6 (reads shared[0] into C as float)
        def build_read_shared(mut builder: DeviceGraphBuilder) raises {imm}:
            var c_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=c_addr)
            var sh_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=shared_addr)
            var rec = builder.recording_context()
            rec.enqueue_function[_read_first_f32](
                c_p, sh_p, grid_dim=1, block_dim=32)
        var g_read_base = DeviceGraph.create(ctx, build_read_shared)
        var g_read_side = Optional[DeviceGraph]()
        if q2_ok:
            g_read_side = DeviceGraph.create(v_graph, build_read_shared)

        # warm the graph internals once quietly
        hstate[0] = Int64(0)
        ctx.enqueue_copy(state, hstate)
        ctx.synchronize()
        g_base.replay()
        ctx.synchronize()

        # ═══ Q1 — replay ordering vs a preceding base-stream copy, NO host sync ═══
        for pressure in range(2):
            var bad = 0
            var stale = 0
            for r in range(ROUNDS):
                var seed = Int64(r + 1)
                hstate[0] = seed
                if pressure == 1:
                    # heavy co-resident pressure: spin grid + copy churn on side streams,
                    # enqueued just BEFORE the seed copy (the admission-wave shape)
                    v_press.enqueue_function[_spin_kernel](
                        sink_press.unsafe_ptr(), Int64(SPIN_ITERS_SHORT), Int64(r),
                        grid_dim=108, block_dim=256)
                    v_lane.enqueue_function[_spin_kernel](
                        sink_lane.unsafe_ptr(), Int64(SPIN_ITERS_SHORT), Int64(r),
                        grid_dim=108, block_dim=256)
                ctx.enqueue_copy(state, hstate)
                g_base.replay()
                ctx.synchronize()
                ctx.enqueue_copy(hC, C)
                ctx.synchronize()
                var got = Float64(hC[0])
                var want = Float64(seed) * Float64(N) + base
                var want_prev = Float64(seed - 1) * Float64(N) + base
                var diff = got - want
                if diff < 0:
                    diff = -diff
                if diff > 1.0:
                    bad += 1
                    var dprev = got - want_prev
                    if dprev < 0:
                        dprev = -dprev
                    if dprev <= 1.0:
                        stale += 1
                if pressure == 1:
                    v_press.synchronize()
                    v_lane.synchronize()
            print("Q1 base-captured replay vs preceding copy, no host sync",
                  "(pressure=" + String(pressure) + "):",
                  bad, "of", ROUNDS, "rounds wrong",
                  "(" + String(stale) + " read the PREVIOUS seed)" if bad > 0 else "",
                  "|", "ORDERED" if bad == 0 else "RACES")

        # ═══ Q3 — dedicated replay stream + event fence from the base stream ═══
        if q2_ok:
            var ev_seed = ctx.create_event()
            var bad = 0
            var stale = 0
            for r in range(ROUNDS):
                var seed = Int64(10000 + r + 1)
                hstate[0] = seed
                v_press.enqueue_function[_spin_kernel](
                    sink_press.unsafe_ptr(), Int64(SPIN_ITERS_SHORT), Int64(r),
                    grid_dim=108, block_dim=256)
                v_lane.enqueue_function[_spin_kernel](
                    sink_lane.unsafe_ptr(), Int64(SPIN_ITERS_SHORT), Int64(r),
                    grid_dim=108, block_dim=256)
                ctx.enqueue_copy(state, hstate)
                # fence: record AFTER the seed copy on stream 0; the graph's stream waits it
                ctx.stream().record_event(ev_seed)
                s_graph.enqueue_wait_for(ev_seed)
                g_side.value().replay()
                v_graph.synchronize()
                ctx.enqueue_copy(hC, C)
                ctx.synchronize()
                var got = Float64(hC[0])
                var want = Float64(seed) * Float64(N) + base
                var want_prev = Float64(seed - 1) * Float64(N) + base
                var diff = got - want
                if diff < 0:
                    diff = -diff
                if diff > 1.0:
                    bad += 1
                    var dprev = got - want_prev
                    if dprev < 0:
                        dprev = -dprev
                    if dprev <= 1.0:
                        stale += 1
                v_press.synchronize()
                v_lane.synchronize()
            print("Q3 side-stream capture + event fence under pressure:",
                  bad, "of", ROUNDS, "rounds wrong",
                  "(" + String(stale) + " stale)" if bad > 0 else "",
                  "|", "FENCE WORKS" if bad == 0 else "FENCE FAILS")

            # Q3b — same shape WITHOUT the event fence (isolate the fence's contribution):
            # side-stream capture, no wait — does the replay order after the base copy at all?
            bad = 0
            stale = 0
            for r in range(ROUNDS):
                var seed = Int64(20000 + r + 1)
                hstate[0] = seed
                v_press.enqueue_function[_spin_kernel](
                    sink_press.unsafe_ptr(), Int64(SPIN_ITERS_SHORT), Int64(r),
                    grid_dim=108, block_dim=256)
                ctx.enqueue_copy(state, hstate)
                g_side.value().replay()
                v_graph.synchronize()
                ctx.enqueue_copy(hC, C)
                ctx.synchronize()
                var got = Float64(hC[0])
                var want = Float64(seed) * Float64(N) + base
                var want_prev = Float64(seed - 1) * Float64(N) + base
                var diff = got - want
                if diff < 0:
                    diff = -diff
                if diff > 1.0:
                    bad += 1
                    var dprev = got - want_prev
                    if dprev < 0:
                        dprev = -dprev
                    if dprev <= 1.0:
                        stale += 1
                v_press.synchronize()
            print("Q3b side-stream capture, NO fence, under pressure:",
                  bad, "of", ROUNDS, "rounds wrong",
                  "(" + String(stale) + " stale)" if bad > 0 else "",
                  "|", "cross-stream replay orders alone" if bad == 0 else "RACES (fence required)")

        # ═══ Q4 — does the base ctx.synchronize() wait in-flight replays? ═══
        # a graph holding one LONG spin; replay it, then time ctx.synchronize()
        var sink_graph = v_graph.enqueue_create_buffer[DType.float32](1024)
        var sg_addr = Int(sink_graph.unsafe_ptr())

        def build_spin(mut builder: DeviceGraphBuilder) raises {imm}:
            var sk_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=sg_addr)
            var rec = builder.recording_context()
            rec.enqueue_function[_spin_kernel](
                sk_p, Int64(SPIN_ITERS), Int64(7), grid_dim=4, block_dim=256)
        var g_spin_base = DeviceGraph.create(ctx, build_spin)

        # calibrate the spin alone on stream 0
        var t0 = perf_counter_ns()
        ctx.enqueue_function[_spin_kernel](
            sink_graph.unsafe_ptr(), Int64(SPIN_ITERS), Int64(8),
            grid_dim=4, block_dim=256)
        ctx.synchronize()
        var spin_ms = _ms(perf_counter_ns() - t0)

        t0 = perf_counter_ns()
        g_spin_base.replay()
        ctx.synchronize()
        var basesync_ms = _ms(perf_counter_ns() - t0)
        print("Q4 base ctx.synchronize() vs in-flight replay of a", spin_ms,
              "ms spin-graph: replay+sync wall", basesync_ms, "ms |",
              "WAITS replay" if basesync_ms > spin_ms * 0.5
              else "DOES NOT WAIT (replay lives off the base stream)")

        # ═══ Q5 — graph->lane direction with an event fence ═══
        if q2_ok:
            var ev_g = ctx.create_event()
            # graph (side stream) writes shared[0] = 555; lane waits the fence, reads it
            def build_write_shared(mut builder: DeviceGraphBuilder) raises {imm}:
                var sh_p = UnsafePointer[Int64, origin=MutAnyOrigin](
                    unsafe_from_address=shared_addr)
                var rec = builder.recording_context()
                rec.enqueue_function[_fill_i64](
                    sh_p, Int64(555), Int64(16), grid_dim=1, block_dim=32)
            var g_write = DeviceGraph.create(v_graph, build_write_shared)
            var q5_bad = 0
            for r in range(100):
                # dirty shared with another value first (lane stream), drain lane only
                v_lane.enqueue_function[_fill_i64](
                    shared.unsafe_ptr(), Int64(-1), Int64(16), grid_dim=1, block_dim=32)
                v_lane.synchronize()
                g_write.replay()
                s_graph.record_event(ev_g)
                s_lane.enqueue_wait_for(ev_g)
                v_lane.enqueue_copy(hshared, shared)
                v_lane.synchronize()
                if hshared[0] != Int64(555):
                    q5_bad += 1
            print("Q5 graph->lane event fence (replay writes, lane waits+reads):",
                  q5_bad, "of 100 wrong |", "WORKS" if q5_bad == 0 else "FAILS")

        # ═══ Q6 — lane->graph with ONLY a host sync (no events) ═══
        # lane fills shared=999, view.synchronize(), graph reads it — under pressure
        var q6_bad = 0
        for r in range(ROUNDS):
            v_press.enqueue_function[_spin_kernel](
                sink_press.unsafe_ptr(), Int64(SPIN_ITERS_SHORT), Int64(r),
                grid_dim=108, block_dim=256)
            v_lane.enqueue_function[_fill_i64](
                shared.unsafe_ptr(), Int64(999), Int64(16), grid_dim=1, block_dim=32)
            v_lane.synchronize()
            g_read_base.replay()
            ctx.synchronize()
            ctx.enqueue_copy(hC, C)
            ctx.synchronize()
            if Float64(hC[0]) != 999.0:
                q6_bad += 1
            v_press.synchronize()
        print("Q6 lane->graph visibility with host-sync only (base graph, under pressure):",
              q6_bad, "of", ROUNDS, "wrong |",
              "VISIBLE" if q6_bad == 0 else "NOT VISIBLE (events required)")

        # ═══ Q7 — DeviceContext.enqueue_wait_for(other view) semantics ═══
        # lane enqueues a long spin; base calls enqueue_wait_for(v_lane), then a tiny op +
        # base sync: the wall includes the spin ONLY if the wait really crossed streams
        v_lane.enqueue_function[_spin_kernel](
            sink_lane.unsafe_ptr(), Int64(SPIN_ITERS), Int64(11),
            grid_dim=4, block_dim=256)
        t0 = perf_counter_ns()
        ctx.enqueue_wait_for(v_lane)
        ctx.enqueue_function[_fill_i64](
            shared.unsafe_ptr(), Int64(7), Int64(16), grid_dim=1, block_dim=32)
        ctx.synchronize()
        var q7_ms = _ms(perf_counter_ns() - t0)
        v_lane.synchronize()
        print("Q7 base ctx.enqueue_wait_for(lane view) then tiny op + sync:", q7_ms,
              "ms vs spin", spin_ms, "ms |",
              "WAITS other stream" if q7_ms > spin_ms * 0.5
              else "DOES NOT WAIT")

        print("graphsync_probe: done")
