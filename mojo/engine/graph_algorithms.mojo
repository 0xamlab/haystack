"""
graph_algorithms.mojo — Graph traversal and network analysis (networkx equivalent).
Zero Python imports.

Public API:
  dijkstra_relax                — edge relaxation for Dijkstra
  bellman_ford_relax            — Bellman-Ford edge update
  pagerank_update               — one PageRank iteration for a node
  betweenness_centrality_norm   — normalised betweenness
  clustering_coefficient        — local clustering coefficient
  degree_centrality             — node degree / (n-1)
  closeness_centrality          — 1 / average shortest path
  eigenvector_centrality_update — power iteration step
  modularity_contribution       — Newman-Girvan modularity term
  graph_density                 — edges / max possible edges
"""
from std.math import sqrt, log


fn dijkstra_relax(
    dist_u: Float64, edge_weight: Float64, dist_v: Float64
) -> Float64:
    """Dijkstra edge relaxation: dist[v] = min(dist[v], dist[u] + w).

    Args:
        dist_u: Current shortest distance to node u.
        edge_weight: Weight of edge u→v.
        dist_v: Current shortest distance to node v.

    Returns:
        Updated distance to v.
    """
    var candidate = dist_u + edge_weight
    if candidate < dist_v:
        return candidate
    return dist_v


fn bellman_ford_relax(
    dist_u: Float64, edge_weight: Float64, dist_v: Float64
) -> Float64:
    """Bellman-Ford edge relaxation (handles negative weights).

    Args:
        dist_u: Current distance to source node u.
        edge_weight: Edge weight (may be negative).
        dist_v: Current distance to destination v.

    Returns:
        Updated distance to v.
    """
    var candidate = dist_u + edge_weight
    if candidate < dist_v:
        return candidate
    return dist_v


fn pagerank_update(
    in_neighbor_pr: Float64, out_degree: Float64,
    damping: Float64, n_nodes: Float64
) -> Float64:
    """One PageRank contribution from a single in-neighbor.

    PR(v) += d × PR(u) / out_degree(u)  (sum over all u)

    Args:
        in_neighbor_pr: PageRank of in-neighbor u.
        out_degree: Out-degree of neighbor u.
        damping: Damping factor d (0.85 typical).
        n_nodes: Total number of nodes N.

    Returns:
        PageRank contribution from this in-neighbor.
    """
    var teleport = (1.0 - damping) / n_nodes
    if out_degree <= 0.0:
        return teleport
    return teleport + damping * in_neighbor_pr / out_degree


fn betweenness_centrality_norm(
    raw_betweenness: Float64, n_nodes: Float64, directed: Float64
) -> Float64:
    """Normalised betweenness centrality.

    BC_norm = BC / ((n-1)(n-2)) for directed, /2 for undirected

    Args:
        raw_betweenness: Raw betweenness count.
        n_nodes: Number of nodes.
        directed: 1.0 for directed graph, 0.0 for undirected.

    Returns:
        Normalised betweenness (0–1).
    """
    if n_nodes <= 2.0:
        return 0.0
    var norm = (n_nodes - 1.0) * (n_nodes - 2.0)
    if directed < 0.5:
        norm = norm / 2.0
    if norm <= 0.0:
        return 0.0
    return raw_betweenness / norm


fn clustering_coefficient(
    triangles: Float64, degree: Float64
) -> Float64:
    """Local clustering coefficient: 2T / (k(k-1)).

    Args:
        triangles: Number of triangles through the node.
        degree: Node degree k.

    Returns:
        Clustering coefficient (0–1).
    """
    if degree <= 1.0:
        return 0.0
    return 2.0 * triangles / (degree * (degree - 1.0))


fn degree_centrality(degree: Float64, n_nodes: Float64) -> Float64:
    """Degree centrality: k / (n-1).

    Args:
        degree: Node degree.
        n_nodes: Total nodes.

    Returns:
        Degree centrality (0–1).
    """
    if n_nodes <= 1.0:
        return 0.0
    return degree / (n_nodes - 1.0)


fn closeness_centrality(
    sum_shortest_paths: Float64, n_nodes: Float64
) -> Float64:
    """Closeness centrality: (n-1) / Σd(u,v).

    Args:
        sum_shortest_paths: Sum of shortest path lengths from node.
        n_nodes: Total reachable nodes.

    Returns:
        Closeness centrality.
    """
    if sum_shortest_paths <= 0.0:
        return 0.0
    return (n_nodes - 1.0) / sum_shortest_paths


fn eigenvector_centrality_update(
    neighbor_scores_sum: Float64, lambda_max: Float64
) -> Float64:
    """Power iteration step for eigenvector centrality.

    x_new = A×x_old / λ_max

    Args:
        neighbor_scores_sum: Sum of eigenvector centrality of neighbors.
        lambda_max: Current largest eigenvalue estimate.

    Returns:
        Updated centrality value (un-normalised).
    """
    if lambda_max <= 0.0:
        return neighbor_scores_sum
    return neighbor_scores_sum / lambda_max


fn modularity_contribution(
    edge_in_community: Float64, degree_u: Float64,
    degree_v: Float64, total_edges: Float64
) -> Float64:
    """Newman-Girvan modularity contribution for one edge.

    Q_ij = A_ij - k_i×k_j / (2m)  where m = total edges

    Args:
        edge_in_community: 1.0 if edge within community, 0.0 otherwise.
        degree_u: Degree of node u.
        degree_v: Degree of node v.
        total_edges: Total number of edges m.

    Returns:
        Modularity contribution from this pair.
    """
    if total_edges <= 0.0:
        return 0.0
    return edge_in_community - degree_u * degree_v / (2.0 * total_edges)


fn graph_density(n_edges: Float64, n_nodes: Float64, directed: Float64) -> Float64:
    """Graph density: E / (N(N-1)) for directed, ×2 for undirected.

    Args:
        n_edges: Number of edges.
        n_nodes: Number of nodes.
        directed: 1.0 = directed, 0.0 = undirected.

    Returns:
        Density (0–1).
    """
    if n_nodes <= 1.0:
        return 0.0
    var max_edges = n_nodes * (n_nodes - 1.0)
    if directed < 0.5:
        max_edges = max_edges / 2.0
    if max_edges <= 0.0:
        return 0.0
    return n_edges / max_edges
