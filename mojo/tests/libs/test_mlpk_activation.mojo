"""test_mlpk_activation.mojo — the GELU convention, and gradients that are proven to be checked.

Hand-written. Two jobs.

FIRST, PIN THE GELU FINDING. The frozen tree holds three GELU spellings and all three are the tanh
approximation — including `activations.gelu`, whose docstring opens "Gaussian Error Linear Unit
(exact)". Hugging Face treats erf-GELU and tanh-GELU as different activations, so the gap decides
whether a checkpoint can be served under the other convention. It is pinned here as a number so it
stays a reported fact rather than drifting into folklore. Also pinned: `gelu_fast` and `gelu_new` are
1 ULP apart (they associate the cubic differently), and `gelu` differs from them in the tenth digit
of `sqrt(2/pi)` — so this is ONE convention spelled three times with three roundings, not two
conventions. The 1-ULP gap is asserted rather than assumed away: a six-point probe read it as zero.

SECOND, THE GRADIENTS, with proof the check can fail. Each activation's analytic gate derivative is
compared against central differences. Then the same test recomputes the gradient with the term a
reader drops and asserts THAT is caught. A gradcheck that cannot fail is decoration.

The erf path gets a wider tolerance and the reason is measured, not assumed: `std.math.erf` on this
toolchain carries ~2e-8 of its own error (at x=2.0 it returns 0.9953222865616017 where the correctly
rounded value is 0.9953222650189527), so a central difference of an erf-based forward cannot resolve
better than that. The golden values below come from a correctly-rounded double reference.
"""
from mlpk.activation import (
    gated_ffn_bwd_flat,
    gated_ffn_fwd_flat,
    mlp_gelu_agreement,
    mlp_gelu_erf,
    mlp_gelu_erf_grad,
    mlp_gelu_tanh_grad,
    swiglu_gradcheck_flat,
)
from mlpk.contract import (
    MLP_ACT_GEGLU_ERF,
    MLP_ACT_GEGLU_TANH,
    MLP_ACT_SWIGLU,
    MLP_ERR_LENGTH_MISMATCH,
    MLP_ERR_UNKNOWN_ACTIVATION,
    MLP_OK,
)
from activations import gelu, gelu_fast, gelu_new
from std.math import exp


fn _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


fn _pseudo(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 23)) / 11.0 - 1.0)
    return o^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── 1. the GELU convention gap, pinned ────────────────────────────────────
    var ag = mlp_gelu_agreement(-4.0, 4.0, 2001)
    if ag.status == MLP_OK and ag.max_abs_delta > 4.0e-4 and ag.max_abs_delta < 5.0e-4:
        passed += 1
        print("  ✅ tanh GELU sits", ag.max_abs_delta, "from the erf form, worst at x =", ag.argmax_input)
    else:
        failed += 1
        print("  ❌ the GELU convention gap moved:", ag.max_abs_delta)

    if not ag.within_tolerance:
        passed += 1
        print("  ✅ and that gap is NOT within tolerance — these are different activations")
    else:
        failed += 1
        print("  ❌ the two GELU conventions were reported as agreeing")

    # One convention, three spellings, three roundings — measured across 81 points, not sampled.
    var worst_pair = 0.0
    var worst_trunc = 0.0
    for i in range(81):
        var x = -4.0 + 0.1 * Float64(i)
        var d_pair = _abs(gelu_fast(x) - gelu_new(x))
        var d_trunc = _abs(gelu(x) - gelu_fast(x))
        if d_pair > worst_pair:
            worst_pair = d_pair
        if d_trunc > worst_trunc:
            worst_trunc = d_trunc
    # NOT bit-identical, and the difference is instructive: one associates the cubic as
    # `C*(x + a*x^3)` and the other as `C*x*(1 + a*x^2)`, so they round differently by ~1 ULP. A
    # six-point probe showed them equal and that reading was wrong; 81 points found the gap.
    if worst_pair > 0.0 and worst_pair < 1.0e-15:
        passed += 1
        print("  ✅ gelu_fast and gelu_new agree to 1 ULP —", worst_pair, "— same convention, different association")
    else:
        failed += 1
        print("  ❌ the gelu_fast/gelu_new gap moved:", worst_pair)

    if worst_trunc > 0.0 and worst_trunc < 1.0e-11:
        passed += 1
        print("  ✅ gelu differs from them only in the truncated constant —", worst_trunc)
    else:
        failed += 1
        print("  ❌ the gelu constant difference moved:", worst_trunc)

    # ── 2. the erf GELU against a correctly-rounded reference ─────────────────
    # Golden values: x * 0.5 * (1 + erf(x/sqrt(2))) computed in correctly-rounded double.
    # The tolerance is 1e-7, which is the toolchain erf's accuracy — NOT a claim of bit-parity.
    var worst_golden = 0.0
    var gx = List[Float64]()
    var gy = List[Float64]()
    gx.append(-2.0); gy.append(-0.04550026389635842)
    gx.append(-1.0); gy.append(-0.15865525393145707)
    gx.append(0.0); gy.append(0.0)
    gx.append(1.0); gy.append(0.8413447460685429)
    gx.append(2.0); gy.append(1.9544997361036416)
    for i in range(len(gx)):
        var delta = _abs(mlp_gelu_erf(gx[i]) - gy[i])
        if delta > worst_golden:
            worst_golden = delta
    if worst_golden < 1.0e-7:
        passed += 1
        print("  ✅ mlp_gelu_erf matches a correctly-rounded reference to", worst_golden)
    else:
        failed += 1
        print("  ❌ the erf GELU drifted from its golden values by", worst_golden)

    # The derivative belongs to the SAME activation as the forward. If the erf grad were secretly the
    # tanh grad, this would be ~0; it is not, and the gap is the same order as the forward gap.
    var worst_grad_gap = 0.0
    for i in range(81):
        var x = -4.0 + 0.1 * Float64(i)
        var d = _abs(mlp_gelu_erf_grad(x) - mlp_gelu_tanh_grad(x))
        if d > worst_grad_gap:
            worst_grad_gap = d
    if worst_grad_gap > 1.0e-4:
        passed += 1
        print("  ✅ the two GELU derivatives differ by", worst_grad_gap, "— neither is standing in for the other")
    else:
        failed += 1
        print("  ❌ the erf and tanh derivatives are suspiciously close:", worst_grad_gap)

    # ── 3. forward parity with the frozen kernels ─────────────────────────────
    var n_tok = 4
    var d_ff = 8
    var v = _pseudo(n_tok * d_ff, 1)
    var g = _pseudo(n_tok * d_ff, 5)

    var sw = gated_ffn_fwd_flat(v, g, n_tok, d_ff, MLP_ACT_SWIGLU)
    var worst_sw = 0.0
    for i in range(n_tok * d_ff):
        var expected = (g[i] / (1.0 + exp(-g[i]))) * v[i]
        var delta = _abs(sw.y[i] - expected)
        if delta > worst_sw:
            worst_sw = delta
    if sw.status == MLP_OK and worst_sw < 1.0e-15:
        passed += 1
        print("  ✅ SwiGLU forward matches swish(gate)*value elementwise —", worst_sw)
    else:
        failed += 1
        print("  ❌ SwiGLU forward drifted by", worst_sw)

    var gt = gated_ffn_fwd_flat(v, g, n_tok, d_ff, MLP_ACT_GEGLU_TANH)
    var worst_gt = 0.0
    for i in range(n_tok * d_ff):
        var delta = _abs(gt.y[i] - gelu_new(g[i]) * v[i])
        if delta > worst_gt:
            worst_gt = delta
    # Sub-ULP rather than exactly zero: the parallel loop lets the compiler contract
    # `gelu_new(g) * v` into an FMA, which rounds once where the reference rounds twice. Asserting
    # bit-equality here would forbid a legitimate optimization to no benefit.
    if gt.status == MLP_OK and worst_gt < 1.0e-15:
        passed += 1
        print("  ✅ the tanh GEGLU path tracks the frozen gelu_new to", worst_gt, "(FMA contraction)")
    else:
        failed += 1
        print("  ❌ the tanh GEGLU path diverged from gelu_new by", worst_gt)

    # ── 4. gradients, each with proof the check has teeth ─────────────────────
    for kind in range(3):
        var gc = swiglu_gradcheck_flat(v, g, n_tok, d_ff, kind, 1.0e-4)
        if gc.status == MLP_OK and gc.within_tolerance:
            passed += 1
            print("  ✅ kind", kind, "gate gradient matches central differences —", gc.max_abs_delta,
                  "tol", gc.tolerance_at_max)
        else:
            failed += 1
            print("  ❌ kind", kind, "gradcheck failed:", gc.max_abs_delta, "tol", gc.tolerance_at_max)

    # The truncation everyone makes: d/dg of g*sigmoid(g) written as just `sigmoid(g)`.
    var ones = List[Float64](capacity=n_tok * d_ff)
    for _ in range(n_tok * d_ff):
        ones.append(1.0)
    var grad = gated_ffn_bwd_flat(ones, v, g, n_tok, d_ff, MLP_ACT_SWIGLU)
    var worst_naive = 0.0
    for i in range(n_tok * d_ff):
        var s = 1.0 / (1.0 + exp(-g[i]))
        var truncated = v[i] * s          # missing the g*(1-s) factor
        var delta = _abs(grad.d_gate[i] - truncated)
        if delta > worst_naive:
            worst_naive = delta
    if worst_naive > 1.0e-3:
        passed += 1
        print("  ✅ truncating the SwiGLU gate derivative is detectable — it moves d_gate by", worst_naive)
    else:
        failed += 1
        print("  ❌ the swish product-rule term is numerically invisible; the gradcheck proves nothing")

    # ── 5. refusals ───────────────────────────────────────────────────────────
    if gated_ffn_fwd_flat(v, g, n_tok, d_ff, 99).status == MLP_ERR_UNKNOWN_ACTIVATION:
        passed += 1
        print("  ✅ an unknown activation is refused rather than defaulted to SwiGLU")
    else:
        failed += 1
        print("  ❌ an unknown activation was accepted")

    var lf5 = _pseudo(5, 1)
    if gated_ffn_fwd_flat(lf5, lf5, 5, 5, MLP_ACT_SWIGLU).status == MLP_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ the A-Z call shape is refused rather than aborting the worker")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted")

    print("  [mlpk.activation] Passed:", passed, "Failed:", failed)
