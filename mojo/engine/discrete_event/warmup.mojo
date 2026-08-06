"""
discrete_event.warmup — transient (warm-up) detection by MSER. Zero Python imports.

The bias this removes
---------------------
A simulation starts empty and idle. The first customers of an M/M/1 queue wait far less than
steady-state customers do, because there is nobody ahead of them, so a mean over the whole run
is biased LOW and the bias shrinks only as `1/n`. Nothing in this tree detected that: neither
`simulation.mm1_simulate` nor any frozen statistic distinguishes an initialisation transient
from the steady state it is trying to measure, and no status anywhere said the estimate was
biased.

MSER, and what it actually minimises
------------------------------------
Batch the observations into non-overlapping batches of `batch_size` (5 is the classical MSER-5)
and let `b_0 .. b_{m-1}` be the batch means. For each candidate truncation `d` the rule scores

    MSER(d) = (1 / (m - d)^2) * sum_{i>=d} (b_i - mean_{i>=d})^2

and picks the `d` that minimises it. The score is the estimated standard error of the retained
mean, so the rule trades bias against variance directly: discarding more removes transient bias
but leaves fewer observations, and the minimum is where the two balance.

TIES GO TO THE SMALLEST `d`. Discarding as little as possible is the conservative direction: an
extra retained batch adds at most a little bias, while an extra discarded batch throws away data
that cannot be recovered.

The search boundary is a REFUSAL, not a truncation
--------------------------------------------------
The candidate set is `d` in `[0, m/2]`. If the minimum lands ON that boundary the rule is saying
"discard everything you are allowed to and it still gets better" — the series has not settled
inside this run, and the mean of the last half is not a steady-state estimate, it is the mean of
whatever the transient had reached by then. So `at_search_boundary` is True, the status is
`DE_ERR_NO_STEADY_STATE`, and `has_estimate` is False. The alternative — returning the tail mean
anyway — is the silent-wrong-answer this package exists to avoid: it is a number where none
exists, and a caller cannot tell it apart from a converged one.

Every discard is COUNTED
------------------------
`n_discarded_obs` is the transient MSER removed. `n_tail_dropped` is the ragged remainder that
does not fill a whole batch and is therefore not part of any batch mean. Both are reported,
because an estimator that silently trimmed its own input cannot be reproduced from its inputs,
and the second one surprises people: `warmup_mser_flat(obs, 103, 5)` uses 100 observations and
says so.

Why `batch_mean_variance` is a diagnostic and not a CI
-----------------------------------------------------
Successive observations from one simulation run are autocorrelated, and batches of 5 are far too
short to break that. So the variance of the batch means UNDERSTATES the variance of the mean, and
using it for an interval would produce a confidence interval that is too narrow — the classic way
a simulation study reports false precision. It is reported as a diagnostic only. Intervals in
this package come from INDEPENDENT REPLICATIONS in `discrete_event.replicate`, where the
independence is a property of the generator's coordinates rather than an assumption about
autocorrelation.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_discrete_event_warmup.mojo
benchmark: benchmarks/mojo_benchmarks/bench_discrete_event.mojo
docs: gitbook/engine/discrete-event-simulation.md
version_introduced: 2026.07.31
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from stats import compute_mean, compute_variance

from discrete_event.contract import (
    DE_ERR_BATCH_RANGE,
    DE_ERR_COUNT,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_NO_STEADY_STATE,
    DE_ERR_NON_FINITE,
    DE_ERR_TOO_FEW,
    DE_ERR_WARMUP_RANGE,
    DE_ERR_WORK_BUDGET,
    DE_MAX_BATCH,
    DE_MAX_OBS,
    DE_MAX_WORK,
    DE_OK,
    de_all_finite,
    de_finite,
)

# MSER needs at least four batches: the candidate set is `[0, m/2]`, and with fewer than four
# batches the boundary candidate retains one batch, whose sum of squared deviations is
# identically zero — a degenerate minimum that would always win and always be reported as the
# answer. Four is the smallest `m` for which every candidate retains at least two batches.
comptime WARMUP_MIN_BATCHES: Int = 4


@fieldwise_init
struct WarmupReport(Copyable, Movable):
    """Where the transient ended, how much was discarded, and whether an estimate exists.

    `batch_means` is returned in full so a caller can plot the series and see the transient
    rather than take this module's word for where it stopped.

    Field pairs are `has_*` plus value throughout, and an absent value slot is exactly `0.0`.
    A steady-state mean of zero is a legitimate answer (a queue nobody waited in), so the flag
    and not the value is what says whether the number exists.
    """

    var status: Int
    var n_obs: Int
    var batch_size: Int
    var n_batches: Int
    var n_discarded_batches: Int
    var n_discarded_obs: Int
    var n_retained_batches: Int
    var n_retained_obs: Int
    var n_tail_dropped: Int
    var search_boundary: Int
    var at_search_boundary: Bool
    var has_mser: Bool
    var mser_value: Float64
    var has_estimate: Bool
    var steady_mean: Float64
    var has_batch_variance: Bool
    var batch_mean_variance: Float64
    var work_charged: Int
    var batch_means: List[Float64]


def _warmup_refusal(code: Int) -> WarmupReport:
    return WarmupReport(
        code, 0, 0, 0, 0, 0, 0, 0, 0, 0, False, False, 0.0, False, 0.0, False, 0.0, 0,
        List[Float64](),
    )


@fieldwise_init
struct BiasAudit(Copyable, Movable):
    """How much the transient was moving the full-sample mean.

    Exported so that discarding observations is a decision with a measured consequence rather
    than a step the caller has to trust. `bias_removed` is `full_mean - truncated_mean`, signed:
    for a queue starting empty it is negative, because the transient pulls the mean DOWN, and
    the sign is the diagnosis.

    `relative_bias` is absent — not zero, not large — when the truncated mean is exactly zero. A
    ratio to zero has no value, and returning one would be a number where none exists.
    """

    var status: Int
    var n_obs: Int
    var n_discarded: Int
    var n_retained: Int
    var has_full_mean: Bool
    var full_mean: Float64
    var has_truncated_mean: Bool
    var truncated_mean: Float64
    var has_bias: Bool
    var bias_removed: Float64
    var has_relative_bias: Bool
    var relative_bias: Float64


def _bias_refusal(code: Int) -> BiasAudit:
    return BiasAudit(code, 0, 0, 0, False, 0.0, False, 0.0, False, 0.0, False, 0.0)


def warmup_mser_flat(obs: List[Float64], n_obs: Int, batch_size: Int) -> WarmupReport:
    """Find the MSER truncation point over the first `n_obs` observations.

    `batch_size = 5` is MSER-5, the classical setting. Larger batches smooth harder and reduce
    the candidate resolution; `batch_size = 1` is legal and is plain MSER over raw observations.

    Refusals:
      * `n_obs` above `len(obs)` -> `DE_ERR_COUNT`, checked before the first subscript. A read
        past a `List` end is an uncatchable abort that ends the worker process, and the
        generated A-Z suite calls every contract function with a five-element list and `5` for
        every `Int`.
      * `n_obs <= 0` -> `DE_ERR_EMPTY`; above `DE_MAX_OBS` -> `DE_ERR_DIMENSION_TOO_LARGE`.
      * `batch_size` outside `[1, DE_MAX_BATCH]` -> `DE_ERR_BATCH_RANGE`. It is a DIVISOR, so
        zero is refused rather than divided by.
      * fewer than `WARMUP_MIN_BATCHES` whole batches -> `DE_ERR_TOO_FEW`. With three or fewer,
        the boundary candidate retains a single batch whose deviation sum is identically zero and
        would always win.
      * a non-finite observation -> `DE_ERR_NON_FINITE`. One NaN makes every comparison in the
        minimisation False, so the search would silently return the first candidate.
      * `4 * m` above `DE_MAX_WORK` -> `DE_ERR_WORK_BUDGET`.

    The minimisation is O(m), not O(m^2): the retained sum and sum of squares are suffix
    accumulations, so `sum (b_i - mean)^2 = Q_d - S_d^2 / k` is one subtraction per candidate.
    That form is cancellation-prone when the batch means are large relative to their spread, so
    it is used ONLY to RANK candidates — a relative comparison — and the reported `steady_mean`
    and `batch_mean_variance` are recomputed exactly at the chosen `d` through the frozen
    `stats.compute_mean` and `stats.compute_variance`.

    ZERO-TRUNCATION DEFECT, FIXED: every batch mean is accumulated relative to `means[0]` before
    `Q_d` and `S_d` are formed, not in its raw magnitude. Sum-of-squared-deviations is translation
    invariant, so this changes no ranking that was ever computed correctly — it only removes an
    additive constant before the cancellation-prone step. Without it, a series whose batch means
    carry a large common offset (a clock that has been running a long time, a counter, a price
    level) drives `Q_d` and `S_d^2/k` to nearly equal huge numbers at every candidate; their
    difference is then dominated by float64 rounding rather than by the real deviations, every
    candidate's raw score can round negative and get clamped to the SAME 0.0, and the tie rule
    ("ties go to the smallest d") then picks `d = 0` — discarding NOTHING — even when the first
    batches carry an obvious, large, decaying transient a human would truncate on sight. That is
    "MSER-5 selects a zero truncation" as an outright numerical bug, distinct from and in addition
    to MSER's separate, genuine statistical limitation (see `bench_queueing_validation.mojo`
    section 7): on a long run where the transient's real contribution to the batch-mean spread is
    a small fraction of steady-state noise, an EXACTLY computed score can still legitimately
    minimise at `d = 0`. Recentering cannot fix that second case and does not try to — it fixes
    only the case where the wrong `d` was picked because the arithmetic, not the statistic, was
    wrong. `mojo/tests/libs/test_discrete_event_warmup.mojo` constructs the first case by hand and
    proves it by mutation: reverting this recentering on that exact input reproduces `best_d == 0`
    with a fabricated `mser_value == 0.0`, though a real decaying transient is sitting in the data.

    A negative deviation sum can still occur from residual rounding after recentering, and is
    clamped to zero as before — but the residual is now bounded by the data's own SPREAD rather
    than an unrelated common offset, so it is too small to out-rank a genuine signal at the scale
    this module is meant to detect.

    @capability warmup_mser_flat
    complexity: O(n_obs)
    counts:
    - n_obs <= len(obs) [kernel_validated]
    @endcapability
    """
    if n_obs > len(obs):
        return _warmup_refusal(DE_ERR_COUNT)
    if n_obs <= 0:
        return _warmup_refusal(DE_ERR_EMPTY)
    if n_obs > DE_MAX_OBS:
        return _warmup_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    if batch_size < 1 or batch_size > DE_MAX_BATCH:
        return _warmup_refusal(DE_ERR_BATCH_RANGE)
    if not de_all_finite(obs, n_obs):
        return _warmup_refusal(DE_ERR_NON_FINITE)
    var m = n_obs // batch_size
    if m < WARMUP_MIN_BATCHES:
        return _warmup_refusal(DE_ERR_TOO_FEW)
    if m > DE_MAX_WORK // 4:
        return _warmup_refusal(DE_ERR_WORK_BUDGET)
    var work = 4 * m
    var tail_dropped = n_obs - m * batch_size

    var means = List[Float64]()
    for j in range(m):
        var total: Float64 = 0.0
        for k in range(batch_size):
            total += obs[j * batch_size + k]
        var bm = total / Float64(batch_size)
        if not de_finite(bm):
            return _warmup_refusal(DE_ERR_NON_FINITE)
        means.append(bm)

    # Suffix sums: suffix_sum[d] and suffix_sq[d] cover batches d..m-1, accumulated RELATIVE to
    # `offset0` rather than in the batch means' own magnitude. `sum (b_i - mean)^2` is translation
    # invariant, so subtracting any fixed constant before accumulating changes no ranking — it
    # only keeps `Q_d` and `S_d` at the scale of the data's own spread instead of at the scale of
    # whatever offset the series happens to carry, which is what keeps `Q_d - S_d^2/k` a real
    # subtraction instead of a cancellation between two nearly-equal huge numbers. See this
    # function's docstring, "ZERO-TRUNCATION DEFECT, FIXED".
    var offset0 = means[0]
    var suffix_sum = List[Float64]()
    var suffix_sq = List[Float64]()
    for _ in range(m + 1):
        suffix_sum.append(0.0)
        suffix_sq.append(0.0)
    for d in range(m - 1, -1, -1):
        var rel = means[d] - offset0
        suffix_sum[d] = suffix_sum[d + 1] + rel
        suffix_sq[d] = suffix_sq[d + 1] + rel * rel

    var boundary = m // 2
    var best_d = 0
    var best_score: Float64 = 0.0
    var have_best = False
    for d in range(boundary + 1):
        var k = m - d
        if k < 2:
            continue
        var kf = Float64(k)
        var ss = suffix_sq[d] - (suffix_sum[d] * suffix_sum[d]) / kf
        if not de_finite(ss):
            continue
        if ss < 0.0:
            ss = 0.0
        var score = ss / (kf * kf)
        if not de_finite(score):
            continue
        if not have_best or score < best_score:
            have_best = True
            best_score = score
            best_d = d

    if not have_best:
        return _warmup_refusal(DE_ERR_NO_STEADY_STATE)

    var at_boundary = best_d == boundary
    var retained_batches = m - best_d
    var discarded_obs = best_d * batch_size
    var retained_obs = retained_batches * batch_size

    # Recompute the reported numbers exactly at the chosen d, through the frozen kernels, over
    # lists whose length IS the count passed — `compute_mean(v, n)` trusts `n`, so the only safe
    # call is one where the two cannot disagree.
    var kept_obs = List[Float64]()
    for i in range(discarded_obs, discarded_obs + retained_obs):
        kept_obs.append(obs[i])
    var kept_means = List[Float64]()
    for d in range(best_d, m):
        kept_means.append(means[d])

    var has_est = False
    var steady: Float64 = 0.0
    if not at_boundary and len(kept_obs) > 0:
        var mu = compute_mean(kept_obs, len(kept_obs))
        if de_finite(mu):
            has_est = True
            steady = mu

    var has_var = False
    var bvar: Float64 = 0.0
    if len(kept_means) > 1:
        var mm = compute_mean(kept_means, len(kept_means))
        if de_finite(mm):
            var v = compute_variance(kept_means, len(kept_means), mm)
            if de_finite(v) and v >= 0.0:
                has_var = True
                bvar = v

    var status = DE_OK
    if at_boundary:
        status = DE_ERR_NO_STEADY_STATE

    return WarmupReport(
        status, n_obs, batch_size, m, best_d, discarded_obs, retained_batches, retained_obs,
        tail_dropped, boundary, at_boundary, True, best_score, has_est, steady,
        has_var, bvar, work, means^,
    )


def warmup_bias_audit(obs: List[Float64], n_obs: Int, n_discard: Int) -> BiasAudit:
    """Compare the full-sample mean with the mean after discarding the first `n_discard`.

    `n_discard` is the START of a range that then SUBSCRIPTS `obs`, which makes both directions
    fatal for different reasons and only one of them expressible in the count grammar:

        0 <= n_discard        -- NOT expressible (the grammar has no lower-bound form), and
                                 fatal: `range(-3, n_obs)` begins at -3 and `obs[-3]` is an
                                 uncatchable process abort, not an error. Checked here.
        n_discard + 1 <= len(obs)  -- expressible, and validated here rather than by the guard,
                                 so `DE_ERR_WARMUP_RANGE` names the argument.

    `n_discard == n_obs` is refused too: discarding everything leaves no truncated mean, and
    reporting `0.0` for it would be indistinguishable from a genuine mean of zero.

    @capability warmup_bias_audit
    complexity: O(n_obs)
    counts:
    - n_obs <= len(obs) [kernel_validated]
    - n_discard + 1 <= len(obs) [kernel_validated]
    @endcapability
    """
    if n_obs > len(obs):
        return _bias_refusal(DE_ERR_COUNT)
    if n_obs <= 0:
        return _bias_refusal(DE_ERR_EMPTY)
    if n_obs > DE_MAX_OBS:
        return _bias_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    if n_discard < 0 or n_discard >= n_obs:
        return _bias_refusal(DE_ERR_WARMUP_RANGE)
    if not de_all_finite(obs, n_obs):
        return _bias_refusal(DE_ERR_NON_FINITE)

    var full = List[Float64]()
    for i in range(n_obs):
        full.append(obs[i])
    var kept = List[Float64]()
    for i in range(n_discard, n_obs):
        kept.append(obs[i])

    var has_full = False
    var full_mean: Float64 = 0.0
    var mf = compute_mean(full, len(full))
    if de_finite(mf):
        has_full = True
        full_mean = mf

    var has_trunc = False
    var trunc_mean: Float64 = 0.0
    if len(kept) > 0:
        var mt = compute_mean(kept, len(kept))
        if de_finite(mt):
            has_trunc = True
            trunc_mean = mt

    var has_bias = False
    var bias: Float64 = 0.0
    if has_full and has_trunc:
        var d = full_mean - trunc_mean
        if de_finite(d):
            has_bias = True
            bias = d

    var has_rel = False
    var rel: Float64 = 0.0
    if has_bias and trunc_mean != 0.0:
        var r = fabs(bias) / fabs(trunc_mean)
        if de_finite(r):
            has_rel = True
            rel = r

    return BiasAudit(
        DE_OK, n_obs, n_discard, n_obs - n_discard, has_full, full_mean, has_trunc, trunc_mean,
        has_bias, bias, has_rel, rel,
    )
