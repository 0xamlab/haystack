"""bench_geometry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from geometry import distance_2d, cross_product_2d, point_in_polygon, polygon_area, polygon_perimeter, convex_hull, line_intersection, centroid, bounding_box, Point
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_distance_2d = distance_2d(Point(0.0,0.0), Point(3.0,4.0))
    var _summary_distance_2d = _summary_float64(_result_distance_2d)
    print("MOJO_RESULT geometry::distance_2d", _summary_distance_2d)
    var _acc_cross_product_2d: Float64 = 0.0
    var _t0_cross_product_2d = perf_counter_ns()
    for _ in range(N):
        _acc_cross_product_2d += cross_product_2d(Point(0.0,0.0), Point(1.0,0.0), Point(0.0,1.0))
    var _t1_cross_product_2d = perf_counter_ns()
    var _ns_cross_product_2d = Float64(_t1_cross_product_2d - _t0_cross_product_2d) / Float64(N)
    print("MOJO_TIMING geometry::cross_product_2d", _ns_cross_product_2d, _acc_cross_product_2d)
    var _result_cross_product_2d = cross_product_2d(Point(0.0,0.0), Point(1.0,0.0), Point(0.0,1.0))
    var _summary_cross_product_2d = _summary_float64(_result_cross_product_2d)
    print("MOJO_RESULT geometry::cross_product_2d", _summary_cross_product_2d)
    var _acc_point_in_polygon: Float64 = 0.0
    var _t0_point_in_polygon = perf_counter_ns()
    for _ in range(N):
        _acc_point_in_polygon += Float64(point_in_polygon(Point(0.5,0.5), [Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)]))
    var _t1_point_in_polygon = perf_counter_ns()
    var _ns_point_in_polygon = Float64(_t1_point_in_polygon - _t0_point_in_polygon) / Float64(N)
    print("MOJO_TIMING geometry::point_in_polygon", _ns_point_in_polygon, _acc_point_in_polygon)
    var _result_point_in_polygon = point_in_polygon(Point(0.5,0.5), [Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)])
    var _summary_point_in_polygon = _summary_bool(_result_point_in_polygon)
    print("MOJO_RESULT geometry::point_in_polygon", _summary_point_in_polygon)
    var _acc_polygon_area: Float64 = 0.0
    var _t0_polygon_area = perf_counter_ns()
    for _ in range(N):
        _acc_polygon_area += polygon_area([Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)])
    var _t1_polygon_area = perf_counter_ns()
    var _ns_polygon_area = Float64(_t1_polygon_area - _t0_polygon_area) / Float64(N)
    print("MOJO_TIMING geometry::polygon_area", _ns_polygon_area, _acc_polygon_area)
    var _result_polygon_area = polygon_area([Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)])
    var _summary_polygon_area = _summary_float64(_result_polygon_area)
    print("MOJO_RESULT geometry::polygon_area", _summary_polygon_area)
    var _acc_polygon_perimeter: Float64 = 0.0
    var _t0_polygon_perimeter = perf_counter_ns()
    for _ in range(N):
        _acc_polygon_perimeter += polygon_perimeter([Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)])
    var _t1_polygon_perimeter = perf_counter_ns()
    var _ns_polygon_perimeter = Float64(_t1_polygon_perimeter - _t0_polygon_perimeter) / Float64(N)
    print("MOJO_TIMING geometry::polygon_perimeter", _ns_polygon_perimeter, _acc_polygon_perimeter)
    var _result_polygon_perimeter = polygon_perimeter([Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)])
    var _summary_polygon_perimeter = _summary_float64(_result_polygon_perimeter)
    print("MOJO_RESULT geometry::polygon_perimeter", _summary_polygon_perimeter)
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
    var _result_bounding_box = bounding_box([Point(0.0,0.0),Point(1.0,0.0),Point(1.0,1.0),Point(0.0,1.0)])
    var _summary_bounding_box = _summary_list_float64(_result_bounding_box)
    print("MOJO_RESULT geometry::bounding_box", _summary_bounding_box)
