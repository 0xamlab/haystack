"""LiDAR / Remote Sensing Library.

Provides functions for LiDAR point cloud processing, terrain analysis,
and remote sensing calculations.
"""

from std.math import sqrt, log, abs, sin, cos, atan


comptime PI: Float64 = 3.141592653589793


def range_from_tof(time_of_flight: Float64, c: Float64 = 3.0e8) -> Float64:
    """Range from time-of-flight: R = c*t/2."""
    return c * time_of_flight / 2.0


def point_density(n_points: Float64, area: Float64) -> Float64:
    """Point density PD = points / area (points/m²)."""
    if area <= 0.0:
        return 0.0
    return n_points / area


def scan_swath_width(altitude: Float64, scan_angle_deg: Float64) -> Float64:
    """Scan swath width W = 2*h*tan(θ/2).

    scan_angle_deg is the full scan angle in degrees.
    """
    var half_angle_rad = (scan_angle_deg / 2.0) * PI / 180.0
    var tan_val = sin(half_angle_rad) / cos(half_angle_rad)
    return 2.0 * altitude * tan_val


def footprint_diameter(altitude: Float64, divergence_mrad: Float64) -> Float64:
    """Laser footprint diameter D = h * divergence/1000."""
    return altitude * divergence_mrad / 1000.0


def pulse_repetition_frequency_to_point_rate(
    prf: Float64, scan_lines_per_sec: Float64 = 1.0, points_per_line: Float64 = 1.0
) -> Float64:
    """Point rate from PRF (simplified): Rate = prf."""
    return prf


def ground_sampling_distance(altitude: Float64, focal_length: Float64, pixel_size: Float64) -> Float64:
    """Ground sampling distance GSD = h * pixel_size / focal_length."""
    if focal_length <= 0.0:
        return 0.0
    return altitude * pixel_size / focal_length


def vegetation_index_from_returns(first_returns: Float64, last_returns: Float64) -> Float64:
    """Vegetation index from returns: VI = (first-last)/first * 100 (simplified)."""
    if first_returns <= 0.0:
        return 0.0
    return (first_returns - last_returns) / first_returns * 100.0


def canopy_height(dsm: Float64, dtm: Float64) -> Float64:
    """Canopy height model CHM = DSM - DTM."""
    return dsm - dtm


def slope_from_elevation(dz: Float64, dx: Float64) -> Float64:
    """Slope from elevation difference: slope = atan(dz/dx) * 180/π."""
    if abs(dx) < 1e-15:
        return 90.0
    return atan(dz / dx) * 180.0 / PI


def intensity_normalization(intensity: Float64, range_val: Float64, ref_range: Float64) -> Float64:
    """Intensity normalization: I_norm = intensity * (range/ref)²."""
    if ref_range <= 0.0:
        return 0.0
    var ratio = range_val / ref_range
    return intensity * ratio * ratio


def overlap_percentage(swath_width: Float64, strip_spacing: Float64) -> Float64:
    """Overlap percentage: Overlap = (W - spacing) / W * 100."""
    if swath_width <= 0.0:
        return 0.0
    return (swath_width - strip_spacing) / swath_width * 100.0


def point_cloud_file_size_mb(n_points: Float64, bytes_per_point: Float64) -> Float64:
    """Estimated point cloud file size: Size = points * bpp / 1e6 (MB)."""
    return n_points * bytes_per_point / 1.0e6
