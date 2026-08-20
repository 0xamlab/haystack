"""cuda_graph_probe.mojo — de-risk probe for the Phase-3a lever: can the pinned toolchain
(mojo 1.0.0 / max 26.5.0) capture a multi-kernel decode-shaped sequence with
`max.gpu.host.DeviceGraph` and replay it with correct results on a real NVIDIA GPU?

What it verifies, in order:
  1. `DeviceGraph.create(ctx, build)` + `builder.recording_context()` records ordinary
     `enqueue_function[kernel]` calls (the spelling residentk.session_cuda uses) as graph
     nodes instead of executing them eagerly.
  2. The dynamic-scalar pattern the graph decode arm needs: kernels read their per-token
     scalars (token_id / pos / n_keys) from a small device STATE buffer instead of taking
     them by value, so ONE captured graph serves every decode step — the host writes the
     scalars into a pinned host buffer, one H2D copy feeds the graph, and the graph is
     replayed unchanged.
  3. `graph.replay()` x SLOTS produces the same results as the eager dispatch sequence,
     including the in-place accumulation pattern (the decode KV-cache write shape: each
     replay writes the NEW slot derived from the state buffer, earlier slots untouched).
  4. A D2H readback copy recorded INSIDE the graph lands the result on the host after
     replay + synchronize — the argmax readback shape the session's step ends with.

Exit output "PROBE PASS" only if every replayed step matches the eager oracle exactly.

Build (same recipe as qwen3_generate_cuda):
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/cuda_graph_probe.mojo -o probe
"""

from max.gpu.host import DeviceContext, DeviceGraph, DeviceGraphBuilder
from std.gpu import block_idx, thread_idx
from std.memory import UnsafePointer
from std.origin import MutAnyOrigin
from std.sys import has_accelerator, is_defined

alias _F32P = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]

comptime CUDA_BUILD: Bool = is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()

comptime N: Int = 256
"""Vector width — decode-kernel-shaped grid (one thread per element)."""

comptime SLOTS: Int = 8
"""Sequential replays = decode steps simulated."""


def _scale_kernel(out: _F32P, state: _I64P, base: _F32P, n_i64: Int64):
    """out[i] = base[i] * state[0] — reads the dynamic scalar from the state buffer: the
    pattern the graph arm's embed twin uses for token_id."""
    var i = Int(block_idx.x) * 128 + Int(thread_idx.x)
    if i < Int(n_i64):
        out[i] = base[i] * Float32(state[0])


def _slot_accum_kernel(acc: _F32P, state: _I64P, src: _F32P):
    """acc[state[1]] += src[0] — writes a state-derived SLOT: the KV-cache-write shape.
    Each replay lands in a different slot and must not disturb the others."""
    var i = Int(block_idx.x) * 128 + Int(thread_idx.x)
    if i == 0:
        acc[state[1]] = acc[state[1]] + src[0]


def _reduce_kernel(out: _F32P, acc: _F32P, slots_i64: Int64):
    """out[0] = sum(acc[0:slots]) — the lm_head+argmax-reduce stand-in."""
    if Int(block_idx.x) == 0 and Int(thread_idx.x) == 0:
        var s = Float32(0)
        for i in range(Int(slots_i64)):
            s += acc[i]
        out[0] = s


def main() raises:
    @parameter
    if not CUDA_BUILD:
        print("cuda_graph_probe: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("cuda_graph_probe: no accelerator on this host")
            return

        var ctx = DeviceContext()
        print("cuda_graph_probe: device:", ctx.name())

        # ── resident buffers (fixed addresses, valid for the graph's life) ──
        var base = ctx.enqueue_create_buffer[DType.float32](N)
        var out = ctx.enqueue_create_buffer[DType.float32](N)
        var acc = ctx.enqueue_create_buffer[DType.float32](SLOTS)
        var result = ctx.enqueue_create_buffer[DType.float32](1)
        var state = ctx.enqueue_create_buffer[DType.int64](3)
        var host_state = ctx.enqueue_create_host_buffer[DType.int64](3)
        var host_result = ctx.enqueue_create_host_buffer[DType.float32](1)

        # base[i] = i + 1 ; acc zeroed (upload via host buffers)
        var host_base = ctx.enqueue_create_host_buffer[DType.float32](N)
        for i in range(N):
            host_base.unsafe_ptr()[i] = Float32(i + 1)
        ctx.enqueue_copy(base, host_base)
        var host_acc = ctx.enqueue_create_host_buffer[DType.float32](SLOTS)
        for i in range(SLOTS):
            host_acc.unsafe_ptr()[i] = Float32(0)
        ctx.enqueue_copy(acc, host_acc)
        ctx.synchronize()

        # ── capture: the recording context records ordinary enqueue calls ──
        def build(mut builder: DeviceGraphBuilder) raises {imm}:
            var rec = builder.recording_context()
            rec.enqueue_function[_scale_kernel](
                out.unsafe_ptr(), state.unsafe_ptr(), base.unsafe_ptr(), Int64(N),
                grid_dim=(N + 127) // 128, block_dim=128,
            )
            rec.enqueue_function[_slot_accum_kernel](
                acc.unsafe_ptr(), state.unsafe_ptr(), out.unsafe_ptr(),
                grid_dim=1, block_dim=128,
            )
            rec.enqueue_function[_reduce_kernel](
                result.unsafe_ptr(), acc.unsafe_ptr(), Int64(SLOTS),
                grid_dim=1, block_dim=1,
            )
            rec.enqueue_copy(host_result, result)

        var graph = DeviceGraph.create(ctx, build)
        print("cuda_graph_probe: graph captured (", SLOTS, "replays planned )")

        # ── replay loop, checked against the eager oracle ──
        var expected_sum = Float32(0)
        var all_ok = True
        for step in range(SLOTS):
            # the dynamic scalars for this step: scale = step+2, slot = step
            host_state.unsafe_ptr()[0] = Int64(step + 2)
            host_state.unsafe_ptr()[1] = Int64(step)
            host_state.unsafe_ptr()[2] = Int64(0)
            ctx.enqueue_copy(state, host_state)
            graph.replay()
            ctx.synchronize()

            # eager oracle: acc[step] += out[0] where out[0] = base[0] * (step+2) = step+2
            expected_sum += Float32(step + 2)
            var got = host_result.unsafe_ptr()[0]
            if got != expected_sum:
                print("cuda_graph_probe: MISMATCH at step", step, ": got", got,
                      "expected", expected_sum)
                all_ok = False

        # ── slot-isolation check: acc[s] must hold exactly (s+2), untouched neighbours ──
        ctx.enqueue_copy(host_acc, acc)
        ctx.synchronize()
        for s in range(SLOTS):
            var want = Float32(s + 2)
            var got = host_acc.unsafe_ptr()[s]
            if got != want:
                print("cuda_graph_probe: SLOT MISMATCH at", s, ": got", got, "expected", want)
                all_ok = False

        if all_ok:
            print("PROBE PASS — DeviceGraph capture/replay + state-buffer indirection verified")
        else:
            print("PROBE FAIL")
