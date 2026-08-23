"""graph_race_probe.mojo — the decisive test for the L5 gate-2 corruption: does a TRIVIAL
captured graph, replayed back-to-back while a side stream runs unrelated kernels, keep its
data dependencies intact? The serve-driver selftest fails exactly in that regime (token
divergence, memcheck-clean, per-dispatch passes, no-overlap passes) — this isolates the
runtime question from the driver entirely.

Chain captured (recording_context, sequential): k_seed writes A[i] = STATE[0] + i, k_copy
copies A -> B, k_sum writes C[0] = sum(B). Replayed K times per round with the STATE seed
bumped between rounds; any stale read or broken dependency shows as a wrong C[0]. Meanwhile
a side stream runs a burst of spin kernels concurrent with the replay loop.

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/graph_race_probe.mojo -o graprace
"""

from max.gpu.host import DeviceContext, DeviceGraph, DeviceGraphBuilder
from max.gpu import barrier
from max.gpu.memory import AddressSpace
from std.gpu import thread_idx, global_idx
from std.memory import stack_allocation
from std.origin import MutAnyOrigin
from std.sys import exit, has_accelerator, is_defined

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]

comptime N: Int = 4096
comptime SPIN_ITERS: Int = 4_000_000
comptime K: Int = 50
comptime ROUNDS: Int = 60


def _k_seed(dst: _FP, state: _I64P, n_i64: Int64):
    var n = Int(n_i64)
    var seed = Float32(Float64(state[0]))
    var i = Int(global_idx.x)
    if i < n:
        dst[i] = seed + Float32(i)


def _k_advance(state: _I64P, log: _I64P):
    """The driver's advance-kernel analog: device-side inter-replay feedback — reads the
    current counter, logs it, increments it IN PLACE. Replay k's write is replay k+1's read;
    this cross-replay dependency (ordered only by stream semantics between graph launches)
    is the structure the serve driver's graph arm has and the first probe cut lacked."""
    var s = state[0]
    log[s] = s
    state[0] = s + 1


def _k_copy(dst: _FP, src: _FP, n_i64: Int64):
    var n = Int(n_i64)
    var i = Int(global_idx.x)
    if i < n:
        dst[i] = src[i]


def _k_sum(dst: _FP, src: _FP, n_i64: Int64):
    var n = Int(n_i64)
    var tid = Int(thread_idx.x)
    var red = stack_allocation[256, DType.float32, address_space = AddressSpace.SHARED]()
    var acc = Float32(0.0)
    var i = tid
    while i < n:
        acc += src[i]
        i += 256
    red[tid] = acc
    barrier()
    var s = 128
    while s > 0:
        if tid < s:
            red[tid] = red[tid] + red[tid + s]
        barrier()
        s = s // 2
    if tid == 0:
        dst[0] = red[0]


def _spin_kernel(sink: _FP, iters_i64: Int64, tag_i64: Int64):
    var iters = Int(iters_i64)
    var tag = Float32(Float64(Int(tag_i64)) * 1.0e-9)
    var gtid = Int(global_idx.x)
    var acc = Float32(Float64(gtid) * 1.0e-13) + tag
    for i in range(iters):
        acc = acc * Float32(1.0000000001) + Float32(1.0e-13)
    if acc == Float32(1.2345e30):
        sink[gtid] = acc


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("graph_race_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("graph_race_probe: no accelerator")
            return

        var ctx = DeviceContext()
        _ = ctx.create_stream()
        var v1 = ctx.select_stream(1)

        var A = ctx.enqueue_create_buffer[DType.float32](N)
        var B = ctx.enqueue_create_buffer[DType.float32](N)
        var C = ctx.enqueue_create_buffer[DType.float32](1)
        var state = ctx.enqueue_create_buffer[DType.int64](1)
        var log = ctx.enqueue_create_buffer[DType.int64](ROUNDS * K + 16)
        var hstate = ctx.enqueue_create_host_buffer[DType.int64](1)
        var hC = ctx.enqueue_create_host_buffer[DType.float32](1)
        var hlog = ctx.enqueue_create_host_buffer[DType.int64](ROUNDS * K + 16)
        var spin_sink = v1.enqueue_create_buffer[DType.float32](1024)
        # the side stream's copy churn — the lane map_to_host / readback analog
        var side_dev = v1.enqueue_create_buffer[DType.int32](1024)
        var side_host = v1.enqueue_create_host_buffer[DType.int32](1024)
        ctx.synchronize()

        var f_seed = ctx.compile_function[_k_seed]()
        var f_copy = ctx.compile_function[_k_copy]()
        var f_sum = ctx.compile_function[_k_sum]()
        var f_adv = ctx.compile_function[_k_advance]()

        var a_addr = Int(A.unsafe_ptr())
        var b_addr = Int(B.unsafe_ptr())
        var c_addr = Int(C.unsafe_ptr())
        var st_addr = Int(state.unsafe_ptr())
        var log_addr = Int(log.unsafe_ptr())

        def build(mut builder: DeviceGraphBuilder) raises {imm}:
            var a_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=a_addr)
            var b_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=b_addr)
            var c_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=c_addr)
            var st_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=st_addr)
            var log_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=log_addr)
            var rec = builder.recording_context()
            rec.enqueue_function[_k_seed](
                a_p, st_p, Int64(N), grid_dim=N // 256, block_dim=256)
            rec.enqueue_function[_k_copy](
                b_p, a_p, Int64(N), grid_dim=N // 256, block_dim=256)
            rec.enqueue_function[_k_sum](
                c_p, b_p, Int64(N), grid_dim=1, block_dim=256)
            rec.enqueue_function[_k_advance](
                st_p, log_p, grid_dim=1, block_dim=32)

        var graph = DeviceGraph.create(ctx, build)
        print("graph_race_probe: device:", ctx.name(),
              "| 4-node graph w/ inter-replay feedback, K =", K,
              "replays/round, rounds =", ROUNDS)

        # expected C[0] after K replays from seed s: the LAST replay sums (s+K-1)+i
        var base = Float64(N) * Float64(N - 1) / 2.0

        var bad = 0
        for r in range(ROUNDS):
            var seed = Int64(r * K)
            hstate[0] = seed

            # side stream: spin bursts + copy churn (H2D + D2H) concurrent with BOTH the
            # default-stream seed copy and the replay loop — the lane map_to_host analog
            for s in range(4):
                v1.enqueue_function[_spin_kernel](
                    spin_sink.unsafe_ptr(), Int64(SPIN_ITERS), Int64(s),
                    grid_dim=4, block_dim=256)
            for c in range(8):
                v1.enqueue_copy(side_dev, side_host)   # H2D churn on the side stream
                v1.enqueue_copy(side_host, side_dev)   # D2H churn on the side stream

            ctx.enqueue_copy(state, hstate)
            ctx.synchronize()

            for _ in range(K):
                graph.replay()
            ctx.synchronize()
            ctx.enqueue_copy(hC, C)
            ctx.enqueue_copy(hlog, log)
            ctx.synchronize()

            # 1. final C[0] = sum of the LAST replay's seed
            var got = Float64(hC[0])
            var want = Float64(seed + Int64(K) - 1) * Float64(N) + base
            var diff = got - want
            if diff < 0:
                diff = -diff
            if diff > 1.0:
                bad += 1
                if bad <= 5:
                    print("  ROUND", r, "SUM MISMATCH: got", got, "want", want)
            # 2. the log must hold the exact ascending sequence seed..seed+K-1
            var log_bad = 0
            for i in range(K):
                if hlog[Int(seed) + i] != seed + Int64(i):
                    log_bad += 1
            if log_bad > 0:
                bad += 1
                if bad <= 10:
                    print("  ROUND", r, "LOG CORRUPT:", log_bad, "of", K, "entries",
                          "| log[seed]=", hlog[Int(seed)],
                          "| log[seed+K-1]=", hlog[Int(seed) + K - 1])

        v1.synchronize()
        if bad == 0:
            print("graph_race_probe: PASS —", ROUNDS, "rounds x", K,
                  "replays clean under side-stream concurrency")
        else:
            print("graph_race_probe: FAIL —", bad, "of", ROUNDS, "rounds corrupted")
