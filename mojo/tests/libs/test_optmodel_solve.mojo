"""test_optmodel_solve.mojo — known-value tests for the formulation→solver bridge.

Hand-written; every optimum below is derived on paper (or by exhaustive enumeration
small enough to do by hand) before it is asserted. The one wrong answer this module
exists to prevent is a NUMBER REPORTED WITHOUT ITS PROOF, so every positive assertion
here has a refusal twin: the same program with less budget, a conflicting row, or an
unbounded direction, asserted to land in its own typed refusal with `has_objective`
False.

  * The production LP `max 3x + 2y, x+y<=4, x+3y<=6` solves to 12 at (4,0) — solver
    certificate (complementary slackness) and original-space audit both pass.
  * The shifted LP `min 2x + 3y, x+y>=1, x∈[-2,5], y∈[0,5]` solves to 2 at (1,0): on
    the binding line the cost is `3 - x`, so push x up until y hits its floor, then
    slide x down to the row — the answer exercises the negative-lower-bound shift AND
    the answer is asserted in the CALLER's coordinates, not the shifted ones.
  * The Wolsey MILP `max 5x + 8y, x+y<=6, 5x+9y<=45, x,y>=0 integral` — the same
    program `test_optimization_integer.mojo` derives node by node — is 40 at (0,5)
    with room to finish, and a REFUSAL (`refused_search_limit`) at `max_nodes = 3`,
    carrying incumbent 39 and bound 370/9 as diagnostics while claiming NO objective.
    A plane that lets the incumbent through as an answer fails exactly this pair.
  * The knapsack `max 10a + 13b + 7c, 6a + 8b + 5c <= 10, binary` is 13 by
    enumeration: singletons 10/13/7, every pair overweight (11/14/13 > 10). Binaries
    take the boxed-[0,1] wire form.
  * `x <= 2` against `x >= 5` is proven infeasible and the refusal NAMES both rows in
    the core while excluding the innocent `y <= 100`; the same conflict written as a
    DECLARED upper bound (x∈[0,2] vs row x>=5) puts variable 0 in `core_bound_vars`
    instead — the row map back to the caller's vocabulary is the assertion.
  * `2x == 1` over an integer x is integer-infeasible with a feasible relaxation, so
    the refusal is `refused_infeasible` with an EMPTY core — the LP has no conflicting
    subset, and inventing one would be lying about where the infeasibility lives.
  * `max x` with no ceiling anywhere is `refused_unbounded` through the analytic
    no-rows path, and the same shape with a `x <= 3` ROW is 3 through the simplex —
    while `min x` over `x ∈ [-2, ...)` with no rows is -2 through the analytic corner,
    which is what proves the no-rows path returns the CALLER's corner, not 0.
  * A policy no solver could honour (`max_nodes = 0`, `max_iterations = 0`) is refused
    as `MODEL_ERR_POLICY` on BOTH dispatch paths — path-dependent validation is how a
    typo survives until the model grows its first integer variable.
"""
from optimization.integer import MILP_INFEASIBLE, MILP_NODE_LIMIT
from optimization.linear import LP_INFEASIBLE, LP_OPTIMAL, LP_UNBOUNDED
from optimization.model import (
    MODEL_ERR_POLICY,
    MODEL_OK,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    VAR_BINARY,
    VAR_CONTINUOUS,
    VAR_FLAG_BOXED,
    VAR_FLAG_HAS_LOWER,
    VAR_INTEGER,
)
from optmodel.formulation import (
    OPTM_ERR_FREE_VARIABLE,
    OPTM_REFUSED_INFEASIBLE,
    OPTM_REFUSED_SEARCH_LIMIT,
    OPTM_REFUSED_UNBOUNDED,
)
from optmodel.solve import formulation_solve_default, formulation_solve_flat


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


def main() raises:
    var passed = 0
    var failed = 0

    var cont2 = _ints(VAR_CONTINUOUS, VAR_CONTINUOUS)
    var haslow2 = _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER)
    var zeros2 = _floats(0.0, 0.0)

    # ── the production LP: 12 at (4, 0), certified twice ──────────────────────
    var lp = formulation_solve_default(
        2, 2, True, _floats(3.0, 2.0), 0.0, _floats(1.0, 1.0, 1.0, 3.0),
        _ints(SENSE_LE, SENSE_LE), _floats(4.0, 6.0), cont2,
        zeros2, zeros2, haslow2, 100,
    )
    if (
        lp.solved and not lp.refused and lp.status == MODEL_OK
        and lp.underlying_status == LP_OPTIMAL and not lp.is_discrete
        and lp.has_objective and lp.objective == 12.0
        and len(lp.x) == 2 and lp.x[0] == 4.0 and lp.x[1] == 0.0
        and lp.audit_feasible and lp.lowered_rows == 2
    ):
        passed += 1
        print("  ✅ production LP: 12 at (4,0), slackness-certified, audit passed")
    else:
        failed += 1
        print("  ❌ production LP wrong:", lp.status, lp.objective, lp.solved)

    # ── the shifted LP answers in the CALLER's coordinates ────────────────────
    var shifted = formulation_solve_default(
        2, 1, False, _floats(2.0, 3.0), 0.0, _floats(1.0, 1.0), _ints(SENSE_GE),
        _floats(1.0), cont2, _floats(-2.0, 0.0), _floats(5.0, 5.0),
        _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED), 100,
    )
    if (
        shifted.solved and shifted.objective == 2.0
        and shifted.x[0] == 1.0 and shifted.x[1] == 0.0
        and shifted.lowered_rows == 3
    ):
        passed += 1
        print("  ✅ shifted LP: 2 at (1,0) in caller coordinates, 3 lowered rows")
    else:
        failed += 1
        print(
            "  ❌ shifted LP wrong:", shifted.status, shifted.objective,
            len(shifted.x),
        )

    # ── Wolsey: proven 40, and a node limit is a REFUSAL, not a 39 ────────────
    var int2 = _ints(VAR_INTEGER, VAR_INTEGER)
    var wolsey = formulation_solve_default(
        2, 2, True, _floats(5.0, 8.0), 0.0, _floats(1.0, 1.0, 5.0, 9.0),
        _ints(SENSE_LE, SENSE_LE), _floats(6.0, 45.0), int2,
        zeros2, zeros2, haslow2, 500,
    )
    var capped = formulation_solve_default(
        2, 2, True, _floats(5.0, 8.0), 0.0, _floats(1.0, 1.0, 5.0, 9.0),
        _ints(SENSE_LE, SENSE_LE), _floats(6.0, 45.0), int2,
        zeros2, zeros2, haslow2, 3,
    )
    if (
        wolsey.solved and wolsey.is_discrete and wolsey.objective == 40.0
        and wolsey.x[0] == 0.0 and wolsey.x[1] == 5.0 and wolsey.audit_feasible
        and capped.refused and not capped.solved
        and capped.status == OPTM_REFUSED_SEARCH_LIMIT
        and capped.underlying_status == MILP_NODE_LIMIT
        and not capped.has_objective and len(capped.x) == 0
        and capped.has_incumbent and capped.incumbent_objective == 39.0
        and capped.has_bound and _close(capped.best_bound, 370.0 / 9.0, 1e-9)
        and capped.nodes_explored == 3
    ):
        passed += 1
        print("  ✅ Wolsey: proven 40 at (0,5); node-limit run refuses, incumbent 39 is a diagnostic")
    else:
        failed += 1
        print(
            "  ❌ Wolsey pair wrong:", wolsey.objective, capped.status,
            capped.has_objective, capped.incumbent_objective,
        )

    # ── binary knapsack: 13 by enumeration ────────────────────────────────────
    var bin3 = _ints(VAR_BINARY, VAR_BINARY, VAR_BINARY)
    var knap = formulation_solve_default(
        3, 1, True, _floats(10.0, 13.0, 7.0), 0.0, _floats(6.0, 8.0, 5.0),
        _ints(SENSE_LE), _floats(10.0), bin3,
        _floats(0.0, 0.0, 0.0), _floats(1.0, 1.0, 1.0),
        _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED, VAR_FLAG_BOXED), 500,
    )
    if (
        knap.solved and knap.objective == 13.0
        and knap.x[0] == 0.0 and knap.x[1] == 1.0 and knap.x[2] == 0.0
    ):
        passed += 1
        print("  ✅ binary knapsack: 13 by taking item 2 alone")
    else:
        failed += 1
        print("  ❌ knapsack wrong:", knap.status, knap.objective)

    # ── a binary's root-box `<= 1` survives even when its OWN row is omitted ──
    # `max x0 + x1`, both binary, `x0 + x1 <= 5` (slack, never binds): x0's upper is
    # the standard 1 — `formulation_lower_flat` now omits its row as redundant with
    # `milp_solve`'s unconditional root box — while x1 is fixed at 0, whose row is
    # NOT redundant and must stay. The answer is 1 at (1, 0); if the omission logic
    # ever over-reached (dropped x1's row too), x1 could reach 1 and either the
    # self-check catches it (refused, not wrong) or the objective would read 2 — this
    # is the mutation that distinguishes "the redundant row is gone" from
    # "enforcement is gone".
    var bin2 = _ints(VAR_BINARY, VAR_BINARY)
    var redundant_row_omitted = formulation_solve_default(
        2, 1, True, _floats(1.0, 1.0), 0.0, _floats(1.0, 1.0), _ints(SENSE_LE),
        _floats(5.0), bin2, _floats(0.0, 0.0), _floats(1.0, 0.0),
        _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED), 100,
    )
    if (
        redundant_row_omitted.solved and redundant_row_omitted.objective == 1.0
        and redundant_row_omitted.x[0] == 1.0 and redundant_row_omitted.x[1] == 0.0
        and redundant_row_omitted.audit_feasible
    ):
        passed += 1
        print("  ✅ binary root box still caps x0 at 1 with its own row omitted; x1 fixed at 0 holds")
    else:
        failed += 1
        print(
            "  ❌ redundant-row omission broke enforcement:",
            redundant_row_omitted.status, redundant_row_omitted.objective,
        )

    # Mutation: `min x0` with x0 binary FIXED at 1 (`lower == upper == 1.0`) must solve
    # to 1, not 0. `_root_node`'s hardcoded box only ever says `<= 1`, unaware of the
    # shift; a broadened redundancy check (testing `upper == 1.0` alone, forgetting
    # `lower == 0.0`) would skip THIS variable's own row too, and a minimiser would
    # happily drift to the un-forced end of `[0, 1]`.
    var fixed_one = formulation_solve_default(
        1, 1, False, _floats(1.0), 0.0, _floats(1.0), _ints(SENSE_LE), _floats(5.0),
        _ints(VAR_BINARY), _floats(1.0), _floats(1.0), _ints(VAR_FLAG_BOXED), 100,
    )
    if (
        fixed_one.solved and fixed_one.objective == 1.0 and fixed_one.x[0] == 1.0
        and fixed_one.audit_feasible
    ):
        passed += 1
        print("  ✅ a binary fixed at 1 stays at 1 under `min x0` — the shift is honoured")
    else:
        failed += 1
        print("  ❌ binary-fixed-at-1 drifted:", fixed_one.status, fixed_one.objective)

    # ── infeasibility NAMES the conflict, in the caller's vocabulary ──────────
    # Rows: 0: x <= 2, 1: x >= 5, 2: y <= 100. The core is {0, 1}; row 2 is innocent.
    var rows_conflict = formulation_solve_default(
        2, 3, True, _floats(1.0, 0.0), 0.0,
        _floats(1.0, 0.0, 1.0, 0.0, 0.0, 1.0),
        _ints(SENSE_LE, SENSE_GE, SENSE_LE), _floats(2.0, 5.0, 100.0), cont2,
        zeros2, zeros2, haslow2, 100,
    )
    var core_named = (
        rows_conflict.refused
        and rows_conflict.status == OPTM_REFUSED_INFEASIBLE
        and rows_conflict.underlying_status == LP_INFEASIBLE
        and rows_conflict.core_verified
        and rows_conflict.core_size == 2
        and len(rows_conflict.core_constraints) == 2
        and rows_conflict.core_constraints[0] == 0
        and rows_conflict.core_constraints[1] == 1
        and len(rows_conflict.core_bound_vars) == 0
    )
    # The same conflict, but `x <= 2` DECLARED as a bound: the core names variable 0's
    # upper bound and constraint 0 (`x >= 5`), nothing else.
    var bound_conflict = formulation_solve_default(
        2, 2, True, _floats(1.0, 0.0), 0.0, _floats(1.0, 0.0, 0.0, 1.0),
        _ints(SENSE_GE, SENSE_LE), _floats(5.0, 100.0), cont2,
        zeros2, _floats(2.0, 0.0), _ints(VAR_FLAG_BOXED, VAR_FLAG_HAS_LOWER), 100,
    )
    var bound_named = (
        bound_conflict.refused
        and bound_conflict.status == OPTM_REFUSED_INFEASIBLE
        and bound_conflict.core_size == 2
        and len(bound_conflict.core_constraints) == 1
        and bound_conflict.core_constraints[0] == 0
        and len(bound_conflict.core_bound_vars) == 1
        and bound_conflict.core_bound_vars[0] == 0
    )
    # The repaired twin: drop the >= 5 row and the same formulation solves to 2.
    var repaired = formulation_solve_default(
        2, 2, True, _floats(1.0, 0.0), 0.0, _floats(1.0, 0.0, 0.0, 1.0),
        _ints(SENSE_LE, SENSE_LE), _floats(2.0, 100.0), cont2,
        zeros2, zeros2, haslow2, 100,
    )
    if core_named and bound_named and repaired.solved and repaired.objective == 2.0:
        passed += 1
        print("  ✅ infeasible cores name rows {0,1} / bound-of-var-0; repaired twin solves")
    else:
        failed += 1
        print(
            "  ❌ core naming wrong:", rows_conflict.core_size,
            len(rows_conflict.core_constraints), len(bound_conflict.core_bound_vars),
            repaired.status,
        )

    # ── integer-infeasible with a feasible relaxation: refuse with EMPTY core ─
    var half = formulation_solve_default(
        1, 1, False, _floats(1.0), 0.0, _floats(2.0), _ints(SENSE_EQ), _floats(1.0),
        _ints(VAR_INTEGER), _floats(0.0), _floats(0.0), _ints(VAR_FLAG_HAS_LOWER), 100,
    )
    if (
        half.refused and half.status == OPTM_REFUSED_INFEASIBLE
        and half.underlying_status == MILP_INFEASIBLE
        and half.core_size == 0 and len(half.core_constraints) == 0
        and not half.has_objective
    ):
        passed += 1
        print("  ✅ 2x == 1 over integers refuses with an EMPTY core — the LP is innocent")
    else:
        failed += 1
        print("  ❌ integer infeasibility wrong:", half.status, half.core_size)

    # ── unbounded: analytic no-rows path and the simplex path agree on the type ─
    var unbounded_free = formulation_solve_default(
        1, 0, True, _floats(1.0), 0.0, _floats(), _ints(), _floats(),
        _ints(VAR_CONTINUOUS), _floats(0.0), _floats(0.0), _ints(VAR_FLAG_HAS_LOWER), 100,
    )
    var unbounded_row = formulation_solve_default(
        2, 1, True, _floats(1.0, 1.0), 0.0, _floats(1.0, -1.0), _ints(SENSE_LE),
        _floats(1.0), cont2, zeros2, zeros2, haslow2, 100,
    )
    var corner = formulation_solve_default(
        1, 0, False, _floats(1.0), 0.0, _floats(), _ints(), _floats(),
        _ints(VAR_INTEGER), _floats(-2.0), _floats(0.0), _ints(VAR_FLAG_HAS_LOWER), 100,
    )
    var ceiling_row = formulation_solve_default(
        1, 1, True, _floats(1.0), 0.0, _floats(1.0), _ints(SENSE_LE), _floats(3.0),
        _ints(VAR_CONTINUOUS), _floats(0.0), _floats(0.0), _ints(VAR_FLAG_HAS_LOWER), 100,
    )
    if (
        unbounded_free.refused and unbounded_free.status == OPTM_REFUSED_UNBOUNDED
        and unbounded_free.underlying_status == LP_UNBOUNDED
        and unbounded_row.refused and unbounded_row.status == OPTM_REFUSED_UNBOUNDED
        and unbounded_row.underlying_status == LP_UNBOUNDED
        and corner.solved and corner.objective == -2.0 and corner.x[0] == -2.0
        and ceiling_row.solved and ceiling_row.objective == 3.0
    ):
        passed += 1
        print("  ✅ unbounded refuses on both paths; the analytic corner is the CALLER's -2")
    else:
        failed += 1
        print(
            "  ❌ unbounded/corner wrong:", unbounded_free.status,
            unbounded_row.status, corner.objective, ceiling_row.objective,
        )

    # ── policy defects refuse on BOTH dispatch paths ──────────────────────────
    var zero_nodes_lp = formulation_solve_default(
        1, 1, True, _floats(1.0), 0.0, _floats(1.0), _ints(SENSE_LE), _floats(3.0),
        _ints(VAR_CONTINUOUS), _floats(0.0), _floats(0.0), _ints(VAR_FLAG_HAS_LOWER), 0,
    )
    var zero_iterations = formulation_solve_flat(
        1, 1, True, _floats(1.0), 0.0, _floats(1.0), _ints(SENSE_LE), _floats(3.0),
        _ints(VAR_INTEGER), _floats(0.0), _floats(0.0), _ints(VAR_FLAG_HAS_LOWER),
        100, 0, 1e-9, 1e-9, 1e-9,
    )
    var free_var = formulation_solve_default(
        1, 1, True, _floats(1.0), 0.0, _floats(1.0), _ints(SENSE_LE), _floats(3.0),
        _ints(VAR_CONTINUOUS), _floats(0.0), _floats(0.0), _ints(0), 100,
    )
    if (
        zero_nodes_lp.refused and zero_nodes_lp.status == MODEL_ERR_POLICY
        and zero_iterations.refused and zero_iterations.status == MODEL_ERR_POLICY
        and free_var.refused and free_var.status == OPTM_ERR_FREE_VARIABLE
        and not free_var.has_objective
    ):
        passed += 1
        print("  ✅ zero nodes, zero iterations and a free variable each refuse, typed")
    else:
        failed += 1
        print(
            "  ❌ policy refusals wrong:", zero_nodes_lp.status,
            zero_iterations.status, free_var.status,
        )

    # ── the generated A–Z suite's fixed shape must refuse, never crash ────────
    # Every contract function is called with 5-element lists and every Int as 5, so
    # `a` arrives 5 long against a declared 5x5. The only acceptable outcome is a
    # typed refusal — an index into a[24] here would abort the whole worker.
    var az = formulation_solve_flat(
        5, 5, True, _floats(0.5, 0.5, 0.5, 0.5, 0.5), 0.5,
        _floats(0.5, 0.5, 0.5, 0.5, 0.5), _ints(5, 5, 5, 5, 5),
        _floats(0.5, 0.5, 0.5, 0.5, 0.5), _ints(5, 5, 5, 5, 5),
        _floats(0.5, 0.5, 0.5, 0.5, 0.5), _floats(0.5, 0.5, 0.5, 0.5, 0.5),
        _ints(5, 5, 5, 5, 5), 5, 5, 0.5, 0.5, 0.5,
    )
    if az.refused and not az.solved and not az.has_objective:
        passed += 1
        print("  ✅ the A–Z fixed shape (5-lists, Ints of 5) refuses instead of indexing")
    else:
        failed += 1
        print("  ❌ A–Z shape not refused:", az.status, az.solved)

    print("  [optmodel.solve] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("optmodel.solve suite failed")
