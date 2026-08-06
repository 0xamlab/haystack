"""Algenta arm of the unweighted-betweenness-centrality head-to-head against networkx.

Usage: graph_betweenness_h2h <mode> <edge_file> <arg3>
Modes:
  dump  <edge_file> <out_file>   run Brandes once, dump every node's raw (unnormalized)
                                  betweenness value as a decimal Float64 bit pattern, one
                                  per line, node 0 first -- the CORRECTNESS artifact.
                                  `graph_betweenness_refs.py dump` produces the same file
                                  shape from the SAME edge file, and the driver diffs them
                                  before any timing number is trusted.
  bench <edge_file> <reps>       time `graph_betweenness_unweighted` alone, `reps` times.
                                  Prints `T bench <n> <rep> <ns>`. Rep 0 is this PROCESS's
                                  cold call (first call after a fresh binary launch, page
                                  faults included), rep 1 is warm, min over the rest is hot
                                  -- the same three-tier convention `gemm_h2h.mojo`'s
                                  header documents, because here too each rep is a whole
                                  process launch's measurement, not an in-process batch.

EDGE FILE FORMAT, why it exists at all
---------------------------------------
    <n_nodes> <n_edges>
    <u_0> <v_0>
    <u_1> <v_1>
    ...
one UNDIRECTED edge per line, u != v, each pair appearing once. It is written by
`graph_betweenness_refs.py gen` from a `networkx` graph object and read verbatim here --
the topology is generated ONCE, on the Python side, and both languages compute betweenness
over the identical edge set. Generating the same "random" graph twice (once per language)
would let two different graphs answer the question instead of one graph answering it
twice, which is the actual comparison this file exists to make honest.

Each undirected edge becomes two directed triplets of weight 1.0 -- the same `_add_both`
convention `mojo/tests/libs/test_graph_analytics_centrality.mojo` uses for its P5 and star
fixtures -- so the CSR this binary builds is structurally symmetric,
`graph_csr_symmetry` auto-detects `undirected=True` inside `_betweenness`, and the
ordered-pair sum is halved exactly as networkx's own undirected `betweenness_centrality`
halves it. Neither side is told "this is undirected" by a flag; both discover it from the
same symmetric structure.

Graph construction (`graph_csr_from_triplets`) happens OUTSIDE every timed region in
`bench` mode, on both sides of this comparison -- a favour to networkx, which is handed a
plain Python object it built itself with no marshalling cost at all, so the fairest
thing this binary can do is not charge itself for CSR construction either.
"""
from std.time import perf_counter_ns
from std.sys import argv

from graph_analytics.adjacency import graph_csr_from_triplets, GRAPH_OK
from graph_analytics.centrality import graph_betweenness_unweighted


def _read_all(path: String) raises -> String:
    var f = open(path, "r")
    var s = f.read()
    f.close()
    return s^


@fieldwise_init
struct EdgeList(Copyable, Movable):
    var n_nodes: Int
    var src: List[Int]
    var dst: List[Int]
    var weight: List[Float64]


def read_edge_file(path: String) raises -> EdgeList:
    """Parses the format above, doubling each undirected edge into two directed ones."""
    var text = _read_all(path)
    var lines = text.split("\n")
    var header = lines[0].split(" ")
    var n_nodes = Int(header[0])
    var n_edges = Int(header[1])
    var src = List[Int](capacity=n_edges * 2)
    var dst = List[Int](capacity=n_edges * 2)
    var weight = List[Float64](capacity=n_edges * 2)
    for i in range(n_edges):
        var toks = lines[i + 1].split(" ")
        var u = Int(toks[0])
        var v = Int(toks[1])
        src.append(u)
        dst.append(v)
        weight.append(1.0)
        src.append(v)
        dst.append(u)
        weight.append(1.0)
    return EdgeList(n_nodes, src^, dst^, weight^)


def _dump_values(path: String, values: List[Float64]) raises:
    var f = open(path, "w")
    var s = String("")
    for i in range(len(values)):
        s += String(values[i].to_bits())
        s += "\n"
    f.write(s)
    f.close()


def main() raises:
    var a = argv()
    if len(a) < 3:
        print("usage: graph_betweenness_h2h <dump|bench> <edge_file> <out_file|reps>")
        return
    var mode = String(a[1])
    var edge_file = String(a[2])
    var el = read_edge_file(edge_file)

    if mode == "dump":
        var out_file = String(a[3])
        var g = graph_csr_from_triplets(el.src, el.dst, el.weight, el.n_nodes)
        var t0 = perf_counter_ns()
        var r = graph_betweenness_unweighted(
            g.row_ptr, g.targets, g.weights, el.n_nodes, False
        )
        var call_ns = Int(perf_counter_ns() - t0)
        if r.status != GRAPH_OK:
            print("STATUS_FAIL", r.status)
            return
        var total = 0.0
        for i in range(len(r.values)):
            total += r.values[i]
        _dump_values(out_file, r.values)
        print(
            "DUMP n=" + String(el.n_nodes),
            "status=" + String(r.status),
            "max_node=" + String(r.max_node),
            "max_value=" + String(r.max_value),
            "sum=" + String(total),
            "undirected=" + ("1" if r.undirected else "0"),
            "path_counts_exact=" + ("1" if r.path_counts_exact else "0"),
            "call_ns=" + String(call_ns),
        )
    elif mode == "bench":
        var reps = Int(String(a[3]))
        var g = graph_csr_from_triplets(el.src, el.dst, el.weight, el.n_nodes)
        for r_i in range(reps):
            var t0 = perf_counter_ns()
            var res = graph_betweenness_unweighted(
                g.row_ptr, g.targets, g.weights, el.n_nodes, False
            )
            var ns = Int(perf_counter_ns() - t0)
            if res.status != GRAPH_OK:
                print("STATUS_FAIL", res.status)
            print("T bench", el.n_nodes, r_i, ns)
    else:
        print("unknown mode", mode)
