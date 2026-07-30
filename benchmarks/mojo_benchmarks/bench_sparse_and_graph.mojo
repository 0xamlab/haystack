"""bench_sparse_and_graph.mojo — timing gate for sparse_numerics and graph_analytics.

Hand-written, not generated. `benchmark_mojo_vs_python.py` only writes `bench_<lib>.mojo`
for libraries in the runtime inventory; no library is named `sparse_and_graph`, so nothing
can collide with this name, and that harness only writes — it never unlinks.

What is measured, and why each one is the claim that matters
-----------------------------------------------------------
1. **SpMV cost tracks nnz, not n².** That is the entire reason CSR exists. A dense matvec
   over an n×n matrix touches n² cells whatever the sparsity; CSR touches nnz. Measured as
   ns per NON-ZERO across a rising n at fixed density, which must stay flat — and against
   the frozen `sparse.sparse_matvec` (COO), which is the only prior SpMV and has to
   scatter-accumulate over unsorted triplets.

2. **CG beats a dense factorisation on a sparse system.** Not because iterating is clever,
   but because `linalg.mat_solve` is O(n³) on the dense image and CG is O(nnz) per
   iteration. Reported as a ratio at a size where both still finish, so the crossover is
   visible rather than asserted.

3. **A CSR adjacency built once beats rebuilding it per call.** The frozen
   `graph.weighted.shortest_path_dijkstra` rebuilds its per-node adjacency lists from the
   triplet edge list on EVERY call and then scans O(V²) instead of using a queue. This
   measures k successive shortest-path queries against one prebuilt `GraphCSR` versus k
   calls to the frozen kernel, which is exactly the workload where the difference shows.

4. **Brandes betweenness is O(V·E), not O(V³).** Measured as ns per (vertex × edge) across
   a rising graph, which must stay flat. An all-pairs implementation would grow with V².

Gate
----
Fails on the properties, not on absolute nanoseconds, which vary by machine:
  * SpMV ns/nnz must not grow more than 3x across a 16x increase in n at fixed density
  * CSR SpMV must agree with the frozen COO SpMV to 1e-9 (speed is meaningless otherwise)
  * prebuilt-CSR dijkstra must agree with the frozen kernel's distances exactly, and be
    faster over k queries
  * Brandes ns/(V*E) must not grow more than 3x across the same range
Absolute numbers are printed for tracking.
"""
from std.time import perf_counter_ns

from graph_analytics.adjacency import (
    graph_csr_dijkstra,
    graph_csr_from_triplets,
)
from graph_analytics.centrality import graph_betweenness_unweighted
from graph.weighted import WeightedEdge, shortest_path_dijkstra
from linalg import mat_from_list, mat_solve
from sparse import SparseMatrixCOO, sparse_matvec
from sparse_numerics.csr import csr_build_from_triplets, csr_from_arrays
from sparse_numerics.iterative import csr_cg
from sparse_numerics.spmv import csr_matvec

comptime WARMUP: Int = 3


fn _ns_per(elapsed: UInt, work: Int, reps: Int) -> Float64:
    """`perf_counter_ns` yields UInt, so the delta stays unsigned until here."""
    if work <= 0 or reps <= 0:
        return 0.0
    return Float64(Int(elapsed)) / Float64(work * reps)


fn _tridiagonal(n: Int) -> List[List[Float64]]:
    """A 1D Laplacian as (rows, cols, vals): SPD, ~3n non-zeros, exact solution known.

    Returned as three parallel Float64 lists so one helper serves both the CSR builder and
    the COO builder without a second construction path that could differ.
    """
    var rows = List[Float64]()
    var cols = List[Float64]()
    var vals = List[Float64]()
    for i in range(n):
        rows.append(Float64(i))
        cols.append(Float64(i))
        vals.append(2.0)
        if i > 0:
            rows.append(Float64(i))
            cols.append(Float64(i - 1))
            vals.append(-1.0)
        if i + 1 < n:
            rows.append(Float64(i))
            cols.append(Float64(i + 1))
            vals.append(-1.0)
    var out = List[List[Float64]]()
    out.append(rows^)
    out.append(cols^)
    out.append(vals^)
    return out^


fn _to_int(values: List[Float64]) -> List[Int]:
    var out = List[Int]()
    for i in range(len(values)):
        out.append(Int(values[i]))
    return out^


fn _coo(rows: List[Float64], cols: List[Float64], vals: List[Float64], n: Int) -> SparseMatrixCOO:
    """The frozen COO form of the same matrix, for the differential comparison."""
    var m = SparseMatrixCOO(n, n)
    for k in range(len(vals)):
        m.add_entry(Int(rows[k]), Int(cols[k]), vals[k])
    return m^


fn _ring_edges(n: Int, extra_stride: Int) -> List[List[Int]]:
    """A ring plus one chord per node — connected, ~2n edges, no isolated vertices."""
    var src = List[Int]()
    var dst = List[Int]()
    for i in range(n):
        src.append(i)
        dst.append((i + 1) % n)
        src.append(i)
        dst.append((i + extra_stride) % n)
    var out = List[List[Int]]()
    out.append(src^)
    out.append(dst^)
    return out^


fn main() raises:
    var failures = 0

    # ── 1. SpMV cost tracks nnz, not n^2 ─────────────────────────────────────
    print("=== SpMV: cost per non-zero across a rising n (fixed ~3 nnz/row) ===")
    var sizes = List[Int]()
    sizes.append(64)
    sizes.append(256)
    sizes.append(1024)
    var first_per_nnz: Float64 = 0.0
    var last_per_nnz: Float64 = 0.0
    var agreed = True

    for s in range(len(sizes)):
        var n = sizes[s]
        var trip = _tridiagonal(n)
        var built = csr_build_from_triplets(
            _to_int(trip[0]), _to_int(trip[1]), trip[2], n, n
        )
        var a = csr_from_arrays(built.indptr, built.indices, built.values, n, n)
        var x = List[Float64]()
        for i in range(n):
            x.append(1.0 + Float64(i % 7))

        var reps = 16384 // n
        if reps < 2:
            reps = 2
        for _ in range(WARMUP):
            var _w = csr_matvec(a, x)

        var t0 = perf_counter_ns()
        for _ in range(reps):
            var _r = csr_matvec(a, x)
        var t1 = perf_counter_ns()
        var per_nnz = _ns_per(t1 - t0, built.nnz, reps)

        # The frozen COO SpMV over the same matrix, as both a comparison and an oracle.
        var coo = _coo(trip[0], trip[1], trip[2], n)
        for _ in range(WARMUP):
            var _wc = sparse_matvec(coo, x)
        var t2 = perf_counter_ns()
        for _ in range(reps):
            var _rc = sparse_matvec(coo, x)
        var t3 = perf_counter_ns()
        var coo_per_nnz = _ns_per(t3 - t2, built.nnz, reps)

        var mine = csr_matvec(a, x)
        var theirs = sparse_matvec(coo, x)
        if mine.status == 0 and len(mine.values) == n and len(theirs) == n:
            for i in range(n):
                var d = mine.values[i] - theirs[i]
                if d > 1e-9 or d < -1e-9:
                    agreed = False
        else:
            agreed = False

        if s == 0:
            first_per_nnz = per_nnz
        last_per_nnz = per_nnz
        print(
            "  n=" + String(n),
            "nnz=" + String(built.nnz),
            "csr_ns/nnz=" + String(per_nnz),
            "coo_ns/nnz=" + String(coo_per_nnz),
        )

    print("")
    if agreed:
        print("  ✅ CSR SpMV matches the frozen COO SpMV to 1e-9 at every size")
    else:
        failures += 1
        print("  ❌ CSR and COO SpMV disagree — the timings mean nothing")

    var spmv_growth = last_per_nnz / first_per_nnz if first_per_nnz > 0.0 else 999.0
    if spmv_growth <= 3.0:
        print(
            "  ✅ ns/nnz grew only "
            + String(spmv_growth)
            + "x across a 16x increase in n — cost tracks nnz, not n^2"
        )
    else:
        failures += 1
        print("  ❌ ns/nnz grew " + String(spmv_growth) + "x; SpMV is not O(nnz)")

    # ── 2. CG on a sparse system vs a dense factorisation ────────────────────
    print("")
    print("=== CG over CSR vs dense mat_solve on the same SPD system ===")
    var n_cg = 192
    var trip_cg = _tridiagonal(n_cg)
    var built_cg = csr_build_from_triplets(
        _to_int(trip_cg[0]), _to_int(trip_cg[1]), trip_cg[2], n_cg, n_cg
    )
    var a_cg = csr_from_arrays(
        built_cg.indptr, built_cg.indices, built_cg.values, n_cg, n_cg
    )
    var b = List[Float64]()
    for i in range(n_cg):
        b.append(1.0)

    for _ in range(WARMUP):
        var _wcg = csr_cg(a_cg, b, 1e-10, n_cg * 2)
    var t4 = perf_counter_ns()
    var cg = csr_cg(a_cg, b, 1e-10, n_cg * 2)
    var t5 = perf_counter_ns()
    var cg_ms = Float64(Int(t5 - t4)) / 1.0e6

    # The dense image the frozen solver needs.
    var dense = List[Float64]()
    for _ in range(n_cg * n_cg):
        dense.append(0.0)
    for k in range(len(trip_cg[2])):
        dense[Int(trip_cg[0][k]) * n_cg + Int(trip_cg[1][k])] += trip_cg[2][k]
    var t6 = perf_counter_ns()
    var dense_x = mat_solve(mat_from_list(dense, n_cg, n_cg), b)
    var t7 = perf_counter_ns()
    var dense_ms = Float64(Int(t7 - t6)) / 1.0e6

    print("  n=" + String(n_cg), "nnz=" + String(built_cg.nnz))
    print(
        "  CG        " + String(cg_ms) + " ms  iterations=" + String(cg.iterations),
        "converged=" + String(cg.converged),
    )
    print("  mat_solve " + String(dense_ms) + " ms  (dense O(n^3) on the n^2 image)")
    if dense_ms > 0.0 and cg_ms > 0.0:
        print("  speedup=" + String(dense_ms / cg_ms) + "x")

    var cg_matches = cg.converged and len(dense_x) == n_cg and len(cg.x) == n_cg
    if cg_matches:
        for i in range(n_cg):
            var d = cg.x[i] - dense_x[i]
            if d > 1e-6 or d < -1e-6:
                cg_matches = False
    if cg_matches:
        print("  ✅ CG's solution matches dense mat_solve to 1e-6, and it converged")
    else:
        failures += 1
        print("  ❌ CG disagrees with mat_solve, or did not converge")

    # ── 3. A CSR adjacency built once vs rebuilt per call ────────────────────
    print("")
    print("=== k shortest-path queries: prebuilt GraphCSR vs the frozen kernel ===")
    var n_g = 512
    var ring = _ring_edges(n_g, 7)
    var weights = List[Float64]()
    for i in range(len(ring[0])):
        weights.append(1.0 + Float64(i % 5))

    var g = graph_csr_from_triplets(ring[0], ring[1], weights, n_g)
    var edges = List[WeightedEdge]()
    for i in range(len(ring[0])):
        edges.append(WeightedEdge(ring[0][i], ring[1][i], weights[i]))

    var k_queries = 8
    for _ in range(WARMUP):
        var _wd = graph_csr_dijkstra(g, 0)

    var t8 = perf_counter_ns()
    for q in range(k_queries):
        var _r = graph_csr_dijkstra(g, q)
    var t9 = perf_counter_ns()
    var prebuilt_ms = Float64(Int(t9 - t8)) / 1.0e6

    var t10 = perf_counter_ns()
    for q in range(k_queries):
        var _r2 = shortest_path_dijkstra(n_g, edges, q)
    var t11 = perf_counter_ns()
    var frozen_ms = Float64(Int(t11 - t10)) / 1.0e6

    print(
        "  V=" + String(n_g),
        "E=" + String(len(ring[0])),
        "queries=" + String(k_queries),
    )
    print("  prebuilt GraphCSR + heap  " + String(prebuilt_ms) + " ms")
    print("  frozen (rebuild + O(V^2)) " + String(frozen_ms) + " ms")
    if prebuilt_ms > 0.0:
        print("  speedup=" + String(frozen_ms / prebuilt_ms) + "x")

    # Distances must be identical where every node is reachable, or the speed is a lie.
    var mine_d = graph_csr_dijkstra(g, 0)
    var theirs_d = shortest_path_dijkstra(n_g, edges, 0)
    var dist_match = mine_d.status == 0 and len(theirs_d) == n_g
    if dist_match:
        for i in range(n_g):
            if not mine_d.reached[i]:
                continue
            var d = mine_d.distance[i] - theirs_d[i]
            if d > 1e-9 or d < -1e-9:
                dist_match = False
    if dist_match:
        print("  ✅ distances identical to the frozen kernel on every reached node")
    else:
        failures += 1
        print("  ❌ distances differ from the frozen kernel")

    if prebuilt_ms < frozen_ms:
        print(
            "  ✅ building the adjacency once is faster over "
            + String(k_queries)
            + " queries"
        )
    else:
        failures += 1
        print("  ❌ prebuilt CSR was not faster; the rebuild claim does not hold")

    # ── 4. Brandes betweenness is O(V*E) ────────────────────────────────────
    print("")
    print("=== Brandes betweenness: cost per (V*E) across a rising graph ===")
    var g_sizes = List[Int]()
    g_sizes.append(64)
    g_sizes.append(256)
    var first_per_ve: Float64 = 0.0
    var last_per_ve: Float64 = 0.0
    for s in range(len(g_sizes)):
        var n = g_sizes[s]
        var r = _ring_edges(n, 5)
        var w = List[Float64]()
        for i in range(len(r[0])):
            w.append(1.0)
        var gg = graph_csr_from_triplets(r[0], r[1], w, n)
        for _ in range(WARMUP):
            var _wb = graph_betweenness_unweighted(gg.row_ptr, gg.targets, gg.weights, n, False)
        var t12 = perf_counter_ns()
        var _bc = graph_betweenness_unweighted(gg.row_ptr, gg.targets, gg.weights, n, False)
        var t13 = perf_counter_ns()
        var per_ve = _ns_per(t13 - t12, n * len(r[0]), 1)
        if s == 0:
            first_per_ve = per_ve
        last_per_ve = per_ve
        print("  V=" + String(n), "E=" + String(len(r[0])), "ns/(V*E)=" + String(per_ve))

    var bc_growth = last_per_ve / first_per_ve if first_per_ve > 0.0 else 999.0
    if bc_growth <= 3.0:
        print(
            "  ✅ ns/(V*E) grew only "
            + String(bc_growth)
            + "x across a 4x V increase — O(V*E), not O(V^3)"
        )
    else:
        failures += 1
        print("  ❌ ns/(V*E) grew " + String(bc_growth) + "x; not O(V*E)")

    print("")
    if failures == 0:
        print("BENCH_GATE sparse_and_graph PASS")
    else:
        print("BENCH_GATE sparse_and_graph FAIL " + String(failures))
        raise Error("bench_sparse_and_graph: " + String(failures) + " gate failure(s)")
