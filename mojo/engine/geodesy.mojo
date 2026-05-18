"""
geodesy.mojo — Geodetic Calculations Library. Zero Python imports.

Pure Mojo implementations for haversine/vincenty distance, bearing,
destination point, midpoint, cross/along-track distance, coordinate
conversions (geodetic↔ECEF), and rhumb line distance.

Public API:
  haversine_distance     — Great-circle distance in km
  vincenty_distance      — More accurate geodesic distance
  initial_bearing        — Forward azimuth in degrees
  destination_point      — Point at distance along bearing
  midpoint               — Geographic midpoint
  cross_track_distance   — Distance from point to great-circle path
  along_track_distance   — Distance along path to nearest point
  geodetic_to_ecef       — Convert to ECEF coordinates
  ecef_to_geodetic       — Convert ECEF to lat/lon/alt
  rhumb_distance         — Distance along rhumb line
"""
from std.math import sin, cos, sqrt, asin, atan2, abs as fabs, log, tan


# ── Constants ────────────────────────────────────────────────────────────────

comptime PI: Float64 = 3.141592653589793
comptime EARTH_RADIUS_KM: Float64 = 6371.0
comptime WGS84_A: Float64 = 6378137.0          # semi-major axis (m)
comptime WGS84_B: Float64 = 6356752.314245      # semi-minor axis (m)
comptime WGS84_F: Float64 = 1.0 / 298.257223563 # flattening


# ── Helpers ──────────────────────────────────────────────────────────────────


fn _deg2rad(d: Float64) -> Float64:
    return d * PI / 180.0


fn _rad2deg(r: Float64) -> Float64:
    return r * 180.0 / PI


# ── haversine_distance ───────────────────────────────────────────────────────


fn haversine_distance(lat1: Float64, lon1: Float64, lat2: Float64, lon2: Float64) -> Float64:
    """Great-circle distance in km using haversine formula."""
    var p1 = _deg2rad(lat1)
    var p2 = _deg2rad(lat2)
    var dp = _deg2rad(lat2 - lat1)
    var dl = _deg2rad(lon2 - lon1)
    var a = sin(dp / 2.0) * sin(dp / 2.0) + cos(p1) * cos(p2) * sin(dl / 2.0) * sin(dl / 2.0)
    var sq = sqrt(a)
    if sq > 1.0:
        sq = 1.0
    return 2.0 * EARTH_RADIUS_KM * asin(sq)


# ── vincenty_distance ────────────────────────────────────────────────────────


fn vincenty_distance(lat1: Float64, lon1: Float64, lat2: Float64, lon2: Float64) -> Float64:
    """Vincenty geodesic distance in km (iterative formula on WGS84 ellipsoid)."""
    var u1 = atan2((1.0 - WGS84_F) * sin(_deg2rad(lat1)), cos(_deg2rad(lat1)))
    var u2 = atan2((1.0 - WGS84_F) * sin(_deg2rad(lat2)), cos(_deg2rad(lat2)))
    var L = _deg2rad(lon2 - lon1)
    var lam = L
    var sin_u1 = sin(u1)
    var cos_u1 = cos(u1)
    var sin_u2 = sin(u2)
    var cos_u2 = cos(u2)

    for _ in range(100):
        var sin_lam = sin(lam)
        var cos_lam = cos(lam)
        var sin_sig = sqrt(
            (cos_u2 * sin_lam) * (cos_u2 * sin_lam)
            + (cos_u1 * sin_u2 - sin_u1 * cos_u2 * cos_lam)
            * (cos_u1 * sin_u2 - sin_u1 * cos_u2 * cos_lam)
        )
        if sin_sig < 1e-12:
            return 0.0  # coincident points
        var cos_sig = sin_u1 * sin_u2 + cos_u1 * cos_u2 * cos_lam
        var sig = atan2(sin_sig, cos_sig)
        var sin_alpha = cos_u1 * cos_u2 * sin_lam / sin_sig
        var cos2_alpha = 1.0 - sin_alpha * sin_alpha
        var cos_2sigm: Float64 = 0.0
        if cos2_alpha > 1e-12:
            cos_2sigm = cos_sig - 2.0 * sin_u1 * sin_u2 / cos2_alpha
        var C = WGS84_F / 16.0 * cos2_alpha * (4.0 + WGS84_F * (4.0 - 3.0 * cos2_alpha))
        var lam_prev = lam
        lam = L + (1.0 - C) * WGS84_F * sin_alpha * (
            sig + C * sin_sig * (cos_2sigm + C * cos_sig * (-1.0 + 2.0 * cos_2sigm * cos_2sigm))
        )
        if fabs(lam - lam_prev) < 1e-12:
            # Converged — compute distance
            var u_sq = cos2_alpha * (WGS84_A * WGS84_A - WGS84_B * WGS84_B) / (WGS84_B * WGS84_B)
            var A_v = 1.0 + u_sq / 16384.0 * (4096.0 + u_sq * (-768.0 + u_sq * (320.0 - 175.0 * u_sq)))
            var B_v = u_sq / 1024.0 * (256.0 + u_sq * (-128.0 + u_sq * (74.0 - 47.0 * u_sq)))
            var dsig = B_v * sin_sig * (
                cos_2sigm + B_v / 4.0 * (
                    cos_sig * (-1.0 + 2.0 * cos_2sigm * cos_2sigm)
                    - B_v / 6.0 * cos_2sigm * (-3.0 + 4.0 * sin_sig * sin_sig) * (-3.0 + 4.0 * cos_2sigm * cos_2sigm)
                )
            )
            return WGS84_B * A_v * (sig - dsig) / 1000.0  # m → km

    # Fallback to haversine if Vincenty doesn't converge
    return haversine_distance(lat1, lon1, lat2, lon2)


# ── initial_bearing ──────────────────────────────────────────────────────────


fn initial_bearing(lat1: Float64, lon1: Float64, lat2: Float64, lon2: Float64) -> Float64:
    """Forward azimuth in degrees [0, 360)."""
    var p1 = _deg2rad(lat1)
    var p2 = _deg2rad(lat2)
    var dl = _deg2rad(lon2 - lon1)
    var x = sin(dl) * cos(p2)
    var y = cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(dl)
    var brng = _rad2deg(atan2(x, y))
    while brng < 0.0:
        brng += 360.0
    while brng >= 360.0:
        brng -= 360.0
    return brng


# ── destination_point ────────────────────────────────────────────────────────


fn destination_point(lat: Float64, lon: Float64, bearing_deg: Float64, distance_km: Float64) -> List[Float64]:
    """Point at distance (km) along bearing (deg). Returns [lat, lon]."""
    var p1 = _deg2rad(lat)
    var l1 = _deg2rad(lon)
    var brng = _deg2rad(bearing_deg)
    var d = distance_km / EARTH_RADIUS_KM
    var p2 = asin(sin(p1) * cos(d) + cos(p1) * sin(d) * cos(brng))
    var l2 = l1 + atan2(sin(brng) * sin(d) * cos(p1), cos(d) - sin(p1) * sin(p2))
    var result = List[Float64]()
    result.append(_rad2deg(p2))
    result.append(_rad2deg(l2))
    return result^


# ── midpoint ─────────────────────────────────────────────────────────────────


fn midpoint(lat1: Float64, lon1: Float64, lat2: Float64, lon2: Float64) -> List[Float64]:
    """Geographic midpoint [lat, lon] in degrees."""
    var p1 = _deg2rad(lat1)
    var p2 = _deg2rad(lat2)
    var l1 = _deg2rad(lon1)
    var dl = _deg2rad(lon2 - lon1)
    var bx = cos(p2) * cos(dl)
    var by = cos(p2) * sin(dl)
    var p3 = atan2(sin(p1) + sin(p2), sqrt((cos(p1) + bx) * (cos(p1) + bx) + by * by))
    var l3 = l1 + atan2(by, cos(p1) + bx)
    var result = List[Float64]()
    result.append(_rad2deg(p3))
    result.append(_rad2deg(l3))
    return result^


# ── cross_track_distance ────────────────────────────────────────────────────


fn cross_track_distance(lat: Float64, lon: Float64, start_lat: Float64, start_lon: Float64, end_lat: Float64, end_lon: Float64) -> Float64:
    """Distance in km from point to great-circle path (start→end). Absolute value."""
    var d13 = haversine_distance(start_lat, start_lon, lat, lon) / EARTH_RADIUS_KM  # angular
    var b13 = _deg2rad(initial_bearing(start_lat, start_lon, lat, lon))
    var b12 = _deg2rad(initial_bearing(start_lat, start_lon, end_lat, end_lon))
    var dxt = asin(sin(d13) * sin(b13 - b12))
    return fabs(dxt) * EARTH_RADIUS_KM


# ── along_track_distance ────────────────────────────────────────────────────


fn along_track_distance(lat: Float64, lon: Float64, start_lat: Float64, start_lon: Float64, end_lat: Float64, end_lon: Float64) -> Float64:
    """Distance in km along great-circle path to point nearest to (lat, lon)."""
    var d13 = haversine_distance(start_lat, start_lon, lat, lon) / EARTH_RADIUS_KM
    var dxt = cross_track_distance(lat, lon, start_lat, start_lon, end_lat, end_lon) / EARTH_RADIUS_KM
    var cos_dxt = cos(dxt)
    if fabs(cos_dxt) < 1e-15:
        return 0.0
    var dat = asin(sqrt(fabs(sin(d13) * sin(d13) - sin(dxt) * sin(dxt))) / cos_dxt)
    return dat * EARTH_RADIUS_KM


# ── geodetic_to_ecef ─────────────────────────────────────────────────────────


fn geodetic_to_ecef(lat: Float64, lon: Float64, alt: Float64) -> List[Float64]:
    """Convert geodetic (lat, lon, alt_m) to ECEF [x, y, z] in meters."""
    var p = _deg2rad(lat)
    var l = _deg2rad(lon)
    var e2 = 1.0 - (WGS84_B * WGS84_B) / (WGS84_A * WGS84_A)
    var sin_p = sin(p)
    var cos_p = cos(p)
    var N = WGS84_A / sqrt(1.0 - e2 * sin_p * sin_p)
    var result = List[Float64]()
    result.append((N + alt) * cos_p * cos(l))
    result.append((N + alt) * cos_p * sin(l))
    result.append((N * (1.0 - e2) + alt) * sin_p)
    return result^


# ── ecef_to_geodetic ─────────────────────────────────────────────────────────


fn ecef_to_geodetic(x: Float64, y: Float64, z: Float64) -> List[Float64]:
    """Convert ECEF (x,y,z meters) to geodetic [lat, lon, alt]. Iterative."""
    var e2 = 1.0 - (WGS84_B * WGS84_B) / (WGS84_A * WGS84_A)
    var lon = atan2(y, x)
    var p = sqrt(x * x + y * y)
    var lat = atan2(z, p * (1.0 - e2))
    for _ in range(10):
        var sin_lat = sin(lat)
        var N = WGS84_A / sqrt(1.0 - e2 * sin_lat * sin_lat)
        lat = atan2(z + e2 * N * sin_lat, p)
    var sin_lat = sin(lat)
    var N = WGS84_A / sqrt(1.0 - e2 * sin_lat * sin_lat)
    var cos_lat = cos(lat)
    var alt: Float64
    if fabs(cos_lat) > 1e-10:
        alt = p / cos_lat - N
    else:
        alt = fabs(z) - WGS84_B
    var result = List[Float64]()
    result.append(_rad2deg(lat))
    result.append(_rad2deg(lon))
    result.append(alt)
    return result^


# ── rhumb_distance ───────────────────────────────────────────────────────────


fn rhumb_distance(lat1: Float64, lon1: Float64, lat2: Float64, lon2: Float64) -> Float64:
    """Distance along rhumb line (constant bearing) in km."""
    var p1 = _deg2rad(lat1)
    var p2 = _deg2rad(lat2)
    var dp = p2 - p1
    var dl = _deg2rad(lon2 - lon1)
    # Stretch factor
    var dpsi = log(tan(PI / 4.0 + p2 / 2.0) / tan(PI / 4.0 + p1 / 2.0))
    var q: Float64
    if fabs(dpsi) > 1e-12:
        q = dp / dpsi
    else:
        q = cos(p1)
    # Normalize dl to [-pi, pi]
    while dl > PI:
        dl -= 2.0 * PI
    while dl < -PI:
        dl += 2.0 * PI
    var dist = sqrt(dp * dp + q * q * dl * dl) * EARTH_RADIUS_KM
    return dist
