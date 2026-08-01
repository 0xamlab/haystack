"""
discrete_event.queue_sim — seeded M/M/1 and M/M/c runs. Zero Python imports.

Two independent streams, and why that is the whole point
-------------------------------------------------------
Every draw goes through the frozen counter-based generator in `determinism.counter_rng`, which
is ADDRESSED rather than sequential: a value is a pure function of
`(master_seed, scenario_id, replication_id, dim0, dim1, stream_id, draw_index)` with no state
to advance. This module uses two stream ids derived by NAME through `determinism.streams`
(`de_stream_arrival`, `de_stream_service`) and `dim0 = customer index`, so:

  * the service time of customer `i` depends on the seed, the replication and `i` — and on
    NOTHING about arrivals. Changing the arrival rate leaves every service draw untouched, so
    two configurations differ only in the thing being varied. That is what makes a comparison
    valid, and `total_service_time` is returned so it is a MEASURABLE property rather than a
    promise: two runs at different arrival rates must report the same total to the last bit.
  * replications are independent by being different `replication_id` coordinates, not by being
    re-seeded. A re-seeded generator gives replications that can overlap; a coordinate cannot.

`simulation.mm1_simulate` is the frozen alternative and stays reachable. It hardcodes
`seed = 42` inside a private LCG and advances ONE state alternately for inter-arrival and
service draws, so its two sources are interleaved: change the arrival rate and every service
time moves. It also cannot be replicated, because there is no seed to vary.

The frozen closed forms, and the sentinel this module exists to make honest
--------------------------------------------------------------------------
`queueing.mm1_avg_wait_time`, `mm1_avg_system_time`, `mm1_avg_system_size`,
`mm1_avg_queue_length` and `mmc_avg_wait_time` are the exact analytical answers and are called,
never re-derived. But each of them returns `1e18` when the queue is unstable — a finite number
a caller cannot distinguish from an answer, which is the frozen failure-value pattern a new
driver exists to wrap. So `qs_closed_form_flat` decides stability FIRST and reports
`exists = False` with zeros in the value slots when `rho >= 1`; it never calls the frozen kernel
in the region where the frozen kernel answers with a sentinel.

A run at `rho >= 1` is still a legitimate simulation — a transient study of a queue that grows —
so `qs_run_flat` runs it and returns `DE_OK` with `has_closed_form = False`. It is
`discrete_event.replicate` that refuses `DE_ERR_UNSTABLE`, because there the comparison against
the steady state IS the answer being asked for.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: required
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_discrete_event_queue_sim.mojo
benchmark: benchmarks/mojo_benchmarks/bench_discrete_event.mojo
docs: gitbook/engine/discrete-event-simulation.md
version_introduced: 2026.07.31
deprecation_state: active
@endcapability
"""
from determinism.counter_rng import rng_exponential
from operations_research import utilization_factor
from queueing import (
    mm1_avg_queue_length,
    mm1_avg_system_size,
    mm1_avg_system_time,
    mm1_avg_wait_time,
    mmc_avg_wait_time,
    mmc_erlang_c,
)

from discrete_event.contract import (
    DE_ERR_CAPACITY,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_RATE_RANGE,
    DE_ERR_SEED_RANGE,
    DE_MAX_JOBS,
    DE_MAX_SERVERS,
    DE_OK,
    de_finite,
    de_stream_arrival,
    de_stream_service,
)
from discrete_event.resource import resource_serve_flat


fn _rate_ok(rate: Float64) -> Bool:
    """A rate must be a positive real number. Zero is not a slow process: an exponential with
    rate 0 has infinite mean and the frozen kernel answers 0.0 for it, which would silently
    become "everything arrives at once"."""
    return de_finite(rate) and rate > 0.0


fn qs_interarrivals(rate: Float64, n: Int, seed: Int, replication: Int) -> List[Float64]:
    """`n` Exponential(rate) inter-arrival gaps, drawn on the arrival stream.

    Gap `i` is `rng_exponential(seed, 0, replication, i, 0, de_stream_arrival(), 0, rate)` —
    one draw, addressed by customer index, on a stream whose id is derived from the NAME
    "discrete_event.interarrival" rather than picked by hand. A hardcoded id collides with
    whoever picked it first and the two streams silently stop being independent with nothing
    failing.

    Returns an EMPTY list on refusal. A bare `List` return has no status field, and an empty
    list is the only representable absence: a valid call with `n >= 1` always returns exactly
    `n` gaps, so the two cannot be confused. Refused for a non-positive or non-finite rate, for
    `n` outside `[1, DE_MAX_JOBS]`, and for a negative `seed` or `replication` — negative
    because they are converted to `UInt64` for the generator's coordinates, where a negative
    `Int` wraps to an enormous unsigned value and would silently address a different stream
    than the caller asked for.

    @capability qs_interarrivals
    complexity: O(n)
    counts: none
    @endcapability
    """
    var out = List[Float64]()
    if not _rate_ok(rate) or n <= 0 or n > DE_MAX_JOBS or seed < 0 or replication < 0:
        return out^
    var stream = UInt64(de_stream_arrival())
    for i in range(n):
        out.append(
            rng_exponential(UInt64(seed), 0, UInt64(replication), UInt64(i), 0, stream, 0, rate)
        )
    return out^


fn qs_service_times(rate: Float64, n: Int, seed: Int, replication: Int) -> List[Float64]:
    """`n` Exponential(rate) service durations, drawn on the SERVICE stream.

    Identical coordinates to `qs_interarrivals` except the stream id, so service time `i`
    depends on `(seed, replication, i)` and on nothing about the arrival process. That is the
    property that makes two configurations comparable, and it is asserted directly in this
    module's suite: two runs differing only in arrival rate report the same
    `total_service_time`.

    Empty list on refusal, for the same reasons and under the same conditions as
    `qs_interarrivals`.

    @capability qs_service_times
    complexity: O(n)
    counts: none
    @endcapability
    """
    var out = List[Float64]()
    if not _rate_ok(rate) or n <= 0 or n > DE_MAX_JOBS or seed < 0 or replication < 0:
        return out^
    var stream = UInt64(de_stream_service())
    for i in range(n):
        out.append(
            rng_exponential(UInt64(seed), 0, UInt64(replication), UInt64(i), 0, stream, 0, rate)
        )
    return out^


fn qs_arrival_times(rate: Float64, n: Int, seed: Int, replication: Int) -> List[Float64]:
    """The running sum of `qs_interarrivals` — absolute arrival instants, non-decreasing.

    Separate from the gaps because the resource engine needs instants and refuses a
    non-monotone arrival list; a caller that wants to inspect the process itself wants the gaps.
    Empty list on refusal, and also empty if a partial sum overflows to a non-finite instant,
    because a calendar cannot order a non-finite time.

    @capability qs_arrival_times
    complexity: O(n)
    counts: none
    @endcapability
    """
    var gaps = qs_interarrivals(rate, n, seed, replication)
    var out = List[Float64]()
    if len(gaps) == 0:
        return out^
    var clock: Float64 = 0.0
    for i in range(len(gaps)):
        clock += gaps[i]
        if not de_finite(clock):
            var empty = List[Float64]()
            return empty^
        out.append(clock)
    return out^


@fieldwise_init
struct ClosedForm(Copyable, Movable):
    """The EXACT analytical steady state, or a declared absence.

    `exists` is False whenever `rho >= 1`: a queue whose arrival rate reaches its total service
    rate has no steady state, and every quantity below is a limit that does not converge. The
    value slots then hold `0.0` and the flag is the answer — which is precisely what the frozen
    kernels do not do, since they return `1e18` and let the caller believe it.

    `prob_wait` is the Erlang C probability that an arrival has to wait. It has its own flag
    because it is a multi-server quantity: for `capacity == 1` it is simply `rho`, and reporting
    that through the same field as a genuine Erlang C would conflate two different formulas.
    """

    var status: Int
    var exists: Bool
    var capacity: Int
    var rho: Float64
    var wait_in_queue: Float64
    var time_in_system: Float64
    var number_in_system: Float64
    var number_in_queue: Float64
    var has_prob_wait: Bool
    var prob_wait: Float64


fn _closed_form_refusal(code: Int) -> ClosedForm:
    return ClosedForm(code, False, 0, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0.0)


fn qs_closed_form_flat(
    arrival_rate: Float64, service_rate: Float64, capacity: Int
) -> ClosedForm:
    """The exact M/M/1 (capacity 1) or M/M/c steady state, from the frozen queueing kernels.

    Stability is decided BEFORE any frozen kernel is called: `rho = lambda / (c * mu)` via
    `operations_research.utilization_factor`, and `rho >= 1` returns `exists = False` with
    zeros. The frozen `mm1_avg_*` and `mmc_avg_wait_time` answer `1e18` in that region, and
    `1e18` is a finite number that survives every serialisation check and every finiteness
    guard while meaning "there is no answer" — so this driver simply never asks them.

    For `capacity == 1` all four quantities come straight from `queueing.mojo`. For
    `capacity > 1`, `Wq` comes from `queueing.mmc_avg_wait_time` (which is Erlang C over
    `c*mu - lambda`), and the remaining three are the definitional identities on top of it:
    `W = Wq + 1/mu`, `L = lambda * W`, `Lq = lambda * Wq`. Those identities are exact for any
    work-conserving M/M/c, so nothing is being approximated.

    @capability qs_closed_form_flat
    complexity: O(capacity)
    counts: none
    @endcapability
    """
    if not _rate_ok(arrival_rate) or not _rate_ok(service_rate):
        return _closed_form_refusal(DE_ERR_RATE_RANGE)
    if capacity < 1 or capacity > DE_MAX_SERVERS:
        return _closed_form_refusal(DE_ERR_CAPACITY)
    var total_service = Float64(capacity) * service_rate
    if not de_finite(total_service) or total_service <= 0.0:
        return _closed_form_refusal(DE_ERR_RATE_RANGE)
    var rho = utilization_factor(arrival_rate, total_service)
    if not de_finite(rho) or rho < 0.0:
        return _closed_form_refusal(DE_ERR_RATE_RANGE)
    if rho >= 1.0:
        return ClosedForm(DE_OK, False, capacity, rho, 0.0, 0.0, 0.0, 0.0, False, 0.0)

    if capacity == 1:
        var wq = mm1_avg_wait_time(arrival_rate, service_rate)
        var w = mm1_avg_system_time(arrival_rate, service_rate)
        var l = mm1_avg_system_size(arrival_rate, service_rate)
        var lq = mm1_avg_queue_length(arrival_rate, service_rate)
        if not de_finite(wq) or not de_finite(w) or not de_finite(l) or not de_finite(lq):
            return _closed_form_refusal(DE_ERR_RATE_RANGE)
        # For a single server the probability of waiting IS rho, which is a different formula
        # from Erlang C even though the two agree at c = 1. Reported through the flag rather
        # than through the Erlang C slot.
        return ClosedForm(DE_OK, True, capacity, rho, wq, w, l, lq, True, rho)

    var wq_c = mmc_avg_wait_time(arrival_rate, service_rate, capacity)
    var pw = mmc_erlang_c(arrival_rate, service_rate, capacity)
    if not de_finite(wq_c) or wq_c < 0.0:
        return _closed_form_refusal(DE_ERR_RATE_RANGE)
    var w_c = wq_c + 1.0 / service_rate
    var l_c = arrival_rate * w_c
    var lq_c = arrival_rate * wq_c
    if not de_finite(w_c) or not de_finite(l_c) or not de_finite(lq_c):
        return _closed_form_refusal(DE_ERR_RATE_RANGE)
    var has_pw = de_finite(pw) and pw >= 0.0 and pw <= 1.0
    var pw_value: Float64 = 0.0
    if has_pw:
        pw_value = pw
    return ClosedForm(DE_OK, True, capacity, rho, wq_c, w_c, l_c, lq_c, has_pw, pw_value)


@fieldwise_init
struct QueueRun(Copyable, Movable):
    """One seeded replication of an M/M/1 or M/M/c queue, beside the exact answer.

    `total_interarrival_time` and `total_service_time` are not decoration. They are the witnesses
    that the two random sources are independent: two runs differing only in `service_rate` must
    report the same `total_interarrival_time` bit for bit, and two runs differing only in
    `arrival_rate` must report the same `total_service_time`. A generator that interleaved the
    two streams would fail both, and nothing else in a returned estimate would look wrong.

    `mean_wait` is time in QUEUE (Wq) and `mean_system` is time in system (W = Wq + service), the
    same split the frozen closed forms use, so the comparison is like for like.
    """

    var status: Int
    var n_customers: Int
    var capacity: Int
    var n_discarded: Int
    var n_retained: Int
    var seed: Int
    var replication: Int
    var events_processed: Int
    var work_charged: Int
    var max_queue_length: Int
    var horizon: Float64
    var observed_from: Float64
    var observed_span: Float64
    var total_interarrival_time: Float64
    var total_service_time: Float64
    var has_mean_wait: Bool
    var mean_wait: Float64
    var has_mean_system: Bool
    var mean_system: Float64
    var has_time_avg_number: Bool
    var time_avg_number: Float64
    var has_utilization: Bool
    var utilization: Float64
    var has_closed_form: Bool
    var closed_form_rho: Float64
    var closed_form_wait: Float64
    var closed_form_system: Float64
    var closed_form_number: Float64
    var has_little_law_check: Bool
    var little_law_consistent: Bool
    var little_law_gap: Float64


fn _queue_refusal(code: Int) -> QueueRun:
    return QueueRun(
        code, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0.0, 0.0, 0.0, 0.0, 0.0,
        False, 0.0, False, 0.0, False, 0.0, False, 0.0,
        False, 0.0, 0.0, 0.0, 0.0,
        False, False, 0.0,
    )


fn qs_run_flat(
    arrival_rate: Float64, service_rate: Float64, n_customers: Int, capacity: Int,
    seed: Int, replication: Int, warmup_jobs: Int,
) -> QueueRun:
    """Simulate `n_customers` through `capacity` exponential servers and report the estimates.

    `capacity == 1` is M/M/1 and `capacity == c` is M/M/c; the same engine serves both because
    the pool is the same pool. Every job carries priority 0, so the discipline is FIFO — a
    priority mix is a `discrete_event.resource` call, where the caller supplies the ranks.

    `warmup_jobs` initial customers are excluded from the reported means and the observation
    window starts at their successor's arrival. They are still SIMULATED: dropping them from the
    run would change the state the retained customers meet, which is the bias the truncation
    exists to remove. `n_discarded` reports how many were excluded, because a steady-state
    estimate that silently trimmed its own input is not reproducible from its inputs.

    Refusals: a non-positive or non-finite rate -> `DE_ERR_RATE_RANGE`; `n_customers` outside
    `[1, DE_MAX_JOBS]` -> `DE_ERR_EMPTY` / `DE_ERR_DIMENSION_TOO_LARGE`; a negative `seed` or
    `replication` -> `DE_ERR_SEED_RANGE` (a negative `Int` wraps when converted to the
    generator's `UInt64` coordinate and would address a stream the caller never named); and
    every refusal `resource_serve_flat` can produce, forwarded unchanged so a caller sees the
    real defect and not a generic one.

    `has_closed_form` is False when `rho >= 1`. The run itself is fine — a queue that grows is a
    legitimate transient study — but there is no steady state to compare it to, and reporting
    the frozen `1e18` sentinel in those slots would hand back a plausible finite number for a
    quantity that does not exist.

    @capability qs_run_flat
    complexity: O(n_customers log n_customers)
    counts: none
    @endcapability
    """
    if not _rate_ok(arrival_rate) or not _rate_ok(service_rate):
        return _queue_refusal(DE_ERR_RATE_RANGE)
    if n_customers <= 0:
        return _queue_refusal(DE_ERR_EMPTY)
    if n_customers > DE_MAX_JOBS:
        return _queue_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    if seed < 0 or replication < 0:
        return _queue_refusal(DE_ERR_SEED_RANGE)
    if capacity < 1 or capacity > DE_MAX_SERVERS:
        return _queue_refusal(DE_ERR_CAPACITY)

    var gaps = qs_interarrivals(arrival_rate, n_customers, seed, replication)
    var service = qs_service_times(service_rate, n_customers, seed, replication)
    if len(gaps) != n_customers or len(service) != n_customers:
        return _queue_refusal(DE_ERR_RATE_RANGE)

    var arrivals = List[Float64]()
    var total_gap: Float64 = 0.0
    var total_service: Float64 = 0.0
    var clock: Float64 = 0.0
    var priority = List[Int]()
    for i in range(n_customers):
        total_gap += gaps[i]
        total_service += service[i]
        clock += gaps[i]
        if not de_finite(clock):
            return _queue_refusal(DE_ERR_RATE_RANGE)
        arrivals.append(clock)
        priority.append(0)
    if not de_finite(total_gap) or not de_finite(total_service):
        return _queue_refusal(DE_ERR_RATE_RANGE)

    var run = resource_serve_flat(arrivals, service, priority, n_customers, capacity, warmup_jobs)
    if run.status != DE_OK:
        return _queue_refusal(run.status)

    var cf = qs_closed_form_flat(arrival_rate, service_rate, capacity)
    var has_cf = cf.status == DE_OK and cf.exists
    var cf_rho: Float64 = 0.0
    var cf_wait: Float64 = 0.0
    var cf_system: Float64 = 0.0
    var cf_number: Float64 = 0.0
    if has_cf:
        cf_rho = cf.rho
        cf_wait = cf.wait_in_queue
        cf_system = cf.time_in_system
        cf_number = cf.number_in_system

    return QueueRun(
        DE_OK, n_customers, capacity, run.n_discarded, run.n_retained, seed, replication,
        run.events_processed, run.work_charged, run.max_queue_length,
        run.horizon, run.observed_from, run.observed_span, total_gap, total_service,
        run.has_mean_wait, run.mean_wait, run.has_mean_system, run.mean_system,
        run.has_time_avg_number, run.time_avg_number, run.has_utilization, run.utilization,
        has_cf, cf_rho, cf_wait, cf_system, cf_number,
        run.has_little_law_check, run.little_law_consistent, run.little_law_gap,
    )
