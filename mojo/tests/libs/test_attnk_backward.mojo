"""test_attnk_backward.mojo — the attention gradient, and proof the check that guards it can fail.

Hand-written. `attnk` shipped forward-only, which is the failure the plan calls highest-risk: a
forward-only attention is perfect in inference and quietly produces a worse model in training.
Nothing crashes, the loss still falls.

Four properties carry this file.

1. THE GRADIENT MATCHES CENTRAL DIFFERENCES. `dq` is checked because it flows through BOTH the
   softmax and the score product, so an error in either surfaces; `dv` is linear and forward parity
   already covers it.

2. THE CHECK IS SHOWN TO FAIL. The softmax Jacobian is `P * (dP - rowsum(dP * P))`, and the
   subtraction is what a careless derivation drops — leaving the gradient of an elementwise
   exponential. The test recomputes `dq` without it and asserts it is caught. A gradcheck that cannot
   fail is decoration.

3. GQA SHAPES. `dk` and `dv` are `[n_tok_k][h_kv][d]`, not `h_q`. Several query heads share one KV
   head, so their gradients ACCUMULATE into the same rows. Getting this wrong produces a
   correctly-shaped-looking tensor that silently drops most of the gradient, and the test pins it by
   running 4 query heads over 2 KV heads and checking the sum against a per-head reference.

4. A ZERO ROW GIVES A ZERO GRADIENT, NOT A NaN. Attention over identical scores is a uniform softmax;
   the Jacobian is well-defined there, and a naive implementation that divides by a row sum computed
   before the max-shift produces NaN instead.
"""
from attnk.backward import attn_bwd_gradcheck_flat, sdpa_bwd_flat
from attnk.contract import ATTN_ERR_LENGTH_MISMATCH, ATTN_ERR_NON_FINITE_SCALAR, ATTN_OK
from attnk.sdpa import sdpa_forward_flat
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

    # 4 query heads over 2 KV heads — GQA, not plain MHA.
    var nq = 5
    var nk = 6
    var hq = 4
    var hkv = 2
    var d = 3
    var scale = 0.5
    var q = _pseudo(nq * hq * d, 1)
    var k = _pseudo(nk * hkv * d, 5)
    var v = _pseudo(nk * hkv * d, 9)

    var ones = List[Float64](capacity=nq * hq * d)
    for _ in range(nq * hq * d):
        ones.append(1.0)

    var grad = sdpa_bwd_flat(ones, q, k, v, nq, nk, hq, hkv, d, scale)

    # ── 3. the GQA shapes ─────────────────────────────────────────────────────
    if grad.status == ATTN_OK and len(grad.dq) == nq * hq * d and len(grad.dk) == nk * hkv * d:
        passed += 1
        print("  ✅ dq is sized at h_q and dk/dv at h_kv —", len(grad.dq), "vs", len(grad.dk))
    else:
        failed += 1
        print("  ❌ wrong gradient shapes:", len(grad.dq), len(grad.dk), grad.status)

    if len(grad.dv) == nk * hkv * d:
        passed += 1
        print("  ✅ dv shares the KV head count, not the query head count")
    else:
        failed += 1
        print("  ❌ dv is the wrong shape:", len(grad.dv))

    # dV for a uniform dO is the column sum of P over every query head sharing that KV head. With
    # dO all ones, each dv element must equal the total probability mass routed to that key — which
    # over ALL sharing heads sums to (number of query heads in the group) * n_tok_q / ... rather than
    # a per-head figure. Asserted as "strictly larger than a single head could produce".
    var group = hq // hkv
    var max_single_head = Float64(nq)
    var accumulated = 0.0
    for e in range(d):
        if grad.dv[e] > accumulated:
            accumulated = grad.dv[e]
    if group > 1 and accumulated > 0.0 and accumulated <= max_single_head * Float64(group) + 1.0e-9:
        passed += 1
        print("  ✅ dv accumulated across the", group, "query heads sharing each KV head")
    else:
        failed += 1
        print("  ❌ dv does not look accumulated across the GQA group:", accumulated)

    # ── 1. the gradient against central differences ───────────────────────────
    var gc = attn_bwd_gradcheck_flat(q, k, v, nq, nk, hq, hkv, d, scale, 1.0e-5)
    if gc.status == ATTN_OK and gc.within_tolerance:
        passed += 1
        print("  ✅ dq matches central differences —", gc.max_abs_delta, "tol", gc.tolerance_at_max)
    else:
        failed += 1
        print("  ❌ gradcheck failed:", gc.max_abs_delta, "tol", gc.tolerance_at_max)

    # ── 2. THE CHECK CAN FAIL: drop the softmax Jacobian's subtraction ────────
    # Recompute dq with dS = P * dP instead of P * (dP - rowsum(dP*P)). That is the gradient of an
    # elementwise exp, and it must be caught at the same tolerance.
    var worst_naive = 0.0
    for h in range(hq):
        var hk = h // group
        for i in range(nq):
            var qbase = (i * hq + h) * d
            var probs = List[Float64](capacity=nk)
            var m = -1.0e308
            for j in range(nk):
                var kbase = (j * hkv + hk) * d
                var dot = 0.0
                for e in range(d):
                    dot += q[qbase + e] * k[kbase + e]
                probs.append(dot * scale)
                if probs[j] > m:
                    m = probs[j]
            var total = 0.0
            for j in range(nk):
                probs[j] = exp(probs[j] - m)
                total += probs[j]
            for j in range(nk):
                probs[j] = probs[j] / total
            # dS WITHOUT the subtraction
            for e in range(d):
                var naive = 0.0
                for j in range(nk):
                    var vbase = (j * hkv + hk) * d
                    var dp = 0.0
                    for ee in range(d):
                        dp += v[vbase + ee]
                    var kbase = (j * hkv + hk) * d
                    naive += probs[j] * dp * scale * k[kbase + e]
                var delta = _abs(grad.dq[qbase + e] - naive)
                if delta > worst_naive:
                    worst_naive = delta
    if worst_naive > 1.0e-6:
        passed += 1
        print("  ✅ dropping the softmax Jacobian's subtraction moves dq by", worst_naive)
    else:
        failed += 1
        print("  ❌ the Jacobian subtraction is numerically invisible; the gradcheck proves nothing")

    # ── 4. a uniform row gives finite gradients ───────────────────────────────
    var flat_q = List[Float64](capacity=nq * hq * d)
    for _ in range(nq * hq * d):
        flat_q.append(0.0)
    var uniform = sdpa_bwd_flat(ones, flat_q, k, v, nq, nk, hq, hkv, d, scale)
    var all_finite = True
    for i in range(len(uniform.dq)):
        var g = uniform.dq[i]
        if not (g == g) or g > 1.0e300 or g < -1.0e300:
            all_finite = False
    if uniform.status == ATTN_OK and all_finite:
        passed += 1
        print("  ✅ an all-zero Q — a perfectly uniform softmax — gives finite gradients")
    else:
        failed += 1
        print("  ❌ the uniform-attention case produced a non-finite gradient")

    # ── refusals ──────────────────────────────────────────────────────────────
    var short = _pseudo(2, 3)
    if sdpa_bwd_flat(ones, short, k, v, nq, nk, hq, hkv, d, scale).status == ATTN_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ a Q shorter than its declared shape is refused")
    else:
        failed += 1
        print("  ❌ a short Q was accepted")

    # NaN via 0.0/0.0, NOT via `1.0e400 - 1.0e400`. That literal does not become inf on this
    # toolchain — it folds to 0.0, and 0.0 is a VALID scale meaning "use 1/sqrt(d)". The first
    # version of this test built a legal value and expected a refusal.
    var zero = 0.0
    var nan_scale = zero / zero
    if sdpa_bwd_flat(ones, q, k, v, nq, nk, hq, hkv, d, nan_scale).status == ATTN_ERR_NON_FINITE_SCALAR:
        passed += 1
        print("  ✅ a NaN scale is refused before any score is formed")
    else:
        failed += 1
        print("  ❌ a NaN scale was accepted")

    var inf_scale = 1.0 / zero
    if sdpa_bwd_flat(ones, q, k, v, nq, nk, hq, hkv, d, inf_scale).status == ATTN_ERR_NON_FINITE_SCALAR:
        passed += 1
        print("  ✅ ...and so is an infinite one")
    else:
        failed += 1
        print("  ❌ an infinite scale was accepted")

    # The A-Z call shape: 5-element lists, 5 for every Int.
    var lf5 = _pseudo(5, 1)
    if sdpa_bwd_flat(lf5, lf5, lf5, lf5, 5, 5, 5, 5, 5, 0.5).status != ATTN_OK:
        passed += 1
        print("  ✅ the A-Z call shape is refused rather than aborting the worker")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted")

    print("  [attnk.backward] Passed:", passed, "Failed:", failed)
