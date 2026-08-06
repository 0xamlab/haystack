"""
palynology.mojo — Pollen and spore science calculations. Zero Python imports.

Public API:
  pollen_concentration          — grains per cm³ from count and volume
  pollen_accumulation_rate      — PAR from concentration and sedimentation
  taxa_diversity_index          — Shannon H' for pollen assemblage
  relative_pollen_percentage    — taxon % of total sum
  r_value_correction            — representativeness correction
  arboreal_non_arboreal_ratio   — A/NAP vegetation indicator
  pollen_influx                 — grains/cm²/yr from PAR × mass
  spore_germination_index       — from temperature sum
  pollen_productivity_estimate  — from trap vs vegetation survey
  pollen_transport_distance     — from wind speed and settling
"""
from std.math import log, sqrt, exp


def pollen_concentration(
    pollen_counted: Float64, exotic_counted: Float64,
    exotic_added: Float64, sample_volume_cm3: Float64
) -> Float64:
    """Pollen concentration from exotic spike method.

    C = (pollen × exotic_added) / (exotic_counted × volume)

    Args:
        pollen_counted: Indigenous pollen grains counted.
        exotic_counted: Exotic marker grains counted.
        exotic_added: Number of exotic grains added to sample.
        sample_volume_cm3: Sample volume (cm³).

    Returns:
        Pollen concentration (grains/cm³).
    """
    if exotic_counted <= 0.0 or sample_volume_cm3 <= 0.0:
        return 0.0
    return (pollen_counted * exotic_added) / (exotic_counted * sample_volume_cm3)


def pollen_accumulation_rate(
    concentration: Float64, sedimentation_rate_cm_yr: Float64
) -> Float64:
    """Pollen accumulation rate.

    PAR = concentration × sedimentation_rate

    Args:
        concentration: Pollen concentration (grains/cm³).
        sedimentation_rate_cm_yr: Sediment accumulation rate (cm/yr).

    Returns:
        PAR (grains/cm²/yr).
    """
    return concentration * sedimentation_rate_cm_yr


def taxa_diversity_index(proportions: Float64, n_taxa: Float64) -> Float64:
    """Simplified Shannon diversity (using mean proportion).

    H' = -Σ(pi × ln pi)  approximated from mean p for n taxa

    Args:
        proportions: Mean relative proportion of taxa (1/n approximately).
        n_taxa: Number of pollen taxa.

    Returns:
        Approximate Shannon H'.
    """
    if n_taxa <= 0.0 or proportions <= 0.0:
        return 0.0
    return -n_taxa * proportions * log(proportions)


def relative_pollen_percentage(
    taxon_count: Float64, pollen_sum: Float64
) -> Float64:
    """Relative pollen percentage of a taxon.

    RPP = (taxon / pollen_sum) × 100

    Args:
        taxon_count: Grains of the target taxon.
        pollen_sum: Total pollen sum (may exclude aquatics, spores).

    Returns:
        Relative pollen percentage (%).
    """
    if pollen_sum <= 0.0:
        return 0.0
    return taxon_count / pollen_sum * 100.0


def r_value_correction(
    relative_pollen_pct: Float64, r_value: Float64
) -> Float64:
    """Pollen representativeness correction using R-value.

    Corrected% = RPP / R_value

    Args:
        relative_pollen_pct: Observed relative pollen percentage.
        r_value: Taxon R-value (pollen productivity relative to reference).

    Returns:
        Corrected vegetation estimate (%).
    """
    if r_value <= 0.0:
        return 0.0
    return relative_pollen_pct / r_value


def arboreal_non_arboreal_ratio(
    arboreal_count: Float64, non_arboreal_count: Float64
) -> Float64:
    """Arboreal to non-arboreal pollen ratio.

    A/NAP = arboreal / (arboreal + non-arboreal)

    Args:
        arboreal_count: Total tree pollen grains.
        non_arboreal_count: Herb and shrub pollen.

    Returns:
        A/NAP ratio (>0.7 = forested, <0.3 = open).
    """
    var total = arboreal_count + non_arboreal_count
    if total <= 0.0:
        return 0.0
    return arboreal_count / total


def pollen_influx(
    par: Float64, bulk_density_g_cm3: Float64
) -> Float64:
    """Pollen influx converted using bulk sediment density.

    influx = PAR × bulk_density × 10  (grains/cm²/yr per g/cm³ basis)

    Args:
        par: Pollen accumulation rate (grains/cm²/yr).
        bulk_density_g_cm3: Sediment dry bulk density (g/cm³).

    Returns:
        Mass-normalised pollen influx (grains/g).
    """
    if bulk_density_g_cm3 <= 0.0:
        return 0.0
    return par / bulk_density_g_cm3


def spore_germination_index(
    temperature_sum: Float64, base_temperature: Float64
) -> Float64:
    """Growing degree-day index for spore germination probability.

    GDI = temperature_sum - base_temperature × days

    Args:
        temperature_sum: Accumulated degree-days above base.
        base_temperature: Minimum threshold temperature (°C).

    Returns:
        Germination probability index (0–1, sigmoid approximated).
    """
    var x = (temperature_sum - base_temperature * 30.0)
    if x <= 0.0:
        return 0.0
    var p = 1.0 - exp(-x / 200.0)
    if p > 1.0:
        return 1.0
    return p


def pollen_productivity_estimate(
    trap_count: Float64, vegetation_cover: Float64, distance_m: Float64
) -> Float64:
    """Relative pollen productivity from trap and vegetation data.

    RPP = trap_count / (vegetation_cover × distance_decay)

    Args:
        trap_count: Grains in pollen trap.
        vegetation_cover: Fractional cover of taxon around trap (0–1).
        distance_m: Mean distance of vegetation from trap (m).

    Returns:
        Relative pollen productivity (RPP value, reference = 1).
    """
    if vegetation_cover <= 0.0 or distance_m <= 0.0:
        return 0.0
    var decay = exp(-distance_m / 500.0)  # 500 m scale for wind-pollinated trees
    return trap_count / (vegetation_cover * decay + 1e-10)


def pollen_transport_distance(
    settling_velocity_m_per_s: Float64, wind_speed_m_per_s: Float64,
    release_height_m: Float64
) -> Float64:
    """Horizontal transport distance before pollen settles.

    d = wind_speed × release_height / settling_velocity

    Args:
        settling_velocity_m_per_s: Grain settling velocity (m/s, ~0.01–0.1).
        wind_speed_m_per_s: Mean wind speed (m/s).
        release_height_m: Height of pollen release (m).

    Returns:
        Approximate transport distance (m).
    """
    if settling_velocity_m_per_s <= 0.0:
        return 0.0
    return wind_speed_m_per_s * release_height_m / settling_velocity_m_per_s
