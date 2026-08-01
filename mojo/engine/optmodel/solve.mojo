"""
solve — the bridge from a formulation onto `lp_solve` / `milp_solve`, refusal-first.

One driver, `formulation_solve_flat`, and one contract: the answer is either a point
that SURVIVED an independent re-audit against the caller's original formulation, or a
typed refusal that says why there is no answer. Nothing in between is representable —
`has_objective` is False on every refusal, so a caller cannot quietly read an incumbent,
a bound or a stale relaxation as if it were an optimum.

Dispatch is by the variable census: all-continuous goes to `lp_solve` and the optimal
basis is certified by `explain.slackness_check` (complementary slackness over the
solver's own duals); anything discrete goes to `milp_solve`, whose `proven_optimal` is
the certificate (its incumbent was already `_verify_point`-checked in the lowered
space). Both certificates are then backed by this package's OWN audit in the ORIGINAL
variable space — `formulation_point_audit_flat` never sees the lowering, so a lowering
bug and a solver bug are both caught by the same check and land in
`OPTM_REFUSED_SELF_CHECK`, never in a reported number.

Infeasibility is explained, not shrugged at: on a proven-infeasible model the driver
runs `explain.infeasibility_core` over the lowered rows and maps the core back through
`row_kind`/`row_ref`, so the refusal names the CALLER's conflicting constraints
(`core_constraints`) and upper bounds (`core_bound_vars`). The implicit `y >= 0` floor
(the caller's lower bounds, after the shift) is the package's variable convention and
never appears in a core; a conflict with a lower bound surfaces through the shifted
rows that contradict it.
@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_optmodel_solve.mojo
benchmark: none
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability
"""

from std.math import abs as fabs

from optimization.explain import infeasibility_core, slackness_check
from optimization.integer import (
    MILP_DEPTH_LIMIT,
    MILP_INFEASIBLE,
    MILP_NODE_LIMIT,
    MILP_OPTIMAL,
    MILP_RELAXATION_UNBOUNDED,
    milp_solve,
)
from optimization.linear import (
    LP_DBL_EPSILON,
    LP_FEAS_ULP_BUDGET,
    LP_INFEASIBLE,
    LP_ITERATION_LIMIT,
    LP_OPTIMAL,
    LP_UNBOUNDED,
    lp_solve,
)
from optimization.model import (
    DEFAULT_FEASIBILITY_TOL,
    DEFAULT_INTEGRALITY_TOL,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_OPTIMALITY_TOL,
    MODEL_ERR_POLICY,
    MODEL_OK,
    VAR_CONTINUOUS,
    _policy_parts_defect,
    minimization_value,
    model_finite as _finite,
)
from optmodel.formulation import (
    LoweredForm,
    OPTM_REFUSED_INFEASIBLE,
    OPTM_REFUSED_SEARCH_LIMIT,
    OPTM_REFUSED_SELF_CHECK,
    OPTM_REFUSED_UNBOUNDED,
    OPTM_REFUSED_UNCERTIFIED,
    formulation_lower_flat,
    formulation_point_audit_flat,
)


# ── return-only result struct ─────────────────────────────────────────────────
# Declared here because a returned struct's marshalling spec is parsed per FILE.


@fieldwise_init
struct OptModelSolve(Copyable, Movable):
    """A solved-and-audited answer, or a typed refusal with its evidence.

    `solved` is the authority: True means `x` is the caller-space point, `objective`
    is its value (solver and audit agree within the rounding budget), the solver's own
    certificate passed AND the independent original-space audit passed. False means
    `status` is the refusal code, `x` is EMPTY and `has_objective` is False.

    Diagnostics survive refusal because they are evidence, not answers: a search-limit
    refusal carries the incumbent (`has_incumbent`/`incumbent_objective`) and the
    surviving bound (`has_bound`/`best_bound`); an infeasibility refusal carries the
    mapped core (`core_constraints` — caller row indices, `core_bound_vars` — caller
    variable indices whose upper bound is in the core) with `core_verified`/`core_minimal`
    saying how much of it was re-proved. `underlying_status` is the raw code from the
    solver underneath, so the composed vocabulary loses nothing.
    """

    var status: Int
    var solved: Bool
    var refused: Bool
    var is_discrete: Bool
    var underlying_status: Int
    var has_objective: Bool
    var objective: Float64
    var x: List[Float64]
    var lowered_rows: Int
    var audit_feasible: Bool
    var has_bound: Bool
    var best_bound: Float64
    var has_incumbent: Bool
    var incumbent_objective: Float64
    var core_verified: Bool
    var core_minimal: Bool
    var core_size: Int
    var core_constraints: List[Int]
    var core_bound_vars: List[Int]
    var nodes_explored: Int
    var lp_iterations: Int


fn _refusal(
    status: Int, underlying: Int, is_discrete: Bool, lowered_rows: Int
) -> OptModelSolve:
    return OptModelSolve(
        status, False, True, is_discrete, underlying, False, 0.0, List[Float64](),
        lowered_rows, False, False, 0.0, False, 0.0, False, False, 0,
        List[Int](), List[Int](), 0, 0,
    )


fn _core_refusal(
    lowered: LoweredForm, is_discrete: Bool, underlying: Int,
    max_iterations: Int, feasibility_tol: Float64, optimality_tol: Float64,
) -> OptModelSolve:
    """An infeasibility refusal that NAMES the conflict in the caller's indices."""
    var core = infeasibility_core(
        lowered.a, lowered.rows, lowered.cols, lowered.senses, lowered.rhs,
        max_iterations, feasibility_tol, optimality_tol,
    )
    var core_constraints = List[Int]()
    var core_bounds = List[Int]()
    for i in range(len(core.core)):
        var row = core.core[i]
        if row < 0 or row >= lowered.rows:
            continue
        if lowered.row_kind[row] == 0:
            core_constraints.append(lowered.row_ref[row])
        else:
            core_bounds.append(lowered.row_ref[row])
    return OptModelSolve(
        OPTM_REFUSED_INFEASIBLE, False, True, is_discrete, underlying,
        False, 0.0, List[Float64](), lowered.rows, False, False, 0.0, False, 0.0,
        core.core_verified, core.minimal, core.core_size,
        core_constraints^, core_bounds^, 0, core.n_solves,
    )


fn _objective_agree_budget(
    feasibility_tol: Float64, c: List[Float64], c0: Float64, x: List[Float64]
) -> Float64:
    """Rounding allowance for 'the audit recomputed the same objective'.

    Same three-part doctrine as `_audit_row_budget`, minus the snap term (nothing is
    snapped between the two evaluations): the caller's absolute tolerance plus
    `LP_FEAS_ULP_BUDGET` ulps at the objective's own accumulation magnitude.
    """
    var scale = fabs(c0)
    for j in range(len(x)):
        scale += fabs(c[j]) * fabs(x[j])
    var budget = feasibility_tol
    if budget < 0.0:
        budget = 0.0
    var rounding = LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * scale
    if _finite(rounding) and rounding > 0.0:
        budget += rounding
    if not _finite(budget) or budget < 0.0:
        return 0.0
    return budget


# PACKING IS LOAD-BEARING: `mojo_inventory` follows a signature a bounded number of
# lines past its first and silently drops what does not close in the window.
fn formulation_solve_flat(
    n_vars: Int, n_cons: Int, maximize: Bool, c: List[Float64], c0: Float64,
    a: List[Float64], senses: List[Int], rhs: List[Float64], var_kind: List[Int],
    var_lower: List[Float64], var_upper: List[Float64], var_flags: List[Int],
    max_nodes: Int, max_iterations: Int, feasibility_tol: Float64,
    optimality_tol: Float64, integrality_tol: Float64,
) -> OptModelSolve:
    """Lower, dispatch, certify, re-audit — or refuse with a typed reason.

    `max_nodes` is validated in BOTH paths (a pure LP ignores it but a policy either is
    legal or is not — path-dependent validation is how one caller's typo survives until
    the model grows its first integer variable).

    @capability formulation_solve_flat
    complexity: O(max_nodes * max_iterations * n_cons * n_vars)
    counts:
    - n_cons * n_vars == len(a) [kernel_validated]
    - n_vars == len(c, var_kind, var_lower, var_upper, var_flags) [kernel_validated]
    - n_cons == len(senses, rhs) [kernel_validated]
    @endcapability
    """
    var policy = _policy_parts_defect(
        max_iterations, feasibility_tol, optimality_tol, integrality_tol
    )
    if policy != MODEL_OK:
        return _refusal(policy, policy, False, 0)
    if max_nodes < 1:
        return _refusal(MODEL_ERR_POLICY, MODEL_ERR_POLICY, False, 0)

    var lowered = formulation_lower_flat(
        n_vars, n_cons, c, c0, a, senses, rhs, var_kind,
        var_lower, var_upper, var_flags,
    )
    if not lowered.ok:
        return _refusal(lowered.status, lowered.status, False, 0)

    var is_discrete = False
    for j in range(n_vars):
        if var_kind[j] != VAR_CONTINUOUS:
            is_discrete = True
            break

    # A formulation with no rows at all (no constraints, no upper bounds) never reaches
    # the simplex: each shifted variable can only grow, so the model is unbounded the
    # moment any objective coefficient rewards growth, and `y = 0` (the lower-bound
    # corner) is optimal otherwise. Discrete kinds change neither statement — 0 is on
    # the grid. Answered analytically so the empty-tableau shape is a THEOREM here, not
    # an untested solver edge case.
    if lowered.rows == 0:
        for j in range(n_vars):
            if minimization_value(lowered.c[j], maximize) < 0.0:
                return _refusal(OPTM_REFUSED_UNBOUNDED, LP_UNBOUNDED, is_discrete, 0)
        var corner = List[Float64]()
        for j in range(n_vars):
            corner.append(lowered.shift[j])
        var corner_audit = formulation_point_audit_flat(
            n_vars, n_cons, c, c0, a, senses, rhs, var_kind,
            var_lower, var_upper, var_flags, corner,
            feasibility_tol, integrality_tol,
        )
        if corner_audit.status != MODEL_OK or not corner_audit.feasible:
            return _refusal(OPTM_REFUSED_SELF_CHECK, MODEL_OK, is_discrete, 0)
        return OptModelSolve(
            MODEL_OK, True, False, is_discrete, LP_OPTIMAL,
            True, lowered.constant, corner^, 0, True,
            True, lowered.constant, False, 0.0, False, False, 0,
            List[Int](), List[Int](), 0, 0,
        )

    if is_discrete:
        var result = milp_solve(
            lowered.c, lowered.constant, lowered.a, lowered.rows, lowered.cols,
            lowered.senses, lowered.rhs, maximize, lowered.var_kind, max_nodes,
            max_iterations, feasibility_tol, optimality_tol, integrality_tol,
        )
        if result.feasible and result.proven_optimal and result.has_objective:
            return _certified(
                n_vars, n_cons, c, c0, a, senses, rhs, var_kind,
                var_lower, var_upper, var_flags, lowered, True, result.status,
                result.objective, result.x, result.nodes_explored,
                result.lp_iterations, feasibility_tol, integrality_tol,
            )
        if result.status == MILP_INFEASIBLE:
            return _core_refusal(
                lowered, True, result.status,
                max_iterations, feasibility_tol, optimality_tol,
            )
        if result.status == MILP_RELAXATION_UNBOUNDED:
            return _refusal(
                OPTM_REFUSED_UNBOUNDED, result.status, True, lowered.rows
            )
        if (
            result.status == MILP_NODE_LIMIT
            or result.status == MILP_DEPTH_LIMIT
            or result.status == LP_ITERATION_LIMIT
        ):
            var out = _refusal(
                OPTM_REFUSED_SEARCH_LIMIT, result.status, True, lowered.rows
            )
            out.has_bound = result.has_bound
            out.best_bound = result.best_bound
            out.has_incumbent = result.has_objective
            out.incumbent_objective = result.objective
            out.nodes_explored = result.nodes_explored
            out.lp_iterations = result.lp_iterations
            return out^
        if result.status != MILP_OPTIMAL:
            return _refusal(
                OPTM_REFUSED_UNCERTIFIED, result.status, True, lowered.rows
            )
        # `MILP_OPTIMAL` without `proven_optimal` is a contradiction in the underlying
        # contract; refuse rather than pick a side of it.
        return _refusal(OPTM_REFUSED_UNCERTIFIED, result.status, True, lowered.rows)

    var lp = lp_solve(
        lowered.c, lowered.constant, lowered.a, lowered.rows, lowered.cols,
        lowered.senses, lowered.rhs, maximize,
        max_iterations, feasibility_tol, optimality_tol,
    )
    if lp.status == LP_OPTIMAL and lp.has_objective:
        # The LP certificate: complementary slackness over the solver's own duals,
        # audited by `explain`, the module built to catch exactly a primal/dual pair
        # that disagrees with itself.
        var certificate = slackness_check(lp.duals, lp.slack, lp.binding, optimality_tol)
        if certificate.status != MODEL_OK or not certificate.complementary:
            return _refusal(
                OPTM_REFUSED_SELF_CHECK, lp.status, False, lowered.rows
            )
        return _certified(
            n_vars, n_cons, c, c0, a, senses, rhs, var_kind,
            var_lower, var_upper, var_flags, lowered, False, lp.status,
            lp.objective, lp.x, 0, lp.iterations, feasibility_tol, integrality_tol,
        )
    if lp.status == LP_INFEASIBLE:
        return _core_refusal(
            lowered, False, lp.status,
            max_iterations, feasibility_tol, optimality_tol,
        )
    if lp.status == LP_UNBOUNDED:
        return _refusal(OPTM_REFUSED_UNBOUNDED, lp.status, False, lowered.rows)
    if lp.status == LP_ITERATION_LIMIT:
        return _refusal(OPTM_REFUSED_SEARCH_LIMIT, lp.status, False, lowered.rows)
    return _refusal(OPTM_REFUSED_UNCERTIFIED, lp.status, False, lowered.rows)


fn _certified(
    n_vars: Int, n_cons: Int, c: List[Float64], c0: Float64, a: List[Float64],
    senses: List[Int], rhs: List[Float64], var_kind: List[Int],
    var_lower: List[Float64], var_upper: List[Float64], var_flags: List[Int],
    lowered: LoweredForm, is_discrete: Bool, underlying: Int, objective: Float64,
    y: List[Float64], nodes: Int, iterations: Int,
    feasibility_tol: Float64, integrality_tol: Float64,
) -> OptModelSolve:
    """Map back to caller space, re-audit there, and only then report a number."""
    if len(y) != n_vars:
        return _refusal(OPTM_REFUSED_SELF_CHECK, underlying, is_discrete, lowered.rows)
    var x = List[Float64]()
    for j in range(n_vars):
        x.append(y[j] + lowered.shift[j])
    var audit = formulation_point_audit_flat(
        n_vars, n_cons, c, c0, a, senses, rhs, var_kind,
        var_lower, var_upper, var_flags, x, feasibility_tol, integrality_tol,
    )
    if audit.status != MODEL_OK or not audit.feasible or not audit.has_objective:
        return _refusal(OPTM_REFUSED_SELF_CHECK, underlying, is_discrete, lowered.rows)
    var budget = _objective_agree_budget(feasibility_tol, c, c0, x)
    if fabs(audit.objective - objective) > budget:
        return _refusal(OPTM_REFUSED_SELF_CHECK, underlying, is_discrete, lowered.rows)
    return OptModelSolve(
        MODEL_OK, True, False, is_discrete, underlying,
        True, objective, x^, lowered.rows, True,
        True, objective, True, objective, False, False, 0,
        List[Int](), List[Int](), nodes, iterations,
    )


fn formulation_solve_default(
    n_vars: Int, n_cons: Int, maximize: Bool, c: List[Float64], c0: Float64,
    a: List[Float64], senses: List[Int], rhs: List[Float64], var_kind: List[Int],
    var_lower: List[Float64], var_upper: List[Float64], var_flags: List[Int],
    max_nodes: Int,
) -> OptModelSolve:
    """`formulation_solve_flat` under `model.mojo`'s default policy.

    `max_nodes` stays explicit even here, exactly as in `milp_solve_default`: it is the
    termination guarantee, and a default for it would silently cap how much of the tree
    an answer covers.

    @capability formulation_solve_default
    complexity: O(max_nodes * n_cons * n_vars)
    counts:
    - n_cons * n_vars == len(a) [kernel_validated]
    - n_vars == len(c, var_kind, var_lower, var_upper, var_flags) [kernel_validated]
    - n_cons == len(senses, rhs) [kernel_validated]
    @endcapability
    """
    return formulation_solve_flat(
        n_vars, n_cons, maximize, c, c0, a, senses, rhs, var_kind,
        var_lower, var_upper, var_flags, max_nodes, DEFAULT_MAX_ITERATIONS,
        DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL, DEFAULT_INTEGRALITY_TOL,
    )
