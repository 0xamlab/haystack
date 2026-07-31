"""test_optimization_quadratic.mojo — known-value tests for the convex QP driver.

Hand-written, and every expected number below was derived before it was run. What each
group is FOR, because a QP suite that only checks "it returned something near a minimum"
would have passed every defect this module was written to avoid:

  * CLOSED FORMS, exact in binary floating point. `Q = 2I` with no constraints has the
    solution `-c/2`; one equality constraint makes the KKT system 2x2 and hand-solvable;
    a box bound that cuts off the unconstrained minimum has the multiplier `Qx + c`; and
    the Euclidean projection onto the unit simplex has the classic `z - θ` form. These are
    asserted with `==` wherever the arithmetic is exact — which it is, because the
    factorisation is LDLᵀ and takes no square roots. A Cholesky would have returned
    1.9999999999999998 for the first one.
  * THE ZERO-HESSIAN CROSS-CHECK, which is the strongest test available here: with `Q = 0`
    this driver is solving a linear program, and `optimization.linear.lp_solve` is an
    independently verified two-phase simplex on the same data. Objective, `x`, the duals AND
    the bound multipliers are asserted against it — the last of those against lp_solve's
    REDUCED COSTS, which is what a bound multiplier is in LP vocabulary. Two different
    algorithms (a pivoting simplex and an active-set null-space search) agreeing on four
    vectors is evidence; a plausible number is not.
  * A CERTIFICATE THAT MUST REJECT (rule 4d). Three points are handed to `qp_kkt_check`,
    each satisfying THREE of the four conditions and failing exactly one, each strictly
    worse than the true optimum, and each of a shape the returned answers never exercise:
    a wrong-SIGN dual on a tight row (the shape of tier 1's certified cost-5 matching whose
    optimum was 1), a nonzero dual on a SLACK row, and a multiplier on a bound the caller
    never declared. If any of the three were certified, the certificate would be worth less
    than no certificate.
  * INFEASIBILITY PER ROW (rule 4b). `x >= 3` and `x <= 2` is a flat contradiction, and it
    stays infeasible with 200 unrelated rows of `x <= 1e7` bolted on. A tolerance scaled by
    `Σ|b_i|` reports that program OPTIMAL, which is exactly what happened in tier 1.
  * NO ANSWER WHERE THERE IS NONE. Infeasible, unbounded, non-convex and asymmetric all
    return an EMPTY `x` and `has_objective == False`, and the suite asserts the module's own
    stated invariant — `x` is non-empty if and only if `feasible` — for every status it
    produces, including the ones that succeed.
  * A TRUNCATED SEARCH IS NOT A SOLVED ONE. At an iteration cap the status is
    `QP_ITERATION_LIMIT`, `proven_optimal` is False, and the reported bound and objective
    SANDWICH the true optimum, which is the only honest thing a truncated run can say.
  * DETERMINISM, both halves. The same seed reproduces the objective, the point and the
    path signature bit-for-bit. A different seed on a deliberately TIE-RICH program
    (two rows blocking at exactly the same step) takes a different path — asserted on the
    signature — and returns the IDENTICAL optimum, which is what convexity requires and
    what a solver whose answer moved with its seed would be violating.
  * HOSTILE SHAPES. The generated A-Z suite calls every contract function with five-element
    lists and the integer 5, so `qp_solve(_lf5, 5, ...)` is called here directly. A
    wrapping `n * n` and a declared `n` the payload cannot justify are rejected rather than
    indexed, and the area ceiling is exercised with a real allocation rather than asserted
    in a comment.
"""
from determinism.counter_rng import rng_uniform
from optimization.linear import LP_OPTIMAL, lp_solve_default
from optimization.model import (
    has_lower_bound,
    MODEL_ERR_BOUNDS_CROSSED,
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_DIMENSION_TOO_LARGE,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_ERR_NON_FINITE_COEFFICIENT,
    MODEL_ERR_NON_FINITE_POINT,
    MODEL_ERR_NON_FINITE_RHS,
    MODEL_ERR_POLICY,
    MODEL_ERR_SENSE,
    MODEL_ERR_VAR_FLAGS,
    MODEL_OK,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    VAR_FLAG_HAS_LOWER,
    VAR_FLAG_HAS_START,
    VAR_FLAG_HAS_UPPER,
)
from optimization.quadratic import (
    QP_ERR_NOT_CONVEX,
    QP_ERR_NOT_SYMMETRIC,
    QP_INFEASIBLE,
    QP_ITERATION_LIMIT,
    QP_NOT_CERTIFIED,
    QP_NUMERICAL_BREAKDOWN,
    QP_OPTIMAL,
    QP_UNBOUNDED,
    QPSolution,
    qp_convexity_flat,
    qp_gap_flat,
    qp_gradient_flat,
    qp_kkt_check,
    qp_objective_flat,
    qp_solve,
    qp_solve_default,
    qp_status_name,
)


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


fn _zeros(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(n):
        out.append(0.0)
    return out^


fn _rep(value: Int, n: Int) -> List[Int]:
    var out = List[Int]()
    for _ in range(n):
        out.append(value)
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
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _bits_identical(a: QPSolution, b: QPSolution) -> Bool:
    """Bit-for-bit, not approximately: a reproducible search reproduces every field."""
    if a.status != b.status or a.path_signature != b.path_signature:
        return False
    if a.objective != b.objective or a.gap != b.gap or a.best_bound != b.best_bound:
        return False
    if a.iterations != b.iterations or a.n_added != b.n_added:
        return False
    if a.n_dropped != b.n_dropped or a.n_active != b.n_active:
        return False
    if not _exact(a.x, b.x):
        return False
    if not _exact(a.duals, b.duals):
        return False
    if not _exact(a.lower_duals, b.lower_duals):
        return False
    return _exact(a.upper_duals, b.upper_duals)


fn _invariant(s: QPSolution) -> Bool:
    """The module's own stated invariant: a point is returned only when it was verified.

    Asserted for EVERY status the suite produces, including the successful ones, because the
    failure this catches is a driver that returns "the closest point" under a status that
    says there is no point.

    Stated by LENGTH — `len(x) == n_vars` when feasible, `0` when not — and not as "non-empty
    iff feasible", because a zero-variable model is feasible with nothing in `x`. The looser
    spelling would have made the invariant itself false in a reachable case, which is worse
    than not having one.
    """
    if s.feasible:
        if len(s.x) != s.n_vars:
            return False
        if not s.has_objective:
            return False
        return len(s.duals) == s.n_constraints
    if len(s.x) != 0 or s.has_objective:
        return False
    return len(s.duals) == 0 and len(s.lower_duals) == 0


# ── the zero-Hessian differential oracle ──────────────────────────────────────
# maximise 5x + 8y  <=>  minimise -5x - 8y, over x + y <= 6, 5x + 9y <= 45, x, y >= 0.
# The two rows meet at 5x + 9(6 - x) = 45, so x = 9/4, y = 15/4 and the objective is
# -(11.25 + 30) = -41.25. Both variables are strictly positive there, so both bound
# multipliers are 0 and the duals solve  [1 1; 5 9]ᵀ μ = (5, 8):  μ = (1.25, 0.75) and the
# reported duals are their negations, -1.25 and -0.75 (relaxing a `<=` row lowers a minimum).
fn _lp_c() -> List[Float64]:
    return _floats(-5.0, -8.0)


fn _lp_a() -> List[Float64]:
    return _floats(1.0, 1.0, 5.0, 9.0)


fn _lp_b() -> List[Float64]:
    return _floats(6.0, 45.0)


# The same rows with a different objective, chosen so a variable sits AT its lower bound at
# the optimum: minimise -5x - y puts the answer at (6, 0), row 2 slack (30 < 45, dual 0), and
# the bound multiplier of y is 4 — which is precisely lp_solve's reduced cost for y.
fn _lp2_c() -> List[Float64]:
    return _floats(-5.0, -1.0)


fn main() raises:
    var passed = 0
    var failed = 0

    var no_a = List[Float64]()
    var no_i = List[Int]()
    var no_f = List[Float64]()
    var free2 = _ints(0, 0)
    var lb2 = _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER)

    # ── 1. the closed form: Q = 2I, no constraints, x = -c/2 ──────────────────
    # f = x1² + x2² - 4x1 - 6x2, minimised at (2, 3) with value 4 + 9 - 8 - 18 = -13.
    var q2i = _floats(2.0, 0.0, 0.0, 2.0)
    var unc = qp_solve_default(
        q2i, 2, _floats(-4.0, -6.0), no_a, 0, no_i, no_f,
        _zeros(2), _zeros(2), free2, UInt64(11),
    )
    if (
        unc.status == QP_OPTIMAL
        and unc.proven_optimal
        and unc.certified
        and unc.convex
        and unc.symmetric
        and _exact(unc.x, _floats(2.0, 3.0))
        and unc.objective == -13.0
        and unc.has_bound
        and unc.best_bound == -13.0
        and unc.has_gap
        and unc.gap == 0.0
        and unc.stationarity_ok
        and unc.primal_ok
        and unc.dual_ok
        and unc.slackness_ok
        and unc.n_active == 0
        and _exact(unc.lower_duals, _zeros(2))
        and _exact(unc.upper_duals, _zeros(2))
        and _invariant(unc)
    ):
        passed += 1
        print("  ✅ unconstrained Q=2I gives exactly -c/2 = (2, 3), objective -13")
    else:
        failed += 1
        print(
            "  ❌ unconstrained closed form wrong:", unc.status, unc.objective,
            len(unc.x), unc.gap, unc.certified,
        )

    # ── 2. one equality constraint: the KKT system is 2x2 and exact ───────────
    # minimise x1² + x2² subject to x1 + x2 = 1.  2x + μ(1,1) = 0 and x1 + x2 = 1 give
    # x = (1/2, 1/2), μ = -1, objective 1/2. ∂f*/∂b = 1: f*(b) = b²/2, derivative b = 1.
    var eq = qp_solve_default(
        q2i, 2, _zeros(2), _floats(1.0, 1.0), 1, _ints(SENSE_EQ), _floats(1.0),
        _zeros(2), _zeros(2), free2, UInt64(3),
    )
    if (
        eq.status == QP_OPTIMAL
        and eq.proven_optimal
        and _exact(eq.x, _floats(0.5, 0.5))
        and eq.objective == 0.5
        and _exact(eq.duals, _floats(1.0))
        and eq.duals[0] == 1.0
        and eq.n_active == 1
        and eq.rank_active == 1
        and not eq.degenerate_active_set
        and eq.gap == 0.0
        and _invariant(eq)
    ):
        passed += 1
        print("  ✅ equality-constrained KKT solved exactly: x=(.5,.5), dual +1")
    else:
        failed += 1
        print(
            "  ❌ equality KKT wrong:", eq.status, eq.objective, len(eq.duals),
            eq.duals[0] if len(eq.duals) > 0 else -99.0,
        )

    # ── 3. an inequality that binds ───────────────────────────────────────────
    # minimise x1² + x2² - 2x1 - 4x2 subject to x1 + x2 <= 2. Unconstrained the minimum is
    # (1, 2), which violates the row, so it binds: 2x1 - 2 + μ = 0, 2x2 - 4 + μ = 0,
    # x1 + x2 = 2 give μ = 1, x = (0.5, 1.5), objective 0.25 + 2.25 - 1 - 6 = -4.5, and the
    # reported dual is -1.
    var c34 = _floats(-2.0, -4.0)
    var ineq = qp_solve_default(
        q2i, 2, c34, _floats(1.0, 1.0), 1, _ints(SENSE_LE), _floats(2.0),
        _zeros(2), _zeros(2), free2, UInt64(5),
    )
    if (
        ineq.status == QP_OPTIMAL
        and ineq.proven_optimal
        # 1e-15 rather than `==`: the step to the boundary is `alpha = 2/3`, which no
        # binary float represents, so the coordinates carry one ulp of that division. The
        # DUAL is exact, because the unnormalised orthogonalisation divides by `||(1,1)||² = 2`.
        and _all_close(ineq.x, _floats(0.5, 1.5), 1e-15)
        and ineq.objective == -4.5
        and _exact(ineq.duals, _floats(-1.0))
        and ineq.binding[0]
        and ineq.row_active[0]
        and ineq.slack[0] == 0.0
        and ineq.activity[0] == 2.0
        and _invariant(ineq)
    ):
        passed += 1
        print("  ✅ binding inequality: x=(.5,1.5), objective -4.5, dual -1")
    else:
        failed += 1
        print("  ❌ binding inequality wrong:", ineq.status, ineq.objective, len(ineq.x))

    # ── 4. THE differential oracle: Q = 0 must reproduce lp_solve exactly ─────
    var z4 = _zeros(4)
    var oracle = lp_solve_default(
        _lp_c(), _lp_a(), 2, 2, _ints(SENSE_LE, SENSE_LE), _lp_b(), False
    )
    var as_qp = qp_solve_default(
        z4, 2, _lp_c(), _lp_a(), 2, _ints(SENSE_LE, SENSE_LE), _lp_b(),
        _zeros(2), _zeros(2), lb2, UInt64(17),
    )
    if (
        oracle.status == LP_OPTIMAL
        and as_qp.status == QP_OPTIMAL
        and as_qp.proven_optimal
        and _close(as_qp.objective, oracle.objective, 1e-9)
        and _close(as_qp.objective, -41.25, 1e-9)
        and _all_close(as_qp.x, oracle.x, 1e-9)
        and _all_close(as_qp.x, _floats(2.25, 3.75), 1e-9)
        and _all_close(as_qp.duals, oracle.duals, 1e-9)
        and _all_close(as_qp.duals, _floats(-1.25, -0.75), 1e-9)
        and _all_close(as_qp.lower_duals, oracle.reduced_costs, 1e-9)
        and as_qp.q_rank == 0
        and as_qp.convex
        and _invariant(as_qp)
    ):
        passed += 1
        print("  ✅ zero Hessian matches lp_solve to 1e-9 on x, objective AND duals")
    else:
        failed += 1
        print(
            "  ❌ zero-Hessian cross-check wrong:", as_qp.status, as_qp.objective,
            oracle.objective, len(as_qp.x),
        )
        if len(as_qp.duals) == 2:
            print("     mine", as_qp.duals[0], as_qp.duals[1])
        if len(oracle.duals) == 2:
            print("     lp  ", oracle.duals[0], oracle.duals[1])

    # ── 4b. a bound multiplier IS a reduced cost ──────────────────────────────
    var oracle2 = lp_solve_default(
        _lp2_c(), _lp_a(), 2, 2, _ints(SENSE_LE, SENSE_LE), _lp_b(), False
    )
    var as_qp2 = qp_solve_default(
        z4, 2, _lp2_c(), _lp_a(), 2, _ints(SENSE_LE, SENSE_LE), _lp_b(),
        _zeros(2), _zeros(2), lb2, UInt64(23),
    )
    if (
        as_qp2.status == QP_OPTIMAL
        and _close(as_qp2.objective, -30.0, 1e-9)
        and _all_close(as_qp2.x, _floats(6.0, 0.0), 1e-9)
        and _all_close(as_qp2.duals, _floats(-5.0, 0.0), 1e-9)
        and _all_close(as_qp2.lower_duals, _floats(0.0, 4.0), 1e-9)
        and _all_close(as_qp2.lower_duals, oracle2.reduced_costs, 1e-9)
        and as_qp2.lower_active[1]
        and not as_qp2.lower_active[0]
        and _invariant(as_qp2)
    ):
        passed += 1
        print("  ✅ a variable at its lower bound carries lp_solve's reduced cost, 4")
    else:
        failed += 1
        print(
            "  ❌ reduced-cost cross-check wrong:", as_qp2.status, as_qp2.objective,
            len(as_qp2.lower_duals),
        )

    # ── 5. a box bound that cuts off the unconstrained minimum ────────────────
    # minimise x² - 4x with x <= 1. Unconstrained the minimum is 2, so the cap binds:
    # x = 1, objective -3, and ∂f*/∂u = 2(1) - 4 = -2 (raising the cap lowers the minimum).
    var boxed = qp_solve_default(
        _floats(2.0), 1, _floats(-4.0), no_a, 0, no_i, no_f,
        _floats(0.0), _floats(1.0), _ints(VAR_FLAG_HAS_UPPER), UInt64(29),
    )
    if (
        boxed.status == QP_OPTIMAL
        and boxed.proven_optimal
        and _exact(boxed.x, _floats(1.0))
        and boxed.objective == -3.0
        and _exact(boxed.upper_duals, _floats(-2.0))
        and _exact(boxed.lower_duals, _floats(0.0))
        and boxed.upper_active[0]
        and boxed.gap == 0.0
        and _invariant(boxed)
    ):
        passed += 1
        print("  ✅ an active upper bound has multiplier Qx+c = -2 at x = 1")
    else:
        failed += 1
        print(
            "  ❌ box bound wrong:", boxed.status, boxed.objective,
            boxed.upper_duals[0] if len(boxed.upper_duals) == 1 else -99.0,
        )

    # ── 6. the Euclidean projection onto the unit simplex, closed form ────────
    # minimise 0.5||x - z||² over Σx = 1, x >= 0, which is  Q = I, c = -z  plus a constant.
    # For z = (0.5, 0.6, 0.9) the projection is z - θ with θ = (Σz - 1)/3 = 1/3, all
    # components positive, so x = (1/6, 4/15, 17/30).
    #
    # The dual is -1/3, not +1/3, and the sign is worth deriving rather than guessing:
    # stationarity is x - z = dual·(1,1,1), so summing gives Σz + 3·dual = b and
    # dual = (b - Σz)/3 = -1/3 at b = 1. As a sensitivity that reads correctly too —
    # RAISING the budget of a projection whose unconstrained optimum sums to 2 moves the
    # answer TOWARDS z, so the minimum falls at rate 1/3. (The equality-constrained case in
    # test 2 has a POSITIVE dual for the same reason run the other way, which is why both are
    # here: a sign convention that only ever gets exercised in one direction is not tested.)
    var q_i3 = _floats(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    var proj = qp_solve_default(
        q_i3, 3, _floats(-0.5, -0.6, -0.9), _floats(1.0, 1.0, 1.0), 1, _ints(SENSE_EQ),
        _floats(1.0), _zeros(3), _zeros(3), _rep(VAR_FLAG_HAS_LOWER, 3), UInt64(31),
    )
    var theta = 1.0 / 3.0
    if (
        proj.status == QP_OPTIMAL
        and proj.proven_optimal
        and _all_close(
            proj.x, _floats(0.5 - theta, 0.6 - theta, 0.9 - theta), 1e-12
        )
        and _close(proj.duals[0], -theta, 1e-15)
        and _all_close(proj.lower_duals, _zeros(3), 1e-12)
        and _close(proj.activity[0], 1.0, 1e-12)
        and _invariant(proj)
    ):
        passed += 1
        print("  ✅ projection onto the simplex matches the closed form z - 1/3")
    else:
        failed += 1
        print("  ❌ simplex projection wrong:", proj.status, len(proj.x))
        if len(proj.x) == 3:
            print("     x", proj.x[0], proj.x[1], proj.x[2])

    # ── 7. a non-convex Q is refused, with the failing pivot ──────────────────
    # Q = [[1,2],[2,1]] has eigenvalues 3 and -1. The pivoted LDLᵀ takes the pivot 1 and the
    # Schur complement is 1 - 2·(1/1)·2 = -3, which is the value reported.
    var indef = qp_solve_default(
        _floats(1.0, 2.0, 2.0, 1.0), 2, _zeros(2), no_a, 0, no_i, no_f,
        _zeros(2), _zeros(2), free2, UInt64(37),
    )
    var indef_cv = qp_convexity_flat(_floats(1.0, 2.0, 2.0, 1.0), 2)
    if (
        indef.status == QP_ERR_NOT_CONVEX
        and not indef.convex
        and indef.symmetric
        and len(indef.x) == 0
        and not indef.has_objective
        and not indef.certified
        and indef_cv.status == QP_ERR_NOT_CONVEX
        and not indef_cv.convex
        and not indef_cv.positive_definite
        and indef_cv.fail_value == -3.0
        and indef_cv.rank == 1
        and _invariant(indef)
    ):
        passed += 1
        print("  ✅ an indefinite Q is refused, naming the -3 pivot, with no answer")
    else:
        failed += 1
        print(
            "  ❌ non-convex handling wrong:", indef.status, indef_cv.fail_value,
            indef_cv.rank, len(indef.x),
        )

    # ── 8. an asymmetric Q is refused, with the measured asymmetry ────────────
    var asym_q = _floats(2.0, 1.0, 0.0, 2.0)
    var asym = qp_solve_default(
        asym_q, 2, _zeros(2), no_a, 0, no_i, no_f, _zeros(2), _zeros(2), free2, UInt64(41)
    )
    var asym_cv = qp_convexity_flat(asym_q, 2)
    if (
        asym.status == QP_ERR_NOT_SYMMETRIC
        and not asym.symmetric
        and asym.asymmetry == 1.0
        and len(asym.x) == 0
        and not asym.has_objective
        and asym_cv.status == QP_ERR_NOT_SYMMETRIC
        and asym_cv.asymmetry == 1.0
        and len(asym_cv.q_sym) == 0
        and _invariant(asym)
    ):
        passed += 1
        print("  ✅ an asymmetric Q is refused with asymmetry 1.0 measured, not repaired")
    else:
        failed += 1
        print("  ❌ asymmetry handling wrong:", asym.status, asym.asymmetry, len(asym.x))

    # ── 9. infeasible, and STILL infeasible under 200 large-rhs rows ──────────
    # {x >= 3, x <= 2} has no point. Adding 200 rows of `x <= 1e7` changes nothing about
    # that — but a feasibility tolerance scaled by Σ|b_i| becomes 2e9·tol and swallows the
    # unit-sized contradiction whole, which is how tier 1 reported an infeasible LP OPTIMAL.
    var big_a = _floats(1.0, 1.0)
    var big_s = _ints(SENSE_GE, SENSE_LE)
    var big_b = _floats(3.0, 2.0)
    for _ in range(200):
        big_a.append(1.0)
        big_s.append(SENSE_LE)
        big_b.append(1.0e7)
    var infeas = qp_solve_default(
        _floats(2.0), 1, _floats(0.0), big_a, 202, big_s, big_b,
        _floats(0.0), _floats(0.0), _ints(0), UInt64(43),
    )
    if (
        infeas.status == QP_INFEASIBLE
        and len(infeas.x) == 0
        and not infeas.has_objective
        and not infeas.feasible
        and not infeas.proven_optimal
        and not infeas.has_bound
        and _invariant(infeas)
    ):
        passed += 1
        print("  ✅ a flat contradiction stays infeasible behind 200 rows of rhs 1e7")
    else:
        failed += 1
        print(
            "  ❌ per-row infeasibility wrong:", infeas.status, len(infeas.x),
            infeas.objective, infeas.primal_violation,
        )

    # ── 9b. the same 200 rows, satisfiable, must NOT be called infeasible ─────
    # The mirror of 9: a program whose rows genuinely hold at a magnitude of 1e7 is optimal.
    # The same test has to get both right, which is what a per-row tolerance does and a
    # global one cannot.
    var ok_a = _floats(1.0)
    var ok_s = _ints(SENSE_GE)
    var ok_b = _floats(3.0)
    for _ in range(200):
        ok_a.append(1.0)
        ok_s.append(SENSE_LE)
        ok_b.append(1.0e7)
    var big_ok = qp_solve_default(
        _floats(2.0), 1, _floats(0.0), ok_a, 201, ok_s, ok_b,
        _floats(0.0), _floats(0.0), _ints(0), UInt64(43),
    )
    if (
        big_ok.status == QP_OPTIMAL
        and big_ok.proven_optimal
        and _close(big_ok.x[0], 3.0, 1e-9)
        and _close(big_ok.objective, 9.0, 1e-8)
        and _invariant(big_ok)
    ):
        passed += 1
        print("  ✅ the same 200 large rows, satisfiable, solve to x = 3 (objective 9)")
    else:
        failed += 1
        print("  ❌ large-rhs feasible case wrong:", big_ok.status, big_ok.objective)

    # ── 10. unbounded below: flat curvature along a feasible descent ray ──────
    # minimise x1² - x2 with x1, x2 >= 0. Q = diag(2, 0) is convex and singular, and x2 can
    # grow forever, so there is no minimum. The ray is (0, 1): Q·(0,1) = 0 and cᵀ(0,1) = -1.
    var unb = qp_solve_default(
        _floats(2.0, 0.0, 0.0, 0.0), 2, _floats(0.0, -1.0), no_a, 0, no_i, no_f,
        _zeros(2), _zeros(2), lb2, UInt64(47),
    )
    if (
        unb.status == QP_UNBOUNDED
        and len(unb.x) == 0
        and not unb.has_objective
        and not unb.has_bound
        and not unb.proven_optimal
        and len(unb.ray) == 2
        and _close(unb.ray[0], 0.0, 1e-12)
        and _close(unb.ray[1], 1.0, 1e-12)
        and unb.convex
        and unb.q_rank == 1
        and _invariant(unb)
    ):
        passed += 1
        print("  ✅ an unbounded convex QP reports the ray (0,1) and no objective")
    else:
        failed += 1
        print(
            "  ❌ unbounded handling wrong:", unb.status, len(unb.x), len(unb.ray),
            unb.objective,
        )

    # ── 11. a truncated search sandwiches the optimum instead of claiming it ──
    # The zero-Hessian program again, with an iteration cap that lets phase 1 finish and cuts
    # the active-set search short. The honest report is: a feasible point (so its objective is
    # an upper bound on the optimum) and a MEASURED linearisation bound below it. -41.25 has
    # to sit between them, and `proven_optimal` has to be False.
    var capped = qp_solve(
        z4, 2, _lp_c(), _lp_a(), 2, _ints(SENSE_LE, SENSE_LE), _lp_b(),
        _zeros(2), _zeros(2), lb2, 2, 1e-9, 1e-9, UInt64(53),
    )
    if (
        capped.status == QP_ITERATION_LIMIT
        and not capped.proven_optimal
        and not capped.certified
        and capped.feasible
        and capped.has_objective
        and capped.objective >= -41.25 - 1e-9
        and capped.has_bound
        and capped.best_bound <= -41.25 + 1e-9
        and capped.has_gap
        and capped.gap > 0.0
        and capped.iterations == 2
        and _invariant(capped)
    ):
        passed += 1
        print("  ✅ an iteration cap reports a feasible point and a bound that bracket -41.25")
    else:
        failed += 1
        print(
            "  ❌ truncation wrong:", capped.status, qp_status_name(capped.status),
            capped.objective, capped.best_bound, capped.gap, capped.iterations,
        )

    # ── 12. the certificate must REJECT: a wrong-SIGN dual on a tight row ─────
    # minimise x² - 2x subject to x <= 2. The optimum is the interior point x = 1 with f = -1
    # and dual 0. The point x = 2 with dual +2 satisfies stationarity (2·2 - 2 = 2·1),
    # primal feasibility (tight) and complementary slackness (the row IS tight, so any dual
    # is allowed) — and is worse, f(2) = 0. ONLY the sign condition on a `<=` row's dual
    # refutes it. This is the shape of tier 1's cost-5 matching certified against a true
    # optimum of 1: the omitted condition was the one the returned answer never exercised.
    var q_1 = _floats(2.0)
    var c_1 = _floats(-2.0)
    var a_1 = _floats(1.0)
    var wrong_sign = qp_kkt_check(
        q_1, 1, c_1, a_1, 1, _ints(SENSE_LE), _floats(2.0), _floats(0.0), _floats(0.0),
        _ints(0), _floats(2.0), _floats(2.0), _floats(0.0), _floats(0.0), 1e-9, 1e-9,
    )
    # And the true optimum of the same program passes every condition.
    var right = qp_kkt_check(
        q_1, 1, c_1, a_1, 1, _ints(SENSE_LE), _floats(2.0), _floats(0.0), _floats(0.0),
        _ints(0), _floats(1.0), _floats(0.0), _floats(0.0), _floats(0.0), 1e-9, 1e-9,
    )
    if (
        not wrong_sign.certified
        and wrong_sign.stationarity_ok
        and wrong_sign.primal_ok
        and wrong_sign.slackness_ok
        and not wrong_sign.dual_ok
        and wrong_sign.dual_violation == 2.0
        and right.certified
        and right.objective == -1.0
    ):
        passed += 1
        print("  ✅ a wrong-sign dual on a tight row is refused; the real optimum passes")
    else:
        failed += 1
        print(
            "  ❌ dual-sign condition wrong:", wrong_sign.certified, wrong_sign.dual_ok,
            wrong_sign.dual_violation, right.certified,
        )

    # ── 13. the certificate must REJECT: a priced row that is not tight ───────
    # Same objective, row x <= 5. Take x = 0.75 and dual -0.5: stationarity holds exactly
    # (2·0.75 - 2 = -0.5), the row holds with slack 4.25, the dual has the right SIGN — and
    # f(0.75) = -0.9375 is worse than -1. Only complementary slackness sees it, and only in
    # the "a nonzero dual implies a tight row" direction.
    var priced_slack = qp_kkt_check(
        q_1, 1, c_1, a_1, 1, _ints(SENSE_LE), _floats(5.0), _floats(0.0), _floats(0.0),
        _ints(0), _floats(0.75), _floats(-0.5), _floats(0.0), _floats(0.0), 1e-9, 1e-9,
    )
    if (
        not priced_slack.certified
        and priced_slack.stationarity_ok
        and priced_slack.primal_ok
        and priced_slack.dual_ok
        and not priced_slack.slackness_ok
        and _close(priced_slack.slack_dual_violation, 0.5, 1e-12)
        and _close(priced_slack.dual_slack_violation, 4.25, 1e-12)
        and priced_slack.objective == -0.9375
    ):
        passed += 1
        print("  ✅ a nonzero dual on a slack row is refused, both magnitudes reported")
    else:
        failed += 1
        print(
            "  ❌ slackness condition wrong:", priced_slack.certified,
            priced_slack.slackness_ok, priced_slack.slack_dual_violation,
            priced_slack.dual_slack_violation,
        )

    # ── 14. the certificate must REJECT: a multiplier on an undeclared bound ──
    # No rows at all, no bounds declared, x = 2 (the unconstrained minimum is 1). Stationarity
    # is "satisfied" only because a lower-bound multiplier of 2 was invented for a bound the
    # caller never stated. Without condition 3 covering ABSENT bounds, every point in R^n
    # certifies.
    var ghost = qp_kkt_check(
        q_1, 1, c_1, no_a, 0, no_i, no_f, _floats(0.0), _floats(0.0), _ints(0),
        _floats(2.0), no_f, _floats(2.0), _floats(0.0), 1e-9, 1e-9,
    )
    if (
        not ghost.certified
        and ghost.stationarity_ok
        and not ghost.dual_ok
        and ghost.dual_violation == 2.0
        and ghost.objective == 0.0
    ):
        passed += 1
        print("  ✅ a multiplier on a bound that was never declared is refused")
    else:
        failed += 1
        print(
            "  ❌ undeclared-bound multiplier accepted:", ghost.certified, ghost.dual_ok,
            ghost.dual_violation,
        )

    # ── 15. a nan must not defeat a threshold silently ────────────────────────
    # `dual_tol = tol * (1 + nan)` is nan, every `fabs(d) > nan` is False, and an audit that
    # computes its tolerance before validating its inputs passes having counted zero
    # violations. Finiteness is therefore established first, and the status says so.
    var nan_dual = 0.0
    nan_dual = nan_dual / nan_dual
    var poisoned = qp_kkt_check(
        q_1, 1, c_1, a_1, 1, _ints(SENSE_LE), _floats(2.0), _floats(0.0), _floats(0.0),
        _ints(0), _floats(1.0), _floats(nan_dual), _floats(0.0), _floats(0.0), 1e-9, 1e-9,
    )
    if (
        not poisoned.certified
        and poisoned.status == MODEL_ERR_NON_FINITE_POINT
        and not poisoned.has_objective
    ):
        passed += 1
        print("  ✅ a nan dual is rejected before any tolerance is computed from it")
    else:
        failed += 1
        print("  ❌ nan dual not rejected:", poisoned.certified, poisoned.status)

    # ── 16. the measured gap at a deliberately suboptimal feasible point ──────
    # Program 3 at x = (0, 0): f = 0, g = (-2, -4), and minimising gᵀz over
    # {z1 + z2 <= 2, z >= 0} puts z at (0, 2) for -8. So the bound is -8 and the gap is 8 —
    # both exact — and the true optimum -4.5 lies inside, which is what a bound must do.
    var gap0 = qp_gap_flat(
        q2i, 2, c34, _floats(1.0, 1.0), 1, _ints(SENSE_LE), _floats(2.0), _zeros(2),
        _zeros(2), lb2, _zeros(2), 1000, 1e-9, 1e-9,
    )
    if (
        gap0.status == MODEL_OK
        and gap0.feasible
        and gap0.objective == 0.0
        and gap0.has_bound
        and _close(gap0.best_bound, -8.0, 1e-9)
        and gap0.has_gap
        and _close(gap0.gap, 8.0, 1e-9)
        and gap0.best_bound <= -4.5
    ):
        passed += 1
        print("  ✅ the linearisation bound at (0,0) is exactly -8, gap 8, and brackets -4.5")
    else:
        failed += 1
        print(
            "  ❌ gap driver wrong:", gap0.status, gap0.objective, gap0.best_bound,
            gap0.gap,
        )
    # An INFEASIBLE point bounds nothing, and saying so is the point of the flag.
    var gap_bad = qp_gap_flat(
        q2i, 2, c34, _floats(1.0, 1.0), 1, _ints(SENSE_LE), _floats(2.0), _zeros(2),
        _zeros(2), lb2, _floats(5.0, 5.0), 1000, 1e-9, 1e-9,
    )
    if not gap_bad.feasible and not gap_bad.has_bound and not gap_bad.has_objective:
        passed += 1
        print("  ✅ an infeasible point yields no bound and no objective")
    else:
        failed += 1
        print("  ❌ infeasible point bounded something:", gap_bad.has_bound)

    # ── 17. determinism: the same seed is bit-identical, twice ────────────────
    # A tie-rich program on purpose: minimise 0.5(x1² + x2²) - x1 - x2 with x1 <= 0.5 and
    # x2 <= 0.5. From the origin the exact step is (1, 1) and BOTH rows block at exactly
    # α = 0.5, so which one enters the active set first is decided by the keyed draw. The
    # answer cannot depend on that — x = (0.5, 0.5), f = 0.25 - 1 = -0.75, both duals -0.5 —
    # and the PATH may.
    var q_tie = _floats(1.0, 0.0, 0.0, 1.0)
    var c_tie = _floats(-1.0, -1.0)
    var a_tie = _floats(1.0, 0.0, 0.0, 1.0)
    var s_tie = _ints(SENSE_LE, SENSE_LE)
    var b_tie = _floats(0.5, 0.5)
    var run_a = qp_solve_default(
        q_tie, 2, c_tie, a_tie, 2, s_tie, b_tie, _zeros(2), _zeros(2), free2, UInt64(1)
    )
    var run_a2 = qp_solve_default(
        q_tie, 2, c_tie, a_tie, 2, s_tie, b_tie, _zeros(2), _zeros(2), free2, UInt64(1)
    )
    if (
        run_a.status == QP_OPTIMAL
        and _bits_identical(run_a, run_a2)
        and _exact(run_a.x, _floats(0.5, 0.5))
        and run_a.objective == -0.75
        and _exact(run_a.duals, _floats(-0.5, -0.5))
        and _invariant(run_a)
    ):
        passed += 1
        print("  ✅ the same seed reproduces the answer AND the path signature bit-for-bit")
    else:
        failed += 1
        print(
            "  ❌ same-seed reproduction wrong:", run_a.status, run_a.objective,
            run_a.path_signature, run_a2.path_signature,
        )

    # ── 18. determinism: a different seed moves the PATH, never the ANSWER ────
    var diff_path = False
    var same_answer = True
    var probes = _ints(2, 3, 4, 5, 6, 7, 8, 9)
    for i in range(len(probes)):
        var other = qp_solve_default(
            q_tie, 2, c_tie, a_tie, 2, s_tie, b_tie, _zeros(2), _zeros(2), free2,
            UInt64(probes[i]),
        )
        if other.path_signature != run_a.path_signature:
            diff_path = True
        if (
            other.status != QP_OPTIMAL
            or other.objective != run_a.objective
            or not _exact(other.x, run_a.x)
            or not _exact(other.duals, run_a.duals)
        ):
            same_answer = False
    if diff_path and same_answer:
        passed += 1
        print("  ✅ eight other seeds: the signature moves, the optimum does not")
    else:
        failed += 1
        print("  ❌ seed independence of the answer wrong:", diff_path, same_answer)

    # ── 19. convexity reports rank and definiteness separately ───────────────
    var cv_zero = qp_convexity_flat(z4, 2)
    var cv_semi = qp_convexity_flat(_floats(2.0, 0.0, 0.0, 0.0), 2)
    var cv_pd = qp_convexity_flat(q2i, 2)
    if (
        cv_zero.status == MODEL_OK
        and cv_zero.convex
        and not cv_zero.positive_definite
        and cv_zero.rank == 0
        and cv_semi.convex
        and not cv_semi.positive_definite
        and cv_semi.rank == 1
        and cv_semi.min_pivot == 2.0
        and cv_pd.convex
        and cv_pd.positive_definite
        and cv_pd.rank == 2
        and cv_pd.asymmetry == 0.0
        and len(cv_pd.q_sym) == 4
    ):
        passed += 1
        print("  ✅ convex-but-singular is distinguished from positive definite, with rank")
    else:
        failed += 1
        print(
            "  ❌ convexity report wrong:", cv_zero.rank, cv_semi.rank,
            cv_semi.positive_definite, cv_pd.rank,
        )

    # ── 20. the scalar and vector drivers, and their absent values ────────────
    var ov = qp_objective_flat(q2i, 2, _floats(-4.0, -6.0), _floats(2.0, 3.0))
    var gv = qp_gradient_flat(q2i, 2, _floats(-4.0, -6.0), _floats(2.0, 3.0))
    var gv_bad = qp_gradient_flat(q2i, 2, _floats(-4.0, -6.0), _floats(1.0))
    var ov_huge = qp_objective_flat(
        _floats(1.0e308, 0.0, 0.0, 1.0e308), 2, _zeros(2), _floats(1.0e10, 1.0e10)
    )
    if (
        ov.status == MODEL_OK
        and ov.has_value
        and ov.value == -13.0
        and gv.has_value
        and _exact(gv.values, _zeros(2))
        and not gv_bad.has_value
        and len(gv_bad.values) == 0
        and not ov_huge.has_value
        and ov_huge.value == 0.0
    ):
        passed += 1
        print("  ✅ objective -13 and a zero gradient at the optimum; an overflow is ABSENT")
    else:
        failed += 1
        print(
            "  ❌ scalar/vector drivers wrong:", ov.value, gv.has_value,
            ov_huge.has_value,
        )

    # ── 21. hostile shapes: the A-Z sample call, a wrap, and a payload lie ────
    # `tests/generate_mojo_tests.py` calls every contract function with five-element lists
    # and the integer 5, so this IS the generated call. Without the `dims_fit` guard it
    # indexes q[24] on a five-element list, which is an uncatchable process crash.
    var lf5 = _floats(0.5, 0.5, 0.5, 0.5, 0.5)
    var li5 = _ints(5, 5, 5, 5, 5)
    var az = qp_solve(lf5, 5, lf5, lf5, 5, li5, lf5, lf5, lf5, li5, 5, 0.5, 0.5, UInt64(42))
    # `3 * 6148914691236517206 == 2`, so a multiply is not a bound; `dims_fit` divides.
    var wrapped = qp_solve_default(
        _floats(1.0, 2.0), 6148914691236517206, no_f, no_a, 0, no_i, no_f, no_f, no_f,
        no_i, UInt64(1),
    )
    # A declared dimension the payload cannot justify: `n = 1 << 26` with two entries.
    var unpaid = qp_solve_default(
        _floats(1.0, 2.0), 1 << 26, no_f, no_a, 0, no_i, no_f, no_f, no_f, no_i, UInt64(1)
    )
    if (
        az.status == MODEL_ERR_DENSE_SHAPE
        and len(az.x) == 0
        and wrapped.status == MODEL_ERR_DENSE_SHAPE
        and unpaid.status == MODEL_ERR_DENSE_SHAPE
        and _invariant(az)
    ):
        passed += 1
        print("  ✅ the generated A-Z call, a wrapping n*n and an unpaid n are all rejected")
    else:
        failed += 1
        print(
            "  ❌ shape rejection wrong:", az.status, wrapped.status, unpaid.status,
        )

    # ── 22. the AREA ceiling, exercised with a real allocation ───────────────
    # n = 800 is a legitimate shape by every dimension test — 640000 cells of Q, well under
    # MAX_CSR_DIM — and is still refused, because the internal row system can carry 2n bound
    # rows over 2n split columns and `(0 + 1600) * 1600` is past the area budget. A dimension
    # ceiling cannot see this; only counting the arrays can.
    var q800 = List[Float64]()
    for _ in range(800 * 800):
        q800.append(0.0)
    var too_wide = qp_solve_default(
        q800, 800, _zeros(800), no_a, 0, no_i, no_f, _zeros(800), _zeros(800),
        _rep(0, 800), UInt64(1),
    )
    if too_wide.status == MODEL_ERR_DIMENSION_TOO_LARGE and len(too_wide.x) == 0:
        passed += 1
        print("  ✅ a structurally valid n = 800 is refused by the AREA budget, not indexed")
    else:
        failed += 1
        print("  ❌ area ceiling wrong:", too_wide.status)

    # ── 23. every other input rejection has its own status ────────────────────
    var nan_v = 0.0
    nan_v = nan_v / nan_v
    var bad_q = qp_solve_default(
        _floats(nan_v, 0.0, 0.0, 2.0), 2, _zeros(2), no_a, 0, no_i, no_f, _zeros(2),
        _zeros(2), free2, UInt64(1),
    )
    var bad_b = qp_solve_default(
        q2i, 2, _zeros(2), _floats(1.0, 1.0), 1, _ints(SENSE_LE), _floats(nan_v),
        _zeros(2), _zeros(2), free2, UInt64(1),
    )
    var bad_sense = qp_solve_default(
        q2i, 2, _zeros(2), _floats(1.0, 1.0), 1, _ints(9), _floats(1.0), _zeros(2),
        _zeros(2), free2, UInt64(1),
    )
    var crossed = qp_solve_default(
        q2i, 2, _zeros(2), no_a, 0, no_i, no_f, _floats(1.0, 0.0), _floats(0.0, 0.0),
        _ints(VAR_FLAG_HAS_LOWER | VAR_FLAG_HAS_UPPER, 0), UInt64(1),
    )
    var warm = qp_solve_default(
        q2i, 2, _zeros(2), no_a, 0, no_i, no_f, _zeros(2), _zeros(2),
        _ints(VAR_FLAG_HAS_START, 0), UInt64(1),
    )
    var bad_len = qp_solve_default(
        q2i, 2, _floats(1.0), no_a, 0, no_i, no_f, _zeros(2), _zeros(2), free2, UInt64(1)
    )
    var bad_pol = qp_solve(
        q2i, 2, _zeros(2), no_a, 0, no_i, no_f, _zeros(2), _zeros(2), free2, 1000, 1e-9,
        0.0, UInt64(1),
    )
    if (
        bad_q.status == MODEL_ERR_NON_FINITE_COEFFICIENT
        and bad_b.status == MODEL_ERR_NON_FINITE_RHS
        and bad_sense.status == MODEL_ERR_SENSE
        and crossed.status == MODEL_ERR_BOUNDS_CROSSED
        and warm.status == MODEL_ERR_VAR_FLAGS
        and bad_len.status == MODEL_ERR_LENGTH_MISMATCH
        and bad_pol.status == MODEL_ERR_POLICY
        and len(bad_pol.x) == 0
    ):
        passed += 1
        print("  ✅ non-finite, bad sense, crossed bounds, a warm-start bit and tol 0 all differ")
    else:
        failed += 1
        print(
            "  ❌ rejection statuses wrong:", bad_q.status, bad_b.status,
            bad_sense.status, crossed.status, warm.status, bad_len.status, bad_pol.status,
        )

    # ── 24. a zero-variable program is a feasibility question, answered ───────
    # `0 >= 1` has no solution and `0 <= 1` needs no variables to hold. Neither may crash,
    # and the answers are different.
    var nv_ok = qp_solve_default(
        no_f, 0, no_f, no_a, 1, _ints(SENSE_LE), _floats(1.0), no_f, no_f, no_i, UInt64(1)
    )
    var nv_bad = qp_solve_default(
        no_f, 0, no_f, no_a, 1, _ints(SENSE_GE), _floats(1.0), no_f, no_f, no_i, UInt64(1)
    )
    if (
        nv_ok.status == QP_OPTIMAL
        and nv_ok.objective == 0.0
        and nv_ok.certified
        and nv_ok.feasible
        and len(nv_ok.x) == 0
        and _invariant(nv_ok)
        and nv_bad.status == QP_INFEASIBLE
        and not nv_bad.has_objective
        and _invariant(nv_bad)
    ):
        passed += 1
        print("  ✅ zero variables: `0 <= 1` is optimal at objective 0, `0 >= 1` infeasible")
    else:
        failed += 1
        print("  ❌ zero-variable handling wrong:", nv_ok.status, nv_bad.status)

    # ── 25. the solver's own answers pass the PUBLIC certificate ──────────────
    # The audit inside `qp_solve` and the audit a caller can run must agree; if they can
    # disagree, one of them is not the certificate.
    var recheck = qp_kkt_check(
        q2i, 2, c34, _floats(1.0, 1.0), 1, _ints(SENSE_LE), _floats(2.0), _zeros(2),
        _zeros(2), free2, ineq.x, ineq.duals, ineq.lower_duals, ineq.upper_duals,
        1e-9, 1e-9,
    )
    var recheck2 = qp_kkt_check(
        q_i3, 3, _floats(-0.5, -0.6, -0.9), _floats(1.0, 1.0, 1.0), 1, _ints(SENSE_EQ),
        _floats(1.0), _zeros(3), _zeros(3), _rep(VAR_FLAG_HAS_LOWER, 3), proj.x,
        proj.duals, proj.lower_duals, proj.upper_duals, 1e-9, 1e-9,
    )
    if (
        recheck.certified
        and recheck.status == QP_OPTIMAL
        and recheck.objective == -4.5
        and recheck2.certified
        and recheck2.status == QP_OPTIMAL
    ):
        passed += 1
        print("  ✅ both solved answers re-certify through the public audit")
    else:
        failed += 1
        print(
            "  ❌ public re-certification failed:", recheck.certified, recheck.message,
            recheck2.certified, recheck2.message,
        )

    # ── 26. a per-row dual threshold, not a global one (rule 4b, in dual clothing) ──
    # Q = diag(2e9, 2), c = (-2e9, -2), row x2 >= 0.5. The true optimum is x = (1, 1) with a
    # slack row and a zero dual. The point (1, 1 - 5e-6) with dual -1e-5 satisfies
    # stationarity EXACTLY in both components — 2e9·1 - 2e9 = 0 and 2(1-5e-6) - 2 + 1e-5 = 0 —
    # and is primal feasible, so only conditions 3 and 4 can refute it. And they only do so
    # when their threshold is the scale of the components the ROW touches: component 0's scale
    # is 4e9, so a single shared `tol + eps·max_j scale_j` is 9.2e-4, which swallows both the
    # wrong-SIGN dual (a `>=` row's dual must be >= 0) and the price on a slack row whole.
    var q_scaled = _floats(2.0e9, 0.0, 0.0, 2.0)
    var c_scaled = _floats(-2.0e9, -2.0)
    var hidden = qp_kkt_check(
        q_scaled, 2, c_scaled, _floats(0.0, 1.0), 1, _ints(SENSE_GE), _floats(0.5),
        _zeros(2), _zeros(2), free2, _floats(1.0, 1.0 - 5.0e-6), _floats(-1.0e-5),
        _zeros(2), _zeros(2), 1e-9, 1e-9,
    )
    # The genuine optimum of the same badly scaled program still certifies, so the tighter
    # threshold is not simply refusing everything.
    var scaled_ok = qp_kkt_check(
        q_scaled, 2, c_scaled, _floats(0.0, 1.0), 1, _ints(SENSE_GE), _floats(0.5),
        _zeros(2), _zeros(2), free2, _floats(1.0, 1.0), _floats(0.0), _zeros(2), _zeros(2),
        1e-9, 1e-9,
    )
    if (
        not hidden.certified
        and hidden.stationarity_ok
        and hidden.primal_ok
        and not hidden.dual_ok
        and not hidden.slackness_ok
        and _close(hidden.dual_violation, 1.0e-5, 1e-15)
        and scaled_ok.certified
    ):
        passed += 1
        print("  ✅ a 1e-5 wrong-sign dual is caught next to a 4e9 component scale")
    else:
        failed += 1
        print(
            "  ❌ dual threshold is not per row:", hidden.certified, hidden.dual_ok,
            hidden.slackness_ok, hidden.dual_violation, scaled_ok.certified,
        )

    # ── 27. an infinite bound PADDING must not disable the declared bound's audit ──
    # The module reads a bound value only when its flag is set, so +inf is legitimate padding
    # for "no upper bound" — and a slackness tolerance built from BOTH bounds at once is then
    # `inf`, every `>` is False, and the test on the bound that IS declared passes vacuously.
    # x = 1.25 with a lower bound of 0 (slack 1.25) and a multiplier of 0.5 on it. Stationarity
    # holds exactly — `Qx + c = 2(1.25) - 2 = 0.5` and the convention is
    # `Qx + c == Aᵀduals + lower_duals + upper_duals` — the bound holds, the sign is right
    # (a lower bound's dual is >= 0), and f(1.25) = -0.9375 is worse than the true -1. Only
    # complementary slackness refutes it, and only if `+inf` in the OTHER bound's slot has not
    # silently turned its threshold into infinity.
    var inf_pad = 1.0e308 * 10.0
    var padded = qp_kkt_check(
        q_1, 1, c_1, no_a, 0, no_i, no_f, _floats(0.0), _floats(inf_pad),
        _ints(VAR_FLAG_HAS_LOWER), _floats(1.25), no_f, _floats(0.5), _floats(0.0),
        1e-9, 1e-9,
    )
    if (
        not padded.certified
        and padded.stationarity_ok
        and padded.primal_ok
        and padded.dual_ok
        and not padded.slackness_ok
        and _close(padded.slack_dual_violation, 0.5, 1e-15)
        and _close(padded.dual_slack_violation, 1.25, 1e-15)
        and padded.objective == -0.9375
    ):
        passed += 1
        print("  ✅ +inf padding on an undeclared bound does not disable the declared one")
    else:
        failed += 1
        print(
            "  ❌ inf padding defeated the audit:", padded.certified,
            padded.slackness_ok, padded.slack_dual_violation,
        )
    # And the same padding on a real solve is simply ignored, as documented.
    var padded_solve = qp_solve_default(
        q_1, 1, c_1, no_a, 0, no_i, no_f, _floats(0.0), _floats(inf_pad),
        _ints(VAR_FLAG_HAS_LOWER), UInt64(59),
    )
    if (
        padded_solve.status == QP_OPTIMAL
        and _exact(padded_solve.x, _floats(1.0))
        and padded_solve.objective == -1.0
        and _exact(padded_solve.lower_duals, _floats(0.0))
        and _invariant(padded_solve)
    ):
        passed += 1
        print("  ✅ an unflagged bound value is never read: +inf padding solves to x = 1")
    else:
        failed += 1
        print("  ❌ padding was read:", padded_solve.status, padded_solve.objective)

    # ── 28. an all-zero row is a real row, and its two cases differ ───────────
    # `0·x <= 0` constrains nothing and is always tight, so it enters the active set, cannot
    # be scaled into gradient units, and is DEPENDENT — the situation that makes a multiplier
    # ambiguous. The answer must still be the unconstrained one, the flag must say the active
    # set was degenerate, and `0·x <= -1` must come back infeasible rather than crash on a
    # zero row norm.
    var zero_row_ok = qp_solve_default(
        q_1, 1, c_1, _floats(0.0), 1, _ints(SENSE_LE), _floats(0.0), _floats(0.0),
        _floats(0.0), _ints(0), UInt64(61),
    )
    var zero_row_bad = qp_solve_default(
        q_1, 1, c_1, _floats(0.0), 1, _ints(SENSE_LE), _floats(-1.0), _floats(0.0),
        _floats(0.0), _ints(0), UInt64(61),
    )
    if (
        zero_row_ok.status == QP_OPTIMAL
        and _exact(zero_row_ok.x, _floats(1.0))
        and zero_row_ok.objective == -1.0
        and _exact(zero_row_ok.duals, _floats(0.0))
        and zero_row_ok.degenerate_active_set
        and _invariant(zero_row_ok)
        and zero_row_bad.status == QP_INFEASIBLE
        and _invariant(zero_row_bad)
    ):
        passed += 1
        print("  ✅ a zero row: solved with a degenerate active set, or infeasible, not crashed")
    else:
        failed += 1
        print(
            "  ❌ zero-row handling wrong:", zero_row_ok.status,
            zero_row_ok.degenerate_active_set, zero_row_bad.status,
        )

    # ── 29. dependent but consistent equality rows ────────────────────────────
    # x1 + x2 = 1 and 2x1 + 2x2 = 2 say the same thing twice. The active set then has rank 1
    # with two members, so one multiplier is arbitrary — the module sets the dependent one to
    # zero and says so — and the certificate has to pass on the numbers actually returned:
    # (1, 1) = 1·(1,1) + 0·(2,2) holds, so the audit is satisfiable and must be satisfied.
    var dup = qp_solve_default(
        q2i, 2, _zeros(2), _floats(1.0, 1.0, 2.0, 2.0), 2, _ints(SENSE_EQ, SENSE_EQ),
        _floats(1.0, 2.0), _zeros(2), _zeros(2), free2, UInt64(67),
    )
    var dup_recheck = qp_kkt_check(
        q2i, 2, _zeros(2), _floats(1.0, 1.0, 2.0, 2.0), 2, _ints(SENSE_EQ, SENSE_EQ),
        _floats(1.0, 2.0), _zeros(2), _zeros(2), free2, dup.x, dup.duals, dup.lower_duals,
        dup.upper_duals, 1e-9, 1e-9,
    )
    if (
        dup.status == QP_OPTIMAL
        and _exact(dup.x, _floats(0.5, 0.5))
        and dup.objective == 0.5
        and dup.n_active == 2
        and dup.rank_active == 1
        and dup.degenerate_active_set
        and dup_recheck.certified
        and _invariant(dup)
    ):
        passed += 1
        print("  ✅ a duplicated equality row is degenerate, solved, and still certifiable")
    else:
        failed += 1
        print(
            "  ❌ dependent equality rows wrong:", dup.status, dup.rank_active,
            dup.n_active, dup_recheck.certified, dup_recheck.message,
        )

    # ── 30. randomised instances, checked against SAMPLED feasible points ─────
    # No second solver is needed to test optimality on a box: every point of the box is
    # feasible, so `f(x*) <= f(y)` for a sample of `y` is a direct check of the claim the
    # status makes. `Q = L Lᵀ` is positive semidefinite by construction (and singular
    # whenever `L` is), the box is bounded, so a minimum EXISTS for every instance and
    # `QP_OPTIMAL` is the only acceptable status — which is what catches a wrong drop rule,
    # a step that overshoots a bound, or a certificate that gives up on a hard face.
    #
    # Every draw is `determinism.counter_rng.rng_uniform`, a counter-based generator, so the
    # instances are a pure function of their coordinates: this test is reproducible, and a
    # failure can be reproduced by hand from the printed instance index.
    var all_optimal = True
    var all_minimal = True
    var worst_over: Float64 = 0.0
    var bad_case = -1
    for inst in range(12):
        var seed_i = UInt64(1000 + inst)
        # `L` is 3 x rank with rank cycling 1, 2, 3, so a third of the instances have a
        # SINGULAR Hessian — the case that both needs the pivoting and admits a flat
        # direction — rather than a generically definite one.
        var rank = 1 + inst % 3
        var l = _zeros(3 * rank)
        for r in range(3):
            for cc in range(rank):
                l[r * rank + cc] = 2.0 * rng_uniform(
                    seed_i, 1, 0, 0, 0, 9, UInt64(r * 3 + cc)
                ) - 1.0
        var qq = _zeros(9)
        for i in range(3):
            for j in range(3):
                var acc: Float64 = 0.0
                for t in range(rank):
                    acc += l[i * rank + t] * l[j * rank + t]
                qq[i * 3 + j] = acc
        var cc2 = _zeros(3)
        for j in range(3):
            cc2[j] = 2.0 * rng_uniform(seed_i, 2, 0, 0, 0, 9, UInt64(j)) - 1.0
        # A row, kept satisfiable by construction: the origin is always inside it.
        var arow = _zeros(3)
        for j in range(3):
            arow[j] = rng_uniform(seed_i, 3, 0, 0, 0, 9, UInt64(j))
        var brow = _floats(1.5)
        var sol = qp_solve_default(
            qq, 3, cc2, arow, 1, _ints(SENSE_LE), brow, _zeros(3), _floats(1.0, 1.0, 1.0),
            _rep(VAR_FLAG_HAS_LOWER | VAR_FLAG_HAS_UPPER, 3), seed_i,
        )
        if sol.status != QP_OPTIMAL or not sol.proven_optimal or not _invariant(sol):
            all_optimal = False
            if bad_case < 0:
                bad_case = inst
            continue
        for trial in range(150):
            var y = _zeros(3)
            var total: Float64 = 0.0
            for j in range(3):
                y[j] = rng_uniform(seed_i, 4, UInt64(trial), 0, 0, 9, UInt64(j))
                total += arow[j] * y[j]
            if total > 1.5:
                continue
            var fy = qp_objective_flat(qq, 3, cc2, y)
            if fy.has_value and sol.objective > fy.value + 1e-9:
                all_minimal = False
                if sol.objective - fy.value > worst_over:
                    worst_over = sol.objective - fy.value
                    bad_case = inst
    if all_optimal and all_minimal:
        passed += 1
        print("  ✅ 12 random PSD instances all solve, and beat 150 sampled feasible points each")
    else:
        failed += 1
        print(
            "  ❌ randomised check failed:", all_optimal, all_minimal, "instance",
            bad_case, "excess", worst_over,
        )

    # ── 31. a PSD matrix that needs a LATE pivot, and a singular Hessian ──────
    # Q = L Lᵀ with L = [[2,0],[1,0],[1,1]]:  [[4,2,2],[2,1,1],[2,1,2]]. Positive semidefinite
    # by construction, rank 2, det 0. It is here because of HOW it factors: the largest
    # diagonal is already first, so step 0 does not pivot, and the Schur complement it leaves
    # is [[0,0],[0,1]] — whose largest diagonal is at the SECOND position, forcing a symmetric
    # swap at step 1, after the first elimination has changed the block.
    #
    # A factorisation that updates only the lower triangle leaves the upper triangle holding
    # the ORIGINAL entries, and that swap then moves a stale 1 into the position where a 0
    # belongs: the next pivot comes out as -1 and this matrix is reported NOT CONVEX. Every
    # earlier assertion in this file involves a matrix that never pivots after step 0, so all
    # of them passed while `Q = L Lᵀ` — the way anybody constructs a covariance — was being
    # refused.
    #
    # The pivots are read off the EQUILIBRATED matrix (see `_ldl_factor`), so the order is by
    # RELATIVE size: `S = diag(1/2, 1, 1)` gives `Q~ = [[1,1,1],[1,1,1],[1,1,2]]`, whose
    # largest diagonal is at index 2, so index 2 is eliminated first. In the CALLER's units —
    # which is what `min_pivot` reports — those pivots are the Schur complements of Q under
    # the order (3, 2, 1): `Q_33 = 2`, then `Q_22 - Q_23²/Q_33 = 1 - 1/2 = 0.5`, then a dead
    # trailing entry. So `min_pivot == 0.5` and the rank is still 2. Under the old
    # largest-ABSOLUTE-diagonal order the pivots were 4 and 1; both sequences are legitimate
    # factorisations of the same matrix, and the equilibrated order is the one whose tolerance
    # means anything (test 33 is why).
    var q_pivot = _floats(4.0, 2.0, 2.0, 2.0, 1.0, 1.0, 2.0, 1.0, 2.0)
    var cv_pivot = qp_convexity_flat(q_pivot, 3)
    # And a solve on it, chosen so the singular direction is harmless: the null space is
    # spanned by (1, -2, 0) and c = (2, 1, 0) is orthogonal to it, so a minimum EXISTS and is
    # not unique. Any stationary point has `Qx = -c`, hence `f = 0.5·cᵀx = -1` — the same
    # value at every minimiser, which is exactly what makes this assertable without pinning x.
    var singular = qp_solve_default(
        q_pivot, 3, _floats(2.0, 1.0, 0.0), no_a, 0, no_i, no_f, _zeros(3), _zeros(3),
        _rep(0, 3), UInt64(71),
    )
    var grad_at = qp_gradient_flat(q_pivot, 3, _floats(2.0, 1.0, 0.0), singular.x)
    var stationary = grad_at.has_value and _all_close(grad_at.values, _zeros(3), 1e-12)
    if (
        cv_pivot.status == MODEL_OK
        and cv_pivot.convex
        and not cv_pivot.positive_definite
        and cv_pivot.rank == 2
        and cv_pivot.min_pivot == 0.5
        and cv_pivot.fail_index == -1
        and singular.status == QP_OPTIMAL
        and singular.proven_optimal
        and _close(singular.objective, -1.0, 1e-12)
        and stationary
        and singular.q_rank == 2
        and _invariant(singular)
    ):
        passed += 1
        print("  ✅ a PSD matrix needing a late pivot stays convex; its singular QP gives -1")
    else:
        failed += 1
        print(
            "  ❌ late-pivot factorisation wrong:", cv_pivot.status, cv_pivot.convex,
            cv_pivot.rank, cv_pivot.min_pivot, singular.status, singular.objective,
            stationary,
        )

    # ── 32. randomised FREE-variable instances: rays verified independently ───
    # Half of a QP's interesting behaviour only appears when the feasible set is unbounded,
    # and a rank-deficient `Q` with free variables produces that case constantly. Each
    # instance is `Q = L Lᵀ` (PSD, rank cycling so a third are singular), one `<=` row through
    # the box centre, and per-variable lower bounds present or absent by a keyed draw.
    #
    # For every instance the status must be a real answer — optimal, unbounded or infeasible,
    # never `QP_NUMERICAL_BREAKDOWN` and never `QP_NOT_CERTIFIED`, the latter being the status
    # that appeared on 2.4% of such instances while a success required the linearisation bound
    # to EXIST rather than merely not to object.
    #
    # And every `QP_UNBOUNDED` verdict is re-derived here from the caller's own arrays: the
    # returned ray `d` must satisfy `Q d = 0` (no curvature to stop the descent), `cᵀd < 0`
    # (it does descend) and `a_iᵀd <= 0` / `d_j >= 0` (it stays feasible for every `t > 0`).
    # Those three ARE the definition of "no minimum", and checking them is the difference
    # between reporting unboundedness and asserting it.
    var rand_ok = True
    var rays_seen = 0
    var opts_seen = 0
    var why = -1
    for inst in range(24):
        var seed_i = UInt64(7000 + inst)
        var nn = 2 + inst % 4
        var rk = 1 + inst % nn
        var ll = _zeros(nn * rk)
        for r in range(nn):
            for cq in range(rk):
                ll[r * rk + cq] = 2.0 * rng_uniform(
                    seed_i, 2, UInt64(r), 0, 0, 9, UInt64(cq)
                ) - 1.0
        var qr = _zeros(nn * nn)
        for i in range(nn):
            for j in range(nn):
                var acc: Float64 = 0.0
                for t in range(rk):
                    acc += ll[i * rk + t] * ll[j * rk + t]
                qr[i * nn + j] = acc
        var cr = _zeros(nn)
        for j in range(nn):
            cr[j] = 4.0 * rng_uniform(seed_i, 3, 0, 0, 0, 9, UInt64(j)) - 2.0
        var ar = _zeros(nn)
        var centre: Float64 = 0.0
        for j in range(nn):
            ar[j] = 2.0 * rng_uniform(seed_i, 5, 0, 0, 0, 9, UInt64(j)) - 1.0
            centre += ar[j] * 0.5
        var br = _floats(centre + 1.0)
        var fl = List[Int]()
        for j in range(nn):
            if rng_uniform(seed_i, 8, 1, 0, 0, 9, UInt64(j)) < 0.5:
                fl.append(VAR_FLAG_HAS_LOWER)
            else:
                fl.append(0)
        var sr = qp_solve_default(
            qr, nn, cr, ar, 1, _ints(SENSE_LE), br, _zeros(nn), _zeros(nn), fl, seed_i
        )
        if not _invariant(sr):
            rand_ok = False
            why = inst
        if sr.status == QP_OPTIMAL:
            opts_seen += 1
            var rc = qp_kkt_check(
                qr, nn, cr, ar, 1, _ints(SENSE_LE), br, _zeros(nn), _zeros(nn), fl, sr.x,
                sr.duals, sr.lower_duals, sr.upper_duals, 1e-9, 1e-9,
            )
            if not rc.certified:
                rand_ok = False
                why = inst
        elif sr.status == QP_UNBOUNDED:
            rays_seen += 1
            if len(sr.ray) != nn:
                rand_ok = False
                why = inst
            else:
                var curve = qp_gradient_flat(qr, nn, _zeros(nn), sr.ray)
                var slope: Float64 = 0.0
                var reach: Float64 = 0.0
                for j in range(nn):
                    slope += cr[j] * sr.ray[j]
                    reach += ar[j] * sr.ray[j]
                if not curve.has_value or not _all_close(curve.values, _zeros(nn), 1e-9):
                    rand_ok = False
                    why = inst
                if slope >= 0.0 or reach > 1e-9:
                    rand_ok = False
                    why = inst
                for j in range(nn):
                    if has_lower_bound(fl[j]) and sr.ray[j] < -1e-12:
                        rand_ok = False
                        why = inst
        elif sr.status != QP_INFEASIBLE:
            rand_ok = False
            why = inst
    if rand_ok and rays_seen > 0 and opts_seen > 0:
        passed += 1
        print(
            "  ✅ 24 free-variable instances: every optimum re-certifies and every ray"
            " verifies (", opts_seen, "optima,", rays_seen, "rays )",
        )
    else:
        failed += 1
        print(
            "  ❌ randomised free-variable check failed at instance", why, "optima",
            opts_seen, "rays", rays_seen,
        )

    # ── 33. THE MIXED-UNIT INDEFINITE Q THAT WAS SOLVED (rule 4b, max-over-items) ──
    # VERBATIM the reproduction: Q = diag(1e12, -0.5) has eigenvalues 1e12 and -0.5, so it is
    # INDEFINITE and the true minimum over the box [-10,10]² is -25 at (0, ±10). Every pivot
    # tolerance used to be scaled by `max_i |Q_ii|`, so with 1e12 present the negative-pivot
    # test accepted anything above -0.68 in ABSOLUTE units: this call returned QP_OPTIMAL with
    # convex = True, certified = True, proven_optimal = True, gap = 0 and x = (0, 0), and BOTH
    # cross-checks agreed because both inherit the convexity verdict. Q = D S D with
    # D = diag(1e6, 0.1) already exceeds that ratio, so this is a portfolio matrix, not a
    # pathology.
    var q_indef_scaled = _floats(1.0e12, 0.0, 0.0, -0.5)
    var box_flags = _ints(
        VAR_FLAG_HAS_LOWER | VAR_FLAG_HAS_UPPER, VAR_FLAG_HAS_LOWER | VAR_FLAG_HAS_UPPER
    )
    var hidden_indef = qp_solve_default(
        q_indef_scaled, 2, _zeros(2), no_a, 0, no_i, no_f, _floats(-10.0, -10.0),
        _floats(10.0, 10.0), box_flags, UInt64(1),
    )
    var hidden_cv = qp_convexity_flat(q_indef_scaled, 2)
    # Non-diagonally too: det([[1e12,1e6],[1e6,0.5]]) = 5e11 - 1e12 < 0, and f(1e-6, -1) is
    # -0.25 while the old run reported the optimum as 0.0 at (0, 0).
    var q_indef_off = _floats(1.0e12, 1.0e6, 1.0e6, 0.5)
    var hidden_off = qp_solve_default(
        q_indef_off, 2, _zeros(2), no_a, 0, no_i, no_f, _floats(-10.0, -10.0),
        _floats(10.0, 10.0), box_flags, UInt64(1),
    )
    # The measured threshold from the reproduction: -0.68 was accepted as convex, -0.70 was
    # not. Both are now refused, because 0.68 is not a rounding error of anything.
    var cv_068 = qp_convexity_flat(_floats(1.0e12, 0.0, 0.0, -0.68), 2)
    # And the two exported cross-checks must refuse the same data on their own, not because
    # `qp_solve` told them to: neither may certify a point of an indefinite objective.
    var indef_kkt = qp_kkt_check(
        q_indef_scaled, 2, _zeros(2), no_a, 0, no_i, no_f, _floats(-10.0, -10.0),
        _floats(10.0, 10.0), box_flags, _zeros(2), no_f, _zeros(2), _zeros(2), 1e-9, 1e-9,
    )
    var indef_gap = qp_gap_flat(
        q_indef_scaled, 2, _zeros(2), no_a, 0, no_i, no_f, _floats(-10.0, -10.0),
        _floats(10.0, 10.0), box_flags, _zeros(2), 1000, 1e-9, 1e-9,
    )
    if (
        hidden_indef.status == QP_ERR_NOT_CONVEX
        and not hidden_indef.convex
        and not hidden_indef.certified
        and not hidden_indef.proven_optimal
        and not hidden_indef.has_objective
        and len(hidden_indef.x) == 0
        and _invariant(hidden_indef)
        and hidden_cv.status == QP_ERR_NOT_CONVEX
        and not hidden_cv.convex
        and not hidden_cv.positive_definite
        and hidden_cv.fail_index == 1
        and hidden_cv.fail_value == -0.5
        and hidden_off.status == QP_ERR_NOT_CONVEX
        and len(hidden_off.x) == 0
        and _invariant(hidden_off)
        and not cv_068.convex
        and cv_068.fail_value == -0.68
        and not indef_kkt.certified
        and not indef_kkt.convex
        and indef_gap.status == QP_ERR_NOT_CONVEX
        and not indef_gap.has_bound
    ):
        passed += 1
        print("  ✅ Q = diag(1e12, -0.5) is refused, not solved: -0.5 is not 1e12's rounding")
    else:
        failed += 1
        print(
            "  ❌ mixed-unit indefinite Q accepted:", hidden_indef.status,
            hidden_indef.convex, hidden_cv.fail_value, hidden_off.status,
            cv_068.convex, indef_kkt.certified, indef_gap.status,
        )

    # ── 33b. the budget the header states, measured at a scale of 1e12 ────────
    # What "convex" costs is now 1024·eps·(n+1) of the DIAGONAL ENTRIES the pivot belongs to,
    # so the same relative violation is accepted or refused at any scale. `Q = [[1e12, s],
    # [s, 1]]` with `s = 1e6(1 + δ)` has Schur complement `1 - (1+δ)² ≈ -2δ` at a diagonal of
    # 1: δ = 1e-13 gives -2e-13, inside the 6.8e-13 budget, and δ = 1e-11 gives -2e-11, which
    # is not. Under the old max-diagonal tolerance BOTH were "convex" — and so was -0.68.
    var s_in = 1.0e6 * (1.0 + 1.0e-13)
    var s_out = 1.0e6 * (1.0 + 1.0e-11)
    var cv_in = qp_convexity_flat(_floats(1.0e12, s_in, s_in, 1.0), 2)
    var cv_out = qp_convexity_flat(_floats(1.0e12, s_out, s_out, 1.0), 2)
    if (
        cv_in.status == MODEL_OK
        and cv_in.convex
        and cv_in.rank == 1
        and not cv_in.positive_definite
        and cv_out.status == QP_ERR_NOT_CONVEX
        and not cv_out.convex
    ):
        passed += 1
        print("  ✅ the rounding budget is 1e-13 OF THE ENTRY, at a scale of 1e12")
    else:
        failed += 1
        print(
            "  ❌ convexity budget is not entry-relative:", cv_in.convex, cv_in.rank,
            cv_out.convex, cv_out.fail_value,
        )

    # ── 34. THE POSITIVE DEFINITE Q REPORTED UNBOUNDED (the same root cause) ──
    # VERBATIM: Q = diag(1e12, 0.5) is strictly positive definite, c = (0, -1), no rows and no
    # bounds, so the unique minimiser is x = (0, 2) with f* = -1. The zero-curvature tests were
    # scaled by `max|Q|` and `max|Hz|`, so a direction whose real curvature is 0.5 was declared
    # flat next to a diagonal of 1e12: the call returned QP_UNBOUNDED with ray = (0, 1), and
    # `Q·ray = (0, 0.5) ≠ 0` — a ray failing the condition the status advertises — while
    # `qp_convexity_flat` on the identical Q said positive_definite = True in the same run.
    var q_pd_scaled = _floats(1.0e12, 0.0, 0.0, 0.5)
    var c_pd = _floats(0.0, -1.0)
    var pd_solve = qp_solve_default(
        q_pd_scaled, 2, c_pd, no_a, 0, no_i, no_f, _zeros(2), _zeros(2), free2, UInt64(1)
    )
    var pd_cv = qp_convexity_flat(q_pd_scaled, 2)
    # With a row present (`x2 <= 5`, which the optimum satisfies) it also reported unbounded,
    # ray (0, -1).
    var pd_row = qp_solve_default(
        q_pd_scaled, 2, c_pd, _floats(0.0, 1.0), 1, _ints(SENSE_LE), _floats(5.0),
        _zeros(2), _zeros(2), free2, UInt64(1),
    )
    # And inside a box the same mis-scaled test drove the search into 500 zero-curvature steps
    # and an iteration limit at x = (0, -10), objective 35, for a problem with f* = -1.
    var pd_box = qp_solve_default(
        q_pd_scaled, 2, c_pd, no_a, 0, no_i, no_f, _floats(-10.0, -10.0),
        _floats(10.0, 10.0), box_flags, UInt64(1),
    )
    # n = 3, Q = diag(1e13, 2, 3), c = (0, -2, -3): x* = (0, 1, 1) and f* = -1 - 1.5 = -2.5.
    var pd3 = qp_solve_default(
        _floats(1.0e13, 0.0, 0.0, 0.0, 2.0, 0.0, 0.0, 0.0, 3.0), 3,
        _floats(0.0, -2.0, -3.0), no_a, 0, no_i, no_f, _zeros(3), _zeros(3), _rep(0, 3),
        UInt64(1),
    )
    # A realistic mixed-units covariance, D S D with correlation 0.5: det = 1e10 - 2.5e9 > 0,
    # so it is positive definite and f* = -0.5·cᵀQ⁻¹c = -0.5·1e12/7.5e9 = -66.666...
    var pd_cov = qp_solve_default(
        _floats(1.0e12, 5.0e4, 5.0e4, 1.0e-2), 2, c_pd, no_a, 0, no_i, no_f,
        _zeros(2), _zeros(2), free2, UInt64(1),
    )
    if (
        pd_solve.status == QP_OPTIMAL
        and pd_solve.proven_optimal
        and pd_solve.certified
        and pd_solve.convex
        and len(pd_solve.ray) == 0
        and _all_close(pd_solve.x, _floats(0.0, 2.0), 1e-12)
        and _close(pd_solve.objective, -1.0, 1e-12)
        and _invariant(pd_solve)
        and pd_cv.positive_definite
        and pd_cv.rank == 2
        and pd_row.status == QP_OPTIMAL
        and _all_close(pd_row.x, _floats(0.0, 2.0), 1e-12)
        and pd_box.status == QP_OPTIMAL
        and pd_box.n_zero_curvature == 0
        and _all_close(pd_box.x, _floats(0.0, 2.0), 1e-12)
        and pd3.status == QP_OPTIMAL
        and _close(pd3.objective, -2.5, 1e-12)
        and pd_cov.status == QP_OPTIMAL
        and _close(pd_cov.objective, -66.66666666666667, 1e-9)
        and _invariant(pd_cov)
    ):
        passed += 1
        print("  ✅ Q = diag(1e12, 0.5) with c = (0,-1) solves to (0, 2), f = -1, not UNBOUNDED")
    else:
        failed += 1
        print(
            "  ❌ positive definite QP still reported unbounded:", pd_solve.status,
            pd_cv.positive_definite, pd_row.status, pd_box.status,
            pd_box.n_zero_curvature, pd3.status, pd3.objective, pd_cov.status,
            pd_cov.objective,
        )

    # ── 35. SELF-CONSISTENCY: two reports of the same fact must not disagree ──
    # `qp_convexity_flat` and `qp_solve` answer the convexity question with the same code, and
    # the suite asserts it rather than assuming it. Two stronger invariants are asserted with
    # them, because each was violated by a returned struct:
    #   * `positive_definite` implies `rank == n` and `convex`. `rank = 1` beside
    #     `positive_definite = True` says "flat in one direction" and "flat in none" at once,
    #     and a caller can act on neither.
    #   * a positive definite objective is bounded below on EVERY set, so `QP_UNBOUNDED` and
    #     `positive_definite = True` cannot both be reported for one Q.
    var agree = True
    var pd_bad = -1
    for probe in range(7):
        var qp_probe = _zeros(4)
        if probe == 0:
            qp_probe = _floats(1.0e12, 0.0, 0.0, 0.5)
        elif probe == 1:
            qp_probe = _floats(1.0e12, 0.0, 0.0, -0.5)
        elif probe == 2:
            qp_probe = _floats(1.0e12, 1.0e6, 1.0e6, 0.5)
        elif probe == 3:
            qp_probe = _floats(2.0, 0.0, 0.0, 0.0)
        elif probe == 4:
            qp_probe = _floats(1.0e-12, 0.0, 0.0, 1.0e12)
        elif probe == 5:
            qp_probe = _floats(0.0, 0.0, 0.0, 0.0)
        else:
            qp_probe = _floats(2.0, 1.0, 1.0, 2.0)
        var cvp = qp_convexity_flat(qp_probe, 2)
        var slp = qp_solve_default(
            qp_probe, 2, _floats(0.0, -1.0), no_a, 0, no_i, no_f, _floats(-10.0, -10.0),
            _floats(10.0, 10.0), box_flags, UInt64(101 + probe),
        )
        if (
            slp.convex != cvp.convex
            or slp.q_rank != cvp.rank
            or slp.min_pivot != cvp.min_pivot
            or slp.symmetric != cvp.symmetric
            or slp.asymmetry != cvp.asymmetry
        ):
            agree = False
            pd_bad = probe
        if cvp.positive_definite and (cvp.rank != 2 or not cvp.convex):
            agree = False
            pd_bad = probe
        if cvp.positive_definite and slp.status == QP_UNBOUNDED:
            agree = False
            pd_bad = probe
        if not _invariant(slp):
            agree = False
            pd_bad = probe
    if agree:
        passed += 1
        print("  ✅ the convexity report, the rank and the solver's status never contradict")
    else:
        failed += 1
        print("  ❌ self-inconsistent convexity reports at probe", pd_bad)

    # ── 36. min_pivot is the SMALLEST pivot, in the caller's units ────────────
    # It is the number a caller judges conditioning by. `diag(1e12, 0.5)` reported 1e12 — the
    # LARGEST — because the factorisation stopped at the first pivot and never reached 0.5, so
    # the field overstated conditioning by twelve orders of magnitude in the reassuring
    # direction and `rank` claimed a flat direction that does not exist.
    var mp_a = qp_convexity_flat(_floats(1.0e12, 0.0, 0.0, 0.5), 2)
    var mp_b = qp_convexity_flat(_floats(0.5, 0.0, 0.0, 1.0e12), 2)
    var mp_c = qp_convexity_flat(_floats(1.0e-8, 0.0, 0.0, 1.0e8), 2)
    if (
        mp_a.min_pivot == 0.5
        and mp_a.rank == 2
        and mp_b.min_pivot == 0.5
        and mp_b.rank == 2
        and mp_c.min_pivot == 1.0e-8
        and mp_c.rank == 2
    ):
        passed += 1
        print("  ✅ min_pivot is 0.5 for diag(1e12, 0.5), whichever end it sits at")
    else:
        failed += 1
        print(
            "  ❌ min_pivot is not the smallest pivot:", mp_a.min_pivot, mp_a.rank,
            mp_b.min_pivot, mp_c.min_pivot,
        )

    # ── 37. at_optimum tracks the GAP, not the tolerance ─────────────────────
    # VERBATIM: `min 0.5x² s.t. x >= 1e9`, whose optimum is f* = 5e17 at x = 1e9. At
    # x = 1e9 + 0.4 the measured gap is exactly 4e8 — the struct SAYS 4e8 — and `at_optimum`
    # came back True, because the threshold was `optimality_tol · (1 + |f(x)|)` = 5e8: a
    # RELATIVE term sized by the caller's tolerance instead of by DBL_EPSILON. The gap is now
    # judged against the caller's ABSOLUTE tolerance plus what the three-term subtraction can
    # have rounded away, so a measured four hundred million is not optimal.
    var big_q = _floats(1.0)
    var big_row = _floats(1.0)
    var far = qp_gap_flat(
        big_q, 1, _floats(0.0), big_row, 1, _ints(SENSE_GE), _floats(1.0e9), _floats(0.0),
        _floats(0.0), _ints(0), _floats(1000000000.4), 1000, 1e-9, 1e-9,
    )
    # The true optimum of the same program still reads at_optimum, so the tighter threshold is
    # not simply refusing everything: at x = 1e9 the linearisation gap is exactly 0.
    var at_opt = qp_gap_flat(
        big_q, 1, _floats(0.0), big_row, 1, _ints(SENSE_GE), _floats(1.0e9), _floats(0.0),
        _floats(0.0), _ints(0), _floats(1.0e9), 1000, 1e-9, 1e-9,
    )
    if (
        far.status == MODEL_OK
        and far.feasible
        and far.has_gap
        and _close(far.gap, 4.0e8, 1.0)
        and not far.at_optimum
        and far.has_bound
        and at_opt.has_gap
        and at_opt.gap == 0.0
        and at_opt.at_optimum
        and at_opt.has_bound
        and _close(at_opt.best_bound, 5.0e17, 1.0e6)
    ):
        passed += 1
        print("  ✅ a measured gap of 4e8 is not at_optimum, and a gap of 0 still is")
    else:
        failed += 1
        print(
            "  ❌ at_optimum tracks the tolerance, not the gap:", far.gap, far.at_optimum,
            at_opt.gap, at_opt.at_optimum, at_opt.best_bound,
        )

    # ── 38. a mixed-unit Hessian solves, and nothing reports a breakdown ─────
    # The regression the four findings share, driven from the public entry point: scales from
    # 1e-6 to 1e12 in one Hessian, with and without rows, must produce a real answer whose
    # certificate holds on the caller's own arrays — never QP_NUMERICAL_BREAKDOWN, and never a
    # status that contradicts the convexity report.
    var mixed_ok = True
    var mixed_bad = -1
    for probe in range(6):
        var d0 = 1.0
        if probe == 0:
            d0 = 1.0e12
        elif probe == 1:
            d0 = 1.0e-6
        elif probe == 2:
            d0 = 1.0e8
        elif probe == 3:
            d0 = 4.0
        elif probe == 4:
            d0 = 1.0e6
        else:
            d0 = 2.5e9
        var qm = _floats(d0, 0.0, 0.0, 2.0)
        var sm = qp_solve_default(
            qm, 2, _floats(-d0, -4.0), _floats(1.0, 1.0), 1, _ints(SENSE_LE),
            _floats(3.0), _zeros(2), _zeros(2), free2, UInt64(200 + probe),
        )
        if sm.status == QP_NUMERICAL_BREAKDOWN or not _invariant(sm):
            mixed_ok = False
            mixed_bad = probe
        if sm.status != QP_OPTIMAL and sm.status != QP_NOT_CERTIFIED:
            mixed_ok = False
            mixed_bad = probe
        if sm.status == QP_OPTIMAL:
            var cm = qp_kkt_check(
                qm, 2, _floats(-d0, -4.0), _floats(1.0, 1.0), 1, _ints(SENSE_LE),
                _floats(3.0), _zeros(2), _zeros(2), free2, sm.x, sm.duals, sm.lower_duals,
                sm.upper_duals, 1e-9, 1e-9,
            )
            if not cm.certified:
                mixed_ok = False
                mixed_bad = probe
    if mixed_ok:
        passed += 1
        print("  ✅ Hessians spanning 1e-6 to 1e12 solve and re-certify, with no breakdown")
    else:
        failed += 1
        print("  ❌ a mixed-unit Hessian failed at probe", mixed_bad)

    print("  [optimization.quadratic] Passed:", passed, "Failed:", failed)
