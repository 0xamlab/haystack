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

The tiling, and the measurement that chose it
-----------------------------------------------
Each threadgroup computes a `BM x BN` block of C, walking K in `BK`-wide steps. Within a group each
THREAD owns a `TM x TN` register tile rather than a single output — that is the optimization. With one
output per thread the inner loop performs two shared-memory loads per multiply-add and the kernel is
bandwidth-bound; a register tile reuses each loaded value TM (or TN) times.

Measured on an M4 Max, hot, at a 2048-cube: the one-output-per-thread version reached 268 GFLOP/s and
this one reaches **2018 GFLOP/s**, a 7.5x improvement from the same arithmetic in a different order.

The specific tile sizes came from measurement and CONTRADICT our own cost model — see the constants
below, where the predicted and measured orderings are tabulated. This is why they are constants with a
table attached rather than numbers someone rounded to.

Public API:
  gemm_metal_available()                                     -> Bool
  gemm_metal_flat(a, b, m, n, k)                             -> MetalGemmResult
  gemm_metal_agreement(a, b, m, n, k)                        -> MetalGemmAgreement
"""

from std.origin import MutAnyOrigin  # Mojo 1.0.0: origins left std.builtin.type_aliases
from std.gpu import block_dim, block_idx, thread_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.host import DeviceContext
from max.gpu.memory import AddressSpace
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

comptime BM: Int = 32
comptime BN: Int = 32
comptime BK: Int = 16
comptime TM: Int = 2
comptime TN: Int = 2
comptime NTHREADS: Int = (BM // TM) * (BN // TN)
"""The threadgroup tile (BM x BN), the K step (BK), and how many outputs ONE THREAD owns (TM x TN).

Each thread computing several outputs is the whole optimization. With one output per thread the inner
loop does two shared-memory loads per multiply-add and the kernel is bandwidth-bound long before it is
compute-bound; holding a TM x TN block of accumulators in registers reuses each loaded value TM (or
TN) times instead of once.

THESE NUMBERS WERE MEASURED, AND THEY CONTRADICT OUR OWN COST MODEL. Scoring candidates through the
frozen `gpu_kernels` roofline — arithmetic intensity, occupancy, register pressure — ranks 128x128
with 8x8 per thread BEST and this 32x32 with 2x2 WORST. Measured hot at a 2048-cube, the order is
reversed:

| config | predicted score | measured hot GFLOP/s |
|---|---|---|
| 32x32, 2x2 | 0.55 (last) | **2018** |
| 64x64, 4x4 | 1.09 | 706 |
| 64x128, 4x8 | 1.46 | 855 |
| 128x128, 8x8 | 2.19 (first) | 620 |

The model ranks by arithmetic intensity, which rewards big tiles, and its occupancy term is constant
across these because they all use 256 threads. What it does not capture is that a big tile means FEWER
threadgroups, and this GPU hides latency by having many small groups in flight rather than few large
ones. `gpu_kernels` was written as a roofline for a machine with a handful of large SMs; Apple silicon
is not that machine.

Recorded rather than corrected. The frozen kernel keeps its behaviour and its callers, and this
package uses the measurement — but a reader who reaches for `roofline_performance` to pick a tile size
on Apple silicon should know it points the wrong way."""

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


def gemm_metal_available() -> Bool:
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


def _tiled_gemm_kernel(
    c_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    a_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    b_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    # Mojo 1.0.0: kernel parameters must be DevicePassable, which the adaptive
    # Int/UInt aliases no longer are — fixed-width only. Widened back to Int
    # once at the top of the body, where all the arithmetic lives.
    m_i32: Int32,
    n_i32: Int32,
    k_i32: Int32,
):
    """A `BM x BN` block of `C = A @ B`, with each thread owning a `TM x TN` register tile.

    Private device function; only the gated launch below may call it.

    Three things here are load-bearing and each has a failure mode worth naming.

    THE SECOND BARRIER. Without it a fast thread overwrites the shared tile for step k+1 while a slow
    one still reads it for step k. The answer comes out almost right, and worse under load — the
    hardest possible failure to debug.

    ZERO-PADDED LOADS RATHER THAN SKIPPED ONES. Out-of-range lanes store 0.0 instead of `continue`-ing.
    Every thread must reach both barriers; an early exit on a partial tile hangs the group.

    THE REGISTER TILE. `acc` lives in per-thread storage, not shared memory. That is what turns two
    shared loads per multiply-add into two loads per TM x TN multiply-adds.
    """
    var m = Int(m_i32)
    var n = Int(n_i32)
    var k = Int(k_i32)
    var a_tile = stack_allocation[
        BM * BK, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var b_tile = stack_allocation[
        BK * BN, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var acc = stack_allocation[TM * TN, DType.float32]()
    var reg_a = stack_allocation[TM, DType.float32]()
    var reg_b = stack_allocation[TN, DType.float32]()

    for i in range(TM * TN):
        acc[i] = 0.0

    var ty = Int(thread_idx.y)
    var tx = Int(thread_idx.x)
    var tid = ty * (BN // TN) + tx
    var block_row = Int(block_idx.y) * BM
    var block_col = Int(block_idx.x) * BN

    var n_steps = (k + BK - 1) // BK
    for step in range(n_steps):
        # Cooperative load. Each thread fetches several elements so the whole group shares one tile.
        for s in range(BM * BK // NTHREADS):
            var idx = tid + s * NTHREADS
            var ar = idx // BK
            var ac = idx % BK
            var gr = block_row + ar
            var gc = step * BK + ac
            a_tile[idx] = a_ptr[gr * k + gc] if (gr < m and gc < k) else Float32(0.0)
        for s in range(BK * BN // NTHREADS):
            var idx = tid + s * NTHREADS
            var br = idx // BN
            var bc = idx % BN
            var gr = step * BK + br
            var gc = block_col + bc
            b_tile[idx] = b_ptr[gr * n + gc] if (gr < k and gc < n) else Float32(0.0)

        barrier()

        for kk in range(BK):
            for i in range(TM):
                reg_a[i] = a_tile[(ty * TM + i) * BK + kk]
            for j in range(TN):
                reg_b[j] = b_tile[kk * BN + tx * TN + j]
            for i in range(TM):
                for j in range(TN):
                    acc[i * TN + j] += reg_a[i] * reg_b[j]

        barrier()

    for i in range(TM):
        for j in range(TN):
            var r = block_row + ty * TM + i
            var c = block_col + tx * TN + j
            if r < m and c < n:
                c_ptr[r * n + c] = acc[i * TN + j]


def gemm_metal_flat(
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


def _run_metal_gemm(
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

    var grid_x = (n + BN - 1) // BN
    var grid_y = (m + BM - 1) // BM
    ctx.enqueue_function[_tiled_gemm_kernel](
        c_buf.unsafe_ptr(),
        a_buf.unsafe_ptr(),
        b_buf.unsafe_ptr(),
        Int32(m),
        Int32(n),
        Int32(k),
        grid_dim=(grid_x, grid_y),
        block_dim=(BN // TN, BM // TM),
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


def gemm_metal_agreement(
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
