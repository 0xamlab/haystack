"""
network_analysis.mojo — Network/graph analytics. Zero Python imports.

Replaces networkx analytics with pure Mojo implementations for degree,
density, PageRank, centrality measures, clustering coefficients,
connectivity checks, and BFS shortest paths.

Public API:
  degree                  — Degree of a node
  degree_distribution     — Degree of each node
  density                 — Graph density (undirected)
  pagerank                — PageRank algorithm
  degree_centrality       — Degree centrality per node
  closeness_centrality    — Closeness centrality via BFS
  clustering_coefficient  — Local clustering coefficient
  avg_clustering_coefficient — Average clustering coefficient
  is_connected            — Check graph connectivity
  connected_components    — Find all connected components
  bfs_distances           — BFS shortest path distances
"""
from std.math import abs as fabs


# ── degree ────────────────────────────────────────────────────────────────────


fn degree(adj: List[List[Int]], node: Int) -> Int:
    """Degree of a node (number of neighbors)."""
    return len(adj[node])


# ── degree_distribution ───────────────────────────────────────────────────────


fn degree_distribution(adj: List[List[Int]]) -> List[Int]:
    """Degree of each node."""
    var result = List[Int]()
    for i in range(len(adj)):
        result.append(len(adj[i]))
    return result^


# ── density ───────────────────────────────────────────────────────────────────


fn density(adj: List[List[Int]]) -> Float64:
    """Graph density = 2E / (V*(V-1)) for undirected graphs."""
    var n = len(adj)
    if n <= 1:
        return 0.0
    var edge_count = 0
    for i in range(n):
        edge_count += len(adj[i])
    # Each edge counted twice in undirected adjacency list
    var e = edge_count
    return Float64(e) / Float64(n * (n - 1))


# ── bfs_distances ─────────────────────────────────────────────────────────────


fn bfs_distances(adj: List[List[Int]], start: Int) -> List[Int]:
    """BFS shortest path distances from start. -1 for unreachable."""
    var n = len(adj)
    var dist = List[Int]()
    for i in range(n):
        dist.append(-1)
    dist[start] = 0
    var queue = List[Int]()
    queue.append(start)
    var head = 0
    while head < len(queue):
        var cur = queue[head]
        head += 1
        var ncount = len(adj[cur])
        for j in range(ncount):
            var nb = adj[cur][j]
            if dist[nb] == -1:
                dist[nb] = dist[cur] + 1
                queue.append(nb)
    return dist^


# ── pagerank ──────────────────────────────────────────────────────────────────


fn pagerank(
    adj: List[List[Int]],
    damping: Float64 = 0.85,
    max_iter: Int = 100,
    tol: Float64 = 1e-6,
) -> List[Float64]:
    """PageRank algorithm. Returns rank for each node."""
    var n = len(adj)
    if n == 0:
        return List[Float64]()
    var rank = List[Float64]()
    var new_rank = List[Float64]()
    var init_val = 1.0 / Float64(n)
    for i in range(n):
        rank.append(init_val)
        new_rank.append(0.0)

    for _ in range(max_iter):
        var base = (1.0 - damping) / Float64(n)
        for i in range(n):
            new_rank[i] = base
        for i in range(n):
            var deg = len(adj[i])
            if deg > 0:
                var share = rank[i] / Float64(deg)
                for j in range(deg):
                    var nb = adj[i][j]
                    new_rank[nb] += damping * share
        # Check convergence
        var diff = 0.0
        for i in range(n):
            diff += fabs(new_rank[i] - rank[i])
        for i in range(n):
            rank[i] = new_rank[i]
        if diff < tol:
            break
    return rank^


# ── degree_centrality ─────────────────────────────────────────────────────────


fn degree_centrality(adj: List[List[Int]]) -> List[Float64]:
    """Degree centrality: degree(v) / (n-1)."""
    var n = len(adj)
    var result = List[Float64]()
    if n <= 1:
        for i in range(n):
            result.append(0.0)
        return result^
    var denom = Float64(n - 1)
    for i in range(n):
        result.append(Float64(len(adj[i])) / denom)
    return result^


# ── closeness_centrality ─────────────────────────────────────────────────────


fn closeness_centrality(adj: List[List[Int]]) -> List[Float64]:
    """Closeness centrality: (n-1) / sum(distances). 0 if disconnected."""
    var n = len(adj)
    var result = List[Float64]()
    if n <= 1:
        for i in range(n):
            result.append(0.0)
        return result^
    for i in range(n):
        var dist = bfs_distances(adj, i)
        var total = 0
        var reachable = 0
        for j in range(n):
            if j != i and dist[j] >= 0:
                total += dist[j]
                reachable += 1
        if total > 0 and reachable == n - 1:
            result.append(Float64(n - 1) / Float64(total))
        else:
            result.append(0.0)
    return result^


# ── _has_edge (helper) ────────────────────────────────────────────────────────


fn _has_edge(adj: List[List[Int]], u: Int, v: Int) -> Bool:
    """Check if edge (u, v) exists."""
    var ncount = len(adj[u])
    for i in range(ncount):
        if adj[u][i] == v:
            return True
    return False


# ── clustering_coefficient ────────────────────────────────────────────────────


fn clustering_coefficient(adj: List[List[Int]], node: Int) -> Float64:
    """Local clustering coefficient: triangles / possible triangles."""
    var k = len(adj[node])
    if k < 2:
        return 0.0
    var triangles = 0
    for i in range(k):
        for j in range(i + 1, k):
            if _has_edge(adj, adj[node][i], adj[node][j]):
                triangles += 1
    var possible = k * (k - 1) // 2
    return Float64(triangles) / Float64(possible)


# ── avg_clustering_coefficient ────────────────────────────────────────────────


fn avg_clustering_coefficient(adj: List[List[Int]]) -> Float64:
    """Average clustering coefficient across all nodes."""
    var n = len(adj)
    if n == 0:
        return 0.0
    var total = 0.0
    for i in range(n):
        total += clustering_coefficient(adj, i)
    return total / Float64(n)


# ── is_connected ──────────────────────────────────────────────────────────────


fn is_connected(adj: List[List[Int]]) -> Bool:
    """Check if graph is connected (BFS from node 0 reaches all)."""
    var n = len(adj)
    if n == 0:
        return True
    var dist = bfs_distances(adj, 0)
    for i in range(n):
        if dist[i] == -1:
            return False
    return True


# ── connected_components ──────────────────────────────────────────────────────


fn connected_components(adj: List[List[Int]]) -> List[List[Int]]:
    """Find all connected components (list of node lists)."""
    var n = len(adj)
    var visited = List[Bool]()
    for i in range(n):
        visited.append(False)
    var components = List[List[Int]]()
    for i in range(n):
        if not visited[i]:
            var dist = bfs_distances(adj, i)
            var comp = List[Int]()
            for j in range(n):
                if dist[j] >= 0:
                    visited[j] = True
                    comp.append(j)
            components.append(comp^)
    return components^
