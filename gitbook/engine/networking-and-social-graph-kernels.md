---
icon: share-nodes
description: HTTP/URL protocol primitives, undirected and directed graph-metric arithmetic over adjacency lists, and the scalar cost formulas behind multi-GPU collective communication.
---

# Networking and social graph kernels

Four modules for three problems that share this page but not much else. `network_protocol` is
web-protocol plumbing — HTTP status text, MIME types, and query-string building/parsing — a
pure-Mojo stand-in for Python's `http.client`, `mimetypes`, and `urllib.parse`; despite the name,
there is no socket, no packet, and no topology anywhere in it. `network_analysis` and
`social_network` are graph-metric arithmetic over plain `List[List[Int]]` adjacency lists, with no
graph-builder object in between: the first assumes an undirected graph (degree, density, PageRank,
degree/closeness centrality, clustering, connectivity, BFS distances), the second a directed one
(in/out-degree, reciprocity, directed clustering, strong connectivity, Independent-Cascade influence
spread, label-propagation communities). `distributed_collectives` is the ML-training-infrastructure
member of the group the hint expected: alpha-beta latency models, ring/tree all-reduce step
arithmetic, gradient-compression ratios, and MoE dispatch-volume sizing — all scalar cost formulas
for planning a collective communication schedule, not an implementation of one. Nothing here
imports anything else on this page.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# A JSON API error path: no table lookup needed, the module already knows the reason phrase
runtime.execute("network_protocol", "http_status_text", [404])["result"]
# "Not Found"

# 8 workers, tree all-reduce: log2(8) = 3 rounds, doubled for reduce + broadcast
runtime.execute("distributed_collectives", "allreduce_tree_step_count", [8.0])["result"]
# 6.0
```

## The modules

| Module | What it does |
| --- | --- |
| `network_protocol` | HTTP status-code reason phrases and 2xx/3xx/4xx/5xx classification, file-extension-to-MIME-type lookup, `Content-Type` header parsing, JSON/text MIME detection, and URL query-string building/parsing. |
| `network_analysis` | Undirected-graph metrics over an adjacency list: degree and its distribution, density, PageRank, degree and closeness centrality, local and average clustering coefficient, connectivity, connected components, and BFS shortest-path distances. |
| `social_network` | Directed-graph metrics over the same kind of adjacency list: in/out-degree, edge reciprocity, Independent-Cascade influence spread, directed local clustering, strong-connectivity check, label-propagation community detection, network density, and a sampled average-path-length estimate. |
| `distributed_collectives` | Scalar cost formulas for multi-GPU/multi-node collectives: ring all-reduce step contribution, reduce-scatter averaging, all-gather offset, broadcast scale, gradient-compression ratio, MoE expert-dispatch byte volume, peer bandwidth utilization, an alpha-beta latency model, compute/comm overlap efficiency, and tree all-reduce step count. |

## `network_protocol`: HTTP and URL primitives, not topology

Reading `mojo/engine/network_protocol.mojo`'s own header confirms the scope directly: it "replaces
Python's `http.client`, `mimetypes`, `urllib.parse` with pure Mojo implementations" — a set of
web-protocol lookup tables and string parsers, not a packet parser, TCP/IP simulator, or anything
that touches a network topology. That is worth stating plainly because "network protocol" is
exactly the name a topology- or packet-flavored module would have, and this one is something
narrower and more mundane.

| Function | What it does |
| --- | --- |
| `http_status_text(code)` | The standard reason phrase for ~27 explicitly-listed codes (`100`-`101`, `200`-`204`, `301`-`308`, `400`-`429`, `500`-`504`); `"Unknown"` for anything else. |
| `is_success` / `is_redirect` / `is_client_error` / `is_server_error(code)` | Plain range checks: `200`-`299`, `300`-`399`, `400`-`499`, `500`-`599`. |
| `mime_type(extension)` | Extension (no dot) to MIME type for over 20 common types; `"application/octet-stream"` for anything unrecognized. |
| `parse_content_type(header)` | Strips a `Content-Type` header down to the bare MIME type, dropping everything from the first `;` onward and trimming surrounding spaces. |
| `is_json_type(mime)` | `True` for `application/json` or anything ending in the `+json` structured-syntax suffix (e.g. `application/vnd.api+json`). |
| `is_text_type(mime)` | `True` iff the string starts with `text/`. |
| `build_query_string(keys, values)` | Joins `key=value` pairs with `&`, over `min(len(keys), len(values))` pairs. |
| `parse_query_string(query)` | Splits on `&`, then on the first `=` in each segment, into `[[key, value], ...]`; a segment with no `=` becomes `[key, ""]`. |

Two codes most other status-code tables treat specially are not in the table by name — `418` and
`451` return `"Unknown"` here, same as any other unlisted code; only the ~27 codes actually written
into the `if` chain get a real phrase.

`http_status_text(429)` returns `"Too Many Requests"`, and `is_client_error(429)` is `True` — the
lookup and the classification are two independent code paths (no shared range table), so a code
missing from one is not automatically consistent with the other; `418` for instance is classified
correctly by `is_client_error` (`True`) despite having no entry in `http_status_text`.

`parse_content_type("application/vnd.api+json; charset=utf-8")` returns
`"application/vnd.api+json"` — semicolon-truncated and space-trimmed — and
`is_json_type("application/vnd.api+json")` is `True` via the `+json` suffix check, not the
exact-match branch.

**`build_query_string` silently truncates on a length mismatch rather than erroring.** Calling it
with three keys (`["q", "limit", "sort"]`) and two values (`["mojo kernels", "25"]`) does not raise
or pad — `n` is clamped to `min(len(keys), len(values)) = 2`, so the result is
`"q=mojo kernels&limit=25"` and `"sort"` disappears from the output with no signal that it was
dropped.

## `network_analysis` and `social_network`: two graph-metric modules, one assumption apart

Both modules take the same shape of input — `List[List[Int]]`, node `i`'s row is its neighbor
list — and neither builds or requires a graph object; that is a real difference from
`graph.algorithms` and `graph_analytics.*`, documented on
[Exact numerics and graph kernels](exact-numerics-and-graph-kernels.md), which construct an
explicit graph via `graph_new`/`graph_csr_build` before running an algorithm over it.
`network_analysis` is written for the adjacency list to already be symmetric (an undirected edge
appears in both endpoints' rows) — `density` divides raw edge-list length by `n*(n-1)`, which is
only the standard undirected density formula because each edge is counted from both sides.
`social_network` makes the opposite assumption: every row is a set of outgoing edges only, and
`in_degree`, `reciprocity`, and the strong-connectivity check all exist specifically because, in a
directed graph, a node's out-row does not tell you its in-edges.

### `network_analysis`

| Function | What it does |
| --- | --- |
| `degree(adj, node)` | `len(adj[node])`; `-1` (a sentinel, not a crash) if `node` is outside `[0, len(adj))`. |
| `degree_distribution(adj)` | Degree of every node, in index order. |
| `density(adj)` | `2E / (V*(V-1))`, assuming `adj` is already symmetric; `0.0` for `V <= 1`. |
| `bfs_distances(adj, start)` | BFS hop-count distances from `start`; `-1` for unreached nodes and for an out-of-range `start`. |
| `pagerank(adj, damping=0.85, max_iter=100, tol=1e-6)` | Standard power-iteration PageRank; `max_iter` is silently clamped to 10,000. |
| `degree_centrality(adj)` | `degree(v) / (n - 1)` per node. |
| `closeness_centrality(adj)` | `(n-1) / Σdistances`, but **only** if every other node was reached — see below. |
| `clustering_coefficient(adj, node)` | Local triangle fraction: `triangles / (k choose 2)` over node's `k` neighbors. |
| `avg_clustering_coefficient(adj)` | Mean of `clustering_coefficient` over all nodes. |
| `is_connected(adj)` | `True` iff a BFS from node `0` reaches every node. |
| `connected_components(adj)` | All components, as a list of node-id lists. |

### `social_network`

| Function | What it does |
| --- | --- |
| `in_degree(adj, node)` | Counts edges `i -> node` by scanning every row; never indexes with `node`, so any integer value is safe and simply returns `0` if `node` names no real node. |
| `out_degree(adj, node)` | `len(adj[node])` — **no bounds guard at all**; see below. |
| `reciprocity(adj)` | Fraction of directed edges `(u, v)` where `(v, u)` also exists. |
| `influence_spread_ic(adj, seeds, p, n_simulations)` | Independent-Cascade Monte Carlo: from `seeds`, each active node activates each inactive out-neighbor independently with probability `p`; returns the mean activated-node count over `n_simulations` runs (clamped to 100,000), each using a fresh `random_float64()` draw per edge attempt. |
| `local_clustering_directed(adj, node)` | `edges_among_neighbors / (k*(k-1))`, over the *union* of in- and out-neighbors (`k` = that union's size), directed edges counted separately in each direction. |
| `strongly_connected_check(adj)` | `True` iff a forward BFS and a reverse-graph BFS, both from node `0`, each reach every node. |
| `community_label_propagation(adj, max_iter)` | Each node adopts its neighbors' (in- and out-) most common label per round, ties broken by first-seen order; stops early on no change, `max_iter` clamped to 100,000. |
| `network_density(adj)` | `E / (V*(V-1))` for a directed graph (no factor of 2 — this is `network_analysis.density`'s counterpart, without the "each edge counted twice" assumption). |
| `average_path_length_estimate(adj, n_samples)` | Mean BFS distance over reachable ordered pairs, sampled from **the first `min(n_samples, n)` nodes by index** — see below. |

## Closeness centrality returns zero for a whole disconnected graph, not just the unreachable part

On a triangle (`adj = [[1,2],[0,2],[0,1]]`), everything here behaves exactly as the textbook
formulas say: `density` is `1.0`, `closeness_centrality` and `degree_centrality` are `1.0` at every
node, `clustering_coefficient` is `1.0` at every node, and `pagerank` converges in a single
iteration to `[1/3, 1/3, 1/3]` because the graph is symmetric under rotation. On a 3-node path
(`adj = [[1],[0,2],[1]]`), `degree_centrality` is `[0.5, 1.0, 0.5]`, `closeness_centrality` is
`[2/3, 1.0, 2/3]`, and `pagerank` settles to `[0.2568, 0.4865, 0.2568]` — the middle node keeps
roughly twice the endpoints' rank.

But split a graph into two components — `adj = [[1],[0],[]]` (edge `0-1`, node `2` isolated) — and
`closeness_centrality` returns `[0.0, 0.0, 0.0]` across the board, rather than `0.0` only for the
truly isolated node `2` and something positive for nodes `0` and `1`, which are still connected to
each other. The guard is `if total > 0 and reachable == n - 1`, and
`reachable == n - 1` requires reaching **every** other node in the whole graph — so nodes `0` and
`1`, which are perfectly connected to each other, still fail the check because neither reaches node
`2`, and both report `0.0` alongside the truly isolated node. This is not a hypothetical
misreading: `mojo/tests/libs/test_graph_analytics_centrality.mojo` builds exactly this shape of
graph, imports `network_analysis.closeness_centrality` explicitly aliased as `frozen_closeness`,
asserts it returns `0.0` for all six nodes of its own six-node three-component test graph, and
says in its own docstring that "the frozen kernel's... zeros are the reason this module
[`graph_analytics.centrality`] exists" — `graph_analytics.centrality.graph_closeness_centrality`
reports per-component values instead. `network_analysis` is the deliberately-kept naive baseline
that the newer module's test suite measures itself against, not a bug nobody noticed.

The same test file draws a second, sharper contrast: `network_analysis.degree_centrality` divides
raw adjacency-row length by `n - 1` with no deduplication, so on a multigraph with two parallel
`0 -> 1` edges, a self-loop `0 -> 0`, and one more distinct edge `0 -> 2`
(`adj = [[1,1,0,2],[0],[]]`), `degree_centrality(adj)[0]` returns `4 / (3-1) = 2.0` — a centrality
score twice the theoretical maximum of `1.0`, because the row's length counts the duplicate edge
and the self-loop as if they were three separate distinct neighbors. `graph_analytics.centrality`'s
degree measure counts distinct neighbors and drops self-loops instead, which is exactly why the
same test asserts `frozen_deg[0] > 1.0` and the newer module's score for the same node `<= 1.0`.

## `out_degree` has no bounds guard; `degree` does

`network_analysis.degree` and `social_network.out_degree` compute the same quantity — the length of
a node's row — but only one of them is safe to call with an untrusted `node`. `degree`'s body opens
with `if node < 0 or node >= len(adj): return -1`, and the source comment names exactly why: "No
such node: absent (-1), not a degree (uncatchable abort below)." `out_degree`'s entire body is
`return len(adj[node])` — no range check anywhere, and no call into `social_network`'s own
`_adj_valid` helper either (that helper validates that every **neighbor value** is in-range, not
the `node` argument itself). Reading the two side by side: `degree(adj, 5)` on a 3-node graph
returns `-1`; `out_degree(adj, 5)` on the same graph indexes `adj[5]` directly, which is the
uncatchable out-of-bounds abort this corpus's other modules go out of their way to guard against.
`in_degree`, by contrast, never needs a guard at all — it only ever compares `adj[i][j] == node`,
so an out-of-range `node` value simply never matches and returns `0`, safely, by construction
rather than by a defensive check.

## Label propagation can oscillate forever instead of converging

Independent tracing of `community_label_propagation` against a symmetric directed 3-cycle
(`adj = [[1],[2],[0]]`, i.e. `0 -> 1 -> 2 -> 0`) turns up a real non-convergent case, verified by
running the exact algorithm in the source by hand and again as an independent script: starting
from labels `[0, 1, 2]`, the labels become `[1, 2, 1]` after round 1, `[2, 1, 2]` after round 2,
`[1, 2, 1]` after round 3, and alternate between those two states every round after — `changed`
never goes `False`, so the loop runs for the full `max_iter` it is given and simply stops wherever
that lands. Calling it with `max_iter = 10` returns `[2, 1, 2]`; `max_iter = 9` (or `11`) would
return `[1, 2, 1]` instead. The function has no cycle detection and no odd/even tie-break rule to
prevent this — on a graph symmetric enough that every node's neighbor-label tally is perpetually
tied, the result depends on the parity of `max_iter` rather than on anything about the graph's real
community structure. This is the same "cheaper alternative" the newer
`graph_analytics.community` module's own test suite (`test_graph_analytics_community.mojo`) treats
`social_network.community_label_propagation` as the baseline for, quoting it directly as "the
oracle for the unambiguous case" that Louvain modularity optimization is compared against and beats
on quality; the oscillation above is a further, independently-confirmed cost of that baseline that
the corresponding test file's own docstring does not itself call out.

## `average_path_length_estimate` samples deterministically, not randomly, despite its own docstring

The module docstring for `average_path_length_estimate` and the function's own docstring both say
"random sample of nodes." The implementation does not do that: the inline comment directly above
the source line reads "Pick source node (sequential for determinism, wraps around)," and the code
is `var source = s % n` — the first `min(n_samples, n)` nodes by index, always starting at `0`, on
every call, with no seed and no randomness anywhere in the function. On the directed path
`0 -> 1 -> 2` (`adj = [[1],[2],[]]`), `average_path_length_estimate(adj, 1)` always returns `1.5`
(node `0`'s BFS alone: distances `1` and `2` to the other two nodes, mean `1.5`), while
`average_path_length_estimate(adj, 2)` and `average_path_length_estimate(adj, 3)` both return
`1.3333...` — adding node `1`'s BFS (one reachable node, distance `1`) pulls the mean down, and
node `2` (unreachable from itself, contributes nothing) never changes the answer once `n_samples`
already covers the first 2 nodes. Passing `n_samples >= n` does not make this a Monte Carlo estimate
at all — with every node sampled exactly once, the "estimate" is the exact mean shortest-path length
over all reachable ordered pairs, not an approximation of it. `influence_spread_ic` in the same
module, by contrast, genuinely is a Monte Carlo simulation — it draws a fresh `random_float64()` per
edge-activation attempt per simulation — so the two functions' names ("estimate" vs. the plainer
"IC model") land, if anything, backwards from which one is actually randomized.

## `distributed_collectives`: collective-communication cost formulas, not an implementation

Every function here is a closed-form scalar formula planning around a collective operation — no
message passing, no device handles, no NCCL/MPI binding, and (per its own module docstring header)
zero Python imports. It reads as the ML-infrastructure-flavored module the family's other pages
would predict: `expert_dispatch_volume` explicitly names MoE dispatch traffic, and the module sits
conceptually next to `moe_production`'s `communication_efficiency_moe` and
`expert_shard_memory_bytes`, documented on
[Mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md) — but neither
page's module imports the other, and nothing here dispatches a token to an expert; it only prices
the bytes such a dispatch would move.

| Function | What it does |
| --- | --- |
| `ring_allreduce_step(local_chunk, recv_chunk, is_reduce_phase)` | Reduce phase (`is_reduce_phase > 0.5`): `local_chunk + recv_chunk`. Broadcast phase: pass `recv_chunk` straight through. |
| `reduce_scatter_element(grad_element, world_size)` | `grad_element / world_size`; unchanged if `world_size <= 0`. |
| `all_gather_offset(rank, shard_size)` | `rank * shard_size` — a rank's starting element index in the gathered buffer. |
| `broadcast_scale(world_size)` | `1 / world_size`; `1.0` if `world_size <= 0`. |
| `gradient_compression_ratio(original_bytes, compressed_bytes)` | `1 - compressed/original`, floored at `0.0`. |
| `expert_dispatch_volume(tokens_per_expert, hidden_dim, dtype_bytes)` | `tokens * hidden_dim * dtype_bytes * 2` (send + recv). |
| `peer_bandwidth_utilization(bytes_transferred, link_bandwidth_gbs, elapsed_ms)` | Bytes moved over theoretical peak bytes for the elapsed time, capped at `1.0`. |
| `collective_latency_alpha_beta(n_bytes, n_steps, alpha_us, beta_gbs)` | `n_steps * (alpha_us + n_bytes / (beta_gbs * 1000))` — the standard alpha-beta network model. |
| `overlap_compute_comm_ratio(compute_ms, comm_ms)` | `min(1, compute_ms / comm_ms)` — how much of communication a compute kernel can hide; `1.0` if `comm_ms <= 0`. |
| `allreduce_tree_step_count(world_size)` | `round(log2(world_size)) * 2`; `0.0` for `world_size <= 1`. |

A worked chain across an 8-GPU ring: `allreduce_tree_step_count(8.0) = 6.0` (three doublings, times
two for reduce-then-broadcast). Dispatching 64 tokens per expert at a 4096-wide hidden dimension in
bf16, `expert_dispatch_volume(64.0, 4096.0, 2.0) = 1,048,576.0` bytes — `64 * 4096 = 262,144`
elements, `* 2` bytes/element `= 524,288`, `* 2` again for send-plus-receive `= 2^20`, exactly one
mebibyte per expert per step. Over a 300 GB/s link, moving a 1 GB tensor in 14 steps (a ring
all-reduce's `2*(world_size-1)` step count
at `world_size = 8`) with a 10 µs per-message overhead:
`collective_latency_alpha_beta(1e9, 14.0, 10.0, 300.0) = 46,806.67` µs, about 46.8 ms — of which
`14 * 10 = 140` µs is pure per-message overhead and the rest is bandwidth-bound transfer time.
Halving that transfer's bytes via compression, `gradient_compression_ratio(4e9, 4e7) = 0.99` — a
99% reduction, keeping 1% of the original 4 GB gradient tensor. And with an 8 ms compute kernel
overlapping a 10 ms communication window, `overlap_compute_comm_ratio(8.0, 10.0) = 0.8` — 80% of the
communication is hidden behind compute, the remaining 20% is exposed on the critical path.

## Verification

`network_protocol` and `distributed_collectives` each have a real
`mojo/tests/libs/test_*.mojo` file, but both are auto-generated coverage smoke tests: every
function is called once with a literal `0.5` (or `"test"`/`5` for string/int parameters) and the
test only checks the result is finite (or, for `network_protocol`, that the call doesn't crash) —
neither file pins a specific numeric output, and `network_protocol.build_query_string` is not
called by its own smoke test at all. `network_analysis` and `social_network` have **no**
`mojo/tests/libs/test_network_analysis.mojo` or `test_social_network.mojo` file of their own — the
only hand-written tests that touch either module are the two `graph_analytics` test files quoted
above (`test_graph_analytics_centrality.mojo`, `test_graph_analytics_community.mojo`), and those
exercise `network_analysis.closeness_centrality`, `network_analysis.degree_centrality`, and
`social_network.community_label_propagation` only as frozen contrast baselines for the newer
module, not as a full test of either module's own behavior. Every worked number in this page —
the triangle and path PageRank/centrality values, the multigraph degree-centrality overflow, the
label-propagation oscillation, the deterministic-sampling divergence, and the distributed-collectives
chain — was hand-traced against the real formulas in `mojo/engine/network_analysis.mojo`,
`mojo/engine/social_network.mojo`, and `mojo/engine/distributed_collectives.mojo`, then independently
re-verified by re-running the same arithmetic in a separate script before being presented here.

**Next:** see [Exact numerics and graph kernels](exact-numerics-and-graph-kernels.md) for the
explicit-graph-object traversal algorithms (`graph.algorithms`, `graph.weighted`) this page's
adjacency-list functions do not use, or [Mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md)
for the token-level MoE arithmetic `expert_dispatch_volume` prices the communication for. Browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
