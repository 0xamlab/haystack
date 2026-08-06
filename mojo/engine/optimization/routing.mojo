"""
optimization.routing — a tour that is a tour, a route that respects its windows, and a
heuristic that never claims to be an optimum. Zero Python.

Why this file exists
--------------------
The tree has exactly one TSP kernel and one bin-packing pair, and both are *seeds*
pretending to be answers at their call sites:

  * `combinatorial.tsp_greedy(distances)` is nearest-neighbour from node 0. It is typically
    25% above optimal and can be arbitrarily bad, it reports no length, it takes a NESTED
    `List[List[Float64]]` (which cannot cross a JSON frame), and it validates nothing: with
    a distance of exactly `1e308` in a row it returns `-1` as the next city and then indexes
    its `visited` list at `-1`. Nothing in the tree improves on its tour.
  * `combinatorial.tsp_tour_length(distances, tour)` indexes `distances[tour[i]][tour[i+1]]`
    with no range check at all, so a tour index outside `[0, n)` is an uncatchable process
    crash rather than an error.
  * `combinatorial.bin_packing_first_fit_decreasing(items, capacity)` returns a bin COUNT
    for a capacity-only problem. There is no vehicle routing anywhere: no capacity per
    route, no time windows, no depot, no way to ask "can four vehicles serve these stops
    before their due times".

So this module is the local search and the vehicle-routing layer, and the frozen kernels
stay exactly what they are: `tsp_greedy` is the seed (called, never reimplemented),
`tsp_tour_length` is the evaluator (called, never reimplemented, and it is the AUTHORITY on
every length reported here), and the two bin-packing kernels price the capacity relaxation.

The nested-list trap
--------------------
`tsp_greedy` and `tsp_tour_length` take `List[List[Float64]]`, which `mojo_inventory` cannot
marshal, so a public signature naming it would drop the function from the runtime contract
silently. Every public entry point here therefore takes a FLAT row-major `List[Float64]`
plus `n`, validates it, and builds the nested form internally for the frozen calls. The
nested copy is the second `n^2` allocation this module makes, and it is what fixes the node
ceiling (see below).

A heuristic is not an optimum, and this file never pretends otherwise
--------------------------------------------------------------------
There is deliberately NO `proven_optimal` field in any struct here, because nothing in this
file can establish one. What is reported instead:

  * `local_optimum` — True only when a full scan of the DECLARED move set found no
    improving move. That is optimality with respect to 2-opt and Or-opt moves ONLY. A
    2-opt/Or-opt local optimum can be far from the global optimum, and this flag says
    nothing about the global optimum.
  * `seed_length` and `improvement` — what the frozen greedy scored and what the local
    search actually bought, so a caller can see the size of the gain rather than trust it.
  * `ROUTE_OK_LIMIT` versus `ROUTE_OK` — the EXACT complement of the `local_optimum` field,
    for every driver in this file that returns a tour or a routing. `ROUTE_OK` is returned
    if and only if `local_optimum` is True; anything else is `ROUTE_OK_LIMIT`, whose name
    says only "verified, and not a local optimum of the declared moves". A status is what a
    caller branches on, so it must never assert something a field in the same value denies:
    code 120's name claims a local optimum, so returning it beside `local_optimum = False`
    made one struct carry two contradictory claims and a caller could use neither. WHICH
    reason the search fell short of a local optimum is read off the fields that measure it —
    `passes` against the cap, `moves_evaluated == 0` for a neighbourhood that was never
    scanned, `n_reeval_rejected > 0` for a move the frozen evaluator refused, and a
    `passes`/`moves_applied` pair below the cap for the work budget below. The frozen seed
    (`tsp_greedy_flat`) and a bare kick (`tsp_perturb_double_bridge`) are not searches at
    all, so they report `ROUTE_OK_LIMIT` too rather than borrowing an optimality claim from
    a code whose name makes one.
  * For vehicle routing, `ROUTE_NO_SOLUTION_FOUND` versus `ROUTE_INFEASIBLE_PROVEN`. The
    first says the construction heuristic did not find a feasible solution; it is NOT a
    proof that none exists, and it carries no routes. The second is a proof from the data
    alone (a stop whose demand exceeds one vehicle, a stop that cannot be reached before
    its due time even by going straight there from the depot, a stop that cannot be left
    in time to get home, or a total demand above the whole fleet's capacity).

Every returned answer is verified against the caller's own data first
--------------------------------------------------------------------
A tour that does not visit each city exactly once is not a tour, and a local search that
corrupts the permutation and returns a shorter "tour" is the archetypal confident wrong
answer for this problem. So:

  * the permutation is re-verified from scratch after EVERY accepted move, not once at the
    end. A break returns `ROUTE_ERR_NOT_A_PERMUTATION` with no numbers attached;
  * the frozen `tsp_tour_length` re-evaluates the tour after every accepted move, and its
    verdict overrides the move's own delta arithmetic. A move whose predicted improvement
    the frozen evaluator does not confirm is DISCARDED and the search stops. Monotone
    non-increase is therefore a property of the construction, not a hope about the algebra;
  * a vehicle-routing answer is re-audited end to end through `_audit_core`, the very same
    routine the public `vrp_check` runs on a stranger's solution. If the audit does not
    confirm capacity, every time window and "every customer served exactly once", the
    answer is thrown away and the status is `ROUTE_NO_SOLUTION_FOUND`.

Determinism is the point, not a nicety
--------------------------------------
A heuristic whose answer changes between runs cannot be used in a decision that has to be
explained. Nothing here calls `random_float64` or `seed(`. Randomness enters in exactly two
places, both counter-based via `determinism/`, so a draw is a pure function of its
coordinates and is identical whatever the search did beforehand:

  * the double-bridge kick in `tsp_iterated_local_search` draws its three cut points from
    `uniform_int_keyed(low, high, seed, stream_id("optimization.routing.kick"), 3k + slot)`
    for kick `k`. Kick `k` is therefore a pure function of `(seed, k)` and of the tour it is
    applied to — not of how many draws earlier kicks consumed;
  * the customer insertion order for vehicle-routing restart `r > 0` is
    `permutation_keyed(n_customers, seed, stream_id("optimization.routing.insertion"),
    r * n_customers)`.

Order and tie-breaks that affect the answer, stated so they can be reproduced:

  * the local search is BEST-improvement, not first-improvement. One full scan of the
    neighbourhood picks the single best move and applies it;
  * candidate moves are compared with a STRICT `<`, so on an exact tie the earlier move in
    scan order wins. Scan order is: all 2-opt moves (`i` ascending, then `j` ascending),
    then all Or-opt moves (segment length ascending, then `i` ascending, then insertion
    position ascending);
  * restart 0 of a vehicle-routing solve uses a stated deterministic insertion order — by
    due time ascending then customer index ascending when there are time windows, by demand
    descending then customer index ascending when there are not (which is the order the
    frozen FFD bound assumes). Restarts 1.. use the keyed permutation above;
  * a restart or a kick replaces the incumbent only on a STRICT improvement, so the
    earliest restart and the incumbent win ties.

Asymmetric distances work, and are reported rather than assumed away
--------------------------------------------------------------------
`d[i][j] != d[j][i]` is legal input. It matters because a 2-opt move REVERSES a segment,
and on an asymmetric matrix the reversed segment's internal cost is not the forward cost, so
the textbook four-edge delta is simply wrong there. Rather than assume symmetry or refuse
the instance, the delta carries the exact correction

    (sum over the segment of d[next][prev]) - (sum over the segment of d[prev][next])

which is obtained in O(1) from a prefix array rebuilt per tour state, and which is
identically zero on a symmetric matrix. `RouteTour.asymmetric` and `max_asymmetry` report
what was detected, and `distance_matrix_check` reports it before any search runs. Or-opt
here is pure RELOCATION with no reversal, so its six-edge delta is exact for both cases;
the reversed-insertion variant is deliberately absent rather than silently wrong.

Bounds, and why the ceiling is what it is
-----------------------------------------
`dims_fit(n, n, len(distance))` from `sparse_numerics.csr` is the shape guard, imported and
never restated: `n * n == len(distance)` is a WRAPPING 64-bit multiply and therefore not a
bound at all (`3 * 6148914691236517206 == 2`). It also ties `n` to what the payload actually
contains — a distance matrix is `n^2` cells, so a 60-byte request cannot declare a large
`n` here the way `linear.lp_from_arenas` once could.

`ROUTE_MAX_NODES` bounds the ALLOCATION on top of that, because a structurally consistent
request can still be a bomb. Two `n^2` Float64 arrays are live at once (the caller's flat
matrix and the nested copy the frozen kernels require), plus a dozen `n`-length arrays,
which the `n^2` term dwarfs. `MAX_CSR_DIM` is the ONE shared ceiling and is justified in
`csr.mojo` as the largest single array the 512 MiB resident-dataset budget tolerates, so it
is used DIVIDED by how many arrays this module holds per unit:

    2 * n^2 <= MAX_CSR_DIM   <=>   n <= sqrt(2^26 / 2) = 5792.6

`ROUTE_MAX_NODES` is `1 << 12` = 4096, the power of two below that, so
`2 * 4096^2 = 2^25` elements = half of `MAX_CSR_DIM`, leaving the `n`-length arrays and the
route bookkeeping inside the same budget. `route_node_ceiling()` exposes it and the suite
asserts the arithmetic, so the relationship is checked rather than commented. `MAX_CSR_DIM`
itself is never raised or lowered here; other packages share it.

Every distance is additionally required to be finite, non-negative and at most
`ROUTE_MAX_DISTANCE` (1e300). That single bound does three jobs: it keeps every tour length
finite (4096 legs x 1e300 = 4.1e303, comfortably inside Float64), it keeps `tsp_greedy` away
from the `1e308` sentinel that makes it return `-1` and index at `-1`, and it makes
"no answer" impossible to confuse with "an enormous answer".

The DIAGONAL is additionally required to be exactly 0.0. `d[c][c]` is the cost of staying
put, and the one place a tour ever reads it is `n == 1`, where the frozen `tsp_tour_length`
sums `d[tour[0]][tour[1]] = d[0][0]`: a nonzero diagonal was therefore priced as the length
of a tour that traverses no legs, and `tsp_two_opt(distance=[7.5], n=1, ...)` came back
`ROUTE_OK` with `tour_length = 7.5` and `local_optimum = True` where the only answer is 0.0.
A nonzero diagonal is a caller typo worth surfacing — the same argument this module already
makes for `demand[0] != 0.0` — so it is `ROUTE_ERR_DISTANCE` with the offending flat index,
not a number quietly folded into a total.

Bounding memory is not bounding WORK
------------------------------------
`ROUTE_MAX_NODES` and `dims_fit` bound what a request may ALLOCATE. They do not bound what it
may COST, and the effort knobs are where that leaks: `max_passes`, `n_kicks` and `n_restarts`
are bare integers that multiply into the cost without touching the payload at all. Clamping
them to a large ceiling is not a bound either — measured, `vrp_capacity_solve` on `n = 100`
(an 80 KB payload) took 2.37 s for four restarts, so the old `n_restarts` clamp of 4096 was
~40 minutes of single-threaded compute bought with one integer, which presents to every other
client of the worker as a hang rather than an error. That is `linear.lp_from_arenas`'s defect
transposed from allocation to time.

So there is ONE work budget, `ROUTE_WORK_BUDGET`, charged in elementary steps and threaded
through every loop that multiplies into the cost: each candidate move delta in the TSP scan,
each `_eval_route` (charged its own length, since that is what it walks), each key comparison
in the construction order, and each tour re-evaluation. Every driver spends at most that
budget however large its knobs are, and exhausting it is REPORTED — the search stopped short,
so `local_optimum` is False and the status is `ROUTE_OK_LIMIT` with a verified answer, never a
converged one. The budget is a compile-time constant, so the answer stays a pure function of
the arguments: determinism is not traded away for the bound. Measured after the change, the
same n = 40 shape asked for 4096 restarts runs 211 of them and returns in 3.07 s, and
`n_restarts = 1000000` is reported back as the count actually attempted rather than accepted in
silence.
@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: optional
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_optimization_routing.mojo
benchmark: benchmarks/mojo_benchmarks/bench_optimization_tier2.mojo
docs: none
version_introduced: pre_manifest
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from combinatorial import (
    bin_packing_first_fit,
    bin_packing_first_fit_decreasing,
    tsp_greedy,
    tsp_tour_length,
)
from determinism.sampling_keyed import permutation_keyed, uniform_int_keyed
from determinism.streams import stream_id
from numerical_stability import kahan_sum
from optimization.model import _ceil_f, model_finite as _finite
from sparse_numerics.csr import MAX_CSR_DIM, dims_fit

# ── status codes ──────────────────────────────────────────────────────────────
# ONE numbering is shared across the `optimization` modules whose statuses reach the same
# caller, so a code has one meaning package-wide. Ranges already taken in that chain:
#
#     0-30    optimization.model
#     40-42   optimization.linear   (extractor)
#     60-63   optimization.linear   (solver)
#     80-86   optimization.explain
#     100-105 optimization.integer
#     120-129 optimization.routing  <- THIS FILE, and nothing outside it
#
# (`optimization.flow` 0-21 and `optimization.assignment` 0-13 are self-contained
# namespaces with their own name tables and are deliberately not part of this chain.)
#
# This module never forwards a code from another module: every rejection below is one of
# these ten, so `route_status_name` needs no fall-through and a caller holding a routing
# status never has to guess which vocabulary produced it.

# An answer, verified, and NOT proven optimal: the search exhausted its move set. Returned if
# and ONLY if the `local_optimum` field of the same value is True — this code's NAME asserts a
# local optimum, so returning it beside `local_optimum = False` would be one struct making two
# contradictory claims.
comptime ROUTE_OK: Int = 120
# An answer, verified, that is NOT a local optimum of the declared moves. The exact complement
# of `ROUTE_OK`, covering every reason a search fell short and every driver that does not
# search at all: the pass cap, the work budget, a move the frozen re-evaluation refused, a
# neighbourhood that is empty at this `n`, both move families disabled, the frozen greedy seed,
# and a bare double-bridge kick. WHICH reason is read off `passes`, `moves_evaluated` and
# `n_reeval_rejected`, which measure it; the code claims nothing beyond "not a local optimum".
comptime ROUTE_OK_LIMIT: Int = 121
# The heuristic found no feasible solution. NOT a proof that none exists. No numbers.
comptime ROUTE_NO_SOLUTION_FOUND: Int = 122
# Proven infeasible from the data alone. No numbers.
comptime ROUTE_INFEASIBLE_PROVEN: Int = 123
# `n` is not positive, or `n * n` is not `len(distance)`.
comptime ROUTE_ERR_SHAPE: Int = 124
# `n` is above the allocation ceiling derived from MAX_CSR_DIM.
comptime ROUTE_ERR_TOO_LARGE: Int = 125
# A parallel array (demand / ready / due / service / route_start) has the wrong length.
comptime ROUTE_ERR_LENGTH_MISMATCH: Int = 126
# A distance is NaN, infinite, negative, above ROUTE_MAX_DISTANCE, or a nonzero diagonal.
comptime ROUTE_ERR_DISTANCE: Int = 127
# A demand, capacity, service time, window, vehicle count or search parameter is not usable.
comptime ROUTE_ERR_INSTANCE: Int = 128
# A tour handed in, or produced, does not visit each city exactly once.
comptime ROUTE_ERR_NOT_A_PERMUTATION: Int = 129

# ── ceilings and tolerances ───────────────────────────────────────────────────

# See the module docstring: 2 * ROUTE_MAX_NODES^2 == 2^25 == MAX_CSR_DIM / 2, so the two
# live n^2 Float64 arrays fit inside half the one shared single-object budget and the
# n-length arrays fit in the rest. Derived from MAX_CSR_DIM, never a second ceiling.
comptime ROUTE_MAX_NODES: Int = 1 << 12

# The largest admissible distance / time / demand. 1e300 with at most 4096 legs keeps every
# accumulated length, time and load finite, and keeps `tsp_greedy` away from its own 1e308
# `best_dist` sentinel — which it would answer with `best_next = -1`, then write
# `visited[-1]`.
comptime ROUTE_MAX_DISTANCE: Float64 = 1e300

# The spacing between consecutive Float64 values at 1.0. Every tolerance in this file is a
# multiple of THIS times the magnitude of the one quantity being judged — never a caller
# tolerance, and never a sum over the instance. A tolerance that scales with the whole
# problem lets one row's units pay for another row's contradiction.
comptime ROUTE_DBL_EPSILON: Float64 = 2.220446049250313e-16

# Ulps of rounding a single move delta is allowed to be. A delta is a sum of at most six
# edge costs plus one asymmetry correction, so its rounding error is a handful of ulps of
# the largest term; 8 is generous for that and is still a ROUNDING budget.
comptime ROUTE_MOVE_ULPS: Float64 = 8.0

# A magnitude cannot be negative, so -1.0 means "never measured". 0.0 would read as
# "no violation", which is the claim these fields exist to substantiate.
comptime ROUTE_ABSENT: Float64 = -1.0

# `distance_matrix_check` tests the triangle inequality, which is O(n^3). Above this it
# reports `triangle_checked = False` rather than either lying or spending the budget. The
# inequality is NOT required by anything here — a matrix that violates it still yields a
# valid permutation — so skipping the test changes no answer.
comptime ROUTE_TRIANGLE_MAX_N: Int = 96

# Hard cap on neighbourhood SCANS, independent of the caller's `max_passes`. Each accepted
# move strictly decreases the frozen evaluator's length and there are finitely many tours, so
# the search already terminates on its own; this caps the number of scans in case it does so
# late. It bounds the pass COUNT and NOT the work, which is why it is not the resource bound:
# `ROUTE_WORK_BUDGET` below is. The effort knobs — `max_passes`, `n_kicks`, `n_restarts` — are
# the caller's, and reaching one is reported as `ROUTE_OK_LIMIT` rather than dressed up as a
# converged answer.
comptime ROUTE_MAX_PASSES: Int = 1 << 16

# THE work bound: the most elementary steps one public call may spend, whatever its effort
# knobs say. Charged where the cost actually is — one unit per candidate move delta in the TSP
# scan, `len(route) + 2` per `_eval_route` (it walks the route once and allocates two arrays of
# that length), `n + 1` per frozen tour re-evaluation, one per key comparison in the
# construction order — and threaded through every loop that multiplies into the cost, so no
# combination of `max_passes`, `n_kicks` and `n_restarts` can exceed it. A clamp on the KNOBS
# cannot do this job: `n_restarts` clamped to 4096 was still ~40 minutes of compute at n = 100,
# because the clamp bounds the iteration count and each iteration's cost is O(n^3).
#
# 1 << 25 is chosen against measurement, not taste. Timed in the JIT harness:
#
#   vrp_capacity_solve   n=100  n_restarts=4        -> 4 restarts run,   2.72 s (not cut)
#   vrp_capacity_solve   n=100  n_restarts=4096     -> 4 restarts run,   3.05 s (budget cut)
#   vrp_capacity_solve   n=40   n_restarts=4096     -> 211 restarts run, 3.07 s (budget cut)
#   tsp_iterated_...     n=60   n_kicks=1000000     -> 570 kicks run,    0.11 s (budget cut)
#
# So the ceiling is ~3 s per call whatever the knobs say, against the ~40 minutes the old
# `n_restarts` clamp permitted at n = 100 and the ~150 s it permitted at n = 40 — and the
# legitimate n = 100 four-restart request that measured 2.37 s still runs to completion, which
# is the constraint that fixes the size from below. Smaller would start truncating real work;
# larger would raise the worst case a caller can buy with one integer.
#
# The consequence to state plainly: an instance whose single construction alone costs more than
# the budget (roughly n > 150, where cheapest-insertion is O(n^3)) will not produce a routing
# and comes back `ROUTE_NO_SOLUTION_FOUND` with `restarts_feasible = 0`. That status claims
# nothing — it is not a proof of infeasibility — and it is the honest report for an instance
# this heuristic cannot serve without occupying a worker for hours.
#
# Exhaustion mid-search is an outcome, not an error: the incumbent has already been audited, so
# it is returned with `local_optimum = False` and `ROUTE_OK_LIMIT`. Because the budget is a
# compile-time constant, every answer remains a pure function of the arguments.
comptime ROUTE_WORK_BUDGET: Int = 1 << 25

comptime ROUTE_DEPOT: Int = 0


def route_status_name(code: Int) -> String:
    """Name for a status code, so a rejection surfaces the defect and not a bare number.

    No fall-through to `model_status_name`: this module never forwards another module's
    code, so a name for one would advertise an outcome that cannot happen here.
    """
    if code == ROUTE_OK:
        return "verified_local_optimum_of_the_declared_moves_not_proven_optimal"
    if code == ROUTE_OK_LIMIT:
        return "verified_but_not_a_local_optimum_of_the_declared_moves"
    if code == ROUTE_NO_SOLUTION_FOUND:
        return "no_feasible_solution_found_which_is_not_a_proof_of_infeasibility"
    if code == ROUTE_INFEASIBLE_PROVEN:
        return "proven_infeasible_from_the_instance_alone"
    if code == ROUTE_ERR_SHAPE:
        return "distance_matrix_shape_invalid"
    if code == ROUTE_ERR_TOO_LARGE:
        return "dimension_too_large"
    if code == ROUTE_ERR_LENGTH_MISMATCH:
        return "parallel_arrays_length_mismatch"
    if code == ROUTE_ERR_DISTANCE:
        return "distance_non_finite_negative_above_1e300_or_nonzero_diagonal"
    if code == ROUTE_ERR_INSTANCE:
        return "demand_capacity_window_vehicle_count_or_parameter_invalid"
    if code == ROUTE_ERR_NOT_A_PERMUTATION:
        return "tour_does_not_visit_each_city_exactly_once"
    return "unknown_status_" + String(code)


def route_node_ceiling() -> Int:
    """The node ceiling, exposed so a caller and a test can assert it rather than infer it.

    Deterministic and zero-argument. `2 * route_node_ceiling()^2 <= MAX_CSR_DIM` is the
    arithmetic the module docstring states, and the suite checks it.
    """
    return ROUTE_MAX_NODES


# ── return-only result structs ────────────────────────────────────────────────
# Declared in THIS file because the marshalling spec for a returned struct is parsed one
# file at a time: returning a struct owned by another module drops the function from the
# runtime contract and from the dispatch silently, with no error anywhere.


@fieldwise_init
struct RouteScalar(Copyable, Movable):
    """One number that may not exist. `has_value` is the authority; `value` is padding.

    NaN is the loudest absence marker in arithmetic and does not survive the JSON frame
    these drivers cross, which is why the flag carries the meaning.
    """

    var status: Int
    var has_value: Bool
    var value: Float64


@fieldwise_init
struct RouteMatrixCensus(Copyable, Movable):
    """What the distance matrix is, before anything is solved on it.

    `symmetric` and `max_asymmetry` exist so asymmetry is a reported fact rather than an
    assumption: `max_asymmetry` is the largest `|d[i][j] - d[j][i]|` and
    `asymmetry_row`/`asymmetry_col` name where it was found (-1 when symmetric).

    `triangle_checked` is False above `ROUTE_TRIANGLE_MAX_N`, and then
    `max_triangle_violation` is `ROUTE_ABSENT` and `triangle_ok` is False — "not measured",
    not "violated". A violated triangle inequality is not an error here: it changes no
    guarantee this module makes, and a valid permutation still comes back.

    `defect_index` is the flat index of the first unusable cell when the status is
    `ROUTE_ERR_DISTANCE`, and -1 otherwise. On any status other than `ROUTE_OK` every other
    field is padding, `symmetric == False` included — the status is the authority there, and
    nothing was measured.
    """

    var status: Int
    var n: Int
    var symmetric: Bool
    var max_asymmetry: Float64
    var asymmetry_row: Int
    var asymmetry_col: Int
    var has_extremes: Bool
    var min_offdiag: Float64
    var max_offdiag: Float64
    var n_zero_offdiag: Int
    var triangle_checked: Bool
    var triangle_ok: Bool
    var max_triangle_violation: Float64
    var defect_index: Int


@fieldwise_init
struct RouteTourCheck(Copyable, Movable):
    """Whether a `List[Int]` is a tour of `n` cities, recomputed from scratch.

    The expected form is the CLOSED one the frozen kernels use and every driver here
    returns: `n + 1` entries, the first `n` a permutation of `0..n-1`, and the last equal to
    the first. `length_ok`, `closed` and `is_permutation` are reported separately so a
    caller learns which of the three failed.
    """

    var status: Int
    var n: Int
    var length_ok: Bool
    var closed: Bool
    var is_permutation: Bool
    var n_repeated: Int
    var n_missing: Int
    var first_defect_position: Int
    var first_missing_city: Int


@fieldwise_init
struct RouteTour(Copyable, Movable):
    """A tour, its length, what the local search bought, and what it does NOT prove.

    There is no `proven_optimal` field on purpose. `local_optimum` means "one full scan of
    the declared move set found no improving move" — optimality with respect to 2-opt and
    Or-opt moves ONLY, which says nothing about the global optimum. The 2-opt half of that
    neighbourhood is complete for the cycle (every non-adjacent pair of tour edges, plus the
    whole-tour reversal that only an asymmetric matrix can benefit from); the Or-opt half
    excludes segments spanning the start city, which `tsp_or_opt` states precisely and which
    is a real restriction rather than a WLOG one.

    `tour` is closed: `n + 1` entries with `tour[n] == tour[0]`, so it can be handed straight
    to `combinatorial.tsp_tour_length`. Every tour a search here produces starts at city 0,
    because the frozen seed does and no move touches position 0; `tsp_perturb_double_bridge`
    preserves whatever start city the caller's tour had, since a rotation of a cycle is the
    same cycle. `is_permutation` is VERIFIED (after every accepted move, not once at the
    end), and on any error status every list is empty and every number is flagged absent.

    `local_optimum` is False when nothing was searched — both move families disabled, a
    neighbourhood that is empty at this `n`, or a zero pass budget — so it never asserts a
    scan that did not happen. `moves_evaluated` is the count that distinguishes the two. It is
    also False when the work budget cut a scan short, because a partial scan cannot say that no
    improving move exists.

    `status` is the EXACT complement of `local_optimum`: `ROUTE_OK` when it is True,
    `ROUTE_OK_LIMIT` when it is False, on every path that returns a tour. Two fields of one
    returned value may not make contradictory claims, and code 120's name claims a local
    optimum.

    `tour_length` is the frozen evaluator's number, not an incrementally maintained one.
    `improvement` is `seed_length - tour_length` and is `ROUTE_ABSENT` when the seed length
    was never formed. `n_reeval_rejected` counts moves whose delta predicted an improvement
    that the frozen re-evaluation did not confirm; a nonzero count with `local_optimum`
    False is exactly why the search stopped short.
    """

    var status: Int
    var n: Int
    var is_permutation: Bool
    var has_length: Bool
    var tour_length: Float64
    var tour: List[Int]
    var has_seed_length: Bool
    var seed_length: Float64
    var improvement: Float64
    var local_optimum: Bool
    var two_opt_enabled: Bool
    var or_opt_enabled: Bool
    var max_segment: Int
    var passes: Int
    var moves_applied: Int
    var moves_evaluated: Int
    var n_reeval_rejected: Int
    var kicks: Int
    var kicks_accepted: Int
    var asymmetric: Bool
    var max_asymmetry: Float64
    var seed: UInt64


@fieldwise_init
struct RouteVehicleBound(Copyable, Movable):
    """How many vehicles the capacity relaxation needs, and how hard the packing is.

    `lower_bound` is `ceil(total_demand / capacity)`, which IS a lower bound on the number
    of vehicles ANY feasible routing needs: every feasible routing induces a feasible
    packing of the demands into capacity-sized bins, and no packing can beat the load ratio.
    Time windows can only push the true number up, never down.

    `ffd_bins` and `ff_bins` are the frozen `bin_packing_first_fit_decreasing` and
    `bin_packing_first_fit` counts. Read them for what they are: a FEASIBLE capacity-only
    packing, hence an upper bound on the relaxation's optimum and NOT a lower bound on
    anything. They are reported because the gap `ffd_bins - lower_bound` tells a caller
    whether the packing alone is hard, and `ffd_bins > n_vehicles` marks an instance that
    needs more than first-fit-decreasing thinking — but only `lower_bound` is ever used to
    prove infeasibility, precisely because FFD's own bound involves a literature constant
    and a wrong lower bound would turn a feasible instance into a false `infeasible`.

    `n_oversized` counts demands above the capacity. One of those is a proof of
    infeasibility, so the status is `ROUTE_INFEASIBLE_PROVEN` and `has_bound` is False:
    the vehicle count of an instance with no solution does not exist.
    """

    var status: Int
    var n_items: Int
    var has_bound: Bool
    var lower_bound: Int
    var ffd_bins: Int
    var ff_bins: Int
    var total_demand: Float64
    var max_demand: Float64
    var n_oversized: Int
    var defect_index: Int


@fieldwise_init
struct RouteSolution(Copyable, Movable):
    """A set of vehicle routes that has been re-audited against the caller's own arrays.

    Capacity and every time window are HARD. `feasible` is True only when `_audit_core` —
    the same routine the public `vrp_check` runs on a stranger's solution — confirms every
    load, every window and "every customer served exactly once". If it does not, the answer
    is discarded and the status is `ROUTE_NO_SOLUTION_FOUND` with empty lists.

    THE LAYOUT INVARIANT, which is what makes the flat arrays readable — every route listed is
    NON-EMPTY, and empty routes are REMOVED rather than retained as slots:

      * `len(route_start) == n_routes_used + 1`, so `for v in range(n_routes_used):
        stops[route_start[v] : route_start[v + 1]]` reads every route and nothing else;
      * `route_start[0] == 0`, `route_start[n_routes_used] == len(stops)`, and the offsets are
        STRICTLY increasing — the routes therefore PARTITION `stops`: no gap, no overlap, and
        no zero-length slot;
      * `route_load`, `route_distance` and `route_return_time` each have exactly
        `n_routes_used` entries, indexed by the same `v`;
      * every customer `1..n-1` appears in exactly one route at exactly one position, which
        `_audit_core` verifies (`all_served`, `n_served == n_customers`), so together with the
        partition above the routes are a partition of the CUSTOMERS as well;
      * `n_vehicles - n_routes_used` vehicles stay at the depot and are simply not listed. A
        vehicle that never moves has no sequence, no load and no distance, and inventing a
        zero-length slot for it once made `n_routes_used` and `route_start` disagree.

    That disagreement was a real defect, not a hypothetical: relocation can EMPTY a route, and
    while an offset was appended for the emptied slot, `n_routes_used` counted only the
    non-empty ones. `route_start = [0, 3, 3, 5, 8]` with `n_routes_used = 3` made a caller
    following this docstring read routes `[0:3]`, `[3:3]`, `[3:5]` and silently drop the three
    customers in `[5:8]` — a reconstruction that `vrp_check` then called infeasible with three
    customers missing, under `ROUTE_OK` and `feasible = True`. Both fields now express the
    single invariant above, and `_solve_core` refuses to return a value that violates it.

    The depot is NOT in `stops`; every route starts and ends there.

    `defect_vehicle`, `defect_stop` and `defect_node` name WHICH vehicle, WHICH position in
    its sequence and WHICH node carried the violation that made an attempt infeasible, or
    -1. On `ROUTE_INFEASIBLE_PROVEN` `defect_node` is the stop the proof is about.

    `restarts` is the number of restarts actually ATTEMPTED, not the number asked for: the
    shared work budget can stop the loop early, and a count below the request is how a caller
    sees that. `restarts_feasible` counts those that produced an audited feasible routing.

    `max_capacity_excess` and `max_lateness` are 0.0 on a verified answer, `ROUTE_ABSENT`
    when nothing was measured. `local_optimum` is with respect to the intra-route 2-opt and
    inter-route relocation moves only — there is no proven-optimal claim here either, it is
    False whenever the improvement scan was vacuous or was cut short by the work budget, and
    `status` is its exact complement: `ROUTE_OK` if and only if `local_optimum` is True,
    `ROUTE_OK_LIMIT` otherwise.
    """

    var status: Int
    var n: Int
    var n_customers: Int
    var n_vehicles: Int
    var windowed: Bool
    var feasible: Bool
    var proven_infeasible: Bool
    var has_total: Bool
    var total_distance: Float64
    var n_routes_used: Int
    var stops: List[Int]
    var route_start: List[Int]
    var route_load: List[Float64]
    var route_distance: List[Float64]
    var route_return_time: List[Float64]
    var lower_bound_vehicles: Int
    var ffd_bins: Int
    var max_capacity_excess: Float64
    var max_lateness: Float64
    var defect_vehicle: Int
    var defect_stop: Int
    var defect_node: Int
    var restarts: Int
    var restarts_feasible: Int
    var passes: Int
    var moves_applied: Int
    var local_optimum: Bool
    var seed: UInt64


@fieldwise_init
struct RouteAudit(Copyable, Movable):
    """Verdict on a routing SOMEBODY ELSE produced, recomputed from the matrix.

    The split between rejecting and reporting is deliberate. A structural break that cannot
    be indexed — a stop outside `[1, n)`, the depot appearing as a stop, a `route_start`
    that is not a non-decreasing cover of `stops` — is a REJECTION, because there is nothing
    to audit. Everything semantic is a REPORT: a duplicated customer, a missing customer, an
    overloaded vehicle and a missed window all come back with `status == ROUTE_OK`,
    `feasible == False` and the counts and defect indices that say which and where.

    `feasible` requires capacity AND every window AND every customer served exactly once —
    a routing that serves a customer twice is not a routing, however cheap it is.
    `total_distance` is reported even when infeasible, because it is a fact about the routes
    given; `feasible` is what says whether they are a solution.

    How the defect triple is attributed, so it can be read without guessing: the first
    offending VEHICLE in index order wins, and within it a window violation names the exact
    sequence position that was late (position `len(route)` means the return leg to the depot,
    which is not a stop). A capacity violation is a property of the whole route rather than of
    one stop, so it names the route's LAST stop, and it is only reported when no window
    violation preceded it. `n_capacity_violations` counts overloaded ROUTES;
    `n_window_violations` counts late stops across all routes.
    """

    var status: Int
    var n: Int
    var n_customers: Int
    var n_vehicles: Int
    var windowed: Bool
    var feasible: Bool
    var all_served: Bool
    var n_served: Int
    var n_duplicated: Int
    var n_missing: Int
    var has_total: Bool
    var total_distance: Float64
    var route_load: List[Float64]
    var route_distance: List[Float64]
    var route_return_time: List[Float64]
    var n_capacity_violations: Int
    var n_window_violations: Int
    var max_capacity_excess: Float64
    var max_lateness: Float64
    var defect_vehicle: Int
    var defect_stop: Int
    var defect_node: Int


# ── Mojo-level internals ──────────────────────────────────────────────────────
# Never in a public signature. `_SearchState` and `_RouteEval` exist so a helper can return
# several correlated values without smuggling them through parallel lists.


@fieldwise_init
struct _SearchState(Copyable, Movable):
    var order: List[Int]
    var length: Float64
    var passes: Int
    var moves: Int
    var evaluated: Int
    var local_optimum: Bool
    var reeval_rejected: Int
    var permutation_broken: Bool


@fieldwise_init
struct _ImproveResult(Copyable, Movable):
    # `evaluated` is what makes `local_optimum` a claim rather than a default: the VRP
    # improvement scan has an empty neighbourhood whenever there are no routes or every route
    # holds one stop with no feasible relocation target, and "no improving move exists" must
    # not be asserted from a scan that examined none. `_local_search` guards the identical
    # claim the identical way — one invariant, one strength, in both halves of this file.
    var routes: List[List[Int]]
    var passes: Int
    var moves: Int
    var evaluated: Int
    var local_optimum: Bool


@fieldwise_init
struct _RouteEval(Copyable, Movable):
    var feasible: Bool
    var load: Float64
    var dist: Float64
    var end_time: Float64
    var cap_excess: Float64
    var lateness: Float64
    var n_cap_violations: Int
    var n_window_violations: Int
    var defect_stop: Int
    var defect_node: Int


# ── tolerances ────────────────────────────────────────────────────────────────


def _accum_tol(scale: Float64, steps: Int) -> Float64:
    """Rounding budget for a quantity accumulated over `steps` additions.

    Sized by `ROUTE_DBL_EPSILON` times the magnitude of the ONE quantity being judged, times
    the number of additions that formed it — which is what floating point can actually
    explain away, and nothing else. Deliberately NOT `tol * (1 + sum over the instance)`:
    an aggregate over rows lets an unrelated large right-hand side swallow a flat
    contradiction, which is how an infeasible LP once came back optimal in this package. Also
    deliberately not a plain fraction of the scale, because a fraction shrinks with the
    quantity's magnitude while a real violation does not.

    Returns 0.0 for a zero scale, so a violation at zero magnitude is caught exactly.
    """
    var s = fabs(scale)
    if not _finite(s):
        return 0.0
    var steps_f = Float64(steps + 1)
    if steps < 0:
        steps_f = 1.0
    return steps_f * ROUTE_DBL_EPSILON * s


def _pair_tol(a: Float64, b: Float64, steps: Int) -> Float64:
    """`_accum_tol` at the larger magnitude of the two quantities being compared.

    A comparison `a > b` is judged at the scale of `a` and `b` and of nothing else — not of
    the fleet, not of the instance, not of any other route.
    """
    var scale = fabs(a)
    if fabs(b) > scale:
        scale = fabs(b)
    return _accum_tol(scale, steps)


def _move_tol(scale: Float64) -> Float64:
    """Rounding budget for one move delta, at the magnitude of its largest term."""
    var s = fabs(scale)
    if not _finite(s):
        return 0.0
    return ROUTE_MOVE_ULPS * ROUTE_DBL_EPSILON * s


# ── shape and content validation ──────────────────────────────────────────────


def _shape_defect(distance: List[Float64], n: Int) -> Int:
    """Everything that must hold before a single cell is read.

    The ceiling is tested BEFORE `dims_fit` so "too big to allocate for" and "these numbers
    do not describe this list" stay separate codes; `dims_fit` folds both into False. `n`
    must be positive: a tour of zero cities does not exist, and returning an empty list for
    it would be an answer where there is none.
    """
    if n <= 0:
        return ROUTE_ERR_SHAPE
    if n > ROUTE_MAX_NODES:
        return ROUTE_ERR_TOO_LARGE
    if not dims_fit(n, n, len(distance)):
        return ROUTE_ERR_SHAPE
    return ROUTE_OK


def _distance_defect_index(distance: List[Float64], n: Int) -> Int:
    """Flat index of the first cell that is not a usable distance, or -1.

    Safe to index: the caller has already established `len(distance) == n * n` through
    `dims_fit`.

    The DIAGONAL must be exactly 0.0, and that is a requirement rather than an observation.
    `d[c][c]` is the cost of staying put, and the one place a tour reads it is `n == 1`, where
    the frozen `tsp_tour_length` sums `d[tour[0]][tour[1]] = d[0][0]`. Left unconstrained, a
    nonzero diagonal was priced as a tour length: `tour_length_flat(distance=[7.5], n=1,
    tour=[0, 0])` answered `has_value = True, value = 7.5`, and `tsp_two_opt(distance=[7.5],
    n=1, max_passes=5)` answered `ROUTE_OK` with `tour_length = 7.5` and `local_optimum = True`
    — for a tour that traverses no legs, whose only length is 0.0. That is the frozen kernel's
    failure value showing through, which is exactly what this wrapper exists to make honest.
    Refusing it also surfaces the caller's typo instead of folding it into a total, the same
    argument `_instance_defect` already makes for `demand[0] != 0.0`.
    """
    for i in range(n):
        for j in range(n):
            var k = i * n + j
            var d = distance[k]
            if not _finite(d):
                return k
            if d < 0.0 or d > ROUTE_MAX_DISTANCE:
                return k
            if i == j and d != 0.0:
                return k
    return -1


def _dist(distance: List[Float64], n: Int, a: Int, b: Int) -> Float64:
    """`d[a][b]` from the flat row-major matrix.

    Deliberately without a range check, and that is safe by construction rather than by
    luck. Every index reaching here is one of three things: an entry of a tour whose
    permutation has been re-verified since the last mutation, a stop id that `_audit_core`
    has already tested against `[1, n)`, or a customer id that `_insertion_order` built as
    `k + 1` for `k` in `[0, n-1)`. Position indices always come from a loop bounded by `n`.
    The permutation re-verification after each accepted move IS this function's bounds guard,
    which is why it runs on every move and not once at the end.
    """
    return distance[a * n + b]


def _nested(distance: List[Float64], n: Int) -> List[List[Float64]]:
    """The nested form the frozen `tsp_greedy` / `tsp_tour_length` require.

    Built here and never exposed: `List[List[Float64]]` cannot be marshalled, so a public
    signature naming it would be dropped from the runtime contract without a word.
    """
    var out = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            row.append(distance[i * n + j])
        out.append(row^)
    return out^


def _asymmetry(distance: List[Float64], n: Int) -> Float64:
    """The largest `|d[i][j] - d[j][i]|`. 0.0 for a symmetric matrix."""
    var worst = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            var gap = fabs(distance[i * n + j] - distance[j * n + i])
            if gap > worst:
                worst = gap
    return worst


def _is_permutation(order: List[Int], n: Int) -> Bool:
    """True when `order` is exactly `0..n-1` in some sequence. O(n), no allocation reuse.

    Called after EVERY accepted move. A local search that corrupts the permutation and
    returns a shorter "tour" is the archetypal confident wrong answer for this problem, so
    the invariant is measured rather than reasoned about.
    """
    if len(order) != n:
        return False
    var seen = List[Bool]()
    for _ in range(n):
        seen.append(False)
    for k in range(n):
        var c = order[k]
        if c < 0 or c >= n:
            return False
        if seen[c]:
            return False
        seen[c] = True
    return True


def _closed(order: List[Int]) -> List[Int]:
    """`order` with its first city appended, which is the frozen kernels' tour form."""
    var out = List[Int]()
    for k in range(len(order)):
        out.append(order[k])
    if len(order) > 0:
        out.append(order[0])
    return out^


def _length_of(nested: List[List[Float64]], order: List[Int]) -> Float64:
    """Tour length via the frozen `combinatorial.tsp_tour_length`, unchanged.

    THE evaluator for this module. Every reported length and every monotonicity decision
    goes through this call, so the number a caller sees is the frozen kernel's own.
    """
    return tsp_tour_length(nested, _closed(order))


def _skew_prefix(
    distance: List[Float64], n: Int, order: List[Int], asymmetric: Bool
) -> List[Float64]:
    """Prefix sums of `d[next][prev] - d[prev][next]` along the tour.

    This is what makes a 2-opt delta exact on an ASYMMETRIC matrix in O(1): reversing
    positions `i..j` replaces the forward internal path by the backward one, and the
    difference is exactly `skew[j] - skew[i]`. Identically zero on a symmetric matrix, so
    the array is filled with zeros and skipped there.
    """
    var skew = List[Float64]()
    skew.append(0.0)
    if not asymmetric:
        for _ in range(1, n):
            skew.append(0.0)
        return skew^
    var acc = 0.0
    for k in range(n - 1):
        var a = order[k]
        var b = order[k + 1]
        acc += _dist(distance, n, b, a) - _dist(distance, n, a, b)
        skew.append(acc)
    return skew^


# ── the local search ──────────────────────────────────────────────────────────


def _apply_two_opt(order: List[Int], i: Int, j: Int) -> List[Int]:
    """`order` with positions `i..j` reversed. Position 0 is never inside the range."""
    var out = List[Int]()
    for k in range(len(order)):
        out.append(order[k])
    var lo = i
    var hi = j
    while lo < hi:
        var tmp = out[lo]
        out[lo] = out[hi]
        out[hi] = tmp
        lo += 1
        hi -= 1
    return out^


def _apply_or_opt(order: List[Int], n: Int, i: Int, seg_len: Int, k: Int) -> List[Int]:
    """`order` with the segment at `i..i+seg_len-1` relocated to just after position `k`.

    Pure relocation: the segment keeps its direction, which is what makes the six-edge
    delta exact for an asymmetric matrix too. `k` is an index into the ORIGINAL order and
    is outside `[i-1, i+seg_len-1]`, so the city at `k` survives the removal and city
    `order[0]` — never inside the segment — stays at position 0.
    """
    var seg = List[Int]()
    for m in range(i, i + seg_len):
        seg.append(order[m])
    var rest = List[Int]()
    for m in range(n):
        if m >= i and m < i + seg_len:
            continue
        rest.append(order[m])
    var pos = k
    if k >= i + seg_len:
        pos = k - seg_len
    var out = List[Int]()
    for m in range(pos + 1):
        out.append(rest[m])
    for m in range(len(seg)):
        out.append(seg[m])
    for m in range(pos + 1, len(rest)):
        out.append(rest[m])
    return out^


def _local_search(
    distance: List[Float64], nested: List[List[Float64]], n: Int, start: List[Int],
    use_two_opt: Bool, use_or_opt: Bool, max_segment: Int, max_passes: Int,
    asymmetric: Bool, mut work: Int
) -> _SearchState:
    """Best-improvement 2-opt + Or-opt from `start`, monotone by construction.

    One pass scans the whole neighbourhood, picks the single best improving move, applies
    it, re-verifies the permutation and re-evaluates the length with the FROZEN evaluator.
    The frozen evaluator is the authority: a move whose predicted improvement it does not
    confirm is discarded and the search stops, so the reported length is non-increasing
    across passes as a property of the code rather than of the delta algebra.

    Candidates are compared with a strict `<`, so ties go to the earlier move in scan order:
    all 2-opt moves (`i` then `j` ascending), then all Or-opt moves (segment length, then
    `i`, then insertion position ascending). No randomness anywhere in this routine.

    `work` is the shared budget, decremented per candidate examined and per frozen
    re-evaluation, and it bounds the cost of the whole call: `max_passes` bounds the pass COUNT
    while one pass is O(n^2 * max_segment), so the cap alone is not a bound. It is checked once
    per outer scan row, so a scan overshoots by at most O(n) — payload-bounded, since an n-city
    instance needs an n^2-cell matrix. A scan the budget CUTS SHORT sets `local_optimum` False
    and applies nothing: a partial scan cannot say that no improving move exists, and the
    incumbent it would compare against is already verified.
    """
    var order = List[Int]()
    for k in range(len(start)):
        order.append(start[k])
    var length = _length_of(nested, order)
    work -= n + 1
    var passes = 0
    var moves = 0
    var evaluated = 0
    var reeval = 0
    var local_opt = False
    var cut = False

    while passes < max_passes:
        if work <= 0:
            # No scan happened this pass, so `local_optimum` stays False and the incumbent —
            # already a verified permutation with a frozen-evaluator length — is what returns.
            break
        var skew = _skew_prefix(distance, n, order, asymmetric)
        work -= n
        var best_delta = 0.0
        var best_kind = -1
        var best_i = -1
        var best_j = -1
        var best_k = -1

        if use_two_opt and n >= 3:
            # Removing edges (order[i-1], order[i]) and (order[j], order[j+1 mod n]).
            # i <= n-2 and j <= n-1 covers every non-adjacent pair of tour edges, plus the
            # (i=1, j=n-1) whole-tour reversal, which is a real move on an asymmetric matrix.
            for i in range(1, n - 1):
                if work <= 0:
                    cut = True
                    break
                for j in range(i + 1, n):
                    evaluated += 1
                    work -= 1
                    var p = order[i - 1]
                    var a = order[i]
                    var b = order[j]
                    var q = order[(j + 1) % n]
                    var d_pa = _dist(distance, n, p, a)
                    var d_bq = _dist(distance, n, b, q)
                    var d_pb = _dist(distance, n, p, b)
                    var d_aq = _dist(distance, n, a, q)
                    var correction = skew[j] - skew[i]
                    var delta = d_pb + d_aq - d_pa - d_bq + correction
                    var scale = d_pa
                    if d_bq > scale:
                        scale = d_bq
                    if d_pb > scale:
                        scale = d_pb
                    if d_aq > scale:
                        scale = d_aq
                    if fabs(correction) > scale:
                        scale = fabs(correction)
                    if delta >= -_move_tol(scale):
                        continue
                    if best_kind < 0 or delta < best_delta:
                        best_delta = delta
                        best_kind = 0
                        best_i = i
                        best_j = j

        if use_or_opt and n >= 4 and not cut:
            var seg_cap = max_segment
            if seg_cap > n - 2:
                seg_cap = n - 2
            for seg_len in range(1, seg_cap + 1):
                if cut:
                    break
                for i in range(1, n - seg_len + 1):
                    if work <= 0:
                        cut = True
                        break
                    var p = order[i - 1]
                    var a = order[i]
                    var b = order[i + seg_len - 1]
                    var q = order[(i + seg_len) % n]
                    var d_pa = _dist(distance, n, p, a)
                    var d_bq = _dist(distance, n, b, q)
                    var d_pq = _dist(distance, n, p, q)
                    for k in range(n):
                        if k >= i - 1 and k <= i + seg_len - 1:
                            continue
                        evaluated += 1
                        work -= 1
                        var u = order[k]
                        var v = order[(k + 1) % n]
                        var d_uv = _dist(distance, n, u, v)
                        var d_ua = _dist(distance, n, u, a)
                        var d_bv = _dist(distance, n, b, v)
                        var delta = d_pq + d_ua + d_bv - d_pa - d_bq - d_uv
                        var scale = d_pa
                        if d_bq > scale:
                            scale = d_bq
                        if d_pq > scale:
                            scale = d_pq
                        if d_uv > scale:
                            scale = d_uv
                        if d_ua > scale:
                            scale = d_ua
                        if d_bv > scale:
                            scale = d_bv
                        if delta >= -_move_tol(scale):
                            continue
                        if best_kind < 0 or delta < best_delta:
                            best_delta = delta
                            best_kind = 1
                            best_i = i
                            best_j = seg_len
                            best_k = k

        if cut:
            # The budget cut this scan short. Nothing is applied — a partial scan's "best"
            # move is not the neighbourhood's best — and `local_optimum` stays False because
            # a scan that did not finish cannot say no improving move exists.
            break
        if best_kind < 0:
            # "No improving move exists" is only a claim if a move was actually examined.
            # With both families disabled, or with a neighbourhood that is empty for this `n`
            # (Or-opt alone needs n >= 4), the scan is VACUOUS and `local_optimum` would
            # otherwise assert a search that never happened. `n <= 2` is the one honest
            # exception: there is exactly one tour, so it is optimal outright.
            local_opt = evaluated > 0 or n <= 2
            break

        var candidate = List[Int]()
        if best_kind == 0:
            candidate = _apply_two_opt(order, best_i, best_j)
        else:
            candidate = _apply_or_opt(order, n, best_i, best_j, best_k)
        passes += 1

        if not _is_permutation(candidate, n):
            return _SearchState(
                List[Int](), 0.0, passes, moves, evaluated, False, reeval, True
            )
        var cand_length = _length_of(nested, candidate)
        work -= n + 1
        if not _finite(cand_length):
            reeval += 1
            break
        if cand_length < length:
            order = candidate^
            length = cand_length
            moves += 1
        else:
            # The delta promised an improvement the frozen evaluator does not confirm. The
            # evaluator wins; the move is dropped and the search stops rather than looping
            # on a move it will keep re-selecting. `local_optimum` stays False, and
            # `n_reeval_rejected` says exactly why the search stopped short.
            reeval += 1
            break

    return _SearchState(
        order^, length, passes, moves, evaluated, local_opt, reeval, False
    )


def _double_bridge(
    order: List[Int], n: Int, seed: UInt64, kick_index: Int
) -> List[Int]:
    """The classic double-bridge 4-opt kick: A C B D from A B C D.

    Not reachable by any sequence of 2-opt or Or-opt moves, which is the point — it escapes
    a local optimum without undoing it.

    The three cut points are drawn from `uniform_int_keyed` at coordinates
    `(seed, stream_id("optimization.routing.kick"), 3 * kick_index + slot)`, so kick `k` is a
    pure function of `(seed, k)` and of the tour handed in — never of how many draws earlier
    kicks consumed. Drawing them NESTED (`p1 < p2 < p3` by construction) rather than drawing
    three and sorting keeps the consumption fixed at three draws and needs no rejection loop.

    `n < 4` has no double bridge; the tour comes back unchanged.
    """
    var out = List[Int]()
    if n < 4:
        for k in range(len(order)):
            out.append(order[k])
        return out^
    var stream = stream_id("optimization.routing.kick")
    var base = UInt64(kick_index) * 3
    var p1 = uniform_int_keyed(1, n - 3, seed, stream, base)
    var p2 = uniform_int_keyed(p1 + 1, n - 2, seed, stream, base + 1)
    var p3 = uniform_int_keyed(p2 + 1, n - 1, seed, stream, base + 2)
    for k in range(p1):
        out.append(order[k])
    for k in range(p2, p3):
        out.append(order[k])
    for k in range(p1, p2):
        out.append(order[k])
    for k in range(p3, n):
        out.append(order[k])
    return out^


# ── TSP: rejections and the seed ──────────────────────────────────────────────


def _no_tour(status: Int, n: Int, seed: UInt64) -> RouteTour:
    """A rejection: every list empty, every number flagged absent."""
    return RouteTour(
        status, n, False, False, 0.0, List[Int](), False, 0.0, ROUTE_ABSENT, False,
        False, False, 0, 0, 0, 0, 0, 0, 0, False, ROUTE_ABSENT, seed,
    )


def _greedy_order(
    distance: List[Float64], nested: List[List[Float64]], n: Int
) -> List[Int]:
    """The frozen `combinatorial.tsp_greedy`'s tour as an OPEN order of `n` cities.

    The frozen kernel is called unchanged and returns the closed form (`n + 1` entries,
    first and last both 0). An empty list comes back when its output is not the closed tour
    it promises — which the distance validation above already rules out, since the only path
    to a malformed output is its `1e308` `best_dist` sentinel.
    """
    var closed = tsp_greedy(nested)
    var empty = List[Int]()
    if len(closed) != n + 1:
        return empty^
    if closed[0] != ROUTE_DEPOT or closed[n] != ROUTE_DEPOT:
        return empty^
    var order = List[Int]()
    for k in range(n):
        order.append(closed[k])
    if not _is_permutation(order, n):
        return empty^
    return order^


def _tour_result(
    n: Int, state: _SearchState, seed_length: Float64,
    use_two_opt: Bool, use_or_opt: Bool, max_segment: Int,
    kicks: Int, kicks_accepted: Int, asymmetry: Float64, seed: UInt64
) -> RouteTour:
    """Package a finished search, verifying the permutation ONE more time before returning.

    The final verification is not redundant with the per-move one: it is the check that the
    value actually leaving this module is a tour, whatever path produced it.

    The status is the EXACT complement of `local_optimum` and is computed from that one field
    and nothing else. It used to be `ROUTE_OK` unless the PASS CAP was specifically the reason
    the search stopped, which made code 120 — whose name is
    `verified_local_optimum_of_the_declared_moves_not_proven_optimal` — assert a local optimum
    the struct's own `local_optimum = False` denied, on three reachable paths:
    `tsp_local_search(six_city, 6, 10, False, False, 1)` (both families disabled,
    `moves_evaluated = 0`), `tsp_or_opt(three_city, 3, 10, 1)` (the Or-opt neighbourhood is
    empty below n = 4), and any run stopped by a refused re-evaluation, which the old
    `reeval_rejected == 0` clause explicitly EXCLUDED from `ROUTE_OK_LIMIT`. A caller branches
    on the status, so one value may not carry two mutually exclusive claims; `max_passes` is
    therefore not consulted here at all, and `passes`, `moves_evaluated` and
    `n_reeval_rejected` are what say WHICH reason applied.
    """
    if state.permutation_broken or not _is_permutation(state.order, n):
        return _no_tour(ROUTE_ERR_NOT_A_PERMUTATION, n, seed)
    if not _finite(state.length):
        return _no_tour(ROUTE_ERR_DISTANCE, n, seed)
    var status = ROUTE_OK
    if not state.local_optimum:
        status = ROUTE_OK_LIMIT
    var has_seed = _finite(seed_length)
    var improvement = ROUTE_ABSENT
    if has_seed:
        improvement = seed_length - state.length
    return RouteTour(
        status, n, True, True, state.length, _closed(state.order), has_seed, seed_length,
        improvement, state.local_optimum, use_two_opt, use_or_opt, max_segment,
        state.passes, state.moves, state.evaluated, state.reeval_rejected, kicks,
        kicks_accepted, asymmetry > 0.0, asymmetry, seed,
    )


# ── TSP: public drivers ───────────────────────────────────────────────────────


def distance_matrix_check(distance: List[Float64], n: Int) -> RouteMatrixCensus:
    """The census of a distance matrix before anything is solved on it.

    Symmetry is REPORTED, never assumed: `max_asymmetry` and the cell that achieves it come
    back so a caller knows which regime its instance is in. The triangle inequality is
    tested only up to `ROUTE_TRIANGLE_MAX_N` because the test is O(n^3), and a violation is
    not an error — it changes no guarantee here and a valid permutation still comes back.

    @capability distance_matrix_check
    complexity: O(n^2)
    counts:
    - n * n == len(distance) [kernel_validated]
    @endcapability
    """
    var defect = _shape_defect(distance, n)
    if defect != ROUTE_OK:
        return RouteMatrixCensus(
            defect, n, False, ROUTE_ABSENT, -1, -1, False, 0.0, 0.0, 0, False, False,
            ROUTE_ABSENT, -1,
        )
    var bad = _distance_defect_index(distance, n)
    if bad >= 0:
        return RouteMatrixCensus(
            ROUTE_ERR_DISTANCE, n, False, ROUTE_ABSENT, -1, -1, False, 0.0, 0.0, 0,
            False, False, ROUTE_ABSENT, bad,
        )

    var worst = 0.0
    var worst_i = -1
    var worst_j = -1
    for i in range(n):
        for j in range(i + 1, n):
            var gap = fabs(distance[i * n + j] - distance[j * n + i])
            if gap > worst:
                worst = gap
                worst_i = i
                worst_j = j

    var lo = 0.0
    var hi = 0.0
    var have = False
    var zeros = 0
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            var d = distance[i * n + j]
            if d == 0.0:
                zeros += 1
            if not have:
                lo = d
                hi = d
                have = True
                continue
            if d < lo:
                lo = d
            if d > hi:
                hi = d

    var checked = n <= ROUTE_TRIANGLE_MAX_N
    var tri_ok = False
    var tri_worst = ROUTE_ABSENT
    if checked:
        tri_ok = True
        tri_worst = 0.0
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                var direct = distance[i * n + j]
                for k in range(n):
                    if k == i or k == j:
                        continue
                    var via = distance[i * n + k] + distance[k * n + j]
                    var excess = direct - via
                    if excess > _accum_tol(direct, 2) and excess > tri_worst:
                        tri_worst = excess
                        tri_ok = False
    return RouteMatrixCensus(
        ROUTE_OK, n, worst == 0.0, worst, worst_i, worst_j, have, lo, hi, zeros,
        checked, tri_ok, tri_worst, -1,
    )


def tour_check(tour: List[Int], n: Int) -> RouteTourCheck:
    """Whether `tour` is a closed tour of `n` cities: `n + 1` entries, first `n` a permutation.

    Recomputed from scratch, so it is usable on a tour this module did not produce. The
    three conditions are reported separately because "wrong length", "not closed" and "not a
    permutation" are three different mistakes at the caller.

    @capability tour_check
    complexity: O(n)
    counts:
    - n + 1 == len(tour) [kernel_validated]
    @endcapability
    """
    if n <= 0:
        return RouteTourCheck(ROUTE_ERR_SHAPE, n, False, False, False, 0, 0, -1, -1)
    if n > ROUTE_MAX_NODES:
        return RouteTourCheck(ROUTE_ERR_TOO_LARGE, n, False, False, False, 0, 0, -1, -1)
    var length_ok = len(tour) == n + 1
    if not length_ok:
        return RouteTourCheck(
            ROUTE_ERR_NOT_A_PERMUTATION, n, False, False, False, 0, 0, -1, -1
        )
    var seen = List[Int]()
    for _ in range(n):
        seen.append(0)
    var repeated = 0
    var first_defect = -1
    for k in range(n):
        var c = tour[k]
        if c < 0 or c >= n:
            if first_defect < 0:
                first_defect = k
            continue
        if seen[c] > 0:
            repeated += 1
            if first_defect < 0:
                first_defect = k
        seen[c] += 1
    var missing = 0
    var first_missing = -1
    for c in range(n):
        if seen[c] == 0:
            missing += 1
            if first_missing < 0:
                first_missing = c
    var closed = tour[n] == tour[0]
    var perm = repeated == 0 and missing == 0 and first_defect < 0
    var status = ROUTE_OK
    if not (perm and closed):
        status = ROUTE_ERR_NOT_A_PERMUTATION
    return RouteTourCheck(
        status, n, length_ok, closed, perm, repeated, missing, first_defect, first_missing
    )


def tour_length_flat(
    distance: List[Float64], n: Int, tour: List[Int]
) -> RouteScalar:
    """Length of `tour` under the flat matrix, via the frozen `tsp_tour_length`.

    The frozen kernel indexes `distances[tour[i]][tour[i+1]]` with NO range check, so a
    stray index is an uncatchable process crash there. This validates the matrix and the
    tour first and only then calls it, which is the whole reason the wrapper exists. A tour
    that is not a closed permutation has no length: `has_value` is False and `value` is
    padding, never a partial sum.

    @capability tour_length_flat
    complexity: O(n^2)
    counts:
    - n * n == len(distance) [kernel_validated]
    - n + 1 == len(tour) [kernel_validated]
    @endcapability
    """
    var defect = _shape_defect(distance, n)
    if defect != ROUTE_OK:
        return RouteScalar(defect, False, 0.0)
    var bad = _distance_defect_index(distance, n)
    if bad >= 0:
        return RouteScalar(ROUTE_ERR_DISTANCE, False, 0.0)
    var check = tour_check(tour, n)
    if check.status != ROUTE_OK:
        return RouteScalar(ROUTE_ERR_NOT_A_PERMUTATION, False, 0.0)
    var value = tsp_tour_length(_nested(distance, n), tour)
    if not _finite(value):
        return RouteScalar(ROUTE_ERR_DISTANCE, False, 0.0)
    return RouteScalar(ROUTE_OK, True, value)


def tsp_greedy_flat(distance: List[Float64], n: Int) -> RouteTour:
    """The frozen `combinatorial.tsp_greedy`, validated, verified and priced.

    A window onto the frozen kernel, not a second implementation: the tour is its own. What
    it does not do is validate its input, report a length, or say whether its output is a
    permutation — all three are here. `local_optimum` is False because nearest-neighbour is
    not a local optimum of anything, and `improvement` is 0.0 because this IS the seed.

    The status is therefore `ROUTE_OK_LIMIT` — "verified, and not a local optimum of the
    declared moves" — and NOT `ROUTE_OK`, whose name asserts a local optimum this tour has no
    claim to. The rule is the same everywhere in this file: the status is the exact complement
    of `local_optimum`, so no returned value contradicts itself.

    @capability tsp_greedy_flat
    complexity: O(n^2)
    counts:
    - n * n == len(distance) [kernel_validated]
    @endcapability
    """
    var defect = _shape_defect(distance, n)
    if defect != ROUTE_OK:
        return _no_tour(defect, n, 0)
    var bad = _distance_defect_index(distance, n)
    if bad >= 0:
        return _no_tour(ROUTE_ERR_DISTANCE, n, 0)
    var nested = _nested(distance, n)
    var order = _greedy_order(distance, nested, n)
    if len(order) != n:
        return _no_tour(ROUTE_ERR_NOT_A_PERMUTATION, n, 0)
    var length = _length_of(nested, order)
    if not _finite(length):
        return _no_tour(ROUTE_ERR_DISTANCE, n, 0)
    var asymmetry = _asymmetry(distance, n)
    return RouteTour(
        ROUTE_OK_LIMIT, n, True, True, length, _closed(order), True, length, 0.0, False,
        False, False, 0, 0, 0, 0, 0, 0, 0, asymmetry > 0.0, asymmetry, 0,
    )


def _search_driver(
    distance: List[Float64], n: Int, max_passes: Int, use_two_opt: Bool,
    use_or_opt: Bool, max_segment: Int, n_kicks: Int, seed: UInt64
) -> RouteTour:
    """Validate, seed from the frozen greedy, run the local search, then optional kicks.

    The one code path behind every TSP driver in this file, so a rejection, a tolerance and
    a tie-break cannot differ between them.

    ONE work budget covers the seed evaluation, the first local search and every kick's local
    search together, so the total cost of the call is bounded whatever `max_passes * n_kicks`
    comes to. `kicks` reports the kicks actually ATTEMPTED, which is what the budget cuts.
    """
    var defect = _shape_defect(distance, n)
    if defect != ROUTE_OK:
        return _no_tour(defect, n, seed)
    var bad = _distance_defect_index(distance, n)
    if bad >= 0:
        return _no_tour(ROUTE_ERR_DISTANCE, n, seed)

    var passes_cap = max_passes
    if passes_cap < 0:
        passes_cap = 0
    if passes_cap > ROUTE_MAX_PASSES:
        passes_cap = ROUTE_MAX_PASSES
    # Clamped to the largest segment the Or-opt neighbourhood can actually move (a segment of
    # n-1 cities leaves nowhere to reinsert it), and REPORTED clamped: `max_segment` in the
    # result must be what was searched, not what was asked for.
    var seg = max_segment
    if seg > n - 2:
        seg = n - 2
    if seg < 1:
        seg = 1
    # Each kick runs a full local search, so an unclamped `n_kicks` is a work bomb from a
    # one-integer request. The CLAMP is not what defuses it — a clamp bounds the iteration
    # count, and 65536 kicks of a full local search is still unbounded compute — the shared
    # `ROUTE_WORK_BUDGET` below is. `kicks` reports kicks actually attempted, so a budget that
    # runs out is visible as a count below the one asked for.
    var kicks = n_kicks
    if kicks < 0:
        kicks = 0
    if kicks > ROUTE_MAX_PASSES:
        kicks = ROUTE_MAX_PASSES
    if n < 4:
        kicks = 0

    var nested = _nested(distance, n)
    var order = _greedy_order(distance, nested, n)
    if len(order) != n:
        return _no_tour(ROUTE_ERR_NOT_A_PERMUTATION, n, seed)
    var asymmetry = _asymmetry(distance, n)
    var seed_length = _length_of(nested, order)
    if not _finite(seed_length):
        return _no_tour(ROUTE_ERR_DISTANCE, n, seed)

    var work = ROUTE_WORK_BUDGET
    var best = _local_search(
        distance, nested, n, order, use_two_opt, use_or_opt, seg, passes_cap,
        asymmetry > 0.0, work,
    )
    if best.permutation_broken:
        return _no_tour(ROUTE_ERR_NOT_A_PERMUTATION, n, seed)

    var accepted = 0
    var attempted = 0
    for kick in range(kicks):
        if work <= 0:
            break
        attempted += 1
        var kicked = _double_bridge(best.order, n, seed, kick)
        work -= n
        if not _is_permutation(kicked, n):
            return _no_tour(ROUTE_ERR_NOT_A_PERMUTATION, n, seed)
        var trial = _local_search(
            distance, nested, n, kicked, use_two_opt, use_or_opt, seg, passes_cap,
            asymmetry > 0.0, work,
        )
        if trial.permutation_broken:
            return _no_tour(ROUTE_ERR_NOT_A_PERMUTATION, n, seed)
        # STRICT improvement only, so the incumbent wins a tie and the whole walk is a
        # deterministic function of (instance, seed, kicks).
        if trial.length < best.length:
            var carried_passes = best.passes + trial.passes
            var carried_moves = best.moves + trial.moves
            var carried_eval = best.evaluated + trial.evaluated
            var carried_reeval = best.reeval_rejected + trial.reeval_rejected
            best = _SearchState(
                trial.order.copy(), trial.length, carried_passes, carried_moves,
                carried_eval,
                trial.local_optimum, carried_reeval, False,
            )
            accepted += 1
        else:
            best = _SearchState(
                best.order.copy(), best.length, best.passes + trial.passes,
                best.moves + trial.moves, best.evaluated + trial.evaluated,
                best.local_optimum, best.reeval_rejected + trial.reeval_rejected, False,
            )

    return _tour_result(
        n, best, seed_length, use_two_opt, use_or_opt, seg, attempted,
        accepted, asymmetry, seed,
    )


def tsp_two_opt(distance: List[Float64], n: Int, max_passes: Int) -> RouteTour:
    """2-opt local search seeded by the frozen greedy. Segment-reversal moves only.

    On a symmetric matrix a 2-opt local optimum has no crossing edges, so on points in
    convex position it is the hull order and therefore the exact optimum — but that is a
    property of THAT instance class, not a guarantee this driver makes. `local_optimum`
    means "no improving 2-opt move exists", and nothing more.

    @capability tsp_two_opt
    complexity: O(max_passes * n^2)
    counts:
    - n * n == len(distance) [kernel_validated]
    @endcapability
    """
    return _search_driver(distance, n, max_passes, True, False, 1, 0, 0)


def tsp_or_opt(
    distance: List[Float64], n: Int, max_passes: Int, max_segment: Int
) -> RouteTour:
    """Or-opt local search seeded by the frozen greedy. Segment RELOCATION moves only.

    Segments of 1..`max_segment` consecutive cities are moved elsewhere keeping their
    direction, so the delta is exact for an asymmetric matrix as well. `max_segment` is
    clamped into `[1, n - 2]` — a longer segment has nowhere to be reinserted — and the
    effective value is reported back rather than the value asked for.

    EXACTLY what `local_optimum` covers here, because a neighbourhood claim is only as good as
    its statement: a segment that spans the start city is NOT enumerated. Every segment lies
    inside positions `1..n-1` of the tour as written. That exclusion is WLOG for 2-opt (a
    reversal spanning the start is the complementary reversal, which is enumerated) but it is
    NOT WLOG for relocation, because relocating an arc splits its complement in two and is
    therefore not a relocation of the complement. So a `local_optimum` from an Or-opt run
    means "no improving relocation of a segment not spanning city 0", and no more than that.
    The reversed-insertion variant of Or-opt is also absent rather than approximated.

    @capability tsp_or_opt
    complexity: O(max_passes * n^2 * max_segment)
    counts:
    - n * n == len(distance) [kernel_validated]
    @endcapability
    """
    return _search_driver(distance, n, max_passes, False, True, max_segment, 0, 0)


def tsp_local_search(
    distance: List[Float64], n: Int, max_passes: Int, use_two_opt: Bool,
    use_or_opt: Bool, max_segment: Int
) -> RouteTour:
    """2-opt and Or-opt together, best-improvement, seeded by the frozen greedy.

    With both move families disabled this returns the frozen greedy's tour with
    `local_optimum` False — an honest "nothing was searched" rather than a silent no-op.

    @capability tsp_local_search
    complexity: O(max_passes * n^2 * max_segment)
    counts:
    - n * n == len(distance) [kernel_validated]
    @endcapability
    """
    return _search_driver(
        distance, n, max_passes, use_two_opt, use_or_opt, max_segment, 0, 0
    )


def tsp_iterated_local_search(
    distance: List[Float64], n: Int, max_passes: Int, max_segment: Int,
    n_kicks: Int, seed: UInt64
) -> RouteTour:
    """Iterated local search: 2-opt + Or-opt, then `n_kicks` double-bridge restarts.

    Deterministic in the strong sense — the whole walk is a pure function of
    `(distance, n, max_passes, max_segment, n_kicks, seed)`. Kick `k` draws its three cut
    points at counter coordinates `(seed, stream_id("optimization.routing.kick"),
    3k .. 3k+2)`, so it does not depend on how many draws the search consumed before it,
    and a kicked tour replaces the incumbent only on a strict improvement.

    The same seed gives a bit-identical tour; a different seed gives a different walk. Still
    a heuristic: there is no proven-optimal flag here either.

    @capability tsp_iterated_local_search
    complexity: O(n_kicks * max_passes * n^2)
    counts:
    - n * n == len(distance) [kernel_validated]
    @endcapability
    """
    return _search_driver(
        distance, n, max_passes, True, True, max_segment, n_kicks, seed
    )


def tsp_perturb_double_bridge(
    distance: List[Float64], n: Int, tour: List[Int], seed: UInt64, kick_index: Int
) -> RouteTour:
    """One double-bridge kick applied to `tour`, priced. The perturbation, exposed.

    Public so the determinism contract is testable on its own: kick `k` under one seed is
    bit-identical every time, and under a different seed it is a different tour. The result
    is a verified permutation, `local_optimum` is False (a kick is a perturbation, not a
    search), and `improvement` is negative when the kick made the tour worse — which is
    normally what a kick does.

    `tour` may start at any city: a rotation of a cycle is the same cycle, and the returned
    tour keeps whatever start the caller's had. `kicks` is 1 when a kick was applied and 0
    when `n < 4`, where no double bridge exists and the tour comes back untouched.

    The status is `ROUTE_OK_LIMIT`, matching `local_optimum = False`: a perturbation searched
    nothing, so it cannot be handed the status whose name asserts a local optimum. `ROUTE_OK`
    from this function would have been the same self-contradiction `_tour_result` used to
    produce.

    @capability tsp_perturb_double_bridge
    complexity: O(n^2)
    counts:
    - n * n == len(distance) [kernel_validated]
    - n + 1 == len(tour) [kernel_validated]
    @endcapability
    """
    var defect = _shape_defect(distance, n)
    if defect != ROUTE_OK:
        return _no_tour(defect, n, seed)
    var bad = _distance_defect_index(distance, n)
    if bad >= 0:
        return _no_tour(ROUTE_ERR_DISTANCE, n, seed)
    var check = tour_check(tour, n)
    if check.status != ROUTE_OK:
        return _no_tour(ROUTE_ERR_NOT_A_PERMUTATION, n, seed)
    if kick_index < 0:
        return _no_tour(ROUTE_ERR_INSTANCE, n, seed)
    var order = List[Int]()
    for k in range(n):
        order.append(tour[k])
    var nested = _nested(distance, n)
    var before = _length_of(nested, order)
    var kicked = _double_bridge(order, n, seed, kick_index)
    if not _is_permutation(kicked, n):
        return _no_tour(ROUTE_ERR_NOT_A_PERMUTATION, n, seed)
    var after = _length_of(nested, kicked)
    if not (_finite(before) and _finite(after)):
        return _no_tour(ROUTE_ERR_DISTANCE, n, seed)
    var asymmetry = _asymmetry(distance, n)
    # `n < 4` has no double bridge at all, so no kick was applied and `kicks` must say 0
    # rather than 1 — the tour came back untouched and the caller has to be able to tell.
    var applied = 1
    if n < 4:
        applied = 0
    return RouteTour(
        ROUTE_OK_LIMIT, n, True, True, after, _closed(kicked), True, before,
        before - after, False, False, False, 0, 0, 0, 0, 0, applied, 0,
        asymmetry > 0.0, asymmetry, seed,
    )


# ── vehicle routing: instance validation ──────────────────────────────────────


def _instance_defect(
    distance: List[Float64], n: Int, demand: List[Float64], capacity: Float64,
    n_vehicles: Int, ready: List[Float64], due: List[Float64],
    service: List[Float64], windowed: Bool
) -> Int:
    """Everything that must hold before a route is built. Order matters for the code.

    `demand[0]` must be 0.0 and `service[0]` must be 0.0: the depot is not a customer, and
    silently ignoring a nonzero value there would make a caller's typo invisible.
    """
    var shape = _shape_defect(distance, n)
    if shape != ROUTE_OK:
        return shape
    if _distance_defect_index(distance, n) >= 0:
        return ROUTE_ERR_DISTANCE
    if len(demand) != n:
        return ROUTE_ERR_LENGTH_MISMATCH
    if windowed and (len(ready) != n or len(due) != n or len(service) != n):
        return ROUTE_ERR_LENGTH_MISMATCH
    if n_vehicles <= 0 or n_vehicles > ROUTE_MAX_NODES:
        return ROUTE_ERR_INSTANCE
    if not _finite(capacity) or capacity <= 0.0 or capacity > ROUTE_MAX_DISTANCE:
        return ROUTE_ERR_INSTANCE
    if demand[ROUTE_DEPOT] != 0.0:
        return ROUTE_ERR_INSTANCE
    for c in range(n):
        var q = demand[c]
        if not _finite(q) or q < 0.0 or q > ROUTE_MAX_DISTANCE:
            return ROUTE_ERR_INSTANCE
    if windowed:
        if service[ROUTE_DEPOT] != 0.0:
            return ROUTE_ERR_INSTANCE
        for c in range(n):
            var r = ready[c]
            var d = due[c]
            var s = service[c]
            if not (_finite(r) and _finite(d) and _finite(s)):
                return ROUTE_ERR_INSTANCE
            if r < 0.0 or d < 0.0 or s < 0.0:
                return ROUTE_ERR_INSTANCE
            if r > ROUTE_MAX_DISTANCE or d > ROUTE_MAX_DISTANCE:
                return ROUTE_ERR_INSTANCE
            if s > ROUTE_MAX_DISTANCE:
                return ROUTE_ERR_INSTANCE
            if r > d:
                return ROUTE_ERR_INSTANCE
    return ROUTE_OK


def _lower_bound_vehicles(demand: List[Float64], n: Int, capacity: Float64) -> Int:
    """`ceil(total demand / capacity)` — a true lower bound on vehicles, clamped.

    Every feasible routing induces a feasible packing of the demands into capacity-sized
    bins, and no packing beats the load ratio, so this bounds the vehicle count from below
    for the routing problem too. Time windows can only push the true number up.

    The ratio is nudged DOWN by its own rounding budget before the ceiling, and that is not a
    decoration. The total is a sum of up to `n` demands, so it carries up to ~n ulps of its
    own magnitude and the quotient inherits that relatively. Ceiling a ratio that rounding
    pushed one ulp above an integer turns a FEASIBLE instance into a proof of infeasibility.
    Measured, before the nudge existed: demands 0.1 and 0.2 against a capacity of 0.3 sum to
    0.30000000000000004, whose ratio is 1.0000000000000002, whose ceiling is 2 — and `2 > 1`
    came back as `ROUTE_INFEASIBLE_PROVEN` for an instance one vehicle serves exactly, while
    `_eval_route` (whose tolerance is per-route and DBL_EPSILON-sized) accepted the very same
    load. One invariant must not be enforced at two strengths inside one module.

    The nudge can only ever UNDERSTATE the bound, and an understated bound merely misses a
    proof — the search then reports `no_solution_found`, which claims nothing. That is the
    safe direction for a value whose whole job is to justify refusing an answer.

    The clamp is what keeps `Int()` safe: `_ceil_f` is total over every finite Float64, but
    `Int()` on a magnitude past the integer grid is poison rather than truncation, so the
    conversion happens only after the value is known to be small. `ROUTE_MAX_NODES + 1`
    means "more than any admissible fleet", which is all a caller can act on anyway.
    """
    var loads = List[Float64]()
    for c in range(n):
        loads.append(demand[c])
    var total = kahan_sum(loads)
    if not _finite(total) or total <= 0.0:
        return 0
    var ratio = total / capacity
    if not _finite(ratio) or ratio > Float64(ROUTE_MAX_NODES + 1):
        return ROUTE_MAX_NODES + 1
    var bound = _ceil_f(ratio - _accum_tol(ratio, n))
    if not _finite(bound) or bound > Float64(ROUTE_MAX_NODES + 1):
        return ROUTE_MAX_NODES + 1
    if bound < 1.0:
        return 1
    return Int(bound)


def _min_arc_into(distance: List[Float64], n: Int, c: Int) -> Float64:
    """`min` over every `p != c` of `d[p][c]`. 0.0 when there is no other node."""
    var best = 0.0
    var have = False
    for p in range(n):
        if p == c:
            continue
        var w = _dist(distance, n, p, c)
        if not have or w < best:
            best = w
            have = True
    return best


def _min_arc_out_of(distance: List[Float64], n: Int, c: Int) -> Float64:
    """`min` over every `q != c` of `d[c][q]`. 0.0 when there is no other node."""
    var best = 0.0
    var have = False
    for q in range(n):
        if q == c:
            continue
        var w = _dist(distance, n, c, q)
        if not have or w < best:
            best = w
            have = True
    return best


def _earliest_arrival_bound(
    distance: List[Float64], n: Int, c: Int, depot_out: Float64
) -> Float64:
    """Sound lower bound on the travel time from leaving the depot to reaching `c`.

    THE DIRECT ARC IS NOT A LOWER BOUND, and using it as one produced FALSE PROOFS of
    infeasibility. Measured over 768 randomised window instances: 7 of them were reported
    `ROUTE_INFEASIBLE_PROVEN` while an exhaustive enumeration found a feasible routing. The
    cause is that `d[0][c]` is only the cheapest way to reach `c` when the triangle inequality
    holds — and this module deliberately accepts matrices that violate it, `tsp_or_opt` and
    `distance_matrix_check` both say so, and a detour `0 -> p -> c` can then be strictly
    faster. A proof that assumes an unstated property of the input is not a proof.

    What IS sound, for every matrix, by cases on the position of `c` in its route:

      * `c` is the FIRST stop: the travel time is exactly `d[0][c]`;
      * `c` is not first: the route's first leg leaves the depot (>= `depot_out`) and its last
        leg enters `c` (>= `min_arc_into(c)`), and those are two DISTINCT legs, with every
        other leg and every service time non-negative.

    So the minimum of the two is a lower bound. Waiting for a `ready` time can only push the
    real arrival later, so relaxing it away keeps the bound valid. This is weaker than a true
    shortest path — which would need the whole `n^2` edge list materialised for the frozen
    `graph.weighted.shortest_path_dijkstra`, several hundred MB at this module's node ceiling
    — and being weaker only ever costs a PROOF, never correctness: an unproven instance falls
    through to the search and is reported as `no_solution_found`, which claims nothing.
    """
    var direct = _dist(distance, n, ROUTE_DEPOT, c)
    var detour = depot_out + _min_arc_into(distance, n, c)
    if direct < detour:
        return direct
    return detour


def _earliest_return_bound(
    distance: List[Float64], n: Int, c: Int, depot_in: Float64
) -> Float64:
    """Sound lower bound on the travel time from finishing service at `c` to the depot.

    The mirror of `_earliest_arrival_bound` and sound for the same reason: either `c` is the
    LAST stop and the leg is exactly `d[c][0]`, or it is not, in which case the route leaves
    `c` (>= `min_arc_out_of(c)`) and later enters the depot (>= `depot_in`) on two distinct
    legs.
    """
    var direct = _dist(distance, n, c, ROUTE_DEPOT)
    var detour = _min_arc_out_of(distance, n, c) + depot_in
    if direct < detour:
        return direct
    return detour


def _customer_demands(demand: List[Float64], n: Int) -> List[Float64]:
    """Demands of customers `1..n-1`, which is what the frozen bin packers take."""
    var out = List[Float64]()
    for c in range(1, n):
        out.append(demand[c])
    return out^


def vrp_vehicle_bound(demand: List[Float64], capacity: Float64) -> RouteVehicleBound:
    """Vehicle bounds for a demand list under one capacity, from the frozen bin packers.

    `demand` here is the CUSTOMER list — no depot entry — because that is what a packing is
    over. `lower_bound` is the load ratio and is the only number used to prove
    infeasibility; `ffd_bins` and `ff_bins` are the frozen `bin_packing_first_fit_decreasing`
    and `bin_packing_first_fit` counts, which are feasible packings and therefore UPPER
    bounds on the relaxation's optimum. Reporting all three is what lets a caller tell a bad
    answer from a hard instance.

    A demand above the capacity makes the instance infeasible, so the status says so and no
    bound is offered: the vehicle count of an instance with no solution does not exist.
    """
    for k in range(len(demand)):
        var q = demand[k]
        if not _finite(q) or q < 0.0 or q > ROUTE_MAX_DISTANCE:
            return RouteVehicleBound(
                ROUTE_ERR_INSTANCE, len(demand), False, 0, 0, 0, 0.0, 0.0, 0, k
            )
    if not _finite(capacity) or capacity <= 0.0 or capacity > ROUTE_MAX_DISTANCE:
        return RouteVehicleBound(
            ROUTE_ERR_INSTANCE, len(demand), False, 0, 0, 0, 0.0, 0.0, 0, -1
        )
    if len(demand) > ROUTE_MAX_NODES:
        return RouteVehicleBound(
            ROUTE_ERR_TOO_LARGE, len(demand), False, 0, 0, 0, 0.0, 0.0, 0, -1
        )
    var total = kahan_sum(demand)
    var biggest = 0.0
    var oversized = 0
    var first_over = -1
    for k in range(len(demand)):
        if demand[k] > biggest:
            biggest = demand[k]
        if demand[k] - capacity > _pair_tol(demand[k], capacity, 1):
            oversized += 1
            if first_over < 0:
                first_over = k
    if oversized > 0:
        return RouteVehicleBound(
            ROUTE_INFEASIBLE_PROVEN, len(demand), False, 0, 0, 0, total, biggest,
            oversized, first_over,
        )
    var ffd = bin_packing_first_fit_decreasing(demand, capacity)
    var ff = bin_packing_first_fit(demand, capacity)
    var padded = List[Float64]()
    padded.append(0.0)
    for k in range(len(demand)):
        padded.append(demand[k])
    var lb = _lower_bound_vehicles(padded, len(padded), capacity)
    return RouteVehicleBound(
        ROUTE_OK, len(demand), True, lb, ffd, ff, total, biggest, 0, -1
    )


# ── vehicle routing: evaluating one route ─────────────────────────────────────


def _eval_route(
    distance: List[Float64], n: Int, demand: List[Float64], capacity: Float64,
    ready: List[Float64], due: List[Float64], service: List[Float64],
    windowed: Bool, route: List[Int], mut work: Int
) -> _RouteEval:
    """Load, distance, return time and every violation of ONE vehicle's sequence.

    Capacity and windows are HARD: `feasible` is False on any violation, and the magnitudes
    come back with it so a caller sees how badly rather than just that. The scan does not
    exit early — a late arrival still departs at `arrival + service`, so the rest of the
    route is evaluated on the real timeline and `max_lateness` covers every stop.

    An empty route is a vehicle that stays at the depot: zero load, zero distance, feasible.
    Charging it `d[0][0]` would invent a cost for a vehicle that never moved.

    Both tolerances are per-quantity and `ROUTE_DBL_EPSILON`-sized: a window is judged
    against the magnitude of the arrival time and the due time being compared, over the
    number of legs that formed the arrival, and a load against the magnitude of the load and
    the capacity. Nothing is judged against a sum over the instance.

    This is the elementary unit of VRP work and it is what the shared budget is charged for:
    `len(route) + 2`, because the scan walks the route once and allocates two arrays of that
    length. It NEVER truncates on an exhausted budget — a partial evaluation would report
    `feasible` from an unfinished check — it only charges, and the callers that own loops
    decide what to stop.
    """
    var m = len(route)
    work -= m + 2
    if m == 0:
        var start_t = 0.0
        if windowed:
            start_t = ready[ROUTE_DEPOT]
        return _RouteEval(True, 0.0, 0.0, start_t, 0.0, 0.0, 0, 0, -1, -1)

    var loads = List[Float64]()
    var legs = List[Float64]()
    var feasible = True
    var worst_late = 0.0
    var n_late = 0
    var defect_stop = -1
    var defect_node = -1
    var t = 0.0
    if windowed:
        t = ready[ROUTE_DEPOT]
    var prev = ROUTE_DEPOT

    for s in range(m):
        var c = route[s]
        var leg = _dist(distance, n, prev, c)
        legs.append(leg)
        loads.append(demand[c])
        if windowed:
            t += leg
            if t < ready[c]:
                t = ready[c]
            var late = t - due[c]
            if late > _pair_tol(t, due[c], s + 1):
                feasible = False
                n_late += 1
                if late > worst_late:
                    worst_late = late
                if defect_stop < 0:
                    defect_stop = s
                    defect_node = c
            t += service[c]
        prev = c

    var back = _dist(distance, n, prev, ROUTE_DEPOT)
    legs.append(back)
    if windowed:
        t += back
        var late = t - due[ROUTE_DEPOT]
        if late > _pair_tol(t, due[ROUTE_DEPOT], m + 1):
            feasible = False
            n_late += 1
            if late > worst_late:
                worst_late = late
            if defect_stop < 0:
                # The return leg is not a stop in the sequence, so it is named by the
                # position one past the end and by the depot.
                defect_stop = m
                defect_node = ROUTE_DEPOT

    var load = kahan_sum(loads)
    var dist_total = kahan_sum(legs)
    var excess = load - capacity
    var n_over = 0
    if excess > _pair_tol(load, capacity, m):
        feasible = False
        n_over = 1
        if defect_stop < 0:
            defect_stop = m - 1
            defect_node = route[m - 1]
    else:
        excess = 0.0
    if not (_finite(load) and _finite(dist_total) and _finite(t)):
        return _RouteEval(
            False, 0.0, 0.0, 0.0, ROUTE_ABSENT, ROUTE_ABSENT, 0, 0, 0, route[0]
        )
    return _RouteEval(
        feasible, load, dist_total, t, excess, worst_late, n_over, n_late, defect_stop,
        defect_node,
    )


def _audit_core(
    distance: List[Float64], n: Int, demand: List[Float64], capacity: Float64,
    ready: List[Float64], due: List[Float64], service: List[Float64],
    windowed: Bool, stops: List[Int], route_start: List[Int], mut work: Int
) -> RouteAudit:
    """The verdict on a flat routing. ONE implementation, used by the solver and the public
    checker alike, so an answer this module returns is verified by exactly the code a caller
    would run on it.

    Charges the shared work budget but NEVER stops early on it: its own cost is
    O(len(stops) + len(route_start) + n), all three payload-bounded, and a verification that
    quit halfway would return `feasible` for conditions it did not check. The charge is here so
    the solver's restart loop pays for the audits it runs.
    """
    var n_vehicles = len(route_start) - 1
    var empty_f = List[Float64]()
    if len(route_start) < 1 or route_start[0] != 0:
        return RouteAudit(
            ROUTE_ERR_LENGTH_MISMATCH, n, n - 1, 0, windowed, False, False, 0, 0, 0,
            False, 0.0, empty_f.copy(), empty_f.copy(), empty_f.copy(), 0, 0, ROUTE_ABSENT, ROUTE_ABSENT,
            -1, -1, -1,
        )
    if route_start[len(route_start) - 1] != len(stops):
        return RouteAudit(
            ROUTE_ERR_LENGTH_MISMATCH, n, n - 1, n_vehicles, windowed, False, False, 0,
            0, 0, False, 0.0, empty_f.copy(), empty_f.copy(), empty_f.copy(), 0, 0, ROUTE_ABSENT,
            ROUTE_ABSENT, -1, -1, -1,
        )
    for v in range(len(route_start) - 1):
        if route_start[v + 1] < route_start[v]:
            return RouteAudit(
                ROUTE_ERR_LENGTH_MISMATCH, n, n - 1, n_vehicles, windowed, False, False,
                0, 0, 0, False, 0.0, empty_f.copy(), empty_f.copy(), empty_f.copy(), 0, 0, ROUTE_ABSENT,
                ROUTE_ABSENT, v, -1, -1,
            )
    for k in range(len(stops)):
        var c = stops[k]
        if c <= ROUTE_DEPOT or c >= n:
            return RouteAudit(
                ROUTE_ERR_NOT_A_PERMUTATION, n, n - 1, n_vehicles, windowed, False,
                False, 0, 0, 0, False, 0.0, empty_f.copy(), empty_f.copy(), empty_f.copy(), 0, 0,
                ROUTE_ABSENT, ROUTE_ABSENT, -1, k, c,
            )

    var visits = List[Int]()
    for _ in range(n):
        visits.append(0)
    for k in range(len(stops)):
        visits[stops[k]] += 1
    var duplicated = 0
    var missing = 0
    var served = 0
    for c in range(1, n):
        if visits[c] == 0:
            missing += 1
        else:
            served += 1
            if visits[c] > 1:
                duplicated += visits[c] - 1

    var loads = List[Float64]()
    var dists = List[Float64]()
    var returns = List[Float64]()
    var feasible = True
    var n_cap = 0
    var n_win = 0
    var worst_excess = 0.0
    var worst_late = 0.0
    var defect_vehicle = -1
    var defect_stop = -1
    var defect_node = -1
    var any_unmeasurable = False
    for v in range(n_vehicles):
        var route = List[Int]()
        for k in range(route_start[v], route_start[v + 1]):
            route.append(stops[k])
        var ev = _eval_route(
            distance, n, demand, capacity, ready, due, service, windowed, route, work
        )
        loads.append(ev.load)
        dists.append(ev.dist)
        returns.append(ev.end_time)
        if ev.cap_excess == ROUTE_ABSENT:
            # `_eval_route` could not form this route's load, distance or timeline at all,
            # so the 0.0 it padded with is not this route's distance and the fleet total
            # cannot be formed from it either. Absent, not zero.
            any_unmeasurable = True
        n_cap += ev.n_cap_violations
        n_win += ev.n_window_violations
        if ev.cap_excess > worst_excess:
            worst_excess = ev.cap_excess
        if ev.lateness > worst_late:
            worst_late = ev.lateness
        if not ev.feasible:
            feasible = False
            if defect_vehicle < 0:
                defect_vehicle = v
                defect_stop = ev.defect_stop
                defect_node = ev.defect_node

    var all_served = missing == 0 and duplicated == 0
    if not all_served:
        feasible = False
    if any_unmeasurable:
        feasible = False
    var total = kahan_sum(dists)
    var has_total = _finite(total) and not any_unmeasurable
    if not has_total:
        total = 0.0
    return RouteAudit(
        ROUTE_OK, n, n - 1, n_vehicles, windowed, feasible, all_served, served,
        duplicated, missing, has_total, total, loads^, dists^, returns^, n_cap, n_win,
        worst_excess, worst_late, defect_vehicle, defect_stop, defect_node,
    )


def vrp_check(
    distance: List[Float64], n: Int, demand: List[Float64], capacity: Float64,
    ready: List[Float64], due: List[Float64], service: List[Float64],
    stops: List[Int], route_start: List[Int]
) -> RouteAudit:
    """Audit a routing somebody else produced: capacity, every window, every customer once.

    Node 0 is the depot; `stops` is the concatenation of the vehicles' customer sequences
    and `route_start` its `n_vehicles + 1` offsets. Time windows are applied when `ready`,
    `due` and `service` all have `n` entries, and skipped when all three are empty — a
    capacity-only routing has no windows to miss, and inventing `[0, +inf)` windows would
    put a number where there is none.

    Structural breaks are rejected (a stop outside `[1, n)`, the depot as a stop, a
    `route_start` that is not a non-decreasing cover of `stops`); everything semantic is
    reported with `feasible == False` and the defect indices. `feasible` requires every
    customer served EXACTLY once: a routing that visits a customer twice is not a routing.

    @capability vrp_check
    complexity: O(n^2)
    counts:
    - n * n == len(distance) [kernel_validated]
    - n == len(demand) [kernel_validated]
    @endcapability
    """
    var windowed = len(ready) == n and len(due) == n and len(service) == n
    var no_windows = len(ready) == 0 and len(due) == 0 and len(service) == 0
    var empty_f = List[Float64]()
    if not (windowed or no_windows):
        return RouteAudit(
            ROUTE_ERR_LENGTH_MISMATCH, n, 0, 0, False, False, False, 0, 0, 0, False,
            0.0, empty_f.copy(), empty_f.copy(), empty_f.copy(), 0, 0, ROUTE_ABSENT, ROUTE_ABSENT, -1, -1, -1,
        )
    var defect = _instance_defect(
        distance, n, demand, capacity, 1, ready, due, service, windowed
    )
    if defect != ROUTE_OK:
        return RouteAudit(
            defect, n, 0, 0, windowed, False, False, 0, 0, 0, False, 0.0,
            empty_f.copy(), empty_f.copy(), empty_f.copy(), 0, 0, ROUTE_ABSENT,
            ROUTE_ABSENT, -1, -1, -1,
        )
    var work = ROUTE_WORK_BUDGET
    return _audit_core(
        distance, n, demand, capacity, ready, due, service, windowed, stops, route_start,
        work,
    )


# ── vehicle routing: construction and improvement ─────────────────────────────


def _insert_at(route: List[Int], pos: Int, city: Int) -> List[Int]:
    var out = List[Int]()
    for k in range(pos):
        out.append(route[k])
    out.append(city)
    for k in range(pos, len(route)):
        out.append(route[k])
    return out^


def _remove_at(route: List[Int], pos: Int) -> List[Int]:
    var out = List[Int]()
    for k in range(len(route)):
        if k == pos:
            continue
        out.append(route[k])
    return out^


def _reverse_span(route: List[Int], i: Int, j: Int) -> List[Int]:
    var out = List[Int]()
    for k in range(len(route)):
        out.append(route[k])
    var lo = i
    var hi = j
    while lo < hi:
        var tmp = out[lo]
        out[lo] = out[hi]
        out[hi] = tmp
        lo += 1
        hi -= 1
    return out^


def _insertion_order(
    demand: List[Float64], n: Int, due: List[Float64], windowed: Bool,
    restart: Int, seed: UInt64, mut work: Int
) -> List[Int]:
    """The order customers are offered to the construction, stated so it reproduces.

    Restart 0 is deterministic: by due time ascending then customer index ascending when
    there are windows (the tightest deadline first, which is what makes a window-feasible
    insertion likely to exist), by demand descending then index ascending when there are not
    — the same order the frozen `bin_packing_first_fit_decreasing` bound assumes, so the
    construction and the bound are talking about the same packing.

    Restarts 1.. use `permutation_keyed(n_customers, seed,
    stream_id("optimization.routing.insertion"), restart * n_customers)`, a counter-based
    draw: the permutation for restart `r` is a pure function of `(seed, r)` and does not
    depend on how many draws the earlier restarts consumed.

    The selection sort below carries indices, which `sorting.insertion_sort` cannot: it
    takes a bare `List[Float64]` and returns no permutation, so the pairing between a key
    and its customer would be lost. That is a missing capability, not a kernel to bypass.

    The selection sort is O(m^2), which is one restart's cost before a single route is built, so
    it is charged against the shared budget too — otherwise a large `n_restarts` buys unbounded
    time in this function alone. It always produces the WHOLE order: a truncated order is not a
    permutation of the customers and would silently drop them, so the budget is charged here and
    enforced by the caller's restart loop.
    """
    var out = List[Int]()
    var m = n - 1
    if m <= 0:
        return out^
    if restart > 0:
        var stream = stream_id("optimization.routing.insertion")
        var draw = UInt64(restart) * UInt64(m)
        var perm = permutation_keyed(m, seed, stream, draw)
        work -= m + 1
        for k in range(len(perm)):
            out.append(perm[k] + 1)
        return out^
    work -= m * m + 1
    var taken = List[Bool]()
    for _ in range(m):
        taken.append(False)
    for _ in range(m):
        var best = -1
        var best_key = 0.0
        for k in range(m):
            if taken[k]:
                continue
            var key = -demand[k + 1]
            if windowed:
                key = due[k + 1]
            if best < 0 or key < best_key:
                best = k
                best_key = key
        taken[best] = True
        out.append(best + 1)
    return out^


def _build_routes(
    distance: List[Float64], n: Int, demand: List[Float64], capacity: Float64,
    ready: List[Float64], due: List[Float64], service: List[Float64],
    windowed: Bool, n_vehicles: Int, order: List[Int], mut work: Int
) -> List[List[Int]]:
    """Sequential cheapest-FEASIBLE insertion. Empty list of routes when it fails.

    Every candidate insertion is scored by re-evaluating the WHOLE affected route, not by a
    three-edge delta: with time windows an insertion shifts arrival times and waiting
    downstream, so a local delta is not the change in feasibility and often not even the
    change in distance. Exactness costs one O(route) pass per candidate and is worth it.

    Ties go to the lowest vehicle index then the earliest position, and a new vehicle is
    opened only when no existing route can take the customer feasibly. Failure returns NO
    routes, which the caller turns into `ROUTE_NO_SOLUTION_FOUND` — not a proof of
    infeasibility, and not a partial answer dressed as a solution.

    This is the O(n^3) half of one restart — every customer against every position of every
    route, each scored by a full `_eval_route` — so it is charged against the shared budget and
    an exhausted budget counts as FAILURE. A construction that stopped early has not placed
    every customer, and a set of routes missing customers is not a solution; returning no routes
    is the only honest outcome, and the caller's restart loop then stops.
    """
    var routes = List[List[Int]]()
    var route_dist = List[Float64]()
    var failed = False
    for idx in range(len(order)):
        if work <= 0:
            failed = True
            break
        var c = order[idx]
        var best_v = -1
        var best_pos = -1
        var best_delta = 0.0
        for v in range(len(routes)):
            for pos in range(len(routes[v]) + 1):
                var candidate = _insert_at(routes[v], pos, c)
                var ev = _eval_route(
                    distance, n, demand, capacity, ready, due, service, windowed,
                    candidate, work,
                )
                if not ev.feasible:
                    continue
                var delta = ev.dist - route_dist[v]
                if best_v < 0 or delta < best_delta:
                    best_v = v
                    best_pos = pos
                    best_delta = delta
        if best_v >= 0:
            var updated = _insert_at(routes[best_v], best_pos, c)
            var ev2 = _eval_route(
                distance, n, demand, capacity, ready, due, service, windowed, updated,
                work,
            )
            routes[best_v] = updated.copy()
            route_dist[best_v] = ev2.dist
            continue
        if len(routes) >= n_vehicles:
            failed = True
            break
        var fresh = List[Int]()
        fresh.append(c)
        var ev3 = _eval_route(
            distance, n, demand, capacity, ready, due, service, windowed, fresh, work
        )
        if not ev3.feasible:
            failed = True
            break
        routes.append(fresh^)
        route_dist.append(ev3.dist)
    if failed:
        return List[List[Int]]()
    return routes^


def _improve_routes(
    distance: List[Float64], n: Int, demand: List[Float64], capacity: Float64,
    ready: List[Float64], due: List[Float64], service: List[Float64],
    windowed: Bool, routes_in: List[List[Int]], max_passes: Int, mut work: Int
) -> _ImproveResult:
    """Best-improvement intra-route 2-opt plus relocation, feasibility enforced throughout.

    Every candidate is re-evaluated IN FULL — both affected routes for a relocation — and
    rejected outright if it breaks capacity or a window, so the search cannot walk through an
    infeasible state to reach a cheaper one. With time windows a local delta is not the
    change in feasibility (an insertion shifts every downstream arrival and every wait), so
    there is no delta shortcut here at all.

    Scan order: vehicle ascending then `i` then `j` for the reversals, then source vehicle,
    source position, target vehicle, target position ascending for the relocations.
    Comparisons are strict, so ties go to the earlier move in that order. As in the TSP
    search, the chosen move is re-evaluated before it is committed and dropped if the
    re-evaluation does not confirm the gain — so the total is non-increasing by construction.

    `evaluated` counts the candidates actually examined, and `local_optimum` is claimed ONLY
    from a scan that examined something and finished. The neighbourhood here really can be
    empty — no routes at all, or a single route holding a single stop whose only relocation
    targets are the two skipped no-ops — and `local_optimum = True` from a vacuous scan asserts
    a search that never happened. `_local_search` guards the same claim the same way; one
    invariant enforced at two strengths in one file is a bug even where the weaker one happens
    to be vacuously true today, because a later change to the move set widens the vacuous case
    and no counter exists to notice.

    The relocation scan is O((V*m)^2) candidates each costing an O(m) `_eval_route`, so the
    shared budget is checked in the INNERMOST loop of each family: an exhausted budget cuts the
    scan, applies nothing, and leaves `local_optimum` False, because a partial scan's best move
    is not the neighbourhood's best and a partial scan cannot certify that none exists.
    """
    var routes = List[List[Int]]()
    for v in range(len(routes_in)):
        var copy = List[Int]()
        for k in range(len(routes_in[v])):
            copy.append(routes_in[v][k])
        routes.append(copy^)
    var dists = List[Float64]()
    var total_stops = 0
    for v in range(len(routes)):
        total_stops += len(routes[v])
        var ev = _eval_route(
            distance, n, demand, capacity, ready, due, service, windowed, routes[v], work
        )
        dists.append(ev.dist)

    var passes = 0
    var moves = 0
    var evaluated = 0
    var local_opt = False
    var cut = False
    while passes < max_passes:
        var best_gain = 0.0
        var best_kind = -1
        var best_a = -1
        var best_b = -1
        var best_c = -1
        var best_d = -1

        for v in range(len(routes)):
            if cut:
                break
            var m = len(routes[v])
            for i in range(m - 1):
                if cut:
                    break
                for j in range(i + 1, m):
                    if work <= 0:
                        cut = True
                        break
                    evaluated += 1
                    var candidate = _reverse_span(routes[v], i, j)
                    var ev = _eval_route(
                        distance, n, demand, capacity, ready, due, service, windowed,
                        candidate, work,
                    )
                    if not ev.feasible:
                        continue
                    var gain = dists[v] - ev.dist
                    if gain <= _move_tol(dists[v]):
                        continue
                    if best_kind < 0 or gain > best_gain:
                        best_gain = gain
                        best_kind = 0
                        best_a = v
                        best_b = i
                        best_c = j

        for v1 in range(len(routes)):
            if cut:
                break
            for p1 in range(len(routes[v1])):
                if work <= 0:
                    cut = True
                    break
                var city = routes[v1][p1]
                var shrunk = _remove_at(routes[v1], p1)
                var ev1 = _eval_route(
                    distance, n, demand, capacity, ready, due, service, windowed, shrunk,
                    work,
                )
                if not ev1.feasible:
                    continue
                for v2 in range(len(routes)):
                    if cut:
                        break
                    for p2 in range(len(routes[v2]) + 1):
                        if v1 == v2 and (p2 == p1 or p2 == p1 + 1):
                            continue
                        if work <= 0:
                            cut = True
                            break
                        evaluated += 1
                        # Positions are stated in the ORIGINAL route's indexing. Within one
                        # route the removal shifts everything after `p1` down by one, and
                        # `p2 == p1` / `p2 == p1 + 1` are the two no-ops, skipped above.
                        var grown = List[Int]()
                        if v1 == v2:
                            var pos_same = p2
                            if p2 > p1:
                                pos_same = p2 - 1
                            grown = _insert_at(shrunk, pos_same, city)
                        else:
                            grown = _insert_at(routes[v2], p2, city)
                        var ev2 = _eval_route(
                            distance, n, demand, capacity, ready, due, service,
                            windowed, grown, work,
                        )
                        if not ev2.feasible:
                            continue
                        var gain = 0.0
                        if v1 == v2:
                            gain = dists[v1] - ev2.dist
                        else:
                            gain = dists[v1] + dists[v2] - ev1.dist - ev2.dist
                        var scale = dists[v1]
                        if dists[v2] > scale:
                            scale = dists[v2]
                        if gain <= _move_tol(scale):
                            continue
                        if best_kind < 0 or gain > best_gain:
                            best_gain = gain
                            best_kind = 1
                            best_a = v1
                            best_b = p1
                            best_c = v2
                            best_d = p2

        if cut:
            # The budget cut this scan short. Nothing is applied and no local optimum is
            # claimed: the incumbent routes are already feasible and audited.
            break
        if best_kind < 0:
            # "No improving move exists" is a claim about a SCAN, so it needs a scan. With no
            # routes, or one route of one stop whose only relocation targets are the two skipped
            # no-ops, nothing was examined. `total_stops <= 1` is the one honest exception and
            # is the exact analogue of `n <= 2` in `_local_search`: with at most one customer
            # there is only one distinct routing (the vehicles are interchangeable), so it is
            # optimal outright rather than merely unexamined.
            local_opt = evaluated > 0 or total_stops <= 1
            break
        passes += 1
        if best_kind == 0:
            var applied = _reverse_span(routes[best_a], best_b, best_c)
            var ev = _eval_route(
                distance, n, demand, capacity, ready, due, service, windowed, applied,
                work,
            )
            if not ev.feasible or ev.dist >= dists[best_a]:
                break
            routes[best_a] = applied.copy()
            dists[best_a] = ev.dist
            moves += 1
        else:
            var city = routes[best_a][best_b]
            var shrunk = _remove_at(routes[best_a], best_b)
            var grown = List[Int]()
            if best_a == best_c:
                var pos = best_d
                if best_d > best_b:
                    pos = best_d - 1
                grown = _insert_at(shrunk, pos, city)
            else:
                grown = _insert_at(routes[best_c], best_d, city)
            var ev_s = _eval_route(
                distance, n, demand, capacity, ready, due, service, windowed, shrunk,
                work,
            )
            var ev_g = _eval_route(
                distance, n, demand, capacity, ready, due, service, windowed, grown, work
            )
            if not (ev_s.feasible and ev_g.feasible):
                break
            if best_a == best_c:
                if ev_g.dist >= dists[best_a]:
                    break
                routes[best_a] = grown.copy()
                dists[best_a] = ev_g.dist
            else:
                if ev_s.dist + ev_g.dist >= dists[best_a] + dists[best_c]:
                    break
                routes[best_a] = shrunk.copy()
                routes[best_c] = grown.copy()
                dists[best_a] = ev_s.dist
                dists[best_c] = ev_g.dist
            moves += 1

    return _ImproveResult(routes^, passes, moves, evaluated, local_opt)


def _layout_partitions(stops: List[Int], route_start: List[Int], n_routes: Int) -> Bool:
    """True when `route_start` is exactly `n_routes + 1` offsets that PARTITION `stops`.

    This is `RouteSolution`'s layout invariant, tested rather than assumed, and it is the check
    that would have caught the defect it exists for: `_solve_core` appended one offset per
    surviving route SLOT including the ones relocation had emptied, while `n_routes_used`
    counted only the non-empty slots, so `route_start = [0, 3, 3, 5, 8]` was returned beside
    `n_routes_used = 3`. A caller reading `stops[route_start[v] : route_start[v + 1]]` for
    `v` in `range(n_routes_used)` then read `[0:3]`, `[3:3]`, `[3:5]` and dropped the three
    customers in `[5:8]` — a routing that is not a routing, under a success status.

    Four conditions, and all four are needed for the slicing loop to be correct:

      * `len(route_start) == n_routes + 1` — the reported count and the offsets are the SAME
        claim, so they cannot disagree;
      * `route_start[0] == 0` and `route_start[n_routes] == len(stops)` — the routes COVER
        `stops`: no prefix and no suffix is left out;
      * STRICTLY increasing — no empty route, hence no zero-length slot, and no overlap.

    Together: every index of `stops` lies in exactly one interval. Composed with `_audit_core`'s
    `all_served` and `n_served == n_customers` (every customer appears exactly once in `stops`),
    the routes are a partition of the customers too, which is what "a routing" means.
    """
    if n_routes < 0:
        return False
    if len(route_start) != n_routes + 1:
        return False
    if route_start[0] != 0:
        return False
    if route_start[n_routes] != len(stops):
        return False
    for v in range(n_routes):
        if route_start[v + 1] <= route_start[v]:
            return False
    return True


def _no_solution(
    status: Int, n: Int, n_vehicles: Int, windowed: Bool, proven: Bool, lb: Int,
    ffd: Int, defect_node: Int, restarts: Int, seed: UInt64
) -> RouteSolution:
    """A rejection or a failure: no routes, no total, the instance facts still reported.

    The bounds and the defect stay because they are facts about the INSTANCE, not claims
    about an answer — which is exactly what a caller holding "no solution" needs next.
    """
    var n_customers = 0
    if n > 0:
        n_customers = n - 1
    return RouteSolution(
        status, n, n_customers, n_vehicles, windowed, False, proven, False,
        0.0, 0, List[Int](), List[Int](), List[Float64](), List[Float64](),
        List[Float64](), lb, ffd, ROUTE_ABSENT, ROUTE_ABSENT, -1, -1, defect_node,
        restarts, 0, 0, 0, False, seed,
    )


def _solve_core(
    distance: List[Float64], n: Int, demand: List[Float64], capacity: Float64,
    n_vehicles: Int, ready: List[Float64], due: List[Float64],
    service: List[Float64], windowed: Bool, max_passes: Int, n_restarts: Int,
    seed: UInt64
) -> RouteSolution:
    """Validate, prove what can be proven, construct, improve, then RE-AUDIT and report."""
    var defect = _instance_defect(
        distance, n, demand, capacity, n_vehicles, ready, due, service, windowed
    )
    if defect != ROUTE_OK:
        return _no_solution(defect, n, n_vehicles, windowed, False, 0, 0, -1, 0, seed)
    if n == 1:
        # A depot and no customers. Zero vehicles move, the total distance is 0.0, and that
        # is a real answer rather than an absence: there is nothing to serve.
        var starts = List[Int]()
        starts.append(0)
        return RouteSolution(
            ROUTE_OK, n, 0, n_vehicles, windowed, True, False, True, 0.0, 0,
            List[Int](), starts^, List[Float64](), List[Float64](), List[Float64](),
            0, 0, 0.0, 0.0, -1, -1, -1, 0, 0, 0, 0, True, seed,
        )

    var customers = _customer_demands(demand, n)
    var lb = _lower_bound_vehicles(demand, n, capacity)
    var ffd = bin_packing_first_fit_decreasing(customers, capacity)

    # ── proofs from the instance alone, before any search ────────────────────
    for c in range(1, n):
        # The SAME strength `_eval_route` judges a one-stop route's load with: a proof that
        # one demand cannot be carried must not be stricter than the check that would carry it.
        if demand[c] - capacity > _pair_tol(demand[c], capacity, 1):
            return _no_solution(
                ROUTE_INFEASIBLE_PROVEN, n, n_vehicles, windowed, True, lb, ffd, c, 0,
                seed,
            )
    if lb > n_vehicles:
        return _no_solution(
            ROUTE_INFEASIBLE_PROVEN, n, n_vehicles, windowed, True, lb, ffd, -1, 0, seed
        )
    if windowed:
        # Hoisted: the cheapest arc out of the depot and the cheapest arc into it are the same
        # two numbers for every customer, and both bounds below need them.
        var depot_out = _min_arc_out_of(distance, n, ROUTE_DEPOT)
        var depot_in = _min_arc_into(distance, n, ROUTE_DEPOT)
        for c in range(1, n):
            var earliest = ready[ROUTE_DEPOT] + _earliest_arrival_bound(
                distance, n, c, depot_out
            )
            if earliest - due[c] > _accum_tol(earliest, 3):
                return _no_solution(
                    ROUTE_INFEASIBLE_PROVEN, n, n_vehicles, windowed, True, lb, ffd, c,
                    0, seed,
                )
            var start = earliest
            if start < ready[c]:
                start = ready[c]
            var home = start + service[c] + _earliest_return_bound(
                distance, n, c, depot_in
            )
            if home - due[ROUTE_DEPOT] > _accum_tol(home, 6):
                return _no_solution(
                    ROUTE_INFEASIBLE_PROVEN, n, n_vehicles, windowed, True, lb, ffd, c,
                    0, seed,
                )

    # Clamps on the KNOBS, which bound the iteration count and NOT the work. The work bound is
    # `work` below: one budget for the whole solve, threaded through the construction order, the
    # construction, the improvement scan and every audit, so `n_restarts` cannot buy time that
    # the payload did not pay for. `restarts` reports the restarts actually ATTEMPTED.
    var restarts = n_restarts
    if restarts < 1:
        restarts = 1
    if restarts > ROUTE_MAX_NODES:
        restarts = ROUTE_MAX_NODES
    var passes_cap = max_passes
    if passes_cap < 0:
        passes_cap = 0
    if passes_cap > ROUTE_MAX_PASSES:
        passes_cap = ROUTE_MAX_PASSES
    var work = ROUTE_WORK_BUDGET

    var best_stops = List[Int]()
    var best_starts = List[Int]()
    var best_total = 0.0
    var have_best = False
    var best_passes = 0
    var best_moves = 0
    var best_local = False
    var n_feasible = 0
    var attempted = 0

    for restart in range(restarts):
        if work <= 0:
            break
        attempted += 1
        var order = _insertion_order(demand, n, due, windowed, restart, seed, work)
        if len(order) != n - 1:
            continue
        var built = _build_routes(
            distance, n, demand, capacity, ready, due, service, windowed, n_vehicles,
            order, work,
        )
        if len(built) == 0:
            continue
        var improved = _improve_routes(
            distance, n, demand, capacity, ready, due, service, windowed, built,
            passes_cap, work,
        )
        var stops = List[Int]()
        var starts = List[Int]()
        starts.append(0)
        for v in range(len(improved.routes)):
            # An EMPTY route is NOT a route, and it does not get a slot. Relocation can empty a
            # route, and appending an offset for the emptied slot is exactly what made
            # `route_start` and `n_routes_used` disagree: the offsets counted slots while the
            # count counted non-empty routes, so a caller slicing by the documented layout read
            # the wrong boundaries and silently dropped whole routes. Compacting here makes the
            # invariant hold by CONSTRUCTION — `len(starts) - 1` is then both the number of
            # offsets and the number of routes, and `_audit_core`'s per-vehicle arrays, which are
            # indexed by `len(route_start) - 1`, line up with the same `v`. The vehicles that
            # stay at the depot are simply not listed; they carry nothing and travel nowhere.
            if len(improved.routes[v]) == 0:
                continue
            for k in range(len(improved.routes[v])):
                stops.append(improved.routes[v][k])
            starts.append(len(stops))
        # The SAME audit a caller would run, on the answer about to be returned.
        var audit = _audit_core(
            distance, n, demand, capacity, ready, due, service, windowed, stops, starts,
            work,
        )
        if audit.status != ROUTE_OK or not audit.feasible or not audit.has_total:
            continue
        if not _layout_partitions(stops, starts, len(starts) - 1):
            continue
        n_feasible += 1
        if not have_best or audit.total_distance < best_total:
            have_best = True
            best_total = audit.total_distance
            best_stops = stops^
            best_starts = starts^
            best_passes = improved.passes
            best_moves = improved.moves
            best_local = improved.local_optimum

    if not have_best:
        return _no_solution(
            ROUTE_NO_SOLUTION_FOUND, n, n_vehicles, windowed, False, lb, ffd, -1,
            attempted, seed,
        )

    var final_audit = _audit_core(
        distance, n, demand, capacity, ready, due, service, windowed, best_stops,
        best_starts, work,
    )
    if final_audit.status != ROUTE_OK or not final_audit.feasible:
        return _no_solution(
            ROUTE_NO_SOLUTION_FOUND, n, n_vehicles, windowed, False, lb, ffd, -1,
            attempted, seed,
        )
    # `n_routes_used` and `route_start` are ONE claim, so they are formed from one number:
    # every listed route is non-empty by construction above, hence the offset count IS the
    # route count. The invariant is then VERIFIED rather than trusted, because the defect this
    # replaces was precisely two fields computed two ways: the offsets must partition `stops`
    # exactly, the per-vehicle arrays must be indexed by the same `v`, and every customer must
    # appear in exactly one route — which `all_served` plus `n_served == n - 1` establishes.
    var used = len(best_starts) - 1
    if not _layout_partitions(best_stops, best_starts, used):
        return _no_solution(
            ROUTE_NO_SOLUTION_FOUND, n, n_vehicles, windowed, False, lb, ffd, -1,
            attempted, seed,
        )
    if not (final_audit.all_served and final_audit.n_served == n - 1):
        return _no_solution(
            ROUTE_NO_SOLUTION_FOUND, n, n_vehicles, windowed, False, lb, ffd, -1,
            attempted, seed,
        )
    if (
        len(final_audit.route_load) != used
        or len(final_audit.route_distance) != used
        or len(final_audit.route_return_time) != used
    ):
        return _no_solution(
            ROUTE_NO_SOLUTION_FOUND, n, n_vehicles, windowed, False, lb, ffd, -1,
            attempted, seed,
        )
    # The fleet size is part of what the answer claims, and `_audit_core` has no fleet
    # parameter to check it against — so it is checked HERE rather than assumed from the
    # construction. A certificate is only as strong as the conditions actually verified.
    if used > n_vehicles:
        return _no_solution(
            ROUTE_NO_SOLUTION_FOUND, n, n_vehicles, windowed, False, lb, ffd, -1,
            attempted, seed,
        )
    # The status is the EXACT complement of `local_optimum`, computed from that one field and
    # nothing else: `max_passes` is not consulted, because `ROUTE_OK`'s name asserts a local
    # optimum and a value may not both assert and deny one.
    var status = ROUTE_OK
    if not best_local:
        status = ROUTE_OK_LIMIT
    return RouteSolution(
        status, n, n - 1, n_vehicles, windowed, True, False, True,
        final_audit.total_distance, used, best_stops^, best_starts^,
        final_audit.route_load.copy(), final_audit.route_distance.copy(),
        final_audit.route_return_time.copy(), lb, ffd, final_audit.max_capacity_excess,
        final_audit.max_lateness, -1, -1, -1, attempted, n_feasible, best_passes,
        best_moves, best_local, seed,
    )


def vrp_capacity_solve(
    distance: List[Float64], n: Int, demand: List[Float64], capacity: Float64,
    n_vehicles: Int, max_passes: Int, n_restarts: Int, seed: UInt64
) -> RouteSolution:
    """Capacity-constrained vehicle routing from depot 0. No time windows.

    Capacity is HARD: every returned route is re-audited against `demand` and `capacity`
    before the answer leaves this function, and an answer that does not survive that audit
    is replaced by `ROUTE_NO_SOLUTION_FOUND` with no routes. `lower_bound_vehicles` and
    `ffd_bins` come back either way so a caller can tell a bad answer from a hard instance.

    Restart 0 inserts customers in demand-descending order — the order the frozen FFD bound
    assumes; restarts 1.. use a keyed permutation of the customers, so the whole solve is a
    pure function of its arguments including `seed`.

    @capability vrp_capacity_solve
    complexity: O(n_restarts * max_passes * n^2)
    counts:
    - n * n == len(distance) [kernel_validated]
    - n == len(demand) [kernel_validated]
    - dim n_vehicles <= ROUTE_MAX_NODES [kernel_validated]
    @endcapability
    """
    var no_times = List[Float64]()
    return _solve_core(
        distance, n, demand, capacity, n_vehicles, no_times, no_times, no_times, False,
        max_passes, n_restarts, seed,
    )


def vrp_time_window_solve(
    distance: List[Float64], n: Int, demand: List[Float64], capacity: Float64,
    n_vehicles: Int, ready: List[Float64], due: List[Float64], service: List[Float64],
    max_passes: Int, n_restarts: Int, seed: UInt64
) -> RouteSolution:
    """Vehicle routing with capacity AND hard time windows, from depot 0.

    `distance` doubles as the travel-time matrix — one matrix, stated, rather than two that
    can silently disagree. A vehicle leaves the depot at `ready[0]`, may WAIT at a stop it
    reaches before `ready[c]`, must begin service by `due[c]`, spends `service[c]` there,
    and must be back at the depot by `due[0]`.

    Both constraint families are hard, and both are re-audited by `_audit_core` — the same
    routine `vrp_check` runs — before anything is returned. A missed window makes the whole
    attempt not a solution: `defect_vehicle`, `defect_stop` and `defect_node` name where,
    and `ROUTE_INFEASIBLE_PROVEN` is reserved for what the data alone proves (a stop that
    cannot be reached before its due time even going straight there, or one that cannot be
    left in time to reach the depot by `due[0]`).

    @capability vrp_time_window_solve
    complexity: O(n_restarts * max_passes * n^2)
    counts:
    - n * n == len(distance) [kernel_validated]
    - n == len(demand, ready, due, service) [kernel_validated]
    - dim n_vehicles <= ROUTE_MAX_NODES [kernel_validated]
    @endcapability
    """
    return _solve_core(
        distance, n, demand, capacity, n_vehicles, ready, due, service, True,
        max_passes, n_restarts, seed,
    )
