"""test_geospatial_contract.mojo — known-value tests for the geospatial status/frame contract.

Hand-written. Every number asserted here is either a closed form a reader can evaluate by
hand or a value derived independently in CPython from the same textbook formula, and each is
named where it is used. Nothing is compared against another geospatial kernel.

The four things this suite exists to prove:

1. *The code vocabulary is injective in both directions.* 700-729 is this package's range and
   one integer must name one defect. Two files in one package once claimed the same code
   independently, so the mapping code -> name and name -> code are both checked for
   collisions, and every code is checked to be inside the declared range.

2. *A swapped latitude/longitude is refused where it is detectable and REPORTED where it is
   not.* `geo_pair_range_defect` is per-SLOT, so a longitude of 174.7 sitting in a latitude
   slot is a refusal and not a wrapped angle.

3. *`geo_cells_fit` bounds a product without forming it.* `3 * 6148914691236517206 == 2` in
   wrapping 64-bit arithmetic, so the multiply-then-compare form admits a request 3e18 times
   over the ceiling. The exact wrapping triple is asserted.

4. *`geo_gap_lower_m` really is a LOWER bound, in the case where the obvious version is not.*
   Two points at latitude 60 separated by 48 degrees of longitude are 2 609 522.27 m apart
   (sigma = 2*asin(cos 60 * sin 24) = 0.40959382679238704 rad, times R = 6 371 000 m —
   evaluated in CPython, and hand-checkable from the haversine identity). The bound this
   package used first, `48 * 111194.92664455873 * cos(60) = 2 668 678.24 m`, is LARGER than
   the distance it claims to bound — which would end a k-nearest ring expansion early and
   silently drop a closer neighbour. Both numbers are asserted: the naive one is above the
   true distance, and the shipped one is below it.
"""
from std.math import abs as fabs

from geospatial.contract import (
    GEO_BOUND_SLACK,
    GEO_EARTH_RADIUS_M,
    GEO_ERR_ANTIMERIDIAN,
    GEO_ERR_BUDGET,
    GEO_ERR_COUNT,
    GEO_ERR_DEGENERATE_RING,
    GEO_ERR_EMPTY,
    GEO_ERR_FRAME,
    GEO_ERR_FRAME_MISMATCH,
    GEO_ERR_LAYOUT,
    GEO_ERR_METRIC,
    GEO_ERR_METRIC_NO_CONVERGENCE,
    GEO_ERR_METRIC_UNSUPPORTED_HERE,
    GEO_ERR_NON_FINITE,
    GEO_ERR_NOT_CONVEX,
    GEO_ERR_NO_CANDIDATE,
    GEO_ERR_OFFSETS,
    GEO_ERR_PARAM,
    GEO_ERR_POLE,
    GEO_ERR_RANGE,
    GEO_ERR_SELF_INTERSECTING,
    GEO_ERR_TOO_LARGE,
    GEO_ERR_UNIT_MISMATCH,
    GEO_ERR_WINDOW,
    GEO_FRAME_LATLON_DEG,
    GEO_FRAME_LONLAT_DEG,
    GEO_FRAME_PLANE_M,
    GEO_M_PER_DEG,
    GEO_MAX_POINTS,
    GEO_METRIC_EUCLIDEAN,
    GEO_METRIC_HAVERSINE,
    GEO_METRIC_VINCENTY,
    GEO_OK,
    GEO_OK_TRUNCATED,
    geo_cells_fit,
    geo_degree_box_half,
    geo_finite,
    geo_finite_or_zero,
    geo_frame_defect,
    geo_frame_name,
    geo_gap_lower_m,
    geo_lat_of,
    geo_lon_delta,
    geo_lon_of,
    geo_m_per_deg_lon_lower,
    geo_metric_defect,
    geo_metric_name,
    geo_normalise_lon,
    geo_offsets_defect,
    geo_pair_range_defect,
    geo_points_defect,
    geo_status_name,
)

#: The great-circle distance in metres between (60N, 0E) and (60N, 48E) on the sphere of
#: radius 6 371 000 m: 2 * asin(cos(60 deg) * sin(24 deg)) * R. Evaluated in CPython from the
#: haversine identity, NOT from any kernel in this tree.
comptime REF_LAT60_DLON48_M: Float64 = 2609522.2704942976

#: The bound the first version of `index.grid_knn_flat` used for the same gap:
#: 48 degrees * 111194.92664455873 m/deg * cos(60 deg). Larger than the distance above, which
#: is why it was not a bound.
comptime REF_NAIVE_BOUND_M: Float64 = 2668678.23946941


fn _codes() -> List[Int]:
    """Every status code this package mints, in declaration order."""
    var c = List[Int]()
    c.append(GEO_OK)
    c.append(GEO_OK_TRUNCATED)
    c.append(GEO_ERR_COUNT)
    c.append(GEO_ERR_TOO_LARGE)
    c.append(GEO_ERR_NON_FINITE)
    c.append(GEO_ERR_FRAME)
    c.append(GEO_ERR_FRAME_MISMATCH)
    c.append(GEO_ERR_METRIC)
    c.append(GEO_ERR_UNIT_MISMATCH)
    c.append(GEO_ERR_RANGE)
    c.append(GEO_ERR_PARAM)
    c.append(GEO_ERR_EMPTY)
    c.append(GEO_ERR_ANTIMERIDIAN)
    c.append(GEO_ERR_POLE)
    c.append(GEO_ERR_DEGENERATE_RING)
    c.append(GEO_ERR_SELF_INTERSECTING)
    c.append(GEO_ERR_NOT_CONVEX)
    c.append(GEO_ERR_LAYOUT)
    c.append(GEO_ERR_WINDOW)
    c.append(GEO_ERR_BUDGET)
    c.append(GEO_ERR_NO_CANDIDATE)
    c.append(GEO_ERR_OFFSETS)
    c.append(GEO_ERR_METRIC_UNSUPPORTED_HERE)
    c.append(GEO_ERR_METRIC_NO_CONVERGENCE)
    return c^


fn main() raises:
    var passed = 0
    var failed = 0
    print("[geospatial.contract]")

    # ── 1. one integer, one meaning ────────────────────────────────────────────
    var codes = _codes()
    var dup_code = False
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            if codes[i] == codes[j]:
                dup_code = True
    var out_of_range = False
    for i in range(len(codes)):
        if codes[i] < 700 or codes[i] > 729:
            out_of_range = True
    var dup_name = False
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            if geo_status_name(codes[i]) == geo_status_name(codes[j]):
                dup_name = True
    var unnamed = False
    for i in range(len(codes)):
        if geo_status_name(codes[i]) == "unknown_status":
            unnamed = True
    if (
        len(codes) == 24
        and not dup_code
        and not out_of_range
        and not dup_name
        and not unnamed
    ):
        passed += 1
        print("  ✅ 24 codes, all in 700..729, all distinct, all distinctly named")
    else:
        failed += 1
        print("  ❌ code vocabulary is not injective:", dup_code, out_of_range, dup_name)

    if (
        geo_status_name(699) == "unknown_status"
        and geo_status_name(730) == "unknown_status"
        and geo_frame_name(3) == "unknown_frame"
        and geo_metric_name(3) == "unknown_metric"
    ):
        passed += 1
        print("  ✅ a code outside the range names itself unknown, never a neighbour")
    else:
        failed += 1
        print("  ❌ an out-of-range tag was given a real name")

    # The frame name carries the AXIS ORDER, because the order is the meaning.
    if (
        geo_frame_name(GEO_FRAME_LONLAT_DEG) == "lonlat_deg_x_is_longitude"
        and geo_frame_name(GEO_FRAME_LATLON_DEG) == "latlon_deg_x_is_latitude"
        and geo_frame_name(GEO_FRAME_PLANE_M) == "plane_m_x_is_easting"
    ):
        passed += 1
        print("  ✅ every frame name states which axis is which")
    else:
        failed += 1
        print("  ❌ a frame name does not state its axis order")

    # ── 2. axis order is resolved from the tag, never assumed ──────────────────
    # (x, y) = (2.3522, 48.8566) is Paris in GeoJSON order: longitude first.
    if (
        geo_lat_of(2.3522, 48.8566, GEO_FRAME_LONLAT_DEG) == 48.8566
        and geo_lon_of(2.3522, 48.8566, GEO_FRAME_LONLAT_DEG) == 2.3522
        and geo_lat_of(48.8566, 2.3522, GEO_FRAME_LATLON_DEG) == 48.8566
        and geo_lon_of(48.8566, 2.3522, GEO_FRAME_LATLON_DEG) == 2.3522
    ):
        passed += 1
        print("  ✅ Paris reads as 48.8566 N, 2.3522 E in BOTH declared orders")
    else:
        failed += 1
        print("  ❌ the frame tag did not resolve the axis order")

    # A projected pair has no latitude. 0.0 is the representable slot, and the FLAG
    # (`geo_is_degree_frame`) is the answer — never read the slot.
    if (
        geo_lat_of(500000.0, 4649776.0, GEO_FRAME_PLANE_M) == 0.0
        and geo_lon_of(500000.0, 4649776.0, GEO_FRAME_PLANE_M) == 0.0
    ):
        passed += 1
        print("  ✅ a projected easting/northing reports no latitude, not a fake one")
    else:
        failed += 1
        print("  ❌ a projected pair produced a latitude")

    # The detectable swap: Tokyo is 35.6762 N, 139.6503 E. Written lon-first when the reader
    # is lat-first, the 139.65 lands in the latitude slot and is not a latitude.
    if (
        geo_pair_range_defect(139.6503, 35.6762, GEO_FRAME_LONLAT_DEG) == GEO_OK
        and geo_pair_range_defect(139.6503, 35.6762, GEO_FRAME_LATLON_DEG) == GEO_ERR_RANGE
        and geo_pair_range_defect(35.6762, 139.6503, GEO_FRAME_LATLON_DEG) == GEO_OK
        and geo_pair_range_defect(35.6762, 139.6503, GEO_FRAME_LONLAT_DEG) == GEO_ERR_RANGE
    ):
        passed += 1
        print("  ✅ Tokyo in the wrong axis order is GEO_ERR_RANGE, not a wrapped angle")
    else:
        failed += 1
        print("  ❌ a swapped Tokyo was accepted")

    # +-90 and +-180 are exactly representable and are legal input: a pole and the seam are
    # real places. 90.5 is not a latitude and no tolerance widens the band to admit it.
    if (
        geo_pair_range_defect(180.0, 90.0, GEO_FRAME_LONLAT_DEG) == GEO_OK
        and geo_pair_range_defect(-180.0, -90.0, GEO_FRAME_LONLAT_DEG) == GEO_OK
        and geo_pair_range_defect(0.0, 90.5, GEO_FRAME_LONLAT_DEG) == GEO_ERR_RANGE
        and geo_pair_range_defect(180.5, 0.0, GEO_FRAME_LONLAT_DEG) == GEO_ERR_RANGE
    ):
        passed += 1
        print("  ✅ +-90/+-180 admitted exactly; 90.5 refused with no epsilon")
    else:
        failed += 1
        print("  ❌ the range band is not exactly +-90 / +-180")

    # A projected coordinate has no angular band — an easting of 500000 is just a number —
    # but it still must be finite.
    var inf_v = 1.0 / 0.0
    var nan_v = inf_v - inf_v
    if (
        geo_pair_range_defect(500000.0, 4649776.0, GEO_FRAME_PLANE_M) == GEO_OK
        and geo_pair_range_defect(inf_v, 0.0, GEO_FRAME_PLANE_M) == GEO_ERR_NON_FINITE
        and geo_pair_range_defect(0.0, nan_v, GEO_FRAME_PLANE_M) == GEO_ERR_NON_FINITE
        and geo_pair_range_defect(nan_v, 0.0, GEO_FRAME_LONLAT_DEG) == GEO_ERR_NON_FINITE
    ):
        passed += 1
        print("  ✅ a projected pair needs only finiteness; NaN and inf are refused")
    else:
        failed += 1
        print("  ❌ finiteness is not enforced on every frame")

    # ── mixed units are refused, not silently computed ─────────────────────────
    if (
        geo_metric_defect(GEO_FRAME_LONLAT_DEG, GEO_METRIC_HAVERSINE) == GEO_OK
        and geo_metric_defect(GEO_FRAME_LONLAT_DEG, GEO_METRIC_VINCENTY) == GEO_OK
        and geo_metric_defect(GEO_FRAME_LONLAT_DEG, GEO_METRIC_EUCLIDEAN)
        == GEO_ERR_UNIT_MISMATCH
        and geo_metric_defect(GEO_FRAME_PLANE_M, GEO_METRIC_HAVERSINE)
        == GEO_ERR_UNIT_MISMATCH
        and geo_metric_defect(GEO_FRAME_PLANE_M, GEO_METRIC_EUCLIDEAN) == GEO_OK
        and geo_metric_defect(GEO_FRAME_PLANE_M, 3) == GEO_ERR_METRIC
        and geo_metric_defect(7, GEO_METRIC_EUCLIDEAN) == GEO_ERR_FRAME
        and geo_metric_defect(-1, GEO_METRIC_EUCLIDEAN) == GEO_ERR_FRAME
        and geo_frame_defect(-1) == GEO_ERR_FRAME
    ):
        passed += 1
        print("  ✅ degrees x euclidean and metres x haversine are both refused")
    else:
        failed += 1
        print("  ❌ a mixed frame/metric pair was admitted")

    # ── the count gate, which is what keeps the worker alive ───────────────────
    var xs = List[Float64]()
    var ys = List[Float64]()
    for i in range(4):
        xs.append(Float64(i))
        ys.append(Float64(i) / 2.0)
    if (
        geo_points_defect(xs, ys, 4, GEO_FRAME_PLANE_M, GEO_MAX_POINTS) == GEO_OK
        and geo_points_defect(xs, ys, 5, GEO_FRAME_PLANE_M, GEO_MAX_POINTS) == GEO_ERR_COUNT
        and geo_points_defect(xs, ys, -1, GEO_FRAME_PLANE_M, GEO_MAX_POINTS) == GEO_ERR_COUNT
        and geo_points_defect(xs, ys, 3, GEO_FRAME_PLANE_M, 2) == GEO_ERR_TOO_LARGE
        and geo_points_defect(xs, ys, 0, GEO_FRAME_PLANE_M, GEO_MAX_POINTS) == GEO_OK
        and geo_points_defect(xs, ys, 1, 9, GEO_MAX_POINTS) == GEO_ERR_FRAME
    ):
        passed += 1
        print("  ✅ n=5 over a 4-long list is GEO_ERR_COUNT; the process is still alive")
    else:
        failed += 1
        print("  ❌ the count gate let something through")

    # A short SECOND list is the asymmetric case a `n <= len(xs)`-only check misses.
    var short_y = List[Float64]()
    short_y.append(0.0)
    if geo_points_defect(xs, short_y, 4, GEO_FRAME_PLANE_M, GEO_MAX_POINTS) == GEO_ERR_COUNT:
        passed += 1
        print("  ✅ both coordinate lists are bounded, not just the first")
    else:
        failed += 1
        print("  ❌ a short ys list was not caught")

    # ── the CSR-style offsets gate ─────────────────────────────────────────────
    var off = List[Int]()
    off.append(0)
    off.append(3)
    off.append(7)
    if (
        geo_offsets_defect(off, 2, 7, 16) == GEO_OK
        and geo_offsets_defect(off, 2, 6, 16) == GEO_ERR_OFFSETS
        and geo_offsets_defect(off, 3, 7, 16) == GEO_ERR_OFFSETS
        and geo_offsets_defect(off, 2, 7, 1) == GEO_ERR_TOO_LARGE
        and geo_offsets_defect(off, -1, 7, 16) == GEO_ERR_PARAM
    ):
        passed += 1
        print("  ✅ offsets: length, tail and ceiling all checked")
    else:
        failed += 1
        print("  ❌ the offsets gate is incomplete")

    var bad_head = List[Int]()
    bad_head.append(1)
    bad_head.append(2)
    var non_mono = List[Int]()
    non_mono.append(0)
    non_mono.append(5)
    non_mono.append(2)
    if (
        geo_offsets_defect(bad_head, 1, 4, 16) == GEO_ERR_OFFSETS
        and geo_offsets_defect(non_mono, 2, 8, 16) == GEO_ERR_OFFSETS
    ):
        passed += 1
        print("  ✅ a non-zero head and a decreasing pointer are both refused")
    else:
        failed += 1
        print("  ❌ a malformed offsets array was accepted")

    # ── the wrapping multiply, with the exact triple that wraps ────────────────
    # 3 * 6148914691236517206 == 2 in wrapping 64-bit arithmetic, so `rows * cols <= ceiling`
    # PASSES for a request 3e18 times over the ceiling. Asserted as arithmetic first, so the
    # reason this function divides is visible in the suite and not only in a comment.
    var wrapper = 6148914691236517206
    var wrapped = 3 * wrapper
    if wrapped == 2 and not geo_cells_fit(3, wrapper, 1 << 22):
        passed += 1
        print("  ✅ 3 * 6148914691236517206 == 2, and geo_cells_fit still refuses it")
    else:
        failed += 1
        print("  ❌ the wrapping product was not caught:", wrapped)

    if (
        geo_cells_fit(1000, 1000, 1 << 20)
        and not geo_cells_fit(1025, 1024, 1 << 20)
        and geo_cells_fit(0, wrapper, 1 << 20)
        and not geo_cells_fit(-1, 4, 1 << 20)
        and not geo_cells_fit(4, 4, -1)
    ):
        passed += 1
        print("  ✅ 1000x1000 fits 2^20, 1025x1024 does not, a zero factor always fits")
    else:
        failed += 1
        print("  ❌ geo_cells_fit is wrong at its boundary")

    # ── absence is representable, never a raw non-finite ──────────────────────
    if (
        geo_finite_or_zero(nan_v) == 0.0
        and geo_finite_or_zero(inf_v) == 0.0
        and geo_finite_or_zero(-inf_v) == 0.0
        and geo_finite_or_zero(-3.5) == -3.5
        and not geo_finite(nan_v)
        and not geo_finite(inf_v)
        and geo_finite(0.0)
    ):
        passed += 1
        print("  ✅ NaN and both infinities collapse to a representable 0.0")
    else:
        failed += 1
        print("  ❌ a non-finite would have reached a struct field")

    # ── the seam: shortest step, and no rounding at +-180 ──────────────────────
    # 179 -> -179 is 2 degrees EAST, not 358 west. That single decision is what makes the
    # pole-winding test a total function.
    if (
        geo_lon_delta(179.0, -179.0) == 2.0
        and geo_lon_delta(-179.0, 179.0) == -2.0
        and geo_lon_delta(0.0, 90.0) == 90.0
        and geo_lon_delta(180.0, -90.0) == 90.0
        and geo_normalise_lon(180.0) == 180.0
        and geo_normalise_lon(-180.0) == -180.0
        and geo_normalise_lon(190.0) == -170.0
        and geo_normalise_lon(-190.0) == 170.0
        and geo_normalise_lon(nan_v) == 0.0
    ):
        passed += 1
        print("  ✅ 179 -> -179 is +2 degrees; +-180 survives the fold unchanged")
    else:
        failed += 1
        print("  ❌ the seam arithmetic is wrong:", geo_lon_delta(179.0, -179.0))

    # ── metres per degree, against the closed form ─────────────────────────────
    # pi * 6371000 / 180 = 111194.92664455873 m, which is a degree of latitude anywhere and
    # a degree of longitude at the equator.
    if fabs(GEO_M_PER_DEG - 111194.92664455873) < 1.0e-9 and GEO_EARTH_RADIUS_M == 6371000.0:
        passed += 1
        print("  ✅ GEO_M_PER_DEG is pi*R/180 = 111194.92664455873 for R = 6371 km")
    else:
        failed += 1
        print("  ❌ GEO_M_PER_DEG is not pi*R/180:", GEO_M_PER_DEG)

    # cos(60 deg) = 0.5 exactly in real arithmetic, so a degree of longitude at 60 N is half
    # a degree of latitude. The band form takes the WORST latitude in the interval.
    var lon60 = geo_m_per_deg_lon_lower(60.0, 30.0)
    if (
        fabs(lon60 - GEO_M_PER_DEG * 0.5) < 1.0e-6
        and geo_m_per_deg_lon_lower(90.0, 0.0) == 0.0
        and geo_m_per_deg_lon_lower(-90.0, 0.0) == 0.0
        and fabs(geo_m_per_deg_lon_lower(0.0, 0.0) - GEO_M_PER_DEG) < 1.0e-9
    ):
        passed += 1
        print("  ✅ a degree of longitude at 60 N is half of one at the equator; 0 at a pole")
    else:
        failed += 1
        print("  ❌ the longitude scale is wrong:", lon60)

    # ── the bound that was NOT a bound ────────────────────────────────────────
    # True distance between (60N, 0E) and (60N, 48E): 2 609 522.2704942976 m (CPython, from
    # 2*asin(cos60*sin24)*R). The naive product 48 * 111194.92664455873 * cos(60) is
    # 2 668 678.24 m — 2.3% ABOVE the distance it claims to bound. `geo_gap_lower_m` is below.
    var gap_bound = geo_gap_lower_m(48.0, GEO_FRAME_LONLAT_DEG, 60.0, 60.0)
    if REF_NAIVE_BOUND_M > REF_LAT60_DLON48_M and gap_bound <= REF_LAT60_DLON48_M:
        passed += 1
        print(
            "  ✅ naive 2668678.24 m > true 2609522.27 m >= bound",
            String(gap_bound),
            "m",
        )
    else:
        failed += 1
        print("  ❌ geo_gap_lower_m is not a lower bound:", gap_bound)

    # It must still be TIGHT, or the k-nearest ring expansion degenerates to a full scan.
    # Within 1% of the true distance at this gap.
    if gap_bound > REF_LAT60_DLON48_M * 0.99:
        passed += 1
        print("  ✅ and it is within 1% of the distance, so it still prunes")
    else:
        failed += 1
        print("  ❌ the bound is too loose to prune:", gap_bound)

    # A small gap at the equator is the linear case: 1 degree -> pi*R/180 metres.
    var eq_gap = geo_gap_lower_m(1.0, GEO_FRAME_LONLAT_DEG, 0.0, 0.0)
    if fabs(eq_gap - GEO_M_PER_DEG) < GEO_M_PER_DEG * 1.0e-4:
        passed += 1
        print("  ✅ a 1-degree gap at the equator bounds at pi*R/180, as it must")
    else:
        failed += 1
        print("  ❌ the equatorial gap bound is wrong:", eq_gap)

    # A RAW longitude gap of 350 degrees is a real separation of 10, so folding through the
    # seam is mandatory: without it the bound would be 35x too large and prune real neighbours.
    var fold10 = geo_gap_lower_m(10.0, GEO_FRAME_LONLAT_DEG, 0.0, 0.0)
    var fold350 = geo_gap_lower_m(350.0, GEO_FRAME_LONLAT_DEG, 0.0, 0.0)
    if fabs(fold350 - fold10) < 1.0e-6 and fold350 < fold10 * 1.0001:
        passed += 1
        print("  ✅ a raw 350-degree gap folds to 10 degrees, not 350")
    else:
        failed += 1
        print("  ❌ the seam fold is missing:", fold350, fold10)

    # A projected gap is metres already; a band touching a pole gives zero, which turns an
    # expanding search into a full scan and stays exact.
    if (
        geo_gap_lower_m(250.0, GEO_FRAME_PLANE_M, 0.0, 0.0) == 250.0
        and geo_gap_lower_m(5.0, GEO_FRAME_LONLAT_DEG, 90.0, 80.0) == 0.0
        and geo_gap_lower_m(0.0, GEO_FRAME_LONLAT_DEG, 0.0, 0.0) == 0.0
        and geo_gap_lower_m(-4.0, GEO_FRAME_LONLAT_DEG, 0.0, 0.0) == 0.0
        and geo_gap_lower_m(5.0, 9, 0.0, 0.0) == 0.0
        and geo_gap_lower_m(nan_v, GEO_FRAME_PLANE_M, 0.0, 0.0) == 0.0
    ):
        passed += 1
        print("  ✅ metres pass through; a pole band and a bad frame bound at 0.0")
    else:
        failed += 1
        print("  ❌ a degenerate gap did not bound at zero")

    if GEO_BOUND_SLACK > 0.0 and GEO_BOUND_SLACK < 1.0e-6:
        passed += 1
        print("  ✅ the bound's slack is relative and tiny (1e-9), not a modelling tolerance")
    else:
        failed += 1
        print("  ❌ GEO_BOUND_SLACK is out of range:", GEO_BOUND_SLACK)

    # ── the search box is a SUPERSET of the disc, in the only safe direction ───
    # 111194.92664455873 m is one degree at the equator, so the half-width there is 1 degree.
    # At 60 N the same radius spans about 2 degrees of longitude, and the box must be at least
    # that wide or pairs are silently dropped.
    var half_eq = geo_degree_box_half(GEO_M_PER_DEG, 0.0)
    var half_60 = geo_degree_box_half(GEO_M_PER_DEG, 60.0)
    if (
        half_eq >= 1.0
        and half_eq < 1.02
        and half_60 >= 2.0
        and half_60 < 2.2
        and geo_degree_box_half(1.0e8, 0.0) == 180.0
        and geo_degree_box_half(GEO_M_PER_DEG, 89.9999) == 180.0
        and geo_degree_box_half(-1.0, 0.0) == 180.0
    ):
        passed += 1
        print("  ✅ box half-width: 1 deg at the equator, >=2 deg at 60 N, 180 near a pole")
    else:
        failed += 1
        print("  ❌ the search box is not a superset:", half_eq, half_60)

    print("  [geospatial.contract] Passed:", passed, "Failed:", failed)
