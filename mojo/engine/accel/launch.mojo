"""
accel.launch — the GPU kernels and the ONE place that knows how to launch one. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: metal
surfaces: none
golden_vectors: mojo/tests/libs/test_accel_launch.mojo
benchmark: benchmarks/mojo_benchmarks/bench_accel.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

`surfaces: none` is the declaration that matters here, and it is not a placeholder: this module is
deliberately unreachable from `library_execute` and `batch_execute`. `stateful: true` because a
launch opens a device context and owns buffers for the duration of the call, unlike every CPU kernel
in this plane. `backend: metal` rather than `mojo` for the same reason — the code that runs is a
compiled shader, not the host binary.

NOT a contract module. Every entry point here is private on purpose — read the next section before
adding anything.

THE RULE: no public function in this file, ever
--------------------------------------------------
Shader codegen is triggered by a statically REACHABLE launch site, at compile time. Verified on a
host with no Metal shader compiler: a caller that reaches a launch fails to build with
`Metal Compiler failed to compile metallib`, while a caller that imports only CPU functions from this
same module builds fine.

The generated runtime dispatch imports and calls every PUBLIC function of every contract module. So a
public launch function here would put a launch site in the dispatch's call graph, and every build host
— including Linux CI, which has no Metal compiler and no GPU — would start requiring one.

Leading underscores keep these out of the inventory, out of the contract and out of the dispatch.
That is a one-character defence against a whole-CI failure, so `test_accel_launch.mojo` asserts that
this file exports nothing public.

Reaching these from outside
-----------------------------
Deliberately unfinished in this change. The GPU path will be driven by a resident handle and a
`main.mojo` message type, following the `dataset_open` / `stream_next` precedent already in the tree —
that is a separate change with its own tests, and doing it here would mean shipping a message type
before the kernels it drives are worth calling.

Until then these are reachable from a local driver (a benchmark, a test) that opts into needing a
shader compiler. `benchmarks/mojo_benchmarks/bench_accel.mojo` is that driver, and it is the only
thing in the tree that requires `DEVELOPER_DIR` to be set.

The launch spelling, which cost six attempts to find
------------------------------------------------------
On this pinned nightly the kernel is passed TWICE as compile-time parameters, and the dimensions are
keyword-only:

    ctx.enqueue_function[kernel, kernel](args..., grid_dim=..., block_dim=...)

`enqueue_function[kernel]` with one parameter fails `signature_func` inference. A pointer argument
needs an explicit origin — `UnsafePointer[Float32, origin=MutAnyOrigin]`, with `MutAnyOrigin` from
`std.builtin.type_aliases`, NOT `MutableAnyOrigin`. `DeviceContext()` raises. All four of those are
one-line mistakes that produce long error messages, which is why the spelling lives in exactly one
file.
"""

from std.builtin.type_aliases import MutAnyOrigin
from std.gpu import block_dim, block_idx, thread_idx
from std.gpu.host import DeviceContext
from std.sys import has_accelerator

comptime _THREADS_PER_GROUP: Int = 256
"""Threads per threadgroup. 256 is the portable default: a multiple of both the 32-wide execution
width that NVIDIA uses and the 32-wide SIMD group Apple uses, and small enough not to exhaust
registers on either."""


fn _saxpy_kernel(
    out_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    x_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    alpha: Float32,
    n: Int,
):
    """`out[i] += alpha * x[i]`, one element per thread.

    The bounds check is not optional. The grid is rounded UP to whole threadgroups, so the last group
    is nearly always partly out of range — without the guard those threads write past the buffer, and
    on a GPU that is silent corruption rather than the clean abort a CPU bounds check would give.
    """
    var i = block_idx.x * block_dim.x + thread_idx.x
    if i < n:
        out_ptr[i] = out_ptr[i] + alpha * x_ptr[i]


fn _accel_saxpy(mut out_host: List[Float32], x_host: List[Float32], alpha: Float32) raises -> Int:
    """Run `out += alpha * x` on the accelerator. Returns the element count, or a negative status.

    Private: see THE RULE at the top of this file. Making this public would put a launch site in the
    generated dispatch and break every build host without a shader compiler.

    This is a deliberately trivial kernel. It exists to prove the launch seam end to end — buffer
    creation, host-to-device copy, launch, synchronize, device-to-host copy — with arithmetic simple
    enough that a wrong answer can only mean the seam is wrong. The real kernels follow once the seam
    is proven; a fused attention kernel written before this worked would have had two possible
    explanations for every failure.
    """
    if not has_accelerator():
        return -1
    var n = len(out_host)
    if n == 0 or len(x_host) < n:
        return -2

    var ctx = DeviceContext()
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n)
    var x_buf = ctx.enqueue_create_buffer[DType.float32](n)

    with out_buf.map_to_host() as host:
        for i in range(n):
            host[i] = out_host[i]
    with x_buf.map_to_host() as host:
        for i in range(n):
            host[i] = x_host[i]

    # Round the grid UP so every element is covered; the kernel's bounds check handles the overhang.
    var groups = (n + _THREADS_PER_GROUP - 1) // _THREADS_PER_GROUP
    ctx.enqueue_function[_saxpy_kernel, _saxpy_kernel](
        out_buf.unsafe_ptr(),
        x_buf.unsafe_ptr(),
        alpha,
        n,
        grid_dim=groups,
        block_dim=_THREADS_PER_GROUP,
    )
    ctx.synchronize()

    with out_buf.map_to_host() as host:
        for i in range(n):
            out_host[i] = host[i]
    return n


fn _accel_device_name() raises -> String:
    """The accelerator's full name, for a local driver that has already opened the device.

    Private, and separate from `accel.device.accel_device_name_len` on purpose: that one is a
    contract function usable anywhere and returns only a length, because a device name identifies the
    host. This one is for a benchmark printing its own configuration.
    """
    if not has_accelerator():
        return String("none")
    var ctx = DeviceContext()
    return ctx.name()


fn _accel_launch_roundtrip_ok() raises -> Bool:
    """Launch a known kernel and check the arithmetic. The proof that the seam works.

    `out = [0, 1, 2, ...]`, `x = [1, 1, 1, ...]`, `alpha = 2` gives `out[i] == i + 2`. Chosen so that
    an off-by-one in the index, a wrong grid size and a skipped copy each produce a different wrong
    answer rather than all producing zero.
    """
    var n = 1024
    var out_host = List[Float32](capacity=n)
    var x_host = List[Float32](capacity=n)
    for i in range(n):
        out_host.append(Float32(i))
        x_host.append(Float32(1.0))

    var count = _accel_saxpy(out_host, x_host, Float32(2.0))
    if count != n:
        return False
    for i in range(n):
        if out_host[i] != Float32(i) + Float32(2.0):
            return False
    return True
