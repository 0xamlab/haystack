"""Wave 18 test suite — Advanced Sampling, Time Series Statistics, Computational Geometry."""

from sampling import (
    halton_sequence,
    halton_2d,
    stratified_sample_1d,
    latin_hypercube_sample,
    sobol_like_2d,
    discrepancy_l2_star,
)
from timeseries_stats import (
    autocorrelation,
    autocorrelation_function,
    partial_autocorrelation,
    rolling_mean,
    rolling_std,
    exponential_smoothing,
    difference,
    adf_test_statistic,
    holt_linear,
)
from geometry import (
    Point,
    distance_2d,
    point_in_polygon,
    polygon_area,
    polygon_perimeter,
    convex_hull,
    line_intersection,
    cross_product_2d,
    centroid,
    bounding_box,
)
from std.math import abs as fabs
from std.random import random_float64


fn assert_true(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("ASSERTION FAILED: " + msg)


fn _make_list2(v0: Float64, v1: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    l.append(v1)
    return l^


fn _make_ts5(v0: Float64, v1: Float64, v2: Float64, v3: Float64, v4: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    l.append(v1)
    l.append(v2)
    l.append(v3)
    l.append(v4)
    return l^


fn _make_ts4(v0: Float64, v1: Float64, v2: Float64, v3: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    l.append(v1)
    l.append(v2)
    l.append(v3)
    return l^


def main() raises:
    print("━━━ Wave 18 test suite (Sampling, TimeSeries, Geometry) ━━━\n")

    # ═══════════════════════════════════════════════════════════════════════════
    # SAMPLING
    # ═══════════════════════════════════════════════════════════════════════════

    # 1. halton_sequence(5, 2) — verify known values {0.5, 0.25, 0.75, 0.125, 0.625}
    var h5 = halton_sequence(5, 2)
    assert_true(len(h5) == 5, "halton(5,2) length == 5")
    assert_true(fabs(h5[0] - 0.5) < 1e-10, "halton(5,2)[0] == 0.5")
    assert_true(fabs(h5[1] - 0.25) < 1e-10, "halton(5,2)[1] == 0.25")
    assert_true(fabs(h5[2] - 0.75) < 1e-10, "halton(5,2)[2] == 0.75")
    assert_true(fabs(h5[3] - 0.125) < 1e-10, "halton(5,2)[3] == 0.125")
    assert_true(fabs(h5[4] - 0.625) < 1e-10, "halton(5,2)[4] == 0.625")

    # 2. halton_2d(100) — all values in (0,1)
    var h2d = halton_2d(100)
    assert_true(len(h2d) == 100, "halton_2d(100) length == 100")
    var h2d_ok = True
    for i in range(100):
        if h2d[i][0] <= 0.0 or h2d[i][0] >= 1.0:
            h2d_ok = False
        if h2d[i][1] <= 0.0 or h2d[i][1] >= 1.0:
            h2d_ok = False
    assert_true(h2d_ok, "halton_2d(100) all values in (0,1)")

    # 3. stratified_sample_1d(10) — 10 values, each in correct stratum
    var strat = stratified_sample_1d(10)
    assert_true(len(strat) == 10, "stratified(10) length == 10")
    var strat_ok = True
    for i in range(10):
        var lo = Float64(i) / 10.0
        var hi = Float64(i + 1) / 10.0
        if strat[i] < lo or strat[i] >= hi:
            strat_ok = False
    assert_true(strat_ok, "stratified(10) each in correct stratum")

    # 4. latin_hypercube_sample(50, 3) — 50 points, 3 dims, all in [0,1]
    var lhs = latin_hypercube_sample(50, 3)
    assert_true(len(lhs) == 50, "LHS(50,3) length == 50")
    var lhs_ok = True
    for i in range(50):
        assert_true(len(lhs[i]) == 3, "LHS point dim == 3")
        for j in range(3):
            if lhs[i][j] < 0.0 or lhs[i][j] > 1.0:
                lhs_ok = False
    assert_true(lhs_ok, "LHS(50,3) all values in [0,1]")

    # 5. sobol_like_2d(100) — all values in [0,1]^2
    var sob = sobol_like_2d(100)
    assert_true(len(sob) == 100, "sobol_like_2d(100) length == 100")
    var sob_ok = True
    for i in range(100):
        if sob[i][0] < 0.0 or sob[i][0] > 1.0:
            sob_ok = False
        if sob[i][1] < 0.0 or sob[i][1] > 1.0:
            sob_ok = False
    assert_true(sob_ok, "sobol_like_2d(100) all in [0,1]^2")

    # 6. discrepancy_l2_star: Halton < random (use n=200)
    var halton_pts = halton_2d(200)
    var disc_halton = discrepancy_l2_star(halton_pts)
    # Generate random points
    var rand_pts = List[List[Float64]]()
    for _ in range(200):
        rand_pts.append(_make_list2(random_float64(), random_float64()))
    var disc_rand = discrepancy_l2_star(rand_pts)
    assert_true(disc_halton < disc_rand, "halton discrepancy < random discrepancy")

    print("✅ Sampling (14 assertions)")

    # ═══════════════════════════════════════════════════════════════════════════
    # TIME SERIES STATISTICS
    # ═══════════════════════════════════════════════════════════════════════════

    # Build a simple time series
    var ts = List[Float64]()
    for i in range(100):
        ts.append(Float64(i) * 0.5 + 2.0)

    # 7. autocorrelation(data, 0) ≈ 1.0
    var ac0 = autocorrelation(ts, 0)
    assert_true(fabs(ac0 - 1.0) < 1e-10, "autocorrelation(ts, 0) ≈ 1.0")

    # 8. autocorrelation_function length == max_lag + 1
    var acf = autocorrelation_function(ts, 10)
    assert_true(len(acf) == 11, "ACF length == max_lag + 1")

    # 9. ACF[0] == 1.0
    assert_true(fabs(acf[0] - 1.0) < 1e-10, "ACF[0] == 1.0")

    # 10. rolling_mean([1,2,3,4,5], 3) == [2.0, 3.0, 4.0]
    var rm = rolling_mean(_make_ts5(1.0, 2.0, 3.0, 4.0, 5.0), 3)
    assert_true(len(rm) == 3, "rolling_mean([1..5], 3) length == 3")
    assert_true(fabs(rm[0] - 2.0) < 1e-10, "rolling_mean[0] == 2.0")
    assert_true(fabs(rm[1] - 3.0) < 1e-10, "rolling_mean[1] == 3.0")
    assert_true(fabs(rm[2] - 4.0) < 1e-10, "rolling_mean[2] == 4.0")

    # 11. rolling_std on constant data ≈ 0.0
    var const_data = _make_ts5(5.0, 5.0, 5.0, 5.0, 5.0)
    var rs = rolling_std(const_data, 3)
    assert_true(len(rs) == 3, "rolling_std length == 3")
    assert_true(fabs(rs[0]) < 1e-10, "rolling_std(constant) ≈ 0.0")
    assert_true(fabs(rs[1]) < 1e-10, "rolling_std(constant)[1] ≈ 0.0")

    # 12. exponential_smoothing first value == data[0]
    var es = exponential_smoothing(_make_ts5(10.0, 20.0, 30.0, 40.0, 50.0), 0.3)
    assert_true(len(es) == 5, "exponential_smoothing length == 5")
    assert_true(fabs(es[0] - 10.0) < 1e-10, "exp_smooth[0] == data[0]")

    # 13. difference([1,4,9,16], 1) == [3,5,7]
    var d1 = difference(_make_ts4(1.0, 4.0, 9.0, 16.0), 1)
    assert_true(len(d1) == 3, "difference(order=1) length == 3")
    assert_true(fabs(d1[0] - 3.0) < 1e-10, "diff[0] == 3")
    assert_true(fabs(d1[1] - 5.0) < 1e-10, "diff[1] == 5")
    assert_true(fabs(d1[2] - 7.0) < 1e-10, "diff[2] == 7")

    # 14. difference([1,4,9,16], 2) == [2,2]
    var d2 = difference(_make_ts4(1.0, 4.0, 9.0, 16.0), 2)
    assert_true(len(d2) == 2, "difference(order=2) length == 2")
    assert_true(fabs(d2[0] - 2.0) < 1e-10, "diff2[0] == 2")
    assert_true(fabs(d2[1] - 2.0) < 1e-10, "diff2[1] == 2")

    # 15. holt_linear length == len(data)
    var hl = holt_linear(_make_ts5(1.0, 3.0, 5.0, 7.0, 9.0), 0.5, 0.3)
    assert_true(len(hl) == 5, "holt_linear length == 5")

    # 16. partial_autocorrelation first value ≈ 1.0
    var pacf = partial_autocorrelation(ts, 5)
    assert_true(len(pacf) == 6, "PACF length == max_lag + 1")
    assert_true(fabs(pacf[0] - 1.0) < 1e-10, "PACF[0] ≈ 1.0")

    # 17. adf_test_statistic on trend data (non-stationary) — just verify it returns a value
    var adf = adf_test_statistic(ts)
    # For a linear trend, the ADF stat should be finite
    assert_true(adf > -1e10 and adf < 1e10, "ADF stat is finite")

    print("✅ Time series statistics (20 assertions)")

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPUTATIONAL GEOMETRY
    # ═══════════════════════════════════════════════════════════════════════════

    # 18. distance_2d(Point(0,0), Point(3,4)) ≈ 5.0
    var dist = distance_2d(Point(0.0, 0.0), Point(3.0, 4.0))
    assert_true(fabs(dist - 5.0) < 1e-10, "distance(0,0)-(3,4) ≈ 5.0")

    # 19. point_in_polygon inside a unit square
    var square = List[Point]()
    square.append(Point(0.0, 0.0))
    square.append(Point(1.0, 0.0))
    square.append(Point(1.0, 1.0))
    square.append(Point(0.0, 1.0))

    assert_true(point_in_polygon(Point(0.5, 0.5), square), "point (0.5,0.5) inside unit square")

    # 20. point_in_polygon outside a square
    assert_true(not point_in_polygon(Point(2.0, 2.0), square), "point (2,2) outside unit square")

    # 21. polygon_area of unit square == 1.0
    var area_sq = polygon_area(square)
    assert_true(fabs(area_sq - 1.0) < 1e-10, "area(unit square) == 1.0")

    # 22. polygon_area of triangle (0,0), (4,0), (0,3) == 6.0
    var tri = List[Point]()
    tri.append(Point(0.0, 0.0))
    tri.append(Point(4.0, 0.0))
    tri.append(Point(0.0, 3.0))
    var area_tri = polygon_area(tri)
    assert_true(fabs(area_tri - 6.0) < 1e-10, "area(triangle 4x3) == 6.0")

    # 23. polygon_perimeter of unit square == 4.0
    var perim_sq = polygon_perimeter(square)
    assert_true(fabs(perim_sq - 4.0) < 1e-10, "perimeter(unit square) == 4.0")

    # 24. convex_hull — 8 points with interior; hull < total
    var pts8 = List[Point]()
    pts8.append(Point(0.0, 0.0))
    pts8.append(Point(1.0, 0.0))
    pts8.append(Point(2.0, 0.0))
    pts8.append(Point(2.0, 2.0))
    pts8.append(Point(0.0, 2.0))
    pts8.append(Point(0.5, 0.5))  # interior
    pts8.append(Point(1.0, 1.0))  # interior
    pts8.append(Point(1.5, 0.5))  # interior
    var hull = convex_hull(pts8)
    assert_true(len(hull) < 8, "convex_hull size < 8 total points")
    assert_true(len(hull) >= 4, "convex_hull size >= 4 (at least corners)")

    # 25. cross_product_2d sign check — CCW
    var cp_ccw = cross_product_2d(Point(0.0, 0.0), Point(1.0, 0.0), Point(0.0, 1.0))
    assert_true(cp_ccw > 0.0, "cross_product CCW > 0")

    # 26. cross_product_2d sign check — CW
    var cp_cw = cross_product_2d(Point(0.0, 0.0), Point(0.0, 1.0), Point(1.0, 0.0))
    assert_true(cp_cw < 0.0, "cross_product CW < 0")

    # 27. centroid of unit square ≈ (0.5, 0.5)
    var ctr = centroid(square)
    assert_true(fabs(ctr.x - 0.5) < 1e-10, "centroid(square).x ≈ 0.5")
    assert_true(fabs(ctr.y - 0.5) < 1e-10, "centroid(square).y ≈ 0.5")

    # 28. bounding_box
    var bb = bounding_box(pts8)
    assert_true(len(bb) == 4, "bounding_box length == 4")
    assert_true(fabs(bb[0] - 0.0) < 1e-10, "bbox min_x == 0")
    assert_true(fabs(bb[1] - 0.0) < 1e-10, "bbox min_y == 0")
    assert_true(fabs(bb[2] - 2.0) < 1e-10, "bbox max_x == 2")
    assert_true(fabs(bb[3] - 2.0) < 1e-10, "bbox max_y == 2")

    # 29. line_intersection of X-pattern
    var ix = line_intersection(
        Point(0.0, 0.0), Point(2.0, 2.0),
        Point(0.0, 2.0), Point(2.0, 0.0),
    )
    assert_true(fabs(ix.x - 1.0) < 1e-10, "line_intersection X → (1,1).x")
    assert_true(fabs(ix.y - 1.0) < 1e-10, "line_intersection X → (1,1).y")

    print("✅ Computational geometry (18 assertions)")

    print("\n✅ All Wave 18 tests passed (52 assertions)")
