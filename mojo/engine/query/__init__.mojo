"""
query — typed expression IR and a columnar executor.

`expr.mojo` already is an expression IR: a parser and evaluator over a flat
`ExprNode` array with integer child indices, 39 opcodes, no pointers. It is frozen
and reused as-is — this package extends the opcode space rather than replacing the
node type, so one representation serves both.

What it cannot express, and why that matters
--------------------------------------------
* **No comparisons.** No `<`, `>`, `==`, `<=`, `>=`, `!=`. Its `if` (op 20) tests
  `cond > 0.0`, so a filter predicate has to be smuggled through arithmetic.
* **No logical operators.** No `and`, `or`, `not`.
* **No null concept.** Float64 only, so "missing" cannot be represented at all.
* **Errors are masked, not raised.** Divide by zero yields 0.0; a negative base to
  `pow` yields 0.0; `log` clamps its argument to 1e-300; an out-of-range node or
  variable index yields 0.0. Each is a silent wrong answer.
* **Scalar tree-walk per row.** Correct, but the wrong shape for a column at a time.

Those five are exactly what a query predicate needs, which is why this exists rather
than a call into `expr.mojo`.

The frozen semantics stay reachable
-----------------------------------
Opcodes 0-38 keep their numbers and their behaviour, including the masking. New
opcodes start at 100. `eval` runs strict by default — each masked case becomes a
typed error — and permissive mode reproduces the frozen behaviour exactly, so the
two can be compared rather than assumed equivalent.

Modules:
  ir   — the v2 opcode space, node constructors, and plan validation
  eval — column-at-a-time evaluation over a RecordBatch

Invoked directly rather than through `library_execute`, so this package is excluded
from the runtime-library inventory.
"""
