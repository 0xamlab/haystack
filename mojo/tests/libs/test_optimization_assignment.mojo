"""test_optimization_assignment.mojo — known-value tests for the optimal assignment.

Hand-written. Every expected number below was computed by hand, and the 3x3 cases are
verified by ENUMERATION inside the suite itself: all six permutations are scored with
`assignment_cost_of` and the suite asserts that the solver's answer is the unique minimum
among them. That is the oracle for optimality, and it is independent of the solver.

The assertions target the failure this module exists to remove. `combinatorial.assignment_greedy`
is greedy and nothing at its call site says so, so a large share of this suite is
DIFFERENTIAL against it: the frozen kernel is called directly, its pairs are compared
cell-for-cell against `greedy_assignment_flat` (proving that driver is a window onto the
frozen kernel and not a second implementation), and its cost is compared against the
optimum on matrices where it is strictly worse — 14 against 10 on the rank-1 matrix, and
1000000004 against 10 on the matrix with one huge-but-finite cost that greedy walks
straight into on its last row.

The duals are the point of the module, so they are checked three ways: exhaustively
(`u[i] + v[j] <= cost[i][j]` over every pair, with equality on every chosen pair, computed
here in the test and not read off the result struct), by the duality identity
(`sum(u) + sum(v)` equals the total cost), and by hand — the potentials of the huge-cost
3x3 are asserted element by element against a traced-by-hand run of the phases. Two separate
cases perturb a valid certificate in the ways that stay tight and would otherwise pass:
giving an idle agent a nonzero potential (the defect the rejected column-reduction
initialisation would have introduced), and giving a MATCHED agent a positive one, which
violates `u[i] <= 0` — the dual of the capacity constraint `sum_j x[i][j] <= 1` — and which
otherwise reports a dual objective equal to the cost of a matching that is not optimal.

The remaining cases cover absence: a non-perfect matching reported as such with empty
lists rather than as a partial assignment, a non-finite cost refused, the wrapping 64-bit
multiply that `sparse_numerics.csr.dims_fit` exists to catch, and the fixed
five-element/five-integer argument pattern refused by every public driver.
"""
from combinatorial import assignment_greedy
from optimization.assignment import (
    ASSIGN_DEFECT_ABSENT,
    ASSIGN_ERR_BOUND_VIOLATED,
    ASSIGN_ERR_CERTIFICATE,
    ASSIGN_ERR_DIMENSION_TOO_LARGE,
    ASSIGN_ERR_DUPLICATE,
    ASSIGN_ERR_FEWER_AGENTS_THAN_TASKS,
    ASSIGN_ERR_INDEX,
    ASSIGN_ERR_ITERATION_LIMIT,
    ASSIGN_ERR_LENGTH_MISMATCH,
    ASSIGN_ERR_NON_FINITE_COST,
    ASSIGN_ERR_NON_FINITE_DUAL,
    ASSIGN_ERR_NO_PERFECT_MATCHING,
    ASSIGN_ERR_OVERFLOW,
    ASSIGN_ERR_SHAPE,
    ASSIGN_NONE,
    ASSIGN_OK,
    Assignment,
    assign_status_name,
    assignment_cost_of,
    assignment_dual_check,
    assignment_dual_check_masked,
    assignment_solve,
    assignment_solve_masked,
    greedy_assignment_flat,
)


def _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _bools(*vals: Bool) -> List[Bool]:
    var out = List[Bool]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _same_ints(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _same_floats(a: List[Float64], b: List[Float64]) -> Bool:
    """Exact equality. Every value compared with this helper is a small integer, so a
    tolerance would hide a genuine mis-accumulation."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _lf5() -> List[Float64]:
    return _floats(1.5, -2.0, 0.5, 3.0, -1.0)


def _li5() -> List[Int]:
    return _ints(1, 2, 3, 4, 5)


def _lb5() -> List[Bool]:
    return _bools(True, False, True, True, False)


def _rank_one() -> List[Float64]:
    """c[i][j] = (i + 1) * (j + 1) — greedy takes the diagonal (1 + 4 + 9 = 14); the
    optimum is the anti-diagonal (3 + 4 + 3 = 10)."""
    return _floats(1.0, 2.0, 3.0, 2.0, 4.0, 6.0, 3.0, 6.0, 9.0)


def _huge_diagonal() -> List[Float64]:
    """One forbidden-by-price pairing per agent, on the diagonal. Every permutation that
    touches the diagonal costs at least 1e9, so the optimum avoids it entirely."""
    return _floats(1.0e9, 1.0, 2.0, 3.0, 1.0e9, 4.0, 5.0, 6.0, 1.0e9)


def _perm(a: Int, b: Int, c: Int) -> List[Int]:
    return _ints(a, b, c)


def _all_perms3() -> List[List[Int]]:
    var out = List[List[Int]]()
    out.append(_perm(0, 1, 2))
    out.append(_perm(0, 2, 1))
    out.append(_perm(1, 0, 2))
    out.append(_perm(1, 2, 0))
    out.append(_perm(2, 0, 1))
    out.append(_perm(2, 1, 0))
    return out^


def _dual_feasible_everywhere(
    cost: List[Float64], rows: Int, cols: Int, result: Assignment
) -> Bool:
    """Dual feasibility for every pair AND for every agent, computed here rather than
    trusted.

    Both families, because the pair constraints alone are not dual feasibility. The agent
    capacity constraint is `sum_j x[i][j] <= 1`, so `u[i] <= 0` is required for every agent,
    matched or idle — and a helper that only walked the chosen pairs (or only the pair
    constraints) would pass a positive potential on a matched agent, which is precisely the
    forgery that certifies a suboptimal matching for `rows > cols`.
    """
    for w in range(rows):
        if result.u[w] > 0.0:
            return False
        for t in range(cols):
            if result.u[w] + result.v[t] > cost[w * cols + t]:
                return False
    return True


def _chosen_pairs_tight(
    cost: List[Float64], rows: Int, cols: Int, result: Assignment
) -> Bool:
    """Equality on every chosen pair — the half of complementary slackness that a
    trivially small `u` and `v` would satisfy the other half of."""
    for w in range(rows):
        var t = result.col_of_row[w]
        if t == ASSIGN_NONE:
            continue
        if result.u[w] + result.v[t] != cost[w * cols + t]:
            return False
    return True


def _dual_sum(result: Assignment) -> Float64:
    var total = 0.0
    for i in range(len(result.u)):
        total += result.u[i]
    for j in range(len(result.v)):
        total += result.v[j]
    return total


def _is_rejection(result: Assignment) -> Bool:
    """A rejection carries no numbers at all: empty lists, absent cost, absent defects."""
    return (
        result.status != ASSIGN_OK
        and not result.perfect
        and not result.has_cost
        and result.total_cost == 0.0
        and result.n_assigned == 0
        and len(result.col_of_row) == 0
        and len(result.row_of_col) == 0
        and len(result.u) == 0
        and len(result.v) == 0
        and not result.dual_certified
        and result.max_dual_violation == ASSIGN_DEFECT_ABSENT
        and result.max_tight_gap == ASSIGN_DEFECT_ABSENT
        and not result.has_greedy_cost
    )


def main() raises:
    var passed = 0
    var failed = 0

    # ── the 3x3 optimum, verified by enumerating all six permutations ─────────
    var rank_one = _rank_one()
    var solved = assignment_solve(rank_one, 3, 3)
    var perms = _all_perms3()
    var best = 0.0
    var have_best = False
    var n_at_best = 0
    var enumeration_ok = True
    for k in range(len(perms)):
        var scored = assignment_cost_of(rank_one, 3, 3, perms[k])
        if scored.status != ASSIGN_OK or not scored.has_cost or not scored.perfect:
            enumeration_ok = False
            continue
        if (not have_best) or scored.total_cost < best:
            best = scored.total_cost
            have_best = True
            n_at_best = 1
        elif scored.total_cost == best:
            n_at_best += 1
    if (
        enumeration_ok
        and have_best
        and best == 10.0
        and n_at_best == 1
        and solved.status == ASSIGN_OK
        and solved.perfect
        and solved.has_cost
        and solved.total_cost == 10.0
        and solved.n_assigned == 3
        and _same_ints(solved.col_of_row, _ints(2, 1, 0))
        and _same_ints(solved.row_of_col, _ints(2, 1, 0))
    ):
        passed += 1
        print("  ✅ 3x3 optimum is 10.0, the unique minimum over all 6 permutations")
    else:
        failed += 1
        print(
            "  ❌ 3x3 optimum wrong:",
            solved.status,
            solved.total_cost,
            best,
            n_at_best,
        )

    # ── greedy is strictly worse, and that is reported, not hidden ────────────
    var greedy_report = greedy_assignment_flat(rank_one, 3, 3)
    if (
        greedy_report.status == ASSIGN_OK
        and greedy_report.has_cost
        and greedy_report.total_cost == 14.0
        and greedy_report.covers_all_tasks
        and greedy_report.n_assigned == 3
        and _same_ints(greedy_report.col_of_row, _ints(0, 1, 2))
        and solved.has_greedy_cost
        and solved.greedy_cost == 14.0
        and solved.improvement == 4.0
        and solved.total_cost < greedy_report.total_cost
    ):
        passed += 1
        print("  ✅ frozen greedy costs 14.0 here; the optimum is 10.0, improvement 4.0")
    else:
        failed += 1
        print(
            "  ❌ greedy comparison wrong:",
            greedy_report.status,
            greedy_report.total_cost,
            solved.greedy_cost,
            solved.improvement,
        )

    # ── the driver is a WINDOW onto the frozen kernel, not a second one ───────
    var nested = List[List[Float64]]()
    for w in range(3):
        var row = List[Float64]()
        for t in range(3):
            row.append(rank_one[w * 3 + t])
        nested.append(row^)
    var frozen_picks = assignment_greedy(nested)
    if (
        _same_ints(frozen_picks, greedy_report.col_of_row)
        and _same_ints(frozen_picks, _ints(0, 1, 2))
    ):
        passed += 1
        print("  ✅ greedy_assignment_flat returns the frozen kernel's own pairs")
    else:
        failed += 1
        print("  ❌ greedy pairs diverged from the frozen kernel")

    # ── the duals prove it: feasible everywhere, tight on the chosen pairs ────
    var dual_a = assignment_dual_check(
        rank_one, 3, 3, solved.col_of_row, solved.u, solved.v
    )
    if (
        _dual_feasible_everywhere(rank_one, 3, 3, solved)
        and _chosen_pairs_tight(rank_one, 3, 3, solved)
        and _dual_sum(solved) == 10.0
        and solved.dual_certified
        and solved.max_dual_violation == 0.0
        and solved.max_tight_gap == 0.0
        and dual_a.status == ASSIGN_OK
        and dual_a.certified
        and dual_a.dual_feasible
        and dual_a.slack_tight
        and dual_a.n_pairs_checked == 9
        and dual_a.n_idle_nonzero == 0
        and dual_a.has_dual_objective
        and dual_a.dual_objective == 10.0
    ):
        passed += 1
        print("  ✅ 3x3 duals satisfy complementary slackness; dual objective = 10.0")
    else:
        failed += 1
        print(
            "  ❌ 3x3 duals wrong:",
            dual_a.status,
            dual_a.certified,
            dual_a.dual_objective,
            _dual_sum(solved),
        )

    # ── a forbidden-by-price pairing is never chosen ──────────────────────────
    # Greedy walks into it on its last row: 1 + 3 + 1e9. Every permutation touching the
    # diagonal costs >= 1e9, and the two that do not cost 10 and 11.
    var huge = _huge_diagonal()
    var huge_solved = assignment_solve(huge, 3, 3)
    var huge_greedy = greedy_assignment_flat(huge, 3, 3)
    var touches_diagonal = False
    for w in range(3):
        if huge_solved.status == ASSIGN_OK and huge_solved.col_of_row[w] == w:
            touches_diagonal = True
    if (
        huge_solved.status == ASSIGN_OK
        and huge_solved.perfect
        and huge_solved.total_cost == 10.0
        and _same_ints(huge_solved.col_of_row, _ints(1, 2, 0))
        and not touches_diagonal
        and huge_greedy.status == ASSIGN_OK
        and huge_greedy.total_cost == 1000000004.0
        and huge_solved.has_greedy_cost
        and huge_solved.greedy_cost == 1000000004.0
        and huge_solved.improvement == 999999994.0
    ):
        passed += 1
        print("  ✅ the 1e9 pairings are all avoided (10.0 against greedy's 1000000004.0)")
    else:
        failed += 1
        print(
            "  ❌ huge-cost case wrong:",
            huge_solved.status,
            huge_solved.total_cost,
            huge_greedy.total_cost,
            huge_solved.improvement,
        )

    # ── the potentials of that case, traced by hand ───────────────────────────
    # Row reduction gives v = (3, 1, 2); the frozen greedy contributes the two tight pairs
    # (t0, a1) and (t1, a0); one augmenting phase settles a0 then a1 with deltas 0, 2 and
    # 2, so u = (-4, -2, 0) and v = (5, 5, 6). Idle agents would have to be 0 and there are
    # none, and a2 — matched but never scanned — keeps 0.
    if (
        _same_floats(huge_solved.u, _floats(-4.0, -2.0, 0.0))
        and _same_floats(huge_solved.v, _floats(5.0, 5.0, 6.0))
        and _dual_sum(huge_solved) == 10.0
        and _dual_feasible_everywhere(huge, 3, 3, huge_solved)
        and _chosen_pairs_tight(huge, 3, 3, huge_solved)
        and huge_solved.warm_started == 2
        and huge_solved.augmentations == 1
    ):
        passed += 1
        print("  ✅ hand-traced potentials (-4, -2, 0) / (5, 5, 6), 2 warm-started pairs")
    else:
        failed += 1
        print(
            "  ❌ potentials wrong:",
            huge_solved.u[0],
            huge_solved.u[1],
            huge_solved.u[2],
            huge_solved.v[0],
            huge_solved.v[1],
            huge_solved.v[2],
            huge_solved.warm_started,
            huge_solved.augmentations,
        )

    # ── rectangular: more agents than tasks, every task assigned ─────────────
    # Column minima are 2 (agent 1) and 1 (agent 0) and they are achieved by distinct
    # agents, so 3.0 is optimal by that bound alone — an oracle independent of the solver.
    var wide = _floats(4.0, 1.0, 2.0, 9.0, 8.0, 8.0, 5.0, 3.0)
    var wide_solved = assignment_solve(wide, 4, 2)
    var col_min_bound = 0.0
    for t in range(2):
        var m = wide[t]
        for w in range(4):
            if wide[w * 2 + t] < m:
                m = wide[w * 2 + t]
        col_min_bound += m
    if (
        wide_solved.status == ASSIGN_OK
        and wide_solved.perfect
        and wide_solved.n_assigned == 2
        and wide_solved.total_cost == 3.0
        and col_min_bound == 3.0
        and _same_ints(wide_solved.col_of_row, _ints(1, 0, ASSIGN_NONE, ASSIGN_NONE))
        and _same_ints(wide_solved.row_of_col, _ints(1, 0))
        and _same_floats(wide_solved.u, _floats(0.0, 0.0, 0.0, 0.0))
        and _same_floats(wide_solved.v, _floats(2.0, 1.0))
        and wide_solved.warm_started == 2
        and wide_solved.augmentations == 0
    ):
        passed += 1
        print("  ✅ 4x2 assigns both tasks for 3.0; the two idle agents carry u = 0")
    else:
        failed += 1
        print(
            "  ❌ rectangular case wrong:",
            wide_solved.status,
            wide_solved.total_cost,
            col_min_bound,
            wide_solved.n_assigned,
        )

    # ── 5 agents / 4 tasks, checked against all 120 injections ───────────────
    # Two of the four tasks are warm-started by the frozen greedy and the other two need a
    # real augmenting path, so this is the case where the exact solver does work greedy
    # cannot: 7.0 against greedy's 10.0. The oracle is exhaustive — every way of handing
    # the four tasks to distinct agents is scored with `assignment_cost_of`.
    var five = _floats(
        8.0, 8.0, 1.0, 7.0,
        6.0, 9.0, 5.0, 9.0,
        2.0, 2.0, 4.0, 2.0,
        2.0, 5.0, 5.0, 1.0,
        3.0, 5.0, 3.0, 7.0,
    )
    var five_solved = assignment_solve(five, 5, 4)
    var five_greedy = greedy_assignment_flat(five, 5, 4)
    var five_best = 0.0
    var five_have = False
    var five_ties = 0
    var five_counted = 0
    for a0 in range(5):
        for a1 in range(5):
            if a1 == a0:
                continue
            for a2 in range(5):
                if a2 == a0 or a2 == a1:
                    continue
                for a3 in range(5):
                    if a3 == a0 or a3 == a1 or a3 == a2:
                        continue
                    var candidate = List[Int]()
                    for _ in range(5):
                        candidate.append(ASSIGN_NONE)
                    candidate[a0] = 0
                    candidate[a1] = 1
                    candidate[a2] = 2
                    candidate[a3] = 3
                    var scored = assignment_cost_of(five, 5, 4, candidate)
                    if scored.status != ASSIGN_OK or not scored.perfect:
                        continue
                    five_counted += 1
                    if (not five_have) or scored.total_cost < five_best:
                        five_best = scored.total_cost
                        five_have = True
                        five_ties = 1
                    elif scored.total_cost == five_best:
                        five_ties += 1
    if (
        five_counted == 120
        and five_best == 7.0
        and five_ties == 1
        and five_solved.status == ASSIGN_OK
        and five_solved.perfect
        and five_solved.total_cost == 7.0
        and five_solved.n_assigned == 4
        and _same_ints(five_solved.col_of_row, _ints(2, ASSIGN_NONE, 1, 3, 0))
        and _same_ints(five_solved.row_of_col, _ints(4, 2, 0, 3))
        and _dual_feasible_everywhere(five, 5, 4, five_solved)
        and _chosen_pairs_tight(five, 5, 4, five_solved)
        and _dual_sum(five_solved) == 7.0
        and five_solved.warm_started == 2
        and five_solved.augmentations == 2
        and five_solved.greedy_cost == 15.0
        and five_solved.improvement == 8.0
        and five_greedy.total_cost == 10.0
        and five_greedy.covers_all_tasks
    ):
        passed += 1
        print("  ✅ 5x4 optimum 7.0 is the unique best of all 120 injections (greedy: 10.0)")
    else:
        failed += 1
        print(
            "  ❌ 5x4 case wrong:",
            five_solved.status,
            five_solved.total_cost,
            five_best,
            five_ties,
            five_counted,
            five_solved.augmentations,
            five_greedy.total_cost,
        )

    # ── an idle agent with a potential is refused, however tight the rest is ──
    # This is the defect the rejected column-reduction initialisation would introduce: the
    # capacity constraint is `sum_j x[i][j] <= 1`, so an unused agent's potential must be
    # exactly 0 or complementary slackness fails. The forged value is NEGATIVE on purpose:
    # -1.0 is dual-feasible (`u[i] <= 0` holds) and every chosen pair is still tight, so the
    # only thing wrong with it is the slackness condition, and the dual objective drops to
    # 2.0 against a primal cost of 3.0 — no strong duality, therefore no proof.
    var forged_u = _floats(0.0, 0.0, -1.0, 0.0)
    var forged = assignment_dual_check(
        wide, 4, 2, wide_solved.col_of_row, forged_u, wide_solved.v
    )
    if (
        forged.status == ASSIGN_OK
        and forged.dual_feasible
        and forged.slack_tight
        and forged.n_idle_nonzero == 1
        and forged.n_agent_sign_violations == 0
        and forged.has_dual_objective
        and forged.dual_objective == 2.0
        and not forged.certified
    ):
        passed += 1
        print("  ✅ a nonzero potential on an idle agent refuses certification")
    else:
        failed += 1
        print(
            "  ❌ idle-potential check wrong:",
            forged.status,
            forged.dual_feasible,
            forged.n_idle_nonzero,
            forged.dual_objective,
            forged.certified,
        )

    # ── a POSITIVE potential on a MATCHED agent is refused too ────────────────
    # The regression. `u[i] <= 0` is the dual of `sum_j x[i][j] <= 1`, and without it this
    # triple passes every other test: feasible on both pairs, tight on the chosen pair, no
    # idle agent carrying a potential (the idle one is at exactly 0.0), and a dual objective
    # of 5.0 that matches the matching's own cost of 5.0 — a perfect-looking strong-duality
    # certificate for a matching whose true optimum is 1.0, reachable by giving the task to
    # agent 1 instead. `n_idle_nonzero` is blind to it because the positive potential sits on
    # the matched agent, and rows > cols is the case this module goes out of its way to
    # support, so this is the shape that mattered.
    var suboptimal_cost = _floats(5.0, 1.0)
    var forged_sign = assignment_dual_check(
        suboptimal_cost, 2, 1, _ints(0, -1), _floats(4.0, 0.0), _floats(1.0)
    )
    var suboptimal_scored = assignment_cost_of(suboptimal_cost, 2, 1, _ints(0, -1))
    var true_optimum = assignment_solve(suboptimal_cost, 2, 1)
    var honest_dual = assignment_dual_check(
        suboptimal_cost, 2, 1, true_optimum.col_of_row, true_optimum.u, true_optimum.v
    )
    # The same forgery, handed to the suite's own dual helper: it must reject it too, or the
    # helper that "proves the duals" for every other case in this file is proving the pair
    # constraints and nothing else. `_chosen_pairs_tight` still accepts it, which is the
    # point — tightness was never the missing half.
    var forged_result = Assignment(
        ASSIGN_OK, True, 2, 1, 1, True, 5.0,
        _ints(0, ASSIGN_NONE), _ints(0), _floats(4.0, 0.0), _floats(1.0),
        True, 0.0, 0.0, False, 0.0, 0.0, 0, 0,
    )
    if (
        not _dual_feasible_everywhere(suboptimal_cost, 2, 1, forged_result)
        and _chosen_pairs_tight(suboptimal_cost, 2, 1, forged_result)
        and _dual_feasible_everywhere(suboptimal_cost, 2, 1, true_optimum)
        and _chosen_pairs_tight(suboptimal_cost, 2, 1, true_optimum)
        and forged_sign.status == ASSIGN_OK
        and not forged_sign.certified
        and not forged_sign.dual_feasible
        and forged_sign.slack_tight
        and forged_sign.n_idle_nonzero == 0
        and forged_sign.n_agent_sign_violations == 1
        and forged_sign.max_dual_violation == 4.0
        and forged_sign.dual_objective == 5.0
        and suboptimal_scored.status == ASSIGN_OK
        and suboptimal_scored.total_cost == 5.0
        and true_optimum.status == ASSIGN_OK
        and true_optimum.perfect
        and true_optimum.total_cost == 1.0
        and _same_ints(true_optimum.col_of_row, _ints(ASSIGN_NONE, 0))
        and _same_floats(true_optimum.u, _floats(0.0, 0.0))
        and _same_floats(true_optimum.v, _floats(1.0))
        and true_optimum.dual_certified
        and honest_dual.certified
        and honest_dual.dual_objective == 1.0
    ):
        passed += 1
        print("  ✅ u = (4, 0) is refused: the optimum of (5, 1) is 1.0, not the certified 5.0")
    else:
        failed += 1
        print(
            "  ❌ agent-sign check wrong:",
            forged_sign.certified,
            forged_sign.dual_feasible,
            forged_sign.n_agent_sign_violations,
            forged_sign.max_dual_violation,
            forged_sign.dual_objective,
            true_optimum.total_cost,
            honest_dual.certified,
        )

    # ── one big cell may not buy slack for a small pair (rule 4b) ─────────────
    # The regression, verbatim as it reproduced. `_certificate_tol` was
    # `DEFAULT_FEASIBILITY_TOL * (1 + max_ij |c_ij|)`: a MAX over every cell, a 1.0 floor, and
    # the caller's tolerance used as the RELATIVE multiplier. One cell of 1e9 made the
    # threshold `1e-9 * (1 + 1e9)` = exactly 1.0, so this triple came back
    # `certified = True, dual_feasible = True` on a matching costing 1e9 + 0.5 whose optimum
    # is 1e9 — the reduced cost of the unchosen pair (0, 0) is -0.5, and 0.5 is not a rounding
    # artefact between terms whose own magnitudes are 0.0, 0.0 and 0.5.
    var scaled_cost = _floats(0.0, 1.0e9, 0.5, 1.0e9)
    var swallowed = assignment_dual_check(
        scaled_cost, 2, 2, _ints(1, 0), _floats(0.0, 0.0), _floats(0.5, 1.0e9)
    )
    var swallowed_scored = assignment_cost_of(scaled_cost, 2, 2, _ints(1, 0))
    var scaled_optimum = assignment_solve(scaled_cost, 2, 2)
    var scaled_honest = assignment_dual_check(
        scaled_cost, 2, 2, scaled_optimum.col_of_row, scaled_optimum.u, scaled_optimum.v
    )
    if (
        swallowed.status == ASSIGN_OK
        and not swallowed.certified
        and not swallowed.dual_feasible
        and swallowed.slack_tight  # tightness was never the missing half
        and swallowed.n_idle_nonzero == 0
        and swallowed.n_agent_sign_violations == 0
        and swallowed.max_dual_violation == 0.5
        and swallowed.dual_objective == 1000000000.5
        # …and the matching it used to certify really is suboptimal, by that same 0.5.
        and swallowed_scored.status == ASSIGN_OK
        and swallowed_scored.total_cost == 1000000000.5
        and scaled_optimum.status == ASSIGN_OK
        and scaled_optimum.total_cost == 1.0e9
        and _same_ints(scaled_optimum.col_of_row, _ints(0, 1))
        and scaled_optimum.dual_certified
        and scaled_honest.certified
        and scaled_honest.dual_objective == 1.0e9
    ):
        passed += 1
        print("  ✅ a 0.5 dual violation beside a 1e9 cell is refused, not certified")
    else:
        failed += 1
        print(
            "  ❌ scaled certificate wrong:",
            swallowed.certified,
            swallowed.dual_feasible,
            swallowed.max_dual_violation,
            swallowed.dual_objective,
            scaled_optimum.total_cost,
            scaled_honest.certified,
        )

    # ── CONTROL 1: the same violation at unit scale was always caught ─────────
    # Identical structure with the 1e9 cells replaced by 1.0 — the reduced cost of pair
    # (0, 0) is still exactly -0.5. The old threshold here was `1e-9 * (1 + 1.0)` = 2e-9, so
    # this case passed before the fix and passes after it. That is what makes the case above a
    # SCALE defect and not a missing check, and it is the assertion that proves the fix is a
    # re-scaling rather than a blanket tightening of the certificate.
    var unit_cost = _floats(0.0, 1.0, 0.5, 1.0)
    var unit_swallowed = assignment_dual_check(
        unit_cost, 2, 2, _ints(1, 0), _floats(0.0, 0.0), _floats(0.5, 1.0)
    )
    if (
        unit_swallowed.status == ASSIGN_OK
        and not unit_swallowed.certified
        and not unit_swallowed.dual_feasible
        and unit_swallowed.slack_tight
        and unit_swallowed.max_dual_violation == 0.5
    ):
        passed += 1
        print("  ✅ the same 0.5 violation at unit scale is refused too")
    else:
        failed += 1
        print(
            "  ❌ unit-scale control wrong:",
            unit_swallowed.certified,
            unit_swallowed.dual_feasible,
            unit_swallowed.max_dual_violation,
        )

    # ── CONTROL 2: a genuine near-zero at 1e9 must still certify ──────────────
    # The optimal triple for the same matrix with `v[1]` nudged by FOUR ULPS of 1e9
    # (ulp(1e9) = 2^-52 * 2^29 = 1.19209...e-7, so the nudge is exactly representable and no
    # rounding hides it). The reduced cost of pairs (0, 1) and (1, 1) is then -4.768e-7 and
    # the chosen pair (1, 1) is off tightness by the same amount — real cancellation noise at
    # this magnitude, which the per-pair budget of `1024 * DBL_EPSILON * 2e9` = 4.5e-4
    # absorbs. A certificate that refused this would be useless on currency-scale costs, so
    # the relative term is still doing its job: `certified` is True WITH a nonzero measured
    # violation reported beside it.
    var four_ulps = 4.76837158203125e-07
    var noisy_v = _floats(0.0, 1.0e9 + four_ulps)
    var noisy = assignment_dual_check(
        scaled_cost, 2, 2, _ints(0, 1), _floats(0.0, 0.0), noisy_v
    )
    # …and the SAME absolute defect at unit scale is 2 billion ulps, so it is a violation.
    var noisy_unit = assignment_dual_check(
        unit_cost, 2, 2, _ints(0, 1), _floats(0.0, 0.0), _floats(0.0, 1.0 + four_ulps)
    )
    if (
        noisy.status == ASSIGN_OK
        and noisy.certified
        and noisy.dual_feasible
        and noisy.slack_tight
        and noisy.max_dual_violation == four_ulps
        and noisy.max_tight_gap == four_ulps
        and noisy.n_agent_sign_violations == 0
        and noisy_unit.status == ASSIGN_OK
        and not noisy_unit.certified
        and not noisy_unit.dual_feasible
        and noisy_unit.max_dual_violation == four_ulps
    ):
        passed += 1
        print("  ✅ 4 ulps of 1e9 still certifies; the same 4.8e-7 at scale 1.0 does not")
    else:
        failed += 1
        print(
            "  ❌ near-zero control wrong:",
            noisy.certified,
            noisy.dual_feasible,
            noisy.slack_tight,
            noisy.max_dual_violation,
            noisy.max_tight_gap,
            noisy_unit.certified,
        )

    # ── an infeasible dual is caught too ─────────────────────────────────────
    var bumped = _floats(solved.u[0] + 1.0, solved.u[1], solved.u[2])
    var bad_dual = assignment_dual_check(rank_one, 3, 3, solved.col_of_row, bumped, solved.v)
    if (
        bad_dual.status == ASSIGN_OK
        and not bad_dual.dual_feasible
        and not bad_dual.certified
        and bad_dual.max_dual_violation == 1.0
    ):
        passed += 1
        print("  ✅ u[0] + 1 breaks feasibility by exactly 1.0 and is reported")
    else:
        failed += 1
        print(
            "  ❌ infeasible dual not caught:",
            bad_dual.dual_feasible,
            bad_dual.max_dual_violation,
        )

    # ── a mask changes the answer, and the forbidden pair stays unused ────────
    # Forbidding (agent 2, task 0) removes the two cheapest permutations, leaving 11.0.
    var mask = _bools(
        True, True, True, True, True, True, False, True, True
    )
    var masked_solved = assignment_solve_masked(rank_one, 3, 3, mask)
    var masked_dual = assignment_dual_check_masked(
        rank_one, 3, 3, masked_solved.col_of_row, masked_solved.u, masked_solved.v, mask
    )
    if (
        masked_solved.status == ASSIGN_OK
        and masked_solved.perfect
        and masked_solved.total_cost == 11.0
        and _same_ints(masked_solved.col_of_row, _ints(2, 0, 1))
        and masked_solved.total_cost > solved.total_cost
        and masked_dual.status == ASSIGN_OK
        and masked_dual.certified
        and masked_dual.n_pairs_checked == 8
        and masked_dual.dual_objective == 11.0
    ):
        passed += 1
        print("  ✅ forbidding one pair moves the optimum from 10.0 to 11.0, still certified")
    else:
        failed += 1
        print(
            "  ❌ masked solve wrong:",
            masked_solved.status,
            masked_solved.total_cost,
            masked_dual.certified,
            masked_dual.n_pairs_checked,
        )

    # ── no perfect matching: a Hall violation only the search can see ─────────
    # Agents 0 and 1 can do task 0 only; task 1 and task 2 both need agent 2. Every task
    # has SOME allowed agent, so the cheap per-task pre-check passes and the alternating
    # tree has to prove it.
    var flat_ones = List[Float64]()
    for _ in range(9):
        flat_ones.append(1.0)
    var hall = _bools(
        True, False, False, True, False, False, True, True, True
    )
    var hall_solved = assignment_solve_masked(flat_ones, 3, 3, hall)
    # And the degenerate form: task 1 has no allowed agent at all.
    var orphan = _bools(
        True, False, True, True, False, True, True, False, True
    )
    var orphan_solved = assignment_solve_masked(flat_ones, 3, 3, orphan)
    if (
        hall_solved.status == ASSIGN_ERR_NO_PERFECT_MATCHING
        and _is_rejection(hall_solved)
        and orphan_solved.status == ASSIGN_ERR_NO_PERFECT_MATCHING
        and _is_rejection(orphan_solved)
        and assign_status_name(hall_solved.status) == "no_perfect_matching"
    ):
        passed += 1
        print("  ✅ both no-perfect-matching shapes are refused with no partial answer")
    else:
        failed += 1
        print(
            "  ❌ no-perfect-matching wrong:",
            hall_solved.status,
            hall_solved.n_assigned,
            orphan_solved.status,
        )

    # ── negative costs work, and the potentials go negative with them ─────────
    var negative = _floats(-5.0, -1.0, -2.0, -3.0)
    var neg_solved = assignment_solve(negative, 2, 2)
    if (
        neg_solved.status == ASSIGN_OK
        and neg_solved.total_cost == -8.0
        and _same_ints(neg_solved.col_of_row, _ints(0, 1))
        and _same_floats(neg_solved.v, _floats(-5.0, -3.0))
        and _same_floats(neg_solved.u, _floats(0.0, 0.0))
        and _dual_sum(neg_solved) == -8.0
        and neg_solved.dual_certified
        and neg_solved.has_greedy_cost
        and neg_solved.greedy_cost == -8.0
        and neg_solved.improvement == 0.0
    ):
        passed += 1
        print("  ✅ negative costs: -8.0 with v = (-5, -3), and greedy ties here")
    else:
        failed += 1
        print(
            "  ❌ negative-cost case wrong:",
            neg_solved.status,
            neg_solved.total_cost,
            neg_solved.improvement,
        )

    # ── the 1x1 problem, and the two empty ones ──────────────────────────────
    var one = assignment_solve(_floats(5.0), 1, 1)
    var nothing = assignment_solve(List[Float64](), 0, 0)
    var idle_only = assignment_solve(List[Float64](), 3, 0)
    if (
        one.status == ASSIGN_OK
        and one.total_cost == 5.0
        and _same_floats(one.u, _floats(0.0))
        and _same_floats(one.v, _floats(5.0))
        and nothing.status == ASSIGN_OK
        and nothing.perfect
        and nothing.has_cost
        and nothing.total_cost == 0.0
        and len(nothing.col_of_row) == 0
        and idle_only.status == ASSIGN_OK
        and idle_only.perfect
        and idle_only.has_cost
        and idle_only.total_cost == 0.0
        and _same_ints(idle_only.col_of_row, _ints(ASSIGN_NONE, ASSIGN_NONE, ASSIGN_NONE))
        and len(idle_only.v) == 0
    ):
        passed += 1
        print("  ✅ 1x1 solves; 0 tasks is a real answer (cost 0.0, every agent idle)")
    else:
        failed += 1
        print(
            "  ❌ small cases wrong:",
            one.status,
            one.total_cost,
            nothing.status,
            idle_only.status,
        )

    # ── more tasks than agents is refused, and greedy's version is not ────────
    # The contrast is the honesty: the frozen greedy hands back a full-length list with
    # every agent placed, and task 2 simply never happens.
    var tall = _floats(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    var tall_solved = assignment_solve(tall, 2, 3)
    var tall_greedy = greedy_assignment_flat(tall, 2, 3)
    if (
        tall_solved.status == ASSIGN_ERR_FEWER_AGENTS_THAN_TASKS
        and _is_rejection(tall_solved)
        and tall_solved.rows == 2
        and tall_solved.cols == 3
        and tall_greedy.status == ASSIGN_OK
        and tall_greedy.n_assigned == 2
        and not tall_greedy.covers_all_tasks
        and tall_greedy.total_cost == 6.0
        and _same_ints(tall_greedy.col_of_row, _ints(0, 1))
    ):
        passed += 1
        print("  ✅ 2 agents / 3 tasks: refused here, silently partial in the frozen kernel")
    else:
        failed += 1
        print(
            "  ❌ tall case wrong:",
            tall_solved.status,
            tall_greedy.n_assigned,
            tall_greedy.covers_all_tasks,
            tall_greedy.total_cost,
        )

    # ── a non-finite cost is refused, not reduced ─────────────────────────────
    var inf_value = Float64(1.0) / Float64(0.0)
    var nan_value = Float64(0.0) / Float64(0.0)
    var with_inf = _floats(1.0, 2.0, inf_value, 4.0)
    var with_nan = _floats(1.0, nan_value, 3.0, 4.0)
    var inf_solved = assignment_solve(with_inf, 2, 2)
    var nan_solved = assignment_solve(with_nan, 2, 2)
    var inf_greedy = greedy_assignment_flat(with_inf, 2, 2)
    if (
        inf_solved.status == ASSIGN_ERR_NON_FINITE_COST
        and _is_rejection(inf_solved)
        and nan_solved.status == ASSIGN_ERR_NON_FINITE_COST
        and _is_rejection(nan_solved)
        and inf_greedy.status == ASSIGN_ERR_NON_FINITE_COST
        and assign_status_name(inf_solved.status) == "non_finite_cost"
    ):
        passed += 1
        print("  ✅ +inf and NaN costs are refused; the defect fields stay absent (-1.0)")
    else:
        failed += 1
        print("  ❌ non-finite cost accepted:", inf_solved.status, nan_solved.status)

    # ── shape: the wrapping multiply, and the fixed generated-suite arguments ─
    # `3 * 6148914691236517206 == 2`, so a `rows * cols == len(cost)` guard would pass this
    # and then read far past the end of a two-element list. The ceiling catches it first
    # and says which of the two things is wrong.
    var wrapped = assignment_solve(_floats(1.0, 2.0), 3, 6148914691236517206)
    var mismatched = assignment_solve(_floats(1.0, 2.0, 3.0, 4.0, 5.0), 2, 3)
    var negative_dim = assignment_solve(List[Float64](), -1, 2)
    if (
        wrapped.status == ASSIGN_ERR_DIMENSION_TOO_LARGE
        and _is_rejection(wrapped)
        and mismatched.status == ASSIGN_ERR_SHAPE
        and negative_dim.status == ASSIGN_ERR_SHAPE
        and assign_status_name(wrapped.status) == "dimension_too_large"
    ):
        passed += 1
        print("  ✅ the wrapping 64-bit product and a mismatched shape are both refused")
    else:
        failed += 1
        print("  ❌ shape guards wrong:", wrapped.status, mismatched.status, negative_dim.status)

    # ── every public driver refuses the five-element / five-integer pattern ───
    # A contract function is called with `_lf5`, `_li5`, `_lb5` and 5 for every Int, and an
    # unguarded `rows`/`cols` would index cost[24] on a 5-element list — an uncatchable
    # process crash that takes the worker down.
    var r1 = assignment_solve(_lf5(), 5, 5)
    var r2 = assignment_solve_masked(_lf5(), 5, 5, _lb5())
    var r3 = greedy_assignment_flat(_lf5(), 5, 5)
    var r4 = assignment_cost_of(_lf5(), 5, 5, _li5())
    var r5 = assignment_dual_check(_lf5(), 5, 5, _li5(), _lf5(), _lf5())
    var r6 = assignment_dual_check_masked(
        _lf5(), 5, 5, _li5(), _lf5(), _lf5(), _lb5()
    )
    if (
        r1.status == ASSIGN_ERR_SHAPE
        and r2.status == ASSIGN_ERR_SHAPE
        and r3.status == ASSIGN_ERR_SHAPE
        and r4.status == ASSIGN_ERR_SHAPE
        and r5.status == ASSIGN_ERR_SHAPE
        and r6.status == ASSIGN_ERR_SHAPE
        and r5.max_dual_violation == ASSIGN_DEFECT_ABSENT
    ):
        passed += 1
        print("  ✅ all six drivers refuse (5-element list, 5, 5) instead of indexing")
    else:
        failed += 1
        print(
            "  ❌ a driver accepted the generated argument pattern:",
            r1.status,
            r2.status,
            r3.status,
            r4.status,
            r5.status,
            r6.status,
        )

    # ── scoring somebody else's assignment ───────────────────────────────────
    var round_trip = assignment_cost_of(rank_one, 3, 3, solved.col_of_row)
    var partial = assignment_cost_of(rank_one, 3, 3, _ints(0, ASSIGN_NONE, ASSIGN_NONE))
    var duplicated = assignment_cost_of(rank_one, 3, 3, _ints(0, 0, 1))
    var out_of_range = assignment_cost_of(rank_one, 3, 3, _ints(3, 0, 1))
    var short_list = assignment_cost_of(rank_one, 3, 3, _ints(0, 1))
    if (
        round_trip.status == ASSIGN_OK
        and round_trip.perfect
        and round_trip.total_cost == solved.total_cost
        and partial.status == ASSIGN_OK
        and not partial.perfect
        and partial.has_cost
        and partial.total_cost == 1.0
        and partial.n_assigned == 1
        and duplicated.status == ASSIGN_ERR_DUPLICATE
        and out_of_range.status == ASSIGN_ERR_INDEX
        and short_list.status == ASSIGN_ERR_LENGTH_MISMATCH
    ):
        passed += 1
        print("  ✅ cost_of: round-trips the optimum, and a partial one is not `perfect`")
    else:
        failed += 1
        print(
            "  ❌ cost_of wrong:",
            round_trip.total_cost,
            partial.perfect,
            duplicated.status,
            out_of_range.status,
            short_list.status,
        )

    # ── a supplied dual that is not finite, and a mismatched dual length ──────
    var nan_dual = assignment_dual_check(
        rank_one, 3, 3, solved.col_of_row, _floats(nan_value, 0.0, 0.0), solved.v
    )
    var short_dual = assignment_dual_check(
        rank_one, 3, 3, solved.col_of_row, _floats(0.0, 0.0), solved.v
    )
    if (
        nan_dual.status == ASSIGN_ERR_NON_FINITE_DUAL
        and not nan_dual.certified
        and nan_dual.max_dual_violation == ASSIGN_DEFECT_ABSENT
        and short_dual.status == ASSIGN_ERR_LENGTH_MISMATCH
        and assign_status_name(nan_dual.status) == "non_finite_dual"
    ):
        passed += 1
        print("  ✅ a NaN potential and a short potential vector are both refused")
    else:
        failed += 1
        print("  ❌ dual guards wrong:", nan_dual.status, short_dual.status)

    # ── every status has its own name ────────────────────────────────────────
    var codes = _ints(
        ASSIGN_OK,
        ASSIGN_ERR_SHAPE,
        ASSIGN_ERR_DIMENSION_TOO_LARGE,
        ASSIGN_ERR_LENGTH_MISMATCH,
        ASSIGN_ERR_NON_FINITE_COST,
        ASSIGN_ERR_FEWER_AGENTS_THAN_TASKS,
        ASSIGN_ERR_NO_PERFECT_MATCHING,
        ASSIGN_ERR_INDEX,
        ASSIGN_ERR_DUPLICATE,
        ASSIGN_ERR_OVERFLOW,
        ASSIGN_ERR_ITERATION_LIMIT,
        ASSIGN_ERR_CERTIFICATE,
        ASSIGN_ERR_BOUND_VIOLATED,
        ASSIGN_ERR_NON_FINITE_DUAL,
    )
    var names_distinct = True
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            if assign_status_name(codes[i]) == assign_status_name(codes[j]):
                names_distinct = False
    if (
        names_distinct
        and len(codes) == 14
        and assign_status_name(ASSIGN_ERR_CERTIFICATE) == "dual_certificate_failed"
        and assign_status_name(ASSIGN_ERR_BOUND_VIOLATED) == "greedy_bound_beats_result"
        and assign_status_name(ASSIGN_ERR_ITERATION_LIMIT) == "iteration_limit"
        and assign_status_name(ASSIGN_ERR_OVERFLOW) == "cost_overflow"
        and assign_status_name(99) == "unknown_status_99"
    ):
        passed += 1
        print("  ✅ all 14 status codes have distinct names")
    else:
        failed += 1
        print("  ❌ status names collide or are wrong")

    # ── a cost that cannot be totalled is absent, not infinite ───────────────
    # Two cells at 1e308 sum to +inf. The matching exists; its total does not, and a caller
    # handed `inf` would go on to compare it.
    var enormous = _floats(1.0e308, 1.0, 1.0, 1.0e308)
    var enormous_solved = assignment_solve(enormous, 2, 2)
    if (
        enormous_solved.status == ASSIGN_OK
        and enormous_solved.total_cost == 2.0
        and _same_ints(enormous_solved.col_of_row, _ints(1, 0))
    ):
        passed += 1
        print("  ✅ 1e308 cells are real costs, avoided in favour of 1.0 + 1.0")
    else:
        failed += 1
        print("  ❌ 1e308 case wrong:", enormous_solved.status, enormous_solved.total_cost)

    var forced = _floats(1.0e308, 1.0e308, 1.0e308, 1.0e308)
    var forced_solved = assignment_solve(forced, 2, 2)
    if forced_solved.status == ASSIGN_ERR_OVERFLOW and _is_rejection(forced_solved):
        passed += 1
        print("  ✅ a total that overflows is reported, not returned as +inf")
    else:
        failed += 1
        print(
            "  ❌ overflow not reported:",
            forced_solved.status,
            forced_solved.total_cost,
        )

    print("  [optimization.assignment] Passed:", passed, "Failed:", failed)
