"""
graph_analytics.centrality — Brandes betweenness and friends over the CSR adjacency.

What the tree already has, and what it does not
-----------------------------------------------
There is no betweenness centrality in this repo. What exists is
`graph_algorithms.betweenness_centrality_norm(raw_betweenness, n_nodes, directed)`, which
divides a number the caller already has by `(n-1)(n-2)` — it is the *normalisation* of
betweenness, and it takes the quantity nobody computes as its first argument. The same
gap shows up downstream: `graph_decision.edge_criticality(edge_betweenness, flow,
capacity)` also expects a betweenness it cannot obtain. So the frozen surface can scale
and consume betweenness but never produce it, and this module is the producer. The frozen
normaliser is *called* here rather than re-derived, so there is one definition of the
denominator.

The other three measures do exist in frozen form, with limits that are the reason for a
new driver rather than a copy:

* `network_analysis.pagerank(adj: List[List[Int]], damping, max_iter, tol)` is a real
  power-iteration PageRank and **is called here**, not reimplemented. Two limits: its
  `List[List[Int]]` adjacency cannot cross a JSON frame (so it is unreachable from the
  SDKs), and it leaks probability mass — a node with no out-edges receives its teleport
  share but distributes nothing, so `sum(rank)` drifts below 1 by the dangling mass every
  iteration and the returned vector is not a distribution. It also returns no convergence
  information, so hitting `max_iter` without converging is indistinguishable from
  converging. `graph_pagerank` fixes the first by *augmenting the input graph* (every
  dangling node links to every node, which is exactly the standard uniform
  redistribution) so the frozen iteration becomes correct on it, and reports `mass`,
  `residual` and `converged` so the second cannot be hidden.
* `network_analysis.closeness_centrality(adj)` returns `0.0` for every node that cannot
  reach all `n-1` others. In any disconnected graph that is every node, and `0.0` is not
  a value closeness can otherwise take — so a graph with one isolated node reports zero
  closeness everywhere, which reads as an answer.
  `graph_algorithms.closeness_centrality(sum_shortest_paths, n_nodes)` is the scalar
  `(n-1)/Σd` and is called here; it also returns `0.0` when `Σd <= 0`.
* `network_analysis.degree_centrality(adj)` and
  `graph_algorithms.degree_centrality(degree, n_nodes)` (called here) are the `k/(n-1)`
  ratio over a `List[List[Int]]`; they count a parallel edge twice and a self-loop once,
  so a multigraph can score above 1.0.
* eigenvector centrality has no frozen implementation at all —
  `graph_algorithms.eigenvector_centrality_update(neighbor_scores_sum, lambda_max)` is
  one division. The dominant eigenvector itself comes from the frozen
  `linalg_ext.mat_power_iteration`, which is called here on the dense adjacency.

Brandes, not all-pairs
----------------------
Betweenness of `v` is the sum over ordered pairs `(s, t)` of the fraction of shortest
`s→t` paths through `v`. Materialising all pairs is O(V^3) time and O(V^2) memory; Brandes
is O(VE) unweighted and needs no distance matrix, because the dependency
`δ_s(v) = Σ_{w: v∈pred(w)} (σ_sv/σ_sw)(1 + δ_s(w))` telescopes one source at a time over
the shortest-path DAG. That needs two things a distance query does not return: the path
**counts** `σ`, and the DAG itself.

The DAG is recovered from the distances by exact float equality: `(u, v)` is a
shortest-path edge iff `dist[u] + w(u,v) == dist[v]`. That is not an approximation for the
edge that produced the distance — `graph_csr_dijkstra` assigns `dist[v] = key +
weights[k]` where `key` is bit-identical to the final `dist[u]` — so every reached node
except the source has at least one bit-exact DAG predecessor, and the DAG is never empty
where it should not be. It *is* a real limitation for a second route of mathematically
equal length whose sum differs by an ulp: that route is not counted, exactly as an
equality-based Dijkstra predecessor list would not count it. With integer or unit weights
the question does not arise, and `graph_betweenness_unweighted` is exact by construction
because levels are integers held in a Float64.

Traversal order is a topological order of that DAG, obtained with Kahn's algorithm and an
explicit queue — never recursion. Sorting the nodes by distance instead would be wrong in
one specific case: a zero-weight edge joins two nodes at *equal* distance, so a distance
order is not a topological order. Kahn also detects the case that has no answer at all: a
zero-weight cycle between distinct nodes means unboundedly many shortest paths, the
counts `σ` do not exist, and `CENTRALITY_ERR_ZERO_WEIGHT_CYCLE` says so instead of
returning one of them. A self-loop is excluded from the DAG outright — it cannot lie on a
shortest path between two distinct nodes — which is also why a zero-weight self-loop is
harmless here.

`σ` is accumulated in Float64 rather than Int on purpose: shortest-path counts grow
combinatorially (a 30×30 unit grid has C(60,30) ≈ 1.2e17 shortest corner-to-corner paths)
and an Int would overflow silently, while a Float64 loses exactness only above 2^53 —
which is *detected* and reported as `path_counts_exact = False`.

Directed or undirected is detected, not assumed
-----------------------------------------------
On an undirected graph the ordered-pair sum counts every pair twice, so the conventional
value is half of it. Rather than take a `directed` flag on faith, the graph is tested with
`graph_csr_symmetry(g, 0.0)`: structural symmetry for the unweighted variant, and *weight*
symmetry for the weighted one, because a symmetric edge set with asymmetric weights has
asymmetric shortest paths and halving would be wrong. The verdict is returned in
`undirected` so a caller can see which convention was applied to its numbers.

Closeness of an unreachable node: absent, not zero
--------------------------------------------------
If `v` cannot reach every other node, `Σd(v, ·)` over all others is infinite and
`(n-1)/Σd` is 0. Reporting 0 is the frozen convention and it is indefensible here: 0 is
unreachable for any node that has a neighbour, so it cannot be told from a genuinely
computed score, and it destroys the difference between "isolated" and "central within its
component". This module makes three distinct statements instead:

* `values[v]` is closeness **within the reachable set**: `r/Σd` where `r` is the number
  of others `v` actually reaches. That is 1/(mean distance to what it can reach) and it is
  a real number for any node with at least one reachable other.
* `scaled_values[v]` is the Wasserman–Faust form `(r/(n-1)) · (r/Σd)`, which reintroduces
  the penalty for reaching few nodes and is comparable across components.
* a node that reaches nobody has no mean distance, so `defined[v]` is False and
  `values[v]` is `CENTRALITY_UNDEFINED = -1.0`, impossible for a real closeness because
  distances are non-negative. `reached_count[v]` and `sum_distance[v]` are returned
  alongside so the caller can apply any other convention without a second traversal.

`graph_harmonic_centrality` is the measure that needs no convention: `Σ 1/d` over
reachable others, where an unreachable node contributes 0 because `1/∞` *is* 0. A sum over
nothing is 0 (an isolated node has harmonic centrality 0 — a real answer, per the
`numeric.contract` rule that a count or sum of nothing is 0 while a mean of nothing is
absent). Its one undefined case is the mirror of closeness's: a zero-weight path to a
distinct node gives `1/0`, so that node's value is absent and counted in
`zero_distance_nodes`.

Cost is refused, not silently paid
----------------------------------
Betweenness and closeness run one traversal per node: O(V(V+E)) unweighted, O(VE log E)
weighted. Inside a worker that is a hang, not a slow answer, so every driver here
estimates `V·(V+E)` first and returns `CENTRALITY_ERR_WORK_TOO_LARGE` above
`CENTRALITY_MAX_WORK`, in the same spirit as `GRAPH_MAX_DENSE_CELLS`.
"""
from std.math import abs as fabs, isinf, isnan

from graph_algorithms import (
    betweenness_centrality_norm,
    closeness_centrality as frozen_closeness_ratio,
    degree_centrality as frozen_degree_ratio,
)
from graph_analytics.adjacency import (
    GRAPH_ERR_EMPTY_GRAPH,
    GRAPH_ERR_INVALID_DIMENSIONS,
    GRAPH_ERR_LENGTH_MISMATCH,
    GRAPH_ERR_NEGATIVE_WEIGHT,
    GRAPH_ERR_NON_FINITE_WEIGHT,
    GRAPH_OK,
    GraphCSR,
    graph_csr_bfs_levels,
    graph_csr_dedupe_min,
    graph_csr_dijkstra,
    graph_csr_from_arrays,
    graph_csr_from_triplets,
    graph_csr_in_degrees,
    graph_csr_out_degrees,
    graph_csr_reverse,
    graph_csr_symmetry,
    graph_csr_to_dense,
    graph_csr_validate,
    graph_status_name,
)
from linalg import mat_from_list
from linalg_ext import mat_power_iteration
from network_analysis import pagerank as frozen_pagerank

# ── status codes ──────────────────────────────────────────────────────────────
# Numbered from 20 so an adjacency code and a centrality code can never collide: a
# caller holding a status from this module still reads `row_ptr_not_monotonic` for a
# broken graph, and `centrality_status_name` delegates for anything below 20.

comptime CENTRALITY_ERR_WORK_TOO_LARGE: Int = 20
comptime CENTRALITY_ERR_ZERO_WEIGHT_CYCLE: Int = 21
comptime CENTRALITY_ERR_DAMPING: Int = 22
comptime CENTRALITY_ERR_MAX_ITER: Int = 23
comptime CENTRALITY_ERR_TOLERANCE: Int = 24

# `-1.0` is impossible for every measure here: closeness, harmonic centrality, a
# non-negative eigenvector and a PageRank are all `>= 0`. So an ignored `defined` flag
# is a loud wrong answer, which `0.0` would not be.
comptime CENTRALITY_UNDEFINED: Float64 = -1.0

# One traversal per node is quadratic in the node count. Past this many
# `V * (V + E)` steps the caller wanted a sampled estimate, and a worker that stops
# answering is worse than a rejection.
comptime CENTRALITY_MAX_WORK: Int = 268435456

# A separate, larger ceiling for `max_iter * n^2` dense multiply-adds, because the two
# units are not comparable: a traversal step chases pointers while this is a contiguous
# multiply-add, and holding both to one number would refuse a second of power iteration
# while allowing ten seconds of Brandes. It also has to stay well clear of the iteration
# counts a caller reaches for after reading `converged = False` — a ceiling that punishes
# the documented remedy is worse than no ceiling.
comptime CENTRALITY_MAX_ITERATION_CELLS: Int = 4294967296

# Above 2^53 a Float64 cannot represent consecutive integers, so a shortest-path count
# beyond it has lost its last digits and `path_counts_exact` goes False.
comptime CENTRALITY_MAX_EXACT_COUNT: Float64 = 9007199254740992.0


def centrality_status_name(code: Int) -> String:
    """Name for a status code, this module's own or an adjacency one it passed through."""
    if code == CENTRALITY_ERR_WORK_TOO_LARGE:
        return "work_too_large_use_sampling"
    if code == CENTRALITY_ERR_ZERO_WEIGHT_CYCLE:
        return "zero_weight_cycle_path_counts_unbounded"
    if code == CENTRALITY_ERR_DAMPING:
        return "damping_out_of_range"
    if code == CENTRALITY_ERR_MAX_ITER:
        return "max_iter_not_positive"
    if code == CENTRALITY_ERR_TOLERANCE:
        return "tolerance_negative"
    return graph_status_name(code)


# ── return-only result structs ────────────────────────────────────────────────
# Declared in this file because the marshalling spec for a returned struct is parsed per
# file: returning `adjacency.GraphVectorResult` here would drop the function from the
# runtime contract with no error anywhere.


@fieldwise_init
struct BetweennessResult(Copyable, Movable):
    """Per-node betweenness plus everything needed to interpret the numbers.

    `undirected` says which pair convention was applied (an undirected graph's ordered
    sum is halved), `normalized` whether the frozen
    `graph_algorithms.betweenness_centrality_norm` denominator was applied, and
    `path_counts_exact` whether any shortest-path count exceeded 2^53 — beyond that the
    `σ` ratios are still close but no longer exact, and a caller comparing two nodes at
    the sixteenth digit needs to know.

    On any non-`GRAPH_OK` status `values` is empty and `max_node` is -1: a rejected
    request has no partial answer.
    """

    var status: Int
    var n_nodes: Int
    var n_sources: Int
    var weighted: Bool
    var normalized: Bool
    var undirected: Bool
    var path_counts_exact: Bool
    var max_node: Int
    var max_value: Float64
    var values: List[Float64]


@fieldwise_init
struct ClosenessResult(Copyable, Movable):
    """Closeness with reachability kept as data rather than folded into a zero.

    `values[v]` is `r/Σd` over the `r` others `v` reaches — 1/(mean distance within the
    reachable set) — and `CENTRALITY_UNDEFINED` where `defined[v]` is False, which happens
    exactly when `v` reaches nobody or reaches everything it reaches at distance 0.
    `scaled_values[v]` is the Wasserman–Faust form, comparable across components.
    `reached_count` and `sum_distance` are the raw ingredients, so any other convention
    (including the frozen "0 unless it reaches all") can be applied without traversing
    again.
    """

    var status: Int
    var n_nodes: Int
    var weighted: Bool
    var defined_count: Int
    var incomplete_count: Int
    var values: List[Float64]
    var scaled_values: List[Float64]
    var defined: List[Bool]
    var reached_count: List[Int]
    var sum_distance: List[Float64]


@fieldwise_init
struct HarmonicResult(Copyable, Movable):
    """Harmonic centrality `Σ 1/d`, which needs no unreachability convention.

    An unreachable other contributes 0 because `1/∞` is 0, so an isolated node scores a
    genuine 0. The one absent case is a distinct node at distance 0 (only reachable with
    zero-weight edges): `1/0` has no value, `defined[v]` is False and `values[v]` is
    `CENTRALITY_UNDEFINED`.
    """

    var status: Int
    var n_nodes: Int
    var weighted: Bool
    var normalized: Bool
    var zero_distance_nodes: Int
    var values: List[Float64]
    var defined: List[Bool]


@fieldwise_init
struct DegreeCentralityResult(Copyable, Movable):
    """Degree centrality on the min-weight canonical form, self-loops excluded.

    Distinct neighbours, not stored edges: the denominator `n-1` is a count of *other
    nodes*, so counting two parallel roads twice pushes the ratio above 1 and stops it
    being a centrality. `parallel_edges_collapsed` and `self_loops_ignored` report exactly
    what was removed to make that true, so a caller that wanted the multigraph count knows
    the difference rather than guessing.

    `total_values` is `(out + in)` scaled by `2(n-1)`, so an undirected graph gives the
    same number in all three vectors.
    """

    var status: Int
    var n_nodes: Int
    var normalized: Bool
    var parallel_edges_collapsed: Int
    var self_loops_ignored: Int
    var out_values: List[Float64]
    var in_values: List[Float64]
    var total_values: List[Float64]


@fieldwise_init
struct EigenvectorResult(Copyable, Movable):
    """Dominant eigenvector of the adjacency matrix, with the caveats it needs.

    `converged` is decided by a residual `max|Ax - λx|` measured after the fact, not by
    the iteration count: the frozen `linalg_ext.mat_power_iteration` always runs its full
    `max_iter` and reports nothing, so "did not converge" would otherwise be
    indistinguishable from "converged".

    `strongly_connected` is the Perron–Frobenius precondition. When it is False the
    dominant eigenspace may be degenerate (a graph of two components has one eigenvector
    per component) and the returned vector is *one* member of it, chosen by the uniform
    start vector — not wrong, but not unique either. `symmetric` says whether the
    eigenvalue is guaranteed real, which is what makes the measure meaningful.

    `shift` is the multiple of the identity that was added before iterating and subtracted
    from `eigenvalue` afterwards — see `graph_eigenvector_centrality` for why iterating
    the bare adjacency does not converge on half the graphs one would want to ask about.
    """

    var status: Int
    var n_nodes: Int
    var max_iter: Int
    var converged: Bool
    var symmetric: Bool
    var strongly_connected: Bool
    var eigenvalue: Float64
    var residual: Float64
    var shift: Float64
    var values: List[Float64]


@fieldwise_init
struct PageRankResult(Copyable, Movable):
    """PageRank from the frozen iteration, with the dangling-mass leak made visible.

    `mass` is `Σ rank`. A correct PageRank is a distribution, so `mass` is 1 up to
    rounding; with `dangling_redistributed = False` and a dangling node present it is
    visibly less, which is the frozen kernel's behaviour and the reason the augmented
    form exists. `residual` is `max|P(x) - x|` on the same graph the iteration used, so
    `converged` is a measured fact rather than the loop having finished.
    """

    var status: Int
    var n_nodes: Int
    var max_iter: Int
    var dangling_nodes: Int
    var dangling_redistributed: Bool
    var converged: Bool
    var damping: Float64
    var mass: Float64
    var residual: Float64
    var values: List[Float64]


# ── shared guards ─────────────────────────────────────────────────────────────


def _weight_status(weights: List[Float64]) -> Int:
    """`GRAPH_OK`, or the code for the first weight a distance measure cannot use.

    NaN is tested before the sign, because `nan < 0.0` is False: a bare negativity check
    would pass a NaN weight and then every comparison downstream would be False too.
    """
    for k in range(len(weights)):
        var w = weights[k]
        if isnan(w) or isinf(w):
            return GRAPH_ERR_NON_FINITE_WEIGHT
        if w < 0.0:
            return GRAPH_ERR_NEGATIVE_WEIGHT
    return GRAPH_OK


def _all_pairs_work_exceeds(n_nodes: Int, n_edges: Int) -> Bool:
    """True when one traversal per node would cost more than the declared ceiling.

    Compared in Float64 so the product itself cannot overflow into a small positive Int
    and wave the request through.
    """
    return (
        Float64(n_nodes) * (Float64(n_nodes) + Float64(n_edges))
        > Float64(CENTRALITY_MAX_WORK)
    )


def _argmax(values: List[Float64]) -> Int:
    """Index of the largest value, -1 for an empty list. Ties go to the lowest index."""
    if len(values) == 0:
        return -1
    var best = 0
    for i in range(1, len(values)):
        if values[i] > values[best]:
            best = i
    return best


def _zeros(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for _ in range(n):
        out.append(0.0)
    return out^


# ── Brandes: one source ───────────────────────────────────────────────────────


def _is_dag_edge(
    dist: List[Float64], u: Int, v: Int, cost: Float64
) -> Bool:
    """Is `(u, v)` on some shortest path from the source, given final distances.

    Exact equality, and exactness is what makes it right: the relaxation that set
    `dist[v]` computed `dist[u] + cost` in this same Float64 arithmetic, so the edge that
    produced the distance always matches bit-for-bit. A self-loop is never a DAG edge —
    it cannot lie on a path between two distinct nodes — which also keeps a zero-weight
    self-loop from looking like a zero-weight cycle.
    """
    if u == v:
        return False
    return dist[u] + cost == dist[v]


def _brandes_source(
    g: GraphCSR,
    source: Int,
    dist: List[Float64],
    reached: List[Bool],
    unit_cost: Bool,
    mut betweenness: List[Float64],
    mut max_sigma: Float64,
) -> Int:
    """Accumulate one source's dependencies into `betweenness`. O(V + E), no recursion.

    Three passes over the shortest-path DAG: Kahn for a topological order, forward for
    the path counts `σ`, backward for the dependencies `δ`. Predecessor lists are never
    materialised — iterating a node's out-edges and testing DAG membership gives the same
    information from the CSR that is already there, so the pass costs no allocation per
    node.
    """
    var n = g.n_nodes

    # Pass 1: in-degree inside the DAG, then Kahn. A distance order would do instead
    # everywhere except across a zero-weight edge, where both endpoints share a distance.
    var indegree = List[Int]()
    for _ in range(n):
        indegree.append(0)
    var reached_count = 0
    for u in range(n):
        if not reached[u]:
            continue
        reached_count += 1
        for k in range(g.row_ptr[u], g.row_ptr[u + 1]):
            var v = g.targets[k]
            if not reached[v]:
                continue
            var cost = 1.0 if unit_cost else g.weights[k]
            if _is_dag_edge(dist, u, v, cost):
                indegree[v] += 1

    var order = List[Int]()
    for u in range(n):
        if reached[u] and indegree[u] == 0:
            order.append(u)
    var head = 0
    while head < len(order):
        var u = order[head]
        head += 1
        for k in range(g.row_ptr[u], g.row_ptr[u + 1]):
            var v = g.targets[k]
            if not reached[v]:
                continue
            var cost = 1.0 if unit_cost else g.weights[k]
            if _is_dag_edge(dist, u, v, cost):
                indegree[v] -= 1
                if indegree[v] == 0:
                    order.append(v)
    if len(order) != reached_count:
        # A cycle of zero-weight edges: every rotation of it is another shortest path, so
        # σ is unbounded and there is no answer to scale a dependency by.
        return CENTRALITY_ERR_ZERO_WEIGHT_CYCLE

    # Pass 2: σ, the number of shortest source→node paths, in topological order.
    var sigma = _zeros(n)
    sigma[source] = 1.0
    for i in range(len(order)):
        var u = order[i]
        for k in range(g.row_ptr[u], g.row_ptr[u + 1]):
            var v = g.targets[k]
            if not reached[v]:
                continue
            var cost = 1.0 if unit_cost else g.weights[k]
            if _is_dag_edge(dist, u, v, cost):
                sigma[v] += sigma[u]

    # Pass 3: δ, in reverse topological order. δ[u] is final once every DAG successor's
    # is, and successors come later in the order — so one reverse sweep suffices and the
    # node's own share can be banked as it is passed.
    var delta = _zeros(n)
    var i = len(order) - 1
    while i >= 0:
        var u = order[i]
        for k in range(g.row_ptr[u], g.row_ptr[u + 1]):
            var v = g.targets[k]
            if not reached[v]:
                continue
            var cost = 1.0 if unit_cost else g.weights[k]
            if _is_dag_edge(dist, u, v, cost) and sigma[v] > 0.0:
                delta[u] += (sigma[u] / sigma[v]) * (1.0 + delta[v])
        if u != source:
            betweenness[u] += delta[u]
        if sigma[u] > max_sigma:
            max_sigma = sigma[u]
        i -= 1
    return GRAPH_OK


def _no_betweenness(
    status: Int, n_nodes: Int, weighted: Bool, normalized: Bool
) -> BetweennessResult:
    return BetweennessResult(
        status, n_nodes, 0, weighted, normalized, False, True, -1,
        CENTRALITY_UNDEFINED, List[Float64](),
    )


def _betweenness(
    g: GraphCSR, weighted: Bool, normalized: Bool
) -> BetweennessResult:
    """Brandes over every source. O(V(V+E)) unweighted, O(VE log E) weighted."""
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return _no_betweenness(status, 0, weighted, normalized)
    var n = g.n_nodes
    if n == 0:
        return _no_betweenness(GRAPH_ERR_EMPTY_GRAPH, 0, weighted, normalized)
    if _all_pairs_work_exceeds(n, len(g.targets)):
        return _no_betweenness(
            CENTRALITY_ERR_WORK_TOO_LARGE, n, weighted, normalized
        )
    if weighted:
        var defect = _weight_status(g.weights)
        if defect != GRAPH_OK:
            return _no_betweenness(defect, n, weighted, normalized)

    # Exact symmetry, because the pair-doubling that halving undoes is only exact when
    # the reverse path has the identical length. Structural symmetry is enough when the
    # weights are ignored.
    var sym = graph_csr_symmetry(g, 0.0)
    var undirected = sym.structurally_symmetric
    if weighted:
        undirected = sym.weight_symmetric

    var values = _zeros(n)
    var max_sigma: Float64 = 0.0
    for s in range(n):
        var dist = List[Float64]()
        var reached = List[Bool]()
        if weighted:
            var d = graph_csr_dijkstra(g, s)
            if d.status != GRAPH_OK:
                return _no_betweenness(d.status, n, weighted, normalized)
            dist = d.distance.copy()
            reached = d.reached.copy()
        else:
            var lv = graph_csr_bfs_levels(g, s)
            if lv.status != GRAPH_OK:
                return _no_betweenness(lv.status, n, weighted, normalized)
            for v in range(n):
                if lv.reached[v]:
                    dist.append(Float64(lv.level[v]))
                else:
                    dist.append(CENTRALITY_UNDEFINED)
                reached.append(lv.reached[v])
        var pass_status = _brandes_source(
            g, s, dist, reached, not weighted, values, max_sigma
        )
        if pass_status != GRAPH_OK:
            return _no_betweenness(pass_status, n, weighted, normalized)

    if undirected:
        for v in range(n):
            values[v] = values[v] / 2.0
    if normalized:
        var directed_flag = 0.0 if undirected else 1.0
        for v in range(n):
            values[v] = betweenness_centrality_norm(
                values[v], Float64(n), directed_flag
            )
    var best = _argmax(values)
    var best_value = CENTRALITY_UNDEFINED
    if best >= 0:
        best_value = values[best]
    return BetweennessResult(
        GRAPH_OK, n, n, weighted, normalized, undirected,
        max_sigma <= CENTRALITY_MAX_EXACT_COUNT, best, best_value, values^,
    )


def graph_betweenness_unweighted(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    normalized: Bool,
) -> BetweennessResult:
    """Brandes betweenness counting hops, ignoring `weights`.

    Exact: levels are integers, so every shortest-path count is an integer sum and the
    DAG equality test cannot miss a route to rounding. This is the variant to use when
    the edges are unweighted or all of equal cost, whatever the weight array says.
    """
    return _betweenness(
        graph_csr_from_arrays(row_ptr, targets, weights, n_nodes), False, normalized
    )


def graph_betweenness_weighted(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    normalized: Bool,
) -> BetweennessResult:
    """Brandes betweenness over weighted shortest paths, one Dijkstra per source.

    Rejects a negative or non-finite weight instead of answering: Dijkstra's distances
    would be wrong, so the DAG built from them would be wrong too, and a betweenness is
    only as sound as the distances under it.
    """
    return _betweenness(
        graph_csr_from_arrays(row_ptr, targets, weights, n_nodes), True, normalized
    )


def graph_betweenness_from_triplets(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    n_nodes: Int,
    weighted: Bool,
    normalized: Bool,
) -> BetweennessResult:
    """Build a CSR from an edge list, then Brandes. Out-of-range endpoints are skipped."""
    if n_nodes < 0:
        return _no_betweenness(
            GRAPH_ERR_INVALID_DIMENSIONS, 0, weighted, normalized
        )
    if len(dst) != len(src) or len(weight) != len(src):
        return _no_betweenness(GRAPH_ERR_LENGTH_MISMATCH, 0, weighted, normalized)
    return _betweenness(
        graph_csr_from_triplets(src, dst, weight, n_nodes), weighted, normalized
    )


# ── closeness ─────────────────────────────────────────────────────────────────


def _no_closeness(status: Int, n_nodes: Int, weighted: Bool) -> ClosenessResult:
    return ClosenessResult(
        status, n_nodes, weighted, 0, 0, List[Float64](), List[Float64](),
        List[Bool](), List[Int](), List[Float64](),
    )


def _closeness(g: GraphCSR, weighted: Bool) -> ClosenessResult:
    """One traversal per node, keeping the reachable count next to every score."""
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return _no_closeness(status, 0, weighted)
    var n = g.n_nodes
    if n == 0:
        return _no_closeness(GRAPH_ERR_EMPTY_GRAPH, 0, weighted)
    if _all_pairs_work_exceeds(n, len(g.targets)):
        return _no_closeness(CENTRALITY_ERR_WORK_TOO_LARGE, n, weighted)
    if weighted:
        var defect = _weight_status(g.weights)
        if defect != GRAPH_OK:
            return _no_closeness(defect, n, weighted)

    var values = List[Float64]()
    var scaled = List[Float64]()
    var defined = List[Bool]()
    var reached_count = List[Int]()
    var sum_distance = List[Float64]()
    var defined_count = 0
    var incomplete = 0

    for u in range(n):
        var others = 0
        var total = 0.0
        if weighted:
            var d = graph_csr_dijkstra(g, u)
            if d.status != GRAPH_OK:
                return _no_closeness(d.status, n, weighted)
            for v in range(n):
                if v != u and d.reached[v]:
                    others += 1
                    total += d.distance[v]
        else:
            var lv = graph_csr_bfs_levels(g, u)
            if lv.status != GRAPH_OK:
                return _no_closeness(lv.status, n, weighted)
            for v in range(n):
                if v != u and lv.reached[v]:
                    others += 1
                    total += Float64(lv.level[v])
        reached_count.append(others)
        sum_distance.append(total)
        if others < n - 1:
            incomplete += 1
        if others == 0 or total <= 0.0:
            # No mean distance exists: nothing reached, or everything reached at
            # distance 0 over zero-weight edges. The frozen kernels return 0.0 for both.
            values.append(CENTRALITY_UNDEFINED)
            scaled.append(CENTRALITY_UNDEFINED)
            defined.append(False)
            continue
        # The frozen scalar is `(n_nodes - 1) / Σd`, so the reachable set's own size goes
        # in as `others + 1` and the ratio comes out component-local.
        var value = frozen_closeness_ratio(total, Float64(others + 1))
        values.append(value)
        defined.append(True)
        defined_count += 1
        if n > 1:
            scaled.append(value * Float64(others) / Float64(n - 1))
        else:
            scaled.append(value)
    return ClosenessResult(
        GRAPH_OK, n, weighted, defined_count, incomplete, values^, scaled^,
        defined^, reached_count^, sum_distance^,
    )


def graph_closeness_centrality(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    weighted: Bool,
) -> ClosenessResult:
    """Closeness per node, component-local, with the reachable count returned alongside.

    A node that reaches nobody is `defined[v] == False`, never `0.0` — see the module
    docstring for why the frozen "0 unless it reaches every other node" convention cannot
    be kept honest. `scaled_values` is the Wasserman–Faust form for cross-component
    comparison.
    """
    return _closeness(
        graph_csr_from_arrays(row_ptr, targets, weights, n_nodes), weighted
    )


def _no_harmonic(
    status: Int, n_nodes: Int, weighted: Bool, normalized: Bool
) -> HarmonicResult:
    return HarmonicResult(
        status, n_nodes, weighted, normalized, 0, List[Float64](), List[Bool]()
    )


def _harmonic(g: GraphCSR, weighted: Bool, normalized: Bool) -> HarmonicResult:
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return _no_harmonic(status, 0, weighted, normalized)
    var n = g.n_nodes
    if n == 0:
        return _no_harmonic(GRAPH_ERR_EMPTY_GRAPH, 0, weighted, normalized)
    if _all_pairs_work_exceeds(n, len(g.targets)):
        return _no_harmonic(
            CENTRALITY_ERR_WORK_TOO_LARGE, n, weighted, normalized
        )
    if weighted:
        var defect = _weight_status(g.weights)
        if defect != GRAPH_OK:
            return _no_harmonic(defect, n, weighted, normalized)

    var values = List[Float64]()
    var defined = List[Bool]()
    var zero_distance_nodes = 0
    for u in range(n):
        var total = 0.0
        var has_zero = False
        if weighted:
            var d = graph_csr_dijkstra(g, u)
            if d.status != GRAPH_OK:
                return _no_harmonic(d.status, n, weighted, normalized)
            for v in range(n):
                if v != u and d.reached[v]:
                    if d.distance[v] == 0.0:
                        has_zero = True
                    else:
                        total += 1.0 / d.distance[v]
        else:
            var lv = graph_csr_bfs_levels(g, u)
            if lv.status != GRAPH_OK:
                return _no_harmonic(lv.status, n, weighted, normalized)
            for v in range(n):
                if v != u and lv.reached[v]:
                    total += 1.0 / Float64(lv.level[v])
        if has_zero:
            # `1/0` is not a large number, it is no number. Only zero-weight edges can
            # put a distinct node at distance 0, and this is the mirror of closeness's
            # undefined case.
            zero_distance_nodes += 1
            values.append(CENTRALITY_UNDEFINED)
            defined.append(False)
            continue
        if normalized and n > 1:
            total = total / Float64(n - 1)
        values.append(total)
        defined.append(True)
    return HarmonicResult(
        GRAPH_OK, n, weighted, normalized, zero_distance_nodes, values^, defined^
    )


def graph_harmonic_centrality(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    weighted: Bool,
    normalized: Bool,
) -> HarmonicResult:
    """`Σ 1/d` over reachable others — the closeness variant a disconnected graph allows.

    An unreachable other contributes exactly 0, so no convention is needed and an
    isolated node's 0 is a real answer rather than a stand-in for "undefined".
    """
    return _harmonic(
        graph_csr_from_arrays(row_ptr, targets, weights, n_nodes),
        weighted,
        normalized,
    )


# ── degree ────────────────────────────────────────────────────────────────────


def _no_degree(status: Int, n_nodes: Int, normalized: Bool) -> DegreeCentralityResult:
    return DegreeCentralityResult(
        status, n_nodes, normalized, 0, 0, List[Float64](), List[Float64](),
        List[Float64](),
    )


def graph_degree_centrality(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    normalized: Bool,
) -> DegreeCentralityResult:
    """Out-, in- and total-degree centrality over *distinct* neighbours.

    Parallel edges are collapsed and self-loops dropped before counting, and both counts
    are reported: `k/(n-1)` is a fraction of the other nodes, so a multigraph edge counted
    twice would put it above 1 and a self-loop would credit a node for reaching itself.
    The frozen `graph_algorithms.degree_centrality` supplies the ratio itself.
    """
    var g = graph_csr_from_arrays(row_ptr, targets, weights, n_nodes)
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return _no_degree(status, 0, normalized)
    var n = g.n_nodes
    if n == 0:
        return _no_degree(GRAPH_ERR_EMPTY_GRAPH, 0, normalized)

    var canonical = graph_csr_dedupe_min(g)
    var collapsed = len(g.targets) - len(canonical.targets)
    var loops = 0
    var loop_per_node = List[Int]()
    for _ in range(n):
        loop_per_node.append(0)
    for u in range(n):
        for k in range(canonical.row_ptr[u], canonical.row_ptr[u + 1]):
            if canonical.targets[k] == u:
                loops += 1
                loop_per_node[u] += 1

    var out_degrees = graph_csr_out_degrees(canonical)
    var in_degrees = graph_csr_in_degrees(canonical)
    var out_values = List[Float64]()
    var in_values = List[Float64]()
    var total_values = List[Float64]()
    for u in range(n):
        var out_k = Float64(out_degrees[u] - loop_per_node[u])
        var in_k = Float64(in_degrees[u] - loop_per_node[u])
        if normalized:
            out_values.append(frozen_degree_ratio(out_k, Float64(n)))
            in_values.append(frozen_degree_ratio(in_k, Float64(n)))
            # Halved so a symmetric graph reads the same in all three vectors: out and
            # in each count the same k, and their sum is over 2(n-1) possible ends.
            total_values.append(frozen_degree_ratio(out_k + in_k, Float64(n)) / 2.0)
        else:
            out_values.append(out_k)
            in_values.append(in_k)
            total_values.append(out_k + in_k)
    return DegreeCentralityResult(
        GRAPH_OK, n, normalized, collapsed, loops, out_values^, in_values^,
        total_values^,
    )


# ── eigenvector centrality ────────────────────────────────────────────────────


def _no_eigenvector(status: Int, n_nodes: Int, max_iter: Int) -> EigenvectorResult:
    return EigenvectorResult(
        status, n_nodes, max_iter, False, False, False, CENTRALITY_UNDEFINED,
        CENTRALITY_UNDEFINED, CENTRALITY_UNDEFINED, List[Float64](),
    )


def _strongly_connected(g: GraphCSR) -> Bool:
    """Does node 0 reach every node, and every node reach node 0.

    Two BFS passes, one on the graph and one on its reverse — the standard Kosaraju
    precondition test, and enough to know whether the adjacency matrix is irreducible and
    therefore whether Perron–Frobenius applies.
    """
    var forward = graph_csr_bfs_levels(g, 0)
    if forward.status != GRAPH_OK or forward.reached_count != g.n_nodes:
        return False
    var backward = graph_csr_bfs_levels(graph_csr_reverse(g), 0)
    return backward.status == GRAPH_OK and backward.reached_count == g.n_nodes


def graph_eigenvector_centrality(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    max_iter: Int,
    tol: Float64,
) -> EigenvectorResult:
    """Dominant eigenvector of the adjacency matrix, from the frozen power iteration.

    `linalg_ext.mat_power_iteration` does the iteration — it is the frozen dominant-
    eigenvector kernel and has no size cap — on the dense image of the min-weight
    canonical graph, shifted by `shift * I`.

    The shift is not a refinement, it is what makes the answer exist. An undirected
    bipartite graph has a spectrum symmetric about 0, so `λ_min = -λ_max` and power
    iteration has two dominant directions of equal magnitude: the iterate oscillates
    between them forever and never converges. On the 3-node path — bipartite, as every
    tree is — the frozen kernel returns eigenvalue `4/3` for any iteration count with a
    vector that alternates between `(1,2,1)/√6` and `(1,1,1)/√3`, neither of which is an
    eigenvector (the true answer is `√2` and `(1,√2,1)/2`). Nothing in its return value
    says so. Adding `c·I` with `c` the maximum row sum — an upper bound on the spectral
    radius of a non-negative matrix — moves every eigenvalue to `λ + c >= 0` without
    moving a single eigenvector, so the dominant direction becomes unique and the
    iteration converges; `c` is then subtracted back off the eigenvalue.

    The shift has a price, and it is visible rather than hidden: it narrows the ratio
    `(λ2 + c)/(λ1 + c)` that sets the convergence rate, so a graph that would have settled
    in 200 iterations may need some hundreds more. `converged = False` with a small
    `residual` means exactly that, and raising `max_iter` is the remedy — which is why the
    iteration ceiling is `CENTRALITY_MAX_ITERATION_CELLS` and not the much tighter
    all-pairs one.

    Everything else added here is what the frozen kernel cannot report: the sign is fixed
    so the vector is the non-negative Perron one, the residual `max|Ax - λx|` is measured
    against the **unshifted** adjacency so `converged` is a fact that the shift cannot
    flatter, negative and non-finite weights are refused (a signed adjacency has no
    Perron vector), and `strongly_connected` warns when the dominant eigenspace may not
    be one-dimensional.

    The dense image caps the graph at `GRAPH_MAX_DENSE_CELLS`, reported as
    `dense_image_too_large` rather than allocated.
    """
    var g = graph_csr_from_arrays(row_ptr, targets, weights, n_nodes)
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return _no_eigenvector(status, 0, max_iter)
    var n = g.n_nodes
    if n == 0:
        return _no_eigenvector(GRAPH_ERR_EMPTY_GRAPH, 0, max_iter)
    if max_iter <= 0:
        return _no_eigenvector(CENTRALITY_ERR_MAX_ITER, n, max_iter)
    if tol < 0.0:
        return _no_eigenvector(CENTRALITY_ERR_TOLERANCE, n, max_iter)
    var defect = _weight_status(g.weights)
    if defect != GRAPH_OK:
        return _no_eigenvector(defect, n, max_iter)
    if Float64(max_iter) * Float64(n) * Float64(n) > Float64(
        CENTRALITY_MAX_ITERATION_CELLS
    ):
        return _no_eigenvector(CENTRALITY_ERR_WORK_TOO_LARGE, n, max_iter)

    var dense = graph_csr_to_dense(g, 0.0)
    if dense.status != GRAPH_OK:
        return _no_eigenvector(dense.status, n, max_iter)
    # `max_i Σ_j |a_ij|` bounds the spectral radius of a non-negative matrix, so this
    # shift is guaranteed to leave no eigenvalue negative and therefore no second
    # direction as dominant as the first.
    var shift = 0.0
    for i in range(n):
        var row_sum = 0.0
        for j in range(n):
            row_sum += dense.values[i * n + j]
        if row_sum > shift:
            shift = row_sum
    var shifted = dense.values.copy()
    for i in range(n):
        shifted[i * n + i] += shift

    var iterated = mat_power_iteration(mat_from_list(shifted, n, n), max_iter)
    var eigenvalue = iterated.eigenvalue - shift
    var vector = iterated.eigenvector.copy()

    # Power iteration is free to return either sign of the eigenvector. A centrality is
    # non-negative, so flip once toward the Perron orientation.
    var signed_total = 0.0
    for i in range(n):
        signed_total += vector[i]
    if signed_total < 0.0:
        for i in range(n):
            vector[i] = -vector[i]

    # Residual against the original adjacency, never the shifted one: `A x = λ x` is the
    # claim being made, and a shift that helped the iteration must not also grade it.
    var residual = 0.0
    for i in range(n):
        var row_value = 0.0
        for j in range(n):
            row_value += dense.values[i * n + j] * vector[j]
        var gap = fabs(row_value - eigenvalue * vector[i])
        if gap > residual:
            residual = gap
    var scale = 1.0
    if fabs(eigenvalue) > 1.0:
        scale = fabs(eigenvalue)
    var converged = residual <= tol * scale
    var sym = graph_csr_symmetry(g, 0.0)
    return EigenvectorResult(
        GRAPH_OK, n, max_iter, converged, sym.weight_symmetric,
        _strongly_connected(g), eigenvalue, residual, shift, vector^,
    )


# ── PageRank ──────────────────────────────────────────────────────────────────


def _no_pagerank(
    status: Int, n_nodes: Int, damping: Float64, max_iter: Int, redistributed: Bool
) -> PageRankResult:
    return PageRankResult(
        status, n_nodes, max_iter, 0, redistributed, False, damping,
        CENTRALITY_UNDEFINED, CENTRALITY_UNDEFINED, List[Float64](),
    )


def graph_pagerank(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    damping: Float64,
    max_iter: Int,
    tol: Float64,
    dangling_uniform: Bool,
) -> PageRankResult:
    """PageRank from the frozen `network_analysis.pagerank`, made correct and measurable.

    The frozen iteration is called, not rewritten. Two things are done around it. First,
    with `dangling_uniform` the *input graph* is augmented so that every node with no
    out-edges links to all nodes — which is precisely the uniform redistribution the
    frozen loop is missing, expressed as a graph rather than as a patch to its
    arithmetic. Second, the result is checked: `mass` exposes the leak when
    `dangling_uniform` is False, and `residual` with `converged` says whether the fixed
    point was actually reached, which the frozen return value cannot.

    Weights are ignored: PageRank is a random walk over out-edges, so a parallel edge is
    deliberately kept and doubles the transition probability, and a self-loop keeps the
    surfer in place. `damping` must be in `[0, 1)` — at 1 there is no teleport and the
    walk has no unique stationary distribution on a general graph.
    """
    var g = graph_csr_from_arrays(row_ptr, targets, weights, n_nodes)
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return _no_pagerank(status, 0, damping, max_iter, dangling_uniform)
    var n = g.n_nodes
    if n == 0:
        return _no_pagerank(
            GRAPH_ERR_EMPTY_GRAPH, 0, damping, max_iter, dangling_uniform
        )
    if isnan(damping) or damping < 0.0 or damping >= 1.0:
        return _no_pagerank(
            CENTRALITY_ERR_DAMPING, n, damping, max_iter, dangling_uniform
        )
    if max_iter <= 0:
        return _no_pagerank(
            CENTRALITY_ERR_MAX_ITER, n, damping, max_iter, dangling_uniform
        )
    if isnan(tol) or tol < 0.0:
        return _no_pagerank(
            CENTRALITY_ERR_TOLERANCE, n, damping, max_iter, dangling_uniform
        )

    var dangling = 0
    for u in range(n):
        if g.row_ptr[u + 1] == g.row_ptr[u]:
            dangling += 1
    var augmented_edges = len(g.targets)
    if dangling_uniform:
        augmented_edges += dangling * n
    if Float64(max_iter) * (Float64(n) + Float64(augmented_edges)) > Float64(
        CENTRALITY_MAX_WORK
    ):
        return _no_pagerank(
            CENTRALITY_ERR_WORK_TOO_LARGE, n, damping, max_iter, dangling_uniform
        )

    # The frozen kernel indexes `adj[i][j]` with no range test; every target here comes
    # from a validated CSR, so the crash it is capable of cannot happen through this path.
    var adjacency = List[List[Int]]()
    for u in range(n):
        var row = List[Int]()
        for k in range(g.row_ptr[u], g.row_ptr[u + 1]):
            row.append(g.targets[k])
        if dangling_uniform and len(row) == 0:
            for v in range(n):
                row.append(v)
        adjacency.append(row^)

    var ranks = frozen_pagerank(adjacency, damping, max_iter, tol)
    if len(ranks) != n:
        return _no_pagerank(
            GRAPH_ERR_LENGTH_MISMATCH, n, damping, max_iter, dangling_uniform
        )

    var mass = 0.0
    for u in range(n):
        mass += ranks[u]

    # One application of the same operator the iteration used: teleport plus each node's
    # share pushed along its out-edges. The gap to `ranks` is the honest convergence test.
    var next_ranks = _zeros(n)
    var teleport = (1.0 - damping) / Float64(n)
    for u in range(n):
        next_ranks[u] = teleport
    for u in range(n):
        var out_degree = len(adjacency[u])
        if out_degree == 0:
            continue
        var share = ranks[u] / Float64(out_degree)
        for j in range(out_degree):
            next_ranks[adjacency[u][j]] += damping * share
    var residual = 0.0
    for u in range(n):
        var gap = fabs(next_ranks[u] - ranks[u])
        if gap > residual:
            residual = gap
    return PageRankResult(
        GRAPH_OK, n, max_iter, dangling, dangling_uniform, residual <= tol,
        damping, mass, residual, ranks^,
    )
