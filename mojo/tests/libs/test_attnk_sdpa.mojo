"""test_attnk_sdpa.mojo — known-value tests for the materialized attention reference.

Hand-written. This module is the thing `attnk.flash` is measured against, so it is checked against
properties that can be reasoned about from the definition rather than against numbers copied from a
previous run — a reference validated by its own output is not a reference.

Four such properties: a softmax row sums to one; attention over a single key returns that key's value
exactly; a causal first row can only see the first key so its output IS the first value row; and
uniform values make attention the identity on those values whatever the scores are.
"""
from attnk.contract import ATTN_ERR_LENGTH_MISMATCH, ATTN_OK
from attnk.mask import mask_causal_flat
from attnk.sdpa import sdpa_forward_flat, sdpa_scores_flat, sdpa_softmax_rows_flat


fn _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


fn _pseudo(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64]()
    var s = seed
    for _ in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        o.append(Float64(s % 2000 - 1000) / 1000.0)
    return o^


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    var n = 6
    var d = 4
    var q = _pseudo(n * d, 17)
    var k = _pseudo(n * d, 83)
    var v = _pseudo(n * d, 191)
    var nobias = List[Float64]()

    # ── every softmax row sums to one ─────────────────────────────────────────
    var s = sdpa_scores_flat(q, k, n, n, 1, 1, d, -1.0)
    var p = sdpa_softmax_rows_flat(s.values, n, n)
    var worst_sum = 0.0
    for r in range(n):
        var total = 0.0
        for c in range(n):
            total += p.values[r * n + c]
        var err = _abs(total - 1.0)
        if err > worst_sum:
            worst_sum = err
    if s.status == ATTN_OK and p.status == ATTN_OK and worst_sum < 1e-15:
        passed += 1
        print("  ✅ every softmax row sums to 1 — worst error", worst_sum)
    else:
        failed += 1
        print("  ❌ a softmax row did not sum to 1:", worst_sum)

    # Stability: shifting every score by a large constant must not change the probabilities. Without
    # max-subtraction this overflows to inf and the row becomes NaN.
    var shifted = List[Float64]()
    for i in range(len(s.values)):
        shifted.append(s.values[i] + 800.0)
    var p2 = sdpa_softmax_rows_flat(shifted, n, n)
    var shift_ok = p2.status == ATTN_OK
    for i in range(len(p.values)):
        if _abs(p.values[i] - p2.values[i]) > 1e-12:
            shift_ok = False
    if shift_ok:
        passed += 1
        print("  ✅ shifting all scores by +800 leaves probabilities unchanged — max-subtracted")
    else:
        failed += 1
        print("  ❌ the softmax is not numerically stable under a large shift")

    # ── a single key returns that value exactly ───────────────────────────────
    var q1 = _pseudo(d, 3)
    var k1 = _pseudo(d, 4)
    var v1 = _pseudo(d, 5)
    var one = sdpa_forward_flat(q1, k1, v1, nobias, 1, 1, 1, 1, d, -1.0, False)
    var one_ok = one.status == ATTN_OK
    for e in range(d):
        if _abs(one.out[e] - v1[e]) > 1e-15:
            one_ok = False
    if one_ok:
        passed += 1
        print("  ✅ attention over one key returns that key's value exactly")
    else:
        failed += 1
        print("  ❌ the single-key case is wrong")

    # ── causal row 0 sees only key 0 ──────────────────────────────────────────
    var cm = mask_causal_flat(n, n, 0)
    var oc = sdpa_forward_flat(q, k, v, cm.bias, n, n, 1, 1, d, -1.0, True)
    var row0_ok = oc.status == ATTN_OK
    for e in range(d):
        if _abs(oc.out[e] - v[e]) > 1e-9:
            row0_ok = False
    if row0_ok:
        passed += 1
        print("  ✅ under a causal mask the first query's output IS the first value row")
    else:
        failed += 1
        print("  ❌ causal masking is not restricting the first row")

    # ── uniform values make attention the identity on them ────────────────────
    # Whatever the scores, a convex combination of identical vectors is that vector. This isolates
    # the value-weighting path from the score path entirely.
    var vu = List[Float64]()
    for _ in range(n):
        for e in range(d):
            vu.append(Float64(e) * 1.5 - 2.0)
    var ou = sdpa_forward_flat(q, k, vu, nobias, n, n, 1, 1, d, -1.0, False)
    var uni_ok = ou.status == ATTN_OK
    for i in range(n):
        for e in range(d):
            if _abs(ou.out[i * d + e] - (Float64(e) * 1.5 - 2.0)) > 1e-12:
                uni_ok = False
    if uni_ok:
        passed += 1
        print("  ✅ identical value rows pass through unchanged, whatever the scores")
    else:
        failed += 1
        print("  ❌ the value-weighting path is wrong")

    # ── lse is finite and consistent ──────────────────────────────────────────
    var lse_ok = len(ou.lse) == n
    for i in range(n):
        if ou.lse[i] < -1.0e300 or ou.lse[i] > 1.0e300:
            lse_ok = False
    if lse_ok:
        passed += 1
        print("  ✅ the log-sum-exp is finite for every row")
    else:
        failed += 1
        print("  ❌ an lse value is not finite")

    # ── GQA ───────────────────────────────────────────────────────────────────
    var qg = _pseudo(n * 4 * d, 61)
    var kg = _pseudo(n * 2 * d, 62)
    var vg = _pseudo(n * 2 * d, 63)
    var og = sdpa_forward_flat(qg, kg, vg, nobias, n, n, 4, 2, d, -1.0, False)
    if og.status == ATTN_OK and len(og.out) == n * 4 * d:
        passed += 1
        print("  ✅ grouped-query attention produces one output row per QUERY head")
    else:
        failed += 1
        print("  ❌ GQA output shape is wrong")

    if sdpa_forward_flat(qg, kg, vg, nobias, n, n, 4, 3, d, -1.0, False).status != ATTN_OK:
        passed += 1
        print("  ✅ a non-divisible head pairing is refused here too")
    else:
        failed += 1
        print("  ❌ a non-divisible pairing was accepted")

    # ── the guards the A-Z harness cannot reach ───────────────────────────────
    if sdpa_forward_flat(q, k, v, nobias, 99, n, 1, 1, d, -1.0, False).status == ATTN_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ a token count larger than the buffer is refused, not an abort")
    else:
        failed += 1
        print("  ❌ the token count was not bounded")

    var short_bias = List[Float64]()
    short_bias.append(0.0)
    if sdpa_forward_flat(q, k, v, short_bias, n, n, 1, 1, d, -1.0, True).status == ATTN_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ a bias smaller than the score matrix is refused")
    else:
        failed += 1
        print("  ❌ a short bias was accepted")

    if sdpa_softmax_rows_flat(s.values, 99, 99).status == ATTN_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ a softmax shape larger than the buffer is refused")
    else:
        failed += 1
        print("  ❌ the softmax shape was not bounded")

    var lf5 = List[Float64]()
    for _ in range(5):
        lf5.append(0.5)
    if sdpa_forward_flat(lf5, lf5, lf5, lf5, 5, 5, 5, 5, 5, -1.0, False).status != ATTN_OK:
        passed += 1
        print("  ✅ the A-Z call shape is refused rather than aborting the worker")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted")

    print("  [attnk.sdpa] Passed:", passed, "Failed:", failed)
