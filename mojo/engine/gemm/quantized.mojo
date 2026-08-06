"""
gemm.quantized — matmul with dequantization fused into the k-loop. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_gemm_quantized.mojo
benchmark: benchmarks/mojo_benchmarks/bench_tensorx_and_gemm.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

The entire point is what is NOT allocated
-------------------------------------------
A 4096x4096 NF4 weight is 8 MB packed and 128 MB as Float64. A "quantized" matmul that dequantizes
into a temporary and then calls a dense kernel has already spent the whole memory saving before it
does any arithmetic — and on token-at-a-time decode, which is bandwidth-bound rather than
compute-bound, that temporary *is* the cost. Reading 128 MB to do 16 M multiply-adds is the slow path
wearing the fast path's name.

So every kernel here reconstructs one weight at a time, inside the reduction loop, and the
dequantized value never leaves a register. `quantized_gemv_golden_delta` exists to prove that the
fused result matches the dequantize-then-dense result it is replacing, rather than asserting it.

Codes arrive unpacked
-----------------------
`w_codes` is one code per `Int`, which is what `tensorx.pack.quantize_nf4` returns. Nibble packing is
a *storage* concern and lives in `tensorx.pack.pack_int4`; forcing it into this signature would mean
every caller unpacks and repacks around a wire boundary that already carries `List[Int]`. The two
compose: pack for transport and storage, unpack once, multiply many times.

Scale indexing follows the block layout, and that is easy to get silently wrong
--------------------------------------------------------------------------------
A blockwise scale array has one entry per `block` consecutive weights **in the flattened row-major
order the quantizer saw**. So the scale for element `(i, j)` of an m-by-n weight is
`scales[(i * n + j) / block]`, not `scales[i]` and not `scales[j]`. Indexing by row is the natural
mistake, it produces a plausible tensor, and it is wrong by a factor that varies per block — which
reads as a model that almost works. The index is written out once here and asserted in the test
against a hand-computed case with two blocks per row.

Public API:
  gemv_nf4_flat(w_codes, w_scales, x, m, n, block)      — the decode hot path
  gemm_nf4_flat(w_codes, w_scales, x, m, n, k, block)
  gemv_int_flat(w_codes, w_scales, x, m, n, block, bits)
  quantized_gemv_golden_delta(w_codes, w_scales, x, m, n, block)
"""

from std.algorithm import parallelize
from std.sys import info

from quantization import dequantize_symmetric
from gemm.contract import (
    GEMM_BACKEND_CPU_SIMD,
    GEMM_BACKEND_SCALAR,
    GEMM_ERR_A_LENGTH,
    GEMM_ERR_BLOCK_SIZE,
    GEMM_ERR_CODE_OUT_OF_RANGE,
    GEMM_ERR_EMPTY_DIM,
    GEMM_ERR_SCALE_LENGTH,
    GEMM_MAX_FLOP_CELLS,
    GEMM_OK,
    gemm_work_fits,
)
from tensorx.contract import TX_OK, tx_count_ok
from tensorx.dtype import DT_F64, dtx_tol_for
from tensorx.pack import PACK_MAX_BLOCK, nf4_levels

comptime QGEMM_MAX_BLOCK: Int = 1024
"""Mirror of `tensorx.pack.PACK_MAX_BLOCK`, restated here because a `dim ... <= NAME` capability
relation must name a constant declared in the file that makes the claim — otherwise the declaration
and the value the kernel actually tests can drift apart in separate commits.

The kernels below still compare against the imported `PACK_MAX_BLOCK`, so this is the declaration's
copy rather than a second source of truth, and `test_gemm_quantized.mojo` asserts the two are equal."""


@fieldwise_init
struct QGemmResult(Copyable, Movable):
    """A quantized product, its shape, and which kernel produced it."""

    var y: List[Float64]
    var rows: Int
    var cols: Int
    var backend_used: Int
    var flop_count: Float64
    var status: Int


@fieldwise_init
struct QDelta(Copyable, Movable):
    """Fused-versus-materialized agreement, and the bar it should be judged against."""

    var max_abs_delta: Float64
    var tolerance_at_max: Float64
    var within_tolerance: Bool
    var n_compared: Int
    var status: Int


def _q_shape_check(
    n_codes: Int, n_scales: Int, elems: Int, block: Int
) -> Int:
    """Validate a blockwise-quantized operand: code count, block size, and scale count together.

    All three in one place because they are one invariant: `elems` codes at `block` per scale need
    exactly `ceil(elems / block)` scales, and checking any two of the three lets the third disagree.
    """
    if elems <= 0:
        return GEMM_ERR_EMPTY_DIM
    if block <= 0 or block > PACK_MAX_BLOCK:
        return GEMM_ERR_BLOCK_SIZE
    if n_codes < elems:
        return GEMM_ERR_A_LENGTH
    var need = (elems + block - 1) // block
    if n_scales < need:
        return GEMM_ERR_SCALE_LENGTH
    return GEMM_OK


def gemv_nf4_flat(
    w_codes: List[Int], w_scales: List[Float64], x: List[Float64],
    m: Int, n: Int, block: Int
) -> QGemmResult:
    """y = W @ x where W is m-by-n NF4, dequantized inside the reduction. No f64 weight is built.

    The decode-shaped kernel: one vector in, one vector out, every weight read exactly once. It is
    memory-bound, so the win comes entirely from reading 4 bits per weight instead of 64 — which only
    holds if nothing here materializes the dequantized matrix.

    @capability gemv_nf4_flat
    complexity: O(m*n)
    counts:
    - m * n <= len(w_codes) [kernel_validated]
    - n <= len(x) [kernel_validated]
    - dim block <= QGEMM_MAX_BLOCK [kernel_validated]
    @endcapability
    """
    var empty = List[Float64]()
    if m <= 0 or n <= 0:
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_EMPTY_DIM)
    if not gemm_work_fits(m, n, 1, GEMM_MAX_FLOP_CELLS):
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_EMPTY_DIM)
    var elems = m * n
    var shape = _q_shape_check(len(w_codes), len(w_scales), elems, block)
    if shape != GEMM_OK:
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, shape)
    if tx_count_ok(n, len(x)) != TX_OK:
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_A_LENGTH)

    var levels = nf4_levels()
    var y = List[Float64](capacity=m)
    var lp = levels.unsafe_ptr()
    var cp = w_codes.unsafe_ptr()
    var sp = w_scales.unsafe_ptr()
    var xp = x.unsafe_ptr()

    # Walk each row block by block rather than element by element. Two things fall out, and both
    # matter more than they look:
    #
    #   * `idx // block` disappears from the inner loop. An integer division is tens of cycles and
    #     this loop is otherwise a lookup and a multiply-add — measured, it was the single largest
    #     cost in the kernel, larger than the memory traffic the whole module exists to reduce.
    #   * the scale becomes loop-invariant, so it multiplies the block's partial sum ONCE instead of
    #     multiplying every element.
    #
    # A block may straddle a row boundary, so the chunk end is the nearer of the row end and the
    # next scale boundary; that is why this is not simply a nested `for block` loop.
    # Codes are validated in one pass up front rather than inside the reduction. Two reasons: the
    # branch was costing a compare per weight in the hottest loop in the module, and a mid-reduction
    # bail-out cannot be expressed inside a `parallelize` worker anyway — a worker cannot return a
    # status. Validating first makes the inner loop branch-free and the failure path exact.
    for idx in range(elems):
        var code = cp[idx]
        if code < 0 or code > 15:
            # Refused, not clamped: a code outside the codebook means these weights did not come from
            # this quantizer, and level 0 or 15 would be a confident wrong answer.
            return QGemmResult(
                List[Float64](), 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_CODE_OUT_OF_RANGE
            )

    for _ in range(m):
        y.append(0.0)
    var yp = y.unsafe_ptr()

    var nw = info.num_physical_cores()
    if nw < 1:
        nw = 1
    if elems < 1 << 16 or m < nw:
        nw = 1
    var qm = m
    var qn2 = n
    var qblock = block
    var qnw = nw

    @parameter
    def nf4_band(tid: Int) capturing:
        var rows_each = qm // qnw
        var lo = tid * rows_each
        var hi = lo + rows_each if tid < qnw - 1 else qm
        for i in range(lo, hi):
            var base = i * qn2
            var acc = 0.0
            var j = 0
            while j < qn2:
                # One integer division per BLOCK, not per weight. Measured: with the division inside
                # the element loop this kernel lost to materialize-then-dense outright, because a
                # 64-bit divide is tens of cycles against a lookup and a multiply-add.
                var blk = (base + j) // qblock
                var chunk_end = (blk + 1) * qblock - base
                if chunk_end > qn2:
                    chunk_end = qn2
                # Four accumulators again: the codebook lookup is a gather that will not vectorise on
                # NEON, so the remaining headroom is instruction-level parallelism on the adds.
                var p0 = 0.0
                var p1 = 0.0
                var p2 = 0.0
                var p3 = 0.0
                while j + 4 <= chunk_end:
                    p0 += lp[cp[base + j]] * xp[j]
                    p1 += lp[cp[base + j + 1]] * xp[j + 1]
                    p2 += lp[cp[base + j + 2]] * xp[j + 2]
                    p3 += lp[cp[base + j + 3]] * xp[j + 3]
                    j += 4
                while j < chunk_end:
                    p0 += lp[cp[base + j]] * xp[j]
                    j += 1
                # The scale multiplies the block's partial sum ONCE, not every element.
                acc += (p0 + p1 + p2 + p3) * sp[blk]
            yp[i] = acc

    parallelize[nf4_band](nw)

    return QGemmResult(y^, m, 1, GEMM_BACKEND_CPU_SIMD, 2.0 * Float64(elems), GEMM_OK)


def gemm_nf4_flat(
    w_codes: List[Int], w_scales: List[Float64], x: List[Float64],
    m: Int, n: Int, k: Int, block: Int
) -> QGemmResult:
    """C = W @ X where W is m-by-k NF4 and X is k-by-n dense. Dequantization stays in the k-loop.

    Loop order is i-k-j for the same reason as the dense kernel: the reconstructed weight `W[i][kk]`
    is invariant across j, so it is rebuilt once per (i, kk) rather than once per output element.
    Ordering this i-j-k would dequantize the same weight n times.

    @capability gemm_nf4_flat
    complexity: O(m*n*k)
    counts:
    - m * k <= len(w_codes) [kernel_validated]
    - k * n <= len(x) [kernel_validated]
    - dim block <= QGEMM_MAX_BLOCK [kernel_validated]
    @endcapability
    """
    var empty = List[Float64]()
    if m <= 0 or n <= 0 or k <= 0:
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_EMPTY_DIM)
    if not gemm_work_fits(m, n, k, GEMM_MAX_FLOP_CELLS):
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_EMPTY_DIM)
    var w_elems = m * k
    var shape = _q_shape_check(len(w_codes), len(w_scales), w_elems, block)
    if shape != GEMM_OK:
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, shape)
    if len(x) < k * n:
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_A_LENGTH)

    var levels = nf4_levels()
    var c = List[Float64](capacity=m * n)
    for _ in range(m * n):
        c.append(0.0)

    for i in range(m):
        var c_row = i * n
        var w_row = i * k
        for kk in range(k):
            var idx = w_row + kk
            var code = w_codes[idx]
            if code < 0 or code > 15:
                return QGemmResult(
                    List[Float64](), 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_CODE_OUT_OF_RANGE
                )
            var w = levels[code] * w_scales[idx // block]
            if w == 0.0:
                continue
            var x_row = kk * n
            for j in range(n):
                c[c_row + j] += w * x[x_row + j]

    return QGemmResult(
        c^, m, n, GEMM_BACKEND_CPU_SIMD, 2.0 * Float64(m) * Float64(n) * Float64(k), GEMM_OK
    )


def gemv_int_flat(
    w_codes: List[Int], w_scales: List[Float64], x: List[Float64],
    m: Int, n: Int, block: Int, bits: Int
) -> QGemmResult:
    """y = W @ x for a uniform symmetric int4/int8 grid, dequantized in the reduction.

    Uses the frozen `quantization.dequantize_symmetric` per weight rather than multiplying here, so a
    uniform code means exactly one thing across the whole tree.

    @capability gemv_int_flat
    complexity: O(m*n)
    counts:
    - m * n <= len(w_codes) [kernel_validated]
    - n <= len(x) [kernel_validated]
    - dim block <= QGEMM_MAX_BLOCK [kernel_validated]
    @endcapability
    """
    var empty = List[Float64]()
    if m <= 0 or n <= 0:
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_EMPTY_DIM)
    if bits != 4 and bits != 8:
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_CODE_OUT_OF_RANGE)
    if not gemm_work_fits(m, n, 1, GEMM_MAX_FLOP_CELLS):
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_EMPTY_DIM)
    var elems = m * n
    var shape = _q_shape_check(len(w_codes), len(w_scales), elems, block)
    if shape != GEMM_OK:
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, shape)
    if tx_count_ok(n, len(x)) != TX_OK:
        return QGemmResult(empty^, 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_A_LENGTH)

    var lo = -8 if bits == 4 else -128
    var hi = 7 if bits == 4 else 127
    var y = List[Float64](capacity=m)

    for i in range(m):
        var base = i * n
        var acc = 0.0
        for j in range(n):
            var idx = base + j
            var code = w_codes[idx]
            if code < lo or code > hi:
                return QGemmResult(
                    List[Float64](), 0, 0, GEMM_BACKEND_SCALAR, 0.0, GEMM_ERR_CODE_OUT_OF_RANGE
                )
            acc += dequantize_symmetric(Float64(code), w_scales[idx // block]) * x[j]
        y.append(acc)

    return QGemmResult(y^, m, 1, GEMM_BACKEND_SCALAR, 2.0 * Float64(elems), GEMM_OK)


def quantized_gemv_golden_delta(
    w_codes: List[Int], w_scales: List[Float64], x: List[Float64],
    m: Int, n: Int, block: Int
) -> QDelta:
    """Compare the fused NF4 GEMV against dequantize-then-dense, element by element.

    The claim this module makes is "same answer, less memory". This is the check that makes it a
    claim rather than an assertion: it materializes the weight matrix the slow way, multiplies it
    densely, and diffs.

    The bar is a tolerance, not exact equality, and the reason is worth stating because the first
    version of this function did assert exact equality and was right to at the time.

    The fused kernel hoists the block scale out of its inner loop — it accumulates
    `sum(level * x)` and multiplies by the scale once per block, rather than multiplying every
    element. That is the optimization that makes the kernel worth having (it removes an integer
    division and a multiply per weight), and it re-associates the arithmetic. Floating-point
    multiplication does not distribute exactly, so the two paths now differ by about one ULP.

    A tolerance still catches the bug this exists for. A scale-indexing error — `scales[i]` instead
    of `scales[(i * n + j) / block]` — is wrong by a *factor*, not by an ULP, so it fails a bound
    built from `dtx_tol_for` by many orders of magnitude. What the tolerance gives up is the ability
    to detect a re-association, which is not a defect.

    Bounded to modest shapes: the reference path allocates the full dense weight, which is exactly
    what the fused kernel refuses to do.

    @capability quantized_gemv_golden_delta
    complexity: O(m*n)
    counts:
    - m * n <= len(w_codes) [kernel_validated]
    - n <= len(x) [kernel_validated]
    - dim block <= QGEMM_MAX_BLOCK [kernel_validated]
    @endcapability
    """
    if m <= 0 or n <= 0 or not gemm_work_fits(m, n, 1, 1 << 20):
        return QDelta(0.0, 0.0, False, 0, GEMM_ERR_EMPTY_DIM)
    var elems = m * n
    var shape = _q_shape_check(len(w_codes), len(w_scales), elems, block)
    if shape != GEMM_OK:
        return QDelta(0.0, 0.0, False, 0, shape)
    if tx_count_ok(n, len(x)) != TX_OK:
        return QDelta(0.0, 0.0, False, 0, GEMM_ERR_A_LENGTH)

    var fused = gemv_nf4_flat(w_codes, w_scales, x, m, n, block)
    if fused.status != GEMM_OK:
        return QDelta(0.0, 0.0, False, 0, fused.status)

    # The path this module exists to avoid: build the whole dense weight, then multiply.
    var levels = nf4_levels()
    var dense = List[Float64](capacity=elems)
    for idx in range(elems):
        var code = w_codes[idx]
        if code < 0 or code > 15:
            return QDelta(0.0, 0.0, False, 0, GEMM_ERR_CODE_OUT_OF_RANGE)
        dense.append(levels[code] * w_scales[idx // block])

    var worst = 0.0
    var worst_tol = 0.0
    var within = True
    for i in range(m):
        var acc = 0.0
        for j in range(n):
            acc += dense[i * n + j] * x[j]
        var d = fused.y[i] - acc
        if d < 0.0:
            d = -d
        # Built from THIS row's own magnitude and the number of additions that produced it — not
        # from a max over the output vector, which is rule 4b spelling 2.
        var tol = dtx_tol_for(acc, DT_F64, 0.0)
        var allowed = tol.relative_term * Float64(n) * 4.0
        if d > allowed:
            within = False
        if d > worst:
            worst = d
            worst_tol = allowed

    return QDelta(worst, worst_tol, within, m, GEMM_OK)
