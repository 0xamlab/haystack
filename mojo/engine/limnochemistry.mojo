"""
limnochemistry.mojo — Freshwater chemical analysis calculations. Zero Python imports.

Public API:
  carbonate_alkalinity          — total alkalinity from titration
  ionic_strength                — from ion concentrations
  activity_coefficient_davies   — Davies equation for ion activity
  saturation_index_calcite      — Langelier-type SI for lakes
  silicon_weathering_flux       — from river Si export
  redox_pe_eh                   — pe from Eh in natural waters
  phosphorus_fractionation      — TP partitioning
  nitrogen_speciation           — DIN from NH4, NO3, NO2
  doc_light_attenuation         — CDOM from DOC
  epilimnion_mixing_depth        — thermocline from temperature profile
"""
from std.math import log, sqrt, exp


fn carbonate_alkalinity(
    hco3_meq_l: Float64, co3_meq_l: Float64, oh_meq_l: Float64, h_meq_l: Float64
) -> Float64:
    """Total carbonate alkalinity.

    Alk = [HCO3⁻] + 2[CO3²⁻] + [OH⁻] - [H⁺]  (meq/L)

    Args:
        hco3_meq_l: Bicarbonate (meq/L).
        co3_meq_l: Carbonate (meq/L).
        oh_meq_l: Hydroxide (meq/L).
        h_meq_l: Proton concentration (meq/L).

    Returns:
        Total alkalinity (meq/L).
    """
    return hco3_meq_l + 2.0 * co3_meq_l + oh_meq_l - h_meq_l


fn ionic_strength(
    concentrations: Float64, charges_sq: Float64
) -> Float64:
    """Ionic strength: I = 0.5 × Σ(ci × zi²).

    Args:
        concentrations: Sum of ion concentrations (mol/L).
        charges_sq: Sum of charge² × concentration (dimensionless).

    Returns:
        Ionic strength (mol/L).
    """
    return 0.5 * charges_sq


fn activity_coefficient_davies(
    ionic_strength: Float64, charge: Float64
) -> Float64:
    """Davies equation activity coefficient for ion in freshwater.

    log γ = -A × z² × (sqrt(I)/(1+sqrt(I)) - 0.3×I)  with A=0.5085 at 25°C

    Args:
        ionic_strength: Solution ionic strength (mol/L).
        charge: Ion charge z.

    Returns:
        Activity coefficient γ (0–1).
    """
    var a = 0.5085
    var si = sqrt(ionic_strength)
    var log_gamma = -a * charge * charge * (si / (1.0 + si) - 0.3 * ionic_strength)
    return pow_10(log_gamma)


fn pow_10(x: Float64) -> Float64:
    return exp(x * log(10.0))


fn saturation_index_calcite(
    ca_mmol_l: Float64, alk_meq_l: Float64, ph: Float64, temp_c: Float64
) -> Float64:
    """Langelier saturation index for calcite in lake water.

    SI = pH - pH_sat  (simplified linear temperature correction)

    Args:
        ca_mmol_l: Calcium concentration (mmol/L).
        alk_meq_l: Alkalinity (meq/L, ≈ HCO3 at normal pH).
        ph: Measured pH.
        temp_c: Water temperature (°C).

    Returns:
        Saturation index (>0 = calcite precipitation expected).
    """
    if ca_mmol_l <= 0.0 or alk_meq_l <= 0.0:
        return -1.0
    var ph_sat = 11.73 - 0.053 * temp_c - log(ca_mmol_l) / log(10.0) - log(alk_meq_l) / log(10.0)
    return ph - ph_sat


fn silicon_weathering_flux(
    si_conc_umol_l: Float64, discharge_m3_s: Float64, catchment_km2: Float64
) -> Float64:
    """Silica weathering flux from river export.

    flux = C_Si × Q / area  (mol/km²/yr)

    Args:
        si_conc_umol_l: River Si concentration (μmol/L).
        discharge_m3_s: Mean annual discharge (m³/s).
        catchment_km2: Catchment area (km²).

    Returns:
        Si export flux (mol/km²/yr).
    """
    if catchment_km2 <= 0.0:
        return 0.0
    var flux_mol_s = si_conc_umol_l * 1e-6 * discharge_m3_s * 1000.0
    return flux_mol_s * 31557600.0 / catchment_km2


fn redox_pe_eh(eh_mv: Float64, temperature_c: Float64) -> Float64:
    """Convert Eh to pe at given temperature.

    pe = Eh × F / (2.303 × R × T)

    Args:
        eh_mv: Redox potential Eh (mV).
        temperature_c: Water temperature (°C).

    Returns:
        pe (dimensionless electron activity).
    """
    var T_K = temperature_c + 273.15
    var factor = 11604.5 / T_K  # F / (R × 2.303)
    return eh_mv / 1000.0 * factor


fn phosphorus_fractionation(
    total_p_ug_l: Float64, dissolved_p_ug_l: Float64
) -> Float64:
    """Particulate phosphorus fraction.

    PP = TP - DP

    Args:
        total_p_ug_l: Total phosphorus (μg/L).
        dissolved_p_ug_l: Dissolved (filtered <0.45μm) phosphorus (μg/L).

    Returns:
        Particulate P (μg/L).
    """
    var pp = total_p_ug_l - dissolved_p_ug_l
    if pp < 0.0:
        return 0.0
    return pp


fn nitrogen_speciation(
    nh4_mg_l: Float64, no3_mg_l: Float64, no2_mg_l: Float64
) -> Float64:
    """Dissolved inorganic nitrogen sum.

    DIN = NH4-N + NO3-N + NO2-N  (mg N/L)

    Args:
        nh4_mg_l: Ammonium-N (mg N/L).
        no3_mg_l: Nitrate-N (mg N/L).
        no2_mg_l: Nitrite-N (mg N/L).

    Returns:
        DIN (mg N/L).
    """
    return nh4_mg_l + no3_mg_l + no2_mg_l


fn doc_light_attenuation(
    doc_mg_l: Float64, specific_absorption: Float64
) -> Float64:
    """CDOM light attenuation from DOC.

    a_CDOM = aCDOM* × DOC

    Args:
        doc_mg_l: Dissolved organic carbon (mg/L).
        specific_absorption: Specific CDOM absorption coefficient (m²/mg; ~0.02–0.08).

    Returns:
        CDOM absorption (m⁻¹).
    """
    return specific_absorption * doc_mg_l


fn epilimnion_mixing_depth(
    surface_temp_c: Float64, bottom_temp_c: Float64, total_depth_m: Float64
) -> Float64:
    """Approximate epilimnion depth from temperature difference.

    Simplified: mixing_depth ≈ depth × (ΔT_threshold / ΔT_total)

    Args:
        surface_temp_c: Surface water temperature (°C).
        bottom_temp_c: Bottom water temperature (°C).
        total_depth_m: Lake maximum depth (m).

    Returns:
        Estimated thermocline/epilimnion depth (m).
    """
    var delta_t = surface_temp_c - bottom_temp_c
    if delta_t <= 0.0:
        return total_depth_m  # fully mixed
    var threshold = 1.0  # °C/m typical thermocline criterion
    return total_depth_m * threshold / delta_t
