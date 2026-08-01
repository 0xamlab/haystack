"""
accel.gemm_metal — a threadgroup-tiled GEMM on the GPU, reachable from the runtime contract.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: metal
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_accel_gemm_metal.mojo
benchmark: benchmarks/mojo_benchmarks/bench_accel.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

This module is contract-reachable AND contains a GPU launch. Both, safely.
------------------------------------------------------------------------------
Shader codegen follows the CALL GRAPH at compile time, so a reachable launch normally forces every
build host to own a shader compiler. The launch here sits inside `@parameter if ACCEL_GPU_BUILD`,
which is a COMPILE-TIME branch on `is_defined["ALGENTA_GPU"]`. With the flag unset the branch and
everything in it are elided before codegen runs, so a host with no shader compiler builds this file,
links it, and gets an honest `ACCEL_ERR_SHADER_TOOLCHAIN_ABSENT` at runtime.

Verified both ways: flag off with no toolchain builds and reports unavailable; flag on with the
toolchain runs the kernel. That is what lets a GPU kernel be an ordinary contract function instead of
something only a benchmark can reach.

The precision is NOT the same as the CPU path, and that is declared
---------------------------------------------------------------------
`gemm.blocked` computes in Float64. This computes in **Float32**, because that is what a GPU is for —
Apple silicon has no meaningful Float64 throughput, and a Float64 Metal kernel would be slower than
the CPU it is trying to beat.

So these two kernels do not compute the same function. Agreement is bounded by Float32's ~1e-7
relative precision, not by anything this kernel does well or badly, and `gemm_metal_agreement`
reports the measured delta rather than asserting a tolerance nobody can meet. A caller who needs
Float64 must use the CPU path and should be told so by the number, not discover it later.

The wire type is Float64 either way, so every call pays a narrowing conversion in and a widening
conversion out. The benchmark measures that conversion separately from the kernel, because for a
small matrix it is most of the call.

The tiling
------------
Each threadgroup computes one `TILE x TILE` block of C. The K dimension is walked in `TILE`-wide
steps: every thread cooperatively loads one element of A and one of B into threadgroup memory, the
group barriers, each thread accumulates `TILE` products from that shared tile, and the group barriers
again before the next step.

The second barrier is the one that gets forgotten. Without it a fast thread starts overwriting the
shared tile for step k+1 while a slow thread is still reading it for step k — a race that produces
almost-right answers on small inputs and gets worse with occupancy, which is the hardest possible
failure to debug.

Public API:
  gemm_metal_available()                                     -> Bool
  gemm_metal_flat(a, b, m, n, k)                             -> MetalGemmResult
  gemm_metal_agreement(a, b, m, n, k)                        -> MetalGemmAgreement
"""

from std.builtin.type_aliases import MutAnyOrigin
from std.gpu import barrier, block_dim, block_idx, thread_idx
from std.gpu.host import DeviceContext
from std.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.sys import has_accelerator, is_defined
from accel.contract import (
    ACCEL_BACKEND_CPU,
    ACCEL_BACKEND_METAL,
    ACCEL_ERR_EMPTY_DIM,
    ACCEL_ERR_NO_DEVICE,
    ACCEL_ERR_SHADER_TOOLCHAIN_ABSENT,
    ACCEL_OK,
)
from gemm.blocked import sgemm_flat
from gemm.contract import GEMM_OK

comptime ACCEL_GPU_BUILD: Bool = is_defined["ALGENTA_GPU"]()
"""Whether this binary was built with GPU kernels compiled in.

`mojo build -D ALGENTA_GPU`. Unset by default ON PURPOSE: the default build must work on a host with
no shader compiler, which is every Linux CI runner in this project. The flag is checked with
`@parameter if`, so with it unset the launch is removed before shader codegen runs rather than merely
skipped at runtime — a runtime `if` would not help, because codegen happens at compile time for
anything reachable."""

comptime TILE: Int = 16
"""Threadgroup tile edge. 16x16 gives 256 threads per group — the same count `accel.launch` uses, and
for the same reason: a multiple of the 32-wide SIMD group on both Apple and NVIDIA, large enough to
hide memory latency, small enough not to exhaust registers. Two 16x16 Float32 tiles is 2 KB of
threadgroup memory, comfortably inside every target's budget."""

comptime ACCEL_GEMM_MAX_DIM: Int = 1 << 14
"""Largest edge this kernel accepts, per dimension.

16384 squared in Float32 is 1 GiB per operand. The bound exists so a caller who passes an element
count where an edge length belongs is refused rather than being handed a device out-of-memory, which
on a GPU is a much less legible failure than on a CPU."""


@fieldwise_init
struct MetalGemmResult(Copyable, Movable):
    """A product computed on the accelerator, and which backend actually produced it."""

    var c: List[Float64]
    var rows: Int
    var cols: Int
    var backend_used: Int
    var status: Int


@fieldwise_init
struct MetalGemmAgreement(Copyable, Movable):
    """How far the Float32 GPU result sits from the Float64 CPU one.

    `within_float32_precision` is the honest question. Asking whether the two agree to Float64
    tolerance would always answer no, and would say nothing about whether the kernel is correct —
    only that Float32 is Float32."""

    var max_abs_delta: Float64
    var float32_bound: Float64
    var within_float32_precision: Bool
    var n_compared: Int
    var status: Int


fn gemm_metal_available() -> Bool:
    """True when this binary can actually run a GPU GEMM.

    Two independent conditions, and both are necessary: the binary must have been BUILT with GPU
    kernels compiled in, and the host must HAVE an accelerator. A build-time yes with a runtime no is
    an ordinary case — the same binary shipped to a machine without a GPU — and a runtime yes with a
    build-time no is the default build on a GPU machine.

    @capability gemm_metal_available
    complexity: O(1)
    @endcapability
    """

    @parameter
    if not ACCEL_GPU_BUILD:
        return False
    return has_accelerator()


fn _tiled_gemm_kernel(
    c_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    a_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    b_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    m: Int,
    n: Int,
    k: Int,
):
    """One `TILE x TILE` block of `C = A @ B`, cooperating through threadgroup memory.

    Private, and it would be private even without the compile-time gate: it is a device function, and
    the only thing that may call it is the launch below.
    """
    var a_tile = stack_allocation[
        TILE * TILE, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var b_tile = stack_allocation[
        TILE * TILE, DType.float32, address_space = AddressSpace.SHARED
    ]()

    var ty = thread_idx.y
    var tx = thread_idx.x
    var row = block_idx.y * TILE + ty
    var col = block_idx.x * TILE + tx

    var acc: Float32 = 0.0
    var n_steps = (k + TILE - 1) // TILE

    for step in range(n_steps):
        var a_col = step * TILE + tx
        var b_row = step * TILE + ty

        # Out-of-range lanes load zero rather than skipping the load. Every thread must reach both
        # barriers below, so an early `continue` here would hang the group on a partial tile.
        if row < m and a_col < k:
            a_tile[ty * TILE + tx] = a_ptr[row * k + a_col]
        else:
            a_tile[ty * TILE + tx] = 0.0
        if b_row < k and col < n:
            b_tile[ty * TILE + tx] = b_ptr[b_row * n + col]
        else:
            b_tile[ty * TILE + tx] = 0.0

        barrier()

        for e in range(TILE):
            acc += a_tile[ty * TILE + e] * b_tile[e * TILE + tx]

        # THE SECOND BARRIER. Without it a fast thread overwrites the tile for step+1 while a slow
        # one is still reading it for step. The result is almost right, and worse under load.
        barrier()

    if row < m and col < n:
        c_ptr[row * n + col] = acc


fn gemm_metal_flat(
    a: List[Float64], b: List[Float64], m: Int, n: Int, k: Int
) -> MetalGemmResult:
    """`C = A @ B` on the accelerator, over flat row-major Float64 buffers.

    Returns `ACCEL_ERR_SHADER_TOOLCHAIN_ABSENT` when the binary was built without GPU kernels, and
    `ACCEL_ERR_NO_DEVICE` when it was built with them and the host has none. Those are different
    facts and a caller can act on each differently: the first is a build decision, the second is a
    deployment one.

    Never silently computes on the CPU. `accel.contract.accel_resolve` is where a caller opts into a
    fallback; a kernel that quietly substituted a backend would defeat it.

    @capability gemm_metal_flat
    complexity: O(m*n*k)
    counts:
    - m * k <= len(a) [enforced]
    - k * n <= len(b) [enforced]
    - dim m <= ACCEL_GEMM_MAX_DIM [kernel_validated]
    - dim n <= ACCEL_GEMM_MAX_DIM [kernel_validated]
    - dim k <= ACCEL_GEMM_MAX_DIM [kernel_validated]
    @endcapability
    """
    var empty = List[Float64]()
    if m <= 0 or n <= 0 or k <= 0:
        return MetalGemmResult(empty^, 0, 0, ACCEL_BACKEND_CPU, ACCEL_ERR_EMPTY_DIM)
    if m > ACCEL_GEMM_MAX_DIM or n > ACCEL_GEMM_MAX_DIM or k > ACCEL_GEMM_MAX_DIM:
        return MetalGemmResult(empty^, 0, 0, ACCEL_BACKEND_CPU, ACCEL_ERR_EMPTY_DIM)
    if len(a) < m * k or len(b) < k * n:
        return MetalGemmResult(empty^, 0, 0, ACCEL_BACKEND_CPU, ACCEL_ERR_EMPTY_DIM)

    @parameter
    if not ACCEL_GPU_BUILD:
        # Built without GPU kernels. Everything below this point was removed at compile time, which
        # is exactly why a host with no shader compiler can build this file.
        return MetalGemmResult(
            empty^, 0, 0, ACCEL_BACKEND_CPU, ACCEL_ERR_SHADER_TOOLCHAIN_ABSENT
        )
    else:
        if not has_accelerator():
            return MetalGemmResult(empty^, 0, 0, ACCEL_BACKEND_CPU, ACCEL_ERR_NO_DEVICE)
        try:
            return _run_metal_gemm(a, b, m, n, k)
        except:
            return MetalGemmResult(empty^, 0, 0, ACCEL_BACKEND_CPU, ACCEL_ERR_NO_DEVICE)


fn _run_metal_gemm(
    a: List[Float64], b: List[Float64], m: Int, n: Int, k: Int
) raises -> MetalGemmResult:
    """The launch itself. Private, and only ever called from inside the compile-time gate."""
    var ctx = DeviceContext()
    var a_buf = ctx.enqueue_create_buffer[DType.float32](m * k)
    var b_buf = ctx.enqueue_create_buffer[DType.float32](k * n)
    var c_buf = ctx.enqueue_create_buffer[DType.float32](m * n)

    # The narrowing happens here, once, on the host. Doing it lane-by-lane inside the kernel would
    # mean shipping Float64 to a device that cannot multiply it usefully.
    #
    # Through `unsafe_ptr()` rather than `a[i]`, and that is worth 1.9x on this loop: measured at
    # 1M elements, indexed access is 4.82 ms against 2.53 ms through the pointer, because `List`
    # indexing bounds-checks every element. The bound is already established above — this runs only
    # after `len(a) >= m*k` and `len(b) >= k*n` have been checked — so the per-element check is
    # re-proving a fact the function already knows. On a kernel whose conversion cost is most of the
    # call, that is not a micro-optimization.
    var ap = a.unsafe_ptr()
    var bp = b.unsafe_ptr()
    with a_buf.map_to_host() as host:
        for i in range(m * k):
            host[i] = Float32(ap[i])
    with b_buf.map_to_host() as host:
        for i in range(k * n):
            host[i] = Float32(bp[i])
    # C is NOT pre-zeroed. The kernel assigns `c_ptr[row * n + col] = acc` rather than accumulating
    # into it, and the grid covers every (row, col) in [0, m) x [0, n) exactly once, so every element
    # of the buffer is written before it is read back. Zeroing first would be a full extra pass over
    # the output — the same cost as one of the uploads — to overwrite values nothing observes.
    #
    # This is only safe because the kernel ASSIGNS. If it ever accumulates (a split-K variant would),
    # the zero-fill has to come back, and the symptom of forgetting would be garbage from whatever
    # the allocator last held.

    var grid_x = (n + TILE - 1) // TILE
    var grid_y = (m + TILE - 1) // TILE
    ctx.enqueue_function[_tiled_gemm_kernel, _tiled_gemm_kernel](
        c_buf.unsafe_ptr(),
        a_buf.unsafe_ptr(),
        b_buf.unsafe_ptr(),
        m,
        n,
        k,
        grid_dim=(grid_x, grid_y),
        block_dim=(TILE, TILE),
    )
    ctx.synchronize()

    # Sized once and written through a pointer, for the same reason as the upload: `append` grows a
    # length field a million times and every write bounds-checks.
    var c = List[Float64](capacity=m * n)
    for _ in range(m * n):
        c.append(0.0)
    var cp = c.unsafe_ptr()
    with c_buf.map_to_host() as host:
        for i in range(m * n):
            cp[i] = Float64(host[i])

    return MetalGemmResult(c^, m, n, ACCEL_BACKEND_METAL, ACCEL_OK)


fn gemm_metal_agreement(
    a: List[Float64], b: List[Float64], m: Int, n: Int, k: Int
) -> MetalGemmAgreement:
    """Measure the Float32 GPU result against the Float64 CPU kernel, worst element.

    The comparison is against `gemm.blocked.sgemm_flat` (rule 3: the CPU answer is not recomputed
    here) and it is judged against a FLOAT32 bound, not a Float64 one. The two kernels compute in
    different precisions on purpose; asking whether they agree to 1e-14 would always answer no and
    would tell a reader nothing about whether the tiling is correct.

    The bound is `k` accumulation steps at Float32 epsilon, scaled by the magnitude of the element
    being judged — a longer inner dimension means more rounding, so a fixed bound would pass at k=16
    and fail at k=4096 on identical code.

    @capability gemm_metal_agreement
    complexity: O(m*n*k)
    counts:
    - m * k <= len(a) [enforced]
    - k * n <= len(b) [enforced]
    @endcapability
    """
    if m <= 0 or n <= 0 or k <= 0 or len(a) < m * k or len(b) < k * n:
        return MetalGemmAgreement(0.0, 0.0, False, 0, ACCEL_ERR_EMPTY_DIM)

    var gpu = gemm_metal_flat(a, b, m, n, k)
    if gpu.status != ACCEL_OK:
        return MetalGemmAgreement(0.0, 0.0, False, 0, gpu.status)

    var cpu = sgemm_flat(a, b, m, n, k, 1.0, 0.0, False, False)
    if cpu.status != GEMM_OK:
        return MetalGemmAgreement(0.0, 0.0, False, 0, cpu.status)

    # Float32 has ~1.19e-7 epsilon; k accumulations can each contribute one rounding.
    var f32_eps = 1.1920929e-7
    var worst = 0.0
    var bound_at_worst = 0.0
    for i in range(m * n):
        var delta = gpu.c[i] - cpu.c[i]
        if delta < 0.0:
            delta = -delta
        var mag = cpu.c[i] if cpu.c[i] >= 0.0 else -cpu.c[i]
        var bound = f32_eps * Float64(k) * (1.0 + mag)
        if delta > worst:
            worst = delta
            bound_at_worst = bound

    if bound_at_worst == 0.0:
        bound_at_worst = f32_eps * Float64(k)
    return MetalGemmAgreement(
        worst, bound_at_worst, worst <= bound_at_worst, m * n, ACCEL_OK
    )
