"""bench_cartography.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cartography import scale_factor, representative_fraction, ground_distance_from_map, map_distance_from_ground, latitude_to_utm_zone, mercator_y, equirectangular_x, equirectangular_y, great_circle_distance, map_area_at_scale, contour_interval_suggestion, declination_correction
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

    var _acc_scale_factor: Float64 = 0.0
    var _t0_scale_factor = perf_counter_ns()
    for _ in range(N):
        _acc_scale_factor += scale_factor(0.5, 0.5)
    var _t1_scale_factor = perf_counter_ns()
    var _ns_scale_factor = Float64(_t1_scale_factor - _t0_scale_factor) / Float64(N)
    print("MOJO_TIMING cartography::scale_factor", _ns_scale_factor, _acc_scale_factor)
    var _result_scale_factor = scale_factor(0.5, 0.5)
    var _summary_scale_factor = _summary_float64(_result_scale_factor)
    print("MOJO_RESULT cartography::scale_factor", _summary_scale_factor)
    var _acc_representative_fraction: Float64 = 0.0
    var _t0_representative_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_representative_fraction += representative_fraction(0.5, 0.5)
    var _t1_representative_fraction = perf_counter_ns()
    var _ns_representative_fraction = Float64(_t1_representative_fraction - _t0_representative_fraction) / Float64(N)
    print("MOJO_TIMING cartography::representative_fraction", _ns_representative_fraction, _acc_representative_fraction)
    var _result_representative_fraction = representative_fraction(0.5, 0.5)
    var _summary_representative_fraction = _summary_float64(_result_representative_fraction)
    print("MOJO_RESULT cartography::representative_fraction", _summary_representative_fraction)
    var _acc_ground_distance_from_map: Float64 = 0.0
    var _t0_ground_distance_from_map = perf_counter_ns()
    for _ in range(N):
        _acc_ground_distance_from_map += ground_distance_from_map(0.5, 0.5)
    var _t1_ground_distance_from_map = perf_counter_ns()
    var _ns_ground_distance_from_map = Float64(_t1_ground_distance_from_map - _t0_ground_distance_from_map) / Float64(N)
    print("MOJO_TIMING cartography::ground_distance_from_map", _ns_ground_distance_from_map, _acc_ground_distance_from_map)
    var _result_ground_distance_from_map = ground_distance_from_map(0.5, 0.5)
    var _summary_ground_distance_from_map = _summary_float64(_result_ground_distance_from_map)
    print("MOJO_RESULT cartography::ground_distance_from_map", _summary_ground_distance_from_map)
    var _acc_map_distance_from_ground: Float64 = 0.0
    var _t0_map_distance_from_ground = perf_counter_ns()
    for _ in range(N):
        _acc_map_distance_from_ground += map_distance_from_ground(0.5, 0.5)
    var _t1_map_distance_from_ground = perf_counter_ns()
    var _ns_map_distance_from_ground = Float64(_t1_map_distance_from_ground - _t0_map_distance_from_ground) / Float64(N)
    print("MOJO_TIMING cartography::map_distance_from_ground", _ns_map_distance_from_ground, _acc_map_distance_from_ground)
    var _result_map_distance_from_ground = map_distance_from_ground(0.5, 0.5)
    var _summary_map_distance_from_ground = _summary_float64(_result_map_distance_from_ground)
    print("MOJO_RESULT cartography::map_distance_from_ground", _summary_map_distance_from_ground)
    var _acc_latitude_to_utm_zone: Float64 = 0.0
    var _t0_latitude_to_utm_zone = perf_counter_ns()
    for _ in range(N):
        _acc_latitude_to_utm_zone += Float64(latitude_to_utm_zone(0.5))
    var _t1_latitude_to_utm_zone = perf_counter_ns()
    var _ns_latitude_to_utm_zone = Float64(_t1_latitude_to_utm_zone - _t0_latitude_to_utm_zone) / Float64(N)
    print("MOJO_TIMING cartography::latitude_to_utm_zone", _ns_latitude_to_utm_zone, _acc_latitude_to_utm_zone)
    var _result_latitude_to_utm_zone = latitude_to_utm_zone(0.5)
    var _summary_latitude_to_utm_zone = _summary_int(_result_latitude_to_utm_zone)
    print("MOJO_RESULT cartography::latitude_to_utm_zone", _summary_latitude_to_utm_zone)
    var _acc_mercator_y: Float64 = 0.0
    var _t0_mercator_y = perf_counter_ns()
    for _ in range(N):
        _acc_mercator_y += mercator_y(0.5)
    var _t1_mercator_y = perf_counter_ns()
    var _ns_mercator_y = Float64(_t1_mercator_y - _t0_mercator_y) / Float64(N)
    print("MOJO_TIMING cartography::mercator_y", _ns_mercator_y, _acc_mercator_y)
    var _result_mercator_y = mercator_y(0.5)
    var _summary_mercator_y = _summary_float64(_result_mercator_y)
    print("MOJO_RESULT cartography::mercator_y", _summary_mercator_y)
    var _acc_equirectangular_x: Float64 = 0.0
    var _t0_equirectangular_x = perf_counter_ns()
    for _ in range(N):
        _acc_equirectangular_x += equirectangular_x(0.5, 0.5, 0.5)
    var _t1_equirectangular_x = perf_counter_ns()
    var _ns_equirectangular_x = Float64(_t1_equirectangular_x - _t0_equirectangular_x) / Float64(N)
    print("MOJO_TIMING cartography::equirectangular_x", _ns_equirectangular_x, _acc_equirectangular_x)
    var _result_equirectangular_x = equirectangular_x(0.5, 0.5, 0.5)
    var _summary_equirectangular_x = _summary_float64(_result_equirectangular_x)
    print("MOJO_RESULT cartography::equirectangular_x", _summary_equirectangular_x)
    var _acc_equirectangular_y: Float64 = 0.0
    var _t0_equirectangular_y = perf_counter_ns()
    for _ in range(N):
        _acc_equirectangular_y += equirectangular_y(0.5)
    var _t1_equirectangular_y = perf_counter_ns()
    var _ns_equirectangular_y = Float64(_t1_equirectangular_y - _t0_equirectangular_y) / Float64(N)
    print("MOJO_TIMING cartography::equirectangular_y", _ns_equirectangular_y, _acc_equirectangular_y)
    var _result_equirectangular_y = equirectangular_y(0.5)
    var _summary_equirectangular_y = _summary_float64(_result_equirectangular_y)
    print("MOJO_RESULT cartography::equirectangular_y", _summary_equirectangular_y)
    var _acc_great_circle_distance: Float64 = 0.0
    var _t0_great_circle_distance = perf_counter_ns()
    for _ in range(N):
        _acc_great_circle_distance += great_circle_distance(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_great_circle_distance = perf_counter_ns()
    var _ns_great_circle_distance = Float64(_t1_great_circle_distance - _t0_great_circle_distance) / Float64(N)
    print("MOJO_TIMING cartography::great_circle_distance", _ns_great_circle_distance, _acc_great_circle_distance)
    var _result_great_circle_distance = great_circle_distance(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_great_circle_distance = _summary_float64(_result_great_circle_distance)
    print("MOJO_RESULT cartography::great_circle_distance", _summary_great_circle_distance)
    var _acc_map_area_at_scale: Float64 = 0.0
    var _t0_map_area_at_scale = perf_counter_ns()
    for _ in range(N):
        _acc_map_area_at_scale += map_area_at_scale(0.5, 0.5)
    var _t1_map_area_at_scale = perf_counter_ns()
    var _ns_map_area_at_scale = Float64(_t1_map_area_at_scale - _t0_map_area_at_scale) / Float64(N)
    print("MOJO_TIMING cartography::map_area_at_scale", _ns_map_area_at_scale, _acc_map_area_at_scale)
    var _result_map_area_at_scale = map_area_at_scale(0.5, 0.5)
    var _summary_map_area_at_scale = _summary_float64(_result_map_area_at_scale)
    print("MOJO_RESULT cartography::map_area_at_scale", _summary_map_area_at_scale)
    var _acc_contour_interval_suggestion: Float64 = 0.0
    var _t0_contour_interval_suggestion = perf_counter_ns()
    for _ in range(N):
        _acc_contour_interval_suggestion += contour_interval_suggestion(0.5, 0.5)
    var _t1_contour_interval_suggestion = perf_counter_ns()
    var _ns_contour_interval_suggestion = Float64(_t1_contour_interval_suggestion - _t0_contour_interval_suggestion) / Float64(N)
    print("MOJO_TIMING cartography::contour_interval_suggestion", _ns_contour_interval_suggestion, _acc_contour_interval_suggestion)
    var _result_contour_interval_suggestion = contour_interval_suggestion(0.5, 0.5)
    var _summary_contour_interval_suggestion = _summary_float64(_result_contour_interval_suggestion)
    print("MOJO_RESULT cartography::contour_interval_suggestion", _summary_contour_interval_suggestion)
    var _acc_declination_correction: Float64 = 0.0
    var _t0_declination_correction = perf_counter_ns()
    for _ in range(N):
        _acc_declination_correction += declination_correction(0.5, 0.5)
    var _t1_declination_correction = perf_counter_ns()
    var _ns_declination_correction = Float64(_t1_declination_correction - _t0_declination_correction) / Float64(N)
    print("MOJO_TIMING cartography::declination_correction", _ns_declination_correction, _acc_declination_correction)
    var _result_declination_correction = declination_correction(0.5, 0.5)
    var _summary_declination_correction = _summary_float64(_result_declination_correction)
    print("MOJO_RESULT cartography::declination_correction", _summary_declination_correction)
