"""
discrete_event.replicate — replications, intervals, and the closed-form check. Zero Python.

The one assertion worth more than the rest
------------------------------------------
An M/M/1 queue has EXACT analytical answers: `Wq = rho/(mu-lambda)`, `W = 1/(mu-lambda)`,
`L = rho/(1-rho)` and utilisation `rho`. They are algebra, not estimates, and they are already
in the frozen tree (`queueing.mojo`). So a simulator of an M/M/1 queue has a right answer to be
wrong against, and `replicate_mm1_flat` reports whether each analytical value falls inside the
replications' confidence interval. If it does not, the simulator is wrong — the algebra is not.

That is why this driver exists at all. Every other number a discrete-event simulator produces is
unfalsifiable without a reference; this one is falsifiable, so it is the assertion that protects
the whole package.

Independence is a coordinate, not a re-seed
------------------------------------------
Replication `r` draws at `replication_id = r`, a COORDINATE of the frozen counter-based
generator. Two replications therefore address disjoint parts of the stream by construction. The
usual alternative — re-seeding a stateful generator per replication — gives replications whose
streams can overlap, and overlapping replications are correlated while looking independent,
which inflates confidence in exactly the direction nobody checks.

The PILOT uses `replication_id = 0` and the replications use `1 .. n_reps`. That split is
deliberate: the warm-up truncation is chosen from the pilot and then APPLIED to different data,
so the amount discarded is not tuned to the sample it is judging. Choosing the truncation from
the same runs it is applied to biases the interval, and the bias is invisible because every
number involved looks reasonable.

Why a Student-t interval and not a normal one
--------------------------------------------
The variance is estimated from the same handful of replications as the mean, so the pivot is a
`t` on `n_reps - 1` degrees of freedom. With 10 replications the 97.5% normal quantile is 1.96
and the `t` quantile is 2.26 — a normal interval would be 14% too narrow, which is a false
precision that would make the coverage check pass more often than it should.
`inference.core.inference_t_quantile` is the tree's t quantile and is called; it reports ABSENT
rather than a bracket edge when the quantile is outside its bracket, and that absence is carried
through to `has_ci = False` rather than being replaced by a plausible number.

An unstable queue is refused here
---------------------------------
`rho >= 1` has no steady state, so there is nothing to cover and `DE_ERR_UNSTABLE` is the
answer. `queue_sim.qs_run_flat` deliberately does NOT refuse it — a growing queue is a
legitimate transient study — but here the comparison against the steady state IS the request.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: required
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_discrete_event_replicate.mojo
benchmark: benchmarks/mojo_benchmarks/bench_discrete_event.mojo
docs: gitbook/engine/discrete-event-simulation.md
version_introduced: 2026.07.31
deprecation_state: active
@endcapability
"""
from std.math import sqrt

from inference.core import inference_t_quantile
from stats import compute_mean, compute_variance

from discrete_event.contract import (
    DE_ERR_BATCH_RANGE,
    DE_ERR_CAPACITY,
    DE_ERR_COUNT,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_LEVEL_RANGE,
    DE_ERR_NON_FINITE,
    DE_ERR_NO_ESTIMATE,
    DE_ERR_NO_STEADY_STATE,
    DE_ERR_RATE_RANGE,
    DE_ERR_SEED_RANGE,
    DE_ERR_TOO_FEW,
    DE_ERR_TOO_FEW_REPS,
    DE_ERR_UNSTABLE,
    DE_ERR_WORK_BUDGET,
    DE_MAX_BATCH,
    DE_MAX_JOBS,
    DE_MAX_REPLICATIONS,
    DE_MAX_SERVERS,
    DE_MAX_WORK,
    DE_OK,
    de_all_finite,
    de_finite,
    de_product_fits,
)
from discrete_event.queue_sim import qs_arrival_times, qs_closed_form_flat, qs_service_times
from discrete_event.resource import resource_serve_flat, resource_work_charge
from discrete_event.warmup import warmup_mser_flat


@fieldwise_init
struct ReplicationCI(Copyable, Movable):
    """A mean over independent replications and its Student-t interval.

    `has_mean` and `has_ci` are SEPARATE flags because they fail separately. One replication has
    a mean and no interval: the mean is a real answer and the interval does not exist, and
    collapsing the two would either hide a usable mean or invent an interval of width zero. So a
    single replication returns `DE_ERR_TOO_FEW_REPS` with `has_mean = True` and `has_ci = False`
    — a refusal that still carries what does exist.

    `half_width` is reported separately from the bounds because it is what a caller uses to
    decide how many more replications to run, and deriving it from the bounds loses a bit of
    precision for no reason.
    """

    var status: Int
    var n_reps: Int
    var level: Float64
    var has_mean: Bool
    var mean: Float64
    var has_variance: Bool
    var variance: Float64
    var has_std_error: Bool
    var std_error: Float64
    var has_t_critical: Bool
    var t_critical: Float64
    var has_ci: Bool
    var ci_lower: Float64
    var ci_upper: Float64
    var has_half_width: Bool
    var half_width: Float64


fn _ci_refusal(code: Int, n_reps: Int, level: Float64) -> ReplicationCI:
    return ReplicationCI(
        code, n_reps, level, False, 0.0, False, 0.0, False, 0.0, False, 0.0, False, 0.0, 0.0,
        False, 0.0,
    )


fn _ci_of(estimates: List[Float64], level: Float64) -> ReplicationCI:
    """The interval over ALL of `estimates`, used internally so the four metrics share one path.

    Takes the whole list rather than a count, which removes the count/length relation entirely
    at every internal call site: the two cannot disagree if there is only one of them.
    """
    var n = len(estimates)
    if n <= 0:
        return _ci_refusal(DE_ERR_EMPTY, 0, level)
    var mu = compute_mean(estimates, n)
    if not de_finite(mu):
        return _ci_refusal(DE_ERR_NON_FINITE, n, level)
    if n < 2:
        return ReplicationCI(
            DE_ERR_TOO_FEW_REPS, n, level, True, mu, False, 0.0, False, 0.0, False, 0.0,
            False, 0.0, 0.0, False, 0.0,
        )
    var var_hat = compute_variance(estimates, n, mu)
    if not de_finite(var_hat) or var_hat < 0.0:
        return ReplicationCI(
            DE_ERR_NON_FINITE, n, level, True, mu, False, 0.0, False, 0.0, False, 0.0,
            False, 0.0, 0.0, False, 0.0,
        )
    var se = sqrt(var_hat / Float64(n))
    if not de_finite(se):
        return ReplicationCI(
            DE_ERR_NON_FINITE, n, level, True, mu, True, var_hat, False, 0.0, False, 0.0,
            False, 0.0, 0.0, False, 0.0,
        )
    var upper_p = 1.0 - (1.0 - level) * 0.5
    var t = inference_t_quantile(upper_p, Float64(n - 1))
    if not de_finite(t) or t < 0.0:
        # The frozen quantile reports ABSENT for a request outside its bracket rather than
        # returning the bracket edge. Carried through as "no interval", never replaced by a
        # plausible-looking critical value.
        return ReplicationCI(
            DE_ERR_NO_ESTIMATE, n, level, True, mu, True, var_hat, True, se, False, 0.0,
            False, 0.0, 0.0, False, 0.0,
        )
    var hw = t * se
    if not de_finite(hw) or not de_finite(mu - hw) or not de_finite(mu + hw):
        return ReplicationCI(
            DE_ERR_NON_FINITE, n, level, True, mu, True, var_hat, True, se, True, t, False,
            0.0, 0.0, False, 0.0,
        )
    return ReplicationCI(
        DE_OK, n, level, True, mu, True, var_hat, True, se, True, t, True, mu - hw, mu + hw,
        True, hw,
    )


fn replicate_ci_flat(
    estimates: List[Float64], n_reps: Int, level: Float64
) -> ReplicationCI:
    """A Student-t interval over the first `n_reps` per-replication estimates.

    General-purpose: the estimates may come from `queue_sim`, from `resource`, or from anything
    else the caller replicated, as long as the replications are independent. This driver cannot
    verify independence and does not pretend to — it is the caller's coordinates that make it
    true, which is why `queue_sim` addresses replications rather than re-seeding.

    Refusals: `n_reps` above `len(estimates)` -> `DE_ERR_COUNT`, checked before the first read,
    because a read past a `List` end aborts the worker process rather than raising;
    `n_reps <= 0` -> `DE_ERR_EMPTY`; above `DE_MAX_REPLICATIONS` ->
    `DE_ERR_DIMENSION_TOO_LARGE`; `level` outside the OPEN interval `(0, 1)` ->
    `DE_ERR_LEVEL_RANGE` (a 0% interval is a point and a 100% interval is the whole line;
    neither is a request this can answer); a non-finite estimate -> `DE_ERR_NON_FINITE`;
    `n_reps == 1` -> `DE_ERR_TOO_FEW_REPS` with the mean present and no interval.

    @capability replicate_ci_flat
    complexity: O(n_reps)
    counts:
    - n_reps <= len(estimates) [kernel_validated]
    @endcapability
    """
    if n_reps > len(estimates):
        return _ci_refusal(DE_ERR_COUNT, 0, level)
    if n_reps <= 0:
        return _ci_refusal(DE_ERR_EMPTY, 0, level)
    if n_reps > DE_MAX_REPLICATIONS:
        return _ci_refusal(DE_ERR_DIMENSION_TOO_LARGE, n_reps, level)
    if not de_finite(level) or level <= 0.0 or level >= 1.0:
        return _ci_refusal(DE_ERR_LEVEL_RANGE, n_reps, level)
    if not de_all_finite(estimates, n_reps):
        return _ci_refusal(DE_ERR_NON_FINITE, n_reps, level)
    var trimmed = List[Float64]()
    for i in range(n_reps):
        trimmed.append(estimates[i])
    return _ci_of(trimmed, level)


@fieldwise_init
struct Mm1Validation(Copyable, Movable):
    """Four replicated estimates, four intervals, and whether the exact answer is inside each.

    `n_metrics_covered` out of `n_metrics_checked` is the headline. At a 95% level a single
    metric misses about one run in twenty by construction, so a caller comparing configurations
    should read the count and the intervals, not a single boolean — which is why there is no
    single boolean.

    `warmup_jobs_used` and `pilot_*` are reported because a steady-state estimate is only
    reproducible if the truncation that produced it is part of the output. An estimator that
    silently trimmed its own input cannot be re-derived from its inputs.
    """

    var status: Int
    var n_reps_requested: Int
    var n_reps_run: Int
    var n_reps_refused: Int
    var n_customers: Int
    var capacity: Int
    var seed: Int
    var level: Float64
    var has_t_critical: Bool
    var t_critical: Float64
    var pilot_batch_size: Int
    var pilot_n_batches: Int
    var pilot_tail_dropped: Int
    var warmup_jobs_used: Int
    var closed_form_rho: Float64
    var closed_form_wait: Float64
    var closed_form_system: Float64
    var closed_form_number: Float64
    var has_wait_ci: Bool
    var wait_mean: Float64
    var wait_ci_lower: Float64
    var wait_ci_upper: Float64
    var wait_covered: Bool
    var has_system_ci: Bool
    var system_mean: Float64
    var system_ci_lower: Float64
    var system_ci_upper: Float64
    var system_covered: Bool
    var has_number_ci: Bool
    var number_mean: Float64
    var number_ci_lower: Float64
    var number_ci_upper: Float64
    var number_covered: Bool
    var has_util_ci: Bool
    var util_mean: Float64
    var util_ci_lower: Float64
    var util_ci_upper: Float64
    var util_covered: Bool
    var n_metrics_checked: Int
    var n_metrics_covered: Int
    var work_charged: Int


fn _validation_refusal(code: Int) -> Mm1Validation:
    return Mm1Validation(
        code, 0, 0, 0, 0, 0, 0, 0.0, False, 0.0, 0, 0, 0, 0,
        0.0, 0.0, 0.0, 0.0,
        False, 0.0, 0.0, 0.0, False,
        False, 0.0, 0.0, 0.0, False,
        False, 0.0, 0.0, 0.0, False,
        False, 0.0, 0.0, 0.0, False,
        0, 0, 0,
    )


fn _covers(ci: ReplicationCI, target: Float64) -> Bool:
    """True when a finite `target` lies inside a computed interval.

    No tolerance: interval membership is exact, and widening it by an epsilon would report
    coverage for a value the interval excludes. False when the interval does not exist, which
    is why `has_*_ci` is reported beside every coverage flag — "not covered" and "not checked"
    are different findings.
    """
    if not ci.has_ci or not de_finite(target):
        return False
    return target >= ci.ci_lower and target <= ci.ci_upper


fn replicate_mm1_flat(
    arrival_rate: Float64, service_rate: Float64, n_customers: Int, capacity: Int,
    n_reps: Int, seed: Int, level: Float64, batch_size: Int,
) -> Mm1Validation:
    """Replicate an M/M/1 or M/M/c run and check the exact steady state against the intervals.

    Sequence, in order, because each step depends on the last:

      1. Refuse unless the closed form EXISTS. `rho >= 1` -> `DE_ERR_UNSTABLE`: there is no
         steady state to cover, and the frozen kernels answer `1e18` in that region, which is a
         finite number meaning "no answer".
      2. Run a PILOT at `replication_id = 0` with no truncation, and put MSER on its per-job
         waiting times. `DE_ERR_NO_STEADY_STATE` from the pilot is forwarded: if the transient
         has not settled within `n_customers`, no amount of replication fixes it, and a longer
         run is the answer rather than a wider interval.
      3. Run `n_reps` replications at `replication_id = 1 .. n_reps`, each discarding the
         truncation the PILOT chose — a different sample from the one that chose it.
      4. Form four Student-t intervals and report which of the four exact values they contain.

    `capacity > 1` is M/M/c and the same four comparisons apply, with the frozen
    `queueing.mmc_avg_wait_time` supplying `Wq`.

    Refusals beyond step 1: a non-positive or non-finite rate -> `DE_ERR_RATE_RANGE`;
    `n_customers` outside `[1, DE_MAX_JOBS]`; `capacity` outside `[1, DE_MAX_SERVERS]` ->
    `DE_ERR_CAPACITY`; `n_reps` outside `[2, DE_MAX_REPLICATIONS]` -> `DE_ERR_TOO_FEW_REPS` /
    `DE_ERR_DIMENSION_TOO_LARGE` (one replication cannot produce an interval, and this driver's
    whole output is intervals); a negative `seed` -> `DE_ERR_SEED_RANGE`; `level` outside
    `(0, 1)` -> `DE_ERR_LEVEL_RANGE`; `batch_size` outside `[1, DE_MAX_BATCH]` ->
    `DE_ERR_BATCH_RANGE`.

    Work is charged as a PRODUCT: `(n_reps + 1) * resource_work_charge(n_customers)`, formed by
    division so it cannot wrap. Charging only `n_reps`, or only `n_customers`, would be a budget
    that counts one factor of a product — the defect that measured 0.49s against 23.89s at an
    identical declared cost.

    @capability replicate_mm1_flat
    complexity: O(n_reps * n_customers log n_customers)
    counts: none
    @endcapability
    """
    if not de_finite(arrival_rate) or arrival_rate <= 0.0:
        return _validation_refusal(DE_ERR_RATE_RANGE)
    if not de_finite(service_rate) or service_rate <= 0.0:
        return _validation_refusal(DE_ERR_RATE_RANGE)
    if n_customers <= 0:
        return _validation_refusal(DE_ERR_EMPTY)
    if n_customers > DE_MAX_JOBS:
        return _validation_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    if capacity < 1 or capacity > DE_MAX_SERVERS:
        return _validation_refusal(DE_ERR_CAPACITY)
    if n_reps < 2:
        return _validation_refusal(DE_ERR_TOO_FEW_REPS)
    if n_reps > DE_MAX_REPLICATIONS:
        return _validation_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    if seed < 0:
        return _validation_refusal(DE_ERR_SEED_RANGE)
    if not de_finite(level) or level <= 0.0 or level >= 1.0:
        return _validation_refusal(DE_ERR_LEVEL_RANGE)
    if batch_size < 1 or batch_size > DE_MAX_BATCH:
        return _validation_refusal(DE_ERR_BATCH_RANGE)

    var per_run = resource_work_charge(n_customers)
    if per_run < 0:
        return _validation_refusal(DE_ERR_WORK_BUDGET)
    if not de_product_fits(n_reps + 1, per_run, DE_MAX_WORK):
        return _validation_refusal(DE_ERR_WORK_BUDGET)
    var charge = (n_reps + 1) * per_run

    var cf = qs_closed_form_flat(arrival_rate, service_rate, capacity)
    if cf.status != DE_OK:
        return _validation_refusal(cf.status)
    if not cf.exists:
        return _validation_refusal(DE_ERR_UNSTABLE)

    var priority = List[Int]()
    for _ in range(n_customers):
        priority.append(0)

    # ── step 2: the pilot chooses the truncation, from data it will not be applied to ──
    var pilot_arrivals = qs_arrival_times(arrival_rate, n_customers, seed, 0)
    var pilot_service = qs_service_times(service_rate, n_customers, seed, 0)
    if len(pilot_arrivals) != n_customers or len(pilot_service) != n_customers:
        return _validation_refusal(DE_ERR_RATE_RANGE)
    var pilot = resource_serve_flat(
        pilot_arrivals, pilot_service, priority, n_customers, capacity, 0
    )
    if pilot.status != DE_OK:
        return _validation_refusal(pilot.status)
    var transient = warmup_mser_flat(pilot.wait, n_customers, batch_size)
    if transient.status == DE_ERR_NO_STEADY_STATE:
        return _validation_refusal(DE_ERR_NO_STEADY_STATE)
    if transient.status == DE_ERR_TOO_FEW:
        return _validation_refusal(DE_ERR_TOO_FEW)
    if transient.status != DE_OK:
        return _validation_refusal(transient.status)
    var warmup_jobs = transient.n_discarded_obs
    if warmup_jobs < 0 or warmup_jobs >= n_customers:
        # MSER cannot exceed half the observations, so this is unreachable today. It is checked
        # anyway because `warmup_jobs` becomes a SUBSCRIPT inside `resource_serve_flat`, and a
        # bad subscript is an uncatchable process abort rather than a wrong number.
        return _validation_refusal(DE_ERR_NO_STEADY_STATE)

    # ── step 3: the replications ──
    var wq = List[Float64]()
    var w = List[Float64]()
    var l = List[Float64]()
    var rho = List[Float64]()
    var refused = 0
    for r in range(1, n_reps + 1):
        var arrivals = qs_arrival_times(arrival_rate, n_customers, seed, r)
        var service = qs_service_times(service_rate, n_customers, seed, r)
        if len(arrivals) != n_customers or len(service) != n_customers:
            refused += 1
            continue
        var run = resource_serve_flat(
            arrivals, service, priority, n_customers, capacity, warmup_jobs
        )
        if run.status != DE_OK:
            refused += 1
            continue
        if not run.has_mean_wait or not run.has_mean_system:
            refused += 1
            continue
        if not run.has_time_avg_number or not run.has_utilization:
            refused += 1
            continue
        wq.append(run.mean_wait)
        w.append(run.mean_system)
        l.append(run.time_avg_number)
        rho.append(run.utilization)

    var n_run = len(wq)
    if n_run < 2:
        return _validation_refusal(DE_ERR_TOO_FEW_REPS)

    # ── step 4: four intervals, four coverage verdicts ──
    var ci_wq = _ci_of(wq, level)
    var ci_w = _ci_of(w, level)
    var ci_l = _ci_of(l, level)
    var ci_rho = _ci_of(rho, level)

    var wq_cov = _covers(ci_wq, cf.wait_in_queue)
    var w_cov = _covers(ci_w, cf.time_in_system)
    var l_cov = _covers(ci_l, cf.number_in_system)
    var rho_cov = _covers(ci_rho, cf.rho)

    var checked = 0
    var covered = 0
    if ci_wq.has_ci:
        checked += 1
        if wq_cov:
            covered += 1
    if ci_w.has_ci:
        checked += 1
        if w_cov:
            covered += 1
    if ci_l.has_ci:
        checked += 1
        if l_cov:
            covered += 1
    if ci_rho.has_ci:
        checked += 1
        if rho_cov:
            covered += 1

    var has_t = ci_wq.has_t_critical
    var t_value: Float64 = 0.0
    if has_t:
        t_value = ci_wq.t_critical

    return Mm1Validation(
        DE_OK, n_reps, n_run, refused, n_customers, capacity, seed, level, has_t, t_value,
        batch_size, transient.n_batches, transient.n_tail_dropped, warmup_jobs,
        cf.rho, cf.wait_in_queue, cf.time_in_system, cf.number_in_system,
        ci_wq.has_ci, ci_wq.mean, ci_wq.ci_lower, ci_wq.ci_upper, wq_cov,
        ci_w.has_ci, ci_w.mean, ci_w.ci_lower, ci_w.ci_upper, w_cov,
        ci_l.has_ci, ci_l.mean, ci_l.ci_lower, ci_l.ci_upper, l_cov,
        ci_rho.has_ci, ci_rho.mean, ci_rho.ci_lower, ci_rho.ci_upper, rho_cov,
        checked, covered, charge,
    )
