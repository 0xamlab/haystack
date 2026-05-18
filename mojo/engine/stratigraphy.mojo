"""
stratigraphy.mojo — Rock layer science and geochronology calculations. Zero Python imports.

Public API:
  sedimentation_rate           — rate from thickness and time
  age_from_depth               — age at depth with constant rate
  radiometric_age              — t from parent/daughter ratio
  radiocarbon_age              — 14C age from activity ratio
  stratigraphic_column_depth   — cumulative depth from layer sequence
  isotope_fractionation        — delta notation from ratio
  unconformity_gap             — missing time from erosion
  thermal_maturity_vitrinite   — Ro from burial temperature
  compaction_correction        — decompacted thickness
  sea_level_proxy              — relative SL from d18O
"""
from std.math import log, exp, sqrt


fn sedimentation_rate(thickness_m: Float64, duration_my: Float64) -> Float64:
    """Sedimentation rate: SR = thickness / time.

    Args:
        thickness_m: Stratigraphic thickness (m).
        duration_my: Duration of deposition (Ma).

    Returns:
        Sedimentation rate (m/Ma).
    """
    if duration_my <= 0.0:
        return 0.0
    return thickness_m / duration_my


fn age_from_depth(
    depth_m: Float64, surface_age_ma: Float64, sed_rate: Float64
) -> Float64:
    """Age at a given depth below surface.

    age = surface_age + depth / sed_rate

    Args:
        depth_m: Depth below surface (m).
        surface_age_ma: Age at surface (Ma).
        sed_rate: Sedimentation rate (m/Ma).

    Returns:
        Age at depth (Ma).
    """
    if sed_rate <= 0.0:
        return surface_age_ma
    return surface_age_ma + depth_m / sed_rate


fn radiometric_age(
    parent_to_daughter_ratio: Float64, decay_constant: Float64
) -> Float64:
    """Radiometric age from parent/daughter isotope ratio.

    t = ln(1 + D/P) / λ

    Args:
        parent_to_daughter_ratio: Daughter / parent ratio (D/P).
        decay_constant: Decay constant λ (Ma⁻¹).

    Returns:
        Age (Ma).
    """
    if decay_constant <= 0.0 or parent_to_daughter_ratio < 0.0:
        return 0.0
    return log(1.0 + parent_to_daughter_ratio) / decay_constant


fn radiocarbon_age(
    activity_fraction: Float64
) -> Float64:
    """Radiocarbon age from fraction of modern carbon (F14C).

    t = -8267 * ln(F14C)   (8267 = T½/ln2 for 14C)

    Args:
        activity_fraction: Fraction of modern 14C activity (F14C).

    Returns:
        Conventional radiocarbon age (14C years BP).
    """
    if activity_fraction <= 0.0 or activity_fraction > 1.0:
        return 0.0
    return -8267.0 * log(activity_fraction)


fn stratigraphic_column_depth(
    layer_thickness1: Float64, layer_thickness2: Float64, n_layers: Float64
) -> Float64:
    """Total depth of a stratigraphic column from repeated layer pairs.

    depth = (t1 + t2) * n_layers / 2  (simplified average)

    Args:
        layer_thickness1: Typical thin layer thickness (m).
        layer_thickness2: Typical thick layer thickness (m).
        n_layers: Number of couplets.

    Returns:
        Total stratigraphic thickness (m).
    """
    return (layer_thickness1 + layer_thickness2) * n_layers / 2.0


fn isotope_fractionation(
    sample_ratio: Float64, standard_ratio: Float64
) -> Float64:
    """Isotope delta notation: δ = (R_sample/R_standard - 1) × 1000.

    Args:
        sample_ratio: Isotope ratio in sample (e.g. ¹³C/¹²C).
        standard_ratio: Reference standard ratio.

    Returns:
        Delta value (‰, per mille).
    """
    if standard_ratio <= 0.0:
        return 0.0
    return (sample_ratio / standard_ratio - 1.0) * 1000.0


fn unconformity_gap(
    section_above_age: Float64, section_below_age: Float64
) -> Float64:
    """Time gap at an unconformity.

    gap = age_below - age_above

    Args:
        section_above_age: Age of strata above unconformity (Ma).
        section_below_age: Age of strata below unconformity (Ma).

    Returns:
        Hiatus duration (Ma).
    """
    var gap = section_below_age - section_above_age
    if gap < 0.0:
        return 0.0
    return gap


fn thermal_maturity_vitrinite(max_temperature: Float64, duration_my: Float64) -> Float64:
    """Vitrinite reflectance from peak burial temperature (simplified).

    Ro ≈ exp(0.0078 * T_max - 1.2) + 0.2  (approximate Barker 1988)

    Args:
        max_temperature: Maximum burial temperature (°C).
        duration_my: Duration at max temperature (Ma).

    Returns:
        Vitrinite reflectance Ro (%).
    """
    # Simple time-temperature approximation
    var ro = exp(0.0078 * max_temperature - 1.2) * (1.0 + 0.01 * log(duration_my + 1.0))
    if ro < 0.2:
        return 0.2
    return ro


fn compaction_correction(
    observed_thickness: Float64, initial_porosity: Float64, current_porosity: Float64
) -> Float64:
    """Decompacted (original) thickness of a sediment layer.

    T_decompacted = T_obs * (1 - φ_current) / (1 - φ_initial)

    Args:
        observed_thickness: Present-day compacted thickness (m).
        initial_porosity: Depositional porosity (fraction).
        current_porosity: Present-day porosity (fraction).

    Returns:
        Original decompacted thickness (m).
    """
    var denom = 1.0 - initial_porosity
    if denom <= 0.0:
        return observed_thickness
    return observed_thickness * (1.0 - current_porosity) / denom


fn sea_level_proxy(
    d18o_benthic: Float64, d18o_reference: Float64, ice_volume_factor: Float64
) -> Float64:
    """Relative sea-level change from benthic δ¹⁸O record.

    ΔRSL ≈ -ice_volume_factor * (δ18O - δ18O_ref)

    Args:
        d18o_benthic: Benthic foram δ¹⁸O (‰ VPDB).
        d18o_reference: Reference (interglacial) δ¹⁸O value (‰).
        ice_volume_factor: m sea level per ‰ δ¹⁸O (~100 m/‰ typically).

    Returns:
        Relative sea level change (m). Positive = higher SL.
    """
    return -ice_volume_factor * (d18o_benthic - d18o_reference)
