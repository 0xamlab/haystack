"""test_data_quality_expect.mojo — known-value tests for the expectation surface.

Hand-written. The worked table, used throughout, is 3 rows x 2 columns (price, qty):

    row 0:  price =  10.0    qty = 1.0
    row 1:  price = -12.0    qty = 2.0
    row 2:  price = ABSENT   qty = 3.0

`price > 0` therefore has exactly three outcomes, one per row, and they are three
DIFFERENT outcomes: row 0 passes, row 1 VIOLATES with the observed value -12.0, and row 2
is UNKNOWN because a null reached the comparison. The headline assertion is the rendered
sentence, character for character:

    row 1, column 0, expected gt 0.0, got -12.0

The work-budget assertion is derived, not measured: `DQ_MAX_WORK` is 2^22 = 4194304 and
`expect_plan_flat` charges `n_cols + n_nodes` per row, so a 1-column table under a
1024-node plan costs 1025 per row and the budget admits 4194304 // 1025 = 4092 rows. A
4093-row request must report exactly one row NOT CHECKED.

The refused plan is the one measured in `data_quality/expect.mojo`'s module docstring: a
frozen opcode with `left = -1` passes `query.ir.validation_error` and then reads
`values[-1]` inside `query.eval`, which ends the process. Here it must come back as a
status.
"""
from data_quality.contract import (
    DQ_ERR_COLUMN_INDEX,
    DQ_ERR_LENGTH_MISMATCH,
    DQ_ERR_TABLE_SHAPE,
    DQ_OK,
    dq_is_finite,
    dq_mask_all_valid,
)
from data_quality.expect import (
    DQ_EXPECT_BETWEEN,
    DQ_EXPECT_ERR_BOUND_NOT_FINITE,
    DQ_EXPECT_ERR_NOTHING_TO_CHECK,
    DQ_EXPECT_ERR_EVAL_REFUSED,
    DQ_EXPECT_ERR_PLAN_ARRAYS,
    DQ_EXPECT_ERR_PLAN_INVALID,
    DQ_EXPECT_ERR_PLAN_ROOT,
    DQ_EXPECT_ERR_TOO_MANY_EXPECTATIONS,
    DQ_EXPECT_ERR_TOO_MANY_NODES,
    DQ_EXPECT_ERR_UNKNOWN_OP,
    DQ_EXPECT_ERR_UNSUPPORTED_OP,
    DQ_EXPECT_FINITE,
    DQ_EXPECT_GE,
    DQ_EXPECT_GT,
    DQ_EXPECT_LE,
    DQ_EXPECT_NOT_NULL,
    DQ_EXPECT_PLAN_TRUE,
    ExpectationReport,
    expect_column_flat,
    expect_failure_line,
    expect_op_name,
    expect_plan_flat,
    expect_status_name,
    expect_suite_flat,
)

# `query.ir` opcodes, written as literals so the flat-plan encoding is exercised exactly as
# a caller over the wire would send it.
comptime IR_LITERAL: Int = 0
comptime IR_DIV: Int = 5
comptime IR_GT: Int = 102
comptime IR_COL_REF: Int = 130
comptime IR_FROZEN_SQRT: Int = 12


fn _nan() -> Float64:
    var zero: Float64 = 0.0
    return zero / zero


fn _demo_table() -> List[Float64]:
    """3 rows x 2 cols: (price, qty) = (10, 1), (-12, 2), (absent, 3)."""
    var t = List[Float64]()
    t.append(10.0)
    t.append(1.0)
    t.append(-12.0)
    t.append(2.0)
    t.append(0.0)
    t.append(3.0)
    return t^


fn _demo_mask() -> List[Bool]:
    var m = dq_mask_all_valid(6)
    m[4] = False
    return m^


fn _node(mut ints: List[Int], mut fvals: List[Float64], op: Int, var_idx: Int, left: Int, right: Int, fval: Float64):
    ints.append(op)
    ints.append(var_idx)
    ints.append(left)
    ints.append(right)
    ints.append(-1)
    fvals.append(fval)


fn _partition_holds(r: ExpectationReport) -> Bool:
    """The three row populations must partition the checked prefix."""
    return r.n_failing_rows + r.n_unknown_rows + r.n_passing_rows == r.n_rows_checked


fn _slots_finite(r: ExpectationReport) -> Bool:
    for k in range(len(r.fail_observed)):
        if not dq_is_finite(r.fail_observed[k]):
            return False
    for k in range(len(r.fail_expected)):
        if not dq_is_finite(r.fail_expected[k]):
            return False
    return True


fn check() raises:
    var passed = 0
    var failed = 0
    var t = _demo_table()
    var m = _demo_mask()

    # ── the headline: a failure names the row, the column, the bound and the value ──
    var gt = expect_column_flat(t, 3, 2, m, 0, DQ_EXPECT_GT, 0.0, 0.0, 16)
    if gt.status == DQ_OK and gt.n_rows_checked == 3 and not gt.work_truncated:
        passed += 1
        print("  ✅ all three rows checked, nothing truncated")
    else:
        failed += 1
        print("  ❌ unexpected status/coverage:", expect_status_name(gt.status), gt.n_rows_checked)

    if (
        gt.n_violations == 1
        and gt.n_failing_rows == 1
        and gt.n_unknown == 1
        and gt.n_unknown_rows == 1
        and gt.n_passing_rows == 1
    ):
        passed += 1
        print("  ✅ one violation, one unknown, one pass — three different outcomes")
    else:
        failed += 1
        print(
            "  ❌ populations wrong:",
            gt.n_violations, gt.n_failing_rows, gt.n_unknown_rows, gt.n_passing_rows,
        )

    if _partition_holds(gt):
        passed += 1
        print("  ✅ failing + unknown + passing == rows checked")
    else:
        failed += 1
        print("  ❌ the row populations do not partition the checked prefix")

    if gt.n_reported == 1 and gt.first_fail_row == 1 and gt.fail_rows[0] == 1:
        passed += 1
        print("  ✅ the failing row is row 1, and it is reported by index")
    else:
        failed += 1
        print("  ❌ the failing row was not addressed:", gt.first_fail_row)

    if (
        gt.fail_columns[0] == 0
        and gt.fail_ops[0] == DQ_EXPECT_GT
        and gt.fail_expected[0] == 0.0
        and gt.fail_observed[0] == -12.0
        and gt.fail_observed_present[0]
        and gt.fail_observed_finite[0]
    ):
        passed += 1
        print("  ✅ the failure carries column 0, op gt, bound 0.0 and observed -12.0")
    else:
        failed += 1
        print("  ❌ the failure detail is wrong")

    var line = expect_failure_line(
        gt.fail_rows[0], gt.fail_columns[0], gt.fail_ops[0], gt.fail_expected[0],
        gt.fail_observed[0], gt.fail_observed_present[0], gt.fail_observed_finite[0],
    )
    if line == "row 1, column 0, expected gt 0.0, got -12.0":
        passed += 1
        print("  ✅ rendered exactly: " + line)
    else:
        failed += 1
        print("  ❌ rendering wrong: " + line)

    # ── a null is UNKNOWN, not a violation; NOT_NULL is how presence is required ──
    var nn = expect_column_flat(t, 3, 2, m, 0, DQ_EXPECT_NOT_NULL, 0.0, 0.0, 16)
    if nn.n_violations == 1 and nn.n_unknown == 0 and nn.fail_rows[0] == 2:
        passed += 1
        print("  ✅ not_null decides every row, and row 2 is the one that fails it")
    else:
        failed += 1
        print("  ❌ not_null wrong:", nn.n_violations, nn.n_unknown)

    var nn_line = expect_failure_line(
        nn.fail_rows[0], nn.fail_columns[0], nn.fail_ops[0], nn.fail_expected[0],
        nn.fail_observed[0], nn.fail_observed_present[0], nn.fail_observed_finite[0],
    )
    if nn_line == "row 2, column 0, expected not_null, got null":
        passed += 1
        print("  ✅ an absent observation renders as null, never as 0.0: " + nn_line)
    else:
        failed += 1
        print("  ❌ absent rendering wrong: " + nn_line)

    # ── BETWEEN names the bound that broke, not just "not between" ─────────────
    var bt = expect_column_flat(t, 3, 2, m, 1, DQ_EXPECT_BETWEEN, 2.0, 2.0, 16)
    if bt.n_violations == 2 and bt.n_failing_rows == 2 and bt.n_checks_per_row == 2:
        passed += 1
        print("  ✅ qty in [2,2] violates twice across two rows, two checks per row")
    else:
        failed += 1
        print("  ❌ between counts wrong:", bt.n_violations, bt.n_failing_rows)

    var lo_line = expect_failure_line(
        bt.fail_rows[0], bt.fail_columns[0], bt.fail_ops[0], bt.fail_expected[0],
        bt.fail_observed[0], bt.fail_observed_present[0], bt.fail_observed_finite[0],
    )
    var hi_line = expect_failure_line(
        bt.fail_rows[1], bt.fail_columns[1], bt.fail_ops[1], bt.fail_expected[1],
        bt.fail_observed[1], bt.fail_observed_present[1], bt.fail_observed_finite[1],
    )
    if (
        lo_line == "row 0, column 1, expected ge 2.0, got 1.0"
        and hi_line == "row 2, column 1, expected le 2.0, got 3.0"
    ):
        passed += 1
        print("  ✅ each end of the range is named separately: ge on row 0, le on row 2")
    else:
        failed += 1
        print("  ❌ between rendering wrong: " + lo_line + " | " + hi_line)

    if bt.fail_ops[0] == DQ_EXPECT_GE and bt.fail_ops[1] == DQ_EXPECT_LE:
        passed += 1
        print("  ✅ the recorded op is the violated comparison, not 'between'")
    else:
        failed += 1
        print("  ❌ between recorded the wrong ops")

    # ── FINITE: a present non-finite is its own failure, and never a value slot ──
    var nan_table = List[Float64]()
    nan_table.append(1.0)
    nan_table.append(_nan())
    nan_table.append(3.0)
    var fin = expect_column_flat(nan_table, 3, 1, dq_mask_all_valid(3), 0, DQ_EXPECT_FINITE, 0.0, 0.0, 8)
    if fin.n_violations == 1 and fin.fail_rows[0] == 1 and not fin.fail_observed_finite[0]:
        passed += 1
        print("  ✅ a present NaN violates 'finite' at row 1 and is flagged non-finite")
    else:
        failed += 1
        print("  ❌ finite check wrong:", fin.n_violations)

    if _slots_finite(fin) and fin.fail_observed[0] == 0.0:
        passed += 1
        print("  ✅ the observed slot is 0.0, so the response stays serializable")
    else:
        failed += 1
        print("  ❌ a raw non-finite reached a value slot")

    var fin_line = expect_failure_line(
        fin.fail_rows[0], fin.fail_columns[0], fin.fail_ops[0], fin.fail_expected[0],
        fin.fail_observed[0], fin.fail_observed_present[0], fin.fail_observed_finite[0],
    )
    if fin_line == "row 1, column 0, expected finite, got a non-finite value":
        passed += 1
        print("  ✅ non-finite renders as itself, not as 0.0: " + fin_line)
    else:
        failed += 1
        print("  ❌ non-finite rendering wrong: " + fin_line)

    # ── a suite aggregates without losing the addresses ───────────────────────
    var cols = List[Int]()
    cols.append(0)
    cols.append(1)
    var ops = List[Int]()
    ops.append(DQ_EXPECT_GT)
    ops.append(DQ_EXPECT_LE)
    var lows = List[Float64]()
    lows.append(0.0)
    lows.append(2.0)
    var highs = List[Float64]()
    highs.append(0.0)
    highs.append(0.0)
    var suite = expect_suite_flat(t, 3, 2, m, cols, ops, lows, highs, 16)
    if (
        suite.status == DQ_OK
        and suite.n_violations == 2
        and suite.n_failing_rows == 2
        and suite.n_unknown == 1
        and _partition_holds(suite)
    ):
        passed += 1
        print("  ✅ a two-expectation suite finds both violations and keeps the partition")
    else:
        failed += 1
        print("  ❌ suite counts wrong:", suite.n_violations, suite.n_failing_rows)

    var suite_rows_ok = True
    for k in range(suite.n_reported):
        if suite.fail_columns[k] != cols[0] and suite.fail_columns[k] != cols[1]:
            suite_rows_ok = False
    if suite.n_reported == 2 and suite_rows_ok:
        passed += 1
        print("  ✅ every suite failure still names the table column it came from")
    else:
        failed += 1
        print("  ❌ a suite failure lost its column attribution")

    # ── a caller-supplied plan: col0 > col1 ───────────────────────────────────
    var ints = List[Int]()
    var fvals = List[Float64]()
    _node(ints, fvals, IR_COL_REF, 0, -1, -1, 0.0)
    _node(ints, fvals, IR_COL_REF, 1, -1, -1, 0.0)
    _node(ints, fvals, IR_GT, -1, 0, 1, 0.0)
    var plan = expect_plan_flat(t, 3, 2, m, ints, fvals, 2, 0, 16)
    if (
        plan.status == DQ_OK
        and plan.n_violations == 1
        and plan.fail_rows[0] == 1
        and plan.fail_ops[0] == DQ_EXPECT_PLAN_TRUE
        and plan.n_unknown == 1
    ):
        passed += 1
        print("  ✅ 'price > qty' fails on row 1 and is unknown on the absent row")
    else:
        failed += 1
        print("  ❌ plan evaluation wrong:", plan.n_violations, plan.n_unknown)

    var plan_line = expect_failure_line(
        plan.fail_rows[0], plan.fail_columns[0], plan.fail_ops[0], plan.fail_expected[0],
        plan.fail_observed[0], plan.fail_observed_present[0], plan.fail_observed_finite[0],
    )
    if plan_line == "row 1, column 0, expected plan_true, got -12.0":
        passed += 1
        print("  ✅ a plan violation renders without inventing a bound: " + plan_line)
    else:
        failed += 1
        print("  ❌ plan rendering wrong: " + plan_line)

    # ── the measured abort, refused ───────────────────────────────────────────
    # nodes = [col_ref(0), frozen op 12 with left = -1]. `validation_error` says "" for
    # this plan because op_arity returns -2 for the frozen range; `query.eval` then reads
    # values[-1] and the process dies. `first_unsupported_op` is the guard.
    var abort_ints = List[Int]()
    var abort_fvals = List[Float64]()
    _node(abort_ints, abort_fvals, IR_COL_REF, 0, -1, -1, 0.0)
    _node(abort_ints, abort_fvals, IR_FROZEN_SQRT, -1, -1, -1, 0.0)
    var refused = expect_plan_flat(t, 3, 2, m, abort_ints, abort_fvals, 1, 0, 8)
    if refused.status == DQ_EXPECT_ERR_UNSUPPORTED_OP:
        passed += 1
        print("  ✅ the frozen-op/-1-child plan is refused instead of killing the worker")
    else:
        failed += 1
        print("  ❌ the abort plan came back as", expect_status_name(refused.status))

    # ── a masked arithmetic case is refused, not silently zeroed ──────────────
    # col0 / 0.0 > 0.0. `expr.mojo` substitutes 0.0 for a divide by zero; running an
    # expectation on substituted zeros would be a clean bill of health for arithmetic that
    # did not happen.
    var div_ints = List[Int]()
    var div_fvals = List[Float64]()
    _node(div_ints, div_fvals, IR_COL_REF, 0, -1, -1, 0.0)
    _node(div_ints, div_fvals, IR_LITERAL, -1, -1, -1, 0.0)
    _node(div_ints, div_fvals, IR_DIV, -1, 0, 1, 0.0)
    _node(div_ints, div_fvals, IR_LITERAL, -1, -1, -1, 0.0)
    _node(div_ints, div_fvals, IR_GT, -1, 2, 3, 0.0)
    var div_plan = expect_plan_flat(t, 3, 2, m, div_ints, div_fvals, 4, 0, 8)
    if div_plan.status == DQ_EXPECT_ERR_EVAL_REFUSED:
        passed += 1
        print("  ✅ a divide by zero refuses the expectation rather than substituting 0.0")
    else:
        failed += 1
        print("  ❌ a masked case was evaluated:", expect_status_name(div_plan.status))

    # ── the work budget: 4194304 // 1025 = 4092 rows, so 4093 leaves one unchecked ──
    var n_rows = 4093
    var big = List[Float64]()
    for i in range(n_rows):
        big.append(Float64(i))
    var big_mask = dq_mask_all_valid(n_rows)
    var pad_ints = List[Int]()
    var pad_fvals = List[Float64]()
    _node(pad_ints, pad_fvals, IR_COL_REF, 0, -1, -1, 0.0)
    _node(pad_ints, pad_fvals, IR_LITERAL, -1, -1, -1, -1.0)
    for _ in range(1021):
        _node(pad_ints, pad_fvals, IR_LITERAL, -1, -1, -1, 0.0)
    _node(pad_ints, pad_fvals, IR_GT, -1, 0, 1, 0.0)
    var budgeted = expect_plan_flat(big, n_rows, 1, big_mask, pad_ints, pad_fvals, 1023, 0, 8)
    if (
        budgeted.status == DQ_OK
        and budgeted.n_rows_checked == 4092
        and budgeted.n_rows_not_checked == 1
        and budgeted.work_truncated
    ):
        passed += 1
        print("  ✅ 4092 of 4093 rows checked, and the report SAYS one was not")
    else:
        failed += 1
        print(
            "  ❌ budget truncation wrong:",
            budgeted.n_rows_checked, budgeted.n_rows_not_checked, budgeted.work_truncated,
        )

    # A truncated SUITE truncates the same way, and its declared cost must be what it pays.
    # 32 GT expectations cost 3 nodes each, so unit_cost is 96 and the budget admits
    # 4194304 // 96 = 43690 rows. A 43691-row table therefore leaves exactly one unchecked,
    # and the whole point of the prefix extraction is that the 32 column copies are 43690
    # rows long rather than 43691 — the un-truncated version paid 32 * 43691 for a request
    # it charged 96 * 43690. That factor is gated by shape in
    # benchmarks/mojo_benchmarks/bench_data_quality.mojo; what is pinned here is the row
    # accounting the cost claim rests on.
    var suite_rows = 43691
    var suite_col = List[Float64]()
    for i in range(suite_rows):
        suite_col.append(Float64(i))
    var suite_mask = dq_mask_all_valid(suite_rows)
    var k32_cols = List[Int]()
    var k32_ops = List[Int]()
    var k32_lows = List[Float64]()
    var k32_highs = List[Float64]()
    # `> 0.0` on a column of 0, 1, 2, ... violates on row 0 alone, once per expectation.
    for _ in range(32):
        k32_cols.append(0)
        k32_ops.append(DQ_EXPECT_GT)
        k32_lows.append(0.0)
        k32_highs.append(0.0)
    var big_suite = expect_suite_flat(
        suite_col, suite_rows, 1, suite_mask, k32_cols, k32_ops, k32_lows, k32_highs, 4
    )
    if (
        big_suite.status == DQ_OK
        and big_suite.n_rows_checked == 43690
        and big_suite.n_rows_not_checked == 1
        and big_suite.work_truncated
        and big_suite.n_checks_per_row == 32
        and big_suite.n_violations == 32
        and big_suite.n_failing_rows == 1
        and big_suite.first_fail_row == 0
        and big_suite.n_reported == 4
        and big_suite.reports_truncated
    ):
        passed += 1
        print("  ✅ 43690 of 43691 rows at 32 expectations: 4194304 // 96, one row declared")
    else:
        failed += 1
        print(
            "  ❌ suite truncation wrong:",
            big_suite.n_rows_checked, big_suite.n_rows_not_checked,
            big_suite.n_checks_per_row, big_suite.n_violations,
            big_suite.n_failing_rows, big_suite.n_reported,
        )

    if budgeted.n_rows_checked + budgeted.n_rows_not_checked == budgeted.n_rows:
        passed += 1
        print("  ✅ checked + not-checked accounts for every row in the table")
    else:
        failed += 1
        print("  ❌ the row accounting does not close")

    var too_many = List[Int]()
    var too_many_f = List[Float64]()
    for _ in range(1025):
        _node(too_many, too_many_f, IR_LITERAL, -1, -1, -1, 0.0)
    if expect_plan_flat(t, 3, 2, m, too_many, too_many_f, 0, 0, 8).status == DQ_EXPECT_ERR_TOO_MANY_NODES:
        passed += 1
        print("  ✅ a 1025-node plan exceeds the node ceiling and is refused")
    else:
        failed += 1
        print("  ❌ the node ceiling was not enforced")

    # ── the report cap: counts stay complete when the address list does not ────
    var capped = expect_column_flat(t, 3, 2, m, 1, DQ_EXPECT_BETWEEN, 2.0, 2.0, 1)
    if (
        capped.n_violations == 2
        and capped.n_reported == 1
        and capped.reports_truncated
        and capped.n_failing_rows == 2
    ):
        passed += 1
        print("  ✅ max_reports=1 caps the addresses at 1 while n_violations stays 2")
    else:
        failed += 1
        print("  ❌ the cap dropped a count as well as an address")

    # ── refusals, one per defect ───────────────────────────────────────────────
    if expect_column_flat(t, 3, 2, m, 0, DQ_EXPECT_GT, _nan(), 0.0, 8).status == DQ_EXPECT_ERR_BOUND_NOT_FINITE:
        passed += 1
        print("  ✅ a NaN bound is refused — every comparison against it would be False")
    else:
        failed += 1
        print("  ❌ a NaN bound was accepted")

    if expect_column_flat(t, 3, 2, m, 0, 99, 0.0, 0.0, 8).status == DQ_EXPECT_ERR_UNKNOWN_OP:
        passed += 1
        print("  ✅ an unknown expectation op is refused")
    else:
        failed += 1
        print("  ❌ an unknown op was run")

    if (
        expect_column_flat(t, 3, 2, m, -1, DQ_EXPECT_GT, 0.0, 0.0, 8).status == DQ_ERR_COLUMN_INDEX
        and expect_column_flat(t, 3, 2, m, 2, DQ_EXPECT_GT, 0.0, 0.0, 8).status == DQ_ERR_COLUMN_INDEX
    ):
        passed += 1
        print("  ✅ a column index out of range in either direction is refused")
    else:
        failed += 1
        print("  ❌ an out-of-range column reached a subscript")

    var short_cols = List[Int]()
    short_cols.append(0)
    if expect_suite_flat(t, 3, 2, m, short_cols, ops, lows, highs, 8).status == DQ_ERR_LENGTH_MISMATCH:
        passed += 1
        print("  ✅ a suite whose parallel lists disagree is refused, not truncated")
    else:
        failed += 1
        print("  ❌ a ragged suite silently dropped an expectation")

    var many_cols = List[Int]()
    var many_ops = List[Int]()
    var many_lows = List[Float64]()
    var many_highs = List[Float64]()
    for _ in range(257):
        many_cols.append(0)
        many_ops.append(DQ_EXPECT_GT)
        many_lows.append(0.0)
        many_highs.append(0.0)
    if expect_suite_flat(t, 3, 2, m, many_cols, many_ops, many_lows, many_highs, 8).status == DQ_EXPECT_ERR_TOO_MANY_EXPECTATIONS:
        passed += 1
        print("  ✅ a 257-expectation suite exceeds the ceiling and is refused")
    else:
        failed += 1
        print("  ❌ the expectation ceiling was not enforced")

    var empty_ints = List[Int]()
    var empty_fvals = List[Float64]()
    if expect_plan_flat(t, 3, 2, m, empty_ints, empty_fvals, 0, 0, 8).status == DQ_EXPECT_ERR_NOTHING_TO_CHECK:
        passed += 1
        print("  ✅ an empty plan is refused")
    else:
        failed += 1
        print("  ❌ an empty plan was run")

    # ── an empty SUITE is the same defect, and used to report a clean partial pass ──
    # `rows = ... if k > 0 else 0` made `work_truncated = (0 < 3)` True, so a request that
    # ran no checks at all came back status 0 with "the pass hit the work ceiling, narrow
    # the table and run again" — advice for a defect that does not exist, attached to a
    # zero-violation report for a table nothing looked at.
    var no_cols_i = List[Int]()
    var no_ops = List[Int]()
    var no_lows = List[Float64]()
    var no_highs = List[Float64]()
    var empty_suite = expect_suite_flat(t, 3, 2, m, no_cols_i, no_ops, no_lows, no_highs, 16)
    if (
        empty_suite.status == DQ_EXPECT_ERR_NOTHING_TO_CHECK
        and not empty_suite.work_truncated
        and empty_suite.n_rows_not_checked == 0
        and empty_suite.n_violations == 0
    ):
        passed += 1
        print("  ✅ an empty SUITE is refused too, and reports no truncation it did not hit")
    else:
        failed += 1
        print(
            "  ❌ a zero-expectation suite reported a partial pass:",
            expect_status_name(empty_suite.status),
            empty_suite.work_truncated, empty_suite.n_rows_not_checked,
        )

    # One vocabulary: 422 now names the shared defect rather than only the plan half.
    if expect_status_name(DQ_EXPECT_ERR_NOTHING_TO_CHECK) == "request_contains_no_expectation_to_check":
        passed += 1
        print("  ✅ 422 is named for both halves of the defect it now covers")
    else:
        failed += 1
        print("  ❌ 422 is still named for the plan only:", expect_status_name(422))

    # ── work_truncated means the CEILING, on every driver that can set it ─────
    # With the empty suite refused, the only way to see True is a genuine budget hit, which
    # is what the reader is told it means. A one-expectation suite over a 3-row table is
    # nowhere near the ceiling and must say so.
    var small_cols = List[Int]()
    small_cols.append(0)
    var small_ops = List[Int]()
    small_ops.append(DQ_EXPECT_GT)
    var small_lows = List[Float64]()
    small_lows.append(0.0)
    var small_highs = List[Float64]()
    small_highs.append(0.0)
    var small_suite = expect_suite_flat(
        t, 3, 2, m, small_cols, small_ops, small_lows, small_highs, 16
    )
    if (
        small_suite.status == DQ_OK
        and not small_suite.work_truncated
        and small_suite.n_rows_checked == 3
        and small_suite.n_rows_not_checked == 0
    ):
        passed += 1
        print("  ✅ a suite inside the budget checks every row and reports no truncation")
    else:
        failed += 1
        print(
            "  ❌ a small suite claimed truncation:",
            small_suite.work_truncated, small_suite.n_rows_checked,
        )

    # ── max_reports is CLAMPED, not validated: the relation says [clamped] ────
    # A negative cap and an absurd cap both leave the request working; only the LIST is
    # bounded, and `reports_truncated` says the list was cut. Pinning both ends pins the
    # corrected enforcement tag on `dim max_reports`.
    var neg_cap = expect_column_flat(t, 3, 2, m, 0, DQ_EXPECT_GT, 0.0, 0.0, -5)
    var huge_cap = expect_column_flat(t, 3, 2, m, 0, DQ_EXPECT_GT, 0.0, 0.0, 1 << 40)
    if (
        neg_cap.status == DQ_OK and neg_cap.n_violations == 1
        and neg_cap.n_reported == 0 and neg_cap.reports_truncated
        and huge_cap.status == DQ_OK and huge_cap.n_violations == 1
        and huge_cap.n_reported == 1 and not huge_cap.reports_truncated
    ):
        passed += 1
        print("  ✅ max_reports clamps at both ends; the COUNT survives a capped list")
    else:
        failed += 1
        print(
            "  ❌ max_reports was not clamped:",
            neg_cap.status, neg_cap.n_reported, huge_cap.status, huge_cap.n_reported,
        )

    var ragged = List[Int]()
    ragged.append(IR_COL_REF)
    var one_f = List[Float64]()
    one_f.append(0.0)
    if expect_plan_flat(t, 3, 2, m, ragged, one_f, 0, 0, 8).status == DQ_EXPECT_ERR_PLAN_ARRAYS:
        passed += 1
        print("  ✅ node_ints that is not 5 per node is refused (a list-to-list check)")
    else:
        failed += 1
        print("  ❌ a ragged plan encoding was decoded anyway")

    if expect_plan_flat(t, 3, 2, m, ints, fvals, 5, 0, 8).status == DQ_EXPECT_ERR_PLAN_ROOT:
        passed += 1
        print("  ✅ a root past the last node is refused — root is a subscript")
    else:
        failed += 1
        print("  ❌ an out-of-range root was indexed")

    if expect_plan_flat(t, 3, 2, m, ints, fvals, -1, 0, 8).status == DQ_EXPECT_ERR_PLAN_ROOT:
        passed += 1
        print("  ✅ a negative root is refused too — the fatal direction")
    else:
        failed += 1
        print("  ❌ a negative root was indexed")

    var self_ref = List[Int]()
    var self_ref_f = List[Float64]()
    _node(self_ref, self_ref_f, IR_COL_REF, 0, -1, -1, 0.0)
    _node(self_ref, self_ref_f, IR_GT, -1, 1, 0, 0.0)
    if expect_plan_flat(t, 3, 2, m, self_ref, self_ref_f, 1, 0, 8).status == DQ_EXPECT_ERR_PLAN_INVALID:
        passed += 1
        print("  ✅ a self-referencing node is refused by the frozen validator")
    else:
        failed += 1
        print("  ❌ a cyclic plan was evaluated")

    if expect_column_flat(t, 3, 3, m, 0, DQ_EXPECT_GT, 0.0, 0.0, 8).status == DQ_ERR_TABLE_SHAPE:
        passed += 1
        print("  ✅ a declared shape that does not match the cell count is refused")
    else:
        failed += 1
        print("  ❌ a wrong shape was indexed")

    if expect_op_name(DQ_EXPECT_PLAN_TRUE) == "plan_true" and expect_op_name(42) == "unknown_expectation_42":
        passed += 1
        print("  ✅ every op has a name, and an unknown one says so")
    else:
        failed += 1
        print("  ❌ op naming incomplete")

    print("  [data_quality.expect] Passed:", passed, "Failed:", failed)


fn main() raises:
    check()
