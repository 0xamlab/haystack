"""
strategy.tournament — rank strategies from a PAIRED comparison, with an honest verdict.

Zero Python imports. Every number here is produced by a frozen kernel or by
`strategy.contract`: `stats.compute_mean` / `compute_variance` for the moments,
`discrete_event.replicate.replicate_ci_flat` for the per-strategy Student-t interval,
`inference.core.inference_t_sf_two_sided` for the paired-t p-value,
`inference.multiplicity` for the family-wise correction, `evaluation.resample`'s coordinate map
and `determinism.sampling_keyed` for the paired bootstrap. None of them is reimplemented here.

The input is an OUTCOME MATRIX, not a simulator
-----------------------------------------------
`outcomes` is a flat `n_strategies x n_replications` row-major block: cell `(s, r)` is what
strategy `s` scored on scenario `r`. Column `r` is THE SAME SCENARIO for every strategy — that is
the whole content of common random numbers, and it is why the comparison here is paired.
`strategy.crn` draws the scenarios and evaluates the policies; this module does nothing but
compare, so the two can be tested separately and a caller with outcomes from anywhere else
(a backtest, a replay, a physical trial) can still use the ranking.

The pairing is MEASURED, not assumed. Every pair reports two variances:

    paired_variance    = Var(a_r - b_r)          over replications
    unpaired_variance  = Var(a) + Var(b)         the variance the same difference would have
                                                  if the two strategies had been run on
                                                  INDEPENDENT scenario draws

`Var(a - b) = Var(a) + Var(b) - 2 Cov(a, b)`, so the first is below the second exactly when
common random numbers induced positive covariance — which is the entire reason to pair. The ratio
is reported per pair and the minimum over pairs is reported for the tournament, so a caller that
handed in an UNPAIRED matrix sees a ratio of about 1.0 rather than a claim of pairing it never
had.

It is reported and NOT enforced, deliberately. A constant strategy has `Var(a) = 0`, so
`Var(a - b) = Var(b) = Var(a) + Var(b)` exactly — the ratio is 1.0 under PERFECT pairing. A
driver that refused to rank unless every pair showed a strict reduction would therefore refuse a
correct, well-paired tournament that happens to contain a constant strategy. So
`all_pairs_paired_lower` is a fact about the data, next to the number it was computed from.

Three outcomes per comparison, because two would be a coin flip
--------------------------------------------------------------
A tournament that always names a winner is a random number generator with extra steps. The
verdict vocabulary is `strategy.contract`'s, and all four values are reachable:

  * `NO_DIFFERENCE` — the comparison was made and the two are indistinguishable at this alpha
    AFTER correction. A VALUE, not a missing winner.
  * `A_BETTER` / `B_BETTER` — the corrected p-value rejects and the sign says which.
  * `UNDECIDED` — the comparison could not be MADE. Never collapsed into `NO_DIFFERENCE`:
    "we tested and found no difference" and "we could not test" are different findings, and
    `strat_verdict_is_decided` separates them for exactly this reason.

`evaluation.gates.GateResult` set the precedent by keeping `decided` apart from `passed`.

Multiplicity, and why it is visible in the result
------------------------------------------------
`n` strategies is `n(n-1)/2` comparisons, and at 20 strategies that is 190 tests: at
alpha = 0.05 an uncorrected family expects nine or ten false "significant" verdicts even when
every strategy is identical. So every p-value goes through `inference.multiplicity` —
Bonferroni, Holm or Benjamini-Hochberg, the caller's choice — and the result reports
`n_comparisons`, `method_name`, `n_significant` AND `n_significant_uncorrected` side by side, so
a reader sees that the correction changed something rather than taking it on trust. The suite
pins a case where it changes a verdict: an uncorrected p of 0.0474 becomes an adjusted 0.1423
and the pair drops from "significant" to "no significant difference".

Refusal, not partial credit
---------------------------
If ANY strategy's interval cannot be formed, or ANY pair's p-value cannot be computed, the whole
tournament is refused. A ranking over the strategies that happened to succeed reports a winner
of a competition the others were removed from, and the correction over a shrunken family
understates the family size as well. `STRAT_ERR_TOO_FEW_REPLICATIONS`, `STRAT_ERR_NON_FINITE`
and `STRAT_ERR_NO_ESTIMATE` are the three ways that happens and each says which.

Bounding memory is not bounding work
------------------------------------
MEASURED on this tree, in situ, from the slope of nineteen real shapes: one per-strategy interval
costs 236-250 MICROSECONDS — that is one `inference_t_quantile` bisection and nothing else — and
one per-pair p-value costs 1.4-1.6 microseconds against about 6 nanoseconds for a per-replication
difference. The interval is a hundred and fifty times the cost of a p-value and four orders of
magnitude more than a subtraction, and NONE of that is visible in
`n_strategies * n_replications`, which is the only product a naive charge would use. A
1024-strategy tournament allocates 8 MB and spends a quarter of a second per hundred strategies
inside the frozen quantile alone, and from the caller's side an accepted request that runs for a
wall-clock second is indistinguishable from a hang. So the charge is

    n_strategies * (TOURNEY_CI_WEIGHT + n_replications * TOURNEY_STAT_WEIGHT)
  + n_pairs      * (TOURNEY_TEST_WEIGHT + n_replications * TOURNEY_DIFF_WEIGHT)

against `strategy.contract.STRAT_MAX_WORK`, every product grown by DIVISION and every sum
checked against the remaining headroom, because `a + b` wraps exactly as `a * b` does. The result
is that 1024 strategies at two replications — a 2048-cell block, inside every allocation ceiling
in the package — is REFUSED, and the largest family accepted at two replications is 374. The
seven accepted shapes the benchmark measures span 0.20 to 0.86 nanoseconds per charged unit on an
idle machine, and 0.26 to 1.54 with two other compilers competing for the CPU; the slowest
finishes in 460 ms idle and 827 ms contended. Both figures are given because the second is why the
benchmark's band is wide: the charge model is being judged through a measurement that itself
varies by 3-7x on this machine.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: optional
supported_dtypes: float64, int64, bool
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_strategy_tournament.mojo
benchmark: benchmarks/mojo_benchmarks/bench_strategy.mojo
docs: gitbook/engine/strategy-simulation.md
version_introduced: 2026.07.31
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, sqrt

from determinism.counter_rng import rng_version
from determinism.sampling_keyed import uniform_int_keyed
from determinism.streams import stream_id
from discrete_event.contract import (
    DE_ERR_COUNT,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_LEVEL_RANGE,
    DE_ERR_NON_FINITE,
    DE_ERR_NO_ESTIMATE,
    DE_ERR_TOO_FEW_REPS,
    DE_OK,
)
from discrete_event.replicate import replicate_ci_flat
from evaluation.contract import EVAL_MAX_RESAMPLES
from evaluation.resample import EVAL_BOOTSTRAP_STREAM_NAME, bootstrap_draw_index
from inference.core import (
    INF_ERR_ALPHA_RANGE,
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_EMPTY,
    INF_ERR_SHAPE,
    INF_OK,
    inference_t_sf_two_sided,
)
from inference.multiplicity import (
    METHOD_BH,
    METHOD_BONFERRONI,
    METHOD_HOLM,
    benjamini_hochberg_flat,
    bonferroni_flat,
    holm_flat,
)
from stats import compute_mean, compute_variance, quantile

from strategy.contract import (
    STRAT_DRAW_WEIGHT,
    STRAT_ERR_COUNT,
    STRAT_ERR_DEGENERATE,
    STRAT_ERR_DIMENSION_TOO_LARGE,
    STRAT_ERR_EMPTY,
    STRAT_ERR_LEVEL_RANGE,
    STRAT_ERR_NON_FINITE,
    STRAT_ERR_NO_ESTIMATE,
    STRAT_ERR_SEED_RANGE,
    STRAT_ERR_SHAPE,
    STRAT_ERR_TOO_FEW_REPLICATIONS,
    STRAT_ERR_TOO_FEW_STRATEGIES,
    STRAT_ERR_UNKNOWN_METHOD,
    STRAT_ERR_WORK_BUDGET,
    STRAT_MAX_PAIRS,
    STRAT_MAX_REPLICATIONS,
    STRAT_MAX_STRATEGIES,
    STRAT_MAX_WORK,
    STRAT_OK,
    STRAT_VERDICT_A_BETTER,
    STRAT_VERDICT_B_BETTER,
    STRAT_VERDICT_NO_DIFFERENCE,
    STRAT_VERDICT_UNDECIDED,
    strat_absent,
    strat_agrees,
    strat_all_finite,
    strat_dims_fit,
    strat_finite,
    strat_level_status,
    strat_product_fits,
    strat_tolerance_status,
)

# ── correction methods: TAGS, not statuses ────────────────────────────────────
# Zero-based tags like `STRAT_VERDICT_*` and `EVAL_METRIC_*`, deliberately outside 450-489 so a
# caller can never read a method selector as a status. The NAMES come from
# `inference.multiplicity` (`tourney_method_name`), never re-spelled here: a second spelling of
# "holm_bonferroni_step_down" in a stored record is how two runs of the same procedure end up
# looking like two procedures.

comptime TOURNEY_METHOD_BONFERRONI: Int = 0
comptime TOURNEY_METHOD_HOLM: Int = 1
comptime TOURNEY_METHOD_BH: Int = 2
comptime TOURNEY_METHOD_COUNT: Int = 3

# ── measured work weights ─────────────────────────────────────────────────────
# One work unit is `strategy.contract`'s unit: one policy-step-factor operation, 1.48 ns as
# measured for the contract's own charge. These four weights convert this module's real costs
# into that unit, and every one of them is FITTED TO MEASUREMENT of the real driver at nineteen
# shapes, not read off a micro-benchmark. The two are not the same number: a micro-benchmark of
# `inference_t_quantile` in a tight loop reported anywhere from 266 to 1245 microseconds per call
# depending on how the loop was written, while the same call inside `tourney_rank_flat` measured
# a stable 236-250 microseconds across ten strategy counts at a fixed replication count. Timing
# on this machine under the JIT carries a 3-7x spread between repetitions of an IDENTICAL call,
# so every number below is the MINIMUM of five to eight repetitions — the minimum is the robust
# estimator here, because scheduler noise only ever adds time.

# One per-strategy interval: one `replicate_ci_flat`, whose cost is one `inference_t_quantile`
# bisection. MEASURED in situ at 236-250 us per strategy, from the slope of ten shapes at two
# replications (473 us at two strategies through 455 ms at 374).
#
# 2^20 units is 1.55 ms, which OVER-CHARGES that by about six times, and the over-charge is
# deliberate and load-bearing: the per-pair cost is NOT constant. It measured 1.82 us per pair at
# 32640 pairs and 5.18 us at 69751 — a superlinearity in the pair count that a product-shaped
# charge cannot express at all. The strategy count is what drives the pair count (quadratically),
# so absorbing the superlinearity into the weight that scales with the strategy count is the only
# honest place to put it. The consequence is stated rather than hidden: a small tournament is
# charged several times what it costs, and no accepted tournament costs more than its charge
# implies. Under-charging is the failure that matters, because from the caller's side an accepted
# request that runs for a wall-clock minute is indistinguishable from the uncatchable abort.
comptime TOURNEY_CI_WEIGHT: Int = 1 << 20

# One pair's p-value: one `inference_t_sf_two_sided`. MEASURED 1350-1615 ns across |t| from 0.1
# to 5000 at df 63 and df 1 — flat in both, so the tail path is not a cost cliff. 1615 / 1.48 =
# 1091 units, rounded UP to 2^11 = 2048.
comptime TOURNEY_TEST_WEIGHT: Int = 2048

# One (pair, replication): a subtract into the difference list, the finiteness sweep, and the two
# frozen passes that mean and variance it. MEASURED as the slope of the replication sweep at two
# strategy counts: 7.7 ns per (pair, replication) at 2016 pairs and 17-41 ns at 10731 and 27966
# pairs, where two rows of 4096 doubles no longer fit in cache. 41 / 1.48 = 27.7 units, rounded UP
# to 32. The first version of this file charged 8 and MEASURED the consequence: replication-heavy
# shapes ran 1.29 s against 0.47 s for a strategy-heavy shape at an identical declared charge, a
# 2.7x mis-ranking of the same kind as the 0.49-s-versus-23.89-s defect this tree already paid
# for. At 32 the worst accepted shape is half a second.
comptime TOURNEY_DIFF_WEIGHT: Int = 32

# One (strategy, replication): the row copy plus `replicate_ci_flat`'s three passes over it.
# MEASURED at 14 ns from the same sweep; 14 / 1.48 = 9.5 units, rounded UP to 16.
comptime TOURNEY_STAT_WEIGHT: Int = 16

# The smallest family a ranking can be made from. TWO strategies is one comparison; ONE strategy
# has a mean and an interval and NOTHING to rank, which is `STRAT_ERR_TOO_FEW_STRATEGIES` rather
# than a tournament of one that trivially names its only member the winner.
comptime TOURNEY_MIN_STRATEGIES: Int = 2


def tourney_method_name(method: Int) -> String:
    """The multiplicity procedure's name, from `inference.multiplicity`, for a method tag.

    The strings are the frozen `METHOD_*` constants of the module that implements the
    procedures, so a stored tournament and a stored correction name the same method with the
    same characters. Returns `"unknown_method"` for a tag outside the vocabulary rather than a
    plausible default, because a silently-substituted correction is a family-wise error rate
    nobody chose.

    @capability tourney_method_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if method == TOURNEY_METHOD_BONFERRONI:
        return METHOD_BONFERRONI
    if method == TOURNEY_METHOD_HOLM:
        return METHOD_HOLM
    if method == TOURNEY_METHOD_BH:
        return METHOD_BH
    return String("unknown_method")


def tourney_pair_count(n_strategies: Int) -> Int:
    """`n(n-1)/2` — the number of unordered pairs — or -1 when that is not representable.

    Formed as `(n // 2) * (n - 1)` when `n` is even and `n * ((n - 1) // 2)` when it is odd, so
    the DIVISION happens before the multiply and the intermediate `n * (n - 1)` never exists.
    That matters at the ceiling: 1024 * 1023 is small, but the general shape of "multiply then
    halve" is the wrapping multiply this tree has already been bitten by, and there is no reason
    to write it once more.

    -1 for fewer than two strategies (no pair exists), above `STRAT_MAX_STRATEGIES`, and for a
    count whose pair total would exceed `STRAT_MAX_PAIRS` — which is `inference.core.MAX_TESTS`,
    so an accepted tournament's pair family is always something `inference.multiplicity` can
    correct.

    @capability tourney_pair_count
    complexity: O(1)
    counts: none
    @endcapability
    """
    if n_strategies < TOURNEY_MIN_STRATEGIES:
        return -1
    if n_strategies > STRAT_MAX_STRATEGIES:
        return -1
    var pairs: Int
    if n_strategies % 2 == 0:
        pairs = (n_strategies // 2) * (n_strategies - 1)
    else:
        pairs = n_strategies * ((n_strategies - 1) // 2)
    if pairs > STRAT_MAX_PAIRS:
        return -1
    return pairs


def tourney_outcome_cell(strategy: Int, replication: Int, n_replications: Int) -> Int:
    """The row-major offset of outcome `(strategy, replication)`, or -1 if not addressable.

    `strategy * n_replications + replication`. -1 for a negative index, for a replication at or
    above `n_replications`, and for a product that would wrap — a negative subscript is an
    uncatchable abort and a wrapped one reads another strategy's row as this one's, which is a
    wrong answer with nothing to notice.

    STRATEGY-MAJOR, matching `strat_policy_row_start`'s parameter block: one strategy's
    replications are contiguous, so the per-strategy statistics read a contiguous run and the
    layout is the same one the policy block already uses. `strategy.crn.crn_evaluate_policies`
    fills its payoff block at this same offset, so its output is this module's input unchanged.

    @capability tourney_outcome_cell
    complexity: O(1)
    counts: none
    @endcapability
    """
    if strategy < 0 or replication < 0 or n_replications <= 0:
        return -1
    if replication >= n_replications:
        return -1
    if not strat_product_fits(strategy, n_replications, STRAT_MAX_WORK):
        return -1
    var base = strategy * n_replications
    if base > STRAT_MAX_WORK - replication:
        return -1
    return base + replication


def tourney_outcome_status(
    outcomes: List[Float64], n_strategies: Int, n_replications: Int
) -> Int:
    """`STRAT_OK` when `outcomes` is exactly an `n_strategies x n_replications` finite block.

    The one guard every entry point here runs first, in this order:

      * `STRAT_ERR_TOO_FEW_STRATEGIES` below one strategy, `STRAT_ERR_DIMENSION_TOO_LARGE`
        above the ceiling. One strategy is accepted HERE — evaluating a single strategy is a
        legitimate request and only ranking needs two, so the two-strategy rule belongs to the
        driver that needs it rather than to the shape check.
      * `STRAT_ERR_TOO_FEW_REPLICATIONS` below two replications. Not `STRAT_ERR_EMPTY`: one
        replication has a mean and no interval, and every comparison this module makes is an
        interval. This is also how "fewer replications than the CI needs" arrives.
      * `STRAT_ERR_SHAPE` when the length is not the product, decided by DIVISION through the
        frozen `dims_fit`, because `n_strategies * n_replications` is a wrapping multiply and a
        shape check that wraps is not a check.
      * `STRAT_ERR_NON_FINITE` for a NaN or an infinity anywhere in the block, checked LAST
        because it is the only O(n) test and there is nothing to scan in a block whose shape is
        already wrong. A non-finite outcome is refused rather than ranked around: it propagates
        into a mean, a variance and a p-value, and the dispatch then refuses the whole response.

    @capability tourney_outcome_status
    complexity: O(n_strategies * n_replications)
    counts:
    - n_strategies * n_replications == len(outcomes) [kernel_validated]
    - dim n_strategies [kernel_validated]
    - dim n_replications [kernel_validated]
    @endcapability

    The two dimensions are declared WITHOUT naming their ceilings. A declared ceiling must name a
    `comptime` constant in the SAME file, and `STRAT_MAX_STRATEGIES` and
    `STRAT_MAX_REPLICATIONS` live in `strategy.contract`, which is the one place they are
    defined — copying either value here is exactly the drift rule 3 warns about, and it would
    create a second number that could disagree with the one this kernel actually tests.
    `evaluation.resample` reached the same conclusion for the same reason. Both ceilings ARE
    checked, four lines below.
    """
    if n_strategies < 1:
        return STRAT_ERR_TOO_FEW_STRATEGIES
    if n_strategies > STRAT_MAX_STRATEGIES:
        return STRAT_ERR_DIMENSION_TOO_LARGE
    if n_replications < 2:
        return STRAT_ERR_TOO_FEW_REPLICATIONS
    if n_replications > STRAT_MAX_REPLICATIONS:
        return STRAT_ERR_DIMENSION_TOO_LARGE
    if not strat_dims_fit(n_strategies, n_replications, len(outcomes)):
        return STRAT_ERR_SHAPE
    if not strat_all_finite(outcomes, len(outcomes)):
        return STRAT_ERR_NON_FINITE
    return STRAT_OK


def tourney_work_charge(n_strategies: Int, n_replications: Int) -> Int:
    """What ranking this shape costs in contract work units, or -1 when it does not fit.

        n_strategies * (TOURNEY_CI_WEIGHT + n_replications * TOURNEY_STAT_WEIGHT)
      + n_pairs      * (TOURNEY_TEST_WEIGHT + n_replications * TOURNEY_DIFF_WEIGHT)

    The two FIXED weights are what a naive `n_strategies * n_replications` charge misses, and
    they are the ones that dominate: one interval costs a millisecond of frozen bisection and one
    p-value costs two microseconds, against six nanoseconds for a per-replication difference. At
    1024 strategies the fixed terms alone are 1.07e9 units against a 5.37e8 ceiling, so the
    request is refused — correctly, because it would spend 1.2 s in the quantile and another
    1.2 s across 523776 p-values before producing anything.

    Every product is grown factor by factor through division and every sum is checked against
    the remaining headroom first, because `a + b` wraps exactly as `a * b` does and a wrapped
    total reads as cheap. -1 rather than a status code, because a charge is a NUMBER and this is
    the "no such number" answer.

    @capability tourney_work_charge
    complexity: O(1)
    counts: none
    @endcapability
    """
    if n_strategies < TOURNEY_MIN_STRATEGIES or n_strategies > STRAT_MAX_STRATEGIES:
        return -1
    if n_replications < 2 or n_replications > STRAT_MAX_REPLICATIONS:
        return -1
    var pairs = tourney_pair_count(n_strategies)
    if pairs < 0:
        return -1

    # Per-strategy: one interval each, plus the three statistic passes over its row.
    if not strat_product_fits(n_replications, TOURNEY_STAT_WEIGHT, STRAT_MAX_WORK):
        return -1
    var per_strategy = TOURNEY_CI_WEIGHT + n_replications * TOURNEY_STAT_WEIGHT
    if not strat_product_fits(n_strategies, per_strategy, STRAT_MAX_WORK):
        return -1
    var strategy_charge = n_strategies * per_strategy

    # Per-pair: one p-value each, plus the difference loop over the replications.
    if not strat_product_fits(n_replications, TOURNEY_DIFF_WEIGHT, STRAT_MAX_WORK):
        return -1
    var per_pair = TOURNEY_TEST_WEIGHT + n_replications * TOURNEY_DIFF_WEIGHT
    if not strat_product_fits(pairs, per_pair, STRAT_MAX_WORK):
        return -1
    var pair_charge = pairs * per_pair

    if strategy_charge > STRAT_MAX_WORK - pair_charge:
        return -1
    return strategy_charge + pair_charge


def _de_to_strat(code: Int) -> Int:
    """Translate a `discrete_event` status into this package's vocabulary.

    `replicate_ci_flat` is the frozen-for-our-purposes interval builder and it answers in
    400-419. Leaking those codes to a `strategy` caller would put two vocabularies in one
    response and a caller would have to know which module answered to read the number.
    Anything unrecognised becomes `STRAT_ERR_NO_ESTIMATE` — "no interval exists" — rather than
    `STRAT_OK`, so a code this table does not know can never be mistaken for success.
    """
    if code == DE_OK:
        return STRAT_OK
    if code == DE_ERR_NON_FINITE:
        return STRAT_ERR_NON_FINITE
    if code == DE_ERR_EMPTY:
        return STRAT_ERR_EMPTY
    if code == DE_ERR_COUNT:
        return STRAT_ERR_COUNT
    if code == DE_ERR_DIMENSION_TOO_LARGE:
        return STRAT_ERR_DIMENSION_TOO_LARGE
    if code == DE_ERR_LEVEL_RANGE:
        return STRAT_ERR_LEVEL_RANGE
    if code == DE_ERR_TOO_FEW_REPS:
        return STRAT_ERR_TOO_FEW_REPLICATIONS
    if code == DE_ERR_NO_ESTIMATE:
        return STRAT_ERR_NO_ESTIMATE
    return STRAT_ERR_NO_ESTIMATE


def _inf_to_strat(code: Int) -> Int:
    """Translate an `inference` status into this package's vocabulary. Same rule as `_de_to_strat`.

    A p-value family this module BUILT and `inference.multiplicity` then refuses means the
    p-values are not usable, which is `STRAT_ERR_NO_ESTIMATE` and not a caller-argument defect.
    """
    if code == INF_OK:
        return STRAT_OK
    if code == INF_ERR_EMPTY:
        return STRAT_ERR_EMPTY
    if code == INF_ERR_SHAPE:
        return STRAT_ERR_SHAPE
    if code == INF_ERR_DIMENSION_TOO_LARGE:
        return STRAT_ERR_DIMENSION_TOO_LARGE
    if code == INF_ERR_ALPHA_RANGE:
        return STRAT_ERR_LEVEL_RANGE
    return STRAT_ERR_NO_ESTIMATE


def _row_copy(outcomes: List[Float64], start: Int, n: Int) -> List[Float64]:
    """Copy `n` values from `start`. The caller has ALREADY validated the range.

    Private, and the two validations that make it safe are `tourney_outcome_status` (the block is
    exactly `n_strategies x n_replications`) and `tourney_outcome_cell` (the row start is
    addressable). Both run before any call to this, and it re-checks anyway — returning an empty
    list rather than reading — because a read past a `List` end is an uncatchable process abort
    and a guard on a subscript is never redundant.
    """
    var out = List[Float64](capacity=n if n > 0 else 1)
    if start < 0 or n <= 0:
        return out^
    if start > len(outcomes) - n:
        return out^
    for i in range(n):
        out.append(outcomes[start + i])
    return out^


struct _PairStat(Copyable, Movable):
    """The paired-difference statistics for one pair, WITHOUT an interval.

    Private, so it may be shaped for the two callers rather than for the wire. The tournament
    path deliberately does NOT form a per-pair interval: that would be one
    `inference_t_quantile` per pair, a measured 1.1 ms each, and 523776 pairs is ten minutes of
    bisection nobody asked for. The single-pair driver does form one, because there the caller
    asked for exactly one comparison and the interval is the answer.
    """

    var status: Int
    var has_stats: Bool
    var mean_a: Float64
    var mean_b: Float64
    var var_a: Float64
    var var_b: Float64
    var mean_diff: Float64
    var paired_variance: Float64
    var unpaired_variance: Float64
    var std_error: Float64
    var has_t_stat: Bool
    var t_stat: Float64
    var has_p: Bool
    var p_value: Float64
    var deterministic: Bool
    var diffs: List[Float64]

    def __init__(out self, status: Int):
        self.status = status
        self.diffs = List[Float64]()
        self.has_stats = False
        self.mean_a = strat_absent()
        self.mean_b = strat_absent()
        self.var_a = strat_absent()
        self.var_b = strat_absent()
        self.mean_diff = strat_absent()
        self.paired_variance = strat_absent()
        self.unpaired_variance = strat_absent()
        self.std_error = strat_absent()
        self.has_t_stat = False
        self.t_stat = strat_absent()
        self.has_p = False
        self.p_value = strat_absent()
        self.deterministic = False


def _pair_stats(
    row_a: List[Float64], row_b: List[Float64], mean_a: Float64, mean_b: Float64,
    var_a: Float64, var_b: Float64, n_replications: Int, abs_tol: Float64,
) -> _PairStat:
    """The paired statistics for two already-copied rows whose MOMENTS are already known.

    The two rows' means and variances are ARGUMENTS, not recomputed here, and that is a
    measured decision rather than a stylistic one. `Var(a)` does not depend on `b`, so a
    round-robin that recomputed it inside the pair loop would compute each strategy's variance
    `n_strategies - 1` times: at 356 strategies that is 355 redundant passes per strategy, and
    MEASURED on this tree `compute_variance` costs 3.14 ns per element against 1.33 ns for
    `compute_mean`, so the redundancy was 60% of the per-pair cost. The caller computes each
    strategy's moments ONCE — the tournament path takes them from the same
    `replicate_ci_flat` result that produced its interval, so the variance behind a strategy's
    interval and the variance behind its pairing gain are the same number by construction.

    The p-value is the PAIRED t on `n_replications - 1` degrees of freedom, computed from the
    differences and not from the two means: pairing is the whole point, and a two-sample test on
    the same data would throw away the covariance that common random numbers created.

    THE DEGENERATE BRANCH, which is where a NaN would otherwise be born. When every difference
    is identical the sample variance is exactly zero, so `t = mean / 0` is an infinity or a
    `0/0` NaN. Both are refused by the dispatch and neither is the answer, so the branch is
    explicit:

      * variance zero AND the mean difference agrees with zero within the tolerance — the two
        strategies scored IDENTICALLY on every scenario. `p_value = 1.0` and `has_t_stat` is
        False, because no finite t describes it. This is the genuine tie, and it must read as
        `NO_DIFFERENCE` rather than as a failure to decide.
      * variance zero and the mean difference does NOT agree with zero — the difference is the
        SAME nonzero number on every scenario, which is deterministic dominance and not
        sampling noise. `p_value = 0.0`, `has_t_stat` False (the statistic is unbounded, and a
        large finite stand-in would be a fabricated measurement).

    Everything else takes `t = mean_diff / std_error` and
    `inference_t_sf_two_sided(|t|, n - 1)`, and reports `STRAT_ERR_NO_ESTIMATE` with `has_p`
    False if that comes back non-finite or outside `[0, 1]` — never a clamped stand-in, because
    a clamped p-value silently changes a verdict.
    """
    var n = n_replications
    if len(row_a) < n or len(row_b) < n or n < 2:
        return _PairStat(STRAT_ERR_COUNT)
    var diffs = List[Float64](capacity=n)
    for r in range(n):
        diffs.append(row_a[r] - row_b[r])
    if not strat_all_finite(diffs, n):
        # Two finite outcomes can still differ non-finitely at the extremes of the range.
        return _PairStat(STRAT_ERR_NON_FINITE)

    var out = _PairStat(STRAT_OK)
    var mu_d = compute_mean(diffs, n)
    if not strat_finite(mean_a) or not strat_finite(mean_b) or not strat_finite(mu_d):
        return _PairStat(STRAT_ERR_NON_FINITE)
    var v_d = compute_variance(diffs, n, mu_d)
    if not strat_finite(var_a) or not strat_finite(var_b) or not strat_finite(v_d):
        return _PairStat(STRAT_ERR_NON_FINITE)
    if var_a < 0.0 or var_b < 0.0 or v_d < 0.0:
        return _PairStat(STRAT_ERR_NON_FINITE)
    var v_unpaired = var_a + var_b
    if not strat_finite(v_unpaired):
        return _PairStat(STRAT_ERR_NON_FINITE)

    out.has_stats = True
    out.mean_a = mean_a
    out.mean_b = mean_b
    out.var_a = var_a
    out.var_b = var_b
    out.mean_diff = mu_d
    out.paired_variance = v_d
    out.unpaired_variance = v_unpaired
    out.diffs = diffs^

    var se = sqrt(v_d / Float64(n))
    if not strat_finite(se):
        out.status = STRAT_ERR_NO_ESTIMATE
        return out^
    out.std_error = se

    if se == 0.0:
        out.deterministic = True
        out.has_p = True
        if strat_agrees(mu_d, 0.0, abs_tol, n):
            out.p_value = 1.0
        else:
            out.p_value = 0.0
        return out^

    var t = mu_d / se
    if not strat_finite(t):
        out.status = STRAT_ERR_NO_ESTIMATE
        return out^
    out.has_t_stat = True
    out.t_stat = t
    var p = inference_t_sf_two_sided(fabs(t), Float64(n - 1))
    if not strat_finite(p) or p < 0.0 or p > 1.0:
        out.status = STRAT_ERR_NO_ESTIMATE
        return out^
    out.has_p = True
    out.p_value = p
    return out^


def _verdict_from(
    rejected: Bool, has_p: Bool, mean_diff: Float64, higher_is_better: Bool
) -> Int:
    """The three-outcome verdict for one comparison. `UNDECIDED` when the test was not MADE.

    The sign convention lives here so it is written once: `mean_diff` is `mean_a - mean_b`, so a
    positive difference favours A when higher is better and favours B when it is not. A rejected
    test with a mean difference of exactly zero cannot happen (a zero mean difference is either
    the degenerate tie with `p = 1.0` or has a t of zero and `p = 1.0`), and if it somehow does,
    `NO_DIFFERENCE` is the honest reading of "significant, direction unknown" — never a coin
    flip between the two directions.
    """
    if not has_p:
        return STRAT_VERDICT_UNDECIDED
    if not rejected:
        return STRAT_VERDICT_NO_DIFFERENCE
    if mean_diff == 0.0:
        return STRAT_VERDICT_NO_DIFFERENCE
    var a_wins = mean_diff > 0.0
    if not higher_is_better:
        a_wins = not a_wins
    if a_wins:
        return STRAT_VERDICT_A_BETTER
    return STRAT_VERDICT_B_BETTER


@fieldwise_init
struct _Correction(Copyable, Movable):
    """One family-wise correction's outcome, translated into this package's vocabulary.

    Private and deliberately NOT `inference.multiplicity.Correction`: a struct owned by another
    module cannot appear in a public signature here without dropping the function from the
    contract, and its `status` is in 320-339. So the three procedures funnel through one place
    that copies the two lists and translates the code exactly once.
    """

    var status: Int
    var adjusted: List[Float64]
    var rejected: List[Bool]


def _correct(
    p_values: List[Float64], n_pairs: Int, alpha: Float64, method: Int
) -> _Correction:
    """Apply the selected multiplicity procedure to the WHOLE pair family at once.

    All three procedures come from `inference.multiplicity` and none is reimplemented: the
    difference between Bonferroni, Holm and Benjamini-Hochberg is a difference in what a
    family-wise claim MEANS, and this module's job is to pass the caller's choice through, not to
    have an opinion. The family is every pair, never a subset — a correction over the pairs that
    happened to produce a p-value would divide by the wrong family size and report an error rate
    nobody chose.
    """
    if method == TOURNEY_METHOD_BONFERRONI:
        var c = bonferroni_flat(p_values, n_pairs, alpha)
        return _Correction(_inf_to_strat(c.status), c.adjusted.copy(), c.rejected.copy())
    if method == TOURNEY_METHOD_HOLM:
        var c2 = holm_flat(p_values, n_pairs, alpha)
        return _Correction(_inf_to_strat(c2.status), c2.adjusted.copy(), c2.rejected.copy())
    if method == TOURNEY_METHOD_BH:
        var c3 = benjamini_hochberg_flat(p_values, n_pairs, alpha)
        return _Correction(_inf_to_strat(c3.status), c3.adjusted.copy(), c3.rejected.copy())
    return _Correction(STRAT_ERR_UNKNOWN_METHOD, List[Float64](), List[Bool]())


struct PairedDiff(Copyable, Movable):
    """ONE paired comparison: the difference, its interval, its p-value and the pairing gain.

    `multiplicity_corrected` is False and says so IN THE RECORD. This is a single comparison and
    its p-value is uncorrected, which is correct for a family of one and wrong for a family of
    many — a caller that ran this twenty times and read twenty p-values at 0.05 would be running
    at a family-wise error rate near 0.64. `tourney_rank_flat` is the entry point that corrects,
    and its per-pair verdicts carry `multiplicity_corrected = True`.

    Every quantity has a `has_*` flag beside it and every absent slot holds exactly 0.0, never a
    non-finite: the dispatch refuses to serialise a NaN, so one absent number would turn the
    whole response into a typed error and erase every present number beside it.
    """

    var status: Int
    var verdict: Int
    var decided: Bool
    var multiplicity_corrected: Bool
    var index_a: Int
    var index_b: Int
    var n_replications: Int
    var level: Float64
    var alpha: Float64
    var higher_is_better: Bool
    var has_means: Bool
    var mean_a: Float64
    var mean_b: Float64
    var variance_a: Float64
    var variance_b: Float64
    var has_mean_diff: Bool
    var mean_diff: Float64
    var has_paired_variance: Bool
    var paired_variance: Float64
    var unpaired_variance: Float64
    var has_variance_ratio: Bool
    var variance_ratio: Float64
    var paired_variance_lower: Bool
    var has_std_error: Bool
    var std_error: Float64
    var has_t_stat: Bool
    var t_stat: Float64
    var has_p: Bool
    var p_value: Float64
    var deterministic: Bool
    var has_t_critical: Bool
    var t_critical: Float64
    var has_ci: Bool
    var ci_lower: Float64
    var ci_upper: Float64
    var has_half_width: Bool
    var half_width: Float64
    var ci_excludes_zero: Bool
    var work_charge: Int

    def __init__(
        out self, status: Int, index_a: Int, index_b: Int, n_replications: Int,
        level: Float64, alpha: Float64, higher_is_better: Bool,
    ):
        self.status = status
        self.verdict = STRAT_VERDICT_UNDECIDED
        self.decided = False
        self.multiplicity_corrected = False
        self.index_a = index_a
        self.index_b = index_b
        self.n_replications = n_replications
        self.level = level
        self.alpha = alpha
        self.higher_is_better = higher_is_better
        self.has_means = False
        self.mean_a = strat_absent()
        self.mean_b = strat_absent()
        self.variance_a = strat_absent()
        self.variance_b = strat_absent()
        self.has_mean_diff = False
        self.mean_diff = strat_absent()
        self.has_paired_variance = False
        self.paired_variance = strat_absent()
        self.unpaired_variance = strat_absent()
        self.has_variance_ratio = False
        self.variance_ratio = strat_absent()
        self.paired_variance_lower = False
        self.has_std_error = False
        self.std_error = strat_absent()
        self.has_t_stat = False
        self.t_stat = strat_absent()
        self.has_p = False
        self.p_value = strat_absent()
        self.deterministic = False
        self.has_t_critical = False
        self.t_critical = strat_absent()
        self.has_ci = False
        self.ci_lower = strat_absent()
        self.ci_upper = strat_absent()
        self.has_half_width = False
        self.half_width = strat_absent()
        self.ci_excludes_zero = False
        self.work_charge = -1


def _ratio_of(paired: Float64, unpaired: Float64) -> Float64:
    """`unpaired / paired`, or -1.0 when that ratio does not exist.

    A paired variance of exactly zero is not an error — it is the deterministic case, which is
    the STRONGEST possible pairing — but `unpaired / 0` is an infinity, the dispatch refuses a
    non-finite, and one absent ratio would erase the whole response. So the ratio is ABSENT
    there and `paired_variance_lower` carries the finding instead. -1.0 is the "no such number"
    marker and the caller's `has_variance_ratio` flag is the answer.
    """
    if not strat_finite(paired) or not strat_finite(unpaired):
        return -1.0
    if paired <= 0.0:
        return -1.0
    var r = unpaired / paired
    if not strat_finite(r):
        return -1.0
    return r


def tourney_paired_diff_flat(
    outcomes: List[Float64], n_strategies: Int, n_replications: Int,
    index_a: Int, index_b: Int, level: Float64, alpha: Float64,
    higher_is_better: Bool, abs_tol: Float64,
) -> PairedDiff:
    """Compare strategies `index_a` and `index_b` on the SAME scenarios. One comparison, no correction.

    Column `r` of the outcome matrix is one scenario, so `a_r - b_r` is the difference on a
    shared scenario and the test is a paired t on `n_replications - 1` degrees of freedom. The
    interval on the mean difference comes from `discrete_event.replicate.replicate_ci_flat`,
    which is where this tree's Student-t interval already lives; its status codes are translated
    into this package's vocabulary rather than leaked.

    `paired_variance` and `unpaired_variance` are both reported so the pairing gain is a NUMBER a
    caller can check, not a property claimed in a docstring: `Var(a - b)` against
    `Var(a) + Var(b)`, the second being what the same difference would cost on independent
    draws. `variance_ratio` is ABSENT when the paired variance is zero, which is the deterministic
    case and the strongest possible pairing rather than a failure.

    Refusals, all typed, none of which can abort the worker: the `tourney_outcome_status`
    contract (shape by division, non-finite, replication count); `STRAT_ERR_COUNT` for an index
    outside `[0, n_strategies)` — the same defect class as a count past a list end, since both
    name a position the payload does not have; `STRAT_ERR_DEGENERATE` for `index_a == index_b`,
    because a strategy always ties with itself and recording `NO_DIFFERENCE` for it would put a
    meaningless verdict in the register; `STRAT_ERR_LEVEL_RANGE` for `level` or `alpha` outside
    the open interval `(0, 1)`; `STRAT_ERR_TOLERANCE` for a negative or non-finite tolerance;
    `STRAT_ERR_WORK_BUDGET` above `STRAT_MAX_WORK`; `STRAT_ERR_NO_ESTIMATE` when the statistic
    or the p-value does not exist.

    @capability tourney_paired_diff_flat
    complexity: O(n_replications)
    counts:
    - n_strategies * n_replications == len(outcomes) [kernel_validated]
    - dim n_replications [kernel_validated]
    @endcapability
    """
    var shape = tourney_outcome_status(outcomes, n_strategies, n_replications)
    if shape != STRAT_OK:
        return PairedDiff(
            shape, index_a, index_b, n_replications, level, alpha, higher_is_better
        )
    if index_a < 0 or index_b < 0 or index_a >= n_strategies or index_b >= n_strategies:
        return PairedDiff(
            STRAT_ERR_COUNT, index_a, index_b, n_replications, level, alpha, higher_is_better
        )
    if index_a == index_b:
        return PairedDiff(
            STRAT_ERR_DEGENERATE, index_a, index_b, n_replications, level, alpha,
            higher_is_better,
        )
    var lvl = strat_level_status(level)
    if lvl != STRAT_OK:
        return PairedDiff(
            lvl, index_a, index_b, n_replications, level, alpha, higher_is_better
        )
    var alp = strat_level_status(alpha)
    if alp != STRAT_OK:
        return PairedDiff(
            alp, index_a, index_b, n_replications, level, alpha, higher_is_better
        )
    var tol = strat_tolerance_status(abs_tol)
    if tol != STRAT_OK:
        return PairedDiff(
            tol, index_a, index_b, n_replications, level, alpha, higher_is_better
        )
    # Charged as the two-strategy, one-pair tournament this is, so a single comparison and a
    # tournament containing it cannot disagree about what it costs.
    var charge = tourney_work_charge(TOURNEY_MIN_STRATEGIES, n_replications)
    if charge < 0:
        return PairedDiff(
            STRAT_ERR_WORK_BUDGET, index_a, index_b, n_replications, level, alpha,
            higher_is_better,
        )

    var start_a = tourney_outcome_cell(index_a, 0, n_replications)
    var start_b = tourney_outcome_cell(index_b, 0, n_replications)
    if start_a < 0 or start_b < 0:
        return PairedDiff(
            STRAT_ERR_SHAPE, index_a, index_b, n_replications, level, alpha, higher_is_better
        )
    var row_a = _row_copy(outcomes, start_a, n_replications)
    var row_b = _row_copy(outcomes, start_b, n_replications)
    if len(row_a) != n_replications or len(row_b) != n_replications:
        return PairedDiff(
            STRAT_ERR_SHAPE, index_a, index_b, n_replications, level, alpha, higher_is_better
        )
    # The two rows' moments, computed here ONCE and handed to the shared core. Four frozen
    # `stats` calls rather than a second spelling of "mean" and "variance" — and the same two
    # numbers the tournament path takes from `replicate_ci_flat`, so a single comparison and a
    # tournament containing it report the same variance for the same strategy.
    var mu_a = compute_mean(row_a, n_replications)
    var mu_b = compute_mean(row_b, n_replications)
    var v_a = compute_variance(row_a, n_replications, mu_a)
    var v_b = compute_variance(row_b, n_replications, mu_b)
    var stat = _pair_stats(
        row_a, row_b, mu_a, mu_b, v_a, v_b, n_replications, abs_tol
    )

    var out = PairedDiff(
        stat.status, index_a, index_b, n_replications, level, alpha, higher_is_better
    )
    out.work_charge = charge
    if not stat.has_stats:
        return out^
    out.has_means = True
    out.mean_a = stat.mean_a
    out.mean_b = stat.mean_b
    out.variance_a = stat.var_a
    out.variance_b = stat.var_b
    out.has_mean_diff = True
    out.mean_diff = stat.mean_diff
    out.has_paired_variance = True
    out.paired_variance = stat.paired_variance
    out.unpaired_variance = stat.unpaired_variance
    var ratio = _ratio_of(stat.paired_variance, stat.unpaired_variance)
    if ratio > 0.0:
        out.has_variance_ratio = True
        out.variance_ratio = ratio
    out.paired_variance_lower = stat.paired_variance < stat.unpaired_variance
    out.has_std_error = True
    out.std_error = stat.std_error
    out.has_t_stat = stat.has_t_stat
    out.t_stat = stat.t_stat
    out.has_p = stat.has_p
    out.p_value = stat.p_value
    out.deterministic = stat.deterministic

    # The interval on the mean difference, from the frozen replication-interval builder, over
    # the difference list the statistics were already computed from — not a second one built the
    # same way, which is how two numbers in one response end up describing different data.
    var ci = replicate_ci_flat(stat.diffs, n_replications, level)
    var ci_status = _de_to_strat(ci.status)
    if ci_status != STRAT_OK and stat.status == STRAT_OK:
        out.status = ci_status
    if ci.has_t_critical:
        out.has_t_critical = True
        out.t_critical = ci.t_critical
    if ci.has_ci:
        out.has_ci = True
        out.ci_lower = ci.ci_lower
        out.ci_upper = ci.ci_upper
        out.ci_excludes_zero = ci.ci_lower > 0.0 or ci.ci_upper < 0.0
    if ci.has_half_width:
        out.has_half_width = True
        out.half_width = ci.half_width

    out.verdict = _verdict_from(
        stat.has_p and stat.p_value <= alpha, stat.has_p, stat.mean_diff, higher_is_better
    )
    out.decided = out.verdict != STRAT_VERDICT_UNDECIDED
    return out^


struct PairedBootstrap(Copyable, Movable):
    """A percentile bootstrap interval on ONE pair's mean difference, resampled PAIRED.

    The resample draws a REPLICATION INDEX and takes both strategies' outcomes at that index, so
    the pairing survives the resample. Resampling the two strategies independently would destroy
    the covariance common random numbers created — the same defect
    `evaluation.resample.bootstrap_metric_ci_flat` avoids by resampling `(prob, label)`
    TOGETHER, and this is that discipline applied to a paired comparison.

    `seed` and `n_boot` are returned so the interval is reproducible from the record alone, and
    `rng_version` names the generator that produced it. A result that cannot be reproduced is
    not a result.
    """

    var status: Int
    var present: Bool
    var index_a: Int
    var index_b: Int
    var n_replications: Int
    var n_boot: Int
    var seed: Int
    var alpha: Float64
    var point: Float64
    var lo: Float64
    var hi: Float64
    var excludes_zero: Bool
    var point_inside: Bool
    var n_draws: Int
    var rng_version: String

    def __init__(
        out self, status: Int, index_a: Int, index_b: Int, n_replications: Int,
        n_boot: Int, seed: Int, alpha: Float64,
    ):
        self.status = status
        self.present = False
        self.index_a = index_a
        self.index_b = index_b
        self.n_replications = n_replications
        self.n_boot = n_boot
        self.seed = seed
        self.alpha = alpha
        self.point = strat_absent()
        self.lo = strat_absent()
        self.hi = strat_absent()
        self.excludes_zero = False
        self.point_inside = False
        self.n_draws = 0
        self.rng_version = rng_version()


def tourney_paired_bootstrap_flat(
    outcomes: List[Float64], n_strategies: Int, n_replications: Int,
    index_a: Int, index_b: Int, alpha: Float64, n_boot: Int, seed: Int,
) -> PairedBootstrap:
    """A percentile bootstrap interval on the paired mean difference. Reproducible from `seed`.

    The second, distribution-free route to the same question the paired t answers: the t
    interval assumes the differences are approximately normal, and this one does not. Both are
    reported by the two entry points here so a caller can see them agree — or not, which is
    itself the finding.

    Composes rather than re-derives: `evaluation.resample.bootstrap_draw_index` is the
    coordinate map, `EVAL_BOOTSTRAP_STREAM_NAME` is the stream (the `evaluation` package owns
    bootstrap resampling and a fourth `strategy` stream for the same process would be a second
    place for one decision to live), `determinism.sampling_keyed.uniform_int_keyed` is the draw,
    and `stats.quantile` is the percentile.

    Refusals: the `tourney_outcome_status` contract; `STRAT_ERR_COUNT` for an index outside
    `[0, n_strategies)`; `STRAT_ERR_DEGENERATE` for `index_a == index_b`;
    `STRAT_ERR_LEVEL_RANGE` for `alpha` outside `(0, 1)`; `STRAT_ERR_EMPTY` for `n_boot < 1`;
    `STRAT_ERR_DIMENSION_TOO_LARGE` above `EVAL_MAX_RESAMPLES`; `STRAT_ERR_SEED_RANGE` for a
    negative seed, refused rather than reinterpreted as an enormous unsigned coordinate, so a
    recorded seed always reproduces the run; `STRAT_ERR_WORK_BUDGET` when
    `STRAT_DRAW_WEIGHT * n_boot * n_replications` exceeds `STRAT_MAX_WORK`, since a keyed draw
    is 64 work units and the resample makes one per replication per bootstrap sample.

    @capability tourney_paired_bootstrap_flat
    complexity: O(n_boot * n_replications log n_boot)
    counts:
    - n_strategies * n_replications == len(outcomes) [kernel_validated]
    - dim n_boot [kernel_validated]
    @endcapability
    """
    var shape = tourney_outcome_status(outcomes, n_strategies, n_replications)
    if shape != STRAT_OK:
        return PairedBootstrap(
            shape, index_a, index_b, n_replications, n_boot, seed, alpha
        )
    if index_a < 0 or index_b < 0 or index_a >= n_strategies or index_b >= n_strategies:
        return PairedBootstrap(
            STRAT_ERR_COUNT, index_a, index_b, n_replications, n_boot, seed, alpha
        )
    if index_a == index_b:
        return PairedBootstrap(
            STRAT_ERR_DEGENERATE, index_a, index_b, n_replications, n_boot, seed, alpha
        )
    var alp = strat_level_status(alpha)
    if alp != STRAT_OK:
        return PairedBootstrap(alp, index_a, index_b, n_replications, n_boot, seed, alpha)
    if n_boot < 1:
        return PairedBootstrap(
            STRAT_ERR_EMPTY, index_a, index_b, n_replications, n_boot, seed, alpha
        )
    if n_boot > EVAL_MAX_RESAMPLES:
        return PairedBootstrap(
            STRAT_ERR_DIMENSION_TOO_LARGE, index_a, index_b, n_replications, n_boot, seed, alpha
        )
    if seed < 0:
        return PairedBootstrap(
            STRAT_ERR_SEED_RANGE, index_a, index_b, n_replications, n_boot, seed, alpha
        )
    if not strat_product_fits(n_boot, n_replications, STRAT_MAX_WORK):
        return PairedBootstrap(
            STRAT_ERR_WORK_BUDGET, index_a, index_b, n_replications, n_boot, seed, alpha
        )
    if not strat_product_fits(STRAT_DRAW_WEIGHT, n_boot * n_replications, STRAT_MAX_WORK):
        return PairedBootstrap(
            STRAT_ERR_WORK_BUDGET, index_a, index_b, n_replications, n_boot, seed, alpha
        )

    var start_a = tourney_outcome_cell(index_a, 0, n_replications)
    var start_b = tourney_outcome_cell(index_b, 0, n_replications)
    if start_a < 0 or start_b < 0:
        return PairedBootstrap(
            STRAT_ERR_SHAPE, index_a, index_b, n_replications, n_boot, seed, alpha
        )
    var diffs = List[Float64](capacity=n_replications)
    for r in range(n_replications):
        diffs.append(outcomes[start_a + r] - outcomes[start_b + r])
    if not strat_all_finite(diffs, n_replications):
        return PairedBootstrap(
            STRAT_ERR_NON_FINITE, index_a, index_b, n_replications, n_boot, seed, alpha
        )
    var point = compute_mean(diffs, n_replications)
    if not strat_finite(point):
        return PairedBootstrap(
            STRAT_ERR_NON_FINITE, index_a, index_b, n_replications, n_boot, seed, alpha
        )

    var stream = stream_id(EVAL_BOOTSTRAP_STREAM_NAME)
    var master = UInt64(seed)
    var replicates = List[Float64](capacity=n_boot)
    for b in range(n_boot):
        var total: Float64 = 0.0
        for i in range(n_replications):
            var coord = bootstrap_draw_index(b, i, n_replications)
            if coord < 0:
                return PairedBootstrap(
                    STRAT_ERR_NO_ESTIMATE, index_a, index_b, n_replications, n_boot, seed, alpha
                )
            var k = uniform_int_keyed(0, n_replications - 1, master, stream, UInt64(coord))
            # `uniform_int_keyed` documents a result inside `[low, high]`; the clamp stays
            # because `diffs[k]` is a subscript and a subscript out of range is an uncatchable
            # process abort, not an exception. A guard on a subscript is never redundant.
            if k < 0:
                k = 0
            if k >= n_replications:
                k = n_replications - 1
            total += diffs[k]
        replicates.append(total / Float64(n_replications))

    var half = alpha / 2.0
    var lo = quantile(replicates, n_boot, half)
    var hi = quantile(replicates, n_boot, 1.0 - half)
    if not strat_finite(lo) or not strat_finite(hi):
        return PairedBootstrap(
            STRAT_ERR_NO_ESTIMATE, index_a, index_b, n_replications, n_boot, seed, alpha
        )
    var out = PairedBootstrap(
        STRAT_OK, index_a, index_b, n_replications, n_boot, seed, alpha
    )
    out.present = True
    out.point = point
    out.lo = lo
    out.hi = hi
    out.excludes_zero = lo > 0.0 or hi < 0.0
    out.point_inside = point >= lo and point <= hi
    out.n_draws = n_boot * n_replications
    return out^


struct Tournament(Copyable, Movable):
    """A full round-robin ranking: per-strategy means and intervals, ranks with TIES AS TIES.

    `ranked` is separate from `status` for the same reason `evaluation.gates.GateResult` keeps
    `decided` apart from `passed`: a refused request produced no ranking at all, while a ranking
    that found nothing distinguishable produced a real result whose content is
    `NO_DIFFERENCE`. Collapsing the two would report "we could not tell" and "they are the same"
    as the same finding.

    `rank[s]` is `1 + (how many strategies are SIGNIFICANTLY better than s after correction)`.
    Two strategies nobody beats therefore share rank 1, which is how a tie is expressed: as one
    number appearing twice, not as an arbitrary order between them. `n_undecided_pairs` is
    reported next to it because the ranking is built from the DECIDED relation, and a reader
    needs to know how much of that relation is unknown.

    `n_significant` and `n_significant_uncorrected` sit side by side so the correction is
    visible in the answer rather than asserted in a docstring; `method_name` names the procedure
    with `inference.multiplicity`'s own string.

    On refusal every list is EMPTY, not zero-filled: a zero-filled mean is a measurement and an
    empty list is the absence of one.
    """

    var status: Int
    var ranked: Bool
    var verdict: Int
    var decided: Bool
    var has_winner: Bool
    var winner: Int
    var n_strategies: Int
    var n_replications: Int
    var level: Float64
    var alpha: Float64
    var abs_tolerance: Float64
    var higher_is_better: Bool
    var method: Int
    var method_name: String
    var n_comparisons: Int
    var n_significant: Int
    var n_significant_uncorrected: Int
    var n_undecided_pairs: Int
    var n_deterministic_pairs: Int
    var n_at_rank_1: Int
    var n_distinct_ranks: Int
    var mean: List[Float64]
    var variance: List[Float64]
    var has_ci: List[Bool]
    var ci_lower: List[Float64]
    var ci_upper: List[Float64]
    var rank: List[Int]
    var n_better: List[Int]
    var n_worse: List[Int]
    var pair_a: List[Int]
    var pair_b: List[Int]
    var pair_mean_diff: List[Float64]
    var pair_p: List[Float64]
    var pair_adjusted: List[Float64]
    var pair_rejected: List[Bool]
    var pair_verdict: List[Int]
    var pair_paired_variance: List[Float64]
    var pair_unpaired_variance: List[Float64]
    var has_min_variance_ratio: Bool
    var min_variance_ratio: Float64
    var all_pairs_paired_lower: Bool
    var multiplicity_corrected: Bool
    var work_charge: Int

    def __init__(
        out self, status: Int, n_strategies: Int, n_replications: Int, level: Float64,
        alpha: Float64, abs_tolerance: Float64, higher_is_better: Bool, method: Int,
    ):
        self.status = status
        self.ranked = False
        self.verdict = STRAT_VERDICT_UNDECIDED
        self.decided = False
        self.has_winner = False
        self.winner = -1
        self.n_strategies = n_strategies
        self.n_replications = n_replications
        self.level = level
        self.alpha = alpha
        self.abs_tolerance = abs_tolerance
        self.higher_is_better = higher_is_better
        self.method = method
        self.method_name = tourney_method_name(method)
        self.n_comparisons = 0
        self.n_significant = 0
        self.n_significant_uncorrected = 0
        self.n_undecided_pairs = 0
        self.n_deterministic_pairs = 0
        self.n_at_rank_1 = 0
        self.n_distinct_ranks = 0
        self.mean = List[Float64]()
        self.variance = List[Float64]()
        self.has_ci = List[Bool]()
        self.ci_lower = List[Float64]()
        self.ci_upper = List[Float64]()
        self.rank = List[Int]()
        self.n_better = List[Int]()
        self.n_worse = List[Int]()
        self.pair_a = List[Int]()
        self.pair_b = List[Int]()
        self.pair_mean_diff = List[Float64]()
        self.pair_p = List[Float64]()
        self.pair_adjusted = List[Float64]()
        self.pair_rejected = List[Bool]()
        self.pair_verdict = List[Int]()
        self.pair_paired_variance = List[Float64]()
        self.pair_unpaired_variance = List[Float64]()
        self.has_min_variance_ratio = False
        self.min_variance_ratio = strat_absent()
        self.all_pairs_paired_lower = False
        self.multiplicity_corrected = True
        self.work_charge = -1


def tourney_rank_flat(
    outcomes: List[Float64], n_strategies: Int, n_replications: Int,
    level: Float64, alpha: Float64, method: Int, higher_is_better: Bool, abs_tol: Float64,
) -> Tournament:
    """Rank every strategy against every other on shared scenarios, with the multiplicity corrected.

    The whole procedure, in the order it runs:

      1. The shape guard, the level, the alpha, the tolerance, the method tag, and the WORK
         CHARGE — all before anything is computed, because a request accepted and then abandoned
         has already spent the time.
      2. One Student-t interval per strategy, from `replicate_ci_flat`. If ANY strategy's
         interval cannot be formed the whole tournament is refused: a ranking over the
         strategies that happened to succeed names the winner of a competition the others were
         removed from.
      3. One paired-t p-value per unordered pair, from the differences on shared scenarios. If
         ANY pair's p-value cannot be computed the whole tournament is refused, because a
         correction applied to a shrunken family understates the family size.
      4. `inference.multiplicity` over ALL `n(n-1)/2` p-values at once — Bonferroni, Holm or
         Benjamini-Hochberg — and the per-pair verdicts are read from the CORRECTED rejections,
         never from the raw p-values.
      5. Ranks from the corrected relation: `rank[s] = 1 + |{j : j significantly better}|`, so
         strategies nobody beats share rank 1 and a tie is one number appearing twice.

    The tournament verdict, which is the answer to "who won":

      * `NO_DIFFERENCE` — every comparison was made and NONE was significant. The strategies
        are indistinguishable at this alpha, which is a finding and not a failure.
      * `A_BETTER` — exactly one strategy is at rank 1 AND it significantly beats every other
        one. `winner` is its index. `B_BETTER` never appears at tournament level: "which one"
        is the `winner` field, and a tag cannot name one of 1024 strategies.
      * `UNDECIDED` — some comparisons were significant but no strategy beats all the others
        (an intransitive or partial order), or at least one pair could not be decided. Reported
        as undecided rather than resolved in favour of the rank-1 strategy, because a partial
        order genuinely does not have a winner.

    @capability tourney_rank_flat
    complexity: O(n_strategies^2 * n_replications)
    counts:
    - n_strategies * n_replications == len(outcomes) [kernel_validated]
    - dim n_strategies [kernel_validated]
    - dim n_replications [kernel_validated]
    @endcapability
    """
    if method < 0 or method >= TOURNEY_METHOD_COUNT:
        return Tournament(
            STRAT_ERR_UNKNOWN_METHOD, n_strategies, n_replications, level, alpha, abs_tol,
            higher_is_better, method,
        )
    var shape = tourney_outcome_status(outcomes, n_strategies, n_replications)
    if shape != STRAT_OK:
        return Tournament(
            shape, n_strategies, n_replications, level, alpha, abs_tol, higher_is_better, method
        )
    if n_strategies < TOURNEY_MIN_STRATEGIES:
        return Tournament(
            STRAT_ERR_TOO_FEW_STRATEGIES, n_strategies, n_replications, level, alpha, abs_tol,
            higher_is_better, method,
        )
    var lvl = strat_level_status(level)
    if lvl != STRAT_OK:
        return Tournament(
            lvl, n_strategies, n_replications, level, alpha, abs_tol, higher_is_better, method
        )
    var alp = strat_level_status(alpha)
    if alp != STRAT_OK:
        return Tournament(
            alp, n_strategies, n_replications, level, alpha, abs_tol, higher_is_better, method
        )
    var tol = strat_tolerance_status(abs_tol)
    if tol != STRAT_OK:
        return Tournament(
            tol, n_strategies, n_replications, level, alpha, abs_tol, higher_is_better, method
        )
    var n_pairs = tourney_pair_count(n_strategies)
    if n_pairs < 1:
        return Tournament(
            STRAT_ERR_DIMENSION_TOO_LARGE, n_strategies, n_replications, level, alpha, abs_tol,
            higher_is_better, method,
        )
    var charge = tourney_work_charge(n_strategies, n_replications)
    if charge < 0:
        return Tournament(
            STRAT_ERR_WORK_BUDGET, n_strategies, n_replications, level, alpha, abs_tol,
            higher_is_better, method,
        )

    var out = Tournament(
        STRAT_OK, n_strategies, n_replications, level, alpha, abs_tol, higher_is_better, method
    )
    out.work_charge = charge
    out.n_comparisons = n_pairs

    # ── step 2: one interval per strategy, or refuse the tournament ───────────
    var rows = List[List[Float64]](capacity=n_strategies)
    for s in range(n_strategies):
        var start = tourney_outcome_cell(s, 0, n_replications)
        if start < 0:
            return Tournament(
                STRAT_ERR_SHAPE, n_strategies, n_replications, level, alpha, abs_tol,
                higher_is_better, method,
            )
        var row = _row_copy(outcomes, start, n_replications)
        if len(row) != n_replications:
            return Tournament(
                STRAT_ERR_SHAPE, n_strategies, n_replications, level, alpha, abs_tol,
                higher_is_better, method,
            )
        var ci = replicate_ci_flat(row, n_replications, level)
        var ci_status = _de_to_strat(ci.status)
        if ci_status != STRAT_OK or not ci.has_mean or not ci.has_variance or not ci.has_ci:
            return Tournament(
                ci_status if ci_status != STRAT_OK else STRAT_ERR_NO_ESTIMATE,
                n_strategies, n_replications, level, alpha, abs_tol, higher_is_better, method,
            )
        out.mean.append(ci.mean)
        out.variance.append(ci.variance)
        out.has_ci.append(True)
        out.ci_lower.append(ci.ci_lower)
        out.ci_upper.append(ci.ci_upper)
        rows.append(row^)

    # ── step 3: one paired p-value per pair, or refuse the tournament ─────────
    var p_values = List[Float64](capacity=n_pairs)
    var min_ratio: Float64 = -1.0
    var all_lower = True
    for a in range(n_strategies):
        for b in range(a + 1, n_strategies):
            var stat = _pair_stats(
                rows[a], rows[b], out.mean[a], out.mean[b], out.variance[a], out.variance[b],
                n_replications, abs_tol,
            )
            if stat.status != STRAT_OK or not stat.has_p or not stat.has_stats:
                return Tournament(
                    stat.status if stat.status != STRAT_OK else STRAT_ERR_NO_ESTIMATE,
                    n_strategies, n_replications, level, alpha, abs_tol, higher_is_better,
                    method,
                )
            out.pair_a.append(a)
            out.pair_b.append(b)
            out.pair_mean_diff.append(stat.mean_diff)
            out.pair_paired_variance.append(stat.paired_variance)
            out.pair_unpaired_variance.append(stat.unpaired_variance)
            p_values.append(stat.p_value)
            if stat.p_value <= alpha:
                out.n_significant_uncorrected += 1
            if stat.deterministic:
                out.n_deterministic_pairs += 1
            if not (stat.paired_variance < stat.unpaired_variance):
                all_lower = False
            var ratio = _ratio_of(stat.paired_variance, stat.unpaired_variance)
            if ratio > 0.0:
                if min_ratio < 0.0 or ratio < min_ratio:
                    min_ratio = ratio
    out.all_pairs_paired_lower = all_lower
    if min_ratio > 0.0:
        out.has_min_variance_ratio = True
        out.min_variance_ratio = min_ratio

    # ── step 4: the family-wise correction over EVERY pair at once ────────────
    var corrected = _correct(p_values, n_pairs, alpha, method)
    if corrected.status != STRAT_OK:
        return Tournament(
            corrected.status, n_strategies, n_replications, level, alpha, abs_tol,
            higher_is_better, method,
        )
    var adjusted = corrected.adjusted.copy()
    var rejected = corrected.rejected.copy()
    if len(adjusted) != n_pairs or len(rejected) != n_pairs:
        # The correction returned a family of a different size than it was given. Refused
        # rather than indexed into: the lists are read below and a short list is an abort.
        return Tournament(
            STRAT_ERR_NO_ESTIMATE, n_strategies, n_replications, level, alpha, abs_tol,
            higher_is_better, method,
        )

    # ── step 5: verdicts from the CORRECTED rejections, then ranks ────────────
    var n_better = List[Int](capacity=n_strategies)
    var n_worse = List[Int](capacity=n_strategies)
    for _ in range(n_strategies):
        n_better.append(0)
        n_worse.append(0)
    for k in range(n_pairs):
        out.pair_p.append(p_values[k])
        out.pair_adjusted.append(adjusted[k])
        out.pair_rejected.append(rejected[k])
        var verdict = _verdict_from(
            rejected[k], True, out.pair_mean_diff[k], higher_is_better
        )
        out.pair_verdict.append(verdict)
        if verdict == STRAT_VERDICT_UNDECIDED:
            out.n_undecided_pairs += 1
        if rejected[k]:
            out.n_significant += 1
        var ia = out.pair_a[k]
        var ib = out.pair_b[k]
        if verdict == STRAT_VERDICT_A_BETTER:
            n_better[ib] += 1
            n_worse[ia] += 1
        elif verdict == STRAT_VERDICT_B_BETTER:
            n_better[ia] += 1
            n_worse[ib] += 1
    for s in range(n_strategies):
        out.n_better.append(n_better[s])
        out.n_worse.append(n_worse[s])
        out.rank.append(1 + n_better[s])
        if n_better[s] == 0:
            out.n_at_rank_1 += 1

    var distinct = 0
    for candidate in range(1, n_strategies + 1):
        var seen = False
        for s in range(n_strategies):
            if out.rank[s] == candidate:
                seen = True
        if seen:
            distinct += 1
    out.n_distinct_ranks = distinct

    out.ranked = True
    if out.n_undecided_pairs > 0:
        # At least one comparison could not be made, so neither "they are the same" nor "this
        # one beats everyone" is supportable. This is unreachable while step 3 refuses a pair
        # without a p-value, and it stays because the two rules must not be able to drift apart.
        out.verdict = STRAT_VERDICT_UNDECIDED
    elif out.n_significant == 0:
        out.verdict = STRAT_VERDICT_NO_DIFFERENCE
    else:
        var champion = -1
        for s in range(n_strategies):
            if n_better[s] == 0 and n_worse[s] == n_strategies - 1:
                champion = s
        if champion >= 0 and out.n_at_rank_1 == 1:
            out.verdict = STRAT_VERDICT_A_BETTER
            out.has_winner = True
            out.winner = champion
        else:
            out.verdict = STRAT_VERDICT_UNDECIDED
    out.decided = out.verdict != STRAT_VERDICT_UNDECIDED
    return out^
