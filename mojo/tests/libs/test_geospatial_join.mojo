"""test_geospatial_join.mojo — known-value tests for spatial joins and route matrices.

Hand-written. A join is checked the only way a join can be: against the complete answer
computed by nested loops, on data small enough that the complete answer is also countable by
hand.

The lattices are integer metre coordinates, so every distance is a Pythagorean number and no
tolerance is involved:

* Left points (0,0) and (10,0); right points (0,0) (1,0) (3,0) (10,0) (10,4).
  At radius 1 m the pairs are (0,0)-(0,0), (0,0)-(1,0) and (10,0)-(10,0) — three pairs, and
  the reader can see why: 3 m and 4 m are outside, 0 m and 1 m are inside, and a radius is
  CLOSED so exactly 1.0 m counts.
* Raising the radius to 4 m adds (0,0)-(3,0) and (10,0)-(10,4): five pairs.

The route matrix is asserted against arithmetic: a 2x3 crow-flies matrix over integer
coordinates, and a 4-node network shaped as a path 0->1->2 plus an isolated node 3, where the
0->2 travel distance is the SUM of the two legs (7.0) rather than the straight line (5.0), and
node 3 is UNREACHABLE — reported as absent, never as a large number.

The ring join is asserted on two adjacent unit squares sharing the edge x = 1, which is the
case every tiling has: a point exactly on the shared edge belongs to the lower-indexed ring
and is reported BOUNDARY, not silently promoted to interior.
"""
from std.math import abs as fabs, sqrt

from geospatial.contract import (
    GEO_ERR_ANTIMERIDIAN,
    GEO_ERR_BUDGET,
    GEO_ERR_COUNT,
    GEO_ERR_METRIC_NO_CONVERGENCE,
    GEO_ERR_OFFSETS,
    GEO_ERR_PARAM,
    GEO_ERR_UNIT_MISMATCH,
    GEO_FRAME_LATLON_DEG,
    GEO_FRAME_LONLAT_DEG,
    GEO_FRAME_PLANE_M,
    GEO_M_PER_DEG,
    GEO_METRIC_EUCLIDEAN,
    GEO_METRIC_HAVERSINE,
    GEO_METRIC_VINCENTY,
    GEO_OK,
    GEO_OK_TRUNCATED,
)
from geospatial.join import (
    GEO_MAX_PAIRS,
    join_point_in_rings_flat,
    join_within_flat,
    network_route_matrix_flat,
    route_matrix_flat,
)
from geospatial.polygon import GEO_PIP_BOUNDARY, GEO_PIP_INSIDE, GEO_PIP_OUTSIDE


def main() raises:
    var passed = 0
    var failed = 0
    print("[geospatial.join]")

    # ── the radius join, against a hand-countable answer ──────────────────────
    var lx = List[Float64]()
    var ly = List[Float64]()
    lx.append(0.0)
    ly.append(0.0)
    lx.append(10.0)
    ly.append(0.0)
    var rx = List[Float64]()
    var ry = List[Float64]()
    rx.append(0.0)
    ry.append(0.0)  # id 0, 0 m from left 0
    rx.append(1.0)
    ry.append(0.0)  # id 1, 1 m from left 0
    rx.append(3.0)
    ry.append(0.0)  # id 2, 3 m from left 0
    rx.append(10.0)
    ry.append(0.0)  # id 3, 0 m from left 1
    rx.append(10.0)
    ry.append(4.0)  # id 4, 4 m from left 1

    var j1 = join_within_flat(
        lx, ly, 2, rx, ry, 5, 1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 1000
    )
    if (
        j1.status == GEO_OK
        and not j1.truncated
        and j1.n_pairs == 3
        and j1.left_ids[0] == 0
        and j1.right_ids[0] == 0
        and j1.distance_m[0] == 0.0
        and j1.left_ids[1] == 0
        and j1.right_ids[1] == 1
        and j1.distance_m[1] == 1.0
        and j1.left_ids[2] == 1
        and j1.right_ids[2] == 3
        and j1.distance_m[2] == 0.0
    ):
        passed += 1
        print("  ✅ radius 1 m gives exactly 3 pairs, ordered by left id then right id")
    else:
        failed += 1
        print("  ❌ the radius-1 join is wrong:", j1.n_pairs, j1.status)

    # The radius is CLOSED, so a point at exactly 1.0 m is in and 3.0 m is out. Raising the
    # radius to 4.0 admits both the 3 m and the 4 m pair — five in total.
    var j4 = join_within_flat(
        lx, ly, 2, rx, ry, 5, 4.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 1000
    )
    if j4.status == GEO_OK and j4.n_pairs == 5:
        passed += 1
        print("  ✅ radius 4 m gives 5 pairs: the closed radius admits exactly 1.0 and 4.0")
    else:
        failed += 1
        print("  ❌ the radius-4 join is wrong:", j4.n_pairs)

    # A zero radius is legitimate and matches only coincident points: left 0 with right 0, and
    # left 1 with right 3.
    var j0 = join_within_flat(
        lx, ly, 2, rx, ry, 5, 0.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 1000
    )
    if j0.status == GEO_OK and j0.n_pairs == 2:
        passed += 1
        print("  ✅ a zero radius is a real request: 2 coincident pairs, nothing else")
    else:
        failed += 1
        print("  ❌ the zero-radius join is wrong:", j0.n_pairs)

    # ── a radius-0 SELF join must pair every point with itself ────────────────
    # `d = 0.0 <= 0.0`, so the answer is exactly n_pairs = n, one per point, with left id and
    # right id equal. On a 10x10 lattice at 0.1 steps this is the query that caught the index
    # dropping its own extent maximum: the x = 0.9 column and the y = 0.9 row are 19 of the
    # 100 points, they sit exactly on the extent the index reconstructed as
    # 0.8999999999999999, and their search boxes were declared "outside the grid". The join
    # returned 81 pairs under `GEO_OK` with `truncated = False` — a 19% silent loss.
    var latx = List[Float64]()
    var laty = List[Float64]()
    for i in range(100):
        latx.append(Float64(i % 10) / 10.0)
        laty.append(Float64(i // 10) / 10.0)
    var selfjoin = join_within_flat(
        latx, laty, 100, latx, laty, 100, 0.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 1 << 20
    )
    var self_ok = (
        selfjoin.status == GEO_OK
        and selfjoin.n_pairs == 100
        and not selfjoin.truncated
    )
    if self_ok:
        for i in range(100):
            if selfjoin.left_ids[i] != i or selfjoin.right_ids[i] != i:
                self_ok = False
            if selfjoin.distance_m[i] != 0.0:
                self_ok = False
    if self_ok:
        passed += 1
        print("  ✅ radius 0 self-join over a 10x10 lattice: all 100 points paired with self")
    else:
        failed += 1
        print(
            "  ❌ the radius-0 self join lost pairs:", selfjoin.n_pairs, "of 100, status",
            selfjoin.status,
        )

    # The same, swept over every lattice side from 2 to 40. Four of those 39 shapes lost pairs
    # to the reconstruction rounding and 35 did not, which is what made it invisible in
    # practice: s = 10 lost 19 of 100, s = 12 lost 23 of 144, s = 19 lost 37 of 361, s = 29
    # lost 57 of 841. A single lattice is not evidence; the sweep is.
    var lost_shapes = 0
    for s in range(2, 41):
        var gx = List[Float64]()
        var gy = List[Float64]()
        for i in range(s * s):
            gx.append(Float64(i % s) / Float64(s))
            gy.append(Float64(i // s) / Float64(s))
        var sj = join_within_flat(
            gx, gy, s * s, gx, gy, s * s, 0.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
            1 << 20,
        )
        if sj.status != GEO_OK or sj.n_pairs != s * s:
            lost_shapes += 1
    if lost_shapes == 0:
        passed += 1
        print("  ✅ radius-0 self-joins over lattices s = 2..40 are complete for all 39 shapes")
    else:
        failed += 1
        print("  ❌ lattice shapes still losing pairs:", lost_shapes, "of 39")

    # ── the CELLS a probe reads are counted, and charged ──────────────────────
    # A right side on the diagonal of a plane, and a left point whose search box sits entirely
    # off that diagonal: the box covers many cells and holds no candidate at all. Both numbers
    # are reported, and `cells_examined > 0` with `candidates_examined == 0` is the shape of
    # cost the budget used to price at zero — 636 us per left point charged as nothing, which
    # at the admitted `n_left` ceiling is about eleven minutes of invisible work.
    var diagx = List[Float64]()
    var diagy = List[Float64]()
    for i in range(4096):
        var t = Float64(i) / 4096.0
        diagx.append(t)
        diagy.append(t)
    var offdiag_l_x = List[Float64]()
    var offdiag_l_y = List[Float64]()
    offdiag_l_x.append(0.75)
    offdiag_l_y.append(0.25)
    var sparse = join_within_flat(
        offdiag_l_x, offdiag_l_y, 1, diagx, diagy, 4096, 0.2,
        GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 1 << 20,
    )
    if (
        sparse.status == GEO_OK
        and sparse.n_pairs == 0
        and sparse.candidates_examined == 0
        and sparse.cells_examined > 0
    ):
        passed += 1
        print(
            "  ✅ an off-diagonal box reads", String(sparse.cells_examined),
            "cells and 0 candidates, and both are reported",
        )
    else:
        failed += 1
        print(
            "  ❌ the cell cost of a probe is not reported:", sparse.cells_examined,
            sparse.candidates_examined,
        )

    # The reported total is the per-probe count times the number of identical probes — the
    # accounting is exact, not an estimate, so a caller can predict the charge.
    var many_l_x = List[Float64]()
    var many_l_y = List[Float64]()
    for _ in range(7):
        many_l_x.append(0.75)
        many_l_y.append(0.25)
    var sparse7 = join_within_flat(
        many_l_x, many_l_y, 7, diagx, diagy, 4096, 0.2,
        GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 1 << 20,
    )
    if (
        sparse7.status == GEO_OK
        and sparse7.cells_examined == 7 * sparse.cells_examined
        and sparse7.candidates_examined == 0
    ):
        passed += 1
        print("  ✅ seven identical probes charge exactly seven times one probe's cells")
    else:
        failed += 1
        print(
            "  ❌ the cell charge is not linear in the probes:", sparse7.cells_examined,
            "vs", 7 * sparse.cells_examined,
        )

    # And the charge is ENFORCED, not merely reported. 2^13 left points, each probing a box of
    # about 41 000 empty cells over a right side of 2^18 points on a diagonal: 3.4e8 cell reads
    # against a ceiling of 2^26. The join must stop at the ceiling with GEO_OK_TRUNCATED and
    # the flag. Charging candidates alone, this same call ran to completion under a plain
    # GEO_OK with `candidates_examined = 0` — a request whose entire cost was invisible to the
    # budget, to the report and to the declared complexity. This assertion is the reason the
    # suite spends half a second here: the ceiling is a real number and the only way to show it
    # binds is to reach it.
    var wall_r = List[Float64]()
    var wall_ry = List[Float64]()
    for i in range(1 << 18):
        var tt = Float64(i) / Float64(1 << 18)
        wall_r.append(tt * 1.0e6)
        wall_ry.append(tt * 1.0e6)
    var wall_l = List[Float64]()
    var wall_ly = List[Float64]()
    for _ in range(1 << 13):
        wall_l.append(7.5e5)
        wall_ly.append(2.5e5)
    var capped = join_within_flat(
        wall_l, wall_ly, 1 << 13, wall_r, wall_ry, 1 << 18, 2.0e5,
        GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 1 << 20,
    )
    if (
        capped.status == GEO_OK_TRUNCATED
        and capped.truncated
        and capped.candidates_examined == 0
        and capped.cells_examined > (1 << 26)
    ):
        passed += 1
        print(
            "  ✅ a cells-only workload truncates at the ceiling:",
            String(capped.cells_examined), "cells charged, 0 candidates",
        )
    else:
        failed += 1
        print(
            "  ❌ an uncharged loop ran past the ceiling:", capped.status,
            capped.cells_examined, capped.candidates_examined,
        )

    # The indexed join must equal the NESTED-LOOP join, pair for pair. That is the only
    # statement worth making about an index, and it is made over a sweep of radii.
    var mismatch = 0
    for step in range(12):
        var radius = Float64(step) * 1.0
        var got = join_within_flat(
            lx, ly, 2, rx, ry, 5, radius, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 1000
        )
        var expect = 0
        for a in range(2):
            for b in range(5):
                var ddx = rx[b] - lx[a]
                var ddy = ry[b] - ly[a]
                # `sqrt`, never `** 0.5`: in this toolchain 9.0 ** 0.5 is
                # 3.0000000000592677, so a pow-based oracle disagrees with the kernel on
                # every pair whose distance equals the radius exactly.
                if sqrt(ddx * ddx + ddy * ddy) <= radius:
                    expect += 1
        if got.status != GEO_OK or got.n_pairs != expect:
            mismatch += 1
    if mismatch == 0:
        passed += 1
        print("  ✅ 12 radii: the indexed join matches the nested-loop join every time")
    else:
        failed += 1
        print("  ❌ indexed and nested-loop joins disagree at", mismatch, "radii")

    # A bigger, denser case where the index has something to prune, still checked against the
    # complete answer: a 12x12 metre lattice joined to itself at radius 1.
    var gx = List[Float64]()
    var gy = List[Float64]()
    for i in range(12):
        for j in range(12):
            gx.append(Float64(i))
            gy.append(Float64(j))
    var big = join_within_flat(
        gx, gy, 144, gx, gy, 144, 1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 100000
    )
    # Each point pairs with itself plus its axis-aligned neighbours at exactly 1 m:
    # 144 self pairs + 2 * (11 * 12) horizontal + 2 * (11 * 12) vertical = 144 + 528 = 672.
    var expect_big = 0
    for a in range(144):
        for b in range(144):
            var ddx = gx[b] - gx[a]
            var ddy = gy[b] - gy[a]
            if sqrt(ddx * ddx + ddy * ddy) <= 1.0:
                expect_big += 1
    if big.status == GEO_OK and big.n_pairs == 672 and expect_big == 672:
        passed += 1
        print("  ✅ a 144-point self-join at radius 1 gives 672 pairs (144 self + 528 edges)")
    else:
        failed += 1
        print("  ❌ the dense self-join is wrong:", big.n_pairs, expect_big)

    # And it examined far fewer candidates than the 20736-cell cross product.
    if (
        big.full_scan_cost == 144 * 144
        and big.candidates_examined < big.full_scan_cost // 4
        and big.has_selectivity
    ):
        passed += 1
        print(
            "  ✅ candidates examined",
            String(big.candidates_examined),
            "vs a 20736-pair full scan",
        )
    else:
        failed += 1
        print("  ❌ the join examined too many candidates:", big.candidates_examined)

    # Within one left id the right ids must ASCEND — a total order, so the pair list does not
    # depend on the index's internal cell resolution.
    var ordered = True
    for i in range(1, big.n_pairs):
        if big.left_ids[i] == big.left_ids[i - 1]:
            if big.right_ids[i] <= big.right_ids[i - 1]:
                ordered = False
        elif big.left_ids[i] < big.left_ids[i - 1]:
            ordered = False
    if ordered:
        passed += 1
        print("  ✅ 672 pairs come back in a strict (left id, right id) total order")
    else:
        failed += 1
        print("  ❌ the pair order is not total")

    # ── truncation is a DIFFERENT status, never a quiet short answer ──────────
    var trunc = join_within_flat(
        gx, gy, 144, gx, gy, 144, 1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 10
    )
    if (
        trunc.status == GEO_OK_TRUNCATED
        and trunc.truncated
        and trunc.n_pairs == 10
    ):
        passed += 1
        print("  ✅ max_pairs=10 returns GEO_OK_TRUNCATED and the flag, not a plain OK")
    else:
        failed += 1
        print("  ❌ a truncated join reported success:", trunc.status, trunc.n_pairs)

    # ── the seam: refused with the offending point, never silently clipped ────
    # A left point at longitude 179.9 with a 200 km radius needs a box that wraps past 180.
    # Clipping it would drop every pair on the other side of the seam.
    var sx = List[Float64]()
    var sy = List[Float64]()
    sx.append(179.9)
    sy.append(0.0)
    var tx = List[Float64]()
    var ty = List[Float64]()
    tx.append(-179.9)
    ty.append(0.0)
    var seam = join_within_flat(
        sx, sy, 1, tx, ty, 1, 200000.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE, 1000
    )
    if seam.status == GEO_ERR_ANTIMERIDIAN and seam.seam_point == 0 and seam.n_pairs == 0:
        passed += 1
        print("  ✅ a search box crossing the seam refuses and names the left point: 0")
    else:
        failed += 1
        print("  ❌ a seam-crossing join was silently clipped:", seam.status)

    # ── join refusals ───────────────────────────────────────────────────────
    var bad_unit = join_within_flat(
        lx, ly, 2, rx, ry, 5, 1.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_EUCLIDEAN, 10
    )
    var bad_rad = join_within_flat(
        lx, ly, 2, rx, ry, 5, -1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 10
    )
    var bad_count = join_within_flat(
        lx, ly, 9, rx, ry, 5, 1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, 10
    )
    var bad_pairs = join_within_flat(
        lx, ly, 2, rx, ry, 5, 1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN, GEO_MAX_PAIRS + 1
    )
    if (
        bad_unit.status == GEO_ERR_UNIT_MISMATCH
        and bad_rad.status == GEO_ERR_PARAM
        and bad_count.status == GEO_ERR_COUNT
        and bad_pairs.status == GEO_ERR_PARAM
        and len(bad_count.left_ids) == 0
    ):
        passed += 1
        print("  ✅ mixed units, a negative radius, n=9 and max_pairs > 2^22 all refuse")
    else:
        failed += 1
        print("  ❌ a join refusal is wrong:", bad_unit.status, bad_rad.status, bad_count.status)

    # The frozen ellipsoid kernel's antipodal hole must not enter a join as "0 m apart",
    # which would make the farthest possible pair look like the closest match.
    var apx = List[Float64]()
    var apy = List[Float64]()
    apx.append(0.0)
    apy.append(0.0)
    var aqx = List[Float64]()
    var aqy = List[Float64]()
    aqx.append(180.0)
    aqy.append(0.0)
    # The radius has to be large enough that the antipode is actually a CANDIDATE: at 1 km
    # the search box is 0.009 degrees wide and the pair never reaches the metric at all. At
    # 30 000 km the box covers the whole longitude range, so the guard is the only thing
    # between the caller and a 0-metre pair.
    var anti = join_within_flat(
        apx, apy, 1, aqx, aqy, 1, 30000000.0, GEO_FRAME_LONLAT_DEG,
        GEO_METRIC_VINCENTY, 10,
    )
    if anti.status == GEO_ERR_METRIC_NO_CONVERGENCE and anti.n_pairs == 0:
        passed += 1
        print("  ✅ an antipodal Vincenty pair refuses instead of joining at 0 m")
    else:
        failed += 1
        print("  ❌ the antipodal hole entered a join:", anti.status, anti.n_pairs)

    # ── the crow-flies route matrix ─────────────────────────────────────────
    # Origins (0,0) (3,0); destinations (0,0) (0,4) (3,4). Row-major, so cell [i][j] is
    # distance from origin i to destination j. All Pythagorean: 0, 4, 5 / 3, 5, 4.
    var oxs = List[Float64]()
    var oys = List[Float64]()
    oxs.append(0.0)
    oys.append(0.0)
    oxs.append(3.0)
    oys.append(0.0)
    var dxs = List[Float64]()
    var dys = List[Float64]()
    dxs.append(0.0)
    dys.append(0.0)
    dxs.append(0.0)
    dys.append(4.0)
    dxs.append(3.0)
    dys.append(4.0)
    var mat = route_matrix_flat(
        oxs, oys, 2, dxs, dys, 3, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if (
        mat.status == GEO_OK
        and mat.n_cells == 6
        and len(mat.distance_m) == 6
        and mat.distance_m[0] == 0.0
        and mat.distance_m[1] == 4.0
        and mat.distance_m[2] == 5.0
        and mat.distance_m[3] == 3.0
        and mat.distance_m[4] == 5.0
        and mat.distance_m[5] == 4.0
        and mat.has_extremes
        and mat.min_distance_m == 0.0
        and mat.max_distance_m == 5.0
        and not mat.network
        and mat.n_unreachable == 0
    ):
        passed += 1
        print("  ✅ the 2x3 crow-flies matrix is 0,4,5 / 3,5,4 with extremes 0 and 5")
    else:
        failed += 1
        print("  ❌ the crow-flies matrix is wrong:", mat.distance_m[1], mat.distance_m[3])

    # Every crow-flies pair is reachable by definition, and the flag says so uniformly.
    var all_reach = len(mat.reachable) == 6
    for i in range(len(mat.reachable)):
        if not mat.reachable[i]:
            all_reach = False
    if all_reach:
        passed += 1
        print("  ✅ every crow-flies cell is marked reachable")
    else:
        failed += 1
        print("  ❌ a crow-flies cell was marked unreachable")

    # An empty matrix has no extremes: has_extremes False rather than a min of 0.0, which a
    # caller would read as "something is zero metres away".
    var no_o = List[Float64]()
    var empty_mat = route_matrix_flat(
        no_o, no_o, 0, dxs, dys, 3, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if (
        empty_mat.status == GEO_OK
        and empty_mat.n_cells == 0
        and not empty_mat.has_extremes
        and empty_mat.min_distance_m == 0.0
    ):
        passed += 1
        print("  ✅ a 0x3 matrix has no extremes, not a minimum of zero")
    else:
        failed += 1
        print("  ❌ an empty matrix claimed extremes")

    # ── the network travel matrix ───────────────────────────────────────────
    # Nodes: 0 (0,0), 1 (3,0), 2 (3,4), 3 (100,100). Edges 0->1 (3 m) and 1->2 (4 m).
    # Travel 0->2 is 7 m, the SUM of the legs, not the 5 m straight line. Node 3 has no edge,
    # so it is unreachable and must be reported ABSENT rather than as a large number.
    var nxs = List[Float64]()
    var nys = List[Float64]()
    nxs.append(0.0)
    nys.append(0.0)
    nxs.append(3.0)
    nys.append(0.0)
    nxs.append(3.0)
    nys.append(4.0)
    nxs.append(100.0)
    nys.append(100.0)
    var esrc = List[Int]()
    var edst = List[Int]()
    esrc.append(0)
    edst.append(1)
    esrc.append(1)
    edst.append(2)
    var origins = List[Int]()
    origins.append(0)
    var dests = List[Int]()
    dests.append(1)
    dests.append(2)
    dests.append(3)
    var net = network_route_matrix_flat(
        nxs, nys, 4, esrc, edst, 2, origins, 1, dests, 3,
        GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
    )
    if (
        net.status == GEO_OK
        and net.network
        and net.n_cells == 3
        and net.reachable[0]
        and net.distance_m[0] == 3.0
        and net.reachable[1]
        and net.distance_m[1] == 7.0
        and not net.reachable[2]
        and net.distance_m[2] == 0.0
        and net.n_unreachable == 1
    ):
        passed += 1
        print("  ✅ network 0->2 is 7 m (the two legs), not the 5 m straight line")
    else:
        failed += 1
        print("  ❌ the travel matrix is wrong:", net.distance_m[0], net.distance_m[1])

    # The unreachable cell is 0.0 with reachable False — never 1e18, which a caller cannot
    # tell from a real distance and will happily add to a budget.
    if net.distance_m[2] == 0.0 and not net.reachable[2] and net.max_distance_m == 7.0:
        passed += 1
        print("  ✅ the unreachable pair is absent (0.0 + False), and excluded from the max")
    else:
        failed += 1
        print("  ❌ an unreachable pair leaked into the extremes:", net.max_distance_m)

    # Edges are DIRECTED: 2->0 does not exist, so the reverse query is unreachable.
    var back_o = List[Int]()
    back_o.append(2)
    var back_d = List[Int]()
    back_d.append(0)
    var back = network_route_matrix_flat(
        nxs, nys, 4, esrc, edst, 2, back_o, 1, back_d, 1,
        GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
    )
    if back.status == GEO_OK and not back.reachable[0] and back.n_unreachable == 1:
        passed += 1
        print("  ✅ the edge list is directed: 2 -> 0 is unreachable")
    else:
        failed += 1
        print("  ❌ a directed edge was traversed backwards")

    # An origin or destination index outside [0, n_nodes) is REFUSED, not clamped: a clamped
    # origin produces a whole row of plausible distances from a node nobody asked about.
    var bad_o = List[Int]()
    bad_o.append(9)
    var bad_net = network_route_matrix_flat(
        nxs, nys, 4, esrc, edst, 2, bad_o, 1, dests, 3,
        GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
    )
    var neg_o = List[Int]()
    neg_o.append(-1)
    var neg_net = network_route_matrix_flat(
        nxs, nys, 4, esrc, edst, 2, neg_o, 1, dests, 3,
        GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
    )
    var over_edges = network_route_matrix_flat(
        nxs, nys, 4, esrc, edst, 99, origins, 1, dests, 3,
        GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
    )
    if (
        bad_net.status == GEO_ERR_PARAM
        and neg_net.status == GEO_ERR_PARAM
        and over_edges.status == GEO_ERR_COUNT
        and len(bad_net.distance_m) == 0
    ):
        passed += 1
        print("  ✅ node index 9 and -1 refuse; n_edges=99 over a 2-edge list refuses")
    else:
        failed += 1
        print("  ❌ a bad node index was clamped:", bad_net.status, neg_net.status)

    # ── the point-in-rings join ─────────────────────────────────────────────
    # Two unit squares sharing the edge x = 1: ring 0 is [0,1]x[0,1], ring 1 is [1,2]x[0,1].
    var ring_x = List[Float64]()
    var ring_y = List[Float64]()
    ring_x.append(0.0)
    ring_y.append(0.0)
    ring_x.append(1.0)
    ring_y.append(0.0)
    ring_x.append(1.0)
    ring_y.append(1.0)
    ring_x.append(0.0)
    ring_y.append(1.0)
    ring_x.append(1.0)
    ring_y.append(0.0)
    ring_x.append(2.0)
    ring_y.append(0.0)
    ring_x.append(2.0)
    ring_y.append(1.0)
    ring_x.append(1.0)
    ring_y.append(1.0)
    var offs = List[Int]()
    offs.append(0)
    offs.append(4)
    offs.append(8)

    var qx = List[Float64]()
    var qy = List[Float64]()
    qx.append(0.5)
    qy.append(0.5)  # inside ring 0
    qx.append(1.5)
    qy.append(0.5)  # inside ring 1
    qx.append(1.0)
    qy.append(0.5)  # exactly on the SHARED edge
    qx.append(5.0)
    qy.append(5.0)  # in neither
    var rj = join_point_in_rings_flat(
        qx, qy, 4, ring_x, ring_y, offs, 2, GEO_FRAME_PLANE_M
    )
    if (
        rj.status == GEO_OK
        and rj.n_matched == 3
        and rj.ring_of_point[0] == 0
        and rj.code_of_point[0] == GEO_PIP_INSIDE
        and rj.ring_of_point[1] == 1
        and rj.code_of_point[1] == GEO_PIP_INSIDE
        and rj.ring_of_point[3] == -1
        and rj.code_of_point[3] == GEO_PIP_OUTSIDE
        and rj.rings_refused == 0
    ):
        passed += 1
        print("  ✅ two adjacent squares: each interior point lands in its own ring, one in none")
    else:
        failed += 1
        print("  ❌ the ring join is wrong:", rj.ring_of_point[0], rj.ring_of_point[1])

    # The shared-edge point: BOTH rings claim it, the LOWER index wins deterministically, and
    # it is reported BOUNDARY rather than promoted to interior. `n_multi` makes the overlap
    # visible instead of resolving it silently.
    if (
        rj.ring_of_point[2] == 0
        and rj.code_of_point[2] == GEO_PIP_BOUNDARY
        and rj.n_boundary == 1
        and rj.n_multi == 1
    ):
        passed += 1
        print("  ✅ a point on the shared edge goes to ring 0 as BOUNDARY, and n_multi is 1")
    else:
        failed += 1
        print("  ❌ the shared-edge tiebreak is wrong:", rj.ring_of_point[2], rj.n_multi)

    # A broken ring is SKIPPED and counted, not allowed to fail the whole join: ring 1 here
    # has only two vertices. `rings_refused` is what says something was dropped.
    var bad_offs = List[Int]()
    bad_offs.append(0)
    bad_offs.append(4)
    bad_offs.append(6)
    var partial = join_point_in_rings_flat(
        qx, qy, 4, ring_x, ring_y, bad_offs, 2, GEO_FRAME_PLANE_M
    )
    if (
        partial.status == GEO_OK
        and partial.rings_refused == 1
        and partial.ring_of_point[0] == 0
        and partial.ring_of_point[1] == -1
    ):
        passed += 1
        print("  ✅ a 2-vertex ring is skipped and counted; the other ring still answers")
    else:
        failed += 1
        print("  ❌ a broken ring was not isolated:", partial.rings_refused)

    # A malformed offsets array is the CSR abort, and it is refused before any read.
    var short_offs = List[Int]()
    short_offs.append(0)
    short_offs.append(4)
    var past_end = List[Int]()
    past_end.append(0)
    past_end.append(4)
    past_end.append(99)
    if (
        join_point_in_rings_flat(
            qx, qy, 4, ring_x, ring_y, short_offs, 2, GEO_FRAME_PLANE_M
        ).status
        == GEO_ERR_OFFSETS
        and join_point_in_rings_flat(
            qx, qy, 4, ring_x, ring_y, past_end, 2, GEO_FRAME_PLANE_M
        ).status
        == GEO_ERR_OFFSETS
    ):
        passed += 1
        print("  ✅ a short offsets array and a tail past the vertices both refuse")
    else:
        failed += 1
        print("  ❌ a malformed offsets array was accepted")

    # Zero rings and zero points are ANSWERS: every point matches nothing, and `ring_of_point`
    # is -1 everywhere rather than 0, which would name ring 0.
    var no_ring_offs = List[Int]()
    no_ring_offs.append(0)
    var no_rings = join_point_in_rings_flat(
        qx, qy, 4, ring_x, ring_y, no_ring_offs, 0, GEO_FRAME_PLANE_M
    )
    if (
        no_rings.status == GEO_OK
        and no_rings.n_matched == 0
        and len(no_rings.ring_of_point) == 4
        and no_rings.ring_of_point[0] == -1
    ):
        passed += 1
        print("  ✅ zero rings: every point is -1 (no ring), never 0 (ring zero)")
    else:
        failed += 1
        print("  ❌ an empty multipolygon named ring 0")

    print("  [geospatial.join] Passed:", passed, "Failed:", failed)
