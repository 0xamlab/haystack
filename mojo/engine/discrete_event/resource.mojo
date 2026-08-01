"""
discrete_event.resource — a capacity pool with a priority waiting queue. Zero Python imports.

This is the deterministic engine: given an arrival time, a service duration and a priority per
job, it runs the whole event calendar and reports what happened. No randomness enters here at
all, which is deliberate — a simulator whose mechanics and whose generator are in the same
function cannot be tested against a hand-computed schedule. `discrete_event.queue_sim` supplies
seeded draws and calls this.

The resource is a Petri place
----------------------------
"Are there `k` free servers" is exactly `marking >= target`, which is
`petri_net.coverability_check` — a frozen kernel, called rather than re-spelled as `free >= 1`.
The point is not to save a comparison; it is that the availability test and the Petri-net
semantics the tree already publishes are the SAME predicate, so a reader who knows one knows
the other. Seizing decrements the place and releasing increments it, which is
`petri_net.incidence_value(output_weight, input_weight)` with weight 1.

Two queues, ONE ordering rule
-----------------------------
The event calendar orders on `(time, priority, sequence)`. The waiting queue is the same
`_EventHeap` from `discrete_event.calendar` with every time set to 0.0, so its order collapses
to `(priority, sequence)` — priority rank first, then arrival order within a rank. That is
reuse, not coincidence: one heap, one comparison, no chance of the two queues disagreeing about
what "higher priority" means. Rule 3 applies inside a package, and a second heap here would be
a second ordering rule.

Coincident events: departures first, and why it is observable
------------------------------------------------------------
A departure and an arrival at the same instant have to resolve somehow. This engine gives every
DEPARTURE calendar priority 0 and every ARRIVAL calendar priority `1 + job_priority`, so at
equal time every departure fires first. That is the standard convention and it is not cosmetic:
with the arrival first, the arriving job joins the queue, `max_queue_length` records a job
waiting, and the departure then serves it at the same timestamp for a wait of zero. The wait is
the same either way; the reported maximum queue length is not. Freeing the server first makes
`max_queue_length` count jobs that genuinely waited.

The consequence for the declared range: a job priority must be at most `DE_MAX_PRIORITY - 1`,
because the calendar carries `1 + job_priority`.

The observation window, and the one exact identity
--------------------------------------------------
`warmup_jobs` names how many initial jobs are excluded from the reported means, and the window
starts at `arrival[warmup_jobs]`. With `warmup_jobs = 0` the window is the whole run and then
Little's law is EXACT, not approximate: the time integral of the number in system over
`[arrival[0], horizon]` equals the sum of every job's sojourn time, term for term, because
`n(t)` counts exactly the jobs whose sojourn covers `t`. So `L = lambda * W` must hold to
floating-point rounding, and `little_law_consistent` says whether it did. The two sides are
accumulated in DIFFERENT ORDERS — the area over `2n` event intervals, the sojourn sum over `n`
jobs — so the tolerance is widened by one ulp per addition and by nothing else.

With `warmup_jobs > 0` the identity no longer holds: jobs that arrived before the cut are still
in the system and contribute area with no sojourn term inside the window. So
`has_little_law_check` is False there, rather than a boolean computed from a broken premise.
That is the point of the flag: an unavailable check is reported unavailable, not answered True.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_discrete_event_resource.mojo
benchmark: benchmarks/mojo_benchmarks/bench_discrete_event.mojo
docs: gitbook/engine/discrete-event-simulation.md
version_introduced: 2026.07.31
deprecation_state: active
@endcapability
"""
from operations_research import little_law_l
from petri_net import coverability_check
from stats import compute_mean

from discrete_event.calendar import (
    _EventHeap,
    _heap_drop_root,
    _heap_push,
    _heap_size,
)
from discrete_event.contract import (
    DE_ERR_CAPACITY,
    DE_ERR_COUNT,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_NEGATIVE_DURATION,
    DE_ERR_NON_FINITE,
    DE_ERR_PRIORITY_RANGE,
    DE_ERR_TIME_BACKWARD,
    DE_ERR_WARMUP_RANGE,
    DE_ERR_WORK_BUDGET,
    DE_MAX_JOBS,
    DE_MAX_PRIORITY,
    DE_MAX_SERVERS,
    DE_MAX_WORK,
    DE_OK,
    de_agrees,
    de_all_finite,
    de_finite,
    de_heap_levels,
    de_heap_work,
    de_nondecreasing,
)

# Event KINDS, not status codes: they name what an event is, and they never appear in a
# `status` field. The status vocabulary stays the single 400-419 range in `contract.mojo`.
comptime RES_EVENT_ARRIVAL: Int = 0
comptime RES_EVENT_DEPARTURE: Int = 1

# The calendar priority a departure carries, below every arrival's `1 + job_priority`.
comptime RES_DEPARTURE_RANK: Int = 0


@fieldwise_init
struct ResourceRun(Copyable, Movable):
    """Everything one run of a capacity pool produced.

    Per-job arrays are returned for ALL `n_jobs`, index-aligned with the caller's input, not
    only for the retained ones. A mean hides which jobs waited, and the job that waited is
    usually the interesting one; `discrete_event.warmup` also needs the raw series to find the
    transient at all.

    Every `has_*` flag guards the field named after it. When a flag is False its value slot
    holds exactly `0.0` — never a NaN, because the dispatch refuses to serialise a non-finite
    and one absent quantity would turn eleven present ones into a typed error, and never a bare
    `0.0` without the flag, because a mean wait of zero is a real answer for a queue nobody
    waited in.
    """

    var status: Int
    var n_jobs: Int
    var n_served: Int
    var n_discarded: Int
    var n_retained: Int
    var capacity: Int
    var events_processed: Int
    var work_charged: Int
    var max_queue_length: Int
    var horizon: Float64
    var observed_from: Float64
    var observed_span: Float64
    var has_mean_wait: Bool
    var mean_wait: Float64
    var has_mean_system: Bool
    var mean_system: Float64
    var has_time_avg_number: Bool
    var time_avg_number: Float64
    var has_utilization: Bool
    var utilization: Float64
    var has_little_law_check: Bool
    var little_law_consistent: Bool
    var little_law_gap: Float64
    var wait: List[Float64]
    var start: List[Float64]
    var depart: List[Float64]


fn _run_refusal(code: Int) -> ResourceRun:
    """A refusal carries no numbers and no per-job arrays.

    A partially-filled run would be indistinguishable from a short simulation, and every
    downstream mean would be computed over a prefix nobody asked for.
    """
    return ResourceRun(
        code, 0, 0, 0, 0, 0, 0, 0, 0,
        0.0, 0.0, 0.0,
        False, 0.0, False, 0.0, False, 0.0, False, 0.0,
        False, False, 0.0,
        List[Float64](), List[Float64](), List[Float64](),
    )


fn resource_work_charge(n_jobs: Int) -> Int:
    """Charged operations for a run of `n_jobs`, or -1 when it does not fit `DE_MAX_WORK`.

    Two heaps are charged, not one. The calendar sees exactly `2 * n_jobs` entries (one arrival
    and one departure per job) and the waiting queue sees at most `n_jobs`, and each entry is
    pushed once and popped once at a cost of one heap depth. Charging `n_jobs` alone would be
    the defect that measured 0.49s against 23.89s at an identical declared cost: the depth is a
    factor of the product, and a budget that counts one factor of a product is not a budget.

    Returns -1 rather than a wrapped sum, because a wrapped work figure reads as a small cost
    for an enormous request.

    @capability resource_work_charge
    complexity: O(log n_jobs)
    counts: none
    @endcapability
    """
    if n_jobs <= 0:
        return 0
    var events = 2 * n_jobs
    var calendar = 2 * events * de_heap_levels(events)
    var waiting = 2 * n_jobs * de_heap_levels(n_jobs)
    if calendar < 0 or waiting < 0:
        return -1
    if calendar > DE_MAX_WORK - waiting:
        return -1
    return calendar + waiting


fn resource_serve_flat(
    arrival: List[Float64], service: List[Float64], priority: List[Int],
    n_jobs: Int, capacity: Int, warmup_jobs: Int,
) -> ResourceRun:
    """Run `n_jobs` through a pool of `capacity` identical servers, non-preemptive.

    The three input lists are index-aligned columns of one job table: when job `i` arrives, how
    long it needs, and its priority rank (0 most urgent). Arrivals must be non-decreasing;
    service durations must be non-negative; both must be finite.

    Discipline: a job that finds a free server starts immediately. Otherwise it joins a
    priority waiting queue and is chosen when a server frees, lowest rank first and arrival
    order within a rank. Service is never interrupted.

    Refusals, one code each, all checked BEFORE the first subscript:

      * `n_jobs` above any of the three list lengths -> `DE_ERR_COUNT`. This is the relation
        that ends the worker process if it is wrong: a read past a `List` end is an uncatchable
        abort, `try`/`except` does not help, and the generated A-Z suite calls every contract
        function with five-element lists and `5` for every `Int`.
      * `n_jobs <= 0` -> `DE_ERR_EMPTY`; above `DE_MAX_JOBS` -> `DE_ERR_DIMENSION_TOO_LARGE`.
      * `capacity` outside `[1, DE_MAX_SERVERS]` -> `DE_ERR_CAPACITY`. Zero servers is not a
        slow queue, it is a queue that never empties.
      * `warmup_jobs` outside `[0, n_jobs - 1]` -> `DE_ERR_WARMUP_RANGE`. This one is a
        SUBSCRIPT (`arrival[warmup_jobs]` sets the window start) and is therefore checked in
        BOTH directions: a negative count merely reads nothing, but a negative index aborts the
        process. `warmup_jobs == n_jobs` is refused too — discarding everything leaves no
        estimate, which is a request that cannot be answered rather than one answered with
        zeros.
      * a non-finite arrival or service -> `DE_ERR_NON_FINITE`; a negative service ->
        `DE_ERR_NEGATIVE_DURATION`; a negative or out-of-order arrival ->
        `DE_ERR_TIME_BACKWARD`. Out-of-order arrivals are refused because the window start
        would otherwise be an arbitrary instant in the middle of the run.
      * a priority outside `[0, DE_MAX_PRIORITY - 1]` -> `DE_ERR_PRIORITY_RANGE`. The upper
        bound is one below the ceiling because the calendar carries `1 + job_priority`.
      * charged work above `DE_MAX_WORK` -> `DE_ERR_WORK_BUDGET`.
      * a departure time that overflows to infinity mid-run -> `DE_ERR_NON_FINITE`, and the
        whole run is discarded. A non-finite event time turns the strict order into a non-order
        (every comparison against it is False) and the heap silently stops being a heap, so
        there is no salvageable prefix.


    @capability resource_serve_flat
    complexity: O(n_jobs log n_jobs)
    counts:
    - n_jobs <= len(arrival, service, priority) [kernel_validated]
    - warmup_jobs + 1 <= len(arrival) [kernel_validated]
    @endcapability
    """
    if n_jobs > len(arrival) or n_jobs > len(service) or n_jobs > len(priority):
        return _run_refusal(DE_ERR_COUNT)
    if n_jobs <= 0:
        return _run_refusal(DE_ERR_EMPTY)
    if n_jobs > DE_MAX_JOBS:
        return _run_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    if capacity < 1 or capacity > DE_MAX_SERVERS:
        return _run_refusal(DE_ERR_CAPACITY)
    if warmup_jobs < 0 or warmup_jobs >= n_jobs:
        return _run_refusal(DE_ERR_WARMUP_RANGE)
    if not de_all_finite(arrival, n_jobs) or not de_all_finite(service, n_jobs):
        return _run_refusal(DE_ERR_NON_FINITE)
    if arrival[0] < 0.0 or not de_nondecreasing(arrival, n_jobs):
        return _run_refusal(DE_ERR_TIME_BACKWARD)
    for i in range(n_jobs):
        if service[i] < 0.0:
            return _run_refusal(DE_ERR_NEGATIVE_DURATION)
        if priority[i] < 0 or priority[i] > DE_MAX_PRIORITY - 1:
            return _run_refusal(DE_ERR_PRIORITY_RANGE)
    var charge = resource_work_charge(n_jobs)
    if charge < 0:
        return _run_refusal(DE_ERR_WORK_BUDGET)

    var wait = List[Float64]()
    var start = List[Float64]()
    var depart = List[Float64]()
    for _ in range(n_jobs):
        wait.append(0.0)
        start.append(0.0)
        depart.append(0.0)

    var cal = _EventHeap()
    var next_seq = 0
    for i in range(n_jobs):
        _heap_push(cal, arrival[i], 1 + priority[i], next_seq, RES_EVENT_ARRIVAL, i)
        next_seq += 1

    # The waiting queue is the same heap with every time 0.0, so its order is (priority,
    # arrival index). Arrivals are non-decreasing, so the index IS arrival order and the
    # discipline is FIFO within a rank.
    var waiting = _EventHeap()

    var free = capacity
    var in_system = 0
    var served = 0
    var events = 0
    var max_queue = 0
    var t_prev: Float64 = 0.0
    var area: Float64 = 0.0
    var busy_area: Float64 = 0.0
    var observed_from = arrival[warmup_jobs]

    while _heap_size(cal) > 0:
        var t = cal.t[0]
        var kind = cal.kind[0]
        var job = cal.ent[0]
        _heap_drop_root(cal)
        events += 1

        # Accumulate over [t_prev, t] clipped to the observation window, using the state
        # BEFORE this event — which is what "the number in system during that interval" means.
        var lo = t_prev
        if observed_from > lo:
            lo = observed_from
        if t > lo:
            var dt = t - lo
            area += Float64(in_system) * dt
            busy_area += Float64(capacity - free) * dt
        t_prev = t

        if kind == RES_EVENT_ARRIVAL:
            in_system += 1
            if coverability_check(free, 1):
                free -= 1
                start[job] = t
                wait[job] = 0.0
                var dep = t + service[job]
                if not de_finite(dep):
                    return _run_refusal(DE_ERR_NON_FINITE)
                _heap_push(cal, dep, RES_DEPARTURE_RANK, next_seq, RES_EVENT_DEPARTURE, job)
                next_seq += 1
            else:
                _heap_push(waiting, 0.0, priority[job], job, job, job)
                if _heap_size(waiting) > max_queue:
                    max_queue = _heap_size(waiting)
        else:
            depart[job] = t
            in_system -= 1
            free += 1
            served += 1
            if _heap_size(waiting) > 0:
                var next_job = waiting.ent[0]
                _heap_drop_root(waiting)
                free -= 1
                start[next_job] = t
                wait[next_job] = t - arrival[next_job]
                var dep2 = t + service[next_job]
                if not de_finite(dep2):
                    return _run_refusal(DE_ERR_NON_FINITE)
                _heap_push(
                    cal, dep2, RES_DEPARTURE_RANK, next_seq, RES_EVENT_DEPARTURE, next_job
                )
                next_seq += 1

    var horizon = t_prev
    var span = horizon - observed_from
    var n_retained = n_jobs - warmup_jobs

    # Retained means, through the frozen kernels, over an explicitly built list whose length
    # IS the count passed — `compute_mean(v, n)` trusts `n`, so the only safe call is one where
    # the two cannot disagree.
    var kept_wait = List[Float64]()
    var kept_system = List[Float64]()
    for i in range(warmup_jobs, n_jobs):
        kept_wait.append(wait[i])
        kept_system.append(depart[i] - arrival[i])

    var has_wait = False
    var mean_wait: Float64 = 0.0
    var has_system = False
    var mean_system: Float64 = 0.0
    if len(kept_wait) > 0:
        var mw = compute_mean(kept_wait, len(kept_wait))
        if de_finite(mw):
            has_wait = True
            mean_wait = mw
        var ms = compute_mean(kept_system, len(kept_system))
        if de_finite(ms):
            has_system = True
            mean_system = ms

    var has_l = False
    var time_avg: Float64 = 0.0
    var has_util = False
    var util: Float64 = 0.0
    if span > 0.0 and de_finite(span) and de_finite(area):
        var l = area / span
        if de_finite(l):
            has_l = True
            time_avg = l
        var u = busy_area / (Float64(capacity) * span)
        if de_finite(u):
            has_util = True
            util = u

    # Little's law is EXACT over the full window and only there — see the module docstring.
    var has_ll = False
    var ll_ok = False
    var ll_gap: Float64 = 0.0
    if warmup_jobs == 0 and has_l and has_system and span > 0.0:
        var lambda_hat = Float64(n_jobs) / span
        var predicted = little_law_l(lambda_hat, mean_system)
        if de_finite(predicted):
            has_ll = True
            # The quantity judged is the measured L; its tolerance comes from its own
            # magnitude, widened by one ulp per addition that built either side (2n event
            # intervals plus n sojourn terms), and by nothing else.
            ll_ok = de_agrees(time_avg, predicted, 0.0, 3 * n_jobs)
            var d = time_avg - predicted
            if de_finite(d):
                ll_gap = d if d >= 0.0 else -d

    return ResourceRun(
        DE_OK, n_jobs, served, warmup_jobs, n_retained, capacity, events, charge, max_queue,
        horizon, observed_from, span,
        has_wait, mean_wait, has_system, mean_system, has_l, time_avg, has_util, util,
        has_ll, ll_ok, ll_gap,
        wait^, start^, depart^,
    )
