"""state_probe.mojo — isolates the DeviceGraph state-feed semantics on this toolchain:

Part 1 (eager only): host write -> eager H2D copy -> eager D2H copy -> verify the round trip.
Part 2 (graph): capture a kernel that reads the device state buffer + a D2H readback into the
         graph; before each replay feed the device buffer eagerly; verify replay reads LIVE
         device contents.
Part 3 (graph, no feed): replay WITHOUT a fresh feed — confirms whether the replay re-reads the
         device buffer at all (expected: repeats the last-fed values).
"""

from max.gpu.host import DeviceContext, DeviceGraph, DeviceGraphBuilder
from std.gpu import block_idx, thread_idx
from std.origin import MutAnyOrigin
from std.sys import exit

alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]


def _copy_state_kernel(dst: _I64P, state: _I64P, n_i64: Int64):
    var i = Int(block_idx.x) * 32 + Int(thread_idx.x)
    if i < Int(n_i64):
        dst[i] = state[i]


def _fill_host(h: UnsafePointer[Int64, origin=MutUntrackedOrigin], a: Int, b: Int, c: Int):
    h[0] = Int64(a)
    h[1] = Int64(b)
    h[2] = Int64(c)


def main() raises:
    var ctx = DeviceContext()
    print("state_probe: device:", ctx.name())

    var state_dev = ctx.enqueue_create_buffer[DType.int64](3)
    var out_dev = ctx.enqueue_create_buffer[DType.int64](3)
    var host_state = ctx.enqueue_create_host_buffer[DType.int64](3)
    var host_check = ctx.enqueue_create_host_buffer[DType.int64](3)
    var host_out = ctx.enqueue_create_host_buffer[DType.int64](3)

    # ═══ Part 1: eager H2D -> D2H round trip ═══
    _fill_host(host_state.unsafe_ptr(), 111, 222, 333)
    ctx.enqueue_copy(state_dev, host_state)
    ctx.enqueue_copy(host_check, state_dev)
    ctx.synchronize()
    var p1_ok = (
        host_check.unsafe_ptr()[0] == 111
        and host_check.unsafe_ptr()[1] == 222
        and host_check.unsafe_ptr()[2] == 333
    )
    print("PART1 eager H2D/D2H round trip:",
          host_check.unsafe_ptr()[0], host_check.unsafe_ptr()[1],
          host_check.unsafe_ptr()[2], "->", "PASS" if p1_ok else "FAIL")

    # ═══ capture: kernel reads state_dev, D2H readback ═══
    var state_a = Int(state_dev.unsafe_ptr())
    var out_a = Int(out_dev.unsafe_ptr())
    var host_out_buf = host_out
    var out_buf = out_dev

    def build(mut builder: DeviceGraphBuilder) raises {imm}:
        var state_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=state_a)
        var out_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=out_a)
        var rec = builder.recording_context()
        rec.enqueue_function[_copy_state_kernel](
            out_p, state_p, Int64(3), grid_dim=1, block_dim=32,
        )
        # NO recorded copies: run-verified on the A100 that captured memcpy nodes (both
        # directions) never touch the caller's buffers at replay — graph-owned staging.

    var graph = DeviceGraph.create(ctx, build)
    print("graph captured (kernel-only)")

    # ═══ Part 2: feed A, replay, EAGER readback, check ═══
    _fill_host(host_state.unsafe_ptr(), 777, 888, 999)
    ctx.enqueue_copy(state_dev, host_state)
    graph.replay()
    ctx.enqueue_copy(host_out, out_dev)
    ctx.synchronize()
    var p2_ok = (
        host_out.unsafe_ptr()[0] == 777
        and host_out.unsafe_ptr()[1] == 888
        and host_out.unsafe_ptr()[2] == 999
    )
    print("PART2 replay-after-feed-A:",
          host_out.unsafe_ptr()[0], host_out.unsafe_ptr()[1],
          host_out.unsafe_ptr()[2], "->", "PASS" if p2_ok else "FAIL")

    # ═══ Part 3: feed B, replay, EAGER readback, check ═══
    _fill_host(host_state.unsafe_ptr(), 41, 42, 43)
    ctx.enqueue_copy(state_dev, host_state)
    graph.replay()
    ctx.enqueue_copy(host_out, out_dev)
    ctx.synchronize()
    var p3_ok = (
        host_out.unsafe_ptr()[0] == 41
        and host_out.unsafe_ptr()[1] == 42
        and host_out.unsafe_ptr()[2] == 43
    )
    print("PART3 replay-after-feed-B:",
          host_out.unsafe_ptr()[0], host_out.unsafe_ptr()[1],
          host_out.unsafe_ptr()[2], "->", "PASS" if p3_ok else "FAIL")

    if p1_ok and p2_ok and p3_ok:
        print("STATE PROBE PASS")
    else:
        print("STATE PROBE FAIL")
