"""
progexec.exec — the FinQA operation vocabulary, executed exactly to the official evaluator's
own spec: unrounded intermediates, one round-half-to-even at the very end.

Where the string-level work happens, and why it is NOT here
-------------------------------------------------------------
A FinQA program's text form (`"divide(100, 100), divide(3.8, #0)"`) mixes three different
jobs: (1) tokenising the program text, (2) resolving a `table_*` op's row-name argument
against the report's table (a string-keyed lookup), and (3) the arithmetic. The first two
are PROGRAM GENERATION / PARSING in this task's own framing — deciding which operation and
which cell — and are done by the Python harness that calls this kernel, exactly as
`docs/mojo/new-kernel-package-rules.md` rule 2 asks: flat lists in, typed struct out. This
module receives only the THIRD job: op codes, tagged operands (a literal, a back-reference
to an earlier step, or a table row already sliced to its numeric cells), and produces the
step-by-step result.

This is a deliberate, checked simplification, not a shortcut: replaying the official
evaluator's OWN table branch against the real dataset (`code/evaluate/evaluate.py`,
`benchmarks/external_baselines/finqa_exec/reference_eval.py` here) shows no gold program
ever references a table row by `#i` (a back-reference standing in for a row NAME) — the
official code has that branch but it is dead on every one of the 8281 real gold programs
train+dev+test. `progexec` therefore requires `ARG_TABLE_ROW` (not `ARG_REF`) for a
`table_*` op's row and returns a typed refusal rather than silently accepting the case that
never occurs, so a future caller that DOES hit it fails loudly instead of getting a
plausible-looking wrong number.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64, bool
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_progexec_exec.mojo
benchmark: benchmarks/external_baselines/finqa_exec/
docs: docs/mojo/new-kernel-package-rules.md
version_introduced: 2026-08
deprecation_state: active
@endcapability
"""

from numeric.reduce import all_valid, is_finite_value, reduce_max, reduce_min, reduce_sum
from progexec.contract import (
    ARG_LITERAL,
    ARG_REF,
    ARG_TABLE_ROW,
    OP_ADD,
    OP_DIVIDE,
    OP_EXP,
    OP_GREATER,
    OP_MULTIPLY,
    OP_SUBTRACT,
    OP_TABLE_AVERAGE,
    OP_TABLE_MAX,
    OP_TABLE_MIN,
    OP_TABLE_SUM,
    PROGEXEC_ERR_BAD_ARG_KIND,
    PROGEXEC_ERR_BAD_REF,
    PROGEXEC_ERR_DIVIDE_BY_ZERO,
    PROGEXEC_ERR_EMPTY_PROGRAM,
    PROGEXEC_ERR_EMPTY_TABLE_ROW,
    PROGEXEC_ERR_LENGTH_MISMATCH,
    PROGEXEC_ERR_NON_FINITE,
    PROGEXEC_ERR_TABLE_RANGE,
    PROGEXEC_ERR_UNKNOWN_OP,
    PROGEXEC_OK,
    PROGEXEC_ROUND_SCALE,
)
from progexec.roundexact import round_half_even_scaled


@fieldwise_init
struct ProgExecResult(Copyable, Movable):
    """The final step's outcome. `present == False` means no answer exists — an invalid
    program, an out-of-range reference, a divide by zero, a non-finite result — and is
    the rule-4 absence, never a fabricated 0.0 standing in for it.

    `is_bool` distinguishes a `greater` final step (`bool_value` is the answer) from a
    numeric one (`value`, already rounded to `PROGEXEC_ROUND_SCALE`, is the answer) —
    FinQA's own `exe_ans` is either a float or the literal string `"yes"`/`"no"`, and
    collapsing that into one Float64 would either lose the distinction or invent a
    fractional value for a question that never had one."""

    var value: Float64
    var is_bool: Bool
    var bool_value: Bool
    var present: Bool
    var status: Int


fn _absent(status: Int) -> ProgExecResult:
    return ProgExecResult(0.0, False, False, False, status)


fn _resolve_operand(
    kind: Int,
    num: Float64,
    step_index: Int,
    results: List[Float64],
    result_is_bool: List[Bool],
    mut out: Float64,
) -> Bool:
    """Resolve one tagged operand against the results computed SO FAR. Returns False
    (out untouched) for anything the official evaluator would also refuse: an unknown
    kind, a forward or self reference, an out-of-range index, or a reference to a step
    whose own result was boolean (no real gold program does this — see the module
    docstring — so refusing it cannot turn a real answer wrong)."""
    if kind == ARG_LITERAL:
        out = num
        return True
    if kind == ARG_REF:
        var ref_idx = Int(num)
        if ref_idx < 0 or ref_idx >= step_index or ref_idx >= len(results):
            return False
        if result_is_bool[ref_idx]:
            return False
        out = results[ref_idx]
        return True
    return False


fn progexec_run_flat(
    ops: List[Int],
    arg1_kind: List[Int],
    arg1_num: List[Float64],
    arg2_kind: List[Int],
    arg2_num: List[Float64],
    table_values: List[Float64],
    table_offset: List[Int],
    table_len: List[Int],
    n_steps: Int,
) -> ProgExecResult:
    """Execute an `n_steps`-step FinQA program. Every `List` argument must have at least
    `n_steps` elements (rule 1: a caller-supplied count is validated against the real
    lengths before anything is indexed, not trusted).

    `table_offset[i]` / `table_len[i]` matter only when `ops[i]` is a `table_*` op: the
    row is `table_values[table_offset[i] : table_offset[i] + table_len[i])`, bounds-
    checked against `len(table_values)` before the slice is read. `arg2_kind[i]` /
    `arg2_num[i]` are ignored for `table_*` ops (FinQA's table aggregates are unary).

    @capability progexec_run_flat
    complexity: O(n_steps + total table row length)
    counts:
    - n_steps <= len(ops, arg1_kind, arg1_num, arg2_kind, arg2_num, table_offset, table_len) [kernel_validated]
    @endcapability
    """
    if n_steps <= 0:
        return _absent(PROGEXEC_ERR_EMPTY_PROGRAM)
    if (
        len(ops) < n_steps
        or len(arg1_kind) < n_steps
        or len(arg1_num) < n_steps
        or len(arg2_kind) < n_steps
        or len(arg2_num) < n_steps
        or len(table_offset) < n_steps
        or len(table_len) < n_steps
    ):
        return _absent(PROGEXEC_ERR_LENGTH_MISMATCH)

    var results = List[Float64]()
    var result_is_bool = List[Bool]()
    var result_bool = List[Bool]()

    var last_value: Float64 = 0.0
    var last_is_bool = False
    var last_bool = False

    for i in range(n_steps):
        var op = ops[i]

        if op == OP_TABLE_MAX or op == OP_TABLE_MIN or op == OP_TABLE_SUM or op == OP_TABLE_AVERAGE:
            if arg1_kind[i] != ARG_TABLE_ROW:
                return _absent(PROGEXEC_ERR_BAD_ARG_KIND)
            var off = table_offset[i]
            var ln = table_len[i]
            if off < 0 or ln < 0 or off + ln > len(table_values):
                return _absent(PROGEXEC_ERR_TABLE_RANGE)
            if ln == 0:
                return _absent(PROGEXEC_ERR_EMPTY_TABLE_ROW)
            var row = List[Float64]()
            for j in range(off, off + ln):
                row.append(table_values[j])
            var valid = all_valid(ln)

            var this_val: Float64 = 0.0
            if op == OP_TABLE_MAX:
                var r = reduce_max(row, valid)
                if not r.present:
                    return _absent(PROGEXEC_ERR_EMPTY_TABLE_ROW)
                this_val = r.value
            elif op == OP_TABLE_MIN:
                var r = reduce_min(row, valid)
                if not r.present:
                    return _absent(PROGEXEC_ERR_EMPTY_TABLE_ROW)
                this_val = r.value
            elif op == OP_TABLE_SUM:
                var r = reduce_sum(row, valid)
                this_val = r.value
            else:  # OP_TABLE_AVERAGE: plain sum/n (rule 3 note in contract.mojo) —
                # `reduce_sum` IS the frozen sum, called rather than re-summed here.
                var r = reduce_sum(row, valid)
                this_val = r.value / Float64(ln)

            if not is_finite_value(this_val):
                return _absent(PROGEXEC_ERR_NON_FINITE)

            results.append(this_val)
            result_is_bool.append(False)
            result_bool.append(False)
            last_value = this_val
            last_is_bool = False
            last_bool = False

        elif (
            op == OP_ADD
            or op == OP_SUBTRACT
            or op == OP_MULTIPLY
            or op == OP_DIVIDE
            or op == OP_EXP
            or op == OP_GREATER
        ):
            var a1: Float64 = 0.0
            var a2: Float64 = 0.0
            if not _resolve_operand(arg1_kind[i], arg1_num[i], i, results, result_is_bool, a1):
                return _absent(PROGEXEC_ERR_BAD_REF)
            if not _resolve_operand(arg2_kind[i], arg2_num[i], i, results, result_is_bool, a2):
                return _absent(PROGEXEC_ERR_BAD_REF)

            var this_val: Float64 = 0.0
            var this_bool = False
            var is_bool_step = False
            if op == OP_ADD:
                this_val = a1 + a2
            elif op == OP_SUBTRACT:
                this_val = a1 - a2
            elif op == OP_MULTIPLY:
                this_val = a1 * a2
            elif op == OP_DIVIDE:
                if a2 == 0.0:
                    return _absent(PROGEXEC_ERR_DIVIDE_BY_ZERO)
                this_val = a1 / a2
            elif op == OP_EXP:
                this_val = a1**a2
            else:  # OP_GREATER
                this_bool = a1 > a2
                is_bool_step = True

            if not is_bool_step and not is_finite_value(this_val):
                return _absent(PROGEXEC_ERR_NON_FINITE)

            results.append(this_val)
            result_is_bool.append(is_bool_step)
            result_bool.append(this_bool)
            last_value = this_val
            last_is_bool = is_bool_step
            last_bool = this_bool

        else:
            return _absent(PROGEXEC_ERR_UNKNOWN_OP)

    if last_is_bool:
        return ProgExecResult(0.0, True, last_bool, True, PROGEXEC_OK)

    var rounded = round_half_even_scaled(last_value, PROGEXEC_ROUND_SCALE)
    return ProgExecResult(rounded, False, False, True, PROGEXEC_OK)
