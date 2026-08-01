"""
strategy.contract — the package's one vocabulary. Zero Python imports.

Everything more than one module in `strategy` must agree about lives here and nowhere else:
the status codes, the verdict and exactness vocabularies, the ceilings, the work budget, the
named RNG streams, the CRN coordinate assignment, and the flat Policy/Scenario encodings.
Rule 3 applies inside a package: `optimization/` shipped `_finite` six times, byte-identical
and private in every file, and the copies then enforced one declared invariant at three
different strengths under three different codes. One definition, one place.

Finiteness, the tolerance builder and the shape guard are IMPORTED from frozen kernels rather
than re-spelled. `inference.core` owns "is this a real number" and the ulp-widened tolerance;
`sparse_numerics.csr.dims_fit` owns "is this flat buffer that shape". A second definition of
either is how two modules in one answer path end up disagreeing about whether an answer exists.

Why this package exists: common random numbers
----------------------------------------------
Comparing two strategies on independently sampled scenarios measures the sampling noise as much
as the strategies. Comparing them on the SAME scenarios measures only the strategies. That
difference is not stylistic — MEASURED on this tree, at a 64-step horizon over 200 scenarios,
two threshold policies differ with variance 0.254 when paired and 4.748 when unpaired: the
unpaired comparison carries 18.7x the variance of the paired one for identical work.

Pairing is only possible because `determinism.counter_rng` is ADDRESSED rather than sequential.
A draw is a pure function of its coordinates, so two strategies that consume different numbers
of decisions still agree on the value at a given (scenario, step, factor). A stateful generator
cannot do this: the moment one strategy takes one extra draw, every subsequent number diverges
and the comparison silently becomes unpaired while still looking paired.

The CRN coordinate assignment — the load-bearing decision
---------------------------------------------------------
The frozen Philox layout is
    k0 = master_seed   k1 = scenario_id
    c0 = replication_id   c1 = (dim0 << 32) | (dim1 << 16) | stream_id   c2/word = draw_index
and this package binds it as `strat_crn_contract()` records:

    master_seed    the caller's run seed. One comparison, one seed.
    scenario_id    the SCENARIO FAMILY key. Constant across every strategy AND every
                   replication of one comparison. Changing it re-rolls the whole scenario
                   population at the same seed, which is a different question from "one more
                   replication" and therefore must be a different word.
    replication_id THE SCENARIO INDEX. One replication is one sampled scenario.
    dim0           the time step within the horizon.
    dim1           the exogenous factor within a step.
    stream_id      WHICH PROCESS: the scenario tape, a policy's own randomisation, or a
                   tie-break. Derived by NAME, never hardcoded.
    draw_index     the sub-draw inside one (step, factor) cell. Fixed per distribution.

THE STRATEGY INDEX APPEARS IN NO ENVIRONMENT COORDINATE. That single omission is the entire
mechanism: the scenario draw at (step, factor) of scenario `r` is a pure function with no `s`
in it, so every strategy evaluated against scenario `r` reads bit-identical numbers by
construction rather than by convention. The strategy index enters only on the POLICY stream, as
`dim1` — a strategy is the "entity" that slot names — so a randomised strategy's own coin at
step `t` is independent across strategies while the environment at step `t` stays shared.

`replication_id` carries the scenario rather than `scenario_id` for two reasons.
`discrete_event.replicate` already replicates along `replication_id` (`1 .. n_reps`), so a
strategy comparison and a queue validation replicate along the same axis and can share a seed
without either package knowing about the other. And `replication_id` is a COUNTER word, mixed
through all ten Philox rounds from round zero, which is the axis the generator's crush
resistance is exercised on as the incrementing coordinate; the key word is left free to be the
per-comparison constant.

Two guards protect the assignment, because a CRN claim that is only asserted is decoration:

  * `strat_coord_status` refuses a factor index at or above 2^16 and a step at or above 2^32.
    `(dim0 << 32) | (dim1 << 16)` packs both into one word, so a factor of 65536 BLEEDS into
    the step field and two different (step, factor) cells silently alias to the same draw —
    identical numbers where the caller asked for independent ones, with nothing failing.
  * `strat_crn_fold` digests a drawn sequence bit-exactly, so "these two strategies saw the
    same scenario" is a number a suite can compare rather than a sentence in a docstring.
    `STRAT_ERR_CRN_VIOLATED` is what a driver returns when the digests differ.

Bounds, and why there are two kinds
-----------------------------------
`STRAT_MAX_*` bound ALLOCATION. `STRAT_MAX_WORK` bounds OPERATIONS, and they are not the same
check: a request can sit inside every allocation ceiling and still drive a wall-clock minute of
loop iterations, which from the caller's side is indistinguishable from the uncatchable abort
`STRAT_ERR_COUNT` exists to prevent.

The work here is a FOUR-factor product and is charged as one. `n_strategies * n_replications *
horizon` alone is not the work: the per-step policy body also scans the factor vector, and
scenario draws are ~63x more expensive than a policy step. MEASURED on this tree at the
permitted extreme, charging only three factors mis-ranks the shapes by 2.7x, which is the
0.49s-versus-23.89s defect in a different costume. So the charge is

    n_strategies * n_replications * horizon * (1 + n_factors)
  + STRAT_DRAW_WEIGHT * n_replications * horizon * n_factors * draws_per_cell

and every product is grown factor by factor through DIVISION (`strat_product4_fits`), never by
multiplying and comparing: `3 * 6148914691236517206 == 2` in wrapping 64-bit arithmetic, so a
multiply is not a bound at all. `sparse_numerics.csr.dims_fit` is the frozen precedent and
`strat_dims_fit` delegates to it rather than restating it.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64, bool
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: none
benchmark: none
docs: none
version_introduced: 2026.07.31
deprecation_state: active
@endcapability

`golden_vectors`, `benchmark` and `docs` are declared `none` because the files do not exist yet
and a declared artifact that is absent is worse than an undeclared one — it reads as coverage
that was never written. The slice that adds `test_strategy_contract.mojo`, the package benchmark
and the GitBook page replaces these three lines in the same commit that creates them.
"""
from std.math import abs as fabs
from std.memory import bitcast

from determinism.counter_rng import (
    GLOBAL_SENTINEL,
    RESERVED_STREAM_MAX,
    rng_version,
)
from determinism.streams import stream_id
from inference.core import (
    inference_finite,
    inference_scaled_tol,
    inference_scaled_tol_ulps,
)
from sparse_numerics.csr import dims_fit

# ── status codes: strategy owns 450-489 ───────────────────────────────────────
# Enumerated before choosing, because rule 4e's failure mode is one integer with two meanings.
# Claimed elsewhere in this tree: 0-49 shared/graph, hostio 050-099, optimization 080-139,
# determinism 200-229, columnar 300-329, forecasting 300-319, tensorx 300-319, gemm 320-339,
# inference 320-339, evaluation 360-379, data_quality 400-449, discrete_event 400-419,
# canonical 700-709, survival_analysis 900-949. No status constant anywhere in the tree sits
# in 443-699, so this range is free by declaration AND by use.
#
# 450-484 are defined here. 485-489 are HELD for the drivers this contract serves, so a later
# slice extends the vocabulary without guessing at a second range. One code per defect,
# because a caller that gets a refusal needs to know WHICH argument is wrong; a single
# "invalid" would send it looking at all nine.

comptime STRAT_OK: Int = 450
comptime STRAT_ERR_NON_FINITE: Int = 451
comptime STRAT_ERR_EMPTY: Int = 452
comptime STRAT_ERR_COUNT: Int = 453
comptime STRAT_ERR_DIMENSION_TOO_LARGE: Int = 454
comptime STRAT_ERR_WORK_BUDGET: Int = 455
comptime STRAT_ERR_SHAPE: Int = 456
comptime STRAT_ERR_HORIZON_RANGE: Int = 457
comptime STRAT_ERR_SEED_RANGE: Int = 458
comptime STRAT_ERR_FACTOR_RANGE: Int = 459
comptime STRAT_ERR_STREAM_RANGE: Int = 460
comptime STRAT_ERR_TOO_FEW_REPLICATIONS: Int = 461
comptime STRAT_ERR_TOO_FEW_STRATEGIES: Int = 462
comptime STRAT_ERR_POLICY_KIND: Int = 463
comptime STRAT_ERR_POLICY_ARITY: Int = 464
comptime STRAT_ERR_ACTION_RANGE: Int = 465
comptime STRAT_ERR_STATE_RANGE: Int = 466
comptime STRAT_ERR_DISCOUNT_RANGE: Int = 467
comptime STRAT_ERR_PROBABILITY: Int = 468
comptime STRAT_ERR_LEVEL_RANGE: Int = 469
comptime STRAT_ERR_TOLERANCE: Int = 470
comptime STRAT_ERR_NOT_EVALUABLE: Int = 471
comptime STRAT_ERR_NO_ESTIMATE: Int = 472
comptime STRAT_ERR_NOT_CONVERGED: Int = 473
comptime STRAT_ERR_NOT_EXACT: Int = 474
comptime STRAT_ERR_PLAYER_COUNT: Int = 475
comptime STRAT_ERR_PAYOFF_ABSENT: Int = 476
comptime STRAT_ERR_CRN_VIOLATED: Int = 477
comptime STRAT_ERR_DEGENERATE: Int = 478
comptime STRAT_ERR_UNKNOWN_CRITERION: Int = 479
comptime STRAT_ERR_UNKNOWN_STATISTIC: Int = 480
comptime STRAT_ERR_UNKNOWN_METHOD: Int = 481
comptime STRAT_ERR_SCENARIO_RANGE: Int = 482
comptime STRAT_ERR_WEIGHTS: Int = 483
comptime STRAT_ERR_INCOMPARABLE: Int = 484

# ── verdict vocabulary: a RANKING outcome, not a status ───────────────────────
# A tournament that always names a winner is a random number generator with extra steps. The
# indistinguishable case is a FIRST-CLASS outcome here, not the absence of one, which is why
# `STRAT_VERDICT_NO_DIFFERENCE` is a value and not a missing winner. `evaluation.gates` set the
# precedent by separating `decided` from `passed`: three outcomes exist, not two, and a
# comparison that collapses "cannot be decided" into either direction reports a preference it
# never measured.
#
# These are TAGS, small and zero-based, like `EVAL_METRIC_*` and `EVAL_BIN_*`. They are
# deliberately NOT drawn from 450-489: a verdict and a status answer different questions and a
# caller must never be able to read one as the other.

comptime STRAT_VERDICT_UNDECIDED: Int = 0
comptime STRAT_VERDICT_NO_DIFFERENCE: Int = 1
comptime STRAT_VERDICT_A_BETTER: Int = 2
comptime STRAT_VERDICT_B_BETTER: Int = 3
comptime STRAT_VERDICT_COUNT: Int = 4

# ── exactness vocabulary: every equilibrium says which it is ──────────────────
# `game_theory.nash_2x2` solves a 2x2 by indifference equations and is EXACT. An N-player
# general-sum solver is iterative and is not, and the difference must travel with the answer or
# a caller stores an approximation as a fact. An approximate answer additionally carries its
# RESIDUAL; `STRAT_EXACT_APPROXIMATE` with no residual is an admission with no evidence, so a
# driver reporting it also reports `has_residual`.

comptime STRAT_EXACT_UNKNOWN: Int = 0
comptime STRAT_EXACT_CLOSED_FORM: Int = 1
comptime STRAT_EXACT_APPROXIMATE: Int = 2
comptime STRAT_EXACT_COUNT: Int = 3

# ── policy kinds: the flat Policy encoding ────────────────────────────────────
# A Policy cannot be a struct. A public signature may carry only flat types plus structs
# declared in the SAME file, and a struct owned by another module DROPS the function from the
# contract entirely — so a `Policy` struct living here would silently un-export every driver
# that accepted one. The encoding is therefore three flat things:
#
#   kind        which decision rule, from the closed set below
#   params      the flat `n_strategies x arity` row-major parameter block, ONE List[Float64]
#   arity       how wide a row is, which is a FUNCTION of the kind and the environment
#
# `strat_policy_arity` is that function. Making arity computed rather than caller-declared is
# what turns non-negotiable 3 into a guard: a tabular policy quoting more states than the
# environment has is an arity mismatch, refused as `STRAT_ERR_POLICY_ARITY` before any read,
# instead of a subscript past the end of the environment's transition table.

comptime STRAT_POLICY_CONSTANT: Int = 0
comptime STRAT_POLICY_THRESHOLD: Int = 1
comptime STRAT_POLICY_TABULAR: Int = 2
comptime STRAT_POLICY_MIXED: Int = 3
comptime STRAT_POLICY_COUNT: Int = 4

# ── factor distributions, and the FIXED draw count each consumes ──────────────
# `counter_rng`'s contract: "Every distribution consumes a FIXED number of draws. Variable-
# consumption sampling (ziggurat, rejection loops) would make draw_index depend on trajectory
# and reintroduce the coupling this design removes." So the per-cell draw count is a property
# of the distribution alone, `strat_draws_per_cell` is the only place it is written, and the
# normal costs two because Box-Muller reads `draw_index` and `draw_index + 1`.

comptime STRAT_FACTOR_UNIFORM: Int = 0
comptime STRAT_FACTOR_EXPONENTIAL: Int = 1
comptime STRAT_FACTOR_NORMAL: Int = 2
comptime STRAT_FACTOR_BERNOULLI: Int = 3
comptime STRAT_FACTOR_COUNT: Int = 4

# The largest count any distribution above consumes: 2, the normal's Box-Muller pair. This is
# the bound on `draw_index` inside one cell, and it is a SEPARATE constant from
# `STRAT_FACTOR_COUNT` even though both are small integers today. Reusing the kind count as the
# draw bound would be two unrelated quantities sharing one number, which holds exactly until a
# fifth distribution is added or a three-draw one is — and then a `draw_index` of 4 is silently
# accepted, overlapping the next cell's coordinates and returning duplicated draws.
comptime STRAT_MAX_DRAWS_PER_CELL: Int = 2

# ── allocation ceilings ───────────────────────────────────────────────────────
# A full round-robin tournament is the memory driver, not the strategy list: it materialises a
# pairwise block of `n_strategies^2` Float64 = 8 MB at 1024, and a per-pair p-value list of
# `n * (n-1) / 2 = 523776` tests, which sits inside `inference.core.MAX_TESTS` (2^20) so a
# multiplicity correction over every pair is always representable. 1024 strategies in one
# tournament is already far past any real request; 4096 would put the pairwise block at 134 MB
# and the pair count past what `inference.multiplicity` accepts.
comptime STRAT_MAX_STRATEGIES: Int = 1 << 10

# Exactly `DE_MAX_REPLICATIONS`. Deliberate: a strategy comparison and a `discrete_event`
# validation must not disagree about how many replications are representable, or a caller
# sharing one seed across both gets a refusal from one and an answer from the other.
comptime STRAT_MAX_REPLICATIONS: Int = 1 << 12

# The step index becomes `dim0`, which occupies bits 32-63 of the packed coordinate word, so the
# hard limit is 2^32. 2^16 is the practical one: `horizon * n_factors` cells is the scenario
# tape and `horizon` additions is the depth of a discounted sum, whose accumulated rounding
# `strat_scaled_tol_additions` widens a tolerance by.
comptime STRAT_MAX_HORIZON: Int = 1 << 16

# The factor index becomes `dim1`, which occupies bits 16-31 — 16 bits wide. 2^8 leaves eight
# bits of headroom below the point where a factor index would bleed into the step field, and
# `strat_coord_status` refuses the bleed anyway rather than relying on this ceiling alone.
comptime STRAT_MAX_FACTORS: Int = 1 << 8

# The scenario tape: `horizon * n_factors` Float64 = 33.5 MB at the ceiling, one object inside
# the 512 MiB resident-dataset budget `algenta_runtime.session` treats as the outer limit. The
# tape is per-REPLICATION, not per-run: replications are the outer loop and one tape is reused,
# which is what keeps this a ceiling on 2^22 cells rather than on 2^22 * n_replications.
comptime STRAT_MAX_SCENARIO_CELLS: Int = 1 << 22

# The returned per-(strategy, replication) payoff block. Charged as a product because
# `n_strategies` and `n_replications` are each inside their own ceiling at values whose product
# is not: 1024 * 4096 = 2^22 exactly, so the joint cap is the binding one and both must hold.
comptime STRAT_MAX_PAYOFF_CELLS: Int = 1 << 22

# Pairwise comparisons in a round-robin. Matches `inference.core.MAX_TESTS` so a family-wise
# correction over the pairs is representable at every accepted tournament size.
comptime STRAT_MAX_PAIRS: Int = 1 << 20

# The tabular-MDP composition. `reinforcement.value_iteration` and `policy_evaluation` index
# `rewards[s][a]` and then `V[transitions[s][a]]` with NO bounds check of their own, so a
# transition naming a state the environment lacks is an uncatchable process abort inside a
# frozen kernel. `strat_ints_in_range` is the guard that has to run first, and these are the
# ceilings that keep the flat reward and transition blocks inside one allocation.
comptime STRAT_MAX_STATES: Int = 1 << 14
comptime STRAT_MAX_ACTIONS: Int = 1 << 10
comptime STRAT_MAX_MDP_CELLS: Int = 1 << 20

# An N-player general-sum payoff tensor is `n_actions ^ n_players` cells, so the player count
# is an EXPONENT and cannot be given a generous ceiling. Eight players at two actions each is
# 256 cells; eight at ten is 10^8 and refused by the cell cap, not by this one.
comptime STRAT_MAX_PLAYERS: Int = 8

# ── the work budget ───────────────────────────────────────────────────────────
# One work unit is one policy-step-factor operation. A Philox draw costs 64 of them.
#
# Both numbers are MEASURED on this tree, not assumed: fitting `a * steps + b * factor_ops`
# to two saturated shapes gives 1.66 ns per step and 1.48 ns per factor operation, against
# 93.3 ns for one addressed draw written into a tape. 93.3 / 1.48 = 63.0, rounded UP to 64 so
# the weight over-charges draws rather than under-charging them; an under-charged draw is a
# request that reports a small cost and then runs for a wall-clock minute.
comptime STRAT_DRAW_WEIGHT: Int = 64

# 2^29 units at ~1.6 ns each. MEASURED at four different shapes that each saturate this
# ceiling to within 1.5%: draw-saturated 0.52s, replication-saturated 0.98s, balanced at four
# factors 0.87s, balanced at sixteen factors 0.69s. The worst accepted request is therefore
# under one second, and the spread across shapes is 1.9x rather than the 2.7x that charging
# three of the four factors produced — which is the evidence that the fourth factor belongs in
# the charge.
comptime STRAT_MAX_WORK: Int = 1 << 29

comptime STRAT_DBL_EPSILON: Float64 = 2.220446049250313e-16

# `inference_scaled_tol` returns this for a non-finite or negative magnitude, and every
# `error > tol` test in this package reads it as "refuse".
comptime STRAT_TOL_UNDEFINED: Float64 = -1.0

# Field widths of the packed coordinate word `(dim0 << 32) | (dim1 << 16) | stream_id`. Written
# as constants because `strat_coord_status` refuses at them and the suite asserts the refusal:
# a factor index at 2^16 aliases onto a different step, which is a wrong ANSWER rather than a
# crash and would never surface on its own.
comptime STRAT_DIM0_LIMIT: Int = 1 << 32
comptime STRAT_DIM1_LIMIT: Int = 1 << 16
comptime STRAT_STREAM_LIMIT: Int = 1 << 16

# The 62-bit mask `strat_crn_fold` applies to its digest. A 64-bit fold reinterpreted as a
# signed `Int` can be negative, and a negative digest is indistinguishable from the -1 that
# every other Int-returning helper here uses for "does not exist". Masking to 62 bits keeps the
# digest non-negative and still leaves 4.6e18 distinguishable values.
comptime STRAT_FOLD_MASK: Int = 0x3FFFFFFFFFFFFFFF

comptime STRAT_FOLD_PRIME: UInt64 = 0x100000001B3
comptime STRAT_FOLD_OFFSET: UInt64 = 0xCBF29CE484222325


fn strat_status_name(code: Int) -> String:
    """Name for a status code, so a refusal surfaces the defect and not a bare number."""
    if code == STRAT_OK:
        return "ok"
    if code == STRAT_ERR_NON_FINITE:
        return "non_finite_input"
    if code == STRAT_ERR_EMPTY:
        return "empty_input"
    if code == STRAT_ERR_COUNT:
        return "count_exceeds_list_length"
    if code == STRAT_ERR_DIMENSION_TOO_LARGE:
        return "dimension_above_ceiling"
    if code == STRAT_ERR_WORK_BUDGET:
        return "work_budget_exceeded"
    if code == STRAT_ERR_SHAPE:
        return "flat_block_is_not_that_shape"
    if code == STRAT_ERR_HORIZON_RANGE:
        return "horizon_out_of_range_or_unreachable"
    if code == STRAT_ERR_SEED_RANGE:
        return "seed_or_coordinate_negative"
    if code == STRAT_ERR_FACTOR_RANGE:
        return "factor_index_out_of_range"
    if code == STRAT_ERR_STREAM_RANGE:
        return "stream_id_reserved_or_out_of_range"
    if code == STRAT_ERR_TOO_FEW_REPLICATIONS:
        return "too_few_replications_for_an_interval"
    if code == STRAT_ERR_TOO_FEW_STRATEGIES:
        return "too_few_strategies_to_compare"
    if code == STRAT_ERR_POLICY_KIND:
        return "unknown_policy_kind"
    if code == STRAT_ERR_POLICY_ARITY:
        return "policy_arity_does_not_match_environment"
    if code == STRAT_ERR_ACTION_RANGE:
        return "action_index_outside_action_set"
    if code == STRAT_ERR_STATE_RANGE:
        return "state_index_outside_state_set"
    if code == STRAT_ERR_DISCOUNT_RANGE:
        return "discount_factor_out_of_range"
    if code == STRAT_ERR_PROBABILITY:
        return "probabilities_are_not_a_distribution"
    if code == STRAT_ERR_LEVEL_RANGE:
        return "confidence_level_out_of_range"
    if code == STRAT_ERR_TOLERANCE:
        return "tolerance_negative_or_non_finite"
    if code == STRAT_ERR_NOT_EVALUABLE:
        return "strategy_cannot_be_evaluated_on_this_environment"
    if code == STRAT_ERR_NO_ESTIMATE:
        return "estimate_does_not_exist"
    if code == STRAT_ERR_NOT_CONVERGED:
        return "solver_hit_its_iteration_cap"
    if code == STRAT_ERR_NOT_EXACT:
        return "an_exact_answer_was_required_and_only_an_approximate_one_exists"
    if code == STRAT_ERR_PLAYER_COUNT:
        return "player_count_out_of_range"
    if code == STRAT_ERR_PAYOFF_ABSENT:
        return "payoff_could_not_be_computed"
    if code == STRAT_ERR_CRN_VIOLATED:
        return "strategies_did_not_see_identical_scenarios"
    if code == STRAT_ERR_DEGENERATE:
        return "no_spread_to_test"
    if code == STRAT_ERR_UNKNOWN_CRITERION:
        return "unknown_decision_criterion"
    if code == STRAT_ERR_UNKNOWN_STATISTIC:
        return "unknown_comparison_statistic"
    if code == STRAT_ERR_UNKNOWN_METHOD:
        return "unknown_multiplicity_method"
    if code == STRAT_ERR_SCENARIO_RANGE:
        return "scenario_index_out_of_range"
    if code == STRAT_ERR_WEIGHTS:
        return "objective_weights_invalid"
    if code == STRAT_ERR_INCOMPARABLE:
        return "results_produced_under_different_crn_contracts"
    return "unknown_status"


fn strat_status_is_ok(code: Int) -> Bool:
    """True only for `STRAT_OK`. A named predicate so no caller writes `code == 450`."""
    return code == STRAT_OK


fn strat_verdict_name(verdict: Int) -> String:
    """Name for a ranking verdict. `no_significant_difference` is a real outcome, not a gap."""
    if verdict == STRAT_VERDICT_UNDECIDED:
        return "undecided"
    if verdict == STRAT_VERDICT_NO_DIFFERENCE:
        return "no_significant_difference"
    if verdict == STRAT_VERDICT_A_BETTER:
        return "a_better"
    if verdict == STRAT_VERDICT_B_BETTER:
        return "b_better"
    return "unknown_verdict"


fn strat_verdict_is_decided(verdict: Int) -> Bool:
    """True when a verdict was reached. A tie IS a verdict; `undecided` is the absence of one.

    The distinction that makes non-negotiable 1 checkable: a ranking may legitimately conclude
    that two strategies are indistinguishable, and that conclusion is decided. It may also fail
    to conclude anything — too few replications, a non-finite payoff — and that is not.
    Collapsing the two lets "we could not tell" be reported as "they are the same".
    """
    return (
        verdict == STRAT_VERDICT_NO_DIFFERENCE
        or verdict == STRAT_VERDICT_A_BETTER
        or verdict == STRAT_VERDICT_B_BETTER
    )


fn strat_exactness_name(kind: Int) -> String:
    """Name for an equilibrium's exactness. Every equilibrium this package returns carries one."""
    if kind == STRAT_EXACT_UNKNOWN:
        return "unknown"
    if kind == STRAT_EXACT_CLOSED_FORM:
        return "exact_closed_form"
    if kind == STRAT_EXACT_APPROXIMATE:
        return "approximate_with_residual"
    return "unknown_exactness"


fn strat_policy_kind_name(kind: Int) -> String:
    """Name for a policy kind, so an unknown tag surfaces as a name rather than an integer."""
    if kind == STRAT_POLICY_CONSTANT:
        return "constant_action"
    if kind == STRAT_POLICY_THRESHOLD:
        return "weighted_threshold"
    if kind == STRAT_POLICY_TABULAR:
        return "tabular_state_to_action"
    if kind == STRAT_POLICY_MIXED:
        return "mixed_distribution_over_actions"
    return "unknown_policy_kind"


fn strat_factor_kind_name(kind: Int) -> String:
    """Name for a scenario factor's distribution, each backed by a frozen `counter_rng` draw."""
    if kind == STRAT_FACTOR_UNIFORM:
        return "uniform_01"
    if kind == STRAT_FACTOR_EXPONENTIAL:
        return "exponential"
    if kind == STRAT_FACTOR_NORMAL:
        return "standard_normal"
    if kind == STRAT_FACTOR_BERNOULLI:
        return "bernoulli"
    return "unknown_factor_kind"


fn strat_draws_per_cell(factor_kind: Int) -> Int:
    """How many generator draws one (step, factor) cell of this distribution consumes.

    Two for the normal, because the frozen `rng_normal` is Box-Muller and reads `draw_index`
    and `draw_index + 1`; one for the others. Returns -1 for an unknown kind rather than a
    plausible 1, because a wrong draw count silently overlaps two cells' coordinates and the
    overlap is invisible: both cells still return finite numbers.

    This is the only place the count is written. A driver that hardcoded it would be a second
    definition of the generator's own consumption contract.
    """
    if factor_kind == STRAT_FACTOR_UNIFORM:
        return 1
    if factor_kind == STRAT_FACTOR_EXPONENTIAL:
        return 1
    if factor_kind == STRAT_FACTOR_NORMAL:
        return 2
    if factor_kind == STRAT_FACTOR_BERNOULLI:
        return 1
    return -1


# ── finiteness, absence, tolerance ────────────────────────────────────────────


fn strat_finite(v: Float64) -> Bool:
    """True for a real number — neither NaN nor an infinity.

    A one-line delegation to `inference.core.inference_finite` ON PURPOSE. This package needs
    one name for the predicate its callers see and it must not be a second implementation: the
    moment two spellings exist they can disagree, and "does this answer exist" is exactly the
    question that must not have two answers.
    """
    return inference_finite(v)


fn strat_absent() -> Float64:
    """The value written into a quantity slot whose `has_*` flag is False: exactly 0.0.

    NOT a NaN. The dispatch REFUSES to serialise a non-finite Float64, so a struct field
    holding one turns the whole response into a typed error — one absent payoff would erase
    every present one beside it. So the value slot is always representable and THE FLAG IS THE
    ANSWER. `0.0` on its own would be the silent-wrong-answer this rule exists to prevent: a
    strategy whose payoff is genuinely zero and one whose payoff could not be computed are
    different findings, and non-negotiable "absence is not zero" is exactly that distinction.
    """
    return 0.0


fn strat_scaled_tol(quantity_magnitude: Float64, abs_tol: Float64) -> Float64:
    """`abs_tol + 256 * DBL_EPSILON * |quantity_magnitude|`, from `inference.core`.

    `quantity_magnitude` must be the magnitude of THE ONE QUANTITY BEING JUDGED. Never a sum or
    a maximum over other items (a `sum |b_i|` scale let 200 ordinary rows swallow a flat
    contradiction and an infeasible LP returned OPTIMAL), never a `1 + |x|` floor (an absolute
    allowance of one whole unit dressed as a relative one), and never the caller's tolerance
    multiplied by a magnitude.
    """
    return inference_scaled_tol(quantity_magnitude, abs_tol)


fn strat_scaled_tol_additions(
    quantity_magnitude: Float64, abs_tol: Float64, additions: Int
) -> Float64:
    """The same tolerance, widened by one ulp per floating-point addition that built the value.

    The case this package has: a discounted payoff over a horizon is `horizon` additions deep,
    and two strategies whose payoffs are mathematically identical can differ in the last bits
    purely from the order the terms were accumulated in. That discrepancy genuinely grows with
    the number of additions, so the allowance does too — with the horizon as `additions`, which
    a caller comparing two discounted returns must pass rather than leaving at zero.

    A negative `additions` widens nothing (clamped to zero), so a nonsense count cannot loosen
    a comparison. `optimization.explain` set the precedent and
    `inference.core.inference_scaled_tol_ulps` is the frozen implementation.
    """
    var extra = additions
    if extra < 0:
        extra = 0
    return inference_scaled_tol_ulps(quantity_magnitude, abs_tol, Float64(extra))


fn strat_agrees(
    quantity: Float64, reference: Float64, abs_tol: Float64, additions: Int
) -> Bool:
    """True when `quantity` equals `reference` within a tolerance built from `quantity` alone.

    `quantity` is the number being judged and is therefore the only magnitude the tolerance may
    come from — not the reference, not a sum over other quantities, not a `1 + |x|` floor.

    Returns FALSE — refuse — when either side is non-finite or the tolerance is undefined. That
    direction is deliberate: a NaN defeats an unvalidated threshold SILENTLY, because
    `gap > nan` is False and an audit then passes having counted zero violations. There is no
    `Float64` this could return instead — an "undefined gap" of 0.0 reads as perfect agreement
    and a negative one reads as inside any tolerance — so the verdict is a `Bool` and the
    caller keeps its own `has_*` flag for whether the comparison was possible at all.
    """
    if not strat_finite(quantity) or not strat_finite(reference):
        return False
    var tol = strat_scaled_tol_additions(quantity, abs_tol, additions)
    if tol < 0.0 or not strat_finite(tol):
        return False
    var d = quantity - reference
    if not strat_finite(d):
        return False
    return fabs(d) <= tol


fn strat_tolerance_status(abs_tol: Float64) -> Int:
    """`STRAT_OK` for a finite, non-negative absolute tolerance; `STRAT_ERR_TOLERANCE` else.

    A negative tolerance makes every comparison fail and a NaN one makes every comparison pass,
    and both look like a working gate from the outside. Checked once, here, so four slices
    cannot each decide differently what a bad tolerance means.
    """
    if not strat_finite(abs_tol) or abs_tol < 0.0:
        return STRAT_ERR_TOLERANCE
    return STRAT_OK


fn strat_level_status(level: Float64) -> Int:
    """`STRAT_OK` for a confidence level strictly inside `(0, 1)`.

    The interval is OPEN on both ends: a 0% interval is a point and a 100% interval is the whole
    line, and neither is a request a ranking can answer. Same convention as
    `discrete_event.replicate`, deliberately, so a caller does not have to remember two rules.
    """
    if not strat_finite(level) or level <= 0.0 or level >= 1.0:
        return STRAT_ERR_LEVEL_RANGE
    return STRAT_OK


fn strat_discount_status(gamma: Float64) -> Int:
    """`STRAT_OK` for a discount factor in `[0, 1]`.

    Closed at both ends: 0.0 is a myopic policy that counts only the current step and 1.0 is an
    undiscounted finite-horizon sum, and both are real requests over a FINITE horizon. Above 1.0
    the discounted sum diverges with the horizon, which is not a large answer but an absent one.
    """
    if not strat_finite(gamma) or gamma < 0.0 or gamma > 1.0:
        return STRAT_ERR_DISCOUNT_RANGE
    return STRAT_OK


# ── list guards: the count is checked BEFORE the first read, every time ───────


fn strat_all_finite(values: List[Float64], n: Int) -> Bool:
    """True when the FIRST `n` entries are all finite, and `n` is a length the list has.

    The count is checked before any read, because `n > len(values)` is not a wrong answer — it
    is an uncatchable bounds abort that takes the whole worker process and every resident
    dataset with it, and `try`/`except` at any layer above does not help. A negative `n` reads
    nothing and is answered True for the empty prefix it names: `range(-3)` is empty, while
    `values[-1]` would abort, which is why this function never subscripts with a caller value.

    @capability strat_all_finite
    complexity: O(n)
    counts:
    - n <= len(values) [kernel_validated]
    @endcapability
    """
    if n > len(values):
        return False
    for i in range(n):
        if not strat_finite(values[i]):
            return False
    return True


fn strat_ints_in_range(values: List[Int], n: Int, lo: Int, hi: Int) -> Bool:
    """True when the first `n` entries all lie in `[lo, hi]`. Count checked before any read.

    This is the guard that stands between a caller and a frozen kernel's unchecked subscript.
    `reinforcement.value_iteration` evaluates `V[transitions[s][a]]` with no range check of its
    own, so a transition naming state 99 in a 10-state MDP is an uncatchable process abort
    inside frozen code that cannot be fixed there. The same applies to an action index used to
    subscript a reward row. Every such block passes through here first, and
    `STRAT_ERR_STATE_RANGE` / `STRAT_ERR_ACTION_RANGE` is what the caller gets instead.

    An empty range (`hi < lo`) is answered False for any `n >= 1` and True for `n <= 0`, which
    is the honest reading: nothing can be inside an empty interval, and no entry was examined.

    @capability strat_ints_in_range
    complexity: O(n)
    counts:
    - n <= len(values) [kernel_validated]
    @endcapability
    """
    if n > len(values):
        return False
    for i in range(n):
        if values[i] < lo or values[i] > hi:
            return False
    return True


fn strat_distribution_status(p: List[Float64], n: Int, abs_tol: Float64) -> Int:
    """`STRAT_OK` when the first `n` entries are a probability distribution.

    Required of a `STRAT_POLICY_MIXED` row and of the state probabilities a
    `decision_analysis` criterion is given. Three separate defects get three separate codes:
    `STRAT_ERR_COUNT` when `n` exceeds the list (checked first, before any read),
    `STRAT_ERR_EMPTY` for a non-positive `n`, `STRAT_ERR_NON_FINITE` for a NaN or infinity, and
    `STRAT_ERR_PROBABILITY` for a negative entry or a total that misses 1.0.

    The sum is judged against 1.0 with a tolerance scaled to 1.0 and widened by one ulp per
    addition, because `n` additions of rounded values do not reach exactly 1.0 and demanding
    that they do would refuse every real distribution. The magnitude is the quantity being
    judged — the total — and never the sum of the absolute entries.

    @capability strat_distribution_status
    complexity: O(n)
    counts:
    - n <= len(p) [kernel_validated]
    @endcapability
    """
    if n > len(p):
        return STRAT_ERR_COUNT
    if n <= 0:
        return STRAT_ERR_EMPTY
    var tol_status = strat_tolerance_status(abs_tol)
    if tol_status != STRAT_OK:
        return tol_status
    var total: Float64 = 0.0
    for i in range(n):
        if not strat_finite(p[i]):
            return STRAT_ERR_NON_FINITE
        if p[i] < 0.0:
            return STRAT_ERR_PROBABILITY
        total += p[i]
    if not strat_finite(total):
        return STRAT_ERR_NON_FINITE
    if not strat_agrees(total, 1.0, abs_tol, n):
        return STRAT_ERR_PROBABILITY
    return STRAT_OK


# ── products, formed by DIVISION so nothing can wrap ──────────────────────────


fn strat_product_fits(a: Int, b: Int, limit: Int) -> Bool:
    """True when `a * b <= limit`, decided WITHOUT forming the product.

    `a * b` is a wrapping 64-bit multiply, so comparing it against a limit is not a bound:
    `3 * 6148914691236517206 == 2` passes any ceiling. Division cannot wrap.
    """
    if a < 0 or b < 0 or limit < 0:
        return False
    if a == 0 or b == 0:
        return True
    return a <= limit // b


fn strat_product3_fits(a: Int, b: Int, c: Int, limit: Int) -> Bool:
    """True when `a * b * c <= limit`, grown factor by factor so no intermediate wraps."""
    if a < 0 or b < 0 or c < 0 or limit < 0:
        return False
    if a == 0 or b == 0 or c == 0:
        return True
    if not strat_product_fits(a, b, limit):
        return False
    return a * b <= limit // c


fn strat_product4_fits(a: Int, b: Int, c: Int, d: Int, limit: Int) -> Bool:
    """True when `a * b * c * d <= limit`, grown factor by factor so no intermediate wraps.

    Four factors because the work in this package is a four-factor product —
    `n_strategies * n_replications * horizon * n_factors` — and a three-factor helper would
    force a caller to form one product itself, which is where the wrap gets reintroduced.
    """
    if a < 0 or b < 0 or c < 0 or d < 0 or limit < 0:
        return False
    if a == 0 or b == 0 or c == 0 or d == 0:
        return True
    if not strat_product3_fits(a, b, c, limit):
        return False
    return a * b * c <= limit // d


fn strat_dims_fit(rows: Int, cols: Int, length: Int) -> Bool:
    """True when `rows` and `cols` are exactly the shape of a `length`-cell flat block.

    Delegates to the FROZEN `sparse_numerics.csr.dims_fit`, which is where this tree's
    division-based shape check already lives and where the wrapping-multiply crash it exists to
    prevent was found. Restating it here would be a second definition of the one guard that
    stands between a flat row-major block and a read far past its end.
    """
    return dims_fit(rows, cols, length)


# ── the flat Policy encoding ──────────────────────────────────────────────────


fn strat_policy_arity(kind: Int, n_factors: Int, n_actions: Int, n_states: Int) -> Int:
    """How many Float64 parameters ONE policy of this kind needs, or -1 for an unknown kind.

    The arity is a FUNCTION of the kind and the environment, never a caller declaration. That
    is what makes non-negotiable 3 a guard rather than a hope: a tabular policy carrying 40
    entries against a 12-state environment is an arity mismatch computed here and refused as
    `STRAT_ERR_POLICY_ARITY`, instead of a subscript into a transition table that does not go
    that far.

      CONSTANT   1                 the action index, stored as a Float64
      THRESHOLD  n_factors + 1     one weight per factor, then the threshold
      TABULAR    n_states          the chosen action for each state
      MIXED      n_actions         a probability per action, validated as a distribution

    Returns -1 for an unknown kind AND for a non-positive environment dimension the kind
    depends on, because an arity of 0 would make every block "the right width" and a block of
    zero-width rows is not a policy. -1 rather than a status code because this answers "how
    wide", and the caller turns the -1 into `STRAT_ERR_POLICY_KIND` or
    `STRAT_ERR_POLICY_ARITY` according to which of its own arguments was at fault.
    """
    if kind == STRAT_POLICY_CONSTANT:
        return 1
    if kind == STRAT_POLICY_THRESHOLD:
        if n_factors <= 0 or n_factors > STRAT_MAX_FACTORS:
            return -1
        return n_factors + 1
    if kind == STRAT_POLICY_TABULAR:
        if n_states <= 0 or n_states > STRAT_MAX_STATES:
            return -1
        return n_states
    if kind == STRAT_POLICY_MIXED:
        if n_actions <= 0 or n_actions > STRAT_MAX_ACTIONS:
            return -1
        return n_actions
    return -1


fn strat_policy_block_status(params: List[Float64], n_strategies: Int, arity: Int) -> Int:
    """`STRAT_OK` when `params` is exactly an `n_strategies x arity` row-major block.

    The one guard every driver taking a flat policy block runs first. `STRAT_ERR_SHAPE` when
    the length is not the product — decided by DIVISION through the frozen `dims_fit`, because
    `n_strategies * arity` is a wrapping multiply and a shape check that wraps is not a check.
    `STRAT_ERR_POLICY_ARITY` for a non-positive arity, which is what `strat_policy_arity`'s -1
    arrives as. `STRAT_ERR_TOO_FEW_STRATEGIES` for a non-positive strategy count, and
    `STRAT_ERR_DIMENSION_TOO_LARGE` above the ceiling. `STRAT_ERR_NON_FINITE` for a NaN or
    infinity anywhere in the block, checked LAST because it is the only O(n) test and there is
    no point scanning a block whose shape is already wrong.

    Row `s` then occupies `params[s * arity .. s * arity + arity)`, and because the shape held,
    every one of those subscripts is inside the list.

    @capability strat_policy_block_status
    complexity: O(n_strategies * arity)
    counts:
    - n_strategies * arity == len(params) [kernel_validated]
    - dim n_strategies <= STRAT_MAX_STRATEGIES [kernel_validated]
    @endcapability
    """
    if arity <= 0:
        return STRAT_ERR_POLICY_ARITY
    if n_strategies <= 0:
        return STRAT_ERR_TOO_FEW_STRATEGIES
    if n_strategies > STRAT_MAX_STRATEGIES:
        return STRAT_ERR_DIMENSION_TOO_LARGE
    if not strat_dims_fit(n_strategies, arity, len(params)):
        return STRAT_ERR_SHAPE
    if not strat_all_finite(params, len(params)):
        return STRAT_ERR_NON_FINITE
    return STRAT_OK


fn strat_policy_row_start(strategy: Int, arity: Int) -> Int:
    """Where strategy `strategy`'s parameter row begins, or -1 if the pair is not addressable.

    Returned rather than left to each call site, so the row-major convention is written once.
    -1 for a negative index or a non-positive arity, and for a product that would wrap: a
    negative subscript is an uncatchable abort, and a wrapped one lands at an arbitrary
    in-range offset and reads another strategy's parameters as this one's — a wrong answer with
    nothing to notice.
    """
    if strategy < 0 or arity <= 0:
        return -1
    if not strat_product_fits(strategy, arity, STRAT_MAX_PAYOFF_CELLS):
        return -1
    return strategy * arity


# ── the flat Scenario encoding ────────────────────────────────────────────────


fn strat_scenario_cells(horizon: Int, n_factors: Int) -> Int:
    """`horizon * n_factors` — the tape size for ONE scenario — or -1 if it does not fit.

    One tape, not `n_replications` of them: replications are the OUTER loop and the tape is
    rewritten in place per replication, which is both what keeps the allocation ceiling at 2^22
    cells and what makes CRN structural — every strategy in the inner loop reads the identical
    `List` object, so "did they see the same scenario" is not a question about coordinates.

    The horizon and factor CEILINGS are checked here as well as the product, because this is the
    call a driver sizes an allocation from. Checking only the product would return a positive,
    plausible 1048576 cells for a horizon of 2^20 at one factor — a tape the driver would fill
    happily and then find `strat_coord_status` refusing every step past 65535, i.e. a size
    accepted here and rejected two calls later.
    """
    if horizon <= 0 or horizon > STRAT_MAX_HORIZON:
        return -1
    if n_factors <= 0 or n_factors > STRAT_MAX_FACTORS:
        return -1
    if not strat_product_fits(horizon, n_factors, STRAT_MAX_SCENARIO_CELLS):
        return -1
    return horizon * n_factors


fn strat_scenario_cell(step: Int, factor: Int, n_factors: Int) -> Int:
    """The row-major tape offset of `(step, factor)`, or -1 when it is not addressable.

    `step * n_factors + factor`. -1 for a negative step or factor, for a factor at or above
    `n_factors`, and for a product that would wrap — each of which is a distinct way to read
    the wrong cell or to abort, and none of which a bare multiply-and-add would notice.
    """
    if step < 0 or factor < 0 or n_factors <= 0:
        return -1
    if factor >= n_factors:
        return -1
    if not strat_product_fits(step, n_factors, STRAT_MAX_SCENARIO_CELLS):
        return -1
    var base = step * n_factors
    if base > STRAT_MAX_SCENARIO_CELLS - factor:
        return -1
    return base + factor


fn strat_scenario_status(tape: List[Float64], horizon: Int, n_factors: Int) -> Int:
    """`STRAT_OK` when `tape` is exactly a `horizon x n_factors` block of finite values.

    `STRAT_ERR_HORIZON_RANGE` for a non-positive horizon or one above the ceiling — which is
    also how "an unreachable horizon" arrives: a request to evaluate over zero steps has no
    payoff to report and is refused rather than scored 0.0. `STRAT_ERR_FACTOR_RANGE` for the
    factor count. `STRAT_ERR_SHAPE` when the length is not the product, by division.
    `STRAT_ERR_NON_FINITE` for a NaN or infinity in the tape, because a non-finite factor
    propagates into every payoff that reads it and the dispatch then refuses the whole response.

    @capability strat_scenario_status
    complexity: O(horizon * n_factors)
    counts:
    - horizon * n_factors == len(tape) [kernel_validated]
    - dim horizon <= STRAT_MAX_HORIZON [kernel_validated]
    @endcapability
    """
    if horizon <= 0 or horizon > STRAT_MAX_HORIZON:
        return STRAT_ERR_HORIZON_RANGE
    if n_factors <= 0 or n_factors > STRAT_MAX_FACTORS:
        return STRAT_ERR_FACTOR_RANGE
    if not strat_dims_fit(horizon, n_factors, len(tape)):
        return STRAT_ERR_SHAPE
    if not strat_all_finite(tape, len(tape)):
        return STRAT_ERR_NON_FINITE
    return STRAT_OK


# ── the CRN coordinate assignment ─────────────────────────────────────────────


fn strat_rng_version() -> String:
    """The frozen generator contract behind every draw, from `determinism.counter_rng`.

    Reported back by every driver so a stored comparison names the generator that produced it.
    A result that cannot be reproduced is not a result. Deterministic, zero-argument.
    """
    return rng_version()


fn strat_crn_contract() -> String:
    """The identifier of THIS package's coordinate assignment. Deterministic, zero-argument.

    `seed:key0,family:key1,scenario:counter0,step:dim0,factor:dim1,process:stream/v1`

    A FUNCTION rather than a comment, for the same reason `discrete_event.de_event_order()` is:
    the assignment IS the reproducibility of every number this package returns, and a stored
    result has to be able to name the rule that produced it. Changing which Philox coordinate
    carries the scenario changes every payoff ever computed here, so the identifier is
    versioned, and `STRAT_ERR_INCOMPARABLE` is what a driver returns when asked to compare two
    results carrying different identifiers.

    Read it as the promise it encodes: the strategy index is absent from the list, which is why
    two strategies at the same seed, family and scenario draw bit-identical numbers.
    """
    return String("seed:key0,family:key1,scenario:counter0,step:dim0,factor:dim1,process:stream/v1")


fn strat_stream_scenario() -> Int:
    """The RNG stream id for scenario (environment) draws.

    Derived by NAME through `determinism.streams.stream_id`, not hardcoded: an integer picked by
    hand collides with whoever picked it first and the two streams silently stop being
    independent, with nothing failing. Returned as `Int` because that is what crosses the wire;
    the generator takes `UInt64` and the conversion is upward from a value the frozen kernel
    guarantees is in [8, 65534].
    """
    return Int(stream_id("strategy.scenario"))


fn strat_stream_policy() -> Int:
    """The RNG stream id a randomised policy's OWN coin flips are drawn on.

    Separate from the scenario stream, and this separation is the reason a mixed strategy does
    not break CRN. If a policy's coin came off the scenario stream it would consume draws the
    environment was going to use, and two strategies with different amounts of randomisation
    would then face different environments — the exact coupling common random numbers exist to
    remove. On its own stream, the strategy index sits in `dim1` and the environment at every
    step is untouched.
    """
    return Int(stream_id("strategy.policy"))


fn strat_stream_tiebreak() -> Int:
    """The RNG stream id for breaking an exact tie between equally-ranked actions.

    Its own stream so that a tie-break, which is a property of the POLICY, never perturbs the
    environment. A tie broken off the scenario stream would make the presence of a tie change
    the future, which is a wrong answer that only appears on inputs with ties in them.
    """
    return Int(stream_id("strategy.tiebreak"))


fn strat_stream_status(stream: Int) -> Int:
    """`STRAT_OK` for a usable stream id: in `[8, 65534]`.

    Ids 1-7 are RESERVED by `counter_rng` — they were handed to named processes by that kernel's
    first consumer, and reusing one silently changes values that consumer already drew. 0xFFFF
    is the global sentinel `dim1` marker. Both are refused with `STRAT_ERR_STREAM_RANGE` rather
    than accepted as ordinary ids, and 0 is refused too: it is the value an uninitialised
    argument has, and a whole package quietly sharing stream 0 is indistinguishable from a
    package with correctly separated streams until someone measures the correlation.
    """
    if stream <= Int(RESERVED_STREAM_MAX):
        return STRAT_ERR_STREAM_RANGE
    if stream >= Int(GLOBAL_SENTINEL):
        return STRAT_ERR_STREAM_RANGE
    if stream >= STRAT_STREAM_LIMIT:
        return STRAT_ERR_STREAM_RANGE
    return STRAT_OK


@fieldwise_init
struct CrnAddress(Copyable, Movable):
    """One resolved set of generator coordinates, with the strategy index conspicuously absent.

    Returned as a value so the coordinate assignment is TESTABLE: a suite asserts known
    coordinates for a known request, and any future edit to the mapping fails that assertion
    instead of quietly renumbering every scenario in the tree. `usable` is False on any refusal
    and every field is then 0, so a caller cannot accidentally draw at a partially-resolved
    address.

    All fields are `Int`, not `UInt64`: these cross the wire, and the generator's conversion
    upward from a validated non-negative `Int` is the direction that cannot surprise anyone. A
    negative `Int` converted to `UInt64` becomes an enormous unsigned coordinate that addresses
    a different stream than the caller asked for, which is why `status` refuses one.
    """

    var status: Int
    var usable: Bool
    var master_seed: Int
    var scenario_family: Int
    var scenario: Int
    var step: Int
    var factor: Int
    var stream: Int
    var draw_index: Int


fn _crn_refusal(code: Int) -> CrnAddress:
    return CrnAddress(code, False, 0, 0, 0, 0, 0, 0, 0)


fn strat_coord_status(
    master_seed: Int, scenario_family: Int, scenario: Int,
    step: Int, factor: Int, stream: Int, draw_index: Int,
) -> Int:
    """`STRAT_OK` when these seven values are a legal address for a Philox draw.

    Six distinct defects, six codes:

      * any coordinate negative -> `STRAT_ERR_SEED_RANGE`. Each is converted to `UInt64`, where
        a negative `Int` wraps to an enormous unsigned value and addresses a stream nobody asked
        for. Nothing fails; the numbers are simply from somewhere else.
      * `step` at or above 2^32 -> `STRAT_ERR_HORIZON_RANGE`, and above the horizon ceiling too.
      * `factor` at or above 2^16 -> `STRAT_ERR_FACTOR_RANGE`. THE SUBTLE ONE: the packed word
        is `(step << 32) | (factor << 16) | stream`, so a factor of 65536 sets bit 32 and lands
        in the STEP field. Cell (0, 65536) then aliases exactly onto (1, 0) and two cells the
        caller believes are independent return identical numbers. A finite, plausible, wrong
        answer — which is why it is refused here and not left to the factor ceiling alone.
      * `stream` reserved, sentinel or too wide -> `STRAT_ERR_STREAM_RANGE`.
      * `scenario` above the replication ceiling -> `STRAT_ERR_SCENARIO_RANGE`.
      * `draw_index` at or above `STRAT_MAX_DRAWS_PER_CELL` -> `STRAT_ERR_DIMENSION_TOO_LARGE`.
        A cell's sub-draws are `0 .. draws_per_cell - 1`, and the largest any distribution here
        consumes is the normal's two. A `draw_index` past that reaches into the coordinates the
        NEXT cell will use, so two cells return the same number and the tape quietly contains
        duplicates.

    @capability strat_coord_status
    complexity: O(1)
    counts: none
    @endcapability
    """
    if master_seed < 0 or scenario_family < 0 or scenario < 0:
        return STRAT_ERR_SEED_RANGE
    if step < 0 or factor < 0 or draw_index < 0:
        return STRAT_ERR_SEED_RANGE
    if step >= STRAT_DIM0_LIMIT or step >= STRAT_MAX_HORIZON:
        return STRAT_ERR_HORIZON_RANGE
    if factor >= STRAT_DIM1_LIMIT or factor >= STRAT_MAX_FACTORS:
        return STRAT_ERR_FACTOR_RANGE
    var stream_status = strat_stream_status(stream)
    if stream_status != STRAT_OK:
        return stream_status
    if scenario >= STRAT_MAX_REPLICATIONS:
        return STRAT_ERR_SCENARIO_RANGE
    if draw_index >= STRAT_MAX_DRAWS_PER_CELL:
        return STRAT_ERR_DIMENSION_TOO_LARGE
    return STRAT_OK


fn strat_crn_address(
    master_seed: Int, scenario_family: Int, scenario: Int,
    step: Int, factor: Int, stream: Int, draw_index: Int,
) -> CrnAddress:
    """Resolve one environment draw's coordinates. THE STRATEGY INDEX IS NOT AN ARGUMENT.

    That omission is the whole design and it is enforced by the signature: there is no way to
    pass a strategy index to an environment draw, so no driver can accidentally make the
    environment depend on which strategy is being evaluated. Two strategies at the same
    `(master_seed, scenario_family, scenario)` therefore address the identical cell at every
    `(step, factor)` and read bit-identical numbers.

    A randomised policy's own coin uses `strat_stream_policy()` and puts the STRATEGY index in
    the `factor` slot — `dim1` is the "which entity" field and a strategy is the entity there —
    so policy randomisation is independent per strategy while the environment stays shared.
    That is the only place a strategy index is ever a coordinate.

    Refuses through `strat_coord_status` and returns `usable = False` with zeroed fields, so a
    partially-resolved address cannot be drawn at.

    @capability strat_crn_address
    complexity: O(1)
    counts: none
    @endcapability
    """
    var status = strat_coord_status(
        master_seed, scenario_family, scenario, step, factor, stream, draw_index
    )
    if status != STRAT_OK:
        return _crn_refusal(status)
    return CrnAddress(
        STRAT_OK, True, master_seed, scenario_family, scenario, step, factor, stream, draw_index
    )


fn strat_crn_fold(values: List[Float64], n: Int) -> Int:
    """A bit-exact digest of the first `n` values, so CRN is MEASURED and not asserted.

    Folds the raw IEEE-754 bits — `bitcast` to `UInt64`, then FNV-1a — so two tapes digest
    equal only if they agree to the last bit. A digest over rounded decimal text, or over
    `Int(v * 2^53)`, would report agreement for tapes that differ in the low mantissa, which is
    exactly the discrepancy an unpaired comparison produces and exactly what this has to catch.
    `columnar.arrow_wire` already compares Float64 columns through `bitcast` for the same
    reason and this is the same shape.

    Returns -1 when `n` exceeds the list — checked before the first read, because a read past
    the end aborts the worker process — and masks the digest to 62 bits otherwise, so a real
    digest is always non-negative and can never be confused with that -1.

    Order-sensitive on purpose: two tapes holding the same multiset of draws in different
    positions are NOT the same scenario, and a commutative digest would call them equal.

    @capability strat_crn_fold
    complexity: O(n)
    counts:
    - n <= len(values) [kernel_validated]
    @endcapability
    """
    if n > len(values):
        return -1
    var acc = STRAT_FOLD_OFFSET
    for i in range(n):
        var bits = bitcast[DType.uint64](values[i])
        # Fold eight bytes at a time, most significant first, so a permutation of the tape
        # cannot produce the same accumulator as the tape itself.
        for byte in range(8):
            var shift = UInt64(56 - 8 * byte)
            acc = acc ^ ((bits >> shift) & 0xFF)
            acc = acc * STRAT_FOLD_PRIME
    return Int(acc) & STRAT_FOLD_MASK


# ── the work budget ───────────────────────────────────────────────────────────


@fieldwise_init
struct WorkBudget(Copyable, Movable):
    """What a request would cost and whether it is allowed, decided before anything runs.

    `fits` is separate from `status` because a refused SHAPE and an over-budget shape are
    different findings: the first cannot be run at any size and the second is a request to make
    smaller. `draw_charge` and `replay_charge` are reported separately so a caller told it is
    over budget can see WHICH factor to reduce — halving the horizon cuts both, halving the
    strategy count cuts only one.

    `total_charge` is -1, not a wrapped product, when the charge does not fit at all. A wrapped
    charge would read as a small cost for an enormous request, which is the failure this whole
    block exists to prevent.
    """

    var status: Int
    var fits: Bool
    var n_strategies: Int
    var n_replications: Int
    var horizon: Int
    var n_factors: Int
    var draws_per_cell: Int
    var draw_charge: Int
    var replay_charge: Int
    var total_charge: Int
    var work_ceiling: Int


fn _budget_refusal(code: Int) -> WorkBudget:
    return WorkBudget(code, False, 0, 0, 0, 0, 0, -1, -1, -1, STRAT_MAX_WORK)


fn strat_shape_status(
    n_strategies: Int, n_replications: Int, horizon: Int, n_factors: Int
) -> Int:
    """`STRAT_OK` when a comparison's four dimensions are each and JOINTLY representable.

    Each against its own ceiling, and then the two products that no single ceiling bounds:
    `n_strategies * n_replications` payoff cells and `horizon * n_factors` tape cells. Both are
    formed by division. 1024 strategies and 4096 replications are each legal and their product
    is exactly the payoff ceiling, so the joint check is the binding one and omitting it would
    let a request inside every stated limit allocate past all of them.

    `n_replications < 2` is `STRAT_ERR_TOO_FEW_REPLICATIONS`, not `STRAT_ERR_EMPTY`: one
    replication has a mean and no interval, and every comparison this package makes is an
    interval. `n_strategies < 1` is `STRAT_ERR_TOO_FEW_STRATEGIES` — a driver that also needs
    two adds that check itself, because evaluating ONE strategy is a legitimate request and
    only RANKING needs a second.

    @capability strat_shape_status
    complexity: O(1)
    counts: none
    @endcapability
    """
    if n_strategies < 1:
        return STRAT_ERR_TOO_FEW_STRATEGIES
    if n_strategies > STRAT_MAX_STRATEGIES:
        return STRAT_ERR_DIMENSION_TOO_LARGE
    if n_replications < 2:
        return STRAT_ERR_TOO_FEW_REPLICATIONS
    if n_replications > STRAT_MAX_REPLICATIONS:
        return STRAT_ERR_DIMENSION_TOO_LARGE
    if horizon < 1 or horizon > STRAT_MAX_HORIZON:
        return STRAT_ERR_HORIZON_RANGE
    if n_factors < 1 or n_factors > STRAT_MAX_FACTORS:
        return STRAT_ERR_FACTOR_RANGE
    if not strat_product_fits(n_strategies, n_replications, STRAT_MAX_PAYOFF_CELLS):
        return STRAT_ERR_DIMENSION_TOO_LARGE
    if not strat_product_fits(horizon, n_factors, STRAT_MAX_SCENARIO_CELLS):
        return STRAT_ERR_DIMENSION_TOO_LARGE
    return STRAT_OK


fn strat_work_charge(
    n_strategies: Int, n_replications: Int, horizon: Int, n_factors: Int, draws_per_cell: Int
) -> Int:
    """The total charge for a comparison, or -1 when it does not fit the budget.

        n_strategies * n_replications * horizon * (1 + n_factors)
      + STRAT_DRAW_WEIGHT * n_replications * horizon * n_factors * draws_per_cell

    Both terms matter and neither alone is the work. Charging only
    `n_strategies * n_replications * horizon` omits the per-step factor scan AND the scenario
    draws, and MEASURED at this tree's ceiling that omission mis-ranks the shapes by 2.7x — the
    same defect as the 0.49s-versus-23.89s pair at an identical declared cost, since a caller
    cannot tell an under-charged request from a hang.

    Every product is grown factor by factor through division, and each partial sum is checked
    against the remaining headroom before it is formed: `a + b` wraps just as `a * b` does, and
    a wrapped total reads as cheap.

    -1 rather than a status code, because a charge is a NUMBER and this is the "no such number"
    answer; `strat_budget` is the call that turns it into `STRAT_ERR_WORK_BUDGET`.
    """
    if draws_per_cell < 1:
        return -1
    var shape = strat_shape_status(n_strategies, n_replications, horizon, n_factors)
    if shape != STRAT_OK:
        return -1

    # replay: n_strategies * n_replications * horizon * (1 + n_factors)
    if not strat_product4_fits(
        n_strategies, n_replications, horizon, 1 + n_factors, STRAT_MAX_WORK
    ):
        return -1
    var replay = n_strategies * n_replications * horizon * (1 + n_factors)

    # draws: STRAT_DRAW_WEIGHT * n_replications * horizon * n_factors * draws_per_cell
    if not strat_product4_fits(
        n_replications, horizon, n_factors, draws_per_cell, STRAT_MAX_WORK
    ):
        return -1
    var cells = n_replications * horizon * n_factors * draws_per_cell
    if not strat_product_fits(STRAT_DRAW_WEIGHT, cells, STRAT_MAX_WORK):
        return -1
    var draws = STRAT_DRAW_WEIGHT * cells

    if replay > STRAT_MAX_WORK - draws:
        return -1
    return replay + draws


fn strat_budget(
    n_strategies: Int, n_replications: Int, horizon: Int, n_factors: Int, draws_per_cell: Int
) -> WorkBudget:
    """The full budget decision for a comparison, with both terms reported separately.

    Refuses BEFORE anything runs, not partway through: a request accepted and then abandoned
    has already spent the time, and from the caller's side a long-running accepted request is
    indistinguishable from the uncatchable abort the count guards exist to prevent.

    `STRAT_ERR_WORK_BUDGET` when the charge exceeds `STRAT_MAX_WORK`; the shape status
    otherwise, so a malformed request gets the code naming its actual defect rather than a
    budget refusal that would send the caller shrinking a dimension that was never the problem.

    @capability strat_budget
    complexity: O(1)
    counts: none
    @endcapability
    """
    if draws_per_cell < 1 or draws_per_cell > STRAT_MAX_DRAWS_PER_CELL:
        return _budget_refusal(STRAT_ERR_DIMENSION_TOO_LARGE)
    var shape = strat_shape_status(n_strategies, n_replications, horizon, n_factors)
    if shape != STRAT_OK:
        return _budget_refusal(shape)
    var total = strat_work_charge(
        n_strategies, n_replications, horizon, n_factors, draws_per_cell
    )
    if total < 0:
        return WorkBudget(
            STRAT_ERR_WORK_BUDGET, False, n_strategies, n_replications, horizon, n_factors,
            draws_per_cell, -1, -1, -1, STRAT_MAX_WORK,
        )
    var replay = n_strategies * n_replications * horizon * (1 + n_factors)
    var draws = total - replay
    return WorkBudget(
        STRAT_OK, True, n_strategies, n_replications, horizon, n_factors, draws_per_cell,
        draws, replay, total, STRAT_MAX_WORK,
    )


fn strat_ceilings() -> List[Int]:
    """Every declared ceiling, in one call, so a caller can size a request before sending it.

    Order is fixed and documented: strategies, replications, horizon, factors, scenario cells,
    payoff cells, pairs, states, actions, MDP cells, players, draw weight, work. Appending a
    new ceiling is additive; reordering is not.
    """
    var out = List[Int]()
    out.append(STRAT_MAX_STRATEGIES)
    out.append(STRAT_MAX_REPLICATIONS)
    out.append(STRAT_MAX_HORIZON)
    out.append(STRAT_MAX_FACTORS)
    out.append(STRAT_MAX_SCENARIO_CELLS)
    out.append(STRAT_MAX_PAYOFF_CELLS)
    out.append(STRAT_MAX_PAIRS)
    out.append(STRAT_MAX_STATES)
    out.append(STRAT_MAX_ACTIONS)
    out.append(STRAT_MAX_MDP_CELLS)
    out.append(STRAT_MAX_PLAYERS)
    out.append(STRAT_DRAW_WEIGHT)
    out.append(STRAT_MAX_WORK)
    return out^
