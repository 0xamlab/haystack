"""
graph_analytics — CSR adjacency and the traversals that need it. Zero Python.

What the tree has today, and why it is not enough
-------------------------------------------------
`graph/algorithms.mojo` and `graph/weighted.mojo` are the two graph surfaces in the
repo, and neither owns a reusable adjacency structure:

* `graph.algorithms.Graph` documents itself as "a flat list with an index array
  indicating where each node's edges begin and end" — a CSR — while its actual fields
  are `_adj_targets: List[List[Int]]` and `_adj_weights: List[List[Float64]]`, one
  heap allocation per node. The docstring describes a layout the struct does not have.
* `graph.weighted.shortest_path_dijkstra(n, edges, source)` takes a triplet edge list
  and *rebuilds* per-node adjacency lists on every call, then settles nodes with an
  O(V^2) scan rather than a priority queue. Two shortest-path queries on one graph pay
  for two rebuilds.
* that rebuild does `adj_dst[s].append(d)` with an unvalidated `s = edges[i].src`, so a
  single edge whose endpoint is `>= n` is not an error — it is a process crash.
* `graph.weighted.WeightedEdge{src, dst, weight}` is `sparse.COOEntry{row, col, val}`
  under a different name: a coordinate triplet, i.e. an assembly format, being used as
  if it were a query format.

Unreachability is the other gap. `floyd_warshall`, `bellman_ford`, `algorithms.dijkstra`
and `shortest_path_dijkstra` all report "no path" as the number `1e18`, which a caller
cannot distinguish from a real distance of `1e18` and which participates in arithmetic:
`1e18 + w` is still `1e18`, so a sentinel silently survives one more relaxation.

What this package adds
----------------------
A CSR adjacency built **once** and reused, and traversals over it that report absence as
absence. Nothing in `graph/` changes; it stays reachable, and this package is compared
against it in test — where both are valid the numbers must agree exactly.

Modules:
  adjacency — GraphCSR (row pointers, targets, weights, plus verified `sorted_targets`
        and `deduplicated` flags), construction from triplet arrays that *skips and
        counts* out-of-range endpoints instead of indexing with them, structural
        validation with one code per defect, the reverse graph, a min-weight
        canonicaliser, degree lists and the degree sequence, an edge query, a symmetry
        report, a dense image, and the traversals: Dijkstra over the frozen
        `heap.mojo` min-heap, BFS levels, and shortest-path reconstruction. Every
        traversal returns a `reached` mask alongside its numbers, so an unreachable node
        is flagged rather than handed a sentinel.
  centrality — betweenness by Brandes' algorithm over that CSR, unweighted (BFS) and
        weighted (Dijkstra), which is O(VE) rather than the O(V^3) of an all-pairs
        formulation and is the only producer of betweenness in the tree — the frozen
        `graph_algorithms.betweenness_centrality_norm` and
        `graph_decision.edge_criticality` both take one as an argument. Plus closeness
        (component-local, with the reachable count returned instead of a zero),
        harmonic centrality, degree centrality over distinct neighbours, eigenvector
        centrality via the frozen `linalg_ext.mat_power_iteration` on a spectrally
        shifted dense adjacency, and PageRank via the frozen `network_analysis.pagerank`
        on a graph augmented so its dangling-mass leak cannot occur.

Public functions take and return only `List`/`Int`/`Float64`/`Bool`/`String` or a
return-only struct declared in the same file, so the package lands in the runtime
library contract without a new message type. It is therefore *not* in
`_SKIP_RUNTIME_DIRS`.
"""
