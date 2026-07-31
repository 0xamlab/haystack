"""
normk.layernorm — tensorized LayerNorm, forward and backward, over flat row-major buffers. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_normk_layernorm.mojo
benchmark: benchmarks/mojo_benchmarks/bench_normk.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Why the variance is computed in two passes and not one
--------------------------------------------------------
The one-pass identity `var = mean(x^2) - mean(x)^2` is a real temptation: it fuses both reductions
into a single walk of the row. It is also catastrophically cancelling. For a row whose values sit far
from zero — which is exactly what a residual stream looks like after a few blocks — the two terms
agree to most of their significant digits and the difference keeps only the noise. It can return a
NEGATIVE variance, at which point `sqrt` yields NaN and the whole model output is NaN from a kernel
that "worked".

So the mean is computed first, then the squared deviations from it. That is two passes over a row
that is already in L1 after the first, which is a much smaller cost than the accuracy it buys.
`layernorm_variance_agrees_flat` reports the gap between the two formulas on real input, so the
choice is a measured number rather than folklore.

What the frozen kernel supplies
---------------------------------
`normalization_layers.layer_norm(x, mean, variance, gamma, beta, eps)` is the per-element formula and
it is called unchanged (rule 3). It takes mean and variance as ARGUMENTS — the reductions, the axis
they run along, and their numerical conditioning were always the caller's problem, and that is the
part this module is.

Public API:
  layernorm_fwd_flat(x, gamma, beta, n_rows, n_cols, eps)               -> LayerNormOut
  layernorm_bwd_flat(dy, x, gamma, mean, rstd, n_rows, n_cols)          -> LayerNormGrad
  layernorm_variance_agrees_flat(x, n_rows, n_cols)                     -> LayerNormAgreement
  layernorm_gradcheck_flat(x, gamma, beta, n_rows, n_cols, eps, step)   -> LayerNormAgreement
"""

from std.algorithm import parallelize
from std.math import sqrt
from std.sys.info import num_physical_cores
from normalization_layers import layer_norm
from normk.contract import (
    NORM_ERR_LENGTH_MISMATCH,
    NORM_OK,
    norm_dims_check,
    norm_tol_for,
)
from tensorx.contract import tx_finite

comptime PARALLEL_MIN_CELLS: Int = 1 << 15
"""Below ~32k cells the fan-out costs more than the norm. Same threshold and reasoning as
`normk.rmsnorm` and `gemm.blocked`."""


@fieldwise_init
struct LayerNormOut(Copyable, Movable):
    """Normalized activations plus the per-row statistics the backward pass consumes."""

    var y: List[Float64]
    var mean: List[Float64]
    var rstd: List[Float64]
    var n_rows: Int
    var n_cols: Int
    var status: Int


@fieldwise_init
struct LayerNormGrad(Copyable, Movable):
    """Gradients with respect to the input, the scale and the shift."""

    var dx: List[Float64]
    var dgamma: List[Float64]
    var dbeta: List[Float64]
    var n_rows: Int
    var n_cols: Int
    var status: Int


@fieldwise_init
struct LayerNormAgreement(Copyable, Movable):
    """How far two spellings of the same quantity are apart, and how far they are allowed to be."""

    var max_abs_delta: Float64
    var tolerance_at_max: Float64
    var within_tolerance: Bool
    var n_compared: Int
    var status: Int


fn layernorm_fwd_flat(
    x: List[Float64], gamma: List[Float64], beta: List[Float64],
    n_rows: Int, n_cols: Int, eps: Float64
) -> LayerNormOut:
    """LayerNorm over `[n_rows][n_cols]` row-major, with shared `gamma` and `beta` of length `n_cols`.

    @capability layernorm_fwd_flat
    complexity: O(n_rows * n_cols)
    counts:
    - n_rows * n_cols <= len(x) [enforced]
    - n_cols <= len(gamma, beta) [enforced]
    @endcapability
    """
    var y = List[Float64]()
    var mean = List[Float64]()
    var rstd = List[Float64]()
    var shape = norm_dims_check(n_rows, n_cols, eps)
    if shape != NORM_OK:
        return LayerNormOut(y^, mean^, rstd^, 0, 0, shape)
    if len(x) < n_rows * n_cols or len(gamma) < n_cols or len(beta) < n_cols:
        return LayerNormOut(y^, mean^, rstd^, 0, 0, NORM_ERR_LENGTH_MISMATCH)

    for _ in range(n_rows * n_cols):
        y.append(0.0)
    for _ in range(n_rows):
        mean.append(0.0)
        rstd.append(0.0)

    var xp = x.unsafe_ptr()
    var gp = gamma.unsafe_ptr()
    var bp = beta.unsafe_ptr()
    var yp = y.unsafe_ptr()
    var mp = mean.unsafe_ptr()
    var rp = rstd.unsafe_ptr()
    var rows = n_rows
    var cols = n_cols
    var e = eps
    var inv_n = 1.0 / Float64(n_cols)
    var workers = num_physical_cores()
    if n_rows * n_cols < PARALLEL_MIN_CELLS or workers > n_rows:
        workers = 1

    @parameter
    fn _row_band(tid: Int) capturing:
        var each = rows // workers
        var lo = tid * each
        var hi = lo + each if tid < workers - 1 else rows
        for i in range(lo, hi):
            var base = i * cols
            # Pass 1: the mean. Four accumulators so the adds are not one dependence chain.
            var s0 = 0.0
            var s1 = 0.0
            var s2 = 0.0
            var s3 = 0.0
            var j = 0
            while j + 4 <= cols:
                s0 += xp[base + j]
                s1 += xp[base + j + 1]
                s2 += xp[base + j + 2]
                s3 += xp[base + j + 3]
                j += 4
            while j < cols:
                s0 += xp[base + j]
                j += 1
            var mu = (s0 + s1 + s2 + s3) * inv_n

            # Pass 2: squared deviations FROM THAT MEAN, never `mean(x^2) - mu^2`.
            var d0 = 0.0
            var d1 = 0.0
            var d2 = 0.0
            var d3 = 0.0
            j = 0
            while j + 4 <= cols:
                var t0 = xp[base + j] - mu
                var t1 = xp[base + j + 1] - mu
                var t2 = xp[base + j + 2] - mu
                var t3 = xp[base + j + 3] - mu
                d0 += t0 * t0
                d1 += t1 * t1
                d2 += t2 * t2
                d3 += t3 * t3
                j += 4
            while j < cols:
                var t = xp[base + j] - mu
                d0 += t * t
                j += 1
            var variance = (d0 + d1 + d2 + d3) * inv_n

            mp[i] = mu
            rp[i] = 1.0 / sqrt(variance + e)
            for c in range(cols):
                yp[base + c] = layer_norm(xp[base + c], mu, variance, gp[c], bp[c], e)

    parallelize[_row_band](workers)

    return LayerNormOut(y^, mean^, rstd^, n_rows, n_cols, NORM_OK)


fn layernorm_bwd_flat(
    dy: List[Float64], x: List[Float64], gamma: List[Float64],
    mean: List[Float64], rstd: List[Float64], n_rows: Int, n_cols: Int
) -> LayerNormGrad:
    """Gradients of LayerNorm, given the `mean` and `rstd` the matching forward returned.

    With `xhat = (x - mu) * rstd` and `dxhat = dy * gamma`:

        dx = rstd * (dxhat - mean(dxhat) - xhat * mean(dxhat * xhat))

    Both correction terms are load-bearing. Dropping the first ignores that shifting one element
    moves the row's mean; dropping the second ignores that it moves the row's variance. Either
    omission still yields finite, plausibly scaled gradients — which is why `layernorm_gradcheck_flat`
    exists rather than a reading of the algebra.

    @capability layernorm_bwd_flat
    complexity: O(n_rows * n_cols)
    counts:
    - n_rows * n_cols <= len(dy, x) [enforced]
    - n_cols <= len(gamma) [enforced]
    - n_rows <= len(mean, rstd) [enforced]
    @endcapability
    """
    var dx = List[Float64]()
    var dgamma = List[Float64]()
    var dbeta = List[Float64]()
    var shape = norm_dims_check(n_rows, n_cols, 0.0)
    if shape != NORM_OK:
        return LayerNormGrad(dx^, dgamma^, dbeta^, 0, 0, shape)
    if len(dy) < n_rows * n_cols or len(x) < n_rows * n_cols or len(gamma) < n_cols:
        return LayerNormGrad(dx^, dgamma^, dbeta^, 0, 0, NORM_ERR_LENGTH_MISMATCH)
    if len(mean) < n_rows or len(rstd) < n_rows:
        return LayerNormGrad(dx^, dgamma^, dbeta^, 0, 0, NORM_ERR_LENGTH_MISMATCH)

    for _ in range(n_rows * n_cols):
        dx.append(0.0)
    for _ in range(n_cols):
        dgamma.append(0.0)
        dbeta.append(0.0)

    var dyp = dy.unsafe_ptr()
    var xp = x.unsafe_ptr()
    var gp = gamma.unsafe_ptr()
    var mp = mean.unsafe_ptr()
    var rp = rstd.unsafe_ptr()
    var dxp = dx.unsafe_ptr()
    var dgp = dgamma.unsafe_ptr()
    var dbp = dbeta.unsafe_ptr()
    var rows = n_rows
    var cols = n_cols
    var inv_n = 1.0 / Float64(n_cols)
    var workers = num_physical_cores()
    if n_rows * n_cols < PARALLEL_MIN_CELLS or workers > n_rows:
        workers = 1

    @parameter
    fn _dx_band(tid: Int) capturing:
        var each = rows // workers
        var lo = tid * each
        var hi = lo + each if tid < workers - 1 else rows
        for i in range(lo, hi):
            var base = i * cols
            var mu = mp[i]
            var r = rp[i]
            var sum_dxhat = 0.0
            var sum_dxhat_xhat = 0.0
            for c in range(cols):
                var xhat = (xp[base + c] - mu) * r
                var dxhat = dyp[base + c] * gp[c]
                sum_dxhat += dxhat
                sum_dxhat_xhat += dxhat * xhat
            var mean_dxhat = sum_dxhat * inv_n
            var mean_dxhat_xhat = sum_dxhat_xhat * inv_n
            for c in range(cols):
                var xhat = (xp[base + c] - mu) * r
                var dxhat = dyp[base + c] * gp[c]
                dxp[base + c] = r * (dxhat - mean_dxhat - xhat * mean_dxhat_xhat)

    parallelize[_dx_band](workers)

    # dgamma and dbeta reduce across ROWS, so they are split by column and summed in row order —
    # parallel and order-stable at once. See the same split in `normk.rmsnorm`.
    var gworkers = num_physical_cores()
    if n_rows * n_cols < PARALLEL_MIN_CELLS or gworkers > n_cols:
        gworkers = 1

    @parameter
    fn _param_band(tid: Int) capturing:
        var each = cols // gworkers
        var lo = tid * each
        var hi = lo + each if tid < gworkers - 1 else cols
        for c in range(lo, hi):
            var g_total = 0.0
            var b_total = 0.0
            for i in range(rows):
                var d = dyp[i * cols + c]
                g_total += d * (xp[i * cols + c] - mp[i]) * rp[i]
                b_total += d
            dgp[c] = g_total
            dbp[c] = b_total

    parallelize[_param_band](gworkers)

    return LayerNormGrad(dx^, dgamma^, dbeta^, n_rows, n_cols, NORM_OK)


fn layernorm_variance_agrees_flat(
    x: List[Float64], n_rows: Int, n_cols: Int
) -> LayerNormAgreement:
    """Measure the one-pass variance identity against the two-pass one, worst row.

    Reports how far `mean(x^2) - mean(x)^2` drifts from `mean((x - mu)^2)` on the caller's own data.
    On values near zero the two agree to the last bit and this returns ~0; on an offset row it can
    return a delta larger than the variance itself, and on a badly offset one the fast form goes
    negative. That is the whole argument for the second pass, expressed as a number the caller can
    check on their own distribution rather than a claim in a docstring.

    @capability layernorm_variance_agrees_flat
    complexity: O(n_rows * n_cols)
    counts:
    - n_rows * n_cols <= len(x) [enforced]
    @endcapability
    """
    var shape = norm_dims_check(n_rows, n_cols, 0.0)
    if shape != NORM_OK:
        return LayerNormAgreement(0.0, 0.0, False, 0, shape)
    if len(x) < n_rows * n_cols:
        return LayerNormAgreement(0.0, 0.0, False, 0, NORM_ERR_LENGTH_MISMATCH)

    var inv_n = 1.0 / Float64(n_cols)
    var worst = 0.0
    var tol_at_worst = 0.0
    for i in range(n_rows):
        var base = i * n_cols
        var total = 0.0
        var total_sq = 0.0
        for c in range(n_cols):
            var v = x[base + c]
            total += v
            total_sq += v * v
        var mu = total * inv_n
        var one_pass = total_sq * inv_n - mu * mu
        var acc = 0.0
        for c in range(n_cols):
            var t = x[base + c] - mu
            acc += t * t
        var two_pass = acc * inv_n
        var delta = one_pass - two_pass
        if delta < 0.0:
            delta = -delta
        if delta > worst:
            worst = delta
            tol_at_worst = norm_tol_for(two_pass, n_cols)

    if tol_at_worst == 0.0:
        tol_at_worst = norm_tol_for(0.0, n_cols)
    return LayerNormAgreement(worst, tol_at_worst, worst <= tol_at_worst, n_rows, NORM_OK)


fn layernorm_gradcheck_flat(
    x: List[Float64], gamma: List[Float64], beta: List[Float64],
    n_rows: Int, n_cols: Int, eps: Float64, step: Float64
) -> LayerNormAgreement:
    """Compare the analytic `dx` against central differences of `sum(y)`, worst element.

    Tolerance reasoning is `normk.rmsnorm.rmsnorm_gradcheck_flat`'s: a central difference cannot beat
    roughly `step^2`, so judging it by a forward tolerance fails on correct code.

    @capability layernorm_gradcheck_flat
    complexity: O(n_rows * n_cols * n_cols)
    counts:
    - n_rows * n_cols <= len(x) [enforced]
    - n_cols <= len(gamma, beta) [enforced]
    @endcapability
    """
    var shape = norm_dims_check(n_rows, n_cols, eps)
    if shape != NORM_OK:
        return LayerNormAgreement(0.0, 0.0, False, 0, shape)
    if len(x) < n_rows * n_cols or len(gamma) < n_cols or len(beta) < n_cols:
        return LayerNormAgreement(0.0, 0.0, False, 0, NORM_ERR_LENGTH_MISMATCH)
    if not tx_finite(step) or step <= 0.0:
        return LayerNormAgreement(0.0, 0.0, False, 0, NORM_ERR_LENGTH_MISMATCH)

    var fwd = layernorm_fwd_flat(x, gamma, beta, n_rows, n_cols, eps)
    if fwd.status != NORM_OK:
        return LayerNormAgreement(0.0, 0.0, False, 0, fwd.status)

    var ones = List[Float64](capacity=n_rows * n_cols)
    for _ in range(n_rows * n_cols):
        ones.append(1.0)
    var grad = layernorm_bwd_flat(ones, x, gamma, fwd.mean, fwd.rstd, n_rows, n_cols)
    if grad.status != NORM_OK:
        return LayerNormAgreement(0.0, 0.0, False, 0, grad.status)

    var probe = List[Float64](capacity=n_rows * n_cols)
    for idx in range(n_rows * n_cols):
        probe.append(x[idx])

    var worst = 0.0
    var tol_at_worst = 0.0
    for idx in range(n_rows * n_cols):
        var original = probe[idx]
        probe[idx] = original + step
        var up = _sum_of_layernorm(probe, gamma, beta, n_rows, n_cols, eps)
        probe[idx] = original - step
        var down = _sum_of_layernorm(probe, gamma, beta, n_rows, n_cols, eps)
        probe[idx] = original

        var numeric = (up - down) / (2.0 * step)
        var delta = grad.dx[idx] - numeric
        if delta < 0.0:
            delta = -delta
        var mag = numeric if numeric >= 0.0 else -numeric
        var tol = step * step * (1.0 + mag) + 1.0e-9 * (1.0 + mag)
        if delta > worst:
            worst = delta
            tol_at_worst = tol

    if tol_at_worst == 0.0:
        tol_at_worst = 1.0e-9
    return LayerNormAgreement(worst, tol_at_worst, worst <= tol_at_worst, n_rows * n_cols, NORM_OK)


fn _sum_of_layernorm(
    x: List[Float64], gamma: List[Float64], beta: List[Float64],
    n_rows: Int, n_cols: Int, eps: Float64
) -> Float64:
    """`SUM(y)` for one perturbed input. Underscore-prefixed: a gradcheck helper, not a kernel."""
    var out = layernorm_fwd_flat(x, gamma, beta, n_rows, n_cols, eps)
    if out.status != NORM_OK:
        return 0.0
    var total = 0.0
    for idx in range(n_rows * n_cols):
        total += out.y[idx]
    return total
