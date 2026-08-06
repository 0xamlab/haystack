"""
silviculture.mojo — Forest management and timber production calculations. Zero Python imports.

Public API:
  basal_area                   — BA = π*(DBH/2)² per tree
  stand_basal_area             — sum BA over trees per hectare
  site_index                   — SI from height and age
  volume_scribner              — log volume in board feet (Scribner)
  timber_yield_per_ha          — from stand density and mean volume
  relative_density_index       — RDI from stand density and mean DBH
  reineke_sdi                  — Stand Density Index (Reineke)
  mean_annual_increment        — MAI = total_volume / age
  current_annual_increment     — CAI from two volume measurements
  thinning_ratio               — desired residual stems after thinning
"""
from std.math import sqrt, log, pow


def basal_area(dbh_cm: Float64) -> Float64:
    """Basal area of a single tree from diameter at breast height.

    BA = π·(DBH/2)²

    Args:
        dbh_cm: Diameter at breast height (cm).

    Returns:
        Basal area (cm²).
    """
    if dbh_cm <= 0.0:
        return 0.0
    var pi = 3.141592653589793
    var r = dbh_cm / 2.0
    return pi * r * r


def stand_basal_area(mean_dbh_cm: Float64, stems_per_ha: Float64) -> Float64:
    """Stand-level basal area (m²/ha).

    Args:
        mean_dbh_cm: Mean DBH of stand (cm).
        stems_per_ha: Number of stems per hectare.

    Returns:
        Stand basal area (m²/ha).
    """
    if mean_dbh_cm <= 0.0 or stems_per_ha <= 0.0:
        return 0.0
    var pi = 3.141592653589793
    var r_m = mean_dbh_cm / 200.0  # cm → m, then /2 for radius
    return pi * r_m * r_m * stems_per_ha


def site_index(height_m: Float64, age_years: Float64, base_age: Float64) -> Float64:
    """Site index: dominant height at base age.

    SI = H · (base_age / age)^b  where b = 0.5 (simplified).

    Args:
        height_m: Current dominant height (m).
        age_years: Current stand age (years).
        base_age: Reference age for site index (typically 50 years).

    Returns:
        Site index (m).
    """
    if age_years <= 0.0 or height_m <= 0.0:
        return 0.0
    return height_m * pow(base_age / age_years, 0.5)


def volume_scribner(small_end_diameter_in: Float64, log_length_ft: Float64) -> Float64:
    """Log volume using Scribner Decimal C rule (approximate).

    V ≈ ((0.79 D² - 2D - 4) · L) / 16

    Args:
        small_end_diameter_in: Small-end diameter inside bark (inches).
        log_length_ft: Log length (feet).

    Returns:
        Log volume (board feet).
    """
    if small_end_diameter_in <= 0.0 or log_length_ft <= 0.0:
        return 0.0
    var d = small_end_diameter_in
    return (0.79 * d * d - 2.0 * d - 4.0) * log_length_ft / 16.0


def timber_yield_per_ha(
    stems_per_ha: Float64, mean_vol_m3_per_tree: Float64
) -> Float64:
    """Standing timber volume per hectare.

    Args:
        stems_per_ha: Stocking density (stems/ha).
        mean_vol_m3_per_tree: Mean individual tree volume (m³).

    Returns:
        Stand volume (m³/ha).
    """
    if stems_per_ha < 0.0 or mean_vol_m3_per_tree < 0.0:
        return 0.0
    return stems_per_ha * mean_vol_m3_per_tree


def relative_density_index(
    stems_per_ha: Float64, mean_dbh_cm: Float64
) -> Float64:
    """Relative Density Index (Curtis 1982): RDI = N / (25.4/DBH)^1.6.

    Args:
        stems_per_ha: Stand density (stems/ha).
        mean_dbh_cm: Mean DBH (cm).

    Returns:
        Relative density index.
    """
    if stems_per_ha <= 0.0 or mean_dbh_cm <= 0.0:
        return 0.0
    return stems_per_ha / pow(25.4 / mean_dbh_cm, 1.6)


def reineke_sdi(stems_per_ha: Float64, mean_dbh_cm: Float64) -> Float64:
    """Reineke Stand Density Index.

    SDI = N · (25.4 / DBH)^1.605

    Args:
        stems_per_ha: Number of stems per hectare.
        mean_dbh_cm: Mean DBH (cm).

    Returns:
        Reineke SDI.
    """
    if stems_per_ha <= 0.0 or mean_dbh_cm <= 0.0:
        return 0.0
    return stems_per_ha * pow(25.4 / mean_dbh_cm, 1.605)


def mean_annual_increment(total_volume_m3: Float64, age_years: Float64) -> Float64:
    """Mean annual increment: MAI = total volume / age.

    Args:
        total_volume_m3: Cumulative stand volume (m³/ha).
        age_years: Stand age (years).

    Returns:
        MAI (m³/ha/yr).
    """
    if age_years <= 0.0:
        return 0.0
    return total_volume_m3 / age_years


def current_annual_increment(
    vol_now: Float64, vol_past: Float64, years: Float64
) -> Float64:
    """Current annual increment over a measurement period.

    CAI = (V2 - V1) / years

    Args:
        vol_now: Volume at end of period (m³/ha).
        vol_past: Volume at start (m³/ha).
        years: Length of period (years).

    Returns:
        CAI (m³/ha/yr).
    """
    if years <= 0.0:
        return 0.0
    return (vol_now - vol_past) / years


def thinning_ratio(
    initial_stems: Float64, target_stems: Float64
) -> Float64:
    """Fraction of trees to remove in a thinning operation.

    Args:
        initial_stems: Pre-thinning stand density (stems/ha).
        target_stems: Post-thinning desired density (stems/ha).

    Returns:
        Thinning ratio (fraction removed, 0–1).
    """
    if initial_stems <= 0.0:
        return 0.0
    var removed = initial_stems - target_stems
    if removed < 0.0:
        return 0.0
    return removed / initial_stems
