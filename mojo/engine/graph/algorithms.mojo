"""
algorithms.mojo — Graph algorithms. Zero Python imports.

Adjacency list representation with weighted directed edges.

Public API:
  struct Graph(Copyable, Movable) — directed weighted graph
  fn graph_new(n: Int) -> Graph
  fn graph_add_edge(mut g: Graph, from_node: Int, to_node: Int, weight: Float64)
  fn dijkstra(g: Graph, source: Int) -> List[Float64]
  fn bfs(g: Graph, source: Int) -> List[Int]
  fn dfs(g: Graph, source: Int) -> List[Int]
  fn topological_sort(g: Graph) -> List[Int]
  fn connected_components(g: Graph) -> List[Int]
  fn shortest_path(g: Graph, source: Int, target: Int) -> List[Int]
"""


# ── Edge ──────────────────────────────────────────────────────────────────────


struct Edge(Copyable, Movable):
    """A weighted directed edge."""

    var target: Int
    var weight: Float64

    fn __init__(out self, target: Int, weight: Float64):
        self.target = target
        self.weight = weight


# ── Graph ─────────────────────────────────────────────────────────────────────


struct Graph(Copyable, Movable):
    """Directed weighted graph using adjacency lists.

    Edges are stored as a flat list with an index array indicating where
    each node's edges begin and end, for cache-friendly access.
    For simplicity, we use List[List[Edge]] style via parallel flat lists
    with a per-node edge list approach.
    """

    var n_nodes: Int
    # Adjacency list: for each node, store lists of targets and weights
    var _adj_targets: List[List[Int]]
    var _adj_weights: List[List[Float64]]

    fn __init__(out self, n: Int):
        self.n_nodes = n
        self._adj_targets = List[List[Int]]()
        self._adj_weights = List[List[Float64]]()
        for _ in range(n):
            self._adj_targets.append(List[Int]())
            self._adj_weights.append(List[Float64]())


# ── graph_new ─────────────────────────────────────────────────────────────────


fn graph_new(n: Int) -> Graph:
    """Create a new graph with n nodes (0-indexed)."""
    return Graph(n)


# ── graph_add_edge ────────────────────────────────────────────────────────────


fn graph_add_edge(mut g: Graph, from_node: Int, to_node: Int, weight: Float64):
    """Add a directed edge from from_node to to_node with given weight."""
    g._adj_targets[from_node].append(to_node)
    g._adj_weights[from_node].append(weight)


# ── Inline MinHeap for Dijkstra (stores (distance, node) pairs) ──────────────


struct _HeapEntry(Copyable, Movable):
    """A (distance, node) pair for the priority queue."""

    var dist: Float64
    var node: Int

    fn __init__(out self, dist: Float64, node: Int):
        self.dist = dist
        self.node = node


struct _DijkHeap:
    """Minimal binary min-heap for (distance, node) pairs.
    Compares by distance (Float64). Used only for Dijkstra."""

    var _dist: List[Float64]
    var _node: List[Int]

    fn __init__(out self):
        self._dist = List[Float64]()
        self._node = List[Int]()

    fn size(self) -> Int:
        return len(self._dist)

    fn push(mut self, dist: Float64, node: Int):
        self._dist.append(dist)
        self._node.append(node)
        self._sift_up(len(self._dist) - 1)

    fn pop(mut self) -> _HeapEntry:
        """Pop the minimum (distance, node) pair."""
        var n = len(self._dist)
        if n == 0:
            return _HeapEntry(0.0, -1)
        if n == 1:
            var d = self._dist[0]
            var nd = self._node[0]
            self._dist = List[Float64]()
            self._node = List[Int]()
            return _HeapEntry(d, nd)

        var d = self._dist[0]
        var nd = self._node[0]
        # Move last to root
        self._dist[0] = self._dist[n - 1]
        self._node[0] = self._node[n - 1]
        # Remove last
        var new_dist = List[Float64]()
        var new_node = List[Int]()
        for i in range(n - 1):
            new_dist.append(self._dist[i])
            new_node.append(self._node[i])
        self._dist = new_dist^
        self._node = new_node^
        self._sift_down(0)
        return _HeapEntry(d, nd)

    fn _sift_up(mut self, idx: Int):
        var i = idx
        while i > 0:
            var parent = (i - 1) // 2
            if self._dist[i] < self._dist[parent]:
                # Swap
                var td = self._dist[i]
                self._dist[i] = self._dist[parent]
                self._dist[parent] = td
                var tn = self._node[i]
                self._node[i] = self._node[parent]
                self._node[parent] = tn
                i = parent
            else:
                break

    fn _sift_down(mut self, idx: Int):
        var n = len(self._dist)
        var i = idx
        while True:
            var left = 2 * i + 1
            var right = 2 * i + 2
            var smallest = i
            if left < n and self._dist[left] < self._dist[smallest]:
                smallest = left
            if right < n and self._dist[right] < self._dist[smallest]:
                smallest = right
            if smallest != i:
                var td = self._dist[i]
                self._dist[i] = self._dist[smallest]
                self._dist[smallest] = td
                var tn = self._node[i]
                self._node[i] = self._node[smallest]
                self._node[smallest] = tn
                i = smallest
            else:
                break


# ── dijkstra ──────────────────────────────────────────────────────────────────


fn dijkstra(g: Graph, source: Int) -> List[Float64]:
    """Dijkstra's shortest path algorithm from source node.

    Returns a list of distances where dist[i] is the shortest distance
    from source to node i. Unreachable nodes have distance 1e18.
    """
    var INF: Float64 = 1e18
    var n = g.n_nodes
    var dist = List[Float64]()
    var visited = List[Bool]()
    for _ in range(n):
        dist.append(INF)
        visited.append(False)

    dist[source] = 0.0
    var heap = _DijkHeap()
    heap.push(0.0, source)

    while heap.size() > 0:
        var pair = heap.pop()
        var d = pair.dist
        var u = pair.node
        if visited[u]:
            continue
        visited[u] = True

        # Relax neighbors
        var num_edges = len(g._adj_targets[u])
        for i in range(num_edges):
            var v = g._adj_targets[u][i]
            var w = g._adj_weights[u][i]
            var new_dist = d + w
            if new_dist < dist[v]:
                dist[v] = new_dist
                heap.push(new_dist, v)

    return dist^


# ── bfs ───────────────────────────────────────────────────────────────────────


fn bfs(g: Graph, source: Int) -> List[Int]:
    """Breadth-first traversal order starting from source."""
    var n = g.n_nodes
    var visited = List[Bool]()
    for _ in range(n):
        visited.append(False)

    var order = List[Int]()
    # Simple queue using a list with a front pointer
    var queue = List[Int]()
    var front = 0

    visited[source] = True
    queue.append(source)

    while front < len(queue):
        var u = queue[front]
        front += 1
        order.append(u)

        var num_edges = len(g._adj_targets[u])
        for i in range(num_edges):
            var v = g._adj_targets[u][i]
            if not visited[v]:
                visited[v] = True
                queue.append(v)

    return order^


# ── dfs ───────────────────────────────────────────────────────────────────────


fn dfs(g: Graph, source: Int) -> List[Int]:
    """Depth-first traversal order starting from source (iterative)."""
    var n = g.n_nodes
    var visited = List[Bool]()
    for _ in range(n):
        visited.append(False)

    var order = List[Int]()
    var stack = List[Int]()
    stack.append(source)

    while len(stack) > 0:
        var u = stack[len(stack) - 1]
        # Pop from stack
        var new_stack = List[Int]()
        for i in range(len(stack) - 1):
            new_stack.append(stack[i])
        stack = new_stack^

        if visited[u]:
            continue
        visited[u] = True
        order.append(u)

        # Push neighbors in reverse order so we visit in forward order
        var num_edges = len(g._adj_targets[u])
        for i in range(num_edges - 1, -1, -1):
            var v = g._adj_targets[u][i]
            if not visited[v]:
                stack.append(v)

    return order^


# ── topological_sort ──────────────────────────────────────────────────────────


fn topological_sort(g: Graph) -> List[Int]:
    """Topological sort of a DAG using Kahn's algorithm.

    Returns a valid topological ordering. If the graph has cycles,
    returns a partial ordering (nodes involved in cycles are omitted).
    """
    var n = g.n_nodes

    # Compute in-degrees
    var in_degree = List[Int]()
    for _ in range(n):
        in_degree.append(0)

    for u in range(n):
        var num_edges = len(g._adj_targets[u])
        for i in range(num_edges):
            var v = g._adj_targets[u][i]
            in_degree[v] = in_degree[v] + 1

    # Queue of nodes with in-degree 0
    var queue = List[Int]()
    var front = 0
    for i in range(n):
        if in_degree[i] == 0:
            queue.append(i)

    var order = List[Int]()
    while front < len(queue):
        var u = queue[front]
        front += 1
        order.append(u)

        var num_edges = len(g._adj_targets[u])
        for i in range(num_edges):
            var v = g._adj_targets[u][i]
            in_degree[v] = in_degree[v] - 1
            if in_degree[v] == 0:
                queue.append(v)

    return order^


# ── connected_components ──────────────────────────────────────────────────────


fn connected_components(g: Graph) -> List[Int]:
    """Find connected components treating the graph as undirected.

    Returns a list where result[i] is the component label (0-based)
    for node i.
    """
    var n = g.n_nodes
    var labels = List[Int]()
    for _ in range(n):
        labels.append(-1)

    # Build undirected adjacency by combining forward and reverse edges
    var undirected_targets = List[List[Int]]()
    for _ in range(n):
        undirected_targets.append(List[Int]())

    for u in range(n):
        var num_edges = len(g._adj_targets[u])
        for i in range(num_edges):
            var v = g._adj_targets[u][i]
            undirected_targets[u].append(v)
            undirected_targets[v].append(u)

    var component = 0
    for start in range(n):
        if labels[start] >= 0:
            continue
        # BFS from start
        var queue = List[Int]()
        var qfront = 0
        labels[start] = component
        queue.append(start)
        while qfront < len(queue):
            var u = queue[qfront]
            qfront += 1
            var num_adj = len(undirected_targets[u])
            for i in range(num_adj):
                var v = undirected_targets[u][i]
                if labels[v] < 0:
                    labels[v] = component
                    queue.append(v)
        component += 1

    return labels^


# ── shortest_path ─────────────────────────────────────────────────────────────


fn shortest_path(g: Graph, source: Int, target: Int) -> List[Int]:
    """Find the actual shortest path from source to target.

    Returns the sequence of nodes from source to target inclusive.
    Returns an empty list if target is unreachable.
    Uses Dijkstra with predecessor tracking.
    """
    var INF: Float64 = 1e18
    var n = g.n_nodes
    var dist = List[Float64]()
    var prev = List[Int]()
    var visited = List[Bool]()
    for _ in range(n):
        dist.append(INF)
        prev.append(-1)
        visited.append(False)

    dist[source] = 0.0
    var heap = _DijkHeap()
    heap.push(0.0, source)

    while heap.size() > 0:
        var pair = heap.pop()
        var d = pair.dist
        var u = pair.node
        if visited[u]:
            continue
        visited[u] = True

        if u == target:
            break

        var num_edges = len(g._adj_targets[u])
        for i in range(num_edges):
            var v = g._adj_targets[u][i]
            var w = g._adj_weights[u][i]
            var new_dist = d + w
            if new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                heap.push(new_dist, v)

    # Reconstruct path
    if dist[target] >= INF:
        return List[Int]()

    var path = List[Int]()
    var node = target
    while node >= 0:
        path.append(node)
        if node == source:
            break
        node = prev[node]

    # Reverse the path
    var reversed_path = List[Int]()
    for i in range(len(path) - 1, -1, -1):
        reversed_path.append(path[i])

    return reversed_path^
