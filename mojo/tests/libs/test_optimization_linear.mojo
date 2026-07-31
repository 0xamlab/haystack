"""test_optimization_linear.mojo — known-value tests for the extractor and the simplex.

Hand-written, and every number below was computed by hand before it was run. The
assertions target the silent wrong answers this module exists to remove, so most of them
are pairings rather than single values:

  * the two-variable optimum is asserted against the FROZEN `lp_solve_2var`, which
    enumerates vertices instead of pivoting — a different algorithm on the same program, so
    agreement is evidence and not a tautology. It maximises and takes `(c, A, b)`, and the
    test passes it in that order deliberately;
  * the duals are asserted three ways at once: complementary slackness (the non-binding
    row's dual is 0), strong duality (`bᵀy` equals the primal optimum), and an INDEPENDENT
    solve of `Bᵀπ = c_B` through the frozen `linalg.mat_from_list` / `mat_solve` from the
    basis the solver reported. Any one of the three can be passed by plausible numbers;
    the three together cannot;
  * infeasible and unbounded are asserted to carry NO answer — empty `x`, `has_objective`
    False — because "the closest point" and "the last vertex" are what a solver returns
    when it reports success on a program that has no optimum;
  * the right-hand-side ranges are hand-derived from `B⁻¹b` for all three rows, including
    the non-binding row whose range has no upper end, which is asserted as a FLAG
    (`has_upper == False`) and not as a large number — and then RE-SOLVED inside every
    reported range. Endpoint arithmetic alone is what let a range whose interior is
    infeasible ship: a rank-deficient equality block leaves an artificial basic, that
    artificial must stay at exactly zero, and the row was reported open on both the
    arithmetic and the flag while every perturbation inside the reported range was
    infeasible. `_ranges_resolve` is the assertion that catches that class;
  * infeasibility is asserted PER ROW. A program with no feasible point plus 200 unrelated
    large-rhs rows is still infeasible, and a program whose rows are genuinely satisfiable at
    a magnitude of 1e7 is still optimal — the same test has to get both right, which a
    threshold scaled by `Σ|b|` cannot;
  * a declared `n_vars` the arenas do not justify is bounded by the payload rather than
    allocated: a one-literal arena asking for `1 << 26` variables comes back with an empty
    coefficient vector, not a 2^26-long one;
  * the extractor is asserted to REJECT `x*y`, `x/y`, `x/0`, `sqrt(x)` and an in-expression
    comparison, each naming the node, the opcode and the variable — and to accept
    `3x + 2y - 4`, `sqrt(4)*x`, a shared subexpression counted once, and `x - x`, whose
    all-zero coefficient vector is a real linear form.

Beale's cycling example is here because a naive most-negative rule loops on it forever.
The assertion is that it terminates AT the hand-computed optimum -1/20, and the same
program under a two-iteration cap reports `iteration_limit` with no answer attached.

Exact equality is used wherever the arithmetic is exact in binary floating point — the
extractor's coefficients, the recovered matrix, the infeasibility residual, the integer
vertex of the three-variable program. A tolerance appears only where a division genuinely
rounds: 16/3 in a range end, and the 1/3 pivots of the two-variable program.
"""
from linalg import mat_from_list, mat_solve
from linear_programming import lp_solve_2var
from optimization.linear import (
    LIN_ERR_NONLINEAR_OP,
    LIN_ERR_NONLINEAR_PRODUCT,
    LIN_ERR_VARIABLE_DIVISOR,
    LP_INFEASIBLE,
    LP_ITERATION_LIMIT,
    LP_OPTIMAL,
    LP_UNBOUNDED,
    LinearForm,
    RhsSensitivity,
    lin_status_name,
    linear_extract_flat,
    linear_form_value,
    lp_dual_objective,
    lp_from_arenas,
    lp_rhs_ranges,
    lp_solve,
    lp_solve_default,
    lp_status_name,
)
from optimization.model import (
    MODEL_ERR_CONSTRAINT_PTR,
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_DIV_BY_ZERO,
    MODEL_ERR_EXPR_ROOT,
    MODEL_ERR_POLICY,
    MODEL_ERR_UNSUPPORTED_OP,
    MODEL_OK,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    expr_evaluate_flat,
    linear_arena,
    linear_model_flat,
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
    """Exact equality. Used only where every value is a small integer or a dyadic
    fraction, so a tolerance would hide a genuine mis-accumulation."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


# ── the three-variable program, hand-solved ───────────────────────────────────
# maximise  5x1 + 4x2 + 3x3
#   2x1 + 3x2 +  x3 <=  5
#   4x1 +  x2 + 2x3 <= 11
#   3x1 + 4x2 + 2x3 <=  8      x >= 0
#
# Optimum 13 at x = (2, 0, 1):  rows 1 and 3 bind (2*2+1 = 5, 3*2+2 = 8), row 2 has
# activity 4*2 + 2*1 = 10 against 11, so its slack is 1 and its dual must be 0.
# Duals y = (1, 0, 1) — bᵀy = 5 + 0 + 8 = 13 = the primal optimum, which is strong duality.
# Reduced costs c - Aᵀy = (5-5, 4-7, 3-3) = (0, -4+1, 0) = (0, -3, 0): non-positive
# everywhere, as a maximisation at optimality requires, and zero on the two basic columns.


fn _c3() -> List[Float64]:
    return _floats(5.0, 4.0, 3.0)


fn _a3() -> List[Float64]:
    return _floats(2.0, 3.0, 1.0, 4.0, 1.0, 2.0, 3.0, 4.0, 2.0)


fn _b3() -> List[Float64]:
    return _floats(5.0, 11.0, 8.0)


fn _le3() -> List[Int]:
    return _ints(SENSE_LE, SENSE_LE, SENSE_LE)


fn _ranges_resolve(
    c: List[Float64], a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool, ranges: RhsSensitivity,
) -> Bool:
    """RE-SOLVE the program with each row's rhs moved INSIDE its reported range.

    A reported endpoint can be checked by hand; a reported range whose interior is infeasible
    cannot, and that is the wrong answer this exists to catch — `lp_rhs_ranges` derived every
    range from `x_B >= 0` alone, which is not the condition a basic artificial on a linearly
    dependent row obeys, and it reported such a row as having no upper limit at all.

    The probe is a quarter of the way up a two-ended range, and `rhs[i] + 1000` when the upper
    end is reported ABSENT — "grows without limit" is a claim about every larger value, so an
    arbitrary increase has to be feasible for the claim to be true.
    """
    for i in range(rows):
        var probe = rhs[i] + 1000.0
        if ranges.has_upper[i]:
            probe = ranges.lower[i] + 0.25 * (ranges.upper[i] - ranges.lower[i])
        var moved = rhs.copy()
        moved[i] = probe
        var again = lp_solve_default(c, a, rows, cols, senses, moved, maximize)
        if again.status != LP_OPTIMAL:
            return False
    return True


fn _arena_var(idx: Int) -> LinearForm:
    """A one-node arena holding `x_idx`, extracted. Used to keep the small cases readable."""
    return linear_extract_flat(
        _ints(1), _floats(0.0), _ints(idx), _ints(-1), _ints(-1), _ints(-1), 0, idx + 1
    )


fn main() raises:
    var passed = 0
    var failed = 0

    # ── two variables, against the frozen vertex enumerator ──────────────────
    # maximise 3x + 5y  s.t.  x <= 4,  2y <= 12,  3x + 2y <= 18,  x, y >= 0.
    # By hand: the binding pair is 2y = 12 and 3x + 2y = 18, so y = 6, x = 2 and the
    # objective is 6 + 30 = 36. `lp_solve_2var` reaches the same vertex by intersecting
    # every pair of lines and testing feasibility — a different algorithm, which is what
    # makes it an oracle rather than a mirror.
    var c2 = _floats(3.0, 5.0)
    var a2 = _floats(1.0, 0.0, 0.0, 2.0, 3.0, 2.0)
    var b2 = _floats(4.0, 12.0, 18.0)
    var rows2 = List[List[Float64]]()
    rows2.append(_floats(1.0, 0.0))
    rows2.append(_floats(0.0, 2.0))
    rows2.append(_floats(3.0, 2.0))
    var frozen = lp_solve_2var(c2, rows2, b2)
    var mine = lp_solve_default(c2, a2, 3, 2, _le3(), b2, True)
    if (
        len(frozen) == 3
        and mine.status == LP_OPTIMAL
        and mine.has_objective
        and _close(mine.objective, 36.0, 1e-9)
        and _close(mine.objective, frozen[2], 1e-9)
        and _close(mine.x[0], frozen[0], 1e-9)
        and _close(mine.x[1], frozen[1], 1e-9)
        and _close(mine.x[0], 2.0, 1e-9)
        and _close(mine.x[1], 6.0, 1e-9)
    ):
        passed += 1
        print("  ✅ the 2-var optimum matches the frozen lp_solve_2var vertex exactly")
    else:
        failed += 1
        print(
            "  ❌ 2-var mismatch:",
            mine.status,
            mine.objective,
            len(frozen),
            len(mine.x),
        )

    # ── three variables, hand-computed vertex, duals and reduced costs ───────
    var sol = lp_solve_default(_c3(), _a3(), 3, 3, _le3(), _b3(), True)
    if (
        sol.status == LP_OPTIMAL
        and sol.has_objective
        and _close(sol.objective, 13.0, 1e-9)
        and _all_close(sol.x, _floats(2.0, 0.0, 1.0), 1e-9)
        and _all_close(sol.duals, _floats(1.0, 0.0, 1.0), 1e-9)
        and _all_close(sol.reduced_costs, _floats(0.0, -3.0, 0.0), 1e-9)
        and _all_close(sol.activity, _floats(5.0, 10.0, 8.0), 1e-9)
        and _all_close(sol.slack, _floats(0.0, 1.0, 0.0), 1e-9)
        and sol.n_vars == 3
        and sol.n_constraints == 3
    ):
        passed += 1
        print("  ✅ the 3-var optimum, duals and reduced costs are the hand-computed ones")
    else:
        failed += 1
        print(
            "  ❌ 3-var wrong:",
            sol.status,
            sol.objective,
            len(sol.x),
            len(sol.duals),
        )

    # ── complementary slackness AND strong duality, as one assertion ─────────
    # Either alone is passable by plausible numbers: a dual vector of zeros satisfies
    # complementary slackness, and a dual vector scaled to hit bᵀy = 13 can be anything.
    # Together with dual feasibility (every reduced cost <= 0 for a maximisation) they are
    # an optimality certificate.
    var dual_obj = lp_dual_objective(sol.duals, _b3())
    var slackness_holds = True
    var dual_sign_holds = True
    for i in range(sol.n_constraints):
        if sol.slack[i] > 1e-9 and not _close(sol.duals[i], 0.0, 1e-12):
            slackness_holds = False
        if sol.duals[i] < -1e-9:
            # A `<=` row in a maximisation can only ever be worth a non-negative amount.
            dual_sign_holds = False
    var costs_signed = True
    for j in range(sol.n_vars):
        if sol.reduced_costs[j] > 1e-9:
            costs_signed = False
        if sol.x[j] > 1e-9 and not _close(sol.reduced_costs[j], 0.0, 1e-9):
            costs_signed = False
    if (
        dual_obj.status == MODEL_OK
        and dual_obj.has_value
        and _close(dual_obj.value, sol.objective, 1e-9)
        and slackness_holds
        and dual_sign_holds
        and costs_signed
        and not sol.binding[1]
        and sol.binding[0]
        and sol.binding[2]
    ):
        passed += 1
        print("  ✅ duals satisfy complementary slackness and strong duality together")
    else:
        failed += 1
        print(
            "  ❌ duality certificate failed:",
            dual_obj.value,
            sol.objective,
            slackness_holds,
            dual_sign_holds,
            costs_signed,
        )

    # ── the duals again, from an INDEPENDENT frozen solve of Bᵀπ = c_B ───────
    # The reported basis is {x1, slack of row 2, x3}. Every row here is `<=` with a
    # non-negative right-hand side, so no row was sign-flipped and slack column `3 + i`
    # is exactly `e_i`. Building Bᵀ and handing it to the frozen `mat_solve` reaches the
    # duals by a route that never touches the tableau: if the tableau's B⁻¹ block had
    # drifted, these two would disagree.
    var bt = List[Float64]()
    var cb = List[Float64]()
    var basis_ok = len(sol.basis) == 3
    if basis_ok:
        for k in range(3):
            var col = sol.basis[k]
            # Row k of Bᵀ is basis column k of B.
            for i in range(3):
                if col < 3:
                    bt.append(_a3()[i * 3 + col])
                elif col - 3 == i:
                    bt.append(1.0)
                else:
                    bt.append(0.0)
            if col < 3:
                # The solver minimises, so its cost vector is -c for a maximisation.
                cb.append(-_c3()[col])
            else:
                cb.append(0.0)
    var oracle = mat_solve(mat_from_list(bt, 3, 3), cb)
    var oracle_duals = List[Float64]()
    for i in range(len(oracle)):
        oracle_duals.append(-oracle[i])
    if basis_ok and len(oracle) == 3 and _all_close(oracle_duals, sol.duals, 1e-9):
        passed += 1
        print("  ✅ the duals match an independent mat_solve of Bᵀπ = c_B")
    else:
        failed += 1
        print("  ❌ dual oracle mismatch:", len(oracle), basis_ok)

    # ── infeasible is reported, with no solution vector ──────────────────────
    # x + y <= 1 and x + y >= 3 cannot both hold, and the minimum total artificial value
    # is exactly 2 — the gap between the two right-hand sides. A solver that returned the
    # nearest point would report a vertex here.
    var infeasible = lp_solve_default(
        _floats(1.0, 1.0), _floats(1.0, 1.0, 1.0, 1.0), 2, 2,
        _ints(SENSE_LE, SENSE_GE), _floats(1.0, 3.0), True,
    )
    if (
        infeasible.status == LP_INFEASIBLE
        and lp_status_name(infeasible.status) == "infeasible"
        and not infeasible.has_objective
        and infeasible.objective == 0.0
        and len(infeasible.x) == 0
        and len(infeasible.duals) == 0
        and infeasible.infeasibility == 2.0
    ):
        passed += 1
        print("  ✅ an infeasible system reports infeasible, residual 2, and no vector")
    else:
        failed += 1
        print(
            "  ❌ infeasible mishandled:",
            infeasible.status,
            infeasible.infeasibility,
            len(infeasible.x),
        )

    # ── unbounded is reported, and the objective is ABSENT ───────────────────
    # maximise x + y subject only to x - y <= 1: moving along y is feasible forever, so
    # there is no optimal objective. The last vertex visited has a finite value, and
    # returning it is the failure this assertion exists for.
    var unbounded = lp_solve_default(
        _floats(1.0, 1.0), _floats(1.0, -1.0), 1, 2, _ints(SENSE_LE), _floats(1.0), True
    )
    if (
        unbounded.status == LP_UNBOUNDED
        and lp_status_name(unbounded.status) == "unbounded"
        and not unbounded.has_objective
        and unbounded.objective == 0.0
        and len(unbounded.x) == 0
        and unbounded.unbounded_variable == 1
    ):
        passed += 1
        print("  ✅ an unbounded system reports unbounded with the objective absent")
    else:
        failed += 1
        print(
            "  ❌ unbounded mishandled:",
            unbounded.status,
            unbounded.has_objective,
            unbounded.objective,
            unbounded.unbounded_variable,
        )

    # ── a program that cycles under the naive rule still terminates ──────────
    # Beale's example. minimise -0.75x1 + 150x2 - 0.02x3 + 6x4 subject to
    #   0.25x1 - 60x2 - 0.04x3 + 9x4 <= 0
    #   0.50x1 - 90x2 - 0.02x3 + 3x4 <= 0
    #                      x3        <= 1
    # Every basis at the origin is degenerate, and Dantzig's most-negative rule returns to
    # it. By hand: with x2 = x4 = 0, row 2 gives x1 <= 0.04x3 and row 1 gives x1 <= 0.16x3,
    # so row 2 binds and the best is x3 = 1, x1 = 0.04, worth -0.75(0.04) - 0.02 = -0.05.
    # Raising x2 by t relaxes row 2 to x1 <= 0.04 + 180t, gaining 135t against a cost of
    # 150t, so it never pays; x4 costs 6 and tightens both rows.
    var cb4 = _floats(-0.75, 150.0, -0.02, 6.0)
    var ab4 = _floats(
        0.25, -60.0, -0.04, 9.0,
        0.5, -90.0, -0.02, 3.0,
        0.0, 0.0, 1.0, 0.0,
    )
    var beale = lp_solve_default(cb4, ab4, 3, 4, _le3(), _floats(0.0, 0.0, 1.0), False)
    var capped = lp_solve(
        cb4, 0.0, ab4, 3, 4, _le3(), _floats(0.0, 0.0, 1.0), False, 2, 1e-9, 1e-9
    )
    if (
        beale.status == LP_OPTIMAL
        and _close(beale.objective, -0.05, 1e-12)
        and _all_close(beale.x, _floats(0.04, 0.0, 1.0, 0.0), 1e-12)
        and beale.iterations < 1000
        and beale.degenerate_pivots > 0
        and beale.used_bland
        and capped.status == LP_ITERATION_LIMIT
        and lp_status_name(capped.status) == "iteration_limit"
        and not capped.has_objective
        and len(capped.x) == 0
        and capped.iterations == 2
    ):
        passed += 1
        print("  ✅ Beale's degenerate program terminates at -1/20; the cap is a status")
    else:
        failed += 1
        print(
            "  ❌ degeneracy mishandled:",
            beale.status,
            beale.objective,
            beale.iterations,
            beale.used_bland,
            capped.status,
        )

    # ── right-hand-side ranges, derived by hand from B⁻¹b ────────────────────
    # Basis {x1, s2, x3} gives x1 = 2, x3 = 1, s2 = 1.
    #   b1 + Δ:  x1 = 2 + 2Δ, x3 = 1 - 3Δ, s2 = 1 - 2Δ  →  Δ ∈ [-1, 1/3]  → [4, 16/3]
    #   b2 + Δ:  only s2 = 1 + Δ moves            →  Δ >= -1, no upper end → [10, ∞)
    #   b3 + Δ:  x1 = 2 - Δ, x3 = 1 + 2Δ, s2 = 1  →  Δ ∈ [-1/2, 2]        → [7.5, 10]
    # The objective is 13 + Δ in the first and third, which is the dual of 1 in both.
    var ranges = lp_rhs_ranges(
        _c3(), 0.0, _a3(), 3, 3, _le3(), _b3(), True, 1000, 1e-9, 1e-9
    )
    if (
        ranges.status == LP_OPTIMAL
        and ranges.has_objective
        and _close(ranges.objective, 13.0, 1e-9)
        and ranges.has_lower[0]
        and ranges.has_upper[0]
        and _close(ranges.lower[0], 4.0, 1e-9)
        and _close(ranges.upper[0], 16.0 / 3.0, 1e-9)
        and ranges.has_lower[1]
        and not ranges.has_upper[1]
        and _close(ranges.lower[1], 10.0, 1e-9)
        and ranges.upper[1] == 11.0
        and ranges.has_lower[2]
        and ranges.has_upper[2]
        and _close(ranges.lower[2], 7.5, 1e-9)
        and _close(ranges.upper[2], 10.0, 1e-9)
        # Hand-derived endpoints are not enough on their own: they say nothing about whether
        # the INTERIOR of a reported range is feasible, which is how a row that could not move
        # at all shipped as a row with no upper limit.
        and _ranges_resolve(_c3(), _a3(), 3, 3, _le3(), _b3(), True, ranges)
    ):
        passed += 1
        print("  ✅ rhs ranges match B⁻¹b by hand and re-solve inside every reported range")
    else:
        failed += 1
        print(
            "  ❌ ranges wrong:",
            ranges.status,
            ranges.lower[0],
            ranges.upper[0],
            ranges.has_upper[1],
            ranges.lower[2],
            ranges.upper[2],
        )

    # ── an INFEASIBLE program is not rescued by an unrelated large-rhs row ────
    # 200 ordinary capacity rows `x0 <= 1e7` plus the contradictory pair `x1 >= 3`,
    # `x1 <= 2`. The phase-1 residual is exactly 1.0 — x1 either sits at 3 and breaks the cap
    # by one or at 2 and breaks the floor by one — and no point satisfies both rows.
    # `feas_tol * (1 + Σ_i |b_i|)` is about 2.0 for this program, so the earlier aggregate
    # threshold accepted it: status LP_OPTIMAL, x = (0, 3), objective 3, with duals, reduced
    # costs and a basis attached, while row 201 was violated by a FULL UNIT.
    var big_a = List[Float64]()
    var big_senses = List[Int]()
    var big_rhs = List[Float64]()
    for _ in range(200):
        big_a.append(1.0)
        big_a.append(0.0)
        big_senses.append(SENSE_LE)
        big_rhs.append(1e7)
    big_a.append(0.0)
    big_a.append(1.0)
    big_senses.append(SENSE_GE)
    big_rhs.append(3.0)
    big_a.append(0.0)
    big_a.append(1.0)
    big_senses.append(SENSE_LE)
    big_rhs.append(2.0)
    var scaled_bad = lp_solve_default(
        _floats(0.0, 1.0), big_a, 202, 2, big_senses, big_rhs, False
    )
    # The same defect without any padding rows: one 1e9 row is enough to lift the aggregate
    # threshold above the 0.5 gap between `x >= 5` and `x <= 4.5`.
    var one_big_row = lp_solve_default(
        _floats(1.0), _floats(1.0, 1.0, 1.0), 3, 1,
        _ints(SENSE_GE, SENSE_LE, SENSE_LE), _floats(5.0, 4.5, 1e9), False,
    )
    # The contradiction ON the large row, which a merely PER-ROW test still gets wrong when
    # its tolerance is a FRACTION of the row: `{x >= 1e9, x <= 1e9 - 1}` has no feasible point
    # and a residual of exactly 1.0, but `1.0 / (1 + 1e9)` is 1e-9 — not greater than the
    # 1e-9 default — so it was reported LP_OPTIMAL at x = 1e9. At magnitude 1e9 one unit is
    # 4.5 million ulps, so there is nothing for floating point to explain away. The budget is
    # therefore `feas_tol + 1024 * DBL_EPSILON * |b_i|`, a rounding allowance rather than a
    # fraction of the answer.
    var big_row_contradiction = lp_solve_default(
        _floats(1.0), _floats(1.0, 1.0), 2, 1,
        _ints(SENSE_GE, SENSE_LE), _floats(1e9, 1e9 - 1.0), False,
    )
    # The paired positive control, and the reason the relative term cannot simply be dropped:
    # these rows are satisfiable only at 1e7, and the elimination leaves a residual of about
    # `1e7 * DBL_EPSILON` = 2.2e-9 there — already past an absolute 1e-9, so a purely absolute
    # test would call every program stated in engineering units infeasible. The ulp budget at
    # 1e7 is 2.3e-6, which absorbs that while still being 4 orders of magnitude below the 1.0
    # violation above.
    var scaled_good = lp_solve_default(
        _floats(1.0), _floats(1.0, 1.0), 2, 1,
        _ints(SENSE_GE, SENSE_LE), _floats(1e7, 1e7), False,
    )
    if (
        scaled_bad.status == LP_INFEASIBLE
        and not scaled_bad.has_objective
        and len(scaled_bad.x) == 0
        and len(scaled_bad.duals) == 0
        and len(scaled_bad.basis) == 0
        and _close(scaled_bad.infeasibility, 1.0, 1e-9)
        and one_big_row.status == LP_INFEASIBLE
        and len(one_big_row.x) == 0
        and _close(one_big_row.infeasibility, 0.5, 1e-9)
        and big_row_contradiction.status == LP_INFEASIBLE
        and not big_row_contradiction.has_objective
        and len(big_row_contradiction.x) == 0
        and scaled_good.status == LP_OPTIMAL
        and _close(scaled_good.objective, 1e7, 1e-3)
    ):
        passed += 1
        print("  ✅ infeasibility is per-row AND absolute: no row's magnitude buys it a pass")
    else:
        failed += 1
        print(
            "  ❌ infeasibility threshold wrong:",
            scaled_bad.status,
            scaled_bad.infeasibility,
            len(scaled_bad.x),
            one_big_row.status,
            big_row_contradiction.status,
            scaled_good.status,
        )

    # ── `binding` is a distance to the row, not a fraction of its rhs ─────────
    # `max x  s.t.  x <= 1e9,  x <= 1e9 - 0.9` optimises at x = 999999999.1 with row 1 tight
    # and row 0 holding 0.8999999761581421 of REAL slack. Row 0 was reported BINDING, because
    # the flag was `gap <= feasibility_tol * (1 + |rhs_i|)` = `1e-9 * (1 + 1e9)` = 1.000000001
    # — an absolute threshold of one whole unit, at a scale no caller chose, built by using
    # `feasibility_tol` (4.5 million ulps at 1e9) as the RELATIVE multiplier. It matters past
    # the flag itself: `explain.binding_constraints` reads `binding` to decide which rows get
    # a shadow price, so a row with nearly a full unit of room was presented as a constraint
    # whose dual is actionable, and `lp_rhs_ranges` ties its intervals to the same basis
    # claim. The budget is now `_lp_row_gap_budget` — the caller's ABSOLUTE tolerance plus
    # 1024 ulps at the row's own magnitude — the identical budget phase 1 accepts a residual
    # under, so "satisfied" and "binds" cannot disagree about one row.
    var big_binding = lp_solve_default(
        _floats(1.0), _floats(1.0, 1.0), 2, 1,
        _ints(SENSE_LE, SENSE_LE), _floats(1e9, 1e9 - 0.9), True,
    )
    # CONTROL, same shape at unit scale: 0.9 of room out of a rhs of 1.0. Non-binding before
    # the fix and non-binding after it — the fix is a rescaling, not a blanket tightening, so
    # the verdict at the scale where the old form happened to work must not move.
    var unit_binding = lp_solve_default(
        _floats(1.0), _floats(1.0, 1.0), 2, 1,
        _ints(SENSE_LE, SENSE_LE), _floats(1.0, 0.1), True,
    )
    # CONTROL, a LEGITIMATE near-zero at large scale: rows at 1e6 separated by 1e-7. That gap
    # is 100x the absolute 1e-9 default, so replacing the broken relative term with a purely
    # absolute test would call this tight row non-binding and drop a real shadow price. 1024
    # ulps at 1e6 is 2.3e-7, which is what rounding at that magnitude actually costs, so the
    # row still binds.
    var scaled_tight = lp_solve_default(
        _floats(1.0), _floats(1.0, 1.0), 2, 1,
        _ints(SENSE_LE, SENSE_LE), _floats(1e6, 1e6 - 1e-7), True,
    )
    # CONTROL, the SAME 1e-7 gap at unit scale: 1024 ulps at 1.0 is 2.3e-13, so 1e-7 is a real
    # distance here and the row does NOT bind. The relative term is tied to the row's scale in
    # both directions; it is not a floor that loosens every comparison in the file.
    var unit_tight = lp_solve_default(
        _floats(1.0), _floats(1.0, 1.0), 2, 1,
        _ints(SENSE_LE, SENSE_LE), _floats(1.0, 1.0 - 1e-7), True,
    )
    # The flag travels: `RhsSensitivity` copies `binding` straight out of the solution, so the
    # ranges report inherits whatever verdict was reached above.
    var big_binding_ranges = lp_rhs_ranges(
        _floats(1.0), 0.0, _floats(1.0, 1.0), 2, 1,
        _ints(SENSE_LE, SENSE_LE), _floats(1e9, 1e9 - 0.9), True, 1000, 1e-9, 1e-9,
    )
    if (
        big_binding.status == LP_OPTIMAL
        and _close(big_binding.x[0], 1e9 - 0.9, 1e-6)
        and _close(big_binding.slack[0], 0.8999999761581421, 1e-12)
        and not big_binding.binding[0]
        and big_binding.binding[1]
        and unit_binding.status == LP_OPTIMAL
        and _close(unit_binding.slack[0], 0.9, 1e-12)
        and not unit_binding.binding[0]
        and unit_binding.binding[1]
        and scaled_tight.status == LP_OPTIMAL
        and scaled_tight.slack[0] > 1e-9
        and scaled_tight.binding[0]
        and scaled_tight.binding[1]
        and unit_tight.status == LP_OPTIMAL
        and not unit_tight.binding[0]
        and unit_tight.binding[1]
        and big_binding_ranges.status == LP_OPTIMAL
        and not big_binding_ranges.binding[0]
        and big_binding_ranges.binding[1]
    ):
        passed += 1
        print("  ✅ `binding` measures the gap in the row's own ulps, not a fraction of rhs")
    else:
        failed += 1
        print(
            "  ❌ binding threshold wrong:",
            big_binding.slack[0],
            big_binding.binding[0],
            unit_binding.binding[0],
            scaled_tight.slack[0],
            scaled_tight.binding[0],
            unit_tight.binding[0],
            big_binding_ranges.binding[0],
        )

    # ── a rank-deficient equality block: the range is PINNED, never open ──────
    # A balanced transportation problem, which is rank-deficient by one BY CONSTRUCTION:
    # supplies 10 + 5 equal demands 8 + 7, so row1 + row2 - row3 - row4 = 0 and phase 1
    # leaves one artificial basic at zero. Solving by hand along the single free direction
    # x11 = t: x12 = 10 - t, x21 = 8 - t, x22 = t - 3, cost = 117 - 6t on t ∈ [3, 8], so the
    # optimum is t = 8, x = (8, 2, 0, 5), objective 69.
    # Every row's rhs is PINNED: the basic artificial's B⁻¹ row spans the left null space
    # (1, 1, -1, -1), so moving ANY single b_i off its value drives that artificial off zero
    # and the program has no feasible point at all. It was reported as row 3 ∈ [7, ∞) with
    # `has_upper[3] == False`, i.e. "grows without limit", for a rhs that cannot move at all.
    var tc = _floats(4.0, 6.0, 9.0, 5.0)
    var ta = _floats(
        1.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 1.0,
        1.0, 0.0, 1.0, 0.0,
        0.0, 1.0, 0.0, 1.0,
    )
    var tb = _floats(10.0, 5.0, 8.0, 7.0)
    var teq = _ints(SENSE_EQ, SENSE_EQ, SENSE_EQ, SENSE_EQ)
    var transport = lp_solve_default(tc, ta, 4, 4, teq, tb, False)
    var transport_dual = lp_dual_objective(transport.duals, tb)
    var tranges = lp_rhs_ranges(tc, 0.0, ta, 4, 4, teq, tb, False, 1000, 1e-9, 1e-9)
    var all_pinned = tranges.status == LP_OPTIMAL
    for i in range(4):
        if not (tranges.has_lower[i] and tranges.has_upper[i]):
            all_pinned = False
        elif not (_close(tranges.lower[i], tb[i], 1e-9) and _close(tranges.upper[i], tb[i], 1e-9)):
            all_pinned = False
    if (
        transport.status == LP_OPTIMAL
        and _close(transport.objective, 69.0, 1e-9)
        and _all_close(transport.x, _floats(8.0, 2.0, 0.0, 5.0), 1e-9)
        and transport_dual.has_value
        and _close(transport_dual.value, 69.0, 1e-9)
        and tranges.status == LP_OPTIMAL
        and _close(tranges.objective, 69.0, 1e-9)
        and all_pinned
        and _ranges_resolve(tc, ta, 4, 4, teq, tb, False, tranges)
    ):
        passed += 1
        print("  ✅ a rank-deficient equality block pins every rhs range and re-solves inside it")
    else:
        failed += 1
        print(
            "  ❌ dependent-row ranging wrong:",
            transport.status,
            transport.objective,
            tranges.status,
            all_pinned,
            tranges.has_upper[3],
            tranges.upper[3],
        )

    # ── an equality row, a `>=` row and a NEGATIVE right-hand side ───────────
    # minimise 2x + 3y  s.t.  x + y == 10,  -x >= -6  (that is, x <= 6), x, y >= 0.
    # By hand: y is dearer, so take x as large as allowed — x = 6, y = 4, z = 12 + 12 = 24.
    # Duals: one more unit of the equality's rhs must be met by y, so dual1 = 3; one more
    # unit of -6 loosens the cap to x <= 5, forcing a unit of x into y, so dual2 = 1.
    # bᵀy = 3(10) + 1(-6) = 24 = z, so strong duality holds through the row that was
    # sign-flipped to make the right-hand side non-negative.
    var mixed = lp_solve_default(
        _floats(2.0, 3.0), _floats(1.0, 1.0, -1.0, 0.0), 2, 2,
        _ints(SENSE_EQ, SENSE_GE), _floats(10.0, -6.0), False,
    )
    var mixed_dual = lp_dual_objective(mixed.duals, _floats(10.0, -6.0))
    if (
        mixed.status == LP_OPTIMAL
        and _close(mixed.objective, 24.0, 1e-9)
        and _all_close(mixed.x, _floats(6.0, 4.0), 1e-9)
        and _all_close(mixed.duals, _floats(3.0, 1.0), 1e-9)
        and mixed_dual.has_value
        and _close(mixed_dual.value, 24.0, 1e-9)
        and mixed.phase1_iterations > 0
    ):
        passed += 1
        print("  ✅ an equality plus a flipped `>=` row keeps the duals in the caller's sense")
    else:
        failed += 1
        print(
            "  ❌ mixed senses wrong:",
            mixed.status,
            mixed.objective,
            len(mixed.duals),
            mixed_dual.value,
        )

    # ── the extractor accepts an affine form, EXACTLY ────────────────────────
    # `linear_arena([3, 2], -4)` is the canonical arena for 3x + 2y - 4. Extracting it and
    # evaluating the recovered form at (2, 5) must agree with model.expr_evaluate_flat
    # walking the arena itself: 6 + 10 - 4 = 12.
    var affine = linear_arena(_floats(3.0, 2.0), -4.0)
    var form = linear_extract_flat(
        affine.ops, affine.values, affine.var_idx, affine.lefts, affine.rights,
        affine.extras, affine.root, 2,
    )
    var point = _floats(2.0, 5.0)
    var by_form = linear_form_value(form.coeffs, form.constant, point)
    var by_arena = expr_evaluate_flat(
        affine.ops, affine.values, affine.var_idx, affine.lefts, affine.rights,
        affine.extras, affine.root, point,
    )
    if (
        form.status == MODEL_OK
        and form.is_linear
        and _exact(form.coeffs, _floats(3.0, 2.0))
        and form.constant == -4.0
        and form.n_terms == 2
        and form.node_index == -1
        and by_form.has_value
        and by_arena.has_value
        and by_form.value == 12.0
        and by_form.value == by_arena.value
    ):
        passed += 1
        print("  ✅ 3x + 2y - 4 extracts exactly and agrees with the arena evaluator")
    else:
        failed += 1
        print(
            "  ❌ affine extraction wrong:",
            form.status,
            form.constant,
            by_form.value,
            by_arena.value,
        )

    # ── the extractor REFUSES x*y, naming the node, the opcode and a variable ─
    var product = linear_extract_flat(
        _ints(1, 1, 4), _floats(0.0, 0.0, 0.0), _ints(0, 1, -1),
        _ints(-1, -1, 0), _ints(-1, -1, 1), _ints(-1, -1, -1), 2, 2,
    )
    if (
        product.status == LIN_ERR_NONLINEAR_PRODUCT
        and lin_status_name(product.status) == "nonlinear_product_of_variables"
        and not product.is_linear
        and product.node_index == 2
        and product.op == 4
        and product.var_index == 0
        and len(product.coeffs) == 0
        and product.constant == 0.0
    ):
        passed += 1
        print("  ✅ x*y is refused, naming node 2, opcode mul and variable 0")
    else:
        failed += 1
        print(
            "  ❌ x*y not refused properly:",
            product.status,
            product.node_index,
            product.op,
            product.var_index,
            len(product.coeffs),
        )

    # ── a variable divisor names the DENOMINATOR's variable ─────────────────
    # x / y is not affine in y, and the useful report is which variable is downstairs.
    var quotient = linear_extract_flat(
        _ints(1, 1, 5), _floats(0.0, 0.0, 0.0), _ints(0, 1, -1),
        _ints(-1, -1, 0), _ints(-1, -1, 1), _ints(-1, -1, -1), 2, 2,
    )
    # x / 0 is a different outcome from x / y and must not be folded to a coefficient.
    var by_zero = linear_extract_flat(
        _ints(1, 0, 5), _floats(0.0, 0.0, 0.0), _ints(0, -1, -1),
        _ints(-1, -1, 0), _ints(-1, -1, 1), _ints(-1, -1, -1), 2, 1,
    )
    # x / 2 IS affine, with coefficient 1/2 exactly.
    var halved = linear_extract_flat(
        _ints(1, 0, 5), _floats(0.0, 2.0, 0.0), _ints(0, -1, -1),
        _ints(-1, -1, 0), _ints(-1, -1, 1), _ints(-1, -1, -1), 2, 1,
    )
    if (
        quotient.status == LIN_ERR_VARIABLE_DIVISOR
        and quotient.var_index == 1
        and quotient.node_index == 2
        and by_zero.status == MODEL_ERR_DIV_BY_ZERO
        and by_zero.node_index == 2
        and len(by_zero.coeffs) == 0
        and halved.is_linear
        and _exact(halved.coeffs, _floats(0.5))
        and halved.constant == 0.0
    ):
        passed += 1
        print("  ✅ x/y names the divisor's variable, x/0 is a status, x/2 is a coefficient")
    else:
        failed += 1
        print(
            "  ❌ division handling wrong:",
            quotient.status,
            quotient.var_index,
            by_zero.status,
            halved.status,
        )

    # ── a nonlinear operator over a variable is refused; over a CONSTANT it folds ─
    # sqrt(x) has no affine form. sqrt(4)*x has one, and the constant is folded through
    # model.evaluate_expr rather than by a second copy of sqrt living here.
    var root_of_var = linear_extract_flat(
        _ints(1, 12), _floats(0.0, 0.0), _ints(0, -1),
        _ints(-1, 0), _ints(-1, -1), _ints(-1, -1), 1, 1,
    )
    var folded = linear_extract_flat(
        _ints(0, 12, 1, 4), _floats(4.0, 0.0, 0.0, 0.0), _ints(-1, -1, 0, -1),
        _ints(-1, 0, -1, 1), _ints(-1, -1, -1, 2), _ints(-1, -1, -1, -1), 3, 1,
    )
    # An in-expression comparison is refused by model.check_expr: a constraint's relation
    # lives in its sense and rhs, so a second one inside the expression would feed 1.0/0.0
    # into arithmetic.
    var compared = linear_extract_flat(
        _ints(1, 0, 101), _floats(0.0, 1.0, 0.0), _ints(0, -1, -1),
        _ints(-1, -1, 0), _ints(-1, -1, 1), _ints(-1, -1, -1), 2, 1,
    )
    if (
        root_of_var.status == LIN_ERR_NONLINEAR_OP
        and root_of_var.node_index == 1
        and root_of_var.op == 12
        and root_of_var.var_index == 0
        and folded.is_linear
        and _exact(folded.coeffs, _floats(2.0))
        and compared.status == MODEL_ERR_UNSUPPORTED_OP
        and not compared.is_linear
    ):
        passed += 1
        print("  ✅ sqrt(x) is refused, sqrt(4)*x folds to 2x, a comparison is refused")
    else:
        failed += 1
        print(
            "  ❌ operator handling wrong:",
            root_of_var.status,
            root_of_var.op,
            folded.status,
            len(folded.coeffs),
            compared.status,
        )

    # ── a shared subexpression is counted ONCE per reference, not per path ───
    # Nodes: 0 = x, 1 = 1.0, 2 = x + 1, 3 = node2 + node2. The root is 2(x+1) = 2x + 2, and
    # a recursive descent would walk node 2 twice — correct here, exponential when the
    # sharing nests. The descending pass visits it once with a multiplier of 2.
    var shared = linear_extract_flat(
        _ints(1, 0, 2, 2), _floats(0.0, 1.0, 0.0, 0.0), _ints(0, -1, -1, -1),
        _ints(-1, -1, 0, 2), _ints(-1, -1, 1, 2), _ints(-1, -1, -1, -1), 3, 1,
    )
    # x - x is a real linear form whose only coefficient is 0. Its `coeffs` is present and
    # zero, which is exactly why an EMPTY coeffs list is what "there is no form" means.
    var cancelled = linear_extract_flat(
        _ints(1, 3), _floats(0.0, 0.0), _ints(0, -1),
        _ints(-1, 0), _ints(-1, 0), _ints(-1, -1), 1, 1,
    )
    # 0 * (x*y) cancels to zero, and is still refused: accepting it would mean deciding
    # whether 0 * (1/x) at x = 0 is 0.0 or undefined.
    var zero_times = linear_extract_flat(
        _ints(0, 1, 1, 4, 4), _floats(0.0, 0.0, 0.0, 0.0, 0.0), _ints(-1, 0, 1, -1, -1),
        _ints(-1, -1, -1, 1, 0), _ints(-1, -1, -1, 2, 3), _ints(-1, -1, -1, -1, -1), 4, 2,
    )
    if (
        shared.is_linear
        and _exact(shared.coeffs, _floats(2.0))
        and shared.constant == 2.0
        and cancelled.is_linear
        and _exact(cancelled.coeffs, _floats(0.0))
        and cancelled.n_terms == 0
        and zero_times.status == LIN_ERR_NONLINEAR_PRODUCT
    ):
        passed += 1
        print("  ✅ a shared subtree scales once; x - x is a form; 0*(x*y) is still refused")
    else:
        failed += 1
        print(
            "  ❌ sharing or cancellation wrong:",
            shared.status,
            shared.constant,
            cancelled.n_terms,
            zero_times.status,
        )

    # ── arenas in, LP data out, and the same optimum ─────────────────────────
    # `model.linear_model_flat` builds the general model for the three-variable program;
    # `lp_from_arenas` extracts (c, A, senses, rhs) back out of its arenas. The recovered
    # numbers must be EXACT — every coefficient survived a round trip through the IR — and
    # solving the recovered data must reproduce the optimum found from the raw data.
    var built = linear_model_flat(
        _c3(), _a3(), 3, 3, _le3(), _b3(),
        _floats(0.0, 0.0, 0.0), _floats(0.0, 0.0, 0.0), _ints(0, 0, 0), _ints(1, 1, 1),
        True,
    )
    var wire = built.model.copy()
    var recovered = lp_from_arenas(
        wire.obj_ops, wire.obj_values, wire.obj_var_idx, wire.obj_lefts, wire.obj_rights,
        wire.obj_extras, wire.obj_root, wire.con_ptr, wire.con_roots, wire.con_senses,
        wire.con_rhs, wire.con_ops, wire.con_values, wire.con_var_idx, wire.con_lefts,
        wire.con_rights, wire.con_extras, 3,
    )
    var resolved = lp_solve_default(
        recovered.c, recovered.a, recovered.n_constraints, recovered.n_vars,
        recovered.senses, recovered.rhs, True,
    )
    if (
        built.status == MODEL_OK
        and recovered.status == MODEL_OK
        and recovered.n_vars == 3
        and recovered.n_constraints == 3
        and recovered.constant == 0.0
        and _exact(recovered.c, _c3())
        and _exact(recovered.a, _a3())
        and _exact(recovered.rhs, _b3())
        and resolved.status == LP_OPTIMAL
        and _close(resolved.objective, 13.0, 1e-9)
    ):
        passed += 1
        print("  ✅ lp_from_arenas recovers the LP exactly and it re-solves to 13")
    else:
        failed += 1
        print(
            "  ❌ arena round trip wrong:",
            built.status,
            recovered.status,
            len(recovered.a),
            resolved.objective,
        )

    # ── a nonlinear CONSTRAINT names the row, not just the node ─────────────
    # Objective x + y, one constraint x*y <= 5. The row index is what a caller needs to fix
    # the model; a bare node index into a concatenated arena is not that.
    var obj_arena = linear_arena(_floats(1.0, 1.0), 0.0)
    var bad_row = lp_from_arenas(
        obj_arena.ops, obj_arena.values, obj_arena.var_idx, obj_arena.lefts,
        obj_arena.rights, obj_arena.extras, obj_arena.root,
        _ints(0, 3), _ints(2), _ints(SENSE_LE), _floats(5.0),
        _ints(1, 1, 4), _floats(0.0, 0.0, 0.0), _ints(0, 1, -1),
        _ints(-1, -1, 0), _ints(-1, -1, 1), _ints(-1, -1, -1), 2,
    )
    if (
        bad_row.status == LIN_ERR_NONLINEAR_PRODUCT
        and bad_row.row_index == 0
        and bad_row.node_index == 2
        and bad_row.op == 4
        and len(bad_row.a) == 0
        and len(bad_row.c) == 0
    ):
        passed += 1
        print("  ✅ a nonlinear constraint is refused naming row 0, node 2 and mul")
    else:
        failed += 1
        print(
            "  ❌ nonlinear row mishandled:",
            bad_row.status,
            bad_row.row_index,
            bad_row.node_index,
            len(bad_row.a),
        )

    # ── a declared n_vars is bounded by the PAYLOAD, not by MAX_CSR_DIM ───────
    # `1 << 26` is exactly `MAX_CSR_DIM`, so the declared count passed the only guard there
    # was: a ONE-NODE literal arena returned MODEL_OK carrying a 2^26-long coefficient vector,
    # and through `lp_from_arenas` the same integer bought five per-variable columns, an
    # `OptVar` with a `String` name each, and two more vectors — ~200 bytes per declared
    # variable, measured at 1.29 GB for 2^22 and 3.50 GB for 2^24. A variable no node
    # references has coefficient 0 in every row, so bounding the width by the highest
    # reference cannot change an answer.
    var literal_only = linear_extract_flat(
        _ints(0), _floats(7.0), _ints(-1), _ints(-1), _ints(-1), _ints(-1), 0, 1 << 26
    )
    # Objective `x0`, one constraint `x0 + x1 <= 5`, and 2^20 variables declared. The rows
    # settle at width 2 — the highest variable ANY arena references — and the objective, whose
    # own arena mentions only x0, is PADDED to that width rather than read past its end.
    var wide = lp_from_arenas(
        _ints(1), _floats(0.0), _ints(0), _ints(-1), _ints(-1), _ints(-1), 0,
        _ints(0, 3), _ints(2), _ints(SENSE_LE), _floats(5.0),
        _ints(1, 1, 2), _floats(0.0, 0.0, 0.0), _ints(0, 1, -1),
        _ints(-1, -1, 0), _ints(-1, -1, 1), _ints(-1, -1, -1), 1 << 20,
    )
    var wide_solved = lp_solve_default(
        wide.c, wide.a, wide.n_constraints, wide.n_vars, wide.senses, wide.rhs, True
    )
    if (
        literal_only.status == MODEL_OK
        and literal_only.is_linear
        and len(literal_only.coeffs) == 0
        and literal_only.n_vars == 0
        and literal_only.n_terms == 0
        and literal_only.constant == 7.0
        and wide.status == MODEL_OK
        and wide.n_vars == 2
        and wide.n_constraints == 1
        and _exact(wide.c, _floats(1.0, 0.0))
        and _exact(wide.a, _floats(1.0, 1.0))
        and _exact(wide.rhs, _floats(5.0))
        and wide_solved.status == LP_OPTIMAL
        and _close(wide_solved.objective, 5.0, 1e-9)
    ):
        passed += 1
        print("  ✅ n_vars is bounded by what the arenas reference, and the objective is padded")
    else:
        failed += 1
        print(
            "  ❌ n_vars not payload-bounded:",
            literal_only.status,
            len(literal_only.coeffs),
            wide.status,
            wide.n_vars,
            len(wide.c),
            len(wide.a),
        )

    # ── the generated suite's argument pattern is REFUSED, not indexed ───────
    # Every contract function is called by the A-Z generator with a 5-element list for each
    # List parameter and 5 for each Int. `A` would then be a 5-element list declared 5x5,
    # and the first unguarded read of A[24] is an uncatchable process crash that takes the
    # whole worker with it — so each of these must come back as a status.
    var lf5 = _floats(0.5, 0.6, 0.7, 0.4, 0.3)
    var li5 = _ints(1, 2, 3, 4, 5)
    var g_solve = lp_solve(lf5, 0.5, lf5, 5, 5, li5, lf5, True, 5, 0.5, 0.5)
    var g_default = lp_solve_default(lf5, lf5, 5, 5, li5, lf5, True)
    var g_ranges = lp_rhs_ranges(lf5, 0.5, lf5, 5, 5, li5, lf5, True, 5, 0.5, 0.5)
    var g_form = linear_extract_flat(li5, lf5, li5, li5, li5, li5, 5, 5)
    var g_arenas = lp_from_arenas(
        li5, lf5, li5, li5, li5, li5, 5, li5, li5, li5, lf5,
        li5, lf5, li5, li5, li5, li5, 5,
    )
    var no_iterations = lp_solve(_c3(), 0.0, _a3(), 3, 3, _le3(), _b3(), True, 0, 1e-9, 1e-9)
    var no_tolerance = lp_solve(_c3(), 0.0, _a3(), 3, 3, _le3(), _b3(), True, 10, 1e-9, 0.0)
    if (
        g_solve.status == MODEL_ERR_DENSE_SHAPE
        and len(g_solve.x) == 0
        and g_default.status == MODEL_ERR_DENSE_SHAPE
        and g_ranges.status == MODEL_ERR_DENSE_SHAPE
        and len(g_ranges.duals) == 0
        and g_form.status == MODEL_ERR_EXPR_ROOT
        and len(g_form.coeffs) == 0
        and g_arenas.status == MODEL_ERR_CONSTRAINT_PTR
        and len(g_arenas.a) == 0
        and no_iterations.status == MODEL_ERR_POLICY
        and no_tolerance.status == MODEL_ERR_POLICY
    ):
        passed += 1
        print("  ✅ the 5-element/5 argument pattern is refused by every driver")
    else:
        failed += 1
        print(
            "  ❌ a guard is missing:",
            g_solve.status,
            g_default.status,
            g_ranges.status,
            g_form.status,
            g_arenas.status,
            no_iterations.status,
            no_tolerance.status,
        )

    # ── every outcome has its own name, and 0 is `optimal` not `ok` ──────────
    # A caller that logs the status name must be able to tell the five outcomes apart; two
    # outcomes sharing a name is the same defect as two outcomes sharing a code.
    var names = List[String]()
    names.append(lp_status_name(LP_OPTIMAL))
    names.append(lp_status_name(LP_INFEASIBLE))
    names.append(lp_status_name(LP_UNBOUNDED))
    names.append(lp_status_name(LP_ITERATION_LIMIT))
    names.append(lin_status_name(LIN_ERR_NONLINEAR_PRODUCT))
    names.append(lin_status_name(LIN_ERR_VARIABLE_DIVISOR))
    names.append(lin_status_name(LIN_ERR_NONLINEAR_OP))
    var distinct = True
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if names[i] == names[j]:
                distinct = False
    if (
        distinct
        and lp_status_name(LP_OPTIMAL) == "optimal"
        # A code this module does not define falls through to model.mojo's table rather
        # than becoming "unknown status 8".
        and lin_status_name(MODEL_ERR_DIV_BY_ZERO) == "division_by_zero"
        and lp_status_name(MODEL_ERR_DENSE_SHAPE) == "dense_shape_invalid"
    ):
        passed += 1
        print("  ✅ status names are distinct and fall through to the model table")
    else:
        failed += 1
        print("  ❌ status naming wrong:", distinct, lp_status_name(LP_OPTIMAL))

    # ── a single variable arena extracts, which keeps the helper honest ──────
    var single = _arena_var(0)
    # A ZERO-VARIABLE objective is a real form with a real answer, mirroring model.mojo's
    # acceptance of a zero-variable model — and on success its `coeffs` is EMPTY, which is
    # the one case where reading `len(coeffs)` instead of `is_linear` inverts the verdict.
    var constant_only = linear_arena(List[Float64](), 5.0)
    var no_vars = linear_extract_flat(
        constant_only.ops, constant_only.values, constant_only.var_idx,
        constant_only.lefts, constant_only.rights, constant_only.extras,
        constant_only.root, 0,
    )
    var empty_lp = lp_from_arenas(
        constant_only.ops, constant_only.values, constant_only.var_idx,
        constant_only.lefts, constant_only.rights, constant_only.extras,
        constant_only.root, List[Int](), List[Int](), List[Int](), List[Float64](),
        List[Int](), List[Float64](), List[Int](), List[Int](), List[Int](),
        List[Int](), 0,
    )
    if (
        single.is_linear
        and _exact(single.coeffs, _floats(1.0))
        and single.n_terms == 1
        and no_vars.is_linear
        and no_vars.constant == 5.0
        and len(no_vars.coeffs) == 0
        and no_vars.n_terms == 0
        and empty_lp.status == MODEL_OK
        and empty_lp.constant == 5.0
        and empty_lp.n_vars == 0
        and empty_lp.n_constraints == 0
    ):
        passed += 1
        print("  ✅ a bare var_ref is coefficient 1; a zero-variable form is still a form")
    else:
        failed += 1
        print(
            "  ❌ degenerate forms wrong:",
            single.status,
            len(single.coeffs),
            no_vars.is_linear,
            empty_lp.status,
        )

    print("  [optimization.linear] Passed:", passed, "Failed:", failed)
