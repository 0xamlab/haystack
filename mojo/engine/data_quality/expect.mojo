"""
data_quality.expect — expectations over the frozen typed expression IR. Zero Python.

A failure must name the ROW and the COLUMN
------------------------------------------
"3 rows failed" is a metric. `row 47, column 2, expected gt 0.0, got -12.0` is a repair
instruction, and that specificity is the whole product. `ExpectationReport` therefore
carries six PARALLEL lists — `fail_rows`, `fail_columns`, `fail_ops`, `fail_expected`,
`fail_observed`, `fail_observed_present` / `fail_observed_finite` — and
`expect_failure_line` renders entry `k` as exactly that sentence.

Where the evaluation comes from
-------------------------------
EXISTING-FROZEN, called, not reimplemented:

  * `query.ir` is the typed IR. `types.ExprNode` is a flat POD with integer child indices,
    so a plan is an array plus a root, which is why it crosses a process boundary at all.
    `literal`, `col_ref`, `binary` and `unary` build the nodes; `validation_error` and
    `first_unsupported_op` reject a malformed one.
  * `query.eval.evaluate` is the columnar evaluator, and it has ALREADY decided the null
    semantics an expectation engine needs: arithmetic and comparison propagate null,
    `AND`/`OR` are three-valued and not strict. Nothing here re-decides that.
  * `columnar.array` / `columnar.batch` build the nullable columns it reads.

MISSING-DRIVER, which is this file: `query.executor` filters WITH a predicate, which
answers "which rows survive". An expectation needs the complement, addressed: which rows
failed, in which column, against which bound, with which observed value. Nothing in the
tree produced that.

A null does not fail a range expectation
---------------------------------------
It is UNKNOWN, counted in `n_unknown`, and it is not a violation. Collapsing unknown to
false is the common shortcut and it silently converts a missing-data problem into a
range-violation problem — two different repairs. `DQ_EXPECT_NOT_NULL` is how a caller
requires presence, and it is the one expectation whose answer is always known.

`DQ_EXPECT_EQ` uses IEEE `==`, NOT the package's identity
---------------------------------------------------------
`query.eval` compares with `==`, so `-0.0 == 0.0` holds and `NaN == NaN` does not.
`contract.dq_values_equal` is a different relation — the normalized bit pattern, under
which both hold — and it is what `data_quality.duplicates` keys on. The two are stated
separately on purpose: an expectation is a comparison against a bound and an equivalence
class is an identity, and conflating them would make `expect ... eq nan` silently pass or
a duplicate scan silently split `-0.0` from `0.0`.

The abort this driver exists to prevent, measured
-------------------------------------------------
`query.ir.validation_error` returns "" — plan is well formed — for a node carrying a
FROZEN opcode (0-38) with `left = -1`, because `op_arity` answers `-2` for that range and
defers to `expr.mojo`, so the "needs a left child" check never runs. `query.eval` then
falls through to its binary branch and evaluates `values[-1]`. Executed on this tree:

    nodes = [col_ref(0), ExprNode(12, 0.0, -1, -1, -1)]   # 12 = frozen OP_SQRT
    validation_error(nodes, 1, 1)  ->  ""
    evaluate(nodes, 1, batch, True)
      -> query/eval.mojo:205: Assert Error: index -1 is out of bounds
      -> mojo: error: execution crashed

That is the uncatchable class: it ends the process, `try`/`except` above it does not help,
and every resident dataset dies with it. `first_unsupported_op` is the frozen kernel that
catches it (it returned 1 for the plan above), so `expect_plan_flat` calls it BEFORE
`evaluate` and refuses with `DQ_EXPECT_ERR_UNSUPPORTED_OP`. Neither frozen kernel is
modified; the guard is the composition's job.

Bounded work, and saying what was not checked
---------------------------------------------
Cost is `n_checks * n_nodes * rows`, and all three factors are charged — bounding memory
is not bounding work. When the product exceeds `contract.DQ_MAX_WORK` a driver checks a
PREFIX of the rows and reports `n_rows_checked`, `n_rows_not_checked` and
`work_truncated`. It does not sample: a sampled pass that reports a clean table is a wrong
answer, while a prefix that says how far it got is a partial one. Only the prefix is
materialised into a `RecordBatch`, so the truncation bounds the allocation too.

Status codes: expect owns 420-429 of the package's 400-449.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64, bool
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_data_quality_expect.mojo
benchmark: benchmarks/mojo_benchmarks/bench_data_quality.mojo
docs: gitbook/engine/data-quality.md
version_introduced: 0.1.0
deprecation_state: active
@endcapability
"""
from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch, Schema
from columnar.dtype import DTYPE_FLOAT64
from query.eval import evaluate
from query.ir import (
    OP_EQ,
    OP_GE,
    OP_GT,
    OP_IS_NOT_NULL,
    OP_LE,
    OP_LT,
    OP_NE,
    binary,
    col_ref,
    first_unsupported_op,
    literal,
    unary,
    validation_error,
)
from types import ExprNode

from data_quality.contract import (
    DQ_ERR_COLUMN_INDEX,
    DQ_ERR_LENGTH_MISMATCH,
    DQ_MAX_EXPECTATIONS,
    DQ_MAX_NODES,
    DQ_MAX_REPORTS,
    DQ_OK,
    dq_column_mask_prefix,
    dq_column_prefix,
    dq_is_finite,
    dq_mask_defect,
    dq_rows_within_budget,
    dq_status_name,
    dq_table_defect,
)

# ── status codes: expect owns 420-429 ─────────────────────────────────────────
comptime DQ_EXPECT_ERR_UNKNOWN_OP: Int = 420
comptime DQ_EXPECT_ERR_BOUND_NOT_FINITE: Int = 421
# ONE code for "the request contains nothing to check", whether the request was a plan with
# no nodes or a suite with no expectations. The two are the same caller defect and they must
# not have two strengths: an empty plan was refused while an empty suite returned status 0
# with `work_truncated = True`, i.e. a report of a truncation that never happened, for a
# pass that never ran. expect owns 420-429 and all ten are allocated, so broadening this one
# is also the only way to say it inside the package's range (rule 4e).
comptime DQ_EXPECT_ERR_NOTHING_TO_CHECK: Int = 422
comptime DQ_EXPECT_ERR_PLAN_ARRAYS: Int = 423
comptime DQ_EXPECT_ERR_PLAN_ROOT: Int = 424
comptime DQ_EXPECT_ERR_UNSUPPORTED_OP: Int = 425
comptime DQ_EXPECT_ERR_PLAN_INVALID: Int = 426
comptime DQ_EXPECT_ERR_EVAL_REFUSED: Int = 427
comptime DQ_EXPECT_ERR_TOO_MANY_NODES: Int = 428
comptime DQ_EXPECT_ERR_TOO_MANY_EXPECTATIONS: Int = 429

# ── expectation vocabulary ───────────────────────────────────────────────────
# Deliberately small. Each one maps to a frozen `query.ir` opcode except BETWEEN (which
# is two comparisons, reported separately so the failing BOUND is named) and FINITE
# (which the frozen IR has no opcode for and is therefore checked in this kernel).
comptime DQ_EXPECT_GT: Int = 0
comptime DQ_EXPECT_GE: Int = 1
comptime DQ_EXPECT_LT: Int = 2
comptime DQ_EXPECT_LE: Int = 3
comptime DQ_EXPECT_EQ: Int = 4
comptime DQ_EXPECT_NE: Int = 5
comptime DQ_EXPECT_BETWEEN: Int = 6
comptime DQ_EXPECT_NOT_NULL: Int = 7
comptime DQ_EXPECT_FINITE: Int = 8
# The largest op a CALLER may name. Everything above it is produced by this module only.
comptime DQ_EXPECT_OP_MAX: Int = 8
# The op recorded for a violated caller-supplied plan. Not nameable as an input, because a
# plan is not a comparison against a bound and has no `expected` value to print.
comptime DQ_EXPECT_PLAN_TRUE: Int = 9

# Nodes a single comparison plan costs, and the plan-node stride of the flat encoding.
comptime DQ_COMPARE_PLAN_NODES: Int = 3
comptime DQ_PLAN_STRIDE: Int = 5


struct ExpectationReport(Copyable, Movable):
    """The outcome of one or more expectations over a table.

    Three row populations PARTITION the checked prefix, and the order of precedence is
    stated: a row that violated any bound is FAILING; a row that violated none but had at
    least one undecided check is UNKNOWN; only a row every check decided in its favour is
    PASSING. So

        n_failing_rows + n_unknown_rows + n_passing_rows == n_rows_checked

    always holds, and the suite asserts it. Counting an undecided row as passing — which
    is what a single `failed` flag per row produces — would report a clean bill of health
    for a row nothing could be decided about.

    `n_violations` and `n_unknown` count (row, check) PAIRS, so both can exceed their row
    counterparts: a BETWEEN whose low bound exceeds its high bound violates twice on one
    row, and both facts are reported.
    """

    var status: Int
    var n_rows: Int
    var n_rows_checked: Int
    var n_rows_not_checked: Int
    var work_truncated: Bool
    var n_checks_per_row: Int
    var n_violations: Int
    var n_failing_rows: Int
    var n_passing_rows: Int
    var n_unknown: Int
    var n_unknown_rows: Int
    var n_reported: Int
    var reports_truncated: Bool
    var first_fail_row: Int
    var fail_rows: List[Int]
    var fail_columns: List[Int]
    var fail_ops: List[Int]
    var fail_expected: List[Float64]
    var fail_observed: List[Float64]
    var fail_observed_present: List[Bool]
    var fail_observed_finite: List[Bool]

    fn __init__(out self, status: Int, n_rows: Int):
        self.status = status
        self.n_rows = n_rows
        self.n_rows_checked = 0
        self.n_rows_not_checked = 0
        self.work_truncated = False
        self.n_checks_per_row = 0
        self.n_violations = 0
        self.n_failing_rows = 0
        self.n_passing_rows = 0
        self.n_unknown = 0
        self.n_unknown_rows = 0
        self.n_reported = 0
        self.reports_truncated = False
        self.first_fail_row = -1
        self.fail_rows = List[Int]()
        self.fail_columns = List[Int]()
        self.fail_ops = List[Int]()
        self.fail_expected = List[Float64]()
        self.fail_observed = List[Float64]()
        self.fail_observed_present = List[Bool]()
        self.fail_observed_finite = List[Bool]()


fn expect_status_name(code: Int) -> String:
    """Name for a status this module can return. One vocabulary, in `contract`.

    @capability expect_status_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    return dq_status_name(code)


fn expect_op_name(op: Int) -> String:
    """Name for an expectation opcode, for a message a human reads.

    @capability expect_op_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if op == DQ_EXPECT_GT:
        return "gt"
    if op == DQ_EXPECT_GE:
        return "ge"
    if op == DQ_EXPECT_LT:
        return "lt"
    if op == DQ_EXPECT_LE:
        return "le"
    if op == DQ_EXPECT_EQ:
        return "eq"
    if op == DQ_EXPECT_NE:
        return "ne"
    if op == DQ_EXPECT_BETWEEN:
        return "between"
    if op == DQ_EXPECT_NOT_NULL:
        return "not_null"
    if op == DQ_EXPECT_FINITE:
        return "finite"
    if op == DQ_EXPECT_PLAN_TRUE:
        return "plan_true"
    return "unknown_expectation_" + String(op)


fn expect_failure_line(
    row: Int,
    column: Int,
    op: Int,
    expected: Float64,
    observed: Float64,
    observed_present: Bool,
    observed_finite: Bool,
) -> String:
    """One failure as the sentence a reader can act on.

        row 47, column 2, expected gt 0.0, got -12.0
        row 3, column 1, expected gt 0.0, got null
        row 9, column 0, expected lt 100.0, got a non-finite value

    The observed value is rendered from the two flags, never from the number, so a slot
    holding 0.0 because nothing existed there can never print as a measurement. That is
    the same discipline the struct fields follow, for the same reason: `0.0` returned for
    "no data" is the silent-wrong-answer this package exists to remove.

    @capability expect_failure_line
    complexity: O(1)
    counts: none
    @endcapability
    """
    var head = "row " + String(row) + ", column " + String(column) + ", expected "
    if op == DQ_EXPECT_NOT_NULL:
        head += "not_null"
    elif op == DQ_EXPECT_FINITE:
        head += "finite"
    elif op == DQ_EXPECT_PLAN_TRUE:
        head += "plan_true"
    elif dq_is_finite(expected):
        head += expect_op_name(op) + " " + String(expected)
    else:
        head += expect_op_name(op) + " <a non-finite bound, which is refused>"
    if not observed_present:
        return head + ", got null"
    if not observed_finite:
        return head + ", got a non-finite value"
    return head + ", got " + String(observed)


fn _ir_op(op: Int) -> Int:
    """The frozen `query.ir` comparison opcode for an expectation op, or -1."""
    if op == DQ_EXPECT_GT:
        return OP_GT
    if op == DQ_EXPECT_GE:
        return OP_GE
    if op == DQ_EXPECT_LT:
        return OP_LT
    if op == DQ_EXPECT_LE:
        return OP_LE
    if op == DQ_EXPECT_EQ:
        return OP_EQ
    if op == DQ_EXPECT_NE:
        return OP_NE
    return -1


fn _one_column_batch(
    values: List[Float64], present: List[Bool], n_rows: Int
) -> RecordBatch:
    """A single-column `RecordBatch` over the first `n_rows` positions.

    The subject column becomes batch column 0, so every plan built here reads
    `col_ref(0)`; the report translates back to the caller's table column index. Building
    one column rather than the whole table is what keeps the allocation proportional to
    the rows actually checked times ONE column instead of times `n_cols`.
    """
    var prefix_values = List[Float64]()
    var prefix_mask = List[Bool]()
    var upto = n_rows
    if len(values) < upto:
        upto = len(values)
    if len(present) < upto:
        upto = len(present)
    for i in range(upto):
        prefix_values.append(values[i])
        prefix_mask.append(present[i])
    var columns = List[Float64Array]()
    columns.append(float64_with_nulls(prefix_values^, prefix_mask))
    var names = List[String]()
    names.append("subject")
    var dtypes = List[Int]()
    dtypes.append(DTYPE_FLOAT64)
    return RecordBatch(Schema(names^, dtypes^), columns^, upto)


fn _comparison_plan(ir_op: Int, bound: Float64) -> List[ExprNode]:
    """`col_ref(0) <op> literal(bound)`, built with the frozen constructors. Root is 2."""
    var nodes = List[ExprNode]()
    nodes.append(col_ref(0))
    nodes.append(literal(bound))
    nodes.append(binary(ir_op, 0, 1))
    return nodes^


fn _not_null_plan() -> List[ExprNode]:
    """`is_not_null(col_ref(0))`. Root is 1. The one plan whose answer is always known."""
    var nodes = List[ExprNode]()
    nodes.append(col_ref(0))
    nodes.append(unary(OP_IS_NOT_NULL, 0))
    return nodes^


fn _record(
    mut report: ExpectationReport,
    row: Int,
    column: Int,
    op: Int,
    expected: Float64,
    observed: Float64,
    observed_present: Bool,
    max_reports: Int,
):
    """Append one violation, capped, and keep the counters honest.

    A capped report sets `reports_truncated` and still increments `n_violations`, so the
    COUNT is complete even when the address list is not. The value slot is zeroed unless
    the observation is both present and finite — a raw non-finite in a returned Float64
    makes the whole response a typed serialization error, and the two flags already carry
    the fact.
    """
    report.n_violations += 1
    if report.first_fail_row < 0 or row < report.first_fail_row:
        report.first_fail_row = row
    if len(report.fail_rows) >= max_reports:
        report.reports_truncated = True
        return
    var finite = observed_present and dq_is_finite(observed)
    report.fail_rows.append(row)
    report.fail_columns.append(column)
    report.fail_ops.append(op)
    report.fail_expected.append(expected)
    report.fail_observed.append(observed if finite else 0.0)
    report.fail_observed_present.append(observed_present)
    report.fail_observed_finite.append(finite)
    report.n_reported = len(report.fail_rows)


fn _apply_check(
    mut report: ExpectationReport,
    mut failed_row: List[Bool],
    mut unknown_row: List[Bool],
    values: List[Float64],
    present: List[Bool],
    rows: Int,
    column: Int,
    op: Int,
    bound: Float64,
    max_reports: Int,
) raises -> Int:
    """Run ONE comparison over `rows` rows of one column. Returns a status code.

    `DQ_EXPECT_FINITE` is evaluated here rather than through the IR because the frozen
    opcode space has no finiteness test; stating that is better than adding an opcode to a
    frozen module or approximating it with a range comparison.
    """
    if op == DQ_EXPECT_FINITE:
        for r in range(rows):
            if not present[r]:
                report.n_unknown += 1
                unknown_row[r] = True
                continue
            if dq_is_finite(values[r]):
                continue
            failed_row[r] = True
            _record(report, r, column, op, 0.0, values[r], True, max_reports)
        return DQ_OK

    var nodes = List[ExprNode]()
    var root = 0
    if op == DQ_EXPECT_NOT_NULL:
        nodes = _not_null_plan()
        root = 1
    else:
        var ir = _ir_op(op)
        if ir < 0:
            return DQ_EXPECT_ERR_UNKNOWN_OP
        if not dq_is_finite(bound):
            return DQ_EXPECT_ERR_BOUND_NOT_FINITE
        nodes = _comparison_plan(ir, bound)
        root = 2

    var batch = _one_column_batch(values, present, rows)
    # Guarded even for a plan this file built itself: the check is cheap, and a guard that
    # only runs on the caller's path is one refactor away from not running at all.
    if first_unsupported_op(nodes) >= 0:
        return DQ_EXPECT_ERR_UNSUPPORTED_OP
    if len(validation_error(nodes, root, batch.width())) > 0:
        return DQ_EXPECT_ERR_PLAN_INVALID

    var verdict = List[Float64]()
    var decided = List[Bool]()
    var evaluated = True
    try:
        var column_out = evaluate(nodes, root, batch, True)
        for r in range(column_out.length):
            verdict.append(column_out.get(r))
            decided.append(column_out.is_valid_at(r))
    except:
        evaluated = False
    if not evaluated:
        return DQ_EXPECT_ERR_EVAL_REFUSED

    for r in range(len(verdict)):
        if not decided[r]:
            report.n_unknown += 1
            unknown_row[r] = True
            continue
        if verdict[r] != 0.0:
            continue
        failed_row[r] = True
        _record(report, r, column, op, bound, values[r], present[r], max_reports)
    return DQ_OK


fn _finish(
    mut report: ExpectationReport,
    failed_row: List[Bool],
    unknown_row: List[Bool],
    rows: Int,
):
    """Partition the checked rows into failing / unknown / passing, in that precedence.

    A failing row is failing even if another check on it was undecided: the violation is
    the actionable fact. A row with no violation and an undecided check is UNKNOWN, never
    passing — see `ExpectationReport`.
    """
    var failing = 0
    var unknown = 0
    for r in range(rows):
        if failed_row[r]:
            failing += 1
        elif unknown_row[r]:
            unknown += 1
    report.n_failing_rows = failing
    report.n_unknown_rows = unknown
    report.n_passing_rows = rows - failing - unknown


fn _plan_nodes_for(op: Int) -> Int:
    """Nodes an expectation costs per row, for the work budget.

    BETWEEN is two comparison plans, FINITE is a direct scan (one unit), everything else
    is one comparison plan. Charging BETWEEN as one plan would understate its cost by
    half, which is exactly the "budget that counts one factor of a product" failure.
    """
    if op == DQ_EXPECT_BETWEEN:
        return 2 * DQ_COMPARE_PLAN_NODES
    if op == DQ_EXPECT_FINITE:
        return 1
    if op == DQ_EXPECT_NOT_NULL:
        return 2
    return DQ_COMPARE_PLAN_NODES


fn expect_column_flat(
    table: List[Float64], n_rows: Int, n_cols: Int, null_mask: List[Bool],
    col: Int, op: Int, bound_low: Float64, bound_high: Float64, max_reports: Int,
) raises -> ExpectationReport:
    """One expectation on one column, reported per failing row.

    `bound_high` is read only by `DQ_EXPECT_BETWEEN`, which is checked as `>= bound_low`
    and `<= bound_high` SEPARATELY so each violation names the bound it broke — an AND
    would report "not between" and leave the reader to work out which end.

    `col` is a subscript into the table, so it is refused in both directions before any
    read. `max_reports` is CLAMPED into [0, DQ_MAX_REPORTS] rather than refused: a negative
    cap would make every append look capped, an unbounded one is an allocation the caller
    controls, and clamping keeps a working request working. The relation below says
    `[clamped]` for that reason — it said `[kernel_validated]`, which claims a typed status
    this function never returns for `max_reports`.

    @capability expect_column_flat
    complexity: O(n_rows)
    counts:
    - n_rows * n_cols == len(table, null_mask) [kernel_validated]
    - dim col [kernel_validated]
    - dim max_reports [clamped]
    @endcapability
    """
    var defect = dq_table_defect(table, n_rows, n_cols)
    if defect != DQ_OK:
        return ExpectationReport(defect, 0)
    if len(null_mask) != len(table):
        return ExpectationReport(dq_mask_defect(null_mask, len(table)), 0)
    if col < 0 or col >= n_cols:
        return ExpectationReport(DQ_ERR_COLUMN_INDEX, n_rows)
    if op < 0 or op > DQ_EXPECT_OP_MAX:
        return ExpectationReport(DQ_EXPECT_ERR_UNKNOWN_OP, n_rows)

    var cap = max_reports
    if cap < 0:
        cap = 0
    if cap > DQ_MAX_REPORTS:
        cap = DQ_MAX_REPORTS

    var rows = dq_rows_within_budget(n_rows, _plan_nodes_for(op))
    var report = ExpectationReport(DQ_OK, n_rows)
    report.n_rows_checked = rows
    report.n_rows_not_checked = n_rows - rows
    report.work_truncated = rows < n_rows
    report.n_checks_per_row = 2 if op == DQ_EXPECT_BETWEEN else 1

    # The prefix only: a truncated pass that extracted the full column would pay for rows it
    # declared unchecked.
    var values = dq_column_prefix(table, n_rows, n_cols, col, rows)
    var present = dq_column_mask_prefix(null_mask, n_rows, n_cols, col, rows)
    var failed_row = List[Bool]()
    var unknown_row = List[Bool]()
    for _ in range(rows):
        failed_row.append(False)
        unknown_row.append(False)

    if op == DQ_EXPECT_BETWEEN:
        var low_status = _apply_check(
            report, failed_row, unknown_row, values, present, rows, col,
            DQ_EXPECT_GE, bound_low, cap,
        )
        if low_status != DQ_OK:
            return ExpectationReport(low_status, n_rows)
        var high_status = _apply_check(
            report, failed_row, unknown_row, values, present, rows, col,
            DQ_EXPECT_LE, bound_high, cap,
        )
        if high_status != DQ_OK:
            return ExpectationReport(high_status, n_rows)
    else:
        var status = _apply_check(
            report, failed_row, unknown_row, values, present, rows, col, op, bound_low, cap
        )
        if status != DQ_OK:
            return ExpectationReport(status, n_rows)

    _finish(report, failed_row, unknown_row, rows)
    return report^


fn expect_suite_flat(
    table: List[Float64], n_rows: Int, n_cols: Int, null_mask: List[Bool],
    cols: List[Int], ops: List[Int], lows: List[Float64], highs: List[Float64],
    max_reports: Int,
) raises -> ExpectationReport:
    """A suite of expectations over one table, aggregated into one report.

    Four parallel lists describe the suite: `cols[k]`, `ops[k]`, `lows[k]`, `highs[k]`.
    They must be the same length; a mismatch is refused rather than truncated to the
    shortest, because a silently dropped expectation is a check the caller believes ran.

    The budget is charged over the WHOLE suite — `sum_k nodes(ops[k]) * rows` — so adding
    a tenth expectation reduces the rows checked rather than multiplying the work. Every
    expectation is applied to the SAME row prefix, which is what makes the per-row
    populations comparable across checks.

    That claim is only true because each expectation extracts the PREFIX of its column
    (`contract.dq_column_prefix`) and not the whole column. Extracting the whole column per
    expectation is what makes a bounded-memory request an unbounded-work one: measured at
    the 4,194,304-cell ceiling, a 256-expectation suite examining 5,461 rows spent 29x the
    wall time of a one-expectation request examining 1,398,101 rows, at an identical
    declared cost of ~4.19e6 work units. Bounding memory is not bounding work.

    An EMPTY suite is refused with `DQ_EXPECT_ERR_NOTHING_TO_CHECK`, exactly as an empty
    plan is. A zero-expectation pass reported `n_rows_checked = 0`, `work_truncated = True`
    and no violations — a clean bill of health for a table nothing looked at, plus a
    truncation that did not happen.

    A defect in any single expectation (an unknown op, a non-finite bound, an
    out-of-range column) fails the whole suite. A partially-applied suite that reported
    "0 violations" would be indistinguishable from a clean table.

    @capability expect_suite_flat
    complexity: O(n_rows * len(ops))
    counts:
    - n_rows * n_cols == len(table, null_mask) [kernel_validated]
    - dim max_reports [clamped]
    @endcapability
    """
    var defect = dq_table_defect(table, n_rows, n_cols)
    if defect != DQ_OK:
        return ExpectationReport(defect, 0)
    if len(null_mask) != len(table):
        return ExpectationReport(dq_mask_defect(null_mask, len(table)), 0)
    var k = len(cols)
    if len(ops) != k or len(lows) != k or len(highs) != k:
        return ExpectationReport(DQ_ERR_LENGTH_MISMATCH, n_rows)
    if k == 0:
        return ExpectationReport(DQ_EXPECT_ERR_NOTHING_TO_CHECK, n_rows)
    if k > DQ_MAX_EXPECTATIONS:
        return ExpectationReport(DQ_EXPECT_ERR_TOO_MANY_EXPECTATIONS, n_rows)

    var cap = max_reports
    if cap < 0:
        cap = 0
    if cap > DQ_MAX_REPORTS:
        cap = DQ_MAX_REPORTS

    var unit_cost = 0
    var checks = 0
    for i in range(k):
        if cols[i] < 0 or cols[i] >= n_cols:
            return ExpectationReport(DQ_ERR_COLUMN_INDEX, n_rows)
        if ops[i] < 0 or ops[i] > DQ_EXPECT_OP_MAX:
            return ExpectationReport(DQ_EXPECT_ERR_UNKNOWN_OP, n_rows)
        unit_cost += _plan_nodes_for(ops[i])
        checks += 2 if ops[i] == DQ_EXPECT_BETWEEN else 1

    # `k >= 1` and `_plan_nodes_for` never returns less than 1, so `unit_cost >= 1` and no
    # zero-cost branch is needed here. The `if k > 0 else 0` that used to guard this line was
    # what made an empty suite report `work_truncated = True` for a pass it never ran.
    var rows = dq_rows_within_budget(n_rows, unit_cost)
    var report = ExpectationReport(DQ_OK, n_rows)
    report.n_rows_checked = rows
    report.n_rows_not_checked = n_rows - rows
    report.work_truncated = rows < n_rows
    report.n_checks_per_row = checks

    var failed_row = List[Bool]()
    var unknown_row = List[Bool]()
    for _ in range(rows):
        failed_row.append(False)
        unknown_row.append(False)

    for i in range(k):
        # The PREFIX, not the column: `rows` is what the budget charged for, so `rows` is
        # what gets copied. See the docstring for the 29x this cost when it was `n_rows`.
        var values = dq_column_prefix(table, n_rows, n_cols, cols[i], rows)
        var present = dq_column_mask_prefix(null_mask, n_rows, n_cols, cols[i], rows)
        if ops[i] == DQ_EXPECT_BETWEEN:
            var s_low = _apply_check(
                report, failed_row, unknown_row, values, present, rows, cols[i],
                DQ_EXPECT_GE, lows[i], cap,
            )
            if s_low != DQ_OK:
                return ExpectationReport(s_low, n_rows)
            var s_high = _apply_check(
                report, failed_row, unknown_row, values, present, rows, cols[i],
                DQ_EXPECT_LE, highs[i], cap,
            )
            if s_high != DQ_OK:
                return ExpectationReport(s_high, n_rows)
        else:
            var s = _apply_check(
                report, failed_row, unknown_row, values, present, rows, cols[i],
                ops[i], lows[i], cap,
            )
            if s != DQ_OK:
                return ExpectationReport(s, n_rows)

    _finish(report, failed_row, unknown_row, rows)
    return report^


fn expect_plan_flat(
    table: List[Float64], n_rows: Int, n_cols: Int, null_mask: List[Bool],
    node_ints: List[Int], node_fvals: List[Float64], root: Int, subject_col: Int,
    max_reports: Int,
) raises -> ExpectationReport:
    """Run a caller-supplied `query.ir` plan as an expectation over a table.

    The plan is the frozen IR, flattened: `node_fvals[j]` is node `j`'s literal value and
    `node_ints` holds five integers per node — `op`, `var_idx`, `left`, `right`, `extra` —
    so `len(node_ints)` must be exactly `5 * len(node_fvals)`. That is a list-to-list
    length agreement, which the count grammar cannot express, so it is checked here and
    returned as `DQ_EXPECT_ERR_PLAN_ARRAYS` (rule 1d: check it in the kernel and say so
    rather than reaching for the nearest relation that parses).

    `subject_col` names the column a failure is ATTRIBUTED to, for the report. It does not
    constrain the plan, which may read any column — a plan can compare two columns, and
    the column a reader should look at is then the author's decision, not something the
    plan reveals.

    Four refusals, in this order, and the order is load-bearing:

      1. `root + 1 <= len(node_fvals)` and `root >= 0`. `root` is a subscript.
      2. `first_unsupported_op` — the measured process abort in the module docstring.
         A frozen opcode with `left = -1` passes `validation_error` and then reads
         `values[-1]`, which ends the worker.
      3. `validation_error` — out-of-range children, forward references, arity.
      4. strict evaluation. A masked case (divide by zero, a non-finite intermediate)
         is REFUSED as `DQ_EXPECT_ERR_EVAL_REFUSED` rather than evaluated permissively:
         substituting 0.0 for a division by zero is the frozen `expr.mojo` behaviour, and
         reporting expectation results computed from substituted zeros would be a clean
         bill of health for arithmetic that did not happen.

    @capability expect_plan_flat
    complexity: O(n_rows * len(node_fvals))
    counts:
    - n_rows * n_cols == len(table, null_mask) [kernel_validated]
    - root + 1 <= len(node_fvals) [kernel_validated]
    - dim subject_col [kernel_validated]
    - dim max_reports [clamped]
    @endcapability
    """
    var defect = dq_table_defect(table, n_rows, n_cols)
    if defect != DQ_OK:
        return ExpectationReport(defect, 0)
    if len(null_mask) != len(table):
        return ExpectationReport(dq_mask_defect(null_mask, len(table)), 0)

    var n_nodes = len(node_fvals)
    if n_nodes == 0:
        return ExpectationReport(DQ_EXPECT_ERR_NOTHING_TO_CHECK, n_rows)
    if n_nodes > DQ_MAX_NODES:
        return ExpectationReport(DQ_EXPECT_ERR_TOO_MANY_NODES, n_rows)
    if len(node_ints) != DQ_PLAN_STRIDE * n_nodes:
        return ExpectationReport(DQ_EXPECT_ERR_PLAN_ARRAYS, n_rows)
    if root < 0 or root >= n_nodes:
        return ExpectationReport(DQ_EXPECT_ERR_PLAN_ROOT, n_rows)
    if subject_col < 0 or subject_col >= n_cols:
        return ExpectationReport(DQ_ERR_COLUMN_INDEX, n_rows)

    var cap = max_reports
    if cap < 0:
        cap = 0
    if cap > DQ_MAX_REPORTS:
        cap = DQ_MAX_REPORTS

    var nodes = List[ExprNode]()
    for j in range(n_nodes):
        var base = DQ_PLAN_STRIDE * j
        nodes.append(
            ExprNode(
                node_ints[base], node_fvals[j], node_ints[base + 1],
                node_ints[base + 2], node_ints[base + 3], node_ints[base + 4],
            )
        )

    # Guard 2 before guard 3: `validation_error` says "" for the plan that aborts.
    if first_unsupported_op(nodes) >= 0:
        return ExpectationReport(DQ_EXPECT_ERR_UNSUPPORTED_OP, n_rows)
    if len(validation_error(nodes, root, n_cols)) > 0:
        return ExpectationReport(DQ_EXPECT_ERR_PLAN_INVALID, n_rows)

    # The plan may read any column, so the whole prefix of the table is materialised:
    # cost is (n_cols + n_nodes) per row, and both factors are charged.
    var rows = dq_rows_within_budget(n_rows, n_cols + n_nodes)
    var report = ExpectationReport(DQ_OK, n_rows)
    report.n_rows_checked = rows
    report.n_rows_not_checked = n_rows - rows
    report.work_truncated = rows < n_rows
    report.n_checks_per_row = 1

    var columns = List[Float64Array]()
    var names = List[String]()
    var dtypes = List[Int]()
    for c in range(n_cols):
        var prefix = dq_column_prefix(table, n_rows, n_cols, c, rows)
        var prefix_mask = dq_column_mask_prefix(null_mask, n_rows, n_cols, c, rows)
        columns.append(float64_with_nulls(prefix^, prefix_mask))
        names.append("c" + String(c))
        dtypes.append(DTYPE_FLOAT64)
    var batch = RecordBatch(Schema(names^, dtypes^), columns^, rows)

    var subject = dq_column_prefix(table, n_rows, n_cols, subject_col, rows)
    var subject_mask = dq_column_mask_prefix(null_mask, n_rows, n_cols, subject_col, rows)

    var verdict = List[Float64]()
    var decided = List[Bool]()
    var evaluated = True
    try:
        var out = evaluate(nodes, root, batch, True)
        for r in range(out.length):
            verdict.append(out.get(r))
            decided.append(out.is_valid_at(r))
    except:
        evaluated = False
    if not evaluated:
        return ExpectationReport(DQ_EXPECT_ERR_EVAL_REFUSED, n_rows)

    var failed_row = List[Bool]()
    var unknown_row = List[Bool]()
    for _ in range(rows):
        failed_row.append(False)
        unknown_row.append(False)
    for r in range(len(verdict)):
        if not decided[r]:
            report.n_unknown += 1
            unknown_row[r] = True
            continue
        if verdict[r] != 0.0:
            continue
        failed_row[r] = True
        _record(
            report, r, subject_col, DQ_EXPECT_PLAN_TRUE, 0.0,
            subject[r], subject_mask[r], cap,
        )
    _finish(report, failed_row, unknown_row, rows)
    return report^
