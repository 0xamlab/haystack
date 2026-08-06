"""bench_geospatial.mojo — the selectivity claim, measured, and gated on SHAPE.

Prints `BENCH_GATE geospatial PASS` when every shape assertion holds.

What is gated, and why it is a ratio and never a nanosecond count
----------------------------------------------------------------
An absolute timing gate measures the machine. This file gates on quantities that are
properties of the ALGORITHM and survive a change of hardware:

1. **Window selectivity improves as the dataset grows.** The extent is fixed at
   1000 x 1000 metres and the query window is a fixed 10 x 10 metres — one ten-thousandth of
   the area — while `n` goes 1024 -> 4096 -> 16384 -> 65536. A full scan examines `n`. The
   index examines the points in the cells the window touches, and because `side` grows as
   sqrt(n / target_per_cell) the cells SHRINK as the data grows, so the fraction examined
   falls towards the ideal 1e-4. The gate is that `candidates / n` strictly decreases at every
   step. That is the only form of a selectivity claim that a faster machine cannot flatter and
   a slower one cannot break.

2. **k-nearest candidate count does not grow with `n`.** Same fixed extent, `k = 8`. An exact
   k-NN over a grid should examine a number of candidates set by `k` and the local density,
   not by the dataset size. The gate is that the count at n = 65536 is below 4x the count at
   n = 1024 — while a full scan's would be 64x — so the claim is that the growth is bounded,
   which is what "sublinear" actually means here.

3. **Per-unit WORK is flat, and per-unit TIME is gated relative to the full scan.** The work
   a window query does is `cells touched + candidates examined`, and both are gated at
   `max <= 1.5 * min` across a 64x size range — that is the algorithmic shape, and it is exact
   arithmetic rather than a measurement.

   Wall time per query is reported but NOT gated as flat, because it is not flat and saying it
   was would be the dishonest version: the working set grows from 8 KB to over 512 KB across
   these sizes, so the same 16 candidate reads cost more as they stop fitting in cache. On this
   machine the indexed query grows about 3.5x while the full scan grows about 68x. What IS
   gated is that RELATIVE fact — the index's growth factor must be at least 8x smaller than the
   scan's over the same range — which is a property of the algorithms and not of the cache.

   Per-unit cost is still gated flat where the working set does NOT grow: nanoseconds per point
   for the build, per edge test for point-in-polygon, per cell for a route matrix, at
   `max <= 4 * min`, which leaves room for a shared machine while failing a hidden quadratic.

   Those three are measured as the MINIMUM of `REPEATS` runs, not a single shot. The workload is
   deterministic, so its true cost is the floor and interference from anything else on the
   machine can only add to it — a single measurement of the 4096-point build came back 7x the
   others on the first attempt at this file, purely because a sibling process was running, and a
   flatness gate over single shots is therefore a test of who else is on the box. A warm-up pass
   runs first as well, so the smallest size is not the one paying for page faults.

4. **The join's selectivity improves too**, on the same ratio-not-time basis.

5. **The CELLS a probe reads are charged, and the ceiling binds.** Every gate above measures
   well-shaped uniform data, where cells and candidates rise together and either would do as a
   proxy for the other. Section 6 measures the case where they do not: a right side clustered
   on a diagonal, and search boxes that cover thousands of cells while examining ZERO
   candidates. Two shapes are gated — cells charged per left point flat as `n_left` grows 16x,
   and the MARGINAL wall time per charged cell flat over the same range (marginal, because one
   join call also pays a fixed index build that would otherwise amortise away and fake a
   falling per-cell cost). Then the ceiling itself: 3.4e8 cell reads against a budget of 2^26
   must come back `GEO_OK_TRUNCATED`. A budget written in candidates alone let that same call
   run to completion under a plain OK with a reported cost of zero, which is how a bounded
   request becomes eleven minutes of invisible work.

6. **The segment clamp costs the same on a long leg as on a short one.** Section 7 fixes a
   query past the end of legs of 1, 30, 95 and 120 degrees and gates `ns per segment` flat,
   with every answer asserted to be the clamped endpoint distance rather than the near-zero
   distance to the infinite great circle. It is a cost gate and a correctness gate at once: the
   case decision is four `initial_bearing` calls whatever the leg length, so a per-segment cost
   that moved with the leg would mean the clamp had acquired a search.

Every coordinate is drawn from the frozen keyed generator
---------------------------------------------------------
`determinism.counter_rng.rng_uniform` with an explicit `MASTER_SEED`, so the point sets are a
pure function of `(seed, stream, index)`. Re-running measures the same work on the same data —
there is no unseeded randomness anywhere in this file, and nothing here is `random_float64`.

Correctness is re-checked at scale, not assumed from the suite
-------------------------------------------------------------
At every size the indexed window is compared against `window_scan_flat`, and the indexed
k-nearest against `knn_scan_flat`. A performance number for a wrong answer is worthless, and a
pruning bug shows up at 65536 points long before it shows up at 25.
"""
from std.math import abs as fabs, sqrt
from std.time import perf_counter_ns

from determinism.counter_rng import rng_uniform

from geospatial.contract import (
    GEO_FRAME_LONLAT_DEG,
    GEO_FRAME_PLANE_M,
    GEO_METRIC_EUCLIDEAN,
    GEO_METRIC_HAVERSINE,
    GEO_OK,
    GEO_OK_TRUNCATED,
)
from geospatial.index import (
    grid_build_flat,
    grid_knn_flat,
    grid_window_flat,
    knn_scan_flat,
    window_scan_flat,
)
from geospatial.join import join_within_flat, route_matrix_flat
from geospatial.mapmatch import point_to_segment_flat
from geospatial.polygon import points_in_ring_flat, ring_area_flat

#: One explicit seed for the whole file. Every coordinate below is a pure function of it.
comptime MASTER_SEED: UInt64 = 0x6765_6F73_7061_7469

#: The fixed extent, in metres. Held constant across sizes so that growing `n` means growing
#: DENSITY — which is the only setting in which a selectivity ratio can improve at all.
comptime EXTENT_M: Float64 = 1000.0

#: The fixed query window side, in metres. 10 x 10 out of 1000 x 1000 is 1e-4 of the area, so
#: the ideal selectivity is 1e-4 and the measured one approaches it from above.
comptime WINDOW_M: Float64 = 10.0

#: Repetitions for every per-unit TIME measurement, of which the MINIMUM is kept. The work is
#: deterministic, so the floor is the estimate and interference can only inflate a sample.
comptime REPEATS: Int = 5

#: Edge tests per point-in-polygon measurement, held CONSTANT across vertex counts by scaling
#: the probe point count inversely: 8192 points x 64 vertices and 256 points x 2048 vertices are
#: both this many. The claim being gated is that cost is the PRODUCT — flat per edge test — and
#: with a fixed point count instead, the 2048-vertex measurement was a 4.2-million-edge-test
#: region of tens of milliseconds while the 64-vertex one was 131 thousand and fitted inside a
#: single scheduling quantum. On a machine under a load average of 400 that asymmetry, and not
#: the algorithm, is what the minimum-of-repeats was measuring: the same 2048-vertex ring read
#: 18 to 85 ns per edge test from run to run, and the measurement moved the same way with this
#: package's clip primitive replaced by its predecessor (42-65 vs 18-72 ns), which is how the
#: confound was identified rather than assumed. Equal-sized regions remove it without touching
#: the 4x criterion, and a genuine quadratic in the vertex count still fails: at a fixed total,
#: quadratic work would make the per-edge-test cost RISE with `m` by the same factor it always
#: would.
comptime PIP_EDGE_TESTS: Int = 524288


def _ns_per(elapsed: UInt, work: Int, reps: Int) -> Float64:
    """`perf_counter_ns` yields UInt, so the delta stays unsigned until here."""
    if work <= 0 or reps <= 0:
        return 0.0
    return Float64(Int(elapsed)) / Float64(work * reps)


def _keyed_points(n: Int, stream: UInt64) -> List[Float64]:
    """`n` coordinates uniform on [0, EXTENT_M), from the frozen keyed generator."""
    var out = List[Float64]()
    for i in range(n):
        out.append(rng_uniform(MASTER_SEED, 0, 0, 0, 0, stream, UInt64(i)) * EXTENT_M)
    return out^


def _ratio_ok(hi: Float64, lo: Float64, factor: Float64) -> Bool:
    """`hi <= factor * lo`, with a zero `lo` treated as unmeasurable rather than as a pass."""
    if lo <= 0.0:
        return False
    return hi <= factor * lo


def main() raises:
    var failures = 0
    print("bench_geospatial — spatial index selectivity and per-unit cost")
    print("seed = 0x6765_6F73_7061_7469, extent = 1000 x 1000 m, window = 10 x 10 m")
    print("")

    # A discarded warm-up. Without it the FIRST size in each loop is measured cold — page
    # faults on a fresh allocation and an unwarmed instruction cache — which makes the
    # smallest problem look the SLOWEST and turns every per-unit flatness gate into a test of
    # start-up cost. The warm-up is thrown away and asserted only to keep the compiler honest.
    var warm_x = _keyed_points(2048, 1)
    var warm_y = _keyed_points(2048, 2)
    var warm_g = grid_build_flat(warm_x, warm_y, 2048, GEO_FRAME_PLANE_M, 4)
    var warm_sum = 0
    for q in range(64):
        var w = grid_window_flat(
            warm_g.cell_start, warm_g.cell_items, warm_x, warm_y, 2048, warm_g.side,
            warm_g.min_x, warm_g.min_y, warm_g.cell_w, warm_g.cell_h,
            0.0, 0.0, EXTENT_M, EXTENT_M, GEO_FRAME_PLANE_M,
        )
        warm_sum += w.n_found
    if warm_g.status != GEO_OK or warm_sum != 64 * 2048:
        failures += 1
        print("  ❌ the warm-up itself did not return every point")

    var sizes = List[Int]()
    sizes.append(1024)
    sizes.append(4096)
    sizes.append(16384)
    sizes.append(65536)

    var sel = List[Float64]()
    var cand_per_query = List[Float64]()
    var cells_per_query = List[Float64]()
    var knn_cand = List[Float64]()
    var build_ns = List[Float64]()
    var window_ns = List[Float64]()
    var scan_ns = List[Float64]()

    print("── 1. window selectivity and per-unit cost, fixed 10x10 m window ──")
    for s in range(len(sizes)):
        var n = sizes[s]
        var xs = _keyed_points(n, 1)
        var ys = _keyed_points(n, 2)

        var best_build: UInt = 0
        var grid = grid_build_flat(xs, ys, n, GEO_FRAME_PLANE_M, 4)
        for r in range(REPEATS):
            var t0 = perf_counter_ns()
            var g = grid_build_flat(xs, ys, n, GEO_FRAME_PLANE_M, 4)
            var t1 = perf_counter_ns()
            if g.status != GEO_OK:
                failures += 1
                break
            if r == 0 or (t1 - t0) < best_build:
                best_build = t1 - t0
        if grid.status != GEO_OK:
            failures += 1
            print("  ❌ build failed at n =", n, "status", grid.status)
            continue
        build_ns.append(_ns_per(best_build, n, 1))

        # 64 windows placed on a deterministic lattice inside the extent, so the measurement
        # is not one lucky query. Each is 10 x 10 m.
        var reps = 64
        var found_total = 0
        var cand_total = 0
        var cells_total = 0
        var best_win: UInt = 0
        for rr in range(REPEATS):
            var w0 = perf_counter_ns()
            for q in range(reps):
                var cx2 = (Float64(q % 8) + 0.5) * EXTENT_M / 8.0
                var cy2 = (Float64(q // 8) + 0.5) * EXTENT_M / 8.0
                var wq = grid_window_flat(
                    grid.cell_start, grid.cell_items, xs, ys, n, grid.side,
                    grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
                    cx2 - WINDOW_M / 2.0, cy2 - WINDOW_M / 2.0,
                    cx2 + WINDOW_M / 2.0, cy2 + WINDOW_M / 2.0, GEO_FRAME_PLANE_M,
                )
                found_total += wq.n_found
            var w1 = perf_counter_ns()
            if rr == 0 or (w1 - w0) < best_win:
                best_win = w1 - w0
        found_total = 0
        var t2 = perf_counter_ns()
        for q in range(reps):
            var cx = (Float64(q % 8) + 0.5) * EXTENT_M / 8.0
            var cy = (Float64(q // 8) + 0.5) * EXTENT_M / 8.0
            var w = grid_window_flat(
                grid.cell_start, grid.cell_items, xs, ys, n, grid.side,
                grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
                cx - WINDOW_M / 2.0, cy - WINDOW_M / 2.0,
                cx + WINDOW_M / 2.0, cy + WINDOW_M / 2.0, GEO_FRAME_PLANE_M,
            )
            if w.status != GEO_OK:
                failures += 1
                print("  ❌ window failed at n =", n, "status", w.status)
                break
            found_total += w.n_found
            cand_total += w.candidates_examined
            cells_total += w.cells_examined
        var t3 = perf_counter_ns()
        _ = t3

        # The same 64 windows through the independent O(n) scan: the answer must be identical
        # at scale, and the scan's cost is what the index is being measured against.
        var scan_found = 0
        var t4 = perf_counter_ns()
        for q in range(reps):
            var cx = (Float64(q % 8) + 0.5) * EXTENT_M / 8.0
            var cy = (Float64(q // 8) + 0.5) * EXTENT_M / 8.0
            var sc = window_scan_flat(
                xs, ys, n,
                cx - WINDOW_M / 2.0, cy - WINDOW_M / 2.0,
                cx + WINDOW_M / 2.0, cy + WINDOW_M / 2.0, GEO_FRAME_PLANE_M,
            )
            scan_found += sc.n_found
        var t5 = perf_counter_ns()

        if scan_found != found_total:
            failures += 1
            print("  ❌ index and scan disagree at n =", n, ":", found_total, "vs", scan_found)
        sel.append(Float64(cand_total) / Float64(reps * n))
        cand_per_query.append(Float64(cand_total) / Float64(reps))
        cells_per_query.append(Float64(cells_total) / Float64(reps))
        window_ns.append(_ns_per(best_win, reps, 1))
        scan_ns.append(_ns_per(t5 - t4, reps, 1))
        print(
            "  n=" + String(n),
            "side=" + String(grid.side),
            "found=" + String(found_total),
            "cand/query=" + String(Float64(cand_total) / Float64(reps)),
            "selectivity=" + String(sel[s]),
            "ns/build_point=" + String(build_ns[s]),
        )

    # The gate: the fraction of the dataset examined must FALL at every step. A constant
    # fraction would mean the grid is not refining with the data; a rising one would mean the
    # index is losing ground as the problem grows, which is the failure that matters.
    var sel_falls = len(sel) == len(sizes)
    for i in range(1, len(sel)):
        if sel[i] >= sel[i - 1]:
            sel_falls = False
    print("")
    if sel_falls:
        print(
            "  ✅ selectivity falls monotonically:",
            String(sel[0]),
            "->",
            String(sel[len(sel) - 1]),
            "(ideal 1e-4)",
        )
    else:
        failures += 1
        print("  ❌ selectivity did not improve as the dataset grew")

    # And the improvement must be substantial, not a rounding: a 64x denser dataset should
    # examine a clearly smaller fraction. 4x is a floor with room for cell granularity.
    if len(sel) == len(sizes) and sel[0] > 0.0 and sel[len(sel) - 1] * 4.0 < sel[0]:
        print(
            "  ✅ and the ratio improves by at least 4x from 1024 to 65536 points:",
            String(sel[0] / sel[len(sel) - 1]) + "x",
        )
    else:
        failures += 1
        print("  ❌ the selectivity improvement is not material")

    # The WORK per query — cells touched plus candidates examined — is the algorithmic shape,
    # and it is exact arithmetic rather than a timing. Both must be flat across a 64x size
    # range: that is what "the query does not read the dataset" means, stated as a number.
    var work_flat = len(cand_per_query) == len(sizes) and len(cells_per_query) == len(sizes)
    if work_flat:
        var clo = cand_per_query[0]
        var chi = cand_per_query[0]
        var klo = cells_per_query[0]
        var khi = cells_per_query[0]
        for i in range(len(cand_per_query)):
            if cand_per_query[i] < clo:
                clo = cand_per_query[i]
            if cand_per_query[i] > chi:
                chi = cand_per_query[i]
            if cells_per_query[i] < klo:
                klo = cells_per_query[i]
            if cells_per_query[i] > khi:
                khi = cells_per_query[i]
        work_flat = _ratio_ok(chi, clo, 1.5) and _ratio_ok(khi, klo, 1.5)
    if work_flat:
        print(
            "  ✅ work per query is flat within 1.5x over a 64x size range:",
            String(cand_per_query[0]),
            "->",
            String(cand_per_query[len(cand_per_query) - 1]),
            "candidates,",
            String(cells_per_query[len(cells_per_query) - 1]),
            "cells",
        )
    else:
        failures += 1
        print("  ❌ work per query grew with n — the query is reading the dataset")

    # Wall time per query is NOT gated flat, because it is not flat: the same 16 candidate
    # reads cost more once the working set stops fitting in cache. What is gated is the
    # RELATIVE growth — the index must grow far more slowly than the scan over the identical
    # range, on this machine's own numbers, which is a statement about the two algorithms and
    # not about the cache either of them is running in.
    if len(scan_ns) == len(sizes) and len(window_ns) == len(sizes):
        var idx_growth = 0.0
        var scan_growth = 0.0
        if window_ns[0] > 0.0:
            idx_growth = window_ns[len(window_ns) - 1] / window_ns[0]
        if scan_ns[0] > 0.0:
            scan_growth = scan_ns[len(scan_ns) - 1] / scan_ns[0]
        print(
            "  ns/query: index",
            String(window_ns[0]) + " -> " + String(window_ns[len(window_ns) - 1]),
            "(" + String(idx_growth) + "x);",
            "scan",
            String(scan_ns[0]) + " -> " + String(scan_ns[len(scan_ns) - 1]),
            "(" + String(scan_growth) + "x)",
        )
        if scan_growth > 8.0 * idx_growth and idx_growth > 0.0:
            print("  ✅ the scan's growth factor is more than 8x the index's over the same range")
        else:
            failures += 1
            print("  ❌ the index did not grow materially more slowly than the full scan")
    else:
        failures += 1
        print("  ❌ the timing series is incomplete")

    # Build cost per point must be flat: a build whose per-point cost rises is a hidden
    # quadratic, and the cell count is chosen to keep it O(n).
    var build_flat = len(build_ns) == len(sizes)
    if build_flat:
        var blo = build_ns[0]
        var bhi = build_ns[0]
        for i in range(len(build_ns)):
            if build_ns[i] < blo:
                blo = build_ns[i]
            if build_ns[i] > bhi:
                bhi = build_ns[i]
        build_flat = _ratio_ok(bhi, blo, 4.0)
    if build_flat:
        print("  ✅ ns per point to build the index is flat across the same range")
    else:
        failures += 1
        print("  ❌ build cost per point is not flat — there is a hidden superlinear term")

    print("")
    print("── 2. exact k-nearest: candidates examined must not track n ──")
    for s in range(len(sizes)):
        var n = sizes[s]
        var xs = _keyed_points(n, 1)
        var ys = _keyed_points(n, 2)
        var grid = grid_build_flat(xs, ys, n, GEO_FRAME_PLANE_M, 4)
        if grid.status != GEO_OK:
            failures += 1
            continue
        var reps = 32
        var cand = 0
        var rings = 0
        var mism = 0
        # The indexed queries are timed ALONE. Putting the O(n) oracle inside the timed region
        # would report the brute force's cost as the index's — which is exactly the mistake
        # that makes a "sublinear" number look linear.
        var t0 = perf_counter_ns()
        for q in range(reps):
            var qx = (Float64(q % 8) + 0.5) * EXTENT_M / 8.0
            var qy = (Float64(q // 8) + 0.5) * EXTENT_M / 8.0
            var kn = grid_knn_flat(
                grid.cell_start, grid.cell_items, xs, ys, n, grid.side,
                grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
                qx, qy, 8, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
            )
            if kn.status != GEO_OK or not kn.exact:
                mism += 1
                continue
            cand += kn.candidates_examined
            rings += kn.rings_expanded
        var t1 = perf_counter_ns()
        # Exactness re-verified at scale, outside the timed region: same ids, same distances,
        # on every query. A pruning bug shows up at 65536 points long before it does at 25.
        for q in range(reps):
            var qx = (Float64(q % 8) + 0.5) * EXTENT_M / 8.0
            var qy = (Float64(q // 8) + 0.5) * EXTENT_M / 8.0
            var kn2 = grid_knn_flat(
                grid.cell_start, grid.cell_items, xs, ys, n, grid.side,
                grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
                qx, qy, 8, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
            )
            var bs = knn_scan_flat(
                xs, ys, n, qx, qy, 8, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
            )
            if kn2.status != GEO_OK or bs.status != GEO_OK:
                mism += 1
                continue
            for i in range(kn2.k_returned):
                if kn2.ids[i] != bs.ids[i] or kn2.distance_m[i] != bs.distance_m[i]:
                    mism += 1
        if mism != 0:
            failures += 1
            print("  ❌ indexed k-NN disagreed with the scan at n =", n, ":", mism)
        knn_cand.append(Float64(cand) / Float64(reps))
        print(
            "  n=" + String(n),
            "k=8",
            "cand/query=" + String(knn_cand[s]),
            "rings/query=" + String(Float64(rings) / Float64(reps)),
            "ns/query=" + String(_ns_per(t1 - t0, reps, 1)),
        )

    # The gate: candidate count is set by `k` and local density, not by dataset size. A 64x
    # larger dataset must not cost 64x more candidates.
    if (
        len(knn_cand) == len(sizes)
        and knn_cand[0] > 0.0
        and knn_cand[len(knn_cand) - 1] <= knn_cand[0] * 4.0
    ):
        print("")
        print(
            "  ✅ k-NN candidates stayed within 4x while the dataset grew 64x:",
            String(knn_cand[0]),
            "->",
            String(knn_cand[len(knn_cand) - 1]),
        )
    else:
        failures += 1
        print("  ❌ k-NN candidate count tracked the dataset size")

    print("")
    print("── 3. radius join: selectivity against the full cross product ──")
    var join_sel = List[Float64]()
    for s in range(len(sizes)):
        var n = sizes[s] // 4
        var xs = _keyed_points(n, 3)
        var ys = _keyed_points(n, 4)
        var t0 = perf_counter_ns()
        var j = join_within_flat(
            xs, ys, n, xs, ys, n, 10.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 1 << 20
        )
        var t1 = perf_counter_ns()
        if j.status != GEO_OK:
            failures += 1
            print("  ❌ join failed at n =", n, "status", j.status)
            continue
        # The nested-loop answer, on the two smallest sizes only — it is O(n^2) and is here as
        # an oracle, not as a measurement.
        if n <= 1024:
            var expect = 0
            for a in range(n):
                for b in range(n):
                    var ddx = xs[b] - xs[a]
                    var ddy = ys[b] - ys[a]
                    if sqrt(ddx * ddx + ddy * ddy) <= 10.0:
                        expect += 1
            if expect != j.n_pairs:
                failures += 1
                print("  ❌ join disagreed with nested loops at n =", n, ":", j.n_pairs, expect)
        join_sel.append(j.selectivity)
        print(
            "  n=" + String(n),
            "pairs=" + String(j.n_pairs),
            "cand=" + String(j.candidates_examined),
            "of " + String(j.full_scan_cost),
            "selectivity=" + String(j.selectivity),
            "ns/pair=" + String(_ns_per(t1 - t0, j.n_pairs if j.n_pairs > 0 else 1, 1)),
        )
    var join_falls = len(join_sel) == len(sizes)
    for i in range(1, len(join_sel)):
        if join_sel[i] >= join_sel[i - 1]:
            join_falls = False
    print("")
    if join_falls:
        print(
            "  ✅ join selectivity falls monotonically:",
            String(join_sel[0]),
            "->",
            String(join_sel[len(join_sel) - 1]),
        )
    else:
        failures += 1
        print("  ❌ join selectivity did not improve with scale")

    print("")
    print("── 4. point-in-polygon: cost per edge test must be flat ──")
    # A regular polygon inscribed in a circle of radius 400 m about the extent's centre, at
    # four vertex counts. The cost that must be flat is per (point x vertex) edge test — the
    # product, because that is the work, and charging only the sum is the defect rule 1c names.
    var ring_sizes = List[Int]()
    ring_sizes.append(64)
    ring_sizes.append(256)
    ring_sizes.append(1024)
    ring_sizes.append(2048)
    var pip_ns = List[Float64]()
    for s in range(len(ring_sizes)):
        var m = ring_sizes[s]
        # Same total edge tests at every vertex count, so every timed region is the same size.
        var n_probe = PIP_EDGE_TESTS // m
        var pxs = _keyed_points(n_probe, 5)
        var pys = _keyed_points(n_probe, 6)
        var rxs = List[Float64]()
        var rys = List[Float64]()
        for v in range(m):
            # Vertices by repeated rotation of a unit step, so no trig call is needed and the
            # ring is a deterministic function of `m` alone.
            var frac = Float64(v) / Float64(m)
            var t = frac * 8.0
            # A square-ish closed convex ring traced at constant speed: piecewise linear in
            # `t`, exact in binary, and convex — enough to exercise every edge.
            var ex = 0.0
            var ey = 0.0
            if t < 2.0:
                ex = t - 1.0
                ey = -1.0
            elif t < 4.0:
                ex = 1.0
                ey = t - 3.0
            elif t < 6.0:
                ex = 5.0 - t
                ey = 1.0
            else:
                ex = -1.0
                ey = 7.0 - t
            rxs.append(EXTENT_M / 2.0 + ex * 400.0)
            rys.append(EXTENT_M / 2.0 + ey * 400.0)
        var best: UInt = 0
        for r in range(REPEATS):
            var a0 = perf_counter_ns()
            var c = points_in_ring_flat(pxs, pys, n_probe, rxs, rys, m, GEO_FRAME_PLANE_M)
            var a1 = perf_counter_ns()
            if c.status != GEO_OK:
                failures += 1
                break
            if r == 0 or (a1 - a0) < best:
                best = a1 - a0
        var t0 = perf_counter_ns()
        var cls = points_in_ring_flat(pxs, pys, n_probe, rxs, rys, m, GEO_FRAME_PLANE_M)
        var t1 = perf_counter_ns()
        _ = t1 - t0
        if cls.status != GEO_OK or cls.edge_tests != n_probe * m:
            failures += 1
            print("  ❌ classification failed at m =", m, "status", cls.status)
            continue
        # The ring is the 800x800 m square centred in a 1000x1000 m extent, so about 64% of a
        # uniform sample must land inside. A sanity band, not a distributional test.
        var frac_in = Float64(cls.n_inside) / Float64(n_probe)
        if frac_in < 0.55 or frac_in > 0.72:
            failures += 1
            print("  ❌ inside fraction implausible at m =", m, ":", frac_in)
        pip_ns.append(_ns_per(best, n_probe * m, 1))
        print(
            "  vertices=" + String(m),
            "points=" + String(n_probe),
            "inside=" + String(cls.n_inside),
            "boundary=" + String(cls.n_boundary),
            "ns/edge_test=" + String(pip_ns[s]),
        )
    var pip_flat = len(pip_ns) == len(ring_sizes)
    if pip_flat:
        var plo = pip_ns[0]
        var phi = pip_ns[0]
        for i in range(len(pip_ns)):
            if pip_ns[i] < plo:
                plo = pip_ns[i]
            if pip_ns[i] > phi:
                phi = pip_ns[i]
        pip_flat = _ratio_ok(phi, plo, 4.0)
    print("")
    if pip_flat:
        print("  ✅ ns per edge test is flat from 64 to 2048 vertices — the cost is the product")
    else:
        failures += 1
        print("  ❌ per-edge-test cost is not flat")

    print("")
    print("── 5. route matrix and area: per-cell and per-vertex cost ──")
    # A route matrix is n_o * n_d distance evaluations, so the per-CELL cost is the shape that
    # matters; charging per row would hide the second factor entirely.
    var mat_ns = List[Float64]()
    var mat_sizes = List[Int]()
    mat_sizes.append(32)
    mat_sizes.append(64)
    mat_sizes.append(128)
    mat_sizes.append(256)
    for s in range(len(mat_sizes)):
        var q = mat_sizes[s]
        var oxs = _keyed_points(q, 7)
        var oys = _keyed_points(q, 8)
        var best: UInt = 0
        for r in range(REPEATS):
            var b0 = perf_counter_ns()
            var mm = route_matrix_flat(
                oxs, oys, q, oxs, oys, q, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
            )
            var b1 = perf_counter_ns()
            if mm.status != GEO_OK:
                failures += 1
                break
            if r == 0 or (b1 - b0) < best:
                best = b1 - b0
        var mat = route_matrix_flat(
            oxs, oys, q, oxs, oys, q, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
        )
        if mat.status != GEO_OK or mat.n_cells != q * q:
            failures += 1
            print("  ❌ route matrix failed at", q)
            continue
        mat_ns.append(_ns_per(best, q * q, 1))
        print(
            "  " + String(q) + "x" + String(q),
            "cells=" + String(mat.n_cells),
            "min=" + String(mat.min_distance_m),
            "max=" + String(mat.max_distance_m),
            "ns/cell=" + String(mat_ns[s]),
        )
    var mat_flat = len(mat_ns) == len(mat_sizes)
    if mat_flat:
        var mlo = mat_ns[0]
        var mhi = mat_ns[0]
        for i in range(len(mat_ns)):
            if mat_ns[i] < mlo:
                mlo = mat_ns[i]
            if mat_ns[i] > mhi:
                mhi = mat_ns[i]
        mat_flat = _ratio_ok(mhi, mlo, 4.0)
    if mat_flat:
        print("  ✅ ns per matrix cell is flat as the matrix grows 64x in cells")
    else:
        failures += 1
        print("  ❌ per-cell matrix cost is not flat")

    # A degree-frame ring area at scale: the projection is O(n) and the shoelace is O(n), so
    # the per-vertex cost must be flat. Vertices are a deterministic fan around (0.5, 0.5).
    var area_ns = List[Float64]()
    for s in range(len(ring_sizes)):
        var m = ring_sizes[s]
        var axs = List[Float64]()
        var ays = List[Float64]()
        for v in range(m):
            var frac = Float64(v) / Float64(m)
            var t = frac * 4.0
            var ex = 0.0
            var ey = 0.0
            if t < 1.0:
                ex = t
                ey = 0.0
            elif t < 2.0:
                ex = 1.0
                ey = t - 1.0
            elif t < 3.0:
                ex = 3.0 - t
                ey = 1.0
            else:
                ex = 0.0
                ey = 4.0 - t
            axs.append(ex)
            ays.append(ey)
        var best: UInt = 0
        for r in range(REPEATS):
            var c0 = perf_counter_ns()
            var aa = ring_area_flat(axs, ays, m, GEO_FRAME_LONLAT_DEG)
            var c1 = perf_counter_ns()
            if aa.status != GEO_OK:
                failures += 1
                break
            if r == 0 or (c1 - c0) < best:
                best = c1 - c0
        var ar = ring_area_flat(axs, ays, m, GEO_FRAME_LONLAT_DEG)
        if ar.status != GEO_OK or not ar.projected or not ar.has_area:
            failures += 1
            print("  ❌ ring area failed at m =", m, "status", ar.status)
            continue
        # The ring traces the 1x1 degree box, whose projected area about its own centre is
        # 12 363 840 916.39 m^2 — the same closed form the suite asserts. A denser tracing of
        # the same square must give the same area, which is a correctness check at scale.
        if fabs(ar.area_m2 - 12363840916.385195) > 12363840916.385195 * 1.0e-6:
            failures += 1
            print("  ❌ the 1x1 degree box area drifted at m =", m, ":", ar.area_m2)
        area_ns.append(_ns_per(best, m, 1))
        print(
            "  vertices=" + String(m),
            "area_m2=" + String(ar.area_m2),
            "ns/vertex=" + String(area_ns[s]),
        )
    var area_flat = len(area_ns) == len(ring_sizes)
    if area_flat:
        var alo = area_ns[0]
        var ahi = area_ns[0]
        for i in range(len(area_ns)):
            if area_ns[i] < alo:
                alo = area_ns[i]
            if area_ns[i] > ahi:
                ahi = area_ns[i]
        area_flat = _ratio_ok(ahi, alo, 4.0)
    if area_flat:
        print("  ✅ ns per vertex for a projected ring area is flat")
    else:
        failures += 1
        print("  ❌ per-vertex area cost is not flat")

    print("")
    print("── 6. the CELLS a probe reads: charged, and the ceiling binds ──")
    # The gates above all measure well-shaped uniform data, where candidates and cells rise
    # together and either one would do as a proxy for the cost. This section measures the case
    # where they do NOT: a right side clustered on the diagonal of a 1e6 x 1e6 m plane, and
    # left points whose search box sits entirely off that diagonal. Every probe then covers
    # thousands of cells and examines ZERO candidates, so a budget or a complexity claim
    # written in candidates prices the whole scan at nothing while it runs for minutes.
    #
    # Two shapes are gated, and neither is a nanosecond count:
    #   * cells charged per left point is FLAT as `n_left` grows 16x — the cost is linear in
    #     the probes, which is what makes it predictable;
    #   * the MARGINAL wall time per charged cell is flat over the same range, which is the
    #     statement that the charged quantity is the one actually being spent. It has to be the
    #     marginal cost and not the average: one join call also pays a fixed
    #     O(n_right log n_right) index build, which at n_left = 64 is most of the measurement
    #     and would make the average per-cell cost fall 6x purely as that fixed cost amortises.
    #     Differencing consecutive sizes removes it. Time per CANDIDATE is not even defined
    #     here, because candidates are zero — that is the point.
    var sparse_right = 1 << 15
    var srx = List[Float64]()
    var sry = List[Float64]()
    for i in range(sparse_right):
        var frac_r = Float64(i) / Float64(sparse_right)
        srx.append(frac_r * 1.0e6)
        sry.append(frac_r * 1.0e6)
    var sparse_lefts = List[Int]()
    sparse_lefts.append(64)
    sparse_lefts.append(256)
    sparse_lefts.append(1024)
    var cells_per_left = List[Float64]()
    var wall_ns = List[Float64]()
    var cells_total = List[Float64]()
    for s in range(len(sparse_lefts)):
        var nl = sparse_lefts[s]
        var slx = List[Float64]()
        var sly = List[Float64]()
        for _ in range(nl):
            slx.append(7.5e5)
            sly.append(2.5e5)
        var best_j: UInt = 0
        for r in range(REPEATS):
            var s0 = perf_counter_ns()
            var jj = join_within_flat(
                slx, sly, nl, srx, sry, sparse_right, 2.0e5,
                GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 1 << 20,
            )
            var s1 = perf_counter_ns()
            if jj.status != GEO_OK or jj.n_pairs != 0:
                failures += 1
                break
            if r == 0 or (s1 - s0) < best_j:
                best_j = s1 - s0
        var probe = join_within_flat(
            slx, sly, nl, srx, sry, sparse_right, 2.0e5,
            GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 1 << 20,
        )
        if probe.status != GEO_OK or probe.cells_examined <= 0:
            failures += 1
            print("  ❌ the sparse probe reported no cell cost at n_left", nl)
            continue
        cells_per_left.append(Float64(probe.cells_examined) / Float64(nl))
        wall_ns.append(Float64(Int(best_j)))
        cells_total.append(Float64(probe.cells_examined))
        print(
            "  n_left=" + String(nl),
            "cells=" + String(probe.cells_examined),
            "candidates=" + String(probe.candidates_examined),
            "cells/left=" + String(cells_per_left[s]),
            "wall_ns=" + String(wall_ns[s]),
        )
    var charge_flat = len(cells_per_left) == len(sparse_lefts)
    if charge_flat:
        var clo = cells_per_left[0]
        var chi = cells_per_left[0]
        for i in range(len(cells_per_left)):
            if cells_per_left[i] < clo:
                clo = cells_per_left[i]
            if cells_per_left[i] > chi:
                chi = cells_per_left[i]
        charge_flat = _ratio_ok(chi, clo, 1.5)
        var marginal = List[Float64]()
        for i in range(1, len(wall_ns)):
            var dcells = cells_total[i] - cells_total[i - 1]
            var dns = wall_ns[i] - wall_ns[i - 1]
            if dcells <= 0.0 or dns <= 0.0:
                charge_flat = False
                continue
            marginal.append(dns / dcells)
            print(
                "  marginal " + String(sparse_lefts[i - 1]) + "->"
                + String(sparse_lefts[i]),
                "ns/cell=" + String(dns / dcells),
            )
        if len(marginal) < 2:
            charge_flat = False
        else:
            var mlo2 = marginal[0]
            var mhi2 = marginal[0]
            for i in range(len(marginal)):
                if marginal[i] < mlo2:
                    mlo2 = marginal[i]
                if marginal[i] > mhi2:
                    mhi2 = marginal[i]
            charge_flat = charge_flat and _ratio_ok(mhi2, mlo2, 4.0)
    if charge_flat:
        print("  ✅ cells charged per left point is flat, and so is the marginal ns per cell")
    else:
        failures += 1
        print("  ❌ the cell charge does not track the work done")

    # And the ceiling BINDS. 2^13 left points over 2^18 diagonal right points is 3.4e8 cell
    # reads against GEO_MAX_CANDIDATE_WORK = 2^26, so the join must stop with
    # GEO_OK_TRUNCATED. Charged on candidates alone this same call completed under a plain
    # GEO_OK with `candidates_examined = 0`: 0.49 s at n_left = 2^13, and 11 minutes at the
    # admitted n_left ceiling, all of it invisible to the budget. A ceiling that no input can
    # reach is not a ceiling, so the gate is that this input reaches it.
    var wall_l = List[Float64]()
    var wall_ly = List[Float64]()
    for _ in range(1 << 13):
        wall_l.append(7.5e5)
        wall_ly.append(2.5e5)
    var wall_r = List[Float64]()
    var wall_ry = List[Float64]()
    for i in range(1 << 18):
        var frac_w = Float64(i) / Float64(1 << 18)
        wall_r.append(frac_w * 1.0e6)
        wall_ry.append(frac_w * 1.0e6)
    var cap0 = perf_counter_ns()
    var capped = join_within_flat(
        wall_l, wall_ly, 1 << 13, wall_r, wall_ry, 1 << 18, 2.0e5,
        GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 1 << 20,
    )
    var cap1 = perf_counter_ns()
    print(
        "  ceiling probe: status=" + String(capped.status),
        "truncated=" + String(capped.truncated),
        "cells=" + String(capped.cells_examined),
        "candidates=" + String(capped.candidates_examined),
        "wall_ms=" + String(Float64(Int(cap1 - cap0)) / 1.0e6),
    )
    if (
        capped.status == GEO_OK_TRUNCATED
        and capped.truncated
        and capped.candidates_examined == 0
        and capped.cells_examined > (1 << 26)
    ):
        print("  ✅ a cells-only workload is stopped by GEO_MAX_CANDIDATE_WORK, not by luck")
    else:
        failures += 1
        print("  ❌ the work ceiling did not bind on a cells-only workload")

    print("")
    print("── 7. the segment clamp: per-segment cost, and long legs ──")
    # `point_to_segment_flat` decides the case from four `initial_bearing` calls, which is a
    # constant. The gate is that the per-segment cost does not depend on the LEG LENGTH: a
    # 120-degree leg must cost the same as a 1-degree one, or the clamp has acquired a
    # search. Legs are laid along the equator so the arithmetic is identical at every length.
    var leg_degs = List[Float64]()
    leg_degs.append(1.0)
    leg_degs.append(30.0)
    leg_degs.append(95.0)
    leg_degs.append(120.0)
    var seg_ns = List[Float64]()
    var clamp_bad = 0
    for s in range(len(leg_degs)):
        var leg = leg_degs[s]
        var best_s: UInt = 0
        for r in range(REPEATS):
            var q0 = perf_counter_ns()
            var acc = 0.0
            for t in range(2048):
                # A query past the END of the leg at every iteration: the clamped answer is the
                # endpoint distance, and the unclamped one would be near zero.
                var over = leg + 1.0 + Float64(t % 16) * 0.5
                var sd = point_to_segment_flat(
                    over, 0.0, 0.0, 0.0, leg, 0.0,
                    GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE,
                )
                if sd.status != GEO_OK or sd.distance_m < 1.0e5:
                    clamp_bad += 1
                acc += sd.distance_m
            var q1 = perf_counter_ns()
            if acc <= 0.0:
                failures += 1
            if r == 0 or (q1 - q0) < best_s:
                best_s = q1 - q0
        seg_ns.append(_ns_per(best_s, 2048, 1))
        print(
            "  leg=" + String(leg) + " deg",
            "ns/segment=" + String(seg_ns[s]),
        )
    var seg_flat = len(seg_ns) == len(leg_degs) and clamp_bad == 0
    if seg_flat:
        var slo = seg_ns[0]
        var shi = seg_ns[0]
        for i in range(len(seg_ns)):
            if seg_ns[i] < slo:
                slo = seg_ns[i]
            if seg_ns[i] > shi:
                shi = seg_ns[i]
        seg_flat = _ratio_ok(shi, slo, 4.0)
    if seg_flat:
        print("  ✅ ns per segment is flat from a 1-degree leg to a 120-degree one, all clamped")
    else:
        failures += 1
        print("  ❌ the clamp cost depends on the leg length, or a long leg was not clamped:", clamp_bad)

    print("")
    print("── 8. determinism: the same seed gives the same layout ──")
    # An index is only comparable across runs if its layout is a pure function of the input.
    # Rebuilding from the same seed must give a bit-identical bucket array.
    var d1x = _keyed_points(4096, 1)
    var d1y = _keyed_points(4096, 2)
    var g1 = grid_build_flat(d1x, d1y, 4096, GEO_FRAME_PLANE_M, 4)
    var d2x = _keyed_points(4096, 1)
    var d2y = _keyed_points(4096, 2)
    var g2 = grid_build_flat(d2x, d2y, 4096, GEO_FRAME_PLANE_M, 4)
    var identical = (
        g1.status == GEO_OK
        and g2.status == GEO_OK
        and len(g1.cell_items) == len(g2.cell_items)
        and len(g1.cell_start) == len(g2.cell_start)
    )
    if identical:
        for i in range(len(g1.cell_items)):
            if g1.cell_items[i] != g2.cell_items[i]:
                identical = False
        for i in range(len(g1.cell_start)):
            if g1.cell_start[i] != g2.cell_start[i]:
                identical = False
    if identical:
        print("  ✅ two builds from the same seed produce a bit-identical bucket layout")
    else:
        failures += 1
        print("  ❌ the index layout is not a pure function of the input")

    print("")
    if failures == 0:
        print("BENCH_GATE geospatial PASS")
    else:
        print("BENCH_GATE geospatial FAIL " + String(failures))
