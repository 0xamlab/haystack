"""
attnk.tiled — blockwise online-softmax attention over flat buffers, with GQA. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_attnk_tiled.mojo
benchmark: benchmarks/mojo_benchmarks/bench_vs_torch_attention.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

Why a new package when the tree already has attention modules
--------------------------------------------------------------
It has three — `transformer_attention`, `flash_attention`, `sparse_attention` — and all three are
frozen, correct, and not attention kernels. Every function in them is scalar. The whole of
`transformer_attention.scaled_dot_product_attention` is:

    return q_dot_k / sqrt(d_k)

It receives an ALREADY-COMPUTED dot product and performs one divide. It never touches Q, K or V, does
no softmax and does no matmul. `flash_attention`'s five functions are the scalar recurrence STEPS of
the online-softmax update — `flash_block_max`, `flash_block_sum_exp`, `flash_block_output` — with no
driver anywhere that loops them over a tile. Counted directly: `List[` appears 0 times in all three
files.

So there was nothing in the tree that computes the same QUANTITY as
`torch.nn.functional.scaled_dot_product_attention`, and no ratio between a one-divide helper and a
fused O(s^2 d) kernel could have meant anything. This module is that driver. It is additive: no
existing file is modified, and the frozen scalar helpers keep their exact semantics. The recurrence
implemented in `_tiled_band` is the same one `flash_attention.mojo` documents element by element —
the value here is the composition and the memory schedule, not the formula.

The two kernels differ in one thing, and it is the point
--------------------------------------------------------
`attn_forward_direct` materializes the full `s_q x s_kv` score matrix for a head, then softmaxes rows
of it. That is what a naive implementation does and what PyTorch's `math` SDPA backend does. Its
intermediate footprint is quadratic in sequence length: at s = 8192, 512 MB per head.

`attn_forward_tiled` never holds more than one `br x bc` tile. It carries a running row maximum `m`
and a running normalizer `l`, rescales the accumulated output by `exp(m_old - m_new)` when the maximum
moves, and finishes a row without any other block's scores having been resident. Its intermediate
footprint is `br*bc + br*d + 2*br` — a constant, at every sequence length.

Both produce the same answer to within summation order. Neither is bit-identical to the other, and
neither can be: they sum the same products in different orders and float addition is not associative.
`attn_reference_delta` measures that difference and reports the tolerance it should be judged against
rather than asserting an equality that is false.

The running maximum is not an optimization, it is the reason the kernel is usable
--------------------------------------------------------------------------------
`attn_forward_unstable` exists to be shown failing. It is byte-identical to the direct kernel except
that it computes `exp(score)` instead of `exp(score - row_max)`. Float64 `exp` overflows to infinity
above ~709.78, so a logit of 800 — entirely reachable with un-normalized weights or a long context —
makes the numerator inf, the denominator inf, and the output NaN. It returns ATTN_ERR_OVERFLOW when
that happens. It is never timed against anything and never reported as a competitor; a straw man
timed against a real kernel would be a rigged comparison, whereas a straw man shown producing NaN at
an input where both real kernels are exact is evidence.

`m` is initialised to -1e308 rather than true -inf, deliberately: `exp(-1e308 - m_new)` underflows to
exactly 0.0, which is the correct first-block correction factor, and it does so without ever putting
an infinity into the arithmetic where a later `0 * inf` could manufacture a NaN.

Parallel unit is a (head, row-block) pair, not a head
-----------------------------------------------------
Partitioning by head alone caps the machine at `batch * h_q` workers — 8 on the benchmark shape, on 16
cores, so half the host idles. Rows of the output are independent in attention (a query row's result
depends on no other query row), so `(b, h_q, row_block)` is the finest legal partition and it is what
is used. Each worker owns a contiguous BAND of those tasks and writes only inside its own output rows;
there is no sharing and no lock. Scratch is allocated once per WORKER, not once per task — at s = 8192
there are 1024 tasks and allocating a score tile per task would put the allocator in the inner loop.

Bounds are validated before any index, because the failure mode is not an exception
----------------------------------------------------------------------------------
`attn_dims_check` compares every dimension against the real buffer lengths first. Reading a `List`
past its end in Mojo is an uncatchable bounds abort that takes the entire worker process down — a
`try`/`except` at the dispatch does not contain it, and the caller observes a request that never
returns rather than an error. That is why the shape contract is exact and checked once, up front,
and why the raw pointers below are only taken after it has passed.

Public API:
  attn_forward_tiled(q, k, v, b, h_q, h_kv, s_q, s_kv, d, scale, causal, br, bc, workers) -> AttnResult
  attn_forward_direct(q, k, v, b, h_q, h_kv, s_q, s_kv, d, scale, causal, workers) -> AttnResult
  attn_forward_unstable(q, k, v, b, h_q, h_kv, s_q, s_kv, d, scale, causal, workers) -> AttnResult
  attn_reference_delta(q, k, v, batch, h_q, h_kv, s_q, s_kv, d, scale, causal) -> AttnDelta
  attn_flop_count(batch, h_q, s_q, s_kv, d, causal) -> Float64
"""

from max.algorithm import parallelize
from std.math import abs as fabs, exp, isinf, isnan, sqrt
from std.sys import info
from std.sys.info import simd_width_of

from attnk.contract import (
    ATTN_BACKEND_DIRECT,
    ATTN_BACKEND_TILED,
    ATTN_BACKEND_UNSTABLE,
    ATTN_ERR_CAUSAL_SHAPE,
    ATTN_ERR_LENGTH_MISMATCH,
    ATTN_ERR_NON_FINITE_SCALE,
    ATTN_ERR_OVERFLOW,
    ATTN_ERR_Q_LENGTH,
    ATTN_ERR_SCORE_BYTES,
    ATTN_ERR_TILE,
    ATTN_MAX_SCORE_BYTES,
    ATTN_OK,
    attn_dims_check,
    attn_scale_ok,
    attn_score_bytes_fit,
    attn_ws_bytes_direct,
    attn_ws_bytes_tiled,
)
from tensorx.dtype import DT_F64, dtx_tol_for

comptime W: Int = simd_width_of[DType.float64]()
"""SIMD lanes for Float64 on the build target. 2 on 128-bit NEON, 8 on AVX-512."""

comptime BR_DEFAULT: Int = 32
comptime BC_DEFAULT: Int = 128
"""Default tile. 32 query rows x 128 keys is a 32 KB score tile; with a 32x64 accumulator (16 KB) and
the 64 KB K and V blocks being streamed against it, one worker's live set is ~176 KB — inside L2 on
this host, and small enough that 16 workers do not evict each other. These are defaults, not a tuning
result: `br` and `bc` are parameters, and `attn_ws_bytes_tiled` reports what any choice costs."""

comptime NEG_BIG: Float64 = -1e308
"""Initial running maximum. See the module docstring: chosen over true -inf so that the first-block
correction `exp(NEG_BIG - m_new)` underflows to exactly 0.0 without an infinity entering the
arithmetic."""

comptime EXP_OVERFLOW_ARG: Float64 = 709.78
"""ln(Float64 max). `exp` of anything above this is +inf. The unstable kernel's failure threshold."""


@fieldwise_init
struct AttnResult(Copyable, Movable):
    """An attention output, which kernel produced it, and what it cost to hold."""

    var out: List[Float64]
    var rows: Int
    """batch * h_q * s_q — output rows, each of `d` elements."""
    var d: Int
    var backend_used: Int
    var flop_count: Float64
    var working_set_bytes: Float64
    """Intermediate bytes ONE worker holds live. Excludes Q/K/V/O, which both kernels pay alike."""
    var n_workers: Int
    """Actual parallel width used. Reported because a ratio between two arms at different thread
    counts is a thread-count measurement, not a kernel measurement."""
    var max_abs_logit: Float64
    """Largest |score * scale| seen. The softmax-stability evidence: this is the number that must be
    compared against EXP_OVERFLOW_ARG to know whether max subtraction was load-bearing on this input."""
    var status: Int


@fieldwise_init
struct AttnDelta(Copyable, Movable):
    """How far the tiled kernel is from the direct one, and how far it is allowed to be."""

    var max_abs_delta: Float64
    var max_rel_delta: Float64
    var tolerance_at_max: Float64
    var within_tolerance: Bool
    var n_compared: Int
    var status: Int


def attn_flop_count(
    batch: Int, h_q: Int, s_q: Int, s_kv: Int, d: Int, causal: Bool
) -> Float64:
    """FLOPs for one forward pass: 2*B*H*Sq*Skv*D for QK^T plus the same again for P@V.

    Halved for causal, which is the exact count for the skipped upper triangle only in the limit; the
    block-granular kernel computes a few masked cells inside diagonal blocks. Stated because a FLOP
    rate derived from a count that is 2x wrong is a 2x wrong rate, and the causal arm's number is
    therefore reported as a lower bound on achieved throughput rather than an exact one.
    """
    if batch < 1 or h_q < 1 or s_q < 1 or s_kv < 1 or d < 1:
        return 0.0
    var f = (
        4.0
        * Float64(batch)
        * Float64(h_q)
        * Float64(s_q)
        * Float64(s_kv)
        * Float64(d)
    )
    return f * 0.5 if causal else f


def _dot_simd(
    qp: UnsafePointer[Float64, origin=AnyOrigin[mut=False]],
    kp: UnsafePointer[Float64, origin=AnyOrigin[mut=False]],
    q_off: Int, k_off: Int, d: Int
) -> Float64:
    """Dot product of two length-`d` contiguous runs, four independent accumulator streams.

    Four streams rather than one because a single chained FMA has ~4 cycles of latency and d = 64 at
    W = 2 is 32 links of that chain — latency-bound at a quarter of the issue rate. Four independent
    partial sums let the pipes fill. `vector_kernels/dot.mojo` uses eight for the same reason;
    the sum order is fixed and identical on every call, so the kernel stays deterministic.

    `alignment=8` is required: a `List`'s heap buffer promises 8-byte alignment for Float64 and
    nothing more, and asking for the SIMD type's natural 16 is a fault waiting for an odd offset.
    """
    var a0 = SIMD[DType.float64, W](0.0)
    var a1 = SIMD[DType.float64, W](0.0)
    var a2 = SIMD[DType.float64, W](0.0)
    var a3 = SIMD[DType.float64, W](0.0)
    var i = 0
    while i + 4 * W <= d:
        a0 += (qp + q_off + i).load[width=W, alignment=8]() * (
            kp + k_off + i
        ).load[width=W, alignment=8]()
        a1 += (qp + q_off + i + W).load[width=W, alignment=8]() * (
            kp + k_off + i + W
        ).load[width=W, alignment=8]()
        a2 += (qp + q_off + i + 2 * W).load[width=W, alignment=8]() * (
            kp + k_off + i + 2 * W
        ).load[width=W, alignment=8]()
        a3 += (qp + q_off + i + 3 * W).load[width=W, alignment=8]() * (
            kp + k_off + i + 3 * W
        ).load[width=W, alignment=8]()
        i += 4 * W
    var acc = ((a0 + a1) + (a2 + a3)).reduce_add()
    while i + W <= d:
        acc += (
            (qp + q_off + i).load[width=W, alignment=8]()
            * (kp + k_off + i).load[width=W, alignment=8]()
        ).reduce_add()
        i += W
    while i < d:
        acc += qp[q_off + i] * kp[k_off + i]
        i += 1
    return acc


def _dot4_simd(
    qp: UnsafePointer[Float64, origin=AnyOrigin[mut=False]],
    kp: UnsafePointer[Float64, origin=AnyOrigin[mut=False]],
    q0: Int, q_stride: Int, k0: Int, d: Int
) -> SIMD[DType.float64, 4]:
    """Four query rows against ONE key row, in one pass. The register-blocked QK^T microkernel.

    Why this exists, measured rather than assumed
    ---------------------------------------------
    The obvious loop computes each score as an independent dot product. Per `W`-wide step that is one
    Q load, one K load and one FMA — two loads per vector FMA. On this core the load ports saturate
    long before the FMA pipes do, so the kernel runs load-bound at roughly a third of the achievable
    rate and the arithmetic units idle.

    Holding four query rows in flight against a single K load makes it five loads per four FMAs
    instead of eight, because the K vector is loaded once and reused across all four accumulators.
    It also gives four independent dependency chains, which is what fills a pipeline whose FMA latency
    is several cycles.

    `q_stride` is `d`: the four rows are consecutive rows of Q for the same (batch, head), so they are
    contiguous and the four loads issue from the same cache lines they would have touched anyway.
    """
    var a0 = SIMD[DType.float64, W](0.0)
    var a1 = SIMD[DType.float64, W](0.0)
    var a2 = SIMD[DType.float64, W](0.0)
    var a3 = SIMD[DType.float64, W](0.0)
    var i = 0
    while i + W <= d:
        var kv = (kp + k0 + i).load[width=W, alignment=8]()
        a0 += (qp + q0 + i).load[width=W, alignment=8]() * kv
        a1 += (qp + q0 + q_stride + i).load[width=W, alignment=8]() * kv
        a2 += (qp + q0 + 2 * q_stride + i).load[width=W, alignment=8]() * kv
        a3 += (qp + q0 + 3 * q_stride + i).load[width=W, alignment=8]() * kv
        i += W
    var out = SIMD[DType.float64, 4](0.0)
    out[0] = a0.reduce_add()
    out[1] = a1.reduce_add()
    out[2] = a2.reduce_add()
    out[3] = a3.reduce_add()
    while i < d:
        var kv = kp[k0 + i]
        out[0] += qp[q0 + i] * kv
        out[1] += qp[q0 + q_stride + i] * kv
        out[2] += qp[q0 + 2 * q_stride + i] * kv
        out[3] += qp[q0 + 3 * q_stride + i] * kv
        i += 1
    return out


def _dot4x4_simd(
    qp: UnsafePointer[Float64, origin=AnyOrigin[mut=False]],
    kp: UnsafePointer[Float64, origin=AnyOrigin[mut=False]],
    q0: Int, q_stride: Int, k0: Int, k_stride: Int, d: Int
) -> SIMD[DType.float64, 16]:
    """FOUR query rows against FOUR key rows: the 4x4 QK^T microkernel.

    `_dot4_simd` reuses one K vector across four accumulators, so a `W`-wide step is five loads
    feeding four FMAs — an arithmetic intensity of 0.8, still short of what keeps the FMA pipes busy.
    Blocking the key dimension as well makes the same step eight loads feeding sixteen FMAs, an
    intensity of 2.0. Sixteen accumulators plus four Q and four K vectors is 24 of the 32 NEON vector
    registers, so nothing spills.

    Measured in isolation at s=512, d=64, one thread: 18.0 -> 23.8 GFLOP/s, a 1.32x gain, against a
    measured single-thread NEON f64 FMA ceiling of 35.8 GFLOP/s.

    Result layout is `[q_row * 4 + k_row]`. Each score accumulates over `d` in exactly the order
    `_dot4_simd` uses, so the two agree BIT-FOR-BIT and this is a pure throughput change.
    """
    var a00 = SIMD[DType.float64, W](0.0)
    var a01 = SIMD[DType.float64, W](0.0)
    var a02 = SIMD[DType.float64, W](0.0)
    var a03 = SIMD[DType.float64, W](0.0)
    var a10 = SIMD[DType.float64, W](0.0)
    var a11 = SIMD[DType.float64, W](0.0)
    var a12 = SIMD[DType.float64, W](0.0)
    var a13 = SIMD[DType.float64, W](0.0)
    var a20 = SIMD[DType.float64, W](0.0)
    var a21 = SIMD[DType.float64, W](0.0)
    var a22 = SIMD[DType.float64, W](0.0)
    var a23 = SIMD[DType.float64, W](0.0)
    var a30 = SIMD[DType.float64, W](0.0)
    var a31 = SIMD[DType.float64, W](0.0)
    var a32 = SIMD[DType.float64, W](0.0)
    var a33 = SIMD[DType.float64, W](0.0)
    var i = 0
    while i + W <= d:
        var q0v = (qp + q0 + i).load[width=W, alignment=8]()
        var q1v = (qp + q0 + q_stride + i).load[width=W, alignment=8]()
        var q2v = (qp + q0 + 2 * q_stride + i).load[width=W, alignment=8]()
        var q3v = (qp + q0 + 3 * q_stride + i).load[width=W, alignment=8]()
        var k0v = (kp + k0 + i).load[width=W, alignment=8]()
        var k1v = (kp + k0 + k_stride + i).load[width=W, alignment=8]()
        var k2v = (kp + k0 + 2 * k_stride + i).load[width=W, alignment=8]()
        var k3v = (kp + k0 + 3 * k_stride + i).load[width=W, alignment=8]()
        a00 += q0v * k0v
        a01 += q0v * k1v
        a02 += q0v * k2v
        a03 += q0v * k3v
        a10 += q1v * k0v
        a11 += q1v * k1v
        a12 += q1v * k2v
        a13 += q1v * k3v
        a20 += q2v * k0v
        a21 += q2v * k1v
        a22 += q2v * k2v
        a23 += q2v * k3v
        a30 += q3v * k0v
        a31 += q3v * k1v
        a32 += q3v * k2v
        a33 += q3v * k3v
        i += W
    var o = SIMD[DType.float64, 16](0.0)
    o[0] = a00.reduce_add()
    o[1] = a01.reduce_add()
    o[2] = a02.reduce_add()
    o[3] = a03.reduce_add()
    o[4] = a10.reduce_add()
    o[5] = a11.reduce_add()
    o[6] = a12.reduce_add()
    o[7] = a13.reduce_add()
    o[8] = a20.reduce_add()
    o[9] = a21.reduce_add()
    o[10] = a22.reduce_add()
    o[11] = a23.reduce_add()
    o[12] = a30.reduce_add()
    o[13] = a31.reduce_add()
    o[14] = a32.reduce_add()
    o[15] = a33.reduce_add()
    # Scalar tail for a head_dim that is not a multiple of W. Same order as `_dot4_simd`'s tail.
    while i < d:
        var qv0 = qp[q0 + i]
        var qv1 = qp[q0 + q_stride + i]
        var qv2 = qp[q0 + 2 * q_stride + i]
        var qv3 = qp[q0 + 3 * q_stride + i]
        var kvv0 = kp[k0 + i]
        var kvv1 = kp[k0 + k_stride + i]
        var kvv2 = kp[k0 + 2 * k_stride + i]
        var kvv3 = kp[k0 + 3 * k_stride + i]
        o[0] += qv0 * kvv0
        o[1] += qv0 * kvv1
        o[2] += qv0 * kvv2
        o[3] += qv0 * kvv3
        o[4] += qv1 * kvv0
        o[5] += qv1 * kvv1
        o[6] += qv1 * kvv2
        o[7] += qv1 * kvv3
        o[8] += qv2 * kvv0
        o[9] += qv2 * kvv1
        o[10] += qv2 * kvv2
        o[11] += qv2 * kvv3
        o[12] += qv3 * kvv0
        o[13] += qv3 * kvv1
        o[14] += qv3 * kvv2
        o[15] += qv3 * kvv3
        i += 1
    return o


def _axpy4_simd(
    op: UnsafePointer[Float64, origin=AnyOrigin[mut=True]],
    vp: UnsafePointer[Float64, origin=AnyOrigin[mut=False]],
    o0: Int, o_stride: Int, v_off: Int, d: Int,
    p0: Float64, p1: Float64, p2: Float64, p3: Float64
):
    """Four output rows accumulate one V row. The register-blocked P@V microkernel.

    Same argument as `_dot4_simd` in the other direction: the V row is loaded once and applied to four
    accumulators, so the load-to-FMA ratio drops from two-to-one to five-to-four.
    """
    var b0 = SIMD[DType.float64, W](p0)
    var b1 = SIMD[DType.float64, W](p1)
    var b2 = SIMD[DType.float64, W](p2)
    var b3 = SIMD[DType.float64, W](p3)
    var i = 0
    while i + W <= d:
        var vv = (vp + v_off + i).load[width=W, alignment=8]()
        var o0v = (op + o0 + i).load[width=W, alignment=8]()
        var o1v = (op + o0 + o_stride + i).load[width=W, alignment=8]()
        var o2v = (op + o0 + 2 * o_stride + i).load[width=W, alignment=8]()
        var o3v = (op + o0 + 3 * o_stride + i).load[width=W, alignment=8]()
        (op + o0 + i).store[alignment=8](o0v + b0 * vv)
        (op + o0 + o_stride + i).store[alignment=8](o1v + b1 * vv)
        (op + o0 + 2 * o_stride + i).store[alignment=8](o2v + b2 * vv)
        (op + o0 + 3 * o_stride + i).store[alignment=8](o3v + b3 * vv)
        i += W
    while i < d:
        var vv = vp[v_off + i]
        op[o0 + i] += p0 * vv
        op[o0 + o_stride + i] += p1 * vv
        op[o0 + 2 * o_stride + i] += p2 * vv
        op[o0 + 3 * o_stride + i] += p3 * vv
        i += 1


def _axpy_simd(
    op: UnsafePointer[Float64, origin=AnyOrigin[mut=True]],
    vp: UnsafePointer[Float64, origin=AnyOrigin[mut=False]],
    o_off: Int, v_off: Int, d: Int, p: Float64
):
    """out[o_off:o_off+d] += p * v[v_off:v_off+d]. The P@V accumulation, one key at a time."""
    var vp_b = SIMD[DType.float64, W](p)
    var i = 0
    while i + 2 * W <= d:
        var o0 = (op + o_off + i).load[width=W, alignment=8]()
        var o1 = (op + o_off + i + W).load[width=W, alignment=8]()
        var v0 = (vp + v_off + i).load[width=W, alignment=8]()
        var v1 = (vp + v_off + i + W).load[width=W, alignment=8]()
        (op + o_off + i).store[alignment=8](o0 + vp_b * v0)
        (op + o_off + i + W).store[alignment=8](o1 + vp_b * v1)
        i += 2 * W
    while i + W <= d:
        var o0 = (op + o_off + i).load[width=W, alignment=8]()
        var v0 = (vp + v_off + i).load[width=W, alignment=8]()
        (op + o_off + i).store[alignment=8](o0 + vp_b * v0)
        i += W
    while i < d:
        op[o_off + i] += p * vp[v_off + i]
        i += 1


def _scale_simd(
    op: UnsafePointer[Float64, origin=AnyOrigin[mut=True]],
    o_off: Int, d: Int, s: Float64,
):
    """out[o_off:o_off+d] *= s. The `exp(m_old - m_new)` rescale of the output accumulator."""
    var sv = SIMD[DType.float64, W](s)
    var i = 0
    while i + W <= d:
        var o0 = (op + o_off + i).load[width=W, alignment=8]()
        (op + o_off + i).store[alignment=8](o0 * sv)
        i += W
    while i < d:
        op[o_off + i] *= s
        i += 1


def _zeros(n: Int) -> List[Float64]:
    var out = List[Float64](capacity=n if n > 0 else 1)
    for _ in range(n):
        out.append(0.0)
    return out^


def _workers_for(tasks: Int, requested: Int) -> Int:
    """`requested` workers, or one per physical core when `requested` <= 0. Never more than tasks.

    Explicit rather than always-auto because a ratio between two arms at different thread counts is a
    thread-count measurement, not a kernel measurement. A single-threaded baseline needs a
    single-threaded arm on our side, and inferring it from a size threshold — the way `gemm.blocked`
    switches at 65536 cells — puts a thread-count discontinuity in the middle of a size sweep where a
    reader will mistake it for a kernel effect.
    """
    var nw = requested
    if nw <= 0:
        nw = info.num_physical_cores()
    if nw < 1:
        nw = 1
    if tasks < nw:
        nw = tasks
    if nw < 1:
        nw = 1
    return nw


def attn_forward_tiled(
    q: List[Float64], k: List[Float64], v: List[Float64],
    batch: Int, h_q: Int, h_kv: Int, s_q: Int, s_kv: Int, d: Int,
    scale: Float64, causal: Bool, br: Int, bc: Int, workers: Int
) -> AttnResult:
    """Grouped-query attention by blockwise online softmax. Intermediates are O(br*bc), not O(s^2).

    Layout is `[batch][head][seq][d]` row-major on all of Q, K, V and the output — the same contiguous
    order a (B, H, S, D) PyTorch tensor has, so a comparison against
    `torch.nn.functional.scaled_dot_product_attention` needs no transpose on either side and neither
    arm is charged a layout conversion the other avoids.

    @capability attn_forward_tiled
    complexity: O(batch*h_q*s_q*s_kv*d)
    counts:
    - batch * h_q * s_q * d == len(q) [kernel_validated]
    - batch * h_kv * s_kv * d == len(k) [kernel_validated]
    - batch * h_kv * s_kv * d == len(v) [kernel_validated]
    @endcapability
    """
    var empty = List[Float64]()
    var shape = attn_dims_check(batch, h_q, h_kv, s_q, s_kv, d)
    if shape != ATTN_OK:
        return AttnResult(
            empty^, 0, 0, ATTN_BACKEND_TILED, 0.0, 0.0, 0, 0.0, shape
        )
    if (
        len(q) < batch * h_q * s_q * d
        or len(k) < batch * h_kv * s_kv * d
        or len(v) < batch * h_kv * s_kv * d
    ):
        return AttnResult(
            empty^, 0, 0, ATTN_BACKEND_TILED, 0.0, 0.0, 0, 0.0,
            ATTN_ERR_LENGTH_MISMATCH,
        )
    if not attn_scale_ok(scale):
        return AttnResult(
            empty^, 0, 0, ATTN_BACKEND_TILED, 0.0, 0.0, 0, 0.0,
            ATTN_ERR_NON_FINITE_SCALE,
        )
    if causal and s_q != s_kv:
        return AttnResult(
            empty^, 0, 0, ATTN_BACKEND_TILED, 0.0, 0.0, 0, 0.0,
            ATTN_ERR_CAUSAL_SHAPE,
        )
    if br < 1 or bc < 1:
        return AttnResult(
            empty^, 0, 0, ATTN_BACKEND_TILED, 0.0, 0.0, 0, 0.0, ATTN_ERR_TILE
        )

    var pbr = br if br <= s_q else s_q
    var pbc = bc if bc <= s_kv else s_kv
    var n_row_blocks = (s_q + pbr - 1) // pbr
    var tasks = batch * h_q * n_row_blocks
    var n_workers = _workers_for(tasks, workers)

    var out = _zeros(batch * h_q * s_q * d)
    var maxlog = _zeros(n_workers)

    var qp = q.unsafe_ptr().as_unsafe_any_origin()
    var kp = k.unsafe_ptr().as_unsafe_any_origin()
    var vp = v.unsafe_ptr().as_unsafe_any_origin()
    var op = out.unsafe_ptr().as_unsafe_any_origin()
    var mlp = maxlog.unsafe_ptr().as_unsafe_any_origin()

    var group = h_q // h_kv
    var pd = d
    var ps_q = s_q
    var ps_kv = s_kv
    var ph_q = h_q
    var ph_kv = h_kv
    var pscale = scale
    var pcausal = causal
    var pnw = n_workers
    var pnrb = n_row_blocks
    var ptasks = tasks

    @parameter
    def band(tid: Int) capturing:
        # Scratch once per worker. Per task would put the allocator in the inner loop.
        var s_tile = _zeros(pbr * pbc)
        var acc = _zeros(pbr * pd)
        var m_run = _zeros(pbr)
        var l_run = _zeros(pbr)
        var sp = s_tile.unsafe_ptr().as_unsafe_any_origin()
        var ap = acc.unsafe_ptr().as_unsafe_any_origin()
        var mp = m_run.unsafe_ptr().as_unsafe_any_origin()
        var lp = l_run.unsafe_ptr().as_unsafe_any_origin()
        var local_max = 0.0

        var each = ptasks // pnw
        var lo = tid * each
        var hi = lo + each if tid < pnw - 1 else ptasks

        for task in range(lo, hi):
            var rb = task % pnrb
            var bh = task // pnrb
            var hq = bh % ph_q
            var bidx = bh // ph_q
            var hkv = hq // group

            var i0 = rb * pbr
            var br_eff = pbr
            if i0 + br_eff > ps_q:
                br_eff = ps_q - i0

            var q_base = ((bidx * ph_q + hq) * ps_q + i0) * pd
            var kv_base = ((bidx * ph_kv + hkv) * ps_kv) * pd
            var o_base = q_base

            for ii in range(br_eff):
                mp[ii] = NEG_BIG
                lp[ii] = 0.0
                var row = ii * pd
                for dd in range(pd):
                    ap[row + dd] = 0.0

            var j0 = 0
            while j0 < ps_kv:
                var bc_eff = pbc
                if j0 + bc_eff > ps_kv:
                    bc_eff = ps_kv - j0
                # A block strictly above the diagonal contributes nothing under a causal mask, so it
                # is skipped rather than computed and masked. Blocks are visited in increasing j0, so
                # once one is past the last query row in this block every later one is too.
                if pcausal and j0 > i0 + br_eff - 1:
                    break

                # Query rows are walked FOUR AT A TIME. Both microkernels below load one K (or V)
                # vector and feed four accumulators with it, which is the whole optimization: the
                # one-row-at-a-time version issues two loads per vector FMA and runs load-bound with
                # the FMA pipes idle. See `_dot4_simd`.
                var ii0 = 0
                while ii0 < br_eff:
                    var nr = 4
                    if ii0 + nr > br_eff:
                        nr = br_eff - ii0

                    # Widest column any row in this group needs. Under a causal mask the rows of a
                    # diagonal block need different widths; computing the group's widest for all four
                    # wastes a little arithmetic there and keeps the microkernel branch-free, and the
                    # extra cells are never READ because each row's softmax below uses its own jmax.
                    var jg = bc_eff
                    if pcausal:
                        var lim_g = (i0 + ii0 + nr - 1) - j0 + 1
                        if lim_g < jg:
                            jg = lim_g

                    if jg > 0:
                        if nr == 4:
                            # Key rows go FOUR at a time too where four remain. `_dot4x4_simd` loads
                            # four Q and four K vectors to feed sixteen FMAs, against `_dot4_simd`'s
                            # five loads for four; the leftover keys fall through to the 4x1 form.
                            var jj = 0
                            while jj + 4 <= jg:
                                var s16 = _dot4x4_simd(
                                    qp, kp, q_base + ii0 * pd, pd,
                                    kv_base + (j0 + jj) * pd, pd, pd,
                                )
                                for r in range(4):
                                    var srow = (ii0 + r) * pbc + jj
                                    for cc in range(4):
                                        var sc = s16[r * 4 + cc] * pscale
                                        sp[srow + cc] = sc
                                        var a = fabs(sc)
                                        if a > local_max:
                                            local_max = a
                                jj += 4
                            while jj < jg:
                                var s4 = _dot4_simd(
                                    qp, kp, q_base + ii0 * pd, pd,
                                    kv_base + (j0 + jj) * pd, pd,
                                )
                                for r in range(4):
                                    var sc = s4[r] * pscale
                                    sp[(ii0 + r) * pbc + jj] = sc
                                    var a = fabs(sc)
                                    if a > local_max:
                                        local_max = a
                                jj += 1
                        else:
                            for r in range(nr):
                                var q_off = q_base + (ii0 + r) * pd
                                var srow_r = (ii0 + r) * pbc
                                for jj in range(jg):
                                    var sc = (
                                        _dot_simd(
                                            qp, kp, q_off,
                                            kv_base + (j0 + jj) * pd, pd,
                                        )
                                        * pscale
                                    )
                                    sp[srow_r + jj] = sc
                                    var a = fabs(sc)
                                    if a > local_max:
                                        local_max = a

                    # Online softmax per row, and the accumulator rescale. Done for all rows of the
                    # group BEFORE the P@V below, so the blocked P@V sees four already-corrected
                    # accumulators and can stream V across them.
                    var uniform = True
                    for r in range(nr):
                        var ii = ii0 + r
                        var jmax = bc_eff
                        if pcausal:
                            var lim = (i0 + ii) - j0 + 1
                            if lim < jmax:
                                jmax = lim
                        if jmax != jg:
                            uniform = False
                        if jmax <= 0:
                            continue
                        var srow = ii * pbc
                        var tmax = NEG_BIG
                        for jj in range(jmax):
                            if sp[srow + jj] > tmax:
                                tmax = sp[srow + jj]
                        var m_old = mp[ii]
                        var m_new = m_old if m_old > tmax else tmax
                        var corr = exp(m_old - m_new)
                        var lsum = 0.0
                        for jj in range(jmax):
                            var p = exp(sp[srow + jj] - m_new)
                            sp[srow + jj] = p
                            lsum += p
                        lp[ii] = lp[ii] * corr + lsum
                        mp[ii] = m_new
                        if corr != 1.0:
                            _scale_simd(ap, ii * pd, pd, corr)

                    # P@V. Blocked when all four rows consume the same number of keys, which is every
                    # block except the diagonal ones under a causal mask.
                    if nr == 4 and uniform and jg > 0:
                        for jj in range(jg):
                            _axpy4_simd(
                                ap, vp, ii0 * pd, pd,
                                kv_base + (j0 + jj) * pd, pd,
                                sp[ii0 * pbc + jj], sp[(ii0 + 1) * pbc + jj],
                                sp[(ii0 + 2) * pbc + jj], sp[(ii0 + 3) * pbc + jj],
                            )
                    else:
                        for r in range(nr):
                            var ii = ii0 + r
                            var jmax = bc_eff
                            if pcausal:
                                var lim = (i0 + ii) - j0 + 1
                                if lim < jmax:
                                    jmax = lim
                            if jmax <= 0:
                                continue
                            var srow = ii * pbc
                            for jj in range(jmax):
                                _axpy_simd(
                                    ap, vp, ii * pd,
                                    kv_base + (j0 + jj) * pd, pd, sp[srow + jj],
                                )
                    ii0 += 4
                j0 += pbc

            for ii in range(br_eff):
                var denom = lp[ii]
                var inv = 0.0 if denom <= 0.0 else 1.0 / denom
                var arow = ii * pd
                var orow = o_base + ii * pd
                for dd in range(pd):
                    op[orow + dd] = ap[arow + dd] * inv

        mlp[tid] = local_max

    parallelize[band](n_workers)

    var global_max = 0.0
    for i in range(n_workers):
        if maxlog[i] > global_max:
            global_max = maxlog[i]

    return AttnResult(
        out^,
        batch * h_q * s_q,
        d,
        ATTN_BACKEND_TILED,
        attn_flop_count(batch, h_q, s_q, s_kv, d, causal),
        attn_ws_bytes_tiled(pbr, pbc, d),
        n_workers,
        global_max,
        ATTN_OK,
    )


def _forward_materialized(
    q: List[Float64], k: List[Float64], v: List[Float64],
    batch: Int, h_q: Int, h_kv: Int, s_q: Int, s_kv: Int, d: Int,
    scale: Float64, causal: Bool, subtract_max: Bool, workers: Int
) -> AttnResult:
    """Direct attention over a materialized s_q x s_kv score matrix per head.

    `subtract_max` False is the unstable diagnostic: same code path, `exp(score)` on raw logits. Kept
    as one function with a flag rather than two near-copies so the ONLY difference between the stable
    and unstable arms is provably the max subtraction and not an accidental divergence elsewhere.
    """
    var backend = ATTN_BACKEND_DIRECT if subtract_max else ATTN_BACKEND_UNSTABLE
    var empty = List[Float64]()
    var shape = attn_dims_check(batch, h_q, h_kv, s_q, s_kv, d)
    if shape != ATTN_OK:
        return AttnResult(empty^, 0, 0, backend, 0.0, 0.0, 0, 0.0, shape)
    if (
        len(q) < batch * h_q * s_q * d
        or len(k) < batch * h_kv * s_kv * d
        or len(v) < batch * h_kv * s_kv * d
    ):
        return AttnResult(
            empty^, 0, 0, backend, 0.0, 0.0, 0, 0.0, ATTN_ERR_LENGTH_MISMATCH
        )
    if not attn_scale_ok(scale):
        return AttnResult(
            empty^, 0, 0, backend, 0.0, 0.0, 0, 0.0, ATTN_ERR_NON_FINITE_SCALE
        )
    if causal and s_q != s_kv:
        return AttnResult(
            empty^, 0, 0, backend, 0.0, 0.0, 0, 0.0, ATTN_ERR_CAUSAL_SHAPE
        )

    var tasks = batch * h_q
    var n_workers = _workers_for(tasks, workers)
    # The quadratic allocation is refused, not attempted. See attnk.contract.
    if not attn_score_bytes_fit(s_q, s_kv, n_workers, ATTN_MAX_SCORE_BYTES):
        return AttnResult(
            empty^, 0, 0, backend,
            0.0, attn_ws_bytes_direct(s_q, s_kv, d), n_workers, 0.0,
            ATTN_ERR_SCORE_BYTES,
        )

    var out = _zeros(batch * h_q * s_q * d)
    var maxlog = _zeros(n_workers)
    var bad = _zeros(n_workers)

    var qp = q.unsafe_ptr().as_unsafe_any_origin()
    var kp = k.unsafe_ptr().as_unsafe_any_origin()
    var vp = v.unsafe_ptr().as_unsafe_any_origin()
    var op = out.unsafe_ptr().as_unsafe_any_origin()
    var mlp = maxlog.unsafe_ptr().as_unsafe_any_origin()
    var badp = bad.unsafe_ptr().as_unsafe_any_origin()

    var group = h_q // h_kv
    var pd = d
    var ps_q = s_q
    var ps_kv = s_kv
    var ph_q = h_q
    var ph_kv = h_kv
    var pscale = scale
    var pcausal = causal
    var psub = subtract_max
    var pnw = n_workers
    var ptasks = tasks

    @parameter
    def band(tid: Int) capturing:
        var scores = _zeros(ps_q * ps_kv)
        var sp = scores.unsafe_ptr().as_unsafe_any_origin()
        var local_max = 0.0
        var local_bad = 0.0

        var each = ptasks // pnw
        var lo = tid * each
        var hi = lo + each if tid < pnw - 1 else ptasks

        for task in range(lo, hi):
            var hq = task % ph_q
            var bidx = task // ph_q
            var hkv = hq // group
            var q_base = ((bidx * ph_q + hq) * ps_q) * pd
            var kv_base = ((bidx * ph_kv + hkv) * ps_kv) * pd

            # Full score matrix first. This is the allocation the tiled kernel does not make.
            for i in range(ps_q):
                var jmax = ps_kv
                if pcausal and i + 1 < jmax:
                    jmax = i + 1
                var q_off = q_base + i * pd
                var srow = i * ps_kv
                for j in range(jmax):
                    var sc = (
                        _dot_simd(qp, kp, q_off, kv_base + j * pd, pd) * pscale
                    )
                    sp[srow + j] = sc
                    var a = fabs(sc)
                    if a > local_max:
                        local_max = a

            for i in range(ps_q):
                var jmax = ps_kv
                if pcausal and i + 1 < jmax:
                    jmax = i + 1
                var srow = i * ps_kv
                var shift = 0.0
                if psub:
                    var rmax = NEG_BIG
                    for j in range(jmax):
                        if sp[srow + j] > rmax:
                            rmax = sp[srow + j]
                    shift = rmax
                var denom = 0.0
                for j in range(jmax):
                    var p = exp(sp[srow + j] - shift)
                    sp[srow + j] = p
                    denom += p
                var orow = q_base + i * pd
                for dd in range(pd):
                    op[orow + dd] = 0.0
                var inv = 0.0
                if denom > 0.0 and not isinf(denom) and not isnan(denom):
                    inv = 1.0 / denom
                else:
                    local_bad = 1.0
                for j in range(jmax):
                    _axpy_simd(
                        op, vp, orow, kv_base + j * pd, pd, sp[srow + j]
                    )
                for dd in range(pd):
                    var ov = op[orow + dd] * inv
                    if isnan(ov) or isinf(ov):
                        local_bad = 1.0
                    op[orow + dd] = ov

        mlp[tid] = local_max
        badp[tid] = local_bad

    parallelize[band](n_workers)

    var global_max = 0.0
    var any_bad = False
    for i in range(n_workers):
        if maxlog[i] > global_max:
            global_max = maxlog[i]
        if bad[i] != 0.0:
            any_bad = True

    var st = ATTN_ERR_OVERFLOW if any_bad else ATTN_OK
    return AttnResult(
        out^,
        batch * h_q * s_q,
        d,
        backend,
        attn_flop_count(batch, h_q, s_q, s_kv, d, causal),
        attn_ws_bytes_direct(s_q, s_kv, d),
        n_workers,
        global_max,
        st,
    )


def attn_forward_direct(
    q: List[Float64], k: List[Float64], v: List[Float64],
    batch: Int, h_q: Int, h_kv: Int, s_q: Int, s_kv: Int, d: Int,
    scale: Float64, causal: Bool, workers: Int
) -> AttnResult:
    """Attention over a materialized score matrix, row-max subtracted. O(s_q*s_kv) intermediates.

    @capability attn_forward_direct
    complexity: O(batch*h_q*s_q*s_kv*d)
    counts:
    - batch * h_q * s_q * d == len(q) [kernel_validated]
    - batch * h_kv * s_kv * d == len(k) [kernel_validated]
    - batch * h_kv * s_kv * d == len(v) [kernel_validated]
    @endcapability
    """
    return _forward_materialized(
        q, k, v, batch, h_q, h_kv, s_q, s_kv, d, scale, causal, True, workers
    )


def attn_forward_unstable(
    q: List[Float64], k: List[Float64], v: List[Float64],
    batch: Int, h_q: Int, h_kv: Int, s_q: Int, s_kv: Int, d: Int,
    scale: Float64, causal: Bool, workers: Int
) -> AttnResult:
    """Deliberately unstable: exp() of raw logits, no max subtraction. Returns ATTN_ERR_OVERFLOW.

    Exists to be shown failing where the two real kernels are exact. Never timed as a competitor.

    @capability attn_forward_unstable
    complexity: O(batch*h_q*s_q*s_kv*d)
    counts:
    - batch * h_q * s_q * d == len(q) [kernel_validated]
    - batch * h_kv * s_kv * d == len(k) [kernel_validated]
    - batch * h_kv * s_kv * d == len(v) [kernel_validated]
    @endcapability
    """
    return _forward_materialized(
        q, k, v, batch, h_q, h_kv, s_q, s_kv, d, scale, causal, False, workers
    )


def attn_reference_delta(
    q: List[Float64], k: List[Float64], v: List[Float64],
    batch: Int, h_q: Int, h_kv: Int, s_q: Int, s_kv: Int, d: Int,
    scale: Float64, causal: Bool
) -> AttnDelta:
    """Tiled against direct, elementwise, judged by the per-element tolerance `tensorx` derives.

    Not an equality assertion, because equality would be false: the two kernels sum the same products
    in different orders and float addition is not associative. `dtx_tol_for` builds the bound from
    each element's own magnitude, which is the only defensible standard for two summation orders of
    the same quantity.

    @capability attn_reference_delta
    complexity: O(batch*h_q*s_q*s_kv*d)
    counts:
    - batch * h_q * s_q * d == len(q) [kernel_validated]
    - batch * h_kv * s_kv * d == len(k) [kernel_validated]
    - batch * h_kv * s_kv * d == len(v) [kernel_validated]
    @endcapability
    """
    var a = attn_forward_tiled(
        q, k, v, batch, h_q, h_kv, s_q, s_kv, d, scale, causal,
        BR_DEFAULT, BC_DEFAULT, 0,
    )
    if a.status != ATTN_OK:
        return AttnDelta(0.0, 0.0, 0.0, False, 0, a.status)
    var b = attn_forward_direct(
        q, k, v, batch, h_q, h_kv, s_q, s_kv, d, scale, causal, 0
    )
    if b.status != ATTN_OK:
        return AttnDelta(0.0, 0.0, 0.0, False, 0, b.status)

    var n = len(a.out)
    if n != len(b.out) or n == 0:
        return AttnDelta(0.0, 0.0, 0.0, False, 0, ATTN_ERR_Q_LENGTH)

    # The absolute term is a summation-order bound, not a guess. Both kernels compute the same
    # o_i = sum_j p_j v_j with sum_j p_j = 1, in different orders. The standard bound on the
    # difference between two orderings of an n-term sum is gamma_n = n*eps/(1 - n*eps) times the sum
    # of the absolute terms, which is at most gamma_n * max|v|. Using dtx_tol_for's relative term
    # ALONE here would be the rule-4b defect in its tightest form: eps*|o_i| for a sum of 8192 terms
    # is roughly s_kv times too small, and a passing result would then be luck.
    var vmax = 0.0
    for i in range(len(v)):
        var av = fabs(v[i])
        if av > vmax:
            vmax = av
    var eps64 = 2.220446049250313e-16
    var neps = Float64(s_kv) * eps64
    var gamma = neps / (1.0 - neps) if neps < 0.5 else 1.0
    var abs_bound = gamma * vmax

    var max_abs = 0.0
    var max_rel = 0.0
    var tol_at_max = 0.0
    var ok = True
    for i in range(n):
        var delta = fabs(a.out[i] - b.out[i])
        var tol = dtx_tol_for(b.out[i], DT_F64, abs_bound).value
        if delta > tol:
            ok = False
        if delta > max_abs:
            max_abs = delta
            tol_at_max = tol
        var mag = fabs(b.out[i])
        if mag > 0.0:
            var rel = delta / mag
            if rel > max_rel:
                max_rel = rel
    return AttnDelta(max_abs, max_rel, tol_at_max, ok, n, ATTN_OK)
