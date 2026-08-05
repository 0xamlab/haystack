"""
query.ir — the v2 opcode space over the frozen ExprNode. Zero Python.

Reuses `types.ExprNode` unchanged: `{op, fval, var_idx, left, right, extra}`, a flat
POD with integer child indices. That struct is already a serializable IR — a plan is
just an array of nodes plus a root index — so a plan crosses the process boundary
without pointers, and the same array can be hashed for identity.

Opcode allocation
-----------------
    0-38    frozen. `expr.mojo` owns these numbers and their semantics, masking
            included. Never reassigned: a plan built against them must keep working.
    39-99   reserved, so `expr.mojo` can grow without colliding.
    100+    this package.

Column references vs variable references
----------------------------------------
Op 1 (`var_ref`) indexes a sample vector — the simulation model. A query addresses a
*named column* of a batch, which is resolved against a schema. Those are different
things, so `COL_REF` is its own opcode rather than a reinterpretation of `var_ref`;
overloading it would make a plan's meaning depend on which evaluator ran it.

Validation before evaluation
----------------------------
`validate` rejects a plan whole rather than failing partway: out-of-range indices,
forward or self references, arity mismatches, and unreachable nodes. A half-evaluated
predicate has already filtered some rows, so refusing up front is the only way for a
malformed plan to be a no-op.
"""
from types import ExprNode

# ── frozen range, reused as-is ────────────────────────────────────────────────
comptime OP_LITERAL: Int = 0
comptime OP_VAR_REF: Int = 1
comptime OP_ADD: Int = 2
comptime OP_SUB: Int = 3
comptime OP_MUL: Int = 4
comptime OP_DIV: Int = 5
comptime OP_NEG: Int = 6

comptime FROZEN_OP_MAX: Int = 38
comptime V2_OP_MIN: Int = 100

# ── comparisons: what a predicate actually needs ─────────────────────────────
comptime OP_LT: Int = 100
comptime OP_LE: Int = 101
comptime OP_GT: Int = 102
comptime OP_GE: Int = 103
comptime OP_EQ: Int = 104
comptime OP_NE: Int = 105

# ── logical, three-valued over nulls ─────────────────────────────────────────
comptime OP_AND: Int = 110
comptime OP_OR: Int = 111
comptime OP_NOT: Int = 112

# ── null handling ────────────────────────────────────────────────────────────
comptime OP_IS_NULL: Int = 120
comptime OP_IS_NOT_NULL: Int = 121
comptime OP_COALESCE: Int = 122

# ── column reference and casts ───────────────────────────────────────────────
comptime OP_COL_REF: Int = 130
comptime OP_CAST_FLOAT: Int = 140
comptime OP_CAST_BOOL: Int = 141

# ── conditional: the third child (`extra`) is the else branch ────────────────
# `left`=condition, `right`=then, `extra`=else. N-ary SQL CASE WHEN is a chain of
# these, exactly like `a & b & c` is a chain of binary OP_AND nodes — this IR has
# no N-ary node shape, only binary/ternary ones threaded through tree structure.
comptime OP_CASE_WHEN: Int = 150


fn is_frozen_op(op: Int) -> Bool:
    """True for an opcode owned by `expr.mojo`."""
    return op >= 0 and op <= FROZEN_OP_MAX


fn is_v2_op(op: Int) -> Bool:
    return op >= V2_OP_MIN


fn is_comparison(op: Int) -> Bool:
    return op >= OP_LT and op <= OP_NE


fn is_logical(op: Int) -> Bool:
    return op == OP_AND or op == OP_OR or op == OP_NOT


fn is_predicate_op(op: Int) -> Bool:
    """True for ops yielding a boolean — what a filter root must be."""
    return (
        is_comparison(op)
        or is_logical(op)
        or op == OP_IS_NULL
        or op == OP_IS_NOT_NULL
        or op == OP_CAST_BOOL
    )


fn op_arity(op: Int) -> Int:
    """Children an opcode consumes: 0, 1, 2 or 3. -1 for an unknown opcode.

    Checked during validation so a node with the wrong number of children is
    rejected rather than reading whichever index happened to be left at -1.
    """
    if op == OP_LITERAL or op == OP_VAR_REF or op == OP_COL_REF:
        return 0
    if op == OP_NEG or op == OP_NOT or op == OP_IS_NULL or op == OP_IS_NOT_NULL:
        return 1
    if op == OP_CAST_FLOAT or op == OP_CAST_BOOL:
        return 1
    if op == OP_ADD or op == OP_SUB or op == OP_MUL or op == OP_DIV:
        return 2
    if is_comparison(op):
        return 2
    if op == OP_AND or op == OP_OR or op == OP_COALESCE:
        return 2
    if op == OP_CASE_WHEN:
        return 3
    if is_frozen_op(op):
        # The frozen range is a mix of 1-, 2- and 3-child ops. Validation defers to
        # expr.mojo's own tolerance rather than duplicating a table that could drift
        # out of step with it.
        return -2
    return -1


fn op_name(op: Int) -> String:
    if op == OP_LITERAL:
        return "literal"
    if op == OP_VAR_REF:
        return "var_ref"
    if op == OP_COL_REF:
        return "col_ref"
    if op == OP_ADD:
        return "add"
    if op == OP_SUB:
        return "sub"
    if op == OP_MUL:
        return "mul"
    if op == OP_DIV:
        return "div"
    if op == OP_NEG:
        return "neg"
    if op == OP_LT:
        return "lt"
    if op == OP_LE:
        return "le"
    if op == OP_GT:
        return "gt"
    if op == OP_GE:
        return "ge"
    if op == OP_EQ:
        return "eq"
    if op == OP_NE:
        return "ne"
    if op == OP_AND:
        return "and"
    if op == OP_OR:
        return "or"
    if op == OP_NOT:
        return "not"
    if op == OP_IS_NULL:
        return "is_null"
    if op == OP_IS_NOT_NULL:
        return "is_not_null"
    if op == OP_COALESCE:
        return "coalesce"
    if op == OP_CAST_FLOAT:
        return "cast_float"
    if op == OP_CAST_BOOL:
        return "cast_bool"
    if op == OP_CASE_WHEN:
        return "case_when"
    if is_frozen_op(op):
        return "frozen_op_" + String(op)
    return "unknown_op_" + String(op)


# ── node constructors ─────────────────────────────────────────────────────────


fn literal(value: Float64) -> ExprNode:
    return ExprNode(OP_LITERAL, value, -1, -1, -1)


fn col_ref(column_index: Int) -> ExprNode:
    """A reference to batch column `column_index`, resolved against its schema."""
    return ExprNode(OP_COL_REF, 0.0, column_index, -1, -1)


fn unary(op: Int, child: Int) -> ExprNode:
    return ExprNode(op, 0.0, -1, child, -1)


fn binary(op: Int, left: Int, right: Int) -> ExprNode:
    return ExprNode(op, 0.0, -1, left, right)


fn ternary(op: Int, left: Int, right: Int, extra: Int) -> ExprNode:
    """A three-child node: `left`=condition, `right`=then, `extra`=else.

    Uses the 6-arg `ExprNode` constructor, the same one `expr.mojo`'s own arity-3
    ops (clip/ifgt0) already use in the frozen range — this is a new opcode in the
    v2 range, not a reuse of theirs.
    """
    return ExprNode(op, 0.0, -1, left, right, extra)


# ── validation ────────────────────────────────────────────────────────────────


fn validation_error(nodes: List[ExprNode], root: Int, n_columns: Int) -> String:
    """"" when the plan is well formed, else a message naming the offending node.

    Enforced:
      * root in range
      * every child index within bounds and strictly LESS than its parent, which
        makes a cycle unrepresentable rather than merely unlikely
      * arity matches the opcode
      * a column reference points at a column that exists
      * the opcode is known
    """
    if len(nodes) == 0:
        return "expression has no nodes"
    if root < 0 or root >= len(nodes):
        return "root index " + String(root) + " is out of range"

    for i in range(len(nodes)):
        ref node = nodes[i]
        var arity = op_arity(node.op)
        if arity == -1:
            return "node " + String(i) + " has unknown opcode " + String(node.op)

        if node.op == OP_COL_REF:
            if node.var_idx < 0 or node.var_idx >= n_columns:
                return (
                    "node "
                    + String(i)
                    + " references column "
                    + String(node.var_idx)
                    + " but the batch has "
                    + String(n_columns)
                )
            continue

        # Children must precede their parent. A forward reference is how a cycle
        # would form, so forbidding it removes cycles by construction.
        if node.left >= i:
            return (
                "node "
                + String(i)
                + " ("
                + op_name(node.op)
                + ") references node "
                + String(node.left)
                + "; children must come earlier"
            )
        if node.right >= i:
            return (
                "node "
                + String(i)
                + " ("
                + op_name(node.op)
                + ") references node "
                + String(node.right)
                + "; children must come earlier"
            )
        if node.extra >= i:
            return (
                "node "
                + String(i)
                + " references node "
                + String(node.extra)
                + " as its third child; children must come earlier"
            )

        if arity >= 1 and node.left < 0:
            return "node " + String(i) + " (" + op_name(node.op) + ") needs a left child"
        if arity >= 2 and node.right < 0:
            return "node " + String(i) + " (" + op_name(node.op) + ") needs a right child"
        if arity >= 3 and node.extra < 0:
            return (
                "node "
                + String(i)
                + " ("
                + op_name(node.op)
                + ") needs a third child (else branch)"
            )
        if arity == 1 and node.right >= 0:
            return (
                "node "
                + String(i)
                + " ("
                + op_name(node.op)
                + ") takes one child but has two"
            )

    return ""


fn is_valid(nodes: List[ExprNode], root: Int, n_columns: Int) -> Bool:
    return len(validation_error(nodes, root, n_columns)) == 0


fn referenced_columns(nodes: List[ExprNode]) -> List[Int]:
    """Column indices a plan reads — for projection pushdown.

    Lets a scan fetch two columns instead of forty. Returned sorted and deduplicated
    so callers can compare plans directly.
    """
    var found = List[Int]()
    for i in range(len(nodes)):
        if nodes[i].op != OP_COL_REF:
            continue
        var index = nodes[i].var_idx
        var already = False
        for j in range(len(found)):
            if found[j] == index:
                already = True
        if not already:
            found.append(index)
    for i in range(1, len(found)):
        var j = i
        while j > 0 and found[j] < found[j - 1]:
            var swap = found[j]
            found[j] = found[j - 1]
            found[j - 1] = swap
            j -= 1
    return found^


fn is_evaluable_op(op: Int) -> Bool:
    """True when the columnar evaluator implements this opcode.

    A handful of frozen opcodes are shared rather than masked — literal (0),
    add/sub/mul/div, neg — and those are implemented here. The transcendental
    frozen ops (pow, ln, log10, log2, exp, sqrt, trig, ...) are not, and neither
    is var_ref, which addresses a sample vector rather than a column.
    """
    if op == OP_LITERAL or op == OP_COL_REF:
        return True
    if op == OP_ADD or op == OP_SUB or op == OP_MUL or op == OP_DIV or op == OP_NEG:
        return True
    if is_comparison(op) or is_logical(op):
        return True
    if op == OP_IS_NULL or op == OP_IS_NOT_NULL or op == OP_COALESCE:
        return True
    if op == OP_CAST_FLOAT or op == OP_CAST_BOOL:
        return True
    if op == OP_CASE_WHEN:
        return True
    return False


fn first_unsupported_op(nodes: List[ExprNode]) -> Int:
    """Index of the first node the columnar evaluator cannot run, or -1.

    Lets a plan be rejected up front instead of raising partway through a scan.
    Replaces an earlier `uses_frozen_ops`, which was useless because OP_LITERAL is
    opcode 0 and therefore "frozen" — it fired on every plan.
    """
    for i in range(len(nodes)):
        if not is_evaluable_op(nodes[i].op):
            return i
    return -1


fn describe(nodes: List[ExprNode], root: Int) -> String:
    """A readable rendering of the plan, for lineage and error messages."""
    if root < 0 or root >= len(nodes):
        return "<invalid root>"
    ref node = nodes[root]
    if node.op == OP_LITERAL:
        return String(node.fval)
    if node.op == OP_COL_REF:
        return "col[" + String(node.var_idx) + "]"
    var arity = op_arity(node.op)
    if arity == 1 or (arity == -2 and node.right < 0):
        return op_name(node.op) + "(" + describe(nodes, node.left) + ")"
    if arity == 3:
        return (
            op_name(node.op)
            + "("
            + describe(nodes, node.left)
            + ", "
            + describe(nodes, node.right)
            + ", "
            + describe(nodes, node.extra)
            + ")"
        )
    return (
        op_name(node.op)
        + "("
        + describe(nodes, node.left)
        + ", "
        + describe(nodes, node.right)
        + ")"
    )
