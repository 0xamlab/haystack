"""bench_lidar.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from lidar import range_from_tof, point_density, scan_swath_width, footprint_diameter, pulse_repetition_frequency_to_point_rate, ground_sampling_distance, vegetation_index_from_returns, canopy_height, slope_from_elevation, intensity_normalization, overlap_percentage, point_cloud_file_size_mb
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

    var _acc_range_from_tof: Float64 = 0.0
    var _t0_range_from_tof = perf_counter_ns()
    for _ in range(N):
        _acc_range_from_tof += range_from_tof(0.5, 0.5)
    var _t1_range_from_tof = perf_counter_ns()
    var _ns_range_from_tof = Float64(_t1_range_from_tof - _t0_range_from_tof) / Float64(N)
    print("MOJO_TIMING lidar::range_from_tof", _ns_range_from_tof, _acc_range_from_tof)
    var _result_range_from_tof = range_from_tof(0.5, 0.5)
    var _summary_range_from_tof = _summary_float64(_result_range_from_tof)
    print("MOJO_RESULT lidar::range_from_tof", _summary_range_from_tof)
    var _acc_point_density: Float64 = 0.0
    var _t0_point_density = perf_counter_ns()
    for _ in range(N):
        _acc_point_density += point_density(0.5, 0.5)
    var _t1_point_density = perf_counter_ns()
    var _ns_point_density = Float64(_t1_point_density - _t0_point_density) / Float64(N)
    print("MOJO_TIMING lidar::point_density", _ns_point_density, _acc_point_density)
    var _result_point_density = point_density(0.5, 0.5)
    var _summary_point_density = _summary_float64(_result_point_density)
    print("MOJO_RESULT lidar::point_density", _summary_point_density)
    var _acc_scan_swath_width: Float64 = 0.0
    var _t0_scan_swath_width = perf_counter_ns()
    for _ in range(N):
        _acc_scan_swath_width += scan_swath_width(0.5, 0.5)
    var _t1_scan_swath_width = perf_counter_ns()
    var _ns_scan_swath_width = Float64(_t1_scan_swath_width - _t0_scan_swath_width) / Float64(N)
    print("MOJO_TIMING lidar::scan_swath_width", _ns_scan_swath_width, _acc_scan_swath_width)
    var _result_scan_swath_width = scan_swath_width(0.5, 0.5)
    var _summary_scan_swath_width = _summary_float64(_result_scan_swath_width)
    print("MOJO_RESULT lidar::scan_swath_width", _summary_scan_swath_width)
    var _acc_footprint_diameter: Float64 = 0.0
    var _t0_footprint_diameter = perf_counter_ns()
    for _ in range(N):
        _acc_footprint_diameter += footprint_diameter(0.5, 0.5)
    var _t1_footprint_diameter = perf_counter_ns()
    var _ns_footprint_diameter = Float64(_t1_footprint_diameter - _t0_footprint_diameter) / Float64(N)
    print("MOJO_TIMING lidar::footprint_diameter", _ns_footprint_diameter, _acc_footprint_diameter)
    var _result_footprint_diameter = footprint_diameter(0.5, 0.5)
    var _summary_footprint_diameter = _summary_float64(_result_footprint_diameter)
    print("MOJO_RESULT lidar::footprint_diameter", _summary_footprint_diameter)
    var _acc_pulse_repetition_frequency_to_point_rate: Float64 = 0.0
    var _t0_pulse_repetition_frequency_to_point_rate = perf_counter_ns()
    for _ in range(N):
        _acc_pulse_repetition_frequency_to_point_rate += pulse_repetition_frequency_to_point_rate(0.5, 0.5, 0.5)
    var _t1_pulse_repetition_frequency_to_point_rate = perf_counter_ns()
    var _ns_pulse_repetition_frequency_to_point_rate = Float64(_t1_pulse_repetition_frequency_to_point_rate - _t0_pulse_repetition_frequency_to_point_rate) / Float64(N)
    print("MOJO_TIMING lidar::pulse_repetition_frequency_to_point_rate", _ns_pulse_repetition_frequency_to_point_rate, _acc_pulse_repetition_frequency_to_point_rate)
    var _result_pulse_repetition_frequency_to_point_rate = pulse_repetition_frequency_to_point_rate(0.5, 0.5, 0.5)
    var _summary_pulse_repetition_frequency_to_point_rate = _summary_float64(_result_pulse_repetition_frequency_to_point_rate)
    print("MOJO_RESULT lidar::pulse_repetition_frequency_to_point_rate", _summary_pulse_repetition_frequency_to_point_rate)
    var _acc_ground_sampling_distance: Float64 = 0.0
    var _t0_ground_sampling_distance = perf_counter_ns()
    for _ in range(N):
        _acc_ground_sampling_distance += ground_sampling_distance(0.5, 0.5, 0.5)
    var _t1_ground_sampling_distance = perf_counter_ns()
    var _ns_ground_sampling_distance = Float64(_t1_ground_sampling_distance - _t0_ground_sampling_distance) / Float64(N)
    print("MOJO_TIMING lidar::ground_sampling_distance", _ns_ground_sampling_distance, _acc_ground_sampling_distance)
    var _result_ground_sampling_distance = ground_sampling_distance(0.5, 0.5, 0.5)
    var _summary_ground_sampling_distance = _summary_float64(_result_ground_sampling_distance)
    print("MOJO_RESULT lidar::ground_sampling_distance", _summary_ground_sampling_distance)
    var _acc_vegetation_index_from_returns: Float64 = 0.0
    var _t0_vegetation_index_from_returns = perf_counter_ns()
    for _ in range(N):
        _acc_vegetation_index_from_returns += vegetation_index_from_returns(0.5, 0.5)
    var _t1_vegetation_index_from_returns = perf_counter_ns()
    var _ns_vegetation_index_from_returns = Float64(_t1_vegetation_index_from_returns - _t0_vegetation_index_from_returns) / Float64(N)
    print("MOJO_TIMING lidar::vegetation_index_from_returns", _ns_vegetation_index_from_returns, _acc_vegetation_index_from_returns)
    var _result_vegetation_index_from_returns = vegetation_index_from_returns(0.5, 0.5)
    var _summary_vegetation_index_from_returns = _summary_float64(_result_vegetation_index_from_returns)
    print("MOJO_RESULT lidar::vegetation_index_from_returns", _summary_vegetation_index_from_returns)
    var _acc_canopy_height: Float64 = 0.0
    var _t0_canopy_height = perf_counter_ns()
    for _ in range(N):
        _acc_canopy_height += canopy_height(0.5, 0.5)
    var _t1_canopy_height = perf_counter_ns()
    var _ns_canopy_height = Float64(_t1_canopy_height - _t0_canopy_height) / Float64(N)
    print("MOJO_TIMING lidar::canopy_height", _ns_canopy_height, _acc_canopy_height)
    var _result_canopy_height = canopy_height(0.5, 0.5)
    var _summary_canopy_height = _summary_float64(_result_canopy_height)
    print("MOJO_RESULT lidar::canopy_height", _summary_canopy_height)
    var _acc_slope_from_elevation: Float64 = 0.0
    var _t0_slope_from_elevation = perf_counter_ns()
    for _ in range(N):
        _acc_slope_from_elevation += slope_from_elevation(0.5, 0.5)
    var _t1_slope_from_elevation = perf_counter_ns()
    var _ns_slope_from_elevation = Float64(_t1_slope_from_elevation - _t0_slope_from_elevation) / Float64(N)
    print("MOJO_TIMING lidar::slope_from_elevation", _ns_slope_from_elevation, _acc_slope_from_elevation)
    var _result_slope_from_elevation = slope_from_elevation(0.5, 0.5)
    var _summary_slope_from_elevation = _summary_float64(_result_slope_from_elevation)
    print("MOJO_RESULT lidar::slope_from_elevation", _summary_slope_from_elevation)
    var _acc_intensity_normalization: Float64 = 0.0
    var _t0_intensity_normalization = perf_counter_ns()
    for _ in range(N):
        _acc_intensity_normalization += intensity_normalization(0.5, 0.5, 0.5)
    var _t1_intensity_normalization = perf_counter_ns()
    var _ns_intensity_normalization = Float64(_t1_intensity_normalization - _t0_intensity_normalization) / Float64(N)
    print("MOJO_TIMING lidar::intensity_normalization", _ns_intensity_normalization, _acc_intensity_normalization)
    var _result_intensity_normalization = intensity_normalization(0.5, 0.5, 0.5)
    var _summary_intensity_normalization = _summary_float64(_result_intensity_normalization)
    print("MOJO_RESULT lidar::intensity_normalization", _summary_intensity_normalization)
    var _acc_overlap_percentage: Float64 = 0.0
    var _t0_overlap_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_overlap_percentage += overlap_percentage(0.5, 0.5)
    var _t1_overlap_percentage = perf_counter_ns()
    var _ns_overlap_percentage = Float64(_t1_overlap_percentage - _t0_overlap_percentage) / Float64(N)
    print("MOJO_TIMING lidar::overlap_percentage", _ns_overlap_percentage, _acc_overlap_percentage)
    var _result_overlap_percentage = overlap_percentage(0.5, 0.5)
    var _summary_overlap_percentage = _summary_float64(_result_overlap_percentage)
    print("MOJO_RESULT lidar::overlap_percentage", _summary_overlap_percentage)
    var _acc_point_cloud_file_size_mb: Float64 = 0.0
    var _t0_point_cloud_file_size_mb = perf_counter_ns()
    for _ in range(N):
        _acc_point_cloud_file_size_mb += point_cloud_file_size_mb(0.5, 0.5)
    var _t1_point_cloud_file_size_mb = perf_counter_ns()
    var _ns_point_cloud_file_size_mb = Float64(_t1_point_cloud_file_size_mb - _t0_point_cloud_file_size_mb) / Float64(N)
    print("MOJO_TIMING lidar::point_cloud_file_size_mb", _ns_point_cloud_file_size_mb, _acc_point_cloud_file_size_mb)
    var _result_point_cloud_file_size_mb = point_cloud_file_size_mb(0.5, 0.5)
    var _summary_point_cloud_file_size_mb = _summary_float64(_result_point_cloud_file_size_mb)
    print("MOJO_RESULT lidar::point_cloud_file_size_mb", _summary_point_cloud_file_size_mb)
