"""
optimization.quadratic — convex QP with a certificate that is checked, not claimed. Zero Python.

What this is for
----------------
Minimise `0.5 xᵀQx + cᵀx` subject to `A x {<=,=,>=} b` and per-variable bounds. That is the
shape of a portfolio variance, a least-squares fit with side conditions, a Euclidean
projection onto a polyhedron, an SVM dual, a tracking-error problem and a ridge fit with a
budget — and the tree could not state any of them. What exists is:

  * `optimization_constrained.eval_objective_c` and friends: an integer `func_id` selecting
    one hardcoded objective, returning 0.0 for an id it does not recognise.
  * `convex.gradient_descent`: unconstrained, and blind to the same id table.
  * `qp_solver.mojo`-shaped helpers: none. `svm_solver` solves ONE quadratic program (the
    SVM dual with its box and its single equality) and nothing else.
  * `optimization.linear.lp_solve`: exact, dual-carrying, and linear only.

So this module is the missing driver, and it is built ON the frozen and tier-1 pieces rather
than beside them: `linear.lp_solve` finds the initial feasible point and computes the
suboptimality bound, `matrix_decomp.is_symmetric` gives the symmetry verdict,
`linalg_ext.mat_is_positive_definite` gives the strict-definiteness verdict, `linalg.vec_dot`
and `vec_norm` do the inner products, and `determinism.sampling_keyed.permutation_keyed`
supplies every tie-break.

MINIMISATION ONLY, and that is not an omission
----------------------------------------------
There is no `maximize` flag. Maximising a convex quadratic is not a convex problem — its
optimum sits at a vertex of the feasible set and the whole apparatus below (a KKT point is a
global minimum) is false for it. A flag would have let a caller ask for that silently and get
a local answer with a success status. A caller who wants to maximise a CONCAVE quadratic
passes `Q = -Q_concave`, `c = -c_concave` and negates the reported objective; the convexity
gate then checks the thing that actually has to be true.

Convexity is a precondition, and it is measured
-----------------------------------------------
`Q` is rejected, not repaired, when it is asymmetric beyond rounding (`QP_ERR_NOT_SYMMETRIC`)
or not positive semidefinite (`QP_ERR_NOT_CONVEX`), and the report carries the measured
asymmetry, the failing pivot's index and its value so the caller can fix the model instead of
guessing. Note that `0.5 xᵀQx` only ever sees `(Q + Qᵀ)/2`, so an asymmetric `Q` is not
ill-posed — it is evidence that the matrix in hand is not the matrix that was meant, which is
why the refusal is worth more than a silent symmetrisation. `qp_convexity_flat` returns the
symmetrised matrix so the caller can adopt it explicitly and see the change.

A non-convex `Q` is refused rather than solved because for an indefinite `Q` every claim this
module makes is false: a KKT point is not a minimum, the reported bound is not a bound, and
"optimal" would mean "a point where the search stopped".

The status is the answer, and the certificate is the gate
---------------------------------------------------------
`QP_OPTIMAL` is returned only when all FOUR KKT conditions have been re-checked against the
CALLER's own arrays — stationarity, primal feasibility, dual feasibility, complementary
slackness in BOTH directions — and an independent linearisation bound has not CONTRADICTED
them. For a convex objective the KKT audit is a proof of global optimality by itself; the
bound is a second computation whose job is to object if either is wrong, and an absent second
opinion (the bound does not exist whenever the feasible set has a ray) is not an objection.
The search's own stopping rule is not evidence of anything and is never consulted. Everything
else is a distinct status:

  * `QP_INFEASIBLE` — no point satisfies the rows and the bounds. No `x`, no objective.
  * `QP_UNBOUNDED` — a feasible ray `d` with `Qd = 0` and `cᵀd < 0` exists, so there is no
    minimum. The ray is returned; the last iterate is NOT, because it is not an answer.
  * `QP_ITERATION_LIMIT` — the search stopped. The iterate IS returned, but with
    `proven_optimal = False` and with a MEASURED lower bound and gap, exactly as
    `integer.milp_solve` reports a truncated search: a verified feasible point with a real
    remaining gap is an answer to a different question, and pretending it converged is the
    one thing that is not allowed.
  * `QP_NOT_CERTIFIED` — the search finished but a KKT condition or the gap did not check
    out. The numbers are reported with every residual, and nothing claims optimality.
  * `QP_NUMERICAL_BREAKDOWN` — a factorisation or a step could not be verified.
  * `QP_FEASIBILITY_SEARCH_FAILED` — the phase-1 LP neither found a point nor proved there
    is none (an iteration cap, say), so infeasibility is NOT established either.

Status ranges taken in this package (rule 4e — 80-84 were once allocated twice):
0-30 `model`, 40-42 `linear`'s extractor, 60-63 `linear`'s solver, 80-86 `explain`,
100-105 `integer`, **110-117 here** (118-119 unallocated). `flow` (0-21) and `assignment`
(0-13) are self-contained namespaces with their own tables.

Every dual is a derivative of the optimum
-----------------------------------------
One convention, uniformly: `duals[i] = ∂f*/∂b_i`, `lower_duals[j] = ∂f*/∂lower_j`, and
`upper_duals[j] = ∂f*/∂upper_j`. So a `<=` row's dual is <= 0 (relaxing a ceiling cannot
raise a minimum), a `>=` row's is >= 0, a lower bound's is >= 0 and an upper bound's is <= 0.
This is `linear.lp_solve`'s convention, which is what makes the zero-Hessian cross-check in
the suite possible: with `Q = 0` this driver's duals must equal the simplex's duals and its
bound multipliers must equal the simplex's reduced costs. In these terms stationarity is the
single equation

    Q x + c  ==  Aᵀ duals + lower_duals + upper_duals

and the Lagrange multiplier of a row is the negation of its dual.

Determinism, which is the reason this package exists
----------------------------------------------------
An active-set search is order-dependent: which blocking row is chosen when two block at the
same step, and which multiplier is dropped when two are equally negative, decide the path. A
path that depends on hash order or on wall time gives an answer that cannot be explained
twice, so every such choice here is a keyed draw:

  * `seed` is explicit and mandatory; `random_float64` and `seed(` are never called.
  * the scan order is `permutation_keyed(m, seed, stream_id("optimization.quadratic"), 0)`
    from `determinism/`, a counter-based generator: a draw is a pure function of its
    coordinates, so the order is identical no matter what the search did beforehand.
  * BLOCKING ROW: smallest step `α`; ties (within a rounding budget of `α`) go to the
    candidate of lowest keyed scan rank.
  * DROPPED ROW: most negative gradient-scaled multiplier; ties go to the lowest keyed scan
    rank.
  * CONVEXITY PIVOT: largest trailing diagonal, ties to the lowest ORIGINAL index — chosen
    seed-INDEPENDENTLY on purpose, because whether a model is convex is a property of the
    model and must not move when a seed moves.
  * UNBOUNDED DIRECTION: the lowest-index null basis vector of the reduced Hessian with a
    nonzero reduced-gradient projection — also seed-independent, for the same reason.

`path_signature` folds the keyed scan order and then every add/drop decision through the
frozen `philox_word`, so it identifies the search itself. The same seed reproduces it
bit-for-bit. A DIFFERENT seed may produce a different signature — and must produce the SAME
optimum, because a convex program has one optimal value and a solver whose answer moved with
its seed would be reporting its own arbitrariness as a result. The suite asserts both halves.

Bounds, allocation, and the arithmetic behind the ceiling
---------------------------------------------------------
`n` is tied to the PAYLOAD, not to a ceiling: `dims_fit(n, n, len(q))` requires `Q` to
actually carry `n²` cells, so `n <= sqrt(len(q))` and the "3.50 GB from a 60-byte request"
shape is unreachable. `rows` is tied the same way through `dims_fit(rows, n, len(a))`. Both
`dims_fit` calls use DIVISION, never `rows * cols == len(a)`, because that product wraps
(`3 * 6148914691236517206 == 2`) and is therefore not a bound.

Then the AREA budget, which a dimension ceiling cannot supply, because an area grows
quadratically in a dimension that is individually legal. Counted, in units of one area:

    1  the symmetrised `Q`                       n x n
    1  the LDLᵀ working copy of it               n x n
    1  the internal row matrix                   m x n     (m <= rows + 2n)
    2  the split-variable LP matrix              m x 2n
    1  the null-space basis `Z`                  nz x n
    1  the active-row basis `Q_mgs`              rank x n
    1  its `R` factor                            n x m
    1  `QZ`                                      nz x n
    2  the reduced Hessian and its LDLᵀ copy     nz x nz
   --
   11 areas, plus the phase-1 tableau, which `_simplex_run` bounds by
      `LP_MAX_TABLEAU_CELLS` and which this module ALSO pre-checks so the rejection names
      the shape instead of surfacing as an LP status three calls down.

So the 512 MiB that `algenta_runtime.session` treats as the outer limit for ONE resident
object — which `linear.LP_MAX_TABLEAU_CELLS` spends on one tableau — is divided by 16 here:
`QP_MAX_MATRIX_CELLS = LP_MAX_TABLEAU_CELLS // 16` = 2^21 cells = 16.8 MB per area, so about
185 MB across the eleven. Divided by 16 and not by 11 because the divisor should be a power of
two that leaves headroom, not a number that has to be revised the moment a twelfth array
appears. `MAX_CSR_DIM` itself is neither raised nor lowered — other packages depend on it —
and no second dimension ceiling is introduced.

The phase-1 tableau is checked here as well rather than left to `_simplex_run`: `m` internal
rows over `2n` split columns needs `m * (2n + slacks + artificials + 1)` cells, and a caller
gets `MODEL_ERR_DIMENSION_TOO_LARGE` before anything is allocated.

What this does NOT prove
------------------------
  * Nothing here is an interior-point method or a factorisation-updating active-set method.
    `Z` and the reduced Hessian are rebuilt from scratch every iteration — the same reason
    `linear._phase` recomputes its reduced costs instead of carrying an updated cost row: an
    updated factorisation accumulates the error of every pivot, and its drift surfaces as an
    optimality claim. The cost is O(n³) per iteration, so this is a driver for models whose
    `Q` fits comfortably in memory, not a large-scale solver.
  * A degenerate active set (dependent rows) makes the multipliers ambiguous. When that
    happens `degenerate_active_set` is True, the dependent rows receive multiplier 0, and the
    certificate still has to pass on the numbers actually returned — an ambiguous dual that
    fails the audit produces `QP_NOT_CERTIFIED`, not a success.
  * Cycling on a degenerate vertex is bounded by `max_iterations` and reported, not
    prevented. Bland-style anti-cycling is `linear`'s; here the honest outcome is
    `QP_ITERATION_LIMIT` with a measured gap.
  * The convexity verdict is a floating-point verdict at a stated rounding budget, and the
    budget is RELATIVE TO THE ENTRIES THE VERDICT IS READ FROM, not absolute and not relative
    to the matrix's largest entry. `Q` is symmetrically equilibrated by powers of two before
    it is factored (`_ldl_factor`), so a negative pivot at position `i` is accepted as
    rounding exactly when `|pivot| <= 1024 · DBL_EPSILON · (n + 1) · Q_ii`, and a trailing
    off-diagonal `(i, j)` when `|Q_ij| <= 1024 · DBL_EPSILON · (n + 1) · sqrt(Q_ii Q_jj)` —
    about 1e-13 of the diagonal entries the quantity belongs to, at any scale, and with the
    same numeric result whether the model is written in dollars or in cents. Symmetry is
    judged the same way, per PAIR: `|Q_ij - Q_ji| <= 1024 · DBL_EPSILON · (n + 1) ·
    (|Q_ij| + |Q_ji|)`.

    This paragraph used to claim a budget of "an eigenvalue of -1e-14 AT UNIT SCALE" while the
    code scaled every pivot tolerance by `max_i |Q_ii|`. With one diagonal at 1e12 that made
    the real budget 0.68 in absolute units: `Q = diag(1e12, -0.5)` — plainly indefinite, true
    minimum -25 over the box `[-10,10]²` — was solved and returned `QP_OPTIMAL` with
    `convex = True`, `certified = True`, `proven_optimal = True`, `gap = 0` and `x = (0, 0)`,
    with BOTH cross-checks agreeing because both inherit the convexity verdict. The same
    mis-scaling in the other direction called a live pivot of 0.5 dead next to a diagonal of
    1e12, so a strictly positive definite `Q = diag(1e12, 0.5)` with `c = (0, -1)` — unique
    minimiser (0, 2) — came back `QP_UNBOUNDED` with a ray whose `Qd` was not zero.
"""
from std.math import abs as fabs, sqrt

from determinism.counter_rng import philox_word
from determinism.sampling_keyed import permutation_keyed
from determinism.streams import stream_id
from linalg import mat_from_list, vec_dot, vec_norm
from linalg_ext import mat_is_positive_definite
from matrix_decomp import is_symmetric
from optimization.linear import (
    LP_DBL_EPSILON,
    LP_FEAS_ULP_BUDGET,
    LP_INFEASIBLE,
    LP_MAX_TABLEAU_CELLS,
    LP_OPTIMAL,
    LP_UNBOUNDED,
    LPSolution,
    lp_solve,
    lp_status_name,
)
from optimization.model import (
    DEFAULT_FEASIBILITY_TOL,
    DEFAULT_INTEGRALITY_TOL,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_OPTIMALITY_TOL,
    MODEL_ERR_BOUNDS_CROSSED,
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_DIMENSION_TOO_LARGE,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_ERR_NON_FINITE_BOUND,
    MODEL_ERR_NON_FINITE_COEFFICIENT,
    MODEL_ERR_NON_FINITE_POINT,
    MODEL_ERR_NON_FINITE_RHS,
    MODEL_ERR_NON_FINITE_VALUE,
    MODEL_ERR_POINT_LENGTH,
    MODEL_ERR_POLICY,
    MODEL_ERR_SENSE,
    MODEL_ERR_VAR_FLAGS,
    MODEL_OK,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    VAR_FLAG_HAS_START,
    _policy_parts_defect,
    has_lower_bound,
    has_upper_bound,
    model_finite as _finite,
    model_status_name,
    var_flags_valid,
)
from sparse_numerics.csr import MAX_CSR_DIM, dims_fit

# ── status codes ──────────────────────────────────────────────────────────────
# RANGE 110-119 is this module's, and only this module's. Taken elsewhere in the shared
# model-status chain: 0-30 model, 40-42 lin, 60-63 lp, 80-86 explain, 100-105 milp.
# 118 and 119 are unallocated — room to grow without renumbering, because a renumber
# silently changes what an already-stored status means.

comptime QP_OPTIMAL: Int = MODEL_OK
comptime QP_ERR_NOT_SYMMETRIC: Int = 110
comptime QP_ERR_NOT_CONVEX: Int = 111
comptime QP_INFEASIBLE: Int = 112
comptime QP_UNBOUNDED: Int = 113
comptime QP_ITERATION_LIMIT: Int = 114
comptime QP_NUMERICAL_BREAKDOWN: Int = 115
comptime QP_NOT_CERTIFIED: Int = 116
comptime QP_FEASIBILITY_SEARCH_FAILED: Int = 117

# ── ceilings ──────────────────────────────────────────────────────────────────
# See the header: nine areas, so ONE object's budget divided by 16. Not a second copy of
# MAX_CSR_DIM (that bounds a dimension; this bounds an area that grows quadratically), and
# not a second copy of LP_MAX_TABLEAU_CELLS either — it is DERIVED from it, so tightening
# that one tightens this one.
comptime QP_MAX_MATRIX_CELLS: Int = LP_MAX_TABLEAU_CELLS // 16

# ── rounding budgets ──────────────────────────────────────────────────────────
# `LP_DBL_EPSILON` and `LP_FEAS_ULP_BUDGET` are IMPORTED, not restated. They carry
# `linear.mojo`'s reasoning, which is this module's reasoning too: a relative term in a
# feasibility or residual test may absorb what floating point can explain away and nothing
# more, so it is sized by DBL_EPSILON and never by the caller's tolerance. A tolerance
# scaled by the caller's `feasibility_tol` times a sum over rows is what let an infeasible
# LP report OPTIMAL, and a merely relative per-row test was still wrong because a fraction
# shrinks with the row's magnitude while the violation does not.
#
# Every threshold below therefore has the shape
#     absolute part (the caller's tol) + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * (own scale)
# where "own scale" spans exactly the quantity being judged and nothing else: one row's own
# terms for that row's feasibility, one component's own terms for that component of
# stationarity, one matrix's own diagonal for that matrix's pivots.

# A pivoted LDLᵀ pivot at step k is the output of up to k rank-1 updates of entries of the
# matrix's own scale, so its noise floor grows with the step count. That growth is written
# into the thresholds as an explicit `(k + 1)` factor at the point of use rather than folded
# into a larger constant here, so a reader can see which quantity it belongs to.

# A magnitude cannot be negative, so -1.0 says "never measured" rather than "zero", which
# would read as "verified". Same convention as `model.MODEL_VIOLATION_ABSENT` and
# `linear.LP_INFEASIBILITY_ABSENT`.
comptime QP_ABSENT: Float64 = -1.0

# The named stream every keyed draw in this module addresses. Derived from a NAME through
# the frozen `determinism.streams.stream_id` rather than hardcoded, because a hardcoded
# integer silently collides with whoever picked it first and the two streams stop being
# independent without anything failing.
comptime QP_STREAM_NAME: String = "optimization.quadratic"


fn qp_status_name(code: Int) -> String:
    """Name for a QP status, falling through to `lp_status_name` and then to the model chain.

    0 is `optimal` here, as it is for the LP: a QP whose KKT point is certified and whose
    measured gap is zero has an optimum, not merely an "ok".
    """
    if code == QP_ERR_NOT_SYMMETRIC:
        return "objective_matrix_not_symmetric"
    if code == QP_ERR_NOT_CONVEX:
        return "objective_matrix_not_positive_semidefinite"
    if code == QP_INFEASIBLE:
        return "infeasible"
    if code == QP_UNBOUNDED:
        return "unbounded_below"
    if code == QP_ITERATION_LIMIT:
        return "iteration_limit"
    if code == QP_NUMERICAL_BREAKDOWN:
        return "numerical_breakdown"
    if code == QP_NOT_CERTIFIED:
        return "found_but_not_certified_optimal"
    if code == QP_FEASIBILITY_SEARCH_FAILED:
        return "feasibility_search_failed"
    return lp_status_name(code)


# ── return-only result structs ────────────────────────────────────────────────
# Declared in THIS file on purpose. `mojo_inventory.parse_runtime_struct_specs` reads one
# file at a time, so a driver returning a struct owned by another module is dropped from the
# runtime contract AND from dispatch with no error at all. `linear.FormValue` would have
# served for `QPValue`; it is not used, for exactly that reason.


@fieldwise_init
struct QPValue(Copyable, Movable):
    """One scalar with its existence flag. `value` is 0.0 padding when `has_value` is False."""

    var status: Int
    var has_value: Bool
    var value: Float64


@fieldwise_init
struct QPVector(Copyable, Movable):
    """One vector with its existence flag. `values` is EMPTY when `has_value` is False."""

    var status: Int
    var has_value: Bool
    var n: Int
    var values: List[Float64]


@fieldwise_init
struct QPConvexity(Copyable, Movable):
    """Whether `0.5 xᵀQx` is a convex objective, with the numbers needed to fix it if not.

    `symmetric` is the frozen `matrix_decomp.is_symmetric`'s verdict, taken on the PAIR-
    RELATIVE matrix so that its one tolerance is per pair; `asymmetry` is the measured
    `max |Q_ij - Q_ji|`, because a Bool does not tell a caller which entry to correct.
    `positive_definite` is the frozen `linalg_ext.mat_is_positive_definite`'s verdict AND
    `rank == n` AND `convex` — STRICT definiteness, a different question from `convex`, which
    is semidefiniteness and is what convexity actually needs. A convex but singular `Q` has
    `convex = True` and `positive_definite = False`, and that combination is precisely the one
    where an unbounded direction can exist.

    The conjunction is what makes the struct self-consistent: definiteness implies full rank,
    so `rank < n` with `positive_definite = True` is two mutually exclusive claims in one
    returned value and is unconstructible here. When the frozen kernel and this module's own
    rank disagree — they use different rounding models — the flag stays False and `message`
    says which said what, rather than one silently overruling the other.

    `fail_index` / `fail_value` name the pivot that refuted semidefiniteness, in the
    caller's own index space; both are -1 / 0.0 when nothing failed. `rank` is the pivoted
    factorisation's rank, so `rank < n` says the objective is flat in `n - rank` directions.

    `q_sym` is `(Q + Qᵀ)/2` — the matrix the quadratic form actually sees. Returned so a
    caller whose `Q` was rejected as asymmetric can adopt the symmetrisation EXPLICITLY and
    diff it, rather than have this module apply it silently.
    """

    var status: Int
    var n: Int
    var symmetric: Bool
    var convex: Bool
    var positive_definite: Bool
    var asymmetry: Float64
    var rank: Int
    var min_pivot: Float64
    var fail_index: Int
    var fail_value: Float64
    var q_sym: List[Float64]
    var message: String


@fieldwise_init
struct QPCertificate(Copyable, Movable):
    """A four-condition KKT audit of a point and its duals — including the conditions the
    point in hand does not exercise (rule 4d).

    Exported so a caller can audit a solution SOMEBODY ELSE produced, which is the only
    reason a certificate is worth more than a status. What it covers, all four and each with
    its own residual:

      1. STATIONARITY: `Q x + c - Aᵀ duals - lower_duals - upper_duals == 0`, per component,
         each against the magnitude of the terms that produced that component.
      2. PRIMAL FEASIBILITY: every row and every bound, per row, against that row's own
         scale. Never against a sum over rows.
      3. DUAL FEASIBILITY: `duals[i] <= 0` for a `<=` row, `>= 0` for a `>=` row, free for
         an `=` row; `lower_duals >= 0`; `upper_duals <= 0`; and ZERO for a bound the caller
         did not declare — a multiplier on a bound that does not exist is not a dual, it is
         a licence to violate stationarity for free.
      4. COMPLEMENTARY SLACKNESS, BOTH DIRECTIONS: a row with slack has a zero dual
         (`slack_dual_violation`), AND a row with a nonzero dual is tight
         (`dual_slack_violation`). With symmetric thresholds these two are contrapositives,
         which is precisely why auditing one and reporting "slackness holds" was wrong: the
         two magnitudes differ (one is a dual, one is a distance) and each names a different
         thing to fix.

    `certified` is the conjunction of all four AND of convexity, because a KKT point of a
    non-convex objective is not a minimum and this struct would otherwise certify a saddle.
    Every threshold is computed from inputs that were checked finite FIRST: a `nan` dual
    makes `tol = SLOP * (1 + nan)` equal `nan`, every `fabs(d) > nan` False, and the audit
    passes having counted zero violations.
    """

    var status: Int
    var certified: Bool
    var convex: Bool
    var symmetric: Bool
    var stationarity_ok: Bool
    var primal_ok: Bool
    var dual_ok: Bool
    var slackness_ok: Bool
    var stationarity_violation: Float64
    var primal_violation: Float64
    var dual_violation: Float64
    var slack_dual_violation: Float64
    var dual_slack_violation: Float64
    var worst_component: Int
    var worst_row: Int
    var worst_bound: Int
    var n_violations: Int
    var has_objective: Bool
    var objective: Float64
    var message: String


@fieldwise_init
struct QPBound(Copyable, Movable):
    """A MEASURED lower bound on the optimum from the linearisation at a feasible point.

    For a convex `f`, `f(z) >= f(x) + ∇f(x)ᵀ(z - x)` everywhere, so minimising the
    linearisation over the SAME feasible set — one `linear.lp_solve` call — gives a genuine
    lower bound on `f*` and hence a genuine upper bound on `f(x) - f*`. That is the number a
    truncated search owes its caller (rule 4: report the bound you actually have), and it is
    also an optimality certificate independent of the KKT audit: `gap == 0` and "KKT holds"
    are two different computations that have to agree.

    `has_bound` is False when the linearisation is unbounded over the feasible set, which is
    NOT the same as the QP being unbounded — curvature can still stop the descent — so no
    bound is reported rather than a wrong one. `lp_status` carries the LP's own status so a
    caller can tell "no bound exists" from "the bound solve failed".

    `at_optimum` is the gap's verdict, decided HERE rather than by the caller, because the
    gap is a difference of three numbers — `f(x)`, `gᵀx` and the LP's value — and only this
    function holds all three. A caller comparing `gap` to a tolerance of its own would be
    sizing the rounding term by the one quantity it can see. It is judged against the caller's
    ABSOLUTE `optimality_tol` plus `1024 · DBL_EPSILON · (|f(x)| + |gᵀx| + |LP|)`, so it
    tracks the GAP: a measured gap of 4e8 on a program whose optimum is 5e17 is NOT at
    optimum, which the earlier `optimality_tol · (1 + |f(x)|)` form reported that it was.

    `best_bound` is a theorem about real numbers evaluated in floating point, so it is a lower
    bound up to the rounding of its own three-term combination — the same
    `1024 · DBL_EPSILON · (|f(x)| + |gᵀx| + |LP|)` budget, which at `f* = 5e17` is a few
    hundred. No sharper claim is available without exact arithmetic, and the budget is stated
    rather than implied.
    """

    var status: Int
    var feasible: Bool
    var has_objective: Bool
    var objective: Float64
    var has_bound: Bool
    var best_bound: Float64
    var has_gap: Bool
    var gap: Float64
    var at_optimum: Bool
    var lp_status: Int
    var message: String


struct QPSolution(Copyable, Movable):
    """A certified minimiser, or a status and the reason it is not one.

    THE INVARIANT, in one sentence: `len(x) == n_vars` when `feasible` is True and `len(x)
    == 0` when it is not — this driver returns a point only when it has re-verified that point
    against the CALLER's own rows and bounds, and `has_objective` follows the same flag
    because the value of an unverified point is not an upper bound on anything. (Stated by
    length rather than as "non-empty iff feasible" because a ZERO-VARIABLE model is a real
    model whose answer is the empty point: `n == 0` with satisfiable rows is feasible, optimal
    and has an objective, with nothing to put in `x`.)

    So `x` is EMPTY, `has_objective` False and every dual list EMPTY for `QP_INFEASIBLE`,
    `QP_UNBOUNDED`, `QP_NUMERICAL_BREAKDOWN` and every input rejection: the closest point to
    an infeasible region, the last iterate of an unbounded descent and the state left by a
    failed factorisation are not answers. `feasible` describes the RETURNED point, so it is
    False for `QP_UNBOUNDED` — which does not mean the region is empty (that is
    `QP_INFEASIBLE`); it means there is no point worth returning.

    `QP_ITERATION_LIMIT` and `QP_NOT_CERTIFIED` DO carry `x`, and this is deliberate — the
    same choice `integer.milp_solve` makes for a truncated branch-and-bound. The point was
    verified feasible against the caller's own arrays (`feasible`), so `objective` is a real
    value at a real point and a true upper bound on the optimum; `best_bound` and `gap` say
    how much room is left. What is NOT claimed is optimality: `proven_optimal` is False,
    `certified` is False, and the status says which of the two happened.

    `proven_optimal` requires the KKT audit AND a measured gap of zero. `certified` is the
    audit alone. They are separate fields because they are separate claims, and a case where
    they disagree is a defect this driver would rather surface than average away.

    `row_active` / `lower_active` / `upper_active` are the ACTIVE SET the search finished on —
    which rows it treated as equalities — while `binding` is the MEASURED tightness of each
    row at `x`. They usually agree; where they do not, the difference is the interesting
    part, so both are reported rather than one inferred from the other.

    `ray` is populated only for `QP_UNBOUNDED`: a direction `d`, scaled to unit max-norm,
    for which `Q d = 0`, `cᵀd < 0` and `x + t d` is feasible for every `t > 0`. All three
    were verified before the status was returned.

    `path_signature` identifies the search path (keyed scan order, then every add and drop).
    Equal seeds give equal signatures; different seeds may not, and must still give the same
    optimum.

    `slackness_violation` carries the DUAL magnitude of the worst both-directions slackness
    failure; `qp_kkt_check` reports the distance as well, because a caller fixing the model
    needs to know which of the two to move. `bound_status` is the bounding LP's own status and
    keeps its `MODEL_OK` default when no bound solve was attempted at all — `has_bound` is the
    authority on whether a bound exists, never the status code.
    """

    var status: Int
    var feasible: Bool
    var proven_optimal: Bool
    var certified: Bool
    var convex: Bool
    var symmetric: Bool
    var has_objective: Bool
    var objective: Float64
    var has_bound: Bool
    var best_bound: Float64
    var has_gap: Bool
    var gap: Float64
    var bound_status: Int
    var n_vars: Int
    var n_constraints: Int
    var iterations: Int
    var n_added: Int
    var n_dropped: Int
    var n_zero_curvature: Int
    var n_active: Int
    var rank_active: Int
    var degenerate_active_set: Bool
    var asymmetry: Float64
    var min_pivot: Float64
    var q_rank: Int
    var q_fail_index: Int
    var stationarity_violation: Float64
    var primal_violation: Float64
    var dual_violation: Float64
    var slackness_violation: Float64
    var stationarity_ok: Bool
    var primal_ok: Bool
    var dual_ok: Bool
    var slackness_ok: Bool
    var phase1_status: Int
    var path_signature: Int
    var x: List[Float64]
    var duals: List[Float64]
    var lower_duals: List[Float64]
    var upper_duals: List[Float64]
    var activity: List[Float64]
    var slack: List[Float64]
    var binding: List[Bool]
    var row_active: List[Bool]
    var lower_active: List[Bool]
    var upper_active: List[Bool]
    var ray: List[Float64]
    var message: String

    fn __init__(out self):
        """Every field at its ABSENT value, so a return path sets only what it established.

        Deliberately not `@fieldwise_init`: 48 positional arguments include runs of five
        consecutive `Bool`s, and a swap inside such a run type-checks and inverts a claim
        (`certified` for `convex`, say) with nothing to catch it. This struct is only ever
        RETURNED, never taken as a parameter, so the runtime's generated table needs no
        memberwise constructor — see the packaging rules on return-only structs.
        """
        self.status = MODEL_OK
        self.feasible = False
        self.proven_optimal = False
        self.certified = False
        self.convex = False
        self.symmetric = False
        self.has_objective = False
        self.objective = 0.0
        self.has_bound = False
        self.best_bound = 0.0
        self.has_gap = False
        self.gap = 0.0
        self.bound_status = MODEL_OK
        self.n_vars = 0
        self.n_constraints = 0
        self.iterations = 0
        self.n_added = 0
        self.n_dropped = 0
        self.n_zero_curvature = 0
        self.n_active = 0
        self.rank_active = 0
        self.degenerate_active_set = False
        self.asymmetry = QP_ABSENT
        self.min_pivot = QP_ABSENT
        self.q_rank = -1
        self.q_fail_index = -1
        self.stationarity_violation = QP_ABSENT
        self.primal_violation = QP_ABSENT
        self.dual_violation = QP_ABSENT
        self.slackness_violation = QP_ABSENT
        self.stationarity_ok = False
        self.primal_ok = False
        self.dual_ok = False
        self.slackness_ok = False
        self.phase1_status = MODEL_OK
        self.path_signature = 0
        self.x = List[Float64]()
        self.duals = List[Float64]()
        self.lower_duals = List[Float64]()
        self.upper_duals = List[Float64]()
        self.activity = List[Float64]()
        self.slack = List[Float64]()
        self.binding = List[Bool]()
        self.row_active = List[Bool]()
        self.lower_active = List[Bool]()
        self.upper_active = List[Bool]()
        self.ray = List[Float64]()
        self.message = String("")


# ── internal-only structs ─────────────────────────────────────────────────────
# Never in a public signature, so they may live here freely.


@fieldwise_init
struct _Chol(Copyable, Movable):
    """A diagonal-pivoted `Pᵀ (S A S) P = L D Lᵀ` of a symmetric matrix. `L` is UNIT lower.

    ONE routine, used for two questions: is `Q` positive semidefinite (and where does it
    fail), and what is the exact step for the equality-constrained subproblem. They are the
    same factorisation, and writing it twice is how the two would come to disagree about
    what "singular" means.

    LDLᵀ and not LLᵀ, for two reasons that both matter here. It takes no square roots, so a
    DIAGONAL matrix factors and solves exactly: `Q = 2I` with `c = (-4, -6)` gives exactly
    `(2, 3)`, where the `sqrt(2)` round trip of a Cholesky returns `1.9999999999999998` and
    turns a closed-form test into a tolerance test. And its pivots are the Schur complements
    themselves, so `min_pivot` is a number in the matrix's own units rather than its root,
    and a semidefinite matrix with exact zero pivots needs no special case.

    `scale` is the EQUILIBRATION `S = diag(s_i)`: the factorisation is of `S A S`, not of
    `A`. See `_ldl_factor` for why, and for why every `s_i` is a power of two. `l` and `d`
    are therefore in the EQUILIBRATED units and `_ldl_solve` / `_ldl_null_vector` undo the
    scaling; `min_pivot` and `fail_value` are converted back to the CALLER's units, because
    they are reported to the caller and a number in an internal unit system is worse than no
    number.

    `psd` False means a pivot was negative beyond the rounding budget for the diagonal entry
    it belongs to, or a trailing block with a dead diagonal carried a live off-diagonal entry
    — which is indefinite, since `|a_ij| <= sqrt(a_ii a_jj)` for a PSD matrix.
    """

    var psd: Bool
    var rank: Int
    var k: Int
    var perm: List[Int]
    var l: List[Float64]
    var d: List[Float64]
    var scale: List[Float64]
    var min_pivot: Float64
    var fail_index: Int
    var fail_value: Float64


@fieldwise_init
struct _Rows(Copyable, Movable):
    """The feasible set as ONE system: `<=` rows and `=` rows, bounds included as rows.

    A `>=` row is stored negated, a lower bound becomes `-x_j <= -l_j` and an upper bound
    becomes `x_j <= u_j`, so the active-set machinery has one kind of object to reason about
    and there is no second code path for bounds to drift from. `origin` is what maps a
    multiplier back to the caller's own row or bound, and `flip` is the ±1 that maps its
    sign back.
    """

    var m: Int
    var n: Int
    var g: List[Float64]
    var h: List[Float64]
    var is_eq: List[Bool]
    var origin: List[Int]
    var flip: List[Float64]
    var row_norm: List[Float64]


@fieldwise_init
struct _NullSpace(Copyable, Movable):
    """An orthonormal split of R^n into the active rows' span and its complement.

    `q` (rank x n) spans the active rows; `z` (nz x n) is the complement, along which a step
    keeps every active row exactly satisfied. `r` (n x k, upper trapezoidal) and `pivot_col`
    are the modified-Gram-Schmidt factors of the active-row matrix TRANSPOSED, kept so the
    multipliers come out of the same factorisation that produced `z` — a second, independent
    solve for the duals is a second chance to disagree about which rows are dependent.
    """

    var ok: Bool
    var rank: Int
    var nz: Int
    var k: Int
    var n: Int
    var q: List[Float64]
    var qn2: List[Float64]
    var z: List[Float64]
    var zn2: List[Float64]
    var r: List[Float64]
    var pivot_col: List[Int]


@fieldwise_init
struct _Convex(Copyable, Movable):
    """The convexity gate's findings plus the symmetrised matrix the solver then uses."""

    var status: Int
    var symmetric: Bool
    var convex: Bool
    var asymmetry: Float64
    var rank: Int
    var min_pivot: Float64
    var fail_index: Int
    var fail_value: Float64
    var q_sym: List[Float64]
    var message: String


# ── small numeric helpers ─────────────────────────────────────────────────────


fn _zeros(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(n):
        out.append(0.0)
    return out^


fn _falses(n: Int) -> List[Bool]:
    var out = List[Bool]()
    for _ in range(n):
        out.append(False)
    return out^


fn _max_abs(v: List[Float64]) -> Float64:
    var best: Float64 = 0.0
    for i in range(len(v)):
        var m = fabs(v[i])
        if m > best:
            best = m
    return best


fn _unscale2(v: Float64, si: Float64, sj: Float64) -> Float64:
    """`v / (si · sj)`, divided one factor at a time.

    Both factors are powers of two, so each division is exact; done SEPARATELY because
    `si · sj` can itself overflow or underflow to zero when the two exponents are far apart,
    and a product that has overflowed would silently return 0.0 for a number that exists.
    """
    return (v / si) / sj


fn _matvec(q: List[Float64], n: Int, x: List[Float64]) -> List[Float64]:
    """`Q x` for a flat row-major `Q`. Callers have already established `len(q) == n*n`."""
    var out = List[Float64]()
    for i in range(n):
        var acc: Float64 = 0.0
        var base = i * n
        for j in range(n):
            acc += q[base + j] * x[j]
        out.append(acc)
    return out^


fn _objective_value(q: List[Float64], n: Int, c: List[Float64], x: List[Float64]) -> Float64:
    """`0.5 xᵀQx + cᵀx`, through the frozen `vec_dot` rather than a hand-rolled loop."""
    var qx = _matvec(q, n, x)
    return 0.5 * vec_dot(x, qx) + vec_dot(c, x)


fn _all_finite(v: List[Float64]) -> Bool:
    for i in range(len(v)):
        if not _finite(v[i]):
            return False
    return True


fn _fold(h: UInt64, v: UInt64, stream: UInt64) -> UInt64:
    """Mix one value into a path signature through the FROZEN Philox core.

    Not a new hash: `philox_word` is the tree's specified counter-based mixer and
    `feature_hashing.hash_feature` is its FNV over BYTES, which is a different input type.
    Reusing the mixer keeps the number of hash definitions in the tree at the number it
    already was.
    """
    return philox_word(h, v, 0, 0, 0, stream, 0) ^ h


fn _unsigned(v: Int) -> UInt64:
    """A signed decision index as a fold input. Negative indices are real (-1 = none)."""
    if v < 0:
        return UInt64(-v) ^ 0x8000000000000000
    return UInt64(v)


# ── the pivoted LDLt, used for convexity AND for the subproblem step ──────────


fn _pow2_scale(m: Float64) -> Float64:
    """The power of two `s` with `m·s² ∈ [1, 4)`, or exactly 1.0 when `m` cannot be scaled.

    A POWER OF TWO, not `1/sqrt(m)`: multiplying by a power of two only moves a double's
    exponent, so `s_i · a_ij · s_j` is computed with NO rounding whatsoever. That is what
    lets `_ldl_factor` say that the equilibrated matrix IS the caller's matrix rather than a
    nearby one — the scaling cannot move a verdict it is not allowed to move.

    `m <= 0` and a non-finite `m` return 1.0: a zero diagonal has no scale of its own (a PSD
    matrix's zero diagonal forces a zero row, which is judged at its neighbours' scale), and
    a negative or non-finite one is refuted by the factorisation itself rather than scaled.

    Bounded work: each loop step moves the exponent by 2, and a double's exponent range is
    2^-1074 .. 2^1024, so at most 550 iterations — charged per DIAGONAL entry, so `k` rows
    cost at most 550k multiplications, which is below the `k²` the factorisation already
    pays for reading the matrix once.
    """
    if not (m > 0.0) or not _finite(m):
        return 1.0
    var v = m
    var s: Float64 = 1.0
    while v >= 4.0:
        v = v * 0.25
        s = s * 0.5
    while v < 1.0:
        v = v * 4.0
        s = s * 2.0
    return s


fn _ldl_factor(a: List[Float64], k: Int) -> _Chol:
    """Diagonal-pivoted `L D Lᵀ` of a symmetric `k x k` flat matrix, with a PSD verdict.

    THE MATRIX IS SYMMETRICALLY EQUILIBRATED FIRST, and that is the whole reason this routine
    can state a rounding budget at all. `S = diag(s_i)` with `s_i` the power of two putting
    `s_i² |a_ii|` in `[1, 4)`, and the factorisation runs on `Ã = S A S`. Three facts make
    that sound, and all three are needed:

      1. `S` is a nonsingular diagonal, so `Ã` is a CONGRUENCE of `A`. By Sylvester's law of
         inertia a congruence preserves the number of positive, negative and zero
         eigenvalues exactly, so `Ã` is PSD if and only if `A` is, and `rank Ã == rank A`.
         The scaling cannot change the verdict.
      2. Every `s_i` is a power of two, so `s_i a_ij s_j` is EXACT (barring overflow, which
         is detected and is itself a refutation — see below). So the matrix factored is not
         merely close to the caller's matrix, it is the caller's matrix in different units,
         and no rounding is introduced by the transform.
      3. After the transform every nonzero diagonal entry is in `[1, 4)` and, for a PSD
         matrix, `|ã_ij| <= sqrt(ã_ii ã_jj) < 4` — so ONE absolute tolerance in the
         equilibrated space IS a per-entry relative tolerance in the caller's:
         `|ã_ij| <= t` says `|a_ij| <= t·sqrt(a_ii a_jj)` up to a factor of two.

    That last point is the defect this replaces. The tolerance used to be
    `budget · eps · (k+1) · max_i |a_ii|` — a MAXIMUM OVER THE WHOLE MATRIX — so with a
    diagonal of 1e12 present the negative-pivot test accepted an eigenvalue of -0.68 as
    "rounding", and the termination test called a live pivot of 0.5 dead, reporting `rank 1`
    and `min_pivot 1e12` for `diag(1e12, 0.5)`. In the equilibrated space "the largest
    trailing diagonal is at the noise floor" and "every trailing diagonal is at ITS OWN noise
    floor" are the same statement, because every diagonal has the same scale. That is why
    equilibrating is the fix and not a per-entry tolerance bolted onto unscaled arithmetic:
    the pivot ORDER has to agree with the tolerance, or the routine divides by a pivot it has
    already called noise.

    Pivoting on the largest trailing diagonal of `Ã` — i.e. the largest RELATIVE to its own
    original diagonal — is what makes this a semidefiniteness test rather than a definiteness
    test: for a PSD matrix the pivoted factorisation runs to the matrix's rank and then finds
    a trailing block that is zero, while for an indefinite one it finds either a negative
    pivot or a dead diagonal with a live off-diagonal (impossible when
    `|a_ij| <= sqrt(a_ii a_jj)`). Both refutations are reported with the offending index and
    value in the CALLER's index space AND in the caller's units.

    The frozen `matrix_decomp.cholesky` and `linalg_ext.mat_is_positive_definite` answer the
    STRICT question and return an empty list / False for a singular-but-convex matrix, so
    they cannot distinguish "flat in one direction" from "not convex" — which is the
    distinction between an unbounded QP and a rejected model. `mat_is_positive_definite` is
    still called by `qp_convexity_flat`, where strict definiteness is a separate reported
    fact and the frozen kernel is the authority on it.

    Ties in the pivot choice go to the earliest position in the current working order, never
    to a keyed draw: whether a model is convex must not move when a seed moves. The
    equilibration does not change that — every `s_i` is a deterministic function of `a_ii`.
    """
    var scale = List[Float64]()
    for i in range(k):
        scale.append(_pow2_scale(fabs(a[i * k + i])))
    var perm = List[Int]()
    for i in range(k):
        perm.append(i)
    var diag = _zeros(k)

    var w = List[Float64]()
    var over_i = -1
    var over_j = -1
    for i in range(k):
        for j in range(k):
            var v = a[i * k + j] * scale[i] * scale[j]
            if not _finite(v) and over_i < 0:
                over_i = i
                over_j = j
            w.append(v)
    if over_i >= 0:
        # `s_i a_ij s_j` overflowed while `s_i² a_ii` and `s_j² a_jj` are both under 4, so
        # `|a_ij|` exceeds `sqrt(a_ii a_jj)` by more than 1e150: the 2x2 minor
        # `a_ii a_jj - a_ij²` is hugely negative and the matrix is indefinite. A refutation,
        # not a breakdown — the evidence is in the caller's own numbers.
        return _Chol(
            False, 0, k, perm^, w^, diag^, scale^, 0.0, over_i, a[over_i * k + over_j]
        )

    # The noise floor of any entry of the EQUILIBRATED matrix: `(k + 1)` rank-1 updates of
    # entries whose own magnitude is 4 or less. Absolute here, relative to
    # `sqrt(a_ii a_jj)` in the caller's units — which is the scale of the one quantity being
    # judged and of nothing else. Zero diagonals scale to exactly 0 and are dead at any
    # floor, which is right: the zero matrix is PSD of rank 0.
    var tol = LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * Float64(k + 1)

    var rank = 0
    var min_pivot: Float64 = 0.0
    var psd = True
    var fail_index = -1
    var fail_value: Float64 = 0.0

    for step in range(k):
        var p = step
        var best = w[step * k + step]
        for i in range(step + 1, k):
            var d = w[i * k + i]
            if d > best:
                best = d
                p = i
        if best <= tol:
            # Nothing left above the noise floor — and because the matrix is equilibrated,
            # "the largest trailing diagonal is at the floor" means EVERY trailing diagonal
            # is at its own floor, which is the statement that actually justifies stopping.
            # PSD now REQUIRES the whole trailing block to vanish; a live entry refutes it.
            for i in range(step, k):
                if w[i * k + i] < -tol:
                    psd = False
                    fail_index = perm[i]
                    fail_value = _unscale2(
                        w[i * k + i], scale[perm[i]], scale[perm[i]]
                    )
                    break
                for j in range(step, i + 1):
                    if fabs(w[i * k + j]) > tol:
                        psd = False
                        fail_index = perm[i]
                        fail_value = _unscale2(
                            w[i * k + j], scale[perm[i]], scale[perm[j]]
                        )
                        break
                if not psd:
                    break
            break
        if p != step:
            # Symmetric permutation: swap rows AND columns, including the already-computed
            # factor columns to the left of `step`.
            #
            # THIS IS WHY THE TRAILING BLOCK IS KEPT ON BOTH SIDES OF THE DIAGONAL. A
            # lower-triangle-only update leaves the upper triangle holding the ORIGINAL
            # entries, and a full row/column swap then moves those stale values into
            # lower-triangle positions — silently, and only when a pivot actually moves.
            # Measured: `Q = L Lᵀ` with `L` of deficient rank is positive semidefinite by
            # construction, and every such instance that needed a swap came back
            # `QP_ERR_NOT_CONVEX` — a legitimate convex model refused. Not one hand-written
            # case pivoted (a diagonal `Q`, or one whose largest diagonal is already first,
            # never does), so 33 passing assertions said nothing about it.
            var t = perm[step]
            perm[step] = perm[p]
            perm[p] = t
            for j in range(k):
                var tmp = w[step * k + j]
                w[step * k + j] = w[p * k + j]
                w[p * k + j] = tmp
            for i in range(k):
                var tmp2 = w[i * k + step]
                w[i * k + step] = w[i * k + p]
                w[i * k + p] = tmp2
        var piv = w[step * k + step]
        # REPORTED in the caller's units, computed in the equilibrated ones. `min_pivot` is
        # the number a caller judges conditioning by, so it is the smallest Schur complement
        # of the CALLER's matrix — for `diag(1e12, 0.5)` that is 0.5, and reporting 1e12
        # (the largest) is worse than reporting nothing, because it reads as reassurance.
        var piv_caller = _unscale2(piv, scale[perm[step]], scale[perm[step]])
        if rank == 0 or piv_caller < min_pivot:
            min_pivot = piv_caller
        diag[step] = piv
        # `L` keeps an IMPLICIT unit diagonal, so the stored column is the Schur ratio and
        # no square root enters the factor.
        for i in range(step + 1, k):
            w[i * k + step] = w[i * k + step] / piv
        for j in range(step + 1, k):
            var ljk = w[j * k + step] * piv
            if ljk != 0.0:
                # `range(step + 1, k)`, NOT `range(j, k)`: the whole trailing block, both
                # triangles, so that a later symmetric swap has consistent data to move. The
                # extra work is a factor of two on the update and buys the pivoting.
                for i in range(step + 1, k):
                    w[i * k + j] -= w[i * k + step] * ljk
        rank += 1

    return _Chol(
        psd, rank, k, perm^, w^, diag^, scale^, min_pivot, fail_index, fail_value
    )


fn _ldl_solve(ch: _Chol, rhs: List[Float64]) -> List[Float64]:
    """One solution of `A y = rhs` using the rank-sized leading block, or all zeros for rank 0.

    The factor is of `Ã = S A S`, so the scaling is undone HERE and not by the caller:
    `A y = rhs` is `Ã (S⁻¹y) = S rhs`, so the right-hand side is scaled going in and the
    solution scaled coming out. `S` is a power of two per entry, so both are exact.

    The trailing components of `y` are set to zero, which picks ONE solution out of an affine
    set when `A` is singular. Consistency is NOT assumed: every caller re-multiplies and
    checks the residual, because a system with no solution is a different outcome from a
    system with many. For a diagonal `A` both triangular solves are the identity and the
    answer is exactly `rhs / d` — the equilibration does not change that, because dividing by
    `s²a_ii` after multiplying by `s` leaves one rounding, exactly as `rhs/a_ii` does.
    """
    var k = ch.k
    var out = _zeros(k)
    if ch.rank == 0:
        return out^
    var z = _zeros(ch.rank)
    for i in range(ch.rank):
        var acc = rhs[ch.perm[i]] * ch.scale[ch.perm[i]]
        for t in range(i):
            acc -= ch.l[i * k + t] * z[t]
        z[i] = acc
    for i in range(ch.rank):
        z[i] = z[i] / ch.d[i]
    var y = _zeros(k)
    for t in range(ch.rank - 1, -1, -1):
        var acc = z[t]
        for i in range(t + 1, ch.rank):
            acc -= ch.l[i * k + t] * y[i]
        y[t] = acc
    for i in range(k):
        out[ch.perm[i]] = y[i]
    for i in range(k):
        out[i] = out[i] * ch.scale[i]
    return out^


fn _ldl_null_vector(ch: _Chol, s: Int) -> List[Float64]:
    """Null basis vector `s` of the factored matrix, in the caller's index space.

    `Pᵀ Ã P = L D Lᵀ` with `L` of full column rank `rank` and `D` nonsingular on that block,
    so `null(Ã) = P · null(Lᵀ)`. Split `Lᵀ = [L11ᵀ  L21ᵀ]`: `y = [-(L11ᵀ)⁻¹ L21ᵀ e_s ; e_s]`
    closes it, and `L11` is UNIT triangular, so the back substitution divides by nothing.

    `Ã = S A S` with `S` nonsingular, so `A y = 0` iff `Ã (S⁻¹y) = 0`: the null space of the
    caller's matrix is `S · null(Ã)`, and the scaling is undone here for the same reason
    `_ldl_solve` undoes it — a direction in internal units is not a direction the caller's
    rows can be checked against.

    Returned normalised to unit 2-norm; the caller still verifies the curvature along it,
    because a claimed null direction is exactly the kind of claim that must be checked rather
    than trusted.
    """
    var k = ch.k
    var y = _zeros(k)
    var row = ch.rank + s
    if row >= k:
        return y^
    y[row] = 1.0
    for t in range(ch.rank - 1, -1, -1):
        var acc = -ch.l[row * k + t]
        for i in range(t + 1, ch.rank):
            acc -= ch.l[i * k + t] * y[i]
        y[t] = acc
    var out = _zeros(k)
    for i in range(k):
        out[ch.perm[i]] = y[i]
    for i in range(k):
        out[i] = out[i] * ch.scale[i]
    var nrm = vec_norm(out)
    if nrm > 0.0:
        for i in range(k):
            out[i] = out[i] / nrm
    return out^


# ── convexity gate ────────────────────────────────────────────────────────────


fn _nested_pair_relative(q: List[Float64], n: Int) -> List[List[Float64]]:
    """`Q` with every entry divided by ITS OWN PAIR's magnitude, for the frozen symmetry test.

    A NESTED list is not marshalable and must never appear in a public signature here; it is
    built internally, for the frozen call, and discarded.

    `N_ij = Q_ij / (|Q_ij| + |Q_ji|)`, so `N_ij - N_ji` is the asymmetry of that ONE pair
    measured in that pair's own units, and the frozen `is_symmetric`'s single tolerance
    becomes a PER-PAIR relative one. A pair of exact zeros has no asymmetry and no scale, so
    it is stored as 0 and passes.

    Written this way rather than by passing `is_symmetric` a tolerance built from the whole
    matrix: `max_ij |Q_ij|` is an aggregate over every OTHER entry, so with one diagonal at
    1e12 the tolerance reached 0.68 and `Q_01 = 0.3` against `Q_10 = 0.7` — a flat
    contradiction — was reported symmetric. The verdict stays the frozen kernel's; only the
    units it judges in are ours.
    """
    var out = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            var pair = fabs(q[i * n + j]) + fabs(q[j * n + i])
            if pair > 0.0:
                row.append(q[i * n + j] / pair)
            else:
                row.append(0.0)
        out.append(row^)
    return out^


fn _convexity(q: List[Float64], n: Int) -> _Convex:
    """Symmetry then semidefiniteness, both measured, on an already-validated `Q`."""
    var asymmetry: Float64 = 0.0
    var worst_rel: Float64 = 0.0
    var worst_i = -1
    var worst_j = -1
    for i in range(n):
        for j in range(i + 1, n):
            var d = fabs(q[i * n + j] - q[j * n + i])
            if d > asymmetry:
                asymmetry = d
            var pair = fabs(q[i * n + j]) + fabs(q[j * n + i])
            var rel = d / pair if pair > 0.0 else 0.0
            if rel > worst_rel:
                worst_rel = rel
                worst_i = i
                worst_j = j
    # PER PAIR, relative to that pair's own two entries. An absolute 1e-10 (the frozen
    # default) calls a matrix of 1e12 entries asymmetric for a rounding difference and a
    # matrix of 1e-12 entries symmetric for a total contradiction; a tolerance scaled by the
    # matrix's LARGEST entry does the second thing to every small entry in a mixed-unit
    # matrix, which is the same defect one level up.
    var sym_tol = LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * Float64(n + 1)
    # The VERDICT is the frozen kernel's; the MEASUREMENT is ours, because a Bool does not
    # tell a caller which entry to correct.
    var nested = _nested_pair_relative(q, n)
    var symmetric = is_symmetric(nested, sym_tol)
    if not symmetric:
        return _Convex(
            QP_ERR_NOT_SYMMETRIC, False, False, asymmetry, -1, 0.0, -1, 0.0,
            List[Float64](),
            "Q is not symmetric: max |Q_ij - Q_ji| = " + String(asymmetry)
            + ", worst pair (" + String(worst_i) + ", " + String(worst_j)
            + ") differs by " + String(worst_rel)
            + " of its own magnitude, past " + String(sym_tol)
            + "; the quadratic form only sees (Q + Qt)/2, so symmetrise explicitly",
        )

    var q_sym = List[Float64]()
    for i in range(n):
        for j in range(n):
            q_sym.append(0.5 * (q[i * n + j] + q[j * n + i]))

    var ch = _ldl_factor(q_sym, n)
    if not ch.psd:
        return _Convex(
            QP_ERR_NOT_CONVEX, True, False, asymmetry, ch.rank, ch.min_pivot,
            ch.fail_index, ch.fail_value, q_sym^,
            "Q is not positive semidefinite: pivot " + String(ch.fail_index)
            + " is " + String(ch.fail_value)
            + "; minimising a non-convex quadratic has no global answer to report",
        )
    return _Convex(
        MODEL_OK, True, True, asymmetry, ch.rank, ch.min_pivot, -1, 0.0, q_sym^, String("")
    )


# ── input validation ──────────────────────────────────────────────────────────


fn _qp_shape_defect(
    q: List[Float64], n: Int, c: List[Float64], a: List[Float64], rows: Int,
    senses: List[Int], b: List[Float64], lower: List[Float64], upper: List[Float64],
    bound_flags: List[Int],
) -> Int:
    """`MODEL_OK` when every length, shape, sense, bound and magnitude is usable.

    Called before ANYTHING is indexed. A read past a List end is an uncatchable process
    crash — not an exception — and the generated A-Z suite calls every contract function with
    five-element lists and the integer 5, so `qp_solve(_lf5, 5, _lf5, _lf5, 5, ...)` reaches
    this function with `len(q) == 5` and `n == 5`.

    `dims_fit` (DIVISION, never `n * n == len(q)`) does two jobs at once: it rejects the
    wrapping-multiply shape, and it ties `n` to what the payload actually carries, so no
    declared dimension can allocate memory the request did not pay for.
    """
    if n < 0 or rows < 0:
        return MODEL_ERR_DENSE_SHAPE
    if not dims_fit(n, n, len(q)):
        return MODEL_ERR_DENSE_SHAPE
    if not dims_fit(rows, n, len(a)):
        return MODEL_ERR_DENSE_SHAPE
    if n > MAX_CSR_DIM or rows > MAX_CSR_DIM:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    if len(c) != n:
        return MODEL_ERR_LENGTH_MISMATCH
    if len(senses) != rows or len(b) != rows:
        return MODEL_ERR_LENGTH_MISMATCH
    if len(lower) != n or len(upper) != n or len(bound_flags) != n:
        return MODEL_ERR_LENGTH_MISMATCH
    if n > 0:
        # Areas, by division: `n*n <= budget`, then the internal row matrix `m x n` and the
        # split LP matrix `m x 2n` for the widest `m` this call can build, which is
        # `rows + 2n` (one row per declared bound). `rows` and `n` are both under
        # MAX_CSR_DIM here, so `rows + 2*n` cannot wrap.
        if n > QP_MAX_MATRIX_CELLS // n:
            return MODEL_ERR_DIMENSION_TOO_LARGE
        var m_max = rows + 2 * n
        if m_max > QP_MAX_MATRIX_CELLS // (2 * n):
            return MODEL_ERR_DIMENSION_TOO_LARGE
        # And the phase-1 tableau itself: `m` rows over `2n` split columns plus at most one
        # slack and one artificial per row. Checked here so the rejection names the shape
        # instead of surfacing as an LP status three calls down.
        var lp_width = 2 * n + 2 * m_max + 1
        if m_max > LP_MAX_TABLEAU_CELLS // lp_width:
            return MODEL_ERR_DIMENSION_TOO_LARGE
    if not _all_finite(q):
        return MODEL_ERR_NON_FINITE_COEFFICIENT
    if not _all_finite(c):
        return MODEL_ERR_NON_FINITE_COEFFICIENT
    if not _all_finite(a):
        return MODEL_ERR_NON_FINITE_COEFFICIENT
    for i in range(rows):
        if senses[i] != SENSE_LE and senses[i] != SENSE_EQ and senses[i] != SENSE_GE:
            return MODEL_ERR_SENSE
        if not _finite(b[i]):
            return MODEL_ERR_NON_FINITE_RHS
    for j in range(n):
        var f = bound_flags[j]
        if not var_flags_valid(f):
            return MODEL_ERR_VAR_FLAGS
        if (f & VAR_FLAG_HAS_START) != 0:
            # There is no warm start on this entry point. Accepting the bit and ignoring it
            # would let a caller believe a starting point was honoured.
            return MODEL_ERR_VAR_FLAGS
        # A bound value is read ONLY when its flag is set, so unflagged padding may be
        # anything — including an infinity, which is the natural padding for "no bound".
        if has_lower_bound(f) and not _finite(lower[j]):
            return MODEL_ERR_NON_FINITE_BOUND
        if has_upper_bound(f) and not _finite(upper[j]):
            return MODEL_ERR_NON_FINITE_BOUND
        if has_lower_bound(f) and has_upper_bound(f) and lower[j] > upper[j]:
            return MODEL_ERR_BOUNDS_CROSSED
    return MODEL_OK


# ── the feasible set as one row system ────────────────────────────────────────


fn _build_rows(
    a: List[Float64], rows: Int, n: Int, senses: List[Int], b: List[Float64],
    lower: List[Float64], upper: List[Float64], bound_flags: List[Int],
) -> _Rows:
    """Caller rows and declared bounds as one `<=`/`=` system. Origins kept for the duals."""
    var g = List[Float64]()
    var h = List[Float64]()
    var is_eq = List[Bool]()
    var origin = List[Int]()
    var flip = List[Float64]()
    var m = 0
    for i in range(rows):
        var sgn: Float64 = 1.0
        if senses[i] == SENSE_GE:
            sgn = -1.0
        for j in range(n):
            g.append(sgn * a[i * n + j])
        h.append(sgn * b[i])
        is_eq.append(senses[i] == SENSE_EQ)
        origin.append(i)
        flip.append(sgn)
        m += 1
    for j in range(n):
        if has_lower_bound(bound_flags[j]):
            for t in range(n):
                if t == j:
                    g.append(-1.0)
                else:
                    g.append(0.0)
            h.append(-lower[j])
            is_eq.append(False)
            origin.append(rows + j)
            flip.append(-1.0)
            m += 1
    for j in range(n):
        if has_upper_bound(bound_flags[j]):
            for t in range(n):
                if t == j:
                    g.append(1.0)
                else:
                    g.append(0.0)
            h.append(upper[j])
            is_eq.append(False)
            origin.append(rows + n + j)
            flip.append(1.0)
            m += 1
    var row_norm = List[Float64]()
    for i in range(m):
        var acc: Float64 = 0.0
        for j in range(n):
            acc += g[i * n + j] * g[i * n + j]
        row_norm.append(sqrt(acc))
    return _Rows(m, n, g^, h^, is_eq^, origin^, flip^, row_norm^)


fn _row_activity(rw: _Rows, i: Int, x: List[Float64]) -> Float64:
    var acc: Float64 = 0.0
    for j in range(rw.n):
        acc += rw.g[i * rw.n + j] * x[j]
    return acc


fn _row_terms_scale(rw: _Rows, i: Int, x: List[Float64]) -> Float64:
    """`|h_i| + Σ_j |g_ij x_j|` — the magnitude of the terms THIS row's residual is made of.

    Spans exactly one row. An aggregate over rows is what let 200 ordinary capacity rows pay
    for one flat contradiction and report an infeasible program as optimal.

    This is the INTERNAL-row twin of `_primal_scan`'s per-row scale, and the duplication is
    deliberate rather than overlooked: the internal system carries the declared bounds as rows
    of its own, so the two range over different objects. Nothing decides feasibility from this
    one — it sizes the "is this row already tight?" test that seeds the active set — and every
    feasibility and slackness verdict comes from `_primal_scan`, on the caller's own arrays.
    """
    var acc = fabs(rw.h[i])
    for j in range(rw.n):
        acc += fabs(rw.g[i * rw.n + j] * x[j])
    return acc


fn _split_lp(
    rw: _Rows, obj: List[Float64], n: Int, max_iterations: Int,
    feasibility_tol: Float64, optimality_tol: Float64,
) -> LPSolution:
    """Minimise `objᵀx` over the internal row system, through `linear.lp_solve`.

    `lp_solve` imposes `x >= 0` on its own columns, and a QP variable may be negative or
    unbounded below, so each `x_j` crosses as the difference of two non-negative columns
    `u_j - v_j`. That is the standard split, it is exact, and it keeps ONE verified simplex
    as the only feasibility authority in the package rather than adding a second one here.
    """
    var m = rw.m
    var cols = 2 * n
    var a2 = List[Float64]()
    for i in range(m):
        for j in range(n):
            a2.append(rw.g[i * n + j])
        for j in range(n):
            a2.append(-rw.g[i * n + j])
    var senses2 = List[Int]()
    for i in range(m):
        if rw.is_eq[i]:
            senses2.append(SENSE_EQ)
        else:
            senses2.append(SENSE_LE)
    var c2 = List[Float64]()
    for j in range(n):
        c2.append(obj[j])
    for j in range(n):
        c2.append(-obj[j])
    return lp_solve(
        c2, 0.0, a2, m, cols, senses2, rw.h, False,
        max_iterations, feasibility_tol, optimality_tol,
    )


fn _unsplit(sol: LPSolution, n: Int) -> List[Float64]:
    var x = List[Float64]()
    for j in range(n):
        x.append(sol.x[j] - sol.x[n + j])
    return x^


# ── the orthogonal split of R^n by the active rows ────────────────────────────


fn _null_space(rw: _Rows, w_set: List[Int], n: Int) -> _NullSpace:
    """Modified Gram-Schmidt on the active rows, with the complement basis and the R factor.

    The bases are ORTHOGONAL but deliberately NOT normalised, and each vector's squared norm
    travels with it. Nothing in the method needs unit length — `gz = Zᵀg`, `Hz = ZᵀQZ` and
    `p = Z pz` are correct for any basis of the null space — while normalising costs accuracy
    on exactly the models people write by hand. A single active row `x1 + x2 = 1` normalises
    by `sqrt(2)`, and the round trip through it returns the multiplier
    `-0.9999999999999999` where the unnormalised division by `||q||² = 2` returns exactly
    `-1`. The pivot entry of `R` is then exactly `1.0`, so the multiplier back-substitution
    divides by nothing at all.

    Twice-orthogonalised (the classic re-orthogonalisation): once is not enough to keep the
    complement orthogonal to the row span when the rows are nearly dependent, and a `Z` that
    is not in the null space produces a step that violates an active row, which then reads as
    a feasibility failure rather than as the arithmetic error it is.

    Rebuilt every iteration rather than updated. See the header: an updated factorisation
    accumulates the error of every pivot and the drift surfaces as an optimality claim.
    """
    var k = len(w_set)
    var q = List[Float64]()
    var qn2 = List[Float64]()
    var r = _zeros(n * k) if k > 0 else List[Float64]()
    var pivot_col = List[Int]()
    var rank = 0
    for idx in range(k):
        var row = w_set[idx]
        var v = List[Float64]()
        for j in range(n):
            v.append(rw.g[row * n + j])
        var norm0 = vec_norm(v)
        for _pass in range(2):
            for t in range(rank):
                var dot: Float64 = 0.0
                for j in range(n):
                    dot += v[j] * q[t * n + j]
                var coef = dot / qn2[t]
                for j in range(n):
                    v[j] -= coef * q[t * n + j]
                r[t * k + idx] += coef
        var nrm = vec_norm(v)
        if not _finite(nrm):
            return _NullSpace(
                False, 0, 0, k, n, List[Float64](), List[Float64](), List[Float64](),
                List[Float64](), List[Float64](), List[Int](),
            )
        # A row is dependent when what survives orthogonalisation is at the level the
        # elimination could have produced from the row's own magnitude.
        var dep_tol = LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * Float64(n + 1) * norm0
        if nrm > dep_tol and rank < n:
            for j in range(n):
                q.append(v[j])
            qn2.append(vec_dot(v, v))
            r[rank * k + idx] = 1.0
            pivot_col.append(idx)
            rank += 1

    var z = List[Float64]()
    var zn2 = List[Float64]()
    var nz = 0
    for j in range(n):
        if rank + nz >= n:
            break
        var v = _zeros(n)
        v[j] = 1.0
        for _pass in range(2):
            for t in range(rank):
                var dot: Float64 = 0.0
                for i in range(n):
                    dot += v[i] * q[t * n + i]
                var coef = dot / qn2[t]
                for i in range(n):
                    v[i] -= coef * q[t * n + i]
            for t in range(nz):
                var dot2: Float64 = 0.0
                for i in range(n):
                    dot2 += v[i] * z[t * n + i]
                var coef2 = dot2 / zn2[t]
                for i in range(n):
                    v[i] -= coef2 * z[t * n + i]
        var nrm = vec_norm(v)
        # `e_j` has norm exactly 1, so the same relative rule with scale 1.
        if nrm > LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * Float64(n + 1):
            for i in range(n):
                z.append(v[i])
            zn2.append(vec_dot(v, v))
            nz += 1
    return _NullSpace(True, rank, nz, k, n, q^, qn2^, z^, zn2^, r^, pivot_col^)


fn _multipliers(ns: _NullSpace, g: List[Float64]) -> List[Float64]:
    """Non-negative-side multipliers `μ` of the active rows from `A_Wᵀ μ = -g`.

    Consistent exactly when `Zᵀg = 0`, which is what "the step is zero" means, and solved by
    back-substitution on the SAME MGS factor that produced `Z` — not by a second, independent
    solve, which is a second chance to disagree about which rows are dependent.

    `-g` is expanded in the (orthogonal, unnormalised) basis by dividing by each vector's own
    squared norm, and the pivot entries of `R` are exactly 1, so the back-substitution is
    subtraction and one division per row. A dependent active row gets `μ = 0`: its multiplier
    is genuinely ambiguous, the choice is stated, and `degenerate_active_set` reports that the
    situation arose. The caller-facing certificate then has to pass on the numbers actually
    returned.
    """
    var k = ns.k
    var mu = _zeros(k)
    if ns.rank == 0:
        return mu^
    var cvec = _zeros(ns.rank)
    for t in range(ns.rank):
        var acc: Float64 = 0.0
        for j in range(ns.n):
            acc += ns.q[t * ns.n + j] * g[j]
        cvec[t] = -acc / ns.qn2[t]
    for t in range(ns.rank - 1, -1, -1):
        var p = ns.pivot_col[t]
        var acc = cvec[t]
        for i in range(p + 1, k):
            acc -= ns.r[t * k + i] * mu[i]
        mu[p] = acc / ns.r[t * k + p]
    return mu^


# ── primal feasibility against the CALLER's arrays ────────────────────────────


@fieldwise_init
struct _Primal(Copyable, Movable):
    """The caller's own rows and bounds, re-checked at a point. Never the internal system.

    The per-row and per-bound TOLERANCES travel with the result, because complementary
    slackness needs the same "is this row tight?" threshold that feasibility used. Recomputing
    the formula at the second call site is how one question comes to have two answers — the
    package has already paid for that once, with one declared invariant enforced at three
    different strengths under three different status codes.
    """

    var feasible: Bool
    var violation: Float64
    var worst_row: Int
    var worst_bound: Int
    var n_violated: Int
    var activity: List[Float64]
    var slack: List[Float64]
    var binding: List[Bool]
    var row_tol: List[Float64]
    var lower_tol: List[Float64]
    var upper_tol: List[Float64]


fn _primal_scan(
    a: List[Float64], rows: Int, n: Int, senses: List[Int], b: List[Float64],
    lower: List[Float64], upper: List[Float64], bound_flags: List[Int],
    x: List[Float64], feasibility_tol: Float64,
) -> _Primal:
    """Per-row feasibility of `x`, each row judged against ITS OWN scale.

    `slack[i]` is the SIGNED distance from row `i`'s own feasible side — `b_i - a_iᵀx` for a
    `<=` row, `a_iᵀx - b_i` for a `>=` row — so for an inequality it is positive with room to
    spare, 0 exactly on the boundary, and negative by the amount of the violation. `fabs(b -
    ax)` would report a violated row and a satisfied row identically, which is what makes
    complementary slackness uncheckable.

    An EQUALITY row has no slack side: every deviation is a violation, so its entry is
    `-|a_iᵀx - b_i|`, which is 0 when the row holds exactly and negative by the deviation
    otherwise. A deviation inside the row's own tolerance therefore shows as a small negative
    number and not as feasibility slack — `binding[i]`, which compares against that tolerance,
    is the flag to read, and `row_tol[i]` is the tolerance itself.

    This scan is deliberately built from the CALLER's `a`, `b`, `senses`, `lower` and
    `upper`, not from the internal row system the search used: an error in translating the
    caller's model into that system is exactly the error that no internal consistency check
    can see.
    """
    var activity = List[Float64]()
    var slack = List[Float64]()
    var row_tol = List[Float64]()
    var lower_tol = _zeros(n)
    var upper_tol = _zeros(n)
    var binding = _falses(rows)
    var worst: Float64 = 0.0
    var worst_row = -1
    var worst_bound = -1
    var n_violated = 0
    for i in range(rows):
        var acc: Float64 = 0.0
        var scale = fabs(b[i])
        for j in range(n):
            var term = a[i * n + j] * x[j]
            acc += term
            scale += fabs(term)
        activity.append(acc)
        var tol = feasibility_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * scale
        row_tol.append(tol)
        var s: Float64 = 0.0
        if senses[i] == SENSE_LE:
            s = b[i] - acc
        elif senses[i] == SENSE_GE:
            s = acc - b[i]
        else:
            s = -fabs(acc - b[i])
        slack.append(s)
        if s < -tol:
            n_violated += 1
            if -s > worst:
                worst = -s
                worst_row = i
        binding[i] = fabs(s) <= tol
    for j in range(n):
        var f = bound_flags[j]
        # PER BOUND. An unflagged bound may hold ±inf as padding, and one `fabs(inf)` in a
        # scale shared between the two turns the threshold into `inf`, every `>` into False,
        # and the test on the bound that IS declared into a no-op.
        if has_lower_bound(f):
            lower_tol[j] = feasibility_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * (
                fabs(lower[j]) + fabs(x[j])
            )
            var d = lower[j] - x[j]
            if d > lower_tol[j]:
                n_violated += 1
                if d > worst:
                    worst = d
                    worst_bound = j
                    worst_row = -1
        if has_upper_bound(f):
            upper_tol[j] = feasibility_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * (
                fabs(upper[j]) + fabs(x[j])
            )
            var d2 = x[j] - upper[j]
            if d2 > upper_tol[j]:
                n_violated += 1
                if d2 > worst:
                    worst = d2
                    worst_bound = j
                    worst_row = -1
    return _Primal(
        n_violated == 0, worst, worst_row, worst_bound, n_violated,
        activity^, slack^, binding^, row_tol^, lower_tol^, upper_tol^,
    )


# ── the four-condition KKT audit ──────────────────────────────────────────────


fn _certificate(
    q: List[Float64], n: Int, c: List[Float64], a: List[Float64], rows: Int,
    senses: List[Int], b: List[Float64], lower: List[Float64], upper: List[Float64],
    bound_flags: List[Int], x: List[Float64], duals: List[Float64],
    lower_duals: List[Float64], upper_duals: List[Float64],
    feasibility_tol: Float64, optimality_tol: Float64, convex: Bool, symmetric: Bool,
) -> QPCertificate:
    """All four KKT conditions, each with its own residual. See `QPCertificate`.

    Finiteness of `x` and of every multiplier is established BEFORE any threshold is
    computed from them: a `nan` multiplier turns every `>` comparison False and an audit
    that computes its tolerance from unvalidated inputs passes by counting zero violations.
    """
    if not (_all_finite(x) and _all_finite(duals)):
        return QPCertificate(
            MODEL_ERR_NON_FINITE_POINT, False, convex, symmetric, False, False, False,
            False, QP_ABSENT, QP_ABSENT, QP_ABSENT, QP_ABSENT, QP_ABSENT, -1, -1, -1, 0,
            False, 0.0, "point or duals not finite; no tolerance can be computed from them",
        )
    if not (_all_finite(lower_duals) and _all_finite(upper_duals)):
        return QPCertificate(
            MODEL_ERR_NON_FINITE_POINT, False, convex, symmetric, False, False, False,
            False, QP_ABSENT, QP_ABSENT, QP_ABSENT, QP_ABSENT, QP_ABSENT, -1, -1, -1, 0,
            False, 0.0, "bound multipliers not finite",
        )

    var pr = _primal_scan(
        a, rows, n, senses, b, lower, upper, bound_flags, x, feasibility_tol
    )

    # 1. Stationarity, per component, against that component's own terms. The per-component
    # scales are KEPT, because conditions 3 and 4 are judged against them: they are the noise
    # floor of the gradient a multiplier acts on, and they are the only honest scale for it.
    var qx = _matvec(q, n, x)
    var comp_scale = _zeros(n)
    var stat: Float64 = 0.0
    var worst_excess: Float64 = 0.0
    var worst_component = -1
    var stationarity_ok = True
    for j in range(n):
        var resid = qx[j] + c[j] - lower_duals[j] - upper_duals[j]
        var scale = fabs(c[j]) + fabs(lower_duals[j]) + fabs(upper_duals[j])
        for k in range(n):
            scale += fabs(q[j * n + k] * x[k])
        for i in range(rows):
            var term = a[i * n + j] * duals[i]
            resid -= term
            scale += fabs(term)
        comp_scale[j] = scale
        var tol = optimality_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * scale
        var mag = fabs(resid)
        # The reported residual is the largest one, violating or not; the reported COMPONENT
        # is the one that exceeded its own tolerance by the most. Folding both into one
        # comparison made the two disagree whenever a satisfied component's residual was
        # larger than a violated one's — which is routine when the components' scales differ.
        if mag > stat:
            stat = mag
        if mag > tol:
            stationarity_ok = False
            if mag - tol > worst_excess:
                worst_excess = mag - tol
                worst_component = j

    # 2. Dual feasibility, judged PER ROW against the components that row actually touches.
    #
    # A single global `dual_tol = tol + eps * max_j scale_j` is the rule-4b defect in dual
    # clothing, and it is reachable: with `Q = diag(2e9, 2)` and `c = (-2e9, -2)` the first
    # component's scale is 4e9, so the shared threshold becomes 9.2e-4 and a wrong-SIGN dual
    # of -1e-5 on a row touching only the second component passes dual feasibility AND the
    # slackness test that shares the threshold. The scale must span the quantity being
    # judged — this row's gradient contribution — and nothing else.
    #
    # `duals[i]` is compared in gradient units, PER COMPONENT: the dual enters component `j`
    # of stationarity as `a_ij · duals[i]`, and that component's own floor is
    # `optimality_tol + eps · comp_scale[j]`. So the dual is indistinguishable from zero only
    # when `|a_ij duals[i]|` is under component `j`'s floor for EVERY `j` the row touches, and
    # `row_priced[i]` is the largest amount by which it is not. Pairing the row's LARGEST
    # coefficient with the LARGEST scale among the components it touches — which is what this
    # did before — pairs two quantities that need not belong to the same component: a row
    # reaching a component of scale 1e12 with a coefficient of 1e-6 there and 1.0 at a
    # component of scale 1 got a threshold of 0.23, so a wrong-sign dual of 0.2 passed
    # condition 3 while contributing 0.2 to a component whose floor is 1e-9. A row of ALL
    # zeros touches no component, so its dual is judged directly against `optimality_tol`;
    # such a row moves no gradient, and complementary slackness is what pins its multiplier.
    var dual_violation: Float64 = 0.0
    var worst_row_dual = -1
    var dual_ok = True
    var row_priced = _zeros(rows)
    var row_visible = _falses(rows)
    for i in range(rows):
        # `priced` is the MAGNITUDE the dual contributes to stationarity, at the component
        # where it contributes most; `visible` says that magnitude beat some component's OWN
        # floor. The magnitude is what is reported, because a caller fixing the model needs the
        # number it gave, not the number minus a threshold.
        var priced: Float64 = 0.0
        var visible = False
        var touches = False
        for j in range(n):
            var aij = a[i * n + j]
            if aij == 0.0:
                continue
            touches = True
            var tol_j = optimality_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * comp_scale[j]
            var mag = fabs(aij * duals[i])
            if mag > priced:
                priced = mag
            if mag > tol_j:
                visible = True
        if not touches:
            priced = fabs(duals[i])
            visible = priced > optimality_tol
        row_priced[i] = priced
        row_visible[i] = visible
        var bad: Float64 = 0.0
        if visible:
            # Visible in stationarity, so its SIGN is a condition and not a rounding artefact.
            if senses[i] == SENSE_LE and duals[i] > 0.0:
                bad = priced
            elif senses[i] == SENSE_GE and duals[i] < 0.0:
                bad = priced
        if bad > 0.0:
            dual_ok = False
            if bad > dual_violation:
                dual_violation = bad
                worst_row_dual = i
    # A bound multiplier appears in exactly ONE component of stationarity, so that
    # component's own scale is its threshold — no maximum over anything.
    var worst_bound_dual = -1
    for j in range(n):
        var f = bound_flags[j]
        var tol_j = optimality_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * comp_scale[j]
        var lo = lower_duals[j]
        var up = upper_duals[j]
        var bad2: Float64 = 0.0
        if has_lower_bound(f):
            if lo < -tol_j:
                bad2 = -lo
        elif fabs(lo) > tol_j:
            # A multiplier on a bound the caller never declared. Not a dual — a free pass on
            # stationarity, and the reason condition 3 is checked for absent bounds too.
            bad2 = fabs(lo)
        if has_upper_bound(f):
            if up > tol_j and up > bad2:
                bad2 = up
        elif fabs(up) > tol_j and fabs(up) > bad2:
            bad2 = fabs(up)
        if bad2 > 0.0:
            dual_ok = False
            if bad2 > dual_violation:
                dual_violation = bad2
                worst_bound_dual = j
                worst_row_dual = -1

    # 4. Complementary slackness, both directions, reported separately, and reusing the SAME
    # per-row thresholds as condition 3 — a second spelling of the same threshold is how the
    # two would come to disagree about whether a dual is nonzero.
    var slack_dual: Float64 = 0.0
    var dual_slack: Float64 = 0.0
    var slackness_ok = True
    for i in range(rows):
        if senses[i] == SENSE_EQ:
            continue
        # `pr.row_tol[i]` is the tolerance the FEASIBILITY test used for this row. Reused
        # rather than recomputed, so "row i is tight" cannot mean one thing in condition 2 and
        # another in condition 4. `row_visible[i]` / `row_priced[i]` come from condition 3 for
        # the same reason: "this dual is nonzero" is one question with one answer.
        var priced_mag = row_priced[i]
        var loose = pr.slack[i] > pr.row_tol[i]
        var priced = row_visible[i]
        if loose and priced:
            slackness_ok = False
            if priced_mag > slack_dual:
                slack_dual = priced_mag
            if pr.slack[i] > dual_slack:
                dual_slack = pr.slack[i]
    for j in range(n):
        var f = bound_flags[j]
        var tol_j = optimality_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * comp_scale[j]
        # `pr.lower_tol[j]` / `pr.upper_tol[j]` again: the same per-bound thresholds the
        # feasibility scan used, which are per bound and never a scale shared between the two,
        # because an unflagged bound may legitimately hold ±inf as padding and one `fabs(inf)`
        # would make the threshold `inf` and the whole test vacuous.
        if has_lower_bound(f):
            var gap = x[j] - lower[j]
            if gap > pr.lower_tol[j] and fabs(lower_duals[j]) > tol_j:
                slackness_ok = False
                if fabs(lower_duals[j]) > slack_dual:
                    slack_dual = fabs(lower_duals[j])
                if gap > dual_slack:
                    dual_slack = gap
        if has_upper_bound(f):
            var gap2 = upper[j] - x[j]
            if gap2 > pr.upper_tol[j] and fabs(upper_duals[j]) > tol_j:
                slackness_ok = False
                if fabs(upper_duals[j]) > slack_dual:
                    slack_dual = fabs(upper_duals[j])
                if gap2 > dual_slack:
                    dual_slack = gap2

    var obj = _objective_value(q, n, c, x)
    var has_obj = _finite(obj)
    var certified = (
        stationarity_ok and pr.feasible and dual_ok and slackness_ok and convex
        and symmetric and has_obj
    )
    var status = QP_OPTIMAL if certified else QP_NOT_CERTIFIED
    var msg = String("")
    if not certified:
        msg = "not certified:"
        if not convex:
            msg += " Q not convex;"
        if not symmetric:
            msg += " Q not symmetric;"
        if not stationarity_ok:
            msg += " stationarity at component " + String(worst_component) + ";"
        if not pr.feasible:
            msg += " primal row " + String(pr.worst_row) + " bound " + String(
                pr.worst_bound
            ) + ";"
        if not dual_ok:
            msg += " dual sign;"
        if not slackness_ok:
            msg += " complementary slackness;"
        if not has_obj:
            msg += " objective not finite;"
    var n_bad = pr.n_violated
    if not stationarity_ok:
        n_bad += 1
    if not dual_ok:
        n_bad += 1
    if not slackness_ok:
        n_bad += 1
    return QPCertificate(
        status, certified, convex, symmetric, stationarity_ok, pr.feasible, dual_ok,
        slackness_ok, stat, pr.violation, dual_violation, slack_dual, dual_slack,
        worst_component, pr.worst_row if pr.worst_row >= 0 else worst_row_dual,
        pr.worst_bound if pr.worst_bound >= 0 else worst_bound_dual, n_bad,
        has_obj, obj if has_obj else 0.0, msg^,
    )


# ── the linearisation bound ───────────────────────────────────────────────────


fn _bound_at(
    q: List[Float64], n: Int, c: List[Float64], rw: _Rows, x: List[Float64],
    max_iterations: Int, feasibility_tol: Float64, optimality_tol: Float64,
) -> QPBound:
    """`f(x)`, a lower bound on `f*` from one LP over the same feasible set, and the gap.

    `f(z) >= f(x) + gᵀ(z - x)` for convex `f`, so `min_z gᵀz` over the feasible set (an LP)
    gives `f* >= f(x) + L - gᵀx`. When there are NO rows and no bounds the feasible set is
    all of R^n and the same statement is closed-form: the linearisation has a minimum only
    when `g == 0`, in which case `x` is already stationary. That case is handled here rather
    than by calling `lp_solve` with zero rows — one less untested corner in the dependency.
    """
    var g = _matvec(q, n, x)
    for j in range(n):
        g[j] += c[j]
    var fx = _objective_value(q, n, c, x)
    if not _finite(fx):
        return QPBound(
            MODEL_ERR_NON_FINITE_POINT, False, False, 0.0, False, 0.0, False, 0.0, False,
            MODEL_ERR_NON_FINITE_POINT, "objective is not finite at this point",
        )
    var gx = vec_dot(g, x)
    if n == 0:
        # A zero-variable objective is a CONSTANT on the feasible set, so `f(x)` is both the
        # bound and the value and the gap is zero by definition. Handled here rather than by
        # calling `lp_solve` with zero columns, which is a corner of the simplex nothing else
        # in the package exercises.
        return QPBound(
            MODEL_OK, True, True, fx, True, fx, True, 0.0, True, LP_OPTIMAL,
            "no variables: the objective is constant on the feasible set",
        )
    if rw.m == 0:
        # No rows and no bounds: the feasible set is all of R^n, so the linearisation has a
        # minimum exactly when the gradient vanishes — and then `x` IS the minimiser of the
        # convex `f`, with gap 0. The vanishing test is per component against that
        # component's own terms, the SAME rule the stationarity audit uses, so the two cannot
        # disagree about whether an unconstrained point is stationary. `== 0.0` was not that
        # rule: `Q = 2I`, `c = (-4, -6)` converges to a gradient of 4.4e-16, which is zero to
        # every tolerance in this module and is not zero to `==`.
        var stationary = True
        for j in range(n):
            var scale = fabs(c[j])
            for t in range(n):
                scale += fabs(q[j * n + t] * x[t])
            if fabs(g[j]) > optimality_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * scale:
                stationary = False
        if stationary:
            return QPBound(
                MODEL_OK, True, True, fx, True, fx, True, 0.0, True, LP_OPTIMAL,
                "unconstrained and stationary: the point is the minimum",
            )
        return QPBound(
            MODEL_OK, True, True, fx, False, 0.0, False, 0.0, False, LP_UNBOUNDED,
            "unconstrained and not stationary: the linearisation has no minimum",
        )
    var lp = _split_lp(rw, g, n, max_iterations, feasibility_tol, optimality_tol)
    if lp.status != LP_OPTIMAL or not lp.has_objective:
        return QPBound(
            MODEL_OK, True, True, fx, False, 0.0, False, 0.0, False, lp.status,
            "no linearisation bound: the bounding LP returned " + lp_status_name(lp.status),
        )
    var bound = fx + lp.objective - gx
    var gap = gx - lp.objective
    # THE QUANTITY JUDGED IS THE GAP, so the threshold is built from the gap and nothing else:
    # the caller's tolerance as an ABSOLUTE allowance, plus what the three-term subtraction
    # `gx - lp.objective` (and the `f(x)` it is compared against) can have rounded away.
    #
    # It used to be `optimality_tol * (1 + |fx|)`, which sizes a RELATIVE term by the CALLER's
    # tolerance instead of by DBL_EPSILON — so on `min 0.5x² s.t. x >= 1e9` (f* = 5e17) the
    # threshold was 5e8 and a MEASURED gap of 400,000,000 came back `at_optimum = True`.
    # `at_optimum` then tracked the tolerance rather than the gap, and the same threshold
    # gates the negative-gap contradiction check below, so `best_bound` could sit above `f*`
    # and still be presented as a lower bound.
    var gap_tol = optimality_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * (
        fabs(fx) + fabs(gx) + fabs(lp.objective)
    )
    if not (_finite(bound) and _finite(gap)):
        return QPBound(
            MODEL_OK, True, True, fx, False, 0.0, False, 0.0, False, QP_NUMERICAL_BREAKDOWN,
            "linearisation bound overflowed",
        )
    if gap < -gap_tol:
        # A negative gap means `f(x)` and the LP disagree about the same feasible set. That
        # is a contradiction, not a tighter bound, so no bound is reported.
        return QPBound(
            MODEL_OK, True, True, fx, False, 0.0, False, 0.0, False, QP_NUMERICAL_BREAKDOWN,
            "linearisation bound exceeds the objective by " + String(-gap),
        )
    var clamped = gap
    if clamped < 0.0:
        clamped = 0.0
    # ONE threshold for both directions of the same judgement: `gap_tol` is the caller's
    # ABSOLUTE optimality tolerance plus what the three-term subtraction can have rounded
    # away, and it is what the negative-gap contradiction check above used. A second, more
    # generous spelling here would have made "the gap is zero" easier to reach than "the gap
    # is impossible", and the two are the same measurement.
    var at_opt = clamped <= gap_tol
    return QPBound(
        MODEL_OK, True, True, fx, True, bound, True, clamped, at_opt, LP_OPTIMAL, String("")
    )


# ── public drivers ────────────────────────────────────────────────────────────


fn qp_convexity_flat(q: List[Float64], n: Int) -> QPConvexity:
    """Is `0.5 xᵀQx` convex, how badly is `Q` asymmetric, and where does convexity fail.

    Separate from `qp_solve` because it is the question a caller asks BEFORE they have a
    model: a matrix that fails here fails every solve, and the reason is a pivot index and a
    value rather than a status code. `positive_definite` comes from the frozen
    `linalg_ext.mat_is_positive_definite`, which is the tree's authority on STRICT
    definiteness; `convex` is semidefiniteness, which is the weaker property convexity
    actually needs and the one the frozen kernel cannot report.
    """
    if n < 0 or not dims_fit(n, n, len(q)):
        return QPConvexity(
            MODEL_ERR_DENSE_SHAPE, n, False, False, False, QP_ABSENT, -1, 0.0, -1, 0.0,
            List[Float64](), "Q is not n x n: len(q) must be exactly n*n",
        )
    if n > 0 and n > QP_MAX_MATRIX_CELLS // n:
        return QPConvexity(
            MODEL_ERR_DIMENSION_TOO_LARGE, n, False, False, False, QP_ABSENT, -1, 0.0, -1,
            0.0, List[Float64](), "n is past this module's area budget",
        )
    if not _all_finite(q):
        return QPConvexity(
            MODEL_ERR_NON_FINITE_COEFFICIENT, n, False, False, False, QP_ABSENT, -1, 0.0,
            -1, 0.0, List[Float64](), "Q has a non-finite entry",
        )
    var cv = _convexity(q, n)
    var frozen_pd = False
    if cv.symmetric and n > 0:
        frozen_pd = mat_is_positive_definite(mat_from_list(cv.q_sym, n, n))
    elif cv.symmetric and n == 0:
        # A zero-variable objective is trivially convex and vacuously definite; say so
        # rather than let a frozen kernel's empty-matrix behaviour decide.
        frozen_pd = True
    # SELF-CONSISTENCY, enforced rather than hoped for. A positive definite matrix has FULL
    # RANK and is convex — those are not two opinions — so the reported flag is the
    # conjunction of the frozen kernel's verdict with this module's own rank, and a struct
    # carrying `rank < n` beside `positive_definite = True` cannot be constructed. That
    # combination was reachable: `diag(1e12, 0.5)` factored to `rank 1` under a tolerance
    # scaled by the largest diagonal while the frozen unpivoted Cholesky said definite, so
    # one returned value asserted both "flat in one direction" and "flat in none" and a
    # caller could use neither.
    var pd = frozen_pd and cv.convex and cv.rank == n
    var msg = cv.message
    if frozen_pd != (cv.convex and cv.rank == n) and cv.status == MODEL_OK:
        # The two computations differ in their rounding model — the frozen kernel is an
        # unpivoted Cholesky with an absolute 1e-15 floor, this one is equilibrated and
        # relative — so a disagreement is a fact about the matrix, reported rather than
        # averaged. The FLAG stays conservative; the message says who said what.
        msg = (
            "definiteness is not agreed: the frozen Cholesky says "
            + String(frozen_pd) + " while the pivoted factorisation reports rank "
            + String(cv.rank) + " of " + String(n)
            + "; positive_definite is reported False, and `convex` (semidefiniteness) is the"
            " property a QP actually needs"
        )
    return QPConvexity(
        cv.status, n, cv.symmetric, cv.convex, pd, cv.asymmetry, cv.rank, cv.min_pivot,
        cv.fail_index, cv.fail_value, cv.q_sym.copy(), msg^,
    )


fn qp_objective_flat(
    q: List[Float64], n: Int, c: List[Float64], x: List[Float64]
) -> QPValue:
    """`0.5 xᵀQx + cᵀx`, or a status and NO value.

    An overflow to infinity is reported as absent rather than returned as a number, which is
    the whole `numeric/contract.mojo` policy: `0.0` and `inf` are both answers a caller would
    branch on, and neither is the answer here.
    """
    if n < 0 or not dims_fit(n, n, len(q)):
        return QPValue(MODEL_ERR_DENSE_SHAPE, False, 0.0)
    if len(c) != n:
        return QPValue(MODEL_ERR_LENGTH_MISMATCH, False, 0.0)
    if len(x) != n:
        return QPValue(MODEL_ERR_POINT_LENGTH, False, 0.0)
    if not (_all_finite(q) and _all_finite(c)):
        return QPValue(MODEL_ERR_NON_FINITE_COEFFICIENT, False, 0.0)
    if not _all_finite(x):
        return QPValue(MODEL_ERR_NON_FINITE_POINT, False, 0.0)
    var v = _objective_value(q, n, c, x)
    if not _finite(v):
        return QPValue(MODEL_ERR_NON_FINITE_VALUE, False, 0.0)
    return QPValue(MODEL_OK, True, v)


fn qp_gradient_flat(
    q: List[Float64], n: Int, c: List[Float64], x: List[Float64]
) -> QPVector:
    """`Q x + c`, or a status and an EMPTY vector.

    Exported because a caller auditing someone else's solution needs the same gradient this
    module's stationarity test uses, computed the same way — not a re-derivation that can
    disagree about the factor of `0.5`. (It is `Qx + c`, not `0.5 Qx + c`: the derivative of
    `0.5 xᵀQx` is `Qx` for symmetric `Q`, and getting that wrong is the single most common
    QP sign error.)
    """
    if n < 0 or not dims_fit(n, n, len(q)):
        return QPVector(MODEL_ERR_DENSE_SHAPE, False, 0, List[Float64]())
    if len(c) != n:
        return QPVector(MODEL_ERR_LENGTH_MISMATCH, False, 0, List[Float64]())
    if len(x) != n:
        return QPVector(MODEL_ERR_POINT_LENGTH, False, 0, List[Float64]())
    if not (_all_finite(q) and _all_finite(c) and _all_finite(x)):
        return QPVector(MODEL_ERR_NON_FINITE_COEFFICIENT, False, 0, List[Float64]())
    var g = _matvec(q, n, x)
    for j in range(n):
        g[j] += c[j]
    if not _all_finite(g):
        return QPVector(MODEL_ERR_NON_FINITE_VALUE, False, 0, List[Float64]())
    return QPVector(MODEL_OK, True, n, g^)


# PACKING IS LOAD-BEARING: `mojo_inventory` matches a signature inside a NINE-line lookahead
# and drops the function from the contract and from dispatch silently on failure. Six lines
# with three lines of headroom; do not let a formatter give each parameter its own line.
fn qp_kkt_check(
    q: List[Float64], n: Int, c: List[Float64], a: List[Float64], rows: Int,
    senses: List[Int], b: List[Float64], lower: List[Float64], upper: List[Float64],
    bound_flags: List[Int], x: List[Float64], duals: List[Float64],
    lower_duals: List[Float64], upper_duals: List[Float64],
    feasibility_tol: Float64, optimality_tol: Float64,
) -> QPCertificate:
    """Audit a point and its duals against all four KKT conditions. See `QPCertificate`.

    The point does not have to have come from `qp_solve`. That is the purpose: a certificate
    a caller can run on a vendor's answer, or on last week's answer after the data moved, is
    worth more than a status this module produced about its own work.
    """
    var defect = _qp_shape_defect(
        q, n, c, a, rows, senses, b, lower, upper, bound_flags
    )
    if defect != MODEL_OK:
        return QPCertificate(
            defect, False, False, False, False, False, False, False, QP_ABSENT, QP_ABSENT,
            QP_ABSENT, QP_ABSENT, QP_ABSENT, -1, -1, -1, 0, False, 0.0,
            "input rejected: " + model_status_name(defect),
        )
    if len(x) != n:
        return QPCertificate(
            MODEL_ERR_POINT_LENGTH, False, False, False, False, False, False, False,
            QP_ABSENT, QP_ABSENT, QP_ABSENT, QP_ABSENT, QP_ABSENT, -1, -1, -1, 0, False,
            0.0, "x must have exactly n entries",
        )
    if len(duals) != rows or len(lower_duals) != n or len(upper_duals) != n:
        return QPCertificate(
            MODEL_ERR_LENGTH_MISMATCH, False, False, False, False, False, False, False,
            QP_ABSENT, QP_ABSENT, QP_ABSENT, QP_ABSENT, QP_ABSENT, -1, -1, -1, 0, False,
            0.0, "one dual per row, one per variable for each bound vector",
        )
    if feasibility_tol < 0.0 or not _finite(feasibility_tol):
        return QPCertificate(
            MODEL_ERR_POLICY, False, False, False, False, False, False, False,
            QP_ABSENT, QP_ABSENT, QP_ABSENT, QP_ABSENT, QP_ABSENT, -1, -1, -1, 0, False,
            0.0, "feasibility_tol must be finite and non-negative",
        )
    if optimality_tol <= 0.0 or not _finite(optimality_tol):
        return QPCertificate(
            MODEL_ERR_POLICY, False, False, False, False, False, False, False,
            QP_ABSENT, QP_ABSENT, QP_ABSENT, QP_ABSENT, QP_ABSENT, -1, -1, -1, 0, False,
            0.0, "optimality_tol must be finite and strictly positive",
        )
    var cv = _convexity(q, n)
    return _certificate(
        q, n, c, a, rows, senses, b, lower, upper, bound_flags, x, duals, lower_duals,
        upper_duals, feasibility_tol, optimality_tol, cv.convex, cv.symmetric,
    )


fn qp_gap_flat(
    q: List[Float64], n: Int, c: List[Float64], a: List[Float64], rows: Int,
    senses: List[Int], b: List[Float64], lower: List[Float64], upper: List[Float64],
    bound_flags: List[Int], x: List[Float64], max_iterations: Int,
    feasibility_tol: Float64, optimality_tol: Float64,
) -> QPBound:
    """A MEASURED upper bound on `f(x) - f*` for a feasible `x`. See `QPBound`.

    Independent of the KKT audit and of this module's own search: it is one `lp_solve` over
    the caller's feasible set. A caller with a point from anywhere can ask "how far from
    optimal can this be?" and get a number that is a theorem rather than an estimate.
    """
    var defect = _qp_shape_defect(
        q, n, c, a, rows, senses, b, lower, upper, bound_flags
    )
    if defect != MODEL_OK:
        return QPBound(
            defect, False, False, 0.0, False, 0.0, False, 0.0, False, defect,
            "input rejected: " + model_status_name(defect),
        )
    if len(x) != n:
        return QPBound(
            MODEL_ERR_POINT_LENGTH, False, False, 0.0, False, 0.0, False, 0.0, False,
            MODEL_ERR_POINT_LENGTH, "x must have exactly n entries",
        )
    if not _all_finite(x):
        return QPBound(
            MODEL_ERR_NON_FINITE_POINT, False, False, 0.0, False, 0.0, False, 0.0, False,
            MODEL_ERR_NON_FINITE_POINT, "x is not finite",
        )
    var policy = _policy_parts_defect(
        max_iterations, feasibility_tol, optimality_tol, DEFAULT_INTEGRALITY_TOL
    )
    if policy != MODEL_OK:
        return QPBound(
            policy, False, False, 0.0, False, 0.0, False, 0.0, False, policy,
            "policy rejected: " + model_status_name(policy),
        )
    var cv = _convexity(q, n)
    if cv.status != MODEL_OK:
        # The inequality the bound rests on is convexity itself. Without it the LP value is
        # not a bound on anything.
        return QPBound(
            cv.status, False, False, 0.0, False, 0.0, False, 0.0, False, cv.status,
            cv.message,
        )
    var pr = _primal_scan(
        a, rows, n, senses, b, lower, upper, bound_flags, x, feasibility_tol
    )
    if not pr.feasible:
        return QPBound(
            MODEL_OK, False, False, 0.0, False, 0.0, False, 0.0, False, QP_INFEASIBLE,
            "x is not feasible, so f(x) bounds nothing: worst violation "
            + String(pr.violation),
        )
    var rw = _build_rows(a, rows, n, senses, b, lower, upper, bound_flags)
    return _bound_at(
        cv.q_sym, n, c, rw, x, max_iterations, feasibility_tol, optimality_tol
    )


fn _qp_rejected(status: Int, message: String) -> QPSolution:
    """No answer, and no numbers to mistake for one. Every list stays empty."""
    var out = QPSolution()
    out.status = status
    out.message = message
    return out^


fn _stamp(mut out: QPSolution, n: Int, rows: Int, cv: _Convex):
    """Copy the problem's shape and the convexity findings onto any outcome.

    ONE place, because the five no-answer paths below were each hand-copying the same seven
    fields and a hand-copy that drifts leaves a status reporting `asymmetry = -1` ("never
    measured") for a matrix whose asymmetry this call measured.
    """
    out.n_vars = n
    out.n_constraints = rows
    out.symmetric = cv.symmetric
    out.convex = cv.convex
    out.asymmetry = cv.asymmetry
    out.min_pivot = cv.min_pivot
    out.q_rank = cv.rank
    out.q_fail_index = cv.fail_index


# PACKING IS LOAD-BEARING: five lines, four of headroom inside `mojo_inventory`'s nine-line
# lookahead. A signature that closes on the tenth line is dropped from the runtime contract
# and from dispatch silently, and the only symptom is a lower per-module function count.
fn qp_solve(
    q: List[Float64], n: Int, c: List[Float64],
    a: List[Float64], rows: Int, senses: List[Int], b: List[Float64],
    lower: List[Float64], upper: List[Float64], bound_flags: List[Int],
    max_iterations: Int, feasibility_tol: Float64, optimality_tol: Float64, seed: UInt64,
) -> QPSolution:
    """Minimise `0.5 xᵀQx + cᵀx` over `A x {senses} b` and the declared bounds.

    A primal active-set method: at each iterate the rows it treats as active are held as
    equalities, the exact minimiser of the quadratic over that face is computed in the
    null space of the active rows, and a row is added when the step is blocked or dropped
    when its multiplier says the face is the wrong one. Two facts make this the honest
    algorithm for the job rather than a fast one:

      * the step is EXACT, not a line search. For a quadratic, the null-space Newton step IS
        the face's minimiser, so "the step is zero" means "this face is solved" and the
        multipliers read at that point are the real ones. A gradient method's small step
        means nothing of the kind, which is why its multipliers cannot be certified.
      * a singular reduced Hessian is a SEPARATE outcome, not a regularised one. If the
        objective is flat along a feasible direction in which it also decreases, and nothing
        blocks that direction, then the program has no minimum — `QP_UNBOUNDED` with the ray
        attached — and adding `δI` to make the factorisation succeed would have returned a
        finite point for a problem with no finite answer.

    `bound_flags[j]` uses `model.VAR_FLAG_HAS_LOWER` / `VAR_FLAG_HAS_UPPER`; an unflagged
    bound value is never read, so ±inf is fine as padding. `VAR_FLAG_HAS_START` is REJECTED
    rather than ignored: there is no warm start on this entry point and a caller who believed
    otherwise would be silently ignored.

    `seed` is mandatory and every tie-break comes from it; see the module header for the
    exact rules and for why the ANSWER must not depend on it while the PATH may.

    The search is run on `(Q + Qᵀ)/2`, which denotes the identical objective, and the KKT
    audit is run on the same matrix; `asymmetry` reports how far the caller's `Q` was from
    symmetric, and the gate has already refused anything past rounding. `qp_kkt_check`
    audits exactly the matrix it is handed, because there the matrix is the caller's claim.

    `max_iterations` is a budget PER SOLVE STAGE, not for the call: the phase-1 LP, the
    active-set search and the bounding LP each get it. A cap too small for phase 1 is
    `QP_FEASIBILITY_SEARCH_FAILED` (infeasibility is NOT established by running out of
    pivots), and a cap too small for the bounding LP costs the bound and nothing else.

    A success status needs the four-condition KKT audit to pass and the independent
    linearisation bound not to contradict it. A DISAGREEMENT between the two is
    `QP_NOT_CERTIFIED` with every residual reported — one of them is wrong and this driver
    cannot say which, so it claims neither.
    """
    var defect = _qp_shape_defect(q, n, c, a, rows, senses, b, lower, upper, bound_flags)
    if defect != MODEL_OK:
        return _qp_rejected(defect, "input rejected: " + model_status_name(defect))
    var policy = _policy_parts_defect(
        max_iterations, feasibility_tol, optimality_tol, DEFAULT_INTEGRALITY_TOL
    )
    if policy != MODEL_OK:
        return _qp_rejected(policy, "policy rejected: " + model_status_name(policy))

    var cv = _convexity(q, n)
    if cv.status != MODEL_OK:
        var bad = _qp_rejected(cv.status, cv.message)
        _stamp(bad, n, rows, cv)
        return bad^
    var qs = cv.q_sym.copy()

    var out = QPSolution()
    _stamp(out, n, rows, cv)

    if n == 0:
        # A zero-variable program is a real program: its rows are `0 {sense} b_i`, which is
        # a feasibility question with a constant objective. Answering it here keeps `n == 0`
        # out of the LP split and out of every loop below.
        var empty_x = List[Float64]()
        var pr0 = _primal_scan(
            a, rows, n, senses, b, lower, upper, bound_flags, empty_x, feasibility_tol
        )
        if not pr0.feasible:
            var inf0 = _qp_rejected(QP_INFEASIBLE, "no variables, and a row rejects 0")
            _stamp(inf0, 0, rows, cv)
            inf0.primal_violation = pr0.violation
            return inf0^
        # The duals are all zero — with no variables there is no stationarity equation to
        # satisfy and a zero multiplier is feasible and slack-compatible for every row — but
        # that is CHECKED rather than asserted, through the same certificate and the same
        # bound routine every other status goes through. A hand-set `certified = True` is a
        # claim; this is a verdict.
        var zero_duals = _zeros(rows)
        var cert0 = _certificate(
            qs, 0, c, a, rows, senses, b, lower, upper, bound_flags, empty_x, zero_duals,
            List[Float64](), List[Float64](), feasibility_tol, optimality_tol, True, True,
        )
        var rw0 = _build_rows(a, rows, 0, senses, b, lower, upper, bound_flags)
        var bnd0 = _bound_at(
            qs, 0, c, rw0, empty_x, max_iterations, feasibility_tol, optimality_tol
        )
        out.feasible = True
        out.certified = cert0.certified
        out.has_objective = cert0.has_objective
        out.objective = cert0.objective
        out.has_bound = bnd0.has_bound
        out.best_bound = bnd0.best_bound
        out.has_gap = bnd0.has_gap
        out.gap = bnd0.gap
        out.bound_status = bnd0.lp_status
        out.proven_optimal = cert0.certified and not (bnd0.has_bound and not bnd0.at_optimum)
        out.status = QP_OPTIMAL if out.proven_optimal else QP_NOT_CERTIFIED
        out.stationarity_ok = cert0.stationarity_ok
        out.primal_ok = cert0.primal_ok
        out.dual_ok = cert0.dual_ok
        out.slackness_ok = cert0.slackness_ok
        out.stationarity_violation = cert0.stationarity_violation
        out.primal_violation = cert0.primal_violation
        out.dual_violation = cert0.dual_violation
        out.slackness_violation = cert0.slack_dual_violation
        out.duals = zero_duals^
        out.activity = pr0.activity.copy()
        out.slack = pr0.slack.copy()
        out.binding = pr0.binding.copy()
        out.row_active = _falses(rows)
        out.message = "no variables: the rows are satisfied by the empty point"
        return out^

    var rw = _build_rows(a, rows, n, senses, b, lower, upper, bound_flags)
    var stream = stream_id(QP_STREAM_NAME)
    var order = permutation_keyed(rw.m, seed, stream, 0)
    var scan_rank = List[Int]()
    for _ in range(rw.m):
        scan_rank.append(0)
    for pos in range(len(order)):
        scan_rank[order[pos]] = pos
    var sig = seed
    for pos in range(len(order)):
        sig = _fold(sig, UInt64(order[pos]), stream)

    # ── phase 1: a feasible point, or a proof there is none ───────────────────
    var x = _zeros(n)
    var phase1_status = LP_OPTIMAL
    if rw.m > 0:
        var lp0 = _split_lp(
            rw, _zeros(n), n, max_iterations, feasibility_tol, optimality_tol
        )
        phase1_status = lp0.status
        out.phase1_status = lp0.status
        if lp0.status == LP_INFEASIBLE:
            var inf1 = _qp_rejected(
                QP_INFEASIBLE,
                "no point satisfies the rows and bounds; phase-1 infeasibility "
                + String(lp0.infeasibility),
            )
            _stamp(inf1, n, rows, cv)
            inf1.phase1_status = lp0.status
            inf1.primal_violation = lp0.infeasibility
            inf1.path_signature = Int(sig >> 1)
            return inf1^
        if lp0.status != LP_OPTIMAL or len(lp0.x) != 2 * n:
            var fail1 = _qp_rejected(
                QP_FEASIBILITY_SEARCH_FAILED,
                "phase 1 neither found a point nor proved there is none: "
                + lp_status_name(lp0.status),
            )
            _stamp(fail1, n, rows, cv)
            fail1.phase1_status = lp0.status
            fail1.path_signature = Int(sig >> 1)
            return fail1^
        x = _unsplit(lp0, n)
        if not _all_finite(x):
            var brk1 = _qp_rejected(
                QP_NUMERICAL_BREAKDOWN, "phase 1 returned a non-finite point"
            )
            _stamp(brk1, n, rows, cv)
            brk1.phase1_status = lp0.status
            brk1.path_signature = Int(sig >> 1)
            return brk1^

    # ── the initial active set, in keyed scan order ───────────────────────────
    var w_set = List[Int]()
    var in_w = _falses(rw.m)
    for pos in range(len(order)):
        var i = order[pos]
        if rw.is_eq[i]:
            w_set.append(i)
            in_w[i] = True
            continue
        var act = _row_activity(rw, i, x)
        var tol = feasibility_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * _row_terms_scale(
            rw, i, x
        )
        if fabs(rw.h[i] - act) <= tol:
            w_set.append(i)
            in_w[i] = True

    var q_full_rank = cv.rank == n
    var iterations = 0
    var n_added = 0
    var n_dropped = 0
    var n_zero_curvature = 0
    var consecutive_drops = 0
    var terminal = 0  # 0 = a candidate optimum; otherwise a status code
    var breakdown = String("")
    var ray = List[Float64]()

    while True:
        if iterations >= max_iterations:
            terminal = QP_ITERATION_LIMIT
            break
        iterations += 1

        var g = _matvec(qs, n, x)
        for j in range(n):
            g[j] += c[j]
        if not _all_finite(g):
            terminal = QP_NUMERICAL_BREAKDOWN
            breakdown = "the gradient overflowed at iteration " + String(iterations)
            break

        var ns = _null_space(rw, w_set, n)
        if not ns.ok:
            terminal = QP_NUMERICAL_BREAKDOWN
            breakdown = "the active-row orthogonalisation did not stay finite"
            break

        var p = _zeros(n)
        var zero_curvature = False
        if ns.nz > 0:
            var gz = _zeros(ns.nz)
            for t in range(ns.nz):
                var acc: Float64 = 0.0
                for j in range(n):
                    acc += ns.z[t * n + j] * g[j]
                gz[t] = acc
            var qz = List[Float64]()
            for t in range(ns.nz):
                var zt = List[Float64]()
                for j in range(n):
                    zt.append(ns.z[t * n + j])
                var qzt = _matvec(qs, n, zt)
                for j in range(n):
                    qz.append(qzt[j])
            var hz = _zeros(ns.nz * ns.nz)
            for t in range(ns.nz):
                for s in range(ns.nz):
                    var acc2: Float64 = 0.0
                    for j in range(n):
                        acc2 += ns.z[t * n + j] * qz[s * n + j]
                    hz[t * ns.nz + s] = acc2
            var ch = _ldl_factor(hz, ns.nz)
            if not ch.psd:
                # `Q` is PSD and `Hz = ZᵀQZ`, so `Hz` is PSD as a matter of algebra. A
                # refutation here is arithmetic, not modelling, and is reported as such
                # rather than as a non-convex objective.
                terminal = QP_NUMERICAL_BREAKDOWN
                breakdown = (
                    "the reduced Hessian factored as indefinite at pivot "
                    + String(ch.fail_index)
                )
                break
            var dir = _zeros(ns.nz)
            var found = False
            for s in range(ns.nz - ch.rank):
                var v = _ldl_null_vector(ch, s)
                # IS THE CURVATURE ALONG `v` ZERO? The quantity judged is that direction's own
                # curvature, so the threshold comes from that direction's own terms and from
                # nothing else:
                #
                #   * `vᵀHz v` against `Σ_ts |v_t Hz_ts v_s|`, the magnitude of the terms the
                #     sum is made of. `Hz` is PSD here (checked above), and for a PSD matrix
                #     `vᵀHv == 0` iff `Hv == 0`, so this scalar is the whole question.
                #   * every component of `Hz v` against THAT row's own terms
                #     `Σ_s |Hz_ts v_s|`, because the ray claim is `Hz v = 0` componentwise.
                #
                # It used to be `_max_abs(Hz v) > budget·eps·(nz+1)·max|Hz|` — a maximum over
                # the WHOLE reduced Hessian. With `Hz = diag(1e12, 0.5)` that threshold is
                # 0.68, so `e_2` was accepted as a flat direction, `QP_UNBOUNDED` was returned
                # with `ray = (0, 1)` and `Q·ray = (0, 0.5) ≠ 0` — a ray failing the very
                # condition the status advertises, for a program whose unique minimum is
                # x = (0, 2). The measurement was right; only the threshold was not.
                var hv = _matvec(hz, ns.nz, v)
                var curv: Float64 = 0.0
                var curv_scale: Float64 = 0.0
                var flat = True
                for t in range(ns.nz):
                    curv += v[t] * hv[t]
                    var row_scale: Float64 = 0.0
                    for u in range(ns.nz):
                        var term = hz[t * ns.nz + u] * v[u]
                        row_scale += fabs(term)
                        curv_scale += fabs(v[t] * term)
                    if fabs(hv[t]) > LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * Float64(
                        ns.nz + 1
                    ) * row_scale:
                        flat = False
                if fabs(curv) > LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * Float64(
                    ns.nz + 1
                ) * curv_scale:
                    flat = False
                if not flat:
                    # A claimed null direction that is not one. Skipped rather than trusted:
                    # a certificate is only worth what its weakest checked condition is.
                    continue
                # DOES IT DESCEND? The quantity is the directional derivative `gzᵀv`, so its
                # own terms `Σ_t |gz_t v_t|` size the rounding part — not `max|gz|`, which is
                # an aggregate over components this direction may not even touch.
                var gv = vec_dot(gz, v)
                var gv_scale: Float64 = 0.0
                for t in range(ns.nz):
                    gv_scale += fabs(gz[t] * v[t])
                var null_tol = optimality_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * gv_scale
                if fabs(gv) > null_tol:
                    var sgn: Float64 = -1.0
                    if gv < 0.0:
                        sgn = 1.0
                    for t in range(ns.nz):
                        dir[t] = sgn * v[t]
                    found = True
                    break
            if found and q_full_rank:
                # SELF-CONSISTENCY, as a check and not as a comment. `Q` has full rank n, so
                # `ZᵀQZ` is positive definite for any full-column-rank `Z` and no flat
                # direction exists in any subspace. Two of this module's own computations
                # therefore contradict each other, and the honest outcome is to say so rather
                # than to act on the one that produces a terminal status.
                terminal = QP_NUMERICAL_BREAKDOWN
                breakdown = (
                    "a zero-curvature direction was found in the reduced Hessian while Q has"
                    " full rank " + String(cv.rank) + "; the two contradict"
                )
                break
            if found:
                zero_curvature = True
                for j in range(n):
                    var acc3: Float64 = 0.0
                    for t in range(ns.nz):
                        acc3 += dir[t] * ns.z[t * n + j]
                    p[j] = acc3
            else:
                var rhs = _zeros(ns.nz)
                for t in range(ns.nz):
                    rhs[t] = -gz[t]
                var pz = _ldl_solve(ch, rhs)
                var chk = _matvec(hz, ns.nz, pz)
                # PER COMPONENT of the residual, each against the terms that produced THAT
                # component: `Σ_s |Hz_ts pz_s| + |gz_t|`. The previous form multiplied the
                # largest entry of the whole reduced Hessian by the largest entry of the whole
                # step, so one large row paid for another row's unsolved equation.
                var resid: Float64 = 0.0
                var resid_bad = False
                for t in range(ns.nz):
                    var d = fabs(chk[t] - rhs[t])
                    if d > resid:
                        resid = d
                    var row_scale = fabs(gz[t])
                    for u in range(ns.nz):
                        row_scale += fabs(hz[t * ns.nz + u] * pz[u])
                    if d > LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * Float64(
                        ns.nz + 1
                    ) * row_scale:
                        resid_bad = True
                if resid_bad or not _all_finite(pz):
                    terminal = QP_NUMERICAL_BREAKDOWN
                    breakdown = (
                        "the reduced Newton system was not solved: residual "
                        + String(resid)
                    )
                    break
                for j in range(n):
                    var acc4: Float64 = 0.0
                    for t in range(ns.nz):
                        acc4 += pz[t] * ns.z[t * n + j]
                    p[j] = acc4

        var pnorm = _max_abs(p)
        # "THE STEP IS ZERO" is a statement about the step against the POINT it would move, so
        # the scale is `x`'s own magnitude and nothing is added to it. A floored `(1 + |x|)` is
        # an ABSOLUTE allowance of one unit dressed as a relative one, and it is measurable:
        # `min 0.5x² - 1e-20 x`, whose minimiser is x = 1e-20, stopped at the ORIGIN and
        # reported it optimal, because the exact first step of 1e-20 was under the floor's
        # 2.3e-13. The objective difference is inside the caller's absolute `optimality_tol`,
        # so the status was not a lie — but the answer was the wrong point for a reason that
        # had nothing to do with the point. With this form the same call returns x = 1e-20.
        # When `x == 0` the test degenerates to `p == 0` exactly, which is the right reading:
        # from the origin, any nonzero step moves.
        var zero_step = LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * _max_abs(x)
        if ns.nz == 0 or pnorm <= zero_step:
            # This face is solved exactly, so the multipliers read here are the real ones.
            var mu = _multipliers(ns, g)
            # The multiplier of row i acts on the gradient as `μ_i · a_i`, so THAT is what is
            # compared with a gradient-scale threshold — and the scale is THIS row's own
            # gradient projection, `Σ_j |g_j · row_ij| / ||row_i||`, not `max_j |g_j|`, which is
            # an aggregate over components the row may not touch and which lets a genuinely
            # negative multiplier read as zero next to a large gradient component elsewhere.
            # Note this threshold governs the SEARCH PATH only: too generous a value stops the
            # dropping early, the point then fails the certificate, and the status is
            # `QP_NOT_CERTIFIED` — never a false success. The certificate's own thresholds are
            # per row and do not come from here.
            #
            # Computed ONCE into a list and then selected from. Recomputing the same
            # expression in a second selection pass invites the two passes to disagree — the
            # compiler is free to contract the two spellings differently — and the second pass
            # produced the INDEX, so a disagreement leaves `pick` at -1 and `w_set[-1]` is an
            # uncatchable process crash rather than an exception.
            var scaled = _zeros(len(w_set))
            var drop_tol = _zeros(len(w_set))
            var worst: Float64 = 0.0
            var have = False
            for idx in range(len(w_set)):
                var row = w_set[idx]
                if rw.is_eq[row]:
                    continue
                var proj_scale: Float64 = 0.0
                for j in range(n):
                    proj_scale += fabs(g[j] * rw.g[row * n + j])
                if rw.row_norm[row] > 0.0:
                    proj_scale = proj_scale / rw.row_norm[row]
                drop_tol[idx] = (
                    optimality_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * proj_scale
                )
                scaled[idx] = mu[idx] * rw.row_norm[row]
                if scaled[idx] < -drop_tol[idx] and (not have or scaled[idx] < worst):
                    worst = scaled[idx]
                    have = True
            if not have:
                terminal = 0
                break
            # The tie window is "are these two multipliers the same number?", so it is sized by
            # the multiplier being matched. `worst < -drop_tol <= 0` is strictly negative, so
            # the window is never degenerate, and the `(1 + ...)` floor it replaces was an
            # absolute 2.2e-13 window that tied multipliers that are not equal at all.
            var tie = LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * fabs(worst)
            var pick = -1
            for idx in range(len(w_set)):
                var row = w_set[idx]
                if rw.is_eq[row]:
                    continue
                # `< -drop_tol` as well as the tie window: without it the window could reach
                # past the threshold and drop a row whose multiplier is not negative at all.
                if scaled[idx] < -drop_tol[idx] and scaled[idx] <= worst + tie:
                    if pick < 0 or scan_rank[row] < scan_rank[w_set[pick]]:
                        pick = idx
            if pick < 0:
                terminal = QP_NUMERICAL_BREAKDOWN
                breakdown = "a droppable multiplier was found and then not found"
                break
            var dropped = w_set[pick]
            in_w[dropped] = False
            var kept = List[Int]()
            for idx in range(len(w_set)):
                if idx != pick:
                    kept.append(w_set[idx])
            w_set = kept^
            n_dropped += 1
            consecutive_drops += 1
            sig = _fold(sig, 1, stream)
            sig = _fold(sig, _unsigned(dropped), stream)
            if consecutive_drops > n + rw.m + 1:
                # Dropping without moving, more times than there are rows and directions.
                # No further progress is available; the certificate decides what this point
                # is, and it will not be called optimal unless it survives the audit.
                terminal = 0
                break
            continue
        consecutive_drops = 0
        if zero_curvature:
            n_zero_curvature += 1

        # ── the line search: how far before an inactive row blocks ────────────
        # Each candidate step is computed ONCE and stored; the selection then reads the list.
        # See the drop branch above for why a second computation of the same quantity is not
        # an acceptable way to find an index: -1 into a List is not an exception.
        # A row only blocks when the step moves INTO it — `a_iᵀp > 0` beyond what the dot
        # product's own rounding explains — so a row just dropped, which the step moves away
        # from, cannot re-enter on the very next iteration.
        var pn2 = vec_norm(p)
        var alphas = _zeros(rw.m)
        var alpha_min: Float64 = 0.0
        var have_block = False
        for i in range(rw.m):
            alphas[i] = -1.0
            if in_w[i] or rw.is_eq[i]:
                continue
            var gp: Float64 = 0.0
            for j in range(n):
                gp += rw.g[i * n + j] * p[j]
            if gp <= LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * rw.row_norm[i] * pn2:
                continue
            var slack_i = rw.h[i] - _row_activity(rw, i, x)
            if slack_i < 0.0:
                # An iterate can sit a rounding step outside a row it is meant to be on. The
                # honest step is then zero — move nothing, make the row active — rather than a
                # negative step, which would walk backwards out of the feasible set.
                slack_i = 0.0
            alphas[i] = slack_i / gp
            if not have_block or alphas[i] < alpha_min:
                alpha_min = alphas[i]
                have_block = True
        var blocker = -1
        if have_block:
            # Sized by the step being matched, as the header states ("ties within a rounding
            # budget of α"). The `(1 + ...)` floor it replaces was an absolute 2.2e-13 window,
            # which at `alpha_min == 0` — a row that blocks immediately, the common degenerate
            # case — tied every row whose step was under 2.2e-13 to a row that does not move
            # at all.
            var tie2 = LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * fabs(alpha_min)
            for i in range(rw.m):
                if alphas[i] >= 0.0 and alphas[i] <= alpha_min + tie2:
                    if blocker < 0 or scan_rank[i] < scan_rank[blocker]:
                        blocker = i
            if blocker < 0:
                terminal = QP_NUMERICAL_BREAKDOWN
                breakdown = "a blocking row was found and then not found"
                break

        if not have_block and zero_curvature:
            # A ray, and every one of its three claims is checked before the status is
            # returned: it keeps every row feasible, the objective is flat along it, and the
            # objective strictly decreases along it. `f(x + t d) = f(x) + t cᵀd → -∞`.
            var ok_ray = True
            for i in range(rw.m):
                var gp3: Float64 = 0.0
                for j in range(n):
                    gp3 += rw.g[i * n + j] * p[j]
                # Deliberately `(n + 1)` times looser than the blocking filter above, and the
                # direction of the difference is load-bearing. For an INACTIVE row the filter
                # already established `a_iᵀp <= its own tighter tolerance`, so this check
                # cannot fire on one; for an ACTIVE row `a_iᵀp` is zero only up to the error of
                # `n` orthogonalisation steps, which is what the factor pays for. A TIGHTER
                # tolerance here would turn a correct unbounded verdict into a spurious
                # breakdown; a looser one anywhere else would let a real violation through.
                var rtol2 = LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * Float64(
                    n + 1
                ) * rw.row_norm[i] * pn2
                if rw.is_eq[i]:
                    if fabs(gp3) > rtol2:
                        ok_ray = False
                elif gp3 > rtol2:
                    ok_ray = False
            # THE CURVATURE ALONG THIS DIRECTION, judged by this direction's own curvature and
            # by nothing else: `pᵀQp` against `Σ_jk |p_j Q_jk p_k|`, and every component of
            # `Qp` against that row's own terms `Σ_k |Q_jk p_k|`. `Q` is PSD here, so
            # `pᵀQp == 0` iff `Qp == 0`, and both are checked because the status promises the
            # second.
            #
            # It used to be `max_abs(Qp) > budget·eps·(n+1)·max|Q|·||p||` — the largest entry of
            # the WHOLE matrix. With `Q = diag(1e12, 0.5)` that threshold is 0.68, so
            # `Q·(0,1) = (0, 0.5)` passed as "no curvature" and `QP_UNBOUNDED` was returned for
            # a strictly convex program with the unique minimum x = (0, 2).
            var qp_dir = _matvec(qs, n, p)
            var curve: Float64 = 0.0
            var curve_scale: Float64 = 0.0
            for j in range(n):
                curve += p[j] * qp_dir[j]
                var row_scale: Float64 = 0.0
                for k2 in range(n):
                    var term = qs[j * n + k2] * p[k2]
                    row_scale += fabs(term)
                    curve_scale += fabs(p[j] * term)
                if fabs(qp_dir[j]) > LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * Float64(
                    n + 1
                ) * row_scale:
                    ok_ray = False
            if fabs(curve) > LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * Float64(
                n + 1
            ) * curve_scale:
                ok_ray = False
            if q_full_rank:
                # A full-rank PSD `Q` is positive definite, so `pᵀQp > 0` for every `p != 0`
                # and no ray can exist. Asserted rather than assumed: the two claims are made
                # by two different computations in this module and a caller must not receive
                # both.
                ok_ray = False
            var slope = vec_dot(g, p)
            if not (slope < 0.0):
                ok_ray = False
            if not ok_ray:
                terminal = QP_NUMERICAL_BREAKDOWN
                breakdown = "an unbounded direction failed its own verification"
                break
            var scale_p = _max_abs(p)
            for j in range(n):
                ray.append(p[j] / scale_p)
            terminal = QP_UNBOUNDED
            break

        var alpha: Float64 = 1.0
        if have_block:
            if zero_curvature or alpha_min < 1.0:
                alpha = alpha_min
        var moved = _zeros(n)
        for j in range(n):
            moved[j] = x[j] + alpha * p[j]
        if not _all_finite(moved):
            terminal = QP_NUMERICAL_BREAKDOWN
            breakdown = "the iterate overflowed at iteration " + String(iterations)
            break
        x = moved^
        sig = _fold(sig, 0, stream)
        if have_block and (zero_curvature or alpha_min <= 1.0):
            w_set.append(blocker)
            in_w[blocker] = True
            n_added += 1
            sig = _fold(sig, _unsigned(blocker), stream)
        else:
            sig = _fold(sig, _unsigned(-1), stream)

    out.iterations = iterations
    out.n_added = n_added
    out.n_dropped = n_dropped
    out.n_zero_curvature = n_zero_curvature
    out.n_active = len(w_set)
    out.phase1_status = phase1_status
    # The top bit is dropped so the signature is a non-negative Int on every platform; it is
    # an identifier for a search path, not an arithmetic value.
    out.path_signature = Int(sig >> 1)

    if terminal == QP_UNBOUNDED:
        var unb = _qp_rejected(
            QP_UNBOUNDED,
            "no minimum: a feasible direction with zero curvature strictly decreases the"
            " objective, so the infimum is -infinity",
        )
        _stamp(unb, n, rows, cv)
        unb.iterations = iterations
        unb.n_added = n_added
        unb.n_dropped = n_dropped
        unb.n_zero_curvature = n_zero_curvature
        unb.n_active = len(w_set)
        unb.phase1_status = phase1_status
        unb.path_signature = Int(sig >> 1)
        unb.ray = ray^
        return unb^
    if terminal == QP_NUMERICAL_BREAKDOWN:
        var brk = _qp_rejected(QP_NUMERICAL_BREAKDOWN, breakdown)
        _stamp(brk, n, rows, cv)
        brk.iterations = iterations
        brk.phase1_status = phase1_status
        brk.path_signature = Int(sig >> 1)
        return brk^

    # ── the duals of the final active set ─────────────────────────────────────
    var ns_f = _null_space(rw, w_set, n)
    var g_f = _matvec(qs, n, x)
    for j in range(n):
        g_f[j] += c[j]
    var mu_f = _multipliers(ns_f, g_f)
    var duals = _zeros(rows)
    var lower_duals = _zeros(n)
    var upper_duals = _zeros(n)
    var row_active = _falses(rows)
    var lower_active = _falses(n)
    var upper_active = _falses(n)
    for idx in range(len(w_set)):
        var row = w_set[idx]
        # ONE formula for every origin: `dual = -μ · flip`. A `<=` row keeps `flip = +1` and
        # gets a non-positive dual, a `>=` row was stored negated and gets a non-negative
        # one, a lower bound was stored as `-x_j <= -l_j` and gets a non-negative one, and an
        # upper bound gets a non-positive one — which is exactly "∂f*/∂(this right-hand
        # side)" in every case.
        var value = -mu_f[idx] * rw.flip[row]
        var origin = rw.origin[row]
        if origin < rows:
            duals[origin] = value
            row_active[origin] = True
        elif origin < rows + n:
            lower_duals[origin - rows] = value
            lower_active[origin - rows] = True
        else:
            upper_duals[origin - rows - n] = value
            upper_active[origin - rows - n] = True

    out.rank_active = ns_f.rank
    out.degenerate_active_set = ns_f.rank < len(w_set)

    var cert = _certificate(
        qs, n, c, a, rows, senses, b, lower, upper, bound_flags, x, duals, lower_duals,
        upper_duals, feasibility_tol, optimality_tol, True, True,
    )
    out.certified = cert.certified
    out.stationarity_ok = cert.stationarity_ok
    out.primal_ok = cert.primal_ok
    out.dual_ok = cert.dual_ok
    out.slackness_ok = cert.slackness_ok
    out.stationarity_violation = cert.stationarity_violation
    out.primal_violation = cert.primal_violation
    out.dual_violation = cert.dual_violation
    out.slackness_violation = cert.slack_dual_violation

    if not cert.primal_ok:
        # Every iterate is feasible by construction, so an infeasible one means the
        # arithmetic broke. The point is NOT returned: the invariant is that `x` is present
        # only when it has been verified.
        var brk2 = _qp_rejected(
            QP_NUMERICAL_BREAKDOWN,
            "the final iterate violates the caller's own rows by "
            + String(cert.primal_violation),
        )
        _stamp(brk2, n, rows, cv)
        brk2.iterations = iterations
        brk2.primal_violation = cert.primal_violation
        brk2.phase1_status = phase1_status
        brk2.path_signature = Int(sig >> 1)
        return brk2^

    var bnd = _bound_at(qs, n, c, rw, x, max_iterations, feasibility_tol, optimality_tol)
    out.bound_status = bnd.lp_status
    out.has_bound = bnd.has_bound
    out.best_bound = bnd.best_bound if bnd.has_bound else 0.0
    out.has_gap = bnd.has_gap
    out.gap = bnd.gap if bnd.has_gap else 0.0

    out.feasible = True
    out.has_objective = cert.has_objective
    out.objective = cert.objective
    # An ABSENT second opinion is not a disagreement. The KKT audit is, for a CONVEX
    # objective, a proof of global optimality on its own; the linearisation bound is a second,
    # independent computation whose job is to CONTRADICT it if either is wrong. So optimality
    # requires the audit to pass and the bound not to object — not for the bound to exist.
    #
    # Measured on 1200 randomised instances (n up to 8, mixed senses, scales 1e-2 to 1e2, half
    # of them with free variables): 29 came back with all four KKT conditions satisfied and NO
    # bound, every one of them because the bounding LP was UNBOUNDED. That is not a defect in
    # either computation. When the feasible set has a ray, the linearisation `min gᵀz` over it
    # is unbounded the moment `g` has any component along that ray — and at a QP optimum `g`'s
    # component along a flat feasible direction is zero only up to rounding. Requiring the
    # bound would therefore have reported `QP_NOT_CERTIFIED`, with every condition satisfied
    # and a gap of zero, for 2.4% of ordinary convex programs.
    #
    # `at_optimum` is the bound's own verdict on its own gap: it holds `f(x)`, `gᵀx` and the
    # LP's value, and re-deciding here from `gap` alone would size the rounding term by one of
    # the three numbers the subtraction used.
    var gap_objects = bnd.has_bound and not bnd.at_optimum
    out.proven_optimal = cert.certified and not gap_objects
    if out.proven_optimal:
        out.status = QP_OPTIMAL
        out.message = String("")
    elif terminal == QP_ITERATION_LIMIT:
        out.status = QP_ITERATION_LIMIT
        out.message = (
            "the search hit its iteration cap; the point is feasible and its objective is"
            " an upper bound, with the remaining gap reported"
        )
    else:
        out.status = QP_NOT_CERTIFIED
        out.message = cert.message
        if cert.certified and gap_objects:
            # The two certificates disagree, which is the case this cross-check exists for:
            # one of them is wrong and nothing here can say which, so neither is believed.
            out.message = (
                "KKT holds but the independent linearisation bound leaves a gap of "
                + String(bnd.gap)
                + "; the two certificates disagree, so neither is claimed"
            )
    out.x = x^
    out.duals = duals^
    out.lower_duals = lower_duals^
    out.upper_duals = upper_duals^
    var pr_f = _primal_scan(
        a, rows, n, senses, b, lower, upper, bound_flags, out.x, feasibility_tol
    )
    out.activity = pr_f.activity.copy()
    out.slack = pr_f.slack.copy()
    out.binding = pr_f.binding.copy()
    out.row_active = row_active^
    out.lower_active = lower_active^
    out.upper_active = upper_active^
    return out^


fn qp_solve_default(
    q: List[Float64], n: Int, c: List[Float64], a: List[Float64], rows: Int,
    senses: List[Int], b: List[Float64], lower: List[Float64], upper: List[Float64],
    bound_flags: List[Int], seed: UInt64,
) -> QPSolution:
    """`qp_solve` with `model.mojo`'s default policy. The seed stays explicit.

    The tolerances have defaults because a caller who has not thought about them wants the
    package's, and `model.policy_defect` is the single definition of which ones are usable.
    The SEED does not: a defaulted seed is how a search stops being reproducible without
    anybody deciding that it should.
    """
    return qp_solve(
        q, n, c, a, rows, senses, b, lower, upper, bound_flags,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL, seed,
    )
