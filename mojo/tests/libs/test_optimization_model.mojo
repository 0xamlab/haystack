"""test_optimization_model.mojo — known-value tests for the general optimization model.

Hand-written. Every number below was computed by hand and is asserted exactly wherever the
arithmetic is exact in binary floating point (small integers and dyadic fractions); a
tolerance appears only where a division or a transcendental genuinely rounds.

The assertions target the failure this module exists to remove. An objective reaching a
frozen optimizer as an integer `func_id` gets `0.0` from an unrecognised id, and the
frozen scalar evaluator `expr.eval_expr` masks every numeric failure into a plausible
number. So a large share of the suite is DIFFERENTIAL against `expr.eval_expr`, the frozen
kernel that solves the same problem the other way — recursively, top-down, with masking —
and each such assertion checks two things at once: that this module agrees with the frozen
kernel value-for-value wherever the frozen kernel is not masking, and that where it *is*
masking (x/0 = 0.0, ln(-1) = -690.776, sqrt(-4) = 0.0, (-2)^0.5 = 0.0, exp(1000) =
exp(709), clip(5, 3, 1) = 1.0, a var_ref past the end of the point = 0.0) the frozen kernel
really does hand back that number while this module reports absence.

The rest covers the validator: one rejection per code, a forward reference (the only way a
cycle could be spelled) rejected, a variable index past the end of the point rejected
rather than crashing the process, crossed bounds, an integer range holding no integer, a
`con_ptr` that does not describe the constraint arena it came with, and the wrapping
64-bit multiply that `sparse_numerics.csr.dims_fit` exists to catch. The arena pack/unpack
pair is asserted field-for-field, including `extra`, which only a three-child opcode uses
and which a five-column transposition would silently drop.
"""
from expr import eval_expr
from optimization.model import (
    MODEL_ERR_BINARY_BOUNDS,
    MODEL_ERR_BOUNDS_CROSSED,
    MODEL_ERR_CONSTRAINT_PTR,
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_DIV_BY_ZERO,
    MODEL_ERR_DOMAIN,
    MODEL_ERR_EMPTY_EXPRESSION,
    MODEL_ERR_EXPR_ROOT,
    MODEL_ERR_EXPR_STRUCTURE,
    MODEL_ERR_INTEGER_BOUNDS,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_ERR_MISSING_THIRD_CHILD,
    MODEL_ERR_NON_FINITE_BOUND,
    MODEL_ERR_NON_FINITE_LITERAL,
    MODEL_ERR_NON_FINITE_POINT,
    MODEL_ERR_NON_FINITE_RHS,
    MODEL_ERR_NON_FINITE_VALUE,
    MODEL_ERR_OVERFLOW,
    MODEL_ERR_POINT_LENGTH,
    MODEL_ERR_POLICY,
    MODEL_ERR_SENSE,
    MODEL_ERR_UNSUPPORTED_OP,
    MODEL_ERR_VAR_FLAGS,
    MODEL_ERR_VAR_INDEX,
    MODEL_ERR_VAR_KIND,
    MODEL_ERR_WARM_START,
    MODEL_OK,
    MODEL_VIOLATION_ABSENT,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    VAR_BINARY,
    VAR_CONTINUOUS,
    VAR_FLAG_BOXED,
    VAR_INTEGER,
    ModelFlat,
    OptConstraint,
    OptVar,
    arena_from_flat,
    arena_roundtrip,
    arena_to_flat,
    check_expr,
    check_variables,
    default_policy,
    evaluate_expr,
    evaluate_model,
    evaluate_objective,
    expr_evaluate_flat,
    expr_validate_flat,
    integer_in_interval,
    is_model_op,
    linear_arena,
    linear_model_flat,
    make_constraint,
    make_model,
    minimization_value,
    model_evaluate,
    model_from_flat,
    model_objective,
    model_op_arity,
    model_status_name,
    model_to_flat,
    model_validate,
    opt_policy_new,
    opt_var,
    opt_var_binary,
    opt_var_free,
    opt_var_warm,
    project_point,
    project_point_flat,
    sense_violation,
    validate_model,
    variables_validate_flat,
    warm_start_point,
)
from types import ExprNode


# ── helpers ───────────────────────────────────────────────────────────────────


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d <= tol


fn _same_ints(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _same_floats(a: List[Float64], b: List[Float64]) -> Bool:
    """Exact equality — every value compared with this helper is a small integer."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _lf5() -> List[Float64]:
    """The generated A-Z suite's sample list: five copies of 0.5."""
    return _floats(0.5, 0.5, 0.5, 0.5, 0.5)


fn _li5() -> List[Int]:
    """The generated A-Z suite's sample list: five copies of 5."""
    return _ints(5, 5, 5, 5, 5)


# ── the hand-verified model ───────────────────────────────────────────────────
# minimize  f(x) = x0^2 + 3*x1
#   c0: x0 + x1 <= 6
#   c1: x0 - x1 == -3
#   c2: x1       >= 2
#   0 <= x0 <= 10,  0 <= x1 <= 10
#
# At x = (2, 5):  f = 4 + 15 = 19;  c0 = 7 (violates by 1);  c1 = -3 (exact);  c2 = 5 (ok).
# At x = (1, 4):  f = 1 + 12 = 13;  c0 = 5 (ok);             c1 = -3 (exact);  c2 = 4 (ok).
# Every value is a small integer, so all of it is exact in binary floating point.


fn _objective_nodes() -> List[ExprNode]:
    var nodes = List[ExprNode]()
    nodes.append(ExprNode(1, 0.0, 0, -1, -1, -1))   # 0: x0
    nodes.append(ExprNode(4, 0.0, -1, 0, 0, -1))    # 1: x0 * x0
    nodes.append(ExprNode(0, 3.0, -1, -1, -1, -1))  # 2: 3
    nodes.append(ExprNode(1, 0.0, 1, -1, -1, -1))   # 3: x1
    nodes.append(ExprNode(4, 0.0, -1, 2, 3, -1))    # 4: 3 * x1
    nodes.append(ExprNode(2, 0.0, -1, 1, 4, -1))    # 5: sum
    return nodes^


fn _sum_nodes() -> List[ExprNode]:
    var nodes = List[ExprNode]()
    nodes.append(ExprNode(1, 0.0, 0, -1, -1, -1))
    nodes.append(ExprNode(1, 0.0, 1, -1, -1, -1))
    nodes.append(ExprNode(2, 0.0, -1, 0, 1, -1))
    return nodes^


fn _diff_nodes() -> List[ExprNode]:
    var nodes = List[ExprNode]()
    nodes.append(ExprNode(1, 0.0, 0, -1, -1, -1))
    nodes.append(ExprNode(1, 0.0, 1, -1, -1, -1))
    nodes.append(ExprNode(3, 0.0, -1, 0, 1, -1))
    return nodes^


fn _x1_nodes() -> List[ExprNode]:
    var nodes = List[ExprNode]()
    nodes.append(ExprNode(1, 0.0, 1, -1, -1, -1))
    return nodes^


fn _model_vars() -> List[OptVar]:
    var variables = List[OptVar]()
    variables.append(opt_var("x0", 0.0, 10.0, VAR_CONTINUOUS))
    variables.append(opt_var("x1", 0.0, 10.0, VAR_CONTINUOUS))
    return variables^


fn _model_constraints() -> List[OptConstraint]:
    var cons = List[OptConstraint]()
    cons.append(make_constraint(_sum_nodes(), 2, SENSE_LE, 6.0, "c0"))
    cons.append(make_constraint(_diff_nodes(), 2, SENSE_EQ, -3.0, "c1"))
    cons.append(make_constraint(_x1_nodes(), 0, SENSE_GE, 2.0, "c2"))
    return cons^


fn _one_var(lower: Float64, upper: Float64, kind: Int) -> List[OptVar]:
    var variables = List[OptVar]()
    variables.append(opt_var("v", lower, upper, kind))
    return variables^


fn _lift_one(v: OptVar) -> List[OptVar]:
    var variables = List[OptVar]()
    variables.append(v.copy())
    return variables^


fn _unbounded_integers(n: Int) -> List[OptVar]:
    """`n` integer variables with no bound on either side, so a projection only snaps."""
    var variables = List[OptVar]()
    for i in range(n):
        variables.append(OptVar("z" + String(i), 0.0, 0.0, VAR_INTEGER, False, False, False, 0.0))
    return variables^


fn _flat_with_ptr(flat: ModelFlat, ptr: List[Int]) -> ModelFlat:
    """The same wire model with a different `con_ptr`, for the pointer-defect cases."""
    return ModelFlat(
        flat.var_lower.copy(),
        flat.var_upper.copy(),
        flat.var_kind.copy(),
        flat.var_flags.copy(),
        flat.var_start.copy(),
        flat.maximize,
        flat.obj_root,
        flat.obj_ops.copy(),
        flat.obj_values.copy(),
        flat.obj_var_idx.copy(),
        flat.obj_lefts.copy(),
        flat.obj_rights.copy(),
        flat.obj_extras.copy(),
        ptr.copy(),
        flat.con_roots.copy(),
        flat.con_senses.copy(),
        flat.con_rhs.copy(),
        flat.con_ops.copy(),
        flat.con_values.copy(),
        flat.con_var_idx.copy(),
        flat.con_lefts.copy(),
        flat.con_rights.copy(),
        flat.con_extras.copy(),
        flat.max_iterations,
        flat.max_time_ms,
        flat.feasibility_tol,
        flat.optimality_tol,
        flat.integrality_tol,
    )


fn main() raises:
    var passed = 0
    var failed = 0

    var infinity = 1.0e308 * 10.0
    var not_a_number = infinity - infinity

    # ── the objective evaluates to the hand-computed number, and so does the frozen
    #    evaluator on the same arena ───────────────────────────────────────────────
    var obj = _objective_nodes()
    var at_25 = _floats(2.0, 5.0)
    var at_14 = _floats(1.0, 4.0)
    var v25 = evaluate_expr(obj, 5, at_25, 2)
    var v14 = evaluate_expr(obj, 5, at_14, 2)
    var frozen_25 = eval_expr(obj, 5, at_25)
    if (
        v25.status == MODEL_OK
        and v25.has_value
        and v25.value == 19.0
        and v25.nodes_evaluated == 6
        and v14.value == 13.0
        and frozen_25 == 19.0
    ):
        passed += 1
        print("  ✅ x0^2 + 3*x1 is 19 at (2,5) and 13 at (1,4); frozen eval_expr agrees")
    else:
        failed += 1
        print("  ❌ objective value:", v25.value, v14.value, frozen_25, v25.status)

    # ── a var_ref past the end of the point is REJECTED, where the frozen evaluator
    #    returns 0.0 and optimises a different function ───────────────────────────
    var past_end = List[ExprNode]()
    past_end.append(ExprNode(1, 0.0, 7, -1, -1, -1))
    var past = evaluate_expr(past_end, 0, _floats(1.0), 1)
    var frozen_past = eval_expr(past_end, 0, _floats(1.0))
    if (
        past.status == MODEL_ERR_VAR_INDEX
        and not past.has_value
        and past.node_index == 0
        and frozen_past == 0.0
    ):
        passed += 1
        print("  ✅ variable 7 of a 1-variable point is rejected; frozen returns 0.0")
    else:
        failed += 1
        print("  ❌ out-of-range var_ref:", past.status, past.value, frozen_past)

    # ── the same reference is rejected by the flat driver with the A-Z sample args,
    #    which is the call that would otherwise crash the worker ──────────────────
    var hostile_expr = expr_evaluate_flat(
        _li5(), _lf5(), _li5(), _li5(), _li5(), _li5(), 5, _lf5()
    )
    var hostile_vars = variables_validate_flat(
        _lf5(), _lf5(), _li5(), _li5(), _lf5(), 0.5
    )
    var hostile_point = project_point_flat(
        _lf5(), _lf5(), _lf5(), _li5(), _li5(), _lf5(), 0.5
    )
    if (
        hostile_expr.status != MODEL_OK
        and not hostile_expr.has_value
        and hostile_vars.status == MODEL_ERR_VAR_KIND
        and hostile_point.status == MODEL_ERR_VAR_KIND
        and len(hostile_point.x) == 0
    ):
        passed += 1
        print("  ✅ the generated-suite argument pattern is refused, not indexed")
    else:
        failed += 1
        print(
            "  ❌ hostile sample args:",
            hostile_expr.status,
            hostile_vars.status,
            hostile_point.status,
        )

    # ── the remaining flat drivers refuse the same pattern, and `linear_model_flat`
    #    refuses `dims_fit(5, 5, 5)` — a 5x5 matrix does not fit five values ──────
    var hostile_check = expr_validate_flat(
        _li5(), _lf5(), _li5(), _li5(), _li5(), _li5(), 5, 5
    )
    var hostile_arena = arena_roundtrip(
        _li5(), _lf5(), _li5(), _li5(), _li5(), _li5(), 5
    )
    var hostile_lp = linear_model_flat(
        _lf5(), _lf5(), 5, 5, _li5(), _lf5(), _lf5(), _lf5(), _li5(), _li5(), True
    )
    if (
        hostile_check.status != MODEL_OK
        and hostile_arena.status == MODEL_OK
        and hostile_arena.n_nodes == 5
        and hostile_lp.status == MODEL_ERR_DENSE_SHAPE
    ):
        passed += 1
        print("  ✅ validate/roundtrip/LP drivers all survive the sample argument pattern")
    else:
        failed += 1
        print(
            "  ❌ hostile drivers:",
            hostile_check.status,
            hostile_arena.status,
            hostile_lp.status,
        )

    # ── a forward reference is the only way a cycle could be spelled, and it is
    #    rejected by query.ir before anything evaluates ───────────────────────────
    var forward = List[ExprNode]()
    forward.append(ExprNode(2, 0.0, -1, 1, 1, -1))
    forward.append(ExprNode(0, 2.0, -1, -1, -1, -1))
    var self_ref = List[ExprNode]()
    self_ref.append(ExprNode(6, 0.0, -1, 0, -1, -1))
    var fwd = check_expr(forward, 0, 0)
    var slf = check_expr(self_ref, 0, 0)
    if (
        fwd.status == MODEL_ERR_EXPR_STRUCTURE
        and slf.status == MODEL_ERR_EXPR_STRUCTURE
        and evaluate_expr(forward, 0, List[Float64](), 0).status == MODEL_ERR_EXPR_STRUCTURE
    ):
        passed += 1
        print("  ✅ a forward reference and a self reference are both refused")
    else:
        failed += 1
        print("  ❌ cycle attempt accepted:", fwd.status, slf.status, fwd.message)

    # ── division by zero: a status here, 0.0 in the frozen kernel ───────────────
    var div_nodes = List[ExprNode]()
    div_nodes.append(ExprNode(0, 1.0, -1, -1, -1, -1))
    div_nodes.append(ExprNode(1, 0.0, 0, -1, -1, -1))
    div_nodes.append(ExprNode(5, 0.0, -1, 0, 1, -1))
    var zero_point = _floats(0.0)
    var divided = evaluate_expr(div_nodes, 2, zero_point, 1)
    var frozen_div = eval_expr(div_nodes, 2, zero_point)
    if (
        divided.status == MODEL_ERR_DIV_BY_ZERO
        and not divided.has_value
        and divided.value == 0.0
        and divided.node_index == 2
        and frozen_div == 0.0
    ):
        passed += 1
        print("  ✅ 1/0 is absent here and 0.0 in expr.eval_expr — the same 0.0")
    else:
        failed += 1
        print("  ❌ divide by zero:", divided.status, divided.value, frozen_div)

    # ── ln of a non-positive argument: the frozen kernel returns ln(1e-300) ─────
    var ln_nodes = List[ExprNode]()
    ln_nodes.append(ExprNode(1, 0.0, 0, -1, -1, -1))
    ln_nodes.append(ExprNode(8, 0.0, -1, 0, -1, -1))
    var minus_one = _floats(-1.0)
    var logged = evaluate_expr(ln_nodes, 1, minus_one, 1)
    var frozen_log = eval_expr(ln_nodes, 1, minus_one)
    if (
        logged.status == MODEL_ERR_DOMAIN
        and not logged.has_value
        and _close(frozen_log, -690.7755278982137, 1e-9)
    ):
        passed += 1
        print("  ✅ ln(-1) has no value here; the frozen kernel answers -690.7755")
    else:
        failed += 1
        print("  ❌ ln domain:", logged.status, frozen_log)

    # ── sqrt of a negative, a negative base to a fractional power, and mod 0 ────
    var sqrt_nodes = List[ExprNode]()
    sqrt_nodes.append(ExprNode(0, -4.0, -1, -1, -1, -1))
    sqrt_nodes.append(ExprNode(12, 0.0, -1, 0, -1, -1))
    var pow_nodes = List[ExprNode]()
    pow_nodes.append(ExprNode(0, -2.0, -1, -1, -1, -1))
    pow_nodes.append(ExprNode(0, 0.5, -1, -1, -1, -1))
    pow_nodes.append(ExprNode(7, 0.0, -1, 0, 1, -1))
    var mod_nodes = List[ExprNode]()
    mod_nodes.append(ExprNode(0, 7.0, -1, -1, -1, -1))
    mod_nodes.append(ExprNode(0, 0.0, -1, -1, -1, -1))
    mod_nodes.append(ExprNode(21, 0.0, -1, 0, 1, -1))
    var no_point = List[Float64]()
    var rooted = evaluate_expr(sqrt_nodes, 1, no_point, 0)
    var powered = evaluate_expr(pow_nodes, 2, no_point, 0)
    var modded = evaluate_expr(mod_nodes, 2, no_point, 0)
    if (
        rooted.status == MODEL_ERR_DOMAIN
        and powered.status == MODEL_ERR_DOMAIN
        and modded.status == MODEL_ERR_DIV_BY_ZERO
        and eval_expr(sqrt_nodes, 1, no_point) == 0.0
        and eval_expr(pow_nodes, 2, no_point) == 0.0
        and eval_expr(mod_nodes, 2, no_point) == 0.0
    ):
        passed += 1
        print("  ✅ sqrt(-4), (-2)^0.5 and 7 % 0 are absent; all three are 0.0 frozen")
    else:
        failed += 1
        print("  ❌ domain trio:", rooted.status, powered.status, modded.status)

    # ── exp overflow: the frozen kernel clamps to exp(709), a finite objective ──
    var exp_nodes = List[ExprNode]()
    exp_nodes.append(ExprNode(0, 1000.0, -1, -1, -1, -1))
    exp_nodes.append(ExprNode(11, 0.0, -1, 0, -1, -1))
    var exploded = evaluate_expr(exp_nodes, 1, no_point, 0)
    var frozen_exp = eval_expr(exp_nodes, 1, no_point)
    if (
        exploded.status == MODEL_ERR_OVERFLOW
        and not exploded.has_value
        and frozen_exp > 1.0e307
        and frozen_exp < infinity
    ):
        passed += 1
        print("  ✅ exp(1000) overflows here; the frozen kernel returns exp(709)")
    else:
        failed += 1
        print("  ❌ exp overflow:", exploded.status, frozen_exp)

    # ── arithmetic that overflows to infinity is a status, not an infinity ──────
    var big_nodes = List[ExprNode]()
    big_nodes.append(ExprNode(0, 1.0e300, -1, -1, -1, -1))
    big_nodes.append(ExprNode(0, 1.0e300, -1, -1, -1, -1))
    big_nodes.append(ExprNode(4, 0.0, -1, 0, 1, -1))
    var overflowed = evaluate_expr(big_nodes, 2, no_point, 0)
    var frozen_big = eval_expr(big_nodes, 2, no_point)
    if (
        overflowed.status == MODEL_ERR_NON_FINITE_VALUE
        and overflowed.node_index == 2
        and frozen_big == infinity
    ):
        passed += 1
        print("  ✅ 1e300 * 1e300 is reported non-finite; the frozen kernel returns inf")
    else:
        failed += 1
        print("  ❌ overflow to inf:", overflowed.status, frozen_big)

    # ── clip with lo > hi denotes an empty interval; the frozen kernel returns hi ─
    var clip_nodes = List[ExprNode]()
    clip_nodes.append(ExprNode(0, 5.0, -1, -1, -1, -1))
    clip_nodes.append(ExprNode(0, 3.0, -1, -1, -1, -1))
    clip_nodes.append(ExprNode(0, 1.0, -1, -1, -1, -1))
    clip_nodes.append(ExprNode(19, 0.0, -1, 0, 1, 2))
    var clipped = evaluate_expr(clip_nodes, 3, no_point, 0)
    var frozen_clip = eval_expr(clip_nodes, 3, no_point)
    var no_third = List[ExprNode]()
    no_third.append(ExprNode(0, 5.0, -1, -1, -1, -1))
    no_third.append(ExprNode(0, 1.0, -1, -1, -1, -1))
    no_third.append(ExprNode(19, 0.0, -1, 0, 1, -1))
    var third = check_expr(no_third, 2, 0)
    if (
        clipped.status == MODEL_ERR_DOMAIN
        and frozen_clip == 1.0
        and third.status == MODEL_ERR_MISSING_THIRD_CHILD
        and third.node_index == 2
    ):
        passed += 1
        print("  ✅ clip(5, 3, 1) is empty here and 1.0 frozen; a missing hi is refused")
    else:
        failed += 1
        print("  ❌ clip:", clipped.status, frozen_clip, third.status)

    # ── a well formed clip evaluates, and matches the frozen kernel ─────────────
    var good_clip = List[ExprNode]()
    good_clip.append(ExprNode(1, 0.0, 0, -1, -1, -1))
    good_clip.append(ExprNode(0, -2.0, -1, -1, -1, -1))
    good_clip.append(ExprNode(0, 3.0, -1, -1, -1, -1))
    good_clip.append(ExprNode(19, 0.0, -1, 0, 1, 2))
    var high = _floats(9.0)
    var clip_high = evaluate_expr(good_clip, 3, high, 1)
    var clip_low = evaluate_expr(good_clip, 3, _floats(-8.0), 1)
    if (
        clip_high.value == 3.0
        and clip_low.value == -2.0
        and eval_expr(good_clip, 3, high) == 3.0
    ):
        passed += 1
        print("  ✅ clip(x, -2, 3) is 3 at x=9 and -2 at x=-8, frozen kernel agreeing")
    else:
        failed += 1
        print("  ❌ clip values:", clip_high.value, clip_low.value)

    # ── ifgt0 is LAZY: the untaken branch is never evaluated, so a division by zero
    #    hiding in it is not a failure ───────────────────────────────────────────
    var lazy = List[ExprNode]()
    lazy.append(ExprNode(0, 1.0, -1, -1, -1, -1))    # 0: condition 1 > 0
    lazy.append(ExprNode(0, 7.0, -1, -1, -1, -1))    # 1: taken branch
    lazy.append(ExprNode(0, 1.0, -1, -1, -1, -1))    # 2: numerator
    lazy.append(ExprNode(1, 0.0, 0, -1, -1, -1))     # 3: x0, which is 0
    lazy.append(ExprNode(5, 0.0, -1, 2, 3, -1))      # 4: 1 / x0
    lazy.append(ExprNode(20, 0.0, -1, 0, 1, 4))      # 5: ifgt0
    var taken = evaluate_expr(lazy, 5, zero_point, 1)
    var frozen_taken = eval_expr(lazy, 5, zero_point)
    var flipped = List[ExprNode]()
    for i in range(len(lazy)):
        flipped.append(lazy[i].copy())
    flipped[0] = ExprNode(0, -1.0, -1, -1, -1, -1)
    var not_taken = evaluate_expr(flipped, 5, zero_point, 1)
    if (
        taken.status == MODEL_OK
        and taken.value == 7.0
        and taken.nodes_evaluated == 3
        and frozen_taken == 7.0
        and not_taken.status == MODEL_ERR_DIV_BY_ZERO
        and not_taken.node_index == 4
    ):
        passed += 1
        print("  ✅ ifgt0 evaluates 3 of 6 nodes; the dead 1/0 branch costs nothing")
    else:
        failed += 1
        print(
            "  ❌ ifgt0 laziness:",
            taken.status,
            taken.value,
            taken.nodes_evaluated,
            not_taken.status,
        )

    # ── opcodes 22-38 are DELEGATED to the frozen evaluator, so they agree bit for
    #    bit, and their clamped domains become statuses ──────────────────────────
    var erf_nodes = List[ExprNode]()
    erf_nodes.append(ExprNode(0, 0.5, -1, -1, -1, -1))
    erf_nodes.append(ExprNode(29, 0.0, -1, 0, -1, -1))
    var fact_nodes = List[ExprNode]()
    fact_nodes.append(ExprNode(0, 5.0, -1, -1, -1, -1))
    fact_nodes.append(ExprNode(32, 0.0, -1, 0, -1, -1))
    var hypot_nodes = List[ExprNode]()
    hypot_nodes.append(ExprNode(0, 3.0, -1, -1, -1, -1))
    hypot_nodes.append(ExprNode(0, 4.0, -1, -1, -1, -1))
    hypot_nodes.append(ExprNode(36, 0.0, -1, 0, 1, -1))
    var comb_nodes = List[ExprNode]()
    comb_nodes.append(ExprNode(0, 5.0, -1, -1, -1, -1))
    comb_nodes.append(ExprNode(0, 2.0, -1, -1, -1, -1))
    comb_nodes.append(ExprNode(33, 0.0, -1, 0, 1, -1))
    var erf_here = evaluate_expr(erf_nodes, 1, no_point, 0)
    var fact_here = evaluate_expr(fact_nodes, 1, no_point, 0)
    var hypot_here = evaluate_expr(hypot_nodes, 2, no_point, 0)
    var comb_here = evaluate_expr(comb_nodes, 2, no_point, 0)
    if (
        erf_here.status == MODEL_OK
        and erf_here.value == eval_expr(erf_nodes, 1, no_point)
        and fact_here.value == 120.0
        and hypot_here.value == 5.0
        and comb_here.value == 10.0
    ):
        passed += 1
        print("  ✅ erf matches the frozen kernel exactly; 5! = 120, hypot = 5, C(5,2) = 10")
    else:
        failed += 1
        print(
            "  ❌ delegated ops:",
            erf_here.value,
            fact_here.value,
            hypot_here.value,
            comb_here.value,
        )

    var bad_fact = List[ExprNode]()
    bad_fact.append(ExprNode(0, -1.0, -1, -1, -1, -1))
    bad_fact.append(ExprNode(32, 0.0, -1, 0, -1, -1))
    var huge_fact = List[ExprNode]()
    huge_fact.append(ExprNode(0, 200.0, -1, -1, -1, -1))
    huge_fact.append(ExprNode(32, 0.0, -1, 0, -1, -1))
    var bad_asin = List[ExprNode]()
    bad_asin.append(ExprNode(0, 2.0, -1, -1, -1, -1))
    bad_asin.append(ExprNode(25, 0.0, -1, 0, -1, -1))
    var neg_fact = evaluate_expr(bad_fact, 1, no_point, 0)
    var big_fact = evaluate_expr(huge_fact, 1, no_point, 0)
    var wide_asin = evaluate_expr(bad_asin, 1, no_point, 0)
    if (
        neg_fact.status == MODEL_ERR_DOMAIN
        and big_fact.status == MODEL_ERR_OVERFLOW
        and wide_asin.status == MODEL_ERR_DOMAIN
        and eval_expr(bad_fact, 1, no_point) == 0.0
        and eval_expr(huge_fact, 1, no_point) == 1.0e308
        and _close(eval_expr(bad_asin, 1, no_point), 1.5707963267948966, 1e-12)
    ):
        passed += 1
        print("  ✅ (-1)!, 200! and asin(2) are refused; frozen gives 0.0, 1e308, pi/2")
    else:
        failed += 1
        print(
            "  ❌ delegated domains:",
            neg_fact.status,
            big_fact.status,
            wide_asin.status,
        )

    # ── an opcode this evaluator cannot run, and a query opcode, are separate
    #    rejections ──────────────────────────────────────────────────────────────
    var comparison = List[ExprNode]()
    comparison.append(ExprNode(1, 0.0, 0, -1, -1, -1))
    comparison.append(ExprNode(0, 1.0, -1, -1, -1, -1))
    comparison.append(ExprNode(100, 0.0, -1, 0, 1, -1))
    var column = List[ExprNode]()
    column.append(ExprNode(130, 0.0, 0, -1, -1, -1))
    var cmp_check = check_expr(comparison, 2, 1)
    var col_check = check_expr(column, 0, 1)
    if (
        cmp_check.status == MODEL_ERR_UNSUPPORTED_OP
        and cmp_check.node_index == 2
        and col_check.status == MODEL_ERR_EXPR_STRUCTURE
        and not is_model_op(100)
        and not is_model_op(130)
        and model_op_arity(19) == 3
        and model_op_arity(33) == 2
        and model_op_arity(36) == 2
        and model_op_arity(29) == 1
        and model_op_arity(39) == -1
    ):
        passed += 1
        print("  ✅ a comparison opcode and a col_ref are both refused, for their own reasons")
    else:
        failed += 1
        print("  ❌ opcode gate:", cmp_check.status, col_check.status)

    # ── a non-finite literal and a non-finite point are refused before the walk ──
    var nan_literal = List[ExprNode]()
    nan_literal.append(ExprNode(0, not_a_number, -1, -1, -1, -1))
    var inf_literal = List[ExprNode]()
    inf_literal.append(ExprNode(0, infinity, -1, -1, -1, -1))
    var nan_check = check_expr(nan_literal, 0, 0)
    var inf_check = check_expr(inf_literal, 0, 0)
    var bad_point = evaluate_expr(_x1_nodes(), 0, _floats(1.0, not_a_number), 2)
    var empty_expr = check_expr(List[ExprNode](), 0, 2)
    var bad_root = check_expr(obj, 9, 2)
    if (
        nan_check.status == MODEL_ERR_NON_FINITE_LITERAL
        and inf_check.status == MODEL_ERR_NON_FINITE_LITERAL
        and bad_point.status == MODEL_ERR_NON_FINITE_POINT
        and empty_expr.status == MODEL_ERR_EMPTY_EXPRESSION
        and bad_root.status == MODEL_ERR_EXPR_ROOT
    ):
        passed += 1
        print("  ✅ NaN and inf literals, a NaN point, an empty arena and a bad root refused")
    else:
        failed += 1
        print(
            "  ❌ finiteness gate:",
            nan_check.status,
            inf_check.status,
            bad_point.status,
            empty_expr.status,
            bad_root.status,
        )

    # ── the arena pack/unpack pair preserves every field, `extra` included ──────
    var packed = arena_to_flat(lazy, 5)
    var unpacked = arena_from_flat(
        packed.ops, packed.values, packed.var_idx, packed.lefts, packed.rights,
        packed.extras,
    )
    var identical = len(unpacked) == len(lazy)
    if identical:
        for i in range(len(lazy)):
            if (
                unpacked[i].op != lazy[i].op
                or unpacked[i].fval != lazy[i].fval
                or unpacked[i].var_idx != lazy[i].var_idx
                or unpacked[i].left != lazy[i].left
                or unpacked[i].right != lazy[i].right
                or unpacked[i].extra != lazy[i].extra
            ):
                identical = False
    var round_trip = arena_roundtrip(
        packed.ops, packed.values, packed.var_idx, packed.lefts, packed.rights,
        packed.extras, 5,
    )
    if (
        identical
        and round_trip.status == MODEL_OK
        and round_trip.n_nodes == 6
        and round_trip.root == 5
        and _same_ints(round_trip.ops, _ints(0, 0, 0, 1, 5, 20))
        and _same_floats(round_trip.values, _floats(1.0, 7.0, 1.0, 0.0, 0.0, 0.0))
        and _same_ints(round_trip.var_idx, _ints(-1, -1, -1, 0, -1, -1))
        and _same_ints(round_trip.lefts, _ints(-1, -1, -1, -1, 2, 0))
        and _same_ints(round_trip.rights, _ints(-1, -1, -1, -1, 3, 1))
        and _same_ints(round_trip.extras, _ints(-1, -1, -1, -1, -1, 4))
    ):
        passed += 1
        print("  ✅ arena pack/unpack round trip is field-for-field identical")
    else:
        failed += 1
        print("  ❌ arena round trip:", identical, round_trip.status, round_trip.n_nodes)

    # ── a short column is a status and empty output, never five aligned lists and
    #    one short one ───────────────────────────────────────────────────────────
    var ragged = arena_roundtrip(
        _ints(0, 0), _floats(1.0), _ints(-1, -1), _ints(-1, -1), _ints(-1, -1),
        _ints(-1, -1), 0,
    )
    if (
        ragged.status == MODEL_ERR_LENGTH_MISMATCH
        and ragged.n_nodes == 0
        and len(ragged.ops) == 0
    ):
        passed += 1
        print("  ✅ a ragged arena is refused whole")
    else:
        failed += 1
        print("  ❌ ragged arena:", ragged.status, ragged.n_nodes)

    # ── linear_arena builds the canonical 4n+1 layout, and its value is 2*4-3*5+1 ─
    var linear = linear_arena(_floats(2.0, -3.0), 1.0)
    var linear_nodes = arena_from_flat(
        linear.ops, linear.values, linear.var_idx, linear.lefts, linear.rights,
        linear.extras,
    )
    var linear_value = evaluate_expr(linear_nodes, linear.root, _floats(4.0, 5.0), 2)
    var constant_only = linear_arena(List[Float64](), 6.5)
    var constant_value = evaluate_expr(
        arena_from_flat(
            constant_only.ops, constant_only.values, constant_only.var_idx,
            constant_only.lefts, constant_only.rights, constant_only.extras,
        ),
        constant_only.root,
        List[Float64](),
        0,
    )
    if (
        linear.status == MODEL_OK
        and linear.n_nodes == 9
        and linear.root == 8
        and linear_value.value == -6.0
        and eval_expr(linear_nodes, linear.root, _floats(4.0, 5.0)) == -6.0
        and constant_only.n_nodes == 1
        and constant_value.value == 6.5
    ):
        passed += 1
        print("  ✅ 2*x0 - 3*x1 + 1 packs into 9 nodes and is -6 at (4,5)")
    else:
        failed += 1
        print(
            "  ❌ linear_arena:",
            linear.status,
            linear.n_nodes,
            linear.root,
            linear_value.value,
        )

    # ── the whole model validates, and evaluates to the hand-computed numbers ───
    var model = make_model(
        _model_vars(), _objective_nodes(), 5, False, _model_constraints(),
        default_policy(),
    )
    var verdict = validate_model(model)
    var infeasible = evaluate_model(model, at_25)
    var feasible = evaluate_model(model, at_14)
    if (
        verdict.status == MODEL_OK
        and verdict.ok
        and verdict.n_vars == 2
        and verdict.n_constraints == 3
        and verdict.n_objective_nodes == 6
        and verdict.n_constraint_nodes == 7
        and verdict.constraint_index == -1
        and infeasible.status == MODEL_OK
        and infeasible.objective == 19.0
        and _same_floats(infeasible.constraint_value, _floats(7.0, -3.0, 5.0))
        and _same_floats(infeasible.violation, _floats(1.0, 0.0, 0.0))
        and not infeasible.feasible
        and infeasible.max_violation == 1.0
        and infeasible.worst_constraint == 0
        and infeasible.n_violated == 1
        and feasible.feasible
        and feasible.objective == 13.0
        and feasible.max_violation == 0.0
        and feasible.worst_constraint == -1
    ):
        passed += 1
        print("  ✅ the model validates; (2,5) violates c0 by 1 and (1,4) is feasible")
    else:
        failed += 1
        print(
            "  ❌ model evaluation:",
            verdict.status,
            infeasible.status,
            infeasible.objective,
            infeasible.max_violation,
            feasible.feasible,
        )

    # ── a maximisation reports the raw objective AND the number to minimise ─────
    var maximised = make_model(
        _model_vars(), _objective_nodes(), 5, True, _model_constraints(),
        default_policy(),
    )
    var max_eval = evaluate_model(maximised, at_25)
    var max_obj = evaluate_objective(maximised, at_25)
    if (
        max_eval.objective == 19.0
        and max_eval.minimization_objective == -19.0
        and max_eval.maximize
        and max_obj.value == 19.0
        and minimization_value(19.0, True) == -19.0
        and minimization_value(19.0, False) == 19.0
    ):
        passed += 1
        print("  ✅ a maximisation is a flag, not a sign-flipped arena")
    else:
        failed += 1
        print(
            "  ❌ direction:",
            max_eval.objective,
            max_eval.minimization_objective,
            max_obj.value,
        )

    # ── a point of the wrong length has no evaluation ───────────────────────────
    var wrong_length = evaluate_model(model, _floats(1.0))
    if (
        wrong_length.status == MODEL_ERR_POINT_LENGTH
        and not wrong_length.has_objective
        and len(wrong_length.constraint_value) == 0
        and wrong_length.max_violation == MODEL_VIOLATION_ABSENT
    ):
        passed += 1
        print("  ✅ a 1-vector against a 2-variable model is refused, with no numbers")
    else:
        failed += 1
        print("  ❌ point length:", wrong_length.status, len(wrong_length.constraint_value))

    # ── one rejection per constraint defect, each naming its constraint ─────────
    var bad_sense = List[OptConstraint]()
    bad_sense.append(make_constraint(_sum_nodes(), 2, SENSE_LE, 6.0, "c0"))
    bad_sense.append(make_constraint(_diff_nodes(), 2, 7, -3.0, "c1"))
    var sense_model = make_model(
        _model_vars(), _objective_nodes(), 5, False, bad_sense^, default_policy()
    )
    var bad_rhs = List[OptConstraint]()
    bad_rhs.append(make_constraint(_sum_nodes(), 2, SENSE_LE, infinity, "c0"))
    var rhs_model = make_model(
        _model_vars(), _objective_nodes(), 5, False, bad_rhs^, default_policy()
    )
    var bad_con_root = List[OptConstraint]()
    bad_con_root.append(make_constraint(_sum_nodes(), 2, SENSE_LE, 6.0, "c0"))
    bad_con_root.append(make_constraint(_diff_nodes(), 5, SENSE_EQ, -3.0, "c1"))
    var con_root_model = make_model(
        _model_vars(), _objective_nodes(), 5, False, bad_con_root^, default_policy()
    )
    var sense_verdict = validate_model(sense_model)
    var rhs_verdict = validate_model(rhs_model)
    var con_root_verdict = validate_model(con_root_model)
    if (
        sense_verdict.status == MODEL_ERR_SENSE
        and sense_verdict.constraint_index == 1
        and rhs_verdict.status == MODEL_ERR_NON_FINITE_RHS
        and rhs_verdict.constraint_index == 0
        and con_root_verdict.status == MODEL_ERR_EXPR_ROOT
        and con_root_verdict.constraint_index == 1
        and not sense_verdict.ok
    ):
        passed += 1
        print("  ✅ sense, rhs and constraint-root defects each name their constraint")
    else:
        failed += 1
        print(
            "  ❌ constraint defects:",
            sense_verdict.status,
            rhs_verdict.status,
            con_root_verdict.status,
        )

    # ── an objective that references a variable the model does not have ─────────
    var one_var = List[OptVar]()
    one_var.append(opt_var("x0", 0.0, 10.0, VAR_CONTINUOUS))
    var short_model = make_model(
        one_var^, _objective_nodes(), 5, False, List[OptConstraint](), default_policy()
    )
    var short_verdict = validate_model(short_model)
    var short_eval = evaluate_model(short_model, _floats(1.0))
    if (
        short_verdict.status == MODEL_ERR_VAR_INDEX
        and short_verdict.node_index == 3
        and short_verdict.constraint_index == -1
        and short_eval.status == MODEL_ERR_VAR_INDEX
        and not short_eval.has_objective
    ):
        passed += 1
        print("  ✅ an objective over x1 in a 1-variable model is refused at node 3")
    else:
        failed += 1
        print("  ❌ objective var index:", short_verdict.status, short_verdict.node_index)

    # ── every variable-block rejection, each with its own code ──────────────────
    var crossed = check_variables(_one_var(3.0, 1.0, VAR_CONTINUOUS), 1e-9)
    var unknown_kind = check_variables(_one_var(0.0, 1.0, 5), 1e-9)
    var wide_binary = check_variables(_one_var(0.0, 2.0, VAR_BINARY), 1e-9)
    var empty_int = check_variables(_one_var(0.2, 0.8, VAR_INTEGER), 1e-9)
    var ok_int = check_variables(_one_var(0.2, 1.8, VAR_INTEGER), 1e-9)
    var inf_bound = check_variables(_one_var(0.0, infinity, VAR_CONTINUOUS), 1e-9)
    if (
        crossed.status == MODEL_ERR_BOUNDS_CROSSED
        and crossed.var_index == 0
        and unknown_kind.status == MODEL_ERR_VAR_KIND
        and wide_binary.status == MODEL_ERR_BINARY_BOUNDS
        and empty_int.status == MODEL_ERR_INTEGER_BOUNDS
        and ok_int.status == MODEL_OK
        and inf_bound.status == MODEL_ERR_NON_FINITE_BOUND
        and integer_in_interval(0.2, 1.8)
        and not integer_in_interval(0.2, 0.8)
    ):
        passed += 1
        print("  ✅ crossed, unknown-kind, wide-binary, [0.2,0.8]-integer and inf bounds refused")
    else:
        failed += 1
        print(
            "  ❌ variable rejections:",
            crossed.status,
            unknown_kind.status,
            wide_binary.status,
            empty_int.status,
            inf_bound.status,
        )

    # ── the variable census, and the warm-start rules ───────────────────────────
    var census_vars = List[OptVar]()
    census_vars.append(opt_var("a", 0.0, 5.0, VAR_CONTINUOUS))
    census_vars.append(opt_var_free("b", VAR_CONTINUOUS))
    census_vars.append(opt_var("c", 0.0, 7.0, VAR_INTEGER))
    census_vars.append(opt_var_binary("d"))
    census_vars.append(opt_var_warm("e", 0.0, 9.0, VAR_CONTINUOUS, 4.5))
    var census = check_variables(census_vars, 1e-9)
    var start_outside = check_variables(
        _lift_one(opt_var_warm("f", 0.0, 1.0, VAR_CONTINUOUS, 4.0)), 1e-9
    )
    var start_fractional = check_variables(
        _lift_one(opt_var_warm("g", 0.0, 9.0, VAR_INTEGER, 2.5)), 1e-9
    )
    var partial_start = warm_start_point(census_vars, 1e-9)
    var full_start = List[OptVar]()
    full_start.append(opt_var_warm("a", 0.0, 9.0, VAR_CONTINUOUS, 1.5))
    full_start.append(opt_var_warm("b", 0.0, 9.0, VAR_INTEGER, 3.0))
    var whole_start = warm_start_point(full_start, 1e-9)
    if (
        census.status == MODEL_OK
        and census.n_vars == 5
        and census.n_continuous == 3
        and census.n_integer == 1
        and census.n_binary == 1
        and census.n_free == 1
        and census.n_warm_started == 1
        and start_outside.status == MODEL_ERR_WARM_START
        and start_fractional.status == MODEL_ERR_WARM_START
        and partial_start.status == MODEL_ERR_WARM_START
        and len(partial_start.x) == 0
        and whole_start.status == MODEL_OK
        and _same_floats(whole_start.x, _floats(1.5, 3.0))
    ):
        passed += 1
        print("  ✅ the kind census is right; a partial or off-grid warm start is refused")
    else:
        failed += 1
        print(
            "  ❌ census / warm start:",
            census.n_continuous,
            census.n_free,
            start_outside.status,
            partial_start.status,
        )

    # ── projection rounds onto the grid and then clamps into the box ────────────
    var box = List[OptVar]()
    box.append(opt_var("a", 0.0, 10.0, VAR_CONTINUOUS))
    box.append(opt_var("b", 0.0, 10.0, VAR_INTEGER))
    box.append(opt_var_binary("c"))
    var projected = project_point(_floats(-1.0, 2.6, 0.4), box, 1e-9)
    var far_out = List[OptVar]()
    far_out.append(opt_var("b", 0.0, 10.0, VAR_INTEGER))
    var clamped = project_point(_floats(15.4), far_out, 1e-9)
    var already_in = project_point(_floats(1.0, 3.0, 1.0), box, 1e-9)
    if (
        projected.status == MODEL_OK
        and _same_floats(projected.x, _floats(0.0, 3.0, 0.0))
        and projected.n_clamped == 1
        and projected.n_rounded == 2
        and _same_floats(clamped.x, _floats(10.0))
        and already_in.n_clamped == 0
        and already_in.n_rounded == 0
    ):
        passed += 1
        print("  ✅ (-1, 2.6, 0.4) projects to (0, 3, 0) with 1 clamp and 2 roundings")
    else:
        failed += 1
        print(
            "  ❌ projection:",
            projected.status,
            projected.n_clamped,
            projected.n_rounded,
            len(projected.x),
        )

    # ── 1e300 onto the integer grid: a number that exists, or none at all ───────
    # `_round_f` was `Float64(Int(v + 0.5))`. `Int()` past the Float64 integer grid is an
    # out-of-range fptosi — poison, not a truncation — so this exact call returned an
    # ARBITRARY coordinate with status MODEL_OK and n_rounded == 1. Every representable
    # Float64 beyond MODEL_INT_GRID_MAX is already an integer, so the honest projection is
    # the identity: 1e300 comes back unchanged and nothing is counted as rounded.
    var poison_scale = 1.0e300
    var poison_point = project_point_flat(
        _floats(poison_scale), _floats(0.0), _floats(0.0), _ints(VAR_INTEGER),
        _ints(0), _floats(0.0), 1e-9,
    )
    # The second reach path: a discrete warm start past the grid is integral by
    # construction, so it is accepted rather than measured with a poisoned conversion.
    var poison_start = check_variables(
        _lift_one(OptVar("h", 0.0, 0.0, VAR_INTEGER, False, False, True, poison_scale)),
        1e-9,
    )
    # The third: `_delegated_domain_defect` calls `_floor_f(a)` for factorial BEFORE the
    # a > 170 guard. With the poisoned floor, `a != _floor_f(a)` held and 1e300! was
    # reported as a DOMAIN error ("not an integer"); the truth is an overflow.
    var poison_factorial = expr_evaluate_flat(
        _ints(0, 32), _floats(poison_scale, 0.0), _ints(-1, -1), _ints(-1, 0),
        _ints(-1, -1), _ints(-1, -1), 1, List[Float64](),
    )
    # The band the FIX for the above opened, and the reason MODEL_INT_GRID_MAX cannot screen
    # it. In `[2^52, 2^53)` consecutive doubles are exactly 1.0 apart, so every value is
    # already an integer AND `v + 0.5` is an exact tie that round-half-to-even carries to the
    # neighbour. `floor(v + 0.5)` therefore moved every ODD integer in the band UP by one:
    # `_round_f(2^52 + 1)` returned `2^52 + 2`, an already-integral coordinate silently
    # replaced by a DIFFERENT integer under MODEL_OK. 9.0e15 is below 2^53, so the grid guard
    # admits the whole band — the short-circuit at 2^52 is what makes this exact.
    var odd_on_grid = 4503599627370497.0  # 2^52 + 1, exactly representable, already integral
    var odd_point = project_point_flat(
        _floats(odd_on_grid), _floats(0.0), _floats(0.0), _ints(VAR_INTEGER),
        _ints(0), _floats(0.0), 1e-9,
    )
    var even_on_grid = project_point_flat(
        _floats(4503599627370498.0), _floats(0.0), _floats(0.0), _ints(VAR_INTEGER),
        _ints(0), _floats(0.0), 1e-9,
    )
    # Half away from zero, unchanged inside the grid — the parity `expr.mojo` opcode 16 has.
    var halves = project_point(_floats(2.5, -2.5, 2.4), _unbounded_integers(3), 1e-9)
    if (
        poison_point.status == MODEL_OK
        and poison_point.length == 1
        and _same_floats(poison_point.x, _floats(poison_scale))
        and poison_point.n_rounded == 0
        and poison_point.n_clamped == 0
        and poison_start.status == MODEL_OK
        and poison_factorial.status == MODEL_ERR_OVERFLOW
        and not poison_factorial.has_value
        and odd_point.status == MODEL_OK
        and _same_floats(odd_point.x, _floats(odd_on_grid))
        and odd_point.n_rounded == 0
        and even_on_grid.status == MODEL_OK
        and _same_floats(even_on_grid.x, _floats(4503599627370498.0))
        and even_on_grid.n_rounded == 0
        and halves.status == MODEL_OK
        and _same_floats(halves.x, _floats(3.0, -3.0, 2.0))
        and halves.n_rounded == 3
    ):
        passed += 1
        print("  ✅ 1e300 and 2^52+1 project to themselves; 1e300! overflows, not domain")
    else:
        failed += 1
        print(
            "  ❌ integer grid:",
            poison_point.status,
            poison_point.n_rounded,
            poison_start.status,
            poison_factorial.status,
            halves.x[0],
            halves.x[1],
        )

    # ── a policy no solver could honour is a rejection, not a default ───────────
    var no_iterations = make_model(
        _model_vars(), _objective_nodes(), 5, False, List[OptConstraint](),
        opt_policy_new(0, 0.0, 1e-9, 1e-9, 1e-9),
    )
    var negative_tol = make_model(
        _model_vars(), _objective_nodes(), 5, False, List[OptConstraint](),
        opt_policy_new(10, 0.0, -1.0, 1e-9, 1e-9),
    )
    if (
        validate_model(no_iterations).status == MODEL_ERR_POLICY
        and validate_model(negative_tol).status == MODEL_ERR_POLICY
        and validate_model(model).status == MODEL_OK
    ):
        passed += 1
        print("  ✅ a zero iteration cap and a negative tolerance are refused")
    else:
        failed += 1
        print("  ❌ policy:", validate_model(no_iterations).status)

    # ── ONE definition of a valid policy ────────────────────────────────────────
    # `policy_defect` rejected only `tol < 0.0`, so `model_validate` said MODEL_OK for a
    # model with `optimality_tol = 0.0` while linear.mojo, integer.mojo and explain.mojo all
    # rejected that same model at their entry points. A zero convergence tolerance is not
    # "be exact", it is "never converge": an LP vertex at 2.9999999999999996 stays fractional
    # forever. A zero FEASIBILITY tolerance is a different question and stays valid — exact
    # satisfaction of a row is askable — which is what the third case below pins.
    var zero_optimality = make_model(
        _model_vars(), _objective_nodes(), 5, False, List[OptConstraint](),
        opt_policy_new(10, 0.0, 1e-9, 0.0, 1e-9),
    )
    var zero_integrality = make_model(
        _model_vars(), _objective_nodes(), 5, False, List[OptConstraint](),
        opt_policy_new(10, 0.0, 1e-9, 1e-9, 0.0),
    )
    var zero_feasibility = make_model(
        _model_vars(), _objective_nodes(), 5, False, List[OptConstraint](),
        opt_policy_new(10, 0.0, 0.0, 1e-9, 1e-9),
    )
    var zero_optimality_flat = model_to_flat(model)
    zero_optimality_flat.optimality_tol = 0.0
    var zero_integrality_flat = model_to_flat(model)
    zero_integrality_flat.integrality_tol = 0.0
    if (
        validate_model(zero_optimality).status == MODEL_ERR_POLICY
        and validate_model(zero_integrality).status == MODEL_ERR_POLICY
        and validate_model(zero_feasibility).status == MODEL_OK
        and model_validate(zero_optimality_flat).status == MODEL_ERR_POLICY
        and not model_validate(zero_optimality_flat).ok
        and model_validate(zero_integrality_flat).status == MODEL_ERR_POLICY
        and model_evaluate(zero_optimality_flat, at_25).status == MODEL_ERR_POLICY
        and check_variables(_model_vars(), 0.0).status == MODEL_ERR_POLICY
    ):
        passed += 1
        print("  ✅ a zero optimality or integrality tolerance is invalid; zero feasibility is not")
    else:
        failed += 1
        print(
            "  ❌ zero tolerances:",
            validate_model(zero_optimality).status,
            validate_model(zero_integrality).status,
            validate_model(zero_feasibility).status,
            model_validate(zero_optimality_flat).status,
        )

    # ── feasibility is measured against the tolerance, so "feasible" and "feasible
    #    by 1e-12" are different answers ─────────────────────────────────────────
    var tight = make_model(
        _model_vars(), _objective_nodes(), 5, False, _model_constraints(),
        opt_policy_new(100, 0.0, 0.0, 1e-9, 1e-9),
    )
    var slack = make_model(
        _model_vars(), _objective_nodes(), 5, False, _model_constraints(),
        opt_policy_new(100, 0.0, 2.0, 1e-9, 1e-9),
    )
    var tight_eval = evaluate_model(tight, at_25)
    var slack_eval = evaluate_model(slack, at_25)
    if (
        not tight_eval.feasible
        and tight_eval.max_violation == 1.0
        and slack_eval.feasible
        and slack_eval.max_violation == 0.0
        and slack_eval.constraint_value[0] == 7.0
        and sense_violation(7.0, SENSE_LE, 6.0, 0.0) == 1.0
        and sense_violation(7.0, SENSE_LE, 6.0, 2.0) == 0.0
        and sense_violation(4.0, SENSE_GE, 5.0, 0.0) == 1.0
        and sense_violation(5.0, SENSE_EQ, 4.0, 0.0) == 1.0
        and sense_violation(5.0, SENSE_EQ, 4.0, 0.0) == 1.0
        and sense_violation(5.0, 9, 4.0, 0.0) == MODEL_VIOLATION_ABSENT
    ):
        passed += 1
        print("  ✅ the same point is infeasible at tol 0 and feasible at tol 2")
    else:
        failed += 1
        print("  ❌ tolerance:", tight_eval.max_violation, slack_eval.max_violation)

    # ── the wire model: pack, unpack, and the same numbers on both sides ────────
    var wire = model_to_flat(model)
    var rebuilt = model_from_flat(wire)
    var wire_eval = model_evaluate(wire, at_25)
    var rebuilt_eval = evaluate_model(rebuilt, at_25)
    var wire_obj = model_objective(wire, at_25)
    if (
        _same_ints(wire.con_ptr, _ints(0, 3, 6, 7))
        and _same_ints(wire.con_roots, _ints(2, 2, 0))
        and _same_ints(wire.con_senses, _ints(SENSE_LE, SENSE_EQ, SENSE_GE))
        and _same_floats(wire.con_rhs, _floats(6.0, -3.0, 2.0))
        and _same_ints(wire.var_flags, _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED))
        and wire.obj_root == 5
        and model_validate(wire).status == MODEL_OK
        and wire_eval.status == MODEL_OK
        and wire_eval.objective == 19.0
        and _same_floats(wire_eval.constraint_value, _floats(7.0, -3.0, 5.0))
        and rebuilt_eval.objective == 19.0
        and _same_floats(rebuilt_eval.violation, _floats(1.0, 0.0, 0.0))
        and wire_obj.value == 19.0
    ):
        passed += 1
        print("  ✅ the wire model round trips: con_ptr [0,3,6,7], roots relative, same values")
    else:
        failed += 1
        print(
            "  ❌ wire model:",
            len(wire.con_ptr),
            wire_eval.status,
            wire_eval.objective,
            rebuilt_eval.objective,
        )

    # ── a constraint root is RELATIVE to its slice; an absolute one is refused ──
    var absolute = _flat_with_ptr(wire, wire.con_ptr.copy())
    absolute.con_roots = _ints(2, 5, 0)
    var absolute_verdict = model_validate(absolute)
    if (
        absolute_verdict.status == MODEL_ERR_EXPR_ROOT
        and absolute_verdict.constraint_index == 1
        and model_evaluate(absolute, at_25).status == MODEL_ERR_EXPR_ROOT
    ):
        passed += 1
        print("  ✅ an absolute root into the concatenated arena is refused, not evaluated")
    else:
        failed += 1
        print("  ❌ relative roots:", absolute_verdict.status, absolute_verdict.constraint_index)

    # ── con_ptr defects: a non-zero start, a decrease, and a wrong tail ─────────
    var ptr_start = _flat_with_ptr(wire, _ints(1, 3, 6, 7))
    var ptr_drop = _flat_with_ptr(wire, _ints(0, 6, 3, 7))
    var ptr_tail = _flat_with_ptr(wire, _ints(0, 3, 6, 6))
    if (
        model_validate(ptr_start).status == MODEL_ERR_CONSTRAINT_PTR
        and model_validate(ptr_drop).status == MODEL_ERR_CONSTRAINT_PTR
        and model_validate(ptr_tail).status == MODEL_ERR_CONSTRAINT_PTR
        and model_evaluate(ptr_tail, at_25).status == MODEL_ERR_CONSTRAINT_PTR
    ):
        passed += 1
        print("  ✅ a con_ptr that does not describe its arena is refused three ways")
    else:
        failed += 1
        print("  ❌ con_ptr:", model_validate(ptr_start).status, model_validate(ptr_drop).status)

    # ── an unknown flag bit is refused rather than dropped ──────────────────────
    var odd_flags = variables_validate_flat(
        _floats(0.0), _floats(1.0), _ints(VAR_CONTINUOUS), _ints(8), _floats(0.0), 1e-9
    )
    if odd_flags.status == MODEL_ERR_VAR_FLAGS:
        passed += 1
        print("  ✅ variable flag bit 3 is refused, not ignored")
    else:
        failed += 1
        print("  ❌ flags:", odd_flags.status)

    # ── linear_model_flat: the LP shape becomes a general model ────────────────
    # maximize 3*x0 + x1  s.t.  x0 + x1 <= 4,  2*x0 - x1 >= 1,  0 <= x <= 10.
    # At x = (1, 2): objective 5; row 0 = 3 (ok); row 1 = 0, which misses >= 1 by 1.
    var lp = linear_model_flat(
        _floats(3.0, 1.0), _floats(1.0, 1.0, 2.0, -1.0), 2, 2,
        _ints(SENSE_LE, SENSE_GE), _floats(4.0, 1.0), _floats(0.0, 0.0),
        _floats(10.0, 10.0), _ints(VAR_CONTINUOUS, VAR_CONTINUOUS),
        _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED), True,
    )
    var lp_eval = model_evaluate(lp.model, _floats(1.0, 2.0))
    if (
        lp.status == MODEL_OK
        and lp.n_vars == 2
        and lp.n_constraints == 2
        and _same_ints(lp.model.con_ptr, _ints(0, 9, 18))
        and lp_eval.status == MODEL_OK
        and lp_eval.objective == 5.0
        and lp_eval.minimization_objective == -5.0
        and _same_floats(lp_eval.constraint_value, _floats(3.0, 0.0))
        and _same_floats(lp_eval.violation, _floats(0.0, 1.0))
        and lp_eval.worst_constraint == 1
    ):
        passed += 1
        print("  ✅ a 2x2 LP packs into the general model and evaluates to 5 at (1,2)")
    else:
        failed += 1
        print(
            "  ❌ linear_model_flat:",
            lp.status,
            lp_eval.status,
            lp_eval.objective,
            len(lp_eval.violation),
        )

    # ── the wrapping multiply: 3 * 6148914691236517206 == 2 exactly ─────────────
    # A `rows * cols == len(a)` guard passes this and then reads a[0..2^62) off a
    # two-element list, which is an uncatchable process crash. dims_fit divides.
    var wrapped = 3 * 6148914691236517206
    var bomb = linear_model_flat(
        _floats(1.0, 1.0), _floats(1.0, 2.0), 3, 6148914691236517206,
        _ints(SENSE_LE, SENSE_LE, SENSE_LE), _floats(1.0, 1.0, 1.0),
        _floats(0.0, 0.0), _floats(1.0, 1.0), _ints(0, 0),
        _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED), False,
    )
    var negative_shape = linear_model_flat(
        _floats(1.0), _floats(1.0), -1, 1, _ints(SENSE_LE), _floats(1.0),
        _floats(0.0), _floats(1.0), _ints(0), _ints(VAR_FLAG_BOXED), False,
    )
    if (
        wrapped == 2
        and bomb.status == MODEL_ERR_DENSE_SHAPE
        and len(bomb.model.con_ops) == 0
        and negative_shape.status == MODEL_ERR_DENSE_SHAPE
    ):
        passed += 1
        print("  ✅ the wrapping shape (3 x 6148914691236517206) is refused, not indexed")
    else:
        failed += 1
        print("  ❌ dense shape:", wrapped, bomb.status, negative_shape.status)

    # ── mismatched LP arrays are named, not guessed ─────────────────────────────
    var short_c = linear_model_flat(
        _floats(1.0), _floats(1.0, 2.0, 3.0, 4.0), 2, 2, _ints(SENSE_LE, SENSE_LE),
        _floats(1.0, 1.0), _floats(0.0, 0.0), _floats(1.0, 1.0), _ints(0, 0),
        _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED), False,
    )
    var bad_lp_sense = linear_model_flat(
        _floats(1.0, 1.0), _floats(1.0, 2.0, 3.0, 4.0), 2, 2, _ints(SENSE_LE, 9),
        _floats(1.0, 1.0), _floats(0.0, 0.0), _floats(1.0, 1.0), _ints(0, 0),
        _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED), False,
    )
    var nan_matrix = linear_model_flat(
        _floats(1.0, 1.0), _floats(1.0, 2.0, 3.0, not_a_number), 2, 2,
        _ints(SENSE_LE, SENSE_LE), _floats(1.0, 1.0), _floats(0.0, 0.0),
        _floats(1.0, 1.0), _ints(0, 0), _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED), False,
    )
    if (
        short_c.status == MODEL_ERR_LENGTH_MISMATCH
        and bad_lp_sense.status == MODEL_ERR_SENSE
        and nan_matrix.status != MODEL_OK
    ):
        passed += 1
        print("  ✅ a short cost vector, an unknown sense and a NaN in A are each named")
    else:
        failed += 1
        print("  ❌ lp arrays:", short_c.status, bad_lp_sense.status, nan_matrix.status)

    # ── every status code has its own name; a duplicate would make two outcomes
    #    indistinguishable in a log, which is this package's whole subject ──────
    var names = List[String]()
    for code in range(0, 31):
        names.append(model_status_name(code))
    var duplicate = False
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if names[i] == names[j]:
                duplicate = True
    if (
        not duplicate
        and model_status_name(MODEL_OK) == "ok"
        and model_status_name(999) == "unknown_status_999"
    ):
        passed += 1
        print("  ✅ all 31 status codes have distinct names")
    else:
        failed += 1
        print("  ❌ status names:", duplicate)

    print("  [optimization.model] Passed:", passed, "Failed:", failed)
