---
icon: route
description: Vehicle routes, schedules, convex quadratic programs, Pareto fronts and decisions under uncertainty — searched on your own machine, reporting the bound you have rather than claiming an optimum.
---

# Routing, scheduling, trade-offs and uncertainty

Five kernel families for the problems where proving the best answer is not on the table:
travelling-salesman and vehicle routing, job-shop and project scheduling, convex quadratic
programs, Pareto fronts, and programs whose data is uncertain. All run as compiled kernels
inside the runtime that ships with the SDK — there is nothing to start and nothing to install
separately.

```python
from algenta import MojoRuntime
import math

runtime = MojoRuntime(mode="local")

# seven stops as coordinates; the kernels take the distance matrix, flat and row-major
pts = [(0.0, 0.0), (4.0, 1.0), (8.0, 0.0), (8.0, 6.0), (4.0, 5.0), (0.0, 6.0), (3.0, 3.0)]
d = [math.dist(p, q) for p in pts for q in pts]

nn = runtime.execute("optimization.routing", "tsp_greedy_flat", [d, 7])["result"]
nn["tour_length"]        # 34.718... — nearest neighbour from stop 0
nn["local_optimum"]      # False — nothing has been searched yet

r = runtime.execute("optimization.routing", "tsp_local_search",
                    [d, 7, 64, True, True, 3])["result"]
r["tour"]                # [0, 1, 2, 3, 4, 6, 5, 0] — closed, and verified a permutation
r["tour_length"]         # 30.848...
r["improvement"]         # 3.870... — what the search bought over its own starting tour
r["local_optimum"]       # True — no improving move of the declared kinds is left
r["moves_evaluated"]     # 154
```

**None of that says "optimal", and neither does the status.** Ask it what the code means and
it tells you in as many words:

```python
runtime.execute("optimization.routing", "route_status_name", [r["status"]])["result"]
# "verified_local_optimum_of_the_declared_moves_not_proven_optimal"
```

`30.848...` is the best tour those two families of moves can reach from that starting tour. It
is a real tour of real length — verified to visit every stop exactly once — and it is not
certified to be the shortest one. Every driver on this page is a search of that kind, so every
one of them reports what it has instead of what it would be nicer to claim.

## The modules

| Module | What it does |
| --- | --- |
| `optimization.routing` | travelling-salesman tours by 2-opt, Or-opt and iterated local search; vehicle routing with hard capacity and hard time windows; a distance-matrix census; and audits of a tour or a routing you were handed |
| `optimization.scheduling` | job-shop scheduling by tabu search over critical machine swaps, resource-constrained project scheduling by multi-start schedule generation, makespan lower bounds with the critical path, resource peak profiles, and verification of a schedule from anywhere |
| `optimization.quadratic` | convex quadratic programs by an active-set method — a KKT certificate, a measured optimality gap from the linearisation, a convexity report, and refusal of an objective that is not convex |
| `optimization.multiobjective` | Pareto front decomposition, front certification, crowding distance and NSGA-II selection, hypervolume against an explicit reference, a genetic search over a linear model, and exact lexicographic optimisation |
| `optimization.robust` | scenario generation, per-scenario optima with worst case and CVaR, the decision that is feasible in every scenario, and measured chance-constraint satisfaction rates |

Matrices cross as flat row-major lists plus their dimensions, and constraint senses are `0`
for `<=`, `1` for `==`, `2` for `>=` — the same conventions as
[the exact solvers](optimization.md), which these drivers call for every inner linear program.

## A heuristic reports its bound, not a verdict

A local search cannot prove that nothing better exists. What it *can* do is measure the
distance to a bound that holds for **every** schedule, tour or point — and that number is worth
more than a status word, because it tells you whether to keep searching.

For a job shop there are two such bounds and both are cheap: the operations of one job run in
sequence, so the longest job is a bound; a machine runs one operation at a time, so its total
load is a bound.

```python
# three jobs, three operations each, three machines
# operation k of job j is index j * 3 + k, and a job's operations run in ascending k
duration   = [3.0, 2.0, 2.0,  2.0, 1.0, 4.0,  4.0, 3.0, 1.0]
machine_of = [0, 1, 2,        0, 2, 1,        1, 2, 0]

bnd = runtime.execute("optimization.scheduling", "jobshop_bound_flat",
                      [duration, machine_of, 3, 3, 3])["result"]
bnd["lower_bound"]         # 10.0
bnd["job_bound"]           # 8.0  — the longest single job
bnd["machine_bound"]       # 10.0 — the busiest machine's load
bnd["critical_machine"]    # 1
```

The search then reports the incumbent, that bound, and the gap between them:

```python
r = runtime.execute("optimization.scheduling", "jobshop_tabu_solve_flat",
                    [duration, machine_of, 3, 3, 3, 7, 200, 8, 40])["result"]

r["makespan"]              # 11.0 — a schedule that exists
r["verified"]              # True — re-checked against your own arrays, not trusted
r["lower_bound"]           # 10.0
r["gap"]                   # 1.0  — what is still unaccounted for
r["relative_gap"]          # 0.1
r["optimal_by_bound"]      # False — the incumbent does not meet the bound
r["initial_makespan"]      # 12.0 — what the construction alone gave
r["iteration_limit_hit"]   # True — the budget stopped the search, not convergence
r["critical_ops"]          # [3, 0, 1, 5] — the chain that produced the makespan
r["start"]                 # one start time per operation
```

There is **no `proven_optimal` field on a tour, a routing, a schedule or a heuristic front**,
and that absence is the design — where a proof genuinely is available, as it is for the convex
quadratic programs below, the field exists and has to be earned. `optimal_by_bound` is a
statement about the bound — the incumbent met it — not about the search, which proves nothing
either way. A solver that prints "optimal" when its own search
stopped has told you about its budget and labelled it a property of your problem; here the two
facts stay separate, and `iteration_limit_hit` is the one that answers "would more time help".

**Why a gap beats a verdict:** `11.0` against a bound of `10.0` says the answer is within one
time unit of anything achievable, which is usually where you stop. A verdict of "optimal" from
a truncated search says nothing you can act on, and a wrong one is undetectable from the
outside.

### The critical path, and when it is the wrong explanation

For a project with renewable resources the same shape holds, with one addition that matters
more than the numbers: a project can be late because of a *resource*, not a dependency, and a
precedence-only critical path reports that as a dependency.

```python
# six activities, one resource of capacity 4
duration  = [3.0, 4.0, 2.0, 2.0, 3.0, 1.0]
demand    = [2.0, 3.0, 2.0, 2.0, 1.0, 4.0]   # n_activities x n_resources, row-major
capacity  = [4.0]
pred_from = [0, 0, 1, 2]                     # pred_from[e] must finish before pred_to[e]
pred_to   = [1, 2, 4, 4]

bnd = runtime.execute("optimization.scheduling", "rcpsp_bound_flat",
                      [duration, demand, capacity, pred_from, pred_to, 6, 1])["result"]
bnd["cp_bound"]            # 10.0 — the longest path through the precedences alone
bnd["resource_bound"]      # 8.25 — total work / capacity, valid because time offers no more
bnd["lower_bound"]         # 10.0 — the larger of the two
bnd["critical_ops"]        # [0, 1, 4] — the path itself, in order

r = runtime.execute("optimization.scheduling", "rcpsp_sgs_solve_flat",
                    [duration, demand, capacity, pred_from, pred_to, 6, 1, 20260731, 32])["result"]
r["makespan"]              # 13.0
r["lower_bound"]           # 10.0
r["gap"]                   # 3.0
r["order"]                 # [0, 1, 2, 4, 3, 5] — the activity list that produced it
r["resource_delayed_at"]   # 5 — activity 5 waited for the resource, not for a predecessor
r["critical_ops"]          # [5] — so the chain stops there rather than inventing a path
r["verified"]              # True
```

`resource_delayed_at` is the honest half of the explanation. Activity 5 starts at `12.0` with
every predecessor long finished; presenting a precedence path as the reason would answer "what
do I change" wrongly. `rcpsp_peak_usage_flat` gives the other half — where each resource
peaks, and when:

```python
p = runtime.execute("optimization.scheduling", "rcpsp_peak_usage_flat",
                    [duration, demand, capacity, 6, 1, r["start"]])["result"]
p["peak"]              # [4.0] — one entry per resource
p["peak_time"]         # [0.0] — the earliest instant attaining it
p["over_capacity"]     # [0]
p["n_over"]            # 0
```

## An answer that does not exist is reported absent

Same rule as [the exact solvers](optimization.md), and it bites harder here, because a search
always has *something* plausible lying around in a partly-built structure. None of it is
returned.

A tour that is not a tour has no length — not a partial sum:

```python
r = runtime.execute("optimization.routing", "tour_length_flat",
                    [[0.0, 2.0, 3.0, 2.0, 0.0, 4.0, 3.0, 4.0, 0.0], 3, [0, 1, 1, 0]])["result"]
r["has_value"]     # False
r["value"]         # 0.0 — padding, never a claim
runtime.execute("optimization.routing", "route_status_name", [r["status"]])["result"]
# "tour_does_not_visit_each_city_exactly_once"
```

A project whose dependencies form a cycle has no schedule, and therefore no bound either:

```python
r = runtime.execute("optimization.scheduling", "rcpsp_sgs_solve_flat",
                    [[2.0, 3.0], [1.0, 1.0], [4.0], [0, 1], [1, 0], 2, 1, 1, 8])["result"]
r["feasible"]        # False
r["has_makespan"]    # False
r["start"]           # [] — no start times, and no makespan a cyclic project cannot have
r["cycle_act"]       # 0
runtime.execute("optimization.scheduling", "sched_status_name", [r["status"]])["result"]
# "precedence_cycle_no_schedule_exists"
```

A dynamic program over a cyclic dependency graph terminates and returns a finite makespan for
a schedule that cannot exist. That is the specific wrong number this status replaces.

An activity demanding more than a resource has is infeasible at every instant, and both
culprits are named because "infeasible" alone is not actionable:

```python
r = runtime.execute("optimization.scheduling", "rcpsp_sgs_solve_flat",
                    [[2.0, 3.0], [1.0, 7.0], [4.0], [], [], 2, 1, 1, 8])["result"]
r["infeasible_act"]         # 1
r["infeasible_resource"]    # 0
runtime.execute("optimization.scheduling", "sched_status_name", [r["status"]])["result"]
# "demand_exceeds_capacity_no_schedule_exists"
```

The same applies to a vehicle count (`vrp_vehicle_bound` on a load bigger than one vehicle
returns `has_bound` `False` and the offending index, because the fleet size of an impossible
instance does not exist), and to a hypervolume reference point (`mo_reference_point` returns an
**empty list** rather than a zero vector, which would be a perfectly plausible reference
somebody would then use).

## Same seed, same answer

These searches are randomised: tie-breaks, restarts, kicks, crossover, mutation and scenario
draws all consume random numbers. Every one of those draws is addressed by an explicit seed
plus its own coordinates, so **the answer is a pure function of the arguments** — including on
a different machine, and whatever else was computed first.

```python
args = [d, 7, 64, 3, 40, 20260731]      # matrix, n, max_passes, max_segment, kicks, seed

first  = runtime.execute("optimization.routing", "tsp_iterated_local_search", args)["result"]
second = runtime.execute("optimization.routing", "tsp_iterated_local_search", args)["result"]

first["tour"] == second["tour"]                  # True
first["tour_length"] == second["tour_length"]     # True — bit-identical, not "close"
first["seed"]                                     # 20260731 — echoed back with the answer
first["kicks"]                                    # 40 perturbations attempted
```

This is not a nicety. **A heuristic whose output changes between runs cannot be used in a
decision that has to be explained**: the schedule you defend in a meeting has to be the
schedule the same call produces tomorrow, and a difference between two runs has to mean
somebody changed the data. So there is no hidden clock and no address-dependent hashing —
nothing about a run depends on when or where it happened.

Where a convenience entry point does supply a seed for you, it is a fixed constant compiled
into the kernel rather than anything drawn at run time, and the sample count comes back with
the result — so the call is still reproducible and still says what it did. A seed taken from
the clock would not be, which is the thing to avoid.

A different seed is a different *walk*, and the result says so without pretending the answer
changed:

```python
Q, c = [2.0, 0.0, 0.0, 2.0], [-2.0, -4.0]
A, senses, b = [1.0, 1.0], [0], [2.0]
lower, upper, flags = [0.0, 0.0], [0.0, 0.0], [1, 1]     # 1 = has a lower bound
qp = [Q, 2, c, A, 1, senses, b, lower, upper, flags]

one   = runtime.execute("optimization.quadratic", "qp_solve_default", [*qp, 20260731])["result"]
again = runtime.execute("optimization.quadratic", "qp_solve_default", [*qp, 20260731])["result"]
other = runtime.execute("optimization.quadratic", "qp_solve_default", [*qp, 99])["result"]

one["path_signature"] == again["path_signature"]     # True — the same search, step for step
one["path_signature"] == other["path_signature"]     # False — a different scan order
one["objective"] == other["objective"]               # True — and the same optimum, -4.5
```

The *path* may depend on the seed; the *answer* may not. Where a search genuinely cannot prove
its answer — a tour, a schedule, a front — a different seed can land on a different local
optimum, which is exactly why the seed travels with the result instead of living in a log.

Scenario draws carry their whole provenance for the same reason:

```python
s = runtime.execute("optimization.robust", "scenario_rhs_normal",
                    [[4.0, 12.0, 18.0], [0.2, 0.5, 1.0], 64, 20260731, "docs.capacity"])["result"]
s["rhs"][:3]        # [3.781..., 12.735..., 16.807...] — scenario 0, one value per row
s["n_scenarios"]    # 64
s["rng"]            # "philox4x64-10/v1" — the generator, named in the result
s["stream"]         # 58721 — the stream that name resolves to
```

Seed, stream, generator and distribution come back with the block, so a stored answer can be
re-derived from the record rather than merely believed.

## A structure that is not valid is not returned

Every driver here re-checks its own answer against the caller's own arrays before returning
it, and discards it if the check fails. A search that builds a structure incrementally is
exactly where a subtle bookkeeping bug produces a plausible-looking result, so the answer is
audited by the same routine that audits a stranger's.

* a **tour** must visit every stop exactly once — verified after every accepted move, not once
  at the end;
* a **routing** must respect every capacity and every time window, and serve every customer
  exactly once;
* a **schedule** must satisfy every precedence and keep every resource inside its limit at
  every instant where the profile can peak;
* a **Pareto front** must contain no dominated point, and must not have left a
  Pareto-optimal one out;
* a **chance constraint** met in 52% of scenarios is not met at 95%, and the measured rate is
  reported next to the level it was judged against.

### Vehicle routing: capacity and windows are hard

```python
# depot 0 at the origin, five customers; one vehicle carries 8
stops_xy = [(0.0, 0.0), (4.0, 3.0), (4.0, -3.0), (-4.0, 3.0), (-4.0, -3.0), (0.0, 5.0)]
dm = [math.dist(p, q) for p in stops_xy for q in stops_xy]
demand = [0.0, 4.0, 4.0, 3.0, 3.0, 2.0]      # the depot's own entry is 0

sol = runtime.execute("optimization.routing", "vrp_capacity_solve",
                      [dm, 6, demand, 8.0, 3, 32, 4, 20260731])["result"]
sol["feasible"]                # True — re-audited against your demand and your capacity
sol["n_routes_used"]           # 2 — of the 3 vehicles offered; the third stays home
sol["route_start"]             # [0, 2, 5] — offsets into stops, strictly increasing
sol["stops"]                   # [2, 1, 4, 3, 5] — customers only, the depot is not listed
sol["route_load"]              # [8.0, 8.0]
sol["total_distance"]          # 36.472...
sol["lower_bound_vehicles"]    # 2 — no routing of this demand fits in fewer
```

Vehicle `v`'s sequence is `stops[route_start[v] : route_start[v + 1]]`. Empty routes are
**removed**, not retained as zero-length slots, so the offsets partition `stops` exactly and a
vehicle that never leaves the depot has no load, no distance and no entry.

`vrp_check` runs that same audit on a routing from anywhere — and a structural break is a
rejection while a *semantic* break is a report, with the counts and the location:

```python
bad_stops = [1, 5, 1, 2, 3]        # customer 1 served twice, customer 4 dropped
audit = runtime.execute("optimization.routing", "vrp_check",
                        [dm, 6, demand, 8.0, [], [], [], bad_stops, [0, 3, 5]])["result"]
audit["feasible"]                 # False
audit["n_served"]                 # 4
audit["n_duplicated"]             # 1
audit["n_missing"]                # 1
audit["route_load"]               # [10.0, 7.0]
audit["max_capacity_excess"]      # 2.0
audit["defect_vehicle"]           # 0
audit["defect_stop"]              # 2 — the position in that vehicle's sequence
audit["defect_node"]              # 1
audit["total_distance"]           # 38.944... — a fact about those routes, not a solution
```

A routing that serves a customer twice is not a routing however cheap it is, so
`total_distance` is reported and `feasible` is what says whether the routes are an answer.

With time windows, `distance` doubles as the travel-time matrix — one matrix, stated, rather
than two that can silently disagree. A vehicle may wait at a stop it reaches early, must begin
service by `due`, and must be back at the depot by `due[0]`. When the data alone makes that
impossible, it is proven rather than searched for:

```python
ready   = [0.0] * 6
due     = [100.0, 30.0, 30.0, 1.0, 30.0, 30.0]     # customer 3 cannot be reached by time 1
service = [0.0, 2.0, 2.0, 2.0, 2.0, 2.0]

sol = runtime.execute("optimization.routing", "vrp_time_window_solve",
                      [dm, 6, demand, 8.0, 3, ready, due, service, 32, 4, 20260731])["result"]
sol["proven_infeasible"]    # True — going straight there is already too late
sol["feasible"]             # False
sol["stops"]                # []
sol["defect_node"]          # 3 — the stop the proof is about
runtime.execute("optimization.routing", "route_status_name", [sol["status"]])["result"]
# "proven_infeasible_from_the_instance_alone"
```

### Fronts: no dominated point, and nothing left out

```python
# five candidates, two objectives, both minimised; row-major
f = [1.0, 5.0,
     2.0, 3.0,
     3.0, 2.0,
     5.0, 1.0,
     4.0, 4.0]      # candidate 4 is beaten by candidates 1 and 2

fs = runtime.execute("optimization.multiobjective", "nondominated_sort", [f, 5, 2])["result"]
fs["rank"]           # [0, 0, 0, 0, 1] — 0 is the Pareto set
fs["n_fronts"]       # 2
fs["front_start"]    # [0, 4, 5] — front r is order[front_start[r] : front_start[r+1]]
fs["first_front"]    # [0, 1, 2, 3]
fs["verified"]       # True — no front contains a dominated member, and the ranks are tight
```

`pareto_certify` checks a front **somebody else produced**, condition by condition, so you can
audit a recommendation rather than adopt it:

```python
partial = runtime.execute("optimization.multiobjective", "pareto_certify",
                          [f, 5, 2, [0, 1, 2]])["result"]
partial["certified"]               # False
partial["mutually_nondominated"]   # True  — it is an antichain
partial["unbeaten"]                # True  — nothing outside it beats a member
partial["maximal"]                 # False — and yet candidate 3 was left out
partial["witness_dominated"]       # 3
partial["n_true_front"]            # 4 — sized independently of the claim

sneaky = runtime.execute("optimization.multiobjective", "pareto_certify",
                         [f, 5, 2, [0, 4]])["result"]
sneaky["unbeaten"]                 # False
sneaky["witness_dominator"]        # 1 — candidate 1 beats the claimed candidate 4
```

Any subset of the true front is an antichain that nothing outside beats, so a claim of one
point out of forty passes the first two conditions. **`maximal` is the condition that makes the
certificate about the whole Pareto set instead of a fragment of it** — and it is the one a
certificate omits when no test exercises the shape that needs it.

### Chance constraints: the rate, next to the level

```python
# maximise 3x + 5y  s.t.  x <= 4,  2y <= 12,  3x + 2y <= 18 — with uncertain right-hand sides
A = [1.0, 0.0,  0.0, 2.0,  3.0, 2.0]
senses = [0, 0, 0]
scen = s["rhs"]        # the 64 scenarios drawn under seed 20260731 above

ch = runtime.execute("optimization.robust", "robust_chance_rates",
                     [[2.0, 6.0], A, 3, 2, senses, scen, 64, 0.95, 1e-9])["result"]
ch["rates"]        # [1.0, 0.515625, 0.53125] — measured, per row
ch["counts"]       # [64, 33, 34]
ch["met"]          # [True, False, False]
ch["joint_rate"]   # 0.28125 — scenarios in which the whole plan is feasible
ch["worst_row"]    # 1
ch["rate_stderr"]  # [0.0, 0.062..., 0.062...] — sampling error of each estimate
runtime.execute("optimization.robust", "robust_status_name", [ch["status"]])["result"]
# "chance_level_not_met"
```

`[2.0, 6.0]` is the optimum of the *deterministic* program, and it sits exactly on two of its
rows — so it survives about half the scenarios, and the plan is feasible in 28% of them. A
boolean would have hidden all of that; the joint rate is usually the number that matters, and
it is not determined by the per-row rates.

## Convexity is checked, not assumed

For an indefinite objective, "optimal" has no meaning: the same point is a minimum along one
direction and a maximum along another. So a non-convex quadratic program is **refused**, with
the pivot that refuted it named in your own index space:

```python
cv = runtime.execute("optimization.quadratic", "qp_convexity_flat",
                     [[1.0, 0.0, 0.0, -2.0], 2])["result"]
cv["convex"]              # False
cv["positive_definite"]   # False
cv["rank"]                # 1
cv["fail_index"]          # 1
cv["fail_value"]          # -2.0 — the curvature that failed, not just a flag

r = runtime.execute("optimization.quadratic", "qp_solve_default",
                    [[1.0, 0.0, 0.0, -2.0], 2, [0.0, 0.0], [1.0, 1.0], 1, [0], [2.0],
                     [0.0, 0.0], [0.0, 0.0], [1, 1], 1])["result"]
r["x"]                # [] — no point, rather than a stationary one that minimises nothing
r["has_objective"]    # False
runtime.execute("optimization.quadratic", "qp_status_name", [r["status"]])["result"]
# "objective_matrix_not_positive_semidefinite"
```

**And the check survives an objective whose units differ by orders of magnitude**, which is the
ordinary case for a portfolio or an engineering trade-off, not an exotic one:

```python
mixed = runtime.execute("optimization.quadratic", "qp_convexity_flat",
                        [[1e12, 0.0, 0.0, -0.68], 2])["result"]
mixed["convex"]        # False — the -0.68 direction is still curved the wrong way
mixed["fail_index"]    # 1
mixed["fail_value"]    # -0.68

fine = runtime.execute("optimization.quadratic", "qp_convexity_flat",
                       [[1e12, 0.0, 0.0, 0.5], 2])["result"]
fine["convex"]              # True
fine["positive_definite"]   # True
fine["rank"]                # 2
fine["min_pivot"]           # 0.5 — judged at its own magnitude, not the matrix's largest
```

A tolerance scaled by the largest entry of the whole matrix accepts a curvature of `-0.68`
beside a `1e12` as convex, and then everything downstream inherits a false premise: a KKT
certificate and an independent bound will both agree the answer is optimal, because both were
handed the same wrong verdict. Each direction's curvature is therefore judged against **its
own** magnitude.

## A certified minimiser, and a measured gap when there is none

```python
# minimise x² + y² - 2x - 4y  subject to  x + y <= 2,  x, y >= 0
Q, c = [2.0, 0.0, 0.0, 2.0], [-2.0, -4.0]
A, senses, b = [1.0, 1.0], [0], [2.0]
lower, upper, flags = [0.0, 0.0], [0.0, 0.0], [1, 1]

r = runtime.execute("optimization.quadratic", "qp_solve_default",
                    [Q, 2, c, A, 1, senses, b, lower, upper, flags, 20260731])["result"]
r["objective"]          # -4.5
r["x"]                  # [0.5, 1.5]
r["duals"]              # [-1.0] — the row's price
r["binding"]            # [True]
r["certified"]          # True — all four KKT conditions, each with its own residual
r["proven_optimal"]     # True — the certificate AND a measured gap of zero
r["best_bound"]         # -4.5
r["gap"]                # 0.0
r["iterations"]         # 5
```

`upper` is padding here: a bound value whose flag is not set is never read, so a variable with
no upper limit is a **flag rather than an infinity** — an infinity that enters arithmetic
produces `inf - inf`, which is not a number.

`certified` and `proven_optimal` are separate fields because they are separate claims, proved
by different computations that have to agree. The bound comes from minimising the objective's
linearisation over the same feasible set, which for a convex objective is a genuine lower
bound — so it is available for **any** feasible point, including one you produced elsewhere:

```python
gap = runtime.execute("optimization.quadratic", "qp_gap_flat",
                      [Q, 2, c, A, 1, senses, b, lower, upper, flags,
                       [0.0, 0.0], 1000, 1e-9, 1e-9])["result"]
gap["feasible"]      # True — the origin satisfies every row
gap["objective"]     # 0.0
gap["best_bound"]    # -8.0 — a theorem about this feasible set, not an estimate
gap["gap"]           # 8.0 — so the origin is at most 8 away from the optimum
gap["at_optimum"]    # False
```

`at_optimum` is decided inside the call rather than left to the caller, because the gap is a
difference of three numbers and only that call holds all three. A tolerance sized by the
objective's magnitude instead of the gap's own terms is how a measured gap of four hundred
million passes for zero on a program whose optimum is near `1e17` — so the verdict is computed
where all three magnitudes are in scope.

`qp_kkt_check` audits a point and its duals from the outside, and the four conditions are
reported separately so a rejection says which one failed:

```python
wrong = runtime.execute("optimization.quadratic", "qp_kkt_check",
                        [Q, 2, c, A, 1, senses, b, lower, upper, flags,
                         [0.5, 1.5], [1.0], [0.0, 0.0], [0.0, 0.0], 1e-9, 1e-9])["result"]
wrong["certified"]              # False — the right point, the wrong sign on its dual
wrong["primal_ok"]              # True
wrong["dual_ok"]                # False
wrong["stationarity_ok"]        # False
wrong["dual_violation"]         # 1.0
wrong["worst_row"]              # 0
wrong["n_violations"]           # 2
```

What the certificate covers, in full: stationarity per component; primal feasibility per row
and per bound, each against **that row's own** scale; dual sign feasibility, including a zero
multiplier on a bound you never declared; and complementary slackness in **both** directions —
a slack row has a zero dual, *and* a priced row is tight. Convexity is part of the conjunction,
because a KKT point of a non-convex objective is not a minimum. Non-finite inputs are rejected
before any tolerance is computed from them: a tolerance derived from a `nan` is a `nan`, every
comparison against it is false, and the audit would pass having counted zero violations.

## Trade-offs: fronts, volumes and priorities

Hypervolume is exact for one and two objectives, and the reference point is echoed back because
the number is meaningless without it:

```python
hv = runtime.execute("optimization.multiobjective", "hypervolume_default",
                     [f, 5, 2, [6.0, 6.0]])["result"]
hv["exact"]              # True
hv["value"]              # 17.0
hv["bound_lower"]        # 12.0 — the largest single box, proven
hv["bound_upper"]        # 25.0 — the spanning box, proven
hv["n_nondominated"]     # 4 — dominated points cannot add volume
hv["reference"]          # [6.0, 6.0]
```

For three or more objectives the sweep is not exact, and the driver says so rather than
returning an estimate in the field a caller reads as a value:

```python
f3 = [1.0, 4.0, 3.0,
      3.0, 1.0, 4.0,
      4.0, 3.0, 1.0]

hv3 = runtime.execute("optimization.multiobjective", "hypervolume",
                      [f3, 3, 3, [5.0, 5.0, 5.0], 4096, 20260731])["result"]
hv3["exact"]           # False
hv3["has_value"]       # False — `value` carries no claim here
hv3["estimate"]        # 18.578125 — deterministic, from the seed
hv3["std_error"]       # 0.453... — sampling error, floored at one draw's own weight
hv3["bound_lower"]     # 8.0  — still exact
hv3["bound_upper"]     # 24.0 — still exact, and the estimate is checked against both
hv3["samples"]         # 4096
runtime.execute("optimization.multiobjective", "mo_status_name", [hv3["status"]])["result"]
# "hypervolume_not_exact_above_two_objectives"
```

The same seed reproduces `18.578125` exactly; a different seed gives a different estimate
inside the same proven bounds. `std_error` is never `0.0` from a degenerate sample — zero hits
out of 4096 draws is no measurement, not a measurement of zero.

A genetic search over a linear model gets the same treatment, plus one bound that **is**
proven: the exact per-objective optimum, from one linear program per objective.

```python
# minimise (-x, -y) over x + y <= 10, 0 <= x, y <= 8 — a straight trade-off
r = runtime.execute("optimization.multiobjective", "nsga2_linear_default",
                    [[-1.0, 0.0, 0.0, -1.0], 2, 2, [1.0, 1.0], 1, [0], [10.0],
                     [0.0, 0.0], [8.0, 8.0], 12, 20260731])["result"]
r["n_front"]            # 12 distinct non-dominated decisions
r["verified"]           # True — every returned point satisfies your rows and its box
r["max_violation"]      # 0.0
r["ideal"]              # [-8.0, -8.0] — proven by one linear program per objective
r["ideal_gap"]          # [0.0, 0.0] — the front reaches both per-objective optima
r["generations_run"]    # 50
runtime.execute("optimization.multiobjective", "mo_status_name", [r["status"]])["result"]
# "heuristic_front_not_proven_optimal"
```

That status is deliberately **not** the success code the exact solvers use, and there is no
`proven_optimal` field to set. `ideal_gap` is the evidence that exists; the front's own spread
is not evidence about anything.

Where priorities are strict rather than traded off, `lexicographic_linear` is **exact** — every
stage is a simplex solve, so its success status is the ordinary one:

```python
# minimise x + y first; then, among the ties, minimise y
lx = runtime.execute("optimization.multiobjective", "lexicographic_linear_default",
                     [[1.0, 1.0, 0.0, 1.0], 2, 2,
                      [1.0, 1.0, 1.0, 0.0], 2, [2, 0], [10.0, 8.0], 0.0])["result"]
lx["x"]                   # [8.0, 2.0]
lx["optima"]              # [10.0, 2.0] — stage by stage
lx["locked"]              # [True, False] — which objectives were frozen for later stages
lx["slack"]               # the room each lock was given, in that objective's own magnitude
lx["objective_values"]    # [10.0, 2.0] — every objective at the answer, optimised or not
lx["verified"]            # True — re-checked against your rows AND every lock
lx["max_deviation"]       # 0.0 — the raw number, unbudgeted
```

## Uncertainty: what a scenario answer does and does not prove

Two different questions live here, and conflating them is the classic error.

**Wait-and-see** solves each scenario on its own. The worst of those optima is a bound on the
robust value, not the robust value itself — nobody gets to pick their decision after seeing
which scenario happened:

```python
c = [3.0, 5.0]
A, senses, rhs = [1.0, 0.0,  0.0, 2.0,  3.0, 2.0], [0, 0, 0], [4.0, 12.0, 18.0]

w = runtime.execute("optimization.robust", "robust_scenario_solve_default",
                    [c, A, 3, 2, senses, rhs, True, 64, scen, 0.95])["result"]
w["n_solved"]              # 64 — every scenario reached an optimum
w["worst_case"]            # 32.300... — the worst per-scenario optimum
w["worst_scenario"]        # 28
w["best_case"]             # 38.012...
w["mean_objective"]        # 35.999...
w["cvar"]                  # 33.151... — expected shortfall at the requested level
w["cvar_level"]            # 0.95
w["cvar_tail_fraction"]    # ≈0.05 — the fraction of scenarios actually averaged
w["bound_direction"]       # +1 — this value is an UPPER bound on the robust optimum
runtime.execute("optimization.robust", "robust_status_name", [w["status"]])["result"]
# "found_but_only_a_bound_on_the_robust_value"
```

The status is the whole point: the number is real, and it is a bound. `bound_direction` is a
field rather than a sentence in the documentation because it flips with the objective sense,
and "my worst case is at least 3" and "at most 3" lead to opposite decisions.
`cvar_tail_fraction` travels with `cvar_level` for the same reason — a caller who meant "the 5%
tail" and passed `0.05` sees a tail fraction of `0.95` and finds out immediately.

If even one scenario fails to solve, there is no risk summary at all, because a worst case over
a subset is a statement about a different scenario set than the one you asked about:

```python
# minimise x subject to x <= 4 and x >= b, where b is drawn around 3 with spread 1.5:
# every scenario that draws b above 4 has no feasible point at all
risky = runtime.execute("optimization.robust", "scenario_rhs_normal",
                        [[4.0, 3.0], [0.0, 1.5], 32, 20260731, "docs.demand"])["result"]

w = runtime.execute("optimization.robust", "robust_scenario_solve_default",
                    [[1.0], [1.0, 1.0], 2, 1, [0, 2], [4.0, 3.0], False, 32,
                     risky["rhs"], 0.95])["result"]
w["has_value"]                 # False
w["n_solved"]                  # 25
w["n_failed"]                  # 7
w["first_failed_scenario"]     # 6
w["objectives"]                # [] — no aggregate over the ones that happened to work
len(w["scenario_status"])      # 32 — the diagnosis survives, one status per scenario
runtime.execute("optimization.robust", "robust_status_name",
                [w["first_failed_status"]])["result"]      # "infeasible"
```

**Here-and-now** is the decision you actually have to make: one point, feasible in every
scenario. Because only the right-hand sides vary, that intersection is a single linear program
and its optimum is exact over the given scenarios — so this driver is not a heuristic, and it
says which scenario binds each row:

```python
h = runtime.execute("optimization.robust", "robust_min_max_rhs_default",
                    [c, A, 3, 2, senses, rhs, True, 64, scen])["result"]
h["objective"]                    # 31.562... — below the wait-and-see worst case, as it must be
h["x"]                            # [1.404..., 5.469...]
h["optimal_for_scenario_set"]     # True
h["effective_rhs"]                # [3.528..., 10.939..., 15.153...] — the tightest each row takes
h["binding_scenario"]             # [21, 19, 28] — which scenario supplied each
h["n_verified_scenarios"]         # 64
h["n_violating_scenarios"]        # 0
h["feasible_rate"]                # 1.0
h["worst_violation"]              # 0.0
h["bound_direction"]              # +1 — against the true support of the uncertainty
```

**What this does not prove.** It is a *sampled* guarantee, over 64 drawn scenarios, and nothing
here is a statement about a scenario nobody drew. A wider draw can only tighten a row, so the
objective errs in the direction `bound_direction` names — that is the honest reading, and it is
not a distributional guarantee. Likewise a satisfaction rate is an **estimate**: `rate_stderr`
is the binomial standard error of the estimate, which measures sampling noise and is not a
confidence bound on the true probability. `n_distinct_scenarios` tells you whether a
per-scenario block was supplied at all: without one, every scenario shares the same row and
the count is 1, because verifying one unchanging row a thousand times is the same measurement
a thousand times rather than evidence about a thousand scenarios. It does not de-duplicate
scenarios you did supply — a thousand supplied rows count as a thousand even if they happen to
be identical, since deciding that two rows are "the same scenario" is a modelling judgement
and not one this kernel makes for you.

## Shapes, sizes and search budgets are checked before anything is read

Every function validates its declared dimensions against the actual list lengths before
indexing, and returns a status rather than reading past the end of an array. Declared sizes are
capped against what the request actually contains, and **the work is bounded too, not only the
memory**: a dimension can sit inside an allocation limit and still drive an unbounded number of
comparisons, so every loop bound that multiplies into the cost is charged against the budget.
Exceeding it is a status, never a truncated answer presented as a complete one.

A tolerance is always derived from the one quantity being judged — this row's own magnitude,
this pivot's own curvature, this gap's own terms — and never from a sum, a maximum or a norm
over everything else in the model. An aggregate lets one row's units pay for another row's
contradiction, and the result is a confident answer to a problem that has none.

Each family has its own status vocabulary and a matching name function —
`route_status_name`, `sched_status_name` (with `sched_violation_name` for which constraint an
audit failed), `qp_status_name`, `mo_status_name`, `robust_status_name` — and each falls
through to the shared vocabulary, so an input rejection keeps the name of the module that
rejected it and tells you which of your arrays to look at.

## See also

* [Optimization & decision programs](optimization.md) — linear, integer, assignment and flow, solved exactly
* [Sparse systems & graph analytics](sparse-and-graph.md) — sparse solvers, shortest paths, centrality
* [Batched and chained execution](coarse-execution.md) — many kernel calls in one frame
* [Runtime library catalog](runtime-library-catalog.md) — every module and function
