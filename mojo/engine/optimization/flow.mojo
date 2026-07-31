"""
optimization.flow — max flow with the min cut as data, and min-cost flow with potentials.

Why this file exists
--------------------
There is no max-flow driver anywhere in the tree. `graph_decision.mojo` has the two
per-step SCALARS — `flow_residual_capacity(capacity, current_flow)` and
`flow_augment_amount(path_min_residual, new_edge_residual)` — and nothing that calls them
in a loop, so the tree can compute one residual and one bottleneck fold but cannot answer
"what is the maximum flow from s to t". `graph.weighted` has shortest paths and
`combinatorial` has a greedy assignment; neither is a flow.

Those two frozen scalars are STEPS, not a driver, and they stay the only place the
clamping lives: every residual below is `flow_residual_capacity(cap, flow)` and every
bottleneck is a fold of `flow_augment_amount`, including the reverse arcs. That is
deliberate — a second `max(0, c - f)` written here would be a second definition of what a
saturated arc is, and the two would drift.

The reverse arc is internal and never exposed
---------------------------------------------
A residual network needs a reverse arc per input edge to be able to *cancel* flow, and a
caller that never asked for that arc must not receive it: `edge_flow` comes back with one
entry per INPUT edge, in input order. Internally arc `2k` is edge `k` forward and arc
`2k + 1` is its twin, so `twin(a)` is a one-bit flip and the pairing is a layout
invariant rather than a lookup table. The reverse arc carries capacity `0.0` and cost
`-cost[k]`, so `flow_residual_capacity(0.0, -f) == f` gives the cancellable amount with no
special case in the traversals.

This is also why the arc adjacency is built here instead of by
`graph_analytics.adjacency.graph_csr_from_triplets`: that build permutes edges into CSR
row order (a counting-sort transpose) and returns no permutation, so the `2k`/`2k+1`
pairing would be lost, and a residual arc would have to become a visible edge to survive
the round trip. `graph_csr_build` IS used, for what it is uniquely good at — the validated
triplet census. It tests both endpoints of every triplet and reports
`skipped_edges`/`negative_weights`/`non_finite_weights` instead of indexing an out-of-range
node, which is the crash `graph.weighted.shortest_path_dijkstra` still has.

An out-of-range endpoint is REJECTED here, not skipped
------------------------------------------------------
`graph_csr_build` counts a stray endpoint and drops the edge, which is right for a
distance question and wrong for this one: dropping an edge changes the max flow, and it
changes the min cut with it, so max-flow == min-cut would still hold on the reduced
network and the invariant below could not catch the loss. The census gives the count, and
the count is what makes the rejection specific.

The invariant is checked INSIDE the driver
------------------------------------------
Max-flow value equals min-cut capacity exactly, and both are computed here from different
data — the value from the augmentations, the cut from a residual reachability sweep and
the ORIGINAL capacities. So the identity is a self-check, not just a test assertion: if
the two disagree by more than a relative tolerance the result is
`FLOW_ERR_CUT_MISMATCH` with no numbers attached. A wrong answer that satisfies neither
side of a checkable identity should not be returned at all.

Absence markers
---------------
`has_value` is the authority and `value` is `0.0` padding, never a claim — the same rule
`optimization.model` follows, and for the same reason: NaN is the loudest marker in
arithmetic but it does not survive the JSON frame these drivers cross. Concretely:

  * a min-cost flow whose requested target exceeds the max flow has NO cost and NO flow
    value: it is `FLOW_ERR_TARGET_UNREACHABLE` with empty lists. Returning the largest
    flow it could route, priced, would answer a question nobody asked;
  * an audit of a point that is not a feasible flow has no flow value either, because the
    "value" of a vector that violates conservation is not a flow value;
  * the bottleneck of an empty path does not exist (`FLOW_ERR_EMPTY_PATH`), where a fold
    seeded with a large sentinel would report that sentinel.

Ceilings
--------
`n_nodes` is bounded by `sparse_numerics.csr.MAX_CSR_DIM`, imported and not redefined —
the same ceiling `graph_analytics.adjacency` uses, because a flow network on `n` nodes IS
an `n x n` sparse matrix and two ceilings would drift. It has to exist because the level
array, the potentials and the arc pointer are one slot PER NODE regardless of how few
edges there are: `max_flow_dinic(no_edges, 10**12, 0, 1)` is a structurally consistent
request and an 8 TB allocation.

The shared ceiling is used DIVIDED, not raw, and that division is the whole bound rather
than a decoration. `MAX_CSR_DIM` is justified as the largest single pointer array the
resident-dataset budget tolerates — 2^26 slots, ~512 MiB, *one object*. Every entry point
here allocates several arrays of length `n_nodes` at once (the triplet census alone peaks
at six, before the level array or the potentials exist), so `n_nodes == MAX_CSR_DIM` with
an EMPTY edge list is a structurally consistent request for several times the whole
budget. `FLOW_MAX_NODES = MAX_CSR_DIM // FLOW_NODE_ARRAYS` makes the product — nodes ×
arrays × 8 bytes — equal to that same 512 MiB, so what is bounded is the request and not
merely each array taken alone. It is still ONE ceiling: change `MAX_CSR_DIM` and this
moves with it.

Work is bounded twice, and the bound is a status
-----------------------------------------------
Dinic's phase count is at most `n_nodes` (the sink's level strictly increases per phase)
and a blocking flow saturates an arc per augmentation, so both have real algorithmic
bounds; `FLOW_MAX_WORK` is the separate safety ceiling on inner steps. Exceeding either is
`FLOW_ERR_ITERATION_LIMIT` / `FLOW_ERR_WORK_LIMIT` with no numbers — an iterative solver
that hit its cap has not converged, and its current iterate is not the answer.

Negative costs are rejected rather than answered wrongly
--------------------------------------------------------
Successive shortest paths prices each augmentation with Dijkstra over REDUCED costs
`cost(a) + pi[u] - pi[v]`, which is non-negative only if the potentials are valid, and the
zero potentials it starts from are valid only if every cost is non-negative. A negative
cost needs either a Bellman-Ford initialisation or negative-cycle cancelling, neither of
which is here, so it is `FLOW_ERR_NEGATIVE_COST`. `graph.weighted.bellman_ford` is the
frozen kernel for negative weights, and the wrong answer avoided is a *cheaper* flow that
is not minimum cost — indistinguishable from the right one without an independent oracle.

The shortest-path phase uses the frozen heap
--------------------------------------------
`heap.heap_push_min` / `heap_pop_min` is a real O(log n) binary heap, so no queue is
hand-rolled here. It stores a bare `Float64` with no payload slot and permutes its list
internally, so node identity travels in a `columnar.hash_index.HashIndex` bucket table —
exactly the arrangement `graph_analytics.adjacency.graph_csr_dijkstra` established, and
exact rather than approximate because the heap only ever MOVES keys, so a popped key is
bit-identical to the pushed one. Packing `(distance, node)` into the one `Float64` was
rejected there and is rejected here for the same reason: it perturbs the distance and can
decode the wrong node.
"""
from std.math import abs as fabs

from columnar.hash_index import HashIndex
from graph_analytics.adjacency import GRAPH_OK, graph_csr_build
from graph_decision import flow_augment_amount, flow_residual_capacity
from heap import heap_pop_min, heap_push_min
from optimization.model import model_finite as _finite
from sparse_numerics.csr import MAX_CSR_DIM

# ── status codes ──────────────────────────────────────────────────────────────
# One code per outcome. A caller holding a rejection has to know which of its five arrays
# or three scalars is wrong, and "invalid input" would send it to check all eight.

comptime FLOW_OK: Int = 0
comptime FLOW_ERR_INVALID_DIMENSIONS: Int = 1
comptime FLOW_ERR_LENGTH_MISMATCH: Int = 2
comptime FLOW_ERR_EMPTY_NETWORK: Int = 3
comptime FLOW_ERR_NODE_OUT_OF_RANGE: Int = 4
comptime FLOW_ERR_SAME_TERMINALS: Int = 5
comptime FLOW_ERR_EDGE_OUT_OF_RANGE: Int = 6
comptime FLOW_ERR_NEGATIVE_CAPACITY: Int = 7
comptime FLOW_ERR_NON_FINITE_CAPACITY: Int = 8
comptime FLOW_ERR_NEGATIVE_COST: Int = 9
comptime FLOW_ERR_NON_FINITE_COST: Int = 10
comptime FLOW_ERR_NEGATIVE_TARGET: Int = 11
comptime FLOW_ERR_NON_FINITE_TARGET: Int = 12
comptime FLOW_ERR_TARGET_UNREACHABLE: Int = 13
comptime FLOW_ERR_ITERATION_LIMIT: Int = 14
comptime FLOW_ERR_WORK_LIMIT: Int = 15
comptime FLOW_ERR_CUT_MISMATCH: Int = 16
comptime FLOW_ERR_POTENTIAL_BREAKDOWN: Int = 17
comptime FLOW_ERR_NON_FINITE_FLOW: Int = 18
comptime FLOW_ERR_PATH_INDEX: Int = 19
comptime FLOW_ERR_EMPTY_PATH: Int = 20
comptime FLOW_ERR_DEAD_PATH: Int = 21

# ── tolerances and ceilings ───────────────────────────────────────────────────

# An arc counts as usable when its residual exceeds this. Not 0.0: a residual of 1e-17
# left by rounding would keep an exhausted arc in the level graph forever, and the phase
# loop would spend its whole budget pushing amounts that change nothing.
comptime FLOW_EPS: Float64 = 1e-12

# Slack allowed on an audited capacity or conservation identity, and on the
# max-flow == min-cut self-check. Relative, because a network with capacities near 1e12
# accumulates absolute error near 1e-4 and a fixed 1e-9 would call it broken.
comptime FLOW_TOL: Float64 = 1e-9

# How many arrays of length n_nodes one request may hold live at the same time. MEASURED
# on the widest path through this file, worst case first:
#
#   * the triplet census `graph_csr_build` -> `graph_csr_from_triplets`: dst_count,
#     dst_start, cursor, out_count, row_ptr, fill = SIX Int arrays of length n, all live
#     together, and it runs before a solver allocates anything;
#   * `_min_cost_run`: arc_ptr + pi + dist + parent_arc (four Int/Float64) plus the
#     `settled` and `known` Bool masks, and `_build_network` peaks at three (out_count,
#     arc_ptr, fill) while building;
#   * `max_flow_dinic`: arc_ptr + level + iter_at + the BFS queue, plus the cut mask;
#   * `flow_audit_flat`: net_out + gross.
#
# Eight, not six: it covers the worst measured path with the `+ 1` pointer tails, the Bool
# masks and the BFS queue folded in, and 2^26 / 8 is exact so the ceiling stays a power of
# two. Raise this if a new per-node array is added — that is cheaper than discovering the
# budget was blown by an array nobody counted.
comptime FLOW_NODE_ARRAYS: Int = 8

# The node ceiling is sparse_numerics.csr's, not a second number — DIVIDED by the count
# above, which is what makes it a bound on the request rather than on one array.
#
# The arithmetic: MAX_CSR_DIM == 2^26 is justified in csr.mojo as "the worst-case pointer
# array at ~512 MB, which the 512 MiB resident-dataset budget already treats as the outer
# limit for ONE object". One object. Used raw here it bounded each array to 512 MiB and
# therefore bounded a request to FLOW_NODE_ARRAYS times the entire budget:
# `max_flow_dinic(no_edges, MAX_CSR_DIM, 0, 1)` is structurally consistent, has nothing in
# it to solve, and still asked for several gigabytes of level/potential/pointer arrays.
# Dividing gives 2^26 / 8 = 2^23 nodes, and 2^23 nodes x 8 arrays x 8 bytes = 512 MiB
# TOTAL — the same single-object budget the shared ceiling was justified against, now for
# the whole request. Do NOT lower MAX_CSR_DIM instead: other packages share it.
#
# The bound is deliberately on ALLOCATION and not on the edge count. A node no edge
# mentions cannot carry flow, but it is a legal node and `source_side` is one slot per
# declared node because the caller asked for that partition, so refusing a sparse network
# with isolated nodes would refuse a well-posed question. The allocation is what has to be
# bounded, and this bounds it.
comptime FLOW_MAX_NODES: Int = MAX_CSR_DIM // FLOW_NODE_ARRAYS

# Safety ceiling on inner advance/retreat steps, separate from the algorithmic bounds
# (phases <= n_nodes, one saturated arc per augmentation). Reaching it is a status.
comptime FLOW_MAX_WORK: Int = 1 << 30

comptime _NO_LEVEL: Int = -1
comptime _NO_ARC: Int = -1


fn flow_status_name(code: Int) -> String:
    """Name for a status code, so a rejection surfaces the defect and not a bare number.
    """
    if code == FLOW_OK:
        return "ok"
    if code == FLOW_ERR_INVALID_DIMENSIONS:
        return "invalid_dimensions"
    if code == FLOW_ERR_LENGTH_MISMATCH:
        return "parallel_arrays_length_mismatch"
    if code == FLOW_ERR_EMPTY_NETWORK:
        return "empty_network"
    if code == FLOW_ERR_NODE_OUT_OF_RANGE:
        return "terminal_node_out_of_range"
    if code == FLOW_ERR_SAME_TERMINALS:
        return "source_equals_sink"
    if code == FLOW_ERR_EDGE_OUT_OF_RANGE:
        return "edge_endpoint_out_of_range"
    if code == FLOW_ERR_NEGATIVE_CAPACITY:
        return "negative_capacity"
    if code == FLOW_ERR_NON_FINITE_CAPACITY:
        return "non_finite_capacity"
    if code == FLOW_ERR_NEGATIVE_COST:
        return "negative_cost_needs_cycle_cancelling"
    if code == FLOW_ERR_NON_FINITE_COST:
        return "non_finite_cost"
    if code == FLOW_ERR_NEGATIVE_TARGET:
        return "negative_target_flow"
    if code == FLOW_ERR_NON_FINITE_TARGET:
        return "non_finite_target_flow"
    if code == FLOW_ERR_TARGET_UNREACHABLE:
        return "target_flow_exceeds_max_flow"
    if code == FLOW_ERR_ITERATION_LIMIT:
        return "iteration_limit"
    if code == FLOW_ERR_WORK_LIMIT:
        return "work_limit"
    if code == FLOW_ERR_CUT_MISMATCH:
        return "flow_does_not_equal_cut"
    if code == FLOW_ERR_POTENTIAL_BREAKDOWN:
        return "negative_reduced_cost"
    if code == FLOW_ERR_NON_FINITE_FLOW:
        return "non_finite_flow"
    if code == FLOW_ERR_PATH_INDEX:
        return "path_edge_out_of_range"
    if code == FLOW_ERR_EMPTY_PATH:
        return "empty_path"
    if code == FLOW_ERR_DEAD_PATH:
        return "augmenting_path_with_no_capacity"
    return "unknown_status"


# ── the residual network ──────────────────────────────────────────────────────
# Mojo-level only, and deliberately absent from every public signature: its arrays are
# arc-indexed, so half of every one of them describes reverse arcs that the caller never
# declared. A `FlowNetwork` on the wire would make those arcs part of the API, and the
# next release could not stop building them.


@fieldwise_init
struct FlowNetwork(Copyable, Movable):
    """Arc-indexed residual network. Arc `2k` is input edge `k`; arc `2k+1` is its twin.

    `arc_cap` holds the ORIGINAL capacity (0.0 on a reverse arc) and `arc_flow` the
    current flow, with `arc_flow[twin(a)] == -arc_flow[a]` maintained by every push. The
    residual is therefore never stored, only derived, which is what keeps
    `graph_decision.flow_residual_capacity` the single definition of a saturated arc.
    """

    var n_nodes: Int
    var n_edges: Int
    var arc_head: List[Int]
    var arc_cap: List[Float64]
    var arc_cost: List[Float64]
    var arc_flow: List[Float64]
    var arc_ptr: List[Int]
    var arc_at: List[Int]

    fn n_arcs(self) -> Int:
        return len(self.arc_head)

    fn residual(self, a: Int) -> Float64:
        """Residual capacity of arc `a` via the frozen scalar. 0.0 for an arc we lack.

        The range test is not redundant with the callers' loops: an arc id reaching here
        out of range would be an uncatchable read past the end, and 0.0 ("nothing can be
        pushed") is the only answer that cannot turn into a wrong flow.
        """
        if a < 0 or a >= len(self.arc_cap):
            return 0.0
        return flow_residual_capacity(self.arc_cap[a], self.arc_flow[a])

    fn tail(self, a: Int) -> Int:
        """Tail of arc `a`, which is the head of its twin. -1 for an arc we lack."""
        var t = _twin(a)
        if t < 0 or t >= len(self.arc_head):
            return -1
        return self.arc_head[t]


fn _twin(a: Int) -> Int:
    """The paired arc. Written as arithmetic rather than `a ^ 1` because `^` is also the
    ownership-transfer sigil in this dialect and the intent should not depend on parsing.
    """
    if a % 2 == 0:
        return a + 1
    return a - 1


# ── return-only result structs ────────────────────────────────────────────────
# Declared in this file because the marshalling spec for a returned struct is parsed per
# file: returning a struct owned by another module drops the function from the runtime
# contract silently, with no error anywhere.


@fieldwise_init
struct FlowReport(Copyable, Movable):
    """The census of an edge list, before anything is solved on it.

    The counts are the point: a caller that hands over four arrays learns how many edges
    name a node that does not exist, how many carry a capacity no flow can use, and how
    many are self-loops or parallel copies — without a second pass and without a crash.
    `status` is `FLOW_OK` only when the list is solvable as given.
    """

    var status: Int
    var n_nodes: Int
    var n_edges: Int
    var n_arcs: Int
    var out_of_range_edges: Int
    var self_loops: Int
    var parallel_edges: Int
    var negative_capacities: Int
    var non_finite_capacities: Int
    var zero_capacity_edges: Int
    var total_capacity: Float64


@fieldwise_init
struct MaxFlow(Copyable, Movable):
    """A maximum flow, the minimum cut that proves it, and the status of the request.

    `has_value` is the authority; `value` is 0.0 padding when it is False. `source_side`
    is the min-cut node partition (True = reachable from the source in the residual
    network) and `cut_edges` lists the input edge indices crossing it, so the cut is data
    a caller can act on rather than a number it has to trust.

    `value == cut_capacity` is guaranteed whenever `status == FLOW_OK`: it is checked
    inside the driver against the original capacities, and a disagreement is
    `FLOW_ERR_CUT_MISMATCH` with no numbers instead.
    """

    var status: Int
    var n_nodes: Int
    var n_edges: Int
    var source: Int
    var sink: Int
    var has_value: Bool
    var value: Float64
    var cut_capacity: Float64
    var cut_edge_count: Int
    var source_side_count: Int
    var phases: Int
    var augmentations: Int
    var edge_flow: List[Float64]
    var source_side: List[Bool]
    var cut_edges: List[Int]


@fieldwise_init
struct MinCostFlow(Copyable, Movable):
    """A minimum-cost flow of the requested value, or an explicit absence of one.

    `has_value` and `has_cost` are separate on purpose: a routed flow always has a cost,
    but a request whose target exceeds the max flow has neither, and folding that into
    "cost 0.0" is the conflation this package exists to remove.

    `target_met` answers "did you get what you asked for", and it is True for
    `min_cost_max_flow` because that call asks for whatever is available — an unlimited
    request cannot miss its target, and `target` is 0.0 there because there was none.

    `potential` is the node potential vector the successive-shortest-path run ended with.
    It is the dual solution — a real answer, not diagnostics — and unlike
    `linear_programming.dual_value` (which is a misnomer: it returns the PRIMAL optimum of
    a two-variable LP) it is an actual dual.
    """

    var status: Int
    var n_nodes: Int
    var n_edges: Int
    var source: Int
    var sink: Int
    var has_value: Bool
    var value: Float64
    var has_cost: Bool
    var cost: Float64
    var target: Float64
    var target_met: Bool
    var augmentations: Int
    var edge_flow: List[Float64]
    var potential: List[Float64]


@fieldwise_init
struct FlowAudit(Copyable, Movable):
    """Whether a caller-supplied per-edge flow really is a flow, and what it is worth.

    This is the verifier, and it exists so "the solver said so" is never the only
    evidence: capacity on every edge, conservation at every non-terminal node, and then
    the value as the source's net outflow. `has_value` is False for an infeasible vector,
    because the value of something that is not a flow is not a flow value.

    `has_cost` is False when no cost array was supplied — a network without costs has no
    cost, which is not the same as a cost of zero.
    """

    var status: Int
    var feasible: Bool
    var has_value: Bool
    var value: Float64
    var has_cost: Bool
    var cost: Float64
    var capacity_violations: Int
    var conservation_violations: Int
    var worst_capacity_violation: Float64
    var worst_conservation_violation: Float64
    var first_bad_edge: Int
    var first_bad_node: Int


@fieldwise_init
struct FlowVector(Copyable, Movable):
    """A per-edge Float64 vector plus status, so "no edges" and "rejected" stay apart."""

    var status: Int
    var length: Int
    var values: List[Float64]


@fieldwise_init
struct FlowScalar(Copyable, Movable):
    """One number that may not exist, plus where it came from.

    `index` is the edge the number is attributable to (the binding bottleneck, or -1 when
    there is none). `has_value` is the authority; `value` is 0.0 padding otherwise.
    """

    var status: Int
    var has_value: Bool
    var value: Float64
    var index: Int


# ── small shared helpers ──────────────────────────────────────────────────────


# `_finite` is `model.model_finite`, imported at the top under this module's old local name so
# no call site changed, and NOT redefined here — five byte-identical copies were five chances
# for the package's definition of "finite" to drift. This module has no other reason to depend
# on `optimization.model` (its status codes are its own), and the import is one line against
# one more copy of the predicate that decides whether a capacity or a cost is admissible.
# Mojo has no access control, so the underscore only keeps the name out of the runtime
# contract; the dependency runs the right way round because `model` imports nothing from here.


fn _tolerance(scale: Float64) -> Float64:
    """Absolute slack for an identity whose terms are of magnitude `scale`."""
    var s = fabs(scale)
    return FLOW_TOL + FLOW_TOL * s


fn _augment_limit(n_nodes: Int, n_edges: Int) -> Int:
    """Generous bound on augmentations: at most one saturated arc each, at most n phases.

    Computed with a division guard rather than `(n_edges + 1) * (n_nodes + 1)`, because
    that product is a wrapping 64-bit multiply and a wrapped limit is not a limit.
    """
    var a = n_edges + 1
    var b = n_nodes + 1
    if b <= 0:
        return FLOW_MAX_WORK
    if a > FLOW_MAX_WORK // b:
        return FLOW_MAX_WORK
    return a * b + 16


fn _network_defect(
    edge_src: List[Int], edge_dst: List[Int], capacity: List[Float64], n_nodes: Int
) -> Int:
    """`FLOW_OK`, or the first reason this edge list is not a network on `n_nodes` nodes.

    The endpoint census is `graph_analytics.adjacency.graph_csr_build`, not a loop written
    here: it already tests both endpoints of every triplet and counts what it cannot
    represent, which is the check `graph.weighted.shortest_path_dijkstra` lacks and
    crashes for. Its verdict is *stricter* here — a skipped edge is a rejection, not a
    smaller network — for the reason in the module docstring.
    """
    if n_nodes < 0 or n_nodes > FLOW_MAX_NODES:
        return FLOW_ERR_INVALID_DIMENSIONS
    var m = len(edge_src)
    if len(edge_dst) != m or len(capacity) != m:
        return FLOW_ERR_LENGTH_MISMATCH
    var census = graph_csr_build(edge_src, edge_dst, capacity, n_nodes)
    if census.status != GRAPH_OK:
        return FLOW_ERR_LENGTH_MISMATCH
    if census.skipped_edges > 0:
        return FLOW_ERR_EDGE_OUT_OF_RANGE
    # Non-finite before negative: `nan < 0.0` is False, so a NaN capacity would pass a
    # bare negativity test and then poison every comparison downstream.
    if census.non_finite_weights > 0:
        return FLOW_ERR_NON_FINITE_CAPACITY
    if census.negative_weights > 0:
        return FLOW_ERR_NEGATIVE_CAPACITY
    return FLOW_OK


fn _cost_defect(cost: List[Float64], n_edges: Int) -> Int:
    """`FLOW_OK` for a cost array successive shortest paths can price with."""
    if len(cost) != n_edges:
        return FLOW_ERR_LENGTH_MISMATCH
    for k in range(n_edges):
        if not _finite(cost[k]):
            return FLOW_ERR_NON_FINITE_COST
        if cost[k] < 0.0:
            return FLOW_ERR_NEGATIVE_COST
    return FLOW_OK


fn _terminal_defect(n_nodes: Int, source: Int, sink: Int) -> Int:
    if n_nodes == 0:
        return FLOW_ERR_EMPTY_NETWORK
    if source < 0 or source >= n_nodes or sink < 0 or sink >= n_nodes:
        return FLOW_ERR_NODE_OUT_OF_RANGE
    if source == sink:
        # Flow from s to s is unbounded by inspection (every unit "arrives" for free), so
        # there is no maximum to report and no cut to report it against.
        return FLOW_ERR_SAME_TERMINALS
    return FLOW_OK


fn _build_network(
    edge_src: List[Int],
    edge_dst: List[Int],
    capacity: List[Float64],
    cost: List[Float64],
    n_nodes: Int,
) -> FlowNetwork:
    """Arc-indexed residual network. Callers must have cleared `_network_defect` first.

    An empty `cost` means an uncosted network and every arc cost is 0.0, which is exactly
    what max flow wants: one builder, not two.
    """
    var m = len(edge_src)
    var costed = len(cost) == m
    var arc_head = List[Int]()
    var arc_cap = List[Float64]()
    var arc_cost = List[Float64]()
    var arc_flow = List[Float64]()
    for k in range(m):
        var c: Float64 = 0.0
        if costed:
            c = cost[k]
        arc_head.append(edge_dst[k])
        arc_cap.append(capacity[k])
        arc_cost.append(c)
        arc_flow.append(0.0)
        arc_head.append(edge_src[k])
        arc_cap.append(0.0)
        arc_cost.append(-c)
        arc_flow.append(0.0)

    # Arc ids grouped by TAIL, by counting sort: O(V + E) and no comparison sort. The ids
    # are kept as ids — the alternative, letting a CSR build permute the arcs, is what
    # would destroy the 2k/2k+1 pairing.
    var n_arcs = len(arc_head)
    var out_count = List[Int]()
    for _ in range(n_nodes):
        out_count.append(0)
    for k in range(m):
        out_count[edge_src[k]] += 1
        out_count[edge_dst[k]] += 1
    var arc_ptr = List[Int]()
    var running = 0
    for u in range(n_nodes):
        arc_ptr.append(running)
        running += out_count[u]
    arc_ptr.append(running)
    var fill = List[Int]()
    for u in range(n_nodes):
        fill.append(arc_ptr[u])
    var arc_at = List[Int]()
    for _ in range(n_arcs):
        arc_at.append(0)
    for k in range(m):
        var forward = 2 * k
        var pos = fill[edge_src[k]]
        arc_at[pos] = forward
        fill[edge_src[k]] = pos + 1
        var back = forward + 1
        pos = fill[edge_dst[k]]
        arc_at[pos] = back
        fill[edge_dst[k]] = pos + 1

    return FlowNetwork(
        n_nodes, m, arc_head^, arc_cap^, arc_cost^, arc_flow^, arc_ptr^, arc_at^
    )


fn _edge_flows(net: FlowNetwork) -> List[Float64]:
    """Flow per INPUT edge, in input order. The twin arcs stay inside."""
    var out = List[Float64]()
    for k in range(net.n_edges):
        out.append(net.arc_flow[2 * k])
    return out^


# ── Dinic ─────────────────────────────────────────────────────────────────────


fn _level_graph(
    net: FlowNetwork, source: Int, sink: Int, mut level: List[Int]
) -> Bool:
    """BFS over arcs with residual capacity. True when the sink is still reachable.

    A queue with a front index, not recursion — the repo convention, and the depth here is
    caller-controlled.
    """
    for i in range(len(level)):
        level[i] = _NO_LEVEL
    var queue = List[Int]()
    var front = 0
    level[source] = 0
    queue.append(source)
    while front < len(queue):
        var u = queue[front]
        front += 1
        for p in range(net.arc_ptr[u], net.arc_ptr[u + 1]):
            var a = net.arc_at[p]
            if net.residual(a) > FLOW_EPS:
                var v = net.arc_head[a]
                if level[v] == _NO_LEVEL:
                    level[v] = level[u] + 1
                    queue.append(v)
    return level[sink] != _NO_LEVEL


fn _blocking_flow(
    mut net: FlowNetwork,
    source: Int,
    sink: Int,
    level: List[Int],
    mut iter_at: List[Int],
    augment_limit: Int,
    mut total: Float64,
    mut augmentations: Int,
    mut work: Int,
) -> Int:
    """Saturate every source-to-sink path in the level graph. Iterative, one arc stack.

    `iter_at` is the current-arc optimisation: an arc that has been rejected once in this
    phase is never examined again, which is what makes a phase O(V·E) instead of O(V·E²).
    Recursion was rejected per the repo convention (`stats.fast_sort`,
    `graph/algorithms.mojo`) and because the path length here is `n_nodes`, a caller
    number.
    """
    var path = List[Int]()
    var u = source
    while True:
        work += 1
        if work > FLOW_MAX_WORK:
            return FLOW_ERR_WORK_LIMIT

        if u == sink:
            # Bottleneck as a fold of the frozen per-step scalar, seeded with the first
            # arc's residual rather than a large sentinel: a sentinel is exactly how an
            # empty path comes to report a bottleneck it does not have.
            var b = net.residual(path[0])
            for i in range(1, len(path)):
                b = flow_augment_amount(b, net.residual(path[i]))
            if b <= FLOW_EPS:
                # Every arc on the path passed `residual > FLOW_EPS` when it was pushed
                # and nothing has changed since, so this is unreachable unless the
                # residual derivation and the advance test disagree. Report it rather
                # than loop forever pushing nothing.
                return FLOW_ERR_DEAD_PATH
            for i in range(len(path)):
                var a = path[i]
                net.arc_flow[a] = net.arc_flow[a] + b
                var t = _twin(a)
                net.arc_flow[t] = net.arc_flow[t] - b
            total += b
            augmentations += 1
            if augmentations > augment_limit:
                return FLOW_ERR_ITERATION_LIMIT
            # Retreat only as far as the first arc this augmentation saturated: the prefix
            # before it is still usable, and rebuilding it would repeat the advance work.
            var cut_at = len(path)
            for i in range(len(path)):
                if net.residual(path[i]) <= FLOW_EPS:
                    cut_at = i
                    break
            while len(path) > cut_at:
                _ = path.pop()
            if cut_at == 0:
                u = source
            else:
                u = net.arc_head[path[cut_at - 1]]
            continue

        var advanced = False
        while iter_at[u] < net.arc_ptr[u + 1]:
            var a = net.arc_at[iter_at[u]]
            var v = net.arc_head[a]
            if net.residual(a) > FLOW_EPS and level[v] == level[u] + 1:
                path.append(a)
                u = v
                advanced = True
                break
            iter_at[u] = iter_at[u] + 1
            work += 1
            if work > FLOW_MAX_WORK:
                return FLOW_ERR_WORK_LIMIT
        if advanced:
            continue

        if u == source:
            return FLOW_OK
        var dead = path.pop()
        u = net.arc_head[_twin(dead)]
        iter_at[u] = iter_at[u] + 1


fn _dinic(
    mut net: FlowNetwork,
    source: Int,
    sink: Int,
    augment_limit: Int,
    mut total: Float64,
    mut phases: Int,
    mut augmentations: Int,
) -> Int:
    var level = List[Int]()
    for _ in range(net.n_nodes):
        level.append(_NO_LEVEL)
    var work = 0
    while True:
        if not _level_graph(net, source, sink, level):
            return FLOW_OK
        phases += 1
        if phases > net.n_nodes:
            # The sink's level strictly increases every phase, so a phase count above
            # n_nodes means the level graph stopped making progress. That is a broken
            # invariant, not a big network, and the flow so far is not the answer.
            return FLOW_ERR_ITERATION_LIMIT
        var iter_at = net.arc_ptr.copy()
        var status = _blocking_flow(
            net, source, sink, level, iter_at, augment_limit, total,
            augmentations, work,
        )
        if status != FLOW_OK:
            return status


fn _residual_reachable(net: FlowNetwork, source: Int) -> List[Bool]:
    """The source side of the min cut: nodes reachable over arcs with residual capacity.

    This is the second, independent computation of the same quantity the augmentations
    produced — which is what makes `value == cut_capacity` a check rather than a slogan.
    """
    var side = List[Bool]()
    for _ in range(net.n_nodes):
        side.append(False)
    var queue = List[Int]()
    var front = 0
    side[source] = True
    queue.append(source)
    while front < len(queue):
        var u = queue[front]
        front += 1
        for p in range(net.arc_ptr[u], net.arc_ptr[u + 1]):
            var a = net.arc_at[p]
            if net.residual(a) > FLOW_EPS:
                var v = net.arc_head[a]
                if not side[v]:
                    side[v] = True
                    queue.append(v)
    return side^


fn _cut_edges(
    edge_src: List[Int],
    edge_dst: List[Int],
    capacity: List[Float64],
    side: List[Bool],
    mut cut: List[Int],
) -> Float64:
    """Capacity of the `side` cut, appending the crossing input edge indices to `cut`.

    Only source-side-to-sink-side edges count. The reverse crossings carry no flow at a
    maximum (their twins would otherwise reach the far node), and counting them would
    turn a cut capacity into a net flow — a different, smaller number.

    A declared edge of capacity 0.0 that crosses the cut is listed: it is structurally in
    the cut and contributes 0.0, so the identity still holds and the caller still learns
    that the edge is on the frontier.
    """
    var total: Float64 = 0.0
    for k in range(len(edge_src)):
        if side[edge_src[k]] and not side[edge_dst[k]]:
            cut.append(k)
            total += capacity[k]
    return total


fn _no_max_flow(status: Int, n_nodes: Int, n_edges: Int, s: Int, t: Int) -> MaxFlow:
    """No answer: empty lists, zero counts, `has_value` False.

    Not "value 0.0 with a status nobody read": a rejected request and a network whose max
    flow really is 0.0 must not look the same, and the second one is `FLOW_OK` with
    `has_value` True.
    """
    return MaxFlow(
        status, n_nodes, n_edges, s, t, False, 0.0, 0.0, 0, 0, 0, 0,
        List[Float64](), List[Bool](), List[Int](),
    )


fn max_flow_dinic(
    edge_src: List[Int], edge_dst: List[Int], capacity: List[Float64],
    n_nodes: Int, source: Int, sink: Int,
) -> MaxFlow:
    """Maximum `source`-to-`sink` flow by Dinic, with the minimum cut that certifies it.

    Returns the flow value, the flow on every INPUT edge in input order, the min-cut node
    partition and the crossing edges. `value == cut_capacity` holds on every `FLOW_OK`
    result — checked here against the original capacities, because both sides of
    max-flow/min-cut are computed from different data and a bug in either the augmentation
    or the cut extraction breaks the equality.

    Dinic rather than Edmonds-Karp: the phase structure bounds the phase count by
    `n_nodes` regardless of the capacity magnitudes, so a network with capacities of 1e9
    does not become 1e9 augmentations. There is no frozen max flow to call — the tree has
    `graph_decision.flow_residual_capacity` and `flow_augment_amount`, which are the two
    per-step scalars this driver folds, and nothing else.

    There is no "unbounded" outcome to report, and that is a consequence of a rejection
    rather than an oversight: a non-finite capacity is refused up front, so the max flow is
    bounded by the (finite) capacity sum. An overflow of that sum to infinity is
    `FLOW_ERR_NON_FINITE_FLOW`, because infinity is not a flow value either.
    """
    var m = len(edge_src)
    if n_nodes < 0 or n_nodes > FLOW_MAX_NODES:
        return _no_max_flow(FLOW_ERR_INVALID_DIMENSIONS, 0, 0, source, sink)
    var terminal = _terminal_defect(n_nodes, source, sink)
    if terminal != FLOW_OK:
        return _no_max_flow(terminal, n_nodes, m, source, sink)
    var defect = _network_defect(edge_src, edge_dst, capacity, n_nodes)
    if defect != FLOW_OK:
        return _no_max_flow(defect, n_nodes, m, source, sink)

    var net = _build_network(
        edge_src, edge_dst, capacity, List[Float64](), n_nodes
    )
    var total: Float64 = 0.0
    var phases = 0
    var augmentations = 0
    var status = _dinic(
        net, source, sink, _augment_limit(n_nodes, m), total, phases, augmentations
    )
    if status != FLOW_OK:
        return _no_max_flow(status, n_nodes, m, source, sink)
    if not _finite(total):
        # Reachable only by summing finite capacities into an overflow. `inf - inf` is NaN
        # and `NaN > tol` is False, so the cut check below would PASS and hand back an
        # infinite flow value as if it were an answer.
        return _no_max_flow(FLOW_ERR_NON_FINITE_FLOW, n_nodes, m, source, sink)

    var side = _residual_reachable(net, source)
    var cut = List[Int]()
    var cut_capacity = _cut_edges(edge_src, edge_dst, capacity, side, cut)
    if fabs(cut_capacity - total) > _tolerance(total):
        # The identity is exact in exact arithmetic, so a gap this large is a defect in
        # one of the two computations. Returning either number would be returning a wrong
        # answer that looks like a right one.
        return _no_max_flow(FLOW_ERR_CUT_MISMATCH, n_nodes, m, source, sink)

    var inside = 0
    for v in range(n_nodes):
        if side[v]:
            inside += 1
    var cut_count = len(cut)
    return MaxFlow(
        FLOW_OK, n_nodes, m, source, sink, True, total, cut_capacity, cut_count,
        inside, phases, augmentations, _edge_flows(net), side^, cut^,
    )


# ── successive shortest paths with potentials ─────────────────────────────────


fn _reduced_dijkstra(
    net: FlowNetwork,
    source: Int,
    pi: List[Float64],
    mut dist: List[Float64],
    mut parent_arc: List[Int],
    mut settled: List[Bool],
) -> Int:
    """Dijkstra over residual arcs priced by reduced cost. Frozen heap, exact identity.

    The heap is `heap.heap_push_min` / `heap_pop_min`; node identity lives in a
    `HashIndex` bucket per distinct key, the arrangement
    `graph_analytics.adjacency.graph_csr_dijkstra` established. Recovery is exact because
    the heap only moves keys, so a popped key is bit-identical to the pushed one and the
    `dist[node] != key` staleness test is a valid exact comparison.

    Runs to completion rather than stopping at the sink: every settled node's potential is
    updated afterwards, and stopping early would leave the potentials inconsistent and the
    next phase's reduced costs negative.
    """
    var n = net.n_nodes
    var known = List[Bool]()
    for i in range(n):
        dist[i] = 0.0
        parent_arc[i] = _NO_ARC
        settled[i] = False
        known.append(False)

    var heap = List[Float64]()
    var pending = HashIndex(64)
    var buckets = List[List[Int]]()
    dist[source] = 0.0
    known[source] = True
    heap_push_min(heap, 0.0)
    var slot = pending.get_or_assign(0.0, len(buckets))
    if slot == len(buckets):
        buckets.append(List[Int]())
    buckets[slot].append(source)

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
        if dist[node] != key:
            continue
        settled[node] = True
        for p in range(net.arc_ptr[node], net.arc_ptr[node + 1]):
            var a = net.arc_at[p]
            if net.residual(a) <= FLOW_EPS:
                continue
            var v = net.arc_head[a]
            var red = net.arc_cost[a] + pi[node] - pi[v]
            if red < 0.0:
                var slack = _tolerance(
                    fabs(net.arc_cost[a]) + fabs(pi[node]) + fabs(pi[v])
                )
                if red < -slack:
                    # A negative reduced cost means the potentials are no longer a valid
                    # dual, and Dijkstra on it would return a shortest path that is not
                    # shortest — a cheaper-looking flow that is not minimum cost.
                    return FLOW_ERR_POTENTIAL_BREAKDOWN
                red = 0.0
            var nd = key + red
            if not known[v] or nd < dist[v]:
                known[v] = True
                dist[v] = nd
                parent_arc[v] = a
                heap_push_min(heap, nd)
                var vslot = pending.get_or_assign(nd, len(buckets))
                if vslot == len(buckets):
                    buckets.append(List[Int]())
                buckets[vslot].append(v)
    return FLOW_OK


fn _ssp(
    mut net: FlowNetwork,
    source: Int,
    sink: Int,
    target: Float64,
    limited: Bool,
    augment_limit: Int,
    mut total: Float64,
    mut cost: Float64,
    mut augmentations: Int,
    mut pi: List[Float64],
) -> Int:
    """Route flow along successively more expensive shortest paths until the target.

    Each augmentation takes a MINIMUM-COST path in the residual network, which is the
    property that makes the result cost-optimal among flows of its value: a cheaper
    non-shortest augmentation reaching the same flow value must pay more somewhere else.
    Costs stay non-negative for Dijkstra by reduced-cost pricing with node potentials
    rather than by re-running Bellman-Ford per phase.
    """
    var n = net.n_nodes
    var dist = List[Float64]()
    var parent_arc = List[Int]()
    var settled = List[Bool]()
    for _ in range(n):
        dist.append(0.0)
        parent_arc.append(_NO_ARC)
        settled.append(False)

    while True:
        if limited and target - total <= FLOW_EPS:
            return FLOW_OK
        var status = _reduced_dijkstra(net, source, pi, dist, parent_arc, settled)
        if status != FLOW_OK:
            return status
        if not settled[sink]:
            # No residual path left: this is the maximum flow, whatever the target said.
            return FLOW_OK

        # Only SETTLED nodes get their potential updated. An arc (u, v) with positive
        # residual, u settled and v not, cannot exist — Dijkstra would have reached v — and
        # an unsettled u can never become reachable later, because an arc INTO u only gains
        # residual when flow is pushed OUT of u, which requires u on an augmenting path.
        # So the arcs whose reduced cost this skips are arcs no later phase can use.
        for v in range(n):
            if settled[v]:
                pi[v] = pi[v] + dist[v]

        var path = List[Int]()
        var node = sink
        var steps = 0
        while node != source and steps <= n:
            var a = parent_arc[node]
            if a == _NO_ARC:
                break
            path.append(a)
            node = net.tail(a)
            if node < 0:
                break
            steps += 1
        if node != source or len(path) == 0:
            # The predecessor chain and the settled mask disagree; there is no path to
            # augment and no partial answer worth returning.
            return FLOW_ERR_DEAD_PATH

        var b = net.residual(path[0])
        for i in range(1, len(path)):
            b = flow_augment_amount(b, net.residual(path[i]))
        if limited:
            b = flow_augment_amount(b, target - total)
        if b <= FLOW_EPS:
            return FLOW_ERR_DEAD_PATH

        var unit_cost: Float64 = 0.0
        for i in range(len(path)):
            var a = path[i]
            unit_cost += net.arc_cost[a]
            net.arc_flow[a] = net.arc_flow[a] + b
            var t = _twin(a)
            net.arc_flow[t] = net.arc_flow[t] - b
        total += b
        cost += b * unit_cost
        augmentations += 1
        if augmentations > augment_limit:
            return FLOW_ERR_ITERATION_LIMIT


fn _no_min_cost(
    status: Int, n_nodes: Int, n_edges: Int, s: Int, t: Int, target: Float64
) -> MinCostFlow:
    return MinCostFlow(
        status, n_nodes, n_edges, s, t, False, 0.0, False, 0.0, target, False, 0,
        List[Float64](), List[Float64](),
    )


fn _min_cost_run(
    edge_src: List[Int], edge_dst: List[Int], capacity: List[Float64],
    cost: List[Float64], n_nodes: Int, source: Int, sink: Int,
    target: Float64, limited: Bool,
) -> MinCostFlow:
    var m = len(edge_src)
    if n_nodes < 0 or n_nodes > FLOW_MAX_NODES:
        return _no_min_cost(FLOW_ERR_INVALID_DIMENSIONS, 0, 0, source, sink, target)
    var terminal = _terminal_defect(n_nodes, source, sink)
    if terminal != FLOW_OK:
        return _no_min_cost(terminal, n_nodes, m, source, sink, target)
    var defect = _network_defect(edge_src, edge_dst, capacity, n_nodes)
    if defect != FLOW_OK:
        return _no_min_cost(defect, n_nodes, m, source, sink, target)
    var cost_defect = _cost_defect(cost, m)
    if cost_defect != FLOW_OK:
        return _no_min_cost(cost_defect, n_nodes, m, source, sink, target)
    if limited:
        if not _finite(target):
            return _no_min_cost(
                FLOW_ERR_NON_FINITE_TARGET, n_nodes, m, source, sink, target
            )
        if target < 0.0:
            return _no_min_cost(
                FLOW_ERR_NEGATIVE_TARGET, n_nodes, m, source, sink, target
            )

    var net = _build_network(edge_src, edge_dst, capacity, cost, n_nodes)
    var pi = List[Float64]()
    for _ in range(n_nodes):
        pi.append(0.0)
    var total: Float64 = 0.0
    var priced: Float64 = 0.0
    var augmentations = 0
    var status = _ssp(
        net, source, sink, target, limited, _augment_limit(n_nodes, m), total,
        priced, augmentations, pi,
    )
    if status != FLOW_OK:
        return _no_min_cost(status, n_nodes, m, source, sink, target)
    if not _finite(total) or not _finite(priced):
        return _no_min_cost(
            FLOW_ERR_NON_FINITE_FLOW, n_nodes, m, source, sink, target
        )
    if limited and target - total > _tolerance(target):
        # The demand cannot be routed at all, so there is no minimum-cost flow of that
        # value and no cost for one. The largest flow this network admits is a different
        # question, and `min_cost_max_flow` is the function that answers it.
        return _no_min_cost(
            FLOW_ERR_TARGET_UNREACHABLE, n_nodes, m, source, sink, target
        )
    var met = True
    if limited:
        met = fabs(total - target) <= _tolerance(target)
    return MinCostFlow(
        FLOW_OK, n_nodes, m, source, sink, True, total, True, priced, target, met,
        augmentations, _edge_flows(net), pi^,
    )


fn min_cost_flow(
    edge_src: List[Int], edge_dst: List[Int], capacity: List[Float64],
    cost: List[Float64], n_nodes: Int, source: Int, sink: Int,
    target_flow: Float64,
) -> MinCostFlow:
    """Cheapest way to route exactly `target_flow` units, or an explicit absence of one.

    Successive shortest paths with node potentials: every augmentation is along a
    minimum-cost residual path, so the expensive edge is used only once the cheap one is
    saturated, and the result is cost-optimal among flows of its value.

    A target the network cannot route is `FLOW_ERR_TARGET_UNREACHABLE` with no value and
    no cost — not the largest flow it managed, which would silently answer a different
    question. Costs must be non-negative; see the module docstring for why that is a
    rejection and not a limitation quietly worked around.
    """
    return _min_cost_run(
        edge_src, edge_dst, capacity, cost, n_nodes, source, sink, target_flow, True
    )


fn min_cost_max_flow(
    edge_src: List[Int], edge_dst: List[Int], capacity: List[Float64],
    cost: List[Float64], n_nodes: Int, source: Int, sink: Int,
) -> MinCostFlow:
    """The cheapest MAXIMUM flow: successive shortest paths run until the sink is cut off.

    Separate from `min_cost_flow` rather than a sentinel target, because "as much as
    possible" and "exactly this much" have different failure modes — the first cannot be
    infeasible and the second can — and a sentinel value in a `Float64` target would be a
    legal demand.
    """
    return _min_cost_run(
        edge_src, edge_dst, capacity, cost, n_nodes, source, sink, 0.0, False
    )


# ── verification and per-step exposure ────────────────────────────────────────


fn flow_audit_flat(
    edge_src: List[Int], edge_dst: List[Int], capacity: List[Float64],
    cost: List[Float64], n_nodes: Int, source: Int, sink: Int,
    edge_flow: List[Float64],
) -> FlowAudit:
    """Is `edge_flow` a feasible flow, what is it worth, and what does it cost.

    Independent of both solvers, which is the point: it re-derives capacity feasibility,
    conservation at every non-terminal node and the value as the source's net outflow, so
    a solver's answer can be checked without trusting the solver. It is also how an
    ALTERNATIVE flow gets priced, which is what makes "this one is cheaper" a measurement.

    `cost` may be empty, and then the flow has no cost rather than a cost of 0.0.
    """
    var m = len(edge_src)
    if n_nodes < 0 or n_nodes > FLOW_MAX_NODES:
        return FlowAudit(
            FLOW_ERR_INVALID_DIMENSIONS, False, False, 0.0, False, 0.0, 0, 0,
            0.0, 0.0, -1, -1,
        )
    var terminal = _terminal_defect(n_nodes, source, sink)
    if terminal != FLOW_OK:
        return FlowAudit(terminal, False, False, 0.0, False, 0.0, 0, 0, 0.0, 0.0, -1, -1)
    var defect = _network_defect(edge_src, edge_dst, capacity, n_nodes)
    if defect != FLOW_OK:
        return FlowAudit(defect, False, False, 0.0, False, 0.0, 0, 0, 0.0, 0.0, -1, -1)
    if len(edge_flow) != m:
        return FlowAudit(
            FLOW_ERR_LENGTH_MISMATCH, False, False, 0.0, False, 0.0, 0, 0, 0.0,
            0.0, -1, -1,
        )
    var costed = len(cost) == m
    if len(cost) != 0 and not costed:
        return FlowAudit(
            FLOW_ERR_LENGTH_MISMATCH, False, False, 0.0, False, 0.0, 0, 0, 0.0,
            0.0, -1, -1,
        )
    for k in range(m):
        if not _finite(edge_flow[k]):
            return FlowAudit(
                FLOW_ERR_NON_FINITE_FLOW, False, False, 0.0, False, 0.0, 0, 0,
                0.0, 0.0, k, -1,
            )
        if costed and not _finite(cost[k]):
            return FlowAudit(
                FLOW_ERR_NON_FINITE_COST, False, False, 0.0, False, 0.0, 0, 0,
                0.0, 0.0, k, -1,
            )

    var net_out = List[Float64]()
    var gross = List[Float64]()
    for _ in range(n_nodes):
        net_out.append(0.0)
        gross.append(0.0)
    var cap_violations = 0
    var worst_cap: Float64 = 0.0
    var first_bad_edge = -1
    var priced: Float64 = 0.0
    for k in range(m):
        var f = edge_flow[k]
        var over = f - capacity[k]
        var under = -f
        var excess = over
        if under > excess:
            excess = under
        if excess > _tolerance(capacity[k]):
            cap_violations += 1
            if excess > worst_cap:
                worst_cap = excess
            if first_bad_edge < 0:
                first_bad_edge = k
        net_out[edge_src[k]] = net_out[edge_src[k]] + f
        net_out[edge_dst[k]] = net_out[edge_dst[k]] - f
        # Gross throughput per node, so the conservation slack scales with the numbers at
        # that node: a fixed 1e-9 would call a node handling 1e12 units broken.
        gross[edge_src[k]] = gross[edge_src[k]] + fabs(f)
        gross[edge_dst[k]] = gross[edge_dst[k]] + fabs(f)
        if costed:
            priced += f * cost[k]

    var conservation_violations = 0
    var worst_conservation: Float64 = 0.0
    var first_bad_node = -1
    for v in range(n_nodes):
        if v == source or v == sink:
            continue
        var imbalance = fabs(net_out[v])
        if imbalance > _tolerance(gross[v]):
            conservation_violations += 1
            if imbalance > worst_conservation:
                worst_conservation = imbalance
            if first_bad_node < 0:
                first_bad_node = v

    var feasible = cap_violations == 0 and conservation_violations == 0
    var value = net_out[source]
    if not feasible:
        # The "value" of a vector that is not a flow is not a flow value, so it is absent
        # rather than reported alongside the violation counts.
        return FlowAudit(
            FLOW_OK, False, False, 0.0, False, 0.0, cap_violations,
            conservation_violations, worst_cap, worst_conservation,
            first_bad_edge, first_bad_node,
        )
    return FlowAudit(
        FLOW_OK, True, True, value, costed, priced, 0, 0, 0.0, 0.0, -1, -1
    )


fn flow_network_check(
    edge_src: List[Int], edge_dst: List[Int], capacity: List[Float64], n_nodes: Int
) -> FlowReport:
    """Census an edge list before solving on it: what it has, and what it cannot be.

    The endpoint and capacity counts come from
    `graph_analytics.adjacency.graph_csr_build`, so there is one validated triplet build
    in the tree and not a second one here. `status` is this module's stricter verdict: an
    out-of-range endpoint is a rejection, because dropping the edge would change the max
    flow and the min cut together and leave the identity intact.
    """
    if n_nodes < 0 or n_nodes > FLOW_MAX_NODES:
        return FlowReport(
            FLOW_ERR_INVALID_DIMENSIONS, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0
        )
    var m = len(edge_src)
    if len(edge_dst) != m or len(capacity) != m:
        return FlowReport(FLOW_ERR_LENGTH_MISMATCH, n_nodes, 0, 0, 0, 0, 0, 0, 0, 0, 0.0)
    var census = graph_csr_build(edge_src, edge_dst, capacity, n_nodes)
    if census.status != GRAPH_OK:
        return FlowReport(FLOW_ERR_LENGTH_MISMATCH, n_nodes, m, 0, 0, 0, 0, 0, 0, 0, 0.0)

    var zero_capacity = 0
    var total: Float64 = 0.0
    for k in range(m):
        if _finite(capacity[k]):
            if capacity[k] == 0.0:
                zero_capacity += 1
            elif capacity[k] > 0.0:
                total += capacity[k]
    var status = FLOW_OK
    if census.skipped_edges > 0:
        status = FLOW_ERR_EDGE_OUT_OF_RANGE
    elif census.non_finite_weights > 0:
        status = FLOW_ERR_NON_FINITE_CAPACITY
    elif census.negative_weights > 0:
        status = FLOW_ERR_NEGATIVE_CAPACITY
    return FlowReport(
        status, n_nodes, m, 2 * m, census.skipped_edges, census.self_loops,
        census.duplicate_edges, census.negative_weights,
        census.non_finite_weights, zero_capacity, total,
    )


fn edge_residuals(
    capacity: List[Float64], edge_flow: List[Float64]
) -> FlowVector:
    """Residual capacity per edge, each one from `graph_decision.flow_residual_capacity`.

    Exposed because a caller inspecting a solved network needs the same clamping the
    solver used — `capacity - flow` written at the call site would disagree on a
    negative-by-rounding residual, and then "saturated" would mean two things.
    """
    if len(capacity) != len(edge_flow):
        return FlowVector(FLOW_ERR_LENGTH_MISMATCH, 0, List[Float64]())
    var out = List[Float64]()
    for k in range(len(capacity)):
        out.append(flow_residual_capacity(capacity[k], edge_flow[k]))
    var length = len(out)
    return FlowVector(FLOW_OK, length, out^)


fn path_bottleneck(
    capacity: List[Float64], edge_flow: List[Float64], path_edges: List[Int]
) -> FlowScalar:
    """How much more can be pushed along `path_edges`, and which edge binds.

    A fold of the frozen `graph_decision.flow_augment_amount`, seeded with the first
    edge's residual. The bottleneck of an EMPTY path does not exist and is
    `FLOW_ERR_EMPTY_PATH` with `has_value` False: seeding the fold with a large sentinel
    would report that sentinel as an amount somebody could push.

    Every path index is checked against the arrays before it is used. The generated
    contract suite calls this with `path_edges = [1, 2, 3, 4, 5]` against five-element
    arrays, and index 5 there would be a read past the end — an uncatchable process
    crash, not an exception.
    """
    if len(capacity) != len(edge_flow):
        return FlowScalar(FLOW_ERR_LENGTH_MISMATCH, False, 0.0, -1)
    if len(path_edges) == 0:
        return FlowScalar(FLOW_ERR_EMPTY_PATH, False, 0.0, -1)
    for i in range(len(path_edges)):
        var k = path_edges[i]
        if k < 0 or k >= len(capacity):
            return FlowScalar(FLOW_ERR_PATH_INDEX, False, 0.0, k)
    var best = flow_residual_capacity(
        capacity[path_edges[0]], edge_flow[path_edges[0]]
    )
    var binding = path_edges[0]
    for i in range(1, len(path_edges)):
        var k = path_edges[i]
        var r = flow_residual_capacity(capacity[k], edge_flow[k])
        var folded = flow_augment_amount(best, r)
        if folded != best:
            binding = k
        best = folded
    return FlowScalar(FLOW_OK, True, best, binding)


fn cut_capacity_of(
    edge_src: List[Int], edge_dst: List[Int], capacity: List[Float64],
    n_nodes: Int, source_side: List[Bool],
) -> FlowScalar:
    """Capacity of the cut a caller's own node partition defines, and its edge count.

    Prices an arbitrary partition with the same rule the driver's own cut uses, so a
    heuristic partition can be compared against the minimum one on equal terms. `index`
    carries the number of crossing edges — the one integer a cut capacity is meaningless
    without, since a cut of 0.0 across zero edges and across three saturated
    zero-capacity edges are different situations.
    """
    var defect = _network_defect(edge_src, edge_dst, capacity, n_nodes)
    if defect != FLOW_OK:
        return FlowScalar(defect, False, 0.0, -1)
    if len(source_side) != n_nodes:
        return FlowScalar(FLOW_ERR_LENGTH_MISMATCH, False, 0.0, -1)
    var cut = List[Int]()
    var total = _cut_edges(edge_src, edge_dst, capacity, source_side, cut)
    var crossing = len(cut)
    return FlowScalar(FLOW_OK, True, total, crossing)


fn is_saturated(capacity: Float64, flow: Float64, tol: Float64) -> Bool:
    """True when no more can be pushed on an edge, by the frozen residual rule.

    A predicate rather than a comparison at the call site, because `flow >= capacity` and
    `flow_residual_capacity(capacity, flow) <= tol` disagree on a negative flow: the first
    calls it unsaturated and open for business, the second calls it saturated because the
    frozen scalar clamps. The clamping definition is the one the solvers use.
    """
    return flow_residual_capacity(capacity, flow) <= tol
