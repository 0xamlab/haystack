"""Tests for Wave 23 — Network Analysis, Discrete Event Simulation, Color Spaces."""

from network_analysis import (
    degree,
    degree_distribution,
    density,
    pagerank,
    degree_centrality,
    closeness_centrality,
    clustering_coefficient,
    avg_clustering_coefficient,
    is_connected,
    connected_components,
    bfs_distances,
)
from simulation import (
    Event,
    SimState,
    create_sim,
    schedule_event,
    next_event,
    has_events,
    run_until,
    cancel_event,
    sim_stats,
    mm1_simulate,
)
from color import (
    RGB,
    HSL,
    HSV,
    rgb_to_hsl,
    hsl_to_rgb,
    rgb_to_hsv,
    hsv_to_rgb,
    rgb_to_hex,
    hex_to_rgb,
    rgb_lerp,
    color_distance,
    grayscale,
    complement,
    clamp01,
)
from std.math import sqrt, abs as fabs


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Helper: build adjacency list ─────────────────────────────────────────────


def _make_triangle() -> List[List[Int]]:
    """3 nodes fully connected: 0-1, 0-2, 1-2."""
    var adj = List[List[Int]]()
    var n0 = List[Int]()
    n0.append(1)
    n0.append(2)
    adj.append(n0^)
    var n1 = List[Int]()
    n1.append(0)
    n1.append(2)
    adj.append(n1^)
    var n2 = List[Int]()
    n2.append(0)
    n2.append(1)
    adj.append(n2^)
    return adj^


def _make_cycle4() -> List[List[Int]]:
    """4-node cycle: 0-1-2-3-0."""
    var adj = List[List[Int]]()
    # node 0: [1, 3]
    var n0 = List[Int]()
    n0.append(1)
    n0.append(3)
    adj.append(n0^)
    # node 1: [0, 2]
    var n1 = List[Int]()
    n1.append(0)
    n1.append(2)
    adj.append(n1^)
    # node 2: [1, 3]
    var n2 = List[Int]()
    n2.append(1)
    n2.append(3)
    adj.append(n2^)
    # node 3: [2, 0]
    var n3 = List[Int]()
    n3.append(2)
    n3.append(0)
    adj.append(n3^)
    return adj^


def _make_star4() -> List[List[Int]]:
    """Star graph with center=0 and leaves 1,2,3."""
    var adj = List[List[Int]]()
    # node 0 (center): [1, 2, 3]
    var n0 = List[Int]()
    n0.append(1)
    n0.append(2)
    n0.append(3)
    adj.append(n0^)
    # node 1: [0]
    var n1 = List[Int]()
    n1.append(0)
    adj.append(n1^)
    # node 2: [0]
    var n2 = List[Int]()
    n2.append(0)
    adj.append(n2^)
    # node 3: [0]
    var n3 = List[Int]()
    n3.append(0)
    adj.append(n3^)
    return adj^


def _make_disconnected() -> List[List[Int]]:
    """Two disconnected components: {0,1} and {2,3}."""
    var adj = List[List[Int]]()
    var n0 = List[Int]()
    n0.append(1)
    adj.append(n0^)
    var n1 = List[Int]()
    n1.append(0)
    adj.append(n1^)
    var n2 = List[Int]()
    n2.append(3)
    adj.append(n2^)
    var n3 = List[Int]()
    n3.append(2)
    adj.append(n3^)
    return adj^


# ── Network Analysis tests ───────────────────────────────────────────────────


def test_network() raises:
    print("── Network Analysis tests ──")
    var n_pass: Int = 0

    # 1. Triangle density == 1.0
    var tri = _make_triangle()
    var d = density(tri)
    _assert_close(d, 1.0, 1e-9, "triangle density == 1.0")
    n_pass += 1

    # 2. degree(triangle, 0) == 2
    _assert(degree(tri, 0) == 2, "degree(triangle, 0) == 2")
    n_pass += 1

    # 3. degree_distribution of triangle
    var dd = degree_distribution(tri)
    _assert(dd[0] == 2 and dd[1] == 2 and dd[2] == 2, "triangle degree_dist all 2")
    n_pass += 1

    # 4. pagerank on 4-node cycle — all ranks ≈ 0.25
    var cyc = _make_cycle4()
    var pr = pagerank(cyc)
    _assert_close(pr[0], 0.25, 0.01, "pagerank cycle node0 ≈ 0.25")
    n_pass += 1
    _assert_close(pr[1], 0.25, 0.01, "pagerank cycle node1 ≈ 0.25")
    n_pass += 1
    _assert_close(pr[2], 0.25, 0.01, "pagerank cycle node2 ≈ 0.25")
    n_pass += 1
    _assert_close(pr[3], 0.25, 0.01, "pagerank cycle node3 ≈ 0.25")
    n_pass += 1

    # 5. degree_centrality of center node in star > edge nodes
    var star = _make_star4()
    var dc = degree_centrality(star)
    _assert(dc[0] > dc[1], "star center centrality > leaf")
    n_pass += 1
    _assert_close(dc[0], 1.0, 1e-9, "star center centrality == 1.0")
    n_pass += 1

    # 6. closeness_centrality of center node in star == 1.0
    var cc = closeness_centrality(star)
    _assert_close(cc[0], 1.0, 1e-9, "star center closeness == 1.0")
    n_pass += 1

    # 7. clustering_coefficient of node in triangle == 1.0
    var cc_tri = clustering_coefficient(tri, 0)
    _assert_close(cc_tri, 1.0, 1e-9, "triangle clustering coeff == 1.0")
    n_pass += 1

    # 8. avg_clustering_coefficient on triangle == 1.0
    var avg_cc = avg_clustering_coefficient(tri)
    _assert_close(avg_cc, 1.0, 1e-9, "triangle avg clustering == 1.0")
    n_pass += 1

    # 9. is_connected on connected graph → True
    _assert(is_connected(tri), "triangle is connected")
    n_pass += 1

    # 10. is_connected on disconnected → False
    var disc = _make_disconnected()
    _assert(not is_connected(disc), "disconnected graph not connected")
    n_pass += 1

    # 11. connected_components on disconnected — correct count
    var comps = connected_components(disc)
    _assert(len(comps) == 2, "disconnected has 2 components")
    n_pass += 1

    # 12. bfs_distances from node 0 in triangle
    var dists = bfs_distances(tri, 0)
    _assert(dists[0] == 0, "bfs dist to self == 0")
    n_pass += 1
    _assert(dists[1] == 1, "bfs dist 0->1 == 1")
    n_pass += 1
    _assert(dists[2] == 1, "bfs dist 0->2 == 1")
    n_pass += 1

    # 13. bfs_distances on disconnected — unreachable == -1
    var dists_d = bfs_distances(disc, 0)
    _assert(dists_d[2] == -1, "disconnected: node 2 unreachable from 0")
    n_pass += 1

    print("  ✓ " + String(n_pass) + " network analysis assertions passed")


# ── Simulation tests ─────────────────────────────────────────────────────────


def test_simulation() raises:
    print("── Simulation tests ──")
    var n_pass: Int = 0

    # 1. create_sim — clock == 0, no events
    var sim = create_sim()
    _assert_close(sim.clock, 0.0, 1e-12, "create_sim clock == 0")
    n_pass += 1
    _assert(not has_events(sim), "create_sim no events")
    n_pass += 1

    # 2. schedule_event then has_events → True
    var eid1 = schedule_event(sim, 5.0, 1)
    _assert(has_events(sim), "has_events after schedule")
    n_pass += 1

    # 3. next_event returns earliest event, advances clock
    var eid2 = schedule_event(sim, 2.0, 2)
    var evt = next_event(sim)
    _assert_close(evt.time, 2.0, 1e-9, "next_event time == 2.0")
    n_pass += 1
    _assert(evt.event_type == 2, "next_event type == 2")
    n_pass += 1
    _assert_close(sim.clock, 2.0, 1e-9, "clock advanced to 2.0")
    n_pass += 1

    # 4. schedule multiple — processed in time order
    var sim2 = create_sim()
    _ = schedule_event(sim2, 10.0, 1)
    _ = schedule_event(sim2, 3.0, 2)
    _ = schedule_event(sim2, 7.0, 3)
    var e1 = next_event(sim2)
    var e2 = next_event(sim2)
    var e3 = next_event(sim2)
    _assert(e1.time <= e2.time and e2.time <= e3.time, "events in time order")
    n_pass += 1
    _assert_close(e1.time, 3.0, 1e-9, "first event at 3.0")
    n_pass += 1

    # 5. run_until processes correct number of events
    var sim3 = create_sim()
    _ = schedule_event(sim3, 1.0, 1)
    _ = schedule_event(sim3, 2.0, 2)
    _ = schedule_event(sim3, 5.0, 3)
    _ = schedule_event(sim3, 8.0, 4)
    var processed = run_until(sim3, 6.0)
    _assert(len(processed) == 3, "run_until(6.0) processes 3 events")
    n_pass += 1
    _assert(has_events(sim3), "1 event remaining after run_until")
    n_pass += 1

    # 6. cancel_event — event removed, returns True
    var sim4 = create_sim()
    var cid = schedule_event(sim4, 5.0, 1)
    _ = schedule_event(sim4, 10.0, 2)
    var cancelled = cancel_event(sim4, cid)
    _assert(cancelled, "cancel_event returns True")
    n_pass += 1

    # 7. cancel_event on non-existent — returns False
    var not_found = cancel_event(sim4, 999)
    _assert(not not_found, "cancel_event non-existent returns False")
    n_pass += 1

    # 8. sim_stats — correct values
    var sim5 = create_sim()
    _ = schedule_event(sim5, 1.0, 1)
    _ = schedule_event(sim5, 2.0, 2)
    _ = next_event(sim5)
    var stats = sim_stats(sim5)
    _assert_close(stats[0], 1.0, 1e-9, "sim_stats: 1 processed")
    n_pass += 1
    _assert_close(stats[1], 1.0, 1e-9, "sim_stats: clock == 1.0")
    n_pass += 1
    _assert_close(stats[2], 1.0, 1e-9, "sim_stats: 1 remaining")
    n_pass += 1

    # 9. mm1_simulate — avg_wait > 0, utilization in (0,1)
    var mm1 = mm1_simulate(0.8, 1.0, 1000)
    _assert(mm1[0] >= 0.0, "mm1 avg_wait >= 0")
    n_pass += 1
    _assert(mm1[2] > 0.0 and mm1[2] < 1.0, "mm1 utilization in (0,1)")
    n_pass += 1
    _assert(mm1[1] > mm1[0], "mm1 system_time > wait_time")
    n_pass += 1

    print("  ✓ " + String(n_pass) + " simulation assertions passed")


# ── Color tests ───────────────────────────────────────────────────────────────


def test_color() raises:
    print("── Color tests ──")
    var n_pass: Int = 0

    # 1. rgb_to_hex(RGB(1,0,0)) == "#FF0000"
    var hex_red = rgb_to_hex(RGB(1.0, 0.0, 0.0))
    _assert(hex_red == "#FF0000", "rgb_to_hex red == #FF0000, got " + hex_red)
    n_pass += 1

    # 2. rgb_to_hex(RGB(0,1,0)) == "#00FF00"
    var hex_green = rgb_to_hex(RGB(0.0, 1.0, 0.0))
    _assert(hex_green == "#00FF00", "rgb_to_hex green == #00FF00, got " + hex_green)
    n_pass += 1

    # 3. hex_to_rgb("#0000FF") → RGB(0,0,1)
    var blue = hex_to_rgb("#0000FF")
    _assert_close(blue.r, 0.0, 0.01, "hex_to_rgb blue r")
    n_pass += 1
    _assert_close(blue.g, 0.0, 0.01, "hex_to_rgb blue g")
    n_pass += 1
    _assert_close(blue.b, 1.0, 0.01, "hex_to_rgb blue b")
    n_pass += 1

    # 4. rgb_to_hsl(RGB(1,0,0)) — h ≈ 0, s ≈ 1, l ≈ 0.5
    var hsl_red = rgb_to_hsl(RGB(1.0, 0.0, 0.0))
    _assert_close(hsl_red.h, 0.0, 1.0, "rgb_to_hsl red h ≈ 0")
    n_pass += 1
    _assert_close(hsl_red.s, 1.0, 0.01, "rgb_to_hsl red s ≈ 1")
    n_pass += 1
    _assert_close(hsl_red.l, 0.5, 0.01, "rgb_to_hsl red l ≈ 0.5")
    n_pass += 1

    # 5. hsl_to_rgb(rgb_to_hsl(c)) roundtrip ≈ original
    var orig = RGB(0.3, 0.6, 0.9)
    var rt = hsl_to_rgb(rgb_to_hsl(orig))
    _assert_close(rt.r, 0.3, 0.01, "hsl roundtrip r")
    n_pass += 1
    _assert_close(rt.g, 0.6, 0.01, "hsl roundtrip g")
    n_pass += 1
    _assert_close(rt.b, 0.9, 0.01, "hsl roundtrip b")
    n_pass += 1

    # 6. rgb_to_hsv(RGB(1,0,0)) — h ≈ 0, s ≈ 1, v ≈ 1
    var hsv_red = rgb_to_hsv(RGB(1.0, 0.0, 0.0))
    _assert_close(hsv_red.h, 0.0, 1.0, "rgb_to_hsv red h ≈ 0")
    n_pass += 1
    _assert_close(hsv_red.s, 1.0, 0.01, "rgb_to_hsv red s ≈ 1")
    n_pass += 1
    _assert_close(hsv_red.v, 1.0, 0.01, "rgb_to_hsv red v ≈ 1")
    n_pass += 1

    # 7. hsv_to_rgb(rgb_to_hsv(c)) roundtrip ≈ original
    var rt2 = hsv_to_rgb(rgb_to_hsv(orig))
    _assert_close(rt2.r, 0.3, 0.01, "hsv roundtrip r")
    n_pass += 1
    _assert_close(rt2.g, 0.6, 0.01, "hsv roundtrip g")
    n_pass += 1
    _assert_close(rt2.b, 0.9, 0.01, "hsv roundtrip b")
    n_pass += 1

    # 8. rgb_lerp(black, white, 0.5) ≈ (0.5, 0.5, 0.5)
    var mid = rgb_lerp(RGB(0.0, 0.0, 0.0), RGB(1.0, 1.0, 1.0), 0.5)
    _assert_close(mid.r, 0.5, 0.01, "lerp mid r")
    n_pass += 1
    _assert_close(mid.g, 0.5, 0.01, "lerp mid g")
    n_pass += 1
    _assert_close(mid.b, 0.5, 0.01, "lerp mid b")
    n_pass += 1

    # 9. color_distance(black, white) ≈ sqrt(3)
    var dist = color_distance(RGB(0.0, 0.0, 0.0), RGB(1.0, 1.0, 1.0))
    _assert_close(dist, sqrt(3.0), 0.01, "color_distance black-white ≈ sqrt(3)")
    n_pass += 1

    # 10. grayscale(RGB(1,0,0)) — all channels equal
    var gray = grayscale(RGB(1.0, 0.0, 0.0))
    _assert_close(gray.r, gray.g, 1e-9, "grayscale r == g")
    n_pass += 1
    _assert_close(gray.g, gray.b, 1e-9, "grayscale g == b")
    n_pass += 1
    _assert_close(gray.r, 0.299, 0.01, "grayscale red luminance ≈ 0.299")
    n_pass += 1

    # 11. complement(RGB(1,0,0)) == RGB(0,1,1)
    var comp = complement(RGB(1.0, 0.0, 0.0))
    _assert_close(comp.r, 0.0, 1e-9, "complement red r == 0")
    n_pass += 1
    _assert_close(comp.g, 1.0, 1e-9, "complement red g == 1")
    n_pass += 1
    _assert_close(comp.b, 1.0, 1e-9, "complement red b == 1")
    n_pass += 1

    # 12. clamp01(-0.5) == 0.0, clamp01(1.5) == 1.0
    _assert_close(clamp01(-0.5), 0.0, 1e-9, "clamp01(-0.5) == 0")
    n_pass += 1
    _assert_close(clamp01(1.5), 1.0, 1e-9, "clamp01(1.5) == 1")
    n_pass += 1
    _assert_close(clamp01(0.5), 0.5, 1e-9, "clamp01(0.5) == 0.5")
    n_pass += 1

    print("  ✓ " + String(n_pass) + " color assertions passed")


# ── main ──────────────────────────────────────────────────────────────────────


def main() raises:
    test_network()
    test_simulation()
    test_color()
    print("All Wave 23 tests passed ✓")
