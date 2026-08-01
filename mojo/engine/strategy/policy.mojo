"""
strategy.policy — a policy is an OBJECT here, not an integer tag. Zero Python imports.

What the tree had
-----------------
`game_theory.iterated_pd(strategy1: Int, strategy2: Int, rounds: Int)` is the whole of
"comparing strategies over repeated play" in this tree, and a strategy there is an INTEGER
selecting one of a handful of rules hardcoded inside the kernel, in the Prisoner's Dilemma and
nowhere else. You cannot state a new rule, you cannot ask what a rule does at a given state, and
you cannot ask whether a rule is even applicable to the environment you have. It stays frozen and
reachable; nothing here extends it.

`reinforcement.mojo` has the other half: `policy_from_q` extracts a tabular policy and
`policy_evaluation` scores one over an MDP. Both are exactly what is wanted for a tabular policy
and both are CALLED here rather than reimplemented. What they do not have is a bounds check —
`policy_evaluation` evaluates `rewards[s][a] + gamma * V[transitions[s][a]]` with no range test of
its own, so a policy naming action 3 in a 2-action MDP, or a transition naming state 99 in a
10-state MDP, is an UNCATCHABLE process abort inside frozen code that cannot be fixed there. That
guard is the main reason this module exists between a caller and those two kernels.

What a policy is here
---------------------
The flat `(kind, params, arity)` triple `strategy.contract` defines: `kind` from a closed set of
four, `params` an `n_strategies x arity` row-major `List[Float64]`, and `arity` COMPUTED by
`strat_policy_arity` from the kind and the environment's dimensions. A closed set of integer kinds
is not a stylistic choice — a public signature may carry only flat types, so a function pointer or
a caller-supplied callable cannot cross it, and a `Policy` STRUCT owned by another module would
silently drop every function that accepted one from the contract.

  CONSTANT   1 parameter          the action index, stored as a Float64
  THRESHOLD  n_factors + 1        a linear score over the factor vector, then the threshold
  TABULAR    n_states             the chosen action for each discretised state
  MIXED      n_actions            a probability per action

`policy_linear_action` is the fourth shape — a linear score per action over the factor vector, with
an argmax — expressed as a COMPOSITION rather than a fifth kind, because its parameter block is
`n_actions x n_factors` and minting a new kind code would put a second copy of the arity function
in this file. Its weight block is shape-checked by the same frozen `dims_fit` and its tie rule is
the same one.

Every dimension a kind does not use is IGNORED rather than validated, because refusing a request
for naming an irrelevant dimension is refusing a legitimate request. A CONSTANT policy is valid
against an environment with no factors and no states.

The refusal that is the point
-----------------------------
A policy that cannot be evaluated is REFUSED, not scored. Four distinct ways that happens, four
codes:

  * the row width does not match the environment — a tabular policy quoting 40 states against a
    12-state environment -> `STRAT_ERR_SHAPE`, and a dimension the arity function cannot use at
    all (zero states) -> `STRAT_ERR_POLICY_ARITY`;
  * a parameter that is not an action of this environment — a table entry of 3.0 where there are
    three actions, or a non-integral 1.5 -> `STRAT_ERR_ACTION_RANGE`. A THRESHOLD policy against a
    ONE-action environment is the same defect: it can emit action 1, which the environment lacks;
  * a lookup at a state the environment does not have -> `STRAT_ERR_STATE_RANGE`;
  * a mixed row that is not a distribution -> `STRAT_ERR_PROBABILITY`.

None of these is scored 0.0. A payoff that could not be computed is ABSENT, and an absent action
is reported as `has_action = False` with the action slot at -1 — never 0, which is a real action.
An absent Float64 slot is exactly 0.0 with its flag False, because the dispatch refuses to
serialise a non-finite and one NaN would turn the whole response into a typed error.

The tie conventions, stated once
--------------------------------
`policy_tie_rule()` is a FUNCTION for the same reason `discrete_event.de_event_order()` is: a tie
rule that lives only in a docstring cannot be checked, and two modules that resolve ties
differently produce two different rankings from one set of inputs.

  argmax     the LOWEST-INDEXED exact maximum wins. This is also what the frozen
             `reinforcement.policy_from_q` does (its `_argmax` advances only on a strict `>`), and
             the suite asserts that rather than trusting it, because the two must agree.
  threshold  the action is 1 when the score is AT or above the threshold — the comparison is
             closed on the threshold, so "meets the threshold" acts.

Both are deterministic, and `at_tie` / `n_tied` report separately that the decision was inside the
caller's tolerance. That separation matters: the ANSWER stays a function of the inputs alone,
while the caller still learns that the winner was not distinguishable from a runner-up. Breaking a
tie at random would be a policy property leaking into the environment; when it is wanted it belongs
on `strat_stream_tiebreak()`, which is a third stream precisely so a tie-break cannot perturb the
scenario.

Randomisation, and where the strategy index is allowed to be a coordinate
------------------------------------------------------------------------
`policy_sample_mixed` draws a mixed policy's action through the frozen counter-based generator on
`strat_stream_policy()`, with the STRATEGY index in the `dim1` slot — the only place in this
package where a strategy index is a generator coordinate. The environment's own coordinates never
carry one, which is what makes two strategies read bit-identical scenarios. One consequence is
visible in the signature and is stated rather than hidden: `dim1` is validated by
`strat_coord_status` against the FACTOR ceiling (256), so a sampled mixed policy is addressable
only for strategy indices below 256, while the deterministic paths accept the full 1024. The guard
refuses the rest with `STRAT_ERR_FACTOR_RANGE` — an over-tight refusal, never an aliased draw.

Counts, and the abort they prevent
----------------------------------
Every count is checked against the real length BEFORE the first read. `n_factors` above
`len(factors)` is `STRAT_ERR_COUNT`, not a wrong answer: a read past a `List` end is an uncatchable
bounds assertion that ends the worker process and takes every resident dataset with it, and
`try`/`except` above it does not help. Shapes are checked by DIVISION through the frozen
`sparse_numerics.csr.dims_fit`, because `3 * 6148914691236517206 == 2` and a wrapping multiply is
not a bound.

Two count relations here are CONDITIONAL on `kind` — `params` is `n_strategies * n_states` wide for
a tabular policy and `n_strategies * (n_factors + 1)` for a threshold one — and the declaration
grammar cannot express a disjunction. Declaring one of the four would be a FALSE relation, which is
worse than none, so those functions declare the dimensions and the docstring names the guard
(`strat_policy_block_status`) that validates the product. The two functions whose shape is
unconditional (`policy_tabular_actions`, `policy_from_q_flat`, `policy_linear_action`,
`policy_evaluate_tabular`) declare the product itself.

Bounding memory is not bounding work
------------------------------------
`policy_evaluate_tabular` calls a frozen fixed-point iteration whose sweep cap is 10000, so its
work is `10000 * n_states` state updates — 1.6e8 at the state ceiling, which no allocation ceiling
bounds. It is charged as a weighted product against `STRAT_MAX_WORK` before the kernel is entered,
and the WEIGHT is measured rather than assumed: charging one unit per update accepted a request at
30.5% of the ceiling that then ran for 4.20 seconds. `POLICY_SWEEP_WEIGHT` records the
measurement and the arithmetic. The largest accepted state count is 1677, which measures 0.74s,
and 1678 is refused with `STRAT_ERR_WORK_BUDGET`.

Exactness travels with the answer
---------------------------------
A table lookup and an argmax are EXACT and say so (`STRAT_EXACT_CLOSED_FORM`). Policy evaluation is
an ITERATION and says so (`STRAT_EXACT_APPROXIMATE`) — and carries its Bellman residual, computed
through the frozen `reinforcement.td_error`, because an "approximate" with no residual is an
admission with no evidence. When the residual does not meet the caller's tolerance the status is
`STRAT_ERR_NOT_CONVERGED` and the values are NOT returned: a vector that is not a fixed point is
not a value function, and returning it would be indistinguishable from a converged one. The
residual is still reported, so the caller learns how far off it was.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64, bool
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_strategy_policy.mojo
benchmark: none
docs: none
version_introduced: 2026.07.31
deprecation_state: active
@endcapability

`benchmark` and `docs` are `none` because those two files do not exist on disk yet, and a declared
artifact that is absent reads as coverage nobody wrote. The slice that adds the package benchmark
and the GitBook page replaces these two lines in the commit that creates them.
"""
from std.math import abs as fabs

from determinism.counter_rng import rng_uniform
from reinforcement import policy_evaluation, policy_from_q, td_error

from strategy.contract import (
    STRAT_ERR_ACTION_RANGE,
    STRAT_ERR_COUNT,
    STRAT_ERR_DIMENSION_TOO_LARGE,
    STRAT_ERR_NON_FINITE,
    STRAT_ERR_NOT_CONVERGED,
    STRAT_ERR_NOT_EVALUABLE,
    STRAT_ERR_POLICY_ARITY,
    STRAT_ERR_POLICY_KIND,
    STRAT_ERR_SHAPE,
    STRAT_ERR_STATE_RANGE,
    STRAT_ERR_WORK_BUDGET,
    STRAT_EXACT_APPROXIMATE,
    STRAT_EXACT_CLOSED_FORM,
    STRAT_EXACT_UNKNOWN,
    STRAT_MAX_ACTIONS,
    STRAT_MAX_FACTORS,
    STRAT_MAX_MDP_CELLS,
    STRAT_MAX_PAYOFF_CELLS,
    STRAT_MAX_STATES,
    STRAT_MAX_WORK,
    STRAT_OK,
    STRAT_POLICY_CONSTANT,
    STRAT_POLICY_COUNT,
    STRAT_POLICY_MIXED,
    STRAT_POLICY_TABULAR,
    STRAT_POLICY_THRESHOLD,
    strat_agrees,
    strat_all_finite,
    strat_crn_address,
    strat_dims_fit,
    strat_discount_status,
    strat_distribution_status,
    strat_finite,
    strat_ints_in_range,
    strat_policy_arity,
    strat_policy_block_status,
    strat_policy_row_start,
    strat_product3_fits,
    strat_product_fits,
    strat_stream_policy,
    strat_tolerance_status,
)

# The sweep cap inside the frozen `reinforcement.policy_evaluation` (`max_iter = 10000`). Mirrored
# here for ONE purpose: charging the work before the kernel is entered. The kernel owns the number
# and this copy never controls the iteration, so the two cannot disagree about the answer — the
# worst a drift could do is over-charge, and a frozen constant cannot drift.
comptime POLICY_EVAL_MAX_SWEEPS: Int = 10000

# What ONE state update of that sweep costs, in this package's work units.
#
# MEASURED, not assumed, and the first number here was WRONG. Charging one unit per state update
# accepted `n_states = 16384` at 30.5% of the work ceiling and it ran for 4.20 SECONDS — the
# 0.49s-versus-23.89s defect exactly: a request that reports a small cost and then hangs, which
# from the caller's side is indistinguishable from the abort the count guards prevent. Timing the
# forced-10000-sweep shape (`tol = 0.0`, which no sweep-to-sweep change can fall below) gave
#
#   n_states  1024 -> 0.397s   38.7 ns/update      1675 -> 0.743s   44.4 ns/update
#             2048 -> 0.688s   33.6 ns/update      4096 -> 1.372s   33.5 ns/update
#             3355 -> 1.341s   40.0 ns/update     16384 -> 4.799s   30.3 ns/update
#
# against the 1.66 ns this package calls one unit. The worst observed update is 44.4 ns, so
# 44.4 / 1.66 = 26.7, rounded UP to 32 — over-charging rather than under-charging, for the same
# reason `STRAT_DRAW_WEIGHT` rounds 63.0 up to 64.
#
# A row-stride effect was hypothesised and DISPROVED by the same measurement rather than assumed
# away: at 2^20 cells, (1024 states x 1024 actions) took 0.374s and (16384 x 64) took 4.97s, so
# the cost tracks `n_states` and not the row width. The per-cell term below is therefore charged
# at weight 1 — it is real work and it is small (2^20 units at the cell ceiling, 0.2% of the
# budget), and pretending it is free would be a different kind of wrong.
#
# The consequence is a REACHABLE refusal, which is the test that matters: the largest accepted
# state count is 1677 (0.74s measured) and 1678 is refused, where before nothing was.
comptime POLICY_SWEEP_WEIGHT: Int = 32

# The action slot's "no such action" value. -1 and not 0, because 0 is a real action index in every
# environment with at least one action, and an absent action reported as 0 is the silent wrong
# answer this package exists to refuse.
comptime POLICY_NO_ACTION: Int = -1


@fieldwise_init
struct PolicyAudit(Copyable, Movable):
    """Whether a policy block is evaluable against a stated environment, and why not if not.

    `evaluable` is separate from `status` for the reason `evaluation.gates` separates `decided`
    from `passed`: a caller that wants to know "can I run this" reads one Bool, and a caller that
    wants to know WHICH argument is wrong reads the code. Collapsing them would force every caller
    to compare against 450.

    `arity` is -1 when it could not be computed at all, which is what `strat_policy_arity`'s -1
    arrives as; it is never a plausible 0, because an arity of 0 makes every block "the right
    width".

    `max_row_error` is present only for `STRAT_POLICY_MIXED`, where a row is a distribution and the
    distance of its total from 1.0 is a real diagnostic. For every other kind there is no such
    quantity, so the flag is False and the slot is exactly 0.0 — a mixed block that sums to 1.0
    exactly reports 0.0 with the flag TRUE, and the two cases are distinguishable.
    """

    var status: Int
    var evaluable: Bool
    var kind: Int
    var arity: Int
    var n_strategies: Int
    var n_params: Int
    var n_factors: Int
    var n_actions: Int
    var n_states: Int
    var n_action_cells: Int
    var has_row_error: Bool
    var max_row_error: Float64


fn _audit_refusal(
    code: Int, kind: Int, arity: Int, n_factors: Int, n_actions: Int, n_states: Int
) -> PolicyAudit:
    return PolicyAudit(
        code, False, kind, arity, 0, 0, n_factors, n_actions, n_states, 0, False, 0.0
    )


@fieldwise_init
struct PolicyAction(Copyable, Movable):
    """One policy's action at one observation, with whether the choice was a tie.

    `has_action` and `action` are a flag/value pair like every other quantity here, and the absent
    slot is `POLICY_NO_ACTION` (-1) rather than 0.

    `has_score` is False for the kinds that HAVE no score: a constant policy and a table lookup do
    not compute one, and reporting 0.0 for it would be indistinguishable from a linear score that
    genuinely came out at zero — which is the exact input a threshold of 0.0 is decided on.

    `at_tie` is True when some alternative was indistinguishable from the winner at the caller's
    tolerance, and `n_tied` counts them INCLUDING the winner (so `n_tied == 1` means a clear
    decision). The action itself stays deterministic either way.
    """

    var status: Int
    var kind: Int
    var strategy: Int
    var state: Int
    var has_action: Bool
    var action: Int
    var has_score: Bool
    var score: Float64
    var at_tie: Bool
    var n_tied: Int


fn _action_refusal(code: Int, kind: Int) -> PolicyAction:
    return PolicyAction(code, kind, -1, -1, False, POLICY_NO_ACTION, False, 0.0, False, 0)


@fieldwise_init
struct PolicyTable(Copyable, Movable):
    """A resolved action for every state — the whole lookup, not one cell.

    Returned as a `List[Int]` of length `n_states` so a caller can check every cell rather than
    probe them one at a time, and so the result feeds `policy_evaluate_tabular` directly without a
    second decoding of the parameter block.

    `exactness` is `STRAT_EXACT_CLOSED_FORM`: a table lookup and an argmax are exact operations.
    It is carried anyway so that no caller has to know which of this package's answers are exact
    and which are iterative — every one of them says.

    On any refusal `actions` is EMPTY and `has_actions` is False. An empty list cannot be confused
    with a valid answer: a valid call with `n_states >= 1` always returns exactly `n_states`
    entries.
    """

    var status: Int
    var exactness: Int
    var n_states: Int
    var n_actions: Int
    var has_actions: Bool
    var actions: List[Int]


fn _table_refusal(code: Int) -> PolicyTable:
    return PolicyTable(code, STRAT_EXACT_UNKNOWN, 0, 0, False, List[Int]())


@fieldwise_init
struct LinearScore(Copyable, Movable):
    """Per-action linear scores over a factor vector, and the argmax over them.

    `scores` is returned in full so the argmax is CHECKABLE — a suite asserts every score and then
    the winner, rather than asserting the winner and trusting the arithmetic behind it.

    `best_score` is absent (flag False, slot 0.0) exactly when no action could be scored, which is
    also when `has_action` is False. They are separate flags because a future scoring rule could
    produce a decision without a comparable magnitude, and one flag standing for two facts is how
    a caller ends up reading a 0.0 as a score.
    """

    var status: Int
    var n_actions: Int
    var n_factors: Int
    var has_action: Bool
    var action: Int
    var at_tie: Bool
    var n_tied: Int
    var has_best: Bool
    var best_score: Float64
    var scores: List[Float64]


fn _linear_refusal(code: Int) -> LinearScore:
    return LinearScore(
        code, 0, 0, False, POLICY_NO_ACTION, False, 0, False, 0.0, List[Float64]()
    )


@fieldwise_init
struct PolicyValues(Copyable, Movable):
    """The value function of a stated tabular policy, with its exactness and its residual.

    `exactness` is `STRAT_EXACT_APPROXIMATE` on every successful call, because the frozen kernel
    behind it is a fixed-point ITERATION with a sweep cap, and `residual` is the evidence: the
    largest Bellman error over the states, computed through the frozen `reinforcement.td_error`.

    `has_values` is False and `values` EMPTY when the iteration did not reach the caller's
    tolerance, and the status is then `STRAT_ERR_NOT_CONVERGED`. The vector the kernel produced is
    deliberately not returned: it is not a fixed point, a caller cannot tell it from a converged
    one, and `residual` already says how far off it was. A refusal that still carries what exists.

    `work_charged` is the product that was checked against the work ceiling before the kernel was
    entered, reported so the charge is auditable rather than asserted. It is -1 on every refusal
    and never 0: a charge of zero reads as "this request was free", which is the opposite of what
    an over-budget refusal means, and the contract's own `WorkBudget.total_charge` uses the same
    -1 for the same reason.
    """

    var status: Int
    var exactness: Int
    var n_states: Int
    var n_actions: Int
    var gamma: Float64
    var tol: Float64
    var converged: Bool
    var has_residual: Bool
    var residual: Float64
    var has_values: Bool
    var values: List[Float64]
    var work_charged: Int


fn _values_refusal(code: Int) -> PolicyValues:
    return PolicyValues(
        code, STRAT_EXACT_UNKNOWN, 0, 0, 0.0, 0.0, False, False, 0.0, False,
        List[Float64](), -1,
    )


fn policy_tie_rule() -> String:
    """The tie conventions this module resolves by. Deterministic, zero-argument.

    `argmax:lowest_index;threshold:closed_at_threshold/v1`

    A FUNCTION and not a comment, for the reason `discrete_event.de_event_order()` is one: a tie
    rule that lives only in prose cannot be compared against, and two modules that resolve ties
    differently turn one set of inputs into two different rankings with nothing failing. The
    identifier is versioned because changing either half changes answers that are already stored.

    `lowest_index` also matches the frozen `reinforcement.policy_from_q`, whose `_argmax` advances
    only on a strict `>`. That agreement is asserted in the suite rather than assumed.

    @capability policy_tie_rule
    complexity: O(1)
    counts: none
    @endcapability
    """
    return String("argmax:lowest_index;threshold:closed_at_threshold/v1")


fn _action_from_param(v: Float64, n_actions: Int) -> Int:
    """Decode a parameter cell as an action index, or -1 if it is not one of this environment's.

    The range test comes FIRST and the conversion second, deliberately: `Int(1e300)` is not a
    meaningful integer, so the value is confined to `[0, n_actions - 1]` — at most 1023 — before
    it is converted at all. Then integrality is checked, because 1.5 is not an action: truncating
    it would silently execute action 1 for a policy that asked for something that does not exist.
    """
    if not strat_finite(v):
        return -1
    if v < 0.0 or v > Float64(n_actions - 1):
        return -1
    var a = Int(v)
    if Float64(a) != v:
        return -1
    return a


fn policy_validate_flat(
    params: List[Float64], n_strategies: Int, kind: Int, n_factors: Int,
    n_actions: Int, n_states: Int, abs_tol: Float64,
) -> PolicyAudit:
    """Decide whether a policy block is evaluable against a stated environment. Refuse if not.

    THE gate. Every other function here runs it before it reads a parameter, so a policy that
    references a dimension the environment lacks is refused once, in one place, with the code that
    names the argument at fault.

    Order of checks, cheapest and most specific first:

      1. `kind` outside the closed set -> `STRAT_ERR_POLICY_KIND`. Checked before the arity
         function, which answers -1 for BOTH an unknown kind and an unusable dimension and could
         not tell the caller which it was.
      2. `n_actions` outside `[1, STRAT_MAX_ACTIONS]` -> `STRAT_ERR_ACTION_RANGE`. Every kind emits
         an action index, so this one is never irrelevant. A THRESHOLD policy additionally needs at
         least TWO actions, because it can emit action 1 and an environment with one action does
         not have it — that is a policy referencing a dimension the environment lacks, refused
         rather than scored.
      3. `abs_tol` negative or non-finite -> `STRAT_ERR_TOLERANCE`. A NaN tolerance makes every
         comparison pass and a negative one makes every comparison fail; both look like a working
         validator from outside.
      4. arity from `strat_policy_arity`; -1 -> `STRAT_ERR_POLICY_ARITY`. This is where a tabular
         policy against a zero-state environment stops.
      5. the block's SHAPE, through `strat_policy_block_status`, which decides
         `n_strategies * arity == len(params)` by division through the frozen `dims_fit` and scans
         for non-finites last.
      6. `n_strategies * arity` against `STRAT_MAX_PAYOFF_CELLS`, so that every row start is
         addressable by `strat_policy_row_start`. Without it a 1024 x 16384 tabular block passes
         the shape check here and then has its later rows refused as unaddressable — a request
         accepted by one call and rejected two calls later, which is the defect
         `strat_scenario_cells` had and fixed.
      7. the kind's own semantics: a CONSTANT or TABULAR cell must be an integral action of this
         environment (`STRAT_ERR_ACTION_RANGE`), and a MIXED row must be a probability
         distribution (`STRAT_ERR_PROBABILITY`, via the contract's own check).

    Dimensions a kind does not use are NOT validated. A constant policy is evaluable against an
    environment with no factors and no states, and refusing it for naming a zero there would refuse
    a legitimate request.

    The parameter scan is O(len(params)), which is memory the caller has already allocated, so it
    needs no work charge of its own.

    @capability policy_validate_flat
    complexity: O(n_strategies * arity)
    counts:
    - dim n_strategies [kernel_validated]
    - dim n_factors [kernel_validated]
    - dim n_actions [kernel_validated]
    - dim n_states [kernel_validated]
    @endcapability

    The `params` relation is CONDITIONAL on `kind` — the row is `n_states` wide for a tabular
    policy, `n_factors + 1` for a threshold one, `n_actions` for a mixed one and 1 for a constant
    one — and the count grammar has no disjunction. Declaring any single one of the four would be
    a FALSE relation, which is worse than an absent one, so the dimensions are declared and the
    product is validated by `strat_policy_block_status`.
    """
    if kind < 0 or kind >= STRAT_POLICY_COUNT:
        return _audit_refusal(
            STRAT_ERR_POLICY_KIND, kind, -1, n_factors, n_actions, n_states
        )
    if n_actions < 1 or n_actions > STRAT_MAX_ACTIONS:
        return _audit_refusal(
            STRAT_ERR_ACTION_RANGE, kind, -1, n_factors, n_actions, n_states
        )
    if kind == STRAT_POLICY_THRESHOLD and n_actions < 2:
        return _audit_refusal(
            STRAT_ERR_ACTION_RANGE, kind, -1, n_factors, n_actions, n_states
        )
    var tol_status = strat_tolerance_status(abs_tol)
    if tol_status != STRAT_OK:
        return _audit_refusal(tol_status, kind, -1, n_factors, n_actions, n_states)

    var arity = strat_policy_arity(kind, n_factors, n_actions, n_states)
    if arity <= 0:
        return _audit_refusal(
            STRAT_ERR_POLICY_ARITY, kind, -1, n_factors, n_actions, n_states
        )

    var block = strat_policy_block_status(params, n_strategies, arity)
    if block != STRAT_OK:
        return _audit_refusal(block, kind, arity, n_factors, n_actions, n_states)
    if not strat_product_fits(n_strategies, arity, STRAT_MAX_PAYOFF_CELLS):
        return _audit_refusal(
            STRAT_ERR_DIMENSION_TOO_LARGE, kind, arity, n_factors, n_actions, n_states
        )

    var n_action_cells = 0
    var has_row_error = False
    var max_row_error: Float64 = 0.0

    if kind == STRAT_POLICY_CONSTANT or kind == STRAT_POLICY_TABULAR:
        # Every cell of these two kinds IS an action index. The block shape held, so
        # `start + i` is inside `params` for every row and column below.
        for s in range(n_strategies):
            var start = strat_policy_row_start(s, arity)
            if start < 0:
                return _audit_refusal(
                    STRAT_ERR_POLICY_ARITY, kind, arity, n_factors, n_actions, n_states
                )
            for i in range(arity):
                if _action_from_param(params[start + i], n_actions) < 0:
                    return _audit_refusal(
                        STRAT_ERR_ACTION_RANGE, kind, arity, n_factors, n_actions, n_states
                    )
                n_action_cells += 1
    elif kind == STRAT_POLICY_MIXED:
        has_row_error = True
        for s in range(n_strategies):
            var start = strat_policy_row_start(s, arity)
            if start < 0:
                return _audit_refusal(
                    STRAT_ERR_POLICY_ARITY, kind, arity, n_factors, n_actions, n_states
                )
            var row = List[Float64]()
            var total: Float64 = 0.0
            for i in range(arity):
                row.append(params[start + i])
                total += params[start + i]
            var dist = strat_distribution_status(row, arity, abs_tol)
            if dist != STRAT_OK:
                return _audit_refusal(dist, kind, arity, n_factors, n_actions, n_states)
            var err = fabs(total - 1.0)
            if err > max_row_error:
                max_row_error = err

    return PolicyAudit(
        STRAT_OK, True, kind, arity, n_strategies, len(params), n_factors, n_actions,
        n_states, n_action_cells, has_row_error, max_row_error,
    )


fn policy_action_flat(
    params: List[Float64], n_strategies: Int, strategy: Int, kind: Int,
    factors: List[Float64], n_factors: Int, state: Int, n_actions: Int,
    n_states: Int, abs_tol: Float64,
) -> PolicyAction:
    """Evaluate ONE policy at ONE observation: the action it takes, and whether that was a tie.

    The observation is both halves of what a policy can see: `factors` is the continuous vector a
    THRESHOLD policy scores, `state` is the discretised index a TABULAR policy looks up. A kind
    reads the half it uses and ignores the other, so a tabular policy is evaluable with `n_factors`
    of 0 and an empty factor list.

    Per kind:

      CONSTANT   the row's single cell, already validated as an action of this environment. No
                 score exists, so `has_score` is False rather than 0.0.
      THRESHOLD  `score = sum_j w_j * x_j`, action 1 when `score >= threshold`. The comparison is
                 CLOSED on the threshold — "meets the threshold" acts — and a score exactly equal
                 to the threshold therefore takes action 1 and reports `at_tie`.
      TABULAR    `params[row_start + state]`, with `state` bounds-checked against `n_states` first:
                 `STRAT_ERR_STATE_RANGE`, which is the refusal non-negotiable 3 asks for.
      MIXED      the argmax of the row, lowest index on an exact tie, with the chosen action's
                 probability as the score.

    `n_factors > len(factors)` is `STRAT_ERR_COUNT`, checked before the first read and
    UNCONDITIONALLY — not only on the kind that reads the list — so the declared relation is true
    of every call rather than of one branch. A non-finite factor is `STRAT_ERR_NON_FINITE` for the
    same reason: it would propagate into the score, where `score >= threshold` is silently False
    for a NaN and the policy would appear to have decided.

    `strategy` outside `[0, n_strategies - 1]` is `STRAT_ERR_NOT_EVALUABLE`: the block holds no
    such strategy, so there is no policy to evaluate. A negative index is refused rather than
    subscripted, because `params[-1]` is an uncatchable abort while a negative COUNT merely reads
    nothing.

    @capability policy_action_flat
    complexity: O(n_strategies * arity + n_factors)
    counts:
    - n_factors <= len(factors) [kernel_validated]
    - dim n_strategies [kernel_validated]
    - dim strategy [kernel_validated]
    - dim state [kernel_validated]
    - dim n_actions [kernel_validated]
    - dim n_states [kernel_validated]
    @endcapability

    `strategy` and `state` bound no list: the cell they address is
    `params[strategy * arity + state]`, a relation with two names multiplied and a third added,
    which the count grammar cannot spell. Both are validated here against `n_strategies` and
    `n_states`, and the block's shape is validated by `policy_validate_flat`, so the sum of the
    three is inside `params` by construction. The `params` product is conditional on `kind` for the
    reason `policy_validate_flat` records.
    """
    if n_factors > len(factors):
        return _action_refusal(STRAT_ERR_COUNT, kind)
    if not strat_all_finite(factors, n_factors):
        return _action_refusal(STRAT_ERR_NON_FINITE, kind)

    var audit = policy_validate_flat(
        params, n_strategies, kind, n_factors, n_actions, n_states, abs_tol
    )
    if audit.status != STRAT_OK:
        return _action_refusal(audit.status, kind)

    if strategy < 0 or strategy >= n_strategies:
        return _action_refusal(STRAT_ERR_NOT_EVALUABLE, kind)
    var start = strat_policy_row_start(strategy, audit.arity)
    if start < 0:
        return _action_refusal(STRAT_ERR_NOT_EVALUABLE, kind)

    if kind == STRAT_POLICY_CONSTANT:
        var a = _action_from_param(params[start], n_actions)
        if a < 0:
            return _action_refusal(STRAT_ERR_ACTION_RANGE, kind)
        return PolicyAction(
            STRAT_OK, kind, strategy, state, True, a, False, 0.0, False, 1
        )

    if kind == STRAT_POLICY_THRESHOLD:
        var score: Float64 = 0.0
        for j in range(n_factors):
            score += params[start + j] * factors[j]
        var threshold = params[start + n_factors]
        if not strat_finite(score):
            return _action_refusal(STRAT_ERR_NON_FINITE, kind)
        var acted = score >= threshold
        var action = 1
        if not acted:
            action = 0
        # The dot product is `n_factors` additions deep, so the allowance for "these two numbers
        # are the same" grows with it — that is what `additions` is for.
        var tie = strat_agrees(score, threshold, abs_tol, n_factors)
        var n_tied = 1
        if tie:
            n_tied = 2
        return PolicyAction(
            STRAT_OK, kind, strategy, state, True, action, True, score, tie, n_tied
        )

    if kind == STRAT_POLICY_TABULAR:
        if state < 0 or state >= n_states:
            return _action_refusal(STRAT_ERR_STATE_RANGE, kind)
        var a = _action_from_param(params[start + state], n_actions)
        if a < 0:
            return _action_refusal(STRAT_ERR_ACTION_RANGE, kind)
        return PolicyAction(
            STRAT_OK, kind, strategy, state, True, a, False, 0.0, False, 1
        )

    # MIXED: the greedy reduction of a distribution over actions.
    var best = 0
    var best_p = params[start]
    for a in range(1, n_actions):
        if params[start + a] > best_p:
            best_p = params[start + a]
            best = a
    var n_tied = 0
    for a in range(n_actions):
        if strat_agrees(params[start + a], best_p, abs_tol, 0):
            n_tied += 1
    return PolicyAction(
        STRAT_OK, kind, strategy, state, True, best, True, best_p, n_tied > 1, n_tied
    )


fn policy_tabular_actions(
    params: List[Float64], n_strategies: Int, strategy: Int, n_actions: Int,
    n_states: Int,
) -> PolicyTable:
    """Resolve a TABULAR policy's action at EVERY state, as the `List[Int]` the MDP kernels want.

    The bridge between this package's flat parameter block and the frozen
    `reinforcement.policy_evaluation`, whose `policy` argument is exactly this: one action index
    per state. Decoding every cell in one pass also makes the lookup checkable cell by cell, which
    is how the suite asserts it.

    Validated through `policy_validate_flat` — the one gate — with `kind` fixed to
    `STRAT_POLICY_TABULAR` and `n_factors` passed as 1. A tabular policy does not read the factor
    vector and its arity does not depend on it, so 1 is a placeholder the arity function ignores
    rather than a claim about the environment.

    @capability policy_tabular_actions
    complexity: O(n_strategies * n_states)
    counts:
    - n_strategies * n_states == len(params) [kernel_validated]
    - dim strategy [kernel_validated]
    - dim n_actions [kernel_validated]
    @endcapability

    The product IS the relation here and it is unconditional, because the kind is fixed. `strategy`
    bounds no list; it is validated against `n_strategies`.
    """
    var audit = policy_validate_flat(
        params, n_strategies, STRAT_POLICY_TABULAR, 1, n_actions, n_states, 0.0
    )
    if audit.status != STRAT_OK:
        return _table_refusal(audit.status)
    if strategy < 0 or strategy >= n_strategies:
        return _table_refusal(STRAT_ERR_NOT_EVALUABLE)
    var start = strat_policy_row_start(strategy, audit.arity)
    if start < 0:
        return _table_refusal(STRAT_ERR_NOT_EVALUABLE)

    var actions = List[Int]()
    for s in range(n_states):
        var a = _action_from_param(params[start + s], n_actions)
        if a < 0:
            return _table_refusal(STRAT_ERR_ACTION_RANGE)
        actions.append(a)
    return PolicyTable(
        STRAT_OK, STRAT_EXACT_CLOSED_FORM, n_states, n_actions, True, actions^
    )


fn policy_linear_action(
    weights: List[Float64], n_actions: Int, n_factors: Int,
    factors: List[Float64], abs_tol: Float64,
) -> LinearScore:
    """Score every action by a linear functional of the factor vector, then take the argmax.

    `weights` is an `n_actions x n_factors` row-major block: row `a` is the weight vector of action
    `a`, and `score_a = sum_j W[a][j] * x_j`. Expressed as a composition rather than a fifth policy
    kind on purpose — its block is a product of two environment dimensions rather than one, so
    minting a kind for it would put a second copy of `strat_policy_arity` in this file, which is
    how one invariant ends up enforced at two different strengths.

    Every score is returned, so the argmax is checkable rather than trusted.

    A non-finite score is refused for the whole call rather than skipped: every comparison against
    a NaN is False, so the argmax would silently return index 0 and report a decision that was
    never made.

    Ties: the LOWEST-INDEXED exact maximum wins, and `n_tied` counts every action indistinguishable
    from it at `abs_tol`, widened by one ulp per addition in the dot product. Three actions whose
    scores are all equal give action 0 with `n_tied == 3` — a deterministic answer AND the
    information that it was arbitrary.

    @capability policy_linear_action
    complexity: O(n_actions * n_factors)
    counts:
    - n_actions * n_factors == len(weights) [kernel_validated]
    - n_factors <= len(factors) [kernel_validated]
    @endcapability
    """
    if n_actions < 1 or n_actions > STRAT_MAX_ACTIONS:
        return _linear_refusal(STRAT_ERR_ACTION_RANGE)
    if n_factors < 1 or n_factors > STRAT_MAX_FACTORS:
        return _linear_refusal(STRAT_ERR_POLICY_ARITY)
    var tol_status = strat_tolerance_status(abs_tol)
    if tol_status != STRAT_OK:
        return _linear_refusal(tol_status)
    if not strat_dims_fit(n_actions, n_factors, len(weights)):
        return _linear_refusal(STRAT_ERR_SHAPE)
    if not strat_all_finite(weights, len(weights)):
        return _linear_refusal(STRAT_ERR_NON_FINITE)
    if n_factors > len(factors):
        return _linear_refusal(STRAT_ERR_COUNT)
    if not strat_all_finite(factors, n_factors):
        return _linear_refusal(STRAT_ERR_NON_FINITE)

    var scores = List[Float64]()
    for a in range(n_actions):
        var acc: Float64 = 0.0
        for j in range(n_factors):
            acc += weights[a * n_factors + j] * factors[j]
        if not strat_finite(acc):
            return _linear_refusal(STRAT_ERR_NON_FINITE)
        scores.append(acc)

    var best = 0
    var best_v = scores[0]
    for a in range(1, n_actions):
        if scores[a] > best_v:
            best_v = scores[a]
            best = a
    var n_tied = 0
    for a in range(n_actions):
        if strat_agrees(scores[a], best_v, abs_tol, n_factors):
            n_tied += 1
    return LinearScore(
        STRAT_OK, n_actions, n_factors, True, best, n_tied > 1, n_tied, True, best_v,
        scores^,
    )


fn policy_sample_mixed(
    params: List[Float64], n_strategies: Int, strategy: Int, n_actions: Int,
    master_seed: Int, scenario_family: Int, scenario: Int, step: Int,
    abs_tol: Float64,
) -> PolicyAction:
    """Draw a MIXED policy's action at one step, reproducibly, on the policy stream.

    The one place in this package where a strategy index becomes a generator coordinate. The draw
    is addressed at `(master_seed, scenario_family, scenario, step, strategy)` on
    `strat_stream_policy()`, with the STRATEGY in the `dim1` slot — `dim1` is the "which entity"
    field and a strategy is the entity there. The environment's own draws never carry a strategy
    index at all, which is what makes two strategies see bit-identical scenarios; putting a
    policy's coin on its own stream is what keeps a randomised strategy from consuming draws the
    environment was going to use.

    A tie-break is NOT this: it belongs on `strat_stream_tiebreak()`, a third stream, so that the
    presence of a tie cannot perturb the future.

    Inverse-CDF over the row, which consumes exactly ONE draw whatever the row contains — a
    rejection loop would make `draw_index` depend on the values and reintroduce the coupling the
    addressed generator removes. The final action absorbs the rounding: a cumulative total that
    stops a hair below 1.0 must not be able to return `n_actions`, which the environment does not
    have.

    `strategy` is validated by `strat_coord_status` against the FACTOR ceiling, because that is the
    field it occupies. That ceiling (256) is below the strategy ceiling (1024), so a sampled mixed
    policy is addressable only for the first 256 strategies and the rest are refused with
    `STRAT_ERR_FACTOR_RANGE`. Stated rather than worked around: the guard exists because a `dim1`
    at or above 65536 ALIASES onto a different step and returns identical draws for cells the
    caller believes are independent, and an over-tight refusal is the safe direction.

    @capability policy_sample_mixed
    complexity: O(n_actions)
    seed_requirements: required
    counts:
    - n_strategies * n_actions == len(params) [kernel_validated]
    - dim strategy [kernel_validated]
    - dim step [kernel_validated]
    @endcapability

    `deterministic` stays TRUE: a counter-based draw is a pure function of its coordinates, so this
    returns the same action for the same arguments on any machine, forever.
    """
    var audit = policy_validate_flat(
        params, n_strategies, STRAT_POLICY_MIXED, 1, n_actions, 0, abs_tol
    )
    if audit.status != STRAT_OK:
        return _action_refusal(audit.status, STRAT_POLICY_MIXED)
    if strategy < 0 or strategy >= n_strategies:
        return _action_refusal(STRAT_ERR_NOT_EVALUABLE, STRAT_POLICY_MIXED)
    var start = strat_policy_row_start(strategy, audit.arity)
    if start < 0:
        return _action_refusal(STRAT_ERR_NOT_EVALUABLE, STRAT_POLICY_MIXED)

    # The strategy index rides in the `factor` slot; the contract's own guard decides whether that
    # is an addressable coordinate, so this module never converts an unvalidated Int to UInt64.
    var addr = strat_crn_address(
        master_seed, scenario_family, scenario, step, strategy, strat_stream_policy(), 0
    )
    if not addr.usable:
        return _action_refusal(addr.status, STRAT_POLICY_MIXED)

    var u = rng_uniform(
        UInt64(addr.master_seed), UInt64(addr.scenario_family), UInt64(addr.scenario),
        UInt64(addr.step), UInt64(addr.factor), UInt64(addr.stream),
        UInt64(addr.draw_index),
    )
    var acc: Float64 = 0.0
    var chosen = n_actions - 1
    for a in range(n_actions):
        acc += params[start + a]
        if u < acc:
            chosen = a
            break
    var p = params[start + chosen]
    var n_tied = 0
    for a in range(n_actions):
        if strat_agrees(params[start + a], p, abs_tol, 0):
            n_tied += 1
    return PolicyAction(
        STRAT_OK, STRAT_POLICY_MIXED, strategy, step, True, chosen, True, p,
        n_tied > 1, n_tied,
    )


fn policy_from_q_flat(q_flat: List[Float64], n_states: Int, n_actions: Int) -> PolicyTable:
    """The greedy policy of a Q-table, through the FROZEN `reinforcement.policy_from_q`.

    Not reimplemented. This function is the guard and the flattening: the frozen kernel takes a
    nested `List[List[Float64]]`, which cannot cross a public signature, so the caller passes an
    `n_states x n_actions` row-major block and this builds the nested form after checking that the
    block IS that shape — by division through the frozen `dims_fit`, because `n_states * n_actions`
    is a wrapping multiply.

    A non-finite Q value is refused before the kernel sees it. The frozen `_argmax` advances only
    on a strict `>`, so a NaN row would leave the winner at index 0 and report a decision that no
    comparison made.

    The returned actions are re-checked against `[0, n_actions - 1]` afterwards. That is not
    distrust of the kernel: it is the guarantee the NEXT call needs, since these actions become the
    `policy` argument of `policy_evaluate_tabular`, where an out-of-range action subscripts a
    reward row inside frozen code.

    @capability policy_from_q_flat
    complexity: O(n_states * n_actions)
    counts:
    - n_states * n_actions == len(q_flat) [kernel_validated]
    @endcapability
    """
    if n_states < 1 or n_states > STRAT_MAX_STATES:
        return _table_refusal(STRAT_ERR_STATE_RANGE)
    if n_actions < 1 or n_actions > STRAT_MAX_ACTIONS:
        return _table_refusal(STRAT_ERR_ACTION_RANGE)
    if not strat_product_fits(n_states, n_actions, STRAT_MAX_MDP_CELLS):
        return _table_refusal(STRAT_ERR_DIMENSION_TOO_LARGE)
    if not strat_dims_fit(n_states, n_actions, len(q_flat)):
        return _table_refusal(STRAT_ERR_SHAPE)
    if not strat_all_finite(q_flat, len(q_flat)):
        return _table_refusal(STRAT_ERR_NON_FINITE)

    var q = List[List[Float64]]()
    for s in range(n_states):
        var row = List[Float64]()
        for a in range(n_actions):
            row.append(q_flat[s * n_actions + a])
        q.append(row^)
    var actions = policy_from_q(q)
    if len(actions) != n_states:
        return _table_refusal(STRAT_ERR_SHAPE)
    if not strat_ints_in_range(actions, n_states, 0, n_actions - 1):
        return _table_refusal(STRAT_ERR_ACTION_RANGE)
    return PolicyTable(
        STRAT_OK, STRAT_EXACT_CLOSED_FORM, n_states, n_actions, True, actions^
    )


fn policy_evaluate_tabular(
    actions: List[Int], n_states: Int, n_actions: Int,
    rewards_flat: List[Float64], transitions_flat: List[Int], gamma: Float64,
    tol: Float64,
) -> PolicyValues:
    """Score a STATED tabular policy over an MDP, through the FROZEN `reinforcement` kernels.

    `reinforcement.policy_evaluation` is the value-function iteration and `reinforcement.td_error`
    is the Bellman error; both are called, neither is reimplemented. What this adds is the three
    things they do not have: the bounds checks, the work charge, and an honest report of whether
    the iteration converged.

    THE BOUNDS CHECKS ARE THE REASON THIS EXISTS. The frozen kernel evaluates
    `rewards[s][a] + gamma * V[transitions[s][a]]` with no range test:

      * an action outside `[0, n_actions - 1]` subscripts past a reward row,
      * a transition naming a state the MDP does not have subscripts past `V`,

    and either is an UNCATCHABLE bounds assertion that ends the worker process — `try`/`except`
    above it does not help, and the defect is inside frozen code where it cannot be fixed. So
    `strat_ints_in_range` runs on both blocks first and the caller gets
    `STRAT_ERR_ACTION_RANGE` / `STRAT_ERR_STATE_RANGE` instead.

    Work, not just memory: the iteration sweeps every state up to `POLICY_EVAL_MAX_SWEEPS` times,
    so the work is `10000 * n_states` state updates — 1.6e8 at the state ceiling, which no
    allocation ceiling bounds. Charged as

        POLICY_SWEEP_WEIGHT * POLICY_EVAL_MAX_SWEEPS * n_states  +  n_states * n_actions

    before the kernel is entered, because a request that is accepted and then runs for a
    wall-clock minute is indistinguishable, from the caller's side, from the abort the bounds
    checks prevent. Both terms are grown by division and the sum is checked against the remaining
    headroom, since a wrapped total reads as cheap. The weight is MEASURED — see
    `POLICY_SWEEP_WEIGHT`, where an unweighted charge is recorded accepting a 4.20-second request
    at 30.5% of the ceiling.

    The charge is checked LAST, after the shapes and ranges, deliberately: a malformed request
    gets the code naming its actual defect instead of a budget refusal that would send the caller
    shrinking a dimension that was never the problem. All of those checks are O(cells) over memory
    the caller already allocated, which the charge itself accounts for.

    Convergence is MEASURED, not assumed. After the kernel returns, the largest Bellman residual
    over the states is computed through the frozen `td_error`; the answer exists only if that
    residual meets the caller's tolerance. It does not, for instance, at `gamma = 1.0` on a
    recurrent MDP with a positive reward, where the value function diverges and the kernel simply
    stops at its sweep cap — the vector it returns is finite, plausible and not a value function.
    That case is `STRAT_ERR_NOT_CONVERGED` with `has_values` False and the residual reported.

    A non-finite value anywhere in the returned vector is `STRAT_ERR_NON_FINITE`: large rewards at
    `gamma = 1.0` overflow to an infinity within a few sweeps, and the dispatch refuses to
    serialise one, so a single infinity would turn the whole response into a typed error.

    @capability policy_evaluate_tabular
    complexity: O(POLICY_EVAL_MAX_SWEEPS * n_states)
    counts:
    - n_states <= len(actions) [kernel_validated]
    - n_states * n_actions == len(rewards_flat, transitions_flat) [kernel_validated]
    @endcapability
    """
    if n_states < 1 or n_states > STRAT_MAX_STATES:
        return _values_refusal(STRAT_ERR_STATE_RANGE)
    if n_actions < 1 or n_actions > STRAT_MAX_ACTIONS:
        return _values_refusal(STRAT_ERR_ACTION_RANGE)
    if not strat_product_fits(n_states, n_actions, STRAT_MAX_MDP_CELLS):
        return _values_refusal(STRAT_ERR_DIMENSION_TOO_LARGE)
    if n_states > len(actions):
        return _values_refusal(STRAT_ERR_COUNT)
    if not strat_dims_fit(n_states, n_actions, len(rewards_flat)):
        return _values_refusal(STRAT_ERR_SHAPE)
    if not strat_dims_fit(n_states, n_actions, len(transitions_flat)):
        return _values_refusal(STRAT_ERR_SHAPE)
    var discount = strat_discount_status(gamma)
    if discount != STRAT_OK:
        return _values_refusal(discount)
    var tol_status = strat_tolerance_status(tol)
    if tol_status != STRAT_OK:
        return _values_refusal(tol_status)
    if not strat_all_finite(rewards_flat, len(rewards_flat)):
        return _values_refusal(STRAT_ERR_NON_FINITE)
    if not strat_ints_in_range(actions, n_states, 0, n_actions - 1):
        return _values_refusal(STRAT_ERR_ACTION_RANGE)
    if not strat_ints_in_range(transitions_flat, len(transitions_flat), 0, n_states - 1):
        return _values_refusal(STRAT_ERR_STATE_RANGE)
    # Two terms, both real, both grown by DIVISION: the sweeps and the nested-list build. The
    # sum is checked against the remaining headroom rather than formed and compared, because
    # `a + b` wraps exactly as `a * b` does and a wrapped total reads as cheap.
    if not strat_product3_fits(
        POLICY_SWEEP_WEIGHT, POLICY_EVAL_MAX_SWEEPS, n_states, STRAT_MAX_WORK
    ):
        return _values_refusal(STRAT_ERR_WORK_BUDGET)
    var sweep_charge = POLICY_SWEEP_WEIGHT * POLICY_EVAL_MAX_SWEEPS * n_states
    var cell_charge = n_states * n_actions
    if sweep_charge > STRAT_MAX_WORK - cell_charge:
        return _values_refusal(STRAT_ERR_WORK_BUDGET)
    var work = sweep_charge + cell_charge

    var rewards = List[List[Float64]]()
    var transitions = List[List[Int]]()
    for s in range(n_states):
        var r_row = List[Float64]()
        var t_row = List[Int]()
        for a in range(n_actions):
            r_row.append(rewards_flat[s * n_actions + a])
            t_row.append(transitions_flat[s * n_actions + a])
        rewards.append(r_row^)
        transitions.append(t_row^)
    # Exactly `n_states` entries, so the kernel's `policy[s]` cannot reach past what was checked.
    var policy = List[Int]()
    for s in range(n_states):
        policy.append(actions[s])

    var values = policy_evaluation(policy, n_states, rewards, transitions, gamma, tol)
    if len(values) != n_states:
        return _values_refusal(STRAT_ERR_SHAPE)
    if not strat_all_finite(values, n_states):
        return _values_refusal(STRAT_ERR_NON_FINITE)

    var residual: Float64 = 0.0
    for s in range(n_states):
        var a = actions[s]
        var cell = s * n_actions + a
        var nxt = transitions_flat[cell]
        var err = td_error(rewards_flat[cell], gamma, values[nxt], values[s])
        if not strat_finite(err):
            return _values_refusal(STRAT_ERR_NON_FINITE)
        var mag = fabs(err)
        if mag > residual:
            residual = mag

    var converged = strat_agrees(residual, 0.0, tol, n_states)
    if not converged:
        return PolicyValues(
            STRAT_ERR_NOT_CONVERGED, STRAT_EXACT_APPROXIMATE, n_states, n_actions, gamma,
            tol, False, True, residual, False, List[Float64](), work,
        )
    return PolicyValues(
        STRAT_OK, STRAT_EXACT_APPROXIMATE, n_states, n_actions, gamma, tol, True, True,
        residual, True, values^, work,
    )
