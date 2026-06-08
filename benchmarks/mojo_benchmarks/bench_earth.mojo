"""bench_earth.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from earth import deg_to_rad, rad_to_deg, is_valid_coordinate, distance_on_unit_sphere, haversine, bearing, midpoint, destination_point, bounding_box, cross_track_distance
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

    var _acc_deg_to_rad: Float64 = 0.0
    var _t0_deg_to_rad = perf_counter_ns()
    for _ in range(N):
        _acc_deg_to_rad += deg_to_rad(0.5)
    var _t1_deg_to_rad = perf_counter_ns()
    var _ns_deg_to_rad = Float64(_t1_deg_to_rad - _t0_deg_to_rad) / Float64(N)
    print("MOJO_TIMING earth::deg_to_rad", _ns_deg_to_rad, _acc_deg_to_rad)
    var _result_deg_to_rad = deg_to_rad(0.5)
    var _summary_deg_to_rad = _summary_float64(_result_deg_to_rad)
    print("MOJO_RESULT earth::deg_to_rad", _summary_deg_to_rad)
    var _acc_rad_to_deg: Float64 = 0.0
    var _t0_rad_to_deg = perf_counter_ns()
    for _ in range(N):
        _acc_rad_to_deg += rad_to_deg(0.5)
    var _t1_rad_to_deg = perf_counter_ns()
    var _ns_rad_to_deg = Float64(_t1_rad_to_deg - _t0_rad_to_deg) / Float64(N)
    print("MOJO_TIMING earth::rad_to_deg", _ns_rad_to_deg, _acc_rad_to_deg)
    var _result_rad_to_deg = rad_to_deg(0.5)
    var _summary_rad_to_deg = _summary_float64(_result_rad_to_deg)
    print("MOJO_RESULT earth::rad_to_deg", _summary_rad_to_deg)
    var _acc_is_valid_coordinate: Float64 = 0.0
    var _t0_is_valid_coordinate = perf_counter_ns()
    for _ in range(N):
        _acc_is_valid_coordinate += Float64(is_valid_coordinate(0.5, 0.5))
    var _t1_is_valid_coordinate = perf_counter_ns()
    var _ns_is_valid_coordinate = Float64(_t1_is_valid_coordinate - _t0_is_valid_coordinate) / Float64(N)
    print("MOJO_TIMING earth::is_valid_coordinate", _ns_is_valid_coordinate, _acc_is_valid_coordinate)
    var _result_is_valid_coordinate = is_valid_coordinate(0.5, 0.5)
    var _summary_is_valid_coordinate = _summary_bool(_result_is_valid_coordinate)
    print("MOJO_RESULT earth::is_valid_coordinate", _summary_is_valid_coordinate)
    var _acc_distance_on_unit_sphere: Float64 = 0.0
    var _t0_distance_on_unit_sphere = perf_counter_ns()
    for _ in range(N):
        _acc_distance_on_unit_sphere += distance_on_unit_sphere(0.5, 0.5, 0.5, 0.5)
    var _t1_distance_on_unit_sphere = perf_counter_ns()
    var _ns_distance_on_unit_sphere = Float64(_t1_distance_on_unit_sphere - _t0_distance_on_unit_sphere) / Float64(N)
    print("MOJO_TIMING earth::distance_on_unit_sphere", _ns_distance_on_unit_sphere, _acc_distance_on_unit_sphere)
    var _result_distance_on_unit_sphere = distance_on_unit_sphere(0.5, 0.5, 0.5, 0.5)
    var _summary_distance_on_unit_sphere = _summary_float64(_result_distance_on_unit_sphere)
    print("MOJO_RESULT earth::distance_on_unit_sphere", _summary_distance_on_unit_sphere)
    var _acc_haversine: Float64 = 0.0
    var _t0_haversine = perf_counter_ns()
    for _ in range(N):
        _acc_haversine += haversine(0.5, 0.5, 0.5, 0.5)
    var _t1_haversine = perf_counter_ns()
    var _ns_haversine = Float64(_t1_haversine - _t0_haversine) / Float64(N)
    print("MOJO_TIMING earth::haversine", _ns_haversine, _acc_haversine)
    var _result_haversine = haversine(0.5, 0.5, 0.5, 0.5)
    var _summary_haversine = _summary_float64(_result_haversine)
    print("MOJO_RESULT earth::haversine", _summary_haversine)
    var _acc_bearing: Float64 = 0.0
    var _t0_bearing = perf_counter_ns()
    for _ in range(N):
        _acc_bearing += bearing(0.5, 0.5, 0.5, 0.5)
    var _t1_bearing = perf_counter_ns()
    var _ns_bearing = Float64(_t1_bearing - _t0_bearing) / Float64(N)
    print("MOJO_TIMING earth::bearing", _ns_bearing, _acc_bearing)
    var _result_bearing = bearing(0.5, 0.5, 0.5, 0.5)
    var _summary_bearing = _summary_float64(_result_bearing)
    print("MOJO_RESULT earth::bearing", _summary_bearing)
    var _acc_midpoint: Float64 = 0.0
    var _t0_midpoint = perf_counter_ns()
    for _ in range(N):
        var _r_midpoint = midpoint(0.5, 0.5, 0.5, 0.5)
        _acc_midpoint += Float64(len(_r_midpoint))
    var _t1_midpoint = perf_counter_ns()
    var _ns_midpoint = Float64(_t1_midpoint - _t0_midpoint) / Float64(N)
    print("MOJO_TIMING earth::midpoint", _ns_midpoint, _acc_midpoint)
    var _result_midpoint = midpoint(0.5, 0.5, 0.5, 0.5)
    var _summary_midpoint = _summary_list_float64(_result_midpoint)
    print("MOJO_RESULT earth::midpoint", _summary_midpoint)
    var _acc_destination_point: Float64 = 0.0
    var _t0_destination_point = perf_counter_ns()
    for _ in range(N):
        var _r_destination_point = destination_point(0.5, 0.5, 0.5, 0.5)
        _acc_destination_point += Float64(len(_r_destination_point))
    var _t1_destination_point = perf_counter_ns()
    var _ns_destination_point = Float64(_t1_destination_point - _t0_destination_point) / Float64(N)
    print("MOJO_TIMING earth::destination_point", _ns_destination_point, _acc_destination_point)
    var _result_destination_point = destination_point(0.5, 0.5, 0.5, 0.5)
    var _summary_destination_point = _summary_list_float64(_result_destination_point)
    print("MOJO_RESULT earth::destination_point", _summary_destination_point)
    var _acc_bounding_box: Float64 = 0.0
    var _t0_bounding_box = perf_counter_ns()
    for _ in range(N):
        var _r_bounding_box = bounding_box(0.5, 0.5, 0.5)
        _acc_bounding_box += Float64(len(_r_bounding_box))
    var _t1_bounding_box = perf_counter_ns()
    var _ns_bounding_box = Float64(_t1_bounding_box - _t0_bounding_box) / Float64(N)
    print("MOJO_TIMING earth::bounding_box", _ns_bounding_box, _acc_bounding_box)
    var _result_bounding_box = bounding_box(0.5, 0.5, 0.5)
    var _summary_bounding_box = _summary_list_float64(_result_bounding_box)
    print("MOJO_RESULT earth::bounding_box", _summary_bounding_box)
    var _acc_cross_track_distance: Float64 = 0.0
    var _t0_cross_track_distance = perf_counter_ns()
    for _ in range(N):
        _acc_cross_track_distance += cross_track_distance(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_cross_track_distance = perf_counter_ns()
    var _ns_cross_track_distance = Float64(_t1_cross_track_distance - _t0_cross_track_distance) / Float64(N)
    print("MOJO_TIMING earth::cross_track_distance", _ns_cross_track_distance, _acc_cross_track_distance)
    var _result_cross_track_distance = cross_track_distance(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_cross_track_distance = _summary_float64(_result_cross_track_distance)
    print("MOJO_RESULT earth::cross_track_distance", _summary_cross_track_distance)
