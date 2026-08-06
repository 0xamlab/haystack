"""
social_network.mojo — Social network analysis. Zero Python imports.

Replaces igraph basics with pure Mojo implementations for directed graph
analysis using adjacency lists (List[List[Int]]).

Public API:
  in_degree                  — Count incoming edges
  out_degree                 — Count outgoing edges
  reciprocity                — Fraction of reciprocated edges
  influence_spread_ic        — Independent Cascade model
  local_clustering_directed  — Local clustering for directed graph
  strongly_connected_check   — Check if graph is strongly connected
  community_label_propagation — Label propagation community detection
  network_density            — E / (V*(V-1)) for directed graph
  average_path_length_estimate — Estimate avg path length via BFS
"""
from std.random import random_float64


# Untrusted simulation/iteration counts are clamped to this ceiling: each round
# walks the graph, so an unbounded value from the wire is a CPU weapon.
comptime MAX_SIM_COUNT: Int = 100000


def _adj_valid(adj: List[List[Int]]) -> Bool:
    """True when every neighbor index lies in [0, n).

    Neighbor values are used directly as indices into adj and per-node arrays;
    a ragged or out-of-range one is an uncatchable out-of-bounds abort.
    """
    var n = len(adj)
    for i in range(n):
        for j in range(len(adj[i])):
            if adj[i][j] < 0 or adj[i][j] >= n:
                return False
    return True


# ── in_degree ────────────────────────────────────────────────────────────────


def in_degree(adj: List[List[Int]], node: Int) -> Int:
    """Count incoming edges to a node.

    Args:
        adj:  Adjacency list (directed).
        node: Target node index.

    Returns:
        Number of incoming edges.
    """
    var count = 0
    for i in range(len(adj)):
        for j in range(len(adj[i])):
            if adj[i][j] == node:
                count += 1
    return count


# ── out_degree ───────────────────────────────────────────────────────────────


def out_degree(adj: List[List[Int]], node: Int) -> Int:
    """Count outgoing edges from a node.

    Args:
        adj:  Adjacency list (directed).
        node: Source node index.

    Returns:
        Number of outgoing edges.
    """
    return len(adj[node])


# ── reciprocity ──────────────────────────────────────────────────────────────


def reciprocity(adj: List[List[Int]]) -> Float64:
    """Fraction of edges that are reciprocated.

    Args:
        adj: Adjacency list (directed).

    Returns:
        Reciprocity (0 to 1).
    """
    var n = len(adj)
    # adj[target] is read with the neighbor value as index.
    if not _adj_valid(adj):
        return 0.0
    var total_edges = 0
    var recip_edges = 0
    for i in range(n):
        for j in range(len(adj[i])):
            total_edges += 1
            var target = adj[i][j]
            # Check if reverse edge exists
            for k in range(len(adj[target])):
                if adj[target][k] == i:
                    recip_edges += 1
                    break
    if total_edges == 0:
        return 0.0
    return Float64(recip_edges) / Float64(total_edges)


# ── _has_edge ────────────────────────────────────────────────────────────────


def _has_edge(adj: List[List[Int]], src: Int, dst: Int) -> Bool:
    """Check if edge src->dst exists."""
    for i in range(len(adj[src])):
        if adj[src][i] == dst:
            return True
    return False


# ── influence_spread_ic ──────────────────────────────────────────────────────


def influence_spread_ic(
    adj: List[List[Int]],
    seeds: List[Int],
    p: Float64,
    n_simulations: Int,
) -> Float64:
    """Independent Cascade model: average number of activated nodes.

    Args:
        adj:            Adjacency list (directed).
        seeds:          Initial seed nodes.
        p:              Propagation probability per edge.
        n_simulations:  Number of Monte Carlo simulations.

    Returns:
        Average number of activated nodes.
    """
    var n = len(adj)
    if not _adj_valid(adj):
        return 0.0
    # n_simulations <= 0 would divide by zero below; huge values are a CPU
    # weapon and get clamped to the documented ceiling.
    var sims = n_simulations
    if sims <= 0:
        return 0.0
    if sims > MAX_SIM_COUNT:
        sims = MAX_SIM_COUNT
    var total_activated: Float64 = 0.0

    for _sim in range(sims):
        # Track activated nodes
        var active = List[Bool]()
        for _i in range(n):
            active.append(False)
        # Queue for BFS-like spread
        var queue = List[Int]()
        for s in range(len(seeds)):
            var seed = seeds[s]
            if seed >= 0 and seed < n:
                active[seed] = True
                queue.append(seed)

        var head = 0
        while head < len(queue):
            var node = queue[head]
            head += 1
            for j in range(len(adj[node])):
                var neighbor = adj[node][j]
                if not active[neighbor]:
                    var r = random_float64()
                    if r < p:
                        active[neighbor] = True
                        queue.append(neighbor)

        var count = 0
        for i in range(n):
            if active[i]:
                count += 1
        total_activated += Float64(count)

    return total_activated / Float64(sims)


# ── local_clustering_directed ────────────────────────────────────────────────


def local_clustering_directed(adj: List[List[Int]], node: Int) -> Float64:
    """Local clustering coefficient for a directed graph node.

    Uses the formula: C = edges among neighbors / (k*(k-1))
    where k = total degree (in + out unique neighbors).

    Args:
        adj:  Adjacency list (directed).
        node: Node index.

    Returns:
        Local clustering coefficient.
    """
    var n = len(adj)
    # node indexes adj directly, and neighbor values index is_neighbor.
    if node < 0 or node >= n or not _adj_valid(adj):
        return 0.0
    # Get all unique neighbors (both in and out)
    var is_neighbor = List[Bool]()
    for _i in range(n):
        is_neighbor.append(False)
    # Out-neighbors
    for j in range(len(adj[node])):
        var nb = adj[node][j]
        if nb != node:
            is_neighbor[nb] = True
    # In-neighbors
    for i in range(n):
        for j in range(len(adj[i])):
            if adj[i][j] == node and i != node:
                is_neighbor[i] = True

    var neighbors = List[Int]()
    for i in range(n):
        if is_neighbor[i]:
            neighbors.append(i)

    var k = len(neighbors)
    if k <= 1:
        return 0.0

    # Count edges among neighbors
    var edges_among = 0
    for i in range(k):
        for j in range(k):
            if i != j:
                if _has_edge(adj, neighbors[i], neighbors[j]):
                    edges_among += 1

    return Float64(edges_among) / Float64(k * (k - 1))


# ── strongly_connected_check ────────────────────────────────────────────────


def strongly_connected_check(adj: List[List[Int]]) -> Bool:
    """Check if directed graph is strongly connected.

    BFS from node 0 reaches all, and reverse graph BFS from 0 also reaches all.

    Args:
        adj: Adjacency list (directed).

    Returns:
        True if strongly connected.
    """
    var n = len(adj)
    if n == 0:
        return True
    # visited[nb] and rev[adj[i][j]] are read with neighbor values as indices.
    if not _adj_valid(adj):
        return False

    # Forward BFS from node 0
    var visited = List[Bool]()
    for _i in range(n):
        visited.append(False)
    var queue = List[Int]()
    visited[0] = True
    queue.append(0)
    var head = 0
    while head < len(queue):
        var node = queue[head]
        head += 1
        for j in range(len(adj[node])):
            var nb = adj[node][j]
            if not visited[nb]:
                visited[nb] = True
                queue.append(nb)

    for i in range(n):
        if not visited[i]:
            return False

    # Build reverse graph
    var rev = List[List[Int]]()
    for _i in range(n):
        rev.append(List[Int]())
    for i in range(n):
        for j in range(len(adj[i])):
            rev[adj[i][j]].append(i)

    # Reverse BFS from node 0
    var visited2 = List[Bool]()
    for _i in range(n):
        visited2.append(False)
    var queue2 = List[Int]()
    visited2[0] = True
    queue2.append(0)
    head = 0
    while head < len(queue2):
        var node = queue2[head]
        head += 1
        for j in range(len(rev[node])):
            var nb = rev[node][j]
            if not visited2[nb]:
                visited2[nb] = True
                queue2.append(nb)

    for i in range(n):
        if not visited2[i]:
            return False

    return True


# ── community_label_propagation ──────────────────────────────────────────────


def community_label_propagation(adj: List[List[Int]], max_iter: Int) -> List[Int]:
    """Label propagation community detection.

    Each node starts with its own label. Iteratively, each node adopts
    the most frequent label among its neighbors.

    Args:
        adj:      Adjacency list (directed, treated as undirected for labels).
        max_iter: Maximum iterations.

    Returns:
        Community label per node.
    """
    var n = len(adj)
    # labels[adj[i][j]] is read with neighbor values as indices.
    if not _adj_valid(adj):
        return List[Int]()
    var labels = List[Int]()
    for i in range(n):
        labels.append(i)

    # Huge max_iter is a CPU weapon; clamp to the documented ceiling.
    var iters = max_iter
    if iters > MAX_SIM_COUNT:
        iters = MAX_SIM_COUNT
    if iters < 0:
        iters = 0

    for _it in range(iters):
        var changed = False
        for i in range(n):
            # Collect neighbor labels (both in and out)
            var neighbor_labels = List[Int]()
            for j in range(len(adj[i])):
                neighbor_labels.append(labels[adj[i][j]])
            # Also add in-neighbors
            for j in range(n):
                for k in range(len(adj[j])):
                    if adj[j][k] == i:
                        neighbor_labels.append(labels[j])
                        break

            if len(neighbor_labels) == 0:
                continue

            # Find most frequent label
            var best_label = neighbor_labels[0]
            var best_count = 0
            for a in range(len(neighbor_labels)):
                var lbl = neighbor_labels[a]
                var cnt = 0
                for b in range(len(neighbor_labels)):
                    if neighbor_labels[b] == lbl:
                        cnt += 1
                if cnt > best_count:
                    best_count = cnt
                    best_label = lbl

            if labels[i] != best_label:
                labels[i] = best_label
                changed = True

        if not changed:
            break

    return labels^


# ── network_density ──────────────────────────────────────────────────────────


def network_density(adj: List[List[Int]]) -> Float64:
    """Network density: E / (V*(V-1)) for directed graph.

    Args:
        adj: Adjacency list (directed).

    Returns:
        Density (0 to 1).
    """
    var n = len(adj)
    if n <= 1:
        return 0.0
    var total_edges = 0
    for i in range(n):
        total_edges += len(adj[i])
    return Float64(total_edges) / Float64(n * (n - 1))


# ── average_path_length_estimate ─────────────────────────────────────────────


def average_path_length_estimate(adj: List[List[Int]], n_samples: Int) -> Float64:
    """Estimate average path length via BFS from random sample of nodes.

    Args:
        adj:       Adjacency list (directed).
        n_samples: Number of source nodes to sample.

    Returns:
        Estimated average shortest path length.
    """
    var n = len(adj)
    if n <= 1:
        return 0.0
    # dist[nb] is read with neighbor values as indices. (n_samples is already
    # clamped to n below, and negative values run zero samples.)
    if not _adj_valid(adj):
        return 0.0

    var total_dist: Float64 = 0.0
    var total_pairs = 0
    var actual_samples = n_samples
    if actual_samples > n:
        actual_samples = n

    for s in range(actual_samples):
        # Pick source node (sequential for determinism, wraps around)
        var source = s % n

        # BFS from source
        var dist = List[Int]()
        for _i in range(n):
            dist.append(-1)
        dist[source] = 0
        var queue = List[Int]()
        queue.append(source)
        var head = 0
        while head < len(queue):
            var node = queue[head]
            head += 1
            for j in range(len(adj[node])):
                var nb = adj[node][j]
                if dist[nb] == -1:
                    dist[nb] = dist[node] + 1
                    queue.append(nb)

        for i in range(n):
            if dist[i] > 0:
                total_dist += Float64(dist[i])
                total_pairs += 1

    if total_pairs == 0:
        return 0.0
    return total_dist / Float64(total_pairs)
