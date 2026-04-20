"""bench_earth.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from earth import deg_to_rad, rad_to_deg, is_valid_coordinate, distance_on_unit_sphere, haversine, bearing, midpoint, destination_point, bounding_box, cross_track_distance
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

    var _acc_deg_to_rad: Float64 = 0.0
    var _t0_deg_to_rad = perf_counter_ns()
    for _ in range(N):
        _acc_deg_to_rad += deg_to_rad(0.5)
    var _t1_deg_to_rad = perf_counter_ns()
    var _ns_deg_to_rad = Float64(_t1_deg_to_rad - _t0_deg_to_rad) / Float64(N)
    print("MOJO_TIMING earth::deg_to_rad", _ns_deg_to_rad, _acc_deg_to_rad)
    var _acc_rad_to_deg: Float64 = 0.0
    var _t0_rad_to_deg = perf_counter_ns()
    for _ in range(N):
        _acc_rad_to_deg += rad_to_deg(0.5)
    var _t1_rad_to_deg = perf_counter_ns()
    var _ns_rad_to_deg = Float64(_t1_rad_to_deg - _t0_rad_to_deg) / Float64(N)
    print("MOJO_TIMING earth::rad_to_deg", _ns_rad_to_deg, _acc_rad_to_deg)
    var _acc_is_valid_coordinate: Float64 = 0.0
    var _t0_is_valid_coordinate = perf_counter_ns()
    for _ in range(N):
        _acc_is_valid_coordinate += Float64(is_valid_coordinate(0.5, 0.5))
    var _t1_is_valid_coordinate = perf_counter_ns()
    var _ns_is_valid_coordinate = Float64(_t1_is_valid_coordinate - _t0_is_valid_coordinate) / Float64(N)
    print("MOJO_TIMING earth::is_valid_coordinate", _ns_is_valid_coordinate, _acc_is_valid_coordinate)
    var _acc_distance_on_unit_sphere: Float64 = 0.0
    var _t0_distance_on_unit_sphere = perf_counter_ns()
    for _ in range(N):
        _acc_distance_on_unit_sphere += distance_on_unit_sphere(0.5, 0.5, 0.5, 0.5)
    var _t1_distance_on_unit_sphere = perf_counter_ns()
    var _ns_distance_on_unit_sphere = Float64(_t1_distance_on_unit_sphere - _t0_distance_on_unit_sphere) / Float64(N)
    print("MOJO_TIMING earth::distance_on_unit_sphere", _ns_distance_on_unit_sphere, _acc_distance_on_unit_sphere)
    var _acc_haversine: Float64 = 0.0
    var _t0_haversine = perf_counter_ns()
    for _ in range(N):
        _acc_haversine += haversine(0.5, 0.5, 0.5, 0.5)
    var _t1_haversine = perf_counter_ns()
    var _ns_haversine = Float64(_t1_haversine - _t0_haversine) / Float64(N)
    print("MOJO_TIMING earth::haversine", _ns_haversine, _acc_haversine)
    var _acc_bearing: Float64 = 0.0
    var _t0_bearing = perf_counter_ns()
    for _ in range(N):
        _acc_bearing += bearing(0.5, 0.5, 0.5, 0.5)
    var _t1_bearing = perf_counter_ns()
    var _ns_bearing = Float64(_t1_bearing - _t0_bearing) / Float64(N)
    print("MOJO_TIMING earth::bearing", _ns_bearing, _acc_bearing)
    var _acc_midpoint: Float64 = 0.0
    var _t0_midpoint = perf_counter_ns()
    for _ in range(N):
        var _r_midpoint = midpoint(0.5, 0.5, 0.5, 0.5)
        _acc_midpoint += Float64(len(_r_midpoint))
    var _t1_midpoint = perf_counter_ns()
    var _ns_midpoint = Float64(_t1_midpoint - _t0_midpoint) / Float64(N)
    print("MOJO_TIMING earth::midpoint", _ns_midpoint, _acc_midpoint)
    var _acc_destination_point: Float64 = 0.0
    var _t0_destination_point = perf_counter_ns()
    for _ in range(N):
        var _r_destination_point = destination_point(0.5, 0.5, 0.5, 0.5)
        _acc_destination_point += Float64(len(_r_destination_point))
    var _t1_destination_point = perf_counter_ns()
    var _ns_destination_point = Float64(_t1_destination_point - _t0_destination_point) / Float64(N)
    print("MOJO_TIMING earth::destination_point", _ns_destination_point, _acc_destination_point)
    var _acc_bounding_box: Float64 = 0.0
    var _t0_bounding_box = perf_counter_ns()
    for _ in range(N):
        var _r_bounding_box = bounding_box(0.5, 0.5, 0.5)
        _acc_bounding_box += Float64(len(_r_bounding_box))
    var _t1_bounding_box = perf_counter_ns()
    var _ns_bounding_box = Float64(_t1_bounding_box - _t0_bounding_box) / Float64(N)
    print("MOJO_TIMING earth::bounding_box", _ns_bounding_box, _acc_bounding_box)
    var _acc_cross_track_distance: Float64 = 0.0
    var _t0_cross_track_distance = perf_counter_ns()
    for _ in range(N):
        _acc_cross_track_distance += cross_track_distance(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_cross_track_distance = perf_counter_ns()
    var _ns_cross_track_distance = Float64(_t1_cross_track_distance - _t0_cross_track_distance) / Float64(N)
    print("MOJO_TIMING earth::cross_track_distance", _ns_cross_track_distance, _acc_cross_track_distance)
