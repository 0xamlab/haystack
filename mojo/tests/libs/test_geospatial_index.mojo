"""test_geospatial_index.mojo — known-value tests for the cell grid, windows and k-nearest.

Hand-written. An index has exactly one job — return the same set a full scan would, faster —
so the assertions are of three kinds, and none of them is the index agreeing with itself:

1. *Hand-countable answers.* A 5x5 lattice of points at integer coordinates 0..4 in a metre
   frame. A window query for [1,2] x [1,2] must return the four points (1,1) (1,2) (2,1) (2,2)
   — a reader can count them. k-nearest from (0,0) with k=3 must return (0,0) at 0 m, then two
   points at exactly 1 m.

2. *An independent oracle.* `window_scan_flat` and `knn_scan_flat` are O(n) implementations
   that share no code path with the grid: they read the coordinate arrays directly and never
   touch `cell_start`/`cell_items`. And the k-nearest DISTANCES are checked a third time
   against the FROZEN `heap.k_smallest` of the complete distance list, which is a kernel from
   another package used as an oracle.

3. *Refusals, on layouts that would otherwise abort the worker.* A pointer array of the wrong
   length, a decreasing pointer, an item id past the point count, `n` past the coordinate
   arrays. Each must come back as `GEO_ERR_LAYOUT` or `GEO_ERR_COUNT`. The suite completing at
   all is the proof: an out-of-range `List` read is an uncatchable abort, so a process that
   prints the final line did not perform one.

The selectivity CLAIM is not asserted here — it is measured in
`benchmarks/mojo_benchmarks/bench_geospatial.mojo`, gated on the ratio improving as the
dataset grows, because a selectivity number on 25 points would be noise dressed as evidence.
"""
from std.math import abs as fabs, sqrt

from heap import k_smallest

from geospatial.contract import (
    GEO_ERR_ANTIMERIDIAN,
    GEO_ERR_BUDGET,
    GEO_ERR_COUNT,
    GEO_ERR_LAYOUT,
    GEO_ERR_METRIC_UNSUPPORTED_HERE,
    GEO_ERR_PARAM,
    GEO_ERR_UNIT_MISMATCH,
    GEO_ERR_WINDOW,
    GEO_FRAME_LONLAT_DEG,
    GEO_FRAME_PLANE_M,
    GEO_M_PER_DEG,
    GEO_METRIC_EUCLIDEAN,
    GEO_METRIC_HAVERSINE,
    GEO_METRIC_VINCENTY,
    GEO_OK,
)
from geospatial.index import (
    GEO_MAX_GRID_SIDE,
    GEO_MAX_TARGET_PER_CELL,
    grid_build_flat,
    grid_knn_flat,
    grid_validate_flat,
    grid_window_flat,
    knn_scan_flat,
    window_scan_flat,
)


fn main() raises:
    var passed = 0
    var failed = 0
    print("[geospatial.index]")

    # ── a 5x5 integer lattice in a metre frame ────────────────────────────────
    var xs = List[Float64]()
    var ys = List[Float64]()
    for i in range(5):
        for j in range(5):
            xs.append(Float64(i))
            ys.append(Float64(j))
    var n = 25

    var grid = grid_build_flat(xs, ys, n, GEO_FRAME_PLANE_M, 4)
    # side is the smallest s with s*s*4 >= 25, i.e. 3 (9 cells, 36 slots).
    if (
        grid.status == GEO_OK
        and grid.side == 3
        and grid.n_cells == 9
        and grid.n_points == 25
        and grid.skipped == 0
        and grid.has_extent
        and grid.min_x == 0.0
        and grid.max_x == 4.0
        and grid.min_y == 0.0
        and grid.max_y == 4.0
        and len(grid.cell_start) == 10
        and len(grid.cell_items) == 25
    ):
        passed += 1
        print("  ✅ 25 points, target 4 per cell -> side 3, 9 cells, 25 items, 0 skipped")
    else:
        failed += 1
        print("  ❌ build wrong:", grid.status, grid.side, grid.n_cells, grid.skipped)

    # Every point must appear exactly once: the buckets partition the set. `skipped` coming
    # back non-zero would mean the cell arithmetic produced an id outside its own grid.
    var seen = List[Int]()
    for _ in range(n):
        seen.append(0)
    for k in range(len(grid.cell_items)):
        var pid = grid.cell_items[k]
        if pid >= 0 and pid < n:
            seen[pid] += 1
    var partition = True
    for i in range(n):
        if seen[i] != 1:
            partition = False
    if partition and grid.occupied_cells > 0 and grid.max_cell_occupancy > 0:
        passed += 1
        print("  ✅ the buckets partition the point set: every id appears exactly once")
    else:
        failed += 1
        print("  ❌ the bucket layout is not a partition")

    if grid_validate_flat(grid.cell_start, grid.cell_items, n, grid.side) == GEO_OK:
        passed += 1
        print("  ✅ the built layout passes the full O(n + cells) certificate")
    else:
        failed += 1
        print("  ❌ a freshly built layout failed its own validator")

    # ── window query: a hand-countable answer ────────────────────────────────
    # [1,2] x [1,2] contains exactly (1,1) (1,2) (2,1) (2,2).
    var win = grid_window_flat(
        grid.cell_start, grid.cell_items, xs, ys, n, grid.side,
        grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
        1.0, 1.0, 2.0, 2.0, GEO_FRAME_PLANE_M,
    )
    var scan = window_scan_flat(xs, ys, n, 1.0, 1.0, 2.0, 2.0, GEO_FRAME_PLANE_M)
    if (
        win.status == GEO_OK
        and win.n_found == 4
        and scan.status == GEO_OK
        and scan.n_found == 4
    ):
        passed += 1
        print("  ✅ the closed box [1,2]x[1,2] holds exactly 4 lattice points")
    else:
        failed += 1
        print("  ❌ window count wrong:", win.n_found, scan.n_found)

    # The indexed answer must be the SAME SET as the full scan's, not merely the same size.
    var same_set = len(win.ids) == len(scan.ids)
    if same_set:
        for a in range(len(scan.ids)):
            var found = False
            for b in range(len(win.ids)):
                if win.ids[b] == scan.ids[a]:
                    found = True
            if not found:
                same_set = False
    if same_set:
        passed += 1
        print("  ✅ and it is the same SET the independent O(n) scan returns")
    else:
        failed += 1
        print("  ❌ the index and the full scan disagree on the window")

    # The index examined fewer candidates than the full scan cost. On 25 points this is a
    # sanity check, not the selectivity claim — that lives in the benchmark.
    if win.candidates_examined < win.full_scan_cost and win.full_scan_cost == n:
        passed += 1
        print(
            "  ✅ candidates examined",
            String(win.candidates_examined),
            "vs a full scan of 25",
        )
    else:
        failed += 1
        print("  ❌ the index examined no fewer candidates:", win.candidates_examined)

    # A window entirely outside the extent is an ANSWER (zero found, status OK), not a refusal:
    # a caller may legitimately ask about empty space. It is not free: the box clamps onto the
    # boundary cell, that cell is read, and `cells_examined` says so. There is no
    # "outside the extent" early-out, because the only extent maximum available to this
    # function would be the reconstructed `min + cell * side`, which is a rounding error short
    # of the truth — see the extent-maximum test below, which is what that early-out broke.
    var empty_win = grid_window_flat(
        grid.cell_start, grid.cell_items, xs, ys, n, grid.side,
        grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
        100.0, 100.0, 200.0, 200.0, GEO_FRAME_PLANE_M,
    )
    if (
        empty_win.status == GEO_OK
        and empty_win.n_found == 0
        and empty_win.cells_examined == 1
        and empty_win.candidates_examined == 4
    ):
        passed += 1
        print("  ✅ a window over empty space answers 0 found, reading only the clamped cell")
    else:
        failed += 1
        print(
            "  ❌ an out-of-extent window was not answered:", empty_win.status,
            empty_win.n_found, empty_win.cells_examined,
        )

    # ── the grid's OWN extent maximum, where a reconstructed extent loses points ─
    # A 10x10 lattice at 0.1 steps: min_x = 0.0, max_x = 0.9, side 5, cell_w = 0.18. The
    # extent maximum reconstructed as `min_x + cell_w * side` is 0.8999999999999999 — strictly
    # BELOW the real 0.9 — so any test of the query box against that reconstruction declares a
    # box on the grid's own right edge to be outside the grid. It is not: 19 of the 100 points
    # (the x = 0.9 column and the y = 0.9 row) live exactly there.
    var lx = List[Float64]()
    var ly = List[Float64]()
    for i in range(100):
        lx.append(Float64(i % 10) / 10.0)
        ly.append(Float64(i // 10) / 10.0)
    var lgrid = grid_build_flat(lx, ly, 100, GEO_FRAME_PLANE_M, 4)
    var recon = lgrid.min_x + lgrid.cell_w * Float64(lgrid.side)
    if lgrid.status == GEO_OK and lgrid.max_x == 0.9 and recon < 0.9:
        passed += 1
        print(
            "  ✅ the reconstructed extent maximum", String(recon),
            "is below the real 0.9 — the trap is live on this data",
        )
    else:
        failed += 1
        print("  ❌ the 10x10 lattice does not reproduce the reconstruction gap:", recon)

    # A degenerate box exactly ON the extent maximum must find the corner point, and the
    # module's independent oracle must agree. This is the assertion the removed early-out
    # failed: it returned GEO_OK with n_found = 0 and cells_examined = 0.
    var corner = grid_window_flat(
        lgrid.cell_start, lgrid.cell_items, lx, ly, 100, lgrid.side,
        lgrid.min_x, lgrid.min_y, lgrid.cell_w, lgrid.cell_h,
        lgrid.max_x, lgrid.max_y, lgrid.max_x, lgrid.max_y, GEO_FRAME_PLANE_M,
    )
    var corner_scan = window_scan_flat(
        lx, ly, 100, lgrid.max_x, lgrid.max_y, lgrid.max_x, lgrid.max_y, GEO_FRAME_PLANE_M
    )
    if (
        corner.status == GEO_OK
        and corner.n_found == 1
        and corner_scan.n_found == 1
        and corner.ids[0] == 99
        and corner.cells_examined >= 1
    ):
        passed += 1
        print("  ✅ a box on the extent maximum finds point 99, and the O(n) scan agrees")
    else:
        failed += 1
        print(
            "  ❌ the extent-maximum box lost the corner point:", corner.status,
            corner.n_found, corner_scan.n_found, corner.cells_examined,
        )

    # And the whole edge, not just the corner: the x = 0.9 column is ten points and the
    # y = 0.9 row is ten more, nine of them shared, so the union is 19 — the exact set the
    # reconstruction dropped. Every one of the 100 points must be found by a box on itself.
    var edge_found = 0
    var edge_bad = 0
    for i in range(100):
        var one = grid_window_flat(
            lgrid.cell_start, lgrid.cell_items, lx, ly, 100, lgrid.side,
            lgrid.min_x, lgrid.min_y, lgrid.cell_w, lgrid.cell_h,
            lx[i], ly[i], lx[i], ly[i], GEO_FRAME_PLANE_M,
        )
        var scan_one = window_scan_flat(
            lx, ly, 100, lx[i], ly[i], lx[i], ly[i], GEO_FRAME_PLANE_M
        )
        if one.status != GEO_OK or one.n_found != scan_one.n_found or one.n_found == 0:
            edge_bad += 1
            continue
        if lx[i] == 0.9 or ly[i] == 0.9:
            edge_found += 1
    if edge_bad == 0 and edge_found == 19:
        passed += 1
        print("  ✅ all 100 self-boxes agree with the scan, including the 19 on the extent edge")
    else:
        failed += 1
        print("  ❌ self-box queries disagree with the scan:", edge_bad, edge_found)

    # A single point is a legitimate degenerate window: the whole extent collapses and every
    # point lands in cell 0, which is correct rather than a division by a zero cell width.
    var one_x = List[Float64]()
    var one_y = List[Float64]()
    for _ in range(6):
        one_x.append(3.0)
        one_y.append(7.0)
    var flat = grid_build_flat(one_x, one_y, 6, GEO_FRAME_PLANE_M, 4)
    if (
        flat.status == GEO_OK
        and flat.cell_w == 0.0
        and flat.cell_h == 0.0
        and flat.occupied_cells == 1
        and flat.max_cell_occupancy == 6
    ):
        passed += 1
        print("  ✅ six identical points: zero cell width, one occupied cell holding all 6")
    else:
        failed += 1
        print("  ❌ a degenerate extent was mishandled:", flat.status, flat.cell_w)

    var flat_win = grid_window_flat(
        flat.cell_start, flat.cell_items, one_x, one_y, 6, flat.side,
        flat.min_x, flat.min_y, flat.cell_w, flat.cell_h,
        3.0, 7.0, 3.0, 7.0, GEO_FRAME_PLANE_M,
    )
    if flat_win.status == GEO_OK and flat_win.n_found == 6:
        passed += 1
        print("  ✅ and a zero-area window at that point finds all six")
    else:
        failed += 1
        print("  ❌ the degenerate window found:", flat_win.n_found)

    # ── window refusals ─────────────────────────────────────────────────────
    # An INVERTED longitude range is how a caller spells a window that wraps the seam, so it
    # gets GEO_ERR_ANTIMERIDIAN and not a generic complaint — silently returning the box's
    # complement (nothing) is the quiet wrong answer. In a projected frame there is no seam.
    var wrapped = window_scan_flat(xs, ys, n, 170.0, 0.0, -170.0, 1.0, GEO_FRAME_LONLAT_DEG)
    var inverted = window_scan_flat(xs, ys, n, 3.0, 0.0, 1.0, 1.0, GEO_FRAME_PLANE_M)
    var inv_y = window_scan_flat(xs, ys, n, 1.0, 3.0, 2.0, 1.0, GEO_FRAME_PLANE_M)
    if (
        wrapped.status == GEO_ERR_ANTIMERIDIAN
        and inverted.status == GEO_ERR_WINDOW
        and inv_y.status == GEO_ERR_WINDOW
    ):
        passed += 1
        print("  ✅ a wrapped degree window is ANTIMERIDIAN; an inverted plane box is WINDOW")
    else:
        failed += 1
        print("  ❌ window refusals wrong:", wrapped.status, inverted.status)

    # ── layout refusals: each one would otherwise read past a List end ───────
    var short_start = List[Int]()
    short_start.append(0)
    var bad_len = grid_window_flat(
        short_start, grid.cell_items, xs, ys, n, grid.side,
        grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
        1.0, 1.0, 2.0, 2.0, GEO_FRAME_PLANE_M,
    )
    var over_count = grid_window_flat(
        grid.cell_start, grid.cell_items, xs, ys, 999, grid.side,
        grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
        1.0, 1.0, 2.0, 2.0, GEO_FRAME_PLANE_M,
    )
    var bad_side = grid_window_flat(
        grid.cell_start, grid.cell_items, xs, ys, n, -3,
        grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
        1.0, 1.0, 2.0, 2.0, GEO_FRAME_PLANE_M,
    )
    if (
        bad_len.status == GEO_ERR_LAYOUT
        and over_count.status == GEO_ERR_COUNT
        and bad_side.status == GEO_ERR_PARAM
    ):
        passed += 1
        print("  ✅ a short pointer array, n=999 and side=-3 all refuse before any read")
    else:
        failed += 1
        print("  ❌ a malformed layout was accepted:", bad_len.status, over_count.status)

    # An item id pointing past the point count is the three-deep abort: cell_items[k] -> xs[id].
    var poisoned = grid.cell_items.copy()
    poisoned[0] = 9999
    var poison_win = grid_window_flat(
        grid.cell_start, poisoned, xs, ys, n, grid.side,
        grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
        0.0, 0.0, 4.0, 4.0, GEO_FRAME_PLANE_M,
    )
    if poison_win.status == GEO_ERR_LAYOUT and poison_win.n_found == 0:
        passed += 1
        print("  ✅ an item id of 9999 over 25 points is GEO_ERR_LAYOUT, not an abort")
    else:
        failed += 1
        print("  ❌ a poisoned item id was followed:", poison_win.status)

    # And the full validator catches the same layouts, plus a non-monotone pointer.
    var non_mono = grid.cell_start.copy()
    non_mono[5] = -1
    if (
        grid_validate_flat(grid.cell_start, poisoned, n, grid.side) == GEO_ERR_LAYOUT
        and grid_validate_flat(non_mono, grid.cell_items, n, grid.side) == GEO_ERR_LAYOUT
        and grid_validate_flat(short_start, grid.cell_items, n, grid.side) == GEO_ERR_LAYOUT
        and grid_validate_flat(grid.cell_start, grid.cell_items, n, 0) == GEO_ERR_PARAM
        and grid_validate_flat(
            grid.cell_start, grid.cell_items, n, GEO_MAX_GRID_SIDE + 1
        )
        == GEO_ERR_PARAM
    ):
        passed += 1
        print("  ✅ the certificate rejects a bad id, a decreasing pointer and side > 2^10")
    else:
        failed += 1
        print("  ❌ the layout certificate misses a defect")

    # ── k-nearest: hand-countable, then two independent oracles ─────────────
    # From (0,0) on the lattice: (0,0) at 0 m, then (0,1) and (1,0) both at exactly 1 m.
    var knn = grid_knn_flat(
        grid.cell_start, grid.cell_items, xs, ys, n, grid.side,
        grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
        0.0, 0.0, 3, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
    )
    if (
        knn.status == GEO_OK
        and knn.k_returned == 3
        and knn.exact
        and knn.distance_m[0] == 0.0
        and knn.distance_m[1] == 1.0
        and knn.distance_m[2] == 1.0
        and knn.has_max_distance
        and knn.max_distance_m == 1.0
    ):
        passed += 1
        print("  ✅ 3-nearest to (0,0): distances 0, 1, 1 metres exactly")
    else:
        failed += 1
        print("  ❌ knn distances wrong:", knn.k_returned, knn.distance_m[0])

    # The two points at 1 m are a TIE, broken by ascending id so the answer is a function of
    # the data and not of which cell was read first. Point (0,1) is id 1 and (1,0) is id 5.
    if knn.ids[0] == 0 and knn.ids[1] == 1 and knn.ids[2] == 5:
        passed += 1
        print("  ✅ the 1-metre tie is broken by ascending id: 0, then 1, then 5")
    else:
        failed += 1
        print("  ❌ the tie-break is layout-dependent:", knn.ids[1], knn.ids[2])

    # Oracle 1: the O(n) brute force, which shares no code path with the grid.
    var brute = knn_scan_flat(xs, ys, n, 0.0, 0.0, 3, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN)
    var agree = brute.status == GEO_OK and brute.k_returned == knn.k_returned
    if agree:
        for i in range(brute.k_returned):
            if brute.ids[i] != knn.ids[i] or brute.distance_m[i] != knn.distance_m[i]:
                agree = False
    if agree:
        passed += 1
        print("  ✅ the indexed answer is identical to the independent O(n) scan, id for id")
    else:
        failed += 1
        print("  ❌ index and brute force disagree")

    # Oracle 2: the FROZEN heap.k_smallest over the complete distance list. A different
    # package, a different algorithm, the same three distances.
    var all_d = List[Float64]()
    for i in range(n):
        var ddx = xs[i]
        var ddy = ys[i]
        all_d.append(sqrt(ddx * ddx + ddy * ddy))
    var oracle = k_smallest(all_d, 3)
    var oracle_ok = len(oracle) == 3
    if oracle_ok:
        for i in range(3):
            if fabs(oracle[i] - knn.distance_m[i]) > 1.0e-12:
                oracle_ok = False
    if oracle_ok:
        passed += 1
        print("  ✅ and the same three distances come out of the frozen heap.k_smallest")
    else:
        failed += 1
        print("  ❌ the frozen k_smallest oracle disagrees")

    # A sweep over every lattice point as the query, at three values of k: the index and the
    # scan must agree EVERY time, not on the one query that was tried.
    var sweep_bad = 0
    for q in range(n):
        for kk in range(1, 4):
            var gi = grid_knn_flat(
                grid.cell_start, grid.cell_items, xs, ys, n, grid.side,
                grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
                xs[q], ys[q], kk, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
            )
            var bs = knn_scan_flat(
                xs, ys, n, xs[q], ys[q], kk, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
            )
            if gi.status != GEO_OK or bs.status != GEO_OK or gi.k_returned != kk:
                sweep_bad += 1
                continue
            for i in range(kk):
                if gi.ids[i] != bs.ids[i] or gi.distance_m[i] != bs.distance_m[i]:
                    sweep_bad += 1
    if sweep_bad == 0:
        passed += 1
        print("  ✅ 75 index/scan comparisons (25 queries x k=1,2,3) agree exactly")
    else:
        failed += 1
        print("  ❌ the sweep found disagreements:", sweep_bad)

    # ── k-nearest on a DEGREE frame, where the stopping bound is the hard part ─
    # This lattice is chosen to be ADVERSARIAL to the stopping rule, not convenient for it.
    # Longitudes -24..24 and latitudes 30..78, both spanning 48 degrees at a 12-degree step,
    # so the grid's cells are ~16 degrees on each side and the worst latitude in the band is
    # 78 N. At that band the discarded bound (gap * metres-per-degree-of-longitude at 78 N)
    # claims 369 899.6 m for a 16-degree gap where the true great-circle distance is
    # 368 750.3 m — 0.3% ABOVE the distance it bounds, so it would end a ring expansion one
    # ring early and drop a real neighbour. Every query below is therefore a live test of the
    # replacement bound, not a formality.
    var gx = List[Float64]()
    var gy = List[Float64]()
    for i in range(5):
        for j in range(5):
            gx.append(Float64(i) * 12.0 - 24.0)
            gy.append(30.0 + Float64(j) * 12.0)
    var ggrid = grid_build_flat(gx, gy, 25, GEO_FRAME_LONLAT_DEG, 4)
    var deg_bad = 0
    for q in range(25):
        var gi = grid_knn_flat(
            ggrid.cell_start, ggrid.cell_items, gx, gy, 25, ggrid.side,
            ggrid.min_x, ggrid.min_y, ggrid.cell_w, ggrid.cell_h,
            gx[q], gy[q], 4, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE,
        )
        var bs = knn_scan_flat(
            gx, gy, 25, gx[q], gy[q], 4, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
        )
        if gi.status != GEO_OK or bs.status != GEO_OK:
            deg_bad += 1
            continue
        for i in range(gi.k_returned):
            if gi.ids[i] != bs.ids[i] or gi.distance_m[i] != bs.distance_m[i]:
                deg_bad += 1
    if deg_bad == 0 and ggrid.status == GEO_OK:
        passed += 1
        print("  ✅ 25 haversine 4-NN queries on the adversarial 30-78 N lattice agree exactly")
    else:
        failed += 1
        print("  ❌ the degree-frame stopping bound pruned a real neighbour:", deg_bad)

    # ── k beyond the data, k = 0, k < 0 ─────────────────────────────────────
    var big_k = knn_scan_flat(
        xs, ys, n, 0.0, 0.0, 100, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    var zero_k = grid_knn_flat(
        grid.cell_start, grid.cell_items, xs, ys, n, grid.side,
        grid.min_x, grid.min_y, grid.cell_w, grid.cell_h,
        0.0, 0.0, 0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
    )
    var neg_k = knn_scan_flat(
        xs, ys, n, 0.0, 0.0, -1, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if (
        big_k.status == GEO_OK
        and big_k.k_requested == 100
        and big_k.k_returned == 25
        and zero_k.status == GEO_OK
        and zero_k.k_returned == 0
        and not zero_k.has_max_distance
        and neg_k.status == GEO_ERR_PARAM
    ):
        passed += 1
        print("  ✅ k=100 over 25 points returns 25; k=0 returns nothing; k=-1 refuses")
    else:
        failed += 1
        print("  ❌ a k boundary is wrong:", big_k.k_returned, zero_k.status, neg_k.status)

    # ── the metric the index cannot prove exactness for ─────────────────────
    var vin = grid_knn_flat(
        grid.cell_start, grid.cell_items, gx, gy, 25, ggrid.side,
        ggrid.min_x, ggrid.min_y, ggrid.cell_w, ggrid.cell_h,
        gx[0], gy[0], 3, GEO_FRAME_LONLAT_DEG, GEO_METRIC_VINCENTY,
    )
    var wrong_unit = knn_scan_flat(
        xs, ys, n, 0.0, 0.0, 3, GEO_FRAME_PLANE_M, GEO_METRIC_HAVERSINE
    )
    if (
        vin.status == GEO_ERR_METRIC_UNSUPPORTED_HERE
        and not vin.exact
        and len(vin.ids) == 0
        and wrong_unit.status == GEO_ERR_UNIT_MISMATCH
    ):
        passed += 1
        print("  ✅ Vincenty is refused by the indexed path rather than claimed exact")
    else:
        failed += 1
        print("  ❌ an unprovable exactness claim slipped through:", vin.status)

    # But the O(n) scan, which has no bound to prove, serves it.
    var vin_scan = knn_scan_flat(
        gx, gy, 25, gx[0], gy[0], 3, GEO_FRAME_LONLAT_DEG, GEO_METRIC_VINCENTY
    )
    if vin_scan.status == GEO_OK and vin_scan.k_returned == 3 and vin_scan.exact:
        passed += 1
        print("  ✅ and knn_scan_flat serves Vincenty in O(n), where no bound is needed")
    else:
        failed += 1
        print("  ❌ the scan refused Vincenty too:", vin_scan.status)

    # ── build parameters ────────────────────────────────────────────────────
    # `target_per_cell` is bounded in BOTH directions. Zero is meaningless, and a huge value
    # would drive the side to its maximum and allocate a 2^20-entry pointer array for a
    # handful of points — the request is refused instead.
    var t0 = grid_build_flat(xs, ys, n, GEO_FRAME_PLANE_M, 0)
    var thuge = grid_build_flat(xs, ys, n, GEO_FRAME_PLANE_M, GEO_MAX_TARGET_PER_CELL + 1)
    var t1 = grid_build_flat(xs, ys, n, GEO_FRAME_PLANE_M, 1)
    if (
        t0.status == GEO_ERR_PARAM
        and thuge.status == GEO_ERR_PARAM
        and t1.status == GEO_OK
        and t1.side == 5
    ):
        passed += 1
        print("  ✅ target 0 and target > 2^20 refuse; target 1 gives side 5 for 25 points")
    else:
        failed += 1
        print("  ❌ target_per_cell is not bounded:", t0.status, thuge.status, t1.side)

    # An empty point set still builds a well-formed empty index: the pointer array exists and
    # is all zeros, `has_extent` is False because the extent of nothing does not exist.
    var no_x = List[Float64]()
    var no_y = List[Float64]()
    var empty = grid_build_flat(no_x, no_y, 0, GEO_FRAME_PLANE_M, 4)
    if (
        empty.status == GEO_OK
        and not empty.has_extent
        and len(empty.cell_items) == 0
        and len(empty.cell_start) == empty.n_cells + 1
        and empty.occupied_cells == 0
    ):
        passed += 1
        print("  ✅ an empty index is well-formed and reports no extent")
    else:
        failed += 1
        print("  ❌ the empty index is malformed:", empty.status, len(empty.cell_start))

    # ── and it must ANSWER a query, which is the sentence the assertion above starts ──
    # An empty index with k >= 1 has no neighbours. That is an answer: `GEO_OK`, zero returned,
    # `exact` true, `has_max_distance` false. Getting it wrong is not a wrong number — the ring
    # loop's stopping test `len(dists) >= k_eff` is `0 >= 0` on the first ring and the next
    # line reads `dists[-1]`, an uncatchable bounds abort that kills the worker and every
    # dataset resident in it. This suite reaching its final line is the proof it does not.
    var empty_knn = grid_knn_flat(
        empty.cell_start, empty.cell_items, no_x, no_y, 0, empty.side,
        empty.min_x, empty.min_y, empty.cell_w, empty.cell_h,
        0.0, 0.0, 1, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
    )
    var empty_scan = knn_scan_flat(
        no_x, no_y, 0, 0.0, 0.0, 1, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if (
        empty_knn.status == GEO_OK
        and empty_knn.k_requested == 1
        and empty_knn.k_returned == 0
        and empty_knn.exact
        and not empty_knn.has_max_distance
        and len(empty_knn.ids) == 0
        and empty_scan.status == GEO_OK
        and empty_scan.k_returned == 0
    ):
        passed += 1
        print("  ✅ 1-NN over an EMPTY index answers 'no neighbours' and agrees with the scan")
    else:
        failed += 1
        print(
            "  ❌ the empty-index neighbour query is wrong:", empty_knn.status,
            empty_knn.k_returned, empty_knn.exact,
        )

    # The same query at every k a caller might pass, including one far above GEO_MAX_POINTS,
    # because `k_eff = min(k, n)` collapses all of them to the same zero.
    var empty_k_bad = 0
    for kk in range(0, 5):
        var e = grid_knn_flat(
            empty.cell_start, empty.cell_items, no_x, no_y, 0, empty.side,
            empty.min_x, empty.min_y, empty.cell_w, empty.cell_h,
            1.0, -1.0, kk, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
        )
        if e.status != GEO_OK or e.k_returned != 0 or e.has_max_distance:
            empty_k_bad += 1
    var e_huge = grid_knn_flat(
        empty.cell_start, empty.cell_items, no_x, no_y, 0, empty.side,
        empty.min_x, empty.min_y, empty.cell_w, empty.cell_h,
        0.0, 0.0, 1 << 40, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
    )
    if empty_k_bad == 0 and e_huge.status == GEO_OK and e_huge.k_returned == 0:
        passed += 1
        print("  ✅ k = 0..4 and k = 2^40 over an empty index all answer 0 neighbours")
    else:
        failed += 1
        print("  ❌ an empty-index k value was mishandled:", empty_k_bad, e_huge.status)

    var over_n = grid_build_flat(xs, ys, 26, GEO_FRAME_PLANE_M, 4)
    if over_n.status == GEO_ERR_COUNT and len(over_n.cell_items) == 0:
        passed += 1
        print("  ✅ n=26 over 25 coordinates refuses with empty arrays, not a partial index")
    else:
        failed += 1
        print("  ❌ an over-count build was accepted:", over_n.status)

    print("  [geospatial.index] Passed:", passed, "Failed:", failed)
