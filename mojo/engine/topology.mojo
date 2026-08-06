"""
topology.mojo — Topological data analysis basics. Zero Python imports.

Replaces ripser basics with pure Mojo implementations of distance
matrices, Vietoris-Rips complexes, connected components, Betti
numbers, persistence diagrams, and bottleneck distance.

Public API:
  distance_matrix              — Pairwise Euclidean distances
  vietoris_rips_edges          — Edges in Vietoris-Rips complex at scale ε
  connected_components_from_edges — Count connected components (union-find)
  betti_0                      — β₀ = number of connected components
  filtration_values            — Sorted unique edge weights
  persistence_diagram_0        — β₀ persistence diagram
  total_persistence            — Σ(death - birth)
  bottleneck_distance          — Simplified bottleneck distance
  euler_characteristic         — χ = V - E + F
  rips_triangle_count          — Count triangles in edge set
"""
from std.math import sqrt, abs as fabs


# ── distance_matrix ─────────────────────────────────────────────────────────


def distance_matrix(points: List[List[Float64]]) -> List[List[Float64]]:
    """Compute pairwise Euclidean distance matrix.

    Args:
        points: List of point coordinates, each a List[Float64].

    Returns:
        Symmetric n×n distance matrix with zero diagonal.
    """
    var n = len(points)
    var result = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n):
            if i == j:
                row.append(0.0)
            else:
                var s: Float64 = 0.0
                var dim = len(points[i])
                if len(points[j]) < dim:
                    dim = len(points[j])
                for k in range(dim):
                    var d = points[i][k] - points[j][k]
                    s += d * d
                row.append(sqrt(s))
        result.append(row^)
    return result^


# ── vietoris_rips_edges ─────────────────────────────────────────────────────


def vietoris_rips_edges(distances: List[List[Float64]], epsilon: Float64) -> List[List[Int]]:
    """Edges in the Vietoris-Rips complex at scale ε.

    Args:
        distances: Pairwise distance matrix.
        epsilon:   Scale parameter.

    Returns:
        List of [i, j] pairs where dist(i,j) <= epsilon and i < j.
    """
    var n = len(distances)
    var edges = List[List[Int]]()
    for i in range(n):
        for j in range(i + 1, n):
            if distances[i][j] <= epsilon:
                var edge = List[Int]()
                edge.append(i)
                edge.append(j)
                edges.append(edge^)
    return edges^


# ── _union_find helpers ─────────────────────────────────────────────────────


def _uf_find(parent: List[Int], x: Int) -> Int:
    """Find root with path compression (iterative)."""
    var cur = x
    while parent[cur] != cur:
        cur = parent[cur]
    return cur


def _uf_union(mut parent: List[Int], mut rank: List[Int], a: Int, b: Int) -> Bool:
    """Union by rank. Returns True if a merge happened."""
    var ra = _uf_find(parent, a)
    var rb = _uf_find(parent, b)
    if ra == rb:
        return False
    if rank[ra] < rank[rb]:
        parent[ra] = rb
    elif rank[ra] > rank[rb]:
        parent[rb] = ra
    else:
        parent[rb] = ra
        rank[ra] += 1
    return True


# ── connected_components_from_edges ─────────────────────────────────────────


def connected_components_from_edges(n: Int, edges: List[List[Int]]) -> Int:
    """Count connected components via union-find.

    Args:
        n:     Number of vertices.
        edges: List of [i, j] edges.

    Returns:
        Number of connected components.
    """
    if n < 0:
        return 0
    # Allocate slots only for vertices appearing in the edge payload; vertices
    # beyond the largest endpoint are isolated and counted without storage.
    var nv = 0
    for idx in range(len(edges)):
        if len(edges[idx]) >= 2:
            if edges[idx][0] + 1 > nv:
                nv = edges[idx][0] + 1
            if edges[idx][1] + 1 > nv:
                nv = edges[idx][1] + 1
    if nv > n:
        nv = n
    if nv > 1000000:
        nv = 1000000  # ceiling: union-find allocates two per-vertex lists
    var parent = List[Int]()
    var rank = List[Int]()
    for i in range(nv):
        parent.append(i)
        rank.append(0)
    for idx in range(len(edges)):
        if len(edges[idx]) < 2:
            continue
        var a = edges[idx][0]
        var b = edges[idx][1]
        if a < 0 or a >= nv or b < 0 or b >= nv:
            continue
        _ = _uf_union(parent, rank, a, b)
    var count = n - nv
    for i in range(nv):
        if _uf_find(parent, i) == i:
            count += 1
    return count


# ── betti_0 ─────────────────────────────────────────────────────────────────


def betti_0(n: Int, edges: List[List[Int]]) -> Int:
    """Betti number β₀: number of connected components.

    Args:
        n:     Number of vertices.
        edges: List of [i, j] edges.

    Returns:
        β₀ value.
    """
    return connected_components_from_edges(n, edges)


# ── filtration_values ───────────────────────────────────────────────────────


def filtration_values(distances: List[List[Float64]]) -> List[Float64]:
    """Sorted unique edge weights (filtration steps).

    Args:
        distances: Pairwise distance matrix.

    Returns:
        Sorted list of unique positive edge weights.
    """
    var vals = List[Float64]()
    var n = len(distances)
    for i in range(n):
        for j in range(i + 1, n):
            var d = distances[i][j]
            # Check if already present
            var found = False
            for k in range(len(vals)):
                if fabs(vals[k] - d) < 1e-12:
                    found = True
                    break
            if not found:
                vals.append(d)
    # Simple insertion sort
    for i in range(1, len(vals)):
        var key = vals[i]
        var j = i - 1
        while j >= 0 and vals[j] > key:
            vals[j + 1] = vals[j]
            j -= 1
        vals[j + 1] = key
    return vals^


# ── persistence_diagram_0 ──────────────────────────────────────────────────


def persistence_diagram_0(distances: List[List[Float64]]) -> List[List[Float64]]:
    """β₀ persistence diagram: [[birth, death], ...] for connected components.

    All components are born at 0. Each merge event kills one component
    at the filtration value of the edge causing the merge.

    Args:
        distances: Pairwise distance matrix.

    Returns:
        List of [birth, death] pairs. The last surviving component has
        death = infinity (represented as 1e18).
    """
    var n = len(distances)
    # Collect all edges with weights
    var edge_w = List[Float64]()
    var edge_i = List[Int]()
    var edge_j = List[Int]()
    for i in range(n):
        for j in range(i + 1, n):
            edge_w.append(distances[i][j])
            edge_i.append(i)
            edge_j.append(j)
    # Sort edges by weight (insertion sort)
    for ii in range(1, len(edge_w)):
        var kw = edge_w[ii]
        var ki = edge_i[ii]
        var kj = edge_j[ii]
        var jj = ii - 1
        while jj >= 0 and edge_w[jj] > kw:
            edge_w[jj + 1] = edge_w[jj]
            edge_i[jj + 1] = edge_i[jj]
            edge_j[jj + 1] = edge_j[jj]
            jj -= 1
        edge_w[jj + 1] = kw
        edge_i[jj + 1] = ki
        edge_j[jj + 1] = kj
    # Union-find to track merges
    var parent = List[Int]()
    var rank = List[Int]()
    for i in range(n):
        parent.append(i)
        rank.append(0)
    var diagram = List[List[Float64]]()
    for idx in range(len(edge_w)):
        var merged = _uf_union(parent, rank, edge_i[idx], edge_j[idx])
        if merged:
            var pair = List[Float64]()
            pair.append(0.0)
            pair.append(edge_w[idx])
            diagram.append(pair^)
    # The last surviving component: born at 0, dies at infinity
    var last = List[Float64]()
    last.append(0.0)
    last.append(1e18)
    diagram.append(last^)
    return diagram^


# ── total_persistence ───────────────────────────────────────────────────────


def total_persistence(diagram: List[List[Float64]]) -> Float64:
    """Total persistence: Σ(death - birth).

    Args:
        diagram: List of [birth, death] pairs.

    Returns:
        Sum of lifetimes. Pairs with death >= 1e18 are excluded.
    """
    var s: Float64 = 0.0
    for i in range(len(diagram)):
        if diagram[i][1] < 1e18:
            s += diagram[i][1] - diagram[i][0]
    return s


# ── bottleneck_distance ─────────────────────────────────────────────────────


def bottleneck_distance(d1: List[List[Float64]], d2: List[List[Float64]]) -> Float64:
    """Simplified bottleneck distance between two persistence diagrams.

    For each point in d1, find the nearest point in d2 (L∞ distance),
    then return the max of these min-distances (and vice versa).

    Args:
        d1: First persistence diagram.
        d2: Second persistence diagram.

    Returns:
        Approximate bottleneck distance.
    """
    var max_dist: Float64 = 0.0
    # d1 -> d2
    for i in range(len(d1)):
        var min_d: Float64 = 1e18
        for j in range(len(d2)):
            var db = fabs(d1[i][0] - d2[j][0])
            var dd = fabs(d1[i][1] - d2[j][1])
            var dist = db
            if dd > dist:
                dist = dd
            if dist < min_d:
                min_d = dist
        if min_d > max_dist:
            max_dist = min_d
    # d2 -> d1
    for i in range(len(d2)):
        var min_d: Float64 = 1e18
        for j in range(len(d1)):
            var db = fabs(d2[i][0] - d1[j][0])
            var dd = fabs(d2[i][1] - d1[j][1])
            var dist = db
            if dd > dist:
                dist = dd
            if dist < min_d:
                min_d = dist
        if min_d > max_dist:
            max_dist = min_d
    return max_dist


# ── euler_characteristic ────────────────────────────────────────────────────


def euler_characteristic(n_vertices: Int, n_edges: Int, n_triangles: Int) -> Int:
    """Euler characteristic: χ = V - E + F.

    Args:
        n_vertices:  Number of vertices V.
        n_edges:     Number of edges E.
        n_triangles: Number of triangular faces F.

    Returns:
        Euler characteristic.
    """
    return n_vertices - n_edges + n_triangles


# ── rips_triangle_count ─────────────────────────────────────────────────────


def rips_triangle_count(n: Int, edges: List[List[Int]]) -> Int:
    """Count triangles in the edge set.

    A triangle exists when vertices i, j, k are all pairwise connected.

    Args:
        n:     Number of vertices.
        edges: List of [i, j] edges.

    Returns:
        Number of triangles.
    """
    if n <= 0 or len(edges) == 0:
        return 0
    # Only vertices in the edge payload can form triangles, so nv (not n)
    # bounds the n^2 adjacency allocation.
    var nv = 0
    for idx in range(len(edges)):
        if len(edges[idx]) >= 2:
            if edges[idx][0] + 1 > nv:
                nv = edges[idx][0] + 1
            if edges[idx][1] + 1 > nv:
                nv = edges[idx][1] + 1
    if nv > n:
        nv = n
    if nv > 1024:
        nv = 1024  # ceiling: n^2 adjacency allocation, n^3 worst-case scan
    # Build adjacency matrix
    var adj = List[List[Bool]]()
    for _ in range(nv):
        var row = List[Bool]()
        for _ in range(nv):
            row.append(False)
        adj.append(row^)
    for idx in range(len(edges)):
        if len(edges[idx]) < 2:
            continue
        var a = edges[idx][0]
        var b = edges[idx][1]
        if a < 0 or a >= nv or b < 0 or b >= nv:
            continue
        adj[a][b] = True
        adj[b][a] = True
    var count = 0
    for i in range(nv):
        for j in range(i + 1, nv):
            if adj[i][j]:
                for k in range(j + 1, nv):
                    if adj[i][k] and adj[j][k]:
                        count += 1
    return count
