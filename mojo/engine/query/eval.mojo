"""
query.eval — evaluate an expression over a whole column at a time. Zero Python.

`expr.mojo` walks the tree once per row. That is right for a simulation objective
(one sample at a time) and wrong for a query, where the same tree applies to every
row: the per-row walk pays tree traversal N times and cannot use the validity mask.

Here each node is evaluated across all rows into a scratch column, bottom-up. Nodes
are already ordered so children precede parents, so a single forward pass suffices —
no recursion, no visited set.

Null semantics
--------------
Arithmetic and comparison propagate: any null operand yields a null result. That is
SQL's rule and the only one consistent with "null means unknown" — the sum of a
number and an unknown is unknown, not the number.

Logical operators are three-valued, and deliberately *not* strict:

    true  OR  null  -> true      (already decided, whatever the unknown is)
    false AND null  -> false     (already decided)
    false OR  null  -> null      (still unknown)
    true  AND null  -> null      (still unknown)

Collapsing unknown to false here is the common shortcut and it silently drops rows
that should have been reported as indeterminate.

`CASE WHEN cond THEN then ELSE else END` (`OP_CASE_WHEN`, ternary: `left`=cond,
`right`=then, `extra`=else) is NOT arithmetic and does not propagate null the way
the general rule above does. It reads `cond`'s mask/value the way a predicate does:

    cond known and true   -> THEN branch, passed through verbatim (a null THEN
                              stays null; the mask is THEN's own, not forced valid)
    cond known and false  -> ELSE branch, passed through verbatim
    cond unknown (null)   -> ELSE branch — unknown is not true, exactly the rule
                              `evaluate_predicate` already states for a filter root,
                              so an unknown condition falls through rather than
                              making the whole CASE null.

Strict vs permissive
--------------------
Strict (the default) turns each of `expr.mojo`'s five masked cases into a typed
error naming the row: divide by zero, negative base to `pow`, non-positive `log`,
out-of-range node index, out-of-range variable index. Permissive reproduces the
frozen behaviour exactly, so the two modes can be compared rather than assumed
equivalent — and a caller who needs the old numbers can still get them.
"""
from std.math import isinf, isnan, log, sqrt

from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch
from columnar.validity import is_valid
from query.ir import (
    OP_ADD,
    OP_AND,
    OP_CASE_WHEN,
    OP_CAST_BOOL,
    OP_CAST_FLOAT,
    OP_COALESCE,
    OP_COL_REF,
    OP_DIV,
    OP_EQ,
    OP_GE,
    OP_GT,
    OP_IS_NOT_NULL,
    OP_IS_NULL,
    OP_LE,
    OP_LITERAL,
    OP_LT,
    OP_MUL,
    OP_NE,
    OP_NEG,
    OP_NOT,
    OP_OR,
    OP_SUB,
    op_name,
    validation_error,
)
from types import ExprNode

# Booleans travel as 1.0/0.0 in a Float64 column, so one column type carries both
# predicates and values. A separate BoolArray path would double every operator.
comptime TRUE_VALUE: Float64 = 1.0
comptime FALSE_VALUE: Float64 = 0.0


fn _truthy(value: Float64) -> Bool:
    return value != 0.0


fn evaluate(
    nodes: List[ExprNode],
    root: Int,
    batch: RecordBatch,
    strict: Bool,
) raises -> Float64Array:
    """Evaluate `nodes[root]` across every row of `batch`.

    Returns a column of the same length. Validation runs first, so a malformed plan
    raises before any row is touched.
    """
    var problem = validation_error(nodes, root, batch.width())
    if len(problem) > 0:
        raise Error("query.eval: " + problem)

    var n = batch.n_rows
    # One scratch column per node. Nodes are topologically ordered already, so a
    # single forward pass fills every slot before its parent reads it.
    var values = List[List[Float64]]()
    var masks = List[List[Bool]]()

    for i in range(len(nodes)):
        ref node = nodes[i]
        var out_values = List[Float64]()
        var out_mask = List[Bool]()

        if node.op == OP_LITERAL:
            for _ in range(n):
                out_values.append(node.fval)
                out_mask.append(True)

        elif node.op == OP_COL_REF:
            var column = batch.column(node.var_idx)
            for r in range(n):
                out_values.append(column.get(r))
                out_mask.append(column.is_valid_at(r))

        elif node.op == OP_IS_NULL or node.op == OP_IS_NOT_NULL:
            # The one place a null input yields a NON-null output: asking whether a
            # value is missing is always answerable.
            ref child_mask = masks[node.left]
            for r in range(n):
                var absent = not child_mask[r]
                var answer = absent if node.op == OP_IS_NULL else not absent
                out_values.append(TRUE_VALUE if answer else FALSE_VALUE)
                out_mask.append(True)

        elif node.op == OP_COALESCE:
            ref lv = values[node.left]
            ref lm = masks[node.left]
            ref rv = values[node.right]
            ref rm = masks[node.right]
            for r in range(n):
                if lm[r]:
                    out_values.append(lv[r])
                    out_mask.append(True)
                elif rm[r]:
                    out_values.append(rv[r])
                    out_mask.append(True)
                else:
                    out_values.append(0.0)
                    out_mask.append(False)

        elif node.op == OP_CASE_WHEN:
            # cond known-and-true -> THEN, passed through verbatim (mask included).
            # cond known-and-false OR cond unknown -> ELSE, passed through verbatim.
            # Unlike OP_AND/OP_OR, the output is never "unknown because cond was
            # unknown" — an unknown cond is simply not true, so it falls to ELSE
            # exactly like evaluate_predicate's own "unknown is not true" rule.
            ref cv = values[node.left]
            ref cm = masks[node.left]
            ref tv = values[node.right]
            ref tm = masks[node.right]
            ref ev = values[node.extra]
            ref em = masks[node.extra]
            for r in range(n):
                var cond_true = cm[r] and _truthy(cv[r])
                if cond_true:
                    out_values.append(tv[r])
                    out_mask.append(tm[r])
                else:
                    out_values.append(ev[r])
                    out_mask.append(em[r])

        elif node.op == OP_AND or node.op == OP_OR:
            ref lv2 = values[node.left]
            ref lm2 = masks[node.left]
            ref rv2 = values[node.right]
            ref rm2 = masks[node.right]
            for r in range(n):
                var l_known = lm2[r]
                var r_known = rm2[r]
                var l_true = l_known and _truthy(lv2[r])
                var r_true = r_known and _truthy(rv2[r])
                if node.op == OP_OR:
                    # Decided as soon as either side is true, even if the other is
                    # unknown.
                    if l_true or r_true:
                        out_values.append(TRUE_VALUE)
                        out_mask.append(True)
                    elif l_known and r_known:
                        out_values.append(FALSE_VALUE)
                        out_mask.append(True)
                    else:
                        out_values.append(0.0)
                        out_mask.append(False)
                else:
                    var l_false = l_known and not _truthy(lv2[r])
                    var r_false = r_known and not _truthy(rv2[r])
                    if l_false or r_false:
                        out_values.append(FALSE_VALUE)
                        out_mask.append(True)
                    elif l_known and r_known:
                        out_values.append(TRUE_VALUE)
                        out_mask.append(True)
                    else:
                        out_values.append(0.0)
                        out_mask.append(False)

        elif node.op == OP_NOT:
            ref cv = values[node.left]
            ref cm = masks[node.left]
            for r in range(n):
                if not cm[r]:
                    out_values.append(0.0)
                    out_mask.append(False)
                else:
                    out_values.append(FALSE_VALUE if _truthy(cv[r]) else TRUE_VALUE)
                    out_mask.append(True)

        elif node.op == OP_NEG or node.op == OP_CAST_FLOAT or node.op == OP_CAST_BOOL:
            ref uv = values[node.left]
            ref um = masks[node.left]
            for r in range(n):
                if not um[r]:
                    out_values.append(0.0)
                    out_mask.append(False)
                    continue
                if node.op == OP_NEG:
                    out_values.append(-uv[r])
                elif node.op == OP_CAST_BOOL:
                    out_values.append(TRUE_VALUE if _truthy(uv[r]) else FALSE_VALUE)
                else:
                    out_values.append(uv[r])
                out_mask.append(True)

        else:
            # Binary arithmetic and comparison: null propagates.
            ref av = values[node.left]
            ref am = masks[node.left]
            ref bv = values[node.right]
            ref bm = masks[node.right]
            for r in range(n):
                if not am[r] or not bm[r]:
                    out_values.append(0.0)
                    out_mask.append(False)
                    continue
                var a = av[r]
                var b = bv[r]
                var result: Float64 = 0.0
                if node.op == OP_ADD:
                    result = a + b
                elif node.op == OP_SUB:
                    result = a - b
                elif node.op == OP_MUL:
                    result = a * b
                elif node.op == OP_DIV:
                    if b == 0.0:
                        if strict:
                            raise Error(
                                "query.eval: divide by zero at row "
                                + String(r)
                                + " in node "
                                + String(i)
                            )
                        # Permissive reproduces expr.mojo exactly.
                        result = 0.0
                    else:
                        result = a / b
                elif node.op == OP_LT:
                    result = TRUE_VALUE if a < b else FALSE_VALUE
                elif node.op == OP_LE:
                    result = TRUE_VALUE if a <= b else FALSE_VALUE
                elif node.op == OP_GT:
                    result = TRUE_VALUE if a > b else FALSE_VALUE
                elif node.op == OP_GE:
                    result = TRUE_VALUE if a >= b else FALSE_VALUE
                elif node.op == OP_EQ:
                    result = TRUE_VALUE if a == b else FALSE_VALUE
                elif node.op == OP_NE:
                    result = TRUE_VALUE if a != b else FALSE_VALUE
                else:
                    raise Error(
                        "query.eval: opcode "
                        + op_name(node.op)
                        + " is not implemented by the columnar evaluator"
                    )

                if strict and (isnan(result) or isinf(result)):
                    raise Error(
                        "query.eval: non-finite result at row "
                        + String(r)
                        + " in node "
                        + String(i)
                        + " ("
                        + op_name(node.op)
                        + ")"
                    )
                out_values.append(result)
                out_mask.append(True)

        values.append(out_values^)
        masks.append(out_mask^)

    var final_values = List[Float64]()
    var final_mask = List[Bool]()
    for r in range(n):
        final_values.append(values[root][r])
        final_mask.append(masks[root][r])
    return float64_with_nulls(final_values^, final_mask)


fn evaluate_predicate(
    nodes: List[ExprNode],
    root: Int,
    batch: RecordBatch,
    strict: Bool,
) raises -> List[Bool]:
    """A row mask for a filter: true only where the predicate is present AND true.

    Unknown is not true. A row whose predicate is indeterminate does not pass — but
    the evaluator distinguished it from `false` on the way here, so a caller that
    cares can inspect the column instead of the mask.
    """
    var column = evaluate(nodes, root, batch, strict)
    var mask = List[Bool]()
    for r in range(column.length):
        mask.append(column.is_valid_at(r) and _truthy(column.get(r)))
    return mask^


fn unknown_rows(
    nodes: List[ExprNode],
    root: Int,
    batch: RecordBatch,
    strict: Bool,
) raises -> Int:
    """How many rows a predicate could not decide.

    Reportable rather than invisible: "1,200 rows excluded because `region` was
    missing" is actionable, and a plain filter cannot say it.
    """
    var column = evaluate(nodes, root, batch, strict)
    var n = 0
    for r in range(column.length):
        if not column.is_valid_at(r):
            n += 1
    return n
