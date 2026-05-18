"""
biogeochemistry.mojo — Element cycling between biosphere and geosphere. Zero Python imports.

Public API:
  net_ecosystem_production      — NEP = GPP - Re
  carbon_use_efficiency         — CUE = NPP / GPP
  nitrogen_mineralisation       — N-min rate from organic matter
  denitrification_rate          — N2O + N2 from nitrate
  phosphorus_sorption           — Langmuir isotherm
  methane_oxidation             — first-order CH4 removal
  soil_carbon_turnover          — first-order SOC decomposition
  weathering_co2_consumption    — from cation flux
  nitrogen_fixation_estimate    — from acetylene reduction
  global_carbon_budget          — atmospheric growth from fluxes
"""
from std.math import log, exp


fn net_ecosystem_production(
    gpp: Float64, ecosystem_respiration: Float64
) -> Float64:
    """Net ecosystem production: NEP = GPP - Re.

    Args:
        gpp: Gross primary production (g C/m²/yr).
        ecosystem_respiration: Total ecosystem respiration (g C/m²/yr).

    Returns:
        NEP (g C/m²/yr; positive = carbon sink).
    """
    return gpp - ecosystem_respiration


fn carbon_use_efficiency(npp: Float64, gpp: Float64) -> Float64:
    """Carbon use efficiency: CUE = NPP / GPP.

    Args:
        npp: Net primary production (g C/m²/yr).
        gpp: Gross primary production (g C/m²/yr).

    Returns:
        CUE (0–1; typical 0.3–0.6 for terrestrial plants).
    """
    if gpp <= 0.0:
        return 0.0
    return npp / gpp


fn nitrogen_mineralisation(
    organic_n: Float64, mineralisation_rate: Float64, temperature_factor: Float64
) -> Float64:
    """N mineralisation: Nmin = k × Norg × Q10_factor.

    Args:
        organic_n: Soil organic N pool (g N/m²).
        mineralisation_rate: Base rate constant k (per year).
        temperature_factor: Q10-based temperature multiplier.

    Returns:
        Mineralisation flux (g N/m²/yr).
    """
    return mineralisation_rate * organic_n * temperature_factor


fn denitrification_rate(
    nitrate_conc: Float64, denitrifier_biomass: Float64,
    anaerobic_fraction: Float64
) -> Float64:
    """Denitrification rate (simplified Michaelis-Menten).

    D = Vmax × [NO3] / (Km + [NO3]) × biomass × anaerobic_frac

    Args:
        nitrate_conc: Soil nitrate (mg N/kg; Km ≈ 10).
        denitrifier_biomass: Denitrifier C biomass (mg C/kg).
        anaerobic_fraction: Fraction of soil anaerobic microsites (0–1).

    Returns:
        Denitrification rate (mg N/kg/day).
    """
    var km = 10.0
    return 0.1 * (nitrate_conc / (km + nitrate_conc)) * denitrifier_biomass * anaerobic_fraction


fn phosphorus_sorption(
    dissolved_p: Float64, max_sorption: Float64, binding_constant: Float64
) -> Float64:
    """Langmuir P sorption isotherm.

    Q = Qmax × KL × C / (1 + KL × C)

    Args:
        dissolved_p: Dissolved P concentration (mg/L).
        max_sorption: Maximum sorption capacity Qmax (mg P/kg soil).
        binding_constant: Langmuir binding constant KL (L/mg).

    Returns:
        Sorbed P (mg/kg).
    """
    var denom = 1.0 + binding_constant * dissolved_p
    if denom <= 0.0:
        return 0.0
    return max_sorption * binding_constant * dissolved_p / denom


fn methane_oxidation(
    ch4_conc: Float64, oxidation_rate: Float64
) -> Float64:
    """First-order aerobic methane oxidation.

    flux = k × [CH4]

    Args:
        ch4_conc: Methane concentration (μmol/m³).
        oxidation_rate: First-order rate k (per day).

    Returns:
        CH4 oxidation flux (μmol/m³/day).
    """
    return oxidation_rate * ch4_conc


fn soil_carbon_turnover(
    soc_pool: Float64, decomposition_rate: Float64, clay_protection: Float64
) -> Float64:
    """Soil organic carbon decomposition flux.

    flux = k × SOC × (1 - clay_protection)

    Args:
        soc_pool: SOC pool size (Mg C/ha).
        decomposition_rate: Intrinsic decomposition rate k (yr⁻¹).
        clay_protection: Clay-mineral protection factor (0–1).

    Returns:
        Annual decomposition flux (Mg C/ha/yr).
    """
    return decomposition_rate * soc_pool * (1.0 - clay_protection)


fn weathering_co2_consumption(
    cation_flux: Float64, charge_equivalents: Float64
) -> Float64:
    """CO2 consumed by silicate weathering from river cation flux.

    CO2_consumption ≈ cation_flux × charge_equivalents × (44/2) / 1e6

    Args:
        cation_flux: River cation flux (mol/km²/yr).
        charge_equivalents: Moles of CO2 consumed per mole cations (typically 1–2).

    Returns:
        CO2 consumption (t C/km²/yr).
    """
    return cation_flux * charge_equivalents * 44.0 / 2.0 / 1e6


fn nitrogen_fixation_estimate(
    acetylene_reduction: Float64
) -> Float64:
    """N2 fixation from acetylene reduction assay (3:1 ratio).

    N2_fixed = ARA / 3

    Args:
        acetylene_reduction: Acetylene reduction rate (μmol C2H4/h).

    Returns:
        N2 fixation rate (μmol N2/h).
    """
    return acetylene_reduction / 3.0


fn global_carbon_budget(
    fossil_emissions: Float64, land_use_change: Float64,
    land_sink: Float64, ocean_sink: Float64
) -> Float64:
    """Atmospheric CO2 growth rate from global carbon budget.

    ΔC_atm = emissions + LUC - land_sink - ocean_sink

    Args:
        fossil_emissions: Fossil fuel CO2 (Gt C/yr).
        land_use_change: Land-use change emissions (Gt C/yr).
        land_sink: Terrestrial carbon uptake (Gt C/yr).
        ocean_sink: Ocean carbon uptake (Gt C/yr).

    Returns:
        Atmospheric CO2 growth (Gt C/yr; ~5 Gt C/yr recently).
    """
    return fossil_emissions + land_use_change - land_sink - ocean_sink
