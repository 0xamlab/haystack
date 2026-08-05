"""
weighted.mojo — Weighted graph algorithms. Zero Python imports.

Replaces networkx weighted-graph functionality with pure Mojo
implementations of Kruskal MST, Floyd-Warshall, Bellman-Ford,
Dijkstra, and Union-Find.

Public API:
  struct WeightedEdge     — edge with src, dst, weight
  kruskal_mst             — minimum spanning tree (Kruskal)
  mst_total_weight        — sum of MST edge weights
  floyd_warshall          — all-pairs shortest paths
  bellman_ford            — single-source shortest paths (negative ok)
  has_negative_cycle      — detect negative weight cycles
  shortest_path_dijkstra  — Dijkstra single-source shortest paths
  union_find_create       — create parent array
  union_find_find         — find with path compression
  union_find_union        — union by rank
"""


# ── Constants ────────────────────────────────────────────────────────────────


comptime INF: Float64 = 1e18


# ── WeightedEdge ─────────────────────────────────────────────────────────────


struct WeightedEdge(Copyable, Movable):
    """A weighted edge from src to dst."""

    var src: Int
    var dst: Int
    var weight: Float64

    fn __init__(out self, src: Int, dst: Int, weight: Float64):
        self.src = src
        self.dst = dst
        self.weight = weight


fn _edges_valid(n: Int, edges: List[WeightedEdge]) -> Bool:
    """True when n >= 0 and every edge endpoint lies in [0, n).

    Endpoint values are used directly as indices into dist/parent arrays; an
    out-of-range one is an uncatchable out-of-bounds abort.
    """
    if n < 0:
        return False
    for i in range(len(edges)):
        if edges[i].src < 0 or edges[i].src >= n or edges[i].dst < 0 or edges[i].dst >= n:
            return False
    return True


# ── Union-Find ───────────────────────────────────────────────────────────────


fn union_find_create(n: Int) -> List[Int]:
    """Create Union-Find parent array (each node is its own parent)."""
    var parent = List[Int]()
    for i in range(n):
        parent.append(i)
    return parent^


fn union_find_find(mut parent: List[Int], x: Int) -> Int:
    """Find root with path compression."""
    if x < 0 or x >= len(parent):
        return -1
    # A malformed parent array (out-of-range link or cycle) would abort or
    # recurse forever below; walk the chain once to prove it terminates.
    var cur = x
    var steps = 0
    while parent[cur] != cur:
        cur = parent[cur]
        if cur < 0 or cur >= len(parent):
            return -1
        steps += 1
        if steps > len(parent):
            return -1
    if parent[x] != x:
        parent[x] = union_find_find(parent, parent[x])
    return parent[x]


fn union_find_union(mut parent: List[Int], x: Int, y: Int) -> Bool:
    """Union two sets. Returns True if they were in different sets."""
    var rx = union_find_find(parent, x)
    var ry = union_find_find(parent, y)
    if rx < 0 or ry < 0:
        return False
    if rx == ry:
        return False
    parent[ry] = rx
    return True


# ── _sort_edges (insertion sort by weight) ───────────────────────────────────


fn _sort_edges(mut edges: List[WeightedEdge]):
    """Sort edges by weight using insertion sort."""
    var n = len(edges)
    for i in range(1, n):
        var key_src = edges[i].src
        var key_dst = edges[i].dst
        var key_w = edges[i].weight
        var j = i - 1
        while j >= 0 and edges[j].weight > key_w:
            edges[j + 1] = WeightedEdge(edges[j].src, edges[j].dst, edges[j].weight)
            j -= 1
        edges[j + 1] = WeightedEdge(key_src, key_dst, key_w)


# ── kruskal_mst ──────────────────────────────────────────────────────────────


fn kruskal_mst(n_nodes: Int, edges: List[WeightedEdge]) -> List[WeightedEdge]:
    """Kruskal's MST using Union-Find. Returns MST edges."""
    if n_nodes <= 0 or not _edges_valid(n_nodes, edges):
        return List[WeightedEdge]()
    var sorted_edges = List[WeightedEdge]()
    for i in range(len(edges)):
        sorted_edges.append(WeightedEdge(edges[i].src, edges[i].dst, edges[i].weight))
    _sort_edges(sorted_edges)

    var parent = union_find_create(n_nodes)
    var mst = List[WeightedEdge]()
    for i in range(len(sorted_edges)):
        var s = sorted_edges[i].src
        var d = sorted_edges[i].dst
        var w = sorted_edges[i].weight
        if union_find_union(parent, s, d):
            mst.append(WeightedEdge(s, d, w))
            if len(mst) == n_nodes - 1:
                break
    return mst^


# ── mst_total_weight ─────────────────────────────────────────────────────────


fn mst_total_weight(mst_edges: List[WeightedEdge]) -> Float64:
    """Sum of MST edge weights."""
    var total: Float64 = 0.0
    for i in range(len(mst_edges)):
        total += mst_edges[i].weight
    return total


# ── floyd_warshall ───────────────────────────────────────────────────────────


fn floyd_warshall(n: Int, edges: List[WeightedEdge]) -> List[List[Float64]]:
    """All-pairs shortest paths. Returns n×n distance matrix."""
    if not _edges_valid(n, edges):
        return List[List[Float64]]()
    var dist = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            if i == j:
                row.append(0.0)
            else:
                row.append(INF)
        dist.append(row^)

    for i in range(len(edges)):
        var s = edges[i].src
        var d = edges[i].dst
        var w = edges[i].weight
        if w < dist[s][d]:
            dist[s][d] = w

    for k in range(n):
        for i in range(n):
            for j in range(n):
                var via = dist[i][k] + dist[k][j]
                if via < dist[i][j]:
                    dist[i][j] = via
    return dist^


# ── bellman_ford ─────────────────────────────────────────────────────────────


fn bellman_ford(
    n: Int, edges: List[WeightedEdge], source: Int
) -> List[Float64]:
    """Single-source shortest paths allowing negative edges."""
    if not _edges_valid(n, edges) or source < 0 or source >= n:
        return List[Float64]()
    var dist = List[Float64]()
    for _ in range(n):
        dist.append(INF)
    dist[source] = 0.0
    var ne = len(edges)

    for _ in range(n - 1):
        for j in range(ne):
            var s = edges[j].src
            var d = edges[j].dst
            var w = edges[j].weight
            if dist[s] < INF:
                var nd = dist[s] + w
                if nd < dist[d]:
                    dist[d] = nd
    return dist^


# ── has_negative_cycle ───────────────────────────────────────────────────────


fn has_negative_cycle(n: Int, edges: List[WeightedEdge]) -> Bool:
    """Check for negative weight cycles using Bellman-Ford from node 0."""
    if not _edges_valid(n, edges):
        return False
    var dist = List[Float64]()
    for _ in range(n):
        dist.append(INF)
    if n > 0:
        dist[0] = 0.0
    var ne = len(edges)

    for _ in range(n - 1):
        for j in range(ne):
            var s = edges[j].src
            var d = edges[j].dst
            var w = edges[j].weight
            if dist[s] < INF:
                var nd = dist[s] + w
                if nd < dist[d]:
                    dist[d] = nd

    for j in range(ne):
        var s = edges[j].src
        var d = edges[j].dst
        var w = edges[j].weight
        if dist[s] < INF:
            if dist[s] + w < dist[d]:
                return True
    return False


# ── shortest_path_dijkstra ───────────────────────────────────────────────────


fn shortest_path_dijkstra(
    n: Int, edges: List[WeightedEdge], source: Int
) -> List[Float64]:
    """Dijkstra's algorithm for non-negative weights.
    Uses simple O(V^2) scan instead of a priority queue."""
    if not _edges_valid(n, edges) or source < 0 or source >= n:
        return List[Float64]()
    var adj_dst = List[List[Int]]()
    var adj_wt = List[List[Float64]]()
    for _ in range(n):
        adj_dst.append(List[Int]())
        adj_wt.append(List[Float64]())
    for i in range(len(edges)):
        var s = edges[i].src
        var d = edges[i].dst
        var w = edges[i].weight
        adj_dst[s].append(d)
        adj_wt[s].append(w)

    var dist = List[Float64]()
    var visited = List[Bool]()
    for _ in range(n):
        dist.append(INF)
        visited.append(False)
    dist[source] = 0.0

    for _ in range(n):
        var u = -1
        var best = INF
        for v in range(n):
            if not visited[v] and dist[v] < best:
                best = dist[v]
                u = v
        if u == -1:
            break
        visited[u] = True
        var ne = len(adj_dst[u])
        for j in range(ne):
            var v = adj_dst[u][j]
            var nd = dist[u] + adj_wt[u][j]
            if nd < dist[v]:
                dist[v] = nd
    return dist^
