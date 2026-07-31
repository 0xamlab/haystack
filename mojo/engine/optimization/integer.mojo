"""
optimization.integer — branch and bound with an optimality gap that tells the truth.

Why this file exists
--------------------
Nothing in the tree solves an integer program. `combinatorial.knapsack_01` is an exact
0/1 knapsack DP and `combinatorial.assignment_greedy` is a heuristic, but both are one
fixed problem shape over `List[Int]`, neither carries a status, and neither can express
"maximise `c·x` over `A x {<=,=,>=} b` with some of `x` integral". `linear_programming`
and `optimization.linear` relax integrality away entirely. So the only route from a model
with integer variables to an answer was to solve the relaxation and round, and a rounded
LP vertex is usually infeasible and never known to be optimal.

The failure this module exists to prevent
-----------------------------------------
A branch-and-bound search that stops early has an INCUMBENT, not an optimum, and the two
are the same data structure. Every field of the answer looks identical: a feasible point,
an objective value, a status. The difference is entirely in whether the unexplored part of
the tree could hold something better — which is a fact about the search, not about the
point. A solver that reports its incumbent as the optimum when a node limit stopped it is
therefore returning a wrong answer with a right-looking shape, and no caller can detect it
from the answer alone.

So `MILPResult` separates three things that are usually conflated:

  * `feasible` — a point was found and VERIFIED against the caller's own rows;
  * `proven_optimal` — nothing unexplored can beat it by more than `optimality_tol`;
  * `search_complete` — the tree was exhausted.

`proven_optimal` is False whenever a limit truncated the search and the remaining bound
does not already close the gap, and `gap` then reports the real remaining uncertainty:
`|objective - best_bound|`, where `best_bound` is the minimum bound over every node that
was never explored. Both endpoints are returned, so the caller can form any relative
measure it wants; no relative gap is reported here, because the scale it needs is the
caller's (`|objective|` is 0 for a legitimate zero optimum, and `1 + |objective|` is a
convention, not a fact).

An infeasible integer program is a distinct outcome from a truncated search that found
nothing, and both are distinct from an UNBOUNDED RELAXATION — which, and this is the point
of having a separate code for it, does NOT prove the integer program is unbounded. The two
directions come apart in both ways: `max x s.t. 2x = 1, x integral` has a bounded
relaxation and no integer point at all, while `max 2x s.t. 3x >= 1` is unbounded as an LP
and also as an integer program. What this solver cannot do is tell the unbounded case from
the infeasible one once the relaxation has no finite optimum, because it never obtains a
bound to branch on. `MILP_RELAXATION_UNBOUNDED` says exactly that and carries no answer,
rather than picking one of the two.

The search
----------
Depth-first over an EXPLICIT STACK of `_Node`, never recursion: the depth is the number of
branch decisions, which is data-dependent, and a recursive search would put the caller's
data in charge of the native stack.

*Bound.* Every node's bound is its own LP relaxation, solved by
`optimization.linear.lp_solve` — the same two-phase simplex the LP surface exposes, called
once per node with no second code path. A node is pruned when its bound cannot beat the
incumbent by more than `optimality_tol`; that is checked twice, once against the bound
inherited at push time (cheap, and the incumbent may have improved since) and once against
the node's own relaxation.

*Branching variable: most fractional, lowest index on a tie.* Stated because
`nodes_branched` is a reported number and a rule chosen at random makes it
unreproducible. Rejected pseudocost branching: it needs per-variable degradation history,
so the tree a caller gets depends on the order nodes happened to be popped, and the same
model can then report a different census run to run for no reason the caller can see.
`branch_choice` is public so the rule is inspectable rather than folded into the loop.

*Branch bounds are ROWS, and they are TIGHTENED, not stacked.* A branch on `x_j` at 2.5
gives children `x_j <= 2` and `x_j >= 3`, expressed the way `optimization.linear` expresses
every bound — as a row of `A`, per its own stated convention that a bound the solver hides
is a bound the caller cannot see. Each node carries one lower and one upper bound per
variable and REPLACES a looser ancestor bound instead of appending another row, so the
per-node LP is at most `rows + 2*cols` and the tableau size does not grow with depth.
The `x >= 0` lower bound is implicit in `lp_solve`, so a lower bound of 0 costs no row.

*Ceil branch first.* An arbitrary choice would be fine for correctness; this one is stated
because it is observable in the census. The ceil child fixes the variable to the larger
value, which in a select-or-produce formulation is where an incumbent usually lives, and an
early incumbent is what makes pruning bite.

*Best-first was rejected.* It gives a valid global bound at every moment, which is
attractive here, but its frontier grows with the whole search rather than with the depth,
and the frozen `heap.heap_push_min` orders bare `Float64` values — a best-first queue would
need a parallel index array kept in step with it by hand, which is a second invariant to
get wrong. Depth-first plus a minimum over the surviving stack gives the same honest bound
at the one moment it is reported.

*A binary variable's upper bound is added here.* General bounds stay the caller's rows, but
`VAR_BINARY` already promises `x in {0, 1}` by its name, and a variable a caller declared
binary coming back as 7 because it forgot the `x <= 1` row is precisely the silent wrong
answer this package removes. `VAR_BINARY` therefore starts with `up = 1` in the root node,
which is a bound row like any other and is counted in neither `n_constraints` nor the
duals — this result reports no duals at all, because an integer program has none: LP
duality does not survive the integrality constraint, and reporting the final node's LP
duals as "the" duals would be a number in the right units about a different program.

*No warm start, and no rounding heuristic.* Both would produce an incumbent that PRUNES,
and an incumbent that has not been verified feasible prunes the true optimum. The
verification is the whole cost of the feature, and `model.check_variables` already rejects a
warm start that is out of its bounds but cannot check the caller's rows, so a start that
looks valid there can still be infeasible. The incumbent here always comes from a node
relaxation that came back integral, and is then re-verified against the caller's own rows
with `model.sense_violation` before it is allowed to prune anything.

Snapping, and the tolerance that has to survive it
--------------------------------------------------
A relaxation optimum that is integral to within `integrality_tol` is snapped to the exact
grid before it becomes the incumbent, and the objective is RECOMPUTED at the snapped point
with `linear.linear_form_value` rather than taken from the LP. A reported objective that
belongs to a slightly different point than the reported `x` is a self-inconsistency a
caller cannot see, and the two differ by up to `integrality_tol * Σ|c_j|`.

Snapping can also break feasibility: moving each SNAPPED coordinate by up to
`integrality_tol` moves row `i`'s activity by up to `integrality_tol * Σ_j |a_ij|` over the
integer and binary columns only, which for a tight row can exceed `feasibility_tol`. The
verification therefore allows exactly that much and no more — see `_verify_row_budget` for
the three terms and for the two forms that are NOT used. A point that violates a row by
more than that budget means the two tolerances are inconsistent with the caller's scaling,
and that is reported as `MILP_SNAP_INFEASIBLE` — an aborted search with no bound and no gap
— rather than accepted as an incumbent that would then prune the real optimum.

Termination, and the two limits
-------------------------------
An integer variable with no upper bound admits an infinite branch chain, so a node limit is
not a convenience, it is the only termination guarantee this search has. `max_nodes` is
required (there is no "unlimited"), and `MILP_MAX_DEPTH` caps the stack depth
independently. Hitting either truncates the search: the abandoned nodes' bounds still count
towards `best_bound`, `search_complete` is False, and `proven_optimal` is False unless the
surviving bound happens to close the gap anyway — in which case the answer IS optimal, the
status says so, and `search_complete` still reports that the tree was not exhausted.

`integrality_tol` must be strictly positive. Zero is rejected rather than honoured: an LP
vertex at 2.9999999999999996 is then fractional, so the solver branches forever on a
program whose answer it is already holding.

A declared variable box is part of the program, not a hint
----------------------------------------------------------
`milp_from_arenas` takes `model.ModelFlat`'s four VARIABLE columns alongside its arenas and
turns the declared box into rows, because `linear.lp_from_arenas` deliberately does not:
that function builds its own all-zero `var_lower`/`var_upper` block with
`VAR_FLAG_HAS_LOWER`, since an LP arena states expressions and its convention is `x >= 0`.
An arena driver that forwarded only `var_kind` therefore solved the caller's ROWS with the
caller's BOX discarded, and a model stating `x <= 3` came back with `x = 10` and
`proven_optimal = True`. A box that extends below zero cannot be expressed at all under the
`x >= 0` convention, so it is `MILP_BOX_BELOW_ZERO` rather than a clip to 0 — clipping
solves a smaller program and the optimum of a smaller program is not this model's.

Status codes are one numbering with `optimization.model` and `optimization.linear`
---------------------------------------------------------------------------------
0 is optimal, `model.mojo`'s 0-30 keep their meanings, `linear.mojo`'s extractor codes
(40+) and solver outcomes (60+) keep theirs — `MILP_INFEASIBLE` IS `LP_INFEASIBLE`,
because an integer program with no feasible point is infeasible in the same sense —
`optimization.explain` owns 80-86, and the new outcomes here start at 100.
`milp_status_name` falls through to `lp_status_name` and then to `model_status_name`, so a
malformed arena names the arena defect rather than "unknown status 8".

Ceilings
--------
`MAX_CSR_DIM` for dimensions and `LP_MAX_TABLEAU_CELLS` for the dense area are imported,
never redefined, and the area test accounts for the `2*cols` bound rows a node can add —
plus, on the arena path, the box rows, counted before a single cell of them is allocated.
Both are compared with a DIVISION: `rows * cols` is a wrapping multiply, and
`3 * 6148914691236517206 == 2`. `MILP_MAX_NODES`, `MILP_MAX_DEPTH` and `MILP_MAX_STACK` are
new because they bound three resources — search work, stack depth and live stack memory —
that no dimension limit constrains.
"""
from std.math import abs as fabs, floor

from linalg import vec_dot
from optimization.linear import (
    LP_DBL_EPSILON,
    LP_FEAS_ULP_BUDGET,
    LP_INFEASIBLE,
    LP_MAX_TABLEAU_CELLS,
    LP_OPTIMAL,
    LP_UNBOUNDED,
    linear_form_value,
    lp_from_arenas,
    lp_solve,
    lp_status_name,
)
from optimization.model import (
    DEFAULT_FEASIBILITY_TOL,
    DEFAULT_INTEGRALITY_TOL,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_OPTIMALITY_TOL,
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_DIMENSION_TOO_LARGE,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_ERR_NON_FINITE_COEFFICIENT,
    MODEL_ERR_NON_FINITE_POINT,
    MODEL_ERR_NON_FINITE_RHS,
    MODEL_ERR_NON_FINITE_VALUE,
    MODEL_ERR_OVERFLOW,
    MODEL_ERR_POLICY,
    MODEL_ERR_SENSE,
    MODEL_ERR_VAR_KIND,
    MODEL_INT_GRID_MAX,
    MODEL_OK,
    MODEL_VIOLATION_ABSENT,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    VAR_BINARY,
    VAR_CONTINUOUS,
    VAR_FLAG_BOXED,
    VAR_INTEGER,
    _policy_parts_defect,
    _round_f as _nearest_int,
    has_lower_bound,
    has_upper_bound,
    minimization_value,
    model_finite as _finite,
    sense_violation,
    variables_defect_flat,
    variables_validate_flat,
)
from sparse_numerics.csr import MAX_CSR_DIM, dims_fit

# ── status codes ──────────────────────────────────────────────────────────────
# ONE numbering is shared across the modules whose statuses reach the same caller, so a
# code has one meaning package-wide. The ranges already taken:
#
#   0-30    `optimization.model` — arena, bound-column and policy defects
#   40-42   `optimization.linear` — the linear extractor's non-linearity codes
#   60-63   `optimization.linear` — solver outcomes (`LP_INFEASIBLE` is 60)
#   80-86   `optimization.explain` — certificate and core-verification outcomes
#   100+    this module
#
# These used to start at 80 and therefore MEANT TWO THINGS AT ONCE: `milp_status_name(81)`
# said "node_limit" while `explain_status_name(81)` said "feasible, no infeasibility core",
# for the same integer out of the same package. A caller that logs or switches on a code
# cannot tell which vocabulary produced it, so the block moved rather than the ambiguity
# being documented. Anything added here goes at 106+ and stays out of 80-86.
#
# (`optimization.flow` and `optimization.assignment` carry their own small numberings from
# 0; they are separate vocabularies that never mix with this one, because neither a flow
# network nor an assignment matrix is a `MILPResult`.)
#
# An integer program with no feasible point reuses LP_INFEASIBLE rather than inventing a
# second code for the same fact: a caller switching on 60 gets the same meaning from either
# solver.

comptime MILP_OPTIMAL: Int = LP_OPTIMAL
comptime MILP_INFEASIBLE: Int = LP_INFEASIBLE

# The relaxation has no finite optimum, so there is no bound to branch on. This is NOT
# "the integer program is unbounded": the integer program may equally be infeasible, and
# distinguishing them needs a bound this solver never obtained.
comptime MILP_RELAXATION_UNBOUNDED: Int = 100

# The search was truncated. An incumbent may be attached; `proven_optimal` says whether it
# is nonetheless optimal, and `gap` says how much is unaccounted for.
comptime MILP_NODE_LIMIT: Int = 101
comptime MILP_DEPTH_LIMIT: Int = 102

# A node's relaxation came back neither optimal nor infeasible — an iteration limit or a
# numerical breakdown inside the simplex. That subtree has no bound, so the search cannot
# continue honestly and `relaxation_status` carries the simplex's own code.
comptime MILP_RELAXATION_FAILED: Int = 103

# An integral relaxation optimum stopped satisfying the caller's rows once it was snapped
# to the grid: `integrality_tol` and `feasibility_tol` are inconsistent with the row
# scaling. Accepting the point would let it prune the true optimum.
comptime MILP_SNAP_INFEASIBLE: Int = 104

# A declared variable box extends BELOW ZERO — a negative lower bound, or no lower bound at
# all — and this solver's variable convention is `x >= 0`. Refused rather than clipped:
# clipping solves a smaller program, and the optimum of a smaller program comes back
# `proven_optimal` for a model that never stated it.
comptime MILP_BOX_BELOW_ZERO: Int = 105

# Search work and stack depth are resources no dimension limit bounds. 2^20 nodes at one
# LP each is already minutes of work; 2^10 branch decisions is deeper than any bounded
# integer program needs, and an unbounded one is stopped by `max_nodes` first.
comptime MILP_MAX_NODES: Int = 1 << 20
comptime MILP_MAX_DEPTH: Int = 1 << 10

# The live stack, stated as a constant instead of left as a consequence a reader has to
# re-derive. It is NOT `max_nodes`: a depth-first walk of a BINARY tree that pushes both
# children and immediately pops one leaves at most one sibling per level behind it, so the
# stack holds at most `depth + 1` nodes — not one per node ever created. The deepest node
# this search ever pops is at `MILP_MAX_DEPTH + 1` (deeper nodes are abandoned), and after
# that pop the stack holds at most `MILP_MAX_DEPTH` nodes plus the two children about to be
# pushed, so `MILP_MAX_DEPTH + 2` is exact and tight.
#
# The memory that bounds: a node carries four columns of `cols` entries — two `Float64` and
# two `Bool`, 18 bytes per variable — so the worst case at the widest `cols` the area check
# admits (`LP_MAX_TABLEAU_CELLS // (2*cols) >= rows` allows `cols` up to 4096 with a single
# row) is `1026 * 4096 * 18` bytes ≈ 76 MB, not the ≈ 76 GB that one node per explored node
# would cost at `MILP_MAX_NODES`. The check below is therefore belt and braces on an
# invariant, and it truncates honestly — as a depth limit, since depth is the resource it
# actually bounds — rather than growing until the allocator fails.
comptime MILP_MAX_STACK: Int = MILP_MAX_DEPTH + 2

# The default for the convenience driver. Explicit, and small enough that an accidental
# call on a hard program returns a truncated answer that SAYS it is truncated rather than
# running for minutes.
comptime MILP_DEFAULT_MAX_NODES: Int = 10000


fn milp_status_name(code: Int) -> String:
    """Name for a branch-and-bound status, falling through to `lp_status_name`."""
    if code == MILP_RELAXATION_UNBOUNDED:
        return "relaxation_unbounded"
    if code == MILP_NODE_LIMIT:
        return "node_limit"
    if code == MILP_DEPTH_LIMIT:
        return "depth_limit"
    if code == MILP_RELAXATION_FAILED:
        return "relaxation_failed"
    if code == MILP_SNAP_INFEASIBLE:
        return "integral_point_infeasible_when_snapped"
    if code == MILP_BOX_BELOW_ZERO:
        return "declared_variable_box_extends_below_zero"
    return lp_status_name(code)


# ── helpers this module USES but does not DEFINE ──────────────────────────────
# `_finite` is `model.model_finite` and `_nearest_int` is `model._round_f`, both imported
# above under the local names this file used to define, so no call site here changed. Mojo
# has no access control, so the leading underscore only keeps a name out of the runtime
# contract (a predicate and a rounding routine are not drivers) — it does not stop a sibling
# importing it, which is why one definition is achievable at all.
#
# `_nearest_int` is NOT redefined here, and the reason is narrow enough to state: the copy
# had to carry a `|v| >= 2^52` short-circuit, because in `[2^52, 2^53)` the spacing between
# doubles is exactly 1.0, so `v + 0.5` is an exact tie that round-half-to-even carries to the
# neighbour — `floor(2^52 + 1 + 0.5)` returned `2^52 + 2`, moving an already-integral value
# to a DIFFERENT integer, and `MODEL_INT_GRID_MAX` does not screen it because 9.0e15 is below
# 2^53. Both copies were fixed the same way at the same time. Two copies of a subtlety that
# narrow is exactly how one of them drifts back. See `model._round_f`.
#
# Policy validation is delegated the same way: `_policy_parts_defect` reaches
# `model.policy_defect`, the package's single definition of a policy a solver will honour.


# ── return-only result structs ────────────────────────────────────────────────
# Declared here because a returned struct's marshalling spec is parsed per FILE: returning
# `linear.LPSolution` would drop the function from the runtime contract silently.


@fieldwise_init
struct BranchChoice(Copyable, Movable):
    """The branching variable at a point, or the fact that there is none.

    `has_branch` is the authority. `var_index == -1` with `MODEL_OK` means every discrete
    variable is already integral to within `integrality_tol` — a real and important answer,
    which is why it is not the same return as a rejected input.

    `fractionality` is the distance to the NEAREST integer, so it lies in
    `(integrality_tol, 0.5]`, and `floor_bound` / `ceil_bound` are the two children's
    bounds. They differ by exactly 1 because the value is strictly fractional.
    """

    var status: Int
    var has_branch: Bool
    var var_index: Int
    var value: Float64
    var fractionality: Float64
    var floor_bound: Float64
    var ceil_bound: Float64
    var n_fractional: Int
    var n_discrete: Int


@fieldwise_init
struct MILPResult(Copyable, Movable):
    """A mixed-integer answer, with the search's own honesty about it.

    Three booleans, because they are three different facts and a solver that ships one of
    them is the reason this module exists:

      * `feasible` — `x` holds a point that satisfies every row of the caller's program and
        is integral on every discrete variable, VERIFIED after snapping rather than trusted
        from the relaxation. False means `x` is EMPTY and `has_objective` is False.
      * `proven_optimal` — no unexplored region can beat `objective` by more than
        `optimality_tol`. False on any truncated search whose remaining bound does not
        already close the gap, and `status` is then the truncation code, never `optimal`.
      * `search_complete` — the branch tree was exhausted. A truncated search can still be
        `proven_optimal` (the surviving bounds closed the gap), so these two are not the
        same flag.

    `best_bound` is a LOWER bound on a minimisation and an UPPER bound on a maximisation —
    the caller's sense throughout, converted with `model.minimization_value`, the same
    involution `optimization.linear` uses. `gap` is the non-negative magnitude
    `|objective - best_bound|`, and `has_gap` is False when either endpoint is missing:
    a gap of 0.0 claims proven optimality, so an unknown gap must not be padded with it.

    `relaxation_objective` is the ROOT relaxation's optimum, in the caller's sense, and
    includes the binary upper bounds. It is reported because "the LP said 41.25 and the
    integer answer is 40" is the first thing anyone checks, and because a relaxation value
    equal to the integer value is the signal that branching was never needed.

    The node census is exact and self-checking:
      `nodes_explored == nodes_pruned + nodes_infeasible + nodes_integral + nodes_branched`
      `1 + 2*nodes_branched == nodes_explored + nodes_open`
    `nodes_open` counts nodes that were never classified: those left on the stack when a
    limit stopped the search, those abandoned at the depth limit, and — on an aborted
    search — the node whose relaxation failed, because its subtree is exactly what remains
    unaccounted for.

    No duals. An integer program has none: LP duality does not survive the integrality
    constraint, and the final node's LP duals are a number in the right units about a
    different program.
    """

    var status: Int
    var feasible: Bool
    var proven_optimal: Bool
    var search_complete: Bool
    var has_objective: Bool
    var objective: Float64
    var has_bound: Bool
    var best_bound: Float64
    var has_gap: Bool
    var gap: Float64
    var has_relaxation_objective: Bool
    var relaxation_objective: Float64
    var relaxation_status: Int
    var n_vars: Int
    var n_constraints: Int
    var n_integer: Int
    var n_binary: Int
    var nodes_explored: Int
    var nodes_pruned: Int
    var nodes_infeasible: Int
    var nodes_integral: Int
    var nodes_branched: Int
    var nodes_open: Int
    var max_depth: Int
    var lp_iterations: Int
    var x: List[Float64]


fn _no_branch(status: Int, n_fractional: Int, n_discrete: Int) -> BranchChoice:
    return BranchChoice(
        status, False, -1, 0.0, 0.0, 0.0, 0.0, n_fractional, n_discrete
    )


fn _milp_rejected(status: Int, n_vars: Int, n_cons: Int) -> MILPResult:
    """A rejected request: no answer, no bound, no gap, and no census to report."""
    return MILPResult(
        status, False, False, False, False, 0.0, False, 0.0, False, 0.0,
        False, 0.0, MODEL_OK, n_vars, n_cons, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        List[Float64](),
    )


# ── the branching rule, public so it can be inspected ─────────────────────────


fn branch_choice(
    x: List[Float64], var_kind: List[Int], integrality_tol: Float64
) -> BranchChoice:
    """The most-fractional discrete variable at `x`, lowest index on a tie.

    Every guard runs before any index is used for arithmetic, and `|x_j|` past the Float64
    integer grid is `MODEL_ERR_OVERFLOW` rather than a `floor` whose `+1` child bound is
    the same number — an "integer" branch that does not narrow anything would loop until
    the node limit and report a gap it could never close.
    """
    if len(var_kind) != len(x):
        return _no_branch(MODEL_ERR_LENGTH_MISMATCH, 0, 0)
    # `model.policy_defect` decides what `integrality_tol` may be, here as everywhere else in
    # the package: zero is refused, not honoured, because at zero 2.9999999999999996 is
    # fractional and the search branches forever on an answer it already has. The three
    # known-valid defaults stand in for the policy fields a branching rule does not take.
    var tol_defect = _policy_parts_defect(
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL,
        DEFAULT_OPTIMALITY_TOL, integrality_tol,
    )
    if tol_defect != MODEL_OK:
        return _no_branch(tol_defect, 0, 0)
    var n = len(x)
    var n_discrete = 0
    for j in range(n):
        var kind = var_kind[j]
        if kind != VAR_CONTINUOUS and kind != VAR_INTEGER and kind != VAR_BINARY:
            return _no_branch(MODEL_ERR_VAR_KIND, 0, 0)
        if kind != VAR_CONTINUOUS:
            n_discrete += 1

    var best = -1
    var best_frac: Float64 = 0.0
    var best_value: Float64 = 0.0
    var n_fractional = 0
    for j in range(n):
        if var_kind[j] == VAR_CONTINUOUS:
            continue
        var v = x[j]
        if not _finite(v):
            return _no_branch(MODEL_ERR_NON_FINITE_POINT, n_fractional, n_discrete)
        if fabs(v) > MODEL_INT_GRID_MAX:
            return _no_branch(MODEL_ERR_OVERFLOW, n_fractional, n_discrete)
        var below = floor(v)
        var frac = v - below
        var distance = frac
        if 1.0 - frac < distance:
            distance = 1.0 - frac
        if distance <= integrality_tol:
            continue
        n_fractional += 1
        # STRICTLY greater, so an exact tie keeps the lower index. A rule whose answer
        # depends on the scan direction is a rule no test can pin down.
        if distance > best_frac:
            best_frac = distance
            best_value = v
            best = j
    if best < 0:
        return BranchChoice(MODEL_OK, False, -1, 0.0, 0.0, 0.0, 0.0, 0, n_discrete)
    var below = floor(best_value)
    return BranchChoice(
        MODEL_OK, True, best, best_value, best_frac, below, below + 1.0,
        n_fractional, n_discrete,
    )


# ── the search's internals ────────────────────────────────────────────────────


@fieldwise_init
struct _Node(Copyable, Movable):
    """One subproblem: the box it inherited, plus the bound it inherited.

    Bounds are per-variable and TIGHTENED on the way down rather than appended, so the
    node's LP has at most `rows + 2*cols` rows whatever the depth. `has_bound` is False
    only for the root, because nothing has been solved yet — and that absence is why the
    global bound can legitimately be missing, rather than being padded with an infinity
    that would then do arithmetic.
    """

    var has_bound: Bool
    var bound: Float64
    var depth: Int
    var lo: List[Float64]
    var has_lo: List[Bool]
    var up: List[Float64]
    var has_up: List[Bool]


@fieldwise_init
struct _Program(Copyable, Movable):
    """A node's LP: the caller's rows with the node's bound rows appended. Internal."""

    var rows: Int
    var a: List[Float64]
    var senses: List[Int]
    var rhs: List[Float64]


fn _milp_input_defect(
    c: List[Float64],
    constant: Float64,
    a: List[Float64],
    rows: Int,
    cols: Int,
    senses: List[Int],
    rhs: List[Float64],
    var_kind: List[Int],
    max_nodes: Int,
    max_iterations: Int,
    feasibility_tol: Float64,
    optimality_tol: Float64,
    integrality_tol: Float64,
) -> Int:
    """`MODEL_OK` when every length, shape, kind and policy is one the search can use.

    These are `linear._lp_input_defect`'s SHAPE checks plus the kind column and the node
    limits, repeated here because this module indexes `a`, `senses` and `rhs` to build each
    node's augmented program BEFORE `lp_solve` ever sees them — an unvalidated read past a
    List end is an uncatchable process crash, not an exception.

    The POLICY checks are not repeated. `_policy_parts_defect` reaches
    `model.policy_defect`, which is the package's single definition of a policy a solver will
    honour, so `max_iterations` and the three tolerances are judged here exactly as
    `model_validate`, `linear._lp_input_defect`, `branch_choice` and
    `explain._core_input_defect` judge them. Only `max_nodes` is this module's own.
    """
    if rows < 0 or cols < 0:
        return MODEL_ERR_DENSE_SHAPE
    if not dims_fit(rows, cols, len(a)):
        # Division inside `dims_fit`, never `rows * cols == len(a)`: that product wraps.
        return MODEL_ERR_DENSE_SHAPE
    if cols > MAX_CSR_DIM or rows > MAX_CSR_DIM:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    if len(c) != cols:
        return MODEL_ERR_LENGTH_MISMATCH
    if len(senses) != rows or len(rhs) != rows:
        return MODEL_ERR_LENGTH_MISMATCH
    if len(var_kind) != cols:
        return MODEL_ERR_LENGTH_MISMATCH
    if cols > 0:
        # A node adds at most one lower and one upper bound row per variable, so the
        # widest program the search can build is `rows + 2*cols` deep. Checked by
        # DIVISION, and `budget - 2*cols` may go negative, which correctly rejects.
        var budget = LP_MAX_TABLEAU_CELLS // cols
        if rows > budget - 2 * cols:
            return MODEL_ERR_DIMENSION_TOO_LARGE
    if max_nodes < 1 or max_nodes > MILP_MAX_NODES:
        # No "unlimited": an integer variable with no upper bound admits an infinite branch
        # chain, so the node limit is this search's only termination guarantee.
        return MODEL_ERR_POLICY
    # Iteration cap and the three tolerances: `model.policy_defect` via
    # `_policy_parts_defect`, never restated here. `max_nodes` above is this module's own
    # field and stays here.
    var policy_status = _policy_parts_defect(
        max_iterations, feasibility_tol, optimality_tol, integrality_tol
    )
    if policy_status != MODEL_OK:
        return policy_status
    if not _finite(constant):
        return MODEL_ERR_NON_FINITE_COEFFICIENT
    for j in range(cols):
        if not _finite(c[j]):
            return MODEL_ERR_NON_FINITE_COEFFICIENT
        var kind = var_kind[j]
        if kind != VAR_CONTINUOUS and kind != VAR_INTEGER and kind != VAR_BINARY:
            return MODEL_ERR_VAR_KIND
    for i in range(len(a)):
        if not _finite(a[i]):
            return MODEL_ERR_NON_FINITE_COEFFICIENT
    for i in range(rows):
        if senses[i] != SENSE_LE and senses[i] != SENSE_EQ and senses[i] != SENSE_GE:
            return MODEL_ERR_SENSE
        if not _finite(rhs[i]):
            return MODEL_ERR_NON_FINITE_RHS
    return MODEL_OK


fn _root_node(cols: Int, var_kind: List[Int]) -> _Node:
    """The root box: nothing bounded, except a binary variable's promised `x <= 1`."""
    var lo = List[Float64]()
    var has_lo = List[Bool]()
    var up = List[Float64]()
    var has_up = List[Bool]()
    for j in range(cols):
        # `x >= 0` is `lp_solve`'s variable convention and costs no row, so the root's
        # lower bounds are all absent rather than all zero.
        lo.append(0.0)
        has_lo.append(False)
        if var_kind[j] == VAR_BINARY:
            up.append(1.0)
            has_up.append(True)
        else:
            up.append(0.0)
            has_up.append(False)
    return _Node(False, 0.0, 0, lo^, has_lo^, up^, has_up^)


fn _augment(
    a: List[Float64],
    rows: Int,
    cols: Int,
    senses: List[Int],
    rhs: List[Float64],
    node: _Node,
) -> _Program:
    """The caller's program with this node's active bounds appended as unit rows.

    A lower bound of 0 or less adds no row: `lp_solve` already enforces `x >= 0`, and a
    redundant row is a row whose dual and slack a reader would have to explain.
    """
    var out_a = a.copy()
    var out_senses = senses.copy()
    var out_rhs = rhs.copy()
    var total = rows
    for j in range(cols):
        if node.has_lo[j] and node.lo[j] > 0.0:
            for k in range(cols):
                if k == j:
                    out_a.append(1.0)
                else:
                    out_a.append(0.0)
            out_senses.append(SENSE_GE)
            out_rhs.append(node.lo[j])
            total += 1
        if node.has_up[j]:
            for k in range(cols):
                if k == j:
                    out_a.append(1.0)
                else:
                    out_a.append(0.0)
            out_senses.append(SENSE_LE)
            out_rhs.append(node.up[j])
            total += 1
    return _Program(total, out_a^, out_senses^, out_rhs^)


fn _child(node: _Node, index: Int, bound: Float64, upper: Bool, value: Float64) -> _Node:
    """`node` with `x_index` bounded by `value`, TIGHTENING any inherited bound.

    Tightening rather than appending keeps the per-node LP at `rows + 2*cols`, and it means
    a bound that is already stronger than the branch survives — dropping to the branch value
    would LOOSEN the child, which is how a node's LP comes back with a bound that is not
    valid for its own subtree.
    """
    var lo = node.lo.copy()
    var has_lo = node.has_lo.copy()
    var up = node.up.copy()
    var has_up = node.has_up.copy()
    if upper:
        if not has_up[index] or value < up[index]:
            up[index] = value
            has_up[index] = True
    else:
        if not has_lo[index] or value > lo[index]:
            lo[index] = value
            has_lo[index] = True
    return _Node(True, bound, node.depth + 1, lo^, has_lo^, up^, has_up^)


fn _verify_row_budget(
    row: List[Float64], x: List[Float64], rhs: Float64, var_kind: List[Int],
    feasibility_tol: Float64, integrality_tol: Float64,
) -> Float64:
    """How far row `i`'s activity may sit past `b_i` and still be the SNAP rather than a defect.

    The judged quantity is `A_i x - b_i` for ONE row, so every term here is built from that
    row's own magnitudes and from nothing else. Three terms, each with a distinct meaning:

      * `feasibility_tol` — the caller's ABSOLUTE allowance, used absolutely. It is never a
        multiplier of anything;
      * `LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * (|b_i| + Σ_j |a_ij x_j|)` — the ROUNDING the
        recomputed `vec_dot` and the subtraction can carry at this row's own magnitude. The
        activity term is here because `value` is recomputed from a snapped point, so the sum's
        own addends are what round; the constants are IMPORTED from `optimization.linear`, so
        a row this module calls satisfied is a row `linear` calls satisfied;
      * `integrality_tol * Σ_{j integral} |a_ij|` — the SNAP, and the only reason this budget
        is looser than `linear._lp_row_gap_budget`. `_nearest_int` moves each integer or
        binary coordinate by at most `integrality_tol`, so this is the exact displacement
        bound for this row's activity. Continuous columns are EXCLUDED because they are copied
        through unchanged: including them added `integrality_tol * |a_ij|` of allowance per
        column that cannot have moved at all, which at `|a_ij| = 1e9` is a full unit.

    Two forms this is deliberately NOT — both shipped in this package and both returned a
    confident wrong answer (see `linear._lp_row_gap_budget` for the executed cases):

      * `feasibility_tol * (1 + Σ_i |b_i|)`: an aggregate over rows. One unrelated large-rhs
        row lifts every other row's threshold without limit;
      * `feasibility_tol * (1 + |b_i|)`: what this function replaces. Per-row and still wrong
        twice over — the `1 +` makes it an ABSOLUTE floor of `feasibility_tol` at a scale the
        caller never chose, and `feasibility_tol` as the RELATIVE multiplier is 4.5 MILLION
        ulps at magnitude 1e9. MEASURED: a point violating `x <= 1e9` by a full unit came back
        `MODEL_OK` from `_verify_point`, so the one check standing between a snapped vertex and
        an incumbent that prunes the real optimum passed it.

    A non-finite relative term contributes 0.0 rather than `inf`: coefficients near 1e308 make
    `Σ_j |a_ij x_j|` overflow, and an infinite budget switches its own test off — `violation >
    inf` is False for every violation, so the row would be certified satisfied without being
    read. The caller's absolute allowance survives that path; the relative terms do not.
    """
    var activity_scale = fabs(rhs)
    var snap_scale: Float64 = 0.0
    for j in range(len(row)):
        var coefficient = fabs(row[j])
        activity_scale += coefficient * fabs(x[j])
        if var_kind[j] != VAR_CONTINUOUS:
            snap_scale += coefficient
    var budget = feasibility_tol
    if budget < 0.0:
        budget = 0.0
    var rounding = LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * activity_scale
    if _finite(rounding) and rounding > 0.0:
        budget += rounding
    var snap = integrality_tol * snap_scale
    if _finite(snap) and snap > 0.0:
        budget += snap
    if not _finite(budget) or budget < 0.0:
        return 0.0
    return budget


fn _verify_point(
    a: List[Float64], rows: Int, cols: Int, senses: List[Int], rhs: List[Float64],
    x: List[Float64], var_kind: List[Int], feasibility_tol: Float64,
    integrality_tol: Float64,
) -> Int:
    """`MODEL_OK` when `x` satisfies the CALLER's rows, allowing for the snap.

    The row budget is `_verify_row_budget`, which states what each of its three terms is for
    and which two forms it refuses. `var_kind` is taken rather than assumed because the snap
    term is a statement about the columns `milp_solve` actually snapped, and a continuous
    column is not one of them.

    `sense_violation` is the frozen-side comparison, reused instead of three inline
    branches, and its `MODEL_VIOLATION_ABSENT` return is handled as an arithmetic failure —
    0.0 would read as "satisfied", which is the confusion the whole package removes.
    """
    if len(var_kind) != cols:
        return MODEL_ERR_LENGTH_MISMATCH
    for j in range(cols):
        if not _finite(x[j]):
            return MODEL_ERR_NON_FINITE_VALUE
        if x[j] < -feasibility_tol:
            # `x >= 0` is the variable convention, so it is verified like any other row.
            return LP_INFEASIBLE
    for i in range(rows):
        var row = List[Float64]()
        for j in range(cols):
            row.append(a[i * cols + j])
        var value = vec_dot(row, x)
        if not _finite(value):
            return MODEL_ERR_NON_FINITE_VALUE
        var tol = _verify_row_budget(
            row, x, rhs[i], var_kind, feasibility_tol, integrality_tol
        )
        var violation = sense_violation(value, senses[i], rhs[i], tol)
        if violation == MODEL_VIOLATION_ABSENT:
            return MODEL_ERR_NON_FINITE_VALUE
        if violation > 0.0:
            return LP_INFEASIBLE
    return MODEL_OK


# ── the driver ────────────────────────────────────────────────────────────────


fn milp_solve(
    c: List[Float64], constant: Float64, a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool, var_kind: List[Int],
    max_nodes: Int, max_iterations: Int, feasibility_tol: Float64,
    optimality_tol: Float64, integrality_tol: Float64,
) -> MILPResult:
    """Branch and bound for `c·x + constant` over `A x {senses} b`, `x >= 0`, `x_j` integral.

    `var_kind[j]` is `model.VAR_CONTINUOUS`, `VAR_INTEGER` or `VAR_BINARY`; a binary
    variable gets its `x_j <= 1` bound row here, and every other bound is a row the caller
    wrote. `maximize` is a flag, never a negated objective vector, so the returned
    `objective` and `best_bound` are in the sense the caller asked for.

    The parameters are packed several per line ON PURPOSE: `mojo_inventory` follows a
    signature at most nine lines past its first, and a one-per-line signature with
    fourteen parameters never closes inside that window — the function is then dropped
    from the runtime contract with no error anywhere.
    """
    var defect = _milp_input_defect(
        c, constant, a, rows, cols, senses, rhs, var_kind, max_nodes,
        max_iterations, feasibility_tol, optimality_tol, integrality_tol,
    )
    if defect != MODEL_OK:
        return _milp_rejected(defect, 0, 0)

    var n_integer = 0
    var n_binary = 0
    for j in range(cols):
        if var_kind[j] == VAR_INTEGER:
            n_integer += 1
        elif var_kind[j] == VAR_BINARY:
            n_binary += 1

    var stack = List[_Node]()
    stack.append(_root_node(cols, var_kind))

    var explored = 0
    var pruned = 0
    var infeasible_nodes = 0
    var integral_nodes = 0
    var branched = 0
    var abandoned = 0
    var max_depth = 0
    var lp_iterations = 0

    var has_incumbent = False
    var incumbent_min: Float64 = 0.0
    var incumbent_objective: Float64 = 0.0
    var incumbent = List[Float64]()

    var has_relaxation = False
    var relaxation_objective: Float64 = 0.0
    var relaxation_status = MODEL_OK

    # The bound over nodes that were never explored. `open_unknown` is the honest state for
    # a subtree whose relaxation never produced a number: it makes the global bound ABSENT
    # rather than optimistic.
    var has_open = False
    var open_min: Float64 = 0.0
    var open_unknown = False

    var stop_status = MODEL_OK
    var abort_status = MODEL_OK

    while len(stack) > 0:
        if explored >= max_nodes:
            stop_status = MILP_NODE_LIMIT
            break
        var node = stack.pop()
        if node.depth > max_depth:
            max_depth = node.depth
        if node.depth > MILP_MAX_DEPTH or len(stack) + 2 > MILP_MAX_STACK:
            # Abandoned, not pruned: its bound is still valid for its subtree, so it counts
            # towards `best_bound` and the search is reported truncated.
            #
            # The second test bounds LIVE MEMORY explicitly. Under the depth-first invariant
            # (see `MILP_MAX_STACK`) it cannot fire before the depth test does, and it is
            # kept anyway so the stack has a stated ceiling rather than one that depends on
            # the push/pop discipline staying exactly as it is. It is checked here, before
            # the node is classified, so both census identities keep holding: the node
            # becomes open, exactly as at the depth limit.
            stop_status = MILP_DEPTH_LIMIT
            abandoned += 1
            if not node.has_bound:
                open_unknown = True
            elif not has_open or node.bound < open_min:
                open_min = node.bound
                has_open = True
            continue
        if (
            node.has_bound
            and has_incumbent
            and node.bound > incumbent_min - optimality_tol
        ):
            # Pruned on the bound it inherited. Checked at POP rather than at push, because
            # the incumbent may have improved in between and this is the cheaper test.
            pruned += 1
            explored += 1
            continue

        var program = _augment(a, rows, cols, senses, rhs, node)
        var lp = lp_solve(
            c, constant, program.a, program.rows, cols, program.senses, program.rhs,
            maximize, max_iterations, feasibility_tol, optimality_tol,
        )
        lp_iterations += lp.iterations
        if node.depth == 0:
            relaxation_status = lp.status
            if lp.status == LP_OPTIMAL and lp.has_objective:
                has_relaxation = True
                relaxation_objective = lp.objective

        if lp.status == LP_INFEASIBLE:
            infeasible_nodes += 1
            explored += 1
            continue
        if lp.status != LP_OPTIMAL:
            # No bound for this subtree, so no honest global bound either. The node is
            # counted OPEN and not explored: its subtree is exactly what is unaccounted for.
            if lp.status == LP_UNBOUNDED:
                abort_status = MILP_RELAXATION_UNBOUNDED
            else:
                abort_status = MILP_RELAXATION_FAILED
            relaxation_status = lp.status
            open_unknown = True
            abandoned += 1
            break

        var bound_min = minimization_value(lp.objective, maximize)
        if has_incumbent and bound_min > incumbent_min - optimality_tol:
            pruned += 1
            explored += 1
            continue

        var choice = branch_choice(lp.x, var_kind, integrality_tol)
        if choice.status != MODEL_OK:
            # `lp.x` is `cols` long and finite by construction, so the only reachable
            # status is a coordinate past the integer grid: no branch narrows anything
            # there, and pretending otherwise loops to the node limit.
            abort_status = MILP_RELAXATION_FAILED
            relaxation_status = choice.status
            open_unknown = True
            abandoned += 1
            break

        if not choice.has_branch:
            integral_nodes += 1
            explored += 1
            var snapped = List[Float64]()
            for j in range(cols):
                if var_kind[j] == VAR_CONTINUOUS:
                    snapped.append(lp.x[j])
                else:
                    snapped.append(_nearest_int(lp.x[j]))
            var verdict = _verify_point(
                a, rows, cols, senses, rhs, snapped, var_kind,
                feasibility_tol, integrality_tol,
            )
            if verdict != MODEL_OK:
                abort_status = MILP_SNAP_INFEASIBLE
                relaxation_status = verdict
                open_unknown = True
                break
            # Recomputed at the SNAPPED point, not read off the relaxation: an objective
            # that belongs to a slightly different point than the returned `x` is an
            # inconsistency the caller cannot see.
            var value = linear_form_value(c, constant, snapped)
            if not value.has_value:
                abort_status = MILP_RELAXATION_FAILED
                relaxation_status = value.status
                open_unknown = True
                break
            var candidate_min = minimization_value(value.value, maximize)
            if not has_incumbent or candidate_min < incumbent_min:
                has_incumbent = True
                incumbent_min = candidate_min
                incumbent_objective = value.value
                incumbent = snapped^
            continue

        branched += 1
        explored += 1
        # Floor child pushed first, so the CEIL child is popped first: the larger value is
        # where an incumbent usually lives in a select-or-produce formulation, and an early
        # incumbent is what makes the bound prune anything.
        stack.append(
            _child(node, choice.var_index, bound_min, True, choice.floor_bound)
        )
        stack.append(
            _child(node, choice.var_index, bound_min, False, choice.ceil_bound)
        )

    for i in range(len(stack)):
        ref pending = stack[i]
        if not pending.has_bound:
            open_unknown = True
        elif not has_open or pending.bound < open_min:
            open_min = pending.bound
            has_open = True
    var open_nodes = len(stack) + abandoned

    var complete = abort_status == MODEL_OK and stop_status == MODEL_OK
    var has_bound = False
    var global_min: Float64 = 0.0
    if abort_status == MODEL_OK:
        if complete:
            # The tree is exhausted, so the incumbent IS the bound. With no incumbent the
            # program is infeasible and there is no bound on an empty feasible set.
            if has_incumbent:
                has_bound = True
                global_min = incumbent_min
        elif has_open and not open_unknown:
            has_bound = True
            global_min = open_min
            if has_incumbent and incumbent_min < global_min:
                global_min = incumbent_min

    var has_gap = has_incumbent and has_bound
    var gap: Float64 = 0.0
    if has_gap:
        gap = incumbent_min - global_min
        if gap < 0.0:
            # Only reachable from the pruning tolerance; a magnitude is never negative.
            gap = 0.0

    var status = MILP_OPTIMAL
    var proven = False
    if abort_status != MODEL_OK:
        status = abort_status
    elif not has_incumbent:
        if complete:
            status = MILP_INFEASIBLE
        else:
            status = stop_status
    elif complete or (has_gap and gap <= optimality_tol):
        # A truncated search whose surviving bounds close the gap HAS proved optimality.
        # `search_complete` still reports that the tree was not exhausted, so the two facts
        # stay separable.
        proven = True
    else:
        status = stop_status

    var answer = List[Float64]()
    if has_incumbent:
        answer = incumbent.copy()
    var reported_bound: Float64 = 0.0
    if has_bound:
        reported_bound = minimization_value(global_min, maximize)
    var reported_objective: Float64 = 0.0
    if has_incumbent:
        reported_objective = incumbent_objective

    return MILPResult(
        status,
        has_incumbent,
        proven,
        complete,
        has_incumbent,
        reported_objective,
        has_bound,
        reported_bound,
        has_gap,
        gap,
        has_relaxation,
        relaxation_objective,
        relaxation_status,
        cols,
        rows,
        n_integer,
        n_binary,
        explored,
        pruned,
        infeasible_nodes,
        integral_nodes,
        branched,
        open_nodes,
        max_depth,
        lp_iterations,
        answer^,
    )


fn milp_solve_default(
    c: List[Float64], a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool,
    var_kind: List[Int], max_nodes: Int,
) -> MILPResult:
    """`milp_solve` with no objective constant and `model.mojo`'s default policy.

    `max_nodes` stays explicit even here: it is the termination guarantee, and a default
    for it would be a silent cap on how much of the tree a caller's answer covers.
    """
    return milp_solve(
        c, 0.0, a, rows, cols, senses, rhs, maximize, var_kind, max_nodes,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
        DEFAULT_INTEGRALITY_TOL,
    )


fn _declared_box(
    n_vars: Int, var_kind: List[Int], var_lower: List[Float64],
    var_upper: List[Float64], var_flags: List[Int],
) -> _Node:
    """The declared variable box as a `_Node`, so `_augment` turns it into rows.

    Reuses the search's own bound-to-row conversion rather than writing a second one: the
    node this returns is fed to `_augment`, which is the ONE place in this module that emits
    a bound row, so the arena path and every branch node cannot disagree about what a bound
    means. Callers must have validated the four columns as parallel and `n_vars` long first.

    A binary variable's `x <= 1` is dropped here when the declared upper bound is 1, because
    `_root_node` adds that row from the KIND: emitting it twice would give the LP a
    duplicated row whose dual and slack a reader would have to explain away.
    """
    var lo = List[Float64]()
    var has_lo = List[Bool]()
    var up = List[Float64]()
    var has_up = List[Bool]()
    for j in range(n_vars):
        var flags = var_flags[j]
        lo.append(var_lower[j])
        has_lo.append(has_lower_bound(flags))
        var declared_up = has_upper_bound(flags)
        if declared_up and var_kind[j] == VAR_BINARY and var_upper[j] >= 1.0:
            declared_up = False
        up.append(var_upper[j])
        has_up.append(declared_up)
    return _Node(False, 0.0, 0, lo^, has_lo^, up^, has_up^)


fn _box_row_count(box: _Node, n_vars: Int) -> Int:
    """How many rows `_augment` will emit for `box`, or -1 when it cannot be expressed.

    Counted BEFORE anything is appended, because `_augment` allocates `cols` cells per row
    it emits: at the widest `cols` the area check admits, a box that needs two rows per
    variable is `2*cols*cols` cells, which is an allocation bomb even though every
    individual dimension is legal. The count feeds the area test, and only then is the
    program built.

    -1 is the box this solver cannot represent at all: `lp_solve`'s variable convention is
    `x >= 0`, so a lower bound below zero, or a variable with no lower bound at all, states
    a feasible region larger than any program this search can build. Clipping it to 0 would
    solve a SMALLER program and hand back its optimum as `proven_optimal`.
    """
    var total = 0
    for j in range(n_vars):
        if not box.has_lo[j]:
            return -1
        var lower = box.lo[j]
        if lower < 0.0:
            return -1
        if lower > 0.0:
            # `x >= 0` is implicit in `lp_solve`, so a lower bound of exactly 0 costs no row.
            total += 1
        if box.has_up[j]:
            total += 1
    return total


# THE PACKING OF THE NEXT SIGNATURE IS LOAD-BEARING. `mojo_inventory` matches a signature
# inside a nine-line lookahead window and SILENTLY drops the function from the runtime contract
# and from dispatch when the closing paren lands outside it — no error, no warning, the
# per-module function count just comes out one lower. At three or four parameters per line this
# closed on exactly the ninth line, so one added parameter or one reflow would have
# unregistered the package's widest driver. Six parameters per line keeps three lines of
# headroom. Do not expand it back out to one parameter per line.
fn milp_from_arenas(
    obj_ops: List[Int], obj_values: List[Float64], obj_var_idx: List[Int], obj_lefts: List[Int], obj_rights: List[Int], obj_extras: List[Int],
    obj_root: Int, con_ptr: List[Int], con_roots: List[Int], con_senses: List[Int], con_rhs: List[Float64], con_ops: List[Int],
    con_values: List[Float64], con_var_idx: List[Int], con_lefts: List[Int], con_rights: List[Int], con_extras: List[Int], n_vars: Int,
    var_kind: List[Int], var_lower: List[Float64], var_upper: List[Float64], var_flags: List[Int], maximize: Bool, max_nodes: Int,
) -> MILPResult:
    """Solve a general model's arenas as a mixed-integer program, box included.

    The columns are exactly `model.ModelFlat`'s — including the four VARIABLE columns, which
    is the point — so a model built by `model.linear_model_flat` or by any caller who wrote
    arenas reaches this solver without a second wire format. `linear.lp_from_arenas` does
    the expression extraction and every structural guard (it delegates those to
    `model.model_validate`), so a nonlinear constraint arrives here as a status naming the
    row, the node and the variable rather than as a linearised program about a different
    problem.

    THE BOUNDS ARE NOT OPTIONAL, and this signature is why. `linear.lp_from_arenas` builds
    its own variable block with `var_lower = 0`, `var_upper = 0` and `VAR_FLAG_HAS_LOWER`
    for every variable and never reads a caller's, because an LP arena states expressions
    and that module's convention is `x >= 0`. So an earlier version of this function, which
    took `var_kind` and nothing else, solved the caller's rows with the caller's box THROWN
    AWAY: a model stating `x <= 3` and a row `x <= 10`, maximised, came back `objective 10,
    x = [10]`, `MILP_OPTIMAL`, `proven_optimal = True` — the bound-free relaxation's answer
    wearing the declared model's status. Only `VAR_BINARY` survived, because `_root_node`
    re-adds its `x <= 1` from the kind. The four columns are taken here so the program that
    is solved is the program that was declared.

    Bounds become ROWS, by this package's convention that a bound the solver hides is a
    bound the caller cannot see, and they are therefore counted in `n_constraints`: the
    reported count is the row count of the program that was solved, `n_constraints` from the
    arenas plus one row per bound that needed one. A lower bound of exactly 0 needs none
    (`x >= 0` is implicit) and a binary variable's `x <= 1` needs none (its kind already
    adds it), so the documented `linear_model_flat` shape with an all-zero lower column and
    no upper flags reports exactly the arena row count, unchanged.

    The block itself is validated by `model.variables_validate_flat` — the frozen check, not
    a second copy — so non-finite bounds, a crossed pair, a binary outside `[0, 1]` and an
    integer range holding no integer are named rather than solved around. `VAR_FLAG_HAS_START`
    is masked off first: there is no warm-start column in this signature, so honouring the
    bit would validate a start the caller never sent, and this search takes no warm start
    anyway (an unverified incumbent prunes the true optimum).
    """
    var matrix = lp_from_arenas(
        obj_ops, obj_values, obj_var_idx, obj_lefts, obj_rights, obj_extras, obj_root,
        con_ptr, con_roots, con_senses, con_rhs,
        con_ops, con_values, con_var_idx, con_lefts, con_rights, con_extras, n_vars,
    )
    if matrix.status != MODEL_OK:
        return _milp_rejected(matrix.status, matrix.n_vars, matrix.n_constraints)

    var n = matrix.n_vars
    var rows = matrix.n_constraints
    if (
        len(var_kind) != n
        or len(var_lower) != n
        or len(var_upper) != n
        or len(var_flags) != n
    ):
        # Checked before ANY of the four is indexed: they are indexed in lockstep below, and
        # a read past a List end is an uncatchable process crash rather than an exception.
        return _milp_rejected(MODEL_ERR_LENGTH_MISMATCH, n, rows)
    var flag_defect = variables_defect_flat(var_lower, var_upper, var_kind, var_flags)
    if flag_defect != MODEL_OK:
        # Validated on the flags the CALLER sent, before the start bit is masked: an unknown
        # bit must be rejected, not quietly dropped by the mask.
        return _milp_rejected(flag_defect, n, rows)

    var box_flags = List[Int]()
    var no_starts = List[Float64]()
    for j in range(n):
        box_flags.append(var_flags[j] & VAR_FLAG_BOXED)
        no_starts.append(0.0)
    var block = variables_validate_flat(
        var_lower, var_upper, var_kind, box_flags, no_starts, DEFAULT_INTEGRALITY_TOL
    )
    if block.status != MODEL_OK:
        return _milp_rejected(block.status, n, rows)

    var box = _declared_box(n, var_kind, var_lower, var_upper, box_flags)
    var box_rows = _box_row_count(box, n)
    if box_rows < 0:
        return _milp_rejected(MILP_BOX_BELOW_ZERO, n, rows)
    if n > 0:
        # The area budget again, now including the box rows. `lp_from_arenas` sized `rows`
        # alone and `milp_solve` allows a further `2*cols` for the branch bounds, so the box
        # has to fit between them. DIVISION, and `budget - 2*n - box_rows` may go negative,
        # which correctly rejects rather than wrapping into a huge allowance.
        var budget = LP_MAX_TABLEAU_CELLS // n
        if rows > budget - 2 * n - box_rows:
            return _milp_rejected(MODEL_ERR_DIMENSION_TOO_LARGE, n, rows)

    var program = _augment(matrix.a, rows, n, matrix.senses, matrix.rhs, box)
    return milp_solve(
        matrix.c, matrix.constant, program.a, program.rows, n,
        program.senses, program.rhs, maximize, var_kind, max_nodes,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
        DEFAULT_INTEGRALITY_TOL,
    )


fn milp_knapsack(
    values: List[Float64], weights: List[Float64], capacity: Float64, max_nodes: Int
) -> MILPResult:
    """Maximise `Σ values[j] x_j` subject to `Σ weights[j] x_j <= capacity`, `x` binary.

    The frozen `combinatorial.knapsack_01_value` is the exact DP for this shape and is NOT
    called here, deliberately. It takes `List[Int]` weights and values, so it cannot answer
    a knapsack with real-valued prices at all, and it returns a bare `Int` with no status —
    `0` for an empty item list and `0` for a capacity it could not fill are the same
    return. Dispatching to it for the integer case was rejected for the reason
    `optimization.linear` gives for not dispatching to `lp_solve_2var`: a second code path
    for a special shape is how a divergence between the two ships unnoticed. The suite
    asserts that this search and that DP agree instead, which is evidence rather than a
    tautology because one is a table over weights and the other is a tree over relaxations.
    """
    if len(values) != len(weights):
        return _milp_rejected(MODEL_ERR_LENGTH_MISMATCH, 0, 0)
    var n = len(values)
    var senses = List[Int]()
    senses.append(SENSE_LE)
    var rhs = List[Float64]()
    rhs.append(capacity)
    var var_kind = List[Int]()
    for _ in range(n):
        var_kind.append(VAR_BINARY)
    return milp_solve(
        values, 0.0, weights, 1, n, senses^, rhs^, True, var_kind^,
        max_nodes, DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL,
        DEFAULT_OPTIMALITY_TOL, DEFAULT_INTEGRALITY_TOL,
    )
