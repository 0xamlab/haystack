"""
earth.mojo — Geospatial math primitives. Zero Python imports.

Replaces geopy with pure Mojo implementations of great-circle distance
(haversine), bearing, midpoint, destination point, bounding box,
coordinate validation, and cross-track distance.

Public API:
  haversine              — great-circle distance in km (R = 6371 km)
  bearing                — initial bearing in degrees (0-360)
  midpoint               — geographic midpoint [lat, lon]
  destination_point      — point at given distance & bearing from start
  bounding_box           — [min_lat, min_lon, max_lat, max_lon]
  deg_to_rad             — degrees to radians
  rad_to_deg             — radians to degrees
  is_valid_coordinate    — lat in [-90,90], lon in [-180,180]
  distance_on_unit_sphere — haversine on unit sphere (radians)
  cross_track_distance   — cross-track distance from great circle path
"""
from std.math import sin, cos, sqrt, asin, atan2, abs as fabs


# ── Constants ────────────────────────────────────────────────────────────────


comptime PI: Float64 = 3.141592653589793
comptime EARTH_RADIUS_KM: Float64 = 6371.0


# ── deg_to_rad ───────────────────────────────────────────────────────────────


def deg_to_rad(deg: Float64) -> Float64:
    """Convert degrees to radians."""
    return deg * PI / 180.0


# ── rad_to_deg ───────────────────────────────────────────────────────────────


def rad_to_deg(rad: Float64) -> Float64:
    """Convert radians to degrees."""
    return rad * 180.0 / PI


# ── is_valid_coordinate ──────────────────────────────────────────────────────


def is_valid_coordinate(lat: Float64, lon: Float64) -> Bool:
    """Check if lat in [-90,90] and lon in [-180,180]."""
    return lat >= -90.0 and lat <= 90.0 and lon >= -180.0 and lon <= 180.0


# ── distance_on_unit_sphere ──────────────────────────────────────────────────


def distance_on_unit_sphere(lat1: Float64, lon1: Float64, lat2: Float64, lon2: Float64) -> Float64:
    """Haversine formula on the unit sphere. Returns angle in radians."""
    var phi1 = deg_to_rad(lat1)
    var phi2 = deg_to_rad(lat2)
    var dphi = deg_to_rad(lat2 - lat1)
    var dlam = deg_to_rad(lon2 - lon1)
    var a = sin(dphi / 2.0) * sin(dphi / 2.0) + cos(phi1) * cos(phi2) * sin(dlam / 2.0) * sin(dlam / 2.0)
    var sq = sqrt(a)
    if sq > 1.0:
        sq = 1.0
    return 2.0 * asin(sq)


# ── haversine ────────────────────────────────────────────────────────────────


def haversine(lat1: Float64, lon1: Float64, lat2: Float64, lon2: Float64) -> Float64:
    """Great-circle distance in km between two points (haversine formula)."""
    return distance_on_unit_sphere(lat1, lon1, lat2, lon2) * EARTH_RADIUS_KM


# ── bearing ──────────────────────────────────────────────────────────────────


def bearing(lat1: Float64, lon1: Float64, lat2: Float64, lon2: Float64) -> Float64:
    """Initial bearing from point 1 to point 2 in degrees (0-360)."""
    var phi1 = deg_to_rad(lat1)
    var phi2 = deg_to_rad(lat2)
    var dlam = deg_to_rad(lon2 - lon1)
    var x = sin(dlam) * cos(phi2)
    var y = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dlam)
    var theta = atan2(x, y)
    var deg = rad_to_deg(theta)
    # Normalize to [0, 360)
    while deg < 0.0:
        deg += 360.0
    while deg >= 360.0:
        deg -= 360.0
    return deg


# ── midpoint ─────────────────────────────────────────────────────────────────


def midpoint(lat1: Float64, lon1: Float64, lat2: Float64, lon2: Float64) -> List[Float64]:
    """Geographic midpoint [lat, lon] in degrees."""
    var phi1 = deg_to_rad(lat1)
    var phi2 = deg_to_rad(lat2)
    var lam1 = deg_to_rad(lon1)
    var dlam = deg_to_rad(lon2 - lon1)
    var bx = cos(phi2) * cos(dlam)
    var by = cos(phi2) * sin(dlam)
    var phi3 = atan2(sin(phi1) + sin(phi2), sqrt((cos(phi1) + bx) * (cos(phi1) + bx) + by * by))
    var lam3 = lam1 + atan2(by, cos(phi1) + bx)
    var result = List[Float64]()
    result.append(rad_to_deg(phi3))
    result.append(rad_to_deg(lam3))
    return result^


# ── destination_point ────────────────────────────────────────────────────────


def destination_point(lat: Float64, lon: Float64, bearing_deg: Float64, distance_km: Float64) -> List[Float64]:
    """Point at given distance (km) and bearing (deg) from start. Returns [lat, lon]."""
    var phi1 = deg_to_rad(lat)
    var lam1 = deg_to_rad(lon)
    var brng = deg_to_rad(bearing_deg)
    var delta = distance_km / EARTH_RADIUS_KM  # angular distance
    var phi2 = asin(sin(phi1) * cos(delta) + cos(phi1) * sin(delta) * cos(brng))
    var lam2 = lam1 + atan2(sin(brng) * sin(delta) * cos(phi1), cos(delta) - sin(phi1) * sin(phi2))
    var result = List[Float64]()
    result.append(rad_to_deg(phi2))
    result.append(rad_to_deg(lam2))
    return result^


# ── bounding_box ─────────────────────────────────────────────────────────────


def bounding_box(lat: Float64, lon: Float64, radius_km: Float64) -> List[Float64]:
    """Bounding box [min_lat, min_lon, max_lat, max_lon] around a point.
    Uses simple angular distance approximation."""
    var delta_lat = rad_to_deg(radius_km / EARTH_RADIUS_KM)
    var phi = deg_to_rad(lat)
    var cos_phi = cos(phi)
    var delta_lon: Float64 = 0.0
    if cos_phi > 1e-10:
        delta_lon = rad_to_deg(radius_km / (EARTH_RADIUS_KM * cos_phi))
    else:
        delta_lon = 180.0  # near pole
    var result = List[Float64]()
    result.append(lat - delta_lat)
    result.append(lon - delta_lon)
    result.append(lat + delta_lat)
    result.append(lon + delta_lon)
    return result^


# ── cross_track_distance ────────────────────────────────────────────────────


def cross_track_distance(lat1: Float64, lon1: Float64, lat2: Float64, lon2: Float64, lat3: Float64, lon3: Float64) -> Float64:
    """Cross-track distance of point 3 from great circle path 1→2, in km.
    Positive = right of path, negative = left. Returns absolute value."""
    var d13 = distance_on_unit_sphere(lat1, lon1, lat3, lon3)
    var brng13 = deg_to_rad(bearing(lat1, lon1, lat3, lon3))
    var brng12 = deg_to_rad(bearing(lat1, lon1, lat2, lon2))
    var dxt = asin(sin(d13) * sin(brng13 - brng12))
    return fabs(dxt) * EARTH_RADIUS_KM
