"""test_attnk_mask.mojo — known-value tests for attention masks.

Hand-written. Every assertion targets a mask bug that produces a working model rather than an error:

* **A decode step with no cache offset** attends to the beginning of its context instead of the end.
  It generates fluent text, so nothing looks wrong.
* **Packed sequences without a block-diagonal mask** let document two attend to document one. Loss
  goes down, the run looks healthy, and the model learns attention that will never exist at inference.
* **A fully-masked row** is where a `-inf` convention turns into NaN across the whole tensor.
* **Two frozen causal kernels** return different things for the same input, and a caller who assumed
  they were interchangeable would be adding a logit to a score.
"""
from attnk.contract import ATTN_ERR_BAD_CU_SEQLENS, ATTN_ERR_EMPTY_DIM, ATTN_OK
from attnk.mask import (
    MASK_NEG,
    mask_block_diagonal_flat,
    mask_causal_flat,
    mask_combine_flat,
    mask_convention_agreement,
    mask_padding_flat,
    mask_row_fully_masked,
    mask_sliding_window_flat,
)
from transformer_attention import causal_mask_value
from transformer_blocks import causal_mask_logit


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── the two frozen kernels are different functions, not two spellings ─────
    var ag = mask_convention_agreement(5.0, 3.0, 2.0)
    if ag.additive_bias == 0.0 and ag.masked_logit == 2.0 and not ag.same_shape:
        passed += 1
        print("  ✅ on an UNMASKED pair the frozen kernels return 0.0 (bias) and 2.0 (the logit)")
    else:
        failed += 1
        print("  ❌ the frozen convention delta drifted:", ag.additive_bias, ag.masked_logit)

    var agm = mask_convention_agreement(3.0, 5.0, 2.0)
    if agm.additive_bias == MASK_NEG and agm.masked_logit == MASK_NEG and agm.same_shape:
        passed += 1
        print("  ✅ on a MASKED pair they coincide — which is exactly why the difference hides")
    else:
        failed += 1
        print("  ❌ masked-pair behaviour changed")

    if causal_mask_value(5.0, 3.0) == 0.0 and causal_mask_logit(2.0, 5.0, 3.0) == 2.0:
        passed += 1
        print("  ✅ both frozen causal kernels are reachable and unchanged")
    else:
        failed += 1
        print("  ❌ a frozen causal kernel changed")

    # ── causal is lower-triangular ────────────────────────────────────────────
    var c = mask_causal_flat(3, 3, 0)
    # row 0 sees only key 0; row 2 sees all three. 3 masked cells in a 3x3.
    if (
        c.status == ATTN_OK
        and c.n_masked == 3
        and c.bias[0] == 0.0
        and c.bias[1] == MASK_NEG
        and c.bias[2] == MASK_NEG
        and c.bias[6] == 0.0
        and c.bias[8] == 0.0
    ):
        passed += 1
        print("  ✅ causal bias is lower-triangular with the right cells masked")
    else:
        failed += 1
        print("  ❌ causal mask shape is wrong, masked =", c.n_masked)

    # ── the decode offset ─────────────────────────────────────────────────────
    # One query against four cached keys. With the offset the query is at position 3 and sees all
    # four. Without it the query reads as position 0 and sees only the FIRST — so the model attends
    # to the start of its context instead of the end, and still produces fluent output.
    if mask_causal_flat(1, 4, 3).n_masked == 0:
        passed += 1
        print("  ✅ a decode step with offset=3 sees all 4 cached keys")
    else:
        failed += 1
        print("  ❌ the KV-cache offset is not applied")

    if mask_causal_flat(1, 4, 0).n_masked == 3:
        passed += 1
        print("  ✅ without the offset the same call masks 3 of 4 — the bug the offset prevents")
    else:
        failed += 1
        print("  ❌ the no-offset case did not behave as documented")

    if mask_causal_flat(1, 4, -1).status == ATTN_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ a negative offset is refused")
    else:
        failed += 1
        print("  ❌ a negative offset was accepted")

    # ── sliding window is strictly more restrictive than causal ───────────────
    var w = mask_sliding_window_flat(4, 4, 2, 0)
    var plain = mask_causal_flat(4, 4, 0)
    if w.status == ATTN_OK and w.n_masked > plain.n_masked:
        passed += 1
        print("  ✅ a sliding window masks strictly more than causal alone:", w.n_masked, ">", plain.n_masked)
    else:
        failed += 1
        print("  ❌ the window added no restriction")

    # window <= 0 means unbounded, so it must equal plain causal exactly.
    var unbounded = mask_sliding_window_flat(4, 4, 0, 0)
    if unbounded.n_masked == plain.n_masked:
        passed += 1
        print("  ✅ window <= 0 means unbounded and reduces to plain causal")
    else:
        failed += 1
        print("  ❌ an unbounded window changed the mask")

    # ── packed sequences ──────────────────────────────────────────────────────
    # Two documents of 2 tokens each. Non-causal: each token sees its own document only, so the two
    # off-diagonal 2x2 blocks are masked = 8 cells of 16.
    var cu = List[Int]()
    cu.append(0)
    cu.append(2)
    cu.append(4)
    var bd = mask_block_diagonal_flat(cu, 2, 4, False)
    if bd.status == ATTN_OK and bd.n_masked == 8 and bd.bias[0 * 4 + 1] == 0.0 and bd.bias[0 * 4 + 2] == MASK_NEG:
        passed += 1
        print("  ✅ packed documents cannot see each other — the cross-document blocks are masked")
    else:
        failed += 1
        print("  ❌ block-diagonal mask is wrong, masked =", bd.n_masked)

    # Causal within each document as well: adds the upper triangle of each 2x2 block.
    var bdc = mask_block_diagonal_flat(cu, 2, 4, True)
    if bdc.n_masked == 10 and bdc.bias[0 * 4 + 1] == MASK_NEG and bdc.bias[1 * 4 + 0] == 0.0:
        passed += 1
        print("  ✅ causal packing masks the future within each document too")
    else:
        failed += 1
        print("  ❌ causal block-diagonal is wrong, masked =", bdc.n_masked)

    # A cu_seqlens that does not start at 0 or does not end at total is malformed, and using it
    # would silently mask the wrong tokens.
    var bad = List[Int]()
    bad.append(1)
    bad.append(4)
    if mask_block_diagonal_flat(bad, 1, 4, False).status == ATTN_ERR_BAD_CU_SEQLENS:
        passed += 1
        print("  ✅ a cu_seqlens not starting at 0 is refused")
    else:
        failed += 1
        print("  ❌ a malformed cu_seqlens was accepted")

    var short_cu = List[Int]()
    short_cu.append(0)
    if mask_block_diagonal_flat(short_cu, 3, 4, False).status == ATTN_ERR_BAD_CU_SEQLENS:
        passed += 1
        print("  ✅ fewer boundaries than sequences is refused, not an out-of-bounds read")
    else:
        failed += 1
        print("  ❌ a short cu_seqlens was not bounded")

    # ── padding masks keys only ───────────────────────────────────────────────
    var p = mask_padding_flat(2, 2, 4)
    if p.status == ATTN_OK and p.n_masked == 4 and p.bias[0] == 0.0 and p.bias[2] == MASK_NEG:
        passed += 1
        print("  ✅ padding masks keys at or beyond valid_len, in every query row")
    else:
        failed += 1
        print("  ❌ padding mask is wrong, masked =", p.n_masked)

    # ── composition is addition, and stays finite ─────────────────────────────
    var comb = mask_combine_flat(c.bias, c.bias, 9)
    if comb.status == ATTN_OK and comb.bias[1] == 2.0 * MASK_NEG and comb.bias[0] == 0.0:
        passed += 1
        print("  ✅ two masks compose by addition; a doubly-masked cell is -2e9")
    else:
        failed += 1
        print("  ❌ mask composition is wrong")

    # The whole reason for -1e9 over -inf: the sum stays finite, so softmax cannot produce NaN.
    if comb.bias[1] > -1.0e30 and comb.bias[1] < 0.0:
        passed += 1
        print("  ✅ the composed bias is still finite — a -inf convention would be NaN by now")
    else:
        failed += 1
        print("  ❌ composition produced a non-finite bias")

    # ── fully-masked rows are detectable ──────────────────────────────────────
    var none_valid = mask_padding_flat(0, 2, 3)
    if mask_row_fully_masked(none_valid.bias, 2, 3) == 2:
        passed += 1
        print("  ✅ fully-masked rows are counted — the case a -inf mask turns into NaN")
    else:
        failed += 1
        print("  ❌ fully-masked rows were not detected")

    if mask_row_fully_masked(c.bias, 3, 3) == 0:
        passed += 1
        print("  ✅ a plain causal mask has no fully-masked row")
    else:
        failed += 1
        print("  ❌ causal reported a fully-masked row")

    if mask_row_fully_masked(c.bias, 99, 99) == -1:
        passed += 1
        print("  ✅ a shape larger than the buffer returns -1, not an out-of-bounds scan")
    else:
        failed += 1
        print("  ❌ the row scan was not bounded")

    print("  [attnk.mask] Passed:", passed, "Failed:", failed)
