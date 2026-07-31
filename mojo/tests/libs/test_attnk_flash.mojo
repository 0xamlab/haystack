"""test_attnk_flash.mojo — known-value tests for tiled attention.

Hand-written. The claim is "same answer as the materialized reference, without the score matrix", so
the assertions are equalities against `attnk.sdpa` plus two properties that a single comparison
cannot express:

* **Block-size invariance.** The online recurrence must give bit-identical results for every block
  size, because the block boundary is a scheduling choice and not part of the definition. If it
  drifts, the rescale correction is being applied at the wrong point — a bug that is invisible at one
  block size and grows with another.
* **The update order.** `flash_block_sum_exp` and `flash_block_output` both consume `(m_old, m_new)`,
  so advancing the running max before them silently drops the correction for everything already
  accumulated. The result is still a valid probability distribution over the wrong weights, which no
  shape or finiteness check would catch.

The lse comparison matters more than the output one: it depends on every score in the row, whereas
the output is a weighted average in which two compensating errors can cancel.
"""
from attnk.contract import ATTN_ERR_LENGTH_MISMATCH, ATTN_OK, attn_status_name
from attnk.flash import flash_agrees_with_sdpa, flash_block_plan, flash_forward_flat
from attnk.mask import mask_causal_flat, mask_padding_flat
from attnk.sdpa import sdpa_forward_flat
from flash_attention import (
    flash_block_max,
    flash_block_output,
    flash_block_sum_exp,
    flash_final_normalize,
)


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

    var nq = 9
    var nk = 21
    var hq = 4
    var hkv = 2
    var d = 8
    var q = _pseudo(nq * hq * d, 11)
    var k = _pseudo(nk * hkv * d, 977)
    var v = _pseudo(nk * hkv * d, 313)
    var nobias = List[Float64]()

    # ── the frozen recurrence is reachable and unchanged ──────────────────────
    # A single step, hand-checked: from m=-1, a score of 3 makes m_new=3, and the running sum
    # rescales by exp(-1-3)=exp(-4).
    var m1 = flash_block_max(-1.0, 3.0)
    var l1 = flash_block_sum_exp(2.0, -1.0, 3.0, 3.0)
    if m1 == 3.0 and _abs(l1 - (2.0 * 2.718281828459045 ** (-4.0) + 1.0)) < 1e-12:
        passed += 1
        print("  ✅ the frozen online-softmax recurrence is reachable and behaves as before")
    else:
        failed += 1
        print("  ❌ a frozen flash kernel changed:", m1, l1)

    if flash_final_normalize(6.0, 3.0) == 2.0 and flash_final_normalize(6.0, 0.0) == 0.0:
        passed += 1
        print("  ✅ final normalize divides, and a zero normalizer gives 0 rather than inf")
    else:
        failed += 1
        print("  ❌ flash_final_normalize changed")

    # ── tiled == materialized, across block sizes ─────────────────────────────
    var blocks = List[Int]()
    blocks.append(1)
    blocks.append(2)
    blocks.append(4)
    blocks.append(8)
    blocks.append(64)
    var all_within = True
    var worst_out = 0.0
    var worst_lse = 0.0
    for bi in range(len(blocks)):
        var ag = flash_agrees_with_sdpa(q, k, v, nobias, nq, nk, hq, hkv, d, -1.0, False, blocks[bi])
        if ag.status != ATTN_OK or not ag.within_tolerance:
            all_within = False
        if ag.max_out_delta > worst_out:
            worst_out = ag.max_out_delta
        if ag.max_lse_delta > worst_lse:
            worst_lse = ag.max_lse_delta
    if all_within:
        passed += 1
        print("  ✅ tiled matches materialized at every block size — out", worst_out, "lse", worst_lse)
    else:
        failed += 1
        print("  ❌ the tiled kernel diverged from the reference")

    # ── block size must not change the answer AT ALL ──────────────────────────
    # Stronger than "within tolerance": the block boundary is a scheduling choice, so two block sizes
    # must produce identical bits. A non-zero delta here means the rescale lands in the wrong place.
    var f1 = flash_forward_flat(q, k, v, nobias, nq, nk, hq, hkv, d, -1.0, False, 1)
    var f64b = flash_forward_flat(q, k, v, nobias, nq, nk, hq, hkv, d, -1.0, False, 64)
    var f7 = flash_forward_flat(q, k, v, nobias, nq, nk, hq, hkv, d, -1.0, False, 7)
    var invariant = 0.0
    for i in range(len(f1.out)):
        var a = _abs(f1.out[i] - f64b.out[i])
        var b = _abs(f1.out[i] - f7.out[i])
        if a > invariant:
            invariant = a
        if b > invariant:
            invariant = b
    if invariant == 0.0:
        passed += 1
        print("  ✅ the answer is bit-identical across block sizes 1, 7 and 64")
    else:
        failed += 1
        print("  ❌ block size changed the answer by", invariant)

    # ...and the block count really did differ, so the invariance is not vacuous.
    if f1.blocks_walked > f64b.blocks_walked * 10:
        passed += 1
        print("  ✅ and it walked", f1.blocks_walked, "vs", f64b.blocks_walked, "blocks — not vacuous")
    else:
        failed += 1
        print("  ❌ the two runs walked a similar number of blocks; invariance proves nothing")

    # ── with masks ────────────────────────────────────────────────────────────
    var cm = mask_causal_flat(nq, nk, nk - nq)
    var agc = flash_agrees_with_sdpa(q, k, v, cm.bias, nq, nk, hq, hkv, d, -1.0, True, 4)
    if agc.status == ATTN_OK and agc.within_tolerance:
        passed += 1
        print("  ✅ agreement holds with a causal mask and a KV-cache offset")
    else:
        failed += 1
        print("  ❌ the masked case diverged:", agc.max_out_delta)

    var pm = mask_padding_flat(nk - 5, nq, nk)
    var agp = flash_agrees_with_sdpa(q, k, v, pm.bias, nq, nk, hq, hkv, d, -1.0, True, 4)
    if agp.status == ATTN_OK and agp.within_tolerance:
        passed += 1
        print("  ✅ agreement holds with a padding mask")
    else:
        failed += 1
        print("  ❌ the padded case diverged:", agp.max_out_delta)

    # ── a single key is the degenerate case that must return V exactly ────────
    # With one key, softmax is 1.0 whatever the score, so the output IS that value row.
    var q1 = _pseudo(1 * 1 * d, 5)
    var k1 = _pseudo(1 * 1 * d, 6)
    var v1 = _pseudo(1 * 1 * d, 7)
    var single = flash_forward_flat(q1, k1, v1, nobias, 1, 1, 1, 1, d, -1.0, False, 1)
    var single_ok = single.status == ATTN_OK
    for e in range(d):
        if _abs(single.out[e] - v1[e]) > 1e-12:
            single_ok = False
    if single_ok:
        passed += 1
        print("  ✅ with one key the output is exactly V — softmax over one element is 1.0")
    else:
        failed += 1
        print("  ❌ the single-key case is wrong")

    # ── GQA ───────────────────────────────────────────────────────────────────
    var ag_mha = flash_agrees_with_sdpa(q, k, v, nobias, nq, nk, 4, 4, d, -1.0, False, 4)
    var kk = _pseudo(nk * 4 * d, 51)
    var vv = _pseudo(nk * 4 * d, 52)
    var ag_full = flash_agrees_with_sdpa(q, kk, vv, nobias, nq, nk, 4, 4, d, -1.0, False, 4)
    if ag_full.status == ATTN_OK and ag_full.within_tolerance:
        passed += 1
        print("  ✅ agreement holds for full multi-head attention as well as grouped")
    else:
        failed += 1
        print("  ❌ the MHA case diverged")
    _ = ag_mha

    # ── planning reports the memory the tiling avoids ─────────────────────────
    var pl = flash_block_plan(32768, 128, 262144)
    if pl.status == ATTN_OK and pl.block_k > 0 and pl.materialized_bytes > 8.0e9:
        passed += 1
        print("  ✅ at 32k context the working set is", pl.working_bytes,
              "bytes against", pl.materialized_bytes, "materialized")
    else:
        failed += 1
        print("  ❌ the plan is wrong")

    if flash_block_plan(0, 128, 262144).status != ATTN_OK:
        passed += 1
        print("  ✅ planning refuses an empty sequence")
    else:
        failed += 1
        print("  ❌ planning accepted an empty sequence")

    # ── the guards the A-Z harness cannot reach ───────────────────────────────
    if flash_forward_flat(q, k, v, nobias, 99, nk, hq, hkv, d, -1.0, False, 4).status != ATTN_OK:
        passed += 1
        print("  ✅ a token count larger than the buffer is refused, not an abort")
    else:
        failed += 1
        print("  ❌ the token count was not bounded")

    var short_bias = List[Float64]()
    short_bias.append(0.0)
    if flash_forward_flat(q, k, v, short_bias, nq, nk, hq, hkv, d, -1.0, True, 4).status == ATTN_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ a bias smaller than the score matrix is refused")
    else:
        failed += 1
        print("  ❌ a short bias was accepted")

    var nan_v = 0.0 / 0.0
    if flash_forward_flat(q, k, v, nobias, nq, nk, hq, hkv, d, nan_v, False, 4).status != ATTN_OK:
        passed += 1
        print("  ✅ a NaN scale is refused before any score is formed")
    else:
        failed += 1
        print("  ❌ a NaN scale was accepted")

    var lf5 = List[Float64]()
    for _ in range(5):
        lf5.append(0.5)
    if flash_forward_flat(lf5, lf5, lf5, lf5, 5, 5, 5, 5, 5, -1.0, False, 5).status != ATTN_OK:
        passed += 1
        print("  ✅ the A-Z call shape is refused rather than aborting the worker")
    else:
        failed += 1
        print("  ❌ the A-Z call shape was accepted")

    print("  [attnk.flash] Passed:", passed, "Failed:", failed)
