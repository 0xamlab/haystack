---
icon: timer
description: Discrete-event simulation with a totally-ordered event calendar, resource pools with priority queues, warm-up detection that reports what it discarded
---

# Discrete-event simulation & queueing

Six kernel families for the question "how long will things wait, and how much of that answer is
noise". They run as compiled kernels inside the runtime that ships with the SDK — nothing to
install separately and nothing to start.

A simulated number is only evidence if three things are true: the same seed gives the same answer,
the estimate is not contaminated by the start-up transient, and the interval around it means what
it says. This package makes each of those a value you can read rather than a promise in a
docstring.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# arrivals 0,1,2,3 — service 2 units each — one server
run = runtime.execute("discrete_event.resource", "resource_serve_flat",
                      [[0.0, 1.0, 2.0, 3.0], [2.0, 2.0, 2.0, 2.0], [0, 0, 0, 0], 4, 1, 0])["result"]

run["wait"]                    # [0.0, 1.0, 2.0, 3.0]   — per job, not just a mean
run["depart"]                  # [2.0, 4.0, 6.0, 8.0]
run["mean_wait"]               # 1.5
run["mean_system"]             # 3.5
run["time_avg_number"]         # 1.75   — the time-average number in system
run["utilization"]             # 1.0
run["max_queue_length"]        # 2
run["little_law_consistent"]   # True
run["little_law_gap"]          # 0.0    — exactly zero, not "small"
```

Everything in that result is hand-checkable: job 1 arrives at 1, finds the server busy until 2, so
it waits 1. Sojourn times are 2, 3, 4, 5 and the horizon is 8, so the time integral of the number
in system is 14 and `L = 14/8 = 1.75`. Little's law says `L = lambda * W = (4/8) * 3.5 = 1.75`, and
over a complete observation window that identity is **exact** rather than approximate — which is
why `little_law_gap` is `0.0` and why the flag beside it is worth reading.

## The modules

| Module | What it does |
| --- | --- |
| `discrete_event.calendar` | The event calendar: a binary min-heap ordered on `(time, priority, sequence)`, a replay that reports the order it produced, and an audit that checks a sequence **this package did not produce** against the same rule |
| `discrete_event.resource` | The deterministic engine — a pool of identical servers with a priority waiting queue, non-preemptive service, per-job waits and departures, the time-average number in system, utilisation, and Little's law checked against its own output |
| `discrete_event.queue_sim` | M/M/1 and M/M/c runs over seeded, independently-streamed exponential draws, returned beside the exact analytical steady state for the same parameters |
| `discrete_event.warmup` | MSER-5 transient detection that reports **how many** observations it discarded, plus a bias audit that measures the size and sign of the bias the truncation removed |
| `discrete_event.replicate` | Independent replications, Student-t confidence intervals, and a coverage verdict on whether the exact `Wq`, `W`, `L` and utilisation fall inside them |
| `discrete_event.contract` | The shared vocabulary: one status code per defect, the declared ceilings, the non-wrapping work budget, the two named random streams, and the ordering rule as a value you can store |

## Tie-breaking is the determinism

Two events at the same timestamp have to resolve somehow. If the answer is "whatever order the
container happened to hold them in", the same seed can give different answers on a different day,
and nothing fails while it happens.

So the order is total and it is named:

```python
runtime.execute("discrete_event.contract", "de_event_order", [])["result"]
# 'time,priority,sequence/v1'
```

Events pop in increasing time; at equal time, in increasing priority rank (0 is most urgent); at
equal time **and** rank, in increasing insertion sequence — a counter that is never reused. The
third key means no two calendar entries can ever compare equal, so the pop order is a function of
the input alone. Store that identifier beside a result and you have recorded the rule that
produced it.

You can check the rule against a sequence without re-running anything:

```python
audit = runtime.execute("discrete_event.calendar", "calendar_order_audit",
                        [[0.0, 0.0, 1.0, 1.0], [0, 3, 0, 1], [0, 1, 2, 3], 4])["result"]

audit["is_ordered"]        # True
audit["first_violation"]   # -1  — there is none
audit["n_time_ties"]       # 2   — normal, and exactly what the later keys resolve
audit["n_duplicate_keys"]  # 0   — this one WOULD be a defect
```

`n_time_ties` is a diagnostic, not a complaint: timestamp collisions are the common case and the
reason the second and third keys exist. `n_duplicate_keys` counts entries equal on all three keys,
which cannot happen inside one calendar and therefore means two calendars were merged or a
sequence number was reused — the one way the order stops being total.

### Coincident departures resolve before arrivals

A departure and an arrival at the same instant are given different calendar ranks, so departures
always fire first. In the example at the top, at `t = 2` job 0 leaves, the job that had been
waiting starts, and only then does the next job arrive to an empty queue. The reported
`max_queue_length` is 2. Had the arrival fired first, the same waits would have come out with a
maximum queue of 2 recorded a step earlier — same answer for the waits, different answer for the
queue statistic. That is why the convention is declared rather than inherited from a data
structure.

## Separate streams, so comparisons stay valid

Every draw comes from a counter-based generator addressed by coordinates rather than advanced by
state, and inter-arrival times and service times are drawn on **two independent named streams**:

```python
a = runtime.execute("discrete_event.queue_sim", "qs_run_flat",
                    [1.0, 2.0, 2000, 1, 20260731, 0, 0])["result"]
b = runtime.execute("discrete_event.queue_sim", "qs_run_flat",
                    [1.5, 2.0, 2000, 1, 20260731, 0, 0])["result"]

a["total_service_time"] == b["total_service_time"]   # True — arrival rate changed, service did not
```

Change the arrival rate and not one service time moves. That is what makes two configurations
comparable on common random numbers, and it is a returned quantity — you can assert it — rather
than a design claim. A generator that interleaved the two streams would fail that equality and
nothing else in the estimate would look wrong.

Re-running with the same seed reproduces every reported number bit for bit, and the generator
identifies itself so a stored estimate names what produced it:

```python
runtime.execute("discrete_event.contract", "de_rng_version", [])["result"]
# 'philox4x64-10/v1'
```

## A steady-state estimate that includes the transient is biased

A queue starts empty. Early customers wait less than steady-state customers, so an average over the
whole run is biased low — and the bias shrinks with run length rather than disappearing, so a
longer run hides it instead of fixing it.

The transient is detected and, crucially, the amount discarded is **reported**:

```python
obs = [100.0]*4 + [20.0]*8
w = runtime.execute("discrete_event.warmup", "warmup_mser_flat", [obs, 12, 1])["result"]

w["n_discarded_obs"]      # 4
w["n_retained_obs"]       # 8
w["steady_mean"]          # 20.0
w["has_estimate"]         # True
w["at_search_boundary"]   # False
```

Ties go to the **smallest** truncation point: discarding 5 or 6 here would score identically and
throw away observations for no gain. An estimator that silently trimmed its own input could not be
re-derived from its inputs, so `n_discarded_obs` travels with the answer.

When the series never settles, the search lands on its boundary and the answer is a refusal rather
than a number: `at_search_boundary` is `True`, no steady mean is returned, and the status says the
transient did not settle within the run. The remedy is a longer run, and the result says so instead
of returning the biased mean anyway.

The size of the bias removed is itself measurable:

```python
b = runtime.execute("discrete_event.warmup", "warmup_bias_audit", [obs, 12, 4])["result"]

b["full_mean"]            # 46.666666666666664   — 560/12, the contaminated average
b["truncated_mean"]       # 20.0
b["bias_removed"]         # 26.666666666666664   — 80/3, and the SIGN says the transient sat high
b["has_relative_bias"]    # True
b["relative_bias"]        # 1.3333333333333333   — 4/3
```

The **sign** of `bias_removed` is part of the answer: positive says the transient sat above the
steady level. If the
truncated mean is zero there is no ratio to report, so `has_relative_bias` is `False` and the
absolute bias is still given — an unavailable quantity is reported unavailable rather than as a
zero that reads like agreement.

## The assertion that matters most: the closed form must land inside the interval

An M/M/1 queue has exact analytical answers. If a simulator disagrees with them, the simulator is
wrong — the algebra is not. So the package runs replications, forms a Student-t interval around
each of four metrics, and reports whether the exact value falls inside:

```python
v = runtime.execute("discrete_event.replicate", "replicate_mm1_flat",
                    [1.0, 2.0, 4000, 1, 10, 20260731, 0.95, 5])["result"]

v["closed_form_wait"]      # 0.5   — exact Wq for lambda=1, mu=2
v["closed_form_system"]     # 1.0   — exact W
v["closed_form_number"]     # 1.0   — exact L
v["closed_form_rho"]        # 0.5   — exact utilisation

v["wait_covered"]           # True
v["system_covered"]         # True
v["number_covered"]         # True
v["util_covered"]           # True
v["n_metrics_covered"]      # 4
v["n_metrics_checked"]      # 4
v["warmup_jobs_used"]       # how many jobs a pilot run's MSER chose to discard
```

There is deliberately **no single "valid" boolean**. At a 95% level one metric in twenty misses by
construction, so a single flag would be either alarmist or meaningless. `n_metrics_covered` out of
`n_metrics_checked`, beside the intervals themselves, is the honest summary.

The check can fail, which is what makes it worth running. At 95% utilisation with only 400
customers the transient dominates: the truncation discards a large fraction of the run, the
intervals still sit below the exact values, and the coverage count comes back 1 of 4. That is the
result correctly telling you the run was too short — not the package flattering itself.

An unstable queue is refused outright. When arrivals reach total service capacity there is no
steady state to cover, and a limit that does not converge is reported as absent rather than as a
large finite number:

```python
cf = runtime.execute("discrete_event.queue_sim", "qs_closed_form_flat", [2.0, 2.0, 1])["result"]
cf["exists"]           # False
cf["wait_in_queue"]    # 0.0  <- a placeholder, and `exists` is the answer
```

M/M/c works the same way through the same call. For three arrivals per unit against two servers at
rate 2, the Erlang C probability of waiting is `9/14`, and `Wq = 9/14`, `W = 8/7`, `L = 24/7`
follow exactly.

## Intervals on anything you replicated

The interval builder is not limited to queues — hand it any set of independent per-replication
estimates:

```python
ci = runtime.execute("discrete_event.replicate", "replicate_ci_flat",
                     [[1.0, 2.0, 3.0, 4.0, 5.0], 5, 0.95])["result"]

ci["mean"]         # 3.0
ci["variance"]     # 2.5
ci["t_critical"]   # 2.7764451051977987   — Student-t on 4 df, not the normal 1.959964
ci["ci_lower"]     # 1.0367568382702546
ci["ci_upper"]     # 4.9632431617297454
ci["half_width"]   # 1.9632431617297454
```

The pivot is Student-t, not normal: with five replications the normal quantile would give an
interval about 30% too narrow, and the error is invisible because the interval still looks like an
interval. `half_width` is reported directly because it is what you use to decide how many more
replications to run.

One replication is a case that fails **partly**, and the result says so: the mean exists and is
returned, the interval does not exist, and the two are reported through separate flags. Collapsing
them would either hide a usable mean or invent an interval of width zero.

## Absence, refusals and bounds

Every driver returns a status and a `has_*` flag beside each quantity that can fail to exist. A
quantity that could not be computed carries `0.0` in its value slot with the flag `False` — never a
NaN, because a non-finite number cannot be serialised and one absent quantity would turn a dozen
present ones into an error, and never a bare `0.0`, because a mean wait of zero is a genuine answer
for a queue nobody waited in. The flag is the answer.

Refusals name the specific defect rather than a generic failure, so you know which argument to fix:

```python
runtime.execute("discrete_event.contract", "de_status_name", [403])["result"]
# 'count_exceeds_list_length'
runtime.execute("discrete_event.contract", "de_status_name", [409])["result"]
# 'no_steady_state_utilisation_at_or_above_one'
runtime.execute("discrete_event.contract", "de_status_name", [411])["result"]
# 'transient_never_settled_within_the_run'
```

Element counts are never trusted against the arrays you passed: an element count larger than the
list it indexes is refused before the first read, because reading past the end of an array is not a
wrong answer, it is a process ending. Warm-up counts are checked in **both** directions, because
they select a position in the run and a negative position is fatal in a way a negative count is
not.

Work is bounded as well as memory, and the two are different limits. A request can sit inside every
size ceiling and still imply minutes of computation. Each driver therefore charges the operations
its loops actually perform — event count times heap depth, replications times customers times depth
— and refuses before starting rather than partway through. The charge is a returned value, so cost
is something you can read before committing to a run:

```python
runtime.execute("discrete_event.resource", "resource_work_charge", [4])["result"]    # 88
runtime.execute("discrete_event.contract", "de_ceilings", [])["result"]
# events, jobs, servers, replications, observations, batch size, priority, work budget
```

## Choosing between the surfaces

* Known arrival times and durations — a trace, a schedule, a measured workload — go to
  `discrete_event.resource`. It is fully deterministic, so a result is reproducible from its inputs
  alone with no seed involved.
* Rates rather than traces go to `discrete_event.queue_sim`, which supplies seeded draws to the
  same engine and returns the exact steady state beside the simulated estimate.
* A number you intend to report, rather than look at, goes through `discrete_event.replicate`:
  replications, an interval, and a coverage verdict against the closed form.
* Priorities, multiple servers and per-job detail are available from every surface; the difference
  is only where the arrival and service numbers come from.

## See also

* [Strategy Simulation](strategy-simulation.md) — comparing policies over the same simulated scenarios
* [Optimization](optimization.md) — solving for a schedule rather than simulating one
* [Runtime Library Catalog](runtime-library-catalog.md) — every module and function
