"""
astronomy.mojo — Astronomical calculations. Zero Python imports.

Replaces astropy basics with pure Mojo implementations for Julian date,
sidereal time, solar position, Kepler equation, orbital mechanics,
magnitude calculations, and coordinate transforms.

Public API:
  julian_date            — Julian Date from calendar date
  modified_julian_date   — MJD = JD - 2400000.5
  sidereal_time          — Greenwich Mean Sidereal Time + local correction
  solar_declination      — Solar declination angle in degrees
  sunrise_hour_angle     — Hour angle of sunrise
  day_length             — Hours of daylight
  parallax_correction    — Parallax angle in arcseconds
  kepler_equation        — Solve Kepler's equation for eccentric anomaly
  orbital_period         — Kepler's 3rd law
  apparent_magnitude     — m = M + 5*log10(d) - 5
  distance_from_magnitude — d = 10^((m-M+5)/5) parsecs
  ecliptic_to_equatorial — Convert ecliptic to equatorial coords
"""
from std.math import cos, sin, tan, acos, sqrt, log10, pow, floor, abs as fabs


# ── Constants ─────────────────────────────────────────────────────────────────

comptime PI: Float64 = 3.14159265358979323846
comptime DEG2RAD: Float64 = PI / 180.0
comptime RAD2DEG: Float64 = 180.0 / PI


# ── Julian Date ───────────────────────────────────────────────────────────────


fn julian_date(year: Int, month: Int, day: Int) -> Float64:
    """Julian Date from calendar date (at noon UT).
    
    Uses the algorithm from Meeus, Astronomical Algorithms.
    """
    var y = year
    var m = month
    if m <= 2:
        y -= 1
        m += 12
    var A = Int(floor(Float64(y) / 100.0))
    var B = 2 - A + Int(floor(Float64(A) / 4.0))
    var jd = floor(365.25 * Float64(y + 4716)) + floor(30.6001 * Float64(m + 1)) + Float64(day) + Float64(B) - 1524.5
    return jd


# ── Modified Julian Date ──────────────────────────────────────────────────────


fn modified_julian_date(jd: Float64) -> Float64:
    """MJD = JD - 2400000.5."""
    return jd - 2400000.5


# ── Sidereal Time ────────────────────────────────────────────────────────────


fn sidereal_time(jd: Float64, longitude: Float64) -> Float64:
    """Greenwich Mean Sidereal Time in hours + local correction.
    
    longitude in degrees (positive east).
    """
    var T = (jd - 2451545.0) / 36525.0
    # GMST in degrees
    var gmst = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * T * T - T * T * T / 38710000.0
    # Add longitude correction
    var lst = gmst + longitude
    # Normalize to [0, 360)
    lst = lst - floor(lst / 360.0) * 360.0
    if lst < 0.0:
        lst += 360.0
    # Convert to hours
    return lst / 15.0


# ── Solar Declination ─────────────────────────────────────────────────────────


fn solar_declination(day_of_year: Int) -> Float64:
    """Solar declination angle in degrees: -23.45*cos(360/365*(day+10))."""
    var angle = 360.0 / 365.0 * Float64(day_of_year + 10) * DEG2RAD
    return -23.45 * cos(angle)


# ── Sunrise Hour Angle ────────────────────────────────────────────────────────


fn sunrise_hour_angle(latitude: Float64, declination: Float64) -> Float64:
    """Hour angle of sunrise in degrees: cos⁻¹(-tan(lat)*tan(dec)).
    
    Returns 0 if no sunrise (polar night) or 180 if no sunset (midnight sun).
    """
    var lat_rad = latitude * DEG2RAD
    var dec_rad = declination * DEG2RAD
    var cos_ha = -tan(lat_rad) * tan(dec_rad)
    if cos_ha > 1.0:
        return 0.0  # No sunrise (polar night)
    if cos_ha < -1.0:
        return 180.0  # No sunset (midnight sun)
    return acos(cos_ha) * RAD2DEG


# ── Day Length ────────────────────────────────────────────────────────────────


fn day_length(latitude: Float64, day_of_year: Int) -> Float64:
    """Hours of daylight."""
    var dec = solar_declination(day_of_year)
    var ha = sunrise_hour_angle(latitude, dec)
    # Day length = 2 * hour_angle / 15 (15 degrees per hour)
    return 2.0 * ha / 15.0


# ── Parallax Correction ──────────────────────────────────────────────────────


fn parallax_correction(distance_au: Float64, radius_earth: Float64) -> Float64:
    """Parallax angle in arcseconds.
    
    p = arctan(R_earth / d) converted to arcseconds.
    For small angles: p ≈ R_earth / d (radians) * 206265.
    """
    if distance_au <= 0.0:
        return 0.0
    # 1 AU = 1.496e11 m; radius_earth typically ~6.371e6 m
    # parallax = atan(R/d) ≈ R/d for small angles, in arcseconds
    var d_meters = distance_au * 1.496e11
    var p_rad = radius_earth / d_meters
    return p_rad * 206265.0  # radians to arcseconds


# ── Kepler Equation ───────────────────────────────────────────────────────────


fn kepler_equation(M: Float64, e: Float64, tol: Float64 = 1e-10) -> Float64:
    """Solve M = E - e*sin(E) for E via Newton's method.
    
    M: mean anomaly in radians.
    e: eccentricity.
    Returns E (eccentric anomaly) in radians.
    """
    var E = M  # Initial guess
    var max_iter = 100
    for _ in range(max_iter):
        var dE = (E - e * sin(E) - M) / (1.0 - e * cos(E))
        E -= dE
        if fabs(dE) < tol:
            break
    return E


# ── Orbital Period ────────────────────────────────────────────────────────────


fn orbital_period(semi_major_au: Float64) -> Float64:
    """Kepler's 3rd law: T = a^(3/2) years (for solar system)."""
    return pow(semi_major_au, 1.5)


# ── Apparent Magnitude ────────────────────────────────────────────────────────


fn apparent_magnitude(abs_mag: Float64, distance_pc: Float64) -> Float64:
    """m = M + 5*log10(d) - 5. Distance in parsecs."""
    if distance_pc <= 0.0:
        return 0.0
    return abs_mag + 5.0 * log10(distance_pc) - 5.0


# ── Distance from Magnitude ──────────────────────────────────────────────────


fn distance_from_magnitude(abs_mag: Float64, app_mag: Float64) -> Float64:
    """d = 10^((m-M+5)/5) parsecs."""
    return pow(10.0, (app_mag - abs_mag + 5.0) / 5.0)


# ── Ecliptic to Equatorial ───────────────────────────────────────────────────


fn ecliptic_to_equatorial(
    ecliptic_lon: Float64, ecliptic_lat: Float64, obliquity: Float64
) -> List[Float64]:
    """Convert ecliptic to equatorial [RA, Dec] in degrees.
    
    All inputs in degrees. obliquity ≈ 23.4393° for J2000.
    """
    var lon_r = ecliptic_lon * DEG2RAD
    var lat_r = ecliptic_lat * DEG2RAD
    var eps_r = obliquity * DEG2RAD

    # sin(dec) = sin(lat)*cos(eps) + cos(lat)*sin(eps)*sin(lon)
    var sin_dec = sin(lat_r) * cos(eps_r) + cos(lat_r) * sin(eps_r) * sin(lon_r)
    # Clamp
    if sin_dec > 1.0:
        sin_dec = 1.0
    if sin_dec < -1.0:
        sin_dec = -1.0
    var dec = acos(sqrt(1.0 - sin_dec * sin_dec)) * RAD2DEG
    if sin_dec < 0.0:
        dec = -dec

    # tan(RA) = (sin(lon)*cos(eps) - tan(lat)*sin(eps)) / cos(lon)
    var y_val = sin(lon_r) * cos(eps_r) - tan(lat_r) * sin(eps_r)
    var x_val = cos(lon_r)
    # atan2 approximation
    var ra_rad = _atan2(y_val, x_val)
    var ra = ra_rad * RAD2DEG
    # Normalize to [0, 360)
    ra = ra - floor(ra / 360.0) * 360.0
    if ra < 0.0:
        ra += 360.0

    var result = List[Float64]()
    result.append(ra)
    result.append(dec)
    return result^


fn _atan2(y: Float64, x: Float64) -> Float64:
    """atan2(y, x) using acos and sign."""
    var r = sqrt(x * x + y * y)
    if r < 1e-15:
        return 0.0
    var angle = acos(x / r)
    if y < 0.0:
        angle = -angle
    return angle
