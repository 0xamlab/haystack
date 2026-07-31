"""optimization.multiobjective — fronts that are really fronts, and a heuristic that says so.

Why this file exists
--------------------
`multi_objective.mojo` (frozen, top level) has the two relations and nothing that composes
them: `is_dominated(a, b, maximize)` decides one pair, `pareto_front(objectives, maximize)`
returns the first front over a NESTED `List[List[Float64]]`, and `ideal_point` / `nadir_point`
/ `normalize_objectives` / `topsis_rank` score alternatives. That is a first front and a
scalarisation. It is not a front DECOMPOSITION (rank 1, rank 2, ...), there is no crowding
distance, no hypervolume, no lexicographic solve, and no search that produces candidate
points in the first place — and none of it can cross the wire, because a nested list is not
marshalable.

Both frozen relations are reused here rather than rewritten. `pareto_front` is the
independent oracle inside `pareto_certify`, and `is_dominated` is the authority on strict
dominance: `mo_dominance` calls it and cross-checks it against the flat-indexed shim the
inner loops use, returning `MO_ERR_VERIFICATION_FAILED` if the two ever disagree (see
"One dominance relation" below).

Dominance convention — MINIMISE EVERY OBJECTIVE
----------------------------------------------
Fixed for the whole module, deliberately narrower than the frozen `maximize: List[Bool]`
mask. A caller maximising objective `j` negates column `j` before calling.

The mask was rejected because three answers here are not invariant under it. A hypervolume
is measured from a reference point that must be WORSE than every solution, and "worse" flips
with the mask; crowding distance normalises by an objective's range, and the boundary points
it protects are the range's ends; a lexicographic stage locks `c_j·x <= opt_j + slack`, whose
sense flips too. One convention applied everywhere is checkable. A mask threaded through
four drivers that each have to agree about it is how a sign error survives a test suite.

With every objective minimised, for finite `p`, `q` in R^k:

  * `q` WEAKLY dominates `p`   iff  `q_j <= p_j` for every `j`;
  * `q` STRICTLY dominates `p` iff  `q_j <= p_j` for every `j` AND `q_j < p_j` for some `j`.

Strict dominance is what every front, rank and hypervolume here uses, and it is a strict
partial order: irreflexive, asymmetric, transitive. Two consequences are load-bearing and
both are tested:

  * two IDENTICAL points do not dominate each other, so both are rank 0 and both are
    returned. They may be different decisions with the same score, and discarding one would
    silently drop a solution;
  * a point equal in every objective but one, where the other point is better, IS dominated.
    That single strictly-better coordinate is the whole difference between the two relations,
    and it is exactly where an off-by-one in a comparison chain hides.

So for finite inputs exactly one of four cases holds for any pair: equal, `a` strictly
dominates `b`, `b` strictly dominates `a`, or incomparable. `mo_dominance` returns all four
flags and the suite asserts the exhaustiveness over all 27 sign patterns in three
objectives.

Non-finite values are REJECTED, not compared. Every comparison against a `nan` is False, so
a `nan` coordinate makes a point neither dominated nor dominating — it would silently become
rank 0 and enter every front, and the frozen `is_dominated` would agree with the shim about
it, so the cross-check could not catch it either. `mo_matrix_defect` is the one door: a
non-finite objective value is `MODEL_ERR_NON_FINITE_VALUE` before any comparison happens.

A heuristic is not an optimum
-----------------------------
`nsga2_linear` is a genetic algorithm. It NEVER returns `MODEL_OK` and carries no
`proven_optimal` flag, because a local search cannot establish one; its success status is
`MO_UNPROVEN`, and `verified` says only what was actually checked — that every returned
point satisfies the CALLER's own rows and box, and that the returned set is pairwise
non-dominated.

What it does prove is stated separately and comes from somewhere else: `ideal[j]` is the
exact global minimum of objective `j` over the feasible region, obtained from an
`optimization.linear.lp_solve` call per objective, so `ideal_gap[j]` is a real per-objective
optimality gap and not a self-assessment. That is the bound this driver actually has. When
an objective's LP is unbounded the Pareto front is unbounded too, and no finite set of points
is that front: the status is `LP_UNBOUNDED` and no front comes back at all.

Those LP optima are also the seeds, which is why "no feasible point was found" is never an
outcome to fake: a zero-objective `lp_solve` decides feasibility exactly — the same device
`explain.infeasibility_core` uses, and for the same reason — so an empty feasible region is
the proven `LP_INFEASIBLE`, and when the region is non-empty at least one feasible individual
exists in generation 0 by construction.

Determinism is the point, not a nicety
--------------------------------------
A heuristic whose answer moves between runs cannot support a decision anybody has to
explain, which is the reason this package exists at all. Nothing here calls
`random_float64` or `seed(`. Every draw is `determinism.counter_rng` / `sampling_keyed`,
addressed by coordinates, so a draw is a pure function of its address and is identical
however much or little the search did beforehand.

The coordinate layout is FROZEN for this module (changing it changes every answer ever
returned):

    master_seed    = the caller's `seed`
    scenario_id    = generation index (0 for the initial population)
    replication_id = individual index, or the Monte-Carlo sample index
    dim0, dim1     = 0, reserved
    stream_id      = stream_id("multiobjective.<purpose>"), see determinism/streams.mojo
    draw_index     = variable index (mutation: 2j and 2j+1), or objective index

Consumption is FIXED per individual — two draws per variable for mutation whether or not it
fires, one per variable for crossover — so no draw's address depends on what an earlier
individual did. Every order that affects an answer is stated: per-objective sorts are
stable, ascending, and break ties by ascending ORIGINAL point index; the selection order is
(front rank ascending, crowding descending with boundary points first, original index
ascending); tournaments walk two keyed permutations per generation.

Boundary crowding distance is a FLAG, never an infinity
-------------------------------------------------------
Textbook NSGA-II gives the extreme point of each objective an infinite crowding distance so
that it always survives truncation. An `inf` in a returned `Float64` goes on to do
arithmetic in the caller — `inf - inf` is `nan` — and does not survive the JSON frame these
drivers cross, so `is_boundary[i]` carries the meaning and `distance[i]` stays finite,
exactly as `linear.lp_rhs_ranges` does with `has_upper`. A boundary point outranks every
non-boundary point regardless of the two numbers.

Hypervolume is meaningless without its reference point
------------------------------------------------------
So the reference point is an explicit parameter, it is echoed back in the result, and it is
validated: any point with a coordinate STRICTLY worse than the reference makes the box edge
negative, and that is `MO_ERR_REFERENCE_POINT` with no numbers. A coordinate exactly EQUAL
to the reference is admitted — its box has zero volume, which is a real answer, not a
broken one — and counted in `degenerate_points` so the zero is interpretable.

Exactness is a flag, not an assumption. The sweep is exact for one and two objectives. For
three or more the status is `MO_HV_INEXACT`, `has_value` is False, and what comes back is a
deterministic Monte-Carlo `estimate` with its `std_error` and sample count, PLUS two bounds
that are exact for any number of objectives: `bound_lower` = the largest single box (the
union contains each box) and `bound_upper` = min(spanning box, sum of the boxes) (the union
is inside the spanning box, and subadditivity). An exact value is checked against those
bounds inside the driver and a violation is `MO_ERR_VERIFICATION_FAILED`, which is a real
self-check because the three numbers come from different arithmetic. The two bounds are also
checked against EACH OTHER: they are both proven, so if they ever crossed, neither could be
used and no numbers come back.

The ESTIMATE is subject to those same bounds. A number that contradicts a proof the same call
carries is known-wrong the moment it is produced — and ordinary Poisson noise at a few expected
hits puts a Monte-Carlo estimate outside a proven interval in both directions — so the estimate
is CLAMPED into it (the clamp can only move it toward the truth, which is inside), its
`std_error` is widened by the distance moved so the raw draw still lies inside `estimate ±
std_error` unless the proven interval is narrower than that distance — an error bar is not
stretched to cover a number the bounds have refuted — and the status becomes
`MO_HV_ESTIMATE_CLAMPED` instead of staying silent. Zero hits
out of `samples` is NO measurement rather than a measurement of zero: the binomial variance
estimate collapses to exactly 0 there, so `std_error` is floored at one draw's own weight,
`spanning box / samples`, and `0.0 ± 0.0` — the strongest possible claim from the weakest
possible data — is unreachable. It is capped by `bound_upper - bound_lower`, the widest error
the two proofs leave room for, so a zero `std_error` says the bounds PIN the volume and never
that a sample was unanimous.

One dominance relation
----------------------
`_strictly_dominates` indexes the flat matrix in place. It exists because the frozen
`is_dominated` takes two `List[Float64]` plus a mask, and building three lists per pair for
the O(n^2) inner loops would allocate millions of times. It is a performance shim over the
frozen relation, not a second definition, and the arrangement is only defensible because the
agreement is CHECKED rather than assumed: `mo_dominance` evaluates both and returns
`MO_ERR_VERIFICATION_FAILED` on any disagreement, and the suite asserts agreement over every
sign pattern in one, two and three objectives. If the frozen relation ever changes, that
check fails loudly instead of the two drifting apart.

Ceilings, and why each is a bound on the REQUEST
------------------------------------------------
`sparse_numerics.csr.MAX_CSR_DIM` is the one shared ceiling and is imported, never
redefined or lowered. `dims_fit` is the shape guard: `n_points * n_obj == len(f)` is a
wrapping multiply and therefore not a guard at all (`3 * 6148914691236517206 == 2`).

Shape validity and resource bounding are separate checks, and the second one is quadratic
here. Every front decomposition is O(n^2) pair comparisons — count, peel, and two
verification passes — so the resource is PAIRS, not points: `MO_MAX_POINTS = 2048` is the
largest power of two with `n^2 * MO_SORT_PAIR_PASSES <= MAX_CSR_DIM`, and the suite asserts
that relation with divisions so a change to the shared ceiling fails a test instead of
silently unbounding this one. The objective count multiplies that work, so the product
`n^2 * n_obj` is checked against `MO_MAX_WORK` up front, with divisions, and rejected before
any allocation rather than discovered halfway through.

`nsga2_linear`'s `pop_size` and `generations` are tied to nothing in the payload — the whole
`n_vars` failure `linear.lp_from_arenas` had — so both have ceilings, `n_vars` is derived
from `len(c)` via `dims_fit` and never trusted, and the live population is
`2 * pop_size * (n_vars + n_obj)` slots, checked by division against the shared ceiling
divided by the number of per-individual arrays. `hypervolume`'s `samples` is the same kind
of untied integer and gets the same treatment.

BOUNDING MEMORY IS NOT BOUNDING WORK, and the paragraph above bounds memory and pairs. Every
loop bound that multiplies into a cost is charged against `MO_MAX_WORK` separately, by
divisions:

  * front decomposition, per call:    `n_points^2 * n_obj * MO_SORT_PAIR_PASSES`
  * front decomposition, per run:     `generations * (2 * pop_size)^2 * n_obj`
  * GA evaluation, per run:           `pop_size * (generations + 1) * (2 * rows + n_obj) * n_vars`
  * seed LPs, per run:                `(n_obj + 1) * (rows + 2 * n_vars) * n_vars`
  * hypervolume sampling, per call:   `samples * n_nondominated * n_obj`

The third is the one this module shipped without: `pop_size = 64, generations = 4096` over a
1000-variable, 1000-row model — an 8 MB payload — was accepted by the second budget, which
never sees a row, and ran for about 45 minutes in one call. `generations + 1` is charged
because the seeded round runs even at `generations = 0`.
"""
from std.math import abs as fabs, sqrt

from linalg import vec_dot
from multi_objective import is_dominated, ideal_point, nadir_point, pareto_front

from determinism.counter_rng import rng_uniform
from determinism.sampling_keyed import permutation_keyed
from determinism.streams import stream_id
from optimization.linear import (
    LP_DBL_EPSILON,
    LP_FEAS_ULP_BUDGET,
    LP_INFEASIBLE,
    LP_MAX_TABLEAU_CELLS,
    LP_OPTIMAL,
    LP_UNBOUNDED,
    lp_solve,
)
from optimization.integer import MILP_BOX_BELOW_ZERO, milp_status_name
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
    MODEL_ERR_NON_FINITE_RHS,
    MODEL_ERR_NON_FINITE_VALUE,
    MODEL_ERR_OVERFLOW,
    MODEL_ERR_SENSE,
    MODEL_OK,
    MODEL_VIOLATION_ABSENT,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    _policy_parts_defect,
    model_finite as _finite,
    sense_violation,
)
from sparse_numerics.csr import MAX_CSR_DIM, dims_fit

# ── status codes ──────────────────────────────────────────────────────────────
# ONE numbering is shared across the modules whose statuses reach the same caller, so a code
# has one meaning package-wide. The ranges already handed out:
#
#   0-30     `optimization.model` — arena, bound-column and policy defects
#   40-42    `optimization.linear` — the linear extractor's non-linearity codes
#   60-63    `optimization.linear` — solver outcomes (`LP_INFEASIBLE` is 60)
#   80-86    `optimization.explain` — certificate and core-verification outcomes
#   100-105  `optimization.integer` — branch-and-bound outcomes
#   140-150  this module
#
# (`optimization.flow` 0-21 and `optimization.assignment` 0-13 are self-contained
# vocabularies with their own tables; neither ever mixes with this chain, because a flow
# network is not a point set.)
#
# 106-139 are deliberately left free: 80-84 were once claimed TWICE inside this package, so
# `milp_status_name(81)` and `explain_status_name(81)` named different defects for one
# integer out of one package. Anything added here goes at 151+.
#
# An outcome that already has a code in the chain reuses it rather than inventing a second
# name for the same fact: an empty feasible region is `LP_INFEASIBLE`, an unbounded objective
# is `LP_UNBOUNDED`, a box below zero is `MILP_BOX_BELOW_ZERO`, and every input defect is one
# of `model.mojo`'s.

# A reference point some solution is strictly worse than in some objective. The box edge
# `ref_j - f_ij` would be negative and the "volume" a signed quantity, so no number is
# returned at all.
comptime MO_ERR_REFERENCE_POINT: Int = 140

# The answer failed its own check against the caller's data: a front holding a point another
# member dominates, a returned solution violating a row it was solved under, an exact
# hypervolume outside its own exact bounds, or a front decomposition whose ranks are not
# tight. No numbers are attached — a result that fails the identity it is defined by is not
# a result. `witness_*` fields name the pair that broke it where one exists.
comptime MO_ERR_VERIFICATION_FAILED: Int = 141

# Three or more objectives: no exact hypervolume. `bound_lower` and `bound_upper` are exact,
# `estimate` and `std_error` are a deterministic Monte-Carlo measurement, `has_value` is
# False. This is not an error — it is the honest shape of the answer, which is why it is not
# spelled ERR.
comptime MO_HV_INEXACT: Int = 142

# A search parameter is outside its admissible range: a population too small to hold the
# seeds, a probability outside [0, 1], a negative tolerance, a sample count above the
# ceiling, a front size above the population.
comptime MO_ERR_PARAMETER: Int = 143

# The search finished and its answer was verified against the caller's rows, and it is still
# only a heuristic answer. NSGA-II's success status. Never `MODEL_OK`: a local search has no
# certificate, and `ideal` / `ideal_gap` carry the only bound that was actually proven.
comptime MO_UNPROVEN: Int = 144

# The request's work exceeds `MO_MAX_WORK` — pair comparisons, Monte-Carlo samples, the GA's
# `pop_size * (generations + 1)` constraint re-evaluations, or its `n_obj + 1` seed LPs.
# Rejected BEFORE any allocation, from divisions on the declared dimensions, rather than
# discovered halfway through a run whose partial answer would mean nothing. Memory ceilings are
# a separate set of checks and a separate code: an allocation that fits can still drive an
# unbounded number of operations, which is how a valid 8 MB request once bought 45 minutes.
comptime MO_ERR_WORK_LIMIT: Int = 145

# An inner LP came back neither optimal nor infeasible — an iteration limit or a numerical
# breakdown inside the simplex. `stage_status` carries the simplex's own code and
# `failed_stage` says which objective's solve it was. Nothing is returned: a lexicographic
# chain with an unsolved link is not a lexicographic optimum, and a seeded search with no
# proven feasible point is not a search.
comptime MO_ERR_LP_STAGE_FAILED: Int = 146

# There is no front, no crowding distance and no hypervolume of nothing. `numeric/contract`'s
# rule: a count of nothing is 0, a spread of nothing does not exist.
comptime MO_ERR_EMPTY_SET: Int = 147

# `n_obj` is below one or above `MO_MAX_OBJECTIVES`. Separate from a dimension defect because
# the objective count is what multiplies every pass in this module, and a caller that sent
# 10 objectives to a 2-objective sweep needs to know which of its two numbers was refused.
comptime MO_ERR_OBJECTIVE_COUNT: Int = 148

# A locked lexicographic row made a program infeasible that the PREVIOUS stage's own optimum
# satisfies. That cannot happen mathematically — the previous optimum is feasible for the
# lock by construction — so it says the slack and the row scaling are inconsistent, exactly
# as `MILP_SNAP_INFEASIBLE` does for a snapped integer point. Reported instead of continuing,
# because continuing would optimise a later objective over a region the earlier stage never
# described.
comptime MO_ERR_LEX_LOCK_INFEASIBLE: Int = 149

# The Monte-Carlo hypervolume estimate fell OUTSIDE the exact `bound_lower` / `bound_upper`
# that the SAME call computed, so it was clamped into them and its `std_error` widened to cover
# the distance it moved. Everything `MO_HV_INEXACT` says still holds — no exact value, exact
# bounds, a deterministic estimate — and this code adds the one fact a caller cannot read off
# the numbers: proof and sample disagreed, and the proof won. It is not a defect in the
# request; it says `samples` is too small to resolve this front, and it is a status rather than
# a silent clamp because a clamp nobody is told about reads as agreement.
comptime MO_HV_ESTIMATE_CLAMPED: Int = 150

# ── ceilings and tolerances ───────────────────────────────────────────────────

# Passes over the O(n^2) pair space that one front decomposition can make: the domination
# count, the front peel, the pairwise verification of each front, and the rank-tightness
# verification, plus headroom for `pareto_certify`'s frozen-oracle pass and its two
# completeness sweeps. MEASURED against the code below; raise it if a pass is added, which is
# cheaper than discovering the quadratic budget was blown by a loop nobody counted.
comptime MO_SORT_PAIR_PASSES: Int = 8

# The point ceiling. The resource is PAIRS, not points: every decomposition compares every
# ordered pair a bounded number of times, so `n^2 * MO_SORT_PAIR_PASSES` is what has to fit
# the one shared ceiling, and 2048 is the largest power of two that does —
# 2048^2 * 8 = 33_554_432 <= 2^26 = MAX_CSR_DIM, where 4096 would need 2^27.
#
# Per-point MEMORY is not what binds: ten arrays of 2048 slots is 160 KB, four orders of
# magnitude inside `MAX_CSR_DIM // MO_POINT_ARRAYS`. Stating the binding resource is the
# point of rule 1c — the ceiling has to bound the request, and here the request's cost is
# quadratic in a number the payload only bounds linearly.
#
# MAX_CSR_DIM is imported, never redefined and never lowered: other packages share it, and
# the suite asserts this relation with divisions (`n <= (MAX_CSR_DIM // passes) // n`), so
# raising the shared ceiling moves this with it and lowering it fails a test.
comptime MO_MAX_POINTS: Int = 1 << 11

# The objective ceiling. `n_obj` is already tied to the payload — `dims_fit(n_points, n_obj,
# len(f))` means `n_obj <= len(f)` for any non-empty set — so this bounds the number of
# per-objective PASSES (a stable sort and a sweep each), not the allocation. 64 objectives is
# far past where a Pareto front means anything and still nowhere near the work ceiling.
comptime MO_MAX_OBJECTIVES: Int = 64

# The absolute work ceiling, in elementary operations — a pair comparison, a sample, or one
# term of one dot product, which are within a small constant of each other. Checked up front
# with divisions on the declared dimensions, never with a multiply that wraps. 2^30 is already
# seconds of work (MEASURED at roughly 2e8 of these per second under the JIT), so anything past
# it is a request to be refused, not throttled. Every loop bound that multiplies into a cost is
# charged against it — see the module docstring's list, which is the whole set.
comptime MO_MAX_WORK: Int = 1 << 30

# Arrays of length `n_points` (or of `2 * pop_size`) that one entry point holds live at once.
# MEASURED on the widest path, `_evolve`: rank, crowd, boundary, feasible, violation, alive,
# order, scratch, plus the two-buffer index sort. Used to bound the GA's live population,
# `2 * pop_size * (n_vars + n_obj)` slots, against the shared ceiling divided by this.
comptime MO_POINT_ARRAYS: Int = 10

# Monte-Carlo sample ceiling for a three-or-more-objective hypervolume. Untied to the
# payload — `samples` is a bare Int, the shape `lp_from_arenas` got wrong — so it has its own
# ceiling AND enters the work product `samples * n_nondominated * n_obj`.
comptime MO_MAX_SAMPLES: Int = 1 << 22

# The default sample count and seed for `hypervolume_default`. Explicit, so a convenience
# call is still reproducible and still says which numbers produced its estimate.
comptime MO_DEFAULT_SAMPLES: Int = 1 << 14
comptime MO_DEFAULT_SEED: UInt64 = 20260730

# GA ceilings. Both are untied to the payload and both amplify: `generations` multiplies the
# whole quadratic selection cost and `pop_size` squares it, so `generations * (2*pop)^2 *
# n_obj` is checked against `MO_MAX_WORK` by division as well. A population of 512 is 1024
# points through the front decomposition, inside `MO_MAX_POINTS`.
#
# Neither ceiling is a bound on the RUN, and that mistake is why the evaluation cost is charged
# separately in `nsga2_linear`: `pop_size * (generations + 1) * (2*rows + n_obj) * n_vars` is
# invisible to both of these numbers and to the quadratic budget, and at these ceilings it
# reaches 5e11 elementary operations — about 45 minutes measured — from an 8 MB payload.
comptime MO_MAX_POPULATION: Int = 512
comptime MO_MAX_GENERATIONS: Int = 1 << 12
comptime MO_DEFAULT_POPULATION: Int = 64
comptime MO_DEFAULT_GENERATIONS: Int = 50
comptime MO_DEFAULT_CROSSOVER_P: Float64 = 0.9
comptime MO_DEFAULT_MUTATION_P: Float64 = 0.1

# A mutation step, as a fraction of the variable's OWN range. A fixed absolute step would
# mean a different thing for a variable in [0, 1] than for one in [0, 1e6]; a relative one
# means the same thing for both, which is the only way a single parameter can serve a model
# whose variables are differently scaled.
comptime MO_MUTATION_SCALE: Float64 = 0.25

# The rounding budget for the module's own identities — the hypervolume/bounds self-check and
# the lexicographic lock audit. Sized by DBL_EPSILON and by the magnitude of the quantity
# being judged, NEVER by a caller tolerance and never by a sum over unrelated quantities:
# `LP_FEAS_ULP_BUDGET` and `LP_DBL_EPSILON` are imported from `optimization.linear` rather
# than restated, so a point this module calls feasible is a point `linear` calls feasible.
comptime MO_ULP_BUDGET: Float64 = LP_FEAS_ULP_BUDGET

# The keyed streams. Named, not numbered: `determinism.streams` maps a name into the space
# above the reserved ids, so two concerns cannot silently collide on an integer somebody
# picked twice. Derived once per driver call, never inside a loop — `stream_id` hashes a
# String.
comptime MO_STREAM_INIT: String = "multiobjective.init"
comptime MO_STREAM_TOURNAMENT_A: String = "multiobjective.tournament.a"
comptime MO_STREAM_TOURNAMENT_B: String = "multiobjective.tournament.b"
comptime MO_STREAM_CROSSOVER: String = "multiobjective.crossover"
comptime MO_STREAM_MUTATION: String = "multiobjective.mutation"
comptime MO_STREAM_HYPERVOLUME: String = "multiobjective.hypervolume"

# Dominance classification, returned by `_classify`. Exhaustive for finite inputs, which is
# what makes the four public flags on `DominanceCheck` mutually exclusive.
comptime MO_REL_EQUAL: Int = 0
comptime MO_REL_A_DOMINATES: Int = 1
comptime MO_REL_B_DOMINATES: Int = 2
comptime MO_REL_INCOMPARABLE: Int = 3


fn mo_status_name(code: Int) -> String:
    """Name for a multi-objective status, falling through to `milp_status_name`.

    The fall-through is what keeps one vocabulary: a code this module never issues but
    receives from an inner `lp_solve` — `LP_INFEASIBLE`, `LP_UNBOUNDED`, any `MODEL_ERR_*` —
    still comes back with the name its own module gave it. That includes zero, which comes
    back as `lp_status_name`'s "optimal": this package already has two names for zero, and a
    third would be one more than a caller can reconcile.
    """
    if code == MO_ERR_REFERENCE_POINT:
        return "reference_point_not_dominated_by_every_solution"
    if code == MO_ERR_VERIFICATION_FAILED:
        return "answer_failed_verification_against_input"
    if code == MO_HV_INEXACT:
        return "hypervolume_not_exact_above_two_objectives"
    if code == MO_ERR_PARAMETER:
        return "search_parameter_out_of_range"
    if code == MO_UNPROVEN:
        return "heuristic_front_not_proven_optimal"
    if code == MO_ERR_WORK_LIMIT:
        return "work_limit"
    if code == MO_ERR_LP_STAGE_FAILED:
        return "inner_lp_neither_optimal_nor_infeasible"
    if code == MO_ERR_EMPTY_SET:
        return "empty_point_set"
    if code == MO_ERR_OBJECTIVE_COUNT:
        return "objective_count_out_of_range"
    if code == MO_ERR_LEX_LOCK_INFEASIBLE:
        return "locked_objective_row_infeasible_at_previous_optimum"
    if code == MO_HV_ESTIMATE_CLAMPED:
        return "hypervolume_estimate_clamped_into_its_exact_bounds"
    return milp_status_name(code)


# ── return-only result structs ────────────────────────────────────────────────
# Declared HERE, in this file, because `mojo_inventory.parse_runtime_struct_specs` reads one
# file at a time: a driver returning a struct owned by another module is dropped from the
# contract AND from dispatch with no error. Every field is a scalar or a flat List, so the
# whole surface marshals without a new message type.


@fieldwise_init
struct DominanceCheck(Copyable, Movable):
    """The complete relation between two objective vectors, with nothing inferred.

    All four of `equal`, `a_dominates_b`, `b_dominates_a` and `incomparable` are reported
    rather than left for a caller to derive, because deriving them is where the off-by-one
    lives: `not a_dominates_b` is not `b_dominates_a`, and neither implies `equal`. For
    finite inputs exactly one of the four is True.

    `a_weakly_dominates_b` is the `<=`-in-every-objective relation, which BOTH directions
    satisfy for identical points — that is the distinction between weak and strict, stated
    as data instead of as a comment.

    `first_difference` is the lowest objective index where the two differ, or -1 when they
    are equal, so a caller looking at `incomparable` can see where the trade-off starts.
    On any status other than `MODEL_OK` every flag is False and `first_difference` is -1.
    """

    var status: Int
    var n_objectives: Int
    var equal: Bool
    var a_dominates_b: Bool
    var b_dominates_a: Bool
    var a_weakly_dominates_b: Bool
    var b_weakly_dominates_a: Bool
    var incomparable: Bool
    var first_difference: Int


@fieldwise_init
struct FrontSort(Copyable, Movable):
    """A full front decomposition, verified pairwise before it is returned.

    `rank[i]` is point `i`'s front index, 0 for the Pareto-optimal set. `order` lists every
    point grouped by front, ascending rank then ascending original index, and
    `front_start` holds `n_fronts + 1` offsets into it, so front `r` is
    `order[front_start[r] : front_start[r+1]]` — the same offsets-plus-payload shape CSR
    uses, because a nested list cannot cross the wire. `first_front` repeats front 0 for the
    common case.

    Two conditions are checked before returning, and a failure is
    `MO_ERR_VERIFICATION_FAILED` with every list EMPTY:

      1. within each front, no member strictly dominates another. A "front" containing a
         dominated point is not a front, and a subtle comparison bug produces exactly that
         and nothing else visible;
      2. every point of rank r >= 1 is strictly dominated by at least one point of rank
         r - 1. Without this the ranks could be tight nowhere and still pass (1) — the
         decomposition would be a valid partition into antichains but not THE front
         decomposition.

    `witness_a` / `witness_b` name the dominating and dominated point when (1) fails, and
    `witness_b` alone names the point with no dominator when (2) fails; both are -1
    otherwise.
    """

    var status: Int
    var verified: Bool
    var n_points: Int
    var n_objectives: Int
    var n_fronts: Int
    var comparisons: Int
    var witness_a: Int
    var witness_b: Int
    var rank: List[Int]
    var order: List[Int]
    var front_start: List[Int]
    var first_front: List[Int]


@fieldwise_init
struct ParetoCertificate(Copyable, Movable):
    """Whether a front SOMEBODY ELSE produced is the Pareto set of this point set.

    `certified` is the conjunction of four conditions, each also reported on its own so a
    caller can see which one failed rather than only that something did:

      1. `indices_valid`         — every claimed index is in `[0, n_points)` and distinct;
      2. `mutually_nondominated` — no claimed member strictly dominates another claimed
                                   member (it is an antichain);
      3. `unbeaten`              — no point OUTSIDE the claim strictly dominates a member;
      4. `maximal`               — every point outside the claim IS strictly dominated by a
                                   member, so nothing Pareto-optimal was left out.

    All four are necessary and only together are they sufficient. (2) and (3) hold for any
    subset of the true front, so a claim of one point out of forty passes both — (4) is what
    makes the certificate about the whole Pareto set instead of about a fragment of it. This
    is the condition a certificate omits when no test exercises the shape that needs it.

    `n_true_front` is computed independently by the FROZEN `multi_objective.pareto_front`, so
    the size comparison comes from code this module did not write. It does NOT depend on the
    claim being any good, so it is computed on every path that reads the point matrix at all —
    a rejected claim reports the same true front size a certified one does — and it is -1,
    never 0, when the matrix itself was refused and no front exists to size. A rank-0 subset of
    a non-empty point set is never empty, so a returned 0 could only ever have been a
    fabrication: the two rejection paths here once disagreed, one returning the real size and
    the other a hardcoded 0 under `MODEL_OK`.

    The two witness fields name a PAIR when (2) or (3) fails: `witness_dominator` beats
    `witness_dominated`. When only (4) fails there is no such pair, so `witness_dominated`
    names the Pareto-optimal point the claim left out and `witness_dominator` stays -1. Both
    are -1 when nothing failed.

    What the certificate does NOT claim: that the point set is complete (points nobody
    supplied cannot be checked), and nothing at all about the decision variables behind the
    objective vectors.
    """

    var status: Int
    var certified: Bool
    var indices_valid: Bool
    var mutually_nondominated: Bool
    var unbeaten: Bool
    var maximal: Bool
    var n_claimed: Int
    var n_true_front: Int
    var witness_dominator: Int
    var witness_dominated: Int


@fieldwise_init
struct Crowding(Copyable, Movable):
    """Crowding distance over ONE front, with the boundary as a flag and not an infinity.

    `distance[i]` is the sum over objectives of the normalised gap between point `i`'s two
    neighbours in that objective's sorted order, and is always FINITE. `is_boundary[i]` is
    True when `i` is first or last in some objective's order, which is the case textbook
    NSGA-II gives an infinite distance: a boundary point outranks every non-boundary point
    however small its finite `distance` is, and `order` already applies that rule.

    `order` is the ranking this file uses everywhere, stated so it is reproducible: boundary
    points first, then descending `distance`, ties broken by ascending original index.

    WHICH points are boundary, stated as the code does it: per objective, the two ENDS of that
    objective's stable ascending order — `order[0]` and `order[m-1]` — are flagged, so exactly
    two flags per objective and never more, however many points share an extreme value. The
    sort's stability then fixes which: among the points tied at the MINIMUM the lowest index
    is flagged, and among those tied at the MAXIMUM the HIGHEST index is. A duplicate of an
    extreme point therefore CAN be boundary itself — for `f = [2,2, 2,2, 2,2]` every point ties
    at both ends of both objectives and the flags are (True, False, True), the lowest and the
    highest index, `n_boundary = 2`. (An earlier version of this paragraph said the lowest
    index was the boundary one at both ends and that a duplicate of an extreme point is never
    boundary; both halves were false, and the second is exactly what that example refutes.)
    The rule is not changed — it is what makes a returned `order` reproducible, it is standard
    NSGA-II's two extremes per objective, and every selection order in this file is derived
    from it.

    An objective whose range is zero contributes nothing to any distance and is counted in
    `degenerate_objectives`; dividing by that range is what would produce the infinity this
    struct exists to avoid.

    Crowding distance across MIXED ranks is not a defined quantity — the caller passes one
    front. Nothing here can detect that it did not, which is why it is said here.
    """

    var status: Int
    var n_points: Int
    var n_objectives: Int
    var n_boundary: Int
    var degenerate_objectives: Int
    var distance: List[Float64]
    var is_boundary: List[Bool]
    var order: List[Int]


@fieldwise_init
struct Selection(Copyable, Movable):
    """NSGA-II environmental selection: whole fronts, then the last one by crowding.

    `chosen` holds `n_selected` distinct point indices in selection order, and `rank` their
    front indices in the same order — non-decreasing by construction, which is asserted
    before returning. `truncated_front` is the rank of the front that had to be cut, or -1
    when the selection landed on a front boundary.

    `n_selected` is `min(n_select, n_points)`: asking for more points than exist is answered
    with all of them, not padded. Asking for none is answered with none.
    """

    var status: Int
    var verified: Bool
    var n_points: Int
    var n_selected: Int
    var n_fronts_used: Int
    var truncated_front: Int
    var chosen: List[Int]
    var rank: List[Int]


@fieldwise_init
struct Hypervolume(Copyable, Movable):
    """The dominated volume against an explicit reference point, exact where it can be.

    `reference` is echoed back because the number is meaningless without it: two
    hypervolumes are comparable only against the same reference, and a value that travelled
    without one cannot be interpreted later.

    `exact` and `has_value` are True only for one or two objectives, where the sweep is
    exact. For three or more the status is `MO_HV_INEXACT`, `has_value` is False, and
    `estimate` / `std_error` / `samples` carry a deterministic Monte-Carlo measurement
    (absent, with `has_estimate` False, when `samples` is 0).

    `bound_lower` and `bound_upper` are EXACT for any number of objectives and always
    populated on success: the largest single box is contained in the union, and the union is
    contained in both the spanning box and the sum of the boxes. An exact `value` outside
    those bounds is `MO_ERR_VERIFICATION_FAILED`, and the two bounds are checked against EACH
    OTHER before anything is returned — two proven bounds that crossed would leave a caller
    with no usable number at all.

    An `estimate` is subject to those same bounds, and this is a GUARANTEE of the struct rather
    than an accident of the sampler: `bound_lower <= estimate <= bound_upper` whenever
    `has_estimate` is True. A draw that landed outside was clamped into the interval, its
    `std_error` widened to cover the distance moved, and the status is
    `MO_HV_ESTIMATE_CLAMPED` to say so. `std_error` is floored at one draw's own weight,
    `spanning box / samples`, because zero hits out of `samples` is no measurement rather than a
    measurement of zero; it is then capped at `bound_upper - bound_lower`, which is the largest
    error the two proofs leave room for. So `std_error == 0.0` occurs only when
    `bound_lower == bound_upper` — the volume proven exactly — and never from a degenerate
    sample.

    `n_nondominated` is the size of the rank-0 subset actually swept — dominated points
    cannot add volume — and `degenerate_points` counts solutions touching the reference in
    some objective, whose own box is empty.
    """

    var status: Int
    var exact: Bool
    var has_value: Bool
    var value: Float64
    var has_estimate: Bool
    var estimate: Float64
    var std_error: Float64
    var samples: Int
    var bound_lower: Float64
    var bound_upper: Float64
    var n_points: Int
    var n_objectives: Int
    var n_nondominated: Int
    var degenerate_points: Int
    var reference: List[Float64]


@fieldwise_init
struct Nsga2Result(Copyable, Movable):
    """A heuristic front, its verification, and the one bound that was actually proven.

    `status` is `MO_UNPROVEN` on success and NEVER `MODEL_OK`. There is deliberately no
    `proven_optimal` field: a genetic algorithm has no certificate to set one from, and a
    flag that a local search can set is a flag a caller will trust.

    `verified` is a narrow, checked claim: every returned point satisfies the caller's rows
    within a per-row budget and lies inside its box, and the returned set is pairwise
    non-dominated. `max_violation` is the largest per-row violation seen among the returned
    points and is 0.0 when `verified` is True.

    `ideal[j]` is the EXACT global minimum of objective `j` over the feasible region, from
    one `lp_solve` per objective, so `ideal_gap[j]` — the returned front's best objective `j`
    minus `ideal[j]` — is a real per-objective optimality gap. It is the bound this driver
    has; the front's own spread is not evidence about anything.

    `front_x` is `n_front * n_vars` row-major and `front_f` is `n_front * n_objectives`, in
    the same point order, ascending by population index. Two DIFFERENT decisions with
    identical objective vectors are BOTH kept — neither dominates the other, and either might
    be the one a caller wants — while an exact duplicate of both vectors is collapsed, because
    a repeated decision is not a second solution. So `n_front <= max_front`, and it is smaller
    when the population held fewer distinct non-dominated points than that.
    """

    var status: Int
    var verified: Bool
    var n_front: Int
    var n_vars: Int
    var n_objectives: Int
    var generations_run: Int
    var evaluations: Int
    var n_feasible: Int
    var stage_status: Int
    var failed_stage: Int
    var has_ideal: Bool
    var max_violation: Float64
    var ideal: List[Float64]
    var ideal_gap: List[Float64]
    var front_x: List[Float64]
    var front_f: List[Float64]


@fieldwise_init
struct LexResult(Copyable, Movable):
    """Lexicographic optimisation by priority order, with every lock reported.

    Objective 0 has the highest priority. Stage `k` minimises `c_k·x` subject to the
    caller's rows AND `c_j·x <= optima[j] + slack[j]` for every `j < k`, so
    `locked[j]` / `optima[j]` / `slack[j]` say exactly which objectives were frozen, at what
    values, and with how much room — the three numbers a caller needs to reproduce the
    answer.

    `slack[j]` is `tolerance * |optima[j]|` plus a rounding allowance sized by DBL_EPSILON
    and by objective `j`'s OWN term magnitudes. Not by a sum over the other objectives:
    that form let 200 unrelated rows swallow a flat contradiction in this package once
    already.

    Unlike `nsga2_linear` this is exact — every stage is a simplex solve — so success is
    `MODEL_OK`. `verified` re-checks the returned `x` against the caller's rows and against
    every lock, each within that row's OWN per-row budget: for a lock that is `slack[j]` plus
    the budget `lp_solve` itself applies to the lock row, because the audit cannot demand more
    of the answer than the solver promised. `max_deviation` is the RAW largest
    `|c_j·x - optima[j]|`, unbudgeted, so a caller can see the number rather than only the
    verdict.

    `objective_values` holds all `n_objectives` objectives at the returned `x`, including the
    stages that were never optimised, because a caller comparing alternatives needs the
    whole vector. On a failure status `x` is EMPTY and `has_solution` is False, while
    `optima` still carries the stages that DID solve — those values were proven, and dropping
    them would discard a real answer along with the missing one.
    """

    var status: Int
    var verified: Bool
    var has_solution: Bool
    var n_vars: Int
    var n_objectives: Int
    var stages_solved: Int
    var failed_stage: Int
    var stage_status: Int
    var iterations: Int
    var max_deviation: Float64
    var x: List[Float64]
    var optima: List[Float64]
    var slack: List[Float64]
    var locked: List[Bool]
    var objective_values: List[Float64]


# ── the dominance relation ────────────────────────────────────────────────────
# ONE relation, used by every pass in this file. `_strictly_dominates` is a flat-indexed shim
# over the FROZEN `multi_objective.is_dominated`, present only because the frozen signature
# takes two `List[Float64]` plus a mask and the inner loops here are O(n^2): building three
# lists per pair would allocate millions of times. `mo_dominance` evaluates BOTH and reports
# `MO_ERR_VERIFICATION_FAILED` on disagreement, and the suite asserts agreement over every
# sign pattern in one, two and three objectives — so the shim cannot drift silently, which is
# the only reason having it is defensible.


fn _strictly_dominates(
    f: List[Float64], n_obj: Int, i: Int, j: Int
) -> Bool:
    """True when point `i` strictly dominates point `j`, minimising every objective.

    `i` and `j` index POINTS in the flat row-major matrix; caller guarantees both are in
    range and every value finite (`mo_matrix_defect`). Weakly better everywhere and strictly
    better somewhere — so identical points do not dominate each other.
    """
    var base_i = i * n_obj
    var base_j = j * n_obj
    var strictly_better = False
    for t in range(n_obj):
        var a = f[base_i + t]
        var b = f[base_j + t]
        if a > b:
            return False
        if a < b:
            strictly_better = True
    return strictly_better


fn _weakly_dominates(f: List[Float64], n_obj: Int, i: Int, j: Int) -> Bool:
    """True when point `i` is no worse than point `j` in EVERY objective.

    A different relation from `_strictly_dominates`, not a weaker copy of it: both directions
    hold for identical points, which is precisely what "weak" means here.
    """
    var base_i = i * n_obj
    var base_j = j * n_obj
    for t in range(n_obj):
        if f[base_i + t] > f[base_j + t]:
            return False
    return True


fn _frozen_dominates(
    f: List[Float64], n_obj: Int, i: Int, j: Int
) -> Bool:
    """`multi_objective.is_dominated` asking whether point `i` dominates point `j`.

    The frozen signature is `is_dominated(a, b, maximize)` = "does b dominate a", so the
    arguments are passed in the order (j, i) — the reversal is the whole reason this wrapper
    exists instead of the call being inlined at three sites.
    """
    var a = List[Float64]()
    var b = List[Float64]()
    var mask = List[Bool]()
    for t in range(n_obj):
        a.append(f[j * n_obj + t])
        b.append(f[i * n_obj + t])
        mask.append(False)
    return is_dominated(a, b, mask)


fn _classify(f: List[Float64], n_obj: Int, i: Int, j: Int) -> Int:
    """One of the four `MO_REL_*` cases. Exhaustive for finite values.

    Equality is checked first so it is never confused with mutual weak dominance, which it
    implies.
    """
    var equal = True
    for t in range(n_obj):
        if f[i * n_obj + t] != f[j * n_obj + t]:
            equal = False
            break
    if equal:
        return MO_REL_EQUAL
    if _strictly_dominates(f, n_obj, i, j):
        return MO_REL_A_DOMINATES
    if _strictly_dominates(f, n_obj, j, i):
        return MO_REL_B_DOMINATES
    return MO_REL_INCOMPARABLE


# ── shape and resource validation ─────────────────────────────────────────────


fn _pair_work_fits(n_points: Int, n_obj: Int) -> Bool:
    """True when `n_points^2 * n_obj * MO_SORT_PAIR_PASSES` fits `MO_MAX_WORK`.

    Written with DIVISIONS throughout. `n_points * n_points` is a wrapping 64-bit multiply, so
    a test written as a product is not a bound at all — the same non-guard
    `sparse_numerics.csr.dims_fit` exists to replace.
    """
    if n_points <= 0 or n_obj <= 0:
        return True
    var budget = MO_MAX_WORK // MO_SORT_PAIR_PASSES
    budget = budget // n_obj
    if budget <= 0:
        return False
    return n_points <= budget // n_points


fn mo_matrix_defect(f: List[Float64], n_points: Int, n_obj: Int) -> Int:
    """`MODEL_OK` when `f` is a usable `n_points x n_obj` objective matrix, else the defect.

    The one door every driver in this file goes through, so a rejection means the same thing
    from all of them. In order: the objective count, the shape (via `dims_fit`, a division —
    `n_points * n_obj == len(f)` wraps), the point ceiling, the quadratic work, emptiness,
    and finally finiteness of every value.

    Finiteness is not a decoration here. Every comparison against a `nan` is False, so a
    `nan` coordinate would make a point neither dominating nor dominated: it would join every
    front as rank 0, and the frozen relation agrees with the shim about it, so the
    cross-check could not catch it either. It has to be refused before any comparison runs.
    """
    if n_obj < 1 or n_obj > MO_MAX_OBJECTIVES:
        return MO_ERR_OBJECTIVE_COUNT
    if not dims_fit(n_points, n_obj, len(f)):
        return MODEL_ERR_DENSE_SHAPE
    if n_points > MO_MAX_POINTS:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    if not _pair_work_fits(n_points, n_obj):
        return MO_ERR_WORK_LIMIT
    if n_points < 1:
        return MO_ERR_EMPTY_SET
    for t in range(len(f)):
        if not _finite(f[t]):
            return MODEL_ERR_NON_FINITE_VALUE
    return MODEL_OK


# ── a stable index sort ───────────────────────────────────────────────────────


fn _stable_index_sort(keys: List[Float64], idx: List[Int]) -> List[Int]:
    """`idx` reordered so `keys[idx[t]]` ascends. Stable, iterative, bottom-up merge.

    No frozen kernel sorts INDICES: `sorting.insertion_sort`, `sorting.mergesort` and
    `stats.fast_sort` all sort values and return no permutation, so the point identity a
    crowding sweep has to walk back to is lost. Stability is what makes "ties break by
    ascending original index" a stated property of every order in this file rather than an
    artefact of a partition step — a quicksort would give a different, equally valid, and
    unreproducible answer.

    Bottom-up rather than recursive, matching `graph/algorithms.mojo`'s preference for an
    explicit iteration, and O(n log n) rather than the insertion sort's O(n^2): the crowding
    pass runs once per objective.
    """
    var n = len(idx)
    var cur = idx.copy()
    if n < 2:
        return cur^
    var buf = idx.copy()
    var width = 1
    while width < n:
        var lo = 0
        while lo < n:
            var mid = lo + width
            if mid > n:
                mid = n
            var hi = lo + width + width
            if hi > n:
                hi = n
            var l = lo
            var r = mid
            var o = lo
            while l < mid and r < hi:
                # `<` and not `<=`, so an equal key keeps the LEFT run's element: that is
                # what makes the sort stable and the tie-break statable.
                if keys[cur[r]] < keys[cur[l]]:
                    buf[o] = cur[r]
                    r += 1
                else:
                    buf[o] = cur[l]
                    l += 1
                o += 1
            while l < mid:
                buf[o] = cur[l]
                l += 1
                o += 1
            while r < hi:
                buf[o] = cur[r]
                r += 1
                o += 1
            lo += width + width
        for t in range(n):
            cur[t] = buf[t]
        width += width
    return cur^


# ── front decomposition ───────────────────────────────────────────────────────


fn _front_ranks(
    f: List[Float64], n_obj: Int, idx: List[Int], mut rank: List[Int]
) -> Int:
    """Deb's fast non-dominated sort over the points `idx` names. Returns the front count.

    `rank` is written positionally — `rank[t]` is the front of `idx[t]` — and is assumed to
    have length `len(idx)`.

    Two passes, both O(m^2) and neither storing the O(m^2) dominated SETS the textbook
    formulation keeps: pass one counts each point's dominators, and the peel then decrements
    those counts front by front. Summed over fronts the peel touches each ordered pair at
    most once, because a point participates as a decrementer in exactly the one front it
    belongs to. So the work is the same and the memory is O(m) instead of O(m^2), which is
    what rule 1c is about — a per-item ceiling is not a bound on total allocation.

    Returns -1 when a front comes back EMPTY with points still unranked. That cannot happen:
    strict dominance is a strict partial order, so every non-empty finite subset has a
    minimal element. It is therefore a self-check on the comparison itself — a cycle means
    `_strictly_dominates` is not asymmetric — and the callers turn it into
    `MO_ERR_VERIFICATION_FAILED` rather than looping forever or returning a partial ranking.
    """
    var m = len(idx)
    if m == 0:
        return 0
    var count = List[Int]()
    for t in range(m):
        count.append(0)
        rank[t] = -1
    for t in range(m):
        for u in range(m):
            if u == t:
                continue
            if _strictly_dominates(f, n_obj, idx[u], idx[t]):
                count[t] += 1

    var current = List[Int]()
    var ranked = 0
    for t in range(m):
        if count[t] == 0:
            rank[t] = 0
            current.append(t)
            ranked += 1
    if len(current) == 0:
        return -1

    var r = 0
    while ranked < m:
        var nxt = List[Int]()
        for c in range(len(current)):
            var member = current[c]
            for t in range(m):
                if rank[t] != -1:
                    continue
                if _strictly_dominates(f, n_obj, idx[member], idx[t]):
                    count[t] -= 1
                    if count[t] == 0:
                        nxt.append(t)
        if len(nxt) == 0:
            return -1
        r += 1
        for t in range(len(nxt)):
            rank[nxt[t]] = r
            ranked += 1
        current = nxt^
    return r + 1


fn _rank0_subset(f: List[Float64], n_points: Int, n_obj: Int) -> List[Int]:
    """The strictly non-dominated points, ascending index. Duplicates all survive.

    Used where only the first front matters — hypervolume, where a dominated point cannot add
    volume. Identical points are mutually non-dominating under the stated convention, so a
    duplicated optimum appears twice; the hypervolume sweep removes it on the staircase step,
    where the removal is the sweep's own invariant rather than a dominance decision.
    """
    var out = List[Int]()
    for i in range(n_points):
        var beaten = False
        for j in range(n_points):
            if j == i:
                continue
            if _strictly_dominates(f, n_obj, j, i):
                beaten = True
                break
        if not beaten:
            out.append(i)
    return out^


fn nondominated_sort(
    f: List[Float64], n_points: Int, n_obj: Int
) -> FrontSort:
    """Rank every point by front, minimising all objectives, and verify the ranks.

    `f` is row-major `n_points x n_obj`. See `FrontSort` for the two verification conditions
    and the `order` / `front_start` layout; a failure returns EMPTY lists, because a
    decomposition that fails its own definition is not a partial answer.
    """
    var defect = mo_matrix_defect(f, n_points, n_obj)
    if defect != MODEL_OK:
        return _no_front(defect, n_points, n_obj)

    var idx = List[Int]()
    var rank = List[Int]()
    for i in range(n_points):
        idx.append(i)
        rank.append(-1)
    var n_fronts = _front_ranks(f, n_obj, idx, rank)
    if n_fronts < 0:
        return _no_front(MO_ERR_VERIFICATION_FAILED, n_points, n_obj)

    # Condition 1: each front is an antichain. This is the check that a plausible-looking
    # front is really a front, and it is done against the caller's own values, not against
    # the counts the sort just used.
    for i in range(n_points):
        for j in range(n_points):
            if i == j or rank[i] != rank[j]:
                continue
            if _strictly_dominates(f, n_obj, i, j):
                var bad = _no_front(MO_ERR_VERIFICATION_FAILED, n_points, n_obj)
                bad.witness_a = i
                bad.witness_b = j
                return bad^

    # Condition 2: the ranks are TIGHT — a point in front r >= 1 has a dominator in front
    # r - 1. Condition 1 alone would accept any partition into antichains.
    for i in range(n_points):
        if rank[i] == 0:
            continue
        var covered = False
        for j in range(n_points):
            if rank[j] != rank[i] - 1:
                continue
            if _strictly_dominates(f, n_obj, j, i):
                covered = True
                break
        if not covered:
            var bad2 = _no_front(MO_ERR_VERIFICATION_FAILED, n_points, n_obj)
            bad2.witness_b = i
            return bad2^

    var front_size = List[Int]()
    for _ in range(n_fronts):
        front_size.append(0)
    for i in range(n_points):
        front_size[rank[i]] += 1
    var front_start = List[Int]()
    var running = 0
    for r in range(n_fronts):
        front_start.append(running)
        running += front_size[r]
    front_start.append(running)

    var cursor = List[Int]()
    for r in range(n_fronts):
        cursor.append(front_start[r])
    var order = List[Int]()
    for _ in range(n_points):
        order.append(0)
    for i in range(n_points):
        order[cursor[rank[i]]] = i
        cursor[rank[i]] += 1
    var first = List[Int]()
    for t in range(front_start[1]):
        first.append(order[t])

    var comparisons = n_points * n_points
    return FrontSort(
        MODEL_OK, True, n_points, n_obj, n_fronts, comparisons, -1, -1,
        rank^, order^, front_start^, first^,
    )


fn _no_front(status: Int, n_points: Int, n_obj: Int) -> FrontSort:
    return FrontSort(
        status, False, n_points, n_obj, 0, 0, -1, -1,
        List[Int](), List[Int](), List[Int](), List[Int](),
    )


fn pareto_certify(
    f: List[Float64], n_points: Int, n_obj: Int, claimed: List[Int]
) -> ParetoCertificate:
    """Check a claimed Pareto set against the point data, condition by condition.

    See `ParetoCertificate` for the four conditions and what the certificate does not cover.
    The true front size comes from the FROZEN `multi_objective.pareto_front`, so the
    comparison is against an independent implementation.
    """
    var defect = mo_matrix_defect(f, n_points, n_obj)
    if defect != MODEL_OK:
        # No front of a matrix this module would not read, so -1 says ABSENT. A 0 here would
        # read as "the true front is empty", which is not a thing a non-empty point set can be.
        return ParetoCertificate(
            defect, False, False, False, False, False, len(claimed), -1, -1, -1
        )

    # The independent oracle: the frozen kernel over its own nested form. Built ONCE, and
    # before the claim is looked at, because the true front size is a property of the POINT
    # SET and not of the claim — every path below reports the same number. Computing it only
    # on the paths that happened to have a test is how one rejection path came to return the
    # real size while the other returned a hardcoded 0 under `MODEL_OK` (rule 4: a fabricated
    # number under a success status). It is also the only source for this field now: the
    # empty-claim path used `_rank0_subset`, this module's own shim, so one field was fed by
    # two implementations and "computed by the frozen kernel" was true of only one path.
    var nested = List[List[Float64]]()
    var mask = List[Bool]()
    for _ in range(n_obj):
        mask.append(False)
    for i in range(n_points):
        var row = List[Float64]()
        for t in range(n_obj):
            row.append(f[i * n_obj + t])
        nested.append(row^)
    var n_true = len(_pareto_front_frozen(nested, mask))

    # Condition 1: in range and distinct. Checked first, because every later condition
    # indexes with these.
    var seen = List[Bool]()
    for _ in range(n_points):
        seen.append(False)
    var indices_valid = True
    for t in range(len(claimed)):
        var c = claimed[t]
        if c < 0 or c >= n_points or seen[c]:
            indices_valid = False
            break
        seen[c] = True
    if not indices_valid:
        return ParetoCertificate(
            MODEL_OK, False, False, False, False, False, len(claimed), n_true, -1, -1
        )
    if len(claimed) == 0:
        # An empty claim is a valid antichain and is trivially unbeaten, but it is maximal
        # only for an empty point set — which `mo_matrix_defect` has already refused. Saying
        # so explicitly beats letting the loops below answer True by vacuity.
        return ParetoCertificate(
            MODEL_OK, False, True, True, True, False, 0, n_true, -1, -1,
        )

    var mutually = True
    var w_dominator = -1
    var w_dominated = -1
    for s in range(len(claimed)):
        for t in range(len(claimed)):
            if s == t:
                continue
            if _strictly_dominates(f, n_obj, claimed[s], claimed[t]):
                mutually = False
                w_dominator = claimed[s]
                w_dominated = claimed[t]
                break
        if not mutually:
            break

    var unbeaten = True
    for t in range(len(claimed)):
        for j in range(n_points):
            if seen[j]:
                continue
            if _strictly_dominates(f, n_obj, j, claimed[t]):
                unbeaten = False
                if w_dominator < 0:
                    w_dominator = j
                    w_dominated = claimed[t]
                break
        if not unbeaten:
            break

    var maximal = True
    for j in range(n_points):
        if seen[j]:
            continue
        var beaten = False
        for t in range(len(claimed)):
            if _strictly_dominates(f, n_obj, claimed[t], j):
                beaten = True
                break
        if not beaten:
            maximal = False
            if w_dominated < 0:
                w_dominated = j
            break

    var certified = indices_valid and mutually and unbeaten and maximal
    return ParetoCertificate(
        MODEL_OK, certified, True, mutually, unbeaten, maximal,
        len(claimed), n_true, w_dominator, w_dominated,
    )


fn _pareto_front_frozen(
    objectives: List[List[Float64]], maximize: List[Bool]
) -> List[Int]:
    """The frozen `multi_objective.pareto_front`, behind a name that says whose code it is.

    PRIVATE, and it has to be: the parameter is a NESTED list. `mojo_inventory` would accept
    the signature — `List[List[Float64]]` is structurally marshalable — and the generated A-Z
    suite would then have to synthesise one, which is the trap `combinatorial.tsp_greedy`
    sets. The underscore keeps it out of the contract; the wrapper still exists so
    `pareto_certify`'s oracle call reads as a call into frozen code.
    """
    return pareto_front(objectives, maximize)


# ── crowding distance ─────────────────────────────────────────────────────────


fn _crowding_for_subset(
    f: List[Float64], n_obj: Int, idx: List[Int],
    mut distance: List[Float64], mut boundary: List[Bool],
) -> Int:
    """Crowding distance over the points `idx` names, written positionally into the outputs.

    Returns the number of objectives whose range over this subset is zero. `distance` and
    `boundary` are assumed to have length `len(idx)`.
    """
    var m = len(idx)
    for t in range(m):
        distance[t] = 0.0
        boundary[t] = False
    if m == 0:
        return 0
    if m <= 2:
        # Both (or the one) points are the extremes of every objective, so every one of them
        # is a boundary point and no interior gap exists. Standard NSGA-II reaches the same
        # place through infinite distances; the flag says it without the infinity.
        for t in range(m):
            boundary[t] = True
        return 0

    var degenerate = 0
    var positions = List[Int]()
    for t in range(m):
        positions.append(t)
    for o in range(n_obj):
        # Keys are indexed BY POSITION in `idx`, so the sort helper's stability gives the
        # documented tie-break (ascending position, hence ascending original index).
        var keys = List[Float64]()
        for t in range(m):
            keys.append(f[idx[t] * n_obj + o])
        var order = _stable_index_sort(keys, positions)
        var lo = keys[order[0]]
        var hi = keys[order[m - 1]]
        var span = hi - lo
        boundary[order[0]] = True
        boundary[order[m - 1]] = True
        if not (span > 0.0):
            # A zero range contributes nothing. Dividing by it is where the infinity this
            # struct exists to avoid would come from.
            degenerate += 1
            continue
        for t in range(1, m - 1):
            var gap = keys[order[t + 1]] - keys[order[t - 1]]
            distance[order[t]] += gap / span
    return degenerate


fn _crowding_order(
    idx: List[Int], distance: List[Float64], boundary: List[Bool]
) -> List[Int]:
    """Positions into `idx`, ordered boundary-first then descending distance then index.

    A selection sort over positions rather than a keyed sort, because the primary key is a
    Bool and the secondary is descending — encoding both into one Float64 key would perturb
    the distance, the same reason `flow.mojo` refused to pack `(distance, node)` into one
    heap key.
    """
    var m = len(idx)
    var used = List[Bool]()
    for _ in range(m):
        used.append(False)
    var out = List[Int]()
    for _ in range(m):
        var best = -1
        for t in range(m):
            if used[t]:
                continue
            if best < 0:
                best = t
                continue
            if boundary[t] != boundary[best]:
                if boundary[t]:
                    best = t
                continue
            if distance[t] > distance[best]:
                best = t
                continue
            if distance[t] == distance[best] and idx[t] < idx[best]:
                best = t
        used[best] = True
        out.append(best)
    return out^


fn crowding_distance(
    f: List[Float64], n_points: Int, n_obj: Int
) -> Crowding:
    """Crowding distance and the NSGA-II ranking order over ONE front.

    See `Crowding` for the boundary convention (a flag, never an infinity), the stated
    ordering and tie-break, and the note that mixed ranks are not a defined input.
    """
    var defect = mo_matrix_defect(f, n_points, n_obj)
    if defect != MODEL_OK:
        return Crowding(
            defect, n_points, n_obj, 0, 0, List[Float64](), List[Bool](), List[Int]()
        )

    var idx = List[Int]()
    var distance = List[Float64]()
    var boundary = List[Bool]()
    for i in range(n_points):
        idx.append(i)
        distance.append(0.0)
        boundary.append(False)
    var degenerate = _crowding_for_subset(f, n_obj, idx, distance, boundary)

    var n_boundary = 0
    for t in range(n_points):
        if boundary[t]:
            n_boundary += 1
    var positions = _crowding_order(idx, distance, boundary)
    var order = List[Int]()
    for t in range(len(positions)):
        order.append(idx[positions[t]])
    return Crowding(
        MODEL_OK, n_points, n_obj, n_boundary, degenerate,
        distance^, boundary^, order^,
    )


# ── environmental selection ───────────────────────────────────────────────────


fn _select_by_rank(
    f: List[Float64], n_obj: Int, rank: List[Int], count: Int,
    n_fronts: Int, n_select: Int,
) -> List[Int]:
    """Whole fronts in rank order, the last one cut by crowding. Point indices, in order.

    Shared by `nsga2_select` and the GA's generational replacement so the two cannot disagree
    about what "the best `n` of these" means. Crowding is computed PER FRONT, which is the
    only set it is defined over.

    `count` is passed explicitly and is NOT `len(rank)`: the GA's arrays are allocated at the
    combined parent-plus-offspring capacity and only the first `count` slots are live, so
    reading the length would rank stale individuals from a previous generation.
    """
    var out = List[Int]()
    if n_select <= 0:
        return out^
    for r in range(n_fronts):
        var members = List[Int]()
        for i in range(count):
            if rank[i] == r:
                members.append(i)
        if len(members) == 0:
            continue
        if len(out) + len(members) <= n_select:
            for t in range(len(members)):
                out.append(members[t])
            if len(out) == n_select:
                return out^
            continue
        var distance = List[Float64]()
        var boundary = List[Bool]()
        for _ in range(len(members)):
            distance.append(0.0)
            boundary.append(False)
        _ = _crowding_for_subset(f, n_obj, members, distance, boundary)
        var positions = _crowding_order(members, distance, boundary)
        var t2 = 0
        while len(out) < n_select and t2 < len(positions):
            out.append(members[positions[t2]])
            t2 += 1
        return out^
    return out^


fn nsga2_select(
    f: List[Float64], n_points: Int, n_obj: Int, n_select: Int
) -> Selection:
    """The NSGA-II survival step: best `n_select` points by front rank then crowding.

    See `Selection`. `n_select` above `n_points` selects everything rather than padding, and
    the returned ranks are verified non-decreasing and the indices distinct before returning.
    """
    var defect = mo_matrix_defect(f, n_points, n_obj)
    if defect != MODEL_OK:
        return Selection(defect, False, n_points, 0, 0, -1, List[Int](), List[Int]())
    if n_select < 0:
        return Selection(
            MO_ERR_PARAMETER, False, n_points, 0, 0, -1, List[Int](), List[Int]()
        )

    var idx = List[Int]()
    var rank = List[Int]()
    for i in range(n_points):
        idx.append(i)
        rank.append(-1)
    var n_fronts = _front_ranks(f, n_obj, idx, rank)
    if n_fronts < 0:
        return Selection(
            MO_ERR_VERIFICATION_FAILED, False, n_points, 0, 0, -1,
            List[Int](), List[Int](),
        )

    var want = n_select if n_select < n_points else n_points
    var chosen = _select_by_rank(f, n_obj, rank, n_points, n_fronts, want)
    var chosen_rank = List[Int]()
    for t in range(len(chosen)):
        chosen_rank.append(rank[chosen[t]])

    # Verification: the right count, distinct indices, non-decreasing ranks. A selection that
    # repeats a point or reaches into a worse front before finishing a better one is not an
    # NSGA-II selection.
    var ok = len(chosen) == want
    var seen = List[Bool]()
    for _ in range(n_points):
        seen.append(False)
    for t in range(len(chosen)):
        var c = chosen[t]
        if c < 0 or c >= n_points or seen[c]:
            ok = False
            break
        seen[c] = True
    for t in range(1, len(chosen_rank)):
        if chosen_rank[t] < chosen_rank[t - 1]:
            ok = False
            break
    if not ok:
        return Selection(
            MO_ERR_VERIFICATION_FAILED, False, n_points, 0, 0, -1,
            List[Int](), List[Int](),
        )

    var fronts_used = 0
    var truncated = -1
    if len(chosen_rank) > 0:
        fronts_used = chosen_rank[len(chosen_rank) - 1] + 1
        var last_rank = chosen_rank[len(chosen_rank) - 1]
        var taken = 0
        var total = 0
        for t in range(len(chosen_rank)):
            if chosen_rank[t] == last_rank:
                taken += 1
        for i in range(n_points):
            if rank[i] == last_rank:
                total += 1
        if taken < total:
            truncated = last_rank
    return Selection(
        MODEL_OK, True, n_points, len(chosen), fronts_used, truncated,
        chosen^, chosen_rank^,
    )


# ── reference points, ideal and nadir ─────────────────────────────────────────


fn _nested_rows(f: List[Float64], n_points: Int, n_obj: Int) -> List[List[Float64]]:
    """The nested form the frozen `multi_objective` kernels take. Internal only.

    A nested list cannot cross the wire (rule 2), so it never appears in a public signature
    here; it exists solely to feed frozen code its own shape, which is the trap
    `combinatorial.tsp_greedy` sets as well.
    """
    var nested = List[List[Float64]]()
    for i in range(n_points):
        var row = List[Float64]()
        for t in range(n_obj):
            row.append(f[i * n_obj + t])
        nested.append(row^)
    return nested^


fn mo_reference_point(
    f: List[Float64], n_points: Int, n_obj: Int, margin: Float64
) -> List[Float64]:
    """A hypervolume reference point every solution dominates: nadir + `margin` * range.

    The ideal and nadir points come from the FROZEN `multi_objective.ideal_point` /
    `nadir_point` rather than from a second pair of min/max loops.

    An objective whose range is zero would put the reference exactly ON every solution and
    give a zero-volume box, so its span falls back to `|nadir_j|`, and to 1.0 when that is
    zero too. Both fallbacks are scale-relative, so the reference means the same thing for an
    objective measured in millions as for one measured in units.

    Returns an EMPTY list — never a zero vector — for a rejected input or a non-positive or
    non-finite `margin`: a reference point that does not exist must be absent, and a vector
    of zeros is a perfectly plausible reference somebody would then use.
    """
    var out = List[Float64]()
    if mo_matrix_defect(f, n_points, n_obj) != MODEL_OK:
        return out^
    if not _finite(margin) or margin <= 0.0:
        return out^
    var nested = _nested_rows(f, n_points, n_obj)
    var mask = List[Bool]()
    for _ in range(n_obj):
        mask.append(False)
    var lo = ideal_point(nested, mask)
    var hi = nadir_point(nested, mask)
    if len(lo) != n_obj or len(hi) != n_obj:
        return out^
    for t in range(n_obj):
        var span = hi[t] - lo[t]
        if not (span > 0.0):
            span = fabs(hi[t])
        if not (span > 0.0):
            span = 1.0
        var value = hi[t] + margin * span
        if not _finite(value):
            return List[Float64]()
        out.append(value)
    return out^


# ── hypervolume ───────────────────────────────────────────────────────────────


fn _no_hypervolume(
    status: Int, n_points: Int, n_obj: Int, samples: Int
) -> Hypervolume:
    return Hypervolume(
        status, False, False, 0.0, False, 0.0, 0.0, samples, 0.0, 0.0,
        n_points, n_obj, 0, 0, List[Float64](),
    )


fn _box_volume(
    f: List[Float64], n_obj: Int, i: Int, reference: List[Float64]
) -> Float64:
    """The volume of point `i`'s own dominated box against the reference. Exact.

    Negative edges are impossible here: the reference check has already refused any point
    with a coordinate past it. A non-finite product (an overflow at 64 objectives of 1e300)
    is returned as-is and screened by the caller, not silently clamped.
    """
    var volume: Float64 = 1.0
    for t in range(n_obj):
        volume *= reference[t] - f[i * n_obj + t]
    return volume


fn _hypervolume_2d(
    f: List[Float64], n_obj: Int, front: List[Int], reference: List[Float64]
) -> Float64:
    """Exact hypervolume of a two-objective front by the staircase sweep.

    The rank-0 filter leaves `f0` non-decreasing and `f1` strictly decreasing along the
    order, except for exact DUPLICATES, which the `f1 < best` step drops: a duplicated point
    is non-dominated under the stated convention and would otherwise have its rectangle
    counted twice.

    Each kept point contributes `(ref0 - f0) * (previous f1 - this f1)`, with `previous f1`
    starting at `ref1`. Hand-check: one point (a, b) against (R0, R1) gives the rectangle
    `(R0 - a) * (R1 - b)`, and {(1,3), (2,1)} against (4,4) gives 3*1 + 2*2 = 7, which is
    also 3 + 6 - 2 by inclusion-exclusion.
    """
    var keys = List[Float64]()
    for i in range(len(f) // n_obj):
        keys.append(f[i * n_obj])
    var order = _stable_index_sort(keys, front)
    var total: Float64 = 0.0
    var prev_y = reference[1]
    for t in range(len(order)):
        var i = order[t]
        var y = f[i * n_obj + 1]
        if not (y < prev_y):
            continue
        total += (reference[0] - f[i * n_obj]) * (prev_y - y)
        prev_y = y
    return total


fn hypervolume(
    f: List[Float64], n_points: Int, n_obj: Int,
    reference: List[Float64], samples: Int, seed: UInt64,
) -> Hypervolume:
    """Volume dominated by the point set and bounded by `reference`. Minimising every objective.

    Exact for one or two objectives (`MODEL_OK`, `exact` True). For three or more the status
    is `MO_HV_INEXACT` with `has_value` False, exact `bound_lower` / `bound_upper`, and a
    deterministic Monte-Carlo `estimate` with its `std_error` when `samples > 0`. See
    `Hypervolume`.

    The estimate is CHECKED against the exact bounds this same call computes: a draw outside
    them is clamped into them, its `std_error` widened by the distance moved, and the status
    raised to `MO_HV_ESTIMATE_CLAMPED`. `std_error` is floored at one draw's weight, so zero
    hits never comes back as `0.0 ± 0.0`.

    The estimate's draws are addressed by (sample index, objective index) through
    `determinism.counter_rng`, so the same `seed` gives a bit-identical estimate and no draw
    depends on the order anything was evaluated in.
    """
    var defect = mo_matrix_defect(f, n_points, n_obj)
    if defect != MODEL_OK:
        return _no_hypervolume(defect, n_points, n_obj, samples)
    if len(reference) != n_obj:
        return _no_hypervolume(MODEL_ERR_LENGTH_MISMATCH, n_points, n_obj, samples)
    for t in range(n_obj):
        if not _finite(reference[t]):
            return _no_hypervolume(MODEL_ERR_NON_FINITE_VALUE, n_points, n_obj, samples)
    if samples < 0 or samples > MO_MAX_SAMPLES:
        return _no_hypervolume(MO_ERR_PARAMETER, n_points, n_obj, samples)

    # The reference must be dominated by every solution, or the box edge is negative and the
    # "volume" is a signed quantity nobody asked for. A coordinate exactly EQUAL to the
    # reference is admitted: that box is empty, which is a real answer, and it is counted.
    var degenerate = 0
    for i in range(n_points):
        var touches = False
        for t in range(n_obj):
            var edge = reference[t] - f[i * n_obj + t]
            if edge < 0.0:
                return _no_hypervolume(
                    MO_ERR_REFERENCE_POINT, n_points, n_obj, samples
                )
            if edge == 0.0:
                touches = True
        if touches:
            degenerate += 1

    var front = _rank0_subset(f, n_points, n_obj)
    var m = len(front)

    # Exact bounds, valid for ANY number of objectives. The union of the boxes contains each
    # one (so the largest is a lower bound) and is contained both in the box spanned by the
    # ideal point and the reference and in the sum of the boxes (subadditivity).
    var bound_lower: Float64 = 0.0
    var sum_boxes: Float64 = 0.0
    for t in range(m):
        var v = _box_volume(f, n_obj, front[t], reference)
        if not _finite(v):
            return _no_hypervolume(MODEL_ERR_OVERFLOW, n_points, n_obj, samples)
        if v > bound_lower:
            bound_lower = v
        sum_boxes += v
    if not _finite(sum_boxes):
        return _no_hypervolume(MODEL_ERR_OVERFLOW, n_points, n_obj, samples)

    var nested = _nested_rows(f, n_points, n_obj)
    var mask = List[Bool]()
    for _ in range(n_obj):
        mask.append(False)
    var lo = ideal_point(nested, mask)
    if len(lo) != n_obj:
        return _no_hypervolume(MO_ERR_VERIFICATION_FAILED, n_points, n_obj, samples)
    var span_volume: Float64 = 1.0
    for t in range(n_obj):
        span_volume *= reference[t] - lo[t]
    if not _finite(span_volume):
        return _no_hypervolume(MODEL_ERR_OVERFLOW, n_points, n_obj, samples)
    var bound_upper = sum_boxes
    if span_volume < bound_upper:
        bound_upper = span_volume

    # SELF-CONSISTENCY OF THE MODULE'S OWN TWO REPORTS, asserted rather than assumed. Both
    # bounds are proven, so `bound_lower <= bound_upper` is an identity and not a tolerance
    # question: `bound_lower` is one of `sum_boxes`' own terms and adding a non-negative term
    # never lowers a rounded partial sum, and every box edge `ref_t - f_it` is at most the
    # spanning edge `ref_t - lo_t` with a product that is monotone in each factor. Two proven
    # bounds that crossed would mean one of them is not what it claims, and then a caller can
    # use NEITHER — so no numbers come back at all, on the exact and the estimated path alike.
    if bound_lower > bound_upper:
        return _no_hypervolume(MO_ERR_VERIFICATION_FAILED, n_points, n_obj, samples)

    var ref_copy = List[Float64]()
    for t in range(n_obj):
        ref_copy.append(reference[t])

    if n_obj <= 2:
        var value: Float64
        if n_obj == 1:
            # One objective: the union of nested intervals is the longest of them, which is
            # exactly `bound_lower`. Written out rather than reusing that variable so the
            # self-check below is not comparing a number with itself.
            var best = f[front[0] * n_obj]
            for t in range(m):
                var v1 = f[front[t] * n_obj]
                if v1 < best:
                    best = v1
            value = reference[0] - best
        else:
            value = _hypervolume_2d(f, n_obj, front, reference)
        if not _finite(value):
            return _no_hypervolume(MODEL_ERR_OVERFLOW, n_points, n_obj, samples)
        # The self-check: three numbers from three different pieces of arithmetic. The slop is
        # a rounding budget sized by DBL_EPSILON and the magnitude being judged — never by a
        # caller tolerance, and never by a sum over anything but the two numbers in the one
        # comparison it guards.
        #
        # TWO comparisons, so TWO budgets, each from its own pair. One budget built from
        # `|bound_upper| + |value|` and used for BOTH is the "aggregate over the other items"
        # spelling of the tolerance defect: it looks per-quantity and is not. `bound_upper` is
        # min(spanning box, Σ OVER ALL THE BOXES), so on the `value >= bound_lower` arm — a
        # comparison against ONE box, the largest — the budget was set by a sum over every other
        # box, and it grows with how many points the caller sent. The inflation is bounded, and
        # by exactly the wrong thing: `bound_upper <= Σ boxes <= m * bound_lower`, so at
        # `value ≈ bound_lower` the lower arm's allowance was up to `m` times too wide, i.e. up
        # to `MO_MAX_POINTS * MO_ULP_BUDGET ≈ 2^21` ULPs of the bound it was guarding instead of
        # 1024. Measured on the suite's own three-point staircase {(0,3),(2,2),(3,0)} against
        # (4,4): `bound_lower = 4`, `bound_upper = 12`, so the shared budget was 4.547e-12 where
        # this arm's own is 2.728e-12 — 1.67x at three points, m-fold in general. This is a
        # verification gate, and a gate that widens as the caller adds unrelated points is
        # measuring the wrong thing.
        var lower_slop = MO_ULP_BUDGET * LP_DBL_EPSILON * (fabs(bound_lower) + fabs(value))
        var upper_slop = MO_ULP_BUDGET * LP_DBL_EPSILON * (fabs(bound_upper) + fabs(value))
        if value < bound_lower - lower_slop or value > bound_upper + upper_slop:
            return _no_hypervolume(
                MO_ERR_VERIFICATION_FAILED, n_points, n_obj, samples
            )
        return Hypervolume(
            MODEL_OK, True, True, value, False, 0.0, 0.0, 0, bound_lower, bound_upper,
            n_points, n_obj, m, degenerate, ref_copy^,
        )

    # Three or more objectives: no exact sweep here, so no exact value is claimed. The
    # estimate is a mean of Bernoulli hits over the spanning box, which is why its standard
    # error is reported alongside — a number without one would read as exact.
    if samples > 0:
        var budget = MO_MAX_WORK // n_obj
        if m > 0 and budget // m < samples:
            return _no_hypervolume(MO_ERR_WORK_LIMIT, n_points, n_obj, samples)
    if samples == 0 or m == 0 or not (span_volume > 0.0):
        return Hypervolume(
            MO_HV_INEXACT, False, False, 0.0, False, 0.0, 0.0, samples,
            bound_lower, bound_upper, n_points, n_obj, m, degenerate, ref_copy^,
        )

    var stream = stream_id(MO_STREAM_HYPERVOLUME)
    var hits = 0
    var point = List[Float64]()
    for _ in range(n_obj):
        point.append(0.0)
    for s in range(samples):
        for t in range(n_obj):
            # Coordinates: replication_id = the sample, draw_index = the objective. A pure
            # function of both, so sample 900 is the same point however many samples ran.
            var u = rng_uniform(seed, 0, UInt64(s), 0, 0, stream, UInt64(t))
            point[t] = lo[t] + u * (reference[t] - lo[t])
        var dominated = False
        for t in range(m):
            var i = front[t]
            var covers = True
            for o in range(n_obj):
                if f[i * n_obj + o] > point[o]:
                    covers = False
                    break
            if covers:
                dominated = True
                break
        if dominated:
            hits += 1
    var p = Float64(hits) / Float64(samples)
    var raw = span_volume * p
    var se = span_volume * sqrt(p * (1.0 - p) / Float64(samples))

    # ZERO HITS IS NO MEASUREMENT, NOT A MEASUREMENT OF ZERO. `hits == 0` (and `hits ==
    # samples`) makes the binomial variance estimate exactly 0, so without this the struct
    # would carry `estimate ± 0` — the strongest claim it can make — from the weakest possible
    # evidence, and zero hits is the NORMAL outcome for a front whose dominated region is a
    # small fraction of the spanning box, which is the only case this path serves. Measured:
    # the three-point front {(0,1,1),(1,0,1),(1,1,0)} against a reference of 1.0001 hits a
    # region of 3e-8 zero times in 4096 draws and reported `0.0 ± 0.0` for a volume the same
    # struct proves is at least 1e-8.
    #
    # Each draw carries weight `span_volume / samples`, so that weight is the finest difference
    # this instrument can resolve and the reported error can never be below it. Sized by the
    # measurement's OWN resolution — the sample weight of the very quantity being reported —
    # never by a caller tolerance and never by an aggregate over anything else. It binds only
    # where the expected hit count is around one, which is exactly where the binomial estimate
    # of its own variance stops meaning anything.
    var resolution = span_volume / Float64(samples)
    if se < resolution:
        se = resolution

    # THE ESTIMATE IS CHECKED AGAINST THE EXACT BOUNDS THIS SAME CALL COMPUTED. Both are proven
    # for any number of objectives, so an estimate outside them is known-wrong at the moment it
    # is produced, and ordinary Poisson noise at a few expected hits puts it outside in BOTH
    # directions (measured: 0.0 against a proven `bound_lower` of 1.0e-8, and 0.078125 against
    # a proven `bound_upper` of 0.06 — 82% above it on another seed). The exact path already
    # refuses this shape as `MO_ERR_VERIFICATION_FAILED`; this path has the strictly better
    # option, because the bounds are not just a check but a valid answer on their own.
    #
    # So the estimate is CLAMPED into the proven interval — the clamp can only move it toward
    # the truth, since the truth is inside — the error bar is widened by however far it moved so
    # the raw draw still lies inside `estimate ± std_error` (unless the proven interval is
    # narrower than that distance, in which case the cap below wins: there is no reason to
    # stretch an error bar to cover a number the bounds have already refuted), and the status
    # SAYS the sampler was overridden. A clamp nobody is told about would read as agreement
    # between proof and sample.
    var estimate = raw
    if estimate < bound_lower:
        estimate = bound_lower
    if estimate > bound_upper:
        estimate = bound_upper
    var moved = fabs(estimate - raw)
    if se < moved:
        se = moved
    # And the proven interval bounds the ERROR as well as the estimate: with both the estimate
    # and the true volume inside `[bound_lower, bound_upper]`, no error larger than the width of
    # that interval is possible, so a sampling error bar wider than the width is arithmetic
    # nobody needs. This is the ONLY route to `std_error == 0.0`, and it needs
    # `bound_lower == bound_upper` — the volume proven exactly, where zero uncertainty is a true
    # statement about the proof and not a claim about the sample. A degenerate sample can never
    # reach it, which is the whole point of the floor above.
    var proven_width = bound_upper - bound_lower
    if se > proven_width:
        se = proven_width
    # The budget for the STATUS only, and it is what floating point cannot represent about the
    # two numbers actually being compared: DBL_EPSILON times their own magnitudes, nothing
    # else. A clamp of a few ULPs is arithmetic; a clamp past that is the sampler being refused.
    var clamp_slop = MO_ULP_BUDGET * LP_DBL_EPSILON * (fabs(raw) + fabs(estimate))
    var status = MO_HV_INEXACT
    if moved > clamp_slop:
        status = MO_HV_ESTIMATE_CLAMPED
    return Hypervolume(
        status, False, False, 0.0, True, estimate, se, samples,
        bound_lower, bound_upper, n_points, n_obj, m, degenerate, ref_copy^,
    )


fn hypervolume_default(
    f: List[Float64], n_points: Int, n_obj: Int, reference: List[Float64]
) -> Hypervolume:
    """`hypervolume` with this module's stated default sample count and seed.

    The defaults are constants, not hidden state: a convenience call is still reproducible,
    and `samples` comes back in the result so the estimate says what produced it.
    """
    return hypervolume(
        f, n_points, n_obj, reference, MO_DEFAULT_SAMPLES, MO_DEFAULT_SEED
    )


# ── linear-model plumbing shared by both solvers ──────────────────────────────


fn _linear_defect(
    c: List[Float64], n_obj: Int, n_vars: Int,
    a: List[Float64], rows: Int, senses: List[Int], rhs: List[Float64],
) -> Int:
    """`MODEL_OK` when the k-objective linear model is well formed, else the defect.

    `n_vars` is checked against `len(c)` through `dims_fit`, never trusted: an `n_vars` tied
    to nothing is how a 60-byte request allocated 3.50 GB in this package once.
    """
    if n_obj < 1 or n_obj > MO_MAX_OBJECTIVES:
        return MO_ERR_OBJECTIVE_COUNT
    if not dims_fit(n_obj, n_vars, len(c)):
        return MODEL_ERR_DENSE_SHAPE
    if n_vars < 1:
        return MODEL_ERR_DENSE_SHAPE
    if n_vars > MAX_CSR_DIM or rows > MAX_CSR_DIM:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    if rows < 0:
        return MODEL_ERR_DENSE_SHAPE
    if not dims_fit(rows, n_vars, len(a)):
        return MODEL_ERR_DENSE_SHAPE
    if len(senses) != rows or len(rhs) != rows:
        return MODEL_ERR_LENGTH_MISMATCH
    for t in range(len(c)):
        if not _finite(c[t]):
            return MODEL_ERR_NON_FINITE_COEFFICIENT
    for t in range(len(a)):
        if not _finite(a[t]):
            return MODEL_ERR_NON_FINITE_COEFFICIENT
    for i in range(rows):
        if not _finite(rhs[i]):
            return MODEL_ERR_NON_FINITE_RHS
        var s = senses[i]
        if s != SENSE_LE and s != SENSE_EQ and s != SENSE_GE:
            return MODEL_ERR_SENSE
    return MODEL_OK


fn _row_of(a: List[Float64], n_vars: Int, i: Int) -> List[Float64]:
    var row = List[Float64]()
    for t in range(n_vars):
        row.append(a[i * n_vars + t])
    return row^


fn _row_budget(
    row: List[Float64], x: List[Float64], rhs: Float64, feasibility_tol: Float64
) -> Float64:
    """The slack row `i` gets, from its OWN magnitude and nothing else.

    `feasibility_tol` is the caller's absolute allowance; the second term is a ROUNDING
    allowance sized by DBL_EPSILON times this row's own term magnitudes plus its right-hand
    side. It is deliberately NOT any of:

      * `tol * (1 + Σ_i |b_i|)` over all rows — the worst defect this package has had. A sum
        over rows lets 200 ordinary capacity rows raise the tolerance for an unrelated
        contradictory row without limit, and an infeasible program came back OPTIMAL;
      * `tol * (1 + |b_i|)` per row — still wrong, because the fraction grows with the row's
        magnitude while a real violation does not, so `{x >= 1e9, x <= 1e9 - 1}` (violation
        exactly 1.0) passes at the 1e-9 default;

    and the constants are IMPORTED from `optimization.linear` rather than restated, so a
    point this module calls feasible is a point `linear` calls feasible. The activity term is
    the one difference from `linear`'s form and it is deliberate: what is judged here is a dot
    product recomputed from a caller-supplied point, whose rounding scale is the sum of THAT
    row's term magnitudes — a quantity spanning exactly the row being judged.
    """
    var scale = fabs(rhs)
    for t in range(len(row)):
        scale += fabs(row[t]) * fabs(x[t])
    var budget = feasibility_tol
    if budget < 0.0:
        budget = 0.0
    return budget + MO_ULP_BUDGET * LP_DBL_EPSILON * scale


fn _total_violation(
    a: List[Float64], rows: Int, n_vars: Int, senses: List[Int], rhs: List[Float64],
    x: List[Float64], feasibility_tol: Float64,
) -> Float64:
    """Summed per-row violation of `x`, or `MODEL_VIOLATION_ABSENT` if any row is unmeasurable.

    Each row is judged against its own budget through the frozen-side `model.sense_violation`,
    which is reused rather than re-branching on the three senses. Its -1.0 return means "not
    measurable", and it is propagated rather than folded into the sum, where it would read as
    a small negative violation, i.e. as satisfied.

    The SUM is only ever used to order two INFEASIBLE candidates against each other, never to
    decide whether one is feasible: that decision is per row, in `_max_violation`.
    """
    var total: Float64 = 0.0
    for i in range(rows):
        var row = _row_of(a, n_vars, i)
        var value = vec_dot(row, x)
        if not _finite(value):
            return MODEL_VIOLATION_ABSENT
        var budget = _row_budget(row, x, rhs[i], feasibility_tol)
        var v = sense_violation(value, senses[i], rhs[i], budget)
        if v == MODEL_VIOLATION_ABSENT:
            return MODEL_VIOLATION_ABSENT
        total += v
    return total


fn _max_violation(
    a: List[Float64], rows: Int, n_vars: Int, senses: List[Int], rhs: List[Float64],
    x: List[Float64], feasibility_tol: Float64,
) -> Float64:
    """The largest per-row violation of `x`, or `MODEL_VIOLATION_ABSENT`.

    This is the feasibility verdict: a row is satisfied or it is not, and no aggregate over
    rows is allowed to decide it. 0.0 means every row holds within its own budget.
    """
    var worst: Float64 = 0.0
    for i in range(rows):
        var row = _row_of(a, n_vars, i)
        var value = vec_dot(row, x)
        if not _finite(value):
            return MODEL_VIOLATION_ABSENT
        var budget = _row_budget(row, x, rhs[i], feasibility_tol)
        var v = sense_violation(value, senses[i], rhs[i], budget)
        if v == MODEL_VIOLATION_ABSENT:
            return MODEL_VIOLATION_ABSENT
        if v > worst:
            worst = v
    return worst


fn _augment_box(
    a: List[Float64], rows: Int, n_vars: Int, senses: List[Int], rhs: List[Float64],
    lower: List[Float64], upper: List[Float64],
    mut out_senses: List[Int], mut out_rhs: List[Float64],
) -> List[Float64]:
    """The caller's rows plus one row per finite box bound, as a flat matrix.

    `lp_solve`'s variable convention is `x >= 0`, so a zero lower bound needs no row and a
    positive one becomes a `>=` row; every upper bound becomes a `<=` row. Building the box
    into the LP is what makes the seed points respect the box the GA samples in — a seed
    outside it would be clipped, and a clipped LP optimum is not an optimum.
    """
    var out = List[Float64]()
    for t in range(len(a)):
        out.append(a[t])
    for i in range(rows):
        out_senses.append(senses[i])
        out_rhs.append(rhs[i])
    for j in range(n_vars):
        for t in range(n_vars):
            out.append(1.0 if t == j else 0.0)
        out_senses.append(SENSE_LE)
        out_rhs.append(upper[j])
    for j in range(n_vars):
        if lower[j] > 0.0:
            for t in range(n_vars):
                out.append(1.0 if t == j else 0.0)
            out_senses.append(SENSE_GE)
            out_rhs.append(lower[j])
    return out^


# ── lexicographic optimisation ────────────────────────────────────────────────


fn _no_lex(
    status: Int, n_vars: Int, n_obj: Int, stages: Int, failed: Int, stage_status: Int,
    var optima: List[Float64], var slack: List[Float64], var locked: List[Bool],
) -> LexResult:
    """No solution, but the stages that DID solve keep their proven optima."""
    return LexResult(
        status, False, False, n_vars, n_obj, stages, failed, stage_status, 0, 0.0,
        List[Float64](), optima^, slack^, locked^, List[Float64](),
    )


# PACKING IS LOAD-BEARING: `mojo_inventory` matches a signature inside a NINE-line lookahead
# and drops the function from the contract and from dispatch silently when it does not close
# in time. Six lines here leaves three of headroom; do not spread these one per line.
fn lexicographic_linear(
    c: List[Float64], n_obj: Int, n_vars: Int, a: List[Float64], rows: Int,
    senses: List[Int], rhs: List[Float64], tolerance: Float64,
    max_iterations: Int, feasibility_tol: Float64, optimality_tol: Float64,
) -> LexResult:
    """Minimise objective 0, then 1 subject to 0 staying at its optimum, and so on.

    `c` is row-major `n_obj x n_vars`; objective 0 has the highest priority. Stage `k` is one
    `optimization.linear.lp_solve` call on the caller's rows plus one locked row per earlier
    objective, `c_j·x <= optima[j] + slack[j]`, so the answer is exact and its success status
    is `MODEL_OK` — this is not a heuristic.

    `tolerance` is a RELATIVE slack on each objective's own optimum: `slack[j]` is
    `tolerance * |optima[j]|` plus a DBL_EPSILON-sized rounding allowance on objective `j`'s
    own term magnitudes. A zero `tolerance` still leaves the rounding allowance, so a lock is
    never tighter than floating point can honour, and no other objective's magnitude enters
    it. See `LexResult` for which fields survive each failure.

    `feasibility_tol` and `optimality_tol` are validated HERE, against
    `model.policy_defect`'s one definition, before any solve: an invalid policy is
    `MODEL_ERR_POLICY` on the caller's own argument, never an inner LP that "did something
    inexplicable". Variables are `x >= 0` — `lp_solve`'s convention. Add explicit rows for any
    other box.
    """
    var empty_f = List[Float64]()
    var empty_b = List[Bool]()
    var defect = _linear_defect(c, n_obj, n_vars, a, rows, senses, rhs)
    if defect != MODEL_OK:
        return _no_lex(
            defect, n_vars, n_obj, 0, -1, MODEL_OK,
            empty_f.copy(), empty_f.copy(), empty_b.copy(),
        )
    if not _finite(tolerance) or tolerance < 0.0:
        return _no_lex(
            MO_ERR_PARAMETER, n_vars, n_obj, 0, -1, MODEL_OK,
            empty_f.copy(), empty_f.copy(), empty_b.copy(),
        )
    if max_iterations < 1:
        return _no_lex(
            MO_ERR_PARAMETER, n_vars, n_obj, 0, -1, MODEL_OK,
            empty_f.copy(), empty_f.copy(), empty_b.copy(),
        )
    # THE CALLER'S POLICY IS AN INPUT, AND AN INVALID INPUT IS NOT A SOLVER BREAKDOWN. Without
    # this, a negative `feasibility_tol` reached `lp_solve`, which correctly refused it with
    # `MODEL_ERR_POLICY` — a code that is neither optimal nor infeasible nor unbounded, so the
    # loop below relabelled it `MO_ERR_LP_STAGE_FAILED`, "an inner LP came back inexplicably".
    # MEASURED: `feasibility_tol = -1.0` on a one-row, two-variable model reported status 146
    # with `stage_status = 20`, sending the caller to debug the simplex over their own argument.
    # Validated BEFORE any solve, so the defect is named where it was made.
    #
    # DELEGATED, never restated: `model._policy_parts_defect` reaches `model.policy_defect`,
    # this package's one definition of a policy a solver will honour — including why a zero
    # `optimality_tol` is refused while a zero `feasibility_tol` is admitted. Lexicographic
    # optimisation has no integrality tolerance, so a known-valid default stands in for the
    # field this entry point does not take. `max_iterations` is checked above FIRST and keeps
    # this module's own `MO_ERR_PARAMETER`, so the delegation below only ever answers about the
    # two tolerances; the two rules for it agree (`>= 1`) and the order fixes which name a
    # caller sees.
    var policy_status = _policy_parts_defect(
        max_iterations, feasibility_tol, optimality_tol, DEFAULT_INTEGRALITY_TOL
    )
    if policy_status != MODEL_OK:
        return _no_lex(
            policy_status, n_vars, n_obj, 0, -1, MODEL_OK,
            empty_f.copy(), empty_f.copy(), empty_b.copy(),
        )

    var work_a = List[Float64]()
    for t in range(len(a)):
        work_a.append(a[t])
    var work_senses = List[Int]()
    var work_rhs = List[Float64]()
    for i in range(rows):
        work_senses.append(senses[i])
        work_rhs.append(rhs[i])

    var optima = List[Float64]()
    var slack = List[Float64]()
    var locked = List[Bool]()
    for _ in range(n_obj):
        locked.append(False)
    var x = List[Float64]()
    var iterations = 0
    var stage_rows = rows

    for k in range(n_obj):
        var ck = _row_of(c, n_vars, k)
        var sol = lp_solve(
            ck, 0.0, work_a, stage_rows, n_vars, work_senses, work_rhs, False,
            max_iterations, feasibility_tol, optimality_tol,
        )
        iterations += sol.iterations
        if sol.status == LP_INFEASIBLE:
            # Stage 0 infeasible is the caller's model; a LATER stage infeasible cannot
            # happen mathematically — the previous optimum satisfies its own lock — so it is
            # a tolerance/scaling inconsistency and gets its own code.
            var code = LP_INFEASIBLE if k == 0 else MO_ERR_LEX_LOCK_INFEASIBLE
            return _no_lex(
                code, n_vars, n_obj, k, k, sol.status, optima^, slack^, locked^
            )
        if sol.status == LP_UNBOUNDED:
            # This objective has no minimum, so the lexicographic optimum does not exist. The
            # stages that already solved are still proven and are reported.
            return _no_lex(
                LP_UNBOUNDED, n_vars, n_obj, k, k, sol.status, optima^, slack^, locked^
            )
        if sol.status != LP_OPTIMAL or not sol.has_objective:
            return _no_lex(
                MO_ERR_LP_STAGE_FAILED, n_vars, n_obj, k, k, sol.status,
                optima^, slack^, locked^,
            )

        var value = sol.objective
        x = List[Float64]()
        for t in range(n_vars):
            x.append(sol.x[t])
        # The lock's rounding allowance is sized by THIS objective's own term magnitudes.
        var own_scale = fabs(value)
        for t in range(n_vars):
            own_scale += fabs(ck[t]) * fabs(x[t])
        var room = tolerance * fabs(value) + MO_ULP_BUDGET * LP_DBL_EPSILON * own_scale
        optima.append(value)
        slack.append(room)
        if k + 1 < n_obj:
            # `locked[k]` means "a lock row for objective k is in the final program", so the
            # LAST objective is not locked: nothing is optimised after it. Its `optima` and
            # `slack` are reported all the same, because its optimum is equally proven — the
            # flag is about the program, not about the strength of the answer.
            locked[k] = True
            for t in range(n_vars):
                work_a.append(ck[t])
            work_senses.append(SENSE_LE)
            work_rhs.append(value + room)
            stage_rows += 1

    # Verification against the caller's own data: every original row, and every lock.
    var verified = True
    var worst = _max_violation(a, rows, n_vars, senses, rhs, x, feasibility_tol)
    if worst == MODEL_VIOLATION_ABSENT or worst > 0.0:
        verified = False
    var deviation: Float64 = 0.0
    var values = List[Float64]()
    for k in range(n_obj):
        var ck2 = _row_of(c, n_vars, k)
        var v = vec_dot(ck2, x)
        if not _finite(v):
            return _no_lex(
                MODEL_ERR_NON_FINITE_VALUE, n_vars, n_obj, n_obj, -1, MODEL_OK,
                optima^, slack^, locked^,
            )
        values.append(v)
        var gap = fabs(v - optima[k])
        if gap > deviation:
            deviation = gap
        # The audit budget is the lock's OWN slack PLUS the per-row budget the simplex itself
        # applied to that lock row. Without the second term the audit demands more of the
        # answer than the solver ever promised, and a large objective fails its own lock: with
        # `opt_0 = -1e9` the lock's slack is 4.547e-4 while `lp_solve` admits a row violation
        # of `feas_tol + 1024 * DBL_EPSILON * |rhs|` = 2.27e-4 on top of it, so `x_0` legally
        # comes back 6.8e-4 below the lock and a CORRECT answer was reported as
        # `MO_ERR_VERIFICATION_FAILED`. Measured, not hypothesised — the suite's
        # magnitude-scaled-slack case is exactly this model.
        #
        # `_row_budget` is the same helper the original rows are judged with, and its scale is
        # this lock row's own magnitude — |rhs| plus this objective's own term magnitudes.
        # Still nothing summed over the other objectives.
        var audit = slack[k] + _row_budget(ck2, x, optima[k] + slack[k], feasibility_tol)
        if gap > audit:
            verified = False
    for t in range(n_vars):
        if x[t] < -feasibility_tol:
            verified = False
    if not verified:
        return _no_lex(
            MO_ERR_VERIFICATION_FAILED, n_vars, n_obj, n_obj, -1, MODEL_OK,
            optima^, slack^, locked^,
        )
    return LexResult(
        MODEL_OK, True, True, n_vars, n_obj, n_obj, -1, MODEL_OK, iterations, deviation,
        x^, optima^, slack^, locked^, values^,
    )


fn lexicographic_linear_default(
    c: List[Float64], n_obj: Int, n_vars: Int, a: List[Float64], rows: Int,
    senses: List[Int], rhs: List[Float64], tolerance: Float64,
) -> LexResult:
    """`lexicographic_linear` with `model.mojo`'s default iteration cap and tolerances."""
    return lexicographic_linear(
        c, n_obj, n_vars, a, rows, senses, rhs, tolerance,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
    )


# ── NSGA-II over a linear model ───────────────────────────────────────────────


fn _no_nsga2(
    status: Int, n_vars: Int, n_obj: Int, stage_status: Int, failed: Int,
    has_ideal: Bool, var ideal: List[Float64],
) -> Nsga2Result:
    """No front. `ideal` survives when the per-objective LPs proved it before the failure."""
    return Nsga2Result(
        status, False, 0, n_vars, n_obj, 0, 0, 0, stage_status, failed,
        has_ideal, 0.0, ideal^, List[Float64](), List[Float64](), List[Float64](),
    )


fn _clip(v: Float64, lo: Float64, hi: Float64) -> Float64:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


# PACKING IS LOAD-BEARING: six lines, three of headroom under the nine-line lookahead.
fn nsga2_linear(
    c: List[Float64], n_obj: Int, n_vars: Int, a: List[Float64], rows: Int,
    senses: List[Int], rhs: List[Float64], lower: List[Float64], upper: List[Float64],
    pop_size: Int, generations: Int, crossover_p: Float64, mutation_p: Float64,
    max_front: Int, seed: UInt64,
) -> Nsga2Result:
    """NSGA-II over `min C x` subject to `A x {senses} b` and a finite box, deterministically.

    `c` is row-major `n_obj x n_vars`, every objective MINIMISED. `lower` / `upper` must be
    finite and non-negative (`lp_solve`'s `x >= 0` convention), because a genetic algorithm
    samples inside a box and an unbounded box cannot be sampled.

    The status on success is `MO_UNPROVEN`, never `MODEL_OK`, and there is no
    `proven_optimal` field: see `Nsga2Result`. What IS proven is `ideal[j]`, the exact global
    minimum of objective `j` from one `lp_solve` per objective, and hence `ideal_gap[j]`.

    Seeding, and why it makes the outcome honest: individual 0 is a zero-objective `lp_solve`
    point, so an empty feasible region is the PROVEN `LP_INFEASIBLE` rather than a search that
    found nothing, and individuals 1..n_obj are the per-objective optima, so the front
    contains genuine extreme points. An objective whose LP is unbounded means the Pareto front
    is unbounded and no finite set of points is that front: `LP_UNBOUNDED`, no front.

    Operators, all keyed (see the module docstring's coordinate layout):
      * binary tournament selection over two keyed permutations per generation, comparing
        (feasible first, then front rank, then crowding with boundary points first, then
        ascending index) — every key deterministic;
      * WHOLE-individual arithmetic crossover, one `alpha` per child. A per-COORDINATE alpha
        would break feasibility: blending (1,0) and (0,1) coordinate-wise can produce (1,1),
        which violates `x + y <= 1` that both parents satisfy. One alpha keeps the child on
        the segment between its parents, so a convex feasible region keeps every child in it;
      * per-variable uniform mutation of `MO_MUTATION_SCALE` of that variable's OWN range,
        clipped into the box. Mutation can leave the linear rows, which is what constrained
        dominance below is for.

    Infeasible individuals never displace feasible ones: ranks are computed over the feasible
    subset with the pure dominance relation, and infeasible individuals are totally ordered
    after all of them by summed violation (Deb's constrained dominance, with the sum used only
    to order two infeasible points and never to call one feasible). Selection is
    (parents + offspring) elitist, so a feasible individual is never lost.

    The COST of the request is bounded, not only its memory: `pop_size * (generations + 1)`
    evaluations at `(2 * rows + n_obj) * n_vars` each, and `n_obj + 1` seed LPs over a
    `(rows + 2 * n_vars) * n_vars` matrix, are both charged against `MO_MAX_WORK` before
    anything is allocated, and a request past either is `MO_ERR_WORK_LIMIT` with no front. A
    population and a generation count that no dimension in the payload bounds are exactly the
    integers a caller can make expensive for free.
    """
    var empty_f = List[Float64]()
    var defect = _linear_defect(c, n_obj, n_vars, a, rows, senses, rhs)
    if defect != MODEL_OK:
        return _no_nsga2(defect, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy())
    if len(lower) != n_vars or len(upper) != n_vars:
        return _no_nsga2(
            MODEL_ERR_LENGTH_MISMATCH, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy()
        )
    for j in range(n_vars):
        if not (_finite(lower[j]) and _finite(upper[j])):
            return _no_nsga2(
                MODEL_ERR_NON_FINITE_BOUND, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy()
            )
        if lower[j] < 0.0:
            return _no_nsga2(
                MILP_BOX_BELOW_ZERO, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy()
            )
        if lower[j] > upper[j]:
            return _no_nsga2(
                MODEL_ERR_BOUNDS_CROSSED, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy()
            )
    if pop_size < 4 or pop_size > MO_MAX_POPULATION or pop_size < n_obj + 2:
        return _no_nsga2(MO_ERR_PARAMETER, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy())
    if generations < 0 or generations > MO_MAX_GENERATIONS:
        return _no_nsga2(MO_ERR_PARAMETER, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy())
    if max_front < 1 or max_front > pop_size:
        return _no_nsga2(MO_ERR_PARAMETER, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy())
    if not (_finite(crossover_p) and crossover_p >= 0.0 and crossover_p <= 1.0):
        return _no_nsga2(MO_ERR_PARAMETER, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy())
    if not (_finite(mutation_p) and mutation_p >= 0.0 and mutation_p <= 1.0):
        return _no_nsga2(MO_ERR_PARAMETER, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy())

    # Resource bounds on the two untied integers. Divisions only: `2 * pop * (n_vars + n_obj)`
    # and `generations * (2*pop)^2 * n_obj` both wrap as multiplies.
    #
    # This one bounds an allocation the PAYLOAD does not: `_augment_box` adds up to two rows
    # per variable, so the seed LP's matrix is `(rows + 2*n_vars) * n_vars` cells while the
    # request only pays for `len(c) = n_obj * n_vars` and `len(a) = rows * n_vars`. Measured:
    # one objective over 6553 variables is a 52 KB payload and a 343 MB matrix, a 6600-fold
    # amplification from a structurally valid request — the `lp_from_arenas` shape exactly.
    # `lp_solve` would refuse the tableau, but only AFTER this file had allocated the matrix,
    # so the check has to be here and it has to be first. The ceiling is `linear`'s own
    # `LP_MAX_TABLEAU_CELLS`, imported: the augmented matrix is what becomes that tableau, and
    # a second area ceiling would drift from it.
    var lp_rows = rows + n_vars + n_vars
    if lp_rows > LP_MAX_TABLEAU_CELLS // n_vars:
        return _no_nsga2(
            MODEL_ERR_DIMENSION_TOO_LARGE, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy()
        )
    # Implied by MO_MAX_POPULATION today (2 * 512 < 2048) and kept anyway: it is the check
    # that has to survive if the population ceiling is ever raised, and the front
    # decomposition below is quadratic in exactly this number.
    var combined = pop_size + pop_size
    if combined > MO_MAX_POINTS:
        return _no_nsga2(
            MODEL_ERR_DIMENSION_TOO_LARGE, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy()
        )
    var slot_budget = (MAX_CSR_DIM // MO_POINT_ARRAYS) // combined
    if n_vars + n_obj > slot_budget:
        return _no_nsga2(
            MODEL_ERR_DIMENSION_TOO_LARGE, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy()
        )
    if not _pair_work_fits(combined, n_obj):
        return _no_nsga2(MO_ERR_WORK_LIMIT, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy())
    if generations > 0:
        var gen_budget = MO_MAX_WORK // n_obj
        gen_budget = gen_budget // combined
        gen_budget = gen_budget // combined
        if gen_budget < generations:
            return _no_nsga2(
                MO_ERR_WORK_LIMIT, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy()
            )

    # BOUNDING MEMORY IS NOT BOUNDING WORK, and everything above this bounds memory or pairs.
    # The dominant cost of the run is the per-individual RE-EVALUATION, which none of those
    # checks can see because none of them mentions `rows` or `n_vars`:
    #
    #   evaluations      = pop_size * (generations + 1)      — one seeded round plus one round
    #                                                          of `pop_size` offspring per
    #                                                          generation, which is exactly what
    #                                                          `Nsga2Result.evaluations` counts
    #   cost per eval    = (2 * rows + n_obj) * n_vars       — `_place` walks every row TWICE
    #                                                          (`_max_violation`, then
    #                                                          `_total_violation`), each walk a
    #                                                          dot product plus a row budget
    #                                                          over `n_vars` terms, and then
    #                                                          `n_obj` objective dot products
    #
    # Measured before this check existed: `n_obj = 2, n_vars = 1000, rows = 1000` — an 8 MB
    # payload, a diagonal inside a box, nothing pathological — cost 658 ms per generation, and
    # `pop_size = 64` with `generations = MO_MAX_GENERATIONS = 4096` was ACCEPTED by the
    # `generations * combined^2 * n_obj` budget above, because that budget never sees a row.
    # That request runs for about 45 minutes in one call; the largest shape the area ceiling
    # still admits runs about 18 hours. Rule 1's outcome — a request the caller cannot tell from
    # a hang, holding every resident dataset in the worker — from a structurally valid payload.
    #
    # So the evaluation cost is charged against the same `MO_MAX_WORK`, by divisions only (the
    # four-way product wraps as a multiply), and `generations + 1` is charged rather than
    # `generations`, because the seeded round happens even at `generations = 0` — which measured
    # 604 ms on its own at `n_vars = rows = 400`. `2 * rows + n_obj` is at least `n_obj >= 1`, so
    # the divisor is never zero, and `2 * rows <= 2^27` cannot wrap.
    var eval_budget = MO_MAX_WORK // n_vars
    eval_budget = eval_budget // (rows + rows + n_obj)
    eval_budget = eval_budget // pop_size
    if eval_budget < generations + 1:
        return _no_nsga2(
            MO_ERR_WORK_LIMIT, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy()
        )

    # The multiplier THIS module puts on top of `lp_solve`: `n_obj + 1` solves of the augmented
    # `lp_rows * n_vars` matrix, one for feasibility and one per objective. `linear` bounds one
    # solve (its area ceiling above, its own iteration cap inside); it cannot bound sixty-five
    # of them, and the number of solves is a caller integer bounded only by `MO_MAX_OBJECTIVES`.
    # What is charged is one pass over the cells per solve — an undercount of the simplex by its
    # iteration count, and stated as such — so this refuses the shape where the SEEDS alone are
    # the unbounded part, e.g. 64 objectives over a matrix at `linear`'s own cell ceiling.
    var seed_budget = MO_MAX_WORK // n_vars
    seed_budget = seed_budget // lp_rows
    if seed_budget < n_obj + 1:
        return _no_nsga2(
            MO_ERR_WORK_LIMIT, n_vars, n_obj, MODEL_OK, -1, False, empty_f.copy()
        )

    # ── the seeds, and with them the feasibility verdict and the proven bound ──
    var box_senses = List[Int]()
    var box_rhs = List[Float64]()
    var box_a = _augment_box(
        a, rows, n_vars, senses, rhs, lower, upper, box_senses, box_rhs
    )
    var box_rows = len(box_rhs)
    var zero_c = List[Float64]()
    for _ in range(n_vars):
        zero_c.append(0.0)
    var feas = lp_solve(
        zero_c, 0.0, box_a, box_rows, n_vars, box_senses, box_rhs, False,
        DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
    )
    if feas.status == LP_INFEASIBLE:
        return _no_nsga2(LP_INFEASIBLE, n_vars, n_obj, feas.status, -1, False, empty_f.copy())
    if feas.status != LP_OPTIMAL:
        return _no_nsga2(
            MO_ERR_LP_STAGE_FAILED, n_vars, n_obj, feas.status, -1, False, empty_f.copy()
        )

    # The LP point is CLIPPED into the box. `lp_solve` satisfies the box rows only within its
    # own per-row budget, so a vertex can sit 1e-12 outside a bound, and the front's box check
    # is exact — an unclipped seed would fail verification for a rounding. The clip's cost is
    # bounded and one-directional: it moves a coordinate by at most that same budget, so a row
    # with very large coefficients could in principle move past this module's row budget and
    # the seed would be judged INFEASIBLE. That direction is a refused front with an honest
    # status, never a wrong front, which is why it is accepted and stated rather than papered
    # over with a looser row test.
    var seeds = List[List[Float64]]()
    var base = List[Float64]()
    for t in range(n_vars):
        base.append(_clip(feas.x[t], lower[t], upper[t]))
    seeds.append(base.copy())
    var ideal = List[Float64]()
    for k in range(n_obj):
        var ck = _row_of(c, n_vars, k)
        var sol = lp_solve(
            ck, 0.0, box_a, box_rows, n_vars, box_senses, box_rhs, False,
            DEFAULT_MAX_ITERATIONS, DEFAULT_FEASIBILITY_TOL, DEFAULT_OPTIMALITY_TOL,
        )
        if sol.status == LP_UNBOUNDED:
            return _no_nsga2(LP_UNBOUNDED, n_vars, n_obj, sol.status, k, False, empty_f.copy())
        if sol.status != LP_OPTIMAL or not sol.has_objective:
            return _no_nsga2(
                MO_ERR_LP_STAGE_FAILED, n_vars, n_obj, sol.status, k, False, empty_f.copy()
            )
        ideal.append(sol.objective)
        var point = List[Float64]()
        for t in range(n_vars):
            point.append(_clip(sol.x[t], lower[t], upper[t]))
        seeds.append(point^)

    var result = _evolve(
        c, n_obj, n_vars, a, rows, senses, rhs, lower, upper, seeds,
        pop_size, generations, crossover_p, mutation_p, max_front, seed, ideal,
    )
    return result^


fn nsga2_linear_default(
    c: List[Float64], n_obj: Int, n_vars: Int, a: List[Float64], rows: Int,
    senses: List[Int], rhs: List[Float64], lower: List[Float64], upper: List[Float64],
    max_front: Int, seed: UInt64,
) -> Nsga2Result:
    """`nsga2_linear` with this module's stated default population, generations and rates."""
    return nsga2_linear(
        c, n_obj, n_vars, a, rows, senses, rhs, lower, upper,
        MO_DEFAULT_POPULATION, MO_DEFAULT_GENERATIONS, MO_DEFAULT_CROSSOVER_P,
        MO_DEFAULT_MUTATION_P, max_front, seed,
    )


fn _objectives_of(
    obj_rows: List[List[Float64]], x: List[Float64], mut out: List[Float64], at: Int
) -> Bool:
    """Write the `k` objective values of `x` into `out[at : at+k]`. False on an overflow.

    The dot product is `linalg.vec_dot`, and the objective rows are extracted ONCE by the
    caller: `pop * generations` evaluations rebuilding them would be the allocation cost of
    the whole search.
    """
    for k in range(len(obj_rows)):
        var v = vec_dot(obj_rows[k], x)
        if not _finite(v):
            return False
        out[at + k] = v
    return True


fn _rank_population(
    fvals: List[Float64], n_obj: Int, count: Int,
    feasible: List[Bool], alive: List[Bool], violation: List[Float64],
    mut rank: List[Int],
) -> Int:
    """Constrained NSGA-II ranks over a population. Returns the number of rank tiers.

    Feasible individuals get ranks `0 .. F-1` from the PURE dominance sort over the feasible
    subset only. Infeasible-but-evaluable individuals are then totally ordered after them by
    ascending summed violation (ties by index), and non-evaluable individuals — an objective
    or an activity that overflowed to a non-finite value — come last of all. A distinct rank
    each means the crowding tie-break never applies to them, which is right: crowding between
    two infeasible points is not a quantity anybody defined.

    Returns -1 if the inner sort reports a dominance cycle (see `_front_ranks`).
    """
    var feasible_idx = List[Int]()
    for i in range(count):
        rank[i] = -1
        if alive[i] and feasible[i]:
            feasible_idx.append(i)
    var tiers = 0
    if len(feasible_idx) > 0:
        var sub_rank = List[Int]()
        for _ in range(len(feasible_idx)):
            sub_rank.append(-1)
        var n_fronts = _front_ranks(fvals, n_obj, feasible_idx, sub_rank)
        if n_fronts < 0:
            return -1
        for t in range(len(feasible_idx)):
            rank[feasible_idx[t]] = sub_rank[t]
        tiers = n_fronts

    var rest = List[Int]()
    for i in range(count):
        if alive[i] and not feasible[i]:
            rest.append(i)
    var order = _stable_index_sort(violation, rest)
    for t in range(len(order)):
        rank[order[t]] = tiers + t
    tiers += len(order)
    for i in range(count):
        if not alive[i]:
            rank[i] = tiers
            tiers += 1
    return tiers


fn _better(
    i: Int, j: Int, rank: List[Int], distance: List[Float64], boundary: List[Bool]
) -> Bool:
    """True when individual `i` wins a tournament against `j`. Total and deterministic.

    Order: smaller rank, then boundary before interior, then larger crowding distance, then
    smaller index. The last clause is what makes it total — without it two identical
    individuals would have an arbitrary winner and the run would stop being reproducible.
    """
    if rank[i] != rank[j]:
        return rank[i] < rank[j]
    if boundary[i] != boundary[j]:
        return boundary[i]
    if distance[i] != distance[j]:
        return distance[i] > distance[j]
    return i < j


# PACKING IS LOAD-BEARING: seven lines, two of headroom. This one is private (the leading
# underscore keeps it out of the contract) but the lookahead does not care.
fn _evolve(
    c: List[Float64], n_obj: Int, n_vars: Int, a: List[Float64], rows: Int,
    senses: List[Int], rhs: List[Float64], lower: List[Float64], upper: List[Float64],
    seeds: List[List[Float64]], pop_size: Int, generations: Int,
    crossover_p: Float64, mutation_p: Float64, max_front: Int, seed: UInt64,
    ideal: List[Float64],
) -> Nsga2Result:
    """The generational loop. Called only by `nsga2_linear`, after all validation."""
    var obj_rows = List[List[Float64]]()
    for k in range(n_obj):
        obj_rows.append(_row_of(c, n_vars, k))

    var stream_init = stream_id(MO_STREAM_INIT)
    var stream_ta = stream_id(MO_STREAM_TOURNAMENT_A)
    var stream_tb = stream_id(MO_STREAM_TOURNAMENT_B)
    var stream_cx = stream_id(MO_STREAM_CROSSOVER)
    var stream_mu = stream_id(MO_STREAM_MUTATION)

    var cap = pop_size + pop_size
    var xs = List[Float64]()
    for _ in range(cap * n_vars):
        xs.append(0.0)
    var fs = List[Float64]()
    for _ in range(cap * n_obj):
        fs.append(0.0)
    var feasible = List[Bool]()
    var alive = List[Bool]()
    var violation = List[Float64]()
    var rank = List[Int]()
    var distance = List[Float64]()
    var boundary = List[Bool]()
    for _ in range(cap):
        feasible.append(False)
        alive.append(False)
        violation.append(0.0)
        rank.append(-1)
        distance.append(0.0)
        boundary.append(False)

    var evaluations = 0
    var point = List[Float64]()
    for _ in range(n_vars):
        point.append(0.0)

    # ── generation 0: the LP seeds, then keyed uniform points in the box ──
    for i in range(pop_size):
        if i < len(seeds):
            for t in range(n_vars):
                point[t] = seeds[i][t]
        else:
            for t in range(n_vars):
                var u = rng_uniform(
                    seed, 0, UInt64(i), 0, 0, stream_init, UInt64(t)
                )
                point[t] = lower[t] + u * (upper[t] - lower[t])
        _place(
            xs, fs, feasible, alive, violation, i, point, obj_rows, n_obj, n_vars,
            a, rows, senses, rhs,
        )
        evaluations += 1

    var count = pop_size
    var generations_run = 0
    for g in range(generations):
        var tiers = _rank_population(fs, n_obj, count, feasible, alive, violation, rank)
        if tiers < 0:
            return _no_nsga2(
                MO_ERR_VERIFICATION_FAILED, n_vars, n_obj, MODEL_OK, -1, True,
                ideal.copy(),
            )
        _crowding_by_tier(fs, n_obj, count, rank, tiers, distance, boundary)

        # Two keyed permutations per generation, offset by generation so their draws never
        # overlap: `permutation_keyed` consumes `pop_size - 1` addresses from its own.
        var offset = UInt64(g * pop_size)
        var perm_a = permutation_keyed(pop_size, seed, stream_ta, offset)
        var perm_b = permutation_keyed(pop_size, seed, stream_tb, offset)
        var parents = List[Int]()
        var half = (pop_size + 1) // 2
        for cix in range(pop_size):
            var t = cix
            var use_a = True
            if cix >= half:
                t = cix - half
                use_a = False
            var s1 = (2 * t) % pop_size
            var s2 = (2 * t + 1) % pop_size
            var i1 = perm_a[s1] if use_a else perm_b[s1]
            var i2 = perm_a[s2] if use_a else perm_b[s2]
            parents.append(i1 if _better(i1, i2, rank, distance, boundary) else i2)

        for cix in range(pop_size):
            var p1 = parents[cix]
            var p2 = parents[(cix + 1) % pop_size]
            # ONE alpha for the whole child: see `nsga2_linear`'s docstring for the (1,0) /
            # (0,1) counterexample that rules out a per-coordinate alpha.
            var u_cx = rng_uniform(
                seed, UInt64(g + 1), UInt64(cix), 0, 0, stream_cx, 0
            )
            var alpha = rng_uniform(
                seed, UInt64(g + 1), UInt64(cix), 0, 0, stream_cx, 1
            )
            for t in range(n_vars):
                var v = xs[p1 * n_vars + t]
                if u_cx < crossover_p:
                    v = alpha * v + (1.0 - alpha) * xs[p2 * n_vars + t]
                # Fixed consumption: two draws per variable whether or not the mutation
                # fires, so no address depends on an earlier decision.
                var u_hit = rng_uniform(
                    seed, UInt64(g + 1), UInt64(cix), 0, 0, stream_mu, UInt64(2 * t)
                )
                var u_mag = rng_uniform(
                    seed, UInt64(g + 1), UInt64(cix), 0, 0, stream_mu, UInt64(2 * t + 1)
                )
                if u_hit < mutation_p:
                    var span = upper[t] - lower[t]
                    v += (2.0 * u_mag - 1.0) * MO_MUTATION_SCALE * span
                point[t] = _clip(v, lower[t], upper[t])
            _place(
                xs, fs, feasible, alive, violation, pop_size + cix, point, obj_rows,
                n_obj, n_vars, a, rows, senses, rhs,
            )
            evaluations += 1

        count = cap
        var tiers2 = _rank_population(fs, n_obj, count, feasible, alive, violation, rank)
        if tiers2 < 0:
            return _no_nsga2(
                MO_ERR_VERIFICATION_FAILED, n_vars, n_obj, MODEL_OK, -1, True,
                ideal.copy(),
            )
        var survivors = _select_by_rank(fs, n_obj, rank, count, tiers2, pop_size)
        var new_xs = List[Float64]()
        var new_fs = List[Float64]()
        var new_feasible = List[Bool]()
        var new_alive = List[Bool]()
        var new_violation = List[Float64]()
        for t in range(len(survivors)):
            var s = survivors[t]
            for j in range(n_vars):
                new_xs.append(xs[s * n_vars + j])
            for k in range(n_obj):
                new_fs.append(fs[s * n_obj + k])
            new_feasible.append(feasible[s])
            new_alive.append(alive[s])
            new_violation.append(violation[s])
        for t in range(len(survivors)):
            for j in range(n_vars):
                xs[t * n_vars + j] = new_xs[t * n_vars + j]
            for k in range(n_obj):
                fs[t * n_obj + k] = new_fs[t * n_obj + k]
            feasible[t] = new_feasible[t]
            alive[t] = new_alive[t]
            violation[t] = new_violation[t]
        count = len(survivors)
        generations_run += 1

    # ── the answer: front 0 of the feasible survivors, verified against the caller ──
    var final_rank = List[Int]()
    for _ in range(count):
        final_rank.append(-1)
    var feasible_idx = List[Int]()
    for i in range(count):
        if alive[i] and feasible[i]:
            feasible_idx.append(i)
    var n_feasible = len(feasible_idx)
    if n_feasible == 0:
        # Unreachable: seed 0 is an `lp_solve` point of the SAME rows, so it is feasible by
        # construction. Reported rather than assumed, because "the search found nothing"
        # under a success status is precisely the lie rule 4 exists to prevent.
        return _no_nsga2(
            MO_ERR_VERIFICATION_FAILED, n_vars, n_obj, MODEL_OK, -1, True, ideal.copy()
        )
    var sub_rank = List[Int]()
    for _ in range(n_feasible):
        sub_rank.append(-1)
    var n_fronts = _front_ranks(fs, n_obj, feasible_idx, sub_rank)
    if n_fronts < 0:
        return _no_nsga2(
            MO_ERR_VERIFICATION_FAILED, n_vars, n_obj, MODEL_OK, -1, True, ideal.copy()
        )
    var front = List[Int]()
    for t in range(n_feasible):
        if sub_rank[t] == 0:
            front.append(feasible_idx[t])

    # Collapse EXACT duplicates — the same decision vector AND the same objective vector.
    # A repeated decision is not a second solution, and keeping it would spend a slot the
    # crowding truncation could give to a distinct point: the seeded population contains the
    # feasibility point and a per-objective optimum that coincide, so this is the common case,
    # not a corner. It is NOT a dominance decision and it does not weaken the stated policy:
    # two DIFFERENT decisions with identical scores both survive, because either might be the
    # one a caller wants.
    var unique = List[Int]()
    for t in range(len(front)):
        var duplicate = False
        for u in range(len(unique)):
            if _same_individual(xs, fs, n_vars, n_obj, front[t], unique[u]):
                duplicate = True
                break
        if not duplicate:
            unique.append(front[t])
    front = unique^

    if len(front) > max_front:
        var dist2 = List[Float64]()
        var bound2 = List[Bool]()
        for _ in range(len(front)):
            dist2.append(0.0)
            bound2.append(False)
        _ = _crowding_for_subset(fs, n_obj, front, dist2, bound2)
        var positions = _crowding_order(front, dist2, bound2)
        var kept = List[Int]()
        for t in range(max_front):
            kept.append(front[positions[t]])
        # Restore ascending index order, so the returned front does not carry the truncation
        # order as if it were meaningful.
        var ordered = List[Int]()
        for i in range(count):
            for t in range(len(kept)):
                if kept[t] == i:
                    ordered.append(i)
        front = ordered^

    var front_x = List[Float64]()
    var front_f = List[Float64]()
    for t in range(len(front)):
        for j in range(n_vars):
            front_x.append(xs[front[t] * n_vars + j])
        for k in range(n_obj):
            front_f.append(fs[front[t] * n_obj + k])

    # Verification 1: every returned point satisfies the CALLER's rows and box, per row.
    var worst: Float64 = 0.0
    for t in range(len(front)):
        var xt = List[Float64]()
        for j in range(n_vars):
            xt.append(front_x[t * n_vars + j])
        var v = _max_violation(a, rows, n_vars, senses, rhs, xt, DEFAULT_FEASIBILITY_TOL)
        if v == MODEL_VIOLATION_ABSENT:
            return _no_nsga2(
                MODEL_ERR_NON_FINITE_VALUE, n_vars, n_obj, MODEL_OK, -1, True,
                ideal.copy(),
            )
        if v > worst:
            worst = v
        for j in range(n_vars):
            if xt[j] < lower[j] or xt[j] > upper[j]:
                return _no_nsga2(
                    MO_ERR_VERIFICATION_FAILED, n_vars, n_obj, MODEL_OK, -1, True,
                    ideal.copy(),
                )
    if worst > 0.0:
        return _no_nsga2(
            MO_ERR_VERIFICATION_FAILED, n_vars, n_obj, MODEL_OK, -1, True, ideal.copy()
        )

    # Verification 2: the returned set is pairwise non-dominated, re-checked on the
    # RETURNED matrix rather than on the population it came from.
    var check = nondominated_sort(front_f, len(front), n_obj)
    if check.status != MODEL_OK or check.n_fronts != 1:
        return _no_nsga2(
            MO_ERR_VERIFICATION_FAILED, n_vars, n_obj, MODEL_OK, -1, True, ideal.copy()
        )

    var gap = List[Float64]()
    for k in range(n_obj):
        var best = front_f[k]
        for t in range(len(front)):
            var v2 = front_f[t * n_obj + k]
            if v2 < best:
                best = v2
        gap.append(best - ideal[k])
    return Nsga2Result(
        MO_UNPROVEN, True, len(front), n_vars, n_obj, generations_run, evaluations,
        n_feasible, MODEL_OK, -1, True, worst, ideal.copy(), gap^, front_x^, front_f^,
    )


fn _same_individual(
    xs: List[Float64], fs: List[Float64], n_vars: Int, n_obj: Int, i: Int, j: Int
) -> Bool:
    """Bit-identical decision AND objective vectors — the same solution twice over."""
    for t in range(n_vars):
        if xs[i * n_vars + t] != xs[j * n_vars + t]:
            return False
    for k in range(n_obj):
        if fs[i * n_obj + k] != fs[j * n_obj + k]:
            return False
    return True


fn _place(
    mut xs: List[Float64], mut fs: List[Float64], mut feasible: List[Bool],
    mut alive: List[Bool], mut violation: List[Float64], slot: Int,
    point: List[Float64], obj_rows: List[List[Float64]], n_obj: Int, n_vars: Int,
    a: List[Float64], rows: Int, senses: List[Int], rhs: List[Float64],
):
    """Store one individual at `slot` and evaluate its objectives and its feasibility.

    `alive` is False when an objective or a row activity came out non-finite. Such an
    individual is never selected and never returned: an overflowed objective is not a score,
    and giving it a large finite value would make it compete on a number nobody computed.
    """
    for t in range(n_vars):
        xs[slot * n_vars + t] = point[t]
    alive[slot] = _objectives_of(obj_rows, point, fs, slot * n_obj)
    if not alive[slot]:
        for k in range(n_obj):
            fs[slot * n_obj + k] = 0.0
        feasible[slot] = False
        violation[slot] = 0.0
        return
    var worst = _max_violation(
        a, rows, n_vars, senses, rhs, point, DEFAULT_FEASIBILITY_TOL
    )
    if worst == MODEL_VIOLATION_ABSENT:
        alive[slot] = False
        feasible[slot] = False
        violation[slot] = 0.0
        return
    feasible[slot] = worst == 0.0
    var total = _total_violation(
        a, rows, n_vars, senses, rhs, point, DEFAULT_FEASIBILITY_TOL
    )
    if total == MODEL_VIOLATION_ABSENT:
        alive[slot] = False
        feasible[slot] = False
        violation[slot] = 0.0
        return
    violation[slot] = total


fn _crowding_by_tier(
    fvals: List[Float64], n_obj: Int, count: Int, rank: List[Int], tiers: Int,
    mut distance: List[Float64], mut boundary: List[Bool],
):
    """Crowding distance within each rank tier, written into the population-wide arrays.

    Per tier, because crowding distance is only defined inside one front — computing it over
    a mixed population would rank a crowded rank-0 point below a lonely rank-3 one.
    """
    for i in range(count):
        distance[i] = 0.0
        boundary[i] = False
    for r in range(tiers):
        var members = List[Int]()
        for i in range(count):
            if rank[i] == r:
                members.append(i)
        if len(members) == 0:
            continue
        var d = List[Float64]()
        var b = List[Bool]()
        for _ in range(len(members)):
            d.append(0.0)
            b.append(False)
        _ = _crowding_for_subset(fvals, n_obj, members, d, b)
        for t in range(len(members)):
            distance[members[t]] = d[t]
            boundary[members[t]] = b[t]


# ── the pairwise relation, as a public driver ────────────────────────────────


fn mo_dominance(
    a: List[Float64], b: List[Float64], n_obj: Int
) -> DominanceCheck:
    """The complete dominance relation between two objective vectors, minimising all.

    Both directions are evaluated twice — once by the flat shim the inner loops use, once by
    the FROZEN `multi_objective.is_dominated` — and a disagreement is
    `MO_ERR_VERIFICATION_FAILED` with every flag cleared. That cross-check is what makes the
    shim a performance detail rather than a second definition of dominance; see the module
    docstring.

    See `DominanceCheck` for why all four cases are reported instead of derived, and for the
    weak/strict distinction the two `*_weakly_dominates_*` flags carry.
    """
    var bad = DominanceCheck(MODEL_OK, n_obj, False, False, False, False, False, False, -1)
    if n_obj < 1 or n_obj > MO_MAX_OBJECTIVES:
        bad.status = MO_ERR_OBJECTIVE_COUNT
        return bad^
    if len(a) < n_obj or len(b) < n_obj:
        bad.status = MODEL_ERR_LENGTH_MISMATCH
        return bad^
    var pair = List[Float64]()
    for t in range(n_obj):
        if not (_finite(a[t]) and _finite(b[t])):
            bad.status = MODEL_ERR_NON_FINITE_VALUE
            return bad^
        pair.append(a[t])
    for t in range(n_obj):
        pair.append(b[t])

    var a_dom = _strictly_dominates(pair, n_obj, 0, 1)
    var b_dom = _strictly_dominates(pair, n_obj, 1, 0)
    if a_dom != _frozen_dominates(pair, n_obj, 0, 1):
        bad.status = MO_ERR_VERIFICATION_FAILED
        return bad^
    if b_dom != _frozen_dominates(pair, n_obj, 1, 0):
        bad.status = MO_ERR_VERIFICATION_FAILED
        return bad^

    var relation = _classify(pair, n_obj, 0, 1)
    var first_difference = -1
    for t in range(n_obj):
        if a[t] != b[t]:
            first_difference = t
            break
    return DominanceCheck(
        MODEL_OK, n_obj, relation == MO_REL_EQUAL, a_dom, b_dom,
        _weakly_dominates(pair, n_obj, 0, 1), _weakly_dominates(pair, n_obj, 1, 0),
        relation == MO_REL_INCOMPARABLE, first_difference,
    )
