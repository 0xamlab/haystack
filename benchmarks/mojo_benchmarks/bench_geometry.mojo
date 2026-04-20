"""bench_geometry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from geometry import distance_2d, cross_product_2d, point_in_polygon, polygon_area, polygon_perimeter, convex_hull, line_intersection, centroid, bounding_box, Point
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_distance_2d: Float64 = 0.0
    var _t0_distance_2d = perf_counter_ns()
    for _ in range(N):
        _acc_distance_2d += distance_2d(Point(0.0,0.0), Point(3.0,4.0))
    var _t1_distance_2d = perf_counter_ns()
    var _ns_distance_2d = Float64(_t1_distance_2d - _t0_distance_2d) / Float64(N)
    print("MOJO_TIMING geometry::distance_2d", _ns_distance_2d, _acc_distance_2d)
    var _acc_cross_product_2d: Float64 = 0.0
    var _t0_cross_product_2d = perf_counter_ns()
    for _ in range(N):
        _acc_cross_product_2d += cross_product_2d(Point(0.0,0.0), Point(1.0,0.0), Point(0.0,1.0))
    var _t1_cross_product_2d = perf_counter_ns()
    var _ns_cross_product_2d = Float64(_t1_cross_product_2d - _t0_cross_product_2d) / Float64(N)
    print("MOJO_TIMING geometry::cross_product_2d", _ns_cross_product_2d, _acc_cross_product_2d)
    var _acc_point_in_polygon: Float64 = 0.0
    var _t0_point_in_polygon = perf_counter_ns()
    for _ in range(N):
        _acc_point_in_polygon += Float64(point_in_polygon(Point(0.5,0.5), [Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)]))
    var _t1_point_in_polygon = perf_counter_ns()
    var _ns_point_in_polygon = Float64(_t1_point_in_polygon - _t0_point_in_polygon) / Float64(N)
    print("MOJO_TIMING geometry::point_in_polygon", _ns_point_in_polygon, _acc_point_in_polygon)
    var _acc_polygon_area: Float64 = 0.0
    var _t0_polygon_area = perf_counter_ns()
    for _ in range(N):
        _acc_polygon_area += polygon_area([Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)])
    var _t1_polygon_area = perf_counter_ns()
    var _ns_polygon_area = Float64(_t1_polygon_area - _t0_polygon_area) / Float64(N)
    print("MOJO_TIMING geometry::polygon_area", _ns_polygon_area, _acc_polygon_area)
    var _acc_polygon_perimeter: Float64 = 0.0
    var _t0_polygon_perimeter = perf_counter_ns()
    for _ in range(N):
        _acc_polygon_perimeter += polygon_perimeter([Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)])
    var _t1_polygon_perimeter = perf_counter_ns()
    var _ns_polygon_perimeter = Float64(_t1_polygon_perimeter - _t0_polygon_perimeter) / Float64(N)
    print("MOJO_TIMING geometry::polygon_perimeter", _ns_polygon_perimeter, _acc_polygon_perimeter)
    var _acc_convex_hull: Float64 = 0.0
    var _t0_convex_hull = perf_counter_ns()
    for _ in range(N):
        var _r_convex_hull = convex_hull([Point(0.0,0.0),Point(1.0,0.0),Point(0.5,1.0),Point(0.5,0.5)])
        _acc_convex_hull += Float64(len(_r_convex_hull))
    var _t1_convex_hull = perf_counter_ns()
    var _ns_convex_hull = Float64(_t1_convex_hull - _t0_convex_hull) / Float64(N)
    print("MOJO_TIMING geometry::convex_hull", _ns_convex_hull, _acc_convex_hull)
    var _keeper_line_intersection = List[Point]()
    _keeper_line_intersection.append(line_intersection(Point(0.0,0.0), Point(1.0,1.0), Point(1.0,0.0), Point(0.0,1.0)))
    var _acc_line_intersection: Float64 = 0.0
    var _t0_line_intersection = perf_counter_ns()
    for _ in range(N):
        _keeper_line_intersection[0] = line_intersection(Point(0.0,0.0), Point(1.0,1.0), Point(1.0,0.0), Point(0.0,1.0))
        _acc_line_intersection += Float64(len(_keeper_line_intersection))
    var _t1_line_intersection = perf_counter_ns()
    var _ns_line_intersection = Float64(_t1_line_intersection - _t0_line_intersection) / Float64(N)
    print("MOJO_TIMING geometry::line_intersection", _ns_line_intersection, _acc_line_intersection)
    var _keeper_centroid = List[Point]()
    _keeper_centroid.append(centroid([Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)]))
    var _acc_centroid: Float64 = 0.0
    var _t0_centroid = perf_counter_ns()
    for _ in range(N):
        _keeper_centroid[0] = centroid([Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)])
        _acc_centroid += Float64(len(_keeper_centroid))
    var _t1_centroid = perf_counter_ns()
    var _ns_centroid = Float64(_t1_centroid - _t0_centroid) / Float64(N)
    print("MOJO_TIMING geometry::centroid", _ns_centroid, _acc_centroid)
    var _acc_bounding_box: Float64 = 0.0
    var _t0_bounding_box = perf_counter_ns()
    for _ in range(N):
        var _r_bounding_box = bounding_box([Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)])
        _acc_bounding_box += Float64(len(_r_bounding_box))
    var _t1_bounding_box = perf_counter_ns()
    var _ns_bounding_box = Float64(_t1_bounding_box - _t0_bounding_box) / Float64(N)
    print("MOJO_TIMING geometry::bounding_box", _ns_bounding_box, _acc_bounding_box)
