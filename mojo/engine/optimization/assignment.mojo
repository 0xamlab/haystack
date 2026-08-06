"""
optimization.assignment — the optimal assignment, plus the duals that prove it optimal.

Why this file exists
--------------------
`combinatorial.assignment_greedy` is the only assignment kernel in the tree, and it is
greedy: "for each row, pick cheapest available column". Nothing at the call site says so.
Its answer is a `List[Int]` that looks exactly like an optimal assignment and is routinely
not one — on the rank-1 matrix `c[i][j] = (i+1)(j+1)` it returns 1+4+9 = 14 where the
optimum is 3+4+3 = 10, and on a matrix with one forbidden-by-cost pairing it walks the
last row straight into that pairing (1 + 3 + 1e9 against an optimum of 10). It also
reports "no column was available" as `-1` inside the same list, so a partial matching and
a complete one are the same return type, and it computes no cost, so a caller cannot even
compare two of its own answers without writing the sum itself.

The other assignment surface is `operations_research.assignment_cost_3(c1, c2, c3)`, which
was grepped for and is worth naming precisely: it is `c1 + c2 + c3`. It takes no matrix,
no assignment and no dimension, it is fixed at three tasks, and it cannot check that the
three costs came from distinct tasks — "costs already matched" is a comment, not a
verified property. `assignment_cost_of` here is the general form of it: a matrix, an
assignment vector, a range check, a distinctness check and a `perfect` flag.

So this module adds the exact solve — Hungarian / Jonker-Volgenant shortest augmenting
paths with dual potentials — and keeps the frozen greedy in the loop in all three of the
roles it is actually good for: a warm start, an upper bound, and an independent oracle.

The frozen greedy is REUSED, three times, not reimplemented
-----------------------------------------------------------
1. *Warm start.* After the row reduction (below), the frozen greedy is called on the
   reduced matrix and every pair it returns that is TIGHT (reduced cost exactly 0.0, pair
   allowed, worker still free) becomes part of the initial matching. That is the classical
   JV "greedy augmenting row reduction" initialisation, and it is exactly what the frozen
   kernel already computes: a row shift does not move a row's argmin, so greedy on the
   reduced matrix is greedy on the original. `Assignment.warm_started` reports how many
   pairs it contributed and `Assignment.augmentations` how many rows the exact solver
   still had to route — on a matrix greedy happens to solve, `augmentations` is 0.
2. *Upper bound.* Its total cost travels out as `greedy_cost`, and `improvement` is
   `greedy_cost - total_cost`, which is how much the greedy call site was losing.
3. *Oracle.* An optimal cost can never exceed a feasible one, so `greedy_cost < total_cost`
   is a proof that this solver is wrong. That comparison is made here, not only in the
   test, and it returns `ASSIGN_ERR_BOUND_VIOLATED` rather than a number.

A pair the frozen greedy returns is never trusted: its columns are re-checked for range,
for distinctness and against the mask, because it knows nothing about the mask and reports
"nothing available" as `-1` in the same slot as a real column.

Rows are agents, columns are tasks, and the COLUMNS are what must be saturated
-----------------------------------------------------------------------------
`cost` is a flat row-major matrix of `rows * cols` cells: `cost[i * cols + j]` is the cost
of agent `i` doing task `j`. A complete answer assigns every task to a distinct agent, so
`cols > rows` is refused as `ASSIGN_ERR_FEWER_AGENTS_THAN_TASKS` rather than answered with
a matching that leaves tasks undone. The transpose is not taken silently: which side must
be saturated is the caller's semantics, and guessing it is precisely how a partial matching
gets reported as complete.

`perfect` is therefore "every task assigned", agents may be idle, and `col_of_row[i] = -1`
is an idle agent — a real answer for `rows > cols`, not a failure.

A non-perfect matching is not an assignment
-------------------------------------------
When no perfect matching exists the status is `ASSIGN_ERR_NO_PERFECT_MATCHING` and every
list comes back empty. Returning the partial matching would be the frozen greedy's failure
mode with extra steps: a `List[Int]` that reads as an assignment and is not one. The two
ways it can happen are both detected: a task with no allowed agent at all (caught in the
row reduction, before any min over an empty set), and a Hall violation that only the
augmenting search can see (k tasks whose allowed agents number fewer than k — the search
exhausts its alternating tree without reaching a free agent, which is the König/Hall
certificate).

A forbidden pairing is a Bool, never a big number and never an infinity
----------------------------------------------------------------------
`assignment_solve_masked` takes `allowed: List[Bool]`, parallel to `cost`. Encoding "this
agent cannot do this task" as a huge cost is the standard trick and it is wrong in two
distinct ways: big-M enters the arithmetic (the duals, the reduced costs, and the total,
where 1e300 + 1e300 overflows and the reported optimum is `inf`), and it silently becomes
*choosable* the moment the alternative is bigger, so an infeasible problem returns a
plausible assignment. `+inf` is worse: `inf - inf` is NaN in the very first reduced-cost
subtraction. This mirrors `model.mojo`'s decision that a free variable is a flag rather
than an infinite bound. A non-finite cost is rejected outright
(`ASSIGN_ERR_NON_FINITE_COST`); the huge-but-finite cost is honoured as a real cost and
simply never chosen when an alternative is cheaper, which is what the test asserts.

Internally the frozen greedy needs *some* number in a forbidden cell, and the one used is
`ASSIGN_FORBIDDEN_SENTINEL = 1e308` — not a hopefully-large constant but exactly
`combinatorial.assignment_greedy`'s own initial `best_cost`, which it compares with a
strict `<`. So a forbidden cell is unselectable by the frozen kernel's own convention.
Its verdict is filtered against the real mask anyway.

The duals, and why there is no column reduction
-----------------------------------------------
`u` is one potential per agent (row), `v` one per task (column), and they satisfy
`u[i] + v[j] <= cost[i][j]` for every allowed pair with EQUALITY on every chosen pair, and
`u[i] <= 0` for EVERY agent. That last one is not decoration: the agent constraint is
`sum_j x[i][j] <= 1`, so its dual variable is sign-constrained, and without it the bound
`cost . x >= sum(u) + sum(v)` fails for any alternative matching that idles an agent
carrying a positive potential — which is exactly how a suboptimal matching acquires a dual
objective that matches its own cost. Together they are the complementary-slackness
certificate; `assignment_dual_check` recomputes all three from the outside, and
`sum(u) + sum(v)` equals the total cost.

The initialisation is a row reduction over TASKS only — `v[j] = min_i cost[i][j]` over
allowed agents — and the agent potentials start at 0.0. Doing the usual second (column)
reduction was tried and rejected: it makes idle agents carry a positive potential, and for
a rectangular problem that breaks the optimality proof. The agent capacity constraint is
`sum_j x[i][j] <= 1`, so complementary slackness requires an idle agent's potential to be
exactly 0. This implementation gets that structurally: an agent's potential is only ever
touched when its column is scanned, a scanned column is always a matched column (the phase
stops before marking the free column it ends on), and a matched column never becomes
free. `DualCheck.n_idle_nonzero` asserts it from the outside, and a nonzero count refuses
certification. It is a strictly weaker condition than `u[i] <= 0` and does not stand in for
it: an idle agent at exactly 0.0 says nothing about a MATCHED agent at +4.0, which is why
`DualCheck.n_agent_sign_violations` counts that separately. Costs may be negative, which is
why the row reduction is done at all:
without it the reduced costs can be negative and the shortest-path search is invalid.

Every tolerance here is sized by the ONE quantity it judges
-----------------------------------------------------------
The certificate is a set of per-pair and per-agent statements, so each one is judged against
its own budget: the caller's ABSOLUTE tolerance plus a ROUNDING allowance of
`1024 * DBL_EPSILON * (the magnitude of that comparison's own terms)`. A reduced cost
`c_ij - u_i - v_j` is judged against `|c_ij| + |u_i| + |v_j|`, an agent potential against the
terms of the pair it is tight on, and the greedy-versus-optimal bound against those two
totals. Nothing is scaled by the matrix.

The form that was here before was `DEFAULT_FEASIBILITY_TOL * (1 + max_ij |c_ij|)`, and it was
three of rule 4b's four spellings at once: a MAX over every cell, a 1.0 floor, and the
caller's tolerance used as the RELATIVE multiplier where only DBL_EPSILON belongs. Executed:
`assignment_dual_check(cost = (0.0, 1e9, 0.5, 1e9), rows = 2, cols = 2,
col_of_row = (1, 0), u = (0, 0), v = (0.5, 1e9))` returned `certified = True` for a matching
costing 1e9 + 0.5 whose optimum is 1e9, because the threshold was `1e-9 * (1 + 1e9) = 1.0`
and the reduced cost of the unchosen pair (0, 0) is -0.5. One cell of 1e9 — an ordinary cost
in currency units — bought a full unit of slack for every comparison in the matrix, and
`certified` is the field a caller checks INSTEAD of looking. 0.5 at magnitude 0.5 is not a
rounding artefact; at magnitude 1e9 the real allowance is 2.3e-4.

`max_dual_violation` and `max_tight_gap` are still the worst violation and gap in the
caller's own units, and they are reported and never thresholded, for the same reason
`linear.LpResult.infeasibility` is: a max over pairs is a summary, not a quantity any single
budget can judge.

Why a dense scan and not a heap
-------------------------------
Each phase is a Dijkstra over reduced costs, run as a dense O(agents) scan per settled
column. `heap.heap_push_min` was rejected: it stores a bare `Float64` with no payload slot
for the column id and it permutes its list internally, so column identity cannot ride
along (`graph_analytics.adjacency` documents the same limitation and pays for a hash-index
sidecar to work around it). `graph_analytics.adjacency.graph_csr_dijkstra` was rejected
too: the search runs on REDUCED costs that change every phase, the path must alternate
along matched edges, and the dual update needs the per-column shortest-path labels that a
CSR traversal does not return — so building a CSR per phase would cost the dense scan it
was supposed to replace and still not answer the question. The matrix is dense already, so
the scan is the same order as reading the input.

Ceilings and shape
------------------
`sparse_numerics.csr.dims_fit` is the shape guard and `MAX_CSR_DIM` the ceiling, both
imported rather than restated: `rows * cols == len(cost)` is a wrapping 64-bit multiply
(`3 * 6148914691236517206 == 2`) and therefore not a bound at all, and this solver
allocates one slot per agent and per task regardless of how many pairs matter, which is
what that ceiling exists to cap. Sums are `numerical_stability.kahan_sum`, so a total over
mixed magnitudes (1e9 next to 1) does not lose the small terms.

Signatures are packed several parameters per line ON PURPOSE: `mojo_inventory` follows a
signature at most nine lines past its first, so a one-parameter-per-line signature with
seven parameters is silently dropped from the runtime contract with no error anywhere.
"""
from std.math import abs as fabs

from combinatorial import assignment_greedy
from numerical_stability import kahan_sum
from optimization.model import DEFAULT_FEASIBILITY_TOL, model_finite as _finite
from sparse_numerics.csr import MAX_CSR_DIM, dims_fit

# ── status codes ──────────────────────────────────────────────────────────────
# One code per outcome. "Optimal", "there are not enough agents", "no perfect matching
# exists", "the search did not terminate" and "the duals do not certify this answer" are
# five different things, and collapsing any pair of them is how a partial matching gets
# consumed as an assignment.

comptime ASSIGN_OK: Int = 0
comptime ASSIGN_ERR_SHAPE: Int = 1
comptime ASSIGN_ERR_DIMENSION_TOO_LARGE: Int = 2
comptime ASSIGN_ERR_LENGTH_MISMATCH: Int = 3
comptime ASSIGN_ERR_NON_FINITE_COST: Int = 4
comptime ASSIGN_ERR_FEWER_AGENTS_THAN_TASKS: Int = 5
comptime ASSIGN_ERR_NO_PERFECT_MATCHING: Int = 6
comptime ASSIGN_ERR_INDEX: Int = 7
comptime ASSIGN_ERR_DUPLICATE: Int = 8
comptime ASSIGN_ERR_OVERFLOW: Int = 9
comptime ASSIGN_ERR_ITERATION_LIMIT: Int = 10
comptime ASSIGN_ERR_CERTIFICATE: Int = 11
comptime ASSIGN_ERR_BOUND_VIOLATED: Int = 12
comptime ASSIGN_ERR_NON_FINITE_DUAL: Int = 13

# An unassigned slot. -1 rather than 0, which is a legal agent and a legal task.
comptime ASSIGN_NONE: Int = -1

# A dual violation and a slackness gap are magnitudes, so a negative one is impossible:
# -1.0 says "not computed" where 0.0 would say "perfectly tight". Same device as
# `model.MODEL_VIOLATION_ABSENT` and `graph_analytics.GRAPH_NO_DISTANCE`.
comptime ASSIGN_DEFECT_ABSENT: Float64 = -1.0

# Exactly `combinatorial.assignment_greedy`'s initial `best_cost`. It selects a column
# only on a strict `<`, so a cell holding this value is unselectable BY THAT KERNEL'S OWN
# convention rather than by a magnitude this module hopes is large enough. Never summed.
comptime ASSIGN_FORBIDDEN_SENTINEL: Float64 = 1e308

# ── tolerances ────────────────────────────────────────────────────────────────

# The spacing between consecutive Float64 values at 1.0. Defined here rather than imported
# from `optimization.linear` (whose `LP_DBL_EPSILON` is the same number) because this module
# has no other reason to depend on the simplex, and `scheduling.SCHED_DBL_EPSILON` set that
# precedent. The VALUE is a property of Float64, not a tuning knob, so it cannot drift.
comptime ASSIGN_DBL_EPSILON: Float64 = 2.220446049250313e-16

# How many ulps OF THE JUDGED QUANTITY a certificate comparison may absorb before the
# violation counts as real. Matches `linear.LP_FEAS_ULP_BUDGET`, and generous on purpose: a
# reduced cost is a difference of three terms, so a few ulps of their magnitude is all that
# floating point can be blamed for. That is the only thing a relative term may ever explain
# away — which is why the multiplier is DBL_EPSILON and never `DEFAULT_FEASIBILITY_TOL`.
# `1e-9` used as a relative multiplier is 4.5 MILLION ulps, and at a cost of 1e9 that is a
# whole unit of dual violation waved through under `certified = True`.
comptime ASSIGN_CERT_ULP_BUDGET: Float64 = 1024.0


def assign_status_name(code: Int) -> String:
    """Name for a status code, so a rejection surfaces the defect and not a bare number."""
    if code == ASSIGN_OK:
        return "ok"
    if code == ASSIGN_ERR_SHAPE:
        return "dense_shape_invalid"
    if code == ASSIGN_ERR_DIMENSION_TOO_LARGE:
        return "dimension_too_large"
    if code == ASSIGN_ERR_LENGTH_MISMATCH:
        return "parallel_arrays_length_mismatch"
    if code == ASSIGN_ERR_NON_FINITE_COST:
        return "non_finite_cost"
    if code == ASSIGN_ERR_FEWER_AGENTS_THAN_TASKS:
        return "fewer_agents_than_tasks"
    if code == ASSIGN_ERR_NO_PERFECT_MATCHING:
        return "no_perfect_matching"
    if code == ASSIGN_ERR_INDEX:
        return "assignment_index_out_of_range"
    if code == ASSIGN_ERR_DUPLICATE:
        return "assignment_reuses_a_task"
    if code == ASSIGN_ERR_OVERFLOW:
        return "cost_overflow"
    if code == ASSIGN_ERR_ITERATION_LIMIT:
        return "iteration_limit"
    if code == ASSIGN_ERR_CERTIFICATE:
        return "dual_certificate_failed"
    if code == ASSIGN_ERR_BOUND_VIOLATED:
        return "greedy_bound_beats_result"
    if code == ASSIGN_ERR_NON_FINITE_DUAL:
        return "non_finite_dual"
    return "unknown_status_" + String(code)


# ── return-only result structs ────────────────────────────────────────────────
# Declared in this file because the marshalling spec for a returned struct is parsed per
# file: returning a struct owned by another module drops the function from the runtime
# contract silently, with no error anywhere.


@fieldwise_init
struct Assignment(Copyable, Movable):
    """An optimal assignment, or the reason there is none.

    `perfect` is the flag the frozen greedy does not have: True only when every task is
    assigned to a distinct agent. On any status other than `ASSIGN_OK` every list is empty
    and `has_cost` is False — a partial matching is not a partial answer, it is a
    `List[Int]` that reads as an assignment and is not one.

    `total_cost` is 0.0 when `has_cost` is False, and that is padding, not a claim; the
    same holds for `greedy_cost` under `has_greedy_cost` (the frozen greedy has no upper
    bound to offer when its own answer is infeasible or incomplete). `u` and `v` are the
    dual potentials, `max_dual_violation` and `max_tight_gap` the measured defect in the
    complementary-slackness certificate, and `ASSIGN_DEFECT_ABSENT` (-1.0) there means the
    certificate was never computed.
    """

    var status: Int
    var perfect: Bool
    var rows: Int
    var cols: Int
    var n_assigned: Int
    var has_cost: Bool
    var total_cost: Float64
    var col_of_row: List[Int]
    var row_of_col: List[Int]
    var u: List[Float64]
    var v: List[Float64]
    var dual_certified: Bool
    var max_dual_violation: Float64
    var max_tight_gap: Float64
    var has_greedy_cost: Bool
    var greedy_cost: Float64
    var improvement: Float64
    var warm_started: Int
    var augmentations: Int


@fieldwise_init
struct GreedyAssignment(Copyable, Movable):
    """`combinatorial.assignment_greedy`'s answer, made honest.

    Same pairs the frozen kernel picks — this is a window onto it, not a second
    implementation — plus the three things it does not report: the cost, how many agents
    it actually placed (it writes -1 into the list when nothing was available), and
    whether every task ended up covered. `covers_all_tasks` False with `status == ASSIGN_OK`
    is the frozen kernel's silent partiality made visible.
    """

    var status: Int
    var rows: Int
    var cols: Int
    var n_assigned: Int
    var covers_all_tasks: Bool
    var has_cost: Bool
    var total_cost: Float64
    var col_of_row: List[Int]


@fieldwise_init
struct CostReport(Copyable, Movable):
    """The cost of an assignment somebody else produced, plus whether it is one.

    The general form of `operations_research.assignment_cost_3`, which is `c1 + c2 + c3`
    over costs a comment claims are "already matched". Here the pairs are checked against
    the matrix: in range, distinct, and `perfect` only when every task is covered. A
    partial assignment is reported (`status == ASSIGN_OK`, `perfect == False`) rather than
    rejected — this is a report on what was passed in, not a solve.
    """

    var status: Int
    var rows: Int
    var cols: Int
    var n_assigned: Int
    var perfect: Bool
    var has_cost: Bool
    var total_cost: Float64


@fieldwise_init
struct DualCheck(Copyable, Movable):
    """Complementary slackness for a (assignment, u, v) triple, recomputed from scratch.

    `dual_feasible` covers BOTH families of dual constraint: `u[i] + v[j] <= cost[i][j]`
    over every allowed pair, and `u[i] <= 0` for every agent, which is the dual of the
    capacity constraint `sum_j x[i][j] <= 1`. `max_dual_violation` is the worst violation
    over both, and `n_agent_sign_violations` says how many agents carry a positive potential
    so the two are still distinguishable. `slack_tight` is equality on every chosen pair,
    and `n_idle_nonzero` counts idle agents carrying a potential — which complementary
    slackness on a slack capacity constraint forbids, so a nonzero count means the duals do
    not prove this matching optimal however tight they look. `certified` requires all of
    them. `dual_objective` is `sum(u) + sum(v)`, which equals the primal cost exactly when
    the triple is certified.

    Each condition is judged PER PAIR or PER AGENT against a budget built from that
    comparison's own terms — the caller's absolute tolerance plus `1024 * DBL_EPSILON` times
    `|c_ij| + |u_i| + |v_j|` — so no cell anywhere else in the matrix can raise the threshold
    a given pair is held to. `max_dual_violation` and `max_tight_gap` are the worst violation
    and gap in the caller's units, reported for inspection and never compared against a
    threshold themselves.
    """

    var status: Int
    var certified: Bool
    var dual_feasible: Bool
    var slack_tight: Bool
    var n_pairs_checked: Int
    var n_tight: Int
    var n_idle_nonzero: Int
    var n_agent_sign_violations: Int
    var max_dual_violation: Float64
    var max_tight_gap: Float64
    var has_dual_objective: Bool
    var dual_objective: Float64


# ── small helpers ─────────────────────────────────────────────────────────────


# `_finite` is `model.model_finite`, imported above under this module's old local name so no
# call site changed, and NOT redefined here — five byte-identical copies were five chances for
# the package's definition of "finite" to drift. Mojo has no access control, so the underscore
# on the alias only keeps the name out of the runtime contract; a predicate is not a driver.


def _pair_allowed(
    allowed: List[Bool], masked: Bool, agent: Int, task: Int, cols: Int
) -> Bool:
    """Mask lookup. Safe to index because the caller has already established
    `len(allowed) == len(cost) == rows * cols` when `masked` is True, and never indexes
    `allowed` at all when it is False."""
    if not masked:
        return True
    return allowed[agent * cols + task]


def _no_assignment(status: Int, rows: Int, cols: Int) -> Assignment:
    """A rejection: every list empty, every number flagged absent."""
    return Assignment(
        status,
        False,
        rows,
        cols,
        0,
        False,
        0.0,
        List[Int](),
        List[Int](),
        List[Float64](),
        List[Float64](),
        False,
        ASSIGN_DEFECT_ABSENT,
        ASSIGN_DEFECT_ABSENT,
        False,
        0.0,
        0.0,
        0,
        0,
    )


def _shape_defect(
    cost: List[Float64], rows: Int, cols: Int, allowed: List[Bool], masked: Bool
) -> Int:
    """Everything that must hold before a single cell is read.

    The dimension ceiling is tested BEFORE `dims_fit` so that "too big to allocate for"
    and "these numbers do not describe this list" stay separate codes; `dims_fit` folds
    both into False.
    """
    if rows < 0 or cols < 0:
        return ASSIGN_ERR_SHAPE
    if rows > MAX_CSR_DIM or cols > MAX_CSR_DIM:
        return ASSIGN_ERR_DIMENSION_TOO_LARGE
    if not dims_fit(rows, cols, len(cost)):
        return ASSIGN_ERR_SHAPE
    if masked and len(allowed) != len(cost):
        return ASSIGN_ERR_LENGTH_MISMATCH
    for k in range(len(cost)):
        if not _finite(cost[k]):
            return ASSIGN_ERR_NON_FINITE_COST
    return ASSIGN_OK


def _rounding_allowance(scale: Float64) -> Float64:
    """`1024 * DBL_EPSILON * scale` — what floating point can explain at `scale`, no more.

    `scale` must be the magnitude of the terms in the ONE comparison being made. There is no
    floor: `scale == 0.0` yields exactly 0.0, which is right, because zero is exactly
    representable and a comparison at magnitude zero has nothing to forgive. A floor of 1.0
    would make this an ABSOLUTE allowance of one unit times the caller's tolerance for every
    comparison below unit magnitude, sized by nothing in the problem — that is rule 4b's
    third spelling and it is what shipped here.

    A non-finite or negative `scale` yields 0.0. That matters: a `nan` scale makes the budget
    `nan`, and `x > nan` is False for EVERY x, so a threshold built from it passes having
    counted zero violations (rule 4d). Costs of 1e308 are legal here — the suite asserts a
    matching around them — and `|c| + |u| + |v|` at that magnitude overflows to `inf`, so
    this is a reachable path, not a defensive one. No allowance at all is the only safe
    reading: it can refuse a certificate, never forge one.
    """
    if not _finite(scale) or scale <= 0.0:
        return 0.0
    var slop = ASSIGN_CERT_ULP_BUDGET * ASSIGN_DBL_EPSILON * scale
    if not _finite(slop):
        return 0.0
    return slop


def _pair_tol(cell: Float64, potential_u: Float64, potential_v: Float64) -> Float64:
    """Budget for judging the reduced cost `cell - potential_u - potential_v`.

    The quantity judged is that one pair's reduced cost, and the only magnitudes that can
    have contributed rounding to it are the three terms it was built from. Not the largest
    cell in the matrix: that cell's units have nothing to do with this pair's cancellation,
    and letting it in is how a 0.5 violation between numbers of magnitude 0.5 was certified
    because some other pair cost 1e9.
    """
    return DEFAULT_FEASIBILITY_TOL + _rounding_allowance(
        fabs(cell) + fabs(potential_u) + fabs(potential_v)
    )


def _agent_tol(
    cost: List[Float64], cols: Int, col_of_row: List[Int],
    u: List[Float64], v: List[Float64], agent: Int,
) -> Float64:
    """Budget for judging `u[agent] <= 0`, sized by THAT agent's own dual relation.

    An agent's potential is not a free-standing number. On the pair it is matched to,
    complementary slackness makes it exactly `cost[agent][t] - v[t]`, so the rounding it can
    carry is what those terms explain — `|u_i| + |c_it| + |v_t|` — and nothing about another
    agent, another task, or the matrix. An idle agent has no such relation and its potential
    must be exactly 0.0 (`n_idle_nonzero` checks that, exactly, and separately), so its only
    allowance is the caller's absolute one.
    """
    var scale = fabs(u[agent])
    var t = col_of_row[agent]
    if t != ASSIGN_NONE and t >= 0 and t < cols:
        scale += fabs(cost[agent * cols + t]) + fabs(v[t])
    return DEFAULT_FEASIBILITY_TOL + _rounding_allowance(scale)


def _total_tol(left: Float64, right: Float64) -> Float64:
    """Budget for comparing two assignment TOTALS — the only two magnitudes in play.

    Both are `kahan_sum` outputs, whose error is a few ulps of the summands regardless of how
    many there were, so `|left| + |right|` bounds the rounding either can carry.
    """
    return DEFAULT_FEASIBILITY_TOL + _rounding_allowance(fabs(left) + fabs(right))


# ── the exact solve ───────────────────────────────────────────────────────────


def _reduced_transpose(
    cost: List[Float64], rows: Int, cols: Int, allowed: List[Bool], masked: Bool,
    task_potential: List[Float64],
) -> List[List[Float64]]:
    """The row-reduced matrix in task-major orientation, for the frozen greedy.

    Task-major because tasks are the side that must be saturated: per-task greedy always
    offers every task a column to try, while per-agent greedy on a matrix with more agents
    than tasks stops offering anything once the tasks run out. `task_potential` is
    1-indexed to match the solver's arrays.
    """
    var out = List[List[Float64]]()
    for t in range(cols):
        var row = List[Float64]()
        for w in range(rows):
            if _pair_allowed(allowed, masked, w, t, cols):
                row.append(cost[w * cols + t] - task_potential[t + 1])
            else:
                row.append(ASSIGN_FORBIDDEN_SENTINEL)
        out.append(row^)
    return out^


def _assignment_core(
    cost: List[Float64], rows: Int, cols: Int, allowed: List[Bool], masked: Bool
) -> Assignment:
    """Hungarian / Jonker-Volgenant, minimising, saturating every task.

    Internally the matrix is transposed — tasks are the shortest-augmenting-path source
    side, agents are the columns — because the algorithm augments once per element of the
    side that must be saturated, and that is the tasks. `task_potential` and
    `agent_potential` are 1-indexed with slot 0 the virtual column that carries the phase's
    source task, which is what keeps the dual update a single loop.
    """
    var defect = _shape_defect(cost, rows, cols, allowed, masked)
    if defect != ASSIGN_OK:
        return _no_assignment(defect, rows, cols)
    if cols > rows:
        return _no_assignment(ASSIGN_ERR_FEWER_AGENTS_THAN_TASKS, rows, cols)

    # No tasks is a real answer, not an edge case to reject: every agent idle, cost 0.0,
    # perfectly assigned. Same precedent as `sparse_numerics.factor`, where the system with
    # 0 unknowns solves rather than erroring.
    if cols == 0:
        var idle = List[Int]()
        var zero_u = List[Float64]()
        for _ in range(rows):
            idle.append(ASSIGN_NONE)
            zero_u.append(0.0)
        return Assignment(
            ASSIGN_OK, True, rows, 0, 0, True, 0.0,
            idle^, List[Int](), zero_u^, List[Float64](),
            True, 0.0, 0.0, True, 0.0, 0.0, 0, 0,
        )

    # ── row reduction over tasks; agent potentials stay at 0.0 ─────────────────
    # Only the task side is reduced. A column reduction would give idle agents a positive
    # potential, which the `sum_j x[i][j] <= 1` constraint forbids in the rectangular case
    # and which would break the optimality proof while leaving every number plausible.
    var task_potential = List[Float64]()
    task_potential.append(0.0)
    for t in range(cols):
        var best = 0.0
        var have = False
        for w in range(rows):
            if _pair_allowed(allowed, masked, w, t, cols):
                var c = cost[w * cols + t]
                if not have or c < best:
                    best = c
                    have = True
        if not have:
            # This task has no agent at all: no perfect matching, and saying so here also
            # keeps the min above from being taken over an empty set.
            return _no_assignment(ASSIGN_ERR_NO_PERFECT_MATCHING, rows, cols)
        task_potential.append(best)

    var agent_potential = List[Float64]()
    for _ in range(rows + 1):
        agent_potential.append(0.0)

    # ── warm start from the frozen greedy ─────────────────────────────────────
    var greedy = assignment_greedy(
        _reduced_transpose(cost, rows, cols, allowed, masked, task_potential)
    )
    # `matched_agent[w + 1]` is the 1-based task holding agent `w`, 0 for free.
    var matched_agent = List[Int]()
    for _ in range(rows + 1):
        matched_agent.append(0)
    var matched_task = List[Bool]()
    for _ in range(cols):
        matched_task.append(False)
    var warm_started = 0
    if len(greedy) == cols:
        for t in range(cols):
            var w = greedy[t]
            if w < 0 or w >= rows:
                continue  # the frozen kernel writes -1 when nothing was available
            if not _pair_allowed(allowed, masked, w, t, cols):
                continue  # it does not know about the mask
            if matched_agent[w + 1] != 0:
                continue  # it should never reuse an agent; verified rather than assumed
            if cost[w * cols + t] - task_potential[t + 1] != 0.0:
                continue  # not tight: taking it would break the dual invariant
            matched_agent[w + 1] = t + 1
            matched_task[t] = True
            warm_started += 1

    # ── one shortest augmenting path per still-unmatched task ─────────────────
    var predecessor = List[Int]()
    for _ in range(rows + 1):
        predecessor.append(0)
    var augmentations = 0
    for t0 in range(cols):
        if matched_task[t0]:
            continue
        var label = List[Float64]()
        var labelled = List[Bool]()
        var settled = List[Bool]()
        for _ in range(rows + 1):
            label.append(0.0)
            labelled.append(False)
            settled.append(False)
        matched_agent[0] = t0 + 1
        var j0 = 0
        var steps = 0
        while True:
            steps += 1
            if steps > rows + 1:
                # Each pass settles one previously unsettled column, so this is
                # unreachable; it is here because a non-terminating solver inside the
                # worker presents to a client as a hang, and a status does not.
                return _no_assignment(ASSIGN_ERR_ITERATION_LIMIT, rows, cols)
            settled[j0] = True
            var source_task = matched_agent[j0]
            var delta = 0.0
            var have_delta = False
            var next_j = 0
            for j in range(1, rows + 1):
                if settled[j]:
                    continue
                if _pair_allowed(allowed, masked, j - 1, source_task - 1, cols):
                    var reduced = (
                        cost[(j - 1) * cols + (source_task - 1)]
                        - task_potential[source_task]
                        - agent_potential[j]
                    )
                    if (not labelled[j]) or reduced < label[j]:
                        label[j] = reduced
                        labelled[j] = True
                        predecessor[j] = j0
                if labelled[j]:
                    if (not have_delta) or label[j] < delta:
                        delta = label[j]
                        have_delta = True
                        next_j = j
            if not have_delta:
                # The alternating tree is exhausted and every column in it is matched, so
                # the scanned tasks outnumber their allowed agents: a Hall violation, and
                # therefore a proof that no perfect matching exists — not a partial one.
                return _no_assignment(ASSIGN_ERR_NO_PERFECT_MATCHING, rows, cols)
            if not _finite(delta):
                return _no_assignment(ASSIGN_ERR_OVERFLOW, rows, cols)
            for j in range(rows + 1):
                if settled[j]:
                    task_potential[matched_agent[j]] += delta
                    agent_potential[j] -= delta
                elif labelled[j]:
                    label[j] -= delta
            j0 = next_j
            if matched_agent[j0] == 0:
                break  # a free agent: the path ends here, and slot j0 stays unsettled
        var walk = j0
        while walk != 0:
            var previous = predecessor[walk]
            matched_agent[walk] = matched_agent[previous]
            walk = previous
        matched_task[t0] = True
        augmentations += 1

    # ── unpack ────────────────────────────────────────────────────────────────
    var col_of_row = List[Int]()
    var row_of_col = List[Int]()
    for _ in range(cols):
        row_of_col.append(ASSIGN_NONE)
    var chosen = List[Float64]()
    var n_assigned = 0
    for w in range(rows):
        var task1 = matched_agent[w + 1]
        if task1 == 0:
            col_of_row.append(ASSIGN_NONE)
            continue
        var t = task1 - 1
        col_of_row.append(t)
        row_of_col[t] = w
        chosen.append(cost[w * cols + t])
        n_assigned += 1
    if n_assigned != cols:
        # Unreachable: every task was augmented or warm-started. Reported rather than
        # returned as a matching, because an incomplete one is not an assignment.
        return _no_assignment(ASSIGN_ERR_NO_PERFECT_MATCHING, rows, cols)

    var u = List[Float64]()
    for w in range(rows):
        u.append(agent_potential[w + 1])
    var v = List[Float64]()
    for t in range(cols):
        v.append(task_potential[t + 1])
    for w in range(rows):
        if not _finite(u[w]):
            return _no_assignment(ASSIGN_ERR_OVERFLOW, rows, cols)
    for t in range(cols):
        if not _finite(v[t]):
            return _no_assignment(ASSIGN_ERR_OVERFLOW, rows, cols)

    var total = kahan_sum(chosen)
    if not _finite(total):
        # The matching exists but its total does not. Reporting the matching with
        # `total_cost = inf` would hand a caller a number it would go on to compare.
        return _no_assignment(ASSIGN_ERR_OVERFLOW, rows, cols)

    # ── the certificate, recomputed from the answer ───────────────────────────
    # Each verdict is taken PER PAIR and PER AGENT against that comparison's own budget
    # (`_pair_tol`, `_agent_tol`). `max_violation` and `max_gap` are accumulated alongside as
    # magnitude summaries in the caller's units and are never themselves thresholded: a max
    # over pairs is not a quantity one budget can judge, because the pair holding the maximum
    # need not be the pair whose scale set the budget. Same split as
    # `linear.LpResult.infeasibility`, which reports a total while the verdict is per row.
    var max_violation = 0.0
    var dual_feasible = True
    for w in range(rows):
        for t in range(cols):
            if not _pair_allowed(allowed, masked, w, t, cols):
                continue
            var cell = cost[w * cols + t]
            var slack = cell - u[w] - v[t]
            if slack < 0.0:
                if -slack > max_violation:
                    max_violation = -slack
                if -slack > _pair_tol(cell, u[w], v[t]):
                    dual_feasible = False
    for w in range(rows):
        # `u[i] <= 0` is the dual of the capacity constraint `sum_j x[i][j] <= 1` and it
        # binds on every agent, not only the idle ones — see `_dual_check_core` for the
        # matching that a certificate without it stamps as optimal. Structurally this holds
        # here: an agent potential starts at 0.0 and is only ever decremented by a
        # nonnegative delta. This loop is the check that the invariant actually held, so the
        # solver's own certificate cannot pass on an answer the external check would reject.
        if u[w] > max_violation:
            max_violation = u[w]
        if u[w] > _agent_tol(cost, cols, col_of_row, u, v, w):
            dual_feasible = False
    var max_gap = 0.0
    var slack_tight = True
    var idle_nonzero = 0
    for w in range(rows):
        var t = col_of_row[w]
        if t == ASSIGN_NONE:
            if u[w] != 0.0:
                idle_nonzero += 1
            continue
        var cell = cost[w * cols + t]
        var gap = fabs(cell - u[w] - v[t])
        if gap > max_gap:
            max_gap = gap
        if gap > _pair_tol(cell, u[w], v[t]):
            slack_tight = False
    var certified = dual_feasible and slack_tight and idle_nonzero == 0
    if not certified:
        # An optimum that cannot be certified is exactly the converged-looking answer this
        # package exists to remove, so it does not travel with a matching attached.
        return _no_assignment(ASSIGN_ERR_CERTIFICATE, rows, cols)

    # ── the frozen greedy as an upper bound and an oracle ─────────────────────
    var greedy_cost = 0.0
    var has_greedy_cost = False
    if len(greedy) == cols:
        var used = List[Bool]()
        for _ in range(rows):
            used.append(False)
        var greedy_pairs = List[Float64]()
        var usable = True
        for t in range(cols):
            var w = greedy[t]
            if w < 0 or w >= rows or used[w]:
                usable = False
                break
            if not _pair_allowed(allowed, masked, w, t, cols):
                usable = False  # it may pick a forbidden pair; then it bounds nothing
                break
            used[w] = True
            greedy_pairs.append(cost[w * cols + t])
        if usable:
            var bound = kahan_sum(greedy_pairs)
            if _finite(bound):
                greedy_cost = bound
                has_greedy_cost = True
    # The quantity judged is the DIFFERENCE of these two totals, so its budget comes from
    # those two totals and nothing else — not from the largest cell, which at 1e9 made this
    # oracle unable to fire below a whole unit and at 1e308 unable to fire at all.
    var bound_tol = _total_tol(greedy_cost, total)
    if has_greedy_cost and greedy_cost < total - bound_tol:
        # A feasible assignment cheaper than the "optimal" one is a proof of a bug in this
        # solver, and the frozen greedy is an independent implementation, so it is worth
        # asking every time.
        return _no_assignment(ASSIGN_ERR_BOUND_VIOLATED, rows, cols)
    var improvement = 0.0
    if has_greedy_cost:
        improvement = greedy_cost - total
        if improvement < bound_tol:
            # Within the rounding the two sums can carry, the two costs are the same number,
            # and a -1e-16 improvement would read as the greedy answer having won.
            improvement = 0.0

    return Assignment(
        ASSIGN_OK,
        True,
        rows,
        cols,
        n_assigned,
        True,
        total,
        col_of_row^,
        row_of_col^,
        u^,
        v^,
        True,
        max_violation,
        max_gap,
        has_greedy_cost,
        greedy_cost,
        improvement,
        warm_started,
        augmentations,
    )


def assignment_solve(cost: List[Float64], rows: Int, cols: Int) -> Assignment:
    """Minimum-cost assignment of every task (column) to a distinct agent (row).

    `cost` is row-major with `rows * cols` cells. Optimal, not greedy: on
    `c[i][j] = (i+1)(j+1)` this returns 10 where `combinatorial.assignment_greedy`
    returns 14, and `improvement` reports the difference the greedy call site was paying.
    Agents may be idle when `rows > cols`; `cols > rows` is refused rather than answered
    with a matching that leaves tasks undone.
    """
    return _assignment_core(cost, rows, cols, List[Bool](), False)


def assignment_solve_masked(
    cost: List[Float64], rows: Int, cols: Int, allowed: List[Bool]
) -> Assignment:
    """`assignment_solve` with forbidden pairings given as a parallel `Bool` mask.

    `allowed[i * cols + j]` False means agent `i` cannot do task `j` at any price. The
    cell's cost is then never read for the objective and the pair can never be chosen, so
    an infeasible problem comes back as `ASSIGN_ERR_NO_PERFECT_MATCHING` instead of as an
    assignment that quietly uses the pairing a big-M cost was meant to forbid.
    """
    return _assignment_core(cost, rows, cols, allowed, True)


# ── the frozen greedy, reported honestly ──────────────────────────────────────


def greedy_assignment_flat(
    cost: List[Float64], rows: Int, cols: Int
) -> GreedyAssignment:
    """`combinatorial.assignment_greedy` over a flat matrix, with its cost and its gaps.

    The pairs are the frozen kernel's own — this calls it, it does not reimplement it —
    and they are then checked for range and distinctness rather than trusted, and summed
    with `kahan_sum`. The frozen kernel's `-1` slots become `n_assigned < rows`, and a
    task no agent took becomes `covers_all_tasks == False`, which is the failure that is
    invisible at its call site. `cols > rows` is NOT refused here: this is a report on what
    the greedy kernel does, and what it does with more tasks than agents is leave tasks
    undone.
    """
    var defect = _shape_defect(cost, rows, cols, List[Bool](), False)
    if defect != ASSIGN_OK:
        return GreedyAssignment(defect, rows, cols, 0, False, False, 0.0, List[Int]())
    var nested = List[List[Float64]]()
    for w in range(rows):
        var row = List[Float64]()
        for t in range(cols):
            row.append(cost[w * cols + t])
        nested.append(row^)
    var picks = assignment_greedy(nested)
    if len(picks) != rows:
        return GreedyAssignment(
            ASSIGN_ERR_LENGTH_MISMATCH, rows, cols, 0, False, False, 0.0, List[Int]()
        )
    var used = List[Bool]()
    for _ in range(cols):
        used.append(False)
    var pairs = List[Float64]()
    var n_assigned = 0
    for w in range(rows):
        var t = picks[w]
        if t == ASSIGN_NONE:
            continue
        if t < 0 or t >= cols:
            return GreedyAssignment(
                ASSIGN_ERR_INDEX, rows, cols, 0, False, False, 0.0, List[Int]()
            )
        if used[t]:
            return GreedyAssignment(
                ASSIGN_ERR_DUPLICATE, rows, cols, 0, False, False, 0.0, List[Int]()
            )
        used[t] = True
        pairs.append(cost[w * cols + t])
        n_assigned += 1
    var covers_all = n_assigned == cols
    var total = kahan_sum(pairs)
    if not _finite(total):
        # Uniform with the other rejections here: no pairs travel with a status that says
        # the sum of those very pairs could not be formed.
        return GreedyAssignment(
            ASSIGN_ERR_OVERFLOW, rows, cols, 0, False, False, 0.0, List[Int]()
        )
    return GreedyAssignment(
        ASSIGN_OK, rows, cols, n_assigned, covers_all, True, total, picks^
    )


# ── scoring and certifying somebody else's assignment ─────────────────────────


def assignment_cost_of(
    cost: List[Float64], rows: Int, cols: Int, col_of_row: List[Int]
) -> CostReport:
    """Total cost of the pairs in `col_of_row`, with range, distinctness and completeness.

    `col_of_row[i]` is the task agent `i` does, or -1 for idle. A reused task is
    `ASSIGN_ERR_DUPLICATE` and a task index outside `[0, cols)` is `ASSIGN_ERR_INDEX`:
    both are silently summable in `operations_research.assignment_cost_3`, which takes
    three costs and no matrix.
    """
    var defect = _shape_defect(cost, rows, cols, List[Bool](), False)
    if defect != ASSIGN_OK:
        return CostReport(defect, rows, cols, 0, False, False, 0.0)
    if len(col_of_row) != rows:
        return CostReport(ASSIGN_ERR_LENGTH_MISMATCH, rows, cols, 0, False, False, 0.0)
    var used = List[Bool]()
    for _ in range(cols):
        used.append(False)
    var pairs = List[Float64]()
    var n_assigned = 0
    for w in range(rows):
        var t = col_of_row[w]
        if t == ASSIGN_NONE:
            continue
        if t < 0 or t >= cols:
            return CostReport(ASSIGN_ERR_INDEX, rows, cols, 0, False, False, 0.0)
        if used[t]:
            return CostReport(ASSIGN_ERR_DUPLICATE, rows, cols, 0, False, False, 0.0)
        used[t] = True
        pairs.append(cost[w * cols + t])
        n_assigned += 1
    var total = kahan_sum(pairs)
    var perfect = n_assigned == cols
    if not _finite(total):
        return CostReport(ASSIGN_ERR_OVERFLOW, rows, cols, n_assigned, perfect, False, 0.0)
    return CostReport(ASSIGN_OK, rows, cols, n_assigned, perfect, True, total)


def _dual_check_core(
    cost: List[Float64], rows: Int, cols: Int, col_of_row: List[Int],
    u: List[Float64], v: List[Float64], allowed: List[Bool], masked: Bool,
) -> DualCheck:
    """Complementary slackness, recomputed over every pair from the outside."""
    var defect = _shape_defect(cost, rows, cols, allowed, masked)
    if defect != ASSIGN_OK:
        return DualCheck(
            defect, False, False, False, 0, 0, 0, 0,
            ASSIGN_DEFECT_ABSENT, ASSIGN_DEFECT_ABSENT, False, 0.0,
        )
    if len(col_of_row) != rows or len(u) != rows or len(v) != cols:
        return DualCheck(
            ASSIGN_ERR_LENGTH_MISMATCH, False, False, False, 0, 0, 0, 0,
            ASSIGN_DEFECT_ABSENT, ASSIGN_DEFECT_ABSENT, False, 0.0,
        )
    for w in range(rows):
        if not _finite(u[w]):
            return DualCheck(
                ASSIGN_ERR_NON_FINITE_DUAL, False, False, False, 0, 0, 0, 0,
                ASSIGN_DEFECT_ABSENT, ASSIGN_DEFECT_ABSENT, False, 0.0,
            )
    for t in range(cols):
        if not _finite(v[t]):
            return DualCheck(
                ASSIGN_ERR_NON_FINITE_DUAL, False, False, False, 0, 0, 0, 0,
                ASSIGN_DEFECT_ABSENT, ASSIGN_DEFECT_ABSENT, False, 0.0,
            )
    var used = List[Bool]()
    for _ in range(cols):
        used.append(False)
    for w in range(rows):
        var t = col_of_row[w]
        if t == ASSIGN_NONE:
            continue
        if t < 0 or t >= cols:
            return DualCheck(
                ASSIGN_ERR_INDEX, False, False, False, 0, 0, 0, 0,
                ASSIGN_DEFECT_ABSENT, ASSIGN_DEFECT_ABSENT, False, 0.0,
            )
        if used[t]:
            return DualCheck(
                ASSIGN_ERR_DUPLICATE, False, False, False, 0, 0, 0, 0,
                ASSIGN_DEFECT_ABSENT, ASSIGN_DEFECT_ABSENT, False, 0.0,
            )
        used[t] = True

    # Every comparison below is judged against ITS OWN budget — `_pair_tol` for a pair,
    # `_agent_tol` for an agent potential. There is deliberately no single `tol` in this
    # function any more: one number covering the whole matrix is exactly how a 0.5 violation
    # between terms of magnitude 0.5 came back `certified = True` because one unrelated cell
    # held 1e9. `max_violation` and `max_gap` are reported, not thresholded.
    var n_pairs = 0
    var n_tight = 0
    var max_violation = 0.0
    var pair_feasible = True
    for w in range(rows):
        for t in range(cols):
            if not _pair_allowed(allowed, masked, w, t, cols):
                continue
            n_pairs += 1
            var cell = cost[w * cols + t]
            var slack = cell - u[w] - v[t]
            var pair_tol = _pair_tol(cell, u[w], v[t])
            if fabs(slack) <= pair_tol:
                n_tight += 1
            if slack < 0.0:
                if -slack > max_violation:
                    max_violation = -slack
                if -slack > pair_tol:
                    pair_feasible = False

    # The second family of dual constraints: `u[i] <= 0` for EVERY agent, matched or idle.
    # The primal capacity constraint is `sum_j x[i][j] <= 1`, an inequality, so its dual
    # variable is sign-constrained, and the bound `cost . x >= sum(u) + sum(v)` only holds
    # for every feasible x when it is respected. Omitting it certifies suboptimal matchings:
    # cost = (5, 1) with rows = 2, cols = 1, col_of_row = (0, -1), u = (4, 0), v = (1) is
    # feasible on both pairs, tight on the chosen pair, has no idle agent with a nonzero
    # potential (the idle agent is at 0.0), and reports dual objective 5.0 against a
    # matching that costs 5.0 — a textbook strong-duality match for an answer whose true
    # optimum is 1.0. `n_idle_nonzero` cannot see it because the positive potential sits on
    # the agent that IS matched; only this loop can.
    var agent_sign_violations = 0
    for w in range(rows):
        if u[w] > _agent_tol(cost, cols, col_of_row, u, v, w):
            agent_sign_violations += 1
        if u[w] > max_violation:
            max_violation = u[w]

    var max_gap = 0.0
    var slack_tight = True
    var idle_nonzero = 0
    for w in range(rows):
        var t = col_of_row[w]
        if t == ASSIGN_NONE:
            if u[w] != 0.0:
                idle_nonzero += 1
            continue
        var cell = cost[w * cols + t]
        var gap = fabs(cell - u[w] - v[t])
        if gap > max_gap:
            max_gap = gap
        if gap > _pair_tol(cell, u[w], v[t]):
            slack_tight = False
    var potentials = List[Float64]()
    for w in range(rows):
        potentials.append(u[w])
    for t in range(cols):
        potentials.append(v[t])
    var objective = kahan_sum(potentials)
    var has_objective = _finite(objective)
    if not has_objective:
        objective = 0.0
    var feasible = pair_feasible and agent_sign_violations == 0
    return DualCheck(
        ASSIGN_OK,
        feasible and slack_tight and idle_nonzero == 0 and has_objective,
        feasible,
        slack_tight,
        n_pairs,
        n_tight,
        idle_nonzero,
        agent_sign_violations,
        max_violation,
        max_gap,
        has_objective,
        objective,
    )


def assignment_dual_check(
    cost: List[Float64], rows: Int, cols: Int, col_of_row: List[Int],
    u: List[Float64], v: List[Float64],
) -> DualCheck:
    """Verify `u[i] + v[j] <= cost[i][j]` everywhere, with equality on the chosen pairs.

    This is the certificate a caller can check without trusting this module: potentials
    that satisfy it prove the matching is optimal, and `dual_objective` then equals the
    total cost. Pass the `u` and `v` from an `Assignment` and it recomputes over every
    pair.
    """
    return _dual_check_core(cost, rows, cols, col_of_row, u, v, List[Bool](), False)


def assignment_dual_check_masked(
    cost: List[Float64], rows: Int, cols: Int, col_of_row: List[Int],
    u: List[Float64], v: List[Float64], allowed: List[Bool],
) -> DualCheck:
    """`assignment_dual_check` restricted to the allowed pairs.

    A forbidden pair carries no dual constraint — the pairing does not exist, so its cell
    is not a cost that any potential has to respect — and checking it anyway would report
    a valid certificate as violated.
    """
    return _dual_check_core(cost, rows, cols, col_of_row, u, v, allowed, True)
