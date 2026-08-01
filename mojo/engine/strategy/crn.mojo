"""
strategy.crn — common random numbers: the reason this package exists. Zero Python imports.

The one claim, and the measurement that backs it
-----------------------------------------------
Comparing two strategies on independently sampled scenarios measures the sampling noise as much
as it measures the strategies. Comparing them on the SAME scenarios measures only the strategies.
That is not a stylistic preference and it is not asserted here — `crn_pairing_audit` computes both
comparisons on one problem and returns both variances, so the claim is a number a caller can read.

MEASURED on this tree (seed 12345, family 7, 64-step undiscounted horizon, one uniform factor,
threshold policies 0.40 and 0.50 against an act cost of 0.5, 32 scenarios):

    PAIRED   (both policies on the same scenario)  mean 0.3360  variance 0.01615  p = 1.0e-15
    UNPAIRED (policy B on an independent scenario) mean 0.2512  variance 2.81207  p = 0.403
    variance ratio unpaired / paired = 174.1

Identical work, identical seed. The paired comparison ranks the two policies decisively; the
unpaired one cannot tell them apart at all. At 200 scenarios the ratio is 175.4 and the unpaired
comparison finally reaches p = 0.0039 — i.e. pairing bought a factor of ~175 in variance, which is
the same as buying ~175x the scenarios. The two conclusions DIFFER at 32 scenarios, and
`conclusions_differ` is a field rather than a sentence because that is the whole finding.

Why pairing is possible at all
------------------------------
Only because `determinism.counter_rng` is ADDRESSED rather than sequential. From its own
docstring: "every draw is a pure function of its coordinates, so the same logical draw yields the
same value regardless of what a trajectory did beforehand. That is what makes valid common random
numbers possible when compared alternatives consume different numbers of draws." A stateful
generator cannot do this — the moment one strategy takes one extra draw, every subsequent number
diverges and the comparison silently becomes unpaired while still looking paired.

The coordinate assignment is `strategy.contract.strat_crn_contract()` and this module implements
exactly it. THE STRATEGY INDEX IS NOT AN ENVIRONMENT COORDINATE: `crn_scenario_tape` has no
strategy parameter, so there is no way for any driver here to make the environment depend on which
strategy is being evaluated. The strategy index enters only on `strat_stream_policy()`, in the
`dim1` slot, for a randomised (MIXED) policy's own coin — so a mixed strategy's coin is
independent per strategy while the environment at every step stays shared.

Three layers of enforcement, none of them a docstring
----------------------------------------------------
STRUCTURAL. `crn_evaluate_policies` loops scenarios OUTER and strategies INNER over one
materialised tape, so every strategy literally reads the same `List` object. `n_tapes_built` is
returned and equals `n_scenarios`, not `n_scenarios * n_strategies` — a number that would change
if the loop nesting were ever inverted.

MEASURED. `crn_pairing_audit` regenerates the tape SEPARATELY for each of the two strategies and
folds both bit-exactly through `strat_crn_fold`. `n_scenarios_bit_identical` counts the scenarios
where the two folds agreed, and a single disagreement is `STRAT_ERR_CRN_VIOLATED` — not a warning.
Two independent generations rather than one shared object, because the claim being tested is that
generation is a pure function of coordinates with no strategy input, and re-reading one list
cannot test that.

REFUSED. `crn_cell_draw` and every tape build resolve their coordinates through
`strat_coord_status`, which refuses the aliasing case the packed counter word makes possible: a
factor index at 2^16 sets bit 32 and lands in the STEP field, so cell (0, 65536) aliases exactly
onto (1, 0) and two cells the caller believes independent return identical numbers. Finite,
plausible and wrong, and it would never surface on its own.

Independence across scenarios is measured too
---------------------------------------------
A counter-based generator gives independent replications by construction, which is a reason to
believe it and not a reason to skip checking it. `crn_independence_audit` pairs scenario `i` with
scenario `i + lag` over DISJOINT scenario pairs (stride `lag + 1`, so no scenario is used twice and
no draw appears in both vectors), correlates the two draw sequences cell by cell through the frozen
`math_ext.correlation`, and reports the correlation, the sampling-noise scale `1/sqrt(n)`, the
z-score and the two-sided p-value from `inference.core.inference_norm_sf_two_sided`.

MEASURED at seed 999, family 3, 256 disjoint lag-1 pairs of a 64-step two-factor tape:

    32768 draw pairs   r = 0.001233   z = 0.223   noise scale 1/sqrt(n) = 0.00552

The correlation is 0.22 sampling-noise units from zero. Disjoint pairs matter: pooling overlapping
pairs `(i, i+1)` for every `i` would put each scenario in both vectors and the p-value would then
describe a different experiment than the one run.

The environment, stated because a payoff is meaningless without it
-----------------------------------------------------------------
`crn_environment_id()` is a versioned FUNCTION for the same reason `strat_crn_contract()` is: a
stored payoff must be able to name the model that produced it. One step `t` of a scenario is a
vector of `n_factors` exogenous draws `x[t][0..n_factors)`. The environment's value of acting at
step `t` is `v_t = sum_j x[t][j] - cost`, with UNIT weights — that is the environment's, not the
policy's. A policy chooses only whether to act:

    CONSTANT   act iff its single parameter is 1.0 (0.0 and 1.0 are the only legal values)
    THRESHOLD  score_t = sum_j w_j x[t][j]; act iff score_t >= theta. The weights are the
               policy's BELIEF about the factors and are deliberately not the environment's unit
               weights — a policy that mis-weights the factors is exactly the thing a comparison
               is supposed to be able to detect.
    MIXED      act with the row's probability of action 1, drawn on `strat_stream_policy()` at
               (step, strategy), so the coin is independent per strategy and the environment is
               untouched by it
    TABULAR    REFUSED. `STRAT_ERR_NOT_EVALUABLE`: a tabular policy indexes a discrete state and
               this environment has none. That is non-negotiable 3 as a guard — a policy
               referencing a dimension the environment lacks is refused, not scored, and the
               alternative is a subscript into a state table that does not exist.

The payoff of one scenario is `sum_t gamma^t * act_t * v_t`. `gamma = 1.0` is legal (a finite
horizon needs no discount) and so is `gamma = 0.0` (a myopic policy), because
`strat_discount_status` closes the interval at both ends.

Why THIS environment demonstrates the point
-------------------------------------------
With one uniform(0,1) factor and `cost = 0.5`, the exact per-step expected payoff of threshold
`theta` is `integral_theta^1 (x - 0.5) dx = (1 - theta^2)/2 - 0.5(1 - theta)`, maximised at
`theta = 0.5`. So `theta = 0.40` and `theta = 0.50` differ by exactly `0.005` per step — a 4%
effect against a per-step standard deviation of 0.166. That is deliberately small relative to
scenario noise, because that is the regime where pairing decides the comparison and an unpaired
comparison ranks wrong. And `theta = 0.40` versus `theta = 0.60` is an EXACT tie by the same
integral (both 0.12 per step), which is the indistinguishable case a ranking must be able to name.

Absence
-------
A payoff that could not be computed is ABSENT, distinctly from 0.0: `payoff_present` is a parallel
`List[Bool]`, the value slot holds `0.0`, and `n_absent` counts them. A discounted sum can reach a
non-finite total from a legitimate request (an exponential factor at rate 1e-300 gives finite but
enormous draws), and the dispatch REFUSES to serialise a non-finite, so one absent payoff written
as a NaN would turn every present payoff beside it into a typed error.

Bounds and work
---------------
Reading past a `List` end is an uncatchable process abort that `try`/`except` cannot contain, so
no caller count is trusted: shapes are checked by DIVISION through `strat_dims_fit` (the frozen
`sparse_numerics.csr.dims_fit`) before the first read. Bounding memory is not bounding work: the
work is the four-factor product `n_strategies * n_scenarios * horizon * (1 + n_factors)` plus the
weighted scenario draws, charged by `strat_work_charge` BEFORE anything runs. `crn_pairing_audit`
charges THREE tape sets and THREE policy replays, because it deliberately regenerates the tape per
strategy; charging one would be the 0.49s-versus-23.89s defect in a new costume.

One deliberate omission in the declared `counts:` blocks: the `dim <name> <= CEILING` form may only
name a `comptime` constant declared in the SAME file, so that a declared ceiling cannot drift from
the one the kernel tests. Every ceiling this module enforces — `STRAT_MAX_HORIZON`,
`STRAT_MAX_FACTORS`, `STRAT_MAX_REPLICATIONS`, `STRAT_MAX_STRATEGIES` — is owned by
`strategy.contract` and imported, so it cannot be named there. Copying the literal 65536 into a
declaration would be a second definition of the ceiling and a mirror `comptime` here would be a
third; both are the drift the rule exists to prevent. So those dimensions are NOT declared: under-
declaring is honest, and a declaration that can silently disagree with the kernel is worse than
none. The relations that bound a payload — `horizon * n_factors == len(tape)` and
`n_strategies * arity == len(params)` — are declared, checked by division, and complete.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: required
supported_dtypes: float64, int64, bool
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_strategy_crn.mojo
benchmark: benchmarks/mojo_benchmarks/bench_strategy.mojo
docs: gitbook/engine/strategy-simulation.md
version_introduced: 2026.07.31
deprecation_state: active
@endcapability
"""
from std.math import sqrt

from determinism.counter_rng import (
    rng_bernoulli,
    rng_exponential,
    rng_normal,
    rng_uniform,
)
from discrete_event.replicate import replicate_ci_flat
from inference.core import inference_norm_sf_two_sided, inference_t_sf_two_sided
from math_ext import correlation
from stats import compute_mean, compute_variance

from strategy.contract import (
    STRAT_ERR_ACTION_RANGE,
    STRAT_ERR_CRN_VIOLATED,
    STRAT_ERR_DIMENSION_TOO_LARGE,
    STRAT_ERR_FACTOR_RANGE,
    STRAT_ERR_LEVEL_RANGE,
    STRAT_ERR_NON_FINITE,
    STRAT_ERR_NOT_EVALUABLE,
    STRAT_ERR_PAYOFF_ABSENT,
    STRAT_ERR_POLICY_ARITY,
    STRAT_ERR_POLICY_KIND,
    STRAT_ERR_PROBABILITY,
    STRAT_ERR_SCENARIO_RANGE,
    STRAT_ERR_SHAPE,
    STRAT_ERR_TOO_FEW_REPLICATIONS,
    STRAT_ERR_TOO_FEW_STRATEGIES,
    STRAT_ERR_WORK_BUDGET,
    STRAT_FACTOR_BERNOULLI,
    STRAT_FACTOR_EXPONENTIAL,
    STRAT_FACTOR_NORMAL,
    STRAT_FACTOR_UNIFORM,
    STRAT_MAX_FACTORS,
    STRAT_MAX_HORIZON,
    STRAT_MAX_REPLICATIONS,
    STRAT_MAX_SCENARIO_CELLS,
    STRAT_MAX_STRATEGIES,
    STRAT_MAX_WORK,
    STRAT_OK,
    STRAT_POLICY_CONSTANT,
    STRAT_POLICY_MIXED,
    STRAT_POLICY_TABULAR,
    STRAT_POLICY_THRESHOLD,
    strat_budget,
    strat_coord_status,
    strat_crn_contract,
    strat_crn_fold,
    strat_discount_status,
    strat_distribution_status,
    strat_draws_per_cell,
    strat_finite,
    strat_policy_arity,
    strat_policy_block_status,
    strat_policy_row_start,
    strat_product_fits,
    strat_rng_version,
    strat_scenario_cells,
    strat_scenario_status,
    strat_stream_policy,
    strat_stream_scenario,
    strat_work_charge,
)

# ── environment constants ─────────────────────────────────────────────────────
# Two actions: hold and act. The count is a NAMED constant because it is what
# `strat_policy_arity` is given as `n_actions`, and a MIXED policy's row is validated as a
# distribution over exactly this many actions. A literal 2 at three call sites is three places
# for the environment's action space to drift apart.
comptime CRN_N_ACTIONS: Int = 2
comptime CRN_ACTION_HOLD: Int = 0
comptime CRN_ACTION_ACT: Int = 1

# This environment has NO discrete state, which is what makes a TABULAR policy not evaluable
# here. Written as a constant so `strat_policy_arity` is called with the real number rather than
# with a plausible one, and so the refusal below names a fact about the environment.
comptime CRN_N_STATES: Int = 0

# The band inside which `crn_independence_audit` calls a correlation indistinguishable from zero,
# in units of its own sampling-noise scale `1/sqrt(n_draw_pairs)`. Four, not two: the audit pools
# tens of thousands of draw pairs and is meant to be run repeatedly, so a 2-sigma band would flag
# a healthy generator by chance about once in twenty calls. |z| <= 4 is a two-sided normal p of
# 6.3e-5. The z-score and the p-value are BOTH returned, so a caller that wants a different band
# does not have to accept this one.
comptime CRN_INDEP_Z_BAND: Float64 = 4.0


fn crn_contract_id() -> String:
    """The CRN coordinate assignment this module implements. Deterministic, zero-argument.

    Delegates to `strat_crn_contract()` rather than restating the string: two spellings of the
    identifier that names the reproducibility of every number here is exactly the drift that
    would make a stored result unreproducible while still carrying an identifier.

    @capability crn_contract_id
    complexity: O(1)
    counts: none
    @endcapability
    """
    return strat_crn_contract()


fn crn_generator_version() -> String:
    """The frozen generator behind every draw. Deterministic, zero-argument.

    @capability crn_generator_version
    complexity: O(1)
    counts: none
    @endcapability
    """
    return strat_rng_version()


fn crn_environment_id() -> String:
    """The versioned identifier of the payoff model. Deterministic, zero-argument.

    A payoff is meaningless without the environment that produced it, and a stored comparison
    that cannot name its environment cannot be reproduced or compared against a later one. So the
    model is a FUNCTION, not a comment: changing the score, the reward or the discounting changes
    every payoff this module has ever returned, and the identifier changes with it.

    @capability crn_environment_id
    complexity: O(1)
    counts: none
    @endcapability
    """
    return String(
        "value:sum_factors-cost,act:policy,payoff:sum_t gamma^t act_t value_t/v1"
    )


fn crn_scenario_stream() -> Int:
    """The stream every environment draw is made on. Deterministic, zero-argument.

    Delegated from the contract so a suite can assert that the tape really is drawn here and not
    on the policy or tie-break stream — a stream mix-up is invisible in the values themselves.

    @capability crn_scenario_stream
    complexity: O(1)
    counts: none
    @endcapability
    """
    return strat_stream_scenario()


fn crn_policy_stream() -> Int:
    """The stream a MIXED policy's own coin is drawn on. Deterministic, zero-argument.

    Separate from the scenario stream, and that separation is why a randomised policy does not
    break pairing: its coin consumes no coordinate the environment was going to use.

    @capability crn_policy_stream
    complexity: O(1)
    counts: none
    @endcapability
    """
    return strat_stream_policy()


fn crn_policy_arity(policy_kind: Int, n_factors: Int) -> Int:
    """How many Float64 parameters one policy of this kind needs IN THIS ENVIRONMENT, or -1.

    Delegates to `strat_policy_arity` with this environment's own action and state counts, so the
    arity is a function of the environment rather than a caller declaration. `CRN_N_STATES` is 0,
    which is why a TABULAR policy gets -1 here: the environment has no discrete state for a table
    to be indexed by.

      CONSTANT   1              the action index, 0.0 or 1.0
      THRESHOLD  n_factors + 1  one weight per factor, then the threshold
      MIXED      CRN_N_ACTIONS  a probability per action, validated as a distribution
      TABULAR    -1             not evaluable in a stateless environment

    @capability crn_policy_arity
    complexity: O(1)
    counts: none
    @endcapability
    """
    return strat_policy_arity(policy_kind, n_factors, CRN_N_ACTIONS, CRN_N_STATES)


fn crn_factor_status(factor_kind: Int, factor_param: Float64) -> Int:
    """`STRAT_OK` when this factor distribution can be sampled with this parameter.

    `STRAT_ERR_NON_FINITE` for a non-finite `factor_param` under EVERY kind, including the two
    that ignore it. One rule, no per-kind exception: an argument silently ignored for half the
    kinds and load-bearing for the other half is how a caller passes a NaN and gets an answer.

    `STRAT_ERR_NOT_EVALUABLE` for an unknown kind — `strat_draws_per_cell` answers -1 there and a
    -1 draw count would silently overlap two cells' coordinates — and for an exponential rate
    that is not strictly positive. The frozen `rng_exponential` returns 0.0 for `rate <= 0`,
    which is a sentinel that would make every factor of the tape exactly zero while every payoff
    stayed finite and plausible. This package owns no rate-range code and inventing one in a
    driver would be a second vocabulary, so the refusal is the honest "this distribution cannot
    be sampled as requested".

    `STRAT_ERR_PROBABILITY` for a Bernoulli parameter outside `[0, 1]`, which genuinely is a
    probability and has a code of its own.

    @capability crn_factor_status
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not strat_finite(factor_param):
        return STRAT_ERR_NON_FINITE
    if strat_draws_per_cell(factor_kind) < 1:
        return STRAT_ERR_NOT_EVALUABLE
    if factor_kind == STRAT_FACTOR_EXPONENTIAL and factor_param <= 0.0:
        return STRAT_ERR_NOT_EVALUABLE
    if factor_kind == STRAT_FACTOR_BERNOULLI:
        if factor_param < 0.0 or factor_param > 1.0:
            return STRAT_ERR_PROBABILITY
    return STRAT_OK


fn crn_policy_status(policy_kind: Int, n_factors: Int, arity: Int) -> Int:
    """`STRAT_OK` when this policy kind is evaluable here at the declared arity.

    Three distinct refusals, three codes:

      * `STRAT_ERR_NOT_EVALUABLE` for TABULAR. A known, legal policy kind that this environment
        cannot support, because a table is indexed by a discrete state and there is none. Refused
        rather than scored, which is non-negotiable 3: the alternative is a subscript into a
        state dimension the environment lacks.
      * `STRAT_ERR_FACTOR_RANGE` when the ENVIRONMENT's factor count is itself out of range,
        checked before the arity so the code names the caller's actual defect. A THRESHOLD arity
        is `n_factors + 1`, so `n_factors = 0` would otherwise surface as an arity mismatch and
        send the caller adjusting a parameter that was correct.
      * `STRAT_ERR_POLICY_KIND` for a kind outside the closed set.
      * `STRAT_ERR_POLICY_ARITY` when the caller's `arity` is not the one the environment
        computes. The arity is a PARAMETER here only so the shape relation
        `n_strategies * arity == len(params)` is declarable and checkable; it is cross-checked
        against `crn_policy_arity` and a mismatch is refused, so it is still computed rather than
        trusted. A tabular row of 40 entries against a 12-state environment is caught here
        instead of past the end of a transition table.

    @capability crn_policy_status
    complexity: O(1)
    counts: none
    @endcapability
    """
    if n_factors < 1 or n_factors > STRAT_MAX_FACTORS:
        return STRAT_ERR_FACTOR_RANGE
    if policy_kind == STRAT_POLICY_TABULAR:
        return STRAT_ERR_NOT_EVALUABLE
    var expected = crn_policy_arity(policy_kind, n_factors)
    if expected < 0:
        if policy_kind < 0 or policy_kind > STRAT_POLICY_MIXED:
            return STRAT_ERR_POLICY_KIND
        return STRAT_ERR_POLICY_ARITY
    if arity != expected:
        return STRAT_ERR_POLICY_ARITY
    return STRAT_OK


fn crn_request_status(
    n_strategies: Int, n_scenarios: Int, horizon: Int, n_factors: Int,
    factor_kind: Int, factor_param: Float64, policy_kind: Int, arity: Int,
    cost: Float64, gamma: Float64,
) -> Int:
    """`STRAT_OK` when a whole comparison request is answerable. The ONE gate every driver runs.

    Ordered cheapest-first and most-specific-first, so a caller gets the code naming its actual
    defect rather than the first thing that happened to fail: the factor distribution, then the
    policy kind and arity, then the discount, then the cost, then the shape and the work budget
    from `strat_budget` (which is where `STRAT_ERR_TOO_FEW_REPLICATIONS`,
    `STRAT_ERR_DIMENSION_TOO_LARGE` and `STRAT_ERR_WORK_BUDGET` come from).

    `n_scenarios < 2` is `STRAT_ERR_TOO_FEW_REPLICATIONS` and not `STRAT_ERR_EMPTY`: one scenario
    has a payoff and no interval, and every comparison this module makes is an interval.

    @capability crn_request_status
    complexity: O(1)
    counts: none
    @endcapability
    """
    var fs = crn_factor_status(factor_kind, factor_param)
    if fs != STRAT_OK:
        return fs
    var ps = crn_policy_status(policy_kind, n_factors, arity)
    if ps != STRAT_OK:
        return ps
    var ds = strat_discount_status(gamma)
    if ds != STRAT_OK:
        return ds
    if not strat_finite(cost):
        return STRAT_ERR_NON_FINITE
    var budget = strat_budget(
        n_strategies, n_scenarios, horizon, n_factors, strat_draws_per_cell(factor_kind)
    )
    return budget.status


# ── one draw, and one scenario tape ───────────────────────────────────────────


fn _factor_draw(
    seed: UInt64, family: UInt64, scen: UInt64, step: UInt64, factor: UInt64,
    stream: UInt64, factor_kind: Int, factor_param: Float64,
) -> Float64:
    """One exogenous draw at exactly the coordinates `strat_crn_contract()` declares.

    `draw_index` is 0 for every kind; the normal consumes indices 0 AND 1 inside the frozen
    `rng_normal`, which is why `strat_draws_per_cell` answers 2 for it and why the coordinate
    validated by the callers is `draws_per_cell - 1`.

    Precondition: `crn_factor_status` has already accepted `(factor_kind, factor_param)`. There is
    therefore no fall-through branch answering 0.0 for an unknown distribution — the final
    `return 0.0` is the Bernoulli FALSE outcome, a real value, not an absence.
    """
    if factor_kind == STRAT_FACTOR_UNIFORM:
        return rng_uniform(seed, family, scen, step, factor, stream, 0)
    if factor_kind == STRAT_FACTOR_EXPONENTIAL:
        return rng_exponential(seed, family, scen, step, factor, stream, 0, factor_param)
    if factor_kind == STRAT_FACTOR_NORMAL:
        return rng_normal(seed, family, scen, step, factor, stream, 0)
    if rng_bernoulli(seed, family, scen, step, factor, stream, 0, factor_param):
        return 1.0
    return 0.0


@fieldwise_init
struct CellDraw(Copyable, Movable):
    """One resolved and drawn scenario cell, so the coordinate assignment is directly testable.

    `has_value` is False on any refusal and `value` is then exactly 0.0 — never a non-finite,
    because the dispatch refuses to serialise one, and the flag is the answer. 0.0 is also a
    legal uniform draw and a legal Bernoulli outcome, which is precisely why the flag exists
    rather than a sentinel value.
    """

    var status: Int
    var has_value: Bool
    var value: Float64
    var stream: Int
    var draws_per_cell: Int
    var cell: Int


fn crn_cell_draw(
    master_seed: Int, scenario_family: Int, scenario: Int, step: Int, factor: Int,
    n_factors: Int, factor_kind: Int, factor_param: Float64,
) -> CellDraw:
    """One environment draw, addressed through `strat_crn_address`'s own validator.

    THERE IS NO STRATEGY PARAMETER. That omission is the mechanism, and it is enforced by the
    signature rather than by discipline: no caller can make an environment draw depend on which
    strategy is being evaluated because there is nowhere to say which one.

    Every coordinate goes through `strat_coord_status`, so the aliasing case is refused here and
    not left to a ceiling: the packed counter word is `(step << 32) | (factor << 16) | stream`, so
    a factor index of 65536 sets bit 32, lands in the STEP field, and makes cell (0, 65536) return
    the identical number to cell (1, 0). A caller asking for independent factors would get
    duplicates, finite and plausible, with nothing failing.

    `cell` is the row-major tape offset of `(step, factor)`, returned so a caller can cross-check
    a tape entry against this call without re-deriving the layout.

    @capability crn_cell_draw
    complexity: O(1)
    counts: none
    @endcapability
    """
    var fs = crn_factor_status(factor_kind, factor_param)
    if fs != STRAT_OK:
        return CellDraw(fs, False, 0.0, 0, 0, -1)
    var dpc = strat_draws_per_cell(factor_kind)
    var stream = strat_stream_scenario()
    # The LAST sub-draw the cell consumes is `dpc - 1`; validating that one validates the whole
    # cell, because `strat_coord_status`'s draw_index test is a monotone range test.
    var cs = strat_coord_status(
        master_seed, scenario_family, scenario, step, factor, stream, dpc - 1
    )
    if cs != STRAT_OK:
        return CellDraw(cs, False, 0.0, stream, dpc, -1)
    if n_factors < 1 or n_factors > STRAT_MAX_FACTORS or factor >= n_factors:
        return CellDraw(STRAT_ERR_SHAPE, False, 0.0, stream, dpc, -1)
    if not strat_product_fits(step, n_factors, STRAT_MAX_SCENARIO_CELLS):
        return CellDraw(STRAT_ERR_DIMENSION_TOO_LARGE, False, 0.0, stream, dpc, -1)
    var value = _factor_draw(
        UInt64(master_seed), UInt64(scenario_family), UInt64(scenario), UInt64(step),
        UInt64(factor), UInt64(stream), factor_kind, factor_param,
    )
    if not strat_finite(value):
        return CellDraw(STRAT_ERR_NON_FINITE, False, 0.0, stream, dpc, step * n_factors + factor)
    return CellDraw(STRAT_OK, True, value, stream, dpc, step * n_factors + factor)


fn _tape_coord_status(
    master_seed: Int, scenario_family: Int, scenario: Int, horizon: Int, n_factors: Int,
    factor_kind: Int,
) -> Int:
    """`STRAT_OK` when EVERY cell of this tape is a legal address, decided from the corner alone.

    The coordinate box is a product of intervals and every test in `strat_coord_status` is a
    per-axis range test on a non-negative value, so validating the maximum of each axis —
    `(horizon - 1, n_factors - 1, draws_per_cell - 1)` at this scenario — implies every interior
    cell validates. That is an argument, not a shortcut: a per-cell call would build one struct
    per draw in the hot loop and the corner carries exactly the same information.
    """
    if horizon < 1 or horizon > STRAT_MAX_HORIZON:
        return STRAT_ERR_SHAPE
    if n_factors < 1 or n_factors > STRAT_MAX_FACTORS:
        return STRAT_ERR_SHAPE
    var dpc = strat_draws_per_cell(factor_kind)
    if dpc < 1:
        return STRAT_ERR_NOT_EVALUABLE
    return strat_coord_status(
        master_seed, scenario_family, scenario, horizon - 1, n_factors - 1,
        strat_stream_scenario(), dpc - 1,
    )


fn crn_scenario_tape(
    master_seed: Int, scenario_family: Int, scenario: Int, horizon: Int, n_factors: Int,
    factor_kind: Int, factor_param: Float64,
) -> List[Float64]:
    """ONE scenario's exogenous factors as a `horizon x n_factors` row-major tape.

    AGAIN, NO STRATEGY PARAMETER. Two strategies compared at one scenario call this with
    identical arguments and therefore receive bit-identical tapes — by construction, not by
    convention. `crn_pairing_audit` calls it twice per scenario and folds both to prove it.

    Returns an EMPTY list on refusal. A bare `List` has no status field and an empty list is the
    only representable absence; a valid call returns exactly `horizon * n_factors` cells, so the
    two cannot be confused. Refused for a bad factor distribution, a horizon or factor count
    outside the ceilings, a product that does not fit `STRAT_MAX_SCENARIO_CELLS`, a negative or
    over-ceiling coordinate, and a non-finite draw (which an exponential at an extreme rate can
    produce and which the dispatch would refuse to serialise anyway).

    One tape, not `n_scenarios` of them: scenarios are the OUTER loop everywhere in this module
    and the tape is rebuilt per scenario, which is what keeps the allocation at
    `STRAT_MAX_SCENARIO_CELLS` and what makes pairing structural.

    @capability crn_scenario_tape
    complexity: O(horizon * n_factors)
    counts: none
    @endcapability
    """
    var out = List[Float64]()
    if crn_factor_status(factor_kind, factor_param) != STRAT_OK:
        return out^
    var cells = strat_scenario_cells(horizon, n_factors)
    if cells < 1:
        return out^
    if _tape_coord_status(
        master_seed, scenario_family, scenario, horizon, n_factors, factor_kind
    ) != STRAT_OK:
        return out^
    var seed = UInt64(master_seed)
    var family = UInt64(scenario_family)
    var scen = UInt64(scenario)
    var stream = UInt64(strat_stream_scenario())
    for t in range(horizon):
        for j in range(n_factors):
            var v = _factor_draw(
                seed, family, scen, UInt64(t), UInt64(j), stream, factor_kind, factor_param
            )
            if not strat_finite(v):
                var empty = List[Float64]()
                return empty^
            out.append(v)
    return out^


fn crn_scenario_digest(
    master_seed: Int, scenario_family: Int, scenario: Int, horizon: Int, n_factors: Int,
    factor_kind: Int, factor_param: Float64,
) -> Int:
    """The bit-exact digest of one scenario's tape, or -1 when the tape does not exist.

    `strat_crn_fold` over the raw IEEE-754 bits, so two tapes digest equal only if they agree to
    the last bit. A digest over rounded text or over `Int(v * 2^53)` would report agreement for
    tapes differing in the low mantissa, which is exactly the discrepancy an unpaired comparison
    produces and exactly what this has to catch.

    -1 for a refused tape, which is distinguishable from every real digest because
    `strat_crn_fold` masks to 62 bits and is therefore never negative.

    @capability crn_scenario_digest
    complexity: O(horizon * n_factors)
    counts: none
    @endcapability
    """
    var tape = crn_scenario_tape(
        master_seed, scenario_family, scenario, horizon, n_factors, factor_kind, factor_param
    )
    if len(tape) == 0:
        return -1
    return strat_crn_fold(tape, len(tape))


# ── evaluating one policy on one scenario ─────────────────────────────────────


@fieldwise_init
struct PolicyOutcome(Copyable, Movable):
    """One policy's payoff on one scenario, with the tape it read identified.

    `has_payoff` is separate from `status` because they fail separately: a discounted sum that
    overflowed to a non-finite total came from a perfectly legal request, so the request is not
    the defect — the payoff is ABSENT (`STRAT_ERR_PAYOFF_ABSENT`, value slot exactly 0.0) and
    `n_acted` still reports what the policy did. Absence is not zero: a policy that never acted
    has a payoff of exactly 0.0 and `has_payoff = True`, which is a different finding.

    `digest` is the fold of the tape this policy was evaluated on. Two outcomes with equal
    digests were evaluated on bit-identical scenarios, which is the CRN property stated as a
    number a caller can compare.
    """

    var status: Int
    var has_payoff: Bool
    var payoff: Float64
    var n_acted: Int
    var horizon: Int
    var policy_kind: Int
    var strategy: Int
    var has_digest: Bool
    var digest: Int


fn _outcome_refusal(code: Int, policy_kind: Int, strategy: Int) -> PolicyOutcome:
    return PolicyOutcome(code, False, 0.0, 0, 0, policy_kind, strategy, False, -1)


fn _row_status(
    policy_kind: Int, params: List[Float64], base: Int, n_factors: Int
) -> Int:
    """`STRAT_OK` when strategy row `base` is a legal policy of this kind.

    Called after the block shape held, so `params[base .. base + arity)` is inside the list.

    CONSTANT: the single parameter is an ACTION INDEX stored as a Float64 and must be exactly 0.0
    or 1.0. A 0.7 is not "mostly act" — it is a caller that meant a mixed policy, and rounding it
    would answer a question nobody asked. `STRAT_ERR_ACTION_RANGE`.

    MIXED: the row is a distribution over `CRN_N_ACTIONS`, validated by the contract's
    `strat_distribution_status` with `abs_tol = 0.0` so the ENTIRE allowance comes from the
    contract's ulp-widened builder rather than from a magic number invented here.
    """
    if policy_kind == STRAT_POLICY_CONSTANT:
        if params[base] != Float64(CRN_ACTION_HOLD) and params[base] != Float64(CRN_ACTION_ACT):
            return STRAT_ERR_ACTION_RANGE
        return STRAT_OK
    if policy_kind == STRAT_POLICY_MIXED:
        var row = List[Float64]()
        for k in range(CRN_N_ACTIONS):
            row.append(params[base + k])
        return strat_distribution_status(row, CRN_N_ACTIONS, 0.0)
    return STRAT_OK


fn _evaluate_row(
    tape: List[Float64], horizon: Int, n_factors: Int, policy_kind: Int,
    params: List[Float64], base: Int, cost: Float64, gamma: Float64,
    master_seed: Int, scenario_family: Int, scenario: Int, strategy: Int,
) -> PolicyOutcome:
    """The evaluation loop, with every guard already run by the caller.

    Split out so the aggregate drivers validate ONCE and then run: re-running
    `strat_scenario_status` (O(cells)) and `strat_policy_block_status` (O(len params)) inside the
    strategy loop would add `n_strategies * n_scenarios * cells` operations that the work charge
    does not account for, and an uncharged term is exactly how an accepted request becomes a
    wall-clock minute.

    Every subscript is provably in range from the caller's guards: `t * n_factors + j` is below
    `horizon * n_factors == len(tape)`, and `base + arity <= len(params)` because
    `n_strategies * arity == len(params)` held and `strategy < n_strategies`.
    """
    var total: Float64 = 0.0
    var disc: Float64 = 1.0
    var acted = 0
    var seed = UInt64(master_seed)
    var family = UInt64(scenario_family)
    var scen = UInt64(scenario)
    var pstream = UInt64(strat_stream_policy())
    for t in range(horizon):
        var cell = t * n_factors
        var value: Float64 = 0.0
        var score: Float64 = 0.0
        for j in range(n_factors):
            var x = tape[cell + j]
            value += x
            if policy_kind == STRAT_POLICY_THRESHOLD:
                score += params[base + j] * x
        value -= cost
        var act: Bool
        if policy_kind == STRAT_POLICY_CONSTANT:
            act = params[base] == Float64(CRN_ACTION_ACT)
        elif policy_kind == STRAT_POLICY_THRESHOLD:
            act = score >= params[base + n_factors]
        else:
            # The strategy index is the `dim1` coordinate here and NOWHERE in the environment.
            # dim0 stays the step, so a mixed policy's coin at step t is independent across
            # strategies while the scenario at step t is shared.
            act = rng_bernoulli(
                seed, family, scen, UInt64(t), UInt64(strategy), pstream, 0,
                params[base + CRN_ACTION_ACT],
            )
        if act:
            acted += 1
            total += disc * value
        disc *= gamma
    if not strat_finite(total):
        # A non-finite total is unreachable from a finite one, so one check at the end is
        # complete: an infinity never returns to a finite value and a NaN never leaves.
        return PolicyOutcome(
            STRAT_ERR_PAYOFF_ABSENT, False, 0.0, acted, horizon, policy_kind, strategy, False, -1
        )
    return PolicyOutcome(
        STRAT_OK, True, total, acted, horizon, policy_kind, strategy, False, -1
    )


fn crn_evaluate_on_tape(
    tape: List[Float64], horizon: Int, n_factors: Int, policy_kind: Int,
    params: List[Float64], n_strategies: Int, arity: Int, strategy: Int,
    cost: Float64, gamma: Float64, master_seed: Int, scenario_family: Int, scenario: Int,
) -> PolicyOutcome:
    """Evaluate strategy `strategy` on a CALLER-SUPPLIED tape, and report the tape's digest.

    This is the primitive that makes common random numbers directly testable from outside: hand
    the same `tape` to two different strategies and the two `digest` fields are equal, because
    the digest is of the scenario and the scenario has no strategy in it.

    `n_strategies` is a parameter so the shape relation `n_strategies * arity == len(params)` is
    declarable and machine-checkable rather than living in this docstring; `strategy` is then
    required to be inside it, and `STRAT_ERR_TOO_FEW_STRATEGIES` is a request for a strategy the
    block does not contain.

    Every refusal is forwarded with the code naming its own defect: the policy kind and arity from
    `crn_policy_status`, the block shape and finiteness from `strat_policy_block_status`, the tape
    shape and finiteness from `strat_scenario_status`, the discount from `strat_discount_status`,
    and the generator coordinates from `strat_coord_status`. A MIXED policy additionally needs its
    strategy index to be a legal `dim1`, so a randomised comparison is limited to
    `STRAT_MAX_FACTORS` strategies and is refused above it rather than silently aliasing two
    strategies onto one coin.

    @capability crn_evaluate_on_tape
    complexity: O(horizon * n_factors)
    counts:
    - horizon * n_factors == len(tape) [kernel_validated]
    - n_strategies * arity == len(params) [kernel_validated]
    @endcapability
    """
    var ps = crn_policy_status(policy_kind, n_factors, arity)
    if ps != STRAT_OK:
        return _outcome_refusal(ps, policy_kind, strategy)
    var bs = strat_policy_block_status(params, n_strategies, arity)
    if bs != STRAT_OK:
        return _outcome_refusal(bs, policy_kind, strategy)
    if strategy < 0 or strategy >= n_strategies:
        return _outcome_refusal(STRAT_ERR_TOO_FEW_STRATEGIES, policy_kind, strategy)
    var ts = strat_scenario_status(tape, horizon, n_factors)
    if ts != STRAT_OK:
        return _outcome_refusal(ts, policy_kind, strategy)
    var ds = strat_discount_status(gamma)
    if ds != STRAT_OK:
        return _outcome_refusal(ds, policy_kind, strategy)
    if not strat_finite(cost):
        return _outcome_refusal(STRAT_ERR_NON_FINITE, policy_kind, strategy)
    var base = strat_policy_row_start(strategy, arity)
    if base < 0:
        return _outcome_refusal(STRAT_ERR_SHAPE, policy_kind, strategy)
    var rs = _row_status(policy_kind, params, base, n_factors)
    if rs != STRAT_OK:
        return _outcome_refusal(rs, policy_kind, strategy)
    var coord_factor = 0
    if policy_kind == STRAT_POLICY_MIXED:
        coord_factor = strategy
    var cs = strat_coord_status(
        master_seed, scenario_family, scenario, horizon - 1, coord_factor,
        strat_stream_policy(), 0,
    )
    if cs != STRAT_OK:
        return _outcome_refusal(cs, policy_kind, strategy)
    var out = _evaluate_row(
        tape, horizon, n_factors, policy_kind, params, base, cost, gamma,
        master_seed, scenario_family, scenario, strategy,
    )
    var digest = strat_crn_fold(tape, len(tape))
    return PolicyOutcome(
        out.status, out.has_payoff, out.payoff, out.n_acted, horizon, policy_kind, strategy,
        digest >= 0, digest,
    )


# ── evaluating a SET of policies across the SAME scenario set ─────────────────


@fieldwise_init
struct PolicySetRun(Copyable, Movable):
    """Every strategy's payoff on every scenario of ONE shared scenario set.

    `n_tapes_built` is the structural witness that pairing happened and is not decoration: it
    equals `n_scenarios`, not `n_scenarios * n_strategies`, and it would change if the loop
    nesting were ever inverted so that each strategy built its own scenarios. A docstring
    claiming "scenarios are shared" cannot fail; this number can.

    `payoffs` is `n_strategies x n_scenarios` row-major with a parallel `payoff_present`. An
    absent payoff carries exactly 0.0 and `False`, because a policy that never acted has a real
    payoff of 0.0 and the two must stay distinguishable, and because the dispatch refuses to
    serialise a non-finite so a NaN in one slot would erase every present payoff beside it.

    `means` and `variances` are over the PRESENT payoffs of each strategy, with `has_mean` and
    `has_variance` as parallel flags: a variance needs two present payoffs and a mean needs one,
    so they fail at different points.
    """

    var status: Int
    var n_strategies: Int
    var n_scenarios: Int
    var horizon: Int
    var n_factors: Int
    var factor_kind: Int
    var policy_kind: Int
    var arity: Int
    var draws_per_cell: Int
    var work_charged: Int
    var cells_per_scenario: Int
    var n_tapes_built: Int
    var n_absent: Int
    var payoffs: List[Float64]
    var payoff_present: List[Bool]
    var n_acted: List[Int]
    var has_mean: List[Bool]
    var means: List[Float64]
    var has_variance: List[Bool]
    var variances: List[Float64]
    var first_digest: Int
    var last_digest: Int


fn _set_refusal(code: Int) -> PolicySetRun:
    return PolicySetRun(
        code, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0,
        List[Float64](), List[Bool](), List[Int](),
        List[Bool](), List[Float64](), List[Bool](), List[Float64](), -1, -1,
    )


fn crn_evaluate_policies(
    master_seed: Int, scenario_family: Int, n_scenarios: Int, horizon: Int, n_factors: Int,
    factor_kind: Int, factor_param: Float64, cost: Float64, policy_kind: Int,
    params: List[Float64], n_strategies: Int, arity: Int, gamma: Float64,
) -> PolicySetRun:
    """Evaluate every strategy in `params` across the SAME scenarios. The paired workhorse.

    Scenarios are the OUTER loop and strategies the INNER loop over ONE materialised tape, so
    every strategy reads the identical `List` object at scenario `r`. That ordering IS the common
    random numbers: it is not possible for two strategies here to see different scenarios, and
    `n_tapes_built == n_scenarios` is the number that says so.

    Every guard runs ONCE, before the loops, through `crn_request_status` — which also charges the
    four-factor work product and refuses over budget before anything runs. A request accepted and
    then abandoned has already spent the time, and from the caller's side a long-running accepted
    request is indistinguishable from the uncatchable abort the count guards exist to prevent.

    `first_digest` and `last_digest` are the bit-exact folds of the first and last scenario's
    tape. Different digests across scenarios is the independence claim, and
    `crn_independence_audit` measures it properly rather than inferring it from two numbers.

    A scenario whose tape cannot be built at all is `STRAT_ERR_SCENARIO_RANGE` for the whole run
    rather than a hole in the middle: the tape is a pure function of validated coordinates, so a
    failure there means the validation and the generator disagree and no payoff from the run can
    be trusted.

    @capability crn_evaluate_policies
    complexity: O(n_strategies * n_scenarios * horizon * n_factors)
    counts:
    - n_strategies * arity == len(params) [kernel_validated]
    @endcapability
    """
    var rs = crn_request_status(
        n_strategies, n_scenarios, horizon, n_factors, factor_kind, factor_param,
        policy_kind, arity, cost, gamma,
    )
    if rs != STRAT_OK:
        return _set_refusal(rs)
    var bs = strat_policy_block_status(params, n_strategies, arity)
    if bs != STRAT_OK:
        return _set_refusal(bs)
    var dpc = strat_draws_per_cell(factor_kind)
    var charge = strat_work_charge(n_strategies, n_scenarios, horizon, n_factors, dpc)
    if charge < 0:
        return _set_refusal(STRAT_ERR_WORK_BUDGET)
    var cells = strat_scenario_cells(horizon, n_factors)
    if cells < 1:
        return _set_refusal(STRAT_ERR_SHAPE)
    if not strat_product_fits(n_strategies, n_scenarios, STRAT_MAX_SCENARIO_CELLS):
        return _set_refusal(STRAT_ERR_DIMENSION_TOO_LARGE)

    var payoffs = List[Float64]()
    var present = List[Bool]()
    for _ in range(n_strategies * n_scenarios):
        payoffs.append(0.0)
        present.append(False)
    var acted = List[Int]()
    var bases = List[Int]()
    for s in range(n_strategies):
        acted.append(0)
        var b = strat_policy_row_start(s, arity)
        if b < 0:
            return _set_refusal(STRAT_ERR_SHAPE)
        var row = _row_status(policy_kind, params, b, n_factors)
        if row != STRAT_OK:
            return _set_refusal(row)
        bases.append(b)
    if policy_kind == STRAT_POLICY_MIXED and n_strategies > STRAT_MAX_FACTORS:
        # A mixed policy's coin puts the STRATEGY index in `dim1`, which `strat_coord_status`
        # bounds by the factor ceiling. Refused rather than allowed to alias two strategies onto
        # one coin, which would look like a correctly randomised comparison.
        return _set_refusal(STRAT_ERR_DIMENSION_TOO_LARGE)
    var coord_factor = 0
    if policy_kind == STRAT_POLICY_MIXED:
        coord_factor = n_strategies - 1
    var pcs = strat_coord_status(
        master_seed, scenario_family, n_scenarios - 1, horizon - 1, coord_factor,
        strat_stream_policy(), 0,
    )
    if pcs != STRAT_OK:
        return _set_refusal(pcs)

    var n_absent = 0
    var tapes_built = 0
    var first_digest = -1
    var last_digest = -1
    for r in range(n_scenarios):
        var tape = crn_scenario_tape(
            master_seed, scenario_family, r, horizon, n_factors, factor_kind, factor_param
        )
        if len(tape) != cells:
            return _set_refusal(STRAT_ERR_SCENARIO_RANGE)
        tapes_built += 1
        if r == 0:
            first_digest = strat_crn_fold(tape, cells)
        if r == n_scenarios - 1:
            last_digest = strat_crn_fold(tape, cells)
        for s in range(n_strategies):
            var out = _evaluate_row(
                tape, horizon, n_factors, policy_kind, params, bases[s], cost, gamma,
                master_seed, scenario_family, r, s,
            )
            acted[s] = acted[s] + out.n_acted
            if out.has_payoff:
                payoffs[s * n_scenarios + r] = out.payoff
                present[s * n_scenarios + r] = True
            else:
                n_absent += 1

    var has_mean = List[Bool]()
    var means = List[Float64]()
    var has_var = List[Bool]()
    var variances = List[Float64]()
    for s in range(n_strategies):
        var kept = List[Float64]()
        for r in range(n_scenarios):
            if present[s * n_scenarios + r]:
                kept.append(payoffs[s * n_scenarios + r])
        var n_kept = len(kept)
        if n_kept < 1:
            has_mean.append(False)
            means.append(0.0)
            has_var.append(False)
            variances.append(0.0)
            continue
        var mu = compute_mean(kept, n_kept)
        if not strat_finite(mu):
            has_mean.append(False)
            means.append(0.0)
            has_var.append(False)
            variances.append(0.0)
            continue
        has_mean.append(True)
        means.append(mu)
        if n_kept < 2:
            has_var.append(False)
            variances.append(0.0)
            continue
        var vr = compute_variance(kept, n_kept, mu)
        if not strat_finite(vr) or vr < 0.0:
            has_var.append(False)
            variances.append(0.0)
        else:
            has_var.append(True)
            variances.append(vr)

    return PolicySetRun(
        STRAT_OK, n_strategies, n_scenarios, horizon, n_factors, factor_kind, policy_kind,
        arity, dpc, charge, cells, tapes_built, n_absent,
        payoffs^, present^, acted^, has_mean^, means^, has_var^, variances^,
        first_digest, last_digest,
    )


@fieldwise_init
struct PolicyRun(Copyable, Movable):
    """ONE policy's payoff on each of `n_scenarios` scenarios, with its spread over them.

    The single-policy case of `crn_evaluate_policies`, kept as its own entry point because
    evaluating one strategy is a legitimate request — `strat_shape_status` accepts
    `n_strategies == 1` and only RANKING needs a second — and because a caller with one policy
    should not have to build a one-row block and then index row 0 out of a matrix.
    """

    var status: Int
    var n_scenarios: Int
    var horizon: Int
    var n_factors: Int
    var policy_kind: Int
    var arity: Int
    var draws_per_cell: Int
    var work_charged: Int
    var n_tapes_built: Int
    var n_acted: Int
    var n_absent: Int
    var payoffs: List[Float64]
    var payoff_present: List[Bool]
    var has_mean: Bool
    var mean: Float64
    var has_variance: Bool
    var variance: Float64
    var first_digest: Int
    var last_digest: Int


fn crn_evaluate_policy(
    master_seed: Int, scenario_family: Int, n_scenarios: Int, horizon: Int, n_factors: Int,
    factor_kind: Int, factor_param: Float64, cost: Float64, policy_kind: Int,
    params: List[Float64], arity: Int, gamma: Float64,
) -> PolicyRun:
    """Evaluate ONE policy across a scenario set. `params` is a single row of `arity` entries.

    Delegates to `crn_evaluate_policies` with `n_strategies = 1` rather than repeating the loop:
    one evaluation path means the single-policy and multi-policy answers cannot disagree, which
    is the whole reason a comparison is trustworthy in the first place.

    @capability crn_evaluate_policy
    complexity: O(n_scenarios * horizon * n_factors)
    counts:
    - arity == len(params) [kernel_validated]
    @endcapability
    """
    var run = crn_evaluate_policies(
        master_seed, scenario_family, n_scenarios, horizon, n_factors, factor_kind,
        factor_param, cost, policy_kind, params, 1, arity, gamma,
    )
    if run.status != STRAT_OK:
        return PolicyRun(
            run.status, 0, 0, 0, policy_kind, arity, 0, -1, 0, 0, 0,
            List[Float64](), List[Bool](), False, 0.0, False, 0.0, -1, -1,
        )
    var mean_ok = len(run.has_mean) == 1 and run.has_mean[0]
    var var_ok = len(run.has_variance) == 1 and run.has_variance[0]
    var mu: Float64 = 0.0
    var vr: Float64 = 0.0
    if mean_ok:
        mu = run.means[0]
    if var_ok:
        vr = run.variances[0]
    return PolicyRun(
        STRAT_OK, run.n_scenarios, run.horizon, run.n_factors, policy_kind, run.arity,
        run.draws_per_cell, run.work_charged, run.n_tapes_built, run.n_acted[0], run.n_absent,
        run.payoffs.copy(), run.payoff_present.copy(), mean_ok, mu, var_ok, vr,
        run.first_digest, run.last_digest,
    )


# ── the audit that justifies the package ──────────────────────────────────────


@fieldwise_init
struct PairingAudit(Copyable, Movable):
    """Both comparisons of the same two strategies on the same problem, side by side.

    `paired_variance` versus `unpaired_variance` is the whole finding, and `variance_ratio` is
    reported rather than left to the caller so a stored audit carries the number that justified
    it. `pairing_reduces_variance` is the strict inequality: if it is False, common random numbers
    bought nothing on this problem and the honest thing is to say so, not to bury it.

    `n_scenarios_bit_identical` is the MEASURED half. The tape is generated TWICE per scenario —
    once for each strategy — and both are folded bit-exactly; the count is how many agreed, and
    `STRAT_ERR_CRN_VIOLATED` is the status when any did not. Two independent generations rather
    than one shared list, because the claim under test is that generation is a pure function of
    coordinates with NO strategy input, and re-reading one list cannot test that.

    `conclusions_differ` is True when exactly one of the two intervals excludes zero: the paired
    comparison ranks the strategies and the unpaired one cannot, or the reverse. That is the field
    that turns a variance ratio into a decision that changed.

    Every `has_*` guards its own quantity because they fail separately: a variance needs two
    present payoffs, a t interval needs `inference_t_quantile` to be inside its bracket, and a
    p-value needs a non-zero standard error.
    """

    var status: Int
    var n_scenarios: Int
    var n_scenarios_used: Int
    var n_scenarios_bit_identical: Int
    var horizon: Int
    var n_factors: Int
    var strategy_a: Int
    var strategy_b: Int
    var level: Float64
    var work_charged: Int
    var n_tapes_built: Int
    var shared_digest: Int
    var independent_digest: Int
    var scenario_sets_differ: Bool
    var has_paired: Bool
    var paired_mean: Float64
    var paired_variance: Float64
    var has_paired_ci: Bool
    var paired_ci_lower: Float64
    var paired_ci_upper: Float64
    var paired_excludes_zero: Bool
    var has_paired_p: Bool
    var paired_p_value: Float64
    var has_unpaired: Bool
    var unpaired_mean: Float64
    var unpaired_variance: Float64
    var has_unpaired_ci: Bool
    var unpaired_ci_lower: Float64
    var unpaired_ci_upper: Float64
    var unpaired_excludes_zero: Bool
    var has_unpaired_p: Bool
    var unpaired_p_value: Float64
    var has_variance_ratio: Bool
    var variance_ratio: Float64
    var pairing_reduces_variance: Bool
    var conclusions_differ: Bool


fn _audit_refusal(code: Int) -> PairingAudit:
    return PairingAudit(
        code, 0, 0, 0, 0, 0, 0, 0, 0.0, -1, 0, -1, -1, False,
        False, 0.0, 0.0, False, 0.0, 0.0, False, False, 0.0,
        False, 0.0, 0.0, False, 0.0, 0.0, False, False, 0.0,
        False, 0.0, False, False,
    )


fn _two_sided_p(mean: Float64, variance: Float64, n: Int) -> Float64:
    """The two-sided t p-value for `mean == 0` on `n - 1` degrees of freedom, or -1.0 for absent.

    A ZERO variance is a real case here and has a defined answer, so it is not left to divide by
    zero: the differences were identical at every scenario, so `mean == 0` means the two
    strategies produced the same payoff on every scenario and there is no evidence of any
    difference at all (p = 1.0), while `mean != 0` means a deterministic difference with no
    sampling variation (p = 0.0). Returning an absence for the identical-strategies case would
    report "cannot tell" for the one case that is certain, and non-negotiable 1 is precisely that
    "no difference" must be a value.

    -1.0 for a genuine absence, which is outside `[0, 1]` and so cannot be read as a p-value;
    the caller's `has_*` flag is the answer.
    """
    if n < 2 or not strat_finite(mean) or not strat_finite(variance) or variance < 0.0:
        return -1.0
    if variance == 0.0:
        if mean == 0.0:
            return 1.0
        return 0.0
    var se = sqrt(variance / Float64(n))
    if not strat_finite(se) or se <= 0.0:
        return -1.0
    var p = inference_t_sf_two_sided(mean / se, Float64(n - 1))
    if not strat_finite(p) or p < 0.0 or p > 1.0:
        return -1.0
    return p


fn crn_pairing_audit(
    master_seed: Int, scenario_family: Int, n_scenarios: Int, horizon: Int, n_factors: Int,
    factor_kind: Int, factor_param: Float64, cost: Float64, policy_kind: Int,
    params: List[Float64], n_strategies: Int, arity: Int, strategy_a: Int, strategy_b: Int,
    gamma: Float64, level: Float64,
) -> PairingAudit:
    """Compare two strategies BOTH ways on one problem, and return both variances.

    THIS IS THE MEASUREMENT THAT JUSTIFIES THE PACKAGE. Per scenario `r`:

      1. generate the tape TWICE at the identical coordinates — once as strategy A's evaluation
         addresses it, once as strategy B's — and fold both bit-exactly. A single disagreement is
         `STRAT_ERR_CRN_VIOLATED`; `n_scenarios_bit_identical` counts the agreements.
      2. evaluate A on the first tape and B on the second. PAIRED: same scenario, both
         strategies.
      3. generate the tape at scenario `n_scenarios + r` — a different scenario from the same
         family and seed, independent by coordinate rather than by re-seeding — and evaluate B on
         it. UNPAIRED: the comparison a caller gets by running the two strategies separately.
      4. form the two difference samples, their Student-t intervals through the frozen
         `discrete_event.replicate_ci_flat`, and their two-sided t p-values.

    The unpaired arm reuses A's PAIRED payoff, so the two comparisons differ in exactly one
    thing: whether B faced A's scenario or an independent one. Anything else would confound the
    finding with a second change.

    Work is charged for THREE tape sets and THREE policy replays, as `charge(3 strategies) +
    2 * charge(1 strategy)`, because the charge helper couples the replay and draw terms. That
    over-charges the replay term by `2 * n_scenarios * horizon * (1 + n_factors)` and never
    under-charges the draws — the only safe direction, since a caller cannot distinguish an
    under-charged request from a hang.

    Refuses `strategy_a == strategy_b` with `STRAT_ERR_TOO_FEW_STRATEGIES`: a strategy compared
    against itself has a difference identically zero, which is a true answer to a question nobody
    means to ask, and returning it as a variance reduction of infinity would be worse.

    @capability crn_pairing_audit
    complexity: O(n_scenarios * horizon * n_factors)
    counts:
    - n_strategies * arity == len(params) [kernel_validated]
    @endcapability
    """
    var rs = crn_request_status(
        n_strategies, n_scenarios, horizon, n_factors, factor_kind, factor_param,
        policy_kind, arity, cost, gamma,
    )
    if rs != STRAT_OK:
        return _audit_refusal(rs)
    if n_strategies < 2:
        return _audit_refusal(STRAT_ERR_TOO_FEW_STRATEGIES)
    if strategy_a < 0 or strategy_b < 0:
        return _audit_refusal(STRAT_ERR_TOO_FEW_STRATEGIES)
    if strategy_a >= n_strategies or strategy_b >= n_strategies:
        return _audit_refusal(STRAT_ERR_TOO_FEW_STRATEGIES)
    if strategy_a == strategy_b:
        return _audit_refusal(STRAT_ERR_TOO_FEW_STRATEGIES)
    if not strat_finite(level) or level <= 0.0 or level >= 1.0:
        return _audit_refusal(STRAT_ERR_LEVEL_RANGE)
    var bs = strat_policy_block_status(params, n_strategies, arity)
    if bs != STRAT_OK:
        return _audit_refusal(bs)
    var dpc = strat_draws_per_cell(factor_kind)
    var cells = strat_scenario_cells(horizon, n_factors)
    if cells < 1:
        return _audit_refusal(STRAT_ERR_SHAPE)
    # The independent arm addresses scenarios `n_scenarios .. 2 * n_scenarios`, so the top one
    # must itself be a legal scenario coordinate. Checked here rather than discovered at the last
    # scenario, after the work has already been spent.
    if not strat_product_fits(2, n_scenarios, STRAT_MAX_REPLICATIONS):
        return _audit_refusal(STRAT_ERR_SCENARIO_RANGE)
    var base3 = strat_work_charge(3, n_scenarios, horizon, n_factors, dpc)
    var base1 = strat_work_charge(1, n_scenarios, horizon, n_factors, dpc)
    if base3 < 0 or base1 < 0:
        return _audit_refusal(STRAT_ERR_WORK_BUDGET)
    if base1 > (STRAT_MAX_WORK - base3) // 2:
        return _audit_refusal(STRAT_ERR_WORK_BUDGET)
    var charge = base3 + 2 * base1
    var ba = strat_policy_row_start(strategy_a, arity)
    var bb = strat_policy_row_start(strategy_b, arity)
    if ba < 0 or bb < 0:
        return _audit_refusal(STRAT_ERR_SHAPE)
    var ra = _row_status(policy_kind, params, ba, n_factors)
    if ra != STRAT_OK:
        return _audit_refusal(ra)
    var rb = _row_status(policy_kind, params, bb, n_factors)
    if rb != STRAT_OK:
        return _audit_refusal(rb)
    if policy_kind == STRAT_POLICY_MIXED and n_strategies > STRAT_MAX_FACTORS:
        return _audit_refusal(STRAT_ERR_DIMENSION_TOO_LARGE)

    var paired = List[Float64]()
    var unpaired = List[Float64]()
    var identical = 0
    var tapes = 0
    var shared_digest = -1
    var independent_digest = -1
    for r in range(n_scenarios):
        var tape_a = crn_scenario_tape(
            master_seed, scenario_family, r, horizon, n_factors, factor_kind, factor_param
        )
        var tape_b = crn_scenario_tape(
            master_seed, scenario_family, r, horizon, n_factors, factor_kind, factor_param
        )
        var tape_i = crn_scenario_tape(
            master_seed, scenario_family, n_scenarios + r, horizon, n_factors,
            factor_kind, factor_param,
        )
        if len(tape_a) != cells or len(tape_b) != cells or len(tape_i) != cells:
            return _audit_refusal(STRAT_ERR_SCENARIO_RANGE)
        tapes += 3
        var fold_a = strat_crn_fold(tape_a, cells)
        var fold_b = strat_crn_fold(tape_b, cells)
        if fold_a < 0 or fold_b < 0:
            return _audit_refusal(STRAT_ERR_SHAPE)
        if fold_a != fold_b:
            return _audit_refusal(STRAT_ERR_CRN_VIOLATED)
        identical += 1
        if r == 0:
            shared_digest = fold_a
            independent_digest = strat_crn_fold(tape_i, cells)
        var oa = _evaluate_row(
            tape_a, horizon, n_factors, policy_kind, params, ba, cost, gamma,
            master_seed, scenario_family, r, strategy_a,
        )
        var ob = _evaluate_row(
            tape_b, horizon, n_factors, policy_kind, params, bb, cost, gamma,
            master_seed, scenario_family, r, strategy_b,
        )
        var oi = _evaluate_row(
            tape_i, horizon, n_factors, policy_kind, params, bb, cost, gamma,
            master_seed, scenario_family, n_scenarios + r, strategy_b,
        )
        if oa.has_payoff and ob.has_payoff and oi.has_payoff:
            var dp = ob.payoff - oa.payoff
            var du = oi.payoff - oa.payoff
            if strat_finite(dp) and strat_finite(du):
                paired.append(dp)
                unpaired.append(du)

    var n_used = len(paired)
    var sets_differ = shared_digest >= 0 and independent_digest >= 0
    sets_differ = sets_differ and shared_digest != independent_digest
    if n_used < 1:
        return PairingAudit(
            STRAT_ERR_PAYOFF_ABSENT, n_scenarios, 0, identical, horizon, n_factors,
            strategy_a, strategy_b, level, charge, tapes, shared_digest, independent_digest,
            sets_differ,
            False, 0.0, 0.0, False, 0.0, 0.0, False, False, 0.0,
            False, 0.0, 0.0, False, 0.0, 0.0, False, False, 0.0,
            False, 0.0, False, False,
        )

    var mp = compute_mean(paired, n_used)
    var mu = compute_mean(unpaired, n_used)
    var vp: Float64 = 0.0
    var vu: Float64 = 0.0
    var has_p = strat_finite(mp)
    var has_u = strat_finite(mu)
    if has_p and n_used >= 2:
        vp = compute_variance(paired, n_used, mp)
        has_p = strat_finite(vp) and vp >= 0.0
    if has_u and n_used >= 2:
        vu = compute_variance(unpaired, n_used, mu)
        has_u = strat_finite(vu) and vu >= 0.0
    if not has_p:
        mp = 0.0
        vp = 0.0
    if not has_u:
        mu = 0.0
        vu = 0.0

    var cip = replicate_ci_flat(paired, n_used, level)
    var ciu = replicate_ci_flat(unpaired, n_used, level)
    var pl: Float64 = 0.0
    var pu: Float64 = 0.0
    var p_excl = False
    if cip.has_ci:
        pl = cip.ci_lower
        pu = cip.ci_upper
        p_excl = pl > 0.0 or pu < 0.0
    var ul: Float64 = 0.0
    var uu: Float64 = 0.0
    var u_excl = False
    if ciu.has_ci:
        ul = ciu.ci_lower
        uu = ciu.ci_upper
        u_excl = ul > 0.0 or uu < 0.0

    var pp = _two_sided_p(mp, vp, n_used)
    var up = _two_sided_p(mu, vu, n_used)
    var has_pp = has_p and pp >= 0.0
    var has_up = has_u and up >= 0.0
    if not has_pp:
        pp = 0.0
    if not has_up:
        up = 0.0

    var has_ratio = has_p and has_u and vp > 0.0
    var ratio: Float64 = 0.0
    if has_ratio:
        ratio = vu / vp
        if not strat_finite(ratio):
            has_ratio = False
            ratio = 0.0
    # Strict, and computed from the variances rather than from the ratio: a ratio of exactly 1.0
    # is not a reduction, and "pairing helped" must be False when it did not.
    var reduces = has_p and has_u and vp < vu
    var differ = (cip.has_ci and ciu.has_ci) and (p_excl != u_excl)

    return PairingAudit(
        STRAT_OK, n_scenarios, n_used, identical, horizon, n_factors, strategy_a, strategy_b,
        level, charge, tapes, shared_digest, independent_digest, sets_differ,
        has_p, mp, vp, cip.has_ci, pl, pu, p_excl, has_pp, pp,
        has_u, mu, vu, ciu.has_ci, ul, uu, u_excl, has_up, up,
        has_ratio, ratio, reduces, differ,
    )


# ── independence across scenarios, measured ───────────────────────────────────


@fieldwise_init
struct IndependenceAudit(Copyable, Movable):
    """The lag-`lag` correlation between scenario draw sequences, and its sampling-noise scale.

    A counter-based generator gives independent scenarios by construction. That is a reason to
    believe it, not a reason to skip checking it, and "independent by construction" is the kind
    of claim that stays true in a docstring long after a coordinate assignment has changed.

    Pairs are DISJOINT: scenario `i * (lag + 1)` with `i * (lag + 1) + lag`, so no scenario is
    used twice and no draw appears in both vectors. Pooling overlapping pairs would put each
    scenario in both sides and the p-value would then describe a different experiment than the
    one run.

    `noise_scale` is `1/sqrt(n_draw_pairs)` — the standard deviation of a sample correlation under
    independence — and `z_score` is `correlation / noise_scale`. Both are returned so a caller can
    apply its own band instead of accepting `CRN_INDEP_Z_BAND`.
    """

    var status: Int
    var n_scenarios: Int
    var lag: Int
    var horizon: Int
    var n_factors: Int
    var cells_per_scenario: Int
    var n_scenario_pairs: Int
    var n_draw_pairs: Int
    var work_charged: Int
    var has_correlation: Bool
    var correlation: Float64
    var has_noise_scale: Bool
    var noise_scale: Float64
    var has_z_score: Bool
    var z_score: Float64
    var has_p_value: Bool
    var p_value: Float64
    var z_band: Float64
    var indistinguishable_from_zero: Bool


fn _independence_refusal(code: Int) -> IndependenceAudit:
    return IndependenceAudit(
        code, 0, 0, 0, 0, 0, 0, 0, -1, False, 0.0, False, 0.0, False, 0.0, False, 0.0,
        CRN_INDEP_Z_BAND, False,
    )


fn crn_independence_audit(
    master_seed: Int, scenario_family: Int, n_scenarios: Int, horizon: Int, n_factors: Int,
    factor_kind: Int, factor_param: Float64, lag: Int,
) -> IndependenceAudit:
    """Measure whether scenario `i` and scenario `i + lag` are correlated. They must not be.

    Builds `n_scenario_pairs` DISJOINT pairs at stride `lag + 1`, concatenates the two sides cell
    by cell, and correlates them with the FROZEN `math_ext.correlation` — never a second
    correlation written here, because two definitions of "are these correlated" is how one answer
    path ends up disagreeing with another.

    Refusals: `lag < 1` -> `STRAT_ERR_SCENARIO_RANGE` (a lag of zero correlates a scenario with
    itself, which is 1.0 by definition and measures nothing); fewer than two complete pairs ->
    `STRAT_ERR_TOO_FEW_REPLICATIONS`; a pooled vector larger than
    `STRAT_MAX_SCENARIO_CELLS` -> `STRAT_ERR_DIMENSION_TOO_LARGE`, checked by DIVISION before
    either vector is allocated; and every refusal `crn_scenario_tape` can produce.

    Work is charged as three strategy-equivalents over `n_scenarios`, which covers the two vector
    fills and the correlation pass in the replay term and the `2 * n_scenario_pairs <=
    n_scenarios` tapes in the draw term.

    @capability crn_independence_audit
    complexity: O(n_scenarios * horizon * n_factors)
    counts: none
    @endcapability
    """
    if lag < 1 or lag >= STRAT_MAX_REPLICATIONS:
        return _independence_refusal(STRAT_ERR_SCENARIO_RANGE)
    var fs = crn_factor_status(factor_kind, factor_param)
    if fs != STRAT_OK:
        return _independence_refusal(fs)
    var dpc = strat_draws_per_cell(factor_kind)
    var budget = strat_budget(3, n_scenarios, horizon, n_factors, dpc)
    if not budget.fits:
        return _independence_refusal(budget.status)
    var cells = strat_scenario_cells(horizon, n_factors)
    if cells < 1:
        return _independence_refusal(STRAT_ERR_SHAPE)
    var stride = lag + 1
    var n_pairs = 0
    while n_pairs * stride + lag < n_scenarios:
        n_pairs += 1
    if n_pairs < 2:
        return _independence_refusal(STRAT_ERR_TOO_FEW_REPLICATIONS)
    if not strat_product_fits(n_pairs, cells, STRAT_MAX_SCENARIO_CELLS):
        return _independence_refusal(STRAT_ERR_DIMENSION_TOO_LARGE)

    var x = List[Float64]()
    var y = List[Float64]()
    for i in range(n_pairs):
        var left = crn_scenario_tape(
            master_seed, scenario_family, i * stride, horizon, n_factors,
            factor_kind, factor_param,
        )
        var right = crn_scenario_tape(
            master_seed, scenario_family, i * stride + lag, horizon, n_factors,
            factor_kind, factor_param,
        )
        if len(left) != cells or len(right) != cells:
            return _independence_refusal(STRAT_ERR_SCENARIO_RANGE)
        for c in range(cells):
            x.append(left[c])
            y.append(right[c])

    var n_draw_pairs = len(x)
    var r = correlation(x, y)
    var has_r = strat_finite(r) and r >= -1.0 and r <= 1.0
    if not has_r:
        r = 0.0
    var scale = 1.0 / sqrt(Float64(n_draw_pairs))
    var has_scale = strat_finite(scale) and scale > 0.0
    if not has_scale:
        scale = 0.0
    var z: Float64 = 0.0
    var has_z = has_r and has_scale
    if has_z:
        z = r / scale
        has_z = strat_finite(z)
        if not has_z:
            z = 0.0
    var p: Float64 = 0.0
    var has_p = False
    if has_z:
        var candidate = inference_norm_sf_two_sided(z)
        if strat_finite(candidate) and candidate >= 0.0 and candidate <= 1.0:
            p = candidate
            has_p = True
    var quiet = False
    if has_z:
        if z <= CRN_INDEP_Z_BAND and z >= -CRN_INDEP_Z_BAND:
            quiet = True

    return IndependenceAudit(
        STRAT_OK, n_scenarios, lag, horizon, n_factors, cells, n_pairs, n_draw_pairs,
        budget.total_charge, has_r, r, has_scale, scale, has_z, z, has_p, p,
        CRN_INDEP_Z_BAND, quiet,
    )
