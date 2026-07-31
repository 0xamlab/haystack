"""
optimization.explain — a status code turned into a reason the caller can act on.

Why this file exists
--------------------
`optimization.linear` answers *what* the optimum is. It does not answer the three
questions a caller actually asks next, and the tree answers none of them honestly today:

  * *which constraints are the ones that cost me, and what is each one worth?* The frozen
    `linear_programming.dual_value` is named for this and computes it for no program at
    all — grep it: its body calls `lp_solve_2var` and returns the PRIMAL optimum, with its
    parameters `(A, b, c)` in the opposite order to the solver it calls. So a caller who
    reads the name gets the objective back, in the right units, for a program that may not
    even be the one they meant.
  * *why is my model infeasible?* Nothing in the tree answers this. `lp_solve_2var` returns
    an empty list, which is also what it returns when the program is unbounded and what it
    returns when the input is malformed, so "infeasible" is not even distinguishable, let
    alone attributable to a subset of rows.
  * *where did the objective go?* Nothing decomposes it, and a decomposition whose parts do
    not sum to the whole is worse than none, because it looks like an audit.

Deliberately NOT `linear_programming.is_feasible`
-------------------------------------------------
The deletion filter below needs a feasibility test per candidate subset, and the tree has a
function called exactly that. It is not usable, for two independent reasons:

  1. It hardcodes the constraint system. Grep `linear_programming.mojo:43`: it tests
     `x >= 0` and `A x <= b` and nothing else. Every `>=` row and every `==` row in the
     caller's model is silently read as `<=`, so the contradictory PAIR this module exists
     to find (`x >= 5` with `x <= 3`) is not even representable — as `<=` rows both hold at
     `x = 0` and the pair reports feasible.
  2. It indexes `b[i]` for `i` over `len(A)` with no check on `len(b)`, so a short `b` is a
     read past the end of a List, which is an uncatchable process crash and not an
     exception (rule 1 of the package rules).

It also takes a point, so it can only ever refute infeasibility, never establish it: no
finite set of trial points shows that a system has NO solution. `lp_solve`'s phase 1 does
establish it — it minimises the sum of the artificials and then compares EACH row's measured
artificial against a budget built from that row's own right-hand side — so every feasibility
question here is asked as an LP status. That is the reuse rule and the correctness argument at
once. (The threshold used to be relative to `Σ|b|`, a sum over every row, and a 2e9
right-hand-side scale then swallowed a one-unit contradiction; the test suite still asserts
that model from this side, because a core is the shape that defect arrives in here.)

The trial solves use a ZERO objective
-------------------------------------
A core is a property of the constraints alone, so `infeasibility_core` does not take `c` or
`maximize` at all. The trial LPs are solved with an all-zero cost vector, which has two
consequences worth stating: phase 2 does zero iterations (no column is ever profitable,
so the answer is complete at the end of phase 1), and `LP_UNBOUNDED` — which is a FEASIBLE
outcome wearing a status a careless classifier would file under "failed" — cannot arise.
It is still classified as feasible below rather than as inconclusive, because a
classification that is only correct while an optimisation holds is a latent wrong answer.

Minimality is MEASURED, never inferred
--------------------------------------
Deletion filtering gives an irreducible set by an argument: when row `i` was tested, the
surviving set was a superset of the final core, dropping `i` from it was feasible, and
every subset of a feasible system is feasible — so dropping `i` from the final core is
feasible too. The argument is sound and it is not what this module reports on. It depends
on every trial solve being conclusive and on the feasible/infeasible classification being
exact at the caller's tolerance, and "the constraint is necessary because a theorem says
the solve I did earlier implies it" is precisely the kind of unverified claim this package
exists to remove. So after the filter, each surviving row is re-tested against the FINAL
core (one solve per core member) and `minimal` is set from those results. `minimal` is
False whenever any solve in the whole procedure was inconclusive, and `n_inconclusive`
says how many. The core itself is likewise re-solved and confirmed infeasible before it is
returned, because "a subset that is still infeasible" is the claim being made.

Complementary slackness is TWO conditions here, not one
-------------------------------------------------------
Complementary slackness says `slack_i > 0` implies `dual_i == 0`, and equivalently that
`dual_i != 0` implies row `i` is tight. Over one exact quantity those are contrapositives and
checking either would establish both. This audit is not given one quantity: it is given a
`binding` FLAG and a `slack` VECTOR as two independent inputs, so "the solver called this row
loose" and "this row has measured room" are two different measurements that can disagree. A
pair carrying `binding_i = True` next to `slack_i = 5` and a nonzero `dual_i` satisfies the
flag-based direction and still contributes `5 * |dual_i|` to the duality gap, so an audit of
that direction alone certifies numbers that are not shadow prices of the solved program.
Both are therefore checked:

  * a row the solver called LOOSE must not be priced, and
  * a PRICED row's complementarity product `|dual_i| * slack_i` must be within rounding of
    zero, whatever the flag says.

`cs_gap` is that product in either case, because the product is exactly what the defect adds
to the duality gap. The product's threshold is PER ROW, built from row `i`'s own two factors
and the caller's absolute `dual_tol` (see `_cs_product_budget`), so pivot noise on a genuinely
tight row is not a contradiction and no other row's magnitudes enter row `i`'s verdict. It was
once `1e-6 * (1 + max|dual| * max slack)`, which is how `duals = [1e6, 0.5]` beside
`slack = [0.0, 10.0]` came back `complementary` with a product of 5.0 on row 1: a threshold
built from a MAXIMUM over other rows looks per-row and is not — it transfers one row's units
onto another row's comparison.

A binding row with a ZERO dual is not a contradiction either. That is ordinary degeneracy: a
redundant row, or a vertex over-determined by more rows than variables, has tight rows worth
nothing at the margin. Flagging it would make this report raise a contradiction on
`x + y <= 2` alongside `x + y <= 2`, so it is counted as `n_degenerate` and reported, never
treated as a defect.

There is also exactly ONE audit function. `slackness_check` validates lengths, the caller's
`dual_tol` and the finiteness of every dual and slack, and then audits; nothing bypasses it,
including `binding_constraints`. A second unvalidated entry into the same audit is not a
duplicate implementation of it — it is a way to pass it, because a nan dual satisfies no
comparison: `|nan| > dual_tol` is False, so an unvalidated audit counts zero violations and
returns "complementary" over numbers it never read.

`binding` is the solver's own verdict, reused and not recomputed: `lp_solve` decides row `i`'s
tightness by its own per-row test on `|b_i - a_iᵀx|`, and that formula is deliberately not
restated here — a second definition of "tight", or a stale copy of the solver's, is how a
report ends up contradicting the solution it is explaining. What this module does own is
direction two of the audit below, which is what makes a `binding` flag that disagrees with its
own `slack` vector detectable at all.

Ceilings, and why there is a third one
--------------------------------------
`MAX_CSR_DIM` bounds a dimension and `linear.LP_MAX_TABLEAU_CELLS` bounds a tableau's area.
Neither bounds what the deletion filter spends, because its cost is measured in SOLVES:
`1 + m + 1 + |core|` of them, each a full two-phase simplex. A 20000-row model is a legal
shape under both existing ceilings and asks for forty thousand simplex solves.
`EXPLAIN_MAX_CORE_ROWS` is that third ceiling, and a model above it is refused with
`dimension_too_large` rather than accepted into a run nobody will wait for.

Absence, as everywhere in this package
--------------------------------------
`has_objective` and the status are the authorities; a number that was never computed is
0.0 padding and every list is EMPTY. The two gap fields (`cs_gap`, `duality_gap`) are
magnitudes, so `EXPLAIN_GAP_ABSENT` (-1.0) says "never measured" where 0.0 would say "no
violation" — the same convention as `model.MODEL_VIOLATION_ABSENT` and
`linear.LP_INFEASIBILITY_ABSENT`. `share` is empty rather than zero-filled when the
variable part of the objective is exactly 0, because a share of nothing does not exist and
`0/0` is not it.
"""
from std.math import abs as fabs

from numerical_stability import kahan_sum
from optimization.linear import (
    LPMatrix,
    LPSolution,
    LP_DBL_EPSILON,
    LP_FEAS_ULP_BUDGET,
    LP_INFEASIBLE,
    LP_OPTIMAL,
    LP_UNBOUNDED,
    linear_form_value,
    lp_dual_objective,
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
    MODEL_ERR_NON_FINITE_VALUE,
    MODEL_ERR_POLICY,
    MODEL_ERR_VAR_KIND,
    MODEL_OK,
    ModelFlat,
    VAR_BINARY,
    VAR_CONTINUOUS,
    VAR_INTEGER,
    _policy_parts_defect,
    has_lower_bound,
    has_upper_bound,
    minimization_value,
    model_finite as _finite,
    model_validate,
    variables_defect_flat,
)
from sparse_numerics.csr import dims_fit

# ── status codes ──────────────────────────────────────────────────────────────
# One numbering with `optimization.model` (0-30) and `optimization.linear` (40s, 60s):
# 0 is success, and the new codes start at 80 so nothing collides and both existing
# name functions keep working. `explain_status_name` falls through to `lp_status_name`,
# which falls through to `model_status_name`, so a rejected arena that reaches here still
# names the arena defect rather than "unknown status 8".
#
# THIS MODULE OWNS 80-86 in that shared numbering. A new code here goes at 87 or above, and
# no other module may reuse 80-86: two modules on one number make two outcomes that
# `explain_status_name` — and every caller switching on the number — cannot tell apart, which
# is the single failure this whole numbering exists to prevent. `optimization.integer`
# allocated 80-84 once and moved its own block rather than shadow these.

comptime EXPLAIN_OK: Int = MODEL_OK
comptime EXPLAIN_ERR_SUM_MISMATCH: Int = 80
comptime EXPLAIN_FEASIBLE_NO_CORE: Int = 81
comptime EXPLAIN_ERR_COMPLEMENTARY_SLACKNESS: Int = 82
comptime EXPLAIN_ERR_DUALITY_GAP: Int = 83
comptime EXPLAIN_ERR_CORE_UNVERIFIED: Int = 84
comptime EXPLAIN_ERR_BOUNDS_NOT_ROWS: Int = 85
comptime EXPLAIN_ERR_DISCRETE_VARIABLE: Int = 86

# A magnitude cannot be negative, so -1.0 is unmistakably "this was never measured".
comptime EXPLAIN_GAP_ABSENT: Float64 = -1.0

# ── every threshold in this file has ONE shape ────────────────────────────────
#
#     budget = <the caller's ABSOLUTE tolerance, when one is in scope>
#            + <ulps> * LP_DBL_EPSILON * <the magnitude of the very quantity being judged>
#
# which is the shape `linear.mojo`'s phase-1 feasibility test has after its own fix. Two
# module constants used to stand where `<ulps> * LP_DBL_EPSILON` stands now, multiplying a
# scale taken from the data: `EXPLAIN_CERT_SLOP = 1e-6` on both certificates and
# `EXPLAIN_SUM_TOL = 1e-9` on the decomposition. Neither is a rounding budget. 1e-9 relative
# is 4.5 MILLION ulps and 1e-6 relative is 4.5 billion, so both certificates certified
# violations nine orders of magnitude above anything floating point could explain:
#
#   * EXECUTED: `slackness_check(duals=[1e6, 0.5], slack=[0.0, 10.0], binding=[True, True],
#     dual_tol=1e-9)` returned `complementary = True`, `EXPLAIN_OK`, `cs_row = -1`,
#     `cs_gap = 0.0` for a complementarity product of `|0.5 * 10| = 5.0` — because the
#     threshold was `1e-6 * (1 + max|dual| * max slack) = 10.000001`. Row 0's price bought
#     row 1's violation a pass, and complementary slackness is a PER-ROW statement.
#   * EXECUTED: at `objective = 1e12` the strong-duality test accepted a primal/dual gap of
#     up to `1e6` as `strong_duality = True` with no `EXPLAIN_ERR_DUALITY_GAP`, and the
#     objective-drift test accepted 1e3 of disagreement between two computations of the same
#     number.
#
# So, here and in every threshold below: no hardcoded relative multiplier, no `1 + |x|`
# (whose 1.0 floor makes the test secretly ABSOLUTE at a scale the caller never chose), no
# scale carried over from a quantity other than the one under test, and no aggregate over
# other rows. `LP_DBL_EPSILON` and `LP_FEAS_ULP_BUDGET` (1024 ulps) come from `linear.mojo`
# rather than being restated, because a second definition of "one ulp" is a second thing to
# drift.
#
# Loosening a certificate threshold is the most damaging edit available in this file: a
# `certified`/`complementary`/`strong_duality` flag that passes a real violation is worse
# than no flag at all, because the caller stops looking (package rule 4d).

# The third ceiling: SOLVES, not dimensions and not cells. `1 + m + 1 + |core|` two-phase
# simplex runs, so 512 rows is up to 1026 solves. Above this the request is refused rather
# than started.
comptime EXPLAIN_MAX_CORE_ROWS: Int = 512

# Feasibility verdicts of one trial solve. Internal: three outcomes, because "not
# infeasible" and "feasible" are not the same claim when a solve can also end
# inconclusively, and collapsing them is how a core gets called minimal on the strength of
# a solve that never converged.
comptime _VERDICT_FEASIBLE: Int = 1
comptime _VERDICT_INFEASIBLE: Int = 2
comptime _VERDICT_INCONCLUSIVE: Int = 3


fn explain_status_name(code: Int) -> String:
    """Name for an explanation status, falling through to `lp_status_name`."""
    if code == EXPLAIN_ERR_SUM_MISMATCH:
        return "objective_parts_do_not_sum_to_the_objective"
    if code == EXPLAIN_FEASIBLE_NO_CORE:
        return "feasible_so_there_is_no_infeasibility_core"
    if code == EXPLAIN_ERR_COMPLEMENTARY_SLACKNESS:
        return "complementary_slackness_violated"
    if code == EXPLAIN_ERR_DUALITY_GAP:
        return "duality_gap_between_primal_and_dual_objective"
    if code == EXPLAIN_ERR_CORE_UNVERIFIED:
        return "core_not_confirmed_infeasible"
    if code == EXPLAIN_ERR_BOUNDS_NOT_ROWS:
        return "variable_bounds_are_not_expressed_as_rows"
    if code == EXPLAIN_ERR_DISCRETE_VARIABLE:
        return "discrete_variable_has_no_lp_certificate"
    return lp_status_name(code)


# `_finite` is `model.model_finite`, imported above under this module's old local name so no
# call site changed, and NOT redefined here — five byte-identical copies were five chances for
# the package's definition of "finite" to drift. Mojo has no access control, so the underscore
# on the alias only keeps the name out of the runtime contract. Policy validation is delegated
# the same way, through `_policy_parts_defect` to `model.policy_defect`.


# ── the two budget builders every threshold below goes through ────────────────


fn _rounding_budget(additions: Int, magnitude: Float64) -> Float64:
    """`LP_FEAS_ULP_BUDGET + additions` ulps of `magnitude`, and never a non-finite budget.

    `magnitude` must be the magnitude of the QUANTITY BEING JUDGED — the operands of the very
    subtraction whose result is compared against this budget, or the addends of the very sum
    whose two summations are being reconciled. Nothing else may be passed here.

    `additions` is how many floating-point additions produced that quantity, because a naive
    dot product over `n` terms accumulates up to one ulp per addition, so a fixed 1024-ulp
    budget would report an honest large-`n` summation as a defect. Every term is a multiple of
    `LP_DBL_EPSILON`, which is what keeps the whole allowance ~1e-13 relative: no real
    violation fits inside it, at any scale.

    A budget that overflowed comes back 0.0 rather than `inf`. An infinite threshold switches
    its own test off, which is the single failure every check in this file is written against;
    demanding exactness instead can only ever raise a false alarm, never certify a violation.
    """
    if additions < 0 or not (magnitude > 0.0):
        # `not (magnitude > 0.0)` and not `magnitude <= 0.0`: a nan magnitude satisfies
        # neither comparison, and it must land here rather than propagate into the budget.
        return 0.0
    var budget = (LP_FEAS_ULP_BUDGET + Float64(additions)) * LP_DBL_EPSILON * magnitude
    if not _finite(budget):
        return 0.0
    return budget


fn _cs_product_budget(dual_mag: Float64, slack_mag: Float64, dual_tol: Float64) -> Float64:
    """How far ONE row's `|dual_i| * slack_i` may sit from zero and still be indistinguishable
    from it.

    Built from row `i`'s own two factors and the caller's absolute `dual_tol`, and from nothing
    else — not from `max|dual|`, not from `max slack`, not from any aggregate over rows.
    Complementary slackness is the per-row statement `dual_i * slack_i = 0`, so row `i`'s
    verdict must not move when another row's numbers change.

    The two terms are the two reasons a nonzero product can still be zero in exact arithmetic:

      * `dual_tol * (|dual_i| + slack_i + dual_tol)` — `dual_tol` is the caller's statement
        that a magnitude that small IS zero, so each factor is only known to within it. A
        product is zero when EITHER factor is, and `|(d ± t)(s ± t)| >= |d s| - t(|d| + |s| + t)`,
        so a product under that bound is not distinguishable from a product of a factor that is
        genuinely zero. This is error propagation through the multiplication, not slop: it is
        the caller's own absolute tolerance carried into the product's units.
      * `LP_FEAS_ULP_BUDGET + 1` ulps of the product itself, for the multiplication and the
        rounding already present in the two stored factors.

    `dual_tol` is the only absolute zero-scale this audit is given, so it stands for the
    uncertainty of BOTH factors. A caller whose slacks carry a noise floor above `dual_tol`
    must raise `dual_tol` — which is exactly why it is a parameter and not a constant, and why
    `binding_constraints` derives it from the solver's own `optimality_tol`.
    """
    var budget = dual_tol * (dual_mag + slack_mag + dual_tol)
    budget += _rounding_budget(1, dual_mag * slack_mag)
    if not _finite(budget) or budget < 0.0:
        return 0.0
    return budget


# ── return-only result structs ────────────────────────────────────────────────
# Declared here because a returned struct's marshalling spec is parsed per FILE: returning
# `linear.LPSolution` would drop the function from the runtime contract with no error
# anywhere.


@fieldwise_init
struct SlacknessCheck(Copyable, Movable):
    """The complementary-slackness audit of one primal/dual pair, in BOTH directions.

    `complementary` is the verdict and covers two conditions, not one: no row the solver
    called loose is priced, AND no priced row has a materially positive `slack_i`. They are
    contrapositives over one exact quantity and not over the flag/vector pair this audit is
    handed — see the module docstring.

    `cs_row` is the worst row that fails either condition, -1 when none does. `cs_gap` is that
    row's complementarity product `|dual_i| * slack_i` — the term that appears in the duality
    gap, so it is the size of the defect in the objective's units — and it is
    `EXPLAIN_GAP_ABSENT` when the inputs could not be compared at all.

    `n_degenerate` counts binding rows priced at zero. That is legal and common, so it is
    reported here rather than folded into the verdict.
    """

    var status: Int
    var complementary: Bool
    var n_rows: Int
    var n_binding: Int
    var n_degenerate: Int
    var cs_row: Int
    var cs_gap: Float64


@fieldwise_init
struct BindingReport(Copyable, Movable):
    """Which rows are tight at the optimum, what each is worth, and the certificate.

    The four `binding_*` lists are parallel and hold only the tight rows, in ascending row
    order, so a caller can print an explanation without filtering. The full-length `duals`,
    `slack`, `activity` and `binding` lists are also here because the interesting question
    is often about a row that did NOT bind.

    What the certificate covers, exactly
    -----------------------------------
    `complementary` is BOTH complementary-slackness conditions: no row the solver called loose
    carries a price, and no priced row has materially positive measured slack (the module
    docstring says why one does not imply the other over a flag/vector pair, and why a tight
    row priced at zero is degeneracy rather than a defect). `strong_duality` is `bᵀy` against
    the variable part of `cᵀx`. Together those are what makes `duals` shadow prices OF THIS
    solution rather than numbers a tableau happened to hold: primal feasibility is phase 1's
    own measured claim in `lp_solve`, and these two audits are what tie the duals to it. They
    do not certify integrality, bounds handled outside the rows, or a unique optimum — a
    degenerate vertex has valid duals that another basis would report differently.

    On any status other than `EXPLAIN_OK`, `EXPLAIN_ERR_COMPLEMENTARY_SLACKNESS` and
    `EXPLAIN_ERR_DUALITY_GAP` every list is EMPTY and `has_objective` is False. Those two
    are the exception ON PURPOSE: the finding IS about the numbers, so discarding them would
    leave a caller with a code and nothing to inspect. Unlike an unbounded program, where
    the vertex is meaningless, here the numbers exist and are exactly what the status is
    about — but they are a certificate that failed its own audit, so they must not be used
    as shadow prices. `complementary` and `strong_duality` say which audit failed. A pair the
    audit could not READ (a non-finite dual or slack) is not in that exception: it comes back
    as the non-finite status with no numbers, because there is nothing to inspect there.
    """

    var status: Int
    var has_objective: Bool
    var objective: Float64
    var dual_objective: Float64
    var duality_gap: Float64
    var strong_duality: Bool
    var complementary: Bool
    var n_vars: Int
    var n_constraints: Int
    var n_binding: Int
    var n_degenerate: Int
    var cs_row: Int
    var cs_gap: Float64
    var x: List[Float64]
    var duals: List[Float64]
    var slack: List[Float64]
    var activity: List[Float64]
    var binding: List[Bool]
    var binding_rows: List[Int]
    var binding_duals: List[Float64]
    var binding_senses: List[Int]
    var binding_rhs: List[Float64]


@fieldwise_init
struct InfeasibilityCore(Copyable, Movable):
    """A subset of rows that is still infeasible, and how much was proved about it.

    `core` holds the row indices in ascending order and `in_core` is the same answer as a
    per-row mask. `core_senses` / `core_rhs` are parallel to `core`.

    Three separate claims, three separate fields, because they are proved by different
    solves and a caller may get one without the others:

      * `is_infeasible` — the FULL model was shown infeasible by phase 1.
      * `core_verified` — the returned subset was re-solved and is infeasible on its own.
      * `minimal` — every member was re-tested against the FINAL core and dropping it made
        that core feasible. False whenever `minimality_verified` is False; there is no
        halfway claim.

    `infeasibility` and `core_infeasibility` are the MEASURED phase-1 residuals of the full
    model and of the core, `EXPLAIN_GAP_ABSENT` when a solve never got far enough to measure
    one. `n_solves` is the price paid, so a caller can see it grow linearly in the row count.
    """

    var status: Int
    var is_infeasible: Bool
    var core_verified: Bool
    var minimal: Bool
    var minimality_verified: Bool
    var n_constraints: Int
    var core_size: Int
    var n_solves: Int
    var n_inconclusive: Int
    var infeasibility: Float64
    var core_infeasibility: Float64
    var core: List[Int]
    var in_core: List[Bool]
    var core_senses: List[Int]
    var core_rhs: List[Float64]
    var necessary: List[Bool]


@fieldwise_init
struct ObjectiveDecomposition(Copyable, Movable):
    """`objective = constant + Σ_j c_j x_j`, itemised, with the residual that proves it.

    `residual` is `objective - (constant + Σ contribution)` and it is the point of the
    struct: parts that do not add up to the whole are an audit that would pass anything, so
    the sum is compared against the objective computed by a different route and the
    difference is reported rather than assumed to be zero. It is signed, so absence cannot
    be a sentinel value in it — `has_objective` and `status` are the authorities, and
    `residual` is 0.0 padding when there is no answer.

    `share` is EMPTY when `has_share` is False, which happens exactly when the variable part
    of the objective is 0. Shares of a zero total do not exist; a zero-filled list would say
    every variable contributed nothing to a total that several of them may have cancelled
    into being.
    """

    var status: Int
    var has_objective: Bool
    var objective: Float64
    var minimization_objective: Float64
    var maximize: Bool
    var constant: Float64
    var parts_total: Float64
    var residual: Float64
    var sums_to_objective: Bool
    var n_vars: Int
    var n_active: Int
    var largest_index: Int
    var largest_contribution: Float64
    var has_share: Bool
    var x: List[Float64]
    var contribution: List[Float64]
    var share: List[Float64]


# ── complementary slackness ───────────────────────────────────────────────────


fn slackness_check(
    duals: List[Float64], slack: List[Float64], binding: List[Bool], dual_tol: Float64
) -> SlacknessCheck:
    """Audit a primal/dual pair for complementary slackness, without solving anything.

    The ONE audit in this module, validation included, and the only way in — there is no
    internal unvalidated twin, because a twin is not a second implementation of the audit, it
    is a way to pass it. A nan satisfies no comparison: with a nan dual every
    `|dual_i| > dual_tol` is False, so an audit that skipped the finiteness check would count
    zero violations and certify "complementary" over numbers it never read. `dual_tol` is
    validated for the same reason — a nan threshold disables every test at once, and
    `binding_constraints` derives its threshold from the duals it is auditing.

    Both directions of complementary slackness are checked; see the module docstring for why
    they are not each other's contrapositive over a `binding` flag and a `slack` vector.

    Takes `binding` rather than recomputing tightness from `slack` and a tolerance, so the
    LOOSE-row direction is about the solver's own notion of a tight row and not about a second
    one invented here. The PRICED-row direction is about the measured slack, which is what
    makes a flag that disagrees with its own vector detectable at all. `dual_tol` is the
    magnitude below which a dual counts as zero; a caller with duals of size 1e6 must scale
    it, which is why it is a parameter and not a constant.

    Exists as its own entry point because a solver bug cannot be summoned on demand: this is
    how the detector is testable on a pair that is deliberately contradictory.
    """
    var m = len(duals)
    if len(slack) != m or len(binding) != m:
        return SlacknessCheck(
            MODEL_ERR_LENGTH_MISMATCH, False, 0, 0, 0, -1, EXPLAIN_GAP_ABSENT
        )
    if not _finite(dual_tol) or dual_tol < 0.0:
        return SlacknessCheck(MODEL_ERR_POLICY, False, m, 0, 0, -1, EXPLAIN_GAP_ABSENT)
    for i in range(m):
        if not (_finite(duals[i]) and _finite(slack[i])):
            return SlacknessCheck(
                MODEL_ERR_NON_FINITE_VALUE, False, m, 0, 0, i, EXPLAIN_GAP_ABSENT
            )

    # There is no threshold computed over the whole vector here, and that is the point. The
    # product threshold is built PER ROW inside the loop by `_cs_product_budget`, from that
    # row's own dual and slack. It used to be `EXPLAIN_CERT_SLOP * (1 + max|dual| * max slack)`
    # — a single number formed from a MAXIMUM over every row — and `duals = [1e6, 0.5]` beside
    # `slack = [0.0, 10.0]` with both rows flagged binding then came back `complementary` at
    # `cs_gap = 0.0`, because that threshold was 10.000001 and row 1's product was 5.0. The
    # same pair with row 0's dual lowered to 1.0 was correctly reported, which is the whole
    # tell: the verdict on row 1 depended on a number belonging to row 0.
    var n_binding = 0
    var n_degenerate = 0
    var cs_row = -1
    var worst: Float64 = 0.0
    for i in range(m):
        var priced = fabs(duals[i]) > dual_tol
        if binding[i]:
            n_binding += 1
        if not priced:
            if binding[i]:
                # Degeneracy, not a defect: a tight row can be worth nothing at the margin.
                n_degenerate += 1
            continue
        var dual_mag = fabs(duals[i])
        var slack_mag = fabs(slack[i])
        var product = dual_mag * slack_mag
        # Direction one: a row the solver called loose, priced anyway.
        var loose = not binding[i]
        # Direction two: a priced row whose MEASURED slack is room, not rounding. Independent
        # of the flag on purpose — `binding_i = True` beside `slack_i = 5` and a nonzero dual
        # passes direction one and still puts `5 * |dual_i|` into the duality gap. Judged
        # against row `i`'s own budget; a product that overflowed to inf is a violation, not a
        # comparison to lose (`inf > inf` is False).
        var not_tight = (
            not _finite(product)
        ) or product > _cs_product_budget(dual_mag, slack_mag, dual_tol)
        if loose or not_tight:
            if cs_row < 0 or product > worst:
                cs_row = i
                worst = product
    if cs_row >= 0:
        return SlacknessCheck(
            EXPLAIN_ERR_COMPLEMENTARY_SLACKNESS, False, m, n_binding, n_degenerate,
            cs_row, worst,
        )
    return SlacknessCheck(EXPLAIN_OK, True, m, n_binding, n_degenerate, -1, 0.0)


# ── binding constraints ───────────────────────────────────────────────────────


fn _no_binding(status: Int, n_vars: Int, n_cons: Int) -> BindingReport:
    return BindingReport(
        status, False, 0.0, 0.0, EXPLAIN_GAP_ABSENT, False, False, n_vars, n_cons,
        0, 0, -1, EXPLAIN_GAP_ABSENT,
        List[Float64](), List[Float64](), List[Float64](), List[Float64](), List[Bool](),
        List[Int](), List[Float64](), List[Int](), List[Float64](),
    )


fn binding_constraints(
    c: List[Float64], constant: Float64,
    a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool,
    max_iterations: Int, feasibility_tol: Float64, optimality_tol: Float64,
) -> BindingReport:
    """The tight rows at the optimum with their shadow prices, plus both certificates.

    Solves through `lp_solve` and does no validation of its own before that call: the
    solver's `_lp_input_defect` is the guard, and its status is propagated unchanged. So the
    generated-suite pattern `(_lf5, 5.0, _lf5, 5, 5, _li5, _lf5, True, 5, 5.0, 5.0)` is
    refused as `dense_shape_invalid` — 25 cells asked of a 5-element list — before anything
    is indexed.

    A non-optimal program has no binding set: an infeasible one has no point at which to
    evaluate tightness, and an unbounded one has no optimum for the duals to be the
    derivative of. Both come back with the solver's status and no numbers.
    """
    var solution = lp_solve(
        c, constant, a, rows, cols, senses, rhs, maximize,
        max_iterations, feasibility_tol, optimality_tol,
    )
    if solution.status != LP_OPTIMAL:
        return _no_binding(solution.status, solution.n_vars, solution.n_constraints)

    var m = solution.n_constraints
    if (
        len(senses) != m
        or len(rhs) != m
        or len(solution.duals) != m
        or len(solution.slack) != m
        or len(solution.binding) != m
        or len(solution.activity) != m
    ):
        # A structural assertion about a value this module did not build. It costs one pass
        # and it is the difference between a status and an uncatchable read past a List end
        # if `lp_solve`'s postcondition ever changes.
        return _no_binding(MODEL_ERR_LENGTH_MISMATCH, solution.n_vars, m)

    var scale: Float64 = 0.0
    for i in range(m):
        # Non-finite magnitudes are kept OUT of the scale deliberately. `nan > scale` is False,
        # so a nan dual would leave the scale at 0 and hide inside a perfectly ordinary
        # tolerance; an inf dual would make `dual_tol` inf and then no dual at all counts as
        # priced. Both end in an audit that reports "complementary" without reading the
        # numbers. Building a finite threshold here lets the audit below reject the pair with
        # the status that names the real defect — a non-finite value — instead of a policy
        # complaint about a tolerance this function computed.
        var magnitude = fabs(solution.duals[i])
        if _finite(magnitude) and magnitude > scale:
            scale = magnitude
    # The magnitude below which a dual counts as ZERO. The caller's `optimality_tol` is the
    # absolute part, because that is the caller's own statement about the dual space — the
    # solver already prices a column as non-profitable below it. The rest is a ROUNDING
    # allowance: every dual comes out of the same elimination, so an entry that should be
    # exactly 0 can carry ulps of the largest magnitude that elimination handled. That is the
    # one place a maximum over rows is admissible, and only because `LP_DBL_EPSILON` keeps it
    # ~1e-13 relative — a dual that is a real price cannot hide under it, and the audit takes a
    # single scalar threshold by contract so there is no per-row form available.
    #
    # It was `EXPLAIN_CERT_SLOP * (1 + max|dual|)`: with duals of size 1e6 that is 1.000001, so
    # every dual under a full unit was read as zero and its row was never audited at all. The
    # new value on that same data is ~2.3e-7, four million times tighter.
    var dual_tol = optimality_tol + _rounding_budget(0, scale)
    # The VALIDATED entry point, never a private twin of the audit: `slackness_check` is what
    # checks the lengths and the finiteness of every dual and slack, and an audit handed a nan
    # counts zero violations and passes. One audit, one door.
    var audit = slackness_check(solution.duals, solution.slack, solution.binding, dual_tol)
    if (
        audit.status != EXPLAIN_OK
        and audit.status != EXPLAIN_ERR_COMPLEMENTARY_SLACKNESS
    ):
        # The certificate could not be audited at all, which is not the same as failing the
        # audit: numbers that FAILED are still returned (see `BindingReport`) because the
        # finding is about them, but numbers that could not BE read are absent.
        return _no_binding(audit.status, solution.n_vars, m)

    var binding_rows = List[Int]()
    var binding_duals = List[Float64]()
    var binding_senses = List[Int]()
    var binding_rhs = List[Float64]()
    for i in range(m):
        if solution.binding[i]:
            binding_rows.append(i)
            binding_duals.append(solution.duals[i])
            binding_senses.append(senses[i])
            binding_rhs.append(rhs[i])

    # Strong duality, as the second half of the certificate. `bᵀy` comes from
    # `lp_dual_objective` — which exists because the frozen `dual_value` does not compute it
    # — and is compared against the VARIABLE part of the primal objective, since the
    # objective constant is not part of `cᵀx`.
    var dual_obj = lp_dual_objective(solution.duals, rhs)
    if not dual_obj.has_value:
        return _no_binding(dual_obj.status, solution.n_vars, m)
    var primal_variable_part = solution.objective - constant
    var gap = fabs(dual_obj.value - primal_variable_part)
    # The judged quantity is that SUBTRACTION, so the budget is sized by its own two operands
    # and nothing else, plus the caller's absolute `optimality_tol`. `bᵀy` is a `vec_dot` over
    # `m` terms and `cᵀx` over `n`, hence `m + n` additions on top of the shared 1024 ulps.
    #
    # It was `EXPLAIN_CERT_SLOP * (1 + |objective|)`, which at `objective = 1e12` accepted a
    # primal/dual gap of up to 1.0e6 as `strong_duality = True` and returned `EXPLAIN_OK`. A
    # gap of a million on an objective of a trillion is not strong duality, it is a solve that
    # did not converge reported as a theorem. The same data now allows ~0.23 — 1024 + m + n
    # ulps of 1e12 — which is what the arithmetic can actually account for.
    var gap_scale = fabs(dual_obj.value)
    if fabs(primal_variable_part) > gap_scale:
        gap_scale = fabs(primal_variable_part)
    var gap_budget = optimality_tol + _rounding_budget(m + solution.n_vars, gap_scale)
    var strong = _finite(gap) and gap <= gap_budget

    var status = EXPLAIN_OK
    if not audit.complementary:
        status = EXPLAIN_ERR_COMPLEMENTARY_SLACKNESS
    elif not strong:
        status = EXPLAIN_ERR_DUALITY_GAP

    return BindingReport(
        status, True, solution.objective, dual_obj.value, gap, strong,
        audit.complementary, solution.n_vars, m, audit.n_binding, audit.n_degenerate,
        audit.cs_row, audit.cs_gap,
        solution.x.copy(), solution.duals.copy(), solution.slack.copy(),
        solution.activity.copy(), solution.binding.copy(),
        binding_rows^, binding_duals^, binding_senses^, binding_rhs^,
    )


fn binding_constraints_default(
    c: List[Float64], a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool,
) -> BindingReport:
    """`binding_constraints` with no objective constant and `model.mojo`'s default policy."""
    return binding_constraints(
        c, 0.0, a, rows, cols, senses, rhs, maximize,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
    )


# ── infeasibility core ────────────────────────────────────────────────────────


fn _no_core(status: Int, n_cons: Int, infeasibility: Float64, n_solves: Int) -> InfeasibilityCore:
    return InfeasibilityCore(
        status, False, False, False, False, n_cons, 0, n_solves, 0,
        infeasibility, EXPLAIN_GAP_ABSENT,
        List[Int](), List[Bool](), List[Int](), List[Float64](), List[Bool](),
    )


fn _core_input_defect(
    a: List[Float64], rows: Int, cols: Int, senses: List[Int], rhs: List[Float64],
    max_iterations: Int, feasibility_tol: Float64, optimality_tol: Float64,
) -> Int:
    """`MODEL_OK` when the filter may start indexing and allocating.

    `lp_solve` validates its own arguments, but it cannot be the only guard here: this
    function allocates a `cols`-length zero cost vector and `rows` subset matrices BEFORE
    any solve, so the shape has to be sound first. `dims_fit` is the dense-shape check
    because `rows * cols == len(a)` is a wrapping multiply and `3 * 6148914691236517206 == 2`
    passes it.

    The SHAPE checks are this function's own; the POLICY checks are not restated here.
    `_policy_parts_defect` reaches `model.policy_defect`, the package's single definition of a
    policy a solver will honour — including why a zero `optimality_tol` is refused: it makes
    every rounding-error-negative column look profitable, so a trial solve pivots until its
    iteration cap and reports `iteration_limit`, an inconclusive verdict manufactured by the
    policy rather than by the model.
    """
    if rows < 0 or cols < 0:
        return MODEL_ERR_DENSE_SHAPE
    if not dims_fit(rows, cols, len(a)):
        return MODEL_ERR_DENSE_SHAPE
    if len(senses) != rows or len(rhs) != rows:
        return MODEL_ERR_LENGTH_MISMATCH
    if rows > EXPLAIN_MAX_CORE_ROWS:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    # An infeasibility core has no integrality tolerance, so a known-valid default stands in
    # for the one policy field this entry point does not take. This is the last check, so the
    # delegated verdict IS the return value — `MODEL_OK` when the policy is honourable.
    return _policy_parts_defect(
        max_iterations, feasibility_tol, optimality_tol, DEFAULT_INTEGRALITY_TOL
    )


fn _verdict(status: Int) -> Int:
    """Feasible / infeasible / inconclusive from one trial solve's status.

    `LP_UNBOUNDED` is FEASIBLE: an unbounded objective is only definable over a nonempty
    feasible set. It cannot occur with the zero cost vector the trials use, and it is
    classified anyway, because a classification that is correct only while an optimisation
    holds is a wrong answer waiting for the optimisation to change.
    """
    if status == LP_OPTIMAL or status == LP_UNBOUNDED:
        return _VERDICT_FEASIBLE
    if status == LP_INFEASIBLE:
        return _VERDICT_INFEASIBLE
    return _VERDICT_INCONCLUSIVE


fn _subset_solve(
    a: List[Float64], rows: Int, cols: Int, senses: List[Int], rhs: List[Float64],
    keep: List[Bool], drop: Int, zeros: List[Float64],
    max_iterations: Int, feasibility_tol: Float64, optimality_tol: Float64,
) -> LPSolution:
    """Solve the feasibility problem over `keep` minus `drop` (`-1` drops nothing).

    The objective is all zeros, so this asks only whether the subset admits a point with
    `x >= 0`. Indexing `a[i * cols + j]` is safe because `_core_input_defect` has already
    established `len(a) == rows * cols` by division.
    """
    var sub_a = List[Float64]()
    var sub_senses = List[Int]()
    var sub_rhs = List[Float64]()
    var sub_rows = 0
    for i in range(rows):
        if not keep[i] or i == drop:
            continue
        for j in range(cols):
            sub_a.append(a[i * cols + j])
        sub_senses.append(senses[i])
        sub_rhs.append(rhs[i])
        sub_rows += 1
    return lp_solve(
        zeros, 0.0, sub_a, sub_rows, cols, sub_senses, sub_rhs, False,
        max_iterations, feasibility_tol, optimality_tol,
    )


fn infeasibility_core(
    a: List[Float64], rows: Int, cols: Int, senses: List[Int], rhs: List[Float64],
    max_iterations: Int, feasibility_tol: Float64, optimality_tol: Float64,
) -> InfeasibilityCore:
    """A small still-infeasible subset of `A x {senses} b, x >= 0`, by deletion filtering.

    Takes no objective and no direction, because a core is a property of the constraints
    alone; passing `c` would invite the belief that the answer depends on it.

    The filter drops row `i` and re-solves: if the remainder is still infeasible, `i` was
    not needed and stays dropped; if the remainder became feasible, `i` is necessary and is
    kept. Every re-solve is `lp_solve`, whose phase 1 ESTABLISHES infeasibility from a
    measured residual — a point-testing predicate such as the frozen
    `linear_programming.is_feasible` could only ever refute it, and that function also reads
    every `>=` row as `<=` and indexes `b[i]` unguarded.

    `x >= 0` is not a candidate for deletion, so it never appears in the core: it is the
    variable convention of this whole package, stated in `linear.mojo`, and a model that is
    infeasible only because of it (`x <= -5`) correctly yields that single row as the core.
    """
    var defect = _core_input_defect(
        a, rows, cols, senses, rhs, max_iterations, feasibility_tol, optimality_tol
    )
    if defect != MODEL_OK:
        return _no_core(defect, 0, EXPLAIN_GAP_ABSENT, 0)
    if rows == 0:
        # `x = 0` satisfies an empty constraint system, so there is nothing to solve and
        # nothing to explain. Answered before allocating anything, which also refuses to
        # build a `cols`-length zero objective for a caller who passed a huge `cols` with no
        # rows — a shape `dims_fit` allows, since zero rows means zero cells.
        return InfeasibilityCore(
            EXPLAIN_FEASIBLE_NO_CORE, False, False, False, False, 0, 0, 0, 0,
            0.0, EXPLAIN_GAP_ABSENT,
            List[Int](), List[Bool](), List[Int](), List[Float64](), List[Bool](),
        )

    var zeros = List[Float64]()
    for _ in range(cols):
        zeros.append(0.0)
    var keep = List[Bool]()
    for _ in range(rows):
        keep.append(True)

    var n_solves = 0
    var full = _subset_solve(
        a, rows, cols, senses, rhs, keep, -1, zeros,
        max_iterations, feasibility_tol, optimality_tol,
    )
    n_solves += 1
    var full_verdict = _verdict(full.status)
    if full_verdict == _VERDICT_FEASIBLE:
        # A feasible model has no core, and inventing one is the overclaim this function
        # exists to avoid. The measured phase-1 residual comes back as evidence.
        return InfeasibilityCore(
            EXPLAIN_FEASIBLE_NO_CORE, False, False, False, False, rows, 0, n_solves, 0,
            full.infeasibility, EXPLAIN_GAP_ABSENT,
            List[Int](), List[Bool](), List[Int](), List[Float64](), List[Bool](),
        )
    if full_verdict == _VERDICT_INCONCLUSIVE:
        # Neither feasible nor shown infeasible. Propagating the solver's status keeps
        # "iteration_limit" from arriving as "feasible, no core".
        return _no_core(full.status, rows, full.infeasibility, n_solves)

    var n_inconclusive = 0
    for i in range(rows):
        var trial = _subset_solve(
            a, rows, cols, senses, rhs, keep, i, zeros,
            max_iterations, feasibility_tol, optimality_tol,
        )
        n_solves += 1
        var verdict = _verdict(trial.status)
        if verdict == _VERDICT_INFEASIBLE:
            keep[i] = False
        elif verdict == _VERDICT_INCONCLUSIVE:
            # Kept, because an unproven row is not a removable one. The count is what stops
            # `minimal` from being claimed on the strength of a solve that never converged.
            n_inconclusive += 1

    var core = List[Int]()
    var core_senses = List[Int]()
    var core_rhs = List[Float64]()
    for i in range(rows):
        if keep[i]:
            core.append(i)
            core_senses.append(senses[i])
            core_rhs.append(rhs[i])
    var core_size = len(core)

    # Claim one: the subset really is infeasible on its own. Re-solved rather than inferred
    # from the filter's bookkeeping.
    var core_solve = _subset_solve(
        a, rows, cols, senses, rhs, keep, -1, zeros,
        max_iterations, feasibility_tol, optimality_tol,
    )
    n_solves += 1
    var core_verified = _verdict(core_solve.status) == _VERDICT_INFEASIBLE and core_size > 0

    # Claim two: every member is necessary. One solve per member against the FINAL core.
    var necessary = List[Bool]()
    var minimality_verified = core_verified and n_inconclusive == 0
    var minimal = minimality_verified
    for k in range(core_size):
        var probe = _subset_solve(
            a, rows, cols, senses, rhs, keep, core[k], zeros,
            max_iterations, feasibility_tol, optimality_tol,
        )
        n_solves += 1
        var verdict = _verdict(probe.status)
        necessary.append(verdict == _VERDICT_FEASIBLE)
        if verdict != _VERDICT_FEASIBLE:
            minimal = False
        if verdict == _VERDICT_INCONCLUSIVE:
            n_inconclusive += 1
            minimality_verified = False

    var in_core = keep.copy()
    var status = EXPLAIN_OK
    if not core_verified:
        status = EXPLAIN_ERR_CORE_UNVERIFIED
    return InfeasibilityCore(
        status, True, core_verified, minimal, minimality_verified, rows, core_size,
        n_solves, n_inconclusive, full.infeasibility, core_solve.infeasibility,
        core^, in_core^, core_senses^, core_rhs^, necessary^,
    )


fn infeasibility_core_default(
    a: List[Float64], rows: Int, cols: Int, senses: List[Int], rhs: List[Float64],
) -> InfeasibilityCore:
    """`infeasibility_core` under `model.mojo`'s default policy."""
    return infeasibility_core(
        a, rows, cols, senses, rhs,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
    )


# ── objective decomposition ───────────────────────────────────────────────────


fn _no_decomposition(status: Int, n_vars: Int, maximize: Bool) -> ObjectiveDecomposition:
    return ObjectiveDecomposition(
        status, False, 0.0, 0.0, maximize, 0.0, 0.0, 0.0, False, n_vars, 0, -1, 0.0,
        False, List[Float64](), List[Float64](), List[Float64](),
    )


fn objective_contributions(
    c: List[Float64], constant: Float64, x: List[Float64], maximize: Bool
) -> ObjectiveDecomposition:
    """Per-variable `c_j x_j` at `x`, with the residual that proves the parts sum to the whole.

    The whole is `linear_form_value`, which is `constant + vec_dot(c, x)` through the frozen
    dot product; the parts are summed with the frozen `numerical_stability.kahan_sum`. Two
    different summations of the same products is the point: `residual` then measures the
    decomposition rather than measuring the same accumulation twice, and a mis-scaled
    contribution shows up as a nonzero residual instead of cancelling in both routes.

    `linear_form_value` is also the length and finiteness guard — it refuses a `c` and an `x`
    of different lengths instead of letting `vec_dot` truncate to the shorter one and value a
    different form.
    """
    var total = linear_form_value(c, constant, x)
    if not total.has_value:
        return _no_decomposition(total.status, len(c), maximize)

    var n = len(c)
    var contribution = List[Float64]()
    var n_active = 0
    var largest_index = -1
    var largest: Float64 = 0.0
    for j in range(n):
        var term = c[j] * x[j]
        if not _finite(term):
            return _no_decomposition(MODEL_ERR_NON_FINITE_VALUE, n, maximize)
        contribution.append(term)
        if term != 0.0:
            n_active += 1
        if largest_index < 0 or fabs(term) > fabs(largest):
            # Ties go to the LOWEST index, so the report does not depend on a scan order.
            largest_index = j
            largest = term

    var parts = kahan_sum(contribution)
    if not _finite(parts):
        return _no_decomposition(MODEL_ERR_NON_FINITE_VALUE, n, maximize)
    var residual = total.value - (constant + parts)
    # The judged quantity is the SUM ITSELF: `residual` is the disagreement between two
    # summations of one identical set of addends, so what the budget must absorb is the
    # rounding of those addends' additions — `|constant| + Σ_j |c_j x_j|`, one ulp per addition
    # plus the shared 1024. This is a sum over items and it is the one place that is right,
    # for exactly the reason `Σ_i |b_i|` was wrong in `linear.mojo`'s per-ROW feasibility test:
    # there the judged quantity was a single row, so other rows' magnitudes were foreign to it;
    # here every addend is a constituent of the very number under test. Cancelling terms
    # therefore do raise the allowance — that is the true error bound of a naive `vec_dot` —
    # but only ever by ulps of what was cancelled, never by a fixed fraction of it.
    #
    # It was `EXPLAIN_SUM_TOL * (1 + |objective|)`: at an objective of 1e12 that admitted 1e3
    # of residual, so an itemisation could disagree with its own total by a thousand and still
    # report `sums_to_objective`. The audit is the only thing standing between a caller and a
    # decomposition of a different number.
    var terms_magnitude = fabs(constant)
    for j in range(n):
        terms_magnitude += fabs(contribution[j])
    var sums = _finite(residual) and fabs(residual) <= _rounding_budget(
        n, terms_magnitude
    )

    var share = List[Float64]()
    var has_share = parts != 0.0
    if has_share:
        for j in range(n):
            var fraction = contribution[j] / parts
            if not _finite(fraction):
                # A denormal total under a large contribution overflows the quotient. A share
                # that overflowed is not a share, so the whole list goes rather than one inf
                # travelling on inside a vector of ordinary fractions.
                has_share = False
                share = List[Float64]()
                break
            share.append(fraction)

    var status = EXPLAIN_OK
    if not sums:
        status = EXPLAIN_ERR_SUM_MISMATCH
    return ObjectiveDecomposition(
        status, True, total.value, minimization_value(total.value, maximize), maximize,
        constant, parts, residual, sums, n, n_active, largest_index, largest,
        has_share, x.copy(), contribution^, share^,
    )


fn optimum_contributions(
    c: List[Float64], constant: Float64,
    a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool,
    max_iterations: Int, feasibility_tol: Float64, optimality_tol: Float64,
) -> ObjectiveDecomposition:
    """`objective_contributions` at the LP optimum, or the solver's status and no numbers.

    The decomposition is computed at the returned vertex and its total is then compared
    against the objective `lp_solve` reported, so a disagreement between the two is the
    `residual` rather than a number nobody checked.
    """
    var solution = lp_solve(
        c, constant, a, rows, cols, senses, rhs, maximize,
        max_iterations, feasibility_tol, optimality_tol,
    )
    if solution.status != LP_OPTIMAL:
        return _no_decomposition(solution.status, solution.n_vars, maximize)
    var parts = objective_contributions(c, constant, solution.x, maximize)
    if not parts.has_objective:
        return parts^
    var drift = fabs(parts.objective - solution.objective)
    # Two computations of the SAME number — `linear_form_value(c, constant, x)` here against
    # `constant + vec_dot(c, x)` inside the solver — so the budget is the caller's absolute
    # `optimality_tol` plus ulps of the two operands of this subtraction, and nothing else.
    #
    # It was `EXPLAIN_SUM_TOL * (1 + |objective|)`, which at an objective of 1e12 let the
    # itemisation be of a number 1.0e3 away from the one the solver reported and still returned
    # it as the itemisation of the vertex.
    var drift_scale = fabs(parts.objective)
    if fabs(solution.objective) > drift_scale:
        drift_scale = fabs(solution.objective)
    var drift_budget = optimality_tol + _rounding_budget(
        solution.n_vars, drift_scale
    )
    if not _finite(drift) or drift > drift_budget:
        # The itemisation is of a different number than the solver reported. Reported as the
        # sum mismatch it is, never quietly returned as an itemisation of the vertex.
        return ObjectiveDecomposition(
            EXPLAIN_ERR_SUM_MISMATCH, True, parts.objective, parts.minimization_objective,
            maximize, constant, parts.parts_total, parts.objective - solution.objective,
            False, parts.n_vars, parts.n_active, parts.largest_index,
            parts.largest_contribution, parts.has_share, parts.x.copy(),
            parts.contribution.copy(), parts.share.copy(),
        )
    return parts^


fn optimum_contributions_default(
    c: List[Float64], a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool,
) -> ObjectiveDecomposition:
    """`optimum_contributions` with no objective constant and the default policy."""
    return optimum_contributions(
        c, 0.0, a, rows, cols, senses, rhs, maximize,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
    )


# ── the general model, explained ──────────────────────────────────────────────


fn _model_lp_defect(flat: ModelFlat) -> Int:
    """`MODEL_OK` when this model's feasible set is exactly what an LP certificate covers.

    `lp_from_arenas` reads the objective and constraint arenas and imposes `x >= 0`; it does
    NOT read the variable bound columns. So a model carrying an upper bound or a nonzero
    lower bound in those columns would be explained over a LARGER feasible set than the one
    it states, and every dual would be a shadow price of the wrong program. That is refused
    rather than silently ignored: bounds belong in rows here, which is the convention
    `linear.mojo` states and does not hide.

    A discrete variable is refused for a different reason. Duals, shadow prices and an
    IIS-style core are certificates of a CONTINUOUS relaxation; over an integer model the
    LP optimum is a bound and not the answer, and reporting its duals as the model's shadow
    prices is a wrong answer with an optimal status. Branch and bound is not in this module.
    """
    var defect = variables_defect_flat(
        flat.var_lower, flat.var_upper, flat.var_kind, flat.var_flags
    )
    if defect != MODEL_OK:
        return defect
    var n = len(flat.var_lower)
    for j in range(n):
        var kind = flat.var_kind[j]
        if kind == VAR_INTEGER or kind == VAR_BINARY:
            return EXPLAIN_ERR_DISCRETE_VARIABLE
        if kind != VAR_CONTINUOUS:
            return MODEL_ERR_VAR_KIND
        var flags = flat.var_flags[j]
        if has_upper_bound(flags):
            return EXPLAIN_ERR_BOUNDS_NOT_ROWS
        if not has_lower_bound(flags):
            # A free variable is not `x >= 0`, and splitting it into a difference of two
            # would report duals in a space the caller cannot see.
            return EXPLAIN_ERR_BOUNDS_NOT_ROWS
        if flat.var_lower[j] != 0.0:
            return EXPLAIN_ERR_BOUNDS_NOT_ROWS
    return MODEL_OK


fn _model_lp(flat: ModelFlat) -> LPMatrix:
    """The model's `(c, constant, A, senses, rhs)`, or a status and no matrix.

    Two validations, both delegated: `model_validate` for the whole model (parallel columns,
    `con_ptr` monotone and terminating at the node count, roots in range, variable
    references in range, finite literals and right-hand sides) and `_model_lp_defect` for
    the bound convention. Re-deriving either here would be a second implementation of an
    invariant, and the copy that drifts is the one that reads past a List end.
    """
    var verdict = model_validate(flat)
    if verdict.status != MODEL_OK:
        return LPMatrix(
            verdict.status, 0, 0, 0.0, verdict.constraint_index, verdict.node_index, -1,
            verdict.var_index, List[Float64](), List[Float64](), List[Int](),
            List[Float64](), verdict.message,
        )
    var bounds = _model_lp_defect(flat)
    if bounds != MODEL_OK:
        return LPMatrix(
            bounds, verdict.n_vars, verdict.n_constraints, 0.0, -1, -1, -1, -1,
            List[Float64](), List[Float64](), List[Int](), List[Float64](),
            explain_status_name(bounds),
        )
    return lp_from_arenas(
        flat.obj_ops, flat.obj_values, flat.obj_var_idx,
        flat.obj_lefts, flat.obj_rights, flat.obj_extras, flat.obj_root,
        flat.con_ptr, flat.con_roots, flat.con_senses, flat.con_rhs,
        flat.con_ops, flat.con_values, flat.con_var_idx,
        flat.con_lefts, flat.con_rights, flat.con_extras, len(flat.var_lower),
    )


fn model_binding_constraints(flat: ModelFlat) -> BindingReport:
    """`binding_constraints` for a general model, under the model's OWN policy.

    A `ModelFlat` parameter rather than twenty-eight flat arguments: the proven pattern is
    `graph_analytics.adjacency.graph_csr_dijkstra(GraphCSR, Int)`, and the dispatch
    generator decodes a struct token positionally.
    """
    var lp = _model_lp(flat)
    if lp.status != MODEL_OK:
        return _no_binding(lp.status, lp.n_vars, lp.n_constraints)
    return binding_constraints(
        lp.c, lp.constant, lp.a, lp.n_constraints, lp.n_vars, lp.senses, lp.rhs,
        flat.maximize, flat.max_iterations, flat.feasibility_tol, flat.optimality_tol,
    )


fn model_infeasibility_core(flat: ModelFlat) -> InfeasibilityCore:
    """`infeasibility_core` for a general model. The objective is not consulted."""
    var lp = _model_lp(flat)
    if lp.status != MODEL_OK:
        return _no_core(lp.status, lp.n_constraints, EXPLAIN_GAP_ABSENT, 0)
    return infeasibility_core(
        lp.a, lp.n_constraints, lp.n_vars, lp.senses, lp.rhs,
        flat.max_iterations, flat.feasibility_tol, flat.optimality_tol,
    )


fn model_contributions(flat: ModelFlat) -> ObjectiveDecomposition:
    """`optimum_contributions` for a general model, itemised over its own variables."""
    var lp = _model_lp(flat)
    if lp.status != MODEL_OK:
        return _no_decomposition(lp.status, lp.n_vars, flat.maximize)
    return optimum_contributions(
        lp.c, lp.constant, lp.a, lp.n_constraints, lp.n_vars, lp.senses, lp.rhs,
        flat.maximize, flat.max_iterations, flat.feasibility_tol, flat.optimality_tol,
    )
