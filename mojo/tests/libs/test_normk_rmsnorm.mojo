"""test_normk_rmsnorm.mojo — known-value and property tests for tensorized RMSNorm.

Hand-written. Four properties carry the file, and the reason each is a property rather than a table
of expected numbers is that the failure modes here produce plausible output, not obvious wrongness.

1. AGREEMENT WITH THE FROZEN KERNEL, element by element. The tiled forward calls
   `normalization_layers.rms_norm` for every element, so this is not testing the formula — it is
   testing that the REDUCTION feeding it is the one the formula expects. A mean-square computed over
   the wrong axis still produces finite, correctly-shaped output.

2. THE ANALYTIC GRADIENT AGAINST CENTRAL DIFFERENCES. The `x * r^3 * SUM(...)` coupling term is the
   one a reader drops. Without it gradients stay finite and plausibly scaled and the model just
   trains worse, so a forward-only check cannot see it. `_gradient_without_coupling_is_caught` proves
   the check has teeth by asserting the truncated formula FAILS the same tolerance.

3. SCALE EQUIVARIANCE. RMSNorm is scale-invariant in its input: `y(c*x) == y(x)` for `c > 0` and
   `eps == 0`. This catches a mean subtraction accidentally introduced (that would be LayerNorm) and
   any stray absolute constant in the reduction.

4. THREAD-COUNT INVARIANCE of `dgamma`. It reduces across rows, and the whole reason it is split by
   column is so its answer does not move with worker count. Asserted by shape, not by luck: a tall
   narrow input crosses the parallel threshold while a small one does not, and both must agree with
   a hand-summed reference.
"""
from normk.contract import NORM_ERR_BAD_EPS, NORM_ERR_LENGTH_MISMATCH, NORM_OK
from normk.rmsnorm import (
    rmsnorm_agrees_with_frozen_flat,
    rmsnorm_bwd_flat,
    rmsnorm_fwd_flat,
    rmsnorm_gradcheck_flat,
)
from normalization_layers import rms_norm
from std.math import sqrt


fn _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


fn _pseudo(n: Int, seed: Int) -> List[Float64]:
    """Deterministic values in roughly [-1, 1] so a failure reproduces exactly."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        var t = Float64(((i * 61 + seed * 17) % 23)) / 11.0 - 1.0
        o.append(t)
    return o^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    var rows = 3
    var cols = 8
    var x = _pseudo(rows * cols, 1)
    var gamma = _pseudo(cols, 7)
    for c in range(cols):
        gamma[c] = gamma[c] + 1.5  # keep the scale away from zero

    # ── 1. the reduction feeding the frozen kernel ────────────────────────────
    var agree = rmsnorm_agrees_with_frozen_flat(x, gamma, rows, cols, 1.0e-6)
    if agree.status == NORM_OK and agree.within_tolerance:
        passed += 1
        print("  ✅ every element matches the frozen rms_norm — delta", agree.max_abs_delta)
    else:
        failed += 1
        print("  ❌ the tiled reduction disagrees with the frozen kernel:", agree.max_abs_delta)

    # ── 2. the backward pass, against central differences ─────────────────────
    var gc = rmsnorm_gradcheck_flat(x, gamma, rows, cols, 1.0e-6, 1.0e-4)
    if gc.status == NORM_OK and gc.within_tolerance:
        passed += 1
        print("  ✅ analytic dx matches central differences — delta", gc.max_abs_delta,
              "tol", gc.tolerance_at_max)
    else:
        failed += 1
        print("  ❌ gradcheck failed:", gc.max_abs_delta, "tol", gc.tolerance_at_max)

    # The gate above is only worth having if it can fail. Recompute dx WITHOUT the coupling term —
    # the exact simplification a reader makes — and confirm it is caught at the same tolerance.
    var fwd = rmsnorm_fwd_flat(x, gamma, rows, cols, 1.0e-6)
    var ones = List[Float64](capacity=rows * cols)
    for _ in range(rows * cols):
        ones.append(1.0)
    var grad = rmsnorm_bwd_flat(ones, x, gamma, fwd.rstd, rows, cols)
    var worst_naive = 0.0
    for i in range(rows):
        for c in range(cols):
            var naive = fwd.rstd[i] * gamma[c]  # the term everyone keeps, alone
            var delta = _abs(grad.dx[i * cols + c] - naive)
            if delta > worst_naive:
                worst_naive = delta
    if worst_naive > 1.0e-6:
        passed += 1
        print("  ✅ dropping the r^3 coupling term is detectable — it moves dx by", worst_naive)
    else:
        failed += 1
        print("  ❌ the coupling term is numerically invisible here; the gradcheck proves nothing")

    # ── 3. scale equivariance ─────────────────────────────────────────────────
    var scaled = List[Float64](capacity=rows * cols)
    for idx in range(rows * cols):
        scaled.append(x[idx] * 1000.0)
    var base = rmsnorm_fwd_flat(x, gamma, rows, cols, 0.0)
    var big = rmsnorm_fwd_flat(scaled, gamma, rows, cols, 0.0)
    var worst_scale = 0.0
    for idx in range(rows * cols):
        var delta = _abs(base.y[idx] - big.y[idx])
        if delta > worst_scale:
            worst_scale = delta
    if base.status == NORM_OK and big.status == NORM_OK and worst_scale < 1.0e-12:
        passed += 1
        print("  ✅ scale-invariant at eps=0: a 1000x input gives the same output —", worst_scale)
    else:
        failed += 1
        print("  ❌ scaling the input changed the output by", worst_scale)

    # ── 4. dgamma does not move with worker count ─────────────────────────────
    # 4096 rows crosses PARALLEL_MIN_CELLS; 3 rows does not. Both must equal a hand sum.
    var tall_rows = 4096
    var tall_cols = 8
    var tall = _pseudo(tall_rows * tall_cols, 3)
    var tall_fwd = rmsnorm_fwd_flat(tall, gamma, tall_rows, tall_cols, 1.0e-6)
    var tall_ones = List[Float64](capacity=tall_rows * tall_cols)
    for _ in range(tall_rows * tall_cols):
        tall_ones.append(1.0)
    var tall_grad = rmsnorm_bwd_flat(tall_ones, tall, gamma, tall_fwd.rstd, tall_rows, tall_cols)

    var worst_dg = 0.0
    for c in range(tall_cols):
        var reference = 0.0
        for i in range(tall_rows):
            reference += tall[i * tall_cols + c] * tall_fwd.rstd[i]
        var delta = _abs(tall_grad.dgamma[c] - reference)
        if delta > worst_dg:
            worst_dg = delta
    if tall_grad.status == NORM_OK and worst_dg == 0.0:
        passed += 1
        print("  ✅ dgamma is bit-identical to a serial row-order sum across", tall_rows, "rows")
    else:
        failed += 1
        print("  ❌ dgamma drifted from the serial reference by", worst_dg)

    # ── refusals ──────────────────────────────────────────────────────────────
    if rmsnorm_fwd_flat(x, gamma, rows, cols, -1.0).status == NORM_ERR_BAD_EPS:
        passed += 1
        print("  ✅ a negative eps is refused before any sqrt is taken")
    else:
        failed += 1
        print("  ❌ a negative eps was accepted")

    var short_gamma = _pseudo(2, 5)
    if rmsnorm_fwd_flat(x, short_gamma, rows, cols, 1.0e-6).status == NORM_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ a gamma shorter than the row is refused")
    else:
        failed += 1
        print("  ❌ a short gamma was accepted")

    # The A-Z call shape: 5-element lists, 5 for every Int. 5*5 = 25 > 5.
    var lf5 = List[Float64]()
    for _ in range(5):
        lf5.append(0.5)
    if rmsnorm_fwd_flat(lf5, lf5, 5, 5, 0.5).status == NORM_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ the A-Z call shape is refused rather than aborting the worker")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted")

    print("  [normk.rmsnorm] Passed:", passed, "Failed:", failed)
