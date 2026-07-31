"""
optimization.linear — the linearity extractor and a real simplex.

Why this file exists
--------------------
The tree's linear programming is `linear_programming.mojo`, and it is a two-variable
vertex enumerator wearing a general name. `lp_solve_2var` enumerates the pairwise
intersections of the constraint lines with the two axes, so it is structurally incapable
of a third variable, it always MAXIMISES, it hardcodes `x >= 0` and `A x <= b`, and it
returns an EMPTY list for infeasible — the same return an unbounded program gets, and the
same return a caller gets for a malformed one.

Worse, the functions around it are named for things they do not compute:

  * `linear_programming.dual_value(A, b, c)` computes NO DUAL AT ALL. Grep it: its body is
    `var sol = lp_solve_2var(c, A, b)` followed by `return sol[2]`, which is the PRIMAL
    optimum. It is a misnomer twice over — its parameter order `(A, b, c)` is also the
    reverse of `lp_solve_2var`'s `(c, A, b)`, so a caller who reads the name and passes
    the arguments in the other order silently solves a different program. It returns
    `0.0` for an infeasible program, and 0.0 is a perfectly ordinary optimum.
  * `linear_programming.sensitivity_rhs` is a finite difference of two `lp_solve_2var`
    calls. Each missing solve contributes 0.0, so a perturbation that makes the program
    infeasible reports a sensitivity of `-orig_val` — a number, in the right units, with
    no relation to the derivative it claims to be.
  * `linear_programming.is_feasible` hardcodes `x >= 0` and indexes `b[i]` without
    checking `len(b)`, so a short `b` is an uncatchable process crash.

`lp_solve_2var` itself stays reachable and is not wrapped here. It is the frozen
two-variable fast path, and the suite uses it as a DIFFERENTIAL ORACLE: on a two-variable
maximisation the optimum found here must equal the one it enumerates. Dispatching to it
internally for `cols == 2` was rejected — a second code path for small inputs is how a
divergence between the two ships unnoticed; a test that asserts they agree is how it is
caught.

Part one: the extractor
-----------------------
`extract_linear` walks a `types.ExprNode` arena and either produces the EXACT
`(coeffs, constant)` of an affine form or fails naming the offending node, its opcode and
the variable that makes it nonlinear. It never approximates: a product of two variables, a
variable divisor, a division by a zero constant, a transcendental applied to anything that
mentions a variable, an out-of-range variable or node index are all statuses. An extractor
that silently linearises `x*y` is worse than no extractor, because the LP it produces is
feasible, optimal and about a different problem.

The walk is a DESCENDING pass over the arena, not a recursive descent from the root, and
that is a correctness decision rather than a style one. `query.ir.validation_error`
guarantees every child index is strictly less than its parent's, so processing nodes from
`n-1` down to `0` visits a node only after every parent that references it. Each node
therefore accumulates a single multiplier from all of its parents, and an arena that SHARES
a subexpression costs one visit rather than one visit per path — a recursive descent over
a shared-subtree DAG is exponential in the sharing depth. The multiplier is distributed by
opcode: `add` passes it to both children, `sub` negates the right, `neg` negates, `mul` by
a variable-free side scales it, `div` by a variable-free side divides it.

A variable-free subtree is folded to a constant by handing it to
`optimization.model.evaluate_expr` with a zero point, so this file contains no second
expression evaluator and inherits every domain status that one reports — `1/0` in a
constant subtree is `division_by_zero`, not a silently folded 0.0 the way
`expr.eval_expr` would give. Literals short-circuit that call, so the canonical
`model.linear_arena` layout folds with no evaluator calls at all.

Nodes whose multiplier cancels to exactly zero are still validated. `0 * (x*y)` is linear
by cancellation, and accepting it would mean deciding whether `0 * (1/x)` at `x = 0` is
`0.0` or undefined. Both are rejected, which is one rule instead of two.

Part two: the simplex
---------------------
A dense tableau simplex on general `n`, two-phase, over `min cᵀx + constant` subject to
row-wise `A x {<=,=,>=} b` and `x >= 0`.

*Two phases, not big-M.* A big-M formulation needs an M large enough to dominate every
objective coefficient and small enough not to swamp the constraint arithmetic, and the
gap between those is a property of the caller's data that this module cannot see. When M
is too small the solver reports an "optimal" vertex of the penalised program, which is a
wrong answer with an optimal status. Phase 1 minimises the sum of the artificials
instead, so infeasibility is a MEASURED residual (`infeasibility` reports its total) and
it is reported as `LP_INFEASIBLE` with no solution vector at all.

The acceptance test on that residual is PER ROW, against each row's OWN magnitude, and it
is `art_i <= feas_tol + 1024 * DBL_EPSILON * |b_i|` — an ABSOLUTE allowance the caller chose
plus a ROUNDING allowance at that row's scale. `_lp_row_gap_budget` is the one definition,
shared with the `binding` flag so the two verdicts about one row cannot disagree.

Two earlier spellings of that threshold each shipped a confident wrong answer, which is why
the form above is stated here rather than left to the call site. `feas_tol * (1 + Σ_i |b_i|)`
is an aggregate and returned `LP_OPTIMAL` for programs with no feasible point: 200 ordinary
`x0 <= 1e7` capacity rows next to the contradictory pair `x1 >= 3, x1 <= 2` push a `1e-9`
tolerance past 1.0, so a row violated by a FULL UNIT passed as optimal, complete with x,
duals, reduced costs and a basis. `feas_tol * (1 + |b_i|)` is per-row and no better: it
floors the test at `feas_tol` regardless of scale and then uses `feas_tol` — 4.5 million
ulps at magnitude 1e9 — as the RELATIVE multiplier, so `{x >= 1e9, x <= 1e9 - 1}` came back
optimal at x = 1e9, and a row with nine tenths of a unit of slack came back BINDING. See
`_simplex_run`, `_solution_from_simplex` and `LP_FEAS_ULP_BUDGET`.

An artificial is created for every row but only made basic where no slack can be: a `<=`
row with `b >= 0` (or a `>=` row with `b < 0`, after the row sign flip that makes every
right-hand side non-negative) starts with its own slack basic. So an all-`<=` program with
`b >= 0` finishes phase 1 in zero iterations, and `phase1_iterations` reports that.

*Unbounded is a status, never a vertex.* When an entering column has no blocking row the
program is unbounded along it; `has_objective` is False, `objective` is 0.0 padding, `x`
is EMPTY, and `unbounded_variable` names the column. Returning the last vertex value —
which is what a solver that stops at its iteration cap and reports success does — is the
exact failure mode this package exists to remove. `LP_ITERATION_LIMIT` is likewise a
distinct status with no answer attached.

*Duals and reduced costs are real, and testable.* Artificial column `i` of the initial
tableau is `e_i`, so column `art0 + i` of the FINAL tableau is column `i` of `B⁻¹`, and
`π̂ = c_Bᵀ B⁻¹` is one dot product per row. Row `i` may have been sign-flipped to make
`b >= 0`; since `π̂ᵀ(D A) = (D π̂)ᵀ A`, the dual of the caller's row is `D_i π̂_i`. Both
duals and reduced costs are then reported in the CALLER's sense — `dual_i` is
`∂objective/∂b_i` of the objective as the caller stated it — using
`model.minimization_value` for the sign conversion, because that conversion is the same
involution in both directions. The reduced costs are recomputed from the ORIGINAL `A` as
`c_j - Σ_i a_ij dual_i` rather than read off the tableau's cost row: an independent route
to the same numbers means a tableau bookkeeping error shows up as a nonzero reduced cost
on a basic variable instead of hiding inside a consistent-looking tableau. For the same
reason `objective` is `constant + c·x` at the returned point via the frozen
`linalg.vec_dot`, not the tableau's accumulated objective cell.

*Cycling.* Dantzig's most-negative rule until the phase objective fails to improve for
`m + n_cols` consecutive pivots, then Bland's rule (lowest-index entering column, lowest
basic-variable index among ratio ties) permanently. Bland's rule terminates finitely, so
the hybrid does. A perturbation of `b` was rejected: it terminates too, but it changes the
program, and the answer then needs an argument that the change was negligible — which is
an argument about the caller's data. `used_bland` and `degenerate_pivots` report what
happened. Beale's cycling example is in the suite and terminates at the hand-computed
optimum.

*No basis solve, and deliberately not `mat_solve`.* The tableau already carries `B⁻¹A`, so
there is nothing for `linalg.mat_solve` to do; and it would be the wrong tool if there
were, because it returns an all-zeros vector for a singular matrix, which is
indistinguishable from a legitimate basic solution at the origin. The suite does use it as
an independent oracle for the duals — `Bᵀπ = c_B` solved from the reported basis — which
is the right use for it: a check, where a zeros return is visibly wrong, rather than a
step, where it would be silently absorbed.

`x >= 0` is the variable convention, and it is not hidden
---------------------------------------------------------
Bounds other than non-negativity are expressed as ROWS. Shifting a lower bound into the
objective, flipping an upper-bounded variable, or splitting a free variable into a
difference of two — the textbook standard-form conversions — were all rejected INSIDE the
solver: each one reports duals and reduced costs in a transformed space the caller cannot
see, and a sign convention the caller cannot see is the failure this package removes.
`model.linear_model_flat` already turns bounds into rows on the way in, and
`lp_from_arenas` extracts them back out again, so the capability is present and visible at
every step.

Status codes are one numbering with `optimization.model`
--------------------------------------------------------
0 is success in every result here (`LP_OPTIMAL == LIN_OK == MODEL_OK`), every code
`model.mojo` already defines keeps its meaning, and the new codes start at 40 and 60 so
nothing collides. `lin_status_name` and `lp_status_name` fall through to
`model_status_name`, so a code from a rejected arena names the arena defect and not
"unknown status 8".

Ceilings
--------
`MAX_CSR_DIM` is imported for dimensions, never redefined. The tableau needs a SECOND and
different ceiling, because it is a different resource: it allocates
`m * (n + n_slack + m + 1)` cells, which is quadratic in `m` and therefore not bounded by
any per-dimension limit — `m = n = 8192` is a legal shape asking for 1.6 GB.
`LP_MAX_TABLEAU_CELLS` bounds the cell count and is tested with a DIVISION, because
`m * width` is a wrapping multiply and `3 * 6148914691236517206 == 2`.

A declared `n_vars` is not a third ceiling and gets no new constant. It is bounded by the
PAYLOAD instead: `extract_linear` and `lp_from_arenas` clamp it to the highest variable the
arenas actually reference, because a variable no expression mentions has coefficient 0 by
construction and cannot change any answer. Without that, `n_vars` was bounded only by
`MAX_CSR_DIM` and nothing tied it to the arenas: `lp_from_arenas` materialises five
parallel per-variable columns, `model_from_flat` then builds one `OptVar` per variable each
carrying a `String` name, and `extract_linear` adds two more per-variable vectors — about
200 bytes per declared variable whatever the arenas contain. Measured: `n_vars = 2^22`
peaked at 1.29 GB and `2^24` at 3.50 GB from a payload of one node plus one integer.
"""
from std.math import abs as fabs

from linalg import vec_dot
from optimization.model import (
    DEFAULT_FEASIBILITY_TOL,
    DEFAULT_INTEGRALITY_TOL,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_TIME_MS,
    DEFAULT_OPTIMALITY_TOL,
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_DIMENSION_TOO_LARGE,
    MODEL_ERR_DIV_BY_ZERO,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_ERR_NON_FINITE_COEFFICIENT,
    MODEL_ERR_NON_FINITE_POINT,
    MODEL_ERR_NON_FINITE_RHS,
    MODEL_ERR_NON_FINITE_VALUE,
    MODEL_ERR_POLICY,
    MODEL_ERR_SENSE,
    MODEL_OK,
    ModelFlat,
    ScalarResult,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    VAR_CONTINUOUS,
    VAR_FLAG_HAS_LOWER,
    _policy_parts_defect,
    arena_flat_defect,
    arena_from_flat,
    check_expr,
    evaluate_expr,
    minimization_value,
    model_finite as _finite,
    model_from_flat,
    model_op_arity,
    model_status_name,
    model_validate,
)
from query.ir import (
    OP_ADD,
    OP_DIV,
    OP_LITERAL,
    OP_MUL,
    OP_NEG,
    OP_SUB,
    OP_VAR_REF,
    op_name,
)
from sparse_numerics.csr import MAX_CSR_DIM, dims_fit
from types import ExprNode

# ── status codes ──────────────────────────────────────────────────────────────
# One numbering shared with `optimization.model`: 0-30 are its codes and keep their
# meaning, 40+ are the extractor's, 60+ are the solver's outcomes. The gaps are room for
# model.mojo to grow without a renumber, because a renumber would silently change what a
# stored status means.

comptime LIN_OK: Int = MODEL_OK
comptime LIN_ERR_NONLINEAR_PRODUCT: Int = 40
comptime LIN_ERR_VARIABLE_DIVISOR: Int = 41
comptime LIN_ERR_NONLINEAR_OP: Int = 42

comptime LP_OPTIMAL: Int = MODEL_OK
comptime LP_INFEASIBLE: Int = 60
comptime LP_UNBOUNDED: Int = 61
comptime LP_ITERATION_LIMIT: Int = 62
comptime LP_NUMERICAL_BREAKDOWN: Int = 63

# The tableau's cell ceiling. 2^25 cells is 268 MB of Float64, inside the 512 MiB that
# `algenta_runtime.session` treats as the outer limit for one resident object. This is NOT
# a second copy of MAX_CSR_DIM: that bounds a dimension, this bounds an area that grows
# quadratically in the row count and is therefore unbounded by any dimension limit.
comptime LP_MAX_TABLEAU_CELLS: Int = 1 << 25

# A pivot smaller than this is refused. Dividing a row by 1e-14 amplifies the whole row's
# rounding error into the answer, and the resulting "optimal" tableau is arbitrary.
comptime LP_PIVOT_MIN: Float64 = 1e-11

# Ratio ties are compared with a tolerance because exact equality of two quotients is not
# a property floating point preserves. Bland's rule needs the tie DETECTED to terminate.
comptime LP_TIE_EPS: Float64 = 1e-12

# A magnitude cannot be negative, so -1.0 says "phase 1 never finished, this was never
# measured" — the same convention as `model.MODEL_VIOLATION_ABSENT`. 0.0 would read as
# "feasible", which is the claim this value exists to substantiate.
comptime LP_INFEASIBILITY_ABSENT: Float64 = -1.0

# The spacing between consecutive Float64 values at 1.0. A row's residual is the output of
# `m` elimination steps on values of the row's own magnitude, so the rounding error it can
# accumulate is proportional to `|b_i| * DBL_EPSILON`, not to `|b_i|`.
comptime LP_DBL_EPSILON: Float64 = 2.220446049250313e-16

# How many ulps of a row's own magnitude the elimination is allowed to have accumulated
# before a residual counts as real. Generous by design — 1024 ulps is far more than a
# well-conditioned pivot sequence produces — but it is a ROUNDING budget, which is the only
# thing a relative feasibility term can legitimately absorb.
#
# Why not a fraction of `|b_i|`: a plain relative test `residual / (1 + |b_i|) > feas_tol`
# looks per-row and still swallows real infeasibility, because the fraction shrinks with the
# row's magnitude while the violation does not. `{x >= 1e9, x <= 1e9 - 1}` has no feasible
# point and its residual is exactly 1.0, but 1.0/(1+1e9) is 1e-9, which is not greater than
# the 1e-9 default — so it came back LP_OPTIMAL at x = 1e9. That 1.0 is 4.5 MILLION ulps at
# magnitude 1e9: unambiguously a real violation, nowhere near the noise floor. Sizing the
# relative term by DBL_EPSILON instead of by `feas_tol` keeps it pinned to what floating
# point can actually explain away.
comptime LP_FEAS_ULP_BUDGET: Float64 = 1024.0


fn _lp_row_gap_budget(feas_tol: Float64, rhs_i: Float64) -> Float64:
    """How far row `i`'s activity may sit from `b_i` and still count as ZERO distance.

    The ONE definition in this file of "this row is met exactly", used by both places that
    ask the question, because they must not be able to disagree about the same row:

      * `_simplex_run` decides SATISFIED — is the phase-1 artificial on this row zero?
      * `_solution_from_simplex` decides BINDS — is the returned point ON this row?

    A row satisfied only because its violation fits the budget is, by construction, a row
    whose activity equals `b_i` to within the same budget, so "infeasible" and "not binding"
    cannot both be claimed about one row, and neither can "satisfied" and "binds" be denied
    together. Two independent thresholds for one geometric fact is how those verdicts drift.

    The quantity being judged is `|b_i - A_i x|`, a distance in row `i`'s OWN units, and the
    budget is built only from that: the caller's ABSOLUTE `feas_tol`, plus a ROUNDING
    allowance of `LP_FEAS_ULP_BUDGET` ulps AT that row's magnitude. Nothing about any other
    row enters, and no other row's magnitude can raise it.

    Rejected forms, both of which shipped here and both of which produced a confident wrong
    answer — see `LP_FEAS_ULP_BUDGET` and `_solution_from_simplex`:

      * `feas_tol * (1 + Σ_i |b_i|)`: an aggregate. One unrelated large row lifts every other
        row's threshold without limit.
      * `feas_tol * (1 + |b_i|)`: per-row and STILL wrong, twice over. The `1 +` makes it a
        FLOOR of `feas_tol` at a scale the caller never chose, and using `feas_tol` itself as
        the RELATIVE multiplier is 4.5 million ulps of slop at magnitude 1e9 — so at
        `b_i = 1e9` the threshold is 1.000000001 and a row with nine tenths of a unit of
        genuine slack was reported as BINDING, complete with a shadow price.
    """
    return feas_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * fabs(rhs_i)


fn lin_status_name(code: Int) -> String:
    """Name for an extractor status, falling through to `model_status_name`."""
    if code == LIN_ERR_NONLINEAR_PRODUCT:
        return "nonlinear_product_of_variables"
    if code == LIN_ERR_VARIABLE_DIVISOR:
        return "division_by_a_variable"
    if code == LIN_ERR_NONLINEAR_OP:
        return "nonlinear_operator_over_a_variable"
    return model_status_name(code)


fn lp_status_name(code: Int) -> String:
    """Name for a solver status. 0 is `optimal` here, not the generic `ok`."""
    if code == LP_OPTIMAL:
        return "optimal"
    if code == LP_INFEASIBLE:
        return "infeasible"
    if code == LP_UNBOUNDED:
        return "unbounded"
    if code == LP_ITERATION_LIMIT:
        return "iteration_limit"
    if code == LP_NUMERICAL_BREAKDOWN:
        return "numerical_breakdown"
    return lin_status_name(code)


# `_finite` is `model.model_finite`, imported above under this module's old local name so
# no call site changed. It is NOT redefined here: five files each carried a byte-identical
# copy, which is five chances for the predicate deciding whether a cost or a right-hand side
# is admissible to drift apart. Mojo has no access control, so the underscore on the alias
# only keeps the name out of the runtime contract.


# ── return-only result structs ────────────────────────────────────────────────
# Declared here because a returned struct's marshalling spec is parsed per FILE: returning
# one owned by another module drops the function from the runtime contract silently.


@fieldwise_init
struct LinearForm(Copyable, Movable):
    """An affine form `Σ coeffs[j] x_j + constant`, or the reason there is none.

    `is_linear` is the authority, and it has to be: on a rejection `coeffs` is EMPTY rather
    than zero-filled, because an all-zero coefficient vector is a perfectly good linear
    form (the constant one) and cannot also mean "no form" — and a ZERO-VARIABLE model,
    which `model.mojo` accepts as real, has an empty `coeffs` on success too. Reading
    `len(coeffs)` as the verdict gets that last case backwards; reading `is_linear` does
    not.

    `node_index` / `op` / `var_index` are the WHERE — the offending node, its opcode, and
    the lowest-indexed variable in the offending subtree — while `status` is the WHAT. -1
    in any of them means "not applicable to this status", never variable 0.
    """

    var status: Int
    var is_linear: Bool
    var n_vars: Int
    var n_terms: Int
    var constant: Float64
    var node_index: Int
    var op: Int
    var var_index: Int
    var coeffs: List[Float64]
    var message: String


@fieldwise_init
struct FormValue(Copyable, Movable):
    """One scalar with its existence flag. `value` is 0.0 padding when `has_value` is False."""

    var status: Int
    var has_value: Bool
    var value: Float64


@fieldwise_init
struct LPMatrix(Copyable, Movable):
    """The `(c, constant, A, senses, rhs)` of a linear program recovered from arenas.

    Carries no optimisation direction: an arena states an expression, not whether to
    maximise it, and inventing a default here would put a sign convention in a place the
    caller cannot see. `row_index` names the constraint whose expression was not linear
    (-1 for the objective or for none).
    """

    var status: Int
    var n_vars: Int
    var n_constraints: Int
    var constant: Float64
    var row_index: Int
    var node_index: Int
    var op: Int
    var var_index: Int
    var c: List[Float64]
    var a: List[Float64]
    var senses: List[Int]
    var rhs: List[Float64]
    var message: String


@fieldwise_init
struct LPSolution(Copyable, Movable):
    """An optimal vertex with its duals, or a status and no numbers.

    On any status other than `LP_OPTIMAL` every list is EMPTY and `has_objective` is False.
    A half-solved program has no partial answer: the iterate a capped solver is sitting on
    is not a vertex of anything, and the vertex an unbounded program last visited is not
    an optimum.

    `basis` holds the column indices of the final basis. Structural columns are
    `[0, n_vars)`; then one slack column per non-equality row IN ROW ORDER, equality rows
    contributing none; then one artificial per row. A basic artificial at the end means the
    row was linearly dependent on the others, and its dual is 0.

    `slack[i]` is the DISTANCE from row `i`'s boundary, so it is >= 0 for a feasible point
    and 0 exactly when the row binds — which is what makes complementary slackness
    (`slack[i] > 0` implies `duals[i] == 0`) checkable by a caller.
    """

    var status: Int
    var has_objective: Bool
    var objective: Float64
    var n_vars: Int
    var n_constraints: Int
    var iterations: Int
    var phase1_iterations: Int
    var degenerate_pivots: Int
    var used_bland: Bool
    var infeasibility: Float64
    var unbounded_variable: Int
    var x: List[Float64]
    var duals: List[Float64]
    var reduced_costs: List[Float64]
    var activity: List[Float64]
    var slack: List[Float64]
    var binding: List[Bool]
    var basis: List[Int]


@fieldwise_init
struct RhsSensitivity(Copyable, Movable):
    """Per-row shadow price and the range of `b_i` over which it stays the shadow price.

    An unbounded side is a FLAG, never `±inf`: `has_upper[i] == False` means row `i`'s
    right-hand side can grow without limit before the basis changes, and `upper[i]` then
    holds `rhs[i]` as padding. An infinite bound would go on to do arithmetic in a caller's
    range check, and `inf - inf` is NaN; a cleared flag cannot.

    A row that cannot move AT ALL — a linearly dependent row still carrying a basic
    artificial — is reported with both flags SET and `lower[i] == upper[i] == rhs[i]`. That
    is a range of width zero, which is the honest answer, and it is deliberately not the same
    shape as a cleared flag: "no limit" and "no movement" are opposites and must not share a
    representation.
    """

    var status: Int
    var has_objective: Bool
    var objective: Float64
    var n_constraints: Int
    var duals: List[Float64]
    var rhs: List[Float64]
    var lower: List[Float64]
    var upper: List[Float64]
    var has_lower: List[Bool]
    var has_upper: List[Bool]
    var slack: List[Float64]
    var binding: List[Bool]


# ── the extractor ─────────────────────────────────────────────────────────────


fn _form_failure(
    status: Int, node_index: Int, op: Int, var_index: Int, n_vars: Int, message: String
) -> LinearForm:
    return LinearForm(
        status, False, n_vars, 0, 0.0, node_index, op, var_index, List[Float64](), message
    )


fn _first_var_in_subtree(nodes: List[ExprNode], start: Int) -> Int:
    """Lowest-indexed variable referenced under `start`, or -1 when there is none.

    The LOWEST rather than the first encountered, so the reported variable does not depend
    on the traversal order — a report that changes with an implementation detail is a
    report nobody can write a test against. `seen` makes a shared subtree cost one visit;
    without it a DAG would be walked once per path.
    """
    var n = len(nodes)
    if start < 0 or start >= n:
        return -1
    var seen = List[Bool]()
    for _ in range(n):
        seen.append(False)
    var stack = List[Int]()
    stack.append(start)
    seen[start] = True
    var best = -1
    while len(stack) > 0:
        var i = stack.pop()
        ref node = nodes[i]
        if node.op == OP_VAR_REF:
            if best < 0 or node.var_idx < best:
                best = node.var_idx
            continue
        var arity = model_op_arity(node.op)
        if arity >= 1 and node.left >= 0 and node.left < n and not seen[node.left]:
            seen[node.left] = True
            stack.append(node.left)
        if arity >= 2 and node.right >= 0 and node.right < n and not seen[node.right]:
            seen[node.right] = True
            stack.append(node.right)
        if arity >= 3 and node.extra >= 0 and node.extra < n and not seen[node.extra]:
            seen[node.extra] = True
            stack.append(node.extra)
    return best


fn _max_var_ref(nodes: List[ExprNode]) -> Int:
    """Highest variable index any `var_ref` node references, or -1 when there is none.

    Only `OP_VAR_REF` nodes are consulted, which is exactly the set `check_expr` range-checks:
    the `var_idx` slot of any other opcode is unused padding and reading it as a reference
    would inflate this bound to no purpose.
    """
    var best = -1
    for i in range(len(nodes)):
        ref node = nodes[i]
        if node.op == OP_VAR_REF and node.var_idx > best:
            best = node.var_idx
    return best


fn _max_var_ref_flat(ops: List[Int], var_idx: List[Int]) -> Int:
    """`_max_var_ref` over the wire form, before the columns are known to be parallel.

    The scan stops at the SHORTER of the two columns because a caller's payload may be
    malformed — `arena_flat_defect` / `model_validate` report that, but they run later, and
    indexing `ops[i]` off the end of a short `ops` first would be an uncatchable crash.
    """
    var n = len(var_idx)
    if len(ops) < n:
        n = len(ops)
    var best = -1
    for i in range(n):
        if ops[i] == OP_VAR_REF and var_idx[i] > best:
            best = var_idx[i]
    return best


fn _const_subtree(
    nodes: List[ExprNode], i: Int, n_vars: Int, zeros: List[Float64]
) -> ScalarResult:
    """Value of a variable-free subtree, via the frozen-safe evaluator in `model.mojo`.

    A literal short-circuits, which is the whole cost in the canonical `linear_arena`
    layout. Anything else is handed to `model.evaluate_expr` at the zero point — correct
    because the subtree mentions no variable, and chosen because that evaluator already
    reports `1/0`, `ln(-1)` and `sqrt(-4)` as statuses where `expr.eval_expr` folds them to
    plausible numbers. A second evaluator here would be a second set of domain rules to
    keep in step.
    """
    ref node = nodes[i]
    if node.op == OP_LITERAL:
        return ScalarResult(MODEL_OK, True, node.fval, -1, 1)
    return evaluate_expr(nodes, i, zeros, n_vars)


fn extract_linear(nodes: List[ExprNode], root: Int, n_vars: Int) -> LinearForm:
    """Exact `(coeffs, constant)` for an affine arena, or a status naming what is not affine.

    Mojo-level: the signature names `types.ExprNode`, so it is outside the runtime contract
    by design. `linear_extract_flat` is its marshalable counterpart.

    `n_vars` is the caller's DECLARED count and the returned `coeffs` is sized by the highest
    variable the arena actually REFERENCES, which may be fewer. `LinearForm.n_vars` reports
    the width that was used, so the form stays self-describing. The clamp is what keeps the
    allocation proportional to the payload: `n_vars` was otherwise bounded only by
    `MAX_CSR_DIM`, so a ONE-NODE literal arena with `n_vars = 1 << 26` returned MODEL_OK
    carrying a 2^26-long coefficient vector. Trailing coefficients dropped this way are
    necessarily 0.0, so no answer changes; a caller composing several forms into one matrix
    must pad them to a common width, which is what `lp_from_arenas` does.
    """
    if n_vars < 0 or n_vars > MAX_CSR_DIM:
        return _form_failure(
            MODEL_ERR_DIMENSION_TOO_LARGE, -1, -1, -1, 0, "variable count out of range"
        )
    # The clamp cannot change a verdict. When every reference is in range it only drops
    # trailing zero coefficients; when a reference is out of range it is inert (the clamp is
    # a minimum, so `n_eff` is still `n_vars`) and `check_expr` rejects the arena below.
    var n_eff = n_vars
    var referenced = _max_var_ref(nodes) + 1
    if referenced < n_eff:
        n_eff = referenced
    # Validated whole first: every index this walk uses — root, children, var_idx — is a
    # property `check_expr` proves, and an unvalidated read past a List end is an
    # uncatchable process crash rather than an exception.
    var check = check_expr(nodes, root, n_eff)
    if check.status != MODEL_OK:
        return _form_failure(check.status, check.node_index, -1, -1, n_eff, check.message)

    var n = len(nodes)
    # Ascending: children come strictly before parents, so one pass answers "does this
    # subtree mention a variable" for every node.
    var has_var = List[Bool]()
    for i in range(n):
        ref node = nodes[i]
        var arity = model_op_arity(node.op)
        var hv = node.op == OP_VAR_REF
        if not hv and arity >= 1 and has_var[node.left]:
            hv = True
        if not hv and arity >= 2 and has_var[node.right]:
            hv = True
        if not hv and arity >= 3 and has_var[node.extra]:
            hv = True
        has_var.append(hv)

    var zeros = List[Float64]()
    var coeffs = List[Float64]()
    for _ in range(n_eff):
        zeros.append(0.0)
        coeffs.append(0.0)
    var constant: Float64 = 0.0

    var mult = List[Float64]()
    var reach = List[Bool]()
    for _ in range(n):
        mult.append(0.0)
        reach.append(False)
    mult[root] = 1.0
    reach[root] = True

    # Descending: a node is processed only after every parent that references it, so its
    # multiplier is complete when it is read. This is what makes a shared subexpression
    # cost one visit instead of one per path.
    var i = n - 1
    while i >= 0:
        if not reach[i]:
            i -= 1
            continue
        ref node = nodes[i]
        var op = node.op
        var m = mult[i]

        if not has_var[i]:
            # A whole variable-free subtree folds, whatever opcodes it uses. This is the
            # only place `sqrt(4)` is accepted, and it is accepted as a number.
            var folded = _const_subtree(nodes, i, n_eff, zeros)
            if not folded.has_value:
                return _form_failure(
                    folded.status,
                    i,
                    op,
                    -1,
                    n_eff,
                    "constant subtree at node " + String(i) + " has no value: "
                    + model_status_name(folded.status),
                )
            constant += m * folded.value
            if not _finite(constant):
                return _form_failure(
                    MODEL_ERR_NON_FINITE_VALUE, i, op, -1, n_eff, "constant overflowed"
                )
            i -= 1
            continue

        if op == OP_VAR_REF:
            coeffs[node.var_idx] += m
        elif op == OP_ADD:
            mult[node.left] += m
            reach[node.left] = True
            mult[node.right] += m
            reach[node.right] = True
        elif op == OP_SUB:
            mult[node.left] += m
            reach[node.left] = True
            mult[node.right] -= m
            reach[node.right] = True
        elif op == OP_NEG:
            mult[node.left] -= m
            reach[node.left] = True
        elif op == OP_MUL:
            if has_var[node.left] and has_var[node.right]:
                return _form_failure(
                    LIN_ERR_NONLINEAR_PRODUCT,
                    i,
                    op,
                    _first_var_in_subtree(nodes, i),
                    n_eff,
                    "node " + String(i) + " multiplies two subexpressions that both"
                    + " contain a variable",
                )
            var child = node.left
            var other = node.right
            if not has_var[node.left]:
                child = node.right
                other = node.left
            var scale = _const_subtree(nodes, other, n_eff, zeros)
            if not scale.has_value:
                return _form_failure(
                    scale.status,
                    other,
                    nodes[other].op,
                    -1,
                    n_eff,
                    "constant factor at node " + String(other) + " has no value",
                )
            var scaled = m * scale.value
            if not _finite(scaled):
                return _form_failure(
                    MODEL_ERR_NON_FINITE_VALUE, i, op, -1, n_eff, "coefficient overflowed"
                )
            mult[child] += scaled
            reach[child] = True
        elif op == OP_DIV:
            if has_var[node.right]:
                return _form_failure(
                    LIN_ERR_VARIABLE_DIVISOR,
                    i,
                    op,
                    _first_var_in_subtree(nodes, node.right),
                    n_eff,
                    "node " + String(i) + " divides by a subexpression containing a"
                    + " variable, which is not affine in it",
                )
            var divisor = _const_subtree(nodes, node.right, n_eff, zeros)
            if not divisor.has_value:
                return _form_failure(
                    divisor.status,
                    node.right,
                    nodes[node.right].op,
                    -1,
                    n_eff,
                    "constant divisor at node " + String(node.right) + " has no value",
                )
            if divisor.value == 0.0:
                return _form_failure(
                    MODEL_ERR_DIV_BY_ZERO, i, op, -1, n_eff,
                    "node " + String(i) + " divides by zero",
                )
            var quotient = m / divisor.value
            if not _finite(quotient):
                return _form_failure(
                    MODEL_ERR_NON_FINITE_VALUE, i, op, -1, n_eff, "coefficient overflowed"
                )
            mult[node.left] += quotient
            reach[node.left] = True
        else:
            return _form_failure(
                LIN_ERR_NONLINEAR_OP,
                i,
                op,
                _first_var_in_subtree(nodes, i),
                n_eff,
                "node " + String(i) + " applies " + op_name(op)
                + " to a subexpression containing a variable",
            )
        i -= 1

    var n_terms = 0
    for j in range(n_eff):
        if not _finite(coeffs[j]):
            return _form_failure(
                MODEL_ERR_NON_FINITE_COEFFICIENT, -1, -1, j, n_eff,
                "coefficient of variable " + String(j) + " is not finite",
            )
        if coeffs[j] != 0.0:
            n_terms += 1
    return LinearForm(
        MODEL_OK, True, n_eff, n_terms, constant, -1, -1, -1, coeffs^, ""
    )


fn linear_extract_flat(
    ops: List[Int], values: List[Float64], var_idx: List[Int],
    lefts: List[Int], rights: List[Int], extras: List[Int],
    root: Int, n_vars: Int,
) -> LinearForm:
    """`extract_linear` over the six-column wire form of an arena."""
    var defect = arena_flat_defect(ops, values, var_idx, lefts, rights, extras)
    if defect != MODEL_OK:
        return _form_failure(defect, -1, -1, -1, n_vars, model_status_name(defect))
    var nodes = arena_from_flat(ops, values, var_idx, lefts, rights, extras)
    return extract_linear(nodes, root, n_vars)


fn linear_form_value(
    coeffs: List[Float64], constant: Float64, x: List[Float64]
) -> FormValue:
    """`Σ coeffs[j] x_j + constant`, or a status. The dot product is `linalg.vec_dot`.

    `vec_dot` truncates to the shorter of its two arguments, which is why the length check
    happens HERE: a caller who passes a 3-coefficient form a 2-element point would
    otherwise get the value of a different form.
    """
    if len(coeffs) != len(x):
        return FormValue(MODEL_ERR_LENGTH_MISMATCH, False, 0.0)
    if not _finite(constant):
        return FormValue(MODEL_ERR_NON_FINITE_COEFFICIENT, False, 0.0)
    for j in range(len(coeffs)):
        if not _finite(coeffs[j]):
            return FormValue(MODEL_ERR_NON_FINITE_COEFFICIENT, False, 0.0)
        if not _finite(x[j]):
            return FormValue(MODEL_ERR_NON_FINITE_POINT, False, 0.0)
    var total = constant + vec_dot(coeffs, x)
    if not _finite(total):
        return FormValue(MODEL_ERR_NON_FINITE_VALUE, False, 0.0)
    return FormValue(MODEL_OK, True, total)


fn lp_dual_objective(duals: List[Float64], rhs: List[Float64]) -> FormValue:
    """`bᵀy` — the dual objective, so strong duality is checkable by the caller.

    Exists because the frozen `linear_programming.dual_value` does not compute it: that
    function calls `lp_solve_2var` and returns the PRIMAL optimum, and returns 0.0 when
    the program is infeasible.
    """
    if len(duals) != len(rhs):
        return FormValue(MODEL_ERR_LENGTH_MISMATCH, False, 0.0)
    for i in range(len(duals)):
        if not _finite(duals[i]) or not _finite(rhs[i]):
            return FormValue(MODEL_ERR_NON_FINITE_VALUE, False, 0.0)
    var total = vec_dot(duals, rhs)
    if not _finite(total):
        return FormValue(MODEL_ERR_NON_FINITE_VALUE, False, 0.0)
    return FormValue(MODEL_OK, True, total)


# ── the simplex ───────────────────────────────────────────────────────────────


@fieldwise_init
struct _Simplex(Copyable, Movable):
    """The working tableau. Internal: never appears in a public signature.

    `t` is `m x width` row-major with the right-hand side in the last column
    (`width == n_cols + 1`). Columns are `[0, n_struct)` structural, then one slack per
    non-equality row in row order, then `m` artificials starting at `art0`. `flip[i]` is
    the ±1 the row was multiplied by so that every right-hand side is non-negative.
    """

    var status: Int
    var m: Int
    var n_struct: Int
    var n_cols: Int
    var width: Int
    var art0: Int
    var t: List[Float64]
    var basis: List[Int]
    var flip: List[Float64]
    var cost: List[Float64]
    var iterations: Int
    var phase1_iterations: Int
    var degenerate_pivots: Int
    var used_bland: Bool
    var infeasibility: Float64
    var unbounded_col: Int


fn _empty_simplex(status: Int) -> _Simplex:
    return _Simplex(
        status, 0, 0, 0, 1, 0, List[Float64](), List[Int](), List[Float64](),
        List[Float64](), 0, 0, 0, False, LP_INFEASIBILITY_ABSENT, -1,
    )


fn _basic_cost(s: _Simplex, cost: List[Float64]) -> Float64:
    var total: Float64 = 0.0
    for k in range(s.m):
        total += cost[s.basis[k]] * s.t[k * s.width + s.n_cols]
    return total


fn _phase(
    mut s: _Simplex, cost: List[Float64], bar_from: Int,
    max_iterations: Int, feas_tol: Float64, opt_tol: Float64,
) -> Int:
    """One simplex phase. `bar_from` is the first column forbidden to enter.

    Phase 1 passes `n_cols` (nothing barred); phase 2 passes `art0`, which keeps the
    artificials out of the basis without deleting their columns — those columns ARE `B⁻¹`
    and the duals are read from them at the end.
    """
    var m = s.m
    var ncols = s.n_cols
    var w = s.width
    var stall = 0
    var last = _basic_cost(s, cost)
    while True:
        # Reduced costs recomputed from scratch each iteration rather than carried in an
        # updated cost row: the carried row accumulates the error of every pivot, and its
        # drift shows up as an "optimal" verdict on a tableau that still has a profitable
        # column. One pass over the tableau is the same asymptotic cost as updating it.
        var d = List[Float64]()
        var is_basic = List[Bool]()
        for j in range(ncols):
            d.append(cost[j])
            is_basic.append(False)
        for k in range(m):
            is_basic[s.basis[k]] = True
            var cb = cost[s.basis[k]]
            if cb != 0.0:
                var base = k * w
                for j in range(ncols):
                    d[j] -= cb * s.t[base + j]

        var enter = -1
        if s.used_bland:
            # Bland: the LOWEST-index profitable column. Provably finite, which is the
            # entire reason to accept its slower descent once a stall is detected.
            for j in range(bar_from):
                if not is_basic[j] and d[j] < -opt_tol:
                    enter = j
                    break
        else:
            var best = -opt_tol
            for j in range(bar_from):
                if not is_basic[j] and d[j] < best:
                    best = d[j]
                    enter = j
        if enter < 0:
            return MODEL_OK

        var row = -1
        var best_ratio: Float64 = 0.0
        for k in range(m):
            var piv = s.t[k * w + enter]
            if piv > LP_PIVOT_MIN:
                var ratio = s.t[k * w + ncols] / piv
                if row < 0 or ratio < best_ratio - LP_TIE_EPS:
                    row = k
                    best_ratio = ratio
                elif ratio <= best_ratio + LP_TIE_EPS and s.basis[k] < s.basis[row]:
                    # Bland's leaving rule: lowest basic-variable index among ties. Applied
                    # always, so the pivot sequence does not depend on which rule chose the
                    # entering column.
                    row = k
                    best_ratio = ratio
        if row < 0:
            # No blocking row: the entering column can grow without limit, so the program
            # is unbounded. The current vertex is NOT the answer and is not returned.
            s.unbounded_col = enter
            return LP_UNBOUNDED
        if s.iterations >= max_iterations:
            return LP_ITERATION_LIMIT
        if best_ratio <= feas_tol:
            s.degenerate_pivots += 1

        var prow = row * w
        var pv = s.t[prow + enter]
        for j in range(w):
            var nv = s.t[prow + j] / pv
            if not _finite(nv):
                return LP_NUMERICAL_BREAKDOWN
            s.t[prow + j] = nv
        # Set exactly rather than trusting `pv / pv`: the pivot column must be a clean unit
        # vector or the identity the duals are read from drifts.
        s.t[prow + enter] = 1.0
        for k in range(m):
            if k == row:
                continue
            var base = k * w
            var f = s.t[base + enter]
            if f != 0.0:
                for j in range(w):
                    var nv = s.t[base + j] - f * s.t[prow + j]
                    if not _finite(nv):
                        return LP_NUMERICAL_BREAKDOWN
                    s.t[base + j] = nv
                s.t[base + enter] = 0.0
        s.basis[row] = enter
        s.iterations += 1

        var now = _basic_cost(s, cost)
        if now > last - opt_tol:
            stall += 1
            if stall > m + ncols:
                # More consecutive non-improving pivots than there are basis changes
                # available means the rule is walking a cycle. Bland's rule from here on,
                # for the rest of the solve.
                s.used_bland = True
        else:
            stall = 0
        last = now


fn _drive_out_artificials(mut s: _Simplex) -> Int:
    """Pivot every basic artificial out of the basis after a feasible phase 1.

    When a row has no non-artificial column with a usable pivot, that row is zero over
    every column phase 2 may enter, so its artificial stays basic at 0 and can never become
    positive — the row was linearly dependent on the others. Nothing needs to be deleted,
    and the row's dual comes out 0, which is the right answer for a redundant row.

    Returns `LP_NUMERICAL_BREAKDOWN` on the FIRST non-finite cell, with the same guard
    `_phase` applies to every cell it writes. Without it an inf reaches the tableau, phase 2
    computes `nan` reduced costs from it, `nan < best` is False for every column, so no
    entering column is found and the solve terminates claiming OPTIMALITY on a tableau that
    means nothing. A wrong answer wearing a success status is exactly what this module exists
    to remove, so the guard cannot be omitted from a loop that writes cells.
    """
    var w = s.width
    for k in range(s.m):
        if s.basis[k] < s.art0:
            continue
        var base = k * w
        var pick = -1
        for j in range(s.art0):
            if fabs(s.t[base + j]) > LP_PIVOT_MIN:
                pick = j
                break
        if pick < 0:
            continue
        var pv = s.t[base + pick]
        for j in range(w):
            var nv = s.t[base + j] / pv
            if not _finite(nv):
                return LP_NUMERICAL_BREAKDOWN
            s.t[base + j] = nv
        s.t[base + pick] = 1.0
        for r in range(s.m):
            if r == k:
                continue
            var rbase = r * w
            var f = s.t[rbase + pick]
            if f != 0.0:
                for j in range(w):
                    var nv = s.t[rbase + j] - f * s.t[base + j]
                    if not _finite(nv):
                        return LP_NUMERICAL_BREAKDOWN
                    s.t[rbase + j] = nv
                s.t[rbase + pick] = 0.0
        s.basis[k] = pick
        s.iterations += 1
    return MODEL_OK


fn _artificial_values(s: _Simplex) -> List[Float64]:
    """Row-by-row phase-1 residual: row `i`'s artificial value, 0.0 when it is not basic.

    Artificial `i` enters as column `e_i`, so row `i` of the tableau states
    `d_i A_i x + coef_i s_i + art_i = d_i b_i` and `art_i` is exactly the amount by which
    THAT ONE ROW is unmet at the current point. Only a basic variable can be nonzero, so one
    pass over the basis fills every row.
    """
    var out = List[Float64]()
    for _ in range(s.m):
        out.append(0.0)
    for k in range(s.m):
        var i = s.basis[k] - s.art0
        if i >= 0 and i < s.m:
            var v = s.t[k * s.width + s.n_cols]
            if v < 0.0:
                # A minutely negative basic value is rounding, never a negative violation.
                v = 0.0
            out[i] = v
    return out^


fn _simplex_run(
    c: List[Float64], a: List[Float64], m: Int, n: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool,
    max_iterations: Int, feas_tol: Float64, opt_tol: Float64,
) -> _Simplex:
    """Build the tableau and run both phases. Every argument is already validated."""
    var n_slack = 0
    for i in range(m):
        if senses[i] != SENSE_EQ:
            n_slack += 1
    var art0 = n + n_slack
    var ncols = art0 + m
    var w = ncols + 1
    # DIVISION, not `m * w <= LP_MAX_TABLEAU_CELLS`: the product wraps, and a wrapped
    # comparison passes for a shape that then allocates nothing and indexes everything.
    if m > 0 and m > LP_MAX_TABLEAU_CELLS // w:
        return _empty_simplex(MODEL_ERR_DIMENSION_TOO_LARGE)

    var t = List[Float64]()
    for _ in range(m * w):
        t.append(0.0)
    var flip = List[Float64]()
    var basis = List[Int]()
    var slack_of = List[Int]()
    var sc = n
    for i in range(m):
        var d: Float64 = 1.0
        if rhs[i] < 0.0:
            # Flip the row so every right-hand side is non-negative, which is what makes
            # the starting basis feasible. The flip is remembered because the dual of the
            # caller's row is the flipped row's dual times the same ±1.
            d = -1.0
        flip.append(d)
        var base = i * w
        for j in range(n):
            t[base + j] = d * a[i * n + j]
        var mine = -1
        if senses[i] != SENSE_EQ:
            var coef: Float64 = 1.0
            if senses[i] == SENSE_GE:
                coef = -1.0
            t[base + sc] = d * coef
            mine = sc
            sc += 1
        slack_of.append(mine)
        t[base + art0 + i] = 1.0
        t[base + ncols] = d * rhs[i]
        # Prefer the slack as the starting basic variable wherever its coefficient is +1
        # after the flip: an all-`<=` program with b >= 0 then needs ZERO phase-1
        # iterations. The artificial column still exists either way, because it is the
        # column the duals are read from.
        if mine >= 0 and t[base + mine] == 1.0:
            basis.append(mine)
        else:
            basis.append(art0 + i)

    var cost1 = List[Float64]()
    var cost2 = List[Float64]()
    for j in range(ncols):
        if j >= art0:
            cost1.append(1.0)
        else:
            cost1.append(0.0)
        if j < n:
            # `minimization_value` is model.mojo's one place where a maximisation becomes a
            # minimisation, reused here rather than a second `-c` written by hand.
            cost2.append(minimization_value(c[j], maximize))
        else:
            cost2.append(0.0)

    var s = _Simplex(
        MODEL_OK, m, n, ncols, w, art0, t^, basis^, flip^, cost2.copy(),
        0, 0, 0, False, LP_INFEASIBILITY_ABSENT, -1,
    )

    var st1 = _phase(s, cost1, ncols, max_iterations, feas_tol, opt_tol)
    s.phase1_iterations = s.iterations
    if st1 != MODEL_OK:
        # Phase 1 minimises a sum of non-negative variables, so it is bounded below by 0.
        # An "unbounded" verdict there is arithmetic breaking down, not a property of the
        # program, and saying so is more useful than passing the wrong outcome through.
        if st1 == LP_UNBOUNDED:
            s.status = LP_NUMERICAL_BREAKDOWN
        else:
            s.status = st1
        return s^

    var residual = _basic_cost(s, cost1)
    if residual < 0.0:
        residual = 0.0
    # The TOTAL residual, reported as a magnitude summary. The verdict below is not taken
    # from it, because a total is not what feasibility is about.
    s.infeasibility = residual

    # Feasibility is decided PER ROW, each row against its OWN magnitude. A row is satisfied
    # or it is not; there is no aggregate of which a row's violation is a component, so a
    # threshold scaled by `Σ_i |b_i|` cannot work — it lets one unrelated large-rhs row raise
    # the tolerance for every other row without limit. 200 ordinary `x0 <= 1e7` capacity rows
    # beside the contradictory pair `x1 >= 3, x1 <= 2` put that threshold above 1.0, so a
    # program with NO feasible point came back LP_OPTIMAL with x = (0, 3) — violating
    # `x1 <= 2` by a full unit — plus duals, reduced costs and a basis. Even one large row
    # was enough: `{x >= 5, x <= 4.5, x <= 1e9}` reported optimal at x = 5.
    #
    # Each row's budget is the caller's ABSOLUTE tolerance plus a ROUNDING allowance sized by
    # what the elimination could have accumulated at that row's magnitude — see
    # `_lp_row_gap_budget`, which is the same budget `_solution_from_simplex` calls a row
    # BINDING by, so "row i is satisfied" and "row i binds" are one threshold. It is
    # deliberately not `feas_tol * (1 + |b_i|)`: that form is per-row and still wrong,
    # because the fraction shrinks with the row's magnitude while the violation does not, so
    # `{x >= 1e9, x <= 1e9 - 1}` (residual exactly 1.0, no feasible point) came back
    # LP_OPTIMAL at x = 1e9.
    var arts = _artificial_values(s)
    for i in range(m):
        var budget = _lp_row_gap_budget(feas_tol, rhs[i])
        if arts[i] > budget:
            s.status = LP_INFEASIBLE
            return s^

    var st_drive = _drive_out_artificials(s)
    if st_drive != MODEL_OK:
        s.status = st_drive
        return s^
    var st2 = _phase(s, cost2, art0, max_iterations, feas_tol, opt_tol)
    s.status = st2
    return s^


fn _no_solution(
    status: Int, n_vars: Int, n_cons: Int, s: _Simplex, unbounded_variable: Int
) -> LPSolution:
    return LPSolution(
        status, False, 0.0, n_vars, n_cons, s.iterations, s.phase1_iterations,
        s.degenerate_pivots, s.used_bland, s.infeasibility, unbounded_variable,
        List[Float64](), List[Float64](), List[Float64](), List[Float64](),
        List[Float64](), List[Bool](), List[Int](),
    )


fn _lp_input_defect(
    c: List[Float64], constant: Float64, a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], max_iterations: Int,
    feasibility_tol: Float64, optimality_tol: Float64,
) -> Int:
    """`MODEL_OK` when every length, shape, sense and magnitude is one the solver can use.

    Called before anything is indexed. `dims_fit` does the dense shape check because
    `rows * cols == len(a)` is a wrapping multiply and therefore not a bound.

    The SHAPE half is the reference statement of this invariant for the package, but it is NOT
    yet the only one, and this docstring will not claim otherwise: `integer._milp_input_defect`
    and `explain._core_input_defect` are hand-copies that have drifted. Today the MILP copy
    adds `MAX_CSR_DIM` and tableau-area ceilings under `MODEL_ERR_DIMENSION_TOO_LARGE` (this
    one defers that to the tableau build in `_phase`), and the core copy is weaker still — it
    bounds `rows` by `EXPLAIN_MAX_CORE_ROWS` but checks neither sense validity nor the
    finiteness of `a` and `rhs`, leaving both to `lp_solve`. Both should delegate here and add
    only the checks their own extra arguments need (`var_kind` and `max_nodes` for the MILP, the
    objective-free shape for the core), because the copy that drifts is the copy that reads past
    a List end.

    Nothing stops that delegation: the underscore prefix keeps this out of the runtime contract
    (a validator is not a driver), not out of reach — Mojo has no access control, so a sibling
    does `from optimization.linear import _lp_input_defect` and gets the same verdict under the
    same status code.

    The POLICY half already IS single. `model._policy_parts_defect` reaches
    `model.policy_defect`, the package's one definition of a policy a solver will honour —
    including why a zero `optimality_tol` is refused rather than read as "be exact" (a zero
    reduced-cost threshold makes every rounding-error-negative column look profitable, so the
    solver pivots forever on an optimal tableau). This function does not restate it.
    """
    if rows < 0 or cols < 0:
        return MODEL_ERR_DENSE_SHAPE
    if not dims_fit(rows, cols, len(a)):
        return MODEL_ERR_DENSE_SHAPE
    if len(c) != cols:
        return MODEL_ERR_LENGTH_MISMATCH
    if len(senses) != rows or len(rhs) != rows:
        return MODEL_ERR_LENGTH_MISMATCH
    # An LP has no integrality tolerance, so a known-valid default stands in for the one
    # field this entry point does not take; see `_policy_parts_defect`.
    var policy_status = _policy_parts_defect(
        max_iterations, feasibility_tol, optimality_tol, DEFAULT_INTEGRALITY_TOL
    )
    if policy_status != MODEL_OK:
        return policy_status
    if not _finite(constant):
        return MODEL_ERR_NON_FINITE_COEFFICIENT
    for j in range(cols):
        if not _finite(c[j]):
            return MODEL_ERR_NON_FINITE_COEFFICIENT
    for i in range(len(a)):
        if not _finite(a[i]):
            return MODEL_ERR_NON_FINITE_COEFFICIENT
    for i in range(rows):
        if senses[i] != SENSE_LE and senses[i] != SENSE_EQ and senses[i] != SENSE_GE:
            return MODEL_ERR_SENSE
        if not _finite(rhs[i]):
            return MODEL_ERR_NON_FINITE_RHS
    return MODEL_OK


fn _duals_from_tableau(s: _Simplex, maximize: Bool) -> List[Float64]:
    """`∂objective/∂b_i` in the CALLER's sense, one per row.

    Artificial column `i` of the final tableau is column `i` of `B⁻¹` — artificial `i`
    started as `e_i` — so `π̂_i = c_Bᵀ B⁻¹ e_i` is a dot product down that column. The row
    flip that made `b >= 0` comes back out as the same ±1, and the minimisation-to-caller
    sign flip is `minimization_value`, which is its own inverse.
    """
    var out = List[Float64]()
    for i in range(s.m):
        var acc: Float64 = 0.0
        for k in range(s.m):
            var cb = s.cost[s.basis[k]]
            if cb != 0.0:
                acc += cb * s.t[k * s.width + s.art0 + i]
        out.append(minimization_value(s.flip[i] * acc, maximize))
    return out^


fn _solution_from_simplex(
    s: _Simplex, c: List[Float64], constant: Float64, a: List[Float64],
    rows: Int, cols: Int, rhs: List[Float64], maximize: Bool, feasibility_tol: Float64,
) -> LPSolution:
    """Read the answer off a finished tableau: `x`, duals, reduced costs, activity, slack.

    Separated from `lp_solve` so that `lp_rhs_ranges` can report a solution AND its ranges
    from ONE `_simplex_run`. It called `lp_solve` and then `_simplex_run` again with identical
    arguments, so every call to a registered public function paid two full two-phase solves
    for one answer.
    """
    if s.status != MODEL_OK:
        var col = -1
        if s.status == LP_UNBOUNDED and s.unbounded_col >= 0 and s.unbounded_col < cols:
            col = s.unbounded_col
        return _no_solution(s.status, cols, rows, s, col)

    var x = List[Float64]()
    for _ in range(cols):
        x.append(0.0)
    for k in range(rows):
        if s.basis[k] < cols:
            x[s.basis[k]] = s.t[k * s.width + s.n_cols]

    var duals = _duals_from_tableau(s, maximize)

    var activity = List[Float64]()
    var slack = List[Float64]()
    var binding = List[Bool]()
    for i in range(rows):
        var row = List[Float64]()
        for j in range(cols):
            row.append(a[i * cols + j])
        var value = vec_dot(row, x)
        activity.append(value)
        var gap = fabs(rhs[i] - value)
        slack.append(gap)
        # "Binds" means the returned point is ON this row, so the only thing the threshold may
        # absorb is what floating point cannot say about THIS gap: the caller's absolute
        # `feasibility_tol` plus a rounding allowance at row `i`'s own magnitude. That is
        # exactly the budget phase 1 accepted the row's residual under, so a row cannot be
        # called satisfied here and violated there — see `_lp_row_gap_budget`.
        #
        # It was `feasibility_tol * (1.0 + fabs(rhs[i]))`, justified as "relative to |rhs|,
        # because binds is a statement about the caller's units". The intuition is right and
        # that implementation of it is not: `feasibility_tol` as the RELATIVE multiplier makes
        # the threshold `1e-9 * (1 + 1e9)` = 1.000000001 at b = 1e9, so `max x s.t.
        # {x <= 1e9, x <= 1e9 - 0.9}` reported row 0 — with 0.8999999761581421 of real slack —
        # as BINDING, and `explain.binding_constraints` then presents that row's dual as an
        # actionable shadow price while `lp_rhs_ranges` ties its interval to the same claim.
        # A row with b = 1e6 whose gap is 1e-7 still reads as binding under the form below:
        # 1024 ulps at 1e6 is 2.3e-7, which is what rounding at that magnitude actually costs.
        binding.append(gap <= _lp_row_gap_budget(feasibility_tol, rhs[i]))

    var reduced = List[Float64]()
    for j in range(cols):
        var acc = c[j]
        for i in range(rows):
            acc -= a[i * cols + j] * duals[i]
        reduced.append(acc)

    var objective = constant + vec_dot(c, x)
    if not _finite(objective):
        return _no_solution(MODEL_ERR_NON_FINITE_VALUE, cols, rows, s, -1)

    return LPSolution(
        LP_OPTIMAL, True, objective, cols, rows, s.iterations, s.phase1_iterations,
        s.degenerate_pivots, s.used_bland, s.infeasibility, -1,
        x^, duals^, reduced^, activity^, slack^, binding^, s.basis.copy(),
    )


fn lp_solve(
    c: List[Float64], constant: Float64,
    a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool,
    max_iterations: Int, feasibility_tol: Float64, optimality_tol: Float64,
) -> LPSolution:
    """Optimise `cᵀx + constant` over `A x {senses} b`, `x >= 0`, with duals.

    `maximize` is a flag, never a negated objective vector: the reported optimum, duals and
    reduced costs are all in the sense the caller asked for, and a caller comparing two
    solutions is not comparing numbers whose sign convention it cannot see.
    """
    var defect = _lp_input_defect(
        c, constant, a, rows, cols, senses, rhs, max_iterations,
        feasibility_tol, optimality_tol,
    )
    if defect != MODEL_OK:
        return _no_solution(defect, 0, 0, _empty_simplex(defect), -1)

    var s = _simplex_run(
        c, a, rows, cols, senses, rhs, maximize, max_iterations,
        feasibility_tol, optimality_tol,
    )
    return _solution_from_simplex(
        s, c, constant, a, rows, cols, rhs, maximize, feasibility_tol
    )


fn lp_solve_default(
    c: List[Float64], a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool,
) -> LPSolution:
    """`lp_solve` with no objective constant and `model.mojo`'s default policy."""
    return lp_solve(
        c, 0.0, a, rows, cols, senses, rhs, maximize,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
    )


fn lp_rhs_ranges(
    c: List[Float64], constant: Float64,
    a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool,
    max_iterations: Int, feasibility_tol: Float64, optimality_tol: Float64,
) -> RhsSensitivity:
    """Shadow price per row plus the range of `b_i` over which it remains the shadow price.

    The range is the interval over which the OPTIMAL BASIS survives: `x_B = B⁻¹b`, and
    moving `b_i` by `Δ` moves `x_B` along column `i` of `B⁻¹`, so the range is where every
    basic variable stays non-negative. Outside it the dual is a different number, which is
    why reporting a dual without its range invites a caller to extrapolate a linear
    prediction that stops being true at a vertex it cannot see.

    Rejected alternative: the frozen `linear_programming.sensitivity_rhs`, which re-solves
    at `b_i + delta` and subtracts. That answers a different question (the change at ONE
    offset, not the interval), it costs two full solves, and it silently contributes 0.0
    for whichever solve came back empty — so a delta that makes the program infeasible is
    reported as a finite sensitivity.

    A row whose basic variable is an ARTIFICIAL is reported PINNED — `lower == upper == b_i`
    with both flags set — not open. `x_B >= 0` is the wrong condition for such a row: a basic
    artificial must stay at EXACTLY zero or the perturbed program has no feasible point, so
    any perturbation that moves it is inadmissible however small. See the loop below.
    """
    var defect = _lp_input_defect(
        c, constant, a, rows, cols, senses, rhs, max_iterations,
        feasibility_tol, optimality_tol,
    )
    if defect != MODEL_OK:
        return RhsSensitivity(
            defect, False, 0.0, 0, List[Float64](), List[Float64](), List[Float64](),
            List[Float64](), List[Bool](), List[Bool](), List[Float64](), List[Bool](),
        )
    # ONE `_simplex_run`, whose tableau answers both questions: the solution is read off it
    # by `_solution_from_simplex` and the ranges below come from the same `B⁻¹` block.
    var s = _simplex_run(
        c, a, rows, cols, senses, rhs, maximize, max_iterations,
        feasibility_tol, optimality_tol,
    )
    var solution = _solution_from_simplex(
        s, c, constant, a, rows, cols, rhs, maximize, feasibility_tol
    )
    if solution.status != LP_OPTIMAL:
        # No optimal basis means no basis to hold fixed, so there is no range. An
        # infeasible or unbounded program has no shadow prices either.
        return RhsSensitivity(
            solution.status, False, 0.0, rows, List[Float64](), List[Float64](),
            List[Float64](), List[Float64](), List[Bool](), List[Bool](),
            List[Float64](), List[Bool](),
        )

    # `_drive_out_artificials` deliberately leaves an artificial BASIC on a linearly dependent
    # row, which is the NORM in the shapes callers range over: a balanced transportation
    # problem or any flow-conservation block is rank-deficient by one. Such an artificial sits
    # at 0 and must STAY at 0 — it is not a variable of the caller's program, so a positive
    # value is not a feasible point of anything.
    var artificial_row = List[Bool]()
    for k in range(rows):
        artificial_row.append(s.basis[k] >= s.art0)

    var lower = List[Float64]()
    var upper = List[Float64]()
    var has_lower = List[Bool]()
    var has_upper = List[Bool]()
    for i in range(rows):
        var down_ok = False
        var up_ok = False
        var pinned = False
        var down: Float64 = 0.0
        var up: Float64 = 0.0
        for k in range(rows):
            var col = s.t[k * s.width + s.art0 + i]
            var xb = s.t[k * s.width + s.n_cols]
            if artificial_row[k]:
                # Moving b_i by Δ moves this basic artificial by `col * Δ`, and any nonzero
                # movement makes the program infeasible rather than merely re-basing it. So
                # the ordinary `x_B >= 0` test does not apply to this row: it admits a whole
                # interval where nothing is feasible. A `col` of zero imposes nothing.
                if col > LP_PIVOT_MIN or col < -LP_PIVOT_MIN:
                    pinned = True
                continue
            if col > LP_PIVOT_MIN:
                var cand = -xb / col
                if not down_ok or cand > down:
                    down = cand
                    down_ok = True
            elif col < -LP_PIVOT_MIN:
                var cand = xb / (-col)
                if not up_ok or cand < up:
                    up = cand
                    up_ok = True
        if pinned:
            # A zero-width range: the reported shadow price holds at this right-hand side and
            # at no other. Reported as two PRESENT ends that coincide, because a cleared
            # `has_upper` reads as "can grow without limit" — the exact opposite of the truth,
            # and the wrong answer this branch exists to prevent.
            lower.append(rhs[i])
            upper.append(rhs[i])
            has_lower.append(True)
            has_upper.append(True)
            continue
        # The tableau is in the FLIPPED row space, so the admissible interval for the
        # caller's b_i is the flipped interval divided by the same ±1 — which swaps the two
        # ends when the row was flipped.
        var lo_ok = down_ok
        var hi_ok = up_ok
        var lo = down
        var hi = up
        if s.flip[i] < 0.0:
            lo_ok = up_ok
            hi_ok = down_ok
            lo = -up
            hi = -down
        if lo_ok:
            lower.append(rhs[i] + lo)
        else:
            lower.append(rhs[i])
        if hi_ok:
            upper.append(rhs[i] + hi)
        else:
            upper.append(rhs[i])
        has_lower.append(lo_ok)
        has_upper.append(hi_ok)

    return RhsSensitivity(
        LP_OPTIMAL, True, solution.objective, rows, solution.duals.copy(), rhs.copy(),
        lower^, upper^, has_lower^, has_upper^, solution.slack.copy(),
        solution.binding.copy(),
    )


# ── arenas to LP data ─────────────────────────────────────────────────────────


fn _matrix_failure(
    status: Int, n_vars: Int, n_cons: Int, row_index: Int,
    node_index: Int, op: Int, var_index: Int, message: String,
) -> LPMatrix:
    return LPMatrix(
        status, n_vars, n_cons, 0.0, row_index, node_index, op, var_index,
        List[Float64](), List[Float64](), List[Int](), List[Float64](), message,
    )


fn _append_padded(mut out: List[Float64], coeffs: List[Float64], width: Int):
    """Append exactly `width` coefficients, zero-filling past the end of `coeffs`.

    `extract_linear` sizes its `coeffs` by the highest variable ITS OWN arena references, so
    in a three-variable model a row that mentions only `x0` comes back with one coefficient.
    Reading `coeffs[j]` up to a common width would then be a read past a List end, which is
    an uncatchable process crash and not an exception. The missing entries are 0.0 by
    construction: a variable the row does not mention has no coefficient in it.
    """
    for j in range(width):
        if j < len(coeffs):
            out.append(coeffs[j])
        else:
            out.append(0.0)


fn lp_from_arenas(
    obj_ops: List[Int], obj_values: List[Float64], obj_var_idx: List[Int], obj_lefts: List[Int],
    obj_rights: List[Int], obj_extras: List[Int], obj_root: Int, con_ptr: List[Int],
    con_roots: List[Int], con_senses: List[Int], con_rhs: List[Float64], con_ops: List[Int],
    con_values: List[Float64], con_var_idx: List[Int], con_lefts: List[Int],
    con_rights: List[Int], con_extras: List[Int], n_vars: Int,
) -> LPMatrix:
    """Recover `(c, constant, A, senses, rhs)` from a model's objective and constraint arenas.

    This is the bridge that makes the extractor worth having: the columns it takes are
    exactly `model.ModelFlat`'s, so a general model built by `model.linear_model_flat` — or
    by any caller who wrote arenas — becomes solver input, and a nonlinear constraint is a
    status naming the ROW, the node and the variable instead of a linearised lie.

    Every structural guard is delegated to `model.model_validate` by assembling a
    `ModelFlat` and validating it: parallel columns, `con_ptr` starting at 0 and
    non-decreasing and ending at the node count, one root/sense/rhs per constraint, roots
    in range, variable references inside `[0, n_vars)`, finite literals and right-hand
    sides. Re-deriving those checks here would be a second implementation of the invariant,
    and the one that drifts is the one that reads past a List end.

    A constraint's own constant moves to the right-hand side: `2x + 3 <= 7` is returned as
    `2x <= 4`.

    `n_vars` is the caller's DECLARED count and the recovered matrix is `n_constraints` by
    the number of variables the arenas actually REFERENCE, which `n_vars` reports. Nothing
    otherwise tied the declared count to the payload — it was bounded only by `MAX_CSR_DIM`
    — while it sizes five parallel per-variable columns here, one `OptVar` with a `String`
    name each inside `model_from_flat`, and two more per-variable vectors inside
    `extract_linear`: about 200 bytes per declared variable, measured at 1.29 GB for
    `n_vars = 2^22` and 3.50 GB for `2^24` against a payload of one node and one integer.
    A variable no expression mentions has coefficient 0 in every row and in the objective,
    so dropping it cannot change any answer — which is why this clamps rather than rejects,
    and why the caller's own per-variable data (a `var_kind` column, a start point) is
    length-checked against `n_vars` of the RESULT by whoever consumes it.
    """
    if n_vars < 0 or n_vars > MAX_CSR_DIM:
        return _matrix_failure(
            MODEL_ERR_DIMENSION_TOO_LARGE, 0, 0, -1, -1, -1, -1,
            "variable count out of range",
        )
    var n_eff = n_vars
    var referenced = _max_var_ref_flat(obj_ops, obj_var_idx) + 1
    var con_referenced = _max_var_ref_flat(con_ops, con_var_idx) + 1
    if con_referenced > referenced:
        referenced = con_referenced
    if referenced < n_eff:
        n_eff = referenced
    var n_cons = 0
    if len(con_ptr) > 0:
        n_cons = len(con_ptr) - 1
    if n_eff > 0 and n_cons > LP_MAX_TABLEAU_CELLS // n_eff:
        # The dense A allocates one cell per (row, variable) whatever the sparsity, so it
        # is governed by the same cell ceiling as the tableau. Division, never a multiply.
        return _matrix_failure(
            MODEL_ERR_DIMENSION_TOO_LARGE, n_eff, n_cons, -1, -1, -1, -1,
            "dense coefficient matrix would exceed the cell ceiling",
        )

    var var_lower = List[Float64]()
    var var_upper = List[Float64]()
    var var_kind = List[Int]()
    var var_flags = List[Int]()
    var var_start = List[Float64]()
    for _ in range(n_eff):
        var_lower.append(0.0)
        var_upper.append(0.0)
        var_kind.append(VAR_CONTINUOUS)
        # `x >= 0` is this module's variable convention, stated as the flag model.mojo
        # defines rather than as a -inf/+inf pair: a bound slot must stay finite even when
        # unused, because an "unused" NaN is how NaN reaches arithmetic three modules on.
        var_flags.append(VAR_FLAG_HAS_LOWER)
        var_start.append(0.0)

    var flat = ModelFlat(
        var_lower^, var_upper^, var_kind^, var_flags^, var_start^,
        False,
        obj_root,
        obj_ops.copy(), obj_values.copy(), obj_var_idx.copy(),
        obj_lefts.copy(), obj_rights.copy(), obj_extras.copy(),
        con_ptr.copy(), con_roots.copy(), con_senses.copy(), con_rhs.copy(),
        con_ops.copy(), con_values.copy(), con_var_idx.copy(),
        con_lefts.copy(), con_rights.copy(), con_extras.copy(),
        DEFAULT_MAX_ITERATIONS, DEFAULT_MAX_TIME_MS, DEFAULT_FEASIBILITY_TOL,
        DEFAULT_OPTIMALITY_TOL, DEFAULT_INTEGRALITY_TOL,
    )
    var verdict = model_validate(flat)
    if verdict.status != MODEL_OK:
        return _matrix_failure(
            verdict.status, n_eff, n_cons, verdict.constraint_index,
            verdict.node_index, -1, verdict.var_index, verdict.message,
        )

    var model = model_from_flat(flat)
    var objective = extract_linear(model.obj_nodes, model.obj_root, n_eff)
    if not objective.is_linear:
        return _matrix_failure(
            objective.status, n_eff, n_cons, -1, objective.node_index, objective.op,
            objective.var_index, "objective: " + objective.message,
        )

    var a = List[Float64]()
    var senses = List[Int]()
    var rhs = List[Float64]()
    for k in range(len(model.constraints)):
        ref con = model.constraints[k]
        var form = extract_linear(con.nodes, con.root, n_eff)
        if not form.is_linear:
            return _matrix_failure(
                form.status, n_eff, n_cons, k, form.node_index, form.op,
                form.var_index, "constraint " + String(k) + ": " + form.message,
            )
        _append_padded(a, form.coeffs, n_eff)
        var moved = con.rhs - form.constant
        if not _finite(moved):
            return _matrix_failure(
                MODEL_ERR_NON_FINITE_RHS, n_eff, n_cons, k, -1, -1, -1,
                "constraint " + String(k) + " right-hand side overflowed when its"
                + " constant was moved across",
            )
        senses.append(con.sense)
        rhs.append(moved)

    # The objective is padded to the same width as the rows: `len(c) == cols` is what
    # `lp_solve` requires, and the objective arena may reference fewer variables than the
    # constraints do.
    var c_out = List[Float64]()
    _append_padded(c_out, objective.coeffs, n_eff)

    return LPMatrix(
        MODEL_OK, n_eff, n_cons, objective.constant, -1, -1, -1, -1,
        c_out^, a^, senses^, rhs^, "",
    )
