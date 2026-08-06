"""
dendrology.mojo — Tree biology and forest structure calculations. Zero Python imports.

Public API:
  tree_height_from_hypsometer   — trigonometric height estimation
  crown_area                    — from crown radii measurements
  crown_competition_factor      — CCF for stand density
  stem_taper_percentage         — form quotient
  heartwood_ratio               — heartwood vs sapwood proportion
  sapwood_area_from_dbh         — allometric estimate
  root_biomass_allometric       — from stem diameter
  leaf_biomass_allometric       — from DBH and height
  tree_age_from_rings           — core sample ring count
  foliar_nitrogen_content       — from specific leaf area
"""
from std.math import sqrt, log, exp, pow


def tree_height_from_hypsometer(
    distance_m: Float64, angle_top_deg: Float64, angle_base_deg: Float64
) -> Float64:
    """Tree height by trigonometry using clinometer readings.

    H = distance × (tan(α_top) + tan(α_base))

    Args:
        distance_m: Horizontal distance from tree (m).
        angle_top_deg: Angle to tree top (degrees, positive upward).
        angle_base_deg: Angle to tree base (degrees, negative if below horizontal).

    Returns:
        Tree height (m).
    """
    var pi = 3.141592653589793
    var a_top = angle_top_deg * pi / 180.0
    var a_base = angle_base_deg * pi / 180.0
    var tan_top = sin_approx(a_top) / (cos_approx(a_top) + 1e-15)
    var tan_base = sin_approx(a_base) / (cos_approx(a_base) + 1e-15)
    return distance_m * (tan_top + tan_base)


def sin_approx(x: Float64) -> Float64:
    var x2 = x * x
    return x * (1.0 - x2 / 6.0 + x2 * x2 / 120.0)


def cos_approx(x: Float64) -> Float64:
    var x2 = x * x
    return 1.0 - x2 / 2.0 + x2 * x2 / 24.0


def crown_area(
    crown_radius_ns_m: Float64, crown_radius_ew_m: Float64
) -> Float64:
    """Crown projection area assuming elliptical shape.

    A = π × r_NS × r_EW

    Args:
        crown_radius_ns_m: Crown radius in N-S direction (m).
        crown_radius_ew_m: Crown radius in E-W direction (m).

    Returns:
        Crown projection area (m²).
    """
    var pi = 3.141592653589793
    return pi * crown_radius_ns_m * crown_radius_ew_m


def crown_competition_factor(
    dbh_cm: Float64, n_trees_per_ha: Float64
) -> Float64:
    """Crown competition factor: CCF = sum(crown_area%) per ha.

    Simplified: CCF = n × 0.001257 × DBH^1.7  per ha

    Args:
        dbh_cm: Mean DBH (cm).
        n_trees_per_ha: Stand density (trees/ha).

    Returns:
        CCF (%; >100 = crowns overlap, closed canopy).
    """
    return n_trees_per_ha * 0.001257 * pow(dbh_cm, 1.7)


def stem_taper_percentage(
    dbh_cm: Float64, diameter_half_height_cm: Float64
) -> Float64:
    """Form quotient: ratio of mid-stem diameter to DBH.

    q = d_h/2 / DBH

    Args:
        dbh_cm: Diameter at breast height (cm).
        diameter_half_height_cm: Diameter at half tree height (cm).

    Returns:
        Form quotient (0.6–0.8 for most conifers).
    """
    if dbh_cm <= 0.0:
        return 0.0
    return diameter_half_height_cm / dbh_cm


def heartwood_ratio(
    heartwood_radius_cm: Float64, total_radius_cm: Float64
) -> Float64:
    """Heartwood area ratio.

    HWR = (r_hw / r_total)²

    Args:
        heartwood_radius_cm: Heartwood radius (cm).
        total_radius_cm: Total stem radius to bark (cm).

    Returns:
        Heartwood fraction of cross-sectional area.
    """
    if total_radius_cm <= 0.0:
        return 0.0
    var ratio = heartwood_radius_cm / total_radius_cm
    return ratio * ratio


def sapwood_area_from_dbh(dbh_cm: Float64, species_factor: Float64) -> Float64:
    """Sapwood area allometric estimate.

    SA = k × DBH^1.8  (species-specific k)

    Args:
        dbh_cm: DBH (cm).
        species_factor: Species-specific scaling factor k (cm² / cm^1.8).

    Returns:
        Sapwood area (cm²).
    """
    return species_factor * pow(dbh_cm, 1.8)


def root_biomass_allometric(dbh_cm: Float64) -> Float64:
    """Coarse root biomass from DBH (global allometric, Cairns 1997).

    root_biomass = exp(-1.0587 + 0.8836 × ln(above_ground_biomass))
    Simplified: root = 0.26 × (0.0673 × DBH^2.42)

    Args:
        dbh_cm: DBH (cm).

    Returns:
        Coarse root biomass (kg dry weight).
    """
    var agb = 0.0673 * pow(dbh_cm, 2.42)
    return 0.26 * agb


def leaf_biomass_allometric(dbh_cm: Float64, height_m: Float64) -> Float64:
    """Leaf biomass from DBH and height.

    leaf_mass = 0.11 × DBH^1.6 × H^0.5

    Args:
        dbh_cm: DBH (cm).
        height_m: Tree height (m).

    Returns:
        Leaf biomass (kg dry weight).
    """
    return 0.11 * pow(dbh_cm, 1.6) * sqrt(height_m)


def tree_age_from_rings(
    ring_count: Float64, pith_offset_rings: Float64
) -> Float64:
    """Estimated tree age from increment core ring count.

    age = rings_counted + pith_offset

    Args:
        ring_count: Annual rings counted on core.
        pith_offset_rings: Estimated rings to pith not captured.

    Returns:
        Estimated age (years).
    """
    return ring_count + pith_offset_rings


def foliar_nitrogen_content(
    leaf_n_mg_g: Float64, specific_leaf_area_m2_kg: Float64
) -> Float64:
    """Area-based foliar nitrogen from mass-based content and SLA.

    N_area = N_mass / SLA

    Args:
        leaf_n_mg_g: Leaf nitrogen content (mg N / g leaf DW).
        specific_leaf_area_m2_kg: SLA (m² / kg; typical 5–20).

    Returns:
        Area-based foliar N (g N / m²).
    """
    if specific_leaf_area_m2_kg <= 0.0:
        return 0.0
    return leaf_n_mg_g / specific_leaf_area_m2_kg
