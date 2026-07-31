"""test_optimization_explain.mojo — known-value tests for the explanation surface.

Hand-written, and every number below was derived by hand before it was run. The assertions
target the ways an explanation can be plausible and wrong:

  * the shadow prices are pinned to hand-differentiated values, not just to "nonzero on the
    tight rows". `min 2x + 3y` under `x + y == 10`, `x <= 6`, `y >= 1` has duals
    `(3, -1, 0)`: raising the equality's right-hand side by one forces another unit of the
    expensive variable (+3) while raising the capacity by one substitutes a cheap unit for an
    expensive one (-1), and the slack row is worth nothing. A report that got the SIGN
    convention wrong, or that reported magnitudes without direction, fails here and passes a
    "duals are nonnegative on binding rows" check;
  * complementary slackness is asserted in both directions — a LOOSE row that carries a price,
    and a row FLAGGED tight whose measured slack is five units of room and whose dual is
    nonzero anyway. The second is the one an audit of the first direction alone passes, and it
    is a defect worth `|dual| * slack` in the duality gap. It is asserted alongside the two
    pairs that must NOT fire: a tight row priced at zero (degeneracy — a checker that flags it
    rejects any model with a duplicated row) and a tight row whose slack is 4e-13 of pivot
    rounding rather than room;
  * a nan or an inf anywhere in the audited pair — a dual, a slack, or the `dual_tol` a caller
    passes — comes back as a status and never as `complementary`. nan satisfies no comparison,
    so `|nan| > dual_tol` and `|y_i| > nan` are both False and an unvalidated audit counts
    zero violations and PASSES; the assertion pins that the one validated entry point is the
    only audit there is, and `binding_constraints`'s own report is replayed through it to pin
    that it goes through the same door;
  * the core is asserted to be EXACTLY the contradictory pair `x >= 5` / `x <= 3` out of four
    rows, with the two innocent rows asserted absent — a superset core is the easy wrong
    answer, and it would pass a "the core is infeasible" check on its own;
  * minimality is asserted together with `minimality_verified` and the SOLVE COUNT
    (`1 + m + 1 + |core|` = 8), because a claim of minimality is only worth the solves that
    were actually spent testing it;
  * the frozen `linear_programming.lp_solve_2var` is a differential oracle for one step of
    the deletion filter: it enumerates vertices instead of pivoting, and it independently
    finds a feasible point for the core minus `x >= 5`, which is exactly the fact the filter
    used to declare that row necessary;
  * `model_evaluate` and `model_objective` are differential oracles for the model-level
    entry points: they walk the constraint and objective ARENAS one node at a time, where
    the report goes through the extracted `c` and dense `A`, so agreement on the activity
    vector and the objective is agreement between two different routes;
  * an infeasible model whose `Σ|b_i|` is LARGE still produces a core: 200 rows of
    `x0 <= 1e7` beside the contradictory pair `x1 >= 3` / `x1 <= 2` is infeasible by one unit
    against a right-hand-side scale of 2e9, and a phase-1 threshold taken relative to that
    scale swallows the residual and reports the model optimal. From this side that arrives as
    `feasible_so_there_is_no_infeasibility_core` with `is_infeasible = False` — a wrong answer
    with a success-shaped status, on a model whose only defect is its units;
  * a feasible model returns an EMPTY core after one solve, an empty constraint system is
    answered without one, `x <= -5` cores to a single row because `x >= 0` is the variable
    convention and is not deletable, an unbounded and an infeasible program return no
    binding set at all, and the generated-suite argument pattern
    (`_lf5` / `_li5` / 5) is refused by every flat entry point — including the wrapping
    multiply `3 * 6148914691236517206 == 2`, which is a legal-looking dense shape and an
    uncatchable crash if the check is not a division.

Exact equality is used wherever the arithmetic is exact in binary floating point: the
vertices, the duals, the itemised contributions, the residual, and the phase-1 residual of
the contradictory pair (`x` can reach 3 and needs 5, so the measured infeasibility is
exactly 2). A tolerance appears only where a genuine division rounds, in the objective
shares 10/13 and 3/13.
"""
from std.math import inf, nan

from linear_programming import lp_solve_2var
from query.ir import OP_MUL, OP_VAR_REF
from optimization.explain import (
    EXPLAIN_ERR_BOUNDS_NOT_ROWS,
    EXPLAIN_ERR_COMPLEMENTARY_SLACKNESS,
    EXPLAIN_ERR_CORE_UNVERIFIED,
    EXPLAIN_ERR_DISCRETE_VARIABLE,
    EXPLAIN_ERR_DUALITY_GAP,
    EXPLAIN_ERR_SUM_MISMATCH,
    EXPLAIN_FEASIBLE_NO_CORE,
    EXPLAIN_GAP_ABSENT,
    EXPLAIN_MAX_CORE_ROWS,
    EXPLAIN_OK,
    binding_constraints,
    binding_constraints_default,
    explain_status_name,
    infeasibility_core,
    infeasibility_core_default,
    model_binding_constraints,
    model_contributions,
    model_infeasibility_core,
    objective_contributions,
    optimum_contributions,
    optimum_contributions_default,
    slackness_check,
)
from optimization.linear import (
    LIN_ERR_NONLINEAR_PRODUCT,
    LP_INFEASIBLE,
    LP_UNBOUNDED,
)
from optimization.model import (
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_DIMENSION_TOO_LARGE,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_ERR_NON_FINITE_VALUE,
    MODEL_ERR_POLICY,
    MODEL_OK,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    VAR_CONTINUOUS,
    VAR_FLAG_BOXED,
    VAR_FLAG_HAS_LOWER,
    VAR_INTEGER,
    linear_model_flat,
    model_evaluate,
    model_objective,
)


fn _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _bools(*vals: Bool) -> List[Bool]:
    var out = List[Bool]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d <= tol


fn _all_close(a: List[Float64], b: List[Float64], tol: Float64) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not _close(a[i], b[i], tol):
            return False
    return True


fn _exact(a: List[Float64], b: List[Float64]) -> Bool:
    """Exact equality, used only where every value is a small integer or a dyadic fraction."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _exact_ints(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _exact_bools(a: List[Bool], b: List[Bool]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


# ── the three-variable program, hand-solved ───────────────────────────────────
# maximise  5x1 + 4x2 + 3x3
#   2x1 + 3x2 +  x3 <=  5     (binds: 2*2 + 1 = 5)
#   4x1 +  x2 + 2x3 <= 11     (activity 10, slack 1, so its dual must be 0)
#   3x1 + 4x2 + 2x3 <=  8     (binds: 3*2 + 2 = 8)          x >= 0
# Optimum 13 at x = (2, 0, 1); duals (1, 0, 1); bᵀy = 5 + 0 + 8 = 13 = the primal optimum.
# Contributions 5*2 = 10, 4*0 = 0, 3*1 = 3, summing to 13 with a zero residual.


fn _c3() -> List[Float64]:
    return _floats(5.0, 4.0, 3.0)


fn _a3() -> List[Float64]:
    return _floats(2.0, 3.0, 1.0, 4.0, 1.0, 2.0, 3.0, 4.0, 2.0)


fn _b3() -> List[Float64]:
    return _floats(5.0, 11.0, 8.0)


fn _le3() -> List[Int]:
    return _ints(SENSE_LE, SENSE_LE, SENSE_LE)


# ── the infeasible four-row model, with a known contradictory PAIR ────────────
# variables x, y >= 0
#   row 0:  x + y <= 10      innocent
#   row 1:      x >=  5      \  contradictory pair: 5 <= x <= 3 is empty
#   row 2:      y <=  4      innocent
#   row 3:      x <=  3      /
# The core is {1, 3} and nothing else. Phase 1 over that pair minimises the single
# artificial of the `>=` row: x can reach 3, needs 5, so the measured infeasibility is
# exactly 2.


fn _a_inf() -> List[Float64]:
    return _floats(1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0)


fn _senses_inf() -> List[Int]:
    return _ints(SENSE_LE, SENSE_GE, SENSE_LE, SENSE_LE)


fn _rhs_inf() -> List[Float64]:
    return _floats(10.0, 5.0, 4.0, 3.0)


fn _zeros(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(n):
        out.append(0.0)
    return out^


fn _repeat_int(value: Int, n: Int) -> List[Int]:
    var out = List[Int]()
    for _ in range(n):
        out.append(value)
    return out^


fn main() raises:
    var passed = 0
    var failed = 0

    var _lf5 = _floats(0.5, 0.5, 0.5, 0.5, 0.5)
    var _li5 = _ints(5, 5, 5, 5, 5)

    # ── one binding row and one slack row, the smallest honest case ───────────
    # maximise x subject to x <= 4 and x <= 10. The first binds and is worth 1 per unit;
    # the second has six units of room and must be worth exactly 0. A report that priced
    # both, or that called both binding, is the failure this asserts against.
    var pair = binding_constraints_default(
        _floats(1.0), _floats(1.0, 1.0), 2, 1, _ints(SENSE_LE, SENSE_LE),
        _floats(4.0, 10.0), True,
    )
    if (
        pair.status == EXPLAIN_OK
        and pair.has_objective
        and pair.objective == 4.0
        and _exact(pair.x, _floats(4.0))
        and _exact(pair.duals, _floats(1.0, 0.0))
        and _exact(pair.slack, _floats(0.0, 6.0))
        and _exact(pair.activity, _floats(4.0, 4.0))
        and _exact_bools(pair.binding, _bools(True, False))
        and pair.n_binding == 1
        and pair.n_degenerate == 0
        and _exact_ints(pair.binding_rows, _ints(0))
        and _exact(pair.binding_duals, _floats(1.0))
        and _exact_ints(pair.binding_senses, _ints(SENSE_LE))
        and _exact(pair.binding_rhs, _floats(4.0))
        and pair.complementary
        and pair.cs_row == -1
        and pair.cs_gap == 0.0
        and pair.strong_duality
        and pair.dual_objective == 4.0
        and pair.duality_gap == 0.0
    ):
        passed += 1
        print("  ✅ the tight row is priced at 1 and the row with room is priced at 0")
    else:
        failed += 1
        print(
            "  ❌ binding/slack pair wrong:",
            pair.status,
            pair.objective,
            pair.n_binding,
            len(pair.duals),
        )

    # ── three variables: two binding rows, one with slack, hand-computed duals ─
    var three = binding_constraints_default(_c3(), _a3(), 3, 3, _le3(), _b3(), True)
    if (
        three.status == EXPLAIN_OK
        and three.objective == 13.0
        and _all_close(three.x, _floats(2.0, 0.0, 1.0), 1e-9)
        and _all_close(three.duals, _floats(1.0, 0.0, 1.0), 1e-9)
        and _all_close(three.slack, _floats(0.0, 1.0, 0.0), 1e-9)
        and _exact_bools(three.binding, _bools(True, False, True))
        and three.n_binding == 2
        and _exact_ints(three.binding_rows, _ints(0, 2))
        and _all_close(three.binding_duals, _floats(1.0, 1.0), 1e-9)
        and _all_close(three.binding_rhs, _floats(5.0, 8.0), 1e-12)
        and three.complementary
        and three.strong_duality
        and _close(three.dual_objective, 13.0, 1e-9)
        and three.n_vars == 3
        and three.n_constraints == 3
    ):
        passed += 1
        print("  ✅ the 3-var binding set, shadow prices and both certificates hold")
    else:
        failed += 1
        print(
            "  ❌ 3-var report wrong:",
            three.status,
            three.objective,
            three.n_binding,
            three.dual_objective,
        )

    # ── an equality row and a `>=` row, where the shadow price is NEGATIVE ────
    # minimise 2x + 3y  s.t.  x + y == 10,  x <= 6,  y >= 1,  x, y >= 0.
    # x is the cheap variable so it goes to its cap: x = 6, y = 4, objective 12 + 12 = 24.
    # Raising the equality to 11 forces another unit of y: dual 0 = +3. Raising the cap to 7
    # swaps a unit of y for a unit of x: 14 + 9 = 23, so dual 1 = -1. y = 4 is nowhere near
    # its floor of 1, so dual 2 = 0. bᵀy = 30 - 6 + 0 = 24 = the primal optimum.
    var mixed = binding_constraints_default(
        _floats(2.0, 3.0), _floats(1.0, 1.0, 1.0, 0.0, 0.0, 1.0), 3, 2,
        _ints(SENSE_EQ, SENSE_LE, SENSE_GE), _floats(10.0, 6.0, 1.0), False,
    )
    if (
        mixed.status == EXPLAIN_OK
        and mixed.objective == 24.0
        and _exact(mixed.x, _floats(6.0, 4.0))
        and _exact(mixed.duals, _floats(3.0, -1.0, 0.0))
        and _exact(mixed.slack, _floats(0.0, 0.0, 3.0))
        and _exact_bools(mixed.binding, _bools(True, True, False))
        and mixed.n_binding == 2
        and _exact_ints(mixed.binding_rows, _ints(0, 1))
        and _exact(mixed.binding_duals, _floats(3.0, -1.0))
        and _exact_ints(mixed.binding_senses, _ints(SENSE_EQ, SENSE_LE))
        and mixed.complementary
        and mixed.strong_duality
        and _close(mixed.dual_objective, 24.0, 1e-9)
        and mixed.n_degenerate == 0
    ):
        passed += 1
        print("  ✅ a capacity row's shadow price is -1 and the slack floor's is 0")
    else:
        failed += 1
        print(
            "  ❌ mixed-sense duals wrong:",
            mixed.status,
            mixed.objective,
            len(mixed.duals),
            mixed.dual_objective,
        )

    # ── complementary slackness, both directions, on hand-made pairs ──────────
    # A solver bug cannot be summoned on demand, so the detector is driven directly. Row 1
    # has five units of room and a price of 0.5: the product 2.5 is the term it contributes
    # to the duality gap, which is why that is the reported magnitude.
    var broken = slackness_check(
        _floats(1.0, 0.5), _floats(0.0, 5.0), _bools(True, False), 1e-6
    )
    var honest = slackness_check(
        _floats(1.0, 0.0), _floats(0.0, 5.0), _bools(True, False), 1e-6
    )
    # A BINDING row priced at zero is degeneracy, not a contradiction. A checker that flags
    # it rejects any model with a duplicated row, so this asserts it does not.
    var degenerate = slackness_check(
        _floats(0.0, 0.0), _floats(0.0, 5.0), _bools(True, False), 1e-6
    )
    var ragged = slackness_check(
        _floats(1.0, 0.0), _floats(0.0, 5.0, 1.0), _bools(True, False), 1e-6
    )
    if (
        broken.status == EXPLAIN_ERR_COMPLEMENTARY_SLACKNESS
        and not broken.complementary
        and broken.cs_row == 1
        and broken.cs_gap == 2.5
        and broken.n_binding == 1
        and broken.n_degenerate == 0
        and honest.status == EXPLAIN_OK
        and honest.complementary
        and honest.cs_row == -1
        and honest.cs_gap == 0.0
        and degenerate.status == EXPLAIN_OK
        and degenerate.complementary
        and degenerate.n_degenerate == 1
        and degenerate.n_binding == 1
        and ragged.status == MODEL_ERR_LENGTH_MISMATCH
        and not ragged.complementary
        and ragged.cs_gap == EXPLAIN_GAP_ABSENT
    ):
        passed += 1
        print("  ✅ a priced slack row is a violation; a tight row priced at 0 is not")
    else:
        failed += 1
        print(
            "  ❌ slackness audit wrong:",
            broken.status,
            broken.cs_row,
            broken.cs_gap,
            degenerate.n_degenerate,
            ragged.status,
        )

    # ── the OTHER direction: a priced row whose SLACK says it is not tight ────
    # Complementary slackness is two conditions. Over one exact quantity they are
    # contrapositives, but this audit is handed a `binding` FLAG and a `slack` VECTOR as
    # separate inputs, so they can disagree. Row 1 below is flagged tight and still has five
    # units of room at a price of 0.5: it satisfies "no LOOSE row is priced" and puts 2.5 into
    # the duality gap. An audit of the loose direction alone returns `complementary` here and
    # hands the caller shadow prices of a program its own solution does not solve.
    var mislabelled = slackness_check(
        _floats(1.0, 0.5), _floats(0.0, 5.0), _bools(True, True), 1e-6
    )
    # The same flags with a zero dual on the roomy row claim nothing about it, so there is
    # nothing to contradict: it is degeneracy, counted and not flagged.
    var mislabelled_unpriced = slackness_check(
        _floats(1.0, 0.0), _floats(0.0, 5.0), _bools(True, True), 1e-6
    )
    # And the direction must not fire on pivot ROUNDING: 4e-13 of slack on a row priced at 1
    # is a product of 4e-13, far under a threshold scaled to the data. A checker that used the
    # solver's own 1e-9 here would report every tight row as a contradiction.
    var noisy = slackness_check(
        _floats(1.0, 1.0), _floats(0.0, 4e-13), _bools(True, True), 1e-6
    )
    if (
        mislabelled.status == EXPLAIN_ERR_COMPLEMENTARY_SLACKNESS
        and not mislabelled.complementary
        and mislabelled.cs_row == 1
        and mislabelled.cs_gap == 2.5
        and mislabelled.n_binding == 2
        and mislabelled.n_degenerate == 0
        and mislabelled_unpriced.status == EXPLAIN_OK
        and mislabelled_unpriced.complementary
        and mislabelled_unpriced.n_binding == 2
        and mislabelled_unpriced.n_degenerate == 1
        and mislabelled_unpriced.cs_row == -1
        and noisy.status == EXPLAIN_OK
        and noisy.complementary
        and noisy.n_binding == 2
        and noisy.n_degenerate == 0
        and noisy.cs_gap == 0.0
    ):
        passed += 1
        print("  ✅ a priced row with measured room fails the audit even when flagged tight")
    else:
        failed += 1
        print(
            "  ❌ second slackness direction wrong:",
            mislabelled.status,
            mislabelled.cs_row,
            mislabelled.cs_gap,
            mislabelled_unpriced.status,
            noisy.status,
        )

    # ── a nan cannot satisfy the certificate ──────────────────────────────────
    # nan compares False against everything, so an audit that trusts its input finds
    # `|nan| > dual_tol` False, counts ZERO violations and returns `complementary` — a passing
    # certificate over numbers it never read. An inf does it from the other end: it makes the
    # tolerance infinite and then no dual is priced at all. Neither is an answer.
    var nan64 = nan[DType.float64]()
    var inf64 = inf[DType.float64]()
    var nan_dual = slackness_check(
        _floats(1.0, nan64), _floats(0.0, 5.0), _bools(True, False), 1e-6
    )
    var nan_slack = slackness_check(
        _floats(1.0, 0.5), _floats(0.0, nan64), _bools(True, False), 1e-6
    )
    var inf_dual = slackness_check(
        _floats(1.0, inf64), _floats(0.0, 5.0), _bools(True, False), 1e-6
    )
    # The third way in is the THRESHOLD, which is why it is validated too: a nan `dual_tol`
    # disables every comparison at once, and `binding_constraints` derives its own threshold
    # as `EXPLAIN_CERT_SLOP * (1 + max|dual|)` from the very duals it is auditing.
    var nan_tol = slackness_check(
        _floats(1.0, 0.5), _floats(0.0, 5.0), _bools(True, False), nan64
    )
    # `binding_constraints` goes through this same door: its report on the 3-var program is
    # replayed here through the public entry point with the tolerance the function derives
    # (max|dual| = 1), and every audited field matches. Two audits is how one of them ends up
    # without the finiteness check.
    var replayed = slackness_check(
        three.duals, three.slack, three.binding, 1e-6 * (1.0 + 1.0)
    )
    if (
        nan_dual.status == MODEL_ERR_NON_FINITE_VALUE
        and not nan_dual.complementary
        and nan_dual.cs_row == 1
        and nan_dual.cs_gap == EXPLAIN_GAP_ABSENT
        and nan_dual.n_binding == 0
        and nan_slack.status == MODEL_ERR_NON_FINITE_VALUE
        and not nan_slack.complementary
        and nan_slack.cs_row == 1
        and inf_dual.status == MODEL_ERR_NON_FINITE_VALUE
        and not inf_dual.complementary
        and nan_tol.status == MODEL_ERR_POLICY
        and not nan_tol.complementary
        and nan_tol.cs_gap == EXPLAIN_GAP_ABSENT
        and replayed.status == three.status
        and replayed.complementary == three.complementary
        and replayed.n_binding == three.n_binding
        and replayed.n_degenerate == three.n_degenerate
        and replayed.cs_row == three.cs_row
        and replayed.cs_gap == three.cs_gap
    ):
        passed += 1
        print("  ✅ a nan dual, slack or tolerance is a status, never a passed certificate")
    else:
        failed += 1
        print(
            "  ❌ non-finite audit input wrong:",
            nan_dual.status,
            nan_dual.complementary,
            nan_slack.status,
            nan_tol.status,
            replayed.cs_gap,
        )

    # ── the infeasibility core is EXACTLY the contradictory pair ──────────────
    var core = infeasibility_core_default(_a_inf(), 4, 2, _senses_inf(), _rhs_inf())
    if (
        core.status == EXPLAIN_OK
        and core.is_infeasible
        and core.core_verified
        and core.core_size == 2
        and _exact_ints(core.core, _ints(1, 3))
        and _exact_bools(core.in_core, _bools(False, True, False, True))
        and _exact_ints(core.core_senses, _ints(SENSE_GE, SENSE_LE))
        and _exact(core.core_rhs, _floats(5.0, 3.0))
        and core.minimal
        and core.minimality_verified
        and _exact_bools(core.necessary, _bools(True, True))
        and core.n_inconclusive == 0
        and core.n_constraints == 4
        # 1 full solve + 4 deletion trials + 1 confirmation of the core + 2 necessity
        # probes. The count is asserted because a minimality claim is worth exactly the
        # solves that were spent testing it.
        and core.n_solves == 8
        and core.infeasibility == 2.0
        and core.core_infeasibility == 2.0
    ):
        passed += 1
        print("  ✅ the core is exactly {x >= 5, x <= 3}, verified minimal, in 8 solves")
    else:
        failed += 1
        print(
            "  ❌ core wrong:",
            core.status,
            core.core_size,
            core.n_solves,
            core.minimal,
            core.infeasibility,
        )

    # ── the frozen vertex enumerator as an independent oracle on one step ─────
    # The filter kept row 1 because dropping it left {x + y <= 10, y <= 4, x <= 3}
    # FEASIBLE. `lp_solve_2var` reaches that conclusion by enumerating pairwise line
    # intersections instead of pivoting, and it returns [x, y, objective] — nonempty means
    # a feasible point exists. Different algorithm, same fact.
    var oracle_rows = List[List[Float64]]()
    oracle_rows.append(_floats(1.0, 1.0))
    oracle_rows.append(_floats(0.0, 1.0))
    oracle_rows.append(_floats(1.0, 0.0))
    var oracle = lp_solve_2var(_floats(1.0, 1.0), oracle_rows, _floats(10.0, 4.0, 3.0))
    if (
        len(oracle) == 3
        and _close(oracle[2], 7.0, 1e-9)
        and core.in_core[1]
        and core.necessary[0]
        and not core.in_core[0]
        and not core.in_core[2]
    ):
        passed += 1
        print("  ✅ the frozen enumerator confirms the dropped rows were droppable")
    else:
        failed += 1
        print("  ❌ oracle disagreement:", len(oracle), core.in_core[1], core.core_size)

    # ── a feasible model has NO core, and says so after one solve ─────────────
    var no_core = infeasibility_core_default(_a3(), 3, 3, _le3(), _b3())
    if (
        no_core.status == EXPLAIN_FEASIBLE_NO_CORE
        and not no_core.is_infeasible
        and not no_core.core_verified
        and no_core.core_size == 0
        and len(no_core.core) == 0
        and len(no_core.necessary) == 0
        # `minimal` is a claim, and there is nothing here to claim it about.
        and not no_core.minimal
        and not no_core.minimality_verified
        and no_core.n_solves == 1
        and no_core.infeasibility == 0.0
        and no_core.core_infeasibility == EXPLAIN_GAP_ABSENT
        and explain_status_name(no_core.status)
        == "feasible_so_there_is_no_infeasibility_core"
    ):
        passed += 1
        print("  ✅ a feasible model returns an empty core rather than inventing one")
    else:
        failed += 1
        print(
            "  ❌ feasible-model core wrong:",
            no_core.status,
            no_core.core_size,
            no_core.n_solves,
            no_core.infeasibility,
        )

    # ── an infeasible model with a LARGE right-hand-side scale still cores ────
    # 200 copies of `x0 <= 1e7`, then the contradictory pair `x1 >= 3` / `x1 <= 2`. The model
    # is infeasible by exactly one unit — x1 can reach 2 and needs 3 — while `Σ|b_i|` is 2e9.
    # A phase-1 verdict that compares the measured residual against a threshold taken relative
    # to that scale (1e-9 * 2e9 = 2) swallows a residual of 1 and reports the model OPTIMAL,
    # and from this side that arrives as EXPLAIN_FEASIBLE_NO_CORE with `is_infeasible = False`:
    # a success-shaped status on a model with no solution, where the only thing that changed
    # was the units of the innocent rows. The core itself is unaffected by the padding, so it
    # must still be exactly the pair.
    var padded_a = List[Float64]()
    var padded_senses = List[Int]()
    var padded_rhs = List[Float64]()
    for _ in range(200):
        padded_a.append(1.0)
        padded_a.append(0.0)
        padded_senses.append(SENSE_LE)
        padded_rhs.append(1e7)
    padded_a.append(0.0)
    padded_a.append(1.0)
    padded_senses.append(SENSE_GE)
    padded_rhs.append(3.0)
    padded_a.append(0.0)
    padded_a.append(1.0)
    padded_senses.append(SENSE_LE)
    padded_rhs.append(2.0)
    var padded = infeasibility_core_default(padded_a, 202, 2, padded_senses, padded_rhs)
    if (
        padded.status == EXPLAIN_OK
        and padded.is_infeasible
        and padded.core_verified
        and padded.core_size == 2
        and _exact_ints(padded.core, _ints(200, 201))
        and _exact(padded.core_rhs, _floats(3.0, 2.0))
        and padded.minimal
        and padded.minimality_verified
        and padded.n_inconclusive == 0
        and padded.n_constraints == 202
        # 1 full solve + 202 deletion trials + 1 confirmation + 2 necessity probes.
        and padded.n_solves == 206
        and padded.infeasibility == 1.0
        and padded.core_infeasibility == 1.0
        and not padded.in_core[0]
        and not padded.in_core[199]
        and padded.in_core[200]
        and padded.in_core[201]
    ):
        passed += 1
        print("  ✅ a 2e9 right-hand-side scale does not turn a 1-unit contradiction feasible")
    else:
        failed += 1
        print(
            "  ❌ large-scale core wrong:",
            padded.status,
            padded.is_infeasible,
            padded.core_size,
            padded.n_solves,
            padded.infeasibility,
        )

    # ── contributions at the optimum sum to the objective, provably ───────────
    var parts = optimum_contributions_default(_c3(), _a3(), 3, 3, _le3(), _b3(), True)
    var share_ok = (
        len(parts.share) == 3
        and _close(parts.share[0], 10.0 / 13.0, 1e-12)
        and parts.share[1] == 0.0
        and _close(parts.share[2], 3.0 / 13.0, 1e-12)
    )
    if (
        parts.status == EXPLAIN_OK
        and parts.has_objective
        and parts.objective == 13.0
        and parts.minimization_objective == -13.0
        and parts.maximize
        and parts.constant == 0.0
        and _exact(parts.contribution, _floats(10.0, 0.0, 3.0))
        and parts.parts_total == 13.0
        and parts.residual == 0.0
        and parts.sums_to_objective
        and parts.n_active == 2
        and parts.largest_index == 0
        and parts.largest_contribution == 10.0
        and parts.has_share
        and share_ok
        and _all_close(parts.x, _floats(2.0, 0.0, 1.0), 1e-9)
    ):
        passed += 1
        print("  ✅ the itemised objective sums to 13 with a residual of exactly 0")
    else:
        failed += 1
        print(
            "  ❌ contributions wrong:",
            parts.status,
            parts.objective,
            parts.parts_total,
            parts.residual,
        )

    # ── a constant, a maximise flag, and a variable part that cancels to 0 ────
    # 2*3 + (-1)*4 = 2, plus a constant of 7, is 9. The constant is NOT a contribution of
    # any variable, so it stays out of the itemisation and out of the shares.
    var with_const = objective_contributions(_floats(2.0, -1.0), 7.0, _floats(3.0, 4.0), True)
    # 1*2 + (-1)*2 = 0: the variable part cancels exactly. Shares of a zero total do not
    # exist, so the list is EMPTY rather than zero-filled or full of 0/0.
    var cancelled = objective_contributions(_floats(1.0, -1.0), 5.0, _floats(2.0, 2.0), False)
    var ragged_parts = objective_contributions(
        _floats(1.0, 2.0), 0.0, _floats(1.0, 2.0, 3.0), False
    )
    if (
        with_const.status == EXPLAIN_OK
        and with_const.objective == 9.0
        and with_const.minimization_objective == -9.0
        and with_const.constant == 7.0
        and _exact(with_const.contribution, _floats(6.0, -4.0))
        and with_const.parts_total == 2.0
        and with_const.residual == 0.0
        and with_const.largest_index == 0
        and with_const.largest_contribution == 6.0
        and with_const.has_share
        and _exact(with_const.share, _floats(3.0, -2.0))
        and cancelled.status == EXPLAIN_OK
        and cancelled.objective == 5.0
        and cancelled.parts_total == 0.0
        and cancelled.n_active == 2
        and not cancelled.has_share
        and len(cancelled.share) == 0
        and ragged_parts.status == MODEL_ERR_LENGTH_MISMATCH
        and not ragged_parts.has_objective
        and len(ragged_parts.contribution) == 0
        and ragged_parts.residual == 0.0
    ):
        passed += 1
        print("  ✅ the constant stays out of the shares and a zero total has none")
    else:
        failed += 1
        print(
            "  ❌ decomposition edge cases wrong:",
            with_const.status,
            with_const.parts_total,
            cancelled.has_share,
            ragged_parts.status,
        )

    # ── an unbounded and an infeasible program carry NO explanation ───────────
    # maximise x subject to x >= 1 is unbounded; the vertex it last visited is not an
    # optimum, so there is nothing to price and every list is empty.
    var unbounded = binding_constraints_default(
        _floats(1.0), _floats(1.0), 1, 1, _ints(SENSE_GE), _floats(1.0), True
    )
    var unbounded_parts = optimum_contributions_default(
        _floats(1.0), _floats(1.0), 1, 1, _ints(SENSE_GE), _floats(1.0), True
    )
    var infeasible = binding_constraints_default(
        _floats(1.0), _floats(1.0, 1.0), 2, 1, _ints(SENSE_GE, SENSE_LE),
        _floats(5.0, 3.0), True,
    )
    if (
        unbounded.status == LP_UNBOUNDED
        and not unbounded.has_objective
        and unbounded.objective == 0.0
        and len(unbounded.duals) == 0
        and len(unbounded.binding_rows) == 0
        and unbounded.n_binding == 0
        and not unbounded.complementary
        and unbounded.cs_gap == EXPLAIN_GAP_ABSENT
        and unbounded.duality_gap == EXPLAIN_GAP_ABSENT
        and unbounded_parts.status == LP_UNBOUNDED
        and not unbounded_parts.has_objective
        and len(unbounded_parts.contribution) == 0
        and infeasible.status == LP_INFEASIBLE
        and not infeasible.has_objective
        and len(infeasible.duals) == 0
        and explain_status_name(infeasible.status) == "infeasible"
    ):
        passed += 1
        print("  ✅ unbounded and infeasible programs get a status and no numbers")
    else:
        failed += 1
        print(
            "  ❌ no-answer paths wrong:",
            unbounded.status,
            unbounded.has_objective,
            infeasible.status,
            len(infeasible.duals),
        )

    # ── the generated-suite argument pattern is REFUSED, not indexed ──────────
    # Every contract function is called as the A-Z generator would: five-element lists and 5
    # for every Int. `rows = cols = 5` over a 5-element matrix asks for 25 cells, so the
    # dense shape is refused before anything is read.
    var gen_binding = binding_constraints(
        _lf5, 0.5, _lf5, 5, 5, _li5, _lf5, True, 5, 0.5, 0.5
    )
    var gen_binding_default = binding_constraints_default(_lf5, _lf5, 5, 5, _li5, _lf5, True)
    var gen_core = infeasibility_core(_lf5, 5, 5, _li5, _lf5, 5, 0.5, 0.5)
    var gen_core_default = infeasibility_core_default(_lf5, 5, 5, _li5, _lf5)
    var gen_parts = optimum_contributions(_lf5, 0.5, _lf5, 5, 5, _li5, _lf5, True, 5, 0.5, 0.5)
    var gen_parts_default = optimum_contributions_default(_lf5, _lf5, 5, 5, _li5, _lf5, True)
    # `objective_contributions(_lf5, 0.5, _lf5, True)` is a LEGAL call — five coefficients
    # and a five-element point — so it must answer instead of refusing: 5 * (0.5 * 0.5) plus
    # the constant 0.5 is 1.75.
    var gen_point = objective_contributions(_lf5, 0.5, _lf5, True)
    if (
        gen_binding.status == MODEL_ERR_DENSE_SHAPE
        and len(gen_binding.duals) == 0
        and gen_binding_default.status == MODEL_ERR_DENSE_SHAPE
        and gen_core.status == MODEL_ERR_DENSE_SHAPE
        and len(gen_core.core) == 0
        and gen_core_default.status == MODEL_ERR_DENSE_SHAPE
        and gen_parts.status == MODEL_ERR_DENSE_SHAPE
        and gen_parts_default.status == MODEL_ERR_DENSE_SHAPE
        and gen_point.status == EXPLAIN_OK
        and gen_point.objective == 1.75
        and len(gen_point.contribution) == 5
        and gen_point.parts_total == 1.25
    ):
        passed += 1
        print("  ✅ the _lf5/_li5/5 pattern is refused by every flat entry point")
    else:
        failed += 1
        print(
            "  ❌ generated pattern not refused:",
            gen_binding.status,
            gen_core.status,
            gen_parts.status,
            gen_point.status,
        )

    # ── the wrapping multiply, the solve budget, and the policy ───────────────
    # 3 * 6148914691236517206 == 2 exactly, so a `rows * cols == len(a)` check passes this
    # shape and then reads a two-element list at index 6148914691236517206 — an uncatchable
    # process crash. `dims_fit` is a division, so it refuses.
    var wrapped = infeasibility_core_default(
        _floats(1.0, 2.0), 3, 6148914691236517206, _ints(SENSE_LE, SENSE_LE, SENSE_LE),
        _floats(1.0, 1.0, 1.0),
    )
    var too_many_rows = EXPLAIN_MAX_CORE_ROWS + 1
    var wide = infeasibility_core_default(
        _zeros(too_many_rows), too_many_rows, 1, _repeat_int(SENSE_LE, too_many_rows),
        _zeros(too_many_rows),
    )
    var no_iterations = infeasibility_core(
        _a_inf(), 4, 2, _senses_inf(), _rhs_inf(), 0, 1e-9, 1e-9
    )
    var zero_opt_tol = infeasibility_core(
        _a_inf(), 4, 2, _senses_inf(), _rhs_inf(), 1000, 1e-9, 0.0
    )
    var zero_opt_binding = binding_constraints(
        _c3(), 0.0, _a3(), 3, 3, _le3(), _b3(), True, 1000, 1e-9, 0.0
    )
    if (
        wrapped.status == MODEL_ERR_DENSE_SHAPE
        and len(wrapped.core) == 0
        and wide.status == MODEL_ERR_DIMENSION_TOO_LARGE
        and wide.n_solves == 0
        and no_iterations.status == MODEL_ERR_POLICY
        and zero_opt_tol.status == MODEL_ERR_POLICY
        and zero_opt_binding.status == MODEL_ERR_POLICY
    ):
        passed += 1
        print("  ✅ a wrapped shape, an over-budget row count and a null policy are refused")
    else:
        failed += 1
        print(
            "  ❌ guards wrong:",
            wrapped.status,
            wide.status,
            no_iterations.status,
            zero_opt_binding.status,
        )

    # ── the general model, explained, against the arena evaluators ────────────
    var kinds3 = _ints(VAR_CONTINUOUS, VAR_CONTINUOUS, VAR_CONTINUOUS)
    var lower_only = _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER)
    var built = linear_model_flat(
        _c3(), _a3(), 3, 3, _le3(), _b3(), _zeros(3), _zeros(3), kinds3, lower_only, True
    )
    var model_report = model_binding_constraints(built.model)
    var model_parts = model_contributions(built.model)
    var model_core = model_infeasibility_core(built.model)
    # Independent routes: `model_evaluate` walks each constraint ARENA node by node to get
    # the activity vector, and `model_objective` walks the objective arena. The report
    # reached the same numbers through the extracted `c` and the dense `A`.
    var walked = model_evaluate(built.model, model_report.x)
    var walked_obj = model_objective(built.model, model_report.x)
    if (
        built.status == MODEL_OK
        and model_report.status == EXPLAIN_OK
        and model_report.objective == 13.0
        and _all_close(model_report.duals, _floats(1.0, 0.0, 1.0), 1e-9)
        and _exact_bools(model_report.binding, _bools(True, False, True))
        and model_parts.status == EXPLAIN_OK
        and _all_close(model_parts.contribution, _floats(10.0, 0.0, 3.0), 1e-9)
        and model_parts.residual == 0.0
        and model_core.status == EXPLAIN_FEASIBLE_NO_CORE
        and walked.status == MODEL_OK
        and walked.feasible
        and _all_close(walked.constraint_value, model_report.activity, 1e-9)
        and walked_obj.has_value
        and _close(walked_obj.value, model_parts.objective, 1e-9)
    ):
        passed += 1
        print("  ✅ the model-level report agrees with the arena evaluators")
    else:
        failed += 1
        print(
            "  ❌ model-level path wrong:",
            model_report.status,
            model_parts.status,
            model_core.status,
            walked.status,
        )

    # ── an infeasible general model, cored through the arenas ─────────────────
    var built_inf = linear_model_flat(
        _zeros(2), _a_inf(), 4, 2, _senses_inf(), _rhs_inf(), _zeros(2), _zeros(2),
        _ints(VAR_CONTINUOUS, VAR_CONTINUOUS),
        _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER), False,
    )
    var model_inf_core = model_infeasibility_core(built_inf.model)
    var model_inf_report = model_binding_constraints(built_inf.model)
    if (
        built_inf.status == MODEL_OK
        and model_inf_core.status == EXPLAIN_OK
        and model_inf_core.is_infeasible
        and _exact_ints(model_inf_core.core, _ints(1, 3))
        and model_inf_core.minimal
        and model_inf_core.core_infeasibility == 2.0
        and model_inf_report.status == LP_INFEASIBLE
        and not model_inf_report.has_objective
    ):
        passed += 1
        print("  ✅ a general infeasible model cores to the same contradictory pair")
    else:
        failed += 1
        print(
            "  ❌ model-level core wrong:",
            model_inf_core.status,
            model_inf_core.core_size,
            model_inf_report.status,
        )

    # ── bounds that are not rows, and a discrete variable, are refused ────────
    # `lp_from_arenas` imposes `x >= 0` and does not read the bound columns, so a model
    # carrying an upper bound there would be explained over a LARGER feasible set than it
    # states and every dual would price the wrong program. An integer variable is refused
    # for a different reason: an LP certificate describes the continuous relaxation.
    var boxed = linear_model_flat(
        _c3(), _a3(), 3, 3, _le3(), _b3(), _zeros(3), _floats(10.0, 10.0, 10.0),
        kinds3, _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED, VAR_FLAG_BOXED), True,
    )
    var shifted = linear_model_flat(
        _c3(), _a3(), 3, 3, _le3(), _b3(), _floats(1.0, 1.0, 1.0), _zeros(3),
        kinds3, lower_only, True,
    )
    var discrete = linear_model_flat(
        _c3(), _a3(), 3, 3, _le3(), _b3(), _zeros(3), _zeros(3),
        _ints(VAR_INTEGER, VAR_CONTINUOUS, VAR_CONTINUOUS), lower_only, True,
    )
    var boxed_report = model_binding_constraints(boxed.model)
    var shifted_core = model_infeasibility_core(shifted.model)
    var discrete_parts = model_contributions(discrete.model)
    if (
        boxed.status == MODEL_OK
        and boxed_report.status == EXPLAIN_ERR_BOUNDS_NOT_ROWS
        and len(boxed_report.duals) == 0
        and shifted.status == MODEL_OK
        and shifted_core.status == EXPLAIN_ERR_BOUNDS_NOT_ROWS
        and discrete.status == MODEL_OK
        and discrete_parts.status == EXPLAIN_ERR_DISCRETE_VARIABLE
        and not discrete_parts.has_objective
        and explain_status_name(EXPLAIN_ERR_BOUNDS_NOT_ROWS)
        == "variable_bounds_are_not_expressed_as_rows"
        and explain_status_name(EXPLAIN_ERR_DISCRETE_VARIABLE)
        == "discrete_variable_has_no_lp_certificate"
    ):
        passed += 1
        print("  ✅ an unstated bound and an integer variable are statuses, not defaults")
    else:
        failed += 1
        print(
            "  ❌ model guards wrong:",
            boxed_report.status,
            shifted_core.status,
            discrete_parts.status,
        )

    # ── a nonlinear model reaches here as the EXTRACTOR's status ──────────────
    # x1 * x2 in a constraint is not linear, and the explanation must name that rather than
    # report a core of a linearised program. The code travels from the extractor through
    # two modules untouched, which is what one shared status numbering buys.
    var product_ops = _ints(OP_VAR_REF, OP_VAR_REF, OP_MUL)
    var product = linear_model_flat(
        _floats(1.0, 1.0), _floats(1.0, 1.0), 1, 2, _ints(SENSE_LE), _floats(4.0),
        _zeros(2), _zeros(2), _ints(VAR_CONTINUOUS, VAR_CONTINUOUS),
        _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER), True,
    )
    var patched = product.model.copy()
    patched.con_ops = product_ops^
    patched.con_values = _floats(0.0, 0.0, 0.0)^
    patched.con_var_idx = _ints(0, 1, -1)^
    patched.con_lefts = _ints(-1, -1, 0)^
    patched.con_rights = _ints(-1, -1, 1)^
    patched.con_extras = _ints(-1, -1, -1)^
    patched.con_ptr = _ints(0, 3)^
    patched.con_roots = _ints(2)^
    var nonlinear_report = model_binding_constraints(patched)
    var nonlinear_core = model_infeasibility_core(patched)
    if (
        product.status == MODEL_OK
        and nonlinear_report.status == LIN_ERR_NONLINEAR_PRODUCT
        and len(nonlinear_report.binding_rows) == 0
        and nonlinear_core.status == LIN_ERR_NONLINEAR_PRODUCT
        and len(nonlinear_core.core) == 0
        and explain_status_name(LIN_ERR_NONLINEAR_PRODUCT)
        == "nonlinear_product_of_variables"
    ):
        passed += 1
        print("  ✅ a nonlinear constraint surfaces as the extractor's own status")
    else:
        failed += 1
        print(
            "  ❌ nonlinear passthrough wrong:",
            nonlinear_report.status,
            nonlinear_core.status,
        )

    # ── one numbering, and no two codes sharing a name ────────────────────────
    # Derived from the numbering itself rather than hardcoded: model 0-30, extractor 40-42,
    # solver 60-63, explanation 80-86. A duplicate name means two outcomes a caller cannot
    # tell apart, which is the whole failure this package removes.
    var codes = List[Int]()
    for code in range(0, 31):
        codes.append(code)
    for code in range(40, 43):
        codes.append(code)
    for code in range(60, 64):
        codes.append(code)
    for code in range(80, 87):
        codes.append(code)
    var names = List[String]()
    for k in range(len(codes)):
        names.append(explain_status_name(codes[k]))
    var all_distinct = True
    var unknown_seen = False
    for i in range(len(names)):
        if names[i] == "unknown_status_" + String(codes[i]):
            unknown_seen = True
        for j in range(i + 1, len(names)):
            if names[i] == names[j]:
                all_distinct = False
    if all_distinct and not unknown_seen and len(names) == 45:
        passed += 1
        print("  ✅ all 45 status codes in the shared numbering have distinct names")
    else:
        failed += 1
        print("  ❌ status names collide or fall through:", len(names), all_distinct)

    # ── the x >= 0 convention shows up as a ONE-row core ──────────────────────
    # `x <= -5` is infeasible on its own because `x >= 0` is the variable convention, and
    # non-negativity is not a candidate for deletion. Phase 1 flips the row so its
    # right-hand side is non-negative and then minimises the single artificial of
    # `-x - s = 5`, whose best value at `x = s = 0` is 5. Solves: 1 full + 1 trial + 1
    # confirmation + 1 necessity probe = 4.
    var single = infeasibility_core_default(
        _floats(1.0), 1, 1, _ints(SENSE_LE), _floats(-5.0)
    )
    if (
        single.status == EXPLAIN_OK
        and single.is_infeasible
        and single.core_verified
        and single.core_size == 1
        and _exact_ints(single.core, _ints(0))
        and _exact_bools(single.in_core, _bools(True))
        and _exact_bools(single.necessary, _bools(True))
        and single.minimal
        and single.n_solves == 4
        and single.infeasibility == 5.0
        and single.core_infeasibility == 5.0
    ):
        passed += 1
        print("  ✅ a row contradicting x >= 0 alone is a one-row verified-minimal core")
    else:
        failed += 1
        print(
            "  ❌ one-row core wrong:",
            single.status,
            single.core_size,
            single.n_solves,
            single.infeasibility,
        )

    # ── no rows at all, and a huge `cols` with no rows ────────────────────────
    # `x = 0` satisfies an empty system, so the answer needs no solve. The second call is
    # the allocation guard: zero rows means zero cells, so `dims_fit` ALLOWS
    # `cols = MAX_CSR_DIM` with an empty matrix — and a `cols`-length zero objective would
    # be half a gigabyte of Float64. It is answered before anything is allocated.
    var no_rows = infeasibility_core_default(
        List[Float64](), 0, 3, List[Int](), List[Float64]()
    )
    var no_rows_wide = infeasibility_core_default(
        List[Float64](), 0, 1 << 26, List[Int](), List[Float64]()
    )
    if (
        no_rows.status == EXPLAIN_FEASIBLE_NO_CORE
        and not no_rows.is_infeasible
        and no_rows.n_solves == 0
        and no_rows.core_size == 0
        and no_rows.infeasibility == 0.0
        and no_rows_wide.status == EXPLAIN_FEASIBLE_NO_CORE
        and no_rows_wide.n_solves == 0
        and len(no_rows_wide.core) == 0
    ):
        passed += 1
        print("  ✅ an empty constraint system is feasible without a solve or an allocation")
    else:
        failed += 1
        print(
            "  ❌ empty-system core wrong:",
            no_rows.status,
            no_rows.n_solves,
            no_rows_wide.status,
        )

    # ── a zero-variable objective is a real answer, not an absent one ─────────
    # `model.mojo` accepts a model with no variables and a constant objective, so its
    # decomposition is an empty itemisation of a real 7.0 — not a rejection, and not a share
    # of a total that does not exist.
    var constant_only = objective_contributions(
        List[Float64](), 7.0, List[Float64](), False
    )
    if (
        constant_only.status == EXPLAIN_OK
        and constant_only.has_objective
        and constant_only.objective == 7.0
        and constant_only.minimization_objective == 7.0
        and constant_only.constant == 7.0
        and constant_only.n_vars == 0
        and constant_only.n_active == 0
        and constant_only.parts_total == 0.0
        and constant_only.residual == 0.0
        and constant_only.sums_to_objective
        and constant_only.largest_index == -1
        and constant_only.largest_contribution == 0.0
        and not constant_only.has_share
        and len(constant_only.contribution) == 0
    ):
        passed += 1
        print("  ✅ a zero-variable objective decomposes to a constant with no shares")
    else:
        failed += 1
        print(
            "  ❌ zero-variable decomposition wrong:",
            constant_only.status,
            constant_only.objective,
            constant_only.largest_index,
        )

    # ── a duality gap is its own status, distinct from a slackness violation ──
    var gap_name = explain_status_name(EXPLAIN_ERR_DUALITY_GAP)
    var sum_name = explain_status_name(EXPLAIN_ERR_SUM_MISMATCH)
    var core_name = explain_status_name(EXPLAIN_ERR_CORE_UNVERIFIED)
    if (
        gap_name == "duality_gap_between_primal_and_dual_objective"
        and sum_name == "objective_parts_do_not_sum_to_the_objective"
        and core_name == "core_not_confirmed_infeasible"
        and explain_status_name(EXPLAIN_OK) == "optimal"
        and explain_status_name(MODEL_ERR_DENSE_SHAPE) == "dense_shape_invalid"
    ):
        passed += 1
        print("  ✅ each explanation outcome names itself and 0 falls through to optimal")
    else:
        failed += 1
        print("  ❌ status naming wrong:", gap_name, sum_name, core_name)

    print("  [optimization.explain] Passed:", passed, "Failed:", failed)
