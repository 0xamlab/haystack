"""test_normk_layernorm.mojo — known-value and property tests for tensorized LayerNorm.

Hand-written. The headline case is the one that justifies the module's most expensive design choice.

THE VARIANCE FORMULA. `mean(x^2) - mean(x)^2` fuses two reductions into one walk of the row and is
the obvious optimization. It is also catastrophically cancelling: on a row offset far from zero the
two terms agree to most of their significant digits and the difference keeps only the noise. This
file measures the damage on a row offset by 1e8 — the shape a residual stream takes after a few
blocks — and asserts the gap is enormous, so the two-pass choice is evidenced rather than asserted.

The rest:

* NORMALIZED MOMENTS. With gamma=1 and beta=0 every output row must have mean 0 and variance 1. That
  is what LayerNorm means, and it catches an axis error, a missing mean subtraction and a wrong
  divisor at once.
* THE GRADIENT, against central differences, plus proof the check can fail — the two correction
  terms in `dx` are exactly what a reader drops, and dropping either still yields finite gradients.
* SHIFT EQUIVARIANCE. Unlike RMSNorm, LayerNorm subtracts the mean, so `y(x + c) == y(x)`. Testing
  both equivariances across the two modules pins which kernel is which; a copy-paste between them
  would break one of the two.
"""
from normk.contract import NORM_ERR_BAD_EPS, NORM_ERR_LENGTH_MISMATCH, NORM_OK
from normk.layernorm import (
    layernorm_bwd_flat,
    layernorm_fwd_flat,
    layernorm_gradcheck_flat,
    layernorm_variance_agrees_flat,
)


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo(n: Int, seed: Int) -> List[Float64]:
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
    var gamma = List[Float64](capacity=cols)
    var beta = List[Float64](capacity=cols)
    for _ in range(cols):
        gamma.append(1.0)
        beta.append(0.0)

    # ── 1. the normalized moments ─────────────────────────────────────────────
    var out = layernorm_fwd_flat(x, gamma, beta, rows, cols, 0.0)
    var worst_mean = 0.0
    var worst_var = 0.0
    for i in range(rows):
        var total = 0.0
        for c in range(cols):
            total += out.y[i * cols + c]
        var mu = total / Float64(cols)
        var acc = 0.0
        for c in range(cols):
            var t = out.y[i * cols + c] - mu
            acc += t * t
        var variance = acc / Float64(cols)
        if _abs(mu) > worst_mean:
            worst_mean = _abs(mu)
        if _abs(variance - 1.0) > worst_var:
            worst_var = _abs(variance - 1.0)
    if out.status == NORM_OK and worst_mean < 1.0e-14 and worst_var < 1.0e-13:
        passed += 1
        print("  ✅ every output row has mean 0 and variance 1 —", worst_mean, worst_var)
    else:
        failed += 1
        print("  ❌ the output moments are wrong:", worst_mean, worst_var)

    # ── 2. THE VARIANCE FORMULA, measured where it breaks ─────────────────────
    var centred = layernorm_variance_agrees_flat(x, rows, cols)
    if centred.status == NORM_OK and centred.within_tolerance:
        passed += 1
        print("  ✅ near zero the one-pass and two-pass variances agree —", centred.max_abs_delta)
    else:
        failed += 1
        print("  ❌ the two variance formulas disagree even on centred data:", centred.max_abs_delta)

    var offset = List[Float64](capacity=rows * cols)
    for idx in range(rows * cols):
        offset.append(x[idx] + 1.0e8)
    var drifted = layernorm_variance_agrees_flat(offset, rows, cols)
    if drifted.status == NORM_OK and not drifted.within_tolerance and drifted.max_abs_delta > 0.01:
        passed += 1
        print("  ✅ offset by 1e8 the one-pass identity loses", drifted.max_abs_delta,
              "— this is why the forward makes two passes")
    else:
        failed += 1
        print("  ❌ the cancellation case did not reproduce:", drifted.max_abs_delta)

    # And the two-pass forward is UNHARMED by the same offset: shift equivariance.
    var shifted_out = layernorm_fwd_flat(offset, gamma, beta, rows, cols, 0.0)
    var worst_shift = 0.0
    for idx in range(rows * cols):
        var delta = _abs(out.y[idx] - shifted_out.y[idx])
        if delta > worst_shift:
            worst_shift = delta
    if shifted_out.status == NORM_OK and worst_shift < 1.0e-6:
        passed += 1
        print("  ✅ shift-equivariant: the same row offset by 1e8 normalizes to", worst_shift)
    else:
        failed += 1
        print("  ❌ a 1e8 shift changed the normalized output by", worst_shift)

    # ── 3. the backward pass ──────────────────────────────────────────────────
    var vgamma = _pseudo(cols, 7)
    for c in range(cols):
        vgamma[c] = vgamma[c] + 1.5
    var gc = layernorm_gradcheck_flat(x, vgamma, beta, rows, cols, 1.0e-5, 1.0e-4)
    if gc.status == NORM_OK and gc.within_tolerance:
        passed += 1
        print("  ✅ analytic dx matches central differences — delta", gc.max_abs_delta,
              "tol", gc.tolerance_at_max)
    else:
        failed += 1
        print("  ❌ gradcheck failed:", gc.max_abs_delta, "tol", gc.tolerance_at_max)

    # Prove the gate can fail: `dxhat * rstd` alone is the version with both corrections dropped.
    var fwd = layernorm_fwd_flat(x, vgamma, beta, rows, cols, 1.0e-5)
    var ones = List[Float64](capacity=rows * cols)
    for _ in range(rows * cols):
        ones.append(1.0)
    var grad = layernorm_bwd_flat(ones, x, vgamma, fwd.mean, fwd.rstd, rows, cols)
    var worst_naive = 0.0
    for i in range(rows):
        for c in range(cols):
            var naive = fwd.rstd[i] * vgamma[c]
            var delta = _abs(grad.dx[i * cols + c] - naive)
            if delta > worst_naive:
                worst_naive = delta
    if worst_naive > 1.0e-6:
        passed += 1
        print("  ✅ dropping the mean/variance corrections is detectable — dx moves by", worst_naive)
    else:
        failed += 1
        print("  ❌ the correction terms are numerically invisible; the gradcheck proves nothing")

    # dbeta is the plain column sum of dy — with dy all ones that is exactly n_rows.
    var worst_db = 0.0
    for c in range(cols):
        var delta = _abs(grad.dbeta[c] - Float64(rows))
        if delta > worst_db:
            worst_db = delta
    if worst_db == 0.0:
        passed += 1
        print("  ✅ dbeta is the exact column sum of dy")
    else:
        failed += 1
        print("  ❌ dbeta drifted from the column sum by", worst_db)

    # ── refusals ──────────────────────────────────────────────────────────────
    if layernorm_fwd_flat(x, gamma, beta, rows, cols, -1.0).status == NORM_ERR_BAD_EPS:
        passed += 1
        print("  ✅ a negative eps is refused before any sqrt is taken")
    else:
        failed += 1
        print("  ❌ a negative eps was accepted")

    var lf5 = List[Float64]()
    for _ in range(5):
        lf5.append(0.5)
    if layernorm_fwd_flat(lf5, lf5, lf5, 5, 5, 0.5).status == NORM_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ the A-Z call shape is refused rather than aborting the worker")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted")

    print("  [normk.layernorm] Passed:", passed, "Failed:", failed)
