"""Graphscale_probe.mojo — LEVER L7 bisect, stage 2: which ingredient of the serve driver's
co-residency corrupts a BASE-captured graph? Round-2 regime (gate 2 with forced graph-under-
lanes) diverges 3/8; graphsync_probe (this round) proved single-copy seed ordering, lane
visibility, base sync scope and cross-view waits are ALL sound under spin pressure with a
2-node graph. What the driver adds: a 258-node chain, K>1 back-to-back replays, and
lane-shaped side traffic (many kernels + H2D/D2H copy churn). Each part A/B's ONE ingredient
with a data check:

  S1  258-node base graph, K=8 back-to-back replays, QUIET GPU
  S2  S1 + co-resident spin bursts (plain compute pressure)
  S3  S1 + lane-shaped side traffic (spin + H2D/D2H copy churn)
  S4  S3 with per-replay host sync (one sync between consecutive replays)
  S5  S3 with K=1 (seed + single replay + sync per round — isolates multi-replay)
  S6  2-node graph + S3 traffic (control: is it the NODE COUNT at all?)

The graph keeps the driver's shape: a long internal dependency chain (ping-pong elementwise
passes, the 258-kernel chain's ordering analog) + one terminal kernel that reads the seeded
STATE region (the embed-reads-STATE analog). Every replay writes C[0] = STATE[0]; any wrong
C[0] names its round's seed as the divergence marker. Build:

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/graphscale_probe.mojo -o graphscale
"""

from max.gpu.host import DeviceBuffer, DeviceContext, DeviceGraph, DeviceGraphBuilder, HostBuffer
from std.gpu import global_idx
from std.origin import MutAnyOrigin
from std.sys import has_accelerator, is_defined
from std.time import perf_counter_ns

comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
comptime _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]
comptime _I32P = UnsafePointer[Int32, origin=MutAnyOrigin]

comptime N: Int = 4096
comptime CHAIN: Int = 257
comptime ROUNDS: Int = 100
comptime K: Int = 8
comptime SPIN_ITERS: Int = 4_000_000


def _ping(dst: _FP, src: _FP, n_i64: Int64):
    var n = Int(n_i64)
    var i = Int(global_idx.x)
    if i < n:
        dst[i] = src[i] + Float32(1.0)


def _read_state(dst: _FP, state: _I64P, src: _FP):
    """Terminal node: C[0] = STATE[0] + (src[0] - src[0]) — reads the seeded region AND a
    chain buffer, so a torn chain AND a torn seed both surface as a wrong C[0]."""
    if Int(global_idx.x) == 0:
        dst[0] = Float32(Float64(state[0])) + (src[0] - src[0])


def _spin_kernel(sink: _FP, iters_i64: Int64, tag_i64: Int64):
    var iters = Int(iters_i64)
    var tag = Float32(Float64(Int(tag_i64)) * 1.0e-9)
    var gtid = Int(global_idx.x)
    var acc = Float32(Float64(gtid) * 1.0e-13) + tag
    for i in range(iters):
        acc = acc * Float32(1.0000000001) + Float32(1.0e-13)
    if acc == Float32(1.2345e30):
        sink[gtid] = acc


def _fill_f32(dst: _FP, val_i64: Int64, n_i64: Int64):
    var val = Float32(Float64(Int(val_i64)))
    var n = Int(n_i64)
    var i = Int(global_idx.x)
    if i < n:
        dst[i] = val


def _ms(ns: Int) -> Float64:
    return Float64(ns) / 1.0e6


def _run_battery(
    tag: String, ref g: DeviceGraph, ctx: DeviceContext, v_lane: DeviceContext,
    mut state: DeviceBuffer[DType.int64], mut hstate: HostBuffer[DType.int64],
    mut C: DeviceBuffer[DType.float32], mut hC: HostBuffer[DType.float32],
    mut sink_lane: DeviceBuffer[DType.float32],
    mut churn_dev: DeviceBuffer[DType.int32], mut churn_host: HostBuffer[DType.int32],
    k_steps: Int, pressure: Int, per_step_sync: Bool,
) raises:
    var bad = 0
    var t0 = perf_counter_ns()
    for r in range(ROUNDS):
        var seed = Int64(r + 1)
        hstate.unsafe_ptr()[0] = seed
        if pressure == 1:
            # plain compute pressure on the lane stream
            v_lane.enqueue_function[_spin_kernel](
                sink_lane.unsafe_ptr(), Int64(SPIN_ITERS), Int64(r),
                grid_dim=108, block_dim=256)
        elif pressure == 2:
            # lane-shaped traffic: a long spin + H2D/D2H copy churn (the admission lane's
            # kernel stream + argmax readback + token-upload traffic, shape-matched)
            v_lane.enqueue_function[_spin_kernel](
                sink_lane.unsafe_ptr(), Int64(SPIN_ITERS), Int64(r),
                grid_dim=108, block_dim=256)
            var hp = churn_host.unsafe_ptr()
            for c in range(8):
                hp[0] = Int32(c)
                v_lane.enqueue_copy(churn_dev, churn_host)
                v_lane.enqueue_copy(churn_host, churn_dev)
        ctx.enqueue_copy(state, hstate)
        ctx.synchronize()
        for s in range(k_steps):
            g.replay()
            if per_step_sync:
                ctx.synchronize()
        ctx.synchronize()
        ctx.enqueue_copy(hC, C)
        ctx.synchronize()
        var got = Float64(hC.unsafe_ptr()[0])
        var want = Float64(seed)  # STATE never advances in this probe; every replay re-reads
        var diff = got - want
        if diff < 0:
            diff = -diff
        if diff > 0.5:
            bad += 1
            if bad <= 3:
                print("   ", tag, "round", r, "got", got, "want", want)
        if pressure > 0:
            v_lane.synchronize()
    var wall = _ms(perf_counter_ns() - t0)
    print(tag, ":", bad, "of", ROUNDS, "rounds wrong |",
          "CLEAN" if bad == 0 else "CORRUPT", "| wall", wall, "ms")


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("graphscale_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("graphscale_probe: no accelerator")
            return

        var ctx = DeviceContext()
        _ = ctx.create_stream()
        var v_lane = ctx.select_stream(1)
        print("graphscale_probe: device:", ctx.name())

        var A = ctx.enqueue_create_buffer[DType.float32](N)
        var B = ctx.enqueue_create_buffer[DType.float32](N)
        var C = ctx.enqueue_create_buffer[DType.float32](1)
        var state = ctx.enqueue_create_buffer[DType.int64](1)
        var hstate = ctx.enqueue_create_host_buffer[DType.int64](1)
        var hC = ctx.enqueue_create_host_buffer[DType.float32](1)
        var sink_lane = v_lane.enqueue_create_buffer[DType.float32](1024)
        var churn_dev = v_lane.enqueue_create_buffer[DType.int32](1024)
        var churn_host = v_lane.enqueue_create_host_buffer[DType.int32](1024)
        # zero the chain buffers so every pass adds 1 from a known base
        ctx.enqueue_function[_fill_f32](A.unsafe_ptr(), Int64(0), Int64(N),
                                        grid_dim=N // 256, block_dim=256)
        ctx.enqueue_function[_fill_f32](B.unsafe_ptr(), Int64(0), Int64(N),
                                        grid_dim=N // 256, block_dim=256)
        ctx.synchronize()

        # warm the side kernels' JIT
        v_lane.enqueue_function[_spin_kernel](
            sink_lane.unsafe_ptr(), Int64(1000), Int64(0), grid_dim=4, block_dim=256)
        v_lane.synchronize()

        var a_addr = Int(A.unsafe_ptr())
        var b_addr = Int(B.unsafe_ptr())
        var c_addr = Int(C.unsafe_ptr())
        var st_addr = Int(state.unsafe_ptr())

        # ═══ the 258-node chain: CHAIN ping-pong passes + the terminal state read ═══
        def build_chain(mut builder: DeviceGraphBuilder) raises {imm}:
            var a_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=a_addr)
            var b_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=b_addr)
            var c_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=c_addr)
            var st_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=st_addr)
            var rec = builder.recording_context()
            for j in range(CHAIN):
                if j % 2 == 0:
                    rec.enqueue_function[_ping](
                        b_p, a_p, Int64(N), grid_dim=N // 256, block_dim=256)
                else:
                    rec.enqueue_function[_ping](
                        a_p, b_p, Int64(N), grid_dim=N // 256, block_dim=256)
            # after CHAIN=257 passes (odd) the fresh result lives in A
            rec.enqueue_function[_read_state](
                c_p, st_p, a_p, grid_dim=1, block_dim=32)

        var g_chain = DeviceGraph.create(ctx, build_chain)

        # the 2-node control (graphsync's shape, same terminal read off B)
        def build_two(mut builder: DeviceGraphBuilder) raises {imm}:
            var a_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=a_addr)
            var b_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=b_addr)
            var c_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=c_addr)
            var st_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=st_addr)
            var rec = builder.recording_context()
            rec.enqueue_function[_ping](
                b_p, a_p, Int64(N), grid_dim=N // 256, block_dim=256)
            rec.enqueue_function[_read_state](
                c_p, st_p, b_p, grid_dim=1, block_dim=32)
        var g_two = DeviceGraph.create(ctx, build_two)

        # quiet warmup of both graphs (capture + one replay each)
        hstate.unsafe_ptr()[0] = Int64(0)
        ctx.enqueue_copy(state, hstate)
        ctx.synchronize()
        g_chain.replay()
        g_two.replay()
        ctx.synchronize()

        _run_battery("S1 258-node K=8 quiet", g_chain, ctx, v_lane, state, hstate, C, hC,
                     sink_lane, churn_dev, churn_host, K, 0, False)
        _run_battery("S2 258-node K=8 +spin", g_chain, ctx, v_lane, state, hstate, C, hC,
                     sink_lane, churn_dev, churn_host, K, 1, False)
        _run_battery("S3 258-node K=8 +lane-traffic", g_chain, ctx, v_lane, state, hstate,
                     C, hC, sink_lane, churn_dev, churn_host, K, 2, False)
        _run_battery("S4 258-node K=8 +lane-traffic per-step-sync", g_chain, ctx, v_lane,
                     state, hstate, C, hC, sink_lane, churn_dev, churn_host, K, 2, True)
        _run_battery("S5 258-node K=1 +lane-traffic", g_chain, ctx, v_lane, state, hstate,
                     C, hC, sink_lane, churn_dev, churn_host, 1, 2, False)
        _run_battery("S6 2-node K=8 +lane-traffic", g_two, ctx, v_lane, state, hstate, C, hC,
                     sink_lane, churn_dev, churn_host, K, 2, False)

        print("graphscale_probe: done")
