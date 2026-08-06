"""
taphonomy.mojo — Fossilisation and post-mortem biological change calculations.
Zero Python imports.

Public API:
  organic_decay_rate            — first-order soft tissue decay
  bone_density_loss             — diagenetic density reduction
  fossil_completeness           — preserved skeletal fraction
  permineralisation_rate        — mineral infill from porosity
  trampling_abrasion_index      — surface modification score
  hydraulic_sorting_index       — size/density sorting during transport
  time_averaged_assemblage      — time averaging from burial rate
  preservation_potential        — from mineralogy and environment
  diagenetic_alteration_index   — bone crystallinity change
  carbon_nitrogen_ratio_bone    — C:N quality indicator
"""
from std.math import log, exp, sqrt


def organic_decay_rate(
    initial_mass: Float64, remaining_mass: Float64, time_days: Float64
) -> Float64:
    """First-order soft tissue decay rate constant.

    k = -ln(m_t / m_0) / t

    Args:
        initial_mass: Initial soft tissue mass (g).
        remaining_mass: Remaining mass at time t.
        time_days: Elapsed time (days).

    Returns:
        Decay rate k (per day).
    """
    if initial_mass <= 0.0 or remaining_mass <= 0.0 or time_days <= 0.0:
        return 0.0
    return -log(remaining_mass / initial_mass) / time_days


def bone_density_loss(
    initial_density: Float64, time_years: Float64, leaching_rate: Float64
) -> Float64:
    """Exponential bone mineral density reduction from diagenesis.

    ρ(t) = ρ₀ × exp(-k × t)

    Args:
        initial_density: Fresh bone density (g/cm³, ~1.9).
        time_years: Time since death (years).
        leaching_rate: Mineral dissolution rate constant k (per year).

    Returns:
        Bone density at time t (g/cm³).
    """
    return initial_density * exp(-leaching_rate * time_years)


def fossil_completeness(
    preserved_elements: Float64, total_skeletal_elements: Float64
) -> Float64:
    """Skeletal completeness index.

    SC = preserved / total × 100

    Args:
        preserved_elements: Number of preserved skeletal elements.
        total_skeletal_elements: Total elements in the body plan.

    Returns:
        Completeness (%; 100 = articulated complete skeleton).
    """
    if total_skeletal_elements <= 0.0:
        return 0.0
    return preserved_elements / total_skeletal_elements * 100.0


def permineralisation_rate(
    porosity: Float64, mineral_saturation: Float64, permeability: Float64
) -> Float64:
    """Mineral infill rate of bone/wood pores.

    rate = porosity × saturation × permeability

    Args:
        porosity: Void fraction of organic material (0–1).
        mineral_saturation: Mineralising fluid saturation index (>1 = oversaturated).
        permeability: Fluid permeability (darcy units).

    Returns:
        Permineralisation index (higher = faster infilling).
    """
    return porosity * mineral_saturation * permeability


def trampling_abrasion_index(
    surface_area_modified: Float64, total_surface_area: Float64,
    depth_modification_mm: Float64
) -> Float64:
    """Surface modification score from trampling.

    TAI = (area_modified / total) × depth_mm

    Args:
        surface_area_modified: Abraded/scratched surface area (cm²).
        total_surface_area: Total bone/shell surface area (cm²).
        depth_modification_mm: Mean scratch/abrasion depth (mm).

    Returns:
        Trampling abrasion index.
    """
    if total_surface_area <= 0.0:
        return 0.0
    return (surface_area_modified / total_surface_area) * depth_modification_mm


def hydraulic_sorting_index(
    element_size_mm: Float64, element_density: Float64,
    transport_velocity: Float64
) -> Float64:
    """Hydraulic equivalence index for skeletal element transport potential.

    HSI = size_mm × density / transport_velocity

    Args:
        element_size_mm: Bone/element size (mm).
        element_density: Density (g/cm³).
        transport_velocity: Stream velocity (m/s).

    Returns:
        Hydraulic sorting index (higher = settles faster = less transport bias).
    """
    if transport_velocity <= 0.0:
        return 0.0
    return element_size_mm * element_density / (transport_velocity * 1000.0)


def time_averaged_assemblage(
    sedimentation_rate_mm_per_yr: Float64, mixing_depth_mm: Float64
) -> Float64:
    """Time averaging estimate from sedimentation and bioturbation.

    T_avg = mixing_depth / sedimentation_rate

    Args:
        sedimentation_rate_mm_per_yr: Accumulation rate (mm/yr).
        mixing_depth_mm: Depth of biological mixing (mm).

    Returns:
        Time averaging duration (years).
    """
    if sedimentation_rate_mm_per_yr <= 0.0:
        return 0.0
    return mixing_depth_mm / sedimentation_rate_mm_per_yr


def preservation_potential(
    mineralogy_score: Float64, burial_depth_m: Float64, oxygen_exposure_h: Float64
) -> Float64:
    """Preservation potential index.

    PP = mineralogy × depth / (1 + oxygen_exposure)

    Args:
        mineralogy_score: Skeleton mineralogy resistance (1–5 scale).
        burial_depth_m: Burial depth (m, deeper = better).
        oxygen_exposure_h: Time exposed to oxic conditions (h).

    Returns:
        Preservation potential index.
    """
    return mineralogy_score * burial_depth_m / (1.0 + oxygen_exposure_h / 24.0)


def diagenetic_alteration_index(
    crystallinity_index_fossil: Float64, crystallinity_index_fresh: Float64
) -> Float64:
    """Bone crystallinity alteration from diagenesis.

    DAI = CI_fossil - CI_fresh  (FTIR-derived)

    Args:
        crystallinity_index_fossil: Fossil bone CI (Weiner & Bar-Yosef, FTIR).
        crystallinity_index_fresh: Fresh bone CI (~2.9–3.2).

    Returns:
        DAI (positive = increased crystallinity from recrystallisation).
    """
    return crystallinity_index_fossil - crystallinity_index_fresh


def carbon_nitrogen_ratio_bone(
    carbon_wt_pct: Float64, nitrogen_wt_pct: Float64
) -> Float64:
    """Atomic C:N ratio as collagen quality indicator.

    C:N = (C% / 12) / (N% / 14)  (molar ratio)

    Args:
        carbon_wt_pct: Bulk carbon content (wt%).
        nitrogen_wt_pct: Bulk nitrogen content (wt%).

    Returns:
        Atomic C:N ratio (3.0–3.6 = good collagen, outside = diagenetically altered).
    """
    if nitrogen_wt_pct <= 0.0:
        return 0.0
    return (carbon_wt_pct / 12.011) / (nitrogen_wt_pct / 14.007)
