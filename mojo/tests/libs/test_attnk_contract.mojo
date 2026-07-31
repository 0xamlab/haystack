"""test_attnk_contract.mojo — known-value tests for the attention status vocabulary and budgets.

Hand-written. The assertion that carries weight is the variable-length work estimate. Attention cost
is quadratic in sequence length, and with packed sequences the naive `n_seq * max_len^2` estimate is
wrong in both directions: it over-charges a batch of short documents and under-charges one containing
a single long document. The under-charge is the dangerous half — it lets the request that actually
runs for hours through the budget.
"""
from attnk.contract import (
    ATTN_ERR_DIM_TOO_LARGE,
    ATTN_ERR_EMPTY_DIM,
    ATTN_ERR_GQA_NOT_DIVISIBLE,
    ATTN_ERR_HEAD_MISMATCH,
    ATTN_ERR_WORK_TOO_LARGE,
    ATTN_MAX_HEAD_DIM,
    ATTN_MAX_SEQ,
    ATTN_MAX_WORK_CELLS,
    ATTN_OK,
    attn_dims_check,
    attn_scalars_ok,
    attn_status_name,
    attn_work_cells_varlen,
    attn_work_fits,
)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── the status vocabulary ─────────────────────────────────────────────────
    var codes = List[Int]()
    codes.append(ATTN_OK)
    codes.append(ATTN_ERR_EMPTY_DIM)
    codes.append(ATTN_ERR_HEAD_MISMATCH)
    codes.append(ATTN_ERR_GQA_NOT_DIVISIBLE)
    codes.append(ATTN_ERR_WORK_TOO_LARGE)
    codes.append(ATTN_ERR_DIM_TOO_LARGE)

    var distinct = True
    var in_range = True
    for i in range(len(codes)):
        if codes[i] < 360 or codes[i] > 379:
            in_range = False
        for j in range(len(codes)):
            if i != j and attn_status_name(codes[i]) == attn_status_name(codes[j]):
                distinct = False
    if distinct and in_range and attn_status_name(1) == String("unknown_status"):
        passed += 1
        print("  ✅ attn statuses are distinct and inside the 360-379 range (rule 4e)")
    else:
        failed += 1
        print("  ❌ attn status codes collide or escaped their range")

    # tensorx owns 300-319 and gemm 320-339; no overlap is allowed.
    var no_overlap = True
    for i in range(len(codes)):
        if codes[i] >= 300 and codes[i] <= 339:
            no_overlap = False
    if no_overlap:
        passed += 1
        print("  ✅ no attn code overlaps the tensorx or gemm ranges")
    else:
        failed += 1
        print("  ❌ an attn status collides with another package")

    # ── GQA divisibility ──────────────────────────────────────────────────────
    if attn_dims_check(1, 32, 8, 128, 128, 64) == ATTN_OK:
        passed += 1
        print("  ✅ 32 query heads over 8 KV heads is accepted")
    else:
        failed += 1
        print("  ❌ a valid GQA configuration was rejected")

    # 32/7 leaves a remainder, so some group would be a different size and every indexing scheme
    # picks a different wrong head for it. The model still produces output.
    if attn_dims_check(1, 32, 7, 128, 128, 64) == ATTN_ERR_GQA_NOT_DIVISIBLE:
        passed += 1
        print("  ✅ a non-divisible head pairing is refused — it would silently mis-group heads")
    else:
        failed += 1
        print("  ❌ a non-divisible GQA pairing was accepted")

    if attn_dims_check(1, 8, 32, 128, 128, 64) == ATTN_ERR_HEAD_MISMATCH:
        passed += 1
        print("  ✅ more KV heads than query heads is a distinct status, not 'not divisible'")
    else:
        failed += 1
        print("  ❌ inverted head counts were not distinguished")

    if attn_dims_check(1, 32, 32, 128, 128, 64) == ATTN_OK:
        passed += 1
        print("  ✅ full multi-head attention (h_q == h_kv) is the divisible case with group 1")
    else:
        failed += 1
        print("  ❌ MHA was rejected")

    # ── the work budget ───────────────────────────────────────────────────────
    if attn_work_fits(1, 8, 512, 64, ATTN_MAX_WORK_CELLS):
        passed += 1
        print("  ✅ an ordinary shape fits the work budget")
    else:
        failed += 1
        print("  ❌ an ordinary shape was rejected")

    # Five factors with the sequence length squared: the widest opportunity in the package for a
    # wrapping multiply to produce a small number from large ones.
    if not attn_work_fits(1024, 128, ATTN_MAX_SEQ, ATTN_MAX_HEAD_DIM, ATTN_MAX_WORK_CELLS):
        passed += 1
        print("  ✅ a shape whose five-factor product overflows the budget is refused, not wrapped")
    else:
        failed += 1
        print("  ❌ the work budget accepted an overflowing product")

    if (
        not attn_work_fits(0, 8, 128, 64, ATTN_MAX_WORK_CELLS)
        and not attn_work_fits(1, 8, -1, 64, ATTN_MAX_WORK_CELLS)
        and not attn_work_fits(1, 8, 128, 64, 0)
    ):
        passed += 1
        print("  ✅ non-positive dimensions and a zero ceiling do not fit vacuously")
    else:
        failed += 1
        print("  ❌ a non-positive input was accepted")

    if not attn_work_fits(1, 1, ATTN_MAX_SEQ + 1, 8, ATTN_MAX_WORK_CELLS):
        passed += 1
        print("  ✅ a sequence past ATTN_MAX_SEQ is refused before the product is considered")
    else:
        failed += 1
        print("  ❌ an oversize sequence was accepted")

    # ── variable-length work is a sum of squares ──────────────────────────────
    # Two documents, 4 and 32 tokens. True cost is (16 + 1024) = 1040 score cells per head-dim unit.
    # The naive n_seq * max_len^2 estimate would say 2 * 1024 = 2048 — nearly double, and in the
    # other direction it under-charges a long document hidden among short ones.
    var cu = List[Int]()
    cu.append(0)
    cu.append(4)
    cu.append(36)
    var cells = attn_work_cells_varlen(cu, 2, 2, 1)
    if cells == 2080.0:
        passed += 1
        print("  ✅ variable-length work is the per-sequence SUM OF SQUARES, not n_seq * max^2")
    else:
        failed += 1
        print("  ❌ varlen work estimate is wrong:", cells, "expected 2080")

    # Same total tokens, evenly split, must cost strictly less than the skewed packing above.
    var even = List[Int]()
    even.append(0)
    even.append(18)
    even.append(36)
    var even_cells = attn_work_cells_varlen(even, 2, 2, 1)
    if even_cells < cells:
        passed += 1
        print("  ✅ an even split costs less than a skewed one at equal token count:",
              even_cells, "<", cells)
    else:
        failed += 1
        print("  ❌ the estimate is insensitive to how tokens are distributed")

    # Malformed boundaries must be refused, not silently treated as zero-length.
    var bad = List[Int]()
    bad.append(1)
    bad.append(4)
    var short_cu = List[Int]()
    short_cu.append(0)
    if attn_work_cells_varlen(bad, 1, 1, 1) < 0.0 and attn_work_cells_varlen(short_cu, 3, 1, 1) < 0.0:
        passed += 1
        print("  ✅ a cu_seqlens not starting at 0, or too short, returns negative rather than 0")
    else:
        failed += 1
        print("  ❌ a malformed cu_seqlens was accepted")

    # ── NaN scale ─────────────────────────────────────────────────────────────
    var nan_v = 0.0 / 0.0
    var inf_v = 1.0 / 0.0
    if attn_scalars_ok(0.125) and not attn_scalars_ok(nan_v) and not attn_scalars_ok(inf_v):
        passed += 1
        print("  ✅ a NaN or infinite scale is refused (rule 4d: validate before you compare)")
    else:
        failed += 1
        print("  ❌ a non-finite scale was accepted")

    print("  [attnk.contract] Passed:", passed, "Failed:", failed)
