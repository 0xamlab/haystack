"""
geophysics.mojo — Earth physics and geophysical exploration calculations. Zero Python imports.

Public API:
  gravity_anomaly_bouguer      — Bouguer gravity correction
  gravitational_acceleration   — g at latitude and elevation
  magnetic_inclination         — dip angle from field components
  seismic_p_wave_velocity      — Vp from elastic moduli
  seismic_s_wave_velocity      — Vs from shear modulus and density
  depth_from_reflection        — depth from travel time
  vp_vs_ratio                  — Poisson's ratio from Vp/Vs
  earth_radius_at_latitude     — geocentric radius
  free_air_correction          — FAC = 0.3086 * h mGal/m
  isostasy_airy                — crustal thickness from topography
"""
from std.math import sqrt, sin, cos, log, pow


def gravity_anomaly_bouguer(
    observed_g: Float64, latitude_rad: Float64, elevation_m: Float64, rock_density: Float64
) -> Float64:
    """Bouguer gravity anomaly.

    Δg_B = g_obs - g_theoretical + FAC - Bouguer_correction

    Args:
        observed_g: Observed gravity (mGal).
        latitude_rad: Latitude (rad).
        elevation_m: Station elevation (m).
        rock_density: Average rock density (g/cm³).

    Returns:
        Bouguer anomaly (mGal).
    """
    # Theoretical gravity (GRS80 simplified)
    var g_th = 978032.7 * (1.0 + 0.005302 * sin(latitude_rad) ** 2.0
               - 0.0000058 * sin(2.0 * latitude_rad) ** 2.0) / 1000.0
    var fac = 0.3086 * elevation_m   # mGal
    var bouguer = 0.04191 * rock_density * elevation_m  # mGal
    return observed_g - g_th + fac - bouguer


def gravitational_acceleration(latitude_rad: Float64, elevation_m: Float64) -> Float64:
    """Gravitational acceleration at a given latitude and elevation.

    g(φ, h) ≈ g_e·(1 + 0.00193185·sin²φ)·(1 - 2h/Re)

    Args:
        latitude_rad: Geographic latitude (rad).
        elevation_m: Elevation above sea level (m).

    Returns:
        Gravitational acceleration (m/s²).
    """
    var ge = 9.7803267714
    var re = 6.371e6  # mean Earth radius m
    var s = sin(latitude_rad)
    var g_lat = ge * (1.0 + 0.00193185 * s * s)
    return g_lat * (1.0 - 2.0 * elevation_m / re)


def magnetic_inclination(bz: Float64, bh: Float64) -> Float64:
    """Magnetic inclination (dip) angle from vertical and horizontal components.

    I = atan(Bz / Bh)  returned as ratio (tan I)

    Args:
        bz: Vertical magnetic field component (nT).
        bh: Horizontal field magnitude (nT).

    Returns:
        Tangent of inclination angle (dimensionless).
    """
    if bh == 0.0:
        return 1e9  # vertical field
    return bz / bh


def seismic_p_wave_velocity(
    bulk_modulus: Float64, shear_modulus: Float64, density: Float64
) -> Float64:
    """P-wave velocity: Vp = sqrt((K + 4G/3) / ρ).

    Args:
        bulk_modulus: Bulk modulus K (GPa).
        shear_modulus: Shear modulus G (GPa).
        density: Rock density (kg/m³).

    Returns:
        P-wave velocity (m/s).
    """
    if density <= 0.0:
        return 0.0
    var M = (bulk_modulus + 4.0 * shear_modulus / 3.0) * 1e9  # GPa → Pa
    return sqrt(M / density)


def seismic_s_wave_velocity(shear_modulus: Float64, density: Float64) -> Float64:
    """S-wave velocity: Vs = sqrt(G / ρ).

    Args:
        shear_modulus: Shear modulus G (GPa).
        density: Rock density (kg/m³).

    Returns:
        S-wave velocity (m/s).
    """
    if density <= 0.0:
        return 0.0
    return sqrt(shear_modulus * 1e9 / density)


def depth_from_reflection(two_way_time: Float64, velocity: Float64) -> Float64:
    """Depth from seismic two-way travel time.

    d = v · t_TWT / 2

    Args:
        two_way_time: Two-way travel time (s).
        velocity: Average interval velocity (m/s).

    Returns:
        Reflector depth (m).
    """
    return velocity * two_way_time / 2.0


def vp_vs_ratio(vp: Float64, vs: Float64) -> Float64:
    """Vp/Vs ratio (related to Poisson's ratio).

    σ = (Vp² - 2Vs²) / (2·(Vp² - Vs²))

    Args:
        vp: P-wave velocity (m/s).
        vs: S-wave velocity (m/s).

    Returns:
        Poisson's ratio σ.
    """
    if vs <= 0.0:
        return 0.5
    var r = vp / vs
    var num = r * r - 2.0
    var den = 2.0 * (r * r - 1.0)
    if den <= 0.0:
        return 0.5
    return num / den


def earth_radius_at_latitude(latitude_rad: Float64) -> Float64:
    """Geocentric Earth radius at a given latitude.

    Args:
        latitude_rad: Latitude (rad).

    Returns:
        Geocentric radius (m).
    """
    var a = 6378137.0      # equatorial radius m
    var b = 6356752.314    # polar radius m
    var cos_lat = cos(latitude_rad)
    var sin_lat = sin(latitude_rad)
    var num = (a * a * cos_lat) ** 2.0 + (b * b * sin_lat) ** 2.0
    var den = (a * cos_lat) ** 2.0 + (b * sin_lat) ** 2.0
    if den <= 0.0:
        return a
    return sqrt(num / den)


def free_air_correction(elevation_m: Float64) -> Float64:
    """Free-air gravity correction: FAC = 0.3086·h mGal.

    Args:
        elevation_m: Station elevation above geoid (m).

    Returns:
        Free-air correction (mGal). Add to observed gravity.
    """
    return 0.3086 * elevation_m


def isostasy_airy(
    topography_m: Float64, crust_density: Float64, mantle_density: Float64
) -> Float64:
    """Airy isostasy: crustal root thickness below sea level.

    t_root = h · ρ_crust / (ρ_mantle - ρ_crust)

    Args:
        topography_m: Topography above sea level (m).
        crust_density: Crustal density (kg/m³).
        mantle_density: Upper mantle density (kg/m³).

    Returns:
        Crustal root depth (m).
    """
    var drho = mantle_density - crust_density
    if drho <= 0.0:
        return 0.0
    return topography_m * crust_density / drho
