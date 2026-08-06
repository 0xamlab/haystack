"""test_optimization_integer.mojo — known-value tests for branch and bound.

Hand-written, and every number below was worked out on paper before it was run. The
assertions target the one wrong answer this module exists to prevent: an INCUMBENT returned
as if it were an OPTIMUM.

  * The same program is solved twice, once with room to finish and once under a node limit
    of THREE. The complete run must report 40 with `proven_optimal` and a zero gap; the
    truncated run must report the incumbent 39 with `proven_optimal` False, `status`
    `node_limit`, and a gap of exactly 19/9 against a bound of 370/9 — both hand-derived
    from the two nodes left on the stack. A solver that reports its incumbent as optimal
    passes every other assertion in this file and fails that one.
  * A node limit of ONE on a program whose relaxation is fractional stops before any integer
    point exists. That run must carry NO objective and NO gap while still carrying a real
    `best_bound`, because "nothing found yet, and nothing below 0.5 exists" is a different
    statement from "the answer is 0.5".
  * `2x = 1` is integer-infeasible with a perfectly feasible relaxation, so the relaxation
    value 0.5 is asserted present at the same time as `feasible` False and an EMPTY `x`.
    Rounding that relaxation is what a solver without this module would have returned.
  * The knapsack is asserted against the frozen `combinatorial.knapsack_01_value`, an exact
    DP over a weight table — a completely different algorithm on the same problem, so
    agreement is evidence and not a mirror. Its LP relaxation is 226/9, which is asserted
    too: a knapsack whose relaxation already answered the question would not test the
    branching at all.
  * A one-variable program declared `VAR_BINARY` with the row `3x <= 10` must return 1, not
    3. Treating a binary variable as a plain integer because the caller wrote no `x <= 1`
    row is a silent wrong answer with a feasible-looking point.
  * The same failure through the ARENA path, which is the executed reproduction of the bug
    `milp_from_arenas` had: one integer variable declared `[0, 3]`, one row `x <= 10`,
    maximised. It returned 10 with `proven_optimal` True, because `linear.lp_from_arenas`
    builds its own all-zero variable block and the declared box never reached the search. It
    must return 3, agree with the same model written with the bound as a ROW, and count the
    box row in `n_constraints`. A box that extends below zero is a status, not a clip, and
    the redundant-upper-bound variant of the two-variable program pins that a bound which
    cannot bind does not change the answer.
  * The incumbent VERIFIER's row budget is asserted per row and at two scales, because its
    threshold used to be `feasibility_tol * (1 + |b_i|)` — the form `linear.mojo` documents as
    rejected. At `b_i = 1e9` that is 1.000000001, so a point violating `x <= 1e9` by a FULL
    UNIT verified as `MODEL_OK`, and `_verify_point` is the only thing standing between a
    snapped vertex and an incumbent that prunes the real optimum. The same violation at unit
    scale is asserted to still fail, a legitimate rounding-scale gap at 1e9 to still pass, and
    the SNAP allowance to survive on an integer column while being absent on a continuous one.
  * The status codes are asserted to sit at 100+, clear of `optimization.explain`'s 80-86:
    when this module started at 80, `milp_status_name(81)` and `explain_status_name(81)` gave
    two different meanings for one integer out of one package.
  * The pure-continuous run is asserted EQUAL to `linear.lp_solve_default` and to have
    branched zero times, so the integer machinery is provably inert when there is nothing
    integral to enforce.
  * An unbounded relaxation is asserted to be its own status, distinct from `infeasible`,
    with no answer at all — because an unbounded relaxation does not prove the integer
    program is unbounded.

Exact equality is used wherever the arithmetic is exact in binary floating point: the
integer optima, the vertex coordinates, 41.25, the census invariants and the returned
integrality. A tolerance appears only where a division genuinely rounds — 370/9, 19/9 and
226/9.
"""
from combinatorial import knapsack_01_value
from optimization.integer import (
    MILP_BOX_BELOW_ZERO,
    MILP_DEFAULT_MAX_NODES,
    MILP_DEPTH_LIMIT,
    MILP_INFEASIBLE,
    MILP_MAX_DEPTH,
    MILP_MAX_NODES,
    MILP_MAX_STACK,
    MILP_NODE_LIMIT,
    MILP_OPTIMAL,
    MILP_RELAXATION_FAILED,
    MILP_RELAXATION_UNBOUNDED,
    MILP_SNAP_INFEASIBLE,
    _verify_point,
    branch_choice,
    milp_from_arenas,
    milp_knapsack,
    milp_solve,
    milp_solve_default,
    milp_status_name,
)
from optimization.linear import LP_INFEASIBLE, LP_OPTIMAL, lp_solve_default
from optimization.model import (
    DEFAULT_FEASIBILITY_TOL,
    DEFAULT_INTEGRALITY_TOL,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_OPTIMALITY_TOL,
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_INTEGER_BOUNDS,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_ERR_OVERFLOW,
    MODEL_ERR_POLICY,
    MODEL_ERR_VAR_KIND,
    MODEL_OK,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    VAR_BINARY,
    VAR_CONTINUOUS,
    VAR_FLAG_BOXED,
    VAR_FLAG_HAS_LOWER,
    VAR_FLAG_HAS_UPPER,
    VAR_INTEGER,
    linear_model_flat,
)


def _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d <= tol


def _exact(a: List[Float64], b: List[Float64]) -> Bool:
    """Exact equality. Used only where every value is a small integer or a dyadic
    fraction, so a tolerance there would hide a genuine mis-accumulation."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _all_integral(x: List[Float64]) -> Bool:
    """Every coordinate is EXACTLY on the integer grid, not merely near it.

    Asserted rather than assumed: the incumbent is snapped before it is accepted, so a
    returned 2.9999999999999996 would mean the snap was skipped and the reported point is
    a relaxation vertex wearing an integer answer's status.
    """
    for i in range(len(x)):
        var v = x[i]
        var truncated = Float64(Int(v))
        if v != truncated:
            return False
    return True


def _census_consistent(
    explored: Int, pruned: Int, infeasible: Int, integral: Int,
    branched: Int, open_nodes: Int
) -> Bool:
    """The two structural identities of a binary branch tree.

    Every popped node ends in exactly one class, and every node ever created is either
    classified or still open. Both are exact integer identities, so they catch a
    miscounted prune or a lost subtree that no value assertion would notice.
    """
    if explored != pruned + infeasible + integral + branched:
        return False
    return 1 + 2 * branched == explored + open_nodes


# ── the program every branching assertion is built on ─────────────────────────
# maximise  5x + 8y   subject to   x + y <= 6,   5x + 9y <= 45,   x, y >= 0 and integral.
#
# Relaxation, by hand: the objective's gradient (5, 8) points between the two row normals,
# so the optimum is where they meet — x + y = 6 and 5x + 9y = 45 give 5x + 9(6 - x) = 45,
# 54 - 4x = 45, x = 9/4 = 2.25, y = 15/4 = 3.75, objective 11.25 + 30 = 41.25.
#
# Integer optimum, by enumeration of the whole feasible box:
#   (0,5) 40  (1,4) 37  (2,3) 34  (3,3) 39  (4,2) 36  (5,1) 33  (6,0) 30
#   (2,4) and (1,5) both break 5x + 9y <= 45.
# So 40 at (0, 5) — BELOW the relaxation's 41.25, which is the whole point: a program whose
# relaxation is already integral would not exercise a single branch.


def _c_wolsey() -> List[Float64]:
    return _floats(5.0, 8.0)


def _a_wolsey() -> List[Float64]:
    return _floats(1.0, 1.0, 5.0, 9.0)


def _b_wolsey() -> List[Float64]:
    return _floats(6.0, 45.0)


def main() raises:
    var passed = 0
    var failed = 0

    var le2 = _ints(SENSE_LE, SENSE_LE)
    var int2 = _ints(VAR_INTEGER, VAR_INTEGER)

    # ── the integer optimum is not the relaxation's ───────────────────────────
    var solved = milp_solve_default(
        _c_wolsey(), _a_wolsey(), 2, 2, le2, _b_wolsey(), True, int2, 500
    )
    if (
        solved.status == MILP_OPTIMAL
        and solved.feasible
        and solved.proven_optimal
        and solved.search_complete
        and solved.has_objective
        and solved.objective == 40.0
        and _exact(solved.x, _floats(0.0, 5.0))
        and _all_integral(solved.x)
        and solved.has_bound
        and solved.best_bound == 40.0
        and solved.has_gap
        and solved.gap == 0.0
        and solved.has_relaxation_objective
        and solved.relaxation_objective == 41.25
        and solved.relaxation_status == LP_OPTIMAL
        and solved.n_integer == 2
        and solved.n_binary == 0
        and solved.nodes_branched > 0
        and solved.nodes_open == 0
        and _census_consistent(
            solved.nodes_explored, solved.nodes_pruned, solved.nodes_infeasible,
            solved.nodes_integral, solved.nodes_branched, solved.nodes_open,
        )
    ):
        passed += 1
        print("  ✅ integer optimum 40 at (0,5) proven, against a relaxation of 41.25")
    else:
        failed += 1
        print(
            "  ❌ wolsey MILP wrong:",
            solved.status,
            solved.objective,
            solved.relaxation_objective,
            solved.proven_optimal,
            len(solved.x),
        )

    # ── THE POINT: a node limit does not prove optimality ─────────────────────
    # Three nodes, and the tree is deterministic, so the state at the cut is hand-derivable:
    #   node 1  root, relaxation 41.25 at (2.25, 3.75). Both coordinates are 1/4 away from
    #           an integer, an exact tie, so the rule takes the LOWER index: branch on x.
    #           Children x >= 3 (pushed last, popped first) and x <= 2.
    #   node 2  x >= 3: the region is the triangle (3,0), (6,0), (3,3) and the optimum is
    #           the integral vertex (3,3) worth 39 — the incumbent.
    #   node 3  x <= 2: 5(2) + 9y = 45 gives y = 35/9, objective 10 + 280/9 = 370/9
    #           = 41.111..., fractional, so it branches and pushes two children.
    # The limit now bites with TWO nodes on the stack, both carrying the bound 370/9. So the
    # honest answer is: incumbent 39, bound 370/9, gap 370/9 - 39 = 19/9, NOT proven.
    var capped = milp_solve_default(
        _c_wolsey(), _a_wolsey(), 2, 2, le2, _b_wolsey(), True, int2, 3
    )
    if (
        capped.status == MILP_NODE_LIMIT
        and not capped.proven_optimal
        and not capped.search_complete
        and capped.feasible
        and capped.has_objective
        and capped.objective == 39.0
        and _exact(capped.x, _floats(3.0, 3.0))
        and capped.has_bound
        and _close(capped.best_bound, 370.0 / 9.0, 1e-9)
        and capped.has_gap
        and _close(capped.gap, 19.0 / 9.0, 1e-9)
        and capped.gap > 0.0
        and capped.nodes_explored == 3
        and capped.nodes_open == 2
        and _census_consistent(
            capped.nodes_explored, capped.nodes_pruned, capped.nodes_infeasible,
            capped.nodes_integral, capped.nodes_branched, capped.nodes_open,
        )
    ):
        passed += 1
        print("  ✅ the node limit keeps the incumbent 39 but reports a gap of 19/9")
    else:
        failed += 1
        print(
            "  ❌ truncated search dishonest:",
            capped.status,
            capped.proven_optimal,
            capped.objective,
            capped.best_bound,
            capped.gap,
            capped.nodes_open,
        )

    # The same incumbent under a limit and after a complete search are the SAME numbers in
    # every field but the three that matter. Asserted as a pair so a regression that drops
    # the distinction cannot pass by making both runs "optimal".
    if (
        solved.proven_optimal
        and not capped.proven_optimal
        and solved.status == MILP_OPTIMAL
        and capped.status != MILP_OPTIMAL
        and capped.objective < solved.objective
    ):
        passed += 1
        print("  ✅ the truncated run's status and proven_optimal both differ from the complete one")
    else:
        failed += 1
        print("  ❌ truncation is not distinguishable:", solved.status, capped.status)

    # ── a limit that bites before any integer point exists ────────────────────
    # minimise x subject to 2x = 1, x integral. The relaxation is x = 1/2 with objective
    # 1/2; one node is allowed, so the root branches and stops. There is a real bound (1/2)
    # and NO answer, and a gap needs both ends.
    var eq1 = _ints(SENSE_EQ)
    var one_node = milp_solve_default(
        _floats(1.0), _floats(2.0), 1, 1, eq1, _floats(1.0), False,
        _ints(VAR_INTEGER), 1,
    )
    if (
        one_node.status == MILP_NODE_LIMIT
        and not one_node.feasible
        and not one_node.has_objective
        and one_node.objective == 0.0
        and len(one_node.x) == 0
        and one_node.has_bound
        and one_node.best_bound == 0.5
        and not one_node.has_gap
        and one_node.gap == 0.0
        and not one_node.proven_optimal
        and one_node.nodes_explored == 1
        and one_node.nodes_open == 2
    ):
        passed += 1
        print("  ✅ a limit hit before the first integer point: a real bound, no answer, no gap")
    else:
        failed += 1
        print(
            "  ❌ bound-without-answer wrong:",
            one_node.status,
            one_node.has_objective,
            one_node.best_bound,
            one_node.has_gap,
        )

    # ── integer-infeasible with a feasible relaxation ─────────────────────────
    # The same 2x = 1, given room to finish: both children (x <= 0 and x >= 1) are
    # infeasible, so the search is complete and there is no integer point at all — while
    # the relaxation had one, at 0.5, which is exactly what a round-the-relaxation solver
    # would have returned as the answer.
    var no_integer = milp_solve_default(
        _floats(1.0), _floats(2.0), 1, 1, eq1, _floats(1.0), False,
        _ints(VAR_INTEGER), 500,
    )
    if (
        no_integer.status == MILP_INFEASIBLE
        and no_integer.search_complete
        and not no_integer.feasible
        and not no_integer.proven_optimal
        and not no_integer.has_objective
        and len(no_integer.x) == 0
        and not no_integer.has_bound
        and not no_integer.has_gap
        and no_integer.has_relaxation_objective
        and no_integer.relaxation_objective == 0.5
        and no_integer.relaxation_status == LP_OPTIMAL
        and no_integer.nodes_infeasible == 2
        and no_integer.nodes_branched == 1
        and no_integer.nodes_explored == 3
        and no_integer.nodes_open == 0
        and _census_consistent(
            no_integer.nodes_explored, no_integer.nodes_pruned,
            no_integer.nodes_infeasible, no_integer.nodes_integral,
            no_integer.nodes_branched, no_integer.nodes_open,
        )
    ):
        passed += 1
        print("  ✅ 2x = 1 is integer-infeasible while its relaxation answers 0.5")
    else:
        failed += 1
        print(
            "  ❌ integer-infeasible wrong:",
            no_integer.status,
            no_integer.relaxation_objective,
            no_integer.feasible,
            no_integer.nodes_infeasible,
        )

    # ── the knapsack, against the frozen DP ──────────────────────────────────
    # weights 3 4 5 8 9, values 4 5 6 10 11, capacity 20. By hand: {0,3,4} weighs
    # 3+8+9 = 20 and is worth 4+10+11 = 25; {0,1,2,3} also weighs 20 and is also worth 25.
    # Two optima, so only the VALUE is compared — the point is the objective, and asserting
    # a particular tie-break would be asserting an implementation detail.
    # The relaxation is the ratio fill: item 0 (4/3), then 1 and 3 (5/4 each) fill 15 units
    # for 19, and 5 of item 4's 9 units add 55/9, so the bound is 226/9 = 25.111... — above
    # 25, so the branching is doing real work here.
    var kn_w = _ints(3, 4, 5, 8, 9)
    var kn_v = _ints(4, 5, 6, 10, 11)
    var dp = knapsack_01_value(kn_w, kn_v, 20)
    var bb = milp_knapsack(
        _floats(4.0, 5.0, 6.0, 10.0, 11.0), _floats(3.0, 4.0, 5.0, 8.0, 9.0), 20.0, 5000
    )
    var bb_weight: Float64 = 0.0
    var bb_binary = True
    if len(bb.x) == 5:
        var w = _floats(3.0, 4.0, 5.0, 8.0, 9.0)
        for j in range(5):
            bb_weight += w[j] * bb.x[j]
            if bb.x[j] != 0.0 and bb.x[j] != 1.0:
                bb_binary = False
    else:
        bb_binary = False
    if (
        dp == 25
        and bb.status == MILP_OPTIMAL
        and bb.proven_optimal
        and bb.search_complete
        and bb.objective == Float64(dp)
        and bb.objective == 25.0
        and bb.gap == 0.0
        and bb_binary
        and bb_weight <= 20.0
        and bb.n_binary == 5
        and bb.n_integer == 0
        and _close(bb.relaxation_objective, 226.0 / 9.0, 1e-9)
        and bb.relaxation_objective > bb.objective
        and _census_consistent(
            bb.nodes_explored, bb.nodes_pruned, bb.nodes_infeasible,
            bb.nodes_integral, bb.nodes_branched, bb.nodes_open,
        )
    ):
        passed += 1
        print("  ✅ the knapsack B&B optimum equals the frozen DP exactly (25), relaxation 226/9")
    else:
        failed += 1
        print(
            "  ❌ knapsack disagrees with the DP:",
            dp,
            bb.status,
            bb.objective,
            bb.relaxation_objective,
            bb_weight,
        )

    # ── a binary variable is bounded by its KIND, not by a row the caller forgot ──
    # maximise x subject to 3x <= 10, x binary. Without the x <= 1 the kind promises, the
    # answer is 3 — feasible, integral, and wrong.
    var binary_one = milp_solve_default(
        _floats(1.0), _floats(3.0), 1, 1, _ints(SENSE_LE), _floats(10.0), True,
        _ints(VAR_BINARY), 100,
    )
    if (
        binary_one.status == MILP_OPTIMAL
        and binary_one.proven_optimal
        and binary_one.objective == 1.0
        and _exact(binary_one.x, _floats(1.0))
        and binary_one.n_binary == 1
        and binary_one.n_constraints == 1
        and binary_one.nodes_branched == 0
    ):
        passed += 1
        print("  ✅ VAR_BINARY caps x at 1 with no row from the caller (1, not 3)")
    else:
        failed += 1
        print(
            "  ❌ binary bound not enforced:",
            binary_one.status,
            binary_one.objective,
            binary_one.n_constraints,
        )

    # ── a pure-continuous model is the LP answer, with zero branching ─────────
    var cont2 = _ints(VAR_CONTINUOUS, VAR_CONTINUOUS)
    var relaxed = milp_solve_default(
        _c_wolsey(), _a_wolsey(), 2, 2, le2, _b_wolsey(), True, cont2, 500
    )
    var direct = lp_solve_default(_c_wolsey(), _a_wolsey(), 2, 2, le2, _b_wolsey(), True)
    if (
        relaxed.status == MILP_OPTIMAL
        and relaxed.proven_optimal
        and relaxed.search_complete
        and relaxed.objective == 41.25
        and direct.status == LP_OPTIMAL
        and relaxed.objective == direct.objective
        and _exact(relaxed.x, direct.x)
        and _exact(relaxed.x, _floats(2.25, 3.75))
        and relaxed.best_bound == 41.25
        and relaxed.gap == 0.0
        and relaxed.relaxation_objective == 41.25
        and relaxed.nodes_branched == 0
        and relaxed.nodes_explored == 1
        and relaxed.nodes_integral == 1
        and relaxed.nodes_open == 0
        and relaxed.n_integer == 0
    ):
        passed += 1
        print("  ✅ a continuous model returns the LP vertex in one node, zero branches")
    else:
        failed += 1
        print(
            "  ❌ continuous passthrough wrong:",
            relaxed.status,
            relaxed.objective,
            direct.objective,
            relaxed.nodes_branched,
        )

    # ── an unbounded relaxation is its own outcome, and carries nothing ───────
    # maximise x with no rows at all. The relaxation is unbounded, and that does NOT prove
    # the integer program is unbounded — it means no bound was ever obtained, so the
    # status says exactly that instead of choosing between unbounded and infeasible.
    var unbounded = milp_solve_default(
        _floats(1.0), List[Float64](), 0, 1, List[Int](), List[Float64](), True,
        _ints(VAR_INTEGER), 100,
    )
    if (
        unbounded.status == MILP_RELAXATION_UNBOUNDED
        and unbounded.status != MILP_INFEASIBLE
        and not unbounded.feasible
        and not unbounded.proven_optimal
        and not unbounded.search_complete
        and not unbounded.has_objective
        and not unbounded.has_bound
        and not unbounded.has_gap
        and len(unbounded.x) == 0
        and not unbounded.has_relaxation_objective
    ):
        passed += 1
        print("  ✅ an unbounded relaxation is a status of its own with no answer attached")
    else:
        failed += 1
        print(
            "  ❌ unbounded relaxation wrong:",
            unbounded.status,
            unbounded.has_objective,
            unbounded.has_bound,
        )

    # ── minimisation: the bound is a LOWER bound, and the signs come back right ──
    # minimise 2x + 3y subject to x + y >= 3/2, x, y >= 0 integral. Relaxation: all the
    # weight on the cheaper variable, x = 3/2, objective 3. Integer: x = 2, objective 4 —
    # ABOVE the relaxation, which is the direction a minimisation's bound must sit.
    var mini = milp_solve_default(
        _floats(2.0, 3.0), _floats(1.0, 1.0), 1, 2, _ints(SENSE_GE), _floats(1.5),
        False, int2, 500,
    )
    if (
        mini.status == MILP_OPTIMAL
        and mini.proven_optimal
        and mini.objective == 4.0
        and _exact(mini.x, _floats(2.0, 0.0))
        and mini.relaxation_objective == 3.0
        and mini.relaxation_objective < mini.objective
        and mini.best_bound == 4.0
        and mini.gap == 0.0
        and _all_integral(mini.x)
    ):
        passed += 1
        print("  ✅ a minimisation returns 4 against a relaxation lower bound of 3")
    else:
        failed += 1
        print(
            "  ❌ minimisation wrong:",
            mini.status,
            mini.objective,
            mini.relaxation_objective,
        )

    # ── the same program through a general model's arenas ─────────────────────
    # `model.linear_model_flat` builds the arenas, `milp_from_arenas` reads them back and
    # solves. The answer must be the SAME 40: the wire form is a representation, not a
    # different problem.
    var zeros2 = _floats(0.0, 0.0)
    var lower_flags = _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER)
    var built = linear_model_flat(
        _c_wolsey(), _a_wolsey(), 2, 2, le2, _b_wolsey(),
        zeros2, zeros2, int2, lower_flags, True,
    )
    var from_model = milp_from_arenas(
        built.model.obj_ops, built.model.obj_values, built.model.obj_var_idx,
        built.model.obj_lefts, built.model.obj_rights, built.model.obj_extras,
        built.model.obj_root,
        built.model.con_ptr, built.model.con_roots, built.model.con_senses,
        built.model.con_rhs,
        built.model.con_ops, built.model.con_values, built.model.con_var_idx,
        built.model.con_lefts, built.model.con_rights, built.model.con_extras, 2,
        int2, zeros2, zeros2, lower_flags, True, 500,
    )
    # The SAME model with the same box declared BOXED instead — upper bounds of 6 and 5, both
    # of them redundant against `x + y <= 6` and `5x + 9y <= 45`. A redundant bound must not
    # change the answer, and it must show up as two extra rows in `n_constraints`, because a
    # bound in this package is a row: an arena path that reported 2 rows while solving 4
    # would be hiding exactly the rows whose absence was the bug.
    var boxed_upper = _floats(6.0, 5.0)
    var boxed_flags = _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED)
    var built_boxed = linear_model_flat(
        _c_wolsey(), _a_wolsey(), 2, 2, le2, _b_wolsey(),
        zeros2, boxed_upper, int2, boxed_flags, True,
    )
    var from_boxed = milp_from_arenas(
        built_boxed.model.obj_ops, built_boxed.model.obj_values,
        built_boxed.model.obj_var_idx,
        built_boxed.model.obj_lefts, built_boxed.model.obj_rights,
        built_boxed.model.obj_extras, built_boxed.model.obj_root,
        built_boxed.model.con_ptr, built_boxed.model.con_roots,
        built_boxed.model.con_senses, built_boxed.model.con_rhs,
        built_boxed.model.con_ops, built_boxed.model.con_values,
        built_boxed.model.con_var_idx, built_boxed.model.con_lefts,
        built_boxed.model.con_rights, built_boxed.model.con_extras, 2,
        int2, zeros2, boxed_upper, boxed_flags, True, 500,
    )
    if (
        built.status == MODEL_OK
        and from_model.status == MILP_OPTIMAL
        and from_model.proven_optimal
        and from_model.objective == 40.0
        and _exact(from_model.x, _floats(0.0, 5.0))
        and from_model.relaxation_objective == 41.25
        and from_model.n_constraints == 2
        and from_model.n_vars == 2
        and built_boxed.status == MODEL_OK
        and from_boxed.status == MILP_OPTIMAL
        and from_boxed.proven_optimal
        and from_boxed.objective == 40.0
        and _exact(from_boxed.x, _floats(0.0, 5.0))
        and from_boxed.n_constraints == 4
    ):
        passed += 1
        print("  ✅ the same model through linear_model_flat's arenas gives the same 40")
    else:
        failed += 1
        print(
            "  ❌ arena path diverges:",
            built.status,
            from_model.status,
            from_model.objective,
            from_boxed.status,
            from_boxed.objective,
            from_boxed.n_constraints,
        )

    # ── THE REPRODUCTION: a declared bound must not be dropped ────────────────
    # One INTEGER variable, box [0, 3], one row `x <= 10`, maximise x. Executed against the
    # bound-dropping version, this returned objective 10 with `x = [10.0]`, status
    # MILP_OPTIMAL and `proven_optimal = True` — for a model that states x <= 3. The bug was
    # that `linear.lp_from_arenas` builds its OWN variable block (`var_lower = 0`,
    # `var_upper = 0`, `VAR_FLAG_HAS_LOWER`) and never reads a caller's, so the box never
    # reached the search and the BOUND-FREE relaxation's vertex came back wearing the
    # declared model's status. Only VAR_BINARY survived, because `_root_node` re-adds its
    # `x <= 1` from the kind.
    #
    # The honest answer is 3: `x <= 3` is the binding constraint, `x <= 10` is redundant, and
    # the box row makes `n_constraints` 2 rather than 1.
    var boxed3_lower = _floats(0.0)
    var boxed3_upper = _floats(3.0)
    var boxed3_flags = _ints(VAR_FLAG_BOXED)
    var int1 = _ints(VAR_INTEGER)
    var built3 = linear_model_flat(
        _floats(1.0), _floats(1.0), 1, 1, _ints(SENSE_LE), _floats(10.0),
        boxed3_lower, boxed3_upper, int1, boxed3_flags, True,
    )
    var bounded3 = milp_from_arenas(
        built3.model.obj_ops, built3.model.obj_values, built3.model.obj_var_idx,
        built3.model.obj_lefts, built3.model.obj_rights, built3.model.obj_extras,
        built3.model.obj_root,
        built3.model.con_ptr, built3.model.con_roots, built3.model.con_senses,
        built3.model.con_rhs,
        built3.model.con_ops, built3.model.con_values, built3.model.con_var_idx,
        built3.model.con_lefts, built3.model.con_rights, built3.model.con_extras, 1,
        int1, boxed3_lower, boxed3_upper, boxed3_flags, True, 500,
    )
    # The same model with the bound also written as a ROW, which is what the caller had to do
    # before: the two must agree exactly, since a box row IS that row.
    var as_rows3 = milp_solve_default(
        _floats(1.0), _floats(1.0, 1.0), 2, 1, le2, _floats(10.0, 3.0), True, int1, 500
    )
    if (
        built3.status == MODEL_OK
        and bounded3.status == MILP_OPTIMAL
        and bounded3.feasible
        and bounded3.proven_optimal
        and bounded3.has_objective
        and bounded3.objective == 3.0
        and _exact(bounded3.x, _floats(3.0))
        and bounded3.relaxation_objective == 3.0
        and bounded3.n_vars == 1
        and bounded3.n_constraints == 2
        and as_rows3.status == MILP_OPTIMAL
        and as_rows3.objective == bounded3.objective
        and _exact(as_rows3.x, bounded3.x)
    ):
        passed += 1
        print("  ✅ a declared box [0,3] against a row x <= 10 answers 3, not the row's 10")
    else:
        failed += 1
        print(
            "  ❌ declared bounds dropped:",
            built3.status,
            bounded3.status,
            bounded3.objective,
            len(bounded3.x),
            bounded3.n_constraints,
            as_rows3.objective,
        )

    # A box this solver cannot express is a STATUS, not a clip. `lp_solve`'s convention is
    # `x >= 0`, so a lower bound of -5 states a region no program here can build; answering
    # from the clipped region would report the optimum of a smaller program as proven.
    var below_zero = milp_from_arenas(
        built3.model.obj_ops, built3.model.obj_values, built3.model.obj_var_idx,
        built3.model.obj_lefts, built3.model.obj_rights, built3.model.obj_extras,
        built3.model.obj_root,
        built3.model.con_ptr, built3.model.con_roots, built3.model.con_senses,
        built3.model.con_rhs,
        built3.model.con_ops, built3.model.con_values, built3.model.con_var_idx,
        built3.model.con_lefts, built3.model.con_rights, built3.model.con_extras, 1,
        int1, _floats(-5.0), boxed3_upper, boxed3_flags, True, 500,
    )
    # A variable with NO lower bound is the same fact: free below zero.
    var free_below = milp_from_arenas(
        built3.model.obj_ops, built3.model.obj_values, built3.model.obj_var_idx,
        built3.model.obj_lefts, built3.model.obj_rights, built3.model.obj_extras,
        built3.model.obj_root,
        built3.model.con_ptr, built3.model.con_roots, built3.model.con_senses,
        built3.model.con_rhs,
        built3.model.con_ops, built3.model.con_values, built3.model.con_var_idx,
        built3.model.con_lefts, built3.model.con_rights, built3.model.con_extras, 1,
        int1, boxed3_lower, boxed3_upper, _ints(VAR_FLAG_HAS_UPPER), True, 500,
    )
    # A box that holds no integer at all, and a short bound column: named by the frozen
    # `model.variables_validate_flat`, not solved around.
    var no_integer_box = milp_from_arenas(
        built3.model.obj_ops, built3.model.obj_values, built3.model.obj_var_idx,
        built3.model.obj_lefts, built3.model.obj_rights, built3.model.obj_extras,
        built3.model.obj_root,
        built3.model.con_ptr, built3.model.con_roots, built3.model.con_senses,
        built3.model.con_rhs,
        built3.model.con_ops, built3.model.con_values, built3.model.con_var_idx,
        built3.model.con_lefts, built3.model.con_rights, built3.model.con_extras, 1,
        int1, _floats(0.2), _floats(0.8), boxed3_flags, True, 500,
    )
    var short_box = milp_from_arenas(
        built3.model.obj_ops, built3.model.obj_values, built3.model.obj_var_idx,
        built3.model.obj_lefts, built3.model.obj_rights, built3.model.obj_extras,
        built3.model.obj_root,
        built3.model.con_ptr, built3.model.con_roots, built3.model.con_senses,
        built3.model.con_rhs,
        built3.model.con_ops, built3.model.con_values, built3.model.con_var_idx,
        built3.model.con_lefts, built3.model.con_rights, built3.model.con_extras, 1,
        int1, List[Float64](), boxed3_upper, boxed3_flags, True, 500,
    )
    if (
        below_zero.status == MILP_BOX_BELOW_ZERO
        and not below_zero.feasible
        and not below_zero.has_objective
        and not below_zero.proven_optimal
        and len(below_zero.x) == 0
        and free_below.status == MILP_BOX_BELOW_ZERO
        and no_integer_box.status == MODEL_ERR_INTEGER_BOUNDS
        and not no_integer_box.has_objective
        and short_box.status == MODEL_ERR_LENGTH_MISMATCH
        and milp_status_name(MILP_BOX_BELOW_ZERO)
        == "declared_variable_box_extends_below_zero"
    ):
        passed += 1
        print("  ✅ a box below zero, an empty integer range and a short column are refused")
    else:
        failed += 1
        print(
            "  ❌ box guards wrong:",
            below_zero.status,
            free_below.status,
            no_integer_box.status,
            short_box.status,
        )

    # ── the depth limit is the other truncation, and it is reachable ──────────
    # minimise y subject to 2x - 2y = 1, x, y >= 0 integral. The row says x - y = 1/2, so
    # there is no integer point at all, and yet every relaxation is feasible: x >= 1 forces
    # y = 1/2, y >= 1 forces x = 3/2, x >= 2 forces y = 3/2, and so on forever. This is the
    # program that makes a node or depth limit a CORRECTNESS requirement rather than a
    # convenience — an unbounded integer variable admits an infinite branch chain.
    #
    # Hand-derived from MILP_MAX_DEPTH, not hardcoded: the chain alternates between the two
    # variables, so each PAIR of levels raises y by 1/2 and the deepest node's bound is
    # MILP_MAX_DEPTH/2. The node at depth MILP_MAX_DEPTH branches and both its children are
    # abandoned, so `nodes_open` is 2; the floor sibling at each of the MILP_MAX_DEPTH levels
    # below it is infeasible. `max_nodes` is set well above the total so it is provably the
    # DEPTH limit that bit, not the node limit.
    var deep = milp_solve_default(
        _floats(0.0, 1.0), _floats(2.0, -2.0), 1, 2, eq1, _floats(1.0), False, int2, 4000
    )
    if (
        deep.status == MILP_DEPTH_LIMIT
        and not deep.search_complete
        and not deep.proven_optimal
        and not deep.feasible
        and not deep.has_objective
        and len(deep.x) == 0
        and not deep.has_gap
        and deep.has_bound
        and deep.best_bound == Float64(MILP_MAX_DEPTH) / 2.0
        and deep.max_depth == MILP_MAX_DEPTH + 1
        and deep.nodes_open == 2
        and deep.nodes_branched == MILP_MAX_DEPTH + 1
        and deep.nodes_infeasible == MILP_MAX_DEPTH
        and deep.nodes_explored == 2 * MILP_MAX_DEPTH + 1
        and deep.nodes_explored < 4000
        and _census_consistent(
            deep.nodes_explored, deep.nodes_pruned, deep.nodes_infeasible,
            deep.nodes_integral, deep.nodes_branched, deep.nodes_open,
        )
    ):
        passed += 1
        print("  ✅ an infinite branch chain stops at the depth limit, bound MILP_MAX_DEPTH/2")
    else:
        failed += 1
        print(
            "  ❌ depth limit wrong:",
            deep.status,
            deep.max_depth,
            deep.best_bound,
            deep.nodes_open,
            deep.nodes_explored,
        )

    # ── a zero-variable program is a real answer; an empty one is not ─────────
    # Mirrors `model.mojo`'s rule that a zero-variable model has a constant objective and a
    # genuine optimum, and `sparse_numerics.factor`'s precedent that the 0-unknown system
    # solves. An empty knapsack with room to spare is worth 0 and that 0 is an ANSWER — so
    # `feasible` is True and the gap is closed — while the same knapsack against a negative
    # capacity is infeasible, which is a different fact than "worth nothing".
    var empty_knapsack = milp_knapsack(List[Float64](), List[Float64](), 5.0, 10)
    var impossible = milp_knapsack(List[Float64](), List[Float64](), -1.0, 10)
    var ragged = milp_knapsack(_floats(1.0, 2.0), _floats(1.0), 5.0, 10)
    if (
        empty_knapsack.status == MILP_OPTIMAL
        and empty_knapsack.feasible
        and empty_knapsack.proven_optimal
        and empty_knapsack.has_objective
        and empty_knapsack.objective == 0.0
        and empty_knapsack.gap == 0.0
        and len(empty_knapsack.x) == 0
        and empty_knapsack.nodes_explored == 1
        and empty_knapsack.nodes_branched == 0
        and impossible.status == MILP_INFEASIBLE
        and not impossible.feasible
        and not impossible.has_objective
        and impossible.search_complete
        and ragged.status == MODEL_ERR_LENGTH_MISMATCH
    ):
        passed += 1
        print("  ✅ a zero-item knapsack is worth 0 as an ANSWER; a negative capacity is infeasible")
    else:
        failed += 1
        print(
            "  ❌ degenerate knapsack wrong:",
            empty_knapsack.status,
            empty_knapsack.objective,
            impossible.status,
            ragged.status,
        )

    # ── the branching rule, stated and checked ───────────────────────────────
    # (2.25, 3.75): both are 1/4 from an integer, an exact tie, so the LOWER index wins.
    var tie = branch_choice(_floats(2.25, 3.75), int2, DEFAULT_INTEGRALITY_TOL)
    # (0.1, 0.5): 0.5 is further from an integer than 0.1, so index 1 wins outright.
    var most = branch_choice(_floats(0.1, 0.5), int2, DEFAULT_INTEGRALITY_TOL)
    # a continuous variable is never a branch candidate, however fractional it is
    var skipped = branch_choice(
        _floats(0.5, 0.25), _ints(VAR_CONTINUOUS, VAR_INTEGER), DEFAULT_INTEGRALITY_TOL
    )
    var integral = branch_choice(_floats(2.0, 5.0), int2, DEFAULT_INTEGRALITY_TOL)
    if (
        tie.status == MODEL_OK
        and tie.has_branch
        and tie.var_index == 0
        and tie.value == 2.25
        and tie.fractionality == 0.25
        and tie.floor_bound == 2.0
        and tie.ceil_bound == 3.0
        and tie.n_fractional == 2
        and tie.n_discrete == 2
        and most.has_branch
        and most.var_index == 1
        and most.fractionality == 0.5
        and skipped.has_branch
        and skipped.var_index == 1
        and skipped.n_fractional == 1
        and skipped.n_discrete == 1
        and integral.status == MODEL_OK
        and not integral.has_branch
        and integral.var_index == -1
        and integral.n_fractional == 0
        and integral.n_discrete == 2
    ):
        passed += 1
        print("  ✅ most-fractional with a lowest-index tie-break, continuous vars skipped")
    else:
        failed += 1
        print(
            "  ❌ branching rule wrong:",
            tie.var_index,
            tie.fractionality,
            most.var_index,
            skipped.var_index,
            integral.has_branch,
        )

    # A near-integer coordinate is INTEGRAL, not a branch: 3 - 2^-40 is what a simplex
    # actually returns, and branching on it would push a child bounded by 2 and a child
    # bounded by 3, neither of which narrows anything.
    var nearly = branch_choice(
        _floats(3.0 - 9.0e-13, 1.0), int2, DEFAULT_INTEGRALITY_TOL
    )
    # -2.5 sits between -3 and -2; the bounds have to straddle it in the right order.
    var negative = branch_choice(_floats(-2.5, 1.0), int2, DEFAULT_INTEGRALITY_TOL)
    if (
        not nearly.has_branch
        and nearly.status == MODEL_OK
        and negative.has_branch
        and negative.var_index == 0
        and negative.floor_bound == -3.0
        and negative.ceil_bound == -2.0
        and negative.fractionality == 0.5
    ):
        passed += 1
        print("  ✅ a near-integer value is integral; a negative value floors downwards")
    else:
        failed += 1
        print(
            "  ❌ rounding edges wrong:",
            nearly.has_branch,
            negative.floor_bound,
            negative.ceil_bound,
        )

    # ── the generated-suite argument pattern must be REFUSED, not indexed ────
    # `tests/generate_mojo_tests.py` calls every contract function with a 5-element list for
    # every List and 5 for every Int, so `rows = cols = 5` against a 5-element matrix. That
    # is `A[24]` on a 5-element list, and a read past a List end is an uncatchable process
    # crash that takes the whole worker with it.
    var lf5 = _floats(0.5, 0.6, 0.7, 0.4, 0.3)
    var li5 = _ints(1, 2, 3, 4, 5)
    var sample_solve = milp_solve(
        lf5, 0.5, lf5, 5, 5, li5, lf5, True, li5, 5, 5, 0.5, 0.5, 0.5
    )
    var sample_default = milp_solve_default(lf5, lf5, 5, 5, li5, lf5, True, li5, 5)
    var sample_arenas = milp_from_arenas(
        li5, lf5, li5, li5, li5, li5, 5,
        li5, li5, li5, lf5,
        li5, lf5, li5, li5, li5, li5, 5,
        li5, lf5, lf5, li5, True, 5,
    )
    var sample_branch = branch_choice(lf5, li5, 0.5)
    # The knapsack driver's sample arguments are a legitimate tiny program, so it must
    # SOLVE rather than refuse — and it must terminate inside its five nodes.
    var sample_knapsack = milp_knapsack(lf5, lf5, 0.5, 5)
    if (
        sample_solve.status == MODEL_ERR_DENSE_SHAPE
        and len(sample_solve.x) == 0
        and sample_default.status == MODEL_ERR_DENSE_SHAPE
        and sample_arenas.status != MODEL_OK
        and len(sample_arenas.x) == 0
        and sample_branch.status == MODEL_ERR_VAR_KIND
        and not sample_branch.has_branch
        and (
            sample_knapsack.status == MILP_OPTIMAL
            or sample_knapsack.status == MILP_NODE_LIMIT
        )
        and sample_knapsack.nodes_explored <= 5
    ):
        passed += 1
        print("  ✅ the generated-suite (_lf5 / _li5 / 5) pattern is refused, never indexed")
    else:
        failed += 1
        print(
            "  ❌ sample-argument pattern not handled:",
            sample_solve.status,
            sample_default.status,
            sample_arenas.status,
            sample_branch.status,
            sample_knapsack.status,
        )

    # ── policies a search cannot honour are refused up front ─────────────────
    var no_nodes = milp_solve(
        _c_wolsey(), 0.0, _a_wolsey(), 2, 2, le2, _b_wolsey(), True, int2, 0,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
        DEFAULT_INTEGRALITY_TOL,
    )
    var too_many_nodes = milp_solve(
        _c_wolsey(), 0.0, _a_wolsey(), 2, 2, le2, _b_wolsey(), True, int2,
        MILP_MAX_NODES + 1, DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL,
        DEFAULT_OPTIMALITY_TOL, DEFAULT_INTEGRALITY_TOL,
    )
    # A zero integrality tolerance makes 2.9999999999999996 fractional, so the search would
    # branch forever on a program whose answer it is already holding.
    var zero_int_tol = milp_solve(
        _c_wolsey(), 0.0, _a_wolsey(), 2, 2, le2, _b_wolsey(), True, int2, 500,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL, 0.0,
    )
    var zero_opt_tol = milp_solve(
        _c_wolsey(), 0.0, _a_wolsey(), 2, 2, le2, _b_wolsey(), True, int2, 500,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, 0.0, DEFAULT_INTEGRALITY_TOL,
    )
    var bad_kind = milp_solve_default(
        _c_wolsey(), _a_wolsey(), 2, 2, le2, _b_wolsey(), True, _ints(VAR_INTEGER, 9), 500
    )
    var short_kinds = milp_solve_default(
        _c_wolsey(), _a_wolsey(), 2, 2, le2, _b_wolsey(), True, _ints(VAR_INTEGER), 500
    )
    if (
        no_nodes.status == MODEL_ERR_POLICY
        and too_many_nodes.status == MODEL_ERR_POLICY
        and zero_int_tol.status == MODEL_ERR_POLICY
        and zero_opt_tol.status == MODEL_ERR_POLICY
        and bad_kind.status == MODEL_ERR_VAR_KIND
        and short_kinds.status == MODEL_ERR_LENGTH_MISMATCH
        and not no_nodes.feasible
        and not bad_kind.has_bound
    ):
        passed += 1
        print("  ✅ zero nodes, an over-large node cap, zero tolerances and a bad kind are refused")
    else:
        failed += 1
        print(
            "  ❌ policy guards wrong:",
            no_nodes.status,
            too_many_nodes.status,
            zero_int_tol.status,
            zero_opt_tol.status,
            bad_kind.status,
            short_kinds.status,
        )

    # branch_choice's own guards, which the search relies on before it snaps anything
    var mismatch = branch_choice(_floats(1.0, 2.0), _ints(VAR_INTEGER), 1e-9)
    var zero_tol = branch_choice(_floats(1.5), _ints(VAR_INTEGER), 0.0)
    var off_grid = branch_choice(_floats(1.0e17), _ints(VAR_INTEGER), 1e-9)
    if (
        mismatch.status == MODEL_ERR_LENGTH_MISMATCH
        and not mismatch.has_branch
        and zero_tol.status == MODEL_ERR_POLICY
        and off_grid.status == MODEL_ERR_OVERFLOW
        and off_grid.var_index == -1
    ):
        passed += 1
        print("  ✅ branch_choice refuses a short kind column, a zero tolerance and an off-grid value")
    else:
        failed += 1
        print(
            "  ❌ branch_choice guards wrong:",
            mismatch.status,
            zero_tol.status,
            off_grid.status,
        )

    # ── one name per outcome, and they fall through to the LP and model tables ──
    var names = List[String]()
    names.append(milp_status_name(MILP_OPTIMAL))
    names.append(milp_status_name(MILP_INFEASIBLE))
    names.append(milp_status_name(MILP_RELAXATION_UNBOUNDED))
    names.append(milp_status_name(MILP_NODE_LIMIT))
    names.append(milp_status_name(MILP_DEPTH_LIMIT))
    names.append(milp_status_name(MILP_RELAXATION_FAILED))
    names.append(milp_status_name(MILP_SNAP_INFEASIBLE))
    names.append(milp_status_name(MILP_BOX_BELOW_ZERO))
    names.append(milp_status_name(MODEL_ERR_VAR_KIND))
    var distinct = True
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if names[i] == names[j]:
                distinct = False
    if (
        distinct
        and milp_status_name(MILP_OPTIMAL) == "optimal"
        and milp_status_name(MILP_INFEASIBLE) == "infeasible"
        and milp_status_name(MILP_NODE_LIMIT) == "node_limit"
        and MILP_DEFAULT_MAX_NODES <= MILP_MAX_NODES
    ):
        passed += 1
        print("  ✅ every status names one outcome, and unknown codes fall through by table")
    else:
        failed += 1
        print("  ❌ status names collide:", distinct, milp_status_name(MODEL_ERR_VAR_KIND))

    # ── the incumbent verifier's row budget, per row and at two scales ────────
    # RULE 4b. `_verify_point`'s threshold was `feasibility_tol * (1.0 + fabs(rhs[i]))
    # + integrality_tol * Σ_j|a_ij|`, which is the second form `linear._lp_row_gap_budget`
    # names as rejected: the `1 +` is an absolute FLOOR at a scale the caller never chose, and
    # `feasibility_tol` as the RELATIVE multiplier is 4.5 million ulps at magnitude 1e9. This
    # is the executed reproduction, verbatim — a point one FULL UNIT past `x <= 1e9` came back
    # `MODEL_OK`, so the one check between a snapped vertex and an incumbent that prunes the
    # real optimum passed a violation of 1.0. It must now be LP_INFEASIBLE, which is what
    # `milp_solve` turns into MILP_SNAP_INFEASIBLE rather than an answer.
    var verify_huge = _verify_point(
        _floats(1.0), 1, 1, _ints(SENSE_LE), _floats(1.0e9),
        _floats(1.0e9 + 1.0), _ints(VAR_INTEGER),
        DEFAULT_FEASIBILITY_TOL, DEFAULT_INTEGRALITY_TOL,
    )
    # CONTROL, same violation at unit scale: the fix must not be a blanket tightening that
    # only ever catches large numbers, and it must not have stopped catching this.
    var verify_unit = _verify_point(
        _floats(1.0), 1, 1, _ints(SENSE_LE), _floats(1.0),
        _floats(2.0), _ints(VAR_INTEGER),
        DEFAULT_FEASIBILITY_TOL, DEFAULT_INTEGRALITY_TOL,
    )
    # CONTROL, a legitimate near-zero at LARGE scale: 2e-7 past `x <= 1e9` is inside 1024 ulps
    # of 1e9 (~2.3e-7 per operand, so ~4.5e-7 over the two here), which is what the recomputed
    # dot product and the subtraction genuinely cost at that magnitude. It must still verify,
    # or every honest large-scale MILP aborts as MILP_SNAP_INFEASIBLE.
    var verify_noise = _verify_point(
        _floats(1.0), 1, 1, _ints(SENSE_LE), _floats(1.0e9),
        _floats(1.0e9 + 2.0e-7), _ints(VAR_INTEGER),
        DEFAULT_FEASIBILITY_TOL, DEFAULT_INTEGRALITY_TOL,
    )
    # CONTROL, the SNAP allowance itself, which is the whole reason this budget is looser than
    # `linear`'s: with `a = 1e9` on an INTEGER column, snapping by up to `integrality_tol`
    # moves the activity by up to 1e-9 * 1e9 = 1.0, so 0.5 past the row is the snap and
    # verifies. The SAME row with the SAME 0.5 on a CONTINUOUS column must NOT verify — a
    # continuous coordinate is copied through unchanged, so nothing snapped and nothing
    # explains the 0.5. Summing |a_ij| over columns that cannot have moved was the second half
    # of this defect: one continuous column with |a| = 1e9 bought a full unit of slack.
    var verify_snap = _verify_point(
        _floats(1.0e9), 1, 1, _ints(SENSE_LE), _floats(1.0e9 - 0.5),
        _floats(1.0), _ints(VAR_INTEGER),
        DEFAULT_FEASIBILITY_TOL, DEFAULT_INTEGRALITY_TOL,
    )
    var verify_nosnap = _verify_point(
        _floats(1.0e9), 1, 1, _ints(SENSE_LE), _floats(1.0e9 - 0.5),
        _floats(1.0), _ints(VAR_CONTINUOUS),
        DEFAULT_FEASIBILITY_TOL, DEFAULT_INTEGRALITY_TOL,
    )
    # PER ROW, not per program: one unrelated large-rhs row must not raise the threshold for
    # the row next to it. `x0 <= 1e12` is satisfied with room to spare and `x1 <= 1.0` is
    # violated by 1.0, and the aggregate form `Σ_i |b_i|` would have forgiven the second.
    var verify_mixed = _verify_point(
        _floats(1.0, 0.0, 0.0, 1.0), 2, 2, _ints(SENSE_LE, SENSE_LE),
        _floats(1.0e12, 1.0), _floats(1.0, 2.0), _ints(VAR_INTEGER, VAR_INTEGER),
        DEFAULT_FEASIBILITY_TOL, DEFAULT_INTEGRALITY_TOL,
    )
    if (
        verify_huge == LP_INFEASIBLE
        and verify_unit == LP_INFEASIBLE
        and verify_noise == MODEL_OK
        and verify_snap == MODEL_OK
        and verify_nosnap == LP_INFEASIBLE
        and verify_mixed == LP_INFEASIBLE
    ):
        passed += 1
        print(
            "  ✅ the verifier's row budget is DBL_EPSILON-scaled per row: a unit violation"
            " at b = 1e9 is refused, 2e-7 of rounding is not, and the snap term is only for"
            " columns that snap"
        )
    else:
        failed += 1
        print(
            "  ❌ verifier row budget wrong:", verify_huge, verify_unit, verify_noise,
            verify_snap, verify_nosnap, verify_mixed,
        )

    # ── the codes are one numbering across the package, not two ───────────────
    # These codes used to start at 80, where `optimization.explain` already lives: 81 was
    # BOTH `MILP_NODE_LIMIT` ("node_limit") and `EXPLAIN_FEASIBLE_NO_CORE`
    # ("feasible_so_there_is_no_infeasibility_core"), so a caller that logged an 81 out of
    # this package could not tell which vocabulary it came from. The range is asserted rather
    # than the sibling's constants imported, so this suite does not stop compiling when
    # `explain.mojo` is edited — and so the reserved window (80-99, explain's 80-86 plus
    # headroom) is stated where a new code would be added.
    var own_codes = _ints(
        MILP_RELAXATION_UNBOUNDED, MILP_NODE_LIMIT, MILP_DEPTH_LIMIT,
        MILP_RELAXATION_FAILED, MILP_SNAP_INFEASIBLE, MILP_BOX_BELOW_ZERO,
    )
    var ranges_clear = True
    for i in range(len(own_codes)):
        var code = own_codes[i]
        # `model.mojo` owns 0-30, `linear.mojo` 40-42 and 60-63, `explain.mojo` 80-86.
        if code < 100:
            ranges_clear = False
        for j in range(i + 1, len(own_codes)):
            if own_codes[j] == code:
                ranges_clear = False
    if (
        ranges_clear
        and MILP_OPTIMAL == 0
        and MILP_INFEASIBLE == 60
        and MILP_NODE_LIMIT == 101
        and MILP_SNAP_INFEASIBLE == 104
        and MILP_MAX_STACK == MILP_MAX_DEPTH + 2
    ):
        passed += 1
        print("  ✅ this module's codes are all >= 100, clear of explain's 80-86 block")
    else:
        failed += 1
        print(
            "  ❌ status code ranges collide:",
            MILP_RELAXATION_UNBOUNDED,
            MILP_NODE_LIMIT,
            MILP_BOX_BELOW_ZERO,
        )

    print("  [optimization.integer] Passed:", passed, "Failed:", failed)
