"""bench_lidar.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from lidar import range_from_tof, point_density, scan_swath_width, footprint_diameter, pulse_repetition_frequency_to_point_rate, ground_sampling_distance, vegetation_index_from_returns, canopy_height, slope_from_elevation, intensity_normalization, overlap_percentage, point_cloud_file_size_mb
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

    var _acc_range_from_tof: Float64 = 0.0
    var _t0_range_from_tof = perf_counter_ns()
    for _ in range(N):
        _acc_range_from_tof += range_from_tof(0.5, 0.5)
    var _t1_range_from_tof = perf_counter_ns()
    var _ns_range_from_tof = Float64(_t1_range_from_tof - _t0_range_from_tof) / Float64(N)
    print("MOJO_TIMING lidar::range_from_tof", _ns_range_from_tof, _acc_range_from_tof)
    var _acc_point_density: Float64 = 0.0
    var _t0_point_density = perf_counter_ns()
    for _ in range(N):
        _acc_point_density += point_density(0.5, 0.5)
    var _t1_point_density = perf_counter_ns()
    var _ns_point_density = Float64(_t1_point_density - _t0_point_density) / Float64(N)
    print("MOJO_TIMING lidar::point_density", _ns_point_density, _acc_point_density)
    var _acc_scan_swath_width: Float64 = 0.0
    var _t0_scan_swath_width = perf_counter_ns()
    for _ in range(N):
        _acc_scan_swath_width += scan_swath_width(0.5, 0.5)
    var _t1_scan_swath_width = perf_counter_ns()
    var _ns_scan_swath_width = Float64(_t1_scan_swath_width - _t0_scan_swath_width) / Float64(N)
    print("MOJO_TIMING lidar::scan_swath_width", _ns_scan_swath_width, _acc_scan_swath_width)
    var _acc_footprint_diameter: Float64 = 0.0
    var _t0_footprint_diameter = perf_counter_ns()
    for _ in range(N):
        _acc_footprint_diameter += footprint_diameter(0.5, 0.5)
    var _t1_footprint_diameter = perf_counter_ns()
    var _ns_footprint_diameter = Float64(_t1_footprint_diameter - _t0_footprint_diameter) / Float64(N)
    print("MOJO_TIMING lidar::footprint_diameter", _ns_footprint_diameter, _acc_footprint_diameter)
    var _acc_pulse_repetition_frequency_to_point_rate: Float64 = 0.0
    var _t0_pulse_repetition_frequency_to_point_rate = perf_counter_ns()
    for _ in range(N):
        _acc_pulse_repetition_frequency_to_point_rate += pulse_repetition_frequency_to_point_rate(0.5, 0.5, 0.5)
    var _t1_pulse_repetition_frequency_to_point_rate = perf_counter_ns()
    var _ns_pulse_repetition_frequency_to_point_rate = Float64(_t1_pulse_repetition_frequency_to_point_rate - _t0_pulse_repetition_frequency_to_point_rate) / Float64(N)
    print("MOJO_TIMING lidar::pulse_repetition_frequency_to_point_rate", _ns_pulse_repetition_frequency_to_point_rate, _acc_pulse_repetition_frequency_to_point_rate)
    var _acc_ground_sampling_distance: Float64 = 0.0
    var _t0_ground_sampling_distance = perf_counter_ns()
    for _ in range(N):
        _acc_ground_sampling_distance += ground_sampling_distance(0.5, 0.5, 0.5)
    var _t1_ground_sampling_distance = perf_counter_ns()
    var _ns_ground_sampling_distance = Float64(_t1_ground_sampling_distance - _t0_ground_sampling_distance) / Float64(N)
    print("MOJO_TIMING lidar::ground_sampling_distance", _ns_ground_sampling_distance, _acc_ground_sampling_distance)
    var _acc_vegetation_index_from_returns: Float64 = 0.0
    var _t0_vegetation_index_from_returns = perf_counter_ns()
    for _ in range(N):
        _acc_vegetation_index_from_returns += vegetation_index_from_returns(0.5, 0.5)
    var _t1_vegetation_index_from_returns = perf_counter_ns()
    var _ns_vegetation_index_from_returns = Float64(_t1_vegetation_index_from_returns - _t0_vegetation_index_from_returns) / Float64(N)
    print("MOJO_TIMING lidar::vegetation_index_from_returns", _ns_vegetation_index_from_returns, _acc_vegetation_index_from_returns)
    var _acc_canopy_height: Float64 = 0.0
    var _t0_canopy_height = perf_counter_ns()
    for _ in range(N):
        _acc_canopy_height += canopy_height(0.5, 0.5)
    var _t1_canopy_height = perf_counter_ns()
    var _ns_canopy_height = Float64(_t1_canopy_height - _t0_canopy_height) / Float64(N)
    print("MOJO_TIMING lidar::canopy_height", _ns_canopy_height, _acc_canopy_height)
    var _acc_slope_from_elevation: Float64 = 0.0
    var _t0_slope_from_elevation = perf_counter_ns()
    for _ in range(N):
        _acc_slope_from_elevation += slope_from_elevation(0.5, 0.5)
    var _t1_slope_from_elevation = perf_counter_ns()
    var _ns_slope_from_elevation = Float64(_t1_slope_from_elevation - _t0_slope_from_elevation) / Float64(N)
    print("MOJO_TIMING lidar::slope_from_elevation", _ns_slope_from_elevation, _acc_slope_from_elevation)
    var _acc_intensity_normalization: Float64 = 0.0
    var _t0_intensity_normalization = perf_counter_ns()
    for _ in range(N):
        _acc_intensity_normalization += intensity_normalization(0.5, 0.5, 0.5)
    var _t1_intensity_normalization = perf_counter_ns()
    var _ns_intensity_normalization = Float64(_t1_intensity_normalization - _t0_intensity_normalization) / Float64(N)
    print("MOJO_TIMING lidar::intensity_normalization", _ns_intensity_normalization, _acc_intensity_normalization)
    var _acc_overlap_percentage: Float64 = 0.0
    var _t0_overlap_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_overlap_percentage += overlap_percentage(0.5, 0.5)
    var _t1_overlap_percentage = perf_counter_ns()
    var _ns_overlap_percentage = Float64(_t1_overlap_percentage - _t0_overlap_percentage) / Float64(N)
    print("MOJO_TIMING lidar::overlap_percentage", _ns_overlap_percentage, _acc_overlap_percentage)
    var _acc_point_cloud_file_size_mb: Float64 = 0.0
    var _t0_point_cloud_file_size_mb = perf_counter_ns()
    for _ in range(N):
        _acc_point_cloud_file_size_mb += point_cloud_file_size_mb(0.5, 0.5)
    var _t1_point_cloud_file_size_mb = perf_counter_ns()
    var _ns_point_cloud_file_size_mb = Float64(_t1_point_cloud_file_size_mb - _t0_point_cloud_file_size_mb) / Float64(N)
    print("MOJO_TIMING lidar::point_cloud_file_size_mb", _ns_point_cloud_file_size_mb, _acc_point_cloud_file_size_mb)
