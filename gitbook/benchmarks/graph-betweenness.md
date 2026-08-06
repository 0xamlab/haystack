---
icon: diagram-project
description: Brandes betweenness centrality over a CSR adjacency, against networkx — ahead in every one of 6 cells, from 3.0x at 200 nodes to 4.3x at 2,000.
---

# Graph betweenness centrality

Betweenness of a node is the share of all shortest paths that pass through it — the
measure behind "which node, if removed, would fragment this network the most."
Materializing every pair of nodes to compute it is `O(V³)` time; `graph_analytics.centrality`'s
`graph_betweenness_unweighted` is Brandes' algorithm, `O(VE)`, over a CSR adjacency, with no
distance matrix at any point.

{% hint style="success" %}
**Zero losses. Ahead of `networkx.betweenness_centrality` in all 6 measured cells, across two
graph structures and four sizes from 200 to 2,000 nodes — from 3.0x at the smallest size to
4.3x at the largest, and widening as the graph grows.**
{% endhint %}

## Results

| graph | nodes | edges | networkx | ours | speedup |
| --- | --- | --- | --- | --- | --- |
| Barabási-Albert | 200 | 784 | 32.17 ms | 10.53 ms | **3.1x** |
| Barabási-Albert | 500 | 1,984 | 228.50 ms | 64.55 ms | **3.5x** |
| Barabási-Albert | 1,000 | 3,984 | 1,037.33 ms | 257.93 ms | **4.0x** |
| Barabási-Albert | 2,000 | 7,984 | 4,460.76 ms | 1,042.78 ms | **4.3x** |
| Erdős-Rényi | 200 | 784 | 32.05 ms | 10.78 ms | **3.0x** |
| Erdős-Rényi | 1,000 | 3,984 | 1,133.66 ms | 270.81 ms | **4.2x** |

Hot-tier wall time, minimum across 3 interleaved rounds; graph construction excluded from the
timed region on both sides. **All 6 cells win, and the margin widens with graph size** — 3.0x-3.1x
at 200 nodes, 4.2x-4.3x at 1,000-2,000, consistent with a per-edge constant-factor advantage that
compounds over `O(VE)` work rather than a fixed offset that would shrink as a fraction of the
total.

### Correctness, checked before every timing

Three checks ran before any cell was timed. First, three hand-verified analytic fixtures: a
5-node path graph (known betweenness `[0, 3, 4, 3, 0]`), and star graphs at 5 and 50 nodes (known
hub betweenness `(n-1)(n-2)/2` — 6.0 and 1,176.0). All three matched bit-for-bit. Second, on every
real random graph measured, the two implementations' raw betweenness values agreed to
4.2×10⁻¹⁶-5.3×10⁻¹⁶ relative difference — floating-point summation-order noise from accumulating
the same dependency values in a different order, not a discrepancy in the algorithm — with the sum
of all values and the arg-max node matching exactly. Third, a cross-round reproducibility gate
(median/min ≤ 1.04, max/min ≤ 1.05 on every one of the 12 (implementation, size) timing series)
confirms the ratios above are not a load-average artifact from either side happening to be measured
during a quiet moment.

## Method

* **Baseline.** `networkx.betweenness_centrality`, `networkx` 3.3, `normalized=False`. Confirmed
  by reading `inspect.getsource` before measuring anything: this entry point has no SciPy dispatch
  underneath it — it is the real, pure-Python reference implementation networkx ships, not an
  accelerated path.
* **What is timed.** `graph_analytics.centrality.graph_betweenness_unweighted`, AOT-compiled
  (`mojo build`, not `mojo run`'s JIT). Graph construction (`graph_csr_from_triplets` on our side,
  the `networkx.Graph` object on theirs) happens outside every timed region on both sides — a
  favour to networkx, which pays nothing to marshal a graph it built itself, so the fairest thing
  this comparison can do is not charge our side for CSR construction either.
* **Identical topology, generated once.** Every graph is generated ONCE, as an edge list, on the
  Python side, and written to a file; both implementations read the same edge file rather than
  each generating "an equivalent random graph" independently. Generating the same distribution
  twice would let two different graphs answer the timing question; reading one graph twice answers
  it once, honestly.
* **Two structures.** Barabási-Albert (scale-free, preferential attachment — a few high-degree
  hubs) and Erdős-Rényi (uniform random) — different enough in shape that a result holding on both
  is not an artifact of one graph's particular structure.
* **Cold / warm / hot.** Each rep is a full process launch (this binary and the Python driver are
  both freshly invoked per repetition, not looped in one process), so cold is genuinely first-call
  including page faults, warm the second, hot the minimum across the remaining repetitions within
  a wall-clock budget. 3 interleaved rounds per cell, with a cross-round dispersion gate; every one
  of the 12 series in this run passed it.
* **Hardware.** Apple M4 Max, 16 physical cores (12 performance + 4 efficiency). Both
  implementations are single-threaded for this comparison.

## What is not claimed

* **Not a claim about weighted betweenness.** `graph_betweenness_weighted` exists and is not
  measured on this page; unweighted (hop-counting) shortest paths only.
* **Not a claim about every graph structure or size.** Two structures, four sizes, 200-2,000
  nodes. Larger or differently-shaped graphs are not measured here.
* **Not a claim about PageRank, closeness, or community detection**, all of which live in the same
  `graph_analytics` package and are not covered by this page.
* **Not interleaved inside one process.** Each side runs as its own process invocation, alternated
  round by round rather than sorting the same bytes in one process the way [sort](sort.md) does.
  Disclosed rather than presented as stronger evidence than it is; the cross-round gate is what
  substitutes for in-process interleaving here.

## Related

* [Sort](sort.md) — a columnar kernel measured the same way.
* [Top-k selection](top-k.md) — a bounded-heap kernel with one honest loss disclosed up front.
* [Survival analysis](survival-analysis.md) — measured against two current real-world
  datasets, 10 of 11 cells ahead of lifelines, same two-process disclosure.
* [Benchmarks](overview.md) — methodology and what is not published.

## Reproduce

```text title="benchmark"
python3 benchmarks/external_baselines/drive_graph_betweenness.py
```

Builds the Mojo binary, generates both graph structures at every size once, and runs both
implementations through the same alternating-round, cross-round-gated procedure described above.
Prints a per-cell table and `BENCH_GATE graph_betweenness PASS|FAIL <n>` on completion.
