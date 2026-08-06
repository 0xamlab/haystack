"""bench_lidar_mapping.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from lidar_mapping import range_from_time_of_flight, point_density, canopy_height_model, leaf_area_index_from_lidar, ground_filter_threshold, beam_divergence_footprint, pulse_return_intensity, scan_line_spacing, vertical_accuracy, surface_roughness_lidar
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_range_from_time_of_flight: Float64 = 0.0
    var _t0_range_from_time_of_flight = perf_counter_ns()
    for _ in range(N):
        _acc_range_from_time_of_flight += range_from_time_of_flight(0.5)
    var _t1_range_from_time_of_flight = perf_counter_ns()
    var _ns_range_from_time_of_flight = Float64(_t1_range_from_time_of_flight - _t0_range_from_time_of_flight) / Float64(N)
    print("MOJO_TIMING lidar_mapping::range_from_time_of_flight", _ns_range_from_time_of_flight, _acc_range_from_time_of_flight)
    var _result_range_from_time_of_flight = range_from_time_of_flight(0.5)
    var _summary_range_from_time_of_flight = _summary_float64(_result_range_from_time_of_flight)
    print("MOJO_RESULT lidar_mapping::range_from_time_of_flight", _summary_range_from_time_of_flight)
    var _acc_point_density: Float64 = 0.0
    var _t0_point_density = perf_counter_ns()
    for _ in range(N):
        _acc_point_density += point_density(0.5, 0.5)
    var _t1_point_density = perf_counter_ns()
    var _ns_point_density = Float64(_t1_point_density - _t0_point_density) / Float64(N)
    print("MOJO_TIMING lidar_mapping::point_density", _ns_point_density, _acc_point_density)
    var _result_point_density = point_density(0.5, 0.5)
    var _summary_point_density = _summary_float64(_result_point_density)
    print("MOJO_RESULT lidar_mapping::point_density", _summary_point_density)
    var _acc_canopy_height_model: Float64 = 0.0
    var _t0_canopy_height_model = perf_counter_ns()
    for _ in range(N):
        _acc_canopy_height_model += canopy_height_model(0.5, 0.5)
    var _t1_canopy_height_model = perf_counter_ns()
    var _ns_canopy_height_model = Float64(_t1_canopy_height_model - _t0_canopy_height_model) / Float64(N)
    print("MOJO_TIMING lidar_mapping::canopy_height_model", _ns_canopy_height_model, _acc_canopy_height_model)
    var _result_canopy_height_model = canopy_height_model(0.5, 0.5)
    var _summary_canopy_height_model = _summary_float64(_result_canopy_height_model)
    print("MOJO_RESULT lidar_mapping::canopy_height_model", _summary_canopy_height_model)
    var _acc_leaf_area_index_from_lidar: Float64 = 0.0
    var _t0_leaf_area_index_from_lidar = perf_counter_ns()
    for _ in range(N):
        _acc_leaf_area_index_from_lidar += leaf_area_index_from_lidar(0.5, 0.5)
    var _t1_leaf_area_index_from_lidar = perf_counter_ns()
    var _ns_leaf_area_index_from_lidar = Float64(_t1_leaf_area_index_from_lidar - _t0_leaf_area_index_from_lidar) / Float64(N)
    print("MOJO_TIMING lidar_mapping::leaf_area_index_from_lidar", _ns_leaf_area_index_from_lidar, _acc_leaf_area_index_from_lidar)
    var _result_leaf_area_index_from_lidar = leaf_area_index_from_lidar(0.5, 0.5)
    var _summary_leaf_area_index_from_lidar = _summary_float64(_result_leaf_area_index_from_lidar)
    print("MOJO_RESULT lidar_mapping::leaf_area_index_from_lidar", _summary_leaf_area_index_from_lidar)
    var _acc_ground_filter_threshold: Float64 = 0.0
    var _t0_ground_filter_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_ground_filter_threshold += ground_filter_threshold(0.5, 0.5)
    var _t1_ground_filter_threshold = perf_counter_ns()
    var _ns_ground_filter_threshold = Float64(_t1_ground_filter_threshold - _t0_ground_filter_threshold) / Float64(N)
    print("MOJO_TIMING lidar_mapping::ground_filter_threshold", _ns_ground_filter_threshold, _acc_ground_filter_threshold)
    var _result_ground_filter_threshold = ground_filter_threshold(0.5, 0.5)
    var _summary_ground_filter_threshold = _summary_float64(_result_ground_filter_threshold)
    print("MOJO_RESULT lidar_mapping::ground_filter_threshold", _summary_ground_filter_threshold)
    var _acc_beam_divergence_footprint: Float64 = 0.0
    var _t0_beam_divergence_footprint = perf_counter_ns()
    for _ in range(N):
        _acc_beam_divergence_footprint += beam_divergence_footprint(0.5, 0.5)
    var _t1_beam_divergence_footprint = perf_counter_ns()
    var _ns_beam_divergence_footprint = Float64(_t1_beam_divergence_footprint - _t0_beam_divergence_footprint) / Float64(N)
    print("MOJO_TIMING lidar_mapping::beam_divergence_footprint", _ns_beam_divergence_footprint, _acc_beam_divergence_footprint)
    var _result_beam_divergence_footprint = beam_divergence_footprint(0.5, 0.5)
    var _summary_beam_divergence_footprint = _summary_float64(_result_beam_divergence_footprint)
    print("MOJO_RESULT lidar_mapping::beam_divergence_footprint", _summary_beam_divergence_footprint)
    var _acc_pulse_return_intensity: Float64 = 0.0
    var _t0_pulse_return_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_pulse_return_intensity += pulse_return_intensity(0.5, 0.5, 0.5)
    var _t1_pulse_return_intensity = perf_counter_ns()
    var _ns_pulse_return_intensity = Float64(_t1_pulse_return_intensity - _t0_pulse_return_intensity) / Float64(N)
    print("MOJO_TIMING lidar_mapping::pulse_return_intensity", _ns_pulse_return_intensity, _acc_pulse_return_intensity)
    var _result_pulse_return_intensity = pulse_return_intensity(0.5, 0.5, 0.5)
    var _summary_pulse_return_intensity = _summary_float64(_result_pulse_return_intensity)
    print("MOJO_RESULT lidar_mapping::pulse_return_intensity", _summary_pulse_return_intensity)
    var _acc_scan_line_spacing: Float64 = 0.0
    var _t0_scan_line_spacing = perf_counter_ns()
    for _ in range(N):
        _acc_scan_line_spacing += scan_line_spacing(0.5, 0.5, 0.5)
    var _t1_scan_line_spacing = perf_counter_ns()
    var _ns_scan_line_spacing = Float64(_t1_scan_line_spacing - _t0_scan_line_spacing) / Float64(N)
    print("MOJO_TIMING lidar_mapping::scan_line_spacing", _ns_scan_line_spacing, _acc_scan_line_spacing)
    var _result_scan_line_spacing = scan_line_spacing(0.5, 0.5, 0.5)
    var _summary_scan_line_spacing = _summary_float64(_result_scan_line_spacing)
    print("MOJO_RESULT lidar_mapping::scan_line_spacing", _summary_scan_line_spacing)
    var _acc_vertical_accuracy: Float64 = 0.0
    var _t0_vertical_accuracy = perf_counter_ns()
    for _ in range(N):
        _acc_vertical_accuracy += vertical_accuracy(0.5, 0.5)
    var _t1_vertical_accuracy = perf_counter_ns()
    var _ns_vertical_accuracy = Float64(_t1_vertical_accuracy - _t0_vertical_accuracy) / Float64(N)
    print("MOJO_TIMING lidar_mapping::vertical_accuracy", _ns_vertical_accuracy, _acc_vertical_accuracy)
    var _result_vertical_accuracy = vertical_accuracy(0.5, 0.5)
    var _summary_vertical_accuracy = _summary_float64(_result_vertical_accuracy)
    print("MOJO_RESULT lidar_mapping::vertical_accuracy", _summary_vertical_accuracy)
    var _acc_surface_roughness_lidar: Float64 = 0.0
    var _t0_surface_roughness_lidar = perf_counter_ns()
    for _ in range(N):
        _acc_surface_roughness_lidar += surface_roughness_lidar(0.5, 0.5)
    var _t1_surface_roughness_lidar = perf_counter_ns()
    var _ns_surface_roughness_lidar = Float64(_t1_surface_roughness_lidar - _t0_surface_roughness_lidar) / Float64(N)
    print("MOJO_TIMING lidar_mapping::surface_roughness_lidar", _ns_surface_roughness_lidar, _acc_surface_roughness_lidar)
    var _result_surface_roughness_lidar = surface_roughness_lidar(0.5, 0.5)
    var _summary_surface_roughness_lidar = _summary_float64(_result_surface_roughness_lidar)
    print("MOJO_RESULT lidar_mapping::surface_roughness_lidar", _summary_surface_roughness_lidar)
