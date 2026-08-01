"""
attnk.backward — gradients of scaled dot-product attention. The half `attnk` shipped without.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_attnk_backward.mojo
benchmark: benchmarks/mojo_benchmarks/bench_attnk.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Why this exists as its own module
-----------------------------------
`attnk` shipped forward-only. Every sibling pack — `normk`, `mlpk`, `lossk` — ships its backward
alongside its forward, and attention was the exception. A forward-only attention looks perfect in
inference and silently produces a worse model in training, which is the failure the plan names as
highest-risk: nothing crashes, the loss still falls, the model is just quietly worse.

The derivation, written out because the middle term is where it goes wrong
----------------------------------------------------------------------------
With `S = scale * Q K^T + bias`, `P = softmax(S)` row-wise, and `O = P V`:

    dV = P^T dO
    dP = dO V^T
    dS = P * (dP - rowsum(dP * P))          <- the softmax Jacobian
    dQ = scale * dS K
    dK = scale * dS^T Q

The subtraction in `dS` is the whole softmax Jacobian. Dropping it leaves `dS = P * dP`, which is the
gradient of an elementwise exponential rather than of a softmax — finite, correctly signed, and wrong
by an amount that grows with how peaked the attention is. `attn_bwd_gradcheck_flat` measures it, and
the test file asserts the truncated form FAILS, so the check is known to have teeth.

`rowsum(dP * P)` is recomputed here rather than taken as `rowsum(dO * O)`
--------------------------------------------------------------------------
Those two are algebraically equal — the standard flash-attention identity — and using `dO * O` is how
a tiled backward avoids re-materializing P. This module does NOT use it, on purpose: it is the
REFERENCE backward, its job is to be obviously the definition, and the identity is exactly the kind of
substitution that is correct in the algebra and wrong in the code by a transposed index. A tiled
backward can adopt it later and be checked against this one.

Public API:
  sdpa_bwd_flat(dout, q, k, v, n_tok_q, n_tok_k, h_q, h_kv, d, scale) -> SdpaGrad
  attn_bwd_gradcheck_flat(q, k, v, n_tok_q, n_tok_k, h_q, h_kv, d, scale, step) -> BwdAgreement
"""

from std.math import exp
from attnk.contract import (
    ATTN_ERR_LENGTH_MISMATCH,
    ATTN_ERR_NON_FINITE_SCALAR,
    ATTN_OK,
    attn_dims_check,
    attn_scalars_ok,
)
from attnk.sdpa import sdpa_forward_flat
from tensorx.contract import tx_finite


@fieldwise_init
struct SdpaGrad(Copyable, Movable):
    """Gradients with respect to the three attention inputs.

    `dk` and `dv` are shaped `[n_tok_k][h_kv][d]` — the KV head count, not the query head count. Under
    grouped-query attention several query heads share one KV head, so their gradients ACCUMULATE into
    the same rows. Returning them at `h_q` would be the wrong shape and would silently drop that
    accumulation, which is the GQA-specific way this goes wrong."""

    var dq: List[Float64]
    var dk: List[Float64]
    var dv: List[Float64]
    var n_tok_q: Int
    var n_tok_k: Int
    var status: Int


@fieldwise_init
struct BwdAgreement(Copyable, Movable):
    """How far the analytic gradient sits from central differences, and how far it may."""

    var max_abs_delta: Float64
    var tolerance_at_max: Float64
    var within_tolerance: Bool
    var n_compared: Int
    var status: Int


fn sdpa_bwd_flat(
    dout: List[Float64], q: List[Float64], k: List[Float64], v: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, scale: Float64
) -> SdpaGrad:
    """Gradients of materialized attention, one query row at a time.

    Recomputes `P` per row rather than taking it as an argument. That costs a second pass over the
    scores and buys the property that this function cannot be called with a `P` that does not match
    its own forward — the failure mode where a caller passes stale probabilities and gets gradients
    for a different attention than the one it ran.

    @capability sdpa_bwd_flat
    complexity: O(h_q * n_tok_q * n_tok_k * d)
    counts:
    - n_tok_q * h_q * d <= len(dout, q) [enforced]
    - n_tok_k * h_kv * d <= len(k, v) [enforced]
    @endcapability
    """
    var dq = List[Float64]()
    var dk = List[Float64]()
    var dv = List[Float64]()
    var shape = attn_dims_check(1, h_q, h_kv, n_tok_q, n_tok_k, d)
    if shape != ATTN_OK:
        return SdpaGrad(dq^, dk^, dv^, 0, 0, shape)
    if not attn_scalars_ok(scale):
        return SdpaGrad(dq^, dk^, dv^, 0, 0, ATTN_ERR_NON_FINITE_SCALAR)
    if len(q) < n_tok_q * h_q * d or len(dout) < n_tok_q * h_q * d:
        return SdpaGrad(dq^, dk^, dv^, 0, 0, ATTN_ERR_LENGTH_MISMATCH)
    if len(k) < n_tok_k * h_kv * d or len(v) < n_tok_k * h_kv * d:
        return SdpaGrad(dq^, dk^, dv^, 0, 0, ATTN_ERR_LENGTH_MISMATCH)

    for _ in range(n_tok_q * h_q * d):
        dq.append(0.0)
    for _ in range(n_tok_k * h_kv * d):
        dk.append(0.0)
        dv.append(0.0)

    var group = h_q // h_kv
    var eff_scale = scale if scale > 0.0 else 1.0 / _sqrt(Float64(d))

    var probs = List[Float64](capacity=n_tok_k)
    var dscore = List[Float64](capacity=n_tok_k)
    for _ in range(n_tok_k):
        probs.append(0.0)
        dscore.append(0.0)

    for h in range(h_q):
        var hk = h // group
        for i in range(n_tok_q):
            var qbase = (i * h_q + h) * d
            var obase = qbase

            # ── recover P for this row, max-shifted ───────────────────────────
            var m = -1.0e308
            for j in range(n_tok_k):
                var kbase = (j * h_kv + hk) * d
                var dot = 0.0
                for e in range(d):
                    dot += q[qbase + e] * k[kbase + e]
                var s = dot * eff_scale
                probs[j] = s
                if s > m:
                    m = s
            var total = 0.0
            for j in range(n_tok_k):
                var ex = exp(probs[j] - m)
                probs[j] = ex
                total += ex
            for j in range(n_tok_k):
                probs[j] = probs[j] / total

            # ── dP = dO V^T, and dV += P^T dO ─────────────────────────────────
            for j in range(n_tok_k):
                var vbase = (j * h_kv + hk) * d
                var dp = 0.0
                for e in range(d):
                    dp += dout[obase + e] * v[vbase + e]
                dscore[j] = dp
                var p = probs[j]
                if p != 0.0:
                    for e in range(d):
                        dv[vbase + e] += p * dout[obase + e]

            # ── the softmax Jacobian: dS = P * (dP - sum(dP * P)) ─────────────
            # The subtraction is the whole Jacobian. Without it this is the gradient of an
            # elementwise exp, not of a softmax.
            var row_dot = 0.0
            for j in range(n_tok_k):
                row_dot += dscore[j] * probs[j]
            for j in range(n_tok_k):
                dscore[j] = probs[j] * (dscore[j] - row_dot)

            # ── dQ and dK from dS ─────────────────────────────────────────────
            for j in range(n_tok_k):
                var ds = dscore[j] * eff_scale
                if ds == 0.0:
                    continue
                var kbase = (j * h_kv + hk) * d
                for e in range(d):
                    dq[qbase + e] += ds * k[kbase + e]
                    # Accumulates across every query head sharing this KV head — the GQA sum.
                    dk[kbase + e] += ds * q[qbase + e]

    return SdpaGrad(dq^, dk^, dv^, n_tok_q, n_tok_k, ATTN_OK)


fn attn_bwd_gradcheck_flat(
    q: List[Float64], k: List[Float64], v: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int,
    scale: Float64, step: Float64
) -> BwdAgreement:
    """Compare the analytic `dq` against central differences of `sum(O)`, worst element.

    `dout` is all ones, so the quantity differentiated is `SUM(O)` and every path through the
    Jacobian contributes. Only `dq` is checked: it is the gradient that flows through BOTH the
    softmax and the score product, so an error in either shows up here, while `dv` is linear and a
    forward parity test already covers it.

    Tolerance is the gradcheck tolerance, not the forward one — a central difference cannot resolve
    better than roughly `step^2`, and the transcendental floor applies on top because the softmax
    goes through `exp`.

    @capability attn_bwd_gradcheck_flat
    complexity: O(h_q * n_tok_q^2 * n_tok_k * d)
    counts:
    - n_tok_q * h_q * d <= len(q) [enforced]
    - n_tok_k * h_kv * d <= len(k, v) [enforced]
    @endcapability
    """
    var shape = attn_dims_check(1, h_q, h_kv, n_tok_q, n_tok_k, d)
    if shape != ATTN_OK:
        return BwdAgreement(0.0, 0.0, False, 0, shape)
    if not tx_finite(step) or step <= 0.0:
        return BwdAgreement(0.0, 0.0, False, 0, ATTN_ERR_NON_FINITE_SCALAR)
    if len(q) < n_tok_q * h_q * d:
        return BwdAgreement(0.0, 0.0, False, 0, ATTN_ERR_LENGTH_MISMATCH)
    if len(k) < n_tok_k * h_kv * d or len(v) < n_tok_k * h_kv * d:
        return BwdAgreement(0.0, 0.0, False, 0, ATTN_ERR_LENGTH_MISMATCH)

    var n_q = n_tok_q * h_q * d
    var ones = List[Float64](capacity=n_q)
    for _ in range(n_q):
        ones.append(1.0)

    var grad = sdpa_bwd_flat(ones, q, k, v, n_tok_q, n_tok_k, h_q, h_kv, d, scale)
    if grad.status != ATTN_OK:
        return BwdAgreement(0.0, 0.0, False, 0, grad.status)

    var probe = List[Float64](capacity=n_q)
    for i in range(n_q):
        probe.append(q[i])
    var no_bias = List[Float64]()

    var worst = 0.0
    var tol_at_worst = 0.0
    for i in range(n_q):
        var original = probe[i]
        probe[i] = original + step
        var up = _sum_out(probe, k, v, no_bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale)
        probe[i] = original - step
        var down = _sum_out(probe, k, v, no_bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale)
        probe[i] = original

        var numeric = (up - down) / (2.0 * step)
        var delta = grad.dq[i] - numeric
        if delta < 0.0:
            delta = -delta
        var mag = numeric if numeric >= 0.0 else -numeric
        # step^2 truncation + the exp/log floor this tree measured at ~1e-9.
        var tol = step * step * (1.0 + mag) + 1.0e-8 * (1.0 + mag)
        if delta > worst:
            worst = delta
            tol_at_worst = tol

    if tol_at_worst == 0.0:
        tol_at_worst = 1.0e-8
    return BwdAgreement(worst, tol_at_worst, worst <= tol_at_worst, n_q, ATTN_OK)


fn _sum_out(
    q: List[Float64], k: List[Float64], v: List[Float64], bias: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, scale: Float64
) -> Float64:
    """`SUM(O)` for one perturbed Q. Underscore-prefixed: a gradcheck helper, not a kernel."""
    var out = sdpa_forward_flat(
        q, k, v, bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale, False
    )
    if out.status != ATTN_OK:
        return 0.0
    var total = 0.0
    for i in range(n_tok_q * h_q * d):
        total += out.out[i]
    return total


fn _sqrt(x: Float64) -> Float64:
    """Square root, guarding the non-positive case. Underscore-prefixed: not a kernel."""
    if x <= 0.0:
        return 1.0
    var guess = x
    for _ in range(40):
        guess = 0.5 * (guess + x / guess)
    return guess
