"""
strategy.equilibrium — N-player normal-form games, adaptive play, and honest exactness.

What the tree already had, and what it did not
---------------------------------------------
`game_theory.mojo` is frozen and every number it produces is called from here, never restated:

  * `nash_2x2` solves a 2x2 mixed equilibrium by indifference equations. It is a CLOSED FORM
    and it is EXACT for that shape, which makes it the reference this module is checked
    against — `eq_nash_2x2_flat` calls it, and `eq_solve_flat` routes a 2x2 game to it rather
    than running an iterative solver on a game with an exact answer.
  * `expected_payoff` evaluates a mixed profile on a 2x2 matrix, so the VALUE reported beside
    a 2x2 equilibrium comes from the frozen kernel too.
  * `dominated_strategy_check` finds strictly dominated ROWS of one player's matrix.
    `eq_dominated_actions_flat` calls it for every two-player game — including the column
    player, by handing it the matrix that player sees — and only falls back to its own tensor
    scan at three players and up, which is a shape the frozen kernel has no form for.
  * `minimax_value` is the row player's maximin. `eq_zero_sum_bounds_flat` calls it TWICE, once
    on the matrix and once on the negated transpose, to get the lower and upper values of a
    zero-sum game from one frozen kernel.
  * `prisoners_dilemma_payoff` builds the 2x2 tensor this module's known-value suite is
    checked on, so even the fixture is the frozen kernel's arithmetic rather than typed digits.

What was missing is everything past those fixed shapes. `nash_2x2` is 2x2 and
`shapley_value_3player` is three players; `iterated_pd(strategy1: Int, strategy2: Int, rounds:
Int)` is the tree's only repeated-play comparison and a "strategy" there is an integer tag
selecting a hardcoded rule in one hardcoded game. All of it stays reachable and unchanged. This
module adds the general shape: an N-player, N-action normal-form game as one flat payoff tensor,
exhaustive pure-equilibrium enumeration, best-response dynamics, regret matching and fictitious
play, and — the part that makes those usable as evidence — an EXPLOITABILITY number beside every
answer.

Exactness is a claim about the RESULT, and it never travels alone
----------------------------------------------------------------
An iterative solver that reports `converged: True` and nothing else is asking to be believed.
Every equilibrium this module returns carries `exactness`:

    STRAT_EXACT_CLOSED_FORM   the result was produced by a closed form or an exhaustive
                              enumeration AND its measured exploitability is inside the
                              caller's tolerance. It is an equilibrium, verified.
    STRAT_EXACT_APPROXIMATE   the result is an eps-equilibrium and `residual` IS eps — the
                              largest amount any single player can gain by deviating from it.
    STRAT_EXACT_UNKNOWN       the exploitability could not be computed, so no claim is made.
                              `has_residual` is False and no `exactness` above it is honest.

`residual` is not a convergence diagnostic and not a step size. It is the max over players of
`max_a u_i(a, sigma_-i) - u_i(sigma)`, computed by `eq_exploitability_flat` — the same PUBLIC
function a caller can run on the returned strategy itself. A residual a caller cannot recompute
is a claim, not a measurement, so the iterative drivers deliberately report a number produced by
the function the caller would check them with.

`nash_2x2` is exact for 2x2, and the exactness reported for its answer is still MEASURED, because
the frozen kernel CLAMPS its indifference solution into `[0, 1]` and a clamped point need not be
an equilibrium. On the Prisoner's Dilemma the clamp lands exactly on the pure equilibrium
(measured: `p = 0`, `q = 0`, residual 0) and the claim is CLOSED_FORM; where it does not land on
one, `residual` says how far off it is and the claim drops to APPROXIMATE. `default_mix_used`
reports the other case the frozen kernel resolves silently: an indifference denominator below its
own `1e-12` floor makes it return 0.5, a number that came from the fallback rather than from the
game, and a caller that is not told cannot know.

Where the exact answer exists, this module does not iterate
----------------------------------------------------------
`eq_solve_flat` routes a 2x2 game to the frozen closed form and only reaches for regret matching
above that shape. The agreement between the two on the shape where both apply is the strongest
correctness check available here, and it is asserted: on matching pennies the frozen kernel gives
`p = q = 0.5` and regret matching's time-average agrees to the last measured digit. That check is
only valid UNDER UNIQUENESS, and the module says so rather than generalising it — in the
coordination game there are three equilibria (two pure, one mixed) and two correct solvers may
legitimately return different ones. What is checked there is that each returned profile has
residual zero, which is a property of each answer alone.

A ranking that must be able to say "no equilibrium exists"
----------------------------------------------------------
`eq_pure_nash_flat` enumerates every profile, so "there are none" is an EXACT finding and it is
reported as one: on matching pennies `n_equilibria == 0` with `residual == 2.0`, the exact amount
the losing player can gain at the closest profile. A solver that always returns a profile would be
hiding that. The same shape covers the opposite extreme: in a game whose payoffs are all equal,
every profile is an equilibrium and the count says so instead of a single arbitrary winner.

Bounds, work, and the two ways this could kill a worker
-------------------------------------------------------
Reading past a `List` end is an uncatchable process abort that no `try` above can contain, so no
caller-supplied count is trusted: `n_players` against `len(actions)`, the tensor length against
`n_players * n_actions^n_players`, and every profile index against the profile count, all checked
BEFORE the first read. The tensor length is checked by DIVISION through the frozen
`sparse_numerics.csr.dims_fit` (via `strat_dims_fit`) and the profile count is grown one factor at
a time through `strat_product_fits`, because `n_actions ** n_players` is a wrapping multiply and a
wrapped size reads as small.

Bounding memory is not bounding work, and here they diverge violently. A tensor is at most
`STRAT_MAX_PAYOFF_CELLS` cells, but the work over it is a PRODUCT: enumeration costs
`profiles * n_players * (n_actions + 1)` payoff reads and one regret-matching iteration costs
`profiles * n_players` weighted accumulations, so an iteration count multiplies the whole tensor.
Both are charged as products against the SHARED `STRAT_MAX_WORK`, before anything runs, with
weights fitted to measurement on this tree rather than assumed — see `EQ_SCAN_WEIGHT` and
`EQ_SWEEP_WEIGHT`. An under-charged request is indistinguishable, from the caller's side, from a
hang. MEASURED at the ceiling: the largest accepted enumeration (2 players x 406 actions, 99.97%
of the budget) takes 0.15 s and the largest accepted regret-matching runs take 0.19-0.92 s, so a
request this module accepts is a request it finishes.

Determinism without a draw
--------------------------
Nothing here consumes a random number. Regret matching, fictitious play and best-response
dynamics are deterministic fixed-point iterations, and every tie between equally-good actions is
broken by the LOWEST ACTION INDEX — a rule named by `eq_tiebreak_rule()` so a stored result can
say what produced it, for the same reason `discrete_event.de_event_order()` exists. That is why
`seed_requirements` is `none` below: a solver that quietly sampled its tie-breaks would return a
different equilibrium on a different day, and `strategy.contract`'s tie-break stream exists for
callers that want a randomised one, not for this module.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64, bool
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_strategy_equilibrium.mojo
benchmark: benchmarks/mojo_benchmarks/bench_strategy.mojo
docs: gitbook/engine/strategy-simulation.md
version_introduced: 2026.07.31
deprecation_state: active
@endcapability
"""
from game_theory import (
    dominated_strategy_check,
    expected_payoff,
    minimax_value,
    nash_2x2,
)
from strategy.contract import (
    STRAT_ERR_ACTION_RANGE,
    STRAT_ERR_COUNT,
    STRAT_ERR_DEGENERATE,
    STRAT_ERR_DIMENSION_TOO_LARGE,
    STRAT_ERR_NON_FINITE,
    STRAT_ERR_NOT_CONVERGED,
    STRAT_ERR_NOT_EVALUABLE,
    STRAT_ERR_NOT_EXACT,
    STRAT_ERR_PAYOFF_ABSENT,
    STRAT_ERR_PLAYER_COUNT,
    STRAT_ERR_PROBABILITY,
    STRAT_ERR_SHAPE,
    STRAT_ERR_TOLERANCE,
    STRAT_ERR_WORK_BUDGET,
    STRAT_EXACT_APPROXIMATE,
    STRAT_EXACT_CLOSED_FORM,
    STRAT_EXACT_UNKNOWN,
    STRAT_MAX_ACTIONS,
    STRAT_MAX_PAYOFF_CELLS,
    STRAT_MAX_PLAYERS,
    STRAT_MAX_WORK,
    STRAT_OK,
    strat_absent,
    strat_agrees,
    strat_all_finite,
    strat_dims_fit,
    strat_distribution_status,
    strat_finite,
    strat_ints_in_range,
    strat_product3_fits,
    strat_product_fits,
    strat_tolerance_status,
)

# ── method tags: 0-based, so a method can never be read as a status ────────────
# Deliberately outside 450-489, exactly like `STRAT_VERDICT_*`. A caller that logs one integer
# must not be able to mistake "this came from regret matching" for "this failed".

comptime EQ_METHOD_ENUMERATION: Int = 0
comptime EQ_METHOD_CLOSED_FORM_2X2: Int = 1
comptime EQ_METHOD_REGRET_MATCHING: Int = 2
comptime EQ_METHOD_FICTITIOUS_PLAY: Int = 3
comptime EQ_METHOD_BEST_RESPONSE: Int = 4
comptime EQ_METHOD_TENSOR_DOMINANCE: Int = 5
comptime EQ_METHOD_COUNT: Int = 6

# ── ceilings this module adds, each with its arithmetic ───────────────────────
# The player, action, cell and WORK ceilings all come from `strategy.contract` and are not
# restated here: a caller that gets an answer from one module of this package and a refusal from
# another for the same shape has been told two different things about one game.

# An iteration count is the horizon of a fixed-point loop, and this ceiling is deliberately set
# so that it is REACHABLE rather than decorative. The smallest legal game — 2 players, 2 actions —
# charges `(4 * 2 + 2 * 2) * EQ_SWEEP_WEIGHT = 576` units per iteration, so 2^19 iterations costs
# 301,989,888 units and fits inside `STRAT_MAX_WORK`, while 2^20 would cost 603,979,776 and be
# refused by the budget for EVERY game in the space. A ceiling no request can ever reach tells a
# caller nothing; this one is the real limit for the smallest game, and any larger game hits the
# work budget first, which is the refusal that names the constraint that actually bound it.
comptime EQ_MAX_ITERS: Int = 1 << 19

# How many equilibrium profile indices `PureNashReport` carries back. The COUNT is always exact;
# only the listing is capped. It has to be capped: in a game whose payoffs are all equal every
# one of up to 2^21 profiles is an equilibrium, and returning that list would be a 16 MB response
# to a question about a 2x2 game's structure. 256 is enough to read a small game's full
# equilibrium set and `listed_truncated` says when it was not.
comptime EQ_MAX_LISTED: Int = 256

# ── cost model, fitted to measurement on this tree ────────────────────────────
# One charged unit is ~1.6 ns, the same unit `strategy.contract` calibrated `STRAT_DRAW_WEIGHT`
# against, so both packages' budgets mean the same thing. These weights live here rather than in
# the contract because they describe THIS work shape — a game tensor — and a weight fitted to one
# shape is wrong for another.
#
# MEASURED through the shipped `eq_pure_nash_flat` on an M4 Max at six shapes: one payoff read in
# the deviation scan costs 1.10 ns on an idle machine and 3.35 ns with five sibling builds
# competing for it. 3.35 / 1.6 = 2.1, rounded UP to 4 so the charge over-states the cost rather
# than under-stating it — an under-charged scan is a request that reports a small cost and then
# runs for a wall-clock second, which from the caller's side is a hang. At this weight the largest
# accepted enumeration is 2 players x 406 actions, 99.97% of `STRAT_MAX_WORK`, which ran in 0.15 s
# idle and 0.45 s loaded; 407 actions is refused. `bench_strategy.mojo` gates the per-unit cost
# against a band across sizes, because a charge model that dropped the `(n_actions + 1)` factor
# would show up as per-unit drift long before the wall time looked wrong.
comptime EQ_SCAN_WEIGHT: Int = 4

# MEASURED through the shipped `eq_regret_matching_flat`, with the player count ISOLATED at a
# fixed 6561 profiles so the factor could be fitted rather than guessed: one (profile, player)
# accumulation costs 17.0 ns at 2 players, 16.5 ns at 4 and 54.2 ns at 8. The weight comes from
# the worst of those — 54.2 / 1.6 = 33.9, rounded up to 48 for headroom on a loaded machine.
#
# The player factor is charged LINEARLY even though the measurement is flat to 4 players and then
# 3.2x worse at 8. Neither `n_players` nor `n_players^2` fits that curve — a quadratic would
# over-charge 4 players by 2x, and refusing work the machine can do is its own defect — so the
# charge stays the shape of the algorithm and the residual is disclosed instead of fitted. At the
# budget ceiling the saturating shapes measured 0.19 / 0.26 / 0.77 / 0.92 s: every accepted
# request is under a second, and the spread across shapes is printed by `bench_strategy.mojo`
# rather than hidden. What IS gated there is per-unit drift as one shape grows, which is what a
# missing factor in the charge model looks like.
comptime EQ_SWEEP_WEIGHT: Int = 48

# `game_theory.nash_2x2` compares `fabs(denominator) > 1e-12` and returns 0.5 when it does not
# hold. This constant MIRRORS that frozen threshold so `default_mix_used` can report the fallback
# instead of passing 0.5 off as a solution; `test_strategy_equilibrium.mojo` pins the mirror by
# constructing games with denominators of exactly 1e-12 and 2e-12 and asserting which side of the
# floor each lands on. If the frozen kernel ever changed, that assertion fails here rather than
# silently mislabelling every degenerate 2x2.
comptime EQ_NASH_2X2_DENOM_FLOOR: Float64 = 1e-12


def eq_method_name(method: Int) -> String:
    """The name of a solver tag. Deterministic, total, and never a plausible default.

    Returns `"unknown_method"` outside the declared tags rather than the first name, because a
    caller that logs a name it did not compute cannot tell the difference.
    """
    if method == EQ_METHOD_ENUMERATION:
        return "exhaustive_pure_enumeration"
    if method == EQ_METHOD_CLOSED_FORM_2X2:
        return "frozen_nash_2x2_closed_form"
    if method == EQ_METHOD_REGRET_MATCHING:
        return "regret_matching_time_average"
    if method == EQ_METHOD_FICTITIOUS_PLAY:
        return "fictitious_play_empirical_average"
    if method == EQ_METHOD_BEST_RESPONSE:
        return "sequential_best_response"
    if method == EQ_METHOD_TENSOR_DOMINANCE:
        return "tensor_dominance_scan"
    return "unknown_method"


def eq_tiebreak_rule() -> String:
    """The identifier of the tie-break rule every solver here uses. Zero-argument, deterministic.

    A FUNCTION rather than a comment, for the same reason `discrete_event.de_event_order()` is.
    Two actions with exactly equal value are ordered by INDEX, so the equilibrium a solver
    returns is a function of the payoffs alone. A sampled tie-break would make the answer depend
    on a seed nobody passed, and a container-order tie-break would make it depend on the
    allocator; both look identical to this one until the day they do not.
    """
    return String("lowest_action_index/v1")


# ── shape arithmetic: every product grown by division, because `a ** p` wraps ──


def eq_game_shape_status(n_players: Int, n_actions: Int) -> Int:
    """`STRAT_OK` when a game of this shape is representable AND has something to decide.

    Four distinct refusals, four codes:

      * `n_players < 2` -> `STRAT_ERR_PLAYER_COUNT`. A one-player "game" is plain maximisation
        and `decision_analysis.maximax` already answers it exactly; an equilibrium report over
        it would dress a trivial argmax as a game-theoretic finding.
      * `n_players > STRAT_MAX_PLAYERS` -> `STRAT_ERR_PLAYER_COUNT`. The player count is an
        EXPONENT in an `n_actions^n_players` tensor, which is why it cannot be given a generous
        ceiling the way a length can.
      * `n_actions < 2` -> `STRAT_ERR_DEGENERATE`. With one action per player there is exactly
        one profile, every deviation gain is trivially zero, and the report would read
        "equilibrium found, residual 0, exact" for a game with no decision in it. That is a
        vacuous claim dressed as a strong one, so it is refused instead.
      * `n_actions > STRAT_MAX_ACTIONS` -> `STRAT_ERR_ACTION_RANGE`.

    A shape that passes here can still be refused by `eq_game_status` for its cell count and by
    the charge functions for its work; those are different questions and carry different codes.
    """
    if n_players < 2 or n_players > STRAT_MAX_PLAYERS:
        return STRAT_ERR_PLAYER_COUNT
    if n_actions < 2:
        return STRAT_ERR_DEGENERATE
    if n_actions > STRAT_MAX_ACTIONS:
        return STRAT_ERR_ACTION_RANGE
    return STRAT_OK


def eq_profile_count(n_players: Int, n_actions: Int) -> Int:
    """`n_actions ** n_players` — the number of joint action profiles — or -1 if it does not fit.

    Grown ONE FACTOR AT A TIME through `strat_product_fits`, which decides by division. A power
    formed by multiplying wraps silently: at 64 bits `3 * 6148914691236517206 == 2`, so
    `total * n_actions <= limit` is not a bound at all and a wrapped profile count reads as a
    small allocation for an enormous game.

    The limit each partial product is grown against is `STRAT_MAX_PAYOFF_CELLS`, because the
    tensor holds `n_players` payoffs per profile and the cell count is the allocation that
    actually has to fit; `eq_payoff_cells` applies the remaining `n_players` factor.

    -1 rather than a status, because this answers "how many" and -1 is the "no such number"
    answer. `eq_game_status` turns it into `STRAT_ERR_DIMENSION_TOO_LARGE`.
    """
    if eq_game_shape_status(n_players, n_actions) != STRAT_OK:
        return -1
    var total = 1
    for _ in range(n_players):
        if not strat_product_fits(total, n_actions, STRAT_MAX_PAYOFF_CELLS):
            return -1
        total = total * n_actions
    return total


def eq_payoff_cells(n_players: Int, n_actions: Int) -> Int:
    """`n_players * n_actions ** n_players` — the exact tensor length — or -1 if it does not fit.

    The JOINT check is the binding one and it is why this is a separate function: 8 players is
    legal and 5 actions is legal, and 5^8 = 390,625 profiles is legal, but the tensor is
    8 * 390,625 = 3,125,000 cells. Checking the profile count alone would accept a request whose
    allocation is past `STRAT_MAX_PAYOFF_CELLS` while every stated dimension was inside it.
    """
    var profiles = eq_profile_count(n_players, n_actions)
    if profiles < 0:
        return -1
    if not strat_product_fits(n_players, profiles, STRAT_MAX_PAYOFF_CELLS):
        return -1
    return n_players * profiles


def eq_profile_stride(player: Int, n_players: Int, n_actions: Int) -> Int:
    """`n_actions ** (n_players - 1 - player)` — how far one step of `player`'s action moves.

    The tensor is row-major over the action tuple with PLAYER 0 MOST SIGNIFICANT, so player `i`'s
    own action is a digit whose place value is this stride. Returned rather than recomputed at
    each call site so the layout is written down once: a deviation scan that used the wrong
    stride would read a real, finite payoff belonging to a different profile, and every number
    downstream would be plausible and wrong.

    -1 for a shape that does not fit and for a `player` outside `[0, n_players)`; a negative
    player index would otherwise become a negative exponent, and a negative subscript aborts.
    """
    if eq_profile_count(n_players, n_actions) < 0:
        return -1
    if player < 0 or player >= n_players:
        return -1
    var s = 1
    for _ in range(n_players - 1 - player):
        s = s * n_actions
    return s


def eq_profile_action(profile: Int, player: Int, n_players: Int, n_actions: Int) -> Int:
    """Which action `player` takes in `profile`, or -1 when the request is not addressable.

    `(profile // stride) % n_actions`, the exact inverse of `eq_profile_index`.
    `test_strategy_equilibrium.mojo` asserts the round trip at EVERY profile of a 3-player
    4-action game — decode to a tuple, re-encode, get the same index — because a layout that is
    only ever used in one direction has nothing to disagree with, and a stride off by one factor
    reads a real, finite payoff belonging to a different profile.

    -1 for a profile outside `[0, profiles)`, which is also the guard between a caller-supplied
    profile index and a tensor subscript.
    """
    var profiles = eq_profile_count(n_players, n_actions)
    if profiles < 0:
        return -1
    if profile < 0 or profile >= profiles:
        return -1
    var s = eq_profile_stride(player, n_players, n_actions)
    if s < 0:
        return -1
    return (profile // s) % n_actions


def eq_profile_index(actions: List[Int], n_players: Int, n_actions: Int) -> Int:
    """The profile index of an action tuple, or -1 when the tuple is not a legal profile.

    The inverse of `eq_profile_action`, mixed-radix with player 0 most significant. `n_players`
    is checked against `len(actions)` BEFORE the first read, because a count above the list
    length is not a wrong index — it is an uncatchable bounds abort that ends the worker process
    and every resident dataset in it, and `try`/`except` at any layer above does not help.

    Every entry is then checked into `[0, n_actions)` through `strat_ints_in_range`, so a tuple
    naming action 40 of a 12-action game is -1 here rather than a read past the end of the
    tensor.

    @capability eq_profile_index
    complexity: O(n_players)
    counts:
    - n_players <= len(actions) [kernel_validated]
    - dim n_players [kernel_validated]
    - dim n_actions [kernel_validated]
    @endcapability
    """
    var profiles = eq_profile_count(n_players, n_actions)
    if profiles < 0:
        return -1
    if n_players > len(actions):
        return -1
    if not strat_ints_in_range(actions, n_players, 0, n_actions - 1):
        return -1
    var index = 0
    for i in range(n_players):
        index = index * n_actions + actions[i]
    return index


def eq_game_status(payoffs: List[Float64], n_players: Int, n_actions: Int) -> Int:
    """`STRAT_OK` when `payoffs` is exactly the tensor of an `n_players` x `n_actions^n_players`
    game and holds only real numbers.

    The one guard every driver here runs first. Layout is PLAYER-MAJOR:
    `payoffs[player * profiles + profile]`, so each player's payoff table is contiguous and the
    deviation scan for a fixed player stays inside one block.

    `STRAT_ERR_DIMENSION_TOO_LARGE` when the profile or cell count does not fit,
    `STRAT_ERR_SHAPE` when the length is not exactly `n_players * profiles` — decided by
    DIVISION through the frozen `sparse_numerics.csr.dims_fit`, because the product is a
    wrapping multiply — and `STRAT_ERR_NON_FINITE` for a NaN or infinity anywhere in the tensor,
    checked LAST because it is the only O(cells) test and there is nothing to scan in a tensor
    whose shape is already wrong. A non-finite payoff cannot be carried: it propagates into
    every expected value that reads it and the dispatch then refuses the whole response, so one
    unusable cell would erase every usable one beside it.

    The exact relation is `n_players * n_actions ** n_players == len(payoffs)`, which the count
    grammar cannot spell because the exponent is a parameter. It is enforced in full here by
    division, and the two dimensions are declared so the SDK guard refuses a negative or
    over-ceiling one before the frame arrives.

    @capability eq_game_status
    complexity: O(n_players * n_actions ** n_players)
    counts:
    - dim n_players [kernel_validated]
    - dim n_actions [kernel_validated]
    @endcapability
    """
    var shape = eq_game_shape_status(n_players, n_actions)
    if shape != STRAT_OK:
        return shape
    var profiles = eq_profile_count(n_players, n_actions)
    if profiles < 0:
        return STRAT_ERR_DIMENSION_TOO_LARGE
    if eq_payoff_cells(n_players, n_actions) < 0:
        return STRAT_ERR_DIMENSION_TOO_LARGE
    if not strat_dims_fit(n_players, profiles, len(payoffs)):
        return STRAT_ERR_SHAPE
    if not strat_all_finite(payoffs, len(payoffs)):
        return STRAT_ERR_NON_FINITE
    return STRAT_OK


# ── the work charges ──────────────────────────────────────────────────────────


def eq_enumeration_charge(n_players: Int, n_actions: Int) -> Int:
    """What an exhaustive pass over every profile costs, or -1 when it exceeds the budget.

        EQ_SCAN_WEIGHT * profiles * n_players * (n_actions + 1)

    Three factors, and none of them is optional. Every profile is visited (`profiles`), every
    player is checked at it (`n_players`), and each check reads that player's payoff plus its
    `n_actions` alternatives (`n_actions + 1`). Charging `profiles` alone — the size of the
    thing being scanned — under-states an 8-player game by 48x and a 512-action game by 1024x,
    and an under-charged request is indistinguishable from a hang from the caller's side.

    Also the bound used for the dominance scan, which costs `profiles * n_actions` reads per
    player: `n_players * (n_actions + 1)` exceeds `n_actions` for every legal shape, so this
    charge is conservative for that path rather than a second cost model that could drift.

    Every product is grown by division. -1 rather than a status, because a charge is a number.
    """
    var profiles = eq_profile_count(n_players, n_actions)
    if profiles < 0:
        return -1
    if not strat_product3_fits(profiles, n_players, n_actions + 1, STRAT_MAX_WORK):
        return -1
    var units = profiles * n_players * (n_actions + 1)
    if not strat_product_fits(EQ_SCAN_WEIGHT, units, STRAT_MAX_WORK):
        return -1
    return EQ_SCAN_WEIGHT * units


def eq_iteration_charge(n_players: Int, n_actions: Int, n_iters: Int) -> Int:
    """What `n_iters` adaptive-play iterations cost, or -1 when they exceed the budget.

        EQ_SWEEP_WEIGHT * n_iters * (profiles * n_players + n_actions * n_players)

    The iteration count MULTIPLIES the whole tensor, which is the specific place an
    equilibrium solver turns into a hang: regret matching over a 1024-action two-player game
    sweeps 2^20 profiles per iteration, so a thousand iterations is 10^9 accumulations. The
    first term is that sweep; the second is the per-iteration strategy update over each
    player's action row, which is smaller for every legal shape but is charged rather than
    ignored, because "smaller" is not "free" and the ratio is not bounded by anything the
    caller declares.

    `n_iters` above `EQ_MAX_ITERS` is -1 here, and every product is grown by division so no
    partial can wrap. The sum of the two terms is checked against the remaining headroom before
    it is formed, because `a + b` wraps exactly as `a * b` does and a wrapped total reads cheap.
    """
    var profiles = eq_profile_count(n_players, n_actions)
    if profiles < 0:
        return -1
    if n_iters < 1 or n_iters > EQ_MAX_ITERS:
        return -1
    if not strat_product_fits(profiles, n_players, STRAT_MAX_WORK):
        return -1
    var sweep_units = profiles * n_players
    if not strat_product_fits(n_actions, n_players, STRAT_MAX_WORK):
        return -1
    var update_units = n_actions * n_players
    if sweep_units > STRAT_MAX_WORK - update_units:
        return -1
    var per_iter = sweep_units + update_units
    if not strat_product3_fits(EQ_SWEEP_WEIGHT, n_iters, per_iter, STRAT_MAX_WORK):
        return -1
    return EQ_SWEEP_WEIGHT * n_iters * per_iter


def eq_best_response_charge(n_players: Int, n_actions: Int, max_rounds: Int) -> Int:
    """What `max_rounds` sweeps of best-response dynamics cost, or -1 over the budget.

        EQ_SCAN_WEIGHT * max_rounds * n_players * n_actions

    A round reads each player's current payoff and its `n_actions` alternatives, and NOTHING
    else — the tensor is never swept, because a pure profile needs no product measure. Charging
    this path with `eq_iteration_charge` would over-state it by `profiles / n_actions`, which at
    a 1024-action two-player game is 1024x and would refuse five rounds of a dynamic that costs
    microseconds. An over-charge is not the safe direction here: it turns valid requests into
    refusals, and a budget that refuses work it could do is as wrong as one that accepts work it
    cannot.
    """
    var profiles = eq_profile_count(n_players, n_actions)
    if profiles < 0:
        return -1
    if max_rounds < 1 or max_rounds > EQ_MAX_ITERS:
        return -1
    if not strat_product3_fits(max_rounds, n_players, n_actions, STRAT_MAX_WORK):
        return -1
    var units = max_rounds * n_players * n_actions
    if not strat_product_fits(EQ_SCAN_WEIGHT, units, STRAT_MAX_WORK):
        return -1
    return EQ_SCAN_WEIGHT * units


# ── results ───────────────────────────────────────────────────────────────────


@fieldwise_init
struct Exploitability(Copyable, Movable):
    """How much any single player can gain by abandoning a stated profile.

    THE verification primitive of this module, and public for that reason: every equilibrium
    reported anywhere here carries a residual produced by this same computation, so a caller can
    re-derive the claim from the returned strategy instead of taking it.

    `residual` is `max_i (max_a u_i(a, sigma_-i) - u_i(sigma))`, floored at zero — a negative
    best-response gain is arithmetically impossible (a player's value under its own mixture is a
    convex combination of its per-action values, so the maximum cannot be below it) and any
    negative is therefore rounding, which must not be reported as a player being better off than
    its own best response.

    `is_equilibrium` is NOT `residual == 0.0`. It is decided per player by comparing the
    best-response value against the achieved value with a tolerance scaled to the value being
    judged and widened by one ulp per addition that built it, because both numbers are sums over
    every profile and demanding exact equality of two differently-ordered sums would refuse
    every real equilibrium.

    `gains` and `values` are per player and EMPTY on any refusal; `worst_player` is -1 when
    absent, never 0, because player 0 is a real answer.
    """

    var status: Int
    var n_players: Int
    var n_actions: Int
    var has_residual: Bool
    var residual: Float64
    var worst_player: Int
    var is_equilibrium: Bool
    var has_value: Bool
    var value: Float64
    var gains: List[Float64]
    var values: List[Float64]


def _exploit_refusal(code: Int, n_players: Int, n_actions: Int) -> Exploitability:
    return Exploitability(
        code, n_players, n_actions, False, strat_absent(), -1, False, False, strat_absent(),
        List[Float64](), List[Float64](),
    )


@fieldwise_init
struct PureNashReport(Copyable, Movable):
    """Every pure equilibrium of a game, or the exact finding that it has none.

    Exhaustive: every profile is checked against every player's alternatives, so
    `n_equilibria == 0` is a THEOREM about the game and not a solver giving up. `residual` is
    the smallest exploitability any profile achieves, so a game with no pure equilibrium still
    reports how close its closest profile comes — 2.0 for matching pennies, the exact amount the
    losing player gains. A report that could only say "found one" or "found nothing" would throw
    that away.

    `first_profile` is the lowest equilibrium index under the declared mixed-radix profile order,
    which is a TOTAL order on profiles; it is first because the enumeration is ordered, not
    because it is better than the others. `n_equilibria` is always exact; `equilibria` lists at
    most `EQ_MAX_LISTED` of them and `listed_truncated` says when the list is shorter than the
    count.
    """

    var status: Int
    var exactness: Int
    var method: Int
    var n_players: Int
    var n_actions: Int
    var n_profiles: Int
    var n_equilibria: Int
    var has_first: Bool
    var first_profile: Int
    var has_residual: Bool
    var residual: Float64
    var best_profile: Int
    var listed_truncated: Bool
    var equilibria: List[Int]


def _pure_refusal(code: Int, n_players: Int, n_actions: Int) -> PureNashReport:
    return PureNashReport(
        code, STRAT_EXACT_UNKNOWN, EQ_METHOD_ENUMERATION, n_players, n_actions, 0, 0, False,
        -1, False, strat_absent(), -1, False, List[Int](),
    )


@fieldwise_init
struct MixedEquilibrium(Copyable, Movable):
    """One mixed profile, the claim made about it, and the number that backs the claim.

    `strategy` is `n_players x n_actions` row-major and EMPTY on any refusal. `exactness` is a
    claim about THIS result — CLOSED_FORM only when a closed form produced it and its measured
    exploitability is inside `abs_tol`, APPROXIMATE with `residual` otherwise, UNKNOWN when the
    residual itself could not be computed and no claim is honest.

    `iterations` is the number of iterations RUN, and for the iterative methods it always equals
    the count requested: there is no early stop. That is deliberate. An early stop makes the
    work data-dependent, which makes the charge a lie in both directions — a caller told a
    request costs X and then billed 0.1X cannot plan, and one told X and billed 3X has been
    handed the hang the budget exists to prevent. `converged` is then a measurement (`residual`
    inside `abs_tol`) rather than a loop condition.

    `default_mix_used` is only ever True on the frozen 2x2 path, and it means the frozen kernel's
    indifference denominator fell below its own floor so 0.5 came from a fallback rather than
    from the game.
    """

    var status: Int
    var exactness: Int
    var method: Int
    var n_players: Int
    var n_actions: Int
    var iterations: Int
    var converged: Bool
    var has_residual: Bool
    var residual: Float64
    var has_value: Bool
    var value: Float64
    var abs_tol: Float64
    var default_mix_used: Bool
    var strategy: List[Float64]


def _mixed_refusal(
    code: Int, method: Int, n_players: Int, n_actions: Int, abs_tol: Float64
) -> MixedEquilibrium:
    return MixedEquilibrium(
        code, STRAT_EXACT_UNKNOWN, method, n_players, n_actions, 0, False, False,
        strat_absent(), False, strat_absent(), abs_tol, False, List[Float64](),
    )


@fieldwise_init
struct BestResponsePath(Copyable, Movable):
    """Where sequential best-response dynamics ended up, and whether it ended at all.

    Players move in index order, each switching to its best response against the others' current
    actions, ties going to the lowest index. When a full sweep produces no switch the profile is
    a pure equilibrium by construction and `converged` is True with `residual` measured, not
    assumed.

    When `max_rounds` is exhausted the status is `STRAT_ERR_NOT_CONVERGED` and the final profile
    and its residual are STILL reported, because a refusal that carries what exists is more
    useful than one that carries nothing — on matching pennies the dynamic cycles forever and the
    honest answer is "no convergence, and the profile you are standing on is 2.0-exploitable",
    not a profile presented as an equilibrium.
    """

    var status: Int
    var exactness: Int
    var method: Int
    var converged: Bool
    var rounds: Int
    var n_switches: Int
    var start_profile: Int
    var final_profile: Int
    var has_residual: Bool
    var residual: Float64


def _path_refusal(code: Int, start_profile: Int) -> BestResponsePath:
    return BestResponsePath(
        code, STRAT_EXACT_UNKNOWN, EQ_METHOD_BEST_RESPONSE, False, 0, 0, start_profile, -1,
        False, strat_absent(),
    )


@fieldwise_init
struct ZeroSumBounds(Copyable, Movable):
    """The lower and upper values of a zero-sum matrix game, and whether they meet.

    `lower_value` is the row player's maximin and `upper_value` the column player's minimax, both
    from the FROZEN `game_theory.minimax_value` — once on the matrix, once on its negated
    transpose. `gap == 0` iff a pure saddle point exists, which is an EXACT statement about the
    game and the cheapest available answer to "does this game need mixing at all".

    Zero-sumness is VERIFIED, not assumed: `sum_defect` is the largest `|a + b|` over the two
    matrices, and a pair that is not zero-sum is refused with `STRAT_ERR_NOT_EVALUABLE` while
    still reporting that defect. Taking one matrix and trusting the caller's word would produce
    two confident bounds that bound nothing.
    """

    var status: Int
    var rows: Int
    var cols: Int
    var has_lower: Bool
    var lower_value: Float64
    var has_upper: Bool
    var upper_value: Float64
    var has_gap: Bool
    var gap: Float64
    var saddle: Bool
    var has_sum_defect: Bool
    var sum_defect: Float64


def _bounds_refusal(code: Int, rows: Int, cols: Int) -> ZeroSumBounds:
    return ZeroSumBounds(
        code, rows, cols, False, strat_absent(), False, strat_absent(), False, strat_absent(),
        False, False, strat_absent(),
    )


@fieldwise_init
struct DominanceReport(Copyable, Movable):
    """Which of one player's actions are STRICTLY dominated, and which kernel decided.

    `method` is `EQ_METHOD_CLOSED_FORM_2X2` when the frozen
    `game_theory.dominated_strategy_check` produced the answer — which is every two-player game,
    including the column player, because the matrix that player sees is built and handed to the
    frozen kernel — and `EQ_METHOD_TENSOR_DOMINANCE` for three players and up, a shape the frozen
    kernel has no form for. Provenance is a field rather than a comment because the two paths must
    agree where they overlap and `test_strategy_equilibrium.mojo` asserts that they do.

    `dominated` is EMPTY on any refusal. Strict dominance only: an action tied with another at
    every opponent profile is not dominated, which is the frozen kernel's convention and is kept
    so the two paths cannot disagree on the definition.
    """

    var status: Int
    var method: Int
    var player: Int
    var n_actions: Int
    var n_dominated: Int
    var dominated: List[Bool]


def _dominance_refusal(code: Int, player: Int, n_actions: Int) -> DominanceReport:
    return DominanceReport(code, EQ_METHOD_TENSOR_DOMINANCE, player, n_actions, 0, List[Bool]())


# ── internals: shared so the residual has exactly one implementation ──────────


def _sweep(
    payoffs: List[Float64],
    n_players: Int,
    n_actions: Int,
    profiles: Int,
    strategy: List[Float64],
    mut q: List[Float64],
    mut digits: List[Int],
    mut pre: List[Float64],
    mut suf: List[Float64],
):
    """`q[i * n_actions + a] = E[u_i(a, sigma_-i)]` under the product profile `strategy`.

    The opponents' weight for player `i` at a profile is the product of every OTHER player's
    probability, and it is formed from a prefix and a suffix product rather than by dividing the
    full product by `strategy[i]`. That is not a micro-optimisation: an action with probability
    exactly zero is normal in a mixed equilibrium (regret matching produces them constantly), and
    the division spelling would be `0 / 0` at every profile containing one.

    All scratch is caller-owned. The iterative drivers call this once per iteration and an
    allocation inside would dominate the cost of a small game — measured 414 ns per iteration of
    a 2x2 game with the scratch allocated here, against 349 ns with it hoisted.
    """
    for t in range(len(q)):
        q[t] = 0.0
    for g in range(profiles):
        var rest = g
        for k in range(n_players):
            var idx = n_players - 1 - k
            digits[idx] = rest % n_actions
            rest = rest // n_actions
        pre[0] = 1.0
        for i in range(n_players):
            pre[i + 1] = pre[i] * strategy[i * n_actions + digits[i]]
        suf[n_players] = 1.0
        for k in range(n_players):
            var i = n_players - 1 - k
            suf[i] = suf[i + 1] * strategy[i * n_actions + digits[i]]
        for i in range(n_players):
            var w = pre[i] * suf[i + 1]
            q[i * n_actions + digits[i]] += w * payoffs[i * profiles + g]


def _zeros(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(n):
        out.append(0.0)
    return out^


def _int_zeros(n: Int) -> List[Int]:
    var out = List[Int]()
    for _ in range(n):
        out.append(0)
    return out^


def _action_values(
    payoffs: List[Float64], n_players: Int, n_actions: Int, profiles: Int,
    strategy: List[Float64],
) -> List[Float64]:
    """One allocation-owning sweep, for the drivers that do exactly one."""
    var q = _zeros(n_players * n_actions)
    var digits = _int_zeros(n_players)
    var pre = _zeros(n_players + 1)
    var suf = _zeros(n_players + 1)
    _sweep(payoffs, n_players, n_actions, profiles, strategy, q, digits, pre, suf)
    return q^


def _within(best: Float64, achieved: Float64, abs_tol: Float64, additions: Int) -> Bool:
    """True when a best-response value does not beat the achieved value by more than tolerance.

    The judged quantity is `best`, a payoff, so the tolerance is scaled to ITS magnitude and
    widened by one ulp per addition that built it — `additions` is the profile count, since both
    numbers are sums over every profile. Judging the GAIN against zero instead would scale the
    allowance by a quantity that is ~0 at an equilibrium, which is a tolerance of `abs_tol`
    exactly and refuses every equilibrium whose two sums rounded differently.
    """
    if best <= achieved:
        return True
    return strat_agrees(best, achieved, abs_tol, additions)


def _exploit_core(
    payoffs: List[Float64], n_players: Int, n_actions: Int, profiles: Int,
    strategy: List[Float64], abs_tol: Float64,
) -> Exploitability:
    """The residual computation, shared by the public entry point and every solver here.

    One implementation, so a solver's reported residual and a caller's independent check of the
    same strategy are the same number by construction. Two implementations would be two answers
    to "is this an equilibrium", and the one the solver used would be the one nobody could see.
    """
    var q = _action_values(payoffs, n_players, n_actions, profiles, strategy)
    var gains = List[Float64]()
    var values = List[Float64]()
    var residual = 0.0
    var worst = -1
    var equilibrium = True
    for i in range(n_players):
        var achieved = 0.0
        var best = q[i * n_actions]
        for a in range(n_actions):
            var qv = q[i * n_actions + a]
            if not strat_finite(qv):
                return _exploit_refusal(STRAT_ERR_PAYOFF_ABSENT, n_players, n_actions)
            achieved += strategy[i * n_actions + a] * qv
            if qv > best:
                best = qv
        if not strat_finite(achieved):
            return _exploit_refusal(STRAT_ERR_PAYOFF_ABSENT, n_players, n_actions)
        var gain = best - achieved
        if not strat_finite(gain):
            return _exploit_refusal(STRAT_ERR_PAYOFF_ABSENT, n_players, n_actions)
        if gain < 0.0:
            gain = 0.0
        gains.append(gain)
        values.append(achieved)
        if not _within(best, achieved, abs_tol, profiles):
            equilibrium = False
        if worst < 0 or gain > residual:
            residual = gain
            worst = i
    return Exploitability(
        STRAT_OK, n_players, n_actions, True, residual, worst, equilibrium, True, values[0],
        gains^, values.copy(),
    )


def _nested(flat: List[Float64], offset: Int, rows: Int, cols: Int) -> List[List[Float64]]:
    """A rectangular `rows x cols` nested copy of a flat block, for the frozen kernels.

    `game_theory` takes `List[List[Float64]]` and reads `payoff[i][j]` with no bounds check of
    its own, so the nested value handed to it is built RECTANGULAR here and only after the flat
    block's length has been verified. A ragged nested list would abort inside frozen code.
    """
    var out = List[List[Float64]]()
    for i in range(rows):
        var row = List[Float64]()
        for j in range(cols):
            row.append(flat[offset + i * cols + j])
        out.append(row^)
    return out^


def _uniform_row(n_actions: Int) -> Float64:
    return 1.0 / Float64(n_actions)


# ── pure equilibria: exhaustive, so "none" is a finding ───────────────────────


def eq_pure_gains_flat(
    payoffs: List[Float64], n_players: Int, n_actions: Int, actions: List[Int],
    abs_tol: Float64,
) -> Exploitability:
    """Each player's best-response gain at ONE pure profile, by direct table lookup.

    `O(n_players * n_actions)`: for each player the payoff at the profile and its `n_actions`
    alternatives are read straight out of the tensor. No product measure is integrated, which
    makes this a genuinely independent second route to the same number —
    `test_strategy_equilibrium.mojo` asserts it equals `eq_exploitability_flat` on the one-hot
    strategy for the same profile. Two spellings of one quantity that are never compared is how
    a layout or weighting bug survives a suite.

    `n_players` is checked against `len(actions)` before the first read — `STRAT_ERR_COUNT`, the
    code that exists for exactly that defect — and every entry into `[0, n_actions)` through
    `strat_ints_in_range`, because both are subscripts into the tensor.

    @capability eq_pure_gains_flat
    complexity: O(n_players * n_actions)
    counts:
    - n_players <= len(actions) [kernel_validated]
    - dim n_players [kernel_validated]
    - dim n_actions [kernel_validated]
    @endcapability
    """
    var game = eq_game_status(payoffs, n_players, n_actions)
    if game != STRAT_OK:
        return _exploit_refusal(game, n_players, n_actions)
    var tol = strat_tolerance_status(abs_tol)
    if tol != STRAT_OK:
        return _exploit_refusal(tol, n_players, n_actions)
    if n_players > len(actions):
        return _exploit_refusal(STRAT_ERR_COUNT, n_players, n_actions)
    if not strat_ints_in_range(actions, n_players, 0, n_actions - 1):
        return _exploit_refusal(STRAT_ERR_ACTION_RANGE, n_players, n_actions)
    var profiles = eq_profile_count(n_players, n_actions)
    var profile = eq_profile_index(actions, n_players, n_actions)
    if profile < 0:
        return _exploit_refusal(STRAT_ERR_ACTION_RANGE, n_players, n_actions)
    var gains = List[Float64]()
    var values = List[Float64]()
    var residual = 0.0
    var worst = -1
    var equilibrium = True
    for i in range(n_players):
        var stride = eq_profile_stride(i, n_players, n_actions)
        if stride < 0:
            return _exploit_refusal(STRAT_ERR_DIMENSION_TOO_LARGE, n_players, n_actions)
        var here = payoffs[i * profiles + profile]
        var base = profile - actions[i] * stride
        var best = here
        for b in range(n_actions):
            var alt = payoffs[i * profiles + base + b * stride]
            if alt > best:
                best = alt
        var gain = best - here
        if not strat_finite(gain):
            return _exploit_refusal(STRAT_ERR_PAYOFF_ABSENT, n_players, n_actions)
        if gain < 0.0:
            gain = 0.0
        gains.append(gain)
        values.append(here)
        if not _within(best, here, abs_tol, 0):
            equilibrium = False
        if worst < 0 or gain > residual:
            residual = gain
            worst = i
    return Exploitability(
        STRAT_OK, n_players, n_actions, True, residual, worst, equilibrium, True, values[0],
        gains^, values.copy(),
    )


def eq_pure_nash_flat(
    payoffs: List[Float64], n_players: Int, n_actions: Int, abs_tol: Float64
) -> PureNashReport:
    """Every pure Nash equilibrium of the game, by exhaustive enumeration.

    Exhaustive is the point. The enumeration visits all `n_actions ** n_players` profiles and
    checks every player's `n_actions` alternatives at each, so the answer is exact in both
    directions: the set it returns is complete, and an empty set is a proof that the game has no
    pure equilibrium rather than a solver that stopped looking. `residual` is the minimum
    exploitability over all profiles — 0 when an equilibrium exists and, when none does, exactly
    how much the best profile still leaks (2.0 on matching pennies).

    Refuses `STRAT_ERR_WORK_BUDGET` before the first read when the pass exceeds
    `eq_enumeration_charge`. The work is a product of three factors and a caller that gets a
    refusal can shrink any of them; a caller that got the pass accepted and then waited would
    have no way to tell that from a hang.

    @capability eq_pure_nash_flat
    complexity: O(n_actions ** n_players * n_players * n_actions)
    counts:
    - dim n_players [kernel_validated]
    - dim n_actions [kernel_validated]
    @endcapability
    """
    var game = eq_game_status(payoffs, n_players, n_actions)
    if game != STRAT_OK:
        return _pure_refusal(game, n_players, n_actions)
    var tol = strat_tolerance_status(abs_tol)
    if tol != STRAT_OK:
        return _pure_refusal(tol, n_players, n_actions)
    if eq_enumeration_charge(n_players, n_actions) < 0:
        return _pure_refusal(STRAT_ERR_WORK_BUDGET, n_players, n_actions)
    var profiles = eq_profile_count(n_players, n_actions)
    var strides = _int_zeros(n_players)
    for i in range(n_players):
        strides[i] = eq_profile_stride(i, n_players, n_actions)
        if strides[i] < 1:
            # Unreachable while `eq_game_status` holds, and checked anyway: a stride of -1 would
            # make `g - digits[i] * stride` a subscript ABOVE the block and `b * stride` a
            # NEGATIVE one, and a negative subscript is an uncatchable abort rather than a wrong
            # answer. A guard that only matters after a future edit is exactly the guard worth
            # having, because the edit will not come with this reasoning attached.
            return _pure_refusal(STRAT_ERR_DIMENSION_TOO_LARGE, n_players, n_actions)
    var digits = _int_zeros(n_players)
    var found = List[Int]()
    var n_equilibria = 0
    var best_residual = strat_absent()
    var best_profile = -1
    var has_best = False
    for g in range(profiles):
        var rest = g
        for k in range(n_players):
            var idx = n_players - 1 - k
            digits[idx] = rest % n_actions
            rest = rest // n_actions
        var worst_gain = 0.0
        var equilibrium = True
        for i in range(n_players):
            var stride = strides[i]
            var here = payoffs[i * profiles + g]
            var base = g - digits[i] * stride
            var best = here
            for b in range(n_actions):
                var alt = payoffs[i * profiles + base + b * stride]
                if alt > best:
                    best = alt
            var gain = best - here
            if not strat_finite(gain):
                return _pure_refusal(STRAT_ERR_PAYOFF_ABSENT, n_players, n_actions)
            if gain > worst_gain:
                worst_gain = gain
            if not _within(best, here, abs_tol, 0):
                equilibrium = False
        if not has_best or worst_gain < best_residual:
            best_residual = worst_gain
            best_profile = g
            has_best = True
        if equilibrium:
            n_equilibria += 1
            if len(found) < EQ_MAX_LISTED:
                found.append(g)
    var first = -1
    if n_equilibria > 0:
        first = found[0]
    return PureNashReport(
        STRAT_OK, STRAT_EXACT_CLOSED_FORM, EQ_METHOD_ENUMERATION, n_players, n_actions,
        profiles, n_equilibria, n_equilibria > 0, first, has_best, best_residual, best_profile,
        n_equilibria > len(found), found^,
    )


def eq_exploitability_flat(
    payoffs: List[Float64], n_players: Int, n_actions: Int, strategy: List[Float64],
    abs_tol: Float64,
) -> Exploitability:
    """How exploitable a stated INDEPENDENT mixed profile is, per player and overall.

    `strategy` is `n_players x n_actions` row-major and each row must be a probability
    distribution — validated through `strat_distribution_status`, which is also the guard that
    keeps a row of NaNs or a row summing to 0.6 from producing a confident finite residual.
    `STRAT_ERR_SHAPE` when the block is not exactly that shape, by division.

    This is the function every solver here reports its residual from, so a caller can hand back
    the strategy it received and get the identical number. `STRAT_ERR_PAYOFF_ABSENT` when an
    expected value overflows to a non-finite despite finite inputs: the value is then ABSENT,
    which is not zero, and the dispatch would refuse a non-finite field outright.

    @capability eq_exploitability_flat
    complexity: O(n_actions ** n_players * n_players)
    counts:
    - n_players * n_actions == len(strategy) [kernel_validated]
    - dim n_players [kernel_validated]
    - dim n_actions [kernel_validated]
    @endcapability
    """
    var game = eq_game_status(payoffs, n_players, n_actions)
    if game != STRAT_OK:
        return _exploit_refusal(game, n_players, n_actions)
    var tol = strat_tolerance_status(abs_tol)
    if tol != STRAT_OK:
        return _exploit_refusal(tol, n_players, n_actions)
    if not strat_dims_fit(n_players, n_actions, len(strategy)):
        return _exploit_refusal(STRAT_ERR_SHAPE, n_players, n_actions)
    for i in range(n_players):
        var row = List[Float64]()
        for a in range(n_actions):
            row.append(strategy[i * n_actions + a])
        var dist = strat_distribution_status(row, n_actions, abs_tol)
        if dist != STRAT_OK:
            return _exploit_refusal(dist, n_players, n_actions)
    var profiles = eq_profile_count(n_players, n_actions)
    if eq_iteration_charge(n_players, n_actions, 1) < 0:
        return _exploit_refusal(STRAT_ERR_WORK_BUDGET, n_players, n_actions)
    return _exploit_core(payoffs, n_players, n_actions, profiles, strategy, abs_tol)


# ── the frozen 2x2 closed form, with its exactness measured ───────────────────


def eq_nash_2x2_flat(
    payoff_a: List[Float64], payoff_b: List[Float64], abs_tol: Float64
) -> MixedEquilibrium:
    """The FROZEN `game_theory.nash_2x2` closed form, with its answer verified and its fallback
    reported.

    Calls the frozen kernel — it is exact for this shape and reimplementing it would be a second
    answer to a question that already has one — and then measures what came back:

      * the VALUE for each player comes from the frozen `game_theory.expected_payoff` on the
        returned mixture, not from a sum written here;
      * `residual` comes from `eq_exploitability_flat`'s computation on the equivalent
        two-player tensor, which is exactly `payoff_a` followed by `payoff_b` under this
        module's layout, so the general machinery checks the closed form;
      * `exactness` is CLOSED_FORM only if that residual is inside `abs_tol`. The frozen kernel
        CLAMPS its indifference solution into `[0, 1]`, and a clamped point is not always an
        equilibrium; where it is not, the claim drops to APPROXIMATE and carries the residual;
      * `default_mix_used` is True when either indifference denominator was at or below
        `EQ_NASH_2X2_DENOM_FLOOR`, the frozen kernel's own floor, in which case that side's 0.5
        is a fallback rather than a solution.

    Both matrices must be exactly four finite entries, row-major, row player first. There is no
    count parameter to bound — the shape is fixed at 2x2 and checked by division against the
    real lengths — so `counts: none` is the honest declaration.

    @capability eq_nash_2x2_flat
    complexity: O(1)
    counts: none
    @endcapability
    """
    var tol = strat_tolerance_status(abs_tol)
    if tol != STRAT_OK:
        return _mixed_refusal(tol, EQ_METHOD_CLOSED_FORM_2X2, 2, 2, abs_tol)
    if not strat_dims_fit(2, 2, len(payoff_a)) or not strat_dims_fit(2, 2, len(payoff_b)):
        return _mixed_refusal(STRAT_ERR_SHAPE, EQ_METHOD_CLOSED_FORM_2X2, 2, 2, abs_tol)
    if not strat_all_finite(payoff_a, 4) or not strat_all_finite(payoff_b, 4):
        return _mixed_refusal(STRAT_ERR_NON_FINITE, EQ_METHOD_CLOSED_FORM_2X2, 2, 2, abs_tol)
    var denom_p = payoff_b[0] - payoff_b[1] - payoff_b[2] + payoff_b[3]
    var denom_q = payoff_a[0] - payoff_a[1] - payoff_a[2] + payoff_a[3]
    var fallback = False
    if denom_p >= -EQ_NASH_2X2_DENOM_FLOOR and denom_p <= EQ_NASH_2X2_DENOM_FLOOR:
        fallback = True
    if denom_q >= -EQ_NASH_2X2_DENOM_FLOOR and denom_q <= EQ_NASH_2X2_DENOM_FLOOR:
        fallback = True
    var nested_a = _nested(payoff_a, 0, 2, 2)
    var nested_b = _nested(payoff_b, 0, 2, 2)
    var solved = nash_2x2(nested_a, nested_b)
    var p = solved[0]
    var q = solved[1]
    if not strat_finite(p) or not strat_finite(q):
        return _mixed_refusal(STRAT_ERR_PAYOFF_ABSENT, EQ_METHOD_CLOSED_FORM_2X2, 2, 2, abs_tol)
    var strategy = List[Float64]()
    strategy.append(p)
    strategy.append(1.0 - p)
    strategy.append(q)
    strategy.append(1.0 - q)
    var p_row = List[Float64]()
    p_row.append(p)
    p_row.append(1.0 - p)
    var p_col = List[Float64]()
    p_col.append(q)
    p_col.append(1.0 - q)
    var value_a = expected_payoff(nested_a, p_row, p_col)
    if not strat_finite(value_a):
        return _mixed_refusal(STRAT_ERR_PAYOFF_ABSENT, EQ_METHOD_CLOSED_FORM_2X2, 2, 2, abs_tol)
    var tensor = List[Float64]()
    for t in range(4):
        tensor.append(payoff_a[t])
    for t in range(4):
        tensor.append(payoff_b[t])
    var audit = _exploit_core(tensor, 2, 2, 4, strategy, abs_tol)
    if audit.status != STRAT_OK:
        return _mixed_refusal(audit.status, EQ_METHOD_CLOSED_FORM_2X2, 2, 2, abs_tol)
    var claim = STRAT_EXACT_APPROXIMATE
    if audit.is_equilibrium:
        claim = STRAT_EXACT_CLOSED_FORM
    return MixedEquilibrium(
        STRAT_OK, claim, EQ_METHOD_CLOSED_FORM_2X2, 2, 2, 1, audit.is_equilibrium, True,
        audit.residual, True, value_a, abs_tol, fallback, strategy^,
    )


# ── adaptive play ─────────────────────────────────────────────────────────────


def eq_regret_matching_flat(
    payoffs: List[Float64], n_players: Int, n_actions: Int, n_iters: Int, abs_tol: Float64
) -> MixedEquilibrium:
    """Regret matching, reporting the TIME-AVERAGE strategy and its measured exploitability.

    Each player plays in proportion to its positive cumulative regret and uniformly while all
    regrets are non-positive. The returned strategy is the average over iterations, which is
    where the theory's guarantee lives — the per-iteration strategy has none — and the number
    reported beside it is the exploitability of THAT average, measured by
    `eq_exploitability_flat`'s own computation.

    `exactness` is APPROXIMATE whenever the residual is outside `abs_tol` and CLOSED_FORM is
    never claimed for the iterative path even when the residual is zero: this is an
    approximation method, and one input where it lands exactly does not make it exact. On
    matching pennies it lands on 0.5/0.5 with residual 0 (measured), which agrees with the
    frozen closed form — and `eq_solve_flat` uses the closed form there anyway, because a game
    with an exact answer should not be iterated.

    Refuses `STRAT_ERR_WORK_BUDGET` before the first iteration. The iteration count multiplies
    the entire tensor, so this is the driver where an uncharged loop becomes a hang.

    @capability eq_regret_matching_flat
    complexity: O(n_iters * n_actions ** n_players * n_players)
    counts:
    - dim n_players [kernel_validated]
    - dim n_actions [kernel_validated]
    - dim n_iters [kernel_validated]
    @endcapability
    """
    var method = EQ_METHOD_REGRET_MATCHING
    var game = eq_game_status(payoffs, n_players, n_actions)
    if game != STRAT_OK:
        return _mixed_refusal(game, method, n_players, n_actions, abs_tol)
    var tol = strat_tolerance_status(abs_tol)
    if tol != STRAT_OK:
        return _mixed_refusal(tol, method, n_players, n_actions, abs_tol)
    if n_iters < 1 or n_iters > EQ_MAX_ITERS:
        return _mixed_refusal(STRAT_ERR_DIMENSION_TOO_LARGE, method, n_players, n_actions, abs_tol)
    if eq_iteration_charge(n_players, n_actions, n_iters) < 0:
        return _mixed_refusal(STRAT_ERR_WORK_BUDGET, method, n_players, n_actions, abs_tol)
    var profiles = eq_profile_count(n_players, n_actions)
    var width = n_players * n_actions
    var regret = _zeros(width)
    var sigma = _zeros(width)
    var total = _zeros(width)
    var q = _zeros(width)
    var digits = _int_zeros(n_players)
    var pre = _zeros(n_players + 1)
    var suf = _zeros(n_players + 1)
    var uniform = _uniform_row(n_actions)
    for _ in range(n_iters):
        for i in range(n_players):
            var positive = 0.0
            for a in range(n_actions):
                var r = regret[i * n_actions + a]
                if r > 0.0:
                    positive += r
            if positive > 0.0:
                for a in range(n_actions):
                    var r = regret[i * n_actions + a]
                    if r > 0.0:
                        sigma[i * n_actions + a] = r / positive
                    else:
                        sigma[i * n_actions + a] = 0.0
            else:
                for a in range(n_actions):
                    sigma[i * n_actions + a] = uniform
        for t in range(width):
            total[t] += sigma[t]
        _sweep(payoffs, n_players, n_actions, profiles, sigma, q, digits, pre, suf)
        for i in range(n_players):
            var achieved = 0.0
            for a in range(n_actions):
                achieved += sigma[i * n_actions + a] * q[i * n_actions + a]
            for a in range(n_actions):
                regret[i * n_actions + a] += q[i * n_actions + a] - achieved
    return _finish_iterative(
        payoffs, n_players, n_actions, profiles, total, n_iters, method, abs_tol
    )


def eq_fictitious_play_flat(
    payoffs: List[Float64], n_players: Int, n_actions: Int, n_iters: Int, abs_tol: Float64
) -> MixedEquilibrium:
    """Fictitious play, reporting the EMPIRICAL frequency of play and its exploitability.

    Every player best-responds to the others' empirical frequencies so far, ties going to the
    lowest action index — `eq_tiebreak_rule()`. Beliefs start uniform, so the first move is a
    best response to uniform play rather than to an arbitrary corner.

    Convergence is genuinely slower than regret matching's and the report says so with a number
    instead of a claim: MEASURED on matching pennies the residual falls 0.104 -> 0.034 -> 0.021
    -> 0.005 at 100, 1000, 4000 and 20000 iterations, while regret matching reaches 0 at 100.
    Both are `STRAT_EXACT_APPROXIMATE` and the residual is what distinguishes them, which is
    the entire reason a converged flag alone is not enough.

    @capability eq_fictitious_play_flat
    complexity: O(n_iters * n_actions ** n_players * n_players)
    counts:
    - dim n_players [kernel_validated]
    - dim n_actions [kernel_validated]
    - dim n_iters [kernel_validated]
    @endcapability
    """
    var method = EQ_METHOD_FICTITIOUS_PLAY
    var game = eq_game_status(payoffs, n_players, n_actions)
    if game != STRAT_OK:
        return _mixed_refusal(game, method, n_players, n_actions, abs_tol)
    var tol = strat_tolerance_status(abs_tol)
    if tol != STRAT_OK:
        return _mixed_refusal(tol, method, n_players, n_actions, abs_tol)
    if n_iters < 1 or n_iters > EQ_MAX_ITERS:
        return _mixed_refusal(STRAT_ERR_DIMENSION_TOO_LARGE, method, n_players, n_actions, abs_tol)
    if eq_iteration_charge(n_players, n_actions, n_iters) < 0:
        return _mixed_refusal(STRAT_ERR_WORK_BUDGET, method, n_players, n_actions, abs_tol)
    var profiles = eq_profile_count(n_players, n_actions)
    var width = n_players * n_actions
    var counts = _zeros(width)
    var belief = _zeros(width)
    var q = _zeros(width)
    var digits = _int_zeros(n_players)
    var pre = _zeros(n_players + 1)
    var suf = _zeros(n_players + 1)
    var uniform = _uniform_row(n_actions)
    for t in range(width):
        belief[t] = uniform
    for _ in range(n_iters):
        _sweep(payoffs, n_players, n_actions, profiles, belief, q, digits, pre, suf)
        for i in range(n_players):
            var best = 0
            var best_value = q[i * n_actions]
            for a in range(1, n_actions):
                if q[i * n_actions + a] > best_value:
                    best_value = q[i * n_actions + a]
                    best = a
            counts[i * n_actions + best] += 1.0
        for i in range(n_players):
            var seen = 0.0
            for a in range(n_actions):
                seen += counts[i * n_actions + a]
            for a in range(n_actions):
                belief[i * n_actions + a] = counts[i * n_actions + a] / seen
    return _finish_iterative(
        payoffs, n_players, n_actions, profiles, counts, n_iters, method, abs_tol
    )


def _finish_iterative(
    payoffs: List[Float64], n_players: Int, n_actions: Int, profiles: Int,
    weights: List[Float64], n_iters: Int, method: Int, abs_tol: Float64,
) -> MixedEquilibrium:
    """Normalise an accumulated weight block into a strategy, then MEASURE it.

    Shared by both iterative drivers so the normalisation and the claim are written once. A row
    whose weights are all zero — reachable only if a driver never touched a player — becomes
    uniform rather than a division by zero, and the residual then reports what that costs
    instead of a NaN travelling into a struct the dispatch would refuse to serialise.
    """
    var strategy = List[Float64]()
    var uniform = _uniform_row(n_actions)
    for i in range(n_players):
        var seen = 0.0
        for a in range(n_actions):
            seen += weights[i * n_actions + a]
        for a in range(n_actions):
            if seen > 0.0:
                strategy.append(weights[i * n_actions + a] / seen)
            else:
                strategy.append(uniform)
    var audit = _exploit_core(payoffs, n_players, n_actions, profiles, strategy, abs_tol)
    if audit.status != STRAT_OK:
        return _mixed_refusal(audit.status, method, n_players, n_actions, abs_tol)
    return MixedEquilibrium(
        STRAT_OK, STRAT_EXACT_APPROXIMATE, method, n_players, n_actions, n_iters,
        audit.is_equilibrium, True, audit.residual, True, audit.value, abs_tol, False,
        strategy^,
    )


def eq_best_response_flat(
    payoffs: List[Float64], n_players: Int, n_actions: Int, start_profile: Int,
    max_rounds: Int, abs_tol: Float64,
) -> BestResponsePath:
    """Sequential best-response dynamics from one pure profile, and whether it settles.

    Players move in index order; each switches to its best response against the others' current
    actions, ties to the lowest index. A full sweep with no switch means the profile is a pure
    equilibrium, verified by `eq_pure_gains_flat` rather than inferred from the loop exiting.

    `STRAT_ERR_NOT_CONVERGED` when `max_rounds` sweeps pass without settling — which is not a
    failure of the implementation but a property of the game: on matching pennies the dynamic
    cycles forever, and the honest report is a refusal that still names where it stopped and how
    exploitable that profile is. Returning the final profile as an equilibrium would be a wrong
    answer nothing downstream could detect.

    `max_rounds` is bounded by `eq_best_response_charge`, which charges the `n_players *
    n_actions` reads a round actually costs. The tensor is never swept here — a pure profile
    needs no product measure — so charging this with the iterative sweep would refuse rounds
    that cost microseconds.

    @capability eq_best_response_flat
    complexity: O(max_rounds * n_players * n_actions)
    counts:
    - dim n_players [kernel_validated]
    - dim n_actions [kernel_validated]
    - dim start_profile [kernel_validated]
    - dim max_rounds [kernel_validated]
    @endcapability
    """
    var game = eq_game_status(payoffs, n_players, n_actions)
    if game != STRAT_OK:
        return _path_refusal(game, start_profile)
    var tol = strat_tolerance_status(abs_tol)
    if tol != STRAT_OK:
        return _path_refusal(tol, start_profile)
    var profiles = eq_profile_count(n_players, n_actions)
    if start_profile < 0 or start_profile >= profiles:
        return _path_refusal(STRAT_ERR_ACTION_RANGE, start_profile)
    if max_rounds < 1 or max_rounds > EQ_MAX_ITERS:
        return _path_refusal(STRAT_ERR_DIMENSION_TOO_LARGE, start_profile)
    if eq_best_response_charge(n_players, n_actions, max_rounds) < 0:
        return _path_refusal(STRAT_ERR_WORK_BUDGET, start_profile)
    var actions = _int_zeros(n_players)
    for i in range(n_players):
        actions[i] = eq_profile_action(start_profile, i, n_players, n_actions)
        if actions[i] < 0:
            return _path_refusal(STRAT_ERR_ACTION_RANGE, start_profile)
    var strides = _int_zeros(n_players)
    for i in range(n_players):
        strides[i] = eq_profile_stride(i, n_players, n_actions)
        if strides[i] < 1:
            # See `eq_pure_nash_flat`: a negative stride turns the deviation scan into a
            # negative subscript, which aborts the process instead of returning a wrong number.
            return _path_refusal(STRAT_ERR_DIMENSION_TOO_LARGE, start_profile)
    var profile = start_profile
    var switches = 0
    var rounds = 0
    var settled = False
    for _ in range(max_rounds):
        rounds += 1
        var moved = False
        for i in range(n_players):
            var base = profile - actions[i] * strides[i]
            var best = actions[i]
            var best_value = payoffs[i * profiles + profile]
            for b in range(n_actions):
                var alt = payoffs[i * profiles + base + b * strides[i]]
                if alt > best_value:
                    best_value = alt
                    best = b
            if best != actions[i]:
                actions[i] = best
                profile = base + best * strides[i]
                switches += 1
                moved = True
        if not moved:
            settled = True
            break
    var audit = eq_pure_gains_flat(payoffs, n_players, n_actions, actions, abs_tol)
    if audit.status != STRAT_OK:
        return BestResponsePath(
            audit.status, STRAT_EXACT_UNKNOWN, EQ_METHOD_BEST_RESPONSE, settled, rounds,
            switches, start_profile, profile, False, strat_absent(),
        )
    var claim = STRAT_EXACT_APPROXIMATE
    if audit.is_equilibrium:
        claim = STRAT_EXACT_CLOSED_FORM
    var status = STRAT_OK
    if not settled:
        status = STRAT_ERR_NOT_CONVERGED
    return BestResponsePath(
        status, claim, EQ_METHOD_BEST_RESPONSE, settled, rounds, switches, start_profile,
        profile, True, audit.residual,
    )


# ── the dispatcher: the exact answer when one exists, and it says which ───────


def eq_solve_flat(
    payoffs: List[Float64], n_players: Int, n_actions: Int, n_iters: Int, abs_tol: Float64,
    require_exact: Bool,
) -> MixedEquilibrium:
    """Solve for a mixed equilibrium, using the FROZEN closed form wherever it applies.

    A 2x2 game goes to `game_theory.nash_2x2` — running an iterative solver on a game with an
    exact closed form would return an approximation to an answer the tree already has exactly.
    Above 2x2 the solver is regret matching, whose result is `STRAT_EXACT_APPROXIMATE` and
    carries its residual.

    `require_exact` is the caller's way of refusing an approximation: with it set, any shape
    without a closed form returns `STRAT_ERR_NOT_EXACT` rather than an APPROXIMATE result the
    caller would have to inspect to discover is not exact. That is what code 474 is for — a
    caller that needs an exact equilibrium and silently receives an eps-equilibrium has been
    given a wrong answer with a plausible shape.

    @capability eq_solve_flat
    complexity: O(n_iters * n_actions ** n_players * n_players)
    counts:
    - dim n_players [kernel_validated]
    - dim n_actions [kernel_validated]
    - dim n_iters [kernel_validated]
    @endcapability
    """
    var game = eq_game_status(payoffs, n_players, n_actions)
    if game != STRAT_OK:
        return _mixed_refusal(game, EQ_METHOD_REGRET_MATCHING, n_players, n_actions, abs_tol)
    if n_players == 2 and n_actions == 2:
        var payoff_a = List[Float64]()
        var payoff_b = List[Float64]()
        for t in range(4):
            payoff_a.append(payoffs[t])
        for t in range(4):
            payoff_b.append(payoffs[4 + t])
        return eq_nash_2x2_flat(payoff_a, payoff_b, abs_tol)
    if require_exact:
        return _mixed_refusal(
            STRAT_ERR_NOT_EXACT, EQ_METHOD_REGRET_MATCHING, n_players, n_actions, abs_tol
        )
    return eq_regret_matching_flat(payoffs, n_players, n_actions, n_iters, abs_tol)


# ── two frozen kernels, generalised only where they have no form ──────────────


def eq_zero_sum_bounds_flat(
    payoff_a: List[Float64], payoff_b: List[Float64], rows: Int, cols: Int, abs_tol: Float64
) -> ZeroSumBounds:
    """The lower and upper values of a zero-sum matrix game, from the FROZEN minimax kernel.

    `lower_value = game_theory.minimax_value(A)` is the row player's maximin. `upper_value` is
    the column player's minimax and is obtained from the SAME frozen kernel applied to the
    negated transpose: `max_j min_i (-A[i][j]) = -min_j max_i A[i][j]`. Two calls, one kernel,
    no second implementation of a min-max scan.

    Zero-sumness is verified before either bound is reported. `sum_defect` is the largest
    `|A[i][j] + B[i][j]|`, judged against zero with a tolerance scaled to the entry being
    judged; a pair that fails is refused with `STRAT_ERR_NOT_EVALUABLE` and the defect is
    reported, because "these bounds do not apply to your game" is only actionable with the
    measurement that says why.

    `gap == 0` iff the game has a pure saddle point, which makes `saddle` an exact structural
    answer and the cheapest available check on whether mixing is needed at all.

    @capability eq_zero_sum_bounds_flat
    complexity: O(rows * cols)
    counts:
    - rows * cols == len(payoff_a, payoff_b) [kernel_validated]
    - dim rows [kernel_validated]
    - dim cols [kernel_validated]
    @endcapability
    """
    var tol = strat_tolerance_status(abs_tol)
    if tol != STRAT_OK:
        return _bounds_refusal(tol, rows, cols)
    if rows < 1 or rows > STRAT_MAX_ACTIONS or cols < 1 or cols > STRAT_MAX_ACTIONS:
        return _bounds_refusal(STRAT_ERR_ACTION_RANGE, rows, cols)
    if not strat_dims_fit(rows, cols, len(payoff_a)):
        return _bounds_refusal(STRAT_ERR_SHAPE, rows, cols)
    if not strat_dims_fit(rows, cols, len(payoff_b)):
        return _bounds_refusal(STRAT_ERR_SHAPE, rows, cols)
    if not strat_all_finite(payoff_a, len(payoff_a)):
        return _bounds_refusal(STRAT_ERR_NON_FINITE, rows, cols)
    if not strat_all_finite(payoff_b, len(payoff_b)):
        return _bounds_refusal(STRAT_ERR_NON_FINITE, rows, cols)
    var defect = 0.0
    var zero_sum = True
    for t in range(rows * cols):
        var total = payoff_a[t] + payoff_b[t]
        if not strat_finite(total):
            return _bounds_refusal(STRAT_ERR_NON_FINITE, rows, cols)
        var magnitude = total
        if magnitude < 0.0:
            magnitude = -magnitude
        if magnitude > defect:
            defect = magnitude
        if not strat_agrees(payoff_a[t], -payoff_b[t], abs_tol, 0):
            zero_sum = False
    if not zero_sum:
        return ZeroSumBounds(
            STRAT_ERR_NOT_EVALUABLE, rows, cols, False, strat_absent(), False, strat_absent(),
            False, strat_absent(), False, True, defect,
        )
    var nested_a = _nested(payoff_a, 0, rows, cols)
    var lower = minimax_value(nested_a)
    var transposed = List[Float64]()
    for j in range(cols):
        for i in range(rows):
            transposed.append(-payoff_a[i * cols + j])
    var upper = -minimax_value(_nested(transposed, 0, cols, rows))
    if not strat_finite(lower) or not strat_finite(upper):
        return _bounds_refusal(STRAT_ERR_PAYOFF_ABSENT, rows, cols)
    var gap = upper - lower
    if not strat_finite(gap):
        return _bounds_refusal(STRAT_ERR_PAYOFF_ABSENT, rows, cols)
    return ZeroSumBounds(
        STRAT_OK, rows, cols, True, lower, True, upper, True, gap,
        strat_agrees(upper, lower, abs_tol, 0), True, defect,
    )


def eq_dominated_actions_flat(
    payoffs: List[Float64], n_players: Int, n_actions: Int, player: Int
) -> DominanceReport:
    """Which of `player`'s actions are strictly dominated, and which kernel decided it.

    For a TWO-PLAYER game the frozen `game_theory.dominated_strategy_check` decides — for both
    players, because the column player's own matrix (its actions as rows, the row player's as
    columns) is built here and handed to the same kernel. For three players and up there is no
    frozen form, so the scan is done here over the tensor: action `b` dominates `a` iff
    `u_i(b, rest) > u_i(a, rest)` at EVERY opponent profile.

    The two paths must agree on the two-player shape, and `test_strategy_equilibrium.mojo`
    asserts they do on the Prisoner's Dilemma, where cooperate is strictly dominated for both
    players. `method` reports which one ran, so a caller reading a result knows whether it came
    from the frozen kernel or the generalisation.

    Bounded by `eq_enumeration_charge`: the tensor scan costs `profiles * n_actions` reads,
    which that charge over-states rather than a second cost model that could drift from it.

    @capability eq_dominated_actions_flat
    complexity: O(n_actions ** n_players * n_actions)
    counts:
    - dim n_players [kernel_validated]
    - dim n_actions [kernel_validated]
    - dim player [kernel_validated]
    @endcapability
    """
    var game = eq_game_status(payoffs, n_players, n_actions)
    if game != STRAT_OK:
        return _dominance_refusal(game, player, n_actions)
    if player < 0 or player >= n_players:
        return _dominance_refusal(STRAT_ERR_PLAYER_COUNT, player, n_actions)
    if eq_enumeration_charge(n_players, n_actions) < 0:
        return _dominance_refusal(STRAT_ERR_WORK_BUDGET, player, n_actions)
    var profiles = eq_profile_count(n_players, n_actions)
    var stride = eq_profile_stride(player, n_players, n_actions)
    if stride < 0:
        return _dominance_refusal(STRAT_ERR_DIMENSION_TOO_LARGE, player, n_actions)
    var flags = List[Bool]()
    var method = EQ_METHOD_TENSOR_DOMINANCE
    if n_players == 2:
        # The frozen kernel's own shape: this player's actions as rows, the opponent's as
        # columns. For player 0 that is the tensor block as stored; for player 1 it is the
        # transpose of its block, which is built rather than the kernel reimplemented.
        method = EQ_METHOD_CLOSED_FORM_2X2
        var own = List[Float64]()
        if player == 0:
            for t in range(profiles):
                own.append(payoffs[t])
        else:
            for a1 in range(n_actions):
                for a0 in range(n_actions):
                    own.append(payoffs[profiles + a0 * n_actions + a1])
        flags = dominated_strategy_check(_nested(own, 0, n_actions, n_actions))
    else:
        var others = profiles // n_actions
        for a in range(n_actions):
            var dominated = False
            for b in range(n_actions):
                if b == a:
                    continue
                var everywhere = True
                for block in range(others):
                    # Opponent profiles are the tensor index with this player's digit removed:
                    # the high part above the stride and the low part below it.
                    var high = block // stride
                    var low = block % stride
                    var base = high * stride * n_actions + low
                    var here = payoffs[player * profiles + base + a * stride]
                    var alt = payoffs[player * profiles + base + b * stride]
                    if alt <= here:
                        everywhere = False
                        break
                if everywhere:
                    dominated = True
                    break
            flags.append(dominated)
    var n_dominated = 0
    for a in range(len(flags)):
        if flags[a]:
            n_dominated += 1
    return DominanceReport(STRAT_OK, method, player, n_actions, n_dominated, flags^)
