"""
llmk.gemv_fast — a parallel matrix-vector multiply for exactly the "transposed operand" decode shape
`gemm.blocked.gemv_flat` computes on its single-threaded scalar path, by that kernel's OWN documented
design. Zero Python. Additive; does not modify `gemm/`.

Why this exists, named precisely
------------------------------------
`benchmarks/llm_smoke/REALRACE_RESULTS.md` (the RealRace phase) traced Algenta's decode throughput
loss to one specific, frozen-kernel-documented design choice: `qwen3_generate.mojo`'s per-layer
Q/K/V/O/gate/up/down projections all call `gemm.blocked.gemv_flat(..., trans=True)`, and that
module's own docstring says outright — *"Transposed operands take the scalar path, on purpose ...
trans_a/trans_b route to a straightforward indexed triple loop ... A caller who cares about speed
transposes once up front instead."* No `parallelize` call anywhere in that branch, so 7 of every 8
decode-step matmuls run on one core while the other 15 sit idle. Only the 8th call — the untransposed
`lm_head` projection — hits the parallelized `gemv_band` branch and fans out.

`gemm/blocked.mojo` is frozen and stays exactly as it is (see `docs/mojo/new-kernel-package-rules.md`
rule 3 and the freeze-verification command). This file adds a PARALLEL PATH for the same shape in a
new, additive namespace instead — the fix the RealRace report itself named as the non-invasive option.

The shape, and why it parallelizes differently than `gemv_band`
--------------------------------------------------------------------
`gemv_flat(a, x, m, n, trans=True)` computes `y = A^T @ x` for `A` stored `[m, n]` row-major (m
input/in-features rows, n output/out-features columns) — exactly `qwen3_generate.mojo`'s pre-transposed
`[in, out]` weight layout (see that file's own docstring on `*_T` weights). For fixed output column
`j`, `y[j] = sum_i A[i, j] * x[i]` is a strided reduction (stride `n`), which is why the scalar branch
instead loops `i` outer and `j` inner: for each input row `i` it broadcasts `x[i]` and walks `A`'s row
contiguously, scatter-accumulating into every `y[j]`. That IS the SIMD-friendly direction, on the wrong
axis for a naive row-per-worker split — every `i` touches every `j`, so partitioning by `i` the way
`gemv_band` partitions its OUTPUT rows would need a lock or a per-thread partial-sum reduction.

The output columns, not the input rows, are what is safe to hand out disjointly: this file partitions
`y`'s `n` columns into contiguous per-worker BANDS via `std.algorithm.parallelize`, the exact same
primitive and disjoint-band idiom `gemv_flat`'s own untransposed `gemv_band` branch already uses for
its output rows (mirrored, not reinvented). Each worker then runs the SAME loop order the scalar
branch does — `i` outer, `j` inner, contiguous — but confined to its own column band, so both the
memory access (contiguous slice of `A`'s row) and the parallel split (disjoint slice of `y`, no
cross-thread writes, no lock) are valid at once.

Below the fan-out threshold, or above the same work budget `gemv_flat` itself enforces, this delegates
to `gemv_flat` directly rather than duplicating its scalar loop (rule 3: call the frozen kernel, do not
reimplement it) — this file adds a parallel path, not a second scalar implementation.

Float64 only, on purpose
---------------------------
Same wire type as every other frozen kernel and as `gemv_flat` itself. `fp16`/`bf16` is a separate,
larger undertaking with its own numeric-tolerance implications (see `gemm.blocked`'s own docstring on
`simd_width_of[float64]() == 2` on this host) — this file's job is isolating the scalar-vs-parallel
factor on its own, so a later precision change is measured against an already-improved baseline
instead of conflating two fixes into one number.

Public API:
  gemv_transposed_parallel_flat(a, x, m, n) -> ParallelGemvResult

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_llmk_gemv_fast.mojo
benchmark: benchmarks/llm_smoke/qwen3_generate.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability
"""

from std.algorithm import parallelize
from std.sys.info import num_physical_cores
from std.sys.info import simd_width_of
from gemm.blocked import gemv_flat
from gemm.contract import GEMM_MAX_FLOP_CELLS, GEMM_OK, gemm_work_fits
from llmk.contract import LLMK_ERR_DIM_TOO_LARGE, LLMK_OK, llmk_gemv_dims_check

comptime W: Int = simd_width_of[DType.float64]()
"""Same SIMD width constant `gemm.blocked` measures on this host: 2 lanes on 128-bit NEON."""

comptime PARALLEL_MIN_CELLS: Int = 1 << 16
"""Same threshold and reasoning as `gemm.blocked.PARALLEL_MIN_CELLS`: below ~65k output cells the
`parallelize` fan-out/join costs more than the work it would save."""


@fieldwise_init
struct ParallelGemvResult(Copyable, Movable):
    """`y = A^T @ x`, its length, and a status code."""

    var y: List[Float64]
    var n: Int
    var status: Int


fn gemv_transposed_parallel_flat(a: List[Float64], x: List[Float64], m: Int, n: Int) -> ParallelGemvResult:
    """`y = A^T @ x` for `A` stored `[m, n]` row-major, `x` length `m`, `y` length `n` — the exact
    shape `gemm.blocked.gemv_flat(..., trans=True)` computes on its documented scalar path. See the
    module docstring for why the output columns, not the input rows, are the axis this partitions.

    @capability gemv_transposed_parallel_flat
    complexity: O(m*n)
    counts:
    - m * n == len(a) [kernel_validated]
    - m == len(x) [kernel_validated]
    @endcapability
    """
    var empty = List[Float64]()
    var shape = llmk_gemv_dims_check(m, n, len(a), len(x))
    if shape != LLMK_OK:
        return ParallelGemvResult(empty^, 0, shape)
    # Same work budget `gemv_flat` itself enforces (`gemm_work_fits(m, n, 1, GEMM_MAX_FLOP_CELLS)`),
    # called rather than re-derived (rule 3).
    if not gemm_work_fits(m, n, 1, GEMM_MAX_FLOP_CELLS):
        return ParallelGemvResult(empty^, 0, LLMK_ERR_DIM_TOO_LARGE)

    var cells = m * n
    var nw = num_physical_cores()
    if nw < 1:
        nw = 1
    if cells < PARALLEL_MIN_CELLS or n < nw:
        # Below the fan-out threshold, or fewer output columns than workers to hand a disjoint band
        # to: delegate to the frozen scalar kernel directly (rule 3) rather than duplicating its loop.
        var r = gemv_flat(a, x, m, n, True)
        if r.status != GEMM_OK:
            return ParallelGemvResult(empty^, 0, LLMK_ERR_DIM_TOO_LARGE)
        return ParallelGemvResult(r.c.copy(), r.rows, LLMK_OK)

    var y = List[Float64](capacity=n)
    for _ in range(n):
        y.append(0.0)

    # Raw pointers hoisted once, same reasoning as `gemm.blocked.sgemm_flat`: nothing below appends,
    # every index was validated by `llmk_gemv_dims_check` above, and the inner loop needs a genuine
    # vector load/store rather than a bounds-checked scalar access per element.
    var ap = a.unsafe_ptr()
    var xp = x.unsafe_ptr()
    var yp = y.unsafe_ptr()
    var pm = m
    var pn = n
    var pnw = nw

    @parameter
    fn col_band(tid: Int) capturing:
        var cols_each = pn // pnw
        var lo = tid * cols_each
        var hi = lo + cols_each if tid < pnw - 1 else pn
        var width = hi - lo
        for i in range(pm):
            var xi = xp[i]
            if xi == 0.0:
                continue
            var row = i * pn
            var j = 0
            while j + W <= width:
                var av = (ap + row + lo + j).load[width=W]()
                var yv = (yp + lo + j).load[width=W]()
                (yp + lo + j).store(yv + av * SIMD[DType.float64, W](xi))
                j += W
            while j < width:
                yp[lo + j] += ap[row + lo + j] * xi
                j += 1

    parallelize[col_band](pnw)

    return ParallelGemvResult(y^, n, LLMK_OK)
