"""test_geospatial_frame.mojo — known-value tests for frame-checked distance and projection.

Hand-written. The distances asserted here are CLOSED FORMS on the sphere of radius
6 371 000 m that a reader can evaluate without running anything, which is the only kind of
distance assertion that is independent of the kernel producing it:

  | pair                              | closed form   | metres              |
  | --------------------------------- | ------------- | ------------------- |
  | (0N, 0E) -> (0N, 1E)              | R * pi / 180  | 111 194.92664455873 |
  | (0N, 0E) -> (90N, 0E)             | R * pi / 2    | 10 007 543.398010286 |
  | (0N, 0E) -> (0N, 180E)            | R * pi        | 20 015 086.79602057 |
  | (45N, 0E) -> (45S, 0E)            | R * pi / 2    | 10 007 543.398010286 |

The first is also `contract.GEO_M_PER_DEG`, and the fact that both come out of the same
number is the point: a degree of latitude anywhere and a degree of longitude at the equator
are the same arc.

For the WGS84 ellipsoid, one degree along the equator is `a * pi / 180` with
a = 6 378 137 m, i.e. 111 319.49079327358 m — the published "111.32 km per degree of
longitude at the equator". Vincenty is iterative, so the assertion allows 1e-4 relative.

One reference value is not a closed form and is named as such: London Heathrow
(51.4700 N, 0.4543 W) to New York JFK (40.6413 N, 73.7781 W) is 5 540 011.32 m by the
spherical law of haversines with R = 6371 km, evaluated in CPython.

The suite also pins the failure this module exists to make impossible — a degree operand
combined with a metre operand — and the one the FROZEN ellipsoid kernel has:
`geodesy.vincenty_distance` returns 0.0 km for two exactly ANTIPODAL points, because it tests
sin(sigma) against 1e-12 and sin(pi) is 0. That kernel is frozen and is not touched; this
module detects the case and reports absence instead of 0 metres.
"""
from std.math import abs as fabs

from geospatial.contract import (
    GEO_ERR_FRAME,
    GEO_ERR_FRAME_MISMATCH,
    GEO_ERR_METRIC_NO_CONVERGENCE,
    GEO_ERR_PARAM,
    GEO_ERR_RANGE,
    GEO_ERR_UNIT_MISMATCH,
    GEO_FRAME_LATLON_DEG,
    GEO_FRAME_LONLAT_DEG,
    GEO_FRAME_PLANE_M,
    GEO_M_PER_DEG,
    GEO_METRIC_EUCLIDEAN,
    GEO_METRIC_HAVERSINE,
    GEO_METRIC_VINCENTY,
    GEO_OK,
)
from geospatial.frame import (
    frame_census_flat,
    frame_distance_flat,
    frame_metric_distance,
    frame_metric_undefined,
    frame_pair_defect,
    frame_path_length_flat,
    frame_project_flat,
    frame_ring_census_flat,
)

#: R * pi / 2 for R = 6 371 000 m — a quarter of the way round the sphere.
comptime REF_QUARTER_M: Float64 = 10007543.398010286
#: R * pi — half way round.
comptime REF_HALF_M: Float64 = 20015086.79602057
#: WGS84 semi-major axis * pi / 180: one degree along the equator on the ellipsoid.
comptime REF_WGS84_DEG_M: Float64 = 111319.49079327358
#: LHR -> JFK by the haversine formula with R = 6371 km, evaluated in CPython.
comptime REF_LHR_JFK_M: Float64 = 5540011.317976542


fn _pair(x0: Float64, y0: Float64, x1: Float64, y1: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(x0)
    out.append(y0)
    out.append(x1)
    out.append(y1)
    return out^


fn main() raises:
    var passed = 0
    var failed = 0
    print("[geospatial.frame]")

    # ── closed-form great-circle distances, in metres ──────────────────────────
    # LONLAT order: x = longitude, y = latitude. One degree of longitude at the equator.
    var d_eq = frame_metric_distance(
        0.0, 0.0, 1.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    if fabs(d_eq - GEO_M_PER_DEG) < 1.0e-6:
        passed += 1
        print("  ✅ 1 degree along the equator is R*pi/180 = 111194.92664455873 m")
    else:
        failed += 1
        print("  ❌ equatorial degree wrong:", d_eq)

    var d_pole = frame_metric_distance(
        0.0, 0.0, 0.0, 90.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    var d_anti = frame_metric_distance(
        0.0, 0.0, 180.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    var d_45 = frame_metric_distance(
        0.0, 45.0, 0.0, -45.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    if (
        fabs(d_pole - REF_QUARTER_M) < 1.0e-3
        and fabs(d_anti - REF_HALF_M) < 1.0e-3
        and fabs(d_45 - REF_QUARTER_M) < 1.0e-3
    ):
        passed += 1
        print("  ✅ equator->pole and 45N->45S are both R*pi/2; antipodal is R*pi")
    else:
        failed += 1
        print("  ❌ a quarter/half circumference is wrong:", d_pole, d_anti, d_45)

    # The SAME two places in the other declared axis order must give the SAME distance.
    # This is the swap that produces a plausible wrong answer when the order is assumed.
    var lonlat = frame_metric_distance(
        -0.4543, 51.47, -73.7781, 40.6413, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    var latlon = frame_metric_distance(
        51.47, -0.4543, 40.6413, -73.7781, GEO_FRAME_LATLON_DEG, GEO_METRIC_HAVERSINE
    )
    if (
        fabs(lonlat - REF_LHR_JFK_M) < 1.0
        and lonlat == latlon
    ):
        passed += 1
        print("  ✅ LHR->JFK is 5540011.32 m, bit-identical in both axis orders")
    else:
        failed += 1
        print("  ❌ the axis order changed the distance:", lonlat, latlon)

    # WGS84: one degree along the equator is a*pi/180 = 111319.49 m, the published 111.32 km.
    var d_wgs = frame_metric_distance(
        0.0, 0.0, 1.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_VINCENTY
    )
    if fabs(d_wgs - REF_WGS84_DEG_M) < REF_WGS84_DEG_M * 1.0e-4 and d_wgs > d_eq:
        passed += 1
        print("  ✅ WGS84 equatorial degree is 111319.49 m, larger than the sphere's")
    else:
        failed += 1
        print("  ❌ Vincenty equatorial degree wrong:", d_wgs)

    # A 3-4-5 triangle in the projected plane: the frozen geometry.distance_2d, exactly.
    var d_plane = frame_metric_distance(
        0.0, 0.0, 3.0, 4.0, GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN
    )
    if d_plane == 5.0:
        passed += 1
        print("  ✅ (0,0)->(3,4) in the metre plane is exactly 5.0 m")
    else:
        failed += 1
        print("  ❌ planar distance wrong:", d_plane)

    # ── the mixed pair, refused by SIGNATURE ──────────────────────────────────
    var mixed = frame_distance_flat(
        0.0, 0.0, GEO_FRAME_LONLAT_DEG, 500000.0, 4649776.0, GEO_FRAME_PLANE_M,
        GEO_METRIC_HAVERSINE,
    )
    if mixed.status == GEO_ERR_FRAME_MISMATCH and not mixed.has_distance:
        passed += 1
        print("  ✅ a longitude and an easting refuse to combine into a number")
    else:
        failed += 1
        print("  ❌ a mixed-frame pair produced a distance:", mixed.status)

    # `has_distance = False` and the slot is a representable 0.0 — never a raw non-finite,
    # and never to be read as "zero metres apart".
    if mixed.distance_m == 0.0:
        passed += 1
        print("  ✅ the refused distance slot is a representable 0.0, and the flag is False")
    else:
        failed += 1
        print("  ❌ a refusal left something in the distance slot:", mixed.distance_m)

    var unit = frame_distance_flat(
        0.0, 0.0, GEO_FRAME_LONLAT_DEG, 1.0, 1.0, GEO_FRAME_LONLAT_DEG,
        GEO_METRIC_EUCLIDEAN,
    )
    var bad_frame = frame_distance_flat(0.0, 0.0, 9, 1.0, 1.0, 9, GEO_METRIC_HAVERSINE)
    var out_of_range = frame_distance_flat(
        0.0, 95.0, GEO_FRAME_LONLAT_DEG, 1.0, 1.0, GEO_FRAME_LONLAT_DEG,
        GEO_METRIC_HAVERSINE,
    )
    if (
        unit.status == GEO_ERR_UNIT_MISMATCH
        and bad_frame.status == GEO_ERR_FRAME
        and out_of_range.status == GEO_ERR_RANGE
        and frame_pair_defect(GEO_FRAME_LONLAT_DEG, GEO_FRAME_LONLAT_DEG) == GEO_OK
        and frame_pair_defect(GEO_FRAME_LONLAT_DEG, GEO_FRAME_LATLON_DEG)
        == GEO_ERR_FRAME_MISMATCH
        and frame_pair_defect(9, 9) == GEO_ERR_FRAME
    ):
        passed += 1
        print("  ✅ euclidean-on-degrees, an unknown frame and a 95 latitude each refuse")
    else:
        failed += 1
        print("  ❌ a refusal path is wrong:", unit.status, bad_frame.status)

    # ── the frozen ellipsoid kernel's antipodal hole, reported not propagated ──
    # geodesy.vincenty_distance((0,0),(0,180)) returns 0.0 km: sin(sigma) < 1e-12 is read as
    # "coincident", but sin(pi) is 0 too. 0 metres between antipodes inside a radius join
    # would make the farthest possible pair the closest match there is.
    var anti_vin = frame_distance_flat(
        0.0, 0.0, GEO_FRAME_LONLAT_DEG, 180.0, 0.0, GEO_FRAME_LONLAT_DEG,
        GEO_METRIC_VINCENTY,
    )
    if (
        anti_vin.status == GEO_ERR_METRIC_NO_CONVERGENCE
        and not anti_vin.has_distance
        and anti_vin.distance_m == 0.0
    ):
        passed += 1
        print("  ✅ antipodal Vincenty is reported ABSENT, not as 0 metres apart")
    else:
        failed += 1
        print("  ❌ the antipodal Vincenty hole leaked:", anti_vin.status, anti_vin.distance_m)

    # And a genuinely coincident pair still answers 0.0 with has_distance True: the detector
    # separates "could not measure" from "measured zero" using the frozen haversine as oracle.
    var same_vin = frame_distance_flat(
        12.5, -7.25, GEO_FRAME_LONLAT_DEG, 12.5, -7.25, GEO_FRAME_LONLAT_DEG,
        GEO_METRIC_VINCENTY,
    )
    if (
        same_vin.status == GEO_OK
        and same_vin.has_distance
        and same_vin.distance_m == 0.0
        and not frame_metric_undefined(
            0.0, 12.5, -7.25, 12.5, -7.25, GEO_FRAME_LONLAT_DEG, GEO_METRIC_VINCENTY
        )
        and frame_metric_undefined(
            0.0, 0.0, 0.0, 180.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_VINCENTY
        )
        and not frame_metric_undefined(
            0.0, 0.0, 0.0, 180.0, 0.0, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
        )
    ):
        passed += 1
        print("  ✅ a coincident pair is still a measured 0.0 m; only antipodes are absent")
    else:
        failed += 1
        print("  ❌ the degeneracy detector confuses coincident with antipodal")

    # ── the frozen kernel's OTHER exit: 100 iterations, then the SPHERE ────────
    # `vincenty_distance` ends `return haversine_distance(...)` when the iteration does not
    # converge, which for a near-antipodal pair hands back the SPHERICAL distance wearing the
    # ellipsoidal metric's name — the exact substitution code 723's rationale refuses to make.
    # It is detected the same way the zero exit is: the frozen haversine is the oracle, and the
    # fallback returns it bit-for-bit, so the equality needs no tolerance. (0N,0E)-(0.4N,179.7E)
    # is such a pair; the two kernels agree to the last bit, which two different formulas do
    # not do by chance.
    var near_anti = frame_distance_flat(
        0.0, 0.0, GEO_FRAME_LONLAT_DEG, 179.7, 0.4, GEO_FRAME_LONLAT_DEG,
        GEO_METRIC_VINCENTY,
    )
    var same_pair_hav = frame_distance_flat(
        0.0, 0.0, GEO_FRAME_LONLAT_DEG, 179.7, 0.4, GEO_FRAME_LONLAT_DEG,
        GEO_METRIC_HAVERSINE,
    )
    if (
        near_anti.status == GEO_ERR_METRIC_NO_CONVERGENCE
        and not near_anti.has_distance
        and near_anti.distance_m == 0.0
        and same_pair_hav.status == GEO_OK
        and same_pair_hav.distance_m > 1.9e7
        and frame_metric_undefined(
            same_pair_hav.distance_m, 0.0, 0.0, 179.7, 0.4, GEO_FRAME_LONLAT_DEG,
            GEO_METRIC_VINCENTY,
        )
    ):
        passed += 1
        print("  ✅ a near-antipodal Vincenty pair is ABSENT, not the spherical value relabelled")
    else:
        failed += 1
        print(
            "  ❌ the non-convergence fallback shipped as Vincenty:", near_anti.status,
            near_anti.distance_m,
        )

    # The haversine metric itself is never "undefined" by this test, even though its own value
    # trivially equals the oracle: the detector answers only for Vincenty, so the spherical
    # metric is not accused of substituting for itself.
    var hav_same = frame_distance_flat(
        0.0, 0.0, GEO_FRAME_LONLAT_DEG, 179.7, 0.4, GEO_FRAME_LONLAT_DEG,
        GEO_METRIC_HAVERSINE,
    )
    if (
        hav_same.status == GEO_OK
        and hav_same.has_distance
        and not frame_metric_undefined(
            hav_same.distance_m, 0.0, 0.0, 179.7, 0.4, GEO_FRAME_LONLAT_DEG,
            GEO_METRIC_HAVERSINE,
        )
    ):
        passed += 1
        print("  ✅ the haversine metric is not accused of substituting for itself")
    else:
        failed += 1
        print("  ❌ the detector fired on the haversine metric:", hav_same.status)

    # A converged, ordinary Vincenty pair is unaffected: London to New York differs from the
    # spherical value by about 0.1%, so it is not equal to the oracle and is not refused.
    var london_ny = frame_distance_flat(
        -0.1278, 51.5074, GEO_FRAME_LONLAT_DEG, -74.006, 40.7128, GEO_FRAME_LONLAT_DEG,
        GEO_METRIC_VINCENTY,
    )
    var london_ny_hav = frame_distance_flat(
        -0.1278, 51.5074, GEO_FRAME_LONLAT_DEG, -74.006, 40.7128, GEO_FRAME_LONLAT_DEG,
        GEO_METRIC_HAVERSINE,
    )
    if (
        london_ny.status == GEO_OK
        and london_ny.has_distance
        and london_ny.distance_m != london_ny_hav.distance_m
        and fabs(london_ny.distance_m - 5570000.0) < 30000.0
    ):
        passed += 1
        print("  ✅ a converged Vincenty pair (London-New York) still answers, ~5570 km")
    else:
        failed += 1
        print("  ❌ the substitution detector refused a converged pair:", london_ny.status)

    # ── census of an unordered batch ──────────────────────────────────────────
    var xs = List[Float64]()
    var ys = List[Float64]()
    # A 1x1 degree box with its corners at (0,0) and (1,1), in LONLAT order.
    xs.append(0.0)
    ys.append(0.0)
    xs.append(1.0)
    ys.append(0.0)
    xs.append(1.0)
    ys.append(1.0)
    xs.append(0.0)
    ys.append(1.0)
    var cen = frame_census_flat(xs, ys, 4, GEO_FRAME_LONLAT_DEG)
    if (
        cen.status == GEO_OK
        and cen.has_extent
        and cen.min_x == 0.0
        and cen.max_x == 1.0
        and cen.min_y == 0.0
        and cen.max_y == 1.0
        and cen.lon_span_deg == 1.0
        and cen.lat_span_deg == 1.0
        and not cen.extent_spans_antimeridian
        and not cen.touches_pole
    ):
        passed += 1
        print("  ✅ the unit degree box: extent 0..1 on both axes, spans 1 degree each")
    else:
        failed += 1
        print("  ❌ census extent wrong:", cen.min_x, cen.max_x, cen.lon_span_deg)

    # Every |x| and |y| <= 90 here, so the batch reads IDENTICALLY as lon/lat and lat/lon and
    # no validator can tell which was meant. That is reported, not guessed.
    if cen.order_ambiguous:
        passed += 1
        print("  ✅ a batch inside +-90 on both axes is reported order_ambiguous")
    else:
        failed += 1
        print("  ❌ an undetectable axis swap was not reported")

    # Push one longitude past 90 and the ambiguity is gone — the data can only be lon/lat.
    var xs2 = xs.copy()
    var ys2 = ys.copy()
    xs2.append(139.6503)
    ys2.append(35.6762)
    var cen2 = frame_census_flat(xs2, ys2, 5, GEO_FRAME_LONLAT_DEG)
    if cen2.status == GEO_OK and not cen2.order_ambiguous:
        passed += 1
        print("  ✅ adding Tokyo's 139.65 longitude resolves the ambiguity")
    else:
        failed += 1
        print("  ❌ ambiguity not resolved by an out-of-latitude-range longitude")

    # An EMPTY batch has no extent. `has_extent` False with status OK: the bounding box of
    # nothing does not exist, and zeros there would read as a box at the origin.
    var none_x = List[Float64]()
    var none_y = List[Float64]()
    var cen0 = frame_census_flat(none_x, none_y, 0, GEO_FRAME_LONLAT_DEG)
    if cen0.status == GEO_OK and not cen0.has_extent and cen0.min_x == 0.0:
        passed += 1
        print("  ✅ an empty batch: status OK, has_extent False, no phantom box at 0,0")
    else:
        failed += 1
        print("  ❌ an empty batch reported an extent")

    # A projected batch has no angular span and no metre-per-degree scale.
    var px = List[Float64]()
    var py = List[Float64]()
    px.append(500000.0)
    py.append(4649776.0)
    px.append(500100.0)
    py.append(4649876.0)
    var cenp = frame_census_flat(px, py, 2, GEO_FRAME_PLANE_M)
    if (
        cenp.status == GEO_OK
        and cenp.has_extent
        and not cenp.has_span
        and not cenp.has_metre_scale
        and cenp.lon_span_deg == 0.0
    ):
        passed += 1
        print("  ✅ a projected batch reports no angular span and no degree scale")
    else:
        failed += 1
        print("  ❌ a projected batch claimed an angular span")

    # ── the ring census: seam, winding, poles ─────────────────────────────────
    # A box straddling the antimeridian: (179,0) (-179,0) (-179,1) (179,1). Two of its four
    # edges have a RAW longitude difference of 358 degrees, so two seam edges.
    var sx = List[Float64]()
    var sy = List[Float64]()
    sx.append(179.0)
    sy.append(0.0)
    sx.append(-179.0)
    sy.append(0.0)
    sx.append(-179.0)
    sy.append(1.0)
    sx.append(179.0)
    sy.append(1.0)
    var seam = frame_ring_census_flat(sx, sy, 4, GEO_FRAME_LONLAT_DEG)
    if (
        seam.status == GEO_OK
        and seam.antimeridian_edges == 2
        and seam.has_winding
        and fabs(seam.lon_winding_deg) < 1.0e-9
        and not seam.encircles_pole
        and seam.n_edges == 4
    ):
        passed += 1
        print("  ✅ a seam-straddling box: 2 antimeridian edges, winding 0, no pole")
    else:
        failed += 1
        print("  ❌ seam census wrong:", seam.antimeridian_edges, seam.lon_winding_deg)

    # A ring around the north pole at 80 N: longitudes 0, 90, 180, -90, each a +90 step by
    # the shortest-path rule, so the winding is exactly +360 and the pole is enclosed.
    var wx = List[Float64]()
    var wy = List[Float64]()
    wx.append(0.0)
    wy.append(80.0)
    wx.append(90.0)
    wy.append(80.0)
    wx.append(180.0)
    wy.append(80.0)
    wx.append(-90.0)
    wy.append(80.0)
    var pole = frame_ring_census_flat(wx, wy, 4, GEO_FRAME_LONLAT_DEG)
    if (
        pole.status == GEO_OK
        and pole.has_winding
        and fabs(pole.lon_winding_deg - 360.0) < 1.0e-9
        and pole.encircles_pole
        and not pole.touches_pole
    ):
        passed += 1
        print("  ✅ a 4-vertex ring at 80 N winds +360 and is flagged pole-encircling")
    else:
        failed += 1
        print("  ❌ pole winding wrong:", pole.lon_winding_deg, pole.encircles_pole)

    # A vertex AT the pole is reported (`touches_pole`) and not refused: the ring is still a
    # planar ring, it is the metre SCALE that degenerates there.
    var tx = List[Float64]()
    var ty = List[Float64]()
    tx.append(0.0)
    ty.append(90.0)
    tx.append(10.0)
    ty.append(80.0)
    tx.append(-10.0)
    ty.append(80.0)
    var touch = frame_ring_census_flat(tx, ty, 3, GEO_FRAME_LONLAT_DEG)
    if touch.status == GEO_OK and touch.touches_pole and not touch.encircles_pole:
        passed += 1
        print("  ✅ a vertex exactly at 90 N is reported, not refused")
    else:
        failed += 1
        print("  ❌ touches_pole wrong:", touch.touches_pole, touch.encircles_pole)

    # An explicitly closed ring repeats its first vertex. The extra edge is zero-length and
    # inert: same winding, same seam count.
    var cx = sx.copy()
    var cy = sy.copy()
    cx.append(179.0)
    cy.append(0.0)
    var closed = frame_ring_census_flat(cx, cy, 5, GEO_FRAME_LONLAT_DEG)
    if (
        closed.explicitly_closed
        and closed.antimeridian_edges == seam.antimeridian_edges
        and fabs(closed.lon_winding_deg - seam.lon_winding_deg) < 1.0e-9
    ):
        passed += 1
        print("  ✅ repeating the first vertex changes nothing but explicitly_closed")
    else:
        failed += 1
        print("  ❌ the closing vertex changed the census")

    # ── path length: one point is zero SEGMENTS, not zero metres ──────────────
    var one_x = List[Float64]()
    var one_y = List[Float64]()
    one_x.append(0.0)
    one_y.append(0.0)
    var p1 = frame_path_length_flat(
        one_x, one_y, 1, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    if (
        p1.status == GEO_OK
        and p1.n_segments == 0
        and not p1.has_length
        and p1.length_m == 0.0
        and not p1.has_extremes
    ):
        passed += 1
        print("  ✅ a one-fix track has NO length, distinct from a zero-metre journey")
    else:
        failed += 1
        print("  ❌ a one-point path claimed a length:", p1.has_length, p1.length_m)

    # Three points along the equator at 0, 1, 3 degrees: 1 + 2 degrees of arc.
    var tr_x = List[Float64]()
    var tr_y = List[Float64]()
    tr_x.append(0.0)
    tr_y.append(0.0)
    tr_x.append(1.0)
    tr_y.append(0.0)
    tr_x.append(3.0)
    tr_y.append(0.0)
    var p3 = frame_path_length_flat(
        tr_x, tr_y, 3, GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE
    )
    if (
        p3.status == GEO_OK
        and p3.n_segments == 2
        and p3.has_length
        and fabs(p3.length_m - 3.0 * GEO_M_PER_DEG) < 1.0e-3
        and fabs(p3.min_segment_m - GEO_M_PER_DEG) < 1.0e-6
        and fabs(p3.max_segment_m - 2.0 * GEO_M_PER_DEG) < 1.0e-6
    ):
        passed += 1
        print("  ✅ 0->1->3 degrees along the equator is 3 * 111194.9266 m, 2 segments")
    else:
        failed += 1
        print("  ❌ path length wrong:", p3.length_m, p3.min_segment_m)

    # ── projection to a local metre plane ─────────────────────────────────────
    # About (0.5, 0.5): x_m = R * (lon - 0.5) in radians * cos(0.5 deg),
    #                   y_m = R * (lat - 0.5) in radians.
    # Half a degree of latitude is 55597.46332227937 m, and half a degree of longitude at
    # 0.5 N is 55595.34634123621 m. Both are R*pi/360 (times cos for the longitude).
    var proj = frame_project_flat(xs, ys, 4, GEO_FRAME_LONLAT_DEG, 0.5, 0.5)
    if (
        proj.status == GEO_OK
        and proj.has_result
        and len(proj.xs_m) == 4
        and fabs(proj.xs_m[0] + 55595.34634123621) < 1.0e-6
        and fabs(proj.ys_m[0] + 55597.46332227937) < 1.0e-6
        and fabs(proj.xs_m[2] - 55595.34634123621) < 1.0e-6
        and fabs(proj.ys_m[2] - 55597.46332227937) < 1.0e-6
        and proj.lon_span_deg == 1.0
        and proj.lat_span_deg == 1.0
    ):
        passed += 1
        print("  ✅ the 1-degree box projects to +-55595.35 m east, +-55597.46 m north")
    else:
        failed += 1
        print("  ❌ projection wrong:", proj.xs_m[0], proj.ys_m[0])

    # A degree of LATITUDE is not distorted by the reference parallel; a degree of LONGITUDE
    # is. The projection says so, and the caller is handed the span to bound the error.
    var y_span_m = proj.ys_m[2] - proj.ys_m[0]
    var x_span_m = proj.xs_m[2] - proj.xs_m[0]
    if fabs(y_span_m - GEO_M_PER_DEG) < 1.0e-6 and x_span_m < y_span_m:
        passed += 1
        print("  ✅ north-south scale is exact; east-west is shortened by cos(0.5 deg)")
    else:
        failed += 1
        print("  ❌ the projection's distortion is not as documented:", x_span_m, y_span_m)

    # "Project the projected" is refused rather than guessed at, and a reference point
    # outside +-90/+-180 is a parameter error. Both return EMPTY arrays, never zeros.
    var reproj = frame_project_flat(px, py, 2, GEO_FRAME_PLANE_M, 0.0, 0.0)
    var badref = frame_project_flat(xs, ys, 4, GEO_FRAME_LONLAT_DEG, 91.0, 0.0)
    if (
        reproj.status == GEO_ERR_FRAME
        and len(reproj.xs_m) == 0
        and badref.status == GEO_ERR_PARAM
        and len(badref.xs_m) == 0
        and not badref.has_result
    ):
        passed += 1
        print("  ✅ projecting a projected frame and a 91-degree reference both refuse")
    else:
        failed += 1
        print("  ❌ a projection refusal is wrong:", reproj.status, badref.status)

    print("  [geospatial.frame] Passed:", passed, "Failed:", failed)
