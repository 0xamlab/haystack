"""test_geospatial_mapmatch.mojo — known-value tests for point-to-segment and map matching.

Hand-written. The one thing a map matcher must get right, and the thing the frozen kernels
cannot do on their own, is the CLAMP: `geodesy.cross_track_distance` measures the distance to
the great CIRCLE through a leg's endpoints, which is an infinite line. Used unclamped it
reports a vehicle 20 km past the end of a street as 3 m from it.

So the assertions are built on segments whose clamped and unclamped answers DIFFER by a large,
hand-computable amount:

* In the metre plane, the segment (0,0) -> (10,0) and the query (20, 3). The perpendicular
  distance to the infinite line is 3. The distance to the SEGMENT is the distance to the
  endpoint (10,0), which is sqrt(100 + 9) = 10.44030650891055. The suite asserts 10.44, so a
  regression to the unclamped 3.0 fails loudly.
* On the sphere, the leg (0N, 0E) -> (0N, 1E) with the query at (0N, 5E). The cross-track
  distance is 0 — the query is ON the great circle, the equator — while the true distance to
  the segment is 4 degrees of arc, 444 779.7065782349 m (4 * R * pi / 180, R = 6 371 000 m).
  An unclamped matcher would report the fix as lying exactly on this road.

Interior cases are checked against closed forms too: for (5, 3) against (0,0) -> (10,0) the
foot is (5,0), `t` is 0.5 and the distance is exactly 3.0.

The matching itself is asserted on a network where the right answer is not arguable: two
parallel roads 1 km apart, and a track that runs along one of them. Every fix must match the
near road. Then the same track with `beta` raised, on a network where the nearest segment per
fix flips mid-track, to show continuity doing its job.
"""
from std.math import abs as fabs, sqrt

from geospatial.contract import (
    GEO_ERR_BUDGET,
    GEO_ERR_COUNT,
    GEO_ERR_METRIC_UNSUPPORTED_HERE,
    GEO_ERR_NO_CANDIDATE,
    GEO_ERR_OFFSETS,
    GEO_ERR_PARAM,
    GEO_ERR_RANGE,
    GEO_ERR_UNIT_MISMATCH,
    GEO_FRAME_LONLAT_DEG,
    GEO_FRAME_PLANE_M,
    GEO_M_PER_DEG,
    GEO_METRIC_EUCLIDEAN,
    GEO_METRIC_HAVERSINE,
    GEO_METRIC_VINCENTY,
    GEO_OK,
)
from geospatial.frame import frame_distance_flat
from geospatial.mapmatch import (
    GEO_FOOT_END,
    GEO_FOOT_INTERIOR,
    GEO_FOOT_START,
    GEO_MAX_SEGMENTS,
    map_match_flat,
    point_to_segment_flat,
)

#: sqrt(100 + 9) — the distance from (20, 3) to the endpoint (10, 0).
comptime REF_PAST_END_M: Float64 = 10.44030650891055
#: 4 * R * pi / 180 for R = 6 371 000 m: four degrees of arc along the equator.
comptime REF_FOUR_DEG_M: Float64 = 444779.7065782349


def main() raises:
    var passed = 0
    var failed = 0
    print("[geospatial.mapmatch]")

    # ── the clamp, in the plane ───────────────────────────────────────────────
    # (20,3) against (0,0)->(10,0): the perpendicular to the infinite LINE is 3.0; the
    # distance to the SEGMENT is to its endpoint, sqrt(109) = 10.4403065089.
    var past = point_to_segment_flat(
        20.0, 3.0, 0.0, 0.0, 10.0, 0.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if (
        past.status == GEO_OK
        and past.has_distance
        and fabs(past.distance_m - REF_PAST_END_M) < 1.0e-12
        and past.where == GEO_FOOT_END
        and past.foot_x == 10.0
        and past.foot_y == 0.0
        and past.t_fraction == 1.0
        and past.has_leg_length
        and past.leg_length_m == 10.0
    ):
        passed += 1
        print("  ✅ (20,3) past the end of (0,0)->(10,0) is 10.4403 m, not the 3.0 m to the line")
    else:
        failed += 1
        print("  ❌ the clamp failed:", past.distance_m, past.where)

    # Before the start is the mirror case.
    var before = point_to_segment_flat(
        -20.0, 3.0, 0.0, 0.0, 10.0, 0.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if (
        before.status == GEO_OK
        and fabs(before.distance_m - sqrt(409.0)) < 1.0e-12
        and before.where == GEO_FOOT_START
        and before.foot_x == 0.0
        and before.t_fraction == 0.0
    ):
        passed += 1
        print("  ✅ (-20,3) before the start is sqrt(409) m with the foot at (0,0)")
    else:
        failed += 1
        print("  ❌ the start clamp failed:", before.distance_m, before.where)

    # An INTERIOR foot: (5,3) is 3.0 from the segment, foot (5,0), t = 0.5 exactly.
    var interior = point_to_segment_flat(
        5.0, 3.0, 0.0, 0.0, 10.0, 0.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if (
        interior.status == GEO_OK
        and interior.distance_m == 3.0
        and interior.where == GEO_FOOT_INTERIOR
        and interior.foot_x == 5.0
        and interior.foot_y == 0.0
        and interior.has_fraction
        and interior.t_fraction == 0.5
    ):
        passed += 1
        print("  ✅ (5,3) is exactly 3.0 m from the segment, foot (5,0), t = 0.5")
    else:
        failed += 1
        print("  ❌ the interior case is wrong:", interior.distance_m, interior.t_fraction)

    # A point exactly ON the segment is 0.0 with an interior foot at itself.
    var on_seg = point_to_segment_flat(
        4.0, 0.0, 0.0, 0.0, 10.0, 0.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if (
        on_seg.status == GEO_OK
        and on_seg.distance_m == 0.0
        and on_seg.where == GEO_FOOT_INTERIOR
        and on_seg.foot_x == 4.0
        and on_seg.t_fraction == 0.4
    ):
        passed += 1
        print("  ✅ a point on the segment is 0.0 m away with t = 0.4")
    else:
        failed += 1
        print("  ❌ an on-segment point is wrong:", on_seg.distance_m, on_seg.t_fraction)

    # A DEGENERATE leg (a == b) has no direction, so there is no fraction of it. The distance
    # is point-to-point and `has_fraction` is False — absence, not a fabricated 0.0 or 0.5.
    var degen = point_to_segment_flat(
        3.0, 4.0, 0.0, 0.0, 0.0, 0.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if (
        degen.status == GEO_OK
        and degen.distance_m == 5.0
        and not degen.has_fraction
        and degen.t_fraction == 0.0
        and degen.where == GEO_FOOT_START
        and degen.leg_length_m == 0.0
    ):
        passed += 1
        print("  ✅ a zero-length leg: 5.0 m away, and NO fraction rather than a made-up one")
    else:
        failed += 1
        print("  ❌ the degenerate leg is wrong:", degen.distance_m, degen.has_fraction)

    # ── the clamp, on the sphere, where the unclamped answer is ZERO ─────────
    # Leg (0N,0E)->(0N,1E) along the equator, query (0N,5E). The query lies exactly ON the
    # great circle through the leg, so cross_track_distance is 0 — an unclamped matcher
    # reports the fix as on this road. The true distance to the SEGMENT is 4 degrees of arc.
    var sphere_past = point_to_segment_flat(
        5.0, 0.0, 0.0, 0.0, 1.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    if (
        sphere_past.status == GEO_OK
        and fabs(sphere_past.distance_m - REF_FOUR_DEG_M) < 1.0
        and sphere_past.where == GEO_FOOT_END
        and sphere_past.foot_x == 1.0
        and sphere_past.foot_y == 0.0
    ):
        passed += 1
        print("  ✅ 4 degrees past a 1-degree leg is 444779.7 m, not the 0 m to the circle")
    else:
        failed += 1
        print("  ❌ the spherical clamp failed:", sphere_past.distance_m, sphere_past.where)

    # An interior foot on the sphere: (0.5N, 0.5E) against the equatorial leg
    # (0N,0E)->(0N,1E). Half a degree of latitude north of the equator: 55597.46332227937 m.
    var sphere_in = point_to_segment_flat(
        0.5, 0.5, 0.0, 0.0, 1.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    if (
        sphere_in.status == GEO_OK
        and sphere_in.where == GEO_FOOT_INTERIOR
        and fabs(sphere_in.distance_m - GEO_M_PER_DEG * 0.5) < 1.0
        and fabs(sphere_in.t_fraction - 0.5) < 1.0e-3
    ):
        passed += 1
        print("  ✅ half a degree off the middle of the leg is 55597.5 m, t about 0.5")
    else:
        failed += 1
        print("  ❌ the spherical interior case is wrong:", sphere_in.distance_m, sphere_in.t_fraction)

    # ── LONG legs, where the clamp used to INVERT ─────────────────────────────
    # A leg of a quarter of the globe or more is where a length-based inside test dies. The
    # frozen `along_track_distance` ends in `asin`, so an along-track angle of 150 degrees
    # comes back as 30; for a point past the end of a leg of length L the two folded numbers
    # sum to `180 - L`, and `along_a + along_b <= leg` degenerates into `180 - L <= L`, which
    # is TRUE for every L >= 90 no matter how far past the end the point is. The bisected
    # threshold was exactly a quarter circle: a leg of 89.99999999999993 degrees was right and
    # 89.99999999999994 degrees was wrong.
    #
    # Every expected value below is `degrees * GEO_M_PER_DEG` — the metres in one degree of
    # arc on the same 6371 km sphere the frozen haversine uses — so a reader can multiply.
    var leg100 = point_to_segment_flat(
        150.0, 0.0, 0.0, 0.0, 100.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    if (
        leg100.status == GEO_OK
        and fabs(leg100.distance_m - 50.0 * GEO_M_PER_DEG) < 1.0e-6
        and leg100.where == GEO_FOOT_END
        and leg100.foot_x == 100.0
        and leg100.foot_y == 0.0
        and leg100.t_fraction == 1.0
    ):
        passed += 1
        print("  ✅ 50 degrees past a 100-degree leg is 5559746.3 m at the END, not 0.0 m")
    else:
        failed += 1
        print(
            "  ❌ the clamp inverted on a 100-degree leg:", leg100.distance_m, leg100.where,
            leg100.foot_x,
        )

    # The same failure at three more shapes, including one just past the quarter-circle
    # threshold, and the two directions (past the end, before the start).
    var leg95 = point_to_segment_flat(
        105.0, 0.0, 0.0, 0.0, 95.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    var leg120_past = point_to_segment_flat(
        160.0, 0.0, 0.0, 0.0, 120.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    var leg120_before = point_to_segment_flat(
        -40.0, 0.0, 0.0, 0.0, 120.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    var threshold = point_to_segment_flat(
        90.99999999999994, 0.0, 0.0, 0.0, 89.99999999999994, 0.0,
        GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE,
    )
    if (
        fabs(leg95.distance_m - 10.0 * GEO_M_PER_DEG) < 1.0e-6
        and leg95.where == GEO_FOOT_END
        and fabs(leg120_past.distance_m - 40.0 * GEO_M_PER_DEG) < 1.0e-6
        and leg120_past.where == GEO_FOOT_END
        and fabs(leg120_before.distance_m - 40.0 * GEO_M_PER_DEG) < 1.0e-6
        and leg120_before.where == GEO_FOOT_START
        and leg120_before.foot_x == 0.0
        and fabs(threshold.distance_m - 1.0 * GEO_M_PER_DEG) < 1.0e-6
        and threshold.where == GEO_FOOT_END
    ):
        passed += 1
        print("  ✅ legs of 95, 120 and 89.99999999999994 degrees clamp at both ends")
    else:
        failed += 1
        print(
            "  ❌ a long leg is still unclamped:", leg95.distance_m,
            leg120_past.distance_m, leg120_before.distance_m, threshold.distance_m,
        )

    # Off-axis, so the cross-track distance to the infinite circle is non-zero and PLAUSIBLE:
    # the query is 40 degrees past the end and one degree north, and the wrong answer was
    # 111194.9 m — one degree, the cross-track distance — instead of 4448953.3 m. The expected
    # value is the frozen point-to-point distance to the endpoint, so the oracle is a different
    # kernel and not this function.
    var off_axis = point_to_segment_flat(
        160.0, 1.0, 0.0, 0.0, 120.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    var to_endpoint = frame_distance_flat(
        160.0, 1.0, GEO_FRAME_LONLAT_DEG, 120.0, 0.0, GEO_FRAME_LONLAT_DEG,
        GEO_METRIC_HAVERSINE,
    )
    if (
        off_axis.status == GEO_OK
        and to_endpoint.status == GEO_OK
        and off_axis.distance_m == to_endpoint.distance_m
        and off_axis.where == GEO_FOOT_END
        and off_axis.distance_m > 4.4e6
    ):
        passed += 1
        print(
            "  ✅ 40 degrees past and 1 north is", String(off_axis.distance_m),
            "m — the frozen distance to the endpoint",
        )
    else:
        failed += 1
        print(
            "  ❌ the off-axis long leg reported the cross-track distance:",
            off_axis.distance_m, "vs", to_endpoint.distance_m,
        )

    # An INTERIOR point more than a quarter circle from `a`: the distance was already right
    # (the cross-track kernel does not fold) but the FOOT and the leg fraction were not,
    # because the along-track distance came back folded. On a 150-degree equatorial leg the
    # point at longitude 100 is on the leg, so the foot is itself and t is 100/150.
    var deep = point_to_segment_flat(
        100.0, 0.0, 0.0, 0.0, 150.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    if (
        deep.status == GEO_OK
        and deep.where == GEO_FOOT_INTERIOR
        and deep.distance_m < 1.0e-6
        and fabs(deep.foot_x - 100.0) < 1.0e-9
        and fabs(deep.t_fraction - 100.0 / 150.0) < 1.0e-12
    ):
        passed += 1
        print("  ✅ an interior foot 100 degrees along a 150-degree leg reports t = 0.667")
    else:
        failed += 1
        print(
            "  ❌ the along-track fold reached the reported foot:", deep.foot_x,
            deep.t_fraction,
        )

    # An exactly ANTIPODAL leg lies on infinitely many great circles, so it names no arc and
    # is refused. The test is an exact equality, so a leg one ulp short of antipodal is served.
    var antipodal = point_to_segment_flat(
        10.0, 10.0, 0.0, 0.0, 180.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    var nearly = point_to_segment_flat(
        10.0, 10.0, 0.0, 0.0, 179.999, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    if (
        antipodal.status == GEO_ERR_PARAM
        and not antipodal.has_distance
        and antipodal.distance_m == 0.0
        and nearly.status == GEO_OK
        and nearly.has_distance
    ):
        passed += 1
        print("  ✅ an antipodal leg refuses; 179.999 degrees still answers")
    else:
        failed += 1
        print("  ❌ the antipodal leg was answered:", antipodal.status, nearly.status)

    # The axis order must not change the answer: the same geometry in LATLON.
    var sphere_swapped = point_to_segment_flat(
        0.0, 5.0, 0.0, 0.0, 0.0, 1.0, 1, GEO_METRIC_HAVERSINE
    )
    if (
        sphere_swapped.status == GEO_OK
        and fabs(sphere_swapped.distance_m - sphere_past.distance_m) < 1.0e-9
        and sphere_swapped.foot_y == 1.0
        and sphere_swapped.foot_x == 0.0
    ):
        passed += 1
        print("  ✅ the same leg in latlon order gives the same distance and a swapped foot")
    else:
        failed += 1
        print("  ❌ the axis order changed the segment distance:", sphere_swapped.distance_m)

    # ── segment refusals ────────────────────────────────────────────────────
    # Vincenty is refused: the clamp is built from SPHERICAL along-track distances, so mixing
    # an ellipsoidal leg length into the inside test would compare two different models.
    var vin = point_to_segment_flat(
        5.0, 0.0, 0.0, 0.0, 1.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_VINCENTY
    )
    var wrong_unit = point_to_segment_flat(
        5.0, 0.0, 0.0, 0.0, 1.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_EUCLIDEAN
    )
    var bad_pt = point_to_segment_flat(
        0.0, 95.0, 0.0, 0.0, 1.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    if (
        vin.status == GEO_ERR_METRIC_UNSUPPORTED_HERE
        and not vin.has_distance
        and vin.distance_m == 0.0
        and wrong_unit.status == GEO_ERR_UNIT_MISMATCH
        and bad_pt.status == GEO_ERR_RANGE
    ):
        passed += 1
        print("  ✅ Vincenty, euclidean-on-degrees and a latitude of 95 each refuse")
    else:
        failed += 1
        print("  ❌ a segment refusal is wrong:", vin.status, wrong_unit.status, bad_pt.status)

    # ── map matching: two parallel roads, and the track is on one of them ────
    # Road 0 (line 0) runs along y = 0 from x = 0 to x = 300. Road 1 runs along y = 1000.
    # Segments come from the CSR-style offsets: line 0 is vertices 0..3, line 1 is 4..7.
    var nx = List[Float64]()
    var ny = List[Float64]()
    for i in range(4):
        nx.append(Float64(i) * 100.0)
        ny.append(0.0)
    for i in range(4):
        nx.append(Float64(i) * 100.0)
        ny.append(1000.0)
    var lo = List[Int]()
    lo.append(0)
    lo.append(4)
    lo.append(8)

    # A track running along road 0, 5 m off it.
    var tx = List[Float64]()
    var ty = List[Float64]()
    for i in range(6):
        tx.append(Float64(i) * 50.0)
        ty.append(5.0)
    var m = map_match_flat(
        tx, ty, 6, nx, ny, lo, 2, 200.0, 1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    var all_near = m.status == GEO_OK and m.n_track == 6 and m.n_segments == 6
    if all_near:
        for t in range(6):
            if m.line_of_point[t] != 0:
                all_near = False
            if fabs(m.offset_m[t] - 5.0) > 1.0e-9:
                all_near = False
            if fabs(m.matched_ys[t]) > 1.0e-9:
                all_near = False
    if all_near and m.has_offsets and fabs(m.max_offset_m - 5.0) < 1.0e-9:
        passed += 1
        print("  ✅ 6 fixes 5 m off road 0 all match road 0, each with a 5.0 m offset")
    else:
        failed += 1
        print("  ❌ the match went to the wrong road:", m.status, m.line_of_point[0], m.offset_m[0])

    # The matched positions are the FEET on the road, so they lie on y = 0 at the fix's own x.
    var feet_ok = m.status == GEO_OK
    if feet_ok:
        for t in range(6):
            if fabs(m.matched_xs[t] - tx[t]) > 1.0e-9:
                feet_ok = False
    if feet_ok:
        passed += 1
        print("  ✅ every matched position is the perpendicular foot at the fix's own x")
    else:
        failed += 1
        print("  ❌ a matched position is not the foot:", m.matched_xs[0], tx[0])

    # The two polylines contribute 3 segments each: 6 in total, and the segment indices are
    # global while `line_of_point` maps back to the polyline.
    if m.n_segments == 6 and m.segment_of_point[0] >= 0 and m.segment_of_point[0] < 3:
        passed += 1
        print("  ✅ 2 polylines of 4 vertices give 6 segments; segment 0..2 belong to line 0")
    else:
        failed += 1
        print("  ❌ the segment/line mapping is wrong:", m.n_segments, m.segment_of_point[0])

    # ── beta: continuity against per-fix accuracy ───────────────────────────
    # Two roads 20 m apart (y = 0 and y = 20) and a track along the first one at y = 1, with
    # one fix at y = 11 — 9 m from road 1 and 11 m from road 0, so the NEAREST road for that
    # fix alone is the far one. The arithmetic, entirely by hand:
    #
    #   staying on road 0: emissions 1+1+11+1+1 = 15, feet 50 m apart throughout, fix steps
    #                      50, 50.990, 50.990, 50  =>  transition sum |50-50|*2 + 0.990*2 = 1.980
    #   taking road 1:     emissions 1+1+9+1+1  = 13, the middle foot jumps 20 m sideways so
    #                      its two foot steps are 53.852  =>  transition sum 2.862*2 = 5.724
    #
    # so beta = 0 buys the 2 m of emission and takes road 1, while beta = 5 pays
    # 15 + 9.90 = 24.90 to stay on road 0 rather than 13 + 28.62 = 41.62 to leave it.
    # That is the lever doing exactly what the docstring says, in numbers a reader can check.
    var px = List[Float64]()
    var py = List[Float64]()
    for i in range(4):
        px.append(Float64(i) * 100.0)
        py.append(0.0)
    for i in range(4):
        px.append(Float64(i) * 100.0)
        py.append(20.0)
    var ox = List[Float64]()
    var oy = List[Float64]()
    for i in range(5):
        ox.append(Float64(i) * 50.0)
        oy.append(1.0)
    oy[2] = 11.0
    var loose = map_match_flat(
        ox, oy, 5, px, py, lo, 2, 200.0, 0.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    var tight = map_match_flat(
        ox, oy, 5, px, py, lo, 2, 200.0, 5.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if (
        loose.status == GEO_OK
        and tight.status == GEO_OK
        and loose.line_of_point[2] == 1
        and tight.line_of_point[2] == 0
    ):
        passed += 1
        print("  ✅ beta=0 takes the nearer road for the odd fix; beta=5 keeps the path together")
    else:
        failed += 1
        print("  ❌ beta had no effect:", loose.line_of_point[2], tight.line_of_point[2])

    # The DP work is reported, and with 2 candidates per fix over 5 fixes it is a countable
    # number rather than an estimate.
    if tight.dp_transitions > 0 and tight.candidates_examined > 0:
        passed += 1
        print(
            "  ✅ the DP reports its own cost:",
            String(tight.dp_transitions),
            "transitions,",
            String(tight.candidates_examined),
            "candidates",
        )
    else:
        failed += 1
        print("  ❌ the DP cost was not reported")

    # ── a gap is a refusal, naming the fix ─────────────────────────────────
    # A track fix 5000 m from every road, with a 100 m search radius. Matching the fixes that
    # DID have candidates and leaving a hole would return a path the vehicle did not take.
    var gx = List[Float64]()
    var gy = List[Float64]()
    gx.append(0.0)
    gy.append(5.0)
    gx.append(50.0)
    gy.append(5000.0)
    gx.append(100.0)
    gy.append(5.0)
    var gap = map_match_flat(
        gx, gy, 3, nx, ny, lo, 2, 100.0, 1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if (
        gap.status == GEO_ERR_NO_CANDIDATE
        and gap.first_unmatched == 1
        and len(gap.segment_of_point) == 0
        and not gap.has_cost
    ):
        passed += 1
        print("  ✅ a fix with no road within 100 m refuses and names fix 1, with empty lists")
    else:
        failed += 1
        print("  ❌ a gap produced a partial match:", gap.status, gap.first_unmatched)

    # ── the long-leg clamp, reached through the DRIVER ────────────────────────
    # One road leg (0,0) -> (120,0) on the equator and one fix at (160,1), which is 4 448 953 m
    # — 4449 km — past the end of it. With a 200 km search radius the only correct answer is
    # "no candidate". The unclamped-on-long-legs version matched it to the road with a 111 km
    # offset inside a 200 km radius: a track snapped to a road it is four thousand kilometres
    # from, under a status of OK. This is the same defect as the `point_to_segment_flat` cases
    # above, asserted where a caller actually meets it.
    var lroad_x = List[Float64]()
    var lroad_y = List[Float64]()
    lroad_x.append(0.0)
    lroad_y.append(0.0)
    lroad_x.append(120.0)
    lroad_y.append(0.0)
    var lroad_off = List[Int]()
    lroad_off.append(0)
    lroad_off.append(2)
    var far_x = List[Float64]()
    var far_y = List[Float64]()
    far_x.append(160.0)
    far_y.append(1.0)
    var far = map_match_flat(
        far_x, far_y, 1, lroad_x, lroad_y, lroad_off, 1, 200000.0, 1.0,
        GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE,
    )
    if (
        far.status == GEO_ERR_NO_CANDIDATE
        and far.first_unmatched == 0
        and len(far.segment_of_point) == 0
        and not far.has_offsets
    ):
        passed += 1
        print("  ✅ a fix 4449 km past the end of a 120-degree road matches NOTHING")
    else:
        failed += 1
        print(
            "  ❌ the driver snapped a distant fix to a long road:", far.status,
            far.first_unmatched,
        )

    # A fix ON that long road still matches it, so the refusal above is the clamp and not a
    # blanket refusal of long legs.
    var near_x = List[Float64]()
    var near_y = List[Float64]()
    near_x.append(60.0)
    near_y.append(0.5)
    var near = map_match_flat(
        near_x, near_y, 1, lroad_x, lroad_y, lroad_off, 1, 200000.0, 1.0,
        GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE,
    )
    if (
        near.status == GEO_OK
        and near.segment_of_point[0] == 0
        and fabs(near.offset_m[0] - 0.5 * GEO_M_PER_DEG) < 1.0
        and near.cells_examined >= 1
    ):
        passed += 1
        print("  ✅ a fix half a degree off the same road matches it, offset 55597 m")
    else:
        failed += 1
        print("  ❌ the long road stopped matching real fixes:", near.status, near.offset_m[0])

    # The CELLS a candidate probe reads are reported, beside the candidates. The search box is
    # widened by the network's longest half-segment, so over a sparse network it is nearly all
    # cells — and a budget counting candidates alone priced that at zero.
    if near.cells_examined > 0 and near.candidates_examined >= 0:
        passed += 1
        print(
            "  ✅ the matcher reports", String(near.cells_examined), "index cells beside",
            String(near.candidates_examined), "candidates",
        )
    else:
        failed += 1
        print("  ❌ the matcher does not report its cell cost:", near.cells_examined)

    # ── match refusals ────────────────────────────────────────────────────
    var zero_r = map_match_flat(
        tx, ty, 6, nx, ny, lo, 2, 0.0, 1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    var neg_beta = map_match_flat(
        tx, ty, 6, nx, ny, lo, 2, 200.0, -1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    var over_track = map_match_flat(
        tx, ty, 99, nx, ny, lo, 2, 200.0, 1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    var bad_vin = map_match_flat(
        tx, ty, 6, nx, ny, lo, 2, 200.0, 1.0, GEO_FRAME_PLANE_M, GEO_METRIC_VINCENTY
    )
    if (
        zero_r.status == GEO_ERR_PARAM
        and neg_beta.status == GEO_ERR_PARAM
        and over_track.status == GEO_ERR_COUNT
        and bad_vin.status != GEO_OK
    ):
        passed += 1
        print("  ✅ radius 0, beta -1, n_track=99 and Vincenty all refuse")
    else:
        failed += 1
        print("  ❌ a match refusal is wrong:", zero_r.status, neg_beta.status, over_track.status)

    var short_lo = List[Int]()
    short_lo.append(0)
    short_lo.append(4)
    var bad_off = map_match_flat(
        tx, ty, 6, nx, ny, short_lo, 2, 200.0, 1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if bad_off.status == GEO_ERR_OFFSETS and len(bad_off.matched_xs) == 0:
        passed += 1
        print("  ✅ a short line_offsets array refuses before any vertex is read")
    else:
        failed += 1
        print("  ❌ a malformed offsets array was accepted:", bad_off.status)

    # A network with no SEGMENT at all — every polyline is a single-vertex stub — cannot match
    # anything, and says so with the no-candidate status rather than an empty success.
    var stub_x = List[Float64]()
    var stub_y = List[Float64]()
    stub_x.append(0.0)
    stub_y.append(0.0)
    stub_x.append(1.0)
    stub_y.append(1.0)
    var stub_lo = List[Int]()
    stub_lo.append(0)
    stub_lo.append(1)
    stub_lo.append(2)
    var stub = map_match_flat(
        tx, ty, 6, stub_x, stub_y, stub_lo, 2, 200.0, 1.0,
        GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN,
    )
    if stub.status == GEO_ERR_NO_CANDIDATE and stub.n_segments == 0:
        passed += 1
        print("  ✅ a network of single-vertex stubs has no segments and refuses")
    else:
        failed += 1
        print("  ❌ a segment-free network was matched:", stub.status)

    # An EMPTY track over a real network is a valid answer with no matches, not a refusal.
    var no_t = List[Float64]()
    var empty_track = map_match_flat(
        no_t, no_t, 0, nx, ny, lo, 2, 200.0, 1.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if (
        empty_track.status == GEO_OK
        and empty_track.n_segments == 6
        and not empty_track.has_cost
        and len(empty_track.segment_of_point) == 0
    ):
        passed += 1
        print("  ✅ an empty track answers OK with 6 segments found and no cost")
    else:
        failed += 1
        print("  ❌ an empty track was refused:", empty_track.status)

    if GEO_MAX_SEGMENTS == (1 << 20):
        passed += 1
        print("  ✅ the segment ceiling is 2^20, declared separately from the line ceiling")
    else:
        failed += 1
        print("  ❌ GEO_MAX_SEGMENTS is not 2^20:", GEO_MAX_SEGMENTS)

    print("  [geospatial.mapmatch] Passed:", passed, "Failed:", failed)
