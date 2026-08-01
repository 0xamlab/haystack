"""
judge — a solved objective against a ground-truth optimum, at two stated tolerances.

Benchmark judges execute the candidate's code and compare ONE number to a verified
optimum. Two tolerance regimes matter and they are not interchangeable, so both are
first-class here rather than one being approximated by the other:

  * STRICT — relative error `|objective - truth| / max(1, |truth|)` at 1e-4. The
    `max(1, ·)` floor makes the test absolute near zero, where a pure relative error
    divides by nothing and declares every answer wrong (or right) for free.
  * LINEAGE — the OptMATH executor's published rule, reproduced exactly: round both
    values to the nearest integer, then require `|round(pred) - round(truth)|` within
    5% of `|round(truth)|`. When `round(truth)` is 0 that quotient does not exist; the
    honest reading is that only `round(pred) == 0` matches, and that is what is coded —
    a division by zero laundered into `inf`/`nan` would silently fail every comparison
    after it.

`formulation_verdict_flat` is the end-to-end driver a harness calls once per instance:
solve (with every refusal and certificate of `optmodel.solve` intact), judge, and land
in exactly one bucket per tolerance regime — `OPTM_VERDICT_VERIFIED`,
`OPTM_VERDICT_REFUSED`, or `OPTM_VERDICT_WRONG`. WRONG requires `solved` — a refusal
can never be wrong, only unhelpful — and any instance that lands there is a defect in
the plane or in the stated truth, to be fixed or converted into a typed refusal, never
shipped as a plausible number.
@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_optmodel_judge.mojo
benchmark: none
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability
"""

from std.math import abs as fabs

from optimization.model import (
    DEFAULT_FEASIBILITY_TOL,
    DEFAULT_INTEGRALITY_TOL,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_OPTIMALITY_TOL,
    MODEL_ERR_POLICY,
    MODEL_INT_GRID_MAX,
    MODEL_OK,
    _round_f as _nearest_int,
    model_finite as _finite,
)
from optmodel.formulation import (
    OPTM_ERR_GROUND_TRUTH,
    OPTM_VERDICT_REFUSED,
    OPTM_VERDICT_VERIFIED,
    OPTM_VERDICT_WRONG,
    optm_status_name,
)
from optmodel.solve import OptModelSolve, formulation_solve_flat

# The strict regime: 1e-4 relative with an absolute floor at magnitude 1. Tight enough
# that a wrong vertex, a dropped constraint or a sign slip cannot hide, loose enough to
# absorb honest last-ulp disagreement between two exact solvers.
comptime OPTM_STRICT_REL_TOL: Float64 = 1e-4

# The lineage regime: OptMATH's executor accepts within 5% relative ON ROUNDED values.
# Reproduced for comparability with published numbers, not endorsed — at 5% a knapsack
# off by its smallest item still "passes", which is exactly why STRICT is also reported.
comptime OPTM_LINEAGE_REL_TOL: Float64 = 0.05


# ── return-only result structs ────────────────────────────────────────────────
# Declared here because a returned struct's marshalling spec is parsed per FILE.


@fieldwise_init
struct JudgeReport(Copyable, Movable):
    """One objective against one truth, both regimes, no verdict inflation.

    `comparable` is the authority: False means the inputs could not be compared at all
    (non-finite value or truth, illegal tolerance) and BOTH match flags are False —
    "not comparable" must never score as a pass. `rounded_objective`/`rounded_truth`
    are the integers the lineage rule actually compared, reported so a surprising
    lineage verdict can be re-derived by eye.
    """

    var status: Int
    var comparable: Bool
    var objective: Float64
    var ground_truth: Float64
    var abs_error: Float64
    var rel_error: Float64
    var strict_match: Bool
    var rounded_objective: Float64
    var rounded_truth: Float64
    var lineage_match: Bool


@fieldwise_init
struct PlaneVerdict(Copyable, Movable):
    """The end-to-end outcome for one formulation: solve, certify, judge, classify.

    `verdict_strict` / `verdict_lineage` are `OPTM_VERDICT_*` codes and agree on
    REFUSED by construction (refusal happens before any tolerance is consulted); they
    may disagree between VERIFIED and WRONG, which is the measured gap between the two
    regimes. Refusal evidence (`core_*`) and solve diagnostics ride along unchanged
    from `OptModelSolve`; `message` is the status's name so a table never prints a
    bare integer.
    """

    var status: Int
    var verdict_strict: Int
    var verdict_lineage: Int
    var solved: Bool
    var refused: Bool
    var is_discrete: Bool
    var underlying_status: Int
    var has_objective: Bool
    var objective: Float64
    var ground_truth: Float64
    var abs_error: Float64
    var rel_error: Float64
    var strict_match: Bool
    var lineage_match: Bool
    var audit_feasible: Bool
    var core_size: Int
    var core_constraints: List[Int]
    var core_bound_vars: List[Int]
    var nodes_explored: Int
    var lp_iterations: Int
    var message: String


fn _no_judge(status: Int, objective: Float64, truth: Float64) -> JudgeReport:
    return JudgeReport(status, False, objective, truth, 0.0, 0.0, False, 0.0, 0.0, False)


fn judge_objective(
    objective: Float64, ground_truth: Float64,
    strict_rel_tol: Float64, lineage_rel_tol: Float64,
) -> JudgeReport:
    """Compare one objective to one truth under both regimes, refusal-first.

    A value past `MODEL_INT_GRID_MAX` cannot be meaningfully rounded to "the nearest
    integer" for the lineage rule — it already IS an integer, so rounding is the
    identity and the rule degrades to a plain 5% relative test there, which is the
    correct limit rather than a special case.
    """
    if not (_finite(strict_rel_tol) and _finite(lineage_rel_tol)):
        return _no_judge(MODEL_ERR_POLICY, 0.0, 0.0)
    if strict_rel_tol < 0.0 or lineage_rel_tol < 0.0:
        return _no_judge(MODEL_ERR_POLICY, 0.0, 0.0)
    if not (_finite(objective) and _finite(ground_truth)):
        return _no_judge(OPTM_ERR_GROUND_TRUTH, 0.0, 0.0)

    var abs_error = fabs(objective - ground_truth)
    var floor = fabs(ground_truth)
    if floor < 1.0:
        floor = 1.0
    var rel_error = abs_error / floor
    var strict = rel_error <= strict_rel_tol

    var rounded_objective = objective
    if fabs(objective) <= MODEL_INT_GRID_MAX:
        rounded_objective = _nearest_int(objective)
    var rounded_truth = ground_truth
    if fabs(ground_truth) <= MODEL_INT_GRID_MAX:
        rounded_truth = _nearest_int(ground_truth)
    var lineage = False
    if rounded_truth == 0.0:
        lineage = rounded_objective == 0.0
    else:
        lineage = (
            fabs(rounded_objective - rounded_truth) / fabs(rounded_truth)
            <= lineage_rel_tol
        )

    return JudgeReport(
        MODEL_OK, True, objective, ground_truth, abs_error, rel_error, strict,
        rounded_objective, rounded_truth, lineage,
    )


fn _verdict_of(matched: Bool) -> Int:
    if matched:
        return OPTM_VERDICT_VERIFIED
    return OPTM_VERDICT_WRONG


# PACKING IS LOAD-BEARING: `mojo_inventory` follows a signature a bounded number of
# lines past its first and silently drops what does not close in the window.
fn formulation_verdict_flat(
    n_vars: Int, n_cons: Int, maximize: Bool, c: List[Float64], c0: Float64,
    a: List[Float64], senses: List[Int], rhs: List[Float64], var_kind: List[Int],
    var_lower: List[Float64], var_upper: List[Float64], var_flags: List[Int],
    ground_truth: Float64, max_nodes: Int, max_iterations: Int,
    feasibility_tol: Float64, optimality_tol: Float64, integrality_tol: Float64,
    strict_rel_tol: Float64, lineage_rel_tol: Float64,
) -> PlaneVerdict:
    """Solve one formulation and classify it against its ground truth, end to end.

    The judge's inputs are validated BEFORE the solve: a harness that hands over a NaN
    truth learns it in microseconds, not after a million branch-and-bound nodes.

    @capability formulation_verdict_flat
    complexity: O(max_nodes * max_iterations * n_cons * n_vars)
    counts:
    - n_cons * n_vars == len(a) [kernel_validated]
    - n_vars == len(c, var_kind, var_lower, var_upper, var_flags) [kernel_validated]
    - n_cons == len(senses, rhs) [kernel_validated]
    @endcapability
    """
    var pre_judge = judge_objective(0.0, 0.0, strict_rel_tol, lineage_rel_tol)
    if pre_judge.status != MODEL_OK:
        return _refused_verdict(pre_judge.status, ground_truth)
    if not _finite(ground_truth):
        return _refused_verdict(OPTM_ERR_GROUND_TRUTH, 0.0)

    var solved = formulation_solve_flat(
        n_vars, n_cons, maximize, c, c0, a, senses, rhs, var_kind,
        var_lower, var_upper, var_flags, max_nodes, max_iterations,
        feasibility_tol, optimality_tol, integrality_tol,
    )
    if not solved.solved:
        var out = _refused_verdict(solved.status, ground_truth)
        out.is_discrete = solved.is_discrete
        out.underlying_status = solved.underlying_status
        out.core_size = solved.core_size
        out.core_constraints = solved.core_constraints.copy()
        out.core_bound_vars = solved.core_bound_vars.copy()
        out.nodes_explored = solved.nodes_explored
        out.lp_iterations = solved.lp_iterations
        return out^

    var report = judge_objective(
        solved.objective, ground_truth, strict_rel_tol, lineage_rel_tol
    )
    if not report.comparable:
        # A solved objective is finite by construction, so the only way here is a truth
        # that stopped being comparable — refuse, do not guess a bucket.
        return _refused_verdict(report.status, ground_truth)

    return PlaneVerdict(
        MODEL_OK, _verdict_of(report.strict_match), _verdict_of(report.lineage_match),
        True, False, solved.is_discrete, solved.underlying_status,
        True, solved.objective, ground_truth, report.abs_error, report.rel_error,
        report.strict_match, report.lineage_match, solved.audit_feasible,
        0, List[Int](), List[Int](), solved.nodes_explored, solved.lp_iterations,
        optm_status_name(MODEL_OK),
    )


fn _refused_verdict(status: Int, ground_truth: Float64) -> PlaneVerdict:
    return PlaneVerdict(
        status, OPTM_VERDICT_REFUSED, OPTM_VERDICT_REFUSED,
        False, True, False, status, False, 0.0, ground_truth, 0.0, 0.0,
        False, False, False, 0, List[Int](), List[Int](), 0, 0,
        optm_status_name(status),
    )


fn formulation_verdict_default(
    n_vars: Int, n_cons: Int, maximize: Bool, c: List[Float64], c0: Float64,
    a: List[Float64], senses: List[Int], rhs: List[Float64], var_kind: List[Int],
    var_lower: List[Float64], var_upper: List[Float64], var_flags: List[Int],
    ground_truth: Float64, max_nodes: Int,
) -> PlaneVerdict:
    """`formulation_verdict_flat` under the default policy and both stated tolerances.

    @capability formulation_verdict_default
    complexity: O(max_nodes * n_cons * n_vars)
    counts:
    - n_cons * n_vars == len(a) [kernel_validated]
    - n_vars == len(c, var_kind, var_lower, var_upper, var_flags) [kernel_validated]
    - n_cons == len(senses, rhs) [kernel_validated]
    @endcapability
    """
    return formulation_verdict_flat(
        n_vars, n_cons, maximize, c, c0, a, senses, rhs, var_kind,
        var_lower, var_upper, var_flags, ground_truth, max_nodes,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
        DEFAULT_INTEGRALITY_TOL, OPTM_STRICT_REL_TOL, OPTM_LINEAGE_REL_TOL,
    )
