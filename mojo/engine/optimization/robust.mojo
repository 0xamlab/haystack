"""
optimization.robust — scenario-based robust LPs and chance constraints. Zero Python.

What this module computes, and what it does NOT prove
-----------------------------------------------------
Three questions, three drivers, one solver underneath (`optimization.linear.lp_solve`,
frozen tier 1 — one call per scenario, no second code path):

1. `robust_scenario_solve` — the WAIT-AND-SEE distribution. One LP per scenario, each
   solved as if that scenario were known in advance, and then the worst case, the best
   case, the sample mean and the CVaR of those per-scenario optima, with the index of the
   scenario that is BINDING for each extreme.

   Its worst case is **not** the robust optimum, and its status says so: on success it
   returns `ROBUST_BOUND_ONLY`, never `MODEL_OK`. For a minimisation, every `x` feasible
   in all scenarios satisfies `f(x, s) >= z*(s)` for each `s`, so
   `max_s f(x, s) >= max_s z*(s)`; taking the min over such `x`,

       min_x max_s f(x, s)  >=  max_s min_x f(x, s)  =  what this driver reports.

   The reported value is therefore a LOWER bound on the robust value when minimising and
   an UPPER bound when maximising — `bound_direction` states which — and it is attained
   only when one `x` happens to be optimal for every scenario at once. A perfect-foresight
   number presented as a robust one is the exact wrong answer this module exists not to
   produce, which is why the success code is not 0.

   `cvar_level` IS A CONFIDENCE, NOT A TAIL FRACTION. `risk.conditional_var` takes
   `1 - tail`, so `cvar_level = 1.0` averages the single WORST scenario and a level
   approaching 0 approaches the average of EVERY scenario. "CVaR at the 5% tail" is
   `cvar_level = 0.95`, and 0.05 asks for something close to the mean. Passing a tail
   fraction understates tail risk by a wide margin and no status would say so, so the result
   carries `cvar_tail_fraction = 1 - cvar_level` — the fraction actually averaged — and the
   driver CHECKS the orientation it claims: a confidence-level CVaR of the costs must lie
   between the sample mean and the worst case, and `has_cvar` is cleared rather than
   reporting a tail number that points the wrong way. Executed on optima 10, 20, 30, 100
   (mean 40): level 0.05 -> 50, 0.5 -> 65, 0.75 -> 100, 1.0 -> 100 = the worst case.

2. `robust_min_max_rhs` — a here-and-now solution that IS optimal for the given scenario
   set, for the case where that reduction is exact: uncertainty in `b` only. `x` is
   feasible in every scenario iff it satisfies every row at the tightest right-hand side
   any scenario supplies (`min_s b_i` for a `<=` row, `max_s b_i` for a `>=` row), because
   `A`, `senses` and `x >= 0` do not vary with the scenario. That intersection is one LP,
   the objective does not vary either (this driver takes no objective scenarios), so its
   optimum is the strictly-robust optimum — and it is then VERIFIED row by row against
   every scenario the caller passed in before it is returned. `optimal_for_scenario_set`
   is set only when all of these hold:

     * `lp_solve` returned `LP_OPTIMAL` (proven by its own duals), and
     * every equality row's right-hand side is constant across scenarios (otherwise the
       robust set is empty by construction — `ROBUST_EQ_CONFLICT`), and
     * the returned `x` satisfies every row in every scenario within that row's own
       budget — measured, not assumed.

   If the verification fails the answer is WITHHELD under `ROBUST_UNVERIFIED`. An
   unverifiable "robust" solution is worse than none, because a caller stops checking.

3. `robust_chance_rates` / `robust_chance_normal` — the MEASURED satisfaction rate of each
   row at a caller-supplied point, over the scenario set. A chance constraint satisfied in
   90% of scenarios is NOT satisfied, so there is no boolean that hides the rate: the rate,
   the count, the requested level and the per-row verdict all come back, together with the
   JOINT rate (the fraction of scenarios in which the point is FEASIBLE — every row holds
   AND `x >= 0`), which is the number a caller actually needs and which no set of per-row
   rates determines.

   WHAT THE JOINT RATE COVERS: this package's feasible set is `A x {senses} b` AND `x >= 0`
   (that is what `lp_solve` optimises over and what the other two drivers verify through
   `_negativity`), so the chance driver measures the same set. `x >= 0` does not vary with
   the scenario, so a negative component fails EVERY scenario at once: `nonnegative` is
   False, `worst_negative` is the magnitude, `joint_rate` is 0.0 and the status is
   `ROBUST_CHANCE_NOT_MET`. The per-row rates are still reported unchanged — a row's
   satisfaction rate at `x` is a measured fact about that row — which is why this is an
   added condition and not a rejection. Measuring only the rows was one declared invariant
   enforced at two strengths in one package (rule 3), and it returned `MODEL_OK` with a 100%
   rate for `x = [-5]`.

What none of this proves
------------------------
*A sampled guarantee is a sampled guarantee.* Every statement above is with respect to the
FINITE scenario set that was passed in. A rate of 0.97 over 100 draws is an estimate of a
probability with sampling error of a few points, not a 97% guarantee; `rate_stderr` reports
the plug-in binomial standard error `sqrt(p(1-p)/S)` of that estimate so the caller can see
its size, and it is a standard error, not a confidence guarantee either.

`robust_min_max_rhs` is optimal over the scenarios GIVEN, and the direction in which that
errs against the true support FLIPS WITH THE SENSE. Enlarging the scenario set can only
shrink the feasible region (a new scenario can only tighten a row, never loosen one), and
shrinking a feasible region RAISES a minimum and LOWERS a maximum. So the reported objective
is a LOWER bound on the true-support objective when MINIMISING and an UPPER bound when
MAXIMISING. Stating one of those two unconditionally is how this docstring was wrong for
every maximisation: `bound_direction` on the result now carries the sign (-1 lower, +1 upper,
0 no value), from `_bound_direction(maximize)` — the single place either driver decides it —
so the claim is machine-readable and cannot drift from the behaviour. Executed, minimising:
scenarios `b = 3, 5` on `x >= b` report 10, and adding `b = 9` reports 18 >= 10. Maximising:
scenarios `b = 3, 5` on `x <= b` report 3, and adding `b = 1` reports 1 <= 3.

Nothing here is a distributional or a probabilistic guarantee, and nothing here is a
guarantee about a scenario nobody drew.

Determinism
-----------
Every draw is addressed, not sequential: scenarios come from `determinism/counter_rng`
through `determinism/sampling_keyed`'s conventions, at coordinates

    master_seed = seed          scenario_id = s          replication_id = 0
    dim0        = row index i   dim1        = 0          stream_id = streams.stream_id(name)
    draw_index  = 0

so cell `(s, i)` is a pure function of `(seed, stream, s, i)` and reproduces exactly
regardless of what was drawn before it, in what order, or on which machine. `ScenarioSet`
carries the seed, the stream id and `rng_version()` back to the caller so a stored result
names the scenario set that produced it. Two runs with the same seed and stream give a
bit-identical block and therefore bit-identical rates; two different seeds give a different
block; the same seed on a different stream name gives a different block.

Tie-breaks that affect a reported answer, all documented and reproducible:

  * `worst_scenario` / `best_scenario` / `worst_row` are the LOWEST index achieving the
    extreme, so equal values do not make the report depend on scan order.
  * `binding_scenario[i]` is the lowest-indexed scenario supplying row `i`'s tightest
    right-hand side.

Common random numbers come out of the addressing for free: cell `(s, i)`'s coordinates do
not mention `S` or the row count, so drawing more scenarios leaves every earlier scenario
bit-identical and adding a row leaves every existing row's draws bit-identical. Two scenario
sets that share a seed and stream therefore agree wherever they overlap, which is what makes
a comparison across two model sizes a comparison of the models rather than of their noise.

Reuse
-----
`lp_solve` (every solve), `risk.conditional_var` (CVaR — the frozen empirical expected
shortfall, whose linearly-interpolated VaR threshold is the definition reported here),
`linalg.vec_dot` (row activity), `model.sense_violation` / `model.minimization_value` /
`model.model_finite`, `linear._lp_input_defect` (the package's one statement of a usable LP
shape, per rule 3 — a hand-copied validator is the copy that reads past a List end),
`linear.LP_FEAS_ULP_BUDGET` / `LP_DBL_EPSILON` (the same rounding budget the simplex uses),
`sparse_numerics.csr.dims_fit` and `MAX_CSR_DIM`, `determinism.counter_rng`,
`determinism.streams`.

Feasibility tolerance
---------------------
A row is satisfied or it is not, and its budget comes from ITS OWN magnitude:

    budget_i = feasibility_tol + LP_FEAS_ULP_BUDGET * DBL_EPSILON * max(|activity_i|, |b_i|)

No sum over rows, no sum over scenarios — an aggregate lets one row's units pay for another
row's contradiction, which is how an infeasible LP was once reported optimal. The relative
term is sized by DBL_EPSILON (what floating point can explain away at that magnitude) and
not by the caller's tolerance, because a fraction of `|b_i|` shrinks with the row while the
violation does not.

EVERY tolerance in this file, and what each is scaled by — there are five, and none is scaled
by an aggregate over other items, by a floor that dominates the real scale, or by the caller's
tolerance times a magnitude:

  1. `_row_budget` — `feasibility_tol + LP_FEAS_ULP_BUDGET * DBL_EPSILON * max(|activity_i|,
     |b_i|)`, i.e. 2.27e-13 of the row's own magnitude, the SAME rounding budget the frozen
     simplex uses. Judges ONE row's violation; scaled by that row's own two magnitudes.
  2. `_negativity` — `_row_budget(feasibility_tol, 0.0, x[j])`, i.e. that COMPONENT's own
     magnitude. Judges how far one coordinate sits below zero.
  3. `_scan_violations` / `_chance_rates_at` — per row and per scenario, `_row_budget` again, so
     the same definition of "satisfied" everywhere. No cross-row and no cross-scenario term.
  4. `_rate_meets` — `8 * DBL_EPSILON * |level * S|`. Judges `count >= level * S`; scaled by
     that threshold's own magnitude, and only to forgive a level such as 2/3 that no Float64
     represents.
  5. `_cvar_bracket_slack` — `8 * DBL_EPSILON * S * max(|a|, |b|)` where `a` and `b` are the two
     averages being compared. Judges the CVaR ORIENTATION check; scaled by those two values'
     own magnitudes times the number of roundings that produced them.

And one place that deliberately has NO tolerance: an equality row's right-hand side must be
BIT-IDENTICAL across scenarios, because any slop there is a constraint the optimality claim
does not cover (see the comment at that branch).

Allocation, and separately WORK
-------------------------------
`n_scenarios` is the one dimension NOT tied to the payload — a scenario count is a request,
not data — so it is bounded twice: by `ROBUST_MAX_SCENARIOS` alone (a zero-row model makes
`S * rows` zero for any `S`, so the product check cannot see it) and by the product
`S * rows` against `ROBUST_MAX_SCENARIO_CELLS`, with a DIVISION, because `S * rows` is a
wrapping multiply. Every other dimension is payload-tied: `rows == len(senses) == len(rhs)`,
`cols == len(c) == len(x)`, `rows * cols == len(a)` via `dims_fit`, and a scenario block is
exactly `S * rows` (or `S * cols`) cells long.

BOUNDING MEMORY IS NOT BOUNDING WORK, and `S` multiplies into both. The same unpayloaded
integer that would allocate a block also drives S full two-phase simplex solves, S draws per
row, and S row-scans, and in a single-threaded worker a minute of CPU from a 120-byte request
presents to every other client as exactly the hang an allocation bomb does. Measured before
this bound existed: `S = 200000` on a 1x1 model took 699 ms (3.5 us/solve), so the
allocation-legal ceiling `S = 2^23` was ~29 s, and a 4-million-scenario re-verification of
one row took 291 ms. So every loop bound that multiplies into the cost is charged against
`ROBUST_MAX_WORK_UNITS` before any of it runs — solves via `_lp_work_units`, drawn cells and
row-scans at one unit each — and an over-budget request is `ROBUST_ERR_WORK_BUDGET` with
nothing computed. The work bound BINDS BEFORE the cell bound for the drivers that touch every
cell; that is intended, and it is why both exist.
"""
from std.math import abs as fabs, sqrt

from determinism.counter_rng import rng_normal_scaled, rng_uniform, rng_version
from determinism.streams import stream_id
from linalg import vec_dot
from math_ext import mean
from optimization.linear import (
    LP_DBL_EPSILON,
    LP_FEAS_ULP_BUDGET,
    LP_INFEASIBLE,
    LP_OPTIMAL,
    LP_UNBOUNDED,
    _lp_input_defect,
    lp_solve,
    lp_status_name,
)
from optimization.model import (
    DEFAULT_FEASIBILITY_TOL,
    DEFAULT_INTEGRALITY_TOL,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_OPTIMALITY_TOL,
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_ERR_NON_FINITE_COEFFICIENT,
    MODEL_ERR_NON_FINITE_POINT,
    MODEL_ERR_NON_FINITE_RHS,
    MODEL_ERR_NON_FINITE_VALUE,
    MODEL_ERR_POINT_LENGTH,
    MODEL_ERR_SENSE,
    MODEL_OK,
    MODEL_VIOLATION_ABSENT,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    _policy_parts_defect,
    minimization_value,
    model_finite as _finite,
    sense_violation,
)
from risk import conditional_var
from sparse_numerics.csr import MAX_CSR_DIM, dims_fit

# ── status codes ──────────────────────────────────────────────────────────────
# THIS PACKAGE'S ALLOCATION, recorded so the next module does not reuse a number.
# Taken in the shared `optimization.model` status chain:
#     0-30    model   (MODEL_OK .. MODEL_ERR_FROZEN_EVAL_RAISED)
#     40-42   linear  (the linearity extractor)
#     60-63   linear  (the simplex outcomes)
#     80-86   explain
#     100-105 integer (MILP)
#     110-117 quadratic
#     120-129 routing
#     130-139 scheduling
#     140-149 multiobjective
#     150-159 robust  (this file — FULL, all ten used)
#     170-170 robust  (this file — the work budget, see the note below)
# `optimization.flow` (0-21) and `optimization.assignment` (0-13) are self-contained
# namespaces with their own name tables and are NOT part of this chain.
#
# Codes 64-79, 87-99, 106-109, 118-119, 160-169 and 171+ are unallocated. Tier 1 handed out
# 80-84 twice, so `milp_status_name(81)` and `explain_status_name(81)` named different
# outcomes in one package; a caller that logs a status integer could not tell which vocabulary
# produced it.
#
# 160 is deliberately NOT taken for this file's eleventh code. 160-169 is the block a sibling
# extending upward from 149 picks first, and this package's second block was allocated while
# those files were being edited in parallel; skipping to 170 makes the collision impossible
# instead of unlikely. Leaving a gap costs nothing — a status code is an identity, not an index.

# The scenario block's shape was rejected: a negative or zero count, a block whose length is
# not exactly `S * rows` (or `S * cols`), or a count whose product with the row width exceeds
# the allocation budget. Nothing was indexed and nothing was allocated.
comptime ROBUST_ERR_SCENARIO_SHAPE: Int = 150

# A confidence or CVaR level outside (0, 1].
#
# ORIENTATION, stated here because this is where a caller looks it up: both `cvar_level` and
# `confidence` are CONFIDENCE levels, in the same sense as `risk.value_at_risk` and
# `risk.conditional_var`, i.e. `1 - tail fraction`.
#
#   * `cvar_level = 1.0` is legal and averages the single WORST scenario — the largest cost
#     when minimising. It does NOT mean "every scenario".
#   * `cvar_level` approaching 0 approaches the average of every scenario, i.e. the mean. It is
#     rejected AT 0 because a tail of zero width names no scenario at all.
#   * "CVaR at the 5% tail" is therefore `cvar_level = 0.95`, NOT 0.05.
#   * For `confidence` in the chance drivers the same reading is the ordinary one: 0.95 is
#     "must hold in at least 95% of scenarios".
#
# Verified against `risk.conditional_var` on optima 10, 20, 30, 100 (mean 40): 0.05 -> 50,
# 0.25 -> 50, 0.5 -> 65, 0.75 -> 100, 1.0 -> 100. This comment previously said 1.0 meant
# "every scenario" and 0 "the average of no scenarios", which is the orientation reversed, and
# it was the module's whole specification of the convention; a caller following it passed 0.05
# for a 5% tail and got 50 where the answer is 100. `RobustScenarioResult.cvar_tail_fraction`
# now reports `1 - cvar_level` so the convention is in the RESULT and not only in a comment.
comptime ROBUST_ERR_CONFIDENCE: Int = 151

# A scenario generator argument that cannot produce a scenario: a negative or non-finite
# standard deviation or half-width. A ZERO dispersion is legal — it produces S identical
# scenarios, which is the degenerate case a robust answer must agree with.
comptime ROBUST_ERR_DISPERSION: Int = 152

# At least one scenario's LP did not reach an optimum (infeasible, unbounded, iteration
# limit, breakdown). No aggregate is returned: a worst case computed over the scenarios that
# happened to solve is a number about a different problem than the one asked about.
comptime ROBUST_SCENARIO_FAILED: Int = 153

# SUCCESS for `robust_scenario_solve`, and deliberately not 0: the value is real and every
# scenario solved, but it is a wait-and-see BOUND on the robust value, not the robust value.
# See `bound_direction` for which side it bounds.
comptime ROBUST_BOUND_ONLY: Int = 154

# No point is feasible in every scenario at once. Distinct from `LP_INFEASIBLE`, which is a
# statement about one program the caller wrote; each individual scenario here may well be
# feasible on its own.
comptime ROBUST_INFEASIBLE: Int = 155

# The robust program is unbounded, so it has no optimum to report.
comptime ROBUST_UNBOUNDED: Int = 156

# An equality row's right-hand side is not constant across scenarios, so the intersection of
# the scenario feasible sets is empty BY CONSTRUCTION. Reported separately from
# `ROBUST_INFEASIBLE` because it is a modelling fact found without a solve, and
# `conflict_row` names the row.
comptime ROBUST_EQ_CONFLICT: Int = 157

# A measured satisfaction rate is below the requested level. The rates are still returned —
# this status is the answer to "did it meet the level", never a replacement for the number.
comptime ROBUST_CHANCE_NOT_MET: Int = 158

# The solution the LP returned failed post-hoc verification against the caller's own
# scenario data. Defensive: it should be unreachable, and if it fires the answer is withheld
# rather than returned with a caveat nobody reads.
comptime ROBUST_UNVERIFIED: Int = 159

# The request is inside every ALLOCATION ceiling and would still take an unbounded amount of
# CPU, so nothing was computed. A refusal, not a partial sweep: a worst case, a rate or a CVaR
# over the scenarios that happened to fit in a time budget is a number about a scenario set the
# caller did not ask about, which is the same reason `ROBUST_SCENARIO_FAILED` withholds
# everything. 170 rather than 160 — see the allocation note in the status block above.
comptime ROBUST_ERR_WORK_BUDGET: Int = 170

# ── scenario kinds ────────────────────────────────────────────────────────────

comptime SCENARIO_KIND_EXPLICIT: Int = 0
comptime SCENARIO_KIND_NORMAL: Int = 1
comptime SCENARIO_KIND_UNIFORM: Int = 2

# Draw indices inside one `(seed, scenario, row, stream)` coordinate. `rng_normal_scaled` is
# Box-Muller and consumes a FIXED two draws (0 and 1), so the uniform generator starts at 2.
# Sharing index 0 would hand the two generators the SAME underlying uniform for the same cell,
# and a model whose rows came from both would have perfectly rank-correlated rows with nothing
# anywhere failing. Both values are frozen: changing either re-addresses every draw.
comptime NORMAL_DRAW_INDEX: UInt64 = 0
comptime UNIFORM_DRAW_INDEX: UInt64 = 2

# ── allocation ceilings ───────────────────────────────────────────────────────
# `MAX_CSR_DIM` (2^26) is the ONE shared dimension ceiling and is not redefined or moved
# here; both constants below are derived from it by dividing by the number of arrays of that
# size a driver holds live at once, per rule 1c.
#
# Cells: a scenario block is one `S * rows` array. `robust_chance_normal` holds the block it
# drew while the rates driver borrows it, and a caller normally holds the `ScenarioSet` too,
# so budget four such arrays: 2^24 cells is 134 MB each, 536 MB for four, which is the
# 512 MiB one-resident-object budget in `algenta_runtime.session`.
comptime ROBUST_MAX_SCENARIO_CELLS: Int = MAX_CSR_DIM // 4

# Scenarios: `robust_scenario_solve` holds five `S`-length arrays at peak — `objectives`,
# `scenario_status`, the minimisation-sense `costs`, the negated `returns` handed to
# `risk.conditional_var`, and that function's own internal sorted copy. 2^23 is 67 MB each,
# 335 MB for five. This bound is needed IN ADDITION to the cell bound because `dims_fit(S, 0,
# 0)` is true for every `S`: a zero-row model makes the product invisible.
comptime ROBUST_MAX_SCENARIOS: Int = MAX_CSR_DIM // 8

# How many ulps of a rate's own magnitude a level comparison may forgive. A rate is a ratio
# of small integers and 3/4 is exact in binary, but a level such as 2/3 is not representable,
# so `count >= level * S` needs the same ulp-sized slack the row budgets use — sized by
# DBL_EPSILON, never by a caller tolerance.
comptime ROBUST_RATE_ULP_BUDGET: Float64 = 8.0

# How many ulps of ITS OWN magnitude the CVaR orientation check may forgive per summed term.
# The two quantities compared are two averages of the SAME S costs, so S roundings at the
# compared value's own magnitude is the error model — see `_cvar_bracket_slack`.
comptime ROBUST_CVAR_ULP_BUDGET: Float64 = 8.0

# ── the work budget ───────────────────────────────────────────────────────────
# Calibrated, not guessed. One unit is ~0.16 us of single-threaded worker time on the machine
# these two numbers were measured on:
#
#   * a 1x1 `lp_solve` measured 3.5 us  -> `_lp_work_units` charges 16 + 2*3   = 22 units
#   * a 5x5 `lp_solve` measured 16.1 us -> `_lp_work_units` charges 16 + 6*11  = 82 units
#
# which is 6.3 and 5.1 units/us — one currency for both, which a bare solve COUNT is not (a
# 100x100 solve is three orders of magnitude dearer than a 1x1 one). A drawn scenario cell and
# a single row-scan are each ~0.07-0.15 us and are charged 1 unit, so both are over-charged
# rather than under-charged. 2^23 units is therefore ~1.4 s, which is the outer limit for one
# synchronous request in a worker shared with every other client.
#
# This is a CPU ceiling and is deliberately independent of `ROBUST_MAX_SCENARIO_CELLS`: a
# request can sit inside every allocation bound and still ask for a minute of arithmetic.
comptime ROBUST_LP_SETUP_UNITS: Int = 16
comptime ROBUST_MAX_WORK_UNITS: Int = 1 << 23


def robust_status_name(code: Int) -> String:
    """Name for a robust status, falling through to the shared `optimization` chain.

    The fall-through is what makes an input rejection legible: a bad LP shape comes back as
    `optimization.model`'s own code and keeps `optimization.model`'s own name.
    """
    if code == ROBUST_ERR_SCENARIO_SHAPE:
        return "scenario_shape_rejected"
    if code == ROBUST_ERR_CONFIDENCE:
        return "confidence_level_out_of_range"
    if code == ROBUST_ERR_DISPERSION:
        return "invalid_scenario_dispersion"
    if code == ROBUST_SCENARIO_FAILED:
        return "scenario_lp_did_not_solve"
    if code == ROBUST_BOUND_ONLY:
        return "found_but_only_a_bound_on_the_robust_value"
    if code == ROBUST_INFEASIBLE:
        return "no_point_feasible_in_every_scenario"
    if code == ROBUST_UNBOUNDED:
        return "robust_program_unbounded"
    if code == ROBUST_EQ_CONFLICT:
        return "equality_rhs_differs_across_scenarios"
    if code == ROBUST_CHANCE_NOT_MET:
        return "chance_level_not_met"
    if code == ROBUST_UNVERIFIED:
        return "solution_failed_scenario_verification"
    if code == ROBUST_ERR_WORK_BUDGET:
        return "scenario_sweep_exceeds_work_budget"
    return lp_status_name(code)


# ── return-only result structs ────────────────────────────────────────────────
# Declared HERE because `mojo_inventory.parse_runtime_struct_specs` reads one file at a
# time: a driver returning a struct owned by another module is dropped from the runtime
# contract and from dispatch silently.


@fieldwise_init
struct ScenarioSet(Copyable, Movable):
    """A drawn scenario set with the coordinates that produced it.

    `rhs` is row-major `S * n_rows`: scenario `s`, row `i` is `rhs[s * n_rows + i]`. On any
    status other than `MODEL_OK` it is EMPTY, never zero-filled — an all-zero right-hand
    side is a perfectly ordinary scenario and cannot also mean "there are no scenarios".

    `seed`, `stream` and `rng` are the provenance: the same three plus `kind` and the base
    arguments reproduce `rhs` bit for bit, which is what makes a stored robust answer
    auditable rather than merely plausible.
    """

    var status: Int
    var n_scenarios: Int
    var n_rows: Int
    var kind: Int
    var seed: UInt64
    var stream: UInt64
    var rng: String
    var rhs: List[Float64]


@fieldwise_init
struct RobustScenarioResult(Copyable, Movable):
    """Per-scenario optima and their risk summary, or a status and no numbers.

    `has_value` is the authority. It is True only when EVERY scenario reached an optimum:
    `objectives` is empty and every aggregate is padding when even one scenario failed,
    because a worst case over a subset is a statement about a different scenario set than
    the caller asked about. `scenario_status` is still returned in that case — it is the
    diagnosis, one `lp_solve` status per scenario in scenario order.

    `worst_case` is the worst in the CALLER's sense: the largest objective when minimising,
    the smallest when maximising. `bound_direction` is -1 when that value is a LOWER bound
    on the robust optimum (minimisation), +1 when it is an UPPER bound (maximisation), and 0
    when there is no value. `worst_scenario` / `best_scenario` are the lowest indices
    attaining them, and -1 when there is no value.

    `cvar` is `risk.conditional_var` at `cvar_level` over the per-scenario objectives read
    as costs (negated when maximising, and reported back in the caller's sense). It is the
    frozen empirical expected shortfall — the average of the scenarios at or beyond a
    linearly interpolated VaR threshold, over the given scenarios treated as equally likely.

    `cvar_level` IS A CONFIDENCE (`1 - tail`), not a tail fraction: 1.0 averages the single
    WORST scenario and a level near 0 approaches the mean. `cvar_tail_fraction` is
    `1 - cvar_level`, the fraction of scenarios actually averaged, and it is in the result so
    that the convention travels WITH the number instead of living in a comment that can invert:
    a caller who meant "the 5% tail" and passed 0.05 sees `cvar_tail_fraction = 0.95` and knows
    immediately. It is 0.0 when the level was rejected as non-finite. `has_cvar` is also
    cleared when the returned CVaR does not lie between `mean_objective` and `worst_case` in
    the caller's sense, which is the orientation this convention implies — two mutually
    exclusive claims in one result leave a caller able to use neither.
    """

    var status: Int
    var n_scenarios: Int
    var n_solved: Int
    var n_failed: Int
    var first_failed_scenario: Int
    var first_failed_status: Int
    var has_value: Bool
    var worst_case: Float64
    var worst_scenario: Int
    var best_case: Float64
    var best_scenario: Int
    var mean_objective: Float64
    var cvar_level: Float64
    var cvar_tail_fraction: Float64
    var has_cvar: Bool
    var cvar: Float64
    var bound_direction: Int
    var objectives: List[Float64]
    var scenario_status: List[Int]


@fieldwise_init
struct RobustMinMaxResult(Copyable, Movable):
    """The strictly-robust optimum over the given scenarios, verified, or no numbers.

    `x` and `objective` exist only when `has_objective` is True, which requires the
    intersection LP to have proven an optimum AND the verification pass to have found no
    violated row in any scenario. `optimal_for_scenario_set` is the stronger claim and
    carries the conditions listed in the module docstring; it is never set from a solve
    alone.

    `effective_rhs[i]` is the tightest right-hand side row `i` takes over the scenarios and
    `binding_scenario[i]` the lowest-indexed scenario supplying it (-1 when the base
    right-hand side was used because no scenario block was given, or for an equality row
    solved at the midpoint of an exactly-constant range). A robust answer whose binding
    scenario is unknown cannot be interrogated, so both are always returned when the shape
    validated.

    `worst_violation` is `MODEL_VIOLATION_ABSENT` (-1.0) when verification never ran, and a
    real magnitude — 0.0 included — when it did. `conflict_row` is the equality row whose
    right-hand side varies, or -1.

    `bound_direction` is the direction in which this answer errs against the TRUE SUPPORT of
    the uncertainty, and it flips with the sense: -1 when the objective is a LOWER bound on the
    true-support objective (minimising — a wider scenario set can only tighten a row, and a
    tighter feasible set raises a minimum) and +1 when it is an UPPER bound (maximising, where
    the same tightening lowers the optimum). 0 when there is no objective. It comes from
    `_bound_direction`, shared with `RobustScenarioResult`, so the two structs cannot disagree.
    A robust answer is used FOR its direction — "my worst-case profit is at least 3" and "at
    most 3" lead to opposite decisions — so it is a field and not a docstring sentence.

    `scenario_data_given` is False when `rhs_scenarios` was empty, i.e. the caller declared
    that nothing varies. `n_distinct_scenarios` is then 1, not `n_scenarios`: with no block
    there is exactly ONE right-hand side, the base one, and `n_verified_scenarios` /
    `n_violating_scenarios` / `feasible_rate` are measured over those DISTINCT scenarios.
    Reporting "verified in 1000 of 1000 scenarios" for a caller who supplied no scenario data
    at all is evidence that does not exist, and re-checking one row 1000 times is not a
    measurement — it is the same measurement 1000 times.
    """

    var status: Int
    var n_scenarios: Int
    var n_rows: Int
    var n_vars: Int
    var has_objective: Bool
    var objective: Float64
    var optimal_for_scenario_set: Bool
    var bound_direction: Int
    var lp_status: Int
    var iterations: Int
    var conflict_row: Int
    var scenario_data_given: Bool
    var n_distinct_scenarios: Int
    var n_verified_scenarios: Int
    var n_violating_scenarios: Int
    var feasible_rate: Float64
    var worst_violation: Float64
    var worst_violation_row: Int
    var worst_violation_scenario: Int
    var x: List[Float64]
    var effective_rhs: List[Float64]
    var duals: List[Float64]
    var binding_scenario: List[Int]


@fieldwise_init
struct ChanceResult(Copyable, Movable):
    """Measured per-row satisfaction rates at a point, with the level they were judged against.

    `rates[i] = counts[i] / n_scenarios` is the MEASURED fraction of scenarios in which row
    `i` holds, and it is returned whenever the shape validated — a status never stands in for
    it. `met[i]` is that rate against `confidence`; `all_rows_met` is the conjunction over
    rows; `joint_rate` is the fraction of scenarios in which the point is FEASIBLE — every row
    holds AND `x >= 0` — which is not determined by the per-row rates and is usually the number
    that matters.

    `x >= 0` is part of this package's feasible set (it is what `lp_solve` optimises over and
    what the other two drivers verify), it does not vary with the scenario, and so a negative
    component fails every scenario at once: `nonnegative` is False, `worst_negative` is how far
    below zero the most negative component sits at its own magnitude's budget, `joint_rate` is
    0.0 and the status is `ROBUST_CHANCE_NOT_MET`. `nonnegative` is True and `worst_negative`
    0.0 whenever the point is admissible. The per-row rates are unaffected: a row's satisfaction
    rate at `x` is a fact about that row, so this is an ADDED condition, never a substitute for
    the numbers. Measuring only the rows returned `MODEL_OK` with a rate of 1.0 for `x = [-5]`,
    a point the sibling drivers reject.

    `status` is `MODEL_OK` only when every per-row rate AND the joint rate meet the level, so
    a caller that branches on the status alone is never told "met" while the joint rate is
    below the level. `all_rows_met` and `joint_met` say which half failed.

    `rate_stderr[i]` is the plug-in binomial standard error `sqrt(p(1-p)/S)` of the rate
    ESTIMATE. It is a measure of sampling noise, not a confidence guarantee, and it does not
    make a sampled rate into a probability bound.

    `worst_row` is the lowest-indexed row attaining the minimum rate, or -1 when there are no
    rows. With zero rows every scenario satisfies all of them vacuously, so `joint_rate` is
    1.0 and `rates` is empty — that is the honest reading of an unconstrained point.

    `drawn` distinguishes a block this module generated (`seed` / `stream` meaningful) from
    one the caller supplied (both 0 and meaningless).
    """

    var status: Int
    var n_scenarios: Int
    var n_rows: Int
    var confidence: Float64
    var drawn: Bool
    var seed: UInt64
    var stream: UInt64
    var has_rates: Bool
    var nonnegative: Bool
    var worst_negative: Float64
    var all_rows_met: Bool
    var joint_met: Bool
    var n_rows_unmet: Int
    var worst_row: Int
    var worst_rate: Float64
    var joint_rate: Float64
    var rates: List[Float64]
    var counts: List[Int]
    var met: List[Bool]
    var rate_stderr: List[Float64]


# ── shared guards ─────────────────────────────────────────────────────────────


def _row_budget(feasibility_tol: Float64, rhs_value: Float64, activity: Float64) -> Float64:
    """The absolute slack one row may have, from ITS OWN magnitude and nothing else.

    `feasibility_tol` is the caller's absolute allowance; the second term is a ROUNDING
    allowance at this row's magnitude, sized by DBL_EPSILON. Deliberately not
    `feasibility_tol * (1 + Σ|b|)` (an unrelated large row then pays for this row's
    contradiction) and not `feasibility_tol * (1 + |b_i|)` either (the fraction shrinks with
    the row's magnitude while a violation does not, so `{x >= 1e9, x <= 1e9 - 1}` passes).
    """
    var mag = fabs(rhs_value)
    var act = fabs(activity)
    if act > mag:
        mag = act
    return feasibility_tol + LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * mag


def _bound_direction(maximize: Bool) -> Int:
    """+1 when a reported optimum is an UPPER bound, -1 when it is a LOWER bound, 0 has no value.

    THE ONE PLACE either driver decides this, because the same flip governs both of the module's
    bound claims and a docstring that stated one of them unconditionally was wrong for every
    maximisation:

      * `robust_scenario_solve` reports `max_s min_x f(x, s)`, and
        `min_x max_s f(x, s) >= max_s min_x f(x, s)` when minimising, so the report is a LOWER
        bound on the robust value; negate `f` and both inequalities flip, so it is an UPPER
        bound when maximising.
      * `robust_min_max_rhs` reports the optimum over the scenarios GIVEN. A scenario nobody
        drew can only TIGHTEN a row (a smaller `min_s b_i`, a larger `max_s b_i`), never loosen
        one, so the true-support feasible set is a SUBSET. A smaller feasible set RAISES a
        minimum and LOWERS a maximum, so the report is again a lower bound when minimising and
        an upper bound when maximising.

    Both statements therefore carry the same sign, which is why one helper serves both structs.
    A caller comparing against a threshold needs this integer, not a sentence: a bound used in
    the wrong comparison cannot be detected downstream.
    """
    if maximize:
        return 1
    return -1


def _bound_direction_agrees(reported: Float64, over_wider_set: Float64, direction: Int) -> Bool:
    """Does `direction` describe how `reported` actually relates to a WIDER scenario set's value.

    `direction == 1` claims `reported` is an upper bound, so a wider (tighter-feasible) set must
    not exceed it; `-1` claims a lower bound, so a wider set must not fall below it. Exposed for
    the suite to assert the DIRECTION rather than only the numbers, which is what stops the
    claim and the behaviour drifting apart again. Exact comparison: the two values come from the
    same solver on nested scenario sets, and the property is an inequality, not an equality, so
    there is no rounding to forgive.
    """
    if direction > 0:
        return over_wider_set <= reported
    if direction < 0:
        return over_wider_set >= reported
    return False


def _cvar_bracket_slack(n_scenarios: Int, a: Float64, b: Float64) -> Float64:
    """Rounding allowance for comparing two averages of the SAME `S` costs.

    `a` and `b` are both an average (or a single member) of the one cost list, so what floating
    point cannot explain away about their DIFFERENCE is the accumulated rounding of that
    summation: about `S` roundings at the compared value's own magnitude. Hence
    `S * DBL_EPSILON * max(|a|, |b|)` — sized by DBL_EPSILON, from the magnitude of the two
    quantities actually being judged, and NOT from a sum or max over the cost list (which would
    let one huge scenario's units pay for an orientation error in the others), NOT from a floor
    of 1.0 (which would be an absolute allowance of one unit of objective), and NOT from any
    caller tolerance (`feasibility_tol` is a constraint budget and says nothing about an
    objective average).
    """
    var mag = fabs(a)
    if fabs(b) > mag:
        mag = fabs(b)
    return ROBUST_CVAR_ULP_BUDGET * LP_DBL_EPSILON * Float64(n_scenarios) * mag


def _lp_work_units(rows: Int, cols: Int) -> Int:
    """Cost proxy for ONE `lp_solve` call, in the units `ROBUST_MAX_WORK_UNITS` counts.

    A fixed setup charge plus the phase-1 tableau area `(rows + 1) * (rows + cols + 1)`, which
    is one currency across shapes: measured 22 units for a 1x1 solve at 3.5 us and 82 for a 5x5
    at 16.1 us, i.e. 6.3 and 5.1 units per microsecond. A bare COUNT of solves is not a bound on
    time at all, which is the trap rule 1c names — a dimension inside the allocation ceiling can
    still drive an unbounded number of operations.

    Saturates instead of multiplying when the area itself would wrap: the caller only ever
    compares against the budget, and a value one past it is refused either way.
    """
    var m = rows + 1
    var n = rows + cols + 1
    if m < 1 or n < 1:
        return ROBUST_MAX_WORK_UNITS + 1
    if m > ROBUST_MAX_WORK_UNITS // n:
        return ROBUST_MAX_WORK_UNITS + 1
    return ROBUST_LP_SETUP_UNITS + m * n


def _cell_units(n_scenarios: Int, per_scenario: Int) -> Int:
    """`n_scenarios * per_scenario` units, saturating rather than wrapping.

    One unit per drawn cell and one per row-scan, both of which measured under a unit
    (~0.07-0.15 us against ~0.16), so this over-charges rather than under-charges. `S * rows` is
    a wrapping 64-bit multiply — `3 * 6148914691236517206 == 2` — so the product is tested with
    a DIVISION exactly as `_scenario_count_defect` does for the allocation bound.
    """
    if n_scenarios < 1 or per_scenario < 1:
        return 0
    if n_scenarios > ROBUST_MAX_WORK_UNITS // per_scenario:
        return ROBUST_MAX_WORK_UNITS + 1
    return n_scenarios * per_scenario


def _work_defect(n_solves: Int, rows: Int, cols: Int, cell_units: Int) -> Int:
    """`MODEL_OK` when `n_solves` solves plus `cell_units` cell operations fit the CPU budget.

    Charged BEFORE any of it runs, and every loop bound that multiplies an UNPAYLOADED integer
    into the cost is in here: the per-scenario solves, the drawn cells and the row-scans.
    Additions are ordered so no intermediate can wrap — each term is compared against what is
    left of the budget rather than summed first.

    What is deliberately NOT charged, and why it is bounded anyway:

      * one pass over the caller's own arrays — `_activity` / `_row_of` over `rows * cols`, and
        the finiteness sweeps over `len(rhs_scenarios)` — is O(bytes the caller actually sent).
        A `rows * cols` of 2^26 requires a 512 MB payload, so it is bounded by the request, not
        by an integer naming work nobody paid for. That is the distinction rule 1c draws, and it
        is why `n_scenarios` needed a bound and `len(a)` does not.
      * the per-scenario `_activity` inside `robust_scenario_solve` IS multiplied by `S`, but
        `_lp_work_units` charges `(rows + 1) * (rows + cols + 1)` per scenario, which dominates
        one `rows * cols` matvec plus a `rows`-long scan — the solve is the expensive half by
        orders of magnitude, so the charge already covers what rides along with it.
    """
    var remaining = ROBUST_MAX_WORK_UNITS
    if cell_units > remaining:
        return ROBUST_ERR_WORK_BUDGET
    remaining -= cell_units
    if n_solves > 0:
        var per = _lp_work_units(rows, cols)
        if per > remaining:
            return ROBUST_ERR_WORK_BUDGET
        if n_solves > remaining // per:
            return ROBUST_ERR_WORK_BUDGET
    return MODEL_OK


def _scenario_count_defect(n_scenarios: Int, rows: Int) -> Int:
    """`MODEL_OK` when `S` and `S * rows` are both inside the allocation budget.

    Both halves are needed. The count alone does not bound the block (`S = 8` with
    `rows = 2^26` is 2 GB) and the product alone does not bound the count (`dims_fit(S, 0, 0)`
    is true for every `S`, so a zero-row model hides it). The product is tested with a
    DIVISION because `S * rows` is a wrapping 64-bit multiply: `3 * 6148914691236517206 == 2`.
    """
    if n_scenarios < 1 or n_scenarios > ROBUST_MAX_SCENARIOS:
        return ROBUST_ERR_SCENARIO_SHAPE
    if rows < 0 or rows > MAX_CSR_DIM:
        return ROBUST_ERR_SCENARIO_SHAPE
    if rows > 0 and n_scenarios > ROBUST_MAX_SCENARIO_CELLS // rows:
        return ROBUST_ERR_SCENARIO_SHAPE
    return MODEL_OK


def _scenario_block_defect(block: List[Float64], n_scenarios: Int, width: Int) -> Int:
    """`MODEL_OK` when `block` is either EMPTY or exactly `S * width` finite cells.

    Empty means "this quantity does not vary", which is a real answer and not a rejection:
    the base vector is then used for every scenario. Any other length is a rejection, and
    `dims_fit` does the check because the product wraps.
    """
    if len(block) == 0:
        return MODEL_OK
    var count_defect = _scenario_count_defect(n_scenarios, width)
    if count_defect != MODEL_OK:
        return count_defect
    if not dims_fit(n_scenarios, width, len(block)):
        return ROBUST_ERR_SCENARIO_SHAPE
    return MODEL_OK


def _level_defect(level: Float64) -> Int:
    """`MODEL_OK` for a level in (0, 1]. A `nan` fails every comparison, so it is rejected."""
    if not _finite(level):
        return ROBUST_ERR_CONFIDENCE
    if level <= 0.0 or level > 1.0:
        return ROBUST_ERR_CONFIDENCE
    return MODEL_OK


def _rate_meets(count: Int, n_scenarios: Int, level: Float64) -> Bool:
    """`count / S >= level`, compared as `count >= level * S` with an ulp-sized slack.

    The multiply keeps the exact integer count out of a division that would round it, and the
    slack covers a level such as 2/3 that no Float64 represents. It is sized by DBL_EPSILON
    at the threshold's own magnitude, so it can forgive a representation error and nothing
    larger: at `level = 0.75, S = 4` both sides are exact and the slack is irrelevant.
    """
    var needed = level * Float64(n_scenarios)
    var slack = ROBUST_RATE_ULP_BUDGET * LP_DBL_EPSILON * fabs(needed)
    return Float64(count) >= needed - slack


def _row_of(a: List[Float64], row: Int, cols: Int) -> List[Float64]:
    """Row `row` of a flat row-major matrix, copied out so `vec_dot` can take it."""
    var out = List[Float64]()
    for j in range(cols):
        out.append(a[row * cols + j])
    return out^


def _activity(
    a: List[Float64], rows: Int, cols: Int, x: List[Float64], mut ok: Bool
) -> List[Float64]:
    """`A x`, one entry per row, through the frozen `linalg.vec_dot`.

    `ok` is cleared and the list comes back EMPTY when any entry is not finite. That has to be
    a separate signal: a non-finite activity makes every `fabs(v) > tol` comparison False, so
    an audit that skipped this check would pass having counted zero violations — the `nan`
    trap that let a certificate certify a wrong matching. The scenario never enters the
    tolerance arithmetic at all.
    """
    ok = True
    var out = List[Float64]()
    for i in range(rows):
        var v = vec_dot(_row_of(a, i, cols), x)
        if not _finite(v):
            ok = False
            out.clear()
            return out^
        out.append(v)
    return out^


@fieldwise_init
struct _Violation(Copyable, Movable):
    """The worst row violation found in one scan. Private: it never enters a public signature.

    `worst` is 0.0 when every row holds, and `row` is then -1. `measured` is False only when
    the scan could not be made at all, which keeps "verified clean" and "not checked" apart —
    the distinction rule 4 exists for, at the level of the check rather than the answer.
    """

    var measured: Bool
    var worst: Float64
    var row: Int


def _negativity(x: List[Float64], feasibility_tol: Float64) -> Float64:
    """How far below zero the most negative component of `x` sits, 0.0 when none is.

    `lp_solve` optimises over `A x {senses} b` AND `x >= 0`, so a certificate that only checks
    the rows is checking part of the feasible set it claims to have searched — the rule-4d
    omission, in the shape it takes here. `x >= 0` does not vary with the scenario, so a
    negative component violates EVERY scenario at once, which is how the callers report it.
    """
    var worst: Float64 = 0.0
    for j in range(len(x)):
        var below = -x[j]
        if below > _row_budget(feasibility_tol, 0.0, x[j]) and below > worst:
            worst = below
    return worst


def _scan_violations(
    activity: List[Float64], senses: List[Int], rhs_vector: List[Float64],
    rows: Int, feasibility_tol: Float64,
) -> _Violation:
    """The largest per-row violation of `A x {senses} rhs_vector`, at each row's own budget.

    THE one definition of "this point satisfies this scenario" in the module: the min-max
    driver's verification pass and the per-scenario verification in `robust_scenario_solve`
    both call it, so a solution cannot be accepted by one driver and rejected by the other. A
    `sense_violation` of `MODEL_VIOLATION_ABSENT` (-1.0) — an unmeasurable row — is reported
    as `measured = False` rather than folded into the maximum, because -1.0 would read as
    "less violated than 0.0".
    """
    var worst: Float64 = 0.0
    var worst_row = -1
    for i in range(rows):
        var budget = _row_budget(feasibility_tol, rhs_vector[i], activity[i])
        var v = sense_violation(activity[i], senses[i], rhs_vector[i], budget)
        # `< 0.0` rather than `== MODEL_VIOLATION_ABSENT`: a violation is a magnitude and can
        # never be negative, so any negative value is a sentinel whatever its exact value, and
        # this does not have to stay in step with the constant's numeric value.
        if v < 0.0:
            return _Violation(False, MODEL_VIOLATION_ABSENT, i)
        if v > worst:
            worst = v
            worst_row = i
    return _Violation(True, worst, worst_row)


def _empty_scenario_set(status: Int, kind: Int, seed: UInt64, stream: UInt64) -> ScenarioSet:
    return ScenarioSet(status, 0, 0, kind, seed, stream, rng_version(), List[Float64]())


def _no_scenario_result(status: Int, n_scenarios: Int, cvar_level: Float64) -> RobustScenarioResult:
    """A rejection: no aggregates, no per-scenario record, and `bound_direction` 0.

    `first_failed_scenario` is -1 and `first_failed_status` is `MODEL_OK` because no scenario
    failed — nothing was solved. Copying `status` into the per-scenario field would report an
    input rejection as a property of scenario 0.

    `cvar_tail_fraction` is `1 - cvar_level` when that is a real number and 0.0 otherwise: a
    rejected non-finite level must not come back as a non-finite tail fraction, which a caller
    that trusted the status would then do arithmetic with.
    """
    var tail: Float64 = 0.0
    if _finite(cvar_level):
        tail = 1.0 - cvar_level
    return RobustScenarioResult(
        status, n_scenarios, 0, 0, -1, MODEL_OK, False, 0.0, -1, 0.0, -1, 0.0,
        cvar_level, tail, False, 0.0, 0, List[Float64](), List[Int](),
    )


def _no_min_max_result(status: Int, n_scenarios: Int) -> RobustMinMaxResult:
    """An input rejection: nothing solved, nothing verified, no direction claimed.

    `lp_status` is `MODEL_OK`, NOT `status`. Every caller of this helper rejects before any LP
    runs, so there is no LP status to report, and copying a robust code such as
    `ROBUST_ERR_SCENARIO_SHAPE` (150) into a field whose vocabulary is `optimization.linear`'s
    is one integer read through two vocabularies — rule 4e at field level rather than range
    level. `lp_status_name(150)` does not name it, and a caller that branches on `lp_status`
    would be branching on a number that means something else in the chain the field belongs to.
    The sibling `_no_scenario_result` already avoided exactly this for `first_failed_status`.
    """
    return RobustMinMaxResult(
        status, n_scenarios, 0, 0, False, 0.0, False, 0, MODEL_OK, 0, -1, False, 0, 0, 0, 0.0,
        MODEL_VIOLATION_ABSENT, -1, -1, List[Float64](), List[Float64](),
        List[Float64](), List[Int](),
    )


def _no_chance_result(
    status: Int, n_scenarios: Int, confidence: Float64, drawn: Bool,
    seed: UInt64, stream: UInt64,
) -> ChanceResult:
    """A rejection: `has_rates` False, every list empty, `worst_row` -1.

    `nonnegative` is False and `worst_negative` 0.0 because nothing was measured — the pair is
    only meaningful when `has_rates` is True, exactly as the rates themselves are.
    """
    return ChanceResult(
        status, n_scenarios, 0, confidence, drawn, seed, stream, False, False, 0.0, False,
        False, 0, -1, 0.0, 0.0, List[Float64](), List[Int](), List[Bool](), List[Float64](),
    )


# ── scenario generation ───────────────────────────────────────────────────────


def _draw_input_defect(base_rhs: List[Float64], dispersion: List[Float64], n_scenarios: Int) -> Int:
    """Validate a generator's arguments before a single cell is allocated.

    `n_rows` is DERIVED from `len(base_rhs)` rather than declared, so there is no caller
    integer to disagree with the payload — the class of bug where a 60-byte request
    materialises gigabytes needs a dimension tied to nothing, and this one is tied to the
    base vector.

    The DRAW is also charged against the work budget, at one unit per cell: `S * rows` counter
    RNG calls is CPU, and the allocation ceiling alone would let 2^24 of them through from a
    request naming two integers.
    """
    var rows = len(base_rhs)
    if len(dispersion) != rows:
        return MODEL_ERR_LENGTH_MISMATCH
    var count_defect = _scenario_count_defect(n_scenarios, rows)
    if count_defect != MODEL_OK:
        return count_defect
    var work_defect = _work_defect(0, rows, 0, _cell_units(n_scenarios, rows + 1))
    if work_defect != MODEL_OK:
        return work_defect
    for i in range(rows):
        if not _finite(base_rhs[i]):
            return MODEL_ERR_NON_FINITE_RHS
    for i in range(rows):
        if not _finite(dispersion[i]) or dispersion[i] < 0.0:
            return ROBUST_ERR_DISPERSION
    return MODEL_OK


def scenario_rhs_normal(
    base_rhs: List[Float64], sigma: List[Float64], n_scenarios: Int,
    seed: UInt64, stream_name: String,
) -> ScenarioSet:
    """`S` right-hand sides drawn as `Normal(base_rhs[i], sigma[i])`, reproducibly.

    Cell `(s, i)` is drawn at coordinates `(seed, scenario_id = s, dim0 = i, stream)` with
    `draw_index = 0`, and `rng_normal_scaled` consumes a fixed two draws there, so no two
    cells share a draw and the block is a pure function of its coordinates: the same seed and
    stream reproduce it exactly, on any machine, whatever else was drawn first.

    `sigma[i] == 0` is legal and produces row `i` constant at `base_rhs[i]` — the degenerate
    scenario set a robust answer must agree with the deterministic one on. A draw that
    overflows to a non-finite value is a rejection, not a cell: `MODEL_ERR_NON_FINITE_RHS`.
    """
    var stream = stream_id(stream_name)
    var defect = _draw_input_defect(base_rhs, sigma, n_scenarios)
    if defect != MODEL_OK:
        return _empty_scenario_set(defect, SCENARIO_KIND_NORMAL, seed, stream)

    var rows = len(base_rhs)
    var out = List[Float64]()
    for s in range(n_scenarios):
        for i in range(rows):
            var v = rng_normal_scaled(
                seed, UInt64(s), 0, UInt64(i), 0, stream, NORMAL_DRAW_INDEX,
                base_rhs[i], sigma[i],
            )
            if not _finite(v):
                return _empty_scenario_set(
                    MODEL_ERR_NON_FINITE_RHS, SCENARIO_KIND_NORMAL, seed, stream
                )
            out.append(v)
    return ScenarioSet(
        MODEL_OK, n_scenarios, rows, SCENARIO_KIND_NORMAL, seed, stream, rng_version(), out^
    )


def scenario_rhs_uniform(
    base_rhs: List[Float64], half_width: List[Float64], n_scenarios: Int,
    seed: UInt64, stream_name: String,
) -> ScenarioSet:
    """`S` right-hand sides drawn uniformly on `[base - half_width, base + half_width]`.

    The box uncertainty set, sampled. Cell `(s, i)` consumes exactly one draw at
    `(seed, scenario_id = s, dim0 = i, stream, draw_index = UNIFORM_DRAW_INDEX)`, past the two
    draws Box-Muller consumes in `scenario_rhs_normal`, so the same seed and stream give the
    two generators INDEPENDENT values for the same cell rather than the same uniform dressed
    differently. `kind` is reported alongside the seed because the distribution is part of the
    scenario set's identity.

    `rng_uniform` is half-open on [0, 1), so the upper endpoint is not attained while the
    lower one is. That asymmetry is one ulp of the range and is stated rather than papered
    over.
    """
    var stream = stream_id(stream_name)
    var defect = _draw_input_defect(base_rhs, half_width, n_scenarios)
    if defect != MODEL_OK:
        return _empty_scenario_set(defect, SCENARIO_KIND_UNIFORM, seed, stream)

    var rows = len(base_rhs)
    var out = List[Float64]()
    for s in range(n_scenarios):
        for i in range(rows):
            var u = rng_uniform(seed, UInt64(s), 0, UInt64(i), 0, stream, UNIFORM_DRAW_INDEX)
            var v = base_rhs[i] + (2.0 * u - 1.0) * half_width[i]
            if not _finite(v):
                return _empty_scenario_set(
                    MODEL_ERR_NON_FINITE_RHS, SCENARIO_KIND_UNIFORM, seed, stream
                )
            out.append(v)
    return ScenarioSet(
        MODEL_OK, n_scenarios, rows, SCENARIO_KIND_UNIFORM, seed, stream, rng_version(), out^
    )


# ── the wait-and-see distribution ─────────────────────────────────────────────


def _scenario_vector(
    block: List[Float64], base: List[Float64], scenario: Int, width: Int
) -> List[Float64]:
    """Scenario `scenario`'s slice of `block`, or a copy of `base` when the block is empty.

    Both lengths are already proven: `len(block) == S * width` and `len(base) == width`, so
    the slice is in range. This is the ONLY place a scenario is materialised, so the "empty
    block means it does not vary" convention has one implementation.
    """
    var out = List[Float64]()
    if len(block) == 0:
        for i in range(width):
            out.append(base[i])
        return out^
    var offset = scenario * width
    for i in range(width):
        out.append(block[offset + i])
    return out^


# PACKING IS LOAD-BEARING: `mojo_inventory` matches a signature inside a nine-line lookahead
# and drops the function from the contract AND from dispatch, silently, if the closing paren
# lands later. This closes on line 5 of 9.
def robust_scenario_solve(
    c: List[Float64], constant: Float64, a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool, n_scenarios: Int,
    rhs_scenarios: List[Float64], c_scenarios: List[Float64], cvar_level: Float64,
    max_iterations: Int, feasibility_tol: Float64, optimality_tol: Float64,
) -> RobustScenarioResult:
    """One `lp_solve` per scenario, then the worst case, the mean and the CVaR of the optima.

    `rhs_scenarios` is `S * rows` row-major and `c_scenarios` is `S * cols` row-major; either
    may be EMPTY, meaning that quantity does not vary across scenarios. Both empty with
    `n_scenarios = S` is `S` copies of one program — the degenerate case whose answer must
    equal the deterministic one, and the strongest cross-check this driver has.

    WHAT THIS IS NOT: the returned `worst_case` is `max_s min_x f(x, s)`, the worst
    PERFECT-FORESIGHT optimum, which bounds the robust value `min_x max_s f(x, s)` from below
    when minimising and from above when maximising. It is not attained by any single `x`
    unless one `x` is optimal in every scenario. The success status is `ROBUST_BOUND_ONLY`
    for exactly that reason; `robust_min_max_rhs` computes the here-and-now answer.

    Every scenario's optimum is VERIFIED against that scenario's own rows before it is
    counted, at each row's own budget, so a per-scenario objective is never believed on the
    strength of a status alone. If any scenario's LP fails the status is
    `ROBUST_SCENARIO_FAILED`; if all reached an optimum but at least one solution does not
    satisfy its own scenario it is `ROBUST_UNVERIFIED`; either way NO aggregate is returned —
    `scenario_status` reports every scenario's outcome and `first_failed_scenario` names the
    earliest. An average over the scenarios that happened to solve is a number about a
    scenario set the caller did not ask about.
    """
    var level_defect = _level_defect(cvar_level)
    if level_defect != MODEL_OK:
        return _no_scenario_result(level_defect, n_scenarios, cvar_level)
    # The base template first: every index used below — `rows`, `cols`, `senses[i]`,
    # `rhs[i]`, `a[i * cols + j]` — is a property this proves, and an unvalidated read past a
    # List end is an uncatchable process crash, not an exception.
    var base_defect = _lp_input_defect(
        c, constant, a, rows, cols, senses, rhs, max_iterations,
        feasibility_tol, optimality_tol,
    )
    if base_defect != MODEL_OK:
        return _no_scenario_result(base_defect, n_scenarios, cvar_level)
    var count_defect = _scenario_count_defect(n_scenarios, rows)
    if count_defect != MODEL_OK:
        return _no_scenario_result(count_defect, n_scenarios, cvar_level)
    var rhs_defect = _scenario_block_defect(rhs_scenarios, n_scenarios, rows)
    if rhs_defect != MODEL_OK:
        return _no_scenario_result(rhs_defect, n_scenarios, cvar_level)
    var c_defect = _scenario_block_defect(c_scenarios, n_scenarios, cols)
    if c_defect != MODEL_OK:
        return _no_scenario_result(c_defect, n_scenarios, cvar_level)
    # `S` full two-phase simplex solves plus `S` verification scans. The allocation ceilings say
    # the ARRAYS fit; this says the arithmetic does. Measured before it existed: the
    # allocation-legal `S = 2^23` on a 1x1 model is ~29 s of worker time from ~120 bytes.
    var work_defect = _work_defect(
        n_scenarios, rows, cols, _cell_units(n_scenarios, rows + 1)
    )
    if work_defect != MODEL_OK:
        return _no_scenario_result(work_defect, n_scenarios, cvar_level)
    # A non-finite scenario cell is an INPUT defect, not a solver failure: letting `lp_solve`
    # discover it per scenario would report a malformed payload as a property of the model.
    for i in range(len(rhs_scenarios)):
        if not _finite(rhs_scenarios[i]):
            return _no_scenario_result(MODEL_ERR_NON_FINITE_RHS, n_scenarios, cvar_level)
    for i in range(len(c_scenarios)):
        if not _finite(c_scenarios[i]):
            return _no_scenario_result(
                MODEL_ERR_NON_FINITE_COEFFICIENT, n_scenarios, cvar_level
            )

    var objectives = List[Float64]()
    var statuses = List[Int]()
    var n_failed = 0
    var n_unverified = 0
    var first_failed = -1
    var first_status = MODEL_OK
    for s in range(n_scenarios):
        var rhs_s = _scenario_vector(rhs_scenarios, rhs, s, rows)
        var c_s = _scenario_vector(c_scenarios, c, s, cols)
        var sol = lp_solve(
            c_s, constant, a, rows, cols, senses, rhs_s, maximize,
            max_iterations, feasibility_tol, optimality_tol,
        )
        var outcome = sol.status
        if sol.status == LP_OPTIMAL:
            if not sol.has_objective or len(sol.x) != cols:
                # An optimal status carrying no value, or a solution vector of the wrong
                # width, is a contradiction inside the solver's own report. It is not an
                # answer, so it is not counted as one — and the length check is also what
                # keeps the verification below from indexing a short vector.
                outcome = ROBUST_UNVERIFIED
            else:
                # VERIFIED against the caller's own scenario before the objective is believed.
                # A solver's optimality proof is about its tableau; this is about the rows the
                # caller wrote, and it is the check that catches a feasibility threshold which
                # accepted a point violating a row — the defect that made an infeasible LP
                # report OPTIMAL with a full solution vector attached.
                var ok = True
                var act = _activity(a, rows, cols, sol.x, ok)
                if not ok:
                    outcome = MODEL_ERR_NON_FINITE_VALUE
                elif _negativity(sol.x, feasibility_tol) > 0.0:
                    outcome = ROBUST_UNVERIFIED
                else:
                    var scan = _scan_violations(act, senses, rhs_s, rows, feasibility_tol)
                    if not scan.measured or scan.worst > 0.0:
                        outcome = ROBUST_UNVERIFIED
        statuses.append(outcome)
        if outcome == LP_OPTIMAL:
            objectives.append(sol.objective)
        else:
            n_failed += 1
            if outcome == ROBUST_UNVERIFIED:
                n_unverified += 1
            if first_failed < 0:
                first_failed = s
                first_status = outcome

    if n_failed > 0:
        # An unsolved scenario and an unverifiable one are different facts, so the aggregate
        # status names the more specific one when every scenario at least reached an optimum.
        var aggregate = ROBUST_SCENARIO_FAILED
        if n_unverified == n_failed:
            aggregate = ROBUST_UNVERIFIED
        return RobustScenarioResult(
            aggregate, n_scenarios, n_scenarios - n_failed, n_failed,
            first_failed, first_status, False, 0.0, -1, 0.0, -1, 0.0,
            cvar_level, 1.0 - cvar_level, False, 0.0, 0, List[Float64](), statuses^,
        )

    # Everything below is in MINIMISATION sense so one comparison serves both directions;
    # `minimization_value` is the frozen flip and is its own inverse, so the report comes
    # back in the caller's sense without a second sign convention written by hand.
    var costs = List[Float64]()
    var returns = List[Float64]()
    for s in range(n_scenarios):
        var cost = minimization_value(objectives[s], maximize)
        costs.append(cost)
        returns.append(-cost)
    var worst_index = 0
    var best_index = 0
    for s in range(n_scenarios):
        # Strict comparisons, so the LOWEST index wins a tie and the report does not depend
        # on the scan direction.
        if costs[s] > costs[worst_index]:
            worst_index = s
        if costs[s] < costs[best_index]:
            best_index = s
    # The frozen arithmetic mean, not a second sum written here.
    var mean_cost = mean(costs)
    if not _finite(mean_cost):
        return _no_scenario_result(MODEL_ERR_NON_FINITE_VALUE, n_scenarios, cvar_level)
    # `cvar_level` is a CONFIDENCE (`1 - tail`), which is the convention `risk.conditional_var`
    # takes: 1.0 averages the single worst cost, and a level near 0 approaches the mean.
    var cvar_cost = conditional_var(returns, cvar_level)
    var has_cvar = _finite(cvar_cost)
    # THE ORIENTATION IS CHECKED, not just documented. A tail average at a confidence level is
    # the mean of a NON-EMPTY worst tail of these same costs, so in minimisation sense it must
    # lie between the sample mean and the worst case. If it does not, the convention is not what
    # this module documents — and a tail risk pointing the wrong way UNDERSTATES risk under a
    # success status, which is the failure the comment above `ROBUST_ERR_CONFIDENCE` describes.
    # The number is then withheld (rule 4) instead of returned beside a claim it contradicts.
    if has_cvar:
        var worst_cost = costs[worst_index]
        var lo_slack = _cvar_bracket_slack(n_scenarios, cvar_cost, mean_cost)
        var hi_slack = _cvar_bracket_slack(n_scenarios, cvar_cost, worst_cost)
        if cvar_cost < mean_cost - lo_slack or cvar_cost > worst_cost + hi_slack:
            has_cvar = False
    # Padding is 0.0, never the non-finite value itself: a `nan` handed back beside a cleared
    # flag goes on to do arithmetic in a caller that trusted the flag.
    var cvar_out: Float64 = 0.0
    if has_cvar:
        cvar_out = minimization_value(cvar_cost, maximize)

    return RobustScenarioResult(
        ROBUST_BOUND_ONLY, n_scenarios, n_scenarios, 0, -1, MODEL_OK, True,
        objectives[worst_index], worst_index, objectives[best_index], best_index,
        minimization_value(mean_cost, maximize), cvar_level, 1.0 - cvar_level, has_cvar,
        cvar_out, _bound_direction(maximize),
        objectives^, statuses^,
    )


def robust_scenario_solve_default(
    c: List[Float64], a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool, n_scenarios: Int,
    rhs_scenarios: List[Float64], cvar_level: Float64,
) -> RobustScenarioResult:
    """`robust_scenario_solve` with no objective constant, no objective scenarios and
    `optimization.model`'s default policy."""
    return robust_scenario_solve(
        c, 0.0, a, rows, cols, senses, rhs, maximize, n_scenarios,
        rhs_scenarios, List[Float64](), cvar_level,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
    )


# ── the here-and-now robust solution ──────────────────────────────────────────


def robust_min_max_rhs(
    c: List[Float64], constant: Float64, a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool, n_scenarios: Int,
    rhs_scenarios: List[Float64], max_iterations: Int,
    feasibility_tol: Float64, optimality_tol: Float64,
) -> RobustMinMaxResult:
    """The optimum over the points feasible in EVERY scenario, then verified against them.

    Exact, not heuristic, and exact for a stated reason: only `b` varies, so `x` is feasible
    in every scenario iff it satisfies each row at that row's tightest right-hand side
    (`min_s b_i` for `<=`, `max_s b_i` for `>=`), and `A`, `senses`, `x >= 0` and the
    objective are all scenario-independent. The intersection is therefore ONE linear program
    and its optimum is the strictly-robust optimum over the given scenarios. The objective
    genuinely cannot vary here — this driver takes no objective scenarios, because
    `min_x max_s c_sᵀ x` does not reduce to a constraint-wise intersection.

    An equality row is only admissible when its right-hand side is BIT-IDENTICAL across
    scenarios: two different values leave an empty intersection, which is
    `ROBUST_EQ_CONFLICT` naming the row rather than an infeasible solve. Exactly, not within a
    tolerance — see the comment at that branch for why a tolerance there would invalidate the
    optimality claim.

    The answer is then CHECKED against the caller's own scenario data before it is returned.
    What the check COVERS: every row of every scenario, at that row's own budget, plus
    `x >= 0` — the whole feasible set, not the rows alone. What it does NOT cover: the
    OPTIMALITY of the intersection LP, which is taken from `lp_solve`'s own simplex proof and
    its duals and is not independently re-derived here; and anything about a scenario nobody
    drew. So `optimal_for_scenario_set` means "feasible in every given scenario, measured, and
    optimal among such points if the frozen simplex is correct" — stated because a caller who
    reads a certificate stops looking, and the one condition it omits is the one that then goes
    unchecked. A violation withholds the answer under `ROBUST_UNVERIFIED`.

    `LP_ITERATION_LIMIT` and `LP_NUMERICAL_BREAKDOWN` pass through unchanged because their
    meaning does not change here, while infeasible and unbounded become `ROBUST_*` codes
    because theirs does: they are statements about the intersection of the scenario feasible
    sets, not about any program the caller wrote.

    The direction in which this answer errs against the TRUE support flips with the sense —
    a LOWER bound when minimising, an UPPER bound when maximising — and `bound_direction`
    carries it; see `_bound_direction` for the derivation. An EMPTY `rhs_scenarios` means
    nothing varies, so there is ONE distinct right-hand side however large `n_scenarios` is:
    `scenario_data_given` is False, `n_distinct_scenarios` is 1, and the verification runs once
    rather than re-checking the base rows `n_scenarios` times and reporting the count as
    evidence.
    """
    var base_defect = _lp_input_defect(
        c, constant, a, rows, cols, senses, rhs, max_iterations,
        feasibility_tol, optimality_tol,
    )
    if base_defect != MODEL_OK:
        return _no_min_max_result(base_defect, n_scenarios)
    var count_defect = _scenario_count_defect(n_scenarios, rows)
    if count_defect != MODEL_OK:
        return _no_min_max_result(count_defect, n_scenarios)
    var block_defect = _scenario_block_defect(rhs_scenarios, n_scenarios, rows)
    if block_defect != MODEL_OK:
        return _no_min_max_result(block_defect, n_scenarios)

    var varying = len(rhs_scenarios) > 0
    # With no block there is ONE right-hand side, so one tightest-rhs scan and one verification
    # pass — not `n_scenarios` copies of the same check. This is both the honest denominator for
    # `feasible_rate` and the reason a 1000-scenario request with no scenario data costs one
    # pass: 4 million re-verifications of one row measured 291 ms of pure repetition.
    var distinct = n_scenarios if varying else 1
    # Two passes over the distinct cells — the tightest-rhs reduction and the verification scan —
    # charged as `2 * (rows + 1)` units each, plus the single intersection solve.
    var work_defect = _work_defect(1, rows, cols, _cell_units(distinct, 2 * rows + 2))
    if work_defect != MODEL_OK:
        return _no_min_max_result(work_defect, n_scenarios)
    for i in range(len(rhs_scenarios)):
        if not _finite(rhs_scenarios[i]):
            return _no_min_max_result(MODEL_ERR_NON_FINITE_RHS, n_scenarios)

    var effective = List[Float64]()
    var binding = List[Int]()
    for i in range(rows):
        var lo = rhs[i]
        var hi = rhs[i]
        var lo_at = -1
        var hi_at = -1
        if varying:
            lo = rhs_scenarios[i]
            hi = lo
            lo_at = 0
            hi_at = 0
            for s in range(1, n_scenarios):
                var v = rhs_scenarios[s * rows + i]
                if v < lo:
                    lo = v
                    lo_at = s
                if v > hi:
                    hi = v
                    hi_at = s
        if senses[i] == SENSE_LE:
            effective.append(lo)
            binding.append(lo_at)
        elif senses[i] == SENSE_GE:
            effective.append(hi)
            binding.append(hi_at)
        else:
            # An equality row pins the activity, so a range of right-hand sides is a range of
            # DIFFERENT hyperplanes whose intersection is empty unless they coincide EXACTLY.
            # Exactly, and not within a tolerance, because the optimality claim below is what
            # a tolerance here would break: solving a spread-out equality row at, say, the
            # midpoint of its range imposes a constraint TIGHTER than "within budget of every
            # scenario", so it can exclude a better point that satisfies all of them and the
            # answer would be reported optimal over a set it does not cover. `hi >= lo` always
            # holds, so `hi > lo` is exactly "not identical", and -0.0 vs 0.0 compares equal —
            # correctly, since they name the same hyperplane.
            if hi > lo:
                return RobustMinMaxResult(
                    ROBUST_EQ_CONFLICT, n_scenarios, rows, cols, False, 0.0, False, 0,
                    MODEL_OK, 0, i, varying, distinct, 0, 0, 0.0,
                    MODEL_VIOLATION_ABSENT, -1, -1,
                    List[Float64](), List[Float64](), List[Float64](), List[Int](),
                )
            effective.append(lo)
            # -1, not 0: every scenario supplies this row's right-hand side, so no single one
            # of them binds it.
            binding.append(-1)

    var sol = lp_solve(
        c, constant, a, rows, cols, senses, effective, maximize,
        max_iterations, feasibility_tol, optimality_tol,
    )
    if sol.status != LP_OPTIMAL or not sol.has_objective or len(sol.x) != cols:
        var mapped = sol.status
        if sol.status == LP_INFEASIBLE:
            mapped = ROBUST_INFEASIBLE
        elif sol.status == LP_UNBOUNDED:
            mapped = ROBUST_UNBOUNDED
        elif sol.status == LP_OPTIMAL:
            # An optimum carrying no value, or a solution vector of the wrong width, is a
            # contradiction inside the solver's own report. It must not leave here under a
            # success code, and the width check is also what keeps the verification below from
            # measuring an activity built from a short vector.
            mapped = ROBUST_UNVERIFIED
        return RobustMinMaxResult(
            mapped, n_scenarios, rows, cols, False, 0.0, False, 0, sol.status,
            sol.iterations, -1, varying, distinct, 0, 0, 0.0,
            MODEL_VIOLATION_ABSENT, -1, -1,
            List[Float64](), effective^, List[Float64](), binding^,
        )

    # Verification. The activity `A x` does not depend on the scenario — only `b` does — so it
    # is computed once and compared against every scenario's right-hand side, through the same
    # `_scan_violations` the per-scenario driver uses.
    var activity_ok = True
    var activity = _activity(a, rows, cols, sol.x, activity_ok)
    if not activity_ok:
        return RobustMinMaxResult(
            MODEL_ERR_NON_FINITE_VALUE, n_scenarios, rows, cols, False, 0.0, False, 0,
            sol.status, sol.iterations, -1, varying, distinct, 0, 0, 0.0,
            MODEL_VIOLATION_ABSENT, -1, -1,
            List[Float64](), effective^, List[Float64](), binding^,
        )

    var n_violating = 0
    var worst_violation: Float64 = 0.0
    var worst_row = -1
    var worst_scenario = -1
    var unmeasured = False
    # `x >= 0` is scenario-independent, so a negative component fails every scenario at once
    # and is reported that way: `worst_violation_row` -1 with a positive `worst_violation`
    # means the violated condition is the non-negativity, which is not a row, and
    # `worst_violation_scenario` is -1 because no single scenario is to blame —
    # `n_violating_scenarios == n_distinct_scenarios` says all of them are.
    var negative = _negativity(sol.x, feasibility_tol)
    if negative > 0.0:
        return RobustMinMaxResult(
            ROBUST_UNVERIFIED, n_scenarios, rows, cols, False, 0.0, False, 0, sol.status,
            sol.iterations, -1, varying, distinct, 0, distinct, 0.0, negative, -1, -1,
            List[Float64](), effective^, List[Float64](), binding^,
        )
    # `distinct`, not `n_scenarios`: with no block every pass would compare the SAME activity
    # against the SAME base right-hand side, and a measurement repeated is not more evidence.
    for s in range(distinct):
        var scenario_rhs = _scenario_vector(rhs_scenarios, rhs, s, rows)
        var scan = _scan_violations(activity, senses, scenario_rhs, rows, feasibility_tol)
        # -1 when no block was given: there is no scenario index to name, and 0 would name a
        # scenario the caller never supplied.
        var label = s if varying else -1
        if not scan.measured:
            # A row that could not be tested is not a row that passed.
            unmeasured = True
            n_violating += 1
            if worst_row < 0:
                worst_row = scan.row
                worst_scenario = label
        elif scan.worst > 0.0:
            n_violating += 1
            if scan.worst > worst_violation:
                worst_violation = scan.worst
                worst_row = scan.row
                worst_scenario = label
    if unmeasured:
        worst_violation = MODEL_VIOLATION_ABSENT

    var verified = distinct - n_violating
    var rate = Float64(verified) / Float64(distinct)
    if n_violating > 0:
        return RobustMinMaxResult(
            ROBUST_UNVERIFIED, n_scenarios, rows, cols, False, 0.0, False, 0, sol.status,
            sol.iterations, -1, varying, distinct, verified, n_violating, rate,
            worst_violation, worst_row, worst_scenario,
            List[Float64](), effective^, List[Float64](), binding^,
        )
    # SELF-CONSISTENCY before a success code. Every claim this result is about to make has to
    # agree with every other one: two mutually exclusive fields in one returned value leave a
    # caller able to use neither, and `optimal_for_scenario_set` is the strongest claim in the
    # module. A `nan` objective under `LP_OPTIMAL` is caught here too — it would otherwise be a
    # number returned where none exists.
    var consistent = (
        verified == distinct
        and worst_violation == 0.0
        and not unmeasured
        and sol.status == LP_OPTIMAL
        and sol.has_objective
        and len(sol.x) == cols
        and _finite(sol.objective)
        and rate == 1.0
    )
    if not consistent:
        return RobustMinMaxResult(
            ROBUST_UNVERIFIED, n_scenarios, rows, cols, False, 0.0, False, 0, sol.status,
            sol.iterations, -1, varying, distinct, verified, n_violating, rate,
            worst_violation, worst_row, worst_scenario,
            List[Float64](), effective^, List[Float64](), binding^,
        )
    return RobustMinMaxResult(
        MODEL_OK, n_scenarios, rows, cols, True, sol.objective, True,
        _bound_direction(maximize), sol.status,
        sol.iterations, -1, varying, distinct, verified, 0, rate, 0.0, -1, -1,
        sol.x.copy(), effective^, sol.duals.copy(), binding^,
    )


def robust_min_max_rhs_default(
    c: List[Float64], a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64], maximize: Bool, n_scenarios: Int,
    rhs_scenarios: List[Float64],
) -> RobustMinMaxResult:
    """`robust_min_max_rhs` with no objective constant and the default policy."""
    return robust_min_max_rhs(
        c, 0.0, a, rows, cols, senses, rhs, maximize, n_scenarios, rhs_scenarios,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
    )


# ── chance constraints ────────────────────────────────────────────────────────


def _chance_rates_at(
    x: List[Float64], a: List[Float64], rows: Int, cols: Int, senses: List[Int],
    rhs_scenarios: List[Float64], n_scenarios: Int, confidence: Float64,
    feasibility_tol: Float64, drawn: Bool, seed: UInt64, stream: UInt64,
) -> ChanceResult:
    """The measured rates. Shared by the explicit and the drawn entry points — one code path,
    so a rate cannot mean two things depending on where the scenarios came from."""
    if rows < 0 or cols < 0 or not dims_fit(rows, cols, len(a)):
        return _no_chance_result(MODEL_ERR_DENSE_SHAPE, n_scenarios, confidence, drawn, seed, stream)
    if len(x) != cols:
        return _no_chance_result(
            MODEL_ERR_POINT_LENGTH, n_scenarios, confidence, drawn, seed, stream
        )
    if len(senses) != rows:
        return _no_chance_result(
            MODEL_ERR_LENGTH_MISMATCH, n_scenarios, confidence, drawn, seed, stream
        )
    var level_defect = _level_defect(confidence)
    if level_defect != MODEL_OK:
        return _no_chance_result(level_defect, n_scenarios, confidence, drawn, seed, stream)
    # One definition of an admissible tolerance for the whole package: the fields this entry
    # point does not take are filled with known-valid defaults, exactly as
    # `linear._lp_input_defect` does for the integrality tolerance.
    var policy_defect = _policy_parts_defect(
        DEFAULT_MAX_ITERATIONS, feasibility_tol, DEFAULT_OPTIMALITY_TOL,
        DEFAULT_INTEGRALITY_TOL,
    )
    if policy_defect != MODEL_OK:
        return _no_chance_result(policy_defect, n_scenarios, confidence, drawn, seed, stream)
    var count_defect = _scenario_count_defect(n_scenarios, rows)
    if count_defect != MODEL_OK:
        return _no_chance_result(count_defect, n_scenarios, confidence, drawn, seed, stream)
    # Charged BEFORE the block-length check on purpose: a sweep this module would refuse to
    # perform is refused whatever the block's length is, and a caller then does not have to
    # materialise `S * rows` cells to be told so. A small-but-wrong block still passes here and
    # gets the shape diagnosis it deserves.
    var work_defect = _work_defect(0, rows, cols, _cell_units(n_scenarios, rows + 1))
    if work_defect != MODEL_OK:
        return _no_chance_result(work_defect, n_scenarios, confidence, drawn, seed, stream)
    # Unlike the solve drivers there is no base right-hand side to fall back on, so an empty
    # block with rows to judge is a rejection rather than "does not vary" — and a NON-empty
    # block for a zero-row model is a rejection too, which is why this is `dims_fit` on every
    # path rather than a `rows > 0` special case: `dims_fit(S, 0, length)` is true only for
    # `length == 0`.
    if not dims_fit(n_scenarios, rows, len(rhs_scenarios)):
        return _no_chance_result(
            ROBUST_ERR_SCENARIO_SHAPE, n_scenarios, confidence, drawn, seed, stream
        )
    for i in range(rows):
        if senses[i] != SENSE_LE and senses[i] != SENSE_EQ and senses[i] != SENSE_GE:
            return _no_chance_result(MODEL_ERR_SENSE, n_scenarios, confidence, drawn, seed, stream)
    for j in range(cols):
        if not _finite(x[j]):
            return _no_chance_result(
                MODEL_ERR_NON_FINITE_POINT, n_scenarios, confidence, drawn, seed, stream
            )
    for i in range(len(a)):
        if not _finite(a[i]):
            return _no_chance_result(
                MODEL_ERR_NON_FINITE_COEFFICIENT, n_scenarios, confidence, drawn, seed, stream
            )
    for i in range(len(rhs_scenarios)):
        if not _finite(rhs_scenarios[i]):
            return _no_chance_result(
                MODEL_ERR_NON_FINITE_RHS, n_scenarios, confidence, drawn, seed, stream
            )

    var activity_ok = True
    var activity = _activity(a, rows, cols, x, activity_ok)
    if not activity_ok:
        return _no_chance_result(
            MODEL_ERR_NON_FINITE_VALUE, n_scenarios, confidence, drawn, seed, stream
        )

    # `x >= 0` is half of this package's feasible set — `lp_solve` optimises over it and the two
    # solve drivers verify it through this same `_negativity`, so measuring only the rows here
    # enforced ONE declared invariant at TWO strengths inside one package (rule 3, and the
    # rule-4d omission `_negativity`'s own docstring names). It does not vary with the scenario,
    # so a negative component fails EVERY scenario at once: the per-row rates stand, and the
    # JOINT rate — the fraction of scenarios in which the point is FEASIBLE — is 0.
    var negative = _negativity(x, feasibility_tol)
    var nonnegative = negative <= 0.0

    var counts = List[Int]()
    for _ in range(rows):
        counts.append(0)
    var joint_count = 0
    for s in range(n_scenarios):
        var all_ok = nonnegative
        for i in range(rows):
            var b = rhs_scenarios[s * rows + i]
            var budget = _row_budget(feasibility_tol, b, activity[i])
            # 0.0 is the only "satisfied" value: MODEL_VIOLATION_ABSENT (-1.0) means the test
            # could not be made, which is not the same as passing it.
            if sense_violation(activity[i], senses[i], b, budget) == 0.0:
                counts[i] += 1
            else:
                all_ok = False
        if all_ok:
            joint_count += 1

    var rates = List[Float64]()
    var met = List[Bool]()
    var stderr = List[Float64]()
    var s_f = Float64(n_scenarios)
    var n_unmet = 0
    var worst_row = -1
    var worst_rate: Float64 = 0.0
    for i in range(rows):
        var p = Float64(counts[i]) / s_f
        rates.append(p)
        stderr.append(sqrt(p * (1.0 - p) / s_f))
        var ok = _rate_meets(counts[i], n_scenarios, confidence)
        met.append(ok)
        if not ok:
            n_unmet += 1
        # Strict, so the LOWEST-indexed row wins a tie.
        if worst_row < 0 or p < worst_rate:
            worst_row = i
            worst_rate = p
    var joint_rate = Float64(joint_count) / s_f
    var joint_met = _rate_meets(joint_count, n_scenarios, confidence)
    # Zero rows: every scenario satisfies all of them vacuously, so the joint rate is 1.0 and
    # the level is met. Reported, not special-cased into an error, because an unconstrained
    # point genuinely does satisfy every constraint it has — but only if the point is IN the
    # feasible set's other half, so this cannot skip `x >= 0`.
    if rows == 0 and nonnegative:
        joint_rate = 1.0
        joint_met = True
    if not nonnegative:
        # Exact 0.0 and False, not a computed rate: `x >= 0` fails in every scenario, and with
        # zero rows the loop above never ran to count it.
        joint_rate = 0.0
        joint_met = False
    var all_met = n_unmet == 0
    var status = MODEL_OK
    if not all_met or not joint_met:
        status = ROBUST_CHANCE_NOT_MET
    return ChanceResult(
        status, n_scenarios, rows, confidence, drawn, seed, stream, True, nonnegative,
        negative, all_met, joint_met, n_unmet, worst_row, worst_rate, joint_rate,
        rates^, counts^, met^, stderr^,
    )


def robust_chance_rates(
    x: List[Float64], a: List[Float64], rows: Int, cols: Int, senses: List[Int],
    rhs_scenarios: List[Float64], n_scenarios: Int, confidence: Float64,
    feasibility_tol: Float64,
) -> ChanceResult:
    """Measured satisfaction rate of every row at `x`, over a caller-supplied scenario block.

    `rhs_scenarios` is `S * rows` row-major and is REQUIRED — there is no base right-hand
    side here to fall back on, so an empty block with rows to judge is
    `ROBUST_ERR_SCENARIO_SHAPE` rather than a silent "nothing varies".

    The rate is what is reported. `confidence` is what it was judged against.
    `MODEL_OK` means every per-row rate and the joint rate met that level;
    `ROBUST_CHANCE_NOT_MET` means at least one did not, and `all_rows_met` / `joint_met` say
    which. A rate is an ESTIMATE over `n_scenarios` draws, with the sampling error
    `rate_stderr` reports — not a probability guarantee. See the module docstring.

    WHAT THE MEASUREMENT COVERS, stated because the sibling drivers state it and a caller who
    reads a coverage claim stops looking for the omission: every row of every scenario at that
    row's own budget, AND `x >= 0`, which is the other half of the feasible set `lp_solve`
    optimises over. The non-negativity is scenario-independent, so it enters `joint_rate` /
    `joint_met` / `nonnegative` / `worst_negative` and never the per-row rates. What it does NOT
    cover: anything about a scenario nobody drew, and any integrality or bound the caller
    enforces elsewhere — this driver knows only the rows it was handed.
    """
    return _chance_rates_at(
        x, a, rows, cols, senses, rhs_scenarios, n_scenarios, confidence,
        feasibility_tol, False, 0, 0,
    )


def robust_chance_normal(
    x: List[Float64], a: List[Float64], rows: Int, cols: Int, senses: List[Int],
    base_rhs: List[Float64], sigma: List[Float64], n_scenarios: Int, seed: UInt64,
    stream_name: String, confidence: Float64, feasibility_tol: Float64,
) -> ChanceResult:
    """`robust_chance_rates` over scenarios this call DRAWS, so the seed determines the rate.

    Draws `scenario_rhs_normal(base_rhs, sigma, n_scenarios, seed, stream_name)` and measures
    against it, then reports the seed and stream on the result: the same seed and stream give
    a bit-identical rate, a different seed gives a different scenario set, and the number is
    reproducible from the coordinates alone. The generator's rejections propagate unchanged —
    a scenario set that could not be built is not a rate of 0.

    This call does the DRAW and the MEASUREMENT, so it charges both against the work budget
    before either runs: the generator and `_chance_rates_at` each guard their own half, and
    checking the sum here is what keeps the pair from spending twice the ceiling between them.
    """
    var work_defect = _work_defect(0, rows, cols, _cell_units(n_scenarios, 2 * len(base_rhs) + 2))
    if work_defect != MODEL_OK:
        return _no_chance_result(
            work_defect, n_scenarios, confidence, True, seed, stream_id(stream_name)
        )
    var drawn = scenario_rhs_normal(base_rhs, sigma, n_scenarios, seed, stream_name)
    if drawn.status != MODEL_OK:
        return _no_chance_result(
            drawn.status, n_scenarios, confidence, True, seed, drawn.stream
        )
    if drawn.n_rows != rows:
        return _no_chance_result(
            MODEL_ERR_LENGTH_MISMATCH, n_scenarios, confidence, True, seed, drawn.stream
        )
    return _chance_rates_at(
        x, a, rows, cols, senses, drawn.rhs, n_scenarios, confidence,
        feasibility_tol, True, seed, drawn.stream,
    )
