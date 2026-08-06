"""
lidar_mapping.mojo — LiDAR point cloud and mapping calculations. Zero Python imports.

Public API:
  range_from_time_of_flight    — R = c * t / 2
  point_density                — pts/m² from count and area
  canopy_height_model          — CHM = DSM - DTM
  leaf_area_index_from_lidar   — LAI from gap fraction
  ground_filter_threshold      — height threshold for ground class
  beam_divergence_footprint    — spot size at range
  pulse_return_intensity       — from reflectance and range
  scan_line_spacing            — SLS from altitude and scan angle
  vertical_accuracy            — RMSE from check points
  surface_roughness_lidar      — σ from residuals of plane fit
"""
from std.math import sqrt, log, exp, cos


def range_from_time_of_flight(time_ns: Float64) -> Float64:
    """Range from time-of-flight: R = c·t/2.

    Args:
        time_ns: Round-trip travel time (ns).

    Returns:
        Range to target (m).
    """
    var c = 2.998e8  # m/s
    return c * time_ns * 1e-9 / 2.0


def point_density(n_points: Float64, area_m2: Float64) -> Float64:
    """Point density of a LiDAR dataset.

    Args:
        n_points: Number of points.
        area_m2: Coverage area (m²).

    Returns:
        Point density (pts/m²).
    """
    if area_m2 <= 0.0:
        return 0.0
    return n_points / area_m2


def canopy_height_model(dsm_elevation: Float64, dtm_elevation: Float64) -> Float64:
    """Canopy height from surface model minus terrain model.

    CHM = DSM - DTM

    Args:
        dsm_elevation: Digital surface model height (m).
        dtm_elevation: Digital terrain model height (m).

    Returns:
        Canopy height (m).
    """
    var chm = dsm_elevation - dtm_elevation
    if chm < 0.0:
        return 0.0
    return chm


def leaf_area_index_from_lidar(
    gap_fraction: Float64, zenith_angle_rad: Float64
) -> Float64:
    """LAI from LiDAR gap fraction (Beer-Lambert).

    LAI = -cos(θ) · ln(gap_fraction) / G  with G ≈ 0.5

    Args:
        gap_fraction: Fraction of pulses reaching ground (0–1).
        zenith_angle_rad: Scan zenith angle (rad).

    Returns:
        Leaf area index.
    """
    if gap_fraction <= 0.0 or gap_fraction >= 1.0:
        return 0.0
    var G = 0.5  # projection function for spherical distribution
    return -cos(zenith_angle_rad) * log(gap_fraction) / G


def ground_filter_threshold(
    scan_angle_rad: Float64, point_spacing: Float64
) -> Float64:
    """Height threshold for progressive TIN ground filter.

    threshold = point_spacing * tan(max_angle)  (simplified)

    Args:
        scan_angle_rad: Maximum slope angle for ground points (rad).
        point_spacing: Average point spacing (m).

    Returns:
        Maximum height threshold (m).
    """
    from std.math import tan
    return point_spacing * tan(scan_angle_rad)


def beam_divergence_footprint(
    range_m: Float64, beam_divergence_mrad: Float64
) -> Float64:
    """Laser beam footprint diameter at a given range.

    D = range × divergence (for small angles: D ≈ R·θ)

    Args:
        range_m: Slant range to target (m).
        beam_divergence_mrad: Full-angle beam divergence (mrad).

    Returns:
        Footprint diameter (m).
    """
    return range_m * beam_divergence_mrad * 1e-3


def pulse_return_intensity(
    reflectance: Float64, range_m: Float64, system_constant: Float64
) -> Float64:
    """Received pulse intensity from range equation (simplified).

    I = C · ρ / R²

    Args:
        reflectance: Target reflectance ρ (0–1).
        range_m: Range to target (m).
        system_constant: System/aperture constant C.

    Returns:
        Return intensity (arbitrary units).
    """
    if range_m <= 0.0:
        return 0.0
    return system_constant * reflectance / (range_m * range_m)


def scan_line_spacing(
    altitude: Float64, scan_rate: Float64, flight_speed: Float64
) -> Float64:
    """Along-track scan line spacing.

    SLS = v / scan_rate

    Args:
        altitude: Flight altitude (m, unused in simplified model).
        scan_rate: Scan lines per second (Hz).
        flight_speed: Aircraft ground speed (m/s).

    Returns:
        Scan line spacing (m).
    """
    if scan_rate <= 0.0:
        return 0.0
    return flight_speed / scan_rate


def vertical_accuracy(
    z_lidar: Float64, z_check: Float64
) -> Float64:
    """Point-wise vertical error: residual = z_LiDAR - z_check.

    Args:
        z_lidar: LiDAR-derived elevation (m).
        z_check: Independent check point elevation (m).

    Returns:
        Vertical residual (m).
    """
    return z_lidar - z_check


def surface_roughness_lidar(mean_residual: Float64, n_points: Float64) -> Float64:
    """Surface roughness as RMS of plane fit residuals.

    σ = sqrt(sum(r²) / n)  approximated from mean_residual.

    Args:
        mean_residual: Mean squared residual from plane fit (m²).
        n_points: Number of points used.

    Returns:
        RMS roughness (m).
    """
    if mean_residual < 0.0:
        return 0.0
    return sqrt(mean_residual)
