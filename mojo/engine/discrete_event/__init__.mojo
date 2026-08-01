"""
discrete_event — event-calendar simulation, resources, warm-up, replications. Zero Python.

What the tree already had, and what it did not
---------------------------------------------
`simulation.mojo` holds an event calendar (`SimState`, `schedule_event`, `next_event`,
`run_until`, `cancel_event`) and one M/M/1 estimator (`mm1_simulate`). `queueing.mojo` and
`operations_research.mojo` hold the exact closed forms for M/M/1 and M/M/c. `petri_net.mojo`
holds the token-availability predicates that a resource pool is an instance of. `scheduler.mojo`
holds topological/priority ordering and a critical path over a task DAG — a static plan, not a
clock. `heap.mojo` holds a real binary min-heap. Every one of them is frozen, and every number
this package reports is either produced by one of them or by `stats`, `inference.core` and
`determinism`.

What was missing is the part that makes a simulated number usable as evidence:

  * A TOTAL ORDER on events. `simulation.schedule_event` inserts before the first strictly
    later event, so two events at the same timestamp resolve by insertion order — an
    ordering that exists but is not declared, cannot be requested, and has no room for
    priority. `discrete_event.calendar` orders on `(time, priority, sequence)` with
    `sequence` a never-reused monotone counter, so NO TWO EVENTS ARE EVER TIED and the pop
    order is a function of the input alone. That is the whole determinism story:
    `de_event_order()` names the rule, and `calendar_order_audit` lets a caller check a
    sequence against it rather than trust a docstring.

  * SEEDED, SEPARATED randomness. `simulation.mm1_simulate` hardcodes `seed = 42` in a
    private LCG and advances ONE stream alternately for inter-arrivals and service times, so
    changing the arrival rate shifts every service draw and no two configurations can be
    compared on common random numbers. `discrete_event.queue_sim` draws through the frozen
    counter-based `determinism.counter_rng`, on two independent named streams from
    `determinism.streams`, addressed by customer index — so a service time is a pure
    function of `(seed, replication, customer)` and is IDENTICAL across arrival rates.
    `QueueRun.total_service_time` and `total_interarrival_time` are returned so that
    property is measurable, not asserted.

  * WARM-UP (transient) detection. Nothing in the tree detects an initialisation transient.
    A steady-state mean that includes it is biased, and no status anywhere said so.
    `discrete_event.warmup` implements MSER-5 and reports HOW MANY observations it
    discarded, plus `warmup_bias_audit` so the size of the bias it removed is a number.

  * REPLICATIONS with a confidence interval, and the closed form checked against it.
    `discrete_event.replicate` runs independent replications (`replication_id` is a
    coordinate of the generator, not a re-seed), forms a Student-t interval through
    `inference.core.inference_t_quantile`, and reports whether the EXACT analytical Wq, W,
    L and utilisation from `queueing.mojo` fall inside it. If they do not, the simulator is
    wrong — that is the single most valuable assertion in the package and it is asserted in
    `mojo/tests/libs/test_discrete_event_replicate.mojo`.

Where the numbers come from (frozen kernels called, never reimplemented)
-----------------------------------------------------------------------
  determinism.counter_rng   rng_exponential, rng_uniform, rng_version — every draw
  determinism.streams       stream_id — the two named streams
  queueing                  mm1_utilization, mm1_avg_wait_time, mm1_avg_system_time,
                            mm1_avg_system_size, mm1_avg_queue_length, mmc_erlang_c
  operations_research       little_law_l, utilization_factor
  petri_net                 coverability_check — "are there k free servers"
  stats                     compute_mean, compute_variance — replication statistics
  heap                      is_min_heap — the calendar's own invariant, checked in its suite
  inference.core            inference_finite, inference_scaled_tol_ulps,
                            inference_t_quantile

`inference.core`'s finiteness predicate and tolerance builder are IMPORTED rather than
re-spelled here. Rule 3 applies inside a package and across two packages that already share
a dependency: a second definition of "finite" is how two modules end up disagreeing about
whether an answer exists.

Absence
-------
Every driver returns a status and a `has_*` flag beside each quantity. A quantity that could
not be computed carries `0.0` in its value slot and `False` in its flag — never a raw
non-finite, because the dispatch refuses to serialise one and the whole response becomes a
typed error, and never a bare `0.0`, because a mean wait of zero is a real answer for a queue
nobody waited in.

Bounds
------
Reading past a `List` end is an uncatchable process abort, so no caller-supplied count is
trusted: every driver checks its counts against the real lengths and returns
`DE_ERR_COUNT`. Every subscript-shaped parameter (`warmup_jobs`, `n_discard`) is checked in
BOTH directions, because `range(-3, n)` reads `obs[-3]` and that is fatal while a negative
plain count merely reads nothing. The event count is bounded AND the heap work it implies is
charged, because bounding memory is not bounding work.

Status codes
------------
This package owns 400-419 and uses no other range. `discrete_event.contract.de_status_name`
is the ONE vocabulary; no module here carries a second status table.

Modules
-------
  contract   — status codes, ceilings, work budget, named streams, the order contract
  calendar   — the totally-ordered event calendar and its audit
  resource   — a capacity pool with a priority waiting queue; the deterministic DES engine
  queue_sim  — M/M/1 and M/M/c runs over seeded, separated streams
  warmup     — MSER-5 transient detection and the bias it removes
  replicate  — replications, Student-t intervals, and the closed-form coverage check
"""
