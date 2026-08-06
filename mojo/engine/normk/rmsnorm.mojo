"""
normk.rmsnorm — tensorized RMSNorm, forward and backward, over flat row-major buffers. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_normk_rmsnorm.mojo
benchmark: benchmarks/mojo_benchmarks/bench_normk.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

What this adds to the frozen kernel, and what it does not
-----------------------------------------------------------
`normalization_layers.rms_norm(x, rms, gamma, eps)` is one element: `x / sqrt(rms^2 + eps) * gamma`.
It takes the row's RMS as an ARGUMENT, so the reduction — the part that has an axis to get wrong, a
width to overflow and an order that decides reproducibility — was always the caller's. That reduction
is what this module is. The per-element arithmetic stays the frozen kernel's (rule 3):
`rmsnorm_agrees_with_frozen_flat` re-derives the whole output through it and reports the delta, so
the claim is measured on every run rather than asserted here.

The backward pass is the reason this exists at all
----------------------------------------------------
A forward-only norm looks perfect in inference and silently produces a worse model in training. With
`ms = mean(x^2) + eps` and `r = ms^(-1/2)`:

    y_j  = x_j * r * g_j
    dx_j = r * (g_j * dy_j) - x_j * r^3 * SUM_k(dy_k * g_k * x_k) / n
    dg_j = SUM_rows(dy_ij * x_ij * r_i)

The second term of `dx` is the one that gets dropped. Without it the gradient is still finite, still
plausibly scaled, and still wrong — every row would be treated as if its own RMS did not depend on
the element being differentiated. `rmsnorm_gradcheck_flat` exists to make that a measured number
against central differences rather than a reviewer's reading of the algebra.

Reduction order is fixed, so a result does not move with thread count
-----------------------------------------------------------------------
`dx` is row-parallel and every element is independent. `dgamma` reduces ACROSS rows, so it is
parallelized over COLUMNS instead — each worker owns whole columns and sums them in row order. Doing
it the obvious way, one worker per row accumulating into a shared `dgamma`, is both a race and
non-deterministic even when it is locked. The determinism promise is per-backend, and this is what
holds up its "same answer regardless of thread count" half.

Public API:
  rmsnorm_fwd_flat(x, gamma, n_rows, n_cols, eps)                  -> NormOut
  rmsnorm_bwd_flat(dy, x, gamma, rstd, n_rows, n_cols)             -> NormGrad
  rmsnorm_agrees_with_frozen_flat(x, gamma, n_rows, n_cols, eps)   -> NormAgreement
  rmsnorm_gradcheck_flat(x, gamma, n_rows, n_cols, eps, step)      -> NormAgreement
"""

from std.algorithm import parallelize
from std.math import sqrt
from std.sys.info import num_physical_cores
from normalization_layers import rms_norm
from normk.contract import (
    NORM_ERR_LENGTH_MISMATCH,
    NORM_OK,
    norm_dims_check,
    norm_tol_for,
)
from tensorx.contract import tx_finite

comptime PARALLEL_MIN_CELLS: Int = 1 << 15
"""Below ~32k cells, run single-threaded — `parallelize` costs more to fan out and join than a small
norm costs to compute. Same reasoning, and the same measured shape, as `gemm.blocked`."""


@fieldwise_init
struct NormOut(Copyable, Movable):
    """Normalized activations plus the per-row reciprocal deviation the backward pass needs.

    `rstd` is returned rather than recomputed later on purpose. Recomputing it in the backward pass
    would re-derive it from `x`, and any difference between the two derivations — a different
    reduction order is enough — makes the analytic gradient disagree with the forward that produced
    it, by an amount too small to notice and large enough to bias training."""

    var y: List[Float64]
    var rstd: List[Float64]
    var n_rows: Int
    var n_cols: Int
    var status: Int


@fieldwise_init
struct NormGrad(Copyable, Movable):
    """Gradients with respect to the input and the scale vector."""

    var dx: List[Float64]
    var dgamma: List[Float64]
    var n_rows: Int
    var n_cols: Int
    var status: Int


@fieldwise_init
struct NormAgreement(Copyable, Movable):
    """How far two spellings of the same quantity are apart, and how far they are allowed to be."""

    var max_abs_delta: Float64
    var tolerance_at_max: Float64
    var within_tolerance: Bool
    var n_compared: Int
    var status: Int


def rmsnorm_fwd_flat(
    x: List[Float64], gamma: List[Float64], n_rows: Int, n_cols: Int, eps: Float64
) -> NormOut:
    """RMSNorm over `[n_rows][n_cols]` row-major, scaled by a shared `gamma` of length `n_cols`.

    @capability rmsnorm_fwd_flat
    complexity: O(n_rows * n_cols)
    counts:
    - n_rows * n_cols <= len(x) [enforced]
    - n_cols <= len(gamma) [enforced]
    @endcapability
    """
    var y = List[Float64]()
    var rstd = List[Float64]()
    var shape = norm_dims_check(n_rows, n_cols, eps)
    if shape != NORM_OK:
        return NormOut(y^, rstd^, 0, 0, shape)
    if len(x) < n_rows * n_cols or len(gamma) < n_cols:
        return NormOut(y^, rstd^, 0, 0, NORM_ERR_LENGTH_MISMATCH)

    for _ in range(n_rows * n_cols):
        y.append(0.0)
    for _ in range(n_rows):
        rstd.append(0.0)

    var xp = x.unsafe_ptr()
    var gp = gamma.unsafe_ptr()
    var yp = y.unsafe_ptr()
    var rp = rstd.unsafe_ptr()
    var rows = n_rows
    var cols = n_cols
    var e = eps
    var workers = num_physical_cores()
    if n_rows * n_cols < PARALLEL_MIN_CELLS or workers > n_rows:
        workers = 1

    @parameter
    def _row_band(tid: Int) capturing:
        var each = rows // workers
        var lo = tid * each
        var hi = lo + each if tid < workers - 1 else rows
        for i in range(lo, hi):
            var base = i * cols
            # Four independent accumulators: the sum of squares is a serial dependence chain
            # otherwise, and one add's latency then sets the loop's throughput (see gemm.blocked).
            var s0 = 0.0
            var s1 = 0.0
            var s2 = 0.0
            var s3 = 0.0
            var j = 0
            while j + 4 <= cols:
                var v0 = xp[base + j]
                var v1 = xp[base + j + 1]
                var v2 = xp[base + j + 2]
                var v3 = xp[base + j + 3]
                s0 += v0 * v0
                s1 += v1 * v1
                s2 += v2 * v2
                s3 += v3 * v3
                j += 4
            while j < cols:
                var v = xp[base + j]
                s0 += v * v
                j += 1
            var mean_sq = (s0 + s1 + s2 + s3) / Float64(cols)
            # The frozen kernel squares what it is handed, so it wants the RMS, not the mean square.
            var row_rms = sqrt(mean_sq)
            rp[i] = 1.0 / sqrt(mean_sq + e)
            for c in range(cols):
                yp[base + c] = rms_norm(xp[base + c], row_rms, gp[c], e)

    parallelize[_row_band](workers)

    return NormOut(y^, rstd^, n_rows, n_cols, NORM_OK)


def rmsnorm_bwd_flat(
    dy: List[Float64], x: List[Float64], gamma: List[Float64], rstd: List[Float64],
    n_rows: Int, n_cols: Int
) -> NormGrad:
    """Gradients of RMSNorm, given the `rstd` the matching forward returned.

    @capability rmsnorm_bwd_flat
    complexity: O(n_rows * n_cols)
    counts:
    - n_rows * n_cols <= len(dy, x) [enforced]
    - n_cols <= len(gamma) [enforced]
    - n_rows <= len(rstd) [enforced]
    @endcapability
    """
    var dx = List[Float64]()
    var dgamma = List[Float64]()
    var shape = norm_dims_check(n_rows, n_cols, 0.0)
    if shape != NORM_OK:
        return NormGrad(dx^, dgamma^, 0, 0, shape)
    if len(dy) < n_rows * n_cols or len(x) < n_rows * n_cols:
        return NormGrad(dx^, dgamma^, 0, 0, NORM_ERR_LENGTH_MISMATCH)
    if len(gamma) < n_cols or len(rstd) < n_rows:
        return NormGrad(dx^, dgamma^, 0, 0, NORM_ERR_LENGTH_MISMATCH)

    for _ in range(n_rows * n_cols):
        dx.append(0.0)
    for _ in range(n_cols):
        dgamma.append(0.0)

    var dyp = dy.unsafe_ptr()
    var xp = x.unsafe_ptr()
    var gp = gamma.unsafe_ptr()
    var rp = rstd.unsafe_ptr()
    var dxp = dx.unsafe_ptr()
    var dgp = dgamma.unsafe_ptr()
    var rows = n_rows
    var cols = n_cols
    var inv_n = 1.0 / Float64(n_cols)
    var workers = num_physical_cores()
    if n_rows * n_cols < PARALLEL_MIN_CELLS or workers > n_rows:
        workers = 1

    @parameter
    def _dx_band(tid: Int) capturing:
        var each = rows // workers
        var lo = tid * each
        var hi = lo + each if tid < workers - 1 else rows
        for i in range(lo, hi):
            var base = i * cols
            var r = rp[i]
            var dot = 0.0
            for c in range(cols):
                dot += dyp[base + c] * gp[c] * xp[base + c]
            var scaled = dot * r * r * r * inv_n
            for c in range(cols):
                dxp[base + c] = r * gp[c] * dyp[base + c] - xp[base + c] * scaled

    parallelize[_dx_band](workers)

    # dgamma reduces ACROSS rows, so it is split by column, not by row: each worker owns whole
    # columns and walks them in row order. Splitting by row would need a shared accumulator, which is
    # a race, and a locked one would still sum in whatever order the threads arrived.
    var gworkers = num_physical_cores()
    if n_rows * n_cols < PARALLEL_MIN_CELLS or gworkers > n_cols:
        gworkers = 1

    @parameter
    def _dgamma_band(tid: Int) capturing:
        var each = cols // gworkers
        var lo = tid * each
        var hi = lo + each if tid < gworkers - 1 else cols
        for c in range(lo, hi):
            var total = 0.0
            for i in range(rows):
                total += dyp[i * cols + c] * xp[i * cols + c] * rp[i]
            dgp[c] = total

    parallelize[_dgamma_band](gworkers)

    return NormGrad(dx^, dgamma^, n_rows, n_cols, NORM_OK)


def rmsnorm_agrees_with_frozen_flat(
    x: List[Float64], gamma: List[Float64], n_rows: Int, n_cols: Int, eps: Float64
) -> NormAgreement:
    """Re-derive the forward one element at a time through the frozen kernel and report the delta.

    Rule 3 evidence, measured rather than claimed. The tiled forward calls `rms_norm` too, so this is
    not asking whether the formula matches — it is asking whether the REDUCTION feeding it does, since
    that is the part this module owns and the part a blocked or vectorized rewrite would change.

    @capability rmsnorm_agrees_with_frozen_flat
    complexity: O(n_rows * n_cols)
    counts:
    - n_rows * n_cols <= len(x) [enforced]
    - n_cols <= len(gamma) [enforced]
    @endcapability
    """
    var shape = norm_dims_check(n_rows, n_cols, eps)
    if shape != NORM_OK:
        return NormAgreement(0.0, 0.0, False, 0, shape)
    if len(x) < n_rows * n_cols or len(gamma) < n_cols:
        return NormAgreement(0.0, 0.0, False, 0, NORM_ERR_LENGTH_MISMATCH)

    var fast = rmsnorm_fwd_flat(x, gamma, n_rows, n_cols, eps)
    if fast.status != NORM_OK:
        return NormAgreement(0.0, 0.0, False, 0, fast.status)

    var worst = 0.0
    var tol_at_worst = 0.0
    for i in range(n_rows):
        var base = i * n_cols
        var total = 0.0
        for c in range(n_cols):
            total += x[base + c] * x[base + c]
        var row_rms = sqrt(total / Float64(n_cols))
        for c in range(n_cols):
            var expected = rms_norm(x[base + c], row_rms, gamma[c], eps)
            var delta = fast.y[base + c] - expected
            if delta < 0.0:
                delta = -delta
            if delta > worst:
                worst = delta
                tol_at_worst = norm_tol_for(expected, n_cols)

    if tol_at_worst == 0.0:
        tol_at_worst = norm_tol_for(0.0, n_cols)
    return NormAgreement(worst, tol_at_worst, worst <= tol_at_worst, n_rows * n_cols, NORM_OK)


def rmsnorm_gradcheck_flat(
    x: List[Float64], gamma: List[Float64], n_rows: Int, n_cols: Int,
    eps: Float64, step: Float64
) -> NormAgreement:
    """Compare the analytic `dx` against central differences of `sum(y)`, worst element.

    `dy` is all ones, so the quantity differentiated is `SUM(y)` and every analytic term is exercised
    — including the `x_j * r^3 * SUM(...)` coupling that a forward-only reading of the kernel would
    drop. A per-element `dy` of zero would hide it.

    The tolerance is deliberately loose relative to the rest of this package. A central difference
    carries truncation error `O(step^2 * |f'''|)` and cancellation error `O(machine_eps * |f| / step)`
    pulling in opposite directions, so the achievable accuracy is bounded well above the forward
    kernel's — around `step^2` at best. Judging a gradcheck by a forward tolerance is rule 4b's
    second spelling and produces a gate that fails on correct code.

    @capability rmsnorm_gradcheck_flat
    complexity: O(n_rows * n_cols * n_cols)
    counts:
    - n_rows * n_cols <= len(x) [enforced]
    - n_cols <= len(gamma) [enforced]
    @endcapability
    """
    var shape = norm_dims_check(n_rows, n_cols, eps)
    if shape != NORM_OK:
        return NormAgreement(0.0, 0.0, False, 0, shape)
    if len(x) < n_rows * n_cols or len(gamma) < n_cols:
        return NormAgreement(0.0, 0.0, False, 0, NORM_ERR_LENGTH_MISMATCH)
    if not tx_finite(step) or step <= 0.0:
        return NormAgreement(0.0, 0.0, False, 0, NORM_ERR_LENGTH_MISMATCH)

    var fwd = rmsnorm_fwd_flat(x, gamma, n_rows, n_cols, eps)
    if fwd.status != NORM_OK:
        return NormAgreement(0.0, 0.0, False, 0, fwd.status)

    var ones = List[Float64](capacity=n_rows * n_cols)
    for _ in range(n_rows * n_cols):
        ones.append(1.0)
    var grad = rmsnorm_bwd_flat(ones, x, gamma, fwd.rstd, n_rows, n_cols)
    if grad.status != NORM_OK:
        return NormAgreement(0.0, 0.0, False, 0, grad.status)

    var probe = List[Float64](capacity=n_rows * n_cols)
    for idx in range(n_rows * n_cols):
        probe.append(x[idx])

    var worst = 0.0
    var tol_at_worst = 0.0
    for idx in range(n_rows * n_cols):
        var original = probe[idx]
        probe[idx] = original + step
        var up = _sum_of_forward(probe, gamma, n_rows, n_cols, eps)
        probe[idx] = original - step
        var down = _sum_of_forward(probe, gamma, n_rows, n_cols, eps)
        probe[idx] = original

        var numeric = (up - down) / (2.0 * step)
        var delta = grad.dx[idx] - numeric
        if delta < 0.0:
            delta = -delta
        # Scaled by the gradient's own magnitude, plus the floor the difference quotient cannot beat.
        var mag = numeric if numeric >= 0.0 else -numeric
        var tol = step * step * (1.0 + mag) + 1.0e-9 * (1.0 + mag)
        if delta > worst:
            worst = delta
            tol_at_worst = tol

    if tol_at_worst == 0.0:
        tol_at_worst = 1.0e-9
    return NormAgreement(worst, tol_at_worst, worst <= tol_at_worst, n_rows * n_cols, NORM_OK)


def _sum_of_forward(
    x: List[Float64], gamma: List[Float64], n_rows: Int, n_cols: Int, eps: Float64
) -> Float64:
    """`SUM(y)` for one perturbed input. Underscore-prefixed: a gradcheck helper, not a kernel."""
    var out = rmsnorm_fwd_flat(x, gamma, n_rows, n_cols, eps)
    if out.status != NORM_OK:
        return 0.0
    var total = 0.0
    for idx in range(n_rows * n_cols):
        total += out.y[idx]
    return total
