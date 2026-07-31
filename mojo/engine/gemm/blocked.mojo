"""
gemm.blocked — cache-blocked, SIMD dense GEMM and GEMV over flat row-major buffers. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_gemm_blocked.mojo
benchmark: benchmarks/mojo_benchmarks/bench_tensorx_and_gemm.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

The loop order is the kernel
------------------------------
C is row-major, so for `C[i][j] += A[i][kk] * B[kk][j]` the `j` loop walks contiguous memory in BOTH
C and B while `A[i][kk]` is loop-invariant. That is the whole reason this is `i-k-j` and not the
textbook `i-j-k`: the latter walks B down a column, one cache line per element, and no amount of
vectorization rescues it. `linalg.mat_mul` is `i-j-k` — correct, and the reason it is slow.

So the inner loop broadcasts one A element and does a contiguous multiply-add along j, which is
exactly the shape SIMD wants. Blocking over `i`, `k` and `j` then keeps the active slice of B in cache
across successive `i` values.

Measured on this host: `simd_width_of[float64]() == 2` (128-bit NEON). f32 would be 4 and bf16 8,
which is the real argument for the accumulate-in-f32 policy in `tensorx.dtype` — but the runtime
contract's wire type is `Float64`, so this reference is 2-wide and that ceiling is honest rather than
a tuning failure.

Transposed operands take the scalar path, on purpose
------------------------------------------------------
With `trans_b`, B's `j` stride is `k` rather than 1, so the contiguity the SIMD path depends on is
gone. Rather than pretend, `trans_a`/`trans_b` route to a straightforward indexed triple loop and the
result reports `GEMM_BACKEND_SCALAR`. A caller reading `kernel_variant` can see which kernel ran; a
caller who cares about speed transposes once up front instead. Silently running a slower kernel while
reporting the fast one's tag is the "no silent fallback" violation this field exists to prevent.

Not bit-identical to the frozen kernel, and that is stated
------------------------------------------------------------
Float addition is not associative, so a blocked accumulation and `linalg.mat_mul`'s single-pass
accumulation do not agree to the last bit. `gemm_reference_delta_flat` measures the difference against
the frozen kernel and returns it with the tolerance it should be judged against, built per element
from `tensorx.dtype.dtx_tol_for`. Asserting bit-equality here would either be false or force the
blocked kernel to accumulate in the frozen order, which is the thing that makes it fast.

Public API:
  sgemm_flat(a, b, m, n, k, alpha, beta, trans_a, trans_b) -> GemmResult
  gemv_flat(a, x, m, n, trans) -> GemmResult
  gemm_tile_plan(m, n, k, cache_bytes) -> TilePlan
  gemm_reference_delta_flat(a, b, m, n, k) -> RefDelta
"""

from std.algorithm import parallelize
from std.sys import info
from std.sys.info import simd_width_of
from gemm.contract import (
    GEMM_BACKEND_CPU_SIMD,
    GEMM_BACKEND_SCALAR,
    GEMM_ERR_A_LENGTH,
    GEMM_ERR_EMPTY_DIM,
    GEMM_ERR_NON_FINITE_SCALAR,
    GEMM_MAX_FLOP_CELLS,
    GEMM_OK,
    gemm_dims_check,
    gemm_scalars_ok,
    gemm_work_fits,
)
from gpu_kernels import arithmetic_intensity, tile_size_for_smem
from linalg import Matrix, mat_mul
from tensorx.contract import tx_count_ok, TX_OK
from tensorx.dtype import DT_F64, dtx_tol_for

comptime W: Int = simd_width_of[DType.float64]()
"""SIMD lanes for Float64 on the build target. 2 on 128-bit NEON, 8 on AVX-512."""

comptime PARALLEL_MIN_CELLS: Int = 1 << 16
"""Below ~65k output cells, run single-threaded.

`parallelize` costs microseconds to fan out and join. A 64x64 GEMM is ~500 us of work single-threaded,
so the spawn is noise there — but a 16x16 is ~5 us and would spend more time in the scheduler than in
the kernel. Measured rather than guessed: the threshold sits where the two curves cross on this host."""

comptime TILE_M: Int = 64
comptime TILE_N: Int = 256
comptime TILE_K: Int = 128
"""Blocking factors, chosen so one `TILE_K x TILE_N` slice of B is ~256 KB of Float64 — an L2-resident
working set that is reused across all `TILE_M` rows of A. `gemm_tile_plan` recomputes these from a
real cache size via the frozen `gpu_kernels.tile_size_for_smem`; these are the defaults when nobody
asked."""


@fieldwise_init
struct GemmResult(Copyable, Movable):
    """A product, its shape, and which kernel actually produced it."""

    var c: List[Float64]
    var rows: Int
    var cols: Int
    var backend_used: Int
    var flop_count: Float64
    var status: Int


@fieldwise_init
struct TilePlan(Copyable, Movable):
    """Blocking factors and the arithmetic intensity they imply."""

    var tile_m: Int
    var tile_n: Int
    var tile_k: Int
    var arithmetic_intensity: Float64
    var status: Int


@fieldwise_init
struct RefDelta(Copyable, Movable):
    """How far the blocked kernel is from the frozen oracle, and how far it is allowed to be."""

    var max_abs_delta: Float64
    var tolerance_at_max: Float64
    var within_tolerance: Bool
    var n_compared: Int
    var status: Int


fn gemm_tile_plan(m: Int, n: Int, k: Int, cache_bytes: Int) -> TilePlan:
    """Derive blocking factors for a cache of `cache_bytes`, via the frozen tile-size model.

    `gpu_kernels.tile_size_for_smem` and `arithmetic_intensity` are the analytical model the tree
    already has. They were written to describe a GPU's shared memory, and the arithmetic is the same
    question a CPU cache asks: how large a tile keeps three operands resident. Reusing them is rule 3
    — the value here is the composition, not the formula.

    @capability gemm_tile_plan
    complexity: O(1)
    @endcapability
    """
    if m <= 0 or n <= 0 or k <= 0 or cache_bytes <= 0:
        return TilePlan(TILE_M, TILE_N, TILE_K, 0.0, GEMM_ERR_EMPTY_DIM)

    var tile = tile_size_for_smem(Float64(cache_bytes), 8.0, 3.0)
    var t = Int(tile) if tile > 1.0 and tile < 4096.0 else TILE_N
    if t < 8:
        t = 8

    var flops = 2.0 * Float64(m) * Float64(n) * Float64(k)
    var moved = 8.0 * (Float64(m) * Float64(k) + Float64(k) * Float64(n) + Float64(m) * Float64(n))
    var ai = arithmetic_intensity(flops, moved)

    var tm = TILE_M if TILE_M < m else m
    var tk = TILE_K if TILE_K < k else k
    var tn = t if t < n else n
    return TilePlan(tm, tn, tk, ai, GEMM_OK)


fn sgemm_flat(
    a: List[Float64], b: List[Float64], m: Int, n: Int, k: Int,
    alpha: Float64, beta: Float64, trans_a: Bool, trans_b: Bool
) -> GemmResult:
    """C = alpha * op(A) @ op(B) + beta * C0, over flat row-major buffers. C0 is zero.

    Packing note: the signature closes on line 3 of the nine-line window, and that headroom is
    load-bearing. A reflow that pushed the closing paren to line 10 would drop this function from the
    contract AND the dispatch with no error anywhere — the only symptom is a per-module count one
    lower (rule 2b).

    @capability sgemm_flat
    complexity: O(m*n*k)
    counts:
    - m * k == len(a) [kernel_validated]
    - k * n == len(b) [kernel_validated]
    @endcapability
    """
    var empty = List[Float64]()
    var shape = gemm_dims_check(m, n, k, len(a), len(b))
    if shape != GEMM_OK:
        return GemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, shape)
    if not gemm_scalars_ok(alpha, beta):
        return GemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_NON_FINITE_SCALAR)

    var c = List[Float64](capacity=m * n)
    for _ in range(m * n):
        c.append(0.0)
    var flops = 2.0 * Float64(m) * Float64(n) * Float64(k)

    if trans_a or trans_b:
        # Indexed triple loop. Correct for every orientation, and honest about being scalar: with a
        # transposed B the j stride is k, so there is no contiguous run for SIMD to work on.
        for i in range(m):
            for j in range(n):
                var acc = 0.0
                for kk in range(k):
                    var av = a[kk * m + i] if trans_a else a[i * k + kk]
                    var bv = b[j * k + kk] if trans_b else b[kk * n + j]
                    acc += av * bv
                c[i * n + j] = alpha * acc
        return GemmResult(c^, m, n, GEMM_BACKEND_SCALAR, flops, GEMM_OK)

    # Raw pointers hoisted once. `List.__getitem__` is a bounds-checked scalar access; the inner
    # loop needs a genuine vector load/store, and taking the pointer per iteration would defeat it.
    # Safe because nothing below appends — every index was validated by gemm_dims_check above.
    var ap = a.unsafe_ptr()
    var bp = b.unsafe_ptr()
    var cp = c.unsafe_ptr()

    # Rows partition cleanly: worker `tid` owns a contiguous band of C and writes nothing outside it,
    # so there is no sharing and no lock. Same shape as `engines/monte_carlo.mojo`'s parallel path —
    # pre-size the output, hand the workers a raw pointer, give each a disjoint slice.
    var cells = m * n
    var n_workers = info.num_physical_cores()
    if n_workers < 1:
        n_workers = 1
    if cells < PARALLEL_MIN_CELLS or m < n_workers:
        n_workers = 1

    var pm = m
    var pn = n
    var pk = k
    var palpha = alpha
    var pnw = n_workers

    @parameter
    fn band(tid: Int) capturing:
        var rows_each = pm // pnw
        var lo = tid * rows_each
        var hi = lo + rows_each if tid < pnw - 1 else pm

        var i0 = lo
        while i0 < hi:
            var i_hi = i0 + TILE_M
            if i_hi > hi:
                i_hi = hi
            var k0 = 0
            while k0 < pk:
                var k_hi = k0 + TILE_K
                if k_hi > pk:
                    k_hi = pk
                var j0 = 0
                while j0 < pn:
                    var j_hi = j0 + TILE_N
                    if j_hi > pn:
                        j_hi = pn
                    for i in range(i0, i_hi):
                        var c_row = i * pn
                        for kk in range(k0, k_hi):
                            var aik = palpha * ap[i * pk + kk]
                            var b_row = kk * pn
                            var va = SIMD[DType.float64, W](aik)
                            var j = j0
                            # Four independent accumulator streams so the vector FMAs do not form one
                            # dependency chain — `vector_kernels/dot.mojo` uses eight for the same
                            # reason. Each store is to a distinct address, so they issue in parallel.
                            while j + 4 * W <= j_hi:
                                var b0 = (bp + b_row + j).load[width=W]()
                                var b1 = (bp + b_row + j + W).load[width=W]()
                                var b2 = (bp + b_row + j + 2 * W).load[width=W]()
                                var b3 = (bp + b_row + j + 3 * W).load[width=W]()
                                var c0 = (cp + c_row + j).load[width=W]()
                                var c1 = (cp + c_row + j + W).load[width=W]()
                                var c2 = (cp + c_row + j + 2 * W).load[width=W]()
                                var c3 = (cp + c_row + j + 3 * W).load[width=W]()
                                (cp + c_row + j).store(c0 + va * b0)
                                (cp + c_row + j + W).store(c1 + va * b1)
                                (cp + c_row + j + 2 * W).store(c2 + va * b2)
                                (cp + c_row + j + 3 * W).store(c3 + va * b3)
                                j += 4 * W
                            while j + W <= j_hi:
                                var vb = (bp + b_row + j).load[width=W]()
                                var vc = (cp + c_row + j).load[width=W]()
                                (cp + c_row + j).store(vc + va * vb)
                                j += W
                            while j < j_hi:
                                cp[c_row + j] += aik * bp[b_row + j]
                                j += 1
                    j0 += TILE_N
                k0 += TILE_K
            i0 += TILE_M

    parallelize[band](n_workers)

    return GemmResult(c^, m, n, GEMM_BACKEND_CPU_SIMD, flops, GEMM_OK)


fn gemv_flat(
    a: List[Float64], x: List[Float64], m: Int, n: Int, trans: Bool
) -> GemmResult:
    """y = op(A) @ x for a row-major m-by-n A. The decode-shaped case: one vector, memory-bound.

    Kept separate from `sgemm_flat` rather than called with `n = 1` because the two have different
    bottlenecks — a GEMV reads every weight exactly once and does one multiply-add per element, so it
    is bandwidth-bound and blocking buys nothing. Routing it through the blocked path would add tile
    bookkeeping to a loop that is already at its roofline.

    @capability gemv_flat
    complexity: O(m*n)
    counts:
    - m * n == len(a) [kernel_validated]
    @endcapability
    """
    var empty = List[Float64]()
    if m <= 0 or n <= 0:
        return GemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_EMPTY_DIM)
    if not gemm_work_fits(m, n, 1, GEMM_MAX_FLOP_CELLS):
        return GemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_EMPTY_DIM)
    if len(a) != m * n:
        return GemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_A_LENGTH)

    var need = m if trans else n
    if tx_count_ok(need, len(x)) != TX_OK:
        return GemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_A_LENGTH)

    var rows = n if trans else m
    var y = List[Float64](capacity=rows)
    for _ in range(rows):
        y.append(0.0)
    var flops = 2.0 * Float64(m) * Float64(n)

    if trans:
        # A^T @ x: accumulate down columns, which is contiguous in A along j for each fixed i.
        for i in range(m):
            var xi = x[i]
            if xi == 0.0:
                continue
            var row = i * n
            for j in range(n):
                y[j] += a[row + j] * xi
        return GemmResult(y^, rows, 1, GEMM_BACKEND_SCALAR, flops, GEMM_OK)

    var gap = a.unsafe_ptr()
    var gxp = x.unsafe_ptr()
    var gyp = y.unsafe_ptr()

    var gcells = m * n
    var gnw = info.num_physical_cores()
    if gnw < 1:
        gnw = 1
    if gcells < PARALLEL_MIN_CELLS or m < gnw:
        gnw = 1
    var gm = m
    var gn = n

    @parameter
    fn gemv_band(tid: Int) capturing:
        var rows_each = gm // gnw
        var lo = tid * rows_each
        var hi = lo + rows_each if tid < gnw - 1 else gm
        for i in range(lo, hi):
            var row = i * gn
            # Four accumulators: a single one serialises on FMA latency, which on a reduction this
            # tight is the binding constraint rather than bandwidth.
            var a0 = SIMD[DType.float64, W](0.0)
            var a1 = SIMD[DType.float64, W](0.0)
            var a2 = SIMD[DType.float64, W](0.0)
            var a3 = SIMD[DType.float64, W](0.0)
            var j = 0
            while j + 4 * W <= gn:
                a0 = a0 + (gap + row + j).load[width=W]() * (gxp + j).load[width=W]()
                a1 = a1 + (gap + row + j + W).load[width=W]() * (gxp + j + W).load[width=W]()
                a2 = a2 + (gap + row + j + 2 * W).load[width=W]() * (gxp + j + 2 * W).load[width=W]()
                a3 = a3 + (gap + row + j + 3 * W).load[width=W]() * (gxp + j + 3 * W).load[width=W]()
                j += 4 * W
            while j + W <= gn:
                a0 = a0 + (gap + row + j).load[width=W]() * (gxp + j).load[width=W]()
                j += W
            var total = (a0 + a1 + a2 + a3).reduce_add()
            while j < gn:
                total += gap[row + j] * gxp[j]
                j += 1
            gyp[i] = total

    parallelize[gemv_band](gnw)

    return GemmResult(y^, rows, 1, GEMM_BACKEND_CPU_SIMD, flops, GEMM_OK)


fn gemm_reference_delta_flat(
    a: List[Float64], b: List[Float64], m: Int, n: Int, k: Int
) -> RefDelta:
    """Compare `sgemm_flat` against the frozen `linalg.mat_mul`, element by element.

    The self-consistency check rule 4b asks for: a package's own reports must agree with each other,
    and that assertion catches a broken premise even where the right answer cannot be typed by hand.

    The two are NOT expected to be bit-identical — a blocked kernel sums in a different order and
    float addition is not associative — so the verdict is against a per-element tolerance built from
    `dtx_tol_for(reference_value, DT_F64, 0.0)`. That tolerance comes from the magnitude of the
    element being judged and nothing else: not the max over the matrix, not a `1 + |x|` floor, not the
    caller's own tolerance scaled by a magnitude. All four are rule 4b spellings and all four have
    shipped in this repo before.

    Bounded to modest shapes on purpose: the frozen oracle is O(n^3) and unblocked, so this is a
    correctness probe, not something to call on a real weight matrix.

    @capability gemm_reference_delta_flat
    complexity: O(m*n*k)
    counts:
    - m * k == len(a) [kernel_validated]
    - k * n == len(b) [kernel_validated]
    @endcapability
    """
    var shape = gemm_dims_check(m, n, k, len(a), len(b))
    if shape != GEMM_OK:
        return RefDelta(0.0, 0.0, False, 0, shape)
    if not gemm_work_fits(m, n, k, 1 << 22):
        return RefDelta(0.0, 0.0, False, 0, GEMM_ERR_EMPTY_DIM)

    var mine = sgemm_flat(a, b, m, n, k, 1.0, 0.0, False, False)
    if mine.status != GEMM_OK:
        return RefDelta(0.0, 0.0, False, 0, mine.status)

    var ma = Matrix(m, k)
    for i in range(m * k):
        ma.data[i] = a[i]
    var mb = Matrix(k, n)
    for i in range(k * n):
        mb.data[i] = b[i]
    var reference = mat_mul(ma, mb)

    var worst = 0.0
    var worst_tol = 0.0
    var within = True
    for i in range(m * n):
        var want = reference.data[i]
        var got = mine.c[i]
        var d = got - want
        if d < 0.0:
            d = -d
        var tol = dtx_tol_for(want, DT_F64, 0.0)
        # Accumulated rounding grows with the reduction length, so the per-element allowance is
        # scaled by k. Still built from THAT element's magnitude — k is the number of additions that
        # produced it, not an aggregate over other elements.
        var allowed = tol.relative_term * Float64(k) * 4.0
        if d > allowed:
            within = False
        if d > worst:
            worst = d
            worst_tol = allowed
    return RefDelta(worst, worst_tol, within, m * n, GEMM_OK)
