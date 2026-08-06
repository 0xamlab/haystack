"""test_graph_analytics_community.mojo — known-value tests for Louvain community detection.

Hand-written. Every modularity asserted here was computed on paper first and is quoted in
the comment above its assertion, because a community detector that returns a plausible
partition with a wrong score is the failure mode that no smoke test catches.

The assertions target the silent failures specifically:

* a connected graph with two obvious communities. `graph.algorithms.connected_components`
  is the frozen oracle for the *other* question and returns one component for it, so the
  test shows components and communities disagreeing rather than asserting that they
  differ in principle.
* a complete graph, where there is no community structure and `Q <= 0` for every
  partition. Reporting groups there is the classic way a detector invents structure, so
  the test asserts one community, `Q == 0.0` exactly, and that a two-way split really
  does score negative.
* the collapsed O(V + E) modularity against the literal per-pair sum over the frozen
  `graph_algorithms.modularity_contribution`. The collapse is exact algebra, so a
  disagreement is a bug in the collapse and nothing else would find it.
* the same seed twice, and two different seeds. `community_visit_order` proves the two
  seeds genuinely produce different node orders, so "identical labels" is evidence of
  reproducibility rather than of a seed that is ignored.
* modularity across aggregation levels, including that aggregation preserves `Q` and `m`
  exactly — the identity the whole ladder's monotonicity rests on.
* label propagation losing to Louvain on the same graph, which is what "cheaper
  alternative" actually costs. The frozen
  `social_network.community_label_propagation` is the oracle for the unambiguous case.
* a negative weight, a NaN-free infinity, a weightless graph, a broken `row_ptr` and the
  generated-suite five-element pattern, all of which must come back as a status with an
  empty partition rather than a number.
"""
from std.math import abs as fabs, isnan

from clustering_metrics import adjusted_rand_index
from graph.algorithms import connected_components, graph_add_edge, graph_new
from graph_algorithms import modularity_contribution
from graph_analytics.adjacency import (
    GRAPH_ERR_NEGATIVE_WEIGHT,
    GRAPH_ERR_NON_FINITE_WEIGHT,
    GRAPH_ERR_ROWPTR_LENGTH,
    GRAPH_OK,
    graph_csr_build,
)
from graph_analytics.community import (
    COMMUNITY_DEFAULT_TOLERANCE,
    COMMUNITY_ERR_INVALID_LIMITS,
    COMMUNITY_ERR_LABEL_LENGTH,
    COMMUNITY_ERR_LABEL_RANGE,
    COMMUNITY_ERR_NO_EDGE_WEIGHT,
    COMMUNITY_ERR_PAIRWISE_TOO_LARGE,
    COMMUNITY_ERR_TOO_MANY_NODES,
    COMMUNITY_LEVEL_LIMIT,
    COMMUNITY_NO_MODULARITY,
    CommunityAggregate,
    CommunityCompare,
    CommunityCounts,
    CommunityLevels,
    CommunityOrder,
    CommunityPartition,
    CommunityScore,
    community_aggregate_driver,
    community_canonical_labels,
    community_compare_labels,
    community_default_tolerance,
    community_label_propagation_driver,
    community_local_moving_driver,
    community_louvain_default_driver,
    community_louvain_driver,
    community_louvain_from_triplets,
    community_louvain_levels_driver,
    community_modularity_driver,
    community_modularity_from_triplets,
    community_modularity_gain,
    community_modularity_pairwise_driver,
    community_status_name,
    community_symmetrized_driver,
    community_version,
    community_visit_order,
)
from social_network import community_label_propagation


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    if isnan(a) or isnan(b):
        return False
    return fabs(a - b) <= tol


def _labels_equal(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


struct _Undirected(Copyable, Movable):
    """An undirected edge list, expanded on demand into either CSR encoding.

    Both encodings matter: storing one direction per edge and storing both are the two
    ways a caller will hand over the same undirected graph, and the kernel must score
    them identically.
    """

    var n: Int
    var a: List[Int]
    var b: List[Int]

    def __init__(out self, n: Int):
        self.n = n
        self.a = List[Int]()
        self.b = List[Int]()

    def add(mut self, u: Int, v: Int):
        self.a.append(u)
        self.b.append(v)

    def unit_weights(self) -> List[Float64]:
        var w = List[Float64]()
        for _ in range(len(self.a)):
            w.append(1.0)
        return w^

    def both_row_ptr(self) -> List[Int]:
        var counts = List[Int]()
        for _ in range(self.n):
            counts.append(0)
        for i in range(len(self.a)):
            counts[self.a[i]] += 1
            counts[self.b[i]] += 1
        var row_ptr = List[Int]()
        var running = 0
        for u in range(self.n):
            row_ptr.append(running)
            running += counts[u]
        row_ptr.append(running)
        return row_ptr^

    def both_targets(self) -> List[Int]:
        var adj = List[List[Int]]()
        for _ in range(self.n):
            adj.append(List[Int]())
        for i in range(len(self.a)):
            adj[self.a[i]].append(self.b[i])
            adj[self.b[i]].append(self.a[i])
        var out = List[Int]()
        for u in range(self.n):
            for j in range(len(adj[u])):
                out.append(adj[u][j])
        return out^

    def both_weights(self) -> List[Float64]:
        var out = List[Float64]()
        for _ in range(2 * len(self.a)):
            out.append(1.0)
        return out^

    def adjacency_lists(self) -> List[List[Int]]:
        var adj = List[List[Int]]()
        for _ in range(self.n):
            adj.append(List[Int]())
        for i in range(len(self.a)):
            adj[self.a[i]].append(self.b[i])
            adj[self.b[i]].append(self.a[i])
        return adj^

    def component_count(self) -> Int:
        """Number of connected components, from the frozen `graph.algorithms` kernel."""
        var g = graph_new(self.n)
        for i in range(len(self.a)):
            graph_add_edge(g, self.a[i], self.b[i], 1.0)
            graph_add_edge(g, self.b[i], self.a[i], 1.0)
        var labels = connected_components(g)
        var highest = -1
        for i in range(len(labels)):
            if labels[i] > highest:
                highest = labels[i]
        return highest + 1


def _two_triangles_bridged() -> _Undirected:
    """Triangles {0,1,2} and {3,4,5} joined by the single edge 2-3. One component."""
    var g = _Undirected(6)
    g.add(0, 1)
    g.add(0, 2)
    g.add(1, 2)
    g.add(3, 4)
    g.add(3, 5)
    g.add(4, 5)
    g.add(2, 3)
    return g^


def _complete_graph(n: Int) -> _Undirected:
    var g = _Undirected(n)
    for i in range(n):
        for j in range(i + 1, n):
            g.add(i, j)
    return g^


def _triangle_ring(triangles: Int) -> _Undirected:
    """`triangles` triangles in a cycle, each joined to the next by one edge.

    The textbook resolution-limit graph: single triangles are optimal for a short ring
    and *pairs* of triangles are optimal for a long one, so Louvain needs a second
    aggregation level to reach the optimum. That is what makes it the right test for the
    aggregation phase rather than for the local-moving phase.
    """
    var n = 3 * triangles
    var g = _Undirected(n)
    for t in range(triangles):
        var base = 3 * t
        g.add(base, base + 1)
        g.add(base, base + 2)
        g.add(base + 1, base + 2)
        g.add(base + 2, (base + 3) % n)
    return g^


def main():
    var passed: Int = 0
    var failed: Int = 0

    print("  [graph_analytics.community]")

    # ── the demonstration: components are not communities ─────────────────────
    # Two triangles joined by one edge. Reachability sees ONE class; modularity sees two
    # groups. Both answers are right about their own question, which is why the frozen
    # connected_components kernel cannot be used as a community detector.
    var bridged = _two_triangles_bridged()
    var rp = bridged.both_row_ptr()
    var tg = bridged.both_targets()
    var wt = bridged.both_weights()

    var components = bridged.component_count()
    var found = community_louvain_default_driver(rp, tg, wt, 6, 7)
    if components == 1 and found.status == GRAPH_OK and found.n_communities == 2:
        passed += 1
        print("  ✅ one connected component, two communities — they are different questions")
    else:
        failed += 1
        print(
            "  ❌ components/communities:", components, found.n_communities,
            "status", found.status,
        )

    # Modularity of {0,1,2} | {3,4,5}, by hand. m = 7, 2m = 14. Degrees 2,2,3,3,2,2.
    # in_c = 2 * 3 edges = 6 and tot_c = 7 for each side, so
    # Q = 2 * (6/14 - (7/14)^2) = 2 * (3/7 - 1/4) = 10/28 = 5/14 = 0.35714285714...
    var q_expected = 5.0 / 14.0
    if _close(found.modularity, q_expected, 1e-15):
        passed += 1
        print("  ✅ Q = 5/14 for the two-triangle split, to the last bit:", found.modularity)
    else:
        failed += 1
        print("  ❌ Q wrong:", found.modularity, "expected", q_expected)

    var split_labels = List[Int]()
    split_labels.append(0)
    split_labels.append(0)
    split_labels.append(0)
    split_labels.append(1)
    split_labels.append(1)
    split_labels.append(1)
    if _labels_equal(found.label, split_labels) and found.size[0] == 3 and found.size[1] == 3:
        passed += 1
        print("  ✅ the partition is exactly {0,1,2} | {3,4,5}, canonically labelled")
    else:
        failed += 1
        print("  ❌ partition is not the two triangles")

    # ── the collapsed scorer against the literal per-pair frozen-kernel sum ───
    # community_modularity_driver collapses the null-model sum algebraically and visits
    # NO node pairs; the pairwise driver visits all 36 and calls
    # graph_algorithms.modularity_contribution on each. Equal answers, different routes.
    var collapsed = community_modularity_driver(rp, tg, wt, 6, split_labels)
    var pairwise = community_modularity_pairwise_driver(rp, tg, wt, 6, split_labels)
    if (
        collapsed.status == GRAPH_OK
        and pairwise.status == GRAPH_OK
        and collapsed.pairs_scanned == 0
        and pairwise.pairs_scanned == 36
        and _close(collapsed.modularity, q_expected, 1e-15)
        and _close(pairwise.modularity, q_expected, 1e-15)
    ):
        passed += 1
        print("  ✅ collapsed (0 pairs) and per-pair (36 pairs) modularity agree on 5/14")
    else:
        failed += 1
        print(
            "  ❌ scorers disagree:", collapsed.modularity, pairwise.modularity,
            collapsed.pairs_scanned, pairwise.pairs_scanned,
        )

    # The per-community terms must reconstruct Q, so a caller can audit the score.
    # in_c = 12 and tot_c = 14 here because both directions are stored, which doubles
    # every weight; Q is invariant to that and the next assertion proves it.
    if (
        _close(collapsed.internal_weight[0], 12.0, 1e-12)
        and _close(collapsed.internal_weight[1], 12.0, 1e-12)
        and _close(collapsed.total_degree[0], 14.0, 1e-12)
        and _close(collapsed.total_degree[1], 14.0, 1e-12)
        and _close(collapsed.total_weight, 14.0, 1e-12)
    ):
        passed += 1
        print("  ✅ per-community in_c and tot_c are the symmetrised values, not the raw ones")
    else:
        failed += 1
        print(
            "  ❌ terms wrong:", collapsed.internal_weight[0],
            collapsed.total_degree[0], collapsed.total_weight,
        )

    # ── one direction stored or both, the score is identical ──────────────────
    # W_ij = D_ij + D_ji, so storing both directions doubles every weight. Q is
    # invariant under a uniform rescale, so the two encodings of one undirected graph
    # must return the same number — a caller will assume this without checking it.
    var one_way = graph_csr_build(bridged.a, bridged.b, bridged.unit_weights(), 6)
    var one_way_score = community_modularity_driver(
        one_way.row_ptr, one_way.targets, one_way.weights, 6, split_labels
    )
    if (
        one_way_score.status == GRAPH_OK
        and _close(one_way_score.modularity, collapsed.modularity, 0.0)
        and _close(one_way_score.total_weight, 7.0, 1e-12)
    ):
        passed += 1
        print("  ✅ one-directional and both-directional encodings score bit-identically")
    else:
        failed += 1
        print(
            "  ❌ encoding changed the score:", one_way_score.modularity,
            "vs", collapsed.modularity, "m =", one_way_score.total_weight,
        )

    var one_way_louvain = community_louvain_from_triplets(
        bridged.a, bridged.b, bridged.unit_weights(), 6, 7, 64, 1024, COMMUNITY_DEFAULT_TOLERANCE
    )
    if one_way_louvain.n_communities == 2 and _labels_equal(one_way_louvain.label, split_labels):
        passed += 1
        print("  ✅ Louvain from a bare triplet list finds the same two communities")
    else:
        failed += 1
        print("  ❌ triplet entry point disagrees:", one_way_louvain.n_communities)

    # ── a complete graph has no community structure ───────────────────────────
    # K5: m = 10, 2m = 20, every k_i = 4. One community scores 20/20 - 1 = 0 exactly.
    # Splitting {0,1} | {2,3,4} scores 2/20 - (8/20)^2 + 6/20 - (12/20)^2 = -0.12, and
    # all singletons score -5 * (4/20)^2 = -0.2. So 0 is the maximum and the only
    # honest answer is a single community.
    var k5 = _complete_graph(5)
    var k5_rp = k5.both_row_ptr()
    var k5_tg = k5.both_targets()
    var k5_wt = k5.both_weights()
    var k5_found = community_louvain_default_driver(k5_rp, k5_tg, k5_wt, 5, 11)
    if (
        k5_found.status == GRAPH_OK
        and k5_found.n_communities == 1
        and _close(k5_found.modularity, 0.0, 1e-15)
    ):
        passed += 1
        print("  ✅ K5: one community and Q = 0 — no structure invented")
    else:
        failed += 1
        print(
            "  ❌ K5 invented", k5_found.n_communities, "communities at Q =",
            k5_found.modularity,
        )

    var k5_split = List[Int]()
    k5_split.append(0)
    k5_split.append(0)
    k5_split.append(1)
    k5_split.append(1)
    k5_split.append(1)
    var k5_two = community_modularity_driver(k5_rp, k5_tg, k5_wt, 5, k5_split)
    var k5_two_pairs = community_modularity_pairwise_driver(k5_rp, k5_tg, k5_wt, 5, k5_split)
    var k5_singletons = List[Int]()
    for i in range(5):
        k5_singletons.append(i)
    var k5_single = community_modularity_driver(k5_rp, k5_tg, k5_wt, 5, k5_singletons)
    if (
        _close(k5_two.modularity, -0.12, 1e-14)
        and _close(k5_two_pairs.modularity, -0.12, 1e-14)
        and _close(k5_single.modularity, -0.2, 1e-14)
    ):
        passed += 1
        print("  ✅ K5: a two-way split scores -0.12 and singletons -0.2, both below 0")
    else:
        failed += 1
        print(
            "  ❌ K5 alternative partitions:", k5_two.modularity,
            k5_two_pairs.modularity, k5_single.modularity,
        )

    # ── the same seed twice, and a seed that genuinely matters ────────────────
    # The visit orders come first: if two seeds produced the same order, "identical
    # labels" would prove nothing at all.
    var order_a = community_visit_order(6, 1, 0, 0)
    var order_b = community_visit_order(6, 2, 0, 0)
    if (
        order_a.status == GRAPH_OK
        and order_b.status == GRAPH_OK
        and len(order_a.values) == 6
        and len(order_b.values) == 6
        and not _labels_equal(order_a.values, order_b.values)
    ):
        passed += 1
        print("  ✅ seed 1 and seed 2 give different visit orders — the seed is load-bearing")
    else:
        failed += 1
        print("  ❌ visit orders did not differ between seeds")

    var order_repeat = community_visit_order(6, 1, 0, 0)
    if _labels_equal(order_a.values, order_repeat.values):
        passed += 1
        print("  ✅ the same (seed, level, pass) reproduces the same order exactly")
    else:
        failed += 1
        print("  ❌ the visit order is not reproducible")

    var run_one = community_louvain_driver(rp, tg, wt, 6, 4242, 64, 1024, 1e-12)
    var run_two = community_louvain_driver(rp, tg, wt, 6, 4242, 64, 1024, 1e-12)
    if (
        _labels_equal(run_one.label, run_two.label)
        and _close(run_one.modularity, run_two.modularity, 0.0)
        and run_one.n_levels == run_two.n_levels
        and run_one.moves == run_two.moves
    ):
        passed += 1
        print("  ✅ the same seed twice gives identical labels, score, levels and move count")
    else:
        failed += 1
        print("  ❌ two runs on one seed disagreed")

    var seeded_compare = community_compare_labels(run_one.label, split_labels)
    if seeded_compare.same_partition and _close(seeded_compare.adjusted_rand_index, 1.0, 1e-12):
        passed += 1
        print("  ✅ partition equality is exact, and the frozen ARI agrees at 1.0")
    else:
        failed += 1
        print(
            "  ❌ compare said", seeded_compare.same_partition,
            seeded_compare.adjusted_rand_index,
        )

    # ── modularity across aggregation levels ─────────────────────────────────
    # A ring of 12 triangles. m = 48, 2m = 96, with 24 nodes of degree 3 and 12 of
    # degree 2. All singletons score -(24*9 + 12*4)/96^2 = -264/9216 = -0.0286458333...
    # Twelve single-triangle communities score 6/8 - 1/12 = 2/3 exactly, and six
    # adjacent-pair communities score 14/16 - 2/12 = 17/24 — so the optimum is only
    # reachable through a SECOND aggregation level, which is what this graph tests.
    var ring = _triangle_ring(12)
    var ring_rp = ring.both_row_ptr()
    var ring_tg = ring.both_targets()
    var ring_wt = ring.both_weights()
    var singleton_q = -264.0 / 9216.0
    var level_one_q = 2.0 / 3.0
    var optimum_q = 17.0 / 24.0

    var ladder_ok = True
    var ladder_note = String("")
    for seed in range(1, 5):
        var ladder = community_louvain_levels_driver(
            ring_rp, ring_tg, ring_wt, 36, seed, 64, 1024, 1e-12
        )
        if ladder.status != GRAPH_OK or ladder.n_levels != 2:
            ladder_ok = False
            ladder_note = String("levels")
            continue
        if len(ladder.level_modularity) != 3:
            ladder_ok = False
            ladder_note = String("length")
            continue
        # Monotonicity checked here rather than read off `ladder.monotone`: a suite that
        # asserts a self-reported flag tests the flag, not the algorithm.
        for i in range(1, 3):
            if ladder.level_modularity[i] < ladder.level_modularity[i - 1]:
                ladder_ok = False
                ladder_note = String("not_monotone")
        if not ladder.monotone:
            ladder_ok = False
            ladder_note = String("flag_disagrees")
        if not _close(ladder.level_modularity[0], singleton_q, 1e-15):
            ladder_ok = False
            ladder_note = String("baseline")
        if not _close(ladder.level_modularity[1], level_one_q, 1e-15):
            ladder_ok = False
            ladder_note = String("level_one")
        if ladder.level_communities[1] != 12:
            ladder_ok = False
            ladder_note = String("level_one_k")
        if ladder.level_modularity[2] <= level_one_q or ladder.level_modularity[2] > optimum_q + 1e-15:
            ladder_ok = False
            ladder_note = String("level_two_range")
    if ladder_ok:
        passed += 1
        print(
            "  ✅ ring of 12 triangles: 2 levels, Q rises",
            singleton_q, "->", level_one_q, "-> at most", optimum_q,
            "for every seed 1-4",
        )
    else:
        failed += 1
        print("  ❌ ladder broke:", ladder_note)

    # Seed 2 reaches the hand-computed optimum exactly. This pins the seeded order: it
    # fails if the draw addressing, the named stream or the tie-break rule ever moves,
    # which is the coupling `community_version` exists to declare.
    var ring_best = community_louvain_levels_driver(
        ring_rp, ring_tg, ring_wt, 36, 2, 64, 1024, 1e-12
    )
    if ring_best.n_communities == 6 and _close(ring_best.modularity, optimum_q, 1e-15):
        passed += 1
        print("  ✅ seed 2 reaches the optimum: 6 paired-triangle communities at 17/24")
    else:
        failed += 1
        print(
            "  ❌ seed 2 gave", ring_best.n_communities, "communities at",
            ring_best.modularity,
        )

    # Local moving alone stops at the twelve triangles — it has no aggregation phase, so
    # it cannot see the pairing. That is the difference between the two drivers, and it
    # is why `community_local_moving_driver` is exposed separately.
    var ring_local = community_local_moving_driver(
        ring_rp, ring_tg, ring_wt, 36, 2, 1024, 1e-12
    )
    if (
        ring_local.n_communities == 12
        and ring_local.n_levels == 0
        and _close(ring_local.modularity, level_one_q, 1e-15)
        and ring_local.converged
        and ring_local.moves > 0
    ):
        passed += 1
        print("  ✅ local moving alone stops at 12 triangles (Q = 2/3), n_levels = 0")
    else:
        failed += 1
        print(
            "  ❌ local moving gave", ring_local.n_communities, "at",
            ring_local.modularity,
        )

    if ring.component_count() == 1 and ring_best.n_communities == 6:
        passed += 1
        print("  ✅ the ring is one component and six communities — the same distinction, 36 nodes wide")
    else:
        failed += 1
        print("  ❌ ring component count:", ring.component_count())

    # ── aggregation preserves Q and m exactly ────────────────────────────────
    # This identity is what makes the level sequence a single monotone objective. If
    # aggregation summed anything else, each level would score a different graph and the
    # monotonicity above would be meaningless rather than wrong.
    var aggregate = community_aggregate_driver(rp, tg, wt, 6, split_labels)
    var aggregate_singletons = List[Int]()
    for i in range(aggregate.n_nodes):
        aggregate_singletons.append(i)
    var aggregate_score = community_modularity_driver(
        aggregate.row_ptr,
        aggregate.targets,
        aggregate.weights,
        aggregate.n_nodes,
        aggregate_singletons,
    )
    if (
        aggregate.status == GRAPH_OK
        and aggregate.n_nodes == 2
        and _close(aggregate.total_weight, collapsed.total_weight, 0.0)
        and _close(aggregate_score.modularity, collapsed.modularity, 0.0)
    ):
        passed += 1
        print("  ✅ aggregation to 2 super-nodes preserves both m and Q bit-exactly")
    else:
        failed += 1
        print(
            "  ❌ aggregation changed the objective:", aggregate.total_weight,
            aggregate_score.modularity,
        )

    # The aggregated diagonal is a real self-loop edge carrying in_c, which is what lets
    # the arrays go straight back in as a CSR. Without it the next level would lose every
    # internal edge and Q would collapse toward 0.
    var diagonal_found = 0
    for u in range(aggregate.n_nodes):
        for p in range(aggregate.row_ptr[u], aggregate.row_ptr[u + 1]):
            if aggregate.targets[p] == u and _close(aggregate.weights[p], 12.0, 1e-12):
                diagonal_found += 1
    if diagonal_found == 2:
        passed += 1
        print("  ✅ each super-node carries its internal weight 12.0 on the diagonal")
    else:
        failed += 1
        print("  ❌ aggregated diagonal missing or wrong:", diagonal_found)

    # ── symmetrisation is inspectable ────────────────────────────────────────
    # 7 undirected edges stored both ways is 14 CSR entries, and every weight is
    # W = 1 + 1 = 2, so 2m = 28 and m = 14.
    var symmetrised = community_symmetrized_driver(rp, tg, wt, 6)
    var all_two = True
    for p in range(len(symmetrised.weights)):
        if not _close(symmetrised.weights[p], 2.0, 0.0):
            all_two = False
    if (
        symmetrised.status == GRAPH_OK
        and symmetrised.n_edges == 14
        and all_two
        and _close(symmetrised.total_weight, 14.0, 1e-12)
    ):
        passed += 1
        print("  ✅ W_ij = D_ij + D_ji = 2.0 for a doubly-stored unit graph, m = 14")
    else:
        failed += 1
        print("  ❌ symmetrisation:", symmetrised.n_edges, symmetrised.total_weight)

    # ── a self-loop counts twice in the degree, which changes m and Q ─────────
    # One-directional storage plus a self-loop of weight 1 on node 0: W_00 = 1 + 1 = 2,
    # so k_0 = 2 + 1 + 1 = 4 and 2m = 16, m = 8. For {0,1,2} | {3,4,5},
    # in_A = 2 + 2*3 = 8 with tot_A = 9, and in_B = 6 with tot_B = 7, giving
    # Q = (8/16 - (9/16)^2) + (6/16 - (7/16)^2) = 0.3671875. If the loop were counted
    # once the degree would be 3 and every term would shift, so this pins the convention.
    var looped_src = bridged.a.copy()
    var looped_dst = bridged.b.copy()
    looped_src.append(0)
    looped_dst.append(0)
    var looped_weight = List[Float64]()
    for _ in range(len(looped_src)):
        looped_weight.append(1.0)
    var looped = graph_csr_build(looped_src, looped_dst, looped_weight, 6)
    var looped_score = community_modularity_driver(
        looped.row_ptr, looped.targets, looped.weights, 6, split_labels
    )
    var looped_pairs = community_modularity_pairwise_driver(
        looped.row_ptr, looped.targets, looped.weights, 6, split_labels
    )
    var looped_louvain = community_louvain_driver(
        looped.row_ptr, looped.targets, looped.weights, 6, 7, 64, 1024, 1e-12
    )
    if (
        looped.self_loops == 1
        and _close(looped_score.total_weight, 8.0, 1e-12)
        and _close(looped_score.modularity, 0.3671875, 1e-15)
        and _close(looped_pairs.modularity, 0.3671875, 1e-14)
        and looped_louvain.n_communities == 2
    ):
        passed += 1
        print("  ✅ a self-loop doubles into the degree: m = 8, Q = 0.3671875, split unchanged")
    else:
        failed += 1
        print(
            "  ❌ self-loop convention:", looped_score.total_weight,
            looped_score.modularity, looped_pairs.modularity,
        )

    # ── the pairwise scorer refuses to spend O(V^2) silently ─────────────────
    # 2100 nodes is 4.41M ordered pairs, above the 4194304 ceiling. The graph is
    # otherwise perfectly valid and has edge weight, so only the declared cap catches it;
    # the collapsed scorer answers the same question on the same input in O(V + E).
    var big_n = 2100
    var big_row_ptr = List[Int]()
    big_row_ptr.append(0)
    big_row_ptr.append(1)
    big_row_ptr.append(2)
    for _ in range(big_n - 2):
        big_row_ptr.append(2)
    var big_targets = List[Int]()
    big_targets.append(1)
    big_targets.append(0)
    var big_weights = List[Float64]()
    big_weights.append(1.0)
    big_weights.append(1.0)
    var big_labels = List[Int]()
    for i in range(big_n):
        big_labels.append(0 if i < 2 else i)
    var big_pairs = community_modularity_pairwise_driver(
        big_row_ptr, big_targets, big_weights, big_n, big_labels
    )
    var big_collapsed = community_modularity_driver(
        big_row_ptr, big_targets, big_weights, big_n, big_labels
    )
    if (
        big_pairs.status == COMMUNITY_ERR_PAIRWISE_TOO_LARGE
        and _close(big_pairs.modularity, COMMUNITY_NO_MODULARITY, 0.0)
        and big_collapsed.status == GRAPH_OK
        and _close(big_collapsed.modularity, 0.0, 1e-15)
    ):
        passed += 1
        print("  ✅ 2100 nodes: the pairwise scan is refused, the collapsed one answers")
    else:
        failed += 1
        print(
            "  ❌ pairwise cap:", big_pairs.status, big_collapsed.status,
            big_collapsed.modularity,
        )

    # ── label propagation: cheaper, and demonstrably worse here ──────────────
    # On the bridged double triangle label propagation collapses everything into one
    # label (Q = 0) while Louvain holds the two triangles at 5/14. The frozen
    # social_network kernel does the same thing on the same graph, so this is label
    # propagation's behaviour and not a bug in this driver.
    var propagated = community_label_propagation_driver(rp, tg, wt, 6, 7, 50)
    if (
        propagated.status == GRAPH_OK
        and propagated.converged
        and propagated.n_communities == 1
        and _close(propagated.modularity, 0.0, 1e-15)
        and propagated.modularity < found.modularity
    ):
        passed += 1
        print("  ✅ label propagation converges to one community (Q = 0) where Louvain scores 5/14")
    else:
        failed += 1
        print(
            "  ❌ label propagation:", propagated.n_communities,
            propagated.modularity, propagated.converged,
        )

    # Remove the bridge and the answer is unambiguous, so the frozen kernel is a valid
    # oracle: two triangles, two labels, whatever the tie-breaks are.
    var disjoint = _Undirected(6)
    disjoint.add(0, 1)
    disjoint.add(1, 2)
    disjoint.add(0, 2)
    disjoint.add(3, 4)
    disjoint.add(4, 5)
    disjoint.add(3, 5)
    var d_rp = disjoint.both_row_ptr()
    var d_tg = disjoint.both_targets()
    var d_wt = disjoint.both_weights()
    var mine = community_label_propagation_driver(d_rp, d_tg, d_wt, 6, 5, 50)
    var frozen_labels = community_label_propagation(disjoint.adjacency_lists(), 50)
    var oracle_compare = community_compare_labels(mine.label, frozen_labels)
    if (
        mine.n_communities == 2
        and oracle_compare.status == GRAPH_OK
        and oracle_compare.same_partition
        and disjoint.component_count() == 2
    ):
        passed += 1
        print("  ✅ two disjoint triangles: this driver and the frozen kernel find the same partition")
    else:
        failed += 1
        print(
            "  ❌ disagreement with the frozen label-propagation kernel:",
            mine.n_communities, oracle_compare.same_partition,
        )

    # Q of two disjoint triangles: m = 6, 2m = 12, in_c = 6 and tot_c = 6 each, so
    # Q = 2 * (6/12 - (6/12)^2) = 0.5.
    var disjoint_louvain = community_louvain_default_driver(d_rp, d_tg, d_wt, 6, 5)
    if disjoint_louvain.n_communities == 2 and _close(disjoint_louvain.modularity, 0.5, 1e-15):
        passed += 1
        print("  ✅ two disjoint triangles score exactly Q = 0.5")
    else:
        failed += 1
        print("  ❌ disjoint triangles:", disjoint_louvain.modularity)

    # ── an isolated node is its own community, not community zero ────────────
    # Node 6 has no edges. It contributes nothing to Q, and folding it into a real
    # community would lower the score — so it must come back alone, which also keeps the
    # labelling a genuine partition of all 7 nodes.
    var with_isolate = _Undirected(7)
    with_isolate.add(0, 1)
    with_isolate.add(1, 2)
    with_isolate.add(0, 2)
    with_isolate.add(3, 4)
    with_isolate.add(4, 5)
    with_isolate.add(3, 5)
    var i_rp = with_isolate.both_row_ptr()
    var i_tg = with_isolate.both_targets()
    var i_wt = with_isolate.both_weights()
    var isolate_found = community_louvain_default_driver(i_rp, i_tg, i_wt, 7, 3)
    if (
        isolate_found.n_communities == 3
        and isolate_found.label[6] == 2
        and isolate_found.size[2] == 1
        and _close(isolate_found.modularity, 0.5, 1e-15)
    ):
        passed += 1
        print("  ✅ an isolated node is its own community and adds 0 to Q")
    else:
        failed += 1
        print(
            "  ❌ isolated node:", isolate_found.n_communities,
            isolate_found.modularity,
        )

    # ── the gain formula is the frozen kernel, divided by m ──────────────────
    var gain = community_modularity_gain(2.0, 4.0, 8.0, 14.0)
    var gain_oracle = modularity_contribution(2.0, 4.0, 8.0, 14.0) / 14.0
    if _close(gain, gain_oracle, 0.0):
        passed += 1
        print("  ✅ the exposed move gain is modularity_contribution / m, bit for bit")
    else:
        failed += 1
        print("  ❌ gain drifted from the frozen kernel:", gain, gain_oracle)

    # m = 0 has no gain to report. 0.0 would be the real gain of a move that changes
    # nothing, so the absent answer must not borrow it.
    if _close(community_modularity_gain(1.0, 1.0, 1.0, 0.0), COMMUNITY_NO_MODULARITY, 0.0):
        passed += 1
        print("  ✅ a gain with no total weight is absent, not 0.0")
    else:
        failed += 1
        print("  ❌ zero-weight gain returned a number")

    # ── refusals, each with an empty partition rather than a plausible one ────
    var negative = d_wt.copy()
    negative[0] = -1.0
    var negative_result = community_louvain_default_driver(d_rp, d_tg, negative, 6, 1)
    if (
        negative_result.status == GRAPH_ERR_NEGATIVE_WEIGHT
        and len(negative_result.label) == 0
        and _close(negative_result.modularity, COMMUNITY_NO_MODULARITY, 0.0)
        and community_status_name(negative_result.status) == "negative_weight_use_bellman_ford"
    ):
        passed += 1
        print("  ✅ a negative weight is refused with no partition attached")
    else:
        failed += 1
        print("  ❌ negative weight:", negative_result.status, len(negative_result.label))

    # 1e18 cubed is still finite; only 1e308 squared overflows to infinity.
    var infinite = d_wt.copy()
    infinite[0] = 1e308 * 1e308
    var infinite_result = community_louvain_default_driver(d_rp, d_tg, infinite, 6, 1)
    if (
        infinite_result.status == GRAPH_ERR_NON_FINITE_WEIGHT
        and len(infinite_result.label) == 0
    ):
        passed += 1
        print("  ✅ an infinite weight is refused before it reaches 2m")
    else:
        failed += 1
        print("  ❌ infinite weight:", infinite_result.status)

    # NaN is checked before the sign test, because `nan < 0.0` is False and a NaN weight
    # would otherwise make 2m NaN and every gain comparison False — the greedy loop would
    # burn its whole pass budget and report singletons as the answer.
    var nan_weights = d_wt.copy()
    var infinity = 1e308 * 1e308
    nan_weights[0] = infinity - infinity
    var nan_result = community_louvain_default_driver(d_rp, d_tg, nan_weights, 6, 1)
    if nan_result.status == GRAPH_ERR_NON_FINITE_WEIGHT and len(nan_result.label) == 0:
        passed += 1
        print("  ✅ a NaN weight is caught by the NaN test, not missed by the sign test")
    else:
        failed += 1
        print("  ❌ NaN weight:", nan_result.status)

    # Three nodes, no edges: 2m = 0, so Q is 0/0 and every partition is equally good.
    # Reporting 0.0 there would be indistinguishable from K5's real answer of 0.0.
    var empty_row_ptr = List[Int]()
    for _ in range(4):
        empty_row_ptr.append(0)
    var weightless = community_louvain_default_driver(
        empty_row_ptr, List[Int](), List[Float64](), 3, 1
    )
    if (
        weightless.status == COMMUNITY_ERR_NO_EDGE_WEIGHT
        and _close(weightless.modularity, COMMUNITY_NO_MODULARITY, 0.0)
        and community_status_name(weightless.status) == "no_edge_weight_modularity_undefined"
    ):
        passed += 1
        print("  ✅ an edgeless graph has NO modularity, distinct from K5's real 0.0")
    else:
        failed += 1
        print("  ❌ edgeless graph:", weightless.status, weightless.modularity)

    # All weights exactly zero is the same 0/0, reached the other way.
    var zero_weights = List[Float64]()
    for _ in range(len(d_wt)):
        zero_weights.append(0.0)
    if (
        community_louvain_default_driver(d_rp, d_tg, zero_weights, 6, 1).status
        == COMMUNITY_ERR_NO_EDGE_WEIGHT
    ):
        passed += 1
        print("  ✅ all-zero weights are the same undefined case, not a zero score")
    else:
        failed += 1
        print("  ❌ all-zero weights were scored")

    # ── the generated suite's five-element pattern must not crash the worker ──
    # Every contract function is called with a 5-element list for each List parameter and
    # 5 for each Int. row_ptr = [1,2,3,4,5] has the wrong length for 5 nodes AND does not
    # start at zero, so an unguarded driver would index targets[5] on a 5-element list —
    # an uncatchable process crash that takes every resident dataset with it.
    var li5 = List[Int]()
    for i in range(5):
        li5.append(i + 1)
    var lf5 = List[Float64]()
    lf5.append(0.5)
    lf5.append(0.6)
    lf5.append(0.7)
    lf5.append(0.4)
    lf5.append(0.3)
    var az_ok = True
    if community_louvain_driver(li5, li5, lf5, 5, 5, 5, 5, 0.5).status != GRAPH_ERR_ROWPTR_LENGTH:
        az_ok = False
    if community_louvain_default_driver(li5, li5, lf5, 5, 5).status != GRAPH_ERR_ROWPTR_LENGTH:
        az_ok = False
    if community_louvain_levels_driver(li5, li5, lf5, 5, 5, 5, 5, 0.5).status != GRAPH_ERR_ROWPTR_LENGTH:
        az_ok = False
    if community_local_moving_driver(li5, li5, lf5, 5, 5, 5, 0.5).status != GRAPH_ERR_ROWPTR_LENGTH:
        az_ok = False
    if community_modularity_driver(li5, li5, lf5, 5, li5).status != GRAPH_ERR_ROWPTR_LENGTH:
        az_ok = False
    if community_modularity_pairwise_driver(li5, li5, lf5, 5, li5).status != GRAPH_ERR_ROWPTR_LENGTH:
        az_ok = False
    if community_label_propagation_driver(li5, li5, lf5, 5, 5, 5).status != GRAPH_ERR_ROWPTR_LENGTH:
        az_ok = False
    if community_aggregate_driver(li5, li5, lf5, 5, li5).status != GRAPH_ERR_ROWPTR_LENGTH:
        az_ok = False
    if community_symmetrized_driver(li5, li5, lf5, 5).status != GRAPH_ERR_ROWPTR_LENGTH:
        az_ok = False
    if az_ok:
        passed += 1
        print("  ✅ all nine array drivers reject the 5-element/5 pattern instead of indexing it")
    else:
        failed += 1
        print("  ❌ a driver did not reject the generated-suite sample arguments")

    # The triplet entry points take the same pattern with src/dst = [1,2,3,4,5] and 5
    # nodes, where node 5 is out of range — those edges are skipped, not indexed.
    var triplet_score = community_modularity_from_triplets(li5, li5, lf5, 5, li5)
    var triplet_louvain = community_louvain_from_triplets(li5, li5, lf5, 5, 5, 5, 5, 0.5)
    if (
        triplet_score.status == COMMUNITY_ERR_LABEL_RANGE
        and triplet_louvain.status == GRAPH_OK
        and triplet_louvain.n_nodes == 5
    ):
        passed += 1
        print("  ✅ the triplet drivers skip the out-of-range endpoint and stay on their feet")
    else:
        failed += 1
        print(
            "  ❌ triplet drivers:", triplet_score.status, triplet_louvain.status,
        )

    # ── labelling guards ────────────────────────────────────────────────────
    var short_label = List[Int]()
    short_label.append(0)
    short_label.append(0)
    if community_modularity_driver(rp, tg, wt, 6, short_label).status == COMMUNITY_ERR_LABEL_LENGTH:
        passed += 1
        print("  ✅ a 2-entry labelling for a 6-node graph is a length error, not a partial score")
    else:
        failed += 1
        print("  ❌ short label accepted")

    var wide_label = List[Int]()
    for i in range(6):
        wide_label.append(6 + i)
    if community_modularity_driver(rp, tg, wt, 6, wide_label).status == COMMUNITY_ERR_LABEL_RANGE:
        passed += 1
        print("  ✅ labels outside [0, n_nodes) are refused before any subscript")
    else:
        failed += 1
        print("  ❌ out-of-range labels were indexed")

    if (
        community_louvain_levels_driver(rp, tg, wt, 6, 1, 0, 10, 1e-12).status
        == COMMUNITY_ERR_INVALID_LIMITS
        and community_local_moving_driver(rp, tg, wt, 6, 1, 0, 1e-12).status
        == COMMUNITY_ERR_INVALID_LIMITS
        and community_label_propagation_driver(rp, tg, wt, 6, 1, 0).status
        == COMMUNITY_ERR_INVALID_LIMITS
    ):
        passed += 1
        print("  ✅ a zero iteration limit asks for no work and is refused, not silently clamped up")
    else:
        failed += 1
        print("  ❌ a zero limit was accepted")

    # A negative tolerance would admit Q-lowering moves and break the one guarantee the
    # ladder rests on, so it is clamped to 0 rather than honoured.
    var negative_tolerance = community_louvain_driver(rp, tg, wt, 6, 7, 64, 1024, -5.0)
    if (
        negative_tolerance.status == GRAPH_OK
        and negative_tolerance.n_communities == 2
        and _close(negative_tolerance.modularity, q_expected, 1e-15)
    ):
        passed += 1
        print("  ✅ a negative tolerance is clamped to 0 and Q still lands on 5/14")
    else:
        failed += 1
        print("  ❌ negative tolerance:", negative_tolerance.modularity)

    # ── canonical labelling and comparison ──────────────────────────────────
    # Two labellings of the same partition with different ids must compare equal, and
    # the canonical form is what makes that an integer comparison instead of a float one.
    var relabelled = List[Int]()
    relabelled.append(4)
    relabelled.append(4)
    relabelled.append(4)
    relabelled.append(1)
    relabelled.append(1)
    relabelled.append(1)
    var canonical = community_canonical_labels(relabelled)
    var same = community_compare_labels(relabelled, split_labels)
    if (
        canonical.status == GRAPH_OK
        and canonical.n_communities == 2
        and _labels_equal(canonical.label, split_labels)
        and canonical.size[0] == 3
        and same.same_partition
        and same.canonical_mismatches == 0
    ):
        passed += 1
        print("  ✅ {4,4,4,1,1,1} canonicalises to {0,0,0,1,1,1} and compares equal")
    else:
        failed += 1
        print("  ❌ canonicalisation:", canonical.n_communities, same.same_partition)

    # Out of range and wrong length are different defects, and a caller holding a False
    # `same_partition` needs to know which one it has rather than concluding the two
    # partitions differ.
    var out_of_range = community_compare_labels(split_labels, wide_label)
    var different_len = community_compare_labels(split_labels, short_label)
    if (
        out_of_range.status == COMMUNITY_ERR_LABEL_RANGE
        and not out_of_range.same_partition
        and different_len.status == COMMUNITY_ERR_LABEL_LENGTH
        and not different_len.same_partition
    ):
        passed += 1
        print("  ✅ comparing mismatched labellings is a status, never a silent False")
    else:
        failed += 1
        print("  ❌ compare guards:", out_of_range.status, different_len.status)

    var all_singletons = List[Int]()
    for i in range(6):
        all_singletons.append(i)
    var against_singletons = community_compare_labels(split_labels, all_singletons)
    var ari_oracle = adjusted_rand_index(split_labels, all_singletons)
    if (
        not against_singletons.same_partition
        and against_singletons.n_communities_a == 2
        and against_singletons.n_communities_b == 6
        and _close(against_singletons.adjusted_rand_index, ari_oracle, 0.0)
    ):
        passed += 1
        print("  ✅ two genuinely different partitions: not equal, and the frozen ARI matches")
    else:
        failed += 1
        print("  ❌ different partitions compared as equal")

    # ── visit-order guards and the zero-argument probes ──────────────────────
    if (
        community_visit_order(-1, 1, 0, 0).status != GRAPH_OK
        and community_visit_order(6, 1, COMMUNITY_LEVEL_LIMIT, 0).status
        == COMMUNITY_ERR_INVALID_LIMITS
        and community_visit_order(1 << 21, 1, 0, 0).status == COMMUNITY_ERR_TOO_MANY_NODES
    ):
        passed += 1
        print("  ✅ visit_order refuses a negative count, an over-cap level and a 2^21-node request")
    else:
        failed += 1
        print("  ❌ visit_order guards did not hold")

    if (
        community_version() == "louvain/newman-girvan-Q/sym-sum/loop-doubled/philox4x64-10-order/v1"
        and _close(community_default_tolerance(), 1e-12, 0.0)
        and community_status_name(999) == "unknown_status"
        and community_status_name(COMMUNITY_ERR_PAIRWISE_TOO_LARGE) == "pairwise_scan_too_large"
    ):
        passed += 1
        print("  ✅ the convention identifier and the status names are pinned")
    else:
        failed += 1
        print("  ❌ version/status names drifted:", community_version())

    print("  [graph_analytics.community] Passed:", passed, "Failed:", failed)
