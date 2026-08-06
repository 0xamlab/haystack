"""test_graph_analytics_centrality.mojo — known-value tests for Brandes and friends.

Hand-written. Every expected number below is computed by hand on a graph small enough to
enumerate: the P5 path, the 5-node star, a 4-cycle whose weights move the shortest paths
off the hop-count paths, a graph in three components including an isolated node, a
multigraph with a self-loop, and a 2-node graph with a dangling sink.

The assertions target the failures that are silent rather than loud:

* a shortest-path count collapsing to 1, so a node on one of two equal-length paths takes
  the whole unit of dependency instead of half of it,
* the undirected halving applied to a directed graph or missed on an undirected one — the
  raw ordered-pair sum is exactly twice the conventional value, so the wrong choice is off
  by a factor of 2 and still looks plausible,
* a weighted run silently using hop counts,
* closeness reporting `0.0` for a node that reaches nobody, which is the frozen convention
  and is indistinguishable from a computed score,
* a zero-weight cycle yielding one of unboundedly many path counts instead of a refusal,
* an out-of-range dimension being indexed instead of rejected — an uncatchable crash, not
  an exception, which is why the A-Z 5-element/5 argument pattern is asserted against
  every driver in this module.

Four frozen kernels are the differential oracles, so the numbers are not just this file
agreeing with itself:

* `linalg_ext.mat_power_iteration` on the dense adjacency, reached independently here
  through `linalg.mat_from_list`, must agree with `graph_eigenvector_centrality`
  component by component — and with the hand value `(1, sqrt2, 1)/2` for P3.
* `graph_algorithms.betweenness_centrality_norm` is the normalisation oracle: the
  normalised P5 value must equal that frozen scalar applied to the raw one.
* `network_analysis.closeness_centrality` returns `0.0` for every node of the
  disconnected graph while this module returns per-component values — asserted, because
  "we changed the convention" is only defensible if the old one is shown returning zeros.
* `network_analysis.degree_centrality` scores a multigraph node above 1.0 on the same
  graph where this module's distinct-neighbour count stays inside [0, 1].
"""
from std.math import abs as fabs, sqrt

from graph_algorithms import betweenness_centrality_norm
from graph_analytics.adjacency import (
    GRAPH_ERR_EMPTY_GRAPH,
    GRAPH_ERR_NEGATIVE_WEIGHT,
    GRAPH_ERR_NON_FINITE_WEIGHT,
    GRAPH_ERR_ROWPTR_LENGTH,
    GRAPH_OK,
    graph_csr_build,
)
from graph_analytics.centrality import (
    CENTRALITY_ERR_DAMPING,
    CENTRALITY_ERR_MAX_ITER,
    CENTRALITY_ERR_TOLERANCE,
    CENTRALITY_ERR_WORK_TOO_LARGE,
    CENTRALITY_ERR_ZERO_WEIGHT_CYCLE,
    CENTRALITY_UNDEFINED,
    centrality_status_name,
    graph_betweenness_from_triplets,
    graph_betweenness_unweighted,
    graph_betweenness_weighted,
    graph_closeness_centrality,
    graph_degree_centrality,
    graph_eigenvector_centrality,
    graph_harmonic_centrality,
    graph_pagerank,
)
from linalg import mat_from_list
from linalg_ext import mat_power_iteration
from network_analysis import (
    closeness_centrality as frozen_closeness,
    degree_centrality as frozen_degree,
)


def _near(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


def _add_edge(
    mut src: List[Int],
    mut dst: List[Int],
    mut weight: List[Float64],
    a: Int,
    b: Int,
    w: Float64,
):
    src.append(a)
    dst.append(b)
    weight.append(w)


def _add_both(
    mut src: List[Int],
    mut dst: List[Int],
    mut weight: List[Float64],
    a: Int,
    b: Int,
    w: Float64,
):
    """An undirected edge is two directed edges with the same weight."""
    _add_edge(src, dst, weight, a, b, w)
    _add_edge(src, dst, weight, b, a, w)


def main() raises:
    var passed = 0
    var failed = 0

    # ── P5: the middle node carries every long pair, the endpoints carry none ──
    # Undirected 0-1-2-3-4. Pairs through node 2 are {0,3},{0,4},{1,3},{1,4} = 4; through
    # node 1 they are {0,2},{0,3},{0,4} = 3; the endpoints are on no pair's interior.
    var p5_src = List[Int]()
    var p5_dst = List[Int]()
    var p5_w = List[Float64]()
    _add_both(p5_src, p5_dst, p5_w, 0, 1, 1.0)
    _add_both(p5_src, p5_dst, p5_w, 1, 2, 1.0)
    _add_both(p5_src, p5_dst, p5_w, 2, 3, 1.0)
    _add_both(p5_src, p5_dst, p5_w, 3, 4, 1.0)
    var p5 = graph_csr_build(p5_src, p5_dst, p5_w, 5)

    var p5_raw = graph_betweenness_unweighted(
        p5.row_ptr, p5.targets, p5.weights, 5, False
    )
    if (
        p5_raw.status == GRAPH_OK
        and len(p5_raw.values) == 5
        and p5_raw.values[0] == 0.0
        and p5_raw.values[4] == 0.0
        and _near(p5_raw.values[1], 3.0, 1e-12)
        and _near(p5_raw.values[2], 4.0, 1e-12)
        and _near(p5_raw.values[3], 3.0, 1e-12)
        and p5_raw.max_node == 2
        and p5_raw.undirected
        and p5_raw.path_counts_exact
    ):
        passed += 1
        print("  ✅ P5 raw betweenness is [0,3,4,3,0] and the middle node is the max")
    else:
        failed += 1
        print(
            "  ❌ P5 raw betweenness wrong:",
            p5_raw.values[0], p5_raw.values[1], p5_raw.values[2],
            p5_raw.values[3], p5_raw.values[4],
            "status", p5_raw.status,
        )

    # The endpoints must be exactly 0, not nearly 0: an endpoint is on no shortest path's
    # interior at all, so any residue there means dependency is leaking into the source.
    var p5_norm = graph_betweenness_unweighted(
        p5.row_ptr, p5.targets, p5.weights, 5, True
    )
    var frozen_norm_middle = betweenness_centrality_norm(4.0, 5.0, 0.0)
    if (
        p5_norm.status == GRAPH_OK
        and p5_norm.normalized
        and p5_norm.values[2] == frozen_norm_middle
        and _near(p5_norm.values[2], 4.0 / 6.0, 1e-15)
        and _near(p5_norm.values[1], 0.5, 1e-15)
    ):
        passed += 1
        print("  ✅ normalised P5 equals the frozen betweenness_centrality_norm")
    else:
        failed += 1
        print(
            "  ❌ normalised P5 disagrees with the frozen normaliser:",
            p5_norm.values[2], "vs", frozen_norm_middle,
        )

    # Unit weights must make the weighted lane reduce to the unweighted one *exactly*:
    # both build the same DAG from the same distances, so any difference is a bug in one
    # of the two orderings, not rounding.
    var p5_weighted = graph_betweenness_weighted(
        p5.row_ptr, p5.targets, p5.weights, 5, False
    )
    var lanes_identical = p5_weighted.status == GRAPH_OK
    for v in range(5):
        if p5_weighted.values[v] != p5_raw.values[v]:
            lanes_identical = False
    if lanes_identical and p5_weighted.weighted and p5_weighted.undirected:
        passed += 1
        print("  ✅ with unit weights the Dijkstra lane matches the BFS lane bit for bit")
    else:
        failed += 1
        print("  ❌ weighted lane differs on unit weights:", p5_weighted.values[2])

    # Uniform *inexact* weights are the sharper version of the same claim: 0.1 has no
    # exact binary form, so if the DAG-membership equality were sloppy about accumulated
    # rounding this would drop routes and change the counts. It cannot: every node's
    # distance is built by the same sequence of additions, so equal-hop routes land on
    # bit-identical sums and the hop answer must come back unchanged.
    var p5_tenths = List[Float64]()
    for _ in range(len(p5_w)):
        p5_tenths.append(0.1)
    var tenths = graph_csr_build(p5_src, p5_dst, p5_tenths, 5)
    var p5_tenth_bc = graph_betweenness_weighted(
        tenths.row_ptr, tenths.targets, tenths.weights, 5, False
    )
    var tenths_identical = p5_tenth_bc.status == GRAPH_OK
    for v in range(5):
        if p5_tenth_bc.values[v] != p5_raw.values[v]:
            tenths_identical = False
    if tenths_identical:
        passed += 1
        print("  ✅ uniform weights of 0.1 reproduce the hop-count betweenness exactly")
    else:
        failed += 1
        print("  ❌ inexact uniform weights changed the answer:", p5_tenth_bc.values[2])

    # ── the star: the hub is (n-1)(n-2)/2, every leaf is 0 ────────────────────
    var star_src = List[Int]()
    var star_dst = List[Int]()
    var star_w = List[Float64]()
    for leaf in range(1, 5):
        _add_both(star_src, star_dst, star_w, 0, leaf, 1.0)
    var star = graph_betweenness_from_triplets(
        star_src, star_dst, star_w, 5, False, False
    )
    var star_norm = graph_betweenness_from_triplets(
        star_src, star_dst, star_w, 5, False, True
    )
    var leaves_zero = True
    for leaf in range(1, 5):
        if star.values[leaf] != 0.0:
            leaves_zero = False
    if (
        star.status == GRAPH_OK
        and _near(star.values[0], 6.0, 1e-12)
        and leaves_zero
        and _near(star_norm.values[0], 1.0, 1e-12)
    ):
        passed += 1
        print("  ✅ star hub betweenness is (n-1)(n-2)/2 = 6, normalises to 1.0")
    else:
        failed += 1
        print("  ❌ star hub betweenness wrong:", star.values[0], star_norm.values[0])

    # ── a directed path gets the same counts under a different convention ─────
    # 0->1->2->3->4 one way only: the ordered pairs are already counted once, so the
    # values must NOT be halved. Same numbers as undirected P5, different reason.
    var dir_src = List[Int]()
    var dir_dst = List[Int]()
    var dir_w = List[Float64]()
    for u in range(4):
        _add_edge(dir_src, dir_dst, dir_w, u, u + 1, 1.0)
    var directed = graph_betweenness_from_triplets(
        dir_src, dir_dst, dir_w, 5, False, False
    )
    if (
        directed.status == GRAPH_OK
        and not directed.undirected
        and _near(directed.values[1], 3.0, 1e-12)
        and _near(directed.values[2], 4.0, 1e-12)
        and _near(directed.values[3], 3.0, 1e-12)
    ):
        passed += 1
        print("  ✅ the directed path is detected as directed and is not halved")
    else:
        failed += 1
        print(
            "  ❌ directed path betweenness wrong:",
            directed.values[1], directed.values[2], directed.values[3],
            "undirected =", directed.undirected,
        )

    # ── weights move the paths, and a tie splits in half ─────────────────────
    # Undirected 0-1(1.0), 1-3(1.0), 0-2(0.4), 2-3(0.4).
    # Hop counts: {0,3} has two 2-hop routes, so nodes 1 and 2 take 0.5 each; {1,2} has
    # two 2-hop routes through 0 and 3, so those take 0.5 each -> all four are 0.5.
    # Weights: 0->3 costs 0.8 via node 2 and 2.0 via node 1, so node 2 takes the whole
    # unit and node 1 takes none; {1,2} is still a tie at 1.4 either way -> 0.5 each.
    var wsrc = List[Int]()
    var wdst = List[Int]()
    var ww = List[Float64]()
    _add_both(wsrc, wdst, ww, 0, 1, 1.0)
    _add_both(wsrc, wdst, ww, 1, 3, 1.0)
    _add_both(wsrc, wdst, ww, 0, 2, 0.4)
    _add_both(wsrc, wdst, ww, 2, 3, 0.4)
    var diamond = graph_csr_build(wsrc, wdst, ww, 4)
    var hop_view = graph_betweenness_unweighted(
        diamond.row_ptr, diamond.targets, diamond.weights, 4, False
    )
    var weight_view = graph_betweenness_weighted(
        diamond.row_ptr, diamond.targets, diamond.weights, 4, False
    )
    var hops_all_half = True
    for v in range(4):
        if not _near(hop_view.values[v], 0.5, 1e-12):
            hops_all_half = False
    if (
        hop_view.status == GRAPH_OK
        and hops_all_half
        and weight_view.status == GRAPH_OK
        and _near(weight_view.values[0], 0.5, 1e-12)
        and weight_view.values[1] == 0.0
        and _near(weight_view.values[2], 1.0, 1e-12)
        and _near(weight_view.values[3], 0.5, 1e-12)
    ):
        passed += 1
        print("  ✅ weights reroute betweenness (1 -> 0, 2 -> 1.0) and ties split 0.5/0.5")
    else:
        failed += 1
        print(
            "  ❌ weighted/unweighted betweenness not distinguished:",
            hop_view.values[1], weight_view.values[1], weight_view.values[2],
        )

    # ── three components, one of them a single isolated node ──────────────────
    # 0-1-2 | 3-4 | 5. Every closeness here is component-local; the frozen kernel returns
    # 0.0 for all six because no node reaches all five others.
    var dsrc = List[Int]()
    var ddst = List[Int]()
    var dw = List[Float64]()
    _add_both(dsrc, ddst, dw, 0, 1, 1.0)
    _add_both(dsrc, ddst, dw, 1, 2, 1.0)
    _add_both(dsrc, ddst, dw, 3, 4, 1.0)
    var split = graph_csr_build(dsrc, ddst, dw, 6)
    var close = graph_closeness_centrality(
        split.row_ptr, split.targets, split.weights, 6, False
    )
    if (
        close.status == GRAPH_OK
        and _near(close.values[0], 2.0 / 3.0, 1e-12)
        and _near(close.values[1], 1.0, 1e-12)
        and _near(close.values[2], 2.0 / 3.0, 1e-12)
        and _near(close.values[3], 1.0, 1e-12)
        and close.values[5] == CENTRALITY_UNDEFINED
        and not close.defined[5]
        and close.defined[0]
        and close.defined_count == 5
        and close.incomplete_count == 6
        and close.reached_count[0] == 2
        and close.reached_count[5] == 0
        and _near(close.sum_distance[0], 3.0, 1e-12)
    ):
        passed += 1
        print("  ✅ closeness is component-local and the isolated node is ABSENT, not 0")
    else:
        failed += 1
        print(
            "  ❌ disconnected closeness wrong:",
            close.values[0], close.values[3], close.values[5],
            "defined_count", close.defined_count,
        )

    # Wasserman-Faust scaling is what makes two components comparable again: node 1 sees
    # 2 of 5 others at mean distance 1, node 3 sees 1 of 5 at distance 1.
    if (
        _near(close.scaled_values[1], 0.4, 1e-12)
        and _near(close.scaled_values[3], 0.2, 1e-12)
        and _near(close.scaled_values[0], 4.0 / 15.0, 1e-12)
        and close.scaled_values[5] == CENTRALITY_UNDEFINED
    ):
        passed += 1
        print("  ✅ Wasserman-Faust scaling penalises the smaller component")
    else:
        failed += 1
        print(
            "  ❌ WF scaling wrong:",
            close.scaled_values[0], close.scaled_values[1], close.scaled_values[3],
        )

    # The frozen kernel on the same graph. Its zeros are the reason this module exists.
    var frozen_adj = List[List[Int]]()
    for u in range(6):
        var row = List[Int]()
        for k in range(split.row_ptr[u], split.row_ptr[u + 1]):
            row.append(split.targets[k])
        frozen_adj.append(row^)
    var frozen_close = frozen_closeness(frozen_adj)
    var frozen_all_zero = True
    for u in range(6):
        if frozen_close[u] != 0.0:
            frozen_all_zero = False
    if frozen_all_zero and close.values[1] > 0.0:
        passed += 1
        print(
            "  ✅ frozen closeness_centrality returns 0.0 for ALL six nodes; this"
            " module does not"
        )
    else:
        failed += 1
        print("  ❌ the frozen-vs-new closeness contrast did not hold:", frozen_close[1])

    # ── harmonic centrality needs no convention, and an isolated node is 0 ────
    # node 0: 1/1 + 1/2 = 1.5. node 1: 1/1 + 1/1 = 2.0. node 3: 1/1 = 1.0. node 5: 0.
    var harmonic = graph_harmonic_centrality(
        split.row_ptr, split.targets, split.weights, 6, False, False
    )
    var harmonic_norm = graph_harmonic_centrality(
        split.row_ptr, split.targets, split.weights, 6, False, True
    )
    if (
        harmonic.status == GRAPH_OK
        and _near(harmonic.values[0], 1.5, 1e-12)
        and _near(harmonic.values[1], 2.0, 1e-12)
        and _near(harmonic.values[3], 1.0, 1e-12)
        and harmonic.values[5] == 0.0
        and harmonic.defined[5]
        and harmonic.zero_distance_nodes == 0
        and _near(harmonic_norm.values[0], 0.3, 1e-12)
    ):
        passed += 1
        print(
            "  ✅ harmonic centrality is defined everywhere; the isolated node's 0 is"
            " a real 0"
        )
    else:
        failed += 1
        print(
            "  ❌ harmonic centrality wrong:",
            harmonic.values[0], harmonic.values[1], harmonic.values[5],
        )

    # ── weighted closeness is not the hop-count closeness ────────────────────
    # In the diamond, node 0 reaches 1 at 1.0, 2 at 0.4 and 3 at 0.8: 3/2.2, not 3/4.
    var wclose = graph_closeness_centrality(
        diamond.row_ptr, diamond.targets, diamond.weights, 4, True
    )
    var uclose = graph_closeness_centrality(
        diamond.row_ptr, diamond.targets, diamond.weights, 4, False
    )
    if (
        wclose.status == GRAPH_OK
        and _near(wclose.values[0], 3.0 / 2.2, 1e-12)
        and _near(wclose.sum_distance[0], 2.2, 1e-12)
        and _near(uclose.values[0], 0.75, 1e-12)
        and wclose.incomplete_count == 0
    ):
        passed += 1
        print("  ✅ weighted closeness uses distances (3/2.2), unweighted uses hops (3/4)")
    else:
        failed += 1
        print(
            "  ❌ weighted closeness wrong:",
            wclose.values[0], wclose.sum_distance[0], uclose.values[0],
        )

    # ── a zero-weight edge is where each measure's absent case lives ──────────
    # 0 <-> 1 with weight 0: two distinct nodes at distance 0. Closeness has no mean
    # distance to report and harmonic has no 1/0, so both say absent rather than large.
    var zsrc = List[Int]()
    var zdst = List[Int]()
    var zw = List[Float64]()
    _add_both(zsrc, zdst, zw, 0, 1, 0.0)
    var zero_graph = graph_csr_build(zsrc, zdst, zw, 2)
    var zero_close = graph_closeness_centrality(
        zero_graph.row_ptr, zero_graph.targets, zero_graph.weights, 2, True
    )
    var zero_harmonic = graph_harmonic_centrality(
        zero_graph.row_ptr, zero_graph.targets, zero_graph.weights, 2, True, False
    )
    if (
        zero_close.status == GRAPH_OK
        and not zero_close.defined[0]
        and zero_close.values[0] == CENTRALITY_UNDEFINED
        and zero_close.reached_count[0] == 1
        and zero_harmonic.status == GRAPH_OK
        and zero_harmonic.zero_distance_nodes == 2
        and zero_harmonic.values[1] == CENTRALITY_UNDEFINED
    ):
        passed += 1
        print("  ✅ a distinct node at distance 0 makes closeness and harmonic absent")
    else:
        failed += 1
        print(
            "  ❌ zero-distance handling wrong:",
            zero_close.values[0], zero_harmonic.values[0],
            zero_harmonic.zero_distance_nodes,
        )

    # ── a zero-weight cycle has unboundedly many shortest paths: refuse ───────
    var csrc = List[Int]()
    var cdst = List[Int]()
    var cw = List[Float64]()
    _add_edge(csrc, cdst, cw, 0, 1, 0.0)
    _add_edge(csrc, cdst, cw, 1, 0, 0.0)
    _add_edge(csrc, cdst, cw, 0, 2, 1.0)
    var cyc = graph_csr_build(csrc, cdst, cw, 3)
    var cyc_weighted = graph_betweenness_weighted(
        cyc.row_ptr, cyc.targets, cyc.weights, 3, False
    )
    var cyc_hops = graph_betweenness_unweighted(
        cyc.row_ptr, cyc.targets, cyc.weights, 3, False
    )
    if (
        cyc_weighted.status == CENTRALITY_ERR_ZERO_WEIGHT_CYCLE
        and len(cyc_weighted.values) == 0
        and cyc_weighted.max_node == -1
        and cyc_hops.status == GRAPH_OK
        and _near(cyc_hops.values[0], 1.0, 1e-12)
        and not cyc_hops.undirected
    ):
        passed += 1
        print(
            "  ✅ a zero-weight cycle is refused by the weighted lane and irrelevant"
            " to the hop lane"
        )
    else:
        failed += 1
        print(
            "  ❌ zero-weight cycle not handled:",
            cyc_weighted.status, cyc_hops.status, cyc_hops.values[0],
        )

    # A zero-weight SELF-loop is not a cycle for this purpose: it cannot lie on a path
    # between two distinct nodes, so it is excluded from the DAG instead of refused.
    var lsrc = List[Int]()
    var ldst = List[Int]()
    var lw = List[Float64]()
    _add_edge(lsrc, ldst, lw, 0, 0, 0.0)
    _add_edge(lsrc, ldst, lw, 0, 1, 1.0)
    var loopy = graph_csr_build(lsrc, ldst, lw, 2)
    var loopy_bc = graph_betweenness_weighted(
        loopy.row_ptr, loopy.targets, loopy.weights, 2, False
    )
    if (
        loopy_bc.status == GRAPH_OK
        and loopy_bc.values[0] == 0.0
        and loopy_bc.values[1] == 0.0
    ):
        passed += 1
        print("  ✅ a zero-weight self-loop is excluded, not mistaken for a zero cycle")
    else:
        failed += 1
        print("  ❌ zero-weight self-loop mishandled:", loopy_bc.status)

    # ── a negative or NaN weight has no Dijkstra answer to build a DAG on ─────
    var nsrc = List[Int]()
    var ndst = List[Int]()
    var nw = List[Float64]()
    _add_edge(nsrc, ndst, nw, 0, 1, 1.0)
    _add_edge(nsrc, ndst, nw, 1, 2, -5.0)
    var negative = graph_csr_build(nsrc, ndst, nw, 3)
    var neg_bc = graph_betweenness_weighted(
        negative.row_ptr, negative.targets, negative.weights, 3, False
    )
    var neg_close = graph_closeness_centrality(
        negative.row_ptr, negative.targets, negative.weights, 3, True
    )
    var neg_hops = graph_betweenness_unweighted(
        negative.row_ptr, negative.targets, negative.weights, 3, False
    )
    var inf_w = List[Float64]()
    inf_w.append(1.0)
    inf_w.append(1e308 * 1e308)
    var infinite = graph_csr_build(nsrc, ndst, inf_w, 3)
    var inf_bc = graph_betweenness_weighted(
        infinite.row_ptr, infinite.targets, infinite.weights, 3, False
    )
    if (
        neg_bc.status == GRAPH_ERR_NEGATIVE_WEIGHT
        and neg_close.status == GRAPH_ERR_NEGATIVE_WEIGHT
        and len(neg_close.values) == 0
        and inf_bc.status == GRAPH_ERR_NON_FINITE_WEIGHT
        and neg_hops.status == GRAPH_OK
    ):
        passed += 1
        print(
            "  ✅ negative and non-finite weights are refused; the hop lane ignores"
            " weights and still answers"
        )
    else:
        failed += 1
        print(
            "  ❌ weight defects not refused:",
            neg_bc.status, neg_close.status, inf_bc.status,
        )

    # ── degree centrality on a multigraph stays inside [0, 1] ─────────────────
    # 0->1 twice, a self-loop 0->0, 0->2, and 1->0. Distinct out-neighbours of node 0 that
    # are not itself: {1, 2}; distinct in-neighbours: {1}.
    var msrc = List[Int]()
    var mdst = List[Int]()
    var mw = List[Float64]()
    _add_edge(msrc, mdst, mw, 0, 1, 1.0)
    _add_edge(msrc, mdst, mw, 0, 1, 2.0)
    _add_edge(msrc, mdst, mw, 0, 0, 1.0)
    _add_edge(msrc, mdst, mw, 0, 2, 1.0)
    _add_edge(msrc, mdst, mw, 1, 0, 1.0)
    var multi = graph_csr_build(msrc, mdst, mw, 3)
    var degrees = graph_degree_centrality(
        multi.row_ptr, multi.targets, multi.weights, 3, True
    )
    var raw_degrees = graph_degree_centrality(
        multi.row_ptr, multi.targets, multi.weights, 3, False
    )
    if (
        degrees.status == GRAPH_OK
        and degrees.parallel_edges_collapsed == 1
        and degrees.self_loops_ignored == 1
        and _near(degrees.out_values[0], 1.0, 1e-12)
        and _near(degrees.in_values[0], 0.5, 1e-12)
        and _near(degrees.total_values[0], 0.75, 1e-12)
        and _near(degrees.out_values[2], 0.0, 1e-12)
        and _near(degrees.in_values[2], 0.5, 1e-12)
        and _near(raw_degrees.out_values[0], 2.0, 1e-12)
        and _near(raw_degrees.in_values[0], 1.0, 1e-12)
    ):
        passed += 1
        print("  ✅ degree centrality counts distinct neighbours and drops the self-loop")
    else:
        failed += 1
        print(
            "  ❌ degree centrality wrong:",
            degrees.out_values[0], degrees.in_values[0], degrees.total_values[0],
            degrees.parallel_edges_collapsed, degrees.self_loops_ignored,
        )

    var frozen_multi_adj = List[List[Int]]()
    for u in range(3):
        var row = List[Int]()
        for k in range(multi.row_ptr[u], multi.row_ptr[u + 1]):
            row.append(multi.targets[k])
        frozen_multi_adj.append(row^)
    var frozen_deg = frozen_degree(frozen_multi_adj)
    if frozen_deg[0] > 1.0 and degrees.out_values[0] <= 1.0:
        passed += 1
        print(
            "  ✅ frozen degree_centrality scores node 0 at",
            frozen_deg[0],
            "> 1.0 on the same multigraph",
        )
    else:
        failed += 1
        print("  ❌ the multigraph degree contrast did not hold:", frozen_deg[0])

    # ── eigenvector centrality on P3 agrees with the frozen power iteration ───
    # A = [[0,1,0],[1,0,1],[0,1,0]] has dominant eigenvalue sqrt(2) and eigenvector
    # (1, sqrt2, 1), which is (0.5, 0.7071..., 0.5) once normalised to unit length.
    var p3_src = List[Int]()
    var p3_dst = List[Int]()
    var p3_w = List[Float64]()
    _add_both(p3_src, p3_dst, p3_w, 0, 1, 1.0)
    _add_both(p3_src, p3_dst, p3_w, 1, 2, 1.0)
    var p3 = graph_csr_build(p3_src, p3_dst, p3_w, 3)
    var eigen = graph_eigenvector_centrality(
        p3.row_ptr, p3.targets, p3.weights, 3, 200, 1e-9
    )
    var root2 = sqrt(2.0)
    if (
        eigen.status == GRAPH_OK
        and eigen.converged
        and eigen.symmetric
        and eigen.strongly_connected
        and _near(eigen.eigenvalue, root2, 1e-9)
        and _near(eigen.values[0], 0.5, 1e-9)
        and _near(eigen.values[1], root2 / 2.0, 1e-9)
        and _near(eigen.values[2], 0.5, 1e-9)
        and eigen.residual <= 1e-9
    ):
        passed += 1
        print("  ✅ P3 eigenvector centrality is (0.5, sqrt2/2, 0.5) with eigenvalue sqrt2")
    else:
        failed += 1
        print(
            "  ❌ P3 eigenvector wrong:",
            eigen.eigenvalue, eigen.values[0], eigen.values[1],
            "converged", eigen.converged,
        )

    var dense = List[Float64]()
    dense.append(0.0); dense.append(1.0); dense.append(0.0)
    dense.append(1.0); dense.append(0.0); dense.append(1.0)
    dense.append(0.0); dense.append(1.0); dense.append(0.0)

    # P3 is bipartite, so its spectrum is {+sqrt2, 0, -sqrt2} and the two ends are equally
    # dominant: the frozen kernel on the BARE adjacency oscillates forever, reporting the
    # uniform vector's Rayleigh quotient 4/3 as the eigenvalue with nothing to say it did
    # not converge. This asserts that silent wrong answer, because it is the entire reason
    # the driver shifts by max-row-sum * I before iterating.
    var unshifted = mat_power_iteration(mat_from_list(dense, 3, 3), 200)
    var unshifted_odd = mat_power_iteration(mat_from_list(dense, 3, 3), 201)
    if (
        _near(unshifted.eigenvalue, 4.0 / 3.0, 1e-12)
        and fabs(unshifted.eigenvalue - root2) > 0.07
        and fabs(unshifted.eigenvector[1] - unshifted_odd.eigenvector[1]) > 0.2
        and eigen.shift == 2.0
    ):
        passed += 1
        print(
            "  ✅ the bare frozen power iteration oscillates on bipartite P3 (4/3, not"
            " sqrt2); the shift of 2.0 is load-bearing"
        )
    else:
        failed += 1
        print(
            "  ❌ the bipartite non-convergence claim does not hold:",
            unshifted.eigenvalue, unshifted.eigenvector[1],
            unshifted_odd.eigenvector[1], eigen.shift,
        )

    # The same frozen kernel on the same shifted matrix, reached independently through
    # linalg. Identical input means identical arithmetic, so this is an equality check on
    # the eigenvalue and not a tolerance check.
    var shifted_dense = dense.copy()
    for i in range(3):
        shifted_dense[i * 3 + i] += 2.0
    var oracle = mat_power_iteration(mat_from_list(shifted_dense, 3, 3), 200)
    var oracle_matches = oracle.eigenvalue - 2.0 == eigen.eigenvalue
    for i in range(3):
        if not _near(fabs(oracle.eigenvector[i]), eigen.values[i], 1e-15):
            oracle_matches = False
    if oracle_matches:
        passed += 1
        print("  ✅ mat_power_iteration on the shifted dense adjacency is matched exactly")
    else:
        failed += 1
        print(
            "  ❌ frozen power iteration disagrees:",
            oracle.eigenvalue - 2.0, "vs", eigen.eigenvalue,
        )

    # Two disjoint edges: the dominant eigenspace is two-dimensional, so the vector is one
    # member of it and the flag has to say so rather than implying uniqueness.
    var pair_src = List[Int]()
    var pair_dst = List[Int]()
    var pair_w = List[Float64]()
    _add_both(pair_src, pair_dst, pair_w, 0, 1, 1.0)
    _add_both(pair_src, pair_dst, pair_w, 2, 3, 1.0)
    var pairs = graph_csr_build(pair_src, pair_dst, pair_w, 4)
    var pair_eigen = graph_eigenvector_centrality(
        pairs.row_ptr, pairs.targets, pairs.weights, 4, 200, 1e-9
    )
    if (
        pair_eigen.status == GRAPH_OK
        and not pair_eigen.strongly_connected
        and _near(pair_eigen.eigenvalue, 1.0, 1e-9)
        and pair_eigen.shift == 1.0
    ):
        passed += 1
        print("  ✅ a disconnected graph is flagged not-strongly-connected, still answered")
    else:
        failed += 1
        print(
            "  ❌ connectivity flag wrong:",
            pair_eigen.strongly_connected, pair_eigen.eigenvalue,
        )

    # A second bipartite hand value, on a graph whose hub dominates: the 4-leaf star has
    # eigenvalue sqrt(4) = 2 and eigenvector (2,1,1,1,1)/sqrt(8).
    var star_csr = graph_csr_build(star_src, star_dst, star_w, 5)
    var star_eigen = graph_eigenvector_centrality(
        star_csr.row_ptr, star_csr.targets, star_csr.weights, 5, 400, 1e-9
    )
    var leaves_equal = True
    for leaf in range(1, 5):
        if not _near(star_eigen.values[leaf], 1.0 / (2.0 * root2), 1e-9):
            leaves_equal = False
    if (
        star_eigen.status == GRAPH_OK
        and star_eigen.converged
        and _near(star_eigen.eigenvalue, 2.0, 1e-9)
        and _near(star_eigen.values[0], root2 / 2.0, 1e-9)
        and leaves_equal
        and star_eigen.shift == 4.0
    ):
        passed += 1
        print("  ✅ star eigenvector centrality is (2,1,1,1,1)/sqrt8 with eigenvalue 2")
    else:
        failed += 1
        print(
            "  ❌ star eigenvector wrong:",
            star_eigen.eigenvalue, star_eigen.values[0], star_eigen.values[1],
            "converged", star_eigen.converged,
        )

    # ── PageRank: a 3-cycle is uniform, and the dangling leak is visible ──────
    var cyc_src = List[Int]()
    var cyc_dst = List[Int]()
    var cyc_w = List[Float64]()
    _add_edge(cyc_src, cyc_dst, cyc_w, 0, 1, 1.0)
    _add_edge(cyc_src, cyc_dst, cyc_w, 1, 2, 1.0)
    _add_edge(cyc_src, cyc_dst, cyc_w, 2, 0, 1.0)
    var ring = graph_csr_build(cyc_src, cyc_dst, cyc_w, 3)
    var ring_pr = graph_pagerank(
        ring.row_ptr, ring.targets, ring.weights, 3, 0.85, 200, 1e-10, True
    )
    if (
        ring_pr.status == GRAPH_OK
        and ring_pr.dangling_nodes == 0
        and ring_pr.converged
        and _near(ring_pr.mass, 1.0, 1e-9)
        and _near(ring_pr.values[0], 1.0 / 3.0, 1e-9)
        and _near(ring_pr.values[2], 1.0 / 3.0, 1e-9)
    ):
        passed += 1
        print("  ✅ PageRank on a 3-cycle is uniform, mass 1.0, and reports converged")
    else:
        failed += 1
        print(
            "  ❌ ring PageRank wrong:",
            ring_pr.values[0], ring_pr.mass, ring_pr.converged, ring_pr.status,
        )

    # 0 -> 1 with node 1 dangling. Left alone the frozen iteration reaches
    # (0.075, 0.13875) and keeps only 0.21375 of the probability mass. Augmenting node 1
    # with a uniform out-row is the standard redistribution and gives
    # (0.350877..., 0.649122...), summing to 1.
    var dang_src = List[Int]()
    var dang_dst = List[Int]()
    var dang_w = List[Float64]()
    _add_edge(dang_src, dang_dst, dang_w, 0, 1, 1.0)
    var sink = graph_csr_build(dang_src, dang_dst, dang_w, 2)
    var leaked = graph_pagerank(
        sink.row_ptr, sink.targets, sink.weights, 2, 0.85, 200, 1e-12, False
    )
    var fixed = graph_pagerank(
        sink.row_ptr, sink.targets, sink.weights, 2, 0.85, 200, 1e-12, True
    )
    if (
        leaked.status == GRAPH_OK
        and leaked.dangling_nodes == 1
        and not leaked.dangling_redistributed
        and _near(leaked.mass, 0.21375, 1e-9)
        and fixed.status == GRAPH_OK
        and fixed.dangling_redistributed
        and _near(fixed.mass, 1.0, 1e-9)
        and _near(fixed.values[1], 0.6491228070175439, 1e-6)
        and _near(fixed.values[0], 0.3508771929824561, 1e-6)
    ):
        passed += 1
        print(
            "  ✅ the frozen dangling-mass leak is measured (mass 0.21375) and fixed"
            " by augmentation (mass 1.0)"
        )
    else:
        failed += 1
        print(
            "  ❌ dangling handling wrong: leaked mass",
            leaked.mass, "fixed mass", fixed.mass, "rank1", fixed.values[1],
        )

    var bad_damping = graph_pagerank(
        ring.row_ptr, ring.targets, ring.weights, 3, 1.0, 200, 1e-10, True
    )
    var bad_iter = graph_pagerank(
        ring.row_ptr, ring.targets, ring.weights, 3, 0.85, 0, 1e-10, True
    )
    var bad_tol = graph_pagerank(
        ring.row_ptr, ring.targets, ring.weights, 3, 0.85, 10, -1.0, True
    )
    var bad_eigen_iter = graph_eigenvector_centrality(
        ring.row_ptr, ring.targets, ring.weights, 3, 0, 1e-9
    )
    if (
        bad_damping.status == CENTRALITY_ERR_DAMPING
        and len(bad_damping.values) == 0
        and bad_iter.status == CENTRALITY_ERR_MAX_ITER
        and bad_tol.status == CENTRALITY_ERR_TOLERANCE
        and bad_eigen_iter.status == CENTRALITY_ERR_MAX_ITER
    ):
        passed += 1
        print("  ✅ damping 1.0, max_iter 0 and a negative tolerance are all refused")
    else:
        failed += 1
        print(
            "  ❌ parameter validation wrong:",
            bad_damping.status, bad_iter.status, bad_tol.status,
            bad_eigen_iter.status,
        )

    # ── the empty graph has no centrality, and says so ────────────────────────
    var no_nodes = List[Int]()
    no_nodes.append(0)
    var no_targets = List[Int]()
    var no_weights = List[Float64]()
    var empty_bc = graph_betweenness_unweighted(
        no_nodes, no_targets, no_weights, 0, False
    )
    var empty_close = graph_closeness_centrality(
        no_nodes, no_targets, no_weights, 0, False
    )
    if (
        empty_bc.status == GRAPH_ERR_EMPTY_GRAPH
        and empty_bc.max_node == -1
        and empty_bc.max_value == CENTRALITY_UNDEFINED
        and empty_close.status == GRAPH_ERR_EMPTY_GRAPH
    ):
        passed += 1
        print("  ✅ the empty graph is empty_graph, not a zero-length success")
    else:
        failed += 1
        print("  ❌ empty graph wrong:", empty_bc.status, empty_close.status)

    # ── one traversal per node is refused before it is paid for ───────────────
    # 20000 isolated nodes is a structurally valid graph whose all-pairs cost is 4e8
    # steps, past the declared ceiling. The refusal must be instant, which it is because
    # the estimate is made from the counts and not by starting.
    var wide_row_ptr = List[Int]()
    for _ in range(20001):
        wide_row_ptr.append(0)
    var wide_bc = graph_betweenness_unweighted(
        wide_row_ptr, no_targets, no_weights, 20000, False
    )
    var wide_close = graph_closeness_centrality(
        wide_row_ptr, no_targets, no_weights, 20000, False
    )
    var wide_harmonic = graph_harmonic_centrality(
        wide_row_ptr, no_targets, no_weights, 20000, False, False
    )
    var wide_eigen = graph_eigenvector_centrality(
        wide_row_ptr, no_targets, no_weights, 20000, 100, 1e-9
    )
    if (
        wide_bc.status == CENTRALITY_ERR_WORK_TOO_LARGE
        and wide_close.status == CENTRALITY_ERR_WORK_TOO_LARGE
        and wide_harmonic.status == CENTRALITY_ERR_WORK_TOO_LARGE
        and wide_eigen.status == CENTRALITY_ERR_WORK_TOO_LARGE
    ):
        passed += 1
        print("  ✅ a 20000-node all-pairs request is refused, not attempted")
    else:
        failed += 1
        print(
            "  ❌ work ceiling not enforced:",
            wide_bc.status, wide_close.status, wide_harmonic.status,
            wide_eigen.status,
        )

    # The remedy for `converged = False` is a bigger `max_iter`, so the iteration ceiling
    # must not be the one that refuses it: 100000 sweeps of a 3-node matrix is a request
    # the driver has to accept, and under the all-pairs ceiling it would not have been.
    var patient = graph_eigenvector_centrality(
        p3.row_ptr, p3.targets, p3.weights, 3, 100000, 1e-12
    )
    if patient.status == GRAPH_OK and patient.converged:
        passed += 1
        print("  ✅ max_iter can be raised to 100000 without hitting a ceiling")
    else:
        failed += 1
        print(
            "  ❌ raising max_iter was refused or did not converge:",
            patient.status, patient.residual,
        )

    # ── the path-count exactness flag has to actually watch the counts ────────
    # A chain of `k` diamonds has exactly 2^k shortest paths end to end, so k = 53 sits on
    # the last exactly representable count and k = 54 is past it. A flag that were simply
    # always True — the plumbing failure this asserts against — would pass every other
    # test in this file, since none of them come near 2^53.
    for stages in range(53, 55):
        var hubs = stages + 1
        var lsrc = List[Int]()
        var ldst = List[Int]()
        var lweight = List[Float64]()
        for i in range(stages):
            var a = hubs + 2 * i
            var b = hubs + 2 * i + 1
            _add_edge(lsrc, ldst, lweight, i, a, 1.0)
            _add_edge(lsrc, ldst, lweight, a, i + 1, 1.0)
            _add_edge(lsrc, ldst, lweight, i, b, 1.0)
            _add_edge(lsrc, ldst, lweight, b, i + 1, 1.0)
        var ladder_n = hubs + 2 * stages
        var ladder = graph_csr_build(lsrc, ldst, lweight, ladder_n)
        var ladder_bc = graph_betweenness_unweighted(
            ladder.row_ptr, ladder.targets, ladder.weights, ladder_n, False
        )
        var want_exact = stages == 53
        if ladder_bc.status == GRAPH_OK and ladder_bc.path_counts_exact == want_exact:
            passed += 1
            print(
                "  ✅ 2^" + String(stages),
                "shortest paths: path_counts_exact =",
                ladder_bc.path_counts_exact,
            )
        else:
            failed += 1
            print(
                "  ❌ path-count exactness flag wrong at 2^" + String(stages) + ":",
                ladder_bc.path_counts_exact, ladder_bc.status,
            )

    # ── status names, including the ones that delegate to adjacency ───────────
    if (
        centrality_status_name(CENTRALITY_ERR_ZERO_WEIGHT_CYCLE)
        == "zero_weight_cycle_path_counts_unbounded"
        and centrality_status_name(CENTRALITY_ERR_WORK_TOO_LARGE)
        == "work_too_large_use_sampling"
        and centrality_status_name(GRAPH_ERR_ROWPTR_LENGTH)
        == "row_ptr_length_not_n_nodes_plus_one"
        and centrality_status_name(GRAPH_OK) == "ok"
    ):
        passed += 1
        print("  ✅ status names cover this module and delegate for adjacency codes")
    else:
        failed += 1
        print(
            "  ❌ status naming wrong:",
            centrality_status_name(CENTRALITY_ERR_ZERO_WEIGHT_CYCLE),
            centrality_status_name(GRAPH_ERR_ROWPTR_LENGTH),
        )

    # ── the generated A-Z pattern: 5-element lists and 5 for every Int ────────
    # This is the argument set every contract function is called with, and an unguarded
    # `row_ptr[5]` or `targets[k]` on it is a process crash rather than an error. Reaching
    # the print below at all is most of the assertion.
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)

    var az_bc = graph_betweenness_unweighted(_li5, _li5, _lf5, 5, True)
    var az_bcw = graph_betweenness_weighted(_li5, _li5, _lf5, 5, True)
    var az_close = graph_closeness_centrality(_li5, _li5, _lf5, 5, True)
    var az_harmonic = graph_harmonic_centrality(_li5, _li5, _lf5, 5, True, True)
    var az_degree = graph_degree_centrality(_li5, _li5, _lf5, 5, True)
    var az_eigen = graph_eigenvector_centrality(_li5, _li5, _lf5, 5, 5, 0.5)
    var az_pr = graph_pagerank(_li5, _li5, _lf5, 5, 0.5, 5, 0.5, True)
    if (
        az_bc.status == GRAPH_ERR_ROWPTR_LENGTH
        and az_bcw.status == GRAPH_ERR_ROWPTR_LENGTH
        and az_close.status == GRAPH_ERR_ROWPTR_LENGTH
        and az_harmonic.status == GRAPH_ERR_ROWPTR_LENGTH
        and az_degree.status == GRAPH_ERR_ROWPTR_LENGTH
        and az_eigen.status == GRAPH_ERR_ROWPTR_LENGTH
        and az_pr.status == GRAPH_ERR_ROWPTR_LENGTH
        and len(az_bc.values) == 0
        and len(az_degree.out_values) == 0
    ):
        passed += 1
        print("  ✅ every array driver rejects the A-Z 5-element/5 sample by length")
    else:
        failed += 1
        print(
            "  ❌ an A-Z sample was not rejected:",
            az_bc.status, az_close.status, az_degree.status, az_eigen.status,
            az_pr.status,
        )

    # The triplet driver takes the same sample and must not index with the node id 5 it
    # contains: that edge is outside [0, 5) and is skipped, leaving four self-loops, whose
    # betweenness is legitimately zero everywhere.
    var az_triplets = graph_betweenness_from_triplets(_li5, _li5, _lf5, 5, True, False)
    var az_all_zero = az_triplets.status == GRAPH_OK and len(az_triplets.values) == 5
    for v in range(len(az_triplets.values)):
        if az_triplets.values[v] != 0.0:
            az_all_zero = False
    if az_all_zero and az_triplets.n_sources == 5:
        passed += 1
        print("  ✅ the triplet driver skips the out-of-range endpoint and answers 0")
    else:
        failed += 1
        print(
            "  ❌ triplet A-Z sample mishandled:",
            az_triplets.status, len(az_triplets.values),
        )

    print("  [graph_analytics.centrality] Passed:", passed, "Failed:", failed)
