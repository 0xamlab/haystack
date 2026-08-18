"""
mlpk.activation — gated feed-forward activations, forward and backward, tensorized. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_mlpk_activation.mojo
benchmark: benchmarks/mojo_benchmarks/bench_mlpk.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

What the frozen tree has, and the one thing it does not
--------------------------------------------------------
`activations.swiglu(x, gate) = swish(gate) * x` is exactly right and is called unchanged (rule 3), as
is `activations.gelu_new` for the tanh GELU variant. What is absent is threefold: the loop over a
real `[n_tok][d_ff]` buffer, every backward derivative, and the erf-convention GELU.

The erf GELU is not a refinement, it is a different activation
----------------------------------------------------------------
All three frozen spellings are the tanh approximation, including the one whose docstring opens
"Gaussian Error Linear Unit (exact)". Measured against `x * 0.5 * (1 + erf(x / sqrt(2)))` the error is
4.73e-4 at x = 2.7 — see `mlpk.contract` for the table and for why nothing here is named "exact". Hugging Face treats the two as different activations
(`hidden_act: "gelu"` is erf; `"gelu_new"` and `"gelu_pytorch_tanh"` are tanh), so which one a
checkpoint wants is decided by its config, not by us.

`mlp_gelu_erf` therefore exists as a SEPARATE contract for new surfaces. Every frozen spelling stays
reachable and unchanged, `mlp_gelu_agreement` reports the delta as a number, and the caller picks with
`MLP_ACT_GEGLU_ERF` or `MLP_ACT_GEGLU_TANH`. There is no default: defaulting would be right for half
of all checkpoints and quietly wrong for the other half.

The derivatives, written out because they are where this goes wrong
---------------------------------------------------------------------
A gated FFN computes `y = act(gate) * value` from two projections. With `s = sigmoid(g)`:

    SwiGLU:  y = g*s*v          d/dv = g*s            d/dg = v * s * (1 + g*(1 - s))
    GEGLU:   y = gelu(g)*v      d/dv = gelu(g)        d/dg = v * gelu'(g)

The SwiGLU gate derivative is the one that gets truncated to `v * s`. That is the derivative of
`sigmoid(g)*v`, not of `swish(g)*v`, and it is wrong by the `g*s*(1-s)` term — largest exactly where
the gate is doing its work. Gradients stay finite and plausibly scaled, so only a gradcheck sees it.
`swiglu_gradcheck_flat` is that check, and the test file proves the check can fail.

Public API:
  mlp_gelu_erf(x)                                          -> Float64
  mlp_gelu_agreement(lo, hi, samples)                        -> GeluAgreement
  gated_ffn_fwd_flat(value, gate, n_tok, d_ff, kind)         -> ActOut
  gated_ffn_bwd_flat(dy, value, gate, n_tok, d_ff, kind)     -> ActGrad
  swiglu_gradcheck_flat(value, gate, n_tok, d_ff, step)      -> GeluAgreement
"""

from max.algorithm import parallelize
from std.math import erf, exp, sqrt, tanh
from std.sys.info import num_physical_cores
from activations import gelu_new, swiglu
from mlpk.contract import (
    MLP_ACT_GEGLU_ERF,
    MLP_ACT_GEGLU_TANH,
    MLP_ACT_SWIGLU,
    MLP_ERR_LENGTH_MISMATCH,
    MLP_ERR_UNKNOWN_ACTIVATION,
    MLP_MAX_TOKENS,
    MLP_OK,
    mlp_activation_known,
    mlp_dims_check,
    mlp_tol_for,
)
from tensorx.contract import tx_finite

comptime PARALLEL_MIN_CELLS: Int = 1 << 15
"""Below ~32k cells the fan-out costs more than the activation. Same threshold as `normk`/`gemm`."""

comptime ERF_GRAD_FLOOR: Float64 = 1.0e-6
"""Extra gradcheck slack for the erf activations, and only for them.

`std.math.erf` carries ~2e-8 of its own error, so a central difference of an erf-based forward cannot
resolve the derivative better than that. Measured on this tree: the tanh gate gradient checks out at
1.3e-9 while the erf one lands at 7.8e-8 against an identical analytic derivation — the gap is the
erf implementation, not the calculus. A floor of 1e-6 absorbs it and is still three orders of
magnitude tighter than a real derivative bug, which the test file shows moves the gradient by ~2."""

comptime GELU_TANH_COEF: Float64 = 0.7978845608028654
"""`sqrt(2/pi)`, at the precision `activations.gelu_new` carries. `activations.gelu` truncates it to
`0.7978845608`, which is why those two frozen spellings differ by 9e-13 while both sit 4.73e-4 from
the erf form. Restated here so the tanh path this module drives matches `gelu_new` rather than
introducing a fourth rounding."""


@fieldwise_init
struct ActOut(Copyable, Movable):
    """Activated feed-forward values, `[n_tok][d_ff]` row-major."""

    var y: List[Float64]
    var n_tok: Int
    var d_ff: Int
    var activation: Int
    var status: Int


@fieldwise_init
struct ActGrad(Copyable, Movable):
    """Gradients with respect to both projections of a gated feed-forward."""

    var d_value: List[Float64]
    var d_gate: List[Float64]
    var n_tok: Int
    var d_ff: Int
    var status: Int


@fieldwise_init
struct GeluAgreement(Copyable, Movable):
    """How far two spellings of the same quantity are apart, and how far they are allowed to be."""

    var max_abs_delta: Float64
    var tolerance_at_max: Float64
    var within_tolerance: Bool
    var argmax_input: Float64
    var n_compared: Int
    var status: Int


def mlp_gelu_erf(x: Float64) -> Float64:
    """GELU via the error function: `x * 0.5 * (1 + erf(x / sqrt(2)))`.

    The erf form, matching Hugging Face's `hidden_act: "gelu"`. A NEW contract, not a correction:
    `activations.gelu`, `gelu_fast` and `gelu_new` keep their current answers for their current
    callers, and the gap between the two families is reported by `mlp_gelu_agreement` rather than
    silently resolved.

    Accurate to roughly 2e-8, which is `std.math.erf`'s own accuracy on this toolchain, NOT to the
    last bit — hence `_erf` rather than `_exact` (see `mlpk.contract`). That is still five orders of
    magnitude closer to the convention than the tanh form's 4.73e-4.

    @capability mlp_gelu_erf
    complexity: O(1)
    @endcapability
    """
    if not tx_finite(x):
        return x
    return x * 0.5 * (1.0 + erf(x / sqrt(2.0)))


def mlp_gelu_erf_grad(x: Float64) -> Float64:
    """`d/dx` of the erf GELU: `Phi(x) + x * phi(x)`.

    `phi` is the standard normal density `exp(-x^2/2) / sqrt(2*pi)`. Written in terms of erf rather
    than differentiating the tanh approximation, so the gradient belongs to the same activation the
    forward computed — pairing an erf forward with a tanh backward is a bug no forward parity test
    can see, because the forward would be right.
    """
    if not tx_finite(x):
        return 0.0
    var cdf = 0.5 * (1.0 + erf(x / sqrt(2.0)))
    var pdf = exp(-0.5 * x * x) / sqrt(2.0 * 3.14159265358979323846)
    return cdf + x * pdf


def mlp_gelu_tanh_grad(x: Float64) -> Float64:
    """`d/dx` of the tanh GELU, matching `activations.gelu_new`'s forward exactly.

    With `u = C * x * (1 + 0.044715 x^2)`, `gelu_new(x) = 0.5 x (1 + tanh u)` and

        d/dx = 0.5 (1 + tanh u) + 0.5 x (1 - tanh^2 u) * C * (1 + 3 * 0.044715 x^2)

    The `3 *` on the cubic term is the part that gets dropped: `u`'s derivative is
    `C(1 + 3a x^2)`, not `C(1 + a x^2)`. Dropping it leaves a gradient that is finite, correctly
    signed and wrong by up to a few percent where the activation is most active.
    """
    if not tx_finite(x):
        return 0.0
    var inner = GELU_TANH_COEF * x * (1.0 + 0.044715 * x * x)
    var t = tanh(inner)
    var d_inner = GELU_TANH_COEF * (1.0 + 3.0 * 0.044715 * x * x)
    return 0.5 * (1.0 + t) + 0.5 * x * (1.0 - t * t) * d_inner


def mlp_gelu_agreement(lo: Float64, hi: Float64, samples: Int) -> GeluAgreement:
    """Measure the frozen tanh GELU against the erf GELU across `[lo, hi]`.

    Reported rather than reconciled. The number a caller needs is not "are they close" but "how far
    apart, and where" — the answer decides whether a checkpoint trained under one convention can be
    served under the other, and it is a per-model judgement rather than a library one.

    @capability mlp_gelu_agreement
    complexity: O(samples)
    counts:
    - dim samples <= MLP_MAX_TOKENS [kernel_validated]
    @endcapability
    """
    if samples <= 0 or not tx_finite(lo) or not tx_finite(hi) or hi <= lo:
        return GeluAgreement(0.0, 0.0, False, 0.0, 0, MLP_ERR_LENGTH_MISMATCH)
    # The package ceiling, not a second literal — a hardcoded bound here would be a second
    # spelling of MLP_MAX_TOKENS free to drift from it.
    if samples > MLP_MAX_TOKENS:
        return GeluAgreement(0.0, 0.0, False, 0.0, 0, MLP_ERR_LENGTH_MISMATCH)

    var worst = 0.0
    var at = 0.0
    var tol = 0.0
    var stride = (hi - lo) / Float64(samples - 1) if samples > 1 else 0.0
    for i in range(samples):
        var x = lo + stride * Float64(i)
        var exact = mlp_gelu_erf(x)
        var approx = gelu_new(x)
        var delta = exact - approx
        if delta < 0.0:
            delta = -delta
        if delta > worst:
            worst = delta
            at = x
            tol = mlp_tol_for(exact, 1)
    if tol == 0.0:
        tol = mlp_tol_for(0.0, 1)
    # `within_tolerance` is expected to be FALSE: these are different activations, not two
    # roundings of one. The field is reported so a caller can assert the gap has not MOVED.
    return GeluAgreement(worst, tol, worst <= tol, at, samples, MLP_OK)


def gated_ffn_fwd_flat(
    value: List[Float64], gate: List[Float64], n_tok: Int, d_ff: Int, kind: Int
) -> ActOut:
    """Gated feed-forward activation over `[n_tok][d_ff]`: `y = act(gate) * value`.

    `value` and `gate` are the two projections a SwiGLU/GEGLU block produces (`up` and `gate` in
    Llama naming). This is the elementwise stage between the two GEMMs, which is why it takes them
    already projected rather than doing the projection: the matmuls belong to `gemm`.

    @capability gated_ffn_fwd_flat
    complexity: O(n_tok * d_ff)
    counts:
    - n_tok * d_ff <= len(value, gate) [enforced]
    @endcapability
    """
    var y = List[Float64]()
    var shape = mlp_dims_check(n_tok, d_ff, 1)
    if shape != MLP_OK:
        return ActOut(y^, 0, 0, kind, shape)
    if not mlp_activation_known(kind):
        return ActOut(y^, 0, 0, kind, MLP_ERR_UNKNOWN_ACTIVATION)
    if len(value) < n_tok * d_ff or len(gate) < n_tok * d_ff:
        return ActOut(y^, 0, 0, kind, MLP_ERR_LENGTH_MISMATCH)

    var total = n_tok * d_ff
    for _ in range(total):
        y.append(0.0)

    var vp = value.unsafe_ptr()
    var gp = gate.unsafe_ptr()
    var yp = y.unsafe_ptr()
    var act = kind
    var n = total
    var workers = num_physical_cores()
    if total < PARALLEL_MIN_CELLS or workers > total:
        workers = 1

    @parameter
    def _act_band(tid: Int) capturing:
        var each = n // workers
        var lo = tid * each
        var hi = lo + each if tid < workers - 1 else n
        if act == MLP_ACT_SWIGLU:
            for i in range(lo, hi):
                # The frozen kernel, unchanged: swiglu(value, gate) = swish(gate) * value.
                yp[i] = swiglu(vp[i], gp[i])
        elif act == MLP_ACT_GEGLU_TANH:
            for i in range(lo, hi):
                yp[i] = gelu_new(gp[i]) * vp[i]
        else:
            for i in range(lo, hi):
                yp[i] = mlp_gelu_erf(gp[i]) * vp[i]

    parallelize[_act_band](workers)

    return ActOut(y^, n_tok, d_ff, kind, MLP_OK)


def gated_ffn_bwd_flat(
    dy: List[Float64], value: List[Float64], gate: List[Float64],
    n_tok: Int, d_ff: Int, kind: Int
) -> ActGrad:
    """Gradients of the gated activation with respect to both projections.

    Every element is independent of every other, so this is embarrassingly parallel and needs no
    cross-element reduction — unlike `normk`, there is no ordering question here at all.

    @capability gated_ffn_bwd_flat
    complexity: O(n_tok * d_ff)
    counts:
    - n_tok * d_ff <= len(dy, value, gate) [enforced]
    @endcapability
    """
    var d_value = List[Float64]()
    var d_gate = List[Float64]()
    var shape = mlp_dims_check(n_tok, d_ff, 1)
    if shape != MLP_OK:
        return ActGrad(d_value^, d_gate^, 0, 0, shape)
    if not mlp_activation_known(kind):
        return ActGrad(d_value^, d_gate^, 0, 0, MLP_ERR_UNKNOWN_ACTIVATION)
    var total = n_tok * d_ff
    if len(dy) < total or len(value) < total or len(gate) < total:
        return ActGrad(d_value^, d_gate^, 0, 0, MLP_ERR_LENGTH_MISMATCH)

    for _ in range(total):
        d_value.append(0.0)
        d_gate.append(0.0)

    var dyp = dy.unsafe_ptr()
    var vp = value.unsafe_ptr()
    var gp = gate.unsafe_ptr()
    var dvp = d_value.unsafe_ptr()
    var dgp = d_gate.unsafe_ptr()
    var act = kind
    var n = total
    var workers = num_physical_cores()
    if total < PARALLEL_MIN_CELLS or workers > total:
        workers = 1

    @parameter
    def _grad_band(tid: Int) capturing:
        var each = n // workers
        var lo = tid * each
        var hi = lo + each if tid < workers - 1 else n
        for i in range(lo, hi):
            var g = gp[i]
            var v = vp[i]
            var d = dyp[i]
            if act == MLP_ACT_SWIGLU:
                var s = 1.0 / (1.0 + exp(-g))
                var swish_g = g * s
                dvp[i] = d * swish_g
                # d/dg of g*sigmoid(g) is s*(1 + g*(1 - s)). Truncating to `s` is the common error.
                dgp[i] = d * v * s * (1.0 + g * (1.0 - s))
            elif act == MLP_ACT_GEGLU_TANH:
                dvp[i] = d * gelu_new(g)
                dgp[i] = d * v * mlp_gelu_tanh_grad(g)
            else:
                dvp[i] = d * mlp_gelu_erf(g)
                dgp[i] = d * v * mlp_gelu_erf_grad(g)

    parallelize[_grad_band](workers)

    return ActGrad(d_value^, d_gate^, n_tok, d_ff, MLP_OK)


def swiglu_gradcheck_flat(
    value: List[Float64], gate: List[Float64], n_tok: Int, d_ff: Int,
    kind: Int, step: Float64
) -> GeluAgreement:
    """Compare the analytic gate gradient against central differences of `sum(y)`, worst element.

    Only the GATE gradient is checked: `d/dvalue` is just `act(gate)` and a forward parity test
    already covers it. The gate derivative is the one with a product rule to get wrong.

    Tolerance is the gradcheck tolerance, not the forward one. A central difference carries
    truncation error `O(step^2)` and cancellation error `O(machine_eps / step)` pulling opposite
    ways, so it cannot beat roughly `step^2`; judging it by a forward bound is rule 4b's second
    spelling and fails on correct code.

    @capability swiglu_gradcheck_flat
    complexity: O(n_tok * d_ff)
    counts:
    - n_tok * d_ff <= len(value, gate) [enforced]
    @endcapability
    """
    var shape = mlp_dims_check(n_tok, d_ff, 1)
    if shape != MLP_OK:
        return GeluAgreement(0.0, 0.0, False, 0.0, 0, shape)
    if not mlp_activation_known(kind):
        return GeluAgreement(0.0, 0.0, False, 0.0, 0, MLP_ERR_UNKNOWN_ACTIVATION)
    var total = n_tok * d_ff
    if len(value) < total or len(gate) < total:
        return GeluAgreement(0.0, 0.0, False, 0.0, 0, MLP_ERR_LENGTH_MISMATCH)
    if not tx_finite(step) or step <= 0.0:
        return GeluAgreement(0.0, 0.0, False, 0.0, 0, MLP_ERR_LENGTH_MISMATCH)

    var ones = List[Float64](capacity=total)
    for _ in range(total):
        ones.append(1.0)
    var grad = gated_ffn_bwd_flat(ones, value, gate, n_tok, d_ff, kind)
    if grad.status != MLP_OK:
        return GeluAgreement(0.0, 0.0, False, 0.0, 0, grad.status)

    var probe = List[Float64](capacity=total)
    for i in range(total):
        probe.append(gate[i])

    var worst = 0.0
    var at = 0.0
    var tol_at_worst = 0.0
    for i in range(total):
        var original = probe[i]
        probe[i] = original + step
        var up = _sum_activated(value, probe, n_tok, d_ff, kind)
        probe[i] = original - step
        var down = _sum_activated(value, probe, n_tok, d_ff, kind)
        probe[i] = original

        var numeric = (up - down) / (2.0 * step)
        var delta = grad.d_gate[i] - numeric
        if delta < 0.0:
            delta = -delta
        var mag = numeric if numeric >= 0.0 else -numeric
        var tol = step * step * (1.0 + mag) + 1.0e-9 * (1.0 + mag)
        if kind == MLP_ACT_GEGLU_ERF:
            tol += ERF_GRAD_FLOOR
        if delta > worst:
            worst = delta
            at = original
            tol_at_worst = tol

    if tol_at_worst == 0.0:
        tol_at_worst = 1.0e-9
    return GeluAgreement(worst, tol_at_worst, worst <= tol_at_worst, at, total, MLP_OK)


def _sum_activated(
    value: List[Float64], gate: List[Float64], n_tok: Int, d_ff: Int, kind: Int
) -> Float64:
    """`SUM(y)` for one perturbed gate. Underscore-prefixed: a gradcheck helper, not a kernel."""
    var out = gated_ffn_fwd_flat(value, gate, n_tok, d_ff, kind)
    if out.status != MLP_OK:
        return 0.0
    var total = 0.0
    for i in range(n_tok * d_ff):
        total += out.y[i]
    return total
