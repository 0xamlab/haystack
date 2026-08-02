"""
progexec.contract — the operation vocabulary, argument-kind tags, and status codes for
`progexec.exec`. Owns 1400-1419 (rule 4e). Zero Python imports.

What this package is for
-------------------------
FinQA (Chen et al., EMNLP 2021, github.com/czyssrs/FinQA) scores a predicted answer by
EXECUTING a short indexed program over ten operations — `add`, `subtract`, `multiply`,
`divide`, `exp`, `greater`, `table_max`, `table_min`, `table_sum`, `table_average` — where
each step may reference an earlier step's result by index (`#i`). The official evaluator
(`code/evaluate/evaluate.py`) keeps every intermediate result as an UNROUNDED Python
float and rounds only the FINAL step's value, once, with `round(x, 5)` (Python's
round-half-to-even). `progexec.exec` reproduces that spec exactly, over the same ten
operations, so the arithmetic step of scoring a program is a driver here rather than a
re-embedded copy of the evaluator's own float loop.

Two ways to get this wrong that are NOT hypothetical, verified against the real dataset
-----------------------------------------------------------------------------------------
1. Rounding an intermediate result before reuse (matching the official evaluator's own
   commented-out `# this_res = round(this_res, 5)` inside its table branch, which someone
   re-implementing the spec from that source is one keystroke from uncommenting for EVERY
   branch) flips 130 of the dataset's 8281 gold final answers relative to `exe_ans`.
2. Rounding the FINAL result with the "obvious" port of `round(x, 5)` — multiply by
   100000.0 in float64, round to the nearest integer, divide back — double-rounds on ties
   that a single float64 multiply corrupts. Six real gold programs hit this exactly
   (`HII/2011/page_100.pdf-3`, `RE/2010/page_42.pdf-4`, `CAT/2017/page_69.pdf-2`,
   `IP/2012/page_84.pdf-2`, `ETR/2017/page_143.pdf-2`, `HIG/2011/page_53.pdf-1`). This
   tree's own `currency.round_currency` — a frozen kernel already in `mojo/engine/`,
   docstring-labelled "banker's rounding" — shares the same single-multiply mechanism AND
   is separately round-half-up rather than round-half-to-even, and independently
   diverges from `exe_ans` on five real gold programs of its own (a different set, not a
   superset — round-half-up gets four of the six above right for the wrong reason; see
   `progexec.roundexact`'s module docstring for both lists). `progexec.roundexact` is
   written new because the frozen tool that looks like it fits is provably the wrong tool
   for reproducing this external spec bit-for-bit, not because no rounder exists in the
   tree.

Modules
-------
  roundexact — status codes none of its own (uses OK/none); `round_half_even_scaled`,
               a correctly-rounded round-half-to-even at a caller-supplied power-of-ten
               scale, built on `exactnum.eft`'s error-free transforms so a genuine decimal
               tie is decided from the exact value of `x * scale`, never from a
               single-rounded approximation of it.
  exec       — status codes 1400-1419; `progexec_run_flat`, the flat-list driver that
               walks a program's steps (op code, two tagged operands, an optional
               CSR-flattened table row) and returns a typed `ProgExecResult`.

What is genuinely missing, classified before anything was written
-------------------------------------------------------------------
* No existing kernel executes an INDEXED PROGRAM (a step referencing an earlier step's own
  result) at all — `optimization.model.evaluate_expr` evaluates a tree, not a flat
  index-referencing sequence, and its own opcode space (0-38) has no `table_max` /
  `table_min` / `table_sum` / `table_average` equivalent scoped to an arbitrary caller-
  supplied row rather than a fixed operand list. This is `exec`'s reason to exist.
* No existing rounder reproduces CPython's `round(x, n)` (round-half-to-even, decided from
  the exact value, not from a single float64 scaling multiply). `currency.round_currency`
  is the closest frozen candidate and is the wrong shape, per the note above. This is
  `roundexact`'s reason to exist.
* The table aggregates themselves are NOT reimplemented: `exec` calls
  `numeric.reduce.reduce_sum` / `reduce_max` / `reduce_min` directly (rule 3), and computes
  `table_average` as `reduce_sum(row).value / n` — the same plain `sum(row) / len(row)`
  the official evaluator uses — rather than `numeric.reduce.reduce_mean`'s Welford
  algorithm, which is a numerically BETTER but DIFFERENT-in-the-last-bit mean than plain
  `sum/n` and would occasionally disagree with `exe_ans` in the last decimal for exactly
  the reason `roundexact` exists: a different, if superior, arithmetic path is still a
  different bit pattern before the final rounding.

Status range
------------
`progexec` owns 1400-1419. Free at the time this was written (see
`docs/mojo/new-kernel-package-rules.md` rule 4e; grep the tree for `14[0-9][0-9]` beside a
`status` comment before reusing any part of this range for something else).

@capability-module
deterministic: true
stateful: false
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: int64
backend: mojo
surfaces: library_execute
golden_vectors: mojo/tests/libs/test_progexec_contract.mojo
benchmark: none
docs: docs/mojo/new-kernel-package-rules.md
version_introduced: 2026-08
deprecation_state: active
@endcapability
"""

# ── operation codes: one per FinQA op, matching evaluate.py's `all_ops` order ──
comptime OP_ADD: Int = 0
comptime OP_SUBTRACT: Int = 1
comptime OP_MULTIPLY: Int = 2
comptime OP_DIVIDE: Int = 3
comptime OP_EXP: Int = 4
comptime OP_GREATER: Int = 5
comptime OP_TABLE_MAX: Int = 6
comptime OP_TABLE_MIN: Int = 7
comptime OP_TABLE_SUM: Int = 8
comptime OP_TABLE_AVERAGE: Int = 9

# ── argument-kind tags, one per operand slot ───────────────────────────────────
comptime ARG_LITERAL: Int = 0
"""`arg*_num[i]` is the operand's value directly."""
comptime ARG_REF: Int = 1
"""`arg*_num[i]` is `Float64(j)` for an earlier step index `j < i` whose OWN result was
numeric (not boolean, not itself absent)."""
comptime ARG_TABLE_ROW: Int = 2
"""Valid for `arg1` on a `table_*` op only: the row lives in `table_values[table_offset[i],
table_offset[i] + table_len[i])`, already extracted and numeric-parsed by the caller (row
selection by the table's own string key is a lookup, not arithmetic, and is done ahead of
the kernel boundary — see `exec`'s module docstring)."""

# ── status codes: progexec owns 1400-1419 ──────────────────────────────────────
comptime PROGEXEC_OK: Int = 1400
comptime PROGEXEC_ERR_EMPTY_PROGRAM: Int = 1401
comptime PROGEXEC_ERR_LENGTH_MISMATCH: Int = 1402
comptime PROGEXEC_ERR_UNKNOWN_OP: Int = 1403
comptime PROGEXEC_ERR_BAD_ARG_KIND: Int = 1404
comptime PROGEXEC_ERR_BAD_REF: Int = 1405
comptime PROGEXEC_ERR_TABLE_RANGE: Int = 1406
comptime PROGEXEC_ERR_EMPTY_TABLE_ROW: Int = 1407
comptime PROGEXEC_ERR_DIVIDE_BY_ZERO: Int = 1408
comptime PROGEXEC_ERR_NON_FINITE: Int = 1409


fn progexec_status_name(code: Int) -> String:
    """The `progexec` status vocabulary. One integer, one meaning (rule 4e)."""
    if code == PROGEXEC_OK:
        return String("ok")
    if code == PROGEXEC_ERR_EMPTY_PROGRAM:
        return String("empty_program")
    if code == PROGEXEC_ERR_LENGTH_MISMATCH:
        return String("length_mismatch")
    if code == PROGEXEC_ERR_UNKNOWN_OP:
        return String("unknown_op")
    if code == PROGEXEC_ERR_BAD_ARG_KIND:
        return String("bad_arg_kind")
    if code == PROGEXEC_ERR_BAD_REF:
        return String("bad_ref")
    if code == PROGEXEC_ERR_TABLE_RANGE:
        return String("table_range")
    if code == PROGEXEC_ERR_EMPTY_TABLE_ROW:
        return String("empty_table_row")
    if code == PROGEXEC_ERR_DIVIDE_BY_ZERO:
        return String("divide_by_zero")
    if code == PROGEXEC_ERR_NON_FINITE:
        return String("non_finite")
    return String("unknown_status")


comptime PROGEXEC_ROUND_SCALE: Float64 = 100000.0
"""FinQA's own final-rounding precision: `round(x, 5)` in the official evaluator. A
literal, not `pow(10.0, 5)` — the scale must be exactly representable and exactly the
value the official evaluator's own rounding targets, not a transcendental approximation
of it (see the `reference_mojo_transcendental_precision` lesson: never let an imprecise
transcendental sit underneath a claimed-exact result)."""
