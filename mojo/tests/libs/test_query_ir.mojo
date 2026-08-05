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
    OP_CASE_WHEN,
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
    ternary,
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
        and op_arity(OP_CASE_WHEN) == 3
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

    # ── CASE WHEN: cond known-true takes THEN, even when THEN is null ───────
    # cond = amount > 5 (true every row); then = qty (null at row 2); else = -99.
    # A null THEN must stay null — the branch is passed through verbatim, not
    # forced valid.
    var case_then_null = List[ExprNode]()
    case_then_null.append(col_ref(0))                    # 0 amount
    case_then_null.append(literal(5.0))                  # 1
    case_then_null.append(binary(OP_GT, 0, 1))            # 2 cond: amount>5 (always true)
    case_then_null.append(col_ref(1))                     # 3 then: qty (null at row 2)
    case_then_null.append(literal(-99.0))                 # 4 else
    case_then_null.append(ternary(OP_CASE_WHEN, 2, 3, 4)) # 5
    var ctn = evaluate(case_then_null, 5, batch, True)
    if (
        ctn.get(0) == 1.0
        and ctn.get(1) == 2.0
        and not ctn.is_valid_at(2)  # then was null -> result stays null
        and ctn.get(3) == 4.0
    ):
        passed += 1
        print("  ✅ CASE WHEN: known-true cond takes THEN; a null THEN stays null")
    else:
        failed += 1
        print("  ❌ CASE WHEN true/null-then wrong:", ctn.is_valid_at(2))

    # ── CASE WHEN: cond known-false takes ELSE, even when ELSE is null ──────
    # cond = amount > 1000 (always false); then = 77; else = qty (null at row 2).
    var case_else_null = List[ExprNode]()
    case_else_null.append(col_ref(0))                     # 0 amount
    case_else_null.append(literal(1000.0))                # 1
    case_else_null.append(binary(OP_GT, 0, 1))             # 2 cond: amount>1000 (always false)
    case_else_null.append(literal(77.0))                   # 3 then
    case_else_null.append(col_ref(1))                      # 4 else: qty (null at row 2)
    case_else_null.append(ternary(OP_CASE_WHEN, 2, 3, 4))  # 5
    var cen = evaluate(case_else_null, 5, batch, True)
    if (
        cen.get(0) == 1.0
        and cen.get(1) == 2.0
        and not cen.is_valid_at(2)  # else was null -> result stays null
        and cen.get(3) == 4.0
    ):
        passed += 1
        print("  ✅ CASE WHEN: known-false cond takes ELSE; a null ELSE stays null")
    else:
        failed += 1
        print("  ❌ CASE WHEN false/null-else wrong:", cen.is_valid_at(2))

    # ── CASE WHEN: cond known-false with a valid ELSE, and known-true with a
    # valid THEN, both over literals (no nulls involved at all) ─────────────
    var case_literal = List[ExprNode]()
    case_literal.append(col_ref(0))                        # 0 amount
    case_literal.append(literal(25.0))                     # 1
    case_literal.append(binary(OP_LT, 0, 1))                # 2 cond: amount<25 -> T,T,F,F
    case_literal.append(literal(1.0))                       # 3 then
    case_literal.append(literal(0.0))                       # 4 else
    case_literal.append(ternary(OP_CASE_WHEN, 2, 3, 4))      # 5
    var clit = evaluate(case_literal, 5, batch, True)
    if (
        clit.get(0) == 1.0
        and clit.get(1) == 1.0
        and clit.get(2) == 0.0
        and clit.get(3) == 0.0
        and clit.null_count() == 0
    ):
        passed += 1
        print("  ✅ CASE WHEN: known-true takes THEN and known-false takes ELSE, over literals")
    else:
        failed += 1
        print("  ❌ CASE WHEN literal true/false wrong")

    # ── CASE WHEN: an UNKNOWN cond falls to ELSE, matching SQL — it does NOT
    # propagate null the way arithmetic/comparison would. This is the case most
    # likely to be wrong from a naive port of AND/OR's three-valued pattern. ──
    # cond = qty > 0: true at rows 0,1,3 (qty=1,2,4), UNKNOWN at row 2 (qty null).
    var case_unknown = List[ExprNode]()
    case_unknown.append(col_ref(1))                         # 0 qty
    case_unknown.append(literal(0.0))                       # 1
    case_unknown.append(binary(OP_GT, 0, 1))                 # 2 cond: qty>0 -> T,T,unknown,T
    case_unknown.append(literal(111.0))                      # 3 then
    case_unknown.append(literal(222.0))                       # 4 else
    case_unknown.append(ternary(OP_CASE_WHEN, 2, 3, 4))       # 5
    var cu = evaluate(case_unknown, 5, batch, True)
    if (
        cu.get(0) == 111.0
        and cu.get(1) == 111.0
        and cu.is_valid_at(2)   # NOT null: falls through to ELSE, decided
        and cu.get(2) == 222.0  # unknown cond -> ELSE, never NULL
        and cu.get(3) == 111.0
        and cu.null_count() == 0
    ):
        passed += 1
        print("  ✅ CASE WHEN: an unknown cond falls to ELSE (never propagates null)")
    else:
        failed += 1
        print("  ❌ CASE WHEN unknown-cond wrong:", cu.is_valid_at(2), cu.get(2))

    # ── chained 3-branch CASE WHEN c1 THEN v1 WHEN c2 THEN v2 ELSE v3 END ────
    # Built as CASE(c1, v1, CASE(c2, v2, v3)) — the same "chain of nodes" shape
    # this IR already uses for a & b & c, not a new N-ary node.
    # c1: amount<15 (only row 0); c2: amount<35 (rows 0,1,2, but row 0 is already
    # decided by c1) -> row0=v1, row1=v2, row2=v2, row3=v3.
    var chained = List[ExprNode]()
    chained.append(col_ref(0))                              # 0 amount
    chained.append(literal(15.0))                            # 1
    chained.append(binary(OP_LT, 0, 1))                       # 2 c1: amount<15
    chained.append(literal(100.0))                             # 3 v1
    chained.append(literal(35.0))                               # 4
    chained.append(binary(OP_LT, 0, 4))                          # 5 c2: amount<35
    chained.append(literal(200.0))                                # 6 v2
    chained.append(literal(300.0))                                 # 7 v3 (final else)
    chained.append(ternary(OP_CASE_WHEN, 5, 6, 7))                  # 8 CASE(c2,v2,v3)
    chained.append(ternary(OP_CASE_WHEN, 2, 3, 8))                   # 9 CASE(c1,v1,inner)
    if len(validation_error(chained, 9, 2)) > 0:
        failed += 1
        print("  ❌ chained CASE WHEN failed validation:", validation_error(chained, 9, 2))
    else:
        var chain_col = evaluate(chained, 9, batch, True)
        if (
            chain_col.get(0) == 100.0
            and chain_col.get(1) == 200.0
            and chain_col.get(2) == 200.0
            and chain_col.get(3) == 300.0
            and chain_col.null_count() == 0
        ):
            passed += 1
            print("  ✅ chained 3-branch CASE WHEN resolves each row to the right branch")
        else:
            failed += 1
            print(
                "  ❌ chained CASE WHEN wrong:",
                chain_col.get(0), chain_col.get(1), chain_col.get(2), chain_col.get(3),
            )

    # ── a CASE WHEN missing its third child (else branch) is rejected ───────
    var case_no_else = List[ExprNode]()
    case_no_else.append(literal(1.0))
    case_no_else.append(literal(2.0))
    case_no_else.append(binary(OP_CASE_WHEN, 0, 1))  # extra defaults to -1
    if len(validation_error(case_no_else, 2, 0)) > 0:
        passed += 1
        print("  ✅ CASE WHEN without a third child is rejected by validation")
    else:
        failed += 1
        print("  ❌ CASE WHEN missing else branch was accepted")

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
