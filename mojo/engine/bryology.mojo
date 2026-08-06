"""
bryology.mojo — Moss, liverwort, and hornwort science calculations. Zero Python imports.

Public API:
  sphagnum_water_holding         — water retention from porosity
  moss_growth_rate               — dry mass accumulation
  carbon_accumulation_peatland   — from moss productivity and decomposition
  bryophyte_desiccation_recovery — rehydration kinetics
  nitrogen_deposition_effect     — growth response to N loading
  moss_photosynthesis_rate       — from light and water potential
  peat_accumulation_rate         — net from production minus decay
  sphagnum_acidity               — pH from ion exchange
  patch_colonisation_probability — dispersal × establishment
  biomass_to_litter_ratio        — turnover index
"""
from std.math import exp, log, sqrt


def sphagnum_water_holding(
    dry_mass_g: Float64, saturated_mass_g: Float64
) -> Float64:
    """Water holding capacity of Sphagnum: WHC = (W_sat - W_dry) / W_dry.

    Args:
        dry_mass_g: Oven-dried Sphagnum mass (g).
        saturated_mass_g: Water-saturated mass (g).

    Returns:
        WHC (g water / g dry mass; Sphagnum ≈ 15–30).
    """
    if dry_mass_g <= 0.0:
        return 0.0
    return (saturated_mass_g - dry_mass_g) / dry_mass_g


def moss_growth_rate(
    initial_mass_g: Float64, final_mass_g: Float64, days: Float64
) -> Float64:
    """Specific growth rate of moss: r = ln(m_f / m_i) / t.

    Args:
        initial_mass_g: Initial dry mass (g).
        final_mass_g: Final dry mass (g).
        days: Growth period (days).

    Returns:
        Specific growth rate (per day).
    """
    if initial_mass_g <= 0.0 or final_mass_g <= 0.0 or days <= 0.0:
        return 0.0
    return log(final_mass_g / initial_mass_g) / days


def carbon_accumulation_peatland(
    npp_g_c_m2_yr: Float64, decomposition_g_c_m2_yr: Float64
) -> Float64:
    """Net carbon accumulation in peatland.

    LARCA = NPP - decomposition

    Args:
        npp_g_c_m2_yr: Net primary productivity (g C/m²/yr).
        decomposition_g_c_m2_yr: Annual decomposition (g C/m²/yr).

    Returns:
        Long-term apparent rate of carbon accumulation (g C/m²/yr).
    """
    return npp_g_c_m2_yr - decomposition_g_c_m2_yr


def bryophyte_desiccation_recovery(
    time_h: Float64, k_recovery: Float64, max_recovery: Float64
) -> Float64:
    """Photosynthetic recovery after rehydration (exponential).

    Pn(t) = Pmax × (1 - exp(-k × t))

    Args:
        time_h: Time after rehydration (h).
        k_recovery: Recovery rate constant (h⁻¹).
        max_recovery: Maximum recoverable Pn fraction (0–1).

    Returns:
        Photosynthesis fraction (0–max_recovery).
    """
    return max_recovery * (1.0 - exp(-k_recovery * time_h))


def nitrogen_deposition_effect(
    n_deposition_kg_ha_yr: Float64, optimal_n_kg_ha_yr: Float64
) -> Float64:
    """Sphagnum growth response to N deposition (hump-shaped simplified).

    response = 1 - |N - N_opt| / N_opt

    Args:
        n_deposition_kg_ha_yr: N deposition rate (kg N/ha/yr).
        optimal_n_kg_ha_yr: Optimal N for maximal growth (kg N/ha/yr, ~2–5).

    Returns:
        Growth response factor (0–1; >1 clamped to 1).
    """
    if optimal_n_kg_ha_yr <= 0.0:
        return 0.0
    var diff = n_deposition_kg_ha_yr - optimal_n_kg_ha_yr
    if diff < 0.0:
        diff = -diff
    var response = 1.0 - diff / optimal_n_kg_ha_yr
    if response < 0.0:
        return 0.0
    return response


def moss_photosynthesis_rate(
    par_umol_m2_s: Float64, pmax: Float64, half_sat_par: Float64,
    water_potential_mpa: Float64
) -> Float64:
    """Moss photosynthesis from Michaelis-Menten light curve × water stress.

    Pn = Pmax × PAR / (Km + PAR) × f(ψ)  where f(ψ) = exp(ψ / ψ_50)

    Args:
        par_umol_m2_s: Photosynthetically active radiation (μmol/m²/s).
        pmax: Maximum photosynthesis (μmol CO2/g/h).
        half_sat_par: Half-saturation PAR Km (μmol/m²/s).
        water_potential_mpa: Moss water potential ψ (MPa; 0 = saturated).

    Returns:
        Net photosynthesis (μmol CO2/g/h).
    """
    var denom = half_sat_par + par_umol_m2_s
    if denom <= 0.0:
        return 0.0
    var light_response = pmax * par_umol_m2_s / denom
    var psi_50 = -2.0  # MPa at 50% inhibition
    var water_factor = exp(water_potential_mpa / (-psi_50))
    if water_factor > 1.0:
        water_factor = 1.0
    return light_response * water_factor


def peat_accumulation_rate(
    productivity_mm_yr: Float64, humification_factor: Float64
) -> Float64:
    """Net peat accumulation rate considering humification.

    PAR = productivity × (1 - humification)

    Args:
        productivity_mm_yr: Sphagnum height growth (mm/yr).
        humification_factor: Fraction lost to decomposition (0–1).

    Returns:
        Net peat accumulation (mm/yr).
    """
    return productivity_mm_yr * (1.0 - humification_factor)


def sphagnum_acidity(
    cation_exchange_capacity: Float64, base_saturation: Float64
) -> Float64:
    """Approximate pH from Sphagnum cation exchange characteristics.

    pH ≈ 3.0 + 2.0 × base_saturation / 100  (empirical for Sphagnum bogs)

    Args:
        cation_exchange_capacity: CEC of Sphagnum (meq/g; ~1.5–2.5).
        base_saturation: Base saturation fraction (%).

    Returns:
        Estimated pH (3.0–5.0 for Sphagnum-dominated systems).
    """
    return 3.0 + 2.0 * base_saturation / 100.0


def patch_colonisation_probability(
    spore_rain: Float64, substrate_suitability: Float64, moisture_factor: Float64
) -> Float64:
    """Probability of bryophyte patch colonisation.

    P_col = spore_rain × suitability × moisture

    Args:
        spore_rain: Spore deposition rate (spores/cm²/yr, normalised 0–1).
        substrate_suitability: Substrate quality score (0–1).
        moisture_factor: Moisture availability (0–1).

    Returns:
        Colonisation probability (0–1).
    """
    var p = spore_rain * substrate_suitability * moisture_factor
    if p > 1.0:
        return 1.0
    return p


def biomass_to_litter_ratio(
    standing_biomass_g_m2: Float64, annual_litter_g_m2_yr: Float64
) -> Float64:
    """Biomass-to-litter production ratio (inverse of turnover rate).

    ratio = biomass / litter_production

    Args:
        standing_biomass_g_m2: Current standing biomass (g/m²).
        annual_litter_g_m2_yr: Annual litter production (g/m²/yr).

    Returns:
        Mean residence time (years).
    """
    if annual_litter_g_m2_yr <= 0.0:
        return 0.0
    return standing_biomass_g_m2 / annual_litter_g_m2_yr
