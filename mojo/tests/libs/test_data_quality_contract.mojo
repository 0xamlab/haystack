"""test_data_quality_contract.mojo — known-value tests for the package vocabulary.

Hand-written. Every expected number below is either derived by hand or taken from a named
reference; nothing is compared against another call to the same function.

References used
---------------
* DBL_EPSILON is 2^-52 = 2.220446049250313e-16 (IEEE 754 binary64 spacing at 1.0), so
  4*eps = 8.881784197001252e-16 and 64*eps = 1.4210854715202004e-14.
* The rounding expectations match CPython's `math.floor(v*10**d + 0.5)/10**d`, computed
  independently: 1.23456 -> 1.23, 0.125 -> 0.13, 2.5 -> 3.0, -2.5 -> -3.0, and
  1.005 -> 1.0 because 1.005 is 1.00499999999999989... in binary64, which is the case a
  "round half up" implementation gets wrong if it multiplies by 100 and adds 0.5 in a
  different order.
* `3 * 6148914691236517206` is 2 in wrapping 64-bit arithmetic. That is the input that
  walked past a `rows * cols != len(dense)` guard in `sparse_numerics.csr` and crashed the
  worker, and it is asserted here as an integer identity before it is used as a shape.
* DQ_MAX_WORK is 2^22 = 4194304, so the budget admits 4194304 // 3 = 1398101 rows at three
  work units per row, and 4194304 rows at one unit per row.
* The prefix extractors are checked against the same 2x3 table as `dq_column`,
  [[10, 11, 12], [20, 21, 22]], whose column 1 is [11, 21] — so its ONE-row prefix is
  exactly [11], readable off the literal.
"""
from std.math import abs as fabs

from data_quality.contract import (
    DQ_DBL_EPSILON,
    DQ_ERR_COLUMN_INDEX,
    DQ_ERR_MASK_LENGTH,
    DQ_ERR_NEGATIVE_SHAPE,
    DQ_ERR_ROWS_TOO_LARGE,
    DQ_ERR_TABLE_SHAPE,
    DQ_ERR_WORK_BUDGET,
    DQ_MAX_DECIMALS,
    DQ_MAX_ROWS,
    DQ_MAX_WORK,
    DQ_OK,
    dq_column,
    dq_column_mask,
    dq_column_mask_prefix,
    dq_column_prefix,
    dq_decimal_scale,
    dq_is_finite,
    dq_live_and_finite,
    dq_mask_all_valid,
    dq_mask_defect,
    dq_quantize,
    dq_quantize_exact,
    dq_relative_tolerance,
    dq_rows_within_budget,
    dq_status_name,
    dq_table_defect,
    dq_ulp_tolerance,
    dq_values_equal,
    dq_work_fits,
)


def _nan() -> Float64:
    var zero: Float64 = 0.0
    return zero / zero


def _inf() -> Float64:
    var zero: Float64 = 0.0
    return 1.0 / zero


def _table6() -> List[Float64]:
    """A 2x3 row-major table: [[10, 11, 12], [20, 21, 22]]."""
    var t = List[Float64]()
    t.append(10.0)
    t.append(11.0)
    t.append(12.0)
    t.append(20.0)
    t.append(21.0)
    t.append(22.0)
    return t^


def check():
    var passed = 0
    var failed = 0

    # ── the wrapping multiply, asserted as arithmetic before it is a shape ─────
    var wrap_a = 3
    var wrap_b = 6148914691236517206
    if wrap_a * wrap_b == 2:
        passed += 1
        print("  ✅ 3 * 6148914691236517206 == 2 — a product comparison is not a bound")
    else:
        failed += 1
        print("  ❌ the wrapping identity does not hold on this platform:", wrap_a * wrap_b)

    if not dq_work_fits(wrap_a, wrap_b):
        passed += 1
        print("  ✅ dq_work_fits refuses the wrapping pair (division, not multiplication)")
    else:
        failed += 1
        print("  ❌ dq_work_fits accepted a pair whose product wraps to 2")

    var two_cells = List[Float64]()
    two_cells.append(1.0)
    two_cells.append(2.0)
    if dq_table_defect(two_cells, wrap_a, wrap_b) != DQ_OK:
        passed += 1
        print("  ✅ the measured crash shape is refused, not indexed")
    else:
        failed += 1
        print("  ❌ dq_table_defect accepted rows=3 cols=6148914691236517206 over 2 cells")

    # ── tolerances: DBL_EPSILON times the judged quantity, and nothing else ────
    if DQ_DBL_EPSILON == 2.220446049250313e-16:
        passed += 1
        print("  ✅ DQ_DBL_EPSILON is 2^-52")
    else:
        failed += 1
        print("  ❌ DQ_DBL_EPSILON is", DQ_DBL_EPSILON)

    if dq_relative_tolerance(1.0, 0.0) == 2.220446049250313e-16:
        passed += 1
        print("  ✅ relative tolerance at magnitude 1.0 is exactly one epsilon")
    else:
        failed += 1
        print("  ❌ tolerance at 1.0 is", dq_relative_tolerance(1.0, 0.0))

    if dq_relative_tolerance(8.0, 0.0) == 1.7763568394002505e-15:
        passed += 1
        print("  ✅ relative tolerance scales linearly: 8.0 -> 8 epsilon")
    else:
        failed += 1
        print("  ❌ tolerance at 8.0 is", dq_relative_tolerance(8.0, 0.0))

    # Spelling 3 of rule 4b: a `1 + |x|` floor turns a relative test into an absolute one
    # at a scale the caller never chose. At |x| = 1e-13 the honest tolerance is ~2.2e-29;
    # a floored one would be ~2.2e-16, thirteen orders of magnitude too slack.
    var tiny_tol = dq_relative_tolerance(1e-13, 0.0)
    if tiny_tol < 1e-28 and tiny_tol > 0.0:
        passed += 1
        print("  ✅ no 1+|x| floor: tolerance at 1e-13 is", tiny_tol, "not ~1e-16")
    else:
        failed += 1
        print("  ❌ tolerance at 1e-13 is", tiny_tol, "— a floor is doing the work")

    # Spelling 4: the caller's tolerance is ADDITIVE, never a multiplier on a magnitude.
    if dq_relative_tolerance(1e6, 0.25) == 0.25 + DQ_DBL_EPSILON * 1e6:
        passed += 1
        print("  ✅ the caller's tolerance is added, not multiplied by the magnitude")
    else:
        failed += 1
        print("  ❌ absolute tolerance is being scaled:", dq_relative_tolerance(1e6, 0.25))

    # A nan threshold makes every `error > tol` test False, so an audit built on one passes
    # having counted zero violations. Refuse to build a tolerance from a non-finite.
    if dq_relative_tolerance(_nan(), 0.5) == 0.5 and dq_ulp_tolerance(_nan(), 8) == 0.0:
        passed += 1
        print("  ✅ a non-finite magnitude contributes nothing to a tolerance")
    else:
        failed += 1
        print("  ❌ a nan magnitude leaked into a tolerance")

    if (
        dq_ulp_tolerance(1.0, 4) == 8.881784197001252e-16
        and dq_ulp_tolerance(1.0, -5) == 0.0
        and dq_ulp_tolerance(1.0, 1000) == 1.4210854715202004e-14
    ):
        passed += 1
        print("  ✅ ulp tolerance is ulps*eps*|x|, clamped to [0, 64] ulps")
    else:
        failed += 1
        print("  ❌ ulp tolerance wrong:", dq_ulp_tolerance(1.0, 4), dq_ulp_tolerance(1.0, 1000))

    # ── the stated float equality ─────────────────────────────────────────────
    if dq_values_equal(-0.0, 0.0):
        passed += 1
        print("  ✅ -0.0 and +0.0 are the same key")
    else:
        failed += 1
        print("  ❌ -0.0 and +0.0 hash to different keys")

    if dq_values_equal(_nan(), _nan()):
        passed += 1
        print("  ✅ every NaN is one key, not one key per row")
    else:
        failed += 1
        print("  ❌ NaN is not self-equal under the package identity")

    if not dq_values_equal(1.0, 1.0 + DQ_DBL_EPSILON * 2.0):
        passed += 1
        print("  ✅ the identity is exact: 1.0 and 1.0+2eps are different keys")
    else:
        failed += 1
        print("  ❌ the identity is not exact")

    if dq_is_finite(1.0) and not dq_is_finite(_nan()) and not dq_is_finite(_inf()):
        passed += 1
        print("  ✅ dq_is_finite agrees with numeric.reduce on nan and inf")
    else:
        failed += 1
        print("  ❌ dq_is_finite disagrees with the frozen definition")

    # ── the declared decimal grid ─────────────────────────────────────────────
    if (
        dq_decimal_scale(0) == 1.0
        and dq_decimal_scale(3) == 1000.0
        and dq_decimal_scale(15) == 1.0e15
        and dq_decimal_scale(16) == 0.0
        and dq_decimal_scale(-1) == 0.0
    ):
        passed += 1
        print("  ✅ decimal scale is exact for 0..15 and 0.0 (refusal) outside")
    else:
        failed += 1
        print("  ❌ decimal scale wrong:", dq_decimal_scale(3), dq_decimal_scale(16))

    if (
        dq_quantize(1.23456, 2) == 1.23
        and dq_quantize(0.125, 2) == 0.13
        and dq_quantize(2.5, 0) == 3.0
        and dq_quantize(-2.5, 0) == -3.0
        and dq_quantize(1.005, 2) == 1.0
    ):
        passed += 1
        print("  ✅ rounding matches the CPython reference, 1.005 -> 1.0 included")
    else:
        failed += 1
        print(
            "  ❌ rounding wrong:",
            dq_quantize(1.23456, 2), dq_quantize(0.125, 2),
            dq_quantize(2.5, 0), dq_quantize(-2.5, 0), dq_quantize(1.005, 2),
        )

    # Rule 4c: `Float64(Int(v))` outside Int's range is undefined, not truncated, and a
    # finiteness guard does not catch it because 1e300 is finite. The grid must REFUSE.
    if not dq_quantize_exact(1e300, 2) and dq_quantize(1e300, 2) == 1e300:
        passed += 1
        print("  ✅ 1e300 is not placeable on a 2-place grid, and is returned unchanged")
    else:
        failed += 1
        print("  ❌ 1e300 was 'rounded' to", dq_quantize(1e300, 2))

    if (
        not dq_quantize_exact(_nan(), 2)
        and not dq_quantize_exact(_inf(), 2)
        and not dq_quantize_exact(1.0, DQ_MAX_DECIMALS + 1)
        and dq_quantize_exact(1.0, 2)
    ):
        passed += 1
        print("  ✅ quantize_exact refuses non-finites and an out-of-range grid")
    else:
        failed += 1
        print("  ❌ quantize_exact accepted something unplaceable")

    # ── table shape and the guarded column extractor ──────────────────────────
    var t = _table6()
    if dq_table_defect(t, 2, 3) == DQ_OK:
        passed += 1
        print("  ✅ 2x3 over 6 cells is a sound shape")
    else:
        failed += 1
        print("  ❌ 2x3 over 6 cells refused:", dq_status_name(dq_table_defect(t, 2, 3)))

    var short = List[Float64]()
    short.append(1.0)
    if dq_table_defect(short, 2, 3) == DQ_ERR_TABLE_SHAPE:
        passed += 1
        print("  ✅ 2x3 over 1 cell is refused as a shape defect")
    else:
        failed += 1
        print("  ❌ a short table was accepted")

    if (
        dq_table_defect(t, -1, 3) == DQ_ERR_NEGATIVE_SHAPE
        and dq_table_defect(t, 2, -3) == DQ_ERR_NEGATIVE_SHAPE
    ):
        passed += 1
        print("  ✅ a negative dimension is refused in both positions")
    else:
        failed += 1
        print("  ❌ a negative dimension was accepted")

    if dq_table_defect(t, DQ_MAX_ROWS + 1, 1) == DQ_ERR_ROWS_TOO_LARGE:
        passed += 1
        print("  ✅ the row ceiling is enforced before any shape arithmetic")
    else:
        failed += 1
        print("  ❌ the row ceiling was not enforced")

    var big_cells = List[Float64]()
    if dq_table_defect(big_cells, 4096, 4096) == DQ_ERR_WORK_BUDGET:
        passed += 1
        print("  ✅ 4096x4096 = 16.7M cells exceeds the 4.19M work budget and is refused")
    else:
        failed += 1
        print("  ❌ the work budget was not charged for table cells")

    var col1 = dq_column(t, 2, 3, 1)
    if len(col1) == 2 and col1[0] == 11.0 and col1[1] == 21.0:
        passed += 1
        print("  ✅ column 1 of [[10,11,12],[20,21,22]] is [11, 21]")
    else:
        failed += 1
        print("  ❌ column extraction wrong, length", len(col1))

    # A negative subscript is the fatal direction: `range(-1)` reads nothing but
    # `table[-1]` ends the process. Both directions must yield an empty result.
    if len(dq_column(t, 2, 3, -1)) == 0 and len(dq_column(t, 2, 3, 3)) == 0:
        passed += 1
        print("  ✅ a column index out of range in either direction yields nothing")
    else:
        failed += 1
        print("  ❌ an out-of-range column index was indexed")

    # ── the PREFIX extractors: bounding memory is not bounding work ───────────
    # A driver that truncates to a row prefix must copy the prefix, not the column. The
    # 2x3 table above is [[10,11,12],[20,21,22]], so one row of column 1 is exactly [11].
    var pre1 = dq_column_prefix(t, 2, 3, 1, 1)
    if len(pre1) == 1 and pre1[0] == 11.0:
        passed += 1
        print("  ✅ one row of column 1 is [11.0] — the prefix, not the whole column")
    else:
        failed += 1
        print("  ❌ prefix extraction wrong, length", len(pre1))

    var pre_all = dq_column_prefix(t, 2, 3, 1, 2)
    var pre_clamped = dq_column_prefix(t, 2, 3, 1, 9)
    if (
        len(pre_all) == 2 and pre_all[0] == 11.0 and pre_all[1] == 21.0
        and len(pre_clamped) == 2
        and len(dq_column_prefix(t, 2, 3, 1, 0)) == 0
        and len(dq_column_prefix(t, 2, 3, 1, -4)) == 0
    ):
        passed += 1
        print("  ✅ rows is a COUNT: clamped to [0, n_rows] in both directions, never a read")
    else:
        failed += 1
        print("  ❌ the prefix row count was not clamped:", len(pre_clamped))

    # `col` is still a SUBSCRIPT here, so it is still refused in both directions.
    if (
        len(dq_column_prefix(t, 2, 3, -1, 2)) == 0
        and len(dq_column_prefix(t, 2, 3, 3, 2)) == 0
        and len(dq_column_prefix(short, 2, 3, 1, 2)) == 0
    ):
        passed += 1
        print("  ✅ the prefix extractor refuses every input dq_column refuses")
    else:
        failed += 1
        print("  ❌ the prefix extractor is weaker than dq_column")

    var tmask = dq_mask_all_valid(6)
    tmask[4] = False
    var cm = dq_column_mask(tmask, 2, 3, 1)
    if len(cm) == 2 and cm[0] and not cm[1]:
        passed += 1
        print("  ✅ the column mask follows the same row-major layout as the table")
    else:
        failed += 1
        print("  ❌ column mask wrong")

    # tmask marks position 4 = row 1, column 1 absent, so a one-row prefix of column 1 is
    # [True] and the full two-row prefix is [True, False].
    var cmp1 = dq_column_mask_prefix(tmask, 2, 3, 1, 1)
    var cmp2 = dq_column_mask_prefix(tmask, 2, 3, 1, 2)
    if (
        len(cmp1) == 1 and cmp1[0]
        and len(cmp2) == 2 and cmp2[0] and not cmp2[1]
        and len(dq_column_mask_prefix(tmask, 2, 3, 1, 99)) == 2
        and len(dq_column_mask_prefix(tmask, 2, 3, -1, 2)) == 0
        and len(dq_column_mask_prefix(tmask, 2, 3, 3, 2)) == 0
    ):
        passed += 1
        print("  ✅ the mask prefix matches the value prefix row for row, and is guarded alike")
    else:
        failed += 1
        print("  ❌ mask prefix wrong:", len(cmp1), len(cmp2))

    # ── the mask contract: exact length or refusal ─────────────────────────────
    var m3 = dq_mask_all_valid(3)
    if dq_mask_defect(m3, 3) == DQ_OK:
        passed += 1
        print("  ✅ a mask of exactly n_rows is accepted")
    else:
        failed += 1
        print("  ❌ an exact mask was refused")

    if dq_mask_defect(m3, 4) == DQ_ERR_MASK_LENGTH and dq_mask_defect(m3, 2) == DQ_ERR_MASK_LENGTH:
        passed += 1
        print("  ✅ a short OR long mask is refused, never padded to 'all absent'")
    else:
        failed += 1
        print("  ❌ a mismatched mask length was tolerated")

    if dq_mask_defect(m3, -1) == DQ_ERR_NEGATIVE_SHAPE:
        passed += 1
        print("  ✅ a negative row count is refused")
    else:
        failed += 1
        print("  ❌ a negative row count was accepted")

    if len(dq_mask_all_valid(3)) == 3 and m3[0] and m3[2]:
        passed += 1
        print("  ✅ dq_mask_all_valid(3) is three present positions")
    else:
        failed += 1
        print("  ❌ dq_mask_all_valid wrong")

    if len(dq_mask_all_valid(-1)) == 0 and len(dq_mask_all_valid(DQ_MAX_ROWS + 1)) == 0:
        passed += 1
        print("  ✅ dq_mask_all_valid refuses a negative and an over-ceiling request")
    else:
        failed += 1
        print("  ❌ dq_mask_all_valid allocated an unbounded mask")

    # ── the live-and-finite mask: three facts, not two ────────────────────────
    var v = List[Float64]()
    v.append(1.0)
    v.append(_nan())
    v.append(3.0)
    var vm = List[Bool]()
    vm.append(True)
    vm.append(True)
    vm.append(False)
    var live = dq_live_and_finite(v, vm)
    if len(live) == 3 and live[0] and not live[1] and not live[2]:
        passed += 1
        print("  ✅ present-and-finite excludes a present NaN and an absent value alike")
    else:
        failed += 1
        print("  ❌ live-and-finite mask wrong")

    # ── the work budget arithmetic ────────────────────────────────────────────
    if DQ_MAX_WORK == 4194304:
        passed += 1
        print("  ✅ DQ_MAX_WORK is 2^22")
    else:
        failed += 1
        print("  ❌ DQ_MAX_WORK is", DQ_MAX_WORK)

    if (
        dq_rows_within_budget(1000000000, 3) == 1398101
        and dq_rows_within_budget(100, 3) == 100
        and dq_rows_within_budget(100, 0) == 0
        and dq_rows_within_budget(-5, 3) == 0
    ):
        passed += 1
        print("  ✅ 4194304 // 3 = 1398101 rows admitted; a zero unit cost admits none")
    else:
        failed += 1
        print("  ❌ budget arithmetic wrong:", dq_rows_within_budget(1000000000, 3))

    # This function CLAMPS `n_rows` against the budget; it does NOT validate it against
    # DQ_MAX_ROWS, and it used to declare that it did. DQ_MAX_ROWS + 1 rows at one work unit
    # each therefore answers DQ_MAX_WORK = 4194304, not 0. Pinning the answer pins the
    # corrected `[clamped]` declaration: if anyone later "enforces" the withdrawn
    # `n_rows <= DQ_MAX_ROWS [kernel_validated]` claim by returning 0 here, this fails.
    if (
        dq_rows_within_budget(DQ_MAX_ROWS + 1, 1) == DQ_MAX_WORK
        and dq_rows_within_budget(DQ_MAX_ROWS + 1, 1) != 0
    ):
        passed += 1
        print("  ✅ over-ceiling n_rows is CLAMPED to the budget here, not refused —")
        print("     the row ceiling is dq_table_defect's question, enforced in one place")
    else:
        failed += 1
        print(
            "  ❌ the budget helper changed its answer for an over-ceiling n_rows:",
            dq_rows_within_budget(DQ_MAX_ROWS + 1, 1),
        )

    # ── one vocabulary across every sub-range ─────────────────────────────────
    if (
        dq_status_name(DQ_OK) == "ok"
        and dq_status_name(410) == "no_columns_to_profile"
        and dq_status_name(425) == "plan_uses_an_op_the_columnar_evaluator_cannot_run"
        and dq_status_name(433) == "proven_feature_is_an_affine_image_of_the_target"
        and dq_status_name(442) == "duplicate_key_column_listed_twice"
        and dq_status_name(999) == "unknown_status_999"
    ):
        passed += 1
        print("  ✅ one status vocabulary resolves all five sub-ranges and names the rest")
    else:
        failed += 1
        print("  ❌ status vocabulary incomplete:", dq_status_name(425), dq_status_name(442))

    if dq_status_name(DQ_ERR_COLUMN_INDEX) == "column_index_out_of_range":
        passed += 1
        print("  ✅ a contract-range code resolves too")
    else:
        failed += 1
        print("  ❌ contract-range code unnamed")

    print("  [data_quality.contract] Passed:", passed, "Failed:", failed)


def main():
    check()
