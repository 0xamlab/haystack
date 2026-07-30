"""test_graph_analytics_adjacency.mojo — known-value tests for the CSR adjacency.

Hand-written. The assertions target the failures that are silent rather than loud: an
edge whose endpoint does not exist being indexed instead of skipped (which is a process
crash, not an error), an unreachable node coming back as `1e18` or `0.0` instead of
absent, a parallel edge or a self-loop changing an answer, a negative weight producing a
confidently wrong shortest path, and a broken `row_ptr` producing a plausible matrix.

Three frozen kernels are the differential oracles, so the numbers here are not just
this file agreeing with itself:

* `graph.weighted.shortest_path_dijkstra` and `graph.algorithms.dijkstra` must agree
  with `graph_csr_dijkstra` **exactly** (not within a tolerance) on every graph where
  both are valid — same edge set, in-range indices, non-negative weights.
* on a graph with a negative edge the frozen Dijkstra is *wrong*, `graph.weighted
  .bellman_ford` is right, and `graph_csr_dijkstra` refuses to answer. All three are
  asserted, because "we reject this input" is only defensible if the frozen alternative
  is named and shown to work.
* `matrix_decomp.is_symmetric` is the oracle for `graph_csr_symmetry` via the dense image.
"""
from sparse_numerics.csr import MAX_CSR_DIM
from graph.algorithms import Graph, graph_add_edge, graph_new
from graph.algorithms import dijkstra as frozen_adj_dijkstra
from graph.weighted import WeightedEdge, bellman_ford, shortest_path_dijkstra
from graph_analytics.adjacency import (
    GRAPH_MAX_NODES,
    GRAPH_ERR_DENSE_TOO_LARGE,
    GRAPH_ERR_EMPTY_GRAPH,
    GRAPH_ERR_INVALID_DIMENSIONS,
    GRAPH_ERR_LENGTH_MISMATCH,
    GRAPH_ERR_NEGATIVE_WEIGHT,
    GRAPH_ERR_NON_FINITE_WEIGHT,
    GRAPH_ERR_ROWPTR_LENGTH,
    GRAPH_ERR_ROWPTR_NOT_MONOTONIC,
    GRAPH_ERR_ROWPTR_START,
    GRAPH_ERR_ROWPTR_TAIL,
    GRAPH_ERR_SOURCE_OUT_OF_RANGE,
    GRAPH_ERR_TARGET_NODE_OUT_OF_RANGE,
    GRAPH_ERR_TARGET_OUT_OF_RANGE,
    GRAPH_NO_DISTANCE,
    GRAPH_NO_LEVEL,
    GRAPH_OK,
    GraphCSR,
    graph_bfs_levels_from_triplets,
    graph_csr_bfs_levels,
    graph_csr_bfs_levels_driver,
    graph_csr_build,
    graph_csr_dedupe_min,
    graph_csr_degree_sequence,
    graph_csr_dijkstra,
    graph_csr_dijkstra_driver,
    graph_csr_edge_min_weight,
    graph_csr_empty,
    graph_csr_from_arrays,
    graph_csr_from_triplets,
    graph_csr_has_edge,
    graph_csr_has_negative_weight,
    graph_csr_in_degrees,
    graph_csr_out_degrees,
    graph_csr_reverse,
    graph_csr_shortest_path,
    graph_csr_symmetry,
    graph_csr_to_dense,
    graph_csr_validate,
    graph_csr_validate_flat,
    graph_dijkstra_from_triplets,
    graph_status_name,
)
from matrix_decomp import is_symmetric

comptime FROZEN_INF: Float64 = 1e18


fn _same_ints(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _same_floats(a: List[Float64], b: List[Float64]) -> Bool:
    """Exact equality. Every weight here is a small integer or a half, so every distance
    is exactly representable; a tolerance would hide a genuine mis-relaxation and would
    hide a distance that came back from the wrong node's bucket."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _frozen_edges(
    src: List[Int], dst: List[Int], weight: List[Float64]
) -> List[WeightedEdge]:
    """The same edge set as a frozen triplet list, so the oracles see identical input."""
    var edges = List[WeightedEdge]()
    for k in range(len(src)):
        edges.append(WeightedEdge(src[k], dst[k], weight[k]))
    return edges^


fn _frozen_graph(
    src: List[Int], dst: List[Int], weight: List[Float64], n: Int
) -> Graph:
    var g = graph_new(n)
    for k in range(len(src)):
        graph_add_edge(g, src[k], dst[k], weight[k])
    return g^


fn _nested(values: List[Float64], n: Int) -> List[List[Float64]]:
    """Flat row-major to the list-of-rows shape `matrix_decomp.is_symmetric` takes."""
    var rows = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            row.append(values[i * n + j])
        rows.append(row^)
    return rows^


fn _demo_src() -> List[Int]:
    """Edges 0->1 (4), 0->2 (1), 2->1 (2), 1->3 (5), 2->3 (8), 3->4 (3); node 5 isolated.
    """
    var out = List[Int]()
    out.append(0)
    out.append(0)
    out.append(2)
    out.append(1)
    out.append(2)
    out.append(3)
    return out^


fn _demo_dst() -> List[Int]:
    var out = List[Int]()
    out.append(1)
    out.append(2)
    out.append(1)
    out.append(3)
    out.append(3)
    out.append(4)
    return out^


fn _demo_weight() -> List[Float64]:
    var out = List[Float64]()
    out.append(4.0)
    out.append(1.0)
    out.append(2.0)
    out.append(5.0)
    out.append(8.0)
    out.append(3.0)
    return out^


fn _ring_src() -> List[Int]:
    """An 8-node ring plus four chords: every node reaches every other, so the frozen
    oracles are valid everywhere and every source can be compared."""
    var out = List[Int]()
    for u in range(8):
        out.append(u)
    out.append(0)
    out.append(2)
    out.append(1)
    out.append(3)
    return out^


fn _ring_dst() -> List[Int]:
    var out = List[Int]()
    for u in range(8):
        out.append((u + 1) % 8)
    out.append(4)
    out.append(6)
    out.append(5)
    out.append(0)
    return out^


fn _ring_weight() -> List[Float64]:
    var out = List[Float64]()
    for _ in range(8):
        out.append(2.0)
    out.append(7.0)
    out.append(3.0)
    out.append(4.0)
    out.append(1.0)
    return out^


fn main() raises:
    var passed = 0
    var failed = 0

    var src = _demo_src()
    var dst = _demo_dst()
    var weight = _demo_weight()
    var g = graph_csr_from_triplets(src, dst, weight, 6)

    # ── the CSR is the layout `graph.algorithms.Graph` only claims to be ──────
    # row_ptr [0,2,3,5,6,6,6]: node 0 owns [0,2), node 4 and node 5 own nothing. Rows
    # ascend by target without a comparison sort, and that is a verified flag, not a hope.
    var want_row_ptr = List[Int]()
    want_row_ptr.append(0)
    want_row_ptr.append(2)
    want_row_ptr.append(3)
    want_row_ptr.append(5)
    want_row_ptr.append(6)
    want_row_ptr.append(6)
    want_row_ptr.append(6)
    var want_targets = List[Int]()
    want_targets.append(1)
    want_targets.append(2)
    want_targets.append(3)
    want_targets.append(1)
    want_targets.append(3)
    want_targets.append(4)
    var want_weights = List[Float64]()
    want_weights.append(4.0)
    want_weights.append(1.0)
    want_weights.append(5.0)
    want_weights.append(2.0)
    want_weights.append(8.0)
    want_weights.append(3.0)
    if (
        graph_csr_validate(g) == GRAPH_OK
        and _same_ints(g.row_ptr, want_row_ptr)
        and _same_ints(g.targets, want_targets)
        and _same_floats(g.weights, want_weights)
        and g.sorted_targets
        and g.deduplicated
        and g.skipped_edges == 0
        and g.n_edges() == 6
        and g.out_degree(0) == 2
        and g.out_degree(5) == 0
        and g.out_degree(99) == 0
    ):
        passed += 1
        print("  ✅ CSR row_ptr [0,2,3,5,6,6,6], rows sorted, no edges invented")
    else:
        failed += 1
        print("  ❌ CSR structure wrong:", g.n_edges(), g.skipped_edges)

    # ── distances agree with BOTH frozen Dijkstras, exactly ──────────────────
    # Hand-computed: 0->2 is 1, so 0->2->1 is 3 and beats the direct 4; 3 is 3+5=8 (not
    # 1+8=9) and 4 is 11. If the heap's bucket table ever returned the wrong node for a
    # popped key, this is where the wrong number would appear.
    var mine = graph_csr_dijkstra(g, 0)
    var frozen_triplet = shortest_path_dijkstra(6, _frozen_edges(src, dst, weight), 0)
    var frozen_adj = frozen_adj_dijkstra(_frozen_graph(src, dst, weight, 6), 0)
    var want_dist = List[Float64]()
    want_dist.append(0.0)
    want_dist.append(3.0)
    want_dist.append(1.0)
    want_dist.append(8.0)
    want_dist.append(11.0)
    var agree = mine.status == GRAPH_OK and len(mine.distance) == 6
    if agree:
        for v in range(5):
            if (
                mine.distance[v] != want_dist[v]
                or frozen_triplet[v] != want_dist[v]
                or frozen_adj[v] != want_dist[v]
            ):
                agree = False
    if agree and mine.settled_count == 5 and mine.heap_pushes >= 5:
        passed += 1
        print("  ✅ distances [0,3,1,8,11] match both frozen Dijkstras exactly")
    else:
        failed += 1
        print("  ❌ distances disagree:", mine.status, len(mine.distance))

    # ── an unreachable node is absent, not 1e18 and not 0.0 ──────────────────
    # The frozen kernels return exactly 1e18 for node 5, which is a legal distance and
    # survives arithmetic (1e18 + 3 == 1e18). That is the failure this contract removes.
    if (
        not mine.reached[5]
        and mine.distance[5] == GRAPH_NO_DISTANCE
        and mine.distance[5] != FROZEN_INF
        and mine.distance[5] != 0.0
        and mine.unreachable_count == 1
        and mine.settled_count + mine.unreachable_count == 6
        and mine.predecessor[5] == -1
        and mine.predecessor[0] == -1
        and mine.predecessor[1] == 2
        and mine.predecessor[4] == 3
        and frozen_triplet[5] == FROZEN_INF
        and frozen_adj[5] == FROZEN_INF
    ):
        passed += 1
        print("  ✅ node 5 reported unreachable; the frozen kernels report 1e18")
    else:
        failed += 1
        print("  ❌ unreachability leaked:", mine.distance[5], mine.reached[5])

    # ── BFS levels count hops, and mark the node they never saw ──────────────
    var levels = graph_csr_bfs_levels(g, 0)
    var want_levels = List[Int]()
    want_levels.append(0)
    want_levels.append(1)
    want_levels.append(1)
    want_levels.append(2)
    want_levels.append(3)
    want_levels.append(GRAPH_NO_LEVEL)
    if (
        levels.status == GRAPH_OK
        and _same_ints(levels.level, want_levels)
        and levels.reached_count == 5
        and levels.unreachable_count == 1
        and levels.max_level == 3
        and not levels.reached[5]
    ):
        passed += 1
        print("  ✅ BFS levels [0,1,1,2,3,absent]; hop count ignores the weights")
    else:
        failed += 1
        print("  ❌ BFS wrong:", levels.status, levels.max_level, levels.reached_count)

    # ── a path is the predecessor walk, and it cannot disagree with its cost ──
    var path = graph_csr_shortest_path(g, 0, 4)
    var want_path = List[Int]()
    want_path.append(0)
    want_path.append(2)
    want_path.append(1)
    want_path.append(3)
    want_path.append(4)
    var no_path = graph_csr_shortest_path(g, 0, 5)
    if (
        path.status == GRAPH_OK
        and path.found
        and _same_ints(path.nodes, want_path)
        and path.hops == 4
        and path.total_weight == 11.0
        and path.total_weight == mine.distance[4]
        and no_path.status == GRAPH_OK
        and not no_path.found
        and len(no_path.nodes) == 0
        and no_path.total_weight == GRAPH_NO_DISTANCE
    ):
        passed += 1
        print("  ✅ path 0->2->1->3->4 costs 11; 0->5 is absent, not a stub path")
    else:
        failed += 1
        print("  ❌ path wrong:", path.found, path.hops, path.total_weight)

    # ── an endpoint outside [0, n) is skipped and counted, and nothing crashes ─
    # `graph.weighted.shortest_path_dijkstra` would do `adj_dst[7].append(...)` on this
    # edge list and take the process down. The distances must be unchanged, because the
    # skipped edges do not exist in a 6-node graph.
    var dirty_src = _demo_src()
    var dirty_dst = _demo_dst()
    var dirty_weight = _demo_weight()
    dirty_src.append(7)
    dirty_dst.append(1)
    dirty_weight.append(0.5)
    dirty_src.append(0)
    dirty_dst.append(-1)
    dirty_weight.append(0.5)
    dirty_src.append(6)
    dirty_dst.append(6)
    dirty_weight.append(0.5)
    var dirty_build = graph_csr_build(dirty_src, dirty_dst, dirty_weight, 6)
    var dirty_dist = graph_dijkstra_from_triplets(
        dirty_src, dirty_dst, dirty_weight, 6, 0
    )
    if (
        dirty_build.status == GRAPH_OK
        and dirty_build.skipped_edges == 3
        and dirty_build.n_edges == 6
        and _same_ints(dirty_build.row_ptr, want_row_ptr)
        and dirty_build.self_loops == 0
        and dirty_build.duplicate_edges == 0
        and dirty_build.negative_weights == 0
        and dirty_dist.status == GRAPH_OK
        and _same_floats(dirty_dist.distance, mine.distance)
        and not dirty_dist.reached[5]
    ):
        passed += 1
        print("  ✅ 3 out-of-range endpoints skipped and reported; distances unchanged")
    else:
        failed += 1
        print("  ❌ stray endpoints mishandled:", dirty_build.status, dirty_build.skipped_edges)

    # ── mismatched triplet arrays are not a graph ────────────────────────────
    var short_weight = List[Float64]()
    short_weight.append(1.0)
    var ragged = graph_csr_from_triplets(src, dst, short_weight, 6)
    var ragged_build = graph_csr_build(src, dst, short_weight, 6)
    var ragged_dijkstra = graph_dijkstra_from_triplets(src, dst, short_weight, 6, 0)
    if (
        ragged.n_edges() == 0
        and ragged.skipped_edges == 6
        and graph_csr_validate(ragged) == GRAPH_OK
        and ragged_build.status == GRAPH_ERR_LENGTH_MISMATCH
        and ragged_build.n_edges == 0
        and ragged_dijkstra.status == GRAPH_ERR_LENGTH_MISMATCH
        and len(ragged_dijkstra.distance) == 0
    ):
        passed += 1
        print("  ✅ ragged triplet arrays: 6 edges skipped, driver says length_mismatch")
    else:
        failed += 1
        print("  ❌ ragged input wrong:", ragged.skipped_edges, ragged_build.status)

    # ── a negative weight is rejected, and the frozen Dijkstra shows why ─────
    # 0->1 (1), 0->2 (5), 2->1 (-10), 1->3 (1). True distances are [0,-5,5,-4]: the path
    # 0->2->1->3 costs -4. The frozen Dijkstra settles node 1 at 1, expands 3 to 2, and
    # only then discovers -5 for node 1 — node 3 keeps the wrong 2.0 and nothing says so.
    var neg_src = List[Int]()
    var neg_dst = List[Int]()
    var neg_w = List[Float64]()
    neg_src.append(0)
    neg_dst.append(1)
    neg_w.append(1.0)
    neg_src.append(0)
    neg_dst.append(2)
    neg_w.append(5.0)
    neg_src.append(2)
    neg_dst.append(1)
    neg_w.append(-10.0)
    neg_src.append(1)
    neg_dst.append(3)
    neg_w.append(1.0)
    var neg_graph = graph_csr_from_triplets(neg_src, neg_dst, neg_w, 4)
    var neg_mine = graph_csr_dijkstra(neg_graph, 0)
    var neg_edges = _frozen_edges(neg_src, neg_dst, neg_w)
    var neg_frozen = shortest_path_dijkstra(4, neg_edges, 0)
    var neg_bellman = bellman_ford(4, neg_edges, 0)
    if (
        neg_mine.status == GRAPH_ERR_NEGATIVE_WEIGHT
        and len(neg_mine.distance) == 0
        and len(neg_mine.reached) == 0
        and neg_mine.settled_count == 0
        and graph_csr_has_negative_weight(neg_graph)
        and neg_frozen[3] == 2.0
        and neg_bellman[3] == -4.0
        and neg_bellman[1] == -5.0
        and graph_status_name(GRAPH_ERR_NEGATIVE_WEIGHT)
        == "negative_weight_use_bellman_ford"
    ):
        passed += 1
        print("  ✅ negative edge refused with a status; frozen dijkstra says 2.0 for")
        print("     node 3 where bellman_ford says -4.0, which is why it is refused")
    else:
        failed += 1
        print("  ❌ negative-weight handling wrong:", neg_mine.status, neg_frozen[3], neg_bellman[3])

    # ── a NaN weight is caught before the sign test ──────────────────────────
    # `nan < 0.0` is False, so a bare negativity check would let it into the relaxation
    # and every comparison downstream would silently be False.
    var nan_w = _demo_weight()
    nan_w[2] = Float64(0.0) / Float64(0.0)
    var nan_graph = graph_csr_from_triplets(src, dst, nan_w, 6)
    var nan_result = graph_csr_dijkstra(nan_graph, 0)
    var inf_w = _demo_weight()
    var huge: Float64 = 1e308
    inf_w[2] = huge * huge
    var inf_result = graph_csr_dijkstra(
        graph_csr_from_triplets(src, dst, inf_w, 6), 0
    )
    if (
        nan_result.status == GRAPH_ERR_NON_FINITE_WEIGHT
        and len(nan_result.distance) == 0
        and inf_result.status == GRAPH_ERR_NON_FINITE_WEIGHT
        and not graph_csr_has_negative_weight(nan_graph)
    ):
        passed += 1
        print("  ✅ NaN and inf weights rejected as non_finite, not as negative")
    else:
        failed += 1
        print("  ❌ non-finite weight leaked:", nan_result.status, inf_result.status)

    # ── every source on a denser graph, against both frozen kernels ──────────
    # A ring makes every node reachable from every other, so the oracles are valid for
    # all eight sources and the comparison covers ties, chords and multi-hop relaxation.
    var rsrc = _ring_src()
    var rdst = _ring_dst()
    var rw = _ring_weight()
    var ring = graph_csr_from_triplets(rsrc, rdst, rw, 8)
    var ring_edges = _frozen_edges(rsrc, rdst, rw)
    var ring_graph = _frozen_graph(rsrc, rdst, rw, 8)
    var ring_ok = graph_csr_validate(ring) == GRAPH_OK and ring.n_edges() == 12
    for s in range(8):
        var got = graph_csr_dijkstra(ring, s)
        var oracle_a = shortest_path_dijkstra(8, ring_edges, s)
        var oracle_b = frozen_adj_dijkstra(ring_graph, s)
        if got.status != GRAPH_OK or got.settled_count != 8:
            ring_ok = False
            continue
        for v in range(8):
            if not got.reached[v]:
                ring_ok = False
            elif got.distance[v] != oracle_a[v] or got.distance[v] != oracle_b[v]:
                ring_ok = False
    if ring_ok:
        passed += 1
        print("  ✅ 8 sources x 8 targets identical to both frozen Dijkstras")
    else:
        failed += 1
        print("  ❌ ring differential failed")

    # ── a self-loop and a parallel edge change nothing, and are counted ──────
    # 0->1 twice (7 and 2), a 1->1 self-loop (3), and 1->2 (1). The lighter parallel edge
    # wins by relaxation, the self-loop can never improve a distance, and the counts say
    # the graph is a multigraph so a caller can canonicalise deliberately.
    var msrc = List[Int]()
    var mdst = List[Int]()
    var mw = List[Float64]()
    msrc.append(0)
    mdst.append(1)
    mw.append(7.0)
    msrc.append(0)
    mdst.append(1)
    mw.append(2.0)
    msrc.append(1)
    mdst.append(1)
    mw.append(3.0)
    msrc.append(1)
    mdst.append(2)
    mw.append(1.0)
    var multi = graph_csr_from_triplets(msrc, mdst, mw, 3)
    var multi_build = graph_csr_build(msrc, mdst, mw, 3)
    var canonical = graph_csr_dedupe_min(multi)
    var multi_dist = graph_csr_dijkstra(multi, 0)
    var canonical_dist = graph_csr_dijkstra(canonical, 0)
    var multi_frozen = shortest_path_dijkstra(3, _frozen_edges(msrc, mdst, mw), 0)
    var want_multi = List[Float64]()
    want_multi.append(0.0)
    want_multi.append(2.0)
    want_multi.append(3.0)
    if (
        multi_build.status == GRAPH_OK
        and multi_build.self_loops == 1
        and multi_build.duplicate_edges == 1
        and not multi_build.deduplicated
        and multi.n_edges() == 4
        and canonical.n_edges() == 3
        and canonical.is_canonical()
        and _same_floats(multi_dist.distance, want_multi)
        and _same_floats(canonical_dist.distance, want_multi)
        and multi_frozen[1] == 2.0
        and multi_frozen[2] == 3.0
    ):
        passed += 1
        print("  ✅ parallel edge + self-loop counted, collapsed to min, answers equal")
    else:
        failed += 1
        print("  ❌ multigraph handling wrong:", multi_build.duplicate_edges, canonical.n_edges())

    # ── arrays from the wire claim nothing, so dedupe sorts before merging ────
    # Row 0 arrives as targets [2, 1, 2] with weights [9, 4, 3]: unsorted, with (0,2)
    # duplicated and its copies *not adjacent*. A dedupe that trusted the input order
    # would merge nothing and keep 9 for (0,2) — the wrong weight, silently. Canonical
    # form is targets [1, 2] with weights [4, 3].
    var wire_ptr = List[Int]()
    wire_ptr.append(0)
    wire_ptr.append(3)
    wire_ptr.append(3)
    wire_ptr.append(3)
    var wire_targets = List[Int]()
    wire_targets.append(2)
    wire_targets.append(1)
    wire_targets.append(2)
    var wire_weights = List[Float64]()
    wire_weights.append(9.0)
    wire_weights.append(4.0)
    wire_weights.append(3.0)
    var wire = graph_csr_from_arrays(wire_ptr, wire_targets, wire_weights, 3)
    var wire_canonical = graph_csr_dedupe_min(wire)
    var wire_twice = graph_csr_dedupe_min(wire_canonical)
    var want_wire_targets = List[Int]()
    want_wire_targets.append(1)
    want_wire_targets.append(2)
    var want_wire_weights = List[Float64]()
    want_wire_weights.append(4.0)
    want_wire_weights.append(3.0)
    var wire_dist = graph_csr_dijkstra(wire, 0)
    var wire_canonical_dist = graph_csr_dijkstra(wire_canonical, 0)
    if (
        not wire.sorted_targets
        and not wire.deduplicated
        and graph_csr_validate(wire) == GRAPH_OK
        and wire_canonical.is_canonical()
        and _same_ints(wire_canonical.targets, want_wire_targets)
        and _same_floats(wire_canonical.weights, want_wire_weights)
        and _same_ints(wire_twice.targets, wire_canonical.targets)
        and _same_floats(wire_twice.weights, wire_canonical.weights)
        and _same_floats(wire_dist.distance, wire_canonical_dist.distance)
        and wire_dist.distance[2] == 3.0
        and graph_csr_edge_min_weight(wire, 0, 2).weight == 3.0
        and graph_csr_edge_min_weight(wire, 0, 2).multiplicity == 2
    ):
        passed += 1
        print("  ✅ unsorted wire arrays: non-adjacent duplicate merged to 3.0, not 9.0,")
        print("     and dedupe is idempotent")
    else:
        failed += 1
        print("  ❌ unsorted input mishandled:", len(wire_canonical.targets), wire_canonical.weights[0])

    # ── an edge query says how many copies, and absence has no weight ────────
    var q_dup = graph_csr_edge_min_weight(multi, 0, 1)
    var q_canon = graph_csr_edge_min_weight(canonical, 0, 1)
    var q_loop = graph_csr_edge_min_weight(multi, 1, 1)
    var q_absent = graph_csr_edge_min_weight(multi, 2, 0)
    var q_bad = graph_csr_edge_min_weight(multi, 0, 9)
    if (
        q_dup.found
        and q_dup.multiplicity == 2
        and q_dup.weight == 2.0
        and q_canon.multiplicity == 1
        and q_canon.weight == 2.0
        and q_loop.found
        and q_loop.weight == 3.0
        and q_absent.status == GRAPH_OK
        and not q_absent.found
        and q_absent.multiplicity == 0
        and q_bad.status == GRAPH_ERR_TARGET_NODE_OUT_OF_RANGE
        and not graph_csr_has_edge(multi, 2, 0)
        and not graph_csr_has_edge(multi, 0, 9)
    ):
        passed += 1
        print("  ✅ edge query: multiplicity 2 min 2.0; absent edge carries no weight")
    else:
        failed += 1
        print("  ❌ edge query wrong:", q_dup.multiplicity, q_dup.weight, q_absent.found)

    # ── symmetry, checked against the frozen is_symmetric on the dense image ─
    # Weights are nonzero so `absent = 0.0` is unambiguous for the oracle; that caveat is
    # in the driver's docstring and is exactly why the oracle is only used this way.
    var usrc = List[Int]()
    var udst = List[Int]()
    var uw = List[Float64]()
    usrc.append(0)
    udst.append(1)
    uw.append(2.0)
    usrc.append(1)
    udst.append(0)
    uw.append(2.0)
    usrc.append(1)
    udst.append(2)
    uw.append(5.0)
    usrc.append(2)
    udst.append(1)
    uw.append(5.0)
    var undirected = graph_csr_from_triplets(usrc, udst, uw, 3)
    var sym = graph_csr_symmetry(undirected, 1e-12)
    var dense_sym = graph_csr_to_dense(undirected, 0.0)
    var oracle_sym = is_symmetric(_nested(dense_sym.values, 3), 1e-12)

    var asym_src = List[Int]()
    var asym_dst = List[Int]()
    var asym_w = List[Float64]()
    for k in range(3):
        asym_src.append(usrc[k])
        asym_dst.append(udst[k])
        asym_w.append(uw[k])
    var asym = graph_csr_from_triplets(asym_src, asym_dst, asym_w, 3)
    var asym_report = graph_csr_symmetry(asym, 1e-12)
    var asym_dense = graph_csr_to_dense(asym, 0.0)
    var asym_oracle = is_symmetric(_nested(asym_dense.values, 3), 1e-12)

    var skew_w = List[Float64]()
    for k in range(4):
        skew_w.append(uw[k])
    skew_w[1] = 3.0
    var skew = graph_csr_symmetry(graph_csr_from_triplets(usrc, udst, skew_w, 3), 1e-12)
    if (
        sym.status == GRAPH_OK
        and sym.structurally_symmetric
        and sym.weight_symmetric
        and sym.distinct_edges == 4
        and sym.self_loops == 0
        and oracle_sym
        and not asym_report.structurally_symmetric
        and asym_report.missing_reverse == 1
        and not asym_oracle
        and skew.structurally_symmetric
        and not skew.weight_symmetric
        and skew.weight_mismatch == 2
    ):
        passed += 1
        print("  ✅ symmetry agrees with frozen is_symmetric; a weight skew is caught")
        print("     structurally but reported as a weight mismatch, not a missing edge")
    else:
        failed += 1
        print("  ❌ symmetry wrong:", sym.weight_symmetric, asym_report.missing_reverse, skew.weight_mismatch)

    # ── the reverse graph is the transpose, twice over ───────────────────────
    # in-degrees counted from `targets` must equal out-degrees of the reverse, and
    # reversing a sorted graph twice must reproduce it array for array.
    var reversed_g = graph_csr_reverse(g)
    var round_trip = graph_csr_reverse(reversed_g)
    var in_deg = graph_csr_in_degrees(g)
    var rev_out = graph_csr_out_degrees(reversed_g)
    var want_in = List[Int]()
    want_in.append(0)
    want_in.append(2)
    want_in.append(1)
    want_in.append(2)
    want_in.append(1)
    want_in.append(0)
    if (
        graph_csr_validate(reversed_g) == GRAPH_OK
        and _same_ints(in_deg, want_in)
        and _same_ints(in_deg, rev_out)
        and reversed_g.sorted_targets
        and _same_ints(round_trip.row_ptr, g.row_ptr)
        and _same_ints(round_trip.targets, g.targets)
        and _same_floats(round_trip.weights, g.weights)
        and graph_csr_has_edge(reversed_g, 4, 3)
        and not graph_csr_has_edge(reversed_g, 3, 4)
    ):
        passed += 1
        print("  ✅ reverse: in-degrees == reversed out-degrees, reverse twice is identity")
    else:
        failed += 1
        print("  ❌ reverse wrong:", len(reversed_g.targets), reversed_g.sorted_targets)

    # ── degree sequence, sorted by the frozen counting sort ──────────────────
    var sequence = graph_csr_degree_sequence(g)
    var want_sequence = List[Int]()
    want_sequence.append(2)
    want_sequence.append(2)
    want_sequence.append(1)
    want_sequence.append(1)
    want_sequence.append(0)
    want_sequence.append(0)
    var out_deg = graph_csr_out_degrees(g)
    var want_out = List[Int]()
    want_out.append(2)
    want_out.append(1)
    want_out.append(2)
    want_out.append(1)
    want_out.append(0)
    want_out.append(0)
    if _same_ints(sequence, want_sequence) and _same_ints(out_deg, want_out):
        passed += 1
        print("  ✅ out-degrees [2,1,2,1,0,0]; degree sequence descending [2,2,1,1,0,0]")
    else:
        failed += 1
        print("  ❌ degrees wrong:", len(sequence), len(out_deg))

    # ── the dense image, and the size it refuses to materialise ──────────────
    var dense = graph_csr_to_dense(g, 0.0)
    var dense_ok = dense.status == GRAPH_OK and dense.length == 36
    if dense_ok:
        # 0->2 is 1.0, 2->3 is 8.0, and the 5th row is empty in both directions.
        if (
            dense.values[0 * 6 + 2] != 1.0
            or dense.values[2 * 6 + 3] != 8.0
            or dense.values[0 * 6 + 0] != 0.0
            or dense.values[5 * 6 + 4] != 0.0
            or dense.values[4 * 6 + 3] != 0.0
        ):
            dense_ok = False
    var too_big = graph_csr_to_dense(graph_csr_empty(3000), 0.0)
    if dense_ok and too_big.status == GRAPH_ERR_DENSE_TOO_LARGE and len(too_big.values) == 0:
        passed += 1
        print("  ✅ dense image 6x6 with the weights in place; 3000x3000 refused")
    else:
        failed += 1
        print("  ❌ dense image wrong:", dense.status, dense.length, too_big.status)

    # ── one code per structural defect ───────────────────────────────────────
    # Each of these is a different array being wrong, and a caller that gets a single
    # "invalid" code has to re-check all four.
    var ok_ptr = List[Int]()
    ok_ptr.append(0)
    ok_ptr.append(1)
    ok_ptr.append(1)
    var one_target = List[Int]()
    one_target.append(1)
    var one_weight = List[Float64]()
    one_weight.append(1.0)
    var non_monotonic = List[Int]()
    non_monotonic.append(0)
    non_monotonic.append(2)
    non_monotonic.append(1)
    var bad_start = List[Int]()
    bad_start.append(1)
    bad_start.append(1)
    bad_start.append(1)
    var bad_tail = List[Int]()
    bad_tail.append(0)
    bad_tail.append(0)
    bad_tail.append(0)
    var far_target = List[Int]()
    far_target.append(9)
    var two_weights = List[Float64]()
    two_weights.append(1.0)
    two_weights.append(2.0)
    if (
        graph_csr_validate_flat(ok_ptr, one_target, one_weight, 2) == GRAPH_OK
        and graph_csr_validate_flat(ok_ptr, one_target, one_weight, -1)
        == GRAPH_ERR_INVALID_DIMENSIONS
        and graph_csr_validate_flat(ok_ptr, one_target, two_weights, 2)
        == GRAPH_ERR_LENGTH_MISMATCH
        and graph_csr_validate_flat(ok_ptr, one_target, one_weight, 5)
        == GRAPH_ERR_ROWPTR_LENGTH
        and graph_csr_validate_flat(bad_start, one_target, one_weight, 2)
        == GRAPH_ERR_ROWPTR_START
        and graph_csr_validate_flat(non_monotonic, one_target, one_weight, 2)
        == GRAPH_ERR_ROWPTR_NOT_MONOTONIC
        and graph_csr_validate_flat(bad_tail, one_target, one_weight, 2)
        == GRAPH_ERR_ROWPTR_TAIL
        and graph_csr_validate_flat(ok_ptr, far_target, one_weight, 2)
        == GRAPH_ERR_TARGET_OUT_OF_RANGE
        and graph_status_name(GRAPH_ERR_ROWPTR_TAIL) == "row_ptr_tail_not_n_edges"
    ):
        passed += 1
        print("  ✅ seven structural defects, seven distinct codes")
    else:
        failed += 1
        print("  ❌ validation codes wrong:", graph_csr_validate_flat(bad_tail, one_target, one_weight, 2))

    # ── a target index past the end is a status, not a crash ─────────────────
    # This is the one that matters most: `row_ptr` says row 0 has an edge and `targets`
    # says it goes to node 9 of a 2-node graph. Relaxing it would read `dist[9]`, which
    # is an uncatchable process crash — so the traversal must never start.
    var poisoned = graph_csr_from_arrays(ok_ptr, far_target, one_weight, 2)
    var poisoned_dist = graph_csr_dijkstra(poisoned, 0)
    var poisoned_bfs = graph_csr_bfs_levels(poisoned, 0)
    var poisoned_dense = graph_csr_to_dense(poisoned, 0.0)
    var poisoned_sym = graph_csr_symmetry(poisoned, 1e-12)
    var poisoned_reverse = graph_csr_reverse(poisoned)
    var poisoned_dedupe = graph_csr_dedupe_min(poisoned)
    if (
        poisoned_dist.status == GRAPH_ERR_TARGET_OUT_OF_RANGE
        and len(poisoned_dist.distance) == 0
        and poisoned_bfs.status == GRAPH_ERR_TARGET_OUT_OF_RANGE
        and len(poisoned_bfs.level) == 0
        and poisoned_dense.status == GRAPH_ERR_TARGET_OUT_OF_RANGE
        and poisoned_sym.status == GRAPH_ERR_TARGET_OUT_OF_RANGE
        and not poisoned_sym.structurally_symmetric
        and poisoned_reverse.n_nodes == 0
        and poisoned_reverse.n_edges() == 0
        and poisoned_dedupe.n_edges() == 0
        and len(graph_csr_out_degrees(poisoned)) == 0
        and len(graph_csr_in_degrees(poisoned)) == 0
    ):
        passed += 1
        print("  ✅ a target of 9 in a 2-node graph yields statuses and no traversal")
    else:
        failed += 1
        print("  ❌ poisoned graph produced results:", poisoned_dist.status, poisoned_reverse.n_edges())

    # ── a broken row_ptr has no reverse, no dense image and no degrees ───────
    var broken = graph_csr_from_arrays(non_monotonic, one_target, one_weight, 2)
    var broken_dist = graph_csr_dijkstra_driver(
        non_monotonic, one_target, one_weight, 2, 0
    )
    var broken_bfs = graph_csr_bfs_levels_driver(
        non_monotonic, one_target, one_weight, 2, 0
    )
    if (
        graph_csr_validate(broken) == GRAPH_ERR_ROWPTR_NOT_MONOTONIC
        and broken_dist.status == GRAPH_ERR_ROWPTR_NOT_MONOTONIC
        and len(broken_dist.distance) == 0
        and broken_dist.settled_count == 0
        and broken_bfs.status == GRAPH_ERR_ROWPTR_NOT_MONOTONIC
        and graph_csr_reverse(broken).n_nodes == 0
        and len(graph_csr_degree_sequence(broken)) == 0
    ):
        passed += 1
        print("  ✅ a non-monotonic row_ptr yields no distances, no reverse, no degrees")
    else:
        failed += 1
        print("  ❌ broken row_ptr produced results:", broken_dist.status)

    # ── a missing source and an empty graph are distinct absences ────────────
    var no_source = graph_csr_dijkstra(g, 99)
    var neg_source = graph_csr_dijkstra(g, -1)
    var empty = graph_csr_dijkstra(graph_csr_empty(0), 0)
    var empty_bfs = graph_csr_bfs_levels(graph_csr_empty(0), 0)
    var no_target = graph_csr_shortest_path(g, 0, 99)
    if (
        no_source.status == GRAPH_ERR_SOURCE_OUT_OF_RANGE
        and len(no_source.distance) == 0
        and neg_source.status == GRAPH_ERR_SOURCE_OUT_OF_RANGE
        and empty.status == GRAPH_ERR_EMPTY_GRAPH
        and empty_bfs.status == GRAPH_ERR_EMPTY_GRAPH
        and no_target.status == GRAPH_ERR_TARGET_NODE_OUT_OF_RANGE
        and not no_target.found
        and no_target.total_weight == GRAPH_NO_DISTANCE
    ):
        passed += 1
        print("  ✅ absent source, absent target and empty graph are three codes")
    else:
        failed += 1
        print("  ❌ absence codes wrong:", no_source.status, empty.status, no_target.status)

    # ── the generated A-Z argument pattern: five-element lists, every Int 5 ──
    # `tests/generate_mojo_tests.py` calls every contract function with `_li5`
    # ([1,2,3,4,5]), `_lf5` and 5 for each Int. Any of these indexing on faith would kill
    # the worker for the whole suite, so the pattern is asserted here rather than
    # discovered in CI.
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
    var az_dijkstra = graph_csr_dijkstra_driver(li5, li5, lf5, 5, 5)
    var az_bfs = graph_csr_bfs_levels_driver(li5, li5, lf5, 5, 5)
    var az_triplet = graph_dijkstra_from_triplets(li5, li5, lf5, 5, 5)
    var az_levels = graph_bfs_levels_from_triplets(li5, li5, lf5, 5, 5)
    var az_build = graph_csr_build(li5, li5, lf5, 5)
    var az_struct = graph_csr_dijkstra(
        GraphCSR(li5.copy(), li5.copy(), lf5.copy(), 5, True, True, 5), 5
    )
    if (
        az_dijkstra.status == GRAPH_ERR_ROWPTR_LENGTH
        and az_bfs.status == GRAPH_ERR_ROWPTR_LENGTH
        and az_struct.status == GRAPH_ERR_ROWPTR_LENGTH
        and az_triplet.status == GRAPH_ERR_SOURCE_OUT_OF_RANGE
        and az_levels.status == GRAPH_ERR_SOURCE_OUT_OF_RANGE
        and az_build.status == GRAPH_OK
        and az_build.skipped_edges == 1
        and az_build.n_edges == 4
        and az_build.self_loops == 4
    ):
        passed += 1
        print("  ✅ the generated suite's 5-element/5 pattern is answered, not crashed")
    else:
        failed += 1
        print("  ❌ A-Z pattern mishandled:", az_dijkstra.status, az_triplet.status, az_build.skipped_edges)

    # ── a consistent node count can still be an allocation bomb ───────────────
    # row_ptr holds one entry PER NODE regardless of edge count, so
    # graph_csr_empty(10**12) was a structurally valid empty graph asking for 8 TB.
    # Clamping negatives (which it did) is not a bound.
    var bomb = graph_csr_empty(1000000000000)
    if bomb.n_nodes == 0:
        passed += 1
        print("  \u2705 graph_csr_empty refuses 10^12 nodes instead of allocating")
    else:
        failed += 1
        print("  \u274c graph_csr_empty allocated", bomb.n_nodes, "nodes")

    var legit = graph_csr_empty(1000)
    if legit.n_nodes == 1000 and len(legit.row_ptr) == 1001:
        passed += 1
        print("  \u2705 a real 1000-node graph still builds")
    else:
        failed += 1
        print("  \u274c a legitimate node count regressed")

    var lone_ptr = List[Int]()
    lone_ptr.append(0)
    var no_tgt = List[Int]()
    var no_wt = List[Float64]()
    if graph_csr_validate_flat(lone_ptr, no_tgt, no_wt, 1000000000000) != GRAPH_OK:
        passed += 1
        print("  \u2705 the validator rejects an over-ceiling node count")
    else:
        failed += 1
        print("  \u274c validator accepted 10^12 nodes")

    # ── the ceiling is SHARED with sparse_numerics, not restated ──────────────
    # A graph adjacency in CSR is exactly an n x n sparse matrix in CSR, so a node count
    # this module accepts must be one the matrix side accepts. Two ceilings would let a
    # graph convert into a matrix its own validator refuses.
    if GRAPH_MAX_NODES == MAX_CSR_DIM:
        passed += 1
        print("  \u2705 the node ceiling IS sparse_numerics MAX_CSR_DIM:", GRAPH_MAX_NODES)
    else:
        failed += 1
        print("  \u274c graph and matrix ceilings diverged")

    # ── the structural validator delegates rather than duplicating ────────────
    # It used to be a line-for-line copy of csr_validate_flat, which is how the graph
    # side missed the dimension ceiling the matrix side had already grown. Same defect,
    # same code, through both entry points.
    var bad_ptr = List[Int]()
    bad_ptr.append(0)
    bad_ptr.append(5)
    bad_ptr.append(2)          # non-monotonic
    var two_tgt = List[Int]()
    two_tgt.append(0)
    two_tgt.append(1)
    var two_wt = List[Float64]()
    two_wt.append(1.0)
    two_wt.append(1.0)
    if graph_csr_validate_flat(bad_ptr, two_tgt, two_wt, 2) == GRAPH_ERR_ROWPTR_NOT_MONOTONIC:
        passed += 1
        print("  \u2705 a non-monotonic row_ptr still reports the GRAPH-shaped code")
    else:
        failed += 1
        print("  \u274c delegation lost the graph error vocabulary")

    print("  [graph_analytics.adjacency] Passed:", passed, "Failed:", failed)
