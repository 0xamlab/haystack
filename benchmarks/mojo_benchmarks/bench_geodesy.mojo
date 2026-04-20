"""bench_geodesy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from geodesy import haversine_distance, vincenty_distance, initial_bearing, destination_point, midpoint, cross_track_distance, along_track_distance, geodetic_to_ecef, ecef_to_geodetic, rhumb_distance
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

    var _acc_haversine_distance: Float64 = 0.0
    var _t0_haversine_distance = perf_counter_ns()
    for _ in range(N):
        _acc_haversine_distance += haversine_distance(0.5, 0.5, 0.5, 0.5)
    var _t1_haversine_distance = perf_counter_ns()
    var _ns_haversine_distance = Float64(_t1_haversine_distance - _t0_haversine_distance) / Float64(N)
    print("MOJO_TIMING geodesy::haversine_distance", _ns_haversine_distance, _acc_haversine_distance)
    var _acc_vincenty_distance: Float64 = 0.0
    var _t0_vincenty_distance = perf_counter_ns()
    for _ in range(N):
        _acc_vincenty_distance += vincenty_distance(0.5, 0.5, 0.5, 0.5)
    var _t1_vincenty_distance = perf_counter_ns()
    var _ns_vincenty_distance = Float64(_t1_vincenty_distance - _t0_vincenty_distance) / Float64(N)
    print("MOJO_TIMING geodesy::vincenty_distance", _ns_vincenty_distance, _acc_vincenty_distance)
    var _acc_initial_bearing: Float64 = 0.0
    var _t0_initial_bearing = perf_counter_ns()
    for _ in range(N):
        _acc_initial_bearing += initial_bearing(0.5, 0.5, 0.5, 0.5)
    var _t1_initial_bearing = perf_counter_ns()
    var _ns_initial_bearing = Float64(_t1_initial_bearing - _t0_initial_bearing) / Float64(N)
    print("MOJO_TIMING geodesy::initial_bearing", _ns_initial_bearing, _acc_initial_bearing)
    var _acc_destination_point: Float64 = 0.0
    var _t0_destination_point = perf_counter_ns()
    for _ in range(N):
        var _r_destination_point = destination_point(0.5, 0.5, 0.5, 0.5)
        _acc_destination_point += Float64(len(_r_destination_point))
    var _t1_destination_point = perf_counter_ns()
    var _ns_destination_point = Float64(_t1_destination_point - _t0_destination_point) / Float64(N)
    print("MOJO_TIMING geodesy::destination_point", _ns_destination_point, _acc_destination_point)
    var _acc_midpoint: Float64 = 0.0
    var _t0_midpoint = perf_counter_ns()
    for _ in range(N):
        var _r_midpoint = midpoint(0.5, 0.5, 0.5, 0.5)
        _acc_midpoint += Float64(len(_r_midpoint))
    var _t1_midpoint = perf_counter_ns()
    var _ns_midpoint = Float64(_t1_midpoint - _t0_midpoint) / Float64(N)
    print("MOJO_TIMING geodesy::midpoint", _ns_midpoint, _acc_midpoint)
    var _acc_cross_track_distance: Float64 = 0.0
    var _t0_cross_track_distance = perf_counter_ns()
    for _ in range(N):
        _acc_cross_track_distance += cross_track_distance(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_cross_track_distance = perf_counter_ns()
    var _ns_cross_track_distance = Float64(_t1_cross_track_distance - _t0_cross_track_distance) / Float64(N)
    print("MOJO_TIMING geodesy::cross_track_distance", _ns_cross_track_distance, _acc_cross_track_distance)
    var _acc_along_track_distance: Float64 = 0.0
    var _t0_along_track_distance = perf_counter_ns()
    for _ in range(N):
        _acc_along_track_distance += along_track_distance(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_along_track_distance = perf_counter_ns()
    var _ns_along_track_distance = Float64(_t1_along_track_distance - _t0_along_track_distance) / Float64(N)
    print("MOJO_TIMING geodesy::along_track_distance", _ns_along_track_distance, _acc_along_track_distance)
    var _acc_geodetic_to_ecef: Float64 = 0.0
    var _t0_geodetic_to_ecef = perf_counter_ns()
    for _ in range(N):
        var _r_geodetic_to_ecef = geodetic_to_ecef(0.5, 0.5, 0.5)
        _acc_geodetic_to_ecef += Float64(len(_r_geodetic_to_ecef))
    var _t1_geodetic_to_ecef = perf_counter_ns()
    var _ns_geodetic_to_ecef = Float64(_t1_geodetic_to_ecef - _t0_geodetic_to_ecef) / Float64(N)
    print("MOJO_TIMING geodesy::geodetic_to_ecef", _ns_geodetic_to_ecef, _acc_geodetic_to_ecef)
    var _acc_ecef_to_geodetic: Float64 = 0.0
    var _t0_ecef_to_geodetic = perf_counter_ns()
    for _ in range(N):
        var _r_ecef_to_geodetic = ecef_to_geodetic(0.5, 0.5, 0.5)
        _acc_ecef_to_geodetic += Float64(len(_r_ecef_to_geodetic))
    var _t1_ecef_to_geodetic = perf_counter_ns()
    var _ns_ecef_to_geodetic = Float64(_t1_ecef_to_geodetic - _t0_ecef_to_geodetic) / Float64(N)
    print("MOJO_TIMING geodesy::ecef_to_geodetic", _ns_ecef_to_geodetic, _acc_ecef_to_geodetic)
    var _acc_rhumb_distance: Float64 = 0.0
    var _t0_rhumb_distance = perf_counter_ns()
    for _ in range(N):
        _acc_rhumb_distance += rhumb_distance(0.5, 0.5, 0.5, 0.5)
    var _t1_rhumb_distance = perf_counter_ns()
    var _ns_rhumb_distance = Float64(_t1_rhumb_distance - _t0_rhumb_distance) / Float64(N)
    print("MOJO_TIMING geodesy::rhumb_distance", _ns_rhumb_distance, _acc_rhumb_distance)
