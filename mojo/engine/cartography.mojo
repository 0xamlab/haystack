"""
cartography.mojo — Cartography / Map Projection Library. Zero Python imports.

Pure Mojo implementations of map scale calculations, coordinate projections,
great circle distance, and cartographic utilities.

Public API:
  scale_factor              — SF = map/ground
  representative_fraction   — RF = 1:ground/map
  ground_distance_from_map  — GD = map_dist * scale
  map_distance_from_ground  — MD = ground / scale
  latitude_to_utm_zone      — Zone = floor((longitude+180)/6) + 1
  mercator_y                — y = ln(tan(π/4 + lat/2))
  equirectangular_x         — x = (lon-cm)*cos_lat
  equirectangular_y         — y = lat (identity)
  great_circle_distance     — d = R*acos(...)
  map_area_at_scale         — map_area = real/(scale²)
  contour_interval_suggestion — CI = range/n
  declination_correction    — True = bearing + declination
"""
from std.math import abs as fabs, log, sin, cos, acos, floor

comptime PI: Float64 = 3.141592653589793


# ── scale_factor ─────────────────────────────────────────────────────────────


fn scale_factor(map_distance: Float64, ground_distance: Float64) -> Float64:
    """Scale factor: SF = map_distance / ground_distance.

    Args:
        map_distance:    Distance on map.
        ground_distance: Corresponding distance on ground.

    Returns:
        Scale factor (dimensionless).
    """
    if fabs(ground_distance) < 1e-30:
        return 0.0
    return map_distance / ground_distance


# ── representative_fraction ──────────────────────────────────────────────────


fn representative_fraction(map_cm: Float64, ground_cm: Float64) -> Float64:
    """Representative fraction denominator: RF = ground/map.

    Args:
        map_cm:    Distance on map (cm).
        ground_cm: Corresponding ground distance (cm).

    Returns:
        Denominator of representative fraction (e.g., 50000 for 1:50000).
    """
    if fabs(map_cm) < 1e-30:
        return 0.0
    return ground_cm / map_cm


# ── ground_distance_from_map ─────────────────────────────────────────────────


fn ground_distance_from_map(map_distance: Float64, scale_denominator: Float64) -> Float64:
    """Ground distance from map distance: GD = map_dist * scale_denominator.

    Args:
        map_distance:      Distance measured on map.
        scale_denominator: Scale denominator (e.g., 50000 for 1:50000).

    Returns:
        Ground distance in same units as map_distance * scale.
    """
    return map_distance * scale_denominator


# ── map_distance_from_ground ─────────────────────────────────────────────────


fn map_distance_from_ground(ground_distance: Float64, scale_denominator: Float64) -> Float64:
    """Map distance from ground distance: MD = ground / scale_denominator.

    Args:
        ground_distance:   Real-world ground distance.
        scale_denominator: Scale denominator.

    Returns:
        Map distance.
    """
    if fabs(scale_denominator) < 1e-30:
        return 0.0
    return ground_distance / scale_denominator


# ── latitude_to_utm_zone ────────────────────────────────────────────────────


fn latitude_to_utm_zone(longitude: Float64) -> Int:
    """UTM zone from longitude: Zone = floor((longitude+180)/6) + 1.

    Args:
        longitude: Longitude in degrees (-180 to 180).

    Returns:
        UTM zone number (1–60).
    """
    return Int(floor((longitude + 180.0) / 6.0)) + 1


# ── mercator_y ───────────────────────────────────────────────────────────────


fn mercator_y(latitude_rad: Float64) -> Float64:
    """Mercator projection y-coordinate: y = ln(tan(π/4 + lat/2)).

    Args:
        latitude_rad: Latitude in radians.

    Returns:
        Mercator y value (dimensionless).
    """
    var arg = PI / 4.0 + latitude_rad / 2.0
    # tan(arg) = sin(arg)/cos(arg)
    var c = cos(arg)
    if fabs(c) < 1e-30:
        return 0.0
    var t = sin(arg) / c
    if t <= 0.0:
        return 0.0
    return log(t)


# ── equirectangular_x ───────────────────────────────────────────────────────


fn equirectangular_x(longitude_rad: Float64, central_meridian: Float64, cos_lat: Float64) -> Float64:
    """Equirectangular projection x: x = (lon - central_meridian) * cos(lat).

    Args:
        longitude_rad:    Longitude in radians.
        central_meridian: Central meridian in radians.
        cos_lat:          Cosine of the standard parallel latitude.

    Returns:
        Projected x-coordinate.
    """
    return (longitude_rad - central_meridian) * cos_lat


# ── equirectangular_y ───────────────────────────────────────────────────────


fn equirectangular_y(latitude_rad: Float64) -> Float64:
    """Equirectangular projection y: y = latitude (identity mapping).

    Args:
        latitude_rad: Latitude in radians.

    Returns:
        Projected y-coordinate (same as latitude_rad).
    """
    return latitude_rad


# ── great_circle_distance ───────────────────────────────────────────────────


fn great_circle_distance(
    lat1: Float64,
    lon1: Float64,
    lat2: Float64,
    lon2: Float64,
    radius: Float64,
) -> Float64:
    """Great circle distance using spherical law of cosines.

    d = R * acos(sin(lat1)*sin(lat2) + cos(lat1)*cos(lat2)*cos(lon2-lon1))

    Args:
        lat1:   Latitude of point 1 (radians).
        lon1:   Longitude of point 1 (radians).
        lat2:   Latitude of point 2 (radians).
        lon2:   Longitude of point 2 (radians).
        radius: Sphere radius (e.g., 6371 km for Earth).

    Returns:
        Great circle distance in same units as radius.
    """
    var cos_angle = sin(lat1) * sin(lat2) + cos(lat1) * cos(lat2) * cos(lon2 - lon1)
    # Clamp to [-1, 1] to avoid numerical issues with acos
    if cos_angle > 1.0:
        cos_angle = 1.0
    if cos_angle < -1.0:
        cos_angle = -1.0
    return radius * acos(cos_angle)


# ── map_area_at_scale ────────────────────────────────────────────────────────


fn map_area_at_scale(real_area: Float64, scale_denominator: Float64) -> Float64:
    """Map area at given scale: map_area = real_area / (scale²).

    Args:
        real_area:         Real-world area.
        scale_denominator: Scale denominator.

    Returns:
        Area on the map.
    """
    var s2 = scale_denominator * scale_denominator
    if fabs(s2) < 1e-30:
        return 0.0
    return real_area / s2


# ── contour_interval_suggestion ──────────────────────────────────────────────


fn contour_interval_suggestion(elevation_range: Float64, n_contours: Float64) -> Float64:
    """Suggest contour interval: CI = elevation_range / n_contours.

    Args:
        elevation_range: Total elevation range.
        n_contours:      Desired number of contour lines.

    Returns:
        Suggested contour interval.
    """
    if fabs(n_contours) < 1e-30:
        return 0.0
    return elevation_range / n_contours


# ── declination_correction ───────────────────────────────────────────────────


fn declination_correction(bearing: Float64, declination: Float64) -> Float64:
    """Correct magnetic bearing for declination: True = bearing + declination.

    Args:
        bearing:     Magnetic bearing (degrees).
        declination: Magnetic declination (degrees, positive east).

    Returns:
        True bearing in degrees.
    """
    return bearing + declination
