"""
graph_analytics.temporal — time-respecting journeys over a timestamped edge stream.

Temporal reachability is not transitive, so a static answer is *wrong*, not coarse
--------------------------------------------------------------------------------
Static reachability composes: `A -> B` and `B -> C` implies `A -> C`. Timestamped edges
do not compose that way. With `A -> B` at `t = 5` and `B -> C` at `t = 3`, the only edge
out of `B` left three time units before anything could arrive at `B`, so `C` is *not*
reachable from `A` — while `graph.weighted.shortest_path_dijkstra` on the same edge set
returns a finite distance for `C` and a caller reads it as a route. That is the failure
this module exists to prevent: a static algorithm on temporal data does not degrade
gracefully, it answers confidently and wrongly. `temporal_static_gap` names the nodes the
static answer invents, and `test_graph_analytics_temporal.mojo` asserts the frozen kernel
is wrong on exactly that three-node graph.

A journey (a time-respecting path) from `s` starting at `start_time` is a sequence of
edges `e1..ek` with `time[e1] >= start_time`, `time[e(i+1)] >= arrival(e_i)`, and
`arrival(e_i) = time[e_i] + duration(e_i)`. Times are **non-decreasing**, i.e. waiting at
a node is allowed and arriving exactly when the next edge departs is legal. Under that
model two edges sharing one timestamp chain only if the first takes zero time, which the
scan below handles explicitly rather than by luck of the edge order.

`weight` is the traversal duration, and that is not a naming choice
------------------------------------------------------------------
The public arrays are `src`, `dst`, `weight`, `time`. `time` is the timestamp at which
the edge departs and `weight` is how long traversing it takes, in the *same units* — the
arrival is `time + weight`, and a quantity in any other unit (a price, a hop count, a
capacity) cannot be added to a timestamp. A cost in other units is a static question and
belongs to `graph_analytics.adjacency`. Pass zeros, or call the `_instant` driver, when
edges are instantaneous events (a message, a contact, a transaction).

A negative duration is refused, not clamped: it means arriving before departing, it makes
the whole non-decreasing model meaningless, and it breaks the single forward scan (an edge
could enable a group already behind the scan). This mirrors
`graph_csr_dijkstra`'s refusal of a negative weight — the frozen alternative there was
`bellman_ford`; here there is no alternative, because the model itself is gone.

Absence: a duration has an impossible value, a timestamp does not
-----------------------------------------------------------------
`graph_analytics.adjacency` can use `-1.0` as a real marker because a Dijkstra distance is
provably `>= 0`. A *timestamp* has no impossible `Float64`: `-1.0` is a perfectly good
event time (one second before an epoch), and NaN cannot cross a JSON frame. So
`TemporalArrival.reached` is the sole authority for "did a journey exist", and
`arrival[v]` at an unreached node holds `TEMPORAL_ARRIVAL_FILLER` — named a *filler*, not
a marker, because it carries no information and a caller that reads it instead of
`reached` gets a wrong answer. The suite asserts the collision head-on: on a graph whose
real answer is `arrival[1] == -1.0`, node 2 is unreachable and also reads `-1.0`.

A *journey duration* is different: it is `arrival - departure` over non-negative
durations, so it is `>= 0` and `TEMPORAL_NO_DURATION = -1.0` is a genuine impossible
value. `TemporalDurations.duration` and `TemporalPath.duration` therefore do carry a real
marker, and the contrast is deliberate — the same distinction
`GraphEdgeQuery`/`GraphDistances` draws in `adjacency.mojo`.

Windows are half-open: `[window_start, window_end)`
---------------------------------------------------
An edge at exactly `window_start` is **in**; an edge at exactly `window_end` is **out**.
Half-open because that is the only convention under which adjacent windows tile a
timeline without double-counting the instant they share — `[0, 86400)` and
`[86400, 172800)` are two whole days and no event belongs to both. `window_start ==
window_end` is a legal empty window; `window_end < window_start` and a non-finite bound
are refused as `TEMPORAL_ERR_WINDOW_INVALID`. Both boundaries are asserted in the suite,
because an off-by-one here silently adds or drops a day of events and every count
downstream still looks plausible.

One forward scan over time, with the same-timestamp group closed to a fixed point
--------------------------------------------------------------------------------
Edges are visited in non-decreasing departure order and each maximal run of *equal*
timestamps is one group. For an edge `(u, v, t, d)` the test is `reached[u] and
arrival[u] <= t`, and the update is `arrival[v] = min(arrival[v], t + d)`. That single
pass is correct because every journey arriving at `u` by time `t` uses only edges
departing at `<= t`, and a later group cannot improve `arrival[u]` to a value `<= t`
(later arrivals are `>= t' > t`). Within one group:

* zero-duration edges arrive at `t` itself, so they *can* chain with each other, and a
  single pass in a bad edge order would miss the chain. They are relaxed to a fixed point
  over at most `group_size + 1` passes — a shortest zero-duration chain uses distinct
  edges, so its length is bounded by the group size, and one extra pass observes no
  change.
* positive-duration edges arrive strictly after `t`, so they can neither chain with each
  other nor with the zero-duration pass. They are applied once, after it, and the result
  is independent of the order within the group.

Ties on arrival break toward fewer hops, which makes `hops` the minimum edge count among
the earliest-arriving journeys rather than an artefact of the scan order. That is what
lets the suite assert, on a graph where every edge shares one timestamp and every
duration is zero, that `hops` equals the frozen unit-weight
`graph.weighted.shortest_path_dijkstra` distance exactly.

Ordering reuses the frozen heap, identity lives outside it
----------------------------------------------------------
`heap.mojo` is the repo's real O(log n) binary heap and it stores a bare `Float64`, so the
edge index cannot ride along inside it. Packing `(time, edge)` into one `Float64` is the
same rejected idea as in `adjacency.mojo`, for the same reason: 53 mantissa bits are
already spent on the timestamp, so any packing perturbs the ordering and decodes to the
wrong edge. Instead the heap holds the timestamps and `columnar.hash_index.HashIndex`
maps each distinct timestamp to a bucket of edge indices. Recovery is exact rather than
approximate — the heap only moves values, never computes on them, so a popped key is
bit-identical to the pushed one — and every timestamp is validated finite first, so no NaN
key can arise. Equal timestamps share a bucket and drain LIFO, which is deterministic and
harmless because the group is closed to a fixed point regardless of its internal order.

Out-of-range endpoints are skipped and counted, never indexed
-------------------------------------------------------------
An edge with an endpoint outside `[0, n_nodes)` is not an edge of this graph. It is
dropped, counted in `skipped_edges`, and never used as a subscript — an out-of-range
`List` read is an uncatchable process crash, not an exception, and `n_nodes` is never
silently widened to make a stray index fit.

The activity summary reports the statistics that do not exist as absent
----------------------------------------------------------------------
Inter-arrival statistics come from the frozen `math_ext.mean` and `math_ext.stdev` over
the gaps between consecutive event times — not from arithmetic rewritten here. Both frozen
kernels return `0.0` when they have nothing to average (`variance` returns `0.0` for a
single observation), and `0.0` reads as "these events are perfectly regular" rather than
"there is no second gap to compare". So every derived quantity carries its own flag:
`has_interarrival` (needs 2 events), `has_dispersion` (needs 3), `has_cv` (needs a
non-zero mean gap) and `has_burstiness` (needs `sigma + mu > 0`). Burstiness is the
Goh-Barabasi coefficient `(sigma - mu) / (sigma + mu)`, `-1` for a perfectly periodic
stream, `0` for Poisson-like, `+1` for maximally bursty; counts are real answers at any
size and are always reported.
"""
from std.math import isinf, isnan
from sparse_numerics.csr import MAX_CSR_DIM

from columnar.hash_index import HashIndex
from graph_analytics.adjacency import GRAPH_OK, graph_bfs_levels_from_triplets
from heap import heap_pop_min, heap_push_min
from math_ext import mean, stdev

# ── status codes ──────────────────────────────────────────────────────────────
# One code per defect: a caller holding a rejection needs to know which of its four
# arrays, or which of its three scalars, is the problem.

comptime TEMPORAL_OK: Int = 0
# The node ceiling is sparse_numerics.csr's MAX_CSR_DIM, shared with adjacency.mojo rather
# than restated, so a node count this module accepts is one the adjacency and matrix forms
# accept too. It is needed because every reachability scan here allocates one slot PER NODE
# (arrival times, visited flags, predecessors) regardless of how few edges exist, so a bare
# `n_nodes < 0` check leaves `temporal_earliest_arrival(..., n_nodes=10**12)` asking for an
# 8 TB allocation from a two-edge stream. Clamping negatives is not a bound.
comptime TEMPORAL_MAX_NODES: Int = MAX_CSR_DIM

comptime TEMPORAL_ERR_INVALID_DIMENSIONS: Int = 1
comptime TEMPORAL_ERR_LENGTH_MISMATCH: Int = 2
comptime TEMPORAL_ERR_NON_FINITE_TIME: Int = 3
comptime TEMPORAL_ERR_NON_FINITE_DURATION: Int = 4
comptime TEMPORAL_ERR_NEGATIVE_DURATION: Int = 5
comptime TEMPORAL_ERR_EMPTY_GRAPH: Int = 6
comptime TEMPORAL_ERR_SOURCE_OUT_OF_RANGE: Int = 7
comptime TEMPORAL_ERR_TARGET_OUT_OF_RANGE: Int = 8
comptime TEMPORAL_ERR_NODE_OUT_OF_RANGE: Int = 9
comptime TEMPORAL_ERR_WINDOW_INVALID: Int = 10
comptime TEMPORAL_ERR_STATIC_REJECTED: Int = 11

# ── absence ───────────────────────────────────────────────────────────────────
# `-1.0` is a real marker for a journey duration (durations are `>= 0`) and only a filler
# for an arrival timestamp (every `Float64` is a legal timestamp). See the module
# docstring; conflating the two is the mistake this pair of names exists to prevent.

comptime TEMPORAL_NO_DURATION: Float64 = -1.0
comptime TEMPORAL_ARRIVAL_FILLER: Float64 = -1.0
comptime TEMPORAL_NO_PREDECESSOR: Int = -1
comptime TEMPORAL_NO_EDGE: Int = -1


fn temporal_status_name(code: Int) -> String:
    """Name for a status code, so a rejection surfaces the defect and not a bare number.
    """
    if code == TEMPORAL_OK:
        return "ok"
    if code == TEMPORAL_ERR_INVALID_DIMENSIONS:
        return "invalid_dimensions"
    if code == TEMPORAL_ERR_LENGTH_MISMATCH:
        return "parallel_arrays_length_mismatch"
    if code == TEMPORAL_ERR_NON_FINITE_TIME:
        return "non_finite_time"
    if code == TEMPORAL_ERR_NON_FINITE_DURATION:
        return "non_finite_duration"
    if code == TEMPORAL_ERR_NEGATIVE_DURATION:
        return "negative_duration_arrival_before_departure"
    if code == TEMPORAL_ERR_EMPTY_GRAPH:
        return "empty_graph"
    if code == TEMPORAL_ERR_SOURCE_OUT_OF_RANGE:
        return "source_out_of_range"
    if code == TEMPORAL_ERR_TARGET_OUT_OF_RANGE:
        return "target_out_of_range"
    if code == TEMPORAL_ERR_NODE_OUT_OF_RANGE:
        return "node_out_of_range"
    if code == TEMPORAL_ERR_WINDOW_INVALID:
        return "window_end_before_start_or_non_finite"
    if code == TEMPORAL_ERR_STATIC_REJECTED:
        return "static_reachability_rejected"
    return "unknown_status"


# ── return-only result structs ────────────────────────────────────────────────
# Declared here because the marshalling spec for a returned struct is parsed per file:
# returning a struct owned by `adjacency.mojo` would drop the function from the runtime
# contract silently, with no error anywhere.


@fieldwise_init
struct TemporalArrival(Copyable, Movable):
    """Earliest arrival per node, with reachability as data rather than as a number.

    `reached[v]` is the authority. `arrival[v]` is `TEMPORAL_ARRIVAL_FILLER` wherever
    `reached[v]` is False — a filler, not a marker: `-1.0` is also a legal answer, so a
    caller that reads `arrival` without `reached` will eventually be wrong.
    `predecessor[v]` and `predecessor_edge[v]` describe the last edge of one
    earliest-arrival journey (`predecessor_edge` indexes the caller's own edge arrays);
    both are `-1` at the source and wherever `reached[v]` is False. `hops[v]` is the
    fewest edges among the journeys that achieve `arrival[v]`.

    On any status other than `TEMPORAL_OK` every list is empty and every count is 0: a
    rejected request has no partial answer.
    """

    var status: Int
    var n_nodes: Int
    var source: Int
    var start_time: Float64
    var reached_count: Int
    var unreachable_count: Int
    var skipped_edges: Int
    var usable_edges: Int
    var arrival: List[Float64]
    var reached: List[Bool]
    var predecessor: List[Int]
    var predecessor_edge: List[Int]
    var hops: List[Int]


@fieldwise_init
struct TemporalPath(Copyable, Movable):
    """One reconstructed journey. `found` is the authority.

    `nodes` has `hops + 1` entries and `arrival_times` matches it position for position
    (`arrival_times[0]` is when the journey is first at the source). `departure_times` has
    `hops` entries — the timestamp of each edge taken — and is non-decreasing by
    construction, with `arrival_times[i] <= departure_times[i]`. That pair of invariants
    *is* the time-respecting property, in a form a caller can re-check.

    When `found` is False every list is empty, `hops` is 0 and `duration` is
    `TEMPORAL_NO_DURATION`; `departure_time` and `arrival_time` hold
    `TEMPORAL_ARRIVAL_FILLER` and mean nothing.
    """

    var status: Int
    var found: Bool
    var source: Int
    var target: Int
    var hops: Int
    var departure_time: Float64
    var arrival_time: Float64
    var duration: Float64
    var nodes: List[Int]
    var arrival_times: List[Float64]
    var departure_times: List[Float64]


@fieldwise_init
struct TemporalDurations(Copyable, Movable):
    """Fastest-journey duration per node — elapsed time, not arrival time.

    A different question from `TemporalArrival`, and frequently a different journey: the
    earliest arrival may take hours of waiting, while a later departure gets there in
    minutes. `duration[v]` is `TEMPORAL_NO_DURATION` (`-1.0`, impossible for a real
    elapsed time) wherever `reached[v]` is False, so this list *does* carry a marker.
    `departure[v]` is the timestamp the fastest journey leaves the source; it is the
    filler at the source itself, whose journey has no edges, and wherever unreached.
    `starts_tried` is how many candidate departure times were evaluated.
    """

    var status: Int
    var n_nodes: Int
    var source: Int
    var reached_count: Int
    var unreachable_count: Int
    var starts_tried: Int
    var duration: List[Float64]
    var departure: List[Float64]
    var reached: List[Bool]


@fieldwise_init
struct TemporalStream(Copyable, Movable):
    """A timestamped edge stream, ascending by time, with everything it dropped counted.

    `windowed` says whether `window_start`/`window_end` are a filter the caller asked for
    (half-open `[start, end)`) or merely the observed first and last timestamp. The three
    drop counts are disjoint and account for every input edge:
    `n_edges + skipped_edges + dropped_before + dropped_after == len(src)`. Endpoint
    validity is tested first, so an out-of-range edge is counted as skipped and not as
    out-of-window.
    """

    var status: Int
    var n_nodes: Int
    var n_edges: Int
    var skipped_edges: Int
    var dropped_before: Int
    var dropped_after: Int
    var windowed: Bool
    var window_start: Float64
    var window_end: Float64
    var src: List[Int]
    var dst: List[Int]
    var weight: List[Float64]
    var time: List[Float64]


@fieldwise_init
struct TemporalActivity(Copyable, Movable):
    """When the edges of this graph fired, and how regularly.

    Counts are real answers at any size and are always filled. Every *derived* quantity
    carries a flag, because the frozen `math_ext.mean`/`stdev` return `0.0` when they have
    nothing to average and `0.0` reads as "perfectly regular" rather than "no answer":

    * `has_span` needs at least one event (`span = t_max - t_min`, `0.0` for one event).
    * `has_interarrival` needs two (one gap) for `mean_interarrival`/`min_gap`/`max_gap`.
    * `has_dispersion` needs three (two gaps) for `stdev_interarrival`, since a sample
      standard deviation of one observation does not exist.
    * `has_cv` additionally needs `mean_interarrival > 0`, and `has_burstiness`
      `stdev + mean > 0` — both fail when every event shares one timestamp.

    `gaps` are the consecutive differences in time order, so they are non-negative and
    sum to `span`.
    """

    var status: Int
    var skipped_edges: Int
    var n_events: Int
    var n_gaps: Int
    var distinct_times: Int
    var simultaneous_events: Int
    var has_span: Bool
    var t_min: Float64
    var t_max: Float64
    var span: Float64
    var has_interarrival: Bool
    var mean_interarrival: Float64
    var min_gap: Float64
    var max_gap: Float64
    var has_dispersion: Bool
    var stdev_interarrival: Float64
    var has_cv: Bool
    var coefficient_of_variation: Float64
    var has_burstiness: Bool
    var burstiness: Float64
    var gaps: List[Float64]


@fieldwise_init
struct TemporalIntsResult(Copyable, Movable):
    """An ascending Int vector plus status, so "none" and "rejected" stay distinguishable.
    """

    var status: Int
    var length: Int
    var values: List[Int]


@fieldwise_init
struct TemporalGap(Copyable, Movable):
    """How much a static reachability answer over-claims on this timestamped edge set.

    `false_positives` are the nodes the static graph reports reachable and no journey can
    reach — ascending node ids, and the reason a static algorithm must not be pointed at
    temporal data. `static_reached_count` comes from
    `adjacency.graph_bfs_levels_from_triplets` on the same edges with the timestamps
    ignored, so the two counts are computed from one input and cannot drift.
    """

    var status: Int
    var n_nodes: Int
    var source: Int
    var temporal_reached_count: Int
    var static_reached_count: Int
    var false_positive_count: Int
    var false_positives: List[Int]


# ── validation ────────────────────────────────────────────────────────────────


fn temporal_validate(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
) -> Int:
    """`TEMPORAL_OK` for a usable edge stream, else the first defect's code.

    This is the single gate that makes every scan below safe: after it, the four arrays
    have one common length, so an index drawn from `range(len(src))` is in range for all
    four, and no comparison can meet a NaN.

    NaN is tested before the sign test on purpose. `nan < 0.0` is False, so a NaN duration
    would slip past a bare negativity check and then poison every `<=` in the scan — every
    comparison against it is False, which reads as "this edge is never usable" for some
    tests and "always usable" for others.

    An out-of-range endpoint is *not* a defect of the stream: it is an edge this graph does
    not have, and it is skipped and counted per call rather than rejecting the request.
    """
    if n_nodes < 0 or n_nodes > TEMPORAL_MAX_NODES:
        return TEMPORAL_ERR_INVALID_DIMENSIONS
    var m = len(src)
    if len(dst) != m or len(weight) != m or len(time) != m:
        return TEMPORAL_ERR_LENGTH_MISMATCH
    for k in range(m):
        var t = time[k]
        if isnan(t) or isinf(t):
            return TEMPORAL_ERR_NON_FINITE_TIME
        var d = weight[k]
        if isnan(d) or isinf(d):
            return TEMPORAL_ERR_NON_FINITE_DURATION
        if d < 0.0:
            return TEMPORAL_ERR_NEGATIVE_DURATION
    return TEMPORAL_OK


fn temporal_validate_driver(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
) -> String:
    """Named verdict for an edge stream that arrived as four arrays — `ok` or the defect.
    """
    return temporal_status_name(temporal_validate(src, dst, weight, time, n_nodes))


fn _window_status(window_start: Float64, window_end: Float64) -> Int:
    """`TEMPORAL_OK` for a window that can contain events, else why it cannot.

    `start == end` is the legal empty window. A non-finite bound is refused rather than
    treated as "unbounded": an unbounded query is the un-windowed driver, and silently
    reinterpreting `inf` as "no filter" would make a caller's arithmetic slip invisible.
    """
    if isnan(window_start) or isinf(window_start):
        return TEMPORAL_ERR_WINDOW_INVALID
    if isnan(window_end) or isinf(window_end):
        return TEMPORAL_ERR_WINDOW_INVALID
    if window_end < window_start:
        return TEMPORAL_ERR_WINDOW_INVALID
    return TEMPORAL_OK


fn _in_range_edges(
    src: List[Int], dst: List[Int], n_nodes: Int
) -> List[Int]:
    """Indices of the edges whose endpoints both exist. Callers index only through this.
    """
    var keep = List[Int]()
    var m = len(src)
    if len(dst) != m:
        return keep^
    for k in range(m):
        if src[k] >= 0 and src[k] < n_nodes and dst[k] >= 0 and dst[k] < n_nodes:
            keep.append(k)
    return keep^


fn _time_order(edge_index: List[Int], time: List[Float64]) -> List[Int]:
    """`edge_index` reordered so `time` is non-decreasing, via the frozen min-heap.

    The heap carries the timestamps and a `HashIndex` bucket carries the identities; see
    the module docstring for why the pair is not packed into the heap's single `Float64`.
    Equal timestamps drain LIFO, which is deterministic and never affects an answer
    because same-timestamp groups are closed to a fixed point.
    """
    var out = List[Int]()
    var heap = List[Float64]()
    var index = HashIndex(64)
    var buckets = List[List[Int]]()
    for i in range(len(edge_index)):
        var k = edge_index[i]
        if k < 0 or k >= len(time):
            continue
        var t = time[k]
        heap_push_min(heap, t)
        var slot = index.get_or_assign(t, len(buckets))
        if slot == len(buckets):
            buckets.append(List[Int]())
        buckets[slot].append(k)
    while len(heap) > 0:
        var key = heap_pop_min(heap)
        var slot = index.find(key)
        if slot < 0:
            continue
        if len(buckets[slot]) == 0:
            continue
        out.append(buckets[slot].pop())
    return out^


# ── earliest arrival ──────────────────────────────────────────────────────────


fn _no_arrival(
    status: Int, n_nodes: Int, source: Int, start_time: Float64
) -> TemporalArrival:
    """No answer. Empty lists and zero counts, so an ignored status cannot read as one."""
    return TemporalArrival(
        status,
        n_nodes,
        source,
        start_time,
        0,
        0,
        0,
        0,
        List[Float64](),
        List[Bool](),
        List[Int](),
        List[Int](),
        List[Int](),
    )


fn _earliest_arrival_scan(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
    source: Int,
    start_time: Float64,
    order: List[Int],
    skipped: Int,
) -> TemporalArrival:
    """One forward scan over time-ordered edges. Inputs are already validated.

    `order` is time-ascending and holds only in-range edge indices, so every subscript
    below is safe by construction rather than by inspection. Splitting each
    same-timestamp group into a zero-duration fixed point and a single positive-duration
    pass is what makes the result independent of the edge order inside the group — see the
    module docstring.
    """
    var n = n_nodes
    var arrival = List[Float64]()
    var reached = List[Bool]()
    var pred = List[Int]()
    var pred_edge = List[Int]()
    var hops = List[Int]()
    for _ in range(n):
        arrival.append(TEMPORAL_ARRIVAL_FILLER)
        reached.append(False)
        pred.append(TEMPORAL_NO_PREDECESSOR)
        pred_edge.append(TEMPORAL_NO_EDGE)
        hops.append(0)
    arrival[source] = start_time
    reached[source] = True

    var total = len(order)
    var usable = 0
    var i = 0
    while i < total:
        var t = time[order[i]]
        var j = i + 1
        while j < total and time[order[j]] == t:
            j += 1
        # Every reached node's arrival is `>= start_time`, so a group departing earlier
        # than the journey begins cannot have a single usable edge.
        if t >= start_time:
            usable += j - i
            # Zero-duration edges arrive at `t`, so they chain within the group. Bounded
            # passes: a shortest chain uses distinct edges of this group, so its length is
            # at most the group size, and one more pass observes no change.
            var limit = j - i + 1
            var passes = 0
            var changed = True
            while changed and passes < limit:
                passes += 1
                changed = False
                for p in range(i, j):
                    var k = order[p]
                    if weight[k] != 0.0:
                        continue
                    var u = src[k]
                    var v = dst[k]
                    if not reached[u] or arrival[u] > t:
                        continue
                    var better_time = not reached[v] or t < arrival[v]
                    var better_hops = (
                        reached[v] and t == arrival[v] and hops[u] + 1 < hops[v]
                    )
                    if better_time or better_hops:
                        reached[v] = True
                        arrival[v] = t
                        pred[v] = u
                        pred_edge[v] = k
                        hops[v] = hops[u] + 1
                        changed = True
            # Positive-duration edges arrive after `t`, so they cannot make any node
            # available at `t`: one pass, order-independent.
            for p in range(i, j):
                var k = order[p]
                var d = weight[k]
                if d == 0.0:
                    continue
                var u = src[k]
                var v = dst[k]
                if not reached[u] or arrival[u] > t:
                    continue
                var na = t + d
                var better_time = not reached[v] or na < arrival[v]
                var better_hops = (
                    reached[v] and na == arrival[v] and hops[u] + 1 < hops[v]
                )
                if better_time or better_hops:
                    reached[v] = True
                    arrival[v] = na
                    pred[v] = u
                    pred_edge[v] = k
                    hops[v] = hops[u] + 1
        i = j

    var reached_count = 0
    for v in range(n):
        if reached[v]:
            reached_count += 1
    return TemporalArrival(
        TEMPORAL_OK,
        n,
        source,
        start_time,
        reached_count,
        n - reached_count,
        skipped,
        usable,
        arrival^,
        reached^,
        pred^,
        pred_edge^,
        hops^,
    )


fn temporal_earliest_arrival(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
    source: Int,
    start_time: Float64,
) -> TemporalArrival:
    """Earliest time a journey leaving `source` no earlier than `start_time` reaches each node.

    Waiting is free and legal, so this is the earliest arrival over *all* journeys, not
    over the shortest one. Raising `start_time` can only remove journeys — a node reachable
    at 08:00 may be unreachable at 09:00 — which is the property no static reachability
    result has and the reason a cached static answer cannot be reused across times.
    """
    var status = temporal_validate(src, dst, weight, time, n_nodes)
    if status != TEMPORAL_OK:
        return _no_arrival(status, 0, source, start_time)
    if n_nodes == 0:
        return _no_arrival(TEMPORAL_ERR_EMPTY_GRAPH, 0, source, start_time)
    if source < 0 or source >= n_nodes:
        return _no_arrival(
            TEMPORAL_ERR_SOURCE_OUT_OF_RANGE, n_nodes, source, start_time
        )
    if isnan(start_time) or isinf(start_time):
        return _no_arrival(
            TEMPORAL_ERR_NON_FINITE_TIME, n_nodes, source, start_time
        )
    var keep = _in_range_edges(src, dst, n_nodes)
    var skipped = len(src) - len(keep)
    var order = _time_order(keep, time)
    return _earliest_arrival_scan(
        src, dst, weight, time, n_nodes, source, start_time, order, skipped
    )


fn temporal_earliest_arrival_instant(
    src: List[Int],
    dst: List[Int],
    time: List[Float64],
    n_nodes: Int,
    source: Int,
    start_time: Float64,
) -> TemporalArrival:
    """Earliest arrival when traversal takes no time — contacts, messages, transactions.

    Every duration is zero, so edges sharing a timestamp chain freely and this is the
    model most event logs actually have. The durations are materialised as zeros rather
    than special-cased, so there is one scan and not two that could disagree.
    """
    var durations = List[Float64]()
    for _ in range(len(src)):
        durations.append(0.0)
    return temporal_earliest_arrival(
        src, dst, durations, time, n_nodes, source, start_time
    )


# The nine parameters below are packed onto eight physical lines deliberately.
# `apps/runtime/mojo_inventory.py` reads a signature with a ten-line lookahead and, when
# the closing `)` falls outside it, drops the function from the runtime contract with no
# error anywhere — the same silent-drop failure mode as returning another module's struct.
fn temporal_earliest_arrival_window(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int, source: Int, start_time: Float64,
    window_start: Float64, window_end: Float64,
) -> TemporalArrival:
    """Earliest arrival using only edges departing inside the half-open `[start, end)`.

    The window is a filter on the edge stream, applied before the scan, so an edge at
    exactly `window_end` does not exist for this query no matter what `start_time` says.
    `start_time` and `window_start` are independent on purpose: the window is which events
    the caller is allowed to see (a billing period, a shift, a retention horizon) and
    `start_time` is when the traveller is ready.
    """
    var status = temporal_validate(src, dst, weight, time, n_nodes)
    if status != TEMPORAL_OK:
        return _no_arrival(status, 0, source, start_time)
    var wstatus = _window_status(window_start, window_end)
    if wstatus != TEMPORAL_OK:
        return _no_arrival(wstatus, n_nodes, source, start_time)
    var fsrc = List[Int]()
    var fdst = List[Int]()
    var fweight = List[Float64]()
    var ftime = List[Float64]()
    for k in range(len(src)):
        var t = time[k]
        if t < window_start or t >= window_end:
            continue
        fsrc.append(src[k])
        fdst.append(dst[k])
        fweight.append(weight[k])
        ftime.append(t)
    return temporal_earliest_arrival(
        fsrc, fdst, fweight, ftime, n_nodes, source, start_time
    )


fn _no_path(status: Int, source: Int, target: Int) -> TemporalPath:
    return TemporalPath(
        status,
        False,
        source,
        target,
        0,
        TEMPORAL_ARRIVAL_FILLER,
        TEMPORAL_ARRIVAL_FILLER,
        TEMPORAL_NO_DURATION,
        List[Int](),
        List[Float64](),
        List[Float64](),
    )


fn _reconstruct(
    arr: TemporalArrival, target: Int, time: List[Float64]
) -> TemporalPath:
    """Walk the predecessor chain back from `target` and turn it into a journey.

    Bounded by `n_nodes` steps. The predecessor relation is acyclic — an edge is only
    recorded when it strictly improves the arrival, or matches it with strictly fewer hops
    — but a bound is cheaper than trusting that, and a walk that fails to land on the
    source reports absence rather than a partial journey starting nowhere.
    """
    var n = arr.n_nodes
    if (
        len(arr.arrival) != n
        or len(arr.reached) != n
        or len(arr.predecessor) != n
        or len(arr.predecessor_edge) != n
    ):
        return _no_path(arr.status, arr.source, target)
    if target < 0 or target >= n:
        return _no_path(TEMPORAL_ERR_TARGET_OUT_OF_RANGE, arr.source, target)
    if not arr.reached[target]:
        return _no_path(TEMPORAL_OK, arr.source, target)

    var backward = List[Int]()
    var node = target
    var steps = 0
    while steps <= n:
        backward.append(node)
        if node == arr.source:
            break
        var p = arr.predecessor[node]
        var e = arr.predecessor_edge[node]
        if p < 0 or p >= n or e < 0 or e >= len(time):
            break
        node = p
        steps += 1
    if len(backward) == 0 or backward[len(backward) - 1] != arr.source:
        return _no_path(TEMPORAL_OK, arr.source, target)

    var nodes = List[Int]()
    var i = len(backward) - 1
    while i >= 0:
        nodes.append(backward[i])
        i -= 1
    var arrival_times = List[Float64]()
    var departure_times = List[Float64]()
    for a in range(len(nodes)):
        arrival_times.append(arr.arrival[nodes[a]])
        if a > 0:
            departure_times.append(time[arr.predecessor_edge[nodes[a]]])
    var hops = len(nodes) - 1
    var departure = arr.start_time
    if hops > 0:
        departure = departure_times[0]
    var arrival_time = arr.arrival[target]
    return TemporalPath(
        TEMPORAL_OK,
        True,
        arr.source,
        target,
        hops,
        departure,
        arrival_time,
        arrival_time - departure,
        nodes^,
        arrival_times^,
        departure_times^,
    )


fn temporal_earliest_arrival_path(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
    source: Int,
    target: Int,
    start_time: Float64,
) -> TemporalPath:
    """The journey behind `temporal_earliest_arrival`'s answer for one target.

    Reconstructed from the predecessor chain the scan already filled, so the journey and
    the arrival time can never disagree. Among journeys arriving that early it is one with
    the fewest edges.
    """
    var arr = temporal_earliest_arrival(
        src, dst, weight, time, n_nodes, source, start_time
    )
    if arr.status != TEMPORAL_OK:
        return _no_path(arr.status, source, target)
    return _reconstruct(arr, target, time)


# ── fastest journeys ──────────────────────────────────────────────────────────


fn _no_durations(status: Int, n_nodes: Int, source: Int) -> TemporalDurations:
    return TemporalDurations(
        status,
        n_nodes,
        source,
        0,
        0,
        0,
        List[Float64](),
        List[Float64](),
        List[Bool](),
    )


fn _source_departure_times(
    src: List[Int], time: List[Float64], source: Int, order: List[Int]
) -> List[Float64]:
    """The distinct timestamps at which `source` has an out-edge, ascending.

    These are the only departure times worth trying: a journey's first edge leaves the
    source, so its timestamp is one of these, and waiting longer than necessary can only
    lengthen the journey.
    """
    var out = List[Float64]()
    for p in range(len(order)):
        var k = order[p]
        if src[k] != source:
            continue
        var t = time[k]
        if len(out) == 0 or out[len(out) - 1] != t:
            out.append(t)
    return out^


fn temporal_fastest_durations(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
    source: Int,
) -> TemporalDurations:
    """Shortest *elapsed* time of any journey from `source` to each node.

    A different question from earliest arrival, and often a different journey: a route
    that leaves now and waits six hours at a hub arrives earliest, while one that leaves
    at noon is over in twenty minutes. Minimised here is `arrival - departure`, so the
    answer does not depend on when the caller happened to ask.

    Method: the earliest-arrival scan is re-run from each distinct departure time of the
    source, which is exact — the optimum is attained at one of them, because a journey's
    first edge leaves the source at one of those timestamps and starting exactly then
    dominates starting earlier. Cost is `O(k * E)` for `k` distinct source departure
    times; `temporal_earliest_arrival` is the single-scan answer when arrival, not elapsed
    time, is what matters.
    """
    var status = temporal_validate(src, dst, weight, time, n_nodes)
    if status != TEMPORAL_OK:
        return _no_durations(status, 0, source)
    if n_nodes == 0:
        return _no_durations(TEMPORAL_ERR_EMPTY_GRAPH, 0, source)
    if source < 0 or source >= n_nodes:
        return _no_durations(TEMPORAL_ERR_SOURCE_OUT_OF_RANGE, n_nodes, source)

    var keep = _in_range_edges(src, dst, n_nodes)
    var skipped = len(src) - len(keep)
    var order = _time_order(keep, time)
    var starts = _source_departure_times(src, time, source, order)

    var duration = List[Float64]()
    var departure = List[Float64]()
    var reached = List[Bool]()
    for _ in range(n_nodes):
        duration.append(TEMPORAL_NO_DURATION)
        departure.append(TEMPORAL_ARRIVAL_FILLER)
        reached.append(False)
    # The empty journey: already there, in no time, having departed nowhere.
    duration[source] = 0.0
    reached[source] = True

    for s in range(len(starts)):
        var t0 = starts[s]
        var arr = _earliest_arrival_scan(
            src, dst, weight, time, n_nodes, source, t0, order, skipped
        )
        if arr.status != TEMPORAL_OK:
            continue
        for v in range(n_nodes):
            if v == source or not arr.reached[v]:
                continue
            var elapsed = arr.arrival[v] - t0
            if not reached[v] or elapsed < duration[v]:
                reached[v] = True
                duration[v] = elapsed
                departure[v] = t0

    var reached_count = 0
    for v in range(n_nodes):
        if reached[v]:
            reached_count += 1
    return TemporalDurations(
        TEMPORAL_OK,
        n_nodes,
        source,
        reached_count,
        n_nodes - reached_count,
        len(starts),
        duration^,
        departure^,
        reached^,
    )


fn temporal_fastest_path(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
    source: Int,
    target: Int,
) -> TemporalPath:
    """The journey with the least elapsed time from `source` to `target`.

    Its `arrival_time` may be much later than `temporal_earliest_arrival_path`'s — that is
    the point of asking for the fastest rather than the earliest. `departure_time` is the
    timestamp of its first edge, and `duration` is `arrival_time - departure_time`.
    """
    var durations = temporal_fastest_durations(
        src, dst, weight, time, n_nodes, source
    )
    if durations.status != TEMPORAL_OK:
        return _no_path(durations.status, source, target)
    if target < 0 or target >= n_nodes:
        return _no_path(TEMPORAL_ERR_TARGET_OUT_OF_RANGE, source, target)
    if not durations.reached[target]:
        return _no_path(TEMPORAL_OK, source, target)
    if target == source:
        var here = List[Int]()
        here.append(source)
        var when = List[Float64]()
        when.append(TEMPORAL_ARRIVAL_FILLER)
        return TemporalPath(
            TEMPORAL_OK,
            True,
            source,
            target,
            0,
            TEMPORAL_ARRIVAL_FILLER,
            TEMPORAL_ARRIVAL_FILLER,
            0.0,
            here^,
            when^,
            List[Float64](),
        )
    # Re-run the scan at the winning departure time: the journey it finds is the fastest
    # one, because starting exactly then makes its arrival the earliest possible.
    var arr = temporal_earliest_arrival(
        src, dst, weight, time, n_nodes, source, durations.departure[target]
    )
    if arr.status != TEMPORAL_OK:
        return _no_path(arr.status, source, target)
    return _reconstruct(arr, target, time)


# ── reachability ──────────────────────────────────────────────────────────────


fn temporal_reachable_set(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
    source: Int,
    start_time: Float64,
) -> TemporalIntsResult:
    """Ascending ids of every node some journey from `source` can reach, `source` included.

    The source is in the set because a journey of zero edges is a journey. This set is
    *not* the static reachable set and is not closed under composition — see
    `temporal_static_gap` for the difference, by node.
    """
    var arr = temporal_earliest_arrival(
        src, dst, weight, time, n_nodes, source, start_time
    )
    if arr.status != TEMPORAL_OK:
        return TemporalIntsResult(arr.status, 0, List[Int]())
    var values = List[Int]()
    for v in range(arr.n_nodes):
        if arr.reached[v]:
            values.append(v)
    var count = len(values)
    return TemporalIntsResult(TEMPORAL_OK, count, values^)


fn temporal_reaches(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
    source: Int,
    target: Int,
    start_time: Float64,
) -> Bool:
    """True only when a real journey from `source` reaches `target` at or after `start_time`.

    False also covers a rejected request and an out-of-range endpoint, exactly as
    `adjacency.graph_csr_has_edge` does: this is the convenience form.
    `temporal_earliest_arrival` is the call that distinguishes "no journey" from "no
    graph".
    """
    var arr = temporal_earliest_arrival(
        src, dst, weight, time, n_nodes, source, start_time
    )
    if arr.status != TEMPORAL_OK:
        return False
    if target < 0 or target >= arr.n_nodes:
        return False
    return arr.reached[target]


fn temporal_static_gap(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
    source: Int,
    start_time: Float64,
) -> TemporalGap:
    """The nodes a static reachability answer claims and no journey can reach.

    Both answers are computed from the one edge set: the temporal one by the scan here,
    the static one by `adjacency.graph_bfs_levels_from_triplets` with the timestamps
    ignored. `false_positive_count > 0` means any static cache, closure or index built over
    these edges is already answering a reachability question wrongly.

    The static side cannot be a subset the other way round: dropping the time constraint
    only adds journeys, so `static_reached_count >= temporal_reached_count` always.
    """
    var arr = temporal_earliest_arrival(
        src, dst, weight, time, n_nodes, source, start_time
    )
    if arr.status != TEMPORAL_OK:
        return TemporalGap(arr.status, n_nodes, source, 0, 0, 0, List[Int]())
    var levels = graph_bfs_levels_from_triplets(src, dst, weight, n_nodes, source)
    if levels.status != GRAPH_OK or len(levels.reached) != n_nodes:
        return TemporalGap(
            TEMPORAL_ERR_STATIC_REJECTED, n_nodes, source, arr.reached_count, 0, 0,
            List[Int](),
        )
    var false_positives = List[Int]()
    var static_count = 0
    for v in range(n_nodes):
        if not levels.reached[v]:
            continue
        static_count += 1
        if not arr.reached[v]:
            false_positives.append(v)
    var count = len(false_positives)
    return TemporalGap(
        TEMPORAL_OK,
        n_nodes,
        source,
        arr.reached_count,
        static_count,
        count,
        false_positives^,
    )


# ── streams and windows ───────────────────────────────────────────────────────


fn _no_stream(status: Int, n_nodes: Int) -> TemporalStream:
    return TemporalStream(
        status,
        n_nodes,
        0,
        0,
        0,
        0,
        False,
        0.0,
        0.0,
        List[Int](),
        List[Int](),
        List[Float64](),
        List[Float64](),
    )


fn _stream_from_order(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
    order: List[Int],
    skipped: Int,
    dropped_before: Int,
    dropped_after: Int,
    windowed: Bool,
    window_start: Float64,
    window_end: Float64,
) -> TemporalStream:
    var osrc = List[Int]()
    var odst = List[Int]()
    var oweight = List[Float64]()
    var otime = List[Float64]()
    for p in range(len(order)):
        var k = order[p]
        osrc.append(src[k])
        odst.append(dst[k])
        oweight.append(weight[k])
        otime.append(time[k])
    var kept = len(osrc)
    return TemporalStream(
        TEMPORAL_OK,
        n_nodes,
        kept,
        skipped,
        dropped_before,
        dropped_after,
        windowed,
        window_start,
        window_end,
        osrc^,
        odst^,
        oweight^,
        otime^,
    )


fn temporal_sorted_by_time(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
) -> TemporalStream:
    """The edges of this graph as one stream, non-decreasing by departure time.

    Out-of-range endpoints are dropped and counted; nothing else is filtered, so
    `window_start`/`window_end` are the observed first and last timestamp and `windowed`
    is False. This is the primitive every driver here scans, exposed because a caller that
    wants to page through its own events needs the same order the answers were computed
    in.
    """
    var status = temporal_validate(src, dst, weight, time, n_nodes)
    if status != TEMPORAL_OK:
        return _no_stream(status, 0)
    var keep = _in_range_edges(src, dst, n_nodes)
    var skipped = len(src) - len(keep)
    var order = _time_order(keep, time)
    var first: Float64 = 0.0
    var last: Float64 = 0.0
    if len(order) > 0:
        first = time[order[0]]
        last = time[order[len(order) - 1]]
    return _stream_from_order(
        src, dst, weight, time, n_nodes, order, skipped, 0, 0, False, first, last
    )


fn temporal_window_subgraph(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
    window_start: Float64,
    window_end: Float64,
) -> TemporalStream:
    """The edges departing inside the half-open window `[window_start, window_end)`.

    Half-open, so an edge at exactly `window_start` is kept and one at exactly
    `window_end` is not. That is what lets consecutive windows tile a timeline with no
    event counted twice and none lost; a closed window would double-count every event on
    a shared boundary, and the totals would still look plausible.

    An edge's *departure* decides membership, not its arrival: an edge departing just
    inside the window may arrive long after it, and truncating that arrival would invent a
    journey nobody can take. `window_start == window_end` is the legal empty window.
    """
    var status = temporal_validate(src, dst, weight, time, n_nodes)
    if status != TEMPORAL_OK:
        return _no_stream(status, 0)
    var wstatus = _window_status(window_start, window_end)
    if wstatus != TEMPORAL_OK:
        return _no_stream(wstatus, n_nodes)
    var keep = List[Int]()
    var skipped = 0
    var dropped_before = 0
    var dropped_after = 0
    for k in range(len(src)):
        if src[k] < 0 or src[k] >= n_nodes or dst[k] < 0 or dst[k] >= n_nodes:
            skipped += 1
            continue
        var t = time[k]
        if t < window_start:
            dropped_before += 1
            continue
        if t >= window_end:
            dropped_after += 1
            continue
        keep.append(k)
    var order = _time_order(keep, time)
    return _stream_from_order(
        src,
        dst,
        weight,
        time,
        n_nodes,
        order,
        skipped,
        dropped_before,
        dropped_after,
        True,
        window_start,
        window_end,
    )


# ── activity and burstiness ───────────────────────────────────────────────────


fn _no_activity(status: Int) -> TemporalActivity:
    return TemporalActivity(
        status,
        0,
        0,
        0,
        0,
        0,
        False,
        0.0,
        0.0,
        0.0,
        False,
        0.0,
        0.0,
        0.0,
        False,
        0.0,
        False,
        0.0,
        False,
        0.0,
        List[Float64](),
    )


fn _activity_of(
    time: List[Float64], order: List[Int], skipped: Int
) -> TemporalActivity:
    """Summarise the timestamps `order` selects, in that (ascending) order.

    Every derived statistic is flagged rather than defaulted, because the frozen
    `math_ext` reductions answer `0.0` for an empty or single-element sample and `0.0` is
    a plausible-looking regularity claim.
    """
    var n_events = len(order)
    if n_events == 0:
        var empty = _no_activity(TEMPORAL_OK)
        empty.skipped_edges = skipped
        return empty^

    var t_min = time[order[0]]
    var t_max = time[order[n_events - 1]]
    var gaps = List[Float64]()
    var distinct = 1
    var simultaneous = 0
    for p in range(1, n_events):
        var gap = time[order[p]] - time[order[p - 1]]
        gaps.append(gap)
        if gap == 0.0:
            simultaneous += 1
        else:
            distinct += 1

    var n_gaps = len(gaps)
    var min_gap: Float64 = 0.0
    var max_gap: Float64 = 0.0
    var mu: Float64 = 0.0
    var has_interarrival = n_gaps >= 1
    if has_interarrival:
        min_gap = gaps[0]
        max_gap = gaps[0]
        for i in range(1, n_gaps):
            if gaps[i] < min_gap:
                min_gap = gaps[i]
            if gaps[i] > max_gap:
                max_gap = gaps[i]
        mu = mean(gaps)

    # A sample standard deviation of one observation does not exist; the frozen kernel
    # reports 0.0 for it, which is the number this flag exists to disown.
    var has_dispersion = n_gaps >= 2
    var sigma: Float64 = 0.0
    if has_dispersion:
        sigma = stdev(gaps)
    var has_cv = has_dispersion and mu > 0.0
    var cv: Float64 = 0.0
    if has_cv:
        cv = sigma / mu
    var has_burstiness = has_dispersion and (sigma + mu) > 0.0
    var burstiness: Float64 = 0.0
    if has_burstiness:
        burstiness = (sigma - mu) / (sigma + mu)

    return TemporalActivity(
        TEMPORAL_OK,
        skipped,
        n_events,
        n_gaps,
        distinct,
        simultaneous,
        True,
        t_min,
        t_max,
        t_max - t_min,
        has_interarrival,
        mu,
        min_gap,
        max_gap,
        has_dispersion,
        sigma,
        has_cv,
        cv,
        has_burstiness,
        burstiness,
        gaps^,
    )


fn temporal_activity_summary(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
) -> TemporalActivity:
    """When this graph's edges fired, and how bursty that stream is.

    Burstiness is `(sigma - mu) / (sigma + mu)` over the gaps between consecutive events:
    `-1` for a perfectly periodic stream, `0` for Poisson-like, approaching `+1` for
    events arriving in tight clusters separated by long silences. It is bounded and unitless
    where the raw standard deviation is neither, which is why it is the reported statistic;
    `coefficient_of_variation` is the unbounded sibling, kept because it is what a queueing
    model wants.
    """
    var status = temporal_validate(src, dst, weight, time, n_nodes)
    if status != TEMPORAL_OK:
        return _no_activity(status)
    var keep = _in_range_edges(src, dst, n_nodes)
    var skipped = len(src) - len(keep)
    return _activity_of(time, _time_order(keep, time), skipped)


fn temporal_node_activity(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    time: List[Float64],
    n_nodes: Int,
    node: Int,
) -> TemporalActivity:
    """The same summary over the edges incident on one node, in or out.

    Both directions, because a node's activity is when it was involved at all — a
    receive-only node with a bursty inbox has bursty activity, and an out-edge-only view
    would call it silent.
    """
    var status = temporal_validate(src, dst, weight, time, n_nodes)
    if status != TEMPORAL_OK:
        return _no_activity(status)
    if n_nodes == 0:
        return _no_activity(TEMPORAL_ERR_EMPTY_GRAPH)
    if node < 0 or node >= n_nodes:
        return _no_activity(TEMPORAL_ERR_NODE_OUT_OF_RANGE)
    var keep = List[Int]()
    var skipped = 0
    for k in range(len(src)):
        if src[k] < 0 or src[k] >= n_nodes or dst[k] < 0 or dst[k] >= n_nodes:
            skipped += 1
            continue
        if src[k] == node or dst[k] == node:
            keep.append(k)
    return _activity_of(time, _time_order(keep, time), skipped)
