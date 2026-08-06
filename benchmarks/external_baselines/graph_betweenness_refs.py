#!/usr/bin/env python3
"""networkx reference arm of the unweighted-betweenness-centrality head-to-head.

Usage:
    graph_betweenness_refs.py gen  <kind> <n> <seed> <edge_file>
    graph_betweenness_refs.py dump <edge_file> <out_file>
    graph_betweenness_refs.py bench <edge_file> <reps>

`kind` is one of: path, star, ba, gnm.

gen
---
Builds the graph with `networkx` and writes it to `edge_file` in the format
`graph_betweenness_h2h.mojo` reads:

    <n_nodes> <n_edges>
    <u_0> <v_0>
    ...

one undirected edge per line. This is the ONLY place either language's edge set is
generated -- `graph_betweenness_h2h.mojo` never calls a random generator, it only reads
this file -- so a size cell is one graph, read twice, not two graphs that happen to share
a size. `ba` is `barabasi_albert_graph(n, m=4, seed)` (scale-free, the primary structure);
`gnm` is `gnm_random_graph(n, m, seed)` with the SAME edge count as the `ba` graph at that
`n`, so density is held fixed across structures too. `path`/`star` are the two fixtures
`mojo/tests/libs/test_graph_analytics_centrality.mojo` already asserts exact analytic
values for (P5 raw betweenness `[0,3,4,3,0]`, star(n) hub `(n-1)(n-2)/2`), regenerated
here independently rather than hand-copied, so agreement is evidence and not an echo.

dump
----
Reads `edge_file`, adds nodes `0..n-1` explicitly (an `edge_file` alone can under-represent
an isolated node, which `gnm` can produce), runs
`nx.betweenness_centrality(G, normalized=False)` -- confirmed by reading
`inspect.getsource(nx.betweenness_centrality)` to have no scipy dispatch, unlike
`nx.pagerank` -- and dumps one Float64 bit pattern per line, node 0 first, in the exact
shape `graph_betweenness_h2h.mojo dump` produces. This is the file the driver diffs
BEFORE trusting a single timing number.

bench
-----
Builds the `nx.Graph` ONCE, outside the timed region (the identical favour
`graph_betweenness_h2h.mojo`'s `bench` mode grants itself for CSR construction), then
times `nx.betweenness_centrality(G, normalized=False)` alone, `reps` times. Prints
`T bench <n> <rep> <ns>`, rep 0 cold / rep 1 warm / min of the rest hot, matching the
Mojo arm's convention line for line so the driver's parser is one regex for both sides.
"""
from __future__ import annotations

import sys
import time

_t_imp = time.perf_counter_ns()
import networkx as nx
import numpy as np

_IMPORT_NS = time.perf_counter_ns() - _t_imp


def _write_edges(path: str, n: int, edges: list[tuple[int, int]]) -> None:
    with open(path, "w") as f:
        f.write(f"{n} {len(edges)}\n")
        for u, v in edges:
            f.write(f"{u} {v}\n")


def _canonical_edges(g: nx.Graph) -> list[tuple[int, int]]:
    """u < v, sorted -- a stable, deduplicated undirected edge list."""
    out = sorted((min(u, v), max(u, v)) for u, v in g.edges())
    return out


def cmd_gen() -> None:
    kind = sys.argv[2]
    n = int(sys.argv[3])
    seed = int(sys.argv[4])
    edge_file = sys.argv[5]

    if kind == "path":
        g = nx.path_graph(n)
    elif kind == "star":
        g = nx.star_graph(n - 1)  # star_graph(k) makes k+1 nodes, hub = 0
    elif kind == "ba":
        m = 4 if n > 4 else 1
        g = nx.barabasi_albert_graph(n, m, seed=seed)
    elif kind == "gnm":
        # Same edge count as ba(n, m=4) at this n, so density matches across structures.
        m_target = int(sys.argv[6]) if len(sys.argv) > 6 else 4 * n
        g = nx.gnm_random_graph(n, m_target, seed=seed)
    else:
        raise SystemExit(f"unknown kind {kind!r}")

    g.add_nodes_from(range(n))  # isolates (gnm can produce them) must still be rows
    edges = _canonical_edges(g)
    _write_edges(edge_file, n, edges)
    print(f"GEN n={n} edges={len(edges)} kind={kind} seed={seed}")


def _load_graph(edge_file: str) -> tuple[int, nx.Graph]:
    with open(edge_file) as f:
        header = f.readline().split()
        n, m = int(header[0]), int(header[1])
        g = nx.Graph()
        g.add_nodes_from(range(n))
        for _ in range(m):
            u, v = f.readline().split()
            g.add_edge(int(u), int(v))
    return n, g


def _dump_values(path: str, values: np.ndarray) -> None:
    bits = values.astype(np.float64).view(np.uint64)
    with open(path, "w") as f:
        f.write("\n".join(str(int(b)) for b in bits) + "\n")


def cmd_dump() -> None:
    edge_file = sys.argv[2]
    out_file = sys.argv[3]
    n, g = _load_graph(edge_file)
    t0 = time.perf_counter_ns()
    result = nx.betweenness_centrality(g, normalized=False)
    call_ns = time.perf_counter_ns() - t0
    values = np.array([result[i] for i in range(n)], dtype=np.float64)
    _dump_values(out_file, values)
    max_node = int(np.argmax(values))
    print(
        f"DUMP n={n} max_node={max_node} max_value={values[max_node]!r} "
        f"sum={float(values.sum())!r} call_ns={call_ns}"
    )


def cmd_bench() -> None:
    edge_file = sys.argv[2]
    reps = int(sys.argv[3])
    n, g = _load_graph(edge_file)
    print("IMPORT_NS", _IMPORT_NS)
    for r in range(reps):
        t0 = time.perf_counter_ns()
        nx.betweenness_centrality(g, normalized=False)
        ns = time.perf_counter_ns() - t0
        print(f"T bench {n} {r} {ns}")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: graph_betweenness_refs.py <gen|dump|bench> ...", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "gen":
        cmd_gen()
    elif cmd == "dump":
        cmd_dump()
    elif cmd == "bench":
        cmd_bench()
    else:
        print(f"unknown command {cmd!r}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
