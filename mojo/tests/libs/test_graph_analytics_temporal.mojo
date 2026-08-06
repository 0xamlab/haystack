"""test_graph_analytics_temporal.mojo — known-value tests for time-respecting journeys.

Hand-written. The assertions target the failures that are silent rather than loud:

* the headline one — temporal reachability is **not transitive**, so a static algorithm on
  timestamped edges answers confidently and wrongly. `0 -> 1` at `t = 5` and `1 -> 2` at
  `t = 3` leaves node 2 unreachable, and the frozen
  `graph.weighted.shortest_path_dijkstra` is asserted to return a finite `2.0` for it
  while this module returns absent. Both numbers are checked, because "we refuse this"
  only means something if the alternative is shown to be wrong.
* a half-open window boundary. An edge at exactly `window_end` is out and one at exactly
  `window_start` is in; a one-instant slip either includes or drops a whole day of events
  and every downstream count still looks plausible, so both boundaries and the drop
  accounting are asserted.
* an unreachable node whose arrival filler `-1.0` collides with a *real* arrival of
  `-1.0`, on a graph with negative timestamps. `reached` is the only authority for an
  arrival time; the marker is real only for a duration.
* edge order inside one timestamp. Reversing the input edge order must not change a single
  arrival or hop count — a same-timestamp chain missed by a bad order is the classic
  one-pass bug.
* frozen reductions that answer `0.0` when they have no answer: `math_ext.stdev` of a
  single gap is `0.0`, which reads as "perfectly regular", and `has_dispersion` is
  asserted False for exactly that sample.

Two frozen kernels are the differential oracles, so the numbers here are not just this
file agreeing with itself:

* `graph.weighted.shortest_path_dijkstra` with unit weights is hop-count reachability. On
  a graph where every edge shares one timestamp and every duration is zero, the temporal
  answer must *become* the static one: `reached[v]` iff its distance is below `1e18`, and
  `hops[v]` equal to that distance exactly. On the non-transitive graph the same oracle
  must disagree, and does.
* `math_ext.mean` and `math_ext.stdev` are the oracles for the inter-arrival summary — the
  gap list is rebuilt by hand here and pushed through the frozen reductions rather than
  comparing against a number typed into this file.
"""
from sparse_numerics.csr import MAX_CSR_DIM
from std.math import abs as fabs

from graph.weighted import WeightedEdge, shortest_path_dijkstra
from graph_analytics.temporal import (
    TEMPORAL_MAX_NODES,
    TEMPORAL_ARRIVAL_FILLER,
    TEMPORAL_ERR_EMPTY_GRAPH,
    TEMPORAL_ERR_INVALID_DIMENSIONS,
    TEMPORAL_ERR_LENGTH_MISMATCH,
    TEMPORAL_ERR_NEGATIVE_DURATION,
    TEMPORAL_ERR_NODE_OUT_OF_RANGE,
    TEMPORAL_ERR_NON_FINITE_DURATION,
    TEMPORAL_ERR_NON_FINITE_TIME,
    TEMPORAL_ERR_SOURCE_OUT_OF_RANGE,
    TEMPORAL_ERR_TARGET_OUT_OF_RANGE,
    TEMPORAL_ERR_WINDOW_INVALID,
    TEMPORAL_NO_DURATION,
    TEMPORAL_OK,
    temporal_activity_summary,
    temporal_earliest_arrival,
    temporal_earliest_arrival_instant,
    temporal_earliest_arrival_path,
    temporal_earliest_arrival_window,
    temporal_fastest_durations,
    temporal_fastest_path,
    temporal_node_activity,
    temporal_reachable_set,
    temporal_reaches,
    temporal_sorted_by_time,
    temporal_static_gap,
    temporal_status_name,
    temporal_validate,
    temporal_validate_driver,
    temporal_window_subgraph,
)
from math_ext import mean, stdev

comptime TOL: Float64 = 1e-12


def _close(a: Float64, b: Float64) -> Bool:
    return fabs(a - b) <= 1e-9


def _ints3(a: Int, b: Int, c: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


def _floats3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


def _zeros(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(n):
        out.append(0.0)
    return out^


def _ones(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(n):
        out.append(1.0)
    return out^


def _reversed_ints(values: List[Int]) -> List[Int]:
    var out = List[Int]()
    var i = len(values) - 1
    while i >= 0:
        out.append(values[i])
        i -= 1
    return out^


def _reversed_floats(values: List[Float64]) -> List[Float64]:
    var out = List[Float64]()
    var i = len(values) - 1
    while i >= 0:
        out.append(values[i])
        i -= 1
    return out^


def _frozen_edges(
    src: List[Int], dst: List[Int], weight: List[Float64]
) -> List[WeightedEdge]:
    """The same edge set as a frozen triplet list, so the oracle sees identical input."""
    var edges = List[WeightedEdge]()
    for k in range(len(src)):
        edges.append(WeightedEdge(src[k], dst[k], weight[k]))
    return edges^


# ── the 5-node hand-computed example ──────────────────────────────────────────
# idx  src dst duration time      note
#   0   0   1     2       1       arrive 1 at t=3
#   1   0   2     1       2       arrive 2 at t=3
#   2   1   3     1       2       unusable: we are at 1 only at t=3 > 2
#   3   1   3     1       4       arrive 3 at t=5, worse than via node 2
#   4   2   3     1       3       arrive 3 at t=4
#   5   3   4     1       3       unusable: we are at 3 only at t=4 > 3
#   6   3   4     2       6       arrive 4 at t=8
#   7   2   4     1      10       arrive 4 at t=11, worse
#   8   0   4    10       0       arrive 4 at t=10, worse
#   9   0   4     1      20       arrive 4 at t=21 — the FASTEST journey, not the earliest


def _g5_src() -> List[Int]:
    var out = List[Int]()
    out.append(0)
    out.append(0)
    out.append(1)
    out.append(1)
    out.append(2)
    out.append(3)
    out.append(3)
    out.append(2)
    out.append(0)
    out.append(0)
    return out^


def _g5_dst() -> List[Int]:
    var out = List[Int]()
    out.append(1)
    out.append(2)
    out.append(3)
    out.append(3)
    out.append(3)
    out.append(4)
    out.append(4)
    out.append(4)
    out.append(4)
    out.append(4)
    return out^


def _g5_duration() -> List[Float64]:
    var out = List[Float64]()
    out.append(2.0)
    out.append(1.0)
    out.append(1.0)
    out.append(1.0)
    out.append(1.0)
    out.append(1.0)
    out.append(2.0)
    out.append(1.0)
    out.append(10.0)
    out.append(1.0)
    return out^


def _g5_time() -> List[Float64]:
    var out = List[Float64]()
    out.append(1.0)
    out.append(2.0)
    out.append(2.0)
    out.append(4.0)
    out.append(3.0)
    out.append(3.0)
    out.append(6.0)
    out.append(10.0)
    out.append(0.0)
    out.append(20.0)
    return out^


# ── the single-timestamp graph: every edge at t=7, every duration 0 ───────────
# 0->1, 1->2, 2->3, 0->4, 4->2, 5->0. Node 5 reaches 0 but 0 never reaches 5, so the
# frozen oracle's `1e18` and the temporal `reached == False` must line up.


def _flat_src() -> List[Int]:
    var out = List[Int]()
    out.append(0)
    out.append(1)
    out.append(2)
    out.append(0)
    out.append(4)
    out.append(5)
    return out^


def _flat_dst() -> List[Int]:
    var out = List[Int]()
    out.append(1)
    out.append(2)
    out.append(3)
    out.append(4)
    out.append(2)
    out.append(0)
    return out^


def main() raises:
    var passed = 0
    var failed = 0
    print("[graph_analytics.temporal] known-value tests")

    # ── temporal reachability is NOT transitive, and the frozen kernel is wrong ──
    # 0 -> 1 at t=5, 1 -> 2 at t=3. The only edge out of node 1 left two units before
    # anything could arrive at node 1, so node 2 is unreachable. The static graph says
    # otherwise, and says it with a number.
    var nt_src = _ints3(0, 1, 0)
    var nt_dst = _ints3(1, 2, 0)
    var nt_time = _floats3(5.0, 3.0, 0.0)
    var nt_dur = _zeros(3)
    # The third entry is a 0->0 self-loop at t=0, present so the graph is not a bare pair
    # and a self-loop cannot smuggle in a chain.
    var nt = temporal_earliest_arrival(nt_src, nt_dst, nt_dur, nt_time, 3, 0, 0.0)
    var nt_set = temporal_reachable_set(nt_src, nt_dst, nt_dur, nt_time, 3, 0, 0.0)
    var nt_gap = temporal_static_gap(nt_src, nt_dst, nt_dur, nt_time, 3, 0, 0.0)
    var frozen_static = shortest_path_dijkstra(3, _frozen_edges(nt_src, nt_dst, _ones(3)), 0)
    if (
        nt.status == TEMPORAL_OK
        and nt.reached[0]
        and nt.reached[1]
        and _close(nt.arrival[1], 5.0)
        and not nt.reached[2]
        and nt.reached_count == 2
        and nt.unreachable_count == 1
        and nt_set.length == 2
        and nt_set.values[0] == 0
        and nt_set.values[1] == 1
        and not temporal_reaches(nt_src, nt_dst, nt_dur, nt_time, 3, 0, 2, 0.0)
        and temporal_reaches(nt_src, nt_dst, nt_dur, nt_time, 3, 0, 1, 0.0)
        and nt_gap.status == TEMPORAL_OK
        and nt_gap.static_reached_count == 3
        and nt_gap.temporal_reached_count == 2
        and nt_gap.false_positive_count == 1
        and nt_gap.false_positives[0] == 2
        # the oracle's confidently wrong answer: two hops to a node no journey reaches
        and _close(frozen_static[2], 2.0)
    ):
        passed += 1
        print("  ✅ A->B at t=5, B->C at t=3: C unreachable, while frozen dijkstra says 2.0")
    else:
        failed += 1
        print(
            "  ❌ non-transitivity mishandled:",
            nt.reached_count,
            nt_gap.false_positive_count,
            frozen_static[2],
        )

    # ── earliest arrival on the hand-computed 5-node example ─────────────────
    var src = _g5_src()
    var dst = _g5_dst()
    var dur = _g5_duration()
    var tm = _g5_time()
    var ea = temporal_earliest_arrival(src, dst, dur, tm, 5, 0, 0.0)
    if (
        ea.status == TEMPORAL_OK
        and ea.reached_count == 5
        and ea.unreachable_count == 0
        and ea.skipped_edges == 0
        and ea.usable_edges == 10
        and _close(ea.arrival[0], 0.0)
        and _close(ea.arrival[1], 3.0)
        and _close(ea.arrival[2], 3.0)
        and _close(ea.arrival[3], 4.0)
        and _close(ea.arrival[4], 8.0)
        and ea.hops[0] == 0
        and ea.hops[1] == 1
        and ea.hops[2] == 1
        and ea.hops[3] == 2
        and ea.hops[4] == 3
        and ea.predecessor[3] == 2
        and ea.predecessor[4] == 3
        and ea.predecessor_edge[4] == 6
    ):
        passed += 1
        print("  ✅ earliest arrival [0,3,3,4,8] with hops [0,1,1,2,3]")
    else:
        failed += 1
        print(
            "  ❌ earliest arrival wrong:",
            ea.arrival[1],
            ea.arrival[2],
            ea.arrival[3],
            ea.arrival[4],
        )

    # ── the journey behind it, and the two invariants that make it time-respecting ──
    var path = temporal_earliest_arrival_path(src, dst, dur, tm, 5, 0, 4, 0.0)
    var respecting = path.found and len(path.departure_times) == path.hops
    for i in range(len(path.departure_times)):
        if path.arrival_times[i] > path.departure_times[i]:
            respecting = False
        if i > 0 and path.departure_times[i] < path.departure_times[i - 1]:
            respecting = False
    if (
        path.status == TEMPORAL_OK
        and path.found
        and path.hops == 3
        and len(path.nodes) == 4
        and path.nodes[0] == 0
        and path.nodes[1] == 2
        and path.nodes[2] == 3
        and path.nodes[3] == 4
        and _close(path.arrival_times[1], 3.0)
        and _close(path.arrival_times[3], 8.0)
        and _close(path.departure_times[0], 2.0)
        and _close(path.departure_times[1], 3.0)
        and _close(path.departure_times[2], 6.0)
        and _close(path.departure_time, 2.0)
        and _close(path.arrival_time, 8.0)
        and _close(path.duration, 6.0)
        and respecting
    ):
        passed += 1
        print("  ✅ journey 0->2->3->4 departs 2,3,6 and every arrival precedes its next departure")
    else:
        failed += 1
        print("  ❌ path wrong:", path.hops, path.departure_time, path.arrival_time, respecting)

    # ── a later start removes journeys, which no static answer can express ──
    var late = temporal_earliest_arrival(src, dst, dur, tm, 5, 0, 2.5)
    if (
        late.status == TEMPORAL_OK
        and late.reached_count == 2
        and late.reached[0]
        and late.reached[4]
        and not late.reached[1]
        and not late.reached[2]
        and not late.reached[3]
        and _close(late.arrival[4], 21.0)
        and late.usable_edges == 6
        and _close(late.arrival[1], TEMPORAL_ARRIVAL_FILLER)
    ):
        passed += 1
        print("  ✅ start_time 2.5 strands nodes 1,2,3 that start_time 0 reaches")
    else:
        failed += 1
        print("  ❌ start_time gating wrong:", late.reached_count, late.arrival[4])

    # ── fastest is a different question from earliest, and a different journey ──
    # Node 4 is reachable by t=8 (leaving at t=2, six units elapsed) but the 20.0 edge
    # gets there in one unit while arriving thirteen units later.
    var fastest = temporal_fastest_durations(src, dst, dur, tm, 5, 0)
    var fpath = temporal_fastest_path(src, dst, dur, tm, 5, 0, 4)
    if (
        fastest.status == TEMPORAL_OK
        and fastest.reached_count == 5
        and fastest.starts_tried == 4
        and _close(fastest.duration[0], 0.0)
        and _close(fastest.duration[1], 2.0)
        and _close(fastest.duration[2], 1.0)
        and _close(fastest.duration[3], 2.0)
        and _close(fastest.duration[4], 1.0)
        and _close(fastest.departure[1], 1.0)
        and _close(fastest.departure[2], 2.0)
        and _close(fastest.departure[4], 20.0)
        and fpath.found
        and fpath.hops == 1
        and _close(fpath.departure_time, 20.0)
        and _close(fpath.arrival_time, 21.0)
        and _close(fpath.duration, 1.0)
        # the earliest arrival is much sooner and much slower
        and _close(ea.arrival[4], 8.0)
        and fpath.arrival_time > ea.arrival[4]
        and fpath.duration < path.duration
    ):
        passed += 1
        print("  ✅ fastest to 4 is 1 unit arriving at 21; earliest arrival is 8 taking 6")
    else:
        failed += 1
        print(
            "  ❌ fastest wrong:",
            fastest.duration[1],
            fastest.duration[4],
            fpath.duration,
            fpath.arrival_time,
        )

    # ── one timestamp for every edge, zero durations: the static answer, exactly ──
    # The frozen unit-weight dijkstra is hop-count reachability; here `hops` must equal it
    # node for node, and its `1e18` must line up with `reached == False`.
    var fsrc = _flat_src()
    var fdst = _flat_dst()
    var flat_time = List[Float64]()
    for _ in range(6):
        flat_time.append(7.0)
    var flat = temporal_earliest_arrival(fsrc, fdst, _zeros(6), flat_time, 6, 0, 0.0)
    var frozen_hops = shortest_path_dijkstra(6, _frozen_edges(fsrc, fdst, _ones(6)), 0)
    var agrees = flat.status == TEMPORAL_OK and len(flat.reached) == 6
    for v in range(6):
        var static_reachable = frozen_hops[v] < 1e18
        if static_reachable != flat.reached[v]:
            agrees = False
        if static_reachable and Float64(flat.hops[v]) != frozen_hops[v]:
            agrees = False
        if flat.reached[v] and v != 0 and not _close(flat.arrival[v], 7.0):
            agrees = False
    # Reversing the input order must not move a single number: a same-timestamp chain
    # missed by a bad edge order is the classic one-pass bug.
    var rflat = temporal_earliest_arrival(
        _reversed_ints(fsrc), _reversed_ints(fdst), _zeros(6), flat_time, 6, 0, 0.0
    )
    var order_stable = rflat.status == TEMPORAL_OK
    for v in range(6):
        if rflat.reached[v] != flat.reached[v] or rflat.hops[v] != flat.hops[v]:
            order_stable = False
        if not _close(rflat.arrival[v], flat.arrival[v]):
            order_stable = False
    if (
        agrees
        and order_stable
        and flat.hops[3] == 3
        and flat.hops[2] == 2
        and not flat.reached[5]
        and frozen_hops[5] == 1e18
    ):
        passed += 1
        print("  ✅ one shared timestamp reproduces the frozen hop counts, in any edge order")
    else:
        failed += 1
        print(
            "  ❌ single-timestamp graph diverged:",
            agrees,
            order_stable,
            flat.hops[3],
            frozen_hops[5],
        )

    # ── positive durations are order-independent too ─────────────────────────
    var rev = temporal_earliest_arrival(
        _reversed_ints(src),
        _reversed_ints(dst),
        _reversed_floats(dur),
        _reversed_floats(tm),
        5,
        0,
        0.0,
    )
    var g5_stable = rev.status == TEMPORAL_OK
    for v in range(5):
        if not _close(rev.arrival[v], ea.arrival[v]):
            g5_stable = False
        if rev.hops[v] != ea.hops[v] or rev.reached[v] != ea.reached[v]:
            g5_stable = False
    if g5_stable:
        passed += 1
        print("  ✅ reversing the 5-node edge order changes no arrival and no hop count")
    else:
        failed += 1
        print("  ❌ answer depends on input edge order:", rev.arrival[4], rev.hops[4])

    # ── the window is half-open: t == window_end is OUT, t == window_start is IN ──
    var w_src = _ints3(0, 1, 1)
    var w_dst = _ints3(1, 2, 2)
    var w_time = _floats3(10.0, 20.0, 30.0)
    var w_dur = _zeros(3)
    var closed_at_20 = temporal_window_subgraph(w_src, w_dst, w_dur, w_time, 3, 10.0, 20.0)
    var open_past_20 = temporal_window_subgraph(w_src, w_dst, w_dur, w_time, 3, 10.0, 20.5)
    var starts_at_11 = temporal_window_subgraph(w_src, w_dst, w_dur, w_time, 3, 11.0, 31.0)
    var empty_window = temporal_window_subgraph(w_src, w_dst, w_dur, w_time, 3, 10.0, 10.0)
    var accounted = (
        closed_at_20.n_edges
        + closed_at_20.skipped_edges
        + closed_at_20.dropped_before
        + closed_at_20.dropped_after
        == 3
    )
    if (
        closed_at_20.status == TEMPORAL_OK
        and closed_at_20.n_edges == 1
        and _close(closed_at_20.time[0], 10.0)
        and closed_at_20.dropped_before == 0
        and closed_at_20.dropped_after == 2
        and closed_at_20.windowed
        and accounted
        and open_past_20.n_edges == 2
        and _close(open_past_20.time[1], 20.0)
        and starts_at_11.n_edges == 2
        and starts_at_11.dropped_before == 1
        and starts_at_11.dropped_after == 0
        and empty_window.status == TEMPORAL_OK
        and empty_window.n_edges == 0
        and empty_window.dropped_after == 3
    ):
        passed += 1
        print("  ✅ [10,20) keeps t=10 and drops t=20; [10,20.5) keeps both; [10,10) is empty")
    else:
        failed += 1
        print(
            "  ❌ window boundary wrong:",
            closed_at_20.n_edges,
            closed_at_20.dropped_after,
            open_past_20.n_edges,
            starts_at_11.dropped_before,
        )

    # ── that one instant is the difference between reachable and not ─────────
    var in_window = temporal_earliest_arrival_window(
        w_src, w_dst, w_dur, w_time, 3, 0, 0.0, 10.0, 20.0
    )
    var wider = temporal_earliest_arrival_window(
        w_src, w_dst, w_dur, w_time, 3, 0, 0.0, 10.0, 20.5
    )
    var bad_window = temporal_earliest_arrival_window(
        w_src, w_dst, w_dur, w_time, 3, 0, 0.0, 20.0, 10.0
    )
    var infinite_bound = temporal_window_subgraph(
        w_src, w_dst, w_dur, w_time, 3, 10.0, 1e308 * 1e308
    )
    if (
        in_window.status == TEMPORAL_OK
        and in_window.reached[1]
        and not in_window.reached[2]
        and wider.reached[2]
        and _close(wider.arrival[2], 20.0)
        and bad_window.status == TEMPORAL_ERR_WINDOW_INVALID
        and len(bad_window.arrival) == 0
        and infinite_bound.status == TEMPORAL_ERR_WINDOW_INVALID
        and temporal_status_name(TEMPORAL_ERR_WINDOW_INVALID)
        == "window_end_before_start_or_non_finite"
    ):
        passed += 1
        print("  ✅ excluding the boundary edge makes node 2 unreachable, not slower")
    else:
        failed += 1
        print(
            "  ❌ windowed reachability wrong:",
            in_window.reached[2],
            wider.reached[2],
            bad_window.status,
        )

    # ── -1.0 is a real arrival time, so `reached` is the only authority ──────
    # Edge 0->1 departs at t=-3 and takes 2, arriving at exactly -1.0 — the same value the
    # unreached node 2 carries as a filler. A caller that reads `arrival` alone cannot tell
    # them apart; that is why the filler is documented as carrying no information.
    var neg_src = _ints3(0, 0, 0)
    var neg_dst = _ints3(1, 1, 1)
    var neg_time = _floats3(-3.0, -3.0, -3.0)
    var neg_dur = _floats3(2.0, 2.0, 2.0)
    var neg = temporal_earliest_arrival(neg_src, neg_dst, neg_dur, neg_time, 3, 0, -10.0)
    var neg_fast = temporal_fastest_durations(neg_src, neg_dst, neg_dur, neg_time, 3, 0)
    if (
        neg.status == TEMPORAL_OK
        and neg.reached[1]
        and _close(neg.arrival[1], -1.0)
        and not neg.reached[2]
        and _close(neg.arrival[2], TEMPORAL_ARRIVAL_FILLER)
        and _close(TEMPORAL_ARRIVAL_FILLER, -1.0)
        # a duration, unlike a timestamp, cannot be -1.0, so there the marker is real
        and _close(neg_fast.duration[1], 2.0)
        and _close(neg_fast.duration[2], TEMPORAL_NO_DURATION)
        and not neg_fast.reached[2]
    ):
        passed += 1
        print("  ✅ a real arrival of -1.0 and an absent one are separated by `reached`")
    else:
        failed += 1
        print("  ❌ filler collision mishandled:", neg.arrival[1], neg.arrival[2], neg.reached[2])

    # ── a negative duration is refused, and NaN is caught before the sign test ──
    # `nan < 0.0` is False, so a bare negativity check would let a NaN duration into the
    # scan, where every comparison against it is False.
    var bad_dur = _floats3(1.0, -1.0, 1.0)
    var nan_dur = _floats3(1.0, Float64(0.0) / Float64(0.0), 1.0)
    var inf_time = _floats3(1.0, 1e308 * 1e308, 3.0)
    var nan_start = temporal_earliest_arrival(
        w_src, w_dst, w_dur, w_time, 3, 0, Float64(0.0) / Float64(0.0)
    )
    var negative = temporal_earliest_arrival(w_src, w_dst, bad_dur, w_time, 3, 0, 0.0)
    var nan_result = temporal_earliest_arrival(w_src, w_dst, nan_dur, w_time, 3, 0, 0.0)
    var inf_result = temporal_earliest_arrival(w_src, w_dst, w_dur, inf_time, 3, 0, 0.0)
    if (
        negative.status == TEMPORAL_ERR_NEGATIVE_DURATION
        and len(negative.arrival) == 0
        and negative.reached_count == 0
        and nan_result.status == TEMPORAL_ERR_NON_FINITE_DURATION
        and len(nan_result.reached) == 0
        and inf_result.status == TEMPORAL_ERR_NON_FINITE_TIME
        and nan_start.status == TEMPORAL_ERR_NON_FINITE_TIME
        and temporal_validate_driver(w_src, w_dst, bad_dur, w_time, 3)
        == "negative_duration_arrival_before_departure"
        and temporal_validate_driver(w_src, w_dst, w_dur, w_time, 3) == "ok"
    ):
        passed += 1
        print("  ✅ negative, NaN and infinite durations/times are refused with no numbers")
    else:
        failed += 1
        print(
            "  ❌ non-finite input leaked:",
            negative.status,
            nan_result.status,
            inf_result.status,
            nan_start.status,
        )

    # ── an endpoint this graph does not have is skipped and counted, never indexed ──
    var stray_src = _ints3(0, 0, -1)
    var stray_dst = _ints3(1, 7, 2)
    var stray = temporal_earliest_arrival(
        stray_src, stray_dst, _zeros(3), _ones(3), 3, 0, 0.0
    )
    var stray_stream = temporal_sorted_by_time(
        stray_src, stray_dst, _zeros(3), _ones(3), 3
    )
    if (
        stray.status == TEMPORAL_OK
        and stray.skipped_edges == 2
        and stray.reached_count == 2
        and stray.reached[1]
        and not stray.reached[2]
        and stray_stream.skipped_edges == 2
        and stray_stream.n_edges == 1
    ):
        passed += 1
        print("  ✅ out-of-range endpoints are dropped and counted, not used as subscripts")
    else:
        failed += 1
        print("  ❌ stray endpoint mishandled:", stray.skipped_edges, stray.reached_count)

    # ── every structural rejection has its own code and no partial answer ────
    var mismatch = temporal_earliest_arrival(w_src, w_dst, _zeros(2), w_time, 3, 0, 0.0)
    var negative_n = temporal_earliest_arrival(w_src, w_dst, w_dur, w_time, -1, 0, 0.0)
    var no_nodes = temporal_earliest_arrival(
        List[Int](), List[Int](), List[Float64](), List[Float64](), 0, 0, 0.0
    )
    var bad_source = temporal_earliest_arrival(w_src, w_dst, w_dur, w_time, 3, 3, 0.0)
    var neg_source = temporal_earliest_arrival(w_src, w_dst, w_dur, w_time, 3, -1, 0.0)
    var bad_target = temporal_earliest_arrival_path(
        w_src, w_dst, w_dur, w_time, 3, 0, 9, 0.0
    )
    var bad_node = temporal_node_activity(w_src, w_dst, w_dur, w_time, 3, 9)
    var unreachable_target = temporal_earliest_arrival_path(
        nt_src, nt_dst, nt_dur, nt_time, 3, 0, 2, 0.0
    )
    if (
        mismatch.status == TEMPORAL_ERR_LENGTH_MISMATCH
        and negative_n.status == TEMPORAL_ERR_INVALID_DIMENSIONS
        and no_nodes.status == TEMPORAL_ERR_EMPTY_GRAPH
        and bad_source.status == TEMPORAL_ERR_SOURCE_OUT_OF_RANGE
        and neg_source.status == TEMPORAL_ERR_SOURCE_OUT_OF_RANGE
        and bad_target.status == TEMPORAL_ERR_TARGET_OUT_OF_RANGE
        and not bad_target.found
        and bad_node.status == TEMPORAL_ERR_NODE_OUT_OF_RANGE
        # an absent journey is not a rejected request: OK, found False, no partial path
        and unreachable_target.status == TEMPORAL_OK
        and not unreachable_target.found
        and len(unreachable_target.nodes) == 0
        and _close(unreachable_target.duration, TEMPORAL_NO_DURATION)
        and temporal_validate(w_src, w_dst, _zeros(2), w_time, 3)
        == TEMPORAL_ERR_LENGTH_MISMATCH
        and temporal_status_name(99) == "unknown_status"
    ):
        passed += 1
        print("  ✅ six rejection codes, and 'no journey' is not one of them")
    else:
        failed += 1
        print(
            "  ❌ rejection codes wrong:",
            mismatch.status,
            no_nodes.status,
            bad_target.status,
            unreachable_target.status,
        )

    # ── the sorted stream is a permutation, ascending, and self-describing ───
    var stream = temporal_sorted_by_time(src, dst, dur, tm, 5)
    var ascending = stream.status == TEMPORAL_OK and stream.n_edges == 10
    for p in range(1, len(stream.time)):
        if stream.time[p] < stream.time[p - 1]:
            ascending = False
    var permuted = True
    for p in range(len(stream.time)):
        var found_match = False
        for k in range(len(tm)):
            if (
                stream.src[p] == src[k]
                and stream.dst[p] == dst[k]
                and _close(stream.weight[p], dur[k])
                and _close(stream.time[p], tm[k])
            ):
                found_match = True
        if not found_match:
            permuted = False
    if (
        ascending
        and permuted
        and not stream.windowed
        and _close(stream.window_start, 0.0)
        and _close(stream.window_end, 20.0)
        and stream.dropped_before == 0
        and stream.dropped_after == 0
    ):
        passed += 1
        print("  ✅ the time-sorted stream is ascending and every edge survives it intact")
    else:
        failed += 1
        print("  ❌ stream wrong:", ascending, permuted, stream.window_end)

    # ── inter-arrival summary against the frozen reductions ──────────────────
    # Four events at t = 0, 1, 2, 10 → gaps 1, 1, 8.
    var act_src = List[Int]()
    var act_dst = List[Int]()
    var act_time = List[Float64]()
    act_src.append(0)
    act_dst.append(1)
    act_time.append(0.0)
    act_src.append(1)
    act_dst.append(0)
    act_time.append(1.0)
    act_src.append(0)
    act_dst.append(1)
    act_time.append(2.0)
    act_src.append(1)
    act_dst.append(0)
    act_time.append(10.0)
    var act = temporal_activity_summary(act_src, act_dst, _zeros(4), act_time, 2)
    var hand_gaps = _floats3(1.0, 1.0, 8.0)
    var oracle_mu = mean(hand_gaps)
    var oracle_sigma = stdev(hand_gaps)
    var oracle_b = (oracle_sigma - oracle_mu) / (oracle_sigma + oracle_mu)
    if (
        act.status == TEMPORAL_OK
        and act.n_events == 4
        and act.n_gaps == 3
        and act.distinct_times == 4
        and act.simultaneous_events == 0
        and act.has_span
        and _close(act.t_min, 0.0)
        and _close(act.t_max, 10.0)
        and _close(act.span, 10.0)
        and act.has_interarrival
        and fabs(act.mean_interarrival - oracle_mu) <= TOL
        and act.has_dispersion
        and fabs(act.stdev_interarrival - oracle_sigma) <= TOL
        and act.has_burstiness
        and fabs(act.burstiness - oracle_b) <= TOL
        and act.has_cv
        and fabs(act.coefficient_of_variation - oracle_sigma / oracle_mu) <= TOL
        and _close(act.min_gap, 1.0)
        and _close(act.max_gap, 8.0)
        and len(act.gaps) == 3
        and _close(act.gaps[2], 8.0)
        and act.burstiness > -1.0
        and act.burstiness < 1.0
        and _close(act.mean_interarrival, 10.0 / 3.0)
    ):
        passed += 1
        print("  ✅ gaps 1,1,8 match math_ext.mean/stdev and give burstiness", act.burstiness)
    else:
        failed += 1
        print(
            "  ❌ activity summary wrong:",
            act.mean_interarrival,
            act.stdev_interarrival,
            act.burstiness,
        )

    # ── the statistics that do not exist are flagged, not defaulted to 0.0 ───
    # The frozen `stdev` of one gap is 0.0, which reads as "perfectly regular". It is not
    # an answer, and `has_dispersion` says so.
    var one_gap = List[Float64]()
    one_gap.append(4.0)
    var two_events = temporal_activity_summary(
        _ints3(0, 1, 0), _ints3(1, 0, 0), _zeros(3), _floats3(0.0, 4.0, 0.0), 2
    )
    var one_event = temporal_activity_summary(
        _ints3(0, 5, 5), _ints3(1, 5, 5), _zeros(3), _floats3(9.0, 0.0, 0.0), 2
    )
    var no_events = temporal_activity_summary(
        List[Int](), List[Int](), List[Float64](), List[Float64](), 3
    )
    var simultaneous = temporal_activity_summary(
        _ints3(0, 0, 1), _ints3(1, 1, 0), _zeros(3), _floats3(5.0, 5.0, 5.0), 2
    )
    if (
        # two events give one gap: a mean exists, a sample deviation does not
        two_events.n_gaps == 2
        and _close(stdev(one_gap), 0.0)
        and one_event.n_events == 1
        and one_event.n_gaps == 0
        and not one_event.has_interarrival
        and not one_event.has_dispersion
        and one_event.has_span
        and _close(one_event.span, 0.0)
        and one_event.skipped_edges == 2
        and no_events.status == TEMPORAL_OK
        and no_events.n_events == 0
        and not no_events.has_span
        and not no_events.has_interarrival
        # every event at one instant: a mean gap of 0 has no CV and no burstiness
        and simultaneous.n_events == 3
        and simultaneous.n_gaps == 2
        and simultaneous.simultaneous_events == 2
        and simultaneous.distinct_times == 1
        and simultaneous.has_dispersion
        and not simultaneous.has_cv
        and not simultaneous.has_burstiness
        and _close(simultaneous.span, 0.0)
    ):
        passed += 1
        print("  ✅ one event, zero events and all-simultaneous events report absence, not 0.0")
    else:
        failed += 1
        print(
            "  ❌ absent statistics defaulted:",
            one_event.has_dispersion,
            no_events.has_span,
            simultaneous.has_burstiness,
        )

    # ── per-node activity sees both directions ──────────────────────────────
    var chain_act = temporal_node_activity(
        _ints3(0, 1, 2), _ints3(1, 2, 3), _zeros(3), _floats3(0.0, 1.0, 5.0), 4, 1
    )
    var leaf_act = temporal_node_activity(
        _ints3(0, 1, 2), _ints3(1, 2, 3), _zeros(3), _floats3(0.0, 1.0, 5.0), 4, 3
    )
    if (
        chain_act.status == TEMPORAL_OK
        and chain_act.n_events == 2
        and _close(chain_act.mean_interarrival, 1.0)
        and chain_act.has_interarrival
        and not chain_act.has_dispersion
        and leaf_act.n_events == 1
        and not leaf_act.has_interarrival
        and _close(leaf_act.t_min, 5.0)
    ):
        passed += 1
        print("  ✅ node activity counts in-edges and out-edges alike")
    else:
        failed += 1
        print("  ❌ node activity wrong:", chain_act.n_events, leaf_act.n_events)

    # ── instantaneous edges: the durations are materialised, not special-cased ──
    var instant = temporal_earliest_arrival_instant(fsrc, fdst, flat_time, 6, 0, 0.0)
    var same = instant.status == TEMPORAL_OK
    for v in range(6):
        if instant.reached[v] != flat.reached[v] or instant.hops[v] != flat.hops[v]:
            same = False
    if same and instant.reached_count == 5:
        passed += 1
        print("  ✅ the instant driver equals the explicit zero-duration scan")
    else:
        failed += 1
        print("  ❌ instant driver diverged:", instant.reached_count, flat.reached_count)

    # ── the generated A-Z argument pattern: five-element lists, every Int 5 ──
    # `tests/generate_mojo_tests.py` calls every contract function with `_li5`
    # ([1,2,3,4,5]), `_lf5` and 5 for each Int, 0.5 for each Float64. Any of these
    # indexing on faith would kill the worker for the whole suite, so the pattern is
    # asserted here rather than discovered in CI.
    var li5 = List[Int]()
    li5.append(1)
    li5.append(2)
    li5.append(3)
    li5.append(4)
    li5.append(5)
    var lf5 = List[Float64]()
    lf5.append(0.5)
    lf5.append(0.6)
    lf5.append(0.7)
    lf5.append(0.4)
    lf5.append(0.3)
    var az_ea = temporal_earliest_arrival(li5, li5, lf5, lf5, 5, 5, 0.5)
    var az_instant = temporal_earliest_arrival_instant(li5, li5, lf5, 5, 5, 0.5)
    var az_window = temporal_earliest_arrival_window(li5, li5, lf5, lf5, 5, 5, 0.5, 0.5, 0.5)
    var az_path = temporal_earliest_arrival_path(li5, li5, lf5, lf5, 5, 5, 5, 0.5)
    var az_fast = temporal_fastest_durations(li5, li5, lf5, lf5, 5, 5)
    var az_fpath = temporal_fastest_path(li5, li5, lf5, lf5, 5, 5, 5)
    var az_set = temporal_reachable_set(li5, li5, lf5, lf5, 5, 5, 0.5)
    var az_gap = temporal_static_gap(li5, li5, lf5, lf5, 5, 5, 0.5)
    var az_stream = temporal_sorted_by_time(li5, li5, lf5, lf5, 5)
    var az_sub = temporal_window_subgraph(li5, li5, lf5, lf5, 5, 0.5, 0.5)
    var az_act = temporal_activity_summary(li5, li5, lf5, lf5, 5)
    var az_node = temporal_node_activity(li5, li5, lf5, lf5, 5, 5)
    if (
        az_ea.status == TEMPORAL_ERR_SOURCE_OUT_OF_RANGE
        and az_instant.status == TEMPORAL_ERR_SOURCE_OUT_OF_RANGE
        and az_window.status == TEMPORAL_ERR_SOURCE_OUT_OF_RANGE
        and az_path.status == TEMPORAL_ERR_SOURCE_OUT_OF_RANGE
        and az_fast.status == TEMPORAL_ERR_SOURCE_OUT_OF_RANGE
        and az_fpath.status == TEMPORAL_ERR_SOURCE_OUT_OF_RANGE
        and az_set.status == TEMPORAL_ERR_SOURCE_OUT_OF_RANGE
        and az_gap.status == TEMPORAL_ERR_SOURCE_OUT_OF_RANGE
        and not temporal_reaches(li5, li5, lf5, lf5, 5, 5, 5, 0.5)
        and temporal_validate_driver(li5, li5, lf5, lf5, 5) == "ok"
        and az_stream.status == TEMPORAL_OK
        and az_stream.n_edges == 4
        and az_stream.skipped_edges == 1
        and az_sub.status == TEMPORAL_OK
        and az_sub.n_edges == 0
        and az_sub.skipped_edges == 1
        and az_sub.dropped_before == 1
        and az_sub.dropped_after == 3
        and az_act.status == TEMPORAL_OK
        and az_act.n_events == 4
        and az_act.skipped_edges == 1
        and az_node.status == TEMPORAL_ERR_NODE_OUT_OF_RANGE
    ):
        passed += 1
        print("  ✅ the generated suite's 5-element/5 pattern is answered, not crashed")
    else:
        failed += 1
        print(
            "  ❌ A-Z pattern mishandled:",
            az_ea.status,
            az_stream.n_edges,
            az_sub.dropped_after,
            az_node.status,
        )

    # ── this module had NO node ceiling at all ────────────────────────────────
    # Every reachability scan allocates one slot PER NODE (arrival times, visited flags,
    # predecessors) regardless of edge count, so `n_nodes = 10**12` on a two-edge stream
    # asked for an 8 TB allocation. Only `n_nodes < 0` was checked, and clamping negatives
    # is not a bound. Its three sibling modules all had ceilings; this one had none.
    var no_src = List[Int]()
    var no_dst = List[Int]()
    var no_w = List[Float64]()
    var no_t = List[Float64]()
    if temporal_validate(no_src, no_dst, no_w, no_t, 1000000000000) != TEMPORAL_OK:
        passed += 1
        print("  \u2705 an over-ceiling node count is refused, not allocated")
    else:
        failed += 1
        print("  \u274c temporal accepted 10^12 nodes")

    # ── and the ceiling is the SAME one adjacency and the matrix form use ─────
    if TEMPORAL_MAX_NODES == MAX_CSR_DIM:
        passed += 1
        print("  \u2705 the ceiling is shared, not restated:", TEMPORAL_MAX_NODES)
    else:
        failed += 1
        print("  \u274c temporal invented its own ceiling")

    # ── a legitimate stream is unaffected ────────────────────────────────────
    var s2 = List[Int]()
    var d2 = List[Int]()
    var w2 = List[Float64]()
    var t2 = List[Float64]()
    s2.append(0); d2.append(1); w2.append(1.0); t2.append(5.0)
    if temporal_validate(s2, d2, w2, t2, 4) == TEMPORAL_OK:
        passed += 1
        print("  \u2705 a real 4-node stream still validates")
    else:
        failed += 1
        print("  \u274c a legitimate stream regressed")

    print("  [graph_analytics.temporal] Passed:", passed, "Failed:", failed)
