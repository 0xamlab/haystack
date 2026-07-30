"""
graph_analytics.adjacency — CSR adjacency built once, traversed with the frozen heap.

Layout
------
`GraphCSR` is `row_ptr` (length `n_nodes + 1`), `targets` (length `n_edges`) and
`weights` (length `n_edges`). Node `u`'s out-edges occupy `[row_ptr[u], row_ptr[u+1])`.
This is what `graph.algorithms.Graph` says it is and is not: three allocations for the
whole graph instead of two per node, and a contiguous scan per node.

Two flags travel with the arrays: `sorted_targets` (each row's targets ascend) and
`deduplicated` (no `(u, v)` pair is stored twice). They are *verified* claims, set only
by the code that establishes them, never guessed — an inferred flag cannot tell "checked
and true" from "not checked", and `graph_csr_from_arrays` therefore claims neither.

Out-of-range endpoints are skipped and counted, never indexed
-------------------------------------------------------------
`graph.weighted.shortest_path_dijkstra` rebuilds adjacency with
`adj_dst[edges[i].src].append(...)` and no range test, so one edge with `src >= n` takes
down the worker: an out-of-range `List` read is not an exception, it is an uncatchable
crash, and inside the worker it presents to a client as a hang. Construction here tests
both endpoints of every triplet, drops the edge if either is outside `[0, n_nodes)`, and
reports the count in `GraphCSR.skipped_edges` and `GraphBuildResult.skipped_edges`. A
silently resized graph would be worse than the crash, so the node count is never widened
to fit a stray index.

Absence is a flag, not a magic number
-------------------------------------
Every frozen shortest-path kernel here reports "no path" as `1e18`
(`graph/weighted.mojo:25` `comptime INF: Float64 = 1e18`, and
`graph/algorithms.mojo:186` repeats it as a local). That value is a legal distance, it
compares as smaller than `1e19`, and `1e18 + w == 1e18` for small `w`, so it survives
relaxation and can be returned as if a path had been found. `GraphDistances` therefore
carries a `reached: List[Bool]` mask, a `settled_count` and an `unreachable_count`
alongside `distance`, and an unreached node's distance is `GRAPH_NO_DISTANCE = -1.0` —
impossible for a real shortest path, because Dijkstra rejects negative weights up front.
`GraphLevels` does the same with `GRAPH_NO_LEVEL = -1`.

Dijkstra's priority queue: the frozen heap plus a value-keyed bucket table
-------------------------------------------------------------------------
`heap.mojo` is a real O(log n) binary heap, but it stores a bare `Float64` — there is no
payload slot for the node id, and it *permutes* its list internally, so a positionally
parallel `List[Int]` cannot be kept in sync with it.

Packing `(distance, node)` into the single `Float64` was rejected, and this is the
precision limit: a `Float64` has 53 mantissa bits and a general distance already uses all
of them. Every packing (`d * n_nodes + node`, or stealing low mantissa bits) is exact only
for the special case where the scaled sum is an integer below 2^53; outside it the stored
key is a *perturbed* distance, which can reorder two distances that differ by less than
the stolen quantum and, worse, decodes to the wrong node id — node identity would be lost
silently, which is precisely the failure this module exists to prevent.

So identity is kept in an explicit index-tracking structure instead: the heap holds the
tentative distances, and `columnar.hash_index.HashIndex` (FNV-1a over the normalized
IEEE-754 bits) maps each distinct key to a bucket of node ids awaiting that key. The
recovery is *exact*, not approximate: the frozen heap only ever moves values, never
computes on them, so a popped key is bit-identical to the pushed one and hashes to the
same bucket. `HashIndex` normalizes `-0.0` and NaN, and weights are validated finite and
non-negative before the loop, so no NaN key can arise. Two nodes at the same distance
share one bucket and are drained LIFO — deterministic, and any tie order is a correct
Dijkstra order because the distances are equal. Cost: one bucket per distinct tentative
distance, O(E) memory, and O(1) expected lookup per pop, so the whole traversal is
O(E log E) instead of the frozen O(V^2).

A stale key (a node whose distance improved after being pushed) is discarded by the
`dist[node] != key` test — again exact float equality, valid because `key` is the same
bit pattern that was stored in `dist`.

Negative weights are rejected, not silently mishandled
------------------------------------------------------
Dijkstra is invalid with a negative edge: a settled node can still be improved, and the
answer it returns is wrong rather than absent. `graph_csr_dijkstra` scans the weights
first and returns `GRAPH_ERR_NEGATIVE_WEIGHT` with no numbers attached.
`graph.weighted.bellman_ford(n, edges, source)` is the frozen kernel for that case, and
`graph.weighted.has_negative_cycle` the frozen guard for the case Bellman-Ford cannot
answer either. Storing a negative weight in a `GraphCSR` is legal — the container is not
the algorithm — and `graph_csr_has_negative_weight` is the cheap pre-check.

Parallel edges and self-loops are kept, and counted
---------------------------------------------------
A duplicate `(u, v)` is a real multigraph edge (two roads between two towns), so
construction keeps both and reports `duplicate_edges`; a self-loop is kept and reported
as `self_loops`. Neither changes a Dijkstra answer — a non-negative self-loop can never
improve a distance, and the lighter of two parallel edges wins by relaxation — so the
traversals need no special case. `graph_csr_dedupe_min` is the explicit canonicaliser
that collapses parallel edges to their minimum weight and sets `deduplicated`; the
symmetry report and the dense image are defined on that canonical form so a parallel edge
cannot be counted twice.
"""
from std.math import abs as fabs, isinf, isnan

from columnar.hash_index import HashIndex
from heap import heap_pop_min, heap_push_min
from sparse_numerics.csr import (
    CSR_ERR_INDEX_OUT_OF_RANGE,
    CSR_ERR_INDPTR_LENGTH,
    CSR_ERR_INDPTR_NOT_MONOTONIC,
    CSR_ERR_INDPTR_START,
    CSR_ERR_INDPTR_TAIL,
    CSR_ERR_LENGTH_MISMATCH,
    CSR_OK,
    MAX_CSR_DIM,
    csr_validate_flat,
)
from sorting import counting_sort_int

# ── status codes ──────────────────────────────────────────────────────────────
# One code per structural defect: a caller holding a rejection needs to know which of
# its four arrays is wrong, and a single "invalid" code would send it to check all four.

comptime GRAPH_OK: Int = 0
comptime GRAPH_ERR_INVALID_DIMENSIONS: Int = 1
comptime GRAPH_ERR_LENGTH_MISMATCH: Int = 2
comptime GRAPH_ERR_ROWPTR_LENGTH: Int = 3
comptime GRAPH_ERR_ROWPTR_START: Int = 4
comptime GRAPH_ERR_ROWPTR_NOT_MONOTONIC: Int = 5
comptime GRAPH_ERR_ROWPTR_TAIL: Int = 6
comptime GRAPH_ERR_TARGET_OUT_OF_RANGE: Int = 7
comptime GRAPH_ERR_SOURCE_OUT_OF_RANGE: Int = 8
comptime GRAPH_ERR_TARGET_NODE_OUT_OF_RANGE: Int = 9
comptime GRAPH_ERR_EMPTY_GRAPH: Int = 10
comptime GRAPH_ERR_NEGATIVE_WEIGHT: Int = 11
comptime GRAPH_ERR_NON_FINITE_WEIGHT: Int = 12
comptime GRAPH_ERR_DENSE_TOO_LARGE: Int = 13

# ── absence markers ───────────────────────────────────────────────────────────
# `-1.0` cannot be a shortest-path distance: Dijkstra only runs on non-negative weights,
# so every real answer is `>= 0`. That makes an ignored `reached` flag a loud wrong
# answer instead of a quiet one, which `1e18` is not.

comptime GRAPH_NO_DISTANCE: Float64 = -1.0
comptime GRAPH_NO_LEVEL: Int = -1
comptime GRAPH_NO_PREDECESSOR: Int = -1

# A dense image is O(n^2); past this many cells the caller wanted a sparse answer and a
# multi-gigabyte allocation is not a service. Reported as a status, not truncated.
comptime GRAPH_MAX_DENSE_CELLS: Int = 4194304

# The node ceiling is sparse_numerics.csr's MAX_CSR_DIM, not a second number. A graph
# adjacency IS an n x n sparse matrix, so a graph that would be a rejected matrix must be
# a rejected graph — two ceilings would mean a graph that converts to a matrix the matrix
# side refuses.
#
# It has to exist at all because `row_ptr` holds one entry PER NODE regardless of how few
# edges there are: `graph_csr_empty(10**12)` is a structurally consistent empty graph and
# asks for an 8 TB allocation. Clamping negatives (which this did) is not a bound.
comptime GRAPH_MAX_NODES: Int = MAX_CSR_DIM


fn graph_status_name(code: Int) -> String:
    """Name for a status code, so a rejection surfaces the defect and not a bare number.
    """
    if code == GRAPH_OK:
        return "ok"
    if code == GRAPH_ERR_INVALID_DIMENSIONS:
        return "invalid_dimensions"
    if code == GRAPH_ERR_LENGTH_MISMATCH:
        return "parallel_arrays_length_mismatch"
    if code == GRAPH_ERR_ROWPTR_LENGTH:
        return "row_ptr_length_not_n_nodes_plus_one"
    if code == GRAPH_ERR_ROWPTR_START:
        return "row_ptr_does_not_start_at_zero"
    if code == GRAPH_ERR_ROWPTR_NOT_MONOTONIC:
        return "row_ptr_not_monotonic"
    if code == GRAPH_ERR_ROWPTR_TAIL:
        return "row_ptr_tail_not_n_edges"
    if code == GRAPH_ERR_TARGET_OUT_OF_RANGE:
        return "target_out_of_range"
    if code == GRAPH_ERR_SOURCE_OUT_OF_RANGE:
        return "source_out_of_range"
    if code == GRAPH_ERR_TARGET_NODE_OUT_OF_RANGE:
        return "target_node_out_of_range"
    if code == GRAPH_ERR_EMPTY_GRAPH:
        return "empty_graph"
    if code == GRAPH_ERR_NEGATIVE_WEIGHT:
        return "negative_weight_use_bellman_ford"
    if code == GRAPH_ERR_NON_FINITE_WEIGHT:
        return "non_finite_weight"
    if code == GRAPH_ERR_DENSE_TOO_LARGE:
        return "dense_image_too_large"
    return "unknown_status"


# ── GraphCSR ──────────────────────────────────────────────────────────────────


@fieldwise_init
struct GraphCSR(Copyable, Movable):
    """Directed weighted graph in compressed sparse row form.

    `skipped_edges` is provenance, not structure: how many input triplets could not be
    represented because an endpoint was outside `[0, n_nodes)`. It is carried on the
    graph so the count cannot be dropped on the floor between building and querying.

    The flags are claims and the arrays are the truth, so every entry point below
    validates the arrays before indexing them — a `GraphCSR` may arrive over the wire
    with any field values at all.
    """

    var row_ptr: List[Int]
    var targets: List[Int]
    var weights: List[Float64]
    var n_nodes: Int
    var sorted_targets: Bool
    var deduplicated: Bool
    var skipped_edges: Int

    fn n_edges(self) -> Int:
        """Stored out-edges, counting parallel edges and self-loops separately."""
        return len(self.targets)

    fn out_degree(self, node: Int) -> Int:
        """Out-edges of one node, or 0 for a node this graph does not have.

        0 rather than a negative span for a broken `row_ptr`: callers size loops with
        this, and a negative count there would read as "skip" in some places and index
        backwards in others.
        """
        if node < 0 or node + 1 >= len(self.row_ptr):
            return 0
        var span = self.row_ptr[node + 1] - self.row_ptr[node]
        if span < 0:
            return 0
        return span

    fn is_canonical(self) -> Bool:
        """Rows ascend and hold no repeated target — the form `dedupe_min` produces."""
        return self.sorted_targets and self.deduplicated


# ── return-only result structs ────────────────────────────────────────────────
# Declared here because the marshalling spec for a returned struct is parsed per file:
# returning a struct owned by another module drops the function from the runtime
# contract silently, with no error anywhere.


@fieldwise_init
struct GraphBuildResult(Copyable, Movable):
    """A built CSR crossing the flat driver boundary, with everything it dropped.

    The four count fields exist so a caller learns what its edge list actually contained
    without a second pass: `skipped_edges` is the edges that do not exist in this graph,
    and `negative_weights` is the pre-check that says "use bellman_ford, not dijkstra".
    """

    var status: Int
    var n_nodes: Int
    var n_edges: Int
    var skipped_edges: Int
    var self_loops: Int
    var duplicate_edges: Int
    var negative_weights: Int
    var non_finite_weights: Int
    var sorted_targets: Bool
    var deduplicated: Bool
    var row_ptr: List[Int]
    var targets: List[Int]
    var weights: List[Float64]


@fieldwise_init
struct GraphIntsResult(Copyable, Movable):
    """An Int vector plus status, so "no nodes" and "not a graph" stay distinguishable.

    A bare `List[Int]` makes both an empty list, and a caller cannot tell that its
    five-node graph was rejected for a broken `row_ptr`.
    """

    var status: Int
    var length: Int
    var values: List[Int]


@fieldwise_init
struct GraphVectorResult(Copyable, Movable):
    """A Float64 vector plus status and the shape it should be read with."""

    var status: Int
    var n_nodes: Int
    var length: Int
    var values: List[Float64]


@fieldwise_init
struct GraphDistances(Copyable, Movable):
    """Single-source distances, with reachability as data rather than as a sentinel.

    `reached[v]` is the authority. `distance[v]` is `GRAPH_NO_DISTANCE` wherever
    `reached[v]` is False, and `predecessor[v]` is `GRAPH_NO_PREDECESSOR` there and at
    the source. `settled_count + unreachable_count == n_nodes` whenever `status` is
    `GRAPH_OK`; on any other status all three lists are empty and the counts are 0,
    because a rejected request has no partial answer.
    """

    var status: Int
    var n_nodes: Int
    var source: Int
    var settled_count: Int
    var unreachable_count: Int
    var heap_pushes: Int
    var distance: List[Float64]
    var reached: List[Bool]
    var predecessor: List[Int]


@fieldwise_init
struct GraphLevels(Copyable, Movable):
    """BFS hop counts. `level[v]` is `GRAPH_NO_LEVEL` exactly where `reached[v]` is False.
    """

    var status: Int
    var n_nodes: Int
    var source: Int
    var reached_count: Int
    var unreachable_count: Int
    var max_level: Int
    var level: List[Int]
    var reached: List[Bool]


@fieldwise_init
struct GraphPath(Copyable, Movable):
    """One reconstructed shortest path. `found` is the authority.

    When `found` is False, `nodes` is empty, `hops` is 0 and `total_weight` is
    `GRAPH_NO_DISTANCE` — never a plausible partial path, which is what a truncated
    predecessor walk would look like.
    """

    var status: Int
    var found: Bool
    var source: Int
    var target: Int
    var hops: Int
    var total_weight: Float64
    var nodes: List[Int]


@fieldwise_init
struct GraphEdgeQuery(Copyable, Movable):
    """Whether `(u, v)` is an edge, how many copies there are, and the lightest weight.

    `multiplicity == 0` means there is no such edge, and then `weight` carries no answer
    at all. Unlike a distance there is no impossible weight to use as a marker — every
    `Float64` is a legal edge weight, and a NaN marker cannot cross a JSON frame — so the
    absence lives in `found`/`multiplicity` and `weight` is left at 0.0 deliberately.
    """

    var status: Int
    var found: Bool
    var multiplicity: Int
    var weight: Float64


@fieldwise_init
struct GraphSymmetry(Copyable, Movable):
    """Whether a directed CSR is the adjacency of an undirected graph.

    Evaluated on the min-weight canonical form, so a parallel edge is not counted twice.
    `structurally_symmetric` means every non-loop edge has a reverse;
    `weight_symmetric` additionally means the two weights agree within `tol`. The two
    counts say how badly, which a Bool cannot.
    """

    var status: Int
    var structurally_symmetric: Bool
    var weight_symmetric: Bool
    var missing_reverse: Int
    var weight_mismatch: Int
    var self_loops: Int
    var distinct_edges: Int


# ── constructors ──────────────────────────────────────────────────────────────


fn graph_csr_empty(n_nodes: Int) -> GraphCSR:
    """A graph with `n_nodes` nodes and no edges. Trivially sorted and deduplicated."""
    var n = n_nodes
    if n < 0 or n > GRAPH_MAX_NODES:
        # Above the ceiling, an "empty graph" is an allocation request, so refuse it the
        # same way a negative count is refused: return the 0-node graph rather than
        # attempting row_ptr of n+1 entries.
        n = 0
    var row_ptr = List[Int]()
    for _ in range(n + 1):
        row_ptr.append(0)
    return GraphCSR(row_ptr^, List[Int](), List[Float64](), n, True, True, 0)


fn _empty_with_skipped(n_nodes: Int, skipped: Int) -> GraphCSR:
    var n = n_nodes
    if n < 0:
        n = 0
    var row_ptr = List[Int]()
    for _ in range(n + 1):
        row_ptr.append(0)
    return GraphCSR(
        row_ptr^, List[Int](), List[Float64](), n, True, True, skipped
    )


fn graph_csr_from_arrays(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
) -> GraphCSR:
    """Wrap caller-supplied arrays. Neither flag is claimed and nothing is validated.

    Arrays arriving over the wire have unknown provenance, so claiming `sorted_targets`
    would let `dedupe_min` skip the sort it actually needs and silently keep a duplicate.
    Validate with `graph_csr_validate` before use; every driver here does.
    """
    return GraphCSR(
        row_ptr.copy(), targets.copy(), weights.copy(), n_nodes, False, False, 0
    )


fn graph_csr_from_triplets(
    src: List[Int], dst: List[Int], weight: List[Float64], n_nodes: Int
) -> GraphCSR:
    """CSR from parallel triplet arrays in one O(V + E) pass pair. Strays are skipped.

    Rows come out ascending by target without a comparison sort: the edges are first
    grouped by `dst` with a counting pass, then distributed by `src`, so each row
    receives its targets in ascending order. That is the counting-sort transpose trick
    `sparse_numerics.csr._transpose_unchecked` uses, applied twice.

    A length mismatch between the three arrays is not a graph: every candidate edge is
    counted in `skipped_edges` and the result has no edges. Use `graph_csr_build` when
    the caller needs to know *why* — a `GraphCSR` has nowhere to put a status.
    """
    var m = len(src)
    if len(dst) != m or len(weight) != m:
        var longest = m
        if len(dst) > longest:
            longest = len(dst)
        if len(weight) > longest:
            longest = len(weight)
        return _empty_with_skipped(n_nodes, longest)

    var n = n_nodes
    if n < 0:
        n = 0

    # Kept edges, by index, so no out-of-range endpoint is ever used as a subscript.
    var keep = List[Int]()
    for k in range(m):
        if src[k] >= 0 and src[k] < n and dst[k] >= 0 and dst[k] < n:
            keep.append(k)
    var skipped = m - len(keep)
    var kept = len(keep)

    if kept == 0:
        return _empty_with_skipped(n, skipped)

    # Pass 1: group kept edges by destination.
    var dst_count = List[Int]()
    for _ in range(n):
        dst_count.append(0)
    for i in range(kept):
        dst_count[dst[keep[i]]] += 1
    var dst_start = List[Int]()
    var running = 0
    for v in range(n):
        dst_start.append(running)
        running += dst_count[v]
    dst_start.append(running)
    var by_dst = List[Int]()
    for _ in range(kept):
        by_dst.append(0)
    var cursor = List[Int]()
    for v in range(n):
        cursor.append(dst_start[v])
    for i in range(kept):
        var k = keep[i]
        var pos = cursor[dst[k]]
        by_dst[pos] = k
        cursor[dst[k]] = pos + 1

    # Pass 2: distribute by source, walking the destination-ordered sequence, which is
    # what leaves every row ascending.
    var row_ptr = List[Int]()
    var out_count = List[Int]()
    for _ in range(n):
        out_count.append(0)
    for i in range(kept):
        out_count[src[by_dst[i]]] += 1
    running = 0
    for u in range(n):
        row_ptr.append(running)
        running += out_count[u]
    row_ptr.append(running)
    var fill = List[Int]()
    for u in range(n):
        fill.append(row_ptr[u])
    var targets = List[Int]()
    var weights = List[Float64]()
    for _ in range(kept):
        targets.append(0)
        weights.append(0.0)
    for i in range(kept):
        var k = by_dst[i]
        var pos = fill[src[k]]
        targets[pos] = dst[k]
        weights[pos] = weight[k]
        fill[src[k]] = pos + 1

    var deduplicated = True
    for u in range(n):
        for p in range(row_ptr[u] + 1, row_ptr[u + 1]):
            if targets[p] == targets[p - 1]:
                deduplicated = False
    return GraphCSR(
        row_ptr^, targets^, weights^, n, True, deduplicated, skipped
    )


# ── validation ────────────────────────────────────────────────────────────────


fn graph_csr_validate_flat(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
) -> Int:
    """`GRAPH_OK` for a structurally sound CSR, else the first defect's code.

    This is the single gate that makes everything below safe, and the checks are ordered
    so each one only indexes what its predecessors proved to exist. A `row_ptr` entry
    beyond `len(targets)` would turn an innocent `for k in range(row_ptr[u],
    row_ptr[u+1])` into a read past the end — an uncatchable process crash, not an
    exception. A zero head plus monotonicity plus a tail equal to `len(targets)` bound
    every entry to `[0, n_edges]`, so no separate range check on `row_ptr` is needed.
    """
    if n_nodes < 0 or n_nodes > GRAPH_MAX_NODES:
        return GRAPH_ERR_INVALID_DIMENSIONS

    # The structural checks are sparse_numerics.csr.csr_validate_flat's, not a second
    # copy of them. A graph adjacency in CSR is exactly an n x n sparse matrix in CSR:
    # row_ptr is indptr, targets are column indices, weights are values. This was
    # previously a line-for-line reimplementation, which meant the package could drift
    # into validating a graph and its own matrix form differently — and the matrix side
    # already grew a dimension ceiling that the graph side had missed.
    var code = csr_validate_flat(row_ptr, targets, weights, n_nodes, n_nodes)
    if code == CSR_OK:
        return GRAPH_OK
    # Translate to this module's vocabulary so callers keep getting graph-shaped errors
    # ("target out of range", not "column index out of range").
    if code == CSR_ERR_LENGTH_MISMATCH:
        return GRAPH_ERR_LENGTH_MISMATCH
    if code == CSR_ERR_INDPTR_LENGTH:
        return GRAPH_ERR_ROWPTR_LENGTH
    if code == CSR_ERR_INDPTR_START:
        return GRAPH_ERR_ROWPTR_START
    if code == CSR_ERR_INDPTR_NOT_MONOTONIC:
        return GRAPH_ERR_ROWPTR_NOT_MONOTONIC
    if code == CSR_ERR_INDPTR_TAIL:
        return GRAPH_ERR_ROWPTR_TAIL
    if code == CSR_ERR_INDEX_OUT_OF_RANGE:
        return GRAPH_ERR_TARGET_OUT_OF_RANGE
    return GRAPH_ERR_INVALID_DIMENSIONS


fn graph_csr_validate(g: GraphCSR) -> Int:
    """`GRAPH_OK` or the first defect's code. The flags are not checked: they are claims.
    """
    return graph_csr_validate_flat(g.row_ptr, g.targets, g.weights, g.n_nodes)


fn graph_csr_has_negative_weight(g: GraphCSR) -> Bool:
    """True if any stored weight is negative — i.e. Dijkstra does not apply here.

    False for a structurally broken graph too: there is no weight set to speak of, and
    `graph_csr_validate` is the call that says so.
    """
    if graph_csr_validate(g) != GRAPH_OK:
        return False
    for k in range(len(g.weights)):
        if g.weights[k] < 0.0:
            return True
    return False


fn _weight_defect(weights: List[Float64]) -> Int:
    """`GRAPH_OK`, or the code for the first weight Dijkstra cannot use.

    NaN is caught before the sign test on purpose: `nan < 0.0` is False, so a NaN weight
    would pass a bare negativity check and then poison every comparison downstream.
    """
    for k in range(len(weights)):
        var w = weights[k]
        if isnan(w) or isinf(w):
            return GRAPH_ERR_NON_FINITE_WEIGHT
        if w < 0.0:
            return GRAPH_ERR_NEGATIVE_WEIGHT
    return GRAPH_OK


# ── reverse graph and canonical form ──────────────────────────────────────────


fn graph_csr_reverse(g: GraphCSR) -> GraphCSR:
    """The graph with every edge reversed, in O(V + E) by counting sort.

    An invalid graph has no reverse, so the result is the 0-node empty graph rather than
    a best-effort structure that would look plausible two calls later.

    The result always has sorted targets even when `g` did not: source nodes are visited
    in ascending order, so each reversed row receives its entries ascending.
    `deduplicated` carries over because reversing a pair-unique edge set keeps it
    pair-unique.
    """
    if graph_csr_validate(g) != GRAPH_OK:
        return graph_csr_empty(0)
    var n = g.n_nodes
    var m = len(g.targets)

    var in_count = List[Int]()
    for _ in range(n):
        in_count.append(0)
    for k in range(m):
        in_count[g.targets[k]] += 1
    var row_ptr = List[Int]()
    var running = 0
    for v in range(n):
        row_ptr.append(running)
        running += in_count[v]
    row_ptr.append(running)

    var fill = List[Int]()
    for v in range(n):
        fill.append(row_ptr[v])
    var targets = List[Int]()
    var weights = List[Float64]()
    for _ in range(m):
        targets.append(0)
        weights.append(0.0)
    for u in range(n):
        for k in range(g.row_ptr[u], g.row_ptr[u + 1]):
            var v = g.targets[k]
            var pos = fill[v]
            targets[pos] = u
            weights[pos] = g.weights[k]
            fill[v] = pos + 1

    return GraphCSR(
        row_ptr^, targets^, weights^, n, True, g.deduplicated, g.skipped_edges
    )


fn graph_csr_sorted(g: GraphCSR) -> GraphCSR:
    """`g` with every row ascending by target, established rather than assumed.

    Reversing twice sorts, in O(V + E) with no comparison sort, and reuses one
    implementation instead of adding a second ordering path that could disagree with it.
    A graph that already claims `sorted_targets` is returned unchanged.
    """
    if graph_csr_validate(g) != GRAPH_OK:
        return graph_csr_empty(0)
    if g.sorted_targets:
        return g.copy()
    return graph_csr_reverse(graph_csr_reverse(g))


fn graph_csr_dedupe_min(g: GraphCSR) -> GraphCSR:
    """Collapse parallel edges to their minimum weight. Self-loops are kept, collapsed.

    Minimum, not sum: for a distance question two parallel roads are one road of the
    shorter length, and this is the form the traversals would reach anyway by
    relaxation. Sum would be the right rule for a capacity or multiplicity question,
    which is a different driver and not this one.
    """
    if graph_csr_validate(g) != GRAPH_OK:
        return graph_csr_empty(0)
    var work = graph_csr_sorted(g)
    var n = work.n_nodes
    var row_ptr = List[Int]()
    var targets = List[Int]()
    var weights = List[Float64]()
    row_ptr.append(0)
    for u in range(n):
        var begin = work.row_ptr[u]
        var end = work.row_ptr[u + 1]
        var k = begin
        while k < end:
            var v = work.targets[k]
            var best = work.weights[k]
            var j = k + 1
            while j < end and work.targets[j] == v:
                if work.weights[j] < best:
                    best = work.weights[j]
                j += 1
            targets.append(v)
            weights.append(best)
            k = j
        row_ptr.append(len(targets))
    return GraphCSR(
        row_ptr^, targets^, weights^, n, True, True, work.skipped_edges
    )


# ── degrees ───────────────────────────────────────────────────────────────────


fn graph_csr_out_degrees(g: GraphCSR) -> List[Int]:
    """Out-degree per node, or an empty list for a structurally invalid graph."""
    var out = List[Int]()
    if graph_csr_validate(g) != GRAPH_OK:
        return out^
    for u in range(g.n_nodes):
        out.append(g.row_ptr[u + 1] - g.row_ptr[u])
    return out^


fn graph_csr_in_degrees(g: GraphCSR) -> List[Int]:
    """In-degree per node, counted directly from `targets` — no reverse graph built."""
    var out = List[Int]()
    if graph_csr_validate(g) != GRAPH_OK:
        return out^
    for _ in range(g.n_nodes):
        out.append(0)
    for k in range(len(g.targets)):
        out[g.targets[k]] += 1
    return out^


fn graph_csr_degree_sequence(g: GraphCSR) -> List[Int]:
    """Out-degrees in descending order — the classic graph invariant, for comparison.

    Sorted by the frozen `sorting.counting_sort_int`, which is exactly right here:
    degrees are non-negative and bounded by the edge count, so counting sort is O(V + E)
    with no comparisons.
    """
    var degrees = graph_csr_out_degrees(g)
    var ascending = counting_sort_int(degrees)
    var out = List[Int]()
    var i = len(ascending) - 1
    while i >= 0:
        out.append(ascending[i])
        i -= 1
    return out^


# ── edge queries ──────────────────────────────────────────────────────────────


fn graph_csr_edge_min_weight(g: GraphCSR, u: Int, v: Int) -> GraphEdgeQuery:
    """Lightest `(u, v)` edge and how many copies exist.

    A sorted graph stops scanning as soon as the row passes `v`; an unsorted one has to
    read the whole row, which is why the flag is worth carrying.
    """
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return GraphEdgeQuery(status, False, 0, 0.0)
    if u < 0 or u >= g.n_nodes:
        return GraphEdgeQuery(GRAPH_ERR_SOURCE_OUT_OF_RANGE, False, 0, 0.0)
    if v < 0 or v >= g.n_nodes:
        return GraphEdgeQuery(GRAPH_ERR_TARGET_NODE_OUT_OF_RANGE, False, 0, 0.0)

    var count = 0
    var best: Float64 = 0.0
    for k in range(g.row_ptr[u], g.row_ptr[u + 1]):
        var t = g.targets[k]
        if t == v:
            if count == 0 or g.weights[k] < best:
                best = g.weights[k]
            count += 1
        elif g.sorted_targets and t > v:
            break
    if count == 0:
        return GraphEdgeQuery(GRAPH_OK, False, 0, 0.0)
    return GraphEdgeQuery(GRAPH_OK, True, count, best)


fn graph_csr_has_edge(g: GraphCSR, u: Int, v: Int) -> Bool:
    """True only when `(u, v)` really is an edge of a structurally valid graph."""
    var q = graph_csr_edge_min_weight(g, u, v)
    return q.status == GRAPH_OK and q.found


# ── symmetry ──────────────────────────────────────────────────────────────────


fn graph_csr_symmetry(g: GraphCSR, tol: Float64) -> GraphSymmetry:
    """Is this directed CSR the adjacency of an undirected graph, and if not, how far off.

    Canonicalised first, so two parallel copies of one edge are one edge and cannot
    inflate `missing_reverse`. A self-loop is its own reverse and is only counted.
    """
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return GraphSymmetry(status, False, False, 0, 0, 0, 0)
    var c = graph_csr_dedupe_min(g)
    var missing = 0
    var mismatch = 0
    var loops = 0
    var distinct = len(c.targets)
    for u in range(c.n_nodes):
        for k in range(c.row_ptr[u], c.row_ptr[u + 1]):
            var v = c.targets[k]
            if v == u:
                loops += 1
                continue
            var back = graph_csr_edge_min_weight(c, v, u)
            if not back.found:
                missing += 1
            elif fabs(back.weight - c.weights[k]) > tol:
                mismatch += 1
    return GraphSymmetry(
        GRAPH_OK, missing == 0, missing == 0 and mismatch == 0, missing,
        mismatch, loops, distinct,
    )


# ── dense image ───────────────────────────────────────────────────────────────


fn graph_csr_to_dense(g: GraphCSR, absent: Float64) -> GraphVectorResult:
    """Flat row-major `n_nodes * n_nodes` adjacency matrix, `absent` where there is no edge.

    The caller chooses `absent` because there is no universally right value: 0.0 for an
    adjacency matrix, a large number for a distance matrix. Parallel edges collapse to
    their minimum, matching `dedupe_min`, and a self-loop lands on the diagonal.

    Note the ambiguity the caller inherits and this driver cannot remove: with
    `absent = 0.0`, a stored edge of weight 0.0 is indistinguishable from no edge in the
    dense image. `graph_csr_edge_min_weight` is the query that keeps them apart.
    """
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return GraphVectorResult(status, 0, 0, List[Float64]())
    var n = g.n_nodes
    if n > 0 and n > GRAPH_MAX_DENSE_CELLS // n:
        return GraphVectorResult(GRAPH_ERR_DENSE_TOO_LARGE, n, 0, List[Float64]())
    var c = graph_csr_dedupe_min(g)
    var cells = n * n
    var values = List[Float64]()
    for _ in range(cells):
        values.append(absent)
    for u in range(n):
        for k in range(c.row_ptr[u], c.row_ptr[u + 1]):
            values[u * n + c.targets[k]] = c.weights[k]
    return GraphVectorResult(GRAPH_OK, n, cells, values^)


# ── Dijkstra ──────────────────────────────────────────────────────────────────


fn _no_distances(status: Int, n_nodes: Int, source: Int) -> GraphDistances:
    """No answer. Empty lists and zero counts, so an ignored status cannot be read as one.
    """
    return GraphDistances(
        status, n_nodes, source, 0, 0, 0, List[Float64](), List[Bool](), List[Int]()
    )


fn graph_csr_dijkstra(g: GraphCSR, source: Int) -> GraphDistances:
    """Single-source shortest distances over a prebuilt CSR, heap-ordered.

    Uses the frozen `heap.heap_push_min` / `heap_pop_min` for the ordering and a
    value-keyed bucket table for node identity — see the module docstring for why the
    `(distance, node)` pair is not packed into the heap's `Float64` and why the bucket
    recovery is exact rather than approximate.

    Rejects a negative weight instead of returning the wrong answer Dijkstra would
    produce: with a negative edge a settled node can still be improved.
    `graph.weighted.bellman_ford(n, edges, source)` is the frozen kernel for that case.

    An unreachable node is `reached[v] == False` and `distance[v] == GRAPH_NO_DISTANCE`,
    never `1e18` — which every frozen shortest-path kernel here returns and no caller can
    tell from a real distance.
    """
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return _no_distances(status, 0, source)
    var n = g.n_nodes
    if n == 0:
        return _no_distances(GRAPH_ERR_EMPTY_GRAPH, 0, source)
    if source < 0 or source >= n:
        return _no_distances(GRAPH_ERR_SOURCE_OUT_OF_RANGE, n, source)
    var defect = _weight_defect(g.weights)
    if defect != GRAPH_OK:
        return _no_distances(defect, n, source)

    var dist = List[Float64]()
    var pred = List[Int]()
    var known = List[Bool]()
    var settled = List[Bool]()
    for _ in range(n):
        dist.append(0.0)
        pred.append(GRAPH_NO_PREDECESSOR)
        known.append(False)
        settled.append(False)

    var heap = List[Float64]()
    var pending = HashIndex(64)
    var buckets = List[List[Int]]()
    var pushes = 0

    dist[source] = 0.0
    known[source] = True
    heap_push_min(heap, 0.0)
    var slot = pending.get_or_assign(0.0, len(buckets))
    if slot == len(buckets):
        buckets.append(List[Int]())
    buckets[slot].append(source)
    pushes += 1

    var settled_count = 0
    while len(heap) > 0:
        var key = heap_pop_min(heap)
        var bucket = pending.find(key)
        if bucket < 0:
            continue
        if len(buckets[bucket]) == 0:
            continue
        var node = buckets[bucket].pop()
        if settled[node]:
            continue
        # A stale key: this node's distance improved after this key was pushed, and the
        # better key is still in the heap.
        if dist[node] != key:
            continue
        settled[node] = True
        settled_count += 1
        for k in range(g.row_ptr[node], g.row_ptr[node + 1]):
            var v = g.targets[k]
            var nd = key + g.weights[k]
            if not known[v] or nd < dist[v]:
                known[v] = True
                dist[v] = nd
                pred[v] = node
                heap_push_min(heap, nd)
                var vslot = pending.get_or_assign(nd, len(buckets))
                if vslot == len(buckets):
                    buckets.append(List[Int]())
                buckets[vslot].append(v)
                pushes += 1

    var out_dist = List[Float64]()
    var reached = List[Bool]()
    var unreachable = 0
    for v in range(n):
        if settled[v]:
            out_dist.append(dist[v])
            reached.append(True)
        else:
            out_dist.append(GRAPH_NO_DISTANCE)
            reached.append(False)
            unreachable += 1
            pred[v] = GRAPH_NO_PREDECESSOR
    return GraphDistances(
        GRAPH_OK, n, source, settled_count, unreachable, pushes, out_dist^,
        reached^, pred^,
    )


fn graph_csr_bfs_levels(g: GraphCSR, source: Int) -> GraphLevels:
    """Hop counts from `source`, ignoring weights. Unreached nodes are `GRAPH_NO_LEVEL`.

    A queue with a front index, not a recursive walk: the frozen `graph.algorithms.bfs`
    does the same, and unlike it this one reports which nodes it never reached.
    """
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return GraphLevels(status, 0, source, 0, 0, GRAPH_NO_LEVEL, List[Int](), List[Bool]())
    var n = g.n_nodes
    if n == 0:
        return GraphLevels(
            GRAPH_ERR_EMPTY_GRAPH, 0, source, 0, 0, GRAPH_NO_LEVEL, List[Int](), List[Bool]()
        )
    if source < 0 or source >= n:
        return GraphLevels(
            GRAPH_ERR_SOURCE_OUT_OF_RANGE, n, source, 0, 0, GRAPH_NO_LEVEL,
            List[Int](), List[Bool](),
        )

    var level = List[Int]()
    var reached = List[Bool]()
    for _ in range(n):
        level.append(GRAPH_NO_LEVEL)
        reached.append(False)

    var queue = List[Int]()
    var front = 0
    level[source] = 0
    reached[source] = True
    queue.append(source)
    var max_level = 0
    while front < len(queue):
        var u = queue[front]
        front += 1
        for k in range(g.row_ptr[u], g.row_ptr[u + 1]):
            var v = g.targets[k]
            if not reached[v]:
                reached[v] = True
                level[v] = level[u] + 1
                if level[v] > max_level:
                    max_level = level[v]
                queue.append(v)
    var reached_count = len(queue)
    return GraphLevels(
        GRAPH_OK, n, source, reached_count, n - reached_count, max_level, level^,
        reached^,
    )


fn graph_csr_shortest_path(g: GraphCSR, source: Int, target: Int) -> GraphPath:
    """The node sequence of one shortest path, or an explicit "no path".

    Reconstructed from the predecessor array Dijkstra already fills, so the path and the
    distance can never disagree. The walk is bounded by `n_nodes` steps: a predecessor
    array is acyclic by construction, and a bound is cheaper than trusting that.
    """
    var d = graph_csr_dijkstra(g, source)
    if d.status != GRAPH_OK:
        return GraphPath(
            d.status, False, source, target, 0, GRAPH_NO_DISTANCE, List[Int]()
        )
    if target < 0 or target >= d.n_nodes:
        return GraphPath(
            GRAPH_ERR_TARGET_NODE_OUT_OF_RANGE, False, source, target, 0,
            GRAPH_NO_DISTANCE, List[Int](),
        )
    if not d.reached[target]:
        return GraphPath(
            GRAPH_OK, False, source, target, 0, GRAPH_NO_DISTANCE, List[Int]()
        )

    var backward = List[Int]()
    var node = target
    var steps = 0
    while steps <= d.n_nodes:
        backward.append(node)
        if node == source:
            break
        node = d.predecessor[node]
        if node < 0:
            break
        steps += 1
    if len(backward) == 0 or backward[len(backward) - 1] != source:
        # No walk back to the source means the predecessor array and the reached mask
        # disagree; report absence rather than a partial path that starts nowhere.
        return GraphPath(
            GRAPH_OK, False, source, target, 0, GRAPH_NO_DISTANCE, List[Int]()
        )
    var nodes = List[Int]()
    var i = len(backward) - 1
    while i >= 0:
        nodes.append(backward[i])
        i -= 1
    return GraphPath(
        GRAPH_OK, True, source, target, len(nodes) - 1, d.distance[target], nodes^
    )


# ── flat drivers ──────────────────────────────────────────────────────────────
# Flat lists in, a typed struct out: the input side crosses a JSON frame unchanged and
# the output side carries its status next to its numbers.


fn _no_build(status: Int) -> GraphBuildResult:
    return GraphBuildResult(
        status, 0, 0, 0, 0, 0, 0, 0, True, True, List[Int](), List[Int](),
        List[Float64](),
    )


fn _build_result(g: GraphCSR, status: Int) -> GraphBuildResult:
    # Duplicates are counted as adjacent repeats, which is exact because every caller
    # here hands over a graph with sorted rows (construction, reverse and dedupe all
    # establish that flag). An unsorted graph would under-count, so do not add one.
    var self_loops = 0
    var duplicates = 0
    var negatives = 0
    var non_finite = 0
    for u in range(g.n_nodes):
        for k in range(g.row_ptr[u], g.row_ptr[u + 1]):
            if g.targets[k] == u:
                self_loops += 1
            if k > g.row_ptr[u] and g.targets[k] == g.targets[k - 1]:
                duplicates += 1
    for k in range(len(g.weights)):
        var w = g.weights[k]
        if isnan(w) or isinf(w):
            non_finite += 1
        elif w < 0.0:
            negatives += 1
    return GraphBuildResult(
        status,
        g.n_nodes,
        len(g.targets),
        g.skipped_edges,
        self_loops,
        duplicates,
        negatives,
        non_finite,
        g.sorted_targets,
        g.deduplicated,
        g.row_ptr.copy(),
        g.targets.copy(),
        g.weights.copy(),
    )


fn graph_csr_build(
    src: List[Int], dst: List[Int], weight: List[Float64], n_nodes: Int
) -> GraphBuildResult:
    """Build a CSR from triplet arrays and report everything the build learned.

    The counts are the point: a caller that hands over an edge list gets back how many
    edges did not exist in the declared node range, how many self-loops and parallel
    edges it actually has, and whether Dijkstra applies at all.
    """
    if n_nodes < 0:
        return _no_build(GRAPH_ERR_INVALID_DIMENSIONS)
    if len(dst) != len(src) or len(weight) != len(src):
        return _no_build(GRAPH_ERR_LENGTH_MISMATCH)
    return _build_result(graph_csr_from_triplets(src, dst, weight, n_nodes), GRAPH_OK)


fn graph_csr_reverse_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
) -> GraphBuildResult:
    var g = graph_csr_from_arrays(row_ptr, targets, weights, n_nodes)
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return _no_build(status)
    return _build_result(graph_csr_reverse(g), GRAPH_OK)


fn graph_csr_dedupe_min_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
) -> GraphBuildResult:
    var g = graph_csr_from_arrays(row_ptr, targets, weights, n_nodes)
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return _no_build(status)
    return _build_result(graph_csr_dedupe_min(g), GRAPH_OK)


fn graph_csr_validate_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
) -> String:
    """Named verdict for a CSR that arrived as four arrays — `ok` or the defect."""
    return graph_status_name(
        graph_csr_validate_flat(row_ptr, targets, weights, n_nodes)
    )


fn graph_csr_out_degrees_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
) -> GraphIntsResult:
    var g = graph_csr_from_arrays(row_ptr, targets, weights, n_nodes)
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return GraphIntsResult(status, 0, List[Int]())
    var degrees = graph_csr_out_degrees(g)
    var count = len(degrees)
    return GraphIntsResult(GRAPH_OK, count, degrees^)


fn graph_csr_in_degrees_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
) -> GraphIntsResult:
    var g = graph_csr_from_arrays(row_ptr, targets, weights, n_nodes)
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return GraphIntsResult(status, 0, List[Int]())
    var degrees = graph_csr_in_degrees(g)
    var count = len(degrees)
    return GraphIntsResult(GRAPH_OK, count, degrees^)


fn graph_csr_degree_sequence_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
) -> GraphIntsResult:
    var g = graph_csr_from_arrays(row_ptr, targets, weights, n_nodes)
    var status = graph_csr_validate(g)
    if status != GRAPH_OK:
        return GraphIntsResult(status, 0, List[Int]())
    var sequence = graph_csr_degree_sequence(g)
    var count = len(sequence)
    return GraphIntsResult(GRAPH_OK, count, sequence^)


fn graph_csr_to_dense_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    absent: Float64,
) -> GraphVectorResult:
    return graph_csr_to_dense(
        graph_csr_from_arrays(row_ptr, targets, weights, n_nodes), absent
    )


fn graph_csr_edge_min_weight_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    u: Int,
    v: Int,
) -> GraphEdgeQuery:
    return graph_csr_edge_min_weight(
        graph_csr_from_arrays(row_ptr, targets, weights, n_nodes), u, v
    )


fn graph_csr_symmetry_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    tol: Float64,
) -> GraphSymmetry:
    return graph_csr_symmetry(
        graph_csr_from_arrays(row_ptr, targets, weights, n_nodes), tol
    )


fn graph_csr_dijkstra_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    source: Int,
) -> GraphDistances:
    return graph_csr_dijkstra(
        graph_csr_from_arrays(row_ptr, targets, weights, n_nodes), source
    )


fn graph_csr_bfs_levels_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    source: Int,
) -> GraphLevels:
    return graph_csr_bfs_levels(
        graph_csr_from_arrays(row_ptr, targets, weights, n_nodes), source
    )


fn graph_csr_shortest_path_driver(
    row_ptr: List[Int],
    targets: List[Int],
    weights: List[Float64],
    n_nodes: Int,
    source: Int,
    target: Int,
) -> GraphPath:
    return graph_csr_shortest_path(
        graph_csr_from_arrays(row_ptr, targets, weights, n_nodes), source, target
    )


fn graph_dijkstra_from_triplets(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    n_nodes: Int,
    source: Int,
) -> GraphDistances:
    """Build once, then Dijkstra: the drop-in replacement for the frozen triplet call.

    `graph.weighted.shortest_path_dijkstra` takes the same four arguments in effect,
    rebuilds adjacency inside every call, scans O(V^2) to settle, crashes on an
    out-of-range endpoint and reports unreachable as `1e18`. This does none of those.
    A caller that will ask more than one question should build a `GraphCSR` once with
    `graph_csr_build` and pass its arrays to `graph_csr_dijkstra_driver` instead.
    """
    if n_nodes < 0:
        return _no_distances(GRAPH_ERR_INVALID_DIMENSIONS, 0, source)
    if len(dst) != len(src) or len(weight) != len(src):
        return _no_distances(GRAPH_ERR_LENGTH_MISMATCH, 0, source)
    return graph_csr_dijkstra(
        graph_csr_from_triplets(src, dst, weight, n_nodes), source
    )


fn graph_bfs_levels_from_triplets(
    src: List[Int],
    dst: List[Int],
    weight: List[Float64],
    n_nodes: Int,
    source: Int,
) -> GraphLevels:
    """Build once, then BFS. Weights are carried but unused; hop counts ignore them."""
    if n_nodes < 0:
        return GraphLevels(
            GRAPH_ERR_INVALID_DIMENSIONS, 0, source, 0, 0, GRAPH_NO_LEVEL,
            List[Int](), List[Bool](),
        )
    if len(dst) != len(src) or len(weight) != len(src):
        return GraphLevels(
            GRAPH_ERR_LENGTH_MISMATCH, 0, source, 0, 0, GRAPH_NO_LEVEL,
            List[Int](), List[Bool](),
        )
    return graph_csr_bfs_levels(
        graph_csr_from_triplets(src, dst, weight, n_nodes), source
    )
