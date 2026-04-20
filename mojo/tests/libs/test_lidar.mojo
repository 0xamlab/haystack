"""test_lidar.mojo — auto-generated tests for lidar library."""
from std.math import isnan, isinf
from lidar import range_from_tof, point_density, scan_swath_width, footprint_diameter, pulse_repetition_frequency_to_point_rate, ground_sampling_distance, vegetation_index_from_returns, canopy_height, slope_from_elevation, intensity_normalization, overlap_percentage, point_cloud_file_size_mb

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_range_from_tof = range_from_tof(0.5, 0.5)
    if is_finite(_v_range_from_tof): passed += 1; print("  ✅ lidar::range_from_tof =", _v_range_from_tof)
    else: failed += 1; print("  ❌ lidar::range_from_tof → non-finite:", _v_range_from_tof)
    var _v_point_density = point_density(0.5, 0.5)
    if is_finite(_v_point_density): passed += 1; print("  ✅ lidar::point_density =", _v_point_density)
    else: failed += 1; print("  ❌ lidar::point_density → non-finite:", _v_point_density)
    var _v_scan_swath_width = scan_swath_width(0.5, 0.5)
    if is_finite(_v_scan_swath_width): passed += 1; print("  ✅ lidar::scan_swath_width =", _v_scan_swath_width)
    else: failed += 1; print("  ❌ lidar::scan_swath_width → non-finite:", _v_scan_swath_width)
    var _v_footprint_diameter = footprint_diameter(0.5, 0.5)
    if is_finite(_v_footprint_diameter): passed += 1; print("  ✅ lidar::footprint_diameter =", _v_footprint_diameter)
    else: failed += 1; print("  ❌ lidar::footprint_diameter → non-finite:", _v_footprint_diameter)
    var _v_pulse_repetition_frequency_to_point_rate = pulse_repetition_frequency_to_point_rate(0.5, 0.5, 0.5)
    if is_finite(_v_pulse_repetition_frequency_to_point_rate): passed += 1; print("  ✅ lidar::pulse_repetition_frequency_to_point_rate =", _v_pulse_repetition_frequency_to_point_rate)
    else: failed += 1; print("  ❌ lidar::pulse_repetition_frequency_to_point_rate → non-finite:", _v_pulse_repetition_frequency_to_point_rate)
    var _v_ground_sampling_distance = ground_sampling_distance(0.5, 0.5, 0.5)
    if is_finite(_v_ground_sampling_distance): passed += 1; print("  ✅ lidar::ground_sampling_distance =", _v_ground_sampling_distance)
    else: failed += 1; print("  ❌ lidar::ground_sampling_distance → non-finite:", _v_ground_sampling_distance)
    var _v_vegetation_index_from_returns = vegetation_index_from_returns(0.5, 0.5)
    if is_finite(_v_vegetation_index_from_returns): passed += 1; print("  ✅ lidar::vegetation_index_from_returns =", _v_vegetation_index_from_returns)
    else: failed += 1; print("  ❌ lidar::vegetation_index_from_returns → non-finite:", _v_vegetation_index_from_returns)
    var _v_canopy_height = canopy_height(0.5, 0.5)
    if is_finite(_v_canopy_height): passed += 1; print("  ✅ lidar::canopy_height =", _v_canopy_height)
    else: failed += 1; print("  ❌ lidar::canopy_height → non-finite:", _v_canopy_height)
    var _v_slope_from_elevation = slope_from_elevation(0.5, 0.5)
    if is_finite(_v_slope_from_elevation): passed += 1; print("  ✅ lidar::slope_from_elevation =", _v_slope_from_elevation)
    else: failed += 1; print("  ❌ lidar::slope_from_elevation → non-finite:", _v_slope_from_elevation)
    var _v_intensity_normalization = intensity_normalization(0.5, 0.5, 0.5)
    if is_finite(_v_intensity_normalization): passed += 1; print("  ✅ lidar::intensity_normalization =", _v_intensity_normalization)
    else: failed += 1; print("  ❌ lidar::intensity_normalization → non-finite:", _v_intensity_normalization)
    var _v_overlap_percentage = overlap_percentage(0.5, 0.5)
    if is_finite(_v_overlap_percentage): passed += 1; print("  ✅ lidar::overlap_percentage =", _v_overlap_percentage)
    else: failed += 1; print("  ❌ lidar::overlap_percentage → non-finite:", _v_overlap_percentage)
    var _v_point_cloud_file_size_mb = point_cloud_file_size_mb(0.5, 0.5)
    if is_finite(_v_point_cloud_file_size_mb): passed += 1; print("  ✅ lidar::point_cloud_file_size_mb =", _v_point_cloud_file_size_mb)
    else: failed += 1; print("  ❌ lidar::point_cloud_file_size_mb → non-finite:", _v_point_cloud_file_size_mb)

    print("  [lidar] Passed:", passed, "Failed:", failed)
