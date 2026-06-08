"""bench_geodesy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from geodesy import haversine_distance, vincenty_distance, initial_bearing, destination_point, midpoint, cross_track_distance, along_track_distance, geodetic_to_ecef, ecef_to_geodetic, rhumb_distance
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

    var _acc_haversine_distance: Float64 = 0.0
    var _t0_haversine_distance = perf_counter_ns()
    for _ in range(N):
        _acc_haversine_distance += haversine_distance(0.5, 0.5, 0.5, 0.5)
    var _t1_haversine_distance = perf_counter_ns()
    var _ns_haversine_distance = Float64(_t1_haversine_distance - _t0_haversine_distance) / Float64(N)
    print("MOJO_TIMING geodesy::haversine_distance", _ns_haversine_distance, _acc_haversine_distance)
    var _result_haversine_distance = haversine_distance(0.5, 0.5, 0.5, 0.5)
    var _summary_haversine_distance = _summary_float64(_result_haversine_distance)
    print("MOJO_RESULT geodesy::haversine_distance", _summary_haversine_distance)
    var _acc_vincenty_distance: Float64 = 0.0
    var _t0_vincenty_distance = perf_counter_ns()
    for _ in range(N):
        _acc_vincenty_distance += vincenty_distance(0.5, 0.5, 0.5, 0.5)
    var _t1_vincenty_distance = perf_counter_ns()
    var _ns_vincenty_distance = Float64(_t1_vincenty_distance - _t0_vincenty_distance) / Float64(N)
    print("MOJO_TIMING geodesy::vincenty_distance", _ns_vincenty_distance, _acc_vincenty_distance)
    var _result_vincenty_distance = vincenty_distance(0.5, 0.5, 0.5, 0.5)
    var _summary_vincenty_distance = _summary_float64(_result_vincenty_distance)
    print("MOJO_RESULT geodesy::vincenty_distance", _summary_vincenty_distance)
    var _acc_initial_bearing: Float64 = 0.0
    var _t0_initial_bearing = perf_counter_ns()
    for _ in range(N):
        _acc_initial_bearing += initial_bearing(0.5, 0.5, 0.5, 0.5)
    var _t1_initial_bearing = perf_counter_ns()
    var _ns_initial_bearing = Float64(_t1_initial_bearing - _t0_initial_bearing) / Float64(N)
    print("MOJO_TIMING geodesy::initial_bearing", _ns_initial_bearing, _acc_initial_bearing)
    var _result_initial_bearing = initial_bearing(0.5, 0.5, 0.5, 0.5)
    var _summary_initial_bearing = _summary_float64(_result_initial_bearing)
    print("MOJO_RESULT geodesy::initial_bearing", _summary_initial_bearing)
    var _acc_destination_point: Float64 = 0.0
    var _t0_destination_point = perf_counter_ns()
    for _ in range(N):
        var _r_destination_point = destination_point(0.5, 0.5, 0.5, 0.5)
        _acc_destination_point += Float64(len(_r_destination_point))
    var _t1_destination_point = perf_counter_ns()
    var _ns_destination_point = Float64(_t1_destination_point - _t0_destination_point) / Float64(N)
    print("MOJO_TIMING geodesy::destination_point", _ns_destination_point, _acc_destination_point)
    var _result_destination_point = destination_point(0.5, 0.5, 0.5, 0.5)
    var _summary_destination_point = _summary_list_float64(_result_destination_point)
    print("MOJO_RESULT geodesy::destination_point", _summary_destination_point)
    var _acc_midpoint: Float64 = 0.0
    var _t0_midpoint = perf_counter_ns()
    for _ in range(N):
        var _r_midpoint = midpoint(0.5, 0.5, 0.5, 0.5)
        _acc_midpoint += Float64(len(_r_midpoint))
    var _t1_midpoint = perf_counter_ns()
    var _ns_midpoint = Float64(_t1_midpoint - _t0_midpoint) / Float64(N)
    print("MOJO_TIMING geodesy::midpoint", _ns_midpoint, _acc_midpoint)
    var _result_midpoint = midpoint(0.5, 0.5, 0.5, 0.5)
    var _summary_midpoint = _summary_list_float64(_result_midpoint)
    print("MOJO_RESULT geodesy::midpoint", _summary_midpoint)
    var _acc_cross_track_distance: Float64 = 0.0
    var _t0_cross_track_distance = perf_counter_ns()
    for _ in range(N):
        _acc_cross_track_distance += cross_track_distance(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_cross_track_distance = perf_counter_ns()
    var _ns_cross_track_distance = Float64(_t1_cross_track_distance - _t0_cross_track_distance) / Float64(N)
    print("MOJO_TIMING geodesy::cross_track_distance", _ns_cross_track_distance, _acc_cross_track_distance)
    var _result_cross_track_distance = cross_track_distance(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_cross_track_distance = _summary_float64(_result_cross_track_distance)
    print("MOJO_RESULT geodesy::cross_track_distance", _summary_cross_track_distance)
    var _acc_along_track_distance: Float64 = 0.0
    var _t0_along_track_distance = perf_counter_ns()
    for _ in range(N):
        _acc_along_track_distance += along_track_distance(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_along_track_distance = perf_counter_ns()
    var _ns_along_track_distance = Float64(_t1_along_track_distance - _t0_along_track_distance) / Float64(N)
    print("MOJO_TIMING geodesy::along_track_distance", _ns_along_track_distance, _acc_along_track_distance)
    var _result_along_track_distance = along_track_distance(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_along_track_distance = _summary_float64(_result_along_track_distance)
    print("MOJO_RESULT geodesy::along_track_distance", _summary_along_track_distance)
    var _acc_geodetic_to_ecef: Float64 = 0.0
    var _t0_geodetic_to_ecef = perf_counter_ns()
    for _ in range(N):
        var _r_geodetic_to_ecef = geodetic_to_ecef(0.5, 0.5, 0.5)
        _acc_geodetic_to_ecef += Float64(len(_r_geodetic_to_ecef))
    var _t1_geodetic_to_ecef = perf_counter_ns()
    var _ns_geodetic_to_ecef = Float64(_t1_geodetic_to_ecef - _t0_geodetic_to_ecef) / Float64(N)
    print("MOJO_TIMING geodesy::geodetic_to_ecef", _ns_geodetic_to_ecef, _acc_geodetic_to_ecef)
    var _result_geodetic_to_ecef = geodetic_to_ecef(0.5, 0.5, 0.5)
    var _summary_geodetic_to_ecef = _summary_list_float64(_result_geodetic_to_ecef)
    print("MOJO_RESULT geodesy::geodetic_to_ecef", _summary_geodetic_to_ecef)
    var _acc_ecef_to_geodetic: Float64 = 0.0
    var _t0_ecef_to_geodetic = perf_counter_ns()
    for _ in range(N):
        var _r_ecef_to_geodetic = ecef_to_geodetic(0.5, 0.5, 0.5)
        _acc_ecef_to_geodetic += Float64(len(_r_ecef_to_geodetic))
    var _t1_ecef_to_geodetic = perf_counter_ns()
    var _ns_ecef_to_geodetic = Float64(_t1_ecef_to_geodetic - _t0_ecef_to_geodetic) / Float64(N)
    print("MOJO_TIMING geodesy::ecef_to_geodetic", _ns_ecef_to_geodetic, _acc_ecef_to_geodetic)
    var _result_ecef_to_geodetic = ecef_to_geodetic(0.5, 0.5, 0.5)
    var _summary_ecef_to_geodetic = _summary_list_float64(_result_ecef_to_geodetic)
    print("MOJO_RESULT geodesy::ecef_to_geodetic", _summary_ecef_to_geodetic)
    var _acc_rhumb_distance: Float64 = 0.0
    var _t0_rhumb_distance = perf_counter_ns()
    for _ in range(N):
        _acc_rhumb_distance += rhumb_distance(0.5, 0.5, 0.5, 0.5)
    var _t1_rhumb_distance = perf_counter_ns()
    var _ns_rhumb_distance = Float64(_t1_rhumb_distance - _t0_rhumb_distance) / Float64(N)
    print("MOJO_TIMING geodesy::rhumb_distance", _ns_rhumb_distance, _acc_rhumb_distance)
    var _result_rhumb_distance = rhumb_distance(0.5, 0.5, 0.5, 0.5)
    var _summary_rhumb_distance = _summary_float64(_result_rhumb_distance)
    print("MOJO_RESULT geodesy::rhumb_distance", _summary_rhumb_distance)
