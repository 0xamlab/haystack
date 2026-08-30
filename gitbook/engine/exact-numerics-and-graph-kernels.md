---
icon: weight-scale
description: Double-double error-free-transform arithmetic and compensated Householder least squares, plus explicit-graph traversal, shortest paths, MST, and union-find.
---

# Exact numerics and graph kernels

Four modules for two unrelated problems that happen to share this page because of how the
runtime's dotted namespaces group them. `exactnum.eft` and `exactnum.lstsq` are about
**precision**: an error-free transformation returns a float64 operation's rounded result
together with the exact rounding error it dropped, and stacking two of them (Knuth's
`two_sum`, Dekker's `two_product`) builds a "double-double" number format with roughly twice
float64's significand — enough to carry a Householder QR least-squares factorisation through
an ill-conditioned design matrix without losing the digits a plain float64 solver would.
`graph.algorithms` and `graph.weighted` are about **traversal**: build an explicit graph node
by node or edge by edge, then run Dijkstra, BFS/DFS, topological sort, connected components,
Kruskal's MST, Floyd-Warshall, Bellman-Ford, or union-find over it. Nothing here shares state
or a status vocabulary across the two pairs — they are documented together because the
runtime's library catalog groups them together, not because the arithmetic and the graphs
depend on each other.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# 2^53 + 1 rounds down to 2^53 in plain float64 -- the "+1" is thrown away.
# eft_two_sum recovers it exactly as the error term instead of losing it.
r = runtime.execute("exactnum.eft", "eft_two_sum", [9007199254740992.0, 1.0])["result"]
r["hi"], r["lo"]
# (9007199254740992.0, 1.0) -- hi + lo reproduces the exact sum, bit for bit

# Triangle 0-1 (1.0), 1-2 (2.0), 0-2 (4.0): Kruskal keeps the two cheapest edges
edges = [{"src": 0, "dst": 1, "weight": 1.0},
         {"src": 1, "dst": 2, "weight": 2.0},
         {"src": 0, "dst": 2, "weight": 4.0}]
mst = runtime.execute("graph.weighted", "kruskal_mst", [3, edges])["result"]
runtime.execute("graph.weighted", "mst_total_weight", [mst])["result"]
# 3.0 -- edges 0-1 and 1-2 are kept, the redundant 4.0 edge is dropped
```

## The modules

| Module | What it does |
| --- | --- |
| `exactnum.eft` | Error-free transformations and double-double (`DD`) arithmetic: `two_sum`, `two_product`, `dd_add/sub/mul/div/sqrt`, a runtime self-check of the FMA/reassociation assumptions everything else rests on, and compensated `Sum2`/`Dot2` reductions. |
| `exactnum.lstsq` | Compensated Householder QR least squares carried in double-double: a flat row-major driver, float64 and polynomial-basis variants (raw and NumPy-style centred/scaled), dimension and work-budget guards, and the per-column dependent-pivot floor. |
| `graph.algorithms` | An explicit adjacency-list `Graph` you build with `graph_new`/`graph_add_edge`, then run Dijkstra, BFS, DFS, Kahn's topological sort, connected components, or reconstruct an actual shortest path over. |
| `graph.weighted` | The same traversal family expressed over a plain `List[WeightedEdge]` instead of a built `Graph`: Kruskal's MST, Floyd-Warshall all-pairs, Bellman-Ford (negative edges allowed), negative-cycle detection, and union-find. |

## `exactnum.eft`: the two transformations everything else is built from

`eft_two_sum(a, b)` and `eft_two_product(a, b)` each return a `DD { hi, lo }` such that
`hi + lo` is the *exact*, infinitely-precise result of `a + b` or `a * b` — not an
approximation to it. `hi` is the ordinary float64 you'd get from `a + b`; `lo` is whatever
that rounding step threw away. The module's own runtime self-check,
`eft_selfcheck_code()`, exists because that guarantee depends on assumptions a future
toolchain could silently break — a non-fused FMA, a compiler that contracts two separate
multiplies into one, or reassociated addition — and a routine that has quietly degraded to
plain float64 still passes any test whose expected value plain float64 already gets right.
So the module's own hand-written test suite (`mojo/tests/libs/test_exactnum_eft.mojo`, golden
values from exact `Fraction` rational arithmetic and mpmath, never from a float64 snapshot of
the implementation) is built around cases where **plain float64 is provably wrong**:

* `eft_two_sum(2^53, 1.0)` returns `DD(hi=9007199254740992.0, lo=1.0)`. Plain `2**53 + 1.0`
  rounds to `2**53` in float64 — round-half-to-even lands exactly on the value below — and
  `eft_two_sum` is the one that keeps the `1.0` instead of discarding it.
* `Sum2` over `[2^53, 1, -1, 2^53]` followed by 500 more `1.0`s (504 terms) is exactly
  `2^54 + 500`. Sequential float64 addition returns exactly `2^54`, losing all 500 ones —
  `Sum2` recovers every one of them.
* `Dot2` of `x = [2^53, 1, 1, -2^53]` against `y = [1, 1, 1, 1]` is exactly `2.0`. A plain
  float64 dot product, summed left to right, returns exactly `0.0` — the `2^53` and `-2^53`
  terms cancel before the two `1`s ever get to contribute.
* `eft_two_product((1 + 2^-52)^2)`'s error term is exactly `2^-104`, and the same expression
  computed without a fused multiply-add (`(a*a) - (a*a)`, forcing two separate roundings)
  gives exactly `0.0` — the anti-vacuity case a degraded, non-FMA build cannot pass by luck.

Double-double arithmetic composes from there: `dd_add(A, B)` where `A = eft_two_product(0.1,
0.3)` (`DD(hi=0.03, lo≈1.665e-18)`, the exact product of the *rounded* floats 0.1 and 0.3) and
`B = eft_two_product(0.3, 0.7)` (`DD(hi=0.21, lo≈-1.332e-17)`) returns `hi = 0.24` together
with a residual, correctly rounded and accurate to better than `2^-100` relative — the test
suite checks this against the exact rational value, not against a second copy of the same
arithmetic. `dd_sqrt` returns a `NaN` pair for a negative radicand rather than inventing a
root, and `0.0` (not `NaN`) for `sqrt(0)`, because a real zero answer must never be
indistinguishable from an absent one. `eft_kahan_sum_f64` is not a rewrite of Kahan summation:
it forwards to the tree's one frozen `numerical_stability.kahan_sum`, so a caller comparing
`Sum2`'s double-double result against "compensated float64" is comparing against the shipped
kernel and not a private reimplementation of it.

`eft_dot2` and `eft_sum2` validate their element count against **both** real buffer lengths
and against `EFT_MAX_TERMS` (`1 << 26`, the same ~512 MB per-object budget used elsewhere in
the runtime) before reading a single element, and refuse a NaN or infinite input before it can
poison a reduction — an unchecked count past the end of a list is an uncatchable abort that
takes the whole worker down, not a catchable error, so the check has to happen before the
first read. `eft_status_name` covers the seven codes `eft` owns in the range **800-809**;
`exactnum.lstsq` owns the adjacent 810-819 and forwards an `eft` status unchanged when that's
the real cause of a refusal, rather than relabelling an arithmetic-assumption failure as a
least-squares condition. One real downstream consumer: `progexec.roundexact` uses
`eft_two_product` and `eft_two_sum` to round a value to a fixed number of decimal places
without the double-rounding a naive `round(x * scale) / scale` introduces — see
[Program execution & scoring](program-execution-scoring.md) for the mechanism.

## `exactnum.lstsq`: compensated Householder QR

`dd_lstsq_flat(a, rows, cols, b, refine)` solves a linear least-squares problem — `a` is the
`rows * cols` design matrix, row-major, and `b` is the length-`rows` response — by Householder
QR with every intermediate quantity (reflector norms, `R`, `Qᵀb`, the back substitution) carried
in double-double rather than float64. `f64_lstsq_flat` is a byte-for-byte transcription of the
same algorithm — same pivot order, same reflector sign rule, same `vᵀv`-by-summation — in plain
float64, so that any difference between the two arms is attributable to the arithmetic and to
nothing else. `dd_poly_lstsq` and `f64_poly_lstsq` fit a power-basis polynomial
`Σ β_k x^k` for `k` from `lo_deg` to `hi_deg` directly; `dd_poly_lstsq_scaled` fits in the
centred, `[-1, 1]`-scaled basis `numpy.polynomial.Polynomial.fit` uses (byte-identical
`mapparms` domain map), then maps the coefficients back to the original parameterisation.

The load-bearing test in `mojo/tests/libs/test_exactnum_lstsq.mojo` needs no external reference
at all: fit `y_i = Σ_{k=0}^{5} x_i^k` at `x = 0, 1, …, 20`. Every design-matrix entry (up to
`20^5 = 3,200,000`) and every response value is an integer well inside float64's exact `2^53`
grid, so the system is represented exactly and the true least-squares solution is provably the
vector of six ones — no rounding assumption, no NIST file needed to know the right answer.

```python
x = [float(i) for i in range(21)]
y = [sum(x[i] ** k for k in range(6)) for i in range(21)]

r = runtime.execute("exactnum.lstsq", "dd_poly_lstsq",
                    [x, y, 21, 0, 5, True, 0])["result"]
r["status"], r["coefficients"]
# (810, [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]) -- exact, all six components

f64 = runtime.execute("exactnum.lstsq", "f64_poly_lstsq",
                      [x, y, 21, 0, 5, False])["result"]
f64["coefficients"]
# NOT all 1.0 -- the identical algorithm in plain float64 loses digits on the same,
# exactly-representable system
```

`dd_powers` is a separate lever from the precision of the solve itself: it selects whether the
polynomial's powers of `x` are formed by repeated **float64** multiplication (the design matrix
itself already loses information before the solver ever sees it) or by repeated
**double-double** multiplication from the same float64 `x` — never worse, because on data whose
powers are already exact in float64 the two are bit-identical.

Every result carries `rank`, `r_diag_min` (`min_i |R[i,i]|`), `pivot_ratio_min` (the same
quantity divided by that column's own norm — the scale-free, per-column version, deliberately
*not* an aggregate like `max_k |R[k,k]|` or `‖A‖`, which would let one column's units pay for
another's comparison), `residual_norm`, and `refine_steps`. A dependent column — the module's
test uses a matrix with a literally duplicated column — returns `LSTSQ_ERR_RANK_DEFICIENT`
(status `818`) with **empty** coefficient lists, never a vector of zeros: the frozen
`linalg.mat_solve` returns an all-zeros vector for a singular system, which makes "the answer is
zero" and "there is no answer" the same return value, and this driver refuses to repeat that
confusion. `dd_poly_lstsq_scaled` similarly refuses (`LSTSQ_ERR_BASIS_NOT_APPLICABLE`, `819`)
rather than approximate when every `x` value is identical — the conditioned basis's domain map
divides by the span, and centring is a reparameterisation of the *whole* polynomial space that a
no-intercept model (`lo_deg > 0`) has no correct inverse for.

Both product-shaped budgets — `lstsq_cells_fit(rows, cols, ceiling)` for `rows * cols` and
`lstsq_work_fits(rows, cols, ceiling)` for `rows * cols * cols` — are checked by division
(`cols <= ceiling // rows`), not by computing the product first: `3 * 6148914691236517206 == 2`
under 64-bit wraparound is how an equivalent guard was walked past elsewhere in the tree. The
full NIST StRD accuracy numbers this solver produces — up to 15.95 correct digits, versus
`numpy.linalg.lstsq`'s default `rcond` scoring 0.00 on the worst-conditioned dataset because it
truncates a rank nobody asked it to truncate — are measured in
[Least-squares accuracy](../benchmarks/least-squares-accuracy.md), which calls these same two
functions through the same `runtime.execute` interface used here.

## `graph.algorithms`: traversal over an explicit `Graph`

`graph_new(n)` returns a `Graph` with `n` nodes and no edges; `graph_add_edge(g, from_node,
to_node, weight)` appends one directed, weighted edge, silently doing nothing if either
endpoint is out of `[0, n)` rather than raising. Every traversal function — `dijkstra`, `bfs`,
`dfs`, `topological_sort`, `connected_components`, `shortest_path` — first checks that the
graph's adjacency structure actually matches `n_nodes` and that every stored neighbor index
lies in range, because a neighbor index is used directly to index a `dist`/`visited`/`label`
array a line later: an unvalidated one would be an uncatchable out-of-bounds abort rather than
a wrong answer. A malformed graph gets an empty result back, not a crash.

`graph_add_edge` takes `g` by mutable reference, and mutation crosses the SDK boundary as a
returned value rather than in place: the call's primary `result` is `None`, and the updated
graph comes back under `mutated_args.g` in the same response, which the caller feeds into the
next call. `graph.weighted`'s `union_find_find`/`union_find_union` mutate their `parent` array
the same way, under `mutated_args.parent`.

```python
g = runtime.execute("graph.algorithms", "graph_new", [5])["result"]
for src, dst, w in [(0, 1, 4.0), (0, 2, 1.0), (2, 1, 2.0), (1, 3, 1.0), (2, 3, 5.0)]:
    g = runtime.execute("graph.algorithms", "graph_add_edge",
                        [g, src, dst, w])["result"]["mutated_args"]["g"]

dist = runtime.execute("graph.algorithms", "dijkstra", [g, 0])["result"]
dist[1]   # 3.0 -- 0->2->1 costs 1.0 + 2.0, cheaper than the direct 0->1 edge (4.0)
dist[3]   # 4.0 -- 0->2->1->3 costs 1.0 + 2.0 + 1.0

comp = runtime.execute("graph.algorithms", "connected_components", [g])["result"]
comp[0] == comp[1] == comp[2] == comp[3]   # True -- nodes 0-3 are reachable from each other
comp[4] != comp[0]                          # True -- node 4 has no edges, its own component
```

Both numeric assertions above (`dist[1] == 3.0`, `dist[3] == 4.0`) are the real, hand-written
values pinned in `tests/mojo/test_wave11.mojo`. `topological_sort` runs Kahn's algorithm and,
traced by hand against this same graph, returns `[0, 4, 2, 1, 3]` — every node with in-degree
zero at the start (`0` and `4`) enters the queue first, then each edge relaxation adds the next
node whose in-degree just hit zero; on a graph with a cycle it returns a **partial** ordering,
silently omitting the nodes the cycle involves rather than raising. `shortest_path(g, source,
target)` reruns Dijkstra with predecessor tracking and reconstructs the actual node sequence
(empty list if `target` is unreachable), distinct from `dijkstra`, which only returns
distances. `connected_components` treats the graph as **undirected** for this purpose —
building a symmetric adjacency from the directed edges before labelling — which is why nodes 0
through 3 above land in one component even though not every pair has a direct edge in both
directions.

## `graph.weighted`: MST, all-pairs, negative edges, and union-find

The same shortest-path and traversal family, but taking a plain `List[WeightedEdge]` (each
edge a `{src, dst, weight}` value) instead of a built `Graph` — no `graph_new` call, no
mutation. `kruskal_mst(n_nodes, edges)` sorts edges by weight (insertion sort) and adds each
one via `union_find_union` unless it would close a cycle, stopping once `n_nodes - 1` edges are
kept; `mst_total_weight` sums an MST's edge weights. On the triangle `0-1 (1.0)`, `1-2 (2.0)`,
`0-2 (4.0)` from the top of this page, the MST keeps exactly 2 edges totalling `3.0` — both
numbers pinned in `tests/mojo/test_wave36.mojo`.

`floyd_warshall(n, edges)` returns the full `n × n` all-pairs distance matrix by dynamic
programming over intermediate nodes; `bellman_ford(n, edges, source)` and
`shortest_path_dijkstra(n, edges, source)` are two different routes to the same single-source
distances, and they agree with each other only when every weight is non-negative — Bellman-Ford
tolerates negative edges (allowing `n - 1` relaxation rounds over every edge), Dijkstra's greedy
choice does not. On the directed triangle `0-1 (1.0)`, `1-2 (2.0)`, `0-2 (10.0)`, both routes
agree that node 2 is reached via node 1 at cost `3.0`, cheaper than the direct `10.0` edge —
`floyd_warshall`'s `[0][2]` entry, `bellman_ford`'s and `shortest_path_dijkstra`'s node-2
distance are all `3.0`. `has_negative_cycle(n, edges)` runs Bellman-Ford from node 0 and checks
whether a further relaxation round would still find an improvement; on that same triangle it's
`False`, and on `0→1 (1.0)`, `1→2 (-3.0)`, `2→0 (1.0)` — a cycle summing to `-1.0` — it's `True`.

`union_find_create(n)` returns each node as its own parent (`[0, 1, …, n-1]`);
`union_find_find` walks the parent chain with path compression, refusing (returning `-1`)
rather than looping forever if a malformed parent array forms a cycle or points out of range —
it walks the chain once, counting steps, and gives up past `len(parent)` hops rather than
trusting the array's own shape; `union_find_union` merges two sets by attaching one root under
the other and returns `True` only when the two elements started in different sets. This is the
same union-find `kruskal_mst` calls internally, and `union_find_find` is the one function in
this pair with an explicit count-relation contract entry binding its `x` argument to `parent`'s
length — the same dimension-safety discipline `eft_dot2`/`eft_sum2` enforce by hand above.

## A same-named module that is not this one

The runtime also ships a bare, undotted `graph_algorithms` module
(`mojo/engine/graph_algorithms.mojo`) — not documented on this page, and not the same thing. Its functions
(`dijkstra_relax`, `bellman_ford_relax`, `pagerank_update`, `betweenness_centrality_norm`, and
similar) are single-step *formulas* a traversal would call once per edge or once per iteration,
the same "one step, not the whole algorithm" shape
[Graph-based reasoning kernels](graph-based-reasoning-kernels.md) describes for `graph_decision`
and `graph_compiler`.
The name collision is real enough that the runtime's own test generator has to guard against
it: `graph.algorithms` (this page's dotted module) and `graph_algorithms` (the bare one) both
naively sanitise to the same identifier, and a comment in
`scripts/generate_runtime_library_dispatch.py` records that this previously produced two
functions named `_dispatch_graph_algorithms` before the generator was fixed to keep dotted and
bare namespaces distinct. Two other existing pages already point at this page's modules by
name without documenting them: [Sparse systems & graph analytics](sparse-and-graph.md) sends a
reader to `graph.weighted.bellman_ford` for negative-weight graphs (its own
`graph_analytics.adjacency.graph_csr_dijkstra_driver` declines rather than returning a
confidently wrong answer) and contrasts Louvain communities against
`graph.algorithms.connected_components`;
[Graph-based reasoning kernels](graph-based-reasoning-kernels.md) points to
`graph.weighted.bellman_ford` for the same reason. Neither page documents the functions
themselves — this page is where that lives.

## Verification

`exactnum.eft` and `exactnum.lstsq` have real, hand-written golden-vector suites
(`mojo/tests/libs/test_exactnum_eft.mojo`, `test_exactnum_lstsq.mojo`) built from exact
`Fraction` rational arithmetic and mpmath, deliberately including cases plain float64
provably cannot pass — the worked examples above are drawn directly from those goldens.
`graph.algorithms` and `graph.weighted` each have their own dedicated test file
(`mojo/tests/libs/test_graph_pkg_algorithms.mojo`, `test_graph_weighted.mojo`), but both are
auto-generated coverage smoke tests: each calls one function once (`graph_new(5)`,
`union_find_create(5)`) and checks only that it doesn't crash, with no pinned numeric output.
The real hand-verified assertions for both graph modules live instead in
`tests/mojo/test_wave11.mojo` (Graph, dijkstra, bfs, dfs, topological_sort,
connected_components, shortest_path) and `tests/mojo/test_wave36.mojo` (kruskal_mst,
mst_total_weight, floyd_warshall, bellman_ford, has_negative_cycle, shortest_path_dijkstra,
union-find) — every dijkstra distance, MST weight, and Floyd-Warshall entry given above is
pinned in one of those two files, and the topological-sort order and connected-components
example were hand-traced against the real source in `mojo/engine/graph/algorithms.mojo` and
independently re-run to confirm.

**Next:** see [Least-squares accuracy](../benchmarks/least-squares-accuracy.md) for the full
NIST StRD correct-digit table these two `exactnum` drivers produce, or
[Sparse systems & graph analytics](sparse-and-graph.md) for the compressed-adjacency traversal
family (`graph_analytics.*`) that sits next to `graph.algorithms` and `graph.weighted` in the
runtime's library list.
