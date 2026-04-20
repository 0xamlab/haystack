"""bench_lidar_mapping.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from lidar_mapping import range_from_time_of_flight, point_density, canopy_height_model, leaf_area_index_from_lidar, ground_filter_threshold, beam_divergence_footprint, pulse_return_intensity, scan_line_spacing, vertical_accuracy, surface_roughness_lidar
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

    var _acc_range_from_time_of_flight: Float64 = 0.0
    var _t0_range_from_time_of_flight = perf_counter_ns()
    for _ in range(N):
        _acc_range_from_time_of_flight += range_from_time_of_flight(0.5)
    var _t1_range_from_time_of_flight = perf_counter_ns()
    var _ns_range_from_time_of_flight = Float64(_t1_range_from_time_of_flight - _t0_range_from_time_of_flight) / Float64(N)
    print("MOJO_TIMING lidar_mapping::range_from_time_of_flight", _ns_range_from_time_of_flight, _acc_range_from_time_of_flight)
    var _acc_point_density: Float64 = 0.0
    var _t0_point_density = perf_counter_ns()
    for _ in range(N):
        _acc_point_density += point_density(0.5, 0.5)
    var _t1_point_density = perf_counter_ns()
    var _ns_point_density = Float64(_t1_point_density - _t0_point_density) / Float64(N)
    print("MOJO_TIMING lidar_mapping::point_density", _ns_point_density, _acc_point_density)
    var _acc_canopy_height_model: Float64 = 0.0
    var _t0_canopy_height_model = perf_counter_ns()
    for _ in range(N):
        _acc_canopy_height_model += canopy_height_model(0.5, 0.5)
    var _t1_canopy_height_model = perf_counter_ns()
    var _ns_canopy_height_model = Float64(_t1_canopy_height_model - _t0_canopy_height_model) / Float64(N)
    print("MOJO_TIMING lidar_mapping::canopy_height_model", _ns_canopy_height_model, _acc_canopy_height_model)
    var _acc_leaf_area_index_from_lidar: Float64 = 0.0
    var _t0_leaf_area_index_from_lidar = perf_counter_ns()
    for _ in range(N):
        _acc_leaf_area_index_from_lidar += leaf_area_index_from_lidar(0.5, 0.5)
    var _t1_leaf_area_index_from_lidar = perf_counter_ns()
    var _ns_leaf_area_index_from_lidar = Float64(_t1_leaf_area_index_from_lidar - _t0_leaf_area_index_from_lidar) / Float64(N)
    print("MOJO_TIMING lidar_mapping::leaf_area_index_from_lidar", _ns_leaf_area_index_from_lidar, _acc_leaf_area_index_from_lidar)
    var _acc_ground_filter_threshold: Float64 = 0.0
    var _t0_ground_filter_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_ground_filter_threshold += ground_filter_threshold(0.5, 0.5)
    var _t1_ground_filter_threshold = perf_counter_ns()
    var _ns_ground_filter_threshold = Float64(_t1_ground_filter_threshold - _t0_ground_filter_threshold) / Float64(N)
    print("MOJO_TIMING lidar_mapping::ground_filter_threshold", _ns_ground_filter_threshold, _acc_ground_filter_threshold)
    var _acc_beam_divergence_footprint: Float64 = 0.0
    var _t0_beam_divergence_footprint = perf_counter_ns()
    for _ in range(N):
        _acc_beam_divergence_footprint += beam_divergence_footprint(0.5, 0.5)
    var _t1_beam_divergence_footprint = perf_counter_ns()
    var _ns_beam_divergence_footprint = Float64(_t1_beam_divergence_footprint - _t0_beam_divergence_footprint) / Float64(N)
    print("MOJO_TIMING lidar_mapping::beam_divergence_footprint", _ns_beam_divergence_footprint, _acc_beam_divergence_footprint)
    var _acc_pulse_return_intensity: Float64 = 0.0
    var _t0_pulse_return_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_pulse_return_intensity += pulse_return_intensity(0.5, 0.5, 0.5)
    var _t1_pulse_return_intensity = perf_counter_ns()
    var _ns_pulse_return_intensity = Float64(_t1_pulse_return_intensity - _t0_pulse_return_intensity) / Float64(N)
    print("MOJO_TIMING lidar_mapping::pulse_return_intensity", _ns_pulse_return_intensity, _acc_pulse_return_intensity)
    var _acc_scan_line_spacing: Float64 = 0.0
    var _t0_scan_line_spacing = perf_counter_ns()
    for _ in range(N):
        _acc_scan_line_spacing += scan_line_spacing(0.5, 0.5, 0.5)
    var _t1_scan_line_spacing = perf_counter_ns()
    var _ns_scan_line_spacing = Float64(_t1_scan_line_spacing - _t0_scan_line_spacing) / Float64(N)
    print("MOJO_TIMING lidar_mapping::scan_line_spacing", _ns_scan_line_spacing, _acc_scan_line_spacing)
    var _acc_vertical_accuracy: Float64 = 0.0
    var _t0_vertical_accuracy = perf_counter_ns()
    for _ in range(N):
        _acc_vertical_accuracy += vertical_accuracy(0.5, 0.5)
    var _t1_vertical_accuracy = perf_counter_ns()
    var _ns_vertical_accuracy = Float64(_t1_vertical_accuracy - _t0_vertical_accuracy) / Float64(N)
    print("MOJO_TIMING lidar_mapping::vertical_accuracy", _ns_vertical_accuracy, _acc_vertical_accuracy)
    var _acc_surface_roughness_lidar: Float64 = 0.0
    var _t0_surface_roughness_lidar = perf_counter_ns()
    for _ in range(N):
        _acc_surface_roughness_lidar += surface_roughness_lidar(0.5, 0.5)
    var _t1_surface_roughness_lidar = perf_counter_ns()
    var _ns_surface_roughness_lidar = Float64(_t1_surface_roughness_lidar - _t0_surface_roughness_lidar) / Float64(N)
    print("MOJO_TIMING lidar_mapping::surface_roughness_lidar", _ns_surface_roughness_lidar, _acc_surface_roughness_lidar)
