"""
causal_inference.dag — identification as a PRECONDITION: d-separation and the backdoor
criterion over a declared graph. Zero Python imports.

Why this file exists, and why it comes first in the package
-----------------------------------------------------------
`causal.mojo` is the tree's causal surface and it has no notion of a graph at all. `ate` is
`mean(treated) - mean(control)`; `ipw_estimate` is a weighted version of the same contrast;
`stratified_ate` averages it within strata. Every one of them returns a Float64 that a caller
will read as "the causal effect", and NONE of them can say whether the quantity they computed
is identified — because none of them was told what the confounding structure is.

That is not a small gap, it is the whole discipline. An unadjusted difference in means is a
causal effect exactly when no backdoor path is open, and a regression coefficient wearing a
causal name otherwise. So this package refuses to estimate an effect it cannot identify, and
this module is where the refusal is decided:

  * `dag_validate` — the declared graph is a DAG, or it is not, and if it is not the report
    NAMES AN EDGE ON THE CYCLE rather than saying "invalid".
  * `d_separated` — the graph-level conditional-independence test (Bayes-Ball), which returns
    a WITNESS PATH when the answer is "not separated". A boolean False is not actionable; the
    path `T <- U -> Y` is.
  * `backdoor_check` — is `E[Y | do(T)]` identified by adjusting for `Z`? If not, the status
    is `CI_ERR_NOT_IDENTIFIED` and the unblocked backdoor path comes back with it.
  * `backdoor_minimal_set` — a minimal sufficient adjustment set out of a candidate pool, with
    minimality MEASURED by one re-check per member rather than inferred.

Nothing here estimates anything. The estimators in this package take an identification verdict
as an argument precisely so that "identified" cannot be assumed by whoever is in a hurry.

Graph representation
--------------------
A flat parallel edge list — `edge_from[k] -> edge_to[k]` — plus `n_nodes`. Directed. Node ids
are `0..n_nodes-1` and carry no names: a name would be a String per node crossing the wire for
no analytic content, and the caller already has its own labels.

Both frozen graph surfaces were considered and one of them is REUSED:

  * `graph.algorithms.topological_sort(g)` runs Kahn's algorithm and returns a PARTIAL order
    when the graph has a cycle ("nodes involved in cycles are omitted"). That is a complete
    acyclicity ORACLE — `len(order) == n_nodes` iff the graph is a DAG — so `dag_validate`
    calls it and does not reimplement Kahn. What it cannot do is say WHICH edge closes the
    cycle, and "your graph is invalid" without an edge is a bug report with no address. So the
    residual nodes it leaves behind are walked once more here to name one.
  * `graph.algorithms.graph_add_edge` does `g._adj_targets[from_node].append(...)` with no
    range check, so a single edge whose endpoint is `>= n` is not an error, it is a process
    crash. Every edge is therefore range-checked HERE before the frozen graph is built, which
    is also why `dag_validate` reports `CI_ERR_INDEX` rather than dying.
  * `graph_analytics.adjacency` builds a real CSR and validates endpoints, but its traversals
    are weighted-shortest-path shaped. d-separation is not a path-length question, so the
    parent/child CSR is built locally — twelve `n_nodes`-length arrays, which is what
    `MAX_CI_NODES` was sized from.

d-separation: Bayes-Ball, not path enumeration
-----------------------------------------------
The definition ("every path from X to Y is blocked by Z") is a statement about paths and there
can be exponentially many of them. Enumerating them would be a hang, i.e. rule 1's uncatchable
abort as seen from the caller. `_reachable_with` is Koller & Friedman Algorithm 3.1 instead: two
linear passes, the first collecting the ancestors of Z (which is what makes a collider
`A -> C <- B` transmit when C has a descendant in Z), the second a BFS over (node, direction)
STATES — 2n of them, so the whole test is O(n + m) whatever the path count.

The direction is load-bearing and is the part that is easy to get wrong: `UP` means the state
was entered from one of the node's CHILDREN (so we are travelling against the arrows), `DOWN`
means it was entered from one of its PARENTS. A node in Z blocks a chain and a fork but a
collider in Z (or with a descendant in Z) OPENS. Those three cases are the three branches in
`_reachable_with`, and the suite enumerates them on hand-drawn four-node graphs where the
answers can be written down without a computer.

The witness path is not decoration. Each of the 2n states records the state it was reached
from, so when a Y-node is reached the chain walks back to an X-node and the trail comes out as
a node list. That trail is an OPEN path given Z, and it is the evidence for the refusal.

Status codes: this module draws from `base.mojo`'s 340-359 allocation and defines none of its
own.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_causal_inference_dag.mojo
benchmark: benchmarks/mojo_benchmarks/bench_causal_inference.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from graph.algorithms import Graph, graph_add_edge, graph_new, topological_sort

from causal_inference.base import (
    CI_ERR_DIMENSION_TOO_LARGE,
    CI_ERR_DUPLICATE,
    CI_ERR_INDEX,
    CI_ERR_LENGTH_MISMATCH,
    CI_ERR_NOT_A_DAG,
    CI_ERR_NOT_IDENTIFIED,
    CI_ERR_SHAPE,
    CI_OK,
    MAX_CI_EDGES,
    MAX_CI_NODES,
)

# A traversal state was entered from a child (travelling against the arrow) or from a parent.
comptime _DIR_UP: Int = 0
comptime _DIR_DOWN: Int = 1

# "No node" in a reported edge or path position. -1 rather than 0, because node 0 is a real
# node and a caller reading `cycle_from == 0` cannot tell a real answer from a default.
comptime DAG_NO_NODE: Int = -1


# ── result structs (declared HERE: a struct owned by another module is silently
#    dropped from the runtime contract along with the function returning it) ───


struct DagReport(Copyable, Movable):
    """Structural verdict on a declared graph.

    `is_dag` is the answer; `cycle_from`/`cycle_to` are an edge ON a cycle when it is False,
    and `DAG_NO_NODE` when it is True. `topo_order` is non-empty ONLY for a real DAG: a
    partial order for a cyclic graph is what `graph.algorithms.topological_sort` returns and
    it is exactly the kind of plausible-looking wrong answer this package exists to remove.
    """

    var status: Int
    var n_nodes: Int
    var n_edges: Int
    var is_dag: Bool
    var cycle_from: Int
    var cycle_to: Int
    var n_self_loops: Int
    var n_duplicate_edges: Int
    var has_order: Bool
    var topo_order: List[Int]
    var in_degree: List[Int]
    var out_degree: List[Int]

    def __init__(out self, status: Int, n_nodes: Int, n_edges: Int):
        self.status = status
        self.n_nodes = n_nodes
        self.n_edges = n_edges
        self.is_dag = False
        self.cycle_from = DAG_NO_NODE
        self.cycle_to = DAG_NO_NODE
        self.n_self_loops = 0
        self.n_duplicate_edges = 0
        self.has_order = False
        self.topo_order = List[Int]()
        self.in_degree = List[Int]()
        self.out_degree = List[Int]()


struct DSepReport(Copyable, Movable):
    """Whether X and Y are d-separated by Z, plus the evidence when they are not.

    `separated` is meaningful only when `status == CI_OK`. When `separated` is False,
    `path_nodes` is one OPEN trail from a node of X to a node of Y — adjacent entries are
    joined by an edge in one direction or the other — and `n_reachable` counts the nodes
    reachable from X given Z, which is the size of the dependence, not just its existence.
    """

    var status: Int
    var separated: Bool
    var has_answer: Bool
    var n_reachable: Int
    var path_nodes: List[Int]
    var reachable_mask: List[Bool]

    def __init__(out self, status: Int):
        self.status = status
        self.separated = False
        self.has_answer = False
        self.n_reachable = 0
        self.path_nodes = List[Int]()
        self.reachable_mask = List[Bool]()


struct BackdoorReport(Copyable, Movable):
    """Whether adjusting for `Z` identifies the effect of `treatment` on `outcome`.

    THE CONTRACT, stated in full because rule 4d says a certificate must check every
    condition it claims. `identified = True` asserts BOTH halves of Pearl's backdoor
    criterion, not one:

      (i)  no node of Z is a descendant of `treatment` — `n_descendant_violations` counts
           them and `first_descendant` names one. Conditioning on a descendant of the
           treatment can open a path or block a causal one, so this is not a technicality;
      (ii) Z blocks every backdoor path, i.e. every path from `treatment` to `outcome`
           that leaves `treatment` through an arrow INTO it. Checked as d-separation of
           `treatment` from `outcome` given Z in the graph with all edges OUT of `treatment`
           deleted, which is the standard equivalent and is linear rather than exponential.

    Nothing else is claimed. In particular this says nothing about unmeasured confounding
    that the DECLARED graph does not contain: identification is relative to the graph, and a
    graph that omits a confounder will happily certify. `unblocked_path` is the witness for
    (ii) failing, and it is populated even under `CI_ERR_NOT_IDENTIFIED` — the refusal has to
    name the path or it is not actionable.
    """

    var status: Int
    var identified: Bool
    var has_verdict: Bool
    var blocks_backdoor_paths: Bool
    var n_descendant_violations: Int
    var first_descendant: Int
    var n_adjustment: Int
    var n_open_backdoor_paths_found: Int
    var unblocked_path: List[Int]

    def __init__(out self, status: Int):
        self.status = status
        self.identified = False
        self.has_verdict = False
        self.blocks_backdoor_paths = False
        self.n_descendant_violations = 0
        self.first_descendant = DAG_NO_NODE
        self.n_adjustment = 0
        self.n_open_backdoor_paths_found = 0
        self.unblocked_path = List[Int]()


struct AdjustmentSet(Copyable, Movable):
    """A sufficient adjustment set drawn from a candidate pool, and how it was arrived at.

    `minimality_measured` is True only when every retained member was individually re-checked
    and found necessary — one d-separation call per member. It is not inferred from the order
    the filter happened to run in, for the same reason `optimization.explain.infeasibility_core`
    measures its core with one re-solve per member instead of trusting the filter's
    monotonicity.

    WHAT A REFUSAL FROM `backdoor_minimal_set` DOES AND DOES NOT MEAN. It means: the canonical
    (ancestral) subset of the candidate pool does not satisfy the backdoor criterion. It does
    NOT mean no subset does. Sufficiency is not monotone in the adjustment set — M-bias is the
    standard counterexample, where the EMPTY set is valid and `{M}` is not — so an exhaustive
    search over subsets is exponential and is not attempted. `n_dropped_non_ancestral` is the
    step that makes the search worth trusting as far as it goes: dropping candidates that are
    not ancestors of the treatment or the outcome cannot turn a valid pool invalid, and it is
    what lets the empty set be reached in the M-bias case. `backdoor_check` on a set the caller
    names is the CONCLUSIVE verdict; this function is a search, and says so.
    """

    var status: Int
    var identified: Bool
    var has_set: Bool
    var chosen: List[Int]
    var n_candidates: Int
    var n_dropped_descendant: Int
    var n_dropped_non_ancestral: Int
    var n_dropped_redundant: Int
    var minimality_measured: Bool
    var n_checks: Int

    def __init__(out self, status: Int):
        self.status = status
        self.identified = False
        self.has_set = False
        self.chosen = List[Int]()
        self.n_candidates = 0
        self.n_dropped_descendant = 0
        self.n_dropped_non_ancestral = 0
        self.n_dropped_redundant = 0
        self.minimality_measured = False
        self.n_checks = 0


# ── internal adjacency ───────────────────────────────────────────────────────


struct _Adj(Copyable, Movable):
    """Parent and child CSR over a validated edge list. Internal: never returned."""

    var n: Int
    var child_ptr: List[Int]
    var child_idx: List[Int]
    var parent_ptr: List[Int]
    var parent_idx: List[Int]

    def __init__(out self):
        self.n = 0
        self.child_ptr = List[Int]()
        self.child_idx = List[Int]()
        self.parent_ptr = List[Int]()
        self.parent_idx = List[Int]()


def _edge_defect(edge_from: List[Int], edge_to: List[Int], n_nodes: Int) -> Int:
    """`CI_OK` or the code naming why this edge list cannot be walked.

    Runs BEFORE anything is allocated from `n_nodes` and before any endpoint is used as an
    index — which is the whole point: `graph.algorithms.graph_add_edge` would index
    `_adj_targets[from_node]` with an unvalidated endpoint, and that is an uncatchable abort,
    not an exception.
    """
    if n_nodes < 0:
        return CI_ERR_SHAPE
    if n_nodes > MAX_CI_NODES:
        return CI_ERR_DIMENSION_TOO_LARGE
    if len(edge_from) != len(edge_to):
        return CI_ERR_LENGTH_MISMATCH
    if len(edge_from) > MAX_CI_EDGES:
        return CI_ERR_DIMENSION_TOO_LARGE
    for k in range(len(edge_from)):
        var u = edge_from[k]
        var v = edge_to[k]
        if u < 0 or u >= n_nodes or v < 0 or v >= n_nodes:
            return CI_ERR_INDEX
    return CI_OK


def _build_adj(edge_from: List[Int], edge_to: List[Int], n_nodes: Int, skip_out_of: Int) -> _Adj:
    """Parent/child CSR. Callers MUST have run `_edge_defect` first.

    `skip_out_of` deletes every edge leaving that node (`DAG_NO_NODE` deletes nothing), which
    is how the backdoor criterion's "graph with the treatment's outgoing edges removed" is
    formed without copying the caller's arrays.
    """
    var a = _Adj()
    a.n = n_nodes
    var m = len(edge_from)

    var child_count = List[Int](capacity=n_nodes + 1)
    var parent_count = List[Int](capacity=n_nodes + 1)
    for _ in range(n_nodes + 1):
        child_count.append(0)
        parent_count.append(0)
    var kept = 0
    for k in range(m):
        var u = edge_from[k]
        if u == skip_out_of:
            continue
        var v = edge_to[k]
        child_count[u] += 1
        parent_count[v] += 1
        kept += 1

    a.child_ptr = List[Int](capacity=n_nodes + 1)
    a.parent_ptr = List[Int](capacity=n_nodes + 1)
    var run_c = 0
    var run_p = 0
    for i in range(n_nodes):
        a.child_ptr.append(run_c)
        a.parent_ptr.append(run_p)
        run_c += child_count[i]
        run_p += parent_count[i]
    a.child_ptr.append(run_c)
    a.parent_ptr.append(run_p)

    a.child_idx = List[Int](capacity=kept if kept > 0 else 1)
    a.parent_idx = List[Int](capacity=kept if kept > 0 else 1)
    for _ in range(kept):
        a.child_idx.append(0)
        a.parent_idx.append(0)
    var cfill = List[Int](capacity=n_nodes + 1)
    var pfill = List[Int](capacity=n_nodes + 1)
    for i in range(n_nodes):
        cfill.append(a.child_ptr[i])
        pfill.append(a.parent_ptr[i])
    for k in range(m):
        var u = edge_from[k]
        if u == skip_out_of:
            continue
        var v = edge_to[k]
        a.child_idx[cfill[u]] = v
        cfill[u] += 1
        a.parent_idx[pfill[v]] = u
        pfill[v] += 1
    return a^


def _mask_defect(nodes: List[Int], n_nodes: Int, mut mask: List[Bool]) -> Int:
    """Set `mask[v]` for every `v` in `nodes`; `CI_ERR_INDEX` out of range,
    `CI_ERR_DUPLICATE` on a repeat. `mask` must already be `n_nodes` long."""
    for i in range(len(nodes)):
        var v = nodes[i]
        if v < 0 or v >= n_nodes:
            return CI_ERR_INDEX
        if mask[v]:
            return CI_ERR_DUPLICATE
        mask[v] = True
    return CI_OK


def _descendant_mask(a: _Adj, root: Int) -> List[Bool]:
    """Nodes reachable from `root` by following arrows forward, INCLUDING `root`.

    Explicit stack, never recursion — matching `stats.fast_sort` and `graph/algorithms.mojo`,
    and because a 65536-node chain would blow a call stack.
    """
    var seen = List[Bool](capacity=a.n if a.n > 0 else 1)
    for _ in range(a.n):
        seen.append(False)
    if root < 0 or root >= a.n:
        return seen^
    var stack = List[Int]()
    stack.append(root)
    seen[root] = True
    while len(stack) > 0:
        var u = stack[len(stack) - 1]
        _ = stack.pop()
        for t in range(a.child_ptr[u], a.child_ptr[u + 1]):
            var v = a.child_idx[t]
            if not seen[v]:
                seen[v] = True
                stack.append(v)
    return seen^


def _ancestor_of_z_mask(a: _Adj, z: List[Bool]) -> List[Bool]:
    """Nodes with a descendant in Z, Z itself included — Phase I of Bayes-Ball.

    This is the mask that makes a COLLIDER transmit. `A -> C <- B` blocks unless C or a
    descendant of C is conditioned on, and "or a descendant of" is precisely this set. A
    d-separation routine that only tested `C in Z` would report separation for
    `A -> C <- B, C -> D, Z = {D}`, which is the textbook counterexample and is asserted in
    the suite.
    """
    var anc = List[Bool](capacity=a.n if a.n > 0 else 1)
    for _ in range(a.n):
        anc.append(False)
    var stack = List[Int]()
    for i in range(a.n):
        if z[i]:
            anc[i] = True
            stack.append(i)
    while len(stack) > 0:
        var u = stack[len(stack) - 1]
        _ = stack.pop()
        for t in range(a.parent_ptr[u], a.parent_ptr[u + 1]):
            var p = a.parent_idx[t]
            if not anc[p]:
                anc[p] = True
                stack.append(p)
    return anc^


def _state(node: Int, direction: Int) -> Int:
    return 2 * node + direction


def _reachable_with(
    a: _Adj, x: List[Bool], z: List[Bool], anc: List[Bool], y: List[Bool]
) -> DSepReport:
    """Bayes-Ball Phase II: d-connection from X to Y given Z, plus a witness path.

    Phase I (`anc`, the ancestors of Z) is a PARAMETER rather than computed here, because
    `backdoor_minimal_set` changes Z on every trial and Phase I depends on Z. Passing it in
    makes recomputation the caller's explicit decision instead of an accident of caching — a
    stale collider mask would answer a question about a different conditioning set, which is
    rule 4d's incomplete check exactly.

    Koller & Friedman Algorithm 3.1. Phase I is `_ancestor_of_z_mask`. Phase II is a BFS over
    `2n` (node, direction) states with these three transitions, which ARE the three blocking
    rules and are the only place they are written down:

      * entered from a child (`_DIR_UP`) at a node NOT in Z: the trail may continue up to any
        parent (`... <- y <- p`, a chain) or down to any child (`... <- y -> c`, a FORK, which
        is open exactly because y is not conditioned on);
      * entered from a parent (`_DIR_DOWN`) at a node NOT in Z: the trail may continue down to
        any child — a chain `p -> y -> c`;
      * entered from a parent at a node in `anc`, the ANCESTORS-OF-Z set: the trail may turn around
        and go up to any parent — a COLLIDER `p -> y <- q` opened by conditioning on y or on a
        descendant of y. Note the two `_DIR_DOWN` branches are independent, not exclusive: a
        node can be both a non-collider continuation and an opened collider.

    A node in Z is never added to the reachable set, and never continues a chain. X-nodes are
    seeded `_DIR_UP` so the first step may go either way.

    `pred` records the state each state was reached from, so a hit on Y walks back to an
    X-node and the trail comes out as a node list. That is the only reason states are BFS'd
    from a queue rather than a stack: the witness path is then a shortest open trail, which is
    the most readable one.
    """
    var n = a.n
    var out = DSepReport(CI_OK)
    var visited = List[Bool](capacity=2 * n if n > 0 else 1)
    var pred = List[Int](capacity=2 * n if n > 0 else 1)
    for _ in range(2 * n):
        visited.append(False)
        pred.append(-1)
    var reach = List[Bool](capacity=n if n > 0 else 1)
    for _ in range(n):
        reach.append(False)

    var queue = List[Int]()
    var head = 0
    for i in range(n):
        if x[i]:
            var s = _state(i, _DIR_UP)
            if not visited[s]:
                visited[s] = True
                queue.append(s)

    var hit_state = -1
    while head < len(queue):
        var s = queue[head]
        head += 1
        var node = s // 2
        var direction = s % 2
        if not z[node]:
            if not reach[node]:
                reach[node] = True
                out.n_reachable += 1
            if y[node] and hit_state < 0:
                hit_state = s

        if direction == _DIR_UP and not z[node]:
            for t in range(a.parent_ptr[node], a.parent_ptr[node + 1]):
                var p = a.parent_idx[t]
                var ns = _state(p, _DIR_UP)
                if not visited[ns]:
                    visited[ns] = True
                    pred[ns] = s
                    queue.append(ns)
            for t in range(a.child_ptr[node], a.child_ptr[node + 1]):
                var c = a.child_idx[t]
                var ns = _state(c, _DIR_DOWN)
                if not visited[ns]:
                    visited[ns] = True
                    pred[ns] = s
                    queue.append(ns)
        elif direction == _DIR_DOWN:
            if not z[node]:
                for t in range(a.child_ptr[node], a.child_ptr[node + 1]):
                    var c = a.child_idx[t]
                    var ns = _state(c, _DIR_DOWN)
                    if not visited[ns]:
                        visited[ns] = True
                        pred[ns] = s
                        queue.append(ns)
            if anc[node]:
                for t in range(a.parent_ptr[node], a.parent_ptr[node + 1]):
                    var p = a.parent_idx[t]
                    var ns = _state(p, _DIR_UP)
                    if not visited[ns]:
                        visited[ns] = True
                        pred[ns] = s
                        queue.append(ns)

    out.reachable_mask = reach^
    out.has_answer = True
    out.separated = hit_state < 0
    if hit_state >= 0:
        var chain = List[Int]()
        var s = hit_state
        while s >= 0:
            chain.append(s // 2)
            s = pred[s]
        var path = List[Int](capacity=len(chain))
        for i in range(len(chain) - 1, -1, -1):
            path.append(chain[i])
        out.path_nodes = path^
    return out^


# ── dag_validate ─────────────────────────────────────────────────────────────


def dag_validate(
    edge_from: List[Int], edge_to: List[Int], n_nodes: Int
) -> DagReport:
    """Is the declared graph a DAG? If not, name an edge on the cycle.

    Acyclicity is decided by the FROZEN `graph.algorithms.topological_sort`: it runs Kahn's
    algorithm and omits nodes involved in cycles, so `len(order) == n_nodes` is exactly
    "acyclic". Kahn is not reimplemented here.

    What the frozen kernel cannot do is say which edge closes the cycle, and a validator that
    reports "not a DAG" without an address is a bug report a caller cannot act on. The nodes
    Kahn left out are precisely the nodes on or downstream of a cycle, so one walk inside that
    residual set must revisit a node within `n_nodes + 1` steps — and the edge that closes the
    revisit is returned.

    THE WALK GOES BACKWARD, along residual PARENTS, and the direction is the whole proof. Kahn
    emits a node when its in-degree among the nodes it has not yet emitted reaches zero, so a
    node it never emitted still has, at termination, at least one incoming edge from another
    node it never emitted: every residual node has at least one residual PARENT, always. It
    does not follow that a residual node has a residual CHILD — a node merely DOWNSTREAM of a
    cycle is residual (nothing ever settles it) and can be a sink. A forward walk therefore
    strands itself on such a node and names no edge at all, which was measured: the graph
    `0 -> 1`, `1 -> 2`, `1 -> 0` reported `not a DAG` with `cycle_from == cycle_to == -1`, while
    the SAME graph with the edge list permuted named an edge — the verdict depended on which
    residual child the walk happened to see first. Backward, no such choice exists to get
    wrong: the invariant holds at every node, so the walk cannot stop early and the `n_nodes + 1`
    step bound forces a repeat.

    The repeat names a real cycle edge. The walk `v0 <- v1 <- ... <- vk` is the edge sequence
    `v_{i+1} -> v_i`, so a repeat `vk == vj` exhibits the path `vj -> v_{k-1} -> ... -> vj`; the
    last edge followed, `vk -> v_{k-1}`, lies on it and is what `cycle_from`/`cycle_to` carry.

    A self loop `v -> v` is a cycle and is reported as one, with `cycle_from == cycle_to`.
    Duplicate edges are counted but are NOT an error: a declared graph with `A -> B` twice
    means the same thing as once.

    `topo_order` is empty unless the graph really is a DAG. Returning Kahn's partial order
    would hand back something that reads as a topological order and is not one.

    @capability dag_validate
    complexity: O(n_nodes + n_edges)
    counts:
    - dim n_nodes [kernel_validated]
    @endcapability
    """
    var defect = _edge_defect(edge_from, edge_to, n_nodes)
    if defect != CI_OK:
        return DagReport(defect, 0, 0)
    var m = len(edge_from)
    var out = DagReport(CI_OK, n_nodes, m)

    var indeg = List[Int](capacity=n_nodes if n_nodes > 0 else 1)
    var outdeg = List[Int](capacity=n_nodes if n_nodes > 0 else 1)
    for _ in range(n_nodes):
        indeg.append(0)
        outdeg.append(0)
    for k in range(m):
        var u = edge_from[k]
        var v = edge_to[k]
        indeg[v] += 1
        outdeg[u] += 1
        if u == v:
            out.n_self_loops += 1

    # Duplicate detection without an n^2 scan and without a hash: sort each node's targets.
    var a = _build_adj(edge_from, edge_to, n_nodes, DAG_NO_NODE)
    for u in range(n_nodes):
        var lo = a.child_ptr[u]
        var hi = a.child_ptr[u + 1]
        var span = hi - lo
        if span < 2:
            continue
        var order = _sorted_int_copy(a, lo, hi)
        for i in range(1, len(order)):
            if order[i] == order[i - 1]:
                out.n_duplicate_edges += 1

    var g = graph_new(n_nodes)
    for k in range(m):
        # Endpoints validated in `_edge_defect`. `graph_add_edge` range-checks nothing and an
        # out-of-range endpoint there is a process abort, not an exception.
        graph_add_edge(g, edge_from[k], edge_to[k], 1.0)
    var order = topological_sort(g)

    if len(order) == n_nodes:
        out.is_dag = True
        out.has_order = True
        out.topo_order = order^
        out.in_degree = indeg^
        out.out_degree = outdeg^
        return out^

    out.is_dag = False
    out.status = CI_ERR_NOT_A_DAG
    out.in_degree = indeg^
    out.out_degree = outdeg^

    var settled = List[Bool](capacity=n_nodes if n_nodes > 0 else 1)
    for _ in range(n_nodes):
        settled.append(False)
    for i in range(len(order)):
        settled[order[i]] = True

    # Walk BACKWARD inside the residual set until a node repeats; the last edge followed closes
    # a cycle. Bounded by n_nodes + 1 steps, so it terminates whatever the structure. Backward
    # and not forward because "every residual node has a residual parent" is the invariant Kahn
    # actually leaves behind — see this function's docstring — so the walk never strands.
    var start = DAG_NO_NODE
    for i in range(n_nodes):
        if not settled[i]:
            start = i
            break
    if start != DAG_NO_NODE:
        var seen_at = List[Int](capacity=n_nodes if n_nodes > 0 else 1)
        for _ in range(n_nodes):
            seen_at.append(-1)
        var cur = start
        var prev = DAG_NO_NODE
        var steps = 0
        while steps <= n_nodes:
            if seen_at[cur] >= 0:
                # `cur` is a residual parent of `prev` that the walk already stood on, so the
                # edge `cur -> prev` closes a cycle through it and both endpoints are real
                # nodes. `prev` has necessarily been assigned by now: `seen_at` starts at -1
                # everywhere, so the very first pass cannot reach this branch, and every later
                # pass ran the `prev = cur` below. No DAG_NO_NODE can escape from here.
                out.cycle_from = cur
                out.cycle_to = prev
                break
            seen_at[cur] = steps
            var nxt = DAG_NO_NODE
            for t in range(a.parent_ptr[cur], a.parent_ptr[cur + 1]):
                var u = a.parent_idx[t]
                if not settled[u]:
                    nxt = u
                    break
            if nxt == DAG_NO_NODE:
                # UNREACHABLE while the frozen Kahn keeps its invariant: a node it never emitted
                # still has an incoming edge from a node it never emitted. Checked rather than
                # assumed, in the same spirit as `aipw_bootstrap_ci`'s unreachable index guard —
                # and reported rather than left as a silent `-1` pair, because "not a DAG,
                # address withheld" is the exact defect this walk exists to remove. The status
                # is REUSED and not borrowed (base.mojo: all twenty codes are assigned): the
                # cycle could not be identified from the declared graph.
                out.status = CI_ERR_NOT_IDENTIFIED
                break
            prev = cur
            cur = nxt
            steps += 1
    return out^


def _sorted_int_copy(a: _Adj, lo: Int, hi: Int) -> List[Int]:
    """Ascending copy of `a.child_idx[lo:hi]` by insertion sort. Internal; spans here are one
    node's out-degree, so the quadratic term is per node and not per graph."""
    var out = List[Int](capacity=hi - lo if hi > lo else 1)
    for t in range(lo, hi):
        out.append(a.child_idx[t])
    for i in range(1, len(out)):
        var v = out[i]
        var j = i - 1
        while j >= 0 and out[j] > v:
            out[j + 1] = out[j]
            j -= 1
        out[j + 1] = v
    return out^


# ── d_separated ──────────────────────────────────────────────────────────────


def d_separated(
    edge_from: List[Int], edge_to: List[Int], n_nodes: Int,
    x_nodes: List[Int], y_nodes: List[Int], z_nodes: List[Int],
) -> DSepReport:
    """Are X and Y d-separated by Z in the declared DAG? With a witness path when not.

    The graph must be acyclic: d-separation is defined on a DAG and the Bayes-Ball recursion
    over a cyclic graph is not the criterion any textbook states, so a cycle is
    `CI_ERR_NOT_A_DAG` rather than an answer. Use `dag_validate` for the edge on the cycle.

    The three node sets must be pairwise DISJOINT and internally duplicate-free
    (`CI_ERR_DUPLICATE`). Overlap makes the query degenerate — a node is not separated from
    itself, and a node in both Y and Z has been conditioned on and asked about at once — and
    guessing which reading the caller meant is how a wrong answer acquires a plausible status.

    Empty X or empty Y is `separated = True` with `has_answer = True`: there is no path from
    nothing to anything. That is a real answer, not an absence.

    @capability d_separated
    complexity: O(n_nodes + n_edges)
    counts:
    - dim n_nodes [kernel_validated]
    @endcapability
    """
    var defect = _edge_defect(edge_from, edge_to, n_nodes)
    if defect != CI_OK:
        return DSepReport(defect)

    # Acyclicity BEFORE the CSR, so a cyclic graph never allocates the twelve n-length arrays.
    if not _acyclic(edge_from, edge_to, n_nodes):
        return DSepReport(CI_ERR_NOT_A_DAG)
    var a = _build_adj(edge_from, edge_to, n_nodes, DAG_NO_NODE)

    var xm = _empty_mask(n_nodes)
    var ym = _empty_mask(n_nodes)
    var zm = _empty_mask(n_nodes)
    var d1 = _mask_defect(x_nodes, n_nodes, xm)
    if d1 != CI_OK:
        return DSepReport(d1)
    var d2 = _mask_defect(y_nodes, n_nodes, ym)
    if d2 != CI_OK:
        return DSepReport(d2)
    var d3 = _mask_defect(z_nodes, n_nodes, zm)
    if d3 != CI_OK:
        return DSepReport(d3)
    for i in range(n_nodes):
        var count = 0
        if xm[i]:
            count += 1
        if ym[i]:
            count += 1
        if zm[i]:
            count += 1
        if count > 1:
            return DSepReport(CI_ERR_DUPLICATE)

    var anc = _ancestor_of_z_mask(a, zm)
    return _reachable_with(a, xm, zm, anc, ym)


def _empty_mask(n: Int) -> List[Bool]:
    var m = List[Bool](capacity=n if n > 0 else 1)
    for _ in range(n):
        m.append(False)
    return m^


def _acyclic(edge_from: List[Int], edge_to: List[Int], n_nodes: Int) -> Bool:
    """Acyclicity via the frozen `graph.algorithms.topological_sort`. Endpoints must already
    be validated — `graph_add_edge` range-checks nothing."""
    var g = graph_new(n_nodes)
    for k in range(len(edge_from)):
        graph_add_edge(g, edge_from[k], edge_to[k], 1.0)
    return len(topological_sort(g)) == n_nodes


# ── backdoor_check ───────────────────────────────────────────────────────────


def backdoor_check(
    edge_from: List[Int], edge_to: List[Int], n_nodes: Int,
    treatment: Int, outcome: Int, adjustment: List[Int],
) -> BackdoorReport:
    """Does adjusting for `adjustment` identify the effect of `treatment` on `outcome`?

    BOTH halves of the backdoor criterion are checked, and the docstring on `BackdoorReport`
    states them in full because rule 4d makes an incomplete certificate worse than none:
    no adjustment node may be a descendant of the treatment, AND the set must block every
    backdoor path. The second is tested as d-separation of `treatment` from `outcome` in the
    graph with the treatment's OUTGOING edges deleted — the standard equivalent, and linear
    where path enumeration is exponential.

    `identified = False` is returned under `CI_ERR_NOT_IDENTIFIED`, with `unblocked_path`
    carrying an open backdoor path and `first_descendant` naming a violating adjustment node.
    That is the point of the module: the caller gets the reason, not a boolean, and gets NO
    estimate. Estimating anyway is the single most damaging thing this package could do.

    `treatment == outcome` is `CI_ERR_DUPLICATE`; an adjustment set containing either is
    `CI_ERR_DUPLICATE` too, since conditioning on the treatment or the outcome is not an
    adjustment. A cyclic graph is `CI_ERR_NOT_A_DAG`.

    @capability backdoor_check
    complexity: O(n_nodes + n_edges)
    counts:
    - dim n_nodes [kernel_validated]
    @endcapability
    """
    var defect = _edge_defect(edge_from, edge_to, n_nodes)
    if defect != CI_OK:
        return BackdoorReport(defect)
    if treatment < 0 or treatment >= n_nodes or outcome < 0 or outcome >= n_nodes:
        return BackdoorReport(CI_ERR_INDEX)
    if treatment == outcome:
        return BackdoorReport(CI_ERR_DUPLICATE)
    if not _acyclic(edge_from, edge_to, n_nodes):
        return BackdoorReport(CI_ERR_NOT_A_DAG)

    var zm = _empty_mask(n_nodes)
    var zdefect = _mask_defect(adjustment, n_nodes, zm)
    if zdefect != CI_OK:
        return BackdoorReport(zdefect)
    if zm[treatment] or zm[outcome]:
        return BackdoorReport(CI_ERR_DUPLICATE)

    var out = BackdoorReport(CI_OK)
    out.n_adjustment = len(adjustment)

    # (i) no adjustment node may be a descendant of the treatment.
    var full = _build_adj(edge_from, edge_to, n_nodes, DAG_NO_NODE)
    var desc = _descendant_mask(full, treatment)
    for i in range(len(adjustment)):
        var v = adjustment[i]
        if desc[v]:
            out.n_descendant_violations += 1
            if out.first_descendant == DAG_NO_NODE:
                out.first_descendant = v

    # (ii) Z blocks every backdoor path, i.e. T is d-separated from Y given Z in G with the
    # edges OUT of T deleted.
    var pruned = _build_adj(edge_from, edge_to, n_nodes, treatment)
    var anc = _ancestor_of_z_mask(pruned, zm)
    var tm = _empty_mask(n_nodes)
    tm[treatment] = True
    var ym = _empty_mask(n_nodes)
    ym[outcome] = True
    var sep = _reachable_with(pruned, tm, zm, anc, ym)
    out.blocks_backdoor_paths = sep.separated
    if not sep.separated:
        out.n_open_backdoor_paths_found = 1
        out.unblocked_path = sep.path_nodes.copy()

    out.has_verdict = True
    out.identified = out.blocks_backdoor_paths and out.n_descendant_violations == 0
    if not out.identified:
        out.status = CI_ERR_NOT_IDENTIFIED
    return out^


# ── backdoor_minimal_set ─────────────────────────────────────────────────────


def backdoor_minimal_set(
    edge_from: List[Int], edge_to: List[Int], n_nodes: Int,
    treatment: Int, outcome: Int, candidates: List[Int],
) -> AdjustmentSet:
    """A MINIMAL sufficient adjustment set out of `candidates`, or a refusal.

    Three phases, and the middle one is what makes the search worth trusting:

      1. Filter by validity — a candidate that is the treatment, the outcome, or a DESCENDANT
         of the treatment can never appear in a valid backdoor set, so it is dropped and
         counted in `n_dropped_descendant`.
      2. Filter to the ANCESTRAL (canonical) pool — a candidate that is not an ancestor of the
         treatment or of the outcome is dropped and counted in `n_dropped_non_ancestral`. This
         is the standard canonical-adjustment-set restriction and it is not an optimisation:
         dropping non-ancestors from a valid set leaves it valid, while KEEPING them can
         destroy validity, because a non-ancestor in the pool is typically a collider whose
         inclusion OPENS a path. Without this step the deletion filter below starts from a
         pool that fails, and M-bias — where the empty set is valid and `{M}` is not — is
         refused. Measured: it was, before this step existed.
      3. Shrink — each retained member is provisionally removed and the criterion re-checked.
         Removal is kept only if the smaller set still blocks. Every retained member has
         therefore been individually SHOWN necessary, which is what `minimality_measured`
         claims; `n_checks` reports how many d-separation calls that took. Minimality is
         w.r.t. single-element removal (a locally minimal set), not the globally smallest
         set — stated here rather than implied, because the two differ and a caller reading
         "minimal" would assume the stronger one.

    A REFUSAL IS NOT A PROOF OF NON-EXISTENCE. `CI_ERR_NOT_IDENTIFIED` here means the ancestral
    pool does not satisfy the criterion, not that no subset of `candidates` does. Sufficiency is
    non-monotone (see M-bias above), so an exhaustive subset search is exponential and is not
    attempted; `AdjustmentSet`'s docstring states the boundary. `backdoor_check` on a named set
    is the conclusive verdict.

    Deterministic: candidates are considered in the order given, so the same pool yields the
    same set every time. Work is `(len(candidates) + 1)` linear d-separations, bounded because
    `len(candidates) <= n_nodes` is enforced through the duplicate check.

    @capability backdoor_minimal_set
    complexity: O(len(candidates) * (n_nodes + n_edges))
    counts:
    - dim n_nodes [kernel_validated]
    @endcapability
    """
    var defect = _edge_defect(edge_from, edge_to, n_nodes)
    if defect != CI_OK:
        return AdjustmentSet(defect)
    if treatment < 0 or treatment >= n_nodes or outcome < 0 or outcome >= n_nodes:
        return AdjustmentSet(CI_ERR_INDEX)
    if treatment == outcome:
        return AdjustmentSet(CI_ERR_DUPLICATE)
    if not _acyclic(edge_from, edge_to, n_nodes):
        return AdjustmentSet(CI_ERR_NOT_A_DAG)

    var dupe = _empty_mask(n_nodes)
    var cdefect = _mask_defect(candidates, n_nodes, dupe)
    if cdefect != CI_OK:
        return AdjustmentSet(cdefect)

    var out = AdjustmentSet(CI_OK)
    out.n_candidates = len(candidates)

    var full = _build_adj(edge_from, edge_to, n_nodes, DAG_NO_NODE)
    var desc = _descendant_mask(full, treatment)
    # An(T) union An(Y), inclusive. `_ancestor_of_z_mask` walks parents from a seed mask, which
    # is exactly this set when the seed is {T, Y}.
    var endpoints = _empty_mask(n_nodes)
    endpoints[treatment] = True
    endpoints[outcome] = True
    var ancestral = _ancestor_of_z_mask(full, endpoints)
    var keep = List[Int]()
    for i in range(len(candidates)):
        var v = candidates[i]
        if v == treatment or v == outcome or desc[v]:
            out.n_dropped_descendant += 1
            continue
        if not ancestral[v]:
            out.n_dropped_non_ancestral += 1
            continue
        keep.append(v)

    var pruned = _build_adj(edge_from, edge_to, n_nodes, treatment)
    var tm = _empty_mask(n_nodes)
    tm[treatment] = True
    var ym = _empty_mask(n_nodes)
    ym[outcome] = True

    var active = List[Bool](capacity=len(keep) if len(keep) > 0 else 1)
    for _ in range(len(keep)):
        active.append(True)

    var first = _blocks(pruned, tm, ym, keep, active, n_nodes)
    out.n_checks += 1
    if not first.separated:
        out.status = CI_ERR_NOT_IDENTIFIED
        out.identified = False
        out.has_set = False
        out.chosen = List[Int]()
        return out^

    for i in range(len(keep)):
        active[i] = False
        var trial = _blocks(pruned, tm, ym, keep, active, n_nodes)
        out.n_checks += 1
        if trial.separated:
            out.n_dropped_redundant += 1
        else:
            active[i] = True

    var chosen = List[Int]()
    for i in range(len(keep)):
        if active[i]:
            chosen.append(keep[i])
    out.chosen = chosen^
    out.identified = True
    out.has_set = True
    out.minimality_measured = True
    return out^


def _blocks(
    pruned: _Adj, tm: List[Bool], ym: List[Bool],
    keep: List[Int], active: List[Bool], n_nodes: Int,
) -> DSepReport:
    """One backdoor-blocking test for the currently active subset of `keep`.

    The Z-ancestor mask is recomputed here on purpose: Z changes on every trial, and Phase I
    depends on Z. Caching it across trials would silently answer a collider question about a
    different conditioning set — the exact shape of rule 4d's incomplete check.
    """
    var zm = _empty_mask(n_nodes)
    for i in range(len(keep)):
        if active[i]:
            zm[keep[i]] = True
    var anc = _ancestor_of_z_mask(pruned, zm)
    return _reachable_with(pruned, tm, zm, anc, ym)


# ── reachability helpers a caller will want ──────────────────────────────────


def dag_descendants(
    edge_from: List[Int], edge_to: List[Int], n_nodes: Int, root: Int
) -> List[Int]:
    """Ascending node ids reachable from `root` along the arrows, INCLUDING `root`.

    Empty on any structural defect, which a caller distinguishes from "no descendants" by the
    fact that `root` itself is always present in a real answer. Exported because "is this
    variable downstream of the treatment?" is the question behind half of all adjustment-set
    mistakes, and because a caller can then check `backdoor_check`'s descendant verdict
    independently.

    @capability dag_descendants
    complexity: O(n_nodes + n_edges)
    counts:
    - dim n_nodes [kernel_validated]
    @endcapability
    """
    if _edge_defect(edge_from, edge_to, n_nodes) != CI_OK:
        return List[Int]()
    if root < 0 or root >= n_nodes:
        return List[Int]()
    var a = _build_adj(edge_from, edge_to, n_nodes, DAG_NO_NODE)
    var mask = _descendant_mask(a, root)
    var out = List[Int]()
    for i in range(n_nodes):
        if mask[i]:
            out.append(i)
    return out^


def dag_ancestors(
    edge_from: List[Int], edge_to: List[Int], n_nodes: Int, root: Int
) -> List[Int]:
    """Ascending node ids that reach `root` along the arrows, INCLUDING `root`.

    @capability dag_ancestors
    complexity: O(n_nodes + n_edges)
    counts:
    - dim n_nodes [kernel_validated]
    @endcapability
    """
    if _edge_defect(edge_from, edge_to, n_nodes) != CI_OK:
        return List[Int]()
    if root < 0 or root >= n_nodes:
        return List[Int]()
    var a = _build_adj(edge_from, edge_to, n_nodes, DAG_NO_NODE)
    var single = _empty_mask(n_nodes)
    single[root] = True
    var mask = _ancestor_of_z_mask(a, single)
    var out = List[Int]()
    for i in range(n_nodes):
        if mask[i]:
            out.append(i)
    return out^
