"""test_query_ir.mojo — known-value tests for the v2 IR and columnar evaluator.

Hand-written. The assertions that matter are the ones `expr.mojo` cannot satisfy:
comparisons and logicals exist, nulls propagate through arithmetic but not through
`is_null`, three-valued logic short-circuits on a decided operand, and strict mode
raises where the frozen evaluator would have substituted 0.0.
"""
from columnar.array import Float64Array, float64_from_list, float64_with_nulls
from columnar.batch import RecordBatch, schema_of
from query.eval import evaluate, evaluate_predicate, unknown_rows
from query.ir import (
    FROZEN_OP_MAX,
    OP_ADD,
    OP_AND,
    OP_COALESCE,
    OP_COL_REF,
    OP_DIV,
    OP_EQ,
    OP_GT,
    OP_IS_NOT_NULL,
    OP_IS_NULL,
    OP_LT,
    OP_MUL,
    OP_NOT,
    OP_OR,
    V2_OP_MIN,
    binary,
    col_ref,
    describe,
    is_frozen_op,
    is_predicate_op,
    is_v2_op,
    is_valid,
    literal,
    op_arity,
    op_name,
    referenced_columns,
    unary,
    first_unsupported_op,
    is_evaluable_op,
    validation_error,
)
from types import ExprNode


fn _batch() -> RecordBatch:
    """amount = [10, 20, 30, 40]; qty = [1, 2, null, 4]."""
    var amount = List[Float64]()
    amount.append(10.0)
    amount.append(20.0)
    amount.append(30.0)
    amount.append(40.0)

    var qty = List[Float64]()
    qty.append(1.0)
    qty.append(2.0)
    qty.append(0.0)
    qty.append(4.0)
    var qty_mask = List[Bool]()
    qty_mask.append(True)
    qty_mask.append(True)
    qty_mask.append(False)
    qty_mask.append(True)

    var names = List[String]()
    names.append("amount")
    names.append("qty")
    var cols = List[Float64Array]()
    cols.append(float64_from_list(amount^))
    cols.append(float64_with_nulls(qty^, qty_mask))
    return RecordBatch(schema_of(names^), cols^, 4)


fn main() raises:
    var passed = 0
    var failed = 0
    var batch = _batch()

    # ── the opcode spaces do not overlap ─────────────────────────────────────
    if (
        is_frozen_op(0)
        and is_frozen_op(FROZEN_OP_MAX)
        and not is_frozen_op(V2_OP_MIN)
        and is_v2_op(OP_LT)
        and V2_OP_MIN > FROZEN_OP_MAX
    ):
        passed += 1
        print("  ✅ frozen 0-38 and v2 100+ do not overlap")
    else:
        failed += 1
        print("  ❌ opcode spaces overlap")

    # ── comparisons and logicals are classified as predicates ────────────────
    if (
        is_predicate_op(OP_GT)
        and is_predicate_op(OP_AND)
        and is_predicate_op(OP_IS_NULL)
        and not is_predicate_op(OP_ADD)
        and not is_predicate_op(OP_COL_REF)
    ):
        passed += 1
        print("  ✅ predicate ops classified; arithmetic is not a predicate")
    else:
        failed += 1
        print("  ❌ predicate classification wrong")

    # ── arity is known, and an unknown opcode is rejected ────────────────────
    if (
        op_arity(OP_COL_REF) == 0
        and op_arity(OP_NOT) == 1
        and op_arity(OP_AND) == 2
        and op_arity(9999) == -1
    ):
        passed += 1
        print("  ✅ arity table covers 0/1/2 children and rejects an unknown opcode")
    else:
        failed += 1
        print("  ❌ arity wrong")

    # ── a well-formed plan validates ────────────────────────────────────────
    # amount > 15
    var plan = List[ExprNode]()
    plan.append(col_ref(0))
    plan.append(literal(15.0))
    plan.append(binary(OP_GT, 0, 1))
    if is_valid(plan, 2, 2) and len(validation_error(plan, 2, 2)) == 0:
        passed += 1
        print("  ✅ a well-formed plan validates")
    else:
        failed += 1
        print("  ❌ valid plan rejected:", validation_error(plan, 2, 2))

    # ── a forward reference is rejected, naming the node ─────────────────────
    var forward = List[ExprNode]()
    forward.append(binary(OP_ADD, 1, 2))  # node 0 pointing at 1 and 2
    forward.append(literal(1.0))
    forward.append(literal(2.0))
    var forward_err = validation_error(forward, 0, 2)
    if len(forward_err) > 0 and forward_err.find("earlier") >= 0:
        passed += 1
        print("  ✅ a forward reference is rejected: cycles are unrepresentable")
    else:
        failed += 1
        print("  ❌ forward reference accepted")

    # ── a column reference past the schema is rejected ───────────────────────
    var bad_col = List[ExprNode]()
    bad_col.append(col_ref(9))
    if len(validation_error(bad_col, 0, 2)) > 0:
        passed += 1
        print("  ✅ a column reference beyond the schema is rejected")
    else:
        failed += 1
        print("  ❌ out-of-range column accepted")

    # ── an out-of-range root and a missing child are rejected ────────────────
    var missing_child = List[ExprNode]()
    missing_child.append(ExprNode(OP_ADD, 0.0, -1, -1, -1))
    if len(validation_error(plan, 99, 2)) > 0 and len(
        validation_error(missing_child, 0, 2)
    ) > 0:
        passed += 1
        print("  ✅ a bad root and a childless binary op are both rejected")
    else:
        failed += 1
        print("  ❌ structural validation gap")

    # ── comparison evaluates across the column ──────────────────────────────
    var gt_mask = evaluate_predicate(plan, 2, batch, True)
    if len(gt_mask) == 4 and not gt_mask[0] and gt_mask[1] and gt_mask[2] and gt_mask[3]:
        passed += 1
        print("  ✅ amount > 15 selects rows 1,2,3 — a comparison expr.mojo lacks")
    else:
        failed += 1
        print("  ❌ comparison wrong")

    # ── null propagates through arithmetic ──────────────────────────────────
    # amount * qty; qty row 2 is null, so row 2 of the result is null.
    var product = List[ExprNode]()
    product.append(col_ref(0))
    product.append(col_ref(1))
    product.append(binary(OP_MUL, 0, 1))
    var prod = evaluate(product, 2, batch, True)
    if (
        prod.get(0) == 10.0
        and prod.get(1) == 40.0
        and not prod.is_valid_at(2)
        and prod.get(3) == 160.0
        and prod.null_count() == 1
    ):
        passed += 1
        print("  ✅ null propagates through arithmetic (row 2 stays unknown)")
    else:
        failed += 1
        print("  ❌ null propagation wrong:", prod.null_count())

    # ── is_null answers even when its input is null ──────────────────────────
    var nullcheck = List[ExprNode]()
    nullcheck.append(col_ref(1))
    nullcheck.append(unary(OP_IS_NULL, 0))
    var nulls = evaluate(nullcheck, 1, batch, True)
    if (
        nulls.null_count() == 0  # every answer is known
        and nulls.get(0) == 0.0
        and nulls.get(2) == 1.0
    ):
        passed += 1
        print("  ✅ is_null is always answerable, even over a null input")
    else:
        failed += 1
        print("  ❌ is_null wrong")

    var notnull = List[ExprNode]()
    notnull.append(col_ref(1))
    notnull.append(unary(OP_IS_NOT_NULL, 0))
    var nn_mask = evaluate_predicate(notnull, 1, batch, True)
    if nn_mask[0] and nn_mask[1] and not nn_mask[2] and nn_mask[3]:
        passed += 1
        print("  ✅ is_not_null selects exactly the present rows")
    else:
        failed += 1
        print("  ❌ is_not_null wrong")

    # ── three-valued OR: true OR unknown is TRUE, not unknown ────────────────
    # (amount > 15) OR (qty > 100). Row 2's qty is null, but amount>15 is true, so
    # the row is decided. Collapsing unknown to false would still give true here, so
    # row 0 is the discriminating case: false OR unknown must be UNKNOWN.
    var three_valued = List[ExprNode]()
    three_valued.append(col_ref(0))       # 0 amount
    three_valued.append(literal(50.0))    # 1
    three_valued.append(binary(OP_GT, 0, 1))   # 2 amount > 15
    three_valued.append(col_ref(1))       # 3 qty
    three_valued.append(literal(100.0))   # 4
    three_valued.append(binary(OP_GT, 3, 4))   # 5 qty > 100
    three_valued.append(binary(OP_OR, 2, 5))   # 6
    var or_col = evaluate(three_valued, 6, batch, True)
    # amount>50 is false everywhere; qty>100 is false,false,UNKNOWN,false.
    # Row 2 is therefore false OR unknown, which must stay UNKNOWN — the case that
    # distinguishes three-valued logic from collapsing unknown to false.
    if (
        or_col.is_valid_at(0)
        and or_col.get(0) == 0.0   # false OR false -> false, decided
        and not or_col.is_valid_at(2)  # false OR unknown -> unknown
    ):
        passed += 1
        print("  ✅ three-valued OR: false OR unknown stays unknown, false OR false is false")
    else:
        failed += 1
        print("  ❌ OR semantics wrong:", or_col.is_valid_at(0), or_col.is_valid_at(2))

    # ── three-valued AND: false AND unknown is FALSE ────────────────────────
    var and_plan = List[ExprNode]()
    and_plan.append(col_ref(0))          # 0 amount
    and_plan.append(literal(15.0))       # 1
    and_plan.append(binary(OP_LT, 0, 1)) # 2 amount < 15  -> true,false,false,false
    and_plan.append(col_ref(1))          # 3 qty
    and_plan.append(literal(0.0))        # 4
    and_plan.append(binary(OP_GT, 3, 4)) # 5 qty > 0      -> true,true,null,true
    and_plan.append(binary(OP_AND, 2, 5))# 6
    var and_col = evaluate(and_plan, 6, batch, True)
    if (
        and_col.is_valid_at(2)      # false AND unknown -> false, decided
        and and_col.get(2) == 0.0
        and and_col.is_valid_at(0)
        and and_col.get(0) == 1.0
    ):
        passed += 1
        print("  ✅ three-valued AND: false AND unknown = false, decided")
    else:
        failed += 1
        print("  ❌ AND semantics wrong")

    # ── NOT of unknown stays unknown ────────────────────────────────────────
    var not_plan = List[ExprNode]()
    not_plan.append(col_ref(1))
    not_plan.append(literal(0.0))
    not_plan.append(binary(OP_GT, 0, 1))
    not_plan.append(unary(OP_NOT, 2))
    var not_col = evaluate(not_plan, 3, batch, True)
    if not not_col.is_valid_at(2) and not_col.is_valid_at(0):
        passed += 1
        print("  ✅ NOT unknown stays unknown")
    else:
        failed += 1
        print("  ❌ NOT semantics wrong")

    # ── coalesce fills a null from its fallback ─────────────────────────────
    var coalesce_plan = List[ExprNode]()
    coalesce_plan.append(col_ref(1))       # qty, null at row 2
    coalesce_plan.append(literal(-1.0))    # fallback
    coalesce_plan.append(binary(OP_COALESCE, 0, 1))
    var filled = evaluate(coalesce_plan, 2, batch, True)
    if filled.null_count() == 0 and filled.get(2) == -1.0 and filled.get(0) == 1.0:
        passed += 1
        print("  ✅ coalesce substitutes the fallback only where the value is absent")
    else:
        failed += 1
        print("  ❌ coalesce wrong")

    # ── strict mode RAISES where expr.mojo would return 0.0 ─────────────────
    var div = List[ExprNode]()
    div.append(col_ref(0))
    div.append(literal(0.0))
    div.append(binary(OP_DIV, 0, 1))
    var raised = False
    try:
        _ = evaluate(div, 2, batch, True)
    except:
        raised = True
    if raised:
        passed += 1
        print("  ✅ strict mode raises on divide-by-zero (expr.mojo returns 0.0)")
    else:
        failed += 1
        print("  ❌ strict mode masked a divide by zero")

    # ── permissive mode reproduces the frozen 0.0 ───────────────────────────
    var permissive = evaluate(div, 2, batch, False)
    if permissive.get(0) == 0.0 and permissive.is_valid_at(0):
        passed += 1
        print("  ✅ permissive mode reproduces the frozen 0.0 substitution")
    else:
        failed += 1
        print("  ❌ permissive mode diverges from the frozen behaviour")

    # ── unknown rows are reportable, not invisible ──────────────────────────
    if unknown_rows(three_valued, 6, batch, True) == 1:
        passed += 1
        print("  ✅ unknown_rows counts the undecided rows a filter would drop")
    else:
        failed += 1
        print("  ❌ unknown_rows wrong:", unknown_rows(three_valued, 6, batch, True))

    # ── projection pushdown sees which columns a plan needs ─────────────────
    var used = referenced_columns(three_valued)
    if len(used) == 2 and used[0] == 0 and used[1] == 1 and len(
        referenced_columns(plan)
    ) == 1:
        passed += 1
        print("  ✅ referenced_columns is sorted and deduplicated for pushdown")
    else:
        failed += 1
        print("  ❌ column discovery wrong:", len(used))

    # ── an unsupported opcode is identified up front, not mid-scan ───────────
    # Regression: an earlier `uses_frozen_ops` fired on every plan, because
    # OP_LITERAL is opcode 0 and therefore inside the frozen range.
    var with_ln = List[ExprNode]()
    with_ln.append(col_ref(0))
    with_ln.append(unary(8, 0))  # frozen ln — not implemented columnwise
    if (
        first_unsupported_op(plan) == -1        # literals and gt ARE supported
        and first_unsupported_op(with_ln) == 1  # ln is not
        and is_evaluable_op(OP_ADD)
        and not is_evaluable_op(8)
    ):
        passed += 1
        print("  ✅ unsupported opcodes identified by node index, before evaluating")
    else:
        failed += 1
        print("  ❌ support detection wrong:", first_unsupported_op(plan))

    # ── describe renders a plan readably ────────────────────────────────────
    if describe(plan, 2) == "gt(col[0], 15.0)" and op_name(OP_EQ) == "eq":
        passed += 1
        print("  ✅ describe renders gt(col[0], 15.0)")
    else:
        failed += 1
        print("  ❌ describe wrong:", describe(plan, 2))

    print("  [query.ir] Passed:", passed, "Failed:", failed)
